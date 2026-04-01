"""
Multi-Provider Model Router for Diagram Generation (ADR-060 Phase 2).

Routes diagram generation tasks to optimal AI providers based on:
1. Task requirements (vision, generation, reasoning)
2. Data classification (CUI/FedRAMP compliance enforcement)
3. Provider availability (circuit breakers, health checks)
4. Cost optimization (cheapest capable provider)
5. GovCloud compliance (Bedrock-only for regulated workloads)

Security:
- API keys stored in SSM Parameter Store (SecureString)
- No credentials in code or environment variables
- Data classification enforcement for FedRAMP/CMMC
- Prompt injection prevention via InputSanitizer (ADR-051)
"""

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional, Protocol

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


class ModelProvider(Enum):
    """Supported AI model providers."""

    BEDROCK = "bedrock"  # AWS Bedrock (Claude) - primary, GovCloud compatible
    OPENAI = "openai"  # OpenAI API (GPT-4V, DALL-E 3)
    VERTEX = "vertex"  # Google Vertex AI (Gemini Pro Vision)


class DiagramTask(Enum):
    """Diagram generation subtasks with optimal model mapping."""

    DSL_GENERATION = "dsl_generation"
    INTENT_EXTRACTION = "intent_extraction"
    DIAGRAM_CRITIQUE = "diagram_critique"
    IMAGE_UNDERSTANDING = "image_understanding"
    CREATIVE_GENERATION = "creative_generation"
    LAYOUT_OPTIMIZATION = "layout_optimization"  # No LLM needed


class DataClassification(Enum):
    """Data sensitivity classification for compliance enforcement."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    CUI = "cui"  # Controlled Unclassified Information - FedRAMP/CMMC
    RESTRICTED = "restricted"


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


# Task-to-Provider mapping - Bedrock as single gateway (ADR-060)
# All models accessed through Bedrock for unified billing, IAM auth, and FedRAMP compliance
# Model IDs use inference profile format (us. prefix) for on-demand invocation
DIAGRAM_TASK_ROUTING: dict[DiagramTask, list[tuple[ModelProvider, str]]] = {
    DiagramTask.DSL_GENERATION: [
        # Haiku for cost-effective DSL generation
        (ModelProvider.BEDROCK, "us.anthropic.claude-3-5-haiku-20241022-v1:0"),
    ],
    DiagramTask.INTENT_EXTRACTION: [
        # Haiku for fast intent extraction
        (ModelProvider.BEDROCK, "us.anthropic.claude-3-5-haiku-20241022-v1:0"),
    ],
    DiagramTask.DIAGRAM_CRITIQUE: [
        # Sonnet for higher quality critique (better reasoning)
        (ModelProvider.BEDROCK, "us.anthropic.claude-3-5-sonnet-20241022-v2:0"),
        # Haiku as fallback
        (ModelProvider.BEDROCK, "us.anthropic.claude-3-5-haiku-20241022-v1:0"),
    ],
    DiagramTask.IMAGE_UNDERSTANDING: [
        # Sonnet has strong vision capabilities
        (ModelProvider.BEDROCK, "us.anthropic.claude-3-5-sonnet-20241022-v2:0"),
        # Haiku as cost-effective fallback for vision
        (ModelProvider.BEDROCK, "us.anthropic.claude-3-5-haiku-20241022-v1:0"),
    ],
    DiagramTask.CREATIVE_GENERATION: [
        # Not supported through Bedrock - layout engine generates SVG instead
        # Future: Could integrate with Titan Image Generator when available
    ],
    DiagramTask.LAYOUT_OPTIMIZATION: [],  # No LLM needed - uses layout engine
}

# GovCloud Bedrock model availability (verified 2026-01)
# Note: All environments use inference profile IDs (us. prefix) for cross-region access
GOVCLOUD_BEDROCK_MODELS = {
    "us.anthropic.claude-3-5-sonnet-20241022-v2:0": True,
    "us.anthropic.claude-3-5-haiku-20241022-v1:0": True,
    "us.anthropic.claude-3-opus-20240229-v1:0": True,
}


@dataclass
class CircuitBreakerState:
    """Circuit breaker state for a provider."""

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure: Optional[datetime] = None
    last_success: Optional[datetime] = None

    # Configuration
    failure_threshold: int = 5
    recovery_timeout: timedelta = field(default_factory=lambda: timedelta(minutes=5))
    half_open_max_calls: int = 3
    _half_open_calls: int = 0

    def record_failure(self) -> None:
        """Record a failure and potentially open the circuit."""
        self.failure_count += 1
        self.last_failure = datetime.utcnow()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures"
            )

    def record_success(self) -> None:
        """Record success and reset circuit to closed."""
        self.failure_count = 0
        self.last_success = datetime.utcnow()
        if self.state == CircuitState.HALF_OPEN:
            logger.info("Circuit breaker closed after successful half-open test")
        self.state = CircuitState.CLOSED
        self._half_open_calls = 0

    def should_allow_request(self) -> bool:
        """Check if a request should be allowed through."""
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if (
                self.last_failure
                and datetime.utcnow() - self.last_failure > self.recovery_timeout
            ):
                self.state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                logger.info("Circuit breaker transitioning to half-open")
                return True
            return False
        # HALF_OPEN: allow limited requests
        if self._half_open_calls < self.half_open_max_calls:
            self._half_open_calls += 1
            return True
        return False


@dataclass
class ProviderConfig:
    """Configuration for an AI provider."""

    provider: ModelProvider
    api_key_ssm_path: Optional[str]
    endpoint: str
    enabled: bool = True
    govcloud_compatible: bool = False
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0


@dataclass
class ProviderCostTracker:
    """Track costs per provider for budget enforcement."""

    provider: ModelProvider
    daily_budget_usd: float = 100.0
    monthly_budget_usd: float = 2000.0
    current_daily_spend: float = 0.0
    current_monthly_spend: float = 0.0
    last_reset_date: Optional[datetime] = None

    def check_budget(self) -> bool:
        """Check if budget allows more requests."""
        self._maybe_reset_daily()
        return self.current_daily_spend < self.daily_budget_usd

    def _maybe_reset_daily(self) -> None:
        """Reset daily spend if it's a new day."""
        now = datetime.utcnow()
        if self.last_reset_date is None or self.last_reset_date.date() < now.date():
            self.current_daily_spend = 0.0
            self.last_reset_date = now
            # Reset monthly on first of month
            if now.day == 1:
                self.current_monthly_spend = 0.0


@dataclass
class RoutingDecision:
    """Result of a routing decision."""

    provider: ModelProvider
    model_id: str
    task: DiagramTask
    classification: DataClassification
    govcloud_mode: bool
    timestamp: datetime = field(default_factory=datetime.utcnow)


class TransientProviderError(Exception):
    """Retriable provider error (rate limit, timeout)."""


class NoAvailableProviderError(Exception):
    """Raised when no provider is available for a task."""


class DataClassificationError(Exception):
    """Raised when data classification prevents provider usage."""


class SecurityError(Exception):
    """Raised for security-related failures."""


class ProviderClient(Protocol):
    """Protocol for provider clients."""

    async def invoke(
        self, model_id: str, messages: list[dict], **kwargs: Any
    ) -> dict[str, Any]:
        """Invoke the model with messages."""
        ...


class DiagramModelRouter:
    """
    Multi-provider model router for diagram generation tasks.

    Extends ADR-015 tiered routing with provider selection based on:
    1. Task requirements (vision, generation, reasoning)
    2. Data classification (CUI enforcement)
    3. Provider availability (API health, rate limits)
    4. Cost optimization (cheapest capable provider)
    5. GovCloud compliance (Bedrock-only for regulated workloads)
    """

    GOVCLOUD_REGIONS = {"us-gov-west-1", "us-gov-east-1"}

    # Prompt injection detection patterns
    INJECTION_PATTERNS = [
        r"ignore (previous|all|above) instructions",
        r"system:\s*",
        r"<\|im_start\|>",
        r"### (System|Human|Assistant)",
        r"STOP\.?\s*NEW INSTRUCTION",
        r"you are now",
        r"pretend you are",
        r"act as if",
    ]

    def __init__(
        self,
        ssm_client: Any = None,
        cloudwatch_client: Any = None,
        environment: str = "dev",
        govcloud_mode: Optional[bool] = None,
    ):
        """
        Initialize the diagram model router.

        Args:
            ssm_client: AWS SSM client for parameter retrieval
            cloudwatch_client: AWS CloudWatch client for metrics
            environment: Deployment environment (dev/qa/prod)
            govcloud_mode: Force GovCloud mode (auto-detected if None)
        """
        self.ssm = ssm_client
        self.cloudwatch = cloudwatch_client
        self.environment = environment
        self.govcloud_mode = (
            govcloud_mode if govcloud_mode is not None else self._detect_govcloud()
        )

        # Provider configurations
        self._providers: dict[ModelProvider, ProviderConfig] = {}
        self._load_provider_configs()

        # Circuit breakers for provider health
        self._circuit_breakers: dict[ModelProvider, CircuitBreakerState] = {
            provider: CircuitBreakerState() for provider in ModelProvider
        }

        # Cost tracking
        self._cost_trackers: dict[ModelProvider, ProviderCostTracker] = {
            provider: ProviderCostTracker(provider=provider)
            for provider in ModelProvider
        }

        # Provider clients (lazy loaded)
        self._clients: dict[ModelProvider, ProviderClient] = {}

        # Routing decisions log for analytics
        self._routing_decisions: list[RoutingDecision] = []

        logger.info(
            f"DiagramModelRouter initialized: env={environment}, "
            f"govcloud={self.govcloud_mode}"
        )

    def _detect_govcloud(self) -> bool:
        """Auto-detect GovCloud based on region."""
        region = os.environ.get("AWS_REGION", "us-east-1")
        return region in self.GOVCLOUD_REGIONS

    def _get_bedrock_region(self) -> str:
        """Get appropriate Bedrock region based on partition."""
        region = os.environ.get("AWS_REGION", "us-east-1")
        if region.startswith("us-gov-"):
            return "us-gov-west-1"  # Bedrock available here
        return region

    def _get_bedrock_endpoint(self) -> str:
        """Get Bedrock endpoint for current region/partition."""
        region = self._get_bedrock_region()
        if region.startswith("us-gov-"):
            return f"bedrock-runtime.{region}.amazonaws-us-gov.com"
        return f"bedrock-runtime.{region}.amazonaws.com"

    def _ssm_path(self, provider: str, key: str) -> str:
        """Construct consistent SSM parameter path."""
        return f"/aura/{self.environment}/providers/{provider}/{key}"

    async def route_task(
        self,
        task: DiagramTask,
        input_data: Optional[dict] = None,
        require_govcloud: bool = False,
        classification: DataClassification = DataClassification.INTERNAL,
    ) -> tuple[Optional[ModelProvider], Optional[str], Optional[ProviderClient]]:
        """
        Route diagram task to optimal provider/model.

        Args:
            task: The diagram generation subtask
            input_data: Task input (for complexity estimation)
            require_govcloud: If True, only use GovCloud-compatible providers
            classification: Data classification level for compliance

        Returns:
            Tuple of (provider, model_id, client) or (None, None, None) if no LLM needed

        Raises:
            NoAvailableProviderError: All providers unavailable or incompatible
            DataClassificationError: Classification prevents external provider usage
        """
        # CRITICAL: CUI and above MUST use Bedrock only (FedRAMP/CMMC compliance)
        if classification in (DataClassification.CUI, DataClassification.RESTRICTED):
            require_govcloud = True
            self._emit_metric(
                "ClassificationEnforcement",
                1,
                {"Classification": classification.value, "ForcedGovCloud": "true"},
            )
            logger.info(
                f"Data classification {classification.value} enforcing GovCloud mode"
            )

        routing_candidates = DIAGRAM_TASK_ROUTING.get(task, [])

        if not routing_candidates:
            # Task doesn't require LLM (e.g., layout optimization)
            logger.debug(f"Task {task.value} does not require LLM")
            return None, None, None

        for provider, model_id in routing_candidates:
            # Check GovCloud compliance
            if require_govcloud or self.govcloud_mode:
                config = self._providers.get(provider)
                if not config or not config.govcloud_compatible:
                    logger.debug(f"Skipping {provider.value}: not GovCloud compatible")
                    continue
                if not self._validate_model_govcloud(model_id):
                    logger.debug(f"Skipping {model_id}: not available in GovCloud")
                    continue

            # Check circuit breaker
            breaker = self._circuit_breakers.get(provider)
            if breaker and not breaker.should_allow_request():
                self._emit_metric(
                    "CircuitBreakerRejection", 1, {"Provider": provider.value}
                )
                logger.debug(f"Skipping {provider.value}: circuit breaker open")
                continue

            # Check budget
            tracker = self._cost_trackers.get(provider)
            if tracker and not tracker.check_budget():
                self._emit_metric("BudgetExceeded", 1, {"Provider": provider.value})
                logger.warning(f"Skipping {provider.value}: daily budget exceeded")
                continue

            # Check provider is enabled
            config = self._providers.get(provider)
            if not config or not config.enabled:
                logger.debug(f"Skipping {provider.value}: not enabled")
                continue

            # Get or create client
            try:
                client = await self._get_or_create_client(provider)
                decision = RoutingDecision(
                    provider=provider,
                    model_id=model_id,
                    task=task,
                    classification=classification,
                    govcloud_mode=self.govcloud_mode or require_govcloud,
                )
                self._routing_decisions.append(decision)
                self._emit_metric(
                    "RoutingDecision",
                    1,
                    {"Task": task.value, "Provider": provider.value},
                )
                logger.info(f"Routed {task.value} to {provider.value}/{model_id}")
                return provider, model_id, client
            except Exception as e:
                self._circuit_breakers[provider].record_failure()
                self._emit_metric("ProviderFailure", 1, {"Provider": provider.value})
                logger.warning(f"Failed to create client for {provider.value}: {e}")
                continue

        raise NoAvailableProviderError(
            f"No available provider for task {task.value}. "
            f"GovCloud required: {require_govcloud}, Classification: {classification.value}"
        )

    def _validate_model_govcloud(self, model_id: str) -> bool:
        """Check if model is available in GovCloud."""
        if not self.govcloud_mode:
            return True
        return GOVCLOUD_BEDROCK_MODELS.get(model_id, False)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(TransientProviderError),
    )
    async def _get_or_create_client(self, provider: ModelProvider) -> ProviderClient:
        """Get or create client with retry on transient failures."""
        if provider in self._clients:
            return self._clients[provider]

        client = await self._create_client(provider)
        self._clients[provider] = client
        return client

    async def _create_client(self, provider: ModelProvider) -> ProviderClient:
        """Create authenticated client for provider.

        ADR-060: Bedrock is the single gateway for all LLM access.
        """
        if provider == ModelProvider.BEDROCK:
            return await self._create_bedrock_client()
        # OpenAI and Vertex are disabled - Bedrock is the single gateway
        raise ValueError(
            f"Provider {provider.value} is disabled. "
            "Bedrock is the single gateway for all LLM access per ADR-060."
        )

    async def _create_bedrock_client(self) -> ProviderClient:
        """Create Bedrock runtime client.

        Uses IAM role authentication - no API keys required.
        """
        from .providers.bedrock_client import BedrockDiagramClient

        return BedrockDiagramClient(region=self._get_bedrock_region())

    def sanitize_prompt(self, prompt: str) -> str:
        """
        Sanitize user prompt to prevent injection attacks.

        Args:
            prompt: Raw user input

        Returns:
            Sanitized prompt

        Raises:
            SecurityError: If injection attempt detected
        """
        if self._contains_injection_attempt(prompt):
            logger.warning("Prompt injection attempt detected")
            raise SecurityError("Potential prompt injection detected")

        # Basic sanitization
        sanitized = prompt.strip()

        # Remove control characters
        sanitized = "".join(c for c in sanitized if c.isprintable() or c in "\n\t")

        return sanitized

    def _contains_injection_attempt(self, prompt: str) -> bool:
        """Detect common prompt injection patterns."""
        prompt_lower = prompt.lower()
        return any(
            re.search(pattern, prompt_lower, re.IGNORECASE)
            for pattern in self.INJECTION_PATTERNS
        )

    def record_cost(
        self, provider: ModelProvider, input_tokens: int, output_tokens: int
    ) -> float:
        """
        Record cost after successful invocation.

        Args:
            provider: The provider that was used
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Total cost in USD
        """
        config = self._providers.get(provider)
        if not config:
            return 0.0

        cost = (
            input_tokens / 1000 * config.cost_per_1k_input
            + output_tokens / 1000 * config.cost_per_1k_output
        )

        tracker = self._cost_trackers[provider]
        tracker.current_daily_spend += cost
        tracker.current_monthly_spend += cost

        # Record success in circuit breaker
        self._circuit_breakers[provider].record_success()

        # Emit CloudWatch metric
        self._emit_metric("ProviderCost", cost, {"Provider": provider.value}, "None")
        self._emit_metric(
            "TokensUsed", input_tokens + output_tokens, {"Provider": provider.value}
        )

        logger.debug(
            f"Recorded cost for {provider.value}: ${cost:.4f} "
            f"({input_tokens} in, {output_tokens} out)"
        )

        return cost

    def _load_provider_configs(self) -> None:
        """Load provider configurations.

        ADR-060: Bedrock is the single gateway for all LLM access.
        This provides unified AWS billing, IAM authentication, and FedRAMP compliance.
        """
        # Bedrock (always available, GovCloud compatible)
        # Uses IAM role for authentication - no API keys needed
        self._providers[ModelProvider.BEDROCK] = ProviderConfig(
            provider=ModelProvider.BEDROCK,
            api_key_ssm_path=None,  # Uses IAM role
            endpoint=self._get_bedrock_endpoint(),
            enabled=True,
            govcloud_compatible=True,
            cost_per_1k_input=0.003,  # Claude Haiku pricing
            cost_per_1k_output=0.015,
        )

        # Note: OpenAI and Vertex providers are disabled per ADR-060.
        # All models are accessed through Bedrock as the single gateway.
        # This ensures unified billing, IAM-based auth, and FedRAMP compliance.

    def _get_ssm_param_sync(self, path: str, default: str = "") -> str:
        """Get SSM parameter synchronously with fallback."""
        if not self.ssm:
            return default
        try:
            response = self.ssm.get_parameter(Name=path, WithDecryption=True)
            return response["Parameter"]["Value"]
        except Exception:
            return default

    def _emit_metric(
        self,
        name: str,
        value: float,
        dimensions: Optional[dict] = None,
        unit: str = "Count",
    ) -> None:
        """Emit CloudWatch metric."""
        if not self.cloudwatch:
            return
        try:
            metric_data: dict[str, Any] = {
                "MetricName": name,
                "Value": value,
                "Unit": unit,
            }
            if dimensions:
                metric_data["Dimensions"] = [
                    {"Name": k, "Value": v} for k, v in dimensions.items()
                ]
            self.cloudwatch.put_metric_data(
                Namespace="Aura/DiagramGeneration", MetricData=[metric_data]
            )
        except Exception as e:
            logger.debug(f"Failed to emit metric {name}: {e}")

    def get_routing_stats(self) -> dict[str, Any]:
        """Get routing statistics for monitoring."""
        stats: dict[str, Any] = {
            "total_decisions": len(self._routing_decisions),
            "by_provider": {},
            "by_task": {},
            "circuit_breakers": {},
            "costs": {},
        }

        for decision in self._routing_decisions:
            # By provider
            provider_key = decision.provider.value
            stats["by_provider"][provider_key] = (
                stats["by_provider"].get(provider_key, 0) + 1
            )

            # By task
            task_key = decision.task.value
            stats["by_task"][task_key] = stats["by_task"].get(task_key, 0) + 1

        # Circuit breaker states
        for provider, breaker in self._circuit_breakers.items():
            stats["circuit_breakers"][provider.value] = {
                "state": breaker.state.value,
                "failure_count": breaker.failure_count,
            }

        # Cost tracking
        for provider, tracker in self._cost_trackers.items():
            stats["costs"][provider.value] = {
                "daily_spend": tracker.current_daily_spend,
                "monthly_spend": tracker.current_monthly_spend,
                "daily_budget": tracker.daily_budget_usd,
            }

        return stats
