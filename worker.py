"""
ArchiMind Worker Process
Standalone background worker for repository analysis.
"""
import os
import sys
import json
import logging
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
from services import RepositoryService, VectorStoreService, DocumentationService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class AnalysisWorker:
    """Worker class for background repository analysis."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.repo_service = RepositoryService()
        self.status_file = config.STATUS_FILE_PATH
    
    def _update_status(self, status: dict) -> None:
        """Updates the status file with current analysis state."""
        with open(self.status_file, 'w') as f:
            json.dump(status, f)
    
    def _update_database_log(self, analysis_log_id: int, status: str) -> None:
        """Updates the analysis log in the database."""
        if not analysis_log_id:
            return
        
        try:
            from flask import Flask
            from app import db, AnalysisLog
            
            app = Flask(__name__)
            app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
                'DATABASE_URL',
                'postgresql://localhost/archimind'
            )
            app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
            db.init_app(app)
            
            with app.app_context():
                log = AnalysisLog.query.get(analysis_log_id)
                if log:
                    log.status = status
                    if status == 'completed':
                        log.completed_at = datetime.utcnow()
                    db.session.commit()
        except Exception as e:
            self.logger.warning(f"Failed to update database log: {e}")
    
    def _clean_json_response(self, raw_value: str) -> str:
        """Cleans JSON response from LLM by removing markdown fences."""
        if not raw_value:
            return ''
        
        cleaned = raw_value.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.lstrip('`')
            if cleaned.startswith('json'):
                cleaned = cleaned[len('json'):]
            cleaned = cleaned.strip()
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
        
        cleaned = cleaned.strip()
        if cleaned and cleaned[0] != '{':
            start = cleaned.find('{')
            end = cleaned.rfind('}')
            if start != -1 and end != -1 and end > start:
                cleaned = cleaned[start:end+1]
        
        return cleaned
    
    def _parse_graph_data(self, raw_value: str, label: str) -> dict:
        """Parses and validates graph JSON data."""
        if not raw_value:
            return {'status': 'error', 'message': f'No {label} data returned.'}
        
        try:
            normalized = self._clean_json_response(raw_value)
            parsed = json.loads(normalized)
            if isinstance(parsed, dict):
                return {'status': 'ok', 'graph': parsed}
            return {
                'status': 'error',
                'message': f'{label} data was not a JSON object.',
                'raw_preview': normalized[:400]
            }
        except json.JSONDecodeError as exc:
            self.logger.error(f"Failed to parse {label} JSON: {exc}")
            return {
                'status': 'error',
                'message': f'Failed to parse {label} JSON.',
                'raw_preview': (raw_value or '')[:400]
            }
    
    def run_analysis(self, repo_url: str, analysis_log_id: int = None) -> None:
        """
        Executes the complete repository analysis workflow.
        
        Args:
            repo_url: URL of the repository to analyze
            analysis_log_id: Optional database log ID for tracking
        """
        status = {'status': 'processing', 'result': None, 'error': None}
        self._update_status(status)
        
        try:
            self._update_database_log(analysis_log_id, 'processing')
            
            repo_name = repo_url.split('/')[-1]
            self.logger.info(f"Starting analysis for repository: {repo_name}")
            
            # Clone repository
            if not self.repo_service.clone_repository(repo_url, config.LOCAL_CLONE_PATH):
                raise Exception("Failed to clone repository")
            
            # Initialize vector store
            vector_service = VectorStoreService(
                db_path=config.CHROMA_DB_PATH,
                collection_name=repo_name,
                embedding_model=config.EMBEDDING_MODEL
            )
            
            # Generate embeddings if needed
            if vector_service.is_empty():
                file_contents = self.repo_service.read_repository_files(
                    config.LOCAL_CLONE_PATH,
                    config.ALLOWED_EXTENSIONS,
                    config.IGNORED_DIRECTORIES
                )
                if not file_contents:
                    raise Exception("No processable files found in repository")
                vector_service.generate_embeddings(file_contents)
            
            # Query relevant context
            query_text = "Generate a complete technical documentation for this software project."
            context = vector_service.query_similar_documents(query_text)
            
            if not context:
                raise Exception("Failed to retrieve context from vector store")
            
            # Generate documentation
            doc_service = DocumentationService(
                api_key=config.GEMINI_API_KEY,
                model_name=config.GENERATION_MODEL
            )
            docs = doc_service.generate_all_documentation(context, repo_name)
            
            # Parse graph data
            hld_result = self._parse_graph_data(docs.get('hld'), 'HLD')
            lld_result = self._parse_graph_data(docs.get('lld'), 'LLD')
            
            # Update status with results
            status['status'] = 'completed'
            status['result'] = {
                'chat_response': docs.get('documentation'),
                'hld_graph': hld_result,
                'lld_graph': lld_result
            }
            
            self._update_database_log(analysis_log_id, 'completed')
            self.logger.info("Analysis completed successfully")
            
        except Exception as e:
            self.logger.error(f"Analysis failed: {e}")
            status['status'] = 'error'
            status['error'] = str(e)
            self._update_database_log(analysis_log_id, 'failed')
        
        finally:
            self._update_status(status)


def main():
    """Main entry point for worker process."""
    if len(sys.argv) < 2:
        logging.error("No repository URL provided.")
        sys.exit(1)
    
    repo_url = sys.argv[1]
    analysis_log_id = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    worker = AnalysisWorker()
    worker.run_analysis(repo_url, analysis_log_id)


if __name__ == '__main__':
    main()
