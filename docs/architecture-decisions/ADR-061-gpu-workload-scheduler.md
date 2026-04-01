# ADR-061: GPU Workload Scheduler

## Status

Deployed

## Date

2026-01-12

## Reviews

| Reviewer | Role | Date | Verdict |
|----------|------|------|---------|
| Architecture Review | AWS AI SaaS Architect | 2026-01-12 | Approve with modifications |
| Design Review | UI/UX Designer | 2026-01-12 | Approve with refinements |

## Context

Aura's AI capabilities increasingly require GPU-accelerated compute for specific workloads including code embedding generation, local LLM inference, model fine-tuning, and neural memory consolidation. Currently, GPU resources are provisioned through EKS node groups with scale-to-zero capability (ADR-058), but there is no user-facing mechanism to:

1. Schedule GPU workloads on-demand
2. Monitor GPU job progress and resource utilization
3. Manage job queues and priorities
4. Control costs associated with GPU compute

Users who need GPU acceleration must currently rely on backend automation or manual kubectl commands, creating a gap in the platform's self-service capabilities.

### GPU Workload Types in Aura

| Workload Type | Description | Typical Duration | GPU Memory |
|---------------|-------------|------------------|------------|
| Code Embedding Generation | Batch vectorization of repository code for semantic search | 5-60 minutes | 4-8 GB |
| Local LLM Inference | On-premise model inference for cost optimization | Continuous | 8-16 GB |
| Vulnerability Classifier Training | Fine-tuning security models on customer patterns | 1-4 hours | 8-16 GB |
| Self-Play SWE-RL Training | Reinforcement learning for agent improvement (ADR-050) | 2-8 hours | 16-24 GB |
| Titan Memory Consolidation | Neural memory write operations (ADR-024) | 5-15 minutes | 4-8 GB |

### Current Infrastructure

- **GPU Node Group:** g4dn.xlarge (1 NVIDIA T4, 16GB VRAM) with Spot instances
- **Scaling:** MinSize=0, MaxSize=4, managed by Cluster Autoscaler
- **Device Plugin:** NVIDIA k8s-device-plugin v0.14.3 (deployed via kustomize)
- **Quota:** 32 vCPUs Spot (DEV approved, QA pending)

### Enterprise Capacity Planning (40M+ LOC)

**Important:** AWS Spot vCPU quotas apply to GPU instances. Each g4dn.xlarge consumes 4 vCPUs from your quota while providing 1 GPU.

| Instance Type | vCPUs | GPUs | GPU Memory | Spot Price (us-east-1) |
|---------------|-------|------|------------|------------------------|
| g4dn.xlarge | 4 | 1 | 16 GB | ~$0.16/hr |
| g4dn.2xlarge | 8 | 1 | 16 GB | ~$0.23/hr |
| g5.xlarge | 4 | 1 | 24 GB | ~$0.30/hr |
| g5.2xlarge | 8 | 1 | 24 GB | ~$0.45/hr |

**Embedding Generation Capacity for 40M LOC Codebase:**

```
40M lines of code
÷ ~50 lines per code chunk (average)
= 800,000 code chunks to embed

Embedding throughput per GPU (CodeBERT on g4dn.xlarge):
~500-1,000 chunks/minute depending on batch size

At 750 chunks/minute average:
800,000 chunks ÷ 750 chunks/min = ~1,067 GPU-minutes
```

| vCPU Quota | Max g4dn.xlarge | Max GPUs | Time to Embed 40M LOC | Est. Cost |
|------------|-----------------|----------|----------------------|-----------|
| 32 (default) | 8 | 8 | ~2.2 hours | ~$2.80 |
| 128 | 32 | 32 | ~33 minutes | ~$2.80 |
| 400 | 100 | 100 | ~11 minutes | ~$2.80 |
| 800 | 200 | 200 | ~5 minutes | ~$2.80 |

**Recommendation:** Request 400-800 vCPU Spot quota proactively for enterprise customer onboarding. Quota increases typically approved within 24-48 hours.

```bash
# Check current G-instance Spot quota
aws service-quotas get-service-quota \
  --service-code ec2 \
  --quota-code L-3819A6DF \
  --query 'Quota.Value'

# Request quota increase
aws service-quotas request-service-quota-increase \
  --service-code ec2 \
  --quota-code L-3819A6DF \
  --desired-value 400
```

## Decision

Implement a GPU Workload Scheduler service with a user-facing UI that enables self-service GPU job management within the Aura platform.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Aura Frontend                                │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                 GPU Workloads Panel                          │    │
│  │  • Job Queue Display    • Progress Indicators                │    │
│  │  • Schedule Modal       • Cost Dashboard                     │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    GPU Scheduler Service (FastAPI)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │ Job Manager  │  │ Queue Engine │  │ Resource Monitor         │   │
│  │              │  │              │  │                          │   │
│  │ • Submit     │  │ • Priority   │  │ • GPU utilization        │   │
│  │ • Cancel     │  │ • Fairness   │  │ • Memory usage           │   │
│  │ • Status     │  │ • Preemption │  │ • Cost tracking          │   │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
      ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
      │  SQS FIFO   │      │  DynamoDB   │      │ CloudWatch  │
      │  Job Queue  │      │  Job Store  │      │  Metrics    │
      └─────────────┘      └─────────────┘      └─────────────┘
              │
              ▼
      ┌─────────────┐      ┌─────────────┐
      │ Kubernetes  │ ──── │ Node Term.  │
      │  Jobs API   │      │  Handler    │
      └─────────────┘      └─────────────┘
```

**Architecture Changes from Review:**
- **Added SQS FIFO Queue** - Ensures job queue durability across service restarts (architecture recommendation)
- **Added Node Termination Handler** - Handles Spot interruptions gracefully (moved from Phase 5 to Phase 1)

### Core Components

#### 1. GPU Scheduler Service

A new FastAPI microservice responsible for job lifecycle management.

**API Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/gpu/jobs` | GET | List all jobs for user/org |
| `/api/v1/gpu/jobs` | POST | Submit new GPU job |
| `/api/v1/gpu/jobs/{id}` | GET | Get job status and details |
| `/api/v1/gpu/jobs/{id}` | DELETE | Cancel/terminate job |
| `/api/v1/gpu/jobs/{id}/logs` | GET | Stream job logs |
| `/api/v1/gpu/resources` | GET | Current GPU availability |
| `/api/v1/gpu/costs` | GET | Cost summary for period |

**Job Schema (Strictly Typed - Security Review Recommendation):**

```python
from typing import Union, Literal, Optional
from pydantic import BaseModel, validator
from datetime import datetime
import re

# Strictly typed job configurations (prevents injection via dict)
class EmbeddingJobConfig(BaseModel):
    repository_id: str
    branch: str = "main"
    model: Literal["codebert-base", "codebert-large", "starencoder"] = "codebert-base"

    @validator('repository_id')
    def validate_repo_id(cls, v):
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Invalid repository ID format')
        return v

class VulnerabilityTrainingConfig(BaseModel):
    dataset_id: str
    epochs: int = 10
    batch_size: int = 32
    learning_rate: float = 0.0001

class SWERLTrainingConfig(BaseModel):
    batch_id: str
    max_epochs: int = 100
    checkpoint_interval_minutes: int = 15

class MemoryConsolidationConfig(BaseModel):
    session_id: str
    retention_threshold: float = 0.7

# Union of all valid configs
JobConfig = Union[
    EmbeddingJobConfig,
    VulnerabilityTrainingConfig,
    SWERLTrainingConfig,
    MemoryConsolidationConfig
]

class GPUJob(BaseModel):
    id: str
    user_id: str
    organization_id: str
    job_type: Literal[
        "embedding_generation",
        "local_inference",
        "vulnerability_training",
        "swe_rl_training",
        "memory_consolidation"
    ]
    status: Literal["queued", "starting", "running", "completed", "failed", "cancelled"]
    priority: Literal["low", "normal", "high"]
    config: JobConfig  # Strictly typed, not dict
    gpu_memory_gb: int
    checkpoint_enabled: bool = True
    checkpoint_s3_path: Optional[str] = None  # s3://aura-checkpoints/{org_id}/{job_id}/
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    progress_percent: Optional[int]
    cost_usd: Optional[float]
    kubernetes_job_name: Optional[str]
    error_message: Optional[str] = None
    error_type: Optional[Literal["oom", "spot_interruption", "timeout", "config_error", "network_error"]] = None
```

#### 2. Job Queue Engine

Priority-based queue with fairness scheduling.

**Queue Policies:**

| Priority | Max Concurrent | Preemption | Use Case |
|----------|----------------|------------|----------|
| High | 2 | Can preempt low | Critical training, production inference |
| Normal | 4 | Cannot preempt | Standard batch jobs |
| Low | 2 | Can be preempted | Background optimization, experiments |

**Fairness Rules:**
- Per-organization quota limits (configurable)
- Round-robin scheduling for equal-priority jobs
- Starvation prevention: low-priority jobs promoted after 30 min wait

#### 3. Resource Monitor

Real-time GPU resource tracking integrated with Kubernetes and CloudWatch.

**Metrics Collected:**

| Metric | Source | Update Frequency |
|--------|--------|------------------|
| GPU Utilization % | NVIDIA DCGM Exporter | 10s |
| GPU Memory Used/Total | NVIDIA DCGM Exporter | 10s |
| Node Count | Kubernetes API | 30s |
| Job Progress | Application callback | Job-specific |
| Cost Accumulation | Spot price API + usage | 1m |

#### 4. Kubernetes Integration

Jobs are executed as Kubernetes Job resources with GPU resource requests.

**Job Template:**

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: gpu-job-${JOB_ID}
  namespace: aura-gpu-workloads
  labels:
    aura.io/job-type: ${JOB_TYPE}
    aura.io/user-id: ${USER_ID}
    aura.io/priority: ${PRIORITY}
spec:
  backoffLimit: 2
  activeDeadlineSeconds: 28800  # 8 hour max
  template:
    spec:
      restartPolicy: Never
      tolerations:
        - key: nvidia.com/gpu
          operator: Exists
          effect: NoSchedule
        - key: workload-type
          operator: Equal
          value: gpu-compute
          effect: NoSchedule
      containers:
        - name: gpu-worker
          image: ${ECR_REPO}/aura-gpu-worker:${VERSION}
          resources:
            limits:
              nvidia.com/gpu: 1
              memory: ${MEMORY_LIMIT}
            requests:
              nvidia.com/gpu: 1
              memory: ${MEMORY_REQUEST}
          env:
            - name: JOB_ID
              value: ${JOB_ID}
            - name: JOB_CONFIG
              value: ${JOB_CONFIG_JSON}
```

### Frontend UI Design

#### GPU Workloads Panel

Located in the platform sidebar under "Resources" section.

```
┌─────────────────────────────────────────────────────────────────┐
│ GPU Workloads                                        [?] [⚙️]   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Resources                                                      │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  GPUs: 1/4 in use  │  Queue: 3 jobs  │  Cost today: $2.47 │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  Active Jobs                                                    │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ ● Embedding Generation                           [Cancel] │ │
│  │   repo/backend • 67% • ETA: 8 min                         │ │
│  │   ████████████████████░░░░░░░░░░                          │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  Queued (2)                                                     │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ ○ Vulnerability Training    Normal    Position: 1  [▲][✕] │ │
│  │ ○ Memory Consolidation      Low       Position: 2  [▲][✕] │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  [+ Schedule New Job]                                           │
│                                                                 │
│  Recent (last 24h)                                              │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ ✓ Embedding Gen - repo/frontend    12:34 PM    $0.89      │ │
│  │ ✓ SWE-RL Training Batch #47        09:15 AM    $3.21      │ │
│  │ ✗ Vuln Training (OOM)              Yesterday   $0.12      │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Schedule Job Modal

```
┌─────────────────────────────────────────────────────────────────┐
│ Schedule GPU Job                                         [✕]   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Job Type                                                       │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ ▼ Code Embedding Generation                               │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  Configuration                                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Repository:  ▼ backend-services                           │ │
│  │ Branches:    ☑ main  ☐ develop  ☐ All branches           │ │
│  │ Model:       ▼ CodeBERT-base (recommended)                │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  Resources                                                      │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ GPU Memory:  ▼ 8 GB (recommended for this job)            │ │
│  │ Priority:    ○ Low  ● Normal  ○ High                      │ │
│  │ Max Runtime: ▼ 2 hours                                    │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  Estimated Cost: $0.45 - $0.90                                  │
│  Queue Position: 3 (starts in ~15 min)                          │
│                                                                 │
│                              [Cancel]  [Schedule Job]           │
└─────────────────────────────────────────────────────────────────┘
```

#### Cost Dashboard (Settings > Usage > GPU)

```
┌─────────────────────────────────────────────────────────────────┐
│ GPU Usage & Costs                                    Jan 2026   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Monthly Summary                                                │
│  ┌─────────────┬─────────────┬─────────────┬─────────────────┐ │
│  │ Total Cost  │ GPU Hours   │ Jobs Run    │ Avg Job Cost    │ │
│  │ $47.82      │ 142.5 hrs   │ 89          │ $0.54           │ │
│  └─────────────┴─────────────┴─────────────┴─────────────────┘ │
│                                                                 │
│  Cost by Job Type                           Usage Trend         │
│  ┌────────────────────────────┐   ┌────────────────────────┐   │
│  │ Embedding Gen    ████ $18  │   │    ╭─╮                 │   │
│  │ SWE-RL Training  ██████$24 │   │   ╭╯ ╰╮  ╭╮           │   │
│  │ Vuln Training    ██ $4     │   │ ╭─╯    ╰──╯╰╮ ╭╮      │   │
│  │ Other            █ $2      │   │ 1  5  10  15  20  25   │   │
│  └────────────────────────────┘   └────────────────────────┘   │
│                                                                 │
│  Budget Alert: ☑ Notify when monthly cost exceeds $[100]        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Data Model

#### DynamoDB Tables

**Table: aura-gpu-jobs**

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| PK | String | Partition | `ORG#{org_id}` |
| SK | String | Sort | `JOB#{job_id}` |
| GSI1PK | String | GSI1 Partition | `ORG#{org_id}#STATUS#{status}` |
| GSI1SK | String | GSI1 Sort | `{created_at}#{job_id}` |

| job_type | String | - | Job type enum |
| user_id | String | - | Submitting user |
| priority | String | - | low/normal/high |
| config | Map | - | Job-specific config |
| status | String | - | Current status |
| progress | Number | - | 0-100 |
| cost_usd | Number | - | Accumulated cost |
| k8s_job_name | String | - | Kubernetes job name |
| created_at | String | - | ISO timestamp |
| started_at | String | - | ISO timestamp |
| completed_at | String | - | ISO timestamp |
| error_message | String | - | If failed |
| ttl | Number | - | Auto-delete after 90 days |

**Note:** GSI1 uses org-scoped partitioning (`ORG#{org_id}#STATUS#{status}`) to prevent hot partitions when many jobs share the same status.

**Table: aura-gpu-quotas**

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| PK | String | Partition | `ORG#{org_id}` |
| SK | String | Sort | `QUOTA` |
| max_concurrent_jobs | Number | - | Max parallel jobs |
| max_gpu_hours_monthly | Number | - | Monthly limit |
| max_job_runtime_hours | Number | - | Per-job limit |
| current_month_usage | Number | - | Hours used this month |

### Security Considerations

1. **Job Isolation:** Each job runs in a dedicated pod with no shared storage
2. **Resource Limits:** Enforced via Kubernetes resource quotas and LimitRanges
3. **Network Policy:** GPU workload namespace has restricted egress (internal services only)
4. **Secret Access:** Jobs access secrets via External Secrets Operator (synced from Secrets Manager)
5. **Audit Logging:** All job submissions logged to CloudTrail via API Gateway
6. **Cost Controls:** Organization-level spending limits with automatic job rejection
7. **Strictly Typed Configs:** Job configurations use Pydantic models to prevent injection

#### RBAC Configuration (Architecture Recommendation)

```yaml
# GPU Scheduler ServiceAccount with IRSA
apiVersion: v1
kind: ServiceAccount
metadata:
  name: gpu-scheduler
  namespace: aura-system
  annotations:
    eks.amazonaws.com/role-arn: arn:${AWS::Partition}:iam::${AWS::AccountId}:role/aura-gpu-scheduler-${Environment}

---
# Scoped Role - GPU workload namespace ONLY
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: gpu-scheduler
  namespace: aura-gpu-workloads
rules:
  - apiGroups: ["batch"]
    resources: ["jobs"]
    verbs: ["create", "delete", "get", "list", "watch"]
  - apiGroups: [""]
    resources: ["pods", "pods/log"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["events"]
    verbs: ["list", "watch"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: gpu-scheduler
  namespace: aura-gpu-workloads
subjects:
  - kind: ServiceAccount
    name: gpu-scheduler
    namespace: aura-system
roleRef:
  kind: Role
  name: gpu-scheduler
  apiGroup: rbac.authorization.k8s.io
```

#### NetworkPolicy (Architecture Recommendation)

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: gpu-workloads-egress
  namespace: aura-gpu-workloads
spec:
  podSelector: {}
  policyTypes:
    - Egress
  egress:
    # Allow DNS
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
      ports:
        - protocol: UDP
          port: 53
    # Allow internal Aura services
    - to:
        - namespaceSelector:
            matchLabels:
              name: aura-system
      ports:
        - protocol: TCP
          port: 8080
    # Allow S3/DynamoDB via VPC endpoints
    - to:
        - ipBlock:
            cidr: 10.0.0.0/8
      ports:
        - protocol: TCP
          port: 443
```

#### ResourceQuota and LimitRange

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: gpu-quota
  namespace: aura-gpu-workloads
spec:
  hard:
    requests.nvidia.com/gpu: "4"
    limits.nvidia.com/gpu: "4"
    count/jobs.batch: "20"

---
apiVersion: v1
kind: LimitRange
metadata:
  name: gpu-limits
  namespace: aura-gpu-workloads
spec:
  limits:
    - type: Container
      default:
        memory: "16Gi"
        nvidia.com/gpu: "1"
      defaultRequest:
        memory: "8Gi"
        nvidia.com/gpu: "1"
      max:
        memory: "24Gi"
        nvidia.com/gpu: "1"
```

### Implementation Phases

#### Phase 1: Core Infrastructure (Foundation)
- GPU Scheduler Service (FastAPI)
- SQS FIFO queue for job durability
- DynamoDB tables for job storage
- Kubernetes Job template and RBAC
- Basic job submission and status API
- **AWS Node Termination Handler deployment** (moved from Phase 5 - critical for Spot)
- **Job checkpointing infrastructure** (S3-based checkpoint storage)
- NetworkPolicy and ResourceQuota for namespace isolation

#### Phase 2: Queue Management
- Priority queue implementation
- Fairness scheduling algorithm
- Job preemption for high-priority work
- Queue position estimation

#### Phase 3: Frontend Integration
- GPU Workloads panel component (with progressive disclosure)
- Schedule Job modal (Simple/Advanced modes)
- Real-time progress updates (WebSocket)
- Job log streaming
- Error state UI (OOM, Spot interruption, timeout)
- Empty/Loading states

#### Phase 4: Observability & Cost
- DCGM Exporter integration
- CloudWatch metrics and dashboards
- Cost tracking and allocation
- Budget alerts with predictive projections
- Cost drill-down by job type

#### Phase 5: Advanced Features
- Job templates (save/reuse configurations)
- Scheduled recurring jobs (cron)
- Multi-GPU job support
- Stalled job detection and alerting

## Consequences

### Positive

1. **Self-Service GPU Access:** Users can schedule GPU workloads without DevOps intervention
2. **Cost Visibility:** Clear cost attribution per job, user, and organization
3. **Resource Efficiency:** Queue management prevents over-provisioning
4. **Audit Trail:** Full history of GPU usage for compliance
5. **Scalability:** Kubernetes-native approach scales with cluster

### Negative

1. **Operational Complexity:** New service to deploy, monitor, and maintain
2. **Cost Overhead:** DynamoDB, additional CloudWatch metrics
3. **Learning Curve:** Users must understand job types and configuration options

### Neutral

1. **Spot Instance Risk:** Jobs may be interrupted; mitigation via checkpointing
2. **Queue Wait Times:** During high demand, users may experience delays

## Alternatives Considered

### 1. AWS Batch

**Decision: Kubernetes-native approach chosen, but AWS Batch remains viable for future scale.**

| Factor | Kubernetes Jobs | AWS Batch |
|--------|-----------------|-----------|
| GPU scheduling | Manual via device plugin | Native GPU support |
| Spot interruption | Node Termination Handler | Built-in Spot best practices |
| Queue management | Custom SQS implementation | Native priority queues |
| Cost | EKS overhead | ~$0 (pay only for compute) |
| Fairshare scheduling | Custom implementation | Native fairshare |
| GovCloud | Yes | Yes |

**Why Kubernetes was chosen:**
- Unified platform: All workloads on same EKS cluster
- Existing EKS investment: Mature infrastructure already deployed
- Fine-grained control: Custom scheduling policies for agent workloads
- GovCloud consistency: Same architecture in commercial and GovCloud

**When to reconsider AWS Batch:**
- Batch job volume exceeds 1,000+ jobs/day
- Complex job dependencies needed (array jobs)
- Multi-account job submission patterns
- Spot interruption rate exceeds 20%

### 2. Kubeflow Pipelines

**Rejected because:**
- Heavyweight for Aura's current needs
- Designed for ML pipelines, not general GPU jobs
- Steep learning curve for users

### 3. Argo Workflows

**Considered for future:**
- Good fit for complex multi-step GPU workflows
- Could replace Phase 5 scheduled jobs feature
- Deferred to avoid scope creep

## UI/UX Specifications (Design Review)

### Design Principles

- **Progressive Disclosure:** Schedule modal uses Simple mode by default, Advanced options collapsed
- **Accessibility:** WCAG 2.1 AA compliance required (text labels alongside color indicators)
- **Consistency:** Use Aura's existing design system (Tailwind, Inter font, 8px spacing)

### Error State Taxonomy

| Error Type | Severity | Background | Icon | User Action |
|------------|----------|------------|------|-------------|
| OOM | High | `bg-red-50` | ExclamationCircle | Retry with more memory |
| Spot Interruption | Medium | `bg-blue-50` | InformationCircle | Auto-retry from checkpoint |
| Configuration Error | High | `bg-red-50` | ExclamationCircle | Fix config and retry |
| Timeout | Medium | `bg-amber-50` | ExclamationTriangle | Extend runtime or optimize |
| Quota Exceeded | Blocking | `bg-red-50` | StopCircle | Request budget increase |

### Required UI States

| State | Priority | Description |
|-------|----------|-------------|
| Empty | P0 | No jobs ever run - show onboarding CTA |
| Loading | P0 | Initial data fetch - skeleton loaders |
| Queue Full | P1 | Max concurrent jobs reached |
| Node Scaling | P1 | GPUs scaling from 0 (show provisioning indicator) |
| Stalled Job | P1 | No progress update for >5 minutes |
| Job Paused | P2 | Manually paused by user |

### Accessibility Requirements

```jsx
// Progress bar with ARIA attributes
<div
  role="progressbar"
  aria-valuenow={67}
  aria-valuemin={0}
  aria-valuemax={100}
  aria-label="Embedding generation: 67% complete, ~8 minutes remaining"
>
  {/* Visual progress bar */}
</div>

// Live region for status announcements
<div aria-live="polite" aria-atomic="true" className="sr-only">
  {statusMessage}
</div>
```

### Component Specifications

```typescript
interface GPUWorkloadPanelProps {
  resources: {
    gpusInUse: number;
    gpusTotal: number;
    queueDepth: number;
    estimatedWait: string;
    costToday: number;
    costDelta: number;
  };
  activeJobs: GPUJob[];
  queuedJobs: GPUJob[];
  recentJobs: GPUJob[];
  onScheduleNew: () => void;
  onCancelJob: (jobId: string) => void;
  onBoostPriority: (jobId: string) => void;
}

interface ScheduleJobModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (config: GPUJobConfig) => Promise<void>;
  repositories: Repository[];
  estimatedQueuePosition: number;
  estimatedWaitTime: string;
  organizationBudget: {
    used: number;
    total: number;
  };
}
```

### Tailwind Class Reference

```jsx
// Card container
className="bg-white rounded-lg shadow-sm border border-gray-200 p-4"

// Progress bar track
className="h-2 bg-gray-200 rounded-full overflow-hidden"

// Progress bar fill (animated)
className="h-full bg-blue-500 rounded-full transition-all duration-300"

// Cancel button (destructive)
className="text-sm text-red-600 hover:text-red-700 font-medium"

// Primary action button
className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
```

## References

- ADR-024: Titan Neural Memory Architecture
- ADR-050: Self-Play SWE-RL Training Pipeline
- ADR-058: EKS Multi-Node Group Architecture
- [NVIDIA GPU Operator](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/overview.html)
- [Kubernetes Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/)
- [DCGM Exporter](https://github.com/NVIDIA/dcgm-exporter)
- [AWS Node Termination Handler](https://github.com/aws/aws-node-termination-handler)
