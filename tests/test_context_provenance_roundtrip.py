"""End-to-end tests for ADR-067 provenance: ingestion records evidence,
retrieval verifies it.

Ingestion runs GitIngestionService against a real local git repository and
the in-memory (MOCK mode) OpenSearchVectorService; retrieval reads the same
store through OpenSearchEvidenceLoader. No AWS calls are made.
"""

import hashlib
import hmac
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from git import Repo

from src.agents.filesystem_navigator_agent import FileMatch
from src.agents.result_synthesis_agent import ResultSynthesisAgent
from src.services.context_provenance import ContentProvenanceService, TrustScoringEngine
from src.services.context_provenance.evidence_loader import OpenSearchEvidenceLoader
from src.services.context_provenance.factory import (
    create_provenance_service_from_env,
    create_provenance_verifier,
    create_provenance_verifier_from_env,
    resolve_hmac_key,
)
from src.services.context_provenance.retrieval_verifier import VerificationOutcome
from src.services.context_retrieval_service import (
    ContextRetrievalService,
    create_context_retrieval_service,
)
from src.services.git_ingestion_service import GitIngestionService
from src.services.opensearch_vector_service import (
    OpenSearchMode,
    OpenSearchVectorService,
)

KEY = "roundtrip-test-hmac-key"
REPO_DIR = "aenea-labs-aura"
ORIGIN = "https://github.com/aenea-labs/aura.git"
A_PY = "def alpha():\n    return 'alpha'\n"
B_PY = "def beta():\n    return 'beta'\n"
ALICE = ("Alice", "alice@aenealabs.com")
BOB = ("Bob", "bob@aenealabs.com")
PROVENANCE_ENV = (
    "AURA_CONTEXT_PROVENANCE_ENABLED",
    "AURA_CONTEXT_PROVENANCE_STRICT",
    "AURA_PROVENANCE_REPOSITORY_SCOPE",
    "AURA_PROVENANCE_INTERNAL_ORGS",
    "AURA_INTEGRITY_HMAC_KEY",
    "AURA_PROVENANCE_HMAC_KEY",
)


def _git(repo_path: Path, *args: str, env: dict | None = None) -> None:
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=repo_path,
        check=True,
        capture_output=True,
        env={**os.environ, **(env or {})},
    )


def _commit(repo_path: Path, rel: str, content: str, author, when: datetime):
    (repo_path / rel).write_text(content)
    stamp = when.strftime("%Y-%m-%dT%H:%M:%S+0000")
    name, email = author
    _git(repo_path, "add", rel)
    _git(
        repo_path,
        "commit",
        "-m",
        f"add {rel}",
        env={
            "GIT_AUTHOR_NAME": name,
            "GIT_AUTHOR_EMAIL": email,
            "GIT_COMMITTER_NAME": name,
            "GIT_COMMITTER_EMAIL": email,
            "GIT_AUTHOR_DATE": stamp,
            "GIT_COMMITTER_DATE": stamp,
        },
    )


@pytest.fixture
def clone_dir(tmp_path):
    """Clone dir holding a repo: a.py by Alice 200 days ago, b.py by Bob now."""
    repo_path = tmp_path / REPO_DIR
    repo_path.mkdir()
    _git(repo_path, "init", "-q")
    now = datetime.now(timezone.utc)
    _commit(repo_path, "a.py", A_PY, ALICE, now - timedelta(days=200))
    _commit(repo_path, "b.py", B_PY, BOB, now - timedelta(minutes=5))
    _git(repo_path, "remote", "add", "origin", ORIGIN)
    return tmp_path


@pytest.fixture
def store():
    return OpenSearchVectorService(mode=OpenSearchMode.MOCK)


def _ingestion(clone_dir, store, provenance_service):
    embeddings = MagicMock()
    embeddings.generate_embedding = MagicMock(return_value=[0.1] * 1024)
    parser = MagicMock()
    parser.parse_file_with_relationships = MagicMock(return_value=([], []))
    return GitIngestionService(
        neptune_service=MagicMock(),
        opensearch_service=store,
        embedding_service=embeddings,
        ast_parser=parser,
        observability_service=MagicMock(),
        clone_base_path=str(clone_dir),
        github_app_auth=MagicMock(),
        provenance_service=provenance_service,
    )


async def _ingest(clone_dir, store, provenance_service=None, key=KEY):
    if provenance_service is None and key is not None:
        provenance_service = ContentProvenanceService(hmac_secret_key=key)
    service = _ingestion(clone_dir, store, provenance_service)
    result = await service.ingest_changes(
        repository_path=clone_dir / REPO_DIR, changed_files=["a.py", "b.py"]
    )
    assert result.success, result.error
    return result


def _doc(store, rel: str) -> dict:
    (doc,) = [
        d for d in store.mock_index.values() if d["metadata"].get("file_path") == rel
    ]
    return doc


def _verifier(store, key=KEY, strict=True, repository=None):
    return create_provenance_verifier(
        store,
        key,
        strict=strict,
        repository=repository,
        trust_engine=TrustScoringEngine(internal_org_ids=["aenea-labs"]),
    )


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


async def _retrieve(verifier, paths):
    service = ContextRetrievalService.__new__(ContextRetrievalService)
    service.provenance_verifier = verifier
    service.result_synthesizer = ResultSynthesisAgent()
    service.query_planner = MagicMock(plan_search=AsyncMock(return_value=[]))
    service._execute_parallel_searches = AsyncMock(
        return_value=([_match(p) for p in paths], [], [], [])
    )
    return await service.retrieve_context("q")


# =============================================================================
# Index time
# =============================================================================


class TestIngestionRecordsEvidence:
    @pytest.mark.asyncio
    async def test_evidence_signs_stored_text_with_per_file_git_provenance(
        self, clone_dir, store
    ):
        await _ingest(clone_dir, store)
        doc_a, doc_b = _doc(store, "a.py"), _doc(store, "b.py")

        text = doc_a["text"].encode()
        assert doc_a["text"] == A_PY
        assert doc_a["integrity"]["content_hash"] == hashlib.sha256(text).hexdigest()
        assert (
            doc_a["integrity"]["content_hmac"]
            == hmac.new(KEY.encode(), text, hashlib.sha256).hexdigest()
        )
        assert doc_a["integrity"]["embedding_fingerprint"]
        assert doc_a["status"] == "ACTIVE"

        # Repository id comes from the origin remote, not the local path;
        # author/commit/timestamp come from the last commit touching each file.
        repo = Repo(clone_dir / REPO_DIR)
        a_commit, b_commit = list(repo.iter_commits())[::-1]
        assert doc_a["provenance"]["repository_id"] == "aenea-labs/aura"
        assert doc_a["provenance"]["author_email"] == ALICE[1]
        assert doc_a["provenance"]["commit_sha"] == a_commit.hexsha
        assert doc_b["provenance"]["author_email"] == BOB[1]
        assert doc_b["provenance"]["commit_sha"] == b_commit.hexsha
        assert doc_a["provenance"]["signature"] is None

    @pytest.mark.asyncio
    async def test_without_provenance_service_documents_unchanged(
        self, clone_dir, store
    ):
        await _ingest(clone_dir, store, key=None)
        doc = _doc(store, "a.py")
        assert set(doc) == {"text", "vector", "metadata", "timestamp"}

    @pytest.mark.asyncio
    async def test_recording_failure_still_indexes_without_evidence(
        self, clone_dir, store
    ):
        signer = MagicMock()
        signer.collect_provenance.side_effect = RuntimeError("kms down")
        await _ingest(clone_dir, store, provenance_service=signer)
        doc = _doc(store, "a.py")
        assert doc["text"] == A_PY
        assert "integrity" not in doc and "provenance" not in doc


# =============================================================================
# Round trip: ingest -> retrieve -> verify
# =============================================================================


class TestRoundTrip:
    @pytest.mark.asyncio
    async def test_ingested_files_admitted_with_trust_scores(self, clone_dir, store):
        await _ingest(clone_dir, store)
        response = await _retrieve(_verifier(store), ["a.py", "b.py"])

        assert {f.file_path for f in response.files} == {"a.py", "b.py"}
        assert response.excluded_by_provenance == []
        # internal repo 1.0*.35 + first-time author .5*.25 + verified 1.0*.25,
        # plus age: a.py established (1.0*.15), b.py brand new (.5*.15).
        assert response.trust_scores["a.py"].score == pytest.approx(0.875)
        assert response.trust_scores["b.py"].score == pytest.approx(0.80)

    @pytest.mark.asyncio
    async def test_tampered_stored_content_excluded(self, clone_dir, store):
        await _ingest(clone_dir, store)
        _doc(store, "a.py")["text"] = "def alpha():\n    __import__('os').system('x')\n"

        response = await _retrieve(_verifier(store), ["a.py", "b.py"])
        assert [f.file_path for f in response.files] == ["b.py"]
        assert response.excluded_by_provenance == ["a.py"]

    @pytest.mark.asyncio
    async def test_tamper_after_successful_verification_is_caught(
        self, clone_dir, store
    ):
        """A prior VERIFIED result must not be reused for changed content."""
        await _ingest(clone_dir, store)
        verifier = _verifier(store)
        assert (await verifier.verify_item("a.py")).allowed is True

        _doc(store, "a.py")["text"] = "def alpha():\n    return 'pwned'\n"
        decision = await verifier.verify_item("a.py")
        assert decision.allowed is False
        assert decision.outcome == VerificationOutcome.INTEGRITY_FAILED

    @pytest.mark.asyncio
    async def test_rehashed_tamper_without_key_fails_hmac(self, clone_dir, store):
        await _ingest(clone_dir, store)
        doc = _doc(store, "a.py")
        doc["text"] = "def alpha():\n    return 'forged'\n"
        doc["integrity"]["content_hash"] = hashlib.sha256(
            doc["text"].encode()
        ).hexdigest()

        decision = await _verifier(store).verify_item("a.py")
        assert decision.allowed is False
        assert decision.outcome == VerificationOutcome.INTEGRITY_FAILED
        assert "HMAC" in decision.details

    @pytest.mark.asyncio
    async def test_signing_key_mismatch_excludes(self, clone_dir, store):
        await _ingest(clone_dir, store)
        decision = await _verifier(store, key="other-key").verify_item("a.py")
        assert decision.allowed is False
        assert decision.outcome == VerificationOutcome.INTEGRITY_FAILED

    @pytest.mark.asyncio
    async def test_missing_evidence_strict_excludes_non_strict_admits(
        self, clone_dir, store
    ):
        await _ingest(clone_dir, store, key=None)  # legacy index, no evidence

        strict = await _retrieve(_verifier(store), ["a.py"])
        assert strict.files == []
        assert strict.excluded_by_provenance == ["a.py"]

        lax = await _verifier(store, strict=False).verify_item("a.py")
        assert lax.allowed is True
        assert lax.outcome == VerificationOutcome.UNVERIFIED_ADMITTED
        assert lax.trust_score is None

    @pytest.mark.asyncio
    async def test_unindexed_path_excluded(self, clone_dir, store):
        await _ingest(clone_dir, store)
        decision = await _verifier(store).verify_item("never_indexed.py")
        assert decision.outcome == VerificationOutcome.NO_EVIDENCE
        assert decision.allowed is False


# =============================================================================
# Evidence loader
# =============================================================================


class TestEvidenceLoader:
    @pytest.mark.asyncio
    async def test_ambiguous_path_requires_repository_scope(self, clone_dir, store):
        await _ingest(clone_dir, store)
        clone = _doc(store, "a.py")
        store.mock_index["other-repo::a.py"] = {
            **clone,
            "metadata": {**clone["metadata"], "repository": "other-repo"},
        }
        repo_id = _doc(store, "b.py")["metadata"]["repository"]

        assert await OpenSearchEvidenceLoader(store)("a.py") is None
        scoped = await OpenSearchEvidenceLoader(store, repository=repo_id)("a.py")
        assert scoped is not None
        assert scoped.chunk_id == f"{repo_id}::a.py"
        assert scoped.provenance.author_email == ALICE[1]

    def test_real_mode_lookup_returns_evidence_fields(self):
        service = OpenSearchVectorService.__new__(OpenSearchVectorService)
        service.mode = OpenSearchMode.AWS
        service.index_name = "aura-code-embeddings"
        service.client = MagicMock()
        service.client.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_id": "r::a.py",
                        "_source": {
                            "text": "x",
                            "metadata": {"file_path": "a.py"},
                            "integrity": {"content_hash": "h"},
                        },
                    }
                ]
            }
        }
        (doc,) = service.find_by_file_path("a.py", repository="r", limit=2)
        assert doc["integrity"] == {"content_hash": "h"}
        assert "provenance" not in doc

        body = service.client.search.call_args.kwargs["body"]
        assert {"provenance", "integrity", "text"} <= set(body["_source"])
        assert body["size"] == 2
        assert len(body["query"]["bool"]["filter"]) == 2


# =============================================================================
# Configuration wiring
# =============================================================================


@pytest.fixture
def clean_env(monkeypatch):
    for name in PROVENANCE_ENV:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


class TestFactoryWiring:
    def test_disabled_builds_nothing(self, clean_env, store):
        clean_env.setenv("AURA_INTEGRITY_HMAC_KEY", KEY)
        assert create_provenance_service_from_env() is None
        assert create_provenance_verifier_from_env(store) is None
        service = create_context_retrieval_service(use_mock=True)
        assert service.provenance_verifier is None

    def test_enabled_without_key_fails_fast(self, clean_env, store):
        clean_env.setenv("AURA_CONTEXT_PROVENANCE_ENABLED", "true")
        with pytest.raises(RuntimeError, match="required"):
            create_provenance_service_from_env()
        with pytest.raises(RuntimeError, match="required"):
            create_provenance_verifier_from_env(store)

    def test_mismatched_keys_rejected(self, clean_env):
        clean_env.setenv("AURA_INTEGRITY_HMAC_KEY", "a")
        clean_env.setenv("AURA_PROVENANCE_HMAC_KEY", "b")
        with pytest.raises(RuntimeError, match="differ"):
            resolve_hmac_key()

    def test_enabled_retrieval_factory_requires_store(self, clean_env):
        clean_env.setenv("AURA_CONTEXT_PROVENANCE_ENABLED", "1")
        clean_env.setenv("AURA_PROVENANCE_HMAC_KEY", KEY)
        with pytest.raises(ValueError, match="provenance_evidence_store"):
            create_context_retrieval_service(use_mock=True)

    @pytest.mark.asyncio
    async def test_env_configured_round_trip(self, clean_env, clone_dir, store):
        clean_env.setenv("AURA_CONTEXT_PROVENANCE_ENABLED", "true")
        clean_env.setenv("AURA_PROVENANCE_HMAC_KEY", KEY)
        clean_env.setenv("AURA_PROVENANCE_INTERNAL_ORGS", "aenea-labs, partner")

        await _ingest(
            clone_dir, store, provenance_service=create_provenance_service_from_env()
        )
        service = create_context_retrieval_service(
            use_mock=True, provenance_evidence_store=store
        )
        verifier = service.provenance_verifier
        assert verifier is not None and verifier.strict is True

        decision = await verifier.verify_item("a.py")
        assert decision.outcome == VerificationOutcome.VERIFIED
        assert decision.trust_score.score == pytest.approx(0.875)

    def test_strict_can_be_disabled(self, clean_env, store):
        clean_env.setenv("AURA_CONTEXT_PROVENANCE_ENABLED", "true")
        clean_env.setenv("AURA_CONTEXT_PROVENANCE_STRICT", "false")
        clean_env.setenv("AURA_INTEGRITY_HMAC_KEY", KEY)
        assert create_provenance_verifier_from_env(store).strict is False
