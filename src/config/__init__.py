"""
Project Aura - Configuration Module

Provides centralized configuration management for the platform,
including integration modes, feature flags, and environment-specific settings.
"""

from src.config.feature_flags import (
    BETA_FEATURES,
    CORE_FEATURES,
    CustomerFeatureOverrides,
    FeatureDefinition,
    FeatureFlagsService,
    FeatureStatus,
    FeatureTier,
    get_beta_features,
    get_environment_defaults,
    get_feature_definition,
    get_feature_flags,
    is_feature_enabled,
)
from src.config.guardrails_config import (
    ContentFilterConfig,
    ContentFilterStrength,
    GuardrailConfig,
    GuardrailEnvironment,
    GuardrailMode,
    GuardrailResult,
    PIIAction,
    PIIEntityConfig,
    TopicConfig,
    format_guardrail_trace,
    get_guardrail_config,
    get_guardrail_environment,
    load_guardrail_ids_from_ssm,
)
from src.config.integration_config import (
    CustomerMCPBudget,
    ExternalToolCategory,
    ExternalToolConfig,
    IntegrationConfig,
    IntegrationMode,
    clear_integration_config_cache,
    get_integration_config,
    get_mode_for_repository,
    require_defense_mode,
    require_enterprise_mode,
)
from src.config.logging_config import (
    CloudWatchJSONFormatter,
    DevelopmentFormatter,
    Environment,
    LogLevel,
    StructuredLogger,
    clear_correlation_id,
    configure_from_environment,
    configure_logging,
    get_correlation_id,
    get_logger,
    set_correlation_id,
)
from src.config.memory_service_config import (
    FeatureFlagsConfig,
    MemoryArchitectureConfig,
    MemoryConfig,
    MemoryServiceConfig,
    ObservabilityConfig,
    PerformanceConfig,
    ServerConfig,
    StorageConfig,
    SurpriseConfig,
    TTTConfig,
)
from src.config.memory_service_config import (
    get_cached_config as get_cached_memory_config,
)
from src.config.memory_service_config import get_config as get_memory_service_config
from src.config.memory_service_config import reload_config as reload_memory_config
from src.config.memory_service_config import validate_config as validate_memory_config
from src.config.paths import get_repo_root, get_sample_project_path, get_workspace_root

__all__ = [
    # Integration config
    "IntegrationMode",
    "IntegrationConfig",
    "CustomerMCPBudget",
    "ExternalToolConfig",
    "ExternalToolCategory",
    "get_integration_config",
    "clear_integration_config_cache",
    "get_mode_for_repository",
    "require_defense_mode",
    "require_enterprise_mode",
    # Guardrails config (ADR-029)
    "GuardrailMode",
    "GuardrailEnvironment",
    "GuardrailConfig",
    "GuardrailResult",
    "ContentFilterConfig",
    "ContentFilterStrength",
    "PIIAction",
    "PIIEntityConfig",
    "TopicConfig",
    "get_guardrail_config",
    "get_guardrail_environment",
    "load_guardrail_ids_from_ssm",
    "format_guardrail_trace",
    # Memory service config (ADR-024)
    "MemoryServiceConfig",
    "MemoryConfig",
    "TTTConfig",
    "SurpriseConfig",
    "MemoryArchitectureConfig",
    "ServerConfig",
    "StorageConfig",
    "PerformanceConfig",
    "ObservabilityConfig",
    "FeatureFlagsConfig",
    "get_memory_service_config",
    "get_cached_memory_config",
    "reload_memory_config",
    "validate_memory_config",
    # Path configuration
    "get_repo_root",
    "get_sample_project_path",
    "get_workspace_root",
    # Feature flags
    "FeatureDefinition",
    "FeatureFlagsService",
    "FeatureStatus",
    "FeatureTier",
    "CustomerFeatureOverrides",
    "get_feature_flags",
    "is_feature_enabled",
    "get_beta_features",
    "get_feature_definition",
    "get_environment_defaults",
    "BETA_FEATURES",
    "CORE_FEATURES",
    # Logging configuration (Issue #45)
    "configure_logging",
    "configure_from_environment",
    "get_logger",
    "LogLevel",
    "Environment",
    "get_correlation_id",
    "set_correlation_id",
    "clear_correlation_id",
    "CloudWatchJSONFormatter",
    "DevelopmentFormatter",
    "StructuredLogger",
]
