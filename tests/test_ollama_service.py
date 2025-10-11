"""Tests for OllamaService."""
import os
import unittest
from unittest.mock import Mock, patch

from ollama_service import OllamaService


class TestOllamaService(unittest.TestCase):
    """Test cases for OllamaService."""
    
    def setUp(self):
        """Reset singleton for each test."""
        OllamaService._instance = None
    
    def test_singleton_pattern(self):
        """Test that OllamaService implements singleton pattern correctly."""
        service1 = OllamaService()
        service2 = OllamaService()
        
        self.assertIs(service1, service2)
        self.assertEqual(id(service1), id(service2))
    
    def test_initialization(self):
        """Test service initialization."""
        service = OllamaService()
        
        self.assertIsNotNone(service.base_url)
        self.assertIsNotNone(service.llm_model)
        self.assertIsNotNone(service.embedding_model)
    
    @patch('ollama_service.requests.post')
    def test_generate_response_success(self, mock_post):
        """Test successful response generation."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"response": "Test response"}
        mock_post.return_value = mock_response
        
        service = OllamaService()
        result = service.generate_response("Test prompt")
        
        self.assertEqual(result, "Test response")
        mock_post.assert_called_once()
    
    @patch('ollama_service.requests.post')
    def test_get_embeddings_success(self, mock_post):
        """Test successful embedding generation."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
        mock_post.return_value = mock_response
        
        service = OllamaService()
        result = service.get_embeddings("Test text")
        
        self.assertEqual(result, [0.1, 0.2, 0.3])
        mock_post.assert_called_once()
    
    @patch('ollama_service.requests.get')
    def test_check_model_availability(self, mock_get):
        """Test model availability check."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "models": [
                {"name": "deepseek-r1:1.5b"},
                {"name": "nomic-embed-text:v1.5"}
            ]
        }
        mock_get.return_value = mock_response
        
        service = OllamaService()
        result = service.check_model_availability()
        
        self.assertTrue(result["llm_available"])
        self.assertTrue(result["embedding_available"])
        self.assertIn("deepseek-r1:1.5b", result["all_models"])


if __name__ == '__main__':
    unittest.main()
