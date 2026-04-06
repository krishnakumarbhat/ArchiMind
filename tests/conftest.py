"""Test environment defaults for deterministic local execution."""

import os
import tempfile


TEST_DB_PATH = os.path.join(tempfile.gettempdir(), "archimind_test_suite.db")

os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["VECTOR_BACKEND"] = "local"
os.environ["GEMINI_API_KEY"] = ""
os.environ["PINECONE_API_KEY"] = ""