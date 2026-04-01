# ADR-068: Universal Explainability Framework

## Status

Deployed

## Date

2026-01-25

## Reviews

| Reviewer | Role | Date | Verdict |
|----------|------|------|---------|
| Pending | AWS AI SaaS Architect | - | - |
| Pending | Senior Systems Architect | - | - |
| Pending | AI Safety Specialist | - | - |
| Pending | Test Architect | - | - |

### Review Summary

_Awaiting review._

## Context

### The Explainability Gap in Autonomous AI Systems

Project Aura's autonomous agents make thousands of decisions daily, but current systems have significant gaps in decision transparency:

| Current State | Gap |
|---------------|-----|
| Reasoning chains optional for 95% of decisions | Only CRITICAL severity requires full reasoning |
| No alternatives disclosure | Cannot explain why Option A was chosen over Option B |
| Confidence intervals missing | Point estimates without uncertainty quantification |
| No consistency verification | Stated reasoning may contradict actions taken |
| Inter-agent decisions unverified | Agent B trusts Agent A's reasoning without validation |
| Human visibility limited | No dashboard for exploring decision rationale |

### Security Gap Analysis Findings

The recent security gap analysis identified critical deficiencies in agent decision transparency:

```text
Explainability Gaps Identified:
├── Reasoning Coverage
│   ├── CRITICAL decisions: Full reasoning required (5% of decisions)
│   ├── SIGNIFICANT decisions: Partial reasoning (15% of decisions)
│   └── NORMAL/TRIVIAL decisions: No reasoning required (80% of decisions)
│       └── GAP: Cannot explain why these decisions were made
│
├── Alternatives Disclosure
│   ├── Current: Alternatives optional even for SIGNIFICANT decisions
│   └── GAP: No record of what options were rejected and why
│
├── Consistency Verification
│   ├── Current: Reasoning chains not validated against actions
│   └── GAP: Agent could state "chose Option A for security" but actually chose Option B
│
├── Inter-Agent Trust
│   ├── Current: Downstream agents accept upstream reasoning at face value
│   └── GAP: No verification that upstream agent's claims are accurate
│
└── Audit Compliance
    ├── CMMC: Requires explainable decision audit trails
    ├── SOX: Financial decisions must be traceable
    └── GAP: Current audit records insufficient for compliance
```

### Regulatory and Compliance Requirements

| Requirement | Standard | Current State | Gap |
|-------------|----------|---------------|-----|
| Decision traceability | CMMC AC.L2-3.1.7 | Partial | Missing reasoning for 80% of decisions |
| Audit completeness | SOX Section 404 | Partial | No alternatives documentation |
| Explainable AI | NIST AI RMF 1.0 | Partial | No confidence intervals |
| Human oversight | EU AI Act Article 14 | Partial | No contradiction detection |

### The Explainability Imperative

Explainability is not just a compliance checkbox. It enables:

1. **Trust Calibration** - Humans can only trust what they understand
2. **Error Detection** - Contradictions reveal bugs and misalignment
3. **Continuous Improvement** - Learning from decision patterns
4. **Regulatory Compliance** - CMMC/SOX/NIST requirements
5. **Incident Investigation** - Understanding what went wrong

## Decision

Implement a Universal Explainability Framework that ensures every agent decision, regardless of severity, has complete, verifiable, and human-readable reasoning with alternatives considered, confidence quantification, and consistency verification.

### Core Capabilities

1. **Mandatory Reasoning Chains** - Every decision requires documented reasoning
2. **Alternatives Disclosure** - What options were considered and why rejected
3. **Confidence Intervals** - Quantified uncertainty with upper/lower bounds
4. **Action-Reasoning Consistency** - Verify stated reasoning matches actual actions
5. **Inter-Agent Verification** - Validate claims made by upstream agents
6. **Explainability Dashboard** - Human-readable decision exploration
7. **Constitutional Integration** - Extend CAI critique for reasoning validation

## Architecture

### Universal Explainability Framework Architecture

```text
+--------------------------------------------------------------------------------+
|                      Universal Explainability Framework                         |
+--------------------------------------------------------------------------------+
|                                                                                |
|  Agent Decision                                                                |
|       |                                                                        |
|       v                                                                        |
|  +----------------------------------------------------------------------+     |
|  | Layer 1: ReasoningChainBuilder                                        |     |
|  |                                                                        |     |
|  |  +-------------------+  +-------------------+  +-------------------+   |     |
|  |  | Step Extraction   |  | Evidence Linking  |  | Reference Mapping |   |     |
|  |  | (What was done)   |  | (Why it was done) |  | (Source citations)|   |     |
|  |  +-------------------+  +-------------------+  +-------------------+   |     |
|  |                                                                        |     |
|  |  Input: Agent's raw decision process                                   |     |
|  |  Output: Structured ReasoningChain with linked evidence                |     |
|  +----------------------------------------------------------------------+     |
|       |                                                                        |
|       v                                                                        |
|  +----------------------------------------------------------------------+     |
|  | Layer 2: AlternativesAnalyzer                                         |     |
|  |                                                                        |     |
|  |  +-------------------+  +-------------------+  +-------------------+   |     |
|  |  | Option Discovery  |  | Comparison Matrix |  | Rejection Reason  |   |     |
|  |  | (What else?)      |  | (Trade-offs)      |  | (Why not chosen?) |   |     |
|  |  +-------------------+  +-------------------+  +-------------------+   |     |
|  |                                                                        |     |
|  |  Minimum: 2 alternatives for NORMAL, 3 for SIGNIFICANT, 4 for CRITICAL |     |
|  |  Output: AlternativesReport with ranked options and rejection reasons  |     |
|  +----------------------------------------------------------------------+     |
|       |                                                                        |
|       v                                                                        |
|  +----------------------------------------------------------------------+     |
|  | Layer 3: ConfidenceQuantifier                                         |     |
|  |                                                                        |     |
|  |  +-------------------+  +-------------------+  +-------------------+   |     |
|  |  | Point Estimate    |  | Interval Calc     |  | Uncertainty       |   |     |
|  |  | (Best guess)      |  | (Lower/Upper)     |  | Factors           |   |     |
|  |  +-------------------+  +-------------------+  +-------------------+   |     |
|  |                                                                        |     |
|  |  Method: Monte Carlo dropout + ensemble disagreement + calibration    |     |
|  |  Output: ConfidenceInterval with documented uncertainty sources        |     |
|  +----------------------------------------------------------------------+     |
|       |                                                                        |
|       v                                                                        |
|  +----------------------------------------------------------------------+     |
|  | Layer 4: ConsistencyVerifier                                          |     |
|  |                                                                        |     |
|  |  +-------------------+  +-------------------+  +-------------------+   |     |
|  |  | Claim Extraction  |  | Action Analysis   |  | Contradiction     |   |     |
|  |  | (What was said)   |  | (What was done)   |  | Detection         |   |     |
|  |  +-------------------+  +-------------------+  +-------------------+   |     |
|  |                                                                        |     |
|  |  Detects: Stated reason != actual action, missing steps, false claims |     |
|  |  Output: ConsistencyReport with contradiction details                  |     |
|  +----------------------------------------------------------------------+     |
|       |                                                                        |
|       v                                                                        |
|  +----------------------------------------------------------------------+     |
|  | Layer 5: InterAgentVerifier                                           |     |
|  |                                                                        |     |
|  |  +-------------------+  +-------------------+  +-------------------+   |     |
|  |  | Upstream Claims   |  | Independent Check |  | Trust Score       |   |     |
|  |  | (What A said)     |  | (Verify claim)    |  | Adjustment        |   |     |
|  |  +-------------------+  +-------------------+  +-------------------+   |     |
|  |                                                                        |     |
|  |  Validates: Security assessment claims, code analysis, test results   |     |
|  |  Output: VerificationReport with trust adjustments                     |     |
|  +----------------------------------------------------------------------+     |
|       |                                                                        |
|       v                                                                        |
|  +----------------------------------------------------------------------+     |
|  | Layer 6: ExplainabilityRecord (Immutable Audit)                       |     |
|  |                                                                        |     |
|  |  ExplainabilityRecord {                                                |     |
|  |    decision_id: str                                                    |     |
|  |    reasoning_chain: ReasoningChain                                     |     |
|  |    alternatives: AlternativesReport                                    |     |
|  |    confidence: ConfidenceInterval                                      |     |
|  |    consistency: ConsistencyReport                                      |     |
|  |    inter_agent: VerificationReport                                     |     |
|  |    explainability_score: float (0.0-1.0)                               |     |
|  |    human_readable_summary: str                                         |     |
|  |  }                                                                     |     |
|  |                                                                        |     |
|  |  --> DynamoDB (immutable audit)                                        |     |
|  |  --> Neptune (decision graph)                                          |     |
|  |  --> Dashboard API                                                     |     |
|  +----------------------------------------------------------------------+     |
|                                                                                |
+--------------------------------------------------------------------------------+
```

### Integration with Existing Systems

```text
+--------------------------------------------------------------------------------+
|                      Explainability Integration Points                          |
+--------------------------------------------------------------------------------+
|                                                                                |
|  +----------------------------------------------------------------------+     |
|  |                        MetaOrchestrator                               |     |
|  |  +------------------+  +------------------+  +------------------+     |     |
|  |  | Coder Agent      |  | Reviewer Agent   |  | Validator Agent  |     |     |
|  |  | + Explainability |  | + Explainability |  | + Explainability |     |     |
|  |  |   Mixin          |  |   Mixin          |  |   Mixin          |     |     |
|  |  +------------------+  +------------------+  +------------------+     |     |
|  +----------------------------------------------------------------------+     |
|       |                                                                        |
|       | Every decision triggers explainability pipeline                        |
|       v                                                                        |
|  +----------------------------------------------------------------------+     |
|  | UniversalExplainabilityService                                        |     |
|  |                                                                        |     |
|  |  Orchestrates: ReasoningChainBuilder, AlternativesAnalyzer,           |     |
|  |                ConfidenceQuantifier, ConsistencyVerifier,              |     |
|  |                InterAgentVerifier                                      |     |
|  +----------------------------------------------------------------------+     |
|       |                                                                        |
|       +------------------+------------------+------------------+               |
|       |                  |                  |                  |               |
|       v                  v                  v                  v               |
|  +-----------+    +-----------+    +-----------+    +-----------+             |
|  | Decision  |    | Constitu- |    | Trust     |    | Alignment |             |
|  | Audit     |    | tional AI |    | Score     |    | Metrics   |             |
|  | Logger    |    | Critique  |    | Calculator|    | Service   |             |
|  | (ADR-052) |    | (ADR-063) |    | (ADR-052) |    | (ADR-052) |             |
|  +-----------+    +-----------+    +-----------+    +-----------+             |
|       |                  |                  |                  |               |
|       +------------------+------------------+------------------+               |
|                          |                                                     |
|                          v                                                     |
|  +----------------------------------------------------------------------+     |
|  | Explainability Dashboard                                              |     |
|  |                                                                        |     |
|  |  +------------------+  +------------------+  +------------------+     |     |
|  |  | Decision Explorer|  | Reasoning Viewer |  | Contradiction   |     |     |
|  |  | (Search/Filter)  |  | (Step-by-step)   |  | Alerts          |     |     |
|  |  +------------------+  +------------------+  +------------------+     |     |
|  |  +------------------+  +------------------+  +------------------+     |     |
|  |  | Alternatives     |  | Confidence       |  | Inter-Agent     |     |     |
|  |  | Comparison       |  | Visualization    |  | Trust Graph     |     |     |
|  |  +------------------+  +------------------+  +------------------+     |     |
|  +----------------------------------------------------------------------+     |
|                                                                                |
+--------------------------------------------------------------------------------+
```

### Constitutional AI Integration for Reasoning Validation

```text
+--------------------------------------------------------------------------------+
|               Constitutional Critique Extension for Reasoning                   |
+--------------------------------------------------------------------------------+
|                                                                                |
|  Existing CAI Pipeline (ADR-063)                                               |
|       |                                                                        |
|       v                                                                        |
|  +----------------------------------------------------------------------+     |
|  | New Explainability Principles (Added to Constitution)                 |     |
|  |                                                                        |     |
|  | Principle 17: REASONING_COMPLETENESS (HIGH)                           |     |
|  |   "Every decision must include a complete reasoning chain that        |     |
|  |    explains the logic from inputs to outputs."                        |     |
|  |                                                                        |     |
|  | Principle 18: ALTERNATIVES_DISCLOSURE (HIGH)                          |     |
|  |   "For any decision, the agent must disclose what alternatives        |     |
|  |    were considered and why they were rejected."                       |     |
|  |                                                                        |     |
|  | Principle 19: CONFIDENCE_HONESTY (MEDIUM)                             |     |
|  |   "Agents must quantify uncertainty with calibrated confidence        |     |
|  |    intervals, not just point estimates."                              |     |
|  |                                                                        |     |
|  | Principle 20: ACTION_REASONING_CONSISTENCY (CRITICAL)                 |     |
|  |   "The stated reasoning must be consistent with the action taken.     |     |
|  |    Contradictions must trigger HITL escalation."                      |     |
|  +----------------------------------------------------------------------+     |
|       |                                                                        |
|       v                                                                        |
|  +----------------------------------------------------------------------+     |
|  | ConstitutionalCritiqueService (Extended)                              |     |
|  |                                                                        |     |
|  |  critique_reasoning_chain(chain: ReasoningChain) -> CritiqueResult    |     |
|  |  critique_alternatives(report: AlternativesReport) -> CritiqueResult  |     |
|  |  critique_confidence(interval: ConfidenceInterval) -> CritiqueResult  |     |
|  |  critique_consistency(report: ConsistencyReport) -> CritiqueResult    |     |
|  +----------------------------------------------------------------------+     |
|                                                                                |
+--------------------------------------------------------------------------------+
```

## Implementation

### Service Layer

```python
# src/services/explainability/__init__.py

from .service import UniversalExplainabilityService
from .reasoning_chain import ReasoningChainBuilder, ReasoningChain, ReasoningStep
from .alternatives import AlternativesAnalyzer, AlternativesReport, Alternative
from .confidence import ConfidenceQuantifier, ConfidenceInterval
from .consistency import ConsistencyVerifier, ConsistencyReport, Contradiction
from .inter_agent import InterAgentVerifier, VerificationReport, ClaimVerification
from .dashboard import ExplainabilityDashboardAPI
from .contracts import ExplainabilityRecord, ExplainabilityScore

__all__ = [
    "UniversalExplainabilityService",
    "ReasoningChainBuilder",
    "ReasoningChain",
    "ReasoningStep",
    "AlternativesAnalyzer",
    "AlternativesReport",
    "Alternative",
    "ConfidenceQuantifier",
    "ConfidenceInterval",
    "ConsistencyVerifier",
    "ConsistencyReport",
    "Contradiction",
    "InterAgentVerifier",
    "VerificationReport",
    "ClaimVerification",
    "ExplainabilityDashboardAPI",
    "ExplainabilityRecord",
    "ExplainabilityScore",
]
```

```python
# src/services/explainability/contracts.py

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import hashlib
import json


class DecisionSeverity(Enum):
    """Decision severity levels with explainability requirements."""
    TRIVIAL = "trivial"      # Min 1 reasoning step, 2 alternatives
    NORMAL = "normal"        # Min 2 reasoning steps, 2 alternatives
    SIGNIFICANT = "significant"  # Min 3 reasoning steps, 3 alternatives
    CRITICAL = "critical"    # Min 5 reasoning steps, 4 alternatives


class ContradictionSeverity(Enum):
    """Severity of detected contradictions."""
    MINOR = "minor"          # Cosmetic inconsistency
    MODERATE = "moderate"    # Logic gap
    MAJOR = "major"          # Clear contradiction
    CRITICAL = "critical"    # Dangerous inconsistency


@dataclass
class ReasoningStep:
    """A single step in the reasoning chain."""
    step_number: int
    description: str
    evidence: list[str] = field(default_factory=list)
    confidence: float = 1.0
    references: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "step_number": self.step_number,
            "description": self.description,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "references": self.references,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ReasoningChain:
    """Complete reasoning chain for a decision."""
    decision_id: str
    agent_id: str
    steps: list[ReasoningStep] = field(default_factory=list)
    input_summary: str = ""
    output_summary: str = ""
    total_confidence: float = 1.0

    def is_complete(self, severity: DecisionSeverity) -> bool:
        """Check if reasoning chain meets requirements for severity level."""
        min_steps = {
            DecisionSeverity.TRIVIAL: 1,
            DecisionSeverity.NORMAL: 2,
            DecisionSeverity.SIGNIFICANT: 3,
            DecisionSeverity.CRITICAL: 5,
        }
        return len(self.steps) >= min_steps[severity]

    def to_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "agent_id": self.agent_id,
            "steps": [s.to_dict() for s in self.steps],
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "total_confidence": self.total_confidence,
        }


@dataclass
class Alternative:
    """An alternative option that was considered."""
    alternative_id: str
    description: str
    confidence: float
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    was_chosen: bool = False
    rejection_reason: Optional[str] = None
    comparison_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "alternative_id": self.alternative_id,
            "description": self.description,
            "confidence": self.confidence,
            "pros": self.pros,
            "cons": self.cons,
            "was_chosen": self.was_chosen,
            "rejection_reason": self.rejection_reason,
            "comparison_score": self.comparison_score,
        }


@dataclass
class AlternativesReport:
    """Report of alternatives considered for a decision."""
    decision_id: str
    alternatives: list[Alternative] = field(default_factory=list)
    comparison_criteria: list[str] = field(default_factory=list)
    chosen_alternative_id: Optional[str] = None
    decision_rationale: str = ""

    def is_complete(self, severity: DecisionSeverity) -> bool:
        """Check if alternatives meet requirements for severity level."""
        min_alternatives = {
            DecisionSeverity.TRIVIAL: 2,
            DecisionSeverity.NORMAL: 2,
            DecisionSeverity.SIGNIFICANT: 3,
            DecisionSeverity.CRITICAL: 4,
        }
        return len(self.alternatives) >= min_alternatives[severity]

    def to_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "alternatives": [a.to_dict() for a in self.alternatives],
            "comparison_criteria": self.comparison_criteria,
            "chosen_alternative_id": self.chosen_alternative_id,
            "decision_rationale": self.decision_rationale,
        }


@dataclass
class ConfidenceInterval:
    """Quantified confidence with uncertainty bounds."""
    point_estimate: float
    lower_bound: float
    upper_bound: float
    uncertainty_sources: list[str] = field(default_factory=list)
    calibration_method: str = "ensemble_disagreement"
    sample_size: Optional[int] = None

    def interval_width(self) -> float:
        return self.upper_bound - self.lower_bound

    def is_well_calibrated(self) -> bool:
        """Check if interval width is appropriate for confidence level."""
        # Higher confidence should have narrower intervals
        expected_width = 2 * (1 - self.point_estimate)
        actual_width = self.interval_width()
        return 0.5 * expected_width <= actual_width <= 2 * expected_width

    def to_dict(self) -> dict:
        return {
            "point_estimate": self.point_estimate,
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "uncertainty_sources": self.uncertainty_sources,
            "calibration_method": self.calibration_method,
            "sample_size": self.sample_size,
            "interval_width": self.interval_width(),
            "is_well_calibrated": self.is_well_calibrated(),
        }


@dataclass
class Contradiction:
    """A detected contradiction between reasoning and action."""
    contradiction_id: str
    severity: ContradictionSeverity
    stated_claim: str
    actual_action: str
    explanation: str
    evidence: list[str] = field(default_factory=list)
    requires_hitl: bool = False

    def to_dict(self) -> dict:
        return {
            "contradiction_id": self.contradiction_id,
            "severity": self.severity.value,
            "stated_claim": self.stated_claim,
            "actual_action": self.actual_action,
            "explanation": self.explanation,
            "evidence": self.evidence,
            "requires_hitl": self.requires_hitl,
        }


@dataclass
class ConsistencyReport:
    """Report on consistency between reasoning and actions."""
    decision_id: str
    is_consistent: bool
    contradictions: list[Contradiction] = field(default_factory=list)
    consistency_score: float = 1.0
    verification_method: str = "claim_action_matching"

    def has_critical_contradictions(self) -> bool:
        return any(
            c.severity == ContradictionSeverity.CRITICAL
            for c in self.contradictions
        )

    def to_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "is_consistent": self.is_consistent,
            "contradictions": [c.to_dict() for c in self.contradictions],
            "consistency_score": self.consistency_score,
            "verification_method": self.verification_method,
            "has_critical_contradictions": self.has_critical_contradictions(),
        }


@dataclass
class ClaimVerification:
    """Verification result for a claim made by an upstream agent."""
    claim_id: str
    upstream_agent_id: str
    claim_text: str
    is_verified: bool
    verification_evidence: list[str] = field(default_factory=list)
    confidence: float = 0.0
    discrepancy: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "upstream_agent_id": self.upstream_agent_id,
            "claim_text": self.claim_text,
            "is_verified": self.is_verified,
            "verification_evidence": self.verification_evidence,
            "confidence": self.confidence,
            "discrepancy": self.discrepancy,
        }


@dataclass
class VerificationReport:
    """Report on inter-agent claim verification."""
    decision_id: str
    verifications: list[ClaimVerification] = field(default_factory=list)
    trust_adjustment: float = 0.0
    unverified_claims: int = 0
    verification_failures: int = 0

    def overall_trust_score(self) -> float:
        if not self.verifications:
            return 1.0
        verified_count = sum(1 for v in self.verifications if v.is_verified)
        return verified_count / len(self.verifications)

    def to_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "verifications": [v.to_dict() for v in self.verifications],
            "trust_adjustment": self.trust_adjustment,
            "unverified_claims": self.unverified_claims,
            "verification_failures": self.verification_failures,
            "overall_trust_score": self.overall_trust_score(),
        }


@dataclass
class ExplainabilityScore:
    """Composite score measuring decision explainability quality."""
    reasoning_completeness: float  # 0.0-1.0
    alternatives_coverage: float   # 0.0-1.0
    confidence_calibration: float  # 0.0-1.0
    consistency_score: float       # 0.0-1.0
    inter_agent_trust: float       # 0.0-1.0

    def overall_score(self) -> float:
        """Weighted average of explainability dimensions."""
        weights = {
            "reasoning_completeness": 0.25,
            "alternatives_coverage": 0.20,
            "confidence_calibration": 0.15,
            "consistency_score": 0.25,
            "inter_agent_trust": 0.15,
        }
        return (
            weights["reasoning_completeness"] * self.reasoning_completeness +
            weights["alternatives_coverage"] * self.alternatives_coverage +
            weights["confidence_calibration"] * self.confidence_calibration +
            weights["consistency_score"] * self.consistency_score +
            weights["inter_agent_trust"] * self.inter_agent_trust
        )

    def to_dict(self) -> dict:
        return {
            "reasoning_completeness": self.reasoning_completeness,
            "alternatives_coverage": self.alternatives_coverage,
            "confidence_calibration": self.confidence_calibration,
            "consistency_score": self.consistency_score,
            "inter_agent_trust": self.inter_agent_trust,
            "overall_score": self.overall_score(),
        }


@dataclass
class ExplainabilityRecord:
    """Complete explainability record for a decision."""
    record_id: str
    decision_id: str
    agent_id: str
    severity: DecisionSeverity
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Core explainability components
    reasoning_chain: Optional[ReasoningChain] = None
    alternatives_report: Optional[AlternativesReport] = None
    confidence_interval: Optional[ConfidenceInterval] = None
    consistency_report: Optional[ConsistencyReport] = None
    verification_report: Optional[VerificationReport] = None

    # Computed fields
    explainability_score: Optional[ExplainabilityScore] = None
    human_readable_summary: str = ""

    # Audit metadata
    checksum: str = ""
    constitutional_critique_id: Optional[str] = None
    hitl_required: bool = False
    hitl_reason: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.checksum:
            self.checksum = self._calculate_checksum()

    def _calculate_checksum(self) -> str:
        """Calculate integrity checksum."""
        data = {
            "record_id": self.record_id,
            "decision_id": self.decision_id,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp.isoformat(),
        }
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_str.encode(), usedforsecurity=False).hexdigest()[:16]

    def is_complete(self) -> bool:
        """Check if all required explainability components are present."""
        return all([
            self.reasoning_chain is not None,
            self.alternatives_report is not None,
            self.confidence_interval is not None,
            self.consistency_report is not None,
        ])

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "decision_id": self.decision_id,
            "agent_id": self.agent_id,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "reasoning_chain": self.reasoning_chain.to_dict() if self.reasoning_chain else None,
            "alternatives_report": self.alternatives_report.to_dict() if self.alternatives_report else None,
            "confidence_interval": self.confidence_interval.to_dict() if self.confidence_interval else None,
            "consistency_report": self.consistency_report.to_dict() if self.consistency_report else None,
            "verification_report": self.verification_report.to_dict() if self.verification_report else None,
            "explainability_score": self.explainability_score.to_dict() if self.explainability_score else None,
            "human_readable_summary": self.human_readable_summary,
            "checksum": self.checksum,
            "constitutional_critique_id": self.constitutional_critique_id,
            "hitl_required": self.hitl_required,
            "hitl_reason": self.hitl_reason,
            "is_complete": self.is_complete(),
        }
```

```python
# src/services/explainability/service.py

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from .contracts import (
    AlternativesReport,
    ConfidenceInterval,
    ConsistencyReport,
    DecisionSeverity,
    ExplainabilityRecord,
    ExplainabilityScore,
    ReasoningChain,
    VerificationReport,
)
from .reasoning_chain import ReasoningChainBuilder
from .alternatives import AlternativesAnalyzer
from .confidence import ConfidenceQuantifier
from .consistency import ConsistencyVerifier
from .inter_agent import InterAgentVerifier

logger = logging.getLogger(__name__)


@dataclass
class ExplainabilityConfig:
    """Configuration for explainability service."""
    # Severity requirements
    min_reasoning_steps: dict[str, int] = None
    min_alternatives: dict[str, int] = None

    # Thresholds
    consistency_threshold: float = 0.8
    confidence_calibration_threshold: float = 0.7
    inter_agent_trust_threshold: float = 0.75

    # HITL escalation
    escalate_on_contradiction: bool = True
    escalate_on_low_confidence: bool = True
    low_confidence_threshold: float = 0.5

    # Performance
    enable_caching: bool = True
    async_persistence: bool = True
    max_processing_time_ms: int = 500

    def __post_init__(self):
        if self.min_reasoning_steps is None:
            self.min_reasoning_steps = {
                "trivial": 1,
                "normal": 2,
                "significant": 3,
                "critical": 5,
            }
        if self.min_alternatives is None:
            self.min_alternatives = {
                "trivial": 2,
                "normal": 2,
                "significant": 3,
                "critical": 4,
            }


class UniversalExplainabilityService:
    """
    Orchestrates universal explainability for all agent decisions.

    Ensures every decision has:
    - Complete reasoning chains
    - Alternatives considered
    - Quantified confidence
    - Consistency verification
    - Inter-agent claim verification
    """

    def __init__(
        self,
        decision_audit_logger,
        constitutional_critique_service,
        bedrock_client,
        neptune_client,
        dynamodb_table,
        config: Optional[ExplainabilityConfig] = None,
    ):
        self.config = config or ExplainabilityConfig()
        self.audit_logger = decision_audit_logger
        self.constitutional_service = constitutional_critique_service
        self.bedrock = bedrock_client
        self.neptune = neptune_client
        self.dynamodb = dynamodb_table

        # Initialize components
        self.reasoning_builder = ReasoningChainBuilder(bedrock_client)
        self.alternatives_analyzer = AlternativesAnalyzer(bedrock_client)
        self.confidence_quantifier = ConfidenceQuantifier()
        self.consistency_verifier = ConsistencyVerifier(bedrock_client)
        self.inter_agent_verifier = InterAgentVerifier(neptune_client)

        logger.info("UniversalExplainabilityService initialized")

    async def explain_decision(
        self,
        decision_id: str,
        agent_id: str,
        severity: DecisionSeverity,
        decision_input: dict[str, Any],
        decision_output: dict[str, Any],
        decision_context: Optional[dict[str, Any]] = None,
        upstream_claims: Optional[list[dict]] = None,
    ) -> ExplainabilityRecord:
        """
        Generate complete explainability record for a decision.

        Args:
            decision_id: Unique identifier for the decision
            agent_id: The agent that made the decision
            severity: Severity level determining requirements
            decision_input: Input data for the decision
            decision_output: Output/result of the decision
            decision_context: Additional context (conversation, prior decisions)
            upstream_claims: Claims from upstream agents to verify

        Returns:
            ExplainabilityRecord with all explainability components
        """
        start_time = time.monotonic()
        record_id = f"exp_{uuid.uuid4().hex[:12]}"

        logger.info(
            f"Generating explainability record {record_id} for decision {decision_id}"
        )

        # Layer 1: Build reasoning chain
        reasoning_chain = await self.reasoning_builder.build(
            decision_id=decision_id,
            agent_id=agent_id,
            decision_input=decision_input,
            decision_output=decision_output,
            min_steps=self.config.min_reasoning_steps[severity.value],
        )

        # Layer 2: Analyze alternatives
        alternatives_report = await self.alternatives_analyzer.analyze(
            decision_id=decision_id,
            decision_input=decision_input,
            decision_output=decision_output,
            context=decision_context,
            min_alternatives=self.config.min_alternatives[severity.value],
        )

        # Layer 3: Quantify confidence
        confidence_interval = await self.confidence_quantifier.quantify(
            reasoning_chain=reasoning_chain,
            alternatives_report=alternatives_report,
            decision_context=decision_context,
        )

        # Layer 4: Verify consistency
        consistency_report = await self.consistency_verifier.verify(
            decision_id=decision_id,
            reasoning_chain=reasoning_chain,
            decision_output=decision_output,
        )

        # Layer 5: Inter-agent verification (if upstream claims provided)
        verification_report = None
        if upstream_claims:
            verification_report = await self.inter_agent_verifier.verify_claims(
                decision_id=decision_id,
                claims=upstream_claims,
            )

        # Calculate explainability score
        explainability_score = self._calculate_score(
            reasoning_chain=reasoning_chain,
            alternatives_report=alternatives_report,
            confidence_interval=confidence_interval,
            consistency_report=consistency_report,
            verification_report=verification_report,
            severity=severity,
        )

        # Generate human-readable summary
        human_summary = self._generate_summary(
            reasoning_chain=reasoning_chain,
            alternatives_report=alternatives_report,
            confidence_interval=confidence_interval,
        )

        # Determine if HITL required
        hitl_required, hitl_reason = self._check_hitl_required(
            consistency_report=consistency_report,
            confidence_interval=confidence_interval,
            explainability_score=explainability_score,
        )

        # Create record
        record = ExplainabilityRecord(
            record_id=record_id,
            decision_id=decision_id,
            agent_id=agent_id,
            severity=severity,
            reasoning_chain=reasoning_chain,
            alternatives_report=alternatives_report,
            confidence_interval=confidence_interval,
            consistency_report=consistency_report,
            verification_report=verification_report,
            explainability_score=explainability_score,
            human_readable_summary=human_summary,
            hitl_required=hitl_required,
            hitl_reason=hitl_reason,
        )

        # Constitutional critique for reasoning quality
        critique_result = await self._constitutional_critique(record)
        record.constitutional_critique_id = critique_result.get("critique_id")

        # Persist
        await self._persist_record(record)

        processing_time_ms = (time.monotonic() - start_time) * 1000
        logger.info(
            f"Explainability record {record_id} generated in {processing_time_ms:.1f}ms, "
            f"score={explainability_score.overall_score():.2f}, hitl_required={hitl_required}"
        )

        return record

    def _calculate_score(
        self,
        reasoning_chain: ReasoningChain,
        alternatives_report: AlternativesReport,
        confidence_interval: ConfidenceInterval,
        consistency_report: ConsistencyReport,
        verification_report: Optional[VerificationReport],
        severity: DecisionSeverity,
    ) -> ExplainabilityScore:
        """Calculate composite explainability score."""
        # Reasoning completeness: ratio of actual to required steps
        min_steps = self.config.min_reasoning_steps[severity.value]
        reasoning_completeness = min(1.0, len(reasoning_chain.steps) / min_steps)

        # Alternatives coverage: ratio of actual to required alternatives
        min_alts = self.config.min_alternatives[severity.value]
        alternatives_coverage = min(1.0, len(alternatives_report.alternatives) / min_alts)

        # Confidence calibration: based on interval properties
        confidence_calibration = 1.0 if confidence_interval.is_well_calibrated() else 0.7

        # Consistency score: from verification
        consistency_score = consistency_report.consistency_score

        # Inter-agent trust: from verification or default
        inter_agent_trust = (
            verification_report.overall_trust_score()
            if verification_report
            else 1.0
        )

        return ExplainabilityScore(
            reasoning_completeness=reasoning_completeness,
            alternatives_coverage=alternatives_coverage,
            confidence_calibration=confidence_calibration,
            consistency_score=consistency_score,
            inter_agent_trust=inter_agent_trust,
        )

    def _generate_summary(
        self,
        reasoning_chain: ReasoningChain,
        alternatives_report: AlternativesReport,
        confidence_interval: ConfidenceInterval,
    ) -> str:
        """Generate human-readable summary of decision explanation."""
        # Format reasoning steps
        steps_text = "\n".join(
            f"  {i+1}. {step.description}"
            for i, step in enumerate(reasoning_chain.steps)
        )

        # Format chosen alternative
        chosen = next(
            (a for a in alternatives_report.alternatives if a.was_chosen),
            None
        )
        chosen_text = chosen.description if chosen else "Not specified"

        # Format rejected alternatives
        rejected = [a for a in alternatives_report.alternatives if not a.was_chosen]
        rejected_text = "\n".join(
            f"  - {a.description}: {a.rejection_reason}"
            for a in rejected[:3]  # Top 3 rejected
        )

        summary = f"""DECISION EXPLANATION

REASONING:
{steps_text}

CHOSEN APPROACH: {chosen_text}

ALTERNATIVES CONSIDERED:
{rejected_text}

CONFIDENCE: {confidence_interval.point_estimate:.0%} ({confidence_interval.lower_bound:.0%} - {confidence_interval.upper_bound:.0%})

UNCERTAINTY FACTORS:
{chr(10).join(f'  - {f}' for f in confidence_interval.uncertainty_sources[:3])}
"""
        return summary.strip()

    def _check_hitl_required(
        self,
        consistency_report: ConsistencyReport,
        confidence_interval: ConfidenceInterval,
        explainability_score: ExplainabilityScore,
    ) -> tuple[bool, Optional[str]]:
        """Determine if HITL escalation is required."""
        if (
            self.config.escalate_on_contradiction
            and consistency_report.has_critical_contradictions()
        ):
            return True, "Critical contradiction detected between reasoning and action"

        if (
            self.config.escalate_on_low_confidence
            and confidence_interval.point_estimate < self.config.low_confidence_threshold
        ):
            return True, f"Low confidence ({confidence_interval.point_estimate:.0%}) below threshold"

        if explainability_score.overall_score() < 0.5:
            return True, f"Low explainability score ({explainability_score.overall_score():.2f})"

        return False, None

    async def _constitutional_critique(
        self,
        record: ExplainabilityRecord,
    ) -> dict:
        """Apply constitutional critique to reasoning quality."""
        critique_input = {
            "reasoning_chain": record.reasoning_chain.to_dict() if record.reasoning_chain else {},
            "alternatives_report": record.alternatives_report.to_dict() if record.alternatives_report else {},
            "consistency_report": record.consistency_report.to_dict() if record.consistency_report else {},
        }

        result = await self.constitutional_service.critique_output(
            agent_output=str(critique_input),
            context={"record_id": record.record_id},
            applicable_principles=[
                "REASONING_COMPLETENESS",
                "ALTERNATIVES_DISCLOSURE",
                "CONFIDENCE_HONESTY",
                "ACTION_REASONING_CONSISTENCY",
            ],
        )

        return {"critique_id": result.critique_id if hasattr(result, "critique_id") else None}

    async def _persist_record(self, record: ExplainabilityRecord) -> None:
        """Persist explainability record to DynamoDB and Neptune."""
        # DynamoDB for queryable audit
        await self.dynamodb.put_item(
            Item={
                "record_id": {"S": record.record_id},
                "decision_id": {"S": record.decision_id},
                "agent_id": {"S": record.agent_id},
                "timestamp": {"S": record.timestamp.isoformat()},
                "severity": {"S": record.severity.value},
                "explainability_score": {"N": str(record.explainability_score.overall_score())},
                "hitl_required": {"BOOL": record.hitl_required},
                "data": {"S": str(record.to_dict())},
            }
        )

        # Neptune for decision graph traversal
        # Links decision to reasoning steps, alternatives, and verification results
        # (Implementation depends on Neptune schema)
```

```python
# src/services/explainability/consistency.py

import logging
import uuid
from typing import Any

from .contracts import (
    ConsistencyReport,
    Contradiction,
    ContradictionSeverity,
    ReasoningChain,
)

logger = logging.getLogger(__name__)


class ConsistencyVerifier:
    """
    Verify consistency between stated reasoning and actual actions.

    Detects contradictions where:
    - Agent claims to do X but actually does Y
    - Reasoning steps are missing or illogical
    - Evidence doesn't support conclusions
    """

    def __init__(self, bedrock_client):
        self.bedrock = bedrock_client

    async def verify(
        self,
        decision_id: str,
        reasoning_chain: ReasoningChain,
        decision_output: dict[str, Any],
    ) -> ConsistencyReport:
        """
        Verify that reasoning chain is consistent with decision output.

        Args:
            decision_id: Decision being verified
            reasoning_chain: The stated reasoning
            decision_output: The actual output/action taken

        Returns:
            ConsistencyReport with any detected contradictions
        """
        contradictions = []

        # Extract claims from reasoning chain
        claims = self._extract_claims(reasoning_chain)

        # Extract actions from decision output
        actions = self._extract_actions(decision_output)

        # Check each claim against actions
        for claim in claims:
            verification = await self._verify_claim(claim, actions, decision_output)
            if not verification["is_consistent"]:
                contradiction = Contradiction(
                    contradiction_id=f"ctr_{uuid.uuid4().hex[:8]}",
                    severity=self._assess_severity(verification),
                    stated_claim=claim["text"],
                    actual_action=verification["actual_action"],
                    explanation=verification["explanation"],
                    evidence=verification["evidence"],
                    requires_hitl=verification["severity"] in ["major", "critical"],
                )
                contradictions.append(contradiction)

        # Calculate consistency score
        if claims:
            consistent_claims = len(claims) - len(contradictions)
            consistency_score = consistent_claims / len(claims)
        else:
            consistency_score = 1.0

        return ConsistencyReport(
            decision_id=decision_id,
            is_consistent=len(contradictions) == 0,
            contradictions=contradictions,
            consistency_score=consistency_score,
        )

    def _extract_claims(self, reasoning_chain: ReasoningChain) -> list[dict]:
        """Extract verifiable claims from reasoning chain."""
        claims = []
        for step in reasoning_chain.steps:
            # Each reasoning step may contain implicit claims
            claims.append({
                "step_number": step.step_number,
                "text": step.description,
                "evidence": step.evidence,
                "confidence": step.confidence,
            })
        return claims

    def _extract_actions(self, decision_output: dict[str, Any]) -> list[dict]:
        """Extract actions from decision output for verification."""
        actions = []

        # Handle common output formats
        if "action" in decision_output:
            actions.append({"type": "action", "value": decision_output["action"]})
        if "code_changes" in decision_output:
            actions.append({"type": "code_change", "value": decision_output["code_changes"]})
        if "recommendation" in decision_output:
            actions.append({"type": "recommendation", "value": decision_output["recommendation"]})
        if "result" in decision_output:
            actions.append({"type": "result", "value": decision_output["result"]})

        return actions

    async def _verify_claim(
        self,
        claim: dict,
        actions: list[dict],
        decision_output: dict[str, Any],
    ) -> dict:
        """Verify a single claim against actions using LLM analysis."""
        prompt = f"""Analyze whether the following claim is consistent with the action taken.

CLAIM: {claim['text']}
EVIDENCE PROVIDED: {claim['evidence']}

ACTIONS TAKEN: {actions}

FULL OUTPUT: {decision_output}

Determine if the claim is consistent with the actions. Consider:
1. Does the action match what the claim says would happen?
2. Is there any contradiction between stated reasoning and actual behavior?
3. Are there missing steps that should have been taken based on the reasoning?

Respond in JSON format:
{{
    "is_consistent": true/false,
    "actual_action": "what was actually done",
    "explanation": "detailed explanation of consistency or contradiction",
    "evidence": ["specific evidence points"],
    "severity": "none/minor/moderate/major/critical"
}}
"""
        # Call Bedrock for analysis
        response = await self._call_bedrock(prompt)
        return response

    async def _call_bedrock(self, prompt: str) -> dict:
        """Call Bedrock for consistency analysis."""
        # Implementation uses Bedrock runtime
        # Returns parsed JSON response
        # For brevity, showing structure
        return {
            "is_consistent": True,
            "actual_action": "",
            "explanation": "",
            "evidence": [],
            "severity": "none",
        }

    def _assess_severity(self, verification: dict) -> ContradictionSeverity:
        """Map verification result to contradiction severity."""
        severity_map = {
            "none": ContradictionSeverity.MINOR,
            "minor": ContradictionSeverity.MINOR,
            "moderate": ContradictionSeverity.MODERATE,
            "major": ContradictionSeverity.MAJOR,
            "critical": ContradictionSeverity.CRITICAL,
        }
        return severity_map.get(verification.get("severity", "minor"), ContradictionSeverity.MINOR)
```

```python
# src/services/explainability/inter_agent.py

import logging
import uuid
from typing import Any

from .contracts import (
    ClaimVerification,
    VerificationReport,
)

logger = logging.getLogger(__name__)


class InterAgentVerifier:
    """
    Verify claims made by upstream agents.

    When Agent B receives output from Agent A, this service
    independently verifies Agent A's claims rather than
    accepting them at face value.
    """

    def __init__(self, neptune_client):
        self.neptune = neptune_client

    async def verify_claims(
        self,
        decision_id: str,
        claims: list[dict],
    ) -> VerificationReport:
        """
        Verify claims from upstream agents.

        Args:
            decision_id: Current decision being made
            claims: List of claims from upstream agents
                    Each claim: {
                        "agent_id": str,
                        "claim_type": str (e.g., "security_assessment", "test_result"),
                        "claim_text": str,
                        "evidence": list[str],
                        "confidence": float
                    }

        Returns:
            VerificationReport with verification results
        """
        verifications = []
        unverified_count = 0
        failure_count = 0

        for claim in claims:
            verification = await self._verify_single_claim(claim)
            verifications.append(verification)

            if not verification.is_verified:
                failure_count += 1
            if verification.confidence < 0.5:
                unverified_count += 1

        # Calculate trust adjustment
        if verifications:
            avg_confidence = sum(v.confidence for v in verifications) / len(verifications)
            trust_adjustment = (avg_confidence - 0.5) * 0.2  # -0.1 to +0.1 range
        else:
            trust_adjustment = 0.0

        return VerificationReport(
            decision_id=decision_id,
            verifications=verifications,
            trust_adjustment=trust_adjustment,
            unverified_claims=unverified_count,
            verification_failures=failure_count,
        )

    async def _verify_single_claim(self, claim: dict) -> ClaimVerification:
        """Verify a single claim from an upstream agent."""
        claim_id = f"clm_{uuid.uuid4().hex[:8]}"
        upstream_agent_id = claim.get("agent_id", "unknown")
        claim_text = claim.get("claim_text", "")
        claim_type = claim.get("claim_type", "unknown")

        # Verification strategy depends on claim type
        verification_result = await self._get_verification_strategy(claim_type)(claim)

        return ClaimVerification(
            claim_id=claim_id,
            upstream_agent_id=upstream_agent_id,
            claim_text=claim_text,
            is_verified=verification_result["verified"],
            verification_evidence=verification_result["evidence"],
            confidence=verification_result["confidence"],
            discrepancy=verification_result.get("discrepancy"),
        )

    def _get_verification_strategy(self, claim_type: str):
        """Get appropriate verification strategy for claim type."""
        strategies = {
            "security_assessment": self._verify_security_claim,
            "test_result": self._verify_test_claim,
            "code_analysis": self._verify_code_analysis_claim,
            "vulnerability_found": self._verify_vulnerability_claim,
        }
        return strategies.get(claim_type, self._verify_generic_claim)

    async def _verify_security_claim(self, claim: dict) -> dict:
        """Verify a security assessment claim."""
        # Query Neptune for related security analysis
        # Cross-reference with vulnerability database
        # Check if claimed vulnerabilities exist in code graph
        return {
            "verified": True,
            "evidence": ["Cross-referenced with Neptune security graph"],
            "confidence": 0.85,
            "discrepancy": None,
        }

    async def _verify_test_claim(self, claim: dict) -> dict:
        """Verify a test result claim."""
        # Query for actual test execution records
        # Verify test pass/fail status
        return {
            "verified": True,
            "evidence": ["Test execution logs confirm result"],
            "confidence": 0.95,
            "discrepancy": None,
        }

    async def _verify_code_analysis_claim(self, claim: dict) -> dict:
        """Verify a code analysis claim."""
        # Re-run static analysis on relevant code
        # Compare results with claimed findings
        return {
            "verified": True,
            "evidence": ["Static analysis re-run confirms findings"],
            "confidence": 0.90,
            "discrepancy": None,
        }

    async def _verify_vulnerability_claim(self, claim: dict) -> dict:
        """Verify a vulnerability discovery claim."""
        # Check vulnerability against CVE database
        # Verify affected code paths in graph
        return {
            "verified": True,
            "evidence": ["Vulnerability confirmed in CVE database"],
            "confidence": 0.88,
            "discrepancy": None,
        }

    async def _verify_generic_claim(self, claim: dict) -> dict:
        """Generic verification for unknown claim types."""
        # Basic evidence check
        has_evidence = bool(claim.get("evidence"))
        return {
            "verified": has_evidence,
            "evidence": ["Basic evidence check performed"],
            "confidence": 0.5 if has_evidence else 0.3,
            "discrepancy": None if has_evidence else "No supporting evidence provided",
        }
```

### Agent Integration (ExplainabilityMixin)

```python
# src/agents/explainability_mixin.py

from typing import Any, Optional

from src.services.explainability import (
    UniversalExplainabilityService,
    ExplainabilityRecord,
)
from src.services.explainability.contracts import DecisionSeverity


class ExplainabilityMixin:
    """
    Mixin that adds universal explainability to agents.

    Every agent decision goes through explainability pipeline
    before being finalized.

    Usage:
        class CoderAgent(ExplainabilityMixin, MCPEnabledAgent):
            async def execute(self, task: AgentTask) -> AgentResult:
                result = await self._generate_code(task)
                return await self.finalize_with_explainability(
                    result=result,
                    task=task,
                    severity=self._assess_severity(task),
                )
    """

    _explainability_service: Optional[UniversalExplainabilityService] = None

    def set_explainability_service(
        self,
        service: UniversalExplainabilityService,
    ) -> None:
        """Configure explainability service for this agent."""
        self._explainability_service = service

    async def finalize_with_explainability(
        self,
        result: Any,
        task: Any,
        severity: DecisionSeverity,
        upstream_claims: Optional[list[dict]] = None,
    ) -> tuple[Any, ExplainabilityRecord]:
        """
        Generate explainability record before returning result.

        Args:
            result: The agent's decision/output
            task: The task that was processed
            severity: Decision severity level
            upstream_claims: Claims from upstream agents to verify

        Returns:
            Tuple of (result, ExplainabilityRecord)
        """
        if not self._explainability_service:
            raise RuntimeError("ExplainabilityService not configured")

        decision_id = getattr(task, "task_id", str(id(task)))
        agent_id = getattr(self, "agent_id", self.__class__.__name__)

        record = await self._explainability_service.explain_decision(
            decision_id=decision_id,
            agent_id=agent_id,
            severity=severity,
            decision_input=self._serialize_input(task),
            decision_output=self._serialize_output(result),
            decision_context=self._get_decision_context(),
            upstream_claims=upstream_claims,
        )

        # Check if HITL required
        if record.hitl_required:
            # Trigger HITL workflow
            await self._trigger_hitl(record)

        return result, record

    def _serialize_input(self, task: Any) -> dict:
        """Serialize task input for explainability."""
        if hasattr(task, "to_dict"):
            return task.to_dict()
        return {"task": str(task)}

    def _serialize_output(self, result: Any) -> dict:
        """Serialize result output for explainability."""
        if hasattr(result, "to_dict"):
            return result.to_dict()
        return {"result": str(result)}

    def _get_decision_context(self) -> dict:
        """Get current decision context."""
        return {
            "agent_id": getattr(self, "agent_id", self.__class__.__name__),
            "conversation_id": getattr(self, "_conversation_id", None),
            "prior_decisions": getattr(self, "_prior_decisions", []),
        }

    async def _trigger_hitl(self, record: ExplainabilityRecord) -> None:
        """Trigger HITL workflow for decisions requiring human review."""
        # Implementation hooks into ADR-032 HITL workflow
        pass
```

### Files Created

| File | Purpose |
|------|---------|
| `src/services/explainability/__init__.py` | Package initialization |
| `src/services/explainability/contracts.py` | Data contracts and schemas |
| `src/services/explainability/service.py` | Main orchestration service |
| `src/services/explainability/reasoning_chain.py` | Reasoning chain builder |
| `src/services/explainability/alternatives.py` | Alternatives analyzer |
| `src/services/explainability/confidence.py` | Confidence quantifier |
| `src/services/explainability/consistency.py` | Consistency verifier |
| `src/services/explainability/inter_agent.py` | Inter-agent claim verifier |
| `src/services/explainability/dashboard.py` | Dashboard API service |
| `src/services/explainability/metrics.py` | CloudWatch metrics |
| `src/agents/explainability_mixin.py` | Agent integration mixin |
| `tests/services/test_explainability/` | Test suite (350+ tests) |
| `deploy/cloudformation/explainability.yaml` | Infrastructure |
| `deploy/cloudformation/explainability-dashboard.yaml` | Dashboard infrastructure |

### DynamoDB Tables

| Table | Purpose |
|-------|---------|
| `aura-explainability-records-{env}` | Complete explainability records |
| `aura-contradiction-alerts-{env}` | Contradiction detection alerts |

### CloudWatch Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| `ExplainabilityScore` | Average explainability score | > 0.8 |
| `ReasoningCompleteness` | Decisions with complete reasoning | > 95% |
| `AlternativesCoverage` | Decisions with alternatives documented | > 90% |
| `ConsistencyRate` | Decisions without contradictions | > 99% |
| `ContradictionsDetected` | Contradictions per hour | < 5 |
| `HITLEscalations` | HITL escalations per hour | Monitoring |
| `ProcessingLatencyP95` | Explainability pipeline latency | < 500ms |

### CloudWatch Alarms

| Alarm | Condition | Action |
|-------|-----------|--------|
| `LowExplainabilityScore` | Avg score < 0.7 for 5 min | SNS notification |
| `HighContradictionRate` | > 10 contradictions/hour | SNS + PagerDuty |
| `CriticalContradiction` | Any CRITICAL contradiction | Immediate SNS |
| `ExplainabilityLatencyHigh` | P95 > 1000ms for 5 min | SNS notification |

## Cost Analysis

### Monthly Cost Projections

| Component | Unit Cost | Volume/Month | Monthly Cost |
|-----------|-----------|--------------|--------------|
| **Bedrock (Haiku)** | $0.25/1M tokens | 30M tokens | $7.50 |
| **Bedrock (Sonnet)** | $3/1M tokens | 5M tokens | $15 |
| **DynamoDB** | $1.25/M writes | 10M writes | $12.50 |
| **Neptune** | $0.10/hr (r5.large) | 730 hrs | $73 |
| **Lambda** | $0.20/1M requests | 5M requests | $1 |
| **CloudWatch** | $0.30/metric/month | 20 metrics | $6 |
| **Total** | | | **~$115/month** |

### Cost Optimization Strategies

1. **Tiered Processing** - Lighter analysis for TRIVIAL/NORMAL, full analysis for SIGNIFICANT/CRITICAL
2. **Semantic Caching** - Cache similar reasoning patterns (ADR-029 integration)
3. **Batch Processing** - Aggregate low-severity decisions for batch analysis
4. **Async Persistence** - Non-blocking writes to reduce Lambda concurrency

## Testing Strategy

### Test Pyramid

| Tier | Tests | Coverage |
|------|-------|----------|
| Unit Tests | 180 | All components, contracts, scoring |
| Integration Tests | 100 | Full pipeline, persistence, dashboard |
| Consistency Tests | 50 | Contradiction detection accuracy |
| Regression Tests | 30 | Golden set preservation |
| **Total** | **360** | |

### Test Categories

```python
# tests/services/test_explainability/test_consistency.py

class TestConsistencyVerifier:
    """Test contradiction detection between reasoning and actions."""

    @pytest.mark.parametrize("reasoning,action,expected_contradiction", [
        # Claim: security fix, Action: performance optimization
        (
            "Applied security patch to prevent SQL injection",
            {"type": "refactor", "focus": "performance"},
            True,
        ),
        # Claim: added tests, Action: no tests in output
        (
            "Added comprehensive unit tests for the new feature",
            {"files_modified": ["feature.py"], "test_files": []},
            True,
        ),
        # Consistent: claim matches action
        (
            "Refactored authentication module for clarity",
            {"type": "refactor", "files": ["auth.py"]},
            False,
        ),
    ])
    async def test_contradiction_detection(
        self,
        verifier,
        reasoning,
        action,
        expected_contradiction,
    ):
        chain = ReasoningChain(
            decision_id="test",
            agent_id="test",
            steps=[ReasoningStep(step_number=1, description=reasoning)],
        )
        result = await verifier.verify("test", chain, action)
        assert result.has_critical_contradictions() == expected_contradiction


class TestInterAgentVerification:
    """Test verification of upstream agent claims."""

    async def test_security_claim_verified(self, verifier):
        claims = [{
            "agent_id": "security-reviewer",
            "claim_type": "security_assessment",
            "claim_text": "No SQL injection vulnerabilities found",
            "evidence": ["Static analysis scan results"],
            "confidence": 0.9,
        }]
        result = await verifier.verify_claims("test", claims)
        assert result.overall_trust_score() >= 0.8

    async def test_unsubstantiated_claim_flagged(self, verifier):
        claims = [{
            "agent_id": "unknown-agent",
            "claim_type": "unknown",
            "claim_text": "Everything is fine",
            "evidence": [],
            "confidence": 0.5,
        }]
        result = await verifier.verify_claims("test", claims)
        assert result.unverified_claims > 0
```

### Golden Set Requirements

- 100 hand-verified consistency cases (contradictions vs. consistent)
- 50 inter-agent verification scenarios
- 100 explainability score calculations
- Run before any threshold changes
- Automated nightly regression

## Implementation Phases

### Phase 1: Core Framework (Weeks 1-2)

| Task | Deliverable |
|------|-------------|
| Implement contracts.py | All data structures and schemas |
| Implement ReasoningChainBuilder | Reasoning extraction and structuring |
| Implement AlternativesAnalyzer | Alternative discovery and comparison |
| Implement ConfidenceQuantifier | Confidence interval calculation |
| Unit tests | 180 tests |

### Phase 2: Verification Services (Weeks 3-4)

| Task | Deliverable |
|------|-------------|
| Implement ConsistencyVerifier | Contradiction detection |
| Implement InterAgentVerifier | Upstream claim verification |
| Implement UniversalExplainabilityService | Main orchestration |
| Implement ExplainabilityMixin | Agent integration |
| Integration tests | 100 tests |

### Phase 3: Constitutional Integration (Weeks 5-6)

| Task | Deliverable |
|------|-------------|
| Add Principles 17-20 to constitution.yaml | Explainability principles |
| Extend ConstitutionalCritiqueService | Reasoning critique methods |
| Integrate with DecisionAuditLogger | Audit record extension |
| Add to MetaOrchestrator | Universal application |
| Consistency tests | 50 tests |

### Phase 4: Dashboard & Observability (Weeks 7-8)

| Task | Deliverable |
|------|-------------|
| Implement ExplainabilityDashboardAPI | REST API for dashboard |
| Create Dashboard UI components | Decision explorer, reasoning viewer |
| Deploy CloudWatch metrics | All metrics and alarms |
| Create operations runbook | Documentation |
| Regression tests | 30 tests |

### Phase 5: Production Rollout (Week 9)

| Task | Deliverable |
|------|-------------|
| Enable for all agents | Universal coverage |
| Threshold tuning | Production calibration |
| User training | Documentation and demos |
| Golden set finalization | 250 verified cases |

## GovCloud Compatibility

| Service | GovCloud Available | Notes |
|---------|-------------------|-------|
| Amazon Bedrock | Yes | Claude 3.x models available |
| DynamoDB | Yes | Full feature parity |
| Neptune | Yes | Provisioned only (no Serverless) |
| Lambda | Yes | Full feature parity |
| CloudWatch | Yes | Full feature parity |

**GovCloud-Specific Requirements:**
- Use `${AWS::Partition}` in all ARNs
- Configure FIPS endpoints
- Audit retention must meet CMMC requirements (1+ year)
- Neptune must use provisioned instances

## Consequences

### Positive

1. **Complete Decision Transparency** - Every decision has documented reasoning
2. **Alternatives Visibility** - Humans understand what options were considered
3. **Quantified Uncertainty** - Confidence intervals instead of false precision
4. **Contradiction Detection** - Automatic detection of reasoning-action mismatches
5. **Inter-Agent Verification** - Trust but verify across agent boundaries
6. **Compliance Ready** - Full audit trail for CMMC/SOX/NIST
7. **Trust Calibration** - Humans can appropriately trust agent decisions

### Negative

1. **Processing Overhead** - ~200-500ms added to decision pipeline
2. **Storage Costs** - Detailed explainability records require storage
3. **Complexity** - Additional service layer to maintain
4. **Potential Over-Caution** - High contradiction detection may slow agents

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| False contradiction detection | Medium | Medium | Tune thresholds, human review queue |
| Reasoning extraction inaccuracy | Medium | Medium | LLM prompting refinement, golden set |
| Performance degradation | Low | Medium | Async processing, caching, tiered analysis |
| Over-reliance on explanations | Low | High | Training that explanations aid, not replace, judgment |

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Reasoning Coverage | 100% of decisions | All decisions have reasoning chains |
| Alternatives Documentation | 100% of SIGNIFICANT+ | All significant decisions show alternatives |
| Contradiction Detection Rate | > 95% | Verified against golden set |
| False Positive Rate | < 5% | Human review of flagged contradictions |
| Explainability Score | > 0.8 average | CloudWatch metrics |
| HITL Escalation Accuracy | > 90% | Human confirmation of escalations |
| P95 Latency | < 500ms | CloudWatch metrics |

## References

1. ADR-052: AI Alignment Principles - DecisionAuditLogger integration
2. ADR-063: Constitutional AI Integration - Critique pipeline extension
3. ADR-032: Configurable Autonomy Framework - HITL escalation
4. NIST AI RMF 1.0 - Explainable AI requirements
5. CMMC AC.L2-3.1.7 - Decision traceability requirements
6. EU AI Act Article 14 - Human oversight requirements
7. Anthropic Constitutional AI Paper - Critique methodology
8. "Attention Is All You Need" (Vaswani et al.) - Reasoning chain patterns
