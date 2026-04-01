"""Neural memory models for Project Aura."""

from .deep_mlp_memory import (
    DeepMLPMemory,
    MemoryConfig,
    PersistentMemory,
    SurpriseCalculator,
    create_memory_model,
)
from .miras_config import (
    AttentionalBias,
    MemoryAlgorithm,
    MIRASConfig,
    MIRASLossFunctions,
    MIRASOptimizer,
    MIRASRetention,
    RetentionGate,
    get_miras_preset,
)

__all__ = [
    # DeepMLPMemory components
    "DeepMLPMemory",
    "MemoryConfig",
    "PersistentMemory",
    "SurpriseCalculator",
    "create_memory_model",
    # MIRAS components
    "AttentionalBias",
    "RetentionGate",
    "MemoryAlgorithm",
    "MIRASConfig",
    "MIRASLossFunctions",
    "MIRASRetention",
    "MIRASOptimizer",
    "get_miras_preset",
]
