"""Constitutional AI Mixin for Agent Integration.

This module provides the ConstitutionalMixin that adds constitutional oversight
to any agent. It integrates with the Phase 1 Constitutional AI services to
provide transparent critique and revision of agent outputs.

ADR-063 Phase 2 Implementation
ADR-063 Phase 3 Enhancements:
- Tiered critique strategy based on autonomy level
- SQS async audit queue for non-blocking persistence

Usage:
    >>> class MyAgent(ConstitutionalMixin, BaseAgent):
    ...     def __init__(self, llm_client):
    ...         super().__init__(llm_client=llm_client)
    ...         self._init_constitutional(llm_service=llm_client)
    ...
    ...     async def execute(self, task):
    ...         result = await self._do_work(task)
    ...         processed = await self.process_with_constitutional(
    ...             output=result,
    ...             context=ConstitutionalContext(agent_name="MyAgent", ...),
    ...         )
    ...         return processed.processed_output
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from src.services.bedrock_llm_service import BedrockLLMService
    from src.services.constitutional_ai.audit_queue_service import (
        ConstitutionalAuditQueueService,
    )
    from src.services.constitutional_ai.critique_service import (
        ConstitutionalCritiqueService,
    )
    from src.services.constitutional_ai.models import (
        ConstitutionalContext,
        ConstitutionalEvaluationSummary,
        CritiqueResult,
        RevisionResult,
    )
    from src.services.constitutional_ai.revision_service import (
        ConstitutionalRevisionService,
    )

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration Classes
# =============================================================================


@dataclass
class ConstitutionalMixinConfig:
    """Per-agent configuration for constitutional oversight.

    Attributes:
        domain_tags: Tags for filtering which principles apply to this agent.
        applicable_principles: Specific principle IDs to apply (None = all applicable).
        skip_for_autonomy_levels: Autonomy levels where constitutional processing is skipped.
        block_on_critical: Whether to block output when critical issues are unresolved.
        enable_hitl_escalation: Whether to escalate unresolved issues to HITL.
        max_revision_iterations: Override for max revision iterations (None = use service default).
        include_in_metrics: Whether to include constitutional metrics in agent metrics.
        mock_mode: Whether to use mock mode (for testing without LLM).
    """

    domain_tags: List[str] = field(default_factory=list)
    applicable_principles: Optional[List[str]] = None
    skip_for_autonomy_levels: List[str] = field(
        default_factory=lambda: ["FULL_AUTONOMOUS"]
    )
    block_on_critical: bool = True
    enable_hitl_escalation: bool = True
    max_revision_iterations: Optional[int] = None
    include_in_metrics: bool = True
    mock_mode: bool = False

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if (
            self.max_revision_iterations is not None
            and self.max_revision_iterations < 1
        ):
            raise ValueError("max_revision_iterations must be at least 1")


@dataclass
class ConstitutionalProcessingResult:
    """Result of constitutional processing of agent output.

    Contains both the processed output and metadata about the constitutional
    evaluation and revision that was applied.

    Attributes:
        original_output: The original output before processing.
        processed_output: The output after constitutional processing.
        was_revised: Whether the output was revised.
        critique_summary: Summary of the critique evaluation.
        revision_result: Result of the revision (if performed).
        hitl_required: Whether HITL escalation was triggered.
        hitl_request_id: ID of the HITL request (if created).
        blocked: Whether the output was blocked.
        block_reason: Reason for blocking (if blocked).
        processing_time_ms: Time taken for processing in milliseconds.
        skipped: Whether processing was skipped (e.g., due to autonomy level).
        skip_reason: Reason for skipping (if skipped).
    """

    original_output: Any
    processed_output: Any
    was_revised: bool = False
    critique_summary: Optional["ConstitutionalEvaluationSummary"] = None
    revision_result: Optional["RevisionResult"] = None
    hitl_required: bool = False
    hitl_request_id: Optional[str] = None
    blocked: bool = False
    block_reason: Optional[str] = None
    processing_time_ms: float = 0.0
    skipped: bool = False
    skip_reason: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "was_revised": self.was_revised,
            "hitl_required": self.hitl_required,
            "hitl_request_id": self.hitl_request_id,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            "processing_time_ms": self.processing_time_ms,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.critique_summary:
            result["critique_summary"] = {
                "total_principles_evaluated": self.critique_summary.total_principles_evaluated,
                "critical_issues": self.critique_summary.critical_issues,
                "high_issues": self.critique_summary.high_issues,
                "requires_revision": self.critique_summary.requires_revision,
                "requires_hitl": self.critique_summary.requires_hitl,
            }
        if self.revision_result:
            result["revision_result"] = {
                "was_modified": self.revision_result.was_modified,
                "revision_iterations": self.revision_result.revision_iterations,
                "converged": self.revision_result.converged,
                "critique_count": self.revision_result.critique_count,
            }
        return result


# =============================================================================
# Constitutional Mixin
# =============================================================================


class ConstitutionalMixin:
    """Mixin that adds constitutional oversight to agents.

    Provides methods for agents to apply constitutional critique and revision
    to their outputs. Uses composition for the underlying services.

    The mixin follows an explicit method pattern - agents call
    `process_with_constitutional()` on outputs they want to process,
    rather than implicitly wrapping all outputs.

    This works with both BaseAgent subclasses and standalone agents
    (like CoderAgent, ReviewerAgent) that don't inherit from BaseAgent.
    """

    # Instance attributes (set by _init_constitutional)
    _constitutional_config: ConstitutionalMixinConfig
    _constitutional_critique_service: Optional["ConstitutionalCritiqueService"]
    _constitutional_revision_service: Optional["ConstitutionalRevisionService"]
    _constitutional_llm: Optional["BedrockLLMService"]
    _constitutional_metrics: Dict[str, Any]
    _constitutional_initialized: bool
    # Phase 3: Audit queue service (ADR-063)
    _constitutional_audit_queue: Optional["ConstitutionalAuditQueueService"]

    def _init_constitutional(
        self,
        llm_service: Optional["BedrockLLMService"] = None,
        critique_service: Optional["ConstitutionalCritiqueService"] = None,
        revision_service: Optional["ConstitutionalRevisionService"] = None,
        config: Optional[ConstitutionalMixinConfig] = None,
        audit_queue_service: Optional["ConstitutionalAuditQueueService"] = None,
    ) -> None:
        """Initialize constitutional AI components.

        Must be called in the agent's __init__ after calling super().__init__.

        Args:
            llm_service: LLM service for critique/revision (if not providing services).
            critique_service: Pre-configured critique service (optional).
            revision_service: Pre-configured revision service (optional).
            config: Per-agent configuration (optional, uses defaults).
            audit_queue_service: SQS audit queue service for Phase 3 (ADR-063).
        """
        self._constitutional_config = config or ConstitutionalMixinConfig()
        self._constitutional_llm = llm_service
        self._constitutional_metrics = {
            "total_processed": 0,
            "total_revised": 0,
            "total_blocked": 0,
            "total_hitl_escalations": 0,
            "total_skipped": 0,
            "critique_counts": {"critical": 0, "high": 0, "medium": 0, "low": 0},
            "total_processing_time_ms": 0.0,
            "revision_iterations_total": 0,
            # Phase 3 metrics
            "cache_hits": 0,
            "fast_path_blocks": 0,
        }

        # Use provided services or create them lazily
        self._constitutional_critique_service = critique_service
        self._constitutional_revision_service = revision_service
        self._constitutional_initialized = True

        # Phase 3: Audit queue service (ADR-063)
        self._constitutional_audit_queue = audit_queue_service

        logger.info(
            f"Initialized ConstitutionalMixin with config: "
            f"domain_tags={self._constitutional_config.domain_tags}, "
            f"mock_mode={self._constitutional_config.mock_mode}"
            f"{', audit_queue enabled' if audit_queue_service else ''}"
        )

    def _ensure_constitutional_initialized(self) -> None:
        """Ensure constitutional components are initialized."""
        if not getattr(self, "_constitutional_initialized", False):
            raise RuntimeError(
                "Constitutional mixin not initialized. "
                "Call _init_constitutional() in your agent's __init__."
            )

    def _get_critique_service(self) -> "ConstitutionalCritiqueService":
        """Get or create the critique service."""
        self._ensure_constitutional_initialized()

        if self._constitutional_critique_service is None:
            from src.services.constitutional_ai.critique_service import (
                ConstitutionalCritiqueService,
            )

            self._constitutional_critique_service = ConstitutionalCritiqueService(
                llm_service=self._constitutional_llm,
                mock_mode=self._constitutional_config.mock_mode,
            )
        return self._constitutional_critique_service

    def _get_revision_service(self) -> "ConstitutionalRevisionService":
        """Get or create the revision service."""
        self._ensure_constitutional_initialized()

        if self._constitutional_revision_service is None:
            from src.services.constitutional_ai.revision_service import (
                ConstitutionalRevisionService,
            )

            self._constitutional_revision_service = ConstitutionalRevisionService(
                critique_service=self._get_critique_service(),
                llm_service=self._constitutional_llm,
                mock_mode=self._constitutional_config.mock_mode,
            )
        return self._constitutional_revision_service

    async def process_with_constitutional(
        self,
        output: Any,
        context: "ConstitutionalContext",
        autonomy_level: Optional[str] = None,
    ) -> ConstitutionalProcessingResult:
        """Apply constitutional critique and revision to an output.

        This is the main entry point for agents to apply constitutional
        oversight. It performs:
        1. Skip check based on autonomy level
        2. Serialize output to string
        3. Critique the output against applicable principles
        4. Revise if issues require revision
        5. Escalate to HITL if critical issues unresolved
        6. Return processed output with full metadata

        Args:
            output: The agent output to process (str or dict).
            context: Constitutional context with agent/operation info.
            autonomy_level: Override autonomy level (uses config default if None).

        Returns:
            ConstitutionalProcessingResult with processed output and metadata.
        """
        self._ensure_constitutional_initialized()
        start_time = time.time()

        # Check if we should skip processing
        if self._should_skip_constitutional(autonomy_level):
            return ConstitutionalProcessingResult(
                original_output=output,
                processed_output=output,
                skipped=True,
                skip_reason=f"Autonomy level {autonomy_level} in skip list",
                processing_time_ms=(time.time() - start_time) * 1000,
            )

        # Serialize output for processing
        output_str = self._serialize_output(output)

        # Update context with config domain tags if not set
        if not context.domain_tags and self._constitutional_config.domain_tags:
            context = self._create_context_with_tags(context)

        # Phase 3: Apply tiered critique strategy based on autonomy level (ADR-063)
        applicable_principles = self._get_tiered_principles(autonomy_level)

        # Perform critique
        critique_service = self._get_critique_service()
        summary = await critique_service.critique_output(
            agent_output=output_str,
            context=context,
            applicable_principles=applicable_principles,
        )

        # Track Phase 3 metrics
        if hasattr(critique_service, "_cache_hits"):
            self._constitutional_metrics["cache_hits"] = critique_service._cache_hits
        if hasattr(critique_service, "_fast_path_blocks"):
            self._constitutional_metrics["fast_path_blocks"] = (
                critique_service._fast_path_blocks
            )

        # Track critique metrics
        self._update_critique_metrics(summary)

        # If no revision needed, return original output
        if not summary.requires_revision:
            processing_time = (time.time() - start_time) * 1000
            self._constitutional_metrics["total_processed"] += 1
            self._constitutional_metrics["total_processing_time_ms"] += processing_time

            return ConstitutionalProcessingResult(
                original_output=output,
                processed_output=output,
                was_revised=False,
                critique_summary=summary,
                processing_time_ms=processing_time,
            )

        # Perform revision
        revision_service = self._get_revision_service()
        max_iterations = (
            self._constitutional_config.max_revision_iterations
            or revision_service.failure_config.max_revision_iterations
        )

        critiques_to_revise = [c for c in summary.critiques if c.requires_revision]

        try:
            revision_result = await revision_service.revise_output(
                agent_output=output_str,
                critiques=critiques_to_revise,
                context=context,
                max_iterations=max_iterations,
            )
        except Exception as e:
            # Handle revision failure based on config
            logger.warning(f"Revision failed: {e}")
            revision_result = None

        # Check if we need HITL escalation
        hitl_required = False
        hitl_request_id = None
        blocked = False
        block_reason = None

        if revision_result and not revision_result.converged:
            # Check remaining critical issues
            remaining_critical = revision_result.metadata.get("remaining_issues", 0)
            if remaining_critical > 0:
                if self._constitutional_config.block_on_critical:
                    blocked = True
                    block_reason = (
                        f"Unresolved critical issues after {revision_result.revision_iterations} "
                        f"revision iterations"
                    )
                if self._constitutional_config.enable_hitl_escalation:
                    hitl_required = True
                    hitl_request_id = await self._request_constitutional_hitl(
                        output=output_str,
                        remaining_issues=critiques_to_revise,
                        context=context,
                    )

        # Deserialize revised output back to original format
        processed_output = output
        was_revised = False
        if revision_result and revision_result.was_modified:
            processed_output = self._deserialize_output(
                revision_result.revised_output, output
            )
            was_revised = True

        # Calculate processing time and update metrics
        processing_time = (time.time() - start_time) * 1000
        self._constitutional_metrics["total_processed"] += 1
        self._constitutional_metrics["total_processing_time_ms"] += processing_time
        if was_revised:
            self._constitutional_metrics["total_revised"] += 1
        if blocked:
            self._constitutional_metrics["total_blocked"] += 1
        if hitl_required:
            self._constitutional_metrics["total_hitl_escalations"] += 1
        if revision_result:
            self._constitutional_metrics[
                "revision_iterations_total"
            ] += revision_result.revision_iterations

        result = ConstitutionalProcessingResult(
            original_output=output,
            processed_output=processed_output if not blocked else output,
            was_revised=was_revised,
            critique_summary=summary,
            revision_result=revision_result,
            hitl_required=hitl_required,
            hitl_request_id=hitl_request_id,
            blocked=blocked,
            block_reason=block_reason,
            processing_time_ms=processing_time,
        )

        # Log audit trail
        await self._log_constitutional_audit(result, context)

        return result

    async def critique_only(
        self,
        output: Any,
        context: "ConstitutionalContext",
    ) -> "ConstitutionalEvaluationSummary":
        """Perform critique without revision (for read-only analysis).

        Useful for agents that want to surface issues without modifying output,
        or for audit/compliance logging.

        Args:
            output: The output to critique.
            context: Constitutional context.

        Returns:
            ConstitutionalEvaluationSummary with all critique results.
        """
        self._ensure_constitutional_initialized()

        output_str = self._serialize_output(output)

        if not context.domain_tags and self._constitutional_config.domain_tags:
            context = self._create_context_with_tags(context)

        critique_service = self._get_critique_service()
        return await critique_service.critique_output(
            agent_output=output_str,
            context=context,
            applicable_principles=self._constitutional_config.applicable_principles,
        )

    def _should_skip_constitutional(
        self,
        autonomy_level: Optional[str] = None,
    ) -> bool:
        """Check if constitutional processing should be skipped.

        Args:
            autonomy_level: Current autonomy level.

        Returns:
            True if processing should be skipped.
        """
        if autonomy_level is None:
            return False
        return autonomy_level in self._constitutional_config.skip_for_autonomy_levels

    def _get_tiered_principles(
        self,
        autonomy_level: Optional[str] = None,
    ) -> Optional[List[str]]:
        """Get applicable principles based on autonomy level tier (Phase 3).

        Uses tiered critique strategy from ADR-063 Phase 3:
        - FULL_AUTONOMOUS: All principles
        - LIMITED_AUTONOMOUS: CRITICAL + HIGH only
        - COLLABORATIVE: All principles
        - FULL_HITL: CRITICAL only (minimal critique)

        Args:
            autonomy_level: Current autonomy level.

        Returns:
            List of principle IDs to apply, or None for all principles.
        """
        from src.services.constitutional_ai.tiered_critique import (
            get_critique_tier,
            get_principles_for_tier,
        )

        tier = get_critique_tier(autonomy_level)
        tier_principles = get_principles_for_tier(tier)

        # Merge with config-specified principles
        if tier_principles is not None:
            if self._constitutional_config.applicable_principles:
                # Intersection: both tier AND config
                config_set = set(self._constitutional_config.applicable_principles)
                tier_set = set(tier_principles)
                return list(config_set & tier_set)
            return tier_principles

        # Tier allows all principles, use config if specified
        return self._constitutional_config.applicable_principles

    def _serialize_output(self, output: Any) -> str:
        """Serialize agent output to string for constitutional processing.

        Handles both string outputs and structured dict outputs from agents.

        Args:
            output: Agent output (str or dict).

        Returns:
            String representation for critique.
        """
        if isinstance(output, str):
            return output
        if isinstance(output, dict):
            try:
                return json.dumps(output, indent=2, default=str)
            except (TypeError, ValueError):
                return str(output)
        return str(output)

    def _deserialize_output(
        self,
        revised_str: str,
        original_output: Any,
    ) -> Any:
        """Deserialize revised output back to original format.

        If original was dict, attempts to parse JSON. Falls back to
        returning string if parse fails.

        Args:
            revised_str: Revised output string.
            original_output: Original output for type detection.

        Returns:
            Output in same format as original.
        """
        if isinstance(original_output, str):
            return revised_str

        if isinstance(original_output, dict):
            try:
                return json.loads(revised_str)
            except (json.JSONDecodeError, TypeError):
                # Fall back to returning string if JSON parse fails
                logger.warning(
                    "Failed to parse revised output as JSON, returning string"
                )
                return revised_str

        return revised_str

    def _create_context_with_tags(
        self, context: "ConstitutionalContext"
    ) -> "ConstitutionalContext":
        """Create a new context with domain tags from config."""
        from src.services.constitutional_ai.models import ConstitutionalContext

        return ConstitutionalContext(
            agent_name=context.agent_name,
            operation_type=context.operation_type,
            user_request=context.user_request,
            domain_tags=self._constitutional_config.domain_tags,
            metadata=context.metadata,
        )

    async def _request_constitutional_hitl(
        self,
        output: Any,
        remaining_issues: List["CritiqueResult"],
        context: "ConstitutionalContext",
    ) -> Optional[str]:
        """Request HITL approval for unresolved constitutional issues.

        Integrates with existing HITL patterns. If agent has MCPToolMixin's
        _request_hitl_approval, uses that. Otherwise creates standalone request.

        Args:
            output: The output with unresolved issues.
            remaining_issues: Critique results requiring human review.
            context: Constitutional context.

        Returns:
            HITL request ID if created, None if HITL disabled.
        """
        if not self._constitutional_config.enable_hitl_escalation:
            return None

        request_id = str(uuid.uuid4())

        # Check if we have MCPToolMixin's HITL method
        if hasattr(self, "_request_hitl_approval"):
            try:
                # Use existing HITL pattern
                await self._request_hitl_approval(  # type: ignore
                    tool_name="constitutional_ai_review",
                    params={
                        "output": self._serialize_output(output)[:1000],
                        "issues": [
                            {
                                "principle_id": c.principle_id,
                                "severity": c.severity.value,
                                "issues": c.issues_found[:3],
                            }
                            for c in remaining_issues[:5]
                        ],
                        "context": context.to_dict(),
                        "request_id": request_id,
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to request HITL via MCPToolMixin: {e}")

        # Log HITL request for standalone handling
        logger.info(
            f"Constitutional AI HITL request created: {request_id}, "
            f"agent={context.agent_name}, "
            f"issues={len(remaining_issues)}"
        )

        return request_id

    def _update_critique_metrics(
        self, summary: "ConstitutionalEvaluationSummary"
    ) -> None:
        """Update critique metrics from evaluation summary."""
        self._constitutional_metrics["critique_counts"][
            "critical"
        ] += summary.critical_issues
        self._constitutional_metrics["critique_counts"]["high"] += summary.high_issues
        self._constitutional_metrics["critique_counts"][
            "medium"
        ] += summary.medium_issues
        self._constitutional_metrics["critique_counts"]["low"] += summary.low_issues

    def _record_constitutional_metrics(
        self,
        result: ConstitutionalProcessingResult,
    ) -> None:
        """Record constitutional processing metrics.

        Tracks:
        - Total outputs processed
        - Critique counts by severity
        - Revision counts and iterations
        - HITL escalation rate
        - Block rate
        - Processing latency

        Args:
            result: The processing result to record.
        """
        self._constitutional_metrics["total_processed"] += 1
        self._constitutional_metrics[
            "total_processing_time_ms"
        ] += result.processing_time_ms

        if result.was_revised:
            self._constitutional_metrics["total_revised"] += 1
        if result.blocked:
            self._constitutional_metrics["total_blocked"] += 1
        if result.hitl_required:
            self._constitutional_metrics["total_hitl_escalations"] += 1
        if result.skipped:
            self._constitutional_metrics["total_skipped"] += 1

    def get_constitutional_metrics(self) -> Dict[str, Any]:
        """Get accumulated constitutional metrics for this agent.

        Returns:
            Dict with all constitutional metrics.
        """
        self._ensure_constitutional_initialized()

        metrics = dict(self._constitutional_metrics)

        # Calculate derived metrics
        total = metrics["total_processed"]
        if total > 0:
            metrics["revision_rate"] = metrics["total_revised"] / total
            metrics["block_rate"] = metrics["total_blocked"] / total
            metrics["hitl_rate"] = metrics["total_hitl_escalations"] / total
            metrics["avg_processing_time_ms"] = (
                metrics["total_processing_time_ms"] / total
            )
        else:
            metrics["revision_rate"] = 0.0
            metrics["block_rate"] = 0.0
            metrics["hitl_rate"] = 0.0
            metrics["avg_processing_time_ms"] = 0.0

        return metrics

    async def _log_constitutional_audit(
        self,
        result: ConstitutionalProcessingResult,
        context: "ConstitutionalContext",
    ) -> None:
        """Log audit trail for constitutional processing.

        Logs to standard logger with structured format for compliance.
        Phase 3 (ADR-063): Also writes to SQS audit queue for async persistence.

        Args:
            result: Processing result to log.
            context: Constitutional context.
        """
        audit_entry = {
            "timestamp": result.timestamp.isoformat(),
            "agent_name": context.agent_name,
            "operation_type": context.operation_type,
            "was_revised": result.was_revised,
            "blocked": result.blocked,
            "hitl_required": result.hitl_required,
            "processing_time_ms": result.processing_time_ms,
        }

        if result.critique_summary:
            audit_entry["critique_summary"] = {
                "total_evaluated": result.critique_summary.total_principles_evaluated,
                "critical_issues": result.critique_summary.critical_issues,
                "requires_revision": result.critique_summary.requires_revision,
            }

        # Standard logger output
        logger.info(f"Constitutional AI audit: {json.dumps(audit_entry)}")

        # Phase 3: Send to SQS audit queue (fire-and-forget)
        if self._constitutional_audit_queue:
            try:
                from src.services.constitutional_ai.audit_queue_service import (
                    create_audit_entry,
                )

                sqs_entry = create_audit_entry(
                    agent_name=context.agent_name,
                    operation_type=context.operation_type,
                    output=self._serialize_output(result.original_output),
                    critique_summary=(
                        result.critique_summary.to_dict()
                        if result.critique_summary
                        else None
                    ),
                    revision_performed=result.was_revised,
                    revision_iterations=(
                        result.revision_result.revision_iterations
                        if result.revision_result
                        else 0
                    ),
                    blocked=result.blocked,
                    block_reason=result.block_reason,
                    hitl_required=result.hitl_required,
                    hitl_request_id=result.hitl_request_id,
                    processing_time_ms=result.processing_time_ms,
                    cache_hit=(
                        getattr(result.critique_summary, "cache_hit", False)
                        if result.critique_summary
                        else False
                    ),
                    fast_path_blocked=(
                        getattr(result.critique_summary, "fast_path_blocked", False)
                        if result.critique_summary
                        else False
                    ),
                )
                await self._constitutional_audit_queue.send_audit_async(sqs_entry)
            except Exception as e:
                logger.warning(f"Failed to send audit to SQS: {e}")
