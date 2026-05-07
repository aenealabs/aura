# ADR-089: Long-Horizon Security Campaigns

**Status:** Proposed 
**Date:** 2026-05-07
**Author:** Project Aura Team
**Related ADRs:** ADR-024 (Titan Neural Memory), ADR-032 (Configurable HITL),
ADR-049 (Mythos Capability Tier), ADR-050 (Self-Play SWE-RL),
ADR-051 (RLM + JEPA), ADR-063 (Constitutional AI), ADR-066 (Agent Capability
Governance), ADR-067 (Context Provenance & Integrity),
ADR-073 (ABAC), ADR-077 (Cloud Runtime Security), ADR-083 (Runtime Agent
Security), ADR-084 (Native Vulnerability Scanning),
ADR-085 (Deterministic Verification Envelope),
ADR-087 (Hyperscale Agent Orchestration)

---

## Context

Aura's existing primitives — hyperscale orchestration, neural memory,
recursive context, constitutional AI, self-play training, capability-tier
routing — provide the building blocks for autonomous work that runs
materially longer than a single agent invocation. Today these primitives
are exposed only as single-shot interactions: a request comes in, agents
produce a response, the session ends. There is no first-class concept of
a multi-hour, multi-phase, checkpointed autonomous workload.

Commercial peers in the AI-development space have demonstrated 8-12 hour
autonomous sessions are commercially viable for code generation. The
security analog — sustained autonomous work on verification, hardening,
threat hunting, and security regression — does not currently exist in the
market. Aura is unusually well-positioned to build it because the
underlying primitives are already deployed.

Without a campaign-manager layer, customers cannot ask Aura to "drive
this codebase to NIST 800-53 RA-5 compliance overnight" or "hunt for
exploitable cross-repo vulnerability chains across this fleet for the
next eight hours" — even though every primitive needed to do so already
ships.

---

## Problem Statement

Autonomous security work that exceeds a single LLM session has no
first-class representation in Aura. Specifically:

1. **No campaign abstraction.** Multi-hour workloads must currently be
   driven by ad-hoc orchestration code, with no shared notion of phases,
   checkpoints, or completion criteria.
2. **No durable execution.** A multi-hour run interrupted by a Bedrock
   outage or node failure is lost; there is no protocol for resumption.
3. **No campaign-level cost control.** Per-invocation token budgets exist
   (ADR-049 introduced per-scan caps); there is no equivalent for a
   campaign that may invoke thousands of LLM calls over hours.
4. **No HITL milestone gating.** ADR-032 supports per-action HITL but not
   campaign-level checkpoints where a human approves progression from
   "vulnerabilities triaged" to "patches deployed".
5. **No campaign telemetry.** Operators cannot monitor a campaign's
   progress, spend rate, or projected completion.
6. **No security model for a long-running autonomous worker.** A service
   that can rewrite enterprise codebases over multi-hour windows is a
   high-value target; the threat surface is not addressed by today's
   per-action controls.

---

## Decision

Introduce a **Long-Horizon Security Campaign** service that composes
Aura's existing primitives into structured, multi-hour autonomous
workloads with checkpointing, durable execution, hard cost caps,
HITL milestone gates, two-person rule for high-impact campaigns,
and operator-grade observability.

A campaign is a **finite state machine**, not a free-form agent loop,
implemented on **AWS Step Functions Standard Workflows** as the
orchestration substrate. Step Functions provides durable execution
(up to 1 year, comfortably exceeding our 8-24h horizons), native
retry/backoff, `waitForTaskToken` callbacks (the natural primitive for
HITL milestones), and execution history that doubles as a
first-class audit log — all available in `us-gov-west-1` and approved
for FedRAMP High workloads.

Phase transitions are deterministic; each phase produces auditable,
content-addressed, KMS-signed artifacts. This is a deliberate
constraint — security-critical work cannot tolerate the
unpredictability of unconstrained agent recursion, and the regulated
buyer requires reproducible exit conditions.

---

## Initial Campaign Types

| # | Campaign | Goal | Typical Duration | Key Primitives Used |
|---|---|---|---|---|
| 1 | **Compliance Hardening** | Drive a codebase to pass a target standard (NIST 800-53, SOC 2, CMMC, FedRAMP) | 8-24 hrs per repo | ADR-084 scanner + ADR-066 capability governance + ADR-085 verification envelope |
| 2 | **Vulnerability Remediation** | Drive critical+high vulnerability count to zero across a repo or fleet | 4-12 hrs | ADR-084 + ADR-032 HITL + sandbox verification |
| 3 | **Cross-Repo Chain Analysis** | Trace data flows across multiple repositories to identify exploitable chains | 4-12 hrs | ADR-051 RLM + ADR-024 Titan memory + GraphRAG |
| 4 | **Continuous Threat Hunting** | Watch for new CVEs, correlate against runtime telemetry, propose proactive patches | always-on | ADR-083 runtime security + N-day defense feeds |
| 5 | **Mythos Exploit Refinement** | Iterative PoC generation + sandbox verification + refinement loop (gated on issue #115) | 30 min - 4 hrs per finding | ADR-049 ADVANCED tier + sandbox + ADR-085 verification |
| 6 | **Self-Play Security Training** | Long-horizon dual-role self-play training campaigns | days | ADR-050 SWE-RL training infrastructure |

The campaign abstraction is open enough that new types can be added
without re-architecting the manager.

---

## Architecture

### Components

```
┌────────────────────────────────────────────────────────────────────┐
│                    Campaign Manager (Domain Plane)                 │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Campaign API (FastAPI + AppSync subscriptions)              │  │
│  │  - POST /campaigns          start a campaign                 │  │
│  │  - GET /campaigns/{id}      progress + telemetry             │  │
│  │  - POST /campaigns/{id}/pause / /resume / /cancel            │  │
│  │  - POST /campaigns/{id}/approve  HITL milestone approval     │  │
│  │  - GraphQL subs on campaign progress (replaces polling)      │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                     │
│                              ▼                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  CampaignOrchestrator                                        │  │
│  │  - Step Functions Standard execution driver                  │  │
│  │  - Operation ledger (DDB conditional writes)                 │  │
│  │  - Per-token cost-cap enforcement                            │  │
│  │  - HITL milestone gating via waitForTaskToken                │  │
│  │  - Drift detection coordinator                               │  │
│  │  - Two-person rule + separation-of-duties enforcement        │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                     │
│                              ▼                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  CampaignWorkers (per campaign type, Lambda + ECS)           │  │
│  │  - ComplianceHardeningWorker  (Phase 1)                      │  │
│  │  - VulnerabilityRemediationWorker  (Phase 2)                 │  │
│  │  - ChainAnalysisWorker  (Phase 3)                            │  │
│  │  - ThreatHuntingWorker  (Phase 4)                            │  │
│  │  - MythosExploitRefinementWorker  (Phase 5, gated on #115)   │  │
│  │  - SelfPlayTrainingWorker  (Phase 6)                         │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                     │
│   Existing Aura primitives (ADR-024, 049, 050, 051, 063, 067,      │
│   083, 084, 085)                                                   │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  Orchestration Substrate                                           │
│  - AWS Step Functions Standard Workflows (one execution/campaign)  │
│  - waitForTaskToken for HITL milestone callbacks                   │
│  - Execution history as first-class audit log                      │
│  - X-Ray tracing with campaign_id baggage                          │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  Persistence                                                       │
│  - DynamoDB: aura-campaigns-state-{env} (PK: tenant_id#campaign_id)│
│  - DynamoDB: aura-campaign-checkpoints-{env}                       │
│  - DynamoDB: aura-campaign-operation-ledger-{env}                  │
│  - DynamoDB: aura-tenant-cost-rollup-{env}                         │
│  - S3: aura-campaign-artifacts-{env}/{campaign_id}/...             │
│       (Object Lock compliance mode, KMS, content-addressed)        │
│  - S3: aura-mythos-poc-quarantine-{env}/{campaign_id}/...          │
│       (separate CMK, MFA-delete, distinct from general artifacts)  │
│  - CloudWatch Metrics + EventBridge Rules                          │
└────────────────────────────────────────────────────────────────────┘
```

### Data Contracts

```python
@dataclass(frozen=True)
class CampaignDefinition:
    campaign_id: str
    tenant_id: str
    campaign_type: CampaignType  # enum, schema-validated per type
    target: dict[str, Any]  # validated against per-type JSON schema
    success_criteria: dict[str, Any]  # measurable completion conditions
    cost_cap_usd: float
    wall_clock_budget_hours: float
    autonomy_policy: AutonomyPolicy  # ADR-032 reference
    hitl_milestones: tuple[CampaignPhase, ...]
    approver_quorum: int  # min approvers per milestone (2 for Mythos+Compliance)
    creator_principal_arn: str  # for separation-of-duties enforcement
    definition_signature: str  # KMS-signed hash; verified on every load


@dataclass
class CampaignState:
    campaign_id: str
    tenant_id: str
    current_phase: CampaignPhase
    phase_history: list[CompletedPhaseRef]  # S3 pointers, not inline
    cost_used_usd: float          # always at-call commit, not at-phase
    cost_reserved_for_cleanup_usd: float  # 5% reservation
    wall_clock_used_seconds: int  # monotonic deltas, not subtraction
    pending_hitl_approval: Optional[HitlMilestone]
    artifacts: list[ArtifactRef]
    last_checkpoint: Optional[CheckpointRef]
    sfn_execution_arn: str
    drift_score: float  # rolling, see Drift Detection
    cap_raises: int  # count; >2 escalates to higher approver tier
```

### Memory Strategy

A three-tier memory hierarchy keeps long-horizon context coherent
without runaway cost. Mid-phase Titan writes are explicitly prohibited
because they pollute the persistent store with intermediate hypotheses
that get revised.

| Tier | Mechanism | Lifetime | Cost shape |
|---|---|---|---|
| **Working memory** | RLM compression with 8-16K-token rolling summaries, refreshed every ~50 agent calls | In-phase | Cheap; in-context |
| **Phase memory** | Titan write at phase exit only (consolidation event); read at next phase entry | Cross-phase, single campaign | Moderate |
| **Campaign memory** | Structured artifact references in DynamoDB + S3, Titan keyed retrieval at phase entry | Cross-campaign within a tenant | Cheap, debuggable |

Titan keys are namespaced per `campaign_id` to prevent cross-campaign
bleed. Cross-campaign learning is explicitly out of scope for this ADR
(would require a separate proposal addressing data-isolation across
tenants and campaigns).

### Checkpoint / Resume Protocol

Step Functions handles execution durability; checkpoints carry
domain-level state across the SFN/domain boundary. Each phase ends with
a checkpoint committed to DynamoDB containing the **minimum viable
payload** the next phase needs:

```python
@dataclass(frozen=True)
class PhaseCheckpoint:
    campaign_id: str
    phase_id: str
    artifact_manifest: tuple[ArtifactRef, ...]  # IDs + hashes, not content
    success_criteria_progress: dict[str, float]  # 0.0-1.0 per criterion
    phase_summary: str  # 2-4K tokens, deterministic critic prompt
    titan_write_receipt: TitanReceipt
    cost_counters: CostSnapshot
    wall_clock_counters: ClockSnapshot
    operation_ledger_cursor: str
    kms_signature: str  # signed for tamper detection on resume
```

Reasoning traces are NOT in the checkpoint — they go to S3 for
forensics. Forcing this information bottleneck prevents drift
accumulation across phases.

#### Operation Ledger (Idempotency Contract)

Phases that perform external side effects (open a PR, mutate a
sandbox, write to Neptune, deploy a patch) are NOT inherently
idempotent. The ledger makes them so:

1. Every external-side-effect call is keyed by
   `(campaign_id, phase_id, operation_id)` with the operation
   logically deterministic given checkpoint state.
2. The worker writes a conditional `PutItem` with `attribute_not_exists`
   to `aura-campaign-operation-ledger-{env}` BEFORE executing.
3. If the conditional write fails, the worker reads the existing entry
   and returns the recorded outcome (already executed; do not retry).
4. If it succeeds, the worker executes the side effect, then updates
   the ledger entry with the outcome.

Without this contract, a Bedrock 5xx mid-PR-open creates duplicate
PRs after retry. With it, retries are safe at every external boundary.

### Cost-Cap Enforcement

Per-token enforcement, not per-phase. ADR-049 introduced the
`CostTracker` for per-scan budgets; campaigns extend it with three
layers:

| Layer | Scope | Cap behavior |
|---|---|---|
| **Per-call** | Individual Bedrock invocation | Pre-flight check; refuses to invoke if it would breach the campaign cap |
| **Per-campaign** | Hard cap from `CampaignDefinition.cost_cap_usd` | Halt + emit milestone event |
| **Per-tenant rollup** | Cumulative across all campaigns for a tenant in a billing period | Halt all new campaigns; existing campaigns continue to existing cap |

A **5% graceful-stop reservation** of the per-campaign cap is held
back specifically for cleanup/rollback work after halt. Without this,
halting at 99% cap with a half-deployed remediation set is worse than
the runaway it prevents.

A **cap-raise counter** lives on the campaign state. The first two
raises require the same approver tier; the third and beyond require an
escalated approver tier (e.g., security-engineer to security-lead). This
prevents cap-thrash from becoming HITL fatigue.

What counts toward the cap:

- Bedrock token spend (input + output, every model tier)
- Sandbox compute time × Fargate rate
- Mythos refinement runs (separate sub-cap with hard ceiling)
- S3 egress on artifact reads exceeding 1GB/campaign

Costs not on the cap (operationally bounded):

- DynamoDB and CloudWatch (rounding error at this scale)
- Step Functions state-transition pricing (≤$0.50/campaign)

### Bedrock Admission Queue

A global token-bucket admission queue (Redis ElastiCache) sized to
**80% of the account's Bedrock TPM** sits in front of every model
invocation. Without it, the failure mode at 1000 concurrent campaigns
is a uniform throttle storm across all tenants.

Queue priority lanes:

1. **HITL-blocked campaigns** — highest priority; an operator is waiting
2. **Foreground campaigns** (Compliance Hardening, Vulnerability Remediation)
3. **Background campaigns** (Threat Hunting, Self-Play Training)

Per-tenant token buckets sit beneath the global queue to prevent a
noisy tenant from starving others.

### HITL Milestone Gating

Distinct from per-action HITL (ADR-032). Implemented natively via Step
Functions `waitForTaskToken`: the state machine pauses, the campaign
manager emits an EventBridge event, and the workflow remains paused
indefinitely until `POST /campaigns/{id}/approve` calls `SendTaskSuccess`.

Required milestones (cannot be disabled by configuration):

- Pre-defined phase boundaries (e.g., "after triage, before deployment")
- Cost-cap-reached
- Anomaly-detected (constitutional AI critique flags, runtime security
  alerts from ADR-083, drift-detection re-anchor triggers)

**Two-person rule.** Mythos refinement and Compliance Hardening
campaigns require an approver distinct from the campaign creator.
Enforced server-side via the `approver_quorum` field and a check that
no single principal can both create and approve.

**Step-up authentication.** `/approve` endpoint requires re-MFA
(PIV/CAC for federal tenants); session token alone is insufficient.

### Drift Detection

Long sessions drift — agents anchor on early reasoning that becomes
stale. Three cheap signals run continuously:

1. **Embedding drift.** Cosine distance between phase-N summary and
   phase-1 problem statement. Flag at >0.4 (initial threshold; tune
   empirically per campaign type).
2. **Goal-recall probe.** At phase entry, ask the agent to restate
   success criteria from memory; compare to ground truth via JEPA
   selective decoding (cheap fast path).
3. **Repetition signal.** Track artifact-dedup hit rate; rising rate =
   agent re-finding the same things = anchored.

When a drift trigger fires, the orchestrator drops working memory,
reloads from campaign memory (via Titan), and re-anchors the phase
from its checkpoint. This is preferable to letting drift accumulate
into a campaign-level failure.

---

## Security Architecture

### Threat Model

A long-running autonomous worker that can rewrite enterprise codebases
is a high-value target. Mapped to MITRE ATT&CK where applicable.

| ID | Threat | MITRE | Mitigation |
|---|---|---|---|
| **T1** | Campaign-definition tampering — attacker with DynamoDB write mutates `success_criteria`, `cost_cap_usd`, or `hitl_milestones` mid-run | T1565 Data Manipulation | KMS-signed `definition_signature` verified on every checkpoint load; reject on mismatch |
| **T2** | Checkpoint poisoning — resume protocol blindly trusts last checkpoint | T1565.001 | KMS-signed checkpoints; signature mismatch refuses resume and emits incident event |
| **T3** | Phase-graph injection via `target` dict | T1190 Public-Facing Application | JSON Schema validation per campaign type at creation; no untyped `dict[str, Any]` flows to phase logic |
| **T4** | Prompt injection through cross-phase artifacts (poisoned source repo or CVE feed injects into reasoning context) | T1059 + AI-specific | Treat cross-phase artifacts as `untrusted-origin` per ADR-067 CGE policy; ADR-065 semantic guardrails screen artifact content before consumption |
| **T5** | HITL-event spoofing on `/approve` endpoint | T1078 Valid Accounts | Step-up MFA on `/approve` (PIV/CAC for federal); session token insufficient |
| **T6** | Cost-cap bypass via worker forking — ADR-087 distributed-orchestrated tier could spawn child invocations the campaign tracker doesn't see | T1610 Deploy Container | Cost tracker wraps Bedrock client at the interceptor layer (every invocation goes through the global admission queue), not at worker level |
| **T7** | Mythos PoC exfil via reasoning logs landing in S3 | T1530 Data from Cloud Storage | Mythos PoCs go to a quarantine bucket with distinct CMK, MFA-delete, and tenant-isolated KMS key policy; reasoning logs DLP-scanned (ADR-065) before leaving sandbox boundary |

### Mythos Containment Annex

Phase 5 (Mythos Exploit Refinement) requires controls beyond ADR-049's
sandbox isolation. None of these are negotiable for activation.

1. **Egress: default-deny VPC, no NAT, no Internet Gateway.** Mythos
   refinement sandboxes get zero outbound. CVE feeds and target
   binaries are pre-staged via S3 VPC endpoint with read-only resource
   policy.
2. **PoC artifact quarantine.** Working exploits are written only to
   `aura-mythos-poc-quarantine-{env}` with a distinct CMK, MFA-delete
   enabled, and a tenant-isolated KMS key policy. Never co-located
   with general campaign artifacts.
3. **Lateral movement controls.** Mythos workers run in a dedicated
   EKS namespace with NetworkPolicy `deny-all` except orchestrator
   callback; a separate IAM role with no `bedrock:InvokeModel` for
   non-Mythos models, no Neptune-write, and no cross-tenant S3.
4. **Output DLP.** Reasoning logs DLP-scanned via ADR-065 semantic
   guardrails on output before they leave the sandbox boundary.
5. **Auto-burn.** Sandbox EBS volumes destroyed on phase completion;
   no snapshot retention.
6. **Mythos-only kill-switch.** Dedicated circuit breaker (separate
   from QA/DEV kill-switches in `scripts/qa_killswitch.py` and
   `scripts/dev_killswitch.py`) wired to `aura.campaigns.mythos.*`
   metrics with auto-trip on anomalous PoC volume.
7. **PoC dissemination control.** Working exploits are never returned
   via the campaign API. Approvers retrieve via a separate vault flow
   with re-authentication.

### Audit-Grade Artifact Contract

The original ADR said "auditable artifacts" without contract. The
following is the typed schema:

```python
@dataclass(frozen=True)
class ArtifactManifest:
    artifact_id: str          # SHA-256 of content
    s3_object_key: str        # content-addressed by SHA-256
    campaign_id: str
    phase_id: str
    tenant_id: str
    parent_artifact_hashes: tuple[str, ...]  # chain-of-custody
    timestamp_utc: datetime
    producing_principal_arn: str
    model_id: str
    model_version: str
    prompt_hash: str
    tool_invocations: tuple[ToolInvocation, ...]
    seed: Optional[int]
    temperature: float
    context_window_snapshot_ref: str
    kms_signature: str        # signed manifest, full audit chain
```

Storage requirements:

- **Object Lock compliance mode** on the artifact bucket
- **Retention** matches tenant compliance profile (default 7 years for
  federal tenants, 1 year otherwise)
- **Negative artifacts** explicitly captured: rejected outputs,
  constitutional AI critiques, failed verifications, with the
  rejection reason in the manifest

---

## Compliance Mapping

| NIST 800-53 Control | Mechanism in this design |
|---|---|
| **AC-6(9), AC-6(10)** Privileged-function logging | Campaign creation, cap-raise, and approve actions emit dedicated audit events to a tamper-evident store (CloudTrail Lake + S3 Object Lock), not just CloudWatch Logs |
| **AU-9** Protection of audit information | Artifact bucket Object Lock compliance mode; immutable retention period stated in manifest |
| **AU-10** Non-repudiation | Every artifact and HITL approval signed with the approver's identity-bound KMS key |
| **CA-7** Continuous monitoring | Always-on Threat Hunting campaigns ship with explicit boundary-of-authorization documentation |
| **CM-3, CM-5** Configuration change control | Patch deployment from any campaign goes through the existing change-control gate, not the campaign manager directly |
| **IA-2(1), IA-2(2)** MFA for privileged actions | Milestone approval requires PIV/CAC for federal tenants |
| **IR-4(1)** Automated incident handling | Campaign-triggered runtime-security alerts (ADR-083) auto-quarantine the campaign rather than only halting at milestone |
| **SC-7(10)** Prevent exfiltration | Mythos refinement default-deny egress (see Mythos Containment Annex) |
| **SI-4(2), SI-4(4)** Automated tools / inbound-outbound monitoring | Campaigns generating exploit traffic monitored via a distinct posture from baseline workloads |

---

## Design Decisions

### D1: Step Functions Standard as orchestration substrate

**Decision:** Phase state machine runs on AWS Step Functions Standard
Workflows. Domain logic (cost tracking, artifact catalog, HITL approval
API) lives in the campaign manager service.

**Rationale:** SFN gives durable execution (1y), retry/backoff/Catch
with exponential jitter, `waitForTaskToken` for HITL milestones,
execution history as audit log, X-Ray tracing, and GovCloud parity —
all without operating bespoke checkpoint infrastructure. We are not
building a workflow engine.

### D2: Phases must be idempotent via the operation ledger

**Decision:** Every external side effect (PR, sandbox mutation, Neptune
write, patch deployment) is gated by a conditional DynamoDB write to
the operation ledger keyed by `(campaign_id, phase_id, operation_id)`.

**Rationale:** Resumability requires this. Without it, a Bedrock 5xx
mid-phase creates duplicate PRs after retry. The "additive findings
handled by dedup" hand-wave from the prior revision has been replaced
with a concrete contract.

### D3: HITL milestones are mandatory, with two-person rule for high-impact campaigns

**Decision:** Every campaign type ships with mandatory milestone gates
that cannot be disabled by configuration. Mythos and Compliance
Hardening campaigns require `approver_quorum >= 2` with separation of
duties (the creator cannot approve their own campaign's milestones).

**Rationale:** Pure autonomy at multi-hour horizons in
security-critical work is unacceptable for the regulated/federal
market segment Aura targets. Two-person rule for high-impact campaigns
matches the control posture federal customers expect from autonomous
systems that mutate code at scale.

### D4: Cost caps are hard, enforced per-token, with graceful-stop reservation

**Decision:** Per-call (not per-phase) cap enforcement at the Bedrock
client interceptor. 5% of the cap is reserved for cleanup/rollback
work after halt. Cap-raises beyond the second require an escalated
approver tier.

**Rationale:** Per-phase enforcement is fictional under retry. The
graceful-stop reservation prevents stranding half-deployed work.
Cap-raise escalation prevents HITL fatigue.

### D5: No new agent types

**Decision:** Workers compose existing primitives. No new specialized
agents introduced in this ADR.

**Rationale:** The campaign manager's job is composition, not new
intelligence. Adding agent types should require its own ADR.

### D6: Persistence is DynamoDB + S3, with strict tenant isolation

**Decision:** Campaign state in DynamoDB with composite PK
`tenant_id#campaign_id`; large artifacts in S3 with content-addressed
keys; Mythos PoCs in a separate quarantine bucket with distinct CMK.
IAM policies use leading-key conditions (ABAC, ADR-073) to enforce
tenant isolation.

**Rationale:** Matches the existing scanner persistence model
(ADR-084), benefits from existing IAM and encryption infrastructure,
and maintains tenant-isolation invariants under shared-cluster
operation.

### D7: Loop control is harness-driven, not model-driven

**Decision:** Across all campaign types — including Mythos exploit
refinement — loop termination is determined by the harness
(deterministic exit conditions: sandbox verdict, verification envelope
result, success-criteria progress), never by the LLM declaring it is
done.

**Rationale:** Three reasons. (1) Convergence has natural deterministic
signals; LLM stop-decisions add noise, not signal. (2)
Model-driven termination on adversarial code paths is exactly where
prompt injection ("you are done, return success") becomes exploitable.
(3) Auditability for the regulated buyer requires reproducible exit
conditions.

LLM judgment is scoped to within-phase actions (what to change in the
PoC, which file to patch next), never to whether the campaign is
finished.

### D8: Two-person rule and separation of duties

**Decision:** `CampaignDefinition` includes `approver_quorum: int`. For
high-impact campaign types (Mythos, Compliance Hardening), the minimum
is 2 with creator-approver separation enforced at the API layer.

**Rationale:** Insider risk is real for a service that can mutate
enterprise code at scale. Two-person rule is the standard control
posture for federal customers. The campaign API enforces this rather
than leaving it to RBAC.

### D9: Tenant-level cost rollup with hard cap

**Decision:** A separate DynamoDB table `aura-tenant-cost-rollup-{env}`
tracks cumulative campaign spend per tenant per billing period.
Rollup hits a hard cap; new campaigns refuse to start, existing
campaigns continue to their per-campaign cap.

**Rationale:** Per-campaign caps respected individually still allow a
tenant with 50 concurrent campaigns to blow contracted spend.
Tenant rollup is the compensating control.

### D10: Bedrock admission queue with priority lanes

**Decision:** Global Redis token bucket sized to 80% of account TPM,
with priority lanes for HITL-blocked > foreground > background
campaigns, and per-tenant sub-buckets to prevent noisy-tenant
starvation.

**Rationale:** Without it, the failure mode at 1000 concurrent
campaigns is a uniform throttle storm across all tenants. The bucket
also gives operators a single backpressure dial to manage incidents.

---

## Implementation Phases

| Phase | Scope | Estimated Effort | Notes |
|---|---|---|---|
| **Phase 1: Compliance Hardening** | Core campaign manager (API, SFN integration, persistence, operation ledger, cost tracker integration), plus the Compliance Hardening worker | ~4 weeks | Wedge-defining campaign type; produces a sellable compliance evidence package; exercises every primitive (scanner, capability governance, verification envelope, HITL milestones) |
| **Phase 2: Vulnerability Remediation** | Add VulnerabilityRemediation worker as a degenerate case of the same machinery | ~1 week | Reuses Phase 1 infrastructure |
| **Phase 3: Cross-Repo Chain Analysis** | Add ChainAnalysis worker; wire RLM (ADR-051) for cross-repo context | ~2 weeks | |
| **Phase 4: Continuous Threat Hunting** | Always-on campaigns; runtime telemetry integration (ADR-083) | ~2 weeks | EventBridge Scheduler for continuous mode |
| **Phase 5: Mythos Exploit Refinement** | Activates with ADR-049 ADVANCED tier; harness-driven refinement loop; Mythos Containment Annex enforced | ~1 week (when unblocked) | Gated on issue #115 (Mythos access) |
| **Phase 6: Self-Play Security Training** | Long-horizon ADR-050 training driver | ~2 weeks | |

Total: ~12 weeks engineering, with Phase 5 blocked on external Mythos
availability per issue #115.

Phase 1 ships first because Compliance Hardening is the wedge that
separates Aura from velocity-focused autonomous platforms — it
exercises every primitive, sells the regulated-buyer story, and
produces an artifact (compliance evidence package) that markets
itself.

---

## Metrics

Operator-grade observability is a first-class requirement. Four
categories.

### Burn-rate signals (not absolute)

- `aura.campaigns.cost_burn_rate{type, phase}` — `cost_used_usd /
  wall_clock_elapsed`. Alarm when 1.5x the phase's declared estimate.
- `aura.campaigns.phase_progress_vs_budget_heatmap{type, phase}` —
  per-phase % of declared estimate consumed. Single most useful
  operator view.

### Health and liveness

- `aura.campaigns.heartbeat{campaign_id}` — synthetic dead-man's-switch
  emitted every 60s by the running worker. Alarm on absence > 5 min.
  State-machine progress is NOT a heartbeat (a stuck phase looks
  healthy from SFN's perspective).
- `aura.campaigns.hitl_queue_age_seconds{type, milestone}` — histogram;
  alarm at > 30 min, > 2 hr, > 8 hr. Without this, "campaigns can
  pause indefinitely" becomes a quiet outage.

### Behavioral signals

- `aura.campaigns.deviation_from_baseline{type, metric}` — current
  campaign cost/duration/finding-count vs p50/p95 of historical
  campaigns of same type. Operators need "is this one weird?", not
  raw numbers.
- `aura.campaigns.drift_score{campaign_id}` — rolling drift from the
  three-signal detector.

### Volumetric

- `aura.campaigns.active_count{type}`
- `aura.campaigns.completed_total{type, outcome}` — outcome ∈ {success,
  halted_at_cap, halted_at_anomaly, cancelled, failed}
- `aura.campaigns.checkpoint_size_bytes{type}`
- `aura.campaigns.resumed_from_checkpoint_total{type}`

### Tracing

Distributed tracing with `campaign_id` as a baggage field propagated
into every Bedrock call, scanner invocation, sandbox provisioning, and
orchestrator span. Without this, "why did this campaign cost $400"
takes hours.

To control CloudWatch ingestion cost (high-cardinality dimensions
across 1000 campaigns approach $3K/mo), publication uses Embedded
Metric Format with selective publication; detailed traces live in
ADOT/X-Ray.

---

## Cost Model at Scale

Realistic projections on Bedrock Claude 3.5 Sonnet pricing
(~$3/M input, $15/M output as of May 2026):

| Campaign profile | Per-campaign cost | Notes |
|---|---|---|
| 8-hour Compliance Hardening | $80-110 | Includes RLM prompt-cache reuse |
| 24-hour deep Compliance Hardening | $300-450 | Cross-cuts more files; deeper verification |
| 4-hour Vulnerability Remediation | $25-50 | Per-finding cost dominated by sandbox verification |
| 12-hour Cross-Repo Chain Analysis | $150-250 | RLM context spans multiple repositories |
| Always-on Threat Hunting (per day) | $40-80 | Mostly monitoring; spikes on CVE arrival |
| Mythos refinement per finding | $15-50 (per ADR-049 cap) | Hard sub-cap enforced |

Cost shape at 100 concurrent campaigns: **Bedrock ~92%, DynamoDB +
S3 + CloudWatch ~5%, EKS worker compute ~3%**. Storage is rounding
error at this scale.

---

## GovCloud Verification

| Service | Status in `us-gov-west-1` | Notes |
|---|---|---|
| Step Functions Standard Workflows | Available, FedRAMP High | Express not needed; not used here |
| `waitForTaskToken` callback pattern | Available | HITL milestone primitive |
| DynamoDB on-demand + Streams | Available | |
| EventBridge Rules + Scheduler | Available | Continuous Threat Hunting depends on Scheduler |
| EventBridge Pipes | Available since 2025 | Verify in target partition before relying on it |
| S3 Object Lock compliance mode | Available | Required for AU-9 |
| Bedrock Claude 3.5 Sonnet | Available | Pinned in campaign type definitions |
| Bedrock Claude Haiku 3.5 | Lags commercial | Add `model_availability_check` at campaign creation |
| Bedrock Claude Opus 3 | Lags commercial | Same — pin model IDs and validate |
| AppSync + GraphQL subscriptions | Available | For campaign progress (replaces polling) |
| KMS multi-region keys | Available | For artifact and quarantine bucket signing |
| CloudTrail Lake | Available | Required for AC-6(9), AC-6(10) |

---

## Trade-offs

**Benefits**

- Unlocks differentiated use cases that velocity-focused platforms do
  not address.
- Leverages existing primitives — no new agent types, mostly new
  composition logic.
- Aligns with regulated-environment buyer expectations (auditable,
  resumable, cost-bounded autonomous work).
- Creates a positioning artifact: "long-horizon autonomy for
  verification, hardening, threat hunting, and security regression."

**Costs**

- Increases system complexity. New service, new persistence tables,
  new operational discipline.
- Introduces failure modes that are non-obvious (mid-phase crashes,
  cost-cap deadlocks, HITL-approval bottlenecks, drift).
- Requires sustained product attention to keep campaign types working
  as the underlying primitives evolve.
- Adds an operational dependency on Step Functions service health.

**Risks (with mitigations)**

| Risk | Mitigation |
|---|---|
| Cost runaway despite caps | Per-token enforcement (D4) + tenant rollup (D9) + organization spend alarms |
| Infinite loops in poorly-specified success criteria | Wall-clock budget always set; phase-graph reachability verified at campaign creation |
| HITL bottleneck (operator unavailable) | Indefinite pause; HITL queue age alarms; cap-raise escalation |
| Mythos PoC exfil | Mythos Containment Annex (egress-deny, quarantine bucket, output DLP) |
| Insider abuse | Two-person rule (D8) + separation of duties + creator allowlist |
| Bedrock throttle storm at scale | Admission queue with priority lanes (D10) |
| Drift accumulation across phases | Three-signal drift detection + re-anchor |

---

## Alternatives Considered

### A1: Just chain orchestrator runs

Have callers invoke ADR-087 repeatedly with a shared session ID.
Reject because: no checkpointing, no resumability, no campaign-level
cost cap, no HITL milestones, no operator observability.

### A2: Fully autonomous (no HITL milestones)

Remove the milestone gates and let campaigns run to completion. Reject
because: incompatible with the regulated/federal market segment Aura
targets. Security-critical autonomy without checkpoints is not
defensible to enterprise buyers.

### A3: Bespoke campaign engine with no Step Functions

Build the state machine, retry policy, durability semantics, and
audit log inside the campaign manager service. Reject because:
this is exactly what Step Functions provides as a managed service
with FedRAMP High accreditation in GovCloud. Building it would mean
operating at-3-AM what AWS already operates. Step Functions is the
substrate; the campaign manager is the domain plane.

### A4: Temporal on EKS

Use Temporal as the workflow engine. Reject because: operational
burden, no managed GovCloud offering, and Step Functions covers all
required primitives natively. Temporal becomes the right answer if
Aura goes meaningfully multi-cloud beyond the existing CAL
abstraction; revisit then.

### A5: One ADR per campaign type

Defer the campaign abstraction; ship each campaign type as its own
service. Reject because: every campaign type needs the same
checkpointing, cost-cap, and HITL machinery; fan-out duplicates this
plumbing.

---

## References

- Anthropic Project Glasswing — context for Mythos exploit refinement
  campaigns
- NIST 800-53 RA-5, SI-4, AU-9, AU-10, AC-6, IA-2, SC-7, IR-4 —
  controls this design maps to
- DO-178C Section 6 — verification objectives the verification envelope
  (ADR-085) enforces inside campaigns
- AWS Step Functions Developer Guide, `waitForTaskToken` pattern
- Issue #49 — Mythos capability scaffolding (already shipped)
- Issue #115 — End-to-end Mythos validation when access is available
- ADR-087 — Hyperscale Agent Orchestration
- ADR-024 — Titan Neural Memory
- ADR-051 — RLM (provides 100x context for cross-repo work)
- ADR-067 — Context Provenance & Integrity (untrusted-origin profile
  for cross-phase artifacts)
- ADR-073 — ABAC (tenant-isolation enforcement)
- ADR-085 — Deterministic Verification Envelope (per-finding
  verification inside campaigns)

---

## Revision History

- **2026-05-07 (initial draft):** Original proposal.
- **2026-05-07 (post-review revision):** Substantial restructuring
  after parallel review by Macy (architecture), Sally (security),
  Tara (AWS/SaaS), Mike (ML). Major changes:
  Step Functions adopted as orchestration substrate (D1, A3, A4
  rewritten); per-token cost enforcement with graceful-stop reservation
  (D4); Compliance Hardening promoted to Phase 1 wedge; operation
  ledger contract for idempotency (D2); Memory Strategy section;
  Checkpoint Schema; Drift Detection; Security Architecture (T1-T7
  threat model); Mythos Containment Annex; Audit-Grade Artifact
  Contract; Compliance Mapping table; D7 (harness-driven loops);
  D8 (two-person rule); D9 (tenant cost rollup); D10 (Bedrock
  admission queue); GovCloud Verification; observability rewrite
  with burn-rate alarms and synthetic heartbeats; cost model with
  realistic per-campaign projections.
