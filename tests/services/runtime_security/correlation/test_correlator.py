"""
Tests for the Runtime-to-Code Correlator.

Covers CorrelationChain and CorrelationResult frozen dataclasses,
single-event and batch correlation, auto-remediation, singleton lifecycle,
and correlator property accessors.
"""

import dataclasses
from datetime import datetime, timezone

import pytest

from src.services.runtime_security.correlation import (
    RuntimeCodeCorrelator,
    get_code_correlator,
    reset_code_correlator,
)
from src.services.runtime_security.correlation.correlator import (
    CorrelationChain,
    CorrelationResult,
)
from src.services.runtime_security.correlation.graph_tracer import (
    CallGraphPath,
    GraphTracer,
    TraceResult,
)
from src.services.runtime_security.correlation.remediation import (
    RemediationOrchestrator,
    RemediationPlan,
    RemediationStatus,
)
from src.services.runtime_security.correlation.vector_matcher import (
    MatchResult,
    VectorMatcher,
    VulnerabilityMatch,
)

# =========================================================================
# CorrelationChain Tests
# =========================================================================


class TestCorrelationChain:
    """Tests for the CorrelationChain frozen dataclass."""

    def test_create_minimal(self):
        """Test creating a CorrelationChain with only required fields."""
        chain = CorrelationChain(
            event_id="te-chain001",
            agent_id="coder-agent",
        )
        assert chain.event_id == "te-chain001"
        assert chain.agent_id == "coder-agent"
        assert chain.trace_result is None
        assert chain.match_result is None
        assert chain.remediation_plan is None

    def test_frozen_immutability(self):
        """Test that CorrelationChain fields cannot be mutated."""
        chain = CorrelationChain(
            event_id="te-frozen",
            agent_id="agent",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            chain.event_id = "te-mutated"  # type: ignore[misc]

    def test_frozen_immutability_agent_id(self):
        """Test that agent_id cannot be mutated."""
        chain = CorrelationChain(
            event_id="te-frozen2",
            agent_id="agent",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            chain.agent_id = "evil-agent"  # type: ignore[misc]

    def test_to_dict_minimal(self):
        """Test to_dict with no trace/match/remediation."""
        chain = CorrelationChain(
            event_id="te-dict",
            agent_id="agent",
        )
        d = chain.to_dict()
        assert d["event_id"] == "te-dict"
        assert d["agent_id"] == "agent"
        assert d["has_trace"] is False
        assert d["has_match"] is False
        assert d["has_remediation"] is False
        assert d["is_complete"] is False
        assert d["trace_result"] is None
        assert d["match_result"] is None
        assert d["remediation_plan"] is None

    def test_has_trace_true(self, now_utc: datetime):
        """Test has_trace is True when trace_result has source."""
        path = CallGraphPath(
            path_id="cp-ht",
            nodes=("a",),
            edges=(),
            source_file="src/found.py",
            confidence=0.8,
        )
        trace = TraceResult(
            trace_id="tr-ht",
            event_id="te-ht",
            paths=(path,),
            total_paths_found=1,
            max_depth_reached=0,
            timestamp=now_utc,
            query_latency_ms=1.0,
        )
        chain = CorrelationChain(
            event_id="te-ht",
            agent_id="agent",
            trace_result=trace,
        )
        assert chain.has_trace is True

    def test_has_trace_false_no_source(self, now_utc: datetime):
        """Test has_trace is False when trace_result has no source file."""
        path = CallGraphPath(
            path_id="cp-nosrc",
            nodes=("a",),
            edges=(),
        )
        trace = TraceResult(
            trace_id="tr-nosrc",
            event_id="te-nosrc",
            paths=(path,),
            total_paths_found=1,
            max_depth_reached=0,
            timestamp=now_utc,
            query_latency_ms=1.0,
        )
        chain = CorrelationChain(
            event_id="te-nosrc",
            agent_id="agent",
            trace_result=trace,
        )
        assert chain.has_trace is False

    def test_has_trace_false_none(self):
        """Test has_trace is False when trace_result is None."""
        chain = CorrelationChain(event_id="te-none", agent_id="agent")
        assert chain.has_trace is False

    def test_has_match_true(self, now_utc: datetime):
        """Test has_match is True when match_result has matches."""
        match = VulnerabilityMatch(
            match_id="vm-hm",
            vulnerability_id="v1",
            vulnerability_type="SQLi",
            description="test",
            similarity_score=0.8,
        )
        match_result = MatchResult(
            result_id="mr-hm",
            query_text="test",
            matches=(match,),
            total_matches=1,
            query_latency_ms=1.0,
            timestamp=now_utc,
        )
        chain = CorrelationChain(
            event_id="te-hm",
            agent_id="agent",
            match_result=match_result,
        )
        assert chain.has_match is True

    def test_has_match_false_empty(self, now_utc: datetime):
        """Test has_match is False when match_result has no matches."""
        match_result = MatchResult(
            result_id="mr-empty",
            query_text="test",
            matches=(),
            total_matches=0,
            query_latency_ms=1.0,
            timestamp=now_utc,
        )
        chain = CorrelationChain(
            event_id="te-nomatch",
            agent_id="agent",
            match_result=match_result,
        )
        assert chain.has_match is False

    def test_has_match_false_none(self):
        """Test has_match is False when match_result is None."""
        chain = CorrelationChain(event_id="te-nm", agent_id="agent")
        assert chain.has_match is False

    def test_has_remediation_true(self, now_utc: datetime):
        """Test has_remediation is True when remediation_plan is present."""
        plan = RemediationPlan(
            plan_id="rp-hr",
            vulnerability_id="v1",
            correlation_id="c1",
            status=RemediationStatus.PATCH_GENERATED,
            patches=(),
            created_at=now_utc,
            updated_at=now_utc,
        )
        chain = CorrelationChain(
            event_id="te-hr",
            agent_id="agent",
            remediation_plan=plan,
        )
        assert chain.has_remediation is True

    def test_has_remediation_false(self):
        """Test has_remediation is False when remediation_plan is None."""
        chain = CorrelationChain(event_id="te-nr", agent_id="agent")
        assert chain.has_remediation is False

    def test_is_complete_true(self, now_utc: datetime):
        """Test is_complete is True when all three components are present."""
        path = CallGraphPath(
            path_id="cp-complete",
            nodes=("a",),
            edges=(),
            source_file="src/file.py",
            confidence=0.9,
        )
        trace = TraceResult(
            trace_id="tr-complete",
            event_id="te-complete",
            paths=(path,),
            total_paths_found=1,
            max_depth_reached=0,
            timestamp=now_utc,
            query_latency_ms=1.0,
        )
        vuln_match = VulnerabilityMatch(
            match_id="vm-complete",
            vulnerability_id="v1",
            vulnerability_type="SQLi",
            description="test",
            similarity_score=0.8,
        )
        match_result = MatchResult(
            result_id="mr-complete",
            query_text="test",
            matches=(vuln_match,),
            total_matches=1,
            query_latency_ms=1.0,
            timestamp=now_utc,
        )
        plan = RemediationPlan(
            plan_id="rp-complete",
            vulnerability_id="v1",
            correlation_id="c1",
            status=RemediationStatus.PATCH_GENERATED,
            patches=(),
            created_at=now_utc,
            updated_at=now_utc,
        )
        chain = CorrelationChain(
            event_id="te-complete",
            agent_id="agent",
            trace_result=trace,
            match_result=match_result,
            remediation_plan=plan,
        )
        assert chain.is_complete is True

    def test_is_complete_false_missing_trace(self, now_utc: datetime):
        """Test is_complete is False when trace is missing."""
        chain = CorrelationChain(event_id="te-inc", agent_id="agent")
        assert chain.is_complete is False

    def test_to_dict_with_all_components(self, now_utc: datetime):
        """Test to_dict with trace, match, and remediation populated."""
        path = CallGraphPath(
            path_id="cp-full",
            nodes=("a",),
            edges=(),
            source_file="src/f.py",
            confidence=0.9,
        )
        trace = TraceResult(
            trace_id="tr-full",
            event_id="te-full",
            paths=(path,),
            total_paths_found=1,
            max_depth_reached=0,
            timestamp=now_utc,
            query_latency_ms=1.0,
        )
        chain = CorrelationChain(
            event_id="te-full",
            agent_id="agent",
            trace_result=trace,
        )
        d = chain.to_dict()
        assert d["trace_result"] is not None
        assert d["trace_result"]["trace_id"] == "tr-full"


# =========================================================================
# CorrelationResult Tests
# =========================================================================


class TestCorrelationResult:
    """Tests for the CorrelationResult frozen dataclass."""

    def test_create(self, now_utc: datetime):
        """Test creating a CorrelationResult."""
        result = CorrelationResult(
            correlation_id="cr-test001",
            chains=(),
            total_events_processed=10,
            events_correlated=7,
            events_with_remediation=3,
            timestamp=now_utc,
            latency_ms=45.6,
        )
        assert result.correlation_id == "cr-test001"
        assert result.total_events_processed == 10
        assert result.events_correlated == 7
        assert result.events_with_remediation == 3

    def test_frozen_immutability(self, now_utc: datetime):
        """Test that CorrelationResult fields cannot be mutated."""
        result = CorrelationResult(
            correlation_id="cr-frozen",
            chains=(),
            total_events_processed=0,
            events_correlated=0,
            events_with_remediation=0,
            timestamp=now_utc,
            latency_ms=0.0,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.correlation_id = "cr-mutated"  # type: ignore[misc]

    def test_correlation_rate(self, now_utc: datetime):
        """Test correlation_rate computes events_correlated / total."""
        result = CorrelationResult(
            correlation_id="cr-rate",
            chains=(),
            total_events_processed=10,
            events_correlated=7,
            events_with_remediation=0,
            timestamp=now_utc,
            latency_ms=0.0,
        )
        assert result.correlation_rate == 0.7

    def test_correlation_rate_zero_division(self, now_utc: datetime):
        """Test correlation_rate returns 0.0 when total_events_processed is 0."""
        result = CorrelationResult(
            correlation_id="cr-zero",
            chains=(),
            total_events_processed=0,
            events_correlated=0,
            events_with_remediation=0,
            timestamp=now_utc,
            latency_ms=0.0,
        )
        assert result.correlation_rate == 0.0

    def test_remediation_rate(self, now_utc: datetime):
        """Test remediation_rate computes with_remediation / correlated."""
        result = CorrelationResult(
            correlation_id="cr-rem",
            chains=(),
            total_events_processed=10,
            events_correlated=8,
            events_with_remediation=4,
            timestamp=now_utc,
            latency_ms=0.0,
        )
        assert result.remediation_rate == 0.5

    def test_remediation_rate_zero_division(self, now_utc: datetime):
        """Test remediation_rate returns 0.0 when events_correlated is 0."""
        result = CorrelationResult(
            correlation_id="cr-remzero",
            chains=(),
            total_events_processed=5,
            events_correlated=0,
            events_with_remediation=0,
            timestamp=now_utc,
            latency_ms=0.0,
        )
        assert result.remediation_rate == 0.0

    def test_to_dict_serialization(self, now_utc: datetime):
        """Test to_dict produces expected keys and values."""
        result = CorrelationResult(
            correlation_id="cr-ser",
            chains=(),
            total_events_processed=10,
            events_correlated=6,
            events_with_remediation=2,
            timestamp=now_utc,
            latency_ms=12.345,
        )
        d = result.to_dict()
        assert d["correlation_id"] == "cr-ser"
        assert d["chains"] == []
        assert d["total_events_processed"] == 10
        assert d["events_correlated"] == 6
        assert d["events_with_remediation"] == 2
        assert d["correlation_rate"] == 0.6
        assert d["remediation_rate"] == round(2 / 6, 4)
        assert d["timestamp"] == now_utc.isoformat()
        assert d["latency_ms"] == 12.345


# =========================================================================
# correlate_event Tests
# =========================================================================


class TestCorrelateEvent:
    """Tests for RuntimeCodeCorrelator.correlate_event."""

    async def test_basic_correlation(self, correlator: RuntimeCodeCorrelator):
        """Test basic correlation returns a CorrelationChain with trace."""
        chain = await correlator.correlate_event(
            event_id="te-basic",
            agent_id="coder-agent",
            tool_name="write_file",
        )
        assert isinstance(chain, CorrelationChain)
        assert chain.event_id == "te-basic"
        assert chain.agent_id == "coder-agent"
        assert chain.trace_result is not None
        assert chain.trace_result.has_source is True

    async def test_correlation_with_anomaly(self, correlator: RuntimeCodeCorrelator):
        """Test that anomaly_description triggers vector search."""
        chain = await correlator.correlate_event(
            event_id="te-anomaly",
            agent_id="coder-agent",
            tool_name="write_file",
            anomaly_description="sql injection query concatenation string",
        )
        assert chain.match_result is not None
        assert chain.match_result.has_matches is True

    async def test_full_chain_with_auto_remediate(
        self, correlator: RuntimeCodeCorrelator
    ):
        """Test full chain: trace + match + remediation with auto_remediate=True."""
        chain = await correlator.correlate_event(
            event_id="te-full",
            agent_id="coder-agent",
            tool_name="write_file",
            anomaly_description="sql injection query concatenation string",
        )
        assert chain.has_trace is True
        assert chain.has_match is True
        assert chain.has_remediation is True
        assert chain.is_complete is True
        assert chain.remediation_plan is not None
        assert chain.remediation_plan.status == RemediationStatus.PATCH_GENERATED

    async def test_no_trace_unknown_agent(self, correlator: RuntimeCodeCorrelator):
        """Test that unknown agent produces chain without source trace."""
        chain = await correlator.correlate_event(
            event_id="te-unknown",
            agent_id="unknown-agent",
            anomaly_description="sql injection query concatenation string",
        )
        # trace_result exists but has_source is False (no mock paths for unknown-agent)
        assert chain.trace_result is not None
        assert chain.has_trace is False

    async def test_no_anomaly_skips_vector_search(
        self, correlator: RuntimeCodeCorrelator
    ):
        """Test that empty anomaly_description means no vector search."""
        chain = await correlator.correlate_event(
            event_id="te-no-desc",
            agent_id="coder-agent",
            tool_name="write_file",
            anomaly_description="",
        )
        assert chain.match_result is None

    async def test_stored_in_chains(self, correlator: RuntimeCodeCorrelator):
        """Test that the chain is appended to the internal _chains list."""
        assert correlator.total_correlations == 0
        await correlator.correlate_event(
            event_id="te-stored",
            agent_id="coder-agent",
        )
        assert correlator.total_correlations == 1

    async def test_auto_remediate_override_false(
        self, correlator: RuntimeCodeCorrelator
    ):
        """Test that auto_remediate=False override prevents remediation."""
        chain = await correlator.correlate_event(
            event_id="te-no-auto",
            agent_id="coder-agent",
            tool_name="write_file",
            anomaly_description="sql injection query concatenation string",
            auto_remediate=False,
        )
        assert chain.has_trace is True
        assert chain.has_match is True
        assert chain.has_remediation is False

    async def test_no_remediation_without_match(
        self, correlator: RuntimeCodeCorrelator
    ):
        """Test that no remediation is generated when there are no matches."""
        chain = await correlator.correlate_event(
            event_id="te-nomatch",
            agent_id="coder-agent",
            tool_name="write_file",
            anomaly_description="completely unrelated gardening topic",
        )
        assert chain.has_trace is True
        assert chain.has_match is False
        assert chain.has_remediation is False


# =========================================================================
# correlate_batch Tests
# =========================================================================


class TestCorrelateBatch:
    """Tests for RuntimeCodeCorrelator.correlate_batch."""

    async def test_batch_processes_multiple_events(
        self, correlator: RuntimeCodeCorrelator
    ):
        """Test that correlate_batch processes all events."""
        events = [
            {
                "event_id": "te-batch1",
                "agent_id": "coder-agent",
                "tool_name": "write_file",
                "description": "sql injection query concatenation string",
            },
            {
                "event_id": "te-batch2",
                "agent_id": "unknown-agent",
                "description": "",
            },
            {
                "event_id": "te-batch3",
                "agent_id": "coder-agent",
                "tool_name": "write_file",
                "description": "",
            },
        ]
        result = await correlator.correlate_batch(events)
        assert isinstance(result, CorrelationResult)
        assert result.total_events_processed == 3
        assert len(result.chains) == 3

    async def test_batch_correct_counts(self, correlator: RuntimeCodeCorrelator):
        """Test that batch result has correct correlated and remediation counts."""
        events = [
            {
                "event_id": "te-cnt1",
                "agent_id": "coder-agent",
                "tool_name": "write_file",
                "description": "sql injection query concatenation string",
            },
            {
                "event_id": "te-cnt2",
                "agent_id": "unknown-agent",
                "description": "sql injection query concatenation string",
            },
        ]
        result = await correlator.correlate_batch(events)
        assert result.total_events_processed == 2
        # coder-agent has mock paths (correlated), unknown does not
        assert result.events_correlated == 1
        # Only the coder-agent event has trace + match -> remediation
        assert result.events_with_remediation == 1

    async def test_batch_latency_positive(self, correlator: RuntimeCodeCorrelator):
        """Test that batch latency_ms is positive."""
        events = [
            {
                "event_id": "te-lat1",
                "agent_id": "coder-agent",
                "description": "",
            },
        ]
        result = await correlator.correlate_batch(events)
        assert result.latency_ms > 0

    async def test_batch_empty_events(self, correlator: RuntimeCodeCorrelator):
        """Test batch with empty events list."""
        result = await correlator.correlate_batch([])
        assert result.total_events_processed == 0
        assert len(result.chains) == 0
        assert result.correlation_rate == 0.0


# =========================================================================
# Correlator Properties Tests
# =========================================================================


class TestCorrelatorProperties:
    """Tests for RuntimeCodeCorrelator property accessors."""

    async def test_total_correlations(self, correlator: RuntimeCodeCorrelator):
        """Test total_correlations increments with each correlation."""
        assert correlator.total_correlations == 0
        await correlator.correlate_event(
            event_id="te-prop1",
            agent_id="coder-agent",
        )
        assert correlator.total_correlations == 1
        await correlator.correlate_event(
            event_id="te-prop2",
            agent_id="coder-agent",
        )
        assert correlator.total_correlations == 2

    async def test_complete_count(self, correlator: RuntimeCodeCorrelator):
        """Test complete_count only includes fully complete chains."""
        # Complete chain (trace + match + remediation)
        await correlator.correlate_event(
            event_id="te-comp1",
            agent_id="coder-agent",
            tool_name="write_file",
            anomaly_description="sql injection query concatenation string",
        )
        # Incomplete chain (no anomaly -> no match -> no remediation)
        await correlator.correlate_event(
            event_id="te-comp2",
            agent_id="coder-agent",
        )
        assert correlator.total_correlations == 2
        assert correlator.complete_count == 1

    async def test_get_all_chains(self, correlator: RuntimeCodeCorrelator):
        """Test get_all_chains returns all stored chains."""
        await correlator.correlate_event(
            event_id="te-all1",
            agent_id="coder-agent",
        )
        await correlator.correlate_event(
            event_id="te-all2",
            agent_id="coder-agent",
        )
        chains = correlator.get_all_chains()
        assert len(chains) == 2
        event_ids = {c.event_id for c in chains}
        assert "te-all1" in event_ids
        assert "te-all2" in event_ids

    async def test_get_complete_chains(self, correlator: RuntimeCodeCorrelator):
        """Test get_complete_chains returns only fully complete chains."""
        # Complete chain
        await correlator.correlate_event(
            event_id="te-gc1",
            agent_id="coder-agent",
            tool_name="write_file",
            anomaly_description="sql injection query concatenation string",
        )
        # Incomplete chain
        await correlator.correlate_event(
            event_id="te-gc2",
            agent_id="unknown-agent",
        )
        complete = correlator.get_complete_chains()
        assert len(complete) == 1
        assert complete[0].event_id == "te-gc1"


# =========================================================================
# Singleton Tests
# =========================================================================


class TestSingleton:
    """Tests for the correlator singleton lifecycle."""

    def test_get_code_correlator_same_instance(self):
        """Test that get_code_correlator returns the same instance."""
        c1 = get_code_correlator()
        c2 = get_code_correlator()
        assert c1 is c2

    def test_reset_code_correlator_creates_new(self):
        """Test that reset_code_correlator creates a new instance."""
        c1 = get_code_correlator()
        reset_code_correlator()
        c2 = get_code_correlator()
        assert c1 is not c2

    def test_get_code_correlator_returns_correlator(self):
        """Test that get_code_correlator returns a RuntimeCodeCorrelator."""
        c = get_code_correlator()
        assert isinstance(c, RuntimeCodeCorrelator)

    def test_reset_clears_state(self):
        """Test that reset clears the singleton so a fresh one is created."""
        c1 = get_code_correlator()
        reset_code_correlator()
        c2 = get_code_correlator()
        # New instance should have zero correlations
        assert c2.total_correlations == 0
