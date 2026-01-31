# Impact Analyzer Quick Start 🚀

## What You Built

A tool that analyzes the impact of code changes by querying your Neo4j infrastructure graph!

## Directory Structure

```
impact-analyzer/
├── impact-analyzer          # Executable script
├── src/
│   ├── __init__.py         # Package initialization
│   ├── impact_analyzer.py  # Main orchestrator
│   ├── change_detector.py  # Git diff parser & breaking change detector
│   ├── graph_analyzer.py   # Neo4j graph querier
│   ├── report_generator.py # Markdown/JSON report generator
│   └── cli.py              # CLI interface (unused in standalone mode)
├── requirements.txt         # Python dependencies
├── setup.py                # Package setup
├── README.md               # Full documentation
└── QUICKSTART.md           # This file

demo-clusters/abby/
└── .github/
    └── workflows/
        └── impact-analysis.yml  # GitHub Actions workflow
```

## Quick Test

### 1. Test Locally

```bash
cd /Users/shay/Projects/1sight/playgrounds/demo-clusters/abby

export NEO4J_URI="bolt+s://4c17f303.databases.neo4j.io:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="your-password"

# Analyze a specific file
/Users/shay/Projects/1sight/playgrounds/infra-analyzer/impact-analyzer/impact-analyzer \
  --files services/user-service/src/index.js \
  --repo-path . \
  --format markdown
```

### 2. Test with Git Diff

```bash
# Make a change to a file
echo "// test change" >> services/user-service/src/index.js
git add services/user-service/src/index.js
git commit -m "Test change"

# Analyze the change
../infra-analyzer/impact-analyzer/impact-analyzer \
  --base-ref HEAD~1 \
  --head-ref HEAD \
  --repo-path .
```

### 3. Use in GitHub Actions

The workflow is already set up in `.github/workflows/impact-analysis.yml`.

**Setup:**

1. Go to your GitHub repo settings → Secrets and variables → Actions
2. Add repository secrets:
   - `NEO4J_URI`: `bolt+s://4c17f303.databases.neo4j.io:7687`
   - `NEO4J_USER`: `neo4j`
   - `NEO4J_PASSWORD`: Your password

3. Create a PR and watch the magic happen! 🎩✨

## What It Does

1. **Detects Changes**: Parses git diff or uses specified files
2. **Maps to Services**: Queries Neo4j to find which services are affected
3. **Calculates Blast Radius**: 
   - Who calls this service? (code modules & other services)
   - Transitive dependencies (2-3 hops)
4. **Breaking Change Detection**: Analyzes code for API modifications
5. **Risk Scoring**: Based on dependencies, public exposure, environment
6. **Recommendations**: Suggests deployment strategies

## Sample Output

```markdown
# 🔍 Impact Analysis Report

## 📊 Summary
- **Changed Files:** 1
- **Affected Services:** 1
- **Total Impact Radius:** 5 component(s)
- **Risk Level:** 🟠 MEDIUM

## 💥 Blast Radius

### Service: `user-service`
- **Cluster:** `arn:aws:eks:eu-west-1:135663523041:cluster/abby-demo-cluster`
- **Direct Code Callers:** 1
  - `services/api-gateway/src/index.js` - HTTP http://user-service:80
- **Direct Service Dependencies:** 3
  - `product-service`
  - `api-gateway`

## 💡 Deployment Recommendations

### `user-service`
- **Strategy:** Canary deployment recommended (high dependencies)
- **Testing Priority:** MEDIUM - Contract tests recommended
```

## How to Use in PRs

### Workflow:

1. Developer creates PR
2. GitHub Actions runs `impact-analyzer`
3. Bot comments on PR with impact report
4. Team reviews impact before merging
5. Profit! 💰

### Exit Codes:

- `0`: All clear, safe to merge
- `1`: Breaking changes detected (⚠️ warning)
- `2`: Critical risk level (🔴 requires review)

## Architecture

```
┌─────────────────┐
│   Your PR       │
│  (git diff)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Change Detector │  Parse diff, identify services
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Graph Analyzer  │  Query Neo4j for dependencies
│   (Neo4j DB)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Report Generator│  Generate markdown/JSON
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  GitHub PR      │  Comment with impact report
│   Comment       │
└─────────────────┘
```

## Tips & Tricks

### 1. Save Reports to File

```bash
impact-analyzer --output impact-report.md
```

### 2. JSON Output for Processing

```bash
impact-analyzer --format json --output report.json
```

### 3. Verbose Mode for Debugging

```bash
impact-analyzer --verbose
```

### 4. Test Without Git

```bash
# Analyze specific files without git diff
impact-analyzer --files file1.js file2.py file3.js
```

### 5. Use as Git Hook

Create `.git/hooks/pre-push`:

```bash
#!/bin/bash
echo "Analyzing impact of changes..."
impact-analyzer --base-ref origin/main --head-ref HEAD
```

## Troubleshooting

### "No services found in graph"

Make sure the Neo4j database is populated:

```bash
cd ../infra-analyzer
./infra-analyzer --skip-aws --skip-k8s /path/to/demo-clusters/abby
```

### "Failed to connect to Neo4j"

Check credentials:

```bash
echo $NEO4J_URI
echo $NEO4J_USER
# Password should be set
```

### "No changed files detected"

Are you in a git repository?

```bash
git status
git log --oneline -5
```

## Next Steps

1. ✅ Test locally with different changes
2. ✅ Create a test PR in demo-clusters/abby
3. ✅ Watch the GitHub Action run
4. ✅ See the impact report comment
5. 🎉 Celebrate!

## Support

- Full docs: `README.md`
- Schema docs: `/context/INFRA_SCHEMA.md`
- Main ingester: `../infra-analyzer/`

---

**Built with ❤️ for understanding code impact**
