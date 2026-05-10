"""Tests for ADR-090 Phase 4c.2 distributed Tier 3 resolver components."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import pytest

from src.agents.ast_parser_agent import CodeEntity, CodeRelationship
from src.services.graph.circuit_breaker import (
    BreakerConfig,
    BreakerState,
    CircuitBreaker,
    CircuitBreakerOpen,
)
from src.services.graph.cost_ceiling import CeilingConfig, InMemoryCostCeiling
from src.services.graph.edge_labels import EdgeLabel
from src.services.graph.resolution_cache import (
    CachedResolution,
    InMemoryResolutionCache,
)
from src.services.graph.symbol_resolver_queue import (
    CandidateRef,
    ResolutionRequest,
    ResolutionResponse,
    UnsupportedSchemaError,
    compute_context_hash,
)
from src.services.graph.symbol_resolver_tier3 import (
    UNVERIFIED,
    Tier3LLMResolver,
    Tier3Stats,
)

# -- Helpers ----------------------------------------------------------


def _entity(name, kind, file_path, line=1, parent_chain=()):
    return CodeEntity(
        name=name,
        entity_type=kind,
        file_path=file_path,
        line_number=line,
        parent_chain=parent_chain,
    )


def _calls(source, target, file_path, line=1, parent_chain=()):
    return CodeRelationship(
        source_name=source,
        source_parent_chain=parent_chain,
        target_name=target,
        relationship=EdgeLabel.CALLS.value,
        properties={"call_site_line": line},
        file_path=file_path,
    )


# -- ResolutionRequest contract --------------------------------------


class TestResolutionRequestContract:
    def test_round_trip_json(self):
        request = ResolutionRequest(
            request_id="req-1",
            tenant_id="tenant-a",
            repo_id="org/repo",
            source_fqn=None,
            source_name="main",
            source_parent_chain=[],
            file_path="myapp/runner.py",
            target_name="helper",
            call_site_line=5,
            candidate_set=[
                CandidateRef(
                    name="helper",
                    entity_type="function",
                    file_path="myapp/utils.py",
                    line_number=10,
                )
            ],
            snippet_hash="abc123",
            context_hash="hash-1",
        )
        encoded = request.to_json()
        decoded = ResolutionRequest.from_json(encoded)
        assert decoded == request

    def test_unknown_schema_raises(self):
        payload = json.dumps(
            {
                "request_id": "req-1",
                "tenant_id": "t",
                "repo_id": "r",
                "source_fqn": None,
                "source_name": "x",
                "source_parent_chain": [],
                "file_path": "x.py",
                "target_name": "y",
                "call_site_line": 1,
                "candidate_set": [],
                "snippet_hash": None,
                "context_hash": "h",
                "schema_version": 999,
            }
        )
        with pytest.raises(UnsupportedSchemaError):
            ResolutionRequest.from_json(payload)

    def test_build_from_relationship_and_candidates(self):
        rel = _calls("main", "helper", "myapp/runner.py", line=7)
        candidates = [_entity("helper", "function", "myapp/utils.py", line=12)]
        request = ResolutionRequest.build(
            request_id="req-1",
            tenant_id="t",
            repo_id="org/repo",
            relationship=rel,
            candidates=candidates,
            snippet_hash="snip-hash",
        )
        assert request.target_name == "helper"
        assert request.call_site_line == 7
        assert len(request.candidate_set) == 1
        assert request.candidate_set[0].file_path == "myapp/utils.py"
        # Context hash is deterministic given the inputs.
        assert request.context_hash == compute_context_hash(
            file_path="myapp/runner.py",
            call_site_line=7,
            target_name="helper",
            candidates=request.candidate_set,
            snippet_hash="snip-hash",
        )


# -- ResolutionResponse contract --------------------------------------


class TestResolutionResponseContract:
    def test_round_trip(self):
        resp = ResolutionResponse(
            request_id="req-1",
            repo_id="org/repo",
            target_fqn="python:org/repo:x:y#function",
            verification_status="verified",
            resolution_method="llm",
            model_id="claude-haiku-4-5",
            prompt_hash="ph",
        )
        round_tripped = ResolutionResponse.from_json(resp.to_json())
        assert round_tripped == resp


# -- Queue producer in Tier 3 -----------------------------------------


class _RecordingPublisher:
    def __init__(self, raises: bool = False):
        self.published: list[ResolutionRequest] = []
        self.raises = raises

    def publish(self, request: ResolutionRequest) -> None:
        if self.raises:
            raise RuntimeError("publish failure")
        self.published.append(request)


class TestQueueProducer:
    def test_queue_mode_skips_inline_bedrock(self):
        publisher = _RecordingPublisher()
        resolver = Tier3LLMResolver(publisher=publisher, tenant_id="tenant-a")

        entities = [
            _entity("helper", "function", "myapp/utils.py"),
            _entity("main", "function", "myapp/runner.py"),
        ]
        relationships = [_calls("main", "helper", "myapp/runner.py")]

        out, stats = asyncio.run(resolver.resolve(entities, relationships, "org/repo"))

        assert resolver.queue_mode is True
        assert stats.published_to_queue == 1
        assert stats.llm_invoked == 0
        # Placeholder edge emitted with CALLS_INFERRED + unverified.
        assert out[0].relationship == EdgeLabel.CALLS_INFERRED.value
        assert out[0].properties["verification_status"] == UNVERIFIED
        # Published payload is a fully-formed ResolutionRequest.
        published = publisher.published[0]
        assert published.tenant_id == "tenant-a"
        assert published.target_name == "helper"

    def test_publish_failure_counted_and_does_not_raise(self):
        publisher = _RecordingPublisher(raises=True)
        resolver = Tier3LLMResolver(publisher=publisher)

        entities = [
            _entity("helper", "function", "myapp/utils.py"),
            _entity("main", "function", "myapp/runner.py"),
        ]
        relationships = [_calls("main", "helper", "myapp/runner.py")]
        out, stats = asyncio.run(resolver.resolve(entities, relationships, "org/repo"))

        assert stats.publish_failed == 1
        assert stats.published_to_queue == 0
        # Even on failure, ingestion gets a placeholder edge.
        assert out[0].relationship == EdgeLabel.CALLS_INFERRED.value


# -- Circuit breaker ---------------------------------------------------


class TestCircuitBreaker:
    def test_closed_call_passes_through(self):
        cb = CircuitBreaker(BreakerConfig(min_samples=1))

        async def op():
            return 42

        assert asyncio.run(cb.call(op)) == 42
        assert cb.state == BreakerState.CLOSED

    def test_failure_rate_trips_breaker(self):
        cb = CircuitBreaker(
            BreakerConfig(
                min_samples=4,
                failure_rate_threshold=0.5,
                cooldown_seconds=10,
            )
        )

        async def fail():
            raise RuntimeError("bedrock down")

        for _ in range(4):
            with pytest.raises(RuntimeError):
                asyncio.run(cb.call(fail))
        assert cb.state == BreakerState.OPEN

        async def ok():
            return 1

        with pytest.raises(CircuitBreakerOpen):
            asyncio.run(cb.call(ok))

    def test_cooldown_transitions_to_half_open(self):
        clock = [100.0]
        cb = CircuitBreaker(
            BreakerConfig(
                min_samples=2, failure_rate_threshold=0.5, cooldown_seconds=5
            ),
            clock=lambda: clock[0],
        )

        async def fail():
            raise RuntimeError("x")

        for _ in range(2):
            with pytest.raises(RuntimeError):
                asyncio.run(cb.call(fail))
        assert cb.state == BreakerState.OPEN

        # Advance past cooldown.
        clock[0] += 6.0
        assert cb.state == BreakerState.HALF_OPEN

    def test_half_open_success_closes(self):
        clock = [100.0]
        cb = CircuitBreaker(
            BreakerConfig(
                min_samples=2, failure_rate_threshold=0.5, cooldown_seconds=5
            ),
            clock=lambda: clock[0],
        )

        async def fail():
            raise RuntimeError("x")

        for _ in range(2):
            with pytest.raises(RuntimeError):
                asyncio.run(cb.call(fail))
        clock[0] += 6.0  # cooldown elapsed -> half_open

        async def ok():
            return 1

        result = asyncio.run(cb.call(ok))
        assert result == 1
        assert cb.state == BreakerState.CLOSED

    def test_half_open_failure_reopens_with_backoff(self):
        clock = [100.0]
        cb = CircuitBreaker(
            BreakerConfig(
                min_samples=2,
                failure_rate_threshold=0.5,
                cooldown_seconds=5,
                max_cooldown_seconds=600,
            ),
            clock=lambda: clock[0],
        )

        async def fail():
            raise RuntimeError("x")

        for _ in range(2):
            with pytest.raises(RuntimeError):
                asyncio.run(cb.call(fail))
        clock[0] += 6.0

        with pytest.raises(RuntimeError):
            asyncio.run(cb.call(fail))
        # Re-open with exponential cooldown.
        assert cb.state == BreakerState.OPEN
        # Probe-window time should be roughly 2x base cooldown after second trip.
        # (We cannot read _next_probe_at directly; observe via clock.)
        clock[0] += 6.0  # not yet past doubled cooldown -> still OPEN
        assert cb.state == BreakerState.OPEN


# -- Resolution cache --------------------------------------------------


class TestResolutionCache:
    def test_get_returns_none_for_missing_key(self):
        cache = InMemoryResolutionCache()
        assert cache.get("missing") is None

    def test_put_then_get_round_trip(self):
        cache = InMemoryResolutionCache()
        resolution = CachedResolution(
            target_fqn="python:r:x:y#function",
            verification_status="verified",
            closure_fingerprint="closure-1",
        )
        cache.put("key-1", resolution)
        result = cache.get("key-1")
        assert result is not None
        assert result.target_fqn == "python:r:x:y#function"
        # Timestamp is auto-populated on put.
        assert result.timestamp > 0

    def test_invalidate_closure_drops_matching_entries(self):
        cache = InMemoryResolutionCache()
        cache.put(
            "k1",
            CachedResolution(
                target_fqn="A",
                verification_status="verified",
                closure_fingerprint="closure-1",
            ),
        )
        cache.put(
            "k2",
            CachedResolution(
                target_fqn="B",
                verification_status="verified",
                closure_fingerprint="closure-2",
            ),
        )
        cache.put(
            "k3",
            CachedResolution(
                target_fqn="C",
                verification_status="verified",
                closure_fingerprint="closure-1",
            ),
        )
        dropped = cache.invalidate_closure("closure-1")
        assert dropped == 2
        assert cache.get("k1") is None
        assert cache.get("k3") is None
        assert cache.get("k2") is not None


# -- Cost ceiling ------------------------------------------------------


class TestCostCeiling:
    def test_admit_under_cap(self):
        ceiling = InMemoryCostCeiling(
            CeilingConfig(tokens_per_window=1000, window_seconds=3600)
        )
        assert ceiling.admit("tenant-a", 500) is True

    def test_admit_at_cap(self):
        ceiling = InMemoryCostCeiling(
            CeilingConfig(tokens_per_window=1000, window_seconds=3600)
        )
        ceiling.record("tenant-a", 800)
        assert ceiling.admit("tenant-a", 200) is True
        assert ceiling.admit("tenant-a", 201) is False

    def test_window_rolls_over_after_expiry(self):
        clock = [100.0]
        ceiling = InMemoryCostCeiling(
            CeilingConfig(tokens_per_window=1000, window_seconds=60),
            clock=lambda: clock[0],
        )
        ceiling.record("tenant-a", 1000)
        assert ceiling.admit("tenant-a", 1) is False
        clock[0] += 61
        # Window rolled; full ceiling available again.
        assert ceiling.admit("tenant-a", 500) is True

    def test_per_tenant_isolation(self):
        ceiling = InMemoryCostCeiling(
            CeilingConfig(tokens_per_window=1000, window_seconds=3600)
        )
        ceiling.record("tenant-a", 1000)
        # Tenant A is exhausted; tenant B is unaffected.
        assert ceiling.admit("tenant-a", 1) is False
        assert ceiling.admit("tenant-b", 999) is True


# -- Worker entry ------------------------------------------------------


class _FakeSqs:
    def __init__(self, batches):
        self.batches = list(batches)
        self.deleted: list[str] = []
        self.dlq: list[dict] = []

    def receive_message(self, **kwargs):
        if not self.batches:
            return {"Messages": []}
        return {"Messages": self.batches.pop(0)}

    def delete_message(self, **kwargs):
        self.deleted.append(kwargs.get("ReceiptHandle"))
        return {}

    def send_message(self, **kwargs):
        self.dlq.append(kwargs)
        return {}


class _FakeNeptune:
    def __init__(self):
        self.calls: list[dict] = []

    def add_relationship(self, **kwargs):
        self.calls.append(kwargs)
        return True


class _FakeBedrock:
    def __init__(self, response_text: str = '{"chosen_index": 0}'):
        self.response_text = response_text
        self.invocations = 0

    async def generate(self, **kwargs):
        self.invocations += 1
        return self.response_text


def _make_request_message(
    target="helper",
    file_path="myapp/runner.py",
    candidate_file="myapp/utils.py",
):
    request = ResolutionRequest(
        request_id="req-x",
        tenant_id="tenant-a",
        repo_id="org/repo",
        source_fqn=None,
        source_name="main",
        source_parent_chain=[],
        file_path=file_path,
        target_name=target,
        call_site_line=7,
        candidate_set=[
            CandidateRef(
                name=target,
                entity_type="function",
                file_path=candidate_file,
                line_number=12,
            )
        ],
        snippet_hash=None,
        context_hash="ctx-1",
    )
    return {"Body": request.to_json(), "ReceiptHandle": "rcpt-1"}


class TestSymbolResolverWorker:
    def test_resolves_writes_to_neptune_and_caches(self):
        from scripts.symbol_resolver_worker import SymbolResolverWorker, WorkerConfig

        sqs = _FakeSqs([[_make_request_message()]])
        neptune = _FakeNeptune()
        bedrock = _FakeBedrock('{"chosen_index": 0}')
        cache = InMemoryResolutionCache()
        worker = SymbolResolverWorker(
            config=WorkerConfig(queue_url="q", max_loops=1),
            sqs_client=sqs,
            bedrock=bedrock,
            neptune=neptune,
            cache=cache,
        )
        stats = asyncio.run(worker.run())
        assert stats.bedrock_invocations == 1
        assert stats.resolved_verified == 1
        # Neptune writeback used CALLS_INFERRED.
        assert neptune.calls[0]["relationship"] == EdgeLabel.CALLS_INFERRED.value
        assert sqs.deleted == ["rcpt-1"]
        # Cache populated.
        cached = cache.get("ctx-1")
        assert cached is not None
        assert cached.target_fqn is not None

    def test_cache_hit_short_circuits_bedrock(self):
        from scripts.symbol_resolver_worker import SymbolResolverWorker, WorkerConfig

        sqs = _FakeSqs([[_make_request_message()]])
        neptune = _FakeNeptune()
        bedrock = _FakeBedrock()
        cache = InMemoryResolutionCache()
        cache.put(
            "ctx-1",
            CachedResolution(
                target_fqn="python:org/repo:x:y#function",
                verification_status="verified",
            ),
        )
        worker = SymbolResolverWorker(
            config=WorkerConfig(queue_url="q", max_loops=1),
            sqs_client=sqs,
            bedrock=bedrock,
            neptune=neptune,
            cache=cache,
        )
        stats = asyncio.run(worker.run())
        assert stats.cache_hits == 1
        assert bedrock.invocations == 0
        assert neptune.calls[0]["to_entity"] == "python:org/repo:x:y#function"

    def test_cost_ceiling_denies_emits_unverified(self):
        from scripts.symbol_resolver_worker import SymbolResolverWorker, WorkerConfig

        sqs = _FakeSqs([[_make_request_message()]])
        neptune = _FakeNeptune()
        bedrock = _FakeBedrock()
        ceiling = InMemoryCostCeiling(
            CeilingConfig(tokens_per_window=1, window_seconds=3600)
        )
        ceiling.record("tenant-a", 100)  # exhaust tenant a
        worker = SymbolResolverWorker(
            config=WorkerConfig(queue_url="q", max_loops=1),
            sqs_client=sqs,
            bedrock=bedrock,
            neptune=neptune,
            cost_ceiling=ceiling,
        )
        stats = asyncio.run(worker.run())
        assert stats.cost_denied == 1
        assert bedrock.invocations == 0
        # Neptune still gets an unverified writeback.
        assert neptune.calls[0]["metadata"]["verification_status"] == UNVERIFIED
        assert neptune.calls[0]["metadata"]["resolution_method"] == "cost_denied"

    def test_breaker_open_skips_delete(self):
        from scripts.symbol_resolver_worker import SymbolResolverWorker, WorkerConfig

        sqs = _FakeSqs([[_make_request_message()]])
        neptune = _FakeNeptune()
        bedrock = _FakeBedrock()
        # Pre-trip the breaker by feeding it failures.
        breaker = CircuitBreaker(
            BreakerConfig(
                min_samples=1,
                failure_rate_threshold=0.1,
                cooldown_seconds=300,
            )
        )

        async def fail():
            raise RuntimeError("x")

        with pytest.raises(RuntimeError):
            asyncio.run(breaker.call(fail))
        assert breaker.state == BreakerState.OPEN

        worker = SymbolResolverWorker(
            config=WorkerConfig(queue_url="q", max_loops=1),
            sqs_client=sqs,
            bedrock=bedrock,
            neptune=neptune,
            breaker=breaker,
        )
        stats = asyncio.run(worker.run())
        assert stats.breaker_short_circuits == 1
        # Message left visible for retry: not deleted.
        assert sqs.deleted == []

    def test_invalid_payload_routes_to_dlq(self):
        from scripts.symbol_resolver_worker import SymbolResolverWorker, WorkerConfig

        bad_message = {"Body": "not-valid-json", "ReceiptHandle": "rcpt-bad"}
        sqs = _FakeSqs([[bad_message]])
        worker = SymbolResolverWorker(
            config=WorkerConfig(queue_url="q", dlq_url="dlq", max_loops=1),
            sqs_client=sqs,
            bedrock=_FakeBedrock(),
            neptune=_FakeNeptune(),
        )
        stats = asyncio.run(worker.run())
        assert stats.invalid_payload == 1
        assert len(sqs.dlq) == 1
        assert sqs.deleted == ["rcpt-bad"]

    def test_max_loops_terminates(self):
        from scripts.symbol_resolver_worker import SymbolResolverWorker, WorkerConfig

        sqs = _FakeSqs([])  # No messages ever.
        worker = SymbolResolverWorker(
            config=WorkerConfig(queue_url="q", max_loops=3),
            sqs_client=sqs,
            bedrock=_FakeBedrock(),
            neptune=_FakeNeptune(),
        )
        stats = asyncio.run(worker.run())
        assert stats.polled == 3
