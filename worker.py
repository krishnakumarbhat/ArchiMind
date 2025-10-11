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

def run_analysis(repo_url):
    status = {'status': 'processing', 'result': None, 'error': None}
    with open(config.STATUS_FILE_PATH, 'w') as f:
        json.dump(status, f)

    try:
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

        status['status'] = 'completed'
        status['result'] = {
            'chat_response': docs.get('documentation'),
            'hld_diagram': docs.get('hld'),
            'lld_diagram': docs.get('lld')
        }

    except Exception as e:
        logging.error(f"An error occurred during analysis: {e}")
        status['status'] = 'error'
        status['error'] = str(e)
    
    finally:
        with open(config.STATUS_FILE_PATH, 'w') as f:
            json.dump(status, f)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        repo_url_arg = sys.argv[1]
        run_analysis(repo_url_arg)
    else:
        logging.error("No repository URL provided.")
