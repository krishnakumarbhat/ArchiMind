"""
Test suite for ArchiMind worker process.
"""
import os
import json
import unittest
from unittest.mock import patch, Mock, MagicMock
import tempfile

from worker import AnalysisWorker


class TestAnalysisWorker(unittest.TestCase):
    """Test cases for AnalysisWorker."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.status_file = os.path.join(self.temp_dir, 'status.json')
        
        # Mock config
        self.config_patcher = patch('worker.config')
        self.mock_config = self.config_patcher.start()
        self.mock_config.STATUS_FILE_PATH = self.status_file
        self.mock_config.LOCAL_CLONE_PATH = os.path.join(self.temp_dir, 'repo')
        self.mock_config.CHROMA_DB_PATH = os.path.join(self.temp_dir, 'chroma')
        self.mock_config.EMBEDDING_MODEL = 'nomic-embed-text'
        self.mock_config.GEMINI_API_KEY = 'test-key'
        self.mock_config.GENERATION_MODEL = 'gemini-2.5-pro'
        self.mock_config.ALLOWED_EXTENSIONS = {'.py', '.md'}
        self.mock_config.IGNORED_DIRECTORIES = {'.git', 'node_modules'}
        
        self.worker = AnalysisWorker()
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.config_patcher.stop()
        
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)
    
    def test_update_status(self):
        """Test status file update."""
        status = {'status': 'processing', 'result': None, 'error': None}
        self.worker._update_status(status)
        
        self.assertTrue(os.path.exists(self.status_file))
        with open(self.status_file, 'r') as f:
            loaded = json.load(f)
        
        self.assertEqual(loaded['status'], 'processing')
    
    def test_clean_json_response_with_fences(self):
        """Test cleaning JSON response with markdown fences."""
        raw = '```json\n{"key": "value"}\n```'
        cleaned = self.worker._clean_json_response(raw)
        self.assertEqual(cleaned, '{"key": "value"}')
    
    def test_clean_json_response_with_prefix(self):
        """Test cleaning JSON response with text prefix."""
        raw = 'Here is the JSON:\n{"key": "value"}'
        cleaned = self.worker._clean_json_response(raw)
        self.assertEqual(cleaned, '{"key": "value"}')
    
    def test_clean_json_response_empty(self):
        """Test cleaning empty JSON response."""
        cleaned = self.worker._clean_json_response('')
        self.assertEqual(cleaned, '')
    
    def test_parse_graph_data_success(self):
        """Test successful graph data parsing."""
        raw_json = '{"title": "Test", "nodes": [], "links": []}'
        result = self.worker._parse_graph_data(raw_json, 'HLD')
        
        self.assertEqual(result['status'], 'ok')
        self.assertIn('graph', result)
        self.assertEqual(result['graph']['title'], 'Test')
    
    def test_parse_graph_data_invalid_json(self):
        """Test parsing invalid JSON."""
        raw_json = '{invalid json}'
        result = self.worker._parse_graph_data(raw_json, 'HLD')
        
        self.assertEqual(result['status'], 'error')
        self.assertIn('message', result)
    
    def test_parse_graph_data_empty(self):
        """Test parsing empty graph data."""
        result = self.worker._parse_graph_data('', 'LLD')
        
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['message'], 'No LLD data returned.')
    
    @patch('worker.DocumentationService')
    @patch('worker.VectorStoreService')
    @patch('worker.RepositoryService')
    def test_run_analysis_success(self, mock_repo_service, mock_vector_service, mock_doc_service):
        """Test successful analysis execution."""
        # Mock RepositoryService
        mock_repo_instance = Mock()
        mock_repo_instance.clone_repository.return_value = True
        mock_repo_instance.read_repository_files.return_value = {
            'main.py': 'print("hello")',
            'test.py': 'def test(): pass'
        }
        mock_repo_service.return_value = mock_repo_instance
        
        # Mock VectorStoreService
        mock_vector_instance = Mock()
        mock_vector_instance.is_empty.return_value = True
        mock_vector_instance.query_similar_documents.return_value = 'Test context'
        mock_vector_service.return_value = mock_vector_instance
        
        # Mock DocumentationService
        mock_doc_instance = Mock()
        mock_doc_instance.generate_all_documentation.return_value = {
            'documentation': '# Test Docs',
            'hld': '{"title": "HLD", "nodes": [], "links": []}',
            'lld': '{"title": "LLD", "nodes": [], "links": []}'
        }
        mock_doc_service.return_value = mock_doc_instance
        
        # Run analysis
        self.worker.run_analysis('https://github.com/test/repo')
        
        # Verify status file
        self.assertTrue(os.path.exists(self.status_file))
        with open(self.status_file, 'r') as f:
            status = json.load(f)
        
        self.assertEqual(status['status'], 'completed')
        self.assertIn('result', status)
        self.assertIn('chat_response', status['result'])
    
    @patch('worker.RepositoryService')
    def test_run_analysis_clone_failure(self, mock_repo_service):
        """Test analysis with repository clone failure."""
        mock_repo_instance = Mock()
        mock_repo_instance.clone_repository.return_value = False
        mock_repo_service.return_value = mock_repo_instance
        
        self.worker.run_analysis('https://github.com/test/repo')
        
        # Verify error status
        with open(self.status_file, 'r') as f:
            status = json.load(f)
        
        self.assertEqual(status['status'], 'error')
        self.assertIn('error', status)
    
    @patch('worker.VectorStoreService')
    @patch('worker.RepositoryService')
    def test_run_analysis_no_files(self, mock_repo_service, mock_vector_service):
        """Test analysis with no processable files."""
        mock_repo_instance = Mock()
        mock_repo_instance.clone_repository.return_value = True
        mock_repo_instance.read_repository_files.return_value = {}
        mock_repo_service.return_value = mock_repo_instance
        
        mock_vector_instance = Mock()
        mock_vector_instance.is_empty.return_value = True
        mock_vector_service.return_value = mock_vector_instance
        
        self.worker.run_analysis('https://github.com/test/repo')
        
        # Verify error status
        with open(self.status_file, 'r') as f:
            status = json.load(f)
        
        self.assertEqual(status['status'], 'error')
        self.assertIn('No processable files', status['error'])


if __name__ == '__main__':
    unittest.main()
