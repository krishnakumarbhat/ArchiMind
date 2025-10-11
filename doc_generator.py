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
        """Generates and returns the High-Level Design Mermaid diagram."""
        prompt = f"""
        You are a senior software architect. From the supplied context of '{repo_name}', produce a
        polished Mermaid.js architecture schematic using `graph LR` syntax.

        Requirements:
        - Represent client, API/services, and data platforms using distinct shapes.
          * Clients: rounded rectangles
          * Services: sharp rectangles
          * Data stores / queues: cylinders
        - Group related services with `subgraph` blocks.
        - Apply class definitions for colour-coding: `classDef client fill:#0ea5e9,stroke:#0c4a6e,color:#fff;`
          `classDef service fill:#6366f1,stroke:#312e81,color:#fff;`
          `classDef datastore fill:#f59e0b,stroke:#92400e,color:#1f2937;`
          `classDef external fill:#10b981,stroke:#065f46,color:#052e16;`
        - Attach the classes using `class` statements.
        - Highlight external dependencies or third-party APIs in a dedicated `subgraph External Systems`.
        - Show primary data/control flow using directional arrows with labels (e.g., `A -->|REST| B`).

        --- RELEVANT CONTEXT ---
        {context}
        ---

        Output only the Mermaid `graph LR` code block.
        """
        return self._generate(prompt)

    def generate_lld(self, context: str, repo_name: str) -> str:
        """Generates and returns the Low-Level Design Mermaid diagram."""
        prompt = f"""
        You are a staff-level engineer. Using the provided context for '{repo_name}', construct a
        detailed Mermaid.js workflow diagram with `flowchart TD` syntax that captures the primary
        runtime pathway end-to-end.

        Requirements:
        - Use the following shapes consistently:
          * `([Start])` and `([End])` for entry/exit
          * `( )` rounded rectangles for user/system actions
          * `[ ]` rectangles for processing steps / business logic
          * `{{ }}` diamonds for decisions (include labelled yes/no branches)
        - Annotate asynchronous steps with `:::async` and define `classDef async stroke-dasharray: 5 5;`
        - Define additional styles: `classDef success fill:#34d399,stroke:#047857,color:#064e3b;`
          `classDef failure fill:#fca5a5,stroke:#b91c1c,color:#7f1d1d;`
        - Highlight error handling branches clearly.
        - Include key data artefacts or messages as parallelogram nodes using `[/Label/]` syntax.

        --- RELEVANT CONTEXT ---
        {context}
        ---

        Return only the Mermaid `flowchart TD` code block.
        """
        return self._generate(prompt)

    def generate_all_docs(self, context: str, repo_name: str) -> dict:
        """Generates all three documentation artifacts."""
        return {
            'documentation': self.generate_documentation(context, repo_name),
            'hld': self.generate_hld(context, repo_name),
            'lld': self.generate_lld(context, repo_name)
        }