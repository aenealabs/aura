"""Tests for the object-code verification scaffold (issue #210 Phase 1).

Covers the Port contract, the stub verifier, and the DAL gate
behaviour. The real toolchain integration (gcc + objdump, embedded
target harness) ships in follow-on phases; these tests assert the
gate-level behaviour the scaffold guarantees.
"""

from __future__ import annotations

from pathlib import Path

from src.services.verification_envelope.object_code import (
    NotImplementedObjectCodeVerifier,
    ObjectCodeGate,
    ObjectCodeVerdict,
    ObjectCodeVerifierStatus,
)
from src.services.verification_envelope.policies.do178c_profiles import (
    DAL_A_PROFILE_NAME,
    DAL_B_PROFILE_NAME,
    DAL_C_PROFILE_NAME,
    DEFAULT_PROFILE_NAME,
    get_coverage_policy,
)

# =============================================================================
# Stub verifier
# =============================================================================


class TestStubVerifier:
    def test_stub_returns_not_implemented(self, tmp_path: Path):
        verifier = NotImplementedObjectCodeVerifier()
        verdict = verifier.verify(
            source="def f(): return 1\n",
            target_triple="x86_64-linux-gnu",
            toolchain="gcc-13",
            scratch_dir=tmp_path,
        )
        assert verdict.status == ObjectCodeVerifierStatus.NOT_IMPLEMENTED
        assert verdict.passed is False
        assert "not yet integrated" in verdict.rationale
        assert verdict.verifier_id == "object-code-stub-v1"

    def test_stub_is_deterministic(self, tmp_path: Path):
        verifier = NotImplementedObjectCodeVerifier()
        v1 = verifier.verify(
            source="x = 1",
            target_triple="x86_64",
            toolchain="gcc",
            scratch_dir=tmp_path,
        )
        v2 = verifier.verify(
            source="x = 1",
            target_triple="x86_64",
            toolchain="gcc",
            scratch_dir=tmp_path,
        )
        assert v1.status == v2.status
        assert v1.rationale == v2.rationale


# =============================================================================
# Gate behaviour with the stub
# =============================================================================


class TestObjectCodeGateAgainstStub:
    def test_dal_a_with_stub_fails_closed(self, tmp_path: Path):
        gate = ObjectCodeGate(verifier=NotImplementedObjectCodeVerifier())
        result = gate.evaluate(
            policy=get_coverage_policy(DAL_A_PROFILE_NAME),
            source="x = 1",
            scratch_dir=tmp_path,
        )
        assert result.required is True
        assert result.passed is False
        assert result.verdict is not None
        assert result.verdict.status == ObjectCodeVerifierStatus.NOT_IMPLEMENTED

    def test_dal_b_does_not_require_verification(self, tmp_path: Path):
        # DAL_B has requires_object_code_verification=False per the policy.
        gate = ObjectCodeGate(verifier=NotImplementedObjectCodeVerifier())
        result = gate.evaluate(
            policy=get_coverage_policy(DAL_B_PROFILE_NAME),
            source="x = 1",
            scratch_dir=tmp_path,
        )
        assert result.required is False
        assert result.passed is True
        assert result.verdict is None

    def test_dal_c_does_not_require_verification(self, tmp_path: Path):
        gate = ObjectCodeGate(verifier=NotImplementedObjectCodeVerifier())
        result = gate.evaluate(
            policy=get_coverage_policy(DAL_C_PROFILE_NAME),
            source="x = 1",
            scratch_dir=tmp_path,
        )
        assert result.passed is True
        assert result.required is False

    def test_default_profile_does_not_require_verification(self, tmp_path: Path):
        gate = ObjectCodeGate(verifier=NotImplementedObjectCodeVerifier())
        result = gate.evaluate(
            policy=get_coverage_policy(DEFAULT_PROFILE_NAME),
            source="x = 1",
            scratch_dir=tmp_path,
        )
        assert result.passed is True
        assert result.required is False


# =============================================================================
# Gate fail-closed when no verifier configured
# =============================================================================


class TestGateFailClosedWithoutVerifier:
    def test_dal_a_without_verifier_fails_closed(self):
        gate = ObjectCodeGate(verifier=None)
        result = gate.evaluate(
            policy=get_coverage_policy(DAL_A_PROFILE_NAME),
            source="x = 1",
        )
        assert result.required is True
        assert result.passed is False
        assert "no verifier is" in result.rationale.lower()

    def test_non_dal_a_without_verifier_still_passes(self):
        gate = ObjectCodeGate(verifier=None)
        result = gate.evaluate(
            policy=get_coverage_policy(DAL_B_PROFILE_NAME),
            source="x = 1",
        )
        assert result.passed is True


# =============================================================================
# Gate behaviour with a hand-crafted MATCHED verdict
# =============================================================================


class _AlwaysMatchedVerifier:
    """Test-only verifier that always returns MATCHED for the happy path."""

    verifier_id: str = "always-matched"

    def verify(
        self,
        *,
        source: str,
        target_triple: str,
        toolchain: str,
        scratch_dir: Path,
    ) -> ObjectCodeVerdict:
        return ObjectCodeVerdict(
            status=ObjectCodeVerifierStatus.MATCHED,
            verifier_id=self.verifier_id,
            target_triple=target_triple,
            toolchain=toolchain,
            source_symbol_count=4,
            object_symbol_count=4,
            rationale="symbol sets identical (test verifier)",
        )


class _AlwaysMismatchedVerifier:
    verifier_id: str = "always-mismatched"

    def verify(
        self,
        *,
        source: str,
        target_triple: str,
        toolchain: str,
        scratch_dir: Path,
    ) -> ObjectCodeVerdict:
        return ObjectCodeVerdict(
            status=ObjectCodeVerifierStatus.MISMATCHED,
            verifier_id=self.verifier_id,
            target_triple=target_triple,
            toolchain=toolchain,
            source_symbol_count=4,
            object_symbol_count=6,
            unexpected_symbols=("__compiler_inserted_a", "__compiler_inserted_b"),
            rationale="2 unexpected symbols (test verifier)",
        )


class TestGateWithRealVerifierShapes:
    def test_matched_verdict_passes_dal_a(self):
        gate = ObjectCodeGate(verifier=_AlwaysMatchedVerifier())
        result = gate.evaluate(
            policy=get_coverage_policy(DAL_A_PROFILE_NAME),
            source="int main(){return 0;}",
            target_triple="x86_64-linux-gnu",
            toolchain="gcc-13",
        )
        assert result.passed is True
        assert result.required is True
        assert result.verdict is not None
        assert result.verdict.status == ObjectCodeVerifierStatus.MATCHED

    def test_mismatched_verdict_fails_dal_a(self):
        gate = ObjectCodeGate(verifier=_AlwaysMismatchedVerifier())
        result = gate.evaluate(
            policy=get_coverage_policy(DAL_A_PROFILE_NAME),
            source="int main(){return 0;}",
        )
        assert result.passed is False
        assert result.required is True
        assert result.verdict is not None
        assert result.verdict.status == ObjectCodeVerifierStatus.MISMATCHED
        assert len(result.verdict.unexpected_symbols) == 2

    def test_toolchain_unavailable_also_fails_dal_a(self):
        class _UnavailableVerifier:
            verifier_id = "unavailable"

            def verify(self, *, source, target_triple, toolchain, scratch_dir):
                return ObjectCodeVerdict(
                    status=ObjectCodeVerifierStatus.TOOLCHAIN_UNAVAILABLE,
                    verifier_id=self.verifier_id,
                    target_triple=target_triple,
                    toolchain=toolchain,
                    rationale="gcc not in PATH",
                )

        gate = ObjectCodeGate(verifier=_UnavailableVerifier())
        result = gate.evaluate(
            policy=get_coverage_policy(DAL_A_PROFILE_NAME),
            source="x = 1",
        )
        assert result.passed is False
        assert result.verdict.status == ObjectCodeVerifierStatus.TOOLCHAIN_UNAVAILABLE


# =============================================================================
# Audit dict
# =============================================================================


class TestAuditDict:
    def test_verdict_to_audit_dict(self, tmp_path: Path):
        verdict = NotImplementedObjectCodeVerifier().verify(
            source="x = 1",
            target_triple="x86_64",
            toolchain="gcc",
            scratch_dir=tmp_path,
        )
        audit = verdict.to_audit_dict()
        assert audit["status"] == "not_implemented"
        assert audit["verifier_id"] == "object-code-stub-v1"
        assert "rationale" in audit
        assert "computed_at" in audit

    def test_gate_result_to_audit_dict(self, tmp_path: Path):
        gate = ObjectCodeGate(verifier=NotImplementedObjectCodeVerifier())
        result = gate.evaluate(
            policy=get_coverage_policy(DAL_A_PROFILE_NAME),
            source="x = 1",
            scratch_dir=tmp_path,
        )
        audit = result.to_audit_dict()
        assert audit["passed"] is False
        assert audit["required"] is True
        assert audit["verdict"]["status"] == "not_implemented"
