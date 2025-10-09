"""Analysis Agent generating high-level architectural insights."""
from __future__ import annotations

import logging
from typing import Dict, Iterable, List

from config import ANALYSIS_PROMPT_TEMPLATE
from ollama_service import get_ollama_service
from .base import AgentContext, BaseAgent

LOGGER = logging.getLogger(__name__)


class AnalysisAgent(BaseAgent):
    """Uses LLM to produce architecture analysis from parsed repository data."""

    def __init__(self, max_files_summary: int = 30) -> None:
        super().__init__(name="analysis_agent")
        self.max_files_summary = max_files_summary
        self.ollama = get_ollama_service()

    def run(self, context: AgentContext) -> AgentContext:
        repo_url = context.get("repo_url", "")
        repo_meta = context.get("repo_meta", {})
        code_files = context.get("code_files", [])
        if not code_files:
            LOGGER.warning("AnalysisAgent received no code files; analysis may be limited.")

        default_branch = repo_meta.get("default_branch", "main")
        description = repo_meta.get("description", "No description available.")
        file_overview = self._build_file_overview(code_files)

        prompt = ANALYSIS_PROMPT_TEMPLATE.format(
            repo_url=repo_url,
            default_branch=default_branch,
            description=description,
            file_overview=file_overview,
        )
        analysis_text = self.ollama.generate_response(prompt)

        return self.update_context(
            context,
            analysis=analysis_text,
            file_overview=file_overview,
        )

    def _build_file_overview(self, code_files: List[Dict[str, object]]) -> str:
        lines: List[str] = []
        for idx, file_meta in enumerate(code_files[: self.max_files_summary], start=1):
            path = file_meta.get("path", "unknown")
            size = file_meta.get("size", 0)
            lines.append(f"{idx}. {path} ({size} bytes)")
        if len(code_files) > self.max_files_summary:
            lines.append(f"... and {len(code_files) - self.max_files_summary} more files")
        return "\n".join(lines)


def build_analysis_agent() -> AnalysisAgent:
    return AnalysisAgent()
