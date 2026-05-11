"""Tests for ``identity.session_state_store`` (Wave 5a, #163).

Closes the 5 OIDC ``# TODO: ... DynamoDB ...`` markers in
``src/api/identity_endpoints.py``. These tests verify both mock-mode
(used by the test suite) and live-mode behaviour against an injected
mock DynamoDB client.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from src.services.identity.models import AuthSession
from src.services.identity.session_state_store import (
    PendingOIDCState,
    SessionStateStore,
    get_session_state_store,
    reset_session_state_store,
)

# ---------------------------------------------------------------------------
# Pending OIDC state - mock mode
# ---------------------------------------------------------------------------


def test_create_pending_state_generates_unique_token() -> None:
    store = SessionStateStore()

    p1 = store.create_pending_state(idp_id="okta-prod")
    p2 = store.create_pending_state(idp_id="okta-prod")

    assert p1.state != p2.state
    assert len(p1.state) >= 32
    assert p1.idp_id == "okta-prod"


def test_get_pending_state_round_trips() -> None:
    store = SessionStateStore()
    p = store.create_pending_state(idp_id="azure-eu", code_verifier="cv-1", nonce="n-1")

    fetched = store.get_pending_state(p.state)

    assert fetched is not None
    assert fetched.idp_id == "azure-eu"
    assert fetched.code_verifier == "cv-1"
    assert fetched.nonce == "n-1"


def test_get_pending_state_returns_none_for_missing() -> None:
    store = SessionStateStore()
    assert store.get_pending_state("never-stored") is None


def test_consume_pending_state_atomically_reads_and_deletes() -> None:
    store = SessionStateStore()
    p = store.create_pending_state(idp_id="okta-prod")

    first = store.consume_pending_state(p.state)
    second = store.consume_pending_state(p.state)

    assert first is not None
    assert first.state == p.state
    assert second is None  # replay rejected


def test_get_pending_state_filters_expired_rows() -> None:
    store = SessionStateStore()
    p = PendingOIDCState(
        state="x",
        idp_id="okta",
        code_verifier=None,
        nonce=None,
        created_at=time.time() - 1000,
        ttl_seconds=60,
    )
    store._put_pending_state(p)

    assert store.get_pending_state("x") is None


# ---------------------------------------------------------------------------
# Pending OIDC state - DynamoDB shape
# ---------------------------------------------------------------------------


def test_pending_state_round_trips_through_dynamodb_attrs() -> None:
    original = PendingOIDCState(
        state="s-1",
        idp_id="okta",
        code_verifier="cv",
        nonce="n",
        organization_id="org-1",
    )
    item = original.to_dynamodb_item()
    restored = PendingOIDCState.from_dynamodb_item(item)

    assert restored.state == "s-1"
    assert restored.idp_id == "okta"
    assert restored.code_verifier == "cv"
    assert restored.nonce == "n"
    assert restored.organization_id == "org-1"


def test_pending_state_dynamodb_attrs_include_ttl() -> None:
    p = PendingOIDCState(state="s", idp_id="okta", code_verifier=None, nonce=None)
    item = p.to_dynamodb_item()
    assert "expires_at" in item
    assert int(item["expires_at"]["N"]) >= int(p.created_at)


def test_pending_state_live_mode_calls_put_item() -> None:
    ddb = MagicMock()
    store = SessionStateStore(dynamodb_client=ddb, pending_state_table="pending-table")

    p = store.create_pending_state(idp_id="okta")

    ddb.put_item.assert_called_once()
    args = ddb.put_item.call_args.kwargs
    assert args["TableName"] == "pending-table"
    assert args["Item"]["state"]["S"] == p.state


def test_pending_state_live_mode_get_item_returns_state() -> None:
    ddb = MagicMock()
    store = SessionStateStore(dynamodb_client=ddb, pending_state_table="pending-table")
    original = PendingOIDCState(
        state="s-x", idp_id="okta", code_verifier="cv", nonce="n"
    )
    ddb.get_item.return_value = {"Item": original.to_dynamodb_item()}

    fetched = store.get_pending_state("s-x")

    assert fetched is not None
    assert fetched.code_verifier == "cv"


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


def test_session_round_trip_in_mock_mode() -> None:
    store = SessionStateStore()
    session = AuthSession(
        session_id="sess-1",
        user_sub="user-1",
        idp_id="okta",
        organization_id="org-1",
        refresh_token_jti="jti-1",
    )

    store.put_session(session)
    fetched = store.get_session("sess-1")

    assert fetched is not None
    assert fetched.session_id == "sess-1"
    assert fetched.refresh_token_jti == "jti-1"


def test_delete_session_removes_row() -> None:
    store = SessionStateStore()
    session = AuthSession(
        session_id="sess-rm",
        user_sub="u",
        idp_id="okta",
        organization_id="org",
    )
    store.put_session(session)
    store.delete_session("sess-rm")

    assert store.get_session("sess-rm") is None


def test_session_live_mode_writes_to_dynamodb() -> None:
    ddb = MagicMock()
    store = SessionStateStore(dynamodb_client=ddb, sessions_table="sessions-table")
    session = AuthSession(
        session_id="sess-2",
        user_sub="u-2",
        idp_id="okta",
        organization_id="org",
        refresh_token_jti="jti",
    )

    store.put_session(session)

    ddb.put_item.assert_called_once()
    args = ddb.put_item.call_args.kwargs
    assert args["TableName"] == "sessions-table"
    assert args["Item"]["session_id"]["S"] == "sess-2"


# ---------------------------------------------------------------------------
# JTI revocation
# ---------------------------------------------------------------------------


def test_invalidate_and_check_jti() -> None:
    store = SessionStateStore()
    assert store.is_refresh_jti_invalidated("jti-a") is False

    store.invalidate_refresh_jti("jti-a")

    assert store.is_refresh_jti_invalidated("jti-a") is True
    assert store.is_refresh_jti_invalidated("jti-b") is False


def test_jti_revocation_live_mode_writes_with_ttl() -> None:
    ddb = MagicMock()
    store = SessionStateStore(dynamodb_client=ddb, revoked_jti_table="revoked-table")

    store.invalidate_refresh_jti("jti-x", ttl_seconds=60)

    args = ddb.put_item.call_args.kwargs
    assert args["TableName"] == "revoked-table"
    item = args["Item"]
    assert item["jti"]["S"] == "jti-x"
    assert int(item["expires_at"]["N"]) > time.time()


def test_jti_revocation_check_live_mode_fail_open_on_ddb_error() -> None:
    """If DynamoDB is unreachable, revocation check returns False.

    Fail-open is intentional: the token's own ``exp`` claim still
    gates use, so a transient DDB outage doesn't lock out all users.
    The downside (briefly accepting a token that was meant to be
    revoked) is bounded by the token TTL.
    """
    ddb = MagicMock()
    ddb.get_item.side_effect = RuntimeError("DDB throttled")
    store = SessionStateStore(dynamodb_client=ddb, revoked_jti_table="revoked-table")

    assert store.is_refresh_jti_invalidated("any-jti") is False


# ---------------------------------------------------------------------------
# Singleton helpers
# ---------------------------------------------------------------------------


def test_get_session_state_store_returns_singleton() -> None:
    reset_session_state_store()
    a = get_session_state_store()
    b = get_session_state_store()
    assert a is b


def test_reset_session_state_store_swaps_instance() -> None:
    custom = SessionStateStore()
    reset_session_state_store(custom)
    assert get_session_state_store() is custom
    reset_session_state_store(None)
    assert get_session_state_store() is not custom
