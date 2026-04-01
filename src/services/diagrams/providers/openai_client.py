"""
OpenAI Client for Diagram Generation (ADR-060 Phase 2).

Provides GPT-4 and DALL-E 3 access for:
- Natural language to diagram DSL generation
- Image understanding and critique
- Creative diagram generation

NOTE: Not FedRAMP authorized - cannot be used with CUI data.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# OpenAI imports with graceful fallback
try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None


class OpenAIDiagramClient:
    """
    OpenAI client for diagram generation tasks.

    Supports:
    - GPT-4 Turbo for text generation
    - GPT-4 Vision for image understanding
    - DALL-E 3 for creative generation
    """

    BASE_URL = "https://api.openai.com/v1"

    def __init__(self, api_key: str):
        """
        Initialize OpenAI client.

        Args:
            api_key: OpenAI API key (from SSM Parameter Store)
        """
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx is required for OpenAI client")

        self.api_key = api_key
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        logger.info("OpenAIDiagramClient initialized")

    async def invoke(
        self,
        model_id: str,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Invoke OpenAI chat completion.

        Args:
            model_id: OpenAI model identifier (gpt-4-turbo, gpt-4-vision-preview)
            messages: List of message dicts with 'role' and 'content'
            system_prompt: Optional system prompt
            max_tokens: Maximum output tokens
            temperature: Sampling temperature
            **kwargs: Additional parameters

        Returns:
            Dict with 'content', 'usage', and 'stop_reason'
        """
        # Build messages list
        formatted_messages = []

        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})

        for m in messages:
            formatted_messages.append({"role": m["role"], "content": m["content"]})

        payload = {
            "model": model_id,
            "messages": formatted_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        # Add optional parameters
        if "top_p" in kwargs:
            payload["top_p"] = kwargs["top_p"]
        if "stop" in kwargs:
            payload["stop"] = kwargs["stop"]

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/chat/completions",
                headers=self._headers,
                json=payload,
            )

            if response.status_code != 200:
                error_body = response.json() if response.content else {}
                error_msg = error_body.get("error", {}).get("message", response.text)
                logger.error(f"OpenAI API error: {response.status_code} - {error_msg}")
                raise Exception(f"OpenAI API error: {error_msg}")

            data = response.json()
            choice = data.get("choices", [{}])[0]
            usage = data.get("usage", {})

            return {
                "content": choice.get("message", {}).get("content", ""),
                "usage": {
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                },
                "stop_reason": choice.get("finish_reason", "unknown"),
                "model_id": model_id,
            }

    async def invoke_with_image(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
        image_data: bytes,
        image_format: str = "png",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Invoke GPT-4 Vision with image input.

        Args:
            model_id: Model identifier (gpt-4-vision-preview)
            messages: List of message dicts
            image_data: Raw image bytes
            image_format: Image format
            **kwargs: Additional parameters

        Returns:
            Dict with 'content', 'usage', and 'stop_reason'
        """
        import base64

        # Encode image
        b64_image = base64.b64encode(image_data).decode("utf-8")
        image_url = f"data:image/{image_format};base64,{b64_image}"

        # Build vision message
        formatted_messages = []
        for m in messages:
            if m["role"] == "user" and "{IMAGE}" in m.get("content", ""):
                text_before, text_after = m["content"].split("{IMAGE}", 1)
                content = []
                if text_before.strip():
                    content.append({"type": "text", "text": text_before.strip()})
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url, "detail": "high"},
                    }
                )
                if text_after.strip():
                    content.append({"type": "text", "text": text_after.strip()})
                formatted_messages.append({"role": "user", "content": content})
            else:
                formatted_messages.append(
                    {
                        "role": m["role"],
                        "content": m["content"],
                    }
                )

        payload = {
            "model": model_id,
            "messages": formatted_messages,
            "max_tokens": kwargs.get("max_tokens", 4096),
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/chat/completions",
                headers=self._headers,
                json=payload,
            )

            if response.status_code != 200:
                error_body = response.json() if response.content else {}
                error_msg = error_body.get("error", {}).get("message", response.text)
                raise Exception(f"OpenAI Vision API error: {error_msg}")

            data = response.json()
            choice = data.get("choices", [{}])[0]
            usage = data.get("usage", {})

            return {
                "content": choice.get("message", {}).get("content", ""),
                "usage": {
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                },
                "stop_reason": choice.get("finish_reason", "unknown"),
                "model_id": model_id,
            }

    async def generate_image(
        self,
        prompt: str,
        model: str = "dall-e-3",
        size: str = "1024x1024",
        quality: str = "standard",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Generate image using DALL-E.

        Args:
            prompt: Image generation prompt
            model: DALL-E model (dall-e-3, dall-e-2)
            size: Image size (1024x1024, 1792x1024, 1024x1792)
            quality: Quality level (standard, hd)
            **kwargs: Additional parameters

        Returns:
            Dict with 'url', 'revised_prompt', and 'usage'
        """
        payload = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "n": 1,
            "response_format": "url",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/images/generations",
                headers=self._headers,
                json=payload,
            )

            if response.status_code != 200:
                error_body = response.json() if response.content else {}
                error_msg = error_body.get("error", {}).get("message", response.text)
                raise Exception(f"DALL-E API error: {error_msg}")

            data = response.json()
            image_data = data.get("data", [{}])[0]

            return {
                "url": image_data.get("url", ""),
                "revised_prompt": image_data.get("revised_prompt", prompt),
                "usage": {
                    "input_tokens": 0,  # DALL-E doesn't report tokens
                    "output_tokens": 0,
                },
                "model_id": model,
            }

    async def health_check(self) -> bool:
        """
        Perform health check.

        Returns:
            True if provider is healthy
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/models",
                    headers=self._headers,
                )
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"OpenAI health check failed: {e}")
            return False
