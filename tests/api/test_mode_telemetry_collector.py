"""Tests for the ADR-087 ModeTelemetryCollector (Wave 4, #163).

The collector replaces the hardcoded zero values in the orchestrator
mode-status endpoint. Each test verifies a clear contract:

  - When the underlying client is unavailable, return a safe fallback
    (desired for warm-pool readiness, 0 for queues/jobs) -- never raise.
  - When the client raises mid-call, swallow + log + return the
    fallback. Settings page must not 500.
  - When the client returns real data, surface it.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from src.api.orchestrator_settings_endpoints import (
    ModeTelemetryCollector,
    _get_mode_telemetry_collector,
    _reset_mode_telemetry_collector,
)

# ---------------------------------------------------------------------------
# Warm pool replicas ready
# ---------------------------------------------------------------------------


def test_warm_pool_returns_zero_when_desired_zero() -> None:
    c = ModeTelemetryCollector()
    assert c.warm_pool_replicas_ready(0, "deploy-x") == 0


def test_warm_pool_falls_back_to_desired_when_k8s_unavailable() -> None:
    c = ModeTelemetryCollector()
    # _k8s_apps_v1 is the sentinel after a failed attempt
    c._k8s_apps_v1 = False
    assert c.warm_pool_replicas_ready(3, "deploy-x") == 3


def test_warm_pool_uses_live_ready_replicas_when_k8s_returns_them() -> None:
    c = ModeTelemetryCollector()
    fake_status = MagicMock()
    fake_status.status.ready_replicas = 5
    fake_api = MagicMock()
    fake_api.read_namespaced_deployment_status.return_value = fake_status
    c._k8s_apps_v1 = fake_api

    assert c.warm_pool_replicas_ready(3, "deploy-x") == 5
    fake_api.read_namespaced_deployment_status.assert_called_once_with(
        name="deploy-x", namespace="aura-system"
    )


def test_warm_pool_falls_back_when_ready_replicas_missing() -> None:
    c = ModeTelemetryCollector()
    fake_status = MagicMock()
    fake_status.status.ready_replicas = None
    fake_api = MagicMock()
    fake_api.read_namespaced_deployment_status.return_value = fake_status
    c._k8s_apps_v1 = fake_api

    assert c.warm_pool_replicas_ready(3, "deploy-x") == 3


def test_warm_pool_swallows_k8s_exception_and_returns_desired() -> None:
    c = ModeTelemetryCollector()
    fake_api = MagicMock()
    fake_api.read_namespaced_deployment_status.side_effect = RuntimeError("k8s 5xx")
    c._k8s_apps_v1 = fake_api

    assert c.warm_pool_replicas_ready(3, "deploy-x") == 3


# ---------------------------------------------------------------------------
# Queue depth (SQS)
# ---------------------------------------------------------------------------


def test_queue_depth_returns_zero_for_no_url() -> None:
    c = ModeTelemetryCollector()
    assert c.queue_depth(None) == 0
    assert c.queue_depth("") == 0


def test_queue_depth_returns_zero_when_sqs_unavailable() -> None:
    c = ModeTelemetryCollector()
    c._sqs_client = False
    assert c.queue_depth("https://sqs.example/queue") == 0


def test_queue_depth_uses_live_sqs_attribute() -> None:
    c = ModeTelemetryCollector()
    fake_sqs = MagicMock()
    fake_sqs.get_queue_attributes.return_value = {
        "Attributes": {"ApproximateNumberOfMessages": "42"}
    }
    c._sqs_client = fake_sqs

    assert c.queue_depth("https://sqs.example/queue") == 42
    fake_sqs.get_queue_attributes.assert_called_once_with(
        QueueUrl="https://sqs.example/queue",
        AttributeNames=["ApproximateNumberOfMessages"],
    )


def test_queue_depth_swallows_sqs_exception() -> None:
    c = ModeTelemetryCollector()
    fake_sqs = MagicMock()
    fake_sqs.get_queue_attributes.side_effect = RuntimeError("throttled")
    c._sqs_client = fake_sqs

    assert c.queue_depth("https://sqs.example/queue") == 0


# ---------------------------------------------------------------------------
# Active burst jobs (K8s)
# ---------------------------------------------------------------------------


def test_active_burst_jobs_zero_when_k8s_unavailable() -> None:
    c = ModeTelemetryCollector()
    c._k8s_batch_v1 = False
    assert c.active_burst_jobs("aura-system") == 0


def test_active_burst_jobs_counts_active_jobs() -> None:
    c = ModeTelemetryCollector()

    def _job(active: Any) -> Any:
        j = MagicMock()
        j.status.active = active
        return j

    fake_api = MagicMock()
    fake_api.list_namespaced_job.return_value.items = [
        _job(2),  # active=2 -> counts as 1
        _job(0),  # active=0 -> skip
        _job(None),  # missing -> skip
        _job(1),  # active=1 -> counts as 1
    ]
    c._k8s_batch_v1 = fake_api

    assert c.active_burst_jobs("aura-system") == 2
    fake_api.list_namespaced_job.assert_called_once_with(
        namespace="aura-system",
        label_selector="aura.io/burst=true",
    )


def test_active_burst_jobs_swallows_k8s_exception() -> None:
    c = ModeTelemetryCollector()
    fake_api = MagicMock()
    fake_api.list_namespaced_job.side_effect = RuntimeError("k8s 5xx")
    c._k8s_batch_v1 = fake_api

    assert c.active_burst_jobs("aura-system") == 0


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


def test_get_mode_telemetry_collector_returns_singleton() -> None:
    _reset_mode_telemetry_collector()
    a = _get_mode_telemetry_collector()
    b = _get_mode_telemetry_collector()
    assert a is b


def test_reset_mode_telemetry_collector_constructs_fresh() -> None:
    a = _get_mode_telemetry_collector()
    _reset_mode_telemetry_collector()
    b = _get_mode_telemetry_collector()
    assert a is not b
