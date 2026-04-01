"""
Bedrock Configuration Management
Provides environment-specific configuration for AWS Bedrock integration
with cost controls and security best practices.
"""

import os
from enum import Enum
from typing import Any


class Environment(Enum):
    """Environment types for configuration."""

    DEV = "development"
    QA = "qa"
    STAGING = "staging"
    PROD = "production"


# Bedrock configuration by environment
BEDROCK_CONFIG: dict[Environment, dict[str, Any]] = {
    Environment.DEV: {
        "aws_region": "us-east-1",
        "model_id_primary": "anthropic.claude-3-5-sonnet-20240620-v1:0",  # Claude 3.5 Sonnet v1 (on-demand available)
        "model_id_fallback": "anthropic.claude-3-haiku-20240307-v1:0",  # Claude 3 Haiku fallback
        "max_tokens_default": 4096,
        "temperature_default": 0.7,
        "daily_budget_usd": 10.0,
        "monthly_budget_usd": 100.0,
        "max_requests_per_minute": 5,
        "max_requests_per_hour": 100,
        "max_requests_per_day": 500,
        "secrets_path": "aura/dev/bedrock-config",
        "cost_table_name": "aura-ddb-dev-llm-costs",
        "cache_enabled": True,
        "cache_ttl_seconds": 86400,  # 24 hours
    },
    Environment.QA: {
        "aws_region": "us-east-1",
        "model_id_primary": "anthropic.claude-3-5-sonnet-20240620-v1:0",  # Claude 3.5 Sonnet v1 (on-demand available)
        "model_id_fallback": "anthropic.claude-3-haiku-20240307-v1:0",  # Claude 3 Haiku fallback
        "max_tokens_default": 4096,
        "temperature_default": 0.7,
        "daily_budget_usd": 25.0,
        "monthly_budget_usd": 250.0,
        "max_requests_per_minute": 10,
        "max_requests_per_hour": 200,
        "max_requests_per_day": 1000,
        "secrets_path": "aura/qa/bedrock-config",
        "cost_table_name": "aura-ddb-qa-llm-costs",
        "cache_enabled": True,
        "cache_ttl_seconds": 86400,
    },
    Environment.STAGING: {
        "aws_region": "us-east-1",
        "model_id_primary": "anthropic.claude-sonnet-4-5-20250929-v1:0",  # Claude Sonnet 4.5 (Sep 2025)
        "model_id_fallback": "anthropic.claude-3-5-sonnet-20240620-v1:0",  # Claude 3.5 Sonnet fallback
        "max_tokens_default": 4096,
        "temperature_default": 0.7,
        "daily_budget_usd": 50.0,
        "monthly_budget_usd": 500.0,
        "max_requests_per_minute": 10,
        "max_requests_per_hour": 300,
        "max_requests_per_day": 2000,
        "secrets_path": "aura/staging/bedrock-config",
        "cost_table_name": "aura-ddb-staging-llm-costs",
        "cache_enabled": True,
        "cache_ttl_seconds": 86400,
    },
    Environment.PROD: {
        "aws_region": "us-east-1",
        "model_id_primary": "anthropic.claude-sonnet-4-5-20250929-v1:0",  # Claude Sonnet 4.5 (Sep 2025)
        "model_id_fallback": "anthropic.claude-3-5-sonnet-20240620-v1:0",  # Claude 3.5 Sonnet fallback
        "max_tokens_default": 4096,
        "temperature_default": 0.7,
        "daily_budget_usd": 100.0,
        "monthly_budget_usd": 2000.0,
        "max_requests_per_minute": 20,
        "max_requests_per_hour": 500,
        "max_requests_per_day": 5000,
        "secrets_path": "aura/prod/bedrock-config",
        "cost_table_name": "aura-ddb-prod-llm-costs",
        "cache_enabled": True,
        "cache_ttl_seconds": 86400,
    },
}


# Model pricing (as of November 2025)
# Update these values as Bedrock pricing changes
MODEL_PRICING: dict[str, dict[str, float]] = {
    # Claude Sonnet 4.5 (Sep 2025) - Primary model
    "anthropic.claude-sonnet-4-5-20250929-v1:0": {
        "input_per_million": 3.00,
        "output_per_million": 15.00,
    },
    # Claude 3.5 Sonnet (June 2024) - Fallback model
    "anthropic.claude-3-5-sonnet-20240620-v1:0": {
        "input_per_million": 3.00,
        "output_per_million": 15.00,
    },
    # Claude 3 Sonnet - Legacy fallback
    "anthropic.claude-3-sonnet-20240229-v1:0": {
        "input_per_million": 3.00,
        "output_per_million": 15.00,
    },
    # Claude 3.5 Sonnet (October 2024) - Requires inference profile
    "anthropic.claude-3-5-sonnet-20241022-v1:0": {
        "input_per_million": 3.00,
        "output_per_million": 15.00,
    },
    # Claude 3 Haiku - Requires use case form submission
    "anthropic.claude-3-haiku-20240307-v1:0": {
        "input_per_million": 0.25,
        "output_per_million": 1.25,
    },
    # Claude 3 Opus
    "anthropic.claude-3-opus-20240229-v1:0": {
        "input_per_million": 15.00,
        "output_per_million": 75.00,
    },
}


def get_environment() -> Environment:
    """
    Get current environment from AURA_ENV or ENVIRONMENT variable.
    Defaults to development if not set.

    Returns:
        Environment enum value
    """
    # Check AURA_ENV first, then ENVIRONMENT (used by ECS tasks)
    env_str = os.environ.get("AURA_ENV") or os.environ.get("ENVIRONMENT", "development")
    env_str = env_str.lower()

    env_map = {
        "development": Environment.DEV,
        "dev": Environment.DEV,
        "qa": Environment.QA,
        "staging": Environment.STAGING,
        "stage": Environment.STAGING,
        "production": Environment.PROD,
        "prod": Environment.PROD,
    }

    return env_map.get(env_str, Environment.DEV)


def get_config() -> dict[str, Any]:
    """
    Get configuration for current environment.

    Returns:
        Configuration dictionary with all settings

    Example:
        >>> config = get_config()
        >>> print(config['model_id_primary'])
        'anthropic.claude-sonnet-4-5-20250929-v1:0'
    """
    env = get_environment()
    return BEDROCK_CONFIG[env].copy()


def get_model_pricing(model_id: str) -> dict[str, float]:
    """
    Get pricing information for a specific model.

    Args:
        model_id: Bedrock model identifier

    Returns:
        Dictionary with 'input_per_million' and 'output_per_million' keys

    Raises:
        ValueError: If model_id is not found in pricing data
    """
    if model_id not in MODEL_PRICING:
        raise ValueError(
            f"Unknown model ID: {model_id}. Available models: {list(MODEL_PRICING.keys())}"
        )

    return MODEL_PRICING[model_id].copy()


def calculate_cost(input_tokens: int, output_tokens: int, model_id: str) -> float:
    """
    Calculate cost for a model invocation.

    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        model_id: Bedrock model identifier

    Returns:
        Cost in USD (rounded to 6 decimal places)

    Example:
        >>> cost = calculate_cost(1000, 500, "anthropic.claude-sonnet-4-5-20250929-v1:0")
        >>> print(f"${cost:.6f}")
        $0.010500
    """
    pricing = get_model_pricing(model_id)

    input_cost = (input_tokens / 1_000_000) * pricing["input_per_million"]
    output_cost = (output_tokens / 1_000_000) * pricing["output_per_million"]

    total_cost = input_cost + output_cost

    return round(total_cost, 6)


def validate_config(config: dict[str, Any]) -> bool:
    """
    Validate configuration dictionary has all required fields.

    Args:
        config: Configuration dictionary to validate

    Returns:
        True if valid

    Raises:
        ValueError: If configuration is missing required fields or has invalid values
    """
    required_fields = [
        "aws_region",
        "model_id_primary",
        "model_id_fallback",
        "max_tokens_default",
        "temperature_default",
        "daily_budget_usd",
        "monthly_budget_usd",
        "max_requests_per_minute",
        "max_requests_per_hour",
        "max_requests_per_day",
        "secrets_path",
    ]

    # Check required fields
    missing = [field for field in required_fields if field not in config]
    if missing:
        raise ValueError(f"Configuration missing required fields: {missing}")

    # Validate types and ranges
    if (
        not isinstance(config["max_tokens_default"], int)
        or config["max_tokens_default"] <= 0
    ):
        raise ValueError("max_tokens_default must be positive integer")

    if not (0 <= config["temperature_default"] <= 1):
        raise ValueError("temperature_default must be between 0 and 1")

    if config["daily_budget_usd"] <= 0 or config["monthly_budget_usd"] <= 0:
        raise ValueError("Budget values must be positive")

    if config["daily_budget_usd"] * 31 < config["monthly_budget_usd"]:
        raise ValueError("Monthly budget should be >= daily budget * 31")

    return True


# Validate all configurations on module import
for env, config in BEDROCK_CONFIG.items():
    try:
        validate_config(config)
    except ValueError as e:
        raise RuntimeError(f"Invalid configuration for {env.value}: {e}") from e


if __name__ == "__main__":
    # Demo usage
    print("Project Aura - Bedrock Configuration")
    print("=" * 50)

    current_env = get_environment()
    print(f"\nCurrent Environment: {current_env.value}")

    config = get_config()
    print("\nConfiguration:")
    print(f"  Region: {config['aws_region']}")
    print(f"  Primary Model: {config['model_id_primary']}")
    print(f"  Daily Budget: ${config['daily_budget_usd']:.2f}")
    print(f"  Monthly Budget: ${config['monthly_budget_usd']:.2f}")
    print(f"  Rate Limit: {config['max_requests_per_minute']}/min")

    # Cost calculation example
    print("\nCost Calculation Example:")
    model = config["model_id_primary"]
    cost = calculate_cost(1000, 500, model)
    print(f"  Model: {model.split('.')[-1]}")
    print("  Input: 1,000 tokens")
    print("  Output: 500 tokens")
    print(f"  Cost: ${cost:.6f}")

    print("\n" + "=" * 50)
    print("Configuration validation: PASSED ✓")
