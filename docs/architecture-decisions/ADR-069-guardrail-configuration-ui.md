# ADR-069: Guardrail Configuration UI

## Status

Deployed

## Date

2026-01-26

## Reviews

| Reviewer | Role | Date | Verdict |
|----------|------|------|---------|
| Pending | AWS AI SaaS Architect | - | - |
| Pending | UI/UX Designer | - | - |
| Pending | Security Architect | - | - |
| Pending | Product Manager | - | - |

### Review Summary

_Awaiting review._

## Context

### The Configurability Gap

Project Aura has implemented four major AI guardrail systems (ADR-065 through ADR-068), but these capabilities are currently invisible to users:

| ADR | Capability | Current State |
|-----|------------|---------------|
| ADR-065 | Semantic Guardrails Engine | Platform-controlled, no user visibility |
| ADR-066 | Agent Capability Governance | Hardcoded policies, no customization |
| ADR-067 | Context Provenance & Integrity | Fixed trust thresholds |
| ADR-068 | Universal Explainability Framework | Single verbosity level |

### User Needs

Different organizations have different risk tolerances and workflow requirements:

```text
Enterprise Customer Spectrum:
├── Startups
│   └── Need: Speed over safety, minimal interruptions
│
├── Enterprise (non-regulated)
│   └── Need: Balanced approach, some customization
│
├── Financial Services (SOX)
│   └── Need: Audit trails, detailed explanations
│
├── Defense Contractors (CMMC)
│   └── Need: Strict controls, mandatory HITL
│
└── Federal Agencies (FedRAMP)
    └── Need: Maximum security, 2-person approval
```

### The Configuration Dilemma

Exposing security settings creates tension between user agency and platform security:

| Too Little Control | Too Much Control |
|-------------------|------------------|
| Users frustrated by unnecessary friction | Users disable protections they don't understand |
| One-size-fits-all doesn't fit | Misconfiguration creates vulnerabilities |
| Competitive disadvantage | Liability exposure |
| Support burden from inflexibility | Support burden from complexity |

### Competitive Landscape

| Competitor | Guardrail Configuration | Aura Opportunity |
|------------|------------------------|------------------|
| GitHub Copilot | No user config, black box | Transparency wins trust |
| Amazon CodeWhisperer | Basic on/off toggles | Granular enterprise control |
| Cursor | Minimal guardrails | Security-first for regulated industries |
| Tabnine | Privacy modes only | Full explainability framework |

## Decision

Implement a **Tiered Exposure Model** for guardrail configuration that exposes policy presets and business-context tuning while keeping core security mechanisms platform-controlled.

### Design Principle

> "Users don't need to configure security; they need to configure their risk tolerance."

Frame the UI around business outcomes (fewer interruptions vs. more oversight) rather than security mechanisms.

### Configuration Tiers

#### Tier 1: Platform-Controlled (Non-Negotiable)

These settings are hidden from all users to maintain security posture:

| Component | Reason |
|-----------|--------|
| ADR-065 Layers 1-3 (Normalization, Pattern Check, Embedding) | Core detection algorithms - exposure enables adversarial evasion |
| ADR-066 CRITICAL tier tool definitions | File deletion, credential access - never user-relaxable |
| ADR-067 Trust calculation weights (35/25/15/25) | Exposing formula enables gaming |
| ADR-068 Internal consistency check thresholds | Audit integrity mechanisms |
| Multi-turn cumulative scoring thresholds | Adversaries could craft multi-message attacks below threshold |
| Threat pattern databases | Security through obscurity for detection patterns |

#### Tier 2: User-Configurable (With Guardrails)

Settings exposed to all users with platform-enforced bounds:

| Setting | Source ADR | Options | Default |
|---------|-----------|---------|---------|
| **Security Profile** | 065, 066 | Conservative / Balanced / Efficient / Aggressive | Balanced |
| **HITL Escalation Sensitivity** | 065, 066, 067 | Low / Medium / High / Critical-Only | Medium |
| **Context Trust Requirements** | 067 | High Only / Medium+ / Low+ / All | Medium+ |
| **Explanation Verbosity** | 068 | Minimal / Standard / Detailed / Debug | Standard |
| **Agent Capability Grants** | 066 | Per-project tool allowlists | Role defaults |
| **Quarantine Review Delegation** | 067 | Self / Team Lead / Security Team | Team Lead |

#### Tier 3: Admin-Only (Enterprise Tier)

Settings available only to organization administrators:

| Setting | Source ADR | Bounds | Use Case |
|---------|-----------|--------|----------|
| Custom threat patterns | 065 | Additive only (cannot remove platform patterns) | Industry-specific threats |
| Trust source weight adjustment | 067 | ±15% from defaults (20-50% range) | Org-specific trust model |
| Tool tier overrides | 066 | Can only promote, not demote | Workflow-specific grants |
| Audit retention period | 068 | 90-2555 days | Compliance requirements |
| Cross-tenant policy inheritance | All | Parent policies as floor | Enterprise hierarchy |
| Compliance profile selection | All | Predefined profiles only | Regulatory requirements |

### Security Profile Presets

| Profile | HITL Threshold | Auto-Approve | Context Trust | Explanation |
|---------|---------------|--------------|---------------|-------------|
| **Conservative** | Low | SAFE only | High Only | Detailed |
| **Balanced** | Medium | SAFE + MONITORING | Medium+ | Standard |
| **Efficient** | High | SAFE + MONITORING | Medium+ | Standard |
| **Aggressive** | Critical-Only | SAFE + MONITORING + DANGEROUS | Low+ | Minimal |

### Compliance Profile Specifications

Compliance profiles override user preferences when activated:

```yaml
# CMMC Level 2 Profile
cmmc_level_2:
  locked_settings:
    min_context_trust_level: MEDIUM
    hitl_required_for: [DANGEROUS, CRITICAL]
    audit_retention_days: 365
    explanation_verbosity: DETAILED  # minimum
    credential_tool_tier: CRITICAL  # cannot demote

  enforced_behaviors:
    - All HITL escalations require CAC/PIV authentication
    - Configuration changes require supervisor approval
    - Quarantine release requires security team review

# SOC 2 Profile
soc2:
  locked_settings:
    audit_retention_days: 365
    explanation_verbosity: STANDARD  # minimum

  enforced_behaviors:
    - All configuration changes logged with business justification
    - Quarterly access review required

# FedRAMP High Profile
fedramp_high:
  locked_settings:
    min_context_trust_level: HIGH
    hitl_required_for: [MONITORING, DANGEROUS, CRITICAL]
    audit_retention_days: 2555  # 7 years
    explanation_verbosity: DETAILED

  enforced_behaviors:
    - Admin settings require 2-person approval
    - All decisions exportable for POAM evidence
    - No reduction in security posture without ISSO approval
```

### Platform Minimum Thresholds

Regardless of user settings, these minimums are enforced:

| Setting | Platform Minimum | Rationale |
|---------|-----------------|-----------|
| HITL for CRITICAL operations | Always required | Irreversible actions need human approval |
| Audit log retention | 90 days | Incident investigation window |
| Threat detection layers | All 6 active | Defense in depth |
| Trust verification | Always enabled | Prevent context poisoning |
| Explanation generation | Always enabled | Audit compliance |

### Validation Layer

All configuration changes pass through a validation layer:

```text
User Configuration Request
          │
          ▼
┌─────────────────────────────────────┐
│      Validation & Bounds Layer       │
├─────────────────────────────────────┤
│ 1. Enforce platform minimums         │
│ 2. Apply compliance profile locks    │
│ 3. Validate setting combinations     │
│ 4. Check permission level            │
│ 5. Require MFA for sensitivity ↓     │
│ 6. Generate audit record             │
└─────────────────────────────────────┘
          │
          ▼
   Configuration Applied
```

### UI Patterns

#### Primary: Progressive Disclosure

Simple preset selector with expandable advanced options:

```
┌─────────────────────────────────────────────────────────────────┐
│  AI Safety Settings                                    [?] Help │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Security Profile                                                │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ ○ Conservative   ○ Balanced   ● Efficient   ○ Aggressive  │ │
│  │                                                            │ │
│  │ Efficient: Agents perform MONITORING operations            │ │
│  │ automatically. DANGEROUS operations require approval.      │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ▶ Advanced Settings                                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Secondary: Impact Preview

Show projected impact before applying changes:

```
┌─────────────────────────────────────────────────────────────────┐
│  Review Changes                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  You're changing: HITL Threshold Medium → High                   │
│                                                                  │
│  Projected Impact (based on last 30 days):                       │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Metric                    Before      After     Change    │ │
│  │  ──────────────────────────────────────────────────────── │ │
│  │  Daily HITL prompts        12          4         -67%     │ │
│  │  Auto-approved operations  847         891       +5%      │ │
│  │  Quarantined items         3           8         +167%    │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ⚠️  Higher threshold means fewer interruptions but more         │
│     items will be quarantined for batch review.                  │
│                                                                  │
│           [ Cancel ]                    [ Apply Changes ]        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Tertiary: Guardrail Activity Dashboard

Read-only visibility into guardrail operations:

```
┌─────────────────────────────────────────────────────────────────┐
│  Guardrail Activity (Last 7 Days)                      [Export] │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Threat Detection                        Context Trust           │
│  ┌─────────────────────────┐            ┌─────────────────────┐ │
│  │ Blocked: 23             │            │ HIGH:      2,847    │ │
│  │ ├─ Prompt injection: 18 │            │ MEDIUM:    1,203    │ │
│  │ ├─ Jailbreak: 3         │            │ LOW:         89     │ │
│  │ └─ Data exfil: 2        │            │ Quarantined: 12     │ │
│  └─────────────────────────┘            └─────────────────────┘ │
│                                                                  │
│  Agent Operations                        Explanations            │
│  ┌─────────────────────────┐            ┌─────────────────────┐ │
│  │ SAFE:       8,234       │            │ Avg confidence: 87% │ │
│  │ MONITORING: 1,456       │            │ Alt. disclosed: 94% │ │
│  │ DANGEROUS:    34 (HITL) │            │ Consistency: 99.2%  │ │
│  │ CRITICAL:      2 (HITL) │            │                     │ │
│  └─────────────────────────┘            └─────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Data Model

```python
@dataclass
class GuardrailConfiguration:
    """User-configurable guardrail settings."""

    # Tier 2: User-configurable
    security_profile: SecurityProfile = SecurityProfile.BALANCED
    hitl_sensitivity: HITLSensitivity = HITLSensitivity.MEDIUM
    min_context_trust: TrustLevel = TrustLevel.MEDIUM
    explanation_verbosity: Verbosity = Verbosity.STANDARD
    quarantine_reviewer: ReviewerType = ReviewerType.TEAM_LEAD

    # Per-project overrides
    project_tool_grants: dict[str, list[ToolGrant]] = field(default_factory=dict)

    # Tier 3: Admin-only
    custom_threat_patterns: list[ThreatPattern] = field(default_factory=list)
    trust_weight_adjustments: dict[str, float] = field(default_factory=dict)
    tool_tier_overrides: dict[str, ToolTier] = field(default_factory=dict)
    audit_retention_days: int = 365
    compliance_profile: Optional[ComplianceProfile] = None

    # Metadata
    last_modified_by: str = ""
    last_modified_at: datetime = field(default_factory=datetime.now)
    change_justification: str = ""


class SecurityProfile(Enum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    EFFICIENT = "efficient"
    AGGRESSIVE = "aggressive"


class ComplianceProfile(Enum):
    NONE = "none"
    SOC2 = "soc2"
    CMMC_L2 = "cmmc_l2"
    CMMC_L3 = "cmmc_l3"
    FEDRAMP_MODERATE = "fedramp_moderate"
    FEDRAMP_HIGH = "fedramp_high"
```

### Audit Requirements

All configuration changes must be logged:

| Field | Description |
|-------|-------------|
| `timestamp` | When the change occurred |
| `user_id` | Who made the change |
| `setting_path` | Which setting was changed |
| `previous_value` | Value before change |
| `new_value` | Value after change |
| `justification` | Business reason (required for admin settings) |
| `approved_by` | Supervisor ID (if 2-person approval required) |
| `compliance_profile` | Active compliance profile at time of change |

## Implementation

### Phase 1: Foundation (Sprint 1-2)

1. **Guardrail Activity Dashboard Widget**
   - Add to ADR-064 widget catalog
   - Read-only metrics from ADR-065 through ADR-068
   - Integrates with existing dashboard persistence

2. **Settings Page MVP**
   - Security profile preset selector
   - Explanation verbosity toggle
   - Configuration audit logging

**Files to Create:**
```
src/services/guardrail_config/
├── __init__.py
├── config_service.py          # Configuration CRUD
├── validation_service.py      # Bounds enforcement
├── compliance_profiles.py     # Profile definitions
└── audit_service.py           # Change logging

frontend/src/components/settings/
├── GuardrailSettings.jsx      # Main settings page
├── SecurityProfileSelector.jsx
└── AdvancedGuardrailSettings.jsx

frontend/src/components/widgets/
└── GuardrailActivityWidget.jsx
```

### Phase 2: Advanced Configuration (Sprint 3-4)

3. **Per-Project Agent Capabilities**
   - Tool allowlist editor
   - Temporary capability grants with expiration
   - Integration with ADR-066 CapabilityRegistry

4. **Context Trust Configuration**
   - Minimum trust level selector
   - Quarantine review delegation
   - Integration with ADR-067 TrustScoringEngine

### Phase 3: Enterprise Features (Sprint 5-6)

5. **Compliance Profiles**
   - Profile selection UI (admin-only)
   - Locked settings indicators
   - Org-level inheritance

6. **Impact Preview & Analytics**
   - Historical trend visualization
   - "What-if" analysis for setting changes
   - Projected impact calculations

### Phase 4: Polish (Sprint 7-8)

7. **Onboarding Integration**
   - Add guardrail configuration to ADR-047 onboarding flow
   - Context-sensitive help and tooltips
   - "Recommended for your industry" suggestions

8. **API & Automation**
   - REST API for programmatic configuration
   - Terraform/CDK provider support
   - Configuration-as-code patterns

## Consequences

### Positive

1. **User Agency** - Organizations can tune guardrails to their risk tolerance
2. **Competitive Differentiation** - Enterprise control competitors lack
3. **Reduced Support Burden** - Self-service reduces "why blocked" tickets
4. **Compliance Demonstration** - Visible controls aid audit evidence
5. **Trust Through Transparency** - Users understand what protects them

### Negative

1. **Complexity** - More settings means more to document and support
2. **Misconfiguration Risk** - Users may choose insecure configurations
3. **Development Effort** - UI and validation logic across 4+ ADRs
4. **Testing Surface** - Many setting combinations to validate

### Mitigations

| Risk | Mitigation |
|------|------------|
| Misconfiguration | Platform minimums, compliance overrides, impact preview |
| Complexity | Progressive disclosure, smart defaults, presets |
| Security bypass | Core mechanisms never exposed, admin-only for sensitive |
| Support burden | In-context help, configuration analytics |

## References

- ADR-032: Configurable Autonomy (7 policy presets)
- ADR-064: Customizable Dashboard Widgets (UI patterns)
- ADR-065: Semantic Guardrails Engine
- ADR-066: Agent Capability Governance
- ADR-067: Context Provenance & Integrity
- ADR-068: Universal Explainability Framework
- AWS Well-Architected Framework: Operational Excellence Pillar
- NIST AI Risk Management Framework 1.0
