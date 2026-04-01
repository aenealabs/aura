"""
Project Aura - Semantic Guardrails Engine Contracts

Core types, enums, and dataclasses for the 6-layer semantic threat detection engine.
Implements ADR-065 with >95% detection rate on novel attack variants.

Layers:
- L1: Canonical Normalization (5ms)
- L2: Fast-Path Pattern Check (10ms)
- L3: Embedding Similarity Detection (50ms)
- L4: LLM Intent Classification (150ms)
- L5: Multi-Turn Session Tracking (20ms)
- L6: Decision Engine & Audit (5ms)

Author: Project Aura Team
Created: 2026-01-25
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class ThreatLevel(Enum):
    """Severity of detected semantic threat.

    Values are numeric for proper comparison ordering.
    Aligned with existing ThreatLevel in llm_prompt_sanitizer.py but extended
    with SAFE for explicitly verified safe inputs.
    """

    SAFE = 0  # Explicitly verified as safe
    LOW = 1  # Suspicious but likely benign
    MEDIUM = 2  # Potential attack attempt
    HIGH = 3  # Likely malicious
    CRITICAL = 4  # Active attack pattern detected

    def __lt__(self, other: object) -> bool:
        if isinstance(other, ThreatLevel):
            return self.value < other.value
        return NotImplemented

    def __gt__(self, other: object) -> bool:
        if isinstance(other, ThreatLevel):
            return self.value > other.value
        return NotImplemented

    def __le__(self, other: object) -> bool:
        if isinstance(other, ThreatLevel):
            return self.value <= other.value
        return NotImplemented

    def __ge__(self, other: object) -> bool:
        if isinstance(other, ThreatLevel):
            return self.value >= other.value
        return NotImplemented


class ThreatCategory(Enum):
    """Category of detected semantic threat.

    Based on OWASP LLM Top 10 and common adversarial AI attack patterns.
    """

    NONE = "none"  # No threat detected
    JAILBREAK = "jailbreak"  # Attempt to bypass safety constraints
    PROMPT_INJECTION = "prompt_injection"  # System prompt override attempt
    ROLE_CONFUSION = "role_confusion"  # Identity manipulation attack
    DATA_EXFILTRATION = "data_exfiltration"  # Attempt to extract sensitive data
    MULTI_TURN_ATTACK = "multi_turn_attack"  # Cumulative attack across turns
    CONTEXT_POISONING = "context_poisoning"  # RAG/context manipulation
    ENCODING_BYPASS = "encoding_bypass"  # Unicode/encoding tricks
    DELIMITER_INJECTION = "delimiter_injection"  # Prompt boundary manipulation


class RecommendedAction(Enum):
    """Recommended action based on threat assessment."""

    ALLOW = "allow"  # Input is safe, proceed normally
    SANITIZE = "sanitize"  # Remove dangerous content, then proceed
    BLOCK = "block"  # Reject the input entirely
    ESCALATE_HITL = "escalate_hitl"  # Human-in-the-loop review required


@dataclass
class NormalizationResult:
    """Result from Layer 1: Canonical Normalization."""

    original_text: str
    normalized_text: str
    transformations_applied: list[str] = field(default_factory=list)
    encoding_detections: list[str] = field(default_factory=list)
    homographs_found: int = 0
    zero_width_chars_removed: int = 0
    processing_time_ms: float = 0.0

    @property
    def was_modified(self) -> bool:
        """Check if normalization changed the input."""
        return self.original_text != self.normalized_text

    @property
    def modifications_summary(self) -> str:
        """Get a summary of modifications applied."""
        if not self.was_modified:
            return "No modifications"
        parts = []
        if self.homographs_found:
            parts.append(f"{self.homographs_found} homographs")
        if self.zero_width_chars_removed:
            parts.append(f"{self.zero_width_chars_removed} zero-width chars")
        if self.encoding_detections:
            parts.append(f"{len(self.encoding_detections)} encodings decoded")
        return ", ".join(parts) if parts else "Minor normalization"


@dataclass
class PatternMatchResult:
    """Result from Layer 2: Fast-Path Pattern Matching."""

    matched: bool
    patterns_detected: list[str] = field(default_factory=list)
    threat_level: ThreatLevel = ThreatLevel.SAFE
    threat_categories: list[ThreatCategory] = field(default_factory=list)
    blocklist_hit: bool = False
    blocklist_hash: Optional[str] = None
    processing_time_ms: float = 0.0

    @property
    def should_fast_exit(self) -> bool:
        """Check if threat level warrants immediate blocking."""
        return self.threat_level >= ThreatLevel.HIGH or self.blocklist_hit


@dataclass
class EmbeddingMatchResult:
    """Result from Layer 3: Embedding Similarity Detection."""

    similar_threats_found: bool
    top_matches: list[dict[str, Any]] = field(default_factory=list)
    max_similarity_score: float = 0.0
    threat_level: ThreatLevel = ThreatLevel.SAFE
    threat_categories: list[ThreatCategory] = field(default_factory=list)
    corpus_version: str = ""
    processing_time_ms: float = 0.0

    @property
    def high_confidence_match(self) -> bool:
        """Check if there's a high-confidence threat match (>0.85)."""
        return self.max_similarity_score > 0.85


@dataclass
class IntentClassificationResult:
    """Result from Layer 4: LLM Intent Classification."""

    classification: str  # A) Legitimate, B) Override, C) Exfil, D) Role confusion, E) False positive
    confidence: float  # 0.0 to 1.0
    threat_level: ThreatLevel = ThreatLevel.SAFE
    threat_categories: list[ThreatCategory] = field(default_factory=list)
    reasoning: str = ""
    model_used: str = ""
    cached: bool = False
    processing_time_ms: float = 0.0

    @property
    def is_legitimate(self) -> bool:
        """Check if classified as legitimate request."""
        return self.classification.upper().startswith("A")

    @property
    def is_high_confidence_threat(self) -> bool:
        """Check if high-confidence threat detected."""
        return not self.is_legitimate and self.confidence > 0.8


@dataclass
class SessionThreatScore:
    """Result from Layer 5: Multi-Turn Session Tracking."""

    session_id: str
    turn_number: int
    current_turn_score: float  # 0.0 to 1.0
    cumulative_score: float  # Exponentially decayed sum
    escalation_triggered: bool = False
    turn_history: list[float] = field(default_factory=list)
    threat_level: ThreatLevel = ThreatLevel.SAFE
    processing_time_ms: float = 0.0

    @property
    def needs_hitl_review(self) -> bool:
        """Check if cumulative score exceeds HITL threshold (2.5)."""
        return self.cumulative_score > 2.5


@dataclass
class LayerResult:
    """Generic result from any detection layer."""

    layer_name: str
    layer_number: int
    threat_level: ThreatLevel
    threat_categories: list[ThreatCategory] = field(default_factory=list)
    confidence: float = 1.0
    details: dict[str, Any] = field(default_factory=dict)
    processing_time_ms: float = 0.0


@dataclass
class ThreatAssessment:
    """Final threat assessment from Layer 6: Decision Engine.

    Aggregates results from all layers into a unified threat assessment
    with recommended action and full audit trail.
    """

    input_hash: str  # SHA-256 of normalized input
    threat_level: ThreatLevel
    recommended_action: RecommendedAction
    primary_category: ThreatCategory
    all_categories: list[ThreatCategory] = field(default_factory=list)
    confidence: float = 1.0  # 0.0 to 1.0
    reasoning: str = ""
    layer_results: list[LayerResult] = field(default_factory=list)
    session_id: Optional[str] = None
    assessed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_processing_time_ms: float = 0.0

    @property
    def is_safe(self) -> bool:
        """Check if the input is deemed safe."""
        return self.recommended_action == RecommendedAction.ALLOW

    @property
    def requires_intervention(self) -> bool:
        """Check if human or system intervention is needed."""
        return self.recommended_action in (
            RecommendedAction.BLOCK,
            RecommendedAction.ESCALATE_HITL,
        )

    def to_audit_dict(self) -> dict[str, Any]:
        """Convert to dictionary for audit logging."""
        return {
            "input_hash": self.input_hash,
            "threat_level": self.threat_level.name,
            "recommended_action": self.recommended_action.value,
            "primary_category": self.primary_category.value,
            "all_categories": [c.value for c in self.all_categories],
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "session_id": self.session_id,
            "assessed_at": self.assessed_at.isoformat(),
            "total_processing_time_ms": self.total_processing_time_ms,
            "layer_summary": [
                {
                    "layer": r.layer_name,
                    "threat_level": r.threat_level.name,
                    "time_ms": r.processing_time_ms,
                }
                for r in self.layer_results
            ],
        }


@dataclass
class ThreatCorpusEntry:
    """Entry in the threat corpus for embedding-based detection."""

    id: str
    text: str
    category: ThreatCategory
    severity: ThreatLevel
    source: str  # e.g., "adversarial_robustness_benchmark", "internal_red_team"
    embedding: Optional[list[float]] = None
    added_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_index_dict(self) -> dict[str, Any]:
        """Convert to dictionary for OpenSearch indexing."""
        return {
            "id": self.id,
            "text": self.text,
            "category": self.category.value,
            "severity": self.severity.name,
            "source": self.source,
            "embedding": self.embedding,
            "added_at": self.added_at.isoformat(),
            "metadata": self.metadata,
        }


# Type aliases for clarity
ThreatPatternDict = dict[str, list[str]]
HomographMap = dict[str, str]
BlocklistSet = set[str]
