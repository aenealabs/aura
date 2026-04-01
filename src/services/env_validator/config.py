"""Environment registry configuration for Environment Validator (ADR-062).

Loads environment-specific values from SSM Parameter Store for security.
Falls back to local config for development/testing.
"""

import json
import logging
import os
from functools import lru_cache
from typing import Optional

from src.services.env_validator.models import EnvironmentConfig, EnvironmentRegistry

logger = logging.getLogger(__name__)

# SSM parameter path pattern
SSM_REGISTRY_PATH = "/aura/{env}/env-validator/registry"


# Default registry for local development and testing ONLY
# In deployed environments, values are loaded from SSM Parameter Store
# IMPORTANT: These defaults use service discovery names (*.aura.local) and
# environment variables - never hardcode account IDs or cluster endpoints
def _get_default_registry() -> dict[str, dict]:
    """Build default registry using environment variables and service discovery."""
    account_id = os.environ.get("AWS_ACCOUNT_ID", "LOCAL_DEV")
    region = os.environ.get("AWS_REGION", "us-east-1")
    gov_region = os.environ.get("AWS_GOVCLOUD_REGION", "us-gov-west-1")

    return {
        "dev": {
            "account_id": account_id,
            "ecr_registry": f"{account_id}.dkr.ecr.{region}.amazonaws.com",
            "neptune_cluster": "neptune.aura.local",
            "opensearch_domain": "opensearch.aura.local",
            "resource_suffix": "-dev",
            "eks_cluster": "aura-cluster-dev",
            "region": region,
        },
        "qa": {
            "account_id": account_id,
            "ecr_registry": f"{account_id}.dkr.ecr.{region}.amazonaws.com",
            "neptune_cluster": "neptune.aura.local",
            "opensearch_domain": "opensearch.aura.local",
            "resource_suffix": "-qa",
            "eks_cluster": "aura-cluster-qa",
            "region": region,
        },
        "staging": {
            "account_id": account_id,
            "ecr_registry": f"{account_id}.dkr.ecr.{region}.amazonaws.com",
            "neptune_cluster": "neptune.aura.local",
            "opensearch_domain": "opensearch.aura.local",
            "resource_suffix": "-staging",
            "eks_cluster": "aura-cluster-staging",
            "region": region,
        },
        "prod": {
            "account_id": account_id,
            "ecr_registry": f"{account_id}.dkr.ecr.{gov_region}.amazonaws.com",
            "neptune_cluster": "neptune.aura.local",
            "opensearch_domain": "opensearch.aura.local",
            "resource_suffix": "-prod",
            "eks_cluster": "aura-cluster-prod",
            "region": gov_region,
        },
    }


def _load_from_ssm(env: str) -> Optional[dict]:
    """Load environment registry from SSM Parameter Store.

    Args:
        env: Current environment name

    Returns:
        Registry dict if successful, None otherwise
    """
    try:
        import boto3

        ssm = boto3.client("ssm")
        param_path = SSM_REGISTRY_PATH.format(env=env)

        response = ssm.get_parameter(Name=param_path, WithDecryption=True)
        return json.loads(response["Parameter"]["Value"])
    except ImportError:
        logger.debug("boto3 not available, using default registry")
        return None
    except Exception as e:
        logger.warning(f"Failed to load registry from SSM: {e}")
        return None


def _build_registry(registry_data: dict) -> EnvironmentRegistry:
    """Build EnvironmentRegistry from dict data.

    Args:
        registry_data: Dict mapping env name to config dict

    Returns:
        EnvironmentRegistry instance
    """
    environments = {}
    for env_name, config_dict in registry_data.items():
        try:
            environments[env_name] = EnvironmentConfig(
                account_id=config_dict["account_id"],
                ecr_registry=config_dict["ecr_registry"],
                neptune_cluster=config_dict["neptune_cluster"],
                opensearch_domain=config_dict["opensearch_domain"],
                resource_suffix=config_dict["resource_suffix"],
                eks_cluster=config_dict["eks_cluster"],
                region=config_dict["region"],
            )
        except KeyError as e:
            logger.error(f"Invalid config for environment {env_name}: missing {e}")
            continue

    return EnvironmentRegistry(environments=environments)


@lru_cache(maxsize=1)
def load_environment_registry(use_ssm: bool = True) -> EnvironmentRegistry:
    """Load the environment registry.

    Builds default registry from environment variables and merges any
    SSM-loaded config on top. This allows SSM to override defaults for
    the current environment while maintaining cross-environment awareness.

    Args:
        use_ssm: Whether to attempt SSM loading (disable for testing)

    Returns:
        EnvironmentRegistry with all environment configurations
    """
    # Build defaults from current environment variables (not cached at import time)
    # This allows tests to set AWS_ACCOUNT_ID before loading the registry
    registry_data = _get_default_registry()

    # Merge SSM config on top (overrides current environment with live values)
    if use_ssm:
        env = os.environ.get("ENVIRONMENT", "dev")
        ssm_data = _load_from_ssm(env)
        if ssm_data:
            logger.info(f"Merging SSM config for environment: {env}")
            registry_data.update(ssm_data)
        else:
            logger.info("SSM not available, using default registry only")

    return _build_registry(registry_data)


def get_environment_config(env: str) -> Optional[EnvironmentConfig]:
    """Get configuration for a specific environment.

    Args:
        env: Environment name (dev, qa, staging, prod)

    Returns:
        EnvironmentConfig if found, None otherwise
    """
    registry = load_environment_registry()
    return registry.get(env)


def get_current_environment() -> str:
    """Get the current environment from ENVIRONMENT variable."""
    return os.environ.get("ENVIRONMENT", "dev")


def clear_registry_cache() -> None:
    """Clear the cached registry (for testing)."""
    load_environment_registry.cache_clear()


# Known patterns for environment detection in resource names/values
ENVIRONMENT_PATTERNS = {
    "dev": ["-dev", "_dev", "/dev/", ".dev."],
    "qa": ["-qa", "_qa", "/qa/", ".qa."],
    "staging": ["-staging", "_staging", "/staging/", ".staging."],
    "prod": ["-prod", "_prod", "/prod/", ".prod.", "-production", "_production"],
}


def detect_environment_in_string(value: str) -> Optional[str]:
    """Detect which environment a string value belongs to.

    Args:
        value: String to check (e.g., table name, endpoint, ARN)

    Returns:
        Environment name if detected, None otherwise
    """
    value_lower = value.lower()
    for env, patterns in ENVIRONMENT_PATTERNS.items():
        for pattern in patterns:
            if pattern in value_lower:
                return env
    return None
