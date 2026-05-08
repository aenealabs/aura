"""Tier 1 deterministic cross-file symbol resolver (ADR-090 Phase 4a).

Resolves the raw ``target_name`` strings emitted by the AST parsers
(Phase 2 Python, Phase 3 JS/TS) into canonical FQNs by walking the
per-repo import graph and entity index. The resolver runs after
parsing and before the ingestion pipeline writes to Neptune.

Tier 1 covers the cleanly deterministic cases:

  1. **Same-file lookup** -- ``helper()`` inside a function that has a
     sibling ``def helper`` in the same file resolves to the
     same-file entity's FQN.
  2. **Direct import** -- ``helper()`` after ``from utils import helper``
     resolves to ``utils.helper``'s FQN, provided the ``utils`` module
     maps to a file in the same repository.
  3. **Module-prefix dotted target** -- ``utils.helper()`` after
     ``import utils`` resolves the same way as direct import,
     keying on ``utils`` as the module alias.

Cases left unresolved (Phase 4b/4c will pick them up):

  - Multi-candidate matches (overloads, multi-file modules) -- skipped
    rather than guessed; deterministic mediation per NIST AC-3.
  - Dynamic dispatch (``getattr``, dict-of-callables) -- requires
    type inference (Tier 2 Pyright) or LLM disambiguation (Tier 3).
  - Cross-package targets (``boto3.client``) -- not in the local
    index; remain raw and queryable as cross-package call signal.
  - ``self.method`` and ``this.method`` -- requires class hierarchy
    traversal; deferred to Tier 2.

Output: a list of CodeRelationship records with ``target_fqn``
populated where Tier 1 succeeded; the original ``target_name`` is
preserved for audit and as the fallback endpoint.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from src.agents.ast_parser_agent import CodeEntity, CodeRelationship
from src.services.graph.edge_labels import EdgeLabel
from src.services.graph.fqn import compute_fqn, derive_module_path


@dataclass
class ResolutionStats:
    """Per-run resolver telemetry.

    Operators inspect these counts on every ingest job to spot
    coverage regressions. Phase 4b/4c report similar stats with
    additional tier breakdowns.
    """

    relationships_seen: int = 0
    calls_seen: int = 0
    same_file_resolved: int = 0
    direct_import_resolved: int = 0
    module_prefix_resolved: int = 0
    ambiguous_skipped: int = 0
    unresolved: int = 0
    skipped_non_calls: int = 0


@dataclass
class _RepoIndex:
    """Per-repo lookup tables built once per resolver run."""

    # (file_path, name) -> [CodeEntity] (list because of overloads)
    by_location: dict[tuple[str, str], list[CodeEntity]] = field(
        default_factory=lambda: defaultdict(list)
    )
    # module_path -> [file_path] (list because tests/main may share names)
    module_to_files: dict[str, list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )
    # file_path -> {local_binding: source_module}
    # Captures both `from X import Y` (local Y -> module X) and
    # `import X` (local X -> module X) for use during resolution.
    file_imports: dict[str, dict[str, str]] = field(
        default_factory=lambda: defaultdict(dict)
    )


class Tier1SymbolResolver:
    """Deterministic cross-file resolver for parser-emitted CALLS edges."""

    def resolve(
        self,
        entities: Iterable[CodeEntity],
        relationships: Iterable[CodeRelationship],
        repo_id: str,
    ) -> tuple[list[CodeRelationship], ResolutionStats]:
        """Return relationships with cross-file targets resolved where possible.

        The input ``relationships`` are not mutated; a new list is
        returned so callers can compare pre/post for diagnostics.
        """
        entities_list = list(entities)
        relationships_list = list(relationships)
        index = self._build_index(entities_list, relationships_list)
        stats = ResolutionStats()

        resolved: list[CodeRelationship] = []
        for rel in relationships_list:
            stats.relationships_seen += 1
            new_rel = self._resolve_one(rel, index, repo_id, stats)
            resolved.append(new_rel)

        return resolved, stats

    # -- Index construction ---------------------------------------------

    def _build_index(
        self,
        entities: list[CodeEntity],
        relationships: list[CodeRelationship],
    ) -> _RepoIndex:
        index = _RepoIndex()

        # Locate every entity by (file, name) and bucket by module.
        for entity in entities:
            if not entity.file_path or not entity.name:
                continue
            index.by_location[(entity.file_path, entity.name)].append(entity)
            module_path = derive_module_path(entity.file_path)
            if entity.file_path not in index.module_to_files[module_path]:
                index.module_to_files[module_path].append(entity.file_path)

        # Build per-file import bindings from IMPORTS relationships.
        # Each import relationship was emitted by the parser with
        # source_name set to the local binding (the alias used in the
        # importer's source code) and target_name set to the source
        # module path.
        for rel in relationships:
            if rel.relationship != EdgeLabel.IMPORTS.value:
                continue
            if not rel.file_path or not rel.source_name or not rel.target_name:
                continue
            index.file_imports[rel.file_path][rel.source_name] = rel.target_name

        return index

    # -- Per-relationship resolution ------------------------------------

    def _resolve_one(
        self,
        rel: CodeRelationship,
        index: _RepoIndex,
        repo_id: str,
        stats: ResolutionStats,
    ) -> CodeRelationship:
        """Return a (possibly enriched) copy of ``rel``.

        Phase 4a only resolves CALLS edges; INHERITS and IMPORTS pass
        through unchanged because their targets are already either
        same-file (INHERITS often is) or external module strings.
        """
        if rel.relationship != EdgeLabel.CALLS.value:
            stats.skipped_non_calls += 1
            return rel

        stats.calls_seen += 1

        target_fqn = self._resolve_call_target(rel, index, repo_id, stats)
        if target_fqn is None:
            return rel

        # Return a new CodeRelationship; do not mutate the input so
        # callers can diff pre/post for diagnostics.
        new_rel = CodeRelationship(
            source_name=rel.source_name,
            source_parent_chain=rel.source_parent_chain,
            target_name=rel.target_name,
            relationship=rel.relationship,
            properties=dict(rel.properties),
            file_path=rel.file_path,
            source_fqn=rel.source_fqn,
            target_fqn=target_fqn,
        )
        return new_rel

    def _resolve_call_target(
        self,
        rel: CodeRelationship,
        index: _RepoIndex,
        repo_id: str,
        stats: ResolutionStats,
    ) -> str | None:
        target = rel.target_name
        if not target or not rel.file_path:
            stats.unresolved += 1
            return None

        # Dotted targets: "utils.helper", "self.method", "obj.x.y".
        if "." in target:
            head, _, rest = target.partition(".")
            # Skip Python self/cls and JS this/super: requires class
            # hierarchy traversal (deferred to Tier 2).
            if head in {"self", "cls", "this", "super"}:
                stats.unresolved += 1
                return None
            return self._resolve_module_prefix(head, rest, rel, index, repo_id, stats)

        # Bare target name.
        return self._resolve_simple_name(target, rel, index, repo_id, stats)

    def _resolve_simple_name(
        self,
        name: str,
        rel: CodeRelationship,
        index: _RepoIndex,
        repo_id: str,
        stats: ResolutionStats,
    ) -> str | None:
        # 1. Same-file lookup first: a sibling definition wins over
        #    any imported binding with the same name.
        same_file = index.by_location.get((rel.file_path, name), [])
        if len(same_file) == 1:
            stats.same_file_resolved += 1
            return self._fqn_for_entity(same_file[0], repo_id)
        if len(same_file) > 1:
            stats.ambiguous_skipped += 1
            return None

        # 2. Direct-import lookup: ``from X import name`` -> resolve
        #    to entity ``name`` in module X.
        bindings = index.file_imports.get(rel.file_path, {})
        if name in bindings:
            source_module = bindings[name]
            entity = self._lookup_in_module(source_module, name, index)
            if entity is not None:
                stats.direct_import_resolved += 1
                return self._fqn_for_entity(entity, repo_id)

        stats.unresolved += 1
        return None

    def _resolve_module_prefix(
        self,
        head: str,
        rest: str,
        rel: CodeRelationship,
        index: _RepoIndex,
        repo_id: str,
        stats: ResolutionStats,
    ) -> str | None:
        """Resolve ``head.rest`` where ``head`` is a module alias.

        After ``import utils``, the call ``utils.helper()`` is rendered
        by the parser as ``target_name="utils.helper"``; ``head`` is
        the local module binding, ``rest`` is the symbol path inside
        that module.
        """
        bindings = index.file_imports.get(rel.file_path, {})
        if head not in bindings:
            stats.unresolved += 1
            return None

        source_module = bindings[head]
        # Only the leaf segment is the entity name; intermediate
        # segments would be sub-modules or class scopes which Tier 1
        # does not traverse.
        leaf = rest.rsplit(".", 1)[-1]
        entity = self._lookup_in_module(source_module, leaf, index)
        if entity is None:
            stats.unresolved += 1
            return None

        stats.module_prefix_resolved += 1
        return self._fqn_for_entity(entity, repo_id)

    def _lookup_in_module(
        self,
        module_path: str,
        name: str,
        index: _RepoIndex,
    ) -> CodeEntity | None:
        """Find a single entity named ``name`` in module ``module_path``.

        Returns ``None`` when the module has no matching file (cross-
        package import) or the name is ambiguous (overloads, multi-
        file module). Tier 1 never guesses across multiple matches.
        """
        files = index.module_to_files.get(module_path, [])
        if not files:
            return None

        candidates: list[CodeEntity] = []
        for file_path in files:
            candidates.extend(index.by_location.get((file_path, name), []))

        if len(candidates) == 1:
            return candidates[0]
        return None

    @staticmethod
    def _fqn_for_entity(entity: CodeEntity, repo_id: str) -> str:
        """Compute the canonical FQN for an entity.

        The FQNBuilder used at write time assigns ``@N`` disambiguators
        for collisions in declaration order. Tier 1 only resolves to
        unambiguous entities (single match), so the FQN it computes
        has no disambiguator and matches the FQN written for the
        first emission of that name.
        """
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
