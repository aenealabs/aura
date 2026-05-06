"""Protocol-conformance tests for FormalVerificationAdapter."""

from __future__ import annotations

from src.services.verification_envelope.formal import (
    FormalVerificationAdapter,
    Z3SMTAdapter,
)


def test_z3_satisfies_protocol() -> None:
    assert isinstance(Z3SMTAdapter(), FormalVerificationAdapter)


def test_z3_exposes_stable_tool_name() -> None:
    assert Z3SMTAdapter().tool_name == "z3_smt"


def test_z3_advertises_axes_c1_through_c4() -> None:
    from src.services.constraint_geometry.contracts import ConstraintAxis

    advertised = Z3SMTAdapter().supported_axes
    assert ConstraintAxis.SYNTACTIC_VALIDITY in advertised
    assert ConstraintAxis.SEMANTIC_CORRECTNESS in advertised
    assert ConstraintAxis.SECURITY_POLICY in advertised
    assert ConstraintAxis.OPERATIONAL_BOUNDS in advertised
    # C5/C6/C7 are explicitly out-of-scope per ADR-085.
    assert ConstraintAxis.DOMAIN_COMPLIANCE not in advertised
    assert ConstraintAxis.PROVENANCE_TRUST not in advertised
    assert ConstraintAxis.TEMPORAL_VALIDITY not in advertised


def test_is_available_is_synchronous() -> None:
    """Availability check must not require an event loop."""
    assert isinstance(Z3SMTAdapter().is_available, bool)
