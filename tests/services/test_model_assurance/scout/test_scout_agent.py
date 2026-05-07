"""End-to-end tests for the Scout Agent (ADR-088 Phase 1.4)."""

from __future__ import annotations

import pytest

from src.services.model_assurance import (
    AdapterRegistry,
    DisqualificationReason,
    ModelProvider,
    ModelRequirements,
)
from src.services.model_assurance.scout import (
    BedrockListClient,
    EligibilityFlag,
    EventBridgeSink,
    InMemoryEventSink,
    InMemoryScoutStateStore,
    ScoutAgent,
    synthesize_default_requirements,
    synthesize_summary,
)


# ----------------------------------------------------------------- helpers


def _agent(
    *,
    fakes: tuple = (),
    state: InMemoryScoutStateStore | None = None,
    requirements: ModelRequirements | None = None,
    commercial_snapshot: tuple = (),
    partition: str = "aws",
) -> tuple[ScoutAgent, InMemoryEventSink, InMemoryScoutStateStore]:
    state = state or InMemoryScoutStateStore()
    client = BedrockListClient(client=None)
    client.install_fake(fakes)
    sink = InMemoryEventSink()
    agent = ScoutAgent(
        bedrock_client=client,
        state_store=state,
        adapter_registry=AdapterRegistry(),
        requirements=requirements or synthesize_default_requirements(),
        sinks=(sink,),
        partition=partition,
        commercial_catalog_snapshot=commercial_snapshot,
    )
    return agent, sink, state


# ------------------------------------------------------ classification


class TestClassification:
    def test_qualified_new_model(self) -> None:
        agent, sink, _ = _agent(
            fakes=(synthesize_summary(model_id="anthropic.claude-future"),),
        )
        result = agent.run_once()
        assert result.new_qualified == 1
        [ev] = sink.events
        assert ev.eligibility is EligibilityFlag.QUALIFIED

    def test_already_incumbent_skipped(self) -> None:
        state = InMemoryScoutStateStore(
            initial_incumbents=frozenset({"anthropic.claude-3-5-sonnet-20240620-v1:0"}),
        )
        agent, sink, _ = _agent(
            fakes=(synthesize_summary(
                model_id="anthropic.claude-3-5-sonnet-20240620-v1:0"
            ),),
            state=state,
        )
        result = agent.run_once()
        assert result.already_known == 1
        assert result.new_qualified == 0
        [ev] = sink.events
        assert ev.eligibility is EligibilityFlag.ALREADY_KNOWN
        assert "incumbent" in ev.notes.lower()

    def test_active_evaluation_dedup(self) -> None:
        state = InMemoryScoutStateStore()
        state.mark_active("anthropic.claude-future")
        agent, sink, _ = _agent(
            fakes=(synthesize_summary(model_id="anthropic.claude-future"),),
            state=state,
        )
        result = agent.run_once()
        assert result.already_known == 1
        assert result.new_qualified == 0
        [ev] = sink.events
        assert "evaluation" in ev.notes.lower()

    def test_previously_rejected_skipped(self) -> None:
        state = InMemoryScoutStateStore(
            initial_rejected=frozenset({"anthropic.claude-bad"}),
        )
        agent, sink, _ = _agent(
            fakes=(synthesize_summary(model_id="anthropic.claude-bad"),),
            state=state,
        )
        result = agent.run_once()
        assert result.already_known == 1
        [ev] = sink.events
        assert ev.eligibility is EligibilityFlag.ALREADY_KNOWN
        assert "rejected" in ev.notes.lower()

    def test_disqualified_by_capability_check(self) -> None:
        # synthesize a model that the registry's qualifier rejects:
        # synthesize_summary defaults streaming=True; require_streaming=False
        # so we trigger a different reason: tool_use=False on synthesised adapter
        # is overridden — instead use a too-strict requirements set.
        agent, sink, _ = _agent(
            fakes=(synthesize_summary(model_id="anthropic.tiny"),),
            requirements=ModelRequirements(
                min_context_tokens=2_000_000,  # bigger than synthesised default
                require_tool_use=True,
                trusted_providers=(ModelProvider.BEDROCK,),
            ),
        )
        result = agent.run_once()
        assert result.new_disqualified == 1
        [ev] = sink.events
        assert ev.eligibility is EligibilityFlag.REJECTED_NO_CAPABILITY
        assert DisqualificationReason.CONTEXT_TOO_SMALL in ev.disqualification_reasons


# -------------------------------------------------- partition awareness


class TestPartitionAwareness:
    def test_commercial_only_model_marked_pending(self) -> None:
        agent, sink, state = _agent(
            partition="aws-us-gov",
            commercial_snapshot=(
                synthesize_summary(model_id="anthropic.claude-commercial-only"),
            ),
        )
        result = agent.run_once()
        assert result.pending_availability == 1
        [ev] = sink.events
        assert ev.eligibility is EligibilityFlag.PENDING_AVAILABILITY
        assert "anthropic.claude-commercial-only" in (
            state.snapshot().pending_availability
        )

    def test_pending_cleared_when_model_appears_in_partition(self) -> None:
        # First run: commercial snapshot only — model marked pending.
        state = InMemoryScoutStateStore()
        commercial = (synthesize_summary(model_id="anthropic.future"),)
        agent1 = ScoutAgent(
            bedrock_client=BedrockListClient(client=None),
            state_store=state,
            adapter_registry=AdapterRegistry(),
            requirements=synthesize_default_requirements(),
            sinks=(InMemoryEventSink(),),
            partition="aws-us-gov",
            commercial_catalog_snapshot=commercial,
        )
        agent1._bedrock.install_fake(())
        agent1.run_once()
        assert "anthropic.future" in state.snapshot().pending_availability

        # Second run: deployment partition catalog now includes the model.
        client2 = BedrockListClient(client=None)
        client2.install_fake(commercial)
        sink2 = InMemoryEventSink()
        agent2 = ScoutAgent(
            bedrock_client=client2,
            state_store=state,
            adapter_registry=AdapterRegistry(),
            requirements=synthesize_default_requirements(),
            sinks=(sink2,),
            partition="aws-us-gov",
            commercial_catalog_snapshot=commercial,
        )
        agent2.run_once()
        assert "anthropic.future" not in state.snapshot().pending_availability
        # Now treated as a normal qualified candidate.
        assert any(
            ev.eligibility is EligibilityFlag.QUALIFIED for ev in sink2.events
        )

    def test_pending_does_not_re_emit_each_run(self) -> None:
        """After marking pending, subsequent runs don't duplicate the event."""
        state = InMemoryScoutStateStore()
        commercial = (synthesize_summary(model_id="anthropic.lagged"),)

        agent, sink, _ = _agent(
            commercial_snapshot=commercial,
            partition="aws-us-gov",
            state=state,
        )
        agent.run_once()
        first_count = len(sink.events)
        agent.run_once()
        # No new events on the second run for the same pending model.
        assert len(sink.events) == first_count


# ----------------------------------------------------- throttle path


class TestThrottlePath:
    def test_throttled_run_returns_partial_flag(self) -> None:
        client = BedrockListClient(client=None)
        # Inject a throttled response by patching list_models directly.
        original_list = client.list_models

        from src.services.model_assurance.scout.bedrock_client import (
            BedrockListResponse,
        )

        def throttled_list():  # type: ignore[no-untyped-def]
            return BedrockListResponse(models=(), throttled=True)

        client.list_models = throttled_list  # type: ignore[method-assign]
        try:
            agent = ScoutAgent(
                bedrock_client=client,
                state_store=InMemoryScoutStateStore(),
                adapter_registry=AdapterRegistry(),
                requirements=synthesize_default_requirements(),
                sinks=(InMemoryEventSink(),),
                partition="aws",
            )
            result = agent.run_once()
        finally:
            client.list_models = original_list  # type: ignore[method-assign]
        assert result.throttled is True
        assert result.polled_models == 0


# ------------------------------------------------------ sink fan-out


class TestSinkFanout:
    def test_multiple_sinks_each_receive(self) -> None:
        client = BedrockListClient(client=None)
        client.install_fake((synthesize_summary(model_id="m1"),))
        s1 = InMemoryEventSink()
        s2 = InMemoryEventSink()
        agent = ScoutAgent(
            bedrock_client=client,
            state_store=InMemoryScoutStateStore(),
            adapter_registry=AdapterRegistry(),
            requirements=synthesize_default_requirements(),
            sinks=(s1, s2),
            partition="aws",
        )
        agent.run_once()
        assert len(s1.events) == 1
        assert len(s2.events) == 1

    def test_failing_sink_does_not_block_others(self) -> None:
        class _BoomSink:
            def emit(self, event):  # type: ignore[no-untyped-def]
                raise RuntimeError("boom")

        good = InMemoryEventSink()
        client = BedrockListClient(client=None)
        client.install_fake((synthesize_summary(model_id="m1"),))
        agent = ScoutAgent(
            bedrock_client=client,
            state_store=InMemoryScoutStateStore(),
            adapter_registry=AdapterRegistry(),
            requirements=synthesize_default_requirements(),
            sinks=(_BoomSink(), good),
            partition="aws",
        )
        agent.run_once()
        assert len(good.events) == 1


# --------------------------------------------- EventBridgeSink mock mode


class TestEventBridgeSinkMockMode:
    def test_no_client_no_op(self) -> None:
        sink = EventBridgeSink(client=None)
        # In mock mode, emit must not raise, even if boto3 is missing entirely.
        sink._is_live = False  # force mock mode regardless of env
        sink.emit(  # type: ignore[arg-type]
            type(
                "E",
                (),
                {
                    "to_eventbridge_detail": lambda self: {"x": 1},
                    "candidate_id": "m",
                },
            )()
        )

    def test_live_call_uses_put_events(self) -> None:
        class _Fake:
            def __init__(self) -> None:
                self.calls = []  # type: ignore[var-annotated]

            def put_events(self, **kwargs):  # type: ignore[no-untyped-def]
                self.calls.append(kwargs)

        client = _Fake()
        sink = EventBridgeSink(client=client, bus_name="aura-events")
        from src.services.model_assurance.scout import make_event

        ev = make_event(
            candidate_id="m",
            display_name="M",
            provider=ModelProvider.BEDROCK,
            partition="aws",
            eligibility=EligibilityFlag.QUALIFIED,
        )
        sink.emit(ev)
        assert len(client.calls) == 1
        entry = client.calls[0]["Entries"][0]
        assert entry["Source"] == "aura.model_assurance.scout"
        assert entry["DetailType"] == "ModelCandidateDetected"
        assert entry["EventBusName"] == "aura-events"


# --------------------------------------------- Default requirements


class TestDefaultRequirements:
    def test_defaults_match_phase_1_baseline(self) -> None:
        reqs = synthesize_default_requirements()
        assert reqs.min_context_tokens == 32_000
        assert reqs.require_tool_use is True
        assert reqs.trusted_providers == (ModelProvider.BEDROCK,)


# --------------------------------------------- idempotency


class TestIdempotency:
    def test_repeated_runs_dont_double_emit(self) -> None:
        """Running twice with the same registry state — second run should
        find every model already known via the previous evaluation lifecycle.

        Phase 1.4 doesn't auto-promote on emit (the evaluation pipeline
        that lands in Phase 2 calls mark_active). So at this layer the
        first run emits QUALIFIED, the second does too — but the test
        below verifies that explicit lifecycle calls suppress the
        re-emission, which is the production path."""
        state = InMemoryScoutStateStore()
        client = BedrockListClient(client=None)
        client.install_fake((synthesize_summary(model_id="m1"),))
        sink = InMemoryEventSink()
        agent = ScoutAgent(
            bedrock_client=client,
            state_store=state,
            adapter_registry=AdapterRegistry(),
            requirements=synthesize_default_requirements(),
            sinks=(sink,),
            partition="aws",
        )
        agent.run_once()
        assert sink.events[0].eligibility is EligibilityFlag.QUALIFIED

        # Production path: orchestrator marks the candidate as active
        # once it picks up the event. After that, subsequent runs
        # treat it as already-known.
        state.mark_active("m1")
        sink2 = InMemoryEventSink()
        agent2 = ScoutAgent(
            bedrock_client=client,
            state_store=state,
            adapter_registry=AdapterRegistry(),
            requirements=synthesize_default_requirements(),
            sinks=(sink2,),
            partition="aws",
        )
        agent2.run_once()
        assert sink2.events[0].eligibility is EligibilityFlag.ALREADY_KNOWN
