"""
Google Vertex AI Client for Diagram Generation (ADR-060 Phase 2).

Provides Gemini Pro Vision access for:
- Image understanding and analysis
- Multimodal diagram generation
- Visual critique and feedback

NOTE: Not FedRAMP authorized - cannot be used with CUI data.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Google Cloud imports with graceful fallback
try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None

try:
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    GOOGLE_AUTH_AVAILABLE = False
    service_account = None
    Request = None


class VertexDiagramClient:
    """
    Vertex AI client for diagram generation tasks.

    Supports:
    - Gemini Pro for text generation
    - Gemini Pro Vision for image understanding
    - Imagen for image generation
    """

    def __init__(
        self,
        credentials_json: str,
        project_id: str | None = None,
        location: str = "us-central1",
    ):
        """
        Initialize Vertex AI client.

        Args:
            credentials_json: Service account JSON (from SSM Parameter Store)
            project_id: GCP project ID (extracted from credentials if not provided)
            location: GCP region for Vertex AI
        """
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx is required for Vertex AI client")

        # Parse credentials
        creds_dict = json.loads(credentials_json)
        self.project_id = project_id or creds_dict.get("project_id")
        self.location = location

        if not self.project_id:
            raise ValueError("project_id must be provided or present in credentials")

        # Set up authentication
        if GOOGLE_AUTH_AVAILABLE:
            self._credentials = service_account.Credentials.from_service_account_info(
                creds_dict,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
        else:
            # Fallback: store credentials for manual token refresh
            self._credentials = None
            self._creds_dict = creds_dict
            logger.warning("google-auth not available, using manual token management")

        self._base_url = (
            f"https://{location}-aiplatform.googleapis.com/v1/"
            f"projects/{self.project_id}/locations/{location}/publishers/google/models"
        )

        logger.info(
            f"VertexDiagramClient initialized for project {self.project_id} "
            f"in {location}"
        )

    async def _get_auth_token(self) -> str:
        """Get authentication token for API requests."""
        if self._credentials and GOOGLE_AUTH_AVAILABLE:
            if self._credentials.expired or not self._credentials.token:
                self._credentials.refresh(Request())
            return self._credentials.token
        raise ValueError("Google authentication not configured")

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
        Invoke Gemini model.

        Args:
            model_id: Vertex AI model identifier
            messages: List of message dicts with 'role' and 'content'
            system_prompt: Optional system instruction
            max_tokens: Maximum output tokens
            temperature: Sampling temperature
            **kwargs: Additional parameters

        Returns:
            Dict with 'content', 'usage', and 'stop_reason'
        """
        token = await self._get_auth_token()

        # Format messages for Gemini API
        contents = []
        for m in messages:
            role = "user" if m["role"] == "user" else "model"
            contents.append(
                {
                    "role": role,
                    "parts": [{"text": m["content"]}],
                }
            )

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        }

        # Add system instruction if provided
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        # Add safety settings
        payload["safetySettings"] = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_ONLY_HIGH",
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_ONLY_HIGH",
            },
        ]

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # Map model IDs
        api_model = self._map_model_id(model_id)
        url = f"{self._base_url}/{api_model}:generateContent"

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=headers, json=payload)

            if response.status_code != 200:
                error_body = response.json() if response.content else {}
                error_msg = error_body.get("error", {}).get("message", response.text)
                logger.error(
                    f"Vertex AI API error: {response.status_code} - {error_msg}"
                )
                raise Exception(f"Vertex AI API error: {error_msg}")

            data = response.json()

            # Extract response
            candidates = data.get("candidates", [])
            if not candidates:
                raise Exception("No response candidates from Vertex AI")

            candidate = candidates[0]
            content_parts = candidate.get("content", {}).get("parts", [])
            content = content_parts[0].get("text", "") if content_parts else ""

            # Extract usage metadata
            usage_metadata = data.get("usageMetadata", {})

            return {
                "content": content,
                "usage": {
                    "input_tokens": usage_metadata.get("promptTokenCount", 0),
                    "output_tokens": usage_metadata.get("candidatesTokenCount", 0),
                },
                "stop_reason": candidate.get("finishReason", "unknown"),
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
        Invoke Gemini Vision with image input.

        Args:
            model_id: Model identifier
            messages: List of message dicts
            image_data: Raw image bytes
            image_format: Image format
            **kwargs: Additional parameters

        Returns:
            Dict with 'content', 'usage', and 'stop_reason'
        """
        import base64

        token = await self._get_auth_token()

        # Encode image
        b64_image = base64.b64encode(image_data).decode("utf-8")

        # Build multimodal content
        contents = []
        for m in messages:
            role = "user" if m["role"] == "user" else "model"
            if m["role"] == "user" and "{IMAGE}" in m.get("content", ""):
                text_before, text_after = m["content"].split("{IMAGE}", 1)
                parts = []
                if text_before.strip():
                    parts.append({"text": text_before.strip()})
                parts.append(
                    {
                        "inlineData": {
                            "mimeType": f"image/{image_format}",
                            "data": b64_image,
                        }
                    }
                )
                if text_after.strip():
                    parts.append({"text": text_after.strip()})
                contents.append({"role": role, "parts": parts})
            else:
                contents.append(
                    {
                        "role": role,
                        "parts": [{"text": m["content"]}],
                    }
                )

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": kwargs.get("max_tokens", 4096),
                "temperature": kwargs.get("temperature", 0.7),
            },
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        api_model = self._map_model_id(model_id)
        url = f"{self._base_url}/{api_model}:generateContent"

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=headers, json=payload)

            if response.status_code != 200:
                error_body = response.json() if response.content else {}
                error_msg = error_body.get("error", {}).get("message", response.text)
                raise Exception(f"Vertex AI Vision API error: {error_msg}")

            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise Exception("No response candidates from Vertex AI")

            candidate = candidates[0]
            content_parts = candidate.get("content", {}).get("parts", [])
            content = content_parts[0].get("text", "") if content_parts else ""

            usage_metadata = data.get("usageMetadata", {})

            return {
                "content": content,
                "usage": {
                    "input_tokens": usage_metadata.get("promptTokenCount", 0),
                    "output_tokens": usage_metadata.get("candidatesTokenCount", 0),
                },
                "stop_reason": candidate.get("finishReason", "unknown"),
                "model_id": model_id,
            }

    def _map_model_id(self, model_id: str) -> str:
        """Map internal model IDs to Vertex AI model names."""
        mapping = {
            "gemini-1.5-pro": "gemini-1.5-pro",
            "gemini-1.5-pro-vision": "gemini-1.5-pro",
            "gemini-pro": "gemini-pro",
            "gemini-pro-vision": "gemini-pro-vision",
            "imagen-3": "imagen-3.0-generate-001",
        }
        return mapping.get(model_id, model_id)

    async def health_check(self) -> bool:
        """
        Perform health check.

        Returns:
            True if provider is healthy
        """
        try:
            token = await self._get_auth_token()
            headers = {"Authorization": f"Bearer {token}"}

            async with httpx.AsyncClient(timeout=10.0) as client:
                # List models endpoint
                url = (
                    f"https://{self.location}-aiplatform.googleapis.com/v1/"
                    f"projects/{self.project_id}/locations/{self.location}/models"
                )
                response = await client.get(url, headers=headers)
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"Vertex AI health check failed: {e}")
            return False
