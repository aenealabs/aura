"""
Project Aura - Constraint Geometry Engine

Main orchestrator for deterministic semantic coherence measurement.
Coordinates constraint resolution, coherence computation, and action
determination across the 7-axis constraint space.

Pipeline:
1. Normalize and hash agent output (SHA-256)
2. Retrieve or compute output embedding (two-tier cache)
3. Resolve applicable constraints (Neptune graph / in-memory)
4. Compute per-axis coherence (cosine similarity vs frozen centroids)
5. Compute composite CCS (weighted geometric mean)
6. Determine action (deterministic threshold comparison)
7. Publish metrics and audit record

Same input + same constraints = same score, always.

Author: Project Aura Team
Created: 2026-02-11
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from .coherence_calculator import CoherenceCalculator
from .config import CGEConfig
from .constraint_graph import ConstraintGraphResolver
from .contracts import AgentOutput, CoherenceResult, ProvenanceContext
from .embedding_cache import EmbeddingCache
from .metrics import CGEMetricsPublisher
from .policy_profile import PolicyProfileManager
from .provenance_adapter import ProvenanceAdapter

logger = logging.getLogger(__name__)


class ConstraintGeometryEngine:
    """Deterministic semantic coherence measurement engine.

    Measures how well an agent output satisfies a multi-dimensional
    constraint space using graph-based constraint resolution and
    vector-based coherence computation.

    All computation after initial embedding is pure arithmetic -
    same input + same constraints = same score, always.

    Usage:
        engine = ConstraintGeometryEngine(
            graph_resolver=resolver,
            coherence_calculator=calculator,
            embedding_cache=cache,
            profile_manager=profiles,
        )

        result = await engine.assess_coherence(
            output=agent_output,
            policy_profile="default",
        )

        if result.is_auto_executable:
            deploy(result)
        elif result.needs_human:
            route_to_hitl(result)
    """

    def __init__(
        self,
        graph_resolver: ConstraintGraphResolver,
        coherence_calculator: CoherenceCalculator,
        embedding_cache: EmbeddingCache,
        profile_manager: PolicyProfileManager,
        provenance_adapter: Optional[ProvenanceAdapter] = None,
        metrics_publisher: Optional[CGEMetricsPublisher] = None,
        config: Optional[CGEConfig] = None,
    ):
        self.graph_resolver = graph_resolver
        self.calculator = coherence_calculator
        self.cache = embedding_cache
        self.profiles = profile_manager
        self.provenance = provenance_adapter or ProvenanceAdapter()
        self.metrics = metrics_publisher
        self.config = config or CGEConfig.for_testing()

    async def assess_coherence(
        self,
        output: AgentOutput,
        policy_profile: str = "default",
        provenance_context: Optional[ProvenanceContext] = None,
    ) -> CoherenceResult:
        """Assess constraint coherence of an agent output.

        This is the primary entry point for the CGE. It executes the
        full deterministic pipeline and returns a CoherenceResult with
        composite CCS, per-axis breakdown, and action determination.

        Args:
            output: The agent output to assess
            policy_profile: Name of the policy profile to apply
            provenance_context: Optional provenance trust context

        Returns:
            CoherenceResult with deterministic CCS and action

        Raises:
            KeyError: If policy profile not found
            RuntimeError: If embedding computation fails
        """
        start = time.monotonic()

        # Step 1: Normalize and hash
        normalized = self._normalize(output.text)
        output_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

        # Step 2: Get or compute output embedding
        output_embedding = await self.cache.get_or_compute(output_hash, normalized)

        # Step 3: Resolve applicable constraints
        profile = self.profiles.get(policy_profile)
        constraints = await self.graph_resolver.resolve(
            profile=profile,
            context=output.context,
        )

        # Step 4: Compute provenance adjustment
        provenance_adjustment = 0.0
        if provenance_context and self.config.enable_provenance_weighting:
            provenance_adjustment = self.provenance.compute_adjustment(
                provenance_context,
                sensitivity=profile.provenance_sensitivity,
            )

        # Step 5: Compute per-axis coherence scores
        axis_scores = self.calculator.compute_axis_scores(
            output_embedding=np.array(output_embedding, dtype=np.float64),
            constraints=constraints,
            axis_weights={
                axis: profile.get_axis_weight(axis) for axis in constraints.active_axes
            },
            provenance_adjustment=provenance_adjustment,
        )

        # Step 6: Compute composite CCS
        composite = self.calculator.compute_composite(axis_scores)

        # Step 7: Determine action
        action = profile.determine_action(composite, provenance_adjustment)

        elapsed_ms = (time.monotonic() - start) * 1000

        result = CoherenceResult(
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

        # Publish metrics (non-blocking)
        if self.metrics:
            try:
                self.metrics.record_assessment(result)
            except Exception:
                logger.warning("Failed to publish CGE metrics", exc_info=True)

        logger.debug(
            "CGE assessment: hash=%s, ccs=%.4f, action=%s, time=%.1fms",
            output_hash[:12],
            composite,
            action.value,
            elapsed_ms,
        )

        return result

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize text for deterministic hashing.

        Collapses all whitespace to single spaces and strips
        leading/trailing whitespace.
        """
        return " ".join(text.strip().split())


# =============================================================================
# Factory Functions
# =============================================================================


def create_engine(
    config: Optional[CGEConfig] = None,
    rules: Optional[list] = None,
) -> ConstraintGeometryEngine:
    """Create a CGE instance with default components.

    Args:
        config: Optional configuration (defaults to test config)
        rules: Optional constraint rules to pre-load

    Returns:
        Configured ConstraintGeometryEngine
    """
    config = config or CGEConfig.for_testing()

    resolver = ConstraintGraphResolver()
    if rules:
        resolver.load_rules(rules)

    calculator = CoherenceCalculator()
    cache = EmbeddingCache(config=config.cache)
    profiles = PolicyProfileManager()
    provenance = ProvenanceAdapter()

    metrics = None
    if config.metrics.enabled:
        metrics = CGEMetricsPublisher(
            config=config.metrics,
            environment=config.environment,
        )

    return ConstraintGeometryEngine(
        graph_resolver=resolver,
        coherence_calculator=calculator,
        embedding_cache=cache,
        profile_manager=profiles,
        provenance_adapter=provenance,
        metrics_publisher=metrics,
        config=config,
    )


# Singleton
_engine_instance: Optional[ConstraintGeometryEngine] = None


def get_cge_engine() -> ConstraintGeometryEngine:
    """Get singleton CGE engine."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = create_engine()
    return _engine_instance


def reset_cge_engine() -> None:
    """Reset singleton (for testing)."""
    global _engine_instance
    _engine_instance = None
