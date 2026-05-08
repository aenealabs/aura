# ADR-090 Phase 1 Migration Runbook

**Last Updated:** May 8, 2026
**Script:** `scripts/migrate_entity_ids_adr090.py`
**Target:** Per-environment Neptune CodeEntity vertices (dev / qa / prod)
**Owner:** Platform Engineering

---

## Overview

ADR-090 Phase 1 backfills the `fqn` (fully qualified name) property on every existing CodeEntity vertex in Neptune. Vertex identity is moving from the brittle `{file_path}::{name}` scheme to a SCIP-style FQN; because Gremlin edges reference internal vertex IDs (not the `entity_id` property), the migration is a property-add. Edges keep working unchanged. Read paths prefer FQN with a fallback to legacy `entity_id` during the migration window.

The script is **idempotent and resumable**:

- Vertices already carrying an `fqn` property are skipped.
- A partial run can be re-executed safely; only un-migrated vertices are touched.
- Failures on individual vertices do not abort the run; they are collected and reported.

## Resume-Correctness Guarantees

The migration is empirically validated to converge to the same final graph state regardless of when it was interrupted. See `tests/integration/migration/test_migration_chaos.py`:

- **10 random seeds** parametrized across **3 injection points** (pre-scan, mid-batch write, last write).
- **Double-interruption** scenario (kill → resume → kill again → resume) also validated.
- Convergence assertion: byte-identical serialized graph state vs. a clean run.

Mocked Neptune throughout; entire chaos suite runs in <1 second so it gates every PR via the standard test workflow.

What this means operationally: if you `Ctrl-C` the migration, restart it, get throttled mid-batch by Neptune, restart again -- the final graph is the same as if the script ran cleanly. **You do not need to roll back state before retrying.**

## Pre-Migration Checklist

- [ ] Environment-scoped run: confirm `AWS_PROFILE` / IAM credentials target the intended environment.
- [ ] `--dry-run` first on every environment. Inspect counts; expected `Migrated` should be approximately equal to `Scanned` minus `Already migrated` minus `Missing repo` on the first real run.
- [ ] Snapshot Neptune (cluster snapshot via AWS console / CLI) before running on prod for the first time. Not required for re-runs.
- [ ] Validate the connection by running `--repo` against a single repository before `--all`.

## Standard Invocation

```bash
# Dry-run (computes assignments, writes nothing)
python -m scripts.migrate_entity_ids_adr090 --all --dry-run

# Single repository
python -m scripts.migrate_entity_ids_adr090 --repo owner/repo

# Full graph
python -m scripts.migrate_entity_ids_adr090 --all
```

## Disambiguation Rule

Within a `(repository, file_path, parent, name, type)` collision bucket, vertices are sorted by `line_number` (ascending) and assigned `@0`, `@1`, ... in that order. `@0` is omitted from the FQN string per ADR-090 convention. This ordering is stable across re-runs: previously-assigned suffixes are preserved when new entries are added to a bucket.

## Failure Modes

| Symptom | Likely cause | Action |
| --- | --- | --- |
| Exit code 1, stderr lists per-entity errors | Per-vertex Neptune write failure (transient throttling, malformed metadata) | Re-run the same command; only the failed vertices will be retried. |
| `Scanned: 0` | Wrong `--repo` filter, or empty graph | Verify the repository identifier matches the `repository` property on existing vertices. |
| `Skipped missing repo` count > 0 | Vertices lack repository metadata (older ingestion data) | Expected for legacy data; vertices stay un-migrated and continue to use the legacy `entity_id` lookup path until re-ingested. |
| Process killed mid-run | Operator action / OOM / instance recycle | Re-run; convergence is guaranteed (see "Resume-Correctness Guarantees" above). |

## Rollback

The migration is property-add only, so rollback is "remove the `fqn` property from every vertex." This is rarely needed because the read path falls back to legacy `entity_id` lookup automatically. If a rollback is genuinely required:

```gremlin
g.V().hasLabel('CodeEntity').properties('fqn').drop()
```

Run that against the target environment's Neptune endpoint via the gremlin console. The script is then safe to re-run from scratch.

## References

- ADR-090: `docs/architecture-decisions/ADR-090-graphrag-ingestion-edge-completeness.md`
- Script: `scripts/migrate_entity_ids_adr090.py`
- Happy-path tests: `tests/test_migrate_entity_ids_adr090.py`
- Chaos tests: `tests/integration/migration/test_migration_chaos.py`
- Issue: #119
