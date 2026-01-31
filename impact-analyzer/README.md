# Impact Analyzer 🔍

Analyze the impact of code changes on your infrastructure using a Neo4j graph database.

## Overview

Impact Analyzer helps you understand:
- **Blast Radius**: What services and components are affected by your changes
- **Helm Chart Changes**: Infrastructure changes in Kubernetes deployments
- **Breaking Changes**: Potential API contract violations
- **Risk Assessment**: Risk scores based on dependencies and exposure
- **Deployment Recommendations**: Suggested deployment strategies

## Features

- 🎯 **Diff-Based Analysis**: Analyze git diffs without scanning entire codebase
- ⎈ **Helm Chart Detection**: Automatically detects and analyzes Helm chart changes
- 🐳 **Container Image Impact**: Shows which pods and services are affected by image changes
- 🌐 **Ingress Analysis**: Critical analysis of external-facing changes
- 🔒 **Network Policy Impact**: Identifies network security implications
- 📊 **Graph-Powered**: Uses Neo4j infrastructure graph for accurate dependency tracking
- 🚨 **Breaking Change Detection**: Static analysis for API and infrastructure modifications
- 💥 **Blast Radius Calculation**: Shows direct and transitive impacts
- 📝 **GitHub-Ready Reports**: Markdown output perfect for PR comments
- 🎲 **Risk Scoring**: Quantifies deployment risk
- 💡 **Smart Recommendations**: Suggests deployment strategies

## Installation

### Option 1: Direct Usage (No Installation)

```bash
# From your project directory
export NEO4J_URI="bolt+s://your-neo4j.databases.neo4j.io:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="your-password"

/path/to/impact-analyzer/impact-analyzer --base-ref origin/main --head-ref HEAD
```

### Option 2: Install Globally

```bash
cd impact-analyzer
pip install -e .

# Now you can use it from anywhere
impact-analyzer --help
```

### Option 3: Docker (Coming Soon)

```bash
docker pull yourusername/impact-analyzer
docker run -e NEO4J_URI=... impact-analyzer
```

## Prerequisites

1. **Neo4j Database** with infrastructure graph (populated by `infra-analyzer`)
2. **Git Repository** with code changes to analyze
3. **Python 3.8+**

## Helm Chart Analysis

The impact analyzer now automatically detects and analyzes Helm chart changes, providing comprehensive infrastructure impact analysis:

### What Gets Detected

- **Chart.yaml**: Metadata changes (version bumps, dependency updates)
- **values.yaml**: Configuration changes that affect deployments
- **templates/**: Kubernetes resource template modifications
  - Deployment templates (CRITICAL severity)
  - Service templates (HIGH severity)
  - Ingress templates (HIGH severity)
  - ConfigMap/Secret templates (MEDIUM/CRITICAL severity)
  - Network policies and other resources

### Impact Analysis Includes

1. **Chart-Level Impact**
   - All services, pods, and ingresses in the chart
   - Dependent services that call your chart's services
   - External code that calls your services
   - Public exposure via ingresses

2. **Container Image Impact**
   - Which pods will be redeployed
   - ECR repository tracking
   - Services exposing the pods
   - Downstream dependencies

3. **Ingress Changes** (CRITICAL)
   - External-facing hostname and path changes
   - Load balancer associations
   - Backend service mappings
   - External callers from your codebase

4. **Network Policy Impact**
   - Which pods are affected
   - Other pods using same policies
   - Ingress/egress rule changes

### Example Queries Run Against Neo4j

The analyzer runs sophisticated Cypher queries to understand impact:

```cypher
// Find all resources in a changed Helm chart
MATCH (hc:HelmChart {name: $chartName})
MATCH (hc)-[:BELONGS_TO_CHART]->(resource)
RETURN resource

// Find services that depend on this chart's services
MATCH (hc:HelmChart)-[:BELONGS_TO_CHART]->(svc:KubernetesService)
MATCH (dependent:KubernetesService)-[:CONNECTS_TO]->(svc)
RETURN dependent

// Find external code calling chart services
MATCH (hc:HelmChart)-[:BELONGS_TO_CHART]->(svc:KubernetesService)
MATCH (code:CodeModule)-[:CALLS_SERVICE]->(svc)
RETURN code
```

## Usage

### Basic Usage

```bash
# Analyze changes between branches
impact-analyzer \
  --neo4j-uri bolt+s://your-instance.neo4j.io:7687 \
  --neo4j-user neo4j \
  --neo4j-password your-password \
  --base-ref origin/main \
  --head-ref HEAD
```

### Analyze Specific Files

```bash
# Analyze only specific files (useful for testing)
impact-analyzer \
  --files services/user-service/src/index.js \
          services/api-gateway/src/routes.js
```

### Generate JSON Report

```bash
# Output JSON instead of Markdown
impact-analyzer \
  --format json \
  --output report.json
```

### Save to File

```bash
# Save markdown report to file
impact-analyzer --output impact-report.md
```

## Environment Variables

Set these to avoid passing credentials on command line:

```bash
export NEO4J_URI="bolt+s://4c17f303.databases.neo4j.io:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="your-password"

# Now you can run without credentials
impact-analyzer --base-ref origin/main --head-ref HEAD
```

## GitHub Actions Integration

### Setup

1. **Add secrets to your repository:**
   - `NEO4J_URI`
   - `NEO4J_USER`
   - `NEO4J_PASSWORD`

2. **Create workflow file** `.github/workflows/impact-analysis.yml`:

```yaml
name: Impact Analysis

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  analyze:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Need full history for git diff
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install neo4j
      
      - name: Run Impact Analysis
        env:
          NEO4J_URI: ${{ secrets.NEO4J_URI }}
          NEO4J_USER: ${{ secrets.NEO4J_USER }}
          NEO4J_PASSWORD: ${{ secrets.NEO4J_PASSWORD }}
        run: |
          # Download or checkout impact-analyzer
          git clone https://github.com/yourusername/infra-analyzer.git /tmp/infra-analyzer
          
          # Run analysis
          /tmp/infra-analyzer/impact-analyzer/impact-analyzer \
            --base-ref origin/${{ github.base_ref }} \
            --head-ref HEAD \
            --output impact-report.md
      
      - name: Comment on PR
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const report = fs.readFileSync('impact-report.md', 'utf8');
            
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: report
            });
      
      - name: Check for breaking changes
        run: |
          # Exit with error if breaking changes detected
          if grep -q "⚠️ Potential Breaking Changes" impact-report.md; then
            echo "::warning::Breaking changes detected!"
            exit 1
          fi
```

### Alternative: Use as Submodule

```bash
# In your project repo
git submodule add https://github.com/yourusername/infra-analyzer.git tools/infra-analyzer

# In GitHub Actions
- name: Checkout submodules
  run: git submodule update --init --recursive

- name: Run Impact Analysis
  run: ./tools/infra-analyzer/impact-analyzer/impact-analyzer ...
```

## Output Examples

### Markdown Report

```markdown
# 🔍 Impact Analysis Report

**Generated:** 2026-01-31T19:00:00

## 📊 Summary

- **Changed Files:** 3
- **Helm Charts Changed:** 1
- **Affected Services:** 2
- **Total Impact Radius:** 7 component(s)
- **Risk Level:** 🔴 CRITICAL

## ⎈ Helm Chart Changes

Detected 2 change(s) in Helm charts:

### Chart: `user-service`
- **DEPLOYMENT_TEMPLATE** - 🔴 CRITICAL
  - File: `templates/deployment.yaml`
- **VALUES** - 🟡 HIGH
  - File: `values.yaml`

## 📦 Helm Chart Impact Analysis

### Chart: `user-service`
⚠️ **Contains Publicly Exposed Services**
- **Services:** `user-service`
- **Pods/Deployments:** 1
- **Ingresses:** `user-service-ingress`
- **Dependent Services:** 1
  - `api-gateway` depends on `user-service`
- **External Code Callers:** 2
  - `services/api-gateway/src/routes.js` → `user-service`

## 🐳 Container Image Impacts

### Pod: `user-service` (Chart: `user-service`)
- **Namespace:** `production`
- **Container Images:**
  - `123456789.dkr.ecr.us-west-2.amazonaws.com/user-service:v1.2.3` (ECR)
- **Exposed via Services:** `user-service`
- **Dependent Services:** `api-gateway`

## 🌐 Ingress Changes (External Impact)

### Ingress: `user-service-ingress` 🔴 CRITICAL
- **Namespace:** `production`
- **Hosts:** ["api.example.com"]
- **Paths:** ["/users", "/auth"]
- **Load Balancer:** `k8s-prod-abcd1234.elb.amazonaws.com`
- **Backend Services:**
  - `user-service` (1 pod(s))

## 📝 Changed Code Components

### `services/user-service/src/index.js`
- **Helm Chart:** `user-service`
- **Owns Services:** `user-service`
- **Calls Services:** `postgresql`, `redis`

## 💥 Blast Radius

### Service: `user-service`
⚠️ **Publicly Exposed via Ingress**
- **Direct Code Callers:** 2
  - `services/api-gateway/src/routes.js` - GET http://user-service:8080/api/users
- **Direct Service Dependencies:** 1
  - `api-gateway`
```

### JSON Report

```json
{
  "timestamp": "2026-01-31T19:00:00",
  "summary": {
    "changedFilesCount": 2,
    "affectedServicesCount": 1,
    "totalImpactCount": 5,
    "overallRiskLevel": "HIGH"
  },
  "blastRadius": [...],
  "breakingChanges": [...],
  "riskAnalysis": [...]
}
```

## Exit Codes

- `0`: Success, no breaking changes, low risk
- `1`: Breaking changes detected
- `2`: Critical risk level detected
- `130`: Interrupted by user

## How It Works

1. **Change Detection**: Parses git diff to find modified files
2. **Helm Chart Detection**: Identifies changes to Chart.yaml, values.yaml, and templates
3. **Component Mapping**: Queries Neo4j graph to map files and charts to services
4. **Infrastructure Impact**: Analyzes impact on:
   - Container images and deployments
   - Ingress rules and external exposure
   - Network policies and security
   - Service dependencies
5. **Blast Radius**: Traverses dependency graph to find affected components
6. **Breaking Analysis**: Static code analysis for API and infrastructure changes
7. **Risk Calculation**: Scores risk based on dependencies, exposure, and change type
8. **Report Generation**: Creates comprehensive markdown or JSON report

## Architecture

```
┌─────────────────┐
│ Change Detector │  → Parse git diff, identify services
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Graph Analyzer  │  → Query Neo4j for dependencies
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Report Generator│  → Generate markdown/JSON
└─────────────────┘
```

## Requirements

- Python 3.8+
- Neo4j 5.0+ database with infrastructure graph
- Git repository

## Configuration

### Neo4j Connection

The analyzer supports all Neo4j connection types:
- `bolt://` - Unencrypted
- `bolt+s://` - Encrypted (SSL/TLS)
- `neo4j://` - Routing unencrypted
- `neo4j+s://` - Routing encrypted

For Neo4j Aura, use `bolt+s://` or `neo4j+s://`.

### SSL Certificate Verification

The analyzer automatically disables SSL certificate verification for `bolt+s://` and `neo4j+s://` connections to work with Neo4j Aura and self-signed certificates.

## Troubleshooting

### "No services found in graph"

Make sure you've run `infra-analyzer` to populate the Neo4j database first:

```bash
cd infra-analyzer
./infra-analyzer all /path/to/your/code
```

### "Failed to connect to Neo4j"

Check your Neo4j credentials and URI:

```bash
# Test connection
echo "RETURN 1" | cypher-shell -a $NEO4J_URI -u $NEO4J_USER -p $NEO4J_PASSWORD
```

### "No changed files detected"

Make sure you're in a git repository and the refs exist:

```bash
git log origin/main..HEAD --oneline
```

## Development

```bash
# Install in development mode
pip install -e .

# Run tests (coming soon)
pytest

# Lint
pylint src/
```

## Related Tools

- **infra-analyzer**: Populates the Neo4j graph with infrastructure and code data
- **cartography**: Extracts AWS and Kubernetes infrastructure

## License

MIT

## Contributing

Contributions welcome! Please open an issue or PR.

## Support

For issues and questions:
- GitHub Issues: https://github.com/yourusername/infra-analyzer/issues
- Documentation: https://docs.example.com
