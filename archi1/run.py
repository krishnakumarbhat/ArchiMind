#!/usr/bin/env python3
"""
ArchiMind Application Startup Script

This script provides a convenient way to start the ArchiMind application
with proper error handling and setup verification.
"""

import os
import sys
import subprocess
from pathlib import Path

def check_requirements():
    """Check if all required dependencies are installed."""
    try:
        import flask
        import neo4j
        import ollama
        import requests
        print("✅ All Python dependencies are installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please run: pip install -r requirements.txt")
        return False

def check_neo4j():
    """Check if Neo4j Aura is accessible."""
    try:
        from neo4j_client import Neo4jClient
        client = Neo4jClient()
        if client.test_connection():
            print("✅ Neo4j Aura connection successful")
            client.close()
            return True
        else:
            print("❌ Neo4j Aura connection failed")
            return False
    except Exception as e:
        print(f"❌ Neo4j Aura error: {e}")
        print("Please ensure your Aura instance is running and check your .env configuration")
        return False

def check_ollama():
    """Check if Ollama is running and has required models."""
    try:
        import ollama
        models = ollama.list()
        model_names = [model['name'] for model in models['models']]
        
        required_models = ['qwen3:8b', 'nomic-embed-text:latest']
        missing_models = []
        
        for model in required_models:
            if not any(model in name for name in model_names):
                missing_models.append(model)
        
        if missing_models:
            print(f"❌ Missing Ollama models: {', '.join(missing_models)}")
            print("Please run:")
            for model in missing_models:
                print(f"  ollama pull {model}")
            return False
        else:
            print("✅ All required Ollama models are available")
            return True
            
    except Exception as e:
        print(f"❌ Ollama error: {e}")
        print("Please ensure Ollama is running and install required models")
        return False

def main():
    """Main startup function."""
    print("🚀 Starting ArchiMind Application...")
    print()
    
    # Check requirements
    if not check_requirements():
        sys.exit(1)
    
    # Check Neo4j Aura
    if not check_neo4j():
        print()
        print("To fix Neo4j Aura issues:")
        print("1. Create a Neo4j Aura account at https://console.neo4j.io")
        print("2. Create a new Aura instance")
        print("3. Update your .env file with Aura connection details")
        print("4. Run: python setup_neo4j.py")
        sys.exit(1)
    
    # Check Ollama
    if not check_ollama():
        print()
        print("To fix Ollama issues:")
        print("1. Install Ollama from https://ollama.ai")
        print("2. Start Ollama service")
        print("3. Pull required models as shown above")
        sys.exit(1)
    
    print()
    print("✅ All checks passed! Starting application...")
    print("🌐 Application will be available at: http://localhost:5000")
    print("📖 Press Ctrl+C to stop the application")
    print()
    
    # Start the Flask application
    try:
        from app import app
        app.run(host='0.0.0.0', port=5000, debug=True)
    except KeyboardInterrupt:
        print("\n👋 Application stopped by user")
    except Exception as e:
        print(f"\n❌ Application error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()