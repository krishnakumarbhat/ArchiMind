# ArchiMind 🏗️🧠

ArchiMind automatically analyzes GitHub repositories, extracts architecture insights, and produces polished technical documentation with interactive Mermaid diagrams. The system combines Retrieval-Augmented Generation (RAG), vector embeddings, and Google's Gemini API to deliver high-fidelity architectural intelligence.

## Table of Contents
- **[Features](#features)**
- **[Architecture & Design](#architecture--design)**
- **[Getting Started](#getting-started)**
- **[Project Structure](#project-structure)**
- **[API Documentation](#api-documentation)**
- **[Testing](#testing)**
- **[Docker Deployment](#docker-deployment)**
- **[Configuration](#configuration)**
- **[Security](#security)**
- **[Troubleshooting](#troubleshooting)**
- **[Roadmap](#roadmap)**
- **[Contributing](#contributing)**
- **[License](#license)**
- **[Acknowledgments](#acknowledgments)**

## Features
- **Automatic Repository Analysis:** Clone and inspect any public GitHub repository with a single request.
- **RAG-Powered Documentation:** Generate chapter-wise architecture handbooks grounded in project context.
- **Interactive Diagrams:** Produce High-Level and Low-Level design graphs rendered via Mermaid.js.
- **Semantic Vector Search:** Index repositories with ChromaDB and Ollama embeddings for fast retrieval.
- **Asynchronous Processing:** Offload long-running work to a background worker for responsive UX.
- **Modern Interface:** Provide a responsive dark-theme UI with rich interactions.

### Authentication & Rate Limiting
- **Anonymous Access:** Track 5 free analyses per browser session without authentication.
- **Premium Mode:** Offer unlimited analyses and history for authenticated users.
- **Secure Credentials:** Hash passwords with PBKDF2-SHA256 using salted secrets.
- **Smart Upgrade Nudges:** Prompt anonymous users to sign up once they reach the free tier limit.

## Architecture & Design
- **Service-Oriented Layout:** Separate presentation, business logic, and infrastructure concerns across dedicated modules.
- **Singleton Services:** Share instances of `RepositoryService` and `VectorStoreService` to maintain consistency and reduce overhead.
- **Factory Abstractions:** Expose documentation generation through `DocumentationService` for HLD, LLD, and handbook flows.
- **Service Layer:** Decouple Flask routes from domain logic to improve testability and scalability.

### Data Flow
- **Step 1:** A user submits a repository URL via the Flask web UI (`app.py`).
- **Step 2:** `DocumentationService` dispatches analysis work to the `worker.py` background process.
- **Step 3:** `RepositoryService` clones the repo and extracts relevant files.
- **Step 4:** `VectorStoreService` embeds the codebase with Ollama and persists vectors in ChromaDB.
- **Step 5:** `DocumentationService` queries the vector store and calls Gemini to generate docs and diagrams.
- **Step 6:** Results and status metadata are stored for rendering in the UI.

```mermaid
graph TD
    userRequest[User Request] --> flaskApp{Flask App}
    flaskApp --> worker[Background Worker]
    worker --> repoService[RepositoryService]
    repoService --> vectorService[VectorStoreService]
    vectorService --> docService[DocumentationService]
    docService --> results[Persisted Results]
    results --> flaskApp
```

## Getting Started
Follow the steps below to launch ArchiMind locally.

### Prerequisites
- **Python 3.11+**
- **PostgreSQL 15+**
- **Ollama** for local embedding generation
- **Gemini API key** from Google AI Studio

### Installation
1. **Clone the repository**
   ```bash
   git clone https://github.com/krishnakumarbhat/ArchiMind.git
   cd ArchiMind
   ```
2. **Create a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```
3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
4. **Provision PostgreSQL**
   ```sql
   CREATE DATABASE archimind;
   CREATE USER archimind_user WITH PASSWORD 'your_secure_password';
   GRANT ALL PRIVILEGES ON DATABASE archimind TO archimind_user;
   ```
5. **Install and start Ollama**
   ```bash
   curl -fsSL https://ollama.ai/install.sh | sh
   ollama pull nomic-embed-text
   ```
6. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   Update `.env` with values similar to:
   ```dotenv
   GEMINI_API_KEY="your_gemini_api_key_here"
   DATABASE_URL="postgresql://archimind_user:your_secure_password@localhost/archimind"
   SECRET_KEY="your_super_secret_flask_key"
   ```
   Generate a strong `SECRET_KEY` if needed:
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```
7. **Run the application**
   ```bash
   python app.py
   ```
   Access the UI at `http://localhost:5000`.

## Project Structure
```text
ArchiMind/
├── app.py              # Flask application, routes, authentication, and DB models
├── services.py         # Business logic layer (Singleton & Factory patterns)
├── worker.py           # Background analysis worker process
├── doc_generator.py    # Gemini prompts for docs, HLD, and LLD
├── config.py           # Configuration constants and environment wiring
├── vector_manager.py   # Vector store utilities and health checks
├── requirements.txt    # Python dependencies
├── templates/          # HTML templates for the web UI
├── static/             # CSS, JavaScript, and asset files
├── tests/              # Unit and integration test suite
└── README.md           # Project documentation
```

## API Documentation
- **`POST /api/analyze`:** Kick off a new repository analysis. Returns `202 Accepted` when enqueued and enforces anonymous rate limits.
- **`GET /api/status`:** Retrieve the latest analysis status and, when complete, the generated documentation payload.
- **`GET /api/check-limit`:** Report remaining free analyses for the current session (`count`, `limit`, `authenticated`).
- **Authentication Endpoints:** `GET/POST /login`, `GET/POST /sign-up`, and `GET /logout` handle user sessions.

## Testing
- **Run the full suite:**
  ```bash
  pytest tests/ -v --cov=.
  ```
- **Generate coverage report:**
  ```bash
  pytest tests/ --cov=. --cov-report=html
  ```
- **Code Quality Tooling:** Enforce `black`, `isort`, `flake8`, and `bandit` locally or through the included GitHub Actions workflow.

## Docker Deployment
- **Build and start services:**
  ```bash
  docker-compose up -d --build
  ```
- **Tail logs:**
  ```bash
  docker-compose logs -f
  ```

## Configuration
- **`GEMINI_API_KEY`:** Required Google Gemini key (from `.env`).
- **`DATABASE_URL`:** PostgreSQL connection string (`postgresql://...`).
- **`SECRET_KEY`:** Flask session secret (use a random 64-char hex value).
- **`ALLOWED_EXTENSIONS`:** File types scanned during repository ingestion (`config.py`).
- **`IGNORED_DIRECTORIES`:** Folders excluded from analysis such as `.git` or `node_modules`.
- **`EMBEDDING_MODEL`:** Ollama embedding model (`nomic-embed-text`).

## Security
- **Password Hashing:** PBKDF2-SHA256 with per-user salts.
- **ORM Guardrails:** SQLAlchemy queries minimize injection risk.
- **Session Safety:** Flask-Login manages secure, server-side sessions.
- **Secret Management:** `.env` keeps credentials out of version control; example values live in `.env.example`.

## Troubleshooting
- **"Generation limit reached" message:** Clear browser cookies or authenticate to reset free-tier counters.
- **PostgreSQL connection failures:** Verify the database service is running and `.env` credentials are accurate.
- **Ollama embedding errors:** Confirm Ollama is running locally and the `nomic-embed-text` model is installed.
- **UI modal or script issues:** Inspect browser dev tools and ensure `static/script.js` loads without errors.

## Roadmap
- [ ] **Multi-repository comparison tooling**
- [ ] **Export documentation to PDF and Markdown**
- [ ] **Support for additional LLM providers (OpenAI, Anthropic)**
- [ ] **Real-time collaboration on generated documents**
- [ ] **Advanced code quality metrics and insights**
- [ ] **Integrations with project management platforms (e.g., Jira)**

## Contributing
Contributions are welcome! Fork the repository, create a feature branch, and open a pull request. Please ensure tests pass and code style checks run cleanly before submission.

## License
This project is licensed under the MIT License. Refer to the `LICENSE` file for full terms.

## Acknowledgments
- **Google Gemini:** Generative backbone powering documentation synthesis.
- **Ollama & ChromaDB:** Local embedding pipeline enabling fast semantic retrieval.
- **Flask & SQLAlchemy:** Core frameworks supporting the web experience and persistence layer.