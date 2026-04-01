"""
Project Aura - LLM Service Abstraction

Abstract interface for Large Language Model operations.
Implementations: AWS Bedrock (Claude), Azure OpenAI (GPT-4)

See ADR-004: Cloud Abstraction Layer for Multi-Cloud Deployment
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator


class ModelFamily(Enum):
    """Supported LLM model families."""

    CLAUDE = "claude"  # Anthropic Claude (via Bedrock or direct)
    GPT = "gpt"  # OpenAI GPT (via Azure OpenAI)
    LLAMA = "llama"  # Meta LLaMA (via Bedrock)
    MISTRAL = "mistral"  # Mistral AI (via Bedrock)
    TITAN = "titan"  # Amazon Titan


@dataclass
class ModelConfig:
    """Configuration for an LLM model."""

    model_id: str  # e.g., "anthropic.claude-3-5-sonnet-20241022-v2:0"
    family: ModelFamily
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 0.9
    stop_sequences: list[str] = field(default_factory=list)

    # Cost tracking
    input_cost_per_1k: float = 0.003  # Cost per 1000 input tokens
    output_cost_per_1k: float = 0.015  # Cost per 1000 output tokens


@dataclass
class LLMRequest:
    """Request to an LLM model."""

    prompt: str
    system_prompt: str | None = None
    messages: list[dict[str, str]] | None = None  # For chat-style requests
    max_tokens: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    stop_sequences: list[str] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert request to dictionary."""
        return {
            "prompt": self.prompt,
            "system_prompt": self.system_prompt,
            "messages": self.messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "stop_sequences": self.stop_sequences,
            "metadata": self.metadata,
        }


@dataclass
class LLMResponse:
    """Response from an LLM model."""

    content: str
    model_id: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    finish_reason: str  # "end_turn", "max_tokens", "stop_sequence"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> dict[str, Any]:
        """Convert response to dictionary."""
        return {
            "content": self.content,
            "model_id": self.model_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": self.latency_ms,
            "finish_reason": self.finish_reason,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class UsageSummary:
    """Summary of LLM usage and costs."""

    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    period_start: datetime
    period_end: datetime
    by_model: dict[str, dict[str, Any]] = field(default_factory=dict)


class LLMService(ABC):
    """
    Abstract interface for LLM operations.

    Implementations:
    - AWS: BedrockLLMService (Claude, LLaMA, Mistral, Titan)
    - Azure: AzureOpenAIService (GPT-4, GPT-4o)
    """

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the LLM service and validate credentials."""

    @abstractmethod
    async def shutdown(self) -> None:
        """Clean up resources."""

    # Model Operations
    @abstractmethod
    async def invoke(
        self,
        request: LLMRequest,
        model_config: ModelConfig | None = None,
    ) -> LLMResponse:
        """
        Invoke the LLM with a request.

        Args:
            request: The LLM request
            model_config: Optional model configuration override

        Returns:
            The LLM response
        """

    @abstractmethod
    async def invoke_streaming(
        self,
        request: LLMRequest,
        model_config: ModelConfig | None = None,
    ) -> AsyncIterator[str]:
        """
        Invoke the LLM with streaming response.

        Args:
            request: The LLM request
            model_config: Optional model configuration override

        Yields:
            Response text chunks as they arrive
        """

    @abstractmethod
    async def generate_code(
        self,
        prompt: str,
        language: str,
        context: str | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """
        Generate code based on a prompt.

        Args:
            prompt: Code generation prompt
            language: Target programming language
            context: Optional code context
            max_tokens: Maximum tokens to generate

        Returns:
            LLM response with generated code
        """

    @abstractmethod
    async def analyze_code(
        self,
        code: str,
        language: str,
        analysis_type: str,  # "security", "quality", "performance", "bugs"
    ) -> LLMResponse:
        """
        Analyze code for specific issues.

        Args:
            code: Code to analyze
            language: Programming language
            analysis_type: Type of analysis to perform

        Returns:
            LLM response with analysis results
        """

    # Embeddings
    @abstractmethod
    async def generate_embedding(
        self,
        text: str,
        model_id: str | None = None,
    ) -> list[float]:
        """
        Generate embedding vector for text.

        Args:
            text: Text to embed
            model_id: Optional embedding model ID

        Returns:
            Embedding vector
        """

    @abstractmethod
    async def generate_embeddings_batch(
        self,
        texts: list[str],
        model_id: str | None = None,
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            model_id: Optional embedding model ID

        Returns:
            List of embedding vectors
        """

    # Cost and Usage Tracking
    @abstractmethod
    async def get_usage_summary(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> UsageSummary:
        """
        Get usage summary for a time period.

        Args:
            start_date: Start of period
            end_date: End of period

        Returns:
            Usage summary with costs
        """

    @abstractmethod
    async def get_daily_spend(self) -> float:
        """Get today's spend in USD."""

    @abstractmethod
    async def get_monthly_spend(self) -> float:
        """Get current month's spend in USD."""

    @abstractmethod
    async def check_budget(
        self, daily_limit: float, monthly_limit: float
    ) -> dict[str, Any]:
        """
        Check if spending is within budget limits.

        Args:
            daily_limit: Daily budget limit in USD
            monthly_limit: Monthly budget limit in USD

        Returns:
            Budget status with remaining amounts
        """

    # Model Management
    @abstractmethod
    async def list_available_models(self) -> list[ModelConfig]:
        """
        List available LLM models.

        Returns:
            List of available model configurations
        """

    @abstractmethod
    async def get_model_config(self, model_id: str) -> ModelConfig | None:
        """
        Get configuration for a specific model.

        Args:
            model_id: Model identifier

        Returns:
            Model configuration if found
        """

    # Health
    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """
        Perform health check on the LLM service.

        Returns:
            Health status including availability, latency, etc.
        """
