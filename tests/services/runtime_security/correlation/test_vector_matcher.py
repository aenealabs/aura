"""
Tests for the OpenSearch Vector Matcher.

Covers VulnerabilityMatch and MatchResult frozen dataclasses, serialization,
mock keyword-overlap scoring, min_similarity filtering, and max_results limits.
"""

import dataclasses
from datetime import datetime, timezone

import pytest

from src.services.runtime_security.correlation.vector_matcher import (
    MatchResult,
    VectorMatcher,
    VulnerabilityMatch,
)

# =========================================================================
# VulnerabilityMatch Tests
# =========================================================================


class TestVulnerabilityMatch:
    """Tests for the VulnerabilityMatch frozen dataclass."""

    def test_create_with_all_fields(self):
        """Test creating a VulnerabilityMatch with all fields."""
        match = VulnerabilityMatch(
            match_id="vm-test001",
            vulnerability_id="vuln-001",
            vulnerability_type="SQL Injection",
            description="SQL query with string concatenation",
            similarity_score=0.92,
            source_file="src/handler.py",
            source_line=42,
            cwe_id="CWE-89",
            severity="critical",
            remediation_hint="Use parameterized queries",
        )
        assert match.match_id == "vm-test001"
        assert match.vulnerability_id == "vuln-001"
        assert match.vulnerability_type == "SQL Injection"
        assert match.similarity_score == 0.92
        assert match.source_file == "src/handler.py"
        assert match.source_line == 42
        assert match.cwe_id == "CWE-89"
        assert match.severity == "critical"
        assert match.remediation_hint == "Use parameterized queries"

    def test_create_with_defaults(self):
        """Test that optional fields default correctly."""
        match = VulnerabilityMatch(
            match_id="vm-defaults",
            vulnerability_id="vuln-002",
            vulnerability_type="XSS",
            description="Unsanitized input",
            similarity_score=0.7,
        )
        assert match.source_file is None
        assert match.source_line is None
        assert match.cwe_id is None
        assert match.severity == "medium"
        assert match.remediation_hint == ""

    def test_frozen_immutability_match_id(self):
        """Test that match_id cannot be mutated."""
        match = VulnerabilityMatch(
            match_id="vm-frozen",
            vulnerability_id="vuln-003",
            vulnerability_type="XSS",
            description="test",
            similarity_score=0.5,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            match.match_id = "vm-mutated"  # type: ignore[misc]

    def test_frozen_immutability_similarity_score(self):
        """Test that similarity_score cannot be mutated."""
        match = VulnerabilityMatch(
            match_id="vm-frozen2",
            vulnerability_id="vuln-004",
            vulnerability_type="SSRF",
            description="test",
            similarity_score=0.8,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            match.similarity_score = 1.0  # type: ignore[misc]

    def test_frozen_immutability_source_file(self):
        """Test that source_file cannot be mutated."""
        match = VulnerabilityMatch(
            match_id="vm-frozen3",
            vulnerability_id="vuln-005",
            vulnerability_type="RCE",
            description="test",
            similarity_score=0.6,
            source_file="original.py",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            match.source_file = "hacked.py"  # type: ignore[misc]

    def test_to_dict_serialization(self):
        """Test to_dict produces expected keys and values."""
        match = VulnerabilityMatch(
            match_id="vm-dict001",
            vulnerability_id="vuln-006",
            vulnerability_type="SQL Injection",
            description="Unsafe query",
            similarity_score=0.87654,
            source_file="src/db.py",
            source_line=99,
            cwe_id="CWE-89",
            severity="critical",
            remediation_hint="Parameterize",
        )
        d = match.to_dict()
        assert d["match_id"] == "vm-dict001"
        assert d["vulnerability_id"] == "vuln-006"
        assert d["vulnerability_type"] == "SQL Injection"
        assert d["description"] == "Unsafe query"
        assert d["similarity_score"] == 0.8765
        assert d["source_file"] == "src/db.py"
        assert d["source_line"] == 99
        assert d["cwe_id"] == "CWE-89"
        assert d["severity"] == "critical"
        assert d["remediation_hint"] == "Parameterize"

    def test_to_dict_optional_fields_null(self):
        """Test that unset optional fields serialize as None."""
        match = VulnerabilityMatch(
            match_id="vm-nulls",
            vulnerability_id="vuln-007",
            vulnerability_type="XSS",
            description="test",
            similarity_score=0.5,
        )
        d = match.to_dict()
        assert d["source_file"] is None
        assert d["source_line"] is None
        assert d["cwe_id"] is None

    def test_similarity_score_rounding(self):
        """Test that similarity_score is rounded to 4 decimal places."""
        match = VulnerabilityMatch(
            match_id="vm-round",
            vulnerability_id="vuln-008",
            vulnerability_type="CSRF",
            description="test",
            similarity_score=0.123456789,
        )
        d = match.to_dict()
        assert d["similarity_score"] == 0.1235


# =========================================================================
# MatchResult Tests
# =========================================================================


class TestMatchResult:
    """Tests for the MatchResult frozen dataclass."""

    def test_create_with_matches(self, now_utc: datetime):
        """Test creating a MatchResult with populated matches."""
        match = VulnerabilityMatch(
            match_id="vm-mr001",
            vulnerability_id="vuln-010",
            vulnerability_type="SQLi",
            description="test",
            similarity_score=0.85,
        )
        result = MatchResult(
            result_id="mr-test001",
            query_text="sql injection query",
            matches=(match,),
            total_matches=1,
            query_latency_ms=2.5,
            timestamp=now_utc,
        )
        assert result.result_id == "mr-test001"
        assert result.query_text == "sql injection query"
        assert len(result.matches) == 1
        assert result.total_matches == 1

    def test_frozen_immutability(self, now_utc: datetime):
        """Test that MatchResult fields cannot be mutated."""
        result = MatchResult(
            result_id="mr-frozen",
            query_text="test",
            matches=(),
            total_matches=0,
            query_latency_ms=0.0,
            timestamp=now_utc,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.result_id = "mr-mutated"  # type: ignore[misc]

    def test_has_matches_true(self, now_utc: datetime):
        """Test has_matches is True when matches are present."""
        match = VulnerabilityMatch(
            match_id="vm-hm",
            vulnerability_id="vuln-011",
            vulnerability_type="XSS",
            description="test",
            similarity_score=0.7,
        )
        result = MatchResult(
            result_id="mr-hm",
            query_text="test",
            matches=(match,),
            total_matches=1,
            query_latency_ms=1.0,
            timestamp=now_utc,
        )
        assert result.has_matches is True

    def test_has_matches_false(self, now_utc: datetime):
        """Test has_matches is False when matches is empty."""
        result = MatchResult(
            result_id="mr-nohm",
            query_text="test",
            matches=(),
            total_matches=0,
            query_latency_ms=1.0,
            timestamp=now_utc,
        )
        assert result.has_matches is False

    def test_best_match_highest_similarity(self, now_utc: datetime):
        """Test best_match returns match with highest similarity_score."""
        low = VulnerabilityMatch(
            match_id="vm-low",
            vulnerability_id="v1",
            vulnerability_type="A",
            description="",
            similarity_score=0.3,
        )
        high = VulnerabilityMatch(
            match_id="vm-high",
            vulnerability_id="v2",
            vulnerability_type="B",
            description="",
            similarity_score=0.95,
        )
        mid = VulnerabilityMatch(
            match_id="vm-mid",
            vulnerability_id="v3",
            vulnerability_type="C",
            description="",
            similarity_score=0.6,
        )
        result = MatchResult(
            result_id="mr-best",
            query_text="test",
            matches=(low, high, mid),
            total_matches=3,
            query_latency_ms=1.0,
            timestamp=now_utc,
        )
        assert result.best_match is high
        assert result.best_match.similarity_score == 0.95

    def test_best_match_none_when_empty(self, now_utc: datetime):
        """Test best_match returns None when matches is empty."""
        result = MatchResult(
            result_id="mr-nobest",
            query_text="test",
            matches=(),
            total_matches=0,
            query_latency_ms=0.0,
            timestamp=now_utc,
        )
        assert result.best_match is None

    def test_to_dict_serialization(self, now_utc: datetime):
        """Test to_dict produces expected keys and values."""
        match = VulnerabilityMatch(
            match_id="vm-ser",
            vulnerability_id="vuln-012",
            vulnerability_type="RCE",
            description="test",
            similarity_score=0.8,
        )
        result = MatchResult(
            result_id="mr-ser",
            query_text="remote code execution attempt",
            matches=(match,),
            total_matches=1,
            query_latency_ms=4.567,
            timestamp=now_utc,
        )
        d = result.to_dict()
        assert d["result_id"] == "mr-ser"
        assert d["query_text"] == "remote code execution attempt"
        assert len(d["matches"]) == 1
        assert d["total_matches"] == 1
        assert d["query_latency_ms"] == 4.567
        assert d["timestamp"] == now_utc.isoformat()
        assert d["has_matches"] is True

    def test_to_dict_truncates_long_query_text(self, now_utc: datetime):
        """Test that query_text is truncated to 200 chars in to_dict."""
        long_text = "x" * 500
        result = MatchResult(
            result_id="mr-trunc",
            query_text=long_text,
            matches=(),
            total_matches=0,
            query_latency_ms=0.0,
            timestamp=now_utc,
        )
        d = result.to_dict()
        assert len(d["query_text"]) == 200


# =========================================================================
# VectorMatcher Tests
# =========================================================================


class TestVectorMatcher:
    """Tests for VectorMatcher mock-mode search."""

    async def test_search_returns_match_result(
        self, mock_vector_matcher: VectorMatcher
    ):
        """Test that search returns a MatchResult."""
        result = await mock_vector_matcher.search(
            query_text="sql injection query concatenation",
        )
        assert isinstance(result, MatchResult)
        assert result.result_id.startswith("mr-")

    async def test_search_finds_sql_injection_pattern(
        self, mock_vector_matcher: VectorMatcher
    ):
        """Test that search finds the SQL injection pattern by keyword overlap."""
        result = await mock_vector_matcher.search(
            query_text="sql injection query concatenation string",
        )
        assert result.has_matches is True
        assert any(m.vulnerability_type == "SQL Injection" for m in result.matches)

    async def test_search_no_matching_keywords(
        self, mock_vector_matcher: VectorMatcher
    ):
        """Test that search with no matching keywords returns empty."""
        result = await mock_vector_matcher.search(
            query_text="completely unrelated topic about gardening",
        )
        assert result.has_matches is False
        assert len(result.matches) == 0

    async def test_add_mock_pattern_works(self):
        """Test that add_mock_pattern makes patterns searchable."""
        matcher = VectorMatcher(use_mock=True)
        matcher.add_mock_pattern(
            vulnerability_id="vuln-custom",
            vulnerability_type="Path Traversal",
            description="File path manipulation",
            keywords=["path", "traversal", "file", "directory"],
            severity="high",
        )
        result = await matcher.search(
            query_text="path traversal file directory attack",
        )
        assert result.has_matches is True
        assert result.matches[0].vulnerability_type == "Path Traversal"

    async def test_min_similarity_filter(self):
        """Test that min_similarity filters out low-scoring matches."""
        matcher = VectorMatcher(use_mock=True)
        matcher.add_mock_pattern(
            vulnerability_id="vuln-filter",
            vulnerability_type="CSRF",
            description="Cross-site request forgery",
            keywords=["csrf", "token", "request", "forgery", "cross"],
        )
        # Only 1 of 5 keywords matches -> similarity=0.2
        result = await matcher.search(
            query_text="csrf",
            min_similarity=0.5,
        )
        assert result.has_matches is False

    async def test_min_similarity_allows_above_threshold(self):
        """Test that matches above min_similarity are returned."""
        matcher = VectorMatcher(use_mock=True)
        matcher.add_mock_pattern(
            vulnerability_id="vuln-above",
            vulnerability_type="SQLi",
            description="test",
            keywords=["sql", "injection"],
        )
        # 2 of 2 keywords match -> similarity=1.0
        result = await matcher.search(
            query_text="sql injection",
            min_similarity=0.5,
        )
        assert result.has_matches is True

    async def test_max_results_limit(self):
        """Test that max_results limits the number of returned matches."""
        matcher = VectorMatcher(use_mock=True)
        for i in range(10):
            matcher.add_mock_pattern(
                vulnerability_id=f"vuln-{i:03d}",
                vulnerability_type="Generic",
                description=f"Pattern {i}",
                keywords=["common", "keyword"],
            )
        result = await matcher.search(
            query_text="common keyword",
            max_results=3,
        )
        assert len(result.matches) == 3
        assert result.total_matches == 3

    async def test_keyword_overlap_scoring(self):
        """Test that similarity is based on keyword overlap."""
        matcher = VectorMatcher(use_mock=True)
        matcher.add_mock_pattern(
            vulnerability_id="vuln-overlap",
            vulnerability_type="Test",
            description="test",
            keywords=["alpha", "beta", "gamma", "delta"],
        )
        # 2 of 4 keywords -> similarity = 0.5
        result = await matcher.search(
            query_text="alpha beta",
            min_similarity=0.0,
        )
        assert result.has_matches is True
        assert result.matches[0].similarity_score == 0.5

    async def test_search_latency_recorded(self, mock_vector_matcher: VectorMatcher):
        """Test that query_latency_ms is recorded."""
        result = await mock_vector_matcher.search(query_text="sql")
        assert result.query_latency_ms >= 0.0

    async def test_search_timestamp_is_utc(self, mock_vector_matcher: VectorMatcher):
        """Test that timestamp has UTC timezone."""
        result = await mock_vector_matcher.search(query_text="test")
        assert result.timestamp.tzinfo is not None


class TestMockSearch:
    """Tests for mock search keyword-overlap scoring behavior."""

    async def test_partial_keyword_match_lower_score(self):
        """Test that partial keyword overlap gives a lower score."""
        matcher = VectorMatcher(use_mock=True)
        matcher.add_mock_pattern(
            vulnerability_id="vuln-partial",
            vulnerability_type="Test",
            description="test",
            keywords=["one", "two", "three", "four", "five"],
        )
        # 1 of 5 keywords -> 0.2
        result = await matcher.search(
            query_text="one",
            min_similarity=0.0,
        )
        assert result.has_matches is True
        assert result.matches[0].similarity_score == pytest.approx(0.2)

    async def test_full_keyword_match_high_score(self):
        """Test that full keyword match gives a score of 1.0."""
        matcher = VectorMatcher(use_mock=True)
        matcher.add_mock_pattern(
            vulnerability_id="vuln-full",
            vulnerability_type="Test",
            description="test",
            keywords=["alpha", "beta"],
        )
        result = await matcher.search(
            query_text="alpha beta",
            min_similarity=0.0,
        )
        assert result.has_matches is True
        assert result.matches[0].similarity_score == 1.0

    async def test_multiple_patterns_ranked_by_score(self):
        """Test that multiple matching patterns are ranked by similarity score."""
        matcher = VectorMatcher(use_mock=True)
        matcher.add_mock_pattern(
            vulnerability_id="vuln-low-rank",
            vulnerability_type="Low",
            description="test",
            keywords=["common", "unique_a", "unique_b", "unique_c"],
        )
        matcher.add_mock_pattern(
            vulnerability_id="vuln-high-rank",
            vulnerability_type="High",
            description="test",
            keywords=["common"],
        )
        # "common" matches both. Pattern 1: 1/4=0.25, Pattern 2: 1/1=1.0
        result = await matcher.search(
            query_text="common",
            min_similarity=0.0,
        )
        assert len(result.matches) == 2
        assert result.matches[0].vulnerability_id == "vuln-high-rank"
        assert result.matches[0].similarity_score == 1.0
        assert result.matches[1].vulnerability_id == "vuln-low-rank"
        assert result.matches[1].similarity_score == 0.25

    async def test_keywords_are_case_insensitive(self):
        """Test that keyword matching is case-insensitive."""
        matcher = VectorMatcher(use_mock=True)
        matcher.add_mock_pattern(
            vulnerability_id="vuln-case",
            vulnerability_type="Test",
            description="test",
            keywords=["SQL", "Injection"],
        )
        result = await matcher.search(
            query_text="sql injection",
            min_similarity=0.0,
        )
        assert result.has_matches is True
        assert result.matches[0].similarity_score == 1.0
