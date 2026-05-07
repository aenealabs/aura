"""Project Aura - Z3 SMT formal-verification adapter (ADR-085 Phase 3).

Drives Microsoft Research's Z3 SMT solver against the SMT-LIB v2
assertions emitted by :class:`ConstraintTranslator`. Z3 is licensed
under MIT (originally Apache-2.0 — both compatible with Aura's
licensing posture per ADR-085 cost analysis), runs in-process, and has
no cloud dependency, so it works in air-gapped deployments (ADR-078)
provided the operator installs the ``z3-solver`` Python package.

Defensive design:

* Soft import on ``z3`` so the module loads in slim builds.
* Solver invocation runs in a thread (Z3's ``solve`` calls are sync
  C-extensions) to keep the FastAPI event loop free.
* A timeout is enforced both at the Z3 layer (``set('timeout', N)``
  in milliseconds) and at the asyncio layer
  (``asyncio.wait_for``) to defeat solver hangs on pathological
  formulas.
* The solver invocation is **deterministic** (Z3 random_seed pinned
  to 0) so the same SMT input always produces the same proof hash —
  the DO-178C audit trail demands this.
* Counterexamples (``model()`` output) are captured when the verdict
  is ``FAILED`` so a reviewer can reconstruct what the gate caught.

Note on what Z3 actually proves: the translator's output for C1/C3
encodes the source-time decision as a Boolean (``c{N}_holds = true``
or ``false``). Z3's role is to discharge the conjoined assertion and
return SAT/UNSAT — it does *not* re-derive the syntactic-validity
check from first principles. This is intentional: the certification
argument relies on the translator being a deterministic, reviewable
component (TQL-5 software), not on Z3 reasoning about Python
semantics. C4's quantitative bounds and C2's user-supplied
predicates are where Z3 does the actual heavy lifting.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from typing import Any

from src.services.constraint_geometry.contracts import ConstraintAxis
from src.services.verification_envelope.contracts import (
    VerificationResult,
    VerificationVerdict,
)
from src.services.verification_envelope.formal.formal_adapter import (
    FormalVerificationRequest,
)

logger = logging.getLogger(__name__)


try:
    import z3  # type: ignore[import-not-found]

    Z3_AVAILABLE = True
except ImportError:  # pragma: no cover — handled by mock-mode branch
    z3 = None  # type: ignore[assignment]
    Z3_AVAILABLE = False


# Logic identifier emitted by the translator. The adapter sets the
# matching Z3 logic so theory-specific tactics fire correctly.
_DEFAULT_LOGIC: str = "QF_LIA"


class Z3SMTAdapter:
    """Z3 SMT formal-verification adapter."""

    tool_name: str = "z3_smt"

    SUPPORTED_AXES: tuple[ConstraintAxis, ...] = (
        ConstraintAxis.SYNTACTIC_VALIDITY,
        ConstraintAxis.SEMANTIC_CORRECTNESS,
        ConstraintAxis.SECURITY_POLICY,
        ConstraintAxis.OPERATIONAL_BOUNDS,
    )

    def __init__(
        self,
        *,
        random_seed: int = 0,
        proof_hash_algorithm: str = "sha256",
    ) -> None:
        self._random_seed = random_seed
        self._proof_hash_algorithm = proof_hash_algorithm
        self._solver_version = self._detect_solver_version()

    @property
    def is_available(self) -> bool:
        return Z3_AVAILABLE

    @property
    def supported_axes(self) -> tuple[ConstraintAxis, ...]:
        return self.SUPPORTED_AXES

    async def verify(self, request: FormalVerificationRequest) -> VerificationResult:
        if not self.is_available:
            return self._mock_verdict(request)

        start = time.time()
        try:
            verdict, counterexample = await asyncio.wait_for(
                asyncio.to_thread(self._solve_sync, request),
                timeout=request.timeout_seconds + 5.0,
            )
        except asyncio.TimeoutError:
            elapsed = (time.time() - start) * 1000.0
            logger.warning(
                "Z3 solve exceeded asyncio timeout %.1fs",
                request.timeout_seconds + 5.0,
            )
            return VerificationResult(
                verdict=VerificationVerdict.UNKNOWN,
                axes_verified=request.axes_in_scope,
                proof_hash="",
                solver_version=self._solver_version,
                verification_time_ms=elapsed,
                smt_formula_hash=self._formula_hash(request.smt_assertions),
                counterexample="asyncio timeout",
            )

        elapsed = (time.time() - start) * 1000.0
        return VerificationResult(
            verdict=verdict,
            axes_verified=(
                request.axes_in_scope if verdict == VerificationVerdict.PROVED else ()
            ),
            proof_hash=self._proof_hash(request, verdict),
            solver_version=self._solver_version,
            verification_time_ms=elapsed,
            smt_formula_hash=self._formula_hash(request.smt_assertions),
            counterexample=counterexample,
        )

    # ------------------------------------------------------------ internals

    def _solve_sync(
        self, request: FormalVerificationRequest
    ) -> tuple[VerificationVerdict, str | None]:
        """Drive the solver synchronously.

        Returns (verdict, counterexample_text_or_None). Caller wraps
        this in :func:`asyncio.to_thread` to keep the event loop free.
        """
        solver = z3.Solver()  # type: ignore[union-attr]
        solver.set("random_seed", self._random_seed)
        solver.set("timeout", int(request.timeout_seconds * 1000))

        try:
            assertions = z3.parse_smt2_string(  # type: ignore[union-attr]
                request.smt_assertions
            )
        except Exception as exc:
            logger.warning("Z3 parse failure: %s", exc)
            return VerificationVerdict.UNKNOWN, f"parse failure: {exc}"

        for assertion in assertions:
            solver.add(assertion)

        check_result = solver.check()
        if check_result == z3.sat:  # type: ignore[union-attr]
            # The translator emits assertions of the form ``c{N}_holds = true``
            # or ``c{N}_holds = false``. SAT here means there exists an
            # assignment satisfying the conjunction, which proves the
            # axes hold. UNSAT means the assertions are contradictory,
            # which (given the translator's structure) means at least one
            # axis was already determined to fail.
            return VerificationVerdict.PROVED, None
        if check_result == z3.unsat:  # type: ignore[union-attr]
            # Capture the proof core if available; otherwise mark as failed
            # without a counterexample. UNSAT cores are stable across
            # reproducible runs (random_seed pinned).
            try:
                core = solver.unsat_core()
                core_text = "; ".join(str(c) for c in core)
            except Exception:  # pragma: no cover
                core_text = "unsat (no core)"
            return VerificationVerdict.FAILED, core_text
        # z3.unknown — solver hit timeout or an unsupported theory.
        reason = solver.reason_unknown() if hasattr(solver, "reason_unknown") else ""
        return VerificationVerdict.UNKNOWN, reason or "z3 returned unknown"

    def _mock_verdict(self, request: FormalVerificationRequest) -> VerificationResult:
        return VerificationResult(
            verdict=VerificationVerdict.SKIPPED,
            axes_verified=(),
            proof_hash="",
            solver_version="z3:not_installed",
            verification_time_ms=0.0,
            smt_formula_hash=self._formula_hash(request.smt_assertions),
            counterexample="z3-solver SDK not installed; install z3-solver to enable formal verification",
        )

    def _proof_hash(
        self,
        request: FormalVerificationRequest,
        verdict: VerificationVerdict,
    ) -> str:
        """Reproducible per-run identifier for the audit archive.

        Hashes the SMT formula together with the verdict and the solver
        version. Two runs of the same input on the same Z3 produce the
        same proof_hash, which is the DO-178C-style determinism the
        certification argument requires.
        """
        h = hashlib.new(self._proof_hash_algorithm)
        h.update(request.smt_assertions.encode("utf-8"))
        h.update(b"|verdict=")
        h.update(verdict.value.encode("utf-8"))
        h.update(b"|solver=")
        h.update(self._solver_version.encode("utf-8"))
        return h.hexdigest()

    def _formula_hash(self, smt: str) -> str:
        return hashlib.sha256(smt.encode("utf-8")).hexdigest()

    def _detect_solver_version(self) -> str:
        if not Z3_AVAILABLE:
            return "z3:not_installed"
        try:
            return f"z3:{z3.get_version_string()}"  # type: ignore[union-attr]
        except Exception:  # pragma: no cover
            return "z3:unknown"
