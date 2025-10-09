from flask import Flask, render_template, jsonify, request, session
import time
import os
from ollama_service import get_ollama_service
from config import (
    ANALYSIS_PROMPT_TEMPLATE, 
    CHAT_PROMPT_TEMPLATE, 
    DEFAULT_HLD_MERMAID, 
    DEFAULT_LLD_MERMAID
)

app = Flask(__name__)
app.secret_key = os.urandom(24) # Required for sessions

@app.route('/')
def index():
    """Renders the main input page."""
    return render_template('index3.html')

@app.route('/api/analyze', methods=['POST'])
def analyze_repo():
    """
    Analyzes the repo using Ollama, with default dummy graphs for HLD and LLD.
    """
    try:
        # Get repository input from request
        data = request.get_json()
        repo_input = data.get('repo_url', 'No repository specified')
        
        # Get Ollama service instance
        ollama = get_ollama_service()
        
        # Generate analysis using Ollama
        prompt = ANALYSIS_PROMPT_TEMPLATE.format(repo_input=repo_input)
        ai_analysis = ollama.generate_response(prompt)
        
        # Format the response with HTML
        chat_explanation = f"""
        <h3>AI-Generated Architecture Analysis</h3>
        <p><strong>Repository:</strong> {repo_input}</p>
        <div style="white-space: pre-wrap;">{ai_analysis}</div>
        <hr>
        <h3>Default Architecture Diagrams</h3>
        <p>Use the tabs below to view separate HLD and LLD diagrams.</p>
        """
        
        # Use separate dummy graphs
        hld_diagram = DEFAULT_HLD_MERMAID
        lld_diagram = DEFAULT_LLD_MERMAID
        
        # Save to session
        session['analysis_data'] = {
            "chat_response": chat_explanation,
            "hld_diagram": hld_diagram,
            "lld_diagram": lld_diagram
        }
        
        return jsonify({"status": "success", "message": "Analysis complete."})
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error: {str(e)}"}), 500

# NEW: A single route for the results page
@app.route('/doc')
def doc_page():
    """Renders the consolidated results page with all three tabs."""
    data = session.get('analysis_data', None)
    if not data:
        return "No analysis data found. Please generate it on the main page first.", 404
    return render_template('doc.html', data=data)

@app.route('/api/chat', methods=['POST'])
def chat_api():
    """
    Chat API using Ollama for architecture-related questions.
    """
    try:
        user_message = request.json.get('message', '')
        
        if not user_message:
            return jsonify({"response": "Please provide a message."})
        
        # Get Ollama service instance
        ollama = get_ollama_service()
        
        # Generate response using Ollama
        prompt = CHAT_PROMPT_TEMPLATE.format(user_message=user_message)
        ai_response = ollama.generate_response(prompt)
        
        return jsonify({"response": ai_response})
    
    except Exception as e:
        return jsonify({"response": f"Error: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)