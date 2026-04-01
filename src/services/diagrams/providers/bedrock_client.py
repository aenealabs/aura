"""
AWS Bedrock Client for Diagram Generation (ADR-060 Phase 2).

Provides Claude model access via AWS Bedrock with:
- Messages API (invoke_model) for reliable invocation
- GovCloud region support
- Automatic retry with exponential backoff
- Token usage tracking
"""

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# AWS imports with graceful fallback
try:
    import boto3
    from botocore.config import Config as BotoConfig
    from botocore.exceptions import ClientError

    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False
    boto3 = None
    BotoConfig = None
    ClientError = Exception


class BedrockDiagramClient:
    """
    Bedrock client for diagram generation tasks.

    Uses the Messages API (invoke_model) for Claude models, which provides:
    - Higher rate limits than Converse API
    - Direct control over request format
    - Better compatibility with inference profiles
    """

    def __init__(self, region: str = "us-east-1"):
        """
        Initialize Bedrock client.

        Args:
            region: AWS region (auto-detects GovCloud endpoint)
        """
        if not AWS_AVAILABLE:
            raise ImportError("boto3 is required for Bedrock client")

        self.region = region

        # Configure client with increased connection pool for async contexts
        config = BotoConfig(
            region_name=region,
            retries={
                "max_attempts": 3,
                "mode": "adaptive",  # Adaptive mode handles throttling better
            },
            connect_timeout=10,
            read_timeout=120,  # LLM responses can take time
            max_pool_connections=50,  # Increased for concurrent async requests
        )

        # Create session explicitly for cleaner credential handling
        self._session = boto3.Session()
        self._client = self._session.client("bedrock-runtime", config=config)
        logger.info(f"BedrockDiagramClient initialized for region {region}")

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
        Invoke Bedrock model using Messages API (invoke_model).

        Args:
            model_id: Bedrock model identifier or inference profile ID
            messages: List of message dicts with 'role' and 'content'
            system_prompt: Optional system prompt
            max_tokens: Maximum output tokens
            temperature: Sampling temperature
            **kwargs: Additional inference parameters

        Returns:
            Dict with 'content', 'usage', and 'stop_reason'
        """
        # Build request body for Anthropic Messages API
        request_body: dict[str, Any] = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {"role": m["role"], "content": m["content"]} for m in messages
            ],
        }

        # Add system prompt if provided
        if system_prompt:
            request_body["system"] = system_prompt

        # Add any additional parameters
        if "top_p" in kwargs:
            request_body["top_p"] = kwargs["top_p"]
        if "stop_sequences" in kwargs:
            request_body["stop_sequences"] = kwargs["stop_sequences"]

        # Retry with exponential backoff for throttling
        max_retries = 3
        base_delay = 2.0

        # Use get_running_loop() for proper async context handling (Python 3.10+)
        loop = asyncio.get_running_loop()

        for attempt in range(max_retries):
            try:
                # Run synchronous boto3 call in thread pool to avoid blocking event loop
                response = await loop.run_in_executor(
                    None,
                    lambda: self._client.invoke_model(
                        modelId=model_id,
                        body=json.dumps(request_body),
                        contentType="application/json",
                        accept="application/json",
                    ),
                )

                # Parse response
                response_body = json.loads(response["body"].read())

                # Extract content from response
                content = ""
                if response_body.get("content"):
                    for block in response_body["content"]:
                        if block.get("type") == "text":
                            content += block.get("text", "")

                return {
                    "content": content,
                    "usage": {
                        "input_tokens": response_body.get("usage", {}).get(
                            "input_tokens", 0
                        ),
                        "output_tokens": response_body.get("usage", {}).get(
                            "output_tokens", 0
                        ),
                    },
                    "stop_reason": response_body.get("stop_reason", "unknown"),
                    "model_id": model_id,
                }

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                error_msg = e.response.get("Error", {}).get("Message", "No message")
                http_status = e.response.get("ResponseMetadata", {}).get(
                    "HTTPStatusCode", 0
                )
                logger.error(
                    f"Bedrock ClientError: code={error_code}, http_status={http_status}, "
                    f"message={error_msg}, model={model_id}"
                )
                if error_code == "ThrottlingException" and attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    logger.warning(
                        f"Bedrock throttled, retrying in {delay}s (attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.error(f"Bedrock API error: {error_code} - {e}")
                raise
            except Exception as e:
                logger.error(f"Bedrock invocation failed: {e}")
                raise

        # Should not reach here, but just in case
        raise Exception("Max retries exceeded")

    async def invoke_with_image(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
        image_data: bytes,
        image_format: str = "png",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Invoke model with image input (for vision tasks).

        Args:
            model_id: Bedrock model identifier
            messages: List of message dicts
            image_data: Raw image bytes
            image_format: Image format (png, jpeg, gif, webp)
            **kwargs: Additional parameters

        Returns:
            Dict with 'content', 'usage', and 'stop_reason'
        """
        import base64

        # Build messages with image content
        formatted_messages = []
        for m in messages:
            if m["role"] == "user" and "{IMAGE}" in m.get("content", ""):
                # Replace placeholder with image
                text_before, text_after = m["content"].split("{IMAGE}", 1)
                content_blocks = []
                if text_before.strip():
                    content_blocks.append({"type": "text", "text": text_before.strip()})
                content_blocks.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": f"image/{image_format}",
                            "data": base64.b64encode(image_data).decode("utf-8"),
                        },
                    }
                )
                if text_after.strip():
                    content_blocks.append({"type": "text", "text": text_after.strip()})
                formatted_messages.append({"role": "user", "content": content_blocks})
            else:
                formatted_messages.append({"role": m["role"], "content": m["content"]})

        request_body: dict[str, Any] = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.7),
            "messages": formatted_messages,
        }

        # Use get_running_loop() for proper async context
        loop = asyncio.get_running_loop()

        try:
            response = await loop.run_in_executor(
                None,
                lambda: self._client.invoke_model(
                    modelId=model_id,
                    body=json.dumps(request_body),
                    contentType="application/json",
                    accept="application/json",
                ),
            )

            response_body = json.loads(response["body"].read())

            content = ""
            if response_body.get("content"):
                for block in response_body["content"]:
                    if block.get("type") == "text":
                        content += block.get("text", "")

            return {
                "content": content,
                "usage": {
                    "input_tokens": response_body.get("usage", {}).get(
                        "input_tokens", 0
                    ),
                    "output_tokens": response_body.get("usage", {}).get(
                        "output_tokens", 0
                    ),
                },
                "stop_reason": response_body.get("stop_reason", "unknown"),
                "model_id": model_id,
            }

        except Exception as e:
            logger.error(f"Bedrock vision invocation failed: {e}")
            raise

    def health_check(self) -> bool:
        """
        Perform health check with minimal token usage.

        Returns:
            True if provider is healthy
        """
        try:
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "hi"}],
            }
            response = self._client.invoke_model(
                modelId="anthropic.claude-3-haiku-20240307-v1:0",
                body=json.dumps(request_body),
                contentType="application/json",
                accept="application/json",
            )
            response_body = json.loads(response["body"].read())
            return response_body.get("stop_reason") is not None
        except Exception as e:
            logger.warning(f"Bedrock health check failed: {e}")
            return False
