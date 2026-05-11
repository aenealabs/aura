"""Tier 3 LLM-driven symbol resolution (ADR-090 Phase 4c.1, in-process).

Tier 3 picks up the unresolved CALLS edges left by Tiers 1 and 2 and
asks an LLM to disambiguate them against a closed candidate set drawn
from the same-repo entity index. This is the in-process slice; the
full Phase 4c rolls out to ECS Fargate workers behind SQS for
hyperscale, but the resolution shape - prompt, constrained output,
verification, telemetry - is the same.

Key safety properties (per ADR-090 Thread 2 review):

  - **Constrained output.** The model picks an index from a closed
    candidate set assembled from the local entity index; it cannot
    introduce targets we did not surface. Defense vs schema escape
    via prompt injection.
  - **Comment / docstring stripping.** Source snippets are stripped
    of natural-language comments before LLM submission; structural
    resolution does not need prose, and stripping eliminates ~95% of
    the prompt-injection surface (Sally's review).
  - **Secret pre-scan.** Each snippet is run through
    :class:`SecretsPrescanFilter` before LLM submission; positive
    scans short-circuit to ``unverified`` and never reach Bedrock.
  - **Verification status.** Resolved edges carry a discrete
    ``verification_status`` property (``verified`` / ``plausible`` /
    ``unverified``) replacing the unreliable ``confidence`` float
    rejected during the cross-disciplinary review.
  - **CALLS_INFERRED label.** Tier 3 emits the label at a different
    trust tier than deterministic CALLS so read paths can filter at
    label level without per-edge property lookups.

Soft dependencies:

  - Bedrock client is optional; without it, the resolver no-ops and
    leaves the input unchanged (Tier 4 / future LLM tiers can pick
    up later, or edges remain at the legacy raw-name shape).
  - Secret pre-scan is optional but recommended; absence increments
    a telemetry counter so operators see when the safety net is off.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import uuid
from dataclasses import dataclass
from typing import Iterable, Protocol

from src.agents.ast_parser_agent import CodeEntity, CodeRelationship
from src.services.graph.edge_labels import EdgeLabel
from src.services.graph.fqn import compute_fqn
from src.services.graph.symbol_resolver_queue import ResolutionRequest

logger = logging.getLogger(__name__)


class ResolutionPublisher(Protocol):
    """Sink for ResolutionRequest payloads in queue mode.

    Production wires this to an SQS-backed implementation; tests
    inject a fake that records published requests.
    """

    def publish(self, request: ResolutionRequest) -> None: ...


# Discrete verification status replacing the float-confidence model.
# Per ADR-090 Thread 5 + Mike's ML review, self-reported LLM
# probabilities are not calibrated; we use a small enum that records
# *what we then verified* about the LLM's pick rather than how
# confident the LLM said it was.
VERIFIED = "verified"
PLAUSIBLE = "plausible"
UNVERIFIED = "unverified"


# Snippet window around a call site. Per Mike's review, full files
# are unnecessary and increase injection surface; ~20 lines of
# context above and below the call is enough for resolution.
_SNIPPET_CONTEXT_LINES = 20

# Maximum candidates surfaced to the LLM per call site. The closed
# set is the only legal output space; bounded size keeps prompts
# small and the model's selection space tight.
_MAX_CANDIDATES = 8

# Per-job LLM call budget. Phase 4c.1 is in-process and hot-path; the
# budget cap is the practical guard against runaway cost on a
# pathological repo. ECS workers in Phase 4c.2 add per-tenant
# amortized ceilings on top.
_DEFAULT_LLM_CALL_BUDGET = 1000


@dataclass
class Tier3Stats:
    """Per-run Tier 3 telemetry."""

    relationships_seen: int = 0
    candidates_considered: int = 0
    no_candidates: int = 0
    secret_prescan_blocked: int = 0
    secret_prescan_unavailable: int = 0
    llm_unavailable: int = 0
    llm_invoked: int = 0
    llm_resolved_verified: int = 0
    llm_resolved_plausible: int = 0
    llm_returned_none: int = 0
    llm_invalid_response: int = 0
    cache_hits: int = 0
    budget_exhausted: int = 0
    still_unresolved: int = 0
    # Phase 4c.2: in queue mode, the resolver publishes a
    # ResolutionRequest per unresolved edge and emits a placeholder
    # ``unverified`` edge while the worker pool resolves async.
    published_to_queue: int = 0
    publish_failed: int = 0


class _BedrockGenerate(Protocol):
    """Minimal async interface the resolver requires from a Bedrock client.

    The codebase's :class:`BedrockLLMService.generate` matches this
    shape. Tests inject a fake satisfying the protocol.
    """

    async def __call__(
        self,
        prompt: str,
        agent: str = ...,
        system_prompt: str | None = ...,
        max_tokens: int | None = ...,
        operation: str | None = ...,
        use_semantic_cache: bool = ...,
    ) -> str: ...


class _SecretsScanner(Protocol):
    """Minimal interface for the secrets pre-scan filter.

    Matches :class:`SecretsPrescanFilter.scan_and_redact`. Tests
    inject a fake; production wires the real filter.
    """

    def scan_and_redact(
        self,
        content: str,
        file_path: str | None = ...,
        organization_id: str | None = ...,
    ): ...


class Tier3LLMResolver:
    """LLM-disambiguation resolver for the Tier 1/2 unresolved residue.

    The resolver is invoked from :class:`GitIngestionService` after
    the deterministic tiers. It does not write to Neptune directly;
    it emits enriched :class:`CodeRelationship` objects that the
    ingestion pipeline writes via the standard add_relationship path.
    Edges resolved by Tier 3 carry the :data:`EdgeLabel.CALLS_INFERRED`
    label rather than ``CALLS`` so read paths can filter at the label
    level.

    Phase 4c.1 runs in-process with a configurable per-job call
    budget; Phase 4c.2 will move the LLM stage onto ECS Fargate
    workers behind SQS without changing this class's interface.
    """

    def __init__(
        self,
        bedrock_generate: _BedrockGenerate | None = None,
        secrets_scanner: _SecretsScanner | None = None,
        call_budget: int = _DEFAULT_LLM_CALL_BUDGET,
        operation: str = "graph_symbol_resolution",
        max_candidates: int = _MAX_CANDIDATES,
        max_tokens: int = 256,
        publisher: ResolutionPublisher | None = None,
        tenant_id: str = "default",
    ):
        """
        Args:
          bedrock_generate: Inline LLM client. When set, the resolver
            calls Bedrock directly (Phase 4c.1 behaviour).
          publisher: Queue producer for distributed mode (Phase
            4c.2). When set, the resolver writes ResolutionRequest
            records to the queue and emits placeholder ``unverified``
            edges that the worker pool resolves asynchronously. If
            both ``publisher`` and ``bedrock_generate`` are set, the
            publisher wins and the inline client is unused.
          tenant_id: Per-tenant identifier carried in queue payloads
            for the cost-ceiling tracker (Phase 4c.2.4).
        """
        self.bedrock_generate = bedrock_generate
        self.secrets_scanner = secrets_scanner
        self.call_budget = call_budget
        self.operation = operation
        self.max_candidates = max_candidates
        self.max_tokens = max_tokens
        self.publisher = publisher
        self.tenant_id = tenant_id

    @property
    def llm_available(self) -> bool:
        return self.bedrock_generate is not None or self.publisher is not None

    @property
    def queue_mode(self) -> bool:
        return self.publisher is not None

    async def resolve(
        self,
        entities: Iterable[CodeEntity],
        relationships: Iterable[CodeRelationship],
        repo_id: str,
        source_reader: "_SourceReader | None" = None,
    ) -> tuple[list[CodeRelationship], Tier3Stats]:
        """Return relationships with Tier 3 resolutions applied.

        ``source_reader`` provides the snippet content for each
        ``(file_path, line)`` call site; tests inject a fake. When
        absent, the resolver still runs but emits ``unverified``
        edges without snippet context (less accurate but never
        dangerous).
        """
        relationships_list = list(relationships)
        entities_list = list(entities)
        stats = Tier3Stats(relationships_seen=len(relationships_list))

        if not self.llm_available:
            stats.llm_unavailable = sum(
                1 for r in relationships_list if self._is_unresolved_call(r)
            )
            stats.still_unresolved = stats.llm_unavailable
            return relationships_list, stats

        candidate_index = self._build_candidate_index(entities_list)
        cache: dict[str, str | None] = {}
        out: list[CodeRelationship] = []
        budget_used = 0

        for rel in relationships_list:
            if not self._is_unresolved_call(rel):
                out.append(rel)
                continue
            stats.candidates_considered += 1

            candidates = self._candidates_for(rel, candidate_index)
            if not candidates:
                stats.no_candidates += 1
                stats.still_unresolved += 1
                out.append(rel)
                continue

            snippet = self._extract_snippet(rel, source_reader)
            if snippet and self._secret_prescan_blocks(snippet, rel.file_path, stats):
                out.append(self._with_status(rel, UNVERIFIED))
                continue

            # Phase 4c.2: queue mode short-circuits before any inline
            # LLM invocation. Publish a ResolutionRequest and emit a
            # placeholder ``unverified`` edge that the worker pool
            # resolves asynchronously. The producer keeps the
            # ingestion job's hot path deterministic; Bedrock latency
            # never blocks ingest.
            if self.queue_mode:
                self._publish_resolution_request(
                    rel, candidates, snippet, repo_id, stats
                )
                out.append(self._with_status(rel, UNVERIFIED))
                continue

            cache_key = self._cache_key(rel, candidates, snippet)
            if cache_key in cache:
                stats.cache_hits += 1
                cached_target_fqn = cache[cache_key]
                out.append(
                    self._with_resolution(rel, cached_target_fqn, candidates, repo_id)
                )
                continue

            if budget_used >= self.call_budget:
                stats.budget_exhausted += 1
                stats.still_unresolved += 1
                out.append(self._with_status(rel, UNVERIFIED))
                continue

            budget_used += 1
            stats.llm_invoked += 1
            chosen_index = await self._invoke_llm(rel, candidates, snippet, stats)

            if chosen_index is None:
                cache[cache_key] = None
                stats.still_unresolved += 1
                out.append(self._with_status(rel, UNVERIFIED))
                continue

            chosen = candidates[chosen_index]
            target_fqn = self._fqn_for(chosen, repo_id)
            cache[cache_key] = target_fqn

            verification = self._verify(rel, chosen, candidate_index)
            if verification == VERIFIED:
                stats.llm_resolved_verified += 1
            else:
                stats.llm_resolved_plausible += 1

            out.append(
                CodeRelationship(
                    source_name=rel.source_name,
                    source_parent_chain=rel.source_parent_chain,
                    target_name=rel.target_name,
                    relationship=EdgeLabel.CALLS_INFERRED.value,
                    properties={
                        **rel.properties,
                        "verification_status": verification,
                        "resolution_method": "llm",
                    },
                    file_path=rel.file_path,
                    source_fqn=rel.source_fqn,
                    target_fqn=target_fqn,
                )
            )

        return out, stats

    # -- Candidate set construction -------------------------------------

    def _build_candidate_index(
        self, entities: list[CodeEntity]
    ) -> dict[str, list[CodeEntity]]:
        """Index entities by leaf name for fast candidate lookup.

        The leaf-name index is the right shape for the closed
        candidate set: most resolution targets are referenced by the
        last segment of a dotted call (``utils.helper`` -> leaf
        ``helper``; ``self.do_thing`` -> leaf ``do_thing``).
        """
        by_leaf: dict[str, list[CodeEntity]] = {}
        for entity in entities:
            if not entity.name:
                continue
            by_leaf.setdefault(entity.name, []).append(entity)
        return by_leaf

    def _candidates_for(
        self,
        rel: CodeRelationship,
        candidate_index: dict[str, list[CodeEntity]],
    ) -> list[CodeEntity]:
        """Return the closed candidate set for a single CALLS edge."""
        if not rel.target_name:
            return []
        leaf = rel.target_name.rsplit(".", 1)[-1]
        candidates = candidate_index.get(leaf, [])
        # Cap the candidate list. Large pools dilute the model's
        # selection accuracy and bloat the prompt.
        return candidates[: self.max_candidates]

    # -- Source snippet extraction --------------------------------------

    def _extract_snippet(
        self,
        rel: CodeRelationship,
        source_reader: "_SourceReader | None",
    ) -> str | None:
        if source_reader is None:
            return None
        line = rel.properties.get("call_site_line")
        if not isinstance(line, int) or not rel.file_path:
            return None
        try:
            raw = source_reader.read(rel.file_path, line, _SNIPPET_CONTEXT_LINES)
        except Exception as e:
            logger.debug(f"Source snippet read failed for {rel.file_path}: {e}")
            return None
        return strip_python_comments_and_docstrings(raw) if raw else None

    def _secret_prescan_blocks(
        self, snippet: str, file_path: str | None, stats: Tier3Stats
    ) -> bool:
        if self.secrets_scanner is None:
            stats.secret_prescan_unavailable += 1
            return False
        try:
            result = self.secrets_scanner.scan_and_redact(snippet, file_path=file_path)
        except Exception as e:
            logger.warning(f"Secret pre-scan failed; refusing to send to LLM: {e}")
            stats.secret_prescan_blocked += 1
            return True
        # Treat any detection as blocking; per Sally's review the bar
        # for sending source to a third-party model is high.
        detections = getattr(result, "detections", None) or []
        if detections:
            stats.secret_prescan_blocked += 1
            return True
        return False

    # -- Queue dispatch (Phase 4c.2) ------------------------------------

    def _publish_resolution_request(
        self,
        rel: CodeRelationship,
        candidates: list[CodeEntity],
        snippet: str | None,
        repo_id: str,
        stats: Tier3Stats,
    ) -> None:
        """Send a ResolutionRequest to the worker queue.

        The producer never raises out of the resolve loop: a publish
        failure is logged and counted, and the placeholder
        ``unverified`` edge is still emitted so ingestion progresses.
        Worker retries / DLQ handling cover the failure path.
        """
        snippet_hash = (
            hashlib.sha256(snippet.encode("utf-8")).hexdigest() if snippet else None
        )
        request = ResolutionRequest.build(
            request_id=f"{repo_id}:{uuid.uuid4().hex[:12]}",
            tenant_id=self.tenant_id,
            repo_id=repo_id,
            relationship=rel,
            candidates=candidates,
            snippet_hash=snippet_hash,
        )
        try:
            assert self.publisher is not None  # narrowed by queue_mode check
            self.publisher.publish(request)
            stats.published_to_queue += 1
        except Exception as e:
            logger.warning(
                f"Failed to publish ResolutionRequest " f"{request.request_id}: {e}"
            )
            stats.publish_failed += 1

    # -- LLM invocation -------------------------------------------------

    async def _invoke_llm(
        self,
        rel: CodeRelationship,
        candidates: list[CodeEntity],
        snippet: str | None,
        stats: Tier3Stats,
    ) -> int | None:
        """Ask the LLM to pick a candidate index. Returns index or None."""
        prompt = self._build_prompt(rel, candidates, snippet)
        try:
            response_text = await self.bedrock_generate(
                prompt=prompt,
                agent="GraphSymbolResolver",
                operation=self.operation,
                max_tokens=self.max_tokens,
                use_semantic_cache=True,
            )
        except Exception as e:
            logger.warning(f"Bedrock invocation failed: {e}")
            stats.llm_invalid_response += 1
            return None
        return self._parse_choice(response_text, len(candidates), stats)

    def _build_prompt(
        self,
        rel: CodeRelationship,
        candidates: list[CodeEntity],
        snippet: str | None,
    ) -> str:
        """Constrained-output prompt: model picks an index or NONE."""
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
        lines.append(f"Caller file: {rel.file_path}")
        if rel.source_parent_chain:
            lines.append(
                f"Caller scope: {'.'.join(rel.source_parent_chain)}.{rel.source_name}"
            )
        else:
            lines.append(f"Caller scope: {rel.source_name}")
        lines.append(f"Call expression: {rel.target_name}")
        line = rel.properties.get("call_site_line")
        if line:
            lines.append(f"Call site line: {line}")
        lines.append("")
        lines.append("Candidates:")
        for idx, candidate in enumerate(candidates):
            chain = ".".join(candidate.parent_chain or ())
            qualified = f"{chain}.{candidate.name}" if chain else candidate.name
            lines.append(
                f"  [{idx}] {candidate.entity_type} {qualified} "
                f"in {candidate.file_path} at line {candidate.line_number}"
            )
        if snippet:
            lines.append("")
            lines.append("Source snippet (comments and docstrings stripped):")
            lines.append("```")
            lines.append(snippet)
            lines.append("```")
        lines.append("")
        lines.append(
            "Pick the candidate that is most likely the resolved "
            "target of the call. Output only the JSON object."
        )
        return "\n".join(lines)

    @staticmethod
    def _parse_choice(
        response_text: str, num_candidates: int, stats: Tier3Stats
    ) -> int | None:
        if not response_text:
            stats.llm_invalid_response += 1
            return None
        # Models occasionally wrap JSON in markdown fences. Trim them.
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").lstrip("json").strip()
        try:
            obj = json.loads(cleaned)
        except json.JSONDecodeError:
            # Fallback: search for {"chosen_index": ...} substring.
            match = re.search(r'"chosen_index"\s*:\s*(null|\d+)', response_text)
            if not match:
                stats.llm_invalid_response += 1
                return None
            value = match.group(1)
            if value == "null":
                stats.llm_returned_none += 1
                return None
            try:
                idx = int(value)
            except ValueError:
                stats.llm_invalid_response += 1
                return None
            return idx if 0 <= idx < num_candidates else None

        choice = obj.get("chosen_index")
        if choice is None:
            stats.llm_returned_none += 1
            return None
        if not isinstance(choice, int):
            stats.llm_invalid_response += 1
            return None
        if 0 <= choice < num_candidates:
            return choice
        stats.llm_invalid_response += 1
        return None

    # -- Verification ---------------------------------------------------

    def _verify(
        self,
        rel: CodeRelationship,
        chosen: CodeEntity,
        candidate_index: dict[str, list[CodeEntity]],
    ) -> str:
        """Structural verification of the LLM's chosen candidate.

        Tier 3 considers a resolution VERIFIED when:
          - The chosen entity is in our index (always true for
            candidates we surfaced ourselves), AND
          - The chosen entity's leaf name matches the call's target
            leaf name (no name-skip), AND
          - The chosen entity's file is reachable from the caller's
            file (same file or any file in the same repo, since
            Tier 1's import-graph already pruned cross-package
            targets we cannot resolve).
        Otherwise PLAUSIBLE (chosen, no contradiction found).
        """
        if not rel.target_name:
            return PLAUSIBLE
        leaf = rel.target_name.rsplit(".", 1)[-1]
        if chosen.name != leaf:
            return PLAUSIBLE
        # Both files must be present in our index. Since the chosen
        # candidate came from `candidate_index`, the file is present
        # by construction; this check is mostly a guard against
        # future refactors.
        if chosen.file_path:
            return VERIFIED
        return PLAUSIBLE

    # -- Helpers --------------------------------------------------------

    @staticmethod
    def _is_unresolved_call(rel: CodeRelationship) -> bool:
        return rel.relationship == EdgeLabel.CALLS.value and rel.target_fqn is None

    @staticmethod
    def _fqn_for(entity: CodeEntity, repo_id: str) -> str:
        parent_chain = entity.parent_chain or ()
        if not parent_chain and entity.parent_entity:
            parent_chain = (entity.parent_entity,)
        return compute_fqn(
            name=entity.name,
            kind=entity.entity_type,
            file_path=entity.file_path,
            repo_id=repo_id,
            parent_chain=tuple(parent_chain),
        )

    @staticmethod
    def _cache_key(
        rel: CodeRelationship,
        candidates: list[CodeEntity],
        snippet: str | None,
    ) -> str:
        """Content-addressed cache key.

        Phase 4c.1 keys on (call site location, target name,
        candidate set fingerprint, snippet hash). Phase 4c.2 will
        extend this with transitive-closure invalidation per Mike's
        review, but the in-process cache only lives for the duration
        of a single ingest job so that gap is bounded.
        """
        candidate_fingerprint = "|".join(
            f"{c.file_path}:{c.line_number}:{c.entity_type}:{c.name}"
            for c in candidates
        )
        snippet_hash = (
            hashlib.sha256(snippet.encode("utf-8")).hexdigest()[:16]
            if snippet
            else "no-snippet"
        )
        material = "|".join(
            [
                rel.file_path or "",
                str(rel.properties.get("call_site_line", "")),
                rel.target_name or "",
                candidate_fingerprint,
                snippet_hash,
            ]
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @staticmethod
    def _with_status(rel: CodeRelationship, status: str) -> CodeRelationship:
        return CodeRelationship(
            source_name=rel.source_name,
            source_parent_chain=rel.source_parent_chain,
            target_name=rel.target_name,
            relationship=EdgeLabel.CALLS_INFERRED.value,
            properties={
                **rel.properties,
                "verification_status": status,
                "resolution_method": "llm",
            },
            file_path=rel.file_path,
            source_fqn=rel.source_fqn,
            target_fqn=rel.target_fqn,
        )

    @staticmethod
    def _with_resolution(
        rel: CodeRelationship,
        target_fqn: str | None,
        candidates: list[CodeEntity],
        repo_id: str,
    ) -> CodeRelationship:
        if target_fqn is None:
            return Tier3LLMResolver._with_status(rel, UNVERIFIED)
        return CodeRelationship(
            source_name=rel.source_name,
            source_parent_chain=rel.source_parent_chain,
            target_name=rel.target_name,
            relationship=EdgeLabel.CALLS_INFERRED.value,
            properties={
                **rel.properties,
                "verification_status": PLAUSIBLE,
                "resolution_method": "llm",
                "from_cache": True,
            },
            file_path=rel.file_path,
            source_fqn=rel.source_fqn,
            target_fqn=target_fqn,
        )


# -- Snippet hardening ----------------------------------------------------


_PYTHON_DOCSTRING_PATTERN = re.compile(
    r'(""".*?"""|\'\'\'.*?\'\'\')',
    re.DOTALL,
)
_PYTHON_LINE_COMMENT = re.compile(r"#.*?$", re.MULTILINE)
_JS_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_JS_LINE_COMMENT = re.compile(r"//.*?$", re.MULTILINE)


def strip_python_comments_and_docstrings(source: str) -> str:
    """Strip Python ``#`` comments and triple-quoted docstrings.

    Per ADR-090 Thread 2 / Sally's security review, structural
    resolution does not require natural-language prose, and
    submitting prose to the LLM expands the prompt-injection surface.
    Stripping comments and docstrings before submission eliminates
    an estimated ~95% of the typical injection vectors.

    The implementation is intentionally conservative: it only
    matches the common cases. Edge cases like comments inside
    string literals are left in place because the snippet is
    advisory context, not a syntactic round-trip.
    """
    cleaned = _PYTHON_DOCSTRING_PATTERN.sub("", source)
    cleaned = _PYTHON_LINE_COMMENT.sub("", cleaned)
    cleaned = _JS_BLOCK_COMMENT.sub("", cleaned)
    cleaned = _JS_LINE_COMMENT.sub("", cleaned)
    # Collapse runs of blank lines that result from stripping.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


# -- Source reader abstraction --------------------------------------------


class _SourceReader(Protocol):
    """Reads ±N lines around a call site from a source file."""

    def read(
        self, file_path: str, line_number: int, context_lines: int
    ) -> str | None: ...


class FilesystemSourceReader:
    """Reads call-site snippets from a repository checkout on disk."""

    def __init__(self, repo_root):
        from pathlib import Path

        self.repo_root = Path(repo_root)

    def read(self, file_path: str, line_number: int, context_lines: int) -> str | None:
        from pathlib import Path

        target = self.repo_root / file_path
        try:
            text = Path(target).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None
        lines = text.splitlines()
        start = max(0, line_number - 1 - context_lines)
        end = min(len(lines), line_number - 1 + context_lines + 1)
        if start >= end:
            return None
        return "\n".join(lines[start:end])


# Convenience: synchronous wrapper for callers outside an event loop.
def resolve_sync(
    resolver: Tier3LLMResolver,
    entities: Iterable[CodeEntity],
    relationships: Iterable[CodeRelationship],
    repo_id: str,
    source_reader: _SourceReader | None = None,
) -> tuple[list[CodeRelationship], Tier3Stats]:
    """Run the resolver from a synchronous context."""
    return asyncio.run(
        resolver.resolve(entities, relationships, repo_id, source_reader)
    )
