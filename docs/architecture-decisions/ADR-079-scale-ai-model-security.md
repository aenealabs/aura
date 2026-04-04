# ADR-079: Scale and AI Model Security

## Status

Deployed

## Date

2026-02-03

## Reviews

| Reviewer | Role | Date | Verdict |
|----------|------|------|---------|
| Pending | AWS AI SaaS Architect | - | - |
| Pending | Senior Systems Architect | - | - |
| Pending | Cybersecurity Analyst | - | - |
| Pending | Test Architect | - | - |

### Review Summary

_Awaiting review._

## Context

### Market Opportunity

The intersection of scale infrastructure and AI model security represents a rapidly emerging market. As of publication, as enterprises deploy larger LLMs and train custom models, new security challenges arise that are not fully addressed by the tools we have surveyed.

**Target Markets:**
- **OpenAI/Anthropic** - Model security for frontier labs ($10B+ valuations)
- **Microsoft** - Azure AI security integration
- **Google** - Vertex AI and GCP security
- **Enterprise AI Teams** - Custom model deployment security

**Market Opportunity:** High demand from AI-first enterprises and hyperscalers

### Current State

Project Aura excels at code security and has foundational LLM integration. However, gaps exist for hyperscale deployments and AI-specific security:

| Current Capability | Gap | Business Impact |
|-------------------|-----|-----------------|
| Neptune graph (single cluster) | Cannot scale to billion-node codebases | Limited to mid-size enterprises |
| Batch code analysis | No real-time CI/CD feedback | Developer friction |
| Code vulnerability detection | No model weight/training security | Missing AI market |
| Semantic guardrails (input) | No protection for model artifacts | Model theft risk |

### Requirements

| ID | Requirement | Source |
|----|-------------|--------|
| R1 | Analyze 10M+ file codebases with sub-second queries | Enterprise scale |
| R2 | Sub-second vulnerability feedback in CI/CD | Developer experience |
| R3 | Cross-language dependency resolution at scale | Monorepo support |
| R4 | Detect AI model weight exfiltration attempts | AI lab security |
| R5 | Detect training data poisoning attacks | Model integrity |
| R6 | Protect inference endpoints from adversarial inputs | Production security |
| R7 | Scale Neptune to 1B+ vertices | Hyperscale requirement |

## Decision

Implement a Scale and AI Model Security service cluster that enables Project Aura to operate at hyperscale (billions of code relationships) and protect AI model artifacts from emerging threats.

### Core Services

### 1. Streaming Analysis Engine

**Responsibilities:**
- Real-time code analysis as files are committed
- Incremental graph updates (no full re-indexing)
- Sub-second vulnerability feedback to CI/CD
- Parallel analysis across multiple repositories
- Prioritized analysis queue (critical paths first)
- Integration with GitHub Actions, GitLab CI, CodeBuild

**Performance Targets:**
- Single file analysis: <500ms
- Incremental commit analysis: <2s
- Full PR analysis: <30s
- Graph update propagation: <1s

**Architecture Approach:**
- Event-driven with Kinesis Data Streams
- Lambda for lightweight analysis, EKS for heavy
- Redis caching for hot paths
- Pre-computed impact graphs

### 2. Polyglot Dependency Graph

**Responsibilities:**
- Unified dependency graph across all languages
- Cross-language call tracking (e.g., Python FFI to C)
- Monorepo support with package boundaries
- Neptune sharding for billion-node scale
- Materialized views for common query patterns
- Federated queries across shards

**Scale Targets:**
- 1B+ vertices (code entities)
- 10B+ edges (relationships)
- 10ms P95 query latency
- 100K QPS sustained

**Sharding Strategy:**
- Horizontal sharding by repository/organization
- Graph-aware partitioning (minimize cross-shard edges)
- Read replicas for query scaling
- Write coalescing for batch efficiency

### 3. Model Weight Guardian

**Responsibilities:**
- Detect unauthorized model weight access/download
- Monitor for weight exfiltration patterns
- Track model artifact provenance
- Watermarking detection for leaked models
- Integration with model registries (MLflow, SageMaker)
- Differential privacy verification

**Detection Methods:**
- Access pattern anomaly detection (unusual bulk downloads)
- Network egress monitoring for model-sized transfers
- Weight fingerprinting for leak detection
- API usage patterns indicating extraction attacks

### 4. Training Data Sentinel

**Responsibilities:**
- Detect training data poisoning attempts
- Monitor data pipeline integrity
- Track data lineage and provenance
- Identify malicious examples in datasets
- Backdoor trigger detection
- Data quality metrics and anomaly detection

**Detection Categories:**
- Label flipping attacks
- Backdoor injection (trigger patterns)
- Data pollution (adversarial examples)
- Gradient-based attacks on training
- Dataset attribution (source tracking)

## Architecture

### Streaming Analysis Engine Architecture

```
+-----------------------------------------------------------------------------+
|                    Streaming Analysis Engine Architecture                    |
+-----------------------------------------------------------------------------+
|                                                                              |
|  Code Events (Commits, PRs, Pushes)                                         |
|  +----------------------------------------------------------------------+   |
|  |  GitHub Webhooks    GitLab Webhooks    CodeCommit Events             |   |
|  +----------------------------------------------------------------------+   |
|         |                     |                     |                        |
|         v                     v                     v                        |
|  +----------------------------------------------------------------------+   |
|  |                    Event Ingestion Layer                              |   |
|  |                                                                       |   |
|  |  +------------------+  +-------------------+  +-------------------+   |   |
|  |  | API Gateway      |  | EventBridge       |  | Kinesis Data      |   |   |
|  |  | (Webhooks)       |  | (Internal Events) |  | Streams           |   |   |
|  |  +------------------+  +-------------------+  +-------------------+   |   |
|  +----------------------------------------------------------------------+   |
|         |                                                                    |
|         v                                                                    |
|  +----------------------------------------------------------------------+   |
|  |                    Analysis Orchestrator                              |   |
|  |                                                                       |   |
|  |  +-------------------+    +-------------------+    +-----------------+ |   |
|  |  | Priority Queue    |    | Work Distribution |    | Result          | |   |
|  |  |                   |    |                   |    | Aggregator      | |   |
|  |  | - Critical paths  |    | - Lambda (light)  |    |                 | |   |
|  |  | - Security files  |--->| - EKS (heavy)     |--->| - Merge results | |   |
|  |  | - Dependencies    |    | - GPU (ML)        |    | - Cache update  | |   |
|  |  +-------------------+    +-------------------+    +-----------------+ |   |
|  +----------------------------------------------------------------------+   |
|         |                                                                    |
|         v                                                                    |
|  +----------------------------------------------------------------------+   |
|  |                    Incremental Analyzers                              |   |
|  |                                                                       |   |
|  |  +------------------+  +-------------------+  +-------------------+   |   |
|  |  | AST Diff         |  | Dependency Delta  |  | Vulnerability     |   |   |
|  |  | Analyzer         |  | Resolver          |  | Scanner           |   |   |
|  |  |                  |  |                   |  |                   |   |   |
|  |  | - Only changed   |  | - Lockfile diffs  |  | - Affected code   |   |   |
|  |  |   functions      |  | - Transitive      |  | - New vulns only  |   |   |
|  |  +------------------+  +-------------------+  +-------------------+   |   |
|  |                                                                       |   |
|  |  +------------------+  +-------------------+  +-------------------+   |   |
|  |  | Impact Graph     |  | Semantic          |  | SBOM Delta        |   |   |
|  |  | Calculator       |  | Classifier        |  | Generator         |   |   |
|  |  |                  |  | (Embedding)       |  |                   |   |   |
|  |  | - Call paths     |  | - Change type     |  | - Component       |   |   |
|  |  | - Data flows     |  | - Risk score      |  |   changes         |   |   |
|  |  +------------------+  +-------------------+  +-------------------+   |   |
|  +----------------------------------------------------------------------+   |
|         |                                                                    |
|         v                                                                    |
|  +----------------------------------------------------------------------+   |
|  |                    Graph Update Service                               |   |
|  |                                                                       |   |
|  |  +-------------------+    +-------------------+    +-----------------+ |   |
|  |  | Batch Writer      |    | Cache Invalidator |    | Event           | |   |
|  |  |                   |    |                   |    | Publisher       | |   |
|  |  | - Coalesce writes |    | - Redis/ElastiC.  |    | - SNS/SQS       | |   |
|  |  | - Neptune bulk    |    | - Materialized    |    | - Webhook       | |   |
|  |  +-------------------+    +-------------------+    +-----------------+ |   |
|  +----------------------------------------------------------------------+   |
|         |                                                                    |
|         v                                                                    |
|  +----------------------------------------------------------------------+   |
|  |                    CI/CD Feedback                                     |   |
|  |                                                                       |   |
|  |  +------------------+  +-------------------+  +-------------------+   |   |
|  |  | GitHub Checks    |  | GitLab Comments   |  | PR Decorations    |   |   |
|  |  +------------------+  +-------------------+  +-------------------+   |   |
|  +----------------------------------------------------------------------+   |
|                                                                              |
+-----------------------------------------------------------------------------+
```

### Polyglot Dependency Graph Architecture

```
+-----------------------------------------------------------------------------+
|                    Polyglot Dependency Graph Architecture                    |
+-----------------------------------------------------------------------------+
|                                                                              |
|  Query Layer                                                                 |
|  +----------------------------------------------------------------------+   |
|  |  +------------------+  +-------------------+  +-------------------+   |   |
|  |  | GraphQL API      |  | Gremlin Proxy     |  | REST API          |   |   |
|  |  +------------------+  +-------------------+  +-------------------+   |   |
|  +----------------------------------------------------------------------+   |
|         |                                                                    |
|         v                                                                    |
|  +----------------------------------------------------------------------+   |
|  |                    Query Router & Optimizer                           |   |
|  |                                                                       |   |
|  |  +-------------------+    +-------------------+    +-----------------+ |   |
|  |  | Query Parser      |    | Shard Router      |    | Query Cache     | |   |
|  |  |                   |    |                   |    |                 | |   |
|  |  | - Analyze query   |    | - Identify shards |    | - Redis cluster | |   |
|  |  | - Optimize plan   |    | - Fan-out/gather  |    | - 1hr TTL       | |   |
|  |  +-------------------+    +-------------------+    +-----------------+ |   |
|  +----------------------------------------------------------------------+   |
|         |                                                                    |
|         v                                                                    |
|  +----------------------------------------------------------------------+   |
|  |                    Neptune Shard Cluster                              |   |
|  |                                                                       |   |
|  |  +-------------+  +-------------+  +-------------+  +-------------+   |   |
|  |  | Shard 1     |  | Shard 2     |  | Shard 3     |  | Shard N     |   |   |
|  |  | (Org A-E)   |  | (Org F-K)   |  | (Org L-R)   |  | (Org S-Z)   |   |   |
|  |  |             |  |             |  |             |  |             |   |   |
|  |  | 250M nodes  |  | 250M nodes  |  | 250M nodes  |  | 250M nodes  |   |   |
|  |  | 2.5B edges  |  | 2.5B edges  |  | 2.5B edges  |  | 2.5B edges  |   |   |
|  |  +-------------+  +-------------+  +-------------+  +-------------+   |   |
|  |        |               |               |               |              |   |
|  |        v               v               v               v              |   |
|  |  +----------------------------------------------------------------------+|
|  |  |                    Read Replica Layer                                 ||
|  |  |                                                                       ||
|  |  |  Each shard: 2 read replicas for query scaling                       ||
|  |  |  Total: 2N read replicas for 100K QPS                                ||
|  |  +----------------------------------------------------------------------+|
|  +----------------------------------------------------------------------+   |
|         |                                                                    |
|         v                                                                    |
|  +----------------------------------------------------------------------+   |
|  |                    Materialized View Store (DynamoDB)                 |   |
|  |                                                                       |   |
|  |  Pre-computed views for common patterns:                              |   |
|  |  - Direct dependencies per package                                    |   |
|  |  - Transitive dependency closure                                      |   |
|  |  - Vulnerability impact paths                                         |   |
|  |  - Call graph for hot functions                                       |   |
|  +----------------------------------------------------------------------+   |
|                                                                              |
|  Cross-Shard Query Optimization                                             |
|  +----------------------------------------------------------------------+   |
|  |                                                                       |   |
|  |  +-------------------+    +-------------------+                       |   |
|  |  | Edge Replication  |    | Federated Query   |                       |   |
|  |  |                   |    | Engine            |                       |   |
|  |  | - Copy cross-org  |    | - Parallel exec   |                       |   |
|  |  |   edges to both   |    | - Result merge    |                       |   |
|  |  |   shards          |    | - Timeout mgmt    |                       |   |
|  |  +-------------------+    +-------------------+                       |   |
|  +----------------------------------------------------------------------+   |
|                                                                              |
+-----------------------------------------------------------------------------+
```

### AI Model Security Architecture

```
+-----------------------------------------------------------------------------+
|                    AI Model Security Architecture                            |
+-----------------------------------------------------------------------------+
|                                                                              |
|  Model Lifecycle Monitoring                                                  |
|  +----------------------------------------------------------------------+   |
|  |                                                                       |   |
|  |  +------------------+  +-------------------+  +-------------------+   |   |
|  |  | Training         |  | Model Registry    |  | Inference         |   |   |
|  |  | Pipeline         |  | (MLflow/SM)       |  | Endpoints         |   |   |
|  |  +------------------+  +-------------------+  +-------------------+   |   |
|  |         |                     |                       |               |   |
|  |         v                     v                       v               |   |
|  +----------------------------------------------------------------------+   |
|                                                                              |
|  +----------------------------------------------------------------------+   |
|  |                    Model Weight Guardian                              |   |
|  |                                                                       |   |
|  |  +-------------------+    +-------------------+    +-----------------+ |   |
|  |  | Access Monitor    |    | Exfiltration      |    | Fingerprint     | |   |
|  |  |                   |    | Detector          |    | Tracker         | |   |
|  |  | - S3 access logs  |    | - Network egress  |    | - Weight hash   | |   |
|  |  | - API calls       |    | - Large transfers |    | - Watermark     | |   |
|  |  | - Download        |--->| - Unusual dest    |--->| - Leak detect   | |   |
|  |  |   patterns        |    | - Time patterns   |    | - Attribution   | |   |
|  |  +-------------------+    +-------------------+    +-----------------+ |   |
|  |         |                         |                       |            |   |
|  |         v                         v                       v            |   |
|  |  +----------------------------------------------------------------------+|
|  |  |                    Alert & Response                                   ||
|  |  |                                                                       ||
|  |  |  - SNS alerts for anomalies                                          ||
|  |  |  - Automatic access revocation (CRITICAL)                            ||
|  |  |  - HITL review for suspicious (HIGH)                                 ||
|  |  |  - Forensic data collection                                          ||
|  |  +----------------------------------------------------------------------+|
|  +----------------------------------------------------------------------+   |
|                                                                              |
|  +----------------------------------------------------------------------+   |
|  |                    Training Data Sentinel                             |   |
|  |                                                                       |   |
|  |  +-------------------+    +-------------------+    +-----------------+ |   |
|  |  | Data Pipeline     |    | Anomaly           |    | Provenance      | |   |
|  |  | Monitor           |    | Detector          |    | Tracker         | |   |
|  |  |                   |    |                   |    |                 | |   |
|  |  | - Ingestion logs  |    | - Distribution    |    | - Source hash   | |   |
|  |  | - Transform ops   |    |   shifts          |    | - Chain of      | |   |
|  |  | - Batch metadata  |--->| - Label anomalies |--->|   custody       | |   |
|  |  |                   |    | - Trigger detect  |    | - Attestation   | |   |
|  |  +-------------------+    +-------------------+    +-----------------+ |   |
|  |         |                         |                       |            |   |
|  |         v                         v                       v            |   |
|  |  +----------------------------------------------------------------------+|
|  |  |                    Poisoning Detection                                ||
|  |  |                                                                       ||
|  |  |  +------------------+  +-------------------+  +------------------+   ||
|  |  |  | Label Flip       |  | Backdoor Trigger  |  | Gradient Attack  |   ||
|  |  |  | Detector         |  | Scanner           |  | Detector         |   ||
|  |  |  |                  |  |                   |  |                  |   ||
|  |  |  | - Statistical    |  | - Pattern search  |  | - Loss landscape |   ||
|  |  |  |   analysis       |  | - Activation map  |  |   analysis       |   ||
|  |  |  +------------------+  +-------------------+  +------------------+   ||
|  |  +----------------------------------------------------------------------+|
|  +----------------------------------------------------------------------+   |
|                                                                              |
|  +----------------------------------------------------------------------+   |
|  |                    Inference Protection                               |   |
|  |                                                                       |   |
|  |  +-------------------+    +-------------------+    +-----------------+ |   |
|  |  | Adversarial       |    | Model Extraction  |    | Prompt          | |   |
|  |  | Input Detector    |    | Detector          |    | Injection       | |   |
|  |  |                   |    |                   |    | (ADR-065)       | |   |
|  |  | - Perturbation    |    | - Query patterns  |    | - Semantic      | |   |
|  |  | - Out-of-dist     |    | - Probing detect  |    |   guardrails    | |   |
|  |  +-------------------+    +-------------------+    +-----------------+ |   |
|  +----------------------------------------------------------------------+   |
|                                                                              |
+-----------------------------------------------------------------------------+
```

## Data Models

### Neptune Graph Schema Extensions

```gremlin
// New Vertex Types for Scale

g.addV('ShardMetadata')
  .property('id', shard_id)
  .property('shard_name', 'shard-1')
  .property('organization_range', 'A-E')
  .property('node_count', 250000000)
  .property('edge_count', 2500000000)
  .property('last_compaction', timestamp)

g.addV('MaterializedView')
  .property('id', view_id)
  .property('view_type', 'transitive_deps|call_graph|vuln_impact')
  .property('source_query', gremlin_query)
  .property('ttl_seconds', 3600)
  .property('computed_at', timestamp)

g.addV('StreamEvent')
  .property('id', event_id)
  .property('event_type', 'commit|pr|push')
  .property('repository_id', repo_id)
  .property('affected_files', [file_paths])
  .property('processing_status', 'pending|processing|complete')
  .property('received_at', timestamp)

// New Vertex Types for AI Security

g.addV('MLModel')
  .property('id', model_id)
  .property('name', 'code-llama-7b')
  .property('version', 'v1.2.0')
  .property('registry', 'sagemaker|mlflow|huggingface')
  .property('weight_hash', sha256)
  .property('size_bytes', 14000000000)
  .property('created_at', timestamp)

g.addV('ModelAccess')
  .property('id', access_id)
  .property('model_id', model_ref)
  .property('accessor_id', user_or_service)
  .property('access_type', 'read|download|deploy')
  .property('source_ip', ip_address)
  .property('bytes_transferred', bytes)
  .property('timestamp', access_time)

g.addV('TrainingDataset')
  .property('id', dataset_id)
  .property('name', 'code-corpus-v3')
  .property('size_samples', 10000000)
  .property('source_hash', sha256)
  .property('created_at', timestamp)

g.addV('DataPipelineRun')
  .property('id', run_id)
  .property('dataset_id', dataset_ref)
  .property('transforms', [transform_list])
  .property('output_hash', sha256)
  .property('anomaly_score', 0.0-1.0)
  .property('completed_at', timestamp)

g.addV('PoisoningAlert')
  .property('id', alert_id)
  .property('dataset_id', dataset_ref)
  .property('alert_type', 'label_flip|backdoor|gradient_attack')
  .property('confidence', 0.0-1.0)
  .property('affected_samples', [sample_ids])
  .property('detected_at', timestamp)

// New Edge Types

g.addE('ACCESS_TO').from(model_access).to(ml_model)
  .property('duration_ms', 1500)
  .property('anomaly_score', 0.1)

g.addE('TRAINED_ON').from(ml_model).to(training_dataset)
  .property('training_run_id', run_id)
  .property('epochs', 10)

g.addE('DERIVED_FROM').from(training_dataset).to(source_dataset)
  .property('transform_type', 'filter|augment|sample')

g.addE('POISONING_DETECTED_IN').from(poisoning_alert).to(training_dataset)
```

### DynamoDB Tables

**aura-stream-events-{env}:**
- PK: `repository_id`
- SK: `timestamp#event_id`
- GSI: `processing_status + timestamp`
- Attributes: event_type, affected_files, analysis_results

**aura-materialized-views-{env}:**
- PK: `view_type#source_key`
- SK: `version`
- Attributes: computed_data, computed_at, ttl

**aura-model-access-{env}:**
- PK: `model_id`
- SK: `timestamp#access_id`
- GSI: `accessor_id + timestamp`, `anomaly_score + timestamp`
- Attributes: access_type, bytes_transferred, source_ip

**aura-poisoning-alerts-{env}:**
- PK: `dataset_id`
- SK: `timestamp#alert_id`
- GSI: `alert_type + confidence`
- Attributes: affected_samples, detection_method, status

### OpenSearch Indices

```json
{
  "aura-stream-analysis": {
    "mappings": {
      "properties": {
        "event_id": { "type": "keyword" },
        "repository_id": { "type": "keyword" },
        "commit_sha": { "type": "keyword" },
        "affected_files": { "type": "keyword" },
        "vulnerabilities_found": { "type": "integer" },
        "analysis_latency_ms": { "type": "integer" },
        "timestamp": { "type": "date" }
      }
    }
  },
  "aura-model-security": {
    "mappings": {
      "properties": {
        "model_id": { "type": "keyword" },
        "event_type": { "type": "keyword" },
        "anomaly_score": { "type": "float" },
        "accessor_id": { "type": "keyword" },
        "description": { "type": "text" },
        "timestamp": { "type": "date" },
        "embedding": {
          "type": "knn_vector",
          "dimension": 1024
        }
      }
    }
  }
}
```

## API Endpoints

### Streaming Analysis APIs

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/stream/webhook/github` | GitHub webhook receiver |
| POST | `/api/v1/stream/webhook/gitlab` | GitLab webhook receiver |
| GET | `/api/v1/stream/events/{id}` | Get event analysis status |
| GET | `/api/v1/stream/events/repository/{id}` | Events for repository |
| GET | `/api/v1/stream/metrics` | Streaming analysis metrics |
| POST | `/api/v1/stream/analyze` | Trigger manual analysis |

### Graph Query APIs

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/graph/query` | Execute Gremlin query |
| GET | `/api/v1/graph/dependencies/{package}` | Get package dependencies |
| GET | `/api/v1/graph/dependents/{package}` | Get package dependents |
| GET | `/api/v1/graph/impact/{vuln_id}` | Vulnerability impact analysis |
| GET | `/api/v1/graph/path` | Find path between nodes |
| GET | `/api/v1/graph/shards` | List shards and health |

### Model Security APIs

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/models/register` | Register model for monitoring |
| GET | `/api/v1/models/{id}/access` | Get access logs for model |
| GET | `/api/v1/models/{id}/anomalies` | Get detected anomalies |
| POST | `/api/v1/models/{id}/fingerprint` | Generate model fingerprint |
| GET | `/api/v1/datasets/{id}/health` | Training data health check |
| GET | `/api/v1/datasets/{id}/poisoning` | Poisoning detection results |
| POST | `/api/v1/inference/protect` | Protect inference endpoint |

## Implementation Plan

### Phase 1: Streaming Analysis Engine (Weeks 1-4)

| Task | Effort | Deliverables |
|------|--------|--------------|
| Event ingestion (webhooks, Kinesis) | 1 week | GitHub/GitLab integration |
| Priority queue and work distribution | 1 week | Analysis orchestrator |
| Incremental analyzers | 1 week | AST diff, dependency delta |
| Graph update service | 0.5 week | Batch writer, cache invalidation |
| CI/CD feedback integration | 0.5 week | GitHub Checks, GitLab comments |

**Estimated LOC:** 6,500 lines Python
**Tests:** 195 tests

### Phase 2: Polyglot Dependency Graph (Weeks 5-8)

| Task | Effort | Deliverables |
|------|--------|--------------|
| Shard router and query optimizer | 1 week | Query distribution |
| Neptune shard deployment automation | 1 week | CloudFormation, provisioning |
| Materialized view system | 1 week | DynamoDB views, refresh |
| Cross-shard query federation | 1 week | Parallel execution, merge |

**Estimated LOC:** 5,200 lines Python
**Tests:** 175 tests

### Phase 3: Model Weight Guardian (Weeks 9-11)

| Task | Effort | Deliverables |
|------|--------|--------------|
| Access monitoring integration | 1 week | S3, SageMaker, MLflow hooks |
| Exfiltration detection | 1 week | Network analysis, patterns |
| Model fingerprinting | 0.5 week | Weight hashing, watermarks |
| Alert and response system | 0.5 week | SNS, auto-revocation |

**Estimated LOC:** 4,100 lines Python
**Tests:** 135 tests

### Phase 4: Training Data Sentinel (Weeks 12-14)

| Task | Effort | Deliverables |
|------|--------|--------------|
| Data pipeline monitoring | 1 week | Ingestion tracking |
| Anomaly detection | 1 week | Statistical analysis |
| Poisoning detectors | 0.5 week | Label flip, backdoor, gradient |
| Provenance tracking | 0.5 week | Chain of custody |

**Estimated LOC:** 3,800 lines Python
**Tests:** 125 tests

## Infrastructure Requirements

### CloudFormation Templates

| Template | Layer | Description |
|----------|-------|-------------|
| `streaming-ingestion.yaml` | 2.11 | Kinesis, API Gateway, Lambda |
| `neptune-sharding.yaml` | 2.12 | Multi-shard Neptune clusters |
| `materialized-views.yaml` | 2.13 | DynamoDB, ElastiCache |
| `model-security-data.yaml` | 2.14 | DynamoDB tables for AI security |
| `streaming-compute.yaml` | 3.9 | EKS workers for analysis |
| `model-guardian.yaml` | 8.9 | Lambda, EventBridge for monitoring |
| `training-sentinel.yaml` | 8.10 | Step Functions, ML analysis |

### Neptune Shard Sizing

| Shard Count | Nodes per Shard | Total Capacity | Use Case |
|-------------|-----------------|----------------|----------|
| 1 | 250M vertices | 250M vertices | Standard |
| 4 | 250M vertices | 1B vertices | Enterprise |
| 8 | 250M vertices | 2B vertices | Hyperscale |
| 16 | 250M vertices | 4B vertices | Maximum |

### Compute Requirements

| Component | Instance Type | Count | Purpose |
|-----------|---------------|-------|---------|
| Streaming Lambda | - | Auto | Light analysis |
| Analysis EKS | c6i.4xlarge | 4-16 | Heavy analysis |
| ML Analysis EKS | p4d.24xlarge | 1-2 | Poisoning detection |
| Redis Cache | r6g.2xlarge | 3 | Query caching |

## Security Considerations

### Model Weight Protection

| Threat | Likelihood | Impact | Mitigation |
|--------|------------|--------|------------|
| Weight download by insider | Medium | Critical | Access monitoring, anomaly detection |
| Network exfiltration | Medium | Critical | Egress monitoring, DLP |
| Model extraction via API | High | High | Query pattern detection |
| Leaked model attribution | Medium | Medium | Fingerprinting, watermarks |

### Training Data Protection

| Threat | Likelihood | Impact | Mitigation |
|--------|------------|--------|------------|
| Backdoor injection | Low | Critical | Trigger pattern detection |
| Label flipping | Medium | High | Statistical anomaly detection |
| Data poisoning | Medium | High | Distribution shift monitoring |
| Supply chain attack | Low | Critical | Data provenance tracking |

### Streaming Analysis Security

| Threat | Likelihood | Impact | Mitigation |
|--------|------------|--------|------------|
| Webhook spoofing | Medium | Medium | Signature verification |
| Analysis DoS | Medium | Medium | Rate limiting, queue management |
| Malicious code execution | Low | High | Sandboxed analysis |

### Compliance Alignment

| Framework | Control | Implementation |
|-----------|---------|----------------|
| CMMC 2.0 | AU-12 | Complete audit logging for model access |
| NIST 800-53 | SI-7 | Training data integrity verification |
| SOC 2 | CC7.2 | Anomaly detection and alerting |
| NIST AI RMF | MAP-1 | Model provenance and lineage |

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Streaming analysis latency P95 | <2s per commit | CloudWatch metrics |
| Graph query latency P95 | <10ms | Neptune metrics |
| Model access detection latency | <1 minute | End-to-end timing |
| Poisoning detection accuracy | >90% | Validation testing |
| False positive rate (exfiltration) | <5% | Alert review |
| Graph query throughput | 100K QPS | Load testing |
| Streaming throughput | 10K events/sec | Kinesis metrics |

## Alternatives Considered

### Alternative 1: Use Existing Graph Database at Scale

Scale single Neptune cluster instead of sharding.

**Pros:**
- Simpler architecture
- No cross-shard queries

**Cons:**
- Neptune has practical limits (~100M vertices performant)
- Single point of failure
- Cannot scale writes

**Decision:** Rejected - billion-node scale requires sharding

### Alternative 2: Use External Model Security Tool

Integrate with existing ML security tools (Robust Intelligence, Adversa AI).

**Pros:**
- Proven technology
- Faster implementation

**Cons:**
- No integration with Aura code graph
- Cannot correlate model issues to code
- Additional vendor dependency

**Decision:** Rejected - code-to-model correlation is key differentiator

### Alternative 3: Batch-Only Analysis

Keep batch analysis instead of streaming.

**Pros:**
- Simpler implementation
- More thorough analysis

**Cons:**
- Slower developer feedback loop
- Delays in vulnerability detection
- Does not match sub-second feedback offered by streaming analysis tools as of publication

**Decision:** Rejected - sub-second feedback is table stakes

## Consequences

### Positive

1. **Hyperscale Support** - Analyze billion-node codebases
2. **Developer Experience** - Sub-second CI/CD feedback
3. **AI Security Leadership** - Early entrant in model protection (as of publication)
4. **Market Differentiation** - Runtime-to-code capability we are not aware of being publicly documented by other vendors as of publication
5. **Revenue Growth** - Access to AI lab and hyperscaler markets
6. **Compliance Ready** - Audit logging for regulated industries

### Negative

1. **Operational Complexity** - Multi-shard graph management
2. **Cost** - Significant infrastructure investment
3. **Expertise** - ML security requires specialized knowledge
4. **Latency Trade-offs** - Some queries slower with sharding
5. **Development Time** - 14 weeks of focused development

### Migration Path

1. **Existing Customers** - Automatic streaming analysis enablement
2. **Large Codebases** - Gradual shard migration with zero downtime
3. **AI Features** - Opt-in model security for interested customers

## Cost Estimate

### Monthly Infrastructure Cost

| Component | Unit Cost | Quantity | Monthly Cost |
|-----------|-----------|----------|--------------|
| Neptune (db.r6g.4xlarge) | $1.80/hr | 4 shards x 3 | $15,552 |
| Neptune Read Replicas | $1.80/hr | 8 replicas | $10,368 |
| Kinesis Data Streams | $0.015/shard-hr | 8 shards | $88 |
| Lambda (streaming) | $0.20/1M | 200M | $40 |
| EKS (analysis) | $0.20/hr | 8 workers | $1,168 |
| ElastiCache Redis | $0.25/hr | 3 nodes | $547 |
| DynamoDB | $1.25/M writes | 500M | $625 |
| GPU (ML analysis) | $32.77/hr | 100 hrs | $3,277 |
| **Total** | | | **~$31,665/month** |

### Development Cost

| Phase | Weeks | Engineers | Total Cost |
|-------|-------|-----------|------------|
| Streaming Engine | 4 | 3 | $120,000 |
| Polyglot Graph | 4 | 3 | $120,000 |
| Model Guardian | 3 | 2 | $60,000 |
| Training Sentinel | 3 | 2 | $60,000 |
| **Total** | 14 | | **$360,000** |

## GovCloud Compatibility

| Service | GovCloud Available | Notes |
|---------|-------------------|-------|
| Neptune | Yes | Full feature parity |
| Kinesis Data Streams | Yes | Full feature parity |
| Lambda | Yes | All runtimes |
| EKS | Yes | GPU instances available |
| DynamoDB | Yes | Full feature parity |
| ElastiCache Redis | Yes | Full feature parity |
| SageMaker | Yes | Model registry supported |

**GovCloud-Specific Considerations:**
- All shards deployed in GovCloud for government customers
- Model weights stored in GovCloud S3 with KMS encryption
- Training data must not leave GovCloud boundary
- FIPS 140-2 validated crypto for model fingerprinting

---

*Competitive references in this ADR reflect publicly available information as of the document date. Vendor products evolve; readers should verify current capabilities before decision-making. Third-party vendor names and products referenced herein are trademarks of their respective owners. References are nominative and do not imply endorsement or partnership.*

## References

- [Neptune Performance Tuning](https://docs.aws.amazon.com/neptune/latest/userguide/best-practices-performance.html)
- [Kinesis Data Streams Scaling](https://docs.aws.amazon.com/streams/latest/dev/kinesis-record-processor-scaling.html)
- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)
- [Robust Machine Learning](https://www.robust-ml.org/)
- [Data Poisoning Attacks](https://arxiv.org/abs/2006.12557)
- [Model Extraction Attacks](https://arxiv.org/abs/2108.13873)
- [ADR-065: Semantic Guardrails Engine](/docs/architecture-decisions/ADR-065-semantic-guardrails-engine.md)
- [ADR-067: Context Provenance and Integrity](/docs/architecture-decisions/ADR-067-context-provenance-integrity.md)
- [ADR-076: SBOM Attestation and Supply Chain Security](/docs/architecture-decisions/ADR-076-sbom-attestation-supply-chain.md)
