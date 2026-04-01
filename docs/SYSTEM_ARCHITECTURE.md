# Project Aura - System Architecture

**Version:** 2.6
**Last Updated:** February 11, 2026
**Status:** All 9 Phases Deployed (Foundation, Data, Compute, Application, Observability, Serverless, Sandbox, Security, Scanning Engine)
**ADRs:** 84 Architecture Decision Records (83 Deployed/Accepted, 1 Proposed)

---

## Table of Contents

1. [High-Level Architecture](#high-level-architecture)
2. [Cloud Abstraction Layer](#cloud-abstraction-layer)
3. [Hybrid Deployment Architecture](#hybrid-deployment-architecture)
4. [Agentic Search System](#agentic-search-system)
5. [Context Retrieval Pipeline](#context-retrieval-pipeline)
6. [Agent Orchestration](#agent-orchestration)
7. [Orchestrator Deployment Modes](#orchestrator-deployment-modes)
8. [Sandbox Infrastructure](#sandbox-infrastructure)
9. [Network Architecture](#network-architecture)
10. [Data Flow](#data-flow)
11. [Security Architecture](#security-architecture)
12. [Deployment Topology](#deployment-topology)

---

## High-Level Architecture

```text
┌──────────────────────────────────────────────────────────────────────────┐
│                          Project Aura - System Overview                   │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                      User Interface Layer                           │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │  │
│  │  │ CKGEConsole  │  │   Future:    │  │      Future:             │ │  │
│  │  │   (React)    │  │  Approval    │  │   GraphRAG Explorer      │ │  │
│  │  │              │  │  Dashboard   │  │                          │ │  │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘ │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                    │                                      │
│                                    ▼                                      │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                    Agent Orchestration Layer                        │  │
│  │  ┌──────────────────────────────────────────────────────────────┐  │  │
│  │  │              System2Orchestrator (Python)                     │  │  │
│  │  │  • Workflow Loop (Plan → Context → Code → Review → Validate) │  │  │
│  │  │  • Agent Coordination                                         │  │  │
│  │  │  • Error Handling & Retry Logic                              │  │  │
│  │  └──────────────────────────────────────────────────────────────┘  │  │
│  │                                                                      │  │
│  │  ┌────────────┐  ┌─────────────┐  ┌────────────┐  ┌────────────┐  │  │
│  │  │   Coder    │  │  Reviewer   │  │ Validator  │  │  Monitor   │  │  │
│  │  │   Agent    │  │   Agent     │  │   Agent    │  │   Agent    │  │  │
│  │  └────────────┘  └─────────────┘  └────────────┘  └────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                    │                                      │
│                                    ▼                                      │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                  Context Retrieval Layer (NEW)                      │  │
│  │  ┌──────────────────────────────────────────────────────────────┐  │  │
│  │  │           ContextRetrievalService (Agentic)                   │  │  │
│  │  │  • QueryPlanningAgent (LLM-powered strategy selection)        │  │  │
│  │  │  • FilesystemNavigatorAgent (pattern/semantic/git search)     │  │  │
│  │  │  • ResultSynthesisAgent (multi-factor ranking)                │  │  │
│  │  │  • Parallel multi-strategy execution                          │  │  │
│  │  └──────────────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                    │                                      │
│                                    ▼                                      │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                      Data & Knowledge Layer                         │  │
│  │  ┌────────────┐  ┌─────────────┐  ┌────────────┐  ┌────────────┐  │  │
│  │  │  Neptune   │  │ OpenSearch  │  │ DynamoDB   │  │    S3      │  │  │
│  │  │  (Graph)   │  │  (Vectors)  │  │  (State)   │  │ (Artifacts)│  │  │
│  │  │            │  │             │  │            │  │            │  │  │
│  │  │ • Call     │  │ • Code      │  │ • Sandbox  │  │ • Code     │  │  │
│  │  │   graphs   │  │   embeddings│  │   state    │  │   repos    │  │  │
│  │  │ • Dependencies│ • Filesystem│  │ • Session  │  │ • Patches  │  │  │
│  │  │ • Inheritance│  │   metadata │  │   data     │  │ • Reports  │  │  │
│  │  └────────────┘  └─────────────┘  └────────────┘  └────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                    │                                      │
│                                    ▼                                      │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                    AI/LLM Integration Layer                         │  │
│  │  ┌────────────┐  ┌─────────────┐  ┌────────────┐                   │  │
│  │  │   Bedrock  │  │   Bedrock   │  │  Future:   │                   │  │
│  │  │  (Claude)  │  │   (Titan)   │  │  OpenAI    │                   │  │
│  │  │            │  │             │  │   GPT-4    │                   │  │
│  │  │ • Query    │  │ • Code      │  │            │                   │  │
│  │  │   planning │  │   embeddings│  │ • Code     │                   │  │
│  │  │ • Code gen │  │ • Semantic  │  │   generation│                   │  │
│  │  │ • Review   │  │   search    │  │            │                   │  │
│  │  └────────────┘  └─────────────┘  └────────────┘                   │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Cloud Abstraction Layer

**Status:** Deployed (ADR-004) | **Implementation Date:** December 16, 2025

Project Aura supports multi-cloud deployment through a Cloud Abstraction Layer (CAL) that enables deployment to both AWS GovCloud and Azure Government.

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                     AURA PLATFORM (Cloud-Agnostic)                       │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Business Logic Layer                          │   │
│  │  • Agent Orchestrator    • Context Retrieval   • LLM Service    │   │
│  │  • Sandbox Management    • HITL Workflows      • Security       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                    │                                     │
│                                    ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              Cloud Abstraction Layer (src/abstractions/)        │   │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────────┐   │   │
│  │  │GraphDatabase  │  │VectorDatabase │  │    LLMService     │   │   │
│  │  │   Service     │  │   Service     │  │                   │   │   │
│  │  └───────────────┘  └───────────────┘  └───────────────────┘   │   │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────────┐   │   │
│  │  │StorageService │  │SecretsService │  │CloudServiceFactory│   │   │
│  │  │               │  │               │  │                   │   │   │
│  │  └───────────────┘  └───────────────┘  └───────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                      │                          │                       │
│           ┌──────────┴────────────┐    ┌───────┴───────────┐           │
│           ▼                       ▼    ▼                   ▼           │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    │
│  │  AWS GovCloud   │    │ Azure Government│    │   Mock (Tests)  │    │
│  ├─────────────────┤    ├─────────────────┤    ├─────────────────┤    │
│  │ Neptune         │    │ Cosmos DB       │    │ MockGraph       │    │
│  │ OpenSearch      │    │ AI Search       │    │ MockVector      │    │
│  │ Bedrock         │    │ Azure OpenAI    │    │ MockLLM         │    │
│  │ S3              │    │ Blob Storage    │    │ MockStorage     │    │
│  │ Secrets Manager │    │ Key Vault       │    │ MockSecrets     │    │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Service Abstractions

| Service | Interface | AWS Implementation | Azure Implementation |
|---------|-----------|-------------------|---------------------|
| **Graph Database** | `GraphDatabaseService` | `NeptuneGraphAdapter` | `CosmosDBGraphService` |
| **Vector Database** | `VectorDatabaseService` | `OpenSearchVectorAdapter` | `AzureAISearchService` |
| **LLM Inference** | `LLMService` | `BedrockLLMAdapter` | `AzureOpenAIService` |
| **Object Storage** | `StorageService` | `S3StorageAdapter` | `AzureBlobService` |
| **Secrets Management** | `SecretsService` | `SecretsManagerAdapter` | `AzureKeyVaultService` |

### Usage

```python
from src.services.providers import CloudServiceFactory, get_graph_service

# Automatic provider selection from CLOUD_PROVIDER environment variable
graph = get_graph_service()

# Explicit provider selection
factory = CloudServiceFactory.for_provider(CloudProvider.AZURE_GOVERNMENT, "usgovvirginia")
graph = factory.create_graph_service()
vector = factory.create_vector_service()
llm = factory.create_llm_service()
```

**Reference:** See [ADR-004](../architecture-decisions/ADR-004-multi-cloud-architecture.md) for full design rationale and [MULTI_CLOUD_ARCHITECTURE.md](cloud-strategy/MULTI_CLOUD_ARCHITECTURE.md) for detailed implementation plan.

---

## Hybrid Deployment Architecture

**Strategy:** ECS Fargate for dev/sandboxes, EKS EC2 for production agents

```text
┌───────────────────────────────────────────────────────────────────────────┐
│                         AWS Commercial Cloud (Dev/QA)                      │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │                    VPC (vpc-0123456789abcdef0)                        │ │
│  │                         10.0.0.0/16                                   │ │
│  │                                                                        │ │
│  │  ┌────────────────────────────────────────────────────────────────┐  │ │
│  │  │  Dev Environment (ECS Fargate) - $231/month [NOT YET DEPLOYED]  │  │ │
│  │  │                                                                  │  │ │
│  │  │  ┌──────────┐  ┌────────────┐  ┌──────────┐  ┌──────────┐     │  │ │
│  │  │  │ dnsmasq  │  │Orchestrator│  │  Coder   │  │ Reviewer │     │  │ │
│  │  │  │ Service  │  │  Service   │  │  Agent   │  │  Agent   │     │  │ │
│  │  │  │          │  │            │  │          │  │          │     │  │ │
│  │  │  │ Fargate  │  │  Fargate   │  │ Fargate  │  │ Fargate  │     │  │ │
│  │  │  │  Task    │  │   Task     │  │  Task    │  │  Task    │     │  │ │
│  │  │  └──────────┘  └────────────┘  └──────────┘  └──────────┘     │  │ │
│  │  │       │              │                │             │           │  │ │
│  │  │       └──────────────┴────────────────┴─────────────┘           │  │ │
│  │  │                              │                                   │  │ │
│  │  │                    AWS Cloud Map Service Discovery              │  │ │
│  │  │                                                                  │  │ │
│  │  │  Scaling: EventBridge (8am-6pm weekdays)                        │  │ │
│  │  │  Capacity: FARGATE_SPOT (70% cost savings)                      │  │ │
│  │  └────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                        │ │
│  │  ┌────────────────────────────────────────────────────────────────┐  │ │
│  │  │  Sandbox Environment (ECS Fargate) - Scale-to-zero [NOT YET DEPLOYED] │  │ │
│  │  │                                                                  │  │ │
│  │  │  ┌──────────────────────────────────────────────────────────┐  │  │ │
│  │  │  │  Ephemeral Sandbox Tasks (0-10 concurrent)                │  │  │ │
│  │  │  │  • Isolated patch testing                                 │  │  │ │
│  │  │  │  • Maximum security (DROP ALL capabilities)               │  │  │ │
│  │  │  │  • No external network access                             │  │  │ │
│  │  │  │  • DynamoDB state tracking with TTL                       │  │  │ │
│  │  │  └──────────────────────────────────────────────────────────┘  │  │ │
│  │  └────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                        │ │
│  │  ┌────────────────────────────────────────────────────────────────┐  │ │
│  │  │  OpenSearch Domain (VPC-only) - $70/month (dev)                │  │ │
│  │  │                                                                  │  │ │
│  │  │  ┌──────────────────────────────────────────────────────────┐  │  │ │
│  │  │  │  • 2x t3.small.search instances (Multi-AZ)                │  │  │ │
│  │  │  │  • KNN vector fields (1536 dimensions, HNSW)              │  │  │ │
│  │  │  │  • Filesystem metadata index                              │  │  │ │
│  │  │  │  • Code embeddings                                        │  │  │ │
│  │  │  │  • Lambda auto-index creation                             │  │  │ │
│  │  │  └──────────────────────────────────────────────────────────┘  │  │ │
│  │  └────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                        │ │
│  │  ┌────────────────────────────────────────────────────────────────┐  │ │
│  │  │  Future: EKS Cluster (EC2 Managed Node Groups)                 │  │ │
│  │  │                                                                  │  │ │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │  │ │
│  │  │  │ System Nodes │  │   App Nodes  │  │  Sandbox Nodes       │  │  │ │
│  │  │  │ (dnsmasq,    │  │ (Production  │  │ (Ephemeral testing)  │  │ │
│  │  │  │  CoreDNS)    │  │  agents)     │  │ (Scale-to-zero)      │  │  │ │
│  │  │  │              │  │              │  │                      │  │  │ │
│  │  │  │ 2x t3.medium │  │ 3-5x m5.xlarge│ │ 0-10x t3.large      │  │  │ │
│  │  │  │ On-Demand    │  │ On-Demand    │  │ Spot instances      │  │  │ │
│  │  │  └──────────────┘  └──────────────┘  └──────────────────────┘  │  │ │
│  │  └────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                        │ │
│  │  ┌────────────────────────────────────────────────────────────────┐  │ │
│  │  │  VPC Endpoints (9 endpoints) - $44/month                        │  │ │
│  │  │  • S3, DynamoDB, Bedrock, CodeConnections, Logs, Secrets, ECR  │  │ │
│  │  │  • No NAT Gateways (CMMC L3 compliant - no internet egress)    │  │ │
│  │  └────────────────────────────────────────────────────────────────┘  │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└───────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────────┐
│                    AWS GovCloud (US) (Future - Q2 2026)                    │
├───────────────────────────────────────────────────────────────────────────┤
│  Similar architecture with:                                                │
│  • STIG-hardened EKS nodes (DISA STIG compliance)                         │
│  • FIPS 140-2 mode enabled                                                │
│  • Private VPC endpoints only                                             │
│  • Enhanced audit logging                                                 │
│  • On-Demand instances (no Spot for production)                           │
└───────────────────────────────────────────────────────────────────────────┘
```

**Cost Summary:**
- **Phase 1 (Deployed):** $44/month (VPC Endpoints)
- **Phase 2 (Ready):** $231/month (ECS Fargate dev) + $70/month (OpenSearch) = **$345/month total**
- **Savings:** $440/month vs. always-on EKS EC2

---

## Agentic Search System

**Status:** ✅ Full Hybrid GraphRAG Complete (Dec 29, 2025)

Multi-strategy context retrieval system that combines graph, vector, filesystem, and git search for optimal code discovery within token budgets.

**Architecture:**

1. **QueryPlanningAgent** - LLM-powered strategy selection
   - Analyzes query intent and selects optimal search strategies (graph/vector/filesystem/git)
   - Estimates token costs and fits strategies to budget
   - Fallback to defaults if LLM unavailable

2. **Parallel Search Execution** (asyncio)
   - **Graph Search:** Neptune Gremlin with 5 query types (call graphs, dependencies, inheritance, references, related)
   - **Vector Search:** OpenSearch KNN (semantic similarity via embeddings)
   - **Filesystem Search:** OpenSearch metadata (glob patterns, wildcards)
   - **Git Search:** Recent changes, blame data, commit history

3. **ResultSynthesisAgent** - Multi-factor ranking & deduplication
   - Composite scoring: multi-strategy boost, recency, file size, module type
   - Budget fitting via greedy algorithm
   - Transparent ranking explanations

**Graph Search Query Types (Dec 29, 2025):**

| Query Type | Gremlin Pattern | Use Case |
|------------|-----------------|----------|
| `CALL_GRAPH` | Traverse `CALLS` edges | Find callers/callees of functions |
| `DEPENDENCIES` | Traverse `IMPORTS`/`DEPENDS_ON` edges | Trace package dependencies |
| `INHERITANCE` | Traverse `EXTENDS`/`IMPLEMENTS` edges | Find class hierarchies |
| `REFERENCES` | Match `REFERENCES` edges | Track symbol usage across codebase |
| `RELATED` | Multi-hop traversal | General semantic context discovery |

**Performance:** 3-5x better context quality for same token budget

**Detailed Documentation:** See [archive/implementation-snapshots/IMPLEMENTATION_AGENTIC_SEARCH.md](archive/implementation-snapshots/IMPLEMENTATION_AGENTIC_SEARCH.md)

---

## Context Retrieval Pipeline

**End-to-End Flow from Query to Context**

```text
┌───────────────────────────────────────────────────────────────────────────┐
│                         Context Retrieval Pipeline                         │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Agent Request: "Fix authentication vulnerability in JWT validation"        │
│                         │                                                   │
│                         ▼                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  Step 1: Query Planning (QueryPlanningAgent)                         │ │
│  │  • LLM analyzes query intent                                         │ │
│  │  • Identifies key concepts: "authentication", "JWT", "validation"    │ │
│  │  • Selects strategies: [vector, filesystem, graph]                   │ │
│  │  • Allocates token budget per strategy                               │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                         │                                                   │
│                         ▼                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  Step 2: Parallel Search Execution                                   │ │
│  │                                                                        │ │
│  │  ┌──────────────────────────────────────────────────────────────┐   │ │
│  │  │  Vector Search (OpenSearch KNN)                               │   │ │
│  │  │  • Embed query: "JWT authentication validation"               │   │ │
│  │  │  • KNN search on docstring_embedding field                    │   │ │
│  │  │  • Returns: auth_service.py, jwt_validator.py (score: 9.5)   │   │ │
│  │  └──────────────────────────────────────────────────────────────┘   │ │
│  │                                                                        │ │
│  │  ┌──────────────────────────────────────────────────────────────┐   │ │
│  │  │  Filesystem Search (OpenSearch Metadata)                      │   │ │
│  │  │  • Pattern: "**/auth/*.py"                                    │   │ │
│  │  │  • Wildcard query on file_path field                          │   │ │
│  │  │  • Returns: auth_service.py, auth_middleware.py (score: 8.0) │   │ │
│  │  └──────────────────────────────────────────────────────────────┘   │ │
│  │                                                                        │ │
│  │  ┌──────────────────────────────────────────────────────────────┐   │ │
│  │  │  Graph Search (Neptune Gremlin)                               │   │ │
│  │  │  • Query: Functions calling JWT validation                    │   │ │
│  │  │  • Traverse call graph                                        │   │ │
│  │  │  • Returns: login.py, api_auth.py (score: 7.5)               │   │ │
│  │  └──────────────────────────────────────────────────────────────┘   │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                         │                                                   │
│                         ▼                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  Step 3: Result Synthesis (ResultSynthesisAgent)                     │ │
│  │                                                                        │ │
│  │  Raw results: 5 files (2 duplicates)                                 │ │
│  │  After deduplication: 3 unique files                                 │ │
│  │                                                                        │ │
│  │  Composite scores:                                                    │ │
│  │  1. auth_service.py: 24.5 (found by vector + filesystem + graph)     │ │
│  │  2. jwt_validator.py: 18.2 (found by vector + graph)                 │ │
│  │  3. auth_middleware.py: 12.0 (found by filesystem only)              │ │
│  │                                                                        │ │
│  │  Budget fitting (budget: 50,000 tokens):                             │ │
│  │  • File 1: 15,000 tokens (selected)                                  │ │
│  │  • File 2: 10,000 tokens (selected)                                  │ │
│  │  • File 3: 8,000 tokens (selected)                                   │ │
│  │  • Total: 33,000 tokens (66% of budget)                              │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                         │                                                   │
│                         ▼                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  Step 4: Context Response                                            │ │
│  │                                                                        │ │
│  │  HybridContext {                                                      │ │
│  │    files: [                                                           │ │
│  │      {path: "auth_service.py", score: 24.5, tokens: 15000},          │ │
│  │      {path: "jwt_validator.py", score: 18.2, tokens: 10000},         │ │
│  │      {path: "auth_middleware.py", score: 12.0, tokens: 8000}         │ │
│  │    ],                                                                 │ │
│  │    total_tokens: 33000,                                               │ │
│  │    strategies_used: ["vector", "filesystem", "graph"],               │ │
│  │    query: "Fix authentication vulnerability in JWT validation"       │ │
│  │  }                                                                    │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                         │                                                   │
│                         ▼                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  Delivered to Agent Orchestrator                                     │ │
│  │  • Coder Agent receives ranked context                               │ │
│  │  • Generates patch with high-quality context                         │ │
│  │  • Expected: 3-5x better code understanding                          │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## Agent Orchestration

**Hybrid Warm Pool Architecture** (Recommended Pattern)

The Agent Orchestrator uses a cost-effective warm pool deployment pattern that provides zero cold start while minimizing infrastructure costs (~$28/month vs $175/month always-on).

```text
┌───────────────────────────────────────────────────────────────────────────┐
│                      Agent Orchestrator Architecture                        │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │                        API Layer                                      │ │
│  │  POST /api/v1/orchestrate     - Submit orchestration job             │ │
│  │  GET  /api/v1/orchestrate/{id} - Get job status                      │ │
│  │  DELETE /api/v1/orchestrate/{id} - Cancel job                        │ │
│  │  WS   /api/v1/orchestrate/{id}/stream - Real-time updates           │ │
│  └────────────────────────────────┬─────────────────────────────────────┘ │
│                                   │                                        │
│                                   ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │                     OrchestrationService                              │ │
│  │  • DynamoDB: aura-orchestrator-jobs-{env} (job state)                │ │
│  │  • SQS: aura-orchestrator-tasks-{env} (job dispatch)                 │ │
│  │  • Dual-mode: MOCK (testing) / AWS (production)                      │ │
│  └────────────────────────────────┬─────────────────────────────────────┘ │
│                                   │                                        │
│                                   ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │              Warm Pool (EKS Deployment - 1 replica)                   │ │
│  │  orchestrator_server.py:                                             │ │
│  │  • HTTP Server: /health/live, /health/ready, /metrics                │ │
│  │  • SQS Consumer: Long-polls for jobs (5s interval)                   │ │
│  │  • Zero cold start: Always-on replica waiting for work               │ │
│  └────────────────────────────────┬─────────────────────────────────────┘ │
│                                   │                                        │
│                                   ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │                    System2Orchestrator                                │ │
│  │  Main Loop: Plan → Context → Code → Review → Validate → Monitor      │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                         │                                                   │
│                         ▼                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  Phase 1: PLAN                                                        │ │
│  │  • Receive task: "Fix CVE-2024-XXXX in auth module"                  │ │
│  │  • Validate input (InputSanitizer)                                   │ │
│  │  • Create execution plan                                             │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                         │                                                   │
│                         ▼                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  Phase 2: CONTEXT (Agentic Search)                                   │ │
│  │  • ContextRetrievalService.retrieve_context()                        │ │
│  │  • Multi-strategy search (graph + vector + filesystem + git)         │ │
│  │  • Returns HybridContext with ranked files                           │ │
│  │  • Context budget: 100,000 tokens                                    │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                         │                                                   │
│                         ▼                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  Phase 3: CODE                                                        │ │
│  │  • Coder Agent receives context                                      │ │
│  │  • LLM (Claude/GPT-4) generates patch                                │ │
│  │  • AST Parser validates syntax                                       │ │
│  │  • Returns unified diff                                              │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                         │                                                   │
│                         ▼                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  Phase 4: REVIEW                                                      │ │
│  │  • Reviewer Agent analyzes patch                                     │ │
│  │  • Security checks (OWASP Top 10, AI-specific threats)               │ │
│  │  • Code quality checks (complexity, maintainability)                 │ │
│  │  • Returns review report with findings                               │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                         │                                                   │
│                         ▼                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  Phase 5: VALIDATE (Sandbox Testing)                                 │ │
│  │  • FargateSandboxOrchestrator.create_sandbox()                       │ │
│  │  • Apply patch in isolated environment                               │ │
│  │  • Run test suite                                                    │ │
│  │  • Collect results                                                   │ │
│  │  • FargateSandboxOrchestrator.destroy_sandbox()                      │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                         │                                                   │
│                         ▼                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  Phase 6: MONITOR                                                     │ │
│  │  • Log activity (tokens used, LOC changed)                           │ │
│  │  • Track security findings                                           │ │
│  │  • Calculate cost ($0.05/1K tokens)                                  │ │
│  │  • Generate comprehensive report                                     │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                         │                                                   │
│                         ▼                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  HITL (Human-in-the-Loop) Approval (Future)                          │ │
│  │  • Present findings to human reviewer                                │ │
│  │  • Approval Dashboard (React UI)                                     │ │
│  │  • SNS notifications                                                 │ │
│  │  • Apply patch if approved                                           │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## Orchestrator Deployment Modes

**Status:** Implemented (December 15, 2025)

The Agent Orchestrator supports three configurable deployment modes, allowing organizations to optimize for cost, latency, or both. Modes can be configured at the platform level or with per-organization overrides.

### Available Modes

| Mode | Base Cost | Cold Start | Best For |
|------|-----------|------------|----------|
| **On-Demand** | $0/mo | ~30 seconds | Dev/test, low volume (<100 jobs/day) |
| **Warm Pool** | ~$28/mo | 0 seconds | Production, high volume (>500 jobs/day) |
| **Hybrid** | ~$28/mo + burst | 0 seconds | Variable workloads, enterprise |

### Mode Selection Architecture

```text
┌───────────────────────────────────────────────────────────────────────────┐
│                  Orchestrator Deployment Mode Architecture                  │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │                         Settings Layer                                │ │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐  │ │
│  │  │  Platform       │    │  Organization   │    │  Settings       │  │ │
│  │  │  Defaults       │ <- │  Overrides      │ <- │  API            │  │ │
│  │  │  (DynamoDB)     │    │  (DynamoDB)     │    │  (REST/Admin)   │  │ │
│  │  └─────────────────┘    └─────────────────┘    └─────────────────┘  │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                    │                                        │
│                                    ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │                     Mode Transition Service                           │ │
│  │  State Machine: ACTIVE -> DRAINING -> COMPLETING -> SCALING -> ACTIVE│ │
│  │  • 5-minute cooldown between changes (anti-thrashing)                │ │
│  │  • Graceful in-flight job completion                                 │ │
│  │  • K8s warm pool scaling via RBAC                                    │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                    │                                        │
│                     ┌──────────────┼──────────────┐                        │
│                     │              │              │                        │
│                     ▼              ▼              ▼                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────────┐   │
│  │  ON-DEMAND  │  │  WARM POOL  │  │          HYBRID                 │   │
│  │  Mode       │  │  Mode       │  │          Mode                   │   │
│  │             │  │             │  │                                 │   │
│  │  EKS Job    │  │  Always-On  │  │  Warm Pool  │  Burst Jobs      │   │
│  │  per        │  │  Replica    │  │  (baseline) │  (overflow)      │   │
│  │  Request    │  │  (1-10)     │  │             │                   │   │
│  │             │  │             │  │             │                   │   │
│  │  $0/mo      │  │  ~$28/mo    │  │  ~$28/mo + $0.15/burst job     │   │
│  │  ~30s start │  │  0s start   │  │  0s (pool) / 30s (burst)       │   │
│  └─────────────┘  └─────────────┘  └─────────────────────────────────┘   │
│                                                                             │
└───────────────────────────────────────────────────────────────────────────┘
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/orchestrator/settings` | GET | Get current mode settings |
| `/api/v1/orchestrator/settings` | PUT | Update mode settings (admin) |
| `/api/v1/orchestrator/settings/modes` | GET | List available modes with details |
| `/api/v1/orchestrator/settings/switch` | POST | Explicitly switch mode (admin) |
| `/api/v1/orchestrator/settings/status` | GET | Current operational status |
| `/api/v1/orchestrator/settings/health` | GET | Health check |

### Per-Organization Overrides

Organizations can override platform defaults for customized deployment modes:

```text
Platform Default: on_demand ($0/mo)
    │
    ├── Org A: Override -> warm_pool ($28/mo)
    │
    ├── Org B: No override (uses on_demand)
    │
    └── Org C: Override -> hybrid ($28/mo + burst)
```

### CloudWatch Alarms

| Alarm | Trigger | Action |
|-------|---------|--------|
| Mode Thrashing | >3 mode changes in 1 hour | SNS notification |
| Warm Pool Not Ready | Ready < Desired for 5 min | SNS notification |
| Burst Overload | Burst jobs > max limit | SNS notification |

**Detailed Documentation:** See [docs/features/ORCHESTRATOR_MODES.md](features/ORCHESTRATOR_MODES.md)

---

## Sandbox Infrastructure

**Isolated Testing Environments**

```text
┌───────────────────────────────────────────────────────────────────────────┐
│                      Sandbox Architecture (ECS Fargate)                    │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │                FargateSandboxOrchestrator (Python)                    │ │
│  │  • create_sandbox(sandbox_id, patch_id, test_suite)                  │ │
│  │  • destroy_sandbox(sandbox_id)                                       │ │
│  │  • get_sandbox_status(sandbox_id)                                    │ │
│  │  • get_sandbox_logs(sandbox_id)                                      │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                         │                                                   │
│                         ▼                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  Sandbox Lifecycle:                                                   │ │
│  │                                                                        │ │
│  │  1. Provision:                                                        │ │
│  │     • Create ECS task with sandbox Docker image                      │ │
│  │     • Store state in DynamoDB (sandbox_id, task_arn, created_at)     │ │
│  │     • Set TTL for auto-cleanup (2 hours)                             │ │
│  │                                                                        │ │
│  │  2. Execute:                                                          │ │
│  │     • Apply patch to codebase                                        │ │
│  │     • Run test suite: pytest, npm test, etc.                         │ │
│  │     • Collect results to CloudWatch Logs                             │ │
│  │                                                                        │ │
│  │  3. Monitor:                                                          │ │
│  │     • Check task status (RUNNING, STOPPED)                           │ │
│  │     • Tail CloudWatch Logs                                           │ │
│  │     • Return results to orchestrator                                 │ │
│  │                                                                        │ │
│  │  4. Cleanup:                                                          │ │
│  │     • Stop ECS task                                                  │ │
│  │     • Delete DynamoDB state                                          │ │
│  │     • Logs retained for 30 days                                      │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                         │                                                   │
│                         ▼                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  Sandbox Security Isolation:                                         │ │
│  │                                                                        │ │
│  │  ┌────────────────────────────────────────────────────────────────┐  │ │
│  │  │  Docker Container (Fargate Task)                                │  │ │
│  │  │  • Linux capabilities: DROP ALL                                 │  │ │
│  │  │  • Read-only root filesystem                                    │  │ │
│  │  │  • Non-root user (UID 2000)                                     │  │ │
│  │  │  • No privileged mode                                           │  │ │
│  │  │  • Temp directory: /tmp (tmpfs, ephemeral)                      │  │ │
│  │  └────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                        │ │
│  │  ┌────────────────────────────────────────────────────────────────┐  │ │
│  │  │  Network Isolation (Security Group)                             │  │ │
│  │  │  • Ingress: DENY ALL                                            │  │ │
│  │  │  • Egress: ALLOW only to dnsmasq (port 53)                      │  │ │
│  │  │  • Metadata service: 169.254.169.254 BLOCKED                    │  │ │
│  │  └────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                        │ │
│  │  ┌────────────────────────────────────────────────────────────────┐  │ │
│  │  │  Resource Limits                                                │  │ │
│  │  │  • CPU: 0.5 vCPU                                                │  │ │
│  │  │  • Memory: 1 GB                                                 │  │ │
│  │  │  • Ephemeral storage: 20 GB                                     │  │ │
│  │  │  • Task timeout: 30 minutes                                     │  │ │
│  │  └────────────────────────────────────────────────────────────────┘  │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  Cost: $0.02 per sandbox (30-minute execution)                             │
│  Scalability: 0-100 concurrent sandboxes                                   │
└───────────────────────────────────────────────────────────────────────────┘
```

**DynamoDB State Tracking:**

```text
┌──────────────────────────────────────────────────────────────┐
│          Sandbox State Table (aura-sandbox-state)             │
├──────────────────────────────────────────────────────────────┤
│  Partition Key: sandbox_id (String)                          │
│                                                                │
│  Attributes:                                                  │
│  • task_arn: ECS task ARN                                    │
│  • patch_id: Associated patch                                │
│  • test_suite: Test command                                  │
│  • status: PROVISIONING | RUNNING | STOPPED | FAILED         │
│  • created_at: Timestamp                                     │
│  • ttl: Auto-delete after 2 hours                            │
│  • log_group: CloudWatch Logs group name                     │
│                                                                │
│  TTL enabled: Automatic cleanup prevents orphaned state      │
└──────────────────────────────────────────────────────────────┘
```

---

## Network Architecture

**Status:** ✅ Phase 1 Deployed (CMMC L3 Compliant)

**VPC Configuration:**
- **VPC:** vpc-0123456789abcdef0 (10.0.0.0/16)
- **Multi-AZ:** us-east-1a, us-east-1b (high availability)
- **Subnets:** Public (10.0.1-2.0/24), Private (10.0.11-12.0/24)
- **Internet Access:** VPC Endpoints only (no NAT Gateway - zero trust architecture)

**VPC Endpoints (No internet egress):**
- **Gateway Endpoints:** S3, DynamoDB (no cost)
- **Interface Endpoints ($44/month):** Bedrock Runtime, Bedrock Agent, CodeConnections, CloudWatch Logs, Secrets Manager, ECR API, ECR DKR

**3-Tier DNS Architecture (dnsmasq):**

1. **Tier 1: EKS DaemonSet** - Per-node DNS caching
   - 5ms average resolution, 50K cache, NetworkPolicy isolation

2. **Tier 2: ECS Fargate VPC-wide** - Centralized DNS service
   - Network Load Balancer, Multi-AZ HA, Auto-scaling

3. **Tier 3: Sandbox DNS** - Ephemeral per-sandbox configuration
   - Custom `.sandbox.aura.local` domain, Mock service endpoints

**Service Discovery Endpoints:**
- neptune.aura.local:8182
- opensearch.aura.local:9200
- context-retrieval.aura.local:8080
- orchestrator.aura.local:8080 (Agent Orchestrator warm pool)
- agent-orchestrator.default.svc.cluster.local:8080 (K8s ClusterIP)

**Performance:** 67% faster DNS resolution, 5x cache capacity, 40% cost reduction

**Detailed Documentation:** See [docs/integrations/DNSMASQ_INTEGRATION.md](integrations/DNSMASQ_INTEGRATION.md)

---

## Data Flow

**Query to Patch Generation**

```text
┌───────────────────────────────────────────────────────────────────────────┐
│                        End-to-End Data Flow                                │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. User Request                                                           │
│     │                                                                       │
│     ├─► CKGEConsole (React UI)                                            │
│     │   • Submit task: "Fix CVE-2024-XXXX"                                │
│     │                                                                       │
│     └─► API Gateway (Future) → Lambda → SQS                               │
│                                                                             │
│  2. Task Processing                                                        │
│     │                                                                       │
│     ├─► System2Orchestrator                                                │
│     │   • Receives task from SQS                                          │
│     │   • Validates input (InputSanitizer)                                │
│     │   • Creates execution plan                                          │
│     │                                                                       │
│     └─► ContextRetrievalService (Agentic Search)                          │
│         • Query: "CVE-2024-XXXX vulnerability code"                       │
│         • Multi-strategy search (graph + vector + filesystem)             │
│         • Returns HybridContext with ranked files                         │
│                                                                             │
│  3. Code Generation                                                        │
│     │                                                                       │
│     ├─► Coder Agent                                                       │
│     │   • Receives context (3-5x better quality)                          │
│     │   • LLM generates patch (Claude via Bedrock)                        │
│     │   • AST Parser validates syntax                                     │
│     │                                                                       │
│     └─► Returns unified diff                                              │
│                                                                             │
│  4. Code Review                                                            │
│     │                                                                       │
│     ├─► Reviewer Agent                                                    │
│     │   • Security analysis (OWASP Top 10)                                │
│     │   • Code quality checks                                             │
│     │   • Generates review report                                         │
│     │                                                                       │
│     └─► Returns findings (severity: CRITICAL/HIGH/MEDIUM/LOW)             │
│                                                                             │
│  5. Sandbox Testing                                                        │
│     │                                                                       │
│     ├─► FargateSandboxOrchestrator                                        │
│     │   • create_sandbox(sandbox_id, patch, test_suite)                   │
│     │   • ECS Fargate task provisioned                                    │
│     │   • Isolated environment (no external network)                      │
│     │   • Apply patch → Run tests → Collect results                       │
│     │   • destroy_sandbox(sandbox_id)                                     │
│     │                                                                       │
│     └─► Returns test results (PASS/FAIL + logs)                           │
│                                                                             │
│  6. Monitoring & Reporting                                                 │
│     │                                                                       │
│     ├─► Monitor Agent                                                     │
│     │   • Log activity (tokens: 15K, LOC changed: 50)                     │
│     │   • Track security findings (1 CRITICAL, 2 HIGH)                    │
│     │   • Calculate cost ($0.75)                                          │
│     │                                                                       │
│     └─► Generate comprehensive report                                     │
│                                                                             │
│  7. HITL Approval (Future)                                                 │
│     │                                                                       │
│     ├─► SNS notification → Email/Slack                                    │
│     │   • Human reviews findings                                          │
│     │   • Approval Dashboard (React UI)                                   │
│     │   • Approve/Reject decision                                         │
│     │                                                                       │
│     └─► If approved: Apply patch to production                            │
│                                                                             │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## Security Architecture

**Status:** Infrastructure controls: 96% GovCloud-ready | Security Services: 100% Deployed | CMMC Level 2 Progress: ~50-60%

> **Related Documentation:**
> - **Adaptive Security Intelligence:** `agent-config/agents/security-code-reviewer.md#adaptive-security-intelligence-workflow` - Proactive threat monitoring, assessment, and remediation workflow
> - **HITL Sandbox Architecture:** `docs/design/HITL_SANDBOX_ARCHITECTURE.md` - Human approval workflow for patches
> - **Compliance Clarification:** `docs/cloud-strategy/GOVCLOUD_READINESS_TRACKER.md#compliance-status-clarification` - Honest CMMC assessment
> - **Security Services Overview:** `docs/security/SECURITY_SERVICES_OVERVIEW.md` - Architecture and compliance mapping

7-layer defense-in-depth architecture with zero internet egress and comprehensive audit logging:

**Layer 1: Network Security**
- VPC isolation with VPC Endpoints only (no NAT Gateway)
- Security groups (least privilege), NetworkPolicy (pod isolation)
- Metadata service blocked (169.254.169.254)

**Layer 2: Container Security**
- Linux capabilities: DROP ALL, non-root user (UID 1000/2000)
- Read-only root filesystem, resource limits, ephemeral storage only

**Layer 3: Application Security**
- InputSanitizer for graph injection prevention
- Input validation, output encoding, secure LLM prompt templates

**Layer 4: Data Security**
- KMS encryption at rest with automatic key rotation
- TLS 1.2+ in transit, node-to-node encryption (OpenSearch)
- Secrets Manager (no environment variables)

**Layer 5: IAM & Access Control**
- Least-privilege policies (no wildcard resources)
- Service roles with temporary credentials, MFA for human access

**Layer 6: Monitoring & Audit**
- CloudWatch Logs (all actions), VPC Flow Logs (365-day retention)
- OpenSearch audit logs, CloudWatch Alarms, SNS notifications

**Layer 7: Security Services (Dec 12, 2025)**
- **Input Validation Service:** SQL injection, XSS, command injection, SSRF, prompt injection detection
- **Secrets Detection Service:** 30+ secret types with entropy-based detection
- **Security Audit Service:** Event logging with CloudWatch/DynamoDB persistence
- **Security Alerts Service:** P1-P5 priority alerts with HITL integration and SNS notifications
- **API Security Integration:** FastAPI decorators, middleware, rate limiting
- **Security Infrastructure:** EventBridge bus, SNS topic, 7 CloudWatch alarms, 3 log groups
- **Test Coverage:** 328 security-specific tests across all services

**Compliance:** CMMC Level 3, SOX, NIST 800-53, SOC2, WCAG 2.1 AA (future)

**Detailed Security Documentation:**
- [SECURITY_FIXES_QUICK_REFERENCE.md](SECURITY_FIXES_QUICK_REFERENCE.md)
- [docs/security/SECURITY_INCIDENT_RESPONSE.md](security/SECURITY_INCIDENT_RESPONSE.md)
- [docs/security/DEVELOPER_SECURITY_GUIDELINES.md](security/DEVELOPER_SECURITY_GUIDELINES.md)
- [docs/security/SECURITY_SERVICES_OVERVIEW.md](security/SECURITY_SERVICES_OVERVIEW.md)

---

## Deployment Topology

**Current State (Phase 1 + Phase 2 Ready)**

```text
┌───────────────────────────────────────────────────────────────────────────┐
│                          Deployment Status                                 │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Phase 1: DEPLOYED ✅                                                      │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  AWS Commercial Cloud (us-east-1)                                    │ │
│  │                                                                        │ │
│  │  • VPC: vpc-0123456789abcdef0                                        │ │
│  │  • Subnets: 2 public + 2 private                                     │ │
│  │  • VPC Endpoints: 9 endpoints (S3, DynamoDB, Bedrock, etc.)          │ │
│  │  • Security Groups: 7 groups                                         │ │
│  │  • IAM Roles: 7 service roles                                        │ │
│  │  • Cost: $44/month (VPC Endpoints + Flow Logs)                       │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  Phase 2: READY FOR DEPLOYMENT ⚠️                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  OpenSearch Domain                                                    │ │
│  │  • CloudFormation template: 685 lines ✅                             │ │
│  │  • KNN vector index schema defined ✅                                │ │
│  │  • Lambda index creator ready ✅                                     │ │
│  │  • Deployment script: deploy-agentic-search.sh ✅                    │ │
│  │  • Estimated cost: $70/month (dev), $213/month (prod)                │ │
│  │  • Status: NOT DEPLOYED                                              │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  ECS Fargate Clusters                                                 │ │
│  │  • Dev cluster template: 600 lines ✅                                │ │
│  │  • Services template: 700 lines ✅                                   │ │
│  │  • Sandbox template: 450 lines ✅                                    │ │
│  │  • Dockerfiles: 3 files ✅                                           │ │
│  │  • Deployment scripts: 2 scripts ✅                                  │ │
│  │  • Estimated cost: $231/month (dev with scaling)                     │ │
│  │  • Status: NOT DEPLOYED                                              │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  Phase 3: PLANNED (Q2 2026)                                                │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  AWS GovCloud (US) Migration                                         │ │
│  │  • STIG-hardened EKS nodes                                           │ │
│  │  • FIPS 140-2 mode enabled                                           │ │
│  │  • Private VPC endpoints only                                        │ │
│  │  • Enhanced audit logging                                            │ │
│  │  • CMMC Level 3 certification                                        │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  Total Monthly Cost (when fully deployed):                                 │
│  • Phase 1: $44 (VPC Endpoints - currently running)                       │
│  • Phase 2: $345 (OpenSearch $70 + ECS Fargate $231 + Misc $44)           │
│  • Total: $389/month (dev environment)                                    │
│  • Savings: $440/month vs. always-on EKS                                  │
│                                                                             │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## Summary

**Project Aura System Architecture - February 11, 2026**

**Key Achievements:**
- ✅ **All 8 Infrastructure Phases Deployed** - Foundation, Data, Compute, Application, Observability, Serverless, Sandbox, Security
- ✅ **84 ADRs (83 Deployed/Accepted, 1 Proposed)** - Architecture Decision Records
- ✅ **Full Hybrid GraphRAG Complete** - Vector + Graph + BM25 search with 5 query types (Issue #151)
- ✅ **Agent Orchestrator Warm Pool** - Cost-effective hybrid architecture (~$28/month vs $175/month)
- ✅ **UI-Configurable Deployment Modes** - On-demand, warm pool, and hybrid with per-org overrides
- ✅ **Cloud Abstraction Layer (ADR-004)** - Multi-cloud AWS/Azure support, 5 service abstractions
- ✅ **Titan Neural Memory (ADR-024)** - 237 tests, 5 phases deployed, cognitive architecture operational
- ✅ **Context Engineering (ADR-034)** - 7 services deployed: scoring, registry, stack, retrieval, hoprag, mcp, summarization
- ✅ **AWS Agent Parity (ADR-037)** - 27 services total: AgentCore, Security, DevOps, Transform, Phase 2
- ✅ **EKS Cluster Operational** - EC2 Managed Node Groups for GovCloud compatibility
- ✅ **Security Services Deployed** - 5 Python services, 328 tests, CloudFormation infrastructure
- ✅ **IAM Permissions Scoped** - Neptune/RDS and OpenSearch permissions scoped to project-specific ARNs
- ✅ **8,113 Tests Passing** - Comprehensive test coverage including 328 security tests
- ✅ **Comprehensive Documentation** - Security incident response, developer guidelines, compliance mapping

**Architecture Highlights:**
- **Hybrid Deployment:** ECS Fargate (dev/sandboxes) + EKS EC2 (production)
- **Agent Orchestrator:** Warm pool deployment with SQS job dispatch and DynamoDB state
- **Hybrid GraphRAG:** Vector (semantic) + Graph (structural) + BM25 (keyword) search
- **Graph Query Types:** CALL_GRAPH, DEPENDENCIES, INHERITANCE, REFERENCES, RELATED
- **Security:** 7-layer defense-in-depth with CMMC Level 3 compliance
- **Security Services:** Input validation, secrets detection, audit, alerts, API integration
- **Cost Optimization:** $440/month savings through scale-to-zero and FARGATE_SPOT

**Overall Completion:** 99%

**Security Metrics:**
- 5 Python security services operational
- 328 security-specific tests
- 7 CloudWatch security alarms
- 3 CloudWatch log groups (90-day retention)
- 1 EventBridge bus + 2 rules
- 1 SNS topic with email subscriptions
- CMMC, SOC2, NIST 800-53 compliance mapping

**Deployed** to AWS Commercial Cloud with clear path to GovCloud migration.

---

**Document Version:** 2.6
**Last Updated:** February 11, 2026
**Status:** Current and Accurate
**ADRs:** 84 Architecture Decision Records (83 Deployed/Accepted, 1 Proposed)
