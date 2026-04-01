"""
Project Aura - Settings Persistence Service

Provides persistent storage for platform settings using AWS DynamoDB.
Replaces the in-memory settings store in settings_endpoints.py with
durable, scalable cloud storage.

Features:
- CRUD operations for platform settings
- Audit logging for all changes
- Support for per-customer and global settings
- Caching layer for performance
- Fallback to defaults on retrieval failure

Table Schema:
- PK: settings_type (e.g., "platform", "customer:{id}")
- SK: settings_key (e.g., "integration_mode", "hitl", "mcp")
- Data stored as JSON in 'value' attribute
"""

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mypy_boto3_dynamodb import DynamoDBClient
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================


class PersistenceMode(Enum):
    """Operating modes for persistence service."""

    MOCK = "mock"  # In-memory storage for testing
    AWS = "aws"  # Real DynamoDB


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class SettingsRecord:
    """Represents a settings record from DynamoDB."""

    settings_type: str  # PK: "platform", "customer:{id}", etc.
    settings_key: str  # SK: "integration_mode", "hitl", "mcp", "security"
    value: dict[str, Any]
    version: int = 1
    created_at: str = ""
    updated_at: str = ""
    updated_by: str = "system"

    def __post_init__(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now


@dataclass
class AuditLogEntry:
    """Audit log for settings changes."""

    timestamp: str
    settings_type: str
    settings_key: str
    action: str  # "create", "update", "delete"
    old_value: dict[str, Any] | None
    new_value: dict[str, Any] | None
    changed_by: str
    change_summary: str


# =============================================================================
# Default Settings
# =============================================================================

DEFAULT_PLATFORM_SETTINGS = {
    "integration_mode": {
        "mode": "defense",
        "description": "Maximum security mode - air-gap compatible",
    },
    "hitl": {
        "require_approval_for_patches": True,
        "require_approval_for_deployments": True,
        "auto_approve_minor_patches": False,
        "approval_timeout_hours": 24,
        "min_approvers": 1,
        "notify_on_approval_request": True,
        "notify_on_approval_timeout": True,
    },
    "mcp": {
        "enabled": False,
        "gateway_url": "",
        "api_key": "",
        "monthly_budget_usd": 100.0,
        "daily_limit_usd": 10.0,
        "external_tools_enabled": [],
        "rate_limit": {
            "requests_per_minute": 60,
            "requests_per_hour": 1000,
        },
    },
    "security": {
        "enforce_air_gap": False,
        "block_external_network": True,
        "sandbox_isolation_level": "vpc",
        "audit_all_actions": True,
        "retain_logs_for_days": 365,
    },
    "compliance": {
        "profile": "commercial",  # commercial, cmmc_l1, cmmc_l2, govcloud
        "kms_encryption_mode": "aws_managed",  # aws_managed, customer_managed
        "log_retention_days": 90,  # 30, 60, 90, 180, 365
        "audit_log_retention_days": 365,  # Always longer for audit trails
        "require_encryption_at_rest": True,
        "require_encryption_in_transit": True,
        "pending_kms_change": False,  # True if KMS change pending deployment
        "last_profile_change_at": None,  # Timestamp of last profile change
        "last_profile_change_by": None,  # User who made last change
    },
    "orchestrator": {
        # Deployment mode settings
        "on_demand_jobs_enabled": True,  # Default: on-demand ($0/mo, pay per job)
        "warm_pool_enabled": False,  # Optional: always-on pool (~$28/mo)
        "hybrid_mode_enabled": False,  # Optional: warm pool + burst jobs
        # Warm pool configuration
        "warm_pool_replicas": 1,  # Replicas when warm pool enabled
        # Hybrid mode configuration
        "hybrid_threshold_queue_depth": 5,  # Queue depth to trigger burst jobs
        "hybrid_scale_up_cooldown_seconds": 60,  # Min time between burst jobs
        "hybrid_max_burst_jobs": 10,  # Max concurrent burst jobs
        # Cost estimates (for UI display)
        "estimated_cost_per_job_usd": 0.15,  # ~15 min job on m5.large
        "estimated_warm_pool_monthly_usd": 28.0,  # 1 replica 24/7
        # Mode change cooldown (anti-thrashing)
        "mode_change_cooldown_seconds": 300,  # 5 minutes between mode changes
        "last_mode_change_at": None,  # Timestamp of last mode change
        "last_mode_change_by": None,  # User who made last change
    },
}


# =============================================================================
# Settings Persistence Service
# =============================================================================


class SettingsPersistenceService:
    """
    Persistent storage for platform settings using AWS DynamoDB.

    Usage:
        service = SettingsPersistenceService()

        # Get all platform settings
        settings = await service.get_all_platform_settings()

        # Get specific setting
        hitl = await service.get_setting("platform", "hitl")

        # Update setting
        await service.update_setting(
            settings_type="platform",
            settings_key="mcp",
            value={"enabled": True, ...},
            updated_by="admin@example.com"
        )
    """

    def __init__(
        self,
        table_name: str | None = None,
        region: str | None = None,
        enable_cache: bool = True,
        cache_ttl_seconds: int = 60,
    ):
        """
        Initialize the settings persistence service.

        Args:
            table_name: DynamoDB table name (defaults to env var or aura-settings-{env})
            region: AWS region (defaults to us-east-1)
            enable_cache: Whether to enable in-memory caching
            cache_ttl_seconds: Cache TTL in seconds
        """
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        env = os.environ.get("ENVIRONMENT", "dev")
        self.table_name = table_name or os.environ.get(
            "SETTINGS_TABLE_NAME", f"aura-platform-settings-{env}"
        )
        self.enable_cache = enable_cache
        self.cache_ttl_seconds = cache_ttl_seconds

        # In-memory cache: {cache_key: (timestamp, value)}
        self._cache: dict[str, tuple[float, Any]] = {}

        # Audit log buffer (in production, this would write to CloudWatch or S3)
        self._audit_log: list[AuditLogEntry] = []

        # DynamoDB client (lazy initialization)
        self._dynamodb_client: "DynamoDBClient | None" = None
        self._dynamodb_resource: "DynamoDBServiceResource | None" = None

        # Fallback mode (use in-memory if DynamoDB unavailable)
        self._fallback_mode = False
        self._in_memory_store: dict[str, dict[str, Any]] = {}

        logger.info(
            f"SettingsPersistenceService initialized: table={self.table_name}, "
            f"region={self.region}, cache={enable_cache}"
        )

    def _get_dynamodb_client(self):
        """Get or create DynamoDB client."""
        if self._dynamodb_client is None:
            try:
                import boto3

                self._dynamodb_client = boto3.client(
                    "dynamodb", region_name=self.region
                )
            except Exception as e:
                logger.warning(f"Failed to create DynamoDB client: {e}")
                self._fallback_mode = True
        return self._dynamodb_client

    def _get_dynamodb_resource(self):
        """Get or create DynamoDB resource."""
        if self._dynamodb_resource is None:
            try:
                import boto3

                self._dynamodb_resource = boto3.resource(
                    "dynamodb", region_name=self.region
                )
            except Exception as e:
                logger.warning(f"Failed to create DynamoDB resource: {e}")
                self._fallback_mode = True
        return self._dynamodb_resource

    # =========================================================================
    # Cache Management
    # =========================================================================

    def _cache_key(self, settings_type: str, settings_key: str) -> str:
        """Generate cache key."""
        return f"{settings_type}:{settings_key}"

    def _get_from_cache(
        self, settings_type: str, settings_key: str
    ) -> dict[str, Any] | None:
        """Get value from cache if not expired."""
        if not self.enable_cache:
            return None

        key = self._cache_key(settings_type, settings_key)
        if key in self._cache:
            timestamp, cached_value = self._cache[key]
            if time.time() - timestamp < self.cache_ttl_seconds:
                logger.debug(f"Cache hit for {key}")
                # Ensure type safety - cache stores dict[str, Any]
                result: dict[str, Any] = cached_value  # type: ignore[assignment]
                return result
            else:
                # Expired
                del self._cache[key]

        return None

    def _set_cache(
        self, settings_type: str, settings_key: str, value: dict[str, Any]
    ) -> None:
        """Set value in cache."""
        if not self.enable_cache:
            return

        key = self._cache_key(settings_type, settings_key)
        self._cache[key] = (time.time(), value)

    def _invalidate_cache(self, settings_type: str, settings_key: str) -> None:
        """Invalidate a cache entry."""
        key = self._cache_key(settings_type, settings_key)
        if key in self._cache:
            del self._cache[key]

    def clear_cache(self) -> None:
        """Clear all cached settings."""
        self._cache.clear()
        logger.info("Settings cache cleared")

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    async def get_setting(
        self,
        settings_type: str,
        settings_key: str,
        default: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        Get a specific setting.

        Args:
            settings_type: Type of settings (e.g., "platform")
            settings_key: Key within the type (e.g., "hitl")
            default: Default value if not found

        Returns:
            Setting value or default
        """
        # Check cache first
        cached = self._get_from_cache(settings_type, settings_key)
        if cached is not None:
            return cached

        # Check fallback mode
        if self._fallback_mode:
            return self._get_from_memory(settings_type, settings_key, default)

        try:
            dynamodb = self._get_dynamodb_resource()
            if dynamodb is None:
                return self._get_from_memory(settings_type, settings_key, default)

            table = dynamodb.Table(self.table_name)
            response = table.get_item(
                Key={
                    "settings_type": settings_type,
                    "settings_key": settings_key,
                }
            )

            if "Item" in response:
                item_value = response["Item"].get("value", {})
                # Handle DynamoDB JSON format if needed
                if isinstance(item_value, str):
                    parsed_value: dict[str, Any] = json.loads(item_value)
                    self._set_cache(settings_type, settings_key, parsed_value)
                    return parsed_value
                else:
                    # Already a dict
                    dict_value: dict[str, Any] = item_value  # type: ignore[assignment]
                    self._set_cache(settings_type, settings_key, dict_value)
                    return dict_value

            # Not found, use default
            if default is None and settings_type == "platform":
                platform_default = DEFAULT_PLATFORM_SETTINGS.get(settings_key)
                if platform_default is not None:
                    return platform_default  # type: ignore[return-value]
                return {}

            return default

        except Exception as e:
            logger.error(f"Error getting setting {settings_type}/{settings_key}: {e}")
            self._fallback_mode = True
            return self._get_from_memory(settings_type, settings_key, default)

    async def update_setting(
        self,
        settings_type: str,
        settings_key: str,
        value: dict[str, Any],
        updated_by: str = "system",
    ) -> bool:
        """
        Update a setting (creates if not exists).

        Args:
            settings_type: Type of settings
            settings_key: Key within the type
            value: New value
            updated_by: User/system making the change

        Returns:
            True if successful
        """
        # Get old value for audit
        old_value = await self.get_setting(settings_type, settings_key)

        # Invalidate cache
        self._invalidate_cache(settings_type, settings_key)

        # Check fallback mode
        if self._fallback_mode:
            result = self._set_in_memory(settings_type, settings_key, value)
            # Log audit even in fallback mode
            self._log_audit(
                settings_type=settings_type,
                settings_key=settings_key,
                action="update" if old_value else "create",
                old_value=old_value,
                new_value=value,
                changed_by=updated_by,
            )
            return result

        try:
            dynamodb = self._get_dynamodb_resource()
            if dynamodb is None:
                return self._set_in_memory(settings_type, settings_key, value)

            table = dynamodb.Table(self.table_name)
            now = datetime.now(timezone.utc).isoformat()

            table.put_item(
                Item={
                    "settings_type": settings_type,
                    "settings_key": settings_key,
                    "value": value,
                    "updated_at": now,
                    "updated_by": updated_by,
                    "version": 1,  # Could implement versioning
                }
            )

            # Log audit entry
            self._log_audit(
                settings_type=settings_type,
                settings_key=settings_key,
                action="update" if old_value else "create",
                old_value=old_value,
                new_value=value,
                changed_by=updated_by,
            )

            logger.info(
                f"Setting updated: {settings_type}/{settings_key} by {updated_by}"
            )
            return True

        except Exception as e:
            logger.error(f"Error updating setting {settings_type}/{settings_key}: {e}")
            self._fallback_mode = True
            return self._set_in_memory(settings_type, settings_key, value)

    async def delete_setting(
        self,
        settings_type: str,
        settings_key: str,
        deleted_by: str = "system",
    ) -> bool:
        """
        Delete a setting.

        Args:
            settings_type: Type of settings
            settings_key: Key within the type
            deleted_by: User/system deleting the setting

        Returns:
            True if successful
        """
        # Get old value for audit
        old_value = await self.get_setting(settings_type, settings_key)

        # Invalidate cache
        self._invalidate_cache(settings_type, settings_key)

        if self._fallback_mode:
            result = self._delete_from_memory(settings_type, settings_key)
            # Log audit even in fallback mode
            self._log_audit(
                settings_type=settings_type,
                settings_key=settings_key,
                action="delete",
                old_value=old_value,
                new_value=None,
                changed_by=deleted_by,
            )
            return result

        try:
            dynamodb = self._get_dynamodb_resource()
            if dynamodb is None:
                return self._delete_from_memory(settings_type, settings_key)

            table = dynamodb.Table(self.table_name)
            table.delete_item(
                Key={
                    "settings_type": settings_type,
                    "settings_key": settings_key,
                }
            )

            # Log audit entry
            self._log_audit(
                settings_type=settings_type,
                settings_key=settings_key,
                action="delete",
                old_value=old_value,
                new_value=None,
                changed_by=deleted_by,
            )

            logger.info(
                f"Setting deleted: {settings_type}/{settings_key} by {deleted_by}"
            )
            return True

        except Exception as e:
            logger.error(f"Error deleting setting {settings_type}/{settings_key}: {e}")
            return False

    # =========================================================================
    # Bulk Operations
    # =========================================================================

    async def get_all_platform_settings(self) -> dict[str, Any]:
        """
        Get all platform settings.

        Returns:
            Dict with all platform settings
        """
        settings = {}
        for key in ["integration_mode", "hitl", "mcp", "security", "orchestrator"]:
            default_value = DEFAULT_PLATFORM_SETTINGS.get(key)
            if default_value is not None:
                typed_default: dict[str, Any] = default_value  # type: ignore[assignment]
                value = await self.get_setting("platform", key, typed_default)
            else:
                value = await self.get_setting("platform", key, None)
            settings[key] = value

        return settings

    async def update_all_platform_settings(
        self,
        settings: dict[str, Any],
        updated_by: str = "system",
    ) -> bool:
        """
        Update all platform settings at once.

        Args:
            settings: Dict with all platform settings
            updated_by: User making the change

        Returns:
            True if all updates successful
        """
        success = True

        for key, value in settings.items():
            if key in [
                "integration_mode",
                "hitl",
                "mcp",
                "security",
                "compliance",
                "orchestrator",
            ]:
                result = await self.update_setting("platform", key, value, updated_by)
                if not result:
                    success = False

        return success

    # =========================================================================
    # Organization Settings (Per-Organization Overrides)
    # =========================================================================

    async def get_organization_setting(
        self,
        organization_id: str,
        settings_key: str,
        default: Any = None,
    ) -> dict[str, Any] | None:
        """
        Get organization-specific settings.

        Organization settings allow per-org overrides of platform defaults.
        The settings_type is automatically prefixed with 'organization:'.

        Args:
            organization_id: Organization identifier
            settings_key: Settings key (e.g., 'orchestrator')
            default: Default value if not found

        Returns:
            Organization-specific settings or None if not found
        """
        settings_type = f"organization:{organization_id}"

        # Try to get org-specific setting
        org_setting = await self.get_setting(settings_type, settings_key, None)

        if org_setting is not None:
            return org_setting

        # Return default if no org-specific setting
        if default is not None:
            result: dict[str, Any] = default  # type: ignore[assignment]
            return result
        return None

    async def update_organization_setting(
        self,
        organization_id: str,
        settings_key: str,
        updates: dict[str, Any],
        updated_by: str = "system",
    ) -> bool:
        """
        Update organization-specific settings.

        Creates or updates settings for a specific organization.
        Only the provided fields are updated (merged with existing).

        Args:
            organization_id: Organization identifier
            settings_key: Settings key (e.g., 'orchestrator')
            updates: Dict of fields to update
            updated_by: User making the change

        Returns:
            True if update successful
        """
        settings_type = f"organization:{organization_id}"

        # Get existing org settings (if any)
        existing = await self.get_setting(settings_type, settings_key, {})

        # Ensure existing is a dict for merging
        if existing is None:
            existing = {}

        # Merge updates with existing
        merged = {**existing, **updates}

        # Save the merged settings (should be update_setting, not save_setting)
        return await self.update_setting(
            settings_type, settings_key, merged, updated_by
        )

    async def delete_organization_setting(
        self,
        organization_id: str,
        settings_key: str,
        deleted_by: str = "system",
    ) -> bool:
        """
        Delete organization-specific settings.

        Removes the org override, causing the org to fall back to platform defaults.

        Args:
            organization_id: Organization identifier
            settings_key: Settings key (e.g., 'orchestrator')
            deleted_by: User making the deletion

        Returns:
            True if deletion successful
        """
        settings_type = f"organization:{organization_id}"
        return await self.delete_setting(settings_type, settings_key, deleted_by)

    async def list_organization_overrides(
        self,
        organization_id: str,
    ) -> dict[str, Any]:
        """
        List all settings overrides for an organization.

        Args:
            organization_id: Organization identifier

        Returns:
            Dict of all org-specific settings
        """
        settings_type = f"organization:{organization_id}"
        overrides = {}

        # Check in-memory store for org settings
        if settings_type in self._in_memory_store:
            overrides = dict(self._in_memory_store[settings_type])

        # In AWS mode, would query DynamoDB for all items with this settings_type
        # For now, return what's in memory
        return overrides

    async def initialize_defaults(self, force: bool = False) -> int:
        """
        Initialize default settings if not present.

        Args:
            force: If True, overwrite existing settings

        Returns:
            Number of settings initialized
        """
        count = 0

        for key, value in DEFAULT_PLATFORM_SETTINGS.items():
            # Check if value is actually stored (not just default)
            stored = self._is_setting_stored("platform", key)

            if not stored or force:
                # Ensure value is typed correctly
                typed_value: dict[str, Any] = value  # type: ignore[assignment]
                await self.update_setting("platform", key, typed_value, "system:init")
                count += 1
                logger.info(f"Initialized default setting: platform/{key}")

        return count

    def _is_setting_stored(self, settings_type: str, settings_key: str) -> bool:
        """Check if a setting is actually stored (vs returning default)."""
        # Check in-memory store
        if settings_type in self._in_memory_store:
            if settings_key in self._in_memory_store[settings_type]:
                return True

        # In non-fallback mode, we'd check DynamoDB here
        # For now, if fallback mode and not in memory, it's not stored
        return False

    # =========================================================================
    # In-Memory Fallback
    # =========================================================================

    def _get_from_memory(
        self, settings_type: str, settings_key: str, default: Any = None
    ) -> dict[str, Any] | None:
        """Get from in-memory store (fallback mode)."""
        type_store = self._in_memory_store.get(settings_type, {})
        value = type_store.get(settings_key)

        if value is None:
            if default is not None:
                result: dict[str, Any] = default  # type: ignore[assignment]
                return result
            if settings_type == "platform":
                platform_default = DEFAULT_PLATFORM_SETTINGS.get(settings_key, {})
                typed_result: dict[str, Any] = platform_default  # type: ignore[assignment]
                return typed_result
            return None

        # Type assertion for value from in-memory store
        typed_value: dict[str, Any] = value  # type: ignore[assignment]
        return typed_value

    def _set_in_memory(
        self, settings_type: str, settings_key: str, value: dict[str, Any]
    ) -> bool:
        """Set in in-memory store (fallback mode)."""
        if settings_type not in self._in_memory_store:
            self._in_memory_store[settings_type] = {}

        self._in_memory_store[settings_type][settings_key] = value
        return True

    def _delete_from_memory(self, settings_type: str, settings_key: str) -> bool:
        """Delete from in-memory store (fallback mode)."""
        if settings_type in self._in_memory_store:
            if settings_key in self._in_memory_store[settings_type]:
                del self._in_memory_store[settings_type][settings_key]
        return True

    # =========================================================================
    # Audit Logging
    # =========================================================================

    def _log_audit(
        self,
        settings_type: str,
        settings_key: str,
        action: str,
        old_value: dict[str, Any] | None,
        new_value: dict[str, Any] | None,
        changed_by: str,
    ) -> None:
        """Log an audit entry for settings changes."""
        # Build change summary
        if action == "create":
            summary = f"Created {settings_type}/{settings_key}"
        elif action == "delete":
            summary = f"Deleted {settings_type}/{settings_key}"
        else:
            # Build diff summary
            changes = []
            if old_value and new_value:
                for key in set(list(old_value.keys()) + list(new_value.keys())):
                    old_v = old_value.get(key)
                    new_v = new_value.get(key)
                    if old_v != new_v:
                        changes.append(f"{key}: {old_v} -> {new_v}")
            summary = (
                f"Updated {settings_type}/{settings_key}: {', '.join(changes[:3])}"
            )
            if len(changes) > 3:
                summary += f" (+{len(changes) - 3} more)"

        entry = AuditLogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            settings_type=settings_type,
            settings_key=settings_key,
            action=action,
            old_value=old_value,
            new_value=new_value,
            changed_by=changed_by,
            change_summary=summary,
        )

        self._audit_log.append(entry)

        # In production, would also write to CloudWatch Logs
        logger.info(f"Audit: {summary} by {changed_by}")

    def get_audit_log(
        self,
        limit: int = 100,
        settings_type: str | None = None,
    ) -> list[AuditLogEntry]:
        """
        Get recent audit log entries.

        Args:
            limit: Maximum entries to return
            settings_type: Filter by settings type

        Returns:
            List of audit log entries
        """
        entries = self._audit_log

        if settings_type:
            entries = [e for e in entries if e.settings_type == settings_type]

        return list(reversed(entries[-limit:]))

    # =========================================================================
    # Health Check
    # =========================================================================

    async def health_check(self) -> dict[str, Any]:
        """
        Check health of the persistence service.

        Returns:
            Health status dict
        """
        status = {
            "service": "settings_persistence",
            "table_name": self.table_name,
            "region": self.region,
            "fallback_mode": self._fallback_mode,
            "cache_enabled": self.enable_cache,
            "cache_entries": len(self._cache),
            "audit_log_entries": len(self._audit_log),
        }

        if not self._fallback_mode:
            try:
                dynamodb = self._get_dynamodb_client()
                if dynamodb:
                    response = dynamodb.describe_table(TableName=self.table_name)
                    status["dynamodb_status"] = response["Table"]["TableStatus"]
                    status["healthy"] = True
                else:
                    status["dynamodb_status"] = "UNAVAILABLE"
                    status["healthy"] = False
            except Exception as e:
                status["dynamodb_status"] = f"ERROR: {str(e)}"
                status["healthy"] = False
        else:
            status["dynamodb_status"] = "FALLBACK_MODE"
            status["healthy"] = True  # Fallback is operational

        return status


# =============================================================================
# Factory Function
# =============================================================================


_service_instance: SettingsPersistenceService | None = None


def get_settings_service() -> SettingsPersistenceService:
    """
    Get or create the settings persistence service singleton.

    Returns:
        SettingsPersistenceService instance
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = SettingsPersistenceService()
    return _service_instance


def create_settings_service(
    table_name: str | None = None,
    region: str | None = None,
    enable_cache: bool = True,
) -> SettingsPersistenceService:
    """
    Create a new settings persistence service instance.

    Args:
        table_name: Optional custom table name
        region: Optional AWS region
        enable_cache: Whether to enable caching

    Returns:
        New SettingsPersistenceService instance
    """
    return SettingsPersistenceService(
        table_name=table_name,
        region=region,
        enable_cache=enable_cache,
    )


def create_settings_persistence_service(
    mode: PersistenceMode = PersistenceMode.MOCK,
    table_name: str | None = None,
    region: str | None = None,
    enable_cache: bool = True,
) -> SettingsPersistenceService:
    """
    Factory function to create SettingsPersistenceService with mode support.

    Args:
        mode: PersistenceMode.MOCK for testing, PersistenceMode.AWS for production
        table_name: Optional custom table name
        region: Optional AWS region
        enable_cache: Whether to enable caching

    Returns:
        New SettingsPersistenceService instance
    """
    # For now, mode is informational - service handles AWS/fallback internally
    return SettingsPersistenceService(
        table_name=table_name,
        region=region,
        enable_cache=enable_cache if mode == PersistenceMode.AWS else False,
    )
