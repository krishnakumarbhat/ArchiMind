"""Embedding Agent for chunking code and generating vector representations."""
from __future__ import annotations

import logging
import uuid
from typing import Dict, Iterable, List

from config import CHUNK_OVERLAP, CHUNK_SIZE, EMBEDDING_SUMMARY_PROMPT
from ollama_service import get_ollama_service
from .base import AgentContext, BaseAgent

LOGGER = logging.getLogger(__name__)


class EmbeddingAgent(BaseAgent):
    """Splits code into chunks, summarizes them, and produces embeddings."""

    def __init__(
        self,
        chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP,
    ) -> None:
        super().__init__(name="embedding_agent")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.ollama = get_ollama_service()

    def run(self, context: AgentContext) -> AgentContext:
        code_files = context.get("code_files", [])
        if not code_files:
            raise ValueError("EmbeddingAgent expects 'code_files' in context")

        chunks = list(self._chunk_files(code_files))
        vector_store = context.get("vector_store")
        embeddings = []

        for chunk in chunks:
            summary_prompt = EMBEDDING_SUMMARY_PROMPT.format(
                path=chunk["path"],
                code=chunk["content"],
            )
            summary = self.ollama.generate_response(summary_prompt)
            vector = self.ollama.get_embeddings(chunk["content"])
            if not vector:
                LOGGER.warning("Failed to embed chunk %s", chunk["chunk_id"])
                continue
            embeddings.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "path": chunk["path"],
                    "start": chunk["start"],
                    "end": chunk["end"],
                    "summary": summary,
                    "embedding": vector,
                }
            )

        if vector_store and embeddings:
            try:
                vector_store.store_embeddings(embeddings)
            except Exception as exc:
                LOGGER.warning("Vector store persistence failed: %s", exc)

        context = self.update_context(context, embeddings=embeddings)
        return context

    def _chunk_files(self, files: List[Dict[str, str]]) -> Iterable[Dict[str, object]]:
        for file_meta in files:
            content: str = file_meta.get("content", "")
            if not content:
                continue
            yield from self._chunk_text(file_meta["path"], content)

    def _chunk_text(self, path: str, text: str):
        text = text.strip()
        if not text:
            return
        start = 0
        text_len = len(text)
        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            chunk_content = text[start:end]
            chunk_id = f"{path}:{uuid.uuid4().hex}"
            yield {
                "chunk_id": chunk_id,
                "path": path,
                "start": start,
                "end": end,
                "content": chunk_content,
            }
            if end == text_len:
                break
            start = max(end - self.chunk_overlap, start + 1)


def build_embedding_agent() -> EmbeddingAgent:
    return EmbeddingAgent()
