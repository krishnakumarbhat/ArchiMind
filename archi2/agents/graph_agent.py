"""Graph Agent responsible for assembling repository knowledge graphs."""
from __future__ import annotations

import json
import logging
from typing import Dict, List

from config import GRAPH_PROMPT_TEMPLATE
from ollama_service import get_ollama_service
from .base import AgentContext, BaseAgent

LOGGER = logging.getLogger(__name__)


class GraphAgent(BaseAgent):
    """Leverages LLM to transform embeddings into a knowledge graph."""

    def __init__(self) -> None:
        super().__init__(name="graph_agent")
        self.ollama = get_ollama_service()

    def run(self, context: AgentContext) -> AgentContext:
        embeddings = context.get("embeddings")
        if not embeddings:
            raise ValueError("GraphAgent requires 'embeddings' in context")

        formatted_context = self._build_context_payload(embeddings)
        prompt = GRAPH_PROMPT_TEMPLATE.format(context=formatted_context)
        llm_response = self.ollama.generate_response(prompt)

        graph_data = self._parse_graph_response(llm_response)

        graph_store = context.get("graph_store")
        if graph_store:
            try:
                graph_store.store_graph(graph_data)
            except Exception as exc:
                LOGGER.warning("Graph store persistence failed: %s", exc)

        context = self.update_context(context, knowledge_graph=graph_data)
        return context

    def _build_context_payload(self, embeddings: List[Dict[str, object]]) -> str:
        snippets = []
        for item in embeddings:
            summary = item.get("summary", "")
            if not summary:
                continue
            snippets.append(
                {
                    "chunk_id": item.get("chunk_id"),
                    "path": item.get("path"),
                    "summary": summary,
                }
            )
            if len(snippets) >= 40:
                break
        return json.dumps(snippets, indent=2)

    def _parse_graph_response(self, response: str) -> Dict[str, List[Dict[str, object]]]:
        try:
            parsed = json.loads(response)
            nodes = parsed.get("nodes", [])
            relationships = parsed.get("relationships", [])
            return {
                "nodes": nodes,
                "relationships": relationships,
            }
        except json.JSONDecodeError:
            LOGGER.warning("LLM graph response was not valid JSON. Returning empty graph.")
            return {"nodes": [], "relationships": []}


def build_graph_agent() -> GraphAgent:
    return GraphAgent()
