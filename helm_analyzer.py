#!/usr/bin/env python3
"""
Helm Chart Application Relations Analyzer
Main entry point for analyzing Helm charts and ingesting into Neo4j.
"""

import argparse
import logging
import sys
from pathlib import Path

from helm_parser import find_helm_charts, render_chart
from k8s_extractor import K8sResourceExtractor
from neo4j_ingester import Neo4jIngester

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def analyze_codebase(
    codebase_path: str,
    neo4j_uri: str = "bolt://localhost:7687",
    neo4j_user: str = "neo4j",
    neo4j_password: str = "cartography",
    namespace_filter: str = None,
    chart_filter: str = None,
):
    """
    Analyze Helm charts in a codebase and ingest into Neo4j.
    
    Args:
        codebase_path: Path to codebase directory
        neo4j_uri: Neo4j connection URI
        neo4j_user: Neo4j username
        neo4j_password: Neo4j password
        namespace_filter: Optional namespace filter
        chart_filter: Optional chart name filter
    """
    codebase_path = Path(codebase_path).resolve()
    
    if not codebase_path.exists():
        logger.error(f"Codebase path does not exist: {codebase_path}")
        return False
    
    logger.info(f"Scanning for Helm charts in: {codebase_path}")
    
    # Find all Helm charts
    try:
        charts = find_helm_charts(codebase_path)
    except Exception as e:
        logger.error(f"Failed to find Helm charts: {e}")
        return False
    
    if not charts:
        logger.warning("No Helm charts found!")
        return False
    
    logger.info(f"Found {len(charts)} Helm chart(s)")
    
    # Filter charts if requested
    if chart_filter:
        charts = [c for c in charts if chart_filter.lower() in c.chart_path.name.lower()]
        logger.info(f"Filtered to {len(charts)} chart(s) matching '{chart_filter}'")
    
    if not charts:
        logger.warning("No charts match the filter criteria")
        return False
    
    # Connect to Neo4j
    ingester = Neo4jIngester(neo4j_uri, neo4j_user, neo4j_password)
    try:
        ingester.connect()
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")
        return False
    
    # Process each chart
    success_count = 0
    error_count = 0
    
    for chart in charts:
        chart_name = chart.chart_path.name
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing chart: {chart_name}")
        logger.info(f"{'='*60}")
        
        try:
            # Render Helm templates
            logger.info("Rendering Helm templates...")
            metadata, resources = render_chart(chart)
            
            chart_name_meta = metadata.get('name', chart_name)
            chart_version = metadata.get('version', '0.0.0')
            chart_path = chart.get_relative_path()
            
            logger.info(f"Rendered {len(resources)} Kubernetes resource(s)")
            
            # Load values for service connection extraction
            values = chart.load_values()
            
            # Extract entities and relationships
            logger.info("Extracting entities and relationships...")
            extractor = K8sResourceExtractor(
                chart_name=chart_name_meta,
                chart_version=chart_version,
                chart_path=chart_path
            )
            
            # Apply namespace filter if specified
            if namespace_filter:
                resources = [r for r in resources 
                            if r.get('metadata', {}).get('namespace', 'default') == namespace_filter]
            
            extracted_data = extractor.extract_resources(resources)
            extracted_data['chart_path'] = chart_path
            
            logger.info(f"Extracted:")
            logger.info(f"  - {len(extracted_data['pods'])} pod reference(s) (will link to Cartography Pods)")
            logger.info(f"  - {len(extracted_data['services'])} service(s)")
            logger.info(f"  - {len(extracted_data['ingresses'])} ingress(es)")
            logger.info(f"  - {len(extracted_data['service_accounts'])} service account(s)")
            
            # Extract service connections from env vars
            service_connections = extractor.extract_service_connections_from_env(values)
            logger.info(f"  - {len(service_connections)} service connection(s) from env vars")
            
            # Ingest into Neo4j
            logger.info("Ingesting into Neo4j...")
            ingester.ingest_chart(metadata, extracted_data, service_connections)
            
            logger.info(f"✓ Successfully processed chart: {chart_name}")
            success_count += 1
            
        except Exception as e:
            logger.error(f"✗ Failed to process chart {chart_name}: {e}", exc_info=True)
            error_count += 1
            continue
    
    # Resolve all service connections (in case some target services were ingested after source services)
    logger.info("\nResolving all service connections...")
    try:
        ingester.resolve_all_service_connections()
    except Exception as e:
        logger.warning(f"Failed to resolve service connections: {e}")
    
    # Close Neo4j connection
    ingester.close()
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("Summary:")
    logger.info(f"{'='*60}")
    logger.info(f"✓ Successfully processed: {success_count} chart(s)")
    if error_count > 0:
        logger.warning(f"✗ Failed: {error_count} chart(s)")
    
    return error_count == 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze Helm charts and ingest application relations into Neo4j"
    )
    parser.add_argument(
        "codebase_path",
        type=str,
        help="Path to codebase directory containing Helm charts"
    )
    parser.add_argument(
        "--neo4j-uri",
        type=str,
        default="bolt://localhost:7687",
        help="Neo4j connection URI (default: bolt://localhost:7687)"
    )
    parser.add_argument(
        "--neo4j-user",
        type=str,
        default="neo4j",
        help="Neo4j username (default: neo4j)"
    )
    parser.add_argument(
        "--neo4j-password",
        type=str,
        default="cartography",
        help="Neo4j password (default: cartography)"
    )
    parser.add_argument(
        "--namespace",
        type=str,
        default=None,
        help="Filter by Kubernetes namespace (optional)"
    )
    parser.add_argument(
        "--chart",
        type=str,
        default=None,
        help="Analyze specific chart only (optional, matches by name)"
    )
    
    args = parser.parse_args()
    
    success = analyze_codebase(
        codebase_path=args.codebase_path,
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password,
        namespace_filter=args.namespace,
        chart_filter=args.chart,
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
