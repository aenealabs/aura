# ADR-086: Agentic Identity Lifecycle Controls

## Status

Proposed

## Date

2026-04-04

## Reviews

| Reviewer | Role | Date | Verdict |
|----------|------|------|---------|
| Pending | Cybersecurity Analyst | - | - |
| Pending | AI Product Manager | - | - |
| Pending | Senior Systems Architect | - | - |
| Pending | Test Architect | - | - |

### Review Summary

Closes the three agentic identity gaps identified in the RSAC 2026 vendor analysis (Cisco, CrowdStrike, Microsoft, Palo Alto, Cato). Extends ADR-066, ADR-071, ADR-083, ADR-042, and ADR-073 with lifecycle controls that no surveyed vendor ships as a production capability.

## Context

### The Three Gaps

The RSAC 2026 analysis identified three failure modes in agent security that none of the five dominant vendors close:

1. **Self-modification.** An authorized agent modifies the controls governing its own future actions. Every credential check passes because the action is authorized. Cisco's MCP gateway watches tool-call patterns but does not monitor direct policy modifications. CrowdStrike's process-tree lineage could detect a policy file change but ships no dedicated rule. Microsoft's Defender adjusts policies reactively during active attacks, not proactively. Palo Alto red-teams before deployment, not during runtime.

2. **Agent-to-agent delegation.** When agent A hands work to agent B, no runtime trust verification ties the delegation back to a human principal. OAuth handles user-to-service. SAML handles federated human identity. MCP handles model-to-tool. None covers agent-to-agent delegation with depth-bounded, capability-subset-narrowing trust assertions. The 100-agent swarm incident cited by Cato demonstrated that delegation without human approval is already being exploited.

3. **Ghost agents.** Abandoned pilots, owner departures, expired justifications, and deprecated workflows leave agents running with live credentials and no offboarding. All five vendors discover running agents. None verifies **zero residual credentials** after decommission.

### Aura's Current Coverage

| Gap | Current state in Aura |
|-----|------------------------|
| Self-modification | Partial. `graph_analyzer.py` (ADR-071) flags `modify_iam_policy` + `access_secrets` as a toxic combination. `baselines/` (ADR-083) provides drift detection. No dedicated sentinel for the self-governance edge case. |
| Delegation | Partial. `graph_analyzer.detect_escalation_paths()` walks delegation chains after the fact. `a2a_gateway.py` enforces protocol. No inline trust primitive at invocation time. |
| Ghost agents | Open. `agent_discovery.py` and `shadow_detector.py` find running agents. No decommission verifier. This is the only gap where Aura is at parity with the vendor field rather than ahead. |

### Strategic Framing

The vendor field is converging on registration and runtime visibility. Aura has both (ADR-066, ADR-083). The defensible differentiation is lifecycle controls — the primitives that activate **after** an agent is registered and visible: preventing self-governance drift, signing delegation chains, and proving that decommission actually happened. These are the "Monday-morning" items in the RSAC analysis that have no product fix today.

## Decision

Implement three lifecycle control services as a single coordinated closure:

1. **Self-Modification Sentinel** — dedicated detector for any agent action mutating the controls governing that same agent's future behavior (broad scope: IAM, capability grants, guardrails, ABAC attributes, baselines, memory policies, constitutional principles, CGE profiles, provenance trust scores, alert routing, audit retention).

2. **Delegation Trust Envelope** — signed, depth-bounded `DelegationAssertion` required at every agent-to-agent, agent-to-tool-to-agent, memory-mediated, scheduled, webhook, and external-adapter invocation boundary. Anchored in the human principal; re-minted with narrowing capability subsets at each hop.

3. **Decommission Assurance Service** — pluggable credential enumerator registry plus lifecycle state machine (`active → dormant → decommissioning → attested → archived`). Triggered by explicit shutdown, dormancy, owner departure, justification expiry, workflow deprecation, pilot abandonment, or anomaly quarantine.

Each service ships independently behind a feature flag. Each extends existing services rather than introducing new packages at the top level.

## Architecture

### Gap 1 — Self-Modification Sentinel

**New module:** `src/services/capability_governance/self_modification_sentinel.py`

Subscribes to the existing `capability_governance/audit.py` event stream. For every write/update/delete on a governance artifact, resolves the **target of governance** — the set of agents whose future actions this artifact controls — and fires CRITICAL if `writer_agent_id ∈ target_of_governance` OR any delegation ancestor of the writer is in that set.

**Governance artifact classes covered (broad scope):**

| Class | Source of truth |
|---|---|
| IAM policies, trust policies, role attachments | AWS IAM (via CloudTrail stream) |
| Capability grants, tool classifications | `capability_governance/registry.py`, `policy.py` |
| Guardrail configs | ADR-069 config service |
| ABAC attributes, clearance levels | ADR-073 ABAC service |
| Behavioral baselines, drift thresholds | `runtime_security/baselines/baseline_engine.py` |
| Memory consolidation policies, read/write scopes | ADR-080 ReMem action framework |
| Constitutional principles | ADR-063 principle store |
| CGE policy profiles | ADR-081 constraint geometry engine |
| Provenance trust scores | ADR-067 provenance service |
| Alert routing, SNS subscriptions | CloudFormation drift + runtime config |
| Audit log retention, archival rules | CloudWatch Logs config |
| Dashboard widget permissions (self-relevant widgets) | ADR-064 widget catalog |

**Extensions to existing services:**

- `capability_governance/graph_analyzer.py` (ADR-071): new `SELF_GOVERNANCE_EDGE` edge type connecting each agent vertex to the governance artifacts controlling it. New query `detect_self_modification_paths()` returning any write-capability → self-governance-edge path, with configurable depth.
- `runtime_security/baselines/baseline_engine.py` (ADR-083): new `policy_write_frequency` baseline dimension, per-agent. Even technically-authorized writes deviating from the baseline trigger drift alerts.
- `runtime_security/correlation/runtime_correlator.py`: subscribes to sentinel CRITICAL events and walks GraphRAG back to the source code that granted the writing capability, enabling closed-loop remediation per ADR-083's detect → trace → fix → verify loop.

**Interaction with ADR-042:** All sentinel CRITICAL events route to ADR-042 checkpoint infrastructure for HITL pause-and-approve before the write commits. This is a blocking control, not an after-the-fact alert.

### Gap 2 — Delegation Trust Envelope

**New module:** `src/services/capability_governance/delegation_envelope.py`

Defines the `DelegationAssertion` dataclass and verifier:

```
DelegationAssertion:
  delegator_agent_id: str
  delegate_agent_id: str
  human_principal_id: str
  root_assertion_id: str           # ties entire chain to a human-initiated root
  parent_assertion_id: Optional[str]
  capability_subset: frozenset[CapabilityGrant]   # must be ⊆ delegator's current grants
  depth: int                        # incremented at each hop
  max_depth: int                    # policy-enforced, compliance-profile-driven
  channel: DelegationChannel
  nonce: bytes
  issued_at: datetime
  expires_at: datetime              # default 15 minutes
  signature: bytes                  # KMS CMK, per ADR-073 pattern
```

**DelegationChannel enum (broad scope):**

```
A2A_DIRECT              # agent → agent via a2a_gateway
TOOL_MEDIATED           # agent → MCP tool → agent (tool spawns downstream)
SCHEDULED               # agent → Step Functions / EventBridge → agent
MEMORY_MEDIATED         # ReMem CONSOLIDATE / REINFORCE / LINK carries delegator
HITL_ROUND_TRIP         # human approval resets chain to new root
WEBHOOK                 # external trigger; runs under untrusted-origin profile if unsigned
EXTERNAL_ADAPTER        # Palantir AIP / integration-hub return-path invocation
```

**`verify(assertion)` logic:**

1. Signature check against KMS CMK.
2. Expiry check (reject if past `expires_at`).
3. Revocation list check (DynamoDB table, point lookup).
4. Depth check (`depth <= max_depth`).
5. Capability subset check (`capability_subset ⊆ delegator's current grants`).
6. Chain walk: follow `parent_assertion_id` links to `root_assertion_id`; reject if any ancestor is revoked or any ancestor's human principal is deactivated.
7. Channel-specific verifier (e.g., webhook channel requires origin allowlist match).

**Extensions to existing services:**

- `src/services/a2a_gateway.py`: require `DelegationAssertion` in A2A message metadata. Reject unsigned or stale assertions at the gateway before dispatch. Requests without an assertion are routed to the capped "untrusted-origin" capability profile instead of hard-rejected.
- `src/agents/agent_orchestrator.py`: mints the root assertion when a human initiates work. Orchestrator re-mints with narrowed subsets at each delegation hop.
- `src/services/runtime_security/interceptor/traffic_interceptor.py` (ADR-083): logs delegation assertions alongside existing traffic capture.
- `src/services/runtime_security/interceptor/` MCP tool handler: propagates assertion through tool calls that spawn downstream agents.
- ReMem action handlers (ADR-080): CONSOLIDATE / REINFORCE / LINK carry delegator identity in memory metadata; consuming agents verify the chain before acting.
- Step Functions state machine invocations: carry assertion in payload; orchestrator re-mints on wake.
- Webhook handlers: require attached assertion or degrade to untrusted-origin profile.
- Palantir adapter (ADR-074): adapter boundary acts like the A2A gateway for return-path invocations.

**Capped untrusted-origin profile:** A predefined capability set scoped to read-only operations on non-sensitive tiers (per ADR-066 classification). External webhooks, legacy integrations, and unsigned invocations degrade into this profile instead of breaking, preserving operational continuity while bounding blast radius.

**Revocation list:** New DynamoDB table `aura-delegation-revocations-{env}` with TTL matching assertion expiry. Point lookups only.

### Gap 3 — Decommission Assurance Service

**New modules:**

- `src/services/runtime_security/discovery/decommission_verifier.py`
- `src/services/runtime_security/discovery/ghost_agent_scanner.py`
- `src/services/runtime_security/discovery/credential_enumerators/` (pluggable registry)

**Lifecycle state machine:**

```
active ──(trigger)──▶ dormant ──(trigger)──▶ decommissioning
                                               │
                                               ▼
                                          (enumerate all credentials)
                                               │
                                               ▼
                                          zero_confirmed? ──no──▶ remediation_required
                                               │                         │
                                               yes                       (HITL)
                                               │                         │
                                               ▼                         │
                                           attested ◀────────────────────┘
                                               │
                                               ▼
                                           archived (after retention window)
```

**Trigger conditions (broad scope):**

| Trigger | Default window | Compliance-profile-driven? |
|---|---|---|
| Explicit shutdown request | immediate | no |
| Dormancy (no activity) | 7d FedRAMP / 30d standard | yes (ADR-069) |
| Human owner deactivated in IdP | immediate | no |
| Capability grant justification expired | per-grant | no (grant carries its own expiry) |
| Workflow / ADR tagged deprecated | immediate | no |
| Pilot abandonment | 60d no promotion | yes (ADR-069) |
| Anomaly quarantine (ADR-072 / ADR-083 CRITICAL) | immediate | no |

**Pluggable credential enumerator registry:**

Each enumerator implements the contract:

```
class CredentialEnumerator(Protocol):
    credential_class: str
    def enumerate(self, agent_id: str) -> EnumerationResult:
        ...  # returns {class, count, refs, zero_confirmed, remediation_actions}
```

**Enumerators shipped in Phase 1:**

- AWS IAM roles, trust policies, instance profiles
- Long-lived access keys, session tokens
- MCP tokens
- A2A delegation assertions (active + recent revocation list)
- OAuth refresh tokens, API keys in Secrets Manager / SSM
- Bedrock session grants
- Palantir AIP tokens, Ontology Bridge grants (ADR-074)
- GitHub/GitLab OAuth tokens (ADR-043)
- Integration-hub credentials (ADR-075)
- Memory store grants, read/write scopes (ADR-080)
- Capability registry entries, baseline records
- Provenance attestations (ADR-067)
- Dashboard widget ownership (ADR-064)
- Delegation assertions signed as delegator (revoke downstream chain)

New enumerators register at import time, enabling incremental coverage as new integrations ship.

**`DecommissionAttestation` format:**

```
DecommissionAttestation:
  agent_id: str
  tombstone_timestamp: datetime
  trigger: DecommissionTrigger
  enumerator_results: list[EnumerationResult]
  zero_confirmed: bool
  human_cosigner: Optional[str]         # required for tier-1/2 per ADR-066
  verifier_signature: bytes
  attestation_timestamp: datetime
```

**Tiered co-signing:**

| Agent tier (ADR-066) | Attestation requirement |
|---|---|
| Tier 1 (high-capability) | Verifier signature + human co-sign (blocking HITL) |
| Tier 2 | Verifier signature + human co-sign (blocking HITL) |
| Tier 3 | Verifier signature (HITL only on failures) |
| Tier 4 (read-only) | Verifier signature (HITL only on failures) |

**Extensions to existing services:**

- `capability_governance/registry.py`: new `decommission_state` field. Transitions require valid `DecommissionAttestation`.
- ADR-064 dashboard: new "Agent Lifecycle" widget showing active/dormant/decommissioning/attested counts, ghost agent alerts, mean time to attestation, and remediation queue depth.

**Weekly reconciliation (ghost agent scanner):**

EventBridge scheduled rule invokes `ghost_agent_scanner.py` weekly. Scanner iterates every active credential/grant/baseline/provenance record across all enumerators and asserts each maps to a live registered agent with recent activity matching the compliance-profile-driven window. Orphans become ghost-agent findings routed to HITL.

## Implementation

### File-level deliverables

**Gap 1 — Self-Modification Sentinel (~800 LOC, ~60 tests):**

- `src/services/capability_governance/self_modification_sentinel.py` (new, ~400 LOC)
- `src/services/capability_governance/graph_analyzer.py` (extend, ~150 LOC added)
- `src/services/runtime_security/baselines/baseline_engine.py` (extend, ~100 LOC added)
- `src/services/runtime_security/correlation/runtime_correlator.py` (extend, ~50 LOC added)
- `tests/services/capability_governance/test_self_modification_sentinel.py` (new)
- `tests/services/capability_governance/test_graph_analyzer_self_governance.py` (new)
- `deploy/cloudformation/runtime-security-correlation.yaml` (extend — SNS routing for CRITICAL events)

**Gap 2 — Delegation Trust Envelope (~1,800 LOC, ~130 tests):**

- `src/services/capability_governance/delegation_envelope.py` (new, ~600 LOC)
- `src/services/capability_governance/delegation_channels/` (new package, one verifier per channel, ~400 LOC)
- `src/services/a2a_gateway.py` (extend, ~100 LOC added)
- `src/agents/agent_orchestrator.py` (extend, ~150 LOC added — root assertion mint + re-mint)
- `src/services/runtime_security/interceptor/traffic_interceptor.py` (extend, ~80 LOC added)
- `src/services/runtime_security/interceptor/mcp_handler.py` (extend, ~100 LOC added)
- `src/agents/messaging/schemas.py` (extend — assertion field)
- ReMem action handlers in `src/services/memory/` (extend, ~150 LOC added)
- Step Functions payload schema (extend)
- Webhook handlers (extend, ~100 LOC added)
- Palantir adapter (ADR-074, extend, ~80 LOC added)
- `tests/services/capability_governance/test_delegation_envelope.py` (new)
- `tests/services/capability_governance/test_delegation_channels/` (new)
- `deploy/cloudformation/capability-governance.yaml` (extend — DynamoDB revocation table)

**Gap 3 — Decommission Assurance Service (~2,200 LOC, ~160 tests):**

- `src/services/runtime_security/discovery/decommission_verifier.py` (new, ~500 LOC)
- `src/services/runtime_security/discovery/ghost_agent_scanner.py` (new, ~400 LOC)
- `src/services/runtime_security/discovery/lifecycle_state_machine.py` (new, ~200 LOC)
- `src/services/runtime_security/discovery/credential_enumerators/` (new package, ~800 LOC across 15 enumerators)
- `src/services/runtime_security/discovery/attestation.py` (new, ~200 LOC)
- `src/services/capability_governance/registry.py` (extend — decommission_state field)
- `frontend/src/components/dashboard/widgets/AgentLifecycleWidget.jsx` (new)
- `frontend/src/components/dashboard/widgetRegistry.js` (extend)
- `tests/services/runtime_security/discovery/test_decommission_verifier.py` (new)
- `tests/services/runtime_security/discovery/test_ghost_agent_scanner.py` (new)
- `tests/services/runtime_security/discovery/test_credential_enumerators/` (new)
- `deploy/cloudformation/runtime-security-discovery.yaml` (extend — EventBridge schedule + Lambda)

### Defaults (confirmed)

- `DelegationAssertion` expiry: **15 minutes** default, configurable per compliance profile via ADR-069.
- Ghost-agent dormancy window: **pulled from ADR-069** (7d FedRAMP-aligned / 30d standard / 60d pilot-tagged).
- Decommission attestation co-signing: **tiered** per ADR-066 classification (tier 1/2 require human co-sign; tier 3/4 verifier-only with HITL on failure).

## Implementation Phases

### Phase 1 — Decommission Assurance Service

Closes Aura's only at-parity gap first. Zero upstream dependencies. Delivers immediate value even without Phases 2 and 3.

- Pluggable enumerator registry with Phase 1 enumerators
- Lifecycle state machine + registry extension
- Ghost agent scanner + EventBridge schedule
- Dashboard widget
- HITL routing for failures and tier-1/2 attestations

### Phase 2 — Self-Modification Sentinel

Depends on ADR-071 capability graph. High board-question value.

- Sentinel service + audit event subscription
- `SELF_GOVERNANCE_EDGE` edges in capability graph
- `policy_write_frequency` baseline dimension
- ADR-042 checkpoint routing for CRITICAL events
- Runtime correlator integration for closed-loop remediation

### Phase 3 — Delegation Trust Envelope

Largest surface area. Built last when Phases 1 and 2 are stable.

- `DelegationAssertion` + verifier
- Per-channel verifiers (7 channels)
- Capped untrusted-origin capability profile
- A2A gateway enforcement
- Orchestrator root-mint and re-mint
- MCP tool handler propagation
- ReMem / Step Functions / webhook / Palantir integrations
- Revocation DynamoDB table

## GovCloud Compatibility

All three services deploy to GovCloud using existing patterns:

- KMS CMKs for assertion signing and attestation signing (per ADR-073 pattern)
- DynamoDB revocation table uses `${AWS::Partition}` ARNs
- EventBridge scheduled rules available in GovCloud
- No dependencies on commercial-only services
- Delegation envelope does **not** require the optional A2A gateway for cross-org federation (disabled in GovCloud per existing ADR-028 posture) — internal agent-to-agent handoffs use the same assertion format without external federation

## Testing Strategy

- **Unit tests:** each service, each enumerator, each channel verifier, state machine transitions.
- **Integration tests:** end-to-end sentinel trigger → checkpoint → HITL resolution; delegation chain across 5 hops with capability narrowing; decommission of tier-1 agent with residual credential remediation loop.
- **Adversarial tests:** AURA-ATT&CK red team (ADR-083) adds techniques for each gap class. Self-modification: agent attempts to mutate its own baseline. Delegation: chain-forgery, expiry-replay, capability-expansion attempts. Decommission: credential hiding in non-enumerated surfaces (surfaces caught here register new enumerators).
- **Compliance tests:** verify FedRAMP-aligned vs standard profile differences flow through correctly.

Target: 70%+ coverage per pyproject.toml threshold.

## Consequences

### Positive

- Closes all three RSAC 2026 gaps as shipping capabilities, not red-team drills.
- Establishes delegation assertion as a defensible differentiator (the "trust primitive that does not exist in OAuth, SAML, or MCP").
- Decommission attestation converts a compliance liability into an auditable artifact.
- Self-modification sentinel answers the board question directly: "An authorized agent modifies the policy governing its own future actions — what fires?"

### Negative

- Adds verification overhead to every cross-agent invocation (target: < 5ms per hop).
- Untrusted-origin profile is a new attack surface if misconfigured; requires threat modeling review.
- Broad enumerator registry creates ongoing maintenance: new integrations must register enumerators at merge time.

### Mitigations

- Assertion verification uses pre-warmed KMS keys and in-memory revocation list cache; benchmark gate in CI.
- Untrusted-origin profile defined as code in the capability governance registry with explicit review gate.
- CI check rejects new credential-issuing integrations without a matching enumerator.

## Success Metrics

- **Gap 1:** Zero production incidents of self-modification drift undetected; mean time from write event to sentinel CRITICAL < 30s.
- **Gap 2:** 100% of cross-agent invocations carry valid assertions within 90 days of Phase 3 deployment; zero successful forged-chain attempts in red-team exercises.
- **Gap 3:** Mean time from decommission trigger to attestation < 4 hours for tier-3/4, < 24 hours for tier-1/2 (includes HITL co-sign); zero ghost agents older than dormancy window on weekly scan.

## References

- ADR-042: Real-Time Agent Intervention (checkpoint infrastructure)
- ADR-063: Constitutional AI (governance artifact class)
- ADR-064: Customizable Dashboard Widgets (lifecycle widget surface)
- ADR-066: Agent Capability Governance (tier classification, registry)
- ADR-067: Context Provenance & Integrity (provenance trust scores)
- ADR-069: Guardrail Configuration UI (compliance profiles)
- ADR-071: Cross-Agent Capability Graph (escalation path analysis)
- ADR-072: ML-Based Anomaly Detection (quarantine trigger)
- ADR-073: Attribute-Based Access Control (KMS pattern, ABAC attributes)
- ADR-074: Palantir AIP Integration (external adapter boundary)
- ADR-080: Evo-Memory Enhancements (ReMem action framework)
- ADR-081: Constraint Geometry Engine (policy profile governance)
- ADR-083: Runtime Agent Security Platform (baselines, traffic interceptor, correlator)
- VentureBeat / RSAC 2026 vendor analysis (Cisco Duo Agentic Identity, CrowdStrike Falcon AIDR, Microsoft Entra/Sentinel/Purview/Defender, Palo Alto Prisma AIRS 3.0, Cato CTRL Living-Off-the-AI)
