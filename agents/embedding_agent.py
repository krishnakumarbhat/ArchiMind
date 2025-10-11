"""Embedding Agent for chunking code and generating vector representations."""
from __future__ import annotations

import logging
import uuid
from typing import Dict, Iterable, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import CHUNK_OVERLAP, CHUNK_SIZE, EMBEDDING_SUMMARY_PROMPT
from ollama_service import OllamaService
from .base import AgentContext, BaseAgent

LOGGER = logging.getLogger(__name__)


def chunk_text(path: str, text: str, chunk_size: int, chunk_overlap: int):
    text = text.strip()
    if not text:
        return
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(start + chunk_size, text_len)
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
        start = max(end - chunk_overlap, start + 1)


def chunk_files(files: List[Dict[str, str]], chunk_size: int, chunk_overlap: int) -> Iterable[Dict[str, object]]:
    for file_meta in files:
        content: str = file_meta.get("content", "")
        if not content:
            continue
        yield from chunk_text(file_meta["path"], content, chunk_size, chunk_overlap)


class EmbeddingAgent(BaseAgent):
    """
    Splits code into chunks, summarizes them, and produces embeddings.
    
    Uses Factory Pattern for embedding service creation and supports
    concurrent processing for improved performance.
    """

    def __init__(
        self,
        chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP,
        max_workers: int = 4,
    ) -> None:
        super().__init__(name="embedding_agent")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_workers = max_workers
        self.ollama = self._create_embedding_service()

    def _create_embedding_service(self) -> OllamaService:
        """Factory method for creating embedding service."""
        return OllamaService()

    def run(self, context: AgentContext) -> AgentContext:
        code_files = context.get("code_files", [])
        if not code_files:
            LOGGER.warning("No code files found in context")
            return self.update_context(context, embeddings=[])

        chunks = list(chunk_files(code_files, self.chunk_size, self.chunk_overlap))
        LOGGER.info(f"Processing {len(chunks)} code chunks")
        
        vector_store = context.get("vector_store")
        embeddings = self._process_chunks_concurrently(chunks)

        if vector_store and embeddings:
            try:
                vector_store.store_embeddings(embeddings)
                LOGGER.info(f"Stored {len(embeddings)} embeddings in vector store")
            except Exception as exc:
                LOGGER.error("Vector store persistence failed: %s", exc)

        return self.update_context(context, embeddings=embeddings)

    def _process_chunks_concurrently(self, chunks: List[Dict]) -> List[Dict]:
        """Process chunks concurrently for better performance."""
        embeddings = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all chunk processing tasks
            future_to_chunk = {
                executor.submit(self._process_single_chunk, chunk): chunk 
                for chunk in chunks
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_chunk):
                try:
                    embedding_result = future.result()
                    if embedding_result:
                        embeddings.append(embedding_result)
                except Exception as exc:
                    chunk = future_to_chunk[future]
                    LOGGER.error(f"Error processing chunk {chunk['chunk_id']}: {exc}")
        
        LOGGER.info(f"Successfully processed {len(embeddings)}/{len(chunks)} chunks")
        return embeddings

    def _process_single_chunk(self, chunk: Dict) -> Optional[Dict]:
        """Process a single chunk to generate summary and embedding."""
        try:
            # Generate summary
            summary_prompt = EMBEDDING_SUMMARY_PROMPT.format(
                path=chunk["path"],
                code=chunk["content"],
            )
            summary = self.ollama.generate_response(summary_prompt)
            
            # Generate embedding
            vector = self.ollama.get_embeddings(chunk["content"])
            if not vector:
                LOGGER.warning(f"Failed to generate embedding for chunk {chunk['chunk_id']}")
                return None
            
            return {
                "chunk_id": chunk["chunk_id"],
                "path": chunk["path"],
                "start": chunk["start"],
                "end": chunk["end"],
                "summary": summary,
                "embedding": vector,
            }
            
        except Exception as exc:
            LOGGER.error(f"Error processing chunk {chunk['chunk_id']}: {exc}")
            return None

 

 
