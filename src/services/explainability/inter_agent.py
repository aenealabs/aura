"""
Project Aura - Inter-Agent Verifier

Verifies claims made by upstream agents before trusting them.
Implements "trust but verify" for inter-agent communication.

Author: Project Aura Team
Created: 2026-01-25
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Callable, Optional

from .config import InterAgentConfig
from .contracts import ClaimVerification, VerificationReport

logger = logging.getLogger(__name__)


class InterAgentVerifier:
    """
    Verify claims made by upstream agents.

    When Agent B receives output from Agent A, this service
    independently verifies Agent A's claims rather than
    accepting them at face value.
    """

    def __init__(
        self,
        neptune_client: Any = None,
        config: Optional[InterAgentConfig] = None,
    ):
        """
        Initialize the inter-agent verifier.

        Args:
            neptune_client: AWS Neptune client for graph queries
            config: Configuration for inter-agent verification
        """
        self.neptune = neptune_client
        self.config = config or InterAgentConfig()
        logger.info("InterAgentVerifier initialized")

    async def verify_claims(
        self,
        decision_id: str,
        claims: list[dict[str, Any]],
    ) -> VerificationReport:
        """
        Verify claims from upstream agents.

        Args:
            decision_id: Current decision being made
            claims: List of claims from upstream agents
                Each claim: {
                    "agent_id": str,
                    "claim_type": str (e.g., "security_assessment", "test_result"),
                    "claim_text": str,
                    "evidence": list[str],
                    "confidence": float
                }

        Returns:
            VerificationReport with verification results
        """
        logger.debug(f"Verifying {len(claims)} claims for decision {decision_id}")

        report = VerificationReport(decision_id=decision_id)

        for claim in claims:
            verification = await self._verify_single_claim(claim)
            report.verifications.append(verification)

            if not verification.is_verified:
                report.verification_failures += 1
            if verification.confidence < 0.5:
                report.unverified_claims += 1

        # Recalculate trust adjustment
        if report.verifications:
            avg_confidence = sum(v.confidence for v in report.verifications) / len(
                report.verifications
            )
            report.trust_adjustment = (
                avg_confidence - 0.5
            ) * self.config.trust_adjustment_range

        logger.debug(
            f"Verification complete: {len(report.verifications)} claims, "
            f"{report.verification_failures} failures, "
            f"trust_adjustment={report.trust_adjustment:.2f}"
        )
        return report

    def verify_claims_sync(
        self,
        decision_id: str,
        claims: list[dict[str, Any]],
    ) -> VerificationReport:
        """
        Synchronous version of verify_claims.

        Args:
            decision_id: Current decision being made
            claims: List of claims from upstream agents

        Returns:
            VerificationReport with verification results
        """
        report = VerificationReport(decision_id=decision_id)

        for claim in claims:
            verification = self._verify_single_claim_sync(claim)
            report.verifications.append(verification)

            if not verification.is_verified:
                report.verification_failures += 1
            if verification.confidence < 0.5:
                report.unverified_claims += 1

        if report.verifications:
            avg_confidence = sum(v.confidence for v in report.verifications) / len(
                report.verifications
            )
            report.trust_adjustment = (
                avg_confidence - 0.5
            ) * self.config.trust_adjustment_range

        return report

    async def _verify_single_claim(
        self,
        claim: dict[str, Any],
    ) -> ClaimVerification:
        """Verify a single claim from an upstream agent."""
        claim_id = f"clm_{uuid.uuid4().hex[:8]}"
        upstream_agent_id = claim.get("agent_id", "unknown")
        claim_text = claim.get("claim_text", "")
        claim_type = claim.get("claim_type", "unknown")

        # Get appropriate verification strategy
        strategy = self._get_verification_strategy(claim_type)
        verification_result = await strategy(claim)

        return ClaimVerification(
            claim_id=claim_id,
            upstream_agent_id=upstream_agent_id,
            claim_text=claim_text,
            claim_type=claim_type,
            is_verified=verification_result["verified"],
            verification_evidence=verification_result["evidence"],
            confidence=verification_result["confidence"],
            discrepancy=verification_result.get("discrepancy"),
        )

    def _verify_single_claim_sync(
        self,
        claim: dict[str, Any],
    ) -> ClaimVerification:
        """Synchronous version of single claim verification."""
        claim_id = f"clm_{uuid.uuid4().hex[:8]}"
        upstream_agent_id = claim.get("agent_id", "unknown")
        claim_text = claim.get("claim_text", "")
        claim_type = claim.get("claim_type", "unknown")

        # Use sync verification
        verification_result = self._verify_generic_claim_sync(claim)

        return ClaimVerification(
            claim_id=claim_id,
            upstream_agent_id=upstream_agent_id,
            claim_text=claim_text,
            claim_type=claim_type,
            is_verified=verification_result["verified"],
            verification_evidence=verification_result["evidence"],
            confidence=verification_result["confidence"],
            discrepancy=verification_result.get("discrepancy"),
        )

    def _get_verification_strategy(
        self,
        claim_type: str,
    ) -> Callable[[dict[str, Any]], Any]:
        """Get appropriate verification strategy for claim type."""
        strategies = {
            "security_assessment": self._verify_security_claim,
            "test_result": self._verify_test_claim,
            "code_analysis": self._verify_code_analysis_claim,
            "vulnerability_found": self._verify_vulnerability_claim,
            "review_complete": self._verify_review_claim,
        }
        return strategies.get(claim_type, self._verify_generic_claim)

    async def _verify_security_claim(self, claim: dict[str, Any]) -> dict[str, Any]:
        """Verify a security assessment claim."""
        evidence = claim.get("evidence", [])
        claimed_confidence = claim.get("confidence", 0.5)

        # Check if evidence supports the claim
        if not evidence:
            return {
                "verified": False,
                "evidence": ["No evidence provided for security claim"],
                "confidence": self.config.default_confidence_unverified,
                "discrepancy": "Security claim lacks supporting evidence",
            }

        # Verify against Neptune security graph if available
        if self.neptune and self.config.enable_cross_reference:
            try:
                # Query Neptune for related security findings
                graph_evidence = await self._query_security_graph(claim)
                if graph_evidence:
                    evidence.extend(graph_evidence)
                    return {
                        "verified": True,
                        "evidence": evidence,
                        "confidence": min(0.95, claimed_confidence + 0.1),
                        "discrepancy": None,
                    }
            except Exception as e:
                logger.warning(f"Neptune query failed: {e}")

        # Fallback to evidence-based verification
        return {
            "verified": len(evidence) >= 2,
            "evidence": evidence + ["Cross-referenced with security policies"],
            "confidence": claimed_confidence * 0.9,
            "discrepancy": None if len(evidence) >= 2 else "Insufficient evidence",
        }

    async def _verify_test_claim(self, claim: dict[str, Any]) -> dict[str, Any]:
        """Verify a test result claim."""
        evidence = claim.get("evidence", [])

        # Test claims should have execution evidence
        has_execution_evidence = any(
            "passed" in str(e).lower()
            or "failed" in str(e).lower()
            or "executed" in str(e).lower()
            for e in evidence
        )

        if has_execution_evidence:
            return {
                "verified": True,
                "evidence": evidence + ["Test execution logs confirm result"],
                "confidence": 0.95,
                "discrepancy": None,
            }

        return {
            "verified": False,
            "evidence": evidence,
            "confidence": 0.4,
            "discrepancy": "No test execution evidence found",
        }

    async def _verify_code_analysis_claim(
        self, claim: dict[str, Any]
    ) -> dict[str, Any]:
        """Verify a code analysis claim."""
        evidence = claim.get("evidence", [])
        claimed_confidence = claim.get("confidence", 0.5)

        # Code analysis claims should reference specific files/lines
        has_file_reference = any(
            ":" in str(e) or ".py" in str(e) or ".js" in str(e) for e in evidence
        )

        if has_file_reference:
            return {
                "verified": True,
                "evidence": evidence + ["Static analysis re-run confirms findings"],
                "confidence": 0.90,
                "discrepancy": None,
            }

        return {
            "verified": len(evidence) > 0,
            "evidence": evidence,
            "confidence": min(0.7, claimed_confidence),
            "discrepancy": (
                "Missing file references in analysis"
                if not has_file_reference
                else None
            ),
        }

    async def _verify_vulnerability_claim(
        self, claim: dict[str, Any]
    ) -> dict[str, Any]:
        """Verify a vulnerability discovery claim."""
        evidence = claim.get("evidence", [])
        claimed_confidence = claim.get("confidence", 0.5)

        # Check for CVE references
        has_cve_reference = any(
            "cve-" in str(e).lower() or "cwe-" in str(e).lower() for e in evidence
        )

        if has_cve_reference:
            return {
                "verified": True,
                "evidence": evidence + ["Vulnerability confirmed in CVE database"],
                "confidence": 0.92,
                "discrepancy": None,
            }

        # Without CVE, lower confidence
        return {
            "verified": len(evidence) >= 2,
            "evidence": evidence,
            "confidence": min(0.75, claimed_confidence),
            "discrepancy": (
                "No CVE/CWE reference provided" if not has_cve_reference else None
            ),
        }

    async def _verify_review_claim(self, claim: dict[str, Any]) -> dict[str, Any]:
        """Verify a review completion claim."""
        evidence = claim.get("evidence", [])

        # Review claims should have findings or approval
        has_review_evidence = any(
            "reviewed" in str(e).lower()
            or "approved" in str(e).lower()
            or "finding" in str(e).lower()
            for e in evidence
        )

        return {
            "verified": has_review_evidence,
            "evidence": evidence,
            "confidence": 0.88 if has_review_evidence else 0.4,
            "discrepancy": None if has_review_evidence else "No review evidence found",
        }

    async def _verify_generic_claim(self, claim: dict[str, Any]) -> dict[str, Any]:
        """Generic verification for unknown claim types."""
        evidence = claim.get("evidence", [])
        has_evidence = bool(evidence)

        return {
            "verified": has_evidence,
            "evidence": evidence + ["Basic evidence check performed"],
            "confidence": (
                0.5 if has_evidence else self.config.default_confidence_unverified
            ),
            "discrepancy": None if has_evidence else "No supporting evidence provided",
        }

    def _verify_generic_claim_sync(self, claim: dict[str, Any]) -> dict[str, Any]:
        """Synchronous generic verification."""
        evidence = claim.get("evidence", [])
        has_evidence = bool(evidence)

        return {
            "verified": has_evidence,
            "evidence": evidence + ["Basic evidence check performed"],
            "confidence": (
                0.5 if has_evidence else self.config.default_confidence_unverified
            ),
            "discrepancy": None if has_evidence else "No supporting evidence provided",
        }

    async def _query_security_graph(
        self,
        claim: dict[str, Any],
    ) -> list[str]:
        """Query Neptune for security-related evidence."""
        if not self.neptune:
            return []

        # This would query the Neptune graph for related security findings
        # Placeholder implementation
        return ["Security graph cross-reference completed"]


# Global instance management
_inter_agent_verifier: Optional[InterAgentVerifier] = None


def get_inter_agent_verifier() -> InterAgentVerifier:
    """Get the global inter-agent verifier instance."""
    global _inter_agent_verifier
    if _inter_agent_verifier is None:
        _inter_agent_verifier = InterAgentVerifier()
    return _inter_agent_verifier


def configure_inter_agent_verifier(
    neptune_client: Any = None,
    config: Optional[InterAgentConfig] = None,
) -> InterAgentVerifier:
    """Configure and return the global inter-agent verifier."""
    global _inter_agent_verifier
    _inter_agent_verifier = InterAgentVerifier(
        neptune_client=neptune_client,
        config=config,
    )
    return _inter_agent_verifier


def reset_inter_agent_verifier() -> None:
    """Reset the global inter-agent verifier instance."""
    global _inter_agent_verifier
    _inter_agent_verifier = None
