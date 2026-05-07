"""Scout Agent — discovers new Bedrock models for the assurance pipeline.

Periodic poll:
    1. List foundation models in the deployment partition.
    2. For each model not already known (active / rejected / incumbent /
       pending), check the Adapter Registry's capability requirements.
    3. Emit a ``ModelCandidateDetected`` event tagged with the
       eligibility flag.

GovCloud partition awareness (per ADR-088 §Stage 1 condition):
Bedrock model availability in ``us-gov-west-1`` lags commercial by
3-6 months. The Scout Agent polls only the deployment partition
(supplied at construction). It never speculatively probes commercial
when running in GovCloud — that would require cross-partition
credentials that no service role should hold. Models flagged
``PENDING_AVAILABILITY`` are detected via the optional commercial
catalog snapshot the operator can supply (admin-curated, not
auto-fetched).

EventBridge integration is via a sink interface so tests can inject
an in-memory recorder. The ``DefaultEventBridgeSink`` writes to the
default AWS bus on the partition ARN; soft-imports boto3 with the
same fallback pattern as the Bedrock client.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Iterable, Protocol

from src.services.model_assurance.adapter_registry import (
    AdapterRegistry,
    DisqualificationReason,
    ModelAdapter,
    ModelArchitecture,
    ModelProvider,
    ModelRequirements,
    TokenizerType,
)
from src.services.model_assurance.scout.bedrock_client import (
    BedrockListClient,
    BedrockModelSummary,
    infer_architecture,
    infer_tokenizer,
)
from src.services.model_assurance.scout.events import (
    EVENT_DETAIL_TYPE,
    EVENT_SOURCE,
    EligibilityFlag,
    ModelCandidateDetected,
    make_event,
)
from src.services.model_assurance.scout.scout_state import (
    ScoutStateStore,
)

logger = logging.getLogger(__name__)


try:  # pragma: no cover — exercised via mock-mode tests
    import boto3

    BOTO3_AVAILABLE = True
except ImportError:  # pragma: no cover
    boto3 = None  # type: ignore[assignment]
    BOTO3_AVAILABLE = False


# =============================================================================
# Sinks — anything that wants to receive ModelCandidateDetected events
# =============================================================================


class CandidateEventSink(Protocol):
    def emit(self, event: ModelCandidateDetected) -> None: ...


class InMemoryEventSink:
    """Test sink — buffers events in declaration order."""

    def __init__(self) -> None:
        self._events: list[ModelCandidateDetected] = []

    def emit(self, event: ModelCandidateDetected) -> None:
        self._events.append(event)

    @property
    def events(self) -> tuple[ModelCandidateDetected, ...]:
        return tuple(self._events)


class EventBridgeSink:
    """Production sink — writes to the EventBridge default bus.

    Soft-imports boto3 and falls through to no-op behaviour when
    unavailable so tests don't need AWS credentials. Errors are
    logged but not raised — a transient EventBridge failure must not
    block the Scout Agent's poll loop.
    """

    def __init__(
        self,
        *,
        bus_name: str = "default",
        region: str = "us-east-1",
        client=None,  # type: ignore[no-untyped-def]
    ) -> None:
        self._bus_name = bus_name
        self._region = region
        if client is not None:
            self._client = client
            self._is_live = True
        elif BOTO3_AVAILABLE:
            try:
                self._client = boto3.client("events", region_name=region)
                self._is_live = True
            except Exception as exc:  # pragma: no cover — env-specific
                logger.info(
                    "EventBridgeSink could not init real client (%s); "
                    "falling back to no-op mode",
                    exc,
                )
                self._client = None
                self._is_live = False
        else:
            self._client = None
            self._is_live = False

    @property
    def is_live(self) -> bool:
        return self._is_live

    def emit(self, event: ModelCandidateDetected) -> None:
        if not self._is_live:
            return
        try:
            self._client.put_events(
                Entries=[
                    {
                        "Source": EVENT_SOURCE,
                        "DetailType": EVENT_DETAIL_TYPE,
                        "Detail": json.dumps(event.to_eventbridge_detail()),
                        "EventBusName": self._bus_name,
                    }
                ]
            )
        except Exception as exc:  # pragma: no cover — runtime AWS failure
            logger.warning(
                "EventBridgeSink put_events failed for %s: %s",
                event.candidate_id,
                exc,
            )


# =============================================================================
# Scout Agent
# =============================================================================


@dataclass(frozen=True)
class ScoutResult:
    """Summary of one Scout Agent run for observability."""

    polled_models: int
    new_qualified: int
    new_disqualified: int
    pending_availability: int
    already_known: int
    throttled: bool


class ScoutAgent:
    """Periodic candidate-discovery agent.

    Constructor takes a Bedrock client wrapper, a state store, an
    adapter registry, the requirements bar, and one or more event
    sinks. The poll loop is implemented in :py:meth:`run_once` —
    EventBridge schedule wiring (CloudFormation rule + Lambda
    invocation) is Phase 2 infrastructure; the agent itself is
    schedule-agnostic so it can be invoked from CLI tools, unit
    tests, or a Lambda runtime equally.
    """

    def __init__(
        self,
        *,
        bedrock_client: BedrockListClient,
        state_store: ScoutStateStore,
        adapter_registry: AdapterRegistry,
        requirements: ModelRequirements,
        sinks: Iterable[CandidateEventSink],
        partition: str = "aws",
        commercial_catalog_snapshot: tuple[BedrockModelSummary, ...] = (),
    ) -> None:
        self._bedrock = bedrock_client
        self._state = state_store
        self._registry = adapter_registry
        self._requirements = requirements
        self._sinks = tuple(sinks)
        self._partition = partition
        self._commercial_snapshot = commercial_catalog_snapshot

    def run_once(self) -> ScoutResult:
        """Execute one poll cycle.

        The cycle is idempotent: a previously-emitted candidate stays
        in the dedup state and won't be re-emitted on the next call.
        """
        response = self._bedrock.list_models()
        snapshot = self._state.snapshot()
        seen_ids = {m.model_id for m in response.models}

        polled = len(response.models)
        new_qual = 0
        new_disqual = 0
        pending = 0
        already = 0

        for model in response.models:
            event = self._classify(model, snapshot)
            self._broadcast(event)
            if event.eligibility is EligibilityFlag.QUALIFIED:
                new_qual += 1
            elif event.eligibility is EligibilityFlag.REJECTED_NO_CAPABILITY:
                new_disqual += 1
            elif event.eligibility is EligibilityFlag.PENDING_AVAILABILITY:
                pending += 1
            else:
                already += 1

        # GovCloud "pending" bookkeeping: any commercial model not
        # in the deployment partition is recorded as pending so it
        # surfaces in dashboards. When it later appears in the
        # deployment partition, the next run_once call clears the
        # pending flag and emits a normal candidate event.
        for model in self._commercial_snapshot:
            if model.model_id in seen_ids:
                # Now available in deployment partition — clear pending.
                self._state.clear_pending(model.model_id)
                continue
            if model.model_id in snapshot.pending_availability:
                continue  # already pending; don't re-emit
            event = make_event(
                candidate_id=model.model_id,
                display_name=model.display_name,
                provider=model.provider,
                partition=self._partition,
                eligibility=EligibilityFlag.PENDING_AVAILABILITY,
                notes=(
                    "Detected in commercial catalog snapshot but not yet "
                    f"available in {self._partition}."
                ),
            )
            self._broadcast(event)
            self._state.mark_pending_availability(model.model_id)
            pending += 1

        return ScoutResult(
            polled_models=polled,
            new_qualified=new_qual,
            new_disqualified=new_disqual,
            pending_availability=pending,
            already_known=already,
            throttled=response.throttled,
        )

    # ---------------------------------------------------------- internals

    def _classify(
        self,
        model: BedrockModelSummary,
        snapshot,  # type: ignore[no-untyped-def]
    ) -> ModelCandidateDetected:
        """Map a Bedrock summary to a ModelCandidateDetected event."""
        if (
            model.model_id in snapshot.active_evaluations
            or model.model_id in snapshot.rejected
            or model.model_id in snapshot.incumbent_ids
        ):
            return make_event(
                candidate_id=model.model_id,
                display_name=model.display_name,
                provider=model.provider,
                partition=self._partition,
                eligibility=EligibilityFlag.ALREADY_KNOWN,
                notes=self._already_known_reason(model.model_id, snapshot),
            )

        # Synthesize a candidate adapter for the registry check.
        candidate_adapter = self._adapter_for(model)
        reasons = self._requirements.check(candidate_adapter)
        if reasons:
            return make_event(
                candidate_id=model.model_id,
                display_name=model.display_name,
                provider=model.provider,
                partition=self._partition,
                eligibility=EligibilityFlag.REJECTED_NO_CAPABILITY,
                disqualification_reasons=reasons,
            )

        return make_event(
            candidate_id=model.model_id,
            display_name=model.display_name,
            provider=model.provider,
            partition=self._partition,
            eligibility=EligibilityFlag.QUALIFIED,
        )

    def _adapter_for(self, model: BedrockModelSummary) -> ModelAdapter:
        """Return the registered adapter, or synthesise one from defaults.

        For models the registry already knows about, the registered
        adapter is authoritative — its hand-curated cost and context-
        window numbers are more accurate than what Bedrock's response
        provides. For unknown models the agent synthesises a defensive
        adapter using zero costs (so unknown-but-eligible models still
        pass the cost check) and inferred tokenizer/architecture.
        """
        existing = self._registry.find(model.model_id)
        if existing is not None:
            return existing
        return ModelAdapter(
            model_id=model.model_id,
            provider=model.provider,
            display_name=model.display_name,
            max_context_tokens=200_000,  # safe optimistic default for Anthropic
            supports_tool_use=True,
            supports_streaming=model.response_streaming_supported,
            tokenizer_type=infer_tokenizer(model.model_id),
            architecture=infer_architecture(model.model_id),
            cost_per_input_mtok=0.0,
            cost_per_output_mtok=0.0,
            required_prompt_format="claude_messages_v1",
            notes="Synthesised by Scout Agent — pricing TBD on first eval.",
        )

    @staticmethod
    def _already_known_reason(
        candidate_id: str, snapshot
    ) -> str:  # type: ignore[no-untyped-def]
        if candidate_id in snapshot.active_evaluations:
            return "currently under evaluation"
        if candidate_id in snapshot.rejected:
            return "previously rejected"
        if candidate_id in snapshot.incumbent_ids:
            return "current incumbent"
        return ""

    def _broadcast(self, event: ModelCandidateDetected) -> None:
        for sink in self._sinks:
            try:
                sink.emit(event)
            except Exception as exc:
                # A failing sink must not stop the others.
                logger.warning(
                    "ScoutAgent sink %s failed for event %s: %s",
                    type(sink).__name__,
                    event.candidate_id,
                    exc,
                )


# =============================================================================
# Suppressed-pricing sentinel — synthesised adapters use zero cost so
# the registry-level cost check doesn't reject them. Real pricing is
# attached at evaluation time when a Provenance Service confirms the
# model has signed metadata available (Phase 2).
# =============================================================================


def synthesize_default_requirements() -> ModelRequirements:
    """Return the v1 production-baseline requirements for new candidates.

    Per ADR-088 condition #6 (Sally): tool use is required, and
    candidates must come from a trusted provider. Bedrock is trusted
    by default. The 32k minimum context matches the lower bound the
    rest of the platform's RAG pipeline assumes.
    """
    return ModelRequirements(
        min_context_tokens=32_000,
        require_tool_use=True,
        require_streaming=False,
        trusted_providers=(ModelProvider.BEDROCK,),
    )
