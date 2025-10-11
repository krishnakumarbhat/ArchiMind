"""Diagram Agent that converts graph data into Mermaid diagrams."""
from __future__ import annotations

import json
import logging
from typing import Dict

from config import DEFAULT_HLD_MERMAID, DEFAULT_LLD_MERMAID, DIAGRAM_PROMPT_TEMPLATE
from ollama_service import OllamaService
from .base import AgentContext, BaseAgent

LOGGER = logging.getLogger(__name__)


def parse_diagram_response(response: str) -> Dict[str, str]:
    """Parse LLM response into HLD/LLD diagrams with safe fallbacks."""
    try:
        parsed = json.loads(response)
        hld = parsed.get("hld", DEFAULT_HLD_MERMAID)
        lld = parsed.get("lld", DEFAULT_LLD_MERMAID)
        return {"hld": hld, "lld": lld}
    except json.JSONDecodeError:
        LOGGER.warning("Diagram response invalid JSON. Using default diagrams.")
        return {"hld": DEFAULT_HLD_MERMAID, "lld": DEFAULT_LLD_MERMAID}


class DiagramAgent(BaseAgent):
    """Generates HLD and LLD diagrams from knowledge graph."""

    def __init__(self) -> None:
        super().__init__(name="diagram_agent")
        self.ollama = OllamaService()

    def run(self, context: AgentContext) -> AgentContext:
        knowledge_graph = context.get("knowledge_graph")
        if not knowledge_graph:
            raise ValueError("DiagramAgent requires 'knowledge_graph' in context")

        graph_json = json.dumps(knowledge_graph, indent=2)
        prompt = DIAGRAM_PROMPT_TEMPLATE.format(graph_description=graph_json)
        response = self.ollama.generate_response(prompt)

        diagrams = parse_diagram_response(response)
        context = self.update_context(context, diagrams=diagrams)
        return context
 
