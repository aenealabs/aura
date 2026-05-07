"""
Project Aura - SWE-Bench Pro Adapter.

Runs Aura's vulnerability-scanner / agent pipeline against the
SWE-Bench Pro benchmark (Scale AI, 2025; 1,865 tasks across 41
professional repositories, public subset of 731 instances).

Per the project's strategic positioning, SWE-Bench Pro is NOT
Aura's primary benchmark — that role belongs to security-specific
suites (CVE-Bench, OWASP Benchmark v1.2, NIST SARD Juliet). SWE-Bench
Pro is run as a baseline reference: how does a security-tuned
platform perform on general-purpose bug-fixing? The answer is useful
for context in investor / design-partner conversations and informs
the roadmap.

Usage (high level):

    1. Load a task subset:
       ``tasks = load_subset(n=30, repo_filter=None)``
    2. Generate predictions via an Adapter:
       ``predictions = await run(tasks, adapter=AuraBedrockAdapter(...))``
    3. Write the SWE-Bench-formatted JSON:
       ``write_submission(predictions, "predictions.json")``
    4. Run the official harness in Docker:
       ``python -m swebench.harness.run_evaluation \\
            --predictions_path predictions.json \\
            --dataset_name ScaleAI/SWE-bench_Pro \\
            --use_local_docker``

Author: Project Aura Team
Created: 2026-05-07
"""

from .adapter import Adapter, AdapterError, BatchAdapter
from .contracts import (
    SWEBenchPrediction,
    SWEBenchResult,
    SWEBenchTask,
    TaskOutcome,
)
from .enhanced_adapter import (
    AuraEnhancedAdapter,
    CannedRetriever,
    NullReviewer,
    NullRetriever,
    Reviewer,
    ReviewResult,
    RepoContextRetriever,
    ScriptedReviewer,
    StubReviewer,
    StubRetriever,
)
from .mock_adapter import (
    DeterministicMockAdapter,
    EmptyPatchAdapter,
    StubAdapter,
)
from .runner import RunReport, run
from .scoring import (
    SimilarityReport,
    TaskSimilarityScore,
    parse_unified_diff,
    score_one,
    score_predictions,
)
from .submission import write_submission

__all__ = [
    "Adapter",
    "AdapterError",
    "AuraEnhancedAdapter",
    "BatchAdapter",
    "CannedRetriever",
    "DeterministicMockAdapter",
    "EmptyPatchAdapter",
    "NullReviewer",
    "NullRetriever",
    "RepoContextRetriever",
    "Reviewer",
    "ReviewResult",
    "RunReport",
    "ScriptedReviewer",
    "SimilarityReport",
    "StubAdapter",
    "StubReviewer",
    "StubRetriever",
    "SWEBenchPrediction",
    "SWEBenchResult",
    "SWEBenchTask",
    "TaskOutcome",
    "TaskSimilarityScore",
    "parse_unified_diff",
    "run",
    "score_one",
    "score_predictions",
    "write_submission",
]
