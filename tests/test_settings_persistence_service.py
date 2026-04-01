"""
Tests for Settings Persistence Service.

Tests DynamoDB-backed settings storage including:
- CRUD operations
- Caching
- Fallback mode
- Audit logging
- Bulk operations
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.services.settings_persistence_service import (
    DEFAULT_PLATFORM_SETTINGS,
    AuditLogEntry,
    SettingsPersistenceService,
    SettingsRecord,
    create_settings_service,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def service():
    """Create a settings persistence service for testing."""
    return SettingsPersistenceService(
        table_name="test-settings",
        region="us-east-1",
        enable_cache=True,
        cache_ttl_seconds=60,
    )


@pytest.fixture
def service_no_cache():
    """Create a service with caching disabled."""
    return SettingsPersistenceService(
        table_name="test-settings",
        enable_cache=False,
    )


@pytest.fixture
def mock_dynamodb_table():
    """Create a mock DynamoDB table."""
    mock_table = MagicMock()
    mock_table.get_item.return_value = {}
    mock_table.put_item.return_value = {}
    mock_table.delete_item.return_value = {}
    return mock_table


@pytest.fixture
def mock_dynamodb_resource(mock_dynamodb_table):
    """Create a mock DynamoDB resource."""
    mock_resource = MagicMock()
    mock_resource.Table.return_value = mock_dynamodb_table
    return mock_resource


# =============================================================================
# Initialization Tests
# =============================================================================


class TestServiceInitialization:
    """Test service initialization."""

    def test_default_initialization(self):
        """Test default initialization values."""
        service = SettingsPersistenceService()
        assert service.region == "us-east-1"
        assert "platform-settings" in service.table_name
        assert service.enable_cache is True
        assert not service._fallback_mode

    def test_custom_initialization(self, service):
        """Test custom initialization."""
        assert service.table_name == "test-settings"
        assert service.region == "us-east-1"
        assert service.enable_cache is True
        assert service.cache_ttl_seconds == 60

    def test_factory_function(self):
        """Test create_settings_service factory."""
        service = create_settings_service(
            table_name="custom-table",
            region="us-west-2",
            enable_cache=False,
        )
        assert service.table_name == "custom-table"
        assert service.region == "us-west-2"
        assert service.enable_cache is False


# =============================================================================
# Fallback Mode Tests (No DynamoDB)
# =============================================================================


class TestFallbackMode:
    """Test in-memory fallback mode."""

    @pytest.mark.asyncio
    async def test_get_default_when_not_set(self, service):
        """Test getting default values when no settings exist."""
        service._fallback_mode = True

        value = await service.get_setting("platform", "hitl")
        assert value is not None
        assert "require_approval_for_patches" in value

    @pytest.mark.asyncio
    async def test_set_and_get_in_memory(self, service):
        """Test setting and getting values in fallback mode."""
        service._fallback_mode = True

        test_value = {"custom_key": "custom_value"}
        await service.update_setting("platform", "custom", test_value)

        result = await service.get_setting("platform", "custom")
        assert result == test_value

    @pytest.mark.asyncio
    async def test_delete_in_memory(self, service):
        """Test deleting values in fallback mode."""
        service._fallback_mode = True

        await service.update_setting("platform", "test", {"key": "value"})
        await service.delete_setting("platform", "test")

        result = await service.get_setting("platform", "test", default=None)
        # Should return default platform settings if key matches
        assert result is None or result == {}


# =============================================================================
# Caching Tests
# =============================================================================


class TestCaching:
    """Test caching functionality."""

    @pytest.mark.asyncio
    async def test_cache_hit(self, service):
        """Test cache hit returns cached value."""
        service._fallback_mode = True

        # Set value and get it (populates cache)
        await service.update_setting("platform", "test", {"value": 1})
        result1 = await service.get_setting("platform", "test")
        assert result1["value"] == 1

        # Directly modify in-memory store (simulating external change)
        # But DON'T invalidate cache
        service._in_memory_store["platform"]["test"] = {"value": 2}

        # Manually set cache with original value to ensure cache hit
        import time

        cache_key = service._cache_key("platform", "test")
        service._cache[cache_key] = (time.time(), {"value": 1})

        # Second call should return cached value
        result2 = await service.get_setting("platform", "test")
        assert result2["value"] == 1  # Cached value, not in-memory value

    @pytest.mark.asyncio
    async def test_cache_invalidation_on_update(self, service):
        """Test cache is invalidated on update."""
        service._fallback_mode = True

        await service.update_setting("platform", "test", {"value": 1})
        await service.get_setting("platform", "test")  # Populate cache

        # Update should invalidate cache
        await service.update_setting("platform", "test", {"value": 2})

        result = await service.get_setting("platform", "test")
        assert result["value"] == 2  # New value

    def test_clear_cache(self, service):
        """Test clearing all cached entries."""
        # Add some entries to cache
        service._cache["key1"] = (0, {"val": 1})
        service._cache["key2"] = (0, {"val": 2})

        service.clear_cache()
        assert len(service._cache) == 0

    @pytest.mark.asyncio
    async def test_no_caching_when_disabled(self, service_no_cache):
        """Test caching is skipped when disabled."""
        service_no_cache._fallback_mode = True

        await service_no_cache.update_setting("platform", "test", {"value": 1})
        await service_no_cache.get_setting("platform", "test")

        # Cache should be empty
        assert len(service_no_cache._cache) == 0


# =============================================================================
# CRUD Operations Tests
# =============================================================================


class TestCRUDOperations:
    """Test CRUD operations."""

    @pytest.mark.asyncio
    async def test_update_creates_new(self, service):
        """Test update creates new setting if not exists."""
        service._fallback_mode = True

        result = await service.update_setting(
            "platform",
            "new_setting",
            {"key": "value"},
            updated_by="test_user",
        )

        assert result is True
        stored = await service.get_setting("platform", "new_setting")
        assert stored["key"] == "value"

    @pytest.mark.asyncio
    async def test_update_modifies_existing(self, service):
        """Test update modifies existing setting."""
        service._fallback_mode = True

        await service.update_setting("platform", "test", {"v": 1})
        await service.update_setting("platform", "test", {"v": 2})

        result = await service.get_setting("platform", "test")
        assert result["v"] == 2

    @pytest.mark.asyncio
    async def test_delete_removes_setting(self, service):
        """Test delete removes the setting."""
        service._fallback_mode = True

        await service.update_setting("platform", "to_delete", {"val": 1})
        await service.delete_setting("platform", "to_delete")

        result = await service.get_setting("platform", "to_delete", default="deleted")
        assert result == "deleted"

    @pytest.mark.asyncio
    async def test_get_with_custom_default(self, service):
        """Test get returns custom default when not found."""
        service._fallback_mode = True

        result = await service.get_setting(
            "custom_type", "nonexistent", default={"fallback": True}
        )
        assert result["fallback"] is True


# =============================================================================
# Bulk Operations Tests
# =============================================================================


class TestBulkOperations:
    """Test bulk operations."""

    @pytest.mark.asyncio
    async def test_get_all_platform_settings(self, service):
        """Test getting all platform settings."""
        service._fallback_mode = True

        # Set some values
        await service.update_setting("platform", "hitl", {"custom": True})

        settings = await service.get_all_platform_settings()

        assert "integration_mode" in settings
        assert "hitl" in settings
        assert "mcp" in settings
        assert "security" in settings
        # Custom value should be present
        assert settings["hitl"].get("custom") is True

    @pytest.mark.asyncio
    async def test_update_all_platform_settings(self, service):
        """Test updating all platform settings."""
        service._fallback_mode = True

        new_settings = {
            "integration_mode": {"mode": "enterprise"},
            "hitl": {"require_approval_for_patches": False},
            "mcp": {"enabled": True},
            "security": {"audit_all_actions": False},
        }

        result = await service.update_all_platform_settings(
            new_settings, updated_by="admin"
        )
        assert result is True

        # Verify all were updated
        settings = await service.get_all_platform_settings()
        assert settings["integration_mode"]["mode"] == "enterprise"
        assert settings["hitl"]["require_approval_for_patches"] is False
        assert settings["mcp"]["enabled"] is True

    @pytest.mark.asyncio
    async def test_initialize_defaults(self, service):
        """Test initializing default settings."""
        service._fallback_mode = True

        # Clear any existing settings first
        service._in_memory_store.clear()
        service.clear_cache()

        count = await service.initialize_defaults()

        assert (
            count == 6
        )  # integration_mode, hitl, mcp, security, compliance, orchestrator

        # Verify defaults are set
        settings = await service.get_all_platform_settings()
        assert settings["integration_mode"]["mode"] == "defense"

    @pytest.mark.asyncio
    async def test_initialize_defaults_no_overwrite(self, service):
        """Test initialize_defaults doesn't overwrite existing."""
        service._fallback_mode = True

        # Set custom value
        await service.update_setting("platform", "integration_mode", {"mode": "custom"})

        _count = await service.initialize_defaults(force=False)

        # Should only initialize missing keys
        settings = await service.get_all_platform_settings()
        assert settings["integration_mode"]["mode"] == "custom"


# =============================================================================
# Audit Logging Tests
# =============================================================================


class TestAuditLogging:
    """Test audit logging."""

    @pytest.mark.asyncio
    async def test_audit_log_on_create(self, service):
        """Test audit log entry created on new setting."""
        service._fallback_mode = True

        await service.update_setting(
            "platform", "new", {"key": "value"}, updated_by="creator"
        )

        log = service.get_audit_log(limit=1)
        assert len(log) == 1
        assert log[0].action == "create"
        assert log[0].changed_by == "creator"

    @pytest.mark.asyncio
    async def test_audit_log_on_update(self, service):
        """Test audit log entry on update."""
        service._fallback_mode = True

        await service.update_setting("platform", "test", {"v": 1})
        await service.update_setting("platform", "test", {"v": 2}, updated_by="updater")

        log = service.get_audit_log(limit=2)
        assert len(log) == 2
        assert log[0].action == "update"
        assert log[0].old_value == {"v": 1}
        assert log[0].new_value == {"v": 2}

    @pytest.mark.asyncio
    async def test_audit_log_on_delete(self, service):
        """Test audit log entry on delete."""
        service._fallback_mode = True

        await service.update_setting("platform", "to_delete", {"val": 1})
        await service.delete_setting("platform", "to_delete", deleted_by="deleter")

        log = service.get_audit_log(limit=2)
        assert log[0].action == "delete"
        assert log[0].changed_by == "deleter"

    def test_audit_log_filtering(self, service):
        """Test audit log filtering by settings type."""
        # Add some entries
        service._log_audit("platform", "key1", "create", None, {}, "user1")
        service._log_audit("customer:123", "key2", "create", None, {}, "user2")
        service._log_audit("platform", "key3", "update", {}, {}, "user3")

        # Filter by type
        platform_logs = service.get_audit_log(settings_type="platform")
        assert len(platform_logs) == 2

        customer_logs = service.get_audit_log(settings_type="customer:123")
        assert len(customer_logs) == 1


# =============================================================================
# DynamoDB Integration Tests
# =============================================================================


class TestDynamoDBIntegration:
    """Test DynamoDB integration (mocked)."""

    @pytest.mark.asyncio
    async def test_get_from_dynamodb(
        self, service, mock_dynamodb_resource, mock_dynamodb_table
    ):
        """Test getting setting from DynamoDB."""
        mock_dynamodb_table.get_item.return_value = {
            "Item": {
                "settings_type": "platform",
                "settings_key": "hitl",
                "value": {"require_approval": True},
            }
        }

        with patch.object(
            service, "_get_dynamodb_resource", return_value=mock_dynamodb_resource
        ):
            result = await service.get_setting("platform", "hitl")

        assert result["require_approval"] is True
        mock_dynamodb_table.get_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_to_dynamodb(
        self, service, mock_dynamodb_resource, mock_dynamodb_table
    ):
        """Test updating setting in DynamoDB."""
        with patch.object(
            service, "_get_dynamodb_resource", return_value=mock_dynamodb_resource
        ):
            result = await service.update_setting(
                "platform", "hitl", {"enabled": True}, "admin"
            )

        assert result is True
        mock_dynamodb_table.put_item.assert_called_once()

        # Verify put_item was called with correct structure
        call_args = mock_dynamodb_table.put_item.call_args
        item = call_args.kwargs["Item"]
        assert item["settings_type"] == "platform"
        assert item["settings_key"] == "hitl"
        assert item["value"] == {"enabled": True}

    @pytest.mark.asyncio
    async def test_delete_from_dynamodb(
        self, service, mock_dynamodb_resource, mock_dynamodb_table
    ):
        """Test deleting setting from DynamoDB."""
        with patch.object(
            service, "_get_dynamodb_resource", return_value=mock_dynamodb_resource
        ):
            result = await service.delete_setting("platform", "test")

        assert result is True
        mock_dynamodb_table.delete_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_on_dynamodb_error(
        self, service, mock_dynamodb_resource, mock_dynamodb_table
    ):
        """Test fallback to in-memory on DynamoDB error."""
        mock_dynamodb_table.get_item.side_effect = Exception("Connection error")

        with patch.object(
            service, "_get_dynamodb_resource", return_value=mock_dynamodb_resource
        ):
            # Should fall back to defaults
            result = await service.get_setting("platform", "hitl")

        assert service._fallback_mode is True
        assert result is not None  # Should return defaults


# =============================================================================
# Health Check Tests
# =============================================================================


class TestHealthCheck:
    """Test health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_fallback_mode(self, service):
        """Test health check in fallback mode."""
        service._fallback_mode = True

        health = await service.health_check()

        assert health["fallback_mode"] is True
        assert health["dynamodb_status"] == "FALLBACK_MODE"
        assert health["healthy"] is True

    @pytest.mark.asyncio
    async def test_health_check_dynamodb_active(self, service):
        """Test health check with active DynamoDB."""
        mock_client = MagicMock()
        mock_client.describe_table.return_value = {"Table": {"TableStatus": "ACTIVE"}}

        with patch.object(service, "_get_dynamodb_client", return_value=mock_client):
            health = await service.health_check()

        assert health["dynamodb_status"] == "ACTIVE"
        assert health["healthy"] is True


# =============================================================================
# Data Model Tests
# =============================================================================


class TestDataModels:
    """Test data model classes."""

    def test_settings_record_defaults(self):
        """Test SettingsRecord default values."""
        record = SettingsRecord(
            settings_type="platform",
            settings_key="test",
            value={"key": "value"},
        )

        assert record.version == 1
        assert record.created_at != ""
        assert record.updated_at != ""
        assert record.updated_by == "system"

    def test_audit_log_entry(self):
        """Test AuditLogEntry creation."""
        entry = AuditLogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            settings_type="platform",
            settings_key="test",
            action="update",
            old_value={"v": 1},
            new_value={"v": 2},
            changed_by="admin",
            change_summary="Updated value",
        )

        assert entry.action == "update"
        assert entry.old_value == {"v": 1}
        assert entry.new_value == {"v": 2}


# =============================================================================
# Default Settings Tests
# =============================================================================


class TestDefaultSettings:
    """Test default platform settings."""

    def test_default_settings_structure(self):
        """Test default settings have expected structure."""
        assert "integration_mode" in DEFAULT_PLATFORM_SETTINGS
        assert "hitl" in DEFAULT_PLATFORM_SETTINGS
        assert "mcp" in DEFAULT_PLATFORM_SETTINGS
        assert "security" in DEFAULT_PLATFORM_SETTINGS

    def test_default_integration_mode(self):
        """Test default integration mode is defense."""
        assert DEFAULT_PLATFORM_SETTINGS["integration_mode"]["mode"] == "defense"

    def test_default_hitl_settings(self):
        """Test default HITL settings."""
        hitl = DEFAULT_PLATFORM_SETTINGS["hitl"]
        assert hitl["require_approval_for_patches"] is True
        assert hitl["require_approval_for_deployments"] is True
        assert hitl["auto_approve_minor_patches"] is False

    def test_default_mcp_disabled(self):
        """Test MCP is disabled by default."""
        assert DEFAULT_PLATFORM_SETTINGS["mcp"]["enabled"] is False

    def test_default_security_settings(self):
        """Test default security settings."""
        security = DEFAULT_PLATFORM_SETTINGS["security"]
        assert security["enforce_air_gap"] is False
        assert security["block_external_network"] is True
        assert security["audit_all_actions"] is True


# =============================================================================
# DynamoDB Client Error Handling Tests
# =============================================================================


class TestDynamoDBErrorHandling:
    """Tests for DynamoDB client error handling - covers lines 230-240, 244-254."""

    def test_dynamodb_client_creation_failure(self):
        """Test _get_dynamodb_client handles creation failure - covers lines 237-240."""
        from unittest.mock import patch

        with patch("boto3.client") as mock_client:
            mock_client.side_effect = Exception("Connection failed")

            service = SettingsPersistenceService()
            service._dynamodb_client = None  # Reset

            result = service._get_dynamodb_client()

            assert result is None
            assert service._fallback_mode is True

    def test_dynamodb_resource_creation_failure(self):
        """Test _get_dynamodb_resource handles creation failure - covers lines 251-254."""
        from unittest.mock import patch

        with patch("boto3.resource") as mock_resource:
            mock_resource.side_effect = Exception("Connection failed")

            service = SettingsPersistenceService()
            service._dynamodb_resource = None  # Reset

            result = service._get_dynamodb_resource()

            assert result is None
            assert service._fallback_mode is True

    def test_dynamodb_client_returns_cached(self):
        """Test _get_dynamodb_client returns cached client - covers lines 230-240."""
        from unittest.mock import MagicMock

        service = SettingsPersistenceService()
        mock_client = MagicMock()
        service._dynamodb_client = mock_client

        result = service._get_dynamodb_client()

        assert result is mock_client

    def test_dynamodb_resource_returns_cached(self):
        """Test _get_dynamodb_resource returns cached resource - covers lines 244-254."""
        from unittest.mock import MagicMock

        service = SettingsPersistenceService()
        mock_resource = MagicMock()
        service._dynamodb_resource = mock_resource

        result = service._get_dynamodb_resource()

        assert result is mock_resource
