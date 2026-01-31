#!/usr/bin/env python3
"""
Report Generator - Generates impact analysis reports in various formats.
"""

import json
from typing import Dict, List
from datetime import datetime


class ReportGenerator:
    """Generates impact analysis reports."""
    
    def __init__(self):
        """Initialize report generator."""
        self.timestamp = datetime.now().isoformat()
    
    def generate_json_report(self, analysis_data: Dict) -> str:
        """
        Generate JSON report.
        
        Args:
            analysis_data: Analysis results
            
        Returns:
            JSON string
        """
        report = {
            'timestamp': self.timestamp,
            'version': '1.0.0',
            **analysis_data
        }
        return json.dumps(report, indent=2)
    
    def generate_markdown_report(self, analysis_data: Dict) -> str:
        """
        Generate Markdown report for GitHub PR comments.
        
        Args:
            analysis_data: Analysis results
            
        Returns:
            Markdown string
        """
        md = []
        
        # Header
        md.append("# 🔍 Impact Analysis Report")
        md.append("")
        md.append(f"**Generated:** {self.timestamp}")
        md.append("")
        
        # Summary
        summary = analysis_data.get('summary', {})
        md.append("## 📊 Summary")
        md.append("")
        md.append(f"- **Changed Files:** {summary.get('changedFilesCount', 0)}")
        md.append(f"- **Helm Charts Changed:** {summary.get('helmChartsChangedCount', 0)}")
        md.append(f"- **Affected Services:** {summary.get('affectedServicesCount', 0)}")
        md.append(f"- **Total Impact Radius:** {summary.get('totalImpactCount', 0)} component(s)")
        md.append(f"- **Risk Level:** {self._format_risk_level(summary.get('overallRiskLevel', 'UNKNOWN'))}")
        md.append("")
        
        # Helm Chart Changes
        helm_changes = analysis_data.get('helmChanges', [])
        if helm_changes:
            md.append("## ⎈ Helm Chart Changes")
            md.append("")
            md.append(f"Detected {len(helm_changes)} change(s) in Helm charts:")
            md.append("")
            
            # Group by chart
            charts_dict = {}
            for change in helm_changes:
                chart_name = change['chart_name']
                if chart_name not in charts_dict:
                    charts_dict[chart_name] = []
                charts_dict[chart_name].append(change)
            
            for chart_name, changes in charts_dict.items():
                md.append(f"### Chart: `{chart_name}`")
                for change in changes:
                    severity_emoji = self._format_severity(change['severity'])
                    md.append(f"- **{change['change_type']}** - {severity_emoji}")
                    md.append(f"  - File: `{change['relative_path']}`")
                md.append("")
        
        # Helm Chart Impacts
        helm_impacts = analysis_data.get('helmChartImpacts', [])
        if helm_impacts:
            md.append("## 📦 Helm Chart Impact Analysis")
            md.append("")
            for impact in helm_impacts:
                chart_name = impact.get('chartName', 'Unknown')
                md.append(f"### Chart: `{chart_name}`")
                
                if impact.get('isPubliclyExposed'):
                    md.append("⚠️ **Contains Publicly Exposed Services**")
                    if impact.get('publicIngresses'):
                        md.append(f"  - Hosts: {impact['publicIngresses']}")
                
                services = impact.get('services', [])
                if services:
                    md.append(f"- **Services:** {', '.join([f'`{s}`' for s in services])}")
                
                pods = impact.get('pods', [])
                if pods:
                    md.append(f"- **Pods/Deployments:** {len(pods)}")
                
                ingresses = impact.get('ingresses', [])
                if ingresses:
                    md.append(f"- **Ingresses:** {', '.join([f'`{i}`' for i in ingresses])}")
                
                dependent_services = impact.get('dependentServices', [])
                if dependent_services:
                    md.append(f"- **Dependent Services:** {len(dependent_services)}")
                    for dep in dependent_services[:5]:
                        if dep and dep.get('service'):
                            md.append(f"  - `{dep['service']}` depends on `{dep.get('dependsOn', '?')}`")
                    if len(dependent_services) > 5:
                        md.append(f"  - ... and {len(dependent_services) - 5} more")
                
                external_callers = impact.get('externalCodeCallers', [])
                if external_callers:
                    md.append(f"- **External Code Callers:** {len(external_callers)}")
                    for caller in external_callers[:5]:
                        if caller and caller.get('codePath'):
                            md.append(f"  - `{caller['codePath']}` → `{caller.get('callsService', '?')}`")
                    if len(external_callers) > 5:
                        md.append(f"  - ... and {len(external_callers) - 5} more")
                
                md.append("")
        
        # Image Impacts
        image_impacts = analysis_data.get('imageImpacts', [])
        if image_impacts:
            md.append("## 🐳 Container Image Impacts")
            md.append("")
            for impact in image_impacts:
                chart_name = impact.get('chartName', 'Unknown')
                pod_name = impact.get('podName', 'Unknown')
                md.append(f"### Pod: `{pod_name}` (Chart: `{chart_name}`)")
                md.append(f"- **Namespace:** `{impact.get('namespace', 'default')}`")
                
                images = impact.get('images', [])
                if images:
                    md.append("- **Container Images:**")
                    for img in images:
                        if img and img.get('image'):
                            ecr_marker = " (ECR)" if img.get('isECR') else ""
                            md.append(f"  - `{img['image']}`{ecr_marker}")
                
                exposed_via = impact.get('exposedViaServices', [])
                if exposed_via:
                    md.append(f"- **Exposed via Services:** {', '.join([f'`{s}`' for s in exposed_via if s])}")
                
                dependent_svcs = impact.get('dependentServices', [])
                if dependent_svcs:
                    md.append(f"- **Dependent Services:** {', '.join([f'`{s}`' for s in dependent_svcs if s])}")
                
                md.append("")
        
        # Ingress Impacts
        ingress_impacts = analysis_data.get('ingressImpacts', [])
        if ingress_impacts:
            md.append("## 🌐 Ingress Changes (External Impact)")
            md.append("")
            for impact in ingress_impacts:
                ingress_name = impact.get('ingressName', 'Unknown')
                md.append(f"### Ingress: `{ingress_name}` 🔴 CRITICAL")
                md.append(f"- **Namespace:** `{impact.get('namespace', 'default')}`")
                
                hosts = impact.get('hosts')
                if hosts:
                    md.append(f"- **Hosts:** {hosts}")
                
                paths = impact.get('paths')
                if paths:
                    md.append(f"- **Paths:** {paths}")
                
                if impact.get('loadBalancer'):
                    md.append(f"- **Load Balancer:** `{impact['loadBalancer']}`")
                
                backend_services = impact.get('backendServices', [])
                if backend_services:
                    md.append("- **Backend Services:**")
                    for svc in backend_services:
                        if svc and svc.get('serviceName'):
                            pods = svc.get('pods', [])
                            pod_info = f" ({len(pods)} pod(s))" if pods else ""
                            md.append(f"  - `{svc['serviceName']}`{pod_info}")
                
                external_callers = impact.get('externalCallers', [])
                if external_callers:
                    md.append(f"- **External Callers (in codebase):** {len(external_callers)}")
                    for caller in external_callers[:3]:
                        if caller:
                            md.append(f"  - `{caller}`")
                
                md.append("")
        
        # Network Policy Impacts
        network_policy_impacts = analysis_data.get('networkPolicyImpacts', [])
        if network_policy_impacts:
            md.append("## 🔒 Network Policy Impacts")
            md.append("")
            for impact in network_policy_impacts:
                pod_name = impact.get('podName', 'Unknown')
                md.append(f"### Pod: `{pod_name}`")
                md.append(f"- **Namespace:** `{impact.get('namespace', 'default')}`")
                
                policies = impact.get('networkPolicies', [])
                if policies:
                    md.append(f"- **Network Policies Applied:** {len(policies)}")
                    for policy in policies:
                        if policy and policy.get('policyName'):
                            md.append(f"  - `{policy['policyName']}`")
                
                other_pods = impact.get('otherAffectedPods', [])
                if other_pods:
                    md.append(f"- **Other Pods Affected by Same Policies:** {len(other_pods)}")
                    for pod in other_pods[:5]:
                        if pod:
                            md.append(f"  - `{pod}`")
                    if len(other_pods) > 5:
                        md.append(f"  - ... and {len(other_pods) - 5} more")
                
                md.append("")
        
        # Changed Components
        components = analysis_data.get('changedComponents', [])
        if components:
            md.append("## 📝 Changed Code Components")
            md.append("")
            for comp in components:
                md.append(f"### `{comp.get('codeFile', 'Unknown')}`")
                if comp.get('helmChart'):
                    md.append(f"- **Helm Chart:** `{comp['helmChart']}`")
                if comp.get('ownsServices'):
                    md.append(f"- **Owns Services:** {', '.join([f'`{s}`' for s in comp['ownsServices']])}")
                if comp.get('callsServices'):
                    md.append(f"- **Calls Services:** {', '.join([f'`{s}`' for s in comp['callsServices']])}")
                md.append("")
        
        # Blast Radius
        impacts = analysis_data.get('blastRadius', [])
        if impacts:
            md.append("## 💥 Blast Radius")
            md.append("")
            for impact in impacts:
                service = impact.get('service', 'Unknown')
                md.append(f"### Service: `{service}`")
                
                if impact.get('isPubliclyExposed'):
                    md.append("⚠️ **Publicly Exposed via Ingress**")
                    if impact.get('ingressHosts'):
                        md.append(f"  - Hosts: {impact['ingressHosts']}")
                
                md.append(f"- **Namespace:** `{impact.get('namespace', 'default')}`")
                if impact.get('clusterName'):
                    md.append(f"- **Cluster:** `{impact.get('clusterName')}`")
                
                # Direct code callers
                code_count = impact.get('directCodeCallersCount', 0)
                if code_count > 0:
                    md.append(f"- **Direct Code Callers:** {code_count}")
                    callers = impact.get('directCodeCallers', [])[:5]  # Show max 5
                    for caller in callers:
                        if caller and caller.get('path'):
                            md.append(f"  - `{caller['path']}` - {caller.get('method', 'GET')} {caller.get('url', '')}")
                    if code_count > 5:
                        md.append(f"  - ... and {code_count - 5} more")
                
                # Direct service callers
                svc_count = impact.get('directServiceCallersCount', 0)
                if svc_count > 0:
                    md.append(f"- **Direct Service Dependencies:** {svc_count}")
                    callers = impact.get('directServiceCallers', [])[:5]
                    for caller in callers:
                        if caller and caller.get('service'):
                            md.append(f"  - `{caller['service']}`")
                
                # Transitive callers
                trans_count = impact.get('transitiveCallersCount', 0)
                if trans_count > 0:
                    md.append(f"- **Transitive Dependencies:** {trans_count} (2-3 hops away)")
                
                md.append("")
        
        # Breaking Changes
        breaking = analysis_data.get('breakingChanges', [])
        if breaking:
            md.append("## ⚠️ Potential Breaking Changes")
            md.append("")
            for change in breaking:
                md.append(f"### {change.get('file', 'Unknown')}")
                md.append(f"- **Type:** {change.get('type', 'Unknown')}")
                md.append(f"- **Severity:** {self._format_severity(change.get('severity', 'UNKNOWN'))}")
                md.append(f"- **Message:** {change.get('message', '')}")
                if change.get('endpoints'):
                    md.append("- **Affected Endpoints:**")
                    for endpoint in change['endpoints'][:10]:  # Max 10
                        md.append(f"  - `{endpoint}`")
                md.append("")
            
            # Breaking impact details
            breaking_impacts = analysis_data.get('breakingImpacts', [])
            if breaking_impacts:
                md.append("### 🚨 Code That Will Break")
                md.append("")
                for impact in breaking_impacts:
                    md.append(f"- `{impact.get('codeFile', 'Unknown')}` calls `{impact.get('url', '')}`")
                    if impact.get('helmChart'):
                        md.append(f"  - Chart: `{impact['helmChart']}`")
                md.append("")
        
        # Risk Analysis
        risks = analysis_data.get('riskAnalysis', [])
        if risks:
            md.append("## 🎲 Risk Analysis")
            md.append("")
            for risk in risks:
                service = risk.get('service', 'Unknown')
                level = risk.get('riskLevel', 'UNKNOWN')
                score = risk.get('riskScore', 0)
                
                md.append(f"### `{service}` - {self._format_risk_level(level)} (Score: {score})")
                md.append(f"- Code callers: {risk.get('codeCallers', 0)}")
                md.append(f"- Service dependencies: {risk.get('serviceCallers', 0)}")
                md.append(f"- Transitive dependencies: {risk.get('transitiveCallers', 0)}")
                if risk.get('isPubliclyExposed'):
                    md.append("- ⚠️ Publicly exposed")
                md.append("")
        
        # Recommendations
        recommendations = analysis_data.get('recommendations', [])
        if recommendations:
            md.append("## 💡 Deployment Recommendations")
            md.append("")
            for rec in recommendations:
                service = rec.get('service', 'Unknown')
                md.append(f"### `{service}`")
                md.append(f"- **Strategy:** {rec.get('recommendation', 'Unknown')}")
                md.append(f"- **Testing Priority:** {rec.get('testingPriority', 'Unknown')}")
                md.append(f"- **Dependents:** {rec.get('dependentCount', 0)} service(s)")
                md.append("")
        
        # Footer
        md.append("---")
        md.append("*Generated by Impact Analyzer*")
        
        return '\n'.join(md)
    
    def _format_risk_level(self, level: str) -> str:
        """Format risk level with emoji."""
        emoji_map = {
            'CRITICAL': '🔴 CRITICAL',
            'HIGH': '🟡 HIGH',
            'MEDIUM': '🟠 MEDIUM',
            'LOW': '🟢 LOW',
            'UNKNOWN': '⚪ UNKNOWN'
        }
        return emoji_map.get(level, level)
    
    def _format_severity(self, severity: str) -> str:
        """Format severity with emoji."""
        emoji_map = {
            'CRITICAL': '🔴 CRITICAL',
            'HIGH': '🟡 HIGH',
            'MEDIUM': '🟠 MEDIUM',
            'LOW': '🟢 LOW',
            'UNKNOWN': '⚪ UNKNOWN'
        }
        return emoji_map.get(severity, severity)
    
    def generate_summary(self, analysis_data: Dict) -> Dict:
        """
        Generate executive summary.
        
        Args:
            analysis_data: Analysis results
            
        Returns:
            Summary dictionary
        """
        impacts = analysis_data.get('blastRadius', [])
        risks = analysis_data.get('riskAnalysis', [])
        breaking = analysis_data.get('breakingChanges', [])
        helm_changes = analysis_data.get('helmChanges', [])
        ingress_impacts = analysis_data.get('ingressImpacts', [])
        
        # Calculate overall risk
        risk_scores = [r.get('riskScore', 0) for r in risks]
        max_risk = max(risk_scores) if risk_scores else 0
        
        # Increase risk if ingresses are affected
        if ingress_impacts:
            max_risk = max(max_risk, 250)
        
        # Increase risk for critical Helm changes
        critical_helm_changes = [h for h in helm_changes if h.get('severity') == 'CRITICAL']
        if critical_helm_changes:
            max_risk = max(max_risk, 200)
        
        if max_risk > 200:
            overall_risk = 'CRITICAL'
        elif max_risk > 100:
            overall_risk = 'HIGH'
        elif max_risk > 50:
            overall_risk = 'MEDIUM'
        else:
            overall_risk = 'LOW'
        
        # Count total impacts
        total_impact = sum(
            i.get('directCodeCallersCount', 0) + 
            i.get('directServiceCallersCount', 0) + 
            i.get('transitiveCallersCount', 0)
            for i in impacts
        )
        
        # Get unique chart names
        helm_charts_changed = len(set(h.get('chart_name') for h in helm_changes if h.get('chart_name')))
        
        return {
            'changedFilesCount': len(analysis_data.get('changedComponents', [])),
            'helmChartsChangedCount': helm_charts_changed,
            'affectedServicesCount': len(impacts),
            'totalImpactCount': total_impact,
            'breakingChangesCount': len(breaking),
            'overallRiskLevel': overall_risk,
            'maxRiskScore': max_risk
        }
