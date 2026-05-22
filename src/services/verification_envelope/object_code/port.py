"""Port definition for object-code verification (issue #210).

The Port is intentionally narrow so future implementations can drop
in without touching the gate or callers:

- Phase 1 (this PR): ``NotImplementedObjectCodeVerifier`` -- stub that
  returns NOT_IMPLEMENTED with structured reason.
- Phase 2 (follow-up): ``GccObjdumpVerifier`` -- gcc cross-compile +
  objdump symbol-table extraction + symbol-set comparison against
  the source AST symbol set extracted by ADR-093 Phase 2.
- Phase 3 (follow-up): ``EmbeddedTargetVerifier`` -- ARM/PowerPC
  target board integration via openocd / pyocd, on-target test
  execution with structural coverage capture.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from src.services.verification_envelope.object_code.contracts import ObjectCodeVerdict


class ObjectCodeVerifierPort(Protocol):
    """Verify object code traceability for a source unit.

    Implementations must be **deterministic** for a given (source,
    toolchain, target_triple) triple, and **side-effect-free** beyond
    writing to a sandbox / scratch directory. Latency budget is
    minutes (not seconds) -- this runs in the slow lane of the DVE
    pipeline after consensus + coverage + formal verification.
    """

    verifier_id: str

    def verify(
        self,
        *,
        source: str,
        target_triple: str,
        toolchain: str,
        scratch_dir: Path,
    ) -> ObjectCodeVerdict:
        """Verify ``source`` compiles to object code that matches.

        Returns a :class:`ObjectCodeVerdict`. Implementations should
        NOT raise -- failures (compile error, missing toolchain,
        symbol mismatch) are encoded in the verdict's ``status`` and
        ``rationale`` fields so the DAL gate can log them
        deterministically.
        """
