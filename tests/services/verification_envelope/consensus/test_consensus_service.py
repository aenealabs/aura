"""End-to-end tests for the consensus service."""

from __future__ import annotations

import asyncio
from typing import Sequence

import pytest

from src.services.verification_envelope.config import DVEConfig
from src.services.verification_envelope.consensus.consensus_service import (
    ConsensusService,
)
from src.services.verification_envelope.contracts import ConsensusOutcome


class _ScriptedGenerator:
    """Cycles through a fixed list of outputs across invocations."""

    def __init__(self, outputs: list[str]) -> None:
        self._outputs = list(outputs)
        self._idx = 0

    async def __call__(self, prompt: str) -> str:
        out = self._outputs[self._idx % len(self._outputs)]
        self._idx += 1
        return out


@pytest.mark.asyncio
async def test_three_identical_outputs_converge() -> None:
    outputs = ["def f(): return 1\n"] * 3
    cfg = DVEConfig.for_testing()
    svc = ConsensusService(config=cfg, generator=_ScriptedGenerator(outputs))
    result = await svc.generate_and_check("write f")
    assert result.outcome == ConsensusOutcome.CONVERGED
    assert result.m_converged == 3
    assert result.selected_output == outputs[0]
    assert result.selection_method == "ast_centroid"
    assert result.convergence_rate == 1.0
    assert result.audit_record_id


@pytest.mark.asyncio
async def test_two_of_three_converge_passes_threshold() -> None:
    outputs = [
        "def f(): return 1\n",
        "def f(): return 1\n",  # equivalent to first
        "def g(): return 99\n",  # different function name, different ast
    ]
    cfg = DVEConfig.for_testing()
    svc = ConsensusService(config=cfg, generator=_ScriptedGenerator(outputs))
    result = await svc.generate_and_check("two of three")
    assert result.outcome == ConsensusOutcome.CONVERGED
    assert result.m_converged == 2
    assert result.selected_output == "def f(): return 1\n"


@pytest.mark.asyncio
async def test_all_different_outputs_diverge() -> None:
    outputs = [
        "def f(): return 1\n",
        "def f(): return 2\n",
        "def f(): return 3\n",
    ]
    cfg = DVEConfig.for_testing()
    svc = ConsensusService(config=cfg, generator=_ScriptedGenerator(outputs))
    result = await svc.generate_and_check("all different")
    assert result.outcome == ConsensusOutcome.DIVERGED
    assert result.selected_output is None
    assert result.needs_hitl is True


@pytest.mark.asyncio
async def test_renamed_args_recognized_as_equivalent() -> None:
    outputs = [
        "def f(x): return x + 1\n",
        "def f(y): return y + 1\n",
        "def f(z): return z + 1\n",
    ]
    cfg = DVEConfig.for_testing()
    svc = ConsensusService(config=cfg, generator=_ScriptedGenerator(outputs))
    result = await svc.generate_and_check("rename equivalence")
    assert result.outcome == ConsensusOutcome.CONVERGED
    assert result.m_converged == 3


@pytest.mark.asyncio
async def test_audit_dict_round_trip() -> None:
    outputs = ["def f(): return 1\n"] * 3
    cfg = DVEConfig.for_testing()
    svc = ConsensusService(config=cfg, generator=_ScriptedGenerator(outputs))
    result = await svc.generate_and_check("audit shape")
    audit = result.to_audit_dict()
    assert audit["outcome"] == "converged"
    assert audit["n_generated"] == 3
    assert audit["m_required"] == 2
    assert audit["m_converged"] == 3
    assert "canonical_hashes" in audit
    assert len(audit["canonical_hashes"]) == 3


@pytest.mark.asyncio
async def test_generation_timeout_propagates() -> None:
    async def slow_gen(_: str) -> str:
        await asyncio.sleep(5)
        return "def f(): return 1\n"

    cfg = DVEConfig(
        consensus_n=2,
        consensus_m=2,
        consensus_timeout_seconds=0.05,
        consensus_temperature=0.0,
    )
    svc = ConsensusService(config=cfg, generator=slow_gen)
    with pytest.raises(asyncio.TimeoutError):
        await svc.generate_and_check("timeout")


@pytest.mark.asyncio
async def test_pairwise_matrix_is_symmetric() -> None:
    outputs = [
        "def f(): return 1\n",
        "def f(): return 2\n",
        "def f(): return 1\n",
    ]
    cfg = DVEConfig.for_testing()
    svc = ConsensusService(config=cfg, generator=_ScriptedGenerator(outputs))
    result = await svc.generate_and_check("symmetry")
    n = result.n_generated
    for i in range(n):
        for j in range(n):
            assert (
                result.pairwise_similarities[i][j] == result.pairwise_similarities[j][i]
            )


@pytest.mark.asyncio
async def test_concurrent_invocations_produce_distinct_audit_ids() -> None:
    outputs = ["def f(): return 1\n"] * 3
    cfg = DVEConfig.for_testing()
    svc1 = ConsensusService(config=cfg, generator=_ScriptedGenerator(outputs))
    svc2 = ConsensusService(config=cfg, generator=_ScriptedGenerator(outputs))
    a, b = await asyncio.gather(
        svc1.generate_and_check("p"), svc2.generate_and_check("p")
    )
    assert a.audit_record_id != b.audit_record_id
