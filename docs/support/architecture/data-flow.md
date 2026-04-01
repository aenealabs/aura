# Data Flow

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This document describes how data moves through Project Aura, from initial repository ingestion through vulnerability detection, patch generation, and deployment. Understanding these flows is essential for debugging, performance optimization, and security analysis.

---

## Primary Data Flows

### 1. Repository Ingestion Flow

When a repository is connected to Aura:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         REPOSITORY INGESTION FLOW                            │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌──────────────┐
    │   GitHub /   │
    │   GitLab     │
    └──────┬───────┘
           │
           │ 1. Clone Repository
           │    (OAuth / Deploy Key)
           ▼
    ┌──────────────┐
    │  Repository  │
    │   Service    │
    └──────┬───────┘
           │
           │ 2. Parse Files
           │
           ▼
    ┌──────────────┐
    │  AST Parser  │
    │  (Tree-sitter)│
    └──────┬───────┘
           │
           ├──────────────────────────────────────────┐
           │                                          │
           │ 3a. Extract Structure                    │ 3b. Generate Embeddings
           ▼                                          ▼
    ┌──────────────┐                           ┌──────────────┐
    │   Neptune    │                           │   Bedrock    │
    │   (Graph)    │                           │   Titan      │
    │              │                           │              │
    │ - Functions  │                           │ - Code embed │
    │ - Classes    │                           │ - Doc embed  │
    │ - Calls      │                           │              │
    │ - Imports    │                           └──────┬───────┘
    └──────────────┘                                  │
                                                      │
                                                      │ 4. Store Vectors
                                                      ▼
                                               ┌──────────────┐
                                               │  OpenSearch  │
                                               │   (Vector)   │
                                               │              │
                                               │ - Embeddings │
                                               │ - Metadata   │
                                               └──────────────┘
```

**Data Elements:**

| Stage | Input | Output | Storage |
|-------|-------|--------|---------|
| Clone | Git URL, credentials | File system | Temp storage |
| Parse | Source files | AST nodes | Memory |
| Structure | AST | Graph vertices/edges | Neptune |
| Embed | Code snippets | 1536-dim vectors | OpenSearch |

**Volume Estimates:**

| Repository Size | Parse Time | Vertices | Vectors |
|-----------------|------------|----------|---------|
| 10K LOC | ~30s | ~2,000 | ~500 |
| 100K LOC | ~5min | ~20,000 | ~5,000 |
| 1M LOC | ~45min | ~200,000 | ~50,000 |

---

### 2. Vulnerability Scan Flow

When a security scan is triggered:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         VULNERABILITY SCAN FLOW                              │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌──────────────┐
    │   Trigger    │
    │ (Schedule/   │
    │  Manual/PR)  │
    └──────┬───────┘
           │
           │ 1. Initiate Scan
           ▼
    ┌──────────────┐
    │  Scan        │
    │  Orchestrator│
    └──────┬───────┘
           │
           ├────────────────────────┬────────────────────────┐
           │                        │                        │
           ▼                        ▼                        ▼
    ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
    │    SAST      │         │     SCA      │         │   Secrets    │
    │   Scanner    │         │   Scanner    │         │   Scanner    │
    │              │         │              │         │              │
    │ - Pattern    │         │ - Dependency │         │ - API keys   │
    │ - Taint      │         │ - CVE lookup │         │ - Passwords  │
    │ - Dataflow   │         │ - License    │         │ - Tokens     │
    └──────┬───────┘         └──────┬───────┘         └──────┬───────┘
           │                        │                        │
           └────────────────────────┼────────────────────────┘
                                    │
                                    │ 2. Aggregate Results
                                    ▼
                             ┌──────────────┐
                             │   Results    │
                             │  Aggregator  │
                             └──────┬───────┘
                                    │
                                    │ 3. Deduplicate & Enrich
                                    ▼
                             ┌──────────────┐
                             │ Vulnerability │
                             │   Service    │
                             └──────┬───────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
       ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
       │  DynamoDB    │      │ EventBridge  │      │   Neptune    │
       │              │      │              │      │              │
       │ - Vuln record│      │ - vuln.detected│    │ - AFFECTS    │
       │ - Status     │      │ - Webhooks   │      │   edges      │
       │ - History    │      │              │      │              │
       └──────────────┘      └──────────────┘      └──────────────┘
```

**Scan Stages:**

| Scanner | Detection Method | Output |
|---------|------------------|--------|
| SAST | Pattern matching, taint analysis | Code vulnerabilities |
| SCA | Dependency manifest parsing, CVE DB | Library vulnerabilities |
| Secrets | Regex patterns, entropy analysis | Exposed credentials |

---

### 3. Patch Generation Flow

When a vulnerability requires remediation:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PATCH GENERATION FLOW                                │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌──────────────┐
    │ Vulnerability │
    │   Record     │
    └──────┬───────┘
           │
           │ 1. Request Patch
           ▼
    ┌──────────────┐
    │ Orchestrator │
    └──────┬───────┘
           │
           │ 2. Retrieve Context
           ▼
    ┌──────────────┐
    │   Context    │
    │  Retrieval   │
    └──────┬───────┘
           │
           ├───────────────┬───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │   Neptune    │ │  OpenSearch  │ │  OpenSearch  │
    │   GRAPH      │ │   VECTOR     │ │    BM25      │
    │              │ │              │ │              │
    │ - Call graph │ │ - Similar    │ │ - Keyword    │
    │ - Deps       │ │   patterns   │ │   match      │
    └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
           │               │               │
           └───────────────┼───────────────┘
                           │
                           │ 3. Fuse Results (RRF)
                           ▼
                    ┌──────────────┐
                    │ Context Docs │
                    │ (Ranked)     │
                    └──────┬───────┘
                           │
                           │ 4. Generate Patch
                           ▼
                    ┌──────────────┐
                    │    Coder     │
                    │    Agent     │
                    └──────┬───────┘
                           │
                           │ 5. LLM Call
                           ▼
                    ┌──────────────┐
                    │   Bedrock    │
                    │ Claude 3.5   │
                    └──────┬───────┘
                           │
                           │ 6. Parse & Validate
                           ▼
                    ┌──────────────┐
                    │    Patch     │
                    │   Parser     │
                    └──────┬───────┘
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
       ┌──────────────┐          ┌──────────────┐
       │  DynamoDB    │          │     S3       │
       │              │          │              │
       │ - Patch meta │          │ - Diff file  │
       │ - Status     │          │ - Context    │
       └──────────────┘          └──────────────┘
```

**Context Window Composition:**

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LLM CONTEXT WINDOW (~8000 tokens)                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ SYSTEM PROMPT (~500 tokens)                                  │   │
│  │ - Role definition                                            │   │
│  │ - Security guidelines                                        │   │
│  │ - Output format                                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ VULNERABILITY CONTEXT (~1000 tokens)                         │   │
│  │ - CVE details                                                │   │
│  │ - Affected code                                              │   │
│  │ - Location info                                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ CODEBASE CONTEXT (~4000 tokens)                              │   │
│  │ - Caller functions                                           │   │
│  │ - Called functions                                           │   │
│  │ - Related types                                              │   │
│  │ - Similar patterns                                           │   │
│  │ - Import structure                                           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ REMEDIATION GUIDANCE (~1500 tokens)                          │   │
│  │ - OWASP recommendations                                      │   │
│  │ - Language-specific patterns                                 │   │
│  │ - Example fixes                                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ USER PROMPT (~1000 tokens)                                   │   │
│  │ - Specific instruction                                       │   │
│  │ - Constraints                                                │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 4. Sandbox Validation Flow

When a patch requires testing:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SANDBOX VALIDATION FLOW                              │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌──────────────┐
    │    Patch     │
    │   (Ready)    │
    └──────┬───────┘
           │
           │ 1. Request Validation
           ▼
    ┌──────────────┐
    │  Validator   │
    │    Agent     │
    └──────┬───────┘
           │
           │ 2. Provision Sandbox
           ▼
    ┌──────────────┐
    │   Sandbox    │
    │ Orchestrator │
    └──────┬───────┘
           │
           │ 3. Launch Container
           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │                    ECS FARGATE SANDBOX                        │
    │  ┌────────────────────────────────────────────────────────┐  │
    │  │ ISOLATED VPC (No Internet, No Production Access)       │  │
    │  │                                                         │  │
    │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │  │
    │  │  │  Clone Repo │─►│ Apply Patch │─►│ Run Tests   │    │  │
    │  │  └─────────────┘  └─────────────┘  └──────┬──────┘    │  │
    │  │                                           │            │  │
    │  │     ┌─────────────────────────────────────┤            │  │
    │  │     │              │              │       │            │  │
    │  │     ▼              ▼              ▼       ▼            │  │
    │  │ ┌────────┐   ┌────────┐   ┌────────┐ ┌────────┐      │  │
    │  │ │ Syntax │   │  Unit  │   │Security│ │ Perf   │      │  │
    │  │ │ Check  │   │ Tests  │   │  Scan  │ │ Bench  │      │  │
    │  │ └───┬────┘   └───┬────┘   └───┬────┘ └───┬────┘      │  │
    │  │     │            │            │          │            │  │
    │  └─────┼────────────┼────────────┼──────────┼────────────┘  │
    │        │            │            │          │                │
    └────────┼────────────┼────────────┼──────────┼────────────────┘
             │            │            │          │
             └────────────┼────────────┼──────────┘
                          │            │
                          │ 4. Collect Results
                          ▼
                   ┌──────────────┐
                   │   Results    │
                   │  Collector   │
                   └──────┬───────┘
                          │
                          │ 5. Store & Notify
                          ▼
         ┌────────────────┴────────────────┐
         │                                 │
         ▼                                 ▼
  ┌──────────────┐                  ┌──────────────┐
  │  DynamoDB    │                  │ EventBridge  │
  │              │                  │              │
  │ - Test results│                 │ - sandbox.complete│
  │ - Metrics    │                  │ - patch.validated│
  └──────────────┘                  └──────────────┘
```

**Sandbox Isolation:**

| Control | Implementation |
|---------|----------------|
| Network | Isolated VPC, no internet gateway |
| Compute | Dedicated Fargate task |
| Storage | Ephemeral, destroyed after test |
| Time | 15-minute maximum execution |
| Resources | 2 vCPU, 4GB memory limit |

---

### 5. HITL Approval Flow

When human approval is required:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          HITL APPROVAL FLOW                                  │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌──────────────┐
    │ Validated    │
    │   Patch      │
    └──────┬───────┘
           │
           │ 1. Check Policy
           ▼
    ┌──────────────┐
    │    HITL      │
    │   Service    │
    └──────┬───────┘
           │
           │ 2. Create Approval Request
           ▼
    ┌──────────────┐
    │  DynamoDB    │
    │ (approvals)  │
    └──────┬───────┘
           │
           │ 3. Send Notifications
           ▼
    ┌──────────────┐
    │ Notification │
    │   Service    │
    └──────┬───────┘
           │
    ┌──────┴──────────────────────┬────────────────────┐
    │                             │                    │
    ▼                             ▼                    ▼
┌─────────┐              ┌─────────────┐        ┌─────────────┐
│  Email  │              │    Slack    │        │   Teams     │
│  (SES)  │              │             │        │             │
└─────────┘              └─────────────┘        └─────────────┘
    │                             │                    │
    └─────────────────────────────┼────────────────────┘
                                  │
                                  │ 4. Human Reviews
                                  ▼
                           ┌──────────────┐
                           │   Approval   │
                           │  Dashboard   │
                           └──────┬───────┘
                                  │
                        ┌─────────┴─────────┐
                        │                   │
                        ▼                   ▼
                 ┌──────────┐        ┌──────────┐
                 │ APPROVE  │        │  REJECT  │
                 └────┬─────┘        └────┬─────┘
                      │                   │
                      │                   │
                      ▼                   ▼
              ┌──────────────┐    ┌──────────────┐
              │   Deploy     │    │   Notify     │
              │   Service    │    │   Coder      │
              └──────────────┘    └──────────────┘
```

**Approval Policies:**

| Autonomy Level | Critical | High | Medium | Low |
|----------------|----------|------|--------|-----|
| FULL_HITL | Approve | Approve | Approve | Approve |
| HITL_FINAL | Approve | Approve | Approve | Approve |
| HITL_CRITICAL | Approve | Approve | Auto | Auto |
| FULL_AUTONOMOUS | Auto | Auto | Auto | Auto |

---

## Data Retention

| Data Type | Retention | Storage | Encryption |
|-----------|-----------|---------|------------|
| Vulnerability records | 7 years | DynamoDB | AES-256 |
| Patch history | 7 years | DynamoDB + S3 | AES-256 |
| Approval decisions | 7 years | DynamoDB | AES-256 |
| Scan results | 2 years | DynamoDB | AES-256 |
| Audit logs | 7 years | CloudWatch + S3 | AES-256 |
| Code graphs | Active repos | Neptune | AES-256 |
| Embeddings | Active repos | OpenSearch | AES-256 |
| Sandbox artifacts | 30 days | S3 | AES-256 |

---

## Data Access Patterns

### Read-Heavy Patterns

| Operation | Source | Frequency |
|-----------|--------|-----------|
| Dashboard queries | DynamoDB + Neptune | High |
| Context retrieval | Neptune + OpenSearch | High |
| Vulnerability listing | DynamoDB | High |

### Write-Heavy Patterns

| Operation | Destination | Frequency |
|-----------|-------------|-----------|
| Scan results | DynamoDB | Medium |
| Graph updates | Neptune | Low (on commit) |
| Embedding updates | OpenSearch | Low (on commit) |

---

## Related Documentation

- [Architecture Index](./index.md)
- [System Overview](./system-overview.md)
- [Security Architecture](./security-architecture.md)
- [Backup and Restore](../operations/backup-restore.md)

---

*Last updated: January 2026 | Version 1.0*
