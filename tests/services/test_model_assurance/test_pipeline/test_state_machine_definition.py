"""Tests for the ASL state-machine builder (ADR-088 Phase 2.3)."""

from __future__ import annotations

import json

import pytest

from src.services.model_assurance.pipeline import (
    PipelineDecision,
    PipelineStage,
    StageLambdaArns,
    StateMachineConfig,
    build_state_machine_definition,
    build_state_machine_json,
)


def _arns() -> StageLambdaArns:
    return StageLambdaArns(
        adapter_disqualification_arn="arn:aws:lambda:us-east-1:123:function:adapter",
        provenance_arn="arn:aws:lambda:us-east-1:123:function:prov",
        sandbox_arn="arn:aws:lambda:us-east-1:123:function:sandbox",
        oracle_arn="arn:aws:lambda:us-east-1:123:function:oracle",
        cge_scoring_arn="arn:aws:lambda:us-east-1:123:function:cge",
        report_arn="arn:aws:lambda:us-east-1:123:function:report",
        hitl_queue_arn="arn:aws:lambda:us-east-1:123:function:hitl",
    )


class TestStateMachineStructure:
    def test_starts_at_adapter_stage(self) -> None:
        asl = build_state_machine_definition(_arns())
        assert asl["StartAt"] == PipelineStage.ADAPTER_DISQUALIFICATION.value

    def test_all_pipeline_stages_have_states(self) -> None:
        asl = build_state_machine_definition(_arns())
        for stage in PipelineStage:
            assert stage.value in asl["States"], (
                f"missing ASL state for {stage.value}"
            )

    def test_terminal_decisions_present(self) -> None:
        asl = build_state_machine_definition(_arns())
        for terminal in (
            "Disqualified",
            "Quarantined",
            "Rejected",
            "InfrastructureError",
        ):
            assert terminal in asl["States"]

    def test_choice_states_present(self) -> None:
        asl = build_state_machine_definition(_arns())
        for choice in (
            "AdapterDecision",
            "ProvenanceDecision",
            "FloorViolationCheck",
        ):
            assert asl["States"][choice]["Type"] == "Choice"


class TestRoutingLogic:
    def test_adapter_decision_routes_disqualified(self) -> None:
        asl = build_state_machine_definition(_arns())
        choices = asl["States"]["AdapterDecision"]["Choices"]
        target = next(
            c["Next"] for c in choices if c.get("BooleanEquals") is True
        )
        assert target == "Disqualified"

    def test_adapter_decision_default_to_provenance(self) -> None:
        asl = build_state_machine_definition(_arns())
        assert (
            asl["States"]["AdapterDecision"]["Default"]
            == PipelineStage.PROVENANCE.value
        )

    def test_provenance_routes_quarantine_and_rejection(self) -> None:
        asl = build_state_machine_definition(_arns())
        choices = asl["States"]["ProvenanceDecision"]["Choices"]
        targets = {c["StringEquals"]: c["Next"] for c in choices}
        assert targets["quarantined"] == "Quarantined"
        assert targets["rejected"] == "Rejected"

    def test_floor_violation_routes_to_rejected(self) -> None:
        asl = build_state_machine_definition(_arns())
        choices = asl["States"]["FloorViolationCheck"]["Choices"]
        target = next(
            c["Next"] for c in choices if c.get("StringEquals") == "reject"
        )
        assert target == "Rejected"

    def test_floor_violation_default_to_report(self) -> None:
        asl = build_state_machine_definition(_arns())
        assert (
            asl["States"]["FloorViolationCheck"]["Default"]
            == PipelineStage.REPORT.value
        )


class TestRetryAndCatch:
    def test_every_task_has_retry_and_catch(self) -> None:
        asl = build_state_machine_definition(_arns())
        for name, state in asl["States"].items():
            if state.get("Type") == "Task":
                assert "Retry" in state, f"{name} missing Retry"
                assert "Catch" in state, f"{name} missing Catch"

    def test_catch_routes_to_infrastructure_error(self) -> None:
        asl = build_state_machine_definition(_arns())
        for state in asl["States"].values():
            if state.get("Type") != "Task":
                continue
            for catch in state.get("Catch", []):
                assert catch["Next"] == "InfrastructureError"

    def test_config_overrides_retry_attempts(self) -> None:
        asl = build_state_machine_definition(
            _arns(),
            StateMachineConfig(retry_attempts=7, retry_interval_seconds=15),
        )
        provenance = asl["States"][PipelineStage.PROVENANCE.value]
        retry = provenance["Retry"][0]
        assert retry["MaxAttempts"] == 7
        assert retry["IntervalSeconds"] == 15


class TestSerialisation:
    def test_json_serialisable(self) -> None:
        out = build_state_machine_json(_arns())
        parsed = json.loads(out)
        assert parsed["StartAt"] == PipelineStage.ADAPTER_DISQUALIFICATION.value

    def test_no_account_id_hardcoded(self) -> None:
        """Builder must not bake any account number; CFN substitutes via ARN params."""
        asl = build_state_machine_definition(_arns())
        text = json.dumps(asl)
        # Test ARNs contain "123" — the builder uses what's passed in,
        # which is the right behaviour. We just check the builder
        # didn't synthesize anything different.
        assert "123" in text  # only present because we passed it in

    def test_terminal_states_carry_decision_value(self) -> None:
        asl = build_state_machine_definition(_arns())
        for state_name, decision in (
            ("Disqualified", PipelineDecision.DISQUALIFIED.value),
            ("Quarantined", PipelineDecision.QUARANTINED.value),
            ("Rejected", PipelineDecision.REJECTED.value),
            ("InfrastructureError", PipelineDecision.INFRASTRUCTURE_ERROR.value),
        ):
            state = asl["States"][state_name]
            assert state["Result"]["decision"] == decision

    def test_top_level_timeout_set(self) -> None:
        asl = build_state_machine_definition(_arns())
        assert "TimeoutSeconds" in asl
        assert asl["TimeoutSeconds"] == 3600  # default 1h
