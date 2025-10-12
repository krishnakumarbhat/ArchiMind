# doc_generator.py
"""
Generates documentation using the Gemini Large Language Model.
"""
from google import genai
import logging
import time

class DocGenerator:
    """Generates technical documentation using the Gemini API."""

    def __init__(self, api_key: str, model_name: str):
        try:
            self.client = genai.Client(api_key=api_key)
            logging.info("API connection established successfully")
            # genai.configure(api_key=api_key)
            # self.model = genai.GenerativeModel(model_name)
            # logging.info(f"Gemini model '{model_name}' configured successfully.")
        except Exception as e:
            logging.error(f"Failed to configure Gemini API: {e}")
            raise

    def _generate(self, prompt: str) -> str:
        """Helper function to generate content from a prompt."""
        logging.info("Sending context to Gemini. This may take a moment...")
        time.sleep(2) # Prevent rate limiting
        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-pro", contents=prompt)
            return response.text
        except Exception as e:
            logging.error(f"An error occurred while calling the Gemini API: {e}")
            return ""

    def generate_documentation(self, context: str, repo_name: str) -> str:
        """Generates and returns the main documentation."""
        prompt = f"""
        You are a principal software architect. Using ONLY the supplied project context, craft a
        chapter-wise technical handbook for the '{repo_name}' repository in GitHub-flavoured Markdown.

        Strictly follow the structure below:

        # {repo_name} Architecture Handbook
        - Concise executive summary bullet list (<=5 bullets)
        - Table of contents linking to every chapter anchor (use Markdown links like [Chapter 1](#chapter-1-title))

        ## Chapter 1: System Overview
        ### Objectives
        ### Core Capabilities
        ### Technology Stack

        ## Chapter 2: Architecture Blueprint
        ### Architectural Style
        ### Key Services & Responsibilities
        ### External Integrations

        ## Chapter 3: Data & Storage
        ### Data Flow Summary
        ### Persistent Stores
        ### Caching / Messaging

        ## Chapter 4: Runtime Behaviour
        ### Primary Execution Flow
        ### Error Handling & Resilience
        ### Observability

        ## Chapter 5: Extension Roadmap
        ### High-Impact Enhancements
        ### Tech Debt / Risks
        ### Deployment Considerations

        Rules:
        - Start every chapter heading exactly with "## Chapter N: ...".
        - Keep sub-sections concise (3-6 sentences or bullet lists).
        - Prefer tables where they improve clarity.
        - Never invent functionality that is absent from the context.
        - Use inline code formatting for important symbols, file names, APIs, or commands.

        --- RELEVANT CONTEXT ---
        {context}
        ---

        Return only the Markdown document.
        """
        return self._generate(prompt)

    def generate_hld(self, context: str, repo_name: str) -> str:
        """Generates and returns the High-Level Design graph definition."""
        prompt = f"""
        You are a senior software architect. From the supplied context of '{repo_name}', craft a JSON
        specification for a Mermaid system-context diagram. The output will be rendered with Mermaid.js.

        Output a single JSON object with the exact shape below (no Markdown code fences):
        {{
          "title": "<short name>",
          "description": "<one sentence summary>",
          "mermaid_code": "graph TD; ..."
        }}

        Rules for `mermaid_code`:
        - Use `graph TD` layout.
        - Include 6-12 nodes covering clients, services, databases, and external systems.
        - Node IDs MUST follow these strict rules:
          * Use only alphanumeric characters (a-z, A-Z, 0-9)
          * Use camelCase format (e.g., webClient, flaskAPI, mysqlDB)
          * NO underscores, hyphens, or special characters in IDs
          * Start with lowercase letter
          * Examples: webClient[Web Client], flaskAPI[Flask API], neo4jDB[Neo4j Database]
        - Represent interactions with directional edges using `-->` and add `|labels|` where helpful.
        - Group related nodes with Mermaid subgraphs when appropriate (e.g., `subgraph Services`).
        - Derive all names strictly from the provided context. Do not invent technologies.
        - Keep node labels (in square brackets) concise and clear.

        Example of valid syntax:
        graph TD
            webClient[Web Client]
            flaskAPI[Flask API]
            neo4jDB[Neo4j Database]
            webClient -->|HTTP Request| flaskAPI
            flaskAPI -->|Query| neo4jDB

        --- RELEVANT CONTEXT ---
        {context}
        ---

        Return only valid JSON.
        """
        return self._generate(prompt)

    def generate_lld(self, context: str, repo_name: str) -> str:
        """Generates and returns the Low-Level Design graph definition."""
        prompt = f"""
        You are a staff-level engineer. Using the provided context for '{repo_name}', produce a JSON
        Mermaid sequence diagram that captures the primary runtime path end-to-end.

        Output a single JSON object with this structure (no Markdown fences):
        {{
          "title": "<short workflow name>",
          "description": "<one sentence summary>",
          "mermaid_code": "sequenceDiagram\n  participant ..."
        }}

        Rules for `mermaid_code`:
        - Use `sequenceDiagram` syntax.
        - Include 6-10 participants covering clients, services, databases, workers, and external APIs.
        - Describe the main happy path plus at least one error or alternate branch using `alt`/`opt` blocks.
        - Use concise arrow labels that map directly to operations found in the supplied context.
        - Do not use `activate` or `deactivate` directives; rely on simple message arrows to show lifelines.
        - Derive every participant and message from the repository context only; do not hallucinate.

        --- RELEVANT CONTEXT ---
        {context}
        ---

        Return only valid JSON.
        """
        return self._generate(prompt)

    def generate_all_docs(self, context: str, repo_name: str) -> dict:
        """Generates all three documentation artifacts."""
        return {
            'documentation': self.generate_documentation(context, repo_name),
            'hld': self.generate_hld(context, repo_name),
            'lld': self.generate_lld(context, repo_name)
        }