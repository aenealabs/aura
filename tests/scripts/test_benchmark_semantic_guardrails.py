"""Smoke test for ``scripts/benchmark_semantic_guardrails.py`` (tiny iteration count)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts" / "benchmark_semantic_guardrails.py"
)
_spec = importlib.util.spec_from_file_location("benchmark_semantic_guardrails", _SCRIPT)
bench = importlib.util.module_from_spec(_spec)
sys.modules["benchmark_semantic_guardrails"] = bench
_spec.loader.exec_module(bench)


def test_percentile_nearest_rank():
    samples = [i * 1_000_000 for i in range(1, 101)]
    assert bench.percentile(samples, 50) == 50.0
    assert bench.percentile(samples, 99) == 99.0


def test_benchmark_runs_with_tiny_iterations():
    report = bench.run(iterations=3, warmup=1, mock_l3_l4=True)
    assert set(bench.TARGETS_MS) <= set(report["layers"])
    e2e = report["layers"]["E2E deterministic (L3/L4 skipped)"]
    assert "benign_20KB_code" in e2e
    for stats in e2e.values():
        assert stats["p95_ms"] >= stats["p50_ms"] >= 0
    assert report["mock_l3_l4_full_engine"]
    assert "Machine:" in bench.render(report)
