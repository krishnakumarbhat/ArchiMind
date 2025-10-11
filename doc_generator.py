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
        specification for a force-directed architecture graph that will be rendered with D3.js.

        Output a single JSON object with the exact shape below (no Markdown code fences):
        {{
          "title": "<short name>",
          "description": "<one sentence summary>",
          "nodes": [
            {{"id": "string", "label": "string", "type": "client|service|datastore|external", "group": "string", "layer": integer}},
            ...
          ],
          "links": [
            {{"source": "node_id", "target": "node_id", "label": "string", "channel": "REST|gRPC|Event|DB|Queue|Other"}},
            ...
          ]
        }}

        Rules:
        - Include between 6 and 12 nodes.
        - Assign every node a `layer` number (0 for clients, higher numbers as depth increases).
        - Ensure all nodes referenced by links exist.
        - Use precise labels derived from the provided context only.
        - Prefer short `group` names (e.g., "API", "Services", "Data").

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
        workflow model for D3.js that captures the primary runtime path end-to-end.

        Output a single JSON object with this structure (no Markdown fences):
        {{
          "title": "<short workflow name>",
          "description": "<one sentence summary>",
          "nodes": [
            {{"id": "string", "label": "string", "type": "start|end|action|process|decision|async|data", "layer": integer, "notes": "short detail"}},
            ...
          ],
          "links": [
            {{"source": "node_id", "target": "node_id", "label": "string", "path": "success|failure|async|default"}},
            ...
          ]
        }}

        Rules:
        - Use between 8 and 14 nodes to cover the main happy path plus error handling.
        - Ensure `layer` increases as the workflow progresses (top-to-bottom rendering).
        - Include at least one `decision` node with explicit labelled branches in `links`.
        - Mark asynchronous steps with `type": "async"`.
        - Derive all labels from the given context; no hallucinations.

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