# ArchiMind - AI-Powered Architecture Analysis

ArchiMind is a full-stack web application that analyzes public GitHub repositories, generates interactive architecture diagrams, and provides a RAG-based chat interface for querying code. Built with Python Flask, Neo4j, and Ollama for local AI processing.

## Features

- **Repository Analysis**: Automatically fetch and analyze GitHub repositories
- **Architecture Diagrams**: Generate High-Level Design (HLD) and Low-Level Design (LLD) diagrams using Vis.js
- **AI Chat Assistant**: RAG-based chat interface powered by Ollama's qwen3:8b model
- **Vector Search**: Semantic code search using nomic-embed-text embeddings
- **Interactive UI**: Modern, responsive interface with tabbed navigation

## Tech Stack

- **Frontend**: HTML, CSS, JavaScript with Vis.js for diagrams
- **Backend**: Python Flask with LangGraph workflow orchestration
- **Database**: Neo4j for both graph and vector storage
- **AI**: Ollama with qwen3:8b for analysis/chat and nomic-embed-text for embeddings
- **Visualization**: Vis.js for interactive network diagrams

## Prerequisites

Before setting up ArchiMind, ensure you have the following installed:

1. **Python 3.8+**
2. **Neo4j 5.0+** (with APOC plugin)
3. **Ollama** with required models
4. **Git** (for repository cloning fallback)

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd ArchiMind
```

### 2. Set up Python Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Set up Neo4j Aura

1. **Create a Neo4j Aura account** at [https://console.neo4j.io](https://console.neo4j.io)
2. **Create a new Aura instance** (Free tier available)
3. **Copy your connection details** (URI, username, password) from the Aura console
4. **Note**: Neo4j Aura includes APOC procedures by default, so no additional setup is needed
5. **Create the vector index** by running the following Cypher query in Neo4j Browser:

```cypher
// Create constraints and indexes
CREATE CONSTRAINT file_path_unique IF NOT EXISTS FOR (f:File) REQUIRE f.path IS UNIQUE;
CREATE CONSTRAINT class_name_unique IF NOT EXISTS FOR (c:Class) REQUIRE c.name IS UNIQUE;
CREATE CONSTRAINT function_name_unique IF NOT EXISTS FOR (f:Function) REQUIRE f.name IS UNIQUE;

// Create performance indexes
CREATE INDEX file_language_idx IF NOT EXISTS FOR (f:File) ON (f.language);
CREATE INDEX class_language_idx IF NOT EXISTS FOR (c:Class) ON (c.language);
CREATE INDEX function_language_idx IF NOT EXISTS FOR (f:Function) ON (f.language);

// Create vector index for embeddings (768 dimensions for nomic-embed-text)
CREATE VECTOR INDEX code_embeddings IF NOT EXISTS 
FOR (c:CodeChunk) ON (c.embedding) 
OPTIONS {indexConfig: {`vector.dimensions`: 768, `vector.similarity_function`: 'cosine'}};
```

### 4. Set up Ollama

1. **Install Ollama** from [https://ollama.ai](https://ollama.ai)
2. **Pull required models**:

```bash
# Pull the chat model
ollama pull qwen3:8b

# Pull the embedding model
ollama pull nomic-embed-text:latest
```

### 5. Configure Environment Variables

**⚠️ Security Notice**: Never commit your `.env` file or credentials to version control! See [SECURITY.md](SECURITY.md) for details.

**Option A: Use the configuration helper (recommended)**
```bash
python configure_aura.py
```

**Option B: Create .env file manually**
Create a `.env` file in the project root:

```env
# Neo4j Aura Configuration
NEO4J_URI=neo4j+s://your-instance-id.databases.neo4j.io
NEO4J_USER=your-username
NEO4J_PASSWORD=your-password

# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=True
```

## Usage

### 1. Start the Application

```bash
# Make sure your Neo4j Aura instance is running
# Make sure Ollama is running with the required models

# Start the Flask application
python app.py
```

The application will be available at `http://localhost:5000`

### 2. Analyze a Repository

1. **Enter a GitHub URL** in the input field (e.g., `https://github.com/username/repository`)
2. **Click "Generate Architecture"** to start the analysis
3. **Wait for processing** (this may take a few minutes for large repositories)
4. **Explore the results** in the three tabs:
   - **Documentation**: View the repository's README
   - **Graph**: Interactive HLD/LLD diagrams with pan/zoom
   - **Chat**: Ask questions about the architecture

### 3. Chat with AI

- Ask questions about the code structure, design patterns, or implementation details
- The AI uses RAG (Retrieval-Augmented Generation) to provide context-aware answers
- Responses are streamed in real-time for better user experience

## Architecture

### Backend Components

- **`app.py`**: Flask application with `/process` and `/chat` endpoints
- **`agents.py`**: LangGraph workflow with four main agents:
  - **Code Parser Agent**: Fetches and parses repository code
  - **Embedding Agent**: Creates vector embeddings for code chunks
  - **Graph Agent**: Builds relationship graphs between code components
  - **Diagram Agent**: Generates Vis.js-compatible diagram data
- **`neo4j_client.py`**: Database operations and vector search

### Frontend Components

- **`templates/index.html`**: Main UI with tabs and input controls
- **`static/script.js`**: JavaScript for API calls, Vis.js rendering, and chat

### Data Flow

1. **Repository Input** → GitHub API or Git Clone
2. **Code Parsing** → Extract functions, classes, imports
3. **Embedding Creation** → Generate vectors for code chunks
4. **Graph Building** → Analyze relationships and dependencies
5. **Diagram Generation** → Create HLD/LLD JSON for Vis.js
6. **Storage** → Save to Neo4j for RAG queries

## Configuration

### Excluded Files/Directories

The parser automatically excludes common non-essential directories:
- `.*` (hidden files)
- `assets/*`, `data/*`, `examples/*`, `images/*`
- `public/*`, `static/*`, `temp/*`, `docs/*`
- `venv/*`, `.venv/*`, `*test*`, `tests/*`
- `node_modules/*`, `dist/*`, `build/*`
- And many more...

### Customization

You can modify the exclusion patterns in `agents.py`:

```python
self.excluded_patterns = [
    r'.*',  # Hidden files
    r'assets/*', r'data/*', r'examples/*',
    # Add your custom patterns here
]
```

## Troubleshooting

### Common Issues

1. **Neo4j Aura Connection Error**
   - Ensure your Aura instance is running
   - Check connection details in `.env` (URI should start with `neo4j+s://`)
   - Verify the vector index was created
   - Check if your Aura instance allows the required APOC procedures

2. **Ollama Model Not Found**
   - Run `ollama list` to check installed models
   - Pull missing models: `ollama pull qwen3:8b`

3. **Repository Access Error**
   - Ensure the repository is public
   - Check GitHub API rate limits
   - Verify the URL format

4. **Memory Issues with Large Repositories**
   - The application processes all files in memory
   - Consider implementing pagination for very large repositories

### Logs

Check the console output for detailed error messages and processing logs.

## Development

### Running Tests

```bash
pytest
```

### Code Structure

```
ArchiMind/
├── app.py                 # Flask application
├── agents.py             # LangGraph workflow agents
├── neo4j_client.py       # Database operations
├── requirements.txt      # Python dependencies
├── templates/
│   └── index.html        # Main UI
├── static/
│   └── script.js         # Frontend JavaScript
└── README.md            # This file
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs for error details
3. Open an issue on GitHub

---

**Note**: This application requires significant computational resources for AI processing. Ensure your system has adequate RAM and processing power for large repositories.