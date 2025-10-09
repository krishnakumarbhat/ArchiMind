from flask import Flask, render_template, jsonify, request, session
import json
import os

from orchestrator import run_analysis, run_chat
from config import DEFAULT_HLD_MERMAID, DEFAULT_LLD_MERMAID

app = Flask(__name__)
# Use stable secret in development to preserve session across restarts
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

@app.route('/')
def index():
    """Renders the main input page."""
    return render_template('index3.html')


@app.route('/api/analyze', methods=['POST'])
def analyze_repo():
    """Analyze a repository, returning generated insights and diagrams."""
    # try:
    data = request.get_json()
    repo_input = data.get('repo_url') if data else None
    if not repo_input:
        return jsonify({"status": "error", "message": "Repository URL required."}), 400

    analysis_result = run_analysis(repo_input)

    analysis_text = analysis_result.get('analysis', '')
    knowledge_graph = analysis_result.get('knowledge_graph', {})
    hld_diagram = analysis_result.get('hld') or DEFAULT_HLD_MERMAID
    lld_diagram = analysis_result.get('lld') or DEFAULT_LLD_MERMAID

    chat_explanation = f"""
    <h3>AI-Generated Architecture Analysis</h3>
    <p><strong>Repository:</strong> {repo_input}</p>
    <pre style="white-space: pre-wrap;">{analysis_text}</pre>
    <hr>
    <h3>Knowledge Graph</h3>
    <pre style="white-space: pre-wrap;">{json.dumps(knowledge_graph, indent=2)}</pre>
    <hr>
    <h3>Generated Architecture Diagrams</h3>
    <p>Use the tabs below to view High-Level and Low-Level diagrams.</p>
    """
    
    session['analysis_data'] = {
        "chat_response": chat_explanation,
        "hld_diagram": hld_diagram,
        "lld_diagram": lld_diagram
    }

    return jsonify({"status": "success", "message": "Analysis complete."})
    
    # except Exception as e:
        # return jsonify({"status": "error", "message": f"Error: {str(e)}"}), 500
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
    # try:
    user_message = request.json.get('message', '')
    
    if not user_message:
        return jsonify({"response": "Please provide a message."})
    
    chat_result = run_chat(user_message)
    return jsonify({
        "response": chat_result.get("answer"),
        "context": chat_result.get("context", "")
    })
    # except Exception as e:
        # return jsonify({"response": f"Error: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=False, use_reloader=False)