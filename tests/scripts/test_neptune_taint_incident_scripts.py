"""Unit tests for the ADR-093 Phase 4.2 incident-response scripts.

Both scripts (kill-switch + revocation) accept an injected client
factory so tests substitute fakes without live AWS / boto3 import.
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock

import pytest

from scripts.disable_neptune_taint_resolver import flip_flag
from scripts.revoke_summary_signatures import revoke_window

# ---------------------------------------------------------------------------
# disable_neptune_taint_resolver.flip_flag
# ---------------------------------------------------------------------------


def test_flip_flag_disable_sets_value_to_false() -> None:
    ssm = MagicMock()

    def factory(_region: str) -> Any:
        return ssm

    rc = flip_flag(
        region="us-east-1",
        parameter_name="/aura/scanner/neptune_taint_resolver_enabled",
        enable=False,
        dry_run=False,
        ssm_client_factory=factory,
    )
    assert rc == 0
    ssm.put_parameter.assert_called_once()
    call = ssm.put_parameter.call_args
    assert call.kwargs["Name"] == "/aura/scanner/neptune_taint_resolver_enabled"
    assert call.kwargs["Value"] == "false"
    assert call.kwargs["Type"] == "String"
    assert call.kwargs["Overwrite"] is True


def test_flip_flag_enable_sets_value_to_true() -> None:
    ssm = MagicMock()
    rc = flip_flag(
        region="us-east-1",
        parameter_name="/x",
        enable=True,
        dry_run=False,
        ssm_client_factory=lambda _r: ssm,
    )
    assert rc == 0
    assert ssm.put_parameter.call_args.kwargs["Value"] == "true"


def test_flip_flag_dry_run_does_not_call_aws(
    caplog: pytest.LogCaptureFixture,
) -> None:
    ssm = MagicMock()
    rc = flip_flag(
        region="us-east-1",
        parameter_name="/x",
        enable=False,
        dry_run=True,
        ssm_client_factory=lambda _r: ssm,
    )
    assert rc == 0
    ssm.put_parameter.assert_not_called()


def test_flip_flag_returns_nonzero_on_aws_failure() -> None:
    ssm = MagicMock()
    ssm.put_parameter.side_effect = RuntimeError("ssm throttled")
    rc = flip_flag(
        region="us-east-1",
        parameter_name="/x",
        enable=False,
        dry_run=False,
        ssm_client_factory=lambda _r: ssm,
    )
    assert rc == 1


# ---------------------------------------------------------------------------
# revoke_summary_signatures.revoke_window
# ---------------------------------------------------------------------------


def test_revoke_window_writes_entry_to_dynamodb() -> None:
    ddb = MagicMock()
    rc = revoke_window(
        region="us-east-1",
        table_name="summary_revocations",
        signer_arn="arn:aws:kms:us-east-1:111:key/abcd",
        from_iso="2026-05-13T14:00:00+00:00",
        to_iso="2026-05-13T16:30:00+00:00",
        reason="worker compromise",
        dry_run=False,
        ddb_client_factory=lambda _r: ddb,
    )
    assert rc == 0
    ddb.put_item.assert_called_once()
    call = ddb.put_item.call_args
    assert call.kwargs["TableName"] == "summary_revocations"
    item = call.kwargs["Item"]
    assert item["signer_arn"]["S"] == "arn:aws:kms:us-east-1:111:key/abcd"
    assert item["from_iso"]["S"] == "2026-05-13T14:00:00+00:00"
    assert item["to_iso"]["S"] == "2026-05-13T16:30:00+00:00"
    assert item["reason"]["S"] == "worker compromise"


def test_revoke_window_rejects_invalid_timestamps() -> None:
    ddb = MagicMock()
    rc = revoke_window(
        region="us-east-1",
        table_name="summary_revocations",
        signer_arn="arn",
        from_iso="not-a-timestamp",
        to_iso="2026-05-13T16:30:00+00:00",
        reason="x",
        dry_run=False,
        ddb_client_factory=lambda _r: ddb,
    )
    assert rc == 2
    ddb.put_item.assert_not_called()


def test_revoke_window_rejects_inverted_window() -> None:
    ddb = MagicMock()
    rc = revoke_window(
        region="us-east-1",
        table_name="summary_revocations",
        signer_arn="arn",
        from_iso="2026-05-13T16:00:00+00:00",
        to_iso="2026-05-13T14:00:00+00:00",
        reason="x",
        dry_run=False,
        ddb_client_factory=lambda _r: ddb,
    )
    assert rc == 2
    ddb.put_item.assert_not_called()


def test_revoke_window_dry_run_does_not_call_aws() -> None:
    ddb = MagicMock()
    rc = revoke_window(
        region="us-east-1",
        table_name="summary_revocations",
        signer_arn="arn",
        from_iso="2026-05-13T14:00:00+00:00",
        to_iso="2026-05-13T16:30:00+00:00",
        reason="x",
        dry_run=True,
        ddb_client_factory=lambda _r: ddb,
    )
    assert rc == 0
    ddb.put_item.assert_not_called()


def test_revoke_window_returns_nonzero_on_aws_failure() -> None:
    ddb = MagicMock()
    ddb.put_item.side_effect = RuntimeError("ddb down")
    rc = revoke_window(
        region="us-east-1",
        table_name="summary_revocations",
        signer_arn="arn",
        from_iso="2026-05-13T14:00:00+00:00",
        to_iso="2026-05-13T16:30:00+00:00",
        reason="x",
        dry_run=False,
        ddb_client_factory=lambda _r: ddb,
    )
    assert rc == 1
