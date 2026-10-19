"""
AWS Bedrock LLM Service
Production-ready service for Claude API integration via AWS Bedrock
with comprehensive cost controls, rate limiting, and security.

ADR-029 Phase 1.3: Semantic caching integration for 60-70% cost reduction.
"""

import asyncio
import hashlib
import json
import logging
import os
import random
import time
import uuid
from collections import OrderedDict
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Optional

# Import Redis cache service for production state management
from src.services.redis_cache_service import RedisCacheService, create_cache_service

# Retry configuration with exponential backoff and jitter
# Note: tenacity is available but not directly used - retry logic is
# implemented manually for finer control over backoff behavior
TENACITY_AVAILABLE = False
try:
    import tenacity  # noqa: F401

    TENACITY_AVAILABLE = True
except ImportError:
    pass

# Import configuration via the canonical ``src.config`` path. Previously this
# module did ``sys.path.insert(0, .../src)`` and then ``from config.X import
# ...``, which works at runtime but causes the SAME modules to live under TWO
# names in ``sys.modules`` (``config.X`` and ``src.config.X``) -- one per
# import string used. Enum class identity is per-import-string, so
# ``GuardrailMode.DISABLED`` from the two copies is unequal. That manifested
# as the CI-only failure in
# ``test_guardrail_unavailable_with_require_guardrails_false`` once another
# test in the suite happened to import via ``src.config.guardrails_config``
# first. See issue #183 cluster C.
from src.config.bedrock_config import (
    DEFAULT_PROMPT_CACHE_MODELS,
    calculate_cost,
    get_config,
    has_pricing,
    register_model_pricing,
)
from src.config.claude_models import CURRENT_CLAUDE_MODELS
from src.config.guardrails_config import (
    GuardrailMode,
    GuardrailResult,
    format_guardrail_trace,
    get_guardrail_config,
    load_guardrail_ids_from_ssm,
)
from src.services.bedrock_model_discovery import (
    _DISCOVERY_CACHE,
    AUTO,
    discover_tier_models,
    parse_claude_model,
)

# Import prompt sanitizer for input security (OWASP LLM01 prevention)
from src.services.llm_prompt_sanitizer import (
    LLMPromptSanitizer,
    SanitizationAction,
    SanitizationResult,
    ThreatLevel,
)

# Type hints for semantic cache (ADR-029 Phase 1.3)
if TYPE_CHECKING:
    from src.services.semantic_cache_service import SemanticCacheService

# AWS imports (will be installed when deploying to AWS)
try:
    import boto3
    from botocore.exceptions import ClientError

    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False
    # Mock for local development without AWS credentials

logger = logging.getLogger(__name__)

# Time constants (seconds)
SECONDS_PER_DAY = 86400
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600


class BedrockMode(Enum):
    """Operating modes for Bedrock service."""

    MOCK = "mock"  # Mock responses for testing
    AWS = "aws"  # Real AWS Bedrock API


class ModelTier(Enum):
    """
    Model tiers for task-based selection (ADR-015).

    - FAST: Haiku - simple classification, expansion, low-stakes tasks
    - ACCURATE: Sonnet - security analysis, standard patches, code review
    - MAXIMUM: Opus - cross-codebase reasoning, novel threats, complex refactoring
    """

    FAST = "fast"
    ACCURATE = "accurate"
    MAXIMUM = "maximum"


# Tier models are configuration (ADR-015 tiers, ADR-088 upgrades). Each environment sets
# ``model_id_fast``, ``model_id_accurate`` and ``model_id_maximum`` in its Bedrock secret or
# config; the default is ``auto``: at startup in AWS mode, Bedrock discovery picks the newest
# active, priced Claude model of the tier's family (see bedrock_model_discovery). Pin
# approved models in the secret; a pinned model is never replaced by discovery.
#
# MODEL_IDS is the fallback for ``auto`` when discovery cannot run (mock mode, or no
# bedrock:ListFoundationModels permission): current Claude models by their Bedrock IDs.
MODEL_IDS: dict[ModelTier, str] = {
    tier: CURRENT_CLAUDE_MODELS[tier.value] for tier in ModelTier
}

# Operation-to-model mapping (ADR-015)
# New operations default to ACCURATE tier for safety
OPERATION_MODEL_MAP: dict[str, ModelTier] = {
    # Fast tier - simple, low-stakes tasks (~40% of calls)
    "query_intent_analysis": ModelTier.FAST,
    "query_expansion": ModelTier.FAST,
    "file_type_classification": ModelTier.FAST,
    "syntax_validation": ModelTier.FAST,
    "format_conversion": ModelTier.FAST,
    "metadata_extraction": ModelTier.FAST,
    "simple_summarization": ModelTier.FAST,
    # Accurate tier - security-critical operations (~55% of calls)
    "vulnerability_ranking": ModelTier.ACCURATE,
    "security_result_scoring": ModelTier.ACCURATE,
    "patch_generation": ModelTier.ACCURATE,
    "code_review": ModelTier.ACCURATE,
    "threat_assessment": ModelTier.ACCURATE,
    "compliance_check": ModelTier.ACCURATE,
    "single_file_analysis": ModelTier.ACCURATE,
    "cve_impact_assessment": ModelTier.ACCURATE,
    # RuntimeIncidentAgent operations (ADR-025)
    "rca_generation": ModelTier.ACCURATE,
    "mitigation_planning": ModelTier.ACCURATE,
    # Maximum tier - complex reasoning operations (~5% of calls)
    "cross_codebase_correlation": ModelTier.MAXIMUM,
    "novel_threat_detection": ModelTier.MAXIMUM,
    "multi_file_refactoring": ModelTier.MAXIMUM,
    "compliance_edge_case": ModelTier.MAXIMUM,
    "architecture_impact_analysis": ModelTier.MAXIMUM,
    "zero_day_pattern_analysis": ModelTier.MAXIMUM,
    "dependency_chain_reasoning": ModelTier.MAXIMUM,
}

# Operation to QueryType mapping for semantic caching (ADR-029 Phase 1.3)
# Maps Bedrock operations to cache TTL categories
OPERATION_QUERY_TYPE_MAP: dict[str, str] = {
    # Vulnerability analysis (24h TTL - stable analysis)
    "vulnerability_ranking": "vulnerability_analysis",
    "security_result_scoring": "vulnerability_analysis",
    "threat_assessment": "vulnerability_analysis",
    "cve_impact_assessment": "vulnerability_analysis",
    "novel_threat_detection": "vulnerability_analysis",
    "zero_day_pattern_analysis": "vulnerability_analysis",
    # Code review (12h TTL - moderately stable)
    "code_review": "code_review",
    "compliance_check": "code_review",
    "compliance_edge_case": "code_review",
    "single_file_analysis": "code_review",
    "rca_generation": "code_review",
    # Query planning (24h TTL - stable strategy)
    "query_intent_analysis": "query_planning",
    "query_expansion": "query_planning",
    # Code generation (1h TTL - may need updates)
    "patch_generation": "code_generation",
    "multi_file_refactoring": "code_generation",
    "mitigation_planning": "code_generation",
    # Validation (6h TTL - may change with code)
    "syntax_validation": "validation",
    # General (12h default)
    "file_type_classification": "general",
    "format_conversion": "general",
    "metadata_extraction": "general",
    "simple_summarization": "general",
    "cross_codebase_correlation": "general",
    "architecture_impact_analysis": "general",
    "dependency_chain_reasoning": "general",
}


def get_model_for_operation(
    operation: str | None, model_ids: dict[ModelTier, str] | None = None
) -> tuple[ModelTier, str]:
    """
    Get the appropriate model tier and ID for an operation.

    Args:
        operation: Operation name (e.g., "query_intent_analysis")
        model_ids: The deployment's tier-to-model map (defaults to MODEL_IDS)

    Returns:
        Tuple of (ModelTier, model_id)
    """
    if operation is None:
        # Default to ACCURATE tier for safety
        tier = ModelTier.ACCURATE
    else:
        tier = OPERATION_MODEL_MAP.get(operation, ModelTier.ACCURATE)
    return tier, (model_ids or MODEL_IDS)[tier]


_JSON_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
}


def schema_problems(data: Any, schema: dict[str, Any], path: str = "") -> list[str]:
    """
    Check data against the subset of JSON Schema used for structured output: type,
    required, properties, items, and enum. Returns the problems found (empty if valid).
    """
    problems: list[str] = []
    where = path or "output"
    expected = schema.get("type")
    if expected in _JSON_TYPES:
        ok = isinstance(data, _JSON_TYPES[expected]) and not (
            expected in ("integer", "number") and isinstance(data, bool)
        )
        if not ok:
            return [f"{where} should be {expected}"]
    if "enum" in schema and data not in schema["enum"]:
        problems.append(f"{where} should be one of {schema['enum']}")
    if isinstance(data, dict):
        for key in schema.get("required", []):
            if key not in data:
                problems.append(f"{where} is missing {key}")
        for key, sub in (schema.get("properties") or {}).items():
            if key in data:
                problems += schema_problems(
                    data[key], sub, f"{path}.{key}" if path else key
                )
    if isinstance(data, list) and "items" in schema:
        for i, item in enumerate(data):
            problems += schema_problems(item, schema["items"], f"{where}[{i}]")
    return problems


def model_request_rules(model_id: str) -> set[str]:
    """
    Request fields a Claude model is known to reject, by family and version:

    - ``no_sampling``: non-default temperature/top_p/top_k return a 400 (Sonnet 5+,
      Opus 4.7+, Fable, Mythos); omit them.
    - ``no_forced_tool_choice``: ``tool_choice`` ``any``/``tool`` returns a 400 (Sonnet 5+,
      Opus 5+, Fable, Mythos; thinking is on by default there); use ``auto``.

    Models not listed here are adapted at runtime if Bedrock rejects a field.
    """
    parsed = parse_claude_model(model_id)
    if parsed is None:
        return set()
    family, version = parsed.family, parsed.version
    rules: set[str] = set()
    newest = family in ("fable", "mythos")
    if (
        newest
        or (family == "opus" and version >= (4, 7))
        or (family == "sonnet" and version >= (5, 0))
    ):
        rules.add("no_sampling")
    if newest or (family in ("opus", "sonnet") and version >= (5, 0)):
        rules.add("no_forced_tool_choice")
    return rules


def _rejected_field(error_text: str) -> str | None:
    """The request rule a Bedrock validation error asks for, if it names a field."""
    text = error_text.lower()
    if "cache_control" in text or "prompt caching" in text or "cache" in text:
        return "no_cache"
    if "tool_choice" in text:
        return "no_forced_tool_choice"
    if any(field in text for field in ("temperature", "top_p", "top_k", "sampling")):
        return "no_sampling"
    return None


def _adapt_request(body: dict[str, Any], rules: set[str]) -> dict[str, Any]:
    """A copy of the request body with the model's request rules applied."""
    adapted = dict(body)
    if "no_sampling" in rules:
        for field in ("temperature", "top_p", "top_k"):
            adapted.pop(field, None)
    choice = adapted.get("tool_choice")
    if (
        "no_forced_tool_choice" in rules
        and isinstance(choice, dict)
        and choice.get("type") in ("any", "tool")
    ):
        adapted["tool_choice"] = {"type": "auto"}
    return adapted


def resolve_model_tiers(
    config: dict[str, Any],
    overrides: dict[str, Any] | None = None,
    is_priced: Callable[[str], bool] | None = None,
    discovered: dict[str, str] | None = None,
) -> dict[ModelTier, str]:
    """The tier-to-model map for a deployment: secret overrides, then config, then ``auto``.

    Keys are ``model_id_fast``, ``model_id_accurate`` and ``model_id_maximum``. ``auto``
    takes the tier's model from ``discovered`` (Bedrock discovery), else MODEL_IDS. When
    ``is_priced`` is given, a configured model without pricing is refused (logged, and
    the tier keeps its default): cost tracking and budgets must cover every live model.
    """
    overrides = overrides or {}
    discovered = discovered or {}
    tiers: dict[ModelTier, str] = {}
    for tier, fallback in MODEL_IDS.items():
        # For "auto": a deployment-wide AURA_MODEL_<TIER> pin, then discovery, then the
        # built-in current model (the same order as claude_model() for other services)
        env_pin = os.environ.get(f"AURA_MODEL_{tier.value.upper()}")
        default = (
            (env_pin if env_pin and env_pin != AUTO else None)
            or discovered.get(tier.value)
            or fallback
        )
        key = f"model_id_{tier.value}"
        model_id = overrides.get(key) or config.get(key) or AUTO
        if model_id == AUTO:
            model_id = default
        if model_id != default and is_priced is not None and not is_priced(model_id):
            logger.error(
                "Model %s for the %s tier has no pricing; keeping %s. Add it to "
                "model_pricing with the upgrade.",
                model_id,
                tier.value,
                default,
            )
            model_id = default
        tiers[tier] = model_id
    return tiers


# Custom Exceptions
class BudgetExceededError(Exception):
    """Raised when budget limit is exceeded."""


class RateLimitExceededError(Exception):
    """Raised when rate limit is exceeded."""


class BedrockError(Exception):
    """General Bedrock API error."""


class GuardrailViolationError(Exception):
    """Raised when guardrail blocks content."""

    def __init__(
        self, message: str, violations: list[dict[str, Any]] | None = None
    ) -> None:
        super().__init__(message)
        self.violations = violations or []


class StructuredOutputError(Exception):
    """Raised when the model does not return the requested structured output."""


class PromptInjectionError(Exception):
    """Raised when prompt injection is detected (OWASP LLM01)."""

    def __init__(
        self,
        message: str,
        threat_level: ThreatLevel,
        patterns_detected: list[str] | None = None,
    ):
        super().__init__(message)
        self.threat_level = threat_level
        self.patterns_detected = patterns_detected or []


class BedrockLLMService:
    """
    Production-ready AWS Bedrock LLM service with:
    - Cost tracking and budget enforcement
    - Rate limiting (per minute/hour/day)
    - Token counting and cost calculation
    - Response caching (reduces costs)
    - Error handling with exponential backoff retry
    - Security best practices (IAM roles, no hardcoded credentials)
    - CloudWatch metrics integration
    - DynamoDB cost logging

    Usage:
        >>> service = BedrockLLMService(mode=BedrockMode.AWS)
        >>> result = service.invoke_model(
        ...     prompt="Fix this security vulnerability...",
        ...     agent="ReviewerAgent",
        ...     max_tokens=2000
        ... )

        >>> print(f"Response: {result['response']}")
        >>> print(f"Cost: ${result['cost_usd']:.6f}")

    Cache Configuration:
        MAX_RESPONSE_CACHE_SIZE: Maximum cached responses (default 1000)
    """

    # Cache size limits (prevents unbounded memory growth)
    MAX_RESPONSE_CACHE_SIZE = int(os.environ.get("LLM_MAX_RESPONSE_CACHE_SIZE", "1000"))

    def __init__(
        self,
        mode: BedrockMode = BedrockMode.MOCK,
        environment: str | None = None,
        semantic_cache: "SemanticCacheService | None" = None,
        sanitize_prompts: bool = True,
        sanitizer_strict_mode: bool = False,
        redis_cache: RedisCacheService | None = None,
        require_guardrails: bool = False,
    ) -> None:
        """
        Initialize Bedrock LLM service.

        Args:
            mode: Operating mode (MOCK or AWS)
            environment: Override environment (defaults to AURA_ENV)
            semantic_cache: Optional semantic cache service (ADR-029 Phase 1.3)
            sanitize_prompts: Enable prompt sanitization (default True, OWASP LLM01)
            sanitizer_strict_mode: Block suspicious prompts rather than sanitize
            redis_cache: Optional Redis cache service for production state management
            require_guardrails: If True, fail startup when guardrails unavailable
        """
        self.mode = mode
        self.config = get_config()
        self.require_guardrails = require_guardrails

        # Prompt sanitization (OWASP LLM01: Prompt Injection prevention)
        self.sanitize_prompts = sanitize_prompts
        self.prompt_sanitizer: Optional[LLMPromptSanitizer]
        if sanitize_prompts:
            # Create a new sanitizer instance with the specified strict mode
            # Don't use singleton to allow different configurations per service
            self.prompt_sanitizer = LLMPromptSanitizer(
                strict_mode=sanitizer_strict_mode,
                log_threats=True,
            )
            logger.info(
                f"Prompt sanitization enabled (strict_mode={sanitizer_strict_mode})"
            )
        else:
            self.prompt_sanitizer = None
            logger.warning("Prompt sanitization disabled - vulnerable to LLM01")

        # Override environment if specified
        if environment:
            os.environ["AURA_ENV"] = environment
            self.config = get_config()

        self.environment = os.environ.get("AURA_ENV", "development")

        # Initialize AWS clients (only in AWS mode)
        if self.mode == BedrockMode.AWS and AWS_AVAILABLE:
            self._init_aws_clients()
        else:
            if self.mode == BedrockMode.AWS:
                logger.warning(
                    "AWS mode requested but boto3 not available. Falling back to MOCK mode."
                )
                self.mode = BedrockMode.MOCK
            self._init_mock_mode()

        # Tier models (ADR-015) come from configuration so upgrades and rollbacks are
        # config changes (ADR-088); secrets override config, config overrides defaults
        overrides = getattr(self, "_secret_overrides", None) or {}
        register_model_pricing(self.config.get("model_pricing"))
        register_model_pricing(overrides.get("model_pricing"))
        self.model_tiers = resolve_model_tiers(
            self.config,
            overrides,
            is_priced=has_pricing,
            discovered=self._discover_models(overrides),
        )
        # model_id_primary / model_id_fallback may also be ``auto``: the accurate and
        # fast tier models
        if getattr(self, "model_id_primary", AUTO) in (AUTO, None):
            self.model_id_primary = self.model_tiers[ModelTier.ACCURATE]
        if getattr(self, "model_id_fallback", AUTO) in (AUTO, None):
            self.model_id_fallback = self.model_tiers[ModelTier.FAST]
        logger.info(
            "Model tiers: "
            + ", ".join(f"{t.value}={m}" for t, m in self.model_tiers.items())
            + f"; primary={self.model_id_primary}"
        )
        # Request fields a model turned out to reject (learned from 400s), per model
        self._learned_quirks: dict[str, set[str]] = {}

        # Prompt caching for tool-use conversations, on models known to accept it
        self.prompt_cache_models: set[str] = (
            set(DEFAULT_PROMPT_CACHE_MODELS)
            | set(self.config.get("prompt_cache_models") or [])
            | set(overrides.get("prompt_cache_models") or [])
        )
        self._cache_rejected: set[str] = set()

        # Initialize Redis cache for production state management
        # Provides externalized state for cost tracking, rate limiting, and response caching
        # Falls back to in-memory when Redis unavailable
        self._redis_cache = redis_cache or create_cache_service()
        logger.info(
            f"State cache backend: {self._redis_cache.backend.value} "
            f"(redis_connected={self._redis_cache.is_redis_connected})"
        )

        # Cost tracking - use Redis if available, otherwise in-memory
        # Load initial values from Redis or DynamoDB
        self.daily_spend = self._redis_cache.get_daily_cost()
        self.monthly_spend = self._redis_cache.get_monthly_cost()

        # Rate limiting - stored in Redis for distributed rate limiting
        # In-memory fallback list for compatibility
        self.request_history: list[float] = self._redis_cache.get_request_history()

        # Response cache using OrderedDict for O(1) LRU eviction
        # Redis provides distributed caching; OrderedDict is local fallback
        self.response_cache: OrderedDict[str, dict[str, Any]] = OrderedDict()

        # Semantic cache (ADR-029 Phase 1.3) - Vector similarity for 60-70% hit rate
        self.semantic_cache = semantic_cache
        if semantic_cache:
            logger.info(
                f"Semantic caching enabled: mode={semantic_cache.mode.value}, "
                f"threshold={semantic_cache.similarity_threshold}"
            )

        # Initialize guardrails (ADR-029 Phase 1.1)
        self.guardrail_config = get_guardrail_config()
        if self.mode == BedrockMode.AWS and AWS_AVAILABLE:
            self._init_guardrails()
        else:
            logger.info("Guardrails disabled in mock mode")

        logger.info(
            f"BedrockLLMService initialized in {self.mode.value} mode for {self.environment} environment"
        )

    def _init_aws_clients(self) -> None:
        """Initialize AWS clients for production use."""
        try:
            self.bedrock_runtime = boto3.client(
                service_name="bedrock-runtime", region_name=self.config["aws_region"]
            )

            # Optional: Secrets Manager for additional config
            # (Not strictly needed since we use IAM roles, but useful for model config)
            try:
                self.secrets_manager = boto3.client(
                    service_name="secretsmanager", region_name=self.config["aws_region"]
                )
                self._load_secrets()
            except Exception as e:
                logger.warning(
                    f"Could not load secrets from Secrets Manager: {e}. Using config defaults."
                )
                self.model_id_primary = self.config["model_id_primary"]
                self.model_id_fallback = self.config["model_id_fallback"]

            # DynamoDB for cost tracking
            self.dynamodb = boto3.resource(
                service_name="dynamodb", region_name=self.config["aws_region"]
            )
            cost_table_name = self.config.get("cost_table_name", "aura-llm-costs")
            self.cost_table = self.dynamodb.Table(cost_table_name)

            # CloudWatch for metrics
            self.cloudwatch = boto3.client(
                service_name="cloudwatch", region_name=self.config["aws_region"]
            )

            # Load current spend from DynamoDB
            self.daily_spend = self._get_daily_spend()
            self.monthly_spend = self._get_monthly_spend()

            logger.info("AWS clients initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize AWS clients: {e}")
            logger.warning("Falling back to MOCK mode")
            self.mode = BedrockMode.MOCK
            self._init_mock_mode()

    # Agents check this (``getattr(llm, "supports_tool_use", False) is True``) before using
    # tool use or structured output, so test doubles and older clients keep the text path.
    supports_tool_use = True

    def _discover_models(self, overrides: dict[str, Any]) -> dict[str, str]:
        """Bedrock discovery for tiers left on ``auto`` (AWS mode only; cached per region)."""
        keys = [f"model_id_{t.value}" for t in ModelTier] + [
            "model_id_primary",
            "model_id_fallback",
        ]
        wants_auto = any(
            (overrides.get(k) or self.config.get(k) or AUTO) == AUTO for k in keys
        )
        if self.mode != BedrockMode.AWS or not wants_auto or not AWS_AVAILABLE:
            return {}
        region = self.config["aws_region"]
        if region in _DISCOVERY_CACHE:
            return _DISCOVERY_CACHE[region]
        try:
            client = boto3.client("bedrock", region_name=region)
            found = discover_tier_models(client, region, has_pricing)
        except Exception as e:  # permissions, network, partition without the API
            logger.warning(
                "Bedrock model discovery failed (%s); auto tiers use the built-in "
                "defaults. Grant bedrock:ListFoundationModels and "
                "bedrock:ListInferenceProfiles, or pin models in %s.",
                e,
                self.config.get("secrets_path"),
            )
            return {}
        logger.info("Bedrock discovery chose: %s", found)
        _DISCOVERY_CACHE[region] = found
        return found

    def _tier_models(self) -> dict[ModelTier, str]:
        """The resolved tier-to-model map (defaults if the service was built without init)."""
        return getattr(self, "model_tiers", None) or MODEL_IDS

    def _init_mock_mode(self) -> None:
        """Initialize mock mode for local development/testing."""
        self.model_id_primary = self.config["model_id_primary"]
        self.model_id_fallback = self.config["model_id_fallback"]
        logger.info("Mock mode initialized (no AWS calls will be made)")

    def _init_guardrails(self) -> None:
        """
        Initialize Bedrock Guardrails from SSM parameters (ADR-029).

        Publishes CloudWatch metric on failure for alerting.
        If require_guardrails=True and initialization fails, raises RuntimeError.
        """
        try:
            ssm_client = boto3.client("ssm", region_name=self.config["aws_region"])
            self.guardrail_config = load_guardrail_ids_from_ssm(
                self.guardrail_config, ssm_client
            )

            if self.guardrail_config.guardrail_id:
                logger.info(
                    f"Guardrails initialized: {self.guardrail_config.guardrail_id} "
                    f"(version: {self.guardrail_config.guardrail_version}, "
                    f"mode: {self.guardrail_config.mode.value})"
                )
                # Publish success metric
                self._publish_guardrail_metric(success=True)
            else:
                logger.warning(
                    "Guardrail ID not found in SSM - guardrails will be disabled"
                )
                self.guardrail_config.mode = GuardrailMode.DISABLED
                # Publish failure metric for alerting
                self._publish_guardrail_metric(
                    success=False, reason="guardrail_id_not_found"
                )
                self._handle_guardrail_failure(
                    "Guardrail ID not found in SSM parameters"
                )

        except Exception as e:
            logger.error(f"Failed to initialize guardrails: {e}")
            self.guardrail_config.mode = GuardrailMode.DISABLED
            # Publish failure metric for alerting
            self._publish_guardrail_metric(success=False, reason="initialization_error")
            self._handle_guardrail_failure(f"Guardrail initialization failed: {e}")

    def _publish_guardrail_metric(
        self, success: bool, reason: str | None = None
    ) -> None:
        """
        Publish guardrail initialization metric to CloudWatch.

        Creates alarmable metric for monitoring guardrail availability.
        Metric: Aura/LLM/GuardrailInitialization with dimensions for environment and status.
        """
        if not hasattr(self, "cloudwatch") or not self.cloudwatch:
            logger.debug("CloudWatch client not available - skipping guardrail metric")
            return

        try:
            metric_data = [
                {
                    "MetricName": "GuardrailInitialization",
                    "Value": 1.0 if success else 0.0,
                    "Unit": "Count",
                    "Dimensions": [
                        {"Name": "Environment", "Value": self.environment},
                        {
                            "Name": "Status",
                            "Value": "success" if success else "failure",
                        },
                    ],
                }
            ]

            # Add failure reason dimension if applicable
            if not success and reason:
                metric_data.append(
                    {
                        "MetricName": "GuardrailInitializationFailure",
                        "Value": 1.0,
                        "Unit": "Count",
                        "Dimensions": [
                            {"Name": "Environment", "Value": self.environment},
                            {"Name": "FailureReason", "Value": reason},
                        ],
                    }
                )

            self.cloudwatch.put_metric_data(
                Namespace="Aura/LLM",
                MetricData=metric_data,
            )

            if success:
                logger.debug("Published guardrail initialization success metric")
            else:
                logger.warning(
                    f"Published guardrail initialization failure metric: reason={reason}"
                )

        except Exception as e:
            logger.error(f"Failed to publish guardrail metric: {e}")

    def _handle_guardrail_failure(self, message: str) -> None:
        """
        Handle guardrail initialization failure based on require_guardrails setting.

        If require_guardrails=True, raises RuntimeError to prevent service startup.
        Otherwise, logs warning and continues with guardrails disabled.
        """
        if self.require_guardrails:
            error_msg = (
                f"CRITICAL: {message}. "
                "Service startup blocked because require_guardrails=True. "
                "Set require_guardrails=False or fix guardrail configuration."
            )
            logger.critical(error_msg)
            raise RuntimeError(error_msg)
        else:
            logger.warning(
                f"{message}. Continuing with guardrails disabled. "
                "Set require_guardrails=True to enforce guardrail availability."
            )

    def _load_secrets(self) -> None:
        """Load additional configuration from AWS Secrets Manager."""
        try:
            response = self.secrets_manager.get_secret_value(
                SecretId=self.config["secrets_path"]
            )
            secrets = json.loads(response["SecretString"])
            self._secret_overrides = secrets

            # Override config with secrets if present
            self.model_id_primary = secrets.get(
                "model_id_primary", self.config["model_id_primary"]
            )
            self.model_id_fallback = secrets.get(
                "model_id_fallback", self.config["model_id_fallback"]
            )

            logger.info("Secrets loaded successfully from Secrets Manager")

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "ResourceNotFoundException":
                logger.warning(
                    f"Secret not found: {self.config['secrets_path']}. Using config defaults."
                )
                # Set model IDs from config when secret not found
                self.model_id_primary = self.config["model_id_primary"]
                self.model_id_fallback = self.config["model_id_fallback"]
            else:
                logger.error(f"Failed to load secrets: {e}")
                raise

    def _get_daily_spend(self) -> float:
        """Query DynamoDB for today's spend."""
        if self.mode == BedrockMode.MOCK:
            return 0.0

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        try:
            response = self.cost_table.query(
                IndexName="date-index",
                KeyConditionExpression="#date = :date",
                ExpressionAttributeNames={"#date": "date"},
                ExpressionAttributeValues={":date": today},
            )
            total = sum(
                float(str(item.get("cost_usd", 0)))
                for item in response.get("Items", [])
            )
            logger.debug(f"Daily spend loaded: ${total:.2f}")
            return total

        except Exception as e:
            logger.error(f"Failed to query daily spend: {e}")
            return 0.0

    def _get_monthly_spend(self) -> float:
        """Query DynamoDB for this month's spend."""
        if self.mode == BedrockMode.MOCK:
            return 0.0

        month = datetime.now(UTC).strftime("%Y-%m")
        try:
            response = self.cost_table.query(
                IndexName="month-index",
                KeyConditionExpression="#month = :month",
                ExpressionAttributeNames={"#month": "month"},
                ExpressionAttributeValues={":month": month},
            )
            total = sum(
                float(str(item.get("cost_usd", 0)))
                for item in response.get("Items", [])
            )
            logger.debug(f"Monthly spend loaded: ${total:.2f}")
            return total

        except Exception as e:
            logger.error(f"Failed to query monthly spend: {e}")
            return 0.0

    def _check_budget(self) -> bool:
        """
        Check if we're within budget limits.

        Returns:
            True if within budget, False otherwise
        """
        daily_limit = self.config["daily_budget_usd"]
        monthly_limit = self.config["monthly_budget_usd"]

        if self.daily_spend >= daily_limit:
            logger.warning(
                f"Daily budget exceeded: ${self.daily_spend:.2f} >= ${daily_limit:.2f}"
            )
            return False

        if self.monthly_spend >= monthly_limit:
            logger.warning(
                f"Monthly budget exceeded: ${self.monthly_spend:.2f} >= ${monthly_limit:.2f}"
            )
            return False

        # Warn at 80% threshold
        if self.daily_spend >= daily_limit * 0.8:
            logger.warning(
                f"Daily budget at {(self.daily_spend / daily_limit) * 100:.1f}%: "
                f"${self.daily_spend:.2f}/${daily_limit:.2f}"
            )

        return True

    def _check_rate_limit(self) -> bool:
        """
        Check if we're within rate limits using Redis for distributed tracking.

        Returns:
            True if within limits, False otherwise
        """
        # Use Redis for distributed rate limiting
        # Falls back to in-memory if Redis unavailable
        recent_minute = self._redis_cache.get_request_count(
            identifier="global", window_seconds=SECONDS_PER_MINUTE
        )
        if recent_minute >= self.config["max_requests_per_minute"]:
            logger.warning(
                f"Rate limit exceeded (per minute): {recent_minute}/"
                f"{self.config['max_requests_per_minute']}"
            )
            return False

        # Check per-hour limit
        recent_hour = self._redis_cache.get_request_count(
            identifier="global", window_seconds=SECONDS_PER_HOUR
        )
        if recent_hour >= self.config["max_requests_per_hour"]:
            logger.warning(
                f"Rate limit exceeded (per hour): {recent_hour}/"
                f"{self.config['max_requests_per_hour']}"
            )
            return False

        # Check per-day limit
        recent_day = self._redis_cache.get_request_count(
            identifier="global", window_seconds=SECONDS_PER_DAY
        )
        if recent_day >= self.config["max_requests_per_day"]:
            logger.warning(
                f"Rate limit exceeded (per day): {recent_day}/{self.config['max_requests_per_day']}"
            )
            return False

        return True

    def _record_request(self) -> None:
        """Record a request for rate limiting using Redis."""
        self._redis_cache.record_request(identifier="global")
        # Update local history for backward compatibility
        self.request_history = self._redis_cache.get_request_history()

    def _cache_key(self, prompt: str, model_id: str, params: dict[str, Any]) -> str:
        """Generate cache key for request."""
        cache_str = f"{prompt}|{model_id}|{json.dumps(params, sort_keys=True)}"
        return hashlib.sha256(cache_str.encode()).hexdigest()

    def _get_cached_response(self, cache_key: str) -> dict[str, Any] | None:
        """
        Retrieve cached response if available and not expired.

        Uses Redis as primary cache with in-memory OrderedDict fallback.
        Provides O(1) LRU access pattern.
        """
        if not self.config.get("cache_enabled", True):
            return None

        cache_ttl = self.config.get("cache_ttl_seconds", 86400)

        # Try Redis first for distributed caching
        redis_cached = self._redis_cache.get_response(cache_key)
        if redis_cached:
            logger.info("Cache hit (Redis) - returning cached response")
            cached_result: dict[str, Any] = redis_cached.copy()
            cached_result["cached"] = True
            cached_result["cache_source"] = "redis"
            cached_result["cost_usd"] = 0.0  # No cost for cached responses
            return cached_result

        # Fall back to local OrderedDict cache
        if cache_key in self.response_cache:
            cached = self.response_cache[cache_key]

            if time.time() - cached["timestamp"] < cache_ttl:
                logger.info("Cache hit (memory) - returning cached response")
                # Move to end to mark as recently used (O(1) with OrderedDict)
                self.response_cache.move_to_end(cache_key)
                cached_result = cached["response"].copy()
                cached_result["cached"] = True
                cached_result["cache_source"] = "memory"
                cached_result["cost_usd"] = 0.0  # No cost for cached responses
                return cached_result
            # Expired - remove from cache
            del self.response_cache[cache_key]

        return None

    def _record_cost(
        self,
        request_id: str,
        agent: str,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        tier: ModelTier | None = None,
        operation: str | None = None,
    ):
        """Record cost to DynamoDB and CloudWatch metrics including tier tracking (ADR-015)."""
        now = datetime.now(UTC)

        # Update cost in Redis (or in-memory fallback) for distributed tracking
        # This provides consistent cost tracking across service instances
        self.daily_spend, self.monthly_spend = self._redis_cache.add_cost(cost_usd)

        if self.mode == BedrockMode.MOCK:
            logger.debug(f"[MOCK] Cost recorded: ${cost_usd:.6f} for {agent}")
            return

        # Determine tier value for metrics
        tier_value = tier.value if tier else "unknown"
        operation_value = operation or "unspecified"

        # Record to DynamoDB
        try:
            self.cost_table.put_item(
                Item={
                    "request_id": request_id,
                    "timestamp": now.isoformat(),
                    "date": now.strftime("%Y-%m-%d"),
                    "month": now.strftime("%Y-%m"),
                    "agent": agent,
                    "model": model_id,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost_usd": str(cost_usd),  # Store as string for decimal precision
                    "environment": self.environment,
                    "tier": tier_value,  # ADR-015: Track model tier
                    "operation": operation_value,  # ADR-015: Track operation type
                }
            )
            logger.debug(f"Cost recorded to DynamoDB: ${cost_usd:.6f}")

        except Exception as e:
            logger.error(f"Failed to record cost to DynamoDB: {e}")

        # Send metrics to CloudWatch
        try:
            model_short_name = model_id.split(".")[-1].split("-")[
                0
            ]  # Extract "claude" from full ID

            # Base metrics: tokens and cost by agent/model
            metric_data = [
                {
                    "MetricName": "TokensUsed",
                    "Value": input_tokens + output_tokens,
                    "Unit": "Count",
                    "Dimensions": [
                        {"Name": "Agent", "Value": agent},
                        {"Name": "Model", "Value": model_short_name},
                        {"Name": "Environment", "Value": self.environment},
                    ],
                },
                {
                    "MetricName": "CostUSD",
                    "Value": cost_usd,
                    "Unit": "None",
                    "Dimensions": [
                        {"Name": "Agent", "Value": agent},
                        {"Name": "Model", "Value": model_short_name},
                        {"Name": "Environment", "Value": self.environment},
                    ],
                },
                # ADR-015: Tier usage tracking
                {
                    "MetricName": "TierInvocations",
                    "Value": 1,
                    "Unit": "Count",
                    "Dimensions": [
                        {"Name": "Tier", "Value": tier_value},
                        {"Name": "Environment", "Value": self.environment},
                    ],
                },
                {
                    "MetricName": "CostByTier",
                    "Value": cost_usd,
                    "Unit": "None",
                    "Dimensions": [
                        {"Name": "Tier", "Value": tier_value},
                        {"Name": "Environment", "Value": self.environment},
                    ],
                },
            ]

            # ADR-015: Detect security operation misuse (fast tier on security ops)
            # Security operations that should use ACCURATE or MAXIMUM tier
            security_operations = {
                "vulnerability_ranking",
                "security_result_scoring",
                "patch_generation",
                "threat_assessment",
                "compliance_check",
                "cve_impact_assessment",
            }
            if tier == ModelTier.FAST and operation_value in security_operations:
                metric_data.append(
                    {
                        "MetricName": "SecurityOperationMisuse",
                        "Value": 1,
                        "Unit": "Count",
                        "Dimensions": [
                            {"Name": "Operation", "Value": operation_value},
                            {"Name": "Environment", "Value": self.environment},
                        ],
                    }
                )
                logger.warning(
                    f"Security operation '{operation_value}' using FAST tier - "
                    "should use ACCURATE or MAXIMUM tier"
                )

            self.cloudwatch.put_metric_data(
                Namespace="Aura/LLM", MetricData=metric_data
            )
            logger.debug("Metrics sent to CloudWatch")

        except Exception as e:
            logger.error(f"Failed to send CloudWatch metrics: {e}")

    def _invoke_bedrock_api(
        self,
        model_id: str,
        prompt: str,
        system_prompt: str | None,
        max_tokens: int,
        temperature: float,
        apply_guardrails: bool = True,
    ) -> dict[str, Any]:
        """
        Invoke AWS Bedrock API with optional guardrails (ADR-029).

        Includes exponential backoff with jitter for ThrottlingException.

        Returns:
            {
                'text': str,
                'input_tokens': int,
                'output_tokens': int,
                'guardrail_result': GuardrailResult | None
            }
        """
        # Prepare request body (Claude Messages API format)
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }

        if system_prompt:
            request_body["system"] = system_prompt

        response_body, guardrail_result = self._send(
            model_id, request_body, apply_guardrails
        )

        # Parse response (Claude Messages API format)
        text_response = "".join(
            block.get("text", "")
            for block in response_body["content"]
            if block.get("type", "text") == "text"
        )
        return {
            "text": text_response,
            "input_tokens": response_body["usage"]["input_tokens"],
            "output_tokens": response_body["usage"]["output_tokens"],
            "guardrail_result": guardrail_result,
        }

    def _invoke_bedrock_messages(
        self,
        model_id: str,
        request_body: dict[str, Any],
        apply_guardrails: bool = True,
    ) -> tuple[dict[str, Any], "GuardrailResult | None"]:
        """
        Send a Claude Messages API request body to Bedrock, with guardrails (ADR-029)
        and throttling retries. Shared by text and tool-use calls.

        Returns:
            (parsed response body, guardrail result or None)
        """
        invoke_params: dict[str, Any] = {
            "modelId": model_id,
            "body": json.dumps(request_body),
        }

        # Add guardrails if enabled (ADR-029)
        guardrail_result: GuardrailResult | None = None
        if (
            apply_guardrails
            and self.guardrail_config.mode != GuardrailMode.DISABLED
            and self.guardrail_config.guardrail_id
        ):
            invoke_params["guardrailIdentifier"] = self.guardrail_config.guardrail_id
            invoke_params["guardrailVersion"] = (
                self.guardrail_config.guardrail_version or "DRAFT"
            )
            # Enable trace for visibility into guardrail decisions
            invoke_params["trace"] = "ENABLED"
            logger.debug(
                f"Applying guardrail {self.guardrail_config.guardrail_id} "
                f"(version: {invoke_params['guardrailVersion']})"
            )

        # Invoke Bedrock with retry logic for throttling
        response = self._invoke_with_retry(invoke_params, model_id)

        response_body = json.loads(response["body"].read())

        # Parse guardrail trace if present (ADR-029)
        if "amazon-bedrock-trace" in response_body:
            trace = response_body["amazon-bedrock-trace"]
            guardrail_trace = trace.get("guardrail", {})
            violations = format_guardrail_trace(guardrail_trace)

            # Determine action taken
            stop_reason = response_body.get("stop_reason", "")
            if stop_reason == "guardrail_intervened":
                action_taken = "blocked"
            elif violations:
                action_taken = "anonymized"
            else:
                action_taken = "none"

            guardrail_result = GuardrailResult(
                passed=(stop_reason != "guardrail_intervened"),
                action_taken=action_taken,
                violations=violations,
                trace_id=guardrail_trace.get("traceId"),
                guardrail_id=self.guardrail_config.guardrail_id,
            )

            if violations:
                logger.warning(
                    f"Guardrail violations detected: {len(violations)} - "
                    f"Action: {action_taken}"
                )
                for v in violations:
                    logger.warning(
                        f"  - {v['type']}: {v.get('name') or v.get('category')}"
                    )

            # Handle blocking in ENFORCE mode
            if (
                self.guardrail_config.mode == GuardrailMode.ENFORCE
                and stop_reason == "guardrail_intervened"
            ):
                raise GuardrailViolationError(
                    "Response blocked by guardrail policy",
                    violations=violations,
                )

        return response_body, guardrail_result

    def _invoke_with_retry(
        self, invoke_params: dict[str, Any], model_id: str
    ) -> dict[str, Any]:
        """
        Invoke Bedrock API with exponential backoff and jitter for throttling.

        Implements retry logic with the following characteristics:
        - Max 5 retry attempts
        - Exponential backoff: 1s, 2s, 4s, 8s, 16s base delays
        - Jitter: +/- 0-1s random delay to prevent thundering herd
        - Only retries on ThrottlingException

        Args:
            invoke_params: Parameters for bedrock_runtime.invoke_model()
            model_id: Model ID for logging

        Returns:
            Bedrock API response

        Raises:
            RateLimitExceededError: If throttling persists after all retries
            BedrockError: For other API errors
        """
        max_attempts = 5
        base_delay = 1.0  # Initial delay in seconds
        max_delay = 32.0  # Cap the delay

        for attempt in range(max_attempts):
            try:
                logger.info(
                    f"Invoking Bedrock model: {model_id} (attempt {attempt + 1})"
                )
                return self.bedrock_runtime.invoke_model(**invoke_params)

            except ClientError as e:
                error_code = e.response["Error"]["Code"]

                if error_code == "ThrottlingException":
                    if attempt == max_attempts - 1:
                        # Final attempt failed
                        logger.error(
                            f"Bedrock throttling persisted after {max_attempts} attempts"
                        )
                        raise RateLimitExceededError(
                            f"Bedrock API throttling after {max_attempts} retries. "
                            "Reduce request rate or increase capacity."
                        ) from e

                    # Calculate delay with exponential backoff and jitter
                    delay = min(base_delay * (2**attempt), max_delay)
                    jitter = random.uniform(0, 1.0)  # noqa: S311
                    total_delay = delay + jitter

                    logger.warning(
                        f"Bedrock throttling on attempt {attempt + 1}, "
                        f"retrying in {total_delay:.2f}s "
                        f"(base={delay:.1f}s, jitter={jitter:.2f}s)"
                    )
                    time.sleep(total_delay)
                    continue

                # Non-retryable errors
                if error_code == "ModelNotReadyException":
                    raise BedrockError(f"Model not ready: {model_id}") from e
                if error_code == "ValidationException":
                    raise BedrockError(f"Invalid request: {e}") from e
                if error_code == "ResourceNotFoundException":
                    raise BedrockError(f"Model not found: {model_id}") from e
                raise BedrockError(f"Bedrock API error ({error_code}): {e}") from e

        # This should not be reached due to the exception in the loop
        raise BedrockError("Unexpected retry loop exit")

    def _mock_invoke(self, prompt: str, agent: str, _max_tokens: int) -> dict[str, Any]:
        """
        Mock LLM invocation for testing without AWS.

        Returns mock response with realistic token counts.
        Note: max_tokens parameter reserved for future mock response length control
        """
        # Generate mock response based on agent type
        mock_responses = {
            "PlannerAgent": "I will analyze the security issue and break it down into actionable steps...",
            "CoderAgent": "def fix_vulnerability():\n    # Sanitize user input\n    clean_input = sanitize(user_input)\n    return clean_input",
            "ReviewerAgent": "Security Analysis:\n✓ Input sanitization implemented\n✓ No SQL injection vectors\n✗ Missing rate limiting",
            "ValidatorAgent": "Test Results:\nPassed: 8/10\nFailed: 2/10\nCoverage: 85%",
        }

        mock_text = mock_responses.get(
            agent, f"Mock response for {agent}: Processing request..."
        )

        # Estimate token counts (rough approximation: 1 token ≈ 4 characters)
        input_tokens = len(prompt) // 4
        output_tokens = len(mock_text) // 4

        logger.info(f"[MOCK] Generated response for {agent} ({output_tokens} tokens)")

        return {
            "text": mock_text,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "guardrail_result": None,  # No guardrails in mock mode
        }

    def invoke_model(
        self,
        prompt: str,
        agent: str,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        use_fallback: bool = False,
        cache_enabled: bool | None = None,
        operation: str | None = None,
        override_tier: ModelTier | None = None,
        apply_guardrails: bool = True,
    ) -> dict[str, Any]:
        """
        Invoke Claude model via Bedrock with full cost/rate control.

        Supports tiered model selection per ADR-015:
        - FAST (Haiku): Simple tasks like query intent, expansion
        - ACCURATE (Sonnet): Security analysis, patches, code review
        - MAXIMUM (Opus): Cross-codebase reasoning, novel threats

        Supports Bedrock Guardrails per ADR-029:
        - Content filtering (hate, violence, prompt attacks)
        - PII protection (SSN, credit cards, AWS credentials)
        - Topic blocking (malware, social engineering)

        Args:
            prompt: User prompt
            agent: Agent name (for cost tracking)
            system_prompt: System prompt (optional)
            max_tokens: Max output tokens (default from config)
            temperature: Temperature 0-1 (default from config)
            use_fallback: DEPRECATED - Use operation or override_tier instead
            cache_enabled: Enable response caching (default from config)
            operation: Operation name for automatic tier selection (ADR-015)
            override_tier: Force specific tier regardless of operation
            apply_guardrails: Apply Bedrock Guardrails (default True, ADR-029)

        Returns:
            {
                'response': str,           # Generated text
                'input_tokens': int,       # Input token count
                'output_tokens': int,      # Output token count
                'cost_usd': float,         # Cost in USD
                'model': str,              # Model ID used
                'tier': str,               # Model tier used (fast/accurate/maximum)
                'operation': str | None,   # Operation name if provided
                'cached': bool,            # Whether response was cached
                'request_id': str,         # Unique request ID
                'guardrail_result': GuardrailResult | None  # Guardrail outcome (ADR-029)
            }

        Raises:
            BudgetExceededError: If budget limit reached
            RateLimitExceededError: If rate limit reached
            BedrockError: For API errors
            GuardrailViolationError: If guardrail blocks content (ADR-029)
            PromptInjectionError: If prompt injection detected (OWASP LLM01)
        """
        request_id = str(uuid.uuid4())

        # Set defaults
        max_tokens = max_tokens or self.config["max_tokens_default"]
        temperature = (
            temperature
            if temperature is not None
            else self.config["temperature_default"]
        )
        cache_enabled = (
            cache_enabled
            if cache_enabled is not None
            else self.config.get("cache_enabled", True)
        )

        # 0. Prompt sanitization (OWASP LLM01: Prompt Injection prevention)
        sanitization_result: SanitizationResult | None = None
        if self.sanitize_prompts and self.prompt_sanitizer:
            sanitization_result = self.prompt_sanitizer.sanitize(
                prompt,
                context={
                    "agent": agent,
                    "operation": operation,
                    "request_id": request_id,
                },
            )

            if sanitization_result.action == SanitizationAction.BLOCKED:
                logger.warning(
                    f"Request {request_id[:8]} blocked by prompt sanitizer: "
                    f"threat_level={sanitization_result.threat_level.value}, "
                    f"patterns={sanitization_result.patterns_detected}"
                )
                raise PromptInjectionError(
                    f"Prompt blocked due to detected injection attempt: "
                    f"{sanitization_result.warnings}",
                    threat_level=sanitization_result.threat_level,
                    patterns_detected=sanitization_result.patterns_detected,
                )

            if sanitization_result.was_modified:
                logger.info(
                    f"Request {request_id[:8]} prompt sanitized: "
                    f"threat_level={sanitization_result.threat_level.value}, "
                    f"patterns={sanitization_result.patterns_detected}"
                )
                # Use sanitized prompt for the rest of the flow
                prompt = sanitization_result.sanitized_prompt

            # Also sanitize system prompt if provided
            if system_prompt:
                sys_result = self.prompt_sanitizer.sanitize_system_prompt(system_prompt)
                if sys_result.action == SanitizationAction.BLOCKED:
                    raise PromptInjectionError(
                        f"System prompt blocked: {sys_result.warnings}",
                        threat_level=sys_result.threat_level,
                        patterns_detected=sys_result.patterns_detected,
                    )
                if sys_result.was_modified:
                    system_prompt = sys_result.sanitized_prompt

        # Model selection (ADR-015 tiered strategy)
        if override_tier is not None:
            # Explicit tier override
            tier = override_tier
            model_id = self._tier_models()[tier]
        elif operation is not None:
            # Operation-based selection
            tier, model_id = get_model_for_operation(operation, self._tier_models())
        elif use_fallback:
            # Legacy fallback support (deprecated)
            tier = ModelTier.FAST
            model_id = self.model_id_fallback
        else:
            # Default to primary model (ACCURATE tier)
            tier = ModelTier.ACCURATE
            model_id = self.model_id_primary

        logger.debug(
            f"Model selection: operation={operation}, tier={tier.value}, model={model_id.split('.')[-1]}"
        )

        # 1. Check cache first (before rate limits)
        if cache_enabled:
            cache_key = self._cache_key(
                prompt,
                model_id,
                {
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "system": system_prompt,
                },
            )
            cached_response = self._get_cached_response(cache_key)
            if cached_response:
                return cached_response

        # 2. Budget check
        if not self._check_budget():
            raise BudgetExceededError(
                f"Budget exceeded. Daily: ${self.daily_spend:.2f}/${self.config['daily_budget_usd']:.2f}, "
                f"Monthly: ${self.monthly_spend:.2f}/${self.config['monthly_budget_usd']:.2f}"
            )

        # 3. Rate limit check
        if not self._check_rate_limit():
            raise RateLimitExceededError(
                "Rate limit exceeded. Please retry later or increase limits in config."
            )

        # 4. Record request (for rate limiting) using Redis
        self._record_request()

        # 5. Invoke model (real or mock)
        if self.mode == BedrockMode.AWS:
            api_response = self._invoke_bedrock_api(
                model_id,
                prompt,
                system_prompt,
                max_tokens,
                temperature,
                apply_guardrails=apply_guardrails,
            )
        else:
            api_response = self._mock_invoke(prompt, agent, max_tokens)

        # 6. Calculate cost
        cost = calculate_cost(
            api_response["input_tokens"], api_response["output_tokens"], model_id
        )

        # 7. Record cost with tier tracking (ADR-015)
        self._record_cost(
            request_id,
            agent,
            model_id,
            api_response["input_tokens"],
            api_response["output_tokens"],
            cost,
            tier=tier,
            operation=operation,
        )

        # 8. Build result
        result = {
            "response": api_response["text"],
            "input_tokens": api_response["input_tokens"],
            "output_tokens": api_response["output_tokens"],
            "cost_usd": cost,
            "model": model_id,
            "tier": tier.value,
            "operation": operation,
            "cached": False,
            "request_id": request_id,
            "guardrail_result": api_response.get("guardrail_result"),  # ADR-029
            "sanitization_result": sanitization_result,  # OWASP LLM01
        }

        # 9. Cache response in both Redis (distributed) and memory (fast local access)
        if cache_enabled:
            cache_ttl = self.config.get("cache_ttl_seconds", 86400)

            # Store in Redis for distributed caching
            self._redis_cache.set_response(cache_key, result, ttl=cache_ttl)

            # Also store in local OrderedDict for fast repeated access
            self.response_cache[cache_key] = {
                "response": result,
                "timestamp": time.time(),
            }
            # Move to end to mark as most recently used (O(1) operation)
            self.response_cache.move_to_end(cache_key)

            # LRU eviction using OrderedDict.popitem(last=False) - O(1) operation
            # Much more efficient than the previous O(n log n) sort-based approach
            while len(self.response_cache) > self.MAX_RESPONSE_CACHE_SIZE:
                evicted_key, _ = self.response_cache.popitem(last=False)
                logger.debug(f"LRU evicted response cache entry: {evicted_key[:16]}...")

        logger.info(
            f"Request {request_id[:8]} completed for {agent}. "
            f"Tier: {tier.value}, Operation: {operation or 'default'}, "
            f"Tokens: {api_response['input_tokens']}+{api_response['output_tokens']}, "
            f"Cost: ${cost:.6f}"
        )

        return result

    def get_spend_summary(self) -> dict[str, Any]:
        """
        Get current spending summary.

        Returns:
            {
                'daily_spend': float,
                'daily_budget': float,
                'daily_remaining': float,
                'daily_percent': float,
                'monthly_spend': float,
                'monthly_budget': float,
                'monthly_remaining': float,
                'monthly_percent': float,
                'total_requests': int
            }
        """
        daily_budget = self.config["daily_budget_usd"]
        monthly_budget = self.config["monthly_budget_usd"]

        return {
            "daily_spend": self.daily_spend,
            "daily_budget": daily_budget,
            "daily_remaining": max(0, daily_budget - self.daily_spend),
            "daily_percent": (
                (self.daily_spend / daily_budget) * 100 if daily_budget > 0 else 0
            ),
            "monthly_spend": self.monthly_spend,
            "monthly_budget": monthly_budget,
            "monthly_remaining": max(0, monthly_budget - self.monthly_spend),
            "monthly_percent": (
                (self.monthly_spend / monthly_budget) * 100 if monthly_budget > 0 else 0
            ),
            "total_requests": len(self.request_history),
        }

    # ------------------------------------------------------------------
    # Tool use and structured output (Claude Messages API ``tools``)
    # ------------------------------------------------------------------

    def _select_model(
        self, operation: str | None, override_tier: ModelTier | None
    ) -> tuple[ModelTier, str]:
        if override_tier is not None:
            return override_tier, self._tier_models()[override_tier]
        if operation is not None:
            return get_model_for_operation(operation, self._tier_models())
        return ModelTier.ACCURATE, self.model_id_primary

    def _sanitize_text(self, text: str, agent: str, operation: str | None) -> str:
        """Prompt-injection screening (OWASP LLM01) for text the agent sends."""
        if not (self.sanitize_prompts and self.prompt_sanitizer):
            return text
        result = self.prompt_sanitizer.sanitize(
            text, context={"agent": agent, "operation": operation}
        )
        if result.action == SanitizationAction.BLOCKED:
            raise PromptInjectionError(
                f"Prompt blocked: {result.warnings}",
                threat_level=result.threat_level,
                patterns_detected=result.patterns_detected,
            )
        return result.sanitized_prompt if result.was_modified else text

    def invoke_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        agent: str = "unknown",
        system_prompt: str | None = None,
        tool_choice: dict[str, Any] | None = None,
        operation: str | None = None,
        override_tier: ModelTier | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        apply_guardrails: bool = True,
    ) -> dict[str, Any]:
        """
        One Messages API turn with tools: the same budget, rate-limit, guardrail and
        cost controls as ``invoke_model``, without response caching (tool turns depend on
        the whole conversation).

        Text the agent writes (string message content and text blocks in user turns) is
        screened for prompt injection. Tool results are passed through unchanged: they
        are data the agent's own tools returned.

        Returns:
            {"content": [blocks], "stop_reason": str, "input_tokens", "output_tokens",
             "cost_usd", "model", "tier", "request_id", "guardrail_result"}
        """
        request_id = str(uuid.uuid4())
        max_tokens = max_tokens or self.config["max_tokens_default"]
        temperature = (
            temperature
            if temperature is not None
            else self.config["temperature_default"]
        )

        screened: list[dict[str, Any]] = []
        for message in messages:
            content = message.get("content")
            if message.get("role") == "user" and isinstance(content, str):
                content = self._sanitize_text(content, agent, operation)
            elif message.get("role") == "user" and isinstance(content, list):
                content = [
                    (
                        {**b, "text": self._sanitize_text(b["text"], agent, operation)}
                        if isinstance(b, dict) and b.get("type") == "text"
                        else b
                    )
                    for b in content
                ]
            screened.append({**message, "content": content})
        if system_prompt and self.sanitize_prompts and self.prompt_sanitizer:
            sys_result = self.prompt_sanitizer.sanitize_system_prompt(system_prompt)
            if sys_result.action == SanitizationAction.BLOCKED:
                raise PromptInjectionError(
                    f"System prompt blocked: {sys_result.warnings}",
                    threat_level=sys_result.threat_level,
                    patterns_detected=sys_result.patterns_detected,
                )
            if sys_result.was_modified:
                system_prompt = sys_result.sanitized_prompt

        tier, model_id = self._select_model(operation, override_tier)

        if not self._check_budget():
            raise BudgetExceededError(
                f"Budget exceeded. Daily: ${self.daily_spend:.2f}/"
                f"${self.config['daily_budget_usd']:.2f}, "
                f"Monthly: ${self.monthly_spend:.2f}/"
                f"${self.config['monthly_budget_usd']:.2f}"
            )
        if not self._check_rate_limit():
            raise RateLimitExceededError(
                "Rate limit exceeded. Please retry later or increase limits in config."
            )
        self._record_request()

        guardrail_result = None
        if self.mode == BedrockMode.AWS:
            request_body: dict[str, Any] = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": screened,
                "tools": tools,
            }
            if system_prompt:
                request_body["system"] = system_prompt
            if tool_choice:
                request_body["tool_choice"] = tool_choice
            body, guardrail_result = self._send(
                model_id, request_body, apply_guardrails, cacheable=True
            )
            content = body.get("content", [])
            stop_reason = body.get("stop_reason", "end_turn")
            usage = body["usage"]
            input_tokens = usage["input_tokens"]
            output_tokens = usage["output_tokens"]
            cache_write_tokens = usage.get("cache_creation_input_tokens") or 0
            cache_read_tokens = usage.get("cache_read_input_tokens") or 0
        else:
            content, stop_reason = self._mock_tool_turn(tools, tool_choice, agent)
            input_tokens = len(json.dumps(screened)) // 4
            output_tokens = len(json.dumps(content)) // 4
            cache_write_tokens = cache_read_tokens = 0

        cost = calculate_cost(
            input_tokens,
            output_tokens,
            model_id,
            cache_write_tokens=cache_write_tokens,
            cache_read_tokens=cache_read_tokens,
        )
        self._record_cost(
            request_id,
            agent,
            model_id,
            input_tokens,
            output_tokens,
            cost,
            tier=tier,
            operation=operation,
        )
        return {
            "content": content,
            "stop_reason": stop_reason,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_write_tokens": cache_write_tokens,
            "cache_read_tokens": cache_read_tokens,
            "cost_usd": cost,
            "model": model_id,
            "tier": tier.value,
            "request_id": request_id,
            "guardrail_result": guardrail_result,
        }

    def _caches_prompts(self, model_id: str) -> bool:
        return (
            self.config.get("prompt_caching_enabled", True) is not False
            and model_id in getattr(self, "prompt_cache_models", ())
            and model_id not in getattr(self, "_cache_rejected", ())
        )

    @staticmethod
    def _with_cache_breakpoints(request_body: dict[str, Any]) -> dict[str, Any]:
        """
        A copy of the request with prompt-cache breakpoints: one on the last tool
        (caching tools and system, which render first) and one on the last block of the
        latest turn (caching the conversation so far). Each tool-loop turn then reads the
        earlier turns from cache instead of paying for them again.
        """
        marker = {"type": "ephemeral"}
        body = dict(request_body)
        if body.get("tools"):
            tools = [dict(t) for t in body["tools"]]
            tools[-1]["cache_control"] = marker
            body["tools"] = tools
        messages = [dict(m) for m in body.get("messages") or []]
        if messages:
            last = messages[-1]
            content = last.get("content")
            if isinstance(content, str):
                content = [{"type": "text", "text": content}]
            if isinstance(content, list) and content:
                content = [dict(b) for b in content]
                content[-1]["cache_control"] = marker
                last["content"] = content
            body["messages"] = messages
        return body

    def _send(
        self,
        model_id: str,
        request_body: dict[str, Any],
        apply_guardrails: bool = True,
        cacheable: bool = False,
    ) -> tuple[dict[str, Any], "GuardrailResult | None"]:
        """
        Send a Messages API request in the shape this model accepts.

        Applies the model's known request rules (model_request_rules) and any it taught
        us earlier, adds prompt-cache breakpoints to cacheable (tool-use) requests for
        models that take them, and if Bedrock rejects a field (a 400 naming temperature,
        tool_choice, or cache_control), retries without it and remembers that for the
        model.
        """
        learned = getattr(self, "_learned_quirks", None)
        if learned is None:
            learned = self._learned_quirks = {}
        rules = model_request_rules(model_id) | learned.get(model_id, set())
        while True:
            body = _adapt_request(request_body, rules)
            if cacheable and "no_cache" not in rules and self._caches_prompts(model_id):
                body = self._with_cache_breakpoints(body)
            try:
                return self._invoke_bedrock_messages(model_id, body, apply_guardrails)
            except BedrockError as e:
                rule = _rejected_field(str(e))
                if rule is None or rule in rules:
                    raise
                logger.warning(
                    "Bedrock rejected a request field for %s (%s); retrying with %s",
                    model_id,
                    e,
                    rule,
                )
                learned.setdefault(model_id, set()).add(rule)
                rules.add(rule)
                if rule == "no_cache":
                    self._cache_rejected.add(model_id)

    @staticmethod
    def _mock_tool_turn(
        tools: list[dict[str, Any]], tool_choice: dict[str, Any] | None, agent: str
    ) -> tuple[list[dict[str, Any]], str]:
        """Mock mode: call the forced tool with empty input, otherwise answer in text."""
        if tool_choice and tool_choice.get("type") == "tool":
            block = {
                "type": "tool_use",
                "id": f"toolu_mock_{uuid.uuid4().hex[:12]}",
                "name": tool_choice["name"],
                "input": {},
            }
            return [block], "tool_use"
        return [{"type": "text", "text": f"Mock response for {agent}"}], "end_turn"

    async def generate_with_tools(self, messages, tools, **kwargs) -> dict[str, Any]:
        """Async ``invoke_with_tools`` (runs the blocking Bedrock call in a thread)."""
        return await asyncio.to_thread(
            self.invoke_with_tools, messages, tools, **kwargs
        )

    async def generate_structured(
        self,
        prompt: str,
        tool_name: str,
        input_schema: dict[str, Any],
        description: str,
        agent: str = "unknown",
        system_prompt: str | None = None,
        operation: str | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """
        Ask for output in a fixed shape by forcing one tool call, and return its input.

        Replaces "reply in JSON" prompts: the response is the tool's arguments, so there
        is no text to parse. The input is checked against the schema's required fields,
        types, and enums.

        Raises:
            StructuredOutputError: the model did not call the tool, or the input does
                not match the schema.
        """
        # Models that reject a forced tool_choice get "auto" (see model_request_rules), so
        # the instruction to answer through the tool is in the prompt as well
        instruction = f"\n\nRespond by calling the {tool_name} tool."
        result = await self.generate_with_tools(
            [{"role": "user", "content": prompt + instruction}],
            [
                {
                    "name": tool_name,
                    "description": description,
                    "input_schema": input_schema,
                }
            ],
            agent=agent,
            system_prompt=system_prompt,
            tool_choice={"type": "tool", "name": tool_name},
            operation=operation,
            max_tokens=max_tokens,
        )
        for block in result["content"]:
            if block.get("type") == "tool_use" and block.get("name") == tool_name:
                data = block.get("input") or {}
                problems = schema_problems(data, input_schema)
                if problems:
                    raise StructuredOutputError(
                        f"{tool_name} output does not match its schema: "
                        + "; ".join(problems)
                    )
                return data
        raise StructuredOutputError(f"The model did not call {tool_name}")

    async def generate(
        self,
        prompt: str,
        agent: str = "QueryPlanningAgent",
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        operation: str | None = None,
        use_semantic_cache: bool = True,
    ) -> str:
        """
        Async interface for agent compatibility with semantic caching (ADR-029).

        Simple wrapper around invoke_model that returns just the response text.
        Used by QueryPlanningAgent and other agents expecting async LLM interface.

        Supports:
        - Tiered model selection per ADR-015 via operation parameter
        - Semantic caching per ADR-029 Phase 1.3 for 60-70% cost reduction
        - Prompt sanitization per OWASP LLM01 prevention

        Args:
            prompt: User prompt
            agent: Agent name for cost tracking (default: QueryPlanningAgent)
            system_prompt: System prompt (optional)
            max_tokens: Max output tokens (optional)
            operation: Operation name for automatic tier selection (ADR-015)
            use_semantic_cache: Whether to use semantic cache (default True)

        Returns:
            Generated text response (string only)

        Raises:
            PromptInjectionError: If prompt injection detected (OWASP LLM01)
        """
        # Note: asyncio is imported at module level for Python 3.10+ compatibility

        # Sanitize prompt before any processing (OWASP LLM01)
        # This ensures malicious prompts don't retrieve cached responses
        if self.sanitize_prompts and self.prompt_sanitizer:
            sanitization_result = self.prompt_sanitizer.sanitize(
                prompt,
                context={"agent": agent, "operation": operation},
            )

            if sanitization_result.action == SanitizationAction.BLOCKED:
                logger.warning(
                    f"Prompt blocked by sanitizer in generate(): "
                    f"threat_level={sanitization_result.threat_level.value}"
                )
                raise PromptInjectionError(
                    f"Prompt blocked: {sanitization_result.warnings}",
                    threat_level=sanitization_result.threat_level,
                    patterns_detected=sanitization_result.patterns_detected,
                )

            if sanitization_result.was_modified:
                prompt = sanitization_result.sanitized_prompt

            # Also sanitize system prompt if provided
            if system_prompt:
                sys_result = self.prompt_sanitizer.sanitize_system_prompt(system_prompt)
                if sys_result.action == SanitizationAction.BLOCKED:
                    raise PromptInjectionError(
                        f"System prompt blocked: {sys_result.warnings}",
                        threat_level=sys_result.threat_level,
                        patterns_detected=sys_result.patterns_detected,
                    )
                if sys_result.was_modified:
                    system_prompt = sys_result.sanitized_prompt

        # Get model ID for semantic cache context
        _, model_id = get_model_for_operation(operation, self._tier_models())

        # Check semantic cache first (ADR-029 Phase 1.3)
        if use_semantic_cache and self.semantic_cache:
            try:
                # Import QueryType lazily to avoid circular imports
                from src.services.semantic_cache_service import QueryType

                # Map operation to QueryType
                query_type_str = OPERATION_QUERY_TYPE_MAP.get(
                    operation or "", "general"
                )
                try:
                    query_type = QueryType(query_type_str)
                except ValueError:
                    query_type = QueryType.GENERAL

                # Check cache
                cache_result = await self.semantic_cache.get_cached_response(
                    query=prompt,
                    model_id=model_id,
                    query_type=query_type,
                    agent_name=agent,
                )

                if cache_result.hit and cache_result.response:
                    logger.info(
                        f"Semantic cache hit for {agent}: "
                        f"score={cache_result.similarity_score:.4f}, "
                        f"saved=${cache_result.cost_saved_usd:.4f}"
                    )
                    return cache_result.response

            except Exception as e:
                logger.warning(f"Semantic cache lookup failed, proceeding to LLM: {e}")

        # Run synchronous invoke_model in executor using asyncio.to_thread()
        # This is the Python 3.9+ recommended replacement for get_event_loop().run_in_executor()
        # and works correctly when called from an already-running event loop
        result = await asyncio.to_thread(
            self.invoke_model,
            prompt=prompt,
            agent=agent,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            operation=operation,
        )

        response: str = str(result["response"])

        # Cache successful response (ADR-029 Phase 1.3)
        if use_semantic_cache and self.semantic_cache and response:
            try:
                from src.services.semantic_cache_service import QueryType

                query_type_str = OPERATION_QUERY_TYPE_MAP.get(
                    operation or "", "general"
                )
                try:
                    query_type = QueryType(query_type_str)
                except ValueError:
                    query_type = QueryType.GENERAL

                await self.semantic_cache.cache_response(
                    query=prompt,
                    response=response,
                    model_id=model_id,
                    model_version=result.get("tier", "unknown"),
                    query_type=query_type,
                    agent_name=agent,
                    metadata={
                        "operation": operation,
                        "input_tokens": result.get("input_tokens"),
                        "output_tokens": result.get("output_tokens"),
                        "request_id": result.get("request_id"),
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to cache response: {e}")

        return response

    def get_semantic_cache_stats(self) -> dict[str, Any] | None:
        """
        Get semantic cache statistics if enabled.

        Returns:
            Cache stats dict or None if semantic cache not enabled
        """
        if not self.semantic_cache:
            return None
        return self.semantic_cache.get_stats().to_dict()

    async def invoke_model_async(
        self,
        prompt: str,
        agent: str,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        operation: str | None = None,
        override_tier: ModelTier | None = None,
        apply_guardrails: bool = True,
        cache_enabled: bool | None = None,
    ) -> dict[str, Any]:
        """
        Async version of invoke_model for parallel processing.

        Wraps the blocking invoke_model call with asyncio.to_thread()
        to enable concurrent LLM requests without blocking the event loop.

        Args:
            prompt: User prompt
            agent: Agent name (for cost tracking)
            system_prompt: System prompt (optional)
            max_tokens: Max output tokens (default from config)
            temperature: Temperature 0-1 (default from config)
            operation: Operation name for automatic tier selection (ADR-015)
            override_tier: Force specific tier regardless of operation
            apply_guardrails: Apply Bedrock Guardrails (default True, ADR-029)
            cache_enabled: Enable response caching (default from config)

        Returns:
            Same as invoke_model - dict with response, tokens, cost, etc.
        """
        # asyncio is imported at module level
        return await asyncio.to_thread(
            self.invoke_model,
            prompt=prompt,
            agent=agent,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            operation=operation,
            override_tier=override_tier,
            apply_guardrails=apply_guardrails,
            cache_enabled=cache_enabled,
        )

    async def invoke_batch_async(
        self,
        requests: list[dict[str, Any]],
        max_concurrent: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Batch invoke multiple LLM requests with parallel processing.

        Uses asyncio.gather() with semaphore-based concurrency control
        for efficient parallel LLM invocations. Significantly faster
        than sequential invocations for multi-prompt workflows.

        Performance improvement: ~3-5x faster than sequential for I/O-bound
        Bedrock API calls (5 concurrent requests vs 1 sequential).

        Args:
            requests: List of request dicts, each containing:
                - prompt (required): User prompt
                - agent (required): Agent name for cost tracking
                - system_prompt (optional): System prompt
                - max_tokens (optional): Max output tokens
                - temperature (optional): Temperature 0-1
                - operation (optional): Operation name for tier selection
                - override_tier (optional): Force specific tier
                - apply_guardrails (optional): Apply guardrails (default True)
            max_concurrent: Maximum concurrent requests (default 5).
                Lower values reduce Bedrock API throttling risk.

        Returns:
            List of response dicts (same order as input requests).
            Failed requests return error dict with 'error' key.

        Example:
            >>> service = BedrockLLMService()
            >>> requests = [
            ...     {"prompt": "Analyze vulnerability A", "agent": "security"},
            ...     {"prompt": "Analyze vulnerability B", "agent": "security"},
            ...     {"prompt": "Analyze vulnerability C", "agent": "security"},
            ... ]
            >>> results = await service.invoke_batch_async(requests, max_concurrent=3)
        """
        # asyncio is imported at module level
        if not requests:
            return []

        semaphore = asyncio.Semaphore(max_concurrent)
        results: list[dict[str, Any]] = [{} for _ in requests]

        async def invoke_with_limit(index: int, request: dict[str, Any]) -> None:
            """Invoke single request with semaphore rate limiting."""
            async with semaphore:
                try:
                    result = await self.invoke_model_async(
                        prompt=request["prompt"],
                        agent=request["agent"],
                        system_prompt=request.get("system_prompt"),
                        max_tokens=request.get("max_tokens"),
                        temperature=request.get("temperature"),
                        operation=request.get("operation"),
                        override_tier=request.get("override_tier"),
                        apply_guardrails=request.get("apply_guardrails", True),
                        cache_enabled=request.get("cache_enabled"),
                    )
                    results[index] = result
                except Exception as e:
                    logger.error(f"Batch request {index} failed: {e}")
                    results[index] = {
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "request_index": index,
                    }

        logger.info(
            f"Starting batch LLM invocation: {len(requests)} requests, "
            f"max_concurrent={max_concurrent}"
        )

        # Create tasks for all requests
        tasks = [invoke_with_limit(i, req) for i, req in enumerate(requests)]

        # Execute all tasks concurrently (limited by semaphore)
        await asyncio.gather(*tasks)

        # Count successes and failures
        successes = sum(1 for r in results if "error" not in r)
        failures = len(results) - successes

        logger.info(
            f"Completed batch LLM invocation: {successes} succeeded, {failures} failed"
        )

        return results


# Convenience function for quick access
def create_llm_service(
    environment: str | None = None,
    enable_semantic_cache: bool = False,
    sanitize_prompts: bool = True,
    sanitizer_strict_mode: bool = False,
) -> BedrockLLMService:
    """
    Create and return a BedrockLLMService instance.

    Args:
        environment: Environment name ('development', 'staging', 'production')
        enable_semantic_cache: Enable semantic caching (ADR-029 Phase 1.3)
        sanitize_prompts: Enable prompt sanitization (default True, OWASP LLM01)
        sanitizer_strict_mode: Block suspicious prompts rather than sanitize

    Returns:
        Configured BedrockLLMService instance
    """
    # Auto-detect mode based on AWS availability
    mode = BedrockMode.AWS if AWS_AVAILABLE else BedrockMode.MOCK

    # Create semantic cache if enabled
    semantic_cache = None
    if enable_semantic_cache:
        try:
            from src.services.semantic_cache_service import (
                CacheMode,
                create_semantic_cache_service,
            )

            semantic_cache = create_semantic_cache_service(mode=CacheMode.READ_WRITE)
            logger.info("Semantic cache enabled for LLM service")
        except Exception as e:
            logger.warning(f"Failed to create semantic cache: {e}")

    return BedrockLLMService(
        mode=mode,
        environment=environment,
        semantic_cache=semantic_cache,
        sanitize_prompts=sanitize_prompts,
        sanitizer_strict_mode=sanitizer_strict_mode,
    )


def create_secure_llm_service(
    environment: str | None = None,
    enable_semantic_cache: bool = False,
) -> BedrockLLMService:
    """
    Create a security-hardened BedrockLLMService for high-risk operations.

    This factory function returns an LLM service configured with strict mode
    prompt sanitization. Use this for security-critical operations such as:
    - Patch generation
    - Code execution approval
    - Agent instructions
    - Any operation that modifies code or system configuration

    The strict mode will BLOCK (not just sanitize) prompts that appear to
    contain prompt injection attacks, preventing them from reaching the LLM.

    Args:
        environment: Environment name ('development', 'staging', 'production')
        enable_semantic_cache: Enable semantic caching (ADR-029 Phase 1.3)

    Returns:
        Security-hardened BedrockLLMService with strict prompt sanitization

    Example:
        >>> from src.services.bedrock_llm_service import create_secure_llm_service
        >>> llm = create_secure_llm_service()
        >>> # This will block suspicious prompts rather than sanitize them
        >>> response = llm.invoke_model(prompt="Generate patch...", agent="security")

    See Also:
        - OWASP LLM01: Prompt Injection
        - ADR-024: Security Requirements
    """
    return create_llm_service(
        environment=environment,
        enable_semantic_cache=enable_semantic_cache,
        sanitize_prompts=True,
        sanitizer_strict_mode=True,  # Block suspicious prompts
    )


if __name__ == "__main__":
    # Demo/test usage
    logging.basicConfig(level=logging.INFO)

    print("Project Aura - Bedrock LLM Service Demo")
    print("=" * 60)

    # Create service (will use mock mode if AWS not configured)
    service = create_llm_service()

    print(f"\nMode: {service.mode.value}")
    print(f"Environment: {service.environment}")
    print(f"Primary Model: {service.model_id_primary}")
    print(f"Daily Budget: ${service.config['daily_budget_usd']:.2f}")

    # Test invocation
    print("\n" + "-" * 60)
    print("Testing model invocation...")

    try:
        result = service.invoke_model(
            prompt="Explain how to prevent SQL injection vulnerabilities in Python.",
            agent="TestAgent",
            system_prompt="You are a security expert.",
            max_tokens=200,
        )

        print("\n✓ Success!")
        print(f"Response: {result['response'][:100]}...")
        print(f"Input Tokens: {result['input_tokens']}")
        print(f"Output Tokens: {result['output_tokens']}")
        print(f"Cost: ${result['cost_usd']:.6f}")
        print(f"Model: {result['model'].split('.')[-1]}")

    except Exception as e:
        print(f"\n✗ Error: {e}")

    # Show spend summary
    print("\n" + "-" * 60)
    summary = service.get_spend_summary()
    print("Spend Summary:")
    print(
        f"  Daily: ${summary['daily_spend']:.2f} / ${summary['daily_budget']:.2f} ({summary['daily_percent']:.1f}%)"
    )
    print(
        f"  Monthly: ${summary['monthly_spend']:.2f} / ${summary['monthly_budget']:.2f} ({summary['monthly_percent']:.1f}%)"
    )
    print(f"  Total Requests: {summary['total_requests']}")

    print("\n" + "=" * 60)
    print("Demo complete!")
