"""Data models for Constitutional AI.

This module defines the core data structures used throughout the Constitutional AI
system, including principles, critique results, and revision results.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class PrincipleSeverity(Enum):
    """Severity levels for constitutional principles.

    Severity determines how principle violations are handled:
    - CRITICAL: Must pass, blocks execution if violated
    - HIGH: Strong recommendation, flagged for review
    - MEDIUM: Moderate concern, logged for awareness
    - LOW: Style/quality preference, informational only
    """

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @classmethod
    def from_string(cls, value: str) -> "PrincipleSeverity":
        """Create severity from string value.

        Args:
            value: String representation of severity

        Returns:
            Corresponding PrincipleSeverity enum value

        Raises:
            ValueError: If value doesn't match any severity
        """
        try:
            return cls(value.lower())
        except ValueError:
            valid_values = [s.value for s in cls]
            raise ValueError(
                f"Invalid severity '{value}'. Must be one of: {valid_values}"
            )


class PrincipleCategory(Enum):
    """Categories for constitutional principles.

    Categories help organize principles and enable selective application:
    - SAFETY: Security vulnerabilities, data protection
    - COMPLIANCE: Regulatory requirements (CMMC, SOX, NIST)
    - TRANSPARENCY: Clear communication, avoiding deception
    - HELPFULNESS: Providing genuinely useful assistance
    - ANTI_SYCOPHANCY: Maintaining honest, objective responses
    - CODE_QUALITY: Code standards, maintainability, patterns
    - META: Cross-cutting concerns, conflict resolution
    """

    SAFETY = "safety"
    COMPLIANCE = "compliance"
    TRANSPARENCY = "transparency"
    HELPFULNESS = "helpfulness"
    ANTI_SYCOPHANCY = "anti_sycophancy"
    CODE_QUALITY = "code_quality"
    META = "meta"

    @classmethod
    def from_string(cls, value: str) -> "PrincipleCategory":
        """Create category from string value.

        Args:
            value: String representation of category

        Returns:
            Corresponding PrincipleCategory enum value

        Raises:
            ValueError: If value doesn't match any category
        """
        try:
            return cls(value.lower())
        except ValueError:
            valid_values = [c.value for c in cls]
            raise ValueError(
                f"Invalid category '{value}'. Must be one of: {valid_values}"
            )


@dataclass
class ConstitutionalPrinciple:
    """A single constitutional principle for AI behavior guidance.

    Attributes:
        id: Unique identifier for the principle (e.g., "principle_1_security_first")
        name: Human-readable name (e.g., "Security-First Code Generation")
        critique_prompt: Prompt template for evaluating outputs against this principle
        revision_prompt: Prompt template for revising outputs that violate this principle
        severity: How critical violations of this principle are
        category: Category this principle belongs to
        domain_tags: Optional tags for domain-specific filtering (e.g., ["security", "owasp"])
        enabled: Whether this principle is currently active
    """

    id: str
    name: str
    critique_prompt: str
    revision_prompt: str
    severity: PrincipleSeverity
    category: PrincipleCategory
    domain_tags: List[str] = field(default_factory=list)
    enabled: bool = True

    def __post_init__(self) -> None:
        """Validate principle after initialization."""
        if not self.id:
            raise ValueError("Principle id cannot be empty")
        if not self.name:
            raise ValueError("Principle name cannot be empty")
        if not self.critique_prompt:
            raise ValueError("Principle critique_prompt cannot be empty")
        if not self.revision_prompt:
            raise ValueError("Principle revision_prompt cannot be empty")

    def to_dict(self) -> Dict[str, Any]:
        """Convert principle to dictionary representation.

        Returns:
            Dictionary with all principle fields
        """
        return {
            "id": self.id,
            "name": self.name,
            "critique_prompt": self.critique_prompt,
            "revision_prompt": self.revision_prompt,
            "severity": self.severity.value,
            "category": self.category.value,
            "domain_tags": self.domain_tags,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConstitutionalPrinciple":
        """Create principle from dictionary.

        Args:
            data: Dictionary containing principle fields

        Returns:
            ConstitutionalPrinciple instance
        """
        return cls(
            id=data["id"],
            name=data["name"],
            critique_prompt=data["critique_prompt"],
            revision_prompt=data["revision_prompt"],
            severity=PrincipleSeverity.from_string(data["severity"]),
            category=PrincipleCategory.from_string(data["category"]),
            domain_tags=data.get("domain_tags", []),
            enabled=data.get("enabled", True),
        )


@dataclass
class CritiqueResult:
    """Result of evaluating an output against a constitutional principle.

    Attributes:
        principle_id: ID of the principle that was evaluated
        principle_name: Human-readable name of the principle
        severity: Severity level of the principle
        issues_found: List of specific issues identified
        reasoning: Chain-of-thought reasoning for the evaluation
        requires_revision: Whether the output needs revision for this principle
        confidence: Confidence score (0.0-1.0) in the evaluation
        timestamp: When the critique was performed
        metadata: Additional context or debugging information
    """

    principle_id: str
    principle_name: str
    severity: PrincipleSeverity
    issues_found: List[str]
    reasoning: str
    requires_revision: bool
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate critique result after initialization."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )
        if self.issues_found is None:
            self.issues_found = []

    @property
    def is_critical(self) -> bool:
        """Check if this critique result is critical and requires revision."""
        return self.severity == PrincipleSeverity.CRITICAL and self.requires_revision

    @property
    def has_issues(self) -> bool:
        """Check if any issues were found."""
        return len(self.issues_found) > 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert critique result to dictionary representation.

        Returns:
            Dictionary with all critique result fields
        """
        return {
            "principle_id": self.principle_id,
            "principle_name": self.principle_name,
            "severity": self.severity.value,
            "issues_found": self.issues_found,
            "reasoning": self.reasoning,
            "requires_revision": self.requires_revision,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CritiqueResult":
        """Create critique result from dictionary.

        Args:
            data: Dictionary containing critique result fields

        Returns:
            CritiqueResult instance
        """
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now(timezone.utc)

        return cls(
            principle_id=data["principle_id"],
            principle_name=data["principle_name"],
            severity=PrincipleSeverity.from_string(data["severity"]),
            issues_found=data.get("issues_found", []),
            reasoning=data.get("reasoning", ""),
            requires_revision=data.get("requires_revision", False),
            confidence=data.get("confidence", 0.0),
            timestamp=timestamp,
            metadata=data.get("metadata", {}),
        )


@dataclass
class RevisionResult:
    """Result of revising an output based on critique feedback.

    Attributes:
        original_output: The original AI output before revision
        revised_output: The output after applying revisions
        critiques_addressed: List of principle IDs that were addressed
        reasoning_chain: Full chain of reasoning for the revisions
        revision_iterations: Number of revision iterations performed
        converged: Whether all critical issues were resolved
        timestamp: When the revision was completed
        metadata: Additional context or debugging information
    """

    original_output: str
    revised_output: str
    critiques_addressed: List[str]
    reasoning_chain: str
    revision_iterations: int
    converged: bool = True
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate revision result after initialization."""
        if self.revision_iterations < 0:
            raise ValueError(
                f"revision_iterations must be non-negative, got {self.revision_iterations}"
            )
        if self.critiques_addressed is None:
            self.critiques_addressed = []

    @property
    def was_modified(self) -> bool:
        """Check if the output was actually modified."""
        return self.original_output != self.revised_output

    @property
    def critique_count(self) -> int:
        """Get the number of critiques that were addressed."""
        return len(self.critiques_addressed)

    def to_dict(self) -> Dict[str, Any]:
        """Convert revision result to dictionary representation.

        Returns:
            Dictionary with all revision result fields
        """
        return {
            "original_output": self.original_output,
            "revised_output": self.revised_output,
            "critiques_addressed": self.critiques_addressed,
            "reasoning_chain": self.reasoning_chain,
            "revision_iterations": self.revision_iterations,
            "converged": self.converged,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RevisionResult":
        """Create revision result from dictionary.

        Args:
            data: Dictionary containing revision result fields

        Returns:
            RevisionResult instance
        """
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now(timezone.utc)

        return cls(
            original_output=data["original_output"],
            revised_output=data["revised_output"],
            critiques_addressed=data.get("critiques_addressed", []),
            reasoning_chain=data.get("reasoning_chain", ""),
            revision_iterations=data.get("revision_iterations", 0),
            converged=data.get("converged", True),
            timestamp=timestamp,
            metadata=data.get("metadata", {}),
        )


@dataclass
class ConstitutionalContext:
    """Context provided to constitutional evaluation.

    Attributes:
        agent_name: Name of the agent that generated the output
        operation_type: Type of operation being performed
        user_request: Original user request (if applicable)
        domain_tags: Tags for filtering applicable principles
        metadata: Additional context for evaluation
    """

    agent_name: str
    operation_type: str
    user_request: Optional[str] = None
    domain_tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary representation.

        Returns:
            Dictionary with all context fields
        """
        return {
            "agent_name": self.agent_name,
            "operation_type": self.operation_type,
            "user_request": self.user_request,
            "domain_tags": self.domain_tags,
            "metadata": self.metadata,
        }


@dataclass
class ConstitutionalEvaluationSummary:
    """Summary of a complete constitutional evaluation.

    Attributes:
        total_principles_evaluated: Number of principles checked
        critical_issues: Number of critical issues found
        high_issues: Number of high severity issues found
        medium_issues: Number of medium severity issues found
        low_issues: Number of low severity issues found
        requires_revision: Whether any issues require revision
        requires_hitl: Whether human review is required
        critiques: List of all critique results
        evaluation_time_ms: Time taken for evaluation in milliseconds
    """

    total_principles_evaluated: int
    critical_issues: int
    high_issues: int
    medium_issues: int
    low_issues: int
    requires_revision: bool
    requires_hitl: bool
    critiques: List[CritiqueResult]
    evaluation_time_ms: float = 0.0

    @classmethod
    def from_critiques(
        cls,
        critiques: List[CritiqueResult],
        evaluation_time_ms: float = 0.0,
    ) -> "ConstitutionalEvaluationSummary":
        """Create summary from list of critiques.

        Args:
            critiques: List of critique results
            evaluation_time_ms: Time taken for evaluation

        Returns:
            ConstitutionalEvaluationSummary instance
        """
        critical_issues = sum(
            1
            for c in critiques
            if c.severity == PrincipleSeverity.CRITICAL and c.requires_revision
        )
        high_issues = sum(
            1
            for c in critiques
            if c.severity == PrincipleSeverity.HIGH and c.requires_revision
        )
        medium_issues = sum(
            1
            for c in critiques
            if c.severity == PrincipleSeverity.MEDIUM and c.requires_revision
        )
        low_issues = sum(
            1
            for c in critiques
            if c.severity == PrincipleSeverity.LOW and c.requires_revision
        )

        requires_revision = any(c.requires_revision for c in critiques)
        requires_hitl = critical_issues > 0

        return cls(
            total_principles_evaluated=len(critiques),
            critical_issues=critical_issues,
            high_issues=high_issues,
            medium_issues=medium_issues,
            low_issues=low_issues,
            requires_revision=requires_revision,
            requires_hitl=requires_hitl,
            critiques=critiques,
            evaluation_time_ms=evaluation_time_ms,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert summary to dictionary representation.

        Returns:
            Dictionary with all summary fields
        """
        return {
            "total_principles_evaluated": self.total_principles_evaluated,
            "critical_issues": self.critical_issues,
            "high_issues": self.high_issues,
            "medium_issues": self.medium_issues,
            "low_issues": self.low_issues,
            "requires_revision": self.requires_revision,
            "requires_hitl": self.requires_hitl,
            "critiques": [c.to_dict() for c in self.critiques],
            "evaluation_time_ms": self.evaluation_time_ms,
        }
