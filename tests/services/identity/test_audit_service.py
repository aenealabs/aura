"""
Project Aura - Identity Audit Service Tests

Tests for the identity audit logging service.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from src.services.identity.audit_service import IdentityAuditService, get_audit_service
from src.services.identity.models import AuthAction


class TestIdentityAuditService:
    """Tests for IdentityAuditService."""

    @pytest.fixture
    def mock_dynamodb(self):
        """Create mock DynamoDB resource."""
        mock_resource = MagicMock()
        mock_table = MagicMock()
        mock_resource.Table.return_value = mock_table
        return mock_resource, mock_table

    @pytest.fixture
    def audit_service(self, mock_dynamodb):
        """Create audit service with mocked DynamoDB."""
        mock_resource, _ = mock_dynamodb
        return IdentityAuditService(
            table_name="test-audit-logs",
            dynamodb_client=mock_resource,
            ttl_days=90,
        )

    @pytest.mark.asyncio
    async def test_log_event_success(self, audit_service, mock_dynamodb):
        """Test logging a basic event."""
        _, mock_table = mock_dynamodb
        mock_table.put_item.return_value = {}

        entry = await audit_service.log_event(
            action=AuthAction.AUTH_SUCCESS,
            idp_id="idp-123",
            organization_id="org-456",
            target_user_id="user-789",
            success=True,
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
        )

        assert entry.action_type == "auth_success"
        assert entry.idp_id == "idp-123"
        assert entry.organization_id == "org-456"
        assert entry.success is True
        assert entry.ip_address == "192.168.1.100"
        assert entry.audit_id is not None
        assert entry.timestamp != ""
        mock_table.put_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_event_with_details(self, audit_service, mock_dynamodb):
        """Test logging event with additional details."""
        _, mock_table = mock_dynamodb
        mock_table.put_item.return_value = {}

        entry = await audit_service.log_event(
            action=AuthAction.CONFIG_UPDATE,
            idp_id="idp-123",
            organization_id="org-456",
            actor_id="admin-user",
            success=True,
            details={"field_changed": "name", "old_value": "Old", "new_value": "New"},
        )

        assert entry.actor_id == "admin-user"
        assert entry.details["field_changed"] == "name"

    @pytest.mark.asyncio
    async def test_log_event_failure(self, audit_service, mock_dynamodb):
        """Test logging a failed event."""
        _, mock_table = mock_dynamodb
        mock_table.put_item.return_value = {}

        entry = await audit_service.log_event(
            action=AuthAction.AUTH_FAILURE,
            idp_id="idp-123",
            organization_id="org-456",
            success=False,
            error_message="Invalid password",
        )

        assert entry.success is False
        assert entry.error_message == "Invalid password"

    @pytest.mark.asyncio
    async def test_log_event_ttl_calculation(self, audit_service, mock_dynamodb):
        """Test TTL is correctly calculated."""
        _, mock_table = mock_dynamodb
        mock_table.put_item.return_value = {}

        entry = await audit_service.log_event(
            action=AuthAction.AUTH_SUCCESS,
            idp_id="idp-123",
            organization_id="org-456",
        )

        # TTL should be ~90 days from now
        now = datetime.now(timezone.utc)
        expected_ttl_min = int((now + timedelta(days=89)).timestamp())
        expected_ttl_max = int((now + timedelta(days=91)).timestamp())

        assert expected_ttl_min <= entry.ttl <= expected_ttl_max

    @pytest.mark.asyncio
    async def test_log_event_dynamodb_error_silent(self, audit_service, mock_dynamodb):
        """Test DynamoDB errors don't propagate (audit shouldn't break auth)."""
        _, mock_table = mock_dynamodb
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ServiceUnavailable"}},
            "PutItem",
        )

        # Should not raise - audit failures are logged but not propagated
        entry = await audit_service.log_event(
            action=AuthAction.AUTH_SUCCESS,
            idp_id="idp-123",
            organization_id="org-456",
        )

        # Entry is still returned (just not persisted)
        assert entry is not None
        assert entry.audit_id is not None

    @pytest.mark.asyncio
    async def test_log_auth_success(self, audit_service, mock_dynamodb):
        """Test convenience method for successful auth."""
        _, mock_table = mock_dynamodb
        mock_table.put_item.return_value = {}

        entry = await audit_service.log_auth_success(
            idp_id="idp-123",
            organization_id="org-456",
            user_id="user-789",
            email="user@example.com",
            ip_address="10.0.0.1",
        )

        assert entry.action_type == "auth_success"
        assert entry.target_user_id == "user-789"
        assert entry.success is True
        assert entry.details["email"] == "user@example.com"

    @pytest.mark.asyncio
    async def test_log_auth_failure(self, audit_service, mock_dynamodb):
        """Test convenience method for failed auth."""
        _, mock_table = mock_dynamodb
        mock_table.put_item.return_value = {}

        entry = await audit_service.log_auth_failure(
            idp_id="idp-123",
            organization_id="org-456",
            username="john.doe",
            error="Account locked",
            ip_address="10.0.0.1",
        )

        assert entry.action_type == "auth_failure"
        assert entry.success is False
        assert entry.error_message == "Account locked"
        assert entry.details["username"] == "john.doe"

    @pytest.mark.asyncio
    async def test_log_config_change(self, audit_service, mock_dynamodb):
        """Test logging config changes."""
        _, mock_table = mock_dynamodb
        mock_table.put_item.return_value = {}

        entry = await audit_service.log_config_change(
            action=AuthAction.CONFIG_CREATE,
            idp_id="idp-new-123",
            organization_id="org-456",
            actor_id="admin-user",
            changes={"created": True, "idp_type": "ldap"},
        )

        assert entry.action_type == "config_create"
        assert entry.actor_id == "admin-user"
        assert entry.details["changes"]["idp_type"] == "ldap"

    @pytest.mark.asyncio
    async def test_get_audit_logs_by_idp(self, audit_service, mock_dynamodb):
        """Test querying audit logs by IdP."""
        _, mock_table = mock_dynamodb
        mock_table.query.return_value = {
            "Items": [
                {
                    "audit_id": "audit-1",
                    "idp_id": "idp-123",
                    "organization_id": "org-456",
                    "action_type": "auth_success",
                    "timestamp": "2026-01-06T10:00:00Z",
                    "success": True,
                },
                {
                    "audit_id": "audit-2",
                    "idp_id": "idp-123",
                    "organization_id": "org-456",
                    "action_type": "auth_failure",
                    "timestamp": "2026-01-06T11:00:00Z",
                    "success": False,
                },
            ]
        }

        entries = await audit_service.get_audit_logs(idp_id="idp-123")

        assert len(entries) == 2
        assert entries[0].audit_id == "audit-1"
        assert entries[1].audit_id == "audit-2"
        mock_table.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_audit_logs_by_organization(self, audit_service, mock_dynamodb):
        """Test querying audit logs by organization."""
        _, mock_table = mock_dynamodb
        mock_table.query.return_value = {
            "Items": [
                {
                    "audit_id": "audit-1",
                    "idp_id": "idp-123",
                    "organization_id": "org-456",
                    "action_type": "config_update",
                    "timestamp": "2026-01-06T10:00:00Z",
                    "success": True,
                },
            ]
        }

        entries = await audit_service.get_audit_logs(organization_id="org-456")

        assert len(entries) == 1
        mock_table.query.assert_called_once()
        # Should use organization-timestamp-index
        call_args = mock_table.query.call_args
        assert call_args.kwargs["IndexName"] == "organization-timestamp-index"

    @pytest.mark.asyncio
    async def test_get_audit_logs_with_time_range(self, audit_service, mock_dynamodb):
        """Test querying audit logs with time range."""
        _, mock_table = mock_dynamodb
        mock_table.query.return_value = {"Items": []}

        start_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end_time = datetime(2026, 1, 31, tzinfo=timezone.utc)

        await audit_service.get_audit_logs(
            idp_id="idp-123",
            start_time=start_time,
            end_time=end_time,
        )

        call_args = mock_table.query.call_args
        assert ":start" in call_args.kwargs["ExpressionAttributeValues"]
        assert ":end" in call_args.kwargs["ExpressionAttributeValues"]

    @pytest.mark.asyncio
    async def test_get_audit_logs_filter_by_action(self, audit_service, mock_dynamodb):
        """Test filtering audit logs by action type."""
        _, mock_table = mock_dynamodb
        mock_table.query.return_value = {
            "Items": [
                {
                    "audit_id": "audit-1",
                    "idp_id": "idp-123",
                    "organization_id": "org-456",
                    "action_type": "auth_success",
                    "timestamp": "2026-01-06T10:00:00Z",
                    "success": True,
                },
                {
                    "audit_id": "audit-2",
                    "idp_id": "idp-123",
                    "organization_id": "org-456",
                    "action_type": "auth_failure",
                    "timestamp": "2026-01-06T11:00:00Z",
                    "success": False,
                },
            ]
        }

        entries = await audit_service.get_audit_logs(
            idp_id="idp-123",
            action_type=AuthAction.AUTH_SUCCESS,
        )

        # Only auth_success entries should be returned
        assert len(entries) == 1
        assert entries[0].action_type == "auth_success"

    @pytest.mark.asyncio
    async def test_get_audit_logs_with_limit(self, audit_service, mock_dynamodb):
        """Test limiting audit log results."""
        _, mock_table = mock_dynamodb
        mock_table.query.return_value = {"Items": []}

        await audit_service.get_audit_logs(
            idp_id="idp-123",
            limit=50,
        )

        call_args = mock_table.query.call_args
        assert call_args.kwargs["Limit"] == 50

    @pytest.mark.asyncio
    async def test_get_audit_logs_scan_fallback(self, audit_service, mock_dynamodb):
        """Test scan fallback when no idp_id or org_id provided."""
        _, mock_table = mock_dynamodb
        mock_table.scan.return_value = {
            "Items": [
                {
                    "audit_id": "audit-1",
                    "idp_id": "idp-123",
                    "organization_id": "org-456",
                    "action_type": "auth_success",
                    "timestamp": "2026-01-06T10:00:00Z",
                }
            ]
        }

        entries = await audit_service.get_audit_logs(limit=10)

        # Should use scan
        mock_table.scan.assert_called_once()
        mock_table.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_audit_logs_error(self, audit_service, mock_dynamodb):
        """Test error handling when query fails."""
        _, mock_table = mock_dynamodb
        mock_table.query.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException"}},
            "Query",
        )

        with pytest.raises(ClientError):
            await audit_service.get_audit_logs(idp_id="idp-123")


class TestAuditServiceSingleton:
    """Tests for audit service singleton."""

    def test_get_audit_service_creates_instance(self):
        """Test singleton creation."""
        import src.services.identity.audit_service as module

        original = module._audit_service
        try:
            module._audit_service = None
            with patch("boto3.resource"):
                service = get_audit_service()
                assert service is not None
                assert isinstance(service, IdentityAuditService)
        finally:
            module._audit_service = original

    def test_get_audit_service_returns_same_instance(self):
        """Test singleton returns same instance."""
        import src.services.identity.audit_service as module

        original = module._audit_service
        try:
            module._audit_service = None
            with patch("boto3.resource"):
                service1 = get_audit_service()
                service2 = get_audit_service()
                assert service1 is service2
        finally:
            module._audit_service = original


class TestAuditServiceConfiguration:
    """Tests for audit service configuration."""

    def test_default_ttl(self):
        """Test default TTL is 90 days."""
        with patch("boto3.resource"):
            service = IdentityAuditService(table_name="test")
            assert service.ttl_days == 90

    def test_custom_ttl(self):
        """Test custom TTL setting."""
        with patch("boto3.resource"):
            service = IdentityAuditService(table_name="test", ttl_days=365)
            assert service.ttl_days == 365

    def test_default_table_name(self):
        """Test default table name from environment."""
        with patch("boto3.resource"):
            with patch.dict("os.environ", {"IDP_AUDIT_TABLE": "custom-audit-table"}):
                service = IdentityAuditService()
                assert service.table_name == "custom-audit-table"

    def test_explicit_table_name(self):
        """Test explicit table name overrides environment."""
        with patch("boto3.resource"):
            with patch.dict("os.environ", {"IDP_AUDIT_TABLE": "env-table"}):
                service = IdentityAuditService(table_name="explicit-table")
                assert service.table_name == "explicit-table"


class TestAuditLogEntry:
    """Tests for audit log entry creation and serialization."""

    @pytest.fixture
    def mock_dynamodb(self):
        """Create mock DynamoDB resource."""
        mock_resource = MagicMock()
        mock_table = MagicMock()
        mock_resource.Table.return_value = mock_table
        return mock_resource, mock_table

    @pytest.fixture
    def audit_service(self, mock_dynamodb):
        """Create audit service with mocked DynamoDB."""
        mock_resource, _ = mock_dynamodb
        return IdentityAuditService(
            table_name="test-audit-logs",
            dynamodb_client=mock_resource,
        )

    @pytest.mark.asyncio
    async def test_entry_has_uuid(self, audit_service, mock_dynamodb):
        """Test each entry gets a unique UUID."""
        _, mock_table = mock_dynamodb
        mock_table.put_item.return_value = {}

        entry1 = await audit_service.log_event(
            action=AuthAction.AUTH_SUCCESS,
            idp_id="idp-123",
            organization_id="org-456",
        )
        entry2 = await audit_service.log_event(
            action=AuthAction.AUTH_SUCCESS,
            idp_id="idp-123",
            organization_id="org-456",
        )

        assert entry1.audit_id != entry2.audit_id
        # Should be valid UUIDs
        assert len(entry1.audit_id) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_entry_has_iso_timestamp(self, audit_service, mock_dynamodb):
        """Test entry timestamp is ISO format."""
        _, mock_table = mock_dynamodb
        mock_table.put_item.return_value = {}

        entry = await audit_service.log_event(
            action=AuthAction.AUTH_SUCCESS,
            idp_id="idp-123",
            organization_id="org-456",
        )

        # Should be parseable as ISO timestamp
        parsed = datetime.fromisoformat(entry.timestamp.replace("Z", "+00:00"))
        assert parsed is not None

    @pytest.mark.asyncio
    async def test_dynamodb_item_format(self, audit_service, mock_dynamodb):
        """Test the DynamoDB item format is correct."""
        _, mock_table = mock_dynamodb
        mock_table.put_item.return_value = {}

        await audit_service.log_event(
            action=AuthAction.CONFIG_UPDATE,
            idp_id="idp-123",
            organization_id="org-456",
            actor_id="admin",
            success=True,
            details={"field": "name"},
        )

        call_args = mock_table.put_item.call_args
        item = call_args.kwargs["Item"]

        assert "audit_id" in item
        assert "idp_id" in item
        assert "organization_id" in item
        assert "action_type" in item
        assert "timestamp" in item
        assert "success" in item
        assert "actor_id" in item
        assert "details" in item
        assert "ttl" in item
