"""
Tests for the SWE-Bench Pro adapter and runner.

Covers:
- Contracts: SWEBenchPrediction.to_submission_dict() shape;
  SWEBenchResult.has_patch logic
- Mock adapters: stub, empty, deterministic, error-raising
- Runner: end-to-end batch run; concurrency cap; per-task timeout;
  AdapterError handling; outcome counting; patch_generation_rate
- Submission writer: file format matches harness expectations;
  metadata file shape
- AuraBedrockAdapter: prompt construction, response parsing
  (fenced and unfenced diffs, prose-only rejection, empty patch),
  cost tracking, cost-cap halt
- Dataset row-to-task adaptation: schema-tolerant parsing of
  FAIL_TO_PASS / PASS_TO_PASS, optional fields
"""

from __future__ import annotations

import asyncio
import json
import pathlib
from typing import Any

import pytest

from src.benchmarks.swe_bench_pro.adapter import Adapter, AdapterError
from src.benchmarks.swe_bench_pro.aura_adapter import (
    AuraBedrockAdapter,
    _extract_unified_diff,
)
from src.benchmarks.swe_bench_pro.contracts import (
    SWEBenchPrediction,
    SWEBenchResult,
    SWEBenchTask,
    TaskOutcome,
)
from src.benchmarks.swe_bench_pro.dataset import _row_to_task
from src.benchmarks.swe_bench_pro.scoring import (
    HunkRange,
    parse_unified_diff,
    score_one,
    score_predictions,
)
from src.benchmarks.swe_bench_pro.mock_adapter import (
    DeterministicMockAdapter,
    EmptyPatchAdapter,
    StubAdapter,
)
from src.benchmarks.swe_bench_pro.prompts import build_user_prompt, system_prompt
from src.benchmarks.swe_bench_pro.runner import run
from src.benchmarks.swe_bench_pro.submission import (
    write_metadata,
    write_submission,
)


# =============================================================================
# Fixtures
# =============================================================================


def _task(
    instance_id: str = "django__django-12345",
    repo: str = "django/django",
    problem: str = "ValueError when X happens",
) -> SWEBenchTask:
    return SWEBenchTask(
        instance_id=instance_id,
        repo=repo,
        base_commit="abc1234def",
        problem_statement=problem,
        hints_text="",
    )


_VALID_DIFF = (
    "diff --git a/file.py b/file.py\n"
    "--- a/file.py\n"
    "+++ b/file.py\n"
    "@@ -1,1 +1,1 @@\n"
    "-old\n"
    "+new\n"
)


# =============================================================================
# Contracts
# =============================================================================


class TestContracts:
    def test_prediction_submission_dict_has_required_keys(self):
        p = SWEBenchPrediction(
            instance_id="x", model_patch="diff", model_name_or_path="m"
        )
        d = p.to_submission_dict()
        assert set(d.keys()) == {
            "instance_id",
            "model_patch",
            "model_name_or_path",
        }
        assert d["instance_id"] == "x"

    def test_result_has_patch_for_generated_with_diff(self):
        r = SWEBenchResult(
            task=_task(),
            prediction=SWEBenchPrediction(
                instance_id="x", model_patch=_VALID_DIFF, model_name_or_path="m"
            ),
            outcome=TaskOutcome.GENERATED,
            duration_seconds=1.0,
        )
        assert r.has_patch is True

    def test_result_has_patch_false_for_empty(self):
        r = SWEBenchResult(
            task=_task(),
            prediction=SWEBenchPrediction(
                instance_id="x", model_patch="", model_name_or_path="m"
            ),
            outcome=TaskOutcome.EMPTY_PATCH,
            duration_seconds=1.0,
        )
        assert r.has_patch is False

    def test_result_has_patch_false_for_error_with_text(self):
        # Even with text in the patch field, error outcomes never have_patch.
        r = SWEBenchResult(
            task=_task(),
            prediction=SWEBenchPrediction(
                instance_id="x", model_patch="diff", model_name_or_path="m"
            ),
            outcome=TaskOutcome.ADAPTER_ERROR,
            duration_seconds=1.0,
        )
        assert r.has_patch is False


# =============================================================================
# Mock adapters
# =============================================================================


class TestMockAdapters:
    @pytest.mark.asyncio
    async def test_stub_returns_fixed_patch(self):
        adapter = StubAdapter(fixed_patch=_VALID_DIFF)
        prediction = await adapter.solve(_task())
        assert prediction.model_patch == _VALID_DIFF
        assert adapter.solve_count == 1

    @pytest.mark.asyncio
    async def test_empty_adapter_returns_empty(self):
        adapter = EmptyPatchAdapter()
        prediction = await adapter.solve(_task())
        assert prediction.model_patch == ""

    @pytest.mark.asyncio
    async def test_deterministic_adapter_per_instance(self):
        adapter = DeterministicMockAdapter(
            patches={"a": _VALID_DIFF, "b": ""},
        )
        pa = await adapter.solve(_task(instance_id="a"))
        pb = await adapter.solve(_task(instance_id="b"))
        pc = await adapter.solve(_task(instance_id="c"))  # not in mapping
        assert pa.model_patch == _VALID_DIFF
        assert pb.model_patch == ""
        assert pc.model_patch == ""

    @pytest.mark.asyncio
    async def test_deterministic_adapter_raises_for_configured_ids(self):
        adapter = DeterministicMockAdapter(
            patches={"a": _VALID_DIFF},
            raise_for_ids={"a"},
        )
        with pytest.raises(AdapterError):
            await adapter.solve(_task(instance_id="a"))


# =============================================================================
# Runner
# =============================================================================


class TestRunner:
    @pytest.mark.asyncio
    async def test_empty_task_list_returns_empty_report(self):
        report = await run([], adapter=StubAdapter())
        assert report.total_tasks == 0
        assert report.results == ()
        assert report.patch_generation_rate == 0.0

    @pytest.mark.asyncio
    async def test_runner_aggregates_outcomes(self):
        adapter = DeterministicMockAdapter(
            patches={
                "a": _VALID_DIFF,
                "b": _VALID_DIFF,
                "c": "",  # empty
            },
            raise_for_ids={"d"},
        )
        tasks = [
            _task(instance_id="a"),
            _task(instance_id="b"),
            _task(instance_id="c"),
            _task(instance_id="d"),
        ]
        report = await run(tasks, adapter=adapter, max_concurrency=2)
        assert report.total_tasks == 4
        assert report.outcome_counts[TaskOutcome.GENERATED] == 2
        assert report.outcome_counts[TaskOutcome.EMPTY_PATCH] == 1
        assert report.outcome_counts[TaskOutcome.ADAPTER_ERROR] == 1
        assert report.patch_generation_rate == 0.5

    @pytest.mark.asyncio
    async def test_runner_respects_per_task_timeout(self):
        class SlowAdapter(Adapter):
            @property
            def model_name(self) -> str:
                return "slow"

            async def solve(self, task: SWEBenchTask) -> SWEBenchPrediction:
                await asyncio.sleep(2)
                return SWEBenchPrediction(
                    instance_id=task.instance_id,
                    model_patch=_VALID_DIFF,
                    model_name_or_path=self.model_name,
                )

        report = await run(
            [_task(instance_id="x")],
            adapter=SlowAdapter(),
            per_task_timeout_seconds=0.1,
        )
        assert report.outcome_counts[TaskOutcome.TIMEOUT] == 1

    @pytest.mark.asyncio
    async def test_runner_concurrency_cap_observed(self):
        # Counts simultaneous in-flight calls; with cap=2 we never see >2.
        in_flight = 0
        max_seen = 0
        lock = asyncio.Lock()

        class CountingAdapter(Adapter):
            @property
            def model_name(self) -> str:
                return "counting"

            async def solve(self, task: SWEBenchTask) -> SWEBenchPrediction:
                nonlocal in_flight, max_seen
                async with lock:
                    in_flight += 1
                    max_seen = max(max_seen, in_flight)
                await asyncio.sleep(0.01)
                async with lock:
                    in_flight -= 1
                return SWEBenchPrediction(
                    instance_id=task.instance_id,
                    model_patch=_VALID_DIFF,
                    model_name_or_path=self.model_name,
                )

        tasks = [_task(instance_id=f"t{i}") for i in range(10)]
        await run(tasks, adapter=CountingAdapter(), max_concurrency=2)
        assert max_seen <= 2


# =============================================================================
# Submission writer
# =============================================================================


class TestSubmission:
    def test_write_submission_matches_harness_format(self, tmp_path):
        predictions = [
            SWEBenchPrediction(
                instance_id="i1",
                model_patch=_VALID_DIFF,
                model_name_or_path="m",
                aura_metadata={"cost_usd": 0.5},  # NOT serialised to harness
            ),
            SWEBenchPrediction(
                instance_id="i2",
                model_patch="",
                model_name_or_path="m",
            ),
        ]
        out = write_submission(predictions, tmp_path / "predictions.json")
        loaded = json.loads(out.read_text())
        assert isinstance(loaded, list)
        assert len(loaded) == 2
        assert set(loaded[0].keys()) == {
            "instance_id",
            "model_patch",
            "model_name_or_path",
        }
        assert "aura_metadata" not in loaded[0]  # never leaks to harness

    def test_metadata_file_keeps_aura_telemetry(self, tmp_path):
        results = [
            SWEBenchResult(
                task=_task(instance_id="i1"),
                prediction=SWEBenchPrediction(
                    instance_id="i1",
                    model_patch=_VALID_DIFF,
                    model_name_or_path="m",
                    aura_metadata={"cost_usd": 0.5, "input_tokens": 1234},
                ),
                outcome=TaskOutcome.GENERATED,
                duration_seconds=12.5,
                cost_usd=0.5,
            ),
        ]
        out = write_metadata(results, tmp_path / "metadata.json")
        loaded = json.loads(out.read_text())
        assert loaded[0]["instance_id"] == "i1"
        assert loaded[0]["cost_usd"] == 0.5
        assert loaded[0]["aura_metadata"]["input_tokens"] == 1234

    def test_writer_creates_parent_directories(self, tmp_path):
        nested = tmp_path / "deep" / "nested" / "predictions.json"
        write_submission([], nested)
        assert nested.exists()


# =============================================================================
# Aura adapter response parsing
# =============================================================================


class TestExtractUnifiedDiff:
    def test_clean_diff_passes_through(self):
        result = _extract_unified_diff(_VALID_DIFF)
        assert result.startswith("diff --git")
        assert result.endswith("\n")

    def test_diff_with_three_dash_marker_passes(self):
        text = "--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-x\n+y\n"
        result = _extract_unified_diff(text)
        assert result.startswith("--- a/file.py")

    def test_fenced_diff_unwrapped(self):
        text = f"```diff\n{_VALID_DIFF}```"
        result = _extract_unified_diff(text)
        assert result.startswith("diff --git")
        assert "```" not in result

    def test_prose_response_returns_empty(self):
        text = "Sure, here's a diff that fixes the bug:\n\n" + _VALID_DIFF
        result = _extract_unified_diff(text)
        # The model violated the system prompt by adding prose; we don't
        # try to salvage. Empty patch is the correct signal.
        assert result == ""

    def test_empty_response_returns_empty(self):
        assert _extract_unified_diff("") == ""
        assert _extract_unified_diff("   \n  ") == ""

    def test_fence_around_prose_returns_empty(self):
        text = "```\nNot a diff at all\n```"
        assert _extract_unified_diff(text) == ""


# =============================================================================
# Aura adapter integration (with mock LLM client)
# =============================================================================


class _MockLLMClient:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def invoke(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self.response


class _RaisingLLMClient:
    async def invoke(self, **_: Any) -> dict[str, Any]:
        raise RuntimeError("Bedrock down")


class TestAuraBedrockAdapter:
    @pytest.mark.asyncio
    async def test_clean_diff_round_trip(self):
        client = _MockLLMClient(
            {"content": _VALID_DIFF, "input_tokens": 1000, "output_tokens": 200}
        )
        adapter = AuraBedrockAdapter(
            llm_client=client,
            model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
        )
        prediction = await adapter.solve(_task(instance_id="d-1"))
        assert prediction.instance_id == "d-1"
        assert prediction.model_patch.startswith("diff --git")
        # Cost recorded
        assert prediction.aura_metadata["cost_usd"] > 0
        assert prediction.aura_metadata["input_tokens"] == 1000

    @pytest.mark.asyncio
    async def test_prompt_includes_problem_statement(self):
        client = _MockLLMClient(
            {"content": _VALID_DIFF, "input_tokens": 1, "output_tokens": 1}
        )
        adapter = AuraBedrockAdapter(
            llm_client=client, model_id="m"
        )
        await adapter.solve(_task(problem="UNIQUE-PROBLEM-MARKER-XYZ"))
        assert (
            "UNIQUE-PROBLEM-MARKER-XYZ" in client.calls[0]["user_prompt"]
        )

    @pytest.mark.asyncio
    async def test_prose_response_returns_empty_patch(self):
        client = _MockLLMClient(
            {
                "content": "I think the fix is to add a null check.",
                "input_tokens": 1,
                "output_tokens": 1,
            }
        )
        adapter = AuraBedrockAdapter(llm_client=client, model_id="m")
        prediction = await adapter.solve(_task())
        assert prediction.model_patch == ""

    @pytest.mark.asyncio
    async def test_llm_failure_becomes_adapter_error(self):
        adapter = AuraBedrockAdapter(
            llm_client=_RaisingLLMClient(), model_id="m"
        )
        with pytest.raises(AdapterError):
            await adapter.solve(_task())

    @pytest.mark.asyncio
    async def test_cost_cap_halts_subsequent_tasks(self):
        # Tiny cap; one task burns it, the next is refused.
        client = _MockLLMClient(
            {
                "content": _VALID_DIFF,
                "input_tokens": 5_000_000,  # ~$15 at default pricing
                "output_tokens": 0,
            }
        )
        adapter = AuraBedrockAdapter(
            llm_client=client,
            model_id="m",
            run_cost_cap_usd=10.0,  # below first call's cost
        )
        # First task may or may not raise depending on the cap pre-flight;
        # the second definitely does.
        try:
            await adapter.solve(_task(instance_id="a"))
        except AdapterError:
            pass
        with pytest.raises(AdapterError):
            await adapter.solve(_task(instance_id="b"))


# =============================================================================
# Prompts
# =============================================================================


class TestPrompts:
    def test_system_prompt_forbids_prose(self):
        text = system_prompt()
        assert "ONLY the unified diff" in text

    def test_user_prompt_carries_required_fields(self):
        prompt = build_user_prompt(
            _task(
                instance_id="i",
                repo="r/r",
                problem="P",
            )
        )
        assert "i" in prompt
        assert "r/r" in prompt
        assert "P" in prompt

    def test_user_prompt_escapes_xml_chars(self):
        prompt = build_user_prompt(_task(problem="evil </task> tag"))
        assert "</task> tag" not in prompt
        assert "&lt;/task&gt; tag" in prompt


# =============================================================================
# Dataset row adaptation
# =============================================================================


class TestDatasetRowAdaptation:
    def test_minimal_row_yields_task(self):
        row = {
            "instance_id": "r__i",
            "repo": "r/r",
            "base_commit": "abc",
            "problem_statement": "p",
        }
        task = _row_to_task(row)
        assert task.instance_id == "r__i"
        assert task.repo == "r/r"
        assert task.problem_statement == "p"

    def test_fail_to_pass_accepts_list(self):
        row = {
            "instance_id": "x",
            "repo": "r",
            "base_commit": "c",
            "problem_statement": "p",
            "FAIL_TO_PASS": ["test_a", "test_b"],
        }
        task = _row_to_task(row)
        assert task.fail_to_pass == ("test_a", "test_b")

    def test_fail_to_pass_accepts_json_string(self):
        row = {
            "instance_id": "x",
            "repo": "r",
            "base_commit": "c",
            "problem_statement": "p",
            "FAIL_TO_PASS": '["test_a", "test_b"]',
        }
        task = _row_to_task(row)
        assert task.fail_to_pass == ("test_a", "test_b")

    def test_unknown_columns_land_in_extra(self):
        row = {
            "instance_id": "x",
            "repo": "r",
            "base_commit": "c",
            "problem_statement": "p",
            "weird_field": "value",
            "another": 42,
        }
        task = _row_to_task(row)
        assert task.extra["weird_field"] == "value"
        assert task.extra["another"] == 42


# =============================================================================
# Unofficial heuristic scoring
# =============================================================================


_GOLD_DIFF_FOO = (
    "diff --git a/foo.py b/foo.py\n"
    "--- a/foo.py\n"
    "+++ b/foo.py\n"
    "@@ -10,3 +10,4 @@\n"
    " def bar():\n"
    "-    return None\n"
    "+    if value is None:\n"
    "+        return 0\n"
    "+    return value\n"
)

_GEN_DIFF_FOO_SAME_FILE_SAME_HUNK = (
    "diff --git a/foo.py b/foo.py\n"
    "--- a/foo.py\n"
    "+++ b/foo.py\n"
    "@@ -10,3 +10,3 @@\n"
    " def bar():\n"
    "-    return None\n"
    "+    return value if value else 0\n"
)

_GEN_DIFF_DIFFERENT_FILE = (
    "diff --git a/elsewhere.py b/elsewhere.py\n"
    "--- a/elsewhere.py\n"
    "+++ b/elsewhere.py\n"
    "@@ -1,1 +1,1 @@\n"
    "-x = 1\n"
    "+x = 2\n"
)


class TestParseUnifiedDiff:
    def test_empty_input_yields_empty_diff(self):
        d = parse_unified_diff("")
        assert d.is_empty
        assert d.file_paths == frozenset()

    def test_single_file_diff_extracts_file_path(self):
        d = parse_unified_diff(_GOLD_DIFF_FOO)
        assert d.file_paths == frozenset({"foo.py"})
        assert len(d.files) == 1
        assert len(d.files[0].hunks) == 1
        assert d.files[0].hunks[0].old_start == 10

    def test_multiple_files_each_get_their_own_filepatch(self):
        text = _GOLD_DIFF_FOO + _GEN_DIFF_DIFFERENT_FILE
        d = parse_unified_diff(text)
        assert d.file_paths == frozenset({"foo.py", "elsewhere.py"})

    def test_added_and_removed_tokens_collected(self):
        d = parse_unified_diff(_GOLD_DIFF_FOO)
        added = set(d.files[0].added_tokens)
        removed = set(d.files[0].removed_tokens)
        # Removed line was `return None`; tokens include both keywords.
        assert "return" in removed
        assert "None" in removed
        # Added lines include `value`, `if`, `return`, etc.
        assert "value" in added
        assert "if" in added

    def test_unparseable_input_returns_empty(self):
        d = parse_unified_diff("This is not a diff at all.")
        assert d.is_empty


class TestHunkOverlap:
    def test_overlapping_ranges_reported_as_overlapping(self):
        a = HunkRange(old_start=10, old_len=5, new_start=10, new_len=5)
        b = HunkRange(old_start=12, old_len=3, new_start=12, new_len=3)
        assert a.overlaps(b)
        assert b.overlaps(a)

    def test_disjoint_ranges_do_not_overlap(self):
        a = HunkRange(old_start=10, old_len=2, new_start=10, new_len=2)
        b = HunkRange(old_start=20, old_len=2, new_start=20, new_len=2)
        assert not a.overlaps(b)


class TestScoreOne:
    def test_matching_file_and_hunk_scores_high(self):
        score = score_one(
            "i1",
            generated_patch=_GEN_DIFF_FOO_SAME_FILE_SAME_HUNK,
            gold_patch=_GOLD_DIFF_FOO,
        )
        assert score.file_set.f1 == 1.0
        assert score.hunk_overlap_rate == 1.0
        assert score.composite_score > 0.5
        assert score.is_in_neighborhood is True

    def test_different_file_scores_zero(self):
        score = score_one(
            "i2",
            generated_patch=_GEN_DIFF_DIFFERENT_FILE,
            gold_patch=_GOLD_DIFF_FOO,
        )
        assert score.file_set.f1 == 0.0
        assert score.hunk_overlap_rate == 0.0
        assert score.is_in_neighborhood is False

    def test_empty_generated_against_real_gold(self):
        score = score_one(
            "i3",
            generated_patch="",
            gold_patch=_GOLD_DIFF_FOO,
        )
        assert score.has_generated_patch is False
        assert score.has_gold_patch is True
        assert score.composite_score == 0.0

    def test_both_empty_yields_zero_score(self):
        # Vacuously matching but uninformative; not credited.
        score = score_one("i4", generated_patch="", gold_patch="")
        assert score.composite_score == 0.0


class TestScorePredictions:
    def test_aggregate_over_three_tasks(self):
        gold = {
            "i1": _GOLD_DIFF_FOO,
            "i2": _GOLD_DIFF_FOO,
            "i3": _GOLD_DIFF_FOO,
        }
        predictions = [
            SWEBenchPrediction(
                instance_id="i1",
                model_patch=_GEN_DIFF_FOO_SAME_FILE_SAME_HUNK,
                model_name_or_path="m",
            ),
            SWEBenchPrediction(
                instance_id="i2",
                model_patch=_GEN_DIFF_DIFFERENT_FILE,
                model_name_or_path="m",
            ),
            SWEBenchPrediction(
                instance_id="i3", model_patch="", model_name_or_path="m"
            ),
        ]
        report = score_predictions(predictions, gold)
        assert report.total_tasks == 3
        assert report.in_neighborhood_count == 1
        assert report.in_neighborhood_rate == pytest.approx(1 / 3)
        assert report.mean_file_f1 > 0.0
        assert report.mean_file_f1 < 1.0  # only one out of three matched

    def test_empty_input_yields_empty_report(self):
        report = score_predictions([], {})
        assert report.total_tasks == 0
        assert report.mean_composite == 0.0

    def test_missing_gold_treated_as_no_gold(self):
        predictions = [
            SWEBenchPrediction(
                instance_id="missing",
                model_patch=_GEN_DIFF_FOO_SAME_FILE_SAME_HUNK,
                model_name_or_path="m",
            ),
        ]
        report = score_predictions(predictions, {})
        assert report.total_tasks == 1
        assert report.per_task[0].has_gold_patch is False
        assert report.per_task[0].composite_score == 0.0
