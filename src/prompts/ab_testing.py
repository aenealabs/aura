"""
A/B Testing Framework for Chain of Draft (CoD) vs Chain of Thought (CoT) Prompts

Provides infrastructure for comparing prompt effectiveness, measuring token savings,
and tracking accuracy metrics across different prompt modes.

ADR-029 Phase 1.2 Implementation
"""

import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, TypeVar

from src.prompts.cod_templates import (
    CoDPromptMode,
    build_cod_prompt,
    estimate_token_savings,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ABTestVariant(Enum):
    """Variants for A/B testing."""

    CONTROL = "control"  # Chain of Thought (baseline)
    TREATMENT = "treatment"  # Chain of Draft (optimization)


@dataclass
class ABTestResult:
    """Results from a single A/B test trial."""

    variant: ABTestVariant
    prompt_mode: CoDPromptMode
    agent_type: str
    prompt_tokens: int
    response_tokens: int
    latency_ms: float
    success: bool
    accuracy_score: float | None = None
    error: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ABTestSummary:
    """Summary statistics for A/B test campaign."""

    control_results: list[ABTestResult]
    treatment_results: list[ABTestResult]

    @property
    def control_avg_tokens(self) -> float:
        """Average total tokens for control group."""
        if not self.control_results:
            return 0.0
        return sum(
            r.prompt_tokens + r.response_tokens for r in self.control_results
        ) / len(self.control_results)

    @property
    def treatment_avg_tokens(self) -> float:
        """Average total tokens for treatment group."""
        if not self.treatment_results:
            return 0.0
        return sum(
            r.prompt_tokens + r.response_tokens for r in self.treatment_results
        ) / len(self.treatment_results)

    @property
    def token_savings_percent(self) -> float:
        """Percentage token savings (treatment vs control)."""
        if self.control_avg_tokens == 0:
            return 0.0
        return (
            (self.control_avg_tokens - self.treatment_avg_tokens)
            / self.control_avg_tokens
        ) * 100

    @property
    def control_avg_latency(self) -> float:
        """Average latency in ms for control group."""
        if not self.control_results:
            return 0.0
        return sum(r.latency_ms for r in self.control_results) / len(
            self.control_results
        )

    @property
    def treatment_avg_latency(self) -> float:
        """Average latency in ms for treatment group."""
        if not self.treatment_results:
            return 0.0
        return sum(r.latency_ms for r in self.treatment_results) / len(
            self.treatment_results
        )

    @property
    def latency_improvement_percent(self) -> float:
        """Percentage latency improvement (treatment vs control)."""
        if self.control_avg_latency == 0:
            return 0.0
        return (
            (self.control_avg_latency - self.treatment_avg_latency)
            / self.control_avg_latency
        ) * 100

    @property
    def control_success_rate(self) -> float:
        """Success rate for control group."""
        if not self.control_results:
            return 0.0
        return sum(1 for r in self.control_results if r.success) / len(
            self.control_results
        )

    @property
    def treatment_success_rate(self) -> float:
        """Success rate for treatment group."""
        if not self.treatment_results:
            return 0.0
        return sum(1 for r in self.treatment_results if r.success) / len(
            self.treatment_results
        )

    @property
    def control_avg_accuracy(self) -> float | None:
        """Average accuracy score for control group (if available)."""
        scores = [
            r.accuracy_score
            for r in self.control_results
            if r.accuracy_score is not None
        ]
        if not scores:
            return None
        return sum(scores) / len(scores)

    @property
    def treatment_avg_accuracy(self) -> float | None:
        """Average accuracy score for treatment group (if available)."""
        scores = [
            r.accuracy_score
            for r in self.treatment_results
            if r.accuracy_score is not None
        ]
        if not scores:
            return None
        return sum(scores) / len(scores)

    def to_dict(self) -> dict[str, Any]:
        """Convert summary to dictionary for reporting."""
        return {
            "total_trials": len(self.control_results) + len(self.treatment_results),
            "control_trials": len(self.control_results),
            "treatment_trials": len(self.treatment_results),
            "token_metrics": {
                "control_avg_tokens": round(self.control_avg_tokens, 1),
                "treatment_avg_tokens": round(self.treatment_avg_tokens, 1),
                "savings_percent": round(self.token_savings_percent, 1),
            },
            "latency_metrics": {
                "control_avg_ms": round(self.control_avg_latency, 1),
                "treatment_avg_ms": round(self.treatment_avg_latency, 1),
                "improvement_percent": round(self.latency_improvement_percent, 1),
            },
            "success_rates": {
                "control": round(self.control_success_rate * 100, 1),
                "treatment": round(self.treatment_success_rate * 100, 1),
            },
            "accuracy": {
                "control_avg": (
                    round(self.control_avg_accuracy, 3)
                    if self.control_avg_accuracy
                    else None
                ),
                "treatment_avg": (
                    round(self.treatment_avg_accuracy, 3)
                    if self.treatment_avg_accuracy
                    else None
                ),
            },
        }


class ABTestRunner:
    """
    Runs A/B tests comparing CoD (treatment) vs CoT (control) prompts.

    Features:
    - Random assignment to control/treatment groups
    - Token usage tracking
    - Latency measurement
    - Optional accuracy scoring via callback
    - Summary statistics

    Example:
        runner = ABTestRunner(llm_client)
        summary = await runner.run_test(
            agent_type="reviewer",
            test_cases=[{"code": "def foo(): pass"}],
            trials_per_case=5,
        )
        print(f"Token savings: {summary.token_savings_percent}%")
    """

    def __init__(
        self,
        llm_client: Any,
        treatment_ratio: float = 0.5,
        accuracy_scorer: Callable[[str, dict], float] | None = None,
    ):
        """
        Initialize A/B test runner.

        Args:
            llm_client: LLM client for making requests
            treatment_ratio: Probability of assigning to treatment group (0.0-1.0)
            accuracy_scorer: Optional callback to score response accuracy
        """
        self.llm = llm_client
        self.treatment_ratio = treatment_ratio
        self.accuracy_scorer = accuracy_scorer
        self.results: list[ABTestResult] = []

    def _assign_variant(self) -> ABTestVariant:
        """Randomly assign variant based on treatment ratio."""
        return (
            ABTestVariant.TREATMENT
            if random.random() < self.treatment_ratio
            else ABTestVariant.CONTROL
        )

    async def run_single_trial(
        self,
        agent_type: str,
        variant: ABTestVariant,
        **prompt_kwargs: Any,
    ) -> ABTestResult:
        """
        Run a single A/B test trial.

        Args:
            agent_type: Type of agent ("reviewer", "coder", etc.)
            variant: Which variant to test
            **prompt_kwargs: Arguments to pass to build_cod_prompt

        Returns:
            ABTestResult with metrics
        """
        # Set prompt mode based on variant
        mode = (
            CoDPromptMode.COT if variant == ABTestVariant.CONTROL else CoDPromptMode.COD
        )

        # Build prompt
        prompt = build_cod_prompt(agent_type, mode=mode, **prompt_kwargs)
        prompt_tokens = len(prompt) // 4  # Rough estimate

        # Call LLM with timing
        start_time = time.perf_counter()
        success = True
        error = None
        response = ""

        try:
            response = await self.llm.generate(prompt, agent=agent_type.title())
        except Exception as e:
            success = False
            error = str(e)
            logger.error(f"A/B test trial failed: {e}")

        latency_ms = (time.perf_counter() - start_time) * 1000
        response_tokens = len(response) // 4 if response else 0

        # Calculate accuracy if scorer provided
        accuracy_score = None
        if self.accuracy_scorer and success:
            try:
                accuracy_score = self.accuracy_scorer(response, prompt_kwargs)
            except Exception as e:
                logger.warning(f"Accuracy scoring failed: {e}")

        result = ABTestResult(
            variant=variant,
            prompt_mode=mode,
            agent_type=agent_type,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
            latency_ms=latency_ms,
            success=success,
            accuracy_score=accuracy_score,
            error=error,
            metadata=prompt_kwargs,
        )

        self.results.append(result)
        return result

    async def run_test(
        self,
        agent_type: str,
        test_cases: list[dict[str, Any]],
        trials_per_case: int = 1,
    ) -> ABTestSummary:
        """
        Run A/B test across multiple test cases.

        Args:
            agent_type: Type of agent to test
            test_cases: List of prompt kwargs dicts
            trials_per_case: Number of trials per test case

        Returns:
            ABTestSummary with aggregate statistics
        """
        logger.info(
            f"Starting A/B test: {len(test_cases)} cases × {trials_per_case} trials"
        )

        for _case_idx, case in enumerate(test_cases):
            for _trial_idx in range(trials_per_case):
                variant = self._assign_variant()
                await self.run_single_trial(agent_type, variant, **case)

        return self.get_summary()

    async def run_balanced_test(
        self,
        agent_type: str,
        test_cases: list[dict[str, Any]],
    ) -> ABTestSummary:
        """
        Run balanced A/B test where each case is tested with both variants.

        This ensures equal representation and is better for statistical comparison.

        Args:
            agent_type: Type of agent to test
            test_cases: List of prompt kwargs dicts

        Returns:
            ABTestSummary with aggregate statistics
        """
        logger.info(f"Starting balanced A/B test: {len(test_cases)} cases × 2 variants")

        for case in test_cases:
            # Run both variants for each case
            await self.run_single_trial(agent_type, ABTestVariant.CONTROL, **case)
            await self.run_single_trial(agent_type, ABTestVariant.TREATMENT, **case)

        return self.get_summary()

    def get_summary(self) -> ABTestSummary:
        """Get summary of all test results."""
        control = [r for r in self.results if r.variant == ABTestVariant.CONTROL]
        treatment = [r for r in self.results if r.variant == ABTestVariant.TREATMENT]
        return ABTestSummary(control_results=control, treatment_results=treatment)

    def clear_results(self) -> None:
        """Clear all stored results."""
        self.results = []


def security_review_accuracy_scorer(response: str, prompt_kwargs: dict) -> float:
    """
    Score accuracy of security review responses.

    Checks if response correctly identifies vulnerabilities in known test cases.

    Args:
        response: LLM response string
        prompt_kwargs: Original prompt parameters including code

    Returns:
        Accuracy score from 0.0 to 1.0
    """
    code = prompt_kwargs.get("code", "")
    response_lower = response.lower()

    # Known vulnerability patterns to detect
    expected_findings = []

    if "sha1" in code.lower() or "hashlib.sha1" in code.lower():
        expected_findings.append("sha1")
    if "md5" in code.lower():
        expected_findings.append("md5")
    if "eval(" in code:
        expected_findings.append("eval")
    if "exec(" in code:
        expected_findings.append("exec")
    if "password=" in code.lower() and '"' in code:
        expected_findings.append("password")

    if not expected_findings:
        # No known vulnerabilities, check for PASS status
        return 1.0 if "pass" in response_lower else 0.5

    # Score based on how many findings were detected
    detected = sum(1 for f in expected_findings if f in response_lower)
    return detected / len(expected_findings)


# Convenience function for quick testing
async def quick_ab_test(
    llm_client: Any,
    agent_type: str = "reviewer",
    num_trials: int = 10,
) -> ABTestSummary:
    """
    Run a quick A/B test with synthetic test cases.

    Args:
        llm_client: LLM client for making requests
        agent_type: Type of agent to test
        num_trials: Number of trials to run

    Returns:
        ABTestSummary with results
    """
    # Generate synthetic test cases
    test_cases = [
        {"code": "import hashlib\ndef foo(): return hashlib.sha1(b'data').hexdigest()"},
        {"code": "def process(data): return eval(data)"},
        {
            "code": "import hashlib\ndef secure(): return hashlib.sha256(b'data').hexdigest()"
        },
        {"code": "password = 'hardcoded123'\ndef login(): pass"},
        {"code": "def safe_function(x): return x * 2"},
    ]

    runner = ABTestRunner(
        llm_client,
        accuracy_scorer=(
            security_review_accuracy_scorer if agent_type == "reviewer" else None
        ),
    )

    # Repeat test cases to reach desired trial count
    repeated_cases = (test_cases * ((num_trials // len(test_cases)) + 1))[:num_trials]

    return await runner.run_balanced_test(agent_type, repeated_cases)


if __name__ == "__main__":
    # Demo mode - print estimated token savings without actual LLM calls
    print("Chain of Draft (CoD) A/B Testing Framework")
    print("=" * 60)

    # Show estimated token savings for each agent type
    agent_types = ["reviewer", "coder", "validator_insights", "query_planner"]

    for agent_type in agent_types:
        if agent_type == "coder":
            kwargs = {
                "vulnerability": "test",
                "context": "test",
                "code": "def foo(): pass",
            }
        elif agent_type == "validator_insights":
            kwargs = {"code": "def foo(): pass", "issues": "None"}
        elif agent_type == "query_planner":
            kwargs = {"query": "Find auth code", "budget": "100000"}
        else:
            kwargs = {"code": "def foo(): pass"}

        cod = build_cod_prompt(agent_type, mode=CoDPromptMode.COD, **kwargs)
        cot = build_cod_prompt(agent_type, mode=CoDPromptMode.COT, **kwargs)

        savings = estimate_token_savings(cod, cot)
        print(f"\n{agent_type}:")
        print(f"  CoD tokens: ~{savings['cod_tokens']}")
        print(f"  CoT tokens: ~{savings['cot_tokens']}")
        print(f"  Savings: {savings['savings_percent']}%")

    print("\n" + "=" * 60)
    print("To run actual A/B tests, use quick_ab_test() with a real LLM client")
