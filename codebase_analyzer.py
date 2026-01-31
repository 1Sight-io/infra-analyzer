#!/usr/bin/env python3
"""
Codebase Analyzer
Main entry point for analyzing codebase and linking to infrastructure.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from code_analyzer import CodeAnalyzer
from code_ingester import CodeIngester

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def find_source_files(codebase_path: Path, languages: Optional[List[str]] = None) -> List[Path]:
    """
    Find all source code files in the codebase.
    
    Args:
        codebase_path: Root path of the codebase
        languages: Optional list of languages to filter ('python', 'javascript')
        
    Returns:
        List of source file paths
    """
    codebase_path = Path(codebase_path)
    if not codebase_path.exists():
        logger.error(f"Codebase path does not exist: {codebase_path}")
        return []
    
    extensions = {
        'python': ['.py'],
        'javascript': ['.js', '.jsx', '.ts', '.tsx'],
    }
    
    # Determine which extensions to include
    if languages:
        ext_list = []
        for lang in languages:
            ext_list.extend(extensions.get(lang, []))
    else:
        ext_list = [ext for exts in extensions.values() for ext in exts]
    
    source_files = []
    
    # Common directories to exclude
    exclude_dirs = {
        'node_modules', '__pycache__', '.git', '.venv', 'venv',
        'env', '.env', 'dist', 'build', '.pytest_cache', '.mypy_cache'
    }
    
    for ext in ext_list:
        for file_path in codebase_path.rglob(f'*{ext}'):
            # Skip files in excluded directories
            if any(excluded in file_path.parts for excluded in exclude_dirs):
                continue
            
            source_files.append(file_path)
    
    return sorted(source_files)


def analyze_codebase(
    codebase_path: str,
    neo4j_uri: str = "bolt://localhost:7687",
    neo4j_user: str = "neo4j",
    neo4j_password: str = "cartography",
    languages: Optional[List[str]] = None,
    repository_name: Optional[str] = None,
    path_filter: Optional[str] = None,
):
    """
    Analyze codebase and ingest results into Neo4j.
    
    Args:
        codebase_path: Path to codebase root
        neo4j_uri: Neo4j connection URI
        neo4j_user: Neo4j username
        neo4j_password: Neo4j password
        languages: Optional list of languages to analyze ('python', 'javascript')
        repository_name: Optional repository name
        path_filter: Optional path filter (e.g., 'services/api-gateway')
    """
    codebase_path = Path(codebase_path).resolve()
    
    if not repository_name:
        repository_name = codebase_path.name
    
    logger.info(f"Analyzing codebase: {codebase_path}")
    logger.info(f"Repository name: {repository_name}")
    
    # Find source files
    logger.info("Finding source files...")
    source_files = find_source_files(codebase_path, languages)
    
    if path_filter:
        path_filter_path = codebase_path / path_filter
        source_files = [f for f in source_files if path_filter_path in f.parents or path_filter_path == f.parent]
        logger.info(f"Filtered to {len(source_files)} file(s) matching path filter: {path_filter}")
    
    if not source_files:
        logger.warning("No source files found")
        return False
    
    logger.info(f"Found {len(source_files)} source file(s)")
    
    # Connect to Neo4j
    ingester = CodeIngester(neo4j_uri, neo4j_user, neo4j_password)
    try:
        ingester.connect()
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")
        return False
    
    # Analyze files
    analyzer = CodeAnalyzer(repository_name=repository_name)
    
    success_count = 0
    error_count = 0
    total_service_calls = 0
    
    for file_path in source_files:
        try:
            logger.debug(f"Analyzing: {file_path}")
            result = analyzer.analyze_file(file_path)
            
            if result:
                service_calls_count = len(result.get('service_calls', []))
                if service_calls_count > 0:
                    logger.info(f"Found {service_calls_count} service call(s) in {file_path.name}")
                    total_service_calls += service_calls_count
                
                # Ingest into Neo4j
                ingester.ingest_code_module(result, repository_name)
                success_count += 1
            else:
                logger.debug(f"No results from {file_path.name}")
                
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}", exc_info=True)
            error_count += 1
            continue
    
    # Link code modules to Helm charts
    logger.info("Linking code modules to Helm charts...")
    try:
        ingester.link_to_helm_charts(str(codebase_path))
    except Exception as e:
        logger.warning(f"Failed to link to Helm charts: {e}")
    
    # Close Neo4j connection
    ingester.close()
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("Summary:")
    logger.info(f"{'='*60}")
    logger.info(f"✓ Successfully analyzed: {success_count} file(s)")
    logger.info(f"  Found {total_service_calls} service call(s)")
    if error_count > 0:
        logger.warning(f"✗ Failed: {error_count} file(s)")
    
    return error_count == 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Analyze codebase and link code to infrastructure services',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze entire codebase
  python codebase_analyzer.py /path/to/codebase

  # Analyze specific directory
  python codebase_analyzer.py /path/to/codebase --path services/api-gateway

  # Filter by language
  python codebase_analyzer.py /path/to/codebase --language python

  # Use custom Neo4j settings
  python codebase_analyzer.py /path/to/codebase \\
    --neo4j-uri bolt://localhost:7687 \\
    --neo4j-user neo4j \\
    --neo4j-password cartography
        """
    )
    
    parser.add_argument(
        'codebase_path',
        help='Path to codebase root directory'
    )
    
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
        '--language',
        action='append',
        choices=['python', 'javascript'],
        help='Filter by programming language (can be specified multiple times)'
    )
    
    parser.add_argument(
        '--path',
        dest='path_filter',
        help='Filter files by path (e.g., services/api-gateway)'
    )
    
    parser.add_argument(
        '--repository',
        dest='repository_name',
        help='Repository name (default: codebase directory name)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        success = analyze_codebase(
            codebase_path=args.codebase_path,
            neo4j_uri=args.neo4j_uri,
            neo4j_user=args.neo4j_user,
            neo4j_password=args.neo4j_password,
            languages=args.language,
            repository_name=args.repository_name,
            path_filter=args.path_filter,
        )
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
