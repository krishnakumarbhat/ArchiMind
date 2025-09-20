# Quick Start Guide - Neo4j Aura

This guide will help you get ArchiMind running with Neo4j Aura in just a few minutes.

## Prerequisites

- Python 3.8+
- Ollama installed and running
- Neo4j Aura account (free tier available)

## Step-by-Step Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set up Ollama Models
```bash
ollama pull qwen3:8b
ollama pull nomic-embed-text:latest
```

### 3. Create Neo4j Aura Instance

1. Go to [https://console.neo4j.io](https://console.neo4j.io)
2. Sign up for a free account
3. Click "New Instance"
4. Choose "Free" tier
5. Give your instance a name (e.g., "archimind")
6. Wait for the instance to be created
7. Copy the connection details (URI, username, password)

### 4. Configure ArchiMind
```bash
python configure_aura.py
```

Follow the prompts to enter your Aura connection details.

### 5. Set up Database Schema
```bash
python setup_neo4j.py
```

### 6. Test the Setup (Optional)
```bash
python test_setup.py
```

### 7. Start the Application
```bash
python run.py
```

## Access the Application

Open your browser and go to: `http://localhost:5000`

## First Use

1. Enter a GitHub repository URL (e.g., `https://github.com/octocat/Hello-World`)
2. Click "Generate Architecture"
3. Wait for processing to complete
4. Explore the three tabs:
   - **Documentation**: View the README
   - **Graph**: Interactive architecture diagrams
   - **Chat**: Ask questions about the code

## Troubleshooting

### Connection Issues
- Verify your Aura instance is running
- Check that your URI starts with `neo4j+s://`
- Ensure your credentials are correct

### Model Issues
- Run `ollama list` to check installed models
- Pull missing models: `ollama pull qwen3:8b`

### Database Issues
- Run `python setup_neo4j.py` to recreate the schema
- Check the Neo4j Aura console for any errors

## Need Help?

- Check the main README.md for detailed documentation
- Review error messages in the console output
- Ensure all services are running and accessible

---

**Note**: The free tier of Neo4j Aura has some limitations. For production use or large repositories, consider upgrading to a paid plan.