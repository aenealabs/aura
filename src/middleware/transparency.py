"""
Transparency Middleware (ADR-052 Phase 2).

Injects audit requirements into agent calls to ensure all decisions
are fully transparent and auditable.

Key Capabilities:
- Require reasoning chains for all significant decisions
- Enforce confidence score disclosure
- Mandate alternative presentation for high-severity actions
- Validate source attribution
- Block responses that don't meet transparency requirements

Reference: ADR-052 AI Alignment Principles & Human-Machine Collaboration
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


class AuditRequirement(Enum):
    """Types of audit requirements."""

    REASONING_CHAIN = "reasoning_chain"
    CONFIDENCE_SCORE = "confidence_score"
    ALTERNATIVES = "alternatives"
    SOURCE_ATTRIBUTION = "source_attribution"
    UNCERTAINTY_DISCLOSURE = "uncertainty_disclosure"
    IMPACT_ASSESSMENT = "impact_assessment"


class ViolationSeverity(Enum):
    """Severity of audit violations."""

    INFO = "info"  # Logged but allowed
    WARNING = "warning"  # Logged and flagged
    ERROR = "error"  # Blocks response, requires correction
    CRITICAL = "critical"  # Blocks and escalates


@dataclass
class TransparencyConfig:
    """Configuration for transparency requirements."""

    # What to require
    require_reasoning_chain: bool = True
    require_confidence_score: bool = True
    require_alternatives: bool = True
    require_source_attribution: bool = True
    require_uncertainty_disclosure: bool = True
    require_impact_assessment: bool = False  # Only for high-severity

    # Thresholds
    min_reasoning_steps: int = 2
    min_alternatives: int = 2  # For high-severity decisions
    min_sources: int = 1

    # Severity levels that trigger requirements
    alternatives_required_severity: list[str] = field(
        default_factory=lambda: ["high", "critical"]
    )
    impact_required_severity: list[str] = field(default_factory=lambda: ["critical"])

    # Enforcement
    block_on_violation: bool = True
    log_all_decisions: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "require_reasoning_chain": self.require_reasoning_chain,
            "require_confidence_score": self.require_confidence_score,
            "require_alternatives": self.require_alternatives,
            "require_source_attribution": self.require_source_attribution,
            "require_uncertainty_disclosure": self.require_uncertainty_disclosure,
            "require_impact_assessment": self.require_impact_assessment,
            "min_reasoning_steps": self.min_reasoning_steps,
            "min_alternatives": self.min_alternatives,
            "min_sources": self.min_sources,
            "block_on_violation": self.block_on_violation,
        }


@dataclass
class AuditViolation:
    """Record of an audit requirement violation."""

    requirement: AuditRequirement
    severity: ViolationSeverity
    message: str
    agent_id: str
    decision_id: str | None = None
    expected: str | None = None
    actual: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "requirement": self.requirement.value,
            "severity": self.severity.value,
            "message": self.message,
            "agent_id": self.agent_id,
            "decision_id": self.decision_id,
            "expected": self.expected,
            "actual": self.actual,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class DecisionContext:
    """Context for a decision being made."""

    decision_id: str
    agent_id: str
    decision_type: str
    severity: str  # "low", "medium", "high", "critical"
    summary: str

    # Transparency data (to be filled in by agent)
    reasoning_steps: list[dict[str, Any]] = field(default_factory=list)
    confidence_score: float | None = None
    alternatives: list[dict[str, Any]] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    _seen_sources: set[str] = field(default_factory=set, repr=False)
    uncertainty_factors: list[str] = field(default_factory=list)
    impact_assessment: dict[str, Any] | None = None

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "decision_id": self.decision_id,
            "agent_id": self.agent_id,
            "decision_type": self.decision_type,
            "severity": self.severity,
            "summary": self.summary,
            "reasoning_steps": self.reasoning_steps,
            "confidence_score": self.confidence_score,
            "alternatives": self.alternatives,
            "sources": self.sources,
            "uncertainty_factors": self.uncertainty_factors,
            "impact_assessment": self.impact_assessment,
            "created_at": self.created_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }


@dataclass
class TransparencyResult:
    """Result of transparency validation."""

    is_compliant: bool
    violations: list[AuditViolation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    decision_context: DecisionContext | None = None
    blocked: bool = False
    block_reason: str | None = None
    validated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def error_count(self) -> int:
        """Count error-level violations."""
        return sum(
            1
            for v in self.violations
            if v.severity in [ViolationSeverity.ERROR, ViolationSeverity.CRITICAL]
        )

    @property
    def warning_count(self) -> int:
        """Count warning-level violations."""
        return sum(
            1 for v in self.violations if v.severity == ViolationSeverity.WARNING
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "is_compliant": self.is_compliant,
            "violations": [v.to_dict() for v in self.violations],
            "warnings": self.warnings,
            "decision_context": (
                self.decision_context.to_dict() if self.decision_context else None
            ),
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            "validated_at": self.validated_at.isoformat(),
            "error_count": self.error_count,
            "warning_count": self.warning_count,
        }


class TransparencyMiddleware:
    """
    Middleware that enforces transparency requirements on agent decisions.

    Validates that agent responses include required audit information
    such as reasoning chains, confidence scores, alternatives, and
    source attribution.

    Usage:
        middleware = TransparencyMiddleware()

        # Create context for a decision
        context = middleware.create_context(
            agent_id="security-reviewer",
            decision_type="vulnerability_assessment",
            severity="high",
            summary="SQL injection vulnerability detected"
        )

        # Add transparency data as agent works
        middleware.add_reasoning_step(context, 1, "Analyzed query patterns")
        middleware.set_confidence(context, 0.85)
        middleware.add_alternative(context, "option_a", "Use parameterized queries")

        # Validate before returning
        result = middleware.validate(context)
        if not result.is_compliant:
            # Handle violations
            pass
    """

    def __init__(
        self,
        config: TransparencyConfig | None = None,
        on_violation: Callable[[AuditViolation], None] | None = None,
    ):
        """
        Initialize the transparency middleware.

        Args:
            config: Transparency configuration
            on_violation: Callback for violations
        """
        self.config = config or TransparencyConfig()
        self.on_violation = on_violation

        # Thread-safe storage
        self._lock = threading.RLock()
        self._active_contexts: dict[str, DecisionContext] = {}
        self._validation_history: list[TransparencyResult] = []
        self._violation_counts: dict[str, int] = {}  # agent_id -> count

    def create_context(
        self,
        agent_id: str,
        decision_type: str,
        severity: str,
        summary: str,
        decision_id: str | None = None,
    ) -> DecisionContext:
        """
        Create a new decision context.

        Args:
            agent_id: Agent making the decision
            decision_type: Type of decision
            severity: Severity level (low, medium, high, critical)
            summary: Brief summary of the decision
            decision_id: Optional explicit decision ID

        Returns:
            DecisionContext to be populated
        """
        import uuid

        context = DecisionContext(
            decision_id=decision_id or f"dec_{uuid.uuid4().hex[:12]}",
            agent_id=agent_id,
            decision_type=decision_type,
            severity=severity,
            summary=summary,
        )

        with self._lock:
            self._active_contexts[context.decision_id] = context

        return context

    def get_context(self, decision_id: str) -> DecisionContext | None:
        """Get an active decision context."""
        with self._lock:
            return self._active_contexts.get(decision_id)

    def add_reasoning_step(
        self,
        context: DecisionContext,
        step_number: int,
        description: str,
        evidence: list[str] | None = None,
        confidence: float | None = None,
    ) -> None:
        """
        Add a reasoning step to the context.

        Args:
            context: Decision context
            step_number: Step number in the chain
            description: What was reasoned
            evidence: Supporting evidence
            confidence: Confidence in this step
        """
        step = {
            "step_number": step_number,
            "description": description,
            "evidence": evidence or [],
            "confidence": confidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        context.reasoning_steps.append(step)

    def set_confidence(self, context: DecisionContext, confidence: float) -> None:
        """
        Set the overall confidence score.

        Args:
            context: Decision context
            confidence: Confidence score (0.0 to 1.0)
        """
        context.confidence_score = max(0.0, min(1.0, confidence))

    def add_alternative(
        self,
        context: DecisionContext,
        option_id: str,
        description: str,
        confidence: float | None = None,
        pros: list[str] | None = None,
        cons: list[str] | None = None,
        was_chosen: bool = False,
    ) -> None:
        """
        Add an alternative option.

        Args:
            context: Decision context
            option_id: Identifier for the option
            description: Description of the alternative
            confidence: Confidence in this option
            pros: Advantages
            cons: Disadvantages
            was_chosen: Whether this was the selected option
        """
        alternative = {
            "option_id": option_id,
            "description": description,
            "confidence": confidence,
            "pros": pros or [],
            "cons": cons or [],
            "was_chosen": was_chosen,
        }
        context.alternatives.append(alternative)

    def add_source(self, context: DecisionContext, source: str) -> None:
        """
        Add a source attribution.

        Args:
            context: Decision context
            source: Source reference (file, URL, document, etc.)
        """
        if source not in context._seen_sources:
            context._seen_sources.add(source)
            context.sources.append(source)

    def add_uncertainty(
        self, context: DecisionContext, uncertainty_factor: str
    ) -> None:
        """
        Add an uncertainty factor.

        Args:
            context: Decision context
            uncertainty_factor: Description of uncertainty
        """
        if uncertainty_factor not in context.uncertainty_factors:
            context.uncertainty_factors.append(uncertainty_factor)

    def set_impact_assessment(
        self, context: DecisionContext, assessment: dict[str, Any]
    ) -> None:
        """
        Set the impact assessment.

        Args:
            context: Decision context
            assessment: Impact assessment details
        """
        context.impact_assessment = assessment

    def validate(self, context: DecisionContext) -> TransparencyResult:
        """
        Validate a decision context against transparency requirements.

        Args:
            context: Decision context to validate

        Returns:
            TransparencyResult with compliance status and any violations
        """
        violations: list[AuditViolation] = []
        warnings: list[str] = []

        # Check reasoning chain
        if self.config.require_reasoning_chain:
            if len(context.reasoning_steps) < self.config.min_reasoning_steps:
                violations.append(
                    AuditViolation(
                        requirement=AuditRequirement.REASONING_CHAIN,
                        severity=ViolationSeverity.ERROR,
                        message=f"Insufficient reasoning steps: {len(context.reasoning_steps)} < {self.config.min_reasoning_steps}",
                        agent_id=context.agent_id,
                        decision_id=context.decision_id,
                        expected=f">= {self.config.min_reasoning_steps} steps",
                        actual=f"{len(context.reasoning_steps)} steps",
                    )
                )

        # Check confidence score
        if self.config.require_confidence_score:
            if context.confidence_score is None:
                violations.append(
                    AuditViolation(
                        requirement=AuditRequirement.CONFIDENCE_SCORE,
                        severity=ViolationSeverity.ERROR,
                        message="Missing confidence score",
                        agent_id=context.agent_id,
                        decision_id=context.decision_id,
                        expected="0.0 - 1.0",
                        actual="None",
                    )
                )

        # Check alternatives (for high-severity decisions)
        if (
            self.config.require_alternatives
            and context.severity in self.config.alternatives_required_severity
        ):
            if len(context.alternatives) < self.config.min_alternatives:
                violations.append(
                    AuditViolation(
                        requirement=AuditRequirement.ALTERNATIVES,
                        severity=ViolationSeverity.ERROR,
                        message=f"Insufficient alternatives for {context.severity} severity decision",
                        agent_id=context.agent_id,
                        decision_id=context.decision_id,
                        expected=f">= {self.config.min_alternatives} alternatives",
                        actual=f"{len(context.alternatives)} alternatives",
                    )
                )

        # Check source attribution
        if self.config.require_source_attribution:
            if len(context.sources) < self.config.min_sources:
                # Warning for low severity, error for high
                severity = (
                    ViolationSeverity.ERROR
                    if context.severity in ["high", "critical"]
                    else ViolationSeverity.WARNING
                )
                violations.append(
                    AuditViolation(
                        requirement=AuditRequirement.SOURCE_ATTRIBUTION,
                        severity=severity,
                        message="Missing source attribution",
                        agent_id=context.agent_id,
                        decision_id=context.decision_id,
                        expected=f">= {self.config.min_sources} sources",
                        actual=f"{len(context.sources)} sources",
                    )
                )

        # Check uncertainty disclosure
        if self.config.require_uncertainty_disclosure:
            # High confidence without any uncertainty disclosure is suspicious
            if context.confidence_score and context.confidence_score > 0.90:
                if not context.uncertainty_factors:
                    warnings.append(
                        "High confidence without any uncertainty factors disclosed"
                    )

        # Check impact assessment (for critical decisions)
        if (
            self.config.require_impact_assessment
            and context.severity in self.config.impact_required_severity
        ):
            if not context.impact_assessment:
                violations.append(
                    AuditViolation(
                        requirement=AuditRequirement.IMPACT_ASSESSMENT,
                        severity=ViolationSeverity.ERROR,
                        message="Missing impact assessment for critical decision",
                        agent_id=context.agent_id,
                        decision_id=context.decision_id,
                        expected="Impact assessment required",
                        actual="None provided",
                    )
                )

        # Determine if compliant
        error_violations = [
            v
            for v in violations
            if v.severity in [ViolationSeverity.ERROR, ViolationSeverity.CRITICAL]
        ]
        is_compliant = len(error_violations) == 0

        # Determine if blocked
        blocked = False
        block_reason = None
        if not is_compliant and self.config.block_on_violation:
            blocked = True
            block_reason = "; ".join(v.message for v in error_violations[:3])

        # Mark context as completed
        context.completed_at = datetime.now(timezone.utc)

        # Create result
        result = TransparencyResult(
            is_compliant=is_compliant,
            violations=violations,
            warnings=warnings,
            decision_context=context,
            blocked=blocked,
            block_reason=block_reason,
        )

        # Store and notify
        with self._lock:
            self._validation_history.append(result)
            if len(self._validation_history) > 1000:
                self._validation_history = self._validation_history[-1000:]

            # Track violations by agent
            if violations:
                agent_id = context.agent_id
                self._violation_counts[agent_id] = self._violation_counts.get(
                    agent_id, 0
                ) + len(violations)

            # Remove from active contexts
            if context.decision_id in self._active_contexts:
                del self._active_contexts[context.decision_id]

        # Notify of violations
        if self.on_violation:
            for violation in violations:
                try:
                    self.on_violation(violation)
                except Exception as e:
                    logger.error(f"Error in violation callback: {e}")

        # Log if configured
        if self.config.log_all_decisions:
            log_level = logging.WARNING if violations else logging.DEBUG
            logger.log(
                log_level,
                f"Decision {context.decision_id}: "
                f"compliant={is_compliant}, violations={len(violations)}",
            )

        return result

    def require_transparency(
        self,
        decision_type: str,
        severity: str = "medium",
    ) -> Callable:
        """
        Decorator to require transparency on a function.

        Args:
            decision_type: Type of decision
            severity: Severity level

        Returns:
            Decorator function
        """

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                # Extract agent_id from args/kwargs or use default
                agent_id = kwargs.get("agent_id", "unknown")

                # Create context
                context = self.create_context(
                    agent_id=agent_id,
                    decision_type=decision_type,
                    severity=severity,
                    summary=f"Executing {func.__name__}",
                )

                # Inject context into kwargs
                kwargs["_transparency_context"] = context

                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    # Validate on exit
                    validation = self.validate(context)
                    if validation.blocked:
                        raise TransparencyViolationError(
                            f"Transparency requirements not met: {validation.block_reason}"
                        )

            return wrapper

        return decorator

    def get_agent_stats(self, agent_id: str) -> dict[str, Any]:
        """Get transparency statistics for an agent."""
        with self._lock:
            agent_validations = [
                v
                for v in self._validation_history
                if v.decision_context and v.decision_context.agent_id == agent_id
            ]

            if not agent_validations:
                return {
                    "agent_id": agent_id,
                    "total_decisions": 0,
                    "compliance_rate": 0,
                    "violation_count": 0,
                }

            compliant = sum(1 for v in agent_validations if v.is_compliant)
            total_violations = self._violation_counts.get(agent_id, 0)

            return {
                "agent_id": agent_id,
                "total_decisions": len(agent_validations),
                "compliant_decisions": compliant,
                "compliance_rate": compliant / len(agent_validations),
                "violation_count": total_violations,
                "blocked_decisions": sum(1 for v in agent_validations if v.blocked),
            }

    def get_overall_stats(self) -> dict[str, Any]:
        """Get overall transparency statistics."""
        with self._lock:
            if not self._validation_history:
                return {
                    "total_decisions": 0,
                    "compliance_rate": 0,
                    "by_requirement": {},
                }

            total = len(self._validation_history)
            compliant = 0
            blocked_count = 0
            requirement_counts: dict[str, int] = {}

            # Single-pass counting for compliant, blocked, and violations
            for v in self._validation_history:
                if v.is_compliant:
                    compliant += 1
                if v.blocked:
                    blocked_count += 1
                for violation in v.violations:
                    req = violation.requirement.value
                    requirement_counts[req] = requirement_counts.get(req, 0) + 1

            return {
                "total_decisions": total,
                "compliant_decisions": compliant,
                "compliance_rate": compliant / total,
                "blocked_decisions": blocked_count,
                "by_requirement": requirement_counts,
                "agents_tracked": len(self._violation_counts),
            }

    def get_validation_history(
        self,
        agent_id: str | None = None,
        compliant_only: bool | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get validation history."""
        with self._lock:
            results = self._validation_history.copy()

            if agent_id:
                results = [
                    r
                    for r in results
                    if r.decision_context and r.decision_context.agent_id == agent_id
                ]
            if compliant_only is not None:
                results = [r for r in results if r.is_compliant == compliant_only]

            # Sort by time, most recent first
            results.sort(key=lambda r: r.validated_at, reverse=True)

            return [r.to_dict() for r in results[:limit]]

    def clear_history(self) -> None:
        """Clear all history (for testing)."""
        with self._lock:
            self._active_contexts.clear()
            self._validation_history.clear()
            self._violation_counts.clear()


class TransparencyViolationError(Exception):
    """Raised when transparency requirements are not met."""
