"""Tests for ``runtime_security.metrics.RuntimeSecurityMetricsPublisher``.

Covers the wave-3 (#163) work that replaced the stub ``_publish_batch``
with a real boto3 CloudWatch emitter. The mock-mode buffer behaviour
must still work for tests that opt out of boto3.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.services.runtime_security.metrics import (
    MetricDatum,
    RuntimeSecurityMetricsPublisher,
    _datum_to_cloudwatch_payload,
)


class _FakeCloudWatchClient:
    """In-memory stand-in for the boto3 CloudWatch client.

    Records every ``put_metric_data`` call so tests can assert the
    namespace, metric count, dimensions, and payload shape without
    touching botocore.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def put_metric_data(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}


def test_publisher_mock_mode_when_no_client() -> None:
    pub = RuntimeSecurityMetricsPublisher()

    assert pub._mock_mode is True
    pub.record_admission_decision("ALLOW", "cluster-a", "default", "Pod")
    assert len(pub._buffer) == 1

    pub.flush()
    # mock mode drops the buffer on flush without sending
    assert len(pub._buffer) == 0


def test_publisher_emit_mode_when_client_injected() -> None:
    client = _FakeCloudWatchClient()
    pub = RuntimeSecurityMetricsPublisher(cloudwatch_client=client)

    assert pub._mock_mode is False
    pub.record_admission_decision("DENY", "cluster-a", "default", "Pod")
    pub.record_admission_latency(42.5, "cluster-a")
    pub.flush()

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["Namespace"] == pub.namespace
    assert len(call["MetricData"]) == 2

    names = {m["MetricName"] for m in call["MetricData"]}
    assert names == {"AdmissionDecision", "AdmissionLatency"}


def test_publisher_splits_oversized_batches() -> None:
    client = _FakeCloudWatchClient()
    pub = RuntimeSecurityMetricsPublisher(cloudwatch_client=client)

    # 600 metrics > _CLOUDWATCH_BATCH_LIMIT (500) -> 2 batches
    for i in range(600):
        pub._buffer.append(MetricDatum(name="X", value=float(i)))
    pub.flush()

    assert len(client.calls) == 2
    assert sum(len(c["MetricData"]) for c in client.calls) == 600


def test_publisher_swallows_batch_errors() -> None:
    class BoomClient:
        def __init__(self) -> None:
            self.attempts = 0

        def put_metric_data(self, **kwargs: Any) -> None:
            self.attempts += 1
            raise RuntimeError("CloudWatch throttled")

    boom = BoomClient()
    pub = RuntimeSecurityMetricsPublisher(cloudwatch_client=boom)

    pub.record_admission_decision("ALLOW", "c", "n", "Pod")
    pub.flush()  # must NOT raise even though boto3 did

    assert boom.attempts == 1


def test_datum_to_payload_with_dimensions() -> None:
    datum = MetricDatum(
        name="Foo",
        value=1.5,
        unit="Count",
        dimensions={"Cluster": "c", "Decision": "ALLOW"},
    )

    payload = _datum_to_cloudwatch_payload(datum)

    assert payload["MetricName"] == "Foo"
    assert payload["Value"] == 1.5
    assert payload["Unit"] == "Count"
    # Dimensions are sorted-list of {Name, Value} maps
    dims = {d["Name"]: d["Value"] for d in payload["Dimensions"]}
    assert dims == {"Cluster": "c", "Decision": "ALLOW"}


def test_datum_to_payload_without_dimensions_omits_field() -> None:
    datum = MetricDatum(name="Foo", value=2.0)

    payload = _datum_to_cloudwatch_payload(datum)

    assert "Dimensions" not in payload


def test_publisher_defensive_no_client_when_mock_mode_off() -> None:
    """When _mock_mode is manually flipped without a client, drop cleanly."""
    pub = RuntimeSecurityMetricsPublisher()  # starts in mock mode
    pub._mock_mode = False  # simulate a misconfigured wiring
    pub._cloudwatch = None

    pub.record_admission_decision("ALLOW", "c", "n", "Pod")
    # Should not raise; should not lose track of the failure path.
    pub.flush()


def test_namespace_uses_config_value() -> None:
    pub = RuntimeSecurityMetricsPublisher()
    assert pub.namespace.startswith("Aura/")
