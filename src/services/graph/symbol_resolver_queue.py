"""SQS queue contracts for the Phase 4c.2 distributed Tier 3 resolver.

Phase 4c.1 ran the LLM stage in-process. Phase 4c.2 keeps the
resolver interface unchanged but moves the LLM invocation onto a
worker pool: the producer (running on the ingest job) writes a
:class:`ResolutionRequest` to SQS for every unresolved CALLS edge,
and a worker (running on ECS Fargate) drains the queue, calls
Bedrock with the same prompt shape, and writes the resolved edge
straight to Neptune.

Two contracts live here:

  - :class:`ResolutionRequest`: the producer-to-worker payload. Every
    field is JSON-serializable so SQS can carry it. The schema is
    versioned via ``schema_version`` so the worker pool can roll
    forward without coordinated producer redeploys.
  - :class:`ResolutionResponse`: the worker-to-result-store payload.
    Used in tests and (optionally) for a results queue if the
    deployment topology requires one; in the default deployment
    workers write directly to Neptune.

Both contracts are deliberately minimal. Anything the worker can
reconstruct from the call-site or candidate set lookup at resolution
time is omitted from the payload to keep messages small and stay
under SQS's 256 KB body limit.

All payload bytes are derived from data the producer already has
post-parse; the worker is stateless and queries Neptune for the
entity index it needs to compute target FQNs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Iterable

from src.agents.ast_parser_agent import CodeEntity, CodeRelationship

# Schema version. Bump when the producer-worker payload changes
# incompatibly. Workers compare the version on receipt and reject
# unknown payloads to a DLQ rather than guessing.
RESOLUTION_REQUEST_SCHEMA_VERSION = 1


@dataclass
class CandidateRef:
    """A single candidate entity surfaced to the LLM.

    Producer constructs these from the per-repo entity index;
    worker uses them to compute target FQNs and present the closed
    set to the model. Equivalent in shape to a slice of CodeEntity
    but JSON-flat.
    """

    name: str
    entity_type: str
    file_path: str
    line_number: int
    parent_chain: list[str] = field(default_factory=list)

    @classmethod
    def from_entity(cls, entity: CodeEntity) -> "CandidateRef":
        return cls(
            name=entity.name,
            entity_type=entity.entity_type,
            file_path=entity.file_path,
            line_number=entity.line_number,
            parent_chain=list(entity.parent_chain or ()),
        )


@dataclass
class ResolutionRequest:
    """SQS payload for a single unresolved CALLS edge.

    Producer fields:
      - request_id: unique per (job, edge); workers use it for
        DLQ correlation and dedup.
      - tenant_id: per-tenant cost ceiling key.
      - repo_id: rendered repo identifier; identifies the Neptune
        scope when writing back the resolved edge.
      - source_fqn / source_name / source_parent_chain / file_path:
        identify the call site for the worker's writeback.
      - target_name: the raw target string the parser emitted.
      - call_site_line: line number of the call expression.
      - candidate_set: closed candidate list assembled by the
        producer; the worker passes this verbatim to the LLM.
      - snippet_hash: hex sha256 of the stripped snippet; the
        worker fetches the snippet from a content-addressed store
        rather than inlining it in the SQS message.
      - schema_version: producer-worker compat marker.
      - context_hash: combined fingerprint of all resolution-
        affecting inputs; used as the content-addressed cache key.
    """

    request_id: str
    tenant_id: str
    repo_id: str
    source_fqn: str | None
    source_name: str
    source_parent_chain: list[str]
    file_path: str
    target_name: str
    call_site_line: int
    candidate_set: list[CandidateRef]
    snippet_hash: str | None
    context_hash: str
    schema_version: int = RESOLUTION_REQUEST_SCHEMA_VERSION

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))

    @classmethod
    def from_json(cls, payload: str) -> "ResolutionRequest":
        data = json.loads(payload)
        if "schema_version" in data and data["schema_version"] not in {
            RESOLUTION_REQUEST_SCHEMA_VERSION,
        }:
            raise UnsupportedSchemaError(
                f"Unsupported schema_version: {data['schema_version']}"
            )
        candidates_raw = data.pop("candidate_set", [])
        candidates = [CandidateRef(**c) for c in candidates_raw]
        return cls(candidate_set=candidates, **data)

    @classmethod
    def build(
        cls,
        *,
        request_id: str,
        tenant_id: str,
        repo_id: str,
        relationship: CodeRelationship,
        candidates: Iterable[CodeEntity],
        snippet_hash: str | None,
    ) -> "ResolutionRequest":
        candidate_refs = [CandidateRef.from_entity(c) for c in candidates]
        line = relationship.properties.get("call_site_line")
        if not isinstance(line, int):
            line = 0
        context_hash = compute_context_hash(
            file_path=relationship.file_path,
            call_site_line=line,
            target_name=relationship.target_name,
            candidates=candidate_refs,
            snippet_hash=snippet_hash,
        )
        return cls(
            request_id=request_id,
            tenant_id=tenant_id,
            repo_id=repo_id,
            source_fqn=relationship.source_fqn,
            source_name=relationship.source_name,
            source_parent_chain=list(relationship.source_parent_chain or ()),
            file_path=relationship.file_path,
            target_name=relationship.target_name or "",
            call_site_line=line,
            candidate_set=candidate_refs,
            snippet_hash=snippet_hash,
            context_hash=context_hash,
        )


@dataclass
class ResolutionResponse:
    """Worker-side resolution result.

    The default deployment topology has the worker write the
    resolved edge to Neptune directly and skip a results queue,
    but the contract is defined here so test harnesses and
    alternative deployments (e.g., async result aggregator) can
    reuse it.
    """

    request_id: str
    repo_id: str
    target_fqn: str | None
    verification_status: str  # verified | plausible | unverified
    resolution_method: str  # llm | secret_blocked | budget_exhausted | invalid
    model_id: str | None = None
    prompt_hash: str | None = None
    error: str | None = None
    schema_version: int = RESOLUTION_REQUEST_SCHEMA_VERSION

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))

    @classmethod
    def from_json(cls, payload: str) -> "ResolutionResponse":
        data = json.loads(payload)
        return cls(**data)


class UnsupportedSchemaError(Exception):
    """Worker received a payload it cannot interpret. Route to DLQ."""


def compute_context_hash(
    *,
    file_path: str,
    call_site_line: int,
    target_name: str,
    candidates: list[CandidateRef],
    snippet_hash: str | None,
) -> str:
    """Deterministic fingerprint of all resolution-affecting inputs.

    The context hash is the cache key used by the content-addressed
    cache (Phase 4c.2.3). Two requests with the same context_hash
    will resolve to the same target as long as the underlying
    candidate set and source snippet have not changed.
    """
    candidate_fingerprint = "|".join(
        f"{c.file_path}:{c.line_number}:{c.entity_type}:{c.name}"
        + (":" + ".".join(c.parent_chain) if c.parent_chain else "")
        for c in candidates
    )
    material = "|".join(
        [
            file_path or "",
            str(call_site_line),
            target_name or "",
            candidate_fingerprint,
            snippet_hash or "no-snippet",
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
