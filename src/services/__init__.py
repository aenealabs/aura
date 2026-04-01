"""Services module for Project Aura.

Note: Titan services require PyTorch and are only imported when torch is available.
Lightweight services (BedrockLLMService, etc.) can be imported without torch.

IMPORTANT: This module uses lazy imports to avoid importing torch at module level.
This is critical for test isolation - tests marked with @pytest.mark.forked must
run before torch is imported to avoid macOS fork safety issues.

Usage:
    # Direct import (preferred for clarity):
    from src.services.titan_memory_service import TitanMemoryService

    # Package import (lazy, imports torch on first access):
    from src.services import TitanMemoryService
"""

from typing import Any

# Names available via 'from src.services import X'
# These are imported lazily via __getattr__ to avoid importing torch at module level
__all__ = [
    # TitanMemoryService
    "TitanMemoryService",
    "TitanMemoryServiceConfig",
    "MemoryMetrics",
    "RetrievalResult",
    "create_titan_memory_service",
    # TitanCognitiveService integration
    "TitanCognitiveService",
    "TitanIntegrationConfig",
    "HybridRetrievalResult",
    "create_titan_cognitive_service",
]

# Lazy import mapping: name -> (module, attribute)
_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "TitanMemoryService": ("src.services.titan_memory_service", "TitanMemoryService"),
    "TitanMemoryServiceConfig": (
        "src.services.titan_memory_service",
        "TitanMemoryServiceConfig",
    ),
    "MemoryMetrics": ("src.services.titan_memory_service", "MemoryMetrics"),
    "RetrievalResult": ("src.services.titan_memory_service", "RetrievalResult"),
    "create_titan_memory_service": (
        "src.services.titan_memory_service",
        "create_titan_memory_service",
    ),
    "TitanCognitiveService": (
        "src.services.titan_cognitive_integration",
        "TitanCognitiveService",
    ),
    "TitanIntegrationConfig": (
        "src.services.titan_cognitive_integration",
        "TitanIntegrationConfig",
    ),
    "HybridRetrievalResult": (
        "src.services.titan_cognitive_integration",
        "HybridRetrievalResult",
    ),
    "create_titan_cognitive_service": (
        "src.services.titan_cognitive_integration",
        "create_titan_cognitive_service",
    ),
}


def __getattr__(name: str) -> Any:
    """
    Lazy import handler for torch-dependent services.

    This allows 'from src.services import TitanMemoryService' to work
    without importing torch until the attribute is actually accessed.
    """
    if name in _LAZY_IMPORTS:
        module_name, attr_name = _LAZY_IMPORTS[name]
        try:
            import importlib

            module = importlib.import_module(module_name)
            return getattr(module, attr_name)
        except (ImportError, RuntimeError) as e:
            # PyTorch not available or torch state corrupted
            raise ImportError(
                f"Cannot import {name}: PyTorch is required but not available. "
                f"Original error: {e}"
            ) from e
    raise AttributeError(f"module 'src.services' has no attribute '{name}'")
