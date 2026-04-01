"""
Project Aura - Trust Scoring Engine

Computes and maintains trust scores for content sources.
Trust scores are computed from repository reputation, author history,
content age, and verification status.

Security Rationale:
- Trust scoring enables risk-based decisions
- Multiple factors prevent single-point manipulation
- Weighted scoring balances security and usability
- Score tracking enables trend analysis

Author: Project Aura Team
Created: 2026-01-25
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from .config import TrustScoringConfig, get_trust_scoring_config
from .contracts import ProvenanceRecord, TrustLevel, TrustScore

logger = logging.getLogger(__name__)


class TrustScoringEngine:
    """
    Computes and maintains trust scores for content sources.

    Trust scores are computed from:
    - Repository reputation
    - Author history
    - Content age
    - Verification status

    Usage:
        engine = TrustScoringEngine(
            internal_org_ids=["aenea-labs"],
            partner_org_ids=["trusted-partner"],
        )
        score = engine.compute_trust_score(
            provenance=provenance_record,
            integrity_verified=True,
        )
    """

    def __init__(
        self,
        dynamodb_client: Optional[Any] = None,
        internal_org_ids: Optional[list[str]] = None,
        partner_org_ids: Optional[list[str]] = None,
        flagged_repo_ids: Optional[list[str]] = None,
        config: Optional[TrustScoringConfig] = None,
    ):
        """
        Initialize trust scoring engine.

        Args:
            dynamodb_client: DynamoDB client for trust data
            internal_org_ids: List of internal organization IDs
            partner_org_ids: List of verified partner org IDs
            flagged_repo_ids: List of flagged repository IDs
            config: Trust scoring configuration
        """
        self.dynamodb = dynamodb_client
        self.internal_orgs = set(internal_org_ids or [])
        self.partner_orgs = set(partner_org_ids or [])
        self.flagged_repos = set(flagged_repo_ids or [])
        self.config = config or get_trust_scoring_config()

        # Cache for author commit counts
        self._author_cache: dict[str, int] = {}
        self._employee_cache: set[str] = set()

        logger.debug(
            f"TrustScoringEngine initialized "
            f"(internal_orgs={len(self.internal_orgs)}, "
            f"partner_orgs={len(self.partner_orgs)})"
        )

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

        trust_score = TrustScore.compute(
            repository_score=repo_score,
            author_score=author_score,
            age_score=age_score,
            verification_score=verification_score,
        )

        logger.debug(
            f"Computed trust score: {trust_score.score:.2f} "
            f"({trust_score.level.value}) for repo={provenance.repository_id}"
        )

        return trust_score

    def _compute_repository_trust(self, repository_id: str) -> float:
        """Compute trust score for repository."""
        # Check for flagged repositories first
        if repository_id in self.flagged_repos:
            return self.config.repo_trust_flagged

        # Parse org from repository_id (format: org/repo)
        org = repository_id.split("/")[0] if "/" in repository_id else repository_id

        if org in self.internal_orgs:
            return self.config.repo_trust_internal
        elif org in self.partner_orgs:
            return self.config.repo_trust_partner
        else:
            # Could enhance with GitHub API data for public repos
            return self.config.repo_trust_unknown

    def _compute_author_trust(
        self,
        author_id: str,
        author_email: str,
        has_gpg: bool,
    ) -> float:
        """Compute trust score for author."""
        # Check if author is a known employee
        if author_id in self._employee_cache:
            return self.config.author_trust_employee

        # Get commit count from cache or database
        commit_count = self._get_author_commit_count(author_id)

        if commit_count > 10:
            base_score = self.config.author_trust_known
        elif commit_count >= 1:
            base_score = self.config.author_trust_contributor
        else:
            base_score = self.config.author_trust_first_time

        # Add GPG signature bonus
        if has_gpg:
            base_score = min(1.0, base_score + self.config.author_gpg_bonus)

        return base_score

    def _compute_age_trust(self, age: timedelta) -> float:
        """Compute trust score based on content age."""
        days = age.total_seconds() / 86400

        if days > 90:
            return self.config.age_trust_established  # Established
        elif days > 30:
            return self.config.age_trust_stable  # Stable
        elif days > 7:
            return self.config.age_trust_recent  # Recent
        elif days > 1:
            return self.config.age_trust_new  # New
        else:
            return self.config.age_trust_brand_new  # Brand new

    def _compute_verification_trust(
        self,
        integrity_verified: bool,
        verification_age_days: float,
    ) -> float:
        """Compute trust score based on verification status."""
        if not integrity_verified:
            return self.config.verification_trust_failed

        if verification_age_days <= 1:
            return self.config.verification_trust_recent  # Recent verification
        elif verification_age_days <= 7:
            return self.config.verification_trust_stale  # Slightly stale
        else:
            return self.config.verification_trust_old  # Stale verification

    def _get_author_commit_count(self, author_id: str) -> int:
        """Get verified commit count for author."""
        if author_id in self._author_cache:
            return self._author_cache[author_id]

        # Query DynamoDB for author history
        if self.dynamodb:
            try:
                response = self.dynamodb.get_item(
                    TableName="aura-author-trust",
                    Key={"author_id": {"S": author_id}},
                )
                if "Item" in response:
                    count = int(response["Item"].get("commit_count", {}).get("N", "0"))
                    self._author_cache[author_id] = count
                    return count
            except Exception as e:
                logger.warning(f"Failed to query author trust data: {e}")

        # Return 0 for unknown authors
        return 0

    def update_author_trust(
        self,
        author_id: str,
        commit_verified: bool,
    ) -> None:
        """
        Update author trust based on new verified commit.

        Args:
            author_id: Author identifier
            commit_verified: Whether the commit was verified
        """
        if commit_verified:
            current_count = self._author_cache.get(author_id, 0)
            self._author_cache[author_id] = current_count + 1

            # Persist to DynamoDB
            if self.dynamodb:
                try:
                    self.dynamodb.update_item(
                        TableName="aura-author-trust",
                        Key={"author_id": {"S": author_id}},
                        UpdateExpression="ADD commit_count :inc",
                        ExpressionAttributeValues={":inc": {"N": "1"}},
                    )
                except Exception as e:
                    logger.warning(f"Failed to update author trust: {e}")

    def add_internal_org(self, org_id: str) -> None:
        """Add an organization to the internal orgs list."""
        self.internal_orgs.add(org_id)

    def add_partner_org(self, org_id: str) -> None:
        """Add an organization to the partner orgs list."""
        self.partner_orgs.add(org_id)

    def flag_repository(self, repo_id: str) -> None:
        """Flag a repository as suspicious."""
        self.flagged_repos.add(repo_id)
        logger.warning(f"Repository flagged: {repo_id}")

    def unflag_repository(self, repo_id: str) -> bool:
        """Unflag a repository."""
        if repo_id in self.flagged_repos:
            self.flagged_repos.remove(repo_id)
            logger.info(f"Repository unflagged: {repo_id}")
            return True
        return False

    def add_employee(self, author_id: str) -> None:
        """Add an author to the employee cache."""
        self._employee_cache.add(author_id)

    def get_trust_level(self, score: float) -> TrustLevel:
        """
        Get trust level for a given score.

        Args:
            score: Trust score (0.0 - 1.0)

        Returns:
            Corresponding TrustLevel
        """
        if score >= 0.80:
            return TrustLevel.HIGH
        elif score >= 0.50:
            return TrustLevel.MEDIUM
        elif score >= 0.30:
            return TrustLevel.LOW
        else:
            return TrustLevel.UNTRUSTED

    def should_quarantine(self, trust_score: TrustScore) -> bool:
        """
        Check if content should be quarantined based on trust score.

        Args:
            trust_score: Computed trust score

        Returns:
            True if content should be quarantined
        """
        return trust_score.level == TrustLevel.UNTRUSTED


# =============================================================================
# Module-Level Functions
# =============================================================================


_trust_scoring_engine: Optional[TrustScoringEngine] = None


def get_trust_scoring_engine() -> TrustScoringEngine:
    """Get the global trust scoring engine instance."""
    global _trust_scoring_engine
    if _trust_scoring_engine is None:
        _trust_scoring_engine = TrustScoringEngine()
        logger.info("TrustScoringEngine initialized with defaults")
    return _trust_scoring_engine


def configure_trust_scoring_engine(
    dynamodb_client: Optional[Any] = None,
    internal_org_ids: Optional[list[str]] = None,
    partner_org_ids: Optional[list[str]] = None,
    flagged_repo_ids: Optional[list[str]] = None,
    config: Optional[TrustScoringConfig] = None,
) -> TrustScoringEngine:
    """Configure the global trust scoring engine."""
    global _trust_scoring_engine
    _trust_scoring_engine = TrustScoringEngine(
        dynamodb_client=dynamodb_client,
        internal_org_ids=internal_org_ids,
        partner_org_ids=partner_org_ids,
        flagged_repo_ids=flagged_repo_ids,
        config=config,
    )
    return _trust_scoring_engine


def reset_trust_scoring_engine() -> None:
    """Reset the global trust scoring engine (for testing)."""
    global _trust_scoring_engine
    _trust_scoring_engine = None
