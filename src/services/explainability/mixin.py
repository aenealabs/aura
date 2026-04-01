"""
Project Aura - Explainability Mixin

Provides a mixin class for agents to easily integrate
explainability capabilities into their decision-making.

Author: Project Aura Team
Created: 2026-01-25
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .contracts import DecisionSeverity, ExplainabilityRecord
from .service import UniversalExplainabilityService, get_explainability_service

logger = logging.getLogger(__name__)


class ExplainabilityMixin:
    """
    Mixin for agents to add explainability capabilities.

    Usage:
        class MyAgent(ExplainabilityMixin):
            def __init__(self):
                self.agent_id = "my_agent"

            def process(self, input_data):
                # Start explaining the decision
                self.start_explanation(
                    decision_input=input_data,
                    severity=DecisionSeverity.NORMAL
                )

                # ... agent logic ...
                output = self._make_decision(input_data)

                # Complete explanation
                record = self.complete_explanation_sync(
                    decision_output=output
                )

                return output, record
    """

    # These should be set by the implementing class
    agent_id: str = "unknown_agent"
    _current_decision_id: Optional[str] = None
    _current_decision_input: Optional[dict[str, Any]] = None
    _current_severity: Optional[DecisionSeverity] = None
    _current_context: Optional[dict[str, Any]] = None
    _current_upstream_claims: Optional[list[dict[str, Any]]] = None
    _explainability_service: Optional[UniversalExplainabilityService] = None

    def get_explainability_service(self) -> UniversalExplainabilityService:
        """Get or create the explainability service instance."""
        if self._explainability_service is None:
            self._explainability_service = get_explainability_service()
        return self._explainability_service

    def set_explainability_service(
        self,
        service: UniversalExplainabilityService,
    ) -> None:
        """Set a custom explainability service instance."""
        self._explainability_service = service

    def start_explanation(
        self,
        decision_input: dict[str, Any],
        severity: DecisionSeverity = DecisionSeverity.NORMAL,
        decision_id: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
        upstream_claims: Optional[list[dict[str, Any]]] = None,
    ) -> str:
        """
        Start tracking a decision for explanation.

        Args:
            decision_input: Input data for the decision
            severity: Decision severity level
            decision_id: Optional explicit decision ID
            context: Optional context for the decision
            upstream_claims: Optional claims from upstream agents

        Returns:
            The decision ID being tracked
        """
        import uuid

        self._current_decision_id = decision_id or f"dec_{uuid.uuid4().hex[:12]}"
        self._current_decision_input = decision_input
        self._current_severity = severity
        self._current_context = context
        self._current_upstream_claims = upstream_claims

        logger.debug(
            f"Started explanation tracking for decision {self._current_decision_id} "
            f"(severity: {severity.value})"
        )

        return self._current_decision_id

    async def complete_explanation(
        self,
        decision_output: dict[str, Any],
        additional_context: Optional[dict[str, Any]] = None,
    ) -> ExplainabilityRecord:
        """
        Complete the explanation for the current decision.

        Args:
            decision_output: Output/result of the decision
            additional_context: Additional context to merge

        Returns:
            ExplainabilityRecord with full explanation

        Raises:
            ValueError: If no decision is being tracked
        """
        if self._current_decision_id is None:
            raise ValueError("No decision being tracked. Call start_explanation first.")

        # Merge context if provided
        context = self._current_context or {}
        if additional_context:
            context.update(additional_context)

        service = self.get_explainability_service()
        record = await service.explain_decision(
            decision_id=self._current_decision_id,
            agent_id=self.agent_id,
            severity=self._current_severity or DecisionSeverity.NORMAL,
            decision_input=self._current_decision_input or {},
            decision_output=decision_output,
            decision_context=context,
            upstream_claims=self._current_upstream_claims,
        )

        # Clear tracking state
        self._clear_tracking_state()

        logger.debug(
            f"Completed explanation for decision {record.decision_id}: "
            f"score={record.explainability_score.overall_score() if record.explainability_score else 'N/A'}"
        )

        return record

    def complete_explanation_sync(
        self,
        decision_output: dict[str, Any],
        additional_context: Optional[dict[str, Any]] = None,
    ) -> ExplainabilityRecord:
        """
        Synchronous version of complete_explanation.

        Args:
            decision_output: Output/result of the decision
            additional_context: Additional context to merge

        Returns:
            ExplainabilityRecord with full explanation

        Raises:
            ValueError: If no decision is being tracked
        """
        if self._current_decision_id is None:
            raise ValueError("No decision being tracked. Call start_explanation first.")

        # Merge context if provided
        context = self._current_context or {}
        if additional_context:
            context.update(additional_context)

        service = self.get_explainability_service()
        record = service.explain_decision_sync(
            decision_id=self._current_decision_id,
            agent_id=self.agent_id,
            severity=self._current_severity or DecisionSeverity.NORMAL,
            decision_input=self._current_decision_input or {},
            decision_output=decision_output,
            decision_context=context,
            upstream_claims=self._current_upstream_claims,
        )

        # Clear tracking state
        self._clear_tracking_state()

        logger.debug(
            f"Completed explanation for decision {record.decision_id}: "
            f"score={record.explainability_score.overall_score() if record.explainability_score else 'N/A'}"
        )

        return record

    def _clear_tracking_state(self) -> None:
        """Clear the current decision tracking state."""
        self._current_decision_id = None
        self._current_decision_input = None
        self._current_severity = None
        self._current_context = None
        self._current_upstream_claims = None

    def add_upstream_claim(
        self,
        agent_id: str,
        claim_type: str,
        claim_text: str,
        evidence: Optional[list[str]] = None,
        confidence: float = 0.5,
    ) -> None:
        """
        Add a claim from an upstream agent to be verified.

        Args:
            agent_id: ID of the agent making the claim
            claim_type: Type of claim (e.g., "security_assessment")
            claim_text: The claim being made
            evidence: Supporting evidence
            confidence: Claimed confidence level
        """
        if self._current_upstream_claims is None:
            self._current_upstream_claims = []

        self._current_upstream_claims.append(
            {
                "agent_id": agent_id,
                "claim_type": claim_type,
                "claim_text": claim_text,
                "evidence": evidence or [],
                "confidence": confidence,
            }
        )

        logger.debug(f"Added upstream claim from {agent_id}: {claim_type}")

    def add_context(
        self,
        key: str,
        value: Any,
    ) -> None:
        """
        Add context information for the current decision.

        Args:
            key: Context key
            value: Context value
        """
        if self._current_context is None:
            self._current_context = {}
        self._current_context[key] = value

    async def explain_standalone(
        self,
        decision_id: str,
        decision_input: dict[str, Any],
        decision_output: dict[str, Any],
        severity: DecisionSeverity = DecisionSeverity.NORMAL,
        context: Optional[dict[str, Any]] = None,
        upstream_claims: Optional[list[dict[str, Any]]] = None,
    ) -> ExplainabilityRecord:
        """
        Generate explanation for a standalone decision.

        This method doesn't require start_explanation to be called first.

        Args:
            decision_id: Unique decision identifier
            decision_input: Input data for the decision
            decision_output: Output/result of the decision
            severity: Decision severity level
            context: Optional context for the decision
            upstream_claims: Optional claims from upstream agents

        Returns:
            ExplainabilityRecord with full explanation
        """
        service = self.get_explainability_service()
        return await service.explain_decision(
            decision_id=decision_id,
            agent_id=self.agent_id,
            severity=severity,
            decision_input=decision_input,
            decision_output=decision_output,
            decision_context=context,
            upstream_claims=upstream_claims,
        )

    def explain_standalone_sync(
        self,
        decision_id: str,
        decision_input: dict[str, Any],
        decision_output: dict[str, Any],
        severity: DecisionSeverity = DecisionSeverity.NORMAL,
        context: Optional[dict[str, Any]] = None,
        upstream_claims: Optional[list[dict[str, Any]]] = None,
    ) -> ExplainabilityRecord:
        """
        Synchronous version of explain_standalone.

        Args:
            decision_id: Unique decision identifier
            decision_input: Input data for the decision
            decision_output: Output/result of the decision
            severity: Decision severity level
            context: Optional context for the decision
            upstream_claims: Optional claims from upstream agents

        Returns:
            ExplainabilityRecord with full explanation
        """
        service = self.get_explainability_service()
        return service.explain_decision_sync(
            decision_id=decision_id,
            agent_id=self.agent_id,
            severity=severity,
            decision_input=decision_input,
            decision_output=decision_output,
            decision_context=context,
            upstream_claims=upstream_claims,
        )

    def requires_hitl(self, record: ExplainabilityRecord) -> bool:
        """
        Check if a decision requires human-in-the-loop review.

        Args:
            record: The explainability record to check

        Returns:
            True if HITL is required
        """
        return record.hitl_required

    def get_explanation_summary(self, record: ExplainabilityRecord) -> str:
        """
        Get a human-readable summary of the explanation.

        Args:
            record: The explainability record

        Returns:
            Summary string
        """
        return record.human_readable_summary or "No summary available"
