# vector_manager.py
"""
Handles vector database operations, including embedding generation and storage.
"""
import chromadb
import ollama
import logging
from typing import Dict, List

class VectorManager:
    """Manages ChromaDB collections and document embeddings."""

    def __init__(self, db_path: str, collection_name: str, embedding_model: str):
        self.db_path = db_path
        self.collection_name = self._sanitize_collection_name(collection_name)
        self.embedding_model = embedding_model
        self.chroma_client = chromadb.PersistentClient(path=self.db_path)
        self.collection = self.chroma_client.get_or_create_collection(name=self.collection_name)
        self.ollama_client = ollama.Client()

    @staticmethod
    def _sanitize_collection_name(name: str) -> str:
        """Sanitizes the collection name for ChromaDB compatibility."""
        return name.replace('-', '_').replace('.', '_')

    def is_empty(self) -> bool:
        """Checks if the collection is empty."""
        return self.collection.count() == 0

    def generate_and_store_embeddings(self, file_contents: Dict[str, str]):
        """Generates and stores embeddings for the given file contents."""
        logging.info(f"Generating embeddings with '{self.embedding_model}' and storing in ChromaDB...")
        total_files = len(file_contents)

        for i, (path, content) in enumerate(file_contents.items(), 1):
            progress = f"[{i}/{total_files}]"
            if not content.strip():
                logging.info(f"{progress} Skipping empty file: {path}")
                continue
            try:
                response = self.ollama_client.embeddings(model=self.embedding_model, prompt=content)
                self.collection.add(
                    embeddings=[response['embedding']],
                    documents=[content],
                    ids=[path]
                )
                logging.info(f"{progress} Embedded and stored: {path}")
            except Exception as e:
                logging.error(f"{progress} Failed to embed {path}: {e}")
        logging.info("All files processed and stored in the vector database.")

    def query_relevant_documents(self, query_text: str, n_results: int = 15) -> List[str]:
        """Queries the collection for documents relevant to the query text."""
        logging.info("Retrieving the most relevant files from the vector database...")
        try:
            query_embedding = self.ollama_client.embeddings(
                model=self.embedding_model,
                prompt=query_text
            )['embedding']
            
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            retrieved_docs = results['documents'][0]
            retrieved_ids = results['ids'][0]

            context = ""
            for path, content in zip(retrieved_ids, retrieved_docs):
                context += f"--- File: {path} ---\n\n{content}\n\n"
            
            logging.info(f"Retrieved {len(retrieved_docs)} files to build context.")
            return context
        except Exception as e:
            logging.error(f"Failed to query the vector database: {e}")
            return ""