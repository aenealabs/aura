# System Overview

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This document provides a comprehensive view of Project Aura's system architecture, including component relationships, communication patterns, and deployment topology.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL CLIENTS                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │  Web UI  │  │   CLI    │  │   API    │  │ Webhooks │  │Integrations│     │
│  │ (React)  │  │          │  │ Clients  │  │ Receivers│  │(Slack/Jira)│     │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘      │
└───────┼─────────────┼─────────────┼─────────────┼─────────────┼─────────────┘
        │             │             │             │             │
        └─────────────┴─────────────┼─────────────┴─────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  AWS WAF (6 Security Rules) │ Rate Limiting │ TLS 1.3 │ Auth        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           KUBERNETES CLUSTER (EKS)                           │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       PRESENTATION LAYER                             │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │   │
│  │  │   REST API   │  │  GraphQL API │  │  WebSocket   │               │   │
│  │  │   Service    │  │   Service    │  │   Server     │               │   │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘               │   │
│  └─────────┼─────────────────┼─────────────────┼───────────────────────┘   │
│            │                 │                 │                            │
│            └─────────────────┼─────────────────┘                            │
│                              │                                              │
│  ┌───────────────────────────▼─────────────────────────────────────────┐   │
│  │                        AGENT LAYER                                   │   │
│  │                                                                      │   │
│  │  ┌────────────────────────────────────────────────────────────────┐ │   │
│  │  │                     ORCHESTRATOR                                │ │   │
│  │  │   - Task coordination    - State management                     │ │   │
│  │  │   - Agent dispatch       - Result aggregation                   │ │   │
│  │  └────────────────────────────┬───────────────────────────────────┘ │   │
│  │                               │                                      │   │
│  │      ┌────────────────────────┼────────────────────────┐            │   │
│  │      │                        │                        │            │   │
│  │      ▼                        ▼                        ▼            │   │
│  │  ┌─────────┐            ┌─────────┐            ┌─────────┐          │   │
│  │  │  CODER  │            │REVIEWER │            │VALIDATOR│          │   │
│  │  │  AGENT  │            │  AGENT  │            │  AGENT  │          │   │
│  │  │         │            │         │            │         │          │   │
│  │  │ Patch   │            │ Security│            │ Sandbox │          │   │
│  │  │ Gen     │            │ Review  │            │ Testing │          │   │
│  │  └────┬────┘            └────┬────┘            └────┬────┘          │   │
│  └───────┼──────────────────────┼──────────────────────┼───────────────┘   │
│          │                      │                      │                    │
│  ┌───────▼──────────────────────▼──────────────────────▼───────────────┐   │
│  │                      INTELLIGENCE LAYER                              │   │
│  │                                                                      │   │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │   │
│  │  │ CONTEXT RETRIEVAL│  │   BEDROCK LLM    │  │ NEURAL MEMORY    │   │   │
│  │  │                  │  │                  │  │                  │   │   │
│  │  │ - Graph queries  │  │ - Claude 3.5    │  │ - Titan Memory   │   │   │
│  │  │ - Vector search  │  │ - Embeddings     │  │ - JEPA Predictor │   │   │
│  │  │ - RRF fusion     │  │ - Guardrails     │  │ - RLM Context    │   │   │
│  │  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘   │   │
│  └───────────┼──────────────────────┼──────────────────────┼───────────┘   │
└──────────────┼──────────────────────┼──────────────────────┼────────────────┘
               │                      │                      │
               ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                      │
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   NEPTUNE   │  │ OPENSEARCH  │  │  DYNAMODB   │  │     S3      │        │
│  │   (Graph)   │  │  (Vector)   │  │   (State)   │  │   (Files)   │        │
│  │             │  │             │  │             │  │             │        │
│  │ - Call graph│  │ - Embeddings│  │ - Sessions  │  │ - Artifacts │        │
│  │ - Deps      │  │ - Similarity│  │ - Approvals │  │ - Backups   │        │
│  │ - Refs      │  │ - BM25      │  │ - Agent state│ │ - Logs      │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. API Gateway Layer

The entry point for all external traffic.

| Component | Technology | Function |
|-----------|------------|----------|
| Load Balancer | AWS ALB | Traffic distribution, TLS termination |
| WAF | AWS WAF | SQL injection, XSS, rate limiting |
| Authentication | Custom + Cognito | JWT validation, SSO support |

**Security Rules:**

```
Rule 1: Rate limiting (1000 req/min per IP)
Rule 2: Geographic restrictions (configurable)
Rule 3: SQL injection detection
Rule 4: XSS prevention
Rule 5: Known bad IP blocking
Rule 6: Request size limits (10MB max)
```

---

### 2. Presentation Layer

Handles all client-facing API operations.

**REST API Service:**

- FastAPI framework
- OpenAPI specification
- Request validation via Pydantic
- Response serialization

**GraphQL Service:**

- Strawberry GraphQL
- Relay-compatible pagination
- Real-time subscriptions via WebSocket

**WebSocket Server:**

- Real-time agent status updates
- Live vulnerability notifications
- Approval workflow events

---

### 3. Agent Layer

The multi-agent system that powers autonomous remediation.

#### Orchestrator

The central coordinator for all agent activities.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                                  │
│                                                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐        │
│  │ Task Queue     │  │ State Machine  │  │ Result Aggregator│       │
│  │                │  │                │  │                │        │
│  │ - Priority     │  │ - Workflow     │  │ - Merge results│        │
│  │ - Scheduling   │  │ - Transitions  │  │ - Conflict res │        │
│  │ - Load balance │  │ - Checkpoints  │  │ - Reporting    │        │
│  └────────────────┘  └────────────────┘  └────────────────┘        │
│                                                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐        │
│  │ Agent Registry │  │ Health Monitor │  │ Cost Tracker   │        │
│  │                │  │                │  │                │        │
│  │ - Discovery    │  │ - Heartbeats   │  │ - LLM tokens   │        │
│  │ - Capabilities │  │ - Auto-recover │  │ - Compute      │        │
│  │ - Versioning   │  │ - Circuit break│  │ - Budget alerts│        │
│  └────────────────┘  └────────────────┘  └────────────────┘        │
└─────────────────────────────────────────────────────────────────────┘
```

#### Coder Agent

Generates security patches using LLM capabilities.

**Responsibilities:**

- Analyze vulnerability context
- Generate fix proposals
- Apply coding patterns
- Handle multiple languages

**Process Flow:**

```
Vulnerability ──► Context Retrieval ──► LLM Prompt ──► Code Generation ──► Validation ──► Patch
```

#### Reviewer Agent

Validates patches against security policies.

**Review Criteria:**

- Security best practices (OWASP)
- Code quality standards
- Performance implications
- Backward compatibility

#### Validator Agent

Executes patches in isolated sandbox environments.

**Validation Categories:**

1. Syntax verification
2. Unit test execution
3. Security regression scanning
4. Performance benchmarking
5. Integration testing

---

### 4. Intelligence Layer

Provides AI capabilities and code understanding.

#### Context Retrieval Service

Hybrid GraphRAG implementation combining multiple retrieval strategies.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CONTEXT RETRIEVAL SERVICE                         │
│                                                                      │
│       Query ────────────────────────────────────────────►           │
│         │                                                            │
│         ├──────────────┐                                            │
│         │              │                                            │
│         ▼              ▼                                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │   NEPTUNE   │  │ OPENSEARCH  │  │ OPENSEARCH  │                 │
│  │   GRAPH     │  │   VECTOR    │  │    BM25     │                 │
│  │             │  │             │  │             │                 │
│  │ Structure   │  │ Semantic    │  │ Keyword     │                 │
│  │ traversal   │  │ similarity  │  │ matching    │                 │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │
│         │                │                │                         │
│         └────────────────┼────────────────┘                         │
│                          │                                          │
│                          ▼                                          │
│                 ┌─────────────────┐                                 │
│                 │  RRF FUSION     │                                 │
│                 │                 │                                 │
│                 │  Reciprocal     │                                 │
│                 │  Rank Fusion    │                                 │
│                 └────────┬────────┘                                 │
│                          │                                          │
│                          ▼                                          │
│                    Ranked Results                                   │
└─────────────────────────────────────────────────────────────────────┘
```

**Query Types:**

| Type | Source | Use Case |
|------|--------|----------|
| CALL_GRAPH | Neptune | Function call relationships |
| DEPENDENCIES | Neptune | Import/require relationships |
| INHERITANCE | Neptune | Class hierarchies |
| REFERENCES | Neptune | Variable/function references |
| SEMANTIC | OpenSearch | Similar code patterns |
| KEYWORD | OpenSearch | Exact text matching |

#### Bedrock LLM Service

Managed interface to Amazon Bedrock.

**Configuration:**

| Parameter | Value |
|-----------|-------|
| Model | Claude 3.5 Sonnet |
| Max Tokens | 8000 |
| Temperature | 0.2 (patch generation) |
| Guardrails | Enabled (prompt injection prevention) |

#### Neural Memory Service

Advanced context management using Titan architecture.

**Components:**

- **Titan Memory:** Long-term pattern storage
- **JEPA Predictor:** Embedding prediction for efficiency
- **RLM Context:** 100x context window scaling

---

### 5. Data Layer

Persistent storage for all platform data.

#### Neptune (Graph Database)

Stores code structure and relationships.

**Graph Schema:**

```
Nodes:
├── Repository (name, url, branch)
├── File (path, language, loc)
├── Class (name, docstring, line)
├── Function (name, signature, line)
├── Variable (name, type, scope)
└── Vulnerability (title, severity, cve)

Edges:
├── CONTAINS (Repository → File, File → Class/Function)
├── CALLS (Function → Function)
├── IMPORTS (File → File)
├── INHERITS (Class → Class)
├── REFERENCES (Function → Variable)
└── AFFECTS (Vulnerability → Function/File)
```

#### OpenSearch (Vector/Search)

Stores embeddings and enables search.

**Indexes:**

| Index | Purpose | Vector Dimension |
|-------|---------|------------------|
| code-embeddings | Code semantic search | 1536 |
| doc-embeddings | Documentation search | 1536 |
| vulnerability-db | CVE/CWE database | 768 |

#### DynamoDB (State Store)

Fast key-value storage for operational data.

**Tables:**

| Table | Partition Key | Sort Key | Purpose |
|-------|---------------|----------|---------|
| agent-state | agent_id | timestamp | Agent checkpoints |
| approval-requests | org_id | request_id | HITL workflow |
| user-sessions | user_id | session_id | Authentication |
| scan-results | repo_id | scan_id | Scan history |

#### S3 (Object Storage)

Blob storage for artifacts.

**Buckets:**

| Bucket | Purpose | Lifecycle |
|--------|---------|-----------|
| aura-artifacts-{env} | Build artifacts | 90 days |
| aura-backups-{env} | Database backups | 365 days |
| aura-logs-{env} | Application logs | 90 days |
| aura-patches-{env} | Generated patches | Indefinite |

---

## Deployment Topology

### Multi-AZ Deployment

```
                         Region: us-east-1
┌─────────────────────────────────────────────────────────────────────┐
│                                                                      │
│     Availability Zone A          Availability Zone B                │
│  ┌────────────────────────┐   ┌────────────────────────┐           │
│  │                        │   │                        │           │
│  │  ┌──────────────────┐  │   │  ┌──────────────────┐  │           │
│  │  │  NAT Gateway     │  │   │  │  NAT Gateway     │  │           │
│  │  └──────────────────┘  │   │  └──────────────────┘  │           │
│  │                        │   │                        │           │
│  │  ┌──────────────────┐  │   │  ┌──────────────────┐  │           │
│  │  │  EKS Workers     │  │   │  │  EKS Workers     │  │           │
│  │  │  (2-10 nodes)    │  │   │  │  (2-10 nodes)    │  │           │
│  │  └──────────────────┘  │   │  └──────────────────┘  │           │
│  │                        │   │                        │           │
│  │  ┌──────────────────┐  │   │  ┌──────────────────┐  │           │
│  │  │  Neptune Replica │  │   │  │  Neptune Primary │  │           │
│  │  └──────────────────┘  │   │  └──────────────────┘  │           │
│  │                        │   │                        │           │
│  │  ┌──────────────────┐  │   │  ┌──────────────────┐  │           │
│  │  │  OpenSearch Node │  │   │  │  OpenSearch Node │  │           │
│  │  └──────────────────┘  │   │  └──────────────────┘  │           │
│  │                        │   │                        │           │
│  └────────────────────────┘   └────────────────────────┘           │
│                                                                      │
│                    ┌────────────────────────┐                       │
│                    │    Availability Zone C │                       │
│                    │  ┌──────────────────┐  │                       │
│                    │  │  OpenSearch Node │  │                       │
│                    │  └──────────────────┘  │                       │
│                    └────────────────────────┘                       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Resource Specifications

| Component | Instance Type | Quantity | Scaling |
|-----------|---------------|----------|---------|
| EKS Workers (General) | m5.xlarge | 2-10 | HPA + Cluster Autoscaler |
| EKS Workers (GPU) | g4dn.xlarge | 0-2 | Manual |
| Neptune | db.r5.large | 2 (Multi-AZ) | Vertical |
| OpenSearch | r6g.large.search | 3 | Horizontal |
| DynamoDB | On-Demand | N/A | Auto |

---

## Communication Patterns

### Synchronous Communication

- REST API requests
- GraphQL queries
- Database queries

### Asynchronous Communication

- Agent task dispatch (SQS)
- Event notifications (EventBridge)
- Webhook delivery (SNS)

### Event-Driven Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Event Source │────►│ EventBridge  │────►│ Event Target │
│              │     │              │     │              │
│ - Agents     │     │ - Routing    │     │ - Lambda     │
│ - API        │     │ - Filtering  │     │ - SQS        │
│ - Scans      │     │ - Transform  │     │ - Step Funcs │
└──────────────┘     └──────────────┘     └──────────────┘
```

---

## Related Documentation

- [Architecture Index](./index.md)
- [Data Flow](./data-flow.md)
- [Security Architecture](./security-architecture.md)
- [Core Concepts](../../product/core-concepts/index.md)
- [HITL Sandbox Architecture](../../design/HITL_SANDBOX_ARCHITECTURE.md)

---

*Last updated: January 2026 | Version 1.0*
