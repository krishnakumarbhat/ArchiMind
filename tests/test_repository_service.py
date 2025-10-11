"""Tests for RepositoryService."""
import os
import tempfile
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

from repository_service import RepositoryService


class TestRepositoryService(unittest.TestCase):
    """Test cases for RepositoryService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.service = RepositoryService()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.service.cleanup()
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)
    
    def test_is_local_path(self):
        """Test local path detection."""
        self.assertTrue(self.service._is_local_path("/path/to/local"))
        self.assertTrue(self.service._is_local_path("relative/path"))
        self.assertFalse(self.service._is_local_path("https://github.com/user/repo"))
        self.assertFalse(self.service._is_local_path("http://example.com/repo"))
    
    def test_detect_primary_language(self):
        """Test primary language detection."""
        # Create test files
        test_files = [
            "main.py", "utils.py", "config.py",
            "index.js", "README.md"
        ]
        
        for filename in test_files:
            Path(self.temp_dir, filename).touch()
        
        language = self.service._detect_primary_language(self.temp_dir)
        self.assertEqual(language, "Python")  # Should detect Python as primary
    
    def test_should_include_file(self):
        """Test file inclusion logic."""
        # Test cases: (path, should_include)
        test_cases = [
            ("main.py", True),
            ("src/utils.js", True),
            ("README.md", True),
            ("node_modules/package.json", False),
            (".git/config", False),
            ("__pycache__/module.pyc", False),
            ("build/output.jar", False),
        ]
        
        for path_str, expected in test_cases:
            path = Path(self.temp_dir) / path_str
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
            
            result = self.service._should_include_file(path)
            self.assertEqual(result, expected, f"Failed for path: {path_str}")
    
    def test_analyze_directory(self):
        """Test directory analysis."""
        # Create test files
        test_file = Path(self.temp_dir) / "main.py"
        test_file.write_text("print('Hello World')")
        
        result = self.service._analyze_directory(self.temp_dir)
        
        self.assertIn("repo_meta", result)
        self.assertIn("code_files", result)
        self.assertEqual(len(result["code_files"]), 1)
        self.assertEqual(result["code_files"][0]["path"], "main.py")
    
    @patch('git.Repo.clone_from')
    def test_analyze_remote_repository(self, mock_clone):
        """Test remote repository analysis."""
        # Mock the cloned repo
        mock_repo = Mock()
        mock_repo.working_dir = self.temp_dir
        mock_repo.remotes.origin.url = "https://github.com/user/test-repo.git"
        mock_repo.active_branch.name = "main"
        mock_clone.return_value = mock_repo
        
        # Create a test file in temp directory
        test_file = Path(self.temp_dir) / "app.py"
        test_file.write_text("def main(): pass")
        
        result = self.service._analyze_remote_repository("https://github.com/user/test-repo")
        
        self.assertIn("repo_meta", result)
        self.assertIn("code_files", result)
        self.assertEqual(result["repo_meta"]["name"], "test-repo")


if __name__ == '__main__':
    unittest.main()
