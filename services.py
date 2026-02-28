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
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple, TypedDict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import git

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


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""


@dataclass
class ChunkRecord:
    """Represents a code chunk and its metadata."""

    chunk_id: str
    text: str
    metadata: Dict[str, object]


class RepositoryService:
    """Repository management service (singleton)."""

    _instance: Optional["RepositoryService"] = None
    _initialized: bool = False

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
            git.Repo.clone_from(repo_url, local_path)
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

    def _http_get_json(self, url: str) -> Optional[dict]:
        request = Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "ArchiMind/1.0",
            },
        )
        try:
            with urlopen(request, timeout=25) as response:
                payload = response.read().decode("utf-8", errors="ignore")
                return json.loads(payload)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            return None

    def _http_get_text(self, url: str, max_bytes: int = 350_000) -> Optional[str]:
        request = Request(url, headers={"User-Agent": "ArchiMind/1.0"})
        try:
            with urlopen(request, timeout=25) as response:
                payload = response.read(max_bytes)
                return payload.decode("utf-8", errors="ignore")
        except (HTTPError, URLError, TimeoutError):
            return None

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
            if size > 350_000:
                continue
            ranked = dict(entry)
            ranked["priority"] = self._score_path_priority(path)
            candidates.append(ranked)

        if len(candidates) <= 140:
            return candidates

        candidates.sort(key=lambda item: (item.get("priority", 0), -(item.get("size") or 0)), reverse=True)
        return candidates[:220]

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

        for entry in selected:
            file_path = entry.get("path")
            if not file_path:
                continue
            file_text = self._http_get_text(f"{raw_base}/{file_path}")
            if file_text and file_text.strip():
                files[file_path] = file_text

        overview = (
            f"Repository: {owner}/{repository}\n"
            f"Description: {repo_meta.get('description') or 'N/A'}\n"
            f"Primary language: {repo_meta.get('language') or 'N/A'}\n"
            f"Stars: {repo_meta.get('stargazers_count', 0)}\n"
            f"Open issues: {repo_meta.get('open_issues_count', 0)}\n"
            f"Default branch: {default_branch}\n"
            f"Topics: {', '.join(repo_meta.get('topics') or [])}\n"
            f"Ingestion strategy: selective remote fetch ({len(files)} files out of {len(entries)} tree entries).\n"
        )
        files["__repo_overview__.md"] = overview
        return files

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


class VectorStoreService:
    """Hierarchical code index with AST chunking and metadata-rich Chroma storage."""

    _instances: Dict[str, "VectorStoreService"] = {}

    def __new__(cls, db_path: str, collection_name: str, embedding_model: str, repo_url: str = ""):
        key = f"{db_path}:{collection_name}"
        if key not in cls._instances:
            cls._instances[key] = super().__new__(cls)
        return cls._instances[key]

    def __init__(self, db_path: str, collection_name: str, embedding_model: str, repo_url: str = ""):
        if hasattr(self, "_initialized"):
            return

        self.db_path = db_path
        self.collection_name = self._sanitize_collection_name(collection_name)
        self.embedding_model = embedding_model
        self.repo_url = repo_url.rstrip("/")
        self.logger = logging.getLogger(self.__class__.__name__)
        self._initialize_database()
        self._initialized = True

    def _initialize_database(self) -> None:
        try:
            if chromadb is not None:
                self.chroma_client = chromadb.PersistentClient(path=self.db_path)
                self.summary_collection = self.chroma_client.get_or_create_collection(
                    name=f"{self.collection_name}_summaries"
                )
                self.chunk_collection = self.chroma_client.get_or_create_collection(
                    name=f"{self.collection_name}_chunks"
                )
                backend = "ChromaDB"
            else:
                self.summary_collection = _SimpleCollection(self.db_path, f"{self.collection_name}_summaries")
                self.chunk_collection = _SimpleCollection(self.db_path, f"{self.collection_name}_chunks")
                backend = "SimpleJSON"

            self.collection = self.chunk_collection
            self.logger.info(
                "Vector index initialized: %s (backend=%s, chunker=LlamaIndex-CodeSplitter)",
                self.collection_name,
                backend,
            )
        except Exception as exc:
            self.logger.error("Failed to initialize vector store: %s", exc)
            raise ConfigurationError(f"Vector store initialization failed: {exc}")

    @staticmethod
    def _sanitize_collection_name(name: str) -> str:
        return name.replace("-", "_").replace(".", "_").replace("/", "_")

    def is_empty(self) -> bool:
        return self.chunk_collection.count() == 0

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

            self.summary_collection.add(
                ids=[summary_id],
                documents=[summary_doc],
                metadatas=[summary_meta],
            )

            chunk_records = self._make_chunk_records(file_path, content)
            if not chunk_records:
                continue

            self.chunk_collection.add(
                ids=[record.chunk_id for record in chunk_records],
                documents=[record.text for record in chunk_records],
                metadatas=[record.metadata for record in chunk_records],
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
    ) -> Dict[str, List[List[object]]]:
        query_kwargs = {"n_results": n_results}
        if where:
            query_kwargs["where"] = where
        try:
            return collection.query(query_texts=[query_text], **query_kwargs)
        except TypeError:
            return collection.query(query_texts=[query_text], n_results=n_results)

    def query_similar_documents(self, query_text: str, n_results: int = 15) -> str:
        if self.chunk_collection.count() == 0:
            return ""

        class RetrievalState(TypedDict):
            question: str
            candidate_files: List[str]
            chunk_hits: List[Dict[str, object]]
            context: str

        def select_files(state: RetrievalState) -> RetrievalState:
            result = self._query_collection(
                self.summary_collection,
                query_text=state["question"],
                n_results=min(8, max(1, self.summary_collection.count())),
            )
            metas = result.get("metadatas", [[]])[0]
            candidate_files = [meta.get("file_path") for meta in metas if isinstance(meta, dict) and meta.get("file_path")]
            state["candidate_files"] = list(dict.fromkeys(candidate_files))
            return state

        def collect_chunks(state: RetrievalState) -> RetrievalState:
            hits: List[Dict[str, object]] = []

            target_files = state["candidate_files"][:5]
            if not target_files:
                result = self._query_collection(
                    self.chunk_collection,
                    query_text=state["question"],
                    n_results=min(n_results, max(1, self.chunk_collection.count())),
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
                    )
                    docs = result.get("documents", [[]])[0]
                    metas = result.get("metadatas", [[]])[0]
                    for doc, meta in zip(docs, metas):
                        hits.append({"document": doc, "metadata": meta or {}})

            state["chunk_hits"] = hits[:n_results]
            return state

        def render_context(state: RetrievalState) -> RetrievalState:
            context_parts: List[str] = []
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

    def __init__(self, api_key: Optional[str] = None, model_name: str = "local", chat_model_name: Optional[str] = None):
        self.api_key = api_key
        self.model_name = model_name
        self.chat_model_name = chat_model_name or model_name
        self.logger = logging.getLogger(self.__class__.__name__)

    def _extract_file_headers(self, context: str) -> List[str]:
        return re.findall(r"--- File: (.+?) ---", context)

    def generate_chat_summary(self, context: str, repo_name: str) -> str:
        files = self._extract_file_headers(context)
        unique_files = list(dict.fromkeys(files))
        top_files = ", ".join(unique_files[:6]) if unique_files else "No indexed files"
        return (
            f"{repo_name} is indexed with a hierarchical code index (file summaries + AST chunks). "
            f"Top relevant files for onboarding: {top_files}."
        )

    def generate_chat_response(self, context: str, repo_name: str, question: str) -> str:
        if not context.strip():
            return f"No indexed context found for '{repo_name}'. Re-run analysis to build the repository index."
        return (
            f"Question: {question}\n\n"
            f"Repository: {repo_name}\n"
            "Answer basis: Retrieved AST-aligned chunks with file-level metadata from ChromaDB.\n\n"
            f"{context[:1800]}"
        )

    def generate_documentation(self, context: str, repo_name: str) -> str:
        files = list(dict.fromkeys(self._extract_file_headers(context)))
        stack = ["Flask", "LangGraph", "LlamaIndex CodeSplitter", "ChromaDB", "SQLite"]

        bullets = "\n".join([f"- {file_path}" for file_path in files[:20]]) or "- No files retrieved"
        return (
            f"# {repo_name} Architecture Handbook\n\n"
            "## Executive Summary\n"
            f"- Stack: {', '.join(stack)}\n"
            "- Retrieval is two-tiered: file summaries then AST code chunks.\n"
            "- Chunks include file path, language, function name, and GitHub source links.\n"
            "- Runtime storage uses SQLite for app data and ChromaDB for vectors.\n\n"
            "## Relevant Files\n"
            f"{bullets}\n\n"
            "## Retrieval Pipeline\n"
            "1. Repository files are scanned and summarized per file (Tier 1).\n"
            "2. Source code is chunked by AST blocks (functions/classes/methods) when possible (Tier 2).\n"
            "3. Query flow: summary search narrows files, chunk search retrieves exact code blocks.\n"
        )

    def generate_all_documentation(self, context: str, repo_name: str) -> Dict[str, str]:
        documentation = self.generate_documentation(context, repo_name)
        hld = json.dumps(
            {
                "title": "High-Level Architecture",
                "description": "Two-tier retrieval over repository code",
                "mermaid_code": (
                    "flowchart TD\n"
                    "A[User Query] --> B[LangGraph Tier 1: File Summaries]\n"
                    "B --> C[LangGraph Tier 2: AST Code Chunks]\n"
                    "C --> D[Context Builder]\n"
                    "D --> E[Documentation Output]"
                ),
            }
        )
        lld = json.dumps(
            {
                "title": "Low-Level Retrieval Sequence",
                "description": "Summary-first then chunk retrieval with metadata",
                "mermaid_code": (
                    "sequenceDiagram\n"
                    "participant U as User\n"
                    "participant G as LangGraph\n"
                    "participant S as SummaryCollection\n"
                    "participant C as ChunkCollection\n"
                    "U->>G: ask(question)\n"
                    "G->>S: query summaries\n"
                    "S-->>G: candidate file paths\n"
                    "G->>C: query chunks by file_path\n"
                    "C-->>G: code chunks + metadata\n"
                    "G-->>U: grounded response"
                ),
            }
        )
        chat_summary = self.generate_chat_summary(context, repo_name)

        return {
            "documentation": documentation,
            "hld": hld,
            "lld": lld,
            "chat_summary": chat_summary,
        }
