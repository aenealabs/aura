"""
Project Aura - Authorization Package

Attribute-Based Access Control (ABAC) for multi-tenant user authorization.
Implements ADR-073 for fine-grained, context-aware access decisions.

Core Components:
- Contracts: Attribute dataclasses and authorization decision models
- Service: ABACAuthorizationService for policy evaluation
- Middleware: FastAPI decorator for endpoint protection

Usage:
    from src.services.authorization import (
        ABACAuthorizationService,
        require_abac,
        AttributeContext,
        AuthorizationDecision,
    )

    # In FastAPI app setup
    app.state.abac_service = ABACAuthorizationService()

    # Protect endpoints
    @router.get("/vulnerabilities/{tenant_id}")
    @require_abac(
        action="view_vulnerabilities",
        resource_resolver=lambda r, tenant_id: f"arn:aws:aura:::tenant/{tenant_id}",
    )
    async def get_vulnerabilities(request: Request, tenant_id: str):
        ...

Author: Project Aura Team
Created: 2026-01-27
"""

from .abac_contracts import (
    AttributeContext,
    AuthorizationDecision,
    ClearanceLevel,
    ContextAttributes,
    ResourceAttributes,
    SensitivityLevel,
    SubjectAttributes,
)
from .abac_middleware import require_abac
from .abac_service import ABACAuthorizationService, get_abac_service, reset_abac_service

__all__ = [
    # Contracts
    "AttributeContext",
    "AuthorizationDecision",
    "ClearanceLevel",
    "ContextAttributes",
    "ResourceAttributes",
    "SensitivityLevel",
    "SubjectAttributes",
    # Service
    "ABACAuthorizationService",
    "get_abac_service",
    "reset_abac_service",
    # Middleware
    "require_abac",
]

__version__ = "1.0.0"
