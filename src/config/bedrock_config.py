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
#
# Model IDs may be "auto": the service discovers the newest active, priced Claude model on
# Bedrock at startup (bedrock_model_discovery). Staging and production pin an approved
# primary model; pin others the same way, in the environment's secret (ADR-088).
BEDROCK_CONFIG: dict[Environment, dict[str, Any]] = {
    Environment.DEV: {
        "aws_region": "us-east-1",
        "model_id_primary": "auto",  # newest active Sonnet on Bedrock (discovered at startup)
        "model_id_fallback": "auto",  # newest active Haiku on Bedrock (discovered at startup)
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
        "model_id_primary": "auto",  # newest active Sonnet on Bedrock (discovered at startup)
        "model_id_fallback": "auto",  # newest active Haiku on Bedrock (discovered at startup)
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
        "model_id_primary": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",  # Claude Sonnet 4.5 via the US inference profile (approved pin)
        "model_id_fallback": "auto",  # newest active Haiku (the retired 3.5 Sonnet was here)
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
        "model_id_primary": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",  # Claude Sonnet 4.5 via the US inference profile (approved pin)
        "model_id_fallback": "auto",  # newest active Haiku (the retired 3.5 Sonnet was here)
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


# List prices (USD per million tokens) by Claude model family, so models found by Bedrock
# discovery, including inference-profile IDs like ``us.anthropic.claude-sonnet-5-5``, are
# priced. Exact entries in MODEL_PRICING take precedence. Keep in step with Anthropic's
# published prices; Haiku 4.5 is its price at release (verify before relying on it).
CLAUDE_FAMILY_PRICING: dict[str, dict[str, float]] = {
    "claude-opus-5-5": {"input_per_million": 4.00, "output_per_million": 20.00},
    "claude-opus-5": {"input_per_million": 5.00, "output_per_million": 25.00},
    "claude-opus-4-8": {"input_per_million": 5.00, "output_per_million": 25.00},
    "claude-sonnet-5-5": {"input_per_million": 2.00, "output_per_million": 10.00},
    "claude-sonnet-5": {"input_per_million": 2.00, "output_per_million": 10.00},
    "claude-sonnet-4-5": {"input_per_million": 3.00, "output_per_million": 15.00},
    "claude-haiku-4-5": {"input_per_million": 1.00, "output_per_million": 5.00},
}


def _family_pricing(model_id: str) -> dict[str, float] | None:
    from src.services.bedrock_model_discovery import parse_claude_model

    parsed = parse_claude_model(model_id)
    return CLAUDE_FAMILY_PRICING.get(parsed.key) if parsed else None


def has_pricing(model_id: str) -> bool:
    """Whether cost tracking can price this model (exactly or by its Claude family)."""
    return model_id in MODEL_PRICING or _family_pricing(model_id) is not None


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
    if model_id in MODEL_PRICING:
        return MODEL_PRICING[model_id].copy()
    family = _family_pricing(model_id)
    if family is not None:
        return family.copy()
    raise ValueError(
        f"Unknown model ID: {model_id}. Available models: {list(MODEL_PRICING.keys())}"
    )


def register_model_pricing(pricing: dict[str, dict[str, Any]] | None) -> list[str]:
    """
    Add pricing for models approved through configuration (ADR-088).

    An approved model upgrade brings its pricing with it (``model_pricing`` in the
    environment config or its Secrets Manager secret), so cost tracking and budgets
    cover it. Entries without numeric input and output prices are ignored.

    Args:
        pricing: {model_id: {"input_per_million": float, "output_per_million": float}}

    Returns:
        The model IDs registered
    """
    registered = []
    for model_id, prices in (pricing or {}).items():
        try:
            entry = {
                "input_per_million": float(prices["input_per_million"]),
                "output_per_million": float(prices["output_per_million"]),
            }
        except (KeyError, TypeError, ValueError):
            continue
        MODEL_PRICING[model_id] = entry
        registered.append(model_id)
    return registered


# Prompt caching (Claude Messages API cache_control): 5-minute cache writes cost 1.25x the
# input price and cache reads 0.1x.
CACHE_WRITE_MULTIPLIER = 1.25
CACHE_READ_MULTIPLIER = 0.1

# Models that accept cache_control breakpoints on Bedrock. Older models (such as the
# Claude 3 defaults) may reject them, so breakpoints are only sent to listed models.
# Environments add models with ``prompt_cache_models`` in their config or secret, alongside
# an approved model upgrade (ADR-088).
DEFAULT_PROMPT_CACHE_MODELS: frozenset[str] = frozenset(
    {
        "anthropic.claude-sonnet-4-5-20250929-v1:0",
        "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    }
)


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    model_id: str,
    cache_write_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float:
    """
    Calculate cost for a model invocation.

    Args:
        input_tokens: Number of uncached input tokens
        output_tokens: Number of output tokens
        model_id: Bedrock model identifier
        cache_write_tokens: Input tokens written to the prompt cache
        cache_read_tokens: Input tokens read from the prompt cache

    Returns:
        Cost in USD (rounded to 6 decimal places)

    Example:
        >>> cost = calculate_cost(1000, 500, "anthropic.claude-sonnet-4-5-20250929-v1:0")
        >>> print(f"${cost:.6f}")
        $0.010500
    """
    pricing = get_model_pricing(model_id)

    input_price = pricing["input_per_million"] / 1_000_000
    input_cost = input_tokens * input_price
    cache_cost = (
        cache_write_tokens * CACHE_WRITE_MULTIPLIER
        + cache_read_tokens * CACHE_READ_MULTIPLIER
    ) * input_price
    output_cost = (output_tokens / 1_000_000) * pricing["output_per_million"]

    total_cost = input_cost + cache_cost + output_cost

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
