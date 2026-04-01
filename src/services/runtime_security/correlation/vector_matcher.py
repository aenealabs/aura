"""
Project Aura - OpenSearch Vector Matcher

Semantic similarity search against vulnerability patterns using
OpenSearch knn_vector queries.

Based on ADR-083: Runtime Agent Security Platform

Integration:
- OpenSearch vector database
- Hybrid GraphRAG semantic search
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VulnerabilityMatch:
    """Immutable match result from vector similarity search."""

    match_id: str
    vulnerability_id: str
    vulnerability_type: str
    description: str
    similarity_score: float
    source_file: Optional[str] = None
    source_line: Optional[int] = None
    cwe_id: Optional[str] = None
    severity: str = "medium"
    remediation_hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "match_id": self.match_id,
            "vulnerability_id": self.vulnerability_id,
            "vulnerability_type": self.vulnerability_type,
            "description": self.description,
            "similarity_score": round(self.similarity_score, 4),
            "source_file": self.source_file,
            "source_line": self.source_line,
            "cwe_id": self.cwe_id,
            "severity": self.severity,
            "remediation_hint": self.remediation_hint,
        }


@dataclass(frozen=True)
class MatchResult:
    """Immutable result of a vector matching operation."""

    result_id: str
    query_text: str
    matches: tuple[VulnerabilityMatch, ...]
    total_matches: int
    query_latency_ms: float
    timestamp: datetime

    @property
    def has_matches(self) -> bool:
        """True if any vulnerability matches were found."""
        return len(self.matches) > 0

    @property
    def best_match(self) -> Optional[VulnerabilityMatch]:
        """Highest similarity match."""
        if not self.matches:
            return None
        return max(self.matches, key=lambda m: m.similarity_score)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "result_id": self.result_id,
            "query_text": self.query_text[:200],
            "matches": [m.to_dict() for m in self.matches],
            "total_matches": self.total_matches,
            "query_latency_ms": round(self.query_latency_ms, 3),
            "timestamp": self.timestamp.isoformat(),
            "has_matches": self.has_matches,
        }


class VectorMatcher:
    """
    Semantic similarity search for vulnerability pattern matching.

    Queries OpenSearch knn_vector index to find known vulnerability
    patterns similar to observed runtime behavior.

    Usage:
        matcher = VectorMatcher()
        result = await matcher.search(
            query_text="SQL query constructed with string concatenation",
            max_results=5,
            min_similarity=0.7,
        )
        for match in result.matches:
            print(f"Found: {match.vulnerability_type} ({match.similarity_score})")
    """

    def __init__(
        self,
        opensearch_client: Optional[Any] = None,
        index_name: str = "aura-vulnerability-patterns",
        use_mock: bool = True,
        embedding_dimension: int = 1024,
    ):
        self._opensearch = opensearch_client
        self.index_name = index_name
        self.use_mock = use_mock
        self.embedding_dimension = embedding_dimension

        # Mock vulnerability patterns
        self._mock_patterns: list[dict[str, Any]] = []

    async def search(
        self,
        query_text: str,
        max_results: int = 5,
        min_similarity: float = 0.5,
    ) -> MatchResult:
        """
        Search for vulnerability patterns similar to the query text.

        Args:
            query_text: Text describing the observed behavior.
            max_results: Maximum number of matches to return.
            min_similarity: Minimum similarity threshold [0, 1].

        Returns:
            MatchResult with vulnerability matches.
        """
        import time

        start = time.monotonic()

        if self.use_mock:
            matches = self._mock_search(query_text, max_results, min_similarity)
        else:
            matches = await self._opensearch_search(
                query_text, max_results, min_similarity
            )

        elapsed_ms = (time.monotonic() - start) * 1000

        return MatchResult(
            result_id=f"mr-{uuid.uuid4().hex[:16]}",
            query_text=query_text,
            matches=tuple(matches),
            total_matches=len(matches),
            query_latency_ms=elapsed_ms,
            timestamp=datetime.now(timezone.utc),
        )

    def add_mock_pattern(
        self,
        vulnerability_id: str,
        vulnerability_type: str,
        description: str,
        keywords: list[str],
        severity: str = "medium",
        cwe_id: Optional[str] = None,
        source_file: Optional[str] = None,
        source_line: Optional[int] = None,
        remediation_hint: str = "",
    ) -> None:
        """Add a mock vulnerability pattern for testing."""
        self._mock_patterns.append(
            {
                "vulnerability_id": vulnerability_id,
                "vulnerability_type": vulnerability_type,
                "description": description,
                "keywords": [k.lower() for k in keywords],
                "severity": severity,
                "cwe_id": cwe_id,
                "source_file": source_file,
                "source_line": source_line,
                "remediation_hint": remediation_hint,
            }
        )

    def _mock_search(
        self,
        query_text: str,
        max_results: int,
        min_similarity: float,
    ) -> list[VulnerabilityMatch]:
        """Mock search using keyword overlap as similarity proxy."""
        query_words = set(query_text.lower().split())
        matches = []

        for pattern in self._mock_patterns:
            keyword_set = set(pattern["keywords"])
            overlap = len(query_words & keyword_set)
            if overlap == 0:
                continue

            similarity = overlap / max(len(keyword_set), 1)
            if similarity < min_similarity:
                continue

            matches.append(
                VulnerabilityMatch(
                    match_id=f"vm-{uuid.uuid4().hex[:12]}",
                    vulnerability_id=pattern["vulnerability_id"],
                    vulnerability_type=pattern["vulnerability_type"],
                    description=pattern["description"],
                    similarity_score=min(similarity, 1.0),
                    source_file=pattern.get("source_file"),
                    source_line=pattern.get("source_line"),
                    cwe_id=pattern.get("cwe_id"),
                    severity=pattern.get("severity", "medium"),
                    remediation_hint=pattern.get("remediation_hint", ""),
                )
            )

        matches.sort(key=lambda m: m.similarity_score, reverse=True)
        return matches[:max_results]

    async def _opensearch_search(
        self,
        query_text: str,
        max_results: int,
        min_similarity: float,
    ) -> list[VulnerabilityMatch]:
        """Search via OpenSearch knn_vector."""
        logger.info("OpenSearch search not implemented for mock-first development")
        return []
