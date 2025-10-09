# ArchiMind - Archi2 (Multi-Agent Edition)

A LangGraph-powered multi-agent system that analyzes GitHub repositories via the GitHub API, stores knowledge in Neo4j, generates architecture diagrams, and answers repository questions with RAG using a local Ollama LLM.

## Features

- **Ollama Integration**: Uses `deepseek-r1:1.5b` for analysis and `nomic-embed-text:v1.5` for embeddings
- **Repository Analysis**: Enter a repository URL/path to get AI-powered architectural analysis
- **Interactive Chat**: Ask questions about software architecture
- **Visual Diagrams**: Default HLD and LLD diagrams displayed as Mermaid graphs
- **Simple Design**: Minimal codebase with clean separation of concerns

## Architecture

```
archi2/
├── agents/
│   ├── analysis_agent.py    # Summarizes repository structure
│   ├── base.py              # Shared agent abstractions
│   ├── chat_agent.py        # RAG-powered Q&A
│   ├── code_parser_agent.py # GitHub tree/blob ingestion
│   ├── diagram_agent.py     # Mermaid HLD/LLD generation
│   ├── embedding_agent.py   # Chunking + embeddings
│   └── graph_agent.py       # Knowledge graph builder
├── stores/
│   └── neo4j_store.py       # Vector + graph persistence in Neo4j
├── orchestrator.py          # LangGraph workflow definitions
├── config.py                # Configuration, prompts, environment variables
├── ollama_service.py        # Ollama HTTP client (singleton)
├── main.py                  # Flask API + HTML views
├── templates/               # HTML templates (`index3.html`, `doc.html`)
├── static/                  # Frontend assets (`scripts2.js`)
└── requirements.txt         # Python dependencies
```

## Prerequisites

1. **Ollama Installation**: Install Ollama from [ollama.com](https://ollama.com)
2. **Required Models**: Pull the specified models:
   ```bash
   ollama pull deepseek-r1:1.5b
   ollama pull nomic-embed-text:v1.5
   ```
3. **Python Dependencies**: Install required packages:
   ```bash
   pip install -r requirements.txt
   ```

## Setup

1. **Clone or navigate to the project directory**
   ```bash
   cd c:\Users\ouymc2\Desktop\ArchiMind\archi2
   ```

2. **Ensure Ollama is running**
   ```bash
   ollama serve  # Run in a separate terminal
   ```

3. **Configure environment variables (optional but recommended)**
   ```bash
   export OLLAMA_BASE_URL=http://localhost:11434
   export GITHUB_TOKEN=<your_personal_access_token>
   export NEO4J_URI=bolt://localhost:7687
   export NEO4J_USERNAME=neo4j
   export NEO4J_PASSWORD=<your_password>
   ```

4. **Start the Flask application**
   ```bash
   python main.py
   ```

5. **Open your browser** and go to `http://localhost:5000`

## Usage

1. **Repository Analysis**:
   - Enter a repository URL or path in the input field
   - Click "Analyze" to get AI-powered architectural insights
   - View results on the documentation page

2. **Interactive Chat**:
   - Ask questions about software architecture
   - Get responses from the deepseek-r1 model

## API Endpoints

- `GET /` - Main input page
- `POST /api/analyze` - Analyze repository
- `POST /api/chat` - Chat with architecture assistant
- `GET /doc` - View analysis results

## Design Patterns Used

- **Singleton Pattern**: `OllamaService` class ensures single instance
- **Service Layer**: Clean separation between web layer and AI services
- **Configuration Management**: Centralized config in `config.py`

## Models

- **LLM**: `deepseek-r1:1.5b` - For text generation and analysis
- **Embeddings**: `nomic-embed-text:v1.5` - For text similarity (currently not used but available)

## Troubleshooting

1. **Ollama Connection Issues**:
   - Ensure Ollama is running on `http://localhost:11434`
   - Check model availability with `ollama list`

2. **Model Not Found**:
   - Pull required models: `ollama pull deepseek-r1:1.5b` and `ollama pull nomic-embed-text:v1.5`

3. **Neo4j Connectivity**:
   - Verify the database is running and credentials match environment variables
   - Ensure APOC / vector indexes are enabled in Neo4j 5+

4. **Flask Issues**:
   - Ensure all dependencies are installed from `requirements.txt`

## License

This project is part of the ArchiMind suite for software architecture analysis.
