#!/usr/bin/env python3
"""
Code Analyzer
Parses source code files to extract HTTP calls and service references.
"""

import ast
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class CodeAnalyzer:
    """Analyzes source code files to extract service calls."""
    
    def __init__(self, repository_name: str = "unknown"):
        """
        Initialize code analyzer.
        
        Args:
            repository_name: Name of the repository (for node identification)
        """
        self.repository_name = repository_name
        self.service_calls: List[Dict] = []
    
    def analyze_file(self, file_path: Path) -> Dict:
        """
        Analyze a source code file and extract service calls.
        
        Args:
            file_path: Path to the source file
            
        Returns:
            Dictionary containing extracted information:
            {
                'path': str,
                'name': str,
                'language': str,
                'service_calls': List[Dict]
            }
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.warning(f"File does not exist: {file_path}")
            return None
        
        # Determine language from extension
        language = self._detect_language(file_path)
        if not language:
            logger.debug(f"Skipping unsupported file: {file_path}")
            return None
        
        try:
            if language == 'python':
                return self._analyze_python_file(file_path)
            elif language == 'javascript':
                return self._analyze_javascript_file(file_path)
        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}", exc_info=True)
            return None
    
    def _detect_language(self, file_path: Path) -> Optional[str]:
        """Detect programming language from file extension."""
        ext = file_path.suffix.lower()
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'javascript',  # TypeScript - treat as JavaScript for now
            '.tsx': 'javascript',
        }
        return language_map.get(ext)
    
    def _analyze_python_file(self, file_path: Path) -> Dict:
        """Analyze Python file using AST."""
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                tree = ast.parse(f.read(), filename=str(file_path))
            except SyntaxError as e:
                logger.warning(f"Syntax error in {file_path}: {e}")
                return None
        
        visitor = PythonServiceCallVisitor(file_path)
        visitor.visit(tree)
        service_calls = visitor.service_calls
        
        return {
            'path': str(file_path),
            'name': file_path.name,
            'language': 'python',
            'service_calls': service_calls,
        }
    
    def _analyze_javascript_file(self, file_path: Path) -> Dict:
        """Analyze JavaScript file using regex patterns (basic approach)."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        service_calls = []
        visitor = JavaScriptServiceCallVisitor(file_path)
        visitor.analyze(content)
        service_calls = visitor.service_calls
        
        return {
            'path': str(file_path),
            'name': file_path.name,
            'language': 'javascript',
            'service_calls': service_calls,
        }
    
    def extract_service_name(self, url: str) -> Optional[str]:
        """
        Extract service name from URL.
        
        Examples:
            http://user-service:80/api/users -> user-service
            https://api.example.com -> api.example.com
            user-service.default.svc.cluster.local -> user-service
        """
        if not url:
            return None
        
        # Handle Kubernetes DNS format
        if '.svc.cluster.local' in url:
            # Extract service name (first part before .)
            parts = url.split('.svc.cluster.local')[0].split('.')
            return parts[0] if parts else None
        
        # Parse URL
        try:
            # Add scheme if missing
            if not url.startswith(('http://', 'https://')):
                url = f'http://{url}'
            
            parsed = urlparse(url)
            hostname = parsed.hostname
            
            if not hostname:
                return None
            
            # Extract service name (remove port, get first part)
            service_name = hostname.split(':')[0]
            
            # For Kubernetes services, often just the service name
            # Remove common prefixes/suffixes
            service_name = service_name.replace('-service', '').replace('_service', '')
            
            return service_name
        except Exception as e:
            logger.debug(f"Error parsing URL {url}: {e}")
            return None


class PythonServiceCallVisitor(ast.NodeVisitor):
    """AST visitor to extract HTTP calls from Python code."""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.service_calls: List[Dict] = []
        # Track variable assignments for environment variables
        self.env_vars: Dict[str, str] = {}
    
    def visit_Call(self, node):
        """Visit function calls."""
        # Check for requests library calls
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                module_name = node.func.value.id
                method_name = node.func.value.id if not hasattr(node.func, 'attr') else node.func.attr
                
                # requests.get(), requests.post(), etc.
                if module_name == 'requests' and node.func.attr in ['get', 'post', 'put', 'delete', 'patch']:
                    self._extract_requests_call(node, method_name)
                
                # httpx.get(), httpx.post(), etc.
                elif module_name == 'httpx' and node.func.attr in ['get', 'post', 'put', 'delete', 'patch']:
                    self._extract_requests_call(node, method_name)
                
                # urllib.request.urlopen()
                elif module_name == 'urllib' and hasattr(node.func, 'attr') and node.func.attr == 'urlopen':
                    self._extract_urlopen_call(node)
        
        # Check for http.client calls
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Attribute):
                if (isinstance(node.func.value.value, ast.Name) and 
                    node.func.value.value.id == 'http' and
                    node.func.value.attr == 'client' and
                    node.func.attr in ['HTTPConnection', 'HTTPSConnection']):
                    self._extract_http_connection_call(node)
        
        self.generic_visit(node)
    
    def visit_Assign(self, node):
        """Track environment variable assignments."""
        # Look for os.environ or os.getenv patterns
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target_name = node.targets[0].id
            # Store for later use (simplified - could be improved)
            if isinstance(node.value, ast.Call):
                if (isinstance(node.value.func, ast.Attribute) and
                    isinstance(node.value.func.value, ast.Name) and
                    node.value.func.value.id == 'os' and
                    node.value.func.attr == 'getenv'):
                    # os.getenv('VAR_NAME')
                    if node.value.args and isinstance(node.value.args[0], ast.Constant):
                        env_var_name = node.value.args[0].value
                        self.env_vars[target_name] = env_var_name
        
        self.generic_visit(node)
    
    def _extract_requests_call(self, node, method: str):
        """Extract URL from requests library call."""
        if not node.args:
            return
        
        # First argument is usually the URL
        url_arg = node.args[0]
        url = self._extract_string_value(url_arg)
        
        if url:
            self.service_calls.append({
                'method': method.upper(),
                'url': url,
                'line': node.lineno,
            })
    
    def _extract_urlopen_call(self, node):
        """Extract URL from urllib.request.urlopen() call."""
        if not node.args:
            return
        
        url_arg = node.args[0]
        url = self._extract_string_value(url_arg)
        
        if url:
            self.service_calls.append({
                'method': 'GET',  # urlopen defaults to GET
                'url': url,
                'line': node.lineno,
            })
    
    def _extract_http_connection_call(self, node):
        """Extract hostname from http.client connection call."""
        if not node.args:
            return
        
        hostname_arg = node.args[0]
        hostname = self._extract_string_value(hostname_arg)
        
        if hostname:
            self.service_calls.append({
                'method': 'HTTP',
                'url': f'http://{hostname}',
                'line': node.lineno,
            })
    
    def _extract_string_value(self, node) -> Optional[str]:
        """Extract string value from AST node."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        elif isinstance(node, ast.Str):  # Python < 3.8
            return node.s
        elif isinstance(node, ast.Name):
            # Variable reference - could look up in env_vars, but simplified for now
            return None
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            # String concatenation
            left = self._extract_string_value(node.left)
            right = self._extract_string_value(node.right)
            if left and right:
                return left + right
        return None


class JavaScriptServiceCallVisitor:
    """Extracts HTTP calls from JavaScript code using regex patterns."""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.service_calls: List[Dict] = []
        self.env_vars: Dict[str, str] = {}  # Track environment variables
    
    def analyze(self, content: str):
        """Analyze JavaScript content for service calls."""
        lines = content.split('\n')
        
        # First pass: extract environment variables with URLs
        # Pattern: const VAR_NAME = process.env.VAR_NAME || 'http://...'
        env_var_pattern = re.compile(
            r'(?:const|let|var)\s+(\w+_SERVICE_URL|\w+_API_URL|\w+_URL)\s*=\s*process\.env\.\1\s*\|\|\s*["\']([^"\']+)["\']',
            re.IGNORECASE
        )
        for line_num, line in enumerate(lines, 1):
            for match in env_var_pattern.finditer(line):
                var_name = match.group(1)
                url = match.group(2)
                self.env_vars[var_name] = url
                # Also add as a service call if it looks like a service URL
                if self._looks_like_service_url(url):
                    self.service_calls.append({
                        'method': 'HTTP',
                        'url': url,
                        'line': line_num,
                        'source': f'env_var_{var_name}',
                    })
        
        # Pattern for fetch() calls
        fetch_pattern = re.compile(r'fetch\s*\(\s*["\']([^"\']+)["\']', re.IGNORECASE)
        
        # Pattern for axios.get(), axios.post(), etc.
        axios_pattern = re.compile(r'axios\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']', re.IGNORECASE)
        
        # Pattern for http.request() or http.get() with string URL
        http_pattern = re.compile(r'http\.(request|get|post)\s*\(\s*["\']([^"\']+)["\']', re.IGNORECASE)
        
        # Pattern for http.request() with options object containing hostname
        # This handles multi-line patterns better
        http_options_hostname_pattern = re.compile(
            r'http\.(request|get|post)\s*\(\s*\{[^}]*hostname\s*:\s*["\']([^"\']+)["\']',
            re.IGNORECASE | re.DOTALL
        )
        
        # Pattern for variable references that might be env vars
        var_ref_pattern = re.compile(r'(\w+_SERVICE_URL|\w+_API_URL)', re.IGNORECASE)
        
        for line_num, line in enumerate(lines, 1):
            # Check fetch()
            for match in fetch_pattern.finditer(line):
                url = match.group(1)
                self.service_calls.append({
                    'method': 'GET',
                    'url': url,
                    'line': line_num,
                })
            
            # Check axios
            for match in axios_pattern.finditer(line):
                method = match.group(1).upper()
                url = match.group(2)
                self.service_calls.append({
                    'method': method,
                    'url': url,
                    'line': line_num,
                })
            
            # Check http.request/get/post with string URL
            for match in http_pattern.finditer(line):
                method = match.group(1).upper()
                url = match.group(2)
                self.service_calls.append({
                    'method': method,
                    'url': url,
                    'line': line_num,
                })
            
            # Check http.request with options object (hostname)
            for match in http_options_hostname_pattern.finditer(line):
                method = match.group(1).upper()
                hostname = match.group(2)
                self.service_calls.append({
                    'method': method,
                    'url': f'http://{hostname}',
                    'line': line_num,
                })
            
            # Check for variable references that match our env vars
            for match in var_ref_pattern.finditer(line):
                var_name = match.group(1)
                if var_name in self.env_vars:
                    url = self.env_vars[var_name]
                    self.service_calls.append({
                        'method': 'HTTP',
                        'url': url,
                        'line': line_num,
                        'source': f'env_var_{var_name}',
                    })
    
    def _looks_like_service_url(self, url: str) -> bool:
        """Check if URL looks like a service URL (not localhost, etc.)."""
        if not url:
            return False
        
        # Skip localhost, 127.0.0.1, etc.
        skip_patterns = ['localhost', '127.0.0.1', '0.0.0.0', '::1']
        url_lower = url.lower()
        
        for pattern in skip_patterns:
            if pattern in url_lower:
                return False
        
        # Check if it contains a service-like pattern (e.g., contains "-service" or looks like k8s service)
        if '-service' in url_lower or '.svc.' in url_lower or 'http://' in url_lower or 'https://' in url_lower:
            return True
        
        return False
