"""Stub object-code verifier (issue #210 Phase 1).

Returns ``NOT_IMPLEMENTED`` with a structured rationale so the DAL
gate can refuse to mark a verdict COMPLETED at DAL A while the real
toolchain integration is pending. The stub is deterministic, has no
side effects, and is safe to wire into every DAL profile that
references ``requires_object_code_verification=True``.

When Phase 2 (gcc + objdump) ships, replace registrations of
``NotImplementedObjectCodeVerifier`` with ``GccObjdumpVerifier``
through the same ``ObjectCodeVerifierPort`` -- no caller code
changes required.
"""

from __future__ import annotations

import time
from pathlib import Path

from src.services.verification_envelope.object_code.contracts import (
    ObjectCodeVerdict,
    ObjectCodeVerifierStatus,
)

_STUB_REASON: str = (
    "Object-code verification (DO-178C 6.4.4.2c) is configured for "
    "this DAL profile but the underlying toolchain is not yet "
    "integrated. Phase 1 ships the Port + gate; Phase 2 ships the "
    "gcc + objdump implementation; Phase 3 ships the embedded-target "
    "harness. Until then, the DAL gate refuses COMPLETED verdicts on "
    "DAL A profiles that require object-code verification."
)


class NotImplementedObjectCodeVerifier:
    """Deterministic stub used until the real verifier ships."""

    verifier_id: str = "object-code-stub-v1"

    def verify(
        self,
        *,
        source: str,
        target_triple: str,
        toolchain: str,
        scratch_dir: Path,
    ) -> ObjectCodeVerdict:
        start = time.time()
        return ObjectCodeVerdict(
            status=ObjectCodeVerifierStatus.NOT_IMPLEMENTED,
            verifier_id=self.verifier_id,
            target_triple=target_triple,
            toolchain=toolchain,
            source_symbol_count=0,
            object_symbol_count=0,
            rationale=_STUB_REASON,
            latency_ms=(time.time() - start) * 1000.0,
        )
