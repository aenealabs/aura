"""
Export Authorization Service - Row-level security for data exports.

This module enforces authorization controls on all data exports to ensure
users and integrations can only access data they are permitted to see.
Implements row-level security based on organization membership and roles.

ADR Reference: ADR-048 Security Considerations - High Control #3
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ExportScope(Enum):
    """Scope of data export permission."""

    ORGANIZATION = "organization"  # All data within organization
    REPOSITORY = "repository"  # Specific repositories only
    PROJECT = "project"  # Specific projects only
    PERSONAL = "personal"  # Only user's own data


class ExportRole(Enum):
    """Roles that determine export permissions."""

    ADMIN = "admin"  # Full access to all organization data
    MANAGER = "manager"  # Access to assigned repositories/projects
    ANALYST = "analyst"  # Read-only access to specific data
    VIEWER = "viewer"  # Limited read access
    INTEGRATION = "integration"  # Service account for integrations


class ExportDataType(Enum):
    """Types of data that can be exported."""

    FINDINGS = "findings"  # Security vulnerability findings
    PATCHES = "patches"  # Generated patches
    APPROVALS = "approvals"  # HITL approval records
    METRICS = "metrics"  # Security KPIs and metrics
    AGENTS = "agents"  # Agent activity logs
    AUDIT = "audit"  # Audit trail
    REPOSITORIES = "repositories"  # Repository metadata
    USERS = "users"  # User information (limited fields)


@dataclass
class ExportRequest:
    """Request for data export."""

    requester_id: str  # User or service account ID
    organization_id: str
    data_type: ExportDataType
    scope: ExportScope = ExportScope.ORGANIZATION
    scope_ids: list[str] = field(default_factory=list)  # Specific repos/projects
    fields: list[str] | None = None  # Optional field filter
    filters: dict[str, Any] = field(default_factory=dict)  # Query filters
    limit: int = 10000
    offset: int = 0
    include_pii: bool = False  # Whether to include PII fields

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "requester_id": self.requester_id,
            "organization_id": self.organization_id,
            "data_type": self.data_type.value,
            "scope": self.scope.value,
            "scope_ids": self.scope_ids,
            "limit": self.limit,
            "include_pii": self.include_pii,
        }


@dataclass
class AuthorizationResult:
    """Result of authorization check."""

    authorized: bool
    allowed_scope: ExportScope | None = None
    allowed_scope_ids: list[str] = field(default_factory=list)
    denied_reason: str | None = None
    field_restrictions: list[str] = field(default_factory=list)  # Fields to exclude
    row_filter: dict[str, Any] = field(default_factory=dict)  # Additional filters

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        result = {
            "authorized": self.authorized,
        }
        if self.authorized:
            result["allowed_scope"] = (
                self.allowed_scope.value if self.allowed_scope else None
            )
            result["allowed_scope_ids"] = self.allowed_scope_ids
            if self.field_restrictions:
                result["field_restrictions"] = self.field_restrictions
        else:
            result["denied_reason"] = self.denied_reason
        return result


# PII fields that require explicit permission
PII_FIELDS: dict[ExportDataType, list[str]] = {
    ExportDataType.USERS: ["email", "full_name", "phone"],
    ExportDataType.APPROVALS: ["approver_email", "requester_email"],
    ExportDataType.AUDIT: ["user_email", "ip_address", "user_agent"],
}

# Fields always excluded from exports (secrets, internal data)
ALWAYS_EXCLUDED_FIELDS: dict[ExportDataType, list[str]] = {
    ExportDataType.FINDINGS: ["raw_code_snippet"],  # May contain secrets
    ExportDataType.PATCHES: ["patch_content_raw"],  # May contain secrets
    ExportDataType.AGENTS: ["internal_state", "credentials"],
    ExportDataType.AUDIT: ["session_token", "auth_token"],
}

# Role permissions matrix
ROLE_PERMISSIONS: dict[ExportRole, dict[str, Any]] = {
    ExportRole.ADMIN: {
        "allowed_types": list(ExportDataType),
        "max_scope": ExportScope.ORGANIZATION,
        "can_include_pii": True,
        "max_limit": 100000,
    },
    ExportRole.MANAGER: {
        "allowed_types": [
            ExportDataType.FINDINGS,
            ExportDataType.PATCHES,
            ExportDataType.APPROVALS,
            ExportDataType.METRICS,
            ExportDataType.REPOSITORIES,
        ],
        "max_scope": ExportScope.REPOSITORY,
        "can_include_pii": False,
        "max_limit": 50000,
    },
    ExportRole.ANALYST: {
        "allowed_types": [
            ExportDataType.FINDINGS,
            ExportDataType.METRICS,
            ExportDataType.REPOSITORIES,
        ],
        "max_scope": ExportScope.REPOSITORY,
        "can_include_pii": False,
        "max_limit": 25000,
    },
    ExportRole.VIEWER: {
        "allowed_types": [
            ExportDataType.METRICS,
        ],
        "max_scope": ExportScope.ORGANIZATION,
        "can_include_pii": False,
        "max_limit": 10000,
    },
    ExportRole.INTEGRATION: {
        "allowed_types": [
            ExportDataType.FINDINGS,
            ExportDataType.PATCHES,
            ExportDataType.APPROVALS,
            ExportDataType.METRICS,
            ExportDataType.AGENTS,
        ],
        "max_scope": ExportScope.ORGANIZATION,
        "can_include_pii": False,
        "max_limit": 100000,
    },
}


class ExportAuthorizationService:
    """
    Service for authorizing data export requests.

    Enforces row-level security based on:
    - User/service account role
    - Organization membership
    - Repository/project access
    - Data type sensitivity
    """

    def __init__(
        self,
        user_service: Any | None = None,
        organization_service: Any | None = None,
        enable_audit_logging: bool = True,
    ):
        """
        Initialize the authorization service.

        Args:
            user_service: Service for user role lookups (injectable)
            organization_service: Service for org membership lookups
            enable_audit_logging: Whether to log authorization decisions
        """
        self._user_service = user_service
        self._organization_service = organization_service
        self._enable_audit = enable_audit_logging

    async def authorize(
        self,
        request: ExportRequest,
        requester_role: ExportRole | None = None,
        requester_orgs: list[str] | None = None,
        requester_repos: list[str] | None = None,
    ) -> AuthorizationResult:
        """
        Authorize an export request.

        Args:
            request: The export request to authorize
            requester_role: Role of the requester (or will be looked up)
            requester_orgs: Organizations the requester belongs to
            requester_repos: Repositories the requester has access to

        Returns:
            AuthorizationResult indicating whether export is allowed
        """
        # Get requester context if not provided
        if requester_role is None:
            requester_role = await self._get_requester_role(request.requester_id)

        if requester_orgs is None:
            requester_orgs = await self._get_requester_orgs(request.requester_id)

        if requester_repos is None:
            requester_repos = await self._get_requester_repos(
                request.requester_id, request.organization_id
            )

        # Check organization membership
        if request.organization_id not in requester_orgs:
            result = AuthorizationResult(
                authorized=False,
                denied_reason="User is not a member of the requested organization",
            )
            self._log_decision(request, result)
            return result

        # Get role permissions
        permissions = ROLE_PERMISSIONS.get(requester_role)
        if not permissions:
            result = AuthorizationResult(
                authorized=False,
                denied_reason=f"Unknown role: {requester_role}",
            )
            self._log_decision(request, result)
            return result

        # Check data type permission
        if request.data_type not in permissions["allowed_types"]:
            result = AuthorizationResult(
                authorized=False,
                denied_reason=f"Role {requester_role.value} cannot export {request.data_type.value}",
            )
            self._log_decision(request, result)
            return result

        # Check scope permission
        allowed_scope = self._resolve_scope(
            request.scope,
            permissions["max_scope"],
            request.scope_ids,
            requester_repos,
        )

        if allowed_scope is None:
            result = AuthorizationResult(
                authorized=False,
                denied_reason="Requested scope exceeds permitted access",
            )
            self._log_decision(request, result)
            return result

        # Check PII permission
        if request.include_pii and not permissions["can_include_pii"]:
            result = AuthorizationResult(
                authorized=False,
                denied_reason="Role cannot export PII fields",
            )
            self._log_decision(request, result)
            return result

        # Build field restrictions
        field_restrictions = self._get_field_restrictions(
            request.data_type,
            request.include_pii,
            permissions["can_include_pii"],
        )

        # Build row filter for scoped access
        row_filter = self._build_row_filter(
            allowed_scope,
            request.organization_id,
            (
                allowed_scope.get("scope_ids", [])
                if isinstance(allowed_scope, dict)
                else []
            ),
        )

        # Enforce limit (stored for future use in pagination)
        _ = min(request.limit, permissions["max_limit"])

        result = AuthorizationResult(
            authorized=True,
            allowed_scope=(
                allowed_scope
                if isinstance(allowed_scope, ExportScope)
                else request.scope
            ),
            allowed_scope_ids=(
                allowed_scope.get("scope_ids", [])
                if isinstance(allowed_scope, dict)
                else request.scope_ids
            ),
            field_restrictions=field_restrictions,
            row_filter=row_filter,
        )

        self._log_decision(request, result)
        return result

    def _resolve_scope(
        self,
        requested_scope: ExportScope,
        max_scope: ExportScope,
        requested_ids: list[str],
        allowed_repos: list[str],
    ) -> ExportScope | dict[str, Any] | None:
        """Resolve the effective scope for the export."""
        scope_hierarchy = [
            ExportScope.PERSONAL,
            ExportScope.PROJECT,
            ExportScope.REPOSITORY,
            ExportScope.ORGANIZATION,
        ]

        requested_idx = scope_hierarchy.index(requested_scope)
        max_idx = scope_hierarchy.index(max_scope)

        if requested_idx > max_idx:
            # Requested broader scope than allowed
            return None

        # For repository/project scope, filter to allowed repos
        if requested_scope in [ExportScope.REPOSITORY, ExportScope.PROJECT]:
            if requested_ids:
                allowed_ids = [r for r in requested_ids if r in allowed_repos]
                if not allowed_ids:
                    return None
                return {"scope": requested_scope, "scope_ids": allowed_ids}
            else:
                # No specific IDs, use all allowed repos
                return {"scope": requested_scope, "scope_ids": allowed_repos}

        return requested_scope

    def _get_field_restrictions(
        self,
        data_type: ExportDataType,
        include_pii: bool,
        can_include_pii: bool,
    ) -> list[str]:
        """Get list of fields to exclude from export."""
        restrictions = []

        # Always exclude sensitive internal fields
        if data_type in ALWAYS_EXCLUDED_FIELDS:
            restrictions.extend(ALWAYS_EXCLUDED_FIELDS[data_type])

        # Exclude PII if not permitted
        if not include_pii or not can_include_pii:
            if data_type in PII_FIELDS:
                restrictions.extend(PII_FIELDS[data_type])

        return restrictions

    def _build_row_filter(
        self,
        scope: ExportScope | dict[str, Any],
        organization_id: str,
        scope_ids: list[str],
    ) -> dict[str, Any]:
        """Build row-level filter for data access."""
        filters: dict[str, Any] = {
            "organization_id": organization_id,
        }

        if isinstance(scope, dict):
            effective_scope = scope.get("scope", ExportScope.ORGANIZATION)
            scope_ids = scope.get("scope_ids", [])
        else:
            effective_scope = scope

        if effective_scope == ExportScope.REPOSITORY and scope_ids:
            filters["repository_id"] = {"$in": scope_ids}
        elif effective_scope == ExportScope.PROJECT and scope_ids:
            filters["project_id"] = {"$in": scope_ids}

        return filters

    async def _get_requester_role(self, requester_id: str) -> ExportRole:
        """Get role for requester from user service."""
        if self._user_service:
            # Real implementation would call user service
            role_str = await self._user_service.get_user_role(requester_id)
            return ExportRole(role_str)
        # Default to viewer for safety
        return ExportRole.VIEWER

    async def _get_requester_orgs(self, requester_id: str) -> list[str]:
        """Get organizations for requester."""
        if self._organization_service:
            return await self._organization_service.get_user_organizations(requester_id)
        return []

    async def _get_requester_repos(
        self, requester_id: str, organization_id: str
    ) -> list[str]:
        """Get repositories accessible to requester in organization."""
        if self._organization_service:
            return await self._organization_service.get_user_repositories(
                requester_id, organization_id
            )
        return []

    def _log_decision(
        self, request: ExportRequest, result: AuthorizationResult
    ) -> None:
        """Log authorization decision for audit trail."""
        if not self._enable_audit:
            return

        log_data = {
            "event_type": "export_authorization",
            "requester_id": request.requester_id,
            "organization_id": request.organization_id,
            "data_type": request.data_type.value,
            "scope": request.scope.value,
            "authorized": result.authorized,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if result.authorized:
            log_data["allowed_scope"] = (
                result.allowed_scope.value if result.allowed_scope else None
            )
            logger.info("Export authorized", extra=log_data)
        else:
            log_data["denied_reason"] = result.denied_reason
            logger.warning("Export denied", extra=log_data)


def filter_export_data(
    data: list[dict[str, Any]],
    auth_result: AuthorizationResult,
) -> list[dict[str, Any]]:
    """
    Apply authorization result to filter exported data.

    Args:
        data: Raw data to filter
        auth_result: Authorization result with field restrictions

    Returns:
        Filtered data with restricted fields removed
    """
    if not auth_result.authorized:
        return []

    filtered = []
    for row in data:
        filtered_row = {
            k: v for k, v in row.items() if k not in auth_result.field_restrictions
        }
        filtered.append(filtered_row)

    return filtered
