ArchiMind 🏗️🧠
ArchiMind is an intelligent system that automatically analyzes GitHub repositories, extracts architectural insights, and generates comprehensive technical documentation with interactive visualizations. Powered by RAG (Retrieval-Augmented Generation), vector embeddings, and Google's Gemini AI.

<div align="center">

⭐ Star us on GitHub | 🐛 Report a Bug | ✨ Request a Feature

</div>

Table of Contents
Features

Architecture & Design

Getting Started

Project Structure

API Documentation

Testing

Docker Deployment

Configuration

Security

Troubleshooting

Roadmap

Contributing

License

Acknowledgments

✨ Features
🎯 Core Capabilities
Automatic Repository Analysis: Clone and analyze any public GitHub repository.

RAG-Powered Documentation: Generate chapter-wise technical handbooks using context-aware AI.

Architecture Visualization: Create interactive High-Level Design (HLD) and Low-Level Design (LLD) graphs.

Vector Search: Utilize efficient semantic search with ChromaDB and Ollama embeddings.

Async Processing: Leverage background workers for non-blocking analysis tasks.

Modern UI: A responsive, user-friendly interface with a dark theme.

🔐 Authentication & Rate Limiting
Anonymous Access: Users get 5 free repository analyses without an account, tracked per browser session.

Authenticated Access: Signed-in users enjoy unlimited analyses and a persistent history of their work.

Secure Authentication: Passwords are securely hashed using the industry-standard PBKDF2-SHA256 algorithm.

Smart Login Prompt: After 5 free generations, anonymous users are greeted with a modal inviting them to sign up or log in.

🏛️ Architecture & Design
ArchiMind is built on a clean, service-oriented architecture that emphasizes modularity and maintainability.

Design Patterns
Singleton Pattern: Used in RepositoryService and VectorStoreService to ensure a single, shared instance, reducing memory overhead and maintaining a consistent state.

Factory Pattern: Implemented in DocumentationService to generate various types of documentation (handbook, HLD, LLD) through a unified method.

Service Layer: Decouples the web interface (Flask) from the core business logic, making the system easier to test, maintain, and scale.

Data Flow
A user submits a repository URL through the web interface.

The Flask application (app.py) validates the request and dispatches a job to the background Worker Process.

The worker utilizes the Service Layer (services.py):

RepositoryService clones the repo and reads relevant files.

VectorStoreService generates embeddings from the code and stores them in ChromaDB.

DocumentationService queries the vector store for context and uses the Gemini API to generate documentation and diagrams.

The final result is saved, and the status is updated for the user to view.

Code snippet

graph TD
    A[User Request] --> B{Flask App};
    B --> C[Background Worker];
    C --> D[RepositoryService: Clone Repo];
    D --> E[VectorStoreService: Create Embeddings];
    E --> F[DocumentationService: Generate Docs];
    F --> G[Save Results];
    G --> B;
🚀 Getting Started
Follow these steps to get a local instance of ArchiMind up and running.

Prerequisites
Python 3.11+

PostgreSQL 15+

Ollama: For local model embeddings.

Google Gemini API Key

Installation Guide
Clone the Repository

Bash

git clone https://github.com/krishnakumarbhat/ArchiMind.git
cd ArchiMind
Set Up a Virtual Environment

Bash

python3 -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
Install Dependencies

Bash

pip install -r requirements.txt
Set Up PostgreSQL Database
Connect to PostgreSQL and create a database and user.

SQL

-- Connect using psql
-- sudo -u postgres psql

CREATE DATABASE archimind;
CREATE USER archimind_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE archimind TO archimind_user;
\q
Install and Run Ollama
Ollama is used for generating vector embeddings locally.

Bash

# Install Ollama (see https://ollama.ai for details)
curl -fsSL https://ollama.ai/install.sh | sh

# Pull the required embedding model
ollama pull nomic-embed-text
Ensure the Ollama server is running before starting the application.

Configure Environment Variables
Copy the example .env file and fill in your credentials.

Bash

cp .env.example .env
Now, edit the .env file:

Code snippet

GEMINI_API_KEY="your_gemini_api_key_here"
DATABASE_URL="postgresql://archimind_user:your_secure_password@localhost/archimind"
SECRET_KEY="your_super_secret_flask_key"
Tip: Generate a secure SECRET_KEY with this command:

Bash

python3 -c "import secrets; print(secrets.token_hex(32))"
Run the Application
The database tables will be created automatically on the first run.

Bash

python app.py
Access ArchiMind
Open your browser and navigate to http://localhost:5000.

📁 Project Structure
ArchiMind/
├── app.py              # Main Flask app, routes, auth, & DB models
├── services.py         # Core business logic (Singleton & Factory patterns)
├── worker.py           # Background analysis worker
├── config.py           # Application configuration
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
├── tests/              # Test suite (unit & integration tests)
├── templates/          # HTML files
├── static/             # CSS, JS, and image assets
└── README.md           # This file
📖 API Documentation
Analysis Endpoints
POST /api/analyze
Starts a new repository analysis. Rate-limited for anonymous users.

Body: { "repo_url": "https://github.com/username/repository" }

Responses:

202 Accepted: Analysis has been successfully started.

400 Bad Request: The repo_url is missing or invalid.

403 Forbidden: Rate limit reached for anonymous user.

409 Conflict: An analysis is already in progress.

GET /api/status
Checks the status of the current analysis.

Response: A JSON object with the current status (pending, processing, completed, failed) and results.

GET /api/check-limit
Checks the current generation count for the user's session.

Response: { "can_generate": true, "count": 2, "limit": 5, "authenticated": false }

Authentication Endpoints
GET/POST /login: Handles user login.

GET/POST /sign-up: Handles new user registration.

GET /logout: Logs the current user out.

🧪 Testing
The project maintains over 80% test coverage to ensure code quality and stability.

Bash

# Run all tests with verbose output and coverage report
pytest tests/ -v --cov=.

# Generate an HTML coverage report
pytest tests/ --cov=. --cov-report=html
Code Quality
We use black for formatting, isort for import sorting, flake8 for linting, and bandit for security analysis. These checks are integrated into our CI/CD pipeline.

🐳 Docker Deployment
A docker-compose.yml file is provided for easy containerized deployment.

Build and Run Containers

Bash

docker-compose up -d --build
This will start the web application and a PostgreSQL database service.

View Logs

Bash

docker-compose logs -f
⚙️ Configuration
Key configuration options can be adjusted in config.py and the .env file.

Environment Variables (.env)
Variable	Description	Default Value
GEMINI_API_KEY	Required. Your API key for Google Gemini.	""
DATABASE_URL	Required. Connection string for PostgreSQL.	postgresql://...
SECRET_KEY	Required. A secret key for Flask sessions.	""

Export to Sheets
Application Settings (config.py)
ALLOWED_EXTENSIONS: A set of file extensions to be included in the analysis.

IGNORED_DIRECTORIES: A set of directories to exclude (e.g., .git, node_modules).

EMBEDDING_MODEL: The Ollama model used for embeddings (nomic-embed-text).

🔒 Security
Password Hashing: Uses PBKDF2-SHA256 with a salt to protect user passwords.

SQL Injection: The use of SQLAlchemy ORM prevents SQL injection vulnerabilities.

CSRF Protection: Flask's secret key provides a basic level of CSRF protection.

Session Management: Secure, server-side sessions are managed by Flask-Login.

Secret Management: All sensitive keys and credentials are loaded from an untracked .env file.

🔧 Troubleshooting
"Generation limit reached" error: This is expected for anonymous users after 5 analyses. Try clearing your browser cookies or signing up for an account.

PostgreSQL Connection Error: Ensure the PostgreSQL service is running and that the DATABASE_URL in your .env file is correct.

Ollama Embedding Error: Make sure the Ollama application is running and that you have pulled the nomic-embed-text model.

Modal doesn't appear: Check the browser's developer console for JavaScript errors and ensure script.js is loaded correctly.

🗺️ Roadmap
Planned Features
[ ] Multi-repository comparison tool

[ ] Export documentation to PDF and Markdown

[ ] Support for additional LLM providers (OpenAI, Anthropic)

[ ] Real-time collaboration on generated documents

[ ] Advanced code quality metrics and analysis

[ ] Integration with project management tools like Jira

[]mcp for with github change with go
🤝 Contributing
Contributions are welcome! Please fork the repository, create a feature branch, and open a pull request. Ensure your code adheres to our quality standards and that all tests pass.

📝 License
This project is licensed under the MIT License. See the LICENSE file for more details.

🙏 Acknowledgments
Google Gemini for its powerful generative AI capabilities.

Ollama & ChromaDB for enabling efficient, local vector search.

The developers of Flask and SQLAlchemy for their exceptional open-source tools.