"""ArchiMind background worker process."""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from typing import Dict, Optional
# Ensure project root is on PYTHONPATH
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

import config
from services import DocumentationService, RepositoryService, VectorStoreService
from oauth_utils import save_repository_to_history


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


class AnalysisWorker:
    """Worker class responsible for running repository analysis."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.repo_service = RepositoryService()
        self.status_file = config.STATUS_FILE_PATH

    # ------------------------------------------------------------------
    # Helper utilities
    # ------------------------------------------------------------------

    def _update_status(self, status: Dict[str, Optional[dict]]) -> None:
        """Persist the current analysis status to disk."""
        os.makedirs(os.path.dirname(self.status_file), exist_ok=True)
        with open(self.status_file, "w", encoding="utf-8") as handle:
            json.dump(status, handle, indent=2)

    def _update_database_log(self, analysis_log_id: Optional[int], status: str) -> None:
        """Record status transitions in the `AnalysisLog` table."""
        if not analysis_log_id:
            return

        try:
            from flask import Flask

            from app import AnalysisLog, db

            app = Flask(__name__)
            app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
                "DATABASE_URL", "postgresql://localhost/archimind"
            )
            app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
            db.init_app(app)

            with app.app_context():
                log_entry = AnalysisLog.query.get(analysis_log_id)
                if not log_entry:
                    return

                log_entry.status = status
                if status == "completed":
                    log_entry.completed_at = datetime.utcnow()

                db.session.commit()
        except Exception as exc:  # pragma: no cover - defensive logging
            self.logger.warning("Failed to update analysis log: %s", exc)

    def _clean_json_response(self, raw_value: str) -> str:
        """Strip Markdown fences and ensure the payload is valid JSON text."""
        if not raw_value:
            return ""

        cleaned = raw_value.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.lstrip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[len("json") :]
            cleaned = cleaned.strip()
            if cleaned.endswith("````"):
                cleaned = cleaned[:-4]
            elif cleaned.endswith("```"):
                cleaned = cleaned[:-3]

        cleaned = cleaned.strip()
        if cleaned and cleaned[0] != "{":
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                cleaned = cleaned[start : end + 1]

        return cleaned

    def _sanitize_mermaid_code(self, code: str) -> str:
        """Normalize Mermaid strings to avoid client-side parse errors."""
        if not isinstance(code, str):
            return code

        # Collapse accidental hard line breaks inside node labels, e.g. `[X\n(Y)]` → `[X (Y)]`
        code = re.sub(
            r"\[([^\]]*?)\n\s*([^\]]*?)\]",
            lambda match: "["
            + re.sub(r"\s+", " ", f"{match.group(1)} {match.group(2)}").strip()
            + "]",
            code,
            flags=re.MULTILINE,
        )

        # Function to convert node IDs to camelCase
        def to_camel_case(node_id: str) -> str:
            parts = re.split(r'[_\-]', node_id)
            if len(parts) > 1:
                camel_case = parts[0].lower() + ''.join(word.capitalize() for word in parts[1:] if word)
                # Ensure it starts with lowercase letter
                if camel_case and not camel_case[0].isalpha():
                    camel_case = 'node' + camel_case
                return camel_case
            return node_id

        # Build a mapping of old node IDs to new camelCase IDs
        node_id_map = {}
        
        # Find all node definitions (e.g., "NodeID[Label]")
        node_pattern = re.compile(r'\b([A-Za-z][A-Za-z0-9_\-]*)\s*\[')
        for match in node_pattern.finditer(code):
            old_id = match.group(1)
            new_id = to_camel_case(old_id)
            if old_id != new_id:
                node_id_map[old_id] = new_id

        # Replace all occurrences of old node IDs with new ones
        # Sort by length (longest first) to avoid partial replacements
        for old_id in sorted(node_id_map.keys(), key=len, reverse=True):
            new_id = node_id_map[old_id]
            # Use word boundaries to avoid partial matches
            code = re.sub(r'\b' + re.escape(old_id) + r'\b', new_id, code)

        # Remove stray single-letter artefacts between nodes (e.g. `] A -->`).
        letter_between_nodes = re.compile(r"\]\s+[A-Za-z]\s+(?=[-<])")

        sanitized_lines = []
        for line in code.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("activate ") or stripped.lower().startswith("deactivate "):
                continue

            line = letter_between_nodes.sub("] ", line)
            sanitized_lines.append(line.rstrip())

        return "\n".join(sanitized_lines)

    def _parse_graph_data(self, raw_value: str, label: str) -> Dict[str, object]:
        """Parse Mermaid graph JSON emitted by the LLM."""
        if not raw_value:
            return {"status": "error", "message": f"No {label} data returned."}

        try:
            normalized = self._clean_json_response(raw_value)
            parsed = json.loads(normalized)
            if isinstance(parsed, dict):
                if isinstance(parsed.get("mermaid_code"), str):
                    parsed["mermaid_code"] = self._sanitize_mermaid_code(parsed["mermaid_code"])
                return {"status": "ok", "graph": parsed}

            return {
                "status": "error",
                "message": f"{label} data was not a JSON object.",
                "raw_preview": normalized[:400],
            }
        except json.JSONDecodeError as exc:
            self.logger.error("Failed to parse %s JSON: %s", label, exc)
            return {
                "status": "error",
                "message": f"Failed to parse {label} JSON.",
                "raw_preview": (raw_value or "")[:400],
            }

    def _save_to_history(
        self, 
        analysis_log_id: int, 
        repo_url: str, 
        repo_name: str,
        documentation: str,
        hld_result: dict,
        lld_result: dict,
        chat_summary: Optional[str]
    ) -> None:
        """Save completed analysis to user's repository history."""
        try:
            from flask import Flask
            from app import AnalysisLog
            
            app = Flask(__name__)
            app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
                "DATABASE_URL", "postgresql://localhost/archimind"
            )
            app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
            from models import db
            db.init_app(app)
            
            with app.app_context():
                log_entry = AnalysisLog.query.get(analysis_log_id)
                if log_entry and log_entry.user_id:
                    # Only save for authenticated users
                    save_repository_to_history(
                        user_id=log_entry.user_id,
                        repo_url=repo_url,
                        repo_name=repo_name,
                        documentation=documentation,
                        hld_graph=hld_result,
                        lld_graph=lld_result,
                        chat_summary=chat_summary
                    )
                    self.logger.info(f"Saved repository {repo_name} to user history")
        except Exception as exc:
            self.logger.warning(f"Failed to save to history: {exc}")
    
    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_analysis(self, repo_url: str, analysis_log_id: Optional[int] = None) -> None:
        """Execute the full repository analysis pipeline."""

        status: Dict[str, Optional[dict]] = {"status": "processing", "result": None, "error": None}
        self._update_status(status)

        try:
            self._update_database_log(analysis_log_id, "processing")

            repo_name = repo_url.rstrip("/").split("/")[-1]
            self.logger.info("Starting analysis for repository: %s", repo_name)

            if not self.repo_service.clone_repository(repo_url, config.LOCAL_CLONE_PATH):
                raise RuntimeError("Failed to clone repository")

            vector_service = VectorStoreService(
                db_path=config.CHROMA_DB_PATH,
                collection_name=repo_name,
                embedding_model=config.EMBEDDING_MODEL,
            )

            if vector_service.is_empty():
                file_contents = self.repo_service.read_repository_files(
                    config.LOCAL_CLONE_PATH,
                    config.ALLOWED_EXTENSIONS,
                    config.IGNORED_DIRECTORIES,
                )
                if not file_contents:
                    raise RuntimeError("No processable files found in repository")

                vector_service.generate_embeddings(file_contents)

            context_query = "Generate a complete technical documentation for this software project."
            context = vector_service.query_similar_documents(context_query)
            if not context:
                raise RuntimeError("Failed to retrieve context from vector store")

            doc_service = DocumentationService(
                api_key=config.GEMINI_API_KEY,
                model_name=config.GENERATION_MODEL,
                chat_model_name=getattr(config, 'CHAT_MODEL', None),
            )
            docs = doc_service.generate_all_documentation(context, repo_name)

            hld_result = self._parse_graph_data(docs.get("hld"), "HLD")
            lld_result = self._parse_graph_data(docs.get("lld"), "LLD")

            status["status"] = "completed"
            status["result"] = {
                "chat_response": docs.get("documentation"),
                "hld_graph": hld_result,
                "lld_graph": lld_result,
                "chat_summary": docs.get("chat_summary"),
                "repo_name": repo_name,
                "repo_url": repo_url,
            }

            self._update_database_log(analysis_log_id, "completed")
            
            # Save to repository history for authenticated users
            if analysis_log_id:
                self._save_to_history(
                    analysis_log_id, 
                    repo_url,
                    repo_name,
                    docs.get("documentation"),
                    hld_result,
                    lld_result,
                    docs.get("chat_summary")
                )
            self.logger.info("Analysis completed successfully")

        except Exception as exc:  # pragma: no cover - mainline error logging
            self.logger.error("Analysis failed: %s", exc)
            status["status"] = "error"
            status["error"] = str(exc)
            self._update_database_log(analysis_log_id, "failed")

        finally:
            status["timestamp"] = int(time.time())
            self._update_status(status)


def main() -> None:
    """CLI entry point for running the worker standalone."""

    if len(sys.argv) < 2:
        logging.error("No repository URL provided.")
        sys.exit(1)

    repo_url = sys.argv[1]
    analysis_log_id = int(sys.argv[2]) if len(sys.argv) > 2 else None

    AnalysisWorker().run_analysis(repo_url, analysis_log_id)


if __name__ == "__main__":
    main()
