"""
Project Aura - Local LLM Adapter

Adapter for local LLM inference engines implementing LLMService interface.
Supports vLLM, TGI, Ollama, and any OpenAI-compatible API.

See ADR-049: Self-Hosted Deployment Strategy

Environment Variables:
    LLM_PROVIDER: Backend type (vllm, tgi, ollama, openai_compatible)
    LLM_ENDPOINT: API endpoint (default: http://localhost:8000/v1)
    LLM_MODEL_ID: Model identifier (default: mistralai/Mistral-7B-Instruct-v0.2)
    LLM_API_KEY: API key for authenticated endpoints (optional)
    LLM_EMBEDDING_MODEL: Embedding model (default: BAAI/bge-base-en-v1.5)
    LLM_MAX_RETRIES: Max retry attempts (default: 3)
    LLM_TIMEOUT: Request timeout in seconds (default: 120)
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

# Lazy import httpx to avoid import errors when not installed
_httpx = None


def _get_httpx():
    """Lazy import httpx."""
    global _httpx
    if _httpx is None:
        try:
            import httpx

            _httpx = httpx
        except ImportError:
            raise ImportError(
                "httpx package not installed. Install with: pip install httpx"
            )
    return _httpx


class LLMProvider:
    """Supported LLM providers for self-hosted deployments."""

    VLLM = "vllm"
    TGI = "tgi"  # Text Generation Inference
    OLLAMA = "ollama"
    OPENAI_COMPATIBLE = "openai_compatible"


# Model configurations for common self-hosted models
LOCAL_MODEL_CONFIGS = {
    "mistralai/Mistral-7B-Instruct-v0.2": ModelConfig(
        model_id="mistralai/Mistral-7B-Instruct-v0.2",
        family=ModelFamily.MISTRAL,
        max_tokens=32768,
        temperature=0.7,
        input_cost_per_1k=0.0,  # Local models are "free"
        output_cost_per_1k=0.0,
    ),
    "meta-llama/Llama-2-70b-chat-hf": ModelConfig(
        model_id="meta-llama/Llama-2-70b-chat-hf",
        family=ModelFamily.LLAMA,
        max_tokens=4096,
        temperature=0.7,
        input_cost_per_1k=0.0,
        output_cost_per_1k=0.0,
    ),
    "codellama/CodeLlama-34b-Instruct-hf": ModelConfig(
        model_id="codellama/CodeLlama-34b-Instruct-hf",
        family=ModelFamily.LLAMA,
        max_tokens=16384,
        temperature=0.3,
        input_cost_per_1k=0.0,
        output_cost_per_1k=0.0,
    ),
    "deepseek-ai/deepseek-coder-33b-instruct": ModelConfig(
        model_id="deepseek-ai/deepseek-coder-33b-instruct",
        family=ModelFamily.LLAMA,  # Similar architecture
        max_tokens=16384,
        temperature=0.3,
        input_cost_per_1k=0.0,
        output_cost_per_1k=0.0,
    ),
}


class LocalLLMAdapter(LLMService):
    """
    Adapter for local LLM inference engines.

    Supports:
    - vLLM: High-throughput serving with PagedAttention
    - TGI: HuggingFace Text Generation Inference
    - Ollama: Easy local model management
    - Any OpenAI-compatible API endpoint

    All providers use the OpenAI-compatible chat/completions API format.
    """

    def __init__(
        self,
        provider: str | None = None,
        endpoint: str | None = None,
        model_id: str | None = None,
        api_key: str | None = None,
        embedding_model: str | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
    ):
        """
        Initialize local LLM adapter.

        Args:
            provider: LLM provider (vllm, tgi, ollama, openai_compatible)
            endpoint: API endpoint URL
            model_id: Default model identifier
            api_key: API key for authenticated endpoints
            embedding_model: Model for embeddings
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
        """
        self.provider = provider or os.environ.get("LLM_PROVIDER", "vllm")
        self.endpoint = endpoint or os.environ.get(
            "LLM_ENDPOINT", "http://localhost:8000/v1"
        )
        self.model_id = model_id or os.environ.get(
            "LLM_MODEL_ID", "mistralai/Mistral-7B-Instruct-v0.2"
        )
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.embedding_model = embedding_model or os.environ.get(
            "LLM_EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5"
        )
        self.timeout = timeout or int(os.environ.get("LLM_TIMEOUT", "120"))
        self.max_retries = max_retries or int(os.environ.get("LLM_MAX_RETRIES", "3"))

        self._client = None
        self._async_client = None
        self._initialized = False
        self._usage_records: list[dict[str, Any]] = []

    def _get_client(self):
        """Get or create sync HTTP client."""
        if self._client is None:
            httpx = _get_httpx()
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.Client(
                base_url=self.endpoint,
                headers=headers,
                timeout=self.timeout,
            )
        return self._client

    def _get_async_client(self):
        """Get or create async HTTP client."""
        if self._async_client is None:
            httpx = _get_httpx()
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._async_client = httpx.AsyncClient(
                base_url=self.endpoint,
                headers=headers,
                timeout=self.timeout,
            )
        return self._async_client

    async def initialize(self) -> bool:
        """Initialize and verify connectivity."""
        try:
            client = self._get_async_client()
            # Check models endpoint to verify connectivity
            response = await client.get("/models")
            if response.status_code == 200:
                self._initialized = True
                logger.info(
                    f"Local LLM adapter initialized (provider: {self.provider}, "
                    f"endpoint: {self.endpoint}, model: {self.model_id})"
                )
                return True
            else:
                logger.error(
                    f"Failed to connect to LLM endpoint: {response.status_code}"
                )
                return False
        except Exception as e:
            logger.error(f"Failed to initialize local LLM adapter: {e}")
            return False

    async def shutdown(self) -> None:
        """Clean up resources."""
        if self._client:
            self._client.close()
            self._client = None
        if self._async_client:
            await self._async_client.aclose()
            self._async_client = None
        self._initialized = False
        logger.info("Local LLM adapter shut down")

    async def invoke(
        self,
        request: LLMRequest,
        model_config: ModelConfig | None = None,
    ) -> LLMResponse:
        """Invoke the LLM with a request."""
        start_time = time.time()
        client = self._get_async_client()

        # Build messages
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})

        if request.messages:
            messages.extend(request.messages)
        else:
            messages.append({"role": "user", "content": request.prompt})

        # Build request payload
        model = model_config.model_id if model_config else self.model_id
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_tokens
            or (model_config.max_tokens if model_config else 4096),
            "temperature": request.temperature
            or (model_config.temperature if model_config else 0.7),
            "top_p": request.top_p or (model_config.top_p if model_config else 0.9),
        }

        if request.stop_sequences:
            payload["stop"] = request.stop_sequences

        # Make request with retry
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = await client.post("/chat/completions", json=payload)
                response.raise_for_status()
                data = response.json()

                # Parse response
                choice = data.get("choices", [{}])[0]
                content = choice.get("message", {}).get("content", "")
                finish_reason = choice.get("finish_reason", "stop")

                usage = data.get("usage", {})
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)

                latency_ms = (time.time() - start_time) * 1000

                # Record usage
                self._record_usage(model, input_tokens, output_tokens)

                return LLMResponse(
                    content=content,
                    model_id=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    finish_reason=finish_reason,
                    metadata={
                        "provider": self.provider,
                        "endpoint": self.endpoint,
                    },
                )
            except Exception as e:
                last_error = e
                logger.warning(f"LLM request attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await self._async_sleep(2**attempt)  # Exponential backoff

        raise RuntimeError(
            f"LLM request failed after {self.max_retries} attempts: {last_error}"
        )

    async def _async_sleep(self, seconds: float) -> None:
        """Async sleep helper."""
        import asyncio

        await asyncio.sleep(seconds)

    async def invoke_streaming(
        self,
        request: LLMRequest,
        model_config: ModelConfig | None = None,
    ) -> AsyncIterator[str]:
        """Invoke the LLM with streaming response."""
        client = self._get_async_client()

        # Build messages
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})

        if request.messages:
            messages.extend(request.messages)
        else:
            messages.append({"role": "user", "content": request.prompt})

        # Build request payload
        model = model_config.model_id if model_config else self.model_id
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_tokens or 4096,
            "temperature": request.temperature or 0.7,
            "stream": True,
        }

        async with client.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        import json

                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except Exception:
                        continue

    async def generate_code(
        self,
        prompt: str,
        language: str,
        context: str | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Generate code based on a prompt."""
        system_prompt = f"""You are an expert {language} programmer.
Generate clean, well-documented, and secure code.
Only output code without explanations unless specifically asked.
Follow best practices for {language}."""

        full_prompt = prompt
        if context:
            full_prompt = (
                f"Context:\n```{language}\n{context}\n```\n\nRequest: {prompt}"
            )

        request = LLMRequest(
            prompt=full_prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=0.3,  # Lower temperature for code generation
        )

        return await self.invoke(request)

    async def analyze_code(
        self,
        code: str,
        language: str,
        analysis_type: str,
    ) -> LLMResponse:
        """Analyze code for specific issues."""
        analysis_prompts = {
            "security": "Analyze this code for security vulnerabilities. List each issue with severity (CRITICAL, HIGH, MEDIUM, LOW), location, and remediation.",
            "quality": "Review this code for quality issues including maintainability, readability, and adherence to best practices.",
            "performance": "Analyze this code for performance issues and optimization opportunities.",
            "bugs": "Find potential bugs, edge cases, and logic errors in this code.",
        }

        system_prompt = f"""You are an expert {language} code analyzer.
Provide detailed, actionable analysis in a structured format.
Be thorough but concise."""

        prompt = f"""{analysis_prompts.get(analysis_type, analysis_prompts['quality'])}

```{language}
{code}
```"""

        request = LLMRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=4096,
            temperature=0.2,  # Low temperature for analysis
        )

        return await self.invoke(request)

    async def generate_embedding(
        self,
        text: str,
        model_id: str | None = None,
    ) -> list[float]:
        """Generate embedding vector for text."""
        client = self._get_async_client()
        model = model_id or self.embedding_model

        payload = {
            "model": model,
            "input": text,
        }

        response = await client.post("/embeddings", json=payload)
        response.raise_for_status()
        data = response.json()

        embedding = data.get("data", [{}])[0].get("embedding", [])
        return embedding

    async def generate_embeddings_batch(
        self,
        texts: list[str],
        model_id: str | None = None,
    ) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        client = self._get_async_client()
        model = model_id or self.embedding_model

        payload = {
            "model": model,
            "input": texts,
        }

        response = await client.post("/embeddings", json=payload)
        response.raise_for_status()
        data = response.json()

        embeddings = [item.get("embedding", []) for item in data.get("data", [])]
        return embeddings

    def _record_usage(
        self, model_id: str, input_tokens: int, output_tokens: int
    ) -> None:
        """Record usage for tracking."""
        self._usage_records.append(
            {
                "timestamp": datetime.now(timezone.utc),
                "model_id": model_id,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
        )
        # Keep only last 10000 records
        if len(self._usage_records) > 10000:
            self._usage_records = self._usage_records[-10000:]

    async def get_usage_summary(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> UsageSummary:
        """Get usage summary for a time period."""
        filtered = [
            r for r in self._usage_records if start_date <= r["timestamp"] <= end_date
        ]

        total_input = sum(r["input_tokens"] for r in filtered)
        total_output = sum(r["output_tokens"] for r in filtered)

        # Group by model
        by_model: dict[str, dict[str, Any]] = {}
        for r in filtered:
            model = r["model_id"]
            if model not in by_model:
                by_model[model] = {
                    "requests": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                }
            by_model[model]["requests"] += 1
            by_model[model]["input_tokens"] += r["input_tokens"]
            by_model[model]["output_tokens"] += r["output_tokens"]

        return UsageSummary(
            total_requests=len(filtered),
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_cost_usd=0.0,  # Local models are free
            period_start=start_date,
            period_end=end_date,
            by_model=by_model,
        )

    async def get_daily_spend(self) -> float:
        """Get today's spend in USD (always 0 for local models)."""
        return 0.0

    async def get_monthly_spend(self) -> float:
        """Get current month's spend in USD (always 0 for local models)."""
        return 0.0

    async def check_budget(
        self, daily_limit: float, monthly_limit: float
    ) -> dict[str, Any]:
        """Check budget (always within budget for local models)."""
        return {
            "daily_spend": 0.0,
            "daily_limit": daily_limit,
            "daily_remaining": daily_limit,
            "daily_within_budget": True,
            "monthly_spend": 0.0,
            "monthly_limit": monthly_limit,
            "monthly_remaining": monthly_limit,
            "monthly_within_budget": True,
        }

    async def list_available_models(self) -> list[ModelConfig]:
        """List available LLM models."""
        try:
            client = self._get_async_client()
            response = await client.get("/models")
            response.raise_for_status()
            data = response.json()

            models = []
            for model_data in data.get("data", []):
                model_id = model_data.get("id", "")
                # Use predefined config if available, otherwise create default
                if model_id in LOCAL_MODEL_CONFIGS:
                    models.append(LOCAL_MODEL_CONFIGS[model_id])
                else:
                    models.append(
                        ModelConfig(
                            model_id=model_id,
                            family=ModelFamily.LLAMA,  # Default assumption
                            max_tokens=4096,
                            input_cost_per_1k=0.0,
                            output_cost_per_1k=0.0,
                        )
                    )
            return models
        except Exception as e:
            logger.warning(f"Failed to list models: {e}")
            # Return default model
            return [
                LOCAL_MODEL_CONFIGS.get(
                    self.model_id,
                    ModelConfig(
                        model_id=self.model_id,
                        family=ModelFamily.LLAMA,
                        max_tokens=4096,
                    ),
                )
            ]

    async def get_model_config(self, model_id: str) -> ModelConfig | None:
        """Get configuration for a specific model."""
        if model_id in LOCAL_MODEL_CONFIGS:
            return LOCAL_MODEL_CONFIGS[model_id]

        # Try to get from endpoint
        models = await self.list_available_models()
        for model in models:
            if model.model_id == model_id:
                return model
        return None

    async def health_check(self) -> dict[str, Any]:
        """Perform health check on the LLM service."""
        try:
            start_time = time.time()
            client = self._get_async_client()
            response = await client.get("/models")
            latency_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()
                model_count = len(data.get("data", []))
                return {
                    "status": "healthy",
                    "provider": self.provider,
                    "endpoint": self.endpoint,
                    "model_id": self.model_id,
                    "available_models": model_count,
                    "latency_ms": latency_ms,
                    "initialized": self._initialized,
                }
            else:
                return {
                    "status": "unhealthy",
                    "provider": self.provider,
                    "endpoint": self.endpoint,
                    "error": f"HTTP {response.status_code}",
                }
        except Exception as e:
            return {
                "status": "error",
                "provider": self.provider,
                "endpoint": self.endpoint,
                "error": str(e),
            }
