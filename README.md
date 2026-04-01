# Project Aura

**Autonomous AI-powered security remediation for enterprise codebases.**

[![License: BSL 1.1](https://img.shields.io/badge/License-BSL_1.1-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![Tests](https://img.shields.io/badge/Tests-23%2C165+-brightgreen.svg)](tests/)
[![Lines of Code](https://img.shields.io/badge/Lines_of_Code-439K+-informational.svg)](docs/PROJECT_STATUS.md)

Project Aura detects vulnerabilities, generates production-ready patches, validates fixes in isolated sandboxes, and queues them for human approval -- all autonomously. Unlike traditional security scanners that stop at detection, Aura provides end-to-end remediation through a multi-agent AI system built for regulated industries.

[Documentation](docs/product/getting-started/index.md) | [Quick Start](#quick-start) | [Architecture](#architecture) | [Contributing](CONTRIBUTING.md)

---

## Why Aura?

Traditional security tools identify problems. Aura solves them.

```
Traditional Scanner                          Aura
-------------------                          ----
SQL Injection found in user_service.py:47    SQL Injection found in user_service.py:47
Severity: Critical                           Severity: Critical
Recommendation: Sanitize user input          Patch generated: parameterized query via ORM
                                             Sandbox validation: PASSED (all tests green)
Then what?                                   Awaiting human approval for deployment...
  - Engineer researches the fix
  - Engineer writes the patch
  - Engineer tests the patch
  - Engineer deploys the fix
  - 45 days later...
```

**Key differentiators:**

- **Full remediation, not just detection** -- generates context-aware patches using deep codebase understanding
- **Hybrid GraphRAG architecture** -- combines structural analysis (call graphs, dependencies) with semantic search for comprehensive code context
- **Multi-agent collaboration** -- specialized Coder, Reviewer, and Validator agents with checks and balances
- **Human-in-the-loop governance** -- configurable approval workflows with industry-specific policy presets
- **Sandbox-first validation** -- every patch is tested in network-isolated environments before reaching human reviewers
- **Constitutional AI guardrails** -- 16-principle critique-revision pipeline ensures safe, compliant agent behavior

---

## Architecture

Project Aura uses a layered architecture with specialized AI agents collaborating through structured workflows.

```
                    Vulnerability Detection
                            |
                            v
    +-----------------------------------------------+
    |              HYBRID GRAPHRAG                   |
    |                                                |
    |   Neptune Graph    OpenSearch     BM25         |
    |   (Structure)      (Semantics)   (Keywords)    |
    |        \               |             /         |
    |         \              |            /          |
    |          Three-Way Fusion (RRF)                |
    +------------------------|-----------------------+
                             |
                             v
    +-----------------------------------------------+
    |            MULTI-AGENT SYSTEM                  |
    |                                                |
    |  Orchestrator --> Coder --> Reviewer --> Validator
    +------------------------|-----------------------+
                             |
                             v
    +-----------------------------------------------+
    |           CONSTITUTIONAL AI                    |
    |   Critique (16 principles) --> Revision        |
    +------------------------|-----------------------+
                             |
                             v
    +-----------------------------------------------+
    |          SANDBOX VALIDATION                    |
    |   Syntax | Unit Tests | Security | Performance |
    +------------------------|-----------------------+
                             |
                             v
    +-----------------------------------------------+
    |            HITL APPROVAL                       |
    |   Policy Engine --> Human Review --> Deploy     |
    +-----------------------------------------------+
```

### Core Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| **Agent Orchestrator** | Coordinates remediation workflows | Python, FastAPI |
| **Hybrid GraphRAG** | Deep code understanding via graph + vector retrieval | Neptune (Gremlin), OpenSearch (k-NN) |
| **Multi-Agent System** | Specialized agents for code gen, review, validation | LLMs via AWS Bedrock |
| **Constitutional AI** | Principled safety guardrails for agent outputs | Critique-revision pipeline |
| **Sandbox Network** | Isolated environments for patch validation | ECS Fargate, network isolation |
| **HITL Workflows** | Configurable human approval gates | 4 autonomy levels, 7 policy presets |

### Technology Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Python 3.11+, FastAPI |
| **LLM Integration** | AWS Bedrock (Claude 3.5 Sonnet, Claude 3.5 Haiku) |
| **Graph Database** | AWS Neptune (Gremlin query language) |
| **Vector Search** | AWS OpenSearch with k-NN |
| **Container Orchestration** | AWS EKS with EC2 Managed Node Groups |
| **Infrastructure as Code** | AWS CloudFormation (155 templates) |
| **Frontend** | React 18, TypeScript, Tailwind CSS, Next.js 14 |
| **Service Discovery** | dnsmasq (3-tier architecture with DNSSEC) |

---

## Key Capabilities

### Hybrid GraphRAG

Aura's retrieval architecture combines three methods for comprehensive code understanding:

- **Graph traversal** (Neptune) -- call graphs, dependency chains, inheritance hierarchies
- **Semantic search** (OpenSearch k-NN) -- embedding-based similarity for related patterns
- **Keyword search** (BM25) -- exact identifier and function name matching

Results are fused using Reciprocal Rank Fusion (RRF), achieving 22-25% improvement in retrieval accuracy compared to single-method approaches.

### Multi-Agent System

Specialized agents collaborate through structured message passing:

| Agent | Responsibility |
|-------|----------------|
| **Orchestrator** | Coordinates workflow phases, manages state and checkpoints |
| **Coder** | Generates context-aware patches using LLM capabilities |
| **Reviewer** | Validates patches against OWASP Top 10 and security policies |
| **Validator** | Executes 5-layer validation pipeline in sandboxed environments |
| **Monitor** | Tracks health, performance, token costs, and security metrics |

### Configurable Autonomy

Organizations configure HITL requirements based on compliance needs:

| Autonomy Level | Behavior | Use Case |
|----------------|----------|----------|
| `FULL_HITL` | All changes require approval | CMMC Level 3, maximum oversight |
| `HITL_FINAL` | Approve deployment only | SOX compliance |
| `HITL_CRITICAL` | Approve critical/high severity only | Balanced automation |
| `FULL_AUTONOMOUS` | No approval required | Development environments |

**7 industry presets:** `defense_contractor`, `financial_services`, `healthcare`, `fintech_startup`, `enterprise_standard`, `internal_tools`, `fully_autonomous`

**Guardrails that always require humans:** Production deployments, credential modifications, access control changes, database migrations, infrastructure changes.

### Constitutional AI

All agent outputs pass through a critique-revision pipeline based on [Anthropic's Constitutional AI research](https://arxiv.org/abs/2212.08073):

- **16 principles** across Safety, Compliance, Anti-Sycophancy, Transparency, Helpfulness, and Code Quality
- **Cost-optimized**: Haiku for critique, Sonnet for revision (~85% cost savings)
- **Constructive engagement**: Issues are revised, not just blocked
- **Trust Center dashboard**: Real-time metrics for critique accuracy, revision convergence, and cache hit rate

### AI Optimizations

| Technique | Impact |
|-----------|--------|
| Chain of Draft prompting | 92% token reduction vs. Chain of Thought |
| Semantic caching (OpenSearch k-NN) | 68% cache hit rate |
| Self-reflection (Reflexion-style) | 30% reduction in false positives |
| Selective decoding (JEPA) | 2.85x inference efficiency for routing tasks |
| Titan Neural Memory | Continuous learning from remediation outcomes |
| Recursive context scaling (RLM) | 100x context window expansion for large codebases |

---

## Quick Start

### Prerequisites

- Python 3.11+
- AWS CLI configured with appropriate credentials
- Podman (recommended) or Docker

### Installation

```bash
git clone https://github.com/aenealabs/aura.git
cd aura
pip install -r requirements.txt
```

### Run Tests

```bash
pytest tests/
```

### Deploy to AWS

```bash
# Deploy foundation layer
./deploy/scripts/deploy-foundation-codebuild.sh
```

See the [Installation Guide](docs/product/getting-started/installation.md) for SaaS, Kubernetes, and Podman deployment options, and the [Deployment Guide](docs/deployment/DEPLOYMENT_GUIDE.md) for complete AWS infrastructure setup.

---

## Deployment Options

| Option | Setup Time | Best For |
|--------|-----------|----------|
| **Cloud (SaaS)** | Same day | Teams wanting immediate value without infrastructure overhead |
| **Self-Hosted (Kubernetes)** | 1-2 weeks | Organizations with data residency requirements or existing EKS clusters |
| **Self-Hosted (Podman)** | 1 day | Air-gapped deployments, small teams, proof-of-concept |

All deployment options support AWS GovCloud regions for government workloads.

---

## Security and Compliance

### Data Protection

| Control | Implementation |
|---------|----------------|
| Encryption at rest | AES-256 via AWS KMS customer-managed keys |
| Encryption in transit | TLS 1.3 for all communications |
| Network isolation | VPC endpoints, no public internet exposure |
| Secrets management | AWS Secrets Manager, no hardcoded credentials |
| Container security | Private ECR base images, vulnerability scanning |

### Compliance Posture

| Framework | Status |
|-----------|--------|
| NIST 800-53 | Technical controls implemented |
| SOX | Controls implemented |
| GovCloud Ready | 100% (all deployed services compatible) |
| CMMC Level 2 | Infrastructure complete, organizational controls pending |
| FedRAMP High | Authorization path available |

### Security Services

- Input validation (SQL injection, XSS, SSRF, prompt injection detection)
- Secrets detection (30+ secret types with entropy-based detection)
- Security audit logging with CloudWatch and DynamoDB persistence
- Real-time threat intelligence with daily blocklist updates
- Semantic guardrails engine (6-layer threat detection)
- Agent capability governance (4-tier tool classification, runtime enforcement)

---

## Documentation

### Getting Started

- [Platform Overview](docs/product/getting-started/index.md) -- What is Aura, key benefits, use cases
- [Quick Start Guide](docs/product/getting-started/quick-start.md) -- Get running in 5 minutes
- [System Requirements](docs/product/getting-started/system-requirements.md) -- Prerequisites
- [Installation Guide](docs/product/getting-started/installation.md) -- SaaS, Kubernetes, Podman deployment
- [First Project Walkthrough](docs/product/getting-started/first-project.md) -- Connect a repository and run your first scan

### Core Concepts

- [Autonomous Code Intelligence](docs/product/core-concepts/autonomous-code-intelligence.md) -- LLM-powered remediation
- [Hybrid GraphRAG](docs/product/core-concepts/hybrid-graphrag.md) -- Neptune + OpenSearch architecture
- [Multi-Agent System](docs/product/core-concepts/multi-agent-system.md) -- Agent orchestration
- [HITL Workflows](docs/product/core-concepts/hitl-workflows.md) -- Autonomy levels and policy presets
- [Sandbox Security](docs/product/core-concepts/sandbox-security.md) -- Isolated validation model

### Operations and Support

- [System Architecture](docs/SYSTEM_ARCHITECTURE.md) -- Technical design and deployment topology
- [API Reference](docs/support/api-reference/index.md) -- REST, GraphQL, and webhooks
- [Troubleshooting](docs/support/troubleshooting/index.md) -- Common issues and solutions
- [Monitoring and Operations](docs/support/operations/index.md) -- Observability, logging, scaling
- [FAQ](docs/support/faq.md) -- Frequently asked questions

### Architecture Decisions

The project maintains [Architecture Decision Records](docs/architecture-decisions/) documenting rationale for significant design choices. Key ADRs include:

- **ADR-024**: Titan Neural Memory Architecture
- **ADR-034**: Context Engineering Framework
- **ADR-063**: Constitutional AI Integration
- **ADR-065**: Semantic Guardrails Engine
- **ADR-083**: Runtime Agent Security Platform

---

## Project Stats

| Metric | Value |
|--------|-------|
| Lines of Code | 439,000+ (193K Python, 142K Tests, 53K JS/JSX, 68K Config) |
| Test Suite | 23,165+ tests (0 failures) |
| Architecture Decision Records | 84 ADRs |
| CloudFormation Templates | 155 (24 CodeBuild + 131 infrastructure) |
| Infrastructure Phases | 8 of 8 complete |

---

## Security Architecture

Aura's security posture has been assessed against known agentic AI attack vectors including command injection, prompt injection, dependency confusion, and agent execution escape. Key architectural controls:

- **Command Execution:** Allowlist-based filtering with `shell=False` enforcement via `SecureCommandExecutor` — eliminates shell metacharacter and Unicode bypass attacks
- **Prompt Injection Defense:** 6-layer Semantic Guardrails Engine (Unicode normalization, pattern matching, embedding similarity, LLM-as-judge, session tracking, decision engine) applied to both user input and ingested repository content
- **Supply Chain:** Purpose-built dependency confusion detector (typosquatting, namespace hijacking, version confusion), SBOM attestation with Sigstore signing, private ECR base images
- **Agent Isolation:** 4-tier tool classification with default-deny policy, container + network sandboxing with eBPF escape detection, restricted Python execution namespace
- **Agent Governance:** Configurable HITL autonomy levels (0-5), time-bounded dynamic grants, shadow agent detection with behavioral baselines and quarantine

For details, see [Security Architecture](docs/support/architecture/security-architecture.md).

---

## Contributing

We welcome contributions. See [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Issue management and labels
- Pull request process and review standards
- Commit message format (Conventional Commits)
- Branch naming conventions
- Release process

---

## Reporting Security Vulnerabilities

If you discover a security vulnerability, please report it responsibly. Do **not** open a public GitHub issue for security vulnerabilities.

Email: **security@aenealabs.com**

We will acknowledge receipt within 48 hours and provide a detailed response within 5 business days.

---

## License

Project Aura is licensed under the [Business Source License 1.1](LICENSE).

The BSL allows you to use the source code for non-production purposes. Production use requires a commercial license from Aenea Labs. The license converts to open source (Apache 2.0) after the change date specified in the LICENSE file.

---

## About

**[Aenea Labs](https://aenealabs.com)** builds autonomous AI infrastructure for enterprise security teams.

Project Aura is designed for organizations that need to remediate vulnerabilities at scale while maintaining full compliance audit trails. The platform is built from the ground up for regulated industries including defense, financial services, healthcare, and government contracting.
