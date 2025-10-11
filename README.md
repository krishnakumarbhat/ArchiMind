# ArchiMind - Refactored Multi-Agent Edition

A streamlined LangGraph-powered multi-agent system that analyzes repositories using GitPython and GitHub API, stores knowledge in Neo4j, generates architecture diagrams, and answers repository questions with RAG using a local Ollama LLM.

## ✨ Recent Improvements (Refactored Version)

This version has been significantly refactored with the following improvements:

- **🔧 Simplified Architecture**: Reduced file count with one class per file pattern
- **🐙 GitPython Integration**: Primary repository cloning with GitHub API fallback
- **🏗️ Enhanced Design Patterns**: Factory pattern, Singleton pattern, and concurrent processing
- **🧪 Comprehensive Testing**: Unit tests, integration tests, and validation scripts
- **🐳 Docker Support**: Full containerization with docker-compose
- **🚀 CI/CD Pipeline**: GitHub Actions for automated testing and validation
- **📊 Performance**: Concurrent chunk processing for faster embeddings

## Features

- **Ollama Integration**: Uses `deepseek-r1:1.5b` for analysis and `nomic-embed-text:v1.5` for embeddings
- **Dual Repository Support**: GitPython cloning + GitHub API fallback for maximum compatibility
- **Repository Analysis**: Supports both local directories and remote repository URLs
- **Interactive Chat**: RAG-powered Q&A about software architecture  
- **Visual Diagrams**: Auto-generated HLD and LLD diagrams with Mermaid
- **Clean Architecture**: Follows SOLID principles with clear separation of concerns

## Architecture

```
ArchiMind/
├── agents/                  # Multi-agent components (one class per file)
│   ├── __init__.py
│   ├── analysis_agent.py    # Repository structure analysis
│   ├── base.py              # Abstract base agent class
│   ├── chat_agent.py        # RAG-powered Q&A system
│   ├── code_parser_agent.py # GitPython + GitHub API integration
│   ├── diagram_agent.py     # Mermaid diagram generation
│   ├── embedding_agent.py   # Concurrent chunking + embeddings
│   └── graph_agent.py       # Knowledge graph construction
├── stores/                  # Unified data persistence layer
│   ├── __init__.py
│   └── neo4j_store.py       # Neo4j vector + graph storage
├── tests/                   # Comprehensive test suite
│   ├── __init__.py
│   ├── test_ollama_service.py
│   ├── test_repository_service.py
│   └── test_integration.py
├── .github/workflows/       # CI/CD automation
│   └── test.yml            # GitHub Actions pipeline
├── templates/               # Web interface
│   ├── index.html          # Main input page
│   └── doc.html           # Results display
├── static/
│   └── script.js           # Frontend interactions
├── orchestrator.py          # LangGraph workflow coordination
├── repository_service.py    # GitPython-based repo management
├── ollama_service.py        # Singleton Ollama client
├── config.py               # Centralized configuration
├── main.py                 # Flask web application
├── validate_setup.py       # System validation script
├── Dockerfile              # Container definition
├── docker-compose.yml      # Multi-service setup
└── requirements.txt        # Python dependencies
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

## Quick Start

### Option 1: Docker Compose (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd ArchiMind

# Start all services (Neo4j + Ollama + ArchiMind)
docker-compose up -d

# Wait for models to download (check logs)
docker-compose logs -f ollama-setup

# Access the application at http://localhost:5000
```

### Option 2: Manual Setup

1. **Validate your environment**
   ```bash
   cd ArchiMind
   python3 validate_setup.py
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Setup Ollama and Models**
   ```bash
   # Install and start Ollama
   ollama serve &
   
   # Pull required models
   ollama pull deepseek-r1:1.5b
   ollama pull nomic-embed-text:v1.5
   ```

4. **Configure Neo4j**
   ```bash
   # Option A: Use Docker
   docker run -d \
     --name neo4j \
     -p 7474:7474 -p 7687:7687 \
     -e NEO4J_AUTH=neo4j/password \
     -e NEO4J_PLUGINS='["apoc"]' \
     neo4j:5.15-community
   
   # Option B: Install locally from neo4j.com
   ```

5. **Set environment variables**
   ```bash
   export NEO4J_URI=bolt://localhost:7687
   export NEO4J_USERNAME=neo4j  
   export NEO4J_PASSWORD=password
   export OLLAMA_BASE_URL=http://localhost:11434
   # GitHub token is optional - GitPython cloning is used instead
   # export GITHUB_TOKEN=<your_token>
   ```

6. **Start the application**
   ```bash
   python main.py
   ```

7. **Open your browser** and go to `http://localhost:5000`

### Secret management

- The app reads the GitHub token in this order:
  1) `GITHUB_TOKEN` environment variable
  2) `secret.txt` at the repository root (single line token)
  3) `secrets.txt` at the repository root (single line token)

- `secret.txt` is ignored by git via `.gitignore`.


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

## Development & Testing

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=. --cov-report=html

# Run specific test files
python -m pytest tests/test_ollama_service.py -v
python -m pytest tests/test_repository_service.py -v 
python -m pytest tests/test_integration.py -v

# Validate setup
python validate_setup.py
```

### GitHub Actions CI/CD

The project includes automated testing via GitHub Actions:

- **Continuous Integration**: Runs tests on push/PR to main branch
- **Multi-service Testing**: Includes Neo4j service for integration tests
- **Code Quality**: Runs linting (flake8), formatting (black), and security scans
- **Coverage Reports**: Uploads coverage to Codecov

### Development Workflow

1. **Make Changes**: Modify code following the established patterns
2. **Validate**: Run `python validate_setup.py` to check imports
3. **Test**: Run `pytest tests/` to ensure functionality
4. **Format**: Use `black .` and `isort .` for consistent formatting
5. **Commit**: Push changes to trigger CI/CD pipeline

## Design Patterns & Architecture

### Applied Design Patterns

- **Singleton Pattern**: `OllamaService` ensures single instance for efficient resource usage
- **Factory Pattern**: `EmbeddingAgent._create_embedding_service()` for service creation
- **Repository Pattern**: Unified data access through `Neo4jVectorStore` and `Neo4jGraphStore`
- **Service Layer**: Clean separation between web layer (`main.py`) and AI services
- **Agent Pattern**: Modular agents with shared `BaseAgent` interface using LangGraph

### Key Architectural Improvements

- **One Class Per File**: Each module contains exactly one primary class for clarity
- **Dependency Injection**: Services injected into agents rather than hard-coded
- **Concurrent Processing**: Multi-threaded embedding generation for better performance
- **Error Handling**: Comprehensive exception handling with graceful fallbacks
- **Configuration Management**: Centralized config in `config.py` with environment variable support
- **Separation of Concerns**: Clear boundaries between parsing, analysis, storage, and presentation

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
