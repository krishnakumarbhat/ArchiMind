# worker.py
"""
This script runs the repository analysis as a standalone process.
"""
import os
import sys
import json
import logging

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
import repo_manager
from vector_manager import VectorManager
from doc_generator import DocGenerator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_analysis(repo_url, analysis_log_id=None):
    status = {'status': 'processing', 'result': None, 'error': None}
    with open(config.STATUS_FILE_PATH, 'w') as f:
        json.dump(status, f)

    try:
        # Update analysis log status if provided
        if analysis_log_id:
            from flask import Flask
            from models import db, AnalysisLog
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
                    log.status = 'processing'
                    db.session.commit()
        
        repo_name = repo_url.split('/')[-1]

        if not repo_manager.clone_repo(repo_url, config.LOCAL_CLONE_PATH):
            raise Exception("Failed to clone repository")

        vector_mgr = VectorManager(
            db_path=config.CHROMA_DB_PATH,
            collection_name=repo_name,
            embedding_model=config.EMBEDDING_MODEL
        )

        if vector_mgr.is_empty():
            all_content = repo_manager.read_repo_files(
                config.LOCAL_CLONE_PATH,
                config.ALLOWED_EXTENSIONS,
                config.IGNORED_DIRECTORIES
            )
            if not all_content:
                raise Exception("No processable files found")
            vector_mgr.generate_and_store_embeddings(all_content)

        query_text = "Generate a complete technical documentation for this software project."
        context = vector_mgr.query_relevant_documents(query_text)

        if not context:
            raise Exception("Failed to retrieve context from vector store")

        doc_gen = DocGenerator(api_key=config.GEMINI_API_KEY, model_name=config.GENERATION_MODEL)
        docs = doc_gen.generate_all_docs(context, repo_name)

        def clean_json(raw_value: str) -> str:
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

        def parse_graph(raw_value, label):
            if not raw_value:
                return {'status': 'error', 'message': f'No {label} data returned.'}
            try:
                normalized = clean_json(raw_value)
                parsed = json.loads(normalized)
                if isinstance(parsed, dict):
                    return {'status': 'ok', 'graph': parsed}
                return {
                    'status': 'error',
                    'message': f'{label} data was not a JSON object.',
                    'raw_preview': normalized[:400]
                }
            except json.JSONDecodeError as exc:
                logging.error(f"Failed to parse {label} JSON: {exc}")
                return {
                    'status': 'error',
                    'message': f'Failed to parse {label} JSON.',
                    'raw_preview': (raw_value or '')[:400]
                }

        hld_result = parse_graph(docs.get('hld'), 'HLD')
        lld_result = parse_graph(docs.get('lld'), 'LLD')

        status['status'] = 'completed'
        status['result'] = {
            'chat_response': docs.get('documentation'),
            'hld_graph': hld_result,
            'lld_graph': lld_result
        }
        
        # Mark analysis as completed in database
        if analysis_log_id:
            with app.app_context():
                log = AnalysisLog.query.get(analysis_log_id)
                if log:
                    log.status = 'completed'
                    from datetime import datetime
                    log.completed_at = datetime.utcnow()
                    db.session.commit()

    except Exception as e:
        logging.error(f"An error occurred during analysis: {e}")
        status['status'] = 'error'
        status['error'] = str(e)
        
        # Mark analysis as failed in database
        if analysis_log_id:
            try:
                with app.app_context():
                    log = AnalysisLog.query.get(analysis_log_id)
                    if log:
                        log.status = 'failed'
                        db.session.commit()
            except:
                pass  # Don't fail the whole process if DB update fails
    
    finally:
        with open(config.STATUS_FILE_PATH, 'w') as f:
            json.dump(status, f)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        repo_url_arg = sys.argv[1]
        analysis_log_id = int(sys.argv[2]) if len(sys.argv) > 2 else None
        run_analysis(repo_url_arg, analysis_log_id)
    else:
        logging.error("No repository URL provided.")
