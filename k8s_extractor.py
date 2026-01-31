#!/usr/bin/env python3
"""
Kubernetes Resource Extractor
Extracts entities and relationships from Kubernetes resources.
"""

import json
import re
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)


class K8sResourceExtractor:
    """Extracts entities and relationships from Kubernetes resources."""
    
    def __init__(self, chart_name: str, chart_version: str, chart_path: str):
        self.chart_name = chart_name
        self.chart_version = chart_version
        self.chart_path = chart_path
        self.pods: List[Dict] = []
        self.services: List[Dict] = []
        self.ingresses: List[Dict] = []
        self.service_accounts: List[Dict] = []
        self.namespaces: Set[str] = set()
        
    def extract_resources(self, resources: List[Dict]) -> Dict:
        """
        Extract all entities and relationships from Kubernetes resources.
        
        Args:
            resources: List of Kubernetes resource dictionaries
            
        Returns:
            Dictionary containing extracted entities and relationships
        """
        # First pass: extract all resources
        for resource in resources:
            kind = resource.get('kind', '')
            metadata = resource.get('metadata', {})
            
            if kind == 'Deployment':
                self._extract_deployment(resource)
            elif kind == 'Service':
                self._extract_service(resource)
            elif kind == 'Ingress':
                self._extract_ingress(resource)
            elif kind == 'ServiceAccount':
                self._extract_service_account(resource)
            elif kind == 'Namespace':
                namespace_name = metadata.get('name', 'default')
                self.namespaces.add(namespace_name)
        
        # Second pass: extract relationships
        relationships = self._extract_relationships()
        
        return {
            'pods': self.pods,
            'services': self.services,
            'ingresses': self.ingresses,
            'service_accounts': self.service_accounts,
            'namespaces': list(self.namespaces),
            'relationships': relationships,
        }
    
    def _extract_deployment(self, deployment: Dict):
        """Extract pod information from Deployment."""
        metadata = deployment.get('metadata', {})
        spec = deployment.get('spec', {})
        template = spec.get('template', {})
        template_spec = template.get('spec', {})
        template_metadata = template.get('metadata', {})
        
        pod_name = metadata.get('name', '')
        namespace = metadata.get('namespace', 'default')
        self.namespaces.add(namespace)
        
        replicas = spec.get('replicas', 1)
        labels = template_metadata.get('labels', {})
        service_account_name = template_spec.get('serviceAccountName', '')
        
        containers = template_spec.get('containers', [])
        images = []
        
        for container in containers:
            image = container.get('image', '')
            if image:
                images.append(image)
        
        # Create pod entity for each container (or one pod with multiple images)
        pod = {
            'id': f"{namespace}/{pod_name}",
            'name': pod_name,
            'namespace': namespace,
            'labels': json.dumps(labels),
            'replicas': replicas,
            'images': images,
            'service_account_name': service_account_name,
            'chart_name': self.chart_name,
            'chart_version': self.chart_version,
            'chart_path': self.chart_path,
        }
        
        self.pods.append(pod)
    
    def _extract_service(self, service: Dict):
        """Extract service information."""
        metadata = service.get('metadata', {})
        spec = service.get('spec', {})
        
        service_name = metadata.get('name', '')
        namespace = metadata.get('namespace', 'default')
        self.namespaces.add(namespace)
        
        service_type = spec.get('type', 'ClusterIP')
        selector = spec.get('selector', {})
        ports = spec.get('ports', [])
        cluster_ip = spec.get('clusterIP', '')
        
        service_data = {
            'id': f"{namespace}/{service_name}",
            'name': service_name,
            'namespace': namespace,
            'type': service_type,
            'selector': json.dumps(selector),
            'ports': json.dumps(ports),
            'cluster_ip': cluster_ip,
            'chart_name': self.chart_name,
            'chart_version': self.chart_version,
            'chart_path': self.chart_path,
        }
        
        self.services.append(service_data)
    
    def _extract_ingress(self, ingress: Dict):
        """Extract ingress information."""
        metadata = ingress.get('metadata', {})
        spec = ingress.get('spec', {})
        
        ingress_name = metadata.get('name', '')
        namespace = metadata.get('namespace', 'default')
        self.namespaces.add(namespace)
        
        rules = spec.get('rules', [])
        hosts = []
        paths = []
        backend_services = []
        
        for rule in rules:
            host = rule.get('host', '')
            if host:
                hosts.append(host)
            
            http_paths = rule.get('http', {}).get('paths', [])
            for path_obj in http_paths:
                path = path_obj.get('path', '/')
                paths.append(path)
                
                backend = path_obj.get('backend', {})
                service = backend.get('service', {})
                service_name = service.get('name', '')
                if service_name:
                    backend_services.append({
                        'name': service_name,
                        'port': service.get('port', {}).get('number', 80),
                    })
        
        ingress_data = {
            'id': f"{namespace}/{ingress_name}",
            'name': ingress_name,
            'namespace': namespace,
            'hosts': json.dumps(hosts),
            'paths': json.dumps(paths),
            'backend_services': backend_services,
            'chart_name': self.chart_name,
            'chart_version': self.chart_version,
            'chart_path': self.chart_path,
        }
        
        self.ingresses.append(ingress_data)
    
    def _extract_service_account(self, service_account: Dict):
        """Extract service account information."""
        metadata = service_account.get('metadata', {})
        
        sa_name = metadata.get('name', '')
        namespace = metadata.get('namespace', 'default')
        self.namespaces.add(namespace)
        
        sa_data = {
            'id': f"{namespace}/{sa_name}",
            'name': sa_name,
            'namespace': namespace,
            'chart_name': self.chart_name,
            'chart_version': self.chart_version,
            'chart_path': self.chart_path,
        }
        
        self.service_accounts.append(sa_data)
    
    def _extract_relationships(self) -> Dict:
        """Extract relationships between entities."""
        relationships = {
            'pod_to_image': [],
            'pod_to_service_account': [],
            'service_to_pod': [],
            'ingress_to_service': [],
            'service_to_service': [],  # From env vars
        }
        
        # Pod to Image relationships
        for pod in self.pods:
            pod_id = pod['id']
            for image in pod.get('images', []):
                image_id = self._parse_image_id(image)
                relationships['pod_to_image'].append({
                    'pod_id': pod_id,
                    'image_id': image_id,
                    'image_full': image,
                })
        
        # Pod to ServiceAccount relationships
        for pod in self.pods:
            pod_id = pod['id']
            sa_name = pod.get('service_account_name', '')
            if sa_name:
                namespace = pod['namespace']
                sa_id = f"{namespace}/{sa_name}"
                relationships['pod_to_service_account'].append({
                    'pod_id': pod_id,
                    'service_account_id': sa_id,
                })
        
        # Service to Pod relationships (via selectors)
        for service in self.services:
            service_id = service['id']
            selector = json.loads(service.get('selector', '{}'))
            
            # Match pods by labels
            for pod in self.pods:
                pod_labels = json.loads(pod.get('labels', '{}'))
                if self._labels_match(selector, pod_labels) and pod['namespace'] == service['namespace']:
                    relationships['service_to_pod'].append({
                        'service_id': service_id,
                        'pod_id': pod['id'],
                    })
        
        # Ingress to Service relationships
        for ingress in self.ingresses:
            ingress_id = ingress['id']
            namespace = ingress['namespace']
            
            for backend_service in ingress.get('backend_services', []):
                service_name = backend_service['name']
                service_id = f"{namespace}/{service_name}"
                relationships['ingress_to_service'].append({
                    'ingress_id': ingress_id,
                    'service_id': service_id,
                })
        
        # Service to Service relationships (from env vars in pods)
        # Extract from pod env vars
        for pod in self.pods:
            # We need to look at the original deployment spec for env vars
            # For now, we'll extract from values.yaml if available
            # This is a simplified approach - in practice, we'd need to parse
            # the rendered deployment spec more carefully
            pass
        
        return relationships
    
    def _parse_image_id(self, image: str) -> str:
        """Parse image string to extract ID (repository:tag or digest)."""
        # Handle digest format: repo@sha256:digest
        if '@' in image:
            return image
        
        # Handle tag format: repo:tag
        if ':' in image:
            return image
        
        # Default: add latest tag
        return f"{image}:latest"
    
    def _labels_match(self, selector: Dict, labels: Dict) -> bool:
        """Check if selector matches labels."""
        if not selector:
            return False
        
        for key, value in selector.items():
            if key not in labels or labels[key] != value:
                return False
        
        return True
    
    def extract_service_connections_from_env(self, values: Dict) -> List[Dict]:
        """
        Extract service-to-service connections from environment variables.
        
        Args:
            values: Helm values dictionary
            
        Returns:
            List of service connection dictionaries
        """
        connections = []
        env_vars = values.get('env', {})
        
        # Pattern to match service URLs: http://service-name:port or service-name:port
        service_url_pattern = re.compile(r'(?:https?://)?([a-zA-Z0-9-]+)(?::(\d+))?')
        
        # Use chart name with hyphens (e.g., "api-gateway" not "apigateway")
        source_service_name = self.chart_name
        
        for key, value in env_vars.items():
            if isinstance(value, str):
                # Look for service URLs in env vars
                matches = service_url_pattern.findall(value)
                for service_name, port in matches:
                    # Skip common non-service patterns
                    if service_name.lower() in ['localhost', '127.0.0.1', '0.0.0.0', 'http', 'https']:
                        continue
                    
                    connections.append({
                        'source_service': source_service_name,
                        'target_service': service_name,
                        'env_var': key,
                        'url': value,
                        'chart_name': self.chart_name,  # Add chart name for matching
                    })
        
        return connections
