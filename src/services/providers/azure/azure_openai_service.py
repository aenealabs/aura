"""
Project Aura - Azure OpenAI Service

Azure OpenAI implementation of LLMService.
Provides LLM capabilities for Azure Government deployments.

See ADR-004: Cloud Abstraction Layer for Multi-Cloud Deployment
"""

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from src.abstractions.llm_service import (
    LLMRequest,
    LLMResponse,
    LLMService,
    ModelConfig,
    ModelFamily,
    UsageSummary,
)

logger = logging.getLogger(__name__)

# Optional Azure dependencies
try:
    from openai import AzureOpenAI

    AZURE_OPENAI_AVAILABLE = True
except ImportError:
    AZURE_OPENAI_AVAILABLE = False
    logger.warning("Azure OpenAI SDK not available - using mock mode")


class AzureOpenAIService(LLMService):
    """
    Azure OpenAI implementation for LLM operations.

    Compatible with Azure Government regions.
    """

    def __init__(
        self,
        endpoint: str | None = None,
        deployment_name: str = "gpt-4",
        api_key: str | None = None,
        api_version: str = "2024-02-01",
    ):
        self.endpoint = endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT")
        self.deployment_name = deployment_name
        self.api_key = api_key or os.environ.get("AZURE_OPENAI_KEY")
        self.api_version = api_version

        self._client: AzureOpenAI | None = None
        self._initialized = False

        # Usage tracking (in-memory for now)
        self._usage_records: list[dict[str, Any]] = []

    @property
    def is_mock_mode(self) -> bool:
        """Check if running in mock mode."""
        return not AZURE_OPENAI_AVAILABLE or not self.endpoint

    async def initialize(self) -> bool:
        """Initialize Azure OpenAI client."""
        if self.is_mock_mode:
            logger.info("Azure OpenAI running in mock mode")
            self._initialized = True
            return True

        if not self.endpoint:
            logger.error("Azure OpenAI endpoint not configured")
            return False

        if not self.api_key:
            logger.error("Azure OpenAI API key not configured")
            return False

        try:
            self._client = AzureOpenAI(
                azure_endpoint=self.endpoint,
                api_key=self.api_key,
                api_version=self.api_version,
            )
            self._initialized = True
            logger.info(f"Connected to Azure OpenAI: {self.deployment_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Azure OpenAI: {e}")
            return False

    async def shutdown(self) -> None:
        """Clean up."""
        self._initialized = False
        self._client = None

    def _record_usage(self, input_tokens: int, output_tokens: int, model: str) -> None:
        """Record usage for cost tracking."""
        self._usage_records.append(
            {
                "timestamp": datetime.now(timezone.utc),
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
        )

    async def invoke(
        self,
        request: LLMRequest,
        model_config: ModelConfig | None = None,
    ) -> LLMResponse:
        """Invoke Azure OpenAI."""
        start_time = time.time()

        if self.is_mock_mode:
            # Mock response
            return LLMResponse(
                content=f"Mock response to: {request.prompt[:50]}...",
                model_id=self.deployment_name,
                input_tokens=len(request.prompt.split()),
                output_tokens=10,
                latency_ms=(time.time() - start_time) * 1000,
                finish_reason="stop",
            )

        if self._client is None:
            raise RuntimeError("Azure OpenAI client not initialized")

        messages: list[dict[str, Any]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})

        if request.messages:
            messages.extend(request.messages)
        else:
            messages.append({"role": "user", "content": request.prompt})

        response = self._client.chat.completions.create(
            model=self.deployment_name,
            messages=messages,  # type: ignore[arg-type]
            max_tokens=request.max_tokens or 4096,
            temperature=request.temperature or 0.7,
            top_p=request.top_p or 0.9,
            stop=request.stop_sequences,
        )

        choice = response.choices[0]
        usage = response.usage

        if usage is None:
            raise RuntimeError("Azure OpenAI response missing usage information")

        self._record_usage(
            usage.prompt_tokens, usage.completion_tokens, self.deployment_name
        )

        return LLMResponse(
            content=choice.message.content or "",
            model_id=self.deployment_name,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            latency_ms=(time.time() - start_time) * 1000,
            finish_reason=str(choice.finish_reason) if choice.finish_reason else "stop",
            metadata=request.metadata,
        )

    async def invoke_streaming(  # type: ignore[override,misc]
        self,
        request: LLMRequest,
        model_config: ModelConfig | None = None,
    ) -> AsyncIterator[str]:
        """Streaming invoke."""
        if self.is_mock_mode:
            yield "Mock "
            yield "streaming "
            yield "response"
            return

        if self._client is None:
            raise RuntimeError("Azure OpenAI client not initialized")

        messages: list[dict[str, Any]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        stream = self._client.chat.completions.create(
            model=self.deployment_name,
            messages=messages,  # type: ignore[arg-type]
            max_tokens=request.max_tokens or 4096,
            temperature=request.temperature or 0.7,
            stream=True,
        )

        for chunk in stream:  # type: ignore[union-attr]
            if chunk.choices and chunk.choices[0].delta.content:  # type: ignore[union-attr]
                yield chunk.choices[0].delta.content  # type: ignore[union-attr]

    async def generate_code(
        self,
        prompt: str,
        language: str,
        context: str | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Generate code."""
        system_prompt = f"""You are an expert {language} programmer.
Generate clean, well-documented, production-ready code.
Follow best practices and include error handling."""

        full_prompt = prompt
        if context:
            full_prompt = f"Context:\n{context}\n\nTask:\n{prompt}"

        request = LLMRequest(
            prompt=full_prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
        )
        return await self.invoke(request)

    async def analyze_code(
        self,
        code: str,
        language: str,
        analysis_type: str,
    ) -> LLMResponse:
        """Analyze code."""
        analysis_prompts = {
            "security": "Analyze this code for security vulnerabilities.",
            "quality": "Review this code for quality issues and code smells.",
            "performance": "Analyze this code for performance issues.",
            "bugs": "Review this code for potential bugs.",
        }

        system_prompt = f"""You are an expert code reviewer specializing in {language}.
{analysis_prompts.get(analysis_type, analysis_prompts['quality'])}
Provide specific, actionable recommendations."""

        request = LLMRequest(
            prompt=f"```{language}\n{code}\n```",
            system_prompt=system_prompt,
            max_tokens=4096,
        )
        return await self.invoke(request)

    async def generate_embedding(
        self,
        text: str,
        model_id: str | None = None,
    ) -> list[float]:
        """Generate embedding using Azure OpenAI."""
        if self.is_mock_mode:
            # Return mock embedding
            return [0.0] * 1536

        if self._client is None:
            raise RuntimeError("Azure OpenAI client not initialized")

        embedding_model = model_id or "text-embedding-ada-002"
        response = self._client.embeddings.create(
            model=embedding_model,
            input=text,
        )
        return list(response.data[0].embedding)

    async def generate_embeddings_batch(
        self,
        texts: list[str],
        model_id: str | None = None,
    ) -> list[list[float]]:
        """Generate embeddings batch."""
        if self.is_mock_mode:
            return [[0.0] * 1536 for _ in texts]

        if self._client is None:
            raise RuntimeError("Azure OpenAI client not initialized")

        embedding_model = model_id or "text-embedding-ada-002"
        response = self._client.embeddings.create(
            model=embedding_model,
            input=texts,
        )
        return [list(item.embedding) for item in response.data]

    async def get_usage_summary(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> UsageSummary:
        """Get usage summary."""
        filtered = [
            r for r in self._usage_records if start_date <= r["timestamp"] <= end_date
        ]

        total_input = sum(r["input_tokens"] for r in filtered)
        total_output = sum(r["output_tokens"] for r in filtered)

        # GPT-4 pricing estimates
        input_cost = (total_input / 1000) * 0.03
        output_cost = (total_output / 1000) * 0.06

        return UsageSummary(
            total_requests=len(filtered),
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_cost_usd=input_cost + output_cost,
            period_start=start_date,
            period_end=end_date,
        )

    async def get_daily_spend(self) -> float:
        """Get today's spend."""
        today = datetime.now(timezone.utc).date()
        daily_records = [
            r for r in self._usage_records if r["timestamp"].date() == today
        ]

        input_tokens = sum(int(r["input_tokens"]) for r in daily_records)
        output_tokens = sum(int(r["output_tokens"]) for r in daily_records)

        return float((input_tokens / 1000) * 0.03 + (output_tokens / 1000) * 0.06)

    async def get_monthly_spend(self) -> float:
        """Get month's spend."""
        now = datetime.now(timezone.utc)
        monthly_records = [
            r
            for r in self._usage_records
            if r["timestamp"].year == now.year and r["timestamp"].month == now.month
        ]

        input_tokens = sum(int(r["input_tokens"]) for r in monthly_records)
        output_tokens = sum(int(r["output_tokens"]) for r in monthly_records)

        return float((input_tokens / 1000) * 0.03 + (output_tokens / 1000) * 0.06)

    async def check_budget(
        self, daily_limit: float, monthly_limit: float
    ) -> dict[str, Any]:
        """Check budget status."""
        daily = await self.get_daily_spend()
        monthly = await self.get_monthly_spend()

        return {
            "daily_spend": daily,
            "daily_limit": daily_limit,
            "daily_remaining": max(0, daily_limit - daily),
            "daily_exceeded": daily > daily_limit,
            "monthly_spend": monthly,
            "monthly_limit": monthly_limit,
            "monthly_remaining": max(0, monthly_limit - monthly),
            "monthly_exceeded": monthly > monthly_limit,
        }

    async def list_available_models(self) -> list[ModelConfig]:
        """List available models."""
        return [
            ModelConfig(
                model_id="gpt-4",
                family=ModelFamily.GPT,
                max_tokens=8192,
                input_cost_per_1k=0.03,
                output_cost_per_1k=0.06,
            ),
            ModelConfig(
                model_id="gpt-4-turbo",
                family=ModelFamily.GPT,
                max_tokens=128000,
                input_cost_per_1k=0.01,
                output_cost_per_1k=0.03,
            ),
            ModelConfig(
                model_id="gpt-35-turbo",
                family=ModelFamily.GPT,
                max_tokens=16385,
                input_cost_per_1k=0.0005,
                output_cost_per_1k=0.0015,
            ),
        ]

    async def get_model_config(self, model_id: str) -> ModelConfig | None:
        """Get model configuration."""
        models = await self.list_available_models()
        for model in models:
            if model.model_id == model_id:
                return model
        return None

    async def health_check(self) -> dict[str, Any]:
        """Health check."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "mode": "mock" if self.is_mock_mode else "azure",
            "endpoint": self.endpoint,
            "deployment": self.deployment_name,
        }
