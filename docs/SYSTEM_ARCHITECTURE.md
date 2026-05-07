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

```mermaid
flowchart TD
    subgraph UI[User Interface Layer]
        direction LR
        CKGE[CKGEConsole<br/>React]
        ApprovalUI[Approval Dashboard<br/>Future]
        GraphExplorer[GraphRAG Explorer<br/>Future]
    end

    subgraph Orchestration[Agent Orchestration Layer]
        direction TB
        S2O["System2Orchestrator · Python<br/>• Workflow Loop · Plan → Context → Code → Review → Validate<br/>• Agent Coordination<br/>• Error handling and retry logic"]
        subgraph Workers[Worker Agents]
            direction LR
            CoderA[Coder] --- ReviewerA[Reviewer] --- ValidatorA[Validator] --- MonitorA[Monitor]
        end
        S2O --> Workers
    end

    subgraph ContextRetrieval[Context Retrieval Layer]
        direction TB
        CRS["ContextRetrievalService · Agentic<br/>• QueryPlanningAgent · LLM-powered strategy selection<br/>• FilesystemNavigatorAgent · pattern / semantic / git search<br/>• ResultSynthesisAgent · multi-factor ranking<br/>• Parallel multi-strategy execution"]
    end

    subgraph Data[Data and Knowledge Layer]
        direction LR
        Neptune[Neptune · Graph<br/>Call graphs<br/>Dependencies<br/>Inheritance]
        OpenSearch[OpenSearch · Vectors<br/>Code embeddings<br/>Filesystem metadata]
        DynamoDB[DynamoDB · State<br/>Sandbox state<br/>Session data]
        S3[S3 · Artifacts<br/>Code repos<br/>Patches<br/>Reports]
    end

    subgraph LLM[AI / LLM Integration Layer]
        direction LR
        Claude[Bedrock · Claude<br/>Query planning<br/>Code gen<br/>Review]
        Titan[Bedrock · Titan<br/>Code embeddings<br/>Semantic search]
        OpenAI[OpenAI GPT-4<br/>Future · Code generation]
    end

    UI --> Orchestration --> ContextRetrieval --> Data --> LLM
```

---

## Cloud Abstraction Layer

**Status:** Deployed (ADR-004) | **Implementation Date:** December 16, 2025

Project Aura supports multi-cloud deployment through a Cloud Abstraction Layer (CAL) that enables deployment to both AWS GovCloud and Azure Government.

```mermaid
flowchart TD
    subgraph Platform[AURA PLATFORM · Cloud-Agnostic]
        direction TB
        subgraph BL[Business Logic Layer]
            direction TB
            BL1["Agent Orchestrator · Context Retrieval · LLM Service<br/>Sandbox Management · HITL Workflows · Security"]
        end

        subgraph CAL[Cloud Abstraction Layer · src/abstractions/]
            direction LR
            GDB[GraphDatabase<br/>Service]
            VDB[VectorDatabase<br/>Service]
            LLM[LLMService]
            STO[StorageService]
            SEC[SecretsService]
            FAC[CloudServiceFactory]
        end

        BL --> CAL

        subgraph AWS[AWS GovCloud]
            direction TB
            AWS1["Neptune<br/>OpenSearch<br/>Bedrock<br/>S3<br/>Secrets Manager"]
        end

        subgraph Azure[Azure Government]
            direction TB
            AZ1["Cosmos DB<br/>AI Search<br/>Azure OpenAI<br/>Blob Storage<br/>Key Vault"]
        end

        subgraph Mock[Mock · Tests]
            direction TB
            MK1["MockGraph<br/>MockVector<br/>MockLLM<br/>MockStorage<br/>MockSecrets"]
        end

        CAL --> AWS
        CAL --> Azure
        CAL --> Mock
    end
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

```mermaid
flowchart TB
    subgraph Commercial[AWS Commercial Cloud · Dev / QA]
        direction TB
        subgraph VPC["VPC · 10.0.0.0/16 · vpc-0123…ef0"]
            direction TB

            subgraph Dev["Dev Environment · ECS Fargate · NOT YET DEPLOYED"]
                direction LR
                D1[dnsmasq<br/>Service<br/>Fargate Task]
                D2[Orchestrator<br/>Service<br/>Fargate Task]
                D3[Coder<br/>Agent<br/>Fargate Task]
                D4[Reviewer<br/>Agent<br/>Fargate Task]
                DM["AWS Cloud Map · Service Discovery<br/>Scaling · EventBridge · weekday business hours<br/>Capacity · FARGATE_SPOT"]
                D1 --- D2 --- D3 --- D4 --- DM
            end

            subgraph Sandbox["Sandbox Environment · ECS Fargate · scale-to-zero · NOT YET DEPLOYED"]
                direction TB
                SB1["Ephemeral Sandbox Tasks · 0–10 concurrent<br/>• Isolated patch testing<br/>• Maximum security · DROP ALL capabilities<br/>• No external network access<br/>• DynamoDB state tracking with TTL"]
            end

            subgraph OS["OpenSearch Domain · VPC-only"]
                direction TB
                OS1["• 2x t3.small.search · Multi-AZ<br/>• KNN vector fields · 1536 dim · HNSW<br/>• Filesystem metadata index<br/>• Code embeddings<br/>• Lambda auto-index creation"]
            end

            subgraph EKS["Future · EKS Cluster · EC2 Managed Node Groups"]
                direction LR
                EKS1[System Nodes<br/>dnsmasq · CoreDNS<br/>2x t3.medium On-Demand]
                EKS2[App Nodes<br/>Production agents<br/>3–5x m5.xlarge On-Demand]
                EKS3[Sandbox Nodes<br/>Ephemeral testing · scale-to-zero<br/>0–10x t3.large Spot]
            end

            subgraph Endpoints["VPC Endpoints · 9 endpoints"]
                direction TB
                EP1["S3 · DynamoDB · Bedrock · CodeConnections · Logs · Secrets · ECR<br/>No NAT Gateways · CMMC L3 compliant · no internet egress"]
            end

            Dev --> Sandbox
            Sandbox --> OS
            OS --> EKS
            EKS --> Endpoints
        end
    end

    subgraph GovCloud[AWS GovCloud · US · Future · Q2 2026]
        direction TB
        GC1["Similar architecture, hardened:<br/>• STIG-hardened EKS nodes · DISA STIG compliance<br/>• FIPS 140-2 mode enabled<br/>• Private VPC endpoints only<br/>• Enhanced audit logging<br/>• On-Demand instances · no Spot for production"]
    end

    Commercial --> GovCloud
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

```mermaid
flowchart TD
    Start(["Agent request:<br/>Fix authentication vulnerability in JWT validation"])

    subgraph S1["Step 1 · Query Planning"]
        QP["QueryPlanningAgent<br/>• LLM analyses query intent<br/>• Key concepts: authentication · JWT · validation<br/>• Strategies: vector · filesystem · graph<br/>• Allocates per-strategy token budget"]
    end

    subgraph S2["Step 2 · Parallel Search Execution"]
        direction TB
        VS["Vector · OpenSearch KNN<br/>Embed query · KNN on docstring_embedding<br/>Returns: auth_service.py · jwt_validator.py · score 9.5"]
        FS["Filesystem · OpenSearch metadata<br/>Pattern: **/auth/*.py · wildcard on file_path<br/>Returns: auth_service.py · auth_middleware.py · score 8.0"]
        GS["Graph · Neptune Gremlin<br/>Functions calling JWT validation<br/>Traverse call graph<br/>Returns: login.py · api_auth.py · score 7.5"]
    end

    subgraph S3["Step 3 · Result Synthesis"]
        RS["ResultSynthesisAgent<br/>Raw: 5 files (2 duplicates) · dedup → 3 unique<br/>Composite scores:<br/>1. auth_service.py · 24.5 · vector + filesystem + graph<br/>2. jwt_validator.py · 18.2 · vector + graph<br/>3. auth_middleware.py · 12.0 · filesystem<br/>Budget fit (50k tokens): 15k + 10k + 8k = 33k · 66%"]
    end

    subgraph S4["Step 4 · Context Response"]
        CR["HybridContext<br/>files: 3 ranked entries · total_tokens: 33000<br/>strategies_used: vector · filesystem · graph<br/>query: original agent request"]
    end

    subgraph S5["Step 5 · Delivered to Agent Orchestrator"]
        OA["Coder Agent receives ranked context<br/>Generates patch with high-quality context<br/>Expected · 3–5x better code understanding"]
    end

    Start --> S1 --> S2 --> S3 --> S4 --> S5
```

---

## Agent Orchestration

**Hybrid Warm Pool Architecture** (Recommended Pattern)

The Agent Orchestrator uses a cost-effective warm pool deployment pattern that provides zero cold start while minimizing infrastructure costs (~$28/month vs $175/month always-on).

```mermaid
flowchart TD
    subgraph API["API Layer"]
        A1["POST /api/v1/orchestrate · submit job<br/>GET /api/v1/orchestrate/{id} · status<br/>DELETE /api/v1/orchestrate/{id} · cancel<br/>WS /api/v1/orchestrate/{id}/stream · live updates"]
    end

    subgraph Svc["OrchestrationService"]
        S1["DynamoDB · aura-orchestrator-jobs-{env} · job state<br/>SQS · aura-orchestrator-tasks-{env} · job dispatch<br/>Dual-mode · MOCK testing / AWS production"]
    end

    subgraph Warm["Warm Pool · EKS · 1 replica"]
        W1["orchestrator_server.py<br/>HTTP · /health/live · /health/ready · /metrics<br/>SQS consumer · long-polls every 5 s<br/>Zero cold start · always-on"]
    end

    subgraph Loop["System2Orchestrator · main loop"]
        direction TB
        P1["Phase 1 · PLAN<br/>Receive task · Validate via InputSanitizer · Create execution plan"]
        P2["Phase 2 · CONTEXT · Agentic Search<br/>ContextRetrievalService.retrieve_context · multi-strategy<br/>Returns HybridContext · budget 100k tokens"]
        P3["Phase 3 · CODE<br/>Coder Agent · LLM Claude / GPT-4 · AST validates syntax · returns unified diff"]
        P4["Phase 4 · REVIEW<br/>Reviewer Agent · OWASP Top 10 + AI threats · code quality · review report"]
        P5["Phase 5 · VALIDATE · Sandbox<br/>FargateSandboxOrchestrator.create_sandbox<br/>Apply patch · run test suite · collect results · destroy_sandbox"]
        P6["Phase 6 · MONITOR<br/>Log activity · track security findings<br/>Generate comprehensive report"]
        P1 --> P2 --> P3 --> P4 --> P5 --> P6
    end

    subgraph HITL["HITL Approval · Future"]
        H1["Present findings to human reviewer<br/>Approval Dashboard · React UI · SNS notifications · apply patch on approval"]
    end

    API --> Svc --> Warm --> Loop --> HITL
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

```mermaid
flowchart TD
    subgraph Settings[Settings Layer]
        direction LR
        Defaults[Platform Defaults<br/>DynamoDB]
        Overrides[Organization Overrides<br/>DynamoDB]
        SettingsAPI[Settings API<br/>REST · Admin]
        SettingsAPI --> Overrides --> Defaults
    end

    subgraph MTS[Mode Transition Service]
        MT1["State machine · ACTIVE → DRAINING → COMPLETING → SCALING → ACTIVE<br/>• 5-minute cooldown · anti-thrashing<br/>• Graceful in-flight job completion<br/>• K8s warm pool scaling via RBAC"]
    end

    subgraph Modes[Deployment Modes]
        direction LR
        OnDemand["ON-DEMAND Mode<br/>EKS Job per request<br/>~30s cold start"]
        Warm["WARM POOL Mode<br/>Always-on replica · 1–10<br/>0s cold start"]
        Hybrid["HYBRID Mode<br/>Warm pool baseline + burst overflow<br/>0s pool · 30s burst"]
    end

    Settings --> MTS
    MTS --> OnDemand
    MTS --> Warm
    MTS --> Hybrid
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

```mermaid
flowchart TD
    Default["Platform Default<br/>on_demand"]
    OrgA["Org A · Override<br/>warm_pool"]
    OrgB["Org B · No override<br/>uses on_demand"]
    OrgC["Org C · Override<br/>hybrid · burst overflow"]
    Default --> OrgA
    Default --> OrgB
    Default --> OrgC
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

```mermaid
flowchart TD
    subgraph Orch[FargateSandboxOrchestrator · Python]
        O1["create_sandbox · sandbox_id, patch_id, test_suite<br/>destroy_sandbox · sandbox_id<br/>get_sandbox_status · sandbox_id<br/>get_sandbox_logs · sandbox_id"]
    end

    subgraph Lifecycle[Sandbox Lifecycle]
        L1["1 · Provision<br/>Create ECS task with sandbox Docker image<br/>Store state in DynamoDB · sandbox_id, task_arn, created_at<br/>Set TTL for auto-cleanup · 2 hours"]
        L2["2 · Execute<br/>Apply patch to codebase<br/>Run test suite · pytest · npm test · etc.<br/>Collect results to CloudWatch Logs"]
        L3["3 · Monitor<br/>Check task status · RUNNING / STOPPED<br/>Tail CloudWatch Logs<br/>Return results to orchestrator"]
        L4["4 · Cleanup<br/>Stop ECS task<br/>Delete DynamoDB state<br/>Logs retained for 30 days"]
        L1 --> L2 --> L3 --> L4
    end

    subgraph Security[Sandbox Security Isolation]
        direction TB
        SC1["Docker Container · Fargate Task<br/>• Linux capabilities · DROP ALL<br/>• Read-only root filesystem<br/>• Non-root user · UID 2000<br/>• No privileged mode<br/>• Temp directory · /tmp tmpfs ephemeral"]
        SC2["Network Isolation · Security Group<br/>• Ingress · DENY ALL<br/>• Egress · ALLOW only to dnsmasq port 53<br/>• Metadata service 169.254.169.254 · BLOCKED"]
        SC3["Resource Limits<br/>• CPU · 0.5 vCPU<br/>• Memory · 1 GB<br/>• Ephemeral storage · 20 GB<br/>• Task timeout · 30 minutes"]
    end

    Notes["Execution window · 30-minute task timeout<br/>Scalability · 0–100 concurrent sandboxes"]

    Orch --> Lifecycle --> Security --> Notes
```

**DynamoDB State Tracking:**

```mermaid
flowchart TD
    subgraph Tbl["Sandbox State Table · aura-sandbox-state"]
        T1["Partition key · sandbox_id · String<br/><br/>Attributes:<br/>• task_arn · ECS task ARN<br/>• patch_id · associated patch<br/>• test_suite · test command<br/>• status · PROVISIONING / RUNNING / STOPPED / FAILED<br/>• created_at · timestamp<br/>• ttl · auto-delete after 2 hours<br/>• log_group · CloudWatch Logs group name<br/><br/>TTL enabled · automatic cleanup prevents orphaned state"]
    end
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

```mermaid
flowchart TD
    subgraph S1["1 · User Request"]
        U1["CKGEConsole · React UI<br/>Submit task · Fix CVE-2024-XXXX"]
        U2["API Gateway · Future · → Lambda → SQS"]
    end

    subgraph S2["2 · Task Processing"]
        T1["System2Orchestrator<br/>Receives task from SQS · validates via InputSanitizer · creates execution plan"]
        T2["ContextRetrievalService · Agentic Search<br/>Query · CVE-2024-XXXX vulnerability code<br/>Multi-strategy · graph + vector + filesystem<br/>Returns HybridContext with ranked files"]
        T1 --> T2
    end

    subgraph S3["3 · Code Generation"]
        C1["Coder Agent<br/>Receives context · 3–5x better quality<br/>LLM generates patch · Claude via Bedrock<br/>AST Parser validates syntax<br/>Returns unified diff"]
    end

    subgraph S4["4 · Code Review"]
        R1["Reviewer Agent<br/>Security analysis · OWASP Top 10<br/>Code quality checks<br/>Returns findings · severity CRITICAL / HIGH / MEDIUM / LOW"]
    end

    subgraph S5["5 · Sandbox Testing"]
        SB1["FargateSandboxOrchestrator<br/>create_sandbox · sandbox_id, patch, test_suite<br/>ECS Fargate task · isolated · no external network<br/>Apply patch → run tests → collect results<br/>destroy_sandbox · returns PASS / FAIL + logs"]
    end

    subgraph S6["6 · Monitoring & Reporting"]
        M1["Monitor Agent<br/>Log activity · tokens used · LOC changed<br/>Track security findings by severity<br/>Generate comprehensive report"]
    end

    subgraph S7["7 · HITL Approval · Future"]
        H1["SNS notification → Email / Slack<br/>Human reviews findings · Approval Dashboard · React UI<br/>Approve / Reject<br/>If approved · apply patch to production"]
    end

    U1 --> T1
    U2 --> T1
    S2 --> S3 --> S4 --> S5 --> S6 --> S7
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

```mermaid
flowchart TD
    subgraph P1["Phase 1 · DEPLOYED ✓"]
        P1B["AWS Commercial Cloud · us-east-1<br/>• VPC · vpc-0123…ef0<br/>• Subnets · 2 public + 2 private<br/>• VPC Endpoints · 9 · S3 · DynamoDB · Bedrock · etc.<br/>• Security Groups · 7<br/>• IAM Roles · 7 service roles<br/>• Workloads · VPC Endpoints + Flow Logs"]
    end

    subgraph P2["Phase 2 · READY FOR DEPLOYMENT"]
        OS["OpenSearch Domain<br/>• CloudFormation · 685 lines<br/>• KNN vector index schema defined<br/>• Lambda index creator ready<br/>• Deploy script · deploy-agentic-search.sh<br/>• Status · NOT DEPLOYED"]
        ECS["ECS Fargate Clusters<br/>• Dev cluster template · 600 lines<br/>• Services template · 700 lines<br/>• Sandbox template · 450 lines<br/>• Dockerfiles · 3<br/>• Deployment scripts · 2<br/>• Status · NOT DEPLOYED"]
    end

    subgraph P3["Phase 3 · PLANNED · Q2 2026"]
        GC["AWS GovCloud · US · Migration<br/>• STIG-hardened EKS nodes<br/>• FIPS 140-2 mode enabled<br/>• Private VPC endpoints only<br/>• Enhanced audit logging<br/>• CMMC Level 3 certification"]
    end

    P1 --> P2 --> P3
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
