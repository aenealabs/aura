# Enterprise Tier Configuration Guide

**Document ID:** HMA-003
**Date:** December 6, 2025
**Audience:** Platform Administrators, Enterprise Customers

---

## Overview

Project Aura supports three enterprise tiers, each configurable to meet specific business requirements. Customers can scale resources independently based on their workload characteristics.

```
┌─────────────────────────────────────────────────────────────────┐
│                    ENTERPRISE TIER OVERVIEW                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  SMALL ENTERPRISE          MEDIUM ENTERPRISE      LARGE ENTERPRISE│
│  ─────────────────          ─────────────────      ────────────────│
│                                                                  │
│  Startups, SMBs            Mid-market, Growth     Fortune 500    │
│  < 50 developers           50-500 developers      500+ developers│
│  < 10 repos                10-100 repos           100+ repos     │
│                                                                  │
│  ┌───────────┐             ┌───────────┐         ┌───────────┐  │
│  │   $5K/mo  │             │  $15K/mo  │         │  $40K/mo  │  │
│  │           │             │           │         │           │  │
│  │  Single   │             │  Multi-AZ │         │ Multi-Reg │  │
│  │  Region   │             │  HA       │         │ HA + DR   │  │
│  └───────────┘             └───────────┘         └───────────┘  │
│                                                                  │
│  All tiers include:                                              │
│  • Same codebase                                                 │
│  • Same security controls                                        │
│  • Same compliance (CMMC, SOX, NIST)                            │
│  • Self-service scaling                                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Tier Comparison

### 1.1 Capacity & Performance

| Capability | Small | Medium | Large |
|------------|-------|--------|-------|
| **Agent Orchestrations** | | | |
| Concurrent | 25 | 100 | 500+ |
| Daily | 1,000 | 10,000 | 100,000+ |
| **Memory Operations** | | | |
| Retrievals/sec | 500 | 5,000 | 50,000+ |
| TTT updates/min | 10 | 100 | 1,000+ |
| **Code Analysis** | | | |
| Repos monitored | 10 | 100 | Unlimited |
| Lines of code | 1M | 10M | 100M+ |
| **Response Time** | | | |
| Retrieval p99 | < 20ms | < 10ms | < 5ms |
| Orchestration p99 | < 5s | < 3s | < 2s |

### 1.2 Infrastructure

| Component | Small | Medium | Large |
|-----------|-------|--------|-------|
| **Memory Service** | | | |
| Retrieval instances | 1× inf2.xlarge | 2× inf2.xlarge | 4× inf2.8xlarge |
| TTT instances | 0-1× g5.xlarge | 0-2× g5.xlarge | 0-3× g5.2xlarge |
| **Compute (EKS)** | | | |
| Node type | m6i.large | m6i.xlarge | m6i.2xlarge |
| Node count | 3 | 5 | 10-20 |
| **Data Layer** | | | |
| Neptune | db.r5.large | db.r5.xlarge | db.r5.2xlarge + 3 replicas |
| OpenSearch | 2× m6g.large | 3× m6g.xlarge | 5× m6g.2xlarge |
| DynamoDB | On-Demand | Provisioned 500 RCU | Provisioned 2000 RCU |
| **High Availability** | | | |
| Multi-AZ | No | Yes | Yes |
| Multi-Region | No | No | Yes (optional) |
| DR Recovery | 24h RPO | 4h RPO | 1h RPO |

### 1.3 Pricing (Estimated)

| Cost Component | Small | Medium | Large |
|----------------|-------|--------|-------|
| Memory Service | $1,500 | $3,500 | $8,000 |
| Compute (EKS) | $300 | $700 | $2,500 |
| Data Layer | $1,000 | $2,500 | $6,000 |
| LLM (Bedrock) | $2,000 | $8,000 | $25,000 |
| Networking | $100 | $300 | $800 |
| Monitoring | $100 | $200 | $400 |
| **Total/Month** | **~$5,000** | **~$15,200** | **~$42,700** |

---

## 2. Configuration Files

### 2.1 Small Enterprise

```yaml
# deploy/config/tiers/small-enterprise.yaml
tier: small-enterprise
description: "Startups and SMBs with < 50 developers"

capacity:
  max_concurrent_orchestrations: 25
  max_daily_orchestrations: 1000
  max_repos: 10
  max_loc: 1000000

sla:
  retrieval_p99_ms: 20
  orchestration_p99_sec: 5
  availability: 99.5

memory_service:
  retrieval:
    instance_type: inf2.xlarge
    count: 1
    autoscaling:
      enabled: false
  ttt:
    instance_type: g5.xlarge
    min_count: 0
    max_count: 1
    scale_to_zero: true

compute:
  eks:
    node_type: m6i.large
    min_nodes: 2
    max_nodes: 4
    spot_enabled: true
    spot_percentage: 50

data:
  neptune:
    instance_type: db.r5.large
    read_replicas: 0
    backup_retention_days: 7
  opensearch:
    instance_type: m6g.large.search
    data_nodes: 2
    master_nodes: 0  # Small clusters don't need dedicated masters
  dynamodb:
    capacity_mode: on-demand

llm:
  bedrock:
    rate_limit_rpm: 500
    daily_token_limit: 5000000
    monthly_budget_usd: 2500
    model_distribution:
      fast: 0.50
      accurate: 0.45
      maximum: 0.05

high_availability:
  multi_az: false
  multi_region: false
  rpo_hours: 24
  rto_hours: 8

features:
  hitl_enabled: true
  sandbox_testing: true
  design_doc_review: true
  penetration_testing: false  # Upgrade to Medium for this
  multi_tenant: false
```

### 2.2 Medium Enterprise

```yaml
# deploy/config/tiers/medium-enterprise.yaml
tier: medium-enterprise
description: "Mid-market companies with 50-500 developers"

capacity:
  max_concurrent_orchestrations: 100
  max_daily_orchestrations: 10000
  max_repos: 100
  max_loc: 10000000

sla:
  retrieval_p99_ms: 10
  orchestration_p99_sec: 3
  availability: 99.9

memory_service:
  retrieval:
    instance_type: inf2.xlarge
    count: 2
    autoscaling:
      enabled: true
      min: 2
      max: 4
      target_utilization: 70
  ttt:
    instance_type: g5.xlarge
    min_count: 0
    max_count: 2
    scale_to_zero: true
    scale_up_threshold_queue_depth: 50

compute:
  eks:
    node_type: m6i.xlarge
    min_nodes: 3
    max_nodes: 8
    spot_enabled: true
    spot_percentage: 30

data:
  neptune:
    instance_type: db.r5.xlarge
    read_replicas: 1
    backup_retention_days: 14
  opensearch:
    instance_type: m6g.xlarge.search
    data_nodes: 3
    master_nodes: 3
  dynamodb:
    capacity_mode: provisioned
    rcu: 500
    wcu: 250
    autoscaling: true

llm:
  bedrock:
    rate_limit_rpm: 2000
    daily_token_limit: 30000000
    monthly_budget_usd: 10000
    model_distribution:
      fast: 0.40
      accurate: 0.55
      maximum: 0.05

high_availability:
  multi_az: true
  multi_region: false
  rpo_hours: 4
  rto_hours: 2

features:
  hitl_enabled: true
  sandbox_testing: true
  design_doc_review: true
  penetration_testing: true
  multi_tenant: true
  max_tenants: 5
  sso_integration: true
```

### 2.3 Large Enterprise

```yaml
# deploy/config/tiers/large-enterprise.yaml
tier: large-enterprise
description: "Fortune 500 with 500+ developers"

capacity:
  max_concurrent_orchestrations: 500
  max_daily_orchestrations: 100000
  max_repos: unlimited
  max_loc: unlimited

sla:
  retrieval_p99_ms: 5
  orchestration_p99_sec: 2
  availability: 99.99

memory_service:
  retrieval:
    instance_type: inf2.8xlarge
    count: 4
    autoscaling:
      enabled: true
      min: 4
      max: 10
      target_utilization: 60
  ttt:
    instance_type: g5.2xlarge
    min_count: 1
    max_count: 5
    scale_to_zero: false  # Always-on for low latency
    scale_up_threshold_queue_depth: 100

compute:
  eks:
    node_type: m6i.2xlarge
    min_nodes: 10
    max_nodes: 50
    spot_enabled: false  # On-demand for predictability
    priority_class: high

data:
  neptune:
    instance_type: db.r5.2xlarge
    read_replicas: 3
    backup_retention_days: 35
    point_in_time_recovery: true
  opensearch:
    instance_type: m6g.2xlarge.search
    data_nodes: 5
    master_nodes: 3
    zone_awareness: true
  dynamodb:
    capacity_mode: provisioned
    rcu: 2000
    wcu: 1000
    autoscaling: true
    global_tables: true  # Multi-region

llm:
  bedrock:
    rate_limit_rpm: 10000
    daily_token_limit: 200000000
    monthly_budget_usd: 30000
    model_distribution:
      fast: 0.40
      accurate: 0.55
      maximum: 0.05
    provisioned_throughput:
      enabled: true
      model_units: 5

high_availability:
  multi_az: true
  multi_region: true
  primary_region: us-east-1
  secondary_region: us-west-2
  rpo_hours: 1
  rto_hours: 0.5
  active_active: false  # Active-passive for cost

features:
  hitl_enabled: true
  sandbox_testing: true
  design_doc_review: true
  penetration_testing: true
  multi_tenant: true
  max_tenants: 50
  sso_integration: true
  dedicated_support: true
  custom_sla: true
  govcloud_compatible: true
  cmmc_level3: true
```

---

## 3. Customization Options

### 3.1 Memory Configuration

Customers can tune neural memory behavior independent of tier:

```yaml
# Custom memory configuration
memory:
  model:
    dimensions: 512        # 256, 512, 1024
    depth: 3               # 2, 3, 4, 5
    hidden_multiplier: 4   # 2, 4, 8

  miras:
    attentional_bias: huber      # l2, l1, huber, cosine
    retention_gate: adaptive     # weight_decay, exponential, adaptive
    retention_strength: 0.01     # 0.001 - 0.1

  surprise:
    memorization_threshold: 0.7  # 0.5 - 0.9 (higher = more selective)
    momentum: 0.9                # 0.8 - 0.95

  checkpointing:
    interval_hours: 1            # 1, 6, 12, 24
    retention_days: 30           # 7, 14, 30, 90
    s3_storage_class: STANDARD   # STANDARD, INTELLIGENT_TIERING, GLACIER
```

### 3.2 Autonomy Policy

Customers can configure HITL behavior:

```yaml
# Autonomy configuration
autonomy:
  level: critical_hitl           # full_hitl, critical_hitl, audit_only, full_autonomous

  thresholds:
    confidence_autonomous: 0.85  # Auto-approve above this
    confidence_review: 0.70      # Request review above this
    confidence_escalate: 0.50    # Escalate below this

  guardrails:
    - production_deployment      # Always require HITL
    - credential_modification
    - database_migration
    - infrastructure_change

  presets:
    # Available presets
    - defense_contractor         # Full HITL (highest security)
    - financial_services         # Full HITL
    - enterprise_standard        # Critical HITL
    - fintech_startup           # Critical HITL
    - internal_tools            # Audit only
```

### 3.3 Integration Mode

Per ADR-023, customers choose integration mode:

```yaml
# Integration mode configuration
integration:
  mode: defense                  # defense, enterprise, hybrid

  # Defense mode (GovCloud, air-gap compatible)
  defense:
    external_tools: false
    mcp_gateway: false
    all_data_internal: true

  # Enterprise mode (full external integrations)
  enterprise:
    external_tools:
      - slack
      - jira
      - pagerduty
      - github
      - datadog
    mcp_gateway: true
    budget_per_million_invocations: 5.00

  # Hybrid mode (selective)
  hybrid:
    external_tools:
      - github                   # Code integration only
    mcp_gateway: false
    audit_external_calls: true
```

---

## 4. Scaling Operations

### 4.1 Upgrade Tier

```bash
# Upgrade from Small to Medium
aura-cli tier upgrade \
  --from small-enterprise \
  --to medium-enterprise \
  --schedule "2025-01-15T02:00:00Z" \
  --notify admin@company.com

# Changes applied:
# - Memory: 1× inf2.xlarge → 2× inf2.xlarge
# - Neptune: db.r5.large → db.r5.xlarge + 1 replica
# - OpenSearch: 2 nodes → 3 nodes
# - Multi-AZ: enabled
# - Features: penetration testing, multi-tenant unlocked
```

### 4.2 Downgrade Tier

```bash
# Downgrade from Medium to Small (cost optimization)
aura-cli tier downgrade \
  --from medium-enterprise \
  --to small-enterprise \
  --confirm-data-migration \
  --schedule "2025-02-01T02:00:00Z"

# Warnings:
# - Multi-AZ will be disabled
# - Read replica will be removed
# - Max repos reduced from 100 to 10
# - Penetration testing will be disabled
```

### 4.3 Component-Level Scaling

```bash
# Scale individual components without tier change
aura-cli scale memory-retrieval \
  --instance-type inf2.8xlarge \
  --count 3

aura-cli scale compute \
  --node-type m6i.2xlarge \
  --min-nodes 8

aura-cli scale neptune \
  --read-replicas 2
```

---

## 5. Monitoring & Alerts

### 5.1 Tier-Specific Dashboards

Each tier includes CloudWatch dashboards:

| Dashboard | Small | Medium | Large |
|-----------|-------|--------|-------|
| Retrieval Latency | ✅ | ✅ | ✅ |
| TTT Queue Depth | ✅ | ✅ | ✅ |
| Agent Orchestrations | ✅ | ✅ | ✅ |
| Cost Tracking | ✅ | ✅ | ✅ |
| Multi-AZ Health | ❌ | ✅ | ✅ |
| Cross-Region Replication | ❌ | ❌ | ✅ |
| Tenant Breakdown | ❌ | ✅ | ✅ |

### 5.2 Automatic Alerts

```yaml
# Tier-specific alert thresholds
alerts:
  small:
    retrieval_p99_threshold_ms: 25
    error_rate_threshold: 0.02
    budget_alert_percentage: 80

  medium:
    retrieval_p99_threshold_ms: 15
    error_rate_threshold: 0.01
    budget_alert_percentage: 75
    rpo_violation_alert: true

  large:
    retrieval_p99_threshold_ms: 8
    error_rate_threshold: 0.005
    budget_alert_percentage: 70
    rpo_violation_alert: true
    cross_region_lag_threshold_sec: 60
```

---

## 6. Compliance by Tier

| Compliance | Small | Medium | Large |
|------------|-------|--------|-------|
| SOC 2 Type II | ✅ | ✅ | ✅ |
| ISO 27001 | ✅ | ✅ | ✅ |
| GDPR | ✅ | ✅ | ✅ |
| HIPAA | ❌ | ✅ | ✅ |
| SOX | ❌ | ✅ | ✅ |
| CMMC Level 2 | ❌ | ✅ | ✅ |
| CMMC Level 3 | ❌ | ❌ | ✅ |
| FedRAMP Moderate | ❌ | ❌ | ✅ |
| FedRAMP High | ❌ | ❌ | ✅ (GovCloud) |

---

## 7. Getting Started

### 7.1 New Customer Onboarding

```bash
# 1. Initialize Aura for your organization
aura-cli init \
  --org-name "Acme Corp" \
  --tier medium-enterprise \
  --region us-east-1

# 2. Configure integrations
aura-cli configure integrations \
  --mode enterprise \
  --github-app-id 12345 \
  --slack-webhook https://hooks.slack.com/...

# 3. Configure autonomy policy
aura-cli configure autonomy \
  --preset enterprise_standard

# 4. Deploy
aura-cli deploy \
  --environment production \
  --confirm
```

### 7.2 Existing Customer Migration

```bash
# 1. Export current configuration
aura-cli config export > current-config.yaml

# 2. Review tier recommendations
aura-cli tier recommend --based-on-usage

# 3. Apply new tier
aura-cli tier set medium-enterprise --config current-config.yaml
```

---

## Summary

| Decision Point | Small | Medium | Large |
|----------------|-------|--------|-------|
| Best for | Startups, POC | Growth, Mid-market | Fortune 500 |
| Developers | < 50 | 50-500 | 500+ |
| Monthly Cost | ~$5K | ~$15K | ~$40K+ |
| Availability SLA | 99.5% | 99.9% | 99.99% |
| Support | Standard | Priority | Dedicated |

**Recommendation:** Start with the tier that matches current needs. Aura's configuration-driven architecture allows seamless upgrades as requirements grow.

---

*Document Version: 1.0*
*Last Updated: December 6, 2025*
