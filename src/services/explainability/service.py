"""
Project Aura - Universal Explainability Service

Main orchestration service for the Universal Explainability Framework.
Coordinates all explainability components to generate complete
decision explanation records.

Author: Project Aura Team
Created: 2026-01-25
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Optional

from .alternatives import AlternativesAnalyzer
from .confidence import ConfidenceQuantifier
from .config import ExplainabilityConfig
from .consistency import ConsistencyVerifier
from .contracts import (
    AlternativesReport,
    ConfidenceInterval,
    ConsistencyReport,
    DecisionSeverity,
    ExplainabilityRecord,
    ExplainabilityScore,
    ReasoningChain,
    VerificationReport,
)
from .inter_agent import InterAgentVerifier
from .reasoning_chain import ReasoningChainBuilder

logger = logging.getLogger(__name__)


class UniversalExplainabilityService:
    """
    Orchestrates universal explainability for all agent decisions.

    Ensures every decision has:
    - Complete reasoning chains
    - Alternatives considered
    - Quantified confidence
    - Consistency verification
    - Inter-agent claim verification
    """

    def __init__(
        self,
        decision_audit_logger: Any = None,
        constitutional_critique_service: Any = None,
        bedrock_client: Any = None,
        neptune_client: Any = None,
        dynamodb_client: Any = None,
        config: Optional[ExplainabilityConfig] = None,
    ):
        """
        Initialize the Universal Explainability Service.

        Args:
            decision_audit_logger: Logger for decision audits
            constitutional_critique_service: Constitutional AI critique service
            bedrock_client: AWS Bedrock client for LLM operations
            neptune_client: AWS Neptune client for graph queries
            dynamodb_client: AWS DynamoDB client for persistence
            config: Configuration for explainability service
        """
        self.config = config or ExplainabilityConfig()
        self.audit_logger = decision_audit_logger
        self.constitutional_service = constitutional_critique_service
        self.bedrock = bedrock_client
        self.neptune = neptune_client
        self.dynamodb = dynamodb_client

        # Initialize components
        self.reasoning_builder = ReasoningChainBuilder(bedrock_client)
        self.alternatives_analyzer = AlternativesAnalyzer(bedrock_client)
        self.confidence_quantifier = ConfidenceQuantifier()
        self.consistency_verifier = ConsistencyVerifier(bedrock_client)
        self.inter_agent_verifier = InterAgentVerifier(neptune_client)

        logger.info("UniversalExplainabilityService initialized")

    async def explain_decision(
        self,
        decision_id: str,
        agent_id: str,
        severity: DecisionSeverity,
        decision_input: dict[str, Any],
        decision_output: dict[str, Any],
        decision_context: Optional[dict[str, Any]] = None,
        upstream_claims: Optional[list[dict[str, Any]]] = None,
    ) -> ExplainabilityRecord:
        """
        Generate complete explainability record for a decision.

        Args:
            decision_id: Unique identifier for the decision
            agent_id: The agent that made the decision
            severity: Severity level determining requirements
            decision_input: Input data for the decision
            decision_output: Output/result of the decision
            decision_context: Additional context (conversation, prior decisions)
            upstream_claims: Claims from upstream agents to verify

        Returns:
            ExplainabilityRecord with all explainability components
        """
        start_time = time.monotonic()
        record_id = f"exp_{uuid.uuid4().hex[:12]}"

        logger.info(
            f"Generating explainability record {record_id} for decision {decision_id}"
        )

        # Layer 1: Build reasoning chain
        reasoning_chain = await self.reasoning_builder.build(
            decision_id=decision_id,
            agent_id=agent_id,
            decision_input=decision_input,
            decision_output=decision_output,
            min_steps=self.config.get_min_reasoning_steps(severity.value),
            context=decision_context,
        )

        # Layer 2: Analyze alternatives
        alternatives_report = await self.alternatives_analyzer.analyze(
            decision_id=decision_id,
            decision_input=decision_input,
            decision_output=decision_output,
            context=decision_context,
            min_alternatives=self.config.get_min_alternatives(severity.value),
        )

        # Layer 3: Quantify confidence
        confidence_interval = await self.confidence_quantifier.quantify(
            reasoning_chain=reasoning_chain,
            alternatives_report=alternatives_report,
            decision_context=decision_context,
        )

        # Layer 4: Verify consistency
        consistency_report = await self.consistency_verifier.verify(
            decision_id=decision_id,
            reasoning_chain=reasoning_chain,
            decision_output=decision_output,
        )

        # Layer 5: Inter-agent verification (if upstream claims provided)
        verification_report = None
        if upstream_claims and self.config.enable_inter_agent_verification:
            verification_report = await self.inter_agent_verifier.verify_claims(
                decision_id=decision_id,
                claims=upstream_claims,
            )

        # Calculate explainability score
        explainability_score = self._calculate_score(
            reasoning_chain=reasoning_chain,
            alternatives_report=alternatives_report,
            confidence_interval=confidence_interval,
            consistency_report=consistency_report,
            verification_report=verification_report,
            severity=severity,
        )

        # Generate human-readable summary
        human_summary = self._generate_summary(
            reasoning_chain=reasoning_chain,
            alternatives_report=alternatives_report,
            confidence_interval=confidence_interval,
        )

        # Determine if HITL required
        hitl_required, hitl_reason = self._check_hitl_required(
            consistency_report=consistency_report,
            confidence_interval=confidence_interval,
            explainability_score=explainability_score,
        )

        # Create record
        record = ExplainabilityRecord(
            record_id=record_id,
            decision_id=decision_id,
            agent_id=agent_id,
            severity=severity,
            reasoning_chain=reasoning_chain,
            alternatives_report=alternatives_report,
            confidence_interval=confidence_interval,
            consistency_report=consistency_report,
            verification_report=verification_report,
            explainability_score=explainability_score,
            human_readable_summary=human_summary,
            hitl_required=hitl_required,
            hitl_reason=hitl_reason,
        )

        # Constitutional critique for reasoning quality (if enabled)
        if self.config.enable_constitutional_critique and self.constitutional_service:
            critique_result = await self._constitutional_critique(record)
            record.constitutional_critique_id = critique_result.get("critique_id")

        # Persist record
        if self.dynamodb and self.config.async_persistence:
            await self._persist_record(record)

        processing_time_ms = (time.monotonic() - start_time) * 1000
        logger.info(
            f"Explainability record {record_id} generated in {processing_time_ms:.1f}ms, "
            f"score={explainability_score.overall_score():.2f}, hitl_required={hitl_required}"
        )

        return record

    def explain_decision_sync(
        self,
        decision_id: str,
        agent_id: str,
        severity: DecisionSeverity,
        decision_input: dict[str, Any],
        decision_output: dict[str, Any],
        decision_context: Optional[dict[str, Any]] = None,
        upstream_claims: Optional[list[dict[str, Any]]] = None,
    ) -> ExplainabilityRecord:
        """
        Synchronous version of explain_decision.

        Args:
            decision_id: Unique identifier for the decision
            agent_id: The agent that made the decision
            severity: Severity level determining requirements
            decision_input: Input data for the decision
            decision_output: Output/result of the decision
            decision_context: Additional context
            upstream_claims: Claims from upstream agents to verify

        Returns:
            ExplainabilityRecord with all explainability components
        """
        record_id = f"exp_{uuid.uuid4().hex[:12]}"

        # Build reasoning chain
        reasoning_chain = self.reasoning_builder.build_sync(
            decision_id=decision_id,
            agent_id=agent_id,
            decision_input=decision_input,
            decision_output=decision_output,
            min_steps=self.config.get_min_reasoning_steps(severity.value),
        )

        # Analyze alternatives
        alternatives_report = self.alternatives_analyzer.analyze_sync(
            decision_id=decision_id,
            decision_input=decision_input,
            decision_output=decision_output,
            min_alternatives=self.config.get_min_alternatives(severity.value),
        )

        # Quantify confidence
        confidence_interval = self.confidence_quantifier.quantify_sync(
            reasoning_chain=reasoning_chain,
            alternatives_report=alternatives_report,
            decision_context=decision_context,
        )

        # Verify consistency
        consistency_report = self.consistency_verifier.verify_sync(
            decision_id=decision_id,
            reasoning_chain=reasoning_chain,
            decision_output=decision_output,
        )

        # Inter-agent verification
        verification_report = None
        if upstream_claims and self.config.enable_inter_agent_verification:
            verification_report = self.inter_agent_verifier.verify_claims_sync(
                decision_id=decision_id,
                claims=upstream_claims,
            )

        # Calculate score
        explainability_score = self._calculate_score(
            reasoning_chain=reasoning_chain,
            alternatives_report=alternatives_report,
            confidence_interval=confidence_interval,
            consistency_report=consistency_report,
            verification_report=verification_report,
            severity=severity,
        )

        # Generate summary
        human_summary = self._generate_summary(
            reasoning_chain=reasoning_chain,
            alternatives_report=alternatives_report,
            confidence_interval=confidence_interval,
        )

        # Check HITL
        hitl_required, hitl_reason = self._check_hitl_required(
            consistency_report=consistency_report,
            confidence_interval=confidence_interval,
            explainability_score=explainability_score,
        )

        return ExplainabilityRecord(
            record_id=record_id,
            decision_id=decision_id,
            agent_id=agent_id,
            severity=severity,
            reasoning_chain=reasoning_chain,
            alternatives_report=alternatives_report,
            confidence_interval=confidence_interval,
            consistency_report=consistency_report,
            verification_report=verification_report,
            explainability_score=explainability_score,
            human_readable_summary=human_summary,
            hitl_required=hitl_required,
            hitl_reason=hitl_reason,
        )

    def _calculate_score(
        self,
        reasoning_chain: ReasoningChain,
        alternatives_report: AlternativesReport,
        confidence_interval: ConfidenceInterval,
        consistency_report: ConsistencyReport,
        verification_report: Optional[VerificationReport],
        severity: DecisionSeverity,
    ) -> ExplainabilityScore:
        """Calculate composite explainability score."""
        # Reasoning completeness: ratio of actual to required steps
        min_steps = self.config.get_min_reasoning_steps(severity.value)
        reasoning_completeness = min(
            1.0, len(reasoning_chain.steps) / max(1, min_steps)
        )

        # Alternatives coverage: ratio of actual to required alternatives
        min_alts = self.config.get_min_alternatives(severity.value)
        alternatives_coverage = min(
            1.0, len(alternatives_report.alternatives) / max(1, min_alts)
        )

        # Confidence calibration: based on interval properties
        confidence_calibration = (
            1.0 if confidence_interval.is_well_calibrated() else 0.7
        )

        # Consistency score: from verification
        consistency_score = consistency_report.consistency_score

        # Inter-agent trust: from verification or default
        inter_agent_trust = (
            verification_report.overall_trust_score() if verification_report else 1.0
        )

        return ExplainabilityScore(
            reasoning_completeness=round(reasoning_completeness, 4),
            alternatives_coverage=round(alternatives_coverage, 4),
            confidence_calibration=round(confidence_calibration, 4),
            consistency_score=round(consistency_score, 4),
            inter_agent_trust=round(inter_agent_trust, 4),
        )

    def _generate_summary(
        self,
        reasoning_chain: ReasoningChain,
        alternatives_report: AlternativesReport,
        confidence_interval: ConfidenceInterval,
    ) -> str:
        """Generate human-readable summary of decision explanation."""
        # Format reasoning steps
        steps_text = "\n".join(
            f"  {i + 1}. {step.description}"
            for i, step in enumerate(reasoning_chain.steps[:5])
        )

        # Format chosen alternative
        chosen = alternatives_report.get_chosen()
        chosen_text = chosen.description if chosen else "Not specified"

        # Format rejected alternatives
        rejected = alternatives_report.get_rejected()
        rejected_text = "\n".join(
            f"  - {a.description}: {a.rejection_reason or 'Not selected'}"
            for a in rejected[:3]
        )

        # Format uncertainty sources
        uncertainty_text = "\n".join(
            f"  - {source}" for source in confidence_interval.uncertainty_sources[:3]
        )

        summary = f"""DECISION EXPLANATION

REASONING:
{steps_text}

CHOSEN APPROACH: {chosen_text}

ALTERNATIVES CONSIDERED:
{rejected_text}

CONFIDENCE: {confidence_interval.point_estimate:.0%} ({confidence_interval.lower_bound:.0%} - {confidence_interval.upper_bound:.0%})

UNCERTAINTY FACTORS:
{uncertainty_text}
"""
        return summary.strip()

    def _check_hitl_required(
        self,
        consistency_report: ConsistencyReport,
        confidence_interval: ConfidenceInterval,
        explainability_score: ExplainabilityScore,
    ) -> tuple[bool, Optional[str]]:
        """Determine if HITL escalation is required."""
        # Check for critical contradictions
        if (
            self.config.escalate_on_contradiction
            and consistency_report.has_critical_contradictions()
        ):
            return True, "Critical contradiction detected between reasoning and action"

        # Check for low confidence
        if (
            self.config.escalate_on_low_confidence
            and confidence_interval.point_estimate
            < self.config.low_confidence_threshold
        ):
            return (
                True,
                f"Low confidence ({confidence_interval.point_estimate:.0%}) "
                f"below threshold ({self.config.low_confidence_threshold:.0%})",
            )

        # Check for low explainability score
        if (
            self.config.escalate_on_low_score
            and explainability_score.overall_score() < self.config.low_score_threshold
        ):
            return (
                True,
                f"Low explainability score ({explainability_score.overall_score():.2f})",
            )

        return False, None

    async def _constitutional_critique(
        self,
        record: ExplainabilityRecord,
    ) -> dict[str, Any]:
        """Apply constitutional critique to reasoning quality."""
        if not self.constitutional_service:
            return {"critique_id": None}

        try:
            critique_input = {
                "reasoning_chain": (
                    record.reasoning_chain.to_dict() if record.reasoning_chain else {}
                ),
                "alternatives_report": (
                    record.alternatives_report.to_dict()
                    if record.alternatives_report
                    else {}
                ),
                "consistency_report": (
                    record.consistency_report.to_dict()
                    if record.consistency_report
                    else {}
                ),
            }

            result = await self.constitutional_service.critique_output(
                agent_output=str(critique_input),
                context={"record_id": record.record_id},
                applicable_principles=[
                    "REASONING_COMPLETENESS",
                    "ALTERNATIVES_DISCLOSURE",
                    "CONFIDENCE_HONESTY",
                    "ACTION_REASONING_CONSISTENCY",
                ],
            )

            return {"critique_id": getattr(result, "critique_id", None)}
        except Exception as e:
            logger.warning(f"Constitutional critique failed: {e}")
            return {"critique_id": None}

    async def _persist_record(self, record: ExplainabilityRecord) -> None:
        """Persist explainability record to DynamoDB."""
        if not self.dynamodb:
            return

        try:
            await self.dynamodb.put_item(
                TableName=self.config.dynamodb_table_name,
                Item={
                    "record_id": {"S": record.record_id},
                    "decision_id": {"S": record.decision_id},
                    "agent_id": {"S": record.agent_id},
                    "timestamp": {"S": record.timestamp.isoformat()},
                    "severity": {"S": record.severity.value},
                    "explainability_score": {
                        "N": str(record.explainability_score.overall_score())
                    },
                    "hitl_required": {"BOOL": record.hitl_required},
                    "data": {"S": str(record.to_dict())},
                },
            )
            logger.debug(f"Persisted explainability record {record.record_id}")
        except Exception as e:
            logger.error(f"Failed to persist explainability record: {e}")


# Global instance management
_explainability_service: Optional[UniversalExplainabilityService] = None


def get_explainability_service() -> UniversalExplainabilityService:
    """Get the global explainability service instance."""
    global _explainability_service
    if _explainability_service is None:
        _explainability_service = UniversalExplainabilityService()
    return _explainability_service


def configure_explainability_service(
    decision_audit_logger: Any = None,
    constitutional_critique_service: Any = None,
    bedrock_client: Any = None,
    neptune_client: Any = None,
    dynamodb_client: Any = None,
    config: Optional[ExplainabilityConfig] = None,
) -> UniversalExplainabilityService:
    """Configure and return the global explainability service."""
    global _explainability_service
    _explainability_service = UniversalExplainabilityService(
        decision_audit_logger=decision_audit_logger,
        constitutional_critique_service=constitutional_critique_service,
        bedrock_client=bedrock_client,
        neptune_client=neptune_client,
        dynamodb_client=dynamodb_client,
        config=config,
    )
    return _explainability_service


def reset_explainability_service() -> None:
    """Reset the global explainability service instance."""
    global _explainability_service
    _explainability_service = None
