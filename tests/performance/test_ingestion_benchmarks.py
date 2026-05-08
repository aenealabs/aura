"""ADR-090 ingestion performance gates (issue #117).

Benchmarks the GitIngestionService end-to-end pipeline against a
medium fixture and asserts the timings stay within calibrated
thresholds:

- Ingestion p95 latency < baseline_p95 × 1.20
- Throughput edges/sec > baseline × 0.80
- Peak RSS < 2 GB hard cap

Per #117, this suite runs on a pinned ``ubuntu-latest-large`` runner
in ``.github/workflows/benchmarks.yml`` -- *not* the main PR pipeline.
Default ``pytest tests/`` collection ignores ``tests/performance/``
via ``pyproject.toml`` ``addopts`` so contributors do not pay the
benchmark cost on every PR.

Local invocation::

    pytest tests/performance/test_ingestion_benchmarks.py --no-cov -v

Re-baselining procedure: see ``tests/performance/README.md``.
"""

from __future__ import annotations

import asyncio
import json
import resource
import statistics
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.agents.ast_parser_agent import ASTParserAgent
from src.services.git_ingestion_service import GitIngestionService
from src.services.neptune_graph_service import NeptuneGraphService, NeptuneMode

_BASELINES_PATH = Path(__file__).parent / "baselines.json"
_BASELINES = json.loads(_BASELINES_PATH.read_text())

# Per #117: 20% latency drift fails. 20% throughput drop fails.
_LATENCY_REGRESSION_THRESHOLD = 1.20
_THROUGHPUT_REGRESSION_THRESHOLD = 0.80

# Hard cap on peak RSS regardless of baseline.
_PEAK_RSS_CAP_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB

# Measurement schedule per #117: 3 warmup + 5 measurement runs.
_WARMUP_RUNS = 3
_MEASURED_RUNS = 5

# Medium fixture sizing. 50 files of representative complexity gives
# a workload that's substantial enough to reveal regressions but
# completes in well under a minute even on shared CI runners.
_MEDIUM_FIXTURE_FILE_COUNT = 50


def _generate_medium_repo(repo: Path, file_count: int) -> None:
    """Synthesize ``file_count`` Python files of mixed shape:
    imports, a class, methods, and intra-class calls. The workload is
    large enough to exercise per-file parser paths and the relationship
    extractor without running into clone-time variance on a real
    GitHub repository.
    """
    for i in range(file_count):
        contents = "\n".join(
            [
                "import json",
                "from typing import Any",
                "",
                f"class Service{i}:",
                "    def init(self):",
                f"        self.config = json.dumps({{'service': {i}}})",
                "    def helper(self):",
                "        return self.init()",
                "    def main(self):",
                "        result = self.helper()",
                "        return result",
                "    def fallback(self):",
                "        return self.main()",
                "",
                f"def module_helper_{i}(svc: Service{i}):",
                "    return svc.fallback()",
                "",
            ]
        )
        (repo / f"module_{i:03d}.py").write_text(contents)


def _measure_peak_rss_bytes() -> int:
    """Return peak resident set size in bytes.

    ``ru_maxrss`` is reported in bytes on macOS and in kilobytes on
    Linux (per ``man getrusage``). The benchmarks workflow runs on
    Linux; tests running locally on macOS will see correct units too.
    """
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return int(raw)
    return int(raw) * 1024


async def _run_ingestion(
    repo: Path,
    neptune: NeptuneGraphService,
    ingestion_service: GitIngestionService,
) -> tuple[int, int]:
    """Execute one full ingestion pass against the medium fixture.

    Returns (entity_count, edge_count) for throughput accounting.
    """
    files = list(repo.glob("**/*.py"))
    entities, relationships = await ingestion_service._parse_files_with_relationships(
        files, repo
    )
    await ingestion_service._populate_graph(
        entities,
        "https://github.com/owner/repo",
        "main",
        relationships=relationships,
    )
    return len(entities), len(neptune.mock_edges)


@pytest.fixture(scope="module")
def medium_repo():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "medium-fixture"
        repo.mkdir()
        _generate_medium_repo(repo, _MEDIUM_FIXTURE_FILE_COUNT)
        yield repo


@pytest.fixture
def neptune():
    svc = NeptuneGraphService(mode=NeptuneMode.MOCK)
    svc.mock_graph.clear()
    svc.mock_edges.clear()
    return svc


@pytest.fixture
def ingestion_service(neptune: NeptuneGraphService):
    with tempfile.TemporaryDirectory() as tmp:
        yield GitIngestionService(
            neptune_service=neptune,
            opensearch_service=MagicMock(
                index_embedding=MagicMock(return_value=True)
            ),
            embedding_service=MagicMock(
                generate_embedding=MagicMock(return_value=[0.1] * 1024)
            ),
            ast_parser=ASTParserAgent(),
            observability_service=MagicMock(),
            clone_base_path=tmp,
        )


def _measured_run(
    repo: Path,
    neptune: NeptuneGraphService,
    ingestion_service: GitIngestionService,
) -> tuple[float, int, int]:
    """One measured ingestion: returns (elapsed_seconds, entities,
    edges). Resets the mock graph beforehand."""
    neptune.mock_graph.clear()
    neptune.mock_edges.clear()
    t0 = time.perf_counter()
    entities, edges = asyncio.run(_run_ingestion(repo, neptune, ingestion_service))
    elapsed = time.perf_counter() - t0
    return elapsed, entities, edges


@pytest.mark.performance
def test_ingestion_p95_latency_within_threshold(
    medium_repo: Path,
    neptune: NeptuneGraphService,
    ingestion_service: GitIngestionService,
) -> None:
    """p95 latency on the medium fixture < baseline × 1.20."""
    for _ in range(_WARMUP_RUNS):
        _measured_run(medium_repo, neptune, ingestion_service)

    timings: list[float] = []
    for _ in range(_MEASURED_RUNS):
        elapsed, _e, _r = _measured_run(medium_repo, neptune, ingestion_service)
        timings.append(elapsed)

    sorted_t = sorted(timings)
    # With 5 measurements, p95 is best approximated by the maximum;
    # statistically that's the 100th percentile, but with a 20%
    # threshold the difference is irrelevant in practice and using
    # max is the strictest interpretation.
    p95 = sorted_t[-1]
    median = statistics.median(timings)
    baseline = float(_BASELINES["ingestion_p95_seconds"])
    threshold = baseline * _LATENCY_REGRESSION_THRESHOLD

    assert p95 < threshold, (
        f"Ingestion p95 latency {p95:.3f}s exceeded threshold "
        f"{threshold:.3f}s (baseline {baseline:.3f}s × "
        f"{_LATENCY_REGRESSION_THRESHOLD}). All timings: "
        f"{[f'{t:.3f}' for t in timings]}, median {median:.3f}s. "
        f"See tests/performance/README.md to update baselines after "
        f"a deliberate perf change."
    )


@pytest.mark.performance
def test_ingestion_throughput_within_threshold(
    medium_repo: Path,
    neptune: NeptuneGraphService,
    ingestion_service: GitIngestionService,
) -> None:
    """Median throughput edges/sec > baseline × 0.80."""
    for _ in range(_WARMUP_RUNS):
        _measured_run(medium_repo, neptune, ingestion_service)

    edges_per_sec_samples: list[float] = []
    for _ in range(_MEASURED_RUNS):
        elapsed, _e, edges = _measured_run(
            medium_repo, neptune, ingestion_service
        )
        edges_per_sec_samples.append(edges / elapsed)

    median_eps = statistics.median(edges_per_sec_samples)
    baseline = float(_BASELINES["edges_per_second"])
    threshold = baseline * _THROUGHPUT_REGRESSION_THRESHOLD

    assert median_eps > threshold, (
        f"Ingestion throughput {median_eps:.1f} edges/sec is below "
        f"threshold {threshold:.1f} (baseline {baseline:.1f} × "
        f"{_THROUGHPUT_REGRESSION_THRESHOLD}). Samples: "
        f"{[f'{x:.1f}' for x in edges_per_sec_samples]}. "
        f"See tests/performance/README.md to update baselines after "
        f"a deliberate perf change."
    )


@pytest.mark.performance
def test_ingestion_peak_rss_under_hard_cap(
    medium_repo: Path,
    neptune: NeptuneGraphService,
    ingestion_service: GitIngestionService,
) -> None:
    """Peak RSS at end of run < 2 GB hard cap."""
    for _ in range(_WARMUP_RUNS):
        _measured_run(medium_repo, neptune, ingestion_service)
    for _ in range(_MEASURED_RUNS):
        _measured_run(medium_repo, neptune, ingestion_service)

    peak_rss = _measure_peak_rss_bytes()
    cap_gb = _PEAK_RSS_CAP_BYTES / (1024**3)
    peak_gb = peak_rss / (1024**3)
    assert peak_rss < _PEAK_RSS_CAP_BYTES, (
        f"Peak RSS {peak_gb:.2f} GB exceeded hard cap {cap_gb:.2f} GB. "
        f"Investigate memory regression in ingestion path."
    )
