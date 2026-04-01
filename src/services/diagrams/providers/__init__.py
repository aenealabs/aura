"""
AI Provider Clients for Diagram Generation (ADR-060 Phase 2).

Provides unified interfaces to multiple AI providers:
- Bedrock (Claude) - Primary, GovCloud compatible
- OpenAI (GPT-4V, DALL-E 3) - Commercial only
- Vertex AI (Gemini) - Commercial only
"""

from .bedrock_client import BedrockDiagramClient
from .openai_client import OpenAIDiagramClient
from .vertex_client import VertexDiagramClient

__all__ = [
    "BedrockDiagramClient",
    "OpenAIDiagramClient",
    "VertexDiagramClient",
]
