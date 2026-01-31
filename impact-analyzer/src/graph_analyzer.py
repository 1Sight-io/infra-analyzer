#!/usr/bin/env python3
"""
Graph Analyzer - Queries Neo4j graph to analyze impact of changes.
"""

from neo4j import GraphDatabase
from typing import List, Dict, Set, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GraphAnalyzer:
    """Analyzes impact of changes using Neo4j graph."""
    
    def __init__(self, uri: str, user: str, password: str):
        """
        Initialize graph analyzer.
        
        Args:
            uri: Neo4j connection URI
            user: Neo4j username
            password: Neo4j password
        """
        # Handle SSL URIs
        driver_uri = uri
        driver_config = {}
        
        if uri.startswith(('bolt+s://', 'neo4j+s://')):
            from neo4j import TrustAll
            
            if uri.startswith('bolt+s://'):
                driver_uri = uri.replace('bolt+s://', 'bolt://')
            elif uri.startswith('neo4j+s://'):
                driver_uri = uri.replace('neo4j+s://', 'neo4j://')
            
            driver_config['encrypted'] = True
            driver_config['trusted_certificates'] = TrustAll()
            logger.info("Disabling SSL certificate verification for secure connection")
        
        self.driver = GraphDatabase.driver(driver_uri, auth=(user, password), **driver_config)
        logger.info(f"Connected to Neo4j at {uri}")
    
    def close(self):
        """Close Neo4j connection."""
        self.driver.close()
    
    def find_affected_components(self, changed_files: List[str]) -> Dict:
        """
        Find components affected by changed files.
        
        Args:
            changed_files: List of file paths
            
        Returns:
            Dictionary with affected components
        """
        with self.driver.session() as session:
            result = session.run("""
                WITH $changedFiles AS files
                UNWIND files AS file
                
                // Find CodeModules that match changed files
                MATCH (cm:CodeModule)
                WHERE cm.path CONTAINS file OR cm.path ENDS WITH file
                
                // Find Helm charts containing this code
                OPTIONAL MATCH (cm)<-[:CONTAINS_CODE]-(hc:HelmChart)
                
                // Find services this code calls
                OPTIONAL MATCH (cm)-[r:CALLS_SERVICE]->(s:KubernetesService)
                
                // Find services owned by the helm chart
                OPTIONAL MATCH (hc)-[:BELONGS_TO_CHART]->(ownedSvc:KubernetesService)
                
                RETURN DISTINCT 
                    cm.path AS codeFile,
                    cm.name AS fileName,
                    cm.language AS language,
                    hc.name AS helmChart,
                    collect(DISTINCT s.name) AS callsServices,
                    collect(DISTINCT ownedSvc.name) AS ownsServices
            """, changedFiles=changed_files)
            
            components = []
            for record in result:
                components.append({
                    'codeFile': record['codeFile'],
                    'fileName': record['fileName'],
                    'language': record['language'],
                    'helmChart': record['helmChart'],
                    'callsServices': [s for s in record['callsServices'] if s],
                    'ownsServices': [s for s in record['ownsServices'] if s]
                })
            
            return {'components': components}
    
    def calculate_blast_radius(self, service_names: List[str]) -> Dict:
        """
        Calculate the blast radius for affected services.
        
        Args:
            service_names: List of service names
            
        Returns:
            Dictionary with blast radius analysis
        """
        with self.driver.session() as session:
            result = session.run("""
                WITH $serviceNames AS services
                UNWIND services AS serviceName
                
                MATCH (s:KubernetesService {name: serviceName})
                
                // Find direct code callers
                OPTIONAL MATCH (cm:CodeModule)-[r1:CALLS_SERVICE]->(s)
                WITH s, collect(DISTINCT {
                    path: cm.path,
                    method: r1.method,
                    url: r1.url
                }) AS directCodeCallers
                
                // Find direct service callers
                OPTIONAL MATCH (s1:KubernetesService)-[r2:CONNECTS_TO]->(s)
                WITH s, directCodeCallers, collect(DISTINCT {
                    service: s1.name,
                    namespace: s1.namespace,
                    envVar: r2.env_var
                }) AS directServiceCallers
                
                // Find transitive service callers (2-3 hops)
                OPTIONAL MATCH path = (s2:KubernetesService)-[:CONNECTS_TO*2..3]->(s)
                WITH s, directCodeCallers, directServiceCallers,
                     collect(DISTINCT {
                         service: s2.name,
                         hops: length(path)
                     }) AS transitiveCallers
                
                // Check if exposed via ingress
                OPTIONAL MATCH (s)-[:EXPOSED_VIA]->(ing:KubernetesIngress)
                
                // Find which cluster/namespace
                OPTIONAL MATCH (s)-[:TARGETS]->(p:KubernetesPod)
                OPTIONAL MATCH (p)<-[:RESOURCE]-(cluster)
                
                RETURN {
                    service: s.name,
                    namespace: s.namespace,
                    chartName: s.chart_name,
                    clusterName: cluster.name,
                    isPubliclyExposed: ing IS NOT NULL,
                    ingressHosts: ing.hosts,
                    directCodeCallers: directCodeCallers,
                    directServiceCallers: directServiceCallers,
                    transitiveCallers: transitiveCallers,
                    directCodeCallersCount: size(directCodeCallers),
                    directServiceCallersCount: size(directServiceCallers),
                    transitiveCallersCount: size(transitiveCallers)
                } AS impact
            """, serviceNames=service_names)
            
            impacts = []
            for record in result:
                impacts.append(record['impact'])
            
            return {'impacts': impacts}
    
    def check_breaking_changes(self, service_name: str, endpoints: List[str]) -> Dict:
        """
        Check which components will break if endpoints are modified/removed.
        
        Args:
            service_name: Name of the service
            endpoints: List of endpoints (format: "GET /api/users")
            
        Returns:
            Dictionary with breaking change analysis
        """
        with self.driver.session() as session:
            result = session.run("""
                WITH $serviceName AS svcName, $endpoints AS endpoints
                
                MATCH (s:KubernetesService {name: svcName})
                MATCH (cm:CodeModule)-[r:CALLS_SERVICE]->(s)
                
                OPTIONAL MATCH (cm)<-[:CONTAINS_CODE]-(hc:HelmChart)
                
                // Check if the code calls any of the affected endpoints
                WITH cm, hc, r, endpoints,
                     ANY(endpoint IN endpoints WHERE r.url CONTAINS endpoint OR endpoint CONTAINS r.url) AS isAffected
                
                WHERE isAffected = true
                
                RETURN DISTINCT {
                    codeFile: cm.path,
                    helmChart: hc.name,
                    method: r.method,
                    url: r.url,
                    severity: 'CRITICAL'
                } AS breakingImpact
            """, serviceName=service_name, endpoints=endpoints)
            
            breaking_impacts = []
            for record in result:
                breaking_impacts.append(record['breakingImpact'])
            
            return {'breakingImpacts': breaking_impacts}
    
    def calculate_risk_score(self, service_names: List[str]) -> Dict:
        """
        Calculate risk score for affected services.
        
        Args:
            service_names: List of service names
            
        Returns:
            Dictionary with risk scores
        """
        with self.driver.session() as session:
            result = session.run("""
                WITH $serviceNames AS services
                UNWIND services AS serviceName
                
                MATCH (s:KubernetesService {name: serviceName})
                
                // Count direct code callers
                OPTIONAL MATCH (cm:CodeModule)-[:CALLS_SERVICE]->(s)
                WITH s, count(DISTINCT cm) AS codeCallers
                
                // Count service callers
                OPTIONAL MATCH (s1:KubernetesService)-[:CONNECTS_TO]->(s)
                WITH s, codeCallers, count(DISTINCT s1) AS serviceCallers
                
                // Count transitive callers
                OPTIONAL MATCH (s2:KubernetesService)-[:CONNECTS_TO*2..3]->(s)
                WITH s, codeCallers, serviceCallers, count(DISTINCT s2) AS transitiveCallers
                
                // Check if publicly exposed
                OPTIONAL MATCH (s)-[:EXPOSED_VIA]->(ing:KubernetesIngress)
                WITH s, codeCallers, serviceCallers, transitiveCallers,
                     CASE WHEN ing IS NOT NULL THEN 1 ELSE 0 END AS isPublic
                
                // Check cluster/environment
                OPTIONAL MATCH (s)-[:TARGETS]->(p:KubernetesPod)<-[:RESOURCE]-(cluster)
                WITH s, codeCallers, serviceCallers, transitiveCallers, isPublic,
                     CASE WHEN cluster.name CONTAINS 'prod' THEN 2 ELSE 1 END AS envMultiplier
                
                // Calculate risk score
                WITH s, codeCallers, serviceCallers, transitiveCallers, isPublic, envMultiplier,
                     (codeCallers * 10 + serviceCallers * 20 + transitiveCallers * 5 + isPublic * 50) * envMultiplier AS riskScore
                
                RETURN {
                    service: s.name,
                    codeCallers: codeCallers,
                    serviceCallers: serviceCallers,
                    transitiveCallers: transitiveCallers,
                    isPubliclyExposed: isPublic = 1,
                    riskScore: riskScore,
                    riskLevel: CASE 
                        WHEN riskScore > 200 THEN 'CRITICAL'
                        WHEN riskScore > 100 THEN 'HIGH'
                        WHEN riskScore > 50 THEN 'MEDIUM'
                        ELSE 'LOW'
                    END
                } AS risk
            """, serviceNames=service_names)
            
            risks = []
            for record in result:
                risks.append(record['risk'])
            
            return {'risks': risks}
    
    def get_deployment_recommendations(self, service_names: List[str]) -> Dict:
        """
        Get deployment recommendations based on service dependencies.
        
        Args:
            service_names: List of service names
            
        Returns:
            Dictionary with recommendations
        """
        with self.driver.session() as session:
            result = session.run("""
                WITH $serviceNames AS services
                UNWIND services AS serviceName
                
                MATCH (s:KubernetesService {name: serviceName})
                
                // Check dependencies
                OPTIONAL MATCH (s1:KubernetesService)-[:CONNECTS_TO]->(s)
                WITH s, count(DISTINCT s1) AS dependentCount
                
                // Check if publicly exposed
                OPTIONAL MATCH (s)-[:EXPOSED_VIA]->(ing:KubernetesIngress)
                
                RETURN {
                    service: s.name,
                    dependentCount: dependentCount,
                    isPublic: ing IS NOT NULL,
                    recommendation: CASE
                        WHEN ing IS NOT NULL THEN 'Blue-Green deployment recommended (public exposure)'
                        WHEN dependentCount > 2 THEN 'Canary deployment recommended (high dependencies)'
                        ELSE 'Rolling update is safe'
                    END,
                    testingPriority: CASE
                        WHEN ing IS NOT NULL THEN 'HIGH - Integration tests required'
                        WHEN dependentCount > 0 THEN 'MEDIUM - Contract tests recommended'
                        ELSE 'LOW - Unit tests sufficient'
                    END
                } AS recommendation
            """, serviceNames=service_names)
            
            recommendations = []
            for record in result:
                recommendations.append(record['recommendation'])
            
            return {'recommendations': recommendations}
