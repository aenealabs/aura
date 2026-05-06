"""Tests for CloudWatchMetricsPublisher (ADR-085 Phase 5)."""

from __future__ import annotations

import pytest

from src.services.verification_envelope.contracts import (
    ASTCanonicalForm,
    ConsensusOutcome,
    ConsensusResult,
    DVEOverallVerdict,
    DVEResult,
    MCDCCoverageReport,
    VerificationResult,
    VerificationVerdict,
)
from src.services.verification_envelope.pipeline import (
    METRIC_NAMESPACE,
    CloudWatchMetricsPublisher,
)


def _consensus() -> ConsensusResult:
    canonical = ASTCanonicalForm(
        source_hash="s",
        canonical_hash="c",
        canonical_dump="dump",
        variable_count=0,
        node_count=1,
    )
    return ConsensusResult(
        outcome=ConsensusOutcome.CONVERGED,
        n_generated=3,
        m_required=2,
        m_converged=3,
        selected_output="def f(): pass\n",
        selection_method="ast_centroid",
        canonical_forms=(canonical, canonical, canonical),
        pairwise_similarities=((1.0, 1.0, 1.0),) * 3,
        convergence_rate=1.0,
        audit_record_id="dve-test",
    )


def _result(
    *,
    verdict: DVEOverallVerdict = DVEOverallVerdict.ACCEPTED,
    dal_level: str = "DAL_A",
) -> DVEResult:
    return DVEResult(
        consensus=_consensus(),
        overall_verdict=verdict,
        pipeline_latency_ms=1234.5,
        dal_level=dal_level,
        audit_record_id="dve-test",
        structural_coverage=MCDCCoverageReport(
            statement_coverage_pct=100.0,
            decision_coverage_pct=100.0,
            mcdc_coverage_pct=100.0,
            dal_policy_satisfied=True,
            coverage_tool="fake",
        ),
        formal_verification=VerificationResult(
            verdict=VerificationVerdict.PROVED,
            axes_verified=(),
            proof_hash="ph",
            solver_version="z3:fake",
            verification_time_ms=2.0,
            smt_formula_hash="fh",
        ),
    )


def test_mock_mode_buffers_points_when_no_client() -> None:
    pub = CloudWatchMetricsPublisher(cloudwatch_client=None)
    pub.publish_pipeline_result(_result(), program_id="fadec-x")
    points = pub.buffered_points
    # 7 metrics emitted per call (latency, convergence, 3 coverage, formal verdict, overall verdict).
    assert len(points) == 7
    names = {p["MetricName"] for p in points}
    assert {
        "PipelineLatencyMs",
        "ConsensusConvergenceRate",
        "CoverageStatementPct",
        "CoverageDecisionPct",
        "CoverageMcdcPct",
        "FormalVerificationVerdict",
        "OverallVerdict",
    } == names


def test_program_id_dimension_added_when_supplied() -> None:
    pub = CloudWatchMetricsPublisher(cloudwatch_client=None)
    pub.publish_pipeline_result(_result(), program_id="fadec-x")
    for point in pub.buffered_points:
        names = {d["Name"] for d in point["Dimensions"]}
        assert "ProgramId" in names


def test_dal_dimension_added_when_supplied() -> None:
    pub = CloudWatchMetricsPublisher(cloudwatch_client=None)
    pub.publish_pipeline_result(_result(dal_level="DAL_A"))
    for point in pub.buffered_points:
        dims = {d["Name"]: d["Value"] for d in point["Dimensions"]}
        assert dims.get("DAL") == "DAL_A"


def test_verdict_metric_carries_verdict_dimension() -> None:
    pub = CloudWatchMetricsPublisher(cloudwatch_client=None)
    pub.publish_pipeline_result(_result(verdict=DVEOverallVerdict.REJECTED))
    [overall] = [
        p for p in pub.buffered_points if p["MetricName"] == "OverallVerdict"
    ]
    dims = {d["Name"]: d["Value"] for d in overall["Dimensions"]}
    assert dims.get("Verdict") == "rejected"


def test_publish_event_count_emits_one_metric() -> None:
    pub = CloudWatchMetricsPublisher(cloudwatch_client=None)
    pub.publish_event_count(
        name="AuditArchiveFailed",
        value=2,
        dimensions={"Sink": "DynamoDB"},
    )
    assert len(pub.buffered_points) == 1
    [point] = pub.buffered_points
    assert point["MetricName"] == "AuditArchiveFailed"
    assert point["Value"] == 2
    dims = {d["Name"]: d["Value"] for d in point["Dimensions"]}
    assert dims["Sink"] == "DynamoDB"
    assert "Environment" in dims


def test_live_path_calls_put_metric_data() -> None:
    """Live mode delegates to the supplied CloudWatch client."""

    class _FakeCloudWatchClient:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def put_metric_data(self, **kwargs):  # type: ignore[no-untyped-def]
            self.calls.append(kwargs)

    client = _FakeCloudWatchClient()
    pub = CloudWatchMetricsPublisher(cloudwatch_client=client)
    pub.publish_pipeline_result(_result())
    assert pub.is_live is True
    assert len(client.calls) == 1
    assert client.calls[0]["Namespace"] == METRIC_NAMESPACE
    assert len(client.calls[0]["MetricData"]) == 7


def test_live_path_falls_back_to_buffer_on_client_failure() -> None:
    class _BoomClient:
        def put_metric_data(self, **kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("CloudWatch quota exceeded")

    pub = CloudWatchMetricsPublisher(cloudwatch_client=_BoomClient())
    pub.publish_pipeline_result(_result())
    # The publisher must not raise; metrics fall through to the buffer.
    assert len(pub.buffered_points) == 7


def test_environment_dimension_default() -> None:
    pub = CloudWatchMetricsPublisher(cloudwatch_client=None)
    pub.publish_event_count(name="Foo")
    [point] = pub.buffered_points
    dims = {d["Name"]: d["Value"] for d in point["Dimensions"]}
    # Default environment is "dev" unless ENVIRONMENT is set.
    assert "Environment" in dims
