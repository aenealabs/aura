"""
Project Aura - Bedrock LLM Adapter

Adapter that wraps BedrockLLMService to implement LLMService interface.

See ADR-004: Cloud Abstraction Layer for Multi-Cloud Deployment
"""

import logging
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from src.abstractions.llm_service import (
    LLMRequest,
    LLMResponse,
    LLMService,
    ModelConfig,
    ModelFamily,
    UsageSummary,
)
from src.services.bedrock_llm_service import BedrockLLMService, BedrockMode

logger = logging.getLogger(__name__)


class BedrockLLMAdapter(LLMService):
    """
    Adapter for AWS Bedrock that implements LLMService interface.

    Wraps the existing BedrockLLMService to provide a cloud-agnostic API.
    """

    def __init__(self, region: str = "us-east-1") -> None:
        self.region = region
        self._service: BedrockLLMService | None = None
        self._initialized = False

    def _get_service(self) -> BedrockLLMService:
        """Get or create the underlying Bedrock service."""
        if self._service is None:
            self._service = BedrockLLMService(mode=BedrockMode.AWS)
        return self._service

    async def initialize(self) -> bool:
        """Initialize the Bedrock service."""
        try:
            service = self._get_service()
            self._initialized = True
            logger.info(f"Bedrock adapter initialized (mode: {service.mode.value})")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock: {e}")
            return False

    async def shutdown(self) -> None:
        """Clean up resources."""
        self._initialized = False
        self._service = None

    async def invoke(
        self,
        request: LLMRequest,
        model_config: ModelConfig | None = None,
    ) -> LLMResponse:
        """Invoke Bedrock with a request."""
        import time

        start_time = time.time()

        service = self._get_service()

        # Build the prompt with system message if provided
        full_prompt = request.prompt
        if request.system_prompt:
            full_prompt = f"{request.system_prompt}\n\n{request.prompt}"

        # BedrockLLMService.invoke_model requires 'agent' parameter
        response = service.invoke_model(
            prompt=full_prompt,
            agent="BedrockAdapter",
            system_prompt=request.system_prompt,
            max_tokens=request.max_tokens or 4096,
            temperature=request.temperature or 0.7,
        )

        latency_ms = (time.time() - start_time) * 1000

        # Extract content from response dict (BedrockLLMService returns dict with 'response' key)
        content = str(response.get("response", ""))
        model_id = str(
            response.get("model_id", "anthropic.claude-3-5-sonnet-20241022-v2:0")
        )
        input_tokens = int(response.get("input_tokens", 0))
        output_tokens = int(response.get("output_tokens", 0))
        finish_reason = str(response.get("stop_reason", "end_turn"))

        return LLMResponse(
            content=content,
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            finish_reason=finish_reason,
            metadata=request.metadata,
        )

    async def invoke_streaming(  # type: ignore[override,misc]
        self,
        request: LLMRequest,
        model_config: ModelConfig | None = None,
    ) -> AsyncIterator[str]:
        """
        Streaming invoke (yields chunks).

        Note: BedrockLLMService doesn't support native streaming yet.
        This implementation yields the full response as a single chunk.
        """
        service = self._get_service()

        full_prompt = request.prompt
        if request.system_prompt:
            full_prompt = f"{request.system_prompt}\n\n{request.prompt}"

        # Use async generate method since BedrockLLMService doesn't have streaming
        response_text = await service.generate(
            prompt=full_prompt,
            agent="BedrockAdapter",
            system_prompt=request.system_prompt,
            max_tokens=request.max_tokens or 4096,
        )

        # Yield full response as single chunk (not true streaming)
        yield response_text

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
        """Analyze code for issues."""
        analysis_prompts = {
            "security": "Analyze this code for security vulnerabilities. Identify OWASP Top 10 issues, injection flaws, and authentication/authorization problems.",
            "quality": "Review this code for quality issues. Check for clean code violations, SOLID principle violations, and code smells.",
            "performance": "Analyze this code for performance issues. Identify bottlenecks, inefficient algorithms, and resource leaks.",
            "bugs": "Review this code for potential bugs. Look for edge cases, null pointer issues, and logic errors.",
        }

        system_prompt = f"""You are an expert code reviewer specializing in {language}.
{analysis_prompts.get(analysis_type, analysis_prompts['quality'])}
Provide specific, actionable recommendations with code examples."""

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
        """
        Generate embedding using Titan.

        Note: BedrockLLMService doesn't have embedding support yet.
        This is a placeholder that raises NotImplementedError.
        """
        raise NotImplementedError(
            "Embedding generation not yet implemented in BedrockLLMService"
        )

    async def generate_embeddings_batch(
        self,
        texts: list[str],
        model_id: str | None = None,
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Note: BedrockLLMService doesn't have embedding support yet.
        This is a placeholder that raises NotImplementedError.
        """
        raise NotImplementedError(
            "Batch embedding generation not yet implemented in BedrockLLMService"
        )

    async def get_usage_summary(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> UsageSummary:
        """Get usage summary."""
        service = self._get_service()
        # BedrockLLMService.get_spend_summary() doesn't take parameters
        summary = service.get_spend_summary()

        # Extract values with proper type casting
        total_requests = int(summary.get("total_requests", 0))
        daily_spend = float(summary.get("daily_spend", 0.0))
        monthly_spend = float(summary.get("monthly_spend", 0.0))

        return UsageSummary(
            total_requests=total_requests,
            total_input_tokens=0,  # Not available in BedrockLLMService summary
            total_output_tokens=0,  # Not available in BedrockLLMService summary
            total_cost_usd=daily_spend + monthly_spend,  # Approximate total cost
            period_start=start_date,
            period_end=end_date,
            by_model={},  # Not available in BedrockLLMService summary
        )

    async def get_daily_spend(self) -> float:
        """Get today's spend."""
        service = self._get_service()
        # Access the public daily_spend attribute
        return float(service.daily_spend)

    async def get_monthly_spend(self) -> float:
        """Get month's spend."""
        service = self._get_service()
        # Access the public monthly_spend attribute
        return float(service.monthly_spend)

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
                model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
                family=ModelFamily.CLAUDE,
                max_tokens=8192,
                input_cost_per_1k=0.003,
                output_cost_per_1k=0.015,
            ),
            ModelConfig(
                model_id="anthropic.claude-3-haiku-20240307-v1:0",
                family=ModelFamily.CLAUDE,
                max_tokens=4096,
                input_cost_per_1k=0.00025,
                output_cost_per_1k=0.00125,
            ),
            ModelConfig(
                model_id="amazon.titan-text-express-v1",
                family=ModelFamily.TITAN,
                max_tokens=8192,
                input_cost_per_1k=0.0002,
                output_cost_per_1k=0.0006,
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
        service = self._get_service()
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "mode": service.mode.value,
            "region": self.region,
        }
