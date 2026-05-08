#!/usr/bin/env python3
"""Project Aura - ADR-090 Phase 1: Backfill FQN property on existing graphs.

Per ADR-090, vertex identity is moving from the brittle
``{file_path}::{name}`` scheme to a SCIP-style fully qualified name.
Because Gremlin edges reference internal vertex IDs (not the
``entity_id`` property), the migration is a property-add: every
existing CodeEntity vertex gains an ``fqn`` property. Edges keep
working unchanged. Read paths prefer FQN lookup with a fallback to
``entity_id`` during the migration window.

This script is idempotent and resumable:

- Vertices already carrying an ``fqn`` property are skipped.
- A partial run can be re-executed safely; only un-migrated vertices
  are touched.
- Failures on individual vertices do not abort the run; they are
  collected and reported.

Disambiguation strategy: within a single (repository, file_path,
parent, name, type) collision bucket, vertices are sorted by
``line_number`` (ascending) and assigned ``@0``, ``@1``, ... in that
order. ``@0`` is omitted from the FQN string per ADR-090 convention.

Usage:

    python -m scripts.migrate_entity_ids_adr090 --repo owner/repo
    python -m scripts.migrate_entity_ids_adr090 --all
    python -m scripts.migrate_entity_ids_adr090 --repo owner/repo --dry-run

Exit codes:
    0 - Migration completed without errors
    1 - One or more vertices failed to migrate; see stderr

Author: Project Aura Team
Created: 2026-05-08
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from src.services.graph.fqn import compute_fqn
from src.services.neptune_graph_service import (
    NeptuneError,
    NeptuneGraphService,
    NeptuneMode,
    escape_gremlin_string,
)

logger = logging.getLogger(__name__)


@dataclass
class MigrationStats:
    """Summary of a migration run."""

    scanned: int = 0
    migrated: int = 0
    skipped_already_migrated: int = 0
    skipped_missing_repo: int = 0
    failed: int = 0
    errors: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


def _entity_collision_key(entity: dict) -> tuple[str, str, str, str, str]:
    """Group key for disambiguation.

    Two entities in the same file with the same name, type, and
    parent are considered overload candidates and are sorted by
    line_number to assign ascending suffixes.
    """
    return (
        str(entity.get("metadata", {}).get("repository", "")),
        str(entity.get("file_path", "")),
        str(entity.get("parent", "")),
        str(entity.get("name", "")),
        str(entity.get("type", "")),
    )


def _build_fqn_for_entity(
    entity: dict,
    disambiguator: int | None,
) -> str | None:
    """Compute the FQN for a single entity dict, or None if data is insufficient."""
    name = entity.get("name")
    kind = entity.get("type")
    file_path = entity.get("file_path")
    repo_id = entity.get("metadata", {}).get("repository")
    if not (name and kind and file_path and repo_id):
        return None

    parent = entity.get("parent")
    parent_chain: tuple[str, ...] = (parent,) if parent else ()

    return compute_fqn(
        name=str(name),
        kind=str(kind),
        file_path=str(file_path),
        repo_id=str(repo_id),
        parent_chain=parent_chain,
        disambiguator=disambiguator,
    )


def _assign_disambiguators(
    all_entities: Iterable[dict],
) -> list[tuple[dict, int | None]]:
    """Assign disambiguator suffixes within each collision bucket.

    All entities — migrated and unmigrated — participate in the index
    assignment so partial re-runs remain stable: an entity that
    received ``@1`` on the first migration is still ``@1`` on a re-run
    that adds new entries. Entities that already carry an ``fqn`` are
    excluded from the returned assignments (no rewrite).

    Sort key is ``(line_number, entity_id)`` so re-runs produce
    deterministic assignments even when two entities share a line.
    """
    groups: dict[tuple[str, str, str, str, str], list[dict]] = defaultdict(list)
    for entity in all_entities:
        groups[_entity_collision_key(entity)].append(entity)

    assignments: list[tuple[dict, int | None]] = []
    for group_entities in groups.values():
        group_entities.sort(
            key=lambda e: (
                int(e.get("line_number", 0) or 0),
                str(e.get("id") or e.get("entity_id") or ""),
            )
        )
        for index, entity in enumerate(group_entities):
            if entity.get("fqn"):
                # Already migrated; index participates in the count
                # (so newly-added entries get the right suffix) but is
                # not rewritten.
                continue
            disambiguator = None if index == 0 else index
            assignments.append((entity, disambiguator))

    return assignments


def _iter_mock_entities(
    service: NeptuneGraphService,
    repo_filter: str | None,
) -> list[dict]:
    """Return a list of entity dicts in mock mode."""
    entities: list[dict] = []
    for entity_id, record in service.mock_graph.items():
        # Mock-mode records lack the entity_id key; fold it in.
        merged = dict(record)
        merged.setdefault("id", entity_id)
        merged.setdefault("entity_id", entity_id)
        if repo_filter is not None:
            if merged.get("metadata", {}).get("repository") != repo_filter:
                continue
        entities.append(merged)
    return entities


def _iter_neptune_entities(
    service: NeptuneGraphService,
    repo_filter: str | None,
) -> list[dict]:
    """Return all CodeEntity vertices in real Neptune mode."""
    if repo_filter:
        safe_repo = escape_gremlin_string(repo_filter)
        query = (
            f"g.V().hasLabel('CodeEntity')"
            f".has('repository', '{safe_repo}')"
            f".valueMap(true)"
        )
    else:
        query = "g.V().hasLabel('CodeEntity').valueMap(true)"

    result = service.client.submit(query).all().result()
    entities: list[dict] = []
    for vertex in result:
        # Neptune valueMap returns property values wrapped in lists; flatten.
        flat = {
            key: (value[0] if isinstance(value, list) and value else value)
            for key, value in vertex.items()
        }
        # The 'repository' property lives at the top level in Gremlin output;
        # mirror the mock-mode metadata layout for downstream code.
        if "repository" in flat:
            flat.setdefault("metadata", {})["repository"] = flat["repository"]
        entities.append(flat)
    return entities


def _write_fqn_mock(service: NeptuneGraphService, entity: dict, fqn: str) -> None:
    """Set the fqn property on a mock-mode vertex."""
    entity_id = entity.get("entity_id") or entity.get("id")
    if entity_id and entity_id in service.mock_graph:
        service.mock_graph[entity_id]["fqn"] = fqn


def _write_fqn_neptune(service: NeptuneGraphService, entity: dict, fqn: str) -> None:
    """Set the fqn property on a real Neptune vertex."""
    entity_id = entity.get("entity_id") or entity.get("id")
    if not entity_id:
        raise NeptuneError("Entity has no entity_id; cannot write fqn")
    safe_id = escape_gremlin_string(str(entity_id))
    safe_fqn = escape_gremlin_string(fqn)
    query = f"g.V().has('entity_id', '{safe_id}')" f".property('fqn', '{safe_fqn}')"
    service.client.submit(query).all().result()


def migrate(
    service: NeptuneGraphService,
    repo_filter: str | None = None,
    dry_run: bool = False,
) -> MigrationStats:
    """Run the FQN backfill against the supplied Neptune service.

    Args:
        service: NeptuneGraphService instance. Mode is honored;
            mock-mode runs are useful for tests and dry-runs in CI.
        repo_filter: Restrict migration to a single repository.
        dry_run: Compute and report assignments without writing.

    Returns:
        MigrationStats summarizing the run.
    """
    stats = MigrationStats()

    if service.mode == NeptuneMode.MOCK:
        entities = _iter_mock_entities(service, repo_filter)
    else:
        entities = _iter_neptune_entities(service, repo_filter)

    stats.scanned = len(entities)
    stats.skipped_already_migrated = sum(1 for e in entities if e.get("fqn"))

    # Pass every entity (migrated and unmigrated) into disambiguator
    # assignment so re-runs over partially-migrated buckets preserve
    # the previously-assigned suffixes and append the next available
    # index to new entries.
    assignments = _assign_disambiguators(entities)

    for entity, disambiguator in assignments:
        fqn = _build_fqn_for_entity(entity, disambiguator)
        if fqn is None:
            stats.skipped_missing_repo += 1
            continue
        if dry_run:
            stats.migrated += 1
            continue
        try:
            if service.mode == NeptuneMode.MOCK:
                _write_fqn_mock(service, entity, fqn)
            else:
                _write_fqn_neptune(service, entity, fqn)
            stats.migrated += 1
        except Exception as exc:  # pragma: no cover - defensive
            stats.failed += 1
            stats.errors.append(f"{entity.get('entity_id', '<unknown>')}: {exc}")

    return stats


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "ADR-090 Phase 1: backfill the fqn property on existing "
            "CodeEntity vertices."
        )
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument(
        "--repo",
        help="Migrate a specific repository (e.g. owner/repo).",
    )
    target.add_argument(
        "--all",
        action="store_true",
        help="Migrate every repository in the graph.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute assignments without writing them.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock NeptuneGraphService (testing only; no real graph).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.mock:
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)
    else:
        service = NeptuneGraphService(mode=NeptuneMode.AWS)

    repo_filter = None if args.all else args.repo
    stats = migrate(service, repo_filter=repo_filter, dry_run=args.dry_run)

    print(
        f"Scanned: {stats.scanned} | "
        f"Migrated: {stats.migrated} | "
        f"Already migrated: {stats.skipped_already_migrated} | "
        f"Missing repo: {stats.skipped_missing_repo} | "
        f"Failed: {stats.failed}"
    )
    if stats.errors:
        for err in stats.errors:
            print(err, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
