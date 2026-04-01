"""Environment Validator Agent (ADR-062).

Validates Kubernetes manifests for environment consistency,
preventing cross-environment misconfigurations.

Usage:
    from src.services.env_validator import validate_manifest_file, validate_manifest_string

    # Validate a file
    result = validate_manifest_file("manifest.yaml", "qa")
    if result.has_critical:
        print(f"Validation failed: {len(result.violations)} critical violations")

    # Validate a string
    result = validate_manifest_string(yaml_content, "dev")

CLI Usage:
    python -m src.services.env_validator.cli manifest.yaml --env qa --strict
"""

from src.services.env_validator.config import (
    get_current_environment,
    get_environment_config,
    load_environment_registry,
)
from src.services.env_validator.engine import (
    ValidationEngine,
    validate_manifest_file,
    validate_manifest_string,
)
from src.services.env_validator.models import (
    EnvironmentConfig,
    EnvironmentRegistry,
    ManifestResource,
    Severity,
    TriggerType,
    ValidationResult,
    ValidationRun,
    Violation,
)
from src.services.env_validator.remediation_engine import (
    MockRemediationEngine,
    RemediationAction,
    RemediationEngine,
    RemediationResult,
    RemediationRisk,
    RemediationStatus,
)
from src.services.env_validator.remediation_strategies import (
    BaseRemediationStrategy,
    ConfigMapValueStrategy,
    EnvironmentVariableStrategy,
    HITLOnlyStrategy,
    MockRemediationStrategy,
    ResourceNamingStrategy,
    TagConsistencyStrategy,
    get_default_strategies,
)

__all__ = [
    # Engine
    "ValidationEngine",
    "validate_manifest_file",
    "validate_manifest_string",
    # Config
    "load_environment_registry",
    "get_environment_config",
    "get_current_environment",
    # Models
    "EnvironmentConfig",
    "EnvironmentRegistry",
    "ManifestResource",
    "Severity",
    "TriggerType",
    "ValidationResult",
    "ValidationRun",
    "Violation",
    # Remediation Engine
    "RemediationEngine",
    "MockRemediationEngine",
    "RemediationAction",
    "RemediationResult",
    "RemediationRisk",
    "RemediationStatus",
    # Remediation Strategies
    "BaseRemediationStrategy",
    "EnvironmentVariableStrategy",
    "ResourceNamingStrategy",
    "TagConsistencyStrategy",
    "ConfigMapValueStrategy",
    "HITLOnlyStrategy",
    "MockRemediationStrategy",
    "get_default_strategies",
]
