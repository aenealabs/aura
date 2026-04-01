# ADR-032: Configurable Autonomy Framework

**Status:** Deployed
**Date:** 2025-12-10
**Decision Makers:** Project Aura Platform Team
**Related:** ADR-005 (HITL Sandbox Architecture), ADR-018 (MetaOrchestrator Dynamic Agent Spawning)

---

## Executive Summary

This ADR documents the decision to implement a configurable autonomy framework that enables organizations to toggle Human-in-the-Loop (HITL) requirements based on their compliance needs. This allows Aura to serve both heavily regulated enterprises (defense, healthcare, financial services) and commercial enterprises with different autonomy requirements.

**Key Outcomes:**
- Configurable HITL toggle at organization level
- Pre-built policy presets for common compliance scenarios
- Granular overrides by severity, operation, and repository
- Guardrails that ALWAYS require human approval regardless of policy
- Target: 85% autonomous operation for commercial enterprises

---

## Context

### Current State

Aura was designed with a HITL-first approach requiring human approval for all critical operations. While this meets the needs of heavily regulated industries (CMMC, SOX, HIPAA, FedRAMP), it creates friction for commercial enterprises that want faster autonomous operation.

### Problem Statement

1. **Commercial Enterprise Adoption:** Startups and commercial enterprises want autonomous code intelligence without mandatory HITL delays
2. **One-Size-Doesn't-Fit-All:** A defense contractor and a fintech startup have vastly different compliance requirements
3. **Development Velocity:** Mandatory HITL for all operations blocks autonomous development workflows
4. **Market Positioning:** Competitors offer varying autonomy levels; Aura needs flexibility

### Requirements

1. **Configurable HITL:** Organizations must be able to enable/disable HITL requirements
2. **Compliance Presets:** Pre-built configurations for common compliance frameworks
3. **Granular Control:** Override autonomy levels by severity, operation type, or repository
4. **Safety Guardrails:** Critical operations MUST require human approval regardless of policy
5. **Audit Trail:** All autonomy decisions must be logged for compliance
6. **Backward Compatible:** Existing HITL workflows must continue to work

---

## Decision

**Implement a multi-layer Autonomy Policy Framework with the following components:**

### 1. Autonomy Levels

| Level | Description | HITL Required |
|-------|-------------|---------------|
| `FULL_HITL` | Human approval for all operations | Always |
| `CRITICAL_HITL` | Human approval for HIGH/CRITICAL severity only | HIGH, CRITICAL |
| `AUDIT_ONLY` | Log decisions, no blocking approval | Never |
| `FULL_AUTONOMOUS` | Fully automated operation | Never |

### 2. Policy Presets

| Preset | Default Level | HITL Enabled | Target Industry |
|--------|--------------|--------------|-----------------|
| `defense_contractor` | FULL_HITL | Yes | GovCloud, CMMC L3+ |
| `financial_services` | FULL_HITL | Yes | SOX, PCI-DSS |
| `healthcare` | FULL_HITL | Yes | HIPAA |
| `fintech_startup` | CRITICAL_HITL | Yes | Growth-stage companies |
| `enterprise_standard` | CRITICAL_HITL | Yes | Fortune 500 |
| `internal_tools` | FULL_AUTONOMOUS | No | Internal dev teams |
| `fully_autonomous` | FULL_AUTONOMOUS | No | Commercial dev/test |

### 3. Guardrails (Always Require HITL)

Regardless of policy settings, these operations ALWAYS require human approval:

- `production_deployment` - Deploying to production environments
- `credential_modification` - Changing API keys, secrets, passwords
- `access_control_change` - Modifying IAM, RBAC, permissions
- `database_migration` - Schema changes, data migrations
- `infrastructure_change` - Cloud resource modifications

### 4. Override Hierarchy

Policy resolution follows this priority:
1. **Guardrails** (highest) - Always enforced
2. **Repository Overrides** - Per-repo configurations
3. **Operation Overrides** - Per-operation configurations
4. **Severity Overrides** - Per-severity configurations
5. **Default Level** (lowest) - Policy default

### Implementation Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     API Layer                                    │
│  /api/v1/autonomy/policies - CRUD operations                    │
│  /api/v1/autonomy/check - HITL requirement check                │
└─────────────────────┬───────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│               AutonomyPolicyService                              │
│  - Policy management and caching                                 │
│  - HITL requirement evaluation                                   │
│  - Decision audit logging                                        │
└─────────────────────┬───────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│               DynamoDB Tables                                    │
│  - autonomy-policies: Organization policies                      │
│  - policy-audit: Change history                                  │
│  - autonomy-decisions: Decision log                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Alternatives Considered

### Alternative 1: Environment Variable Toggle (Rejected)

Simple boolean `HITL_ENABLED=true/false` at deployment time.

**Rejected because:**
- No per-organization customization
- No granular control by severity/operation
- Requires redeployment to change
- No audit trail

### Alternative 2: Hardcoded Compliance Modes (Rejected)

Pre-defined modes like "GovCloud Mode" vs "Commercial Mode".

**Rejected because:**
- Too coarse-grained
- Doesn't account for hybrid organizations
- Can't handle organization-specific requirements
- No progression path (defense → autonomous)

### Alternative 3: Full Policy Engine (Considered but Simplified)

Implement a full RBAC-style policy engine with conditions, inheritance, etc.

**Rejected because:**
- Over-engineered for initial use cases
- Significant implementation complexity
- Can be added later if needed
- Current design covers 90% of use cases

---

## Consequences

### Positive

1. **Commercial Market Access:** Can compete for commercial enterprise contracts
2. **Flexibility:** Organizations configure autonomy to match their compliance posture
3. **Progressive Adoption:** Organizations can start strict and gradually enable autonomy
4. **Safety Preserved:** Guardrails ensure dangerous operations always require humans
5. **Audit Compliance:** Full decision logging for any compliance framework

### Negative

1. **Configuration Complexity:** More settings to manage per organization
2. **Testing Surface:** Must test all autonomy level combinations
3. **Documentation:** Users need to understand policy implications

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Organization selects too-permissive policy | Medium | High | Default to CRITICAL_HITL; warning in UI |
| Guardrail bypass attempt | Low | Critical | Guardrails enforced in code, not configurable |
| Audit log tampering | Low | High | Immutable DynamoDB logging with GSI |
| Policy misconfiguration | Medium | Medium | Validation in API; preset recommendations |

---

## Implementation

### Files Created

| File | Purpose |
|------|---------|
| `src/services/autonomy_policy_service.py` | Core policy management service |
| `src/api/autonomy_endpoints.py` | REST API for policy configuration |
| `tests/test_autonomy_policy_service.py` | Comprehensive test suite (37 tests) |

### DynamoDB Tables Added

| Table | Purpose |
|-------|---------|
| `aura-autonomy-policies-{env}` | Organization policy storage |
| `aura-policy-audit-{env}` | Policy change audit log |
| `aura-autonomy-decisions-{env}` | Autonomy decision log |

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/autonomy/policies` | GET | List policies |
| `/api/v1/autonomy/policies` | POST | Create policy |
| `/api/v1/autonomy/policies/{id}` | GET | Get policy |
| `/api/v1/autonomy/policies/{id}` | PUT | Update policy |
| `/api/v1/autonomy/policies/{id}` | DELETE | Deactivate policy |
| `/api/v1/autonomy/policies/{id}/toggle` | PUT | Toggle HITL |
| `/api/v1/autonomy/policies/{id}/overrides` | POST | Add override |
| `/api/v1/autonomy/policies/{id}/overrides` | DELETE | Remove override |
| `/api/v1/autonomy/check` | POST | Check HITL requirement |
| `/api/v1/autonomy/presets` | GET | List available presets |

### Integration Points

1. **MetaOrchestrator:** Checks `requires_hitl_approval()` before agent execution
2. **HITL Workflow:** Respects policy decisions in Step Functions
3. **Sandbox Service:** Applies autonomy level to sandbox operations
4. **Monitoring:** Tracks autonomous vs HITL decisions in CloudWatch

---

## Future Enhancements

1. **Policy Inheritance:** Child organizations inherit from parent with overrides
2. **Time-Based Policies:** Different autonomy levels for business hours vs off-hours
3. **ML-Based Recommendations:** Suggest autonomy level based on historical decisions
4. **Approval Delegation:** Allow certain users to approve on behalf of roles

---

## References

- ADR-005: HITL Sandbox Architecture
- ADR-018: MetaOrchestrator Dynamic Agent Spawning
- ADR-021: Guardrails Cognitive Architecture
- NIST 800-53: Access Control (AC) family
- CMMC Level 3: Access Control requirements
