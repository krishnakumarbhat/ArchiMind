# main.py
"""
Main script to run the RAG-based documentation generation workflow.
"""
import argparse
import logging

# Import configurations and managers
import config
import repo_manager
from vector_manager import VectorManager
from doc_generator import DocGenerator

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main(repo_url: str):
    """Main function to run the documentation generation workflow."""
    repo_name = repo_url.split('/')[-1]

    # 1. Clone the repository
    if not repo_manager.clone_repo(repo_url, config.LOCAL_CLONE_PATH):
        logging.error("Exiting due to repository cloning failure.")
        return

    # 2. Initialize the vector manager
    vector_mgr = VectorManager(
        db_path=config.CHROMA_DB_PATH,
        collection_name=repo_name,
        embedding_model=config.EMBEDDING_MODEL
    )

    # 3. Embed files if the collection is empty
    if vector_mgr.is_empty():
        logging.info(f"Vector store for '{repo_name}' is empty. Proceeding with embedding.")
        all_content = repo_manager.read_repo_files(
            config.LOCAL_CLONE_PATH,
            config.ALLOWED_EXTENSIONS,
            config.IGNORED_DIRECTORIES
        )
        if not all_content:
            logging.warning("No processable files found. Exiting.")
            return
        vector_mgr.generate_and_store_embeddings(all_content)
    else:
        logging.info(f"Embeddings already exist for '{repo_name}'. Skipping embedding process.")

    # 4. Generate the final documentation
    query_text = (
        "Generate a complete technical documentation for this software project, "
        "including architecture, workflow, and a breakdown of key components."
    )
    context = vector_mgr.query_relevant_documents(query_text)

    if not context:
        logging.error("Failed to retrieve context from vector store. Cannot generate documentation.")
        return

    try:
        doc_gen = DocGenerator(api_key=config.GEMINI_API_KEY, model_name=config.GENERATION_MODEL)
        documentation = doc_gen.generate_documentation(context, repo_name)
        
        if documentation:
            output_filename = f"{repo_name}_documentation.md"
            with open(output_filename, 'w', encoding='utf-8') as f:
                f.write(documentation)
            logging.info(f"Successfully generated and saved documentation to '{output_filename}'")
        else:
            logging.error("Documentation generation failed.")
    except Exception as e:
        logging.error(f"An error occurred during documentation generation: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate technical documentation for a GitHub repository.")
    parser.add_argument(
        "repo_url",
        type=str,
        help="The URL of the GitHub repository to document."
    )
    args = parser.parse_args()
    
    main(args.repo_url)