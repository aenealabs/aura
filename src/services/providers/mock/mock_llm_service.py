"""
Project Aura - Mock LLM Service

In-memory mock implementation of LLMService for testing.
"""

import logging
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


class MockLLMService(LLMService):
    """Mock LLM service for testing."""

    def __init__(self) -> None:
        self._initialized = False
        self._usage_records: list[dict[str, Any]] = []

    async def initialize(self) -> bool:
        self._initialized = True
        logger.info("MockLLMService initialized")
        return True

    async def shutdown(self) -> None:
        self._initialized = False

    async def invoke(
        self,
        request: LLMRequest,
        model_config: ModelConfig | None = None,
    ) -> LLMResponse:
        input_tokens = len(request.prompt.split())
        output_tokens = 20

        self._usage_records.append(
            {
                "timestamp": datetime.now(timezone.utc),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
        )

        return LLMResponse(
            content=f"Mock response to: {request.prompt[:100]}...",
            model_id="mock-model",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=50.0,
            finish_reason="stop",
            metadata=request.metadata,
        )

    async def invoke_streaming(  # type: ignore[override, misc]
        self,
        request: LLMRequest,
        model_config: ModelConfig | None = None,
    ) -> AsyncIterator[str]:
        words = [
            "Mock",
            " streaming",
            " response",
            " to:",
            f" {request.prompt[:50]}...",
        ]
        for word in words:
            yield word

    async def generate_code(
        self,
        prompt: str,
        language: str,
        context: str | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        code = f"""# Mock generated {language} code
def mock_function():
    # Generated for: {prompt[:50]}
    pass
"""
        return LLMResponse(
            content=code,
            model_id="mock-model",
            input_tokens=len(prompt.split()),
            output_tokens=len(code.split()),
            latency_ms=100.0,
            finish_reason="stop",
        )

    async def analyze_code(
        self,
        code: str,
        language: str,
        analysis_type: str,
    ) -> LLMResponse:
        analysis = f"""# Mock {analysis_type} analysis for {language}
- No critical issues found
- Code follows best practices
- Consider adding more comments
"""
        return LLMResponse(
            content=analysis,
            model_id="mock-model",
            input_tokens=len(code.split()),
            output_tokens=len(analysis.split()),
            latency_ms=75.0,
            finish_reason="stop",
        )

    async def generate_embedding(
        self,
        text: str,
        model_id: str | None = None,
    ) -> list[float]:
        # Return deterministic mock embedding based on text hash
        import hashlib

        text_hash = hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()
        values = [int(c, 16) / 15.0 for c in text_hash]
        # Extend to 1536 dimensions
        embedding = (values * 96)[:1536]
        return embedding

    async def generate_embeddings_batch(
        self,
        texts: list[str],
        model_id: str | None = None,
    ) -> list[list[float]]:
        return [await self.generate_embedding(text, model_id) for text in texts]

    async def get_usage_summary(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> UsageSummary:
        filtered = [
            r for r in self._usage_records if start_date <= r["timestamp"] <= end_date
        ]

        return UsageSummary(
            total_requests=len(filtered),
            total_input_tokens=sum(r["input_tokens"] for r in filtered),
            total_output_tokens=sum(r["output_tokens"] for r in filtered),
            total_cost_usd=0.0,  # Mock is free
            period_start=start_date,
            period_end=end_date,
        )

    async def get_daily_spend(self) -> float:
        return 0.0

    async def get_monthly_spend(self) -> float:
        return 0.0

    async def check_budget(
        self, daily_limit: float, monthly_limit: float
    ) -> dict[str, Any]:
        return {
            "daily_spend": 0.0,
            "daily_limit": daily_limit,
            "daily_remaining": daily_limit,
            "daily_exceeded": False,
            "monthly_spend": 0.0,
            "monthly_limit": monthly_limit,
            "monthly_remaining": monthly_limit,
            "monthly_exceeded": False,
        }

    async def list_available_models(self) -> list[ModelConfig]:
        return [
            ModelConfig(
                model_id="mock-model",
                family=ModelFamily.CLAUDE,
                max_tokens=4096,
                input_cost_per_1k=0.0,
                output_cost_per_1k=0.0,
            ),
        ]

    async def get_model_config(self, model_id: str) -> ModelConfig | None:
        models = await self.list_available_models()
        for model in models:
            if model.model_id == model_id:
                return model
        return None

    async def health_check(self) -> dict[str, Any]:
        return {"status": "healthy", "mode": "mock"}
