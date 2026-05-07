"""Project Aura - DVE CloudWatch metrics publisher (ADR-085 Phase 5).

Emits operational metrics for the four DVE pillars and the pipeline
verdict so a CloudWatch dashboard can graph cert-readiness over time.
Soft-imports boto3 so air-gapped builds load cleanly; in-memory mode
captures emissions for tests and dev demos.

Metric namespace: ``Aura/DVE``. Standard dimensions on every metric:
``Environment`` (dev/qa/prod) and ``DAL`` (DAL_A/DAL_B/DEFAULT/...).
Operators add the ``ProgramId`` dimension where they need to break
out per-program SLOs.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

from src.services.verification_envelope.contracts import (
    DVEOverallVerdict,
    DVEResult,
    VerificationVerdict,
)

logger = logging.getLogger(__name__)


try:
    import boto3  # type: ignore[import-not-found]

    BOTO3_AVAILABLE = True
except ImportError:  # pragma: no cover
    boto3 = None  # type: ignore[assignment]
    BOTO3_AVAILABLE = False


METRIC_NAMESPACE = "Aura/DVE"


@dataclass
class _MetricBuffer:
    """In-memory accumulator used in mock mode and tests."""

    points: list[dict[str, Any]] = field(default_factory=list)


class CloudWatchMetricsPublisher:
    """Publishes DVE metrics to CloudWatch (or buffers them in mock mode)."""

    def __init__(
        self,
        *,
        namespace: str = METRIC_NAMESPACE,
        environment: str | None = None,
        cloudwatch_client: Any | None = None,
    ) -> None:
        self._namespace = namespace
        self._environment = environment or os.environ.get("ENVIRONMENT", "dev")
        self._client = cloudwatch_client
        if self._client is None and BOTO3_AVAILABLE:
            try:
                self._client = boto3.client("cloudwatch")  # type: ignore[union-attr]
            except Exception as exc:  # pragma: no cover — credential failure
                logger.warning("CloudWatch client init failed: %s", exc)
                self._client = None
        self._buffer = _MetricBuffer()

    @property
    def is_live(self) -> bool:
        return self._client is not None

    @property
    def buffered_points(self) -> tuple[dict[str, Any], ...]:
        """Inspect mock-mode emissions for tests."""
        return tuple(self._buffer.points)

    # -------------------------------------------------------- publication

    def publish_pipeline_result(
        self,
        result: DVEResult,
        *,
        program_id: str | None = None,
    ) -> None:
        """Emit one metric per dimension of the pipeline run.

        Metrics emitted per call:
            * ``PipelineLatencyMs`` (Average + p99-friendly Maximum)
            * ``ConsensusConvergenceRate`` (proportion 0..1)
            * ``CoverageStatementPct``, ``CoverageDecisionPct``, ``CoverageMcdcPct``
            * ``FormalVerificationVerdict`` (count by verdict, dimension)
            * ``OverallVerdict`` (count by verdict, dimension)
        """
        base_dims = self._dimensions(dal_level=result.dal_level, program_id=program_id)
        ts = time.time()
        points: list[dict[str, Any]] = [
            self._point(
                name="PipelineLatencyMs",
                value=result.pipeline_latency_ms,
                unit="Milliseconds",
                dims=base_dims,
                ts=ts,
            ),
            self._point(
                name="ConsensusConvergenceRate",
                value=result.consensus.convergence_rate,
                unit="None",
                dims=base_dims,
                ts=ts,
            ),
            self._point(
                name="CoverageStatementPct",
                value=result.structural_coverage.statement_coverage_pct,
                unit="Percent",
                dims=base_dims,
                ts=ts,
            ),
            self._point(
                name="CoverageDecisionPct",
                value=result.structural_coverage.decision_coverage_pct,
                unit="Percent",
                dims=base_dims,
                ts=ts,
            ),
            self._point(
                name="CoverageMcdcPct",
                value=result.structural_coverage.mcdc_coverage_pct,
                unit="Percent",
                dims=base_dims,
                ts=ts,
            ),
            # Verdict counts get one dimension extra (the verdict itself)
            # so consumers can graph PROVED vs FAILED vs UNKNOWN cleanly.
            self._point(
                name="FormalVerificationVerdict",
                value=1,
                unit="Count",
                dims=(
                    *base_dims,
                    {
                        "Name": "Verdict",
                        "Value": result.formal_verification.verdict.value,
                    },
                ),
                ts=ts,
            ),
            self._point(
                name="OverallVerdict",
                value=1,
                unit="Count",
                dims=(
                    *base_dims,
                    {"Name": "Verdict", "Value": result.overall_verdict.value},
                ),
                ts=ts,
            ),
        ]

        if self.is_live:
            try:
                self._client.put_metric_data(  # type: ignore[union-attr]
                    Namespace=self._namespace,
                    MetricData=points,
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("CloudWatch put_metric_data failed: %s", exc)
                self._buffer.points.extend(points)
        else:
            self._buffer.points.extend(points)

    def publish_event_count(
        self,
        *,
        name: str,
        value: int = 1,
        dimensions: dict[str, str] | None = None,
    ) -> None:
        """One-off counter for arbitrary DVE events.

        Useful for tracking gate-level errors that aren't captured in
        :class:`DVEResult` (e.g. adapter selection fallback, audit
        archive write failures). The ``Environment`` dimension is
        always added; callers supply program-specific dimensions
        (``ProgramId``, ``Adapter`` …) as needed.
        """
        dims = list(self._dimensions(dal_level=None, program_id=None))
        if dimensions:
            dims.extend({"Name": k, "Value": v} for k, v in sorted(dimensions.items()))
        point = self._point(
            name=name,
            value=value,
            unit="Count",
            dims=tuple(dims),
            ts=time.time(),
        )
        if self.is_live:
            try:
                self._client.put_metric_data(  # type: ignore[union-attr]
                    Namespace=self._namespace, MetricData=[point]
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("CloudWatch put_metric_data failed: %s", exc)
                self._buffer.points.append(point)
        else:
            self._buffer.points.append(point)

    # ------------------------------------------------------------ helpers

    def _dimensions(
        self, *, dal_level: str | None, program_id: str | None
    ) -> tuple[dict[str, str], ...]:
        dims = [{"Name": "Environment", "Value": self._environment}]
        if dal_level is not None:
            dims.append({"Name": "DAL", "Value": dal_level})
        if program_id is not None:
            dims.append({"Name": "ProgramId", "Value": program_id})
        return tuple(dims)

    @staticmethod
    def _point(
        *,
        name: str,
        value: float,
        unit: str,
        dims: tuple[dict[str, str], ...],
        ts: float,
    ) -> dict[str, Any]:
        from datetime import datetime, timezone

        return {
            "MetricName": name,
            "Value": value,
            "Unit": unit,
            "Dimensions": list(dims),
            "Timestamp": datetime.fromtimestamp(ts, tz=timezone.utc),
        }
