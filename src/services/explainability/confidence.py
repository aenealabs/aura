"""
Project Aura - Confidence Quantifier

Quantifies confidence with intervals and uncertainty bounds
rather than just point estimates.

Author: Project Aura Team
Created: 2026-01-25
"""

from __future__ import annotations

import logging
import math
import statistics
from typing import Any, Optional

from .config import ConfidenceConfig
from .contracts import AlternativesReport, ConfidenceInterval, ReasoningChain

logger = logging.getLogger(__name__)


class ConfidenceQuantifier:
    """
    Quantify confidence with intervals and uncertainty bounds.

    Uses multiple methods including ensemble disagreement,
    Monte Carlo dropout simulation, and calibration scaling
    to produce well-calibrated confidence intervals.
    """

    def __init__(self, config: Optional[ConfidenceConfig] = None):
        """
        Initialize the confidence quantifier.

        Args:
            config: Configuration for confidence quantification
        """
        self.config = config or ConfidenceConfig()
        logger.info("ConfidenceQuantifier initialized")

    async def quantify(
        self,
        reasoning_chain: ReasoningChain,
        alternatives_report: AlternativesReport,
        decision_context: Optional[dict[str, Any]] = None,
    ) -> ConfidenceInterval:
        """
        Quantify confidence for a decision.

        Args:
            reasoning_chain: The reasoning chain for the decision
            alternatives_report: Alternatives analysis
            decision_context: Additional context

        Returns:
            ConfidenceInterval with bounds and uncertainty sources
        """
        logger.debug(
            f"Quantifying confidence for decision {reasoning_chain.decision_id}"
        )

        # Collect confidence signals
        signals = self._collect_confidence_signals(
            reasoning_chain, alternatives_report, decision_context
        )

        # Calculate point estimate
        point_estimate = self._calculate_point_estimate(signals)

        # Calculate interval bounds based on calibration method
        lower_bound, upper_bound = self._calculate_bounds(
            point_estimate, signals, self.config.default_calibration_method
        )

        # Identify uncertainty sources
        uncertainty_sources = self._identify_uncertainty_sources(
            reasoning_chain, alternatives_report, signals
        )

        interval = ConfidenceInterval(
            point_estimate=round(point_estimate, 4),
            lower_bound=round(lower_bound, 4),
            upper_bound=round(upper_bound, 4),
            uncertainty_sources=uncertainty_sources[
                : self.config.max_uncertainty_sources
            ],
            calibration_method=self.config.default_calibration_method,
            sample_size=len(signals),
        )

        logger.debug(
            f"Confidence: {interval.point_estimate:.2f} "
            f"[{interval.lower_bound:.2f}, {interval.upper_bound:.2f}]"
        )
        return interval

    def quantify_sync(
        self,
        reasoning_chain: ReasoningChain,
        alternatives_report: AlternativesReport,
        decision_context: Optional[dict[str, Any]] = None,
    ) -> ConfidenceInterval:
        """
        Synchronous version of quantify.

        Args:
            reasoning_chain: The reasoning chain for the decision
            alternatives_report: Alternatives analysis
            decision_context: Additional context

        Returns:
            ConfidenceInterval with bounds and uncertainty sources
        """
        signals = self._collect_confidence_signals(
            reasoning_chain, alternatives_report, decision_context
        )

        point_estimate = self._calculate_point_estimate(signals)
        lower_bound, upper_bound = self._calculate_bounds(
            point_estimate, signals, self.config.default_calibration_method
        )
        uncertainty_sources = self._identify_uncertainty_sources(
            reasoning_chain, alternatives_report, signals
        )

        return ConfidenceInterval(
            point_estimate=round(point_estimate, 4),
            lower_bound=round(lower_bound, 4),
            upper_bound=round(upper_bound, 4),
            uncertainty_sources=uncertainty_sources[
                : self.config.max_uncertainty_sources
            ],
            calibration_method=self.config.default_calibration_method,
            sample_size=len(signals),
        )

    def _collect_confidence_signals(
        self,
        reasoning_chain: ReasoningChain,
        alternatives_report: AlternativesReport,
        decision_context: Optional[dict[str, Any]],
    ) -> list[float]:
        """Collect confidence signals from various sources."""
        signals = []

        # Reasoning chain confidence
        if reasoning_chain.steps:
            signals.extend([step.confidence for step in reasoning_chain.steps])
            signals.append(reasoning_chain.total_confidence)

        # Alternatives confidence
        if alternatives_report.alternatives:
            chosen = alternatives_report.get_chosen()
            if chosen:
                signals.append(chosen.confidence)

            # Gap between chosen and next best
            sorted_alts = sorted(
                alternatives_report.alternatives,
                key=lambda x: x.confidence,
                reverse=True,
            )
            if len(sorted_alts) >= 2:
                confidence_gap = sorted_alts[0].confidence - sorted_alts[1].confidence
                # Larger gap = higher confidence in choice
                signals.append(min(1.0, 0.5 + confidence_gap))

        # Context-based confidence
        if decision_context:
            if decision_context.get("prior_decisions"):
                # More context = higher confidence
                signals.append(0.8)
            if decision_context.get("verified"):
                signals.append(0.95)

        # Ensure we have at least one signal
        if not signals:
            signals = [0.5]

        return signals

    def _calculate_point_estimate(self, signals: list[float]) -> float:
        """Calculate point estimate from signals."""
        if not signals:
            return 0.5

        # Weighted average favoring lower confidences (conservative)
        weights = [1.0 / (s + 0.1) for s in signals]
        weighted_sum = sum(s * w for s, w in zip(signals, weights))
        total_weight = sum(weights)

        return min(1.0, max(0.0, weighted_sum / total_weight))

    def _calculate_bounds(
        self,
        point_estimate: float,
        signals: list[float],
        method: str,
    ) -> tuple[float, float]:
        """Calculate confidence interval bounds."""
        if method == "ensemble_disagreement":
            return self._ensemble_disagreement_bounds(point_estimate, signals)
        elif method == "monte_carlo_dropout":
            return self._monte_carlo_bounds(point_estimate, signals)
        elif method == "temperature_scaling":
            return self._temperature_scaling_bounds(point_estimate, signals)
        else:
            return self._default_bounds(point_estimate, signals)

    def _ensemble_disagreement_bounds(
        self,
        point_estimate: float,
        signals: list[float],
    ) -> tuple[float, float]:
        """Calculate bounds based on ensemble disagreement."""
        if len(signals) < 2:
            # Default to +/- 10% of point estimate
            margin = max(0.1, 0.1 * point_estimate)
            return max(0.0, point_estimate - margin), min(1.0, point_estimate + margin)

        # Use standard deviation of signals
        try:
            std_dev = statistics.stdev(signals)
        except statistics.StatisticsError:
            std_dev = 0.1

        # 95% confidence interval approximation
        z_score = 1.96
        margin = z_score * std_dev / math.sqrt(len(signals))

        lower = max(0.0, point_estimate - margin)
        upper = min(1.0, point_estimate + margin)

        return lower, upper

    def _monte_carlo_bounds(
        self,
        point_estimate: float,
        signals: list[float],
    ) -> tuple[float, float]:
        """Calculate bounds using Monte Carlo simulation."""
        if len(signals) < self.config.min_samples_for_mc:
            return self._ensemble_disagreement_bounds(point_estimate, signals)

        # Simulate dropout by perturbing signals
        import random

        simulations = []
        for _ in range(100):
            # Randomly drop 20% of signals
            sample = random.sample(signals, max(1, int(len(signals) * 0.8)))
            sim_estimate = sum(sample) / len(sample)
            simulations.append(sim_estimate)

        # Use percentiles for bounds
        simulations.sort()
        lower_idx = int(len(simulations) * 0.025)
        upper_idx = int(len(simulations) * 0.975)

        return simulations[lower_idx], simulations[upper_idx]

    def _temperature_scaling_bounds(
        self,
        point_estimate: float,
        signals: list[float],
    ) -> tuple[float, float]:
        """Calculate bounds using temperature scaling."""
        # Temperature scaling adjusts confidence based on calibration
        temperature = 1.5  # Higher temperature = wider intervals

        # Apply temperature scaling
        if point_estimate > 0.5:
            scaled = math.exp(math.log(point_estimate + 0.01) / temperature)
        else:
            scaled = 1 - math.exp(math.log(1 - point_estimate + 0.01) / temperature)

        # Create asymmetric interval
        upper_margin = (1 - scaled) * 0.5
        lower_margin = scaled * 0.5

        lower = max(0.0, point_estimate - lower_margin)
        upper = min(1.0, point_estimate + upper_margin)

        return lower, upper

    def _default_bounds(
        self,
        point_estimate: float,
        signals: list[float],
    ) -> tuple[float, float]:
        """Calculate default bounds."""
        # Simple +/- 15% margin
        margin = 0.15
        return max(0.0, point_estimate - margin), min(1.0, point_estimate + margin)

    def _identify_uncertainty_sources(
        self,
        reasoning_chain: ReasoningChain,
        alternatives_report: AlternativesReport,
        signals: list[float],
    ) -> list[str]:
        """Identify sources of uncertainty."""
        sources = []

        # Low confidence steps
        if reasoning_chain.steps:
            low_conf_steps = [s for s in reasoning_chain.steps if s.confidence < 0.7]
            if low_conf_steps:
                sources.append(
                    f"Low confidence in {len(low_conf_steps)} reasoning steps"
                )

        # Missing evidence
        steps_without_evidence = [s for s in reasoning_chain.steps if not s.evidence]
        if steps_without_evidence:
            sources.append(
                f"{len(steps_without_evidence)} steps lack supporting evidence"
            )

        # Close alternatives
        if alternatives_report.alternatives:
            top_alts = sorted(
                alternatives_report.alternatives,
                key=lambda x: x.confidence,
                reverse=True,
            )
            if len(top_alts) >= 2:
                gap = top_alts[0].confidence - top_alts[1].confidence
                if gap < 0.1:
                    sources.append("Close competition between top alternatives")

        # Signal variance
        if len(signals) >= 3:
            try:
                variance = statistics.variance(signals)
                if variance > 0.1:
                    sources.append("High variance in confidence signals")
            except statistics.StatisticsError:
                pass

        # Limited information
        if len(reasoning_chain.steps) < 3:
            sources.append("Limited reasoning depth")

        if not sources:
            sources.append("Standard uncertainty in decision-making")

        return sources


# Global instance management
_confidence_quantifier: Optional[ConfidenceQuantifier] = None


def get_confidence_quantifier() -> ConfidenceQuantifier:
    """Get the global confidence quantifier instance."""
    global _confidence_quantifier
    if _confidence_quantifier is None:
        _confidence_quantifier = ConfidenceQuantifier()
    return _confidence_quantifier


def configure_confidence_quantifier(
    config: Optional[ConfidenceConfig] = None,
) -> ConfidenceQuantifier:
    """Configure and return the global confidence quantifier."""
    global _confidence_quantifier
    _confidence_quantifier = ConfidenceQuantifier(config=config)
    return _confidence_quantifier


def reset_confidence_quantifier() -> None:
    """Reset the global confidence quantifier instance."""
    global _confidence_quantifier
    _confidence_quantifier = None
