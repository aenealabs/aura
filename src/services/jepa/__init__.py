"""
JEPA (Joint Embedding Predictive Architecture) Services Package.

This package implements the VL-JEPA architecture from Meta FAIR (December 2025)
for 2.85x efficiency improvement through selective decoding.

Key Components:
- EmbeddingPredictor: JEPA-style embedding prediction for selective decoding
- SelectiveDecodingService: Service layer for agent integration
- TaskType: Enum for routing generative vs non-generative tasks
- JEPAConfig: Configuration for JEPA architecture

Efficiency Gains:
- Non-generative tasks (classification, retrieval, similarity, routing) skip
  the decoder entirely, providing 2.85x fewer operations
- Generative tasks (code generation, explanation) use the full pipeline

Reference: ADR-051 Recursive Context Scaling and Embedding Prediction
"""

from src.services.jepa.embedding_predictor import (  # Core classes; Configuration; Data classes; Enums; Protocols; Aliases
    JEPA,
    Decoder,
    EmbeddingPredictor,
    Encoder,
    JEPAConfig,
    MaskingStrategy,
    PredictionResult,
    SelectiveDecoder,
    SelectiveDecodingService,
    TaskType,
    TransformerLayer,
)

__all__ = [
    # Core Engine
    "EmbeddingPredictor",
    "SelectiveDecodingService",
    # Configuration
    "JEPAConfig",
    # Data Classes
    "PredictionResult",
    "MaskingStrategy",
    "TransformerLayer",
    # Enums
    "TaskType",
    # Protocols
    "Encoder",
    "Decoder",
    # Aliases
    "JEPA",
    "SelectiveDecoder",
]
