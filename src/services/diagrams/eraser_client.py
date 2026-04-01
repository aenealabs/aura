"""
Eraser.io API Client for Professional Diagram Generation.

Integrates with Eraser.io's Diagramming API to generate high-quality
cloud architecture diagrams with official AWS/Azure/GCP icons.

API Documentation: https://docs.eraser.io/reference/generate-diagram-from-prompt

Requires ERASER_API_KEY environment variable or SSM parameter.
"""

import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class EraserDiagramType(str, Enum):
    """Supported diagram types in Eraser.io API."""

    CLOUD_ARCHITECTURE = "cloud-architecture-diagram"
    SEQUENCE = "sequence-diagram"
    ENTITY_RELATIONSHIP = "entity-relationship-diagram"
    FLOWCHART = "flowchart-diagram"
    BPMN = "bpmn-diagram"


class EraserMode(str, Enum):
    """AI model modes for diagram generation."""

    STANDARD = "standard"  # GPT-4.1
    PREMIUM = "premium"  # o4-mini-high


@dataclass
class EraserDiagramResult:
    """Result from Eraser.io diagram generation."""

    request_id: str
    image_url: str  # PNG URL
    dsl_code: str  # Eraser DSL for editing
    diagram_type: str
    file_url: Optional[str] = None  # Link to edit in Eraser


class EraserApiError(Exception):
    """Error from Eraser.io API."""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code


class EraserClient:
    """
    Client for Eraser.io Diagramming API.

    Usage:
        client = EraserClient(api_key="your-key")
        result = await client.generate_diagram(
            prompt="Create AWS architecture with EKS, Neptune, and Bedrock",
            diagram_type=EraserDiagramType.CLOUD_ARCHITECTURE
        )
        print(result.image_url)  # PNG URL
    """

    API_BASE_URL = "https://app.eraser.io/api/render"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Eraser client.

        Args:
            api_key: Eraser API key. If not provided, reads from
                     ERASER_API_KEY environment variable.
        """
        self.api_key = api_key or os.environ.get("ERASER_API_KEY")
        if not self.api_key:
            logger.warning(
                "ERASER_API_KEY not set - Eraser.io integration will be disabled"
            )

    @property
    def is_configured(self) -> bool:
        """Check if the client is properly configured."""
        return bool(self.api_key)

    async def generate_diagram(
        self,
        prompt: str,
        diagram_type: EraserDiagramType = EraserDiagramType.CLOUD_ARCHITECTURE,
        mode: EraserMode = EraserMode.STANDARD,
        create_file: bool = False,
    ) -> EraserDiagramResult:
        """
        Generate a diagram from natural language prompt.

        Args:
            prompt: Natural language description of the diagram
            diagram_type: Type of diagram to generate
            mode: AI model mode (standard or premium)
            create_file: Whether to create an editable Eraser file

        Returns:
            EraserDiagramResult with image URL and DSL code

        Raises:
            EraserApiError: If API call fails
        """
        if not self.is_configured:
            raise EraserApiError("Eraser API key not configured", status_code=503)

        url = f"{self.API_BASE_URL}/prompt"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "text": prompt,
            "diagramType": diagram_type.value,
            "mode": mode.value,
        }

        if create_file:
            payload["fileOptions"] = {
                "createFile": True,
                "linkAccess": "edit",
            }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    diagrams = data.get("diagrams", [{}])
                    first_diagram = diagrams[0] if diagrams else {}

                    return EraserDiagramResult(
                        request_id=data.get("requestId", ""),
                        image_url=data.get("imageUrl", ""),
                        dsl_code=first_diagram.get("code", ""),
                        diagram_type=first_diagram.get(
                            "diagramType", diagram_type.value
                        ),
                        file_url=data.get("fileUrl") or data.get("createEraserFileUrl"),
                    )

                elif response.status_code == 400:
                    raise EraserApiError(
                        f"Invalid request: {response.text}", status_code=400
                    )
                elif response.status_code == 403:
                    raise EraserApiError(
                        "Eraser API authentication failed", status_code=403
                    )
                elif response.status_code == 503:
                    raise EraserApiError(
                        "Eraser service temporarily unavailable", status_code=503
                    )
                else:
                    raise EraserApiError(
                        f"Eraser API error: {response.status_code} - {response.text}",
                        status_code=response.status_code,
                    )

        except httpx.TimeoutException:
            raise EraserApiError("Eraser API request timed out", status_code=504)
        except httpx.RequestError as e:
            raise EraserApiError(f"Network error: {str(e)}", status_code=503)

    async def render_dsl(
        self,
        dsl_code: str,
        diagram_type: EraserDiagramType = EraserDiagramType.CLOUD_ARCHITECTURE,
    ) -> EraserDiagramResult:
        """
        Render a diagram from Eraser DSL code.

        Args:
            dsl_code: Eraser DSL code
            diagram_type: Type of diagram

        Returns:
            EraserDiagramResult with image URL
        """
        if not self.is_configured:
            raise EraserApiError("Eraser API key not configured", status_code=503)

        url = f"{self.API_BASE_URL}/elements"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "elements": [
                {
                    "type": "diagram",
                    "diagramType": diagram_type.value,
                    "code": dsl_code,
                }
            ]
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    return EraserDiagramResult(
                        request_id=data.get("requestId", ""),
                        image_url=data.get("imageUrl", ""),
                        dsl_code=dsl_code,
                        diagram_type=diagram_type.value,
                    )
                else:
                    raise EraserApiError(
                        f"Eraser API error: {response.status_code}",
                        status_code=response.status_code,
                    )

        except httpx.TimeoutException:
            raise EraserApiError("Eraser API request timed out", status_code=504)
        except httpx.RequestError as e:
            raise EraserApiError(f"Network error: {str(e)}", status_code=503)


# Singleton instance
_eraser_client: Optional[EraserClient] = None


def get_eraser_client() -> EraserClient:
    """Get or create the Eraser client singleton."""
    global _eraser_client
    if _eraser_client is None:
        _eraser_client = EraserClient()
    return _eraser_client
