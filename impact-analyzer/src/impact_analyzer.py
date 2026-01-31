#!/usr/bin/env python3
"""
Impact Analyzer - Main orchestrator for analyzing code change impacts.
"""

import logging
from typing import Dict, List, Optional
try:
    from .change_detector import ChangeDetector
    from .graph_analyzer import GraphAnalyzer
    from .report_generator import ReportGenerator
except ImportError:
    from change_detector import ChangeDetector
    from graph_analyzer import GraphAnalyzer
    from report_generator import ReportGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ImpactAnalyzer:
    """Main impact analyzer that orchestrates the analysis process."""
    
    def __init__(
        self,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        repo_path: str = "."
    ):
        """
        Initialize impact analyzer.
        
        Args:
            neo4j_uri: Neo4j connection URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            repo_path: Path to git repository
        """
        self.change_detector = ChangeDetector(repo_path)
        self.graph_analyzer = GraphAnalyzer(neo4j_uri, neo4j_user, neo4j_password)
        self.report_generator = ReportGenerator()
        self.repo_path = repo_path
    
    def analyze(
        self,
        base_ref: str = "origin/main",
        head_ref: str = "HEAD",
        changed_files: Optional[List[str]] = None
    ) -> Dict:
        """
        Perform complete impact analysis.
        
        Args:
            base_ref: Base branch/commit for comparison
            head_ref: Head branch/commit for comparison
            changed_files: Optional list of changed files (overrides git diff)
            
        Returns:
            Complete analysis results
        """
        logger.info("=" * 80)
        logger.info("Starting Impact Analysis")
        logger.info("=" * 80)
        
        # Step 1: Detect changed files
        logger.info("\n[Step 1/6] Detecting changed files...")
        changes = self.change_detector.get_changed_files(
            base_ref=base_ref,
            head_ref=head_ref,
            file_list=changed_files
        )
        
        all_changed_files = (
            changes['modified'] + 
            changes['added'] + 
            changes['deleted']
        )
        
        logger.info(f"Found {len(all_changed_files)} changed file(s)")
        if not all_changed_files:
            logger.warning("No changed files detected")
            return self._empty_analysis()
        
        # Step 2: Identify affected services
        logger.info("\n[Step 2/6] Identifying affected services...")
        affected_services = self.change_detector.identify_affected_services(all_changed_files)
        logger.info(f"Identified {len(affected_services)} affected service(s): {', '.join(affected_services)}")
        
        # Step 3: Find affected components in graph
        logger.info("\n[Step 3/6] Querying graph for affected components...")
        components_result = self.graph_analyzer.find_affected_components(all_changed_files)
        changed_components = components_result['components']
        logger.info(f"Found {len(changed_components)} component(s) in graph")
        
        # Extract service names from components
        service_names = set()
        for comp in changed_components:
            service_names.update(comp.get('ownsServices', []))
        service_names = list(service_names)
        
        # Add services identified by path analysis
        service_names.extend(affected_services)
        service_names = list(set(service_names))  # Deduplicate
        
        if not service_names:
            logger.warning("No services found in graph for changed files")
            return self._empty_analysis()
        
        logger.info(f"Analyzing impact for services: {', '.join(service_names)}")
        
        # Step 4: Calculate blast radius
        logger.info("\n[Step 4/6] Calculating blast radius...")
        blast_radius_result = self.graph_analyzer.calculate_blast_radius(service_names)
        blast_radius = blast_radius_result['impacts']
        logger.info(f"Calculated blast radius for {len(blast_radius)} service(s)")
        
        # Step 5: Detect breaking changes
        logger.info("\n[Step 5/6] Detecting potential breaking changes...")
        breaking_changes = self.change_detector.detect_breaking_changes(changes['modified'])
        logger.info(f"Detected {len(breaking_changes)} potential breaking change(s)")
        
        # Check breaking impacts for API changes
        breaking_impacts = []
        for change in breaking_changes:
            if change.get('type') == 'API_ENDPOINTS_MODIFIED':
                # Extract service name from file path
                service = self._extract_service_from_path(change['file'])
                if service:
                    endpoints = change.get('endpoints', [])
                    # Extract just the paths from endpoints like "GET /api/users"
                    paths = [e.split(' ', 1)[1] if ' ' in e else e for e in endpoints]
                    
                    result = self.graph_analyzer.check_breaking_changes(service, paths)
                    breaking_impacts.extend(result.get('breakingImpacts', []))
        
        logger.info(f"Found {len(breaking_impacts)} breaking impact(s)")
        
        # Step 6: Calculate risk and recommendations
        logger.info("\n[Step 6/6] Calculating risk scores and recommendations...")
        risk_result = self.graph_analyzer.calculate_risk_score(service_names)
        risks = risk_result['risks']
        
        recommendations_result = self.graph_analyzer.get_deployment_recommendations(service_names)
        recommendations = recommendations_result['recommendations']
        
        logger.info("Analysis complete!")
        
        # Compile results
        analysis_data = {
            'changedFiles': all_changed_files,
            'changedComponents': changed_components,
            'affectedServices': service_names,
            'blastRadius': blast_radius,
            'breakingChanges': breaking_changes,
            'breakingImpacts': breaking_impacts,
            'riskAnalysis': risks,
            'recommendations': recommendations
        }
        
        # Add summary
        analysis_data['summary'] = self.report_generator.generate_summary(analysis_data)
        
        return analysis_data
    
    def generate_report(self, analysis_data: Dict, format: str = 'markdown') -> str:
        """
        Generate report from analysis data.
        
        Args:
            analysis_data: Analysis results
            format: Output format ('json' or 'markdown')
            
        Returns:
            Report string
        """
        if format == 'json':
            return self.report_generator.generate_json_report(analysis_data)
        else:
            return self.report_generator.generate_markdown_report(analysis_data)
    
    def _extract_service_from_path(self, filepath: str) -> Optional[str]:
        """Extract service name from file path."""
        parts = filepath.split('/')
        if len(parts) >= 2:
            if parts[0] in ['services', 'apps', 'microservices']:
                return parts[1]
        return None
    
    def _empty_analysis(self) -> Dict:
        """Return empty analysis result."""
        return {
            'changedFiles': [],
            'changedComponents': [],
            'affectedServices': [],
            'blastRadius': [],
            'breakingChanges': [],
            'breakingImpacts': [],
            'riskAnalysis': [],
            'recommendations': [],
            'summary': {
                'changedFilesCount': 0,
                'affectedServicesCount': 0,
                'totalImpactCount': 0,
                'breakingChangesCount': 0,
                'overallRiskLevel': 'LOW',
                'maxRiskScore': 0
            }
        }
    
    def close(self):
        """Close connections."""
        self.graph_analyzer.close()
