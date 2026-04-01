"""
Project Aura - Dynamic Capability Grant Manager

Manages dynamic capability grants issued through HITL approval.
Handles grant creation, validation, usage tracking, and expiration.

Security Rationale:
- Time-bounded grants prevent permanent privilege escalation
- Usage-limited grants enable single-use approvals
- Revocation support for emergency response
- Full audit trail for all grant operations

Author: Project Aura Team
Created: 2026-01-26
"""

import ast
import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from .contracts import (
    CapabilityApprovalResponse,
    CapabilityScope,
    DynamicCapabilityGrant,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Grant Manager Configuration
# =============================================================================


@dataclass
class GrantManagerConfig:
    """Configuration for dynamic grant management."""

    # DynamoDB settings
    table_name: str = "aura-capability-grants"

    # Default grant durations by scope
    single_use_expiry_minutes: int = 60
    session_expiry_hours: int = 8
    task_tree_expiry_hours: int = 24
    time_bounded_default_hours: int = 4

    # Grant limits
    max_active_grants_per_agent: int = 10
    max_usage_per_grant: int = 100

    # Cleanup settings
    cleanup_interval_seconds: float = 300.0  # 5 minutes
    enable_background_cleanup: bool = True

    # Cache settings
    cache_ttl_seconds: int = 60
    cache_max_size: int = 1000


# =============================================================================
# Grant Manager
# =============================================================================


class DynamicGrantManager:
    """
    Manages dynamic capability grants.

    Handles:
    - Grant creation from HITL approval
    - Grant validation and lookup
    - Usage tracking and limits
    - Grant revocation
    - Automatic expiration

    Usage:
        manager = DynamicGrantManager()
        grant = await manager.create_grant(approval_response, "agent-123")
        is_valid = await manager.check_grant("agent-123", "tool_name", "action", "context")
    """

    def __init__(
        self,
        config: Optional[GrantManagerConfig] = None,
        dynamodb_client: Optional[Any] = None,
    ):
        """
        Initialize the grant manager.

        Args:
            config: Grant manager configuration
            dynamodb_client: Optional boto3 DynamoDB client (for testing)
        """
        self.config = config or GrantManagerConfig()
        self._dynamodb = dynamodb_client

        # In-memory cache for active grants
        # Key: agent_id, Value: list of DynamicCapabilityGrant
        self._grant_cache: dict[str, list[DynamicCapabilityGrant]] = {}
        self._cache_timestamps: dict[str, float] = {}

        # Background cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

        # Metrics
        self._grants_created = 0
        self._grants_used = 0
        self._grants_revoked = 0
        self._grants_expired = 0
        self._cache_hits = 0
        self._cache_misses = 0

        logger.debug(
            f"DynamicGrantManager initialized " f"(table={self.config.table_name})"
        )

    async def start(self) -> None:
        """Start the background cleanup task."""
        if self._running:
            return

        self._running = True
        if self.config.enable_background_cleanup:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Grant manager cleanup task started")

    async def stop(self) -> None:
        """Stop the background cleanup task."""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info(
            f"Grant manager stopped "
            f"(created={self._grants_created}, "
            f"used={self._grants_used}, "
            f"revoked={self._grants_revoked})"
        )

    def _get_dynamodb_client(self) -> Any:
        """Get or create DynamoDB client."""
        if self._dynamodb is None:
            try:
                import boto3

                self._dynamodb = boto3.client("dynamodb")
            except ImportError:
                logger.warning("boto3 not available, using in-memory storage only")
                return None
        return self._dynamodb

    def _calculate_expiry(self, scope: CapabilityScope) -> datetime:
        """Calculate expiry time based on scope."""
        now = datetime.now(timezone.utc)

        if scope == CapabilityScope.SINGLE_USE:
            return now + timedelta(minutes=self.config.single_use_expiry_minutes)
        elif scope == CapabilityScope.SESSION:
            return now + timedelta(hours=self.config.session_expiry_hours)
        elif scope == CapabilityScope.TASK_TREE:
            return now + timedelta(hours=self.config.task_tree_expiry_hours)
        else:  # TIME_BOUNDED
            return now + timedelta(hours=self.config.time_bounded_default_hours)

    async def create_grant(
        self,
        approval: CapabilityApprovalResponse,
        agent_id: str,
        tool_name: str,
        action: str,
        context_restrictions: Optional[list[str]] = None,
    ) -> DynamicCapabilityGrant:
        """
        Create a dynamic grant from an approval response.

        Args:
            approval: The HITL approval response
            agent_id: Agent receiving the grant
            tool_name: Tool being granted
            action: Action being granted
            context_restrictions: Optional context restrictions

        Returns:
            Created DynamicCapabilityGrant
        """
        # Check active grant limit
        existing_grants = await self.get_active_grants(agent_id)
        if len(existing_grants) >= self.config.max_active_grants_per_agent:
            raise ValueError(
                f"Agent {agent_id} has reached maximum active grants "
                f"({self.config.max_active_grants_per_agent})"
            )

        # Calculate expiry
        if approval.expires_at:
            expires_at = approval.expires_at
        else:
            expires_at = self._calculate_expiry(approval.scope)

        # Determine max usage based on scope
        max_usage = None
        if approval.scope == CapabilityScope.SINGLE_USE:
            max_usage = 1
        elif "max_usage" in approval.constraints:
            max_usage = approval.constraints["max_usage"]

        # Create grant
        grant = DynamicCapabilityGrant(
            grant_id=str(uuid.uuid4()),
            agent_id=agent_id,
            tool_name=tool_name,
            action=action,
            scope=approval.scope,
            constraints=approval.constraints,
            granted_by=approval.request_id,
            approver=approval.approver_id,
            granted_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            usage_count=0,
            max_usage=max_usage,
            context_restrictions=context_restrictions or [],
        )

        # Persist to DynamoDB
        await self._save_grant(grant)

        # Update cache
        self._invalidate_cache(agent_id)

        self._grants_created += 1
        logger.info(
            f"Created grant: {grant.grant_id} "
            f"(agent={agent_id}, tool={tool_name}, "
            f"scope={approval.scope.value}, expires={expires_at.isoformat()})"
        )

        return grant

    async def _save_grant(self, grant: DynamicCapabilityGrant) -> None:
        """Save a grant to DynamoDB."""
        client = self._get_dynamodb_client()
        if not client:
            # Fall back to in-memory storage
            if grant.agent_id not in self._grant_cache:
                self._grant_cache[grant.agent_id] = []
            self._grant_cache[grant.agent_id].append(grant)
            return

        ttl_timestamp = int(grant.expires_at.timestamp())

        item = {
            "PK": {"S": f"GRANT#{grant.agent_id}"},
            "SK": {"S": f"{grant.tool_name}#{grant.grant_id}"},
            "grant_id": {"S": grant.grant_id},
            "agent_id": {"S": grant.agent_id},
            "tool_name": {"S": grant.tool_name},
            "action": {"S": grant.action},
            "scope": {"S": grant.scope.value},
            "constraints": {"S": str(grant.constraints)},
            "granted_by": {"S": grant.granted_by},
            "approver": {"S": grant.approver},
            "granted_at": {"S": grant.granted_at.isoformat()},
            "expires_at": {"S": grant.expires_at.isoformat()},
            "usage_count": {"N": str(grant.usage_count)},
            "revoked": {"BOOL": grant.revoked},
            "TTL": {"N": str(ttl_timestamp)},
            # GSI for tool-based queries
            "GSI1PK": {"S": f"TOOL#{grant.tool_name}"},
            "GSI1SK": {"S": f"{grant.agent_id}#{grant.grant_id}"},
        }

        if grant.max_usage is not None:
            item["max_usage"] = {"N": str(grant.max_usage)}
        if grant.context_restrictions:
            item["context_restrictions"] = {"SS": grant.context_restrictions}

        try:
            client.put_item(
                TableName=self.config.table_name,
                Item=item,
            )
        except Exception as e:
            logger.error(f"Failed to save grant: {e}")
            raise

    async def get_active_grants(
        self,
        agent_id: str,
    ) -> list[DynamicCapabilityGrant]:
        """
        Get all active grants for an agent.

        Args:
            agent_id: Agent ID to query

        Returns:
            List of active grants
        """
        # Check cache
        cache_key = agent_id
        if cache_key in self._grant_cache:
            cache_age = time.time() - self._cache_timestamps.get(cache_key, 0)
            if cache_age < self.config.cache_ttl_seconds:
                self._cache_hits += 1
                # Filter to only valid grants
                return [g for g in self._grant_cache[cache_key] if g.is_valid]

        self._cache_misses += 1

        client = self._get_dynamodb_client()
        if not client:
            # Return from in-memory cache even if expired
            return [g for g in self._grant_cache.get(agent_id, []) if g.is_valid]

        try:
            response = client.query(
                TableName=self.config.table_name,
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": {"S": f"GRANT#{agent_id}"}},
            )

            grants = []
            for item in response.get("Items", []):
                grant = self._item_to_grant(item)
                if grant.is_valid:
                    grants.append(grant)

            # Update cache
            self._grant_cache[cache_key] = grants
            self._cache_timestamps[cache_key] = time.time()

            return grants

        except Exception as e:
            logger.error(f"Failed to get grants: {e}")
            return []

    def _item_to_grant(self, item: dict[str, Any]) -> DynamicCapabilityGrant:
        """Convert DynamoDB item to DynamicCapabilityGrant."""
        return DynamicCapabilityGrant(
            grant_id=item["grant_id"]["S"],
            agent_id=item["agent_id"]["S"],
            tool_name=item["tool_name"]["S"],
            action=item["action"]["S"],
            scope=CapabilityScope(item["scope"]["S"]),
            constraints=ast.literal_eval(item["constraints"]["S"]),
            granted_by=item["granted_by"]["S"],
            approver=item["approver"]["S"],
            granted_at=datetime.fromisoformat(item["granted_at"]["S"]),
            expires_at=datetime.fromisoformat(item["expires_at"]["S"]),
            usage_count=int(item["usage_count"]["N"]),
            max_usage=(int(item["max_usage"]["N"]) if "max_usage" in item else None),
            revoked=item["revoked"]["BOOL"],
            context_restrictions=(
                list(item["context_restrictions"]["SS"])
                if "context_restrictions" in item
                else []
            ),
        )

    async def check_grant(
        self,
        agent_id: str,
        tool_name: str,
        action: str,
        context: str,
    ) -> Optional[DynamicCapabilityGrant]:
        """
        Check if an agent has a valid grant for a tool/action.

        Args:
            agent_id: Agent ID
            tool_name: Tool name
            action: Action type
            context: Execution context

        Returns:
            Matching grant if found and valid, None otherwise
        """
        grants = await self.get_active_grants(agent_id)

        for grant in grants:
            if grant.is_applicable(tool_name, action, context):
                return grant

        return None

    async def use_grant(
        self,
        grant_id: str,
        agent_id: str,
    ) -> bool:
        """
        Record usage of a grant.

        Args:
            grant_id: Grant ID
            agent_id: Agent ID

        Returns:
            True if usage recorded, False if grant exhausted
        """
        client = self._get_dynamodb_client()

        # Update usage count
        if client:
            try:
                # Find the grant's sort key
                response = client.query(
                    TableName=self.config.table_name,
                    KeyConditionExpression="PK = :pk",
                    FilterExpression="grant_id = :grant_id",
                    ExpressionAttributeValues={
                        ":pk": {"S": f"GRANT#{agent_id}"},
                        ":grant_id": {"S": grant_id},
                    },
                )

                items = response.get("Items", [])
                if not items:
                    return False

                item = items[0]
                sk = item["SK"]["S"]

                # Atomic increment with condition
                client.update_item(
                    TableName=self.config.table_name,
                    Key={
                        "PK": {"S": f"GRANT#{agent_id}"},
                        "SK": {"S": sk},
                    },
                    UpdateExpression="SET usage_count = usage_count + :inc",
                    ConditionExpression=(
                        "attribute_not_exists(max_usage) OR " "usage_count < max_usage"
                    ),
                    ExpressionAttributeValues={
                        ":inc": {"N": "1"},
                    },
                    ReturnValues="UPDATED_NEW",
                )

                self._grants_used += 1
                logger.debug(f"Used grant: {grant_id} (agent={agent_id})")

                # Invalidate cache
                self._invalidate_cache(agent_id)

                return True

            except client.exceptions.ConditionalCheckFailedException:
                logger.warning(f"Grant {grant_id} exhausted")
                return False
            except Exception as e:
                logger.error(f"Failed to use grant: {e}")
                return False
        else:
            # In-memory update
            if agent_id in self._grant_cache:
                for grant in self._grant_cache[agent_id]:
                    if grant.grant_id == grant_id:
                        if (
                            grant.max_usage is None
                            or grant.usage_count < grant.max_usage
                        ):
                            grant.usage_count += 1
                            self._grants_used += 1
                            return True
                        return False
            return False

    async def revoke_grant(
        self,
        grant_id: str,
        agent_id: str,
        reason: str,
        revoked_by: str = "system",
    ) -> bool:
        """
        Revoke a grant.

        Args:
            grant_id: Grant ID to revoke
            agent_id: Agent ID
            reason: Reason for revocation
            revoked_by: ID of revoker

        Returns:
            True if revoked, False if not found
        """
        client = self._get_dynamodb_client()

        if client:
            try:
                # Find the grant
                response = client.query(
                    TableName=self.config.table_name,
                    KeyConditionExpression="PK = :pk",
                    FilterExpression="grant_id = :grant_id",
                    ExpressionAttributeValues={
                        ":pk": {"S": f"GRANT#{agent_id}"},
                        ":grant_id": {"S": grant_id},
                    },
                )

                items = response.get("Items", [])
                if not items:
                    return False

                item = items[0]
                sk = item["SK"]["S"]

                # Mark as revoked
                client.update_item(
                    TableName=self.config.table_name,
                    Key={
                        "PK": {"S": f"GRANT#{agent_id}"},
                        "SK": {"S": sk},
                    },
                    UpdateExpression=(
                        "SET revoked = :revoked, "
                        "revoked_at = :revoked_at, "
                        "revoked_reason = :reason, "
                        "revoked_by = :revoked_by"
                    ),
                    ExpressionAttributeValues={
                        ":revoked": {"BOOL": True},
                        ":revoked_at": {"S": datetime.now(timezone.utc).isoformat()},
                        ":reason": {"S": reason},
                        ":revoked_by": {"S": revoked_by},
                    },
                )

                self._grants_revoked += 1
                self._invalidate_cache(agent_id)
                logger.info(f"Revoked grant: {grant_id} (reason={reason})")
                return True

            except Exception as e:
                logger.error(f"Failed to revoke grant: {e}")
                return False
        else:
            # In-memory revocation
            if agent_id in self._grant_cache:
                for grant in self._grant_cache[agent_id]:
                    if grant.grant_id == grant_id:
                        grant.revoked = True
                        grant.revoked_at = datetime.now(timezone.utc)
                        grant.revoked_reason = reason
                        self._grants_revoked += 1
                        return True
            return False

    async def revoke_all_grants(
        self,
        agent_id: str,
        reason: str,
        revoked_by: str = "system",
    ) -> int:
        """
        Revoke all grants for an agent.

        Args:
            agent_id: Agent ID
            reason: Reason for revocation
            revoked_by: ID of revoker

        Returns:
            Number of grants revoked
        """
        grants = await self.get_active_grants(agent_id)
        revoked_count = 0

        for grant in grants:
            if await self.revoke_grant(grant.grant_id, agent_id, reason, revoked_by):
                revoked_count += 1

        logger.info(f"Revoked {revoked_count} grants for agent {agent_id}")
        return revoked_count

    async def extend_grant(
        self,
        grant_id: str,
        agent_id: str,
        extension_hours: int,
        extended_by: str,
    ) -> bool:
        """
        Extend the expiry of a grant.

        Args:
            grant_id: Grant ID
            agent_id: Agent ID
            extension_hours: Hours to extend
            extended_by: ID of extender

        Returns:
            True if extended, False if not found or invalid
        """
        client = self._get_dynamodb_client()

        if not client:
            # In-memory extension
            if agent_id in self._grant_cache:
                for grant in self._grant_cache[agent_id]:
                    if grant.grant_id == grant_id and grant.is_valid:
                        grant.expires_at += timedelta(hours=extension_hours)
                        return True
            return False

        try:
            # Find the grant
            response = client.query(
                TableName=self.config.table_name,
                KeyConditionExpression="PK = :pk",
                FilterExpression="grant_id = :grant_id",
                ExpressionAttributeValues={
                    ":pk": {"S": f"GRANT#{agent_id}"},
                    ":grant_id": {"S": grant_id},
                },
            )

            items = response.get("Items", [])
            if not items:
                return False

            item = items[0]
            sk = item["SK"]["S"]
            current_expiry = datetime.fromisoformat(item["expires_at"]["S"])
            new_expiry = current_expiry + timedelta(hours=extension_hours)

            # Update expiry
            client.update_item(
                TableName=self.config.table_name,
                Key={
                    "PK": {"S": f"GRANT#{agent_id}"},
                    "SK": {"S": sk},
                },
                UpdateExpression=(
                    "SET expires_at = :expires_at, "
                    "TTL = :ttl, "
                    "extended_by = :extended_by, "
                    "extended_at = :extended_at"
                ),
                ConditionExpression="revoked = :false",
                ExpressionAttributeValues={
                    ":expires_at": {"S": new_expiry.isoformat()},
                    ":ttl": {"N": str(int(new_expiry.timestamp()))},
                    ":extended_by": {"S": extended_by},
                    ":extended_at": {"S": datetime.now(timezone.utc).isoformat()},
                    ":false": {"BOOL": False},
                },
            )

            self._invalidate_cache(agent_id)
            logger.info(
                f"Extended grant {grant_id} by {extension_hours} hours "
                f"(new_expiry={new_expiry.isoformat()})"
            )
            return True

        except client.exceptions.ConditionalCheckFailedException:
            logger.warning(f"Cannot extend revoked grant: {grant_id}")
            return False
        except Exception as e:
            logger.error(f"Failed to extend grant: {e}")
            return False

    def _invalidate_cache(self, agent_id: str) -> None:
        """Invalidate cache for an agent."""
        if agent_id in self._grant_cache:
            del self._grant_cache[agent_id]
        if agent_id in self._cache_timestamps:
            del self._cache_timestamps[agent_id]

    async def _cleanup_loop(self) -> None:
        """Background task to clean up expired grants from cache."""
        while self._running:
            try:
                await asyncio.sleep(self.config.cleanup_interval_seconds)

                # Clean up expired grants from cache
                now = time.time()
                expired_agents = []

                for agent_id, timestamp in self._cache_timestamps.items():
                    if now - timestamp > self.config.cache_ttl_seconds * 2:
                        expired_agents.append(agent_id)

                for agent_id in expired_agents:
                    self._invalidate_cache(agent_id)
                    self._grants_expired += 1

                if expired_agents:
                    logger.debug(f"Cleaned up cache for {len(expired_agents)} agents")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

    def get_metrics(self) -> dict[str, Any]:
        """Get grant manager metrics."""
        return {
            "grants_created": self._grants_created,
            "grants_used": self._grants_used,
            "grants_revoked": self._grants_revoked,
            "grants_expired": self._grants_expired,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_size": len(self._grant_cache),
        }


# =============================================================================
# Global Manager Singleton
# =============================================================================

_grant_manager: Optional[DynamicGrantManager] = None


def get_grant_manager() -> DynamicGrantManager:
    """Get the global grant manager instance."""
    global _grant_manager
    if _grant_manager is None:
        _grant_manager = DynamicGrantManager()
    return _grant_manager


def reset_grant_manager() -> None:
    """Reset the global grant manager (for testing)."""
    global _grant_manager
    _grant_manager = None
