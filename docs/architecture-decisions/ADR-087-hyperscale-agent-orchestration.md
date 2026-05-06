# ADR-087: Configurable Hyperscale Agent Orchestration

## Status

Accepted (Phase 1 Implemented; full implementation in progress)

Phase 1 deployed: UI gating, execution tier selection, security gate validation, Integration Mode enforcement, hyperscale endpoints (`src/api/orchestrator_settings_endpoints.py`, 39 tests at `tests/test_hyperscale_endpoints.py`).

Outstanding before Phase 2: tenant isolation on per-org settings reads/writes, DynamoDB persistence for `_hyperscale_settings` (currently in-memory module-global, lost on pod restart), and the remainder of the planned 1,990 test suite.

## Date

2026-05-05 (proposed) / 2026-05-06 (Phase 1 status update)

## Reviews

| Role | Date | Verdict |
|------|------|---------|
| AWS/AI SaaS Architect | 2026-05-05 | Approved with conditions |
| Cybersecurity Analyst | 2026-05-05 | Approved with conditions |
| AI Product Manager | 2026-05-05 | Approved with conditions |
| Principal Data Engineer | 2026-05-05 | Approved with conditions |

## Context

### The Orchestration Gap

Project Aura's MetaOrchestrator caps at 10 parallel agents via in-process `asyncio.gather()` in a single EKS pod. This design was appropriate for the initial implementation but creates two limitations:

1. **Enterprise codebases cannot be processed in parallel.** A 500K-line codebase with 2,000 files is scanned sequentially in batches of 10. At ~30 seconds per agent invocation, a full scan takes hours rather than minutes.

2. **The orchestration layer is invisible.** Most competitors treat the model as the product and orchestration as plumbing. Aura's differentiator is that orchestration — bounded by pre-approved specs — is where coherence at scale is unlocked.

### Current Architecture Constraints

| Component | Current Limit | Constraint Type |
|---|---|---|
| `max_parallel_agents` | 10 | Constructor parameter (not wired to config) |
| DAG execution | In-process `asyncio.gather()` | Single pod, single event loop |
| SQS topology | 4 fixed queues (coder, reviewer, validator, responses) | No tenant sharding |
| Lambda dispatcher | Concurrency disabled (account quota: 10) | AWS account limit |
| Agent pod resources | 1 CPU / 2GB request, 2 CPU / 4GB limit | K8s resource spec |
| `MAX_CONCURRENT_AGENTS` env var | Defined in Helm but not read by code | Orphaned configuration |

### Design Principles

Two capabilities define this approach:

**Reverse engineering before generation.** Every task is validated against the codebase knowledge graph (Neptune + OpenSearch) before agents generate code. The pre-generation feasibility gate extracts mutation site constraints, checks architectural conformance, and blocks infeasible generation attempts. This grounding is what makes autonomy safe at enterprise scale.

**Orchestration at hyperscale.** Thousands of agents work in parallel, bounded by pre-approved specs (autonomy policies, Constitutional AI, Constraint Geometry Engine). Coherence at scale requires the orchestration layer to enforce governance invariants regardless of parallelism level.

## Decision

Implement configurable hyperscale agent orchestration as a **UI-gated platform capability** with three execution tiers, a pre-generation feasibility gate, and graduated security controls. Hyperscale is structurally unavailable to defense customers via dual-layer enforcement (UI gate + backend policy enforcement).

### Platform Capability Gating

Hyperscale agent orchestration is gated by the platform's existing Integration Mode system and autonomy policy presets. This dual-layer enforcement ensures defense customers cannot access hyperscale regardless of API access patterns.

#### UI Gating (Frontend)

The Orchestrator Mode tab in Platform Settings gains a new "Hyperscale Orchestration" section:

- **Defense Mode**: Section displays a "Coming Soon" banner with account team contact link (same UX pattern as MCP Gateway in Defense Mode). Defense customers see the capability exists but cannot enable it.
- **Enterprise / Hybrid Mode**: Section is fully interactive with:
  - Toggle to enable/disable hyperscale orchestration
  - Three execution tier cards (In-Process / Distributed Simple / Distributed Orchestrated) — selecting a tier auto-sets the max parallel agents range to the tier's default
  - Max parallel agents slider (exposed in an Advanced expandable, ceiling determined by tier and edition)
  - Security gate status indicators showing Gate 1/2/3 validation progress
  - Cost circuit breaker configuration cross-linked to Cost Management settings

#### Backend Enforcement (Server-Side)

The MetaOrchestrator checks integration mode at the orchestrator level before spawning agents — not at the API gateway alone. This prevents bypass via service mesh or direct pod access:

```python
# In MetaOrchestrator._validate_scale_request()
tenant_config = await self._get_tenant_config(tenant_id)
integration_mode = tenant_config.integration_mode  # defense | enterprise | hybrid
preset = tenant_config.autonomy_preset

# Orchestrator-level enforcement — not bypassable via API
max_allowed = PRESET_CEILINGS[preset]  # defense_contractor=5, etc.
if requested_agents > max_allowed:
    raise ScaleCeilingExceeded(
        f"Preset '{preset}' caps at {max_allowed} agents"
    )
```

#### Audit Trail for Preset Transitions (NIST AU-3)

Any change to a tenant's autonomy preset or integration mode generates an auditable event with approval chain:

| Event | Required | Logged Fields |
|---|---|---|
| Preset change (e.g., defense → enterprise) | Admin approval + reason | tenant_id, old_preset, new_preset, approver, timestamp, justification |
| Integration mode change | Admin approval + confirmation dialog | tenant_id, old_mode, new_mode, approver, timestamp |
| Max parallel agents increase | Automatic if within preset ceiling | tenant_id, old_value, new_value, preset, timestamp |

Events are published to CloudTrail and the platform's EventBridge bus for SIEM integration.

#### Edition-Based Tier Gating (Pricing)

Hyperscale maps to paid platform editions:

| Edition | Max Agents | Execution Tiers | Included |
|---|---|---|---|
| **Standard** | 20 | In-Process only | Included |
| **Enterprise** | 200 | In-Process + Distributed Simple | Licensed |
| **Scale** | 1,000+ | All tiers | Consumption-based pricing |

The cost circuit breaker becomes a selling point: "scale with guardrails" reduces buyer risk.

#### Defense Parallel Roadmap (Future)

Defense customers are not permanently excluded. A "Defense Parallel" tier (max 50 agents with enhanced HITL checkpoints and full audit logging) is planned for the roadmap. This tier would require:
- All Gate 1 + Gate 2 security controls validated
- Full HITL on every agent action (no auto-approve)
- FedRAMP-authorized infrastructure only
- Dedicated Neptune cluster per tenant (physical isolation)

### Three-Tier Execution Model

| Tier | Agent Count | Execution Model | Use Case |
|---|---|---|---|
| **In-Process** | 1–20 | Single pod, asyncio, Kahn's DAG | Small repos, targeted scans |
| **Distributed Simple** | 20–200 | SQS fan-out, DynamoDB job graph, aggregation service | Mid-size enterprise repos |
| **Distributed Orchestrated** | 200–1,000+ | Step Functions Express fan-out + Standard DAG stages, Karpenter autoscaling | Full enterprise codebase scans |

The MetaOrchestrator selects execution tier automatically based on the configured `max_parallel_agents` for the tenant, or the tier can be specified explicitly.

#### In-Process Tier (1–20 agents)

No architectural changes. Wire `max_parallel_agents` to tenant configuration in DynamoDB and the `MAX_CONCURRENT_AGENTS` environment variable. Kahn's algorithm DAG execution remains in-process via `asyncio.gather()`.

#### Distributed Simple Tier (20–200 agents)

Externalize the DAG to DynamoDB. Each node in the task graph is an independent agent job dispatched via SQS FIFO queues. A lightweight aggregation service collects results and triggers downstream DAG stages when dependencies resolve.

**SQS FIFO throughput:** FIFO queues cap at 300 messages/second per `MessageGroupId`. To avoid bottlenecking large tenants, use composite MessageGroupIds: `{tenant_id}#{priority_band}` (e.g., `tenant-42#critical`, `tenant-42#standard`, `tenant-42#low`). This multiplies per-tenant throughput by the number of bands while preserving per-band ordering. Strict cross-band ordering is not required since agents operate on independent files. High-throughput FIFO mode must be enabled.

```
MetaOrchestrator → DynamoDB Job Graph → SQS FIFO Dispatch
                                              ↓
                                     EKS Agent Pods (Karpenter)
                                              ↓
                                     DynamoDB Results → Aggregation Service
                                              ↓
                                     Next DAG Stage (repeat)
```

#### Distributed Orchestrated Tier (200–1,000+ agents)

Step Functions Express Workflows orchestrate within-stage fan-out (Map state, up to 10,000 concurrent iterations). Step Functions Standard Workflows manage cross-stage DAG transitions (avoids Express 5-minute limit). Karpenter provisions spot-first node pools with on-demand fallback.

```
MetaOrchestrator → Step Functions Standard (DAG stages)
                        ↓
                   Step Functions Express (Map state fan-out)
                        ↓
                   SQS FIFO → EKS Agent Pods (Karpenter spot pools)
                        ↓
                   DynamoDB Results → Stage Completion Check
                        ↓
                   Next DAG Stage (Standard Workflow transition)
```

### Pre-Generation Feasibility Gate

Inserted between context retrieval and code generation in both `System2Orchestrator` (line 1382→1392 of `agent_orchestrator.py`) and `MetaOrchestrator` (line 915→932 of `meta_orchestrator.py`).

#### Three Components

**1. Mutation Site Analyzer**
Queries Neptune for structural metadata about the target entity before generation: callers, dependents, inheritance chains, public API contracts. Returns a `MutationSiteProfile` with modification constraints.

```python
@dataclass(frozen=True)
class MutationSiteProfile:
    entity_id: str
    entity_type: str                    # function, class, module
    caller_count: int                   # how many entities call this
    dependent_count: int                # how many entities depend on this
    is_public_api: bool                 # signature is a contract
    inheritance_depth: int              # position in class hierarchy
    security_sensitive: bool            # touches auth, crypto, sandbox
    constraints: list[MutationConstraint]  # extracted from constraint registry
```

**2. Pre-Generation CGE Mode**
Extends `ConstraintGeometryEngine.assess_coherence()` to accept a `MutationSpec` (proposed change intent) in addition to `AgentOutput` (generated code). Same 7-axis scoring applied to intent rather than output. Returns a `FeasibilityResult`:

```python
@dataclass(frozen=True)
class FeasibilityResult:
    is_feasible: bool
    feasibility_score: float            # 0.0–1.0
    blocking_constraints: list[str]     # hard blocks
    warnings: list[str]                 # soft warnings
    recommendation: str                 # PROCEED | REVIEW | BLOCK
```

**3. Architecture Constraint Registry**
Machine-readable rules stored as Neptune edges attached to code entities:

| Edge Type | Meaning | Example |
|---|---|---|
| `CONSTRAINS` | Limits modifications | "public API signature is frozen" |
| `FORBIDS` | Blocks specific changes | "no new dependencies on module X" |
| `REQUIRES` | Mandates patterns | "this module uses factory pattern" |
| `PRESERVES` | Invariants | "function must remain idempotent" |

Constraints are populated during repository ingestion and can be authored manually by repository owners.

#### Gate Behavior

| Result | Agent Count ≤ 20 | Agent Count > 20 |
|---|---|---|
| **PROCEED** | Generate immediately | Dispatch to agent queue |
| **REVIEW** | Flag for HITL pre-approval | Pause task, escalate |
| **BLOCK** | Skip task, return constraint violation | Skip task, log to job graph |

### Configuration Surface

```yaml
# Per-tenant orchestration configuration (DynamoDB: aura-platform-settings)
orchestration:
  max_parallel_agents: 200              # Ceiling for this tenant
  execution_mode: auto                  # auto | in_process | distributed_simple | distributed_orchestrated
  feasibility_gate_enabled: true        # Pre-generation validation
  sandbox_concurrency_ceiling: 50       # Platform-wide sandbox limit
  agent_resource_profile: standard      # standard | memory_optimized | gpu
  cost_circuit_breaker_usd: 500        # Pause job if estimated cost exceeds threshold

# Per-tenant quotas (enforced at admission control)
quotas:
  max_concurrent_agents: 200            # Hard limit across all active jobs
  max_jobs_queued: 20                   # Pending job backlog limit
  max_task_nodes_per_job: 5000          # DAG size ceiling (fork bomb prevention)
  max_agent_duration_seconds: 1800      # Per-task timeout
  bedrock_token_budget_per_day: 10000000  # Daily LLM token ceiling
```

Governed by autonomy policy presets:

| Preset | Max Parallel | Execution Mode | Feasibility Gate |
|---|---|---|---|
| `defense_contractor` | 5 | in_process | Required, REVIEW threshold: 0.95 |
| `financial_services` | 20 | in_process | Required, REVIEW threshold: 0.90 |
| `healthcare` | 20 | in_process | Required, REVIEW threshold: 0.90 |
| `enterprise_standard` | 200 | auto | Required, REVIEW threshold: 0.80 |
| `fintech_startup` | 500 | auto | Enabled, REVIEW threshold: 0.70 |
| `internal_tools` | 1000 | auto | Enabled, REVIEW threshold: 0.60 |
| `fully_autonomous` | 1000 | auto | Enabled, REVIEW threshold: 0.60 |

### Security Architecture

#### Graduated Security Gates

Security controls scale with agent count. Each gate must be validated before advancing to the next scale tier:

**Gate 1: Scale to 50 agents (prerequisite for distributed execution)**

| Control | Requirement | Maps To |
|---|---|---|
| Neptune tenant partitioning | Property-based isolation via `tenant_id` on all vertices/edges, enforced at query level by `TenantIsolatedGraphService` wrapper (Neptune Gremlin does not support named graphs) | NIST AC-4 |
| DAG validation | Cycle detection + total task ceiling per job | Fork bomb prevention |
| Constitutional AI fail-closed | Infrastructure-level enforcement — reject on timeout, never approve by default | NIST SI-4 |
| Per-tenant EKS ResourceQuotas | CPU, memory, pod count limits per tenant namespace | NIST SC-5 |
| Per-task execution timeouts | Kubernetes Job `deadlineSeconds` on every agent pod | Resource exhaustion prevention |

**Gate 2: Scale to 200 agents**

| Control | Requirement | Maps To |
|---|---|---|
| Tiered IAM roles | Map ADR-066 4-tier tool classification (SAFE/GUARDED/RESTRICTED/CRITICAL) to separate IAM roles | NIST AC-6 |
| STS session tagging | Embed tenant_id, task_id, agent_id in every assumed role session | NIST AU-3 |
| Job-graph governance | Aggregate impact assessment of full DAG before execution begins | Salami attack prevention |
| HITL rate limiting | Max K approval requests per tenant per T minutes; priority stratification | Approval fatigue prevention |
| Sandbox concurrency ceiling | Platform-wide cap independent of per-tenant agent limits | Coordinated sandbox escape mitigation |

**Gate 3: Scale to 1,000+ agents**

| Control | Requirement | Maps To |
|---|---|---|
| Write quorum for Neptune | No single-agent graph mutation committed without second-agent validation or configurable delay | ADR-085 N-of-M consensus |
| Cumulative impact tracking | Running tally of changes per job graph; auto-pause if scope exceeds thresholds | Emergent behavior detection |
| Graph mutation journaling | Append-only journal of all Neptune writes per job graph; atomic rollback capability | Incident response |
| Behavioral baseline recalibration | ADR-083 baselines retrained for 1000-agent workload patterns | NIST SI-4 |
| Incident response playbooks | Agent swarm compromise scenarios added to IR procedures | NIST IR-4 |

#### Blast Radius Controls

**Confused Agent Cascade Prevention (Write-Ahead Staging Graph):**

At scale, a single agent's bad graph write can poison context for hundreds of downstream agents. The primary defense is a write-ahead staging model that isolates agent mutations from the live tenant graph:

1. **Staging subgraph per job.** Agent writes target a staging partition (property `graph_scope = staging:{job_id}`) rather than the live tenant graph. Other agents in the same job read from a snapshot of the live graph taken at job start time (`snapshot_version` property on read queries).

2. **Batch validation before commit.** When a job completes, all staged writes are validated as a composite:
   - CGE evaluates the aggregate diff (all staged writes together, not individually)
   - Cross-reference conflict detection across staged writes
   - Constitutional AI critique on the aggregate change set (fail-closed)
   - Only after validation passes are staged writes promoted to the live graph

3. **Per-job staging limits.** To prevent staging graph DoS (a malicious or buggy agent generating massive staging data):
   - Maximum staging graph size: 10,000 vertices + 50,000 edges per job (configurable per preset)
   - Commit window timeout: 120 seconds for validation + promotion (configurable)
   - If either limit is exceeded, the job pauses and escalates to HITL

4. **Snapshot staleness bound.** Long-running jobs risk reading outdated topology as other jobs commit to the live graph. If the live graph diverges beyond a configurable threshold (default: 50 commits since snapshot), the job either forces a re-read of affected subgraphs or pauses for operator review.

5. At Gate 3 (1,000+), write quorum validation requires second-agent confirmation before any staged write is accepted into the staging partition.

**Salami Attack Prevention (Cumulative Impact Tracking):**

1. **Pre-execution DAG impact projection.** Before the job starts, analyze the full DAG to estimate composite scope. If >30% of tasks target the same module/subsystem, require HITL pre-approval of the full plan (not individual patches). Thresholds are tunable per autonomy preset.

2. **Running cumulative impact tracker.** As agents complete tasks, maintain a per-job tally: `{module: files_modified, lines_changed, functions_altered}`. After each task completion, re-evaluate cumulative impact against preset-specific thresholds. Auto-pause and escalate if cumulative changes to a single subsystem exceed the configured limit.

3. **Semantic change clustering via CGE.** Use the 7-axis scoring to detect semantic convergence across tasks. If N tasks all score high on the `security_boundary` axis, the composite change reshapes the security surface even if individual tasks are benign.

**HITL Queue Saturation Prevention:**
1. Per-tenant HITL rate limit (configurable per preset, default: 20 approvals per 10 minutes)
2. Priority stratification: credential/infrastructure approvals surface above code-change approvals
3. If rate limit exceeded, agent pool pauses and escalates to tenant admin

### Infrastructure

#### Karpenter Autoscaling

Two NodePools with spot-first, on-demand fallback:

```
NodePool: agent-workers (weight: 50, spot)
  Instance types: c6i.4xlarge, c6i.8xlarge, c6a.4xlarge, c6a.8xlarge, c7i.4xlarge, m6i.4xlarge
  Limits: 2000 CPU, 4000Gi memory
  Consolidation: 30s after underutilization
  Taints: workload-type=agent:NoSchedule

NodePool: agent-workers-on-demand (weight: 10, on-demand fallback)
  Instance types: c6i.8xlarge, c6i.16xlarge
  Limits: 500 CPU
```

Spot interruption handling via AWS Node Termination Handler (NTH). Agent pods must be idempotent — on termination, checkpoint to DynamoDB and re-enqueue task.

#### Queue Architecture

SQS FIFO queues with composite `MessageGroupId = {tenant_id}#{priority_band}` for per-tenant, per-priority ordering within shared queues. Three priority bands (`critical`, `standard`, `low`) multiply per-tenant throughput from 300 msg/s to 900 msg/s while preserving per-band ordering. High-throughput FIFO mode must be enabled.

A dispatch service (2–3 EKS replicas) reads from FIFO queues and enforces per-tenant concurrency via sliding window counters.

No separate queues per tenant — this does not scale and creates operational overhead.

#### DynamoDB Job Graph Schema

```
Table: aura-job-graph-{env}
  Partition Key: agent_id (String)     # Distributes writes across partitions
  Sort Key: job_id#node_id (String)    # Composite for job + DAG node

GSI-1: job-shard-index
  Partition Key: job_id#shard_id (String)  # Write-sharded: {job_id}#{0-9}
  Sort Key: status#node_id                 # Query pending/completed nodes per job

GSI-2: tenant-active-index
  Partition Key: tenant_id
  Sort Key: created_at                 # Per-tenant active job tracking
```

Base table partition key is `agent_id` (not `job_id`) to avoid hot partitions when 1,000 agents write results to the same job simultaneously.

**GSI-1 write sharding:** The original `job_id` partition key for GSI-1 creates a hot partition when 1,000 agents write status updates to the same job. To avoid DynamoDB's 1,000 WCU/s per-partition limit, GSI-1 uses a composite key `{job_id}#{shard_id}` where `shard_id` is `hash(agent_id) % 10`. Reads against GSI-1 use scatter-gather across 10 shards. This distributes writes evenly across partitions at the cost of 10 parallel queries on read — acceptable since job-level reads are infrequent compared to per-agent writes.

### GovCloud Compatibility

All services in this architecture are available in us-gov-west-1:

| Service | GovCloud | FIPS Endpoint |
|---|---|---|
| EKS | Yes | Yes |
| SQS (Standard + FIFO) | Yes | Yes |
| DynamoDB + Streams | Yes | Yes |
| Step Functions (Standard + Express) | Yes | Yes |
| Karpenter (via EC2 APIs) | Yes | Yes |
| Bedrock (Claude models) | Yes | Yes |
| Lambda | Yes | Yes |

No GovCloud blockers.

### Cost Management

#### Per-Job Cost Estimation

The pre-generation feasibility gate includes cost projection before execution:

| Component | Cost per Agent | 1,000 Agents |
|---|---|---|
| Bedrock (avg 8K in / 2K out tokens) | $0.054 | $54 |
| EKS compute (spot, 2 min avg) | $0.004 | $4 |
| SQS + DynamoDB | $0.001 | $1 |
| **Per-job total** | | **~$59** |

With 3 LLM calls per agent average: **~$162/job**.

#### Cost Controls

1. **Cost circuit breaker (server-side)**: Enforced at the Step Functions execution level and SQS dispatch service — not via UI polling. Step Functions Standard Workflow has a `TimeoutSeconds` hard stop per job. The dispatch service tracks running cost via DynamoDB atomic counters and halts task dispatch when the per-tenant threshold is reached. SQS dead-letter queues catch tasks that exceed per-agent timeout. The UI displays cost status but the enforcement is server-side.
2. **Model routing**: Haiku for validation/review agents (12x cheaper), Sonnet for code generation agents only
3. **Semantic caching**: ADR-029 Phase 1.3 (already deployed) — deduplicates identical context retrievals across agents in same job
4. **Bedrock Batch API**: For non-latency-sensitive agents, batch inference at 50% discount
5. **Per-tenant daily token budget**: Hard ceiling on Bedrock token consumption per billing cycle

## Implementation Plan

### Phase 1: Configuration and In-Process Scaling (2–3 weeks)

- Wire `max_parallel_agents` to tenant config in DynamoDB and `MAX_CONCURRENT_AGENTS` env var
- Increase in-process ceiling to 20 with validated pod resource limits
- Implement per-tenant admission control (quota checks at MetaOrchestrator entry)
- Add CloudWatch metrics: `ActiveAgents`, `QueueDepth`, `AgentDuration` per tenant
- Implement DAG validation: cycle detection, total task ceiling, depth limit
- **Security gate: Validate Gate 1 controls**

### Phase 2: Pre-Generation Feasibility Gate (3–4 weeks)

- Implement Mutation Site Analyzer (Neptune queries for structural metadata)
- Extend CGE with pre-generation assessment mode (`MutationSpec` → `FeasibilityResult`)
- Implement Architecture Constraint Registry (Neptune edge types: CONSTRAINS, FORBIDS, REQUIRES, PRESERVES)
- Insert feasibility gate between context retrieval and code generation in both orchestrators
- Populate constraints during repository ingestion pipeline
- **Tests: ~400 planned**

### Phase 3: Distributed Execution (3–4 weeks)

- Implement DynamoDB-backed job graph with external DAG state (write-sharded GSI-1)
- Build dispatch service with SQS FIFO + composite MessageGroupId routing (`{tenant_id}#{priority_band}`)
- Implement agent pod heartbeat, checkpoint-on-termination, and restart-on-failure
- Deploy Karpenter NodePools for agent workers (spot + on-demand)
- Implement aggregation service for result collection and DAG stage transitions
- Neptune property-based tenant partitioning via `TenantIsolatedGraphService` wrapper
- Implement write-ahead staging graph model with batch validation and commit window
- Implement snapshot staleness detection with forced re-read semantics
- **Security gate: Validate Gate 2 controls**
- Load test at 50, 100, 200 agents

### Phase 4: Step Functions Orchestration + Production Hardening (3–4 weeks)

- Step Functions Express for within-stage fan-out (Map state)
- Step Functions Standard for cross-stage DAG transitions with `TimeoutSeconds` hard stop
- Per-tenant concurrency controls on Step Functions Express (prevent noisy-tenant exhaustion of 6,000 account-level concurrency limit). Proactively request quota increase for orchestration account.
- Spot interruption handling (NTH + agent idempotency)
- Bedrock rate limiting and TPM quota management (request RPM/TPM limit increase before Gate 2 load testing)
- Constitutional AI fail-closed enforcement at infrastructure level
- HITL rate limiting with priority stratification
- Server-side cost circuit breaker via execution timeouts and DynamoDB atomic cost counters
- Job-graph-level governance (cumulative impact tracking + semantic change clustering)
- Audit trail for autonomy preset transitions (AU-3 events to CloudTrail + EventBridge)
- UI component: Hyperscale Orchestration section in OrchestratorModeTab with Defense Mode gating
- **Security gate: Validate Gate 3 controls**
- Load test at 500, 1,000 agents

### Estimated Scope

| Component | Lines (est.) | Tests (est.) |
|---|---|---|
| Platform capability gating (UI + backend) | ~800 | ~100 |
| Configuration + admission control | ~600 | ~80 |
| Pre-generation feasibility gate | ~1,800 | ~400 |
| Mutation Site Analyzer | ~800 | ~120 |
| Architecture Constraint Registry | ~1,200 | ~150 |
| DynamoDB job graph + dispatch service (sharded GSI) | ~1,700 | ~220 |
| Aggregation service | ~600 | ~80 |
| Write-ahead staging graph + commit pipeline | ~1,200 | ~180 |
| Cumulative impact tracker + salami prevention | ~800 | ~120 |
| Step Functions orchestration + concurrency controls | ~900 | ~110 |
| Karpenter NodePool configs | ~200 | ~30 |
| Security controls (all gates) + audit trail | ~2,200 | ~340 |
| CloudWatch metrics + cost controls | ~500 | ~60 |
| **Total** | **~13,300** | **~1,990** |

## Consequences

### Benefits

- **Dual-market positioning**: Defense customers get maximum security (capped at 5 agents, Defense Parallel on roadmap); commercial customers get governance-bounded hyperscale
- **Configurable scale**: Commercial tenants choose parallelism ceiling (1–1,000+) based on edition, needs, budget, and risk tolerance
- **Safe autonomy at scale**: Write-ahead staging graph, cumulative impact tracking, and fail-closed Constitutional AI ensure governance invariants hold regardless of agent count
- **Cost-efficient**: Spot-first autoscaling, model routing, semantic caching, batch API, and server-side cost circuit breakers reduce per-agent cost with hard stops
- **Enterprise differentiator**: No competitor offers governance-bounded hyperscale agent orchestration
- **Monetization event**: Three-tier edition gating (Standard/Enterprise/Scale) creates clear upgrade path
- **GovCloud ready**: All services available in us-gov-west-1 with FIPS endpoints

### Risks

- **Emergent behavior**: 1,000 agents interacting through shared state will produce behaviors never tested at 10. Mitigated by graduated rollout gates (10→50→100→500→1,000) with automated security test suites at each gate, per-tenant kill-switches, and write-ahead staging isolation
- **Bedrock cost dominance**: LLM costs account for ~78% of per-job expense. Mitigated by model routing, caching, batch API, and server-side cost circuit breakers with Step Functions execution timeouts
- **Governance overhead**: Constitutional AI + CGE + feasibility gate at 1,000x scale may reduce effective throughput gain. Mitigated by batching critique evaluations and selective application (generation agents only, not read-only analysis agents)
- **Neptune connection pressure**: 1,000 concurrent Gremlin traversals require connection pooling at the `TenantIsolatedGraphService` level with bounded pool per tenant, not per-agent connections
- **Staging graph commit serialization**: Neptune's single-writer architecture serializes the commit phase when staged writes are promoted to the live graph. Mitigated by per-job staging size limits, commit window timeouts, and batched promotion
- **Snapshot staleness**: Long-running jobs may make decisions on outdated graph topology. Mitigated by staleness bound with forced re-read or job pause semantics

### Dependencies

| Dependency | ADR | Status |
|---|---|---|
| Autonomy Policy Framework | ADR-032 | Deployed |
| Agent Optimization (semantic caching) | ADR-029 | Deployed (enabled by default) |
| Constitutional AI Integration | ADR-063 | Deployed |
| Agent Capability Governance (4-tier) | ADR-066 | Deployed |
| Constraint Geometry Engine | ADR-081 | Phase 1 Deployed |
| Runtime Agent Security Platform | ADR-083 | Deployed |
| Agentic Identity Lifecycle Controls | ADR-086 | Deployed |

### Supersedes

None. Extends the existing MetaOrchestrator architecture without replacing it — in-process execution remains the default for ≤20 agents.

## Review Conditions

All four reviewers approved with conditions. The following conditions have been incorporated into this ADR:

| # | Condition | Source | Status |
|---|-----------|--------|--------|
| 1 | Neptune isolation must be property-based partitioning (Gremlin has no named graphs) | Architecture + Data Engineering | Incorporated |
| 2 | Orchestrator-level enforcement of integration mode (not API-only) | Cybersecurity | Incorporated |
| 3 | Per-job staging graph size ceiling + commit window time bound | Cybersecurity + Data Engineering | Incorporated |
| 4 | Shard DynamoDB GSI-1 on `{job_id}#{shard_id}` to prevent hot partitions | Data Engineering | Incorporated |
| 5 | Split SQS MessageGroupId to `{tenant_id}#{priority_band}` for throughput | Data Engineering | Incorporated |
| 6 | Snapshot staleness bound with forced re-read or pause semantics | Data Engineering | Incorporated |
| 7 | Server-side cost circuit breaker via execution timeouts, not UI polling | Architecture | Incorporated |
| 8 | Audit trail (AU-3) for autonomy preset transitions with approval chain | Cybersecurity | Incorporated |
| 9 | Threshold values tunable per preset, not hardcoded | Cybersecurity | Incorporated |
| 10 | UI simplification: tier-driven defaults, slider in Advanced expandable | Product | Incorporated |
| 11 | Gate to paid tier (Standard/Enterprise/Scale editions) | Product | Incorporated |
| 12 | Defense UX: "coming soon" not "unavailable"; add Defense Parallel to roadmap | Product | Incorporated |
| 13 | Step Functions Express: per-tenant concurrency controls + proactive quota increase | Architecture | Incorporated |

## References

- [MetaOrchestrator](../../src/agents/meta_orchestrator.py) — Current orchestrator implementation
- [System2Orchestrator](../../src/agents/agent_orchestrator.py) — Primary execution flow
- [Coder Agent](../../src/agents/coder_agent.py) — Code generation agent
- [Context Retrieval Service](../../src/services/context_retrieval_service.py) — Hybrid GraphRAG retrieval
- [Constraint Geometry Engine](../../src/services/constraint_geometry/engine.py) — 7-axis coherence scoring
- [Orchestrator Dispatcher](../../src/lambda/orchestrator_dispatcher.py) — Lambda→EKS dispatch
- [Agent Queue Service](../../src/services/agent_queue_service.py) — SQS queue routing
- [SettingsPage](../../frontend/src/components/SettingsPage.jsx) — Platform Settings (Integration Mode, tab routing)
- [OrchestratorModeTab](../../frontend/src/components/settings/OrchestratorModeTab.jsx) — Orchestrator deployment modes (hyperscale section target)
- [AutonomyPoliciesTab](../../frontend/src/components/settings/AutonomyPoliciesTab.jsx) — Autonomy policy presets
- [orchestratorApi](../../frontend/src/services/orchestratorApi.js) — Orchestrator settings API service
- [autonomyApi](../../frontend/src/services/autonomyApi.js) — Autonomy policy API service
- [Constitutional AI Failure Policy](../../src/services/constitutional_ai/failure_policy.py) — CritiqueFailurePolicy enum (fail-closed enforcement)
- [Neptune Graph Service](../../src/services/neptune_graph_service.py) — Gremlin client (TenantIsolatedGraphService wrapper target)
