"""
Project Aura - IdP Routing Service

Routes authentication requests to the appropriate identity provider
based on email domain, organization, or explicit selection.

Author: Project Aura Team
Created: 2026-01-06
Version: 1.0.0
"""

# Re-export from idp_config_service for backwards compatibility
from src.services.identity.idp_config_service import (
    IdPRoutingService,
    get_idp_routing_service,
)

__all__ = ["IdPRoutingService", "get_idp_routing_service"]
