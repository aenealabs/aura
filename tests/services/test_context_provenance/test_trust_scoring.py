"""
Tests for trust scoring engine.

Tests trust score computation from repository, author, age, and verification.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.services.context_provenance import (
    ProvenanceRecord,
    TrustLevel,
    TrustScoringConfig,
    TrustScoringEngine,
    get_trust_scoring_engine,
    reset_trust_scoring_engine,
)


class TestTrustScoringEngine:
    """Test TrustScoringEngine class."""

    def test_initialization(self):
        """Test engine initialization."""
        engine = TrustScoringEngine()
        assert engine.dynamodb is None
        assert len(engine.internal_orgs) == 0
        assert len(engine.partner_orgs) == 0

    def test_initialization_with_orgs(self):
        """Test engine initialization with org lists."""
        engine = TrustScoringEngine(
            internal_org_ids=["org1", "org2"],
            partner_org_ids=["partner1"],
            flagged_repo_ids=["bad-repo"],
        )
        assert "org1" in engine.internal_orgs
        assert "org2" in engine.internal_orgs
        assert "partner1" in engine.partner_orgs
        assert "bad-repo" in engine.flagged_repos

    def test_initialization_with_config(self):
        """Test engine initialization with custom config."""
        config = TrustScoringConfig(repo_trust_internal=0.95)
        engine = TrustScoringEngine(config=config)
        assert engine.config.repo_trust_internal == 0.95


class TestComputeTrustScore:
    """Test compute_trust_score method."""

    @pytest.fixture
    def engine(self):
        """Create engine for tests."""
        return TrustScoringEngine(
            internal_org_ids=["aenea-labs"],
            partner_org_ids=["trusted-partner"],
            flagged_repo_ids=["malicious-org/bad-repo"],
        )

    def test_high_trust_internal_repo(self, engine: TrustScoringEngine):
        """Test high trust for internal repository."""
        provenance = ProvenanceRecord(
            repository_id="aenea-labs/core-lib",
            commit_sha="abc123",
            author_id="employee-001",
            author_email="dev@aenea-labs.com",
            timestamp=datetime.now(timezone.utc) - timedelta(days=100),
            branch="main",
            signature="gpg-sig",
        )
        # Register as employee
        engine._employee_cache.add("employee-001")

        score = engine.compute_trust_score(
            provenance=provenance,
            integrity_verified=True,
            verification_age_days=0,
        )

        assert score.level == TrustLevel.HIGH
        assert score.score >= 0.80

    def test_medium_trust_partner_repo(self, engine: TrustScoringEngine):
        """Test medium trust for partner repository."""
        provenance = ProvenanceRecord(
            repository_id="trusted-partner/their-lib",
            commit_sha="def456",
            author_id="partner-dev",
            author_email="dev@partner.com",
            timestamp=datetime.now(timezone.utc) - timedelta(days=45),
            branch="main",
            signature=None,
        )
        # Add some commit history
        engine._author_cache["partner-dev"] = 5

        score = engine.compute_trust_score(
            provenance=provenance,
            integrity_verified=True,
            verification_age_days=1,
        )

        assert score.level in (TrustLevel.MEDIUM, TrustLevel.HIGH)

    def test_low_trust_unknown_repo(self, engine: TrustScoringEngine):
        """Test lower trust for unknown repository."""
        provenance = ProvenanceRecord(
            repository_id="random-org/random-repo",
            commit_sha="xyz789",
            author_id="unknown-author",
            author_email="author@unknown.com",
            timestamp=datetime.now(timezone.utc) - timedelta(hours=12),
            branch="main",
            signature=None,
        )

        score = engine.compute_trust_score(
            provenance=provenance,
            integrity_verified=True,
            verification_age_days=0,
        )

        # Unknown repo + first-time author + brand new = lower trust
        assert score.components["repository"] <= 0.5
        assert score.components["author"] <= 0.6

    def test_flagged_repo_zero_repository_score(self, engine: TrustScoringEngine):
        """Test that flagged repository gets zero repository score."""
        provenance = ProvenanceRecord(
            repository_id="malicious-org/bad-repo",
            commit_sha="bad123",
            author_id="attacker",
            author_email="attacker@evil.com",
            timestamp=datetime.now(timezone.utc) - timedelta(days=5),
            branch="main",
            signature=None,
        )

        score = engine.compute_trust_score(
            provenance=provenance,
            integrity_verified=True,
            verification_age_days=0,
        )

        # Flagged repo should have 0.0 repository score
        assert score.components["repository"] == 0.0
        # Overall score is low because other factors contribute
        assert score.level in (TrustLevel.LOW, TrustLevel.UNTRUSTED)

    def test_failed_integrity_lowers_score(self, engine: TrustScoringEngine):
        """Test that failed integrity lowers trust score."""
        provenance = ProvenanceRecord(
            repository_id="aenea-labs/core-lib",
            commit_sha="abc123",
            author_id="employee-001",
            author_email="dev@aenea-labs.com",
            timestamp=datetime.now(timezone.utc) - timedelta(days=100),
            branch="main",
            signature="gpg-sig",
        )
        engine._employee_cache.add("employee-001")

        verified_score = engine.compute_trust_score(
            provenance=provenance,
            integrity_verified=True,
        )

        failed_score = engine.compute_trust_score(
            provenance=provenance,
            integrity_verified=False,
        )

        assert failed_score.score < verified_score.score
        assert failed_score.components["verification"] == 0.0


class TestRepositoryTrust:
    """Test repository trust computation."""

    @pytest.fixture
    def engine(self):
        """Create engine for tests."""
        return TrustScoringEngine(
            internal_org_ids=["internal-org"],
            partner_org_ids=["partner-org"],
            flagged_repo_ids=["bad-org/flagged-repo"],
        )

    def test_internal_org_trust(self, engine: TrustScoringEngine):
        """Test trust for internal organization."""
        score = engine._compute_repository_trust("internal-org/some-repo")
        assert score == 1.0

    def test_partner_org_trust(self, engine: TrustScoringEngine):
        """Test trust for partner organization."""
        score = engine._compute_repository_trust("partner-org/their-repo")
        assert score == 0.9

    def test_unknown_org_trust(self, engine: TrustScoringEngine):
        """Test trust for unknown organization."""
        score = engine._compute_repository_trust("random-org/random-repo")
        assert score == 0.3  # repo_trust_unknown default

    def test_flagged_repo_trust(self, engine: TrustScoringEngine):
        """Test trust for flagged repository."""
        score = engine._compute_repository_trust("bad-org/flagged-repo")
        assert score == 0.0

    def test_repo_without_org(self, engine: TrustScoringEngine):
        """Test trust for repo ID without org prefix."""
        score = engine._compute_repository_trust("standalone-repo")
        assert score == 0.3  # Treated as unknown


class TestAuthorTrust:
    """Test author trust computation."""

    @pytest.fixture
    def engine(self):
        """Create engine for tests."""
        return TrustScoringEngine()

    def test_employee_trust(self, engine: TrustScoringEngine):
        """Test trust for known employee."""
        engine._employee_cache.add("employee-001")
        score = engine._compute_author_trust(
            "employee-001", "emp@company.com", has_gpg=False
        )
        assert score == 1.0

    def test_known_contributor_trust(self, engine: TrustScoringEngine):
        """Test trust for known contributor with >10 commits."""
        engine._author_cache["known-author"] = 15
        score = engine._compute_author_trust(
            "known-author", "known@test.com", has_gpg=False
        )
        assert score == 0.9  # author_trust_known default

    def test_contributor_trust(self, engine: TrustScoringEngine):
        """Test trust for contributor with 1-10 commits."""
        engine._author_cache["contributor"] = 5
        score = engine._compute_author_trust(
            "contributor", "contrib@test.com", has_gpg=False
        )
        assert score == 0.7  # author_trust_contributor default

    def test_first_time_author_trust(self, engine: TrustScoringEngine):
        """Test trust for first-time author."""
        score = engine._compute_author_trust(
            "new-author", "new@test.com", has_gpg=False
        )
        assert score == 0.5  # author_trust_first_time default

    def test_gpg_bonus(self, engine: TrustScoringEngine):
        """Test GPG signature bonus."""
        engine._author_cache["author"] = 5
        without_gpg = engine._compute_author_trust(
            "author", "a@test.com", has_gpg=False
        )
        with_gpg = engine._compute_author_trust("author", "a@test.com", has_gpg=True)
        assert with_gpg == without_gpg + 0.1

    def test_gpg_bonus_capped_at_one(self, engine: TrustScoringEngine):
        """Test GPG bonus doesn't exceed 1.0."""
        engine._employee_cache.add("employee")
        score = engine._compute_author_trust("employee", "e@test.com", has_gpg=True)
        assert score == 1.0  # Capped at 1.0


class TestAgeTrust:
    """Test age trust computation."""

    @pytest.fixture
    def engine(self):
        """Create engine for tests."""
        return TrustScoringEngine()

    def test_established_content(self, engine: TrustScoringEngine):
        """Test trust for established content (>90 days)."""
        age = timedelta(days=100)
        score = engine._compute_age_trust(age)
        assert score == 1.0

    def test_stable_content(self, engine: TrustScoringEngine):
        """Test trust for stable content (30-90 days)."""
        age = timedelta(days=45)
        score = engine._compute_age_trust(age)
        assert score == 0.9

    def test_recent_content(self, engine: TrustScoringEngine):
        """Test trust for recent content (7-30 days)."""
        age = timedelta(days=14)
        score = engine._compute_age_trust(age)
        assert score == 0.8

    def test_new_content(self, engine: TrustScoringEngine):
        """Test trust for new content (1-7 days)."""
        age = timedelta(days=3)
        score = engine._compute_age_trust(age)
        assert score == 0.7

    def test_brand_new_content(self, engine: TrustScoringEngine):
        """Test trust for brand new content (<1 day)."""
        age = timedelta(hours=12)
        score = engine._compute_age_trust(age)
        assert score == 0.5


class TestVerificationTrust:
    """Test verification trust computation."""

    @pytest.fixture
    def engine(self):
        """Create engine for tests."""
        return TrustScoringEngine()

    def test_verified_recent(self, engine: TrustScoringEngine):
        """Test trust for recently verified content."""
        score = engine._compute_verification_trust(
            integrity_verified=True, verification_age_days=0
        )
        assert score == 1.0

    def test_verified_stale(self, engine: TrustScoringEngine):
        """Test trust for stale verified content (1-7 days)."""
        score = engine._compute_verification_trust(
            integrity_verified=True, verification_age_days=5
        )
        assert score == 0.9

    def test_verified_old(self, engine: TrustScoringEngine):
        """Test trust for old verified content (>30 days)."""
        score = engine._compute_verification_trust(
            integrity_verified=True, verification_age_days=45
        )
        assert score == 0.7

    def test_failed_verification(self, engine: TrustScoringEngine):
        """Test trust for failed verification."""
        score = engine._compute_verification_trust(
            integrity_verified=False, verification_age_days=0
        )
        assert score == 0.0


class TestAuthorManagement:
    """Test author registration and lookup."""

    @pytest.fixture
    def engine(self):
        """Create engine for tests."""
        return TrustScoringEngine()

    def test_add_employee(self, engine: TrustScoringEngine):
        """Test adding an employee."""
        engine.add_employee("emp-001")
        assert "emp-001" in engine._employee_cache

    def test_remove_employee_from_cache(self, engine: TrustScoringEngine):
        """Test removing an employee from cache directly."""
        engine.add_employee("emp-001")
        engine._employee_cache.remove("emp-001")
        assert "emp-001" not in engine._employee_cache

    def test_update_author_trust(self, engine: TrustScoringEngine):
        """Test updating author trust with verified commit."""
        engine.update_author_trust("author-001", commit_verified=True)
        assert engine._author_cache["author-001"] == 1
        engine.update_author_trust("author-001", commit_verified=True)
        assert engine._author_cache["author-001"] == 2

    def test_update_author_trust_unverified(self, engine: TrustScoringEngine):
        """Test that unverified commits don't update cache."""
        engine.update_author_trust("author-001", commit_verified=False)
        assert "author-001" not in engine._author_cache

    def test_get_author_commit_count(self, engine: TrustScoringEngine):
        """Test getting author commit count."""
        assert engine._get_author_commit_count("unknown") == 0
        engine._author_cache["known"] = 5
        assert engine._get_author_commit_count("known") == 5


class TestOrgManagement:
    """Test organization management."""

    @pytest.fixture
    def engine(self):
        """Create engine for tests."""
        return TrustScoringEngine()

    def test_add_internal_org(self, engine: TrustScoringEngine):
        """Test adding internal organization."""
        engine.add_internal_org("new-org")
        assert "new-org" in engine.internal_orgs

    def test_remove_internal_org_from_set(self, engine: TrustScoringEngine):
        """Test removing internal organization from set directly."""
        engine.internal_orgs.add("org-to-remove")
        engine.internal_orgs.remove("org-to-remove")
        assert "org-to-remove" not in engine.internal_orgs

    def test_add_partner_org(self, engine: TrustScoringEngine):
        """Test adding partner organization."""
        engine.add_partner_org("new-partner")
        assert "new-partner" in engine.partner_orgs

    def test_flag_repository(self, engine: TrustScoringEngine):
        """Test flagging a repository."""
        engine.flag_repository("bad/repo")
        assert "bad/repo" in engine.flagged_repos

    def test_unflag_repository(self, engine: TrustScoringEngine):
        """Test unflagging a repository."""
        engine.flagged_repos.add("repo-to-unflag")
        engine.unflag_repository("repo-to-unflag")
        assert "repo-to-unflag" not in engine.flagged_repos


class TestGetTrustLevel:
    """Test get_trust_level helper method."""

    @pytest.fixture
    def engine(self):
        """Create engine for tests."""
        return TrustScoringEngine()

    def test_get_trust_level_high(self, engine: TrustScoringEngine):
        """Test get_trust_level for high score."""
        level = engine.get_trust_level(0.85)
        assert level == TrustLevel.HIGH

    def test_get_trust_level_medium(self, engine: TrustScoringEngine):
        """Test get_trust_level for medium score."""
        level = engine.get_trust_level(0.65)
        assert level == TrustLevel.MEDIUM

    def test_get_trust_level_low(self, engine: TrustScoringEngine):
        """Test get_trust_level for low score."""
        level = engine.get_trust_level(0.35)
        assert level == TrustLevel.LOW

    def test_get_trust_level_untrusted(self, engine: TrustScoringEngine):
        """Test get_trust_level for untrusted score."""
        level = engine.get_trust_level(0.25)
        assert level == TrustLevel.UNTRUSTED

    def test_get_trust_level_boundary_high(self, engine: TrustScoringEngine):
        """Test boundary at 0.80."""
        assert engine.get_trust_level(0.80) == TrustLevel.HIGH
        assert engine.get_trust_level(0.79) == TrustLevel.MEDIUM

    def test_get_trust_level_boundary_medium(self, engine: TrustScoringEngine):
        """Test boundary at 0.50."""
        assert engine.get_trust_level(0.50) == TrustLevel.MEDIUM
        assert engine.get_trust_level(0.49) == TrustLevel.LOW


class TestSingletonFunctions:
    """Test singleton management functions."""

    def test_get_trust_scoring_engine(self):
        """Test get_trust_scoring_engine returns singleton."""
        engine1 = get_trust_scoring_engine()
        engine2 = get_trust_scoring_engine()
        assert engine1 is engine2

    def test_reset_trust_scoring_engine(self):
        """Test reset_trust_scoring_engine creates new instance."""
        engine1 = get_trust_scoring_engine()
        reset_trust_scoring_engine()
        engine2 = get_trust_scoring_engine()
        assert engine1 is not engine2
