"""
Ollama Service - Simple service pattern for interacting with Ollama models.
Uses Singleton pattern to ensure single instance of the service.
"""

import requests
import json
from typing import Optional, Dict, Any
from config import OLLAMA_BASE_URL, LLM_MODEL, EMBEDDING_MODEL


class OllamaService:
    """
    Service class for interacting with Ollama API.
    Implements Singleton pattern for efficient resource usage.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OllamaService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self.base_url = OLLAMA_BASE_URL
        self.llm_model = LLM_MODEL
        self.embedding_model = EMBEDDING_MODEL
        self._initialized = True
    
    def generate_response(self, prompt: str, model: Optional[str] = None) -> str:
        """
        Generate a response from the LLM model.
        
        Args:
            prompt: The input prompt for the model
            model: Optional model name (defaults to LLM_MODEL from config)
            
        Returns:
            Generated text response
        """
        model_name = model or self.llm_model
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False
        }
        
        try:
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "No response generated.")
        except requests.exceptions.RequestException as e:
            return f"Error communicating with Ollama: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"
    
    def get_embeddings(self, text: str, model: Optional[str] = None) -> Optional[list]:
        """
        Get embeddings for the given text.
        
        Args:
            text: The text to embed
            model: Optional model name (defaults to EMBEDDING_MODEL from config)
            
        Returns:
            List of embedding values or None on error
        """
        model_name = model or self.embedding_model
        url = f"{self.base_url}/api/embeddings"
        
        payload = {
            "model": model_name,
            "prompt": text
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            return result.get("embedding", None)
        except requests.exceptions.RequestException as e:
            print(f"Error getting embeddings: {str(e)}")
            return None
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            return None
    
    def check_model_availability(self) -> Dict[str, bool]:
        """
        Check if required models are available in Ollama.
        
        Returns:
            Dictionary with model availability status
        """
        url = f"{self.base_url}/api/tags"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            result = response.json()
            models = [model.get("name", "") for model in result.get("models", [])]
            
            return {
                "llm_available": self.llm_model in models,
                "embedding_available": self.embedding_model in models,
                "all_models": models
            }
        except Exception as e:
            print(f"Error checking models: {str(e)}")
            return {
                "llm_available": False,
                "embedding_available": False,
                "all_models": []
            }
 
