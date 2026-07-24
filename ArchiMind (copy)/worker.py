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

    def _status_file_for_analysis(self, analysis_log_id: Optional[int]) -> str:
        if analysis_log_id:
            return os.path.join(config.DATA_PATH, f"status_{analysis_log_id}.json")
        return self.status_file

    def _update_status(self, status: Dict[str, Optional[dict]], status_file_path: Optional[str] = None) -> None:
        """Persist the current analysis status to disk."""
        target_path = status_file_path or self.status_file
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as handle:
            json.dump(status, handle, indent=2)

        if target_path != self.status_file:
            os.makedirs(os.path.dirname(self.status_file), exist_ok=True)
            with open(self.status_file, "w", encoding="utf-8") as handle:
                json.dump(status, handle, indent=2)

    def _set_stage(
        self,
        status: Dict[str, Optional[dict]],
        *,
        stage: str,
        message: str,
        progress: int,
        status_file_path: str,
    ) -> None:
        status["stage"] = stage
        status["message"] = message
        status["progress"] = progress
        self._update_status(status, status_file_path)

    @staticmethod
    def _derive_repo_name(repo_url: str) -> str:
        cleaned = repo_url.rstrip("/")
        repo_name = cleaned.split("/")[-1]
        return repo_name.removesuffix(".git")

    def _derive_repo_collection(self, repo_url: str) -> str:
        return self.repo_service.build_collection_name(repo_url)

    def _update_database_log(self, analysis_log_id: Optional[int], status: str) -> None:
        """Record status transitions in the `AnalysisLog` table."""
        if not analysis_log_id:
            return

        try:
            from app import create_app
            from models import AnalysisLog, db

            app = create_app()

            with app.app_context():
                log_entry = db.session.get(AnalysisLog, analysis_log_id)
                if not log_entry:
                    return

                log_entry.status = status
                if status in {"completed", "failed"}:
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
            from app import create_app
            from models import AnalysisLog, db

            app = create_app()
            
            with app.app_context():
                log_entry = db.session.get(AnalysisLog, analysis_log_id)
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

        status: Dict[str, Optional[dict]] = {
            "status": "processing",
            "result": None,
            "error": None,
            "analysis_id": analysis_log_id,
            "stage": "queued",
            "message": "Analysis queued.",
            "progress": 0,
        }
        status_file_path = self._status_file_for_analysis(analysis_log_id)
        self._update_status(status, status_file_path)

        try:
            self._update_database_log(analysis_log_id, "processing")

            repo_name = self._derive_repo_name(repo_url)
            repo_collection = self._derive_repo_collection(repo_url)
            self.logger.info("Starting analysis for repository: %s", repo_name)
            repo_local_path = os.path.join(
                config.LOCAL_CLONE_PATH,
                f"{repo_name}_{analysis_log_id or int(time.time())}",
            )

            self._set_stage(
                status,
                stage="preparing",
                message="Preparing repository analysis.",
                progress=8,
                status_file_path=status_file_path,
            )

            vector_service = VectorStoreService(
                db_path=config.CHROMA_DB_PATH,
                collection_name=repo_collection,
                embedding_model=config.EMBEDDING_MODEL,
                repo_url=repo_url,
            )

            had_existing_index = not vector_service.is_empty()

            self._set_stage(
                status,
                stage="ingestion",
                message="Collecting repository files.",
                progress=22,
                status_file_path=status_file_path,
            )
            file_contents = self.repo_service.collect_repository_files(
                repo_url,
                repo_local_path,
                config.ALLOWED_EXTENSIONS,
                config.IGNORED_DIRECTORIES,
            )
            if not file_contents:
                raise RuntimeError("No processable files found from remote ingestion or local clone")

            self._set_stage(
                status,
                stage="indexing",
                message="Refreshing repository index." if had_existing_index else "Building repository index.",
                progress=46,
                status_file_path=status_file_path,
            )
            vector_service.reset()
            vector_service.generate_embeddings(file_contents)

            context_query = "Generate a complete technical documentation for this software project."
            self._set_stage(
                status,
                stage="retrieval",
                message="Retrieving relevant architectural context.",
                progress=64,
                status_file_path=status_file_path,
            )
            context = vector_service.query_similar_documents(context_query)
            if not context:
                raise RuntimeError("Failed to retrieve context from vector store")

            doc_service = DocumentationService(
                api_key=config.GEMINI_API_KEY,
                model_name=config.DOCUMENTATION_MODEL,
                chat_model_name=config.CHAT_MODEL,
                thinking_level=config.GEMINI_THINKING_LEVEL,
                api_version=config.GEMINI_API_VERSION,
                context_char_limit=config.DOCUMENTATION_CONTEXT_CHAR_LIMIT,
            )
            self.logger.info("Documentation backend selected: %s", doc_service.describe_backend())

            self._set_stage(
                status,
                stage="generation",
                message="Generating handbook, diagrams, and summary.",
                progress=82,
                status_file_path=status_file_path,
            )
            docs = doc_service.generate_all_documentation(context, repo_name)

            hld_result = self._parse_graph_data(docs.get("hld"), "HLD")
            lld_result = self._parse_graph_data(docs.get("lld"), "LLD")
            flow_result = self._parse_graph_data(docs.get("flow"), "Flow")

            status["status"] = "completed"
            status["stage"] = "completed"
            status["message"] = "Analysis complete."
            status["progress"] = 100
            status["result"] = {
                "chat_response": docs.get("documentation"),
                "hld_graph": hld_result,
                "lld_graph": lld_result,
                "flow_graph": flow_result,
                "chat_summary": docs.get("chat_summary"),
                "repo_name": repo_name,
                "repo_url": repo_url,
                "repo_collection": repo_collection,
                "generation_backend": doc_service.describe_backend(),
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
            status["stage"] = "error"
            status["message"] = "Analysis failed."
            status["error"] = str(exc)
            self._update_database_log(analysis_log_id, "failed")

        finally:
            status["timestamp"] = int(time.time())
            self._update_status(status, status_file_path)


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
