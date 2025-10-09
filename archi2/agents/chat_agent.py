"""Chat Agent leveraging RAG over stored embeddings."""
from __future__ import annotations

import logging
from typing import List

from config import CHAT_PROMPT_TEMPLATE
from ollama_service import get_ollama_service
from .base import AgentContext, BaseAgent

LOGGER = logging.getLogger(__name__)


class ChatAgent(BaseAgent):
    """Answers questions about the repository using retrieval-augmented generation."""

    def __init__(self, top_k: int = 5) -> None:
        super().__init__(name="chat_agent")
        self.top_k = top_k
        self.ollama = get_ollama_service()

    def run(self, context: AgentContext) -> AgentContext:
        question = context.get("chat_question")
        if not question:
            raise ValueError("ChatAgent requires 'chat_question' in context")

        vector_store = context.get("vector_store")
        if not vector_store:
            LOGGER.warning("ChatAgent missing vector_store. Responding without context.")
            answer = self._generate_answer(question, "")
            return self.update_context(context, chat_answer=answer)

        question_vector = self.ollama.get_embeddings(question)
        if not question_vector:
            LOGGER.warning("Failed to embed chat question; returning direct LLM answer.")
            answer = self._generate_answer(question, "")
            return self.update_context(context, chat_answer=answer)

        results = vector_store.query_embeddings(question_vector, top_k=self.top_k)
        formatted_context = self._format_results(results)
        answer = self._generate_answer(question, formatted_context)
        return self.update_context(context, chat_answer=answer, chat_context=formatted_context)

    def _format_results(self, results: List[dict]) -> str:
        sections = []
        for idx, item in enumerate(results, start=1):
            summary = item.get("summary", "")
            path = item.get("path", "unknown")
            sections.append(f"Snippet {idx} ({path}):\n{summary}")
        return "\n\n".join(sections)

    def _generate_answer(self, question: str, context_snippets: str) -> str:
        prompt = CHAT_PROMPT_TEMPLATE.format(user_message=question, context=context_snippets)
        return self.ollama.generate_response(prompt)


def build_chat_agent() -> ChatAgent:
    return ChatAgent()
