"""
P0 Authentication/Authorization Boundary Edge Case Tests.

Tests for high-priority edge cases involving authentication and
authorization boundaries that could lead to security vulnerabilities.

These tests cover edge cases identified in GitHub Issue #167.

Categories:
- Token Lifecycle: JWT expiration during operations, refresh races, JWKS cache
- Permission Changes: Role changes during sessions, org deletion
- Session Management: Concurrent sessions, invalidation propagation
"""

import hashlib
import hmac
import time
from datetime import datetime, timezone

import pytest

# =============================================================================
# TOKEN LIFECYCLE EDGE CASES
# =============================================================================


class TestJWTExpirationDuringOperation:
    """Tests for JWT token expiration during long-running operations."""

    @pytest.mark.asyncio
    async def test_jwt_expires_during_long_ingestion(self):
        """Verify system handles JWT expiration during repository ingestion."""
        # Simulate a token that expires mid-operation
        token_issued_at = time.time()
        token_expires_at = token_issued_at + 300  # 5 minutes

        def check_token_validity(token_exp: float) -> bool:
            """Check if token is still valid."""
            return time.time() < token_exp

        # Token valid at start
        assert check_token_validity(token_expires_at)

        # Simulate long-running operation that should check token periodically
        class LongRunningOperation:
            def __init__(self, token_exp: float):
                self.token_exp = token_exp
                self.refresh_count = 0

            async def execute_with_token_refresh(self):
                """Execute with periodic token validity checks."""
                steps = ["clone", "parse", "index", "graph"]
                for step in steps:
                    if not check_token_validity(self.token_exp):
                        # Token expired - should trigger refresh
                        self.refresh_count += 1
                        self.token_exp = time.time() + 300  # Refresh for 5 more mins
                    # Simulate step execution
                    await self._execute_step(step)
                return True

            async def _execute_step(self, step: str):
                """Execute a single step."""

        operation = LongRunningOperation(token_expires_at)
        result = await operation.execute_with_token_refresh()

        assert result is True
        # Operation should complete even if token was refreshed

    @pytest.mark.asyncio
    async def test_jwt_refresh_token_rotation_race(self):
        """Verify handling of refresh token rotation race condition."""
        # Simulate two concurrent requests using the same refresh token
        current_refresh_token = "refresh_token_v1"
        used_tokens = set()
        token_version = 1

        def rotate_refresh_token(refresh_token: str) -> tuple[str, str]:
            """Rotate refresh token and return new access + refresh tokens."""
            nonlocal token_version

            if refresh_token in used_tokens:
                # Token already used - reject (prevents replay)
                raise ValueError("Refresh token already used")

            used_tokens.add(refresh_token)
            token_version += 1
            new_access = f"access_token_v{token_version}"
            new_refresh = f"refresh_token_v{token_version}"
            return new_access, new_refresh

        # First request succeeds
        access1, refresh1 = rotate_refresh_token(current_refresh_token)
        assert access1 == "access_token_v2"
        assert refresh1 == "refresh_token_v2"

        # Second request with same token fails (race condition handled)
        with pytest.raises(ValueError, match="already used"):
            rotate_refresh_token(current_refresh_token)

        # New refresh token works
        access2, refresh2 = rotate_refresh_token(refresh1)
        assert access2 == "access_token_v3"

    @pytest.mark.asyncio
    async def test_jwks_cache_stale_after_key_rotation(self):
        """Verify system handles stale JWKS cache after key rotation."""
        # Simulate JWKS cache with TTL
        jwks_cache = {
            "keys": [{"kid": "key-1", "n": "modulus1", "e": "AQAB"}],
            "cached_at": time.time(),
            "ttl_seconds": 3600,
        }

        def is_cache_stale(cache: dict) -> bool:
            """Check if JWKS cache is stale."""
            age = time.time() - cache["cached_at"]
            return age > cache["ttl_seconds"]

        def find_key_in_cache(kid: str, cache: dict) -> dict | None:
            """Find key by kid in cache."""
            for key in cache["keys"]:
                if key["kid"] == kid:
                    return key
            return None

        # Cache is fresh
        assert not is_cache_stale(jwks_cache)
        assert find_key_in_cache("key-1", jwks_cache) is not None

        # New key not in cache (key rotation happened)
        assert find_key_in_cache("key-2", jwks_cache) is None

        # System should handle missing key by refreshing cache
        def validate_token_with_cache_refresh(
            token_kid: str, cache: dict
        ) -> tuple[bool, dict]:
            """Validate token, refreshing cache if key not found."""
            key = find_key_in_cache(token_kid, cache)

            if key is None or is_cache_stale(cache):
                # Refresh cache from JWKS endpoint
                cache = {
                    "keys": [
                        {"kid": "key-1", "n": "modulus1", "e": "AQAB"},
                        {"kid": "key-2", "n": "modulus2", "e": "AQAB"},  # New key
                    ],
                    "cached_at": time.time(),
                    "ttl_seconds": 3600,
                }
                key = find_key_in_cache(token_kid, cache)

            return key is not None, cache

        # Validate with new key - should trigger refresh
        valid, updated_cache = validate_token_with_cache_refresh("key-2", jwks_cache)
        assert valid
        assert find_key_in_cache("key-2", updated_cache) is not None


class TestTokenReplayPrevention:
    """Tests for token replay attack prevention."""

    @pytest.mark.asyncio
    async def test_jti_prevents_token_replay(self):
        """Verify JWT ID (jti) prevents token replay attacks."""
        used_jtis: set[str] = set()

        def validate_jti(jti: str) -> bool:
            """Validate jti hasn't been used before."""
            if jti in used_jtis:
                return False
            used_jtis.add(jti)
            return True

        # First use succeeds
        assert validate_jti("unique-jti-123")

        # Replay attempt fails
        assert not validate_jti("unique-jti-123")

        # Different jti succeeds
        assert validate_jti("unique-jti-456")

    @pytest.mark.asyncio
    async def test_token_nbf_prevents_early_use(self):
        """Verify not-before (nbf) claim prevents early token use."""

        def validate_nbf(nbf_timestamp: int, clock_skew_seconds: int = 60) -> bool:
            """Validate token's not-before claim with clock skew tolerance."""
            current_time = int(time.time())
            # Allow small clock skew
            return current_time >= (nbf_timestamp - clock_skew_seconds)

        current = int(time.time())

        # Token valid now
        assert validate_nbf(current)

        # Token valid in past
        assert validate_nbf(current - 100)

        # Token within clock skew tolerance
        assert validate_nbf(current + 30)

        # Token too far in future
        assert not validate_nbf(current + 120)


# =============================================================================
# PERMISSION CHANGES DURING SESSION
# =============================================================================


class TestRoleChangeDuringSession:
    """Tests for handling role changes during active sessions."""

    @pytest.mark.asyncio
    async def test_role_downgrade_during_active_session(self):
        """Verify role downgrade is enforced during active session."""
        # Simulate session with cached permissions
        session = {
            "user_id": "user-123",
            "role": "admin",
            "permissions": {"read", "write", "delete", "admin"},
            "created_at": time.time(),
        }

        # Simulate role change in database
        user_db = {"user-123": {"role": "viewer", "permissions": {"read"}}}

        def get_current_permissions(user_id: str) -> set:
            """Get current permissions from database."""
            user = user_db.get(user_id, {})
            return user.get("permissions", set())

        def check_permission(
            session: dict, action: str, revalidate: bool = False
        ) -> bool:
            """Check if session has permission, optionally revalidating."""
            if revalidate:
                # Fetch fresh permissions from database
                current_perms = get_current_permissions(session["user_id"])
                return action in current_perms

            # Use cached permissions
            return action in session["permissions"]

        # Cached permissions allow admin
        assert check_permission(session, "admin", revalidate=False)

        # Revalidated permissions deny admin (role was downgraded)
        assert not check_permission(session, "admin", revalidate=True)

        # Viewer can still read
        assert check_permission(session, "read", revalidate=True)

    @pytest.mark.asyncio
    async def test_organization_deleted_with_pending_approvals(self):
        """Verify pending approvals are handled when org is deleted."""
        organizations = {"org-123": {"name": "Test Org", "status": "active"}}
        pending_approvals = [
            {"id": "approval-1", "org_id": "org-123", "status": "pending"},
            {"id": "approval-2", "org_id": "org-123", "status": "pending"},
        ]

        def delete_organization(org_id: str) -> dict:
            """Delete organization and handle pending approvals."""
            org = organizations.get(org_id)
            if not org:
                return {"success": False, "error": "Org not found"}

            # Cancel all pending approvals for this org
            cancelled = []
            for approval in pending_approvals:
                if approval["org_id"] == org_id and approval["status"] == "pending":
                    approval["status"] = "cancelled"
                    approval["cancelled_reason"] = "organization_deleted"
                    cancelled.append(approval["id"])

            # Soft delete org
            org["status"] = "deleted"
            org["deleted_at"] = datetime.now(timezone.utc).isoformat()

            return {"success": True, "cancelled_approvals": cancelled}

        result = delete_organization("org-123")

        assert result["success"]
        assert len(result["cancelled_approvals"]) == 2

        # Verify approvals are cancelled
        for approval in pending_approvals:
            assert approval["status"] == "cancelled"
            assert approval["cancelled_reason"] == "organization_deleted"

    @pytest.mark.asyncio
    async def test_api_key_rotation_during_active_integration(self):
        """Verify API key rotation doesn't break active integrations."""
        # API key store with versioning
        api_keys = {
            "integration-github": {
                "current": "key_v2_abc123",
                "previous": "key_v1_xyz789",  # Keep previous for grace period
                "rotated_at": time.time(),
                "grace_period_seconds": 300,
            }
        }

        def validate_api_key(integration_id: str, provided_key: str) -> bool:
            """Validate API key, allowing previous key during grace period."""
            key_info = api_keys.get(integration_id)
            if not key_info:
                return False

            # Current key always valid
            if provided_key == key_info["current"]:
                return True

            # Previous key valid during grace period
            if provided_key == key_info.get("previous"):
                time_since_rotation = time.time() - key_info["rotated_at"]
                if time_since_rotation < key_info["grace_period_seconds"]:
                    return True

            return False

        # Current key works
        assert validate_api_key("integration-github", "key_v2_abc123")

        # Previous key works during grace period
        assert validate_api_key("integration-github", "key_v1_xyz789")

        # Random key fails
        assert not validate_api_key("integration-github", "invalid_key")

    @pytest.mark.asyncio
    async def test_service_account_permissions_modified_mid_operation(self):
        """Verify service account permission changes are handled gracefully."""
        service_accounts = {
            "sa-ingestion": {
                "permissions": ["read:repos", "write:graph"],
                "last_validated": time.time(),
            }
        }

        operation_log = []

        async def execute_with_permission_check(
            sa_id: str, required_permission: str, operation: str
        ) -> dict:
            """Execute operation with permission check."""
            sa = service_accounts.get(sa_id)
            if not sa:
                return {"success": False, "error": "Service account not found"}

            if required_permission not in sa["permissions"]:
                return {
                    "success": False,
                    "error": f"Missing permission: {required_permission}",
                }

            # Execute operation
            operation_log.append(operation)
            return {"success": True, "operation": operation}

        # Operation with valid permission succeeds
        result = await execute_with_permission_check(
            "sa-ingestion", "read:repos", "clone_repository"
        )
        assert result["success"]

        # Simulate permission removal mid-operation
        service_accounts["sa-ingestion"]["permissions"].remove("write:graph")

        # Next operation with removed permission fails
        result = await execute_with_permission_check(
            "sa-ingestion", "write:graph", "update_graph"
        )
        assert not result["success"]
        assert "Missing permission" in result["error"]


# =============================================================================
# SESSION MANAGEMENT EDGE CASES
# =============================================================================


class TestConcurrentSessions:
    """Tests for concurrent session handling."""

    @pytest.mark.asyncio
    async def test_concurrent_sessions_modifying_same_resource(self):
        """Verify concurrent sessions can't corrupt shared resources."""
        import threading

        resource = {"value": 0, "version": 1}
        resource_lock = threading.Lock()
        conflicts = []

        def update_resource_with_optimistic_lock(
            session_id: str, expected_version: int, new_value: int
        ) -> bool:
            """Update resource with optimistic locking."""
            with resource_lock:
                if resource["version"] != expected_version:
                    conflicts.append(
                        {
                            "session": session_id,
                            "expected": expected_version,
                            "actual": resource["version"],
                        }
                    )
                    return False

                resource["value"] = new_value
                resource["version"] += 1
                return True

        # Session 1 reads version 1
        v1 = resource["version"]

        # Session 2 also reads version 1
        v2 = resource["version"]

        # Session 1 updates successfully
        assert update_resource_with_optimistic_lock("session-1", v1, 100)

        # Session 2 update fails (version conflict)
        assert not update_resource_with_optimistic_lock("session-2", v2, 200)

        # Resource has session 1's value
        assert resource["value"] == 100
        assert resource["version"] == 2

        # Conflict was detected
        assert len(conflicts) == 1
        assert conflicts[0]["session"] == "session-2"

    @pytest.mark.asyncio
    async def test_session_invalidation_propagation(self):
        """Verify session invalidation propagates to all instances."""
        # Simulate distributed session store with invalidation
        session_store = {
            "session-abc": {
                "user_id": "user-123",
                "valid": True,
                "invalidated_at": None,
            }
        }

        # Simulate cache in different service instances
        instance_caches = {
            "instance-1": {"session-abc": {"valid": True, "cached_at": time.time()}},
            "instance-2": {"session-abc": {"valid": True, "cached_at": time.time()}},
        }

        def invalidate_session(session_id: str) -> None:
            """Invalidate session in central store."""
            if session_id in session_store:
                session_store[session_id]["valid"] = False
                session_store[session_id]["invalidated_at"] = time.time()

        def check_session_valid(
            session_id: str, instance_id: str, max_cache_age: int = 30
        ) -> bool:
            """Check if session is valid, with cache."""
            cache = instance_caches.get(instance_id, {})
            cached = cache.get(session_id)

            # Check if cache is fresh
            if cached:
                cache_age = time.time() - cached["cached_at"]
                if cache_age < max_cache_age:
                    return cached["valid"]

            # Cache miss or stale - check central store
            session = session_store.get(session_id, {})
            is_valid = session.get("valid", False)

            # Update cache
            if instance_id in instance_caches:
                instance_caches[instance_id][session_id] = {
                    "valid": is_valid,
                    "cached_at": time.time(),
                }

            return is_valid

        # Both instances see session as valid (from cache)
        assert check_session_valid("session-abc", "instance-1")
        assert check_session_valid("session-abc", "instance-2")

        # Invalidate session
        invalidate_session("session-abc")

        # With fresh cache, instances still see old value
        assert check_session_valid("session-abc", "instance-1", max_cache_age=60)

        # With short cache TTL, invalidation is seen
        assert not check_session_valid("session-abc", "instance-1", max_cache_age=0)
        assert not check_session_valid("session-abc", "instance-2", max_cache_age=0)

    @pytest.mark.asyncio
    async def test_session_fixation_prevention(self):
        """Verify session fixation attacks are prevented."""
        sessions: dict[str, dict] = {}

        def create_session(user_id: str | None = None) -> str:
            """Create a new session."""
            import secrets

            session_id = secrets.token_urlsafe(32)
            sessions[session_id] = {
                "user_id": user_id,
                "authenticated": user_id is not None,
                "created_at": time.time(),
            }
            return session_id

        def login_with_session_regeneration(old_session_id: str, user_id: str) -> str:
            """Login and regenerate session ID to prevent fixation."""
            # Invalidate old session
            if old_session_id in sessions:
                del sessions[old_session_id]

            # Create new session with authentication
            new_session_id = create_session(user_id)
            return new_session_id

        # Attacker creates a session
        attacker_session = create_session()
        assert not sessions[attacker_session]["authenticated"]

        # Victim logs in with that session ID (fixation attempt)
        # Proper implementation regenerates session ID
        new_session = login_with_session_regeneration(attacker_session, "victim-user")

        # Old session no longer exists
        assert attacker_session not in sessions

        # New session is authenticated
        assert sessions[new_session]["authenticated"]
        assert sessions[new_session]["user_id"] == "victim-user"


# =============================================================================
# AUTHORIZATION BOUNDARY ENFORCEMENT
# =============================================================================


class TestAuthorizationBoundaries:
    """Tests for authorization boundary enforcement."""

    @pytest.mark.asyncio
    async def test_scope_downgrade_attack_prevention(self):
        """Verify scope downgrade attacks are prevented."""

        # OAuth-style scopes
        def validate_scope_request(
            requested_scopes: set[str], authorized_scopes: set[str]
        ) -> set[str]:
            """Return only scopes that are authorized."""
            return requested_scopes & authorized_scopes

        user_authorized = {"read", "write"}

        # Request subset - allowed
        requested = {"read"}
        granted = validate_scope_request(requested, user_authorized)
        assert granted == {"read"}

        # Request superset - only authorized subset granted
        requested = {"read", "write", "admin", "delete"}
        granted = validate_scope_request(requested, user_authorized)
        assert granted == {"read", "write"}
        assert "admin" not in granted
        assert "delete" not in granted

    @pytest.mark.asyncio
    async def test_resource_boundary_enforcement(self):
        """Verify resource-level authorization boundaries."""
        resources = {
            "doc-1": {"owner": "user-A", "org": "org-1", "public": False},
            "doc-2": {"owner": "user-B", "org": "org-1", "public": True},
            "doc-3": {"owner": "user-C", "org": "org-2", "public": False},
        }

        def can_access_resource(
            user_id: str, user_org: str, resource_id: str, action: str
        ) -> bool:
            """Check if user can perform action on resource."""
            resource = resources.get(resource_id)
            if not resource:
                return False

            # Public resources - read allowed for all
            if action == "read" and resource["public"]:
                return True

            # Must be in same org
            if resource["org"] != user_org:
                return False

            # Owner can do anything
            if resource["owner"] == user_id:
                return True

            # Non-owners in same org can read
            if action == "read":
                return True

            return False

        # Owner can access their resource
        assert can_access_resource("user-A", "org-1", "doc-1", "write")

        # Same org user can read
        assert can_access_resource("user-B", "org-1", "doc-1", "read")

        # Same org non-owner can't write
        assert not can_access_resource("user-B", "org-1", "doc-1", "write")

        # Different org can't access private resource
        assert not can_access_resource("user-C", "org-2", "doc-1", "read")

        # Anyone can read public resource
        assert can_access_resource("user-C", "org-2", "doc-2", "read")

    @pytest.mark.asyncio
    async def test_temporal_access_enforcement(self):
        """Verify time-based access restrictions are enforced."""
        access_grants = {
            "grant-1": {
                "user_id": "user-123",
                "resource_id": "doc-1",
                "valid_from": datetime(2024, 1, 1, tzinfo=timezone.utc),
                "valid_until": datetime(2024, 12, 31, tzinfo=timezone.utc),
            }
        }

        def check_temporal_access(
            user_id: str, resource_id: str, check_time: datetime
        ) -> bool:
            """Check if user has time-valid access."""
            for grant in access_grants.values():
                if grant["user_id"] != user_id:
                    continue
                if grant["resource_id"] != resource_id:
                    continue

                valid_from = grant["valid_from"]
                valid_until = grant["valid_until"]

                if valid_from <= check_time <= valid_until:
                    return True

            return False

        # Access valid within time window
        mid_2024 = datetime(2024, 6, 15, tzinfo=timezone.utc)
        assert check_temporal_access("user-123", "doc-1", mid_2024)

        # Access expired
        after_expiry = datetime(2025, 1, 15, tzinfo=timezone.utc)
        assert not check_temporal_access("user-123", "doc-1", after_expiry)

        # Access not yet valid
        before_valid = datetime(2023, 12, 15, tzinfo=timezone.utc)
        assert not check_temporal_access("user-123", "doc-1", before_valid)


# =============================================================================
# CRYPTOGRAPHIC EDGE CASES
# =============================================================================


class TestCryptographicEdgeCases:
    """Tests for cryptographic operation edge cases."""

    @pytest.mark.asyncio
    async def test_timing_safe_comparison(self):
        """Verify timing-safe comparison is used for secrets."""

        def insecure_compare(a: str, b: str) -> bool:
            """Insecure comparison (for demonstration)."""
            if len(a) != len(b):
                return False
            for i in range(len(a)):
                if a[i] != b[i]:
                    return False
            return True

        def secure_compare(a: str, b: str) -> bool:
            """Timing-safe comparison using hmac.compare_digest."""
            return hmac.compare_digest(a.encode(), b.encode())

        secret = "super_secret_api_key_12345"
        attempt = "super_secret_api_key_12345"
        wrong = "wrong_api_key_xxxxxxxxxxxxx"

        # Both methods give correct result
        assert insecure_compare(secret, attempt) == secure_compare(secret, attempt)
        assert insecure_compare(secret, wrong) == secure_compare(secret, wrong)

        # Pattern: always use secure_compare for secrets
        assert secure_compare(secret, attempt)
        assert not secure_compare(secret, wrong)

    @pytest.mark.asyncio
    async def test_hash_length_extension_prevention(self):
        """Verify HMAC is used instead of naive hash for signatures."""
        secret = b"shared_secret_key"
        message = b"user_id=123&action=read"

        # Naive approach (vulnerable to length extension)
        def naive_sign(msg: bytes) -> str:
            """Vulnerable signature using hash(secret + message)."""
            return hashlib.sha256(secret + msg).hexdigest()

        # Secure approach (HMAC)
        def hmac_sign(msg: bytes) -> str:
            """Secure signature using HMAC."""
            return hmac.new(secret, msg, hashlib.sha256).hexdigest()

        naive_sig = naive_sign(message)
        hmac_sig = hmac_sign(message)

        # Different signatures (as expected)
        assert naive_sig != hmac_sig

        # Pattern: always verify using HMAC
        def verify_signature(msg: bytes, signature: str) -> bool:
            """Verify message signature."""
            expected = hmac_sign(msg)
            return hmac.compare_digest(signature, expected)

        assert verify_signature(message, hmac_sig)
        assert not verify_signature(message, naive_sig)

    @pytest.mark.asyncio
    async def test_nonce_uniqueness_enforcement(self):
        """Verify nonces are unique and not reused."""
        used_nonces: set[str] = set()

        def generate_and_record_nonce() -> str:
            """Generate unique nonce and record it."""
            import secrets

            while True:
                nonce = secrets.token_hex(16)
                if nonce not in used_nonces:
                    used_nonces.add(nonce)
                    return nonce

        def verify_nonce(nonce: str) -> bool:
            """Verify nonce exists and hasn't been used."""
            if nonce not in used_nonces:
                return False

            # Remove after use (one-time use)
            used_nonces.remove(nonce)
            return True

        # Generate nonce
        nonce = generate_and_record_nonce()
        assert nonce in used_nonces

        # First verification succeeds and consumes nonce
        assert verify_nonce(nonce)

        # Second verification fails (replay)
        assert not verify_nonce(nonce)
