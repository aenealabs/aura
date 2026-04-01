"""
Integration services for external developer tools and data platforms.

This module provides the base adapter interface and shared utilities for
all integrations (IDE extensions, data connectors, etc.) as defined in ADR-048.
"""

from src.services.integrations.base_adapter import (
    BaseIntegrationAdapter,
    IntegrationConfig,
    IntegrationError,
    IntegrationResult,
    IntegrationType,
)
from src.services.integrations.export_authorization_service import (
    ExportAuthorizationService,
    ExportRequest,
    ExportScope,
)
from src.services.integrations.secrets_prescan_filter import (
    RedactionResult,
    SecretDetection,
    SecretsPrescanFilter,
)
from src.services.integrations.slack_adapter import (
    SlackAdapter,
    SlackConfig,
    create_slack_adapter,
)

__all__ = [
    # Base adapter
    "BaseIntegrationAdapter",
    "IntegrationConfig",
    "IntegrationError",
    "IntegrationResult",
    "IntegrationType",
    # Secrets filter
    "SecretsPrescanFilter",
    "SecretDetection",
    "RedactionResult",
    # Export authorization
    "ExportAuthorizationService",
    "ExportRequest",
    "ExportScope",
    # Slack adapter
    "SlackAdapter",
    "SlackConfig",
    "create_slack_adapter",
]
