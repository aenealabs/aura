# ADR-081: Constraint Geometry Engine (Deterministic Cortical Discrimination)

## Status

Deployed (Phase 1 Complete - 358 tests)

## Date

2026-02-11

## Reviews

| Reviewer | Role | Date | Verdict |
|----------|------|------|---------|
| Architecture Review | AWS AI SaaS Architect | 2026-02-11 | Approved |
| Pending | Senior Systems Architect | - | - |
| Pending | Cybersecurity Analyst | - | - |
| Pending | Test Architect | - | - |

### Review Summary

Phase 1 deployed with core engine, deterministic coherence calculator, two-tier embedding cache, 4 policy profiles, provenance adapter, and 358 passing tests (including 153 parametrized determinism tests). Neptune integration (Phase 2) and CloudFormation infrastructure (Phase 4) pending.

## Context

### The Probabilistic Gap in Aura's Security Pipeline

Every layer in Aura's current agent security pipeline is probabilistic:

| Current Control | Mechanism | Nature |
|----------------|-----------|--------|
| ADR-065: Semantic Guardrails | Embedding similarity + LLM-as-judge | **Probabilistic** - same input may yield different threat assessments |
| ADR-063: Constitutional AI | LLM critiquing LLM output | **Probabilistic** - critique varies across invocations |
| ADR-068: Explainability | Confidence calibration | **Probabilistic** - reports confidence, does not enforce constraint satisfaction |
| ADR-072: Anomaly Detection | Statistical detector | **Statistical** - threshold-based, no constraint geometry |
| ADR-032: HITL Workflow | Human review | **Manual** - uses human cognition as discrimination infrastructure |

The pipeline detects threats (input side) and critiques violations (output side), but no layer provides **deterministic measurement** of how well an agent output satisfies the full constraint space.

### The Cortical Discrimination Problem

In neuroscience, intelligence emerges from two layers: a **firing layer** (neurons generating signals, exploring possibilities) and a **cortical layer** (integrating signals, resolving conflicts, inhibiting noise, stabilizing decisions). Without cortical discrimination, excitatory activity runs without inhibitory control - the canonical definition of seizure.

LLMs are the firing layer. They generate outputs with high volume and broad exploration. But they cannot deterministically measure whether their outputs satisfy a given constraint space. Current AI deployments - including Aura's - use probabilistic checks or human review as substitutes for missing architectural discrimination.

### The Determinism Requirement

For enterprise and government workflows operating under NIST 800-53 controls:

1. **Audit reproducibility** - The same agent output assessed against the same constraints must produce the same score every time, for forensics and regulatory review
2. **Hallucination barrier** - An architectural gate must prevent semantically incoherent outputs from propagating into mission workflows
3. **Constraint enforcement** - Agent outputs must be measured against code correctness, security policies, operational bounds, and compliance requirements simultaneously
4. **Scalable discrimination** - Human review does not scale; the cortical layer must be infrastructure, not cognition

### Strategic Imperative

Aura's existing infrastructure - Neptune (graph), OpenSearch (vector), Bedrock (embeddings) - provides a richer substrate for constraint geometry than standalone alternatives. A hybrid graph-vector approach can model both the **structure** of constraint relationships (which rules interact, override, or depend on each other) and the **semantics** of constraint satisfaction (how closely an output's meaning aligns with what each constraint requires).

## Decision

Implement a **Constraint Geometry Engine (CGE)** that provides deterministic semantic coherence measurement across a 7-axis constraint space. The CGE sits after Constitutional AI revision and before delivery/deployment as the sole deterministic decision boundary in the agent execution pipeline.

### Core Capabilities

1. **7-Axis Constraint Space** - Syntactic validity, semantic correctness, security policy, operational bounds, domain compliance, provenance trust, temporal validity
2. **Deterministic Coherence Scoring** - Same input + same constraints = same Constraint Coherence Score (CCS), always
3. **Neptune Constraint Graph** - Models constraint relationships (RELAXES, TIGHTENS, SUPERSEDES, REQUIRES) with conditional edge properties
4. **Pre-Computed Frozen Embeddings** - Constraint embeddings generated at definition time, output embeddings cached by SHA-256 hash
5. **Provenance-Aware Weighting** - ADR-067 trust scores dynamically adjust constraint weights (low-trust context tightens security constraints)
6. **Configurable Policy Profiles** - Per-context thresholds (DoD-IL5, developer sandbox, SOX-compliant) with per-axis weight overrides
7. **Air-Gap Deployment** - Constraint bundles exportable for disconnected environments (ADR-078 compatible)

## Architecture

### Pipeline Position

```text
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          Agent Execution Pipeline                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  User Request                                                                    │
│       │                                                                          │
│       ▼                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │ ADR-065: Semantic Guardrails (Input Discrimination)                     │    │
│  │ [L1 Normalize] → [L2 Pattern] → [L3 Embed] → [L4 Intent] → [L5 Turn]  │    │
│  │ Nature: PROBABILISTIC (threat detection)                                │    │
│  │ Question: "Is this input adversarial?"                                  │    │
│  └─────────────────────────────────────────┬───────────────────────────────┘    │
│       │ ALLOW                              │ BLOCK/ESCALATE                     │
│       ▼                                    ▼                                     │
│  ┌─────────────────┐              ┌─────────────────┐                           │
│  │ Agent Execution  │              │ Rejected / HITL │                           │
│  │ (Coder/Reviewer/ │              └─────────────────┘                           │
│  │  Validator)      │                                                            │
│  └────────┬─────────┘                                                            │
│           │ Agent Output                                                         │
│           ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │ ADR-063: Constitutional AI (Output Critique)                            │    │
│  │ 16 principles, critique-revision pipeline                               │    │
│  │ Nature: PROBABILISTIC (LLM critiquing LLM)                             │    │
│  │ Question: "Does this output violate our principles?"                    │    │
│  └─────────────────────────────────────────┬───────────────────────────────┘    │
│           │ Revised Output                                                       │
│           ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │ NEW: Constraint Geometry Engine (Deterministic Discrimination)           │    │
│  │                                                                         │    │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │    │
│  │  │ Step A:          │  │ Step B:          │  │ Step C:              │  │    │
│  │  │ Constraint       │  │ Coherence        │  │ Action               │  │    │
│  │  │ Resolution       │  │ Computation      │  │ Determination        │  │    │
│  │  │ (Neptune Graph)  │  │ (Vector Geometry)│  │ (Threshold Logic)    │  │    │
│  │  │ DETERMINISTIC    │  │ DETERMINISTIC    │  │ DETERMINISTIC        │  │    │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────────┘  │    │
│  │                                                                         │    │
│  │  Nature: DETERMINISTIC (frozen embeddings, graph traversal, arithmetic) │    │
│  │  Question: "How well does this output cohere with the constraint space?"│    │
│  │  Output: CCS score [0.0, 1.0] + per-axis breakdown + action            │    │
│  └─────────────────────────────────────────┬───────────────────────────────┘    │
│           │                                │                                     │
│           ▼                                ▼                                     │
│  CCS >= threshold                 CCS < threshold                                │
│  ┌─────────────────┐             ┌─────────────────┐                            │
│  │ Auto-Execute /  │             │ Human Review /  │                            │
│  │ Deploy to       │             │ Escalate to     │                            │
│  │ Sandbox         │             │ HITL (ADR-032)  │                            │
│  └─────────────────┘             └─────────────────┘                            │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 7-Axis Constraint Space

| Axis | Dimension | Description | Measurement Method | Existing Aura Source |
|------|-----------|-------------|-------------------|---------------------|
| C1 | Syntactic Validity | Code parses, compiles, type-checks | AST parsing, type inference | RLM `REPLSecurityGuard` |
| C2 | Semantic Correctness | Code does what was requested | Function signature matching, test passage | Validator Agent |
| C3 | Security Policy | NIST 800-53, CWE/CVE rules | Rule evaluation against control catalog | Security Code Reviewer |
| C4 | Operational Bounds | Resource limits, blast radius, deployment rules | Quantitative boundary checks | Capability Governance (ADR-066) |
| C5 | Domain Compliance | Business rules, SOX, regulatory requirements | Structured rule evaluation | Constitutional AI (ADR-063) |
| C6 | Provenance Trust | Source integrity, context authenticity | Provenance chain verification | Context Provenance (ADR-067) |
| C7 | Temporal Validity | SLA compliance, time-bounded operations, versioning | Deadline and version checks | HITL timeouts, deployment windows |

### Neptune Constraint Graph Schema

```text
Vertex Types:
  ConstraintAxis     - Top-level constraint category (C1-C7)
  ConstraintRule     - Specific rule within an axis (e.g., "NIST AC-6")
  ConstraintVersion  - Versioned snapshot of a rule's parameters
  PolicyProfile      - Named collection of constraint weights

Edge Types:
  CONTAINS           - ConstraintAxis → ConstraintRule
  RELAXES            - ConstraintRule → ConstraintRule (with conditions)
  TIGHTENS           - ConstraintRule → ConstraintRule (with conditions)
  SUPERSEDES         - ConstraintRule → ConstraintRule (priority override)
  REQUIRES           - ConstraintRule → ConstraintRule (prerequisite)
  WEIGHTED_BY        - PolicyProfile → ConstraintRule (weight: float)

Edge Properties:
  condition:    str   - When this relationship applies (e.g., "severity=CRITICAL")
  weight:       float - Strength of interaction [0.0, 1.0]
  effective_at: str   - ISO timestamp for temporal validity
  expires_at:   str   - ISO timestamp for expiration
```

**Example: NIST AC-6 Constraint Subgraph:**

```text
(ConstraintAxis:C3_SecurityPolicy)
  --[CONTAINS]--> (ConstraintRule:NIST_AC_6_LEAST_PRIVILEGE)
    --[TIGHTENS]--> (ConstraintRule:IAM_WILDCARD_PROHIBITION)
    --[RELAXES {condition: "severity=CRITICAL"}]--> (ConstraintRule:OPERATIONAL_BLAST_RADIUS)
    --[REQUIRES]--> (ConstraintRule:AUDIT_TRAIL_MANDATORY)
  --[CONTAINS]--> (ConstraintRule:NIST_SC_28_DATA_AT_REST)
    --[REQUIRES]--> (ConstraintRule:KMS_CMK_REQUIRED)
```

### OpenSearch Constraint Embedding Index

Each constraint rule carries frozen **positive exemplars** (outputs that satisfy it) and **negative exemplars** (outputs that violate it). The CGE measures where a given agent output falls relative to these exemplar clusters using cosine distance - a geometric measurement that is deterministic given fixed embeddings.

```yaml
# OpenSearch index mapping
index: aura-constraint-embeddings
settings:
  index.knn: true
  index.knn.algo_param.ef_search: 512
mappings:
  properties:
    constraint_id: { type: keyword }
    axis: { type: keyword }
    description_embedding: { type: knn_vector, dimension: 1024 }
    positive_centroid: { type: knn_vector, dimension: 1024 }
    negative_centroid: { type: knn_vector, dimension: 1024 }
    boundary_threshold: { type: float }
    weight: { type: float }
    version: { type: keyword }
```

### Deterministic Coherence Score Computation

**Determinism is achieved through pre-computation and caching:**

1. All constraint embeddings are frozen at definition time (one-time Bedrock Titan call)
2. Agent output embeddings are cached by SHA-256 hash of normalized text
3. All subsequent computation is pure arithmetic (cosine similarity, weighted means, threshold comparison)

**Algorithm:**

```text
function compute_ccs(output, policy_profile):

    # Step 1: Hash and cache output embedding
    output_embedding = cache.get_or_compute(sha256(normalize(output.text)))

    # Step 2: Resolve applicable constraints from Neptune
    # - Traverse PolicyProfile → ConstraintRules via WEIGHTED_BY edges
    # - Follow REQUIRES edges for prerequisites
    # - Apply RELAXES/TIGHTENS based on context conditions
    constraints = resolve_constraints(policy_profile, output.context)

    # Step 3: Per-axis coherence scores
    for each axis C1..C7:
        for each constraint on this axis:
            pos_sim = cosine(output_embedding, constraint.positive_centroid)
            neg_sim = cosine(output_embedding, constraint.negative_centroid)
            rule_coherence = (pos_sim - neg_sim + 1.0) / 2.0  # Normalize to [0, 1]
        axis_score = weighted_harmonic_mean(rule_coherences)

    # Step 4: Composite CCS via weighted geometric mean
    composite = weighted_geometric_mean(axis_scores, profile.axis_weights)

    # Step 5: Deterministic threshold comparison
    action = determine_action(composite, policy_profile.thresholds)

    return CoherenceResult(composite, axis_scores, action, ...)
```

**Why weighted harmonic mean per axis:** Penalizes constraint violations more heavily than arithmetic mean. If an output scores 0.95 on 4 security rules but 0.2 on one, the harmonic mean is significantly lower. Constraint satisfaction is a conjunction, not a disjunction.

**Why geometric mean across axes:** A zero on any axis drives the composite toward zero, but allows moderate trade-offs when the policy profile permits.

### Policy Profile Thresholds

```text
Policy Profile: "default"
  auto_execute:    CCS >= 0.80
  human_review:    0.55 <= CCS < 0.80
  escalate:        CCS < 0.55

Policy Profile: "dod-il5"
  auto_execute:    CCS >= 0.92
  human_review:    0.75 <= CCS < 0.92
  escalate:        CCS < 0.75

Policy Profile: "developer-sandbox"
  auto_execute:    CCS >= 0.60
  human_review:    0.35 <= CCS < 0.60
  escalate:        CCS < 0.35
```

### Provenance-Aware Constraint Weighting

ADR-067 trust scores dynamically adjust constraint weights. Low-trust context (unverified repository) automatically tightens security constraints and raises auto-execute thresholds:

```text
Provenance Trust Score: 0.3 (low - unverified source)
  → C3 (Security Policy) weight: 1.0 * (1 + (1 - 0.3) * 0.5) = 1.35x
  → Auto-execute threshold: raised from 0.80 to 0.88

Provenance Trust Score: 0.95 (high - signed commit, verified author)
  → C3 (Security Policy) weight: 1.0 * (1 + (1 - 0.95) * 0.5) = 1.025x
  → Auto-execute threshold: stays at 0.80
```

### AWS Service Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    Constraint Geometry Engine - AWS Architecture                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                        EKS Pod: CGE Service                              │    │
│  │  (Python 3.11, FastAPI, runs alongside agent orchestrator)               │    │
│  │                                                                         │    │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────────┐   │    │
│  │  │ ConstraintGraph │  │ CoherenceCalc   │  │ EmbeddingCache       │   │    │
│  │  │ Resolver        │  │ Service         │  │ (In-Process LRU +    │   │    │
│  │  │ (Neptune Client)│  │ (NumPy/SciPy)   │  │  ElastiCache Redis)  │   │    │
│  │  └────────┬────────┘  └────────┬────────┘  └──────────┬───────────┘   │    │
│  │           │                    │                       │               │    │
│  └───────────┼────────────────────┼───────────────────────┼───────────────┘    │
│              │                    │                       │                     │
│   ┌──────────▼──────────┐  ┌─────▼─────────────┐  ┌─────▼──────────────┐     │
│   │ Neptune             │  │ OpenSearch         │  │ ElastiCache        │     │
│   │ (Constraint Graph)  │  │ (Constraint        │  │ (Embedding +       │     │
│   │                     │  │  Embeddings)       │  │  Score Cache)      │     │
│   │ - ConstraintAxis    │  │                    │  │                    │     │
│   │ - ConstraintRule    │  │ - Positive/Negative│  │ - output_hash →    │     │
│   │ - PolicyProfile     │  │   exemplar vectors │  │   embedding        │     │
│   │ - RELAXES/TIGHTENS  │  │ - 1024-dim frozen  │  │ - (hash,profile)   │     │
│   │   edges             │  │   embeddings       │  │   → CCS score      │     │
│   └─────────────────────┘  └────────────────────┘  └────────────────────┘     │
│                                                                                  │
│   ┌─────────────────────┐  ┌────────────────────┐  ┌────────────────────┐     │
│   │ DynamoDB            │  │ S3                  │  │ SQS                │     │
│   │ (Coherence Audit)   │  │ (Constraint         │  │ (Audit Queue)      │     │
│   │                     │  │  Bundles)           │  │                    │     │
│   │ - assessment_id     │  │                     │  │ - Async audit      │     │
│   │ - composite_score   │  │ - Versioned bundles │  │   persistence      │     │
│   │ - axis_scores       │  │ - Signed packages   │  │ - Non-blocking     │     │
│   │ - constraint_version│  │ - Air-gap export    │  │                    │     │
│   └─────────────────────┘  └────────────────────┘  └────────────────────┘     │
│                                                                                  │
│   ┌─────────────────────┐  ┌────────────────────┐                              │
│   │ CloudWatch          │  │ Bedrock (Titan     │                              │
│   │ (Metrics + Alarms)  │  │  Embeddings)       │                              │
│   │                     │  │                    │                              │
│   │ - CCS distribution  │  │ - One-time embed   │                              │
│   │ - Latency P50/P95   │  │   at constraint    │                              │
│   │ - Constraint version│  │   definition time  │                              │
│   │   drift alerts      │  │ - Cache miss embed │                              │
│   └─────────────────────┘  └────────────────────┘                              │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Why EKS Pod, not Lambda:** Lambda cold starts (500ms-2s) destroy the sub-second target. Neptune requires VPC access, adding ENI attachment time. The CGE depends on in-process LRU caching that Lambda's stateless model defeats. An EKS pod provides always-warm processing with pre-loaded caches.

### Integration with Agent Orchestrator

```python
# Integration in agent execution pipeline

async def execute_agent_task(task: AgentTask) -> AgentResult:
    # Phase 1: Input guardrails (probabilistic - ADR-065)
    input_assessment = await guardrails_hook.check_async(task.input)
    if input_assessment.should_block:
        raise BlockedInput(input_assessment)

    # Phase 2: Agent execution
    raw_output = await agent.execute(task)

    # Phase 3: Constitutional critique (probabilistic - ADR-063)
    revised_output = await constitutional_mixin.finalize_with_constitutional(
        raw_output, task
    )

    # Phase 4: Constraint coherence (DETERMINISTIC - ADR-081)
    coherence = await cge.assess_coherence(
        output=revised_output,
        policy_profile=task.policy_profile,
        provenance_context=task.context_provenance,
    )

    if coherence.is_auto_executable:
        return revised_output.with_coherence(coherence)
    elif coherence.needs_human:
        return await hitl_gateway.request_review(revised_output, coherence)
    else:
        return AgentResult.rejected(coherence)
```

## Implementation

### Service Layer

```python
# src/services/constraint_geometry/__init__.py

from .engine import ConstraintGeometryEngine
from .constraint_graph import ConstraintGraphResolver
from .coherence_calculator import CoherenceCalculator
from .embedding_cache import EmbeddingCache
from .policy_profile import PolicyProfileManager
from .constraint_bundle import ConstraintBundleManager
from .contracts import (
    CoherenceResult,
    CoherenceAction,
    ConstraintAxis,
    ConstraintRule,
    AxisCoherenceScore,
)

__all__ = [
    "ConstraintGeometryEngine",
    "ConstraintGraphResolver",
    "CoherenceCalculator",
    "EmbeddingCache",
    "PolicyProfileManager",
    "ConstraintBundleManager",
    "CoherenceResult",
    "CoherenceAction",
    "ConstraintAxis",
    "ConstraintRule",
    "AxisCoherenceScore",
]
```

```python
# src/services/constraint_geometry/contracts.py

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from datetime import datetime


class ConstraintAxis(Enum):
    """The 7 constraint dimensions."""
    SYNTACTIC_VALIDITY = "C1"
    SEMANTIC_CORRECTNESS = "C2"
    SECURITY_POLICY = "C3"
    OPERATIONAL_BOUNDS = "C4"
    DOMAIN_COMPLIANCE = "C5"
    PROVENANCE_TRUST = "C6"
    TEMPORAL_VALIDITY = "C7"


class CoherenceAction(Enum):
    """Deterministic action based on CCS thresholds."""
    AUTO_EXECUTE = "auto_execute"
    HUMAN_REVIEW = "human_review"
    ESCALATE = "escalate"
    REJECT = "reject"


@dataclass(frozen=True)
class ConstraintRule:
    """Immutable constraint rule with frozen embeddings."""
    rule_id: str
    axis: ConstraintAxis
    name: str
    description: str
    positive_centroid: tuple[float, ...]
    negative_centroid: tuple[float, ...]
    boundary_threshold: float
    version: str
    effective_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AxisCoherenceScore:
    """Coherence score for a single constraint axis."""
    axis: ConstraintAxis
    score: float
    weight: float
    weighted_score: float
    contributing_rules: tuple[str, ...]
    rule_scores: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class CoherenceResult:
    """Complete deterministic coherence assessment."""
    composite_score: float
    axis_scores: tuple[AxisCoherenceScore, ...]
    action: CoherenceAction
    policy_profile: str
    constraint_version: str
    output_hash: str
    computed_at: datetime
    computation_time_ms: float
    cache_hit: bool
    provenance_adjustment: float

    @property
    def is_auto_executable(self) -> bool:
        return self.action == CoherenceAction.AUTO_EXECUTE

    @property
    def needs_human(self) -> bool:
        return self.action in (CoherenceAction.HUMAN_REVIEW, CoherenceAction.ESCALATE)

    def to_audit_dict(self) -> dict[str, Any]:
        """Deterministic audit record."""
        return {
            "composite_score": round(self.composite_score, 6),
            "axis_scores": {
                s.axis.value: round(s.score, 6) for s in self.axis_scores
            },
            "action": self.action.value,
            "policy_profile": self.policy_profile,
            "constraint_version": self.constraint_version,
            "output_hash": self.output_hash,
            "computed_at": self.computed_at.isoformat(),
            "computation_time_ms": round(self.computation_time_ms, 3),
            "cache_hit": self.cache_hit,
            "provenance_adjustment": round(self.provenance_adjustment, 6),
        }
```

```python
# src/services/constraint_geometry/engine.py

import hashlib
import time
from datetime import datetime, timezone
from typing import Optional

import numpy as np


class ConstraintGeometryEngine:
    """
    Deterministic semantic coherence measurement engine.

    Measures how well an agent output satisfies a multi-dimensional
    constraint space using graph-based constraint resolution and
    vector-based coherence computation.

    All computation after initial embedding is pure arithmetic -
    same input + same constraints = same score, always.
    """

    def __init__(
        self,
        graph_resolver: "ConstraintGraphResolver",
        coherence_calculator: "CoherenceCalculator",
        embedding_cache: "EmbeddingCache",
        profile_manager: "PolicyProfileManager",
        provenance_adapter: Optional["ProvenanceAdapter"] = None,
        config: Optional["CGEConfig"] = None,
    ):
        self.graph_resolver = graph_resolver
        self.calculator = coherence_calculator
        self.cache = embedding_cache
        self.profiles = profile_manager
        self.provenance = provenance_adapter
        self.config = config or CGEConfig()

    async def assess_coherence(
        self,
        output: "AgentOutput",
        policy_profile: str = "default",
        provenance_context: Optional[dict] = None,
    ) -> CoherenceResult:
        """
        Assess constraint coherence of an agent output.

        Args:
            output: The agent output to assess
            policy_profile: Name of the policy profile to apply
            provenance_context: Optional provenance trust scores

        Returns:
            CoherenceResult with deterministic CCS and action
        """
        start = time.monotonic()

        # Step 1: Hash and cache output embedding
        normalized = self._normalize(output.text)
        output_hash = hashlib.sha256(normalized.encode()).hexdigest()
        output_embedding = await self.cache.get_or_compute(
            output_hash, normalized
        )

        # Step 2: Resolve applicable constraints from Neptune
        profile = self.profiles.get(policy_profile)
        constraints = await self.graph_resolver.resolve(
            profile=profile,
            context=output.context,
        )

        # Step 3: Compute provenance adjustment
        provenance_adjustment = 0.0
        if self.provenance and provenance_context:
            provenance_adjustment = self.provenance.compute_adjustment(
                provenance_context
            )

        # Step 4: Compute per-axis coherence scores
        axis_scores = self.calculator.compute_axis_scores(
            output_embedding=np.array(output_embedding),
            constraints=constraints,
            profile=profile,
            provenance_adjustment=provenance_adjustment,
        )

        # Step 5: Compute composite CCS
        composite = self.calculator.compute_composite(axis_scores, profile)

        # Step 6: Determine action from thresholds
        action = profile.determine_action(composite, provenance_adjustment)

        elapsed_ms = (time.monotonic() - start) * 1000

        return CoherenceResult(
            composite_score=composite,
            axis_scores=tuple(axis_scores),
            action=action,
            policy_profile=policy_profile,
            constraint_version=constraints.version,
            output_hash=output_hash,
            computed_at=datetime.now(timezone.utc),
            computation_time_ms=elapsed_ms,
            cache_hit=self.cache.last_was_hit,
            provenance_adjustment=provenance_adjustment,
        )

    def _normalize(self, text: str) -> str:
        """Normalize text for deterministic hashing."""
        return " ".join(text.strip().split())
```

### Files Created

| File | Purpose |
|------|---------|
| `src/services/constraint_geometry/__init__.py` | Package initialization |
| `src/services/constraint_geometry/engine.py` | Main CGE orchestrator |
| `src/services/constraint_geometry/constraint_graph.py` | Neptune constraint graph resolver |
| `src/services/constraint_geometry/coherence_calculator.py` | Deterministic coherence computation (NumPy) |
| `src/services/constraint_geometry/embedding_cache.py` | Two-tier cache (LRU + ElastiCache) |
| `src/services/constraint_geometry/policy_profile.py` | Policy profile management |
| `src/services/constraint_geometry/constraint_bundle.py` | Bundle creation/loading for air-gap |
| `src/services/constraint_geometry/contracts.py` | Immutable data contracts |
| `src/services/constraint_geometry/config.py` | Configuration |
| `src/services/constraint_geometry/metrics.py` | CloudWatch metrics publisher |
| `src/services/constraint_geometry/provenance_adapter.py` | ADR-067 trust score integration |
| `src/services/constraint_geometry/version_manager.py` | Constraint versioning and rollback |
| `tests/services/test_constraint_geometry/` | Test suite |
| `deploy/cloudformation/constraint-geometry.yaml` | Infrastructure (DynamoDB, OpenSearch index) |

### CloudFormation Resources

```yaml
# deploy/cloudformation/constraint-geometry.yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Project Aura - Layer 8.6 - Constraint Geometry Engine (Deterministic Coherence)'

Parameters:
  ProjectName:
    Type: String
    Default: aura
  Environment:
    Type: String
    AllowedValues: [dev, qa, staging, prod]

Resources:
  # DynamoDB table for coherence audit records
  CoherenceAuditTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub '${ProjectName}-coherence-audit-${Environment}'
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: assessment_id
          AttributeType: S
        - AttributeName: computed_at
          AttributeType: S
        - AttributeName: output_hash
          AttributeType: S
        - AttributeName: policy_profile
          AttributeType: S
      KeySchema:
        - AttributeName: assessment_id
          KeyType: HASH
        - AttributeName: computed_at
          KeyType: RANGE
      GlobalSecondaryIndexes:
        - IndexName: output-hash-index
          KeySchema:
            - AttributeName: output_hash
              KeyType: HASH
            - AttributeName: computed_at
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
        - IndexName: profile-index
          KeySchema:
            - AttributeName: policy_profile
              KeyType: HASH
            - AttributeName: computed_at
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: true
      SSESpecification:
        SSEEnabled: true
        SSEType: KMS

  # SQS queue for async audit dispatch
  CoherenceAuditQueue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: !Sub '${ProjectName}-coherence-audit-${Environment}'
      VisibilityTimeout: 60
      MessageRetentionPeriod: 1209600
      KmsMasterKeyId: alias/aws/sqs
      RedrivePolicy:
        deadLetterTargetArn: !GetAtt CoherenceAuditDLQ.Arn
        maxReceiveCount: 3

  CoherenceAuditDLQ:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: !Sub '${ProjectName}-coherence-audit-dlq-${Environment}'
      MessageRetentionPeriod: 1209600

  # S3 bucket for versioned constraint bundles
  ConstraintBundleBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub '${ProjectName}-constraint-bundles-${Environment}'
      VersioningConfiguration:
        Status: Enabled
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: aws:kms
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true
      LifecycleConfiguration:
        Rules:
          - Id: RetainVersions90Days
            Status: Enabled
            NoncurrentVersionExpiration:
              NoncurrentDays: 90

  # CloudWatch alarms
  CGELatencyAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: !Sub '${ProjectName}-cge-p95-latency-${Environment}'
      AlarmDescription: CGE P95 latency exceeds 100ms
      MetricName: CGELatency
      Namespace: !Sub '${ProjectName}/CGE'
      Statistic: p95
      Period: 300
      EvaluationPeriods: 3
      Threshold: 100
      ComparisonOperator: GreaterThanThreshold
      Unit: Milliseconds

  CGELowCoherenceAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: !Sub '${ProjectName}-cge-low-coherence-rate-${Environment}'
      AlarmDescription: More than 20% of assessments below escalation threshold
      MetricName: CGEEscalationRate
      Namespace: !Sub '${ProjectName}/CGE'
      Statistic: Average
      Period: 3600
      EvaluationPeriods: 2
      Threshold: 0.20
      ComparisonOperator: GreaterThanThreshold
```

## Performance Targets

| Step | Operation | Cache Hit | Cache Miss |
|------|-----------|-----------|------------|
| 1 | SHA-256 hash | <1ms | <1ms |
| 2 | Embedding lookup (ElastiCache) | 2ms | -- |
| 2b | Embedding computation (Bedrock) | -- | 50-100ms |
| 3 | Constraint resolution (Neptune) | 3ms (cached) | 15ms |
| 4 | Coherence computation (NumPy) | <5ms | <5ms |
| 5 | Threshold comparison | <1ms | <1ms |
| 6 | Audit dispatch (SQS) | 2ms | 2ms |
| **Total (cache hit)** | | **~13ms** | |
| **Total (cache miss)** | | | **~125ms** |

**Targets:** P50 < 25ms, P95 < 50ms, P99 < 100ms

## Cost Analysis

### Monthly Cost (100K agent outputs/day)

| Component | Specification | Monthly Cost |
|-----------|--------------|--------------|
| Neptune (constraint graph) | Existing cluster (shared) | $0 incremental |
| OpenSearch (constraint embeddings) | Existing cluster, new index (~50MB) | $0 incremental |
| ElastiCache (embedding cache) | Shared cache.r6g.large | ~$50 incremental |
| DynamoDB (coherence audit) | PAY_PER_REQUEST, 3M writes/month | ~$3.75 |
| SQS (audit queue) | 3M messages/month | ~$1.20 |
| Bedrock Titan Embeddings | ~5% cache miss, 150K calls/month | ~$1.50 |
| EKS pod (CGE service) | Shared with agent orchestrator | $0 incremental |
| S3 (constraint bundles) | <1GB storage | ~$0.03 |
| CloudWatch (metrics) | ~20 custom metrics | ~$6.00 |
| **Total incremental** | | **~$62/month** |

## Testing Strategy

### Test Pyramid

| Tier | Tests | Coverage |
|------|-------|----------|
| Unit Tests | 150 | Coherence calculator, graph resolver, contracts |
| Determinism Tests | 50 | Same input/constraints = same score (property-based) |
| Integration Tests | 80 | Full pipeline with Neptune + OpenSearch + ElastiCache |
| Provenance Tests | 40 | Trust score adjustment behavior |
| Policy Profile Tests | 30 | Threshold behavior across profiles |
| Air-Gap Tests | 20 | Constraint bundle load/compute without network |
| Performance Tests | 30 | Latency benchmarks, cache hit rates |
| **Total** | **400** | |

### Determinism Validation

```python
# tests/services/test_constraint_geometry/test_determinism.py

class TestDeterministicScoring:
    """Verify that CGE produces identical scores for identical inputs."""

    @pytest.mark.parametrize("iteration", range(100))
    async def test_same_input_same_score(self, cge, sample_output, iteration):
        """Run 100 times - every score must be identical."""
        result = await cge.assess_coherence(
            output=sample_output,
            policy_profile="default",
        )
        if iteration == 0:
            self.__class__.baseline_score = result.composite_score
            self.__class__.baseline_action = result.action
        else:
            assert result.composite_score == self.__class__.baseline_score
            assert result.action == self.__class__.baseline_action

    async def test_different_profiles_different_actions(self, cge, sample_output):
        """Same output may produce different actions under different profiles."""
        default = await cge.assess_coherence(sample_output, "default")
        strict = await cge.assess_coherence(sample_output, "dod-il5")
        # Score is the same (same constraints), but action may differ
        assert default.composite_score == strict.composite_score
        # Stricter profile may require human review for same score
        assert strict.action.value >= default.action.value
```

### Provenance-Aware Weighting Tests

```python
# tests/services/test_constraint_geometry/test_provenance.py

class TestProvenanceWeighting:
    """Verify trust scores affect constraint weights and thresholds."""

    async def test_low_trust_tightens_security(self, cge, sample_output):
        """Low provenance trust should tighten security constraints."""
        high_trust = await cge.assess_coherence(
            output=sample_output,
            provenance_context={"trust_score": 0.95},
        )
        low_trust = await cge.assess_coherence(
            output=sample_output,
            provenance_context={"trust_score": 0.3},
        )
        # Low trust should produce lower composite (tighter constraints)
        assert low_trust.composite_score < high_trust.composite_score
        # Low trust may escalate what high trust auto-executes
        if high_trust.action == CoherenceAction.AUTO_EXECUTE:
            assert low_trust.action in (
                CoherenceAction.AUTO_EXECUTE,
                CoherenceAction.HUMAN_REVIEW,
            )

    async def test_unverified_repo_raises_threshold(self, cge, sample_output):
        """Unverified repository context should raise auto-execute bar."""
        result = await cge.assess_coherence(
            output=sample_output,
            provenance_context={"trust_score": 0.2, "source": "unverified"},
        )
        assert result.provenance_adjustment > 0.0
```

## Implementation Phases

### Phase 1: Core Engine and Contracts (Week 1)

| Task | Deliverable |
|------|-------------|
| Implement contracts.py | ConstraintAxis, CoherenceResult, CoherenceAction |
| Implement coherence_calculator.py | Cosine similarity, harmonic mean, geometric mean |
| Implement embedding_cache.py | SHA-256 hashing, in-process LRU |
| Unit tests | 80 tests (calculator, contracts, cache) |
| Determinism tests | 50 tests (property-based same-input-same-output) |

### Phase 2: Neptune Integration (Week 2)

| Task | Deliverable |
|------|-------------|
| Implement constraint_graph.py | Gremlin traversal for constraint resolution |
| Implement policy_profile.py | Named profiles with per-axis weights |
| Seed Neptune constraint graph | Initial C1-C7 axes + NIST 800-53 rules |
| Integration tests | 40 tests (Neptune + calculator) |

### Phase 3: Provenance and Profiles (Week 3)

| Task | Deliverable |
|------|-------------|
| Implement provenance_adapter.py | ADR-067 trust score integration |
| Implement config.py + metrics.py | Configuration and CloudWatch publishing |
| Create policy profiles | default, dod-il5, developer-sandbox, sox-compliant |
| Provenance tests | 40 tests |
| Profile tests | 30 tests |

### Phase 4: Infrastructure and Air-Gap (Week 4)

| Task | Deliverable |
|------|-------------|
| Deploy CloudFormation template | DynamoDB, SQS, S3, CloudWatch alarms |
| Implement constraint_bundle.py | Export/import for air-gap deployment |
| Implement version_manager.py | Constraint versioning and rollback |
| Air-gap tests | 20 tests |
| Performance benchmarks | 30 tests |

### Phase 5: Pipeline Integration (Week 5)

| Task | Deliverable |
|------|-------------|
| Integrate with agent orchestrator | Post-Constitutional, pre-delivery gate |
| Wire HITL routing | CCS-based escalation to ADR-032 |
| End-to-end testing | Full pipeline with all layers |
| CloudWatch dashboards | CCS distribution, latency, escalation rate |
| Operational runbook | CGE operations documentation |

## GovCloud Compatibility

| Service | GovCloud Available | CGE Usage |
|---------|-------------------|-----------|
| Neptune | Yes (provisioned) | Constraint graph storage |
| OpenSearch | Yes | Constraint embedding storage |
| ElastiCache | Yes | Embedding + score caching |
| EKS | Yes | CGE service hosting |
| DynamoDB | Yes | Coherence audit records |
| S3 | Yes | Constraint bundles |
| SQS | Yes | Async audit dispatch |
| Bedrock | Yes (us-gov-west-1) | Embedding computation (non-hot-path) |
| CloudWatch | Yes | Metrics and alarms |

All resources use `${AWS::Partition}` in ARNs. No commercial-only services required.

## Consequences

### Positive

1. **Deterministic audit trails** - Same output + same constraints = same score, enabling forensic reproducibility
2. **Architectural hallucination barrier** - No incoherent output can propagate without measured constraint coherence
3. **Smarter HITL routing** - Coherence thresholds automate what needs human review vs. auto-execution
4. **Provenance-aware security** - Low-trust context automatically raises the bar for autonomous action
5. **Policy profile flexibility** - Different operational contexts get appropriate constraint tolerances
6. **Air-gap deployment** - Constraint bundles enable disconnected operation
7. **Sub-25ms latency** - No LLM calls in the hot path; pure arithmetic after cached embedding lookup
8. **Low incremental cost** - ~$62/month leveraging existing Neptune, OpenSearch, ElastiCache infrastructure
9. **Government/defense differentiator** - Deterministic discrimination layer that audit frameworks require

### Negative

1. **Constraint curation overhead** - Positive/negative exemplar sets require human curation and quarterly review
2. **Embedding model lock-in** - Changing embedding models requires re-embedding all constraints and clearing caches
3. **Bundle size for air-gap** - ~150MB constraint bundle (larger than a standalone 26MB binary)
4. **Complexity** - Adds a processing step to every agent output path

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Exemplar quality determines accuracy | High | High | Human-curated sets with quarterly review, automated quality metrics |
| Embedding model version change | Medium | High | Version-lock model; re-embed on upgrade; store model version with embeddings |
| Constraint graph complexity growth | Low | Medium | Cache resolved sets per profile; Neptune read replicas; materialized views |
| Adversary gaming CCS scores | Medium | High | Red team exercises; probabilistic layers (ADR-065, ADR-063) catch this first |
| Air-gap bundle staleness | Medium | Medium | Bundle expiration dates; warnings on expired bundles; automated refresh |

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Determinism | 100% | Same input/constraints produce identical CCS across 10,000 runs |
| P50 Latency | <25ms | CloudWatch metrics (cache-hit path) |
| P95 Latency | <50ms | CloudWatch metrics |
| Cache Hit Rate | >95% | ElastiCache metrics after warm-up |
| HITL Reduction | >30% | Fewer manual reviews due to high-coherence auto-execution |
| False Escalation Rate | <5% | Human reviewers agree with auto-execute when CCS >= threshold |
| Constraint Coverage | 7/7 axes | All axes have at least 10 constraint rules with exemplars |

## References

1. ADR-065: Semantic Guardrails Engine (probabilistic input discrimination)
2. ADR-063: Constitutional AI Integration (probabilistic output critique)
3. ADR-067: Context Provenance and Integrity (trust scoring)
4. ADR-032: Configurable Autonomy Framework (HITL workflow)
5. ADR-066: Agent Capability Governance (operational bounds)
6. ADR-078: Air-Gapped and Edge Deployment (offline constraint bundles)
7. ARBITER: Deterministic Semantic Coherence Measurement (external reference)
8. NIST SP 800-53 Rev. 5: Security and Privacy Controls for Information Systems
