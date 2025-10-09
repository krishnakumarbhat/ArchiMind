"""
Configuration file for Ollama models and application settings.
"""

# Ollama Model Configuration
OLLAMA_BASE_URL = "http://localhost:11434"

# Model names
LLM_MODEL = "deepseek-r1:1.5b"
EMBEDDING_MODEL = "nomic-embed-text:v1.5"

# Default dummy graphs - Separate HLD and LLD diagrams
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

# Analysis prompts
ANALYSIS_PROMPT_TEMPLATE = """
Analyze the following repository information and provide architectural insights:

Repository URL/Path: {repo_input}

Provide a brief analysis covering:
1. Suggested High-Level Design (HLD) architecture
2. Suggested Low-Level Design (LLD) components
3. Key design patterns to use
4. Technology stack recommendations

Keep the response concise and structured.
"""

CHAT_PROMPT_TEMPLATE = """
You are an architecture assistant. Answer the following question about software architecture:

Question: {user_message}

Provide a clear, concise answer focusing on architectural best practices.
"""
