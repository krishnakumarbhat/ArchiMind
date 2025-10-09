# ArchiMind - Archi2 (Simplified)

A lightweight Flask application that uses Ollama models to analyze software repositories and provide architectural insights with HLD/LLD diagrams.

## Features

- **Ollama Integration**: Uses `deepseek-r1:1.5b` for analysis and `nomic-embed-text:v1.5` for embeddings
- **Repository Analysis**: Enter a repository URL/path to get AI-powered architectural analysis
- **Interactive Chat**: Ask questions about software architecture
- **Visual Diagrams**: Default HLD and LLD diagrams displayed as Mermaid graphs
- **Simple Design**: Minimal codebase with clean separation of concerns

## Architecture

```
archi2/
├── config.py           # Configuration and prompts
├── ollama_service.py   # Singleton service for Ollama API
├── main.py            # Flask application with routes
├── requirements.txt   # Python dependencies
├── templates/         # HTML templates
│   ├── index3.html
│   └── doc.html
└── static/           # JavaScript files
    └── scripts2.js
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

3. **Start the Flask application**
   ```bash
   python main.py
   ```

4. **Open your browser** and go to `http://localhost:5000`

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

3. **Flask Issues**:
   - Ensure all dependencies are installed from `requirements.txt`

## License

This project is part of the ArchiMind suite for software architecture analysis.
