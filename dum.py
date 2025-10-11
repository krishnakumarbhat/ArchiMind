# doc_generator.py

import os
import base64
import logging
import argparse
import requests
import ollama
import chromadb
import google.generativeai as genai
from dotenv import load_dotenv

# --- Configuration ---
# Load environment variables from a .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Securely load API keys from environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") # Optional, but increases API rate limit

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set.")

# Models
EMBEDDING_MODEL = 'nomic-embed-text'
GENERATION_MODEL = 'gemini-1.5-pro-latest'

# File and Directory Settings
ALLOWED_EXTENSIONS = {
    '.py', '.md', '.txt', '.js', '.ts', '.html', '.css',
    '.json', '.yaml', '.yml', '.sh', 'Dockerfile'
}
IGNORED_DIRECTORIES = {
    '.git', '__pycache__', 'node_modules', 'dist',
    'build', '.vscode', 'venv', '.idea', 'docs'
}


def get_repo_contents_from_api(owner: str, repo: str, path: str = "") -> dict:
    """
    Recursively fetches file contents from a GitHub repository using the API.
    """
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    file_contents = {}

    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        contents = response.json()

        for item in contents:
            if item['type'] == 'dir' and item['name'] not in IGNORED_DIRECTORIES:
                file_contents.update(get_repo_contents_from_api(owner, repo, item['path']))
            elif item['type'] == 'file' and any(item['name'].endswith(ext) for ext in ALLOWED_EXTENSIONS):
                file_response = requests.get(item['download_url'], headers=headers)
                file_response.raise_for_status()
                # Decode from base64 if content is encoded, otherwise use text
                if 'content' in item:
                    content = base64.b64decode(item['content']).decode('utf-8', errors='ignore')
                else:
                    content = file_response.text
                file_contents[item['path']] = content
                logging.info(f"Fetched file: {item['path']}")

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching repo contents from {api_url}: {e}")
    
    return file_contents


def main(repo_url: str):
    """Main function to run the RAG-based documentation workflow."""
    try:
        owner, repo_name = repo_url.rstrip('/').split('/')[-2:]
    except ValueError:
        logging.error("Invalid GitHub URL format. Expected 'https://github.com/owner/repo'")
        return

    # 1. Fetch repository files via GitHub API
    logging.info(f"Fetching repository contents for {owner}/{repo_name}...")
    all_content = get_repo_contents_from_api(owner, repo_name)
    if not all_content:
        logging.error("No processable files found or failed to fetch repository data. Exiting.")
        return
    logging.info(f"Successfully fetched {len(all_content)} files.")

    # 2. Setup in-memory vector database and generate embeddings
    logging.info("Initializing in-memory vector database...")
    chroma_client = chromadb.Client() # In-memory client
    collection_name = repo_name.replace('-', '_').replace('.', '_')
    collection = chroma_client.get_or_create_collection(name=collection_name)
    ollama_client = ollama.Client()

    logging.info(f"Generating embeddings with '{EMBEDDING_MODEL}'...")
    total_files = len(all_content)
    for i, (path, content) in enumerate(all_content.items(), 1):
        if not content.strip():
            logging.info(f"[{i}/{total_files}] Skipping empty file: {path}")
            continue
        try:
            response = ollama_client.embeddings(model=EMBEDDING_MODEL, prompt=content)
            collection.add(
                embeddings=[response['embedding']],
                documents=[content],
                ids=[path]
            )
            logging.info(f"[{i}/{total_files}] Embedded and stored: {path}")
        except Exception as e:
            logging.error(f"[{i}/{total_files}] Failed to embed {path}: {e}")
    logging.info("All files embedded in the in-memory vector store.")

    # 3. Query vector store to build context for the LLM
    query_text = (
        "Generate a complete technical documentation for this software project, "
        "including architecture, workflow, and a breakdown of key components."
    )
    logging.info("Querying vector store for relevant context...")
    query_embedding = ollama_client.embeddings(model=EMBEDDING_MODEL, prompt=query_text)['embedding']
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(15, len(all_content)) # Retrieve up to 15 documents
    )
    
    retrieved_docs = results['documents'][0]
    retrieved_ids = results['ids'][0]
    
    context = ""
    for path, content in zip(retrieved_ids, retrieved_docs):
        context += f"--- File: {path} ---\n\n{content}\n\n"
    
    logging.info(f"Retrieved {len(retrieved_docs)} files to build context for Gemini.")

    # 4. Generate the final documentation using Gemini
    prompt = f"""
    You are a world-class senior software architect. Your task is to generate a comprehensive
    technical documentation for the '{repo_name}' project.

    Based ONLY on the following context, create a single, well-structured Markdown document.

    The documentation must include:
    1.  **Project Overview**: A summary of the project's purpose and technology stack.
    2.  **Architecture Diagram**: A Mermaid.js `graph TD` diagram of the main components.
    3.  **Workflow Diagram**: A Mermaid.js `flowchart TD` diagram of the primary workflow.
    4.  **Core Components Analysis**: A breakdown of the key files provided, explaining their purpose.

    --- RELEVANT CONTEXT ---
    {context}
    ---

    Generate the complete documentation now.
    """
    
    logging.info("Sending context to Gemini for documentation generation...")
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(GENERATION_MODEL)
        response = model.generate_content(prompt)
        
        output_filename = f"{repo_name}_documentation.md"
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(response.text)
        logging.info(f"✅ Successfully generated and saved documentation to '{output_filename}'")
    except Exception as e:
        logging.error(f"❌ An error occurred while calling the Gemini API: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate technical documentation for a GitHub repository using its API.")
    parser.add_argument("repo_url", type=str, help="The full URL of the GitHub repository (e.g., https://github.com/owner/repo).")
    args = parser.parse_args()
    main(args.repo_url)