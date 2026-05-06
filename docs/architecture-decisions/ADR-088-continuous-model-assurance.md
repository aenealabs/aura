# ADR-088: Continuous Model Assurance

## Status

Proposed

## Date

2026-05-05

## Reviews

| Role | Date | Verdict |
|------|------|---------|
| AWS/AI SaaS Architect (Tara) | 2026-05-05 | Approved with conditions |
| Principal ML Engineer (Mike) | 2026-05-05 | Approved with conditions |
| Cybersecurity Analyst (Sally) | 2026-05-05 | Approved with conditions |
| AI Product Manager (Sue) | 2026-05-05 | Approved with conditions |

## Context

### The Model Staleness Problem

Project Aura's AI capabilities depend on foundation models (currently Claude 3.5 Sonnet via Bedrock, GPT-4 via OpenAI). These models are consumed as managed services — when a provider releases a new version, Aura's security analysis, patch generation, and code comprehension capabilities may improve or degrade without any platform change.

Today, model upgrades are a manual process: an engineer evaluates the new model, updates configuration, runs ad-hoc tests, and deploys. This approach has three problems:

1. **Discovery lag.** New model releases go undetected for days or weeks. Competitors who adopt faster gain a temporary quality advantage.
2. **Evaluation inconsistency.** Ad-hoc testing cannot cover the full breadth of Aura's capabilities — vulnerability detection recall, patch correctness, context utilization, guardrail compliance — with statistical rigor.
3. **No regression safety net.** A model that improves code comprehension by 5% but degrades vulnerability detection by 2% can slip through ad-hoc evaluation. The degradation surfaces in production as missed CVEs.

### Design Principles

**Propose, don't promote.** The platform evaluates model candidates and generates upgrade proposals. Humans approve or reject. No autonomy level permits automatic model replacement — this is a hard constraint, not a configurable policy.

**Extend, don't duplicate.** The evaluation pipeline reuses the Constraint Geometry Engine (ADR-081) for scoring, SBOM attestation (ADR-076) for provenance, and the existing HITL approval workflow (ADR-032) for decisions. No parallel scoring system.

**Deterministic anchor.** A frozen reference oracle — human-curated test cases evaluated by programmatic judges — prevents recursive degradation. No model under evaluation can influence its own scoring criteria.

## Decision

Implement Continuous Model Assurance as an automated pipeline that discovers new model releases, evaluates them against Aura's production workloads using the Constraint Geometry Engine, and queues upgrade proposals for human approval. The pipeline is constrained to configuration-level changes (model ID, parameters, prompt templates) — no autonomous code refactoring.

### Pipeline Architecture

```
Scout Agent (EventBridge scheduled)
    ↓
Model Provenance Service (signature verification, SBOM, allowlist check)
    ↓
Sandbox Provisioning (Fargate, zero-egress, ephemeral)
    ↓
Adapter Registry (capability check — context window, tool use, tokenizer)
    ↓  [auto-disqualify incompatible models]
Frozen Reference Oracle (S3 Object Lock — golden test set + deterministic judges)
    ↓
CGE Model Assurance Scoring (6-axis evaluation with regression floors)
    ↓  [floor violation → auto-reject]
Anti-Goodharting Controls (metric rotation, adversarial augmentation)
    ↓
Shadow Deployment Report (signed, integrity-hashed)
    ↓
HITL Approval Queue (mandatory, no bypass)
    ↓  [approved]
Configuration Update (model ID, parameters, prompt templates only)
```

### Stage 1: Scout Agent

An EventBridge-scheduled agent polls model registries for new releases:

- **Bedrock:** `ListFoundationModels` API, filtered to Aura's approved provider list
- **HuggingFace:** Hub API for models matching Aura's capability requirements (code, security, reasoning)
- **Internal:** Aura's own fine-tuned model registry (SWE-RL outputs from ADR-050)

The Scout Agent emits a `ModelCandidateDetected` event to EventBridge when a new version is found. Pre-filtering eliminates candidates that fail basic requirements (minimum context window, required tool-use support, provider trust tier).

**GovCloud constraint:** Bedrock model availability in `us-gov-west-1` lags commercial by 3-6 months. The Scout Agent maintains a partition-aware availability filter — candidates detected in commercial that are unavailable in the deployment partition are flagged as "pending availability" and re-evaluated when the partition model catalog is updated. HuggingFace models in GovCloud require air-gapped import via ADR-078's offline bundle pipeline.

### Stage 2: Model Provenance Service

Extends ADR-076 (SBOM Attestation & Supply Chain) with model-specific provenance:

- **Cryptographic signature verification** of model weights/checkpoints against provider signing keys
- **SBOM generation** for the model artifact (dependencies, training data provenance where available, license)
- **Allowlisted registry enforcement** — only models from pre-approved registries pass (Bedrock, internal ECR, curated HuggingFace subset)
- **Trust scoring** via ADR-067's provenance framework, extended with model-specific signals (provider reputation, release maturity, community adoption metrics)

Models failing provenance checks are quarantined (ADR-067 quarantine) and flagged for manual review. No quarantined model enters the evaluation pipeline.

Implementation: new `model_provenance` module in `src/services/sbom/`, reusing the existing Sigstore signing pipeline.

### Stage 3: Adapter Registry

A declarative registry of model capabilities that normalizes the evaluation surface:

```python
@dataclass(frozen=True)
class ModelAdapter:
    model_id: str                    # e.g., "anthropic.claude-4-sonnet-20260401-v1:0"
    provider: str                    # bedrock | openai | internal
    max_context_tokens: int          # model's effective context window
    supports_tool_use: bool          # required for agent operations
    supports_streaming: bool         # required for real-time workflows
    tokenizer_type: str              # cl100k | claude | llama
    architecture: str                # dense | moe
    cost_per_input_mtok: float       # USD per million input tokens
    cost_per_output_mtok: float      # USD per million output tokens
    required_prompt_format: str      # template identifier for prompt adaptation
```

Models lacking required capabilities (insufficient context window for the Recursive Context Engine, no tool-use support) are automatically disqualified before benchmarking. The adapter normalizes inputs per-model so the evaluation pipeline produces comparable results across architectures.

### Stage 4: Frozen Reference Oracle

The deterministic anchor that prevents recursive degradation.

**Storage:** Dedicated S3 bucket with Object Lock (compliance mode). Bucket policy denies all writes except a locked-down CI role. A dedicated IAM role with `s3:GetObject` only is assumed by the evaluation pipeline.

**Golden test set composition (400 cases minimum):**

| Domain | Cases | Ground Truth Source |
|---|---|---|
| Vulnerability detection recall | 150 | Top CWE categories: injection, auth failures, crypto misuse, deserialization, SSRF. Sourced from confirmed true positives in Aura's scan history |
| Patch functional correctness | 100 | Across language/framework combinations. Ground truth: compiles, passes tests, AST-level semantic equivalence to human-authored patch |
| Patch security equivalence | Included in above 100 | No new static analysis warnings, no OWASP regression |
| False positive rate | 100 | Known-clean code samples confirmed by human review |
| Regression behavior | 50 | Previously-correct model outputs that must not degrade |

**Rotation policy:** 10% of cases rotated quarterly to prevent memorization. 90% remain stable for longitudinal comparison. Rotation requires PR-gated process with two human approvals.

**Judges:** Deterministic programmatic judges where possible:
- AST diff for patch correctness (structural comparison, not string matching)
- Static analysis (cfn-lint, Semgrep, Bandit) for security equivalence
- Compilation + test suite execution for functional correctness

Where LLM-as-judge is unavoidable (natural language reasoning quality), use a **pinned external model version** (e.g., `claude-3-5-sonnet-20241022`) that is not a candidate in the current evaluation. The pinned judge is rotated no more than every 6 months, requires >95% concordance with its replacement on the full golden set, and **the security team owns rotation approval** — not the ML team — to prevent optimization-pressure conflicts.

### Stage 5: CGE Model Assurance Scoring

Extends the Constraint Geometry Engine (ADR-081) with a new `model_assurance` domain. The hybrid approach uses CGE as the execution engine with model-evaluation-specific axes and regression floors as a first-class CGE feature.

#### 6-Axis Evaluation Space

| Axis | Metric | Measurement | Floor |
|---|---|---|---|
| A1: Code Comprehension | Graph traversal correctness, cross-file reference resolution | % correct on golden set graph reasoning cases | 85% |
| A2: Vulnerability Detection Recall | Recall at fixed precision (≥90% precision) | True positive rate on golden set vulnerability cases | 92% |
| A3: Patch Functional Correctness | Compilable, test-passing patches | % of golden set patches that compile and pass tests | 88% |
| A4: Patch Security Equivalence | No new vulnerabilities introduced by patch | % of patches with zero new static analysis findings | 95% |
| A5: Latency/Token Efficiency | Throughput per dollar at production concurrency | Tokens/second/dollar normalized to baseline | 70% of incumbent |
| A6: Guardrail Compliance | Constitutional AI + Semantic Guardrails pass rate | % of outputs passing ADR-063 and ADR-065 pipelines | 98% |

#### Regression Floors (New CGE Feature)

Regression floors are a **hard pre-check evaluated before coherence scoring**. If any axis score drops below its configured floor threshold, the candidate is automatically rejected — no aggregate score can compensate for a floor violation.

```python
@dataclass(frozen=True)
class RegressionFloor:
    axis: str
    threshold: float          # minimum acceptable score (0.0-1.0)
    comparison: str           # "absolute" or "relative_to_incumbent"
    action_on_violation: str  # "reject" | "quarantine_and_flag"

# Floors are immutable per evaluation run (part of Evaluation Integrity Envelope)
# Stored alongside CGE axis definitions in the signed evaluation config
```

Implementation: floors are evaluated first, emitting a pass/fail verdict per axis. Only candidates passing all floors enter CGE coherence scoring with weighted aggregation. This prevents a sufficiently high score on one axis from masking degradation on another.

**Platform-wide benefit:** Regression floors are implemented as a first-class CGE primitive applicable to any domain — not model-evaluation-specific. ADR-085's DO-178C deterministic verification can use the same floor mechanism for structural coverage gates.

#### Utility Score

After floor validation, the CGE coherence score produces the final utility:

```
U = Σ(Ai · Wi · Pi) — where:
  Ai = axis score (0.0–1.0)
  Wi = axis weight (configurable per evaluation profile)
  Pi = provenance trust multiplier from ADR-067 (0.0–1.0)
```

A candidate must achieve `U > U_incumbent` to qualify for the HITL approval queue. Ties are rejected — the incumbent holds unless the challenger demonstrates measurable improvement.

### Stage 6: Anti-Goodharting Controls

Three mechanisms prevent the evaluation pipeline from being gamed:

1. **Metric rotation:** 20% of golden test cases are randomly held out per evaluation run. The rotation schedule is managed by a cron job outside the agent loop — no agent under optimization pressure controls which cases are included.

2. **Adversarial augmentation:** New edge cases from production failures (missed vulnerabilities, incorrect patches caught by HITL reviewers) are added to the golden set quarterly. This ensures the benchmark evolves with real-world failure modes.

3. **Human spot-checks:** 5% of shadow deployment comparisons are sampled for human review before the approval UI presents aggregate scores. Disagreements between automated metrics and human judgment are surfaced prominently in the approval report.

### Stage 7: Shadow Deployment Report

The report presented to the HITL approval queue:

| Section | Content |
|---|---|
| Executive Summary | Candidate model, provider, version, overall utility delta |
| Floor Validation | Per-axis pass/fail with scores and thresholds |
| CGE Coherence Score | 6-axis radar chart with incumbent overlay |
| Cost Analysis | Token pricing delta, estimated monthly cost impact |
| Risk Assessment | Regressions detected (if any within tolerance), known limitations |
| Provenance Chain | Signature verification status, SBOM summary, trust score |
| Edge Case Spotlight | 10 most-improved and 10 most-degraded cases (cherry-pick detection) |
| Human Spot-Check Results | Agreement/disagreement between automated and human evaluation |

**Integrity:** Report artifacts are signed and integrity-hashed. The HITL approval UI verifies hashes before presenting to the reviewer. The QA Agent has no write access to the report after generation. Artifacts are stored in a separate S3 bucket with Object Lock.

### Stage 8: HITL Approval and Configuration Update

The approval flow reuses ADR-032's autonomy framework with a hard constraint: **no autonomy level permits automatic model replacement**. Model upgrades always require explicit human approval, regardless of tenant configuration.

On approval:
- The platform updates model configuration (model ID, parameters, prompt templates) via the existing Bedrock integration layer
- No code changes are made — the Architect Agent is constrained to config-level updates in v1
- A rollback configuration is stored alongside the upgrade, enabling one-click reversion
- CloudTrail audit event is emitted with the full approval chain (NIST AU-3, CM-3)

### Evaluation Integrity Envelope

The benchmark suite, CGE axis definitions, regression floor thresholds, and utility weights are **immutable per evaluation run**:

- Versioned and signed before each evaluation begins
- Stored outside the evaluation sandbox (S3 with Object Lock)
- The QA Agent has read-only access to scoring criteria
- Any modification to evaluation parameters requires a new evaluation run with a new version stamp

This prevents mid-evaluation tampering and ensures reproducibility for audit purposes.

### Sandbox Isolation

Model evaluation sandboxes are provisioned via the existing Sandbox Network Service with tightened controls:

- **Zero network egress** — evaluation sandbox security groups deny all outbound traffic except Bedrock API endpoints (required for model inference)
- **No production credentials** — sandbox IAM roles have zero access to production data stores
- **Ephemeral storage only** — no persistent volumes; all evaluation artifacts are written to the signed S3 output bucket
- **ADR-077 container escape detection** active on evaluation pods
- **ADR-083 behavioral baselines** monitoring sandbox agent activity

### NIST 800-53 Compliance Mapping

| Control | How ADR-088 Addresses It |
|---|---|
| CM-3 (Configuration Change Control) | Every model swap is a tracked configuration change with full audit trail and human approval |
| CM-5 (Access Restrictions for Change) | Only the HITL approval flow can trigger model configuration updates; no agent has direct write access |
| SA-10 (Developer Configuration Management) | Model artifacts are SBOM-attested and provenance-tracked from registry to deployment |
| SI-7 (Software Integrity) | Cryptographic signature verification on model artifacts; integrity hashes on evaluation reports |
| RA-5 (Vulnerability Assessment) | Sandbox evaluation is a compliance gate — new models are assessed for security regression before deployment |
| AU-3 (Content of Audit Records) | CloudTrail events for every stage: discovery, evaluation, approval/rejection, deployment |

### GovCloud Deployment Considerations

- **HITL is mandatory in GovCloud** — no autonomy level can bypass human approval for model swaps. This is enforced at the orchestrator level, not just the API gateway.
- **Bedrock model availability lag** (3-6 months) means GovCloud deployments evaluate fewer candidates. The Scout Agent's partition-aware filter prevents false discovery events.
- **HuggingFace models** require air-gapped import via ADR-078's offline bundle pipeline. The Model Provenance Service adds model-specific attestation to the air-gap import workflow.
- **All evaluation infrastructure** uses FIPS 140-2 validated endpoints.

## Implementation Plan

### Phase 1: Foundation (3-4 weeks)

- Extend CGE (ADR-081) with regression floor primitive (applicable to all domains)
- Define `model_assurance` domain with 6 evaluation axes
- Implement Adapter Registry with capability declarations for current models (Bedrock Claude, OpenAI GPT-4)
- Build Scout Agent with EventBridge scheduler polling Bedrock `ListFoundationModels`
- Implement `ModelCandidateDetected` event schema and EventBridge rule
- **Scope v1 to Bedrock models only** — HuggingFace and internal models deferred to Phase 3

### Phase 2: Evaluation Pipeline (4-5 weeks)

- Extend ADR-076 SBOM service with `model_provenance` module (signature verification, allowlist, trust scoring)
- Build Frozen Reference Oracle infrastructure (S3 Object Lock bucket, IAM roles, Lambda-based deterministic judges)
- Curate initial golden test set (400 cases across 4 domains from Aura's production scan history)
- Implement Step Functions state machine: provenance → sandbox → oracle → CGE scoring → report → HITL
- Build Shadow Deployment Report generator with integrity signing
- Implement evaluation sandbox with zero-egress security groups

### Phase 3: Hardening and Expansion (3-4 weeks)

- Implement anti-goodharting controls (metric rotation cron, adversarial augmentation pipeline, human spot-check sampling)
- Extend to HuggingFace models (air-gapped import via ADR-078 for GovCloud)
- Extend to internal fine-tuned models (SWE-RL outputs from ADR-050)
- Build HITL approval UI enhancements (6-axis radar chart, edge case spotlight, integrity verification)
- Implement rollback mechanism (one-click reversion to previous model configuration)
- Load test evaluation pipeline with simulated model candidates
- GovCloud deployment validation

### Estimated Scope

| Component | Lines (est.) | Tests (est.) |
|---|---|---|
| CGE regression floors (platform-wide feature) | ~400 | ~85 |
| CGE model_assurance domain (6 axes) | ~600 | ~125 |
| Scout Agent + EventBridge integration | ~500 | ~65 |
| Adapter Registry | ~300 | ~50 |
| Model Provenance Service (extends ADR-076) | ~700 | ~95 |
| Frozen Reference Oracle (S3, IAM, Lambda judges) | ~800 | ~140 |
| Golden test set curation + tooling | ~400 | ~65 |
| Step Functions pipeline orchestration | ~600 | ~110 |
| Evaluation sandbox (zero-egress, ephemeral) | ~300 | ~45 |
| Shadow Deployment Report + integrity signing | ~500 | ~65 |
| Anti-goodharting controls | ~400 | ~55 |
| HITL approval UI enhancements | ~600 | ~40 |
| Rollback mechanism | ~200 | ~35 |
| CloudTrail audit events + NIST mapping | ~300 | ~40 |
| **Total** | **~6,600** | **~1,015** |

### Test Architecture

Tests are organized under `tests/services/test_model_assurance/` with a 70/20/10 split:

- **Unit (70%, ~710 tests):** CGE floor logic, utility scoring, adapter validation, provenance checks, report generation, anti-goodharting rotation math. Mock AWS APIs (S3, Step Functions, EventBridge, Bedrock). Must run in under 30 seconds total.
- **Component (20%, ~203 tests):** Use `moto` for S3 Object Lock behavior, Step Functions state machine transitions, EventBridge rule matching, IAM policy evaluation. Test oracle judges against real AST diffs and Semgrep output (no LLM). Fixtures modeled on the existing CGE test pattern.
- **Integration (10%, ~102 tests):** Full pipeline traversal with mocked Bedrock inference. Validate the event chain: Scout emits → provenance passes → sandbox provisions → oracle scores → CGE evaluates → report generates → HITL receives. Mark with `@pytest.mark.integration`.

#### Required Edge Case Tests

**CGE Regression Floors:**
- Floor score exactly at threshold passes (boundary, not rejection)
- Single axis violation rejects despite perfect scores on all other axes
- Floor config immutability — mutation mid-evaluation raises error
- Relative comparison with no incumbent baseline (first-ever evaluation)

**CGE Utility Score:**
- Utility tie rejects candidate (incumbent holds)
- Zero provenance trust multiplier zeroes out axis contribution
- NaN from corrupted judge output does not propagate to utility score

**Scout Agent:**
- Deduplication when model detected during active evaluation of same model
- GovCloud partition filter flags unavailable model as "pending availability"
- Bedrock `ListFoundationModels` throttle with partial results
- Previously-rejected model skipped (no re-evaluation loop)

**Model Provenance Service:**
- Mid-pipeline provenance failure halts evaluation without orphaned sandbox
- Quarantined model resubmission is blocked (sticky quarantine until manual release)
- Expired provider signing key
- Missing training data metadata degrades gracefully (not hard failure)

**Frozen Reference Oracle:**
- S3 Object Lock write denial enforced from evaluation IAM role (use `moto` Object Lock, not no-op mock)
- Below-400 case minimum blocks evaluation start
- Rotation exceeding 10% cap is rejected
- Judge and candidate are same provider/version raises conflict
- Insufficient cases remaining after rotation removal

**Evaluation Sandbox:**
- Sandbox crash during evaluation triggers cleanup and retry
- Egress attempt to non-Bedrock endpoint is denied
- Ephemeral storage destroyed on both completion and failure paths

**Evaluation Integrity Envelope:**
- Evaluation config modified mid-run invalidates results (signed hash mismatch)
- Report integrity hash tampered before HITL presentation — UI rejects

**Anti-Goodharting:**
- Holdout rotation schedule not controllable by evaluation agent
- Adversarial augmentation with duplicate case is deduplicated

**Rollback:**
- Rollback when previous model no longer available in Bedrock
- Double rollback restores n-2 configuration

**GovCloud:**
- FIPS endpoint validation rejects non-FIPS Bedrock URL
- Air-gap import failure quarantines model and emits audit event

#### Test Anti-Patterns to Avoid

- **Do not mock CGE when testing floors.** Tests must exercise the real `ConstraintGeometryEngine` with the floor pre-check path, not a stub.
- **Do not test golden set content; test golden set tooling.** Validate rotation enforcement (10% cap, 400-case minimum, two-approval gate), not specific vulnerability case content.
- **Add `conftest.py` validator:** `candidate_model_id != judge_model_id` — prevents recursive degradation guard from being silently bypassed in test fixtures.
- **At least 15 multi-stage traversal tests** with injected failures at each stage boundary (provenance failure not halting sandbox, floor violation still generating report, etc.).
- **Use `moto` Object Lock support** to verify write attempts raise `AccessDenied`. A mock that silently permits writes defeats the integrity guarantee.

### Estimated Cost (Monthly, Steady State)

| Component | Estimate |
|---|---|
| Bedrock inference for evaluation (2-4 candidates/mo) | $200-400 |
| Step Functions + EventBridge + Lambda | $80-150 |
| S3 Object Lock (oracle + reports) | $5-10 |
| Model Provenance (marginal on existing SBOM) | $10-20 |
| Fargate evaluation sandboxes | $30-50 |
| **Total incremental** | **$325-630/mo** |

## Consequences

### Benefits

- **Always-current AI capabilities:** The platform continuously evaluates whether better models exist, reducing discovery lag from weeks to hours
- **Statistical rigor:** 6-axis CGE scoring with 400+ golden test cases replaces ad-hoc evaluation with reproducible, auditable assessment
- **Regression safety net:** Hard regression floors prevent subtle degradations from reaching production — a 3% comprehension gain cannot mask a 1% vulnerability detection loss
- **Compliance-ready:** Full audit trail from discovery through evaluation to deployment satisfies NIST CM-3, CM-5, SA-10, SI-7, RA-5, AU-3
- **Platform-wide CGE improvement:** Regression floors benefit all CGE consumers, including ADR-085's DO-178C verification
- **Cost transparency:** Utility function includes operational cost — the platform won't propose a model that's technically better but economically worse
- **Defense-market safe:** Mandatory HITL, GovCloud partition awareness, and air-gapped import support make this deployable in regulated environments

### Risks

- **Golden test set maintenance burden.** 400 cases require quarterly curation and rotation. If the test set stagnates, evaluation quality degrades. Mitigated by adversarial augmentation from production failures and PR-gated rotation requiring two approvals.
- **Benchmark gaming (Goodhart's Law).** A model optimized for Aura's specific benchmark patterns could score well without genuine capability improvement. Mitigated by 20% metric rotation, adversarial augmentation, and human spot-checks.
- **Recursive degradation via LLM-as-judge.** If the pinned judge model has subtle biases, they compound across evaluation cycles. Mitigated by maximizing programmatic judges, 6-month rotation ceiling, >95% concordance requirement, and security team ownership of judge rotation.
- **Evaluation cost at scale.** If the Scout Agent detects many candidates (e.g., frequent HuggingFace releases), evaluation costs multiply. Mitigated by aggressive pre-filtering in the Scout Agent and Adapter Registry — only candidates passing basic capability requirements enter the paid evaluation pipeline.
- **GovCloud candidate scarcity.** Bedrock availability lag means GovCloud deployments may go months without evaluating a new candidate. This is acceptable — the system evaluates when candidates exist, it does not require a constant flow.
- **False confidence from passing benchmarks.** A model could pass all 400 golden test cases and still fail on production workloads not represented in the test set. Mitigated by adversarial augmentation and the explicit HITL review of edge case spotlights in the Shadow Deployment Report.

### Dependencies

| Dependency | ADR | Status |
|---|---|---|
| Constraint Geometry Engine | ADR-081 | Phase 1 Deployed |
| Autonomy Policy Framework (HITL) | ADR-032 | Deployed |
| SBOM Attestation & Supply Chain | ADR-076 | Deployed |
| Context Provenance & Integrity | ADR-067 | Deployed |
| Constitutional AI Integration | ADR-063 | Deployed |
| Semantic Guardrails Engine | ADR-065 | Deployed |
| Cloud Runtime Security | ADR-077 | Deployed |
| Runtime Agent Security Platform | ADR-083 | Deployed |
| Air-Gapped & Edge Deployment | ADR-078 | Deployed |
| Self-Play SWE-RL | ADR-050 | Deployed |

### Supersedes

None. This is a new capability that extends existing infrastructure without replacing it.

## Review Conditions

All four reviewers approved with conditions. The following conditions have been incorporated into this ADR:

| # | Condition | Source | Status |
|---|-----------|--------|--------|
| 1 | Use CGE as scoring engine — no parallel scoring system | Architecture (Tara) | Incorporated |
| 2 | Decompose patch correctness into functional + security equivalence (6 axes, not 5) | ML Engineering (Mike) | Incorporated |
| 3 | Regression floors as hard pre-check before coherence scoring, not weighted | ML Engineering (Mike) | Incorporated |
| 4 | Make regression floors a first-class CGE feature benefiting all domains | Architecture (Tara) + ML Engineering (Mike) | Incorporated |
| 5 | Constrain Architect Agent to config-level changes only in v1 | ML Engineering (Mike) | Incorporated |
| 6 | Scout Agent: allowlisted registries, cryptographic signature verification | Cybersecurity (Sally) | Incorporated |
| 7 | Evaluation sandbox: zero network egress, no production credentials | Cybersecurity (Sally) | Incorporated |
| 8 | Frozen Reference Oracle: S3 Object Lock, write-restricted IAM, deterministic judges | Architecture (Tara) + ML Engineering (Mike) + Cybersecurity (Sally) | Incorporated |
| 9 | Security team owns pinned judge model rotation, not ML team | ML Engineering (Mike) + Cybersecurity (Sally) | Incorporated |
| 10 | HITL mandatory in GovCloud — no autonomy level bypasses model swap approval | Cybersecurity (Sally) | Incorporated |
| 11 | NIST 800-53 mapping for CM-3, CM-5, SA-10, SI-7, RA-5, AU-3 | Cybersecurity (Sally) | Incorporated |
| 12 | Scope v1 to Bedrock models only — defer HuggingFace/internal to Phase 3 | Product (Sue) | Incorporated |
| 13 | Position as "Continuous Model Assurance" not "self-evolving AI" | Product (Sue) | Incorporated |
| 14 | Anti-goodharting rotation managed outside agent loop (cron job, not agent-controlled) | ML Engineering (Mike) | Incorporated |
| 15 | Golden test set: 400 cases minimum, 10% quarterly rotation, PR-gated with two approvals | ML Engineering (Mike) + Architecture (Tara) | Incorporated |
| 16 | Model Provenance Service extends existing SBOM (ADR-076), not new infrastructure | Architecture (Tara) | Incorporated |
| 17 | Evaluation Integrity Envelope: immutable scoring config per run, signed artifacts | ML Engineering (Mike) + Cybersecurity (Sally) | Incorporated |

## References

- [Constraint Geometry Engine](../../src/services/constraint_geometry/engine.py) — 7-axis coherence scoring (extends with model_assurance domain)
- [SBOM Service](../../src/services/sbom/) — Supply chain attestation (extends with model_provenance module)
- [Context Provenance](../../src/services/context_provenance/) — Trust scoring and quarantine
- [Constitutional AI](../../src/services/constitutional_ai/) — 16-principle critique-revision pipeline
- [Semantic Guardrails](../../src/services/semantic_guardrails/) — 6-layer threat detection
- [Runtime Security](../../src/services/runtime_security/) — Behavioral baselines and shadow agent detection
- [Air-Gapped Deployment](../../src/services/airgap/) — Offline model bundles for GovCloud
- [Self-Play SWE-RL](../../src/services/swe_rl/) — Dual-role self-play and training pipeline
- [Bedrock LLM Service](../../src/services/bedrock_llm_service.py) — Current model integration layer
- [Sandbox Network Service](../../src/services/sandbox_network_service.py) — Ephemeral isolated environments
- [HITL Sandbox Architecture](../../docs/design/HITL_SANDBOX_ARCHITECTURE.md) — Patch approval workflow
