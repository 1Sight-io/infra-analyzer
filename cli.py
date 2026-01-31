#!/usr/bin/env python3
"""
Infrastructure Analyzer CLI
Unified command-line interface for all infrastructure scanning and analysis tools.
"""

import argparse
import logging
import sys
from pathlib import Path

# Import the existing analyzers
from helm_analyzer import analyze_codebase as analyze_helm
from cartography_runner import CartographyRunner
from codebase_analyzer import analyze_codebase as analyze_code

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def cmd_helm(args):
    """Run Helm chart analyzer."""
    logger.info("=" * 80)
    logger.info("Running Helm Chart Analyzer")
    logger.info("=" * 80)
    
    success = analyze_helm(
        codebase_path=args.codebase_path,
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password,
        namespace_filter=args.namespace,
        chart_filter=args.chart,
    )
    
    return 0 if success else 1


def cmd_cartography(args):
    """Run Cartography to extract AWS and Kubernetes infrastructure."""
    logger.info("=" * 80)
    logger.info("Running Cartography Infrastructure Extractor")
    logger.info("=" * 80)
    
    # Determine which modules to run
    modules = []
    if args.aws_only:
        modules = ['aws']
    elif args.k8s_only:
        modules = ['k8s']
    else:
        modules = ['aws', 'k8s']
    
    runner = CartographyRunner(
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password,
        aws_profile=args.aws_profile,
        aws_region=args.aws_region,
        kubeconfig_path=args.kubeconfig,
        k8s_cluster_name=args.cluster_name,
        k8s_context=getattr(args, 'k8s_context', None),
        permission_mapping_file=args.permission_mapping_file,
        skip_k8s_on_error=args.skip_k8s_on_error,
        cartography_path=args.cartography_path,
    )
    
    if args.verify:
        if not runner.verify_prerequisites():
            logger.error("Prerequisites check failed. Fix issues and try again.")
            return 1
    
    return runner.run(modules=modules)


def cmd_aws(args):
    """Run AWS-only infrastructure extraction."""
    logger.info("=" * 80)
    logger.info("Running AWS Infrastructure Extractor (via Cartography)")
    logger.info("=" * 80)
    
    runner = CartographyRunner(
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password,
        aws_profile=args.aws_profile,
        aws_region=args.aws_region,
        permission_mapping_file=args.permission_mapping_file,
        cartography_path=args.cartography_path,
    )
    
    if args.verify:
        if not runner.verify_prerequisites():
            logger.error("Prerequisites check failed. Fix issues and try again.")
            return 1
    
    return runner.run(modules=['aws'])


def cmd_k8s(args):
    """Run Kubernetes-only infrastructure extraction."""
    logger.info("=" * 80)
    logger.info("Running Kubernetes Infrastructure Extractor (via Cartography)")
    logger.info("=" * 80)
    
    runner = CartographyRunner(
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password,
        kubeconfig_path=args.kubeconfig,
        k8s_cluster_name=args.cluster_name,
        k8s_context=getattr(args, 'k8s_context', None),
        skip_k8s_on_error=False,
        cartography_path=args.cartography_path,
    )
    
    if args.verify:
        if not runner.verify_prerequisites():
            logger.error("Prerequisites check failed. Fix issues and try again.")
            return 1
    
    return runner.run(modules=['k8s'])


def cmd_code(args):
    """Run code analyzer to extract service calls from source code."""
    logger.info("=" * 80)
    logger.info("Running Code Analyzer")
    logger.info("=" * 80)
    
    success = analyze_code(
        codebase_path=args.codebase_path,
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password,
        languages=args.language,
        repository_name=args.repository,
        path_filter=args.path_filter,
    )
    
    return 0 if success else 1


def cmd_all(args):
    """Run all analyzers in sequence."""
    logger.info("=" * 80)
    logger.info("Running ALL Infrastructure Analyzers")
    logger.info("=" * 80)
    
    exit_codes = []
    
    # Step 1: Run Cartography to extract infrastructure
    logger.info("\n" + "=" * 80)
    logger.info("Step 1/3: Extracting Infrastructure (Cartography)")
    logger.info("=" * 80)
    
    cartography_modules = []
    if not args.skip_aws:
        cartography_modules.append('aws')
    if not args.skip_k8s:
        cartography_modules.append('k8s')
    
    if cartography_modules:
        runner = CartographyRunner(
            neo4j_uri=args.neo4j_uri,
            neo4j_user=args.neo4j_user,
            neo4j_password=args.neo4j_password,
            aws_profile=args.aws_profile,
            aws_region=args.aws_region,
            kubeconfig_path=args.kubeconfig,
            k8s_cluster_name=args.cluster_name,
            k8s_context=getattr(args, 'k8s_context', None),
            permission_mapping_file=args.permission_mapping_file,
            skip_k8s_on_error=args.skip_k8s_on_error,
            cartography_path=args.cartography_path,
        )
        
        exit_code = runner.run(modules=cartography_modules)
        exit_codes.append(exit_code)
        
        if exit_code != 0:
            logger.warning(f"Cartography exited with code {exit_code}")
    else:
        logger.info("Skipping Cartography (both AWS and K8s disabled)")
    
    # Step 2: Run Helm analyzer if codebase path is provided
    if args.codebase_path and not args.skip_helm:
        logger.info("\n" + "=" * 80)
        logger.info("Step 2/3: Analyzing Helm Charts")
        logger.info("=" * 80)
        
        success = analyze_helm(
            codebase_path=args.codebase_path,
            neo4j_uri=args.neo4j_uri,
            neo4j_user=args.neo4j_user,
            neo4j_password=args.neo4j_password,
            namespace_filter=args.namespace,
            chart_filter=args.chart,
        )
        
        exit_codes.append(0 if success else 1)
        
        if not success:
            logger.warning("Helm analyzer failed")
    else:
        if args.skip_helm:
            logger.info("\nSkipping Helm analyzer (--skip-helm flag)")
        else:
            logger.info("\nSkipping Helm analyzer (no codebase path provided)")
    
    # Step 3: Run Code analyzer if codebase path is provided
    if args.codebase_path and not args.skip_code:
        logger.info("\n" + "=" * 80)
        logger.info("Step 3/3: Analyzing Source Code")
        logger.info("=" * 80)
        
        success = analyze_code(
            codebase_path=args.codebase_path,
            neo4j_uri=args.neo4j_uri,
            neo4j_user=args.neo4j_user,
            neo4j_password=args.neo4j_password,
            languages=args.code_language,
            repository_name=args.repository,
            path_filter=args.code_path_filter,
        )
        
        exit_codes.append(0 if success else 1)
        
        if not success:
            logger.warning("Code analyzer failed")
    else:
        if args.skip_code:
            logger.info("\nSkipping Code analyzer (--skip-code flag)")
        else:
            logger.info("\nSkipping Code analyzer (no codebase path provided)")
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    
    if all(code == 0 for code in exit_codes):
        logger.info("✓ All analyzers completed successfully")
        return 0
    else:
        logger.warning(f"⚠ Some analyzers failed. Exit codes: {exit_codes}")
        return max(exit_codes)


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Infrastructure Analyzer - Unified CLI for scanning and analyzing infrastructure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all analyzers (Cartography + Helm + Code)
  %(prog)s all /path/to/codebase --aws-region us-west-2 --cluster-name my-cluster
  
  # Extract AWS infrastructure only
  %(prog)s aws --aws-region us-west-2 --aws-profile myprofile
  
  # Extract Kubernetes infrastructure only
  %(prog)s k8s --cluster-name my-cluster
  
  # Run Cartography with both AWS and K8s
  %(prog)s cartography --aws-region us-west-2 --cluster-name my-cluster
  
  # Analyze Helm charts only
  %(prog)s helm /path/to/codebase
  
  # Analyze source code only
  %(prog)s code /path/to/codebase --language python
  
  # Run everything with custom Neo4j settings
  %(prog)s all /path/to/codebase --neo4j-uri bolt://neo4j.example.com:7687
        """
    )
    
    # Global options
    parser.add_argument(
        '--neo4j-uri',
        default='bolt://localhost:7687',
        help='Neo4j connection URI (default: bolt://localhost:7687)'
    )
    parser.add_argument(
        '--neo4j-user',
        default='neo4j',
        help='Neo4j username (default: neo4j)'
    )
    parser.add_argument(
        '--neo4j-password',
        default='cartography',
        help='Neo4j password (default: cartography)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    # Subcommands
    subparsers = parser.add_subparsers(
        title='commands',
        description='Available analysis modules',
        dest='command',
        required=True
    )
    
    # --- Helm command ---
    helm_parser = subparsers.add_parser(
        'helm',
        help='Analyze Helm charts and extract application relationships'
    )
    helm_parser.add_argument(
        'codebase_path',
        help='Path to codebase directory containing Helm charts'
    )
    helm_parser.add_argument(
        '--namespace',
        help='Filter by Kubernetes namespace'
    )
    helm_parser.add_argument(
        '--chart',
        help='Analyze specific chart only (matches by name)'
    )
    helm_parser.set_defaults(func=cmd_helm)
    
    # --- Cartography command ---
    cartography_parser = subparsers.add_parser(
        'cartography',
        help='Run Cartography to extract AWS and Kubernetes infrastructure'
    )
    cartography_parser.add_argument(
        '--aws-profile',
        help='AWS profile name from ~/.aws/credentials'
    )
    cartography_parser.add_argument(
        '--aws-region',
        help='AWS region (e.g., us-west-2, eu-west-1)'
    )
    cartography_parser.add_argument(
        '--kubeconfig',
        help='Path to kubeconfig file (default: ~/.kube/config)'
    )
    cartography_parser.add_argument(
        '--cluster-name',
        help='Specific Kubernetes cluster name to target'
    )
    cartography_parser.add_argument(
        '--k8s-context',
        help='Specific Kubernetes context to use from kubeconfig'
    )
    cartography_parser.add_argument(
        '--permission-mapping-file',
        help='Path to AWS permission mapping YAML file'
    )
    cartography_parser.add_argument(
        '--cartography-path',
        help='Path to extended Cartography fork directory'
    )
    cartography_parser.add_argument(
        '--aws-only',
        action='store_true',
        help='Run only AWS module'
    )
    cartography_parser.add_argument(
        '--k8s-only',
        action='store_true',
        help='Run only Kubernetes module'
    )
    cartography_parser.add_argument(
        '--skip-k8s-on-error',
        action='store_true',
        help='If Kubernetes sync fails, retry with AWS only'
    )
    cartography_parser.add_argument(
        '--verify',
        action='store_true',
        help='Verify prerequisites before running'
    )
    cartography_parser.set_defaults(func=cmd_cartography)
    
    # --- AWS command ---
    aws_parser = subparsers.add_parser(
        'aws',
        help='Extract AWS infrastructure only (via Cartography)'
    )
    aws_parser.add_argument(
        '--aws-profile',
        help='AWS profile name from ~/.aws/credentials'
    )
    aws_parser.add_argument(
        '--aws-region',
        help='AWS region (e.g., us-west-2, eu-west-1)'
    )
    aws_parser.add_argument(
        '--permission-mapping-file',
        help='Path to AWS permission mapping YAML file'
    )
    aws_parser.add_argument(
        '--cartography-path',
        help='Path to extended Cartography fork directory'
    )
    aws_parser.add_argument(
        '--verify',
        action='store_true',
        help='Verify prerequisites before running'
    )
    aws_parser.set_defaults(func=cmd_aws)
    
    # --- K8s command ---
    k8s_parser = subparsers.add_parser(
        'k8s',
        help='Extract Kubernetes infrastructure only (via Cartography)'
    )
    k8s_parser.add_argument(
        '--kubeconfig',
        help='Path to kubeconfig file (default: ~/.kube/config)'
    )
    k8s_parser.add_argument(
        '--cluster-name',
        help='Specific Kubernetes cluster name to target'
    )
    k8s_parser.add_argument(
        '--k8s-context',
        help='Specific Kubernetes context to use from kubeconfig'
    )
    k8s_parser.add_argument(
        '--cartography-path',
        help='Path to extended Cartography fork directory'
    )
    k8s_parser.add_argument(
        '--verify',
        action='store_true',
        help='Verify prerequisites before running'
    )
    k8s_parser.set_defaults(func=cmd_k8s)
    
    # --- Code command ---
    code_parser = subparsers.add_parser(
        'code',
        help='Analyze source code and extract service calls'
    )
    code_parser.add_argument(
        'codebase_path',
        help='Path to codebase directory'
    )
    code_parser.add_argument(
        '--language',
        action='append',
        choices=['python', 'javascript'],
        help='Filter by programming language (can be specified multiple times)'
    )
    code_parser.add_argument(
        '--path',
        dest='path_filter',
        help='Filter files by path (e.g., services/api-gateway)'
    )
    code_parser.add_argument(
        '--repository',
        help='Repository name (default: codebase directory name)'
    )
    code_parser.set_defaults(func=cmd_code)
    
    # --- All command ---
    all_parser = subparsers.add_parser(
        'all',
        help='Run all analyzers in sequence (Cartography + Helm + Code)'
    )
    all_parser.add_argument(
        'codebase_path',
        nargs='?',
        help='Path to codebase directory containing Helm charts and source code (optional)'
    )
    all_parser.add_argument(
        '--aws-profile',
        help='AWS profile name from ~/.aws/credentials'
    )
    all_parser.add_argument(
        '--aws-region',
        help='AWS region (e.g., us-west-2, eu-west-1)'
    )
    all_parser.add_argument(
        '--kubeconfig',
        help='Path to kubeconfig file (default: ~/.kube/config)'
    )
    all_parser.add_argument(
        '--cluster-name',
        help='Specific Kubernetes cluster name to target'
    )
    all_parser.add_argument(
        '--k8s-context',
        help='Specific Kubernetes context to use from kubeconfig'
    )
    all_parser.add_argument(
        '--permission-mapping-file',
        help='Path to AWS permission mapping YAML file'
    )
    all_parser.add_argument(
        '--cartography-path',
        help='Path to extended Cartography fork directory'
    )
    all_parser.add_argument(
        '--namespace',
        help='Filter Helm charts by Kubernetes namespace'
    )
    all_parser.add_argument(
        '--chart',
        help='Analyze specific Helm chart only (matches by name)'
    )
    all_parser.add_argument(
        '--skip-aws',
        action='store_true',
        help='Skip AWS infrastructure extraction'
    )
    all_parser.add_argument(
        '--skip-k8s',
        action='store_true',
        help='Skip Kubernetes infrastructure extraction'
    )
    all_parser.add_argument(
        '--skip-helm',
        action='store_true',
        help='Skip Helm chart analysis'
    )
    all_parser.add_argument(
        '--skip-code',
        action='store_true',
        help='Skip source code analysis'
    )
    all_parser.add_argument(
        '--skip-k8s-on-error',
        action='store_true',
        help='If Kubernetes sync fails, continue with AWS only'
    )
    all_parser.add_argument(
        '--code-language',
        action='append',
        choices=['python', 'javascript'],
        help='Filter code analysis by language (can be specified multiple times)'
    )
    all_parser.add_argument(
        '--code-path',
        dest='code_path_filter',
        help='Filter code files by path (e.g., services/api-gateway)'
    )
    all_parser.add_argument(
        '--repository',
        help='Repository name for code analysis (default: codebase directory name)'
    )
    all_parser.set_defaults(func=cmd_all)
    
    # Parse arguments
    args = parser.parse_args()
    
    # Setup logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Execute command
    try:
        exit_code = args.func(args)
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
