"""Tests for the CGE → SMT constraint translator."""

from __future__ import annotations

from src.services.constraint_geometry.contracts import (
    ConstraintAxis,
    ConstraintRule,
)
from src.services.verification_envelope.formal import (
    ConstraintTranslator,
    TranslationContext,
    build_request,
)


def _annotated_clean_source() -> str:
    return "def add(a: int, b: int) -> int:\n    return a + b\n"


def _unannotated_source() -> str:
    return "def add(a, b):\n    return a + b\n"


def _eval_source() -> str:
    return "def f(x):\n    return eval(x)\n"


def _wildcard_iam_source() -> str:
    return '''
policy = {
    "Statement": [{"Action": "*", "Resource": "arn:aws:s3:::bucket/*"}]
}
'''


# --------------------------------------------------------------------- C1


def test_clean_annotated_source_passes_c1() -> None:
    out = ConstraintTranslator().translate(
        source_code=_annotated_clean_source(),
        axes_in_scope=(ConstraintAxis.SYNTACTIC_VALIDITY,),
    )
    assert out.axis_holds[ConstraintAxis.SYNTACTIC_VALIDITY] is True
    # The SMT block records c1_holds = true.
    assert "(assert (= c1_holds true))" in out.smt_assertions


def test_unannotated_source_fails_c1() -> None:
    out = ConstraintTranslator().translate(
        source_code=_unannotated_source(),
        axes_in_scope=(ConstraintAxis.SYNTACTIC_VALIDITY,),
    )
    assert out.axis_holds[ConstraintAxis.SYNTACTIC_VALIDITY] is False
    assert "(assert (= c1_holds false))" in out.smt_assertions
    assert any("unannotated" in n for n in out.notes)


def test_parse_failure_fails_c1() -> None:
    out = ConstraintTranslator().translate(
        source_code="def broken(:\n",
        axes_in_scope=(ConstraintAxis.SYNTACTIC_VALIDITY,),
    )
    assert out.axis_holds[ConstraintAxis.SYNTACTIC_VALIDITY] is False
    assert any("parse failure" in n for n in out.notes)


def test_private_function_does_not_require_annotations() -> None:
    """Private (underscore-prefixed) helpers don't need annotations."""
    out = ConstraintTranslator().translate(
        source_code="def _helper(a, b):\n    return a + b\n",
        axes_in_scope=(ConstraintAxis.SYNTACTIC_VALIDITY,),
    )
    assert out.axis_holds[ConstraintAxis.SYNTACTIC_VALIDITY] is True


# --------------------------------------------------------------------- C2


def test_c2_with_no_predicates_passes() -> None:
    out = ConstraintTranslator().translate(
        source_code=_annotated_clean_source(),
        axes_in_scope=(ConstraintAxis.SEMANTIC_CORRECTNESS,),
    )
    assert out.axis_holds[ConstraintAxis.SEMANTIC_CORRECTNESS] is True
    assert "no C2 predicates supplied" in out.smt_assertions


def test_c2_predicates_emitted_into_smt() -> None:
    ctx = TranslationContext(
        c2_predicates={
            "output_is_positive": "(> output 0)",
            "input_is_bounded": "(<= input 100)",
        }
    )
    out = ConstraintTranslator().translate(
        source_code=_annotated_clean_source(),
        axes_in_scope=(ConstraintAxis.SEMANTIC_CORRECTNESS,),
        context=ctx,
    )
    assert "(> output 0)" in out.smt_assertions
    assert "(<= input 100)" in out.smt_assertions


# --------------------------------------------------------------------- C3


def test_eval_call_violates_c3() -> None:
    out = ConstraintTranslator().translate(
        source_code=_eval_source(),
        axes_in_scope=(ConstraintAxis.SECURITY_POLICY,),
    )
    assert out.axis_holds[ConstraintAxis.SECURITY_POLICY] is False
    assert "(assert (= c3_holds false))" in out.smt_assertions
    assert any("eval_on_user_input" in n for n in out.notes)


def test_wildcard_iam_violates_c3() -> None:
    out = ConstraintTranslator().translate(
        source_code=_wildcard_iam_source(),
        axes_in_scope=(ConstraintAxis.SECURITY_POLICY,),
    )
    assert out.axis_holds[ConstraintAxis.SECURITY_POLICY] is False
    assert any("wildcard_iam_action" in n for n in out.notes)


def test_clean_source_passes_c3() -> None:
    out = ConstraintTranslator().translate(
        source_code=_annotated_clean_source(),
        axes_in_scope=(ConstraintAxis.SECURITY_POLICY,),
    )
    assert out.axis_holds[ConstraintAxis.SECURITY_POLICY] is True


def test_rule_supplied_forbid_substring_violates_c3() -> None:
    rule = ConstraintRule(
        rule_id="custom-1",
        axis=ConstraintAxis.SECURITY_POLICY,
        name="no_legacy_helper",
        description="Forbid the legacy_helper() shim that's been retired.",
        positive_centroid=(0.0,) * 8,
        negative_centroid=(0.0,) * 8,
        boundary_threshold=0.5,
        metadata=(("forbid_substring", "legacy_helper("),),
    )
    src = "def f():\n    return legacy_helper(1)\n"
    out = ConstraintTranslator().translate(
        source_code=src,
        axes_in_scope=(ConstraintAxis.SECURITY_POLICY,),
        rules=(rule,),
    )
    assert out.axis_holds[ConstraintAxis.SECURITY_POLICY] is False
    assert any("rule:custom-1" in n for n in out.notes)


# --------------------------------------------------------------------- C4


def test_c4_with_no_bounds_passes() -> None:
    out = ConstraintTranslator().translate(
        source_code=_annotated_clean_source(),
        axes_in_scope=(ConstraintAxis.OPERATIONAL_BOUNDS,),
    )
    assert out.axis_holds[ConstraintAxis.OPERATIONAL_BOUNDS] is True
    assert "no C4 bounds supplied" in out.smt_assertions


def test_c4_explicit_bounds_emit_declarations() -> None:
    ctx = TranslationContext(
        c4_bounds={"max_resource_allocation": 1024, "timeout_ms": 30000}
    )
    out = ConstraintTranslator().translate(
        source_code=_annotated_clean_source(),
        axes_in_scope=(ConstraintAxis.OPERATIONAL_BOUNDS,),
        context=ctx,
    )
    assert "(declare-const max_resource_allocation Int)" in out.smt_assertions
    assert "(assert (<= max_resource_allocation 1024))" in out.smt_assertions
    assert "(declare-const timeout_ms Int)" in out.smt_assertions


def test_c4_rule_metadata_supplies_bounds() -> None:
    rule = ConstraintRule(
        rule_id="ops-1",
        axis=ConstraintAxis.OPERATIONAL_BOUNDS,
        name="cpu_cap",
        description="Cap CPU.",
        positive_centroid=(0.0,) * 8,
        negative_centroid=(0.0,) * 8,
        boundary_threshold=0.5,
        metadata=(("upper_bound_cpu_units", 4096),),
    )
    out = ConstraintTranslator().translate(
        source_code=_annotated_clean_source(),
        axes_in_scope=(ConstraintAxis.OPERATIONAL_BOUNDS,),
        rules=(rule,),
    )
    assert "(declare-const cpu_units Int)" in out.smt_assertions
    assert "(assert (<= cpu_units 4096))" in out.smt_assertions


# --------------------------------------------------------------- composite


def test_unsupported_axis_dropped_with_warning() -> None:
    """C5/C6/C7 are deferred to CGE; translator drops them silently."""
    out = ConstraintTranslator().translate(
        source_code=_annotated_clean_source(),
        axes_in_scope=(
            ConstraintAxis.SYNTACTIC_VALIDITY,
            ConstraintAxis.DOMAIN_COMPLIANCE,
        ),
    )
    assert ConstraintAxis.DOMAIN_COMPLIANCE not in out.axes_in_scope
    assert ConstraintAxis.SYNTACTIC_VALIDITY in out.axes_in_scope


def test_full_translation_emits_check_sat() -> None:
    out = ConstraintTranslator().translate(source_code=_annotated_clean_source())
    assert "(check-sat)" in out.smt_assertions
    assert out.smt_assertions.startswith("(set-logic QF_LIA)")


def test_build_request_helper_returns_consistent_request() -> None:
    request = build_request(source_code=_annotated_clean_source())
    assert request.smt_assertions.startswith("(set-logic QF_LIA)")
    assert request.axes_in_scope == ConstraintTranslator.SUPPORTED_AXES
    assert request.timeout_seconds == 30.0
