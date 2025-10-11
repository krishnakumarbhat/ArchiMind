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

    def generate_documentation(self, context: str, repo_name: str) -> str:
        """Generates and returns documentation based on the provided context."""
        prompt = f"""
        You are a world-class senior software architect. Your task is to generate a comprehensive
        technical documentation for the '{repo_name}' project.

        Based ONLY on the following context, which contains the source code from the most
        relevant project files, create a single, well-structured Markdown document.

        The documentation must include:
        1.  **Project Overview**: A high-level summary of the project's purpose and technology stack.
        2.  **High-Level Design (HLD)**: A Mermaid.js `graph TD` diagram showing the main architectural components and their interactions.
        3.  **Low-Level Design (LLD)**: A Mermaid.js `flowchart TD` diagram detailing the primary step-by-step workflow.
        4.  **Core Components Analysis**: A breakdown of the key files provided, explaining their purpose and role.

        --- RELEVANT CONTEXT ---
        {context}
        ---

        Generate the complete documentation now.
        """
        
        logging.info("Sending context to Gemini. This may take a moment...")
        # A short delay can help manage API rate limits in frequent-use scenarios.
        time.sleep(5)

        try:
            response = self.client.models.generate_content(
            model="gemini-2.5-pro", contents=prompt)
            return response.text
        except Exception as e:
            logging.error(f"An error occurred while calling the Gemini API: {e}")
            return ""