from flask import Flask, render_template, jsonify, request, session
import time
import os

app = Flask(__name__)
app.secret_key = os.urandom(24) # Required for sessions

@app.route('/')
def index():
    """Renders the main input page."""
    return render_template('index3.html')

@app.route('/api/analyze', methods=['POST'])
def analyze_repo():
    """
    Analyzes the repo, saves the result to the session, and returns a success response.
    """
    time.sleep(1) # Simulate analysis time
    
    chat_explanation = """
    <h3>High-Level Design (HLD) Overview</h3>
    <p>This architecture represents a typical microservices-based e-commerce platform. We've chosen this approach for scalability and maintainability. Each service is responsible for a distinct business capability.</p>
    <h3>Low-Level Design (LLD) - User Service</h3>
    <p>Diving deeper into the User Service, we see a standard layered architecture. This separation of concerns makes the service easier to test and manage.</p>
    """
    mermaid_code = """
    graph TD
        subgraph HLD [High-Level Design]
            A[Client] --> B(API Gateway)
            B --> C{User Service}
            B --> D{Product Service}
        end
        subgraph LLD [Low-Level Design: User Service]
            direction LR
            AA[API Gateway] --> BB(Controller)
            BB --> CC(Service Layer)
        end
    """
    
    session['analysis_data'] = {
        "chat_response": chat_explanation,
        "mermaid_diagram": mermaid_code
    }
    
    return jsonify({"status": "success", "message": "Analysis complete."})

# NEW: A single route for the results page
@app.route('/doc')
def doc_page():
    """Renders the consolidated results page with all three tabs."""
    data = session.get('analysis_data', None)
    if not data:
        return "No analysis data found. Please generate it on the main page first.", 404
    return render_template('doc.html', data=data)

# This API for the chat tab remains the same
@app.route('/api/chat', methods=['POST'])
def chat_api():
    user_message = request.json.get('message', '')
    time.sleep(0.5)
    ai_response = f"This is a simulated AI response about '{user_message}'."
    return jsonify({"response": ai_response})

if __name__ == '__main__':
    app.run(debug=True)