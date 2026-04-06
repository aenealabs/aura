# ADR-086: Agentic Identity Lifecycle Controls

## Status

Deployed

## Date

2026-04-06

## Reviews

| Reviewer | Role | Date | Verdict |
|----------|------|------|---------|
| Pending | Cybersecurity Analyst | - | - |
| Pending | AI Product Manager | - | - |
| Pending | Senior Systems Architect | - | - |

## Context

### The Three Agentic Identity Gaps

The RSAC 2026 vendor analysis (Cisco Duo Agentic Identity, CrowdStrike Falcon AIDR, Microsoft Entra/Sentinel/Purview/Defender, Palo Alto Prisma AIRS 3.0, Cato CTRL Living-Off-the-AI) identified three gaps no surveyed vendor ships production coverage for:

| Gap | Problem | Industry State |
|-----|---------|---------------|
| **Ghost agents** | Abandoned pilots, departed owners, expired justifications leave agents running with live credentials and no offboarding | All vendors discover running agents. None verifies zero residual credentials after decommission. |
| **Self-modification** | An authorized agent rewrites the policy governing its own future actions. Every credential check passes because the action is authorized. | No vendor ships a dedicated runtime detection rule. |
| **Delegation trust** | When agent A hands work to agent B, no runtime trust verification ties the delegation back to a human principal. | The trust primitive is missing from OAuth, SAML, and MCP. |

### Aura's Current Position

Aura has partial coverage:

- **ADR-083** baselines detect behavioral drift but do not enforce decommission attestation
- **ADR-071** flags toxic tool combinations (e.g., `modify_iam_policy` + `access_secrets`) but does not treat self-governance modification as a first-class event class
- **ADR-071** `detect_escalation_paths()` walks delegation chains after the fact but provides no inline runtime primitive to reject invalid delegations at invocation time
- **ADR-066** classifies tools into 4 tiers but has no lifecycle state preventing decommissioned agents from retaining active grants

### Strategic Framing

The vendor field is converging on registration and runtime visibility. Aura has both. The defensible differentiation is lifecycle controls -- the primitives that activate after an agent is registered and visible.

## Decision

Implement **Agentic Identity Lifecycle Controls** across three sequential phases:

### Phase 1: Decommission Assurance Service

Lifecycle state machine (`active -> dormant -> decommissioning -> attested -> archived`) with a pluggable credential enumerator registry. 15 enumerators verify zero residual credentials across IAM, MCP, OAuth, Secrets Manager, SSM, Bedrock, Palantir AIP, GitHub/GitLab, integration-hub, ReMem, capability governance, baselines, provenance, and dashboard widgets. Tiered attestation co-signing per ADR-066 agent tier. Weekly ghost agent reconciliation via EventBridge.

### Phase 2: Self-Modification Sentinel

Dedicated detector treating "agent mutating its own governing controls" as a first-class event class. Subscribes to ADR-066 audit stream, resolves target-of-governance for every write, fires CRITICAL if writer is in the governed set. Covers 12 governance artifact classes. Routes through ADR-042 checkpoint infrastructure for blocking HITL approval. Extends Neptune capability graph with `SELF_GOVERNANCE_EDGE` edge type.

### Phase 3: Delegation Trust Envelope

Signed, depth-bounded `DelegationAssertion` required at every cross-agent invocation boundary. Chains anchored in a human principal, re-minted with narrowing capability subsets at each hop. 7 delegation channels (A2A direct, tool-mediated, scheduled, memory-mediated, HITL round-trip, webhook, external adapter). KMS-signed assertions with DynamoDB revocation table. Unsigned invocations degrade to capped untrusted-origin profile.

## Consequences

### Positive

- Closes all three identity gaps ahead of surveyed vendor field
- Each phase ships independently behind feature flags
- Extends existing ADR-042, ADR-066, ADR-071, ADR-073, ADR-083 infrastructure
- GovCloud-compatible (uses `${AWS::Partition}` in all ARNs)

### Negative

- Per-hop verification adds latency to cross-agent invocations (target < 5ms p99)
- Tier 1/2 decommission requires human co-sign, adding operational overhead
- 15 credential enumerators require maintenance as new integrations are added

### Risks

- CI enforcement (rejecting credential-issuing integrations without matching enumerators) may slow new integration development
- Weekly ghost agent scanner may surface false positives during pilot periods

## Implementation

- **Scope:** ~4,800 lines source, ~350 tests across three phases
- **Deploy order:** Phase 1 (no dependencies) -> Phase 2 (depends on Phase 1) -> Phase 3 (depends on Phases 1 and 2)

### Phase 1 Deliverables

- `src/services/runtime_security/discovery/lifecycle_state_machine.py`
- `src/services/runtime_security/discovery/credential_enumerators/` (15 enumerators)
- `src/services/runtime_security/discovery/decommission_verifier.py`
- `src/services/runtime_security/discovery/ghost_agent_scanner.py`
- `src/services/runtime_security/discovery/attestation.py`
- `frontend/src/components/dashboard/widgets/AgentLifecycleWidget.jsx`
- `deploy/cloudformation/runtime-security-discovery.yaml`

### Phase 2 Deliverables

- `src/services/capability_governance/self_modification_sentinel.py`
- Extensions to `graph_analyzer.py`, `baseline_engine.py`, `runtime_correlator.py`

### Phase 3 Deliverables

- `src/services/capability_governance/delegation_envelope.py`
- `src/services/capability_governance/delegation_channels/` (7 channel verifiers)
- Extensions to `a2a_gateway.py`, `agent_orchestrator.py`, `traffic_interceptor.py`

## References

- ADR-042: Real-Time Agent Intervention
- ADR-066: Agent Capability Governance
- ADR-067: Context Provenance & Integrity
- ADR-069: Guardrail Configuration UI
- ADR-071: Cross-Agent Capability Graph
- ADR-073: Attribute-Based Access Control
- ADR-080: Evo-Memory Enhancements
- ADR-083: Runtime Agent Security Platform
- RSAC 2026 vendor analysis (VentureBeat)
