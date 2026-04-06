"""
Project Aura - Runtime-to-Code Correlator

Main correlation engine that orchestrates the detect → trace → fix → verify
closed loop. Uses GraphRAG (Neptune + OpenSearch) to trace runtime security
events back to source code root causes.

Based on ADR-083: Runtime Agent Security Platform
Extended by ADR-086: Self-modification sentinel event subscription

This is the architectural moat: no competitor offers detect → trace → fix.

Compliance:
- NIST 800-53 SI-4: Information system monitoring
- NIST 800-53 IR-4: Incident handling
- NIST 800-53 IR-5: Incident monitoring
- NIST 800-53 CM-5: Access restrictions for change (ADR-086)
"""

import logging
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from .graph_tracer import GraphTracer, TraceResult
from .remediation import RemediationOrchestrator, RemediationPlan
from .vector_matcher import MatchResult, VectorMatcher

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CorrelationChain:
    """Immutable chain showing the full detect → trace → match → fix pipeline."""

    event_id: str
    agent_id: str
    trace_result: Optional[TraceResult] = None
    match_result: Optional[MatchResult] = None
    remediation_plan: Optional[RemediationPlan] = None

    @property
    def has_trace(self) -> bool:
        """True if graph trace found source code."""
        return self.trace_result is not None and self.trace_result.has_source

    @property
    def has_match(self) -> bool:
        """True if vector search found vulnerability patterns."""
        return self.match_result is not None and self.match_result.has_matches

    @property
    def has_remediation(self) -> bool:
        """True if a remediation plan was generated."""
        return self.remediation_plan is not None

    @property
    def is_complete(self) -> bool:
        """True if the full detect → trace → fix chain completed."""
        return self.has_trace and self.has_match and self.has_remediation

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "event_id": self.event_id,
            "agent_id": self.agent_id,
            "has_trace": self.has_trace,
            "has_match": self.has_match,
            "has_remediation": self.has_remediation,
            "is_complete": self.is_complete,
            "trace_result": self.trace_result.to_dict() if self.trace_result else None,
            "match_result": self.match_result.to_dict() if self.match_result else None,
            "remediation_plan": (
                self.remediation_plan.to_dict() if self.remediation_plan else None
            ),
        }


@dataclass(frozen=True)
class CorrelationResult:
    """Immutable result of a full correlation operation."""

    correlation_id: str
    chains: tuple[CorrelationChain, ...]
    total_events_processed: int
    events_correlated: int
    events_with_remediation: int
    timestamp: datetime
    latency_ms: float

    @property
    def correlation_rate(self) -> float:
        """Percentage of events successfully correlated."""
        if self.total_events_processed == 0:
            return 0.0
        return self.events_correlated / self.total_events_processed

    @property
    def remediation_rate(self) -> float:
        """Percentage of correlated events with remediation plans."""
        if self.events_correlated == 0:
            return 0.0
        return self.events_with_remediation / self.events_correlated

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "correlation_id": self.correlation_id,
            "chains": [c.to_dict() for c in self.chains],
            "total_events_processed": self.total_events_processed,
            "events_correlated": self.events_correlated,
            "events_with_remediation": self.events_with_remediation,
            "correlation_rate": round(self.correlation_rate, 4),
            "remediation_rate": round(self.remediation_rate, 4),
            "timestamp": self.timestamp.isoformat(),
            "latency_ms": round(self.latency_ms, 3),
        }


class RuntimeCodeCorrelator:
    """
    Main correlation engine for the detect → trace → fix → verify loop.

    Coordinates graph tracing (Neptune), vector matching (OpenSearch),
    and remediation (Coder agent + HITL) to create a closed-loop
    security response system.

    Usage:
        correlator = RuntimeCodeCorrelator(
            graph_tracer=GraphTracer(),
            vector_matcher=VectorMatcher(),
            remediation=RemediationOrchestrator(),
        )

        # Correlate a single event
        chain = await correlator.correlate_event(
            event_id="te-abc123",
            agent_id="coder-agent",
            tool_name="write_file",
            anomaly_description="Unusual file write pattern",
        )

        if chain.is_complete:
            print(f"Root cause: {chain.trace_result.best_path.source_file}")
            print(f"Patch: {chain.remediation_plan.best_patch.patched_code}")
    """

    def __init__(
        self,
        graph_tracer: Optional[GraphTracer] = None,
        vector_matcher: Optional[VectorMatcher] = None,
        remediation: Optional[RemediationOrchestrator] = None,
        auto_remediate: bool = False,
    ):
        self.tracer = graph_tracer or GraphTracer()
        self.matcher = vector_matcher or VectorMatcher()
        self.remediation = remediation or RemediationOrchestrator()
        self.auto_remediate = auto_remediate

        self._chains: deque[CorrelationChain] = deque(maxlen=10000)
        self._sentinel_correlation_count = 0

    async def correlate_event(
        self,
        event_id: str,
        agent_id: str,
        tool_name: Optional[str] = None,
        anomaly_description: str = "",
        auto_remediate: Optional[bool] = None,
    ) -> CorrelationChain:
        """
        Correlate a single runtime event to source code.

        Steps:
        1. Trace event through Neptune call graph to find source code
        2. Search OpenSearch for matching vulnerability patterns
        3. Generate remediation plan if vulnerability found

        Args:
            event_id: Traffic event ID.
            agent_id: Agent that produced the event.
            tool_name: Optional tool name for narrowing search.
            anomaly_description: Description of the anomalous behavior.
            auto_remediate: Override auto_remediate setting.

        Returns:
            CorrelationChain with trace, match, and remediation results.
        """
        should_remediate = (
            auto_remediate if auto_remediate is not None else self.auto_remediate
        )

        # Step 1: Trace through call graph
        trace_result = await self.tracer.trace_event(
            event_id=event_id,
            agent_id=agent_id,
            tool_name=tool_name,
        )

        # Step 2: Search for vulnerability patterns
        match_result = None
        if anomaly_description:
            match_result = await self.matcher.search(
                query_text=anomaly_description,
            )

        # Step 3: Generate remediation if we have both trace and match
        remediation_plan = None
        if (
            should_remediate
            and trace_result.has_source
            and match_result
            and match_result.has_matches
        ):
            best_path = trace_result.best_path
            best_match = match_result.best_match
            if best_path and best_match:
                remediation_plan = await self.remediation.create_plan(
                    vulnerability_id=best_match.vulnerability_id,
                    correlation_id=event_id,
                    source_file=best_path.source_file or "",
                    line_start=best_path.source_line_start or 0,
                    line_end=best_path.source_line_end or 0,
                    description=best_match.description,
                )

        chain = CorrelationChain(
            event_id=event_id,
            agent_id=agent_id,
            trace_result=trace_result,
            match_result=match_result,
            remediation_plan=remediation_plan,
        )
        self._chains.append(chain)
        return chain

    async def correlate_batch(
        self,
        events: list[dict[str, Any]],
    ) -> CorrelationResult:
        """
        Correlate a batch of events.

        Args:
            events: List of dicts with keys: event_id, agent_id, tool_name, description.

        Returns:
            CorrelationResult with all chains.
        """
        import time

        start = time.monotonic()

        chains = []
        for event in events:
            chain = await self.correlate_event(
                event_id=event.get("event_id", ""),
                agent_id=event.get("agent_id", ""),
                tool_name=event.get("tool_name"),
                anomaly_description=event.get("description", ""),
            )
            chains.append(chain)

        elapsed_ms = (time.monotonic() - start) * 1000
        correlated = sum(1 for c in chains if c.has_trace)
        with_remediation = sum(1 for c in chains if c.has_remediation)

        return CorrelationResult(
            correlation_id=f"cr-{uuid.uuid4().hex[:16]}",
            chains=tuple(chains),
            total_events_processed=len(events),
            events_correlated=correlated,
            events_with_remediation=with_remediation,
            timestamp=datetime.now(timezone.utc),
            latency_ms=elapsed_ms,
        )

    async def correlate_sentinel_alert(
        self,
        alert: Any,
    ) -> CorrelationChain:
        """
        Correlate a self-modification sentinel alert to source code.

        Converts a SentinelAlert (ADR-086 Phase 2) into the standard
        detect → trace → fix pipeline so that self-modification findings
        get traced back to the code that granted the writing capability.

        Args:
            alert: SentinelAlert from the self-modification sentinel.

        Returns:
            CorrelationChain with trace results for the self-modification event.
        """
        self._sentinel_correlation_count += 1

        description = (
            f"Self-modification detected: agent {alert.writer_agent_id} "
            f"{alert.event.action.value}d {alert.event.artifact_class.value} "
            f"'{alert.event.artifact_id}' governing "
            f"{sorted(alert.governed_agent_ids)}"
        )

        chain = await self.correlate_event(
            event_id=alert.event.event_id,
            agent_id=alert.writer_agent_id,
            anomaly_description=description,
            auto_remediate=False,  # Self-mod always requires HITL
        )

        logger.warning(
            f"Sentinel correlation complete: event={alert.event.event_id} "
            f"agent={alert.writer_agent_id} traced={chain.has_trace}"
        )

        return chain

    def register_sentinel_handler(self) -> None:
        """
        Register this correlator as a handler on the global sentinel.

        Connects the self-modification sentinel's CRITICAL alert stream
        to the runtime-to-code correlation pipeline.
        """
        import asyncio

        from ...capability_governance.self_modification_sentinel import (
            get_self_modification_sentinel,
        )

        sentinel = get_self_modification_sentinel()

        def _handle_alert(alert: Any) -> None:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.correlate_sentinel_alert(alert))
            except RuntimeError:
                logger.debug(
                    "No running event loop for sentinel correlation; "
                    "alert will be correlated on next batch."
                )

        sentinel.on_alert(_handle_alert)
        logger.info("Correlator registered as sentinel alert handler")

    @property
    def sentinel_correlation_count(self) -> int:
        """Number of sentinel alerts correlated."""
        return self._sentinel_correlation_count

    def get_all_chains(self) -> list[CorrelationChain]:
        """Get all correlation chains."""
        return list(self._chains)

    def get_complete_chains(self) -> list[CorrelationChain]:
        """Get chains that completed the full detect → trace → fix pipeline."""
        return [c for c in self._chains if c.is_complete]

    @property
    def total_correlations(self) -> int:
        """Total number of correlations performed."""
        return len(self._chains)

    @property
    def complete_count(self) -> int:
        """Number of complete correlation chains."""
        return sum(1 for c in self._chains if c.is_complete)


# Singleton instance
_correlator_instance: Optional[RuntimeCodeCorrelator] = None


def get_code_correlator() -> RuntimeCodeCorrelator:
    """Get singleton correlator instance."""
    global _correlator_instance
    if _correlator_instance is None:
        _correlator_instance = RuntimeCodeCorrelator()
    return _correlator_instance


def reset_code_correlator() -> None:
    """Reset correlator singleton (for testing)."""
    global _correlator_instance
    _correlator_instance = None
