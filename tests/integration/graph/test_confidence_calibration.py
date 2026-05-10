"""ADR-090 Tier 3 LLM resolver confidence calibration test (issue #118).

The Phase 4c.1/4c.2 LLM resolver emits a discrete ``verification_status``
(``verified`` / ``plausible`` / ``unverified``) replacing the rejected
confidence float. Tests today exercise the verification logic on
hand-crafted fixtures, but nothing asserts that **on real ambiguous
inputs the verifier marks resolutions less confidently than on real
unambiguous inputs**. Without this signal, a prompt change that makes
the model say "verified" to everything looks fine in unit tests but is
an integrity regression.

This test runs the resolver across 40 fixtures (20 unambiguous + 20
ambiguous) using recorded Bedrock responses (no live LLM in CI) and
asserts:

- The status distribution differs by category (Mann-Whitney U
  p-value < 0.01).
- Median score separation > 0.3 on the (verified=2, plausible=1,
  unverified=0) numeric scale.

When the prompt is intentionally changed or a new model snapshot is
rolled out, recordings must be regenerated. See
``tests/fixtures/bedrock_recordings/calibration/REGENERATING.md``.
"""

from __future__ import annotations

import asyncio
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from src.agents.ast_parser_agent import CodeEntity, CodeRelationship
from src.services.graph.edge_labels import EdgeLabel
from src.services.graph.symbol_resolver_tier3 import (
    PLAUSIBLE,
    UNVERIFIED,
    VERIFIED,
    Tier3LLMResolver,
)

_RECORDINGS_PATH = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "bedrock_recordings"
    / "calibration"
    / "recordings.json"
)

# Numeric mapping per #118: verified=2 / plausible=1 / unverified=0.
_STATUS_SCORE: dict[str, int] = {
    VERIFIED: 2,
    PLAUSIBLE: 1,
    UNVERIFIED: 0,
}


@dataclass
class CalibrationFixture:
    """One call-site scenario plus the entity index needed to surface
    the candidate set the resolver inspects."""

    fixture_id: str
    category: str
    entities: list[CodeEntity]
    relationship: CodeRelationship


def _build_unambiguous_fixtures() -> list[CalibrationFixture]:
    """20 fixtures where the call site has exactly one structurally
    matching candidate. Realistic LLM behavior on these is high
    confidence: pick the only available index.
    """
    fixtures: list[CalibrationFixture] = []
    for i in range(20):
        target_name = f"helper_{i}"
        caller_name = f"caller_{i}"
        file_path = f"src/svc_{i}.py"
        entities = [
            CodeEntity(
                name=target_name,
                entity_type="method",
                file_path=file_path,
                line_number=5,
                parent_chain=("Service",),
            ),
            CodeEntity(
                name=caller_name,
                entity_type="method",
                file_path=file_path,
                line_number=10,
                parent_chain=("Service",),
            ),
        ]
        rel = CodeRelationship(
            source_name=caller_name,
            source_parent_chain=("Service",),
            target_name=target_name,
            relationship=EdgeLabel.CALLS.value,
            properties={"call_site_line": 11},
            file_path=file_path,
        )
        fixtures.append(
            CalibrationFixture(
                fixture_id=f"unambiguous_{i:03d}",
                category="unambiguous",
                entities=entities,
                relationship=rel,
            )
        )
    return fixtures


def _build_ambiguous_fixtures() -> list[CalibrationFixture]:
    """20 fixtures where the call site has multiple structurally
    matching candidates (overload-style: same leaf name across
    different classes). Realistic LLM behavior on these is uncertain:
    null is the safe answer when context is insufficient.
    """
    fixtures: list[CalibrationFixture] = []
    for i in range(20):
        target_name = f"verify_{i}"
        caller_name = f"caller_{i}"
        entities = [
            CodeEntity(
                name=target_name,
                entity_type="method",
                file_path=f"src/auth_{i}_a.py",
                line_number=5,
                parent_chain=("AuthA",),
            ),
            CodeEntity(
                name=target_name,
                entity_type="method",
                file_path=f"src/auth_{i}_b.py",
                line_number=10,
                parent_chain=("AuthB",),
            ),
            CodeEntity(
                name=target_name,
                entity_type="method",
                file_path=f"src/auth_{i}_c.py",
                line_number=15,
                parent_chain=("AuthC",),
            ),
            CodeEntity(
                name=caller_name,
                entity_type="method",
                file_path=f"src/caller_{i}.py",
                line_number=20,
                parent_chain=(),
            ),
        ]
        rel = CodeRelationship(
            source_name=caller_name,
            source_parent_chain=(),
            target_name=target_name,
            relationship=EdgeLabel.CALLS.value,
            properties={"call_site_line": 21},
            file_path=f"src/caller_{i}.py",
        )
        fixtures.append(
            CalibrationFixture(
                fixture_id=f"ambiguous_{i:03d}",
                category="ambiguous",
                entities=entities,
                relationship=rel,
            )
        )
    return fixtures


def _load_recordings() -> dict[str, str]:
    payload: dict[str, Any] = json.loads(_RECORDINGS_PATH.read_text())
    return {entry["fixture_id"]: entry["response"] for entry in payload["fixtures"]}


@pytest.fixture(scope="module")
def all_fixtures() -> list[CalibrationFixture]:
    return _ALL_FIXTURES


@pytest.fixture(scope="module")
def recordings() -> dict[str, str]:
    return _RECORDINGS


def test_recordings_cover_every_fixture(
    all_fixtures: list[CalibrationFixture],
    recordings: dict[str, str],
) -> None:
    """Sanity check: every fixture has a recording and there are no
    stale recordings. Catches silent fixture / recording drift."""
    fixture_ids = {f.fixture_id for f in all_fixtures}
    recorded_ids = set(recordings.keys())

    missing = fixture_ids - recorded_ids
    extra = recorded_ids - fixture_ids
    assert not missing, (
        f"Missing recordings for fixtures: {sorted(missing)}. " f"See REGENERATING.md."
    )
    assert not extra, (
        f"Stale recordings without fixtures: {sorted(extra)}. " f"See REGENERATING.md."
    )


async def _resolve_fixture(
    fixture: CalibrationFixture,
    recorded_response: str,
) -> str:
    """Invoke the Tier 3 resolver on a single fixture using the
    recorded Bedrock response. Returns the verification_status of the
    emitted relationship.

    Bound the recorded response via a default argument so the closure
    captures the value, not the loop variable.
    """

    async def _stub_bedrock(*, _bound: str = recorded_response, **_kw: Any) -> str:
        return _bound

    resolver = Tier3LLMResolver(bedrock_generate=_stub_bedrock)
    out, _stats = await resolver.resolve(
        entities=fixture.entities,
        relationships=[fixture.relationship],
        repo_id="test/repo",
    )
    assert len(out) == 1, "Resolver should return exactly one relationship"
    return out[0].properties.get("verification_status", UNVERIFIED)


async def _collect_all_statuses(
    all_fixtures: list[CalibrationFixture],
    recordings: dict[str, str],
) -> dict[str, list[str]]:
    """Resolve every fixture in a single async pass so the test
    function itself can be sync. Mixing async tests with scipy's lazy
    numpy imports under pytest-asyncio's auto mode triggers a numpy
    'cannot load module more than once per process' error in the
    environment; staying sync at the test boundary side-steps it.
    """
    by_category: dict[str, list[str]] = {"unambiguous": [], "ambiguous": []}
    for fixture in all_fixtures:
        recorded = recordings[fixture.fixture_id]
        status = await _resolve_fixture(fixture, recorded)
        by_category[fixture.category].append(status)
    return by_category


def _mannwhitney_u_two_sided(
    group_a: list[float],
    group_b: list[float],
) -> tuple[float, float]:
    """Mann-Whitney U test, two-sided, with tie correction and a
    normal approximation for the p-value.

    Reimplemented in pure Python so the test does not depend on
    scipy.stats.mannwhitneyu. scipy's implementation triggers a
    cyclic import inside its array_api_extra layer when the rank
    distribution contains ties; that cyclic import collides with
    numpy's load state under the pytest+asyncio session in this
    project's environment ("cannot load module more than once per
    process"). At n>=10 per group with many ties, the normal
    approximation is the textbook approach anyway.

    Returns:
        (U, p) where U is min(U_a, U_b) and p is the two-sided
        approximate p-value from the standard normal.
    """
    n1 = len(group_a)
    n2 = len(group_b)
    if n1 == 0 or n2 == 0:
        return 0.0, 1.0

    combined: list[tuple[float, str]] = [(v, "a") for v in group_a] + [
        (v, "b") for v in group_b
    ]
    combined.sort(key=lambda x: x[0])
    n_total = n1 + n2

    ranks: list[float] = [0.0] * n_total
    tie_group_sizes: list[int] = []
    i = 0
    while i < n_total:
        j = i
        while j < n_total and combined[j][0] == combined[i][0]:
            j += 1
        # Average rank for positions i..j-1 (1-indexed).
        avg_rank = (i + j + 1) / 2.0
        for k in range(i, j):
            ranks[k] = avg_rank
        if j - i > 1:
            tie_group_sizes.append(j - i)
        i = j

    rank_sum_a = sum(ranks[k] for k in range(n_total) if combined[k][1] == "a")
    u_a = rank_sum_a - n1 * (n1 + 1) / 2.0
    u_b = n1 * n2 - u_a
    u_min = min(u_a, u_b)

    mean_u = n1 * n2 / 2.0
    tie_correction = sum(t**3 - t for t in tie_group_sizes)
    if n_total > 1:
        var_u = (n1 * n2 / 12.0) * (
            n_total + 1 - tie_correction / (n_total * (n_total - 1))
        )
    else:
        var_u = 0.0

    if var_u <= 0:
        return u_min, 1.0

    # Continuity-corrected z-score, two-sided p via standard normal.
    z = (abs(u_a - mean_u) - 0.5) / math.sqrt(var_u)
    p_two_sided = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(z / math.sqrt(2.0))))
    return u_min, p_two_sided


# Resolve every fixture eagerly at module-import time so asyncio.run
# completes before any test starts.
_ALL_FIXTURES: list[CalibrationFixture] = (
    _build_unambiguous_fixtures() + _build_ambiguous_fixtures()
)
_RECORDINGS: dict[str, str] = _load_recordings()
_STATUS_DISTRIBUTIONS: dict[str, list[str]] = asyncio.run(
    _collect_all_statuses(_ALL_FIXTURES, _RECORDINGS)
)


def test_calibration_separates_ambiguous_from_unambiguous() -> None:
    """Assert the verification_status distributions are statistically
    separable per the calibration thresholds."""
    statuses_unambig = _STATUS_DISTRIBUTIONS["unambiguous"]
    statuses_ambig = _STATUS_DISTRIBUTIONS["ambiguous"]

    assert len(statuses_unambig) == 20
    assert len(statuses_ambig) == 20

    scores_unambig = [_STATUS_SCORE[s] for s in statuses_unambig]
    scores_ambig = [_STATUS_SCORE[s] for s in statuses_ambig]

    # Mann-Whitney U on the rank distributions, two-sided. We want
    # *separation*, not direction. See _mannwhitney_u_two_sided
    # docstring for why this is hand-rolled rather than scipy.
    _u_stat, p_value = _mannwhitney_u_two_sided(scores_unambig, scores_ambig)
    assert p_value < 0.01, (
        f"MWU p-value {p_value:.6f} >= 0.01. "
        f"Distributions collapsed; either prompt drift or fixture "
        f"rot. unambig={scores_unambig} ambig={scores_ambig}"
    )

    median_unambig = sorted(scores_unambig)[len(scores_unambig) // 2]
    median_ambig = sorted(scores_ambig)[len(scores_ambig) // 2]
    separation = median_unambig - median_ambig
    assert separation > 0.3, (
        f"Median separation {separation} <= 0.3. "
        f"unambig median={median_unambig} ambig median={median_ambig}. "
        f"See REGENERATING.md if this is an intentional prompt change."
    )


def test_status_score_mapping_is_complete() -> None:
    """If the resolver ever introduces a new verification_status
    enum value, the calibration test must be updated to map it. Catch
    that drift early.
    """
    expected_statuses = {VERIFIED, PLAUSIBLE, UNVERIFIED}
    mapped_statuses = set(_STATUS_SCORE.keys())
    assert mapped_statuses == expected_statuses, (
        "Calibration scoring map drifted from the resolver's status "
        "enum. Update _STATUS_SCORE in this test file."
    )


def test_mannwhitney_u_helper_matches_textbook_example() -> None:
    """Sanity check on the hand-rolled MWU implementation against a
    known result. Group A clearly dominates Group B; expect a small
    p-value and U_min == 0 (no overlap).
    """
    group_a = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]
    group_b = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    u, p = _mannwhitney_u_two_sided(group_a, group_b)
    assert u == 0.0
    assert p < 0.001


def test_mannwhitney_u_helper_handles_identical_distributions() -> None:
    """When both groups have the same distribution, p should be near
    1.0 -- no separation."""
    group_a = [0, 1, 2, 0, 1, 2, 0, 1, 2, 0]
    group_b = [0, 1, 2, 0, 1, 2, 0, 1, 2, 0]
    _u, p = _mannwhitney_u_two_sided(group_a, group_b)
    assert p > 0.9
