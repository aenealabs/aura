"""
Project Aura - ABAC Authorization Service

Attribute-Based Access Control service for multi-tenant authorization.
Implements ADR-073 with support for both OPA and AWS Verified Permissions.

Features:
- Attribute resolution from JWT, DynamoDB, and resource tags
- Policy evaluation against ABAC rules
- Caching for performance (TTL-based)
- Audit logging for compliance
"""

import logging
import time
from collections import OrderedDict, deque
from datetime import datetime
from typing import Any, Callable

from .abac_contracts import (
    ACTION_ROLE_MAPPING,
    AttributeContext,
    AuthorizationDecision,
    ContextAttributes,
    ResourceAttributes,
    SensitivityLevel,
    SubjectAttributes,
)

logger = logging.getLogger(__name__)


class AttributeCache:
    """Simple TTL-based cache for attribute resolution using OrderedDict for O(1) eviction."""

    def __init__(self, ttl_seconds: int = 300, max_size: int = 10000):
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._ttl = ttl_seconds
        self._max_size = max_size

    def get(self, key: str) -> Any | None:
        """Get cached value if not expired."""
        if key not in self._cache:
            return None

        value, timestamp = self._cache[key]
        if time.time() - timestamp > self._ttl:
            del self._cache[key]
            return None

        # Move to end (most recently accessed)
        self._cache.move_to_end(key)
        return value

    def set(self, key: str, value: Any) -> None:
        """Set value in cache."""
        if key in self._cache:
            # Update existing entry and move to end
            self._cache[key] = (value, time.time())
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self._max_size:
                # Evict oldest entries (first items in OrderedDict) - O(1) per eviction
                evict_count = self._max_size // 4
                for _ in range(min(evict_count, len(self._cache))):
                    self._cache.popitem(last=False)

            self._cache[key] = (value, time.time())

    def invalidate(self, key: str) -> None:
        """Invalidate a cache entry."""
        if key in self._cache:
            del self._cache[key]

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()


class ABACAuthorizationService:
    """
    Attribute-Based Access Control authorization service.

    Evaluates authorization requests against ABAC policies using:
    - Subject attributes (user/principal)
    - Resource attributes (target object)
    - Context attributes (environment)
    - Action being performed

    Supports:
    - Built-in policy evaluation (default)
    - OPA policy evaluation (optional)
    - AWS Verified Permissions (optional)
    """

    def __init__(
        self,
        dynamodb_client: Any | None = None,
        opa_url: str | None = None,
        verified_permissions_client: Any | None = None,
        policy_store_id: str | None = None,
        cache_ttl_seconds: int = 300,
    ):
        """
        Initialize the ABAC service.

        Args:
            dynamodb_client: Boto3 DynamoDB client for user profiles
            opa_url: URL of OPA policy engine (if using OPA)
            verified_permissions_client: Boto3 Verified Permissions client
            policy_store_id: AWS Verified Permissions policy store ID
            cache_ttl_seconds: TTL for attribute cache
        """
        self.dynamodb = dynamodb_client
        self.opa_url = opa_url
        self.avp_client = verified_permissions_client
        self.policy_store_id = policy_store_id
        self._attribute_cache = AttributeCache(ttl_seconds=cache_ttl_seconds)
        self._decision_cache = AttributeCache(
            ttl_seconds=60
        )  # Shorter TTL for decisions
        self._audit_log: deque[dict[str, Any]] = deque(maxlen=10000)

        # Resource tag resolver (can be overridden)
        self._tag_resolver: Callable[[str], dict[str, str]] | None = None

    def set_tag_resolver(self, resolver: Callable[[str], dict[str, str]]) -> None:
        """Set custom resource tag resolver."""
        self._tag_resolver = resolver

    async def authorize(
        self,
        jwt_claims: dict[str, Any],
        action: str,
        resource_arn: str,
        request_context: dict[str, Any] | None = None,
    ) -> AuthorizationDecision:
        """
        Evaluate authorization request against ABAC policies.

        Args:
            jwt_claims: Decoded JWT claims from Cognito
            action: The action being requested (e.g., "view_vulnerabilities")
            resource_arn: ARN of the target resource
            request_context: Additional context (IP, time, device info)

        Returns:
            AuthorizationDecision with allow/deny and explanation
        """
        start_time = time.time()
        request_context = request_context or {}

        try:
            # Resolve all attributes
            attr_context = await self._resolve_attributes(
                jwt_claims, action, resource_arn, request_context
            )

            # Evaluate policy
            if self.avp_client and self.policy_store_id:
                decision = await self._evaluate_verified_permissions(attr_context)
            elif self.opa_url:
                decision = await self._evaluate_opa(attr_context)
            else:
                decision = await self._evaluate_builtin(attr_context)

            decision.action = action
            decision.resource_arn = resource_arn
            decision.evaluation_time_ms = (time.time() - start_time) * 1000

            # Audit log
            await self._audit_decision(attr_context, decision)

            return decision

        except Exception as e:
            logger.error(f"Authorization error: {e}")
            return AuthorizationDecision(
                allowed=False,
                action=action,
                resource_arn=resource_arn,
                explanation=f"Authorization error: {str(e)}",
                evaluation_time_ms=(time.time() - start_time) * 1000,
            )

    async def _resolve_attributes(
        self,
        jwt_claims: dict[str, Any],
        action: str,
        resource_arn: str,
        request_context: dict[str, Any],
    ) -> AttributeContext:
        """Resolve all attributes from their sources."""
        # Subject attributes from JWT + DynamoDB
        subject = await self._resolve_subject(jwt_claims)

        # Resource attributes from tags/metadata
        resource = await self._resolve_resource(resource_arn)

        # Context attributes from request
        context = ContextAttributes.from_request(request_context)

        return AttributeContext(
            subject=subject,
            resource=resource,
            context=context,
            action=action,
        )

    async def _resolve_subject(self, jwt_claims: dict[str, Any]) -> SubjectAttributes:
        """Resolve subject attributes from JWT and DynamoDB."""
        user_id = jwt_claims.get("sub", "")

        # Check cache
        cache_key = f"subject:{user_id}"
        cached = self._attribute_cache.get(cache_key)
        if cached:
            return cached

        # Get extended attributes from DynamoDB if available
        extended_attrs = {}
        if self.dynamodb:
            try:
                response = await self._async_dynamodb_get(
                    table_name="UserProfiles",
                    key={"user_id": {"S": user_id}},
                )
                if "Item" in response:
                    item = response["Item"]
                    extended_attrs = {
                        k: v.get("S") or v.get("N") or v.get("BOOL")
                        for k, v in item.items()
                    }
            except Exception as e:
                logger.warning(f"Failed to get user profile: {e}")

        subject = SubjectAttributes.from_jwt_claims(jwt_claims, extended_attrs)

        # Cache result
        self._attribute_cache.set(cache_key, subject)

        return subject

    async def _async_dynamodb_get(
        self, table_name: str, key: dict[str, Any]
    ) -> dict[str, Any]:
        """Async wrapper for DynamoDB get_item."""
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.dynamodb.get_item(TableName=table_name, Key=key),
        )

    async def _resolve_resource(self, resource_arn: str) -> ResourceAttributes:
        """Resolve resource attributes from tags and metadata."""
        # Check cache
        cache_key = f"resource:{resource_arn}"
        cached = self._attribute_cache.get(cache_key)
        if cached:
            return cached

        # Get resource tags
        tags = {}
        if self._tag_resolver:
            try:
                tags = self._tag_resolver(resource_arn)
            except Exception as e:
                logger.warning(f"Failed to resolve resource tags: {e}")

        resource = ResourceAttributes.from_arn(resource_arn, tags)

        # Cache result
        self._attribute_cache.set(cache_key, resource)

        return resource

    async def _evaluate_builtin(
        self, attr_context: AttributeContext
    ) -> AuthorizationDecision:
        """Evaluate using built-in ABAC rules."""
        matched_policies = []

        # Rule 1: Check basic role permission (RBAC foundation)
        allowed_roles = ACTION_ROLE_MAPPING.get(attr_context.action, [])
        has_role = any(role in attr_context.subject.roles for role in allowed_roles)

        if not has_role:
            return AuthorizationDecision(
                allowed=False,
                explanation=(
                    f"Action '{attr_context.action}' requires one of roles: "
                    f"{allowed_roles}, but user has: {attr_context.subject.roles}"
                ),
                matched_policies=["rbac_role_check:deny"],
            )
        matched_policies.append("rbac_role_check:permit")

        # Rule 2: Tenant isolation (ABAC extension)
        tenant_match = self._check_tenant_isolation(attr_context)
        if not tenant_match:
            return AuthorizationDecision(
                allowed=False,
                explanation=(
                    f"Tenant isolation violation: user tenant "
                    f"'{attr_context.subject.tenant_id}' cannot access resource "
                    f"in tenant '{attr_context.resource.tenant_id}'"
                ),
                matched_policies=matched_policies + ["tenant_isolation:deny"],
            )
        matched_policies.append("tenant_isolation:permit")

        # Rule 3: Clearance level check
        clearance_ok = self._check_clearance(attr_context)
        if not clearance_ok:
            return AuthorizationDecision(
                allowed=False,
                explanation=(
                    f"Insufficient clearance: user has "
                    f"'{attr_context.subject.clearance_level.value}' but resource "
                    f"requires '{attr_context.resource.sensitivity.value}'"
                ),
                matched_policies=matched_policies + ["clearance_check:deny"],
            )
        matched_policies.append("clearance_check:permit")

        # Rule 4: MFA requirement for sensitive resources
        mfa_ok = self._check_mfa_requirement(attr_context)
        if not mfa_ok:
            return AuthorizationDecision(
                allowed=False,
                explanation=(
                    f"MFA required for accessing "
                    f"'{attr_context.resource.sensitivity.value}' resources"
                ),
                matched_policies=matched_policies + ["mfa_requirement:deny"],
            )
        matched_policies.append("mfa_requirement:permit")

        # Rule 5: Business hours check for certain actions
        business_hours_ok = self._check_business_hours(attr_context)
        if not business_hours_ok:
            return AuthorizationDecision(
                allowed=False,
                explanation=(
                    f"Action '{attr_context.action}' is only allowed during "
                    "business hours (8am-6pm)"
                ),
                matched_policies=matched_policies + ["business_hours:deny"],
            )
        matched_policies.append("business_hours:permit")

        return AuthorizationDecision(
            allowed=True,
            explanation="All policy checks passed",
            matched_policies=matched_policies,
            policy_version="builtin-1.0",
        )

    def _check_tenant_isolation(self, attr_context: AttributeContext) -> bool:
        """Check tenant isolation rule."""
        # Platform admins can access any tenant (with MFA)
        if "platform-admin" in attr_context.subject.roles:
            return attr_context.context.mfa_verified

        # Empty tenant on resource means no isolation required
        if not attr_context.resource.tenant_id:
            return True

        # User tenant must match resource tenant
        return attr_context.subject.tenant_id == attr_context.resource.tenant_id

    def _check_clearance(self, attr_context: AttributeContext) -> bool:
        """Check clearance level against resource sensitivity."""
        user_level = attr_context.subject.clearance_level.numeric_level
        resource_level = attr_context.resource.sensitivity.numeric_level
        return user_level >= resource_level

    def _check_mfa_requirement(self, attr_context: AttributeContext) -> bool:
        """Check MFA requirement for sensitive resources."""
        sensitive_levels = [
            SensitivityLevel.CONFIDENTIAL,
            SensitivityLevel.RESTRICTED,
            SensitivityLevel.TOP_LEVEL,
        ]

        if attr_context.resource.sensitivity in sensitive_levels:
            return attr_context.context.mfa_verified

        return True

    def _check_business_hours(self, attr_context: AttributeContext) -> bool:
        """Check business hours restriction for certain actions."""
        restricted_actions = ["approve_patch", "deploy_production"]

        if attr_context.action in restricted_actions:
            return attr_context.context.is_business_hours()

        return True

    async def _evaluate_opa(
        self, attr_context: AttributeContext
    ) -> AuthorizationDecision:
        """Evaluate policy against OPA."""
        import httpx

        input_data = {"input": attr_context.to_dict()}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.opa_url}/v1/data/aura/authz/allow",
                    json=input_data,
                    timeout=1.0,
                )

            result = response.json()
            allowed = result.get("result", False)

            return AuthorizationDecision(
                allowed=allowed,
                explanation=(
                    "OPA policy evaluation" if allowed else "Denied by OPA policy"
                ),
                policy_version="opa",
            )

        except Exception as e:
            logger.error(f"OPA evaluation failed: {e}")
            # Fallback to builtin on OPA failure
            return await self._evaluate_builtin(attr_context)

    async def _evaluate_verified_permissions(
        self, attr_context: AttributeContext
    ) -> AuthorizationDecision:
        """Evaluate policy using AWS Verified Permissions."""
        try:
            response = self.avp_client.is_authorized(
                policyStoreId=self.policy_store_id,
                principal={
                    "entityType": "Aura::User",
                    "entityId": attr_context.subject.user_id,
                },
                action={
                    "actionType": "Aura::Action",
                    "actionId": attr_context.action,
                },
                resource={
                    "entityType": "Aura::Resource",
                    "entityId": attr_context.resource.resource_id,
                },
                context={
                    "contextMap": {
                        "tenant_id": {"string": attr_context.subject.tenant_id},
                        "mfa_verified": {"boolean": attr_context.context.mfa_verified},
                        "clearance_level": {
                            "string": attr_context.subject.clearance_level.value
                        },
                    }
                },
            )

            allowed = response.get("decision") == "ALLOW"

            return AuthorizationDecision(
                allowed=allowed,
                explanation=(
                    "Verified Permissions evaluation"
                    if allowed
                    else "Denied by Verified Permissions policy"
                ),
                policy_version=self.policy_store_id or "",
            )

        except Exception as e:
            logger.error(f"Verified Permissions evaluation failed: {e}")
            # Fallback to builtin on AVP failure
            return await self._evaluate_builtin(attr_context)

    async def _audit_decision(
        self,
        attr_context: AttributeContext,
        decision: AuthorizationDecision,
    ) -> None:
        """Log authorization decision for audit trail."""
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": attr_context.subject.user_id,
            "tenant_id": attr_context.subject.tenant_id,
            "action": attr_context.action,
            "resource_type": attr_context.resource.resource_type,
            "resource_id": attr_context.resource.resource_id,
            "allowed": decision.allowed,
            "explanation": decision.explanation,
            "matched_policies": decision.matched_policies,
            "evaluation_time_ms": decision.evaluation_time_ms,
            "source_ip": attr_context.context.source_ip,
            "mfa_verified": attr_context.context.mfa_verified,
        }

        self._audit_log.append(audit_entry)

        logger.info(
            f"ABAC decision: user={attr_context.subject.user_id} "
            f"action={attr_context.action} allowed={decision.allowed}"
        )

    async def check_permission(
        self,
        jwt_claims: dict[str, Any],
        action: str,
        resource_arn: str,
    ) -> bool:
        """Simple permission check (returns bool only)."""
        decision = await self.authorize(jwt_claims, action, resource_arn)
        return decision.allowed

    def get_audit_log(
        self,
        user_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get audit log entries, optionally filtered by user."""
        logs = list(self._audit_log)
        if user_id:
            logs = [log for log in logs if log["user_id"] == user_id]
        return logs[-limit:]

    def invalidate_cache(self, user_id: str | None = None) -> None:
        """Invalidate attribute cache."""
        if user_id:
            self._attribute_cache.invalidate(f"subject:{user_id}")
        else:
            self._attribute_cache.clear()


# Singleton instance
_service_instance: ABACAuthorizationService | None = None


def get_abac_service() -> ABACAuthorizationService:
    """Get or create the singleton ABAC service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = ABACAuthorizationService()
    return _service_instance


def reset_abac_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _service_instance
    _service_instance = None
