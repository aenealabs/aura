#!/usr/bin/env python3
"""
Project Aura - SWE-Bench Pro Benchmark Runner.

Drives Aura's pipeline against a configurable subset of SWE-Bench Pro
and writes a submission file the official Docker harness consumes.

Workflow:

    1. python scripts/benchmarks/run_swe_bench_pro.py \\
           --subset 30 \\
           --out predictions.json \\
           --metadata metadata.json

    2. python -m swebench.harness.run_evaluation \\
           --predictions_path predictions.json \\
           --dataset_name ScaleAI/SWE-bench_Pro \\
           --use_local_docker

The script does NOT run the official harness — that requires Docker
on the invoking machine and is intentionally separate. Aura's job
ends at producing the predictions JSON.

Three modes:

- ``--mode stub`` (default): no AWS needed; validates the wiring.
- ``--mode bedrock``: real Aura+Bedrock adapter; defaults to current
  Sonnet-class flagship. Use ``--model-id`` to choose a specific
  model (Sonnet, Haiku, Opus, or any non-Anthropic Bedrock model
  Aura supports via its Cloud Abstraction Layer). Costs depend on
  model choice; produces a submission file the official Docker
  harness consumes.
- ``--mode unofficial``: real Bedrock adapter but defaulting to a
  current cheap Haiku-class model AND running heuristic similarity
  scoring in-process instead of the Docker harness. Run typically
  finishes in 5-10 minutes for 30 tasks. Output is a triage signal,
  NOT a correctness benchmark — see scoring.py for the caveats.

Aura is multi-provider via ADR-004's Cloud Abstraction Layer. While
this script defaults to Bedrock-hosted Claude, the same adapter
shape works against any LLMService implementation (Llama / Mistral
on Bedrock, Gemini on Vertex AI, GPT-class on Azure / OpenAI).
Substitute by injecting a different ``LLMClient`` into
``AuraBedrockAdapter`` directly.

Author: Project Aura Team
Created: 2026-05-07
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Make the package importable when invoking the script directly.
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from src.benchmarks.swe_bench_pro import (  # noqa: E402
    StubAdapter,
    run,
    write_submission,
)
from src.benchmarks.swe_bench_pro.dataset import load_subset  # noqa: E402
from src.benchmarks.swe_bench_pro.submission import write_metadata  # noqa: E402

logger = logging.getLogger("aura.benchmarks.swe_bench_pro")


# Default model SKUs. Aura is multi-provider via the Cloud Abstraction
# Layer (ADR-004); these defaults reflect the current Claude generation
# on Bedrock as of May 2026. Pass ``--model-id`` to override with any
# other Bedrock model (Claude older gens, Llama, Mistral, Cohere, AI21)
# or run against an Azure / Vertex / OpenAI deployment by injecting a
# different LLMService.
_UNOFFICIAL_DEFAULT_MODEL = "anthropic.claude-haiku-4-5-20251001"
_BEDROCK_DEFAULT_MODEL = "anthropic.claude-sonnet-4-6"
# Flagship for highest-quality runs. Opus 4.7 is premium-priced — only
# selected explicitly via ``--model-id``, never as a default.
_FLAGSHIP_MODEL = "anthropic.claude-opus-4-7"


def _build_adapter(mode: str, model_id: str | None):
    """Construct the adapter the user requested."""
    if mode == "stub":
        return StubAdapter()
    if mode in ("bedrock", "unofficial"):
        # Lazy import so users without boto3 / Bedrock access can still
        # run the stub mode against the dataset loader.
        from src.benchmarks.swe_bench_pro.aura_adapter import (
            AuraBedrockAdapter,
        )

        chosen = model_id or (
            _UNOFFICIAL_DEFAULT_MODEL
            if mode == "unofficial"
            else _BEDROCK_DEFAULT_MODEL
        )

        # Production wiring: pass the project's Bedrock LLM client. To keep
        # this script free of Bedrock SDK imports for users on the stub
        # path, the import is deferred and constructed inline.
        from src.services.bedrock_llm_service import (  # type: ignore
            BedrockLLMClient,
        )

        client = BedrockLLMClient()  # uses AWS default credentials chain
        # Unofficial mode caps spend hard — even cheaper-model runs can
        # surprise an operator if the dataset has very long issues.
        cap = 5.0 if mode == "unofficial" else 100.0
        return AuraBedrockAdapter(
            llm_client=client,
            model_id=chosen,
            run_cost_cap_usd=cap,
        )
    raise SystemExit(
        f"unknown --mode {mode!r}; use 'stub', 'bedrock', or 'unofficial'"
    )


async def _amain(args: argparse.Namespace) -> int:
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )
    repos = args.repo or None
    logger.info(
        "Loading SWE-Bench Pro subset: n=%d repos=%s",
        args.subset,
        repos,
    )
    tasks = load_subset(
        n=args.subset,
        repo_filter=repos,
        seed=args.seed,
    )
    logger.info("Loaded %d tasks", len(tasks))

    adapter = _build_adapter(args.mode, args.model_id)
    logger.info("Adapter: %s (mode=%s)", adapter.model_name, args.mode)

    report = await run(
        tasks,
        adapter=adapter,
        max_concurrency=args.concurrency,
        per_task_timeout_seconds=args.timeout,
    )
    out = write_submission(report.predictions, args.out)
    logger.info("Submission written to %s", out)

    if args.metadata:
        meta = write_metadata(report.results, args.metadata)
        logger.info("Telemetry written to %s", meta)

    from src.benchmarks.swe_bench_pro.contracts import TaskOutcome

    generated_count = report.outcome_counts.get(TaskOutcome.GENERATED, 0)
    print(
        f"\nSWE-Bench Pro run summary "
        f"({adapter.model_name}, {args.mode} mode):"
    )
    print(f"  Tasks attempted:        {report.total_tasks}")
    print(
        f"  Patches generated:      {generated_count} "
        f"({report.patch_generation_rate:.1%})"
    )
    for outcome, count in report.outcome_counts.items():
        outcome_label = (
            outcome.value if hasattr(outcome, "value") else str(outcome)
        )
        print(f"    {outcome_label}: {count}")
    print(f"  Total cost:             ${report.total_cost_usd:.2f}")
    print(f"  Mean duration:          {report.mean_duration_seconds:.1f}s")
    print(f"  Submission file:        {out}")

    if args.mode == "unofficial":
        from src.benchmarks.swe_bench_pro.dataset import load_gold_patches
        from src.benchmarks.swe_bench_pro.scoring import score_predictions

        instance_ids = [t.instance_id for t in tasks]
        gold = load_gold_patches(instance_ids)
        scored = score_predictions(report.predictions, gold)
        print("\nUnofficial heuristic similarity scoring:")
        print(f"  In-neighborhood rate:   {scored.in_neighborhood_rate:.1%} "
              f"({scored.in_neighborhood_count}/{scored.total_tasks})")
        print(f"  Mean file F1:           {scored.mean_file_f1:.3f}")
        print(f"  Mean hunk overlap:      {scored.mean_hunk_overlap_rate:.3f}")
        print(f"  Mean token Jaccard:     {scored.mean_token_jaccard:.3f}")
        print(f"  Mean composite:         {scored.mean_composite:.3f}")
        print(
            "\nReminder: heuristic similarity is a TRIAGE signal, NOT a "
            "correctness metric. For a real correctness score, run --mode "
            "bedrock and pass predictions.json to the official harness."
        )
    else:
        print(
            "\nNext step: run the official harness to evaluate correctness:\n"
            f"  python -m swebench.harness.run_evaluation \\\n"
            f"      --predictions_path {out} \\\n"
            f"      --dataset_name ScaleAI/SWE-bench_Pro \\\n"
            f"      --use_local_docker"
        )
    return 0


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--subset",
        type=int,
        default=30,
        help="Number of tasks to run (default: 30; public set has 731).",
    )
    p.add_argument(
        "--repo",
        action="append",
        default=[],
        help="Filter to specific repos (repeatable). e.g. --repo django/django",
    )
    p.add_argument(
        "--mode",
        choices=("stub", "bedrock", "unofficial"),
        default="stub",
        help=(
            "Adapter to use. 'stub' for wire-up validation; "
            "'bedrock' for the real Aura+Bedrock adapter (Sonnet by "
            "default; submission piped to the official Docker harness); "
            "'unofficial' for cheap-model (Haiku) runs scored in-process "
            "via heuristic patch-similarity (no Docker, ~$0.25 for 30 tasks)."
        ),
    )
    p.add_argument(
        "--model-id",
        default=None,
        help="Bedrock model id when --mode bedrock "
        "(e.g. anthropic.claude-3-5-sonnet-20241022-v2:0)",
    )
    p.add_argument(
        "--out",
        default="swe_bench_pro_predictions.json",
        help="Where to write the submission JSON.",
    )
    p.add_argument(
        "--metadata",
        default="swe_bench_pro_metadata.json",
        help="Where to write the Aura-side telemetry file. "
        "Pass empty string to skip.",
    )
    p.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Max concurrent in-flight tasks (default: 4).",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=600.0,
        help="Per-task timeout in seconds (default: 600).",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Shuffle seed for reproducibility (default: 42).",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose logging.",
    )
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(asyncio.run(_amain(_parse_args())))
