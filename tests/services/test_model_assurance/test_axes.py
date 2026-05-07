"""Tests for the 6-axis model_assurance domain (ADR-088 Phase 1.3)."""

from __future__ import annotations

import pytest

from src.services.constraint_geometry.contracts import (
    RegressionFloorAction,
    RegressionFloorComparisonMode,
)
from src.services.model_assurance.axes import (
    AXIS_DEFINITIONS,
    AXIS_DEFINITIONS_BY_AXIS,
    AxisDefinition,
    ModelAssuranceAxis,
    default_floors,
    default_weights,
)


class TestAxisEnum:
    def test_six_axes(self) -> None:
        assert len(list(ModelAssuranceAxis)) == 6

    def test_axis_values_have_ma_prefix(self) -> None:
        for axis in ModelAssuranceAxis:
            assert axis.value.startswith("MA"), (
                f"{axis.name}={axis.value} should be prefixed to disambiguate "
                f"from CGE ConstraintAxis values like 'C3'"
            )

    def test_display_name_present(self) -> None:
        for axis in ModelAssuranceAxis:
            assert axis.display_name
            assert axis.display_name != axis.value

    def test_axis_values_match_adr_naming(self) -> None:
        # Spot-check the ADR-aligned identifiers to catch silent renames
        assert (
            ModelAssuranceAxis.VULNERABILITY_DETECTION_RECALL.value
            == "MA2_vulnerability_detection_recall"
        )
        assert (
            ModelAssuranceAxis.PATCH_SECURITY_EQUIVALENCE.value
            == "MA4_patch_security_equivalence"
        )
        assert (
            ModelAssuranceAxis.LATENCY_TOKEN_EFFICIENCY.value
            == "MA5_latency_token_efficiency"
        )


class TestAxisDefinitions:
    def test_six_definitions(self) -> None:
        assert len(AXIS_DEFINITIONS) == 6

    def test_one_definition_per_axis(self) -> None:
        axes_seen = {d.axis for d in AXIS_DEFINITIONS}
        assert axes_seen == set(ModelAssuranceAxis)

    def test_lookup_by_axis(self) -> None:
        for d in AXIS_DEFINITIONS:
            assert AXIS_DEFINITIONS_BY_AXIS[d.axis] is d

    @pytest.mark.parametrize(
        "axis,expected_floor",
        [
            (ModelAssuranceAxis.CODE_COMPREHENSION, 0.85),
            (ModelAssuranceAxis.VULNERABILITY_DETECTION_RECALL, 0.92),
            (ModelAssuranceAxis.PATCH_FUNCTIONAL_CORRECTNESS, 0.88),
            (ModelAssuranceAxis.PATCH_SECURITY_EQUIVALENCE, 0.95),
            (ModelAssuranceAxis.LATENCY_TOKEN_EFFICIENCY, 0.70),
            (ModelAssuranceAxis.GUARDRAIL_COMPLIANCE, 0.98),
        ],
    )
    def test_default_floors_match_adr(
        self, axis: ModelAssuranceAxis, expected_floor: float
    ) -> None:
        d = AXIS_DEFINITIONS_BY_AXIS[axis]
        assert d.default_floor == expected_floor

    def test_latency_floor_is_relative(self) -> None:
        d = AXIS_DEFINITIONS_BY_AXIS[ModelAssuranceAxis.LATENCY_TOKEN_EFFICIENCY]
        assert d.floor_comparison is RegressionFloorComparisonMode.RELATIVE_TO_INCUMBENT

    def test_other_floors_are_absolute(self) -> None:
        for d in AXIS_DEFINITIONS:
            if d.axis is ModelAssuranceAxis.LATENCY_TOKEN_EFFICIENCY:
                continue
            assert d.floor_comparison is RegressionFloorComparisonMode.ABSOLUTE


class TestDefaultBuilders:
    def test_default_floors_returns_six_floors(self) -> None:
        floors = default_floors()
        assert len(floors) == 6
        assert {f.axis for f in floors} == {a.value for a in ModelAssuranceAxis}

    def test_default_floors_use_string_axis_id(self) -> None:
        for f in default_floors():
            assert isinstance(f.axis, str)
            assert f.axis.startswith("MA")

    def test_default_floors_action_is_reject(self) -> None:
        for f in default_floors():
            assert f.action is RegressionFloorAction.REJECT

    def test_default_floor_ids_are_unique(self) -> None:
        ids = [f.floor_id for f in default_floors()]
        assert len(ids) == len(set(ids))

    def test_default_weights_returns_six_axes(self) -> None:
        w = default_weights()
        assert set(w.keys()) == set(ModelAssuranceAxis)

    def test_security_axes_weighted_higher_than_efficiency(self) -> None:
        """Sanity check: security weights > efficiency weight."""
        w = default_weights()
        sec_weights = [
            w[ModelAssuranceAxis.VULNERABILITY_DETECTION_RECALL],
            w[ModelAssuranceAxis.PATCH_SECURITY_EQUIVALENCE],
            w[ModelAssuranceAxis.GUARDRAIL_COMPLIANCE],
        ]
        eff_weight = w[ModelAssuranceAxis.LATENCY_TOKEN_EFFICIENCY]
        for sec in sec_weights:
            assert sec > eff_weight


class TestAxisDefinitionToFloor:
    def test_to_floor_creates_unique_id(self) -> None:
        floors = [d.to_floor() for d in AXIS_DEFINITIONS]
        assert len({f.floor_id for f in floors}) == 6

    def test_floor_threshold_matches_definition(self) -> None:
        for d in AXIS_DEFINITIONS:
            f = d.to_floor()
            assert f.threshold == d.default_floor

    def test_floor_axis_is_axis_value_string(self) -> None:
        for d in AXIS_DEFINITIONS:
            f = d.to_floor()
            assert f.axis == d.axis.value
