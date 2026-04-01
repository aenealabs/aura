# IR-002: GraphRAG Context Poisoning Incident Response Playbook

**Version:** 1.0
**Last Updated:** January 25, 2026
**Owner:** Security Team
**Classification:** Public

---

## 1. Overview

### 1.1 Purpose
This playbook provides procedures for detecting, containing, and remediating context poisoning attacks against Project Aura's GraphRAG knowledge graph system.

### 1.2 Scope
Applies to incidents affecting:
- Neptune graph database (code relationships, dependencies)
- OpenSearch vector store (semantic embeddings)
- Context Retrieval Service
- HopRAG traversal engine

### 1.3 MITRE ATT&CK Mapping
| Technique | ID | Description |
|-----------|-----|-------------|
| Data Manipulation | T1565 | Stored data manipulation |
| Supply Chain Compromise | T1195 | Compromise of code repositories |
| Trusted Relationship | T1199 | Abuse of repository trust |

---

## 2. Severity Classification

| Severity | Criteria | Response Time |
|----------|----------|---------------|
| **Critical** | Production patches generated from poisoned context | Immediate (< 15 min) |
| **High** | Poisoned data detected in production graph | < 1 hour |
| **Medium** | Suspicious ingestion patterns detected | < 4 hours |
| **Low** | Failed poisoning attempt blocked | < 24 hours |

---

## 3. Detection

### 3.1 Detection Sources

| Source | Alert Type | SNS Topic |
|--------|------------|-----------|
| Graph Integrity Auditor | Anomalous entity patterns | `aura-security-alerts-{env}` |
| SecurityAuditService | `GRAPHRAG_CONTEXT_MANIPULATION` | `aura-security-alerts-{env}` |
| Ingestion Pipeline | Malicious code patterns | `aura-critical-anomalies-{env}` |
| Neptune Audit Logs | Unauthorized write operations | CloudWatch |

### 3.2 Indicators of Compromise (IOCs)

**Graph Anomalies:**
- Unusual spike in entity creation rate
- Entities with suspicious provenance (unknown repositories)
- Code snippets containing obfuscated payloads
- Circular dependencies injected artificially
- Backdoor patterns in function definitions

**Behavioral Indicators:**
- Agent generating patches with unexpected dependencies
- Retrieval results containing code not in indexed repos
- Embedding similarity scores dramatically different from baseline
- Unauthorized repository connections

### 3.3 Log Queries

**Neptune Audit - Suspicious Writes:**
```
fields @timestamp, @message
| filter @message like /mutate|addVertex|addEdge/
| filter @message not like /expected-service-role/
| sort @timestamp desc
| limit 100
```

**Context Retrieval Anomalies:**
```
fields @timestamp, repository_id, entity_count, confidence_score
| filter confidence_score < 0.3 or entity_count > 1000
| stats count() by repository_id
```

---

## 4. Containment

### 4.1 Immediate Actions (First 15 Minutes)

| Step | Action | Owner |
|------|--------|-------|
| 1 | Pause ingestion pipeline | On-Call Engineer |
| 2 | Identify affected repositories | On-Call Engineer |
| 3 | Quarantine suspicious entities | On-Call Engineer |
| 4 | Block context retrieval for affected repos | On-Call Engineer |
| 5 | Preserve Neptune snapshots | On-Call Engineer |

### 4.2 Pause Ingestion Pipeline

**Stop Step Functions Execution:**
```bash
aws stepfunctions stop-execution \
  --execution-arn ${EXECUTION_ARN} \
  --cause "Security incident - context poisoning"
```

**Disable EventBridge Rule:**
```bash
aws events disable-rule \
  --name aura-repo-ingestion-trigger-${ENV}
```

### 4.3 Quarantine Entities

**Mark Entities as Quarantined in Neptune:**
```gremlin
g.V().has('repository_id', '${REPO_ID}')
  .property('quarantined', true)
  .property('quarantine_reason', 'IR-002 investigation')
  .property('quarantine_date', datetime())
```

**Block Retrieval for Repository:**
```bash
aws ssm put-parameter \
  --name "/aura/${ENV}/blocked-repositories" \
  --value "${REPO_ID}" \
  --type StringList \
  --overwrite
```

### 4.4 Evidence Preservation

**Create Neptune Snapshot:**
```bash
aws neptune create-db-cluster-snapshot \
  --db-cluster-identifier aura-neptune-${ENV} \
  --db-cluster-snapshot-identifier "ir002-$(date +%Y%m%d-%H%M%S)"
```

**Export OpenSearch Index:**
```bash
# Use snapshot API to preserve vector store state
curl -X PUT "https://${OPENSEARCH_ENDPOINT}/_snapshot/ir-backup/ir002-snapshot" \
  -H "Content-Type: application/json" \
  --aws-sigv4 "aws:amz:us-east-1:es"
```

---

## 5. Eradication

### 5.1 Root Cause Analysis

| Question | Investigation Method |
|----------|---------------------|
| How was malicious data ingested? | Review ingestion logs, repository connections |
| What was the attack vector? | Analyze poisoned entities |
| Which repositories are affected? | Query graph for provenance |
| What patches were generated with poisoned context? | Review agent outputs |
| Are other tenants affected? | Multi-tenant isolation check |

### 5.2 Remove Poisoned Data

**Delete Quarantined Entities:**
```gremlin
g.V().has('quarantined', true)
  .has('quarantine_reason', 'IR-002 investigation')
  .drop()
```

**Reindex Clean Data:**
```bash
# Trigger re-ingestion for affected repository
aws stepfunctions start-execution \
  --state-machine-arn ${INGESTION_STATE_MACHINE} \
  --input '{"repository_id": "${REPO_ID}", "full_reindex": true}'
```

### 5.3 Strengthen Defenses

**Add Content Validation Rules:**
- Implement code snippet sanitization before indexing
- Add entropy checks for obfuscation detection
- Enable provenance verification for all entities

---

## 6. Recovery

### 6.1 Service Restoration

| Step | Action | Verification |
|------|--------|--------------|
| 1 | Re-enable ingestion pipeline | Health check passes |
| 2 | Unquarantine verified entities | Manual review |
| 3 | Resume context retrieval | Test queries succeed |
| 4 | Monitor for recurrence | Dashboard alerts clear |

### 6.2 Patch Review

If patches were generated using poisoned context:
- [ ] Identify all affected patches
- [ ] Revoke/reject pending HITL approvals
- [ ] Notify customers of potentially compromised patches
- [ ] Re-generate patches with clean context

---

## 7. Escalation Matrix

| Severity | Primary | Secondary | Executive |
|----------|---------|-----------|-----------|
| Critical | On-Call Engineer | Security Lead + Data Team | CTO (within 1 hour) |
| High | On-Call Engineer | Security Lead | CTO (within 4 hours) |
| Medium | On-Call Engineer | Security Lead | Weekly report |
| Low | On-Call Engineer | - | Monthly report |

---

## 8. Post-Incident Activities

### 8.1 Incident Report
Complete within 72 hours:
- [ ] Timeline of events
- [ ] Affected repositories and entities
- [ ] Patches generated with poisoned context
- [ ] Customer impact assessment
- [ ] Remediation actions taken

### 8.2 Metrics
| Metric | Target |
|--------|--------|
| Time to Detection (TTD) | < 1 hour |
| Time to Containment (TTC) | < 30 minutes |
| Time to Eradication (TTE) | < 8 hours |
| Time to Recovery (TTR) | < 24 hours |

---

## Appendix A: Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│        GRAPHRAG CONTEXT POISONING - QUICK REFERENCE         │
├─────────────────────────────────────────────────────────────┤
│ 1. PAUSE     - Stop ingestion pipeline immediately          │
│ 2. IDENTIFY  - Find affected repositories/entities          │
│ 3. QUARANTINE- Mark suspicious entities, block retrieval    │
│ 4. SNAPSHOT  - Preserve Neptune + OpenSearch state          │
│ 5. ANALYZE   - Determine attack vector and scope            │
│ 6. PURGE     - Remove poisoned entities from graph          │
│ 7. REINDEX   - Re-ingest clean data                         │
│ 8. RESTORE   - Re-enable services with monitoring           │
├─────────────────────────────────────────────────────────────┤
│ CRITICAL: Review ALL patches generated during incident      │
│ SNS Topic: aura-security-alerts-{env}                       │
└─────────────────────────────────────────────────────────────┘
```
