"""
Project Aura - ABAC Contracts

Dataclasses for Attribute-Based Access Control.
Implements ADR-073 for multi-tenant user authorization.

Attribute Categories:
- Subject: User/principal attributes (from JWT + DynamoDB)
- Resource: Target object attributes (from tags/metadata)
- Context: Environmental attributes (from request)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ClearanceLevel(Enum):
    """Security clearance levels for users."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    TOP_LEVEL = "top_level"  # Highest clearance

    @property
    def numeric_level(self) -> int:
        """Get numeric level for comparison."""
        levels = {
            "public": 0,
            "internal": 1,
            "confidential": 2,
            "restricted": 3,
            "top_level": 4,
        }
        return levels.get(self.value, 0)

    def __ge__(self, other: "ClearanceLevel") -> bool:
        return self.numeric_level >= other.numeric_level

    def __gt__(self, other: "ClearanceLevel") -> bool:
        return self.numeric_level > other.numeric_level

    def __le__(self, other: "ClearanceLevel") -> bool:
        return self.numeric_level <= other.numeric_level

    def __lt__(self, other: "ClearanceLevel") -> bool:
        return self.numeric_level < other.numeric_level


class SensitivityLevel(Enum):
    """Sensitivity levels for resources."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    TOP_LEVEL = "top_level"  # Highest sensitivity

    @property
    def numeric_level(self) -> int:
        """Get numeric level for comparison."""
        levels = {
            "public": 0,
            "internal": 1,
            "confidential": 2,
            "restricted": 3,
            "top_level": 4,
        }
        return levels.get(self.value, 0)


class DeviceTrust(Enum):
    """Device trust levels."""

    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    MANAGED = "managed"


class AuthMethod(Enum):
    """Authentication methods."""

    BASIC = "basic"  # Username/credential authentication
    MFA = "mfa"
    SSO = "sso"
    API_KEY = "api_key"
    SERVICE_ACCOUNT = "service_account"


@dataclass
class SubjectAttributes:
    """
    Subject (user/principal) attributes for authorization decisions.

    Sources:
    - JWT claims from Cognito
    - Extended attributes from DynamoDB UserProfiles table
    """

    user_id: str
    tenant_id: str
    roles: list[str] = field(default_factory=list)
    department: str | None = None
    clearance_level: ClearanceLevel = ClearanceLevel.INTERNAL
    risk_score: float = 0.0
    organization: str = ""
    email: str | None = None
    groups: list[str] = field(default_factory=list)
    mfa_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for policy evaluation."""
        return {
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "roles": self.roles,
            "department": self.department,
            "clearance_level": self.clearance_level.value,
            "risk_score": self.risk_score,
            "organization": self.organization,
            "email": self.email,
            "groups": self.groups,
            "mfa_enabled": self.mfa_enabled,
        }

    @classmethod
    def from_jwt_claims(
        cls,
        claims: dict[str, Any],
        extended_attrs: dict[str, Any] | None = None,
    ) -> "SubjectAttributes":
        """Create from JWT claims and optional extended attributes."""
        extended = extended_attrs or {}

        clearance_str = extended.get("clearance_level", "internal")
        try:
            clearance = ClearanceLevel(clearance_str)
        except ValueError:
            clearance = ClearanceLevel.INTERNAL

        return cls(
            user_id=claims.get("sub", ""),
            tenant_id=claims.get("custom:tenant_id", extended.get("tenant_id", "")),
            roles=claims.get("cognito:groups", []),
            department=extended.get("department"),
            clearance_level=clearance,
            risk_score=float(extended.get("risk_score", 0.0)),
            organization=extended.get("organization", ""),
            email=claims.get("email"),
            groups=claims.get("cognito:groups", []),
            mfa_enabled=extended.get("mfa_enabled", False),
        )


@dataclass
class ResourceAttributes:
    """
    Resource (target object) attributes for authorization decisions.

    Sources:
    - Resource tags (S3, DynamoDB, Neptune)
    - Resource metadata from ARN parsing
    """

    resource_type: str
    resource_id: str
    tenant_id: str
    sensitivity: SensitivityLevel = SensitivityLevel.INTERNAL
    owner_id: str = ""
    classification: str = ""
    tags: dict[str, str] = field(default_factory=dict)
    environment: str = "production"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for policy evaluation."""
        return {
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "tenant_id": self.tenant_id,
            "sensitivity": self.sensitivity.value,
            "owner_id": self.owner_id,
            "classification": self.classification,
            "tags": self.tags,
            "environment": self.environment,
        }

    @classmethod
    def from_arn(
        cls, arn: str, tags: dict[str, str] | None = None
    ) -> "ResourceAttributes":
        """Create from ARN and optional tags."""
        tags = tags or {}

        # Parse ARN: arn:aws:service:region:account:resource-type/resource-id
        parts = arn.split(":")
        if len(parts) >= 6:
            resource_part = parts[5]
            if "/" in resource_part:
                resource_type, resource_id = resource_part.split("/", 1)
            else:
                resource_type = resource_part
                resource_id = ""
        else:
            resource_type = "unknown"
            resource_id = arn

        sensitivity_str = tags.get("sensitivity", "internal")
        try:
            sensitivity = SensitivityLevel(sensitivity_str)
        except ValueError:
            sensitivity = SensitivityLevel.INTERNAL

        return cls(
            resource_type=resource_type,
            resource_id=resource_id,
            tenant_id=tags.get("tenant_id", ""),
            sensitivity=sensitivity,
            owner_id=tags.get("owner_id", ""),
            classification=tags.get("classification", ""),
            tags=tags,
            environment=tags.get("environment", "production"),
        )


@dataclass
class ContextAttributes:
    """
    Context (environmental) attributes for authorization decisions.

    Sources:
    - Request metadata (IP, headers)
    - Session information
    - Time-based attributes
    """

    request_time: datetime = field(default_factory=datetime.utcnow)
    source_ip: str = ""
    device_trust: DeviceTrust = DeviceTrust.UNKNOWN
    session_risk: float = 0.0
    mfa_verified: bool = False
    auth_method: AuthMethod = AuthMethod.BASIC
    user_agent: str = ""
    request_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for policy evaluation."""
        return {
            "request_time": self.request_time.isoformat(),
            "source_ip": self.source_ip,
            "device_trust": self.device_trust.value,
            "session_risk": self.session_risk,
            "mfa_verified": self.mfa_verified,
            "auth_method": self.auth_method.value,
            "user_agent": self.user_agent,
            "request_id": self.request_id,
        }

    @classmethod
    def from_request(cls, request_context: dict[str, Any]) -> "ContextAttributes":
        """Create from request context dictionary."""
        device_trust_str = request_context.get("device_trust", "unknown")
        try:
            device_trust = DeviceTrust(device_trust_str)
        except ValueError:
            device_trust = DeviceTrust.UNKNOWN

        auth_method_str = request_context.get("auth_method", "password")
        try:
            auth_method = AuthMethod(auth_method_str)
        except ValueError:
            auth_method = AuthMethod.BASIC

        request_time = request_context.get("request_time")
        if isinstance(request_time, str):
            try:
                request_time = datetime.fromisoformat(request_time)
            except ValueError:
                request_time = datetime.utcnow()
        elif request_time is None:
            request_time = datetime.utcnow()

        return cls(
            request_time=request_time,
            source_ip=request_context.get("source_ip", ""),
            device_trust=device_trust,
            session_risk=float(request_context.get("session_risk", 0.0)),
            mfa_verified=request_context.get("mfa_verified", False),
            auth_method=auth_method,
            user_agent=request_context.get("user_agent", ""),
            request_id=request_context.get("request_id", ""),
        )

    def is_business_hours(self, timezone_offset: int = 0) -> bool:
        """Check if request is during business hours (8am-6pm)."""
        adjusted_hour = (self.request_time.hour + timezone_offset) % 24
        return 8 <= adjusted_hour <= 18


@dataclass
class AttributeContext:
    """Combined attribute context for authorization evaluation."""

    subject: SubjectAttributes
    resource: ResourceAttributes
    context: ContextAttributes
    action: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for policy evaluation."""
        return {
            "action": self.action,
            "subject": self.subject.to_dict(),
            "resource": self.resource.to_dict(),
            "context": self.context.to_dict(),
        }


@dataclass
class AuthorizationDecision:
    """Result of an authorization evaluation."""

    allowed: bool
    action: str = ""
    resource_arn: str = ""
    explanation: str | None = None
    evaluated_at: datetime = field(default_factory=datetime.utcnow)
    policy_version: str = ""
    matched_policies: list[str] = field(default_factory=list)
    evaluation_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/response."""
        return {
            "allowed": self.allowed,
            "action": self.action,
            "resource_arn": self.resource_arn,
            "explanation": self.explanation,
            "evaluated_at": self.evaluated_at.isoformat(),
            "policy_version": self.policy_version,
            "matched_policies": self.matched_policies,
            "evaluation_time_ms": self.evaluation_time_ms,
        }


@dataclass
class ABACPolicy:
    """Definition of an ABAC policy rule."""

    policy_id: str
    name: str
    description: str
    effect: str  # "permit" or "deny"
    actions: list[str]
    conditions: dict[str, Any]
    priority: int = 0
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "description": self.description,
            "effect": self.effect,
            "actions": self.actions,
            "conditions": self.conditions,
            "priority": self.priority,
            "enabled": self.enabled,
        }


# Action to role mappings (default RBAC foundation)
ACTION_ROLE_MAPPING: dict[str, list[str]] = {
    "view_vulnerabilities": ["security-engineer", "devops", "admin", "viewer"],
    "approve_patch": ["security-engineer", "admin"],
    "deploy_production": ["devops", "admin"],
    "deploy_staging": ["devops", "developer", "admin"],
    "manage_users": ["admin"],
    "view_billing": ["billing_admin", "admin"],
    "access_all_tenants": ["platform-admin"],
    "view_audit_logs": ["security-engineer", "compliance", "admin"],
    "configure_agents": ["admin", "devops"],
    "view_metrics": ["viewer", "devops", "admin"],
    "manage_policies": ["admin", "security-engineer"],
}
