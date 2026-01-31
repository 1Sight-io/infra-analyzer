#!/usr/bin/env python3
"""
Change Detector - Detects changed files and components from git diffs.
"""

import subprocess
import os
import re
import json
import yaml
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
        self._helm_charts_cache = None
        
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
    
    def detect_helm_changes(self, changed_files: List[str]) -> List[Dict]:
        """
        Detect changes to Helm charts.
        
        Args:
            changed_files: List of changed file paths
            
        Returns:
            List of changed Helm chart information
        """
        helm_changes = []
        helm_charts = self._find_helm_charts()
        
        for filepath in changed_files:
            file_path = Path(filepath)
            
            # Check if file is part of a Helm chart
            for chart_path in helm_charts:
                try:
                    # Check if file is within chart directory
                    relative = file_path.relative_to(chart_path)
                    
                    # Determine type of change
                    change_type = self._categorize_helm_change(relative)
                    
                    if change_type:
                        chart_name = self._get_chart_name(chart_path)
                        helm_changes.append({
                            'chart_path': str(chart_path),
                            'chart_name': chart_name,
                            'changed_file': filepath,
                            'relative_path': str(relative),
                            'change_type': change_type,
                            'severity': self._assess_helm_change_severity(change_type, relative)
                        })
                        break
                except ValueError:
                    # File is not relative to this chart
                    continue
        
        return helm_changes
    
    def _find_helm_charts(self) -> List[Path]:
        """Find all Helm charts in the repository."""
        if self._helm_charts_cache is not None:
            return self._helm_charts_cache
        
        charts = []
        
        # Walk through directories looking for Chart.yaml
        for root, dirs, files in os.walk(self.repo_path):
            # Skip hidden directories and common ignore patterns
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'venv', '__pycache__', '.git']]
            
            # Check if this directory has Chart.yaml
            if 'Chart.yaml' in files:
                charts.append(Path(root))
        
        self._helm_charts_cache = charts
        return charts
    
    def _get_chart_name(self, chart_path: Path) -> str:
        """Get chart name from Chart.yaml."""
        chart_yaml = chart_path / 'Chart.yaml'
        
        if chart_yaml.exists():
            try:
                with open(chart_yaml, 'r') as f:
                    data = yaml.safe_load(f)
                    return data.get('name', chart_path.name)
            except Exception:
                pass
        
        return chart_path.name
    
    def _categorize_helm_change(self, relative_path: Path) -> Optional[str]:
        """Categorize the type of Helm change."""
        path_str = str(relative_path)
        name = relative_path.name
        
        if name == 'Chart.yaml':
            return 'CHART_METADATA'
        elif name == 'values.yaml' or name.endswith('.values.yaml'):
            return 'VALUES'
        elif path_str.startswith('templates/'):
            # Categorize by resource type
            if 'deployment' in name.lower():
                return 'DEPLOYMENT_TEMPLATE'
            elif 'service' in name.lower():
                return 'SERVICE_TEMPLATE'
            elif 'ingress' in name.lower():
                return 'INGRESS_TEMPLATE'
            elif 'configmap' in name.lower():
                return 'CONFIGMAP_TEMPLATE'
            elif 'secret' in name.lower():
                return 'SECRET_TEMPLATE'
            else:
                return 'TEMPLATE'
        elif path_str.startswith('charts/'):
            return 'DEPENDENCY'
        
        return None
    
    def _assess_helm_change_severity(self, change_type: str, relative_path: Path) -> str:
        """Assess severity of Helm change."""
        severity_map = {
            'CHART_METADATA': 'MEDIUM',
            'VALUES': 'HIGH',
            'DEPLOYMENT_TEMPLATE': 'CRITICAL',
            'SERVICE_TEMPLATE': 'HIGH',
            'INGRESS_TEMPLATE': 'HIGH',
            'CONFIGMAP_TEMPLATE': 'MEDIUM',
            'SECRET_TEMPLATE': 'CRITICAL',
            'TEMPLATE': 'MEDIUM',
            'DEPENDENCY': 'HIGH',
        }
        
        return severity_map.get(change_type, 'MEDIUM')
