#!/usr/bin/env python3
"""
Validation script for ArchiMind setup.

This script checks that all dependencies are properly installed
and the basic components can be imported successfully.
"""

import sys
import importlib
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Required modules and their descriptions
REQUIRED_MODULES = {
    # Core dependencies
    'flask': 'Web framework',
    'requests': 'HTTP library',
    'neo4j': 'Neo4j database driver',
    'git': 'GitPython library',
    'langgraph': 'LangGraph framework',
    'langchain_core': 'LangChain core',
    
    # ArchiMind modules
    'config': 'Configuration module',
    'ollama_service': 'Ollama service',
    'repository_service': 'Repository service',
    'orchestrator': 'Workflow orchestrator',
    'main': 'Main application',
}

AGENT_MODULES = [
    'agents.base',
    'agents.analysis_agent',
    'agents.chat_agent', 
    'agents.code_parser_agent',
    'agents.diagram_agent',
    'agents.embedding_agent',
    'agents.graph_agent'
]

STORE_MODULES = [
    'stores.neo4j_store'
]


def check_module(module_name: str, description: str = '') -> bool:
    """Check if a module can be imported."""
    try:
        importlib.import_module(module_name)
        logger.info(f"✓ {module_name}: {description}")
        return True
    except ImportError as e:
        logger.error(f"✗ {module_name}: {description} - {str(e)}")
        return False
    except Exception as e:
        logger.warning(f"? {module_name}: {description} - {str(e)}")
        return False


def check_file_structure() -> bool:
    """Check that required files exist."""
    required_files = [
        'main.py',
        'config.py', 
        'ollama_service.py',
        'repository_service.py',
        'orchestrator.py',
        'requirements.txt',
        'agents/__init__.py',
        'stores/__init__.py',
        'stores/neo4j_store.py',
        'templates/index.html',
        'templates/doc.html',
        'static/script.js'
    ]
    
    all_exist = True
    logger.info("\n=== File Structure Check ===")
    
    for file_path in required_files:
        if Path(file_path).exists():
            logger.info(f"✓ {file_path}")
        else:
            logger.error(f"✗ {file_path} - Missing")
            all_exist = False
    
    return all_exist


def check_imports() -> bool:
    """Check all module imports."""
    logger.info("\n=== Module Import Check ===")
    
    success_count = 0
    total_count = 0
    
    # Check core dependencies
    for module, desc in REQUIRED_MODULES.items():
        if check_module(module, desc):
            success_count += 1
        total_count += 1
    
    # Check agent modules
    logger.info("\n--- Agent Modules ---")
    for module in AGENT_MODULES:
        if check_module(module):
            success_count += 1
        total_count += 1
    
    # Check store modules  
    logger.info("\n--- Store Modules ---")
    for module in STORE_MODULES:
        if check_module(module):
            success_count += 1
        total_count += 1
    
    return success_count == total_count


def check_configuration():
    """Check configuration settings."""
    logger.info("\n=== Configuration Check ===")
    
    try:
        import config
        
        # Check required config variables
        required_configs = [
            'OLLAMA_BASE_URL',
            'LLM_MODEL', 
            'EMBEDDING_MODEL',
            'NEO4J_URI',
            'NEO4J_USERNAME',
            'NEO4J_PASSWORD'
        ]
        
        for config_name in required_configs:
            if hasattr(config, config_name):
                value = getattr(config, config_name)
                logger.info(f"✓ {config_name}: {value}")
            else:
                logger.error(f"✗ {config_name}: Missing")
        
        return True
        
    except Exception as e:
        logger.error(f"Configuration check failed: {str(e)}")
        return False


def test_basic_functionality():
    """Test basic functionality without external dependencies."""
    logger.info("\n=== Basic Functionality Test ===")
    
    try:
        # Test OllamaService singleton
        from ollama_service import OllamaService
        service1 = OllamaService()
        service2 = OllamaService()
        
        if service1 is service2:
            logger.info("✓ OllamaService singleton pattern working")
        else:
            logger.error("✗ OllamaService singleton pattern failed")
            return False
        
        # Test RepositoryService
        from repository_service import RepositoryService
        repo_service = RepositoryService()
        logger.info("✓ RepositoryService can be instantiated")
        
        # Test agent creation
        from agents.analysis_agent import AnalysisAgent
        from agents.embedding_agent import EmbeddingAgent
        
        analysis_agent = AnalysisAgent()
        embedding_agent = EmbeddingAgent()
        logger.info("✓ Agents can be instantiated")
        
        # Test store classes
        from stores.neo4j_store import Neo4jVectorStore, Neo4jGraphStore
        
        vector_store = Neo4jVectorStore()
        graph_store = Neo4jGraphStore()
        logger.info("✓ Store classes can be instantiated")
        
        return True
        
    except Exception as e:
        logger.error(f"Basic functionality test failed: {str(e)}")
        return False


def main():
    """Main validation function."""
    logger.info("ArchiMind Setup Validation")
    logger.info("=" * 50)
    
    checks = [
        ("File Structure", check_file_structure),
        ("Module Imports", check_imports), 
        ("Configuration", check_configuration),
        ("Basic Functionality", test_basic_functionality)
    ]
    
    results = []
    
    for check_name, check_func in checks:
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            logger.error(f"Check '{check_name}' failed with exception: {str(e)}")
            results.append((check_name, False))
    
    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("VALIDATION SUMMARY")
    logger.info("=" * 50)
    
    total_checks = len(results)
    passed_checks = sum(1 for _, result in results if result)
    
    for check_name, result in results:
        status = "PASS" if result else "FAIL"
        logger.info(f"{check_name}: {status}")
    
    logger.info(f"\nOverall: {passed_checks}/{total_checks} checks passed")
    
    if passed_checks == total_checks:
        logger.info("🎉 All validation checks passed! ArchiMind is ready to use.")
        return 0
    else:
        logger.warning("⚠️  Some validation checks failed. Please review the errors above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
