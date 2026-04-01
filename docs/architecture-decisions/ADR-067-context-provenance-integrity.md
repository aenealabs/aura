# ADR-067: Context Provenance and Integrity for GraphRAG

## Status

Deployed

## Date

2026-01-25 (Proposed) | 2026-01-26 (Deployed)

## Reviews

| Reviewer | Role | Date | Verdict |
|----------|------|------|---------|
| Architecture Review | AWS AI SaaS Architect | 2026-01-26 | Approved |
| Systems Review | Senior Systems Architect | 2026-01-26 | Approved |
| Security Review | Cybersecurity Analyst | 2026-01-26 | Approved |
| Kelly | Test Architect | 2026-01-26 | Approved |

### Review Summary

All reviewers approved. Implementation includes 8 Python services with 275 tests achieving comprehensive coverage. CloudFormation infrastructure (Layer 2.8) provides DynamoDB tables, SNS alerts, EventBridge routing, and CloudWatch alarms. Security controls prevent context poisoning attacks through multi-layer verification.

## Context

### The GraphRAG Context Poisoning Threat

Security gap analysis identified a critical vulnerability in Project Aura's hybrid GraphRAG architecture: **no integrity verification occurs on code retrieved from Neptune and OpenSearch before it reaches the LLM**. This creates a direct attack vector where malicious code injected into the graph appears as "legitimate context."

```text
Attack Vector Analysis:

                     Attacker compromises
                     source repository
                            │
                            ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                   Code Indexing Pipeline                     │
    │                                                              │
    │   Malicious code → Parser → Neptune Graph + OpenSearch       │
    │                            ↓                                 │
    │                   No integrity checks                        │
    │                   No provenance tracking                     │
    │                   No anomaly detection                       │
    └─────────────────────────────────────────────────────────────┘
                            │
                            ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                  Context Retrieval                           │
    │                                                              │
    │   User Query → ContextRetrievalService → Poisoned Results   │
    │                ↓                                             │
    │   No pre-retrieval scanning                                  │
    │   No source verification                                     │
    │   No trust scoring                                           │
    └─────────────────────────────────────────────────────────────┘
                            │
                            ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                    LLM Processing                            │
    │                                                              │
    │   Poisoned context included in prompt                        │
    │   LLM generates code based on malicious patterns             │
    │   Coder Agent outputs vulnerable code                        │
    │                                                              │
    │   Sanitization happens AFTER retrieval = too late            │
    └─────────────────────────────────────────────────────────────┘
```

### Current State Gaps

| Gap | Risk | Current Mitigation |
|-----|------|-------------------|
| No content provenance | Cannot trace indexed content to verified source | None |
| No integrity verification | Modified content undetected | None |
| Post-retrieval sanitization | Poisoned content reaches LLM context | ADR-065 (insufficient) |
| No anomaly detection | Unusual patterns not flagged | None |
| No trust scoring | All sources treated equally | None |
| No quarantine mechanism | Suspicious content not isolated | None |
| No provenance audit trail | Compliance gap for CMMC/SOX | None |

### Threat Model

**T1: Direct Repository Poisoning**
- Attacker gains write access to indexed repository
- Injects malicious code patterns, backdoors, or vulnerable dependencies
- Indexed into Neptune/OpenSearch as legitimate code
- Retrieved as context for code generation

**T2: Supply Chain Contamination**
- Attacker compromises upstream dependency
- Malicious patterns propagate through code analysis
- Graph relationships encode dangerous patterns as "normal"

**T3: Gradual Context Drift**
- Attacker makes small, incremental changes over time
- Each change passes review individually
- Cumulative effect creates exploitable patterns

**T4: Metadata Manipulation**
- Attacker modifies file metadata (timestamps, authors)
- Inflates trust scores for malicious content
- Content appears more authoritative than it is

### ADR-065 Limitations

ADR-065 (Semantic Guardrails Engine) provides user input sanitization but does not address context integrity:

```text
ADR-065 Scope:              ADR-067 Scope:
┌──────────────────────┐    ┌──────────────────────────────────┐
│ User Input           │    │ Retrieved Context                 │
│ • Prompt injection   │    │ • Source provenance               │
│ • Jailbreak attempts │    │ • Content integrity               │
│ • Role confusion     │    │ • Trust scoring                   │
│                      │    │ • Anomaly detection               │
│ Post-retrieval only  │    │ Pre-retrieval + at-index time     │
└──────────────────────┘    └──────────────────────────────────┘
```

## Decision

Implement a Context Provenance and Integrity system that tracks, verifies, and validates all content indexed into and retrieved from Neptune and OpenSearch. The system operates at three points: index time, retrieval time, and serving time.

### Core Capabilities

1. **Content Provenance Tracking** - Record origin of all indexed content (repository, commit SHA, author, timestamp, signatures)
2. **Cryptographic Integrity Verification** - SHA-256 hashes on all indexed chunks with tamper detection
3. **Pre-Retrieval Scanning** - Detect injection patterns in context BEFORE LLM processing
4. **Trust Scoring Engine** - Assign and maintain trust levels for content sources
5. **Anomaly Detection** - Identify unusual patterns in retrieved context
6. **Quarantine Mechanism** - Isolate and review suspicious content
7. **Provenance Audit Trail** - Log all provenance checks for compliance

## Architecture

### Context Provenance and Integrity Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                     Context Provenance and Integrity System                          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌───────────────────────────────────────────────────────────────────────────────┐ │
│  │                           INDEX-TIME VERIFICATION                              │ │
│  │                                                                               │ │
│  │   Repository Source                                                           │ │
│  │         │                                                                     │ │
│  │         ▼                                                                     │ │
│  │   ┌─────────────────────────────────────────────────────────────────────────┐│ │
│  │   │ ProvenanceCollector                                                      ││ │
│  │   │ • Git commit SHA extraction                                              ││ │
│  │   │ • Author verification (GPG signatures when available)                    ││ │
│  │   │ • Timestamp recording                                                    ││ │
│  │   │ • Repository trust level lookup                                          ││ │
│  │   └─────────────────────────────────────────────────────────────────────────┘│ │
│  │         │                                                                     │ │
│  │         ▼                                                                     │ │
│  │   ┌─────────────────────────────────────────────────────────────────────────┐│ │
│  │   │ IntegrityHasher                                                          ││ │
│  │   │ • SHA-256 content hash                                                   ││ │
│  │   │ • Chunk boundary hashing                                                 ││ │
│  │   │ • Embedding vector fingerprint                                           ││ │
│  │   │ • HMAC signature with index key                                          ││ │
│  │   └─────────────────────────────────────────────────────────────────────────┘│ │
│  │         │                                                                     │ │
│  │         ▼                                                                     │ │
│  │   ┌─────────────────────────────────────────────────────────────────────────┐│ │
│  │   │ InitialTrustScorer                                                       ││ │
│  │   │ • Repository reputation (internal = 1.0, verified partner = 0.8, etc.)  ││ │
│  │   │ • Author trust (known contributor = 1.0, first-time = 0.5)              ││ │
│  │   │ • Content age factor (established = 1.0, brand new = 0.7)               ││ │
│  │   │ • Composite initial trust score                                          ││ │
│  │   └─────────────────────────────────────────────────────────────────────────┘│ │
│  │         │                                                                     │ │
│  │         ▼                                                                     │ │
│  │   Neptune (provenance properties) + OpenSearch (integrity fields)            │ │
│  │                                                                               │ │
│  └───────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                     │
│  ┌───────────────────────────────────────────────────────────────────────────────┐ │
│  │                          RETRIEVAL-TIME VERIFICATION                           │ │
│  │                                                                               │ │
│  │   ContextRetrievalService Query                                               │ │
│  │         │                                                                     │ │
│  │         ▼                                                                     │ │
│  │   ┌─────────────────────────────────────────────────────────────────────────┐│ │
│  │   │ IntegrityVerificationService (Pre-Retrieval)                             ││ │
│  │   │                                                                          ││ │
│  │   │ For each retrieved chunk:                                                ││ │
│  │   │ ┌─────────────────────────────────────────────────────────────────────┐ ││ │
│  │   │ │ 1. Hash Verification                                                 │ ││ │
│  │   │ │    • Recompute SHA-256 of content                                    │ ││ │
│  │   │ │    • Compare against stored hash                                     │ ││ │
│  │   │ │    • HMAC signature validation                                       │ ││ │
│  │   │ │    • Flag: INTEGRITY_VERIFIED | INTEGRITY_FAILED | HASH_MISSING      │ ││ │
│  │   │ └─────────────────────────────────────────────────────────────────────┘ ││ │
│  │   │ ┌─────────────────────────────────────────────────────────────────────┐ ││ │
│  │   │ │ 2. Provenance Validation                                             │ ││ │
│  │   │ │    • Verify source repository still exists                           │ ││ │
│  │   │ │    • Check commit SHA exists in repository                           │ ││ │
│  │   │ │    • Validate author is still authorized                             │ ││ │
│  │   │ │    • Flag: PROVENANCE_VALID | PROVENANCE_STALE | PROVENANCE_INVALID  │ ││ │
│  │   │ └─────────────────────────────────────────────────────────────────────┘ ││ │
│  │   │ ┌─────────────────────────────────────────────────────────────────────┐ ││ │
│  │   │ │ 3. Trust Score Lookup                                                │ ││ │
│  │   │ │    • Retrieve current trust score from TrustScoringEngine            │ ││ │
│  │   │ │    • Apply decay for stale content                                   │ ││ │
│  │   │ │    • Factor in repository-level trust changes                        │ ││ │
│  │   │ └─────────────────────────────────────────────────────────────────────┘ ││ │
│  │   └─────────────────────────────────────────────────────────────────────────┘│ │
│  │         │                                                                     │ │
│  │         ▼                                                                     │ │
│  │   ┌─────────────────────────────────────────────────────────────────────────┐│ │
│  │   │ ContextAnomalyDetector                                                   ││ │
│  │   │                                                                          ││ │
│  │   │ • Embedding-based injection detection (ADR-065 threat corpus)           ││ │
│  │   │ • Structural anomaly detection (unusual AST patterns)                   ││ │
│  │   │ • Statistical outlier detection (content diverges from repo norms)     ││ │
│  │   │ • Hidden instruction scanning (comments, strings, docstrings)          ││ │
│  │   │                                                                          ││ │
│  │   │ Output: AnomalyReport {                                                  ││ │
│  │   │   anomaly_score: 0.0 - 1.0                                              ││ │
│  │   │   anomaly_types: [INJECTION_PATTERN, STRUCTURAL_ANOMALY, ...]           ││ │
│  │   │   suspicious_spans: [(start, end, reason), ...]                         ││ │
│  │   │ }                                                                        ││ │
│  │   └─────────────────────────────────────────────────────────────────────────┘│ │
│  │         │                                                                     │ │
│  │         ▼                                                                     │ │
│  │   ┌─────────────────────────────────────────────────────────────────────────┐│ │
│  │   │ QuarantineManager                                                        ││ │
│  │   │                                                                          ││ │
│  │   │ IF integrity_failed OR trust_score < 0.3 OR anomaly_score > 0.7:        ││ │
│  │   │   • Move chunk to quarantine index                                       ││ │
│  │   │   • Remove from active retrieval pool                                    ││ │
│  │   │   • Create HITL review ticket                                            ││ │
│  │   │   • Log to provenance audit trail                                        ││ │
│  │   │                                                                          ││ │
│  │   │ Quarantine Table: aura-context-quarantine-{env}                          ││ │
│  │   └─────────────────────────────────────────────────────────────────────────┘│ │
│  │         │                                                                     │ │
│  │         ▼                                                                     │ │
│  │   Verified Context → LLM Prompt (with trust metadata)                        │ │
│  │                                                                               │ │
│  └───────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Integration with ContextRetrievalService

```text
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                       Modified Context Retrieval Pipeline                            │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│   User Query                                                                        │
│       │                                                                             │
│       ▼                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │ QueryPlanningAgent (existing)                                                │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│       │                                                                             │
│       ▼                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │ Parallel Search (existing)                                                   │  │
│   │ • Neptune Graph Search                                                       │  │
│   │ • OpenSearch Vector Search                                                   │  │
│   │ • Filesystem Search                                                          │  │
│   │ • Git Search                                                                 │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│       │                                                                             │
│       ▼                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │ NEW: ContextProvenanceVerifier                                               │  │
│   │                                                                              │  │
│   │ For each result from parallel search:                                        │  │
│   │   integrity_result = IntegrityVerificationService.verify(chunk)              │  │
│   │   trust_score = TrustScoringEngine.get_trust(chunk.provenance)               │  │
│   │   anomaly_result = ContextAnomalyDetector.scan(chunk)                        │  │
│   │                                                                              │  │
│   │   IF not integrity_result.verified:                                          │  │
│   │       QuarantineManager.quarantine(chunk, "INTEGRITY_FAILURE")               │  │
│   │       EXCLUDE from results                                                   │  │
│   │                                                                              │  │
│   │   IF trust_score < config.min_trust_threshold:                               │  │
│   │       ProvenanceAuditLogger.log("LOW_TRUST_EXCLUDED", chunk)                 │  │
│   │       EXCLUDE from results (or include with warning)                         │  │
│   │                                                                              │  │
│   │   IF anomaly_result.score > config.anomaly_threshold:                        │  │
│   │       QuarantineManager.quarantine(chunk, anomaly_result.types)              │  │
│   │       EXCLUDE from results                                                   │  │
│   │                                                                              │  │
│   │   chunk.verified_provenance = integrity_result                               │  │
│   │   chunk.trust_score = trust_score                                            │  │
│   │   chunk.anomaly_report = anomaly_result                                      │  │
│   │                                                                              │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│       │                                                                             │
│       ▼                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │ ResultSynthesisAgent (existing + enhanced)                                   │  │
│   │ • Ranking now factors trust_score                                            │  │
│   │ • Context includes provenance metadata for transparency                      │  │
│   │ • Low-trust content deprioritized or excluded                                │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│       │                                                                             │
│       ▼                                                                             │
│   Verified, Trust-Scored Context → LLM Prompt                                      │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Neptune Provenance Properties

```text
CodeEntity Vertex (enhanced):
┌─────────────────────────────────────────────────────────────────┐
│ Existing Properties                                              │
│ • entity_id, name, type, file_path, line_number, created_at     │
│                                                                  │
│ NEW Provenance Properties:                                       │
│ • provenance_repository_id: str       (repository identifier)   │
│ • provenance_commit_sha: str          (git commit SHA)          │
│ • provenance_author_id: str           (author identifier)       │
│ • provenance_author_email: str        (author email)            │
│ • provenance_timestamp: datetime      (commit timestamp)        │
│ • provenance_signature: str | null    (GPG signature if signed) │
│ • provenance_branch: str              (source branch)           │
│ • content_hash_sha256: str            (SHA-256 of content)      │
│ • content_hmac: str                   (HMAC with index key)     │
│ • trust_score: float                  (0.0 - 1.0)               │
│ • trust_score_updated_at: datetime    (last trust recalc)       │
│ • indexed_at: datetime                (when added to graph)     │
│ • verified_at: datetime | null        (last integrity check)    │
│ • quarantine_status: str | null       (ACTIVE | QUARANTINED)    │
└─────────────────────────────────────────────────────────────────┘
```

### OpenSearch Integrity Fields

```text
aura-code-embeddings Index (enhanced mapping):
{
  "mappings": {
    "properties": {
      // Existing fields
      "doc_id": { "type": "keyword" },
      "text": { "type": "text" },
      "vector": { "type": "knn_vector", "dimension": 1024 },
      "file_path": { "type": "keyword" },
      "language": { "type": "keyword" },

      // NEW Provenance fields
      "provenance": {
        "type": "object",
        "properties": {
          "repository_id": { "type": "keyword" },
          "commit_sha": { "type": "keyword" },
          "author_id": { "type": "keyword" },
          "author_email": { "type": "keyword" },
          "timestamp": { "type": "date" },
          "signature": { "type": "keyword" },
          "branch": { "type": "keyword" }
        }
      },

      // NEW Integrity fields
      "integrity": {
        "type": "object",
        "properties": {
          "content_hash": { "type": "keyword" },
          "content_hmac": { "type": "keyword" },
          "chunk_boundary_hash": { "type": "keyword" },
          "embedding_fingerprint": { "type": "keyword" },
          "indexed_at": { "type": "date" },
          "verified_at": { "type": "date" }
        }
      },

      // NEW Trust fields
      "trust": {
        "type": "object",
        "properties": {
          "score": { "type": "float" },
          "score_components": {
            "type": "object",
            "properties": {
              "repository": { "type": "float" },
              "author": { "type": "float" },
              "age": { "type": "float" },
              "verification": { "type": "float" }
            }
          },
          "updated_at": { "type": "date" }
        }
      },

      // NEW Status field
      "status": {
        "type": "keyword"  // ACTIVE | QUARANTINED | PENDING_REVIEW
      }
    }
  }
}
```

### Trust Scoring Model

```text
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           Trust Scoring Engine                                       │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  Trust Score = weighted average of component scores                                 │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │ Component Scores:                                                            │   │
│  │                                                                              │   │
│  │ 1. Repository Trust (weight: 0.35)                                           │   │
│  │    ┌─────────────────────────────────────────────────────────────────────┐  │   │
│  │    │ Internal repository (same org)              │ 1.00                   │  │   │
│  │    │ Verified partner repository                 │ 0.90                   │  │   │
│  │    │ Public repository (high stars, active)      │ 0.70                   │  │   │
│  │    │ Public repository (low activity)            │ 0.50                   │  │   │
│  │    │ Unknown/unverified repository               │ 0.30                   │  │   │
│  │    │ Flagged/suspicious repository               │ 0.00                   │  │   │
│  │    └─────────────────────────────────────────────────────────────────────┘  │   │
│  │                                                                              │   │
│  │ 2. Author Trust (weight: 0.25)                                               │   │
│  │    ┌─────────────────────────────────────────────────────────────────────┐  │   │
│  │    │ Verified internal employee                  │ 1.00                   │  │   │
│  │    │ Known contributor (>10 verified commits)    │ 0.90                   │  │   │
│  │    │ Contributor (1-10 verified commits)         │ 0.70                   │  │   │
│  │    │ First-time contributor                      │ 0.50                   │  │   │
│  │    │ Unverified author                           │ 0.30                   │  │   │
│  │    │ GPG-signed commit bonus                     │ +0.10                  │  │   │
│  │    └─────────────────────────────────────────────────────────────────────┘  │   │
│  │                                                                              │   │
│  │ 3. Content Age Trust (weight: 0.15)                                          │   │
│  │    ┌─────────────────────────────────────────────────────────────────────┐  │   │
│  │    │ Established (>90 days, no modifications)    │ 1.00                   │  │   │
│  │    │ Stable (30-90 days)                         │ 0.90                   │  │   │
│  │    │ Recent (7-30 days)                          │ 0.80                   │  │   │
│  │    │ New (<7 days)                               │ 0.70                   │  │   │
│  │    │ Brand new (<24 hours)                       │ 0.50                   │  │   │
│  │    └─────────────────────────────────────────────────────────────────────┘  │   │
│  │                                                                              │   │
│  │ 4. Verification Status Trust (weight: 0.25)                                  │   │
│  │    ┌─────────────────────────────────────────────────────────────────────┐  │   │
│  │    │ Integrity verified (recent)                 │ 1.00                   │  │   │
│  │    │ Integrity verified (stale >7 days)          │ 0.90                   │  │   │
│  │    │ Provenance valid, integrity not checked     │ 0.70                   │  │   │
│  │    │ Provenance stale (source unavailable)       │ 0.50                   │  │   │
│  │    │ Integrity verification failed               │ 0.00                   │  │   │
│  │    └─────────────────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                     │
│  Final Trust Score = Σ(component_score × weight)                                    │
│                                                                                     │
│  Trust Thresholds:                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │ >= 0.80  │ HIGH_TRUST      │ Include in context with full confidence       │   │
│  │ >= 0.50  │ MEDIUM_TRUST    │ Include with provenance metadata visible      │   │
│  │ >= 0.30  │ LOW_TRUST       │ Include only if no better alternatives        │   │
│  │ < 0.30   │ UNTRUSTED       │ Exclude from context, flag for review         │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## Implementation

### Service Layer

```python
# src/services/context_provenance/__init__.py

from .provenance_service import ContentProvenanceService
from .integrity_service import IntegrityVerificationService
from .anomaly_detector import ContextAnomalyDetector
from .trust_scoring import TrustScoringEngine
from .quarantine_manager import QuarantineManager
from .audit_logger import ProvenanceAuditLogger
from .contracts import (
    ProvenanceRecord,
    IntegrityResult,
    AnomalyReport,
    TrustScore,
    VerifiedContext,
)

__all__ = [
    "ContentProvenanceService",
    "IntegrityVerificationService",
    "ContextAnomalyDetector",
    "TrustScoringEngine",
    "QuarantineManager",
    "ProvenanceAuditLogger",
    "ProvenanceRecord",
    "IntegrityResult",
    "AnomalyReport",
    "TrustScore",
    "VerifiedContext",
]
```

### Contract Definitions

```python
# src/services/context_provenance/contracts.py

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class IntegrityStatus(Enum):
    """Result of integrity verification."""
    VERIFIED = "verified"
    FAILED = "failed"
    HASH_MISSING = "hash_missing"
    HMAC_INVALID = "hmac_invalid"


class ProvenanceStatus(Enum):
    """Result of provenance validation."""
    VALID = "valid"
    STALE = "stale"          # Source unavailable for verification
    INVALID = "invalid"       # Provenance data doesn't match source
    MISSING = "missing"       # No provenance data recorded


class TrustLevel(Enum):
    """Trust classification for content."""
    HIGH = "high"             # >= 0.80
    MEDIUM = "medium"         # >= 0.50
    LOW = "low"               # >= 0.30
    UNTRUSTED = "untrusted"   # < 0.30


class QuarantineReason(Enum):
    """Reason for quarantining content."""
    INTEGRITY_FAILURE = "integrity_failure"
    LOW_TRUST = "low_trust"
    ANOMALY_DETECTED = "anomaly_detected"
    PROVENANCE_INVALID = "provenance_invalid"
    MANUAL_FLAG = "manual_flag"


class AnomalyType(Enum):
    """Types of detected anomalies."""
    INJECTION_PATTERN = "injection_pattern"
    STRUCTURAL_ANOMALY = "structural_anomaly"
    STATISTICAL_OUTLIER = "statistical_outlier"
    HIDDEN_INSTRUCTION = "hidden_instruction"
    OBFUSCATED_CODE = "obfuscated_code"


@dataclass
class ProvenanceRecord:
    """Complete provenance record for indexed content."""
    repository_id: str
    commit_sha: str
    author_id: str
    author_email: str
    timestamp: datetime
    branch: str
    signature: Optional[str] = None  # GPG signature if available

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "repository_id": self.repository_id,
            "commit_sha": self.commit_sha,
            "author_id": self.author_id,
            "author_email": self.author_email,
            "timestamp": self.timestamp.isoformat(),
            "branch": self.branch,
            "signature": self.signature,
        }


@dataclass
class IntegrityRecord:
    """Integrity verification data for indexed content."""
    content_hash_sha256: str
    content_hmac: str
    chunk_boundary_hash: str
    embedding_fingerprint: str
    indexed_at: datetime
    verified_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "content_hash": self.content_hash_sha256,
            "content_hmac": self.content_hmac,
            "chunk_boundary_hash": self.chunk_boundary_hash,
            "embedding_fingerprint": self.embedding_fingerprint,
            "indexed_at": self.indexed_at.isoformat(),
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
        }


@dataclass
class IntegrityResult:
    """Result of integrity verification."""
    status: IntegrityStatus
    content_hash_match: bool
    hmac_valid: bool
    verified_at: datetime
    details: Optional[str] = None

    @property
    def verified(self) -> bool:
        """Check if integrity verification passed."""
        return self.status == IntegrityStatus.VERIFIED


@dataclass
class TrustScore:
    """Trust score with component breakdown."""
    score: float  # 0.0 - 1.0
    level: TrustLevel
    components: dict[str, float]  # repository, author, age, verification
    updated_at: datetime

    @classmethod
    def compute(
        cls,
        repository_score: float,
        author_score: float,
        age_score: float,
        verification_score: float,
    ) -> "TrustScore":
        """Compute trust score from components."""
        weights = {
            "repository": 0.35,
            "author": 0.25,
            "age": 0.15,
            "verification": 0.25,
        }

        score = (
            repository_score * weights["repository"]
            + author_score * weights["author"]
            + age_score * weights["age"]
            + verification_score * weights["verification"]
        )

        # Determine trust level
        if score >= 0.80:
            level = TrustLevel.HIGH
        elif score >= 0.50:
            level = TrustLevel.MEDIUM
        elif score >= 0.30:
            level = TrustLevel.LOW
        else:
            level = TrustLevel.UNTRUSTED

        return cls(
            score=score,
            level=level,
            components={
                "repository": repository_score,
                "author": author_score,
                "age": age_score,
                "verification": verification_score,
            },
            updated_at=datetime.now(),
        )


@dataclass
class AnomalyReport:
    """Result of anomaly detection scan."""
    anomaly_score: float  # 0.0 - 1.0
    anomaly_types: list[AnomalyType]
    suspicious_spans: list[tuple[int, int, str]]  # (start, end, reason)
    details: Optional[str] = None

    @property
    def has_anomalies(self) -> bool:
        """Check if any anomalies detected above threshold."""
        return self.anomaly_score > 0.3


@dataclass
class VerifiedContext:
    """Context chunk with verification metadata."""
    content: str
    file_path: str
    provenance: ProvenanceRecord
    integrity: IntegrityResult
    trust_score: TrustScore
    anomaly_report: AnomalyReport

    @property
    def is_safe(self) -> bool:
        """Check if context passed all verification checks."""
        return (
            self.integrity.verified
            and self.trust_score.level != TrustLevel.UNTRUSTED
            and not self.anomaly_report.has_anomalies
        )


@dataclass
class QuarantineRecord:
    """Record for quarantined content."""
    chunk_id: str
    content_hash: str
    reason: QuarantineReason
    details: str
    quarantined_at: datetime
    quarantined_by: str  # "system" or user_id
    provenance: ProvenanceRecord
    review_status: str = "pending"  # pending | reviewed | released | deleted
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
```

### Core Services

```python
# src/services/context_provenance/provenance_service.py

import hashlib
import hmac
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .contracts import ProvenanceRecord, IntegrityRecord

logger = logging.getLogger(__name__)


class ContentProvenanceService:
    """
    Collects and stores provenance data for indexed content.

    Operates at index time to capture origin information
    before content enters Neptune and OpenSearch.
    """

    def __init__(
        self,
        neptune_client,
        opensearch_client,
        hmac_secret_key: str,
    ):
        """
        Initialize provenance service.

        Args:
            neptune_client: Neptune graph database client
            opensearch_client: OpenSearch client
            hmac_secret_key: Secret key for HMAC signatures (from Secrets Manager)
        """
        self.neptune = neptune_client
        self.opensearch = opensearch_client
        self._hmac_key = hmac_secret_key.encode()

    def collect_provenance(
        self,
        file_path: str,
        content: str,
        git_info: dict[str, Any],
    ) -> tuple[ProvenanceRecord, IntegrityRecord]:
        """
        Collect provenance and generate integrity records for content.

        Args:
            file_path: Path to source file
            content: File content being indexed
            git_info: Git metadata (commit, author, timestamp, etc.)

        Returns:
            Tuple of (ProvenanceRecord, IntegrityRecord)
        """
        # Build provenance record
        provenance = ProvenanceRecord(
            repository_id=git_info.get("repository_id", "unknown"),
            commit_sha=git_info.get("commit_sha", ""),
            author_id=git_info.get("author_id", ""),
            author_email=git_info.get("author_email", ""),
            timestamp=git_info.get("timestamp", datetime.now(timezone.utc)),
            branch=git_info.get("branch", "main"),
            signature=git_info.get("gpg_signature"),
        )

        # Generate integrity hashes
        content_hash = self._compute_sha256(content)
        content_hmac = self._compute_hmac(content)
        chunk_boundary_hash = self._compute_chunk_boundary_hash(content)

        integrity = IntegrityRecord(
            content_hash_sha256=content_hash,
            content_hmac=content_hmac,
            chunk_boundary_hash=chunk_boundary_hash,
            embedding_fingerprint="",  # Set after embedding generation
            indexed_at=datetime.now(timezone.utc),
        )

        logger.info(
            f"Collected provenance for {file_path}: "
            f"repo={provenance.repository_id}, commit={provenance.commit_sha[:8]}"
        )

        return provenance, integrity

    def set_embedding_fingerprint(
        self,
        integrity: IntegrityRecord,
        embedding: list[float],
    ) -> IntegrityRecord:
        """
        Add embedding fingerprint to integrity record.

        The fingerprint is a hash of the first and last 16 dimensions
        plus the vector norm, enabling detection of embedding tampering.
        """
        fingerprint_data = (
            str(embedding[:16])
            + str(embedding[-16:])
            + str(sum(x*x for x in embedding) ** 0.5)
        )
        integrity.embedding_fingerprint = self._compute_sha256(fingerprint_data)
        return integrity

    def _compute_sha256(self, content: str) -> str:
        """Compute SHA-256 hash of content."""
        return hashlib.sha256(content.encode()).hexdigest()

    def _compute_hmac(self, content: str) -> str:
        """Compute HMAC-SHA256 signature of content."""
        return hmac.new(
            self._hmac_key,
            content.encode(),
            hashlib.sha256
        ).hexdigest()

    def _compute_chunk_boundary_hash(self, content: str) -> str:
        """
        Compute hash of chunk boundaries.

        This detects if chunk boundaries have been maliciously
        shifted to hide or expose specific content.
        """
        # Hash first 100 and last 100 chars plus total length
        boundary_data = f"{content[:100]}|{content[-100:]}|{len(content)}"
        return hashlib.sha256(boundary_data.encode()).hexdigest()[:32]
```

```python
# src/services/context_provenance/integrity_service.py

import hashlib
import hmac
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .contracts import IntegrityResult, IntegrityStatus

logger = logging.getLogger(__name__)


class IntegrityVerificationService:
    """
    Verifies integrity of retrieved content.

    Operates at retrieval time to ensure content
    has not been modified since indexing.
    """

    def __init__(
        self,
        hmac_secret_key: str,
        cache_ttl_seconds: int = 300,
    ):
        """
        Initialize integrity verification service.

        Args:
            hmac_secret_key: Secret key for HMAC validation
            cache_ttl_seconds: TTL for verification cache
        """
        self._hmac_key = hmac_secret_key.encode()
        self._cache_ttl = cache_ttl_seconds
        self._verification_cache: dict[str, IntegrityResult] = {}

    def verify(
        self,
        content: str,
        stored_hash: str,
        stored_hmac: str,
        chunk_id: Optional[str] = None,
    ) -> IntegrityResult:
        """
        Verify content integrity against stored hashes.

        Args:
            content: Retrieved content to verify
            stored_hash: SHA-256 hash from index time
            stored_hmac: HMAC signature from index time
            chunk_id: Optional chunk ID for caching

        Returns:
            IntegrityResult with verification status
        """
        now = datetime.now(timezone.utc)

        # Check cache
        if chunk_id and chunk_id in self._verification_cache:
            cached = self._verification_cache[chunk_id]
            age = (now - cached.verified_at).total_seconds()
            if age < self._cache_ttl:
                return cached

        # Handle missing hashes
        if not stored_hash or not stored_hmac:
            result = IntegrityResult(
                status=IntegrityStatus.HASH_MISSING,
                content_hash_match=False,
                hmac_valid=False,
                verified_at=now,
                details="No integrity hashes stored for this content",
            )
            return result

        # Verify content hash
        computed_hash = hashlib.sha256(content.encode()).hexdigest()
        hash_match = computed_hash == stored_hash

        # Verify HMAC
        computed_hmac = hmac.new(
            self._hmac_key,
            content.encode(),
            hashlib.sha256
        ).hexdigest()
        hmac_valid = hmac.compare_digest(computed_hmac, stored_hmac)

        # Determine status
        if hash_match and hmac_valid:
            status = IntegrityStatus.VERIFIED
            details = None
        elif not hash_match:
            status = IntegrityStatus.FAILED
            details = f"Content hash mismatch: expected {stored_hash[:16]}..., got {computed_hash[:16]}..."
        else:
            status = IntegrityStatus.HMAC_INVALID
            details = "HMAC signature validation failed - possible tampering"

        result = IntegrityResult(
            status=status,
            content_hash_match=hash_match,
            hmac_valid=hmac_valid,
            verified_at=now,
            details=details,
        )

        # Cache result
        if chunk_id:
            self._verification_cache[chunk_id] = result

        if status != IntegrityStatus.VERIFIED:
            logger.warning(
                f"Integrity verification failed for chunk {chunk_id}: {status.value}"
            )

        return result

    def batch_verify(
        self,
        chunks: list[dict[str, Any]],
    ) -> dict[str, IntegrityResult]:
        """
        Verify integrity of multiple chunks.

        Args:
            chunks: List of chunk dicts with content, hash, hmac, id

        Returns:
            Dict mapping chunk_id to IntegrityResult
        """
        results = {}
        for chunk in chunks:
            result = self.verify(
                content=chunk["content"],
                stored_hash=chunk.get("integrity", {}).get("content_hash", ""),
                stored_hmac=chunk.get("integrity", {}).get("content_hmac", ""),
                chunk_id=chunk.get("id"),
            )
            results[chunk.get("id", "")] = result
        return results
```

```python
# src/services/context_provenance/trust_scoring.py

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from .contracts import TrustScore, TrustLevel, ProvenanceRecord

logger = logging.getLogger(__name__)


class TrustScoringEngine:
    """
    Computes and maintains trust scores for content sources.

    Trust scores are computed from:
    - Repository reputation
    - Author history
    - Content age
    - Verification status
    """

    # Repository trust levels
    REPO_TRUST_INTERNAL = 1.00
    REPO_TRUST_PARTNER = 0.90
    REPO_TRUST_PUBLIC_HIGH = 0.70
    REPO_TRUST_PUBLIC_LOW = 0.50
    REPO_TRUST_UNKNOWN = 0.30
    REPO_TRUST_FLAGGED = 0.00

    # Author trust levels
    AUTHOR_TRUST_EMPLOYEE = 1.00
    AUTHOR_TRUST_KNOWN = 0.90
    AUTHOR_TRUST_CONTRIBUTOR = 0.70
    AUTHOR_TRUST_FIRST_TIME = 0.50
    AUTHOR_TRUST_UNVERIFIED = 0.30
    AUTHOR_GPG_BONUS = 0.10

    def __init__(
        self,
        dynamodb_client,
        internal_org_ids: list[str],
        partner_org_ids: list[str],
    ):
        """
        Initialize trust scoring engine.

        Args:
            dynamodb_client: DynamoDB client for trust data
            internal_org_ids: List of internal organization IDs
            partner_org_ids: List of verified partner org IDs
        """
        self.dynamodb = dynamodb_client
        self.internal_orgs = set(internal_org_ids)
        self.partner_orgs = set(partner_org_ids)

        # Cache for author commit counts
        self._author_cache: dict[str, int] = {}

    def compute_trust_score(
        self,
        provenance: ProvenanceRecord,
        integrity_verified: bool,
        verification_age_days: float = 0,
    ) -> TrustScore:
        """
        Compute trust score for content.

        Args:
            provenance: Content provenance record
            integrity_verified: Whether integrity check passed
            verification_age_days: Days since last verification

        Returns:
            TrustScore with component breakdown
        """
        # Compute repository trust
        repo_score = self._compute_repository_trust(provenance.repository_id)

        # Compute author trust
        author_score = self._compute_author_trust(
            provenance.author_id,
            provenance.author_email,
            has_gpg=provenance.signature is not None,
        )

        # Compute age trust
        content_age = datetime.now(timezone.utc) - provenance.timestamp
        age_score = self._compute_age_trust(content_age)

        # Compute verification trust
        verification_score = self._compute_verification_trust(
            integrity_verified,
            verification_age_days,
        )

        return TrustScore.compute(
            repository_score=repo_score,
            author_score=author_score,
            age_score=age_score,
            verification_score=verification_score,
        )

    def _compute_repository_trust(self, repository_id: str) -> float:
        """Compute trust score for repository."""
        # Parse org from repository_id (format: org/repo)
        org = repository_id.split("/")[0] if "/" in repository_id else repository_id

        if org in self.internal_orgs:
            return self.REPO_TRUST_INTERNAL
        elif org in self.partner_orgs:
            return self.REPO_TRUST_PARTNER
        else:
            # Could enhance with GitHub API data for public repos
            return self.REPO_TRUST_UNKNOWN

    def _compute_author_trust(
        self,
        author_id: str,
        author_email: str,
        has_gpg: bool,
    ) -> float:
        """Compute trust score for author."""
        # Get commit count from cache or database
        commit_count = self._get_author_commit_count(author_id)

        if commit_count > 10:
            base_score = self.AUTHOR_TRUST_KNOWN
        elif commit_count >= 1:
            base_score = self.AUTHOR_TRUST_CONTRIBUTOR
        else:
            base_score = self.AUTHOR_TRUST_FIRST_TIME

        # Add GPG signature bonus
        if has_gpg:
            base_score = min(1.0, base_score + self.AUTHOR_GPG_BONUS)

        return base_score

    def _compute_age_trust(self, age: timedelta) -> float:
        """Compute trust score based on content age."""
        days = age.total_seconds() / 86400

        if days > 90:
            return 1.00  # Established
        elif days > 30:
            return 0.90  # Stable
        elif days > 7:
            return 0.80  # Recent
        elif days > 1:
            return 0.70  # New
        else:
            return 0.50  # Brand new

    def _compute_verification_trust(
        self,
        integrity_verified: bool,
        verification_age_days: float,
    ) -> float:
        """Compute trust score based on verification status."""
        if not integrity_verified:
            return 0.00

        if verification_age_days <= 1:
            return 1.00  # Recent verification
        elif verification_age_days <= 7:
            return 0.90  # Slightly stale
        else:
            return 0.70  # Stale verification

    def _get_author_commit_count(self, author_id: str) -> int:
        """Get verified commit count for author."""
        if author_id in self._author_cache:
            return self._author_cache[author_id]

        # Query DynamoDB for author history
        # In production, this would query aura-author-trust-{env}
        # For now, return 0 for unknown authors
        return 0

    def update_author_trust(
        self,
        author_id: str,
        commit_verified: bool,
    ) -> None:
        """Update author trust based on new verified commit."""
        if commit_verified:
            self._author_cache[author_id] = (
                self._author_cache.get(author_id, 0) + 1
            )
```

```python
# src/services/context_provenance/anomaly_detector.py

import logging
import re
from typing import Any, Optional

from .contracts import AnomalyReport, AnomalyType

logger = logging.getLogger(__name__)


class ContextAnomalyDetector:
    """
    Detects anomalies in retrieved context before LLM processing.

    Combines:
    - Embedding-based injection detection (reuses ADR-065 corpus)
    - Structural anomaly detection (unusual AST patterns)
    - Statistical outlier detection
    - Hidden instruction scanning
    """

    # Patterns indicating hidden instructions
    HIDDEN_INSTRUCTION_PATTERNS = [
        r"(?i)ignore\s+(?:all\s+)?(?:previous|above|prior)\s+instructions?",
        r"(?i)disregard\s+(?:all\s+)?(?:previous|above|prior)",
        r"(?i)you\s+are\s+now\s+(?:a|an|the)",
        r"(?i)act\s+as\s+(?:if\s+you\s+were|a|an)",
        r"(?i)pretend\s+(?:you\s+are|to\s+be)",
        r"(?i)system\s*:\s*",
        r"(?i)\[\s*system\s*\]",
        r"(?i)<<\s*SYS\s*>>",
    ]

    # Obfuscation patterns
    OBFUSCATION_PATTERNS = [
        r"eval\s*\(",
        r"exec\s*\(",
        r"compile\s*\(",
        r"__import__\s*\(",
        r"getattr\s*\(",
        r"setattr\s*\(",
        r"base64\s*\.\s*b64decode",
        r"codecs\s*\.\s*decode",
        r"\\x[0-9a-fA-F]{2}",  # Hex escapes
        r"\\u[0-9a-fA-F]{4}",  # Unicode escapes
    ]

    def __init__(
        self,
        embedding_detector,  # From ADR-065
        opensearch_client,
        anomaly_threshold: float = 0.7,
    ):
        """
        Initialize anomaly detector.

        Args:
            embedding_detector: EmbeddingThreatDetector from ADR-065
            opensearch_client: OpenSearch client for statistical analysis
            anomaly_threshold: Threshold for flagging anomalies
        """
        self.embedding_detector = embedding_detector
        self.opensearch = opensearch_client
        self.anomaly_threshold = anomaly_threshold

        # Compile patterns
        self._hidden_patterns = [
            re.compile(p) for p in self.HIDDEN_INSTRUCTION_PATTERNS
        ]
        self._obfuscation_patterns = [
            re.compile(p) for p in self.OBFUSCATION_PATTERNS
        ]

    async def scan(
        self,
        content: str,
        file_path: Optional[str] = None,
        repository_id: Optional[str] = None,
    ) -> AnomalyReport:
        """
        Scan content for anomalies.

        Args:
            content: Content to scan
            file_path: Optional file path for context
            repository_id: Optional repo for statistical comparison

        Returns:
            AnomalyReport with findings
        """
        anomaly_types = []
        suspicious_spans = []
        max_score = 0.0

        # Check for injection patterns using ADR-065 embedding detector
        embedding_result = await self.embedding_detector.detect(content)
        if embedding_result["max_similarity"] > 0.7:
            anomaly_types.append(AnomalyType.INJECTION_PATTERN)
            max_score = max(max_score, embedding_result["max_similarity"])

        # Check for hidden instructions in comments and strings
        hidden_matches = self._scan_hidden_instructions(content)
        if hidden_matches:
            anomaly_types.append(AnomalyType.HIDDEN_INSTRUCTION)
            suspicious_spans.extend(hidden_matches)
            max_score = max(max_score, 0.9)  # High confidence for pattern match

        # Check for obfuscation patterns
        obfuscation_matches = self._scan_obfuscation(content)
        if obfuscation_matches:
            anomaly_types.append(AnomalyType.OBFUSCATED_CODE)
            suspicious_spans.extend(obfuscation_matches)
            max_score = max(max_score, 0.6)

        # Statistical outlier detection (if repository context available)
        if repository_id:
            is_outlier, outlier_reason = await self._check_statistical_outlier(
                content, repository_id
            )
            if is_outlier:
                anomaly_types.append(AnomalyType.STATISTICAL_OUTLIER)
                max_score = max(max_score, 0.5)

        return AnomalyReport(
            anomaly_score=max_score,
            anomaly_types=anomaly_types,
            suspicious_spans=suspicious_spans,
            details=f"Found {len(anomaly_types)} anomaly types" if anomaly_types else None,
        )

    def _scan_hidden_instructions(
        self,
        content: str,
    ) -> list[tuple[int, int, str]]:
        """Scan for hidden instruction patterns."""
        matches = []

        # Extract comments and strings
        comment_pattern = re.compile(r'#.*$|"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'', re.MULTILINE)

        for match in comment_pattern.finditer(content):
            comment_text = match.group()

            for pattern in self._hidden_patterns:
                if pattern.search(comment_text):
                    matches.append((
                        match.start(),
                        match.end(),
                        f"Hidden instruction pattern in comment/string",
                    ))
                    break

        return matches

    def _scan_obfuscation(
        self,
        content: str,
    ) -> list[tuple[int, int, str]]:
        """Scan for code obfuscation patterns."""
        matches = []

        for pattern in self._obfuscation_patterns:
            for match in pattern.finditer(content):
                matches.append((
                    match.start(),
                    match.end(),
                    f"Potential obfuscation: {match.group()[:50]}",
                ))

        return matches

    async def _check_statistical_outlier(
        self,
        content: str,
        repository_id: str,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if content is a statistical outlier for the repository.

        Compares content characteristics against repository norms.
        """
        # Compute content characteristics
        char_count = len(content)
        line_count = content.count('\n') + 1
        avg_line_length = char_count / line_count if line_count > 0 else 0

        # Query repository statistics from OpenSearch
        # (In production, this queries pre-computed stats)

        # Simplified outlier detection
        if avg_line_length > 500:  # Very long lines unusual for code
            return True, "Abnormally long lines"

        if char_count > 100000:  # Very large single chunk
            return True, "Abnormally large content chunk"

        return False, None
```

```python
# src/services/context_provenance/quarantine_manager.py

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from .contracts import QuarantineRecord, QuarantineReason, ProvenanceRecord

logger = logging.getLogger(__name__)


class QuarantineManager:
    """
    Manages quarantined content that failed verification.

    Quarantined content is:
    - Removed from active retrieval pool
    - Stored in separate quarantine table
    - Flagged for HITL review
    - Logged to audit trail
    """

    def __init__(
        self,
        dynamodb_client,
        neptune_client,
        opensearch_client,
        sns_client,
        table_name: str = "aura-context-quarantine",
        alert_topic_arn: Optional[str] = None,
    ):
        """
        Initialize quarantine manager.

        Args:
            dynamodb_client: DynamoDB client
            neptune_client: Neptune client for graph updates
            opensearch_client: OpenSearch client for index updates
            sns_client: SNS client for alerts
            table_name: DynamoDB table for quarantine records
            alert_topic_arn: SNS topic for quarantine alerts
        """
        self.dynamodb = dynamodb_client
        self.neptune = neptune_client
        self.opensearch = opensearch_client
        self.sns = sns_client
        self.table_name = table_name
        self.alert_topic = alert_topic_arn

    async def quarantine(
        self,
        chunk_id: str,
        content: str,
        reason: QuarantineReason,
        details: str,
        provenance: ProvenanceRecord,
    ) -> QuarantineRecord:
        """
        Quarantine a content chunk.

        Args:
            chunk_id: Unique chunk identifier
            content: Content being quarantined
            reason: Reason for quarantine
            details: Detailed explanation
            provenance: Content provenance

        Returns:
            QuarantineRecord
        """
        record = QuarantineRecord(
            chunk_id=chunk_id,
            content_hash=self._compute_hash(content),
            reason=reason,
            details=details,
            quarantined_at=datetime.now(timezone.utc),
            quarantined_by="system",
            provenance=provenance,
        )

        # Store in quarantine table
        await self._store_quarantine_record(record)

        # Update Neptune vertex status
        await self._update_neptune_status(chunk_id, "QUARANTINED")

        # Update OpenSearch document status
        await self._update_opensearch_status(chunk_id, "QUARANTINED")

        # Send alert
        if self.alert_topic:
            await self._send_alert(record)

        logger.warning(
            f"Quarantined chunk {chunk_id}: {reason.value} - {details}"
        )

        return record

    async def review(
        self,
        chunk_id: str,
        reviewer_id: str,
        decision: str,  # "release" | "delete"
        notes: Optional[str] = None,
    ) -> bool:
        """
        Review quarantined content.

        Args:
            chunk_id: Quarantined chunk ID
            reviewer_id: Reviewer user ID
            decision: Review decision
            notes: Optional review notes

        Returns:
            True if review processed successfully
        """
        if decision == "release":
            # Restore to active status
            await self._update_neptune_status(chunk_id, "ACTIVE")
            await self._update_opensearch_status(chunk_id, "ACTIVE")
            review_status = "released"
        else:
            # Mark for deletion
            await self._delete_from_neptune(chunk_id)
            await self._delete_from_opensearch(chunk_id)
            review_status = "deleted"

        # Update quarantine record
        await self._update_quarantine_record(
            chunk_id,
            review_status=review_status,
            reviewed_by=reviewer_id,
            reviewed_at=datetime.now(timezone.utc),
        )

        logger.info(
            f"Quarantine review complete for {chunk_id}: {decision} by {reviewer_id}"
        )

        return True

    async def get_pending_reviews(
        self,
        limit: int = 50,
    ) -> list[QuarantineRecord]:
        """Get quarantine records pending review."""
        # Query DynamoDB for pending records
        response = self.dynamodb.query(
            TableName=self.table_name,
            IndexName="review-status-index",
            KeyConditionExpression="review_status = :status",
            ExpressionAttributeValues={":status": {"S": "pending"}},
            Limit=limit,
        )

        records = []
        for item in response.get("Items", []):
            records.append(self._item_to_record(item))

        return records

    def _compute_hash(self, content: str) -> str:
        """Compute SHA-256 hash."""
        import hashlib
        return hashlib.sha256(content.encode()).hexdigest()

    async def _store_quarantine_record(self, record: QuarantineRecord) -> None:
        """Store record in DynamoDB."""
        self.dynamodb.put_item(
            TableName=self.table_name,
            Item={
                "chunk_id": {"S": record.chunk_id},
                "content_hash": {"S": record.content_hash},
                "reason": {"S": record.reason.value},
                "details": {"S": record.details},
                "quarantined_at": {"S": record.quarantined_at.isoformat()},
                "quarantined_by": {"S": record.quarantined_by},
                "review_status": {"S": record.review_status},
                "provenance": {"S": str(record.provenance.to_dict())},
            }
        )

    async def _update_neptune_status(self, chunk_id: str, status: str) -> None:
        """Update vertex status in Neptune."""
        query = f"""
        g.V().has('entity_id', '{chunk_id}')
         .property('quarantine_status', '{status}')
        """
        self.neptune.client.submit(query).all().result()

    async def _update_opensearch_status(self, chunk_id: str, status: str) -> None:
        """Update document status in OpenSearch."""
        self.opensearch.update(
            index="aura-code-embeddings",
            id=chunk_id,
            body={"doc": {"status": status}},
        )

    async def _send_alert(self, record: QuarantineRecord) -> None:
        """Send SNS alert for quarantine event."""
        message = {
            "event": "CONTEXT_QUARANTINED",
            "chunk_id": record.chunk_id,
            "reason": record.reason.value,
            "details": record.details,
            "repository": record.provenance.repository_id,
            "commit": record.provenance.commit_sha,
            "timestamp": record.quarantined_at.isoformat(),
        }

        self.sns.publish(
            TopicArn=self.alert_topic,
            Message=str(message),
            Subject="Context Quarantine Alert",
        )
```

```python
# src/services/context_provenance/audit_logger.py

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ProvenanceAuditEvent(Enum):
    """Types of provenance audit events."""
    CONTENT_INDEXED = "content_indexed"
    INTEGRITY_VERIFIED = "integrity_verified"
    INTEGRITY_FAILED = "integrity_failed"
    TRUST_COMPUTED = "trust_computed"
    LOW_TRUST_EXCLUDED = "low_trust_excluded"
    ANOMALY_DETECTED = "anomaly_detected"
    CONTENT_QUARANTINED = "content_quarantined"
    QUARANTINE_REVIEWED = "quarantine_reviewed"
    CONTENT_SERVED = "content_served"


class ProvenanceAuditLogger:
    """
    Logs all provenance-related events for compliance.

    Audit events are written to:
    - CloudWatch Logs (immediate, searchable)
    - DynamoDB (long-term retention, queryable)
    - EventBridge (for downstream processing)
    """

    def __init__(
        self,
        dynamodb_client,
        eventbridge_client,
        cloudwatch_logs_client,
        table_name: str = "aura-provenance-audit",
        log_group: str = "/aura/provenance/audit",
        event_bus: str = "aura-security-events",
    ):
        """
        Initialize audit logger.

        Args:
            dynamodb_client: DynamoDB client
            eventbridge_client: EventBridge client
            cloudwatch_logs_client: CloudWatch Logs client
            table_name: DynamoDB table for audit records
            log_group: CloudWatch log group
            event_bus: EventBridge event bus name
        """
        self.dynamodb = dynamodb_client
        self.eventbridge = eventbridge_client
        self.logs = cloudwatch_logs_client
        self.table_name = table_name
        self.log_group = log_group
        self.event_bus = event_bus

    async def log(
        self,
        event_type: ProvenanceAuditEvent,
        chunk_id: str,
        details: dict[str, Any],
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """
        Log a provenance audit event.

        Args:
            event_type: Type of audit event
            chunk_id: Content chunk ID
            details: Event details
            user_id: Optional user ID
            session_id: Optional session ID

        Returns:
            Audit record ID
        """
        import uuid

        audit_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)

        record = {
            "audit_id": audit_id,
            "event_type": event_type.value,
            "chunk_id": chunk_id,
            "timestamp": timestamp.isoformat(),
            "details": details,
            "user_id": user_id,
            "session_id": session_id,
        }

        # Write to all destinations concurrently
        await self._write_to_dynamodb(record)
        await self._write_to_cloudwatch(record)

        # Send to EventBridge for security-critical events
        if event_type in (
            ProvenanceAuditEvent.INTEGRITY_FAILED,
            ProvenanceAuditEvent.ANOMALY_DETECTED,
            ProvenanceAuditEvent.CONTENT_QUARANTINED,
        ):
            await self._send_to_eventbridge(record)

        logger.info(
            f"Audit event logged: {event_type.value} for chunk {chunk_id}"
        )

        return audit_id

    async def query_by_chunk(
        self,
        chunk_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        """Query audit events for a specific chunk."""
        key_condition = "chunk_id = :chunk_id"
        expression_values = {":chunk_id": {"S": chunk_id}}

        if start_time and end_time:
            key_condition += " AND #ts BETWEEN :start AND :end"
            expression_values[":start"] = {"S": start_time.isoformat()}
            expression_values[":end"] = {"S": end_time.isoformat()}

        response = self.dynamodb.query(
            TableName=self.table_name,
            IndexName="chunk-id-index",
            KeyConditionExpression=key_condition,
            ExpressionAttributeValues=expression_values,
            ExpressionAttributeNames={"#ts": "timestamp"} if start_time else None,
        )

        return response.get("Items", [])

    async def query_by_event_type(
        self,
        event_type: ProvenanceAuditEvent,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query recent audit events of a specific type."""
        response = self.dynamodb.query(
            TableName=self.table_name,
            IndexName="event-type-index",
            KeyConditionExpression="event_type = :type",
            ExpressionAttributeValues={":type": {"S": event_type.value}},
            Limit=limit,
            ScanIndexForward=False,  # Most recent first
        )

        return response.get("Items", [])

    async def _write_to_dynamodb(self, record: dict[str, Any]) -> None:
        """Write audit record to DynamoDB."""
        self.dynamodb.put_item(
            TableName=self.table_name,
            Item={
                "audit_id": {"S": record["audit_id"]},
                "event_type": {"S": record["event_type"]},
                "chunk_id": {"S": record["chunk_id"]},
                "timestamp": {"S": record["timestamp"]},
                "details": {"S": json.dumps(record["details"])},
                "user_id": {"S": record["user_id"] or "system"},
                "session_id": {"S": record["session_id"] or ""},
            }
        )

    async def _write_to_cloudwatch(self, record: dict[str, Any]) -> None:
        """Write audit record to CloudWatch Logs."""
        self.logs.put_log_events(
            logGroupName=self.log_group,
            logStreamName=f"provenance-{datetime.now().strftime('%Y-%m-%d')}",
            logEvents=[{
                "timestamp": int(datetime.now().timestamp() * 1000),
                "message": json.dumps(record),
            }]
        )

    async def _send_to_eventbridge(self, record: dict[str, Any]) -> None:
        """Send security-critical event to EventBridge."""
        self.eventbridge.put_events(
            Entries=[{
                "Source": "aura.context-provenance",
                "DetailType": f"Context Provenance - {record['event_type']}",
                "Detail": json.dumps(record),
                "EventBusName": self.event_bus,
            }]
        )
```

### Files Created

| File | Purpose |
|------|---------|
| `src/services/context_provenance/__init__.py` | Package initialization |
| `src/services/context_provenance/contracts.py` | Pydantic/dataclass schemas |
| `src/services/context_provenance/provenance_service.py` | Index-time provenance collection |
| `src/services/context_provenance/integrity_service.py` | Retrieval-time integrity verification |
| `src/services/context_provenance/trust_scoring.py` | Trust score computation |
| `src/services/context_provenance/anomaly_detector.py` | Context anomaly detection |
| `src/services/context_provenance/quarantine_manager.py` | Suspicious content isolation |
| `src/services/context_provenance/audit_logger.py` | Compliance audit logging |
| `src/services/context_provenance/config.py` | Configuration management |
| `tests/services/test_context_provenance/` | Test suite (400+ tests) |
| `deploy/cloudformation/context-provenance.yaml` | Infrastructure resources |

### CloudFormation Resources

```yaml
# deploy/cloudformation/context-provenance.yaml

AWSTemplateFormatVersion: '2010-09-09'
Description: 'Project Aura - Layer 8.4 - Context Provenance Infrastructure'

Parameters:
  ProjectName:
    Type: String
    Default: aura
  Environment:
    Type: String
    AllowedValues: [dev, qa, prod]
  DataEncryptionKeyArn:
    Type: String
    Description: KMS key ARN for data encryption

Resources:
  # DynamoDB table for quarantine records
  QuarantineTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub '${ProjectName}-context-quarantine-${Environment}'
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: chunk_id
          AttributeType: S
        - AttributeName: quarantined_at
          AttributeType: S
        - AttributeName: review_status
          AttributeType: S
      KeySchema:
        - AttributeName: chunk_id
          KeyType: HASH
        - AttributeName: quarantined_at
          KeyType: RANGE
      GlobalSecondaryIndexes:
        - IndexName: review-status-index
          KeySchema:
            - AttributeName: review_status
              KeyType: HASH
            - AttributeName: quarantined_at
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: true
      SSESpecification:
        SSEEnabled: true
        SSEType: KMS
        KMSMasterKeyId: !Ref DataEncryptionKeyArn
      Tags:
        - Key: Project
          Value: !Ref ProjectName
        - Key: Environment
          Value: !Ref Environment

  # DynamoDB table for provenance audit
  ProvenanceAuditTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub '${ProjectName}-provenance-audit-${Environment}'
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: audit_id
          AttributeType: S
        - AttributeName: timestamp
          AttributeType: S
        - AttributeName: chunk_id
          AttributeType: S
        - AttributeName: event_type
          AttributeType: S
      KeySchema:
        - AttributeName: audit_id
          KeyType: HASH
        - AttributeName: timestamp
          KeyType: RANGE
      GlobalSecondaryIndexes:
        - IndexName: chunk-id-index
          KeySchema:
            - AttributeName: chunk_id
              KeyType: HASH
            - AttributeName: timestamp
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
        - IndexName: event-type-index
          KeySchema:
            - AttributeName: event_type
              KeyType: HASH
            - AttributeName: timestamp
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: true
      SSESpecification:
        SSEEnabled: true
        SSEType: KMS
        KMSMasterKeyId: !Ref DataEncryptionKeyArn
      TimeToLiveSpecification:
        AttributeName: ttl
        Enabled: true
      Tags:
        - Key: Project
          Value: !Ref ProjectName
        - Key: Environment
          Value: !Ref Environment

  # DynamoDB table for author trust data
  AuthorTrustTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub '${ProjectName}-author-trust-${Environment}'
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: author_id
          AttributeType: S
        - AttributeName: repository_id
          AttributeType: S
      KeySchema:
        - AttributeName: author_id
          KeyType: HASH
        - AttributeName: repository_id
          KeyType: RANGE
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: true
      SSESpecification:
        SSEEnabled: true
        SSEType: KMS
        KMSMasterKeyId: !Ref DataEncryptionKeyArn
      Tags:
        - Key: Project
          Value: !Ref ProjectName
        - Key: Environment
          Value: !Ref Environment

  # SNS topic for quarantine alerts
  QuarantineAlertTopic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: !Sub '${ProjectName}-quarantine-alerts-${Environment}'
      KmsMasterKeyId: alias/aws/sns
      Tags:
        - Key: Project
          Value: !Ref ProjectName
        - Key: Environment
          Value: !Ref Environment

  # CloudWatch log group for provenance audit
  ProvenanceAuditLogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: !Sub '/aura/provenance/audit/${Environment}'
      RetentionInDays: 365
      KmsKeyId: !Ref DataEncryptionKeyArn
      Tags:
        - Key: Project
          Value: !Ref ProjectName
        - Key: Environment
          Value: !Ref Environment

  # Secrets Manager secret for HMAC key
  HmacSecretKey:
    Type: AWS::SecretsManager::Secret
    Properties:
      Name: !Sub '${ProjectName}/provenance/hmac-key-${Environment}'
      Description: HMAC secret key for content integrity signatures
      GenerateSecretString:
        SecretStringTemplate: '{}'
        GenerateStringKey: hmac_key
        PasswordLength: 64
        ExcludeCharacters: '"@/\'
      KmsKeyId: !Ref DataEncryptionKeyArn
      Tags:
        - Key: Project
          Value: !Ref ProjectName
        - Key: Environment
          Value: !Ref Environment

  # CloudWatch alarm for high quarantine rate
  HighQuarantineRateAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: !Sub '${ProjectName}-high-quarantine-rate-${Environment}'
      AlarmDescription: Alerts when quarantine rate exceeds threshold
      MetricName: QuarantinedChunks
      Namespace: !Sub '${ProjectName}/ContextProvenance'
      Statistic: Sum
      Period: 300
      EvaluationPeriods: 3
      Threshold: 50
      ComparisonOperator: GreaterThanThreshold
      TreatMissingData: notBreaching
      AlarmActions:
        - !Ref QuarantineAlertTopic

  # CloudWatch alarm for integrity failures
  IntegrityFailureAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: !Sub '${ProjectName}-integrity-failures-${Environment}'
      AlarmDescription: Alerts when integrity verification failures spike
      MetricName: IntegrityVerificationFailed
      Namespace: !Sub '${ProjectName}/ContextProvenance'
      Statistic: Sum
      Period: 60
      EvaluationPeriods: 3
      Threshold: 10
      ComparisonOperator: GreaterThanThreshold
      TreatMissingData: notBreaching
      AlarmActions:
        - !Ref QuarantineAlertTopic

Outputs:
  QuarantineTableName:
    Description: Quarantine DynamoDB table name
    Value: !Ref QuarantineTable
    Export:
      Name: !Sub '${ProjectName}-quarantine-table-${Environment}'

  ProvenanceAuditTableName:
    Description: Provenance audit DynamoDB table name
    Value: !Ref ProvenanceAuditTable
    Export:
      Name: !Sub '${ProjectName}-provenance-audit-table-${Environment}'

  HmacSecretArn:
    Description: HMAC secret key ARN
    Value: !Ref HmacSecretKey
    Export:
      Name: !Sub '${ProjectName}-hmac-secret-arn-${Environment}'

  QuarantineAlertTopicArn:
    Description: Quarantine alert SNS topic ARN
    Value: !Ref QuarantineAlertTopic
    Export:
      Name: !Sub '${ProjectName}-quarantine-alert-topic-${Environment}'
```

## Cost Analysis

### Monthly Cost Projections

| Component | Unit Cost | Volume/Month | Monthly Cost |
|-----------|-----------|--------------|--------------|
| **DynamoDB (3 tables)** | On-demand | 10M reads, 2M writes | ~$15 |
| **OpenSearch (enhanced)** | Existing cluster | No additional cost | $0 |
| **Neptune (enhanced)** | Existing cluster | No additional cost | $0 |
| **CloudWatch Logs** | $0.50/GB | 5 GB | ~$2.50 |
| **Secrets Manager** | $0.40/secret | 1 secret | ~$0.40 |
| **SNS** | $0.50/M messages | 10K messages | ~$0.01 |
| **EventBridge** | $1/M events | 100K events | ~$0.10 |
| **Compute (verification)** | Lambda/EKS | Integrated with retrieval | ~$5 |
| **Total** | | | **~$23/month** |

### Cost Optimization Strategies

1. **Verification caching** - Cache integrity verification results for 5 minutes
2. **Batch verification** - Verify multiple chunks in single call
3. **DynamoDB TTL** - Auto-expire old audit records after retention period
4. **Lazy provenance validation** - Skip full validation for HIGH_TRUST sources

## Testing Strategy

### Test Pyramid

| Tier | Tests | Coverage |
|------|-------|----------|
| Unit Tests | 200 | Contracts, hashing, trust scoring |
| Integration Tests | 100 | Full verification pipeline, DynamoDB, OpenSearch |
| Security Tests | 80 | Tamper detection, bypass attempts |
| Regression Tests | 50 | Golden set preservation |
| **Total** | **430** | |

### Security Test Cases

```python
# tests/services/test_context_provenance/test_security.py

class TestTamperDetection:
    """Test that content tampering is detected."""

    async def test_content_modification_detected(self, integrity_service):
        """Modified content fails integrity check."""
        original = "def validate(x): return x > 0"
        stored_hash = hashlib.sha256(original.encode()).hexdigest()

        modified = "def validate(x): return True  # always pass"

        result = integrity_service.verify(
            content=modified,
            stored_hash=stored_hash,
            stored_hmac="valid_hmac",
        )

        assert result.status == IntegrityStatus.FAILED
        assert not result.content_hash_match

    async def test_hmac_forgery_detected(self, integrity_service):
        """Forged HMAC signature is detected."""
        content = "legitimate code"
        stored_hash = hashlib.sha256(content.encode()).hexdigest()
        forged_hmac = "0" * 64  # Attacker's forged signature

        result = integrity_service.verify(
            content=content,
            stored_hash=stored_hash,
            stored_hmac=forged_hmac,
        )

        assert result.status == IntegrityStatus.HMAC_INVALID


class TestProvenanceValidation:
    """Test provenance validation edge cases."""

    async def test_missing_provenance_flagged(self, provenance_verifier):
        """Content without provenance gets low trust score."""
        chunk = {"content": "code", "provenance": None}

        result = await provenance_verifier.verify(chunk)

        assert result.trust_score.level == TrustLevel.UNTRUSTED

    async def test_stale_provenance_detected(self, provenance_verifier):
        """Provenance pointing to deleted repo is flagged stale."""
        chunk = {
            "content": "code",
            "provenance": {
                "repository_id": "deleted-org/deleted-repo",
                "commit_sha": "abc123",
            }
        }

        result = await provenance_verifier.verify(chunk)

        assert result.provenance_status == ProvenanceStatus.STALE


class TestAnomalyDetection:
    """Test anomaly detection capabilities."""

    @pytest.mark.parametrize("malicious_content,expected_anomaly", [
        ('# ignore previous instructions', AnomalyType.HIDDEN_INSTRUCTION),
        ('exec(base64.b64decode("..."))', AnomalyType.OBFUSCATED_CODE),
        ('getattr(obj, "__" + "class" + "__")', AnomalyType.OBFUSCATED_CODE),
    ])
    async def test_malicious_patterns_detected(
        self,
        anomaly_detector,
        malicious_content,
        expected_anomaly,
    ):
        """Malicious patterns in content are flagged."""
        result = await anomaly_detector.scan(malicious_content)

        assert result.has_anomalies
        assert expected_anomaly in result.anomaly_types
```

## Implementation Phases

### Phase 1: Foundation (Weeks 1-2)

| Task | Deliverable |
|------|-------------|
| Implement contracts.py | All data classes and enums |
| Implement provenance_service.py | Index-time provenance collection |
| Implement integrity_service.py | Hash verification logic |
| Deploy HMAC secret | Secrets Manager configuration |
| Unit tests | 200 tests |

### Phase 2: Trust Scoring (Weeks 3-4)

| Task | Deliverable |
|------|-------------|
| Implement trust_scoring.py | Trust score computation |
| Create author trust table | DynamoDB table + GSIs |
| Integrate with ContextRetrievalService | Pre-retrieval trust checks |
| Integration tests | 50 tests |

### Phase 3: Anomaly Detection (Weeks 5-6)

| Task | Deliverable |
|------|-------------|
| Implement anomaly_detector.py | Pattern + embedding detection |
| Integrate ADR-065 threat corpus | Reuse embedding detector |
| Implement quarantine_manager.py | Isolation workflow |
| Security tests | 80 tests |

### Phase 4: Audit and Compliance (Weeks 7-8)

| Task | Deliverable |
|------|-------------|
| Implement audit_logger.py | Multi-destination logging |
| Deploy CloudFormation resources | DynamoDB, SNS, CloudWatch |
| Create CloudWatch dashboards | Provenance metrics |
| Regression tests | 50 tests |

### Phase 5: Production Hardening (Week 9)

| Task | Deliverable |
|------|-------------|
| Performance optimization | Caching, batching |
| HITL review UI | Quarantine review interface |
| Runbook creation | Operations documentation |
| End-to-end testing | Full pipeline validation |

## GovCloud Compatibility

| Service | GovCloud Available | Notes |
|---------|-------------------|-------|
| DynamoDB | Yes | Full feature parity |
| Neptune | Yes | Provisioned only |
| OpenSearch | Yes | k-NN supported |
| Secrets Manager | Yes | Full feature parity |
| SNS | Yes | FIFO not available |
| EventBridge | Yes | Full feature parity |
| CloudWatch | Yes | Full feature parity |

**GovCloud-Specific Requirements:**
- Use `${AWS::Partition}` in all ARNs
- Neptune must use provisioned instances (not Serverless)
- Audit log retention must meet CMMC requirements (1+ year)
- HMAC key must use FIPS-validated algorithms

## Consequences

### Positive

1. **Tamper detection** - Modified content detected before reaching LLM
2. **Source traceability** - Full provenance chain for all indexed content
3. **Trust-based filtering** - Low-trust content excluded or deprioritized
4. **Anomaly prevention** - Injection patterns caught in context
5. **Compliance ready** - Complete audit trail for CMMC/SOX
6. **Quarantine workflow** - Suspicious content isolated for review
7. **Defense in depth** - Complements ADR-065 user input sanitization

### Negative

1. **Storage overhead** - Additional metadata per indexed chunk (~2KB)
2. **Retrieval latency** - ~10-20ms added for verification
3. **Index migration** - Existing content needs provenance backfill
4. **Operational complexity** - Quarantine review requires staffing

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| False positives block legitimate code | Medium | Medium | Configurable thresholds, HITL review |
| Verification latency exceeds budget | Low | Medium | Caching, batch verification |
| Provenance backfill incomplete | Medium | Low | Gradual migration, trust decay for unverified |
| HMAC key compromise | Low | High | Key rotation, Secrets Manager audit logging |

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Tampered content detection rate | >99% | Simulated tampering tests |
| Verification latency P95 | <50ms | CloudWatch metrics |
| Quarantine review SLA | <24 hours | DynamoDB timestamps |
| False positive rate | <0.1% | Production monitoring |
| Provenance coverage | 100% | New content only |

## References

1. ADR-065: Semantic Guardrails Engine
2. ADR-063: Constitutional AI Integration
3. ADR-034: Context Engineering
4. NIST SP 800-53 SI-7: Software, Firmware, and Information Integrity
5. CMMC Practice SI.L2-3.14.6: Monitor communications for attacks
6. OWASP LLM Top 10: LLM07 Insecure Plugin Design (context injection)
7. Neptune Graph Data Model: `docs/database/NEPTUNE_SCHEMA.md`
8. OpenSearch Index Configuration: `docs/database/OPENSEARCH_INDEXES.md`
