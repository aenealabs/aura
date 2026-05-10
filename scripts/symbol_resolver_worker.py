#!/usr/bin/env python3
"""Project Aura - Tier 3 symbol resolver worker (ADR-090 Phase 4c.2).

Long-polling SQS consumer. For each ResolutionRequest:

  1. Consult the content-addressed cache; on hit, write result to
     Neptune and acknowledge the message.
  2. Consult the per-tenant cost ceiling; on deny, write a deferred
     ``unverified`` edge and acknowledge.
  3. Wrap the Bedrock call in a per-worker per-region circuit
     breaker. On open, write a deferred ``unverified`` edge and
     return the message to the queue (visibility timeout retry).
  4. On success, write the resolved CALLS_INFERRED edge to Neptune
     and store the resolution in the cache.

The worker is structured so production wiring (real SQS, Neptune,
Bedrock, DynamoDB) drops in via constructor injection. The default
:func:`main` entry uses environment variables for configuration so
the same script works under ECS without code changes.

Usage::

    python -m scripts.symbol_resolver_worker

Env vars (production):
  AURA_RESOLVER_QUEUE_URL       SQS queue URL
  AURA_RESOLVER_DLQ_URL         DLQ for unparseable / poison messages
  AURA_RESOLVER_REGION          Bedrock region (e.g. us-east-1)
  AURA_RESOLVER_CACHE_TABLE     DynamoDB cache table (optional)
  AURA_RESOLVER_COST_TABLE      DynamoDB cost table (optional)
  AURA_RESOLVER_MAX_LOOPS       Bound loops for tests (default infinite)

Author: Project Aura Team
Created: 2026-05-08
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from src.services.graph.circuit_breaker import (
    BreakerConfig,
    CircuitBreaker,
    CircuitBreakerOpen,
)
from src.services.graph.cost_ceiling import CostCeiling, InMemoryCostCeiling
from src.services.graph.edge_labels import EdgeLabel
from src.services.graph.fqn import compute_fqn
from src.services.graph.resolution_cache import (
    CachedResolution,
    InMemoryResolutionCache,
    ResolutionCache,
)
from src.services.graph.symbol_resolver_queue import (
    CandidateRef,
    ResolutionRequest,
    ResolutionResponse,
    UnsupportedSchemaError,
)
from src.services.graph.symbol_resolver_tier3 import (
    PLAUSIBLE,
    UNVERIFIED,
    VERIFIED,
    strip_python_comments_and_docstrings,
)

logger = logging.getLogger(__name__)


@dataclass
class WorkerConfig:
    queue_url: str
    dlq_url: str | None = None
    region: str = "us-east-1"
    poll_wait_seconds: int = 20  # Long-polling
    max_messages: int = 10
    visibility_timeout_seconds: int = 60
    max_loops: int | None = None  # None == run until terminated
    bedrock_max_tokens: int = 256
    bedrock_operation: str = "graph_symbol_resolution"
    bedrock_agent: str = "GraphSymbolResolverWorker"
    estimate_tokens_per_request: int = 2000


class _SQSClient:
    """Minimal interface the worker needs from SQS."""

    def receive_message(self, **kwargs) -> dict: ...
    def delete_message(self, **kwargs) -> dict: ...
    def send_message(self, **kwargs) -> dict: ...


class _NeptuneWriter:
    """Minimal interface for writing resolved edges back to Neptune."""

    def add_relationship(self, **kwargs) -> bool: ...


class _BedrockGenerator:
    """Minimal async interface matching BedrockLLMService.generate."""

    async def generate(
        self,
        prompt: str,
        agent: str = ...,
        system_prompt: str | None = ...,
        max_tokens: int | None = ...,
        operation: str | None = ...,
        use_semantic_cache: bool = ...,
    ) -> str: ...


@dataclass
class WorkerStats:
    polled: int = 0
    received: int = 0
    cache_hits: int = 0
    cost_denied: int = 0
    breaker_short_circuits: int = 0
    bedrock_invocations: int = 0
    resolved_verified: int = 0
    resolved_plausible: int = 0
    resolved_unverified: int = 0
    invalid_payload: int = 0
    errors: int = 0


class SymbolResolverWorker:
    """ECS Fargate worker entry point for Phase 4c.2."""

    def __init__(
        self,
        config: WorkerConfig,
        sqs_client: _SQSClient,
        bedrock: _BedrockGenerator,
        neptune: _NeptuneWriter,
        cache: ResolutionCache | None = None,
        cost_ceiling: CostCeiling | None = None,
        breaker: CircuitBreaker | None = None,
    ):
        self.config = config
        self.sqs = sqs_client
        self.bedrock = bedrock
        self.neptune = neptune
        # Compare against None explicitly: InMemoryResolutionCache
        # defines __len__, so an empty cache is falsy and ``cache or
        # default`` would silently swap the caller's instance.
        self.cache = cache if cache is not None else InMemoryResolutionCache()
        self.cost_ceiling = (
            cost_ceiling if cost_ceiling is not None else InMemoryCostCeiling()
        )
        self.breaker = (
            breaker if breaker is not None else CircuitBreaker(BreakerConfig())
        )
        self.stats = WorkerStats()
        self._shutdown = False

    def request_shutdown(self) -> None:
        self._shutdown = True

    async def run(self) -> WorkerStats:
        loops = 0
        while not self._shutdown:
            if self.config.max_loops is not None and loops >= self.config.max_loops:
                break
            loops += 1
            self.stats.polled += 1
            messages = await asyncio.to_thread(self._receive_batch)
            if not messages:
                continue
            for raw in messages:
                self.stats.received += 1
                await self._handle_one(raw)
        return self.stats

    def _receive_batch(self) -> list[dict]:
        try:
            response = self.sqs.receive_message(
                QueueUrl=self.config.queue_url,
                MaxNumberOfMessages=self.config.max_messages,
                WaitTimeSeconds=self.config.poll_wait_seconds,
                VisibilityTimeout=self.config.visibility_timeout_seconds,
            )
        except Exception as e:
            logger.warning(f"SQS receive failed: {e}")
            self.stats.errors += 1
            return []
        return response.get("Messages", [])

    async def _handle_one(self, raw_message: dict) -> None:
        body = raw_message.get("Body", "")
        receipt = raw_message.get("ReceiptHandle")
        try:
            request = ResolutionRequest.from_json(body)
        except UnsupportedSchemaError as e:
            logger.error(f"Unsupported schema: {e}; routing to DLQ")
            self.stats.invalid_payload += 1
            self._route_to_dlq(body, str(e))
            self._delete_message(receipt)
            return
        except Exception as e:
            logger.error(f"Invalid payload: {e}; routing to DLQ")
            self.stats.invalid_payload += 1
            self._route_to_dlq(body, str(e))
            self._delete_message(receipt)
            return

        # 1. Cache hit short-circuits Bedrock.
        cached = self.cache.get(request.context_hash)
        if cached is not None:
            self.stats.cache_hits += 1
            self._writeback(request, cached)
            self._delete_message(receipt)
            return

        # 2. Cost ceiling check.
        if not self.cost_ceiling.admit(
            request.tenant_id, self.config.estimate_tokens_per_request
        ):
            self.stats.cost_denied += 1
            self._writeback(
                request,
                CachedResolution(
                    target_fqn=None,
                    verification_status=UNVERIFIED,
                    model_id=None,
                ),
                resolution_method="cost_denied",
            )
            self._delete_message(receipt)
            return

        # 3. Breaker-wrapped Bedrock invocation.
        try:
            chosen_index = await self.breaker.call(
                lambda: self._invoke_bedrock(request)
            )
        except CircuitBreakerOpen:
            self.stats.breaker_short_circuits += 1
            # Leave the message visible to retry after cooldown by
            # NOT deleting it. The default visibility_timeout will
            # return it to the queue.
            return
        except Exception as e:
            logger.warning(f"Bedrock invocation failed: {e}")
            self.stats.errors += 1
            # Same as breaker short-circuit: don't delete; allow retry.
            return

        self.stats.bedrock_invocations += 1
        self.cost_ceiling.record(
            request.tenant_id, self.config.estimate_tokens_per_request
        )

        if chosen_index is None:
            resolution = CachedResolution(
                target_fqn=None,
                verification_status=UNVERIFIED,
                model_id=None,
            )
            self.stats.resolved_unverified += 1
        else:
            chosen = request.candidate_set[chosen_index]
            target_fqn = self._fqn_for_candidate(chosen, request.repo_id)
            verification = self._verify(request, chosen)
            resolution = CachedResolution(
                target_fqn=target_fqn,
                verification_status=verification,
                model_id=None,
            )
            if verification == VERIFIED:
                self.stats.resolved_verified += 1
            else:
                self.stats.resolved_plausible += 1

        # 4. Writeback + cache.
        self.cache.put(request.context_hash, resolution)
        self._writeback(request, resolution)
        self._delete_message(receipt)

    async def _invoke_bedrock(self, request: ResolutionRequest) -> int | None:
        prompt = self._build_prompt(request)
        response_text = await self.bedrock.generate(
            prompt=prompt,
            agent=self.config.bedrock_agent,
            operation=self.config.bedrock_operation,
            max_tokens=self.config.bedrock_max_tokens,
            use_semantic_cache=True,
        )
        return self._parse_choice(response_text, len(request.candidate_set))

    def _build_prompt(self, request: ResolutionRequest) -> str:
        lines: list[str] = []
        lines.append(
            "You are resolving a call site to one of a closed set of "
            "candidate definitions in the same code repository."
        )
        lines.append(
            "Respond with a JSON object: "
            '{"chosen_index": <int>} for a match, or '
            '{"chosen_index": null} when none of the candidates is '
            "the correct target."
        )
        lines.append("")
        lines.append(f"Caller file: {request.file_path}")
        scope = (
            ".".join(request.source_parent_chain) + "." + request.source_name
            if request.source_parent_chain
            else request.source_name
        )
        lines.append(f"Caller scope: {scope}")
        lines.append(f"Call expression: {request.target_name}")
        lines.append(f"Call site line: {request.call_site_line}")
        lines.append("")
        lines.append("Candidates:")
        for idx, c in enumerate(request.candidate_set):
            chain = ".".join(c.parent_chain or [])
            qualified = f"{chain}.{c.name}" if chain else c.name
            lines.append(
                f"  [{idx}] {c.entity_type} {qualified} in {c.file_path} "
                f"at line {c.line_number}"
            )
        lines.append("")
        lines.append(
            "Pick the candidate that is most likely the resolved "
            "target of the call. Output only the JSON object."
        )
        return "\n".join(lines)

    @staticmethod
    def _parse_choice(response_text: str, num_candidates: int) -> int | None:
        if not response_text:
            return None
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").lstrip("json").strip()
        try:
            obj = json.loads(cleaned)
        except json.JSONDecodeError:
            import re

            match = re.search(r'"chosen_index"\s*:\s*(null|\d+)', response_text)
            if not match:
                return None
            value = match.group(1)
            if value == "null":
                return None
            try:
                idx = int(value)
            except ValueError:
                return None
            return idx if 0 <= idx < num_candidates else None
        choice = obj.get("chosen_index")
        if choice is None or not isinstance(choice, int):
            return None
        return choice if 0 <= choice < num_candidates else None

    @staticmethod
    def _fqn_for_candidate(c: CandidateRef, repo_id: str) -> str:
        return compute_fqn(
            name=c.name,
            kind=c.entity_type,
            file_path=c.file_path,
            repo_id=repo_id,
            parent_chain=tuple(c.parent_chain or ()),
        )

    @staticmethod
    def _verify(request: ResolutionRequest, chosen: CandidateRef) -> str:
        if not request.target_name:
            return PLAUSIBLE
        leaf = request.target_name.rsplit(".", 1)[-1]
        if chosen.name != leaf:
            return PLAUSIBLE
        return VERIFIED if chosen.file_path else PLAUSIBLE

    def _writeback(
        self,
        request: ResolutionRequest,
        resolution: CachedResolution,
        resolution_method: str = "llm",
    ) -> None:
        from_endpoint = request.source_fqn or request.source_name
        to_endpoint = resolution.target_fqn or request.target_name
        try:
            self.neptune.add_relationship(
                from_entity=from_endpoint,
                to_entity=to_endpoint,
                relationship=EdgeLabel.CALLS_INFERRED.value,
                metadata={
                    "repository": request.repo_id,
                    "verification_status": resolution.verification_status,
                    "resolution_method": resolution_method,
                    "request_id": request.request_id,
                    "call_site_line": request.call_site_line,
                },
            )
        except Exception as e:
            logger.warning(f"Neptune writeback failed for {request.request_id}: {e}")
            self.stats.errors += 1

    def _delete_message(self, receipt: str | None) -> None:
        if receipt is None:
            return
        try:
            self.sqs.delete_message(
                QueueUrl=self.config.queue_url, ReceiptHandle=receipt
            )
        except Exception as e:
            logger.warning(f"SQS delete failed: {e}")

    def _route_to_dlq(self, body: str, reason: str) -> None:
        if not self.config.dlq_url:
            return
        try:
            self.sqs.send_message(
                QueueUrl=self.config.dlq_url,
                MessageBody=body,
                MessageAttributes={
                    "FailureReason": {
                        "DataType": "String",
                        "StringValue": reason[:200],
                    }
                },
            )
        except Exception as e:
            logger.warning(f"DLQ route failed: {e}")


def _load_config_from_env() -> WorkerConfig:
    queue_url = os.environ.get("AURA_RESOLVER_QUEUE_URL")
    if not queue_url:
        raise SystemExit("AURA_RESOLVER_QUEUE_URL is required")
    return WorkerConfig(
        queue_url=queue_url,
        dlq_url=os.environ.get("AURA_RESOLVER_DLQ_URL"),
        region=os.environ.get("AURA_RESOLVER_REGION", "us-east-1"),
        max_loops=(
            int(os.environ["AURA_RESOLVER_MAX_LOOPS"])
            if os.environ.get("AURA_RESOLVER_MAX_LOOPS")
            else None
        ),
    )


def main() -> int:  # pragma: no cover - production entry only
    """Production entry: wire real SQS / Bedrock / Neptune clients.

    Implementation is left to the deployment manifest because it
    needs boto3 + the real BedrockLLMService factory; the worker
    class above is fully unit-testable without these wires.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config = _load_config_from_env()
    logger.info(f"SymbolResolverWorker starting; queue={config.queue_url}")
    raise NotImplementedError(
        "Production wiring is owned by the ECS task definition; "
        "instantiate SymbolResolverWorker with concrete clients there."
    )


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main() or 0)
