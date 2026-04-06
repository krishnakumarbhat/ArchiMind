"""ArchiMind service layer with lightweight local-first indexing and retrieval."""

from __future__ import annotations

import ast
import hashlib
import importlib
import json
import logging
import math
import os
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from http.client import IncompleteRead
from typing import Dict, List, Optional, Set, Tuple, TypedDict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import config
import git

try:
    from google import genai
    from google.genai import types as genai_types
except Exception:
    genai = None
    genai_types = None

try:
    from pinecone import Pinecone, ServerlessSpec
except Exception:
    Pinecone = None
    ServerlessSpec = None

try:
    import chromadb
except Exception:
    chromadb = None

try:
    _llama_module = importlib.import_module("llama_index.core.node_parser")
    CodeSplitter = getattr(_llama_module, "CodeSplitter", None)
except Exception:
    CodeSplitter = None

try:
    _langgraph_module = importlib.import_module("langgraph.graph")
    END = getattr(_langgraph_module, "END", None)
    StateGraph = getattr(_langgraph_module, "StateGraph", None)
except Exception:
    END = None
    StateGraph = None


def _is_pinecone_namespace_missing_error(exc: Exception) -> bool:
    return "namespace not found" in str(exc).lower()


def _format_vector_backend_error(exc: Exception) -> str:
    message = str(exc)
    lowered = message.lower()
    if "invalid api key" in lowered or "unauthorized" in lowered:
        return (
            "Pinecone authentication failed. Verify PINECONE_API_KEY, "
            "PINECONE_INDEX_NAME, and PINECONE_HOST."
        )
    return message


def _extract_index_attribute(index_info, name: str):
    if isinstance(index_info, dict):
        return index_info.get(name)
    return getattr(index_info, name, None)


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""


@dataclass
class ChunkRecord:
    """Represents a code chunk and its metadata."""

    chunk_id: str
    text: str
    metadata: Dict[str, object]


@dataclass
class RetrievedContextFile:
    """Represents a retrieved file excerpt rendered into repository context."""

    file_path: str
    language: str
    function_name: str
    github_url: str
    content: str


class RepositoryService:
    """Repository management service (singleton)."""

    _instance: Optional["RepositoryService"] = None
    _initialized: bool = False
    _HTTP_RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
    _HTTP_MAX_ATTEMPTS = 3

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.logger = logging.getLogger(self.__class__.__name__)
            self._initialized = True

    def clone_repository(self, repo_url: str, local_path: str) -> bool:
        if os.path.exists(local_path):
            self.logger.info("Repository already exists at: %s. Skipping clone.", local_path)
            return True

        self.logger.info("Cloning repository from %s to %s...", repo_url, local_path)
        try:
            git.Repo.clone_from(repo_url, local_path, depth=1, single_branch=True)
            self.logger.info("Repository cloned successfully.")
            return True
        except git.exc.GitCommandError as exc:
            self.logger.error("Error cloning repository: %s", exc)
            return False

    def _parse_github_repo(self, repo_url: str) -> Optional[Tuple[str, str]]:
        match = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?/?$", repo_url.strip())
        if not match:
            return None
        return match.group(1), match.group(2)

    @staticmethod
    def build_collection_name(repo_url: str) -> str:
        match = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?/?$", repo_url.strip())
        if match:
            return f"{match.group(1).lower()}__{match.group(2).lower()}"

        fallback = repo_url.rstrip("/").split("/")[-1].removesuffix(".git") or "repository"
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", fallback).lower()

    @staticmethod
    def _retry_delay_seconds(attempt: int) -> float:
        return min(2.0, 0.35 * attempt)

    def _http_get_bytes(
        self,
        url: str,
        *,
        accept: Optional[str] = None,
        max_bytes: Optional[int] = None,
    ) -> Optional[bytes]:
        headers = {
            "Accept-Encoding": "identity",
            "User-Agent": "ArchiMind/1.0",
        }
        if accept:
            headers["Accept"] = accept

        for attempt in range(1, self._HTTP_MAX_ATTEMPTS + 1):
            request = Request(url, headers=headers)
            try:
                with urlopen(request, timeout=config.REQUEST_TIMEOUT_SECONDS) as response:
                    payload = response.read() if max_bytes is None else response.read(max_bytes)
                return payload or None
            except IncompleteRead as exc:
                partial = exc.partial or b""
                if partial and max_bytes is not None:
                    self.logger.warning(
                        "Using partial payload after IncompleteRead for %s on attempt %s/%s (%s bytes)",
                        url,
                        attempt,
                        self._HTTP_MAX_ATTEMPTS,
                        len(partial),
                    )
                    return partial

                self.logger.warning(
                    "Retrying %s after IncompleteRead on attempt %s/%s (%s bytes read)",
                    url,
                    attempt,
                    self._HTTP_MAX_ATTEMPTS,
                    len(partial),
                )
                if attempt == self._HTTP_MAX_ATTEMPTS:
                    return partial or None
            except HTTPError as exc:
                self.logger.warning("HTTP error while fetching %s: %s", url, exc)
                if exc.code not in self._HTTP_RETRYABLE_STATUS_CODES or attempt == self._HTTP_MAX_ATTEMPTS:
                    return None
            except (URLError, TimeoutError, OSError) as exc:
                self.logger.warning("Retrying %s after transport error on attempt %s/%s: %s", url, attempt, self._HTTP_MAX_ATTEMPTS, exc)
                if attempt == self._HTTP_MAX_ATTEMPTS:
                    return None

            time.sleep(self._retry_delay_seconds(attempt))

        return None

    def _http_get_json(self, url: str) -> Optional[dict]:
        for attempt in range(1, self._HTTP_MAX_ATTEMPTS + 1):
            payload = self._http_get_bytes(url, accept="application/vnd.github+json")
            if not payload:
                return None

            try:
                return json.loads(payload.decode("utf-8", errors="ignore"))
            except json.JSONDecodeError as exc:
                self.logger.warning(
                    "Retrying %s after incomplete JSON payload on attempt %s/%s: %s",
                    url,
                    attempt,
                    self._HTTP_MAX_ATTEMPTS,
                    exc,
                )
                if attempt == self._HTTP_MAX_ATTEMPTS:
                    return None
                time.sleep(self._retry_delay_seconds(attempt))

        return None

    def _http_get_text(self, url: str, max_bytes: int = 350_000) -> Optional[str]:
        payload = self._http_get_bytes(url, max_bytes=max_bytes)

        if not payload:
            return None
        return payload.decode("utf-8", errors="ignore")

    @staticmethod
    def _is_allowed_file(file_path: str, allowed_extensions: Set[str], ignored_dirs: Set[str]) -> bool:
        parts = file_path.split("/")
        if any(part in ignored_dirs for part in parts[:-1]):
            return False
        extension = os.path.splitext(file_path)[1]
        file_name = os.path.basename(file_path)
        return extension in allowed_extensions or file_name in allowed_extensions

    @staticmethod
    def _score_path_priority(file_path: str) -> int:
        lowered = file_path.lower()
        score = 0

        if lowered.startswith("readme") or "/readme" in lowered:
            score += 200
        if lowered.startswith("docs/") or "/docs/" in lowered:
            score += 130
        if any(token in lowered for token in ["architecture", "design", "diagram", "hld", "lld"]):
            score += 120
        if any(token in lowered for token in ["dockerfile", "docker-compose", "requirements", "pyproject", "setup.py"]):
            score += 100
        if any(token in lowered for token in ["app", "main", "server", "api", "service", "worker", "model", "controller"]):
            score += 80
        if lowered.endswith(".md"):
            score += 30
        if lowered.count("/") <= 1:
            score += 20
        return score

    def _select_remote_paths(
        self,
        tree_entries: List[dict],
        allowed_extensions: Set[str],
        ignored_dirs: Set[str],
    ) -> List[dict]:
        candidates: List[dict] = []
        for entry in tree_entries:
            if entry.get("type") != "blob":
                continue
            path = entry.get("path", "")
            if not path or not self._is_allowed_file(path, allowed_extensions, ignored_dirs):
                continue
            size = entry.get("size") or 0
            if size > config.REMOTE_FILE_MAX_BYTES:
                continue
            ranked = dict(entry)
            ranked["priority"] = self._score_path_priority(path)
            candidates.append(ranked)

        if len(candidates) <= config.REMOTE_FETCH_MAX_FILES:
            return candidates

        candidates.sort(key=lambda item: (item.get("priority", 0), -(item.get("size") or 0)), reverse=True)
        return candidates[: config.REMOTE_FETCH_MAX_FILES]

    def _fetch_remote_repository_files(
        self,
        repo_url: str,
        allowed_extensions: Set[str],
        ignored_dirs: Set[str],
    ) -> Dict[str, str]:
        parsed = self._parse_github_repo(repo_url)
        if not parsed:
            return {}

        owner, repository = parsed
        repo_meta = self._http_get_json(f"https://api.github.com/repos/{owner}/{repository}")
        if not repo_meta:
            return {}

        default_branch = repo_meta.get("default_branch") or "main"
        tree_data = self._http_get_json(
            f"https://api.github.com/repos/{owner}/{repository}/git/trees/{default_branch}?recursive=1"
        )
        if not tree_data:
            return {}

        entries = tree_data.get("tree") or []
        selected = self._select_remote_paths(entries, allowed_extensions, ignored_dirs)
        if not selected:
            return {}

        files: Dict[str, str] = {}
        raw_base = f"https://raw.githubusercontent.com/{owner}/{repository}/{default_branch}"

        def fetch_entry(entry: dict) -> Optional[Tuple[str, str]]:
            file_path = entry.get("path")
            if not file_path:
                return None

            file_text = self._http_get_text(
                f"{raw_base}/{file_path}",
                max_bytes=config.REMOTE_FILE_MAX_BYTES,
            )
            if file_text and file_text.strip():
                return file_path, file_text
            return None

        with ThreadPoolExecutor(max_workers=max(2, config.REMOTE_FETCH_CONCURRENCY)) as executor:
            future_map = {executor.submit(fetch_entry, entry): entry.get("path", "") for entry in selected}
            for future in as_completed(future_map):
                try:
                    result = future.result()
                except Exception as exc:
                    self.logger.warning("Failed to fetch remote file %s: %s", future_map[future], exc)
                    continue

                if result:
                    files[result[0]] = result[1]

        overview = (
            f"Repository: {owner}/{repository}\n"
            f"Description: {repo_meta.get('description') or 'N/A'}\n"
            f"Primary language: {repo_meta.get('language') or 'N/A'}\n"
            f"Stars: {repo_meta.get('stargazers_count', 0)}\n"
            f"Open issues: {repo_meta.get('open_issues_count', 0)}\n"
            f"Default branch: {default_branch}\n"
            f"Topics: {', '.join(repo_meta.get('topics') or [])}\n"
            f"Tree truncated by GitHub API: {bool(tree_data.get('truncated'))}\n"
            f"Ingestion strategy: selective remote fetch ({len(files)} files out of {len(entries)} tree entries).\n"
        )
        files["__repo_overview__.md"] = overview
        return files

    def get_repository_preview(self, repo_url: str) -> Optional[Dict[str, object]]:
        parsed = self._parse_github_repo(repo_url)
        if not parsed:
            return None

        owner, repository = parsed
        repo_meta = self._http_get_json(f"https://api.github.com/repos/{owner}/{repository}")
        if not repo_meta:
            return None

        return {
            "owner": owner,
            "repo_name": repo_meta.get("name") or repository,
            "full_name": repo_meta.get("full_name") or f"{owner}/{repository}",
            "description": repo_meta.get("description") or "No description available.",
            "language": repo_meta.get("language") or "Unknown",
            "stars": repo_meta.get("stargazers_count", 0),
            "forks": repo_meta.get("forks_count", 0),
            "open_issues": repo_meta.get("open_issues_count", 0),
            "topics": repo_meta.get("topics") or [],
            "default_branch": repo_meta.get("default_branch") or "main",
            "html_url": repo_meta.get("html_url") or repo_url,
            "updated_at": repo_meta.get("updated_at"),
        }

    def collect_repository_files(
        self,
        repo_url: str,
        local_path: str,
        allowed_extensions: Set[str],
        ignored_dirs: Set[str],
    ) -> Dict[str, str]:
        self.logger.info("Collecting repository context for %s", repo_url)

        remote_files = self._fetch_remote_repository_files(repo_url, allowed_extensions, ignored_dirs)
        if remote_files:
            self.logger.info("Using selective remote ingestion with %s files", len(remote_files))
            return remote_files

        self.logger.info("Remote ingestion unavailable; falling back to local clone")
        if os.path.exists(local_path):
            shutil.rmtree(local_path, ignore_errors=True)

        if not self.clone_repository(repo_url, local_path):
            return {}
        return self.read_repository_files(local_path, allowed_extensions, ignored_dirs)

    def read_repository_files(
        self,
        repo_path: str,
        allowed_extensions: Set[str],
        ignored_dirs: Set[str],
    ) -> Dict[str, str]:
        file_contents: Dict[str, str] = {}
        self.logger.info("Reading files from repository...")

        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            for file_name in files:
                ext = os.path.splitext(file_name)[1]
                if ext in allowed_extensions or file_name in allowed_extensions:
                    file_path = os.path.join(root, file_name)
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
                            relative = os.path.relpath(file_path, repo_path)
                            file_contents[relative] = handle.read()
                    except Exception as exc:
                        self.logger.warning("Could not read file %s: %s", file_path, exc)

        self.logger.info("Collected %s files from repository.", len(file_contents))
        return file_contents


class _SimpleCollection:
    """Tiny JSON-backed collection used when ChromaDB is unavailable."""

    def __init__(self, db_path: str, collection_name: str):
        os.makedirs(db_path, exist_ok=True)
        self._file_path = os.path.join(db_path, f"{collection_name}.json")
        self._records: Dict[str, Dict[str, object]] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self._file_path):
            return
        try:
            with open(self._file_path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
            if isinstance(raw, dict):
                self._records = raw
        except Exception:
            self._records = {}

    def _save(self) -> None:
        with open(self._file_path, "w", encoding="utf-8") as handle:
            json.dump(self._records, handle)

    def count(self) -> int:
        return len(self._records)

    def clear(self) -> None:
        self._records = {}
        self._save()

    def add(
        self,
        documents: List[str],
        ids: List[str],
        metadatas: Optional[List[Dict[str, object]]] = None,
        embeddings: Optional[List[List[float]]] = None,
    ) -> None:
        metadatas = metadatas or [{} for _ in documents]
        embeddings = embeddings or [[] for _ in documents]
        for doc, doc_id, meta, emb in zip(documents, ids, metadatas, embeddings):
            self._records[doc_id] = {"document": doc, "metadata": meta, "embedding": emb}
        self._save()

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return -1.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return -1.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _keyword_score(query_text: str, text: str) -> float:
        if not query_text or not text:
            return 0.0
        tokens = {tok for tok in re.split(r"\W+", query_text.lower()) if tok}
        if not tokens:
            return 0.0
        lowered = text.lower()
        hits = sum(1 for tok in tokens if tok in lowered)
        return hits / max(1, len(tokens))

    def query(
        self,
        query_embeddings: Optional[List[List[float]]] = None,
        query_texts: Optional[List[str]] = None,
        n_results: int = 5,
        where: Optional[Dict[str, object]] = None,
    ) -> Dict[str, List[List[object]]]:
        ranked: List[Tuple[float, str, str, Dict[str, object]]] = []
        where = where or {}

        text_query = query_texts[0] if query_texts else ""
        emb_query = query_embeddings[0] if query_embeddings else []

        for doc_id, payload in self._records.items():
            metadata = payload.get("metadata", {}) or {}
            file_path_filter = where.get("file_path")
            if file_path_filter and metadata.get("file_path") != file_path_filter:
                continue

            if emb_query:
                score = self._cosine_similarity(emb_query, payload.get("embedding", []))
            else:
                score = self._keyword_score(text_query, payload.get("document", ""))

            ranked.append((score, doc_id, payload.get("document", ""), metadata))

        ranked.sort(key=lambda item: item[0], reverse=True)
        top = ranked[: max(1, n_results)]
        return {
            "ids": [[item[1] for item in top]],
            "documents": [[item[2] for item in top]],
            "metadatas": [[item[3] for item in top]],
        }


class _PineconeCollection:
    """Pinecone-backed collection with document metadata persistence."""

    def __init__(
        self,
        api_key: str,
        index_name: str,
        namespace: str,
        dimension: int,
        cloud: str,
        region: str,
        host: Optional[str] = None,
    ):
        if Pinecone is None:
            raise ConfigurationError("Pinecone backend requested but pinecone package is unavailable")

        self._namespace = namespace
        self._dimension = dimension
        self._client = Pinecone(api_key=api_key)
        self._index_name = index_name
        self._host = host
        self._ensure_index(cloud, region)
        if self._host:
            self._index = self._client.Index(host=self._host)
        else:
            self._index = self._client.Index(index_name)

    @property
    def dimension(self) -> int:
        return self._dimension

    def _list_index_names(self) -> Set[str]:
        raw_indexes = self._client.list_indexes()
        if hasattr(raw_indexes, "names"):
            return set(raw_indexes.names())

        names: Set[str] = set()
        iterable = raw_indexes if isinstance(raw_indexes, list) else getattr(raw_indexes, "indexes", raw_indexes)
        for item in iterable or []:
            if isinstance(item, str):
                names.add(item)
            elif isinstance(item, dict) and item.get("name"):
                names.add(item["name"])
            else:
                name = getattr(item, "name", None)
                if name:
                    names.add(name)
        return names

    def _ensure_index(self, cloud: str, region: str) -> None:
        if self._index_name in self._list_index_names():
            index_info = self._client.describe_index(self._index_name)
            self._dimension = int(_extract_index_attribute(index_info, "dimension") or self._dimension)
            self._host = self._host or _extract_index_attribute(index_info, "host")
            return

        if ServerlessSpec is None:
            raise ConfigurationError("Pinecone serverless support is unavailable in this environment")

        self._client.create_index(
            name=self._index_name,
            dimension=self._dimension,
            metric="cosine",
            spec=ServerlessSpec(cloud=cloud, region=region),
        )
        time.sleep(2)
        index_info = self._client.describe_index(self._index_name)
        self._dimension = int(_extract_index_attribute(index_info, "dimension") or self._dimension)
        self._host = self._host or _extract_index_attribute(index_info, "host")

    def count(self) -> int:
        stats = self._index.describe_index_stats()
        namespaces = getattr(stats, "namespaces", None)
        if namespaces is None and isinstance(stats, dict):
            namespaces = stats.get("namespaces", {})
        if not isinstance(namespaces, dict):
            return 0

        namespace_stats = namespaces.get(self._namespace, {})
        if isinstance(namespace_stats, dict):
            return int(namespace_stats.get("vector_count", 0))
        return int(getattr(namespace_stats, "vector_count", 0))

    def clear(self) -> None:
        delete_method = getattr(self._index, "delete", None)
        if not callable(delete_method):
            return
        try:
            delete_method(delete_all=True, namespace=self._namespace)
        except TypeError:
            try:
                delete_method(namespace=self._namespace, delete_all=True)
            except Exception as exc:
                if _is_pinecone_namespace_missing_error(exc):
                    return
                raise
        except Exception as exc:
            if _is_pinecone_namespace_missing_error(exc):
                return
            raise

    def add(
        self,
        documents: List[str],
        ids: List[str],
        metadatas: Optional[List[Dict[str, object]]] = None,
        embeddings: Optional[List[List[float]]] = None,
    ) -> None:
        metadatas = metadatas or [{} for _ in documents]
        embeddings = embeddings or [[] for _ in documents]
        vectors = []

        for doc, doc_id, meta, emb in zip(documents, ids, metadatas, embeddings):
            payload = dict(meta)
            payload["document"] = doc
            vectors.append({"id": doc_id, "values": emb, "metadata": payload})

        for start in range(0, len(vectors), 100):
            self._index.upsert(vectors=vectors[start : start + 100], namespace=self._namespace)

    def query(
        self,
        query_embeddings: Optional[List[List[float]]] = None,
        query_texts: Optional[List[str]] = None,
        n_results: int = 5,
        where: Optional[Dict[str, object]] = None,
    ) -> Dict[str, List[List[object]]]:
        del query_texts

        vector = (query_embeddings or [[0.0] * self._dimension])[0]
        try:
            result = self._index.query(
                namespace=self._namespace,
                vector=vector,
                top_k=n_results,
                include_metadata=True,
                filter=where or None,
            )
        except Exception as exc:
            if _is_pinecone_namespace_missing_error(exc):
                return {"ids": [[]], "documents": [[]], "metadatas": [[]]}
            raise

        raw_matches = getattr(result, "matches", None)
        if raw_matches is None and isinstance(result, dict):
            raw_matches = result.get("matches", [])

        ids: List[object] = []
        documents: List[object] = []
        metadatas: List[object] = []

        for match in raw_matches or []:
            if isinstance(match, dict):
                metadata = dict(match.get("metadata") or {})
                ids.append(match.get("id"))
            else:
                metadata = dict(getattr(match, "metadata", None) or {})
                ids.append(getattr(match, "id", None))

            documents.append(metadata.pop("document", ""))
            metadatas.append(metadata)

        return {"ids": [ids], "documents": [documents], "metadatas": [metadatas]}


class VectorStoreService:
    """Hierarchical code index with AST chunking and pluggable vector storage."""

    def __init__(self, db_path: str, collection_name: str, embedding_model: str, repo_url: str = ""):
        self.db_path = db_path
        self.collection_name = self._sanitize_collection_name(collection_name)
        self.summary_collection_name = f"{self.collection_name}_summaries"
        self.chunk_collection_name = f"{self.collection_name}_chunks"
        self.embedding_model = embedding_model
        self.repo_url = repo_url.rstrip("/")
        self.embedding_dimension = config.PINECONE_DIMENSION
        self.vector_backend = config.VECTOR_BACKEND.lower()
        self.logger = logging.getLogger(self.__class__.__name__)
        self._initialize_database()

    def _initialize_database(self) -> None:
        try:
            if self.vector_backend == "pinecone" and config.PINECONE_API_KEY:
                self.summary_collection = _PineconeCollection(
                    api_key=config.PINECONE_API_KEY,
                    index_name=config.PINECONE_INDEX_NAME,
                    namespace=f"{config.PINECONE_NAMESPACE}:{self.collection_name}:summaries",
                    dimension=self.embedding_dimension,
                    cloud=config.PINECONE_CLOUD,
                    region=config.PINECONE_REGION,
                    host=config.PINECONE_HOST,
                )
                self.chunk_collection = _PineconeCollection(
                    api_key=config.PINECONE_API_KEY,
                    index_name=config.PINECONE_INDEX_NAME,
                    namespace=f"{config.PINECONE_NAMESPACE}:{self.collection_name}:chunks",
                    dimension=self.embedding_dimension,
                    cloud=config.PINECONE_CLOUD,
                    region=config.PINECONE_REGION,
                    host=config.PINECONE_HOST,
                )
                backend = "Pinecone"
            elif chromadb is not None and self.vector_backend == "chroma":
                self.chroma_client = chromadb.PersistentClient(path=self.db_path)
                self.summary_collection = self.chroma_client.get_or_create_collection(
                    name=self.summary_collection_name
                )
                self.chunk_collection = self.chroma_client.get_or_create_collection(
                    name=self.chunk_collection_name
                )
                backend = "ChromaDB"
            else:
                self.summary_collection = _SimpleCollection(self.db_path, self.summary_collection_name)
                self.chunk_collection = _SimpleCollection(self.db_path, self.chunk_collection_name)
                backend = "SimpleJSON"

            self.collection = self.chunk_collection
            self.logger.info(
                "Vector index initialized: %s (backend=%s, chunker=LlamaIndex-CodeSplitter)",
                self.collection_name,
                backend,
            )
            if self.vector_backend == "pinecone":
                self.embedding_dimension = getattr(self.chunk_collection, "dimension", self.embedding_dimension)
        except Exception as exc:
            formatted_error = _format_vector_backend_error(exc)
            self.logger.error("Failed to initialize vector store: %s", formatted_error)
            raise ConfigurationError(f"Vector store initialization failed: {formatted_error}")

    @staticmethod
    def _sanitize_collection_name(name: str) -> str:
        return name.replace("-", "_").replace(".", "_").replace("/", "_")

    def _normalize_embedding(self, values: List[float]) -> List[float]:
        if len(values) > self.embedding_dimension:
            values = values[: self.embedding_dimension]
        elif len(values) < self.embedding_dimension:
            values = values + [0.0] * (self.embedding_dimension - len(values))

        magnitude = math.sqrt(sum(value * value for value in values))
        if magnitude == 0:
            return values
        return [value / magnitude for value in values]

    def _hash_embed_text(self, text: str) -> List[float]:
        tokens = [token for token in re.split(r"\W+", text.lower()) if token][:2200]
        vector = [0.0] * self.embedding_dimension
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            weight = min(2.0, 1.0 + (len(token) / 12.0))
            for offset in range(0, 8, 2):
                index = int.from_bytes(digest[offset : offset + 2], "big") % self.embedding_dimension
                sign = 1.0 if digest[offset + 8] % 2 == 0 else -1.0
                vector[index] += sign * weight

        return self._normalize_embedding(vector)

    def _embed_with_gemini(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        if genai is None or genai_types is None or not config.GEMINI_API_KEY:
            raise ConfigurationError("Gemini embeddings requested without API support")

        client_kwargs = {"api_key": config.GEMINI_API_KEY}
        if config.GEMINI_API_VERSION and getattr(genai_types, "HttpOptions", None) is not None:
            client_kwargs["http_options"] = genai_types.HttpOptions(api_version=config.GEMINI_API_VERSION)

        model_names = [self.embedding_model]
        if self.embedding_model != "gemini-embedding-001":
            model_names.append("gemini-embedding-001")

        last_error = None
        response = None
        with genai.Client(**client_kwargs) as client:
            for model_name in model_names:
                try:
                    response = client.models.embed_content(model=model_name, contents=texts)
                    break
                except Exception as exc:
                    last_error = exc

        if response is None:
            raise last_error or ConfigurationError("Gemini embeddings failed")

        response_embeddings = getattr(response, "embeddings", None)
        if response_embeddings is None and isinstance(response, dict):
            response_embeddings = response.get("embeddings", [])

        embeddings: List[List[float]] = []
        for item in response_embeddings or []:
            values = getattr(item, "values", None)
            if values is None and isinstance(item, dict):
                values = item.get("values", [])
            embeddings.append(self._normalize_embedding(list(values or [])))

        return embeddings

    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        if config.GEMINI_API_KEY:
            try:
                embeddings = self._embed_with_gemini(texts)
                if len(embeddings) == len(texts):
                    return embeddings
            except Exception as exc:
                self.logger.warning("Embedding fallback engaged after Gemini embed failure: %s", exc)

        return [self._hash_embed_text(text) for text in texts]

    def is_empty(self) -> bool:
        return self.chunk_collection.count() == 0

    def reset(self) -> None:
        if chromadb is not None and self.vector_backend == "chroma":
            delete_collection = getattr(self.chroma_client, "delete_collection", None)
            if callable(delete_collection):
                for collection_name in (self.summary_collection_name, self.chunk_collection_name):
                    try:
                        delete_collection(name=collection_name)
                    except TypeError:
                        delete_collection(collection_name)
                    except Exception:
                        pass

                self.summary_collection = self.chroma_client.get_or_create_collection(name=self.summary_collection_name)
                self.chunk_collection = self.chroma_client.get_or_create_collection(name=self.chunk_collection_name)
                self.collection = self.chunk_collection
                self.logger.info("Reset vector index: %s", self.collection_name)
                return

        for collection in (self.summary_collection, self.chunk_collection):
            clear_method = getattr(collection, "clear", None)
            if callable(clear_method):
                clear_method()
                continue

            get_method = getattr(collection, "get", None)
            delete_method = getattr(collection, "delete", None)
            if callable(get_method) and callable(delete_method):
                payload = get_method()
                ids = payload.get("ids") if isinstance(payload, dict) else None
                if ids:
                    delete_method(ids=ids)

        self.collection = self.chunk_collection
        self.logger.info("Reset vector index: %s", self.collection_name)

    def _guess_language(self, file_path: str) -> str:
        extension = os.path.splitext(file_path)[1].lower()
        mapping = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".go": "go",
            ".rs": "rust",
            ".md": "markdown",
            ".json": "json",
            ".yml": "yaml",
            ".yaml": "yaml",
            ".html": "html",
            ".css": "css",
            ".sh": "bash",
        }
        if os.path.basename(file_path) == "Dockerfile":
            return "dockerfile"
        return mapping.get(extension, "text")

    def _extract_python_blocks(self, source: str) -> List[Tuple[str, str, int, int]]:
        blocks: List[Tuple[str, str, int, int]] = []
        lines = source.splitlines()
        try:
            tree = ast.parse(source)
        except Exception:
            return []

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = getattr(node, "lineno", 1)
                end = getattr(node, "end_lineno", start)
                block = "\n".join(lines[start - 1 : end]).strip()
                if block:
                    blocks.append((block, node.name, start, end))
        return blocks

    def _llama_code_split(self, content: str, language: str) -> List[str]:
        if CodeSplitter is None:
            return []
        try:
            splitter = CodeSplitter(language=language, chunk_lines=120, chunk_lines_overlap=20, max_chars=3200)
            chunks = splitter.split_text(content)
            return [chunk for chunk in chunks if chunk.strip()]
        except Exception:
            return []

    def _line_based_split(self, content: str, step: int = 80) -> List[Tuple[str, int, int]]:
        lines = content.splitlines()
        chunks: List[Tuple[str, int, int]] = []
        for index in range(0, len(lines), step):
            start = index + 1
            end = min(len(lines), index + step)
            chunk = "\n".join(lines[index:end]).strip()
            if chunk:
                chunks.append((chunk, start, end))
        return chunks

    def _build_summary(self, file_path: str, content: str) -> str:
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        non_comment = [line for line in lines if not line.startswith("#") and not line.startswith("//")]
        first_line = non_comment[0] if non_comment else "File has minimal content."

        class_count = len(re.findall(r"\bclass\s+\w+", content))
        fn_count = len(re.findall(r"\b(def|function)\s+\w+", content))
        import_count = len(re.findall(r"\b(import|from)\b", content))

        return (
            f"{file_path} appears to define core logic around: {first_line[:140]}. "
            f"It contains approximately {class_count} classes, {fn_count} functions, and {import_count} import statements."
        )

    def _build_github_url(self, file_path: str, start_line: int, end_line: int) -> str:
        if not self.repo_url:
            return ""
        base = self.repo_url.replace(".git", "")
        if start_line > 0 and end_line >= start_line:
            return f"{base}/blob/main/{file_path}#L{start_line}-L{end_line}"
        return f"{base}/blob/main/{file_path}"

    def _make_chunk_records(self, file_path: str, content: str) -> List[ChunkRecord]:
        language = self._guess_language(file_path)
        records: List[ChunkRecord] = []

        python_blocks = self._extract_python_blocks(content) if language == "python" else []
        if python_blocks:
            for index, (chunk, fn_name, start_line, end_line) in enumerate(python_blocks):
                chunk_id = hashlib.sha256(f"{file_path}:{start_line}:{index}".encode("utf-8")).hexdigest()[:16]
                metadata = {
                    "file_path": file_path,
                    "language": language,
                    "function_name": fn_name,
                    "github_url": self._build_github_url(file_path, start_line, end_line),
                    "start_line": start_line,
                    "end_line": end_line,
                }
                records.append(ChunkRecord(chunk_id=chunk_id, text=chunk, metadata=metadata))
            return records

        llama_chunks = self._llama_code_split(content, language)
        if llama_chunks:
            for index, chunk in enumerate(llama_chunks):
                fn_match = re.search(r"\b(def|class|function)\s+([A-Za-z_][A-Za-z0-9_]*)", chunk)
                fn_name = fn_match.group(2) if fn_match else ""
                start_line = content[: content.find(chunk)].count("\n") + 1 if chunk in content else 1
                end_line = start_line + chunk.count("\n")
                chunk_id = hashlib.sha256(f"{file_path}:llama:{index}".encode("utf-8")).hexdigest()[:16]
                metadata = {
                    "file_path": file_path,
                    "language": language,
                    "function_name": fn_name,
                    "github_url": self._build_github_url(file_path, start_line, end_line),
                    "start_line": start_line,
                    "end_line": end_line,
                }
                records.append(ChunkRecord(chunk_id=chunk_id, text=chunk, metadata=metadata))
            return records

        for index, (chunk, start_line, end_line) in enumerate(self._line_based_split(content)):
            fn_match = re.search(r"\b(def|class|function)\s+([A-Za-z_][A-Za-z0-9_]*)", chunk)
            fn_name = fn_match.group(2) if fn_match else ""
            chunk_id = hashlib.sha256(f"{file_path}:line:{index}".encode("utf-8")).hexdigest()[:16]
            metadata = {
                "file_path": file_path,
                "language": language,
                "function_name": fn_name,
                "github_url": self._build_github_url(file_path, start_line, end_line),
                "start_line": start_line,
                "end_line": end_line,
            }
            records.append(ChunkRecord(chunk_id=chunk_id, text=chunk, metadata=metadata))

        return records

    def generate_embeddings(self, file_contents: Dict[str, str]) -> None:
        self.logger.info("Building hierarchical index (file summaries + AST code chunks)...")

        summary_ids: List[str] = []
        summary_docs: List[str] = []
        summary_metas: List[Dict[str, object]] = []
        chunk_ids: List[str] = []
        chunk_docs: List[str] = []
        chunk_metas: List[Dict[str, object]] = []

        for file_path, content in file_contents.items():
            if not content.strip():
                continue

            language = self._guess_language(file_path)
            summary_id = hashlib.sha256(f"summary:{file_path}".encode("utf-8")).hexdigest()[:16]
            summary_doc = self._build_summary(file_path, content)
            summary_meta = {
                "file_path": file_path,
                "language": language,
                "function_name": "",
                "github_url": self._build_github_url(file_path, 0, 0),
            }

            summary_ids.append(summary_id)
            summary_docs.append(summary_doc)
            summary_metas.append(summary_meta)

            chunk_records = self._make_chunk_records(file_path, content)
            if not chunk_records:
                continue

            chunk_ids.extend(record.chunk_id for record in chunk_records)
            chunk_docs.extend(record.text for record in chunk_records)
            chunk_metas.extend(record.metadata for record in chunk_records)

        if summary_docs:
            self.summary_collection.add(
                ids=summary_ids,
                documents=summary_docs,
                metadatas=summary_metas,
                embeddings=self._embed_texts(summary_docs),
            )

        if chunk_docs:
            self.chunk_collection.add(
                ids=chunk_ids,
                documents=chunk_docs,
                metadatas=chunk_metas,
                embeddings=self._embed_texts(chunk_docs),
            )

        self.logger.info(
            "Index build complete. summary_count=%s chunk_count=%s",
            self.summary_collection.count(),
            self.chunk_collection.count(),
        )

    def _query_collection(
        self,
        collection,
        query_text: str,
        n_results: int,
        where: Optional[Dict[str, object]] = None,
        query_embedding: Optional[List[float]] = None,
    ) -> Dict[str, List[List[object]]]:
        query_kwargs = {"n_results": n_results}
        if where:
            query_kwargs["where"] = where
        if query_embedding:
            query_kwargs["query_embeddings"] = [query_embedding]
        else:
            query_kwargs["query_texts"] = [query_text]
        try:
            return collection.query(**query_kwargs)
        except TypeError:
            if query_embedding:
                return collection.query(query_embeddings=[query_embedding], n_results=n_results)
            return collection.query(query_texts=[query_text], n_results=n_results)

    def query_similar_documents(self, query_text: str, n_results: int = 15) -> str:
        if self.chunk_collection.count() == 0:
            return ""

        query_embedding = self._embed_texts([query_text])[0]

        class RetrievalState(TypedDict):
            question: str
            candidate_files: List[str]
            summary_hits: List[Dict[str, object]]
            chunk_hits: List[Dict[str, object]]
            context: str

        def select_files(state: RetrievalState) -> RetrievalState:
            result = self._query_collection(
                self.summary_collection,
                query_text=state["question"],
                n_results=min(8, max(1, self.summary_collection.count())),
                query_embedding=query_embedding,
            )
            docs = result.get("documents", [[]])[0]
            metas = result.get("metadatas", [[]])[0]
            candidate_files = [meta.get("file_path") for meta in metas if isinstance(meta, dict) and meta.get("file_path")]
            state["candidate_files"] = list(dict.fromkeys(candidate_files))
            state["summary_hits"] = [
                {"document": doc, "metadata": meta or {}}
                for doc, meta in zip(docs, metas)
                if isinstance(meta, dict) and meta.get("file_path")
            ]
            return state

        def collect_chunks(state: RetrievalState) -> RetrievalState:
            hits: List[Dict[str, object]] = []

            target_files = state["candidate_files"][:5]
            if not target_files:
                result = self._query_collection(
                    self.chunk_collection,
                    query_text=state["question"],
                    n_results=min(n_results, max(1, self.chunk_collection.count())),
                    query_embedding=query_embedding,
                )
                docs = result.get("documents", [[]])[0]
                metas = result.get("metadatas", [[]])[0]
                for doc, meta in zip(docs, metas):
                    hits.append({"document": doc, "metadata": meta or {}})
            else:
                each_limit = max(1, math.ceil(n_results / max(1, len(target_files))))
                for file_path in target_files:
                    result = self._query_collection(
                        self.chunk_collection,
                        query_text=state["question"],
                        n_results=each_limit,
                        where={"file_path": file_path},
                        query_embedding=query_embedding,
                    )
                    docs = result.get("documents", [[]])[0]
                    metas = result.get("metadatas", [[]])[0]
                    for doc, meta in zip(docs, metas):
                        hits.append({"document": doc, "metadata": meta or {}})

            state["chunk_hits"] = hits[:n_results]
            return state

        def render_context(state: RetrievalState) -> RetrievalState:
            context_parts: List[str] = []

            for hit in state["summary_hits"][:5]:
                meta = hit.get("metadata", {})
                context_parts.append(
                    "\n".join(
                        [
                            f"--- File: {meta.get('file_path', 'unknown')} ---",
                            f"language={meta.get('language', 'text')}",
                            "function_name=file_summary",
                            f"github_url={meta.get('github_url', '')}",
                            "",
                            f"Repository file summary: {hit.get('document', '')}",
                            "",
                        ]
                    )
                )

            for hit in state["chunk_hits"]:
                meta = hit.get("metadata", {})
                context_parts.append(
                    "\n".join(
                        [
                            f"--- File: {meta.get('file_path', 'unknown')} ---",
                            f"language={meta.get('language', 'text')}",
                            f"function_name={meta.get('function_name', '')}",
                            f"github_url={meta.get('github_url', '')}",
                            "",
                            hit.get("document", ""),
                            "",
                        ]
                    )
                )
            state["context"] = "\n".join(context_parts)
            return state

        initial_state: RetrievalState = {
            "question": query_text,
            "candidate_files": [],
            "summary_hits": [],
            "chunk_hits": [],
            "context": "",
        }

        if StateGraph is not None:
            try:
                graph = StateGraph(RetrievalState)
                graph.add_node("select_files", select_files)
                graph.add_node("collect_chunks", collect_chunks)
                graph.add_node("render_context", render_context)
                graph.set_entry_point("select_files")
                graph.add_edge("select_files", "collect_chunks")
                graph.add_edge("collect_chunks", "render_context")
                graph.add_edge("render_context", END)
                app = graph.compile()
                final_state = app.invoke(initial_state)
            except Exception:
                final_state = render_context(collect_chunks(select_files(initial_state)))
        else:
            final_state = render_context(collect_chunks(select_files(initial_state)))

        return final_state["context"]


class DocumentationService:
    """Lightweight documentation service built on retrieved project context."""

    CONTEXT_BLOCK_PATTERN = re.compile(
        r"--- File: (?P<file_path>.+?) ---\n"
        r"language=(?P<language>[^\n]*)\n"
        r"function_name=(?P<function_name>[^\n]*)\n"
        r"github_url=(?P<github_url>[^\n]*)\n\n"
        r"(?P<content>.*?)(?=\n--- File: |\Z)",
        re.DOTALL,
    )

    GRAPH_RESPONSE_SCHEMA = {
        "type": "object",
        "required": ["title", "description", "mermaid_code"],
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "mermaid_code": {"type": "string"},
        },
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "local",
        chat_model_name: Optional[str] = None,
        thinking_level: str = "high",
        api_version: str = "v1alpha",
        context_char_limit: int = 28000,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model_name = model_name
        self.chat_model_name = chat_model_name or model_name
        self.thinking_level = thinking_level
        self.api_version = api_version
        self.context_char_limit = max(4000, context_char_limit)
        self.logger = logging.getLogger(self.__class__.__name__)

    def _can_use_gemini(self) -> bool:
        return bool(
            self.model_name != "local"
            and self.api_key
            and genai is not None
            and genai_types is not None
        )

    def describe_backend(self) -> str:
        if self._can_use_gemini():
            return f"gemini:{self.model_name}"
        return "local"

    def _clip_context(self, context: str) -> str:
        cleaned = context.strip()
        if len(cleaned) <= self.context_char_limit:
            return cleaned

        truncated = cleaned[: self.context_char_limit]
        return truncated.rsplit("\n", 1)[0].strip()

    @staticmethod
    def _response_to_text(response: object) -> str:
        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()

        parts = getattr(response, "parts", None) or []
        fragments = [getattr(part, "text", "") for part in parts if getattr(part, "text", "")]
        return "".join(fragments).strip()

    def _generate_with_gemini(
        self,
        prompt: str,
        model_name: str,
        response_mime_type: str = "text/plain",
        response_json_schema: Optional[Dict[str, object]] = None,
        system_instruction: Optional[str] = None,
    ) -> str:
        if not self._can_use_gemini():
            raise ConfigurationError("Gemini generation requested without SDK support or API key")

        config_kwargs = {
            "thinking_config": genai_types.ThinkingConfig(thinking_level=self.thinking_level),
            "response_mime_type": response_mime_type,
        }
        if response_json_schema:
            config_kwargs["response_json_schema"] = response_json_schema
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        generation_config = genai_types.GenerateContentConfig(**config_kwargs)
        client_kwargs = {"api_key": self.api_key}
        if self.api_version and getattr(genai_types, "HttpOptions", None) is not None:
            client_kwargs["http_options"] = genai_types.HttpOptions(api_version=self.api_version)

        start_time = time.time()
        with genai.Client(**client_kwargs) as client:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=generation_config,
            )

        elapsed = time.time() - start_time
        self.logger.info("Gemini generate_content completed in %.2fs using %s", elapsed, model_name)

        text = self._response_to_text(response)
        if not text:
            raise RuntimeError(f"Gemini returned an empty response for model '{model_name}'")
        return text

    def _documentation_prompt(self, context: str, repo_name: str) -> str:
        return (
            f"Repository: {repo_name}\n\n"
            "Write a grounded architecture handbook in GitHub-flavored Markdown using only the provided repository context. "
            "Do not invent files, services, or runtime behavior. If something is unclear, call it out as an assumption.\n\n"
            "Required sections:\n"
            "1. Executive Summary\n"
            "2. Product or Package Purpose\n"
            "3. Primary Components\n"
            "4. Runtime or Execution Flow\n"
            "5. Data and State Management\n"
            "6. External Integrations and Dependencies\n"
            "7. Security and Operational Considerations\n"
            "8. Deployment or Usage Notes\n"
            "9. Follow-up Checks and Recommended Improvements\n\n"
            "Repository context:\n"
            f"{self._clip_context(context)}"
        )

    def _graph_prompt(self, context: str, repo_name: str, graph_kind: str) -> str:
        if graph_kind == "hld":
            instructions = (
                "Create a high-level Mermaid flowchart that shows the main user or caller, the actual entry points, major modules, "
                "data stores, and external integrations that appear in the repository context. If the repository is a library or CLI tool, "
                "show that shape instead of inventing a web application."
            )
        elif graph_kind == "flow":
            instructions = (
                "Create a Mermaid flowchart that focuses on the repository's main functional flow. Use actual files, modules, and outputs from the "
                "provided context. For web apps, show request-to-response. For libraries or CLI tools, show input-to-output."
            )
        else:
            instructions = (
                "Create a low-level Mermaid sequenceDiagram or flowchart showing the most concrete execution path supported by the repository context. "
                "Use actual files and functions when visible. If an HTTP request path is not evident, show the module call flow instead."
            )

        return (
            f"Repository: {repo_name}\n\n"
            f"{instructions} Return a JSON object only that matches the provided schema. "
            "The mermaid_code value must be valid Mermaid and must not be wrapped in code fences.\n\n"
            "Repository context:\n"
            f"{self._clip_context(context)}"
        )

    def _chat_summary_prompt(self, context: str, repo_name: str) -> str:
        return (
            f"Repository: {repo_name}\n\n"
            "Write a concise onboarding summary for an engineer who has never seen this project before. "
            "Keep it to 8-10 sentences, highlight the actual entry points, core workflow, storage, external integrations, and usage or deployment expectations, "
            "and stay strictly grounded in the supplied repository context.\n\n"
            "Repository context:\n"
            f"{self._clip_context(context)}"
        )

    def _chat_answer_prompt(self, context: str, repo_name: str, question: str) -> str:
        return (
            f"Repository: {repo_name}\n"
            f"Question: {question}\n\n"
            "Answer the question using only the supplied repository context. Provide a direct answer first, then a brief reasoning section, "
            "and mention the most relevant file paths when the context supports it. If the context is incomplete, say so explicitly.\n\n"
            "Repository context:\n"
            f"{self._clip_context(context)}"
        )

    @staticmethod
    def _dedupe_preserve_order(items: List[str]) -> List[str]:
        return list(dict.fromkeys([item for item in items if item]))

    @staticmethod
    def _trim_text(text: str, limit: int = 280) -> str:
        cleaned = re.sub(r"\s+", " ", (text or "")).strip()
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: limit - 3].rstrip() + "..."

    @staticmethod
    def _natural_join(items: List[str]) -> str:
        filtered = [item for item in items if item]
        if not filtered:
            return ""
        if len(filtered) == 1:
            return filtered[0]
        if len(filtered) == 2:
            return f"{filtered[0]} and {filtered[1]}"
        return f"{', '.join(filtered[:-1])}, and {filtered[-1]}"

    @staticmethod
    def _has_any_pattern(text: str, patterns: List[str]) -> bool:
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)

    def _parse_context_records(self, context: str) -> List[RetrievedContextFile]:
        records: List[RetrievedContextFile] = []
        for match in self.CONTEXT_BLOCK_PATTERN.finditer(context or ""):
            records.append(
                RetrievedContextFile(
                    file_path=match.group("file_path").strip(),
                    language=match.group("language").strip() or "text",
                    function_name=match.group("function_name").strip(),
                    github_url=match.group("github_url").strip(),
                    content=match.group("content").strip(),
                )
            )
        return records

    def _extract_overview(self, records: List[RetrievedContextFile]) -> Dict[str, str]:
        overview: Dict[str, str] = {}
        for record in records:
            if record.file_path != "__repo_overview__.md":
                continue
            for line in record.content.splitlines():
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                overview[key.strip().lower()] = value.strip()
            break
        return overview

    def _readme_excerpt(self, records: List[RetrievedContextFile]) -> str:
        fallback_excerpt = ""
        for record in records:
            base_name = os.path.basename(record.file_path).lower()
            if not base_name.startswith("readme"):
                continue

            heading_candidates: List[str] = []
            for line in record.content.splitlines():
                stripped = line.strip()
                if not stripped.startswith("#"):
                    continue
                heading = stripped.lstrip("#").strip()
                if not heading:
                    continue
                if any(token in heading.lower() for token in ["setup", "installation", "running", "viewing", "usage"]):
                    continue
                heading_candidates.append(heading)

            paragraphs = re.split(r"\n\s*\n", record.content)
            for paragraph in paragraphs:
                cleaned_lines = []
                for line in paragraph.splitlines():
                    stripped = line.strip()
                    if not stripped:
                        continue
                    if stripped.startswith("```"):
                        continue
                    if stripped.startswith("#") or stripped.startswith("![") or stripped.startswith("[!["):
                        continue
                    cleaned_lines.append(stripped)

                if not cleaned_lines:
                    continue

                excerpt = self._trim_text(" ".join(cleaned_lines), limit=260)
                if not excerpt:
                    continue

                lowered = excerpt.lower()
                setup_like = any(
                    marker in lowered
                    for marker in [
                        "make sure you have",
                        "pip install",
                        "requirements.txt",
                        "clone the repository",
                        "python manage.py",
                        "virtual environment",
                        "venv",
                    ]
                )
                purpose_like = any(
                    re.search(pattern, lowered)
                    for pattern in [
                        r"\bis\b",
                        r"\ballows\b",
                        r"\bhelps\b",
                        r"\bprovides\b",
                        r"\bconverts?\b",
                        r"\bgenerates?\b",
                    ]
                )

                if purpose_like and not setup_like:
                    return excerpt
                if not fallback_excerpt and not setup_like:
                    fallback_excerpt = excerpt

            descriptive_headings = [heading for heading in heading_candidates if " " in heading]
            if descriptive_headings:
                return self._trim_text(descriptive_headings[0], limit=120)
            if len(heading_candidates) > 1:
                return self._trim_text(heading_candidates[1], limit=120)
            if heading_candidates:
                return self._trim_text(heading_candidates[0], limit=120)

        return fallback_excerpt

    @staticmethod
    def _normalize_description(description: str) -> str:
        normalized = (description or "").strip()
        if normalized.lower() in {"", "n/a", "none", "no description available."}:
            return ""
        return normalized

    def _infer_stack(self, records: List[RetrievedContextFile], overview: Dict[str, str]) -> List[str]:
        searchable = "\n".join(
            f"{record.file_path}\n{record.content}" for record in records
        )
        stack: List[str] = []

        primary_language = self._normalize_description(overview.get("primary language", ""))
        if primary_language:
            stack.append(primary_language)

        tech_markers = [
            ("Flask", [r"\bfrom flask\b", r"\bFlask\(", r"\bflask\b"]),
            ("FastAPI", [r"\bfrom fastapi\b", r"\bFastAPI\("]),
            ("Django", [r"\bdjango\b"]),
            ("SQLAlchemy", [r"\bsqlalchemy\b", r"\bSQLAlchemy\b"]),
            ("PostgreSQL", [r"\bpostgres(?:ql)?\b", r"\bpsycopg\b"]),
            ("SQLite", [r"\bsqlite\b"]),
            ("Jinja templates", [r"render_template\(", r"templates/", r"\.html\b"]),
            ("Docker", [r"dockerfile", r"docker-compose"]),
            ("Gunicorn", [r"\bgunicorn\b"]),
            ("Pandas", [r"\bpandas\b"]),
            ("NumPy", [r"\bnumpy\b"]),
            ("Requests", [r"\brequests\b"]),
            ("Click", [r"\bclick\b"]),
            ("LangGraph", [r"\blanggraph\b"]),
            ("Pinecone", [r"\bpinecone\b"]),
        ]

        for label, patterns in tech_markers:
            if self._has_any_pattern(searchable, patterns):
                stack.append(label)

        return self._dedupe_preserve_order(stack)[:7]

    def _infer_repo_type(self, records: List[RetrievedContextFile], stack: List[str]) -> str:
        searchable = "\n".join(
            f"{record.file_path}\n{record.content}" for record in records
        )
        file_paths = [record.file_path for record in records]

        if any(framework in stack for framework in ["Flask", "FastAPI", "Django"]) or any(
            path.startswith("templates/") or path.endswith(".html") for path in file_paths
        ):
            return "web application"

        if self._has_any_pattern(searchable, [r"\bargparse\b", r"\bclick\b", r"__main__", r"def main\("]):
            return "CLI tool"

        if any(
            os.path.basename(path) in {"pyproject.toml", "setup.py"} or path.endswith("/__init__.py")
            for path in file_paths
        ):
            return "library/package"

        return "software project"

    def _find_entry_points(self, records: List[RetrievedContextFile]) -> List[str]:
        entry_points: List[str] = []
        preferred_names = {
            "app.py",
            "main.py",
            "server.py",
            "run.py",
            "manage.py",
            "wsgi.py",
            "asgi.py",
            "__main__.py",
            "index.js",
        }

        for record in records:
            base_name = os.path.basename(record.file_path).lower()
            content = record.content
            if base_name in preferred_names:
                entry_points.append(record.file_path)
                continue
            if self._has_any_pattern(content, [r"\bFlask\(", r"@app\.route", r"@bp\.route", r"def main\(", r"__main__"]):
                entry_points.append(record.file_path)

        if not entry_points:
            for record in records:
                if record.file_path == "__repo_overview__.md":
                    continue
                if record.file_path.startswith("tests/"):
                    continue
                if record.file_path.endswith((".py", ".js", ".ts")):
                    entry_points.append(record.file_path)
                    break

        return self._dedupe_preserve_order(entry_points)[:3]

    def _score_component(self, record: RetrievedContextFile) -> int:
        file_path = record.file_path.lower()
        base_name = os.path.basename(file_path)
        content = record.content
        score = 0

        if file_path == "__repo_overview__.md":
            return -1
        if base_name in {"app.py", "main.py", "server.py", "run.py", "manage.py", "wsgi.py", "asgi.py"}:
            score += 140
        if file_path.endswith(".py"):
            score += 45
        if any(token in file_path for token in ["route", "view", "controller", "service", "model", "config", "auth", "util", "helper", "form"]):
            score += 90
        if self._has_any_pattern(content, [r"\bFlask\(", r"@app\.route", r"@bp\.route", r"\bFastAPI\(", r"def main\("]):
            score += 110
        if file_path.startswith("templates/") or file_path.endswith(".html"):
            score += 70
        if file_path.endswith(("requirements.txt", "pyproject.toml", "dockerfile")) or "docker-compose" in file_path:
            score += 50
        if file_path.startswith("tests/"):
            score -= 20
        if file_path.count("/") == 0:
            score += 15

        return score

    def _infer_component_role(self, record: RetrievedContextFile) -> str:
        file_path = record.file_path.lower()
        content = record.content
        base_name = os.path.basename(file_path)

        if self._has_any_pattern(content, [r"\bFlask\(", r"@app\.route", r"@bp\.route", r"render_template\("]):
            return "HTTP entry point and route handling"
        if self._has_any_pattern(content, [r"\bFastAPI\(", r"@app\.(get|post|put|delete)"]):
            return "API entry point and route handling"
        if "auth" in file_path:
            return "authentication or access-control logic"
        if any(token in file_path for token in ["model", "schema"]):
            return "data model definitions"
        if any(token in file_path for token in ["service", "logic"]):
            return "core application logic"
        if any(token in file_path for token in ["config", "settings"]):
            return "configuration and runtime settings"
        if file_path.startswith("templates/") or file_path.endswith(".html"):
            return "server-rendered UI template"
        if file_path.endswith(".js"):
            return "browser-side behavior"
        if file_path.endswith(".css"):
            return "styling and presentation"
        if file_path.startswith("tests/") or base_name.startswith("test_"):
            return "test coverage"
        if base_name.startswith("readme"):
            return "project overview and setup notes"
        if base_name in {"requirements.txt", "pyproject.toml", "setup.py"}:
            return "dependency and packaging metadata"
        if self._has_any_pattern(content, [r"def main\(", r"__main__"]):
            return "command entry point"
        return "supporting application module"

    def _select_components(self, records: List[RetrievedContextFile]) -> List[Dict[str, str]]:
        ranked = sorted(records, key=self._score_component, reverse=True)
        components: List[Dict[str, str]] = []
        seen_paths: Set[str] = set()

        for record in ranked:
            if record.file_path in seen_paths:
                continue
            if record.file_path == "__repo_overview__.md":
                continue

            components.append(
                {
                    "path": record.file_path,
                    "role": self._infer_component_role(record),
                }
            )
            seen_paths.add(record.file_path)

            if len(components) == 6:
                break

        return components

    def _infer_data_stores(self, records: List[RetrievedContextFile]) -> List[str]:
        searchable = "\n".join(
            f"{record.file_path}\n{record.content}" for record in records
        )
        file_paths = [record.file_path.lower() for record in records]
        stores: List[str] = []

        if self._has_any_pattern(searchable, [r"\bpostgres(?:ql)?\b", r"\bpsycopg\b"]):
            stores.append("PostgreSQL")
        if self._has_any_pattern(searchable, [r"\bsqlite\b"]):
            stores.append("SQLite")
        if self._has_any_pattern(searchable, [r"\bsqlalchemy\b"]):
            stores.append("SQLAlchemy-managed relational data")
        if self._has_any_pattern(searchable, [r"\bjson\.load\b", r"\bjson\.dump\b"]) or any(path.endswith(".json") for path in file_paths):
            stores.append("JSON files")
        if any(path.endswith(".csv") for path in file_paths):
            stores.append("CSV files")

        return self._dedupe_preserve_order(stores)

    def _infer_integrations(self, records: List[RetrievedContextFile]) -> List[str]:
        searchable = "\n".join(
            f"{record.file_path}\n{record.content}" for record in records
        )
        integrations: List[str] = []
        integration_markers = [
            ("GitHub", [r"api\.github\.com", r"github\.com/"]),
            ("Google OAuth", [r"accounts\.google\.com", r"\boauth\b"]),
            ("SMTP/email", [r"\bsmtplib\b", r"\bemail\.message\b"]),
            ("OpenAI", [r"\bopenai\b"]),
        ]

        for label, patterns in integration_markers:
            if self._has_any_pattern(searchable, patterns):
                integrations.append(label)

        return self._dedupe_preserve_order(integrations)

    def _infer_deployment_clues(self, records: List[RetrievedContextFile]) -> List[str]:
        clues: List[str] = []
        file_paths = [record.file_path for record in records]
        basenames = {os.path.basename(path) for path in file_paths}
        searchable = "\n".join(
            f"{record.file_path}\n{record.content}" for record in records
        )

        if "Dockerfile" in basenames or any("docker-compose" in path for path in file_paths):
            clues.append("Docker artifacts")
        if any(base in basenames for base in ["requirements.txt", "pyproject.toml", "setup.py"]):
            clues.append("Python packaging metadata")
        if self._has_any_pattern(searchable, [r"\bgunicorn\b"]):
            clues.append("Gunicorn runtime references")
        if any(os.path.basename(path) in {"Procfile", "render.yaml"} for path in file_paths):
            clues.append("deployment manifest files")

        return self._dedupe_preserve_order(clues)

    def _build_flow_steps(self, profile: Dict[str, object]) -> List[str]:
        entry_points = profile.get("entry_points", [])
        components = profile.get("components", [])
        data_stores = profile.get("data_stores", [])
        repo_type = profile.get("repo_type", "software project")

        entry_label = entry_points[0] if entry_points else "the retrieved entry point"
        core_components = [
            component["path"]
            for component in components
            if component["path"] not in entry_points
            and all(
                token not in component["role"].lower()
                for token in ["template", "browser-side", "styling", "test coverage", "dependency", "overview"]
            )
        ]
        presentation_component = next(
            (
                component["path"]
                for component in components
                if any(token in component["role"].lower() for token in ["template", "browser-side", "styling"])
            ),
            "",
        )

        if repo_type == "web application":
            steps = [f"A browser or client reaches {entry_label}."]
            if core_components:
                steps.append(
                    f"The request is handed to {self._natural_join(core_components[:2])} for the main application logic."
                )
            else:
                steps.append("Most of the visible logic appears to live directly in the entry layer.")
            if data_stores:
                steps.append(f"State is read or written through {self._natural_join(data_stores[:2])} when needed.")
            if presentation_component:
                steps.append(f"The result is rendered through {presentation_component} before it is returned.")
            else:
                steps.append("The result is returned directly to the caller as the response.")
            return steps

        if repo_type == "CLI tool":
            steps = [f"The caller invokes {entry_label}."]
            if core_components:
                steps.append(
                    f"The command path delegates the main work to {self._natural_join(core_components[:2])}."
                )
            if data_stores:
                steps.append(f"Persistent state, if any, is handled through {self._natural_join(data_stores[:2])}.")
            steps.append("The command returns output to stdout or to the invoking environment.")
            return steps

        steps = [f"The main execution appears to start from {entry_label}."]
        if core_components:
            steps.append(
                f"Core behavior is organized around {self._natural_join(core_components[:2])}."
            )
        if data_stores:
            steps.append(f"Observed state management involves {self._natural_join(data_stores[:2])}.")
        steps.append("The retrieved files suggest a lightweight input-to-output flow rather than a multi-stage worker pipeline.")
        return steps

    def _build_repository_profile(self, context: str, repo_name: str) -> Dict[str, object]:
        records = self._parse_context_records(context)
        overview = self._extract_overview(records)
        description = self._normalize_description(overview.get("description", ""))
        if not description:
            description = self._readme_excerpt(records)

        stack = self._infer_stack(records, overview)
        repo_type = self._infer_repo_type(records, stack)
        entry_points = self._find_entry_points(records)
        components = self._select_components(records)
        data_stores = self._infer_data_stores(records)
        integrations = self._infer_integrations(records)
        deployment_clues = self._infer_deployment_clues(records)
        searchable = "\n".join(
            f"{record.file_path}\n{record.content}" for record in records
        )

        purpose = description or f"The retrieved files suggest that {repo_name} is a {repo_type}."
        advanced_pipeline_present = self._has_any_pattern(
            searchable,
            [
                r"\blanggraph\b",
                r"\bcelery\b",
                r"\brq\b",
                r"\bdramatiq\b",
                r"\bpinecone\b",
                r"\bchroma(?:db)?\b",
                r"\bvector\s*store\b",
            ],
        )
        tests_present = any(
            record.file_path.startswith("tests/") or os.path.basename(record.file_path).startswith("test_")
            for record in records
        )

        return {
            "repo_name": repo_name,
            "records": records,
            "files": self._dedupe_preserve_order([record.file_path for record in records]),
            "overview": overview,
            "purpose": purpose,
            "stack": stack,
            "repo_type": repo_type,
            "entry_points": entry_points,
            "components": components,
            "data_stores": data_stores,
            "integrations": integrations,
            "deployment_clues": deployment_clues,
            "tests_present": tests_present,
            "advanced_pipeline_present": advanced_pipeline_present,
            "flow_steps": self._build_flow_steps(
                {
                    "repo_type": repo_type,
                    "entry_points": entry_points,
                    "components": components,
                    "data_stores": data_stores,
                }
            ),
        }

    @staticmethod
    def _question_tokens(question: str) -> List[str]:
        stop_words = {
            "the",
            "and",
            "for",
            "that",
            "this",
            "with",
            "from",
            "what",
            "which",
            "does",
            "into",
            "about",
            "main",
            "repo",
            "repository",
            "there",
            "their",
            "your",
            "have",
            "use",
            "uses",
            "point",
        }
        return [
            token
            for token in re.split(r"\W+", question.lower())
            if len(token) > 2 and token not in stop_words
        ]

    def _select_relevant_files_for_question(
        self,
        records: List[RetrievedContextFile],
        question: str,
        profile: Dict[str, object],
    ) -> List[str]:
        tokens = self._question_tokens(question)
        lower_question = question.lower()
        ranked: List[Tuple[int, str]] = []

        for record in records:
            searchable = f"{record.file_path}\n{record.content}".lower()
            score = sum(1 for token in tokens if token in searchable)
            if score:
                ranked.append((score, record.file_path))

        ranked.sort(key=lambda item: item[0], reverse=True)
        matched_files = self._dedupe_preserve_order([file_path for _, file_path in ranked])
        fallback_files = list(profile.get("entry_points", []))
        if any(token in lower_question for token in ["framework", "dependency", "dependencies", "stack", "technology"]):
            fallback_files.extend(
                record.file_path
                for record in records
                if os.path.basename(record.file_path).lower() in {"requirements.txt", "pyproject.toml", "setup.py", "readme.md"}
            )
        fallback_files.extend(component["path"] for component in profile.get("components", [])[:3])
        selected_files = self._dedupe_preserve_order(fallback_files + matched_files)
        return selected_files[:4]

    def _build_local_chat_answer(self, profile: Dict[str, object], question: str) -> str:
        lower_question = question.lower()
        entry_points = profile.get("entry_points", [])
        stack = profile.get("stack", [])
        data_stores = profile.get("data_stores", [])
        components = profile.get("components", [])
        records = profile.get("records", [])

        direct_points: List[str] = []
        if any(token in lower_question for token in ["entry point", "entrypoint", "start", "run", "boot", "main"]):
            if entry_points:
                direct_points.append(f"The main retrieved entry point is {self._natural_join(entry_points[:2])}.")

        if any(token in lower_question for token in ["framework", "stack", "technology", "library", "dependency", "dependencies"]):
            if stack:
                direct_points.append(f"The visible framework and dependency stack includes {self._natural_join(stack[:5])}.")

        if any(token in lower_question for token in ["database", "storage", "state", "persistence", "persist"]):
            if data_stores:
                direct_points.append(f"State management appears to rely on {self._natural_join(data_stores[:3])}.")
            else:
                direct_points.append("I do not see an explicit database or durable storage layer in the retrieved context.")

        if any(token in lower_question for token in ["component", "module", "file", "structure"]):
            if components:
                direct_points.append(
                    f"The main visible modules are {self._natural_join([component['path'] for component in components[:4]])}."
                )

        if not direct_points:
            direct_points.append(self._trim_text(self._build_local_summary(profile), limit=320))

        reasoning_points: List[str] = []
        if entry_points:
            reasoning_points.append(f"Entry points visible in the retrieved context: {self._natural_join(entry_points[:3])}.")
        if stack:
            reasoning_points.append(f"Framework and dependency markers found: {self._natural_join(stack[:5])}.")
        if data_stores:
            reasoning_points.append(f"Observed state or persistence markers: {self._natural_join(data_stores[:3])}.")
        if not reasoning_points:
            reasoning_points.append("The answer is based only on the retrieved repository slice available in the current index.")

        relevant_files = self._select_relevant_files_for_question(records, question, profile)

        lines = [f"Direct answer: {' '.join(self._dedupe_preserve_order(direct_points))}", "", "Reasoning:"]
        lines.extend(f"- {point}" for point in reasoning_points)

        if relevant_files:
            lines.append("")
            lines.append("Relevant files:")
            lines.extend(f"- {file_path}" for file_path in relevant_files)

        return "\n".join(lines)

    def _build_local_summary(self, profile: Dict[str, object]) -> str:
        repo_name = profile["repo_name"]
        entry_points = profile.get("entry_points", [])
        stack = profile.get("stack", [])
        components = profile.get("components", [])
        data_stores = profile.get("data_stores", [])
        deployment_clues = profile.get("deployment_clues", [])

        purpose_text = (profile.get("purpose") or "").strip().rstrip(".")
        lowered_purpose = purpose_text.lower()
        if not purpose_text:
            first_sentence = f"{repo_name} appears to be a software project."
        elif lowered_purpose.startswith("the retrieved files suggest that") or lowered_purpose.startswith(repo_name.lower()):
            first_sentence = f"{purpose_text}."
        elif re.search(r"\b(is|are|allows|helps|provides|converts?|generates?)\b", lowered_purpose):
            first_sentence = f"{repo_name} appears to be {purpose_text}."
        else:
            article = "" if lowered_purpose.startswith(("a ", "an ", "the ")) else "a "
            first_sentence = f"{repo_name} appears to be {article}{lowered_purpose}."

        sentences = [self._trim_text(first_sentence, limit=220)]

        if entry_points:
            sentences.append(
                f"The main retrieved entry point is {self._natural_join(entry_points[:2])}."
            )

        if stack:
            sentences.append(f"The visible stack includes {self._natural_join(stack[:5])}.")

        if components:
            visible_components = [
                component
                for component in components
                if all(
                    token not in component["role"].lower()
                    for token in ["dependency", "overview"]
                )
            ]
            visible_components = visible_components or components
            component_bits = [
                f"{component['path']} ({component['role'].lower()})"
                for component in visible_components[:3]
            ]
            sentences.append(f"Key files in the retrieved slice are {self._natural_join(component_bits)}.")

        if data_stores:
            sentences.append(
                f"State management appears to rely on {self._natural_join(data_stores)}."
            )
        elif profile.get("advanced_pipeline_present"):
            sentences.append(
                "I do not see an explicit relational database in the retrieved files, but there are references to orchestration or vector-style components in the stack."
            )
        else:
            sentences.append(
                "I do not see an explicit database, background queue, or advanced retrieval/orchestration layer in the retrieved files."
            )

        if deployment_clues:
            sentences.append(
                f"Runtime or deployment clues come from {self._natural_join(deployment_clues)}."
            )

        if profile.get("tests_present"):
            sentences.append(
                "Tests are present in the retrieved files, which helps validate the visible flow."
            )
        else:
            sentences.append(
                "Tests were not visible in the retrieved slice, so some behavior may sit outside the current context."
            )

        sentences.append(
            "This onboarding summary is based only on the indexed repository context retrieved for this analysis."
        )
        return " ".join(sentences)

    @staticmethod
    def _mermaid_node_id(label: str, index: int) -> str:
        words = re.sub(r"[^A-Za-z0-9]+", " ", label).strip().split()
        if not words:
            return f"node{index}"

        node_id = words[0].lower() + "".join(word.title() for word in words[1:4])
        node_id = re.sub(r"[^A-Za-z0-9]", "", node_id)
        if not node_id:
            return f"node{index}"
        if not node_id[0].isalpha():
            return f"node{node_id}"
        return node_id

    def _mermaid_label(self, label: str, limit: int = 40) -> str:
        cleaned = re.sub(r"\s+", " ", label).replace("[", "(").replace("]", ")").strip()
        return self._trim_text(cleaned, limit=limit)

    def _graph_payload(self, title: str, description: str, mermaid_code: str) -> str:
        return json.dumps(
            {
                "title": title,
                "description": description,
                "mermaid_code": mermaid_code,
            }
        )

    def _build_local_hld(self, profile: Dict[str, object]) -> str:
        components = profile.get("components", [])
        entry_points = profile.get("entry_points", [])
        data_stores = profile.get("data_stores", [])
        integrations = profile.get("integrations", [])
        repo_type = profile.get("repo_type", "software project")

        definitions: List[str] = []
        edges: List[str] = []
        node_ids: Dict[str, str] = {}

        def ensure_node(key: str, label: str) -> str:
            if key in node_ids:
                return node_ids[key]
            node_id = self._mermaid_node_id(label, len(node_ids) + 1)
            while node_id in node_ids.values():
                node_id = f"{node_id}{len(node_ids) + 1}"
            node_ids[key] = node_id
            definitions.append(f"    {node_id}[{self._mermaid_label(label)}]")
            return node_id

        caller_label = "User / Browser" if repo_type == "web application" else "Caller / Script"
        caller_node = ensure_node("caller", caller_label)
        entry_label = entry_points[0] if entry_points else "Entry Layer"
        entry_node = ensure_node("entry", f"Entry: {entry_label}")
        edges.append(f"    {caller_node} --> {entry_node}")

        previous_node = entry_node
        core_components = [
            component
            for component in components
            if component["path"] not in entry_points
            and all(
                token not in component["role"].lower()
                for token in ["template", "browser-side", "styling", "test coverage", "dependency", "overview"]
            )
        ]
        for component in core_components[:2]:
            component_node = ensure_node(component["path"], f"{component['path']}: {component['role']}")
            edges.append(f"    {previous_node} --> {component_node}")
            previous_node = component_node

        presentation_component = next(
            (
                component
                for component in components
                if any(token in component["role"].lower() for token in ["template", "browser-side", "styling"])
            ),
            None,
        )
        if presentation_component:
            presentation_node = ensure_node(
                presentation_component["path"],
                f"{presentation_component['path']}: {presentation_component['role']}",
            )
            edges.append(f"    {previous_node} --> {presentation_node}")
            previous_node = presentation_node

        output_node = ensure_node("output", "Output / Result")
        edges.append(f"    {previous_node} --> {output_node}")

        anchor_node = previous_node if previous_node != entry_node else entry_node
        for store in data_stores[:2]:
            store_node = ensure_node(store, f"State: {store}")
            edges.append(f"    {anchor_node} -.-> {store_node}")

        for integration in integrations[:2]:
            integration_node = ensure_node(integration, f"External: {integration}")
            edges.append(f"    {entry_node} -.-> {integration_node}")

        mermaid_code = "\n".join(["flowchart TD", *definitions, *edges])
        return self._graph_payload(
            title="High-Level Architecture",
            description="Main modules and interactions inferred from the retrieved repository files.",
            mermaid_code=mermaid_code,
        )

    def _build_local_lld(self, profile: Dict[str, object]) -> str:
        components = profile.get("components", [])
        entry_points = profile.get("entry_points", [])
        data_stores = profile.get("data_stores", [])
        repo_type = profile.get("repo_type", "software project")

        caller_label = "Browser/User" if repo_type == "web application" else "Caller"
        entry_label = entry_points[0] if entry_points else "entry module"
        core_components = [
            component["path"]
            for component in components
            if component["path"] not in entry_points
            and all(
                token not in component["role"].lower()
                for token in ["template", "browser-side", "styling", "test coverage", "dependency", "overview"]
            )
        ]
        view_component = next(
            (
                component["path"]
                for component in components
                if any(token in component["role"].lower() for token in ["template", "browser-side", "styling"])
            ),
            "",
        )

        lines = [
            "sequenceDiagram",
            f"    participant Caller as {self._mermaid_label(caller_label, 24)}",
            f"    participant Entry as {self._mermaid_label(entry_label, 28)}",
        ]

        if core_components:
            lines.append(f"    participant Core as {self._mermaid_label(core_components[0], 28)}")
        if data_stores:
            lines.append(f"    participant Store as {self._mermaid_label(data_stores[0], 24)}")
        if view_component:
            lines.append(f"    participant View as {self._mermaid_label(view_component, 26)}")

        lines.append("    Caller->>Entry: start flow")
        if core_components:
            lines.append("    Entry->>Core: invoke main logic")
            if data_stores:
                lines.append("    Core->>Store: read or write state")
            lines.append("    Core-->>Entry: return result")
        elif data_stores:
            lines.append("    Entry->>Store: read or write state")
            lines.append("    Store-->>Entry: return state")

        if view_component:
            lines.append("    Entry->>View: render output")
            lines.append("    View-->>Caller: response")
        else:
            lines.append("    Entry-->>Caller: output")

        return self._graph_payload(
            title="Low-Level Flow",
            description="Concrete execution path inferred from the retrieved repository files.",
            mermaid_code="\n".join(lines),
        )

    def _build_local_flow(self, profile: Dict[str, object]) -> str:
        components = profile.get("components", [])
        entry_points = profile.get("entry_points", [])
        data_stores = profile.get("data_stores", [])
        repo_type = profile.get("repo_type", "software project")

        definitions: List[str] = []
        edges: List[str] = []
        node_ids: Dict[str, str] = {}

        def ensure_node(key: str, label: str) -> str:
            if key in node_ids:
                return node_ids[key]
            node_id = self._mermaid_node_id(label, len(node_ids) + 1)
            while node_id in node_ids.values():
                node_id = f"{node_id}{len(node_ids) + 1}"
            node_ids[key] = node_id
            definitions.append(f"    {node_id}[{self._mermaid_label(label)}]")
            return node_id

        input_label = "Browser Request" if repo_type == "web application" else "Input / Invocation"
        current_node = ensure_node("input", input_label)
        entry_label = entry_points[0] if entry_points else "Entry Layer"
        entry_node = ensure_node("entry", entry_label)
        edges.append(f"    {current_node} --> {entry_node}")
        current_node = entry_node

        selected_components = [
            component
            for component in components
            if component["path"] not in entry_points
            and all(
                token not in component["role"].lower()
                for token in ["test coverage", "dependency", "overview"]
            )
        ]

        for component in selected_components[:3]:
            component_node = ensure_node(component["path"], component["path"])
            edges.append(f"    {current_node} --> {component_node}")
            current_node = component_node

        output_node = ensure_node("output", "Rendered output / returned result")
        edges.append(f"    {current_node} --> {output_node}")

        if data_stores:
            store_node = ensure_node("flowStore", f"State: {data_stores[0]}")
            edges.append(f"    {entry_node} -.-> {store_node}")

        mermaid_code = "\n".join(["flowchart LR", *definitions, *edges])
        return self._graph_payload(
            title="Main Functional Flow",
            description="Primary input-to-output path inferred from the retrieved repository files.",
            mermaid_code=mermaid_code,
        )

    def _build_local_documentation(self, profile: Dict[str, object]) -> str:
        stack = profile.get("stack", [])
        entry_points = profile.get("entry_points", [])
        components = profile.get("components", [])
        data_stores = profile.get("data_stores", [])
        integrations = profile.get("integrations", [])
        deployment_clues = profile.get("deployment_clues", [])
        flow_steps = profile.get("flow_steps", [])

        stack_text = self._natural_join(stack) or "No framework or language markers were obvious in the retrieved files"
        entry_text = self._natural_join(entry_points) or "No clear entry point was retrieved"
        summary = self._build_local_summary(profile)

        component_rows = "\n".join(
            f"| {component['path']} | {component['role']} |"
            for component in components
        ) or "| - | No components were retrieved |"

        flow_lines = "\n".join(
            f"{index}. {step}" for index, step in enumerate(flow_steps, start=1)
        ) or "1. The retrieved files did not expose a clear runtime flow."

        data_lines = "\n".join(f"- {item}" for item in data_stores) or "- No explicit persistent store was visible in the retrieved files."

        integration_lines = []
        if stack:
            integration_lines.append(f"- Visible frameworks and dependencies: {stack_text}.")
        if integrations:
            integration_lines.extend(f"- External integration markers: {item}." for item in integrations)
        if not integration_lines:
            integration_lines.append("- No strong evidence of external service integrations was retrieved.")

        deployment_lines = "\n".join(
            f"- {item}" for item in deployment_clues
        ) or "- No deployment-specific files were visible in the retrieved slice."
        integration_section = "\n".join(integration_lines)

        follow_up_lines = [
            "- This fallback uses retrieved repository excerpts rather than a full clone, so deeper modules may sit outside the current context.",
            "- Validate actual entry points, startup commands, and deployment steps against the full repository before making production decisions.",
        ]
        if not profile.get("tests_present"):
            follow_up_lines.append("- Retrieve or inspect the test suite before assuming key flows are covered by automated checks.")
        if not profile.get("advanced_pipeline_present"):
            follow_up_lines.append("- The retrieved files do not show a separate worker or advanced retrieval/orchestration layer; treat any earlier claim of that architecture as incorrect for this repository slice.")
        follow_up_section = "\n".join(follow_up_lines)

        return (
            f"# {profile['repo_name']} Architecture Handbook\n\n"
            "## Executive Summary\n"
            f"{summary}\n\n"
            "## Product or Package Purpose\n"
            f"{profile['purpose']}\n\n"
            f"- Repository type: {profile['repo_type'].capitalize()}\n"
            f"- Likely entry points: {entry_text}\n"
            f"- Visible stack: {stack_text}\n\n"
            "## Primary Components\n"
            "| File | Observed responsibility |\n"
            "| --- | --- |\n"
            f"{component_rows}\n\n"
            "## Runtime or Execution Flow\n"
            f"{flow_lines}\n\n"
            "## Data and State Management\n"
            f"{data_lines}\n\n"
            "## External Integrations and Dependencies\n"
            f"{integration_section}\n\n"
            "## Deployment or Usage Notes\n"
            f"{deployment_lines}\n\n"
            "## Risks, Gaps, and Follow-up Checks\n"
            f"{follow_up_section}\n"
        )

    def _generate_documentation_with_gemini(self, context: str, repo_name: str) -> str:
        return self._generate_with_gemini(
            prompt=self._documentation_prompt(context, repo_name),
            model_name=self.model_name,
            system_instruction=(
                "You are a senior software architect producing production-ready technical documentation. "
                "Stay grounded in the provided repository context."
            ),
        )

    def _generate_graph_with_gemini(self, context: str, repo_name: str, graph_kind: str) -> str:
        return self._generate_with_gemini(
            prompt=self._graph_prompt(context, repo_name, graph_kind),
            model_name=self.model_name,
            response_mime_type="application/json",
            response_json_schema=self.GRAPH_RESPONSE_SCHEMA,
            system_instruction=(
                "You are generating Mermaid architecture diagrams for a software repository. "
                "Return valid Mermaid syntax and stay grounded in the provided context."
            ),
        )

    def _generate_chat_summary_with_gemini(self, context: str, repo_name: str) -> str:
        return self._generate_with_gemini(
            prompt=self._chat_summary_prompt(context, repo_name),
            model_name=self.chat_model_name,
            system_instruction=(
                "You are summarizing a software repository for engineering onboarding. "
                "Be concise, concrete, and grounded in the supplied context."
            ),
        )

    def _generate_chat_answer_with_gemini(self, context: str, repo_name: str, question: str) -> str:
        return self._generate_with_gemini(
            prompt=self._chat_answer_prompt(context, repo_name, question),
            model_name=self.chat_model_name,
            system_instruction=(
                "You are an architecture assistant answering questions about a repository. "
                "Stay grounded in the provided retrieval context and never invent missing details."
            ),
        )

    def _extract_file_headers(self, context: str) -> List[str]:
        records = self._parse_context_records(context)
        if records:
            return [record.file_path for record in records]
        return re.findall(r"--- File: (.+?) ---", context)

    def generate_chat_summary(self, context: str, repo_name: str) -> str:
        profile = self._build_repository_profile(context, repo_name)
        return self._build_local_summary(profile)

    def generate_chat_answer(self, context: str, repo_name: str, question: str) -> str:
        if self._can_use_gemini():
            try:
                return self._generate_chat_answer_with_gemini(context, repo_name, question)
            except Exception as exc:
                self.logger.warning("Gemini Q&A failed, falling back to local answer synthesis: %s", exc)

        return self.generate_chat_response(context, repo_name, question)

    def generate_chat_response(self, context: str, repo_name: str, question: str) -> str:
        if not context.strip():
            return f"No indexed context found for '{repo_name}'. Re-run analysis to build the repository index."
        profile = self._build_repository_profile(context, repo_name)
        return self._build_local_chat_answer(profile, question)

    def generate_documentation(self, context: str, repo_name: str) -> str:
        profile = self._build_repository_profile(context, repo_name)
        return self._build_local_documentation(profile)

    def generate_all_documentation(self, context: str, repo_name: str) -> Dict[str, str]:
        if self._can_use_gemini():
            try:
                return {
                    "documentation": self._generate_documentation_with_gemini(context, repo_name),
                    "hld": self._generate_graph_with_gemini(context, repo_name, "hld"),
                    "lld": self._generate_graph_with_gemini(context, repo_name, "lld"),
                    "flow": self._generate_graph_with_gemini(context, repo_name, "flow"),
                    "chat_summary": self._generate_chat_summary_with_gemini(context, repo_name),
                }
            except Exception as exc:
                self.logger.warning("Gemini generation failed, falling back to local documentation: %s", exc)

        profile = self._build_repository_profile(context, repo_name)
        documentation = self._build_local_documentation(profile)
        hld = self._build_local_hld(profile)
        lld = self._build_local_lld(profile)
        flow = self._build_local_flow(profile)
        chat_summary = self._build_local_summary(profile)

        return {
            "documentation": documentation,
            "hld": hld,
            "lld": lld,
            "flow": flow,
            "chat_summary": chat_summary,
        }
