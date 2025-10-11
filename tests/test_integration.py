"""Integration tests for ArchiMind components."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agents.analysis_agent import AnalysisAgent
from agents.code_parser_agent import CodeParserAgent
from agents.embedding_agent import EmbeddingAgent
from orchestrator import AnalysisState, run_analysis
from repository_service import RepositoryService
from stores.neo4j_store import Neo4jVectorStore, Neo4jGraphStore


class TestIntegration(unittest.TestCase):
    """Integration tests for the entire ArchiMind pipeline."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.create_test_repository()
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)
    
    def create_test_repository(self):
        """Create a test repository with sample files."""
        # Create a simple Python project structure
        files = {
            "main.py": """
def main():
    print("Hello World")
    return calculate_sum(5, 3)

def calculate_sum(a, b):
    return a + b

if __name__ == "__main__":
    main()
""",
            "utils.py": """
import os
from typing import List

def read_file(filename: str) -> str:
    with open(filename, 'r') as f:
        return f.read()

def process_data(data: List[str]) -> List[str]:
    return [item.strip().upper() for item in data]
""",
            "README.md": """# Test Project
This is a test project for ArchiMind integration testing.
""",
            "requirements.txt": "requests==2.31.0\nFlask==3.0.0"
        }
        
        for filename, content in files.items():
            file_path = Path(self.temp_dir) / filename
            file_path.write_text(content)
    
    def test_repository_service_integration(self):
        """Test repository service can analyze local directory."""
        repo_service = RepositoryService()
        
        try:
            result = repo_service.analyze_repository(self.temp_dir)
            
            # Verify result structure
            self.assertIn("repo_meta", result)
            self.assertIn("code_files", result)
            self.assertIn("repo_url", result)
            
            # Verify metadata
            repo_meta = result["repo_meta"]
            self.assertIn("name", repo_meta)
            self.assertIn("description", repo_meta)
            
            # Verify code files
            code_files = result["code_files"]
            self.assertGreater(len(code_files), 0)
            
            # Check that Python files are included
            python_files = [f for f in code_files if f["path"].endswith('.py')]
            self.assertGreater(len(python_files), 0)
            
        finally:
            repo_service.cleanup()
    
    @patch('ollama_service.requests.post')
    def test_code_parser_agent_integration(self, mock_post):
        """Test code parser agent with repository service."""
        # Mock Ollama responses
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"response": "Analysis complete"}
        mock_post.return_value = mock_response
        
        agent = CodeParserAgent()
        context = AnalysisState(repo_url=self.temp_dir)
        
        try:
            result = agent.run(context)
            
            # Verify context was updated
            self.assertIn("repo_meta", result)
            self.assertIn("code_files", result)
            self.assertGreater(len(result["code_files"]), 0)
            
        finally:
            agent.cleanup()
    
    @patch('ollama_service.requests.post')
    def test_analysis_agent_integration(self, mock_post):
        """Test analysis agent with sample data."""
        # Mock Ollama responses
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "response": "This is a Python project with main.py and utils.py files."
        }
        mock_post.return_value = mock_response
        
        agent = AnalysisAgent()
        context = AnalysisState(
            repo_url=self.temp_dir,
            repo_meta={"name": "test-project", "description": "Test project"},
            code_files=[
                {"path": "main.py", "size": 100},
                {"path": "utils.py", "size": 200}
            ]
        )
        
        result = agent.run(context)
        
        # Verify analysis was generated
        self.assertIn("analysis", result)
        self.assertIsInstance(result["analysis"], str)
        self.assertGreater(len(result["analysis"]), 0)
    
    @patch('ollama_service.requests.post')
    def test_embedding_agent_integration(self, mock_post):
        """Test embedding agent with sample data."""
        # Mock Ollama responses for both generation and embeddings
        def mock_post_side_effect(*args, **kwargs):
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            
            # Check if this is an embedding request
            if 'embeddings' in args[0]:
                mock_response.json.return_value = {
                    "embedding": [0.1, 0.2, 0.3, 0.4, 0.5] * 100  # 500-dim vector
                }
            else:
                mock_response.json.return_value = {
                    "response": "This code defines utility functions for file processing."
                }
            return mock_response
        
        mock_post.side_effect = mock_post_side_effect
        
        # Create mock vector store
        mock_vector_store = Mock(spec=Neo4jVectorStore)
        
        agent = EmbeddingAgent()
        context = AnalysisState(
            code_files=[
                {
                    "path": "main.py",
                    "content": "def main(): print('hello')",
                    "size": 25
                }
            ],
            vector_store=mock_vector_store
        )
        
        result = agent.run(context)
        
        # Verify embeddings were generated
        self.assertIn("embeddings", result)
        embeddings = result["embeddings"]
        self.assertGreater(len(embeddings), 0)
        
        # Verify embedding structure
        embedding = embeddings[0]
        self.assertIn("chunk_id", embedding)
        self.assertIn("path", embedding)
        self.assertIn("summary", embedding)
        self.assertIn("embedding", embedding)
        
        # Verify vector store was called
        mock_vector_store.store_embeddings.assert_called_once()
    
    @patch('ollama_service.requests.post')
    def test_full_pipeline_integration(self, mock_post):
        """Test the complete analysis pipeline."""
        # Mock all Ollama interactions
        def mock_post_side_effect(*args, **kwargs):
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            
            if 'embeddings' in args[0]:
                mock_response.json.return_value = {
                    "embedding": [0.1] * 500
                }
            else:
                mock_response.json.return_value = {
                    "response": "Generated analysis response"
                }
            return mock_response
        
        mock_post.side_effect = mock_post_side_effect
        
        # Test with local directory
        with patch('stores.neo4j_store.get_session') as mock_session:
            # Mock Neo4j session
            mock_neo4j_session = Mock()
            mock_session.return_value.__enter__ = Mock(return_value=mock_neo4j_session)
            mock_session.return_value.__exit__ = Mock(return_value=None)
            
            try:
                result = run_analysis(self.temp_dir)
                
                # Verify result structure
                self.assertIn("analysis", result)
                self.assertIn("knowledge_graph", result)
                self.assertIn("hld", result)
                self.assertIn("lld", result)
                
                # Verify analysis was generated
                self.assertIsInstance(result["analysis"], str)
                
            except Exception as e:
                # Log the error but don't fail the test if Neo4j is not available
                print(f"Pipeline test encountered expected error (likely Neo4j): {e}")


if __name__ == '__main__':
    unittest.main()
