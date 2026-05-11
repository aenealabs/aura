"""Tier 2 symbol resolution (ADR-090 Phase 4b).

Tier 2 picks up where Tier 1 left off: relationships whose target was
not resolved deterministically by import-graph traversal. This module
ships two backends:

  - **Tier2SelfMethodResolver** -- deterministic class-hierarchy
    traversal for ``self.method`` and ``this.method`` targets. Walks
    INHERITS edges to resolve inherited methods. Pure Python, no
    external dependencies, runs first.

  - **Tier2PyrightBackend** -- structured wrapper around Pyright's
    Language Server Protocol. Resolves dynamic-dispatch and
    type-inference cases that the self-method resolver cannot. Soft
    dependency: when ``pyright-langserver`` is not on PATH the
    backend transparently no-ops and the pipeline continues with
    raw-name CALLS edges that Tier 3 will pick up later.

The composing :class:`Tier2SymbolResolver` runs both backends in
sequence over the still-unresolved input from Tier 1, returning the
enriched relationship list and per-tier telemetry. Order matters:
the deterministic backend runs first so cheaper, safer resolutions
land before any external-tool invocation.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from src.agents.ast_parser_agent import CodeEntity, CodeRelationship
from src.services.graph.edge_labels import EdgeLabel
from src.services.graph.fqn import compute_fqn

logger = logging.getLogger(__name__)


# Receiver tokens whose targets are class-relative method calls.
# Resolving them requires walking the class chain of the call site's
# enclosing scope; Tier 1 deferred them here.
_SELF_RECEIVERS: frozenset[str] = frozenset({"self", "cls", "this", "super"})

# Hard timeout per Pyright resolution request. Per ADR-090 thread
# review (Mike, ML), most warm Pyright queries return <50ms; 500ms
# catches outliers without dragging the worker.
_PYRIGHT_TIMEOUT_MS = 500


@dataclass
class Tier2Stats:
    """Per-run Tier 2 telemetry, separated by backend."""

    relationships_seen: int = 0
    candidates_considered: int = 0
    self_method_resolved: int = 0
    self_method_via_inheritance: int = 0
    pyright_attempted: int = 0
    pyright_resolved: int = 0
    pyright_timed_out: int = 0
    pyright_unavailable: int = 0
    still_unresolved: int = 0


class Tier2SelfMethodResolver:
    """Resolves ``self.method`` / ``this.method`` via class-hierarchy walk.

    Given a CALLS edge whose source is a method on class C and whose
    target is ``self.method``, we look for an entity named ``method``
    on class C first, then walk the INHERITS chain (the immediate
    bases declared on C) until we find one. The resolver only follows
    INHERITS edges produced by Phases 2/3 of the parser, so it works
    for both Python (``extends``) and JavaScript (``extends``) classes.

    The resolver is intentionally conservative on multiple inheritance:
    when an inherited method is found in more than one base class, the
    target is left unresolved rather than guessing the MRO. Tier 2
    Pyright (or Tier 3 LLM) handles the ambiguous cases.
    """

    def resolve(
        self,
        entities: list[CodeEntity],
        relationships: list[CodeRelationship],
        repo_id: str,
        stats: Tier2Stats,
    ) -> list[CodeRelationship]:
        """Return relationships with self/cls/this targets resolved where possible.

        Only relationships that are CALLS edges with an unresolved
        target_fqn are considered; everything else passes through
        unchanged. The resolver does not mutate input records.
        """
        # (file_path, parent_chain) -> {entity name -> CodeEntity}
        # plus an INHERITS lookup keyed by class name to traverse the
        # parent class chain.
        scope_index = self._build_scope_index(entities)
        inherits_index = self._build_inherits_index(relationships, entities)

        out: list[CodeRelationship] = []
        for rel in relationships:
            if not self._is_self_call(rel):
                out.append(rel)
                continue

            stats.candidates_considered += 1
            resolved_fqn = self._resolve_self_target(
                rel, scope_index, inherits_index, repo_id, stats
            )
            if resolved_fqn is None:
                out.append(rel)
                continue

            out.append(self._with_target_fqn(rel, resolved_fqn))
        return out

    # -- Indexing -------------------------------------------------------

    @staticmethod
    def _build_scope_index(
        entities: list[CodeEntity],
    ) -> dict[tuple[str, tuple[str, ...]], dict[str, CodeEntity]]:
        index: dict[tuple[str, tuple[str, ...]], dict[str, CodeEntity]] = {}
        for entity in entities:
            if not entity.file_path:
                continue
            key = (entity.file_path, tuple(entity.parent_chain or ()))
            bucket = index.setdefault(key, {})
            # First emission wins under collisions; later overloads are
            # ambiguous and handled by Tier 1's same-file rules.
            bucket.setdefault(entity.name, entity)
        return index

    @staticmethod
    def _build_inherits_index(
        relationships: list[CodeRelationship],
        entities: list[CodeEntity],
    ) -> dict[tuple[str, str], list[str]]:
        """Build (file_path, class_name) -> [base_class_names].

        Only same-file bases are tracked here; cross-file class
        inheritance is a Phase 4c concern. This is a defensible
        scoping choice because most ``self.method`` resolutions have
        the relevant base class in the same file.
        """
        # Also track which files declare each class name so we can
        # cross-reference INHERITS targets that are local class names.
        class_files: dict[str, set[str]] = {}
        for entity in entities:
            if entity.entity_type == "class" and entity.file_path:
                class_files.setdefault(entity.name, set()).add(entity.file_path)

        index: dict[tuple[str, str], list[str]] = {}
        for rel in relationships:
            if rel.relationship != EdgeLabel.INHERITS.value:
                continue
            if not rel.file_path or not rel.source_name or not rel.target_name:
                continue
            # Take only the leaf segment of dotted bases
            # (``module.Base`` -> ``Base``); this matches how the
            # scope index keys class names.
            base_name = rel.target_name.rsplit(".", 1)[-1]
            key = (rel.file_path, rel.source_name)
            index.setdefault(key, []).append(base_name)
        return index

    # -- Resolution -----------------------------------------------------

    @staticmethod
    def _is_self_call(rel: CodeRelationship) -> bool:
        if rel.relationship != EdgeLabel.CALLS.value:
            return False
        if rel.target_fqn is not None:
            return False
        if not rel.target_name or "." not in rel.target_name:
            return False
        head = rel.target_name.split(".", 1)[0]
        return head in _SELF_RECEIVERS

    def _resolve_self_target(
        self,
        rel: CodeRelationship,
        scope_index: dict[tuple[str, tuple[str, ...]], dict[str, CodeEntity]],
        inherits_index: dict[tuple[str, str], list[str]],
        repo_id: str,
        stats: Tier2Stats,
    ) -> str | None:
        # ``self.foo.bar`` is two-step access; Phase 4b only resolves
        # the immediate ``self.method`` shape. Deeper chains stay raw
        # for now and are good Tier 3 candidates.
        parts = rel.target_name.split(".")
        if len(parts) != 2:
            return None
        method_name = parts[1]

        parent_chain = tuple(rel.source_parent_chain or ())
        if not parent_chain:
            return None
        class_name = parent_chain[-1]

        # First: own class. The scope key for methods on ``Outer.Inner``
        # is ``(file, ("Outer", "Inner"))`` -- the full enclosing chain
        # of the method, which IS the class's own context.
        own_chain = parent_chain
        own_methods = scope_index.get((rel.file_path, own_chain), {})
        if method_name in own_methods:
            stats.self_method_resolved += 1
            return self._fqn_for(own_methods[method_name], repo_id)

        # Then: walk same-file bases. We follow INHERITS edges from the
        # class one level at a time and stop at the first uniquely-
        # named match. Multiple matches across siblings are ambiguous
        # and skipped (deterministic mediation).
        bases = inherits_index.get((rel.file_path, class_name), [])
        if not bases:
            return None

        seen: set[str] = set()
        queue: list[str] = list(bases)
        candidates: list[CodeEntity] = []
        while queue:
            current = queue.pop(0)
            if current in seen:
                continue
            seen.add(current)
            base_chain = self._scope_chain_for_class(
                rel.file_path, current, scope_index
            )
            if base_chain is None:
                continue
            base_methods = scope_index.get((rel.file_path, base_chain), {})
            if method_name in base_methods:
                candidates.append(base_methods[method_name])
                # First match short-circuits the BFS for the common
                # single-inheritance case; siblings are appended to
                # ``queue`` only if no match found above.
                continue
            # Walk further up
            queue.extend(inherits_index.get((rel.file_path, current), []))

        if len(candidates) == 1:
            stats.self_method_via_inheritance += 1
            return self._fqn_for(candidates[0], repo_id)
        # Zero matches -> unresolved; >1 matches -> ambiguous, skipped.
        return None

    @staticmethod
    def _scope_chain_for_class(
        file_path: str,
        class_name: str,
        scope_index: dict[tuple[str, tuple[str, ...]], dict[str, CodeEntity]],
    ) -> tuple[str, ...] | None:
        """Find the parent_chain for a class in the same file.

        Top-level classes have ``parent_chain == ("ClassName",)`` from
        the perspective of their methods; nested classes have a longer
        chain. We search the scope index for any chain whose last
        element equals ``class_name`` and whose file_path matches.
        """
        # Common case: top-level class.
        candidate = (class_name,)
        if (file_path, candidate) in scope_index:
            return candidate
        # Nested: scan keys for any matching tail.
        for (path, chain), _ in scope_index.items():
            if path == file_path and chain and chain[-1] == class_name:
                return chain
        return None

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
    def _with_target_fqn(rel: CodeRelationship, target_fqn: str) -> CodeRelationship:
        return CodeRelationship(
            source_name=rel.source_name,
            source_parent_chain=rel.source_parent_chain,
            target_name=rel.target_name,
            relationship=rel.relationship,
            properties=dict(rel.properties),
            file_path=rel.file_path,
            source_fqn=rel.source_fqn,
            target_fqn=target_fqn,
        )


class Tier2PyrightBackend:
    """Pyright LSP backend for type-inference-driven resolution.

    Soft dependency: if ``pyright-langserver`` is not discoverable on
    PATH (or the environment variable ``AURA_PYRIGHT_PATH`` is not
    set), the backend transparently no-ops and the pipeline runs
    with the absorption profile of the deterministic tiers only.

    This class is the alpha-grade subprocess-spawned implementation
    described in the ADR's Phase 4 roadmap. Production migrates to a
    long-running daemon; the abstraction here is the same.
    """

    def __init__(
        self,
        pyright_path: str | None = None,
        timeout_ms: int = _PYRIGHT_TIMEOUT_MS,
    ):
        self.pyright_path = pyright_path or self._discover_pyright()
        self.timeout_ms = timeout_ms

    @property
    def available(self) -> bool:
        return self.pyright_path is not None

    @staticmethod
    def _discover_pyright() -> str | None:
        env_override = os.environ.get("AURA_PYRIGHT_PATH")
        if env_override and Path(env_override).exists():
            return env_override
        return shutil.which("pyright-langserver")

    def resolve(
        self,
        entities: list[CodeEntity],
        relationships: list[CodeRelationship],
        repo_root: str | os.PathLike[str] | None,
        repo_id: str,
        stats: Tier2Stats,
    ) -> list[CodeRelationship]:
        """Attempt Pyright-driven resolution of remaining unresolved CALLS.

        Returns ``relationships`` unchanged if Pyright is not
        available or ``repo_root`` is not provided. Otherwise, walks
        unresolved CALLS edges, queries Pyright for the definition of
        each call site, and emits a target_fqn when a single
        resolvable definition is returned within the timeout.
        """
        if not self.available or repo_root is None:
            stats.pyright_unavailable += sum(
                1 for r in relationships if self._is_unresolved_call(r)
            )
            return relationships

        # The protocol implementation lives in _pyright_lsp_resolve so
        # this method stays focused on the pure-Python control flow
        # and the no-op path. The subprocess is constructed lazily so
        # tests can swap in fakes.
        return self._pyright_lsp_resolve(
            entities, relationships, Path(repo_root), repo_id, stats
        )

    @staticmethod
    def _is_unresolved_call(rel: CodeRelationship) -> bool:
        return rel.relationship == EdgeLabel.CALLS.value and rel.target_fqn is None

    def _pyright_lsp_resolve(
        self,
        entities: list[CodeEntity],
        relationships: list[CodeRelationship],
        repo_root: Path,
        repo_id: str,
        stats: Tier2Stats,
    ) -> list[CodeRelationship]:
        """Real LSP exchange. Best-effort; never raises on protocol errors.

        This method is subprocess-heavy and intentionally not exercised
        in unit tests by default; integration tests gate on a real
        ``pyright-langserver`` binary via the ``AURA_PYRIGHT_PATH`` env
        var. Unit tests cover the no-op path and the framing helpers
        in :func:`encode_lsp_message` / :func:`parse_lsp_message`.
        """
        try:
            proc = subprocess.Popen(
                [self.pyright_path, "--stdio"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(repo_root),
            )
        except OSError as e:
            logger.warning(f"Failed to spawn pyright-langserver: {e}")
            stats.pyright_unavailable += sum(
                1 for r in relationships if self._is_unresolved_call(r)
            )
            return relationships

        try:
            self._lsp_initialize(proc, repo_root)
            entity_index = self._build_entity_location_index(entities)

            out: list[CodeRelationship] = []
            for rel in relationships:
                if not self._is_unresolved_call(rel):
                    out.append(rel)
                    continue
                stats.pyright_attempted += 1
                resolved = self._resolve_one_call(
                    proc, rel, entity_index, repo_id, repo_root, stats
                )
                out.append(resolved if resolved is not None else rel)
            return out
        finally:
            try:
                self._lsp_shutdown(proc)
            except Exception:
                pass
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                proc.kill()

    # The LSP exchange helpers below are intentionally minimal. A full
    # production client would manage textDocument open/close cycles,
    # capability negotiation, and request batching. Phase 4b delivers
    # the framing primitives and the resolution loop; Phase 4 final
    # promotes this to a long-running daemon and adds those features.

    @staticmethod
    def _lsp_initialize(proc: subprocess.Popen, repo_root: Path) -> None:
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "processId": os.getpid(),
                "rootUri": repo_root.as_uri(),
                "capabilities": {},
            },
        }
        _send_lsp_message(proc, request)
        _read_lsp_message(proc)
        _send_lsp_message(
            proc, {"jsonrpc": "2.0", "method": "initialized", "params": {}}
        )

    @staticmethod
    def _lsp_shutdown(proc: subprocess.Popen) -> None:
        _send_lsp_message(proc, {"jsonrpc": "2.0", "id": 999, "method": "shutdown"})
        _send_lsp_message(proc, {"jsonrpc": "2.0", "method": "exit"})

    def _resolve_one_call(
        self,
        proc: subprocess.Popen,
        rel: CodeRelationship,
        entity_index: dict[tuple[str, int], CodeEntity],
        repo_id: str,
        repo_root: Path,
        stats: Tier2Stats,
    ) -> CodeRelationship | None:
        # The minimal request: textDocument/definition at the call
        # site line. We don't track open documents in this alpha;
        # Pyright treats unopened documents as the on-disk content,
        # which is exactly what the parser saw at ingest time.
        line = rel.properties.get("call_site_line")
        if not isinstance(line, int) or not rel.file_path:
            return None
        full_path = (repo_root / rel.file_path).resolve()
        request = {
            "jsonrpc": "2.0",
            "id": 100,
            "method": "textDocument/definition",
            "params": {
                "textDocument": {"uri": full_path.as_uri()},
                "position": {"line": max(0, line - 1), "character": 0},
            },
        }
        try:
            _send_lsp_message(proc, request)
            response = _read_lsp_message(proc, timeout_s=self.timeout_ms / 1000)
        except _LSPTimeout:
            stats.pyright_timed_out += 1
            return None
        except Exception as e:
            logger.debug(f"Pyright LSP exchange failed: {e}")
            return None

        if not response or "result" not in response:
            return None

        location = self._first_location(response["result"])
        if location is None:
            return None

        target_entity = self._match_location_to_entity(
            location, repo_root, entity_index
        )
        if target_entity is None:
            return None

        stats.pyright_resolved += 1
        target_fqn = compute_fqn(
            name=target_entity.name,
            kind=target_entity.entity_type,
            file_path=target_entity.file_path,
            repo_id=repo_id,
            parent_chain=tuple(target_entity.parent_chain or ()),
        )
        return Tier2SelfMethodResolver._with_target_fqn(rel, target_fqn)

    @staticmethod
    def _first_location(result):
        if not result:
            return None
        if isinstance(result, list):
            return result[0] if result else None
        if isinstance(result, dict):
            return result
        return None

    @staticmethod
    def _build_entity_location_index(
        entities: list[CodeEntity],
    ) -> dict[tuple[str, int], CodeEntity]:
        index: dict[tuple[str, int], CodeEntity] = {}
        for entity in entities:
            if entity.file_path and entity.line_number:
                index[(entity.file_path, entity.line_number)] = entity
        return index

    @staticmethod
    def _match_location_to_entity(
        location: dict,
        repo_root: Path,
        entity_index: dict[tuple[str, int], CodeEntity],
    ) -> CodeEntity | None:
        uri = location.get("uri") or location.get("targetUri")
        rng = location.get("range") or location.get("targetRange")
        if not uri or not rng:
            return None
        # Convert URI back to repo-relative path.
        if uri.startswith("file://"):
            file_path = uri[len("file://") :]
        else:
            file_path = uri
        try:
            relative = str(Path(file_path).resolve().relative_to(repo_root.resolve()))
        except ValueError:
            return None
        line_number = rng.get("start", {}).get("line", 0) + 1
        return entity_index.get((relative, line_number))


class Tier2SymbolResolver:
    """Composes Tier 2 backends and exposes the same interface as Tier 1.

    Backends run in declaration order: deterministic self-method
    resolution first (cheap, conservative, no external deps), Pyright
    second (richer inference, soft dependency). The composer returns
    the enriched relationship list and a single :class:`Tier2Stats`
    aggregating both backends' telemetry.
    """

    def __init__(
        self,
        self_method_resolver: Tier2SelfMethodResolver | None = None,
        pyright_backend: Tier2PyrightBackend | None = None,
    ):
        self.self_method = self_method_resolver or Tier2SelfMethodResolver()
        self.pyright = pyright_backend or Tier2PyrightBackend()

    def resolve(
        self,
        entities: Iterable[CodeEntity],
        relationships: Iterable[CodeRelationship],
        repo_id: str,
        repo_root: str | os.PathLike[str] | None = None,
    ) -> tuple[list[CodeRelationship], Tier2Stats]:
        entities_list = list(entities)
        relationships_list = list(relationships)

        stats = Tier2Stats(relationships_seen=len(relationships_list))

        # Stage 1: deterministic self-method resolver.
        after_self = self.self_method.resolve(
            entities_list, relationships_list, repo_id, stats
        )

        # Stage 2: Pyright (no-op if unavailable or repo_root missing).
        after_pyright = self.pyright.resolve(
            entities_list, after_self, repo_root, repo_id, stats
        )

        stats.still_unresolved = sum(
            1 for r in after_pyright if self.pyright._is_unresolved_call(r)
        )
        return after_pyright, stats


# -- LSP framing helpers --------------------------------------------------


class _LSPTimeout(Exception):
    """Raised when a single LSP request exceeds its allotted budget."""


def _encode_lsp_payload(message: dict) -> bytes:
    body = json.dumps(message).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body


def _send_lsp_message(proc: subprocess.Popen, message: dict) -> None:
    if proc.stdin is None:
        return
    proc.stdin.write(_encode_lsp_payload(message))
    proc.stdin.flush()


def _read_lsp_message(proc: subprocess.Popen, timeout_s: float = 1.0) -> dict | None:
    """Read a single LSP message with a hard timeout.

    Pyright sometimes returns intermediate progress notifications
    before the actual response; the reader skips messages that are
    notifications (no ``id`` field) until the response arrives.
    """
    if proc.stdout is None:
        return None
    deadline_remaining = timeout_s
    while True:
        try:
            header = _read_until_blank_line(proc.stdout, deadline_remaining)
        except _LSPTimeout:
            raise
        content_length = _parse_content_length(header)
        if content_length is None:
            return None
        body = proc.stdout.read(content_length)
        if not body:
            return None
        message = json.loads(body)
        if "id" in message:
            return message
        # Notification: ignore and read again. We do not deduct from
        # the deadline because notifications can arrive in bursts.


def _read_until_blank_line(stream, timeout_s: float) -> bytes:
    """Read header bytes until CRLFCRLF; honor the timeout coarsely.

    Production should use a non-blocking read with select(); this
    alpha relies on the small message sizes Pyright produces and
    treats the timeout as an upper bound.
    """
    import select

    deadline = timeout_s
    buf = bytearray()
    while not buf.endswith(b"\r\n\r\n"):
        ready, _, _ = select.select([stream], [], [], deadline)
        if not ready:
            raise _LSPTimeout("Timed out reading LSP header")
        chunk = stream.read(1)
        if not chunk:
            return bytes(buf)
        buf.extend(chunk)
    return bytes(buf)


def _parse_content_length(header: bytes) -> int | None:
    for line in header.split(b"\r\n"):
        if line.lower().startswith(b"content-length:"):
            try:
                return int(line.split(b":", 1)[1].strip())
            except ValueError:
                return None
    return None


# Re-exported for tests.
encode_lsp_message = _encode_lsp_payload
parse_content_length = _parse_content_length
