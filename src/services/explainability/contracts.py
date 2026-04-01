"""
Project Aura - Universal Explainability Framework Contracts

Defines data contracts for the explainability framework including
reasoning chains, alternatives analysis, confidence quantification,
consistency verification, and inter-agent claim verification.

Security Rationale:
- Every decision must have documented reasoning
- Alternatives must be disclosed for significant decisions
- Confidence must be quantified with intervals
- Consistency between reasoning and actions must be verified
- Inter-agent claims must be independently validated

Author: Project Aura Team
Created: 2026-01-25
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

# =============================================================================
# Enums
# =============================================================================


class DecisionSeverity(Enum):
    """Decision severity levels with explainability requirements."""

    TRIVIAL = "trivial"  # Min 1 reasoning step, 2 alternatives
    NORMAL = "normal"  # Min 2 reasoning steps, 2 alternatives
    SIGNIFICANT = "significant"  # Min 3 reasoning steps, 3 alternatives
    CRITICAL = "critical"  # Min 5 reasoning steps, 4 alternatives


class ContradictionSeverity(Enum):
    """Severity of detected contradictions."""

    MINOR = "minor"  # Cosmetic inconsistency
    MODERATE = "moderate"  # Logic gap
    MAJOR = "major"  # Clear contradiction
    CRITICAL = "critical"  # Dangerous inconsistency


class VerificationStatus(Enum):
    """Status of claim verification."""

    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    FAILED = "failed"
    PENDING = "pending"


class CalibrationMethod(Enum):
    """Methods for confidence calibration."""

    ENSEMBLE_DISAGREEMENT = "ensemble_disagreement"
    MONTE_CARLO_DROPOUT = "monte_carlo_dropout"
    TEMPERATURE_SCALING = "temperature_scaling"
    PLATT_SCALING = "platt_scaling"


# =============================================================================
# Reasoning Chain
# =============================================================================


@dataclass
class ReasoningStep:
    """A single step in the reasoning chain."""

    step_number: int
    description: str
    evidence: list[str] = field(default_factory=list)
    confidence: float = 1.0
    references: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "step_number": self.step_number,
            "description": self.description,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "references": self.references,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReasoningStep:
        """Create from dictionary."""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now(timezone.utc)

        return cls(
            step_number=data.get("step_number", 0),
            description=data.get("description", ""),
            evidence=data.get("evidence", []),
            confidence=data.get("confidence", 1.0),
            references=data.get("references", []),
            timestamp=timestamp,
        )


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

    def add_step(
        self,
        description: str,
        evidence: list[str] | None = None,
        confidence: float = 1.0,
        references: list[str] | None = None,
    ) -> ReasoningStep:
        """Add a new step to the reasoning chain."""
        step = ReasoningStep(
            step_number=len(self.steps) + 1,
            description=description,
            evidence=evidence or [],
            confidence=confidence,
            references=references or [],
        )
        self.steps.append(step)
        self._recalculate_confidence()
        return step

    def _recalculate_confidence(self) -> None:
        """Recalculate total confidence from individual steps."""
        if not self.steps:
            self.total_confidence = 1.0
            return
        # Product of step confidences (chain rule)
        confidence = 1.0
        for step in self.steps:
            confidence *= step.confidence
        self.total_confidence = confidence

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "decision_id": self.decision_id,
            "agent_id": self.agent_id,
            "steps": [s.to_dict() for s in self.steps],
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "total_confidence": self.total_confidence,
            "step_count": len(self.steps),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReasoningChain:
        """Create from dictionary."""
        steps = [ReasoningStep.from_dict(s) for s in data.get("steps", [])]
        return cls(
            decision_id=data.get("decision_id", ""),
            agent_id=data.get("agent_id", ""),
            steps=steps,
            input_summary=data.get("input_summary", ""),
            output_summary=data.get("output_summary", ""),
            total_confidence=data.get("total_confidence", 1.0),
        )


# =============================================================================
# Alternatives Analysis
# =============================================================================


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

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Alternative:
        """Create from dictionary."""
        return cls(
            alternative_id=data.get("alternative_id", ""),
            description=data.get("description", ""),
            confidence=data.get("confidence", 0.0),
            pros=data.get("pros", []),
            cons=data.get("cons", []),
            was_chosen=data.get("was_chosen", False),
            rejection_reason=data.get("rejection_reason"),
            comparison_score=data.get("comparison_score", 0.0),
        )


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

    def get_chosen(self) -> Optional[Alternative]:
        """Get the chosen alternative."""
        for alt in self.alternatives:
            if alt.was_chosen:
                return alt
        return None

    def get_rejected(self) -> list[Alternative]:
        """Get all rejected alternatives."""
        return [alt for alt in self.alternatives if not alt.was_chosen]

    def add_alternative(
        self,
        alternative_id: str,
        description: str,
        confidence: float,
        pros: list[str] | None = None,
        cons: list[str] | None = None,
        was_chosen: bool = False,
        rejection_reason: str | None = None,
    ) -> Alternative:
        """Add an alternative to the report."""
        alt = Alternative(
            alternative_id=alternative_id,
            description=description,
            confidence=confidence,
            pros=pros or [],
            cons=cons or [],
            was_chosen=was_chosen,
            rejection_reason=rejection_reason,
        )
        self.alternatives.append(alt)
        if was_chosen:
            self.chosen_alternative_id = alternative_id
        return alt

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "decision_id": self.decision_id,
            "alternatives": [a.to_dict() for a in self.alternatives],
            "comparison_criteria": self.comparison_criteria,
            "chosen_alternative_id": self.chosen_alternative_id,
            "decision_rationale": self.decision_rationale,
            "alternative_count": len(self.alternatives),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AlternativesReport:
        """Create from dictionary."""
        alternatives = [Alternative.from_dict(a) for a in data.get("alternatives", [])]
        return cls(
            decision_id=data.get("decision_id", ""),
            alternatives=alternatives,
            comparison_criteria=data.get("comparison_criteria", []),
            chosen_alternative_id=data.get("chosen_alternative_id"),
            decision_rationale=data.get("decision_rationale", ""),
        )


# =============================================================================
# Confidence Quantification
# =============================================================================


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
        """Calculate the width of the confidence interval."""
        return self.upper_bound - self.lower_bound

    def is_well_calibrated(self) -> bool:
        """Check if interval width is appropriate for confidence level."""
        # Higher confidence should have narrower intervals
        expected_width = 2 * (1 - self.point_estimate)
        actual_width = self.interval_width()
        # Allow 50% to 200% of expected width
        return 0.5 * expected_width <= actual_width <= 2 * expected_width

    def contains(self, value: float) -> bool:
        """Check if a value falls within the confidence interval."""
        return self.lower_bound <= value <= self.upper_bound

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConfidenceInterval:
        """Create from dictionary."""
        return cls(
            point_estimate=data.get("point_estimate", 0.5),
            lower_bound=data.get("lower_bound", 0.0),
            upper_bound=data.get("upper_bound", 1.0),
            uncertainty_sources=data.get("uncertainty_sources", []),
            calibration_method=data.get("calibration_method", "ensemble_disagreement"),
            sample_size=data.get("sample_size"),
        )


# =============================================================================
# Consistency Verification
# =============================================================================


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

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "contradiction_id": self.contradiction_id,
            "severity": self.severity.value,
            "stated_claim": self.stated_claim,
            "actual_action": self.actual_action,
            "explanation": self.explanation,
            "evidence": self.evidence,
            "requires_hitl": self.requires_hitl,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Contradiction:
        """Create from dictionary."""
        severity_str = data.get("severity", "minor")
        try:
            severity = ContradictionSeverity(severity_str)
        except ValueError:
            severity = ContradictionSeverity.MINOR

        return cls(
            contradiction_id=data.get("contradiction_id", ""),
            severity=severity,
            stated_claim=data.get("stated_claim", ""),
            actual_action=data.get("actual_action", ""),
            explanation=data.get("explanation", ""),
            evidence=data.get("evidence", []),
            requires_hitl=data.get("requires_hitl", False),
        )


@dataclass
class ConsistencyReport:
    """Report on consistency between reasoning and actions."""

    decision_id: str
    is_consistent: bool
    contradictions: list[Contradiction] = field(default_factory=list)
    consistency_score: float = 1.0
    verification_method: str = "claim_action_matching"
    verified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def has_critical_contradictions(self) -> bool:
        """Check if any contradictions are critical severity."""
        return any(
            c.severity == ContradictionSeverity.CRITICAL for c in self.contradictions
        )

    def has_major_contradictions(self) -> bool:
        """Check if any contradictions are major or critical severity."""
        return any(
            c.severity in (ContradictionSeverity.MAJOR, ContradictionSeverity.CRITICAL)
            for c in self.contradictions
        )

    def add_contradiction(
        self,
        contradiction_id: str,
        severity: ContradictionSeverity,
        stated_claim: str,
        actual_action: str,
        explanation: str,
        evidence: list[str] | None = None,
    ) -> Contradiction:
        """Add a contradiction to the report."""
        contradiction = Contradiction(
            contradiction_id=contradiction_id,
            severity=severity,
            stated_claim=stated_claim,
            actual_action=actual_action,
            explanation=explanation,
            evidence=evidence or [],
            requires_hitl=severity
            in (ContradictionSeverity.MAJOR, ContradictionSeverity.CRITICAL),
        )
        self.contradictions.append(contradiction)
        self.is_consistent = False
        self._recalculate_score()
        return contradiction

    def _recalculate_score(self) -> None:
        """Recalculate consistency score based on contradictions."""
        if not self.contradictions:
            self.consistency_score = 1.0
            return

        # Deduct based on severity
        deductions = {
            ContradictionSeverity.MINOR: 0.05,
            ContradictionSeverity.MODERATE: 0.15,
            ContradictionSeverity.MAJOR: 0.30,
            ContradictionSeverity.CRITICAL: 0.50,
        }
        total_deduction = sum(
            deductions.get(c.severity, 0.05) for c in self.contradictions
        )
        self.consistency_score = max(0.0, 1.0 - total_deduction)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "decision_id": self.decision_id,
            "is_consistent": self.is_consistent,
            "contradictions": [c.to_dict() for c in self.contradictions],
            "consistency_score": self.consistency_score,
            "verification_method": self.verification_method,
            "verified_at": self.verified_at.isoformat(),
            "has_critical_contradictions": self.has_critical_contradictions(),
            "contradiction_count": len(self.contradictions),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConsistencyReport:
        """Create from dictionary."""
        contradictions = [
            Contradiction.from_dict(c) for c in data.get("contradictions", [])
        ]
        verified_at = data.get("verified_at")
        if isinstance(verified_at, str):
            verified_at = datetime.fromisoformat(verified_at)
        elif verified_at is None:
            verified_at = datetime.now(timezone.utc)

        return cls(
            decision_id=data.get("decision_id", ""),
            is_consistent=data.get("is_consistent", True),
            contradictions=contradictions,
            consistency_score=data.get("consistency_score", 1.0),
            verification_method=data.get(
                "verification_method", "claim_action_matching"
            ),
            verified_at=verified_at,
        )


# =============================================================================
# Inter-Agent Verification
# =============================================================================


@dataclass
class ClaimVerification:
    """Verification result for a claim made by an upstream agent."""

    claim_id: str
    upstream_agent_id: str
    claim_text: str
    claim_type: str
    is_verified: bool
    verification_evidence: list[str] = field(default_factory=list)
    confidence: float = 0.0
    discrepancy: Optional[str] = None
    verified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "claim_id": self.claim_id,
            "upstream_agent_id": self.upstream_agent_id,
            "claim_text": self.claim_text,
            "claim_type": self.claim_type,
            "is_verified": self.is_verified,
            "verification_evidence": self.verification_evidence,
            "confidence": self.confidence,
            "discrepancy": self.discrepancy,
            "verified_at": self.verified_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClaimVerification:
        """Create from dictionary."""
        verified_at = data.get("verified_at")
        if isinstance(verified_at, str):
            verified_at = datetime.fromisoformat(verified_at)
        elif verified_at is None:
            verified_at = datetime.now(timezone.utc)

        return cls(
            claim_id=data.get("claim_id", ""),
            upstream_agent_id=data.get("upstream_agent_id", ""),
            claim_text=data.get("claim_text", ""),
            claim_type=data.get("claim_type", "unknown"),
            is_verified=data.get("is_verified", False),
            verification_evidence=data.get("verification_evidence", []),
            confidence=data.get("confidence", 0.0),
            discrepancy=data.get("discrepancy"),
            verified_at=verified_at,
        )


@dataclass
class VerificationReport:
    """Report on inter-agent claim verification."""

    decision_id: str
    verifications: list[ClaimVerification] = field(default_factory=list)
    trust_adjustment: float = 0.0
    unverified_claims: int = 0
    verification_failures: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def overall_trust_score(self) -> float:
        """Calculate overall trust score from verification results."""
        if not self.verifications:
            return 1.0
        verified_count = sum(1 for v in self.verifications if v.is_verified)
        return verified_count / len(self.verifications)

    def has_failures(self) -> bool:
        """Check if any verifications failed."""
        return self.verification_failures > 0

    def add_verification(
        self,
        claim_id: str,
        upstream_agent_id: str,
        claim_text: str,
        claim_type: str,
        is_verified: bool,
        confidence: float,
        verification_evidence: list[str] | None = None,
        discrepancy: str | None = None,
    ) -> ClaimVerification:
        """Add a verification result to the report."""
        verification = ClaimVerification(
            claim_id=claim_id,
            upstream_agent_id=upstream_agent_id,
            claim_text=claim_text,
            claim_type=claim_type,
            is_verified=is_verified,
            verification_evidence=verification_evidence or [],
            confidence=confidence,
            discrepancy=discrepancy,
        )
        self.verifications.append(verification)

        if not is_verified:
            self.verification_failures += 1
        if confidence < 0.5:
            self.unverified_claims += 1

        self._recalculate_trust_adjustment()
        return verification

    def _recalculate_trust_adjustment(self) -> None:
        """Recalculate trust adjustment based on verifications."""
        if not self.verifications:
            self.trust_adjustment = 0.0
            return

        avg_confidence = sum(v.confidence for v in self.verifications) / len(
            self.verifications
        )
        # -0.1 to +0.1 range based on average confidence
        self.trust_adjustment = (avg_confidence - 0.5) * 0.2

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "decision_id": self.decision_id,
            "verifications": [v.to_dict() for v in self.verifications],
            "trust_adjustment": self.trust_adjustment,
            "unverified_claims": self.unverified_claims,
            "verification_failures": self.verification_failures,
            "overall_trust_score": self.overall_trust_score(),
            "created_at": self.created_at.isoformat(),
            "verification_count": len(self.verifications),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VerificationReport:
        """Create from dictionary."""
        verifications = [
            ClaimVerification.from_dict(v) for v in data.get("verifications", [])
        ]
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now(timezone.utc)

        return cls(
            decision_id=data.get("decision_id", ""),
            verifications=verifications,
            trust_adjustment=data.get("trust_adjustment", 0.0),
            unverified_claims=data.get("unverified_claims", 0),
            verification_failures=data.get("verification_failures", 0),
            created_at=created_at,
        )


# =============================================================================
# Explainability Score
# =============================================================================


@dataclass
class ExplainabilityScore:
    """Composite score measuring decision explainability quality."""

    reasoning_completeness: float  # 0.0-1.0
    alternatives_coverage: float  # 0.0-1.0
    confidence_calibration: float  # 0.0-1.0
    consistency_score: float  # 0.0-1.0
    inter_agent_trust: float  # 0.0-1.0

    def overall_score(self) -> float:
        """Calculate weighted average of explainability dimensions."""
        weights = {
            "reasoning_completeness": 0.25,
            "alternatives_coverage": 0.20,
            "confidence_calibration": 0.15,
            "consistency_score": 0.25,
            "inter_agent_trust": 0.15,
        }
        score = (
            weights["reasoning_completeness"] * self.reasoning_completeness
            + weights["alternatives_coverage"] * self.alternatives_coverage
            + weights["confidence_calibration"] * self.confidence_calibration
            + weights["consistency_score"] * self.consistency_score
            + weights["inter_agent_trust"] * self.inter_agent_trust
        )
        return round(score, 4)

    def is_acceptable(self, threshold: float = 0.7) -> bool:
        """Check if overall score meets threshold."""
        return self.overall_score() >= threshold

    def get_weakest_dimension(self) -> tuple[str, float]:
        """Get the weakest explainability dimension."""
        dimensions = {
            "reasoning_completeness": self.reasoning_completeness,
            "alternatives_coverage": self.alternatives_coverage,
            "confidence_calibration": self.confidence_calibration,
            "consistency_score": self.consistency_score,
            "inter_agent_trust": self.inter_agent_trust,
        }
        weakest = min(dimensions.items(), key=lambda x: x[1])
        return weakest

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "reasoning_completeness": self.reasoning_completeness,
            "alternatives_coverage": self.alternatives_coverage,
            "confidence_calibration": self.confidence_calibration,
            "consistency_score": self.consistency_score,
            "inter_agent_trust": self.inter_agent_trust,
            "overall_score": self.overall_score(),
            "is_acceptable": self.is_acceptable(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExplainabilityScore:
        """Create from dictionary."""
        return cls(
            reasoning_completeness=data.get("reasoning_completeness", 0.0),
            alternatives_coverage=data.get("alternatives_coverage", 0.0),
            confidence_calibration=data.get("confidence_calibration", 0.0),
            consistency_score=data.get("consistency_score", 0.0),
            inter_agent_trust=data.get("inter_agent_trust", 0.0),
        )


# =============================================================================
# Complete Explainability Record
# =============================================================================


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
        """Calculate checksum after initialization."""
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
        return all(
            [
                self.reasoning_chain is not None,
                self.alternatives_report is not None,
                self.confidence_interval is not None,
                self.consistency_report is not None,
            ]
        )

    def requires_human_review(self) -> bool:
        """Check if this record requires human review."""
        if self.hitl_required:
            return True
        if (
            self.consistency_report
            and self.consistency_report.has_critical_contradictions()
        ):
            return True
        if (
            self.explainability_score
            and self.explainability_score.overall_score() < 0.5
        ):
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "record_id": self.record_id,
            "decision_id": self.decision_id,
            "agent_id": self.agent_id,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "reasoning_chain": (
                self.reasoning_chain.to_dict() if self.reasoning_chain else None
            ),
            "alternatives_report": (
                self.alternatives_report.to_dict() if self.alternatives_report else None
            ),
            "confidence_interval": (
                self.confidence_interval.to_dict() if self.confidence_interval else None
            ),
            "consistency_report": (
                self.consistency_report.to_dict() if self.consistency_report else None
            ),
            "verification_report": (
                self.verification_report.to_dict() if self.verification_report else None
            ),
            "explainability_score": (
                self.explainability_score.to_dict()
                if self.explainability_score
                else None
            ),
            "human_readable_summary": self.human_readable_summary,
            "checksum": self.checksum,
            "constitutional_critique_id": self.constitutional_critique_id,
            "hitl_required": self.hitl_required,
            "hitl_reason": self.hitl_reason,
            "is_complete": self.is_complete(),
            "requires_human_review": self.requires_human_review(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExplainabilityRecord:
        """Create from dictionary."""
        severity_str = data.get("severity", "normal")
        try:
            severity = DecisionSeverity(severity_str)
        except ValueError:
            severity = DecisionSeverity.NORMAL

        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now(timezone.utc)

        return cls(
            record_id=data.get("record_id", ""),
            decision_id=data.get("decision_id", ""),
            agent_id=data.get("agent_id", ""),
            severity=severity,
            timestamp=timestamp,
            reasoning_chain=(
                ReasoningChain.from_dict(data["reasoning_chain"])
                if data.get("reasoning_chain")
                else None
            ),
            alternatives_report=(
                AlternativesReport.from_dict(data["alternatives_report"])
                if data.get("alternatives_report")
                else None
            ),
            confidence_interval=(
                ConfidenceInterval.from_dict(data["confidence_interval"])
                if data.get("confidence_interval")
                else None
            ),
            consistency_report=(
                ConsistencyReport.from_dict(data["consistency_report"])
                if data.get("consistency_report")
                else None
            ),
            verification_report=(
                VerificationReport.from_dict(data["verification_report"])
                if data.get("verification_report")
                else None
            ),
            explainability_score=(
                ExplainabilityScore.from_dict(data["explainability_score"])
                if data.get("explainability_score")
                else None
            ),
            human_readable_summary=data.get("human_readable_summary", ""),
            checksum=data.get("checksum", ""),
            constitutional_critique_id=data.get("constitutional_critique_id"),
            hitl_required=data.get("hitl_required", False),
            hitl_reason=data.get("hitl_reason"),
        )
