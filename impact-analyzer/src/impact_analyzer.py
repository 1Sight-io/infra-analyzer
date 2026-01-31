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
        logger.info("\n[Step 1/9] Detecting changed files...")
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
        
        # Step 2: Detect Helm chart changes
        logger.info("\n[Step 2/9] Detecting Helm chart changes...")
        helm_changes = self.change_detector.detect_helm_changes(all_changed_files)
        logger.info(f"Detected {len(helm_changes)} Helm chart change(s)")
        
        # Extract chart names
        changed_chart_names = list(set(hc['chart_name'] for hc in helm_changes))
        
        # Step 3: Identify affected services
        logger.info("\n[Step 3/9] Identifying affected services...")
        affected_services = self.change_detector.identify_affected_services(all_changed_files)
        logger.info(f"Identified {len(affected_services)} affected service(s): {', '.join(affected_services)}")
        
        # Step 4: Find affected components in graph
        logger.info("\n[Step 4/9] Querying graph for affected components...")
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
        
        # Step 5: Analyze Helm chart impacts
        helm_chart_impacts = []
        image_impacts = []
        network_policy_impacts = []
        ingress_impacts = []
        
        if changed_chart_names:
            logger.info(f"\n[Step 5/9] Analyzing Helm chart impacts for {len(changed_chart_names)} chart(s)...")
            
            # Get comprehensive Helm chart impact
            chart_impact_result = self.graph_analyzer.analyze_helm_chart_impact(changed_chart_names)
            helm_chart_impacts = chart_impact_result['chartImpacts']
            logger.info(f"  - Analyzed {len(helm_chart_impacts)} chart impact(s)")
            
            # Analyze image changes
            image_impact_result = self.graph_analyzer.analyze_image_changes(changed_chart_names)
            image_impacts = image_impact_result['imageImpacts']
            logger.info(f"  - Analyzed {len(image_impacts)} image impact(s)")
            
            # Analyze network policy impacts
            network_policy_result = self.graph_analyzer.analyze_network_policy_impact(changed_chart_names)
            network_policy_impacts = network_policy_result['networkPolicyImpacts']
            logger.info(f"  - Analyzed {len(network_policy_impacts)} network policy impact(s)")
            
            # Analyze ingress changes
            ingress_impact_result = self.graph_analyzer.analyze_ingress_changes(changed_chart_names)
            ingress_impacts = ingress_impact_result['ingressImpacts']
            logger.info(f"  - Analyzed {len(ingress_impacts)} ingress impact(s)")
            
            # Extract services from Helm chart impacts
            for chart_impact in helm_chart_impacts:
                service_names.extend(chart_impact.get('services', []))
            service_names = list(set(service_names))  # Deduplicate
        else:
            logger.info("\n[Step 5/9] No Helm chart changes detected, skipping Helm-specific analysis")
        
        if not service_names and not helm_chart_impacts:
            logger.warning("No services or charts found for analysis")
            return self._empty_analysis()
        
        logger.info(f"Analyzing impact for {len(service_names)} total service(s): {', '.join(service_names)}")
        
        # Step 6: Calculate blast radius
        blast_radius = []
        if service_names:
            logger.info("\n[Step 6/9] Calculating blast radius...")
            blast_radius_result = self.graph_analyzer.calculate_blast_radius(service_names)
            blast_radius = blast_radius_result['impacts']
            logger.info(f"Calculated blast radius for {len(blast_radius)} service(s)")
        else:
            logger.info("\n[Step 6/9] Skipping blast radius calculation (no services)")
        
        # Step 7: Detect breaking changes
        logger.info("\n[Step 7/9] Detecting potential breaking changes...")
        breaking_changes = self.change_detector.detect_breaking_changes(changes['modified'])
        logger.info(f"Detected {len(breaking_changes)} potential breaking change(s)")
        
        # Add Helm changes to breaking changes
        for helm_change in helm_changes:
            if helm_change['severity'] in ['HIGH', 'CRITICAL']:
                breaking_changes.append({
                    'file': helm_change['changed_file'],
                    'type': f"HELM_{helm_change['change_type']}",
                    'chart': helm_change['chart_name'],
                    'severity': helm_change['severity'],
                    'message': f"Helm chart change: {helm_change['change_type']} in {helm_change['relative_path']}"
                })
        
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
        
        # Step 8: Calculate risk and recommendations
        risks = []
        recommendations = []
        
        if service_names:
            logger.info("\n[Step 8/9] Calculating risk scores and recommendations...")
            risk_result = self.graph_analyzer.calculate_risk_score(service_names)
            risks = risk_result['risks']
            
            recommendations_result = self.graph_analyzer.get_deployment_recommendations(service_names)
            recommendations = recommendations_result['recommendations']
        else:
            logger.info("\n[Step 8/9] Skipping risk calculation (no services)")
        
        logger.info("\n[Step 9/9] Compiling results...")
        logger.info("Analysis complete!")
        
        # Compile results
        analysis_data = {
            'changedFiles': all_changed_files,
            'changedComponents': changed_components,
            'affectedServices': service_names,
            'helmChanges': helm_changes,
            'helmChartImpacts': helm_chart_impacts,
            'imageImpacts': image_impacts,
            'networkPolicyImpacts': network_policy_impacts,
            'ingressImpacts': ingress_impacts,
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
            'helmChanges': [],
            'helmChartImpacts': [],
            'imageImpacts': [],
            'networkPolicyImpacts': [],
            'ingressImpacts': [],
            'blastRadius': [],
            'breakingChanges': [],
            'breakingImpacts': [],
            'riskAnalysis': [],
            'recommendations': [],
            'summary': {
                'changedFilesCount': 0,
                'affectedServicesCount': 0,
                'helmChartsChangedCount': 0,
                'totalImpactCount': 0,
                'breakingChangesCount': 0,
                'overallRiskLevel': 'LOW',
                'maxRiskScore': 0
            }
        }
    
    def close(self):
        """Close connections."""
        self.graph_analyzer.close()
