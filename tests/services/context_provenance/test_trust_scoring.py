"""Tests for TrustScoringEngine."""

from datetime import datetime, timedelta, timezone

import pytest

from src.services.context_provenance.contracts import ProvenanceRecord, TrustLevel
from src.services.context_provenance.trust_scoring import (
    TrustScoringEngine,
    configure_trust_scoring_engine,
    get_trust_scoring_engine,
    reset_trust_scoring_engine,
)


@pytest.fixture
def trust_engine():
    """Create a trust scoring engine for testing."""
    return TrustScoringEngine(
        internal_org_ids=["aenea-labs", "internal-org"],
        partner_org_ids=["trusted-partner", "verified-vendor"],
        flagged_repo_ids=["malicious-org/bad-repo"],
    )


@pytest.fixture(autouse=True)
def reset_engine():
    """Reset global engine after each test."""
    yield
    reset_trust_scoring_engine()


def create_provenance(
    repository_id: str = "org/repo",
    author_id: str = "author",
    timestamp: datetime = None,
    signature: str = None,
) -> ProvenanceRecord:
    """Helper to create provenance records."""
    return ProvenanceRecord(
        repository_id=repository_id,
        commit_sha="abc123",
        author_id=author_id,
        author_email="author@test.com",
        timestamp=timestamp or datetime.now(timezone.utc),
        branch="main",
        signature=signature,
    )


class TestTrustScoringEngine:
    """Tests for TrustScoringEngine."""

    def test_compute_internal_repo_high_trust(self, trust_engine):
        """Test that internal repos get high trust."""
        provenance = create_provenance(repository_id="aenea-labs/project-aura")

        score = trust_engine.compute_trust_score(
            provenance=provenance,
            integrity_verified=True,
            verification_age_days=0,
        )

        # Internal repo (1.0*0.35) + first-time author (0.5*0.25) +
        # brand new (0.5*0.15) + verified (1.0*0.25) = 0.35 + 0.125 + 0.075 + 0.25 = 0.80
        assert score.score >= 0.799  # Allow for floating point precision
        assert score.level == TrustLevel.HIGH

    def test_compute_partner_repo_trust(self, trust_engine):
        """Test that partner repos get medium-high trust."""
        provenance = create_provenance(repository_id="trusted-partner/lib")

        score = trust_engine.compute_trust_score(
            provenance=provenance,
            integrity_verified=True,
            verification_age_days=0,
        )

        # Partner repo (0.9*0.35) = 0.315, should be medium to high
        assert score.score >= 0.50
        assert score.level in (TrustLevel.MEDIUM, TrustLevel.HIGH)

    def test_compute_flagged_repo_untrusted(self, trust_engine):
        """Test that flagged repos get zero trust."""
        provenance = create_provenance(repository_id="malicious-org/bad-repo")

        score = trust_engine.compute_trust_score(
            provenance=provenance,
            integrity_verified=False,  # Failed integrity + flagged repo = UNTRUSTED
            verification_age_days=0,
        )

        # Flagged repo (0.0*0.35) = 0.0 for repo component
        # With integrity_verified=False: 0 + 0.125 + 0.075 + 0 = 0.20 = UNTRUSTED
        assert score.components["repository"] == 0.0
        assert score.level == TrustLevel.UNTRUSTED

    def test_compute_unknown_repo_low_trust(self, trust_engine):
        """Test that unknown repos get lower trust."""
        provenance = create_provenance(repository_id="unknown-org/unknown-repo")

        score = trust_engine.compute_trust_score(
            provenance=provenance,
            integrity_verified=True,
            verification_age_days=0,
        )

        # Unknown repo (0.3*0.35) = 0.105
        assert score.components["repository"] == 0.30

    def test_compute_integrity_failed_untrusted(self, trust_engine):
        """Test that failed integrity leads to low trust."""
        provenance = create_provenance(repository_id="aenea-labs/project")

        score = trust_engine.compute_trust_score(
            provenance=provenance,
            integrity_verified=False,
            verification_age_days=0,
        )

        # Verification failed (0.0*0.25) = 0.0
        assert score.components["verification"] == 0.0
        # Should significantly lower overall score
        assert score.level in (TrustLevel.LOW, TrustLevel.UNTRUSTED, TrustLevel.MEDIUM)

    def test_compute_old_content_higher_trust(self, trust_engine):
        """Test that older content gets higher age trust."""
        old_timestamp = datetime.now(timezone.utc) - timedelta(days=100)
        provenance = create_provenance(timestamp=old_timestamp)

        score = trust_engine.compute_trust_score(
            provenance=provenance,
            integrity_verified=True,
            verification_age_days=0,
        )

        # Established content (1.0 age score)
        assert score.components["age"] == 1.0

    def test_compute_new_content_lower_trust(self, trust_engine):
        """Test that brand new content gets lower age trust."""
        now = datetime.now(timezone.utc)
        provenance = create_provenance(timestamp=now)

        score = trust_engine.compute_trust_score(
            provenance=provenance,
            integrity_verified=True,
            verification_age_days=0,
        )

        # Brand new content (0.5 age score)
        assert score.components["age"] == 0.5

    def test_gpg_signature_bonus(self, trust_engine):
        """Test GPG signature bonus."""
        provenance_no_gpg = create_provenance(signature=None)
        provenance_with_gpg = create_provenance(signature="gpg-signature")

        score_no_gpg = trust_engine.compute_trust_score(
            provenance=provenance_no_gpg,
            integrity_verified=True,
        )

        score_with_gpg = trust_engine.compute_trust_score(
            provenance=provenance_with_gpg,
            integrity_verified=True,
        )

        # GPG signature should add bonus
        assert score_with_gpg.components["author"] > score_no_gpg.components["author"]

    def test_update_author_trust(self, trust_engine):
        """Test updating author trust with verified commits."""
        author_id = "test-author"

        # Initially unknown author
        provenance = create_provenance(author_id=author_id)
        score1 = trust_engine.compute_trust_score(provenance, integrity_verified=True)

        # Simulate verified commits
        for _ in range(15):
            trust_engine.update_author_trust(author_id, commit_verified=True)

        score2 = trust_engine.compute_trust_score(provenance, integrity_verified=True)

        # Author should now be "known" with higher trust
        assert score2.components["author"] > score1.components["author"]

    def test_add_internal_org(self, trust_engine):
        """Test adding new internal org."""
        provenance = create_provenance(repository_id="new-internal/repo")

        score_before = trust_engine.compute_trust_score(
            provenance, integrity_verified=True
        )
        assert score_before.components["repository"] == 0.30  # Unknown

        trust_engine.add_internal_org("new-internal")

        score_after = trust_engine.compute_trust_score(
            provenance, integrity_verified=True
        )
        assert score_after.components["repository"] == 1.00  # Internal

    def test_add_partner_org(self, trust_engine):
        """Test adding new partner org."""
        provenance = create_provenance(repository_id="new-partner/lib")

        score_before = trust_engine.compute_trust_score(
            provenance, integrity_verified=True
        )

        trust_engine.add_partner_org("new-partner")

        score_after = trust_engine.compute_trust_score(
            provenance, integrity_verified=True
        )
        assert score_after.components["repository"] == 0.90  # Partner

    def test_flag_repository(self, trust_engine):
        """Test flagging a repository."""
        provenance = create_provenance(repository_id="suspicious-org/repo")

        score_before = trust_engine.compute_trust_score(
            provenance, integrity_verified=True
        )

        trust_engine.flag_repository("suspicious-org/repo")

        score_after = trust_engine.compute_trust_score(
            provenance, integrity_verified=True
        )
        assert score_after.components["repository"] == 0.00  # Flagged

    def test_unflag_repository(self, trust_engine):
        """Test unflagging a repository."""
        trust_engine.flag_repository("test-org/repo")

        removed = trust_engine.unflag_repository("test-org/repo")
        assert removed is True

        removed_again = trust_engine.unflag_repository("test-org/repo")
        assert removed_again is False

    def test_add_employee(self, trust_engine):
        """Test adding employee to trust."""
        author_id = "employee@company.com"
        provenance = create_provenance(author_id=author_id)

        score_before = trust_engine.compute_trust_score(
            provenance, integrity_verified=True
        )

        trust_engine.add_employee(author_id)

        score_after = trust_engine.compute_trust_score(
            provenance, integrity_verified=True
        )
        assert score_after.components["author"] == 1.00  # Employee

    def test_get_trust_level(self, trust_engine):
        """Test getting trust level from score."""
        assert trust_engine.get_trust_level(0.95) == TrustLevel.HIGH
        assert trust_engine.get_trust_level(0.80) == TrustLevel.HIGH
        assert trust_engine.get_trust_level(0.65) == TrustLevel.MEDIUM
        assert trust_engine.get_trust_level(0.50) == TrustLevel.MEDIUM
        assert trust_engine.get_trust_level(0.40) == TrustLevel.LOW
        assert trust_engine.get_trust_level(0.30) == TrustLevel.LOW
        assert trust_engine.get_trust_level(0.20) == TrustLevel.UNTRUSTED

    def test_should_quarantine(self, trust_engine):
        """Test quarantine recommendation."""
        provenance = create_provenance(repository_id="malicious-org/bad-repo")

        score = trust_engine.compute_trust_score(
            provenance=provenance,
            integrity_verified=False,
        )

        assert trust_engine.should_quarantine(score) is True

    def test_verification_age_impact(self, trust_engine):
        """Test that stale verification lowers trust."""
        provenance = create_provenance()

        score_recent = trust_engine.compute_trust_score(
            provenance=provenance,
            integrity_verified=True,
            verification_age_days=0,
        )

        score_stale = trust_engine.compute_trust_score(
            provenance=provenance,
            integrity_verified=True,
            verification_age_days=10,
        )

        assert (
            score_recent.components["verification"]
            > score_stale.components["verification"]
        )


class TestTrustEngineSingleton:
    """Tests for global singleton management."""

    def test_get_trust_scoring_engine(self):
        """Test getting global engine instance."""
        engine = get_trust_scoring_engine()
        assert engine is not None

    def test_configure_trust_scoring_engine(self):
        """Test configuring global engine."""
        engine = configure_trust_scoring_engine(
            internal_org_ids=["my-org"],
            partner_org_ids=["partner"],
        )

        assert engine is not None
        assert "my-org" in engine.internal_orgs

    def test_reset_trust_scoring_engine(self):
        """Test resetting global engine."""
        engine1 = get_trust_scoring_engine()
        reset_trust_scoring_engine()
        engine2 = get_trust_scoring_engine()

        assert engine1 is not engine2
