"""Unified Neo4j-backed storage for embeddings and knowledge graphs."""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional

from neo4j import GraphDatabase, Session

from config import (
    NEO4J_DATABASE,
    NEO4J_GRAPH_NAMESPACE,
    NEO4J_PASSWORD,
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_VECTOR_INDEX,
)

LOGGER = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_driver():
    """Get cached Neo4j driver instance."""
    LOGGER.info("Connecting to Neo4j at %s", NEO4J_URI)
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))


def get_session() -> Session:
    """Get Neo4j session for database operations."""
    driver = get_driver()
    if NEO4J_DATABASE:
        return driver.session(database=NEO4J_DATABASE)
    return driver.session()


class Neo4jVectorStore:
    """Stores and queries embeddings using Neo4j native vector indexes."""

    def __init__(self, index_name: str = NEO4J_VECTOR_INDEX, namespace: str = NEO4J_GRAPH_NAMESPACE) -> None:
        self.index_name = index_name
        self.namespace = namespace
        self._index_ready = False

    def store_embeddings(self, embeddings: Iterable[Dict[str, Any]]) -> None:
        embeddings = list(embeddings)
        if not embeddings:
            return
        dimension = len(embeddings[0].get("embedding", []))
        if not dimension:
            LOGGER.warning("Embeddings missing vector dimension; skipping store.")
            return

        self._ensure_index(dimension)

        payload = []
        for chunk in embeddings:
            vector = chunk.get("embedding")
            if not vector:
                continue
            payload.append(
                {
                    "chunk_id": chunk.get("chunk_id"),
                    "path": chunk.get("path"),
                    "summary": chunk.get("summary"),
                    "start": chunk.get("start"),
                    "end": chunk.get("end"),
                    "embedding": vector,
                }
            )

        if not payload:
            return

        with get_session() as session:
            session.run(
                """
                UNWIND $rows AS row
                MERGE (c:CodeChunk {namespace: $namespace, chunk_id: row.chunk_id})
                SET c.path = row.path,
                    c.summary = row.summary,
                    c.start = row.start,
                    c.end = row.end,
                    c.embedding = row.embedding
                """,
                rows=payload,
                namespace=self.namespace,
            )

    def query_embeddings(self, query_vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        if not query_vector:
            return []
        self._ensure_index(len(query_vector))
        with get_session() as session:
            result = session.run(
                """
                CALL db.index.vector.queryNodes($index_name, $top_k, $embedding)
                YIELD node, score
                WHERE node.namespace = $namespace
                RETURN node.chunk_id AS chunk_id,
                       node.path AS path,
                       node.summary AS summary,
                       node.start AS start,
                       node.end AS end,
                       score
                ORDER BY score ASC
                """,
                index_name=self.index_name,
                top_k=top_k,
                embedding=query_vector,
                namespace=self.namespace,
            )
            return [dict(record) for record in result]

    def _ensure_index(self, dimension: int) -> None:
        if self._index_ready:
            return
        with get_session() as session:
            existing = session.run(
                """
                SHOW INDEXES YIELD name
                WHERE name = $index_name
                RETURN count(*) AS count
                """,
                index_name=self.index_name,
            ).single()
            if existing and existing.get("count", 0) > 0:
                self._index_ready = True
                return
            LOGGER.info("Creating Neo4j vector index %s", self.index_name)
            session.run(
                """
                CALL db.index.vector.createNodeIndex(
                    $index_name,
                    'CodeChunk',
                    'embedding',
                    $dimension,
                    'cosine'
                )
                """,
                index_name=self.index_name,
                dimension=dimension,
            )
            self._index_ready = True


class Neo4jGraphStore:
    """Persists knowledge graph nodes and relationships."""

    def __init__(self, namespace: str = NEO4J_GRAPH_NAMESPACE) -> None:
        self.namespace = namespace

    def store_graph(self, graph: Dict[str, Any]) -> None:
        nodes = graph.get("nodes", [])
        relationships = graph.get("relationships", [])
        with get_session() as session:
            if nodes:
                session.run(
                    """
                    UNWIND $nodes AS node
                    MERGE (n:GraphNode {namespace: $namespace, node_id: node.id})
                    SET n.name = node.label,
                        n.type = node.type,
                        n.description = node.description
                    """,
                    nodes=nodes,
                    namespace=self.namespace,
                )
            if relationships:
                prepared = [
                    {
                        "source": rel.get("source"),
                        "target": rel.get("target"),
                        "type": rel.get("type"),
                        "description": rel.get("description"),
                    }
                    for rel in relationships
                ]
                session.run(
                    """
                    UNWIND $rels AS rel
                    MATCH (src:GraphNode {namespace: $namespace, node_id: rel.source})
                    MATCH (dst:GraphNode {namespace: $namespace, node_id: rel.target})
                    MERGE (src)-[r:GRAPH_RELATION {namespace: $namespace, rel_type: rel.type}]->(dst)
                    SET r.description = rel.description
                    """,
                    rels=prepared,
                    namespace=self.namespace,
                )


 
