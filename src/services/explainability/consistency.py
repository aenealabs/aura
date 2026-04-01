"""
Project Aura - Consistency Verifier

Verifies consistency between stated reasoning and actual actions.
Detects contradictions where agents claim to do X but actually do Y.

Author: Project Aura Team
Created: 2026-01-25
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Optional

from .config import ConsistencyConfig
from .contracts import ConsistencyReport, ContradictionSeverity, ReasoningChain

logger = logging.getLogger(__name__)


class ConsistencyVerifier:
    """
    Verify consistency between stated reasoning and actual actions.

    Detects contradictions where:
    - Agent claims to do X but actually does Y
    - Reasoning steps are missing or illogical
    - Evidence doesn't support conclusions
    """

    def __init__(
        self,
        bedrock_client: Any = None,
        config: Optional[ConsistencyConfig] = None,
    ):
        """
        Initialize the consistency verifier.

        Args:
            bedrock_client: AWS Bedrock client for LLM verification
            config: Configuration for consistency verification
        """
        self.bedrock = bedrock_client
        self.config = config or ConsistencyConfig()
        logger.info("ConsistencyVerifier initialized")

    async def verify(
        self,
        decision_id: str,
        reasoning_chain: ReasoningChain,
        decision_output: dict[str, Any],
    ) -> ConsistencyReport:
        """
        Verify that reasoning chain is consistent with decision output.

        Args:
            decision_id: Decision being verified
            reasoning_chain: The stated reasoning
            decision_output: The actual output/action taken

        Returns:
            ConsistencyReport with any detected contradictions
        """
        logger.debug(f"Verifying consistency for decision {decision_id}")

        report = ConsistencyReport(
            decision_id=decision_id,
            is_consistent=True,
        )

        # Extract claims from reasoning chain
        claims = self._extract_claims(reasoning_chain)

        # Extract actions from decision output
        actions = self._extract_actions(decision_output)

        # Check each claim against actions
        for claim in claims[: self.config.max_claims_per_verification]:
            if self.config.enable_llm_verification and self.bedrock:
                verification = await self._verify_claim_with_llm(
                    claim, actions, decision_output
                )
            else:
                verification = self._verify_claim_heuristic(
                    claim, actions, decision_output
                )

            if not verification["is_consistent"]:
                severity = self._assess_severity(verification)
                report.add_contradiction(
                    contradiction_id=f"ctr_{uuid.uuid4().hex[:8]}",
                    severity=severity,
                    stated_claim=claim["text"],
                    actual_action=verification.get("actual_action", "Unknown"),
                    explanation=verification.get(
                        "explanation", "Inconsistency detected"
                    ),
                    evidence=verification.get("evidence", []),
                )

        logger.debug(
            f"Consistency verification complete: "
            f"consistent={report.is_consistent}, "
            f"contradictions={len(report.contradictions)}"
        )
        return report

    def verify_sync(
        self,
        decision_id: str,
        reasoning_chain: ReasoningChain,
        decision_output: dict[str, Any],
    ) -> ConsistencyReport:
        """
        Synchronous version using heuristic verification.

        Args:
            decision_id: Decision being verified
            reasoning_chain: The stated reasoning
            decision_output: The actual output/action taken

        Returns:
            ConsistencyReport with any detected contradictions
        """
        report = ConsistencyReport(
            decision_id=decision_id,
            is_consistent=True,
        )

        claims = self._extract_claims(reasoning_chain)
        actions = self._extract_actions(decision_output)

        for claim in claims[: self.config.max_claims_per_verification]:
            verification = self._verify_claim_heuristic(claim, actions, decision_output)

            if not verification["is_consistent"]:
                severity = self._assess_severity(verification)
                report.add_contradiction(
                    contradiction_id=f"ctr_{uuid.uuid4().hex[:8]}",
                    severity=severity,
                    stated_claim=claim["text"],
                    actual_action=verification.get("actual_action", "Unknown"),
                    explanation=verification.get(
                        "explanation", "Inconsistency detected"
                    ),
                    evidence=verification.get("evidence", []),
                )

        return report

    def _extract_claims(self, reasoning_chain: ReasoningChain) -> list[dict[str, Any]]:
        """Extract verifiable claims from reasoning chain."""
        claims = []
        for step in reasoning_chain.steps:
            claims.append(
                {
                    "step_number": step.step_number,
                    "text": step.description,
                    "evidence": step.evidence,
                    "confidence": step.confidence,
                }
            )
        return claims

    def _extract_actions(self, decision_output: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract actions from decision output for verification."""
        actions = []

        # Handle common output formats
        if "action" in decision_output:
            actions.append({"type": "action", "value": str(decision_output["action"])})
        if "code_changes" in decision_output:
            actions.append(
                {
                    "type": "code_change",
                    "value": str(decision_output["code_changes"]),
                }
            )
        if "recommendation" in decision_output:
            actions.append(
                {
                    "type": "recommendation",
                    "value": str(decision_output["recommendation"]),
                }
            )
        if "result" in decision_output:
            actions.append({"type": "result", "value": str(decision_output["result"])})
        if "files" in decision_output or "files_modified" in decision_output:
            files = decision_output.get("files") or decision_output.get(
                "files_modified"
            )
            actions.append({"type": "file_modification", "value": str(files)})

        return actions

    async def _verify_claim_with_llm(
        self,
        claim: dict[str, Any],
        actions: list[dict[str, Any]],
        decision_output: dict[str, Any],
    ) -> dict[str, Any]:
        """Verify a single claim against actions using LLM analysis."""
        prompt = f"""Analyze whether the following claim is consistent with the action taken.

CLAIM: {claim['text']}
EVIDENCE PROVIDED: {claim['evidence']}

ACTIONS TAKEN: {json.dumps(actions, default=str)}

FULL OUTPUT: {json.dumps(decision_output, default=str)[:1500]}

Determine if the claim is consistent with the actions. Consider:
1. Does the action match what the claim says would happen?
2. Is there any contradiction between stated reasoning and actual behavior?
3. Are there missing steps that should have been taken based on the reasoning?

Respond in JSON format:
{{
    "is_consistent": true/false,
    "actual_action": "what was actually done",
    "explanation": "detailed explanation of consistency or contradiction",
    "evidence": ["specific evidence points"],
    "severity": "none/minor/moderate/major/critical"
}}
"""

        try:
            response = await self._call_bedrock(prompt)
            return response
        except Exception as e:
            logger.warning(f"LLM verification failed: {e}, using heuristic")
            return self._verify_claim_heuristic(claim, actions, decision_output)

    def _verify_claim_heuristic(
        self,
        claim: dict[str, Any],
        actions: list[dict[str, Any]],
        decision_output: dict[str, Any],
    ) -> dict[str, Any]:
        """Verify a claim using heuristic rules."""
        claim_text = claim["text"].lower()
        action_texts = [a["value"].lower() for a in actions]
        output_text = str(decision_output).lower()

        # Check for keyword consistency
        inconsistencies = []

        # Security claim but no security action
        if "security" in claim_text or "secure" in claim_text:
            if not any("security" in a or "secure" in a for a in action_texts):
                inconsistencies.append("Security claimed but not evident in actions")

        # Test claim but no tests
        if "test" in claim_text and "test" not in output_text:
            if "test" not in " ".join(action_texts):
                inconsistencies.append("Tests claimed but not found in output")

        # Fix claim but no code changes
        if "fix" in claim_text or "patch" in claim_text:
            if not any("code" in a or "change" in a for a in action_texts):
                if "file" not in output_text and "modified" not in output_text:
                    inconsistencies.append("Fix claimed but no code changes detected")

        # Refactor claim consistency
        if "refactor" in claim_text:
            if "refactor" not in output_text and "restructure" not in output_text:
                # This might be okay if there are file changes
                if not any("file" in a for a in action_texts):
                    inconsistencies.append(
                        "Refactor claimed without structural changes"
                    )

        if inconsistencies:
            return {
                "is_consistent": False,
                "actual_action": (
                    actions[0]["value"] if actions else "No action detected"
                ),
                "explanation": "; ".join(inconsistencies),
                "evidence": inconsistencies,
                "severity": "moderate" if len(inconsistencies) == 1 else "major",
            }

        return {
            "is_consistent": True,
            "actual_action": actions[0]["value"] if actions else "Action taken",
            "explanation": "Claim appears consistent with actions",
            "evidence": ["Keyword consistency check passed"],
            "severity": "none",
        }

    def _assess_severity(self, verification: dict[str, Any]) -> ContradictionSeverity:
        """Map verification result to contradiction severity."""
        severity_str = verification.get("severity", "minor")
        severity_map = {
            "none": ContradictionSeverity.MINOR,
            "minor": ContradictionSeverity.MINOR,
            "moderate": ContradictionSeverity.MODERATE,
            "major": ContradictionSeverity.MAJOR,
            "critical": ContradictionSeverity.CRITICAL,
        }
        return severity_map.get(severity_str.lower(), ContradictionSeverity.MINOR)

    async def _call_bedrock(self, prompt: str) -> dict[str, Any]:
        """Call Bedrock for LLM verification."""
        if not self.bedrock:
            return {
                "is_consistent": True,
                "actual_action": "",
                "explanation": "No LLM verification available",
                "evidence": [],
                "severity": "none",
            }

        try:
            response = self.bedrock.invoke_model(
                modelId=self.config.verification_model,
                body=json.dumps(
                    {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 1000,
                        "temperature": self.config.verification_temperature,
                        "messages": [{"role": "user", "content": prompt}],
                    }
                ),
                contentType="application/json",
                accept="application/json",
            )

            response_body = json.loads(response["body"].read())
            content = response_body.get("content", [{}])[0].get("text", "{}")

            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())

            return {
                "is_consistent": True,
                "actual_action": "",
                "explanation": "Could not parse LLM response",
                "evidence": [],
                "severity": "none",
            }

        except Exception as e:
            logger.error(f"Bedrock call failed: {e}")
            return {
                "is_consistent": True,
                "actual_action": "",
                "explanation": f"Verification error: {e}",
                "evidence": [],
                "severity": "none",
            }


# Global instance management
_consistency_verifier: Optional[ConsistencyVerifier] = None


def get_consistency_verifier() -> ConsistencyVerifier:
    """Get the global consistency verifier instance."""
    global _consistency_verifier
    if _consistency_verifier is None:
        _consistency_verifier = ConsistencyVerifier()
    return _consistency_verifier


def configure_consistency_verifier(
    bedrock_client: Any = None,
    config: Optional[ConsistencyConfig] = None,
) -> ConsistencyVerifier:
    """Configure and return the global consistency verifier."""
    global _consistency_verifier
    _consistency_verifier = ConsistencyVerifier(
        bedrock_client=bedrock_client,
        config=config,
    )
    return _consistency_verifier


def reset_consistency_verifier() -> None:
    """Reset the global consistency verifier instance."""
    global _consistency_verifier
    _consistency_verifier = None
