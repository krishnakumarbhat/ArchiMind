"""
Comprehensive test suite for ArchiMind services.
"""
import os
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from services import (
    RepositoryService,
    VectorStoreService,
    DocumentationService,
    ConfigurationError
)


class TestRepositoryService(unittest.TestCase):
    """Test cases for RepositoryService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.service = RepositoryService()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)
    
    def test_singleton_pattern(self):
        """Test that RepositoryService implements Singleton pattern."""
        service1 = RepositoryService()
        service2 = RepositoryService()
        self.assertIs(service1, service2, "RepositoryService should be a singleton")
    
    @patch('git.Repo.clone_from')
    def test_clone_repository_success(self, mock_clone):
        """Test successful repository cloning."""
        repo_url = "https://github.com/test/repo"
        result = self.service.clone_repository(repo_url, self.temp_dir + "/new_repo")
        self.assertTrue(result)
        mock_clone.assert_called_once()
    
    @patch('git.Repo.clone_from')
    def test_clone_repository_failure(self, mock_clone):
        """Test repository cloning failure."""
        import git
        mock_clone.side_effect = git.exc.GitCommandError("clone", "error")
        repo_url = "https://github.com/test/repo"
        result = self.service.clone_repository(repo_url, self.temp_dir + "/new_repo")
        self.assertFalse(result)
    
    def test_clone_repository_existing(self):
        """Test cloning when repository already exists."""
        result = self.service.clone_repository("https://github.com/test/repo", self.temp_dir)
        self.assertTrue(result, "Should return True when directory exists")
    
    def test_read_repository_files(self):
        """Test reading repository files."""
        # Create test files
        test_file = Path(self.temp_dir) / "test.py"
        test_file.write_text("print('Hello World')")
        
        ignored_dir = Path(self.temp_dir) / "node_modules"
        ignored_dir.mkdir()
        (ignored_dir / "package.json").write_text("{}")
        
        allowed_extensions = {'.py', '.md'}
        ignored_dirs = {'node_modules', '.git'}
        
        result = self.service.read_repository_files(
            self.temp_dir,
            allowed_extensions,
            ignored_dirs
        )
        
        self.assertEqual(len(result), 1)
        self.assertIn("test.py", result)
        self.assertEqual(result["test.py"], "print('Hello World')")
    
    def test_read_repository_files_empty(self):
        """Test reading repository with no matching files."""
        allowed_extensions = {'.py'}
        ignored_dirs = set()
        
        result = self.service.read_repository_files(
            self.temp_dir,
            allowed_extensions,
            ignored_dirs
        )
        
        self.assertEqual(len(result), 0)


class TestVectorStoreService(unittest.TestCase):
    """Test cases for VectorStoreService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "chroma_db")
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)
    
    @patch('chromadb.PersistentClient')
    @patch('ollama.Client')
    def test_initialization(self, mock_ollama, mock_chroma):
        """Test VectorStoreService initialization."""
        mock_collection = Mock()
        mock_chroma.return_value.get_or_create_collection.return_value = mock_collection
        
        service = VectorStoreService(
            db_path=self.db_path,
            collection_name="test-repo",
            embedding_model="nomic-embed-text"
        )
        
        self.assertEqual(service.collection_name, "test_repo")
        mock_chroma.assert_called_once_with(path=self.db_path)
    
    @patch('chromadb.PersistentClient')
    @patch('ollama.Client')
    def test_singleton_per_collection(self, mock_ollama, mock_chroma):
        """Test that VectorStoreService creates one instance per collection."""
        mock_collection = Mock()
        mock_chroma.return_value.get_or_create_collection.return_value = mock_collection
        
        service1 = VectorStoreService(self.db_path, "test-repo", "model")
        service2 = VectorStoreService(self.db_path, "test-repo", "model")
        service3 = VectorStoreService(self.db_path, "other-repo", "model")
        
        self.assertIs(service1, service2)
        self.assertIsNot(service1, service3)
    
    def test_sanitize_collection_name(self):
        """Test collection name sanitization."""
        result = VectorStoreService._sanitize_collection_name("test-repo.name/path")
        self.assertEqual(result, "test_repo_name_path")
    
    @patch('chromadb.PersistentClient')
    @patch('ollama.Client')
    def test_is_empty(self, mock_ollama, mock_chroma):
        """Test checking if collection is empty."""
        mock_collection = Mock()
        mock_collection.count.return_value = 0
        mock_chroma.return_value.get_or_create_collection.return_value = mock_collection
        
        service = VectorStoreService(self.db_path, "test", "model")
        self.assertTrue(service.is_empty())
        
        mock_collection.count.return_value = 5
        self.assertFalse(service.is_empty())
    
    @patch('chromadb.PersistentClient')
    @patch('ollama.Client')
    def test_generate_embeddings(self, mock_ollama, mock_chroma):
        """Test generating and storing embeddings."""
        mock_collection = Mock()
        mock_chroma.return_value.get_or_create_collection.return_value = mock_collection
        
        mock_ollama_instance = Mock()
        mock_ollama_instance.embeddings.return_value = {
            'embedding': [0.1, 0.2, 0.3] * 100
        }
        mock_ollama.return_value = mock_ollama_instance
        
        service = VectorStoreService(self.db_path, "test", "model")
        file_contents = {
            "test.py": "print('hello')",
            "main.py": "def main(): pass"
        }
        
        service.generate_embeddings(file_contents)
        
        self.assertEqual(mock_collection.add.call_count, 2)
    
    @patch('chromadb.PersistentClient')
    @patch('ollama.Client')
    def test_query_similar_documents(self, mock_ollama, mock_chroma):
        """Test querying similar documents."""
        mock_collection = Mock()
        mock_collection.query.return_value = {
            'documents': [['content1', 'content2']],
            'ids': [['file1.py', 'file2.py']]
        }
        mock_chroma.return_value.get_or_create_collection.return_value = mock_collection
        
        mock_ollama_instance = Mock()
        mock_ollama_instance.embeddings.return_value = {
            'embedding': [0.1, 0.2, 0.3] * 100
        }
        mock_ollama.return_value = mock_ollama_instance
        
        service = VectorStoreService(self.db_path, "test", "model")
        result = service.query_similar_documents("test query", n_results=2)
        
        self.assertIn("file1.py", result)
        self.assertIn("content1", result)
        self.assertIn("file2.py", result)
        self.assertIn("content2", result)


class TestDocumentationService(unittest.TestCase):
    """Test cases for DocumentationService."""
    
    @patch('genai.Client')
    def test_initialization_success(self, mock_client):
        """Test successful DocumentationService initialization."""
        service = DocumentationService(api_key="test-key")
        self.assertIsNotNone(service.client)
        mock_client.assert_called_once_with(api_key="test-key")
    
    @patch('genai.Client')
    def test_initialization_failure(self, mock_client):
        """Test DocumentationService initialization failure."""
        mock_client.side_effect = Exception("API Error")
        
        with self.assertRaises(ConfigurationError):
            DocumentationService(api_key="invalid-key")
    
    @patch('genai.Client')
    def test_generate_documentation(self, mock_client):
        """Test generating documentation."""
        mock_response = Mock()
        mock_response.text = "# Test Documentation"
        
        mock_client_instance = Mock()
        mock_client_instance.models.generate_content.return_value = mock_response
        mock_client.return_value = mock_client_instance
        
        service = DocumentationService(api_key="test-key")
        result = service.generate_documentation("context", "test-repo")
        
        self.assertEqual(result, "# Test Documentation")
        mock_client_instance.models.generate_content.assert_called_once()
    
    @patch('genai.Client')
    def test_generate_high_level_design(self, mock_client):
        """Test generating HLD graph."""
        mock_response = Mock()
        mock_response.text = '{"title": "Test HLD", "nodes": [], "links": []}'
        
        mock_client_instance = Mock()
        mock_client_instance.models.generate_content.return_value = mock_response
        mock_client.return_value = mock_client_instance
        
        service = DocumentationService(api_key="test-key")
        result = service.generate_high_level_design("context", "test-repo")
        
        self.assertIn("Test HLD", result)
    
    @patch('genai.Client')
    def test_generate_low_level_design(self, mock_client):
        """Test generating LLD graph."""
        mock_response = Mock()
        mock_response.text = '{"title": "Test LLD", "nodes": [], "links": []}'
        
        mock_client_instance = Mock()
        mock_client_instance.models.generate_content.return_value = mock_response
        mock_client.return_value = mock_client_instance
        
        service = DocumentationService(api_key="test-key")
        result = service.generate_low_level_design("context", "test-repo")
        
        self.assertIn("Test LLD", result)
    
    @patch('genai.Client')
    def test_generate_all_documentation(self, mock_client):
        """Test factory method for generating all documentation."""
        mock_response = Mock()
        mock_response.text = "Generated content"
        
        mock_client_instance = Mock()
        mock_client_instance.models.generate_content.return_value = mock_response
        mock_client.return_value = mock_client_instance
        
        service = DocumentationService(api_key="test-key")
        result = service.generate_all_documentation("context", "test-repo")
        
        self.assertIn('documentation', result)
        self.assertIn('hld', result)
        self.assertIn('lld', result)
        self.assertEqual(mock_client_instance.models.generate_content.call_count, 3)


if __name__ == '__main__':
    unittest.main()
