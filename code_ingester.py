#!/usr/bin/env python3
"""
Code Ingester
Ingests code analysis results into Neo4j.
"""

import time
import logging
from typing import Dict, List, Optional
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


class CodeIngester:
    """Handles ingestion of code analysis results into Neo4j."""
    
    def __init__(self, uri: str, user: str, password: str):
        """
        Initialize Neo4j connection.
        
        Args:
            uri: Neo4j connection URI (e.g., bolt://localhost:7687)
            user: Neo4j username
            password: Neo4j password
        """
        self.uri = uri
        self.user = user
        self.password = password
        self.driver = None
        self.update_tag = int(time.time())
    
    def connect(self):
        """Connect to Neo4j."""
        try:
            # For secure connections, convert URI and disable SSL verification
            # This is useful for Neo4j Aura and self-signed certificates
            uri = self.uri
            driver_config = {}
            
            if self.uri.startswith(('bolt+s://', 'neo4j+s://')):
                # Convert secure URI to non-secure and manually configure encryption
                # This allows us to use TrustAll() for certificate validation
                from neo4j import TrustAll
                
                if self.uri.startswith('bolt+s://'):
                    uri = self.uri.replace('bolt+s://', 'bolt://')
                elif self.uri.startswith('neo4j+s://'):
                    uri = self.uri.replace('neo4j+s://', 'neo4j://')
                
                driver_config['encrypted'] = True
                driver_config['trusted_certificates'] = TrustAll()
                logger.info("Disabling SSL certificate verification for secure connection")
            
            self.driver = GraphDatabase.driver(
                uri,
                auth=(self.user, self.password),
                **driver_config
            )
            # Verify connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            logger.info(f"Connected to Neo4j at {self.uri}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise
    
    def close(self):
        """Close Neo4j connection."""
        if self.driver:
            self.driver.close()
    
    def ingest_code_module(self, module_data: Dict, repository_name: str = "unknown"):
        """
        Ingest a code module and its service calls.
        
        Args:
            module_data: Dictionary with 'path', 'name', 'language', 'service_calls'
            repository_name: Name of the repository
        """
        if not self.driver:
            raise RuntimeError("Not connected to Neo4j. Call connect() first.")
        
        if not module_data:
            return
        
        with self.driver.session() as session:
            # Create CodeModule node
            module_id = module_data['path']
            
            session.run("""
                MERGE (cm:CodeModule {id: $id})
                SET cm.path = $path,
                    cm.name = $name,
                    cm.language = $language,
                    cm.repository = $repository,
                    cm.firstseen = coalesce(cm.firstseen, $update_tag),
                    cm.lastupdated = $update_tag
            """, id=module_id,
                path=module_data['path'],
                name=module_data['name'],
                language=module_data['language'],
                repository=repository_name,
                update_tag=self.update_tag)
            
            # Create service call relationships
            for call in module_data.get('service_calls', []):
                self._create_service_call_relationship(session, module_id, call)
    
    def _create_service_call_relationship(self, session, module_id: str, call: Dict):
        """Create CALLS_SERVICE relationship between CodeModule and KubernetesService."""
        url = call.get('url', '')
        method = call.get('method', 'GET')
        
        if not url:
            return
        
        # Extract service name from URL
        service_name = self._extract_service_name(url)
        if not service_name:
            logger.debug(f"Could not extract service name from URL: {url}")
            return
        
        # Find matching KubernetesService nodes
        # Try exact match first, then substring match
        result = session.run("""
            MATCH (s:KubernetesService)
            WHERE s.name = $service_name
               OR s.name ENDS WITH $service_name_with_dash
               OR s.name = $service_name_with_dash
            RETURN s.id as id, s.name as name, s.namespace as namespace
            ORDER BY 
                CASE 
                    WHEN s.name = $service_name THEN 1
                    WHEN s.name ENDS WITH $service_name_with_dash THEN 2
                    ELSE 3
                END
            LIMIT 10
        """, service_name=service_name,
            service_name_with_dash=f"-{service_name}",
            service_name_dash=f"-{service_name}-")
        
        services = [record for record in result]
        
        # If no exact match, try broader search
        if not services:
            result = session.run("""
                MATCH (s:KubernetesService)
                WHERE s.name CONTAINS $service_name
                RETURN s.id as id, s.name as name, s.namespace as namespace
                LIMIT 5
            """, service_name=service_name)
            services = [record for record in result]
        
        if not services:
            logger.debug(f"No KubernetesService found for service name: {service_name} (from URL: {url})")
            return
        
        # Create relationships to all matching services
        for service_record in services:
            service_id = service_record['id']
            service_name_found = service_record['name']
            
            try:
                session.run("""
                    MATCH (cm:CodeModule {id: $module_id})
                    MATCH (s:KubernetesService {id: $service_id})
                    MERGE (cm)-[r:CALLS_SERVICE]->(s)
                    SET r.method = $method,
                        r.url = $url,
                        r.service_name_extracted = $service_name,
                        r.lastupdated = $update_tag
                """, module_id=module_id,
                    service_id=service_id,
                    method=method,
                    url=url,
                    service_name=service_name,
                    update_tag=self.update_tag)
                
                logger.debug(f"Created CALLS_SERVICE: {module_id} -> {service_name_found} (method: {method})")
            except Exception as e:
                logger.warning(f"Failed to create CALLS_SERVICE relationship: {e}")
                continue
    
    def _extract_service_name(self, url: str) -> Optional[str]:
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
            parts = url.split('.svc.cluster.local')[0].split('.')
            return parts[0] if parts else None
        
        # Parse URL
        try:
            # Add scheme if missing
            if not url.startswith(('http://', 'https://')):
                url = f'http://{url}'
            
            from urllib.parse import urlparse
            parsed = urlparse(url)
            hostname = parsed.hostname
            
            if not hostname:
                return None
            
            # Extract service name (remove port, get first part)
            service_name = hostname.split(':')[0]
            
            # For Kubernetes services, extract just the service name
            # Remove domain parts if present
            if '.' in service_name:
                service_name = service_name.split('.')[0]
            
            return service_name
        except Exception as e:
            logger.debug(f"Error parsing URL {url}: {e}")
            return None
    
    def link_to_helm_charts(self, codebase_path: str):
        """
        Link CodeModule nodes to HelmChart nodes if code is in chart directories.
        
        Args:
            codebase_path: Base path of the codebase
        """
        if not self.driver:
            raise RuntimeError("Not connected to Neo4j. Call connect() first.")
        
        logger.info("Linking CodeModule nodes to HelmChart nodes...")
        
        with self.driver.session() as session:
            # Get all CodeModule nodes
            result = session.run("""
                MATCH (cm:CodeModule)
                RETURN cm.id as id, cm.path as path
            """)
            
            modules = [record for record in result]
            
            # For each module, check if it's in a Helm chart directory
            # and try to match with HelmChart nodes
            linked_count = 0
            for module_record in modules:
                module_id = module_record['id']
                module_path = module_record['path']
                
                # Try to find matching HelmChart by path patterns
                # Common patterns: services/{service-name}/src/... or charts/{chart-name}/...
                chart_name = self._extract_chart_name_from_path(module_path)
                
                if chart_name:
                    # Try to find HelmChart with matching name
                    chart_result = session.run("""
                        MATCH (hc:HelmChart)
                        WHERE hc.name = $chart_name
                           OR hc.name CONTAINS $chart_name
                        RETURN hc.id as id, hc.name as name
                        LIMIT 1
                    """, chart_name=chart_name)
                    
                    chart_record = chart_result.single()
                    if chart_record:
                        chart_id = chart_record['id']
                        # Create CONTAINS_CODE relationship
                        session.run("""
                            MATCH (hc:HelmChart {id: $chart_id})
                            MATCH (cm:CodeModule {id: $module_id})
                            MERGE (hc)-[r:CONTAINS_CODE]->(cm)
                            SET r.lastupdated = $update_tag
                        """, chart_id=chart_id,
                            module_id=module_id,
                            update_tag=self.update_tag)
                        linked_count += 1
                        logger.debug(f"Linked CodeModule {module_id} to HelmChart {chart_record['name']}")
            
            logger.info(f"Linked {linked_count} CodeModule nodes to HelmChart nodes")
    
    def _extract_chart_name_from_path(self, path: str) -> Optional[str]:
        """Extract potential chart/service name from file path."""
        # Common patterns:
        # services/{service-name}/src/...
        # charts/{chart-name}/...
        # {service-name}/src/...
        
        import re
        patterns = [
            r'services/([^/]+)',
            r'charts/([^/]+)',
            r'([^/]+)/src/',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, path)
            if match:
                return match.group(1)
        
        return None
