"""Gate that integrates object-code verification into the DAL policy.

Consumers (callers of the consensus / coverage / formal pipeline) hand
the gate a DAL policy and the source they want to certify. The gate
consults the policy's ``requires_object_code_verification`` flag and,
when set, runs the configured ``ObjectCodeVerifierPort`` over the
source. The gate's ``passed`` field is True only when:

  - the policy does not require object-code verification, OR
  - the policy requires it AND the verifier returned MATCHED.

NOT_IMPLEMENTED, TOOLCHAIN_UNAVAILABLE, and MISMATCHED all result in
``passed=False`` so the upstream DVE pipeline forces HITL escalation
rather than silently marking a DAL A verdict COMPLETED with a stub
verifier in the loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.services.verification_envelope.object_code.contracts import (
    ObjectCodeVerdict,
    ObjectCodeVerifierStatus,
)
from src.services.verification_envelope.object_code.port import ObjectCodeVerifierPort
from src.services.verification_envelope.policies.do178c_profiles import (
    DALCoveragePolicy,
)


@dataclass(frozen=True)
class ObjectCodeGateResult:
    """Outcome of the gate."""

    passed: bool
    required: bool  # did the policy require object-code verification?
    verdict: Optional[ObjectCodeVerdict]
    rationale: str

    def to_audit_dict(self) -> dict:
        return {
            "passed": self.passed,
            "required": self.required,
            "rationale": self.rationale,
            "verdict": self.verdict.to_audit_dict() if self.verdict else None,
        }


class ObjectCodeGate:
    """Integrate :class:`ObjectCodeVerifierPort` with a DAL policy."""

    def __init__(self, verifier: Optional[ObjectCodeVerifierPort] = None) -> None:
        # When None, the gate behaves as if no verifier is configured.
        # That is a CONFIGURATION ERROR for policies that require
        # object-code verification -- the gate returns passed=False
        # with a clear rationale so deployment doesn't accidentally
        # claim DAL A compliance without the gate running.
        self._verifier = verifier

    def evaluate(
        self,
        *,
        policy: DALCoveragePolicy,
        source: str,
        target_triple: str = "x86_64-linux-gnu",
        toolchain: str = "gcc",
        scratch_dir: Optional[Path] = None,
    ) -> ObjectCodeGateResult:
        if not policy.requires_object_code_verification:
            return ObjectCodeGateResult(
                passed=True,
                required=False,
                verdict=None,
                rationale=(
                    f"DAL profile {policy.profile_name!r} does not require "
                    f"object-code verification (DO-178C 6.4.4.2c)."
                ),
            )

        if self._verifier is None:
            return ObjectCodeGateResult(
                passed=False,
                required=True,
                verdict=None,
                rationale=(
                    f"DAL profile {policy.profile_name!r} requires "
                    f"object-code verification but no verifier is "
                    f"configured. Gate fails closed (#210)."
                ),
            )

        verdict = self._verifier.verify(
            source=source,
            target_triple=target_triple,
            toolchain=toolchain,
            scratch_dir=scratch_dir or Path("/tmp/aura-obj-code-scratch"),
        )

        # MATCHED is the only passing state. NOT_IMPLEMENTED,
        # TOOLCHAIN_UNAVAILABLE, MISMATCHED all block COMPLETED.
        passed = verdict.status == ObjectCodeVerifierStatus.MATCHED
        return ObjectCodeGateResult(
            passed=passed,
            required=True,
            verdict=verdict,
            rationale=(
                verdict.rationale
                or f"Object-code verifier returned {verdict.status.value}."
            ),
        )
