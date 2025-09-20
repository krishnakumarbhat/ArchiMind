# app.py

from flask import Flask, render_template, request, jsonify
import ollama

# Initialize the Flask application
app = Flask(__name__)

# This route serves the main HTML page
@app.route('/')
def index():
    """
    Renders the chat interface page.
    """
    return render_template('index.html')

# This route handles the chat logic
@app.route('/chat', methods=['POST'])
def chat():
    """
    Receives a user message, sends it to the Ollama model,
    and returns the model's response.
    """
    # Get the user's message from the request's JSON body
    user_message = request.json.get('message')

    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    try:
        # Send the message to the Ollama model
        response = ollama.chat(
            model='qwen3:8b',
            messages=[{'role': 'user', 'content': user_message}]
        )
        
        # Extract the content of the response message
        bot_response = response['message']['content']
        
        return jsonify({"response": bot_response})

    except Exception as e:
        # Handle potential errors, like if Ollama is not running
        print(f"Error communicating with Ollama: {e}")
        return jsonify({"error": "Failed to get response from Ollama."}), 500

# Run the Flask app
if __name__ == '__main__':
    # Running on 0.0.0.0 makes it accessible from your network
    app.run(host='0.0.0.0', port=5000, debug=True)