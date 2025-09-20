# neo4j_client.py

import logging
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

class Neo4jClient:
    """Client for Neo4j database operations."""
    
    def __init__(self, uri: str = None, user: str = None, password: str = None, database: str = None):
        self.uri = uri or os.getenv('NEO4J_URI', 'bolt://localhost:7687')
        self.user = user or os.getenv('NEO4J_USER') or os.getenv('NEO4J_USERNAME', 'neo4j')
        self.password = password or os.getenv('NEO4J_PASSWORD', 'password')
        self.database = database or os.getenv('NEO4J_DATABASE', 'neo4j')
        self.driver = None
        self._connect()
    
    def _connect(self):
        """Establish connection to Neo4j."""
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            logger.info("Connected to Neo4j successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {str(e)}")
            raise
    
    def test_connection(self):
        """Test the database connection."""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("RETURN 1 as test")
                return result.single()['test'] == 1
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            raise
    
    def initialize_schema(self):
        """Initialize the database schema and vector index."""
        with self.driver.session(database=self.database) as session:
            # Create constraints and indexes
            constraints_and_indexes = [
                # Node constraints
                "CREATE CONSTRAINT file_path_unique IF NOT EXISTS FOR (f:File) REQUIRE f.path IS UNIQUE",
                "CREATE CONSTRAINT class_name_unique IF NOT EXISTS FOR (c:Class) REQUIRE c.name IS UNIQUE",
                "CREATE CONSTRAINT function_name_unique IF NOT EXISTS FOR (f:Function) REQUIRE f.name IS UNIQUE",
                
                # Indexes for performance
                "CREATE INDEX file_language_idx IF NOT EXISTS FOR (f:File) ON (f.language)",
                "CREATE INDEX class_language_idx IF NOT EXISTS FOR (c:Class) ON (c.language)",
                "CREATE INDEX function_language_idx IF NOT EXISTS FOR (f:Function) ON (f.language)",
                
                # Vector index for embeddings
                "CREATE VECTOR INDEX code_embeddings IF NOT EXISTS FOR (c:CodeChunk) ON (c.embedding) OPTIONS {indexConfig: {`vector.dimensions`: 768, `vector.similarity_function`: 'cosine'}}"
            ]
            
            for query in constraints_and_indexes:
                try:
                    session.run(query)
                    logger.info(f"Executed: {query}")
                except Exception as e:
                    logger.warning(f"Failed to execute {query}: {str(e)}")
    
    def store_code_chunks(self, chunks: List[Dict[str, Any]]):
        """Store code chunks with embeddings in Neo4j."""
        with self.driver.session(database=self.database) as session:
            for chunk in chunks:
                query = """
                MERGE (c:CodeChunk {
                    file_path: $file_path,
                    chunk_index: $chunk_index
                })
                SET c.content = $content,
                    c.chunk_type = $chunk_type,
                    c.language = $language,
                    c.embedding = $embedding
                """
                session.run(query, **chunk)
    
    def store_graph_data(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]):
        """Store graph nodes and edges in Neo4j."""
        with self.driver.session(database=self.database) as session:
            # Store nodes
            for node in nodes:
                if node['type'] == 'file':
                    query = """
                    MERGE (f:File {path: $path})
                    SET f.label = $label,
                        f.language = $language,
                        f.size = $size
                    """
                    session.run(query, 
                        path=node['id'].replace('file_', ''),
                        label=node['label'],
                        language=node['language'],
                        size=node['size']
                    )
                
                elif node['type'] == 'class':
                    query = """
                    MERGE (c:Class {name: $name, file: $file})
                    SET c.label = $label,
                        c.language = $language
                    """
                    session.run(query,
                        name=node['label'],
                        file=node['file'],
                        label=node['label'],
                        language=node['language']
                    )
                
                elif node['type'] == 'function':
                    query = """
                    MERGE (f:Function {name: $name, file: $file})
                    SET f.label = $label,
                        f.language = $language
                    """
                    session.run(query,
                        name=node['label'],
                        file=node['file'],
                        label=node['label'],
                        language=node['language']
                    )
            
            # Store edges
            for edge in edges:
                if edge['type'] == 'IMPORTS':
                    query = """
                    MATCH (from:File {path: $from_path})
                    MATCH (to:File {path: $to_path})
                    MERGE (from)-[r:IMPORTS]->(to)
                    """
                    session.run(query,
                        from_path=edge['from'].replace('file_', ''),
                        to_path=edge['to'].replace('file_', '')
                    )
                
                elif edge['type'] == 'CONTAINS':
                    if 'class_' in edge['to']:
                        query = """
                        MATCH (f:File {path: $file_path})
                        MATCH (c:Class {name: $class_name, file: $file_path})
                        MERGE (f)-[r:CONTAINS]->(c)
                        """
                        class_name = edge['to'].split('_')[-1]
                        session.run(query,
                            file_path=edge['from'].replace('file_', ''),
                            class_name=class_name
                        )
                    
                    elif 'func_' in edge['to']:
                        query = """
                        MATCH (f:File {path: $file_path})
                        MATCH (func:Function {name: $func_name, file: $file_path})
                        MERGE (f)-[r:CONTAINS]->(func)
                        """
                        func_name = edge['to'].split('_')[-1]
                        session.run(query,
                            file_path=edge['from'].replace('file_', ''),
                            func_name=func_name
                        )
    
    def search_similar_code(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for similar code using vector similarity."""
        try:
            # Create embedding for the query
            import ollama
            response = ollama.embeddings(
                model='nomic-embed-text:latest',
                prompt=query
            )
            query_embedding = response['embedding']
            
            # Search using vector similarity
            search_query = """
            CALL db.index.vector.queryNodes('code_embeddings', $limit, $query_embedding)
            YIELD node, score
            RETURN node.content as content, node.file_path as file_path, 
                   node.chunk_type as chunk_type, node.language as language, score
            ORDER BY score DESC
            """
            
            with self.driver.session(database=self.database) as session:
                result = session.run(search_query, 
                    limit=limit, 
                    query_embedding=query_embedding
                )
                
                return [{
                    'content': record['content'],
                    'file_path': record['file_path'],
                    'chunk_type': record['chunk_type'],
                    'language': record['language'],
                    'score': record['score']
                } for record in result]
                
        except Exception as e:
            logger.error(f"Vector search failed: {str(e)}")
            return []
    
    def get_repository_stats(self) -> Dict[str, Any]:
        """Get statistics about the stored repository data."""
        with self.driver.session(database=self.database) as session:
            stats_query = """
            MATCH (f:File)
            OPTIONAL MATCH (c:Class)
            OPTIONAL MATCH (func:Function)
            OPTIONAL MATCH (chunk:CodeChunk)
            RETURN count(DISTINCT f) as files,
                   count(DISTINCT c) as classes,
                   count(DISTINCT func) as functions,
                   count(DISTINCT chunk) as chunks
            """
            
            result = session.run(stats_query)
            record = result.single()
            
            return {
                'files': record['files'],
                'classes': record['classes'],
                'functions': record['functions'],
                'chunks': record['chunks']
            }
    
    def clear_repository_data(self):
        """Clear all repository data from the database."""
        with self.driver.session(database=self.database) as session:
            clear_query = """
            MATCH (n)
            DETACH DELETE n
            """
            session.run(clear_query)
            logger.info("Cleared all repository data")
    
    def close(self):
        """Close the database connection."""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")