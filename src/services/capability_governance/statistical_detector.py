"""
Project Aura - Statistical Anomaly Detector

Phase 1 anomaly detection using statistical methods: Z-scores, n-gram analysis,
and temporal pattern detection. Uses CloudWatch Anomaly Detection as backing store.

Implements ADR-072 for ML-based anomaly detection.

Detection Types:
- Volume Anomaly: Z-score based detection of unusual invocation counts
- Sequence Anomaly: N-gram analysis for unusual tool invocation patterns
- Temporal Anomaly: Activity outside normal operational hours
"""

import logging
import math
from datetime import datetime, timedelta
from typing import Protocol

from .anomaly_contracts import (
    AnomalyDetectionConfig,
    AnomalyResult,
    AnomalyType,
    StatisticalBaseline,
)

logger = logging.getLogger(__name__)


class BaselineService(Protocol):
    """Protocol for baseline data retrieval service."""

    async def get_baseline(
        self,
        agent_type: str,
        tool_classification: str | None = None,
    ) -> StatisticalBaseline:
        """Retrieve baseline for an agent type and optional tool classification."""
        ...

    async def update_baseline(
        self,
        agent_type: str,
        baseline: StatisticalBaseline,
    ) -> None:
        """Update baseline for an agent type."""
        ...


class InMemoryBaselineService:
    """In-memory baseline service for testing and local development."""

    def __init__(self):
        self._baselines: dict[str, StatisticalBaseline] = {}
        self._initialize_default_baselines()

    def _initialize_default_baselines(self):
        """Initialize default baselines for common agent types."""
        default_baselines = [
            StatisticalBaseline(
                agent_type="coder",
                tool_classification=None,
                mean_hourly_count=15.0,
                std_hourly_count=5.0,
                mean_daily_count=120.0,
                std_daily_count=30.0,
                typical_sequences=[
                    ("read_file", "analyze_code", "write_file"),
                    ("search_code", "read_file", "modify_code"),
                    ("run_tests", "read_output", "fix_code"),
                ],
                active_hours=list(range(6, 22)),  # 6am - 10pm
            ),
            StatisticalBaseline(
                agent_type="reviewer",
                tool_classification=None,
                mean_hourly_count=8.0,
                std_hourly_count=3.0,
                mean_daily_count=60.0,
                std_daily_count=20.0,
                typical_sequences=[
                    ("read_file", "analyze_code", "submit_review"),
                    ("fetch_diff", "review_changes", "approve"),
                    ("check_tests", "analyze_coverage", "comment"),
                ],
                active_hours=list(range(8, 20)),  # 8am - 8pm
            ),
            StatisticalBaseline(
                agent_type="validator",
                tool_classification=None,
                mean_hourly_count=5.0,
                std_hourly_count=2.0,
                mean_daily_count=40.0,
                std_daily_count=15.0,
                typical_sequences=[
                    ("run_tests", "check_coverage", "report"),
                    ("validate_config", "check_deps", "approve"),
                    ("lint_code", "check_style", "report"),
                ],
                active_hours=list(range(0, 24)),  # 24/7 for CI/CD
            ),
            StatisticalBaseline(
                agent_type="orchestrator",
                tool_classification=None,
                mean_hourly_count=20.0,
                std_hourly_count=8.0,
                mean_daily_count=200.0,
                std_daily_count=50.0,
                typical_sequences=[
                    ("dispatch_task", "monitor_agent", "collect_result"),
                    ("plan_workflow", "execute_step", "checkpoint"),
                    ("schedule_task", "delegate_agent", "sync"),
                ],
                active_hours=list(range(0, 24)),  # 24/7
            ),
        ]

        for baseline in default_baselines:
            key = self._make_key(baseline.agent_type, baseline.tool_classification)
            self._baselines[key] = baseline

    def _make_key(self, agent_type: str, tool_classification: str | None = None) -> str:
        """Create lookup key for baselines."""
        if tool_classification:
            return f"{agent_type}:{tool_classification}"
        return agent_type

    async def get_baseline(
        self,
        agent_type: str,
        tool_classification: str | None = None,
    ) -> StatisticalBaseline:
        """Retrieve baseline for an agent type."""
        key = self._make_key(agent_type, tool_classification)
        if key in self._baselines:
            return self._baselines[key]

        # Fallback to agent type only
        if tool_classification:
            agent_only_key = self._make_key(agent_type, None)
            if agent_only_key in self._baselines:
                return self._baselines[agent_only_key]

        # Return a default baseline for unknown agent types
        return StatisticalBaseline(
            agent_type=agent_type,
            tool_classification=tool_classification,
            mean_hourly_count=10.0,
            std_hourly_count=5.0,
            mean_daily_count=80.0,
            std_daily_count=30.0,
            typical_sequences=[],
            active_hours=list(range(8, 20)),
        )

    async def update_baseline(
        self,
        agent_type: str,
        baseline: StatisticalBaseline,
    ) -> None:
        """Update baseline for an agent type."""
        key = self._make_key(agent_type, baseline.tool_classification)
        self._baselines[key] = baseline


class StatisticalAnomalyDetector:
    """
    Phase 1: Statistical anomaly detection using Z-scores and pattern analysis.

    This detector provides the first layer of anomaly detection using
    computationally efficient statistical methods. It serves as a baseline
    before more complex ML models are deployed (Phase 2).

    Detection methods:
    - Volume: Z-score based detection of unusual invocation counts
    - Sequence: N-gram analysis for unusual tool invocation patterns
    - Temporal: Activity outside normal operational hours
    """

    def __init__(
        self,
        baseline_service: BaselineService | None = None,
        config: AnomalyDetectionConfig | None = None,
    ):
        self.baselines = baseline_service or InMemoryBaselineService()
        self.config = config or AnomalyDetectionConfig()

    async def detect_volume_anomaly(
        self,
        agent_id: str,
        agent_type: str,
        tool_classification: str | None,
        current_count: int,
        window_hours: int = 1,
    ) -> AnomalyResult:
        """
        Detect unusual invocation volume using Z-score.

        Z > 3.0 = Anomaly (99.7% confidence)
        Z > 2.5 = Suspicious

        Args:
            agent_id: Unique identifier for the agent
            agent_type: Type of agent (e.g., coder, reviewer)
            tool_classification: Tool classification (SAFE, MONITORING, etc.)
            current_count: Number of invocations in the current window
            window_hours: Size of the counting window in hours

        Returns:
            AnomalyResult with is_anomaly, score, and details
        """
        baseline = await self.baselines.get_baseline(
            agent_type=agent_type,
            tool_classification=tool_classification,
        )

        # Scale baseline by window size
        expected_mean = baseline.mean_hourly_count * window_hours
        expected_std = baseline.std_hourly_count * math.sqrt(window_hours)

        # Avoid division by zero
        if expected_std == 0:
            expected_std = 1.0

        z_score = (current_count - expected_mean) / expected_std

        # Normalize score to 0-1 range
        normalized_score = min(1.0, max(0.0, z_score / 5.0))

        is_anomaly = z_score > self.config.volume_z_score_threshold

        logger.debug(
            f"Volume anomaly check: agent={agent_id}, count={current_count}, "
            f"z_score={z_score:.2f}, is_anomaly={is_anomaly}"
        )

        return AnomalyResult(
            is_anomaly=is_anomaly,
            score=normalized_score,
            anomaly_type=AnomalyType.VOLUME,
            details={
                "z_score": round(z_score, 3),
                "current_count": current_count,
                "expected_mean": round(expected_mean, 2),
                "expected_std": round(expected_std, 2),
                "threshold": self.config.volume_z_score_threshold,
                "window_hours": window_hours,
                "agent_type": agent_type,
                "tool_classification": tool_classification,
            },
        )

    async def detect_sequence_anomaly(
        self,
        agent_id: str,
        agent_type: str,
        recent_tools: list[str],
        ngram_size: int = 3,
    ) -> AnomalyResult:
        """
        Detect unusual tool invocation sequences using n-gram analysis.

        Compares observed tool sequences against learned typical sequences
        for the agent type. High ratio of unseen n-grams indicates anomaly.

        Args:
            agent_id: Unique identifier for the agent
            agent_type: Type of agent
            recent_tools: List of recently invoked tool names
            ngram_size: Size of n-grams to analyze (default: 3)

        Returns:
            AnomalyResult with unseen ratio as score
        """
        baseline = await self.baselines.get_baseline(agent_type=agent_type)

        # Need at least ngram_size tools to analyze
        if len(recent_tools) < ngram_size:
            return AnomalyResult(
                is_anomaly=False,
                score=0.0,
                anomaly_type=AnomalyType.SEQUENCE,
                details={
                    "reason": "insufficient_data",
                    "tools_count": len(recent_tools),
                    "min_required": ngram_size,
                },
            )

        # Extract n-grams from recent tools
        ngrams = [
            tuple(recent_tools[i : i + ngram_size])
            for i in range(len(recent_tools) - ngram_size + 1)
        ]

        # Convert baseline sequences to set for O(1) lookup
        typical_set = set(baseline.typical_sequences)

        # Count unseen n-grams
        unseen_ngrams = [ng for ng in ngrams if ng not in typical_set]
        unseen_count = len(unseen_ngrams)
        total_ngrams = len(ngrams)

        unseen_ratio = unseen_count / max(total_ngrams, 1)
        is_anomaly = unseen_ratio > self.config.sequence_unseen_ratio_threshold

        logger.debug(
            f"Sequence anomaly check: agent={agent_id}, unseen_ratio={unseen_ratio:.2f}, "
            f"is_anomaly={is_anomaly}"
        )

        return AnomalyResult(
            is_anomaly=is_anomaly,
            score=unseen_ratio,
            anomaly_type=AnomalyType.SEQUENCE,
            details={
                "unseen_ngrams": unseen_count,
                "total_ngrams": total_ngrams,
                "unseen_ratio": round(unseen_ratio, 3),
                "threshold": self.config.sequence_unseen_ratio_threshold,
                "unseen_examples": [list(ng) for ng in unseen_ngrams[:3]],
                "agent_type": agent_type,
            },
        )

    async def detect_temporal_anomaly(
        self,
        agent_id: str,
        agent_type: str,
        current_hour: int | None = None,
        current_time: datetime | None = None,
    ) -> AnomalyResult:
        """
        Detect activity outside normal operational hours.

        Args:
            agent_id: Unique identifier for the agent
            agent_type: Type of agent
            current_hour: Hour of day (0-23). If None, uses current time.
            current_time: Datetime to check. If None, uses current time.

        Returns:
            AnomalyResult with binary score (0 or 1)
        """
        baseline = await self.baselines.get_baseline(agent_type=agent_type)

        if current_hour is None:
            if current_time is None:
                current_time = datetime.utcnow()
            current_hour = current_time.hour

        is_unusual_hour = current_hour not in baseline.active_hours

        logger.debug(
            f"Temporal anomaly check: agent={agent_id}, hour={current_hour}, "
            f"typical_hours={baseline.active_hours}, is_unusual={is_unusual_hour}"
        )

        return AnomalyResult(
            is_anomaly=is_unusual_hour,
            score=1.0 if is_unusual_hour else 0.0,
            anomaly_type=AnomalyType.TEMPORAL,
            details={
                "current_hour": current_hour,
                "typical_hours": baseline.active_hours,
                "is_unusual": is_unusual_hour,
                "agent_type": agent_type,
            },
        )

    async def detect_cross_agent_anomaly(
        self,
        agent_ids: list[str],
        shared_resource: str,
        access_times: list[datetime],
        correlation_window_seconds: int = 60,
    ) -> AnomalyResult:
        """
        Detect coordinated suspicious behavior across multiple agents.

        Identifies when multiple agents access the same resource within
        a short time window, which may indicate coordinated attacks.

        Args:
            agent_ids: List of agent IDs that accessed the resource
            shared_resource: Name of the shared resource
            access_times: Timestamps of each access
            correlation_window_seconds: Time window for correlation

        Returns:
            AnomalyResult based on access clustering
        """
        if len(agent_ids) < 2 or len(access_times) < 2:
            return AnomalyResult(
                is_anomaly=False,
                score=0.0,
                anomaly_type=AnomalyType.CROSS_AGENT,
                details={"reason": "insufficient_agents"},
            )

        # Sort access times
        sorted_times = sorted(access_times)

        # Count accesses within correlation window using sliding window
        clustered_count = 0
        window = timedelta(seconds=correlation_window_seconds)
        right = 0

        for left in range(len(sorted_times)):
            while (
                right < len(sorted_times)
                and sorted_times[right] - sorted_times[left] <= window
            ):
                right += 1
            # Number of pairs with sorted_times[left] as the earlier element
            # that fall within the window: (right - left - 1)
            clustered_count += right - left - 1

        # Calculate clustering score
        max_possible_clusters = len(access_times) * (len(access_times) - 1) // 2
        cluster_ratio = clustered_count / max(max_possible_clusters, 1)

        # Suspicious if high clustering with multiple agents
        unique_agents = len(set(agent_ids))
        is_anomaly = cluster_ratio > 0.7 and unique_agents >= 3

        return AnomalyResult(
            is_anomaly=is_anomaly,
            score=cluster_ratio,
            anomaly_type=AnomalyType.CROSS_AGENT,
            details={
                "unique_agents": unique_agents,
                "total_accesses": len(access_times),
                "clustered_accesses": clustered_count,
                "cluster_ratio": round(cluster_ratio, 3),
                "shared_resource": shared_resource,
                "correlation_window_seconds": correlation_window_seconds,
            },
        )

    async def fuse_anomaly_scores(
        self,
        anomaly_results: list[AnomalyResult],
        weights: dict[AnomalyType, float] | None = None,
    ) -> AnomalyResult:
        """
        Combine multiple anomaly scores into a single fused result.

        Uses weighted average of individual scores with configurable weights.

        Args:
            anomaly_results: List of individual anomaly results
            weights: Optional weights per anomaly type (default: equal weights)

        Returns:
            Fused AnomalyResult with combined score
        """
        if not anomaly_results:
            return AnomalyResult(
                is_anomaly=False,
                score=0.0,
                anomaly_type=AnomalyType.ML_ENSEMBLE,
                details={"reason": "no_results_to_fuse"},
            )

        # Default weights
        if weights is None:
            weights = {
                AnomalyType.VOLUME: 1.0,
                AnomalyType.SEQUENCE: 1.0,
                AnomalyType.TEMPORAL: 0.5,  # Lower weight for temporal
                AnomalyType.CROSS_AGENT: 1.5,  # Higher weight for cross-agent
                AnomalyType.HONEYPOT: 10.0,  # Honeypot overrides everything
                AnomalyType.CONTEXT: 1.0,
            }

        total_weight = 0.0
        weighted_sum = 0.0
        component_scores = {}

        for result in anomaly_results:
            weight = weights.get(result.anomaly_type, 1.0)
            weighted_sum += result.score * weight
            total_weight += weight
            component_scores[result.anomaly_type.value] = result.score

        fused_score = weighted_sum / total_weight if total_weight > 0 else 0.0

        # Any honeypot trigger makes it definitely anomalous
        has_honeypot = any(
            r.anomaly_type == AnomalyType.HONEYPOT and r.is_anomaly
            for r in anomaly_results
        )

        is_anomaly = has_honeypot or fused_score > self.config.alert_threshold

        return AnomalyResult(
            is_anomaly=is_anomaly,
            score=min(1.0, fused_score),
            anomaly_type=AnomalyType.ML_ENSEMBLE,
            details={
                "component_scores": component_scores,
                "weights_used": {k.value: v for k, v in weights.items()},
                "has_honeypot_trigger": has_honeypot,
                "components_analyzed": len(anomaly_results),
            },
        )


# Singleton instance
_detector_instance: StatisticalAnomalyDetector | None = None


def get_statistical_detector() -> StatisticalAnomalyDetector:
    """Get or create the singleton statistical detector instance."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = StatisticalAnomalyDetector()
    return _detector_instance


def reset_statistical_detector() -> None:
    """Reset the singleton instance (for testing)."""
    global _detector_instance
    _detector_instance = None
