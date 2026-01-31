#!/usr/bin/env python3
"""
Cartography Runner
Runs Cartography to extract AWS and Kubernetes (EKS) data into Neo4j.
"""

import argparse
import logging
import os
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Optional

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

logger = logging.getLogger(__name__)


class CartographyRunner:
    """Runs Cartography with AWS and Kubernetes modules."""
    
    def __init__(
        self,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "cartography",
        aws_profile: Optional[str] = None,
        aws_region: Optional[str] = None,
        kubeconfig_path: Optional[str] = None,
        k8s_cluster_name: Optional[str] = None,
        k8s_context: Optional[str] = None,
        permission_mapping_file: Optional[str] = None,
        skip_k8s_on_error: bool = False,
        cartography_path: Optional[str] = None,
    ):
        """
        Initialize Cartography runner.
        
        Args:
            neo4j_uri: Neo4j connection URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            aws_profile: AWS profile name (from ~/.aws/credentials)
            aws_region: AWS region (e.g., us-west-2)
            kubeconfig_path: Path to kubeconfig file for Kubernetes access
            k8s_cluster_name: Specific Kubernetes cluster name to target (optional)
            k8s_context: Specific Kubernetes context to use from kubeconfig (optional)
            permission_mapping_file: Path to AWS permission mapping YAML file (optional)
            skip_k8s_on_error: If True, retry with AWS only if Kubernetes sync fails
            cartography_path: Path to extended Cartography fork directory (optional).
                            If provided, uses extended Cartography instead of pip-installed version.
        """
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.aws_profile = aws_profile
        self.aws_region = aws_region
        self.kubeconfig_path = kubeconfig_path
        self.k8s_cluster_name = k8s_cluster_name
        self.k8s_context = k8s_context
        self.permission_mapping_file = permission_mapping_file
        self.skip_k8s_on_error = skip_k8s_on_error
        self.cartography_path = cartography_path
        
    def run(self, modules: list = None):
        """
        Run Cartography with specified modules.
        
        Args:
            modules: List of modules to run. Options: 'aws', 'k8s', 'all'.
                    If None, runs all available modules.
        """
        if modules is None:
            modules = ['aws', 'k8s']
        
        if 'all' in modules:
            modules = ['aws', 'k8s']
        
        # Determine Cartography command path
        if self.cartography_path:
            # Use extended Cartography from fork
            cartography_path = Path(self.cartography_path).resolve()
            if not cartography_path.exists():
                logger.error(f"Cartography path does not exist: {cartography_path}")
                sys.exit(1)
            
            # Verify cartography module exists
            cartography_module = cartography_path / 'cartography'
            if not cartography_module.exists():
                logger.error(f"Cartography module not found in: {cartography_path}")
                sys.exit(1)
            
            # Use Python module execution for extended Cartography
            # This allows running the fork without installing it
            python_executable = sys.executable
            cmd = [python_executable, '-m', 'cartography']
            
            # Add the fork directory to Python path (so 'cartography' module can be imported)
            # The fork directory contains the 'cartography' package directory
            env = os.environ.copy()
            python_path = env.get('PYTHONPATH', '')
            if python_path:
                env['PYTHONPATH'] = f"{cartography_path}:{python_path}"
            else:
                env['PYTHONPATH'] = str(cartography_path)
            
            logger.info(f"Using extended Cartography from: {cartography_path}")
            logger.debug(f"PYTHONPATH set to: {env['PYTHONPATH']}")
        else:
            # Use standard pip-installed Cartography with SSL wrapper for secure connections
            if self.neo4j_uri.startswith(('bolt+s://', 'neo4j+s://')):
                # Use our SSL wrapper to disable certificate verification
                wrapper_path = Path(__file__).parent / 'cartography_ssl_wrapper.py'
                cmd = ['python3.12', str(wrapper_path)]
                logger.info("Using SSL wrapper for Cartography to disable certificate verification")
            else:
                cmd = ['cartography']
            env = os.environ.copy()
        
        # Neo4j configuration
        cmd.extend(['--neo4j-uri', self.neo4j_uri])
        cmd.extend(['--neo4j-user', self.neo4j_user])
        
        # Set password via environment variable (Cartography uses --neo4j-password-env-var)
        env['NEO4J_PASSWORD'] = self.neo4j_password
        cmd.extend(['--neo4j-password-env-var', 'NEO4J_PASSWORD'])
        
        # Build module list for --selected-modules
        module_list = []
        
        # AWS module configuration
        if 'aws' in modules:
            module_list.append('aws')
            
            # Explicitly set AWS profile to prevent Cartography from auto-discovering profiles
            # This is important because kubeconfig contexts may reference other AWS accounts
            # (like tavily account) that don't have profiles configured
            if self.aws_profile:
                env['AWS_PROFILE'] = self.aws_profile
                # Unset any other profile-related env vars that might interfere
                env.pop('AWS_ACCESS_KEY_ID', None)
                env.pop('AWS_SECRET_ACCESS_KEY', None)
                env.pop('AWS_SESSION_TOKEN', None)
                logger.info(f"Using AWS profile: {self.aws_profile}")
            else:
                # If no profile specified, warn that Cartography might discover profiles from kubeconfig
                logger.warning("No AWS profile specified. Cartography may discover profiles from kubeconfig contexts.")
            
            if self.aws_region:
                env['AWS_DEFAULT_REGION'] = self.aws_region
                # Cartography also accepts --aws-regions flag
                cmd.extend(['--aws-regions', self.aws_region])
                logger.info(f"Using AWS region: {self.aws_region}")
            
            if self.permission_mapping_file:
                if os.path.exists(self.permission_mapping_file):
                    cmd.extend(['--permission-relationships-file', self.permission_mapping_file])
                    logger.info(f"Using permission mapping file: {self.permission_mapping_file}")
                else:
                    logger.warning(f"Permission mapping file not found: {self.permission_mapping_file}")
        
        # Kubernetes module configuration
        if 'k8s' in modules:
            module_list.append('kubernetes')
            
            if self.kubeconfig_path:
                if os.path.exists(self.kubeconfig_path):
                    env['KUBECONFIG'] = self.kubeconfig_path
                    cmd.extend(['--k8s-kubeconfig', self.kubeconfig_path])
                    logger.info(f"Using kubeconfig: {self.kubeconfig_path}")
                else:
                    logger.error(f"Kubeconfig file not found: {self.kubeconfig_path}")
                    sys.exit(1)
            else:
                # Use default kubeconfig location
                default_kubeconfig = os.path.expanduser('~/.kube/config')
                if os.path.exists(default_kubeconfig):
                    env['KUBECONFIG'] = default_kubeconfig
                    cmd.extend(['--k8s-kubeconfig', default_kubeconfig])
                    logger.info(f"Using default kubeconfig: {default_kubeconfig}")
                else:
                    logger.warning("No kubeconfig found. Kubernetes module may fail.")
            
            if self.k8s_cluster_name:
                env['K8S_CLUSTER_NAME'] = self.k8s_cluster_name
                logger.info(f"Targeting Kubernetes cluster: {self.k8s_cluster_name}")
            
            # If k8s_context is specified, create a filtered kubeconfig with only that context
            # This prevents Cartography from trying to sync unreachable clusters
            if self.k8s_context:
                kubeconfig_to_filter = self.kubeconfig_path or os.path.expanduser('~/.kube/config')
                filtered_kubeconfig = self._create_context_filtered_kubeconfig(kubeconfig_to_filter, self.k8s_context)
                if filtered_kubeconfig:
                    env['KUBECONFIG'] = filtered_kubeconfig
                    # Update the --k8s-kubeconfig argument
                    try:
                        kubeconfig_idx = cmd.index('--k8s-kubeconfig')
                        cmd[kubeconfig_idx + 1] = filtered_kubeconfig
                    except ValueError:
                        # If --k8s-kubeconfig not found, add it
                        cmd.extend(['--k8s-kubeconfig', filtered_kubeconfig])
                    logger.info(f"Using Kubernetes context '{self.k8s_context}': {filtered_kubeconfig}")
            # If cluster name is specified, create a filtered kubeconfig with only that cluster
            # This prevents Cartography from trying to sync unreachable clusters
            elif self.k8s_cluster_name:
                kubeconfig_to_filter = self.kubeconfig_path or os.path.expanduser('~/.kube/config')
                filtered_kubeconfig = self._create_filtered_kubeconfig(kubeconfig_to_filter, self.k8s_cluster_name)
                if filtered_kubeconfig:
                    env['KUBECONFIG'] = filtered_kubeconfig
                    # Update the --k8s-kubeconfig argument
                    try:
                        kubeconfig_idx = cmd.index('--k8s-kubeconfig')
                        cmd[kubeconfig_idx + 1] = filtered_kubeconfig
                    except ValueError:
                        # If --k8s-kubeconfig not found, add it
                        cmd.extend(['--k8s-kubeconfig', filtered_kubeconfig])
                    logger.info(f"Using filtered kubeconfig for cluster '{self.k8s_cluster_name}': {filtered_kubeconfig}")
        
        # Set selected modules (if specified, otherwise Cartography runs all available)
        if module_list:
            cmd.extend(['--selected-modules', ','.join(module_list)])
            logger.info(f"Running modules: {', '.join(module_list)}")
        
        # Log the command (without password)
        logger.info(f"Running Cartography command: {' '.join(cmd)}")
        
        try:
            # Run Cartography
            result = subprocess.run(
                cmd,
                env=env,
                check=True,
                capture_output=False,  # Show output in real-time
            )
            logger.info("Cartography completed successfully")
            return result.returncode
        except subprocess.CalledProcessError as e:
            # If Kubernetes sync failed and skip_k8s_on_error is enabled, try AWS only
            if self.skip_k8s_on_error and 'kubernetes' in module_list and e.returncode != 0:
                logger.warning("Kubernetes sync failed. Retrying with AWS only...")
                # Remove Kubernetes from modules and retry
                aws_only_modules = [m for m in module_list if m != 'kubernetes']
                if aws_only_modules:
                    # Rebuild command without Kubernetes
                    cmd_aws_only = ['cartography']
                    cmd_aws_only.extend(['--neo4j-uri', self.neo4j_uri])
                    cmd_aws_only.extend(['--neo4j-user', self.neo4j_user])
                    cmd_aws_only.extend(['--neo4j-password-env-var', 'NEO4J_PASSWORD'])
                    
                    # Add AWS-specific flags
                    if 'aws' in aws_only_modules:
                        if self.aws_region:
                            cmd_aws_only.extend(['--aws-regions', self.aws_region])
                        if self.permission_mapping_file and os.path.exists(self.permission_mapping_file):
                            cmd_aws_only.extend(['--permission-relationships-file', self.permission_mapping_file])
                    
                    cmd_aws_only.extend(['--selected-modules', ','.join(aws_only_modules)])
                    
                    # Remove KUBECONFIG from env
                    env_aws_only = {k: v for k, v in env.items() if k != 'KUBECONFIG' and k != 'K8S_CLUSTER_NAME'}
                    
                    logger.info("Retrying with AWS module only...")
                    logger.info(f"Running Cartography command: {' '.join(cmd_aws_only)}")
                    try:
                        result = subprocess.run(
                            cmd_aws_only,
                            env=env_aws_only,
                            check=True,
                            capture_output=False,
                        )
                        logger.info("Cartography completed successfully (AWS only)")
                        return result.returncode
                    except subprocess.CalledProcessError as e2:
                        logger.error(f"Cartography failed with exit code {e2.returncode}")
                        sys.exit(e2.returncode)
                else:
                    logger.error("No modules to run after skipping Kubernetes")
                    sys.exit(e.returncode)
            else:
                logger.error(f"Cartography failed with exit code {e.returncode}")
                if 'kubernetes' in module_list:
                    logger.error("Tip: If Kubernetes sync failed due to network issues, use --skip-k8s-on-error")
                sys.exit(e.returncode)
        except FileNotFoundError:
            logger.error(
                "Cartography not found. Please install it:\n"
                "  pip install cartography\n"
                "Or see: https://cartography-cncf.github.io/cartography/"
            )
            sys.exit(1)
    
    def verify_prerequisites(self):
        """Verify that prerequisites are met."""
        issues = []
        warnings = []
        
        # Check if Cartography is available
        if self.cartography_path:
            cartography_path = Path(self.cartography_path).resolve()
            if not cartography_path.exists():
                issues.append(f"Cartography path does not exist: {cartography_path}")
            elif not (cartography_path / 'cartography').exists():
                issues.append(f"Cartography module not found in: {cartography_path}")
        else:
            # Check if Cartography is installed via pip
            try:
                result = subprocess.run(
                    ['cartography', '--version'],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode != 0:
                    issues.append("Cartography is installed but not working properly")
            except FileNotFoundError:
                issues.append("Cartography is not installed. Install with: pip install cartography or use --cartography-path")
            except subprocess.TimeoutExpired:
                issues.append("Cartography command timed out")
        
        # Check AWS credentials if AWS module will be used
        if self.aws_profile:
            aws_creds_path = os.path.expanduser('~/.aws/credentials')
            if not os.path.exists(aws_creds_path):
                issues.append(f"AWS credentials file not found at {aws_creds_path}")
        
        # Check kubeconfig if K8s module will be used
        kubeconfig_to_check = self.kubeconfig_path or os.path.expanduser('~/.kube/config')
        if os.path.exists(kubeconfig_to_check):
            # Try to verify cluster connectivity
            try:
                result = subprocess.run(
                    ['kubectl', '--kubeconfig', kubeconfig_to_check, 'cluster-info'],
                    capture_output=True,
                    timeout=10
                )
                if result.returncode != 0:
                    warnings.append(f"Kubeconfig found but cluster connectivity check failed. This may cause Kubernetes sync to fail.")
            except FileNotFoundError:
                warnings.append("kubectl not found. Cannot verify cluster connectivity.")
            except subprocess.TimeoutExpired:
                warnings.append("Cluster connectivity check timed out. Cluster may be unreachable.")
        else:
            if self.kubeconfig_path:
                issues.append(f"Kubeconfig file not found: {self.kubeconfig_path}")
            else:
                warnings.append(f"Default kubeconfig not found at {kubeconfig_to_check}. Kubernetes sync will be skipped.")
        
        if issues:
            logger.warning("Prerequisites check found issues:")
            for issue in issues:
                logger.warning(f"  - {issue}")
            return False
        
        if warnings:
            logger.info("Prerequisites check found warnings:")
            for warning in warnings:
                logger.info(f"  - {warning}")
        
        logger.info("Prerequisites check passed")
        return True
    
    def _create_filtered_kubeconfig(self, kubeconfig_path: str, cluster_name: str) -> Optional[str]:
        """
        Create a filtered kubeconfig containing only the specified cluster.
        This prevents Cartography from trying to sync unreachable clusters.
        
        Args:
            kubeconfig_path: Path to original kubeconfig
            cluster_name: Name of cluster to include
            
        Returns:
            Path to filtered kubeconfig, or None if filtering failed
        """
        if not YAML_AVAILABLE:
            logger.warning("PyYAML not available. Cannot create filtered kubeconfig. Install with: pip install pyyaml")
            return None
        
        try:
            # Read original kubeconfig
            with open(kubeconfig_path, 'r') as f:
                config = yaml.safe_load(f)
            
            if not config:
                return None
            
            # Find the context that matches the cluster name
            target_context = None
            target_cluster = None
            target_user = None
            
            for context in config.get('contexts', []):
                ctx_name = context.get('name', '')
                # Match by cluster name in context name or cluster reference
                if cluster_name.lower() in ctx_name.lower():
                    target_context = context
                    cluster_ref = context.get('context', {}).get('cluster', '')
                    user_ref = context.get('context', {}).get('user', '')
                    
                    # Find matching cluster and user
                    for cluster in config.get('clusters', []):
                        if cluster.get('name') == cluster_ref:
                            target_cluster = cluster
                            break
                    
                    for user in config.get('users', []):
                        if user.get('name') == user_ref:
                            target_user = user
                            break
                    break
            
            # If not found by context name, try to find by cluster ARN pattern
            if not target_context:
                for cluster in config.get('clusters', []):
                    cluster_name_in_config = cluster.get('name', '')
                    if cluster_name.lower() in cluster_name_in_config.lower():
                        target_cluster = cluster
                        # Find context using this cluster
                        for context in config.get('contexts', []):
                            if context.get('context', {}).get('cluster') == cluster_name_in_config:
                                target_context = context
                                user_ref = context.get('context', {}).get('user', '')
                                for user in config.get('users', []):
                                    if user.get('name') == user_ref:
                                        target_user = user
                                        break
                                break
                        break
            
            if not target_context or not target_cluster:
                logger.warning(f"Could not find cluster '{cluster_name}' in kubeconfig. Using full kubeconfig.")
                return None
            
            # Create filtered config
            filtered_config = {
                'apiVersion': config.get('apiVersion', 'v1'),
                'kind': config.get('kind', 'Config'),
                'clusters': [target_cluster],
                'users': [target_user] if target_user else [],
                'contexts': [target_context],
                'current-context': target_context.get('name', '')
            }
            
            # Create temporary file for filtered kubeconfig
            temp_dir = tempfile.gettempdir()
            filtered_path = os.path.join(temp_dir, f'kubeconfig-filtered-{cluster_name}.yaml')
            
            with open(filtered_path, 'w') as f:
                yaml.dump(filtered_config, f, default_flow_style=False)
            
            logger.info(f"Created filtered kubeconfig with only cluster '{cluster_name}'")
            return filtered_path
            
        except Exception as e:
            logger.warning(f"Failed to create filtered kubeconfig: {e}. Using full kubeconfig.")
            return None
    
    def _create_context_filtered_kubeconfig(self, kubeconfig_path: str, context_name: str) -> Optional[str]:
        """
        Create a filtered kubeconfig containing only the specified context.
        This is simpler than cluster-based filtering since we match the context directly.
        
        Args:
            kubeconfig_path: Path to original kubeconfig
            context_name: Name of context to use
            
        Returns:
            Path to filtered kubeconfig, or None if filtering failed
        """
        if not YAML_AVAILABLE:
            logger.warning("PyYAML not available. Cannot create filtered kubeconfig. Install with: pip install pyyaml")
            return None
        
        try:
            # Read original kubeconfig
            with open(kubeconfig_path, 'r') as f:
                config = yaml.safe_load(f)
            
            if not config:
                return None
            
            # Find the specified context
            target_context = None
            target_cluster = None
            target_user = None
            
            for context in config.get('contexts', []):
                if context.get('name') == context_name:
                    target_context = context
                    cluster_ref = context.get('context', {}).get('cluster', '')
                    user_ref = context.get('context', {}).get('user', '')
                    
                    # Find matching cluster and user
                    for cluster in config.get('clusters', []):
                        if cluster.get('name') == cluster_ref:
                            target_cluster = cluster
                            break
                    
                    for user in config.get('users', []):
                        if user.get('name') == user_ref:
                            target_user = user
                            break
                    break
            
            if not target_context or not target_cluster:
                logger.warning(f"Could not find context '{context_name}' in kubeconfig. Using full kubeconfig.")
                return None
            
            # Create filtered config
            filtered_config = {
                'apiVersion': config.get('apiVersion', 'v1'),
                'kind': config.get('kind', 'Config'),
                'clusters': [target_cluster],
                'users': [target_user] if target_user else [],
                'contexts': [target_context],
                'current-context': context_name
            }
            
            # Create temporary file for filtered kubeconfig
            temp_dir = tempfile.gettempdir()
            # Sanitize context name for filename (replace colons and slashes)
            safe_context_name = context_name.replace(':', '-').replace('/', '-')
            filtered_path = os.path.join(temp_dir, f'kubeconfig-context-{safe_context_name}.yaml')
            
            with open(filtered_path, 'w') as f:
                yaml.dump(filtered_config, f, default_flow_style=False)
            
            logger.info(f"Created filtered kubeconfig with only context '{context_name}'")
            return filtered_path
            
        except Exception as e:
            logger.warning(f"Failed to create filtered kubeconfig: {e}. Using full kubeconfig.")
            return None


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Run Cartography to extract AWS and Kubernetes data into Neo4j',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default settings (AWS + K8s)
  python cartography_runner.py

  # Run AWS only for specific region
  python cartography_runner.py --aws-only --aws-region us-west-2 --aws-profile myprofile

  # Run K8s only for specific cluster
  python cartography_runner.py --k8s-only --kubeconfig ~/.kube/config --cluster-name my-eks-cluster

  # Run both with custom Neo4j
  python cartography_runner.py \\
    --neo4j-uri bolt://neo4j.example.com:7687 \\
    --neo4j-user neo4j \\
    --neo4j-password mypassword \\
    --aws-profile production \\
    --aws-region us-east-1 \\
    --kubeconfig ~/.kube/config \\
    --cluster-name production-eks

  # Use extended Cartography fork
  python cartography_runner.py \\
    --cartography-path ../cartography-fork \\
    --cluster-name abby-demo-cluster \\
    --aws-region eu-west-1
        """
    )
    
    # Neo4j configuration
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
    
    # AWS configuration
    parser.add_argument(
        '--aws-profile',
        default='1sight',  # Default to the profile used in Terraform config
        help='AWS profile name from ~/.aws/credentials (default: 1sight)'
    )
    parser.add_argument(
        '--aws-region',
        help='AWS region (e.g., us-west-2, us-east-1)'
    )
    
    # Kubernetes configuration
    parser.add_argument(
        '--kubeconfig',
        dest='kubeconfig_path',
        help='Path to kubeconfig file (default: ~/.kube/config)'
    )
    parser.add_argument(
        '--cluster-name',
        dest='k8s_cluster_name',
        help='Specific Kubernetes cluster name to target'
    )
    
    # Module selection
    parser.add_argument(
        '--aws-only',
        action='store_true',
        help='Run only AWS module'
    )
    parser.add_argument(
        '--k8s-only',
        action='store_true',
        help='Run only Kubernetes module'
    )
    
    # Optional configuration
    parser.add_argument(
        '--permission-mapping-file',
        help='Path to AWS permission mapping YAML file'
    )
    
    # Other options
    parser.add_argument(
        '--cartography-path',
        help='Path to extended Cartography fork directory. If provided, uses extended Cartography instead of pip-installed version.'
    )
    parser.add_argument(
        '--skip-k8s-on-error',
        action='store_true',
        help='If Kubernetes sync fails, retry with AWS only instead of exiting'
    )
    parser.add_argument(
        '--verify',
        action='store_true',
        help='Verify prerequisites before running'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Determine which modules to run
    modules = []
    if args.aws_only:
        modules = ['aws']
    elif args.k8s_only:
        modules = ['k8s']
    else:
        modules = ['aws', 'k8s']
    
    # Create runner
    runner = CartographyRunner(
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password,
        aws_profile=args.aws_profile,
        aws_region=args.aws_region,
        kubeconfig_path=args.kubeconfig_path,
        k8s_cluster_name=args.k8s_cluster_name,
        permission_mapping_file=args.permission_mapping_file,
        skip_k8s_on_error=args.skip_k8s_on_error,
        cartography_path=args.cartography_path,
    )
    
    # Verify prerequisites if requested
    if args.verify:
        if not runner.verify_prerequisites():
            logger.error("Prerequisites check failed. Fix issues and try again.")
            sys.exit(1)
    
    # Run Cartography
    try:
        exit_code = runner.run(modules=modules)
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
