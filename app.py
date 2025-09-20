# app.py

from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import json
import logging
from agents import ArchiMindWorkflow
from neo4j_client import Neo4jClient
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the Flask application
app = Flask(__name__)
CORS(app)

# Initialize Neo4j client
neo4j_client = Neo4jClient()

@app.route('/')
def index():
    """
    Renders the main application page.
    """
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_repository():
    """
    Processes a GitHub repository URL and generates architecture diagrams.
    """
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({"error": "URL is required"}), 400
        
        repo_url = data['url']
        logger.info(f"Processing repository: {repo_url}")
        
        # Initialize the workflow
        workflow = ArchiMindWorkflow()
        
        # Run the complete workflow
        result = workflow.run(repo_url)
        
        if result.get('error'):
            return jsonify({"error": result['error']}), 500
        
        # Return the HLD and LLD data
        return jsonify({
            "hld": result.get('hld', {}),
            "lld": result.get('lld', {}),
            "readme": result.get('readme', ''),
            "status": "success"
        })
        
    except Exception as e:
        logger.error(f"Error processing repository: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": f"Failed to process repository: {str(e)}"}), 500

@app.route('/chat', methods=['POST'])
def chat():
    """
    Handles RAG-based chat functionality.
    """
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({"error": "Message is required"}), 400
        
        user_message = data['message']
        logger.info(f"Processing chat message: {user_message}")
        
        # Get relevant context from Neo4j using vector search
        context = neo4j_client.search_similar_code(user_message, limit=5)
        
        # Prepare context for the LLM
        context_text = "\n".join([doc['content'] for doc in context])
        
        # Create the prompt with context
        prompt = f"""Based on the following code context, answer the user's question about the software architecture.

Context:
{context_text}

User Question: {user_message}

Please provide a helpful and accurate response based on the code context provided."""

        # Stream the response
        def generate_response():
            try:
                import ollama
                
                # Use streaming for better user experience
                stream = ollama.chat(
                    model='qwen3:8b',
                    messages=[{'role': 'user', 'content': prompt}],
                    stream=True
                )
                
                for chunk in stream:
                    if 'message' in chunk and 'content' in chunk['message']:
                        content = chunk['message']['content']
                        yield f"data: {json.dumps({'content': content})}\n\n"
                
                # Send completion signal
                yield f"data: {json.dumps({'done': True})}\n\n"
                
            except Exception as e:
                logger.error(f"Error in chat generation: {str(e)}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return Response(
            stream_with_context(generate_response()),
            mimetype='text/plain',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Content-Type': 'text/event-stream'
            }
        )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        return jsonify({"error": f"Failed to process chat message: {str(e)}"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint.
    """
    try:
        # Test Neo4j connection
        neo4j_client.test_connection()
        return jsonify({"status": "healthy", "neo4j": "connected"})
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

if __name__ == '__main__':
    # Initialize Neo4j schema
    try:
        neo4j_client.initialize_schema()
        logger.info("Neo4j schema initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Neo4j schema: {str(e)}")
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)