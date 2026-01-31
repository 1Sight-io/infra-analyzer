#!/usr/bin/env python3
"""
Helm Chart Parser
Discovers Helm charts in a codebase and renders their templates.
"""

import os
import subprocess
import yaml
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class HelmChart:
    """Represents a Helm chart with its metadata and rendered resources."""
    
    def __init__(self, chart_path: Path, codebase_path: Path):
        self.chart_path = chart_path
        self.codebase_path = codebase_path
        self.chart_yaml_path = chart_path / "Chart.yaml"
        self.values_yaml_path = chart_path / "values.yaml"
        self.metadata: Optional[Dict] = None
        self.values: Optional[Dict] = None
        self.rendered_resources: List[Dict] = []
        
    def load_metadata(self) -> Dict:
        """Load Chart.yaml metadata."""
        if self.metadata is not None:
            return self.metadata
            
        if not self.chart_yaml_path.exists():
            raise FileNotFoundError(f"Chart.yaml not found: {self.chart_yaml_path}")
        
        with open(self.chart_yaml_path, 'r') as f:
            self.metadata = yaml.safe_load(f) or {}
        
        return self.metadata
    
    def load_values(self) -> Dict:
        """Load values.yaml."""
        if self.values is not None:
            return self.values
        
        self.values = {}
        if self.values_yaml_path.exists():
            with open(self.values_yaml_path, 'r') as f:
                self.values = yaml.safe_load(f) or {}
        
        return self.values
    
    def render_templates(self) -> List[Dict]:
        """Render Helm templates using helm template command."""
        if self.rendered_resources:
            return self.rendered_resources
        
        try:
            # Run helm template command
            cmd = [
                "helm", "template",
                str(self.chart_path.name),
                str(self.chart_path),
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.chart_path.parent,
                check=True
            )
            
            # Parse the rendered YAML (may contain multiple documents)
            rendered_yaml = result.stdout
            resources = []
            
            for doc in yaml.safe_load_all(rendered_yaml):
                if doc:  # Skip empty documents
                    resources.append(doc)
            
            self.rendered_resources = resources
            return resources
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to render Helm chart {self.chart_path}: {e.stderr}")
            raise
        except FileNotFoundError:
            logger.error("Helm CLI not found. Please install Helm: https://helm.sh/docs/intro/install/")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse rendered YAML for {self.chart_path}: {e}")
            raise
    
    def get_relative_path(self) -> str:
        """Get relative path from codebase root."""
        return str(self.chart_path.relative_to(self.codebase_path))


def find_helm_charts(codebase_path: Path) -> List[HelmChart]:
    """
    Recursively scan codebase for Helm charts.
    A Helm chart is identified by the presence of Chart.yaml file.
    
    Args:
        codebase_path: Root path to scan
        
    Returns:
        List of HelmChart objects
    """
    charts = []
    codebase_path = Path(codebase_path).resolve()
    
    if not codebase_path.exists():
        raise ValueError(f"Codebase path does not exist: {codebase_path}")
    
    # Walk through directories looking for Chart.yaml
    for root, dirs, files in os.walk(codebase_path):
        # Skip hidden directories and common ignore patterns
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'venv', '__pycache__', '.git']]
        
        # Check if this directory has Chart.yaml
        chart_yaml = Path(root) / "Chart.yaml"
        if chart_yaml.exists():
            chart_path = Path(root)
            try:
                chart = HelmChart(chart_path, codebase_path)
                chart.load_metadata()
                charts.append(chart)
                logger.info(f"Found Helm chart: {chart.get_relative_path()}")
            except Exception as e:
                logger.warning(f"Skipping invalid chart at {chart_path}: {e}")
    
    return charts


def render_chart(chart: HelmChart) -> Tuple[Dict, List[Dict]]:
    """
    Render a Helm chart and return metadata and resources.
    
    Args:
        chart: HelmChart object
        
    Returns:
        Tuple of (metadata dict, list of resource dicts)
    """
    metadata = chart.load_metadata()
    resources = chart.render_templates()
    
    return metadata, resources
