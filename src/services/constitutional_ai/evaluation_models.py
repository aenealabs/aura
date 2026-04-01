"""Data models for Constitutional AI Phase 4 evaluation infrastructure.

This module defines data structures for the LLM-as-Judge evaluation pipeline,
golden set regression testing, and quality metrics tracking as specified in
ADR-063 Phase 4 (Evaluation).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from src.services.constitutional_ai.models import ConstitutionalContext


class JudgePreference(Enum):
    """Preference verdict from LLM-as-Judge evaluation.

    Used to indicate which response in a pair is preferred:
    - RESPONSE_A: Original/baseline response is preferred
    - RESPONSE_B: Revised/alternative response is preferred
    - TIE: Both responses are equally good
    - INVALID: Could not determine preference (error case)
    """

    RESPONSE_A = "a"
    RESPONSE_B = "b"
    TIE = "tie"
    INVALID = "invalid"

    @classmethod
    def from_string(cls, value: str) -> "JudgePreference":
        """Create preference from string value.

        Args:
            value: String representation ("a", "b", "tie", or "invalid")

        Returns:
            Corresponding JudgePreference enum value
        """
        value_lower = value.lower().strip()
        for pref in cls:
            if pref.value == value_lower:
                return pref
        return cls.INVALID


class GoldenSetCategory(Enum):
    """Categories for golden set test cases.

    Aligns with PrincipleCategory but focused on evaluation:
    - SECURITY: Security vulnerability detection (principles 1-3)
    - COMPLIANCE: Regulatory compliance (principles 4-5)
    - HELPFULNESS: Genuine assistance (principles 8-9)
    - ANTI_SYCOPHANCY: Honest feedback (principles 10-11)
    - CODE_QUALITY: Code standards (principles 12-15)
    """

    SECURITY = "security"
    COMPLIANCE = "compliance"
    HELPFULNESS = "helpfulness"
    ANTI_SYCOPHANCY = "anti_sycophancy"
    CODE_QUALITY = "code_quality"

    @classmethod
    def from_string(cls, value: str) -> "GoldenSetCategory":
        """Create category from string value."""
        try:
            return cls(value.lower())
        except ValueError:
            valid_values = [c.value for c in cls]
            raise ValueError(
                f"Invalid category '{value}'. Must be one of: {valid_values}"
            )


class RegressionSeverity(Enum):
    """Severity of a regression detected in golden set testing.

    - CRITICAL: Core safety/security principle regressed
    - HIGH: Important compliance/quality principle regressed
    - MEDIUM: Moderate quality degradation
    - LOW: Minor behavioral change
    """

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ResponsePair:
    """A pair of responses for LLM-as-Judge evaluation.

    Used for preference evaluation where the judge compares two responses
    and determines which better aligns with constitutional principles.

    Attributes:
        pair_id: Unique identifier for this response pair
        prompt: The original prompt/request that generated responses
        response_a: First response (typically baseline/original)
        response_b: Second response (typically revised/alternative)
        context: Constitutional context for evaluation
        applicable_principles: List of principle IDs to evaluate against
        human_preference: Human-annotated preference ("a", "b", "tie")
        human_reasoning: Human explanation for preference
        metadata: Additional metadata (source, version, tags)
    """

    pair_id: str
    prompt: str
    response_a: str
    response_b: str
    context: ConstitutionalContext
    applicable_principles: List[str] = field(default_factory=list)
    human_preference: Optional[str] = None
    human_reasoning: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate response pair after initialization."""
        if not self.pair_id:
            raise ValueError("pair_id cannot be empty")
        if not self.prompt:
            raise ValueError("prompt cannot be empty")
        if not self.response_a:
            raise ValueError("response_a cannot be empty")
        if not self.response_b:
            raise ValueError("response_b cannot be empty")
        if self.human_preference and self.human_preference not in ("a", "b", "tie"):
            raise ValueError(
                f"human_preference must be 'a', 'b', or 'tie', got '{self.human_preference}'"
            )

    @property
    def has_human_label(self) -> bool:
        """Check if this pair has a human preference label."""
        return self.human_preference is not None

    def to_dict(self) -> Dict[str, Any]:
        """Convert response pair to dictionary representation."""
        return {
            "pair_id": self.pair_id,
            "prompt": self.prompt,
            "response_a": self.response_a,
            "response_b": self.response_b,
            "context": self.context.to_dict(),
            "applicable_principles": self.applicable_principles,
            "human_preference": self.human_preference,
            "human_reasoning": self.human_reasoning,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResponsePair":
        """Create response pair from dictionary."""
        context_data = data.get("context", {})
        if isinstance(context_data, dict):
            context = ConstitutionalContext(
                agent_name=context_data.get("agent_name", "unknown"),
                operation_type=context_data.get("operation_type", "unknown"),
                user_request=context_data.get("user_request"),
                domain_tags=context_data.get("domain_tags", []),
                metadata=context_data.get("metadata", {}),
            )
        else:
            context = context_data

        return cls(
            pair_id=data["pair_id"],
            prompt=data["prompt"],
            response_a=data["response_a"],
            response_b=data["response_b"],
            context=context,
            applicable_principles=data.get("applicable_principles", []),
            human_preference=data.get("human_preference"),
            human_reasoning=data.get("human_reasoning"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class JudgeResult:
    """Result of LLM-as-Judge evaluation on a response pair.

    Attributes:
        pair_id: ID of the evaluated response pair
        judge_preference: Which response the judge preferred
        judge_reasoning: Chain-of-thought reasoning for the preference
        confidence: Confidence score (0.0-1.0) in the judgment
        principles_evaluated: Principles considered in evaluation
        agrees_with_human: Whether judge agrees with human label (if available)
        latency_ms: Time taken for evaluation in milliseconds
        timestamp: When the evaluation was performed
        metadata: Additional evaluation metadata
    """

    pair_id: str
    judge_preference: JudgePreference
    judge_reasoning: str
    confidence: float = 0.0
    principles_evaluated: List[str] = field(default_factory=list)
    agrees_with_human: Optional[bool] = None
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate judge result after initialization."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"confidence must be between 0.0 and 1.0, got {self.confidence}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert judge result to dictionary representation."""
        return {
            "pair_id": self.pair_id,
            "judge_preference": self.judge_preference.value,
            "judge_reasoning": self.judge_reasoning,
            "confidence": self.confidence,
            "principles_evaluated": self.principles_evaluated,
            "agrees_with_human": self.agrees_with_human,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JudgeResult":
        """Create judge result from dictionary."""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now(timezone.utc)

        return cls(
            pair_id=data["pair_id"],
            judge_preference=JudgePreference.from_string(data["judge_preference"]),
            judge_reasoning=data.get("judge_reasoning", ""),
            confidence=data.get("confidence", 0.0),
            principles_evaluated=data.get("principles_evaluated", []),
            agrees_with_human=data.get("agrees_with_human"),
            latency_ms=data.get("latency_ms", 0.0),
            timestamp=timestamp,
            metadata=data.get("metadata", {}),
        )


@dataclass
class ExpectedCritique:
    """Expected critique result for a golden set case.

    Defines what the critique service should detect for a given test case.

    Attributes:
        principle_id: ID of the principle being tested
        should_flag: Whether this principle should flag an issue
        expected_issues: List of expected issue descriptions (partial match)
        severity_if_flagged: Expected severity if flagged
    """

    principle_id: str
    should_flag: bool
    expected_issues: List[str] = field(default_factory=list)
    severity_if_flagged: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "principle_id": self.principle_id,
            "should_flag": self.should_flag,
            "expected_issues": self.expected_issues,
            "severity_if_flagged": self.severity_if_flagged,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExpectedCritique":
        """Create from dictionary."""
        return cls(
            principle_id=data["principle_id"],
            should_flag=data.get("should_flag", False),
            expected_issues=data.get("expected_issues", []),
            severity_if_flagged=data.get("severity_if_flagged"),
        )


@dataclass
class GoldenSetCase:
    """A verified test case in the regression golden set.

    Golden set cases are hand-verified examples that ensure the critique
    service maintains consistent behavior over time.

    Attributes:
        case_id: Unique identifier for this test case
        category: Category of the test case (security, compliance, etc.)
        input_prompt: The prompt/request that generated the output
        agent_output: The agent output to be critiqued
        expected_critiques: Expected critique results by principle
        expected_revision_needed: Whether revision should be required
        human_verified_at: When the case was verified by a human
        verifier_id: Identifier of the human verifier
        tags: Optional tags for filtering (e.g., ["owasp", "sql_injection"])
        metadata: Additional case metadata
    """

    case_id: str
    category: GoldenSetCategory
    input_prompt: str
    agent_output: str
    expected_critiques: List[ExpectedCritique]
    expected_revision_needed: bool
    human_verified_at: datetime
    verifier_id: str
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate golden set case after initialization."""
        if not self.case_id:
            raise ValueError("case_id cannot be empty")
        if not self.input_prompt:
            raise ValueError("input_prompt cannot be empty")
        if not self.agent_output:
            raise ValueError("agent_output cannot be empty")
        if not self.verifier_id:
            raise ValueError("verifier_id cannot be empty")

    @property
    def principle_ids(self) -> List[str]:
        """Get list of principle IDs being tested."""
        return [ec.principle_id for ec in self.expected_critiques]

    @property
    def expected_flagged_principles(self) -> List[str]:
        """Get list of principles expected to be flagged."""
        return [ec.principle_id for ec in self.expected_critiques if ec.should_flag]

    def to_dict(self) -> Dict[str, Any]:
        """Convert golden set case to dictionary representation."""
        return {
            "case_id": self.case_id,
            "category": self.category.value,
            "input_prompt": self.input_prompt,
            "agent_output": self.agent_output,
            "expected_critiques": [ec.to_dict() for ec in self.expected_critiques],
            "expected_revision_needed": self.expected_revision_needed,
            "human_verified_at": self.human_verified_at.isoformat(),
            "verifier_id": self.verifier_id,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GoldenSetCase":
        """Create golden set case from dictionary."""
        verified_at = data.get("human_verified_at")
        if isinstance(verified_at, str):
            verified_at = datetime.fromisoformat(verified_at)
        elif verified_at is None:
            verified_at = datetime.now(timezone.utc)

        expected_critiques = [
            ExpectedCritique.from_dict(ec) for ec in data.get("expected_critiques", [])
        ]

        return cls(
            case_id=data["case_id"],
            category=GoldenSetCategory.from_string(data["category"]),
            input_prompt=data["input_prompt"],
            agent_output=data["agent_output"],
            expected_critiques=expected_critiques,
            expected_revision_needed=data.get("expected_revision_needed", False),
            human_verified_at=verified_at,
            verifier_id=data.get("verifier_id", "unknown"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class RegressionItem:
    """A single regression detected during golden set testing.

    Attributes:
        case_id: ID of the golden set case that regressed
        principle_id: ID of the principle that regressed
        regression_type: Type of regression (false_negative, false_positive, severity_change)
        expected: What was expected
        actual: What actually happened
        severity: Severity of this regression
        details: Additional details about the regression
    """

    case_id: str
    principle_id: str
    regression_type: str
    expected: str
    actual: str
    severity: RegressionSeverity
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert regression item to dictionary representation."""
        return {
            "case_id": self.case_id,
            "principle_id": self.principle_id,
            "regression_type": self.regression_type,
            "expected": self.expected,
            "actual": self.actual,
            "severity": self.severity.value,
            "details": self.details,
        }


@dataclass
class RegressionReport:
    """Report of regression testing against the golden set.

    Attributes:
        run_id: Unique identifier for this regression run
        total_cases: Total number of golden set cases tested
        passed_cases: Number of cases that passed
        failed_cases: Number of cases with regressions
        regressions: List of individual regressions detected
        pass_rate: Percentage of cases that passed (0.0-1.0)
        critical_regressions: Count of critical severity regressions
        run_timestamp: When the regression test was run
        run_duration_ms: Duration of the regression test in milliseconds
        metadata: Additional run metadata
    """

    run_id: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    regressions: List[RegressionItem]
    pass_rate: float
    critical_regressions: int = 0
    run_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    run_duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate and compute derived fields."""
        if not 0.0 <= self.pass_rate <= 1.0:
            raise ValueError(
                f"pass_rate must be between 0.0 and 1.0, got {self.pass_rate}"
            )
        # Count critical regressions if not provided
        if self.critical_regressions == 0 and self.regressions:
            self.critical_regressions = sum(
                1 for r in self.regressions if r.severity == RegressionSeverity.CRITICAL
            )

    @property
    def has_critical_regressions(self) -> bool:
        """Check if any critical regressions were detected."""
        return self.critical_regressions > 0

    @property
    def is_passing(self) -> bool:
        """Check if the regression test passed (no critical regressions)."""
        return not self.has_critical_regressions

    def to_dict(self) -> Dict[str, Any]:
        """Convert regression report to dictionary representation."""
        return {
            "run_id": self.run_id,
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "failed_cases": self.failed_cases,
            "regressions": [r.to_dict() for r in self.regressions],
            "pass_rate": self.pass_rate,
            "critical_regressions": self.critical_regressions,
            "run_timestamp": self.run_timestamp.isoformat(),
            "run_duration_ms": self.run_duration_ms,
            "metadata": self.metadata,
        }


@dataclass
class EvaluationDataset:
    """Container for an evaluation dataset with diversity requirements.

    Attributes:
        dataset_id: Unique identifier for this dataset
        version: Semantic version of the dataset (e.g., "1.0.0")
        name: Human-readable name for the dataset
        description: Description of the dataset
        response_pairs: List of response pairs for evaluation
        diversity_metrics: Metrics tracking principle/category coverage
        created_at: When the dataset was created
        metadata: Additional dataset metadata
    """

    dataset_id: str
    version: str
    name: str
    description: str
    response_pairs: List[ResponsePair]
    diversity_metrics: Dict[str, int] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate and compute diversity metrics."""
        if not self.dataset_id:
            raise ValueError("dataset_id cannot be empty")
        if not self.version:
            raise ValueError("version cannot be empty")
        # Compute diversity metrics if not provided
        if not self.diversity_metrics and self.response_pairs:
            self._compute_diversity_metrics()

    def _compute_diversity_metrics(self) -> None:
        """Compute diversity metrics from response pairs."""
        principle_counts: Dict[str, int] = {}
        agent_counts: Dict[str, int] = {}
        operation_counts: Dict[str, int] = {}

        for pair in self.response_pairs:
            for principle_id in pair.applicable_principles:
                principle_counts[principle_id] = (
                    principle_counts.get(principle_id, 0) + 1
                )
            agent_name = pair.context.agent_name
            agent_counts[agent_name] = agent_counts.get(agent_name, 0) + 1
            op_type = pair.context.operation_type
            operation_counts[op_type] = operation_counts.get(op_type, 0) + 1

        self.diversity_metrics = {
            "total_pairs": len(self.response_pairs),
            "unique_principles": len(principle_counts),
            "unique_agents": len(agent_counts),
            "unique_operations": len(operation_counts),
            "labeled_pairs": sum(1 for p in self.response_pairs if p.has_human_label),
        }

    @property
    def pair_count(self) -> int:
        """Get total number of response pairs."""
        return len(self.response_pairs)

    @property
    def labeled_count(self) -> int:
        """Get number of pairs with human labels."""
        return sum(1 for p in self.response_pairs if p.has_human_label)

    def to_dict(self) -> Dict[str, Any]:
        """Convert dataset to dictionary representation."""
        return {
            "dataset_id": self.dataset_id,
            "version": self.version,
            "name": self.name,
            "description": self.description,
            "response_pairs": [p.to_dict() for p in self.response_pairs],
            "diversity_metrics": self.diversity_metrics,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvaluationDataset":
        """Create dataset from dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now(timezone.utc)

        response_pairs = [
            ResponsePair.from_dict(p) for p in data.get("response_pairs", [])
        ]

        return cls(
            dataset_id=data["dataset_id"],
            version=data["version"],
            name=data.get("name", "Unnamed Dataset"),
            description=data.get("description", ""),
            response_pairs=response_pairs,
            diversity_metrics=data.get("diversity_metrics", {}),
            created_at=created_at,
            metadata=data.get("metadata", {}),
        )


@dataclass
class EvaluationMetrics:
    """Aggregated metrics from an evaluation run.

    Used for CloudWatch publishing and quality tracking.

    Attributes:
        critique_accuracy: Agreement rate with human labels (0.0-1.0)
        revision_convergence_rate: Rate of successful revisions (0.0-1.0)
        cache_hit_rate: Semantic cache hit rate (0.0-1.0)
        non_evasive_rate: Rate of constructive engagement (0.0-1.0)
        golden_set_pass_rate: Golden set regression test pass rate (0.0-1.0)
        critique_latency_p95_ms: P95 latency for critique in milliseconds
        evaluation_pairs_processed: Number of pairs evaluated
        critique_count: Total number of critiques performed
        issues_by_severity: Count of issues by severity level
        run_timestamp: When the evaluation was performed
    """

    critique_accuracy: float
    revision_convergence_rate: float
    cache_hit_rate: float
    non_evasive_rate: float
    golden_set_pass_rate: float
    critique_latency_p95_ms: float
    evaluation_pairs_processed: int = 0
    critique_count: int = 0
    issues_by_severity: Dict[str, int] = field(default_factory=dict)
    run_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Validate metrics."""
        for field_name, value in [
            ("critique_accuracy", self.critique_accuracy),
            ("revision_convergence_rate", self.revision_convergence_rate),
            ("cache_hit_rate", self.cache_hit_rate),
            ("non_evasive_rate", self.non_evasive_rate),
            ("golden_set_pass_rate", self.golden_set_pass_rate),
        ]:
            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"{field_name} must be between 0.0 and 1.0, got {value}"
                )

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary representation."""
        return {
            "critique_accuracy": self.critique_accuracy,
            "revision_convergence_rate": self.revision_convergence_rate,
            "cache_hit_rate": self.cache_hit_rate,
            "non_evasive_rate": self.non_evasive_rate,
            "golden_set_pass_rate": self.golden_set_pass_rate,
            "critique_latency_p95_ms": self.critique_latency_p95_ms,
            "evaluation_pairs_processed": self.evaluation_pairs_processed,
            "critique_count": self.critique_count,
            "issues_by_severity": self.issues_by_severity,
            "run_timestamp": self.run_timestamp.isoformat(),
        }

    def meets_targets(self) -> Dict[str, bool]:
        """Check if metrics meet ADR-063 targets.

        Returns:
            Dict mapping metric name to whether target is met
        """
        return {
            "critique_accuracy": self.critique_accuracy >= 0.90,
            "revision_convergence_rate": self.revision_convergence_rate >= 0.95,
            "cache_hit_rate": self.cache_hit_rate >= 0.30,
            "non_evasive_rate": self.non_evasive_rate >= 0.70,
            "critique_latency_p95": self.critique_latency_p95_ms <= 500.0,
        }
