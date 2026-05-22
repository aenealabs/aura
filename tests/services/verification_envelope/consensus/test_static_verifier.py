"""Tests for the non-LLM static verifier track (issue #209)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.services.verification_envelope.config import DVEConfig
from src.services.verification_envelope.consensus.consensus_service import (
    ConsensusService,
)
from src.services.verification_envelope.consensus.static_verifier import (
    ASTRuleVerifier,
    StaticVerificationFinding,
    StaticVerificationVerdict,
    StaticVerifierDispatcher,
)
from src.services.verification_envelope.contracts import ConsensusOutcome

# =============================================================================
# ASTRuleVerifier -- rule pack
# =============================================================================


class TestASTRuleVerifier:
    def test_clean_code_passes(self):
        verifier = ASTRuleVerifier()
        verdict = verifier.verify("def add(a: int, b: int) -> int:\n    return a + b\n")
        assert verdict.passed is True
        assert verdict.findings == ()

    def test_eval_call_flagged_as_high(self):
        verifier = ASTRuleVerifier()
        verdict = verifier.verify("def run(s: str):\n    return eval(s)\n")
        assert verdict.passed is False
        ids = [f.rule_id for f in verdict.findings]
        assert "AURA-SV-001" in ids
        assert any(f.cwe_id == "CWE-94" for f in verdict.findings)

    def test_os_system_flagged(self):
        verifier = ASTRuleVerifier()
        verdict = verifier.verify("import os\n\ndef run(s: str):\n    os.system(s)\n")
        assert verdict.passed is False
        assert any(f.rule_id == "AURA-SV-002" for f in verdict.findings)
        assert any(f.cwe_id == "CWE-78" for f in verdict.findings)

    def test_pickle_loads_flagged(self):
        verifier = ASTRuleVerifier()
        verdict = verifier.verify(
            "import pickle\n\ndef d(b: bytes):\n    return pickle.loads(b)\n"
        )
        assert verdict.passed is False
        assert any(f.rule_id == "AURA-SV-003" for f in verdict.findings)
        assert any(f.cwe_id == "CWE-502" for f in verdict.findings)

    def test_shell_true_flagged(self):
        verifier = ASTRuleVerifier()
        verdict = verifier.verify(
            "import subprocess\n"
            "def r(cmd: str):\n"
            "    subprocess.run(cmd, shell=True)\n"
        )
        assert verdict.passed is False
        assert any(f.rule_id == "AURA-SV-004" for f in verdict.findings)

    def test_hardcoded_secret_flagged(self):
        verifier = ASTRuleVerifier()
        verdict = verifier.verify(
            'API_KEY = "sk-prod-abcdef0123456789"\n'
            "def get_key():\n    return API_KEY\n"
        )
        assert verdict.passed is False
        assert any(f.rule_id == "AURA-SV-005" for f in verdict.findings)
        assert any(f.cwe_id == "CWE-798" for f in verdict.findings)

    def test_short_string_assignments_are_not_secrets(self):
        verifier = ASTRuleVerifier()
        verdict = verifier.verify('foo = "bar"\n')
        assert verdict.passed is True

    def test_unparseable_source_defers_to_normaliser(self):
        verifier = ASTRuleVerifier()
        verdict = verifier.verify("def broken(:")
        # Parse-fail does not double-fail; AST normaliser handles it.
        assert verdict.passed is True
        assert verdict.findings[0].rule_id == "AURA-SV-PARSE"

    def test_multiple_findings_aggregated(self):
        verifier = ASTRuleVerifier()
        verdict = verifier.verify(
            "import os, pickle\n"
            'API_KEY = "sk-prod-abcdef0123456789"\n'
            "def run(s):\n"
            "    eval(s)\n"
            "    os.system(s)\n"
            "    pickle.loads(b'')\n"
        )
        assert verdict.passed is False
        rule_ids = {f.rule_id for f in verdict.findings}
        assert {"AURA-SV-001", "AURA-SV-002", "AURA-SV-003", "AURA-SV-005"} <= rule_ids


# =============================================================================
# Dispatcher
# =============================================================================


@dataclass
class _AlwaysPassVerifier:
    verifier_id: str = "always-pass"

    def verify(self, source: str) -> StaticVerificationVerdict:
        return StaticVerificationVerdict(verifier_id=self.verifier_id, passed=True)


@dataclass
class _AlwaysFailVerifier:
    verifier_id: str = "always-fail"

    def verify(self, source: str) -> StaticVerificationVerdict:
        return StaticVerificationVerdict(
            verifier_id=self.verifier_id,
            passed=False,
            findings=(
                StaticVerificationFinding(
                    rule_id="TEST-001",
                    severity="HIGH",
                    message="forced disagreement",
                ),
            ),
        )


class TestDispatcher:
    def test_empty_dispatcher_is_empty(self):
        d = StaticVerifierDispatcher(verifiers=[])
        assert d.is_empty()
        report = d.verify("anything")
        assert report.verifier_count == 0
        assert report.agreed_with_llm is True

    def test_all_pass_agrees(self):
        d = StaticVerifierDispatcher([_AlwaysPassVerifier(), ASTRuleVerifier()])
        report = d.verify("def f(): return 1\n")
        assert report.agreed_with_llm is True
        assert report.verifier_count == 2

    def test_any_fail_disagrees(self):
        d = StaticVerifierDispatcher([_AlwaysPassVerifier(), _AlwaysFailVerifier()])
        report = d.verify("def f(): return 1\n")
        assert report.agreed_with_llm is False
        assert report.disagreed_with_llm is True
        assert any(v.passed is False for v in report.verdicts)

    def test_duplicate_verifier_id_rejected(self):
        with pytest.raises(ValueError):
            StaticVerifierDispatcher([_AlwaysPassVerifier(), _AlwaysPassVerifier()])


# =============================================================================
# ConsensusService integration (the actual issue #209 closure)
# =============================================================================


def _three_identical_outputs() -> list[str]:
    return [
        "def add(a: int, b: int) -> int:\n    return a + b\n",
        "def add(a: int, b: int) -> int:\n    return a + b\n",
        "def add(a: int, b: int) -> int:\n    return a + b\n",
    ]


def _three_unsafe_outputs() -> list[str]:
    """Three LLM runs all converge on dangerous code (eval)."""
    return [
        "def run(s: str):\n    return eval(s)\n",
        "def run(s: str):\n    return eval(s)\n",
        "def run(s: str):\n    return eval(s)\n",
    ]


def _make_generator(outputs: list[str]):
    """Builds an async generator returning outputs[0], [1], [2] in order."""
    iter_outputs = iter(outputs)

    async def _gen(prompt: str) -> str:
        return next(iter_outputs)

    return _gen


class TestConsensusServiceIntegration:
    @pytest.mark.asyncio
    async def test_no_static_verifier_behaves_like_pre_209(self):
        cfg = DVEConfig.for_testing()
        svc = ConsensusService(
            config=cfg, generator=_make_generator(_three_identical_outputs())
        )
        result = await svc.generate_and_check("dummy prompt")
        assert result.outcome == ConsensusOutcome.CONVERGED
        assert result.static_verification.enabled is False
        assert result.static_verification.agreed_with_llm is True

    @pytest.mark.asyncio
    async def test_static_voice_disagreement_forces_diverged_at_dal_a(self):
        # Policy: require_non_llm_voice=True (DAL A/B). Three runs converge
        # on eval()-laden code; static voice flags it as unsafe; outcome is
        # downgraded to DIVERGED so the orchestrator escalates to HITL.
        cfg = DVEConfig.for_testing()
        from dataclasses import replace

        cfg = replace(cfg, require_non_llm_voice=True)
        svc = ConsensusService(
            config=cfg,
            generator=_make_generator(_three_unsafe_outputs()),
            static_verifier=StaticVerifierDispatcher([ASTRuleVerifier()]),
        )
        result = await svc.generate_and_check("dummy prompt")
        assert result.outcome == ConsensusOutcome.DIVERGED
        assert result.selected_output is None  # forced HITL
        assert result.static_verification.enabled is True
        assert result.static_verification.agreed_with_llm is False
        assert result.static_verification.blocking_finding_count >= 1

    @pytest.mark.asyncio
    async def test_static_voice_agreement_keeps_converged(self):
        cfg = DVEConfig.for_testing()
        from dataclasses import replace

        cfg = replace(cfg, require_non_llm_voice=True)
        svc = ConsensusService(
            config=cfg,
            generator=_make_generator(_three_identical_outputs()),
            static_verifier=StaticVerifierDispatcher([ASTRuleVerifier()]),
        )
        result = await svc.generate_and_check("dummy prompt")
        assert result.outcome == ConsensusOutcome.CONVERGED
        assert result.selected_output is not None
        assert result.static_verification.enabled is True
        assert result.static_verification.agreed_with_llm is True

    @pytest.mark.asyncio
    async def test_shadow_mode_records_but_does_not_override(self):
        # Shadow mode: verifier runs and disagrees, but consensus outcome
        # is NOT overridden -- only audit-trail captures the disagreement.
        cfg = DVEConfig.for_testing()
        from dataclasses import replace

        cfg = replace(
            cfg, require_non_llm_voice=False, static_verifier_shadow_mode=True
        )
        svc = ConsensusService(
            config=cfg,
            generator=_make_generator(_three_unsafe_outputs()),
            static_verifier=StaticVerifierDispatcher([ASTRuleVerifier()]),
        )
        result = await svc.generate_and_check("dummy prompt")
        assert result.outcome == ConsensusOutcome.CONVERGED
        assert result.selected_output is not None
        assert result.static_verification.enabled is True
        assert result.static_verification.agreed_with_llm is False
        assert result.static_verification.blocking_finding_count >= 1

    @pytest.mark.asyncio
    async def test_dal_a_policy_with_no_verifier_fails_closed(self):
        # require_non_llm_voice=True but no dispatcher configured ->
        # fail-closed: downgrade to DIVERGED rather than silently accept.
        cfg = DVEConfig.for_testing()
        from dataclasses import replace

        cfg = replace(cfg, require_non_llm_voice=True)
        svc = ConsensusService(
            config=cfg, generator=_make_generator(_three_identical_outputs())
        )
        result = await svc.generate_and_check("dummy prompt")
        assert result.outcome == ConsensusOutcome.DIVERGED
        assert result.selected_output is None
        assert result.static_verification.enabled is False
        assert "fail-closed" in result.static_verification.rationale

    @pytest.mark.asyncio
    async def test_audit_dict_includes_static_verification(self):
        cfg = DVEConfig.for_testing()
        from dataclasses import replace

        cfg = replace(cfg, require_non_llm_voice=True)
        svc = ConsensusService(
            config=cfg,
            generator=_make_generator(_three_identical_outputs()),
            static_verifier=StaticVerifierDispatcher([ASTRuleVerifier()]),
        )
        result = await svc.generate_and_check("dummy prompt")
        audit = result.to_audit_dict()
        assert "static_verification" in audit
        assert audit["static_verification"]["enabled"] is True
        assert audit["static_verification"]["verifier_count"] == 1
