# main.py
"""
Main script to run the RAG-based documentation generation workflow.
"""
import logging
from flask import Flask, render_template, request, jsonify

# Import configurations and managers
import config
import repo_manager
from vector_manager import VectorManager
from doc_generator import DocGenerator

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

import subprocess
import json
import os
import sys

@app.route('/api/analyze', methods=['POST'])
def analyze_repo():
    repo_url = request.json.get('repo_url')
    if not repo_url:
        return jsonify({'error': 'Repository URL is required'}), 400

    # Check if a process is already running
    try:
        with open(config.STATUS_FILE_PATH, 'r') as f:
            status = json.load(f)
            if status.get('status') == 'processing':
                return jsonify({'error': 'An analysis is already in progress'}), 409
    except (FileNotFoundError, json.JSONDecodeError):
        pass # No status file or it's invalid, so we can proceed

    # Start the worker as a separate process
    subprocess.Popen([sys.executable, 'worker.py', repo_url])
    
    return jsonify({'status': 'success', 'message': 'Analysis started'}), 202

@app.route('/api/status')
def get_status():
    try:
        with open(config.STATUS_FILE_PATH, 'r') as f:
            status = json.load(f)
            return jsonify(status)
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({'status': 'idle', 'result': None, 'error': None})

@app.route('/doc')
def documentation():
    try:
        with open(config.STATUS_FILE_PATH, 'r') as f:
            status = json.load(f)
        if status.get('status') == 'completed':
            return render_template('doc.html', data=status.get('result'))
        else:
            return "Analysis not complete or failed. Please check the status.", 404
    except (FileNotFoundError, json.JSONDecodeError):
        return "Analysis has not been run yet.", 404

if __name__ == "__main__":
    # Ensure the data directory and status file are initialized
    if not os.path.exists(config.DATA_PATH):
        os.makedirs(config.DATA_PATH)
    with open(config.STATUS_FILE_PATH, 'w') as f:
        json.dump({'status': 'idle'}, f)

    app.run(debug=True)