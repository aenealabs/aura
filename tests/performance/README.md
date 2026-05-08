# Ingestion Performance Gates

This directory hosts the ADR-090 ingestion performance benchmarks (issue #117). The suite asserts that the GitIngestionService end-to-end pipeline stays within calibrated thresholds on a synthetic medium fixture:

| Metric | Threshold |
| --- | --- |
| Ingestion p95 latency | < `baseline_p95 × 1.20` |
| Throughput edges/sec | > `baseline_edges_per_sec × 0.80` |
| Peak RSS | < 2 GB hard cap |

## Workflow boundary

These tests do **not** run on the standard PR pipeline. They are excluded from default `pytest tests/` collection via `--ignore=tests/performance` in `pyproject.toml` `addopts`. The dedicated workflow `.github/workflows/benchmarks.yml` runs them on a pinned `ubuntu-latest-large` runner where CI variance is bounded.

Local invocation:

```bash
pytest tests/performance/test_ingestion_benchmarks.py -m performance --no-cov -v
```

## Baselines

`baselines.json` holds the reference values the assertions compare against. Two values matter:

```json
{
  "ingestion_p95_seconds": 0.5,
  "edges_per_second": 5000.0
}
```

The values committed in this initial PR are **placeholder safe values** that will pass anywhere but only catch order-of-magnitude regressions. The first authoritative baseline must be captured on the pinned `ubuntu-latest-large` runner. Until that capture happens, the suite is a smoke test, not a regression detector.

## Updating baselines after a deliberate perf change

If a perf-relevant change (parser refactor, edge-extraction rewrite, embedding pipeline change, etc.) causes the assertions to fail and the new behavior is intentional:

1. **Verify the change is intentional.** Read the PR diff. If you cannot articulate *why* the regression is acceptable in one sentence, the assertion is doing its job; investigate before touching baselines.
2. **Run the suite three times** on the same target environment (CI runner or your local machine, depending on where the regression is observed). Capture the median p95 and the median edges/sec across the three runs.
3. **Update `baselines.json`** with the new values. Round to the same precision as the existing entries.
4. **Document the rationale** in the PR description: which change prompted the rebaseline, what the old and new values are, and whether the regression is one-time (e.g., richer edge extraction added 15% latency in exchange for new functionality) or a sign of a longer trend.
5. **Get explicit reviewer sign-off** on the rebaseline. A perf regression with rebaseline is a different kind of change than a normal feature; the reviewer should be aware they are signing off on both.

## Capturing the first CI baseline

When the benchmarks workflow runs for the first time on a clean baseline:

1. Run the workflow manually via `workflow_dispatch`.
2. Read the workflow logs for the printed timings and edges/sec values.
3. Open a PR that updates `baselines.json` with the captured values, removing the "placeholder" wording from `_metadata.description`.
4. After that PR merges, the assertions are real regression gates rather than smoke tests.

## What the medium fixture exercises

`_generate_medium_repo` synthesizes 50 Python files, each containing:

- 2 imports
- 1 class with 4 methods
- 1 module-level function
- intra-class call patterns

This is enough to exercise the parser, the entity-and-relationship extractor, the FQN compute path, and the Neptune mock writes. It is *not* a replacement for ingesting a real repository -- it is a controlled, reproducible workload that catches regressions in the hot path.

## Files

- `test_ingestion_benchmarks.py` -- the benchmark suite
- `baselines.json` -- the tracked baselines (committed; updated via PR)
- `__init__.py` -- empty; makes the directory a package
- `README.md` -- this document
