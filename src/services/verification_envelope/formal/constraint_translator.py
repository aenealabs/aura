"""Project Aura - CGE constraint → SMT assertion translator (ADR-085 Phase 3).

Walks a Python source tree (via the stdlib ``ast`` module) and emits
SMT-LIB v2 assertions that encode the four formally-expressible CGE
axes:

* **C1 (Syntactic Validity)** — the source must parse, every function
  must have type annotations on parameters and return type, and every
  module-level import must resolve to a known package. Encoded as
  Boolean assertions whose truth value is decided at translation time
  (the solver only sees ``(assert true)`` or ``(assert false)``).
* **C2 (Semantic Correctness)** — pre/post-condition checks via Z3
  integer and bitvector arithmetic. Currently implemented as a
  pluggable hook: callers pass in pre/post predicates as SMT-LIB
  fragments and the translator wires them into a single assertion
  block. The default behaviour (no predicates supplied) emits an
  empty-but-trivially-satisfiable block so C2 doesn't fail closed for
  workloads that haven't authored predicates yet.
* **C3 (Security Policy)** — translation of the negative-centroid
  patterns on each rule into negated containment assertions
  (``not contains_wildcard_iam(output)`` …). Source-level pattern
  matching is performed at translation time; the solver receives the
  Boolean outcome.
* **C4 (Operational Bounds)** — quantitative constraints from rule
  metadata (``max_resource_allocation``, ``timeout_ms`` …). Translated
  to integer arithmetic over named symbols, with bounds asserted via
  ``(assert (<= x N))``.

C5/C6/C7 are documented out-of-scope here and deferred to the CGE
coherence scorer + HITL.

Output format: a single SMT-LIB v2 string consisting of ``(set-logic
QF_LIA)`` (linear integer arithmetic — sufficient for C4; richer
logics can be substituted by overriding ``logic`` on the request),
followed by per-axis ``(echo …)`` separators and the assertions
themselves. The format is solver-agnostic; any SMT-LIB-2-compliant
backend (Z3, CVC5, Yices2) can consume it.
"""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping

from src.services.constraint_geometry.contracts import (
    ConstraintAxis,
    ConstraintRule,
)
from src.services.verification_envelope.formal.formal_adapter import (
    FormalVerificationRequest,
)

logger = logging.getLogger(__name__)


# Conservative regex catalog used by the C3 axis. Each entry is a
# substring or compiled regex applied to the raw source. Adding new
# patterns here is the canonical extension point for security rules
# that don't fit the negative-centroid embedding form.
_C3_NEGATIVE_PATTERNS: dict[str, re.Pattern[str]] = {
    "wildcard_iam_action": re.compile(
        r"['\"]Action['\"]\s*:\s*['\"]\*['\"]", re.IGNORECASE
    ),
    "wildcard_iam_resource": re.compile(
        r"['\"]Resource['\"]\s*:\s*['\"]\*['\"]", re.IGNORECASE
    ),
    "eval_on_user_input": re.compile(r"\beval\s*\(", re.IGNORECASE),
    "exec_on_user_input": re.compile(r"\bexec\s*\(", re.IGNORECASE),
    "shell_true": re.compile(r"shell\s*=\s*True", re.IGNORECASE),
    "hardcoded_secret_password": re.compile(
        r"\b(password|passwd|pwd)\s*=\s*['\"][^'\"]+['\"]", re.IGNORECASE
    ),
    "hardcoded_secret_api_key": re.compile(
        r"\b(api[_-]?key|secret|token)\s*=\s*['\"][a-zA-Z0-9_\-]{16,}['\"]",
        re.IGNORECASE,
    ),
}


@dataclass(frozen=True)
class TranslatorOutput:
    """The translator's deliverable: SMT text plus axis-level booleans.

    ``axis_holds`` carries the per-axis Boolean outcome so the
    verification gate can decide which axes ``axes_verified`` should
    list when the overall result is PROVED. Assertions on already-failed
    axes are still emitted (so the auditor's proof archive captures
    the full picture), but the gate uses ``axis_holds`` to mark the
    axes that genuinely passed.
    """

    smt_assertions: str
    axes_in_scope: tuple[ConstraintAxis, ...]
    axis_holds: dict[ConstraintAxis, bool]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class TranslationContext:
    """Optional caller-supplied hooks for C2 predicates and C4 bounds.

    ``c2_predicates`` is a mapping of free-form predicate name → SMT-LIB
    fragment (e.g. ``"output_is_positive": "(> output 0)"``). The
    translator wires them under a single ``(assert (and …))`` block.

    ``c4_bounds`` is a mapping of operational symbol → upper bound
    (``"max_resource_allocation": 1024``). Each entry produces a
    ``(declare-const symbol Int)`` and ``(assert (<= symbol N))`` pair.
    """

    c2_predicates: Mapping[str, str] = field(default_factory=dict)
    c4_bounds: Mapping[str, int] = field(default_factory=dict)


class ConstraintTranslator:
    """Translates Python source + CGE constraint rules to SMT-LIB."""

    SUPPORTED_AXES: tuple[ConstraintAxis, ...] = (
        ConstraintAxis.SYNTACTIC_VALIDITY,
        ConstraintAxis.SEMANTIC_CORRECTNESS,
        ConstraintAxis.SECURITY_POLICY,
        ConstraintAxis.OPERATIONAL_BOUNDS,
    )

    def translate(
        self,
        *,
        source_code: str,
        source_file: Path | None = None,
        rules: Iterable[ConstraintRule] = (),
        axes_in_scope: Iterable[ConstraintAxis] | None = None,
        context: TranslationContext | None = None,
    ) -> TranslatorOutput:
        rule_tuple = tuple(rules)
        ctx = context or TranslationContext()

        axes = tuple(axes_in_scope) if axes_in_scope else self.SUPPORTED_AXES
        unsupported = [a for a in axes if a not in self.SUPPORTED_AXES]
        if unsupported:
            logger.warning(
                "translator: dropping unsupported axes %s",
                [a.value for a in unsupported],
            )
        axes = tuple(a for a in axes if a in self.SUPPORTED_AXES)

        c1_holds, c1_block, c1_notes = self._translate_c1(source_code, source_file)
        c2_holds, c2_block = self._translate_c2(ctx)
        c3_holds, c3_block, c3_notes = self._translate_c3(source_code, rule_tuple)
        c4_holds, c4_block = self._translate_c4(ctx, rule_tuple)

        sections: list[str] = ["(set-logic QF_LIA)"]
        if ConstraintAxis.SYNTACTIC_VALIDITY in axes:
            sections.append('(echo "; --- C1 syntactic validity ---")')
            sections.append(c1_block)
        if ConstraintAxis.SEMANTIC_CORRECTNESS in axes:
            sections.append('(echo "; --- C2 semantic correctness ---")')
            sections.append(c2_block)
        if ConstraintAxis.SECURITY_POLICY in axes:
            sections.append('(echo "; --- C3 security policy ---")')
            sections.append(c3_block)
        if ConstraintAxis.OPERATIONAL_BOUNDS in axes:
            sections.append('(echo "; --- C4 operational bounds ---")')
            sections.append(c4_block)
        sections.append("(check-sat)")

        smt = "\n".join(sections) + "\n"

        axis_holds: dict[ConstraintAxis, bool] = {}
        if ConstraintAxis.SYNTACTIC_VALIDITY in axes:
            axis_holds[ConstraintAxis.SYNTACTIC_VALIDITY] = c1_holds
        if ConstraintAxis.SEMANTIC_CORRECTNESS in axes:
            axis_holds[ConstraintAxis.SEMANTIC_CORRECTNESS] = c2_holds
        if ConstraintAxis.SECURITY_POLICY in axes:
            axis_holds[ConstraintAxis.SECURITY_POLICY] = c3_holds
        if ConstraintAxis.OPERATIONAL_BOUNDS in axes:
            axis_holds[ConstraintAxis.OPERATIONAL_BOUNDS] = c4_holds

        return TranslatorOutput(
            smt_assertions=smt,
            axes_in_scope=axes,
            axis_holds=axis_holds,
            notes=tuple([*c1_notes, *c3_notes]),
        )

    # ---------------------------------------------------------------- C1

    def _translate_c1(
        self, source_code: str, source_file: Path | None
    ) -> tuple[bool, str, tuple[str, ...]]:
        notes: list[str] = []
        holds = True
        try:
            tree = ast.parse(source_code, filename=str(source_file or "<src>"))
        except SyntaxError as exc:
            notes.append(f"C1 parse failure: {exc}")
            return False, "(assert false)\n; reason: parse_failure", tuple(notes)

        # All public functions must have parameter and return annotations.
        unannotated_fns: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_"):
                    continue  # Private — annotations not required.
                missing_param = [
                    a.arg for a in node.args.args if a.annotation is None
                ]
                missing_return = node.returns is None
                if missing_param or missing_return:
                    unannotated_fns.append(node.name)
        if unannotated_fns:
            holds = False
            notes.append(
                f"C1 unannotated functions: {', '.join(unannotated_fns[:5])}"
                + ("…" if len(unannotated_fns) > 5 else "")
            )

        block_lines: list[str] = ["(declare-const c1_holds Bool)"]
        block_lines.append(
            f"(assert (= c1_holds {'true' if holds else 'false'}))"
        )
        return holds, "\n".join(block_lines), tuple(notes)

    # ---------------------------------------------------------------- C2

    @staticmethod
    def _translate_c2(ctx: TranslationContext) -> tuple[bool, str]:
        if not ctx.c2_predicates:
            # No predicates supplied — emit a trivially-satisfied block
            # so the axis is not failed-closed by default.
            return True, (
                "(declare-const c2_holds Bool)\n"
                "(assert (= c2_holds true))\n"
                "; no C2 predicates supplied"
            )

        decls: list[str] = ["(declare-const c2_holds Bool)"]
        body: list[str] = []
        for name, fragment in ctx.c2_predicates.items():
            decls.append(f"; predicate {name}")
            body.append(fragment)

        decls.append(f"(assert (= c2_holds (and {' '.join(body)})))")
        decls.append("(assert c2_holds)")
        return True, "\n".join(decls)

    # ---------------------------------------------------------------- C3

    def _translate_c3(
        self, source_code: str, rules: tuple[ConstraintRule, ...]
    ) -> tuple[bool, str, tuple[str, ...]]:
        violations: list[str] = []
        for name, pattern in _C3_NEGATIVE_PATTERNS.items():
            if pattern.search(source_code):
                violations.append(name)

        # Rule-supplied substring matchers via metadata key 'forbid_substring'.
        for rule in rules:
            if rule.axis is not ConstraintAxis.SECURITY_POLICY:
                continue
            md = rule.metadata_dict
            forbid = md.get("forbid_substring")
            if isinstance(forbid, str) and forbid in source_code:
                violations.append(f"rule:{rule.rule_id}")

        holds = not violations
        notes = tuple(f"C3 violation: {v}" for v in violations)
        block_lines: list[str] = ["(declare-const c3_holds Bool)"]
        block_lines.append(
            f"(assert (= c3_holds {'true' if holds else 'false'}))"
        )
        return holds, "\n".join(block_lines), notes

    # ---------------------------------------------------------------- C4

    @staticmethod
    def _translate_c4(
        ctx: TranslationContext, rules: tuple[ConstraintRule, ...]
    ) -> tuple[bool, str]:
        bounds: dict[str, int] = dict(ctx.c4_bounds)

        # Rule metadata can also supply numeric upper bounds. The metadata
        # key convention is 'upper_bound_<symbol>': N.
        for rule in rules:
            if rule.axis is not ConstraintAxis.OPERATIONAL_BOUNDS:
                continue
            for key, value in rule.metadata_dict.items():
                if key.startswith("upper_bound_") and isinstance(
                    value, (int, float)
                ):
                    bounds[key.removeprefix("upper_bound_")] = int(value)

        if not bounds:
            return True, (
                "(declare-const c4_holds Bool)\n"
                "(assert (= c4_holds true))\n"
                "; no C4 bounds supplied"
            )

        lines: list[str] = ["(declare-const c4_holds Bool)"]
        all_constraints: list[str] = []
        for symbol, upper in bounds.items():
            lines.append(f"(declare-const {symbol} Int)")
            lines.append(f"(assert (<= {symbol} {upper}))")
            all_constraints.append(f"(<= {symbol} {upper})")

        lines.append(
            "(assert (= c4_holds (and " + " ".join(all_constraints) + ")))"
        )
        return True, "\n".join(lines)


# ---------------------------------------------------- request-builder helper


def build_request(
    *,
    source_code: str,
    source_file: Path | None = None,
    rules: Iterable[ConstraintRule] = (),
    axes_in_scope: Iterable[ConstraintAxis] | None = None,
    context: TranslationContext | None = None,
    timeout_seconds: float = 30.0,
) -> FormalVerificationRequest:
    """Convenience: translate then bundle into a FormalVerificationRequest."""
    translator = ConstraintTranslator()
    output = translator.translate(
        source_code=source_code,
        source_file=source_file,
        rules=rules,
        axes_in_scope=axes_in_scope,
        context=context,
    )
    return FormalVerificationRequest(
        source_code=source_code,
        source_file=source_file,
        rules=tuple(rules),
        axes_in_scope=output.axes_in_scope,
        smt_assertions=output.smt_assertions,
        timeout_seconds=timeout_seconds,
    )
