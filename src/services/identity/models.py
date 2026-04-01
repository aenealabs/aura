"""
Project Aura - Identity Provider Data Models

Data models, enums, and validators for the multi-IdP authentication system.

Author: Project Aura Team
Created: 2026-01-06
Version: 1.0.0
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class IdPType(Enum):
    """Supported identity provider types."""

    COGNITO = "cognito"
    LDAP = "ldap"
    SAML = "saml"
    OIDC = "oidc"
    PINGID = "pingid"
    SSO = "sso"

    @classmethod
    def from_string(cls, value: str) -> "IdPType":
        """Convert string to IdPType enum."""
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(
                f"Invalid IdP type: {value}. " f"Valid types: {[t.value for t in cls]}"
            )


class AuthAction(Enum):
    """Authentication audit action types."""

    CONFIG_CREATE = "config_create"
    CONFIG_UPDATE = "config_update"
    CONFIG_DELETE = "config_delete"
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    TOKEN_REFRESH = "token_refresh"
    TOKEN_REVOKE = "token_revoke"
    SESSION_LOGOUT = "session_logout"
    HEALTH_CHECK = "health_check"


class ConnectionStatus(Enum):
    """Identity provider connection status."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    DEGRADED = "degraded"
    AUTH_FAILED = "auth_failed"


@dataclass
class AttributeMapping:
    """
    Maps an IdP attribute/claim to an Aura user attribute.

    Example: Map LDAP 'mail' attribute to Aura 'email' field.
    """

    source_attribute: str  # IdP claim name (e.g., "mail", "displayName", "memberOf")
    target_attribute: str  # Aura field (e.g., "email", "name", "groups")
    transform: str | None = None  # Optional transform (lowercase, uppercase, split)
    required: bool = False  # Whether this mapping is required for auth to succeed
    default_value: str | None = None  # Default if source is missing and not required

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for DynamoDB storage."""
        return {
            "source_attribute": self.source_attribute,
            "target_attribute": self.target_attribute,
            "transform": self.transform,
            "required": self.required,
            "default_value": self.default_value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AttributeMapping":
        """Create from dictionary."""
        return cls(
            source_attribute=data["source_attribute"],
            target_attribute=data["target_attribute"],
            transform=data.get("transform"),
            required=data.get("required", False),
            default_value=data.get("default_value"),
        )


@dataclass
class GroupMapping:
    """
    Maps an IdP group to an Aura role.

    Supports exact match or regex patterns for group matching.
    """

    source_group: str  # IdP group (DN for LDAP, group name for SAML/OIDC)
    target_role: str  # Aura role (admin, security-engineer, developer, viewer)
    is_regex: bool = False  # Whether source_group is a regex pattern
    priority: int = (
        100  # For multi-group membership conflicts (lower = higher priority)
    )

    def matches(self, group: str) -> bool:
        """Check if an IdP group matches this mapping."""
        if self.is_regex:
            return bool(re.match(self.source_group, group, re.IGNORECASE))
        return group.lower() == self.source_group.lower()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for DynamoDB storage."""
        return {
            "source_group": self.source_group,
            "target_role": self.target_role,
            "is_regex": self.is_regex,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GroupMapping":
        """Create from dictionary."""
        return cls(
            source_group=data["source_group"],
            target_role=data["target_role"],
            is_regex=data.get("is_regex", False),
            priority=data.get("priority", 100),
        )


@dataclass
class IdentityProviderConfig:
    """
    Configuration for an identity provider.

    Stores all settings needed to authenticate users against an external IdP.
    """

    idp_id: str  # Unique identifier (UUID)
    organization_id: str  # Organization this IdP belongs to
    idp_type: IdPType  # Type of identity provider
    name: str  # Display name (e.g., "Corporate Active Directory")
    enabled: bool = True  # Whether this IdP is active
    priority: int = 100  # Order for multi-IdP (lower = higher priority)

    # Connection settings (type-specific, see provider implementations)
    connection_settings: dict[str, Any] = field(default_factory=dict)

    # Reference to Secrets Manager ARN for credentials
    credentials_secret_arn: str | None = None

    # Certificate settings (for SAML, LDAP TLS)
    certificate_settings: dict[str, Any] = field(default_factory=dict)

    # Attribute mapping (IdP claims -> Aura user fields)
    attribute_mappings: list[AttributeMapping] = field(default_factory=list)

    # Group mapping (IdP groups -> Aura roles)
    group_mappings: list[GroupMapping] = field(default_factory=list)

    # Email domain routing (users with these domains auto-route to this IdP)
    email_domains: list[str] = field(default_factory=list)

    # Metadata
    created_at: str = ""
    updated_at: str = ""
    created_by: str = ""

    def __post_init__(self):
        """Validate and normalize configuration."""
        if isinstance(self.idp_type, str):
            self.idp_type = IdPType.from_string(self.idp_type)

        # Convert dict attribute mappings to objects
        if self.attribute_mappings:
            self.attribute_mappings = [
                AttributeMapping.from_dict(m) if isinstance(m, dict) else m
                for m in self.attribute_mappings
            ]

        # Convert dict group mappings to objects
        if self.group_mappings:
            self.group_mappings = [
                GroupMapping.from_dict(m) if isinstance(m, dict) else m
                for m in self.group_mappings
            ]

    def to_dynamodb_item(self) -> dict[str, Any]:
        """Convert to DynamoDB item format."""
        return {
            "idp_id": self.idp_id,
            "organization_id": self.organization_id,
            "idp_type": self.idp_type.value,
            "name": self.name,
            "enabled": self.enabled,
            "priority": self.priority,
            "connection_settings": self.connection_settings,
            "credentials_secret_arn": self.credentials_secret_arn,
            "certificate_settings": self.certificate_settings,
            "attribute_mappings": [m.to_dict() for m in self.attribute_mappings],
            "group_mappings": [m.to_dict() for m in self.group_mappings],
            "email_domains": self.email_domains,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "created_by": self.created_by,
        }

    @classmethod
    def from_dynamodb_item(cls, item: dict[str, Any]) -> "IdentityProviderConfig":
        """Create from DynamoDB item."""
        return cls(
            idp_id=item["idp_id"],
            organization_id=item["organization_id"],
            idp_type=IdPType.from_string(item["idp_type"]),
            name=item["name"],
            enabled=item.get("enabled", True),
            priority=item.get("priority", 100),
            connection_settings=item.get("connection_settings", {}),
            credentials_secret_arn=item.get("credentials_secret_arn"),
            certificate_settings=item.get("certificate_settings", {}),
            attribute_mappings=[
                AttributeMapping.from_dict(m)
                for m in item.get("attribute_mappings", [])
            ],
            group_mappings=[
                GroupMapping.from_dict(m) for m in item.get("group_mappings", [])
            ],
            email_domains=item.get("email_domains", []),
            created_at=item.get("created_at", ""),
            updated_at=item.get("updated_at", ""),
            created_by=item.get("created_by", ""),
        )

    def get_default_attribute_mappings(self) -> list[AttributeMapping]:
        """Get default attribute mappings for this IdP type."""
        defaults = {
            IdPType.LDAP: [
                AttributeMapping("mail", "email", required=True),
                AttributeMapping("displayName", "name"),
                AttributeMapping("sAMAccountName", "username"),
                AttributeMapping("memberOf", "groups"),
            ],
            IdPType.SAML: [
                AttributeMapping(
                    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
                    "email",
                    required=True,
                ),
                AttributeMapping(
                    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name", "name"
                ),
                AttributeMapping(
                    "http://schemas.microsoft.com/ws/2008/06/identity/claims/groups",
                    "groups",
                ),
            ],
            IdPType.OIDC: [
                AttributeMapping("email", "email", required=True),
                AttributeMapping("name", "name"),
                AttributeMapping("preferred_username", "username"),
                AttributeMapping("groups", "groups"),
            ],
            IdPType.COGNITO: [
                AttributeMapping("email", "email", required=True),
                AttributeMapping("name", "name"),
                AttributeMapping("cognito:username", "username"),
                AttributeMapping("cognito:groups", "groups"),
            ],
            IdPType.PINGID: [
                AttributeMapping("email", "email", required=True),
                AttributeMapping("name", "name"),
                AttributeMapping("sub", "username"),
                AttributeMapping("groups", "groups"),
            ],
            IdPType.SSO: [
                AttributeMapping("email", "email", required=True),
                AttributeMapping("name", "name"),
            ],
        }
        return defaults.get(self.idp_type, [])


@dataclass
class AuthCredentials:
    """
    Credentials for authentication.

    The actual fields used depend on the IdP type:
    - LDAP: username + password
    - SAML: saml_response
    - OIDC: code + code_verifier (for code exchange) or id_token (for validation)
    """

    username: str | None = None
    password: str | None = None
    saml_response: str | None = None
    relay_state: str | None = None
    code: str | None = None
    code_verifier: str | None = None
    state: str | None = None
    nonce: str | None = None
    id_token: str | None = None
    access_token: str | None = None


@dataclass
class AuthResult:
    """Result of an authentication attempt."""

    success: bool
    user_id: str | None = None  # Provider-specific user ID
    email: str | None = None
    name: str | None = None
    groups: list[str] = field(default_factory=list)  # Raw IdP groups
    roles: list[str] = field(default_factory=list)  # Mapped Aura roles
    attributes: dict[str, Any] = field(default_factory=dict)  # All mapped attributes
    provider_metadata: dict[str, Any] = field(default_factory=dict)  # IdP-specific data
    error: str | None = None
    error_code: str | None = None


@dataclass
class TokenResult:
    """Result of token exchange or refresh."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600  # Seconds
    refresh_token: str | None = None
    id_token: str | None = None
    scope: str | None = None


@dataclass
class TokenValidationResult:
    """Result of token validation."""

    valid: bool
    claims: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    expires_at: datetime | None = None


@dataclass
class UserInfo:
    """User information from identity provider."""

    user_id: str
    email: str | None = None
    name: str | None = None
    username: str | None = None
    groups: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthCheckResult:
    """Result of IdP health check."""

    healthy: bool
    status: ConnectionStatus
    latency_ms: float = 0.0
    message: str | None = None
    last_checked: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuraTokens:
    """Aura JWT tokens issued after successful authentication."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600
    id_token: str | None = None  # Aura doesn't issue separate ID tokens


@dataclass
class AuthSession:
    """Active authentication session."""

    session_id: str
    user_sub: str  # Aura subject (hashed IdP + user ID)
    idp_id: str
    organization_id: str
    email: str | None = None
    roles: list[str] = field(default_factory=list)
    refresh_token_jti: str | None = None  # For refresh token validation
    created_at: str = ""
    expires_at: str = ""
    last_activity: str = ""
    ip_address: str | None = None
    user_agent: str | None = None

    def to_dynamodb_item(self) -> dict[str, Any]:
        """Convert to DynamoDB item format."""
        return {
            "session_id": self.session_id,
            "user_sub": self.user_sub,
            "idp_id": self.idp_id,
            "organization_id": self.organization_id,
            "email": self.email,
            "roles": self.roles,
            "refresh_token_jti": self.refresh_token_jti,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "last_activity": self.last_activity,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
        }

    @classmethod
    def from_dynamodb_item(cls, item: dict[str, Any]) -> "AuthSession":
        """Create from DynamoDB item."""
        return cls(
            session_id=item["session_id"],
            user_sub=item["user_sub"],
            idp_id=item["idp_id"],
            organization_id=item["organization_id"],
            email=item.get("email"),
            roles=item.get("roles", []),
            refresh_token_jti=item.get("refresh_token_jti"),
            created_at=item.get("created_at", ""),
            expires_at=item.get("expires_at", ""),
            last_activity=item.get("last_activity", ""),
            ip_address=item.get("ip_address"),
            user_agent=item.get("user_agent"),
        )


@dataclass
class AuditLogEntry:
    """Audit log entry for identity operations."""

    audit_id: str
    idp_id: str
    organization_id: str
    action_type: str  # AuthAction value
    actor_id: str | None = None  # User who performed the action
    target_user_id: str | None = None  # User affected (for auth events)
    timestamp: str = ""
    success: bool = True
    error_message: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    ttl: int | None = None  # DynamoDB TTL

    def to_dynamodb_item(self) -> dict[str, Any]:
        """Convert to DynamoDB item format."""
        item = {
            "audit_id": self.audit_id,
            "idp_id": self.idp_id,
            "organization_id": self.organization_id,
            "action_type": self.action_type,
            "actor_id": self.actor_id,
            "target_user_id": self.target_user_id,
            "timestamp": self.timestamp,
            "success": self.success,
            "error_message": self.error_message,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "details": self.details,
        }
        if self.ttl:
            item["ttl"] = self.ttl
        return item


# Validation helpers
VALID_AURA_ROLES = ["admin", "security-engineer", "developer", "viewer"]


def validate_role(role: str) -> bool:
    """Check if a role is a valid Aura role."""
    return role in VALID_AURA_ROLES


def validate_email_domain(domain: str) -> bool:
    """Validate email domain format."""
    pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z]{2,})+$"
    return bool(re.match(pattern, domain))


def extract_email_domain(email: str) -> str | None:
    """Extract domain from email address."""
    if "@" in email:
        return email.split("@")[1].lower()
    return None
