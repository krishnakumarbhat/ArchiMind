"""
Test suite for ArchiMind Flask application.
"""
import os
import json
import unittest
from unittest.mock import patch, Mock, MagicMock
import tempfile

# Set test environment before importing app
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['SECRET_KEY'] = 'test-secret-key'

from app import ArchiMindApplication, User, AnalysisLog, db


class TestArchiMindApplication(unittest.TestCase):
    """Test cases for Flask application."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.app_instance = ArchiMindApplication()
        self.app = self.app_instance.app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        
        with self.app.app_context():
            db.create_all()
    
    def tearDown(self):
        """Clean up test fixtures."""
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)
    
    def test_index_route(self):
        """Test home page route."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'ArchiMind', response.data)
    
    def test_api_analyze_missing_url(self):
        """Test analysis API with missing URL."""
        response = self.client.post(
            '/api/analyze',
            json={},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    @patch('subprocess.Popen')
    def test_api_analyze_success(self, mock_popen):
        """Test successful analysis request."""
        with self.app.app_context():
            response = self.client.post(
                '/api/analyze',
                json={'repo_url': 'https://github.com/test/repo'},
                content_type='application/json'
            )
            
            self.assertEqual(response.status_code, 202)
            data = json.loads(response.data)
            self.assertEqual(data['status'], 'success')
            
            # Verify analysis log was created
            log = AnalysisLog.query.first()
            self.assertIsNotNone(log)
            self.assertEqual(log.repo_url, 'https://github.com/test/repo')
    
    def test_api_analyze_rate_limit(self):
        """Test rate limiting for anonymous users."""
        with self.app.app_context():
            # Create 5 analysis logs for the session
            for i in range(5):
                log = AnalysisLog(
                    session_id='test-session',
                    repo_url=f'https://github.com/test/repo{i}',
                    status='completed'
                )
                db.session.add(log)
            db.session.commit()
            
            # Try to create the 6th analysis
            with self.client.session_transaction() as sess:
                sess['session_id'] = 'test-session'
            
            response = self.client.post(
                '/api/analyze',
                json={'repo_url': 'https://github.com/test/repo6'},
                content_type='application/json'
            )
            
            self.assertEqual(response.status_code, 403)
            data = json.loads(response.data)
            self.assertTrue(data['limit_reached'])
    
    def test_api_status_no_file(self):
        """Test status API when no status file exists."""
        response = self.client.get('/api/status')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'idle')
    
    def test_api_check_limit_anonymous(self):
        """Test check limit API for anonymous user."""
        response = self.client.get('/api/check-limit')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data['authenticated'])
        self.assertEqual(data['limit'], 5)
        self.assertTrue(data['can_generate'])
    
    def test_login_route_get(self):
        """Test login page GET request."""
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'login', response.data.lower())
    
    def test_sign_up_route_get(self):
        """Test sign up page GET request."""
        response = self.client.get('/sign-up')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'sign', response.data.lower())
    
    def test_sign_up_success(self):
        """Test successful user registration."""
        with self.app.app_context():
            response = self.client.post(
                '/sign-up',
                data={
                    'email': 'test@example.com',
                    'firstName': 'Test',
                    'password1': 'password123',
                    'password2': 'password123'
                },
                follow_redirects=True
            )
            
            self.assertEqual(response.status_code, 200)
            
            # Verify user was created
            user = User.query.filter_by(email='test@example.com').first()
            self.assertIsNotNone(user)
            self.assertEqual(user.first_name, 'Test')
    
    def test_sign_up_password_mismatch(self):
        """Test sign up with password mismatch."""
        response = self.client.post(
            '/sign-up',
            data={
                'email': 'test@example.com',
                'firstName': 'Test',
                'password1': 'password123',
                'password2': 'different123'
            }
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"don't match", response.data.lower())
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials."""
        response = self.client.post(
            '/login',
            data={
                'email': 'nonexistent@example.com',
                'password': 'wrongpassword'
            }
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'does not exist', response.data.lower())


class TestDatabaseModels(unittest.TestCase):
    """Test cases for database models."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.app = ArchiMindApplication().app
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        with self.app.app_context():
            db.create_all()
    
    def tearDown(self):
        """Clean up test fixtures."""
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
    
    def test_user_creation(self):
        """Test User model creation."""
        with self.app.app_context():
            user = User(
                email='test@example.com',
                password='hashed_password',
                first_name='Test'
            )
            db.session.add(user)
            db.session.commit()
            
            retrieved = User.query.filter_by(email='test@example.com').first()
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.first_name, 'Test')
    
    def test_user_get_analysis_count(self):
        """Test User.get_analysis_count method."""
        with self.app.app_context():
            user = User(
                email='test@example.com',
                password='hashed_password',
                first_name='Test'
            )
            db.session.add(user)
            db.session.commit()
            
            # Add analysis logs
            for i in range(3):
                log = AnalysisLog(
                    user_id=user.id,
                    repo_url=f'https://github.com/test/repo{i}',
                    status='completed'
                )
                db.session.add(log)
            db.session.commit()
            
            self.assertEqual(user.get_analysis_count(), 3)
    
    def test_analysis_log_creation(self):
        """Test AnalysisLog model creation."""
        with self.app.app_context():
            log = AnalysisLog(
                session_id='test-session',
                repo_url='https://github.com/test/repo',
                status='pending'
            )
            db.session.add(log)
            db.session.commit()
            
            retrieved = AnalysisLog.query.first()
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.repo_url, 'https://github.com/test/repo')
            self.assertEqual(retrieved.status, 'pending')


if __name__ == '__main__':
    unittest.main()
