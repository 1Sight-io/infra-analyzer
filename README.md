# Infrastructure Analyzer

A unified CLI for analyzing infrastructure and applications, extracting relationships, and ingesting them into Neo4j.

## Features

✨ **Unified Interface** - Single CLI for all infrastructure analysis tools  
🔍 **AWS Infrastructure** - Extract EKS clusters, ECR repositories, VPCs, and more  
☸️ **Kubernetes Resources** - Discover pods, services, namespaces, and RBAC  
⎈ **Helm Charts** - Analyze application relationships from Helm deployments  
💻 **Source Code Analysis** - Extract HTTP calls and service dependencies from code  
🔗 **Smart Linking** - Automatically connects infrastructure, applications, and code  
📊 **Neo4j Integration** - Visualize everything as an intuitive graph  
🚀 **One Command** - Run complete analysis with a single command  
⚡ **Flexible** - Run individual modules or everything together  

📖 **[Quick Start](#quick-start)**

## Getting Started

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Ensure prerequisites are available**:
   - Python 3.7+
   - Helm CLI installed (`helm version`)
   - Neo4j database running (default: `bolt://localhost:7687`)
   - AWS credentials configured (for AWS scanning)
   - Kubernetes access configured (for K8s scanning)

3. **Run a quick scan**:
   ```bash
   # Analyze everything in one command (uses default Neo4j: bolt://localhost:7687)
   ./infra-analyzer all /path/to/codebase --aws-region us-west-2 --cluster-name my-cluster
   
   # Or with custom Neo4j connection
   ./infra-analyzer all /path/to/codebase \
     --neo4j-uri bolt://neo4j.example.com:7687 \
     --neo4j-user myuser \
     --neo4j-password mypassword \
     --aws-region us-west-2 \
     --cluster-name my-cluster
   ```

4. **Query Neo4j** to see results:
   - Open Neo4j Browser: http://localhost:7474
   - Run queries to explore relationships

## Unified CLI

The infrastructure analyzer provides a unified command-line interface for all scanning and analysis tools:

```bash
./infra-analyzer <command> [options]
# or
./cli.py <command> [options]
```

### Available Commands

| Command | Description | What It Scans |
|---------|-------------|---------------|
| **`all`** | Run all analyzers in sequence | AWS + Kubernetes + Helm + Code |
| **`cartography`** | Run Cartography infrastructure extraction | AWS + Kubernetes (configurable) |
| **`aws`** | Extract AWS infrastructure only | AWS accounts, EKS, ECR, VPCs, etc. |
| **`k8s`** | Extract Kubernetes infrastructure only | K8s pods, services, namespaces, RBAC |
| **`helm`** | Analyze Helm charts | Application relationships from Helm charts |
| **`code`** | Analyze source code | HTTP calls, service dependencies in Python/JS |

### Quick Start

```bash
# Run everything (recommended workflow)
./infra-analyzer all /path/to/codebase --aws-region us-west-2 --cluster-name my-cluster

# Extract AWS infrastructure only
./infra-analyzer aws --aws-region us-west-2 --aws-profile myprofile

# Extract Kubernetes infrastructure only
./infra-analyzer k8s --cluster-name my-cluster

# Analyze Helm charts only
./infra-analyzer helm /path/to/codebase

# Analyze source code only
./infra-analyzer code /path/to/codebase --language python
```

### Recommended Workflow

The best way to get complete infrastructure visibility is to run the `all` command, which:

1. **Extracts AWS infrastructure** (EKS clusters, ECR repositories, VPCs, etc.)
2. **Extracts Kubernetes resources** (pods, services, namespaces, RBAC)
3. **Analyzes Helm charts** (application relationships, service connections)
4. **Analyzes source code** (HTTP calls, service dependencies)
5. **Links everything together** (code → services → pods → clusters → ECR)

```bash
# Example: Complete analysis of the 'abby' demo cluster
./infra-analyzer all \
  ../demo-clusters/abby \
  --aws-region eu-west-1 \
  --aws-profile default \
  --cluster-name abby-demo-cluster \
  --verbose
```

After running, you'll have a complete graph in Neo4j showing:
- Infrastructure resources (AWS accounts, EKS clusters, VPCs)
- Application resources (pods, services, ingresses from Helm charts)
- Source code modules (Python/JavaScript files)
- Complete relationships (code → services → pods → images → ECR, etc.)

### Common Options

These **global** options work with all commands (must be specified **before** the subcommand):

- `--neo4j-uri` - Neo4j connection URI (default: `bolt://localhost:7687`)
- `--neo4j-user` - Neo4j username (default: `neo4j`)
- `--neo4j-password` - Neo4j password (default: `cartography`)
- `--verbose` - Enable verbose logging

For detailed options for each command, use:

```bash
./infra-analyzer <command> --help
```

**📖 See [USAGE.md](USAGE.md) for comprehensive usage guide and examples.**

### Advanced Examples

```bash
# Run everything with custom settings
./infra-analyzer all /path/to/codebase \
  --aws-region eu-west-1 \
  --aws-profile production \
  --cluster-name prod-cluster \
  --neo4j-uri bolt://neo4j.example.com:7687 \
  --neo4j-password mypassword \
  --verbose

# Run Cartography for AWS only, skip Kubernetes
./infra-analyzer all /path/to/codebase \
  --aws-region us-west-2 \
  --skip-k8s

# Run Kubernetes and Helm, skip AWS
./infra-analyzer all /path/to/codebase \
  --cluster-name my-cluster \
  --skip-aws

# Filter Helm charts by namespace and specific chart
./infra-analyzer helm /path/to/codebase \
  --namespace production \
  --chart api-gateway

# Run Cartography with K8s error handling
./infra-analyzer cartography \
  --aws-region us-west-2 \
  --cluster-name my-cluster \
  --skip-k8s-on-error

# Use custom kubeconfig file
./infra-analyzer k8s \
  --cluster-name my-cluster \
  --kubeconfig ~/.kube/custom-config

# Verify prerequisites before running
./infra-analyzer cartography --verify --aws-region us-west-2
```

## Tools

The CLI wraps these individual tools:

1. **Cartography Runner** - Runs Cartography to extract AWS and Kubernetes (EKS) infrastructure data
2. **Helm Chart Analyzer** - Analyzes Helm charts from a codebase, extracts application-level relationships
3. **Code Analyzer** - Parses source code (Python/JavaScript) to extract HTTP calls and service dependencies

---

## Code Analyzer

Analyzes source code files (Python and JavaScript) to extract HTTP calls and service references, then links them to infrastructure services in Neo4j.

### Features

- 🔍 Parses Python and JavaScript source files
- 🌐 Extracts HTTP calls (requests, fetch, axios, etc.)
- 🔗 Links code modules to Kubernetes services
- 📊 Ingests relationships into Neo4j graph

### Usage

#### Using the Unified CLI (Recommended)

```bash
# Analyze all source code
./infra-analyzer code /path/to/codebase

# Analyze only Python files
./infra-analyzer code /path/to/codebase --language python

# Analyze specific directory
./infra-analyzer code /path/to/codebase --path services/api-gateway
```

#### Using the Standalone Script

```bash
python codebase_analyzer.py /path/to/codebase
```

### Supported Patterns

**Python:**
- `requests.get()`, `requests.post()`, etc.
- `httpx.get()`, `httpx.post()`, etc.
- `urllib.request.urlopen()`
- `http.client.HTTPConnection()`

**JavaScript:**
- `fetch(url)`
- `axios.get()`, `axios.post()`, etc.
- `http.request()`, `http.get()`, `http.post()`

### Neo4j Schema

Creates `CodeModule` nodes and `CALLS_SERVICE` relationships:

```cypher
(CodeModule)-[:CALLS_SERVICE {
  method: "GET",
  url: "http://user-service:80/api/users"
}]->(KubernetesService)
```

### Example Queries

```cypher
// Find all code modules that call a specific service
MATCH (cm:CodeModule)-[r:CALLS_SERVICE]->(s:KubernetesService {name: "user-service"})
RETURN cm.path, r.method, r.url

// Trace from code to infrastructure
MATCH path = (cm:CodeModule)
      -[:CALLS_SERVICE]->(s:KubernetesService)
      -[:TARGETS]->(p:KubernetesPod)
      -[:RESOURCE]->(eks:EKSCluster)
RETURN path
```

---

## Helm Chart Application Relations Analyzer

A service that analyzes Helm charts from a codebase, extracts application-level relationships, and ingests them into Neo4j. This complements the existing infrastructure analysis done by `tf-to-ls/` which handles Terraform→LocalStack→Neo4j.

## Features

- 🔍 Automatically scans directories for Helm charts (directories containing `Chart.yaml`)
- 📦 Renders Helm templates using Helm CLI
- 🔗 Extracts application-level relationships:
  - Pod → Image relations
  - Pod → ServiceAccount relations
  - Service → Pod relations (via selectors)
  - Ingress → Service relations
  - Service → Service relations (from environment variables)
- 📊 Ingests entities and relationships into Neo4j
- 🔗 Links to existing infrastructure nodes (EKSCluster, ECRImage) when available

## Prerequisites

- Python 3.7+
- Helm CLI installed and available in PATH
- Neo4j database running (can use the one from `tf-to-ls/tools/`)
- Neo4j Python driver dependencies

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure Helm CLI is installed:
```bash
helm version
```

If not installed, follow: https://helm.sh/docs/intro/install/

## Usage

### Using the Unified CLI (Recommended)

```bash
# Analyze Helm charts only
./infra-analyzer helm /path/to/codebase

# Use with custom Neo4j settings
./infra-analyzer helm /path/to/codebase \
  --neo4j-uri bolt://localhost:7687 \
  --neo4j-password mypassword
```

### Using the Standalone Script

```bash
python helm_analyzer.py /absolute/path/to/codebase
```

### Options

- `--neo4j-uri URL`: Specify Neo4j connection URI (default: `bolt://localhost:7687`)
- `--neo4j-user USER`: Neo4j username (default: `neo4j`)
- `--neo4j-password PASSWORD`: Neo4j password (default: `cartography`)
- `--namespace NAMESPACE`: Filter by Kubernetes namespace (optional)
- `--chart CHART_NAME`: Analyze specific chart only (optional, matches by name)

### Examples

```bash
# Analyze all Helm charts in demo-clusters/abby
python helm_analyzer.py /Users/shay/Projects/1sight/playgrounds/demo-clusters/abby

# Use custom Neo4j settings
python helm_analyzer.py /path/to/codebase \
  --neo4j-uri bolt://localhost:7687 \
  --neo4j-user neo4j \
  --neo4j-password cartography

# Filter by namespace
python helm_analyzer.py /path/to/codebase --namespace production

# Analyze specific chart only
python helm_analyzer.py /path/to/codebase --chart api-gateway
```

## How It Works

1. **Scanning**: Recursively scans the provided directory for `Chart.yaml` files
2. **Rendering**: For each chart found:
   - Runs `helm template` to render templates with values
   - Parses rendered YAML into Kubernetes resources
3. **Extraction**: Extracts entities and relationships:
   - **From Deployments**: Pod references (for linking), images, service accounts
   - **From Services**: Service definitions, selectors, ports
   - **From Ingress**: External exposure, backend services
   - **From Environment Variables**: Service-to-service connections
4. **Ingestion**: Creates nodes and relationships in Neo4j:
   - **Does NOT create Pod nodes** - Pods come from Cartography's actual cluster state
   - Creates nodes: `KubernetesService`, `KubernetesIngress`, `Image`, `HelmChart`, etc.
   - Links to existing `KubernetesPod` nodes from Cartography
   - Creates relationships: `USES_IMAGE`, `TARGETS`, `CONNECTS_TO`, `EXPOSED_VIA`, etc.
   - Links to existing infrastructure nodes (EKSCluster, ECRImage) when possible

**Important**: This tool should be run **after** Cartography has synced the Kubernetes cluster state. It links Helm chart resources to the actual Pods discovered by Cartography.

## Directory Structure

```
infra-analyzer/
├── infra-analyzer           # Main CLI wrapper (executable) - START HERE
├── cli.py                   # Unified CLI implementation
├── USAGE.md                 # Comprehensive usage guide
├── cartography_runner.py    # Cartography runner for AWS/K8s extraction
├── helm_analyzer.py         # Helm chart analyzer entry point
├── helm_parser.py           # Helm chart discovery and template rendering
├── k8s_extractor.py         # Kubernetes resource parsing and relation extraction
├── codebase_analyzer.py     # Code analyzer entry point
├── code_analyzer.py         # Source code parsing (Python/JavaScript)
├── code_ingester.py         # Code analysis Neo4j ingestion
├── neo4j_ingester.py        # Neo4j connection and data ingestion
├── requirements.txt         # Python dependencies
└── README.md                # This file
```

### Module Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Unified CLI (cli.py)                     │
│          Single entry point for all operations              │
└─────────────────────────────────────────────────────────────┘
                            │
           ┌────────────────┼─────────────────┐
           │                │                 │
           ▼                ▼                 ▼
    ┌───────────┐   ┌──────────────┐  ┌────────────┐
    │   Helm    │   │ Cartography  │  │    Code    │
    │ Analyzer  │   │   Runner     │  │  Analyzer  │
    └───────────┘   └──────────────┘  └────────────┘
           │                │                 │
           │         ┌──────┴──────┐          │
           │         │             │          │
           ▼         ▼             ▼          ▼
    ┌──────────┐  ┌─────┐      ┌─────┐  ┌──────────┐
    │  Helm    │  │ AWS │      │ K8s │  │  Source  │
    │  Charts  │  │     │      │     │  │   Code   │
    └──────────┘  └─────┘      └─────┘  └──────────┘
           │         │             │         │
           └─────────┴─────────────┴─────────┘
                         │
                         ▼
                ┌─────────────────┐
                │   Neo4j Graph   │
                │    Database     │
                └─────────────────┘
          
          Relationships:
          Code → Services → Pods → Clusters → ECR
```

## Neo4j Schema

The service creates nodes and relationships compatible with Cartography's Kubernetes schema. See `context/INFRA_SCHEMA.md` for complete schema documentation.

### Key Entities

- `KubernetesPod` - **NOT created by this tool** - Pods come from Cartography's actual cluster state. This tool links to existing Pods.
- `KubernetesService` - Kubernetes services (created from Helm charts)
- `KubernetesIngress` - Kubernetes ingress resources (created from Helm charts)
- `KubernetesNamespace` - Kubernetes namespaces
- `KubernetesServiceAccount` - Kubernetes service accounts
- `Image` / `ContainerImage` - Container images (can link to ECRImage)
- `HelmChart` - Helm chart metadata

### Key Relationships

- `USES_IMAGE` - Pod → Image
- `TARGETS` - Service → Pod
- `CONNECTS_TO` - Service → Service (via env vars)
- `EXPOSED_VIA` - Ingress → Service
- `USES_SERVICE_ACCOUNT` - Pod → ServiceAccount
- `BELONGS_TO_CHART` - Resources → HelmChart
- `CONTAINS` - Namespace → Resources
- `LINKED_TO` - Image → ECRImage (when matched)

## Integration with Cartography

**Workflow**: Run Cartography first to sync actual Kubernetes cluster state, then run this tool to link Helm charts to the discovered resources.

### Using the Unified CLI (Recommended)

Run everything in one command:

```bash
./infra-analyzer all /path/to/codebase --aws-region eu-west-1 --cluster-name abby-demo-cluster
```

### Manual Steps

1. **First, run Cartography** to sync Kubernetes cluster state:
   ```bash
   ./infra-analyzer cartography --cluster-name abby-demo-cluster --aws-region eu-west-1
   # OR
   python cartography_runner.py --cluster-name abby-demo-cluster --aws-region eu-west-1
   ```

2. **Then, run Helm analyzer** to link Helm charts to existing Pods:
   ```bash
   ./infra-analyzer helm /path/to/codebase
   # OR
   python helm_analyzer.py /path/to/codebase
   ```

The Helm analyzer will:
- Link to existing `KubernetesPod` nodes created by Cartography (by namespace and name)
- Create `KubernetesService` and `KubernetesIngress` nodes from Helm charts
- Link Services to existing Pods via selectors
- Link HelmChart to existing Pods

## Integration with Existing Infrastructure

The service automatically links application resources to infrastructure when possible:

- **Images → ECRImage**: Matches container images to ECR images by repository and tag
- **Pods → EKSCluster**: Already linked by Cartography
- **Services → LoadBalancerV2**: Can be linked for LoadBalancer type services (requires DNS matching)

## Troubleshooting

### Helm CLI not found
- Ensure Helm is installed: `helm version`
- Install from: https://helm.sh/docs/intro/install/

### Neo4j connection issues
- Check if Neo4j is running: `docker ps | grep neo4j`
- Verify connection settings (URI, username, password)
- Check Neo4j logs: `docker logs neo4j`

### No charts found
- Verify the codebase path contains directories with `Chart.yaml` files
- Check that the path is absolute or relative to current directory

### Template rendering fails
- Verify Helm chart is valid: `helm lint /path/to/chart`
- Check that `values.yaml` exists and is valid YAML
- Review Helm template syntax

## Example Relationship Chains

After ingestion, you can query Neo4j for relationship chains like:

```cypher
// Pod → Service → Pod → Service → Image → ECRImage
MATCH (p1:KubernetesPod)-[:TARGETS]-(s1:KubernetesService)-[:TARGETS]-(p2:KubernetesPod)
      -[:USES_IMAGE]-(img:Image)-[:LINKED_TO]-(ecr:ECRImage)
RETURN p1, s1, p2, img, ecr

// Service connections via env vars
MATCH (s1:KubernetesService)-[r:CONNECTS_TO]->(s2:KubernetesService)
RETURN s1.name, s2.name, r.env_var, r.url

// All resources in a Helm chart
MATCH (hc:HelmChart {name: 'api-gateway'})-[:BELONGS_TO_CHART]->(resource)
RETURN hc, resource
```

## Notes

- The service uses the same Neo4j database as Cartography (from `tf-to-ls/`)
- All nodes include `firstseen` and `lastupdated` timestamps
- Resources are linked to their Helm charts via `BELONGS_TO_CHART` relationships
- The service continues processing even if individual charts fail

---

## Cartography Runner

A tool that runs [Cartography](https://cartography-cncf.github.io/cartography/) to extract AWS and Kubernetes (EKS) infrastructure data into Neo4j. Cartography consolidates infrastructure assets and relationships in an intuitive graph view.

### Features

- 🔍 Extracts AWS infrastructure (EKS clusters, ECR repositories, VPCs, security groups, etc.)
- ☸️ Extracts Kubernetes resources from EKS clusters (pods, services, namespaces, RBAC, etc.)
- 🔗 Discovers relationships between AWS and Kubernetes resources
- 📊 Ingests everything into Neo4j for graph analysis

### Prerequisites

1. **Cartography installed**:
   ```bash
   pip install cartography
   ```

2. **AWS credentials configured**:
   - AWS CLI configured with credentials (`~/.aws/credentials`)
   - Or set `AWS_PROFILE` environment variable
   - Required permissions: `SecurityAudit` managed policy (minimum)
   - For Inspector2: `AmazonInspector2ReadOnlyAccess`

3. **Kubernetes access**:
   - Kubeconfig file with access to EKS cluster(s)
   - Default location: `~/.kube/config`
   - Or specify with `--kubeconfig` option
   - Required RBAC: read access to cluster resources (pods, services, namespaces, etc.)

4. **Neo4j database running**:
   - Default: `bolt://localhost:7687`
   - Or specify with `--neo4j-uri`

### Installation

Install dependencies (including Cartography):

```bash
pip install -r requirements.txt
```

### Usage

#### Using the Unified CLI (Recommended)

```bash
# Run Cartography with both AWS and K8s
./infra-analyzer cartography --aws-region us-west-2 --cluster-name my-cluster

# Extract AWS infrastructure only
./infra-analyzer aws --aws-region us-west-2 --aws-profile myprofile

# Extract Kubernetes infrastructure only
./infra-analyzer k8s --cluster-name my-cluster
```

#### Using the Standalone Script

Run Cartography with default settings (extracts both AWS and Kubernetes):

```bash
python cartography_runner.py
```

#### AWS Only

Extract only AWS infrastructure:

```bash
python cartography_runner.py --aws-only --aws-region us-west-2 --aws-profile myprofile
```

#### Kubernetes Only

Extract only Kubernetes resources:

```bash
python cartography_runner.py --k8s-only --cluster-name abby-demo-cluster
```

#### Full Example

Extract both AWS and Kubernetes with custom configuration:

```bash
python cartography_runner.py \
  --neo4j-uri bolt://neo4j.example.com:7687 \
  --neo4j-user neo4j \
  --neo4j-password mypassword \
  --aws-profile production \
  --aws-region us-east-1 \
  --kubeconfig ~/.kube/config \
  --cluster-name production-eks
```

### Options

#### Neo4j Configuration

- `--neo4j-uri URI`: Neo4j connection URI (default: `bolt://localhost:7687`)
- `--neo4j-user USER`: Neo4j username (default: `neo4j`)
- `--neo4j-password PASSWORD`: Neo4j password (default: `cartography`)

#### AWS Configuration

- `--aws-profile PROFILE`: AWS profile name from `~/.aws/credentials`
- `--aws-region REGION`: AWS region (e.g., `us-west-2`, `us-east-1`)

#### Kubernetes Configuration

- `--kubeconfig PATH`: Path to kubeconfig file (default: `~/.kube/config`)
- `--cluster-name NAME`: Specific Kubernetes cluster name to target

#### Module Selection

- `--aws-only`: Run only AWS module
- `--k8s-only`: Run only Kubernetes module
- (default: run both AWS and Kubernetes)

#### Other Options

- `--permission-mapping-file PATH`: Path to AWS permission mapping YAML file (optional)
- `--skip-k8s-on-error`: If Kubernetes sync fails (e.g., cluster unreachable), retry with AWS only instead of exiting
- `--verify`: Verify prerequisites before running
- `--verbose`, `-v`: Enable verbose logging

### What Gets Extracted

#### AWS Resources

- **EKSCluster**: EKS clusters with metadata (version, status, region)
- **ECRImage**: Container images in ECR repositories
- **ECRRepository**: ECR repositories
- **AWSVpc**: VPCs and networking
- **EC2Subnet**: Subnets
- **EC2SecurityGroup**: Security groups
- **LoadBalancerV2**: Application and Network Load Balancers
- **AWSAccount**: AWS account information
- **IAM roles, policies, and relationships**

#### Kubernetes Resources

- **KubernetesPod**: Pods and their metadata
- **KubernetesService**: Services
- **KubernetesNamespace**: Namespaces
- **KubernetesServiceAccount**: Service accounts
- **KubernetesClusterRole**: Cluster roles
- **KubernetesRoleBinding**: Role bindings
- **RBAC relationships**: Who can do what

#### Relationships

- **RESOURCE**: Ownership relationships (Account → Cluster → Pods)
- **MEMBER_OF_AWS_VPC**: Subnet → VPC
- **USES_IMAGE**: Pod → Image → ECRImage
- **TARGETS**: Service → Pod
- And many more...

### Verification

Check prerequisites before running:

```bash
python cartography_runner.py --verify
```

### Troubleshooting

#### Cartography not found

```bash
pip install cartography
```

Or see: https://cartography-cncf.github.io/cartography/

#### AWS credentials issues

- Verify AWS credentials: `aws sts get-caller-identity`
- Check profile exists: `aws configure list --profile myprofile`
- Ensure required permissions are attached

#### Kubernetes access issues

- Verify kubeconfig: `kubectl cluster-info`
- Check cluster access: `kubectl get nodes`
- Ensure RBAC permissions allow reading resources
- **DNS resolution errors**: If you see errors like "Failed to resolve 'xxx.eks.amazonaws.com'", the cluster endpoint may be:
  - Private and requires VPN or network access
  - The kubeconfig may be outdated (run `aws eks update-kubeconfig --name <cluster-name>`)
  - The cluster may not exist anymore
- **Workaround**: Use `--skip-k8s-on-error` to run AWS sync only if Kubernetes sync fails:
  ```bash
  python cartography_runner.py --skip-k8s-on-error --aws-region us-west-2
  ```

#### Neo4j connection issues

- Check if Neo4j is running: `docker ps | grep neo4j`
- Verify connection: `neo4j-admin dbms check-connectivity`
- Check firewall/network access

### Integration with Helm Analyzer

The Cartography runner extracts **infrastructure** (AWS, EKS), while the Helm analyzer extracts **application** resources (from Helm charts). Together they provide:

1. **Infrastructure layer**: AWS accounts, EKS clusters, ECR repositories, VPCs, etc.
2. **Application layer**: Pods, services, ingresses from Helm charts
3. **Cross-layer links**: Pods → EKS clusters, Images → ECR images

Run both tools to get a complete picture:

**Using the Unified CLI (Recommended)**:

```bash
./infra-analyzer all /path/to/codebase --aws-region us-west-2 --cluster-name my-cluster
```

**Manual steps**:

```bash
# 1. Extract infrastructure (AWS + EKS)
./infra-analyzer cartography --aws-region us-west-2 --cluster-name my-cluster

# 2. Extract applications (Helm charts)
./infra-analyzer helm /path/to/codebase
```

### Example Queries

After running Cartography, query Neo4j for infrastructure insights:

```cypher
// Find all EKS clusters
MATCH (cluster:EKSCluster)
RETURN cluster.name, cluster.region, cluster.version

// Find pods in a specific cluster
MATCH (cluster:EKSCluster {name: 'my-cluster'})-[:RESOURCE]->(pod:KubernetesPod)
RETURN pod.name, pod.namespace

// Find all ECR images used by pods
MATCH (pod:KubernetesPod)-[:USES_IMAGE]->(img:Image)-[:LINKED_TO]->(ecr:ECRImage)
RETURN pod.name, ecr.repository, ecr.tag

// Find security groups attached to EKS clusters
MATCH (cluster:EKSCluster)-[:RESOURCE]->(sg:EC2SecurityGroup)
RETURN cluster.name, sg.name, sg.id
```

### References

- [Cartography Documentation](https://cartography-cncf.github.io/cartography/)
- [Cartography AWS Module](https://cartography-cncf.github.io/cartography/modules/aws/config.html)
- [Cartography Kubernetes Module](https://cartography-cncf.github.io/cartography/modules/kubernetes/config.html)
- [Cartography Schema](https://cartography-cncf.github.io/cartography/schema.html)

---

## Additional Resources

- **[Helm Documentation](https://helm.sh/docs/)** - Official Helm docs
- **[Neo4j Cypher Reference](https://neo4j.com/docs/cypher-manual/current/)** - Query language guide

## Support

For issues or questions:

1. Run with `--verbose` flag for detailed logging
2. Use `--verify` flag to check prerequisites
3. Review the troubleshooting sections in this README

## Contributing

Contributions are welcome! The CLI is designed to be extensible:

- Add new subcommands in `cli.py`
- Create new analyzer modules following the existing pattern
- Update documentation in README.md and USAGE.md

---

**Happy Analyzing! 🚀**
