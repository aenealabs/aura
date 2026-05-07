"""Scout Agent — model candidate discovery.

Phase 1.4 covers Bedrock; Phase 3.2 adds HuggingFace + internal
SWE-RL sources plus the GovCloud air-gap import path.
"""

from __future__ import annotations

from .airgap_importer import (
    AirgapBundleInput,
    AirgapBundleStatus,
    AirgapImportRecord,
    import_bundle,
    import_many,
)
from .bedrock_client import (
    BedrockListClient,
    BedrockListResponse,
    BedrockModelSummary,
    infer_architecture,
    infer_tokenizer,
    synthesize_summary,
)
from .events import (
    EVENT_DETAIL_TYPE,
    EVENT_SOURCE,
    SCHEMA_VERSION,
    EligibilityFlag,
    ModelCandidateDetected,
    make_event,
)
from .huggingface_client import (
    HF_AVAILABLE,
    HuggingFaceListClient,
    HuggingFaceListResponse,
    HuggingFaceModelSummary,
    synthesize_hf_summary,
    to_bedrock_compatible_summary as hf_to_bedrock_compatible_summary,
)
from .internal_client import (
    InternalListResponse,
    InternalModelClient,
    InternalModelSummary,
    synthesize_internal_summary,
    to_bedrock_compatible_summary as internal_to_bedrock_compatible_summary,
)
from .scout_agent import (
    CandidateEventSink,
    EventBridgeSink,
    InMemoryEventSink,
    ScoutAgent,
    ScoutResult,
    synthesize_default_requirements,
)
from .scout_state import (
    InMemoryScoutStateStore,
    ScoutStateSnapshot,
    ScoutStateStore,
)

__all__ = [
    "BedrockListClient",
    "BedrockListResponse",
    "BedrockModelSummary",
    "synthesize_summary",
    "infer_tokenizer",
    "infer_architecture",
    "EVENT_SOURCE",
    "EVENT_DETAIL_TYPE",
    "SCHEMA_VERSION",
    "EligibilityFlag",
    "ModelCandidateDetected",
    "make_event",
    "ScoutStateStore",
    "ScoutStateSnapshot",
    "InMemoryScoutStateStore",
    "ScoutAgent",
    "ScoutResult",
    "CandidateEventSink",
    "InMemoryEventSink",
    "EventBridgeSink",
    "synthesize_default_requirements",
    # Phase 3.2
    "HF_AVAILABLE",
    "HuggingFaceListClient",
    "HuggingFaceListResponse",
    "HuggingFaceModelSummary",
    "synthesize_hf_summary",
    "hf_to_bedrock_compatible_summary",
    "InternalModelClient",
    "InternalListResponse",
    "InternalModelSummary",
    "synthesize_internal_summary",
    "internal_to_bedrock_compatible_summary",
    "AirgapBundleInput",
    "AirgapBundleStatus",
    "AirgapImportRecord",
    "import_bundle",
    "import_many",
]
