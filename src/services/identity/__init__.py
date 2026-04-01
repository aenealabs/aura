"""
Project Aura - Identity Provider Services

Multi-IdP authentication system supporting:
- AWS Cognito (OAuth2/OIDC)
- LDAP / Active Directory
- SAML 2.0 Federation
- OpenID Connect (OIDC)
- PingID / PingFederate
- Generic SSO

Implements ADR-054: Multi-Identity Provider Authentication System

Author: Project Aura Team
Created: 2026-01-06
Version: 1.0.0
"""

from src.services.identity.audit_service import IdentityAuditService
from src.services.identity.base_provider import IdentityProvider
from src.services.identity.idp_config_service import IdPConfigService
from src.services.identity.idp_routing_service import IdPRoutingService
from src.services.identity.models import (
    AttributeMapping,
    AuthCredentials,
    AuthResult,
    GroupMapping,
    HealthCheckResult,
    IdentityProviderConfig,
    IdPType,
    TokenResult,
    TokenValidationResult,
    UserInfo,
)
from src.services.identity.token_service import TokenNormalizationService

__all__ = [
    # Models
    "IdPType",
    "IdentityProviderConfig",
    "AttributeMapping",
    "GroupMapping",
    "AuthCredentials",
    "AuthResult",
    "TokenResult",
    "TokenValidationResult",
    "UserInfo",
    "HealthCheckResult",
    # Services
    "IdentityProvider",
    "IdPConfigService",
    "TokenNormalizationService",
    "IdPRoutingService",
    "IdentityAuditService",
]
