#!/usr/bin/env python3
"""
Example: Using the Impact Analyzer with Helm Chart Detection

This example demonstrates how to use the enhanced impact analyzer to detect
and analyze Helm chart changes along with code changes.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from impact_analyzer import ImpactAnalyzer


def example_full_analysis():
    """Example 1: Full analysis including Helm charts"""
    print("=" * 80)
    print("Example 1: Full Analysis with Helm Chart Detection")
    print("=" * 80)
    
    # Initialize analyzer
    analyzer = ImpactAnalyzer(
        neo4j_uri=os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
        neo4j_user=os.getenv('NEO4J_USER', 'neo4j'),
        neo4j_password=os.getenv('NEO4J_PASSWORD', 'cartography'),
        repo_path='.'
    )
    
    # Run analysis
    results = analyzer.analyze(
        base_ref='origin/main',
        head_ref='HEAD'
    )
    
    # Print summary
    summary = results['summary']
    print("\n📊 Summary:")
    print(f"  - Changed Files: {summary['changedFilesCount']}")
    print(f"  - Helm Charts Changed: {summary['helmChartsChangedCount']}")
    print(f"  - Affected Services: {summary['affectedServicesCount']}")
    print(f"  - Risk Level: {summary['overallRiskLevel']}")
    
    # Print Helm changes
    helm_changes = results.get('helmChanges', [])
    if helm_changes:
        print(f"\n⎈ Helm Chart Changes: {len(helm_changes)}")
        for change in helm_changes[:5]:
            print(f"  - {change['chart_name']}: {change['change_type']} ({change['severity']})")
    
    # Print chart impacts
    chart_impacts = results.get('helmChartImpacts', [])
    if chart_impacts:
        print(f"\n📦 Helm Chart Impacts: {len(chart_impacts)}")
        for impact in chart_impacts[:3]:
            print(f"  - Chart: {impact['chartName']}")
            print(f"    Services: {len(impact.get('services', []))}")
            print(f"    Dependent Services: {len(impact.get('dependentServices', []))}")
            print(f"    External Callers: {len(impact.get('externalCodeCallers', []))}")
    
    # Print ingress impacts (CRITICAL)
    ingress_impacts = results.get('ingressImpacts', [])
    if ingress_impacts:
        print(f"\n🌐 Ingress Changes (CRITICAL): {len(ingress_impacts)}")
        for impact in ingress_impacts:
            print(f"  - {impact['ingressName']}: {impact.get('hosts', 'N/A')}")
    
    # Generate report
    report = analyzer.generate_report(results, format='markdown')
    
    # Save report
    with open('impact-report.md', 'w') as f:
        f.write(report)
    print("\n✅ Report saved to: impact-report.md")
    
    analyzer.close()
    return results


def example_specific_files():
    """Example 2: Analyze specific Helm chart files"""
    print("\n" + "=" * 80)
    print("Example 2: Analyze Specific Helm Files")
    print("=" * 80)
    
    analyzer = ImpactAnalyzer(
        neo4j_uri=os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
        neo4j_user=os.getenv('NEO4J_USER', 'neo4j'),
        neo4j_password=os.getenv('NEO4J_PASSWORD', 'cartography'),
        repo_path='.'
    )
    
    # Analyze specific Helm files
    changed_files = [
        'services/user-service/Chart.yaml',
        'services/user-service/values.yaml',
        'services/user-service/templates/deployment.yaml'
    ]
    
    results = analyzer.analyze(changed_files=changed_files)
    
    # Print what was detected
    helm_changes = results.get('helmChanges', [])
    print(f"\nDetected {len(helm_changes)} Helm change(s):")
    for change in helm_changes:
        print(f"  - {change['relative_path']}: {change['change_type']} ({change['severity']})")
    
    analyzer.close()
    return results


def example_json_output():
    """Example 3: Generate JSON report for CI/CD integration"""
    print("\n" + "=" * 80)
    print("Example 3: JSON Output for CI/CD")
    print("=" * 80)
    
    analyzer = ImpactAnalyzer(
        neo4j_uri=os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
        neo4j_user=os.getenv('NEO4J_USER', 'neo4j'),
        neo4j_password=os.getenv('NEO4J_PASSWORD', 'cartography'),
        repo_path='.'
    )
    
    results = analyzer.analyze(
        base_ref='origin/main',
        head_ref='HEAD'
    )
    
    # Generate JSON report
    json_report = analyzer.generate_report(results, format='json')
    
    # Save JSON
    with open('impact-report.json', 'w') as f:
        f.write(json_report)
    print("\n✅ JSON report saved to: impact-report.json")
    
    # Check for critical risks
    summary = results['summary']
    if summary['overallRiskLevel'] == 'CRITICAL':
        print("\n⚠️  CRITICAL risk detected!")
        print("    Consider additional testing before deployment.")
    
    analyzer.close()
    return results


def example_query_specific_chart():
    """Example 4: Analyze impact of a specific chart"""
    print("\n" + "=" * 80)
    print("Example 4: Analyze Specific Chart Impact")
    print("=" * 80)
    
    analyzer = ImpactAnalyzer(
        neo4j_uri=os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
        neo4j_user=os.getenv('NEO4J_USER', 'neo4j'),
        neo4j_password=os.getenv('NEO4J_PASSWORD', 'cartography'),
        repo_path='.'
    )
    
    # Query impact for specific chart
    chart_names = ['user-service']
    
    chart_impact = analyzer.graph_analyzer.analyze_helm_chart_impact(chart_names)
    image_impact = analyzer.graph_analyzer.analyze_image_changes(chart_names)
    ingress_impact = analyzer.graph_analyzer.analyze_ingress_changes(chart_names)
    
    print(f"\n📦 Chart Impact for '{chart_names[0]}':")
    for impact in chart_impact['chartImpacts']:
        print(f"  - Services: {impact.get('services', [])}")
        print(f"  - Dependent Services: {len(impact.get('dependentServices', []))}")
        print(f"  - External Callers: {len(impact.get('externalCodeCallers', []))}")
        print(f"  - Publicly Exposed: {impact.get('isPubliclyExposed', False)}")
    
    print(f"\n🐳 Image Impact:")
    for impact in image_impact['imageImpacts']:
        print(f"  - Pod: {impact['podName']}")
        images = impact.get('images', [])
        for img in images:
            if img.get('image'):
                ecr = " (ECR)" if img.get('isECR') else ""
                print(f"    Image: {img['image']}{ecr}")
    
    print(f"\n🌐 Ingress Impact:")
    for impact in ingress_impact['ingressImpacts']:
        print(f"  - Ingress: {impact['ingressName']}")
        print(f"    Hosts: {impact.get('hosts', 'N/A')}")
        print(f"    Severity: CRITICAL")
    
    analyzer.close()


def main():
    """Run all examples"""
    print("Impact Analyzer - Helm Chart Analysis Examples")
    print("=" * 80)
    
    try:
        # Example 1: Full analysis
        example_full_analysis()
        
        # Example 2: Specific files
        # example_specific_files()
        
        # Example 3: JSON output
        # example_json_output()
        
        # Example 4: Query specific chart
        # example_query_specific_chart()
        
        print("\n" + "=" * 80)
        print("✅ Examples completed successfully!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
