"""Configuration for the ArchiMind archi2 multi-agent system."""

from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv


load_dotenv()


# Ollama Model Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Model names
LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "deepseek-r1:1.5b")
EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text:v1.5")

# GitHub parsing configuration
MAX_FILE_SIZE = int(os.getenv("ARCHIMIND_MAX_FILE_SIZE", "200000"))  # bytes
MAX_CODE_FILES = int(os.getenv("ARCHIMIND_MAX_CODE_FILES", "200"))

# Embedding chunk settings
CHUNK_SIZE = int(os.getenv("ARCHIMIND_CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("ARCHIMIND_CHUNK_OVERLAP", "120"))

# Neo4j configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
NEO4J_VECTOR_INDEX = os.getenv("NEO4J_VECTOR_INDEX", "archimind_embeddings")
NEO4J_GRAPH_NAMESPACE = os.getenv("NEO4J_GRAPH_NAMESPACE", "archimind")

# Default dummy graphs - Separate HLD and LLD diagrams for fallback rendering
DEFAULT_HLD_MERMAID = """
graph TD
    subgraph HLD["High-Level Design"]
        A[Client] --> B[API Gateway]
        B --> C[User Service]
        B --> D[Product Service]
        B --> E[Order Service]
        C --> F[(User DB)]
        D --> G[(Product DB)]
        E --> H[(Order DB)]
    end
"""

DEFAULT_LLD_MERMAID = """
graph TD
    subgraph LLD["Low-Level Design: User Service"]
        AA[API Gateway] --> BB[Controller]
        BB --> CC[Service Layer]
        CC --> DD[Repository]
        DD --> EE[(Database)]
        CC --> FF[External APIs]
    end
"""

# Prompt templates
ANALYSIS_PROMPT_TEMPLATE = """
You are an expert software architect. Analyze the following repository structure and metadata.

Repository URL: {repo_url}
Default Branch: {default_branch}
Description: {description}

File Summary:
{file_overview}

Provide:
1. A concise system overview
2. Key architectural components
3. Suggested high-level architecture
4. Notable design patterns or risks
"""

EMBEDDING_SUMMARY_PROMPT = """
You are generating semantic chunks for architecture analysis. Summarize the following code segment in 3-4 sentences focusing on its purpose, inputs, outputs, and dependencies.

Code Path: {path}
Code:
{code}
"""

GRAPH_PROMPT_TEMPLATE = """
You are building a knowledge graph of the repository. Based on the provided summaries and dependencies, produce structured JSON with nodes and relationships.

Each node must include: id, label, type (module, class, function, component), description.
Each relationship must include: source, target, type, description.

Context:
{context}
"""

DIAGRAM_PROMPT_TEMPLATE = """
You are an architecture diagram specialist. Using the knowledge graph description below, produce two Mermaid diagrams in JSON with keys `hld` and `lld`.

HLD should highlight major components and data flow.
LLD should focus on internal module/class interactions.

Knowledge Graph:
{graph_description}
"""

CHAT_PROMPT_TEMPLATE = """
You are an architecture assistant. Use the provided context snippets from the knowledge graph and embeddings to answer the question.

Question: {user_message}
Context:
{context}

Answer in 3-5 paragraphs, referencing relevant components.
"""

def get_github_token() -> Optional[str]:
    """Return GitHub token from environment variables."""

    token = os.getenv("GITHUB_TOKEN")
    return token.strip() if token else None
