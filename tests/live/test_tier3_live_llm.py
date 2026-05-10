"""ADR-090 Tier 3 LLM resolver live-Bedrock smoke (issue #120, P2).

Opt-in nightly suite that exercises the Tier 3 resolver against real
Bedrock. The mocked Tier 3 tests prove resolver code is correct given
a known-shaped LLM response; this test catches the failure modes
mocks cannot:

- Model snapshot rolls forward, response shape changes silently.
- Bedrock returns a refusal (prompt-injection defense kicks in).
- Throttling story shifts; resolver no longer handles it gracefully.

Per #120 this is **deferrable / P2**: it costs real money per run
and adds little signal beyond what the mocked tests already prove.
The cost ceiling enforced below makes the blast radius bounded.

Skip semantics:

- Module-level skip when ``AWS_BEDROCK_AVAILABLE`` is unset (no
  false negatives in stripped CI images that lack credentials).
- ``live_llm`` marker required so default ``pytest`` collection
  also skips this; the nightly workflow runs with ``-m live_llm``.

Failure interpretation: see ``docs/runbooks/ADR090_LIVE_LLM_SMOKE_RUNBOOK.md``.
"""

from __future__ import annotations

import os

import pytest

from src.agents.ast_parser_agent import CodeEntity, CodeRelationship
from src.services.graph.edge_labels import EdgeLabel
from src.services.graph.symbol_resolver_tier3 import UNVERIFIED, Tier3LLMResolver

# Module-level skip: nothing in this module runs unless real Bedrock
# is available in the runner environment. Equivalent to a pytest.skip
# at collect time.
pytestmark = [
    pytest.mark.live_llm,
    pytest.mark.skipif(
        os.environ.get("AWS_BEDROCK_AVAILABLE") != "1",
        reason=(
            "Live-LLM tests require AWS_BEDROCK_AVAILABLE=1 and valid "
            "AWS credentials with Bedrock model access. "
            "See docs/runbooks/ADR090_LIVE_LLM_SMOKE_RUNBOOK.md."
        ),
    ),
]

# Per #120: cost cap of USD 0.50 per run. The resolver invokes Bedrock
# at most once per fixture; with max_tokens=256 output and ~1-2K input
# tokens per fixture, 5 fixtures cost well under USD 0.10 at Claude
# Sonnet 4.6 rates. The cap exists as a hard guardrail in case the
# fixture set grows or output budgets are raised without re-reviewing
# this test.
_PER_RUN_COST_CAP_USD = 0.50
_PER_FIXTURE_MAX_TOKENS = 256
# Cost coefficients per million tokens at Claude Sonnet 4.6 list
# pricing (approximate; review when pricing changes).
_INPUT_COST_PER_MTOK = 3.00
_OUTPUT_COST_PER_MTOK = 15.00


def _representative_fixtures() -> list[tuple[str, list[CodeEntity], CodeRelationship]]:
    """Five representative call-site scenarios per #120.

    Returns a list of ``(label, entities, relationship)`` tuples.
    """
    fixtures: list[tuple[str, list[CodeEntity], CodeRelationship]] = []

    # 1. Single direct-import: clear winner, expect verified.
    fixtures.append(
        (
            "single_direct_import",
            [
                CodeEntity(
                    name="helper",
                    entity_type="function",
                    file_path="src/utils.py",
                    line_number=5,
                    parent_chain=(),
                ),
            ],
            CodeRelationship(
                source_name="run",
                source_parent_chain=(),
                target_name="helper",
                relationship=EdgeLabel.CALLS.value,
                properties={"call_site_line": 12},
                file_path="src/main.py",
            ),
        )
    )

    # 2. Dynamic dispatch: single candidate, model should still pick it.
    fixtures.append(
        (
            "dynamic_dispatch",
            [
                CodeEntity(
                    name="handle",
                    entity_type="method",
                    file_path="src/dispatcher.py",
                    line_number=20,
                    parent_chain=("Dispatcher",),
                ),
            ],
            CodeRelationship(
                source_name="dispatch",
                source_parent_chain=("Dispatcher",),
                target_name="handle",
                relationship=EdgeLabel.CALLS.value,
                properties={"call_site_line": 35},
                file_path="src/dispatcher.py",
            ),
        )
    )

    # 3. Ambiguous overload: 3 candidates with same leaf name.
    fixtures.append(
        (
            "ambiguous_overload",
            [
                CodeEntity(
                    name="verify",
                    entity_type="method",
                    file_path="src/auth_a.py",
                    line_number=5,
                    parent_chain=("AuthA",),
                ),
                CodeEntity(
                    name="verify",
                    entity_type="method",
                    file_path="src/auth_b.py",
                    line_number=5,
                    parent_chain=("AuthB",),
                ),
                CodeEntity(
                    name="verify",
                    entity_type="method",
                    file_path="src/auth_c.py",
                    line_number=5,
                    parent_chain=("AuthC",),
                ),
            ],
            CodeRelationship(
                source_name="login",
                source_parent_chain=(),
                target_name="verify",
                relationship=EdgeLabel.CALLS.value,
                properties={"call_site_line": 12},
                file_path="src/login.py",
            ),
        )
    )

    # 4. Cross-package: candidate in a different module path.
    fixtures.append(
        (
            "cross_package",
            [
                CodeEntity(
                    name="serialize",
                    entity_type="function",
                    file_path="vendor/json_lib/codec.py",
                    line_number=42,
                    parent_chain=(),
                ),
            ],
            CodeRelationship(
                source_name="encode",
                source_parent_chain=("Codec",),
                target_name="serialize",
                relationship=EdgeLabel.CALLS.value,
                properties={"call_site_line": 18},
                file_path="src/serializer.py",
            ),
        )
    )

    # 5. Deeply-nested method: candidate has long parent chain.
    fixtures.append(
        (
            "deeply_nested_method",
            [
                CodeEntity(
                    name="commit",
                    entity_type="method",
                    file_path="src/db/transaction.py",
                    line_number=88,
                    parent_chain=("Database", "Connection", "Transaction"),
                ),
            ],
            CodeRelationship(
                source_name="finalize",
                source_parent_chain=("Database", "Connection"),
                target_name="commit",
                relationship=EdgeLabel.CALLS.value,
                properties={"call_site_line": 102},
                file_path="src/db/transaction.py",
            ),
        )
    )

    return fixtures


def _estimate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    """Approximate dollar cost from token counts."""
    return (
        input_tokens * _INPUT_COST_PER_MTOK / 1_000_000
        + output_tokens * _OUTPUT_COST_PER_MTOK / 1_000_000
    )


@pytest.mark.asyncio
async def test_tier3_resolution_rate_above_threshold() -> None:
    """Run the resolver against real Bedrock on five representative
    fixtures. Assert resolution rate > 60% and cost < USD 0.50.

    The resolution rate is the fraction of fixtures that produced a
    non-UNVERIFIED status. We do not assert on the *correctness* of
    the chosen index because correctness depends on prompt-engineering
    choices that this test should reflect, not gate. The integrity
    signal is "the model picked something with verifiable structure
    on most inputs".
    """
    # Lazy import: BedrockLLMService loads heavy AWS SDK modules and
    # we want the module-level skip to short-circuit before that.
    from src.services.bedrock_llm_service import BedrockLLMService

    bedrock = BedrockLLMService()
    resolver = Tier3LLMResolver(
        bedrock_generate=bedrock.generate,
        max_tokens=_PER_FIXTURE_MAX_TOKENS,
    )

    fixtures = _representative_fixtures()
    statuses: list[str] = []
    estimated_input_tokens = 0
    estimated_output_tokens = 0

    for label, entities, relationship in fixtures:
        out, _stats = await resolver.resolve(
            entities=entities,
            relationships=[relationship],
            repo_id="test/live-tier3",
        )
        assert len(out) == 1
        status = out[0].properties.get("verification_status", UNVERIFIED)
        statuses.append(status)
        # Crude per-fixture estimate: prompt is short, output is
        # capped at _PER_FIXTURE_MAX_TOKENS. Real usage would be
        # tracked via the cost ceiling, but the live-test budget
        # bound here is intentionally loose.
        estimated_input_tokens += 1500  # generous per-prompt estimate
        estimated_output_tokens += _PER_FIXTURE_MAX_TOKENS

    resolution_rate = sum(
        1 for s in statuses if s != UNVERIFIED
    ) / len(statuses)
    cost_usd = _estimate_cost_usd(estimated_input_tokens, estimated_output_tokens)

    # Surface the metrics into the workflow summary so the nightly
    # job can pull them out and post to the tracking issue.
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    summary_lines = [
        "## ADR-090 Live-LLM Smoke Result",
        "",
        f"- Resolution rate: {resolution_rate:.0%} ({sum(1 for s in statuses if s != UNVERIFIED)}/{len(statuses)})",
        f"- Estimated cost: ${cost_usd:.4f} (cap ${_PER_RUN_COST_CAP_USD:.2f})",
        f"- Per-fixture statuses: {dict(zip([f[0] for f in fixtures], statuses))}",
    ]
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(summary_lines) + "\n")
    print("\n".join(summary_lines))

    # Hard cost guardrail.
    assert cost_usd < _PER_RUN_COST_CAP_USD, (
        f"Estimated run cost ${cost_usd:.4f} exceeded cap "
        f"${_PER_RUN_COST_CAP_USD:.2f}. Tighten max_tokens or shrink "
        f"the fixture set."
    )

    # Resolution rate threshold per #120.
    assert resolution_rate > 0.60, (
        f"Resolution rate {resolution_rate:.0%} is below 60% threshold. "
        f"Per-fixture statuses: "
        f"{dict(zip([f[0] for f in fixtures], statuses))}. "
        f"See docs/runbooks/ADR090_LIVE_LLM_SMOKE_RUNBOOK.md for "
        f"failure-mode interpretation (model drift vs fixture rot vs "
        f"Bedrock outage)."
    )
