"""
Tests for Credential Enumerator Registry and Enumerators (ADR-086 Phase 1).

Covers the EnumeratorRegistry, CredentialRecord/EnumerationResult contracts,
all 15 concrete enumerators, and bulk registration.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.services.runtime_security.discovery.credential_enumerators import (
    CredentialEnumerator,
    CredentialRecord,
    CredentialStatus,
    EnumerationResult,
    EnumeratorRegistry,
    get_enumerator_registry,
    reset_enumerator_registry,
)
from src.services.runtime_security.discovery.credential_enumerators.enumerators import (
    ALL_ENUMERATOR_CLASSES,
    AccessKeyEnumerator,
    BaselineRecordEnumerator,
    BedrockSessionEnumerator,
    CapabilityGrantEnumerator,
    GitHubOAuthEnumerator,
    GitLabOAuthEnumerator,
    IAMRoleEnumerator,
    IntegrationHubEnumerator,
    MCPTokenEnumerator,
    OAuthRefreshTokenEnumerator,
    PalantirAIPTokenEnumerator,
    ProvenanceRecordEnumerator,
    ReMemGrantEnumerator,
    SSMParameterEnumerator,
    SecretsManagerEnumerator,
    register_all_enumerators,
)


# ---------------------------------------------------------------------------
# CredentialRecord
# ---------------------------------------------------------------------------


class TestCredentialRecord:
    """Tests for CredentialRecord frozen dataclass."""

    def test_create(self):
        cr = CredentialRecord(
            credential_class="aws_iam_roles",
            credential_id="role-123",
            agent_id="agent-1",
            status=CredentialStatus.ACTIVE,
        )
        assert cr.is_active is True
        assert cr.credential_class == "aws_iam_roles"

    def test_is_active_for_revoked(self):
        cr = CredentialRecord(
            credential_class="test",
            credential_id="id",
            agent_id="a1",
            status=CredentialStatus.REVOKED,
        )
        assert cr.is_active is False

    def test_to_dict(self):
        cr = CredentialRecord(
            credential_class="test",
            credential_id="id",
            agent_id="a1",
            status=CredentialStatus.ACTIVE,
            description="test credential",
        )
        d = cr.to_dict()
        assert d["credential_class"] == "test"
        assert d["status"] == "active"
        assert d["description"] == "test credential"

    def test_frozen(self):
        cr = CredentialRecord(
            credential_class="test",
            credential_id="id",
            agent_id="a1",
            status=CredentialStatus.ACTIVE,
        )
        with pytest.raises(AttributeError):
            cr.status = CredentialStatus.REVOKED


# ---------------------------------------------------------------------------
# EnumerationResult
# ---------------------------------------------------------------------------


class TestEnumerationResult:
    """Tests for EnumerationResult."""

    def test_zero_confirmed(self):
        r = EnumerationResult(
            credential_class="test",
            agent_id="a1",
            zero_confirmed=True,
        )
        assert r.active_count == 0
        assert r.needs_remediation is False

    def test_needs_remediation(self):
        cr = CredentialRecord(
            credential_class="test",
            credential_id="id",
            agent_id="a1",
            status=CredentialStatus.ACTIVE,
        )
        r = EnumerationResult(
            credential_class="test",
            agent_id="a1",
            credentials=[cr],
        )
        assert r.active_count == 1
        assert r.needs_remediation is True

    def test_mixed_credentials(self):
        active = CredentialRecord(
            credential_class="test",
            credential_id="id1",
            agent_id="a1",
            status=CredentialStatus.ACTIVE,
        )
        revoked = CredentialRecord(
            credential_class="test",
            credential_id="id2",
            agent_id="a1",
            status=CredentialStatus.REVOKED,
        )
        r = EnumerationResult(
            credential_class="test",
            agent_id="a1",
            credentials=[active, revoked],
        )
        assert r.active_count == 1

    def test_to_dict(self):
        r = EnumerationResult(
            credential_class="test",
            agent_id="a1",
            zero_confirmed=True,
        )
        d = r.to_dict()
        assert d["zero_confirmed"] is True
        assert d["credential_class"] == "test"


# ---------------------------------------------------------------------------
# EnumeratorRegistry
# ---------------------------------------------------------------------------


class TestEnumeratorRegistry:
    """Tests for EnumeratorRegistry."""

    def setup_method(self):
        self.registry = EnumeratorRegistry()

    def test_register_and_get(self):
        enum = IAMRoleEnumerator()
        self.registry.register(enum)
        assert self.registry.get("aws_iam_roles") is enum

    def test_unregister(self):
        enum = IAMRoleEnumerator()
        self.registry.register(enum)
        assert self.registry.unregister("aws_iam_roles") is True
        assert self.registry.get("aws_iam_roles") is None

    def test_unregister_nonexistent(self):
        assert self.registry.unregister("nonexistent") is False

    def test_list_classes(self):
        self.registry.register(IAMRoleEnumerator())
        self.registry.register(MCPTokenEnumerator())
        classes = self.registry.list_classes()
        assert "aws_iam_roles" in classes
        assert "mcp_tokens" in classes

    def test_count(self):
        assert self.registry.count == 0
        self.registry.register(IAMRoleEnumerator())
        assert self.registry.count == 1

    def test_enumerate_all_no_client(self):
        """Enumerators with no client return zero_confirmed."""
        self.registry.register(IAMRoleEnumerator())
        self.registry.register(MCPTokenEnumerator())
        results = self.registry.enumerate_all("agent-1")
        assert len(results) == 2
        assert all(r.zero_confirmed for r in results)

    def test_enumerate_all_with_error(self):
        """Enumerator errors are captured, not raised."""
        mock_client = MagicMock()
        mock_client.list_roles_for_agent.side_effect = RuntimeError("boom")
        enum = IAMRoleEnumerator(client=mock_client)
        self.registry.register(enum)
        results = self.registry.enumerate_all("agent-1")
        assert len(results) == 1
        assert results[0].error is not None

    def test_all_zero_confirmed_true(self):
        results = [
            EnumerationResult(credential_class="a", agent_id="x", zero_confirmed=True),
            EnumerationResult(credential_class="b", agent_id="x", zero_confirmed=True),
        ]
        assert self.registry.all_zero_confirmed(results) is True

    def test_all_zero_confirmed_false_with_active(self):
        results = [
            EnumerationResult(credential_class="a", agent_id="x", zero_confirmed=True),
            EnumerationResult(credential_class="b", agent_id="x", zero_confirmed=False),
        ]
        assert self.registry.all_zero_confirmed(results) is False

    def test_all_zero_confirmed_false_with_error(self):
        results = [
            EnumerationResult(
                credential_class="a", agent_id="x",
                zero_confirmed=True, error="oops",
            ),
        ]
        assert self.registry.all_zero_confirmed(results) is False

    def test_all_zero_confirmed_empty(self):
        assert self.registry.all_zero_confirmed([]) is False


# ---------------------------------------------------------------------------
# Concrete Enumerators
# ---------------------------------------------------------------------------


class TestConcreteEnumerators:
    """Tests for all 15 concrete enumerator classes."""

    def test_all_15_enumerator_classes_exist(self):
        assert len(ALL_ENUMERATOR_CLASSES) == 15

    def test_unique_credential_classes(self):
        classes = [cls.credential_class for cls in ALL_ENUMERATOR_CLASSES]
        assert len(set(classes)) == 15

    @pytest.mark.parametrize("cls", ALL_ENUMERATOR_CLASSES)
    def test_enumerator_no_client_returns_zero(self, cls):
        """Each enumerator with no client returns zero_confirmed."""
        enum = cls()
        result = enum.enumerate("test-agent")
        assert result.zero_confirmed is True
        assert result.active_count == 0
        assert result.credential_class == cls.credential_class

    @pytest.mark.parametrize("cls", ALL_ENUMERATOR_CLASSES)
    def test_enumerator_implements_protocol(self, cls):
        """Each enumerator satisfies CredentialEnumerator protocol."""
        enum = cls()
        assert isinstance(enum, CredentialEnumerator)

    def test_iam_role_with_results(self):
        mock_client = MagicMock()
        mock_client.list_roles_for_agent.return_value = [
            {"role_arn": "arn:aws:iam::123:role/test", "role_name": "test"},
        ]
        enum = IAMRoleEnumerator(client=mock_client)
        result = enum.enumerate("agent-1")
        assert result.active_count == 1
        assert result.zero_confirmed is False
        assert result.credentials[0].credential_id == "arn:aws:iam::123:role/test"

    def test_access_key_with_error(self):
        mock_client = MagicMock()
        mock_client.list_access_keys_for_agent.side_effect = Exception("fail")
        enum = AccessKeyEnumerator(client=mock_client)
        result = enum.enumerate("agent-1")
        assert result.error is not None
        assert result.zero_confirmed is False


# ---------------------------------------------------------------------------
# Bulk registration
# ---------------------------------------------------------------------------


class TestBulkRegistration:
    """Tests for register_all_enumerators."""

    def test_register_all(self):
        registry = EnumeratorRegistry()
        register_all_enumerators(registry=registry)
        assert registry.count == 15

    def test_register_all_with_clients(self):
        registry = EnumeratorRegistry()
        mock_client = MagicMock()
        register_all_enumerators(
            registry=registry,
            clients={"aws_iam_roles": mock_client},
        )
        iam_enum = registry.get("aws_iam_roles")
        assert iam_enum._client is mock_client


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


class TestEnumeratorRegistrySingleton:
    """Tests for singleton lifecycle."""

    def setup_method(self):
        reset_enumerator_registry()

    def teardown_method(self):
        reset_enumerator_registry()

    def test_singleton(self):
        r1 = get_enumerator_registry()
        r2 = get_enumerator_registry()
        assert r1 is r2

    def test_reset(self):
        r1 = get_enumerator_registry()
        reset_enumerator_registry()
        r2 = get_enumerator_registry()
        assert r1 is not r2
