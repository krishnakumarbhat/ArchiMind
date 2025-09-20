# agents.py

import os
import re
import json
import logging
import requests
import subprocess
import tempfile
import shutil
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import ast
import ollama
from neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)

@dataclass
class CodeFile:
    """Represents a code file with its content and metadata."""
    path: str
    content: str
    language: str
    size: int
    functions: List[Dict[str, Any]]
    classes: List[Dict[str, Any]]
    imports: List[str]

class CodeParserAgent:
    """Agent responsible for fetching and parsing repository code."""
    
    def __init__(self):
        self.excluded_patterns = [
            r'.*',  # Hidden files
            r'assets/*', r'data/*', r'examples/*', r'images/*', 
            r'public/*', r'static/*', r'temp/*', r'docs/*',
            r'venv/*', r'.venv/*', r'*test*', r'tests/*',
            r'v1/*', r'dist/*', r'build/*', r'experimental/*',
            r'deprecated/*', r'misc/*', r'legacy/*', r'.git/*',
            r'.github/*', r'.next/*', r'.vscode/*', r'obj/*',
            r'bin/*', r'node_modules/*', r'*.log'
        ]
        self.compiled_patterns = [re.compile(pattern) for pattern in self.excluded_patterns]
    
    def should_exclude_file(self, file_path: str) -> bool:
        """Check if a file should be excluded based on patterns."""
        for pattern in self.compiled_patterns:
            if pattern.match(file_path):
                return True
        return False
    
    def fetch_repository(self, repo_url: str) -> Dict[str, Any]:
        """Fetch repository contents using GitHub API or git clone."""
        try:
            # Try GitHub API first
            if 'github.com' in repo_url:
                return self._fetch_via_github_api(repo_url)
            else:
                return self._fetch_via_git_clone(repo_url)
        except Exception as e:
            logger.error(f"Failed to fetch repository: {str(e)}")
            raise
    
    def _fetch_via_github_api(self, repo_url: str) -> Dict[str, Any]:
        """Fetch repository using GitHub API."""
        # Extract owner and repo from URL
        match = re.search(r'github\.com/([^/]+)/([^/]+)', repo_url)
        if not match:
            raise ValueError("Invalid GitHub URL format")
        
        owner, repo = match.groups()
        repo = repo.rstrip('.git')  # Remove .git suffix if present
        
        # Get repository info
        repo_info_url = f"https://api.github.com/repos/{owner}/{repo}"
        headers = {'Accept': 'application/vnd.github.v3+json'}
        
        repo_response = requests.get(repo_info_url, headers=headers)
        if repo_response.status_code != 200:
            raise Exception(f"Failed to fetch repo info: {repo_response.status_code}")
        
        repo_info = repo_response.json()
        
        # Get README
        readme_url = f"https://api.github.com/repos/{owner}/{repo}/readme"
        readme_response = requests.get(readme_url, headers=headers)
        readme_content = ""
        if readme_response.status_code == 200:
            readme_data = readme_response.json()
            import base64
            readme_content = base64.b64decode(readme_data['content']).decode('utf-8')
        
        # Get repository tree
        tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"
        tree_response = requests.get(tree_url, headers=headers)
        if tree_response.status_code != 200:
            raise Exception(f"Failed to fetch tree: {tree_response.status_code}")
        
        tree_data = tree_response.json()
        
        # Process files
        files = []
        for item in tree_data.get('tree', []):
            if item['type'] == 'blob' and not self.should_exclude_file(item['path']):
                # Get file content
                content_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{item['path']}"
                content_response = requests.get(content_url, headers=headers)
                if content_response.status_code == 200:
                    content_data = content_response.json()
                    if content_data.get('encoding') == 'base64':
                        import base64
                        content = base64.b64decode(content_data['content']).decode('utf-8')
                        files.append({
                            'path': item['path'],
                            'content': content,
                            'size': item['size']
                        })
        
        return {
            'name': repo_info['name'],
            'description': repo_info.get('description', ''),
            'readme': readme_content,
            'files': files
        }
    
    def _fetch_via_git_clone(self, repo_url: str) -> Dict[str, Any]:
        """Fetch repository using git clone."""
        temp_dir = tempfile.mkdtemp()
        try:
            # Clone repository
            subprocess.run(['git', 'clone', repo_url, temp_dir], check=True)
            
            # Read README
            readme_content = ""
            readme_files = ['README.md', 'README.rst', 'README.txt', 'README']
            for readme_file in readme_files:
                readme_path = os.path.join(temp_dir, readme_file)
                if os.path.exists(readme_path):
                    with open(readme_path, 'r', encoding='utf-8') as f:
                        readme_content = f.read()
                    break
            
            # Process files
            files = []
            for root, dirs, filenames in os.walk(temp_dir):
                # Remove excluded directories
                dirs[:] = [d for d in dirs if not self.should_exclude_file(d)]
                
                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    relative_path = os.path.relpath(file_path, temp_dir)
                    
                    if not self.should_exclude_file(relative_path):
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            files.append({
                                'path': relative_path,
                                'content': content,
                                'size': len(content)
                            })
                        except UnicodeDecodeError:
                            # Skip binary files
                            continue
            
            return {
                'name': os.path.basename(repo_url.rstrip('.git')),
                'description': '',
                'readme': readme_content,
                'files': files
            }
        finally:
            shutil.rmtree(temp_dir)
    
    def parse_code_file(self, file_path: str, content: str) -> CodeFile:
        """Parse a code file and extract metadata."""
        language = self._detect_language(file_path)
        functions = []
        classes = []
        imports = []
        
        if language == 'python':
            functions, classes, imports = self._parse_python_file(content)
        elif language in ['javascript', 'typescript']:
            functions, classes, imports = self._parse_js_file(content)
        elif language == 'java':
            functions, classes, imports = self._parse_java_file(content)
        
        return CodeFile(
            path=file_path,
            content=content,
            language=language,
            size=len(content),
            functions=functions,
            classes=classes,
            imports=imports
        )
    
    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        ext = Path(file_path).suffix.lower()
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.cs': 'csharp',
            '.go': 'go',
            '.rs': 'rust',
            '.php': 'php',
            '.rb': 'ruby',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala'
        }
        return language_map.get(ext, 'unknown')
    
    def _parse_python_file(self, content: str) -> tuple:
        """Parse Python file for functions, classes, and imports."""
        try:
            tree = ast.parse(content)
            functions = []
            classes = []
            imports = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append({
                        'name': node.name,
                        'line': node.lineno,
                        'args': [arg.arg for arg in node.args.args],
                        'docstring': ast.get_docstring(node)
                    })
                elif isinstance(node, ast.ClassDef):
                    classes.append({
                        'name': node.name,
                        'line': node.lineno,
                        'bases': [base.id for base in node.bases if isinstance(base, ast.Name)],
                        'docstring': ast.get_docstring(node)
                    })
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.append(alias.name)
                    else:
                        module = node.module or ''
                        for alias in node.names:
                            imports.append(f"{module}.{alias.name}" if module else alias.name)
            
            return functions, classes, imports
        except SyntaxError:
            return [], [], []
    
    def _parse_js_file(self, content: str) -> tuple:
        """Parse JavaScript/TypeScript file for functions and classes."""
        functions = []
        classes = []
        imports = []
        
        # Simple regex-based parsing for JS/TS
        # Function declarations
        func_pattern = r'function\s+(\w+)\s*\([^)]*\)'
        for match in re.finditer(func_pattern, content):
            functions.append({
                'name': match.group(1),
                'line': content[:match.start()].count('\n') + 1,
                'args': [],
                'docstring': None
            })
        
        # Class declarations
        class_pattern = r'class\s+(\w+)'
        for match in re.finditer(class_pattern, content):
            classes.append({
                'name': match.group(1),
                'line': content[:match.start()].count('\n') + 1,
                'bases': [],
                'docstring': None
            })
        
        # Import statements
        import_pattern = r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]'
        for match in re.finditer(import_pattern, content):
            imports.append(match.group(1))
        
        return functions, classes, imports
    
    def _parse_java_file(self, content: str) -> tuple:
        """Parse Java file for methods and classes."""
        functions = []
        classes = []
        imports = []
        
        # Class declarations
        class_pattern = r'(?:public\s+)?class\s+(\w+)'
        for match in re.finditer(class_pattern, content):
            classes.append({
                'name': match.group(1),
                'line': content[:match.start()].count('\n') + 1,
                'bases': [],
                'docstring': None
            })
        
        # Method declarations
        method_pattern = r'(?:public|private|protected)?\s*(?:static\s+)?\w+\s+(\w+)\s*\([^)]*\)'
        for match in re.finditer(method_pattern, content):
            functions.append({
                'name': match.group(1),
                'line': content[:match.start()].count('\n') + 1,
                'args': [],
                'docstring': None
            })
        
        # Import statements
        import_pattern = r'import\s+([^;]+);'
        for match in re.finditer(import_pattern, content):
            imports.append(match.group(1))
        
        return functions, classes, imports

class EmbeddingAgent:
    """Agent responsible for creating embeddings from code chunks."""
    
    def __init__(self):
        self.neo4j_client = Neo4jClient()
    
    def create_embeddings(self, files: List[CodeFile]) -> List[Dict[str, Any]]:
        """Create embeddings for code files and store in Neo4j."""
        chunks = []
        
        for file in files:
            # Create chunks from file content
            file_chunks = self._chunk_file(file)
            
            for i, chunk in enumerate(file_chunks):
                # Create embedding
                embedding = self._create_embedding(chunk['content'])
                
                chunk_data = {
                    'file_path': file.path,
                    'chunk_index': i,
                    'content': chunk['content'],
                    'chunk_type': chunk['type'],
                    'language': file.language,
                    'embedding': embedding
                }
                chunks.append(chunk_data)
        
        # Store chunks in Neo4j
        self.neo4j_client.store_code_chunks(chunks)
        
        return chunks
    
    def _chunk_file(self, file: CodeFile) -> List[Dict[str, Any]]:
        """Split file into chunks for embedding."""
        chunks = []
        content = file.content
        
        # Split by functions and classes for better granularity
        if file.language == 'python':
            chunks.extend(self._chunk_python_file(file))
        else:
            # Generic chunking for other languages
            chunk_size = 1000  # characters
            overlap = 200
            
            for i in range(0, len(content), chunk_size - overlap):
                chunk_content = content[i:i + chunk_size]
                if chunk_content.strip():
                    chunks.append({
                        'content': chunk_content,
                        'type': 'code_block'
                    })
        
        return chunks
    
    def _chunk_python_file(self, file: CodeFile) -> List[Dict[str, Any]]:
        """Create specific chunks for Python files."""
        chunks = []
        
        # Add file-level chunk
        chunks.append({
            'content': f"File: {file.path}\n\n{file.content[:500]}...",
            'type': 'file_overview'
        })
        
        # Add class chunks
        for class_info in file.classes:
            chunks.append({
                'content': f"Class: {class_info['name']} in {file.path}\nDocstring: {class_info.get('docstring', 'N/A')}",
                'type': 'class'
            })
        
        # Add function chunks
        for func_info in file.functions:
            chunks.append({
                'content': f"Function: {func_info['name']} in {file.path}\nDocstring: {func_info.get('docstring', 'N/A')}",
                'type': 'function'
            })
        
        return chunks
    
    def _create_embedding(self, text: str) -> List[float]:
        """Create embedding using nomic-embed-text model."""
        try:
            response = ollama.embeddings(
                model='nomic-embed-text:latest',
                prompt=text
            )
            return response['embedding']
        except Exception as e:
            logger.error(f"Failed to create embedding: {str(e)}")
            return [0.0] * 768  # Default embedding size

class GraphAgent:
    """Agent responsible for building graph models of code relationships."""
    
    def __init__(self):
        self.neo4j_client = Neo4jClient()
    
    def build_graph(self, files: List[CodeFile]) -> Dict[str, Any]:
        """Build a graph model of code relationships."""
        try:
            # Analyze code relationships
            relationships = self._analyze_relationships(files)
            
            # Create graph nodes and edges
            nodes = []
            edges = []
            
            # Add file nodes
            for file in files:
                nodes.append({
                    'id': f"file_{file.path}",
                    'label': file.path,
                    'type': 'file',
                    'language': file.language,
                    'size': file.size
                })
            
            # Add class and function nodes
            for file in files:
                for class_info in file.classes:
                    node_id = f"class_{file.path}_{class_info['name']}"
                    nodes.append({
                        'id': node_id,
                        'label': class_info['name'],
                        'type': 'class',
                        'file': file.path,
                        'language': file.language
                    })
                    # Connect class to file
                    edges.append({
                        'from': f"file_{file.path}",
                        'to': node_id,
                        'type': 'CONTAINS'
                    })
                
                for func_info in file.functions:
                    node_id = f"func_{file.path}_{func_info['name']}"
                    nodes.append({
                        'id': node_id,
                        'label': func_info['name'],
                        'type': 'function',
                        'file': file.path,
                        'language': file.language
                    })
                    # Connect function to file
                    edges.append({
                        'from': f"file_{file.path}",
                        'to': node_id,
                        'type': 'CONTAINS'
                    })
            
            # Add relationship edges
            for rel in relationships:
                edges.append(rel)
            
            # Store in Neo4j
            self.neo4j_client.store_graph_data(nodes, edges)
            
            return {
                'nodes': nodes,
                'edges': edges,
                'statistics': {
                    'total_files': len(files),
                    'total_classes': sum(len(f.classes) for f in files),
                    'total_functions': sum(len(f.functions) for f in files),
                    'total_relationships': len(relationships)
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to build graph: {str(e)}")
            raise
    
    def _analyze_relationships(self, files: List[CodeFile]) -> List[Dict[str, Any]]:
        """Analyze relationships between code components."""
        relationships = []
        
        # Analyze imports
        for file in files:
            for import_name in file.imports:
                # Find files that might contain this import
                for other_file in files:
                    if other_file.path != file.path:
                        # Check if other file has classes/functions that match import
                        for class_info in other_file.classes:
                            if class_info['name'] in import_name:
                                relationships.append({
                                    'from': f"file_{file.path}",
                                    'to': f"file_{other_file.path}",
                                    'type': 'IMPORTS'
                                })
        
        return relationships

class DiagramAgent:
    """Agent responsible for generating Vis.js-compatible diagrams."""
    
    def generate_hld(self, graph_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate High-Level Design diagram."""
        nodes = []
        edges = []
        
        # Create HLD nodes (files and major components)
        for node in graph_data['nodes']:
            if node['type'] == 'file':
                nodes.append({
                    'id': node['id'],
                    'label': node['label'],
                    'group': 'file',
                    'title': f"File: {node['label']}\nLanguage: {node['language']}\nSize: {node['size']} chars"
                })
        
        # Create HLD edges (file relationships)
        for edge in graph_data['edges']:
            if edge['type'] == 'IMPORTS':
                edges.append({
                    'from': edge['from'],
                    'to': edge['to'],
                    'arrows': 'to',
                    'label': 'imports'
                })
        
        return {
            'nodes': nodes,
            'edges': edges
        }
    
    def generate_lld(self, graph_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate Low-Level Design diagram."""
        nodes = []
        edges = []
        
        # Create LLD nodes (all components)
        for node in graph_data['nodes']:
            if node['type'] == 'file':
                nodes.append({
                    'id': node['id'],
                    'label': node['label'],
                    'group': 'file',
                    'title': f"File: {node['label']}\nLanguage: {node['language']}"
                })
            elif node['type'] == 'class':
                nodes.append({
                    'id': node['id'],
                    'label': node['label'],
                    'group': 'class',
                    'title': f"Class: {node['label']}\nFile: {node['file']}"
                })
            elif node['type'] == 'function':
                nodes.append({
                    'id': node['id'],
                    'label': node['label'],
                    'group': 'function',
                    'title': f"Function: {node['label']}\nFile: {node['file']}"
                })
        
        # Create LLD edges (all relationships)
        for edge in graph_data['edges']:
            edges.append({
                'from': edge['from'],
                'to': edge['to'],
                'arrows': 'to',
                'label': edge['type'].lower()
            })
        
        return {
            'nodes': nodes,
            'edges': edges
        }

class ArchiMindWorkflow:
    """Main workflow orchestrator using LangGraph pattern."""
    
    def __init__(self):
        self.parser = CodeParserAgent()
        self.embedder = EmbeddingAgent()
        self.graph_agent = GraphAgent()
        self.diagram_agent = DiagramAgent()
    
    def run(self, repo_url: str) -> Dict[str, Any]:
        """Run the complete workflow."""
        try:
            logger.info(f"Starting workflow for repository: {repo_url}")
            
            # Step 1: Parse repository
            logger.info("Step 1: Parsing repository...")
            repo_data = self.parser.fetch_repository(repo_url)
            
            # Parse individual files
            parsed_files = []
            for file_data in repo_data['files']:
                try:
                    parsed_file = self.parser.parse_code_file(
                        file_data['path'], 
                        file_data['content']
                    )
                    parsed_files.append(parsed_file)
                except Exception as e:
                    logger.warning(f"Failed to parse file {file_data['path']}: {str(e)}")
                    continue
            
            # Step 2: Create embeddings
            logger.info("Step 2: Creating embeddings...")
            self.embedder.create_embeddings(parsed_files)
            
            # Step 3: Build graph
            logger.info("Step 3: Building graph...")
            graph_data = self.graph_agent.build_graph(parsed_files)
            
            # Step 4: Generate diagrams
            logger.info("Step 4: Generating diagrams...")
            hld = self.diagram_agent.generate_hld(graph_data)
            lld = self.diagram_agent.generate_lld(graph_data)
            
            return {
                'hld': hld,
                'lld': lld,
                'readme': repo_data['readme'],
                'statistics': graph_data['statistics'],
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"Workflow failed: {str(e)}")
            return {
                'error': str(e),
                'status': 'failed'
            }