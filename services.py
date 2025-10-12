"""
ArchiMind Services Module
Consolidated service classes with design patterns (Singleton, Factory, Service Layer)
"""
import os
import logging
import time
from typing import Dict, List, Set, Optional
import git
import chromadb
import ollama
from google import genai


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""
    pass


class RepositoryService:
    """
    Repository management service with Singleton pattern.
    Handles Git repository cloning and file reading operations.
    """
    _instance: Optional['RepositoryService'] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.logger = logging.getLogger(self.__class__.__name__)
            self._initialized = True
    
    def clone_repository(self, repo_url: str, local_path: str) -> bool:
        """
        Clones a GitHub repository if the local path doesn't exist.
        
        Args:
            repo_url: URL of the Git repository
            local_path: Local path to clone the repository
            
        Returns:
            True if successful, False otherwise
        """
        if os.path.exists(local_path):
            self.logger.info(f"Repository already exists at: {local_path}. Skipping clone.")
            return True
        
        self.logger.info(f"Cloning repository from {repo_url} to {local_path}...")
        try:
            git.Repo.clone_from(repo_url, local_path)
            self.logger.info("Repository cloned successfully.")
            return True
        except git.exc.GitCommandError as e:
            self.logger.error(f"Error cloning repository: {e}")
            return False
    
    def read_repository_files(
        self,
        repo_path: str,
        allowed_extensions: Set[str],
        ignored_dirs: Set[str]
    ) -> Dict[str, str]:
        """
        Reads all allowed text files from the repository.
        
        Args:
            repo_path: Path to the repository
            allowed_extensions: Set of allowed file extensions
            ignored_dirs: Set of directory names to ignore
            
        Returns:
            Dictionary mapping relative file paths to their contents
        """
        file_contents = {}
        self.logger.info("Reading files from the repository...")
        
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            for file in files:
                if any(file.endswith(ext) for ext in allowed_extensions):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            relative_path = os.path.relpath(file_path, repo_path)
                            file_contents[relative_path] = f.read()
                    except Exception as e:
                        self.logger.warning(f"Could not read file {file_path}: {e}")
        
        self.logger.info(f"Found and read {len(file_contents)} files.")
        return file_contents


class VectorStoreService:
    """
    Vector database service using ChromaDB with Singleton pattern.
    Manages embeddings generation and similarity search.
    """
    _instances: Dict[str, 'VectorStoreService'] = {}
    
    def __new__(cls, db_path: str, collection_name: str, embedding_model: str):
        key = f"{db_path}:{collection_name}"
        if key not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[key] = instance
        return cls._instances[key]
    
    def __init__(self, db_path: str, collection_name: str, embedding_model: str):
        if not hasattr(self, '_initialized'):
            self.db_path = db_path
            self.collection_name = self._sanitize_collection_name(collection_name)
            self.embedding_model = embedding_model
            self.logger = logging.getLogger(self.__class__.__name__)
            self._initialize_database()
            self._initialized = True
    
    def _initialize_database(self):
        """Initializes ChromaDB client and collection."""
        try:
            self.chroma_client = chromadb.PersistentClient(path=self.db_path)
            self.collection = self.chroma_client.get_or_create_collection(
                name=self.collection_name
            )
            self.ollama_client = ollama.Client()
            self.logger.info(f"Vector store initialized: {self.collection_name}")
        except Exception as e:
            self.logger.error(f"Failed to initialize vector store: {e}")
            raise ConfigurationError(f"Vector store initialization failed: {e}")
    
    @staticmethod
    def _sanitize_collection_name(name: str) -> str:
        """Sanitizes the collection name for ChromaDB compatibility."""
        return name.replace('-', '_').replace('.', '_').replace('/', '_')
    
    def is_empty(self) -> bool:
        """Checks if the collection is empty."""
        return self.collection.count() == 0
    
    def generate_embeddings(self, file_contents: Dict[str, str]) -> None:
        """
        Generates and stores embeddings for the given file contents.
        
        Args:
            file_contents: Dictionary mapping file paths to their contents
        """
        self.logger.info(f"Generating embeddings with '{self.embedding_model}'...")
        total_files = len(file_contents)
        
        for i, (path, content) in enumerate(file_contents.items(), 1):
            progress = f"[{i}/{total_files}]"
            if not content.strip():
                self.logger.info(f"{progress} Skipping empty file: {path}")
                continue
            
            try:
                response = self.ollama_client.embeddings(
                    model=self.embedding_model,
                    prompt=content
                )
                self.collection.add(
                    embeddings=[response['embedding']],
                    documents=[content],
                    ids=[path]
                )
                self.logger.info(f"{progress} Embedded and stored: {path}")
            except Exception as e:
                self.logger.error(f"{progress} Failed to embed {path}: {e}")
        
        self.logger.info("All files processed and stored in vector database.")
    
    def query_similar_documents(self, query_text: str, n_results: int = 15) -> str:
        """
        Queries the collection for documents similar to the query text.
        
        Args:
            query_text: Query text to search for
            n_results: Number of results to return
            
        Returns:
            Concatenated context string from retrieved documents
        """
        self.logger.info("Retrieving relevant files from vector database...")
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
            
            self.logger.info(f"Retrieved {len(retrieved_docs)} files to build context.")
            return context
        except Exception as e:
            self.logger.error(f"Failed to query vector database: {e}")
            return ""


class DocumentationService:
    """
    Documentation generation service using Google Gemini API.
    Implements Factory pattern for different documentation types.
    """
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-pro", chat_model_name: Optional[str] = None):
        self.model_name = model_name
        self.chat_model_name = chat_model_name or model_name
        self.logger = logging.getLogger(self.__class__.__name__)
        self._initialize_client(api_key)
    
    def _initialize_client(self, api_key: str) -> None:
        """Initializes the Gemini API client."""
        try:
            self.client = genai.Client(api_key=api_key)
            self.logger.info("Gemini API client initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to configure Gemini API: {e}")
            raise ConfigurationError(f"Gemini API initialization failed: {e}")
    
    def _generate_content(self, prompt: str, model_override: Optional[str] = None) -> str:
        """
        Helper method to generate content from a prompt.
        
        Args:
            prompt: Input prompt for generation
            
        Returns:
            Generated text content
        """
        self.logger.info("Sending context to Gemini API...")
        time.sleep(2)  # Rate limiting
        target_model = model_override or self.model_name
        try:
            response = self.client.models.generate_content(
                model=target_model,
                contents=prompt
            )
            return response.text
        except Exception as e:
            self.logger.error(f"Error calling Gemini API ({target_model}): {e}")
            return ""

    def generate_chat_summary(self, context: str, repo_name: str) -> str:
        """
        Generates a conversational summary of the repository for chat onboarding.
        """
        prompt = f"""
        You are an enthusiastic architecture assistant helping engineers explore the repository '{repo_name}'.
        Using strictly the provided repository context, craft a concise conversational summary (3-4 short paragraphs or bullet groups)
        highlighting the project's purpose, key components, architecture style, and any standout integrations.
        Avoid filler phrases and stay factual to the context.

        --- RELEVANT CONTEXT ---
        {context}
        ---
        """
        return self._generate_content(prompt, model_override=self.chat_model_name)

    def generate_chat_response(self, context: str, repo_name: str, question: str) -> str:
        """
        Generates a contextual response for chat interactions.
        """
        prompt = f"""
        You are an architecture copilot for '{repo_name}'.
        Answer the user's question using ONLY the supplied context. Be specific about services, data flow, and technologies mentioned.
        If the context lacks the necessary information, clearly state that and suggest where the answer might live in the codebase.

        --- USER QUESTION ---
        {question}
        ---

        --- RELEVANT CONTEXT ---
        {context}
        ---
        """
        return self._generate_content(prompt, model_override=self.chat_model_name)
    
    def generate_documentation(self, context: str, repo_name: str) -> str:
        """
        Generates comprehensive technical documentation.
        
        Args:
            context: Concatenated file contents as context
            repo_name: Name of the repository
            
        Returns:
            Generated documentation in Markdown format
        """
        prompt = f"""
        You are a principal software architect. Using ONLY the supplied project context, craft a
        chapter-wise technical handbook for the '{repo_name}' repository in GitHub-flavoured Markdown.

        Strictly follow the structure below:

        # {repo_name} Architecture Handbook
        - Concise executive summary bullet list (<=5 bullets)
        - Table of contents linking to every chapter anchor (use Markdown links like [Chapter 1](#chapter-1-title))

        ## Chapter 1: System Overview
        ### Objectives
        ### Core Capabilities
        ### Technology Stack

        ## Chapter 2: Architecture Blueprint
        ### Architectural Style
        ### Key Services & Responsibilities
        ### External Integrations

        ## Chapter 3: Data & Storage
        ### Data Flow Summary
        ### Persistent Stores
        ### Caching / Messaging

        ## Chapter 4: Runtime Behaviour
        ### Primary Execution Flow
        ### Error Handling & Resilience
        ### Observability

        ## Chapter 5: Extension Roadmap
        ### High-Impact Enhancements
        ### Tech Debt / Risks
        ### Deployment Considerations

        Rules:
        - Start every chapter heading exactly with "## Chapter N: ...".
        - Keep sub-sections concise (3-6 sentences or bullet lists).
        - Prefer tables where they improve clarity.
        - Never invent functionality that is absent from the context.
        - Use inline code formatting for important symbols, file names, APIs, or commands.

        --- RELEVANT CONTEXT ---
        {context}
        ---

        Return only the Markdown document.
        """
        return self._generate_content(prompt)
    
    def generate_high_level_design(self, context: str, repo_name: str) -> str:
        """
        Generates High-Level Design (HLD) graph definition.
        
        Args:
            context: Concatenated file contents as context
            repo_name: Name of the repository
            
        Returns:
            JSON string representing HLD graph structure
        """
        prompt = f"""
        You are a senior software architect. From the supplied context of '{repo_name}', craft a JSON
        specification for a Mermaid system-context diagram. The output will be consumed by the frontend
        and rendered with Mermaid.js.

        Output a single JSON object with the exact shape below (no Markdown code fences):
        {{
          "title": "<short name>",
          "description": "<one sentence summary>",
          "mermaid_code": "graph TD; ..."
        }}

        Rules for `mermaid_code`:
        - Use `graph TD` layout.
        - Include 6-12 nodes covering clients, services, databases, and external systems.
        - Use descriptive IDs like `Client[Web Client]`, `Service_API[Flask API]` etc.
        - Represent interactions with directional edges using `-->` and add `|labels|` where helpful.
        - Group related nodes with Mermaid subgraphs when appropriate (e.g., `subgraph Services`).
        - Derive all names strictly from the provided context. Do not invent technologies.

        --- RELEVANT CONTEXT ---
        {context}
        ---

        Return only valid JSON.
        """
        return self._generate_content(prompt)

    def generate_low_level_design(self, context: str, repo_name: str) -> str:
        """
        Generates Low-Level Design (LLD) workflow definition.
        
        Args:
{{ ... }}
            repo_name: Name of the repository
            
        Returns:
            JSON string representing LLD workflow structure
        """
        prompt = f"""
        You are a staff-level engineer. Using the provided context for '{repo_name}', produce a JSON
        Mermaid sequence diagram that captures the primary runtime flow end-to-end.

        Output a single JSON object with this structure (no Markdown fences):
        {{
          "title": "<short workflow name>",
          "description": "<one sentence summary>",
          "mermaid_code": "sequenceDiagram\n  participant ..."
        }}

        Rules for `mermaid_code`:
        - Use `sequenceDiagram` syntax.
        - Include 6-10 participants covering clients, services, databases, workers, and external APIs.
        - Describe the main happy path plus at least one error or alternate branch using `alt`/`opt` blocks.
        - Use concise arrow labels that map directly to operations found in the supplied context.
        - Derive every participant and message from the repository context only; do not hallucinate.

        --- RELEVANT CONTEXT ---
        {context}
        ---

        Return only valid JSON.
        """
        return self._generate_content(prompt)
    
    def generate_all_documentation(self, context: str, repo_name: str) -> Dict[str, str]:
        """
        Factory method to generate all documentation types.
        
        Args:
            context: Concatenated file contents as context
            repo_name: Name of the repository
            
        Returns:
            Dictionary with documentation, hld, and lld keys
        """
        return {
            'documentation': self.generate_documentation(context, repo_name),
            'hld': self.generate_high_level_design(context, repo_name),
            'lld': self.generate_low_level_design(context, repo_name),
            'chat_summary': self.generate_chat_summary(context, repo_name)
        }
