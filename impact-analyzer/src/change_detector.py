#!/usr/bin/env python3
"""
Change Detector - Detects changed files and components from git diffs.
"""

import subprocess
import os
import re
import json
from pathlib import Path
from typing import List, Dict, Set, Optional


class ChangeDetector:
    """Detects code changes from git diffs and maps them to components."""
    
    def __init__(self, repo_path: str = "."):
        """
        Initialize change detector.
        
        Args:
            repo_path: Path to git repository
        """
        self.repo_path = Path(repo_path).resolve()
        
    def get_changed_files(
        self, 
        base_ref: str = "origin/main", 
        head_ref: str = "HEAD",
        file_list: Optional[List[str]] = None
    ) -> Dict[str, List[str]]:
        """
        Get changed files from git diff.
        
        Args:
            base_ref: Base branch/commit (e.g., 'origin/main')
            head_ref: Head branch/commit (e.g., 'HEAD')
            file_list: Optional list of files (instead of git diff)
            
        Returns:
            Dictionary with modified, added, deleted files
        """
        if file_list:
            return {
                'modified': file_list,
                'added': [],
                'deleted': []
            }
        
        try:
            # Get diff with name-status
            result = subprocess.run(
                ['git', 'diff', '--name-status', f'{base_ref}...{head_ref}'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            
            changes = {
                'modified': [],
                'added': [],
                'deleted': []
            }
            
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                    
                parts = line.split('\t', 1)
                if len(parts) != 2:
                    continue
                    
                status, filepath = parts
                
                if status == 'M':
                    changes['modified'].append(filepath)
                elif status == 'A':
                    changes['added'].append(filepath)
                elif status == 'D':
                    changes['deleted'].append(filepath)
                elif status.startswith('R'):  # Renamed
                    # Format: R100\told_path\tnew_path
                    changes['modified'].append(filepath)
            
            return changes
            
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to get git diff: {e}")
            return {'modified': [], 'added': [], 'deleted': []}
    
    def detect_breaking_changes(self, changed_files: List[str]) -> List[Dict]:
        """
        Detect potential breaking changes by analyzing code.
        
        Args:
            changed_files: List of modified file paths
            
        Returns:
            List of detected breaking changes
        """
        breaking_changes = []
        
        for filepath in changed_files:
            full_path = self.repo_path / filepath
            
            if not full_path.exists():
                continue
            
            # Detect removed/changed API endpoints
            if filepath.endswith('.js') or filepath.endswith('.ts'):
                changes = self._analyze_javascript_changes(full_path)
                breaking_changes.extend(changes)
            elif filepath.endswith('.py'):
                changes = self._analyze_python_changes(full_path)
                breaking_changes.extend(changes)
        
        return breaking_changes
    
    def _analyze_javascript_changes(self, filepath: Path) -> List[Dict]:
        """Analyze JavaScript/TypeScript file for breaking changes."""
        breaking_changes = []
        
        try:
            content = filepath.read_text()
            
            # Look for Express/Fastify route definitions
            route_patterns = [
                r'app\.(get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]',
                r'router\.(get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]',
                r'fastify\.(get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]',
            ]
            
            endpoints = set()
            for pattern in route_patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    method = match.group(1).upper()
                    path = match.group(2)
                    endpoints.add(f"{method} {path}")
            
            if endpoints:
                # Note: To detect removals, we'd need to compare with previous version
                # For now, just flag that endpoints exist in this file
                breaking_changes.append({
                    'file': str(filepath.relative_to(self.repo_path)),
                    'type': 'API_ENDPOINTS_MODIFIED',
                    'endpoints': list(endpoints),
                    'severity': 'HIGH',
                    'message': f'File contains {len(endpoints)} API endpoint(s) that may be affected'
                })
        
        except Exception as e:
            print(f"Warning: Failed to analyze {filepath}: {e}")
        
        return breaking_changes
    
    def _analyze_python_changes(self, filepath: Path) -> List[Dict]:
        """Analyze Python file for breaking changes."""
        breaking_changes = []
        
        try:
            content = filepath.read_text()
            
            # Look for Flask/FastAPI route definitions
            route_patterns = [
                r'@app\.route\s*\(\s*[\'"]([^\'"]+)[\'"].*?methods\s*=\s*\[([^\]]+)\]',
                r'@app\.(get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]',
                r'@router\.(get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]',
            ]
            
            endpoints = set()
            for pattern in route_patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    if len(match.groups()) == 2 and match.group(1).startswith('/'):
                        # Flask @app.route with methods
                        path = match.group(1)
                        methods = match.group(2).replace("'", "").replace('"', '').split(',')
                        for method in methods:
                            endpoints.add(f"{method.strip().upper()} {path}")
                    else:
                        # Decorator with method in name
                        method = match.group(1).upper()
                        path = match.group(2)
                        endpoints.add(f"{method} {path}")
            
            if endpoints:
                breaking_changes.append({
                    'file': str(filepath.relative_to(self.repo_path)),
                    'type': 'API_ENDPOINTS_MODIFIED',
                    'endpoints': list(endpoints),
                    'severity': 'HIGH',
                    'message': f'File contains {len(endpoints)} API endpoint(s) that may be affected'
                })
        
        except Exception as e:
            print(f"Warning: Failed to analyze {filepath}: {e}")
        
        return breaking_changes
    
    def identify_affected_services(self, changed_files: List[str]) -> Set[str]:
        """
        Identify which services are affected by changed files.
        
        Args:
            changed_files: List of changed file paths
            
        Returns:
            Set of service names
        """
        services = set()
        
        for filepath in changed_files:
            # Extract service name from path patterns like:
            # services/user-service/...
            # apps/api-gateway/...
            # infrastructure/helm/product-service/...
            
            parts = Path(filepath).parts
            
            # Check for common patterns
            if len(parts) >= 2:
                if parts[0] in ['services', 'apps', 'microservices']:
                    services.add(parts[1])
                elif len(parts) >= 3 and parts[0] == 'infrastructure' and parts[1] == 'helm':
                    services.add(parts[2])
        
        return services
