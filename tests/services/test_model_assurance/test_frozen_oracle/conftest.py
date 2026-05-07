"""Test conftest for the Frozen Reference Oracle.

Per ADR-088 Phase 2 issue #111 acceptance criteria:

    "conftest.py validator: candidate_model_id != judge_model_id"

This validator runs against every fixture that wires both a
candidate and a judge model id; it prevents tests from accidentally
configuring a self-grading scenario, which would silently bypass
the recursive-degradation guard the LLM judge enforces at runtime.
"""

from __future__ import annotations

import pytest

from src.services.model_assurance.frozen_oracle import assert_no_self_grading


@pytest.fixture(scope="session")
def assert_no_self_grading_validator():
    """Expose the guard so any fixture can call it explicitly."""
    return assert_no_self_grading


@pytest.fixture
def candidate_model_id() -> str:
    return "anthropic.claude-3-5-sonnet-20240620-v1:0"


@pytest.fixture
def judge_model_id() -> str:
    return "anthropic.claude-3-haiku-20240307-v1:0"


@pytest.fixture(autouse=True)
def assert_test_fixtures_use_distinct_models(request):
    """Run the recursive-degradation guard on any test that wires both
    ``candidate_model_id`` and ``judge_model_id`` fixtures.

    Tests that don't use these fixtures are unaffected. Tests that do
    will fail loudly at setup if they ever resolve to the same value.
    """
    fixturenames = getattr(request, "fixturenames", ())
    if "candidate_model_id" in fixturenames and "judge_model_id" in fixturenames:
        candidate = request.getfixturevalue("candidate_model_id")
        judge = request.getfixturevalue("judge_model_id")
        assert_no_self_grading(
            candidate_model_id=candidate, judge_model_id=judge,
        )
    yield
