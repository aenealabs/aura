"""ADR-090 Phase 1 migration chaos test.

Per issue #119 (Kelly's closeout P1 #7).

The Phase 1 migration backfills ``fqn`` properties on every CodeEntity
vertex. The script is documented as idempotent and resumable. This
test injects ``KeyboardInterrupt`` at randomly-chosen points during a
migration run, resumes the migration, and asserts byte-identical
convergence to a clean-run baseline.

Three injection points exercised across the seed sweep:

- ``pre-scan``: raised before any vertex is read from the graph.
- ``mid-batch``: raised at a randomly-chosen iteration inside the
  write loop.
- ``last-write``: raised on the final write call before the loop
  exits. This is the closest mock-mode analog to "final commit"
  failure -- in real Neptune the property write *is* the commit, so
  the relevant failure mode is "write didn't happen" rather than
  "write happened but commit didn't acknowledge".

Parametrized over ten seeds so any non-deterministic resume behaviour
surfaces. ``seed % 3`` deterministically distributes injections
across the three semantic points so the parameter sweep cannot miss
one by chance. Mock Neptune throughout; runs in well under 30s/seed.
"""

from __future__ import annotations

import json
import random
from unittest.mock import patch

import pytest

from scripts import migrate_entity_ids_adr090 as migration_module
from scripts.migrate_entity_ids_adr090 import migrate
from src.services.neptune_graph_service import NeptuneGraphService, NeptuneMode


_REPO = "owner/repo"


def _seed_workload(svc: NeptuneGraphService) -> None:
    """Insert a deterministic workload spanning collision buckets and
    standalone entities. The mix is chosen to make disambiguator
    ordering observable: re-running migration on a partially-migrated
    graph must preserve the suffixes assigned in the first run, which
    is exactly the property the chaos test stresses."""
    # Collision bucket: 5 overloads of User.verify in src/auth.py.
    for line in (10, 20, 30, 40, 50):
        key = f"src/auth.py::verify::L{line}"
        svc.mock_graph[key] = {
            "id": key,
            "entity_id": key,
            "name": "verify",
            "type": "method",
            "file_path": "src/auth.py",
            "line_number": line,
            "parent": "User",
            "metadata": {"repository": _REPO},
        }

    # Collision bucket: 4 overloads of Repository.query in src/db.py.
    for line in (5, 15, 25, 35):
        key = f"src/db.py::query::L{line}"
        svc.mock_graph[key] = {
            "id": key,
            "entity_id": key,
            "name": "query",
            "type": "method",
            "file_path": "src/db.py",
            "line_number": line,
            "parent": "Repository",
            "metadata": {"repository": _REPO},
        }

    # Standalone classes spread across files (no collisions).
    standalone = [
        ("src/api.py", "Application"),
        ("src/api.py", "RequestHandler"),
        ("src/api.py", "ResponseBuilder"),
        ("src/auth.py", "Token"),
        ("src/auth.py", "Session"),
        ("src/db.py", "Connection"),
        ("src/db.py", "Transaction"),
        ("src/utils.py", "Logger"),
    ]
    for offset, (file_path, name) in enumerate(standalone):
        line = (offset + 1) * 100
        key = f"{file_path}::{name}::L{line}"
        svc.mock_graph[key] = {
            "id": key,
            "entity_id": key,
            "name": name,
            "type": "class",
            "file_path": file_path,
            "line_number": line,
            "parent": None,
            "metadata": {"repository": _REPO},
        }


def _serialize(svc: NeptuneGraphService) -> str:
    """Serialize the mock graph to a byte-stable JSON form for diffing.

    Sort by entity id so dict iteration order does not perturb the
    output; restrict to fields the migration is expected to leave
    deterministic so unrelated mock-mode noise doesn't trigger
    spurious diffs.
    """
    rows = sorted(
        (
            {
                "id": key,
                "fqn": record.get("fqn"),
                "name": record.get("name"),
                "type": record.get("type"),
                "file_path": record.get("file_path"),
                "line_number": record.get("line_number"),
                "parent": record.get("parent"),
            }
            for key, record in svc.mock_graph.items()
        ),
        key=lambda row: row["id"] or "",
    )
    return json.dumps(rows, sort_keys=True, indent=2)


def _fresh_service() -> NeptuneGraphService:
    svc = NeptuneGraphService(mode=NeptuneMode.MOCK)
    svc.mock_graph.clear()
    svc.mock_edges.clear()
    _seed_workload(svc)
    return svc


class _InterruptAtCount:
    """Wrap the original ``_write_fqn_mock`` so the Nth invocation
    raises ``KeyboardInterrupt`` instead of writing.

    The interrupt is raised *before* delegating to the original, so the
    Nth write does not occur -- that is the relevant failure mode for
    a write-then-commit boundary.
    """

    def __init__(self, original, fail_at: int) -> None:
        self._original = original
        self._fail_at = fail_at
        self.call_count = 0

    def __call__(self, service, entity, fqn) -> None:
        self.call_count += 1
        if self.call_count == self._fail_at:
            raise KeyboardInterrupt(
                f"Chaos: interrupt at write {self.call_count}"
            )
        return self._original(service, entity, fqn)


@pytest.fixture
def golden_state() -> str:
    """Run a clean migration on a fresh workload and capture the
    serialized graph as the convergence target for chaos runs."""
    svc = _fresh_service()
    migrate(svc)
    return _serialize(svc)


@pytest.mark.parametrize("seed", list(range(10)))
def test_chaos_resume_converges_to_golden(seed: int, golden_state: str) -> None:
    """Inject a KeyboardInterrupt at a seed-determined point, resume,
    and assert the resulting graph matches the clean-run baseline.

    ``seed % 3`` selects the injection point so the 10-seed sweep
    deterministically covers all three semantic locations:

    - ``seed % 3 == 0``: pre-scan
    - ``seed % 3 == 1``: mid-batch (random index in [1, total-1])
    - ``seed % 3 == 2``: last-write (index == total)
    """
    rng = random.Random(seed)
    svc = _fresh_service()
    total_writes = len(svc.mock_graph)
    assert total_writes >= 3, (
        "Workload must have at least three vertices for the three "
        "injection points to be distinguishable."
    )

    injection_class = seed % 3
    if injection_class == 0:
        # pre-scan: short-circuit _iter_mock_entities before any read.
        with patch.object(
            migration_module,
            "_iter_mock_entities",
            side_effect=KeyboardInterrupt("Chaos: pre-scan"),
        ):
            with pytest.raises(KeyboardInterrupt):
                migrate(svc)
        # No vertex should have an fqn yet.
        assert all("fqn" not in v for v in svc.mock_graph.values()), (
            "pre-scan injection should leave the graph fully unmigrated."
        )
    elif injection_class == 1:
        # mid-batch: wrap _write_fqn_mock to raise on a random
        # mid-loop iteration.
        injection_point = rng.randint(1, total_writes - 1)
        original = migration_module._write_fqn_mock
        wrapper = _InterruptAtCount(original, fail_at=injection_point)
        with patch.object(migration_module, "_write_fqn_mock", wrapper):
            with pytest.raises(KeyboardInterrupt):
                migrate(svc)
        assert wrapper.call_count == injection_point
        # Exactly (injection_point - 1) writes should have committed
        # before the interrupt.
        migrated_so_far = sum(1 for v in svc.mock_graph.values() if "fqn" in v)
        assert migrated_so_far == injection_point - 1
    else:
        # last-write: interrupt on the final write of the loop.
        injection_point = total_writes
        original = migration_module._write_fqn_mock
        wrapper = _InterruptAtCount(original, fail_at=injection_point)
        with patch.object(migration_module, "_write_fqn_mock", wrapper):
            with pytest.raises(KeyboardInterrupt):
                migrate(svc)
        assert wrapper.call_count == injection_point
        # Every write except the last should have committed.
        migrated_so_far = sum(1 for v in svc.mock_graph.values() if "fqn" in v)
        assert migrated_so_far == total_writes - 1

    # Resume: the migration is documented as idempotent. Running
    # migrate(svc) on a partially-migrated graph must complete the
    # remaining work and leave the graph indistinguishable from a
    # clean run.
    resume_stats = migrate(svc)
    assert resume_stats.failed == 0, (
        f"Resume run reported failures: {resume_stats.errors}"
    )

    chaos_state = _serialize(svc)
    assert chaos_state == golden_state, (
        f"Chaos run with seed={seed} (injection_class={injection_class}) "
        f"diverged from clean-run baseline.\n"
        f"--- expected ---\n{golden_state}\n"
        f"--- got ---\n{chaos_state}"
    )


def test_double_interruption_still_converges(golden_state: str) -> None:
    """Inject a chaos failure, partially recover, then inject a
    second failure mid-resume. Convergence must still hold.

    Real-world incidents rarely involve a single clean interruption;
    operator runbook flow may be: kill -> retry -> kill again -> retry.
    The migration's idempotency promise has to survive that.
    """
    svc = _fresh_service()
    total_writes = len(svc.mock_graph)

    # First interruption: kill mid-batch.
    original = migration_module._write_fqn_mock
    first_wrapper = _InterruptAtCount(original, fail_at=total_writes // 3)
    with patch.object(migration_module, "_write_fqn_mock", first_wrapper):
        with pytest.raises(KeyboardInterrupt):
            migrate(svc)

    # Second interruption: kill the resume mid-batch as well. The
    # remaining count is total_writes - (first_wrapper.call_count - 1)
    # and we want to interrupt around halfway through it.
    remaining = total_writes - (first_wrapper.call_count - 1)
    second_wrapper = _InterruptAtCount(
        original, fail_at=max(1, remaining // 2)
    )
    with patch.object(migration_module, "_write_fqn_mock", second_wrapper):
        with pytest.raises(KeyboardInterrupt):
            migrate(svc)

    # Final clean resume.
    final_stats = migrate(svc)
    assert final_stats.failed == 0
    assert _serialize(svc) == golden_state, (
        "Double-interruption sequence diverged from clean-run baseline."
    )
