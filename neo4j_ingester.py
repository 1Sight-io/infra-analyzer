#!/usr/bin/env python3
"""
Neo4j Ingester
Ingests extracted Kubernetes entities and relationships into Neo4j.
"""

import json
import time
from typing import Dict, List, Optional
import logging
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


class Neo4jIngester:
    """Handles ingestion of Kubernetes resources into Neo4j."""
    
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
    
    def resolve_all_service_connections(self):
        """
        Resolve all service connections by finding services that reference other services
        via environment variables but don't have CONNECTS_TO relationships yet.
        This should be called after all charts are ingested.
        """
        if not self.driver:
            raise RuntimeError("Not connected to Neo4j. Call connect() first.")
        
        logger.info("Resolving all service connections...")
        
        with self.driver.session() as session:
            # Find all HelmChart nodes and their service connections from env vars
            # We'll need to re-extract connections from stored data or query by chart relationships
            # For now, let's query for services that might need connections based on their chart
            
            # Get all charts and try to match services
            charts_result = session.run("""
                MATCH (hc:HelmChart)
                RETURN hc.name as chart_name, hc.id as chart_id
            """)
            
            resolved_count = 0
            for chart_record in charts_result:
                chart_name = chart_record['chart_name']
                
                # Find services from this chart
                services_result = session.run("""
                    MATCH (hc:HelmChart {name: $chart_name})-[:BELONGS_TO_CHART]->(s:KubernetesService)
                    RETURN s.id as service_id, s.name as service_name, s.namespace as namespace
                """, chart_name=chart_name)
                
                # Try to find connections by matching service names
                # This is a fallback - ideally we'd store the env vars, but for now we'll use heuristics
                for service_record in services_result:
                    service_name = service_record['service_name']
                    # Common service name patterns that might indicate connections
                    # This is a simplified approach
                    pass
            
            logger.info(f"Resolved {resolved_count} additional service connections")
    
    def close(self):
        """Close Neo4j connection."""
        if self.driver:
            self.driver.close()
    
    def ingest_chart(self, chart_metadata: Dict, extracted_data: Dict, service_connections: List[Dict]):
        """
        Ingest a Helm chart's resources into Neo4j.
        
        Args:
            chart_metadata: Chart metadata from Chart.yaml
            extracted_data: Extracted entities and relationships
            service_connections: Service-to-service connections from env vars
        """
        if not self.driver:
            raise RuntimeError("Not connected to Neo4j. Call connect() first.")
        
        with self.driver.session() as session:
            # Create HelmChart node
            chart_id = chart_metadata.get('name', 'unknown')
            chart_path = extracted_data.get('chart_path', '')
            
            session.run("""
                MERGE (hc:HelmChart {id: $chart_id})
                SET hc.name = $name,
                    hc.version = $version,
                    hc.app_version = $app_version,
                    hc.path = $path,
                    hc.firstseen = coalesce(hc.firstseen, $update_tag),
                    hc.lastupdated = $update_tag
            """, chart_id=chart_id,
                name=chart_metadata.get('name', ''),
                version=chart_metadata.get('version', ''),
                app_version=chart_metadata.get('appVersion', ''),
                path=chart_path,
                update_tag=self.update_tag)
            
            # Ingest namespaces
            for namespace_name in extracted_data.get('namespaces', []):
                self._ingest_namespace(session, namespace_name, chart_id)
            
            # Ingest images
            image_map = {}
            for pod in extracted_data.get('pods', []):
                for image_full in pod.get('images', []):
                    image_id = self._parse_image_id(image_full)
                    if image_id not in image_map:
                        image_map[image_id] = image_full
                        self._ingest_image(session, image_id, image_full)
            
            # Ingest service accounts
            for sa in extracted_data.get('service_accounts', []):
                self._ingest_service_account(session, sa, chart_id)
            
            # Skip pod ingestion - Pods are created by Cartography from actual cluster state
            # Instead, we'll link to existing Pods from Cartography
            logger.info("Skipping pod ingestion - Pods should come from Cartography's cluster state")
            
            # Ingest services
            for service in extracted_data.get('services', []):
                self._ingest_service(session, service, chart_id)
            
            # Ingest ingresses
            for ingress in extracted_data.get('ingresses', []):
                self._ingest_ingress(session, ingress, chart_id)
            
            # Create relationships
            relationships = extracted_data.get('relationships', {})
            
            # Pod to Image (link to existing Pods from Cartography)
            for rel in relationships.get('pod_to_image', []):
                self._link_pod_image_relationship(session, rel)
            
            # Pod to ServiceAccount (link to existing Pods from Cartography)
            for rel in relationships.get('pod_to_service_account', []):
                self._link_pod_service_account_relationship(session, rel)
            
            # Service to Pod (link to existing Pods from Cartography)
            for rel in relationships.get('service_to_pod', []):
                self._link_service_pod_relationship(session, rel)
            
            # Link HelmChart to existing Pods from Cartography
            self._link_chart_to_existing_pods(session, chart_id, extracted_data)
            
            # Ingress to Service
            for rel in relationships.get('ingress_to_service', []):
                self._create_ingress_service_relationship(session, rel)
            
            # Service to Service (from env vars)
            for conn in service_connections:
                self._create_service_service_relationship(session, conn, extracted_data)
            
            # Link resources to HelmChart
            self._link_resources_to_chart(session, chart_id, extracted_data)
            
            # Link resources to namespaces
            self._link_resources_to_namespaces(session, extracted_data)
            
            # Try to link to existing infrastructure (EKSCluster, ECRImage)
            self._link_to_infrastructure(session, extracted_data)
    
    def _ingest_namespace(self, session, namespace_name: str, chart_id: str):
        """Ingest KubernetesNamespace node."""
        namespace_id = namespace_name
        
        session.run("""
            MERGE (ns:KubernetesNamespace {id: $id})
            SET ns.name = $name,
                ns.firstseen = coalesce(ns.firstseen, $update_tag),
                ns.lastupdated = $update_tag
        """, id=namespace_id,
            name=namespace_name,
            update_tag=self.update_tag)
    
    def _ingest_image(self, session, image_id: str, image_full: str):
        """Ingest Image node."""
        # Parse image into repository and tag
        repository, tag = self._parse_image_repo_tag(image_full)
        
        session.run("""
            MERGE (img:Image {id: $id})
            SET img.repository = $repository,
                img.tag = $tag,
                img.full_name = $full_name,
                img.firstseen = coalesce(img.firstseen, $update_tag),
                img.lastupdated = $update_tag
        """, id=image_id,
            repository=repository,
            tag=tag,
            full_name=image_full,
            update_tag=self.update_tag)
    
    # Note: _ingest_pod method removed - Pods are created by Cartography from actual cluster state
    # We link to existing Pods instead of creating new ones
    
    def _ingest_service(self, session, service: Dict, chart_id: str):
        """Ingest KubernetesService node."""
        service_id = service['id']
        
        session.run("""
            MERGE (s:KubernetesService {id: $id})
            SET s.name = $name,
                s.namespace = $namespace,
                s.type = $type,
                s.ports = $ports,
                s.selector = $selector,
                s.cluster_ip = $cluster_ip,
                s.chart_name = $chart_name,
                s.firstseen = coalesce(s.firstseen, $update_tag),
                s.lastupdated = $update_tag
        """, id=service_id,
            name=service['name'],
            namespace=service['namespace'],
            type=service.get('type', 'ClusterIP'),
            ports=service.get('ports', '[]'),
            selector=service.get('selector', '{}'),
            cluster_ip=service.get('cluster_ip', ''),
            chart_name=service.get('chart_name', ''),
            update_tag=self.update_tag)
    
    def _ingest_ingress(self, session, ingress: Dict, chart_id: str):
        """Ingest KubernetesIngress node."""
        ingress_id = ingress['id']
        
        session.run("""
            MERGE (ing:KubernetesIngress {id: $id})
            SET ing.name = $name,
                ing.namespace = $namespace,
                ing.hosts = $hosts,
                ing.paths = $paths,
                ing.chart_name = $chart_name,
                ing.firstseen = coalesce(ing.firstseen, $update_tag),
                ing.lastupdated = $update_tag
        """, id=ingress_id,
            name=ingress['name'],
            namespace=ingress['namespace'],
            hosts=ingress.get('hosts', '[]'),
            paths=ingress.get('paths', '[]'),
            chart_name=ingress.get('chart_name', ''),
            update_tag=self.update_tag)
    
    def _ingest_service_account(self, session, sa: Dict, chart_id: str):
        """Ingest KubernetesServiceAccount node."""
        sa_id = sa['id']
        
        session.run("""
            MERGE (sa:KubernetesServiceAccount {id: $id})
            SET sa.name = $name,
                sa.namespace = $namespace,
                sa.firstseen = coalesce(sa.firstseen, $update_tag),
                sa.lastupdated = $update_tag
        """, id=sa_id,
            name=sa['name'],
            namespace=sa['namespace'],
            update_tag=self.update_tag)
    
    def _link_pod_image_relationship(self, session, rel: Dict):
        """Link existing Pod from Cartography to Image."""
        # Extract namespace and name from pod_id (format: "namespace/name")
        pod_id = rel['pod_id']
        if '/' in pod_id:
            namespace, name = pod_id.split('/', 1)
        else:
            logger.warning(f"Unexpected pod_id format: {pod_id}")
            return
        
        # Find existing Pod from Cartography by namespace and name
        # Cartography Pod IDs might include cluster name, so we match by namespace and name
        session.run("""
            MATCH (p:KubernetesPod)
            WHERE p.namespace = $namespace AND p.name = $name
            MATCH (img:Image {id: $image_id})
            MERGE (p)-[r:USES_IMAGE]->(img)
            SET r.lastupdated = $update_tag
        """, namespace=namespace,
            name=name,
            image_id=rel['image_id'],
            update_tag=self.update_tag)
    
    def _link_pod_service_account_relationship(self, session, rel: Dict):
        """Link existing Pod from Cartography to ServiceAccount."""
        pod_id = rel['pod_id']
        if '/' in pod_id:
            namespace, name = pod_id.split('/', 1)
        else:
            logger.warning(f"Unexpected pod_id format: {pod_id}")
            return
        
        # Find existing Pod and ServiceAccount
        session.run("""
            MATCH (p:KubernetesPod)
            WHERE p.namespace = $namespace AND p.name = $name
            MATCH (sa:KubernetesServiceAccount {id: $sa_id})
            MERGE (p)-[r:USES_SERVICE_ACCOUNT]->(sa)
            SET r.lastupdated = $update_tag
        """, namespace=namespace,
            name=name,
            sa_id=rel['service_account_id'],
            update_tag=self.update_tag)
    
    def _link_service_pod_relationship(self, session, rel: Dict):
        """Link Service to existing Pod from Cartography."""
        pod_id = rel['pod_id']
        if '/' in pod_id:
            namespace, name = pod_id.split('/', 1)
        else:
            logger.warning(f"Unexpected pod_id format: {pod_id}")
            return
        
        # Find existing Pod from Cartography
        session.run("""
            MATCH (s:KubernetesService {id: $service_id})
            MATCH (p:KubernetesPod)
            WHERE p.namespace = $namespace AND p.name = $name
            MERGE (s)-[r:TARGETS]->(p)
            SET r.lastupdated = $update_tag
        """, service_id=rel['service_id'],
            namespace=namespace,
            name=name,
            update_tag=self.update_tag)
    
    def _create_ingress_service_relationship(self, session, rel: Dict):
        """Create EXPOSED_VIA relationship (Service → Ingress, meaning Service is exposed via Ingress)."""
        session.run("""
            MATCH (s:KubernetesService {id: $service_id})
            MATCH (ing:KubernetesIngress {id: $ingress_id})
            MERGE (s)-[r:EXPOSED_VIA]->(ing)
            SET r.lastupdated = $update_tag
        """, service_id=rel['service_id'],
            ingress_id=rel['ingress_id'],
            update_tag=self.update_tag)
    
    def _create_service_service_relationship(self, session, conn: Dict, extracted_data: Dict):
        """Create CONNECTS_TO relationship (Service → Service)."""
        chart_name = conn.get('chart_name', '')
        target_service_name = conn['target_service']
        
        # Find source service from current chart's services
        source_services = extracted_data.get('services', [])
        
        # If no services found in current chart, try to find by chart name in Neo4j
        if not source_services and chart_name:
            result = session.run("""
                MATCH (hc:HelmChart {name: $chart_name})-[:BELONGS_TO_CHART]->(s:KubernetesService)
                RETURN s.id as id, s.name as name, s.namespace as namespace
            """, chart_name=chart_name)
            source_services = [{'id': record['id'], 'name': record['name'], 'namespace': record['namespace']} 
                             for record in result]
        
        # If still no source services, try matching by chart name pattern
        if not source_services and chart_name:
            # Try to match service name that contains chart name
            result = session.run("""
                MATCH (s:KubernetesService)
                WHERE s.name CONTAINS $chart_name OR s.chart_name = $chart_name
                RETURN s.id as id, s.name as name, s.namespace as namespace
                LIMIT 10
            """, chart_name=chart_name)
            source_services = [{'id': record['id'], 'name': record['name'], 'namespace': record['namespace']} 
                             for record in result]
        
        # Find target service in Neo4j (could be from any chart, already ingested)
        # Kubernetes service DNS names can be just the service name or include release prefix
        # Match by: exact name, ends with "-service-name", or contains "service-name"
        target_services_result = session.run("""
            MATCH (s:KubernetesService)
            WHERE s.name = $service_name 
               OR s.name ENDS WITH $service_name_with_dash
               OR s.name = $service_name_with_dash
               OR (s.name CONTAINS $service_name AND s.name CONTAINS $service_name_dash)
            RETURN s.id as id, s.name as name, s.namespace as namespace
            ORDER BY 
                CASE 
                    WHEN s.name = $service_name THEN 1
                    WHEN s.name ENDS WITH $service_name_with_dash THEN 2
                    ELSE 3
                END
            LIMIT 10
        """, service_name=target_service_name,
            service_name_with_dash=f"-{target_service_name}",
            service_name_dash=f"-{target_service_name}-")
        target_services = [{'id': record['id'], 'name': record['name'], 'namespace': record['namespace']} 
                          for record in target_services_result]
        
        # If still no match, try broader search (service name might be part of a longer name)
        if not target_services:
            target_services_result = session.run("""
                MATCH (s:KubernetesService)
                WHERE s.name CONTAINS $service_name
                RETURN s.id as id, s.name as name, s.namespace as namespace
                LIMIT 5
            """, service_name=target_service_name)
            target_services = [{'id': record['id'], 'name': record['name'], 'namespace': record['namespace']} 
                              for record in target_services_result]
        
        # Log what we found
        if not source_services:
            logger.warning(f"No source service found for chart '{chart_name}' when creating CONNECTS_TO to '{target_service_name}'")
        if not target_services:
            logger.warning(f"Target service '{target_service_name}' not found in Neo4j (may not be ingested yet)")
        
        # Create relationships
        created_count = 0
        for source_service in source_services:
            source_id = source_service['id']
            source_name = source_service.get('name', source_id)
            
            for target_service in target_services:
                target_id = target_service['id']
                target_name = target_service.get('name', target_id)
                
                if source_id != target_id:
                    try:
                        session.run("""
                            MATCH (s1:KubernetesService {id: $source_id})
                            MATCH (s2:KubernetesService {id: $target_id})
                            MERGE (s1)-[r:CONNECTS_TO]->(s2)
                            SET r.env_var = $env_var,
                                r.url = $url,
                                r.lastupdated = $update_tag
                        """, source_id=source_id,
                            target_id=target_id,
                            env_var=conn['env_var'],
                            url=conn['url'],
                            update_tag=self.update_tag)
                        created_count += 1
                        logger.debug(f"Created CONNECTS_TO: {source_name} -> {target_name} (via {conn['env_var']})")
                    except Exception as e:
                        logger.warning(f"Failed to create CONNECTS_TO relationship from {source_id} to {target_id}: {e}")
                        continue
        
        if created_count == 0 and source_services and target_services:
            logger.warning(f"Could not create CONNECTS_TO relationship despite finding services. Source: {source_services}, Target: {target_services}")
    
    def _link_resources_to_chart(self, session, chart_id: str, extracted_data: Dict):
        """Link all resources to HelmChart."""
        # Skip pods - they will be linked via _link_chart_to_existing_pods
        
        # Link services
        for service in extracted_data.get('services', []):
            session.run("""
                MATCH (hc:HelmChart {id: $chart_id})
                MATCH (s:KubernetesService {id: $service_id})
                MERGE (hc)-[r:BELONGS_TO_CHART]->(s)
                SET r.lastupdated = $update_tag
            """, chart_id=chart_id, service_id=service['id'], update_tag=self.update_tag)
        
        # Link ingresses
        for ingress in extracted_data.get('ingresses', []):
            session.run("""
                MATCH (hc:HelmChart {id: $chart_id})
                MATCH (ing:KubernetesIngress {id: $ingress_id})
                MERGE (hc)-[r:BELONGS_TO_CHART]->(ing)
                SET r.lastupdated = $update_tag
            """, chart_id=chart_id, ingress_id=ingress['id'], update_tag=self.update_tag)
    
    def _link_chart_to_existing_pods(self, session, chart_id: str, extracted_data: Dict):
        """Link HelmChart to existing Pods from Cartography."""
        # Link chart to Pods that match the deployment names from Helm charts
        # Pods are created by Cartography from actual cluster state
        for pod_ref in extracted_data.get('pods', []):
            namespace = pod_ref['namespace']
            name = pod_ref['name']
            
            # Find existing Pods from Cartography by namespace and name
            # Cartography may have multiple Pod instances (replicas), so we match all
            result = session.run("""
                MATCH (hc:HelmChart {id: $chart_id})
                MATCH (p:KubernetesPod)
                WHERE p.namespace = $namespace AND p.name = $name
                MERGE (hc)-[r:BELONGS_TO_CHART]->(p)
                SET r.lastupdated = $update_tag
                RETURN count(p) as linked_count
            """, chart_id=chart_id,
                namespace=namespace,
                name=name,
                update_tag=self.update_tag)
            
            record = result.single()
            if record and record['linked_count'] > 0:
                logger.debug(f"Linked {record['linked_count']} Pod(s) from Cartography to chart '{chart_id}'")
            else:
                logger.warning(f"No Pods found in Cartography for {namespace}/{name} - ensure Cartography has synced the cluster")
    
    def _link_resources_to_namespaces(self, session, extracted_data: Dict):
        """Link resources to namespaces using CONTAINS relationship."""
        # Skip pods - Cartography already links Pods to namespaces
        
        # Link services
        for service in extracted_data.get('services', []):
            namespace = service['namespace']
            session.run("""
                MATCH (ns:KubernetesNamespace {id: $namespace_id})
                MATCH (s:KubernetesService {id: $service_id})
                MERGE (ns)-[r:CONTAINS]->(s)
                SET r.lastupdated = $update_tag
            """, namespace_id=namespace, service_id=service['id'], update_tag=self.update_tag)
    
    def _link_to_infrastructure(self, session, extracted_data: Dict):
        """Link to existing infrastructure nodes (EKSCluster, ECRImage)."""
        # Try to link images to ECRImage
        # Extract image info from pod references (even though we don't create Pod nodes)
        for pod_ref in extracted_data.get('pods', []):
            for image_full in pod_ref.get('images', []):
                image_id = self._parse_image_id(image_full)
                # Try to match ECR image by repository:tag
                repository, tag = self._parse_image_repo_tag(image_full)
                
                # Look for ECRImage with matching repository and tag
                result = session.run("""
                    MATCH (img:Image {id: $image_id})
                    MATCH (ecr:ECRImage)
                    WHERE ecr.repository = $repository 
                      AND (ecr.tag = $tag OR ecr.tag IS NULL)
                    MERGE (img)-[r:LINKED_TO]->(ecr)
                    SET r.lastupdated = $update_tag
                    RETURN ecr.id as ecr_id
                    LIMIT 1
                """, image_id=image_id, repository=repository, tag=tag, update_tag=self.update_tag)
                
                if result.single():
                    logger.info(f"Linked image {image_id} to ECRImage")
        
        # Try to link pods to EKSCluster (if cluster_name is set)
        # This would require matching cluster names, which we don't have from Helm charts
        # For now, we'll skip this and let users manually link or extend later
    
    def _parse_image_id(self, image: str) -> str:
        """Parse image string to extract ID."""
        if '@' in image:
            return image
        if ':' in image:
            return image
        return f"{image}:latest"
    
    def _parse_image_repo_tag(self, image: str) -> tuple:
        """Parse image into (repository, tag) tuple."""
        # Handle digest format
        if '@' in image:
            repo = image.split('@')[0]
            return repo, None
        
        # Handle tag format
        if ':' in image:
            parts = image.rsplit(':', 1)
            return parts[0], parts[1]
        
        return image, 'latest'
