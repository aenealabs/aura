"""
Tests for inter-agent verifier.
"""

import pytest

from src.services.explainability.config import InterAgentConfig
from src.services.explainability.inter_agent import (
    InterAgentVerifier,
    configure_inter_agent_verifier,
    get_inter_agent_verifier,
    reset_inter_agent_verifier,
)


class TestInterAgentVerifier:
    """Tests for InterAgentVerifier class."""

    def setup_method(self):
        """Reset verifier before each test."""
        reset_inter_agent_verifier()

    def teardown_method(self):
        """Reset verifier after each test."""
        reset_inter_agent_verifier()

    def test_init_without_neptune(self):
        """Test initialization without Neptune client."""
        verifier = InterAgentVerifier()
        assert verifier.neptune is None
        assert verifier.config is not None

    def test_init_with_config(self):
        """Test initialization with custom config."""
        config = InterAgentConfig(trust_adjustment_range=0.3)
        verifier = InterAgentVerifier(config=config)
        assert verifier.config.trust_adjustment_range == 0.3

    @pytest.mark.asyncio
    async def test_verify_claims_empty(self):
        """Test verifying empty claims list."""
        verifier = InterAgentVerifier()
        report = await verifier.verify_claims(
            decision_id="dec_test",
            claims=[],
        )

        assert report.decision_id == "dec_test"
        assert len(report.verifications) == 0

    @pytest.mark.asyncio
    async def test_verify_claims_single(self, sample_upstream_claims):
        """Test verifying a single claim."""
        verifier = InterAgentVerifier()
        report = await verifier.verify_claims(
            decision_id="dec_test",
            claims=[sample_upstream_claims[0]],
        )

        assert report.decision_id == "dec_test"
        assert len(report.verifications) == 1

    @pytest.mark.asyncio
    async def test_verify_claims_multiple(self, sample_upstream_claims):
        """Test verifying multiple claims."""
        verifier = InterAgentVerifier()
        report = await verifier.verify_claims(
            decision_id="dec_test",
            claims=sample_upstream_claims,
        )

        assert report.decision_id == "dec_test"
        assert len(report.verifications) == len(sample_upstream_claims)

    def test_verify_claims_sync_empty(self):
        """Test synchronous verification of empty claims."""
        verifier = InterAgentVerifier()
        report = verifier.verify_claims_sync(
            decision_id="dec_test",
            claims=[],
        )

        assert report.decision_id == "dec_test"
        assert len(report.verifications) == 0

    def test_verify_claims_sync_single(self, sample_upstream_claims):
        """Test synchronous verification of a single claim."""
        verifier = InterAgentVerifier()
        report = verifier.verify_claims_sync(
            decision_id="dec_test",
            claims=[sample_upstream_claims[0]],
        )

        assert report.decision_id == "dec_test"
        assert len(report.verifications) == 1

    @pytest.mark.asyncio
    async def test_verify_security_claim_with_evidence(self):
        """Test verifying security claim with evidence."""
        verifier = InterAgentVerifier()
        claim = {
            "agent_id": "scanner",
            "claim_type": "security_assessment",
            "claim_text": "Found critical vulnerability",
            "evidence": ["CVE-2024-1234", "OWASP A03:2021"],
            "confidence": 0.95,
        }

        result = await verifier._verify_security_claim(claim)
        assert result["verified"] is True
        assert result["confidence"] > 0.5

    @pytest.mark.asyncio
    async def test_verify_security_claim_without_evidence(self):
        """Test verifying security claim without evidence."""
        verifier = InterAgentVerifier()
        claim = {
            "agent_id": "scanner",
            "claim_type": "security_assessment",
            "claim_text": "System is secure",
            "evidence": [],
            "confidence": 0.9,
        }

        result = await verifier._verify_security_claim(claim)
        assert result["verified"] is False
        assert result["discrepancy"] is not None

    @pytest.mark.asyncio
    async def test_verify_test_claim_with_execution_evidence(self):
        """Test verifying test claim with execution evidence."""
        verifier = InterAgentVerifier()
        claim = {
            "agent_id": "test_runner",
            "claim_type": "test_result",
            "claim_text": "All tests passed",
            "evidence": ["50 tests executed", "0 failures"],
            "confidence": 0.99,
        }

        result = await verifier._verify_test_claim(claim)
        assert result["verified"] is True
        assert result["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_verify_test_claim_without_execution_evidence(self):
        """Test verifying test claim without execution evidence."""
        verifier = InterAgentVerifier()
        claim = {
            "agent_id": "test_runner",
            "claim_type": "test_result",
            "claim_text": "Tests look good",
            "evidence": ["code review complete"],
            "confidence": 0.8,
        }

        result = await verifier._verify_test_claim(claim)
        assert result["verified"] is False
        assert result["confidence"] < 0.5

    @pytest.mark.asyncio
    async def test_verify_code_analysis_claim_with_references(self):
        """Test verifying code analysis claim with file references."""
        verifier = InterAgentVerifier()
        claim = {
            "agent_id": "analyzer",
            "claim_type": "code_analysis",
            "claim_text": "Found potential issue",
            "evidence": [
                "app.py:42 - unused variable",
                "utils.js:15 - missing null check",
            ],
            "confidence": 0.85,
        }

        result = await verifier._verify_code_analysis_claim(claim)
        assert result["verified"] is True
        assert result["confidence"] == 0.90

    @pytest.mark.asyncio
    async def test_verify_code_analysis_claim_without_references(self):
        """Test verifying code analysis claim without file references."""
        verifier = InterAgentVerifier()
        claim = {
            "agent_id": "analyzer",
            "claim_type": "code_analysis",
            "claim_text": "Code quality issues found",
            "evidence": ["Some issues exist"],
            "confidence": 0.7,
        }

        result = await verifier._verify_code_analysis_claim(claim)
        assert result["confidence"] <= 0.7

    @pytest.mark.asyncio
    async def test_verify_vulnerability_claim_with_cve(self):
        """Test verifying vulnerability claim with CVE reference."""
        verifier = InterAgentVerifier()
        claim = {
            "agent_id": "vuln_scanner",
            "claim_type": "vulnerability_found",
            "claim_text": "Critical vulnerability detected",
            "evidence": ["CVE-2024-1234 confirmed", "CWE-79 XSS"],
            "confidence": 0.95,
        }

        result = await verifier._verify_vulnerability_claim(claim)
        assert result["verified"] is True
        assert result["confidence"] == 0.92

    @pytest.mark.asyncio
    async def test_verify_vulnerability_claim_without_cve(self):
        """Test verifying vulnerability claim without CVE reference."""
        verifier = InterAgentVerifier()
        claim = {
            "agent_id": "vuln_scanner",
            "claim_type": "vulnerability_found",
            "claim_text": "Potential security issue",
            "evidence": ["Manual review found issue", "Needs attention"],
            "confidence": 0.7,
        }

        result = await verifier._verify_vulnerability_claim(claim)
        assert result["verified"] is True  # Has evidence
        assert result["discrepancy"] is not None  # No CVE

    @pytest.mark.asyncio
    async def test_verify_review_claim_with_evidence(self):
        """Test verifying review claim with review evidence."""
        verifier = InterAgentVerifier()
        claim = {
            "agent_id": "reviewer",
            "claim_type": "review_complete",
            "claim_text": "Code review completed",
            "evidence": ["Reviewed by senior engineer", "Approved with minor findings"],
            "confidence": 0.9,
        }

        result = await verifier._verify_review_claim(claim)
        assert result["verified"] is True
        assert result["confidence"] == 0.88

    @pytest.mark.asyncio
    async def test_verify_review_claim_without_evidence(self):
        """Test verifying review claim without review evidence."""
        verifier = InterAgentVerifier()
        claim = {
            "agent_id": "reviewer",
            "claim_type": "review_complete",
            "claim_text": "Review done",
            "evidence": ["Completed task"],
            "confidence": 0.9,
        }

        result = await verifier._verify_review_claim(claim)
        assert result["verified"] is False
        assert result["confidence"] < 0.5

    @pytest.mark.asyncio
    async def test_verify_generic_claim_with_evidence(self):
        """Test verifying generic claim with evidence."""
        verifier = InterAgentVerifier()
        claim = {
            "agent_id": "generic_agent",
            "claim_type": "unknown_type",
            "claim_text": "Task completed",
            "evidence": ["Output generated", "Process finished"],
            "confidence": 0.8,
        }

        result = await verifier._verify_generic_claim(claim)
        assert result["verified"] is True
        assert result["confidence"] == 0.5

    @pytest.mark.asyncio
    async def test_verify_generic_claim_without_evidence(self):
        """Test verifying generic claim without evidence."""
        verifier = InterAgentVerifier()
        claim = {
            "agent_id": "generic_agent",
            "claim_type": "unknown_type",
            "claim_text": "Task completed",
            "evidence": [],
            "confidence": 0.8,
        }

        result = await verifier._verify_generic_claim(claim)
        assert result["verified"] is False

    def test_verify_generic_claim_sync_with_evidence(self):
        """Test synchronous generic claim verification with evidence."""
        verifier = InterAgentVerifier()
        claim = {
            "agent_id": "agent",
            "claim_type": "unknown",
            "claim_text": "Done",
            "evidence": ["Complete"],
            "confidence": 0.8,
        }

        result = verifier._verify_generic_claim_sync(claim)
        assert result["verified"] is True

    def test_verify_generic_claim_sync_without_evidence(self):
        """Test synchronous generic claim verification without evidence."""
        verifier = InterAgentVerifier()
        claim = {
            "agent_id": "agent",
            "claim_type": "unknown",
            "claim_text": "Done",
            "evidence": [],
            "confidence": 0.8,
        }

        result = verifier._verify_generic_claim_sync(claim)
        assert result["verified"] is False

    def test_get_verification_strategy(self):
        """Test getting appropriate verification strategy."""
        verifier = InterAgentVerifier()

        strategy = verifier._get_verification_strategy("security_assessment")
        assert strategy == verifier._verify_security_claim

        strategy = verifier._get_verification_strategy("test_result")
        assert strategy == verifier._verify_test_claim

        strategy = verifier._get_verification_strategy("code_analysis")
        assert strategy == verifier._verify_code_analysis_claim

        strategy = verifier._get_verification_strategy("unknown_type")
        assert strategy == verifier._verify_generic_claim

    def test_trust_adjustment_calculation(self, sample_upstream_claims):
        """Test trust adjustment calculation."""
        verifier = InterAgentVerifier()
        report = verifier.verify_claims_sync(
            decision_id="dec_test",
            claims=sample_upstream_claims,
        )

        # Trust adjustment should be based on average confidence
        assert -0.2 <= report.trust_adjustment <= 0.2

    def test_verification_failures_counted(self):
        """Test that verification failures are counted."""
        verifier = InterAgentVerifier()
        claims = [
            {
                "agent_id": "agent1",
                "claim_type": "security_assessment",
                "claim_text": "Secure",
                "evidence": [],  # Will fail - no evidence
                "confidence": 0.9,
            },
            {
                "agent_id": "agent2",
                "claim_type": "test_result",
                "claim_text": "Tests pass",
                "evidence": ["50 tests passed"],  # Will pass
                "confidence": 0.9,
            },
        ]

        report = verifier.verify_claims_sync(
            decision_id="dec_test",
            claims=claims,
        )

        # Should have 1 failure (security claim without evidence)
        assert report.verification_failures >= 1


class TestGlobalVerifierManagement:
    """Tests for global verifier management functions."""

    def setup_method(self):
        """Reset verifier before each test."""
        reset_inter_agent_verifier()

    def teardown_method(self):
        """Reset verifier after each test."""
        reset_inter_agent_verifier()

    def test_get_inter_agent_verifier(self):
        """Test getting the global verifier."""
        verifier = get_inter_agent_verifier()
        assert verifier is not None
        assert isinstance(verifier, InterAgentVerifier)

    def test_configure_inter_agent_verifier(self, mock_neptune_client):
        """Test configuring the global verifier."""
        config = InterAgentConfig(trust_adjustment_range=0.3)
        verifier = configure_inter_agent_verifier(
            neptune_client=mock_neptune_client,
            config=config,
        )

        assert verifier.neptune is mock_neptune_client
        assert verifier.config.trust_adjustment_range == 0.3

    def test_reset_inter_agent_verifier(self):
        """Test resetting the global verifier."""
        config = InterAgentConfig(trust_adjustment_range=0.3)
        configure_inter_agent_verifier(config=config)

        reset_inter_agent_verifier()

        verifier = get_inter_agent_verifier()
        assert verifier.config.trust_adjustment_range == 0.2  # Default

    def test_verifier_singleton(self):
        """Test that get returns the same instance."""
        v1 = get_inter_agent_verifier()
        v2 = get_inter_agent_verifier()
        assert v1 is v2
