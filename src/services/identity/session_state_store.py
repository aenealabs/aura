"""Session and OIDC-state persistence for the identity API (Wave 5a, #163).

Closes the 5 OIDC ``# TODO: ... DynamoDB ...`` markers in
``src/api/identity_endpoints.py`` by providing a single store with two
item kinds:

  - **PendingOIDCState**: the ``state`` + ``nonce`` + ``code_verifier``
    triple created at ``/oidc/login`` and consumed by ``/oidc/callback``.
    Short-lived (TTL ~10 minutes) so abandoned login attempts don't
    accumulate.
  - **AuthSession**: the durable session record (``session_id``,
    ``user_sub``, ``idp_id``, ``refresh_token_jti``, ...) issued after
    a successful callback. TTL aligned with the refresh-token lifetime
    so DynamoDB cleans them up automatically.

Plus a tiny ``invalidate_refresh_jti`` API so ``/logout`` can revoke
a session's refresh token; ``is_refresh_jti_invalidated`` is the read
side that the token service consults before issuing new tokens off a
refresh.

Two modes:

  - **mock**: in-memory dicts. Default and what unit tests use.
  - **aws**: boto3 DynamoDB client. Each item type lives in its own
    table to keep the schema simple and the TTL configuration tight.

Author: Project Aura Team
Created: 2026-05-11
"""

from __future__ import annotations

import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from .models import AuthSession

logger = logging.getLogger(__name__)


# Default TTLs. Both are deliberately short so the DynamoDB-side TTL
# cleanup keeps the tables compact even without scheduled grooming.
_DEFAULT_PENDING_STATE_TTL_SECONDS = 600  # 10 minutes
_DEFAULT_SESSION_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days (refresh lifetime)
_DEFAULT_JTI_REVOCATION_TTL_SECONDS = 60 * 60 * 24 * 30


@dataclass
class PendingOIDCState:
    """Transient state created at ``/oidc/login`` and consumed at callback.

    ``state`` is the URL-safe token that goes to the IdP; we use it as
    the DynamoDB key. ``code_verifier`` is the PKCE secret. ``nonce``
    is the OIDC replay-protection nonce that must round-trip through
    the IdP and back via the id_token.
    """

    state: str
    idp_id: str
    code_verifier: Optional[str]
    nonce: Optional[str]
    organization_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    ttl_seconds: int = _DEFAULT_PENDING_STATE_TTL_SECONDS

    @property
    def expires_at_epoch(self) -> int:
        """DynamoDB TTL attribute value (Unix epoch seconds)."""
        return int(self.created_at + self.ttl_seconds)

    def is_expired(self, now: Optional[float] = None) -> bool:
        return (now or time.time()) >= self.created_at + self.ttl_seconds

    def to_dynamodb_item(self) -> dict[str, Any]:
        return {
            "state": {"S": self.state},
            "idp_id": {"S": self.idp_id},
            "code_verifier": (
                {"S": self.code_verifier} if self.code_verifier else {"NULL": True}
            ),
            "nonce": ({"S": self.nonce} if self.nonce else {"NULL": True}),
            "organization_id": (
                {"S": self.organization_id} if self.organization_id else {"NULL": True}
            ),
            "created_at": {"N": str(int(self.created_at))},
            "ttl_seconds": {"N": str(int(self.ttl_seconds))},
            "expires_at": {"N": str(self.expires_at_epoch)},
        }

    @classmethod
    def from_dynamodb_item(cls, item: dict[str, Any]) -> "PendingOIDCState":
        def _maybe_str(attr: dict[str, Any] | None) -> Optional[str]:
            if not attr or attr.get("NULL"):
                return None
            return attr.get("S")

        return cls(
            state=item["state"]["S"],
            idp_id=item["idp_id"]["S"],
            code_verifier=_maybe_str(item.get("code_verifier")),
            nonce=_maybe_str(item.get("nonce")),
            organization_id=_maybe_str(item.get("organization_id")),
            created_at=float(item.get("created_at", {}).get("N", "0")),
            ttl_seconds=int(
                item.get("ttl_seconds", {}).get(
                    "N", str(_DEFAULT_PENDING_STATE_TTL_SECONDS)
                )
            ),
        )


class SessionStateStore:
    """Persistence for OIDC pending state, sessions, and JTI revocations.

    Construct with ``dynamodb_client=None`` for unit tests (mock mode).
    In production wiring, pass ``boto3.client('dynamodb')`` and the
    three table names; the service will route writes there.
    """

    def __init__(
        self,
        dynamodb_client: Optional[Any] = None,
        pending_state_table: Optional[str] = None,
        sessions_table: Optional[str] = None,
        revoked_jti_table: Optional[str] = None,
    ) -> None:
        self._ddb = dynamodb_client
        env = os.environ.get
        self._pending_table = (
            pending_state_table
            or env("AURA_IDENTITY_PENDING_STATE_TABLE")
            or "aura-identity-pending-state"
        )
        self._sessions_table = (
            sessions_table
            or env("AURA_IDENTITY_SESSIONS_TABLE")
            or "aura-identity-sessions"
        )
        self._revoked_table = (
            revoked_jti_table
            or env("AURA_IDENTITY_REVOKED_JTI_TABLE")
            or "aura-identity-revoked-jtis"
        )
        # Mock-mode in-memory storage
        self._mock_pending: dict[str, PendingOIDCState] = {}
        self._mock_sessions: dict[str, AuthSession] = {}
        self._mock_revoked: dict[str, float] = {}  # jti -> revoked_at_epoch

    @property
    def mock_mode(self) -> bool:
        return self._ddb is None

    # ---------------------------------------------------------------
    # Pending OIDC state
    # ---------------------------------------------------------------

    def create_pending_state(
        self,
        idp_id: str,
        code_verifier: Optional[str] = None,
        nonce: Optional[str] = None,
        organization_id: Optional[str] = None,
        ttl_seconds: int = _DEFAULT_PENDING_STATE_TTL_SECONDS,
    ) -> PendingOIDCState:
        """Generate a fresh state token and persist it.

        Returns the populated ``PendingOIDCState`` so the caller can
        forward the ``state`` value to the IdP authorization URL.
        """
        state = secrets.token_urlsafe(32)
        pending = PendingOIDCState(
            state=state,
            idp_id=idp_id,
            code_verifier=code_verifier,
            nonce=nonce,
            organization_id=organization_id,
            ttl_seconds=ttl_seconds,
        )
        self._put_pending_state(pending)
        return pending

    def _put_pending_state(self, state: PendingOIDCState) -> None:
        if self.mock_mode:
            self._mock_pending[state.state] = state
            return
        try:
            self._ddb.put_item(
                TableName=self._pending_table, Item=state.to_dynamodb_item()
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("put_item pending_state failed: %s", exc)
            raise

    def get_pending_state(self, state: str) -> Optional[PendingOIDCState]:
        """Look up a pending state. Returns None if missing or expired."""
        if self.mock_mode:
            found = self._mock_pending.get(state)
            if found is None or found.is_expired():
                return None
            return found
        try:
            resp = self._ddb.get_item(
                TableName=self._pending_table, Key={"state": {"S": state}}
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("get_item pending_state failed: %s", exc)
            return None
        item = resp.get("Item")
        if not item:
            return None
        result = PendingOIDCState.from_dynamodb_item(item)
        if result.is_expired():
            return None
        return result

    def consume_pending_state(self, state: str) -> Optional[PendingOIDCState]:
        """Look up and delete a pending state in one step.

        Used at the ``/oidc/callback`` boundary so a replayed
        authorization code can't re-use the same state value.
        """
        found = self.get_pending_state(state)
        if found is None:
            return None
        self.delete_pending_state(state)
        return found

    def delete_pending_state(self, state: str) -> None:
        if self.mock_mode:
            self._mock_pending.pop(state, None)
            return
        try:
            self._ddb.delete_item(
                TableName=self._pending_table, Key={"state": {"S": state}}
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("delete_item pending_state failed: %s", exc)

    # ---------------------------------------------------------------
    # AuthSession
    # ---------------------------------------------------------------

    def put_session(self, session: AuthSession) -> None:
        """Persist (or upsert) a session record."""
        if self.mock_mode:
            self._mock_sessions[session.session_id] = session
            return
        item = self._session_to_ddb_item(session)
        try:
            self._ddb.put_item(TableName=self._sessions_table, Item=item)
        except Exception as exc:  # noqa: BLE001
            logger.error("put_item session failed: %s", exc)
            raise

    def get_session(self, session_id: str) -> Optional[AuthSession]:
        if self.mock_mode:
            return self._mock_sessions.get(session_id)
        try:
            resp = self._ddb.get_item(
                TableName=self._sessions_table,
                Key={"session_id": {"S": session_id}},
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("get_item session failed: %s", exc)
            return None
        item = resp.get("Item")
        if not item:
            return None
        return self._session_from_ddb_item(item)

    def delete_session(self, session_id: str) -> None:
        if self.mock_mode:
            self._mock_sessions.pop(session_id, None)
            return
        try:
            self._ddb.delete_item(
                TableName=self._sessions_table,
                Key={"session_id": {"S": session_id}},
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("delete_item session failed: %s", exc)

    # ---------------------------------------------------------------
    # Refresh-token JTI revocation
    # ---------------------------------------------------------------

    def invalidate_refresh_jti(
        self,
        jti: str,
        ttl_seconds: int = _DEFAULT_JTI_REVOCATION_TTL_SECONDS,
    ) -> None:
        """Mark a refresh-token JTI as revoked.

        Items live in the revocation table with a TTL that matches the
        refresh-token lifetime; once the token expires by its own
        ``exp`` claim, DynamoDB removes the revocation row too.
        """
        revoked_at = time.time()
        if self.mock_mode:
            self._mock_revoked[jti] = revoked_at
            return
        try:
            self._ddb.put_item(
                TableName=self._revoked_table,
                Item={
                    "jti": {"S": jti},
                    "revoked_at": {"N": str(int(revoked_at))},
                    "expires_at": {"N": str(int(revoked_at + ttl_seconds))},
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("put_item revoked_jti failed: %s", exc)
            raise

    def is_refresh_jti_invalidated(self, jti: str) -> bool:
        if self.mock_mode:
            return jti in self._mock_revoked
        try:
            resp = self._ddb.get_item(
                TableName=self._revoked_table, Key={"jti": {"S": jti}}
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("get_item revoked_jti failed: %s", exc)
            return False  # fail-open; the token's own exp claim still gates use
        return bool(resp.get("Item"))

    # ---------------------------------------------------------------
    # Internals
    # ---------------------------------------------------------------

    def _session_to_ddb_item(self, session: AuthSession) -> dict[str, Any]:
        """Convert an AuthSession to a DynamoDB item.

        Wraps the existing ``AuthSession.to_dynamodb_item`` shape in
        DynamoDB attribute-value format so callers can pass the result
        straight to ``put_item``.
        """
        plain = session.to_dynamodb_item()

        def _av(value: Any) -> dict[str, Any]:
            if value is None:
                return {"NULL": True}
            if isinstance(value, bool):
                return {"BOOL": value}
            if isinstance(value, (int, float)):
                return {"N": str(value)}
            if isinstance(value, list):
                return {"L": [_av(v) for v in value]}
            return {"S": str(value)}

        item = {k: _av(v) for k, v in plain.items()}
        # TTL attribute: keep ~30 days from creation. AuthSession's
        # created_at is an ISO string; for the simple TTL math here
        # we use the current time as the anchor.
        item.setdefault(
            "expires_at_epoch",
            {"N": str(int(time.time() + _DEFAULT_SESSION_TTL_SECONDS))},
        )
        return item

    def _session_from_ddb_item(self, item: dict[str, Any]) -> AuthSession:
        def _plain(attr: dict[str, Any]) -> Any:
            if attr.get("NULL"):
                return None
            if "S" in attr:
                return attr["S"]
            if "N" in attr:
                try:
                    return int(attr["N"])
                except ValueError:
                    return float(attr["N"])
            if "BOOL" in attr:
                return attr["BOOL"]
            if "L" in attr:
                return [_plain(x) for x in attr["L"]]
            return None

        flat = {k: _plain(v) for k, v in item.items() if k != "expires_at_epoch"}
        return AuthSession.from_dynamodb_item(flat)


# Process-singleton so the OIDC login / callback / refresh handlers
# share one client + cache instead of constructing per-request.
_INSTANCE: Optional[SessionStateStore] = None


def get_session_state_store() -> SessionStateStore:
    """Return the process-singleton ``SessionStateStore``.

    Tests should call ``reset_session_state_store()`` between cases.
    """
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = SessionStateStore()
    return _INSTANCE


def reset_session_state_store(replacement: Optional[SessionStateStore] = None) -> None:
    """Replace the singleton (test hook)."""
    global _INSTANCE
    _INSTANCE = replacement
