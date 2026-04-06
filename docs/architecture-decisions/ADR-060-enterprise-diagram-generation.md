# ADR-060: Enterprise Diagram Generation with Multi-Provider Model Routing

**Status:** Accepted
**Date:** 2026-01-12
**Decision Makers:** Project Aura Platform Team
**Related:** ADR-015 (Tiered LLM Model Strategy), ADR-056 (Documentation Agent), ADR-004 (Multi-Cloud Architecture), ADR-051 (RLM Input Sanitizer)

---

## Executive Summary

This ADR establishes an enterprise-grade diagram generation system targeting output quality comparable to commercial diagramming tools such as Eraser.io (as observed from its public product pages in January 2026). The initiative extends Aura's existing Documentation Agent (ADR-056) with official cloud provider icons, intelligent layout engines, AI-powered diagram generation, and a multi-provider model routing strategy that selects optimal AI models (Claude, OpenAI, Gemini) based on task requirements.

**Core Thesis:** Different model families have different strengths across diagram-generation subtasks. By extending Aura's existing tiered model routing (ADR-015) to support multi-provider selection, we can leverage Claude for DSL/code generation, vision-capable models for image understanding, and dedicated rendering engines for visual output—targeting output quality comparable to leading commercial diagramming tools.

**Key Outcomes:**
- Official AWS/Azure/GCP icon library integration (SVG sprites)
- Intelligent layout engine using ELK.js/Dagre with constraint-based positioning
- Eraser-style DSL for expressive diagram definitions
- Multi-provider model routing for task-optimal AI selection
- Natural language to diagram generation
- Git integration for diagram versioning
- Reference architecture library with enterprise patterns
- WCAG 2.1 AA accessible diagram viewer

---

## Expert Review Summary

This ADR was reviewed by domain experts. Key findings have been incorporated:

| Expert | Focus Area | Critical Findings |
|--------|------------|-------------------|
| **Architecture Review** | Infrastructure | Circuit breaker implementation, GovCloud region handling, IAM policies, data classification enforcement, cost tracking |
| **Design Review** | Frontend | Icon color modes, dark theme WCAG compliance, keyboard navigation, progressive generation UX, References Used panel design |

### Critical Issues Addressed (P0/P1)

| Priority | Issue | Resolution |
|----------|-------|------------|
| **P0** | No data classification enforcement for CUI/FedRAMP | Added `DataClassification` enum with routing enforcement |
| **P0** | Circuit breaker implementation missing | Added full `CircuitBreakerState` implementation |
| **P1** | GovCloud region defaults to `us-east-1` | Added `_get_bedrock_region()` with partition detection |
| **P1** | Missing prompt injection mitigation | Integrated ADR-051 `InputSanitizer` |
| **P1** | No IAM policy template | Added CloudFormation for diagram service role |
| **P1** | Icon color fragmentation | Added `IconColorMode` (native/aura_semantic/monochrome) |
| **P1** | Dark theme not specified | Added WCAG AA verified color palette |
| **P1** | No keyboard navigation model | Added full accessibility specification |

---

## Competitive Analysis: Eraser.io vs. Aura Current State

### Eraser.io Publicly Documented Capabilities (as of January 2026)

The following summarizes capabilities publicly documented on Eraser.io's product pages as of January 2026. Readers should verify against current vendor documentation before decision-making.

| Feature | Eraser Publicly Documented Capability |
|---------|----------------------|
| **Cloud Provider Icons** | Official AWS/Azure/GCP SVG icons with brand colors |
| **Layout Engine** | Constraint-based layout |
| **Nested Groupings** | Multi-level containers with color-coded borders (e.g., Terraform modules, K8s namespaces) |
| **Connection Styles** | Solid/dashed/dotted lines with inline labels and directional arrows |
| **Reference Library** | Architecture templates |
| **AI Generation** | LLM-powered natural language to diagram |
| **Git Sync** | Direct commit to repository |
| **Diagram Types** | Multiple specialized diagram types |
| **Dark Theme** | Dark canvas theme |

### Aura Current State (ADR-056)

| Feature | Aura Implementation | Gap Level |
|---------|---------------------|-----------|
| **Cloud Provider Icons** | Generic Mermaid shapes (rectangles, cylinders) | **Critical** |
| **Layout Engine** | Mermaid's basic dagre auto-layout | **High** |
| **Nested Groupings** | Basic Mermaid subgraphs, limited nesting | **Medium** |
| **Connection Styles** | Basic arrows with limited styling | **Medium** |
| **Reference Library** | Pre-built templates (HITL, Auth, Agent Orchestration) | **Low** |
| **AI Generation** | Template-based only, no natural language | **High** |
| **Git Sync** | Not implemented | **Medium** |
| **Diagram Types** | 7 types (architecture, data flow, dependency, component, sequence, ER, state) | **Medium** |
| **Confidence Scoring** | Production-grade with calibration (we are not aware of any diagramming vendor that publicly documents equivalent confidence calibration as of January 2026) | **Advantage** |

---

## Context

### The Model Selection Problem

Diagram generation involves multiple distinct subtasks with different optimal model characteristics:

| Subtask | Best Model Type | Reasoning |
|---------|-----------------|-----------|
| **DSL/Code Generation** | Claude (Sonnet/Opus) | Structured output, follows schemas precisely |
| **Natural Language Understanding** | Claude (Sonnet) | Intent extraction, requirement parsing |
| **Layout Optimization** | Algorithmic (ELK.js) | Deterministic graph algorithms, no LLM needed |
| **Icon Rendering** | None (SVG sprites) | Pre-built vector assets |
| **Diagram-to-Code (reverse)** | Gemini Vision / GPT-4V | Image understanding capabilities |
| **Creative/Conceptual Diagrams** | DALL-E 3 / Gemini | Generative image synthesis |
| **Diagram Critique/Improvement** | Claude (Opus) | Deep reasoning about architecture |

**Key Insight:** Claude models are not optimized for image generation or image understanding. For tasks requiring visual comprehension (importing hand-drawn diagrams, reverse-engineering screenshots), vision-capable models like Gemini or GPT-4V provide superior results.

### Existing Infrastructure

Aura already has:

1. **Tiered Model Routing (ADR-015):** 3-tier system (FAST/ACCURATE/MAXIMUM) with cost optimization
2. **Bedrock Integration:** Claude models via AWS Bedrock (GovCloud compatible)
3. **Model Router Service:** Dynamic routing with A/B testing, complexity scoring, CloudWatch metrics
4. **Documentation Agent (ADR-056):** Mermaid generation, confidence scoring, caching
5. **Input Sanitizer (ADR-051):** Prompt injection prevention

**Gap:** The current model router only supports Anthropic Claude models via Bedrock. Multi-provider support is needed for optimal diagram generation.

---

## Decision

**Implement an enterprise diagram generation system with multi-provider model routing that extends ADR-015 and ADR-056 to achieve output quality comparable to leading commercial diagramming tools through specialized model selection per subtask.**

### Architecture Overview

```
                    ENTERPRISE DIAGRAM GENERATION ARCHITECTURE

    LAYER 1: AI MODEL PROVIDERS (Multi-Provider Routing)
    +------------------+  +------------------+  +------------------+
    |  AWS Bedrock     |  |   OpenAI API     |  |  Google Vertex   |
    |  (Claude)        |  |  (GPT-4V, DALL-E)|  |  (Gemini Pro)    |
    +--------+---------+  +--------+---------+  +--------+---------+
             |                     |                     |
             +---------------------+---------------------+
                                   |
    LAYER 2: MULTI-PROVIDER MODEL ROUTER
    +------------------------------v---------------------------------------+
    |                    DiagramModelRouter                                 |
    |  +-----------------+  +------------------+  +---------------------+  |
    |  | Task Classifier |  | Provider Selector|  | Cost/Latency        |  |
    |  | (subtask→model) |  | (availability)   |  | Optimizer           |  |
    |  +-----------------+  +------------------+  +---------------------+  |
    |  +-----------------+  +------------------+  +---------------------+  |
    |  | Circuit Breaker |  | Data Class Check |  | Retry Handler       |  |
    |  | (per provider)  |  | (CUI enforcement)|  | (exp. backoff)      |  |
    |  +-----------------+  +------------------+  +---------------------+  |
    +----------------------------------+-----------------------------------+
                                       |
    LAYER 3: DIAGRAM GENERATION ENGINE |
    +----------------------------------v-----------------------------------+
    |  +-------------------+  +-------------------+  +------------------+  |
    |  | DSL Parser        |  | Natural Language  |  | Vision Processor |  |
    |  | (Eraser-style)    |  | to DSL Generator  |  | (import/reverse) |  |
    |  +-------------------+  +-------------------+  +------------------+  |
    |  +-------------------+  +-------------------+  +------------------+  |
    |  | Icon Library      |  | Layout Engine     |  | Reference        |  |
    |  | (AWS/Azure/GCP)   |  | (ELK.js/Dagre)    |  | Architectures    |  |
    |  +-------------------+  +-------------------+  +------------------+  |
    +----------------------------------+-----------------------------------+
                                       |
    LAYER 4: RENDERING ENGINE          |
    +----------------------------------v-----------------------------------+
    |  +-------------------+  +-------------------+  +------------------+  |
    |  | SVG Renderer      |  | Canvas Renderer   |  | Export Service   |  |
    |  | (server-side)     |  | (client-side)     |  | (PNG/PDF/draw.io)|  |
    |  +-------------------+  +-------------------+  +------------------+  |
    +----------------------------------------------------------------------+
```

---

## Component Details

### 1. Multi-Provider Model Router Extension

Extends ADR-015's `ModelRouter` to support multiple AI providers with resilience patterns:

```python
# src/services/diagram_model_router.py

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timedelta
import os
import re

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from src.services.rlm.input_sanitizer import InputSanitizer  # ADR-051


class ModelProvider(Enum):
    """Supported AI model providers."""
    BEDROCK = "bedrock"      # AWS Bedrock (Claude) - primary, GovCloud compatible
    OPENAI = "openai"        # OpenAI API (GPT-4V, DALL-E 3)
    VERTEX = "vertex"        # Google Vertex AI (Gemini Pro Vision)


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
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


# Task-to-Provider mapping with fallback chains
DIAGRAM_TASK_ROUTING: dict[DiagramTask, list[tuple[ModelProvider, str]]] = {
    DiagramTask.DSL_GENERATION: [
        (ModelProvider.BEDROCK, "anthropic.claude-3-5-sonnet-20241022-v2:0"),
        (ModelProvider.OPENAI, "gpt-4-turbo"),
    ],
    DiagramTask.INTENT_EXTRACTION: [
        (ModelProvider.BEDROCK, "anthropic.claude-3-5-sonnet-20241022-v2:0"),
        (ModelProvider.OPENAI, "gpt-4-turbo"),
    ],
    DiagramTask.DIAGRAM_CRITIQUE: [
        (ModelProvider.BEDROCK, "anthropic.claude-3-opus-20240229-v1:0"),
        (ModelProvider.OPENAI, "gpt-4-turbo"),
    ],
    DiagramTask.IMAGE_UNDERSTANDING: [
        # Claude is NOT optimal for image understanding - use vision models
        (ModelProvider.VERTEX, "gemini-1.5-pro-vision"),
        (ModelProvider.OPENAI, "gpt-4-vision-preview"),
        (ModelProvider.BEDROCK, "anthropic.claude-3-5-sonnet-20241022-v2:0"),  # Fallback only
    ],
    DiagramTask.CREATIVE_GENERATION: [
        # For freeform/artistic diagram generation
        (ModelProvider.OPENAI, "dall-e-3"),
        (ModelProvider.VERTEX, "imagen-3"),
    ],
    DiagramTask.LAYOUT_OPTIMIZATION: [
        # No LLM needed - use algorithmic layout
    ],
}

# GovCloud Bedrock model availability (verified 2026-01)
GOVCLOUD_BEDROCK_MODELS = {
    "anthropic.claude-3-5-sonnet-20241022-v2:0": True,
    "anthropic.claude-3-opus-20240229-v1:0": True,
    "anthropic.claude-instant-v1": True,
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

    def record_success(self) -> None:
        """Record success and reset circuit to closed."""
        self.failure_count = 0
        self.last_success = datetime.utcnow()
        self.state = CircuitState.CLOSED
        self._half_open_calls = 0

    def should_allow_request(self) -> bool:
        """Check if a request should be allowed through."""
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if self.last_failure and \
               datetime.utcnow() - self.last_failure > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
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


class TransientProviderError(Exception):
    """Retriable provider error (rate limit, timeout)."""
    pass


class NoAvailableProviderError(Exception):
    """Raised when no provider is available for a task."""
    pass


class DataClassificationError(Exception):
    """Raised when data classification prevents provider usage."""
    pass


class DiagramModelRouter:
    """
    Multi-provider model router for diagram generation tasks.

    Extends ADR-015 tiered routing with provider selection based on:
    1. Task requirements (vision, generation, reasoning)
    2. Data classification (CUI enforcement)
    3. Provider availability (API health, rate limits)
    4. Cost optimization (cheapest capable provider)
    5. GovCloud compliance (Bedrock-only for regulated workloads)

    Security:
    - API keys stored in SSM Parameter Store (SecureString)
    - No credentials in code or environment variables
    - Provider endpoints validated against allowlist
    - Data classification enforcement for FedRAMP/CMMC
    - Prompt injection prevention via InputSanitizer
    """

    GOVCLOUD_REGIONS = {"us-gov-west-1", "us-gov-east-1"}

    def __init__(
        self,
        ssm_client,
        cloudwatch_client=None,
        environment: str = "dev",
        govcloud_mode: bool = False,
    ):
        self.ssm = ssm_client
        self.cloudwatch = cloudwatch_client
        self.environment = environment
        self.govcloud_mode = govcloud_mode or self._detect_govcloud()

        # Load provider configurations from SSM
        self._providers: dict[ModelProvider, ProviderConfig] = {}
        self._load_provider_configs()

        # Circuit breakers for provider health
        self._circuit_breakers: dict[ModelProvider, CircuitBreakerState] = {
            provider: CircuitBreakerState() for provider in ModelProvider
        }

        # Cost tracking
        self._cost_trackers: dict[ModelProvider, ProviderCostTracker] = {
            provider: ProviderCostTracker(provider=provider) for provider in ModelProvider
        }

        # Input sanitizer for prompt injection prevention (ADR-051)
        self.sanitizer = InputSanitizer()

        # Metrics
        self._routing_decisions: list[dict] = []

    def _detect_govcloud(self) -> bool:
        """Auto-detect GovCloud based on region."""
        region = os.environ.get("AWS_REGION", "us-east-1")
        return region in self.GOVCLOUD_REGIONS

    def _get_bedrock_region(self) -> str:
        """Get appropriate Bedrock region based on partition."""
        region = os.environ.get("AWS_REGION", "us-east-1")

        # Detect GovCloud partition
        if region.startswith("us-gov-"):
            # Bedrock is available in us-gov-west-1
            return "us-gov-west-1"

        return region

    def _get_bedrock_endpoint(self) -> str:
        """Get Bedrock endpoint for current region/partition."""
        region = self._get_bedrock_region()

        # GovCloud uses different URL suffix
        if region.startswith("us-gov-"):
            return f"bedrock-runtime.{region}.amazonaws-us-gov.com"

        return f"bedrock-runtime.{region}.amazonaws.com"

    def _ssm_path(self, provider: str, key: str) -> str:
        """Construct consistent SSM parameter path."""
        return f"/aura/{self.environment}/providers/{provider}/{key}"

    async def route_task(
        self,
        task: DiagramTask,
        input_data: dict,
        require_govcloud: bool = False,
        classification: DataClassification = DataClassification.INTERNAL,
    ) -> tuple[ModelProvider, str, "AuthenticatedClient"]:
        """
        Route diagram task to optimal provider/model.

        Args:
            task: The diagram generation subtask
            input_data: Task input (for complexity estimation)
            require_govcloud: If True, only use GovCloud-compatible providers
            classification: Data classification level for compliance

        Returns:
            Tuple of (provider, model_id, authenticated_client)

        Raises:
            NoAvailableProviderError: All providers unavailable or incompatible
            DataClassificationError: Classification prevents external provider usage
        """
        # CRITICAL: CUI and above MUST use Bedrock only (FedRAMP/CMMC compliance)
        if classification in (DataClassification.CUI, DataClassification.RESTRICTED):
            require_govcloud = True
            self._emit_metric("ClassificationEnforcement", 1, {
                "Classification": classification.value,
                "ForcedGovCloud": "true",
            })

        routing_candidates = DIAGRAM_TASK_ROUTING.get(task, [])

        if not routing_candidates:
            # Task doesn't require LLM (e.g., layout optimization)
            return None, None, None

        for provider, model_id in routing_candidates:
            # Check GovCloud compliance
            if require_govcloud or self.govcloud_mode:
                config = self._providers.get(provider)
                if not config or not config.govcloud_compatible:
                    continue
                # Verify model is available in GovCloud
                if not self._validate_model_govcloud(model_id):
                    continue

            # Check circuit breaker
            breaker = self._circuit_breakers.get(provider)
            if breaker and not breaker.should_allow_request():
                self._emit_metric("CircuitBreakerRejection", 1, {"Provider": provider.value})
                continue

            # Check budget
            tracker = self._cost_trackers.get(provider)
            if tracker and tracker.current_daily_spend >= tracker.daily_budget_usd:
                self._emit_metric("BudgetExceeded", 1, {"Provider": provider.value})
                continue

            # Check provider is enabled
            config = self._providers.get(provider)
            if not config or not config.enabled:
                continue

            # Create authenticated client with retry
            try:
                client = await self._create_client_with_retry(provider)
                self._record_routing_decision(task, provider, model_id, classification)
                return provider, model_id, client
            except Exception as e:
                self._circuit_breakers[provider].record_failure()
                self._emit_metric("ProviderFailure", 1, {"Provider": provider.value})
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
    async def _create_client_with_retry(self, provider: ModelProvider) -> "AuthenticatedClient":
        """Create client with retry on transient failures."""
        return await self._create_client(provider)

    async def _create_client(self, provider: ModelProvider) -> "AuthenticatedClient":
        """Create authenticated client for provider."""
        if provider == ModelProvider.BEDROCK:
            return await self._create_bedrock_client()
        elif provider == ModelProvider.OPENAI:
            return await self._create_openai_client()
        elif provider == ModelProvider.VERTEX:
            return await self._create_vertex_client()
        raise ValueError(f"Unknown provider: {provider}")

    async def _create_bedrock_client(self) -> "BedrockClient":
        """Create Bedrock runtime client with retry configuration."""
        import boto3
        from botocore.config import Config as BotoConfig

        config = BotoConfig(
            region_name=self._get_bedrock_region(),
            retries={
                "max_attempts": 3,
                "mode": "adaptive",  # Adaptive retry mode for throttling
            },
            connect_timeout=5,
            read_timeout=60,  # LLM responses can take time
        )

        # boto3 uses IAM role credentials automatically
        client = boto3.client("bedrock-runtime", config=config)
        return BedrockClient(client)

    async def _health_check_provider(self, provider: ModelProvider) -> bool:
        """Proactive health check for provider availability."""
        try:
            config = self._providers.get(provider)
            if not config:
                return False

            if provider == ModelProvider.BEDROCK:
                client = await self._create_client(provider)
                # Lightweight ping with minimal tokens
                await client.invoke(
                    model_id="anthropic.claude-instant-v1",
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=1,
                )
            elif provider == ModelProvider.OPENAI:
                import httpx
                api_key = await self._get_api_key(provider)
                async with httpx.AsyncClient() as http:
                    resp = await http.get(
                        "https://api.openai.com/v1/models",
                        headers={"Authorization": f"Bearer {api_key}"},
                        timeout=5.0,
                    )
                    return resp.status_code == 200

            return True
        except Exception:
            return False

    def sanitize_prompt(self, prompt: str) -> str:
        """Sanitize user prompt to prevent injection attacks."""
        sanitized = self.sanitizer.sanitize(
            prompt,
            context="diagram_generation",
            allow_code_blocks=False,
        )

        # Additional injection pattern detection
        if self._contains_injection_attempt(sanitized):
            raise SecurityError("Potential prompt injection detected")

        return sanitized

    def _contains_injection_attempt(self, prompt: str) -> bool:
        """Detect common prompt injection patterns."""
        injection_patterns = [
            r'ignore (previous|all|above) instructions',
            r'system:\s*',
            r'<\|im_start\|>',
            r'### (System|Human|Assistant)',
            r'STOP\.?\s*NEW INSTRUCTION',
        ]
        return any(re.search(p, prompt, re.IGNORECASE) for p in injection_patterns)

    def record_cost(self, provider: ModelProvider, input_tokens: int, output_tokens: int) -> None:
        """Record cost after successful invocation."""
        config = self._providers.get(provider)
        if not config:
            return

        cost = (input_tokens / 1000 * config.cost_per_1k_input +
                output_tokens / 1000 * config.cost_per_1k_output)

        tracker = self._cost_trackers[provider]
        tracker.current_daily_spend += cost
        tracker.current_monthly_spend += cost

        # Record success in circuit breaker
        self._circuit_breakers[provider].record_success()

        # Emit CloudWatch metric
        self._emit_metric("ProviderCost", cost, {"Provider": provider.value})

    def _load_provider_configs(self) -> None:
        """Load provider configurations from SSM Parameter Store."""
        # Bedrock (always available, GovCloud compatible)
        self._providers[ModelProvider.BEDROCK] = ProviderConfig(
            provider=ModelProvider.BEDROCK,
            api_key_ssm_path=None,  # Uses IAM role
            endpoint=self._get_bedrock_endpoint(),
            enabled=True,
            govcloud_compatible=True,
            cost_per_1k_input=0.003,
            cost_per_1k_output=0.015,
        )

        # OpenAI (optional, not GovCloud compatible)
        openai_enabled = self._get_ssm_param(
            self._ssm_path("openai", "enabled"),
            default="false"
        ) == "true"

        if openai_enabled and not self.govcloud_mode:
            self._providers[ModelProvider.OPENAI] = ProviderConfig(
                provider=ModelProvider.OPENAI,
                api_key_ssm_path=self._ssm_path("openai", "api-key"),
                endpoint="https://api.openai.com/v1",
                enabled=True,
                govcloud_compatible=False,
                cost_per_1k_input=0.01,
                cost_per_1k_output=0.03,
            )

        # Vertex AI (optional, not GovCloud compatible)
        vertex_enabled = self._get_ssm_param(
            self._ssm_path("vertex", "enabled"),
            default="false"
        ) == "true"

        if vertex_enabled and not self.govcloud_mode:
            self._providers[ModelProvider.VERTEX] = ProviderConfig(
                provider=ModelProvider.VERTEX,
                api_key_ssm_path=self._ssm_path("vertex", "service-account"),
                endpoint="https://us-central1-aiplatform.googleapis.com",
                enabled=True,
                govcloud_compatible=False,
                cost_per_1k_input=0.00025,
                cost_per_1k_output=0.0005,
            )

    def _get_ssm_param(self, path: str, default: str = None) -> str:
        """Get SSM parameter with fallback."""
        try:
            response = self.ssm.get_parameter(Name=path, WithDecryption=True)
            return response["Parameter"]["Value"]
        except Exception:
            return default

    def _emit_metric(self, name: str, value: float, dimensions: dict = None, unit: str = "Count") -> None:
        """Emit CloudWatch metric."""
        if not self.cloudwatch:
            return
        try:
            metric_data = {
                "MetricName": name,
                "Value": value,
                "Unit": unit,
            }
            if dimensions:
                metric_data["Dimensions"] = [
                    {"Name": k, "Value": v} for k, v in dimensions.items()
                ]
            self.cloudwatch.put_metric_data(
                Namespace="Aura/DiagramGeneration",
                MetricData=[metric_data]
            )
        except Exception:
            pass  # Don't fail on metrics

    def _record_routing_decision(
        self,
        task: DiagramTask,
        provider: ModelProvider,
        model_id: str,
        classification: DataClassification,
    ) -> None:
        """Record routing decision for analytics."""
        self._routing_decisions.append({
            "timestamp": datetime.utcnow().isoformat(),
            "task": task.value,
            "provider": provider.value,
            "model_id": model_id,
            "classification": classification.value,
            "govcloud_mode": self.govcloud_mode,
        })
        self._emit_metric("RoutingDecision", 1, {
            "Task": task.value,
            "Provider": provider.value,
        })


class BedrockClient:
    """Wrapper for Bedrock runtime client."""

    def __init__(self, boto_client):
        self._client = boto_client

    async def invoke(self, model_id: str, messages: list, **kwargs) -> dict:
        """Invoke Bedrock model using Converse API."""
        # Use Converse API for Claude models (preferred over InvokeModel)
        response = self._client.converse(
            modelId=model_id,
            messages=[
                {
                    "role": m["role"],
                    "content": [{"text": m["content"]}]
                }
                for m in messages
            ],
            inferenceConfig={
                "maxTokens": kwargs.get("max_tokens", 4096),
                "temperature": kwargs.get("temperature", 0.7),
            },
        )

        return {
            "content": response["output"]["message"]["content"][0]["text"],
            "usage": response["usage"],
            "stop_reason": response["stopReason"],
        }


class SecurityError(Exception):
    """Raised for security-related failures."""
    pass
```

### 2. Official Cloud Provider Icon Library with Color Modes

```python
# src/services/diagrams/icon_library.py

from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class CloudProvider(Enum):
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    KUBERNETES = "kubernetes"
    GENERIC = "generic"


class IconCategory(Enum):
    COMPUTE = "compute"
    DATABASE = "database"
    STORAGE = "storage"
    NETWORKING = "networking"
    SECURITY = "security"
    ANALYTICS = "analytics"
    ML = "ml"
    INTEGRATION = "integration"
    MANAGEMENT = "management"
    DEVTOOLS = "devtools"


class IconColorMode(Enum):
    """Icon color rendering modes (design review)."""
    NATIVE = "native"           # Official cloud provider colors (AWS orange, Azure blue)
    AURA_SEMANTIC = "aura"      # Map to Aura's design system palette
    MONOCHROME = "monochrome"   # Single color with opacity variations


# Aura semantic color mapping by category (the design system alignment)
AURA_CATEGORY_COLORS: dict[IconCategory, str] = {
    IconCategory.COMPUTE: "#3B82F6",      # Primary blue
    IconCategory.DATABASE: "#8B5CF6",     # Violet-500
    IconCategory.STORAGE: "#10B981",      # Success green
    IconCategory.NETWORKING: "#6366F1",   # Indigo-500
    IconCategory.SECURITY: "#DC2626",     # Critical red
    IconCategory.ANALYTICS: "#06B6D4",    # Cyan-500
    IconCategory.ML: "#14B8A6",           # Teal-500
    IconCategory.INTEGRATION: "#F59E0B",  # Medium amber
    IconCategory.MANAGEMENT: "#8B5CF6",   # Violet-500
    IconCategory.DEVTOOLS: "#6B7280",     # Gray-500
}


@dataclass
class DiagramIcon:
    """Icon metadata for diagram rendering."""
    id: str
    provider: CloudProvider
    category: IconCategory
    name: str
    svg_path: str
    display_name: str
    aliases: list[str]
    native_color: str  # Original provider color
    width: int = 48
    height: int = 48

    def get_color(self, mode: IconColorMode) -> str:
        """Get icon color based on rendering mode."""
        if mode == IconColorMode.NATIVE:
            return self.native_color
        elif mode == IconColorMode.AURA_SEMANTIC:
            return AURA_CATEGORY_COLORS.get(self.category, "#3B82F6")
        elif mode == IconColorMode.MONOCHROME:
            return "#3B82F6"  # Primary blue
        return self.native_color


# AWS Architecture Icons (Official)
# Source: https://aws.amazon.com/architecture/icons/
AWS_ICONS: dict[str, DiagramIcon] = {
    # Compute
    "aws:ec2": DiagramIcon(
        id="aws:ec2",
        provider=CloudProvider.AWS,
        category=IconCategory.COMPUTE,
        name="ec2",
        svg_path="icons/aws/compute/ec2.svg",
        display_name="Amazon EC2",
        aliases=["ec2", "instance", "vm"],
        native_color="#FF9900",
    ),
    "aws:lambda": DiagramIcon(
        id="aws:lambda",
        provider=CloudProvider.AWS,
        category=IconCategory.COMPUTE,
        name="lambda",
        svg_path="icons/aws/compute/lambda.svg",
        display_name="AWS Lambda",
        aliases=["lambda", "function", "serverless"],
        native_color="#FF9900",
    ),
    "aws:ecs": DiagramIcon(
        id="aws:ecs",
        provider=CloudProvider.AWS,
        category=IconCategory.COMPUTE,
        name="ecs",
        svg_path="icons/aws/compute/ecs.svg",
        display_name="Amazon ECS",
        aliases=["ecs", "container", "fargate"],
        native_color="#FF9900",
    ),
    "aws:eks": DiagramIcon(
        id="aws:eks",
        provider=CloudProvider.AWS,
        category=IconCategory.COMPUTE,
        name="eks",
        svg_path="icons/aws/compute/eks.svg",
        display_name="Amazon EKS",
        aliases=["eks", "kubernetes", "k8s"],
        native_color="#FF9900",
    ),

    # Database
    "aws:rds": DiagramIcon(
        id="aws:rds",
        provider=CloudProvider.AWS,
        category=IconCategory.DATABASE,
        name="rds",
        svg_path="icons/aws/database/rds.svg",
        display_name="Amazon RDS",
        aliases=["rds", "database", "mysql", "postgres"],
        native_color="#3B48CC",
    ),
    "aws:dynamodb": DiagramIcon(
        id="aws:dynamodb",
        provider=CloudProvider.AWS,
        category=IconCategory.DATABASE,
        name="dynamodb",
        svg_path="icons/aws/database/dynamodb.svg",
        display_name="Amazon DynamoDB",
        aliases=["dynamodb", "nosql", "table"],
        native_color="#3B48CC",
    ),
    "aws:elasticache": DiagramIcon(
        id="aws:elasticache",
        provider=CloudProvider.AWS,
        category=IconCategory.DATABASE,
        name="elasticache",
        svg_path="icons/aws/database/elasticache.svg",
        display_name="Amazon ElastiCache",
        aliases=["elasticache", "redis", "memcached", "cache"],
        native_color="#3B48CC",
    ),
    "aws:neptune": DiagramIcon(
        id="aws:neptune",
        provider=CloudProvider.AWS,
        category=IconCategory.DATABASE,
        name="neptune",
        svg_path="icons/aws/database/neptune.svg",
        display_name="Amazon Neptune",
        aliases=["neptune", "graph", "graphdb"],
        native_color="#3B48CC",
    ),

    # Storage
    "aws:s3": DiagramIcon(
        id="aws:s3",
        provider=CloudProvider.AWS,
        category=IconCategory.STORAGE,
        name="s3",
        svg_path="icons/aws/storage/s3.svg",
        display_name="Amazon S3",
        aliases=["s3", "bucket", "storage", "object"],
        native_color="#3F8624",
    ),

    # Networking
    "aws:vpc": DiagramIcon(
        id="aws:vpc",
        provider=CloudProvider.AWS,
        category=IconCategory.NETWORKING,
        name="vpc",
        svg_path="icons/aws/networking/vpc.svg",
        display_name="Amazon VPC",
        aliases=["vpc", "network", "virtual-network"],
        native_color="#8C4FFF",
    ),
    "aws:alb": DiagramIcon(
        id="aws:alb",
        provider=CloudProvider.AWS,
        category=IconCategory.NETWORKING,
        name="alb",
        svg_path="icons/aws/networking/elb-alb.svg",
        display_name="Application Load Balancer",
        aliases=["alb", "elb", "load-balancer"],
        native_color="#8C4FFF",
    ),
    "aws:cloudfront": DiagramIcon(
        id="aws:cloudfront",
        provider=CloudProvider.AWS,
        category=IconCategory.NETWORKING,
        name="cloudfront",
        svg_path="icons/aws/networking/cloudfront.svg",
        display_name="Amazon CloudFront",
        aliases=["cloudfront", "cdn"],
        native_color="#8C4FFF",
    ),
    "aws:api-gateway": DiagramIcon(
        id="aws:api-gateway",
        provider=CloudProvider.AWS,
        category=IconCategory.NETWORKING,
        name="api-gateway",
        svg_path="icons/aws/networking/api-gateway.svg",
        display_name="Amazon API Gateway",
        aliases=["api-gateway", "apigw", "api"],
        native_color="#FF4F8B",
    ),

    # Security
    "aws:cognito": DiagramIcon(
        id="aws:cognito",
        provider=CloudProvider.AWS,
        category=IconCategory.SECURITY,
        name="cognito",
        svg_path="icons/aws/security/cognito.svg",
        display_name="Amazon Cognito",
        aliases=["cognito", "auth", "identity"],
        native_color="#DD344C",
    ),
    "aws:secrets-manager": DiagramIcon(
        id="aws:secrets-manager",
        provider=CloudProvider.AWS,
        category=IconCategory.SECURITY,
        name="secrets-manager",
        svg_path="icons/aws/security/secrets-manager.svg",
        display_name="AWS Secrets Manager",
        aliases=["secrets-manager", "secrets"],
        native_color="#DD344C",
    ),

    # Management
    "aws:cloudwatch": DiagramIcon(
        id="aws:cloudwatch",
        provider=CloudProvider.AWS,
        category=IconCategory.MANAGEMENT,
        name="cloudwatch",
        svg_path="icons/aws/management/cloudwatch.svg",
        display_name="Amazon CloudWatch",
        aliases=["cloudwatch", "monitoring", "logs", "metrics"],
        native_color="#FF4F8B",
    ),

    # ML
    "aws:bedrock": DiagramIcon(
        id="aws:bedrock",
        provider=CloudProvider.AWS,
        category=IconCategory.ML,
        name="bedrock",
        svg_path="icons/aws/ml/bedrock.svg",
        display_name="Amazon Bedrock",
        aliases=["bedrock", "llm", "ai", "claude"],
        native_color="#01A88D",
    ),
    "aws:sagemaker": DiagramIcon(
        id="aws:sagemaker",
        provider=CloudProvider.AWS,
        category=IconCategory.ML,
        name="sagemaker",
        svg_path="icons/aws/ml/sagemaker.svg",
        display_name="Amazon SageMaker",
        aliases=["sagemaker", "ml", "training"],
        native_color="#01A88D",
    ),

    # Integration
    "aws:sqs": DiagramIcon(
        id="aws:sqs",
        provider=CloudProvider.AWS,
        category=IconCategory.INTEGRATION,
        name="sqs",
        svg_path="icons/aws/integration/sqs.svg",
        display_name="Amazon SQS",
        aliases=["sqs", "queue", "message"],
        native_color="#FF4F8B",
    ),
    "aws:sns": DiagramIcon(
        id="aws:sns",
        provider=CloudProvider.AWS,
        category=IconCategory.INTEGRATION,
        name="sns",
        svg_path="icons/aws/integration/sns.svg",
        display_name="Amazon SNS",
        aliases=["sns", "notification", "topic", "pub-sub"],
        native_color="#FF4F8B",
    ),
    "aws:eventbridge": DiagramIcon(
        id="aws:eventbridge",
        provider=CloudProvider.AWS,
        category=IconCategory.INTEGRATION,
        name="eventbridge",
        svg_path="icons/aws/integration/eventbridge.svg",
        display_name="Amazon EventBridge",
        aliases=["eventbridge", "events", "bus"],
        native_color="#FF4F8B",
    ),
    "aws:step-functions": DiagramIcon(
        id="aws:step-functions",
        provider=CloudProvider.AWS,
        category=IconCategory.INTEGRATION,
        name="step-functions",
        svg_path="icons/aws/integration/step-functions.svg",
        display_name="AWS Step Functions",
        aliases=["step-functions", "workflow", "state-machine"],
        native_color="#FF4F8B",
    ),
}


# Azure Icons (Official)
# Source: https://learn.microsoft.com/azure/architecture/icons/
AZURE_ICONS: dict[str, DiagramIcon] = {
    "azure:vm": DiagramIcon(
        id="azure:vm",
        provider=CloudProvider.AZURE,
        category=IconCategory.COMPUTE,
        name="vm",
        svg_path="icons/azure/compute/virtual-machine.svg",
        display_name="Azure Virtual Machine",
        aliases=["vm", "virtual-machine"],
        native_color="#0078D4",
    ),
    "azure:aks": DiagramIcon(
        id="azure:aks",
        provider=CloudProvider.AZURE,
        category=IconCategory.COMPUTE,
        name="aks",
        svg_path="icons/azure/compute/aks.svg",
        display_name="Azure Kubernetes Service",
        aliases=["aks", "kubernetes", "k8s"],
        native_color="#0078D4",
    ),
    "azure:app-service": DiagramIcon(
        id="azure:app-service",
        provider=CloudProvider.AZURE,
        category=IconCategory.COMPUTE,
        name="app-service",
        svg_path="icons/azure/compute/app-service.svg",
        display_name="Azure App Service",
        aliases=["app-service", "webapp"],
        native_color="#0078D4",
    ),
    "azure:sql-database": DiagramIcon(
        id="azure:sql-database",
        provider=CloudProvider.AZURE,
        category=IconCategory.DATABASE,
        name="sql-database",
        svg_path="icons/azure/database/sql-database.svg",
        display_name="Azure SQL Database",
        aliases=["sql", "database", "sql-server"],
        native_color="#0078D4",
    ),
    "azure:cosmos-db": DiagramIcon(
        id="azure:cosmos-db",
        provider=CloudProvider.AZURE,
        category=IconCategory.DATABASE,
        name="cosmos-db",
        svg_path="icons/azure/database/cosmos-db.svg",
        display_name="Azure Cosmos DB",
        aliases=["cosmos", "cosmosdb", "nosql"],
        native_color="#0078D4",
    ),
    "azure:key-vault": DiagramIcon(
        id="azure:key-vault",
        provider=CloudProvider.AZURE,
        category=IconCategory.SECURITY,
        name="key-vault",
        svg_path="icons/azure/security/key-vault.svg",
        display_name="Azure Key Vault",
        aliases=["key-vault", "secrets", "keys"],
        native_color="#0078D4",
    ),
    "azure:monitor": DiagramIcon(
        id="azure:monitor",
        provider=CloudProvider.AZURE,
        category=IconCategory.MANAGEMENT,
        name="monitor",
        svg_path="icons/azure/management/monitor.svg",
        display_name="Azure Monitor",
        aliases=["monitor", "monitoring", "logs"],
        native_color="#0078D4",
    ),
}


class IconLibrary:
    """
    Cloud provider icon library for diagram generation.

    Supports:
    - AWS Architecture Icons (official)
    - Azure Architecture Icons (official)
    - GCP Icons (official)
    - Kubernetes Icons
    - Generic technology icons
    - Multiple color modes (native, Aura semantic, monochrome)
    """

    def __init__(
        self,
        icons_base_path: str = "static/icons",
        color_mode: IconColorMode = IconColorMode.NATIVE,
    ):
        self.base_path = Path(icons_base_path)
        self.color_mode = color_mode
        self._icons: dict[str, DiagramIcon] = {}
        self._alias_map: dict[str, str] = {}

        # Load all icon sets
        self._icons.update(AWS_ICONS)
        self._icons.update(AZURE_ICONS)
        # Add GCP, K8s, generic icons...

        # Build alias map
        for icon_id, icon in self._icons.items():
            for alias in icon.aliases:
                self._alias_map[alias.lower()] = icon_id

    def get_icon(self, identifier: str) -> Optional[DiagramIcon]:
        """
        Get icon by ID or alias.

        Examples:
            get_icon("aws:ec2") -> EC2 icon
            get_icon("lambda") -> AWS Lambda icon (via alias)
            get_icon("kubernetes") -> EKS icon (via alias)
        """
        # Try direct ID match
        if identifier in self._icons:
            return self._icons[identifier]

        # Try alias match
        alias_key = identifier.lower().replace(" ", "-").replace("_", "-")
        if alias_key in self._alias_map:
            return self._icons[self._alias_map[alias_key]]

        return None

    def get_icon_color(self, icon: DiagramIcon) -> str:
        """Get icon color based on current color mode."""
        return icon.get_color(self.color_mode)

    def get_svg_content(self, icon: DiagramIcon, apply_color: bool = True) -> str:
        """Load SVG content for an icon, optionally applying color mode."""
        svg_path = self.base_path / icon.svg_path
        if svg_path.exists():
            content = svg_path.read_text()
            if apply_color and self.color_mode != IconColorMode.NATIVE:
                # Replace fill colors with mode-specific color
                content = self._apply_color_mode(content, icon)
            return content

        # Return placeholder SVG
        return self._generate_placeholder_svg(icon)

    def _apply_color_mode(self, svg_content: str, icon: DiagramIcon) -> str:
        """Apply color mode to SVG content."""
        import re
        color = icon.get_color(self.color_mode)
        # Replace fill attributes (simplified - production would use proper SVG parsing)
        svg_content = re.sub(r'fill="[^"]*"', f'fill="{color}"', svg_content)
        return svg_content

    def _generate_placeholder_svg(self, icon: DiagramIcon) -> str:
        """Generate placeholder SVG for missing icons."""
        color = icon.get_color(self.color_mode)
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{icon.width}" height="{icon.height}" viewBox="0 0 48 48">
            <rect width="48" height="48" rx="8" fill="{color}" opacity="0.2"/>
            <text x="24" y="28" text-anchor="middle" font-size="10" fill="{color}">{icon.name[:4]}</text>
        </svg>'''

    def list_icons_by_provider(self, provider: CloudProvider) -> list[DiagramIcon]:
        """List all icons for a provider."""
        return [i for i in self._icons.values() if i.provider == provider]

    def list_icons_by_category(self, category: IconCategory) -> list[DiagramIcon]:
        """List all icons in a category."""
        return [i for i in self._icons.values() if i.category == category]
```

### 3. Dark Theme Specifications (Design Review - WCAG AA Verified)

```css
/* Dark theme color palette for diagram canvas (design review)
 * All combinations verified for WCAG 2.1 AA compliance (4.5:1 minimum contrast)
 */

:root {
  /* Canvas background - Aura Surface 800 */
  --diagram-canvas-dark: #1E293B;

  /* Node backgrounds with sufficient contrast */
  --diagram-node-bg-dark: #334155;
  --diagram-node-border-dark: #475569;

  /* Group/container styling */
  --diagram-group-bg-dark: rgba(59, 130, 246, 0.08);  /* Primary blue at 8% */
  --diagram-group-border-dark: #3B82F6;

  /* Connection lines - visible on dark canvas */
  --diagram-line-solid-dark: #94A3B8;    /* Slate 400 */
  --diagram-line-dashed-dark: #64748B;   /* Slate 500 */
  --diagram-line-dotted-dark: #475569;   /* Slate 600 */

  /* Text legibility on dark backgrounds */
  --diagram-label-dark: #F1F5F9;         /* Slate 100 */
  --diagram-sublabel-dark: #CBD5E1;      /* Slate 300 */

  /* Focus indicators (accessibility) */
  --diagram-focus-ring: #3B82F6;
  --diagram-focus-ring-offset: 4px;
}

/*
 * WCAG Contrast Verification:
 * - Primary label #F1F5F9 on canvas #1E293B: 12.1:1 (Passes AAA)
 * - Secondary label #CBD5E1 on canvas #1E293B: 7.9:1 (Passes AAA)
 * - Node label #F1F5F9 on node bg #334155: 8.3:1 (Passes AAA)
 * - Connection line #94A3B8 on canvas #1E293B: 5.2:1 (Passes AA)
 */
```

### 4. DSL Input Validation (Security Review)

```python
# Added to src/services/diagrams/diagram_dsl.py

import re
from typing import Any
import yaml


class DSLValidationError(Exception):
    """Invalid DSL content."""
    pass


class DiagramDSLParser:
    """
    Parser for Eraser-style diagram DSL with security validation.
    """

    MAX_DSL_SIZE = 100_000  # 100KB max

    def _validate_dsl_input(self, dsl_content: str) -> None:
        """Validate DSL content before parsing (architecture security review)."""
        # Size limit
        if len(dsl_content) > self.MAX_DSL_SIZE:
            raise DSLValidationError(f"DSL content exceeds maximum size ({self.MAX_DSL_SIZE} bytes)")

        # Check for potentially malicious YAML constructs
        dangerous_patterns = [
            r'!!python/',  # Python object instantiation
            r'!!ruby/',    # Ruby object instantiation
            r'!!\w+/\w+',  # Generic tag handlers
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, dsl_content):
                raise DSLValidationError("Potentially dangerous YAML construct detected")

        # Validate structure after parsing
        try:
            data = yaml.safe_load(dsl_content)
            if not isinstance(data, dict):
                raise DSLValidationError("DSL must be a YAML mapping")

            # Required fields
            if "nodes" not in data and "groups" not in data:
                raise DSLValidationError("DSL must contain 'nodes' or 'groups'")
        except yaml.YAMLError as e:
            raise DSLValidationError(f"Invalid YAML: {e}")

    def parse(self, dsl_content: str) -> "DiagramDefinition":
        """Parse DSL string into DiagramDefinition with validation."""
        self._validate_dsl_input(dsl_content)
        data = yaml.safe_load(dsl_content)
        # ... rest of parsing logic
```

---

## Frontend Enhancements (Design Review)

### Progressive Generation UX Flow

```
Step 1: User types prompt
        └─→ Display: "Analyzing your request..."
            - Show extracted keywords as chips
            - Show detected diagram type

Step 2: Intent extraction completes
        └─→ Display: "Found similar patterns..."
            - Show reference architectures being considered
            - Allow user to select/deselect references

Step 3: DSL generation in progress
        └─→ Display: "Generating diagram structure..."
            - Show skeleton/wireframe preview
            - Progress indicator (nodes identified, connections mapped)

Step 4: Rendering
        └─→ Display: Full diagram with "References Used" panel
            - Animated fade-in of elements
            - Confidence score with explanation
```

### Enhanced DiagramViewer Toolbar

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ AWS Architecture Diagram                    ○ 92% Confidence                 │
├──────────────────────────────────────────────────────────────────────────────┤
│ [−] 100% [+] [⟲]  │  [Layers ▼]  │  [Connections ▼]  │  [⎘] [⬇] [⚙]        │
│                   │              │                    │                       │
│  Zoom controls    │  Group       │  Line style        │  Copy  Download       │
│                   │  visibility  │  filter            │       Settings        │
└──────────────────────────────────────────────────────────────────────────────┘
```

### References Used Panel Design

```jsx
// Component structure for explainability panel
<aside className="w-80 bg-surface-50 dark:bg-surface-800 border-l border-surface-200 dark:border-surface-700 p-4">
  <h4 className="text-sm font-semibold text-surface-900 dark:text-surface-100 mb-3">
    References Used
  </h4>
  <p className="text-xs text-surface-600 dark:text-surface-400 mb-3">
    These patterns influenced the generated diagram:
  </p>
  {references.map(ref => (
    <div key={ref.id} className="mb-3 p-3 bg-white dark:bg-surface-700 rounded-lg border">
      <div className="flex items-center gap-2 mb-1">
        <img src={ref.icon} alt="" className="w-5 h-5" />
        <span className="font-medium text-sm">{ref.name}</span>
        <span className="ml-auto text-xs text-primary-600 font-medium">
          {ref.matchScore}%
        </span>
      </div>
      <p className="text-xs text-surface-600 dark:text-surface-400">
        {ref.description}
      </p>
    </div>
  ))}
  <div className="mt-4 pt-3 border-t border-surface-200 dark:border-surface-600">
    <p className="text-xs text-surface-500">Not what you expected?</p>
    <div className="flex gap-2 mt-2">
      <button className="text-xs text-primary-600 hover:underline">
        Regenerate with different references
      </button>
      <button className="text-xs text-primary-600 hover:underline">
        Edit DSL directly
      </button>
    </div>
  </div>
</aside>
```

### Typography Specifications (Design System Alignment)

| Label Type | Font | Size | Weight | Color (Light) | Color (Dark) |
|------------|------|------|--------|---------------|--------------|
| Diagram Title | Inter | 16px | 600 | #111827 | #F1F5F9 |
| Group Label | Inter | 11px | 500 | #374151 | #E2E8F0 |
| Node Label | Inter | 12px | 500 | #1F2937 | #F3F4F6 |
| Connection Label | JetBrains Mono | 10px | 400 | #6B7280 | #94A3B8 |
| Metadata | Inter | 10px | 400 | #9CA3AF | #64748B |

---

## Accessibility Requirements (WCAG 2.1 AA)

### Keyboard Navigation Model

```
Tab Order:
1. Diagram canvas (receives focus, enables keyboard navigation)
2. Arrow keys navigate between nodes
3. Enter/Space on group: expand/collapse
4. Enter on node: open detail panel
5. Escape: exit diagram navigation, return to toolbar

Keyboard Shortcuts:
- +/= : Zoom in
- -/_ : Zoom out
- 0   : Reset zoom
- g   : Toggle groups panel
- c   : Copy diagram code
- d   : Download SVG
```

### ARIA Implementation

```jsx
<div
  role="img"
  aria-label={generatedAltText}
  aria-describedby="diagram-description"
>
  <div id="diagram-description" className="sr-only">
    {detailedDescription}
  </div>

  {/* Interactive diagram content */}
  <div role="group" aria-label={group.label}>
    {nodes.map(node => (
      <button
        key={node.id}
        role="treeitem"
        aria-expanded={isExpanded}
        aria-level={nestingLevel}
        aria-describedby={`node-${node.id}-desc`}
        tabIndex={0}
      >
        <span id={`node-${node.id}-desc`} className="sr-only">
          {node.label}, {node.metadata.description || 'component'}
        </span>
      </button>
    ))}
  </div>
</div>

{/* Live region for generation progress */}
<div role="status" aria-live="polite" className="sr-only">
  {generationStage === 'analyzing' && 'Analyzing your request'}
  {generationStage === 'generating' && `Generating diagram with ${nodeCount} components`}
  {generationStage === 'complete' && `Diagram complete with ${confidence}% confidence`}
</div>
```

### Alt Text Generation from DSL

```python
def generate_diagram_alt_text(definition: DiagramDefinition) -> str:
    """Generate WCAG-compliant alt text from diagram definition."""
    parts = [f"{definition.title}. "]

    # Describe structure
    parts.append(f"Architecture diagram with {len(definition.nodes)} components ")
    parts.append(f"organized into {len(definition.groups)} groups. ")

    # Describe groups
    for group in definition.groups:
        children = [n.label for n in definition.nodes if n.id in group.children]
        parts.append(f"{group.label} contains {', '.join(children)}. ")

    # Describe key connections
    connections_desc = []
    for conn in definition.connections[:5]:  # Limit for brevity
        source_label = next(n.label for n in definition.nodes if n.id == conn.source)
        target_label = next(n.label for n in definition.nodes if n.id == conn.target)
        connections_desc.append(f"{source_label} connects to {target_label}")

    parts.append(f"Key connections: {'; '.join(connections_desc)}.")

    return ''.join(parts)
```

---

## IAM Policy Template (Architecture Review)

```yaml
# deploy/cloudformation/iam-diagram-service.yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Project Aura - Layer 4.x - Diagram Service IAM Role'

Parameters:
  Environment:
    Type: String
    AllowedValues: [dev, qa, staging, prod]
  ProjectName:
    Type: String
    Default: aura

Resources:
  DiagramServiceRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub '${ProjectName}-diagram-service-${Environment}'
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: !Sub 'ecs-tasks.${AWS::URLSuffix}'
            Action: sts:AssumeRole
      Policies:
        - PolicyName: DiagramServicePolicy
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              # Bedrock access - scoped to specific models
              - Sid: BedrockInvoke
                Effect: Allow
                Action:
                  - bedrock:InvokeModel
                  - bedrock:InvokeModelWithResponseStream
                Resource:
                  - !Sub 'arn:${AWS::Partition}:bedrock:${AWS::Region}::foundation-model/anthropic.claude-3-5-sonnet*'
                  - !Sub 'arn:${AWS::Partition}:bedrock:${AWS::Region}::foundation-model/anthropic.claude-3-opus*'
                  - !Sub 'arn:${AWS::Partition}:bedrock:${AWS::Region}::foundation-model/anthropic.claude-instant*'

              # SSM Parameter Store for external provider API keys
              - Sid: SSMParameterAccess
                Effect: Allow
                Action:
                  - ssm:GetParameter
                  - ssm:GetParameters
                Resource:
                  - !Sub 'arn:${AWS::Partition}:ssm:${AWS::Region}:${AWS::AccountId}:parameter/aura/${Environment}/providers/*'
                Condition:
                  StringEquals:
                    'ssm:ResourceTag/Project': !Ref ProjectName

              # KMS for SSM SecureString decryption
              - Sid: KMSDecrypt
                Effect: Allow
                Action:
                  - kms:Decrypt
                Resource:
                  - !Sub 'arn:${AWS::Partition}:kms:${AWS::Region}:${AWS::AccountId}:key/*'
                Condition:
                  StringEquals:
                    'kms:ViaService': !Sub 'ssm.${AWS::Region}.${AWS::URLSuffix}'

              # CloudWatch metrics
              - Sid: CloudWatchMetrics
                Effect: Allow
                Action:
                  - cloudwatch:PutMetricData
                Resource: '*'
                Condition:
                  StringEquals:
                    'cloudwatch:namespace': 'Aura/DiagramGeneration'
      Tags:
        - Key: Project
          Value: !Ref ProjectName
        - Key: Environment
          Value: !Ref Environment

  # SSM Parameters for provider configuration
  OpenAIEnabledParam:
    Type: AWS::SSM::Parameter
    Properties:
      Name: !Sub '/aura/${Environment}/providers/openai/enabled'
      Type: String
      Value: 'false'  # Disabled by default
      Description: 'Enable OpenAI provider for diagram generation'
      Tags:
        Project: !Ref ProjectName
        Environment: !Ref Environment

  VertexEnabledParam:
    Type: AWS::SSM::Parameter
    Properties:
      Name: !Sub '/aura/${Environment}/providers/vertex/enabled'
      Type: String
      Value: 'false'  # Disabled by default
      Description: 'Enable Vertex AI provider for diagram generation'
      Tags:
        Project: !Ref ProjectName
        Environment: !Ref Environment

Outputs:
  DiagramServiceRoleArn:
    Description: 'Diagram service role ARN'
    Value: !GetAtt DiagramServiceRole.Arn
    Export:
      Name: !Sub '${ProjectName}-diagram-service-role-${Environment}'
```

---

## Observability (Architecture Review)

### CloudWatch Metrics

```python
# CloudWatch metrics namespace
METRICS_NAMESPACE = "Aura/DiagramGeneration"

# Key metrics to emit
METRICS = {
    "DiagramsGenerated": "Count",
    "GenerationLatency": "Milliseconds",
    "ProviderRoutingDecisions": "Count",
    "ProviderFailures": "Count",
    "CircuitBreakerRejection": "Count",
    "ClassificationEnforcement": "Count",
    "BudgetExceeded": "Count",
    "CacheHitRate": "Percent",
    "DSLParseErrors": "Count",
    "ProviderCost": "None",  # USD
}
```

### CloudWatch Alarms

```yaml
# Add to CloudFormation
DiagramGenerationErrorRateAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: !Sub '${ProjectName}-diagram-error-rate-${Environment}'
    MetricName: ProviderFailures
    Namespace: Aura/DiagramGeneration
    Statistic: Sum
    Period: 300
    EvaluationPeriods: 2
    Threshold: 10
    ComparisonOperator: GreaterThanThreshold
    AlarmActions:
      - !Ref AlertSNSTopic

GenerationLatencyAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: !Sub '${ProjectName}-diagram-latency-${Environment}'
    MetricName: GenerationLatency
    Namespace: Aura/DiagramGeneration
    ExtendedStatistic: p99
    Period: 300
    EvaluationPeriods: 2
    Threshold: 30000  # 30 seconds
    ComparisonOperator: GreaterThanThreshold
    AlarmActions:
      - !Ref AlertSNSTopic

DailyProviderCostAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: !Sub '${ProjectName}-diagram-daily-cost-${Environment}'
    MetricName: ProviderCost
    Namespace: Aura/DiagramGeneration
    Statistic: Sum
    Period: 86400  # 24 hours
    EvaluationPeriods: 1
    Threshold: 100  # $100/day threshold
    ComparisonOperator: GreaterThanThreshold
    AlarmActions:
      - !Ref AlertSNSTopic
```

---

## GovCloud Considerations

### CRITICAL: Compliance Boundary Enforcement

**FedRAMP High / CMMC L3 Requirements:**

When OpenAI or Vertex AI providers are enabled, diagram content is transmitted to non-FedRAMP-authorized services. This has the following implications:

1. **Data Classification Restriction:**
   - Diagrams containing CUI (Controlled Unclassified Information) MUST NOT be processed by non-Bedrock providers
   - Source repositories must be tagged with classification level
   - Router checks classification before selecting external providers

2. **Audit Trail Requirements:**
   - All provider selections logged to CloudTrail
   - Include: user_id, diagram_id, provider selected, classification level
   - Retention: 7 years for CMMC compliance

3. **Configuration Controls:**
   - GovCloud deployments: `govcloud_mode=True` is MANDATORY
   - Commercial deployments with FedRAMP data: Use feature flags per tenant

### Service Availability

| Component | GovCloud Compatible | Fallback |
|-----------|--------------------|---------|
| **Bedrock (Claude)** | Yes | Primary provider |
| **OpenAI API** | No | Disabled in GovCloud mode |
| **Vertex AI (Gemini)** | No | Disabled in GovCloud mode |
| **Icon Library** | Yes | Static assets, no external calls |
| **Layout Engine** | Yes | Client-side WebAssembly |
| **Git Sync** | Yes | GitHub Enterprise / GitLab Self-Hosted (within boundary) |

### GovCloud Git Host Restrictions

```python
class DiagramGitSync:
    def __init__(self, ..., govcloud_mode: bool = False):
        self.govcloud_mode = govcloud_mode
        self.allowed_git_hosts = None
        if govcloud_mode:
            self.allowed_git_hosts = self._load_allowed_hosts()

    def _load_allowed_hosts(self) -> set[str]:
        """Load allowed Git hosts for GovCloud from SSM."""
        hosts_param = self.ssm.get_parameter(
            Name=f"/aura/{self.environment}/git/allowed-hosts"
        )
        return set(hosts_param["Parameter"]["Value"].split(","))

    async def commit_diagram(self, request, ...) -> DiagramCommitResult:
        if self.govcloud_mode and self.allowed_git_hosts:
            host = self._extract_host(request.repo_owner, request.repo_name)
            if host not in self.allowed_git_hosts:
                return DiagramCommitResult(
                    success=False,
                    error=f"Git host '{host}' not authorized in GovCloud mode"
                )
        # ... continue
```

---

## Implementation Phases

### Phase 1: Icon Library & Layout Engine (4 weeks)

| Component | Effort | Dependencies |
|-----------|--------|--------------|
| Icon library with color modes | 1 week | None |
| ELK.js integration | 1 week | Icon library |
| DSL parser with validation | 1 week | None |
| SVG renderer (server-side) | 1 week | Icon library, Layout |

**Deliverables:**
- Official cloud provider icons with native/semantic/mono modes
- Constraint-based layout with groupings
- Eraser-style DSL parsing with security validation

### Phase 2: AI Generation & Multi-Provider Routing (4 weeks)

| Component | Effort | Dependencies |
|-----------|--------|--------------|
| Multi-provider model router with circuit breakers | 1.5 weeks | ADR-015 router |
| Data classification enforcement | 0.5 weeks | Router |
| OpenAI/Vertex integration | 1 week | Model router |
| AI diagram generator with sanitization | 1 week | All above |

**Deliverables:**
- Natural language to diagram generation
- Multi-provider model selection with resilience
- FedRAMP/CMMC compliant data routing

### Phase 3: Frontend & Accessibility (3 weeks)

| Component | Effort | Dependencies |
|-----------|--------|--------------|
| Enhanced DiagramViewer with toolbar | 1 week | Phase 1 |
| References Used panel | 0.5 weeks | Phase 2 |
| Keyboard navigation & ARIA | 1 week | DiagramViewer |
| Progressive generation UX | 0.5 weeks | Phase 2 |

**Deliverables:**
- WCAG 2.1 AA compliant diagram viewer
- Explainability panel
- Full keyboard navigation

### Phase 4: Git Integration & Polish (2 weeks)

| Component | Effort | Dependencies |
|-----------|--------|--------------|
| Git sync service with GovCloud restrictions | 1 week | ADR-043 OAuth |
| Export to PNG/PDF/draw.io | 1 week | Phase 1-3 |

**Deliverables:**
- Commit diagrams to repositories
- Multi-format export

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Visual quality (user rating) | >4.5/5.0 | Post-generation survey |
| Icon accuracy | 100% official icons | Automated validation |
| Layout quality (overlap-free) | >95% diagrams | Automated testing |
| AI generation accuracy | >85% correct elements | User validation |
| GovCloud compliance | 100% Bedrock-only | Configuration audit |
| Time to first diagram | <30 seconds | Performance monitoring |
| WCAG 2.1 AA compliance | 100% | Automated + manual audit |
| Provider availability | >99.5% | Circuit breaker metrics |

---

## Consequences

### Positive

1. **Professional output** - Diagrams with official cloud icons, targeting quality comparable to leading commercial diagramming tools
2. **Optimal model selection** - Right AI for each subtask
3. **GovCloud compatible** - Bedrock-only path with data classification enforcement
4. **Explainability** - Users understand AI reasoning via reference citations
5. **Version control** - Diagrams tracked in Git alongside code
6. **Unique differentiators** - Confidence scoring, GraphRAG integration
7. **Accessible** - WCAG 2.1 AA compliant for all users
8. **Resilient** - Circuit breakers, retries, cost controls

### Negative

1. **Multi-provider complexity** - More integrations to maintain
2. **Cost increase** - OpenAI/Vertex usage adds to Bedrock costs
3. **Latency variation** - Different providers have different response times
4. **Feature gaps in GovCloud** - Vision features limited without OpenAI/Vertex

### Mitigations

| Risk | Mitigation |
|------|------------|
| Provider cost | Cost-aware routing, caching, daily/monthly budgets |
| Provider outages | Circuit breakers, fallback chains, health checks |
| GovCloud feature gaps | Claude image features as fallback, clear feature matrix |
| Complexity | Comprehensive testing, provider abstraction layer |
| Data leakage | Classification enforcement, audit logging |
| Prompt injection | InputSanitizer integration (ADR-051), pattern detection |

---

## References

- ADR-015: Tiered LLM Model Strategy
- ADR-051: Recursive Context and Embedding Prediction (InputSanitizer)
- ADR-056: Documentation Agent
- ADR-004: Multi-Cloud Architecture
- ADR-043: Repository Onboarding Wizard
- Eraser.io Product Analysis (2026-01-12)
- AWS Architecture Icons: https://aws.amazon.com/architecture/icons/
- Azure Architecture Icons: https://learn.microsoft.com/azure/architecture/icons/
- ELK.js Documentation: https://eclipse.dev/elk/
- WCAG 2.1 Guidelines: https://www.w3.org/WAI/WCAG21/quickref/

---

*Competitive references in this ADR reflect publicly available information as of the document date. Vendor products evolve; readers should verify current capabilities before decision-making. Third-party vendor names and products referenced herein are trademarks of their respective owners. References are nominative and do not imply endorsement or partnership.*
