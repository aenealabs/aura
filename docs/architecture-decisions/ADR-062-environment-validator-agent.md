# ADR-062: Environment Validator Agent

## Status

Deployed (DEV/QA)

## Date

2026-01-14

## Reviews

| Reviewer | Role | Date | Verdict |
|----------|------|------|---------|
| Architecture Review | AWS AI SaaS Architect | 2026-01-14 | Approve with modifications |
| Design Review | UI/UX Designer | 2026-01-14 | Approve |

### Review Summary

**Key Modifications (Required before implementation):**

- P1: Move environment registry to SSM Parameter Store (security)
- P1: Add explicit IRSA policy with resource scoping
- P1: Use single-table DynamoDB design to prevent hot partitions
- P2: Add rules ENV-006 (region), ENV-007 (KMS), ENV-008 (IAM roles)
- P2: Add Kubernetes ValidatingAdmissionWebhook in Phase 2
- P2: Define explicit auto-remediation safe/unsafe matrix

**UI Design:** Complete dashboard specification with validation timeline, violation heatmap, drift status panel, agent activity feed, and remediation history. 8-week Phase 3 implementation roadmap provided.

## Context

During GPU Scheduler Phase 2 deployment, several environment misconfiguration issues were discovered that could have been caught by automated validation:

1. **QA ConfigMap with DEV values:** The QA Kubernetes cluster had a ConfigMap pointing to DEV DynamoDB tables, Neptune endpoints, and SNS topics
2. **Cross-account ECR references:** QA deployment was pulling container images from DEV ECR instead of QA ECR
3. **Environment variable mismatches:** `ENVIRONMENT=dev` was set in QA pods

These issues caused AccessDeniedException errors and data isolation violations. Manual discovery and remediation consumed significant engineering time and could have caused data leakage between environments in a production scenario.

### Root Causes

| Issue | Root Cause | Impact |
|-------|------------|--------|
| ConfigMap mismatch | Kustomize overlay not applied correctly | API accessed wrong account resources |
| ECR cross-reference | kubectl set image with wrong registry | Container from untested environment deployed |
| Environment variable | ConfigMap not updated during deployment | Wrong DynamoDB tables queried |

### Existing Validation Gaps

| Stage | Current Validation | Missing Validation |
|-------|-------------------|-------------------|
| Pre-deploy | cfn-lint, pre-commit hooks | Environment consistency checks |
| Deploy | CloudFormation stack validation | Cross-resource environment alignment |
| Post-deploy | Health checks (basic) | Environment-specific resource verification |
| Runtime | None | Continuous drift detection |

## Decision

Implement an **Environment Validator Agent** that autonomously validates environment consistency across deployments, detecting misconfigurations before they cause failures or security issues.

### Core Capabilities

1. **Pre-Deployment Validation:** Analyze kustomize overlays, ConfigMaps, and deployment manifests before apply
2. **Post-Deployment Verification:** Verify deployed resources reference correct environment-specific endpoints
3. **Continuous Drift Detection:** Scheduled scans to detect configuration drift between environments
4. **Cross-Account Boundary Enforcement:** Ensure no DEV/QA/PROD cross-contamination

## Architecture

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                     Environment Validator Agent                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐   │
│  │  Config Scanner  │  │  Resource        │  │  Drift Detector      │   │
│  │                  │  │  Validator       │  │                      │   │
│  │  - ConfigMaps    │  │  - ARN parsing   │  │  - Scheduled scans   │   │
│  │  - Secrets refs  │  │  - Account ID    │  │  - Baseline compare  │   │
│  │  - Env vars      │  │  - Region check  │  │  - Alert on drift    │   │
│  │  - Image refs    │  │  - Naming check  │  │                      │   │
│  └────────┬─────────┘  └────────┬─────────┘  └──────────┬───────────┘   │
│           │                     │                        │              │
│           └─────────────────────┼────────────────────────┘              │
│                                 ▼                                       │
│                    ┌────────────────────────┐                           │
│                    │   Validation Engine    │                           │
│                    │   - Rule evaluation    │                           │
│                    │   - Severity scoring   │                           │
│                    │   - Fix suggestions    │                           │
│                    └───────────┬────────────┘                           │
│                                │                                        │
│           ┌────────────────────┼────────────────────┐                   │
│           ▼                    ▼                    ▼                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐          │
│  │  Block Deploy   │  │  Alert/Warn     │  │  Auto-Remediate │          │
│  │  (CI/CD gate)   │  │  (Notification) │  │  (Safe fixes)   │          │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Validation Rules

#### Critical (Block Deployment)

| Rule ID | Description | Example Violation |
|---------|-------------|-------------------|
| ENV-001 | Account ID in ARNs must match target environment | QA ARN contains DEV account ID (123456789012) |
| ENV-002 | ECR image registry must match target account | QA deployment pulls from DEV ECR |
| ENV-003 | DynamoDB table names must contain correct env suffix | `aura-*-dev` table referenced in QA |
| ENV-004 | Neptune/OpenSearch endpoints must match environment | DEV endpoint in QA ConfigMap |
| ENV-005 | SNS/SQS ARNs must reference correct account | Cross-account message publishing |
| ENV-006 | Region in ARNs must match target environment | us-east-1 resources in GovCloud prod |
| ENV-007 | KMS key ARNs must be environment-specific | Cross-env key usage |
| ENV-008 | IAM role ARNs must match target account | IRSA role from wrong account |

#### Warning (Alert but Allow)

| Rule ID | Description | Example Violation |
|---------|-------------|-------------------|
| ENV-101 | ENVIRONMENT variable should match deployment target | `ENVIRONMENT=dev` in QA pod |
| ENV-102 | Secret references should use environment-specific paths | `/aura/dev/*` secret in QA |
| ENV-103 | Log group names should contain environment suffix | `/aws/eks/aura-cluster-dev/` in QA |
| ENV-104 | Service account annotations should match account | IRSA role from wrong account |

#### Informational (Log Only)

| Rule ID | Description | Example |
|---------|-------------|---------|
| ENV-201 | Resource naming convention compliance | Missing `aura-` prefix |
| ENV-202 | Tag consistency | Missing environment tag |

### Environment Registry

The agent loads environment-specific values from SSM Parameter Store (not hardcoded) for security:

```python
# config.py - Load from SSM Parameter Store
import boto3
import json
import os

def load_environment_registry() -> dict:
    """Load environment registry from SSM Parameter Store."""
    ssm = boto3.client('ssm')
    env = os.environ.get('ENVIRONMENT', 'dev')

    param = ssm.get_parameter(
        Name=f'/aura/{env}/env-validator/registry',
        WithDecryption=True
    )
    return json.loads(param['Value'])

# SSM parameter structure (stored encrypted with KMS):
# /aura/dev/env-validator/registry = {
#     "dev": {"account_id": "...", "ecr_registry": "...", ...},
#     "qa": {"account_id": "...", "ecr_registry": "...", ...},
#     "prod": {"account_id": "...", "ecr_registry": "...", ...}
# }

# Registry schema per environment:
REGISTRY_SCHEMA = {
    "account_id": str,           # AWS account ID
    "ecr_registry": str,         # ECR registry URL
    "neptune_cluster": str,      # Neptune endpoint pattern
    "opensearch_domain": str,    # OpenSearch domain pattern
    "resource_suffix": str,      # Environment suffix (-dev, -qa, -prod)
    "eks_cluster": str,          # EKS cluster name
    "region": str,               # AWS region (us-east-1 or us-gov-west-1)
}
```

### Integration Points

#### 1. CI/CD Pipeline Integration (Pre-Deploy Gate)

```yaml
# buildspec addition for k8s-deploy
phases:
  pre_build:
    commands:
      # Validate kustomize output before apply
      - kustomize build deploy/kubernetes/aura-api/overlays/${ENVIRONMENT}/ > /tmp/manifest.yaml
      - python -m src.services.env_validator.validate_manifest /tmp/manifest.yaml --env ${ENVIRONMENT} --strict
```

#### 2. Post-Deployment Webhook

Triggered via Argo Rollouts PostSync hook or Kubernetes Job:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: env-validator-postsync
  annotations:
    argocd.argoproj.io/hook: PostSync
spec:
  template:
    spec:
      containers:
        - name: validator
          image: ${ECR_REGISTRY}/aura-env-validator:latest
          args: ["--mode", "post-deploy", "--namespace", "default", "--env", "${ENVIRONMENT}"]
```

#### 3. Scheduled Drift Detection

EventBridge rule triggers Lambda every 6 hours:

```yaml
# CloudFormation resource
EnvironmentDriftRule:
  Type: AWS::Events::Rule
  Properties:
    Name: !Sub '${ProjectName}-env-drift-check-${Environment}'
    ScheduleExpression: 'rate(6 hours)'
    State: ENABLED
    Targets:
      - Id: DriftDetector
        Arn: !GetAtt EnvironmentValidatorLambda.Arn
```

### API Endpoints

```text
POST /api/v1/environment/validate
  - Body: { manifest: "...", target_env: "qa" }
  - Returns: { valid: bool, violations: [], warnings: [] }

GET /api/v1/environment/drift
  - Query: env=qa
  - Returns: { drift_detected: bool, drifted_resources: [], last_scan: datetime }

GET /api/v1/environment/registry
  - Returns: Environment configuration registry

GET /api/v1/environment/validation-history
  - Query: env=qa, limit=100
  - Returns: Recent validation runs with results
```

### Observability

#### CloudWatch Metrics

| Metric | Dimension | Description |
|--------|-----------|-------------|
| ValidationRuns | Environment | Total validation executions |
| ViolationsDetected | Environment, Severity | Count of violations by severity |
| DeploymentsBlocked | Environment | Deployments blocked by critical violations |
| DriftDetected | Environment | Drift detection events |
| RemediationsApplied | Environment | Auto-fixes applied |

#### CloudWatch Alarms

| Alarm | Threshold | Action |
|-------|-----------|--------|
| CriticalViolationDetected | >= 1 | SNS alert to ops team |
| DriftDetected | >= 1 resource | SNS alert, Slack notification |
| ValidationFailureRate | > 10% | Page on-call engineer |

#### Dashboard Widgets (Design Phase)

1. **Validation Timeline:** Time-series of validation runs with pass/fail status
2. **Violation Heatmap:** Matrix of rule violations by environment
3. **Drift Status:** Current drift status per environment with affected resources
4. **Agent Activity Feed:** Real-time feed of agent actions and decisions
5. **Remediation History:** Auto-fix actions taken with before/after state

### Data Model

```python
@dataclass
class ValidationRun:
    run_id: str
    timestamp: datetime
    environment: str
    trigger: Literal["pre_deploy", "post_deploy", "scheduled", "manual"]
    manifest_hash: Optional[str]
    duration_ms: int
    result: Literal["pass", "fail", "warn"]
    violations: list[Violation]
    warnings: list[Warning]

@dataclass
class Violation:
    rule_id: str
    severity: Literal["critical", "warning", "info"]
    resource_type: str
    resource_name: str
    expected_value: str
    actual_value: str
    message: str
    suggested_fix: Optional[str]
    auto_remediable: bool

@dataclass
class DriftReport:
    report_id: str
    timestamp: datetime
    environment: str
    baseline_timestamp: datetime
    drifted_resources: list[DriftedResource]

@dataclass
class DriftedResource:
    resource_type: str
    resource_name: str
    field: str
    baseline_value: str
    current_value: str
    drift_type: Literal["modified", "added", "removed"]
```

### DynamoDB Tables

Single-table design to prevent hot partitions (architecture recommendation):

```yaml
# Validation History Table - Single-table design
aura-env-validation-{env}:
  KeySchema:
    - AttributeName: PK        # "ENV#qa" or "RUNID#uuid"
      KeyType: HASH
    - AttributeName: SK        # "RUN#2026-01-14T10:00:00Z" or "VIOLATION#rule-id"
      KeyType: RANGE
  GlobalSecondaryIndexes:
    - IndexName: GSI1
      KeySchema:
        - AttributeName: GSI1PK  # "DATE#2026-01-14"
          KeyType: HASH
        - AttributeName: GSI1SK  # "ENV#qa#RUN#timestamp"
          KeyType: RANGE
  BillingMode: PAY_PER_REQUEST

# Access patterns enabled:
# 1. All runs for an environment: PK="ENV#qa", SK begins_with "RUN#"
# 2. All violations for a run: PK="RUNID#uuid", SK begins_with "VIOLATION#"
# 3. Runs by date (dashboards): GSI1PK="DATE#2026-01-14"

# Drift Baseline Table
aura-env-baseline-{env}:
  KeySchema:
    - AttributeName: resource_key  # "configmap/aura-api-config"
      KeyType: HASH
    - AttributeName: environment
      KeyType: RANGE
  TimeToLiveSpecification:
    AttributeName: baseline_expires_at  # Auto-expire old baselines
    Enabled: true
  BillingMode: PAY_PER_REQUEST
```

## Implementation Phases

### Phase 1: Core Validation Engine (MVP)

**Deliverables:**

- `src/services/env_validator/` module with validation logic
- Environment registry configuration
- CLI tool for local validation
- Pre-deploy CI/CD integration

**Files:**

```
src/services/env_validator/
├── __init__.py
├── config.py              # Environment registry
├── validators/
│   ├── __init__.py
│   ├── configmap.py       # ConfigMap validation
│   ├── deployment.py      # Deployment/image validation
│   ├── arn.py             # ARN account/region validation
│   └── naming.py          # Naming convention validation
├── engine.py              # Validation orchestration
├── models.py              # Data models
└── cli.py                 # Command-line interface
```

### Phase 2: Post-Deploy & Drift Detection

**Deliverables:**

- Kubernetes post-sync validation job
- Kubernetes ValidatingAdmissionWebhook (defense-in-depth)
- Lambda for scheduled drift detection
- DynamoDB tables for history/baseline
- CloudWatch metrics and alarms

**ValidatingAdmissionWebhook (architecture recommendation):**

```yaml
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingWebhookConfiguration
metadata:
  name: env-validator-webhook
webhooks:
  - name: validate.env.aura.io
    rules:
      - apiGroups: [""]
        apiVersions: ["v1"]
        operations: ["CREATE", "UPDATE"]
        resources: ["configmaps", "secrets"]
      - apiGroups: ["apps"]
        apiVersions: ["v1"]
        operations: ["CREATE", "UPDATE"]
        resources: ["deployments"]
    failurePolicy: Fail  # Block deployment on webhook error
```

**Files:**

```
src/services/env_validator/
├── drift_detector.py      # Drift detection logic
├── baseline_manager.py    # Baseline capture/compare
├── lambda_handler.py      # Lambda entry point
└── webhook_handler.py     # Admission webhook server

deploy/cloudformation/
└── env-validator-infrastructure.yaml

deploy/kubernetes/env-validator/
├── webhook-deployment.yaml
└── webhook-config.yaml
```

### Phase 3: API & Observability UI

**Deliverables:**

- REST API endpoints
- Dashboard widgets (design phase)
- Agent activity feed
- Slack/Teams integration

**Files:**

```
src/api/env_validator_endpoints.py
frontend/src/components/EnvValidator/
├── ValidationTimeline.tsx
├── ViolationHeatmap.tsx
├── DriftStatus.tsx
└── AgentActivityFeed.tsx
```

### Phase 4: Auto-Remediation

**Deliverables:**

- Safe auto-fix for known patterns
- Approval workflow for risky fixes
- Remediation audit trail

**Auto-Remediation Safety Matrix (architecture recommendation):**

| Pattern | Auto-Remediate? | Justification |
|---------|-----------------|---------------|
| ENVIRONMENT env var wrong | YES | Zero risk, simple patch |
| Log group name wrong | NO | Requires new log group creation |
| ConfigMap value wrong | YES (dev/qa only) | Data change, needs HITL in prod |
| Image tag wrong | NO | Could deploy untested code |
| ARN account wrong | NO | Security-critical, HITL required |
| KMS key reference wrong | NO | Security-critical |
| IRSA role wrong | NO | Security-critical |
| Resource suffix wrong | YES (dev/qa only) | Naming fix, HITL in prod |

## Alternatives Considered

### 1. OPA/Gatekeeper Policy Engine

**Pros:** Industry standard, extensive policy library
**Cons:** Requires separate infrastructure, steep learning curve, doesn't cover post-deploy drift

### 2. Crossplane Environment Validation

**Pros:** Native Kubernetes, declarative
**Cons:** Heavy infrastructure, doesn't address CI/CD pre-validation

### 3. Custom Admission Webhook Only

**Pros:** Catches issues at apply time
**Cons:** Doesn't help with CI/CD validation, no drift detection

### Selected Approach: Custom Agent

Provides end-to-end coverage (pre-deploy → post-deploy → continuous) with Aura-specific knowledge and tight integration with existing observability.

## Security Considerations

1. **Read-Only Access:** Agent only reads configurations, never modifies without explicit approval
2. **IRSA Scoped:** Minimal permissions per policy below
3. **Audit Trail:** All validation runs logged to CloudWatch and DynamoDB
4. **No Secrets Exposure:** Validation results never include secret values, only references
5. **Detection-Only Cross-Account:** Parse ARNs to extract account IDs, never access other accounts

### IRSA Policy (architecture recommendation)

```yaml
Statement:
  # AWS Resource Validation (describe only)
  - Sid: DescribeResources
    Effect: Allow
    Action:
      - dynamodb:DescribeTable
      - dynamodb:ListTables
      - neptune:DescribeDBClusters
      - opensearch:DescribeDomain
      - ecr:DescribeRepositories
      - sns:GetTopicAttributes
      - sqs:GetQueueAttributes
      - secretsmanager:ListSecrets
      - ssm:GetParameter
    Resource:
      - !Sub 'arn:${AWS::Partition}:dynamodb:${AWS::Region}:${AWS::AccountId}:table/${ProjectName}-*-${Environment}'
      - !Sub 'arn:${AWS::Partition}:neptune:${AWS::Region}:${AWS::AccountId}:cluster:${ProjectName}-*-${Environment}'
      - !Sub 'arn:${AWS::Partition}:es:${AWS::Region}:${AWS::AccountId}:domain/${ProjectName}-*-${Environment}'
      - !Sub 'arn:${AWS::Partition}:ecr:${AWS::Region}:${AWS::AccountId}:repository/${ProjectName}-*'
      - !Sub 'arn:${AWS::Partition}:sns:${AWS::Region}:${AWS::AccountId}:${ProjectName}-*-${Environment}'
      - !Sub 'arn:${AWS::Partition}:sqs:${AWS::Region}:${AWS::AccountId}:${ProjectName}-*-${Environment}'
      - !Sub 'arn:${AWS::Partition}:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:${ProjectName}/${Environment}/*'
      - !Sub 'arn:${AWS::Partition}:ssm:${AWS::Region}:${AWS::AccountId}:parameter/aura/${Environment}/*'

  # CloudWatch Metrics (required wildcard per ADR-041)
  - Sid: CloudWatchMetrics
    Effect: Allow
    Action: cloudwatch:PutMetricData
    Resource: '*'
    Condition:
      StringEquals:
        cloudwatch:namespace: 'Aura/EnvValidator'

  # DynamoDB for validation history
  - Sid: ValidationHistory
    Effect: Allow
    Action: [dynamodb:PutItem, dynamodb:GetItem, dynamodb:Query]
    Resource:
      - !Sub 'arn:${AWS::Partition}:dynamodb:${AWS::Region}:${AWS::AccountId}:table/${ProjectName}-env-validation-${Environment}'
      - !Sub 'arn:${AWS::Partition}:dynamodb:${AWS::Region}:${AWS::AccountId}:table/${ProjectName}-env-baseline-${Environment}'
      - !Sub 'arn:${AWS::Partition}:dynamodb:${AWS::Region}:${AWS::AccountId}:table/${ProjectName}-env-validation-${Environment}/index/*'

  # Explicit deny for write operations (defense-in-depth)
  - Sid: ExplicitDenyWrites
    Effect: Deny
    Action:
      - dynamodb:DeleteItem
      - neptune:ModifyDBCluster
      - ecr:DeleteRepository
      - sns:DeleteTopic
    Resource: '*'
```

## Cost Estimate

| Component | Monthly Cost (per env) |
|-----------|----------------------|
| Lambda invocations (6hr schedule) | < $1 |
| DynamoDB (on-demand, low volume) | < $5 |
| CloudWatch Logs/Metrics | < $5 |
| **Total** | **~$11/env/month** |

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Environment misconfigurations caught pre-deploy | 95% | Violations blocked / total violations |
| Mean time to detect drift | < 6 hours | Time from drift to alert |
| False positive rate | < 5% | Manual overrides / total blocks |
| Auto-remediation success rate | > 90% | Successful fixes / attempted fixes |

## References

- [ADR-061: GPU Workload Scheduler](ADR-061-gpu-workload-scheduler.md) - Context for issue discovery
- [ADR-042: Real-Time Agent Intervention](ADR-042-realtime-agent-intervention.md) - Agent checkpoint patterns
- [Kubernetes Admission Controllers](https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/)
- [OPA Gatekeeper](https://open-policy-agent.github.io/gatekeeper/website/)

---

## Appendix A: UI Design Specification (Design Review)

### Dashboard Layout

Route: `/validator` in main navigation with `ShieldExclamationIcon`

```text
+------------------------------------------------------------------+
|  Page Header: Environment Validator                               |
|  [Time Range v] [Environment: All v] [Run Validation]            |
+------------------------------------------------------------------+
|  +----------------+  +----------------+  +----------------+       |
|  | Total Runs     |  | Pass Rate      |  | Active Viols   |       |
|  | 145 [+12 today]|  | 97.9% [+2.1%]  |  | 3 [1 critical] |       |
|  +----------------+  +----------------+  +----------------+       |
+------------------------------------------------------------------+
|  VALIDATION TIMELINE (24h time-series pass/fail)                  |
+------------------------------------------------------------------+
|  VIOLATION HEATMAP        |  AGENT ACTIVITY FEED                  |
|  [Rule x Environment]     |  [Real-time actions]                  |
+------------------------------------------------------------------+
|  RECENT VIOLATIONS TABLE (sortable, filterable)                   |
+------------------------------------------------------------------+
```

### Key Components

| Component | Purpose |
|-----------|---------|
| ValidationSummaryCards | Top metric cards (runs, pass rate, violations, blocked) |
| ValidationTimeline | Time-series chart with pass/fail/warn status |
| ViolationHeatmap | Rule x Environment matrix with severity colors |
| AgentActivityFeed | Real-time WebSocket feed of agent actions |
| DriftStatusPanel | Per-environment drift status with scan trigger |
| RemediationHistory | Auto-fix history with before/after diff view |

### Color System (WCAG 2.1 AA compliant)

| Severity | Color | Hex |
|----------|-------|-----|
| Critical | Red | `#DC2626` |
| Warning | Amber | `#F59E0B` |
| Info | Blue | `#3B82F6` |
| Success | Green | `#10B981` |

### Implementation Roadmap (Phase 3)

- **Week 1-2:** Core dashboard, summary cards, timeline
- **Week 3-4:** Heatmap, violations table, detail modals
- **Week 5-6:** Activity feed (WebSocket), drift status
- **Week 7-8:** Remediation history, acknowledgment workflow, accessibility audit
- **Week 5-6:** Activity feed (WebSocket), drift status
- **Week 7-8:** Remediation history, acknowledgment workflow, accessibility audit
