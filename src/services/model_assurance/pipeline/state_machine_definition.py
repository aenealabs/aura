"""ASL (Amazon States Language) builder for the assurance state machine.

This module mirrors the control flow of :class:`PipelineOrchestrator`
in Step Functions ASL JSON. The CloudFormation template at
``deploy/cloudformation/model-assurance-pipeline.yaml`` references
the JSON this builder produces.

Keeping the ASL generated from a single Python builder rather than
hand-edited JSON gives us:

  * One source of truth for state names + transitions.
  * Tests can verify the ASL structure without invoking the SF runtime.
  * Renaming a stage in ``PipelineStage`` enum updates ASL automatically.

The Lambda ARNs are passed in by the caller (CloudFormation
substitutes them in the generated template); this module never
hard-codes account IDs or partition prefixes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from src.services.model_assurance.pipeline.contracts import (
    PipelineDecision,
    PipelineStage,
)


@dataclass(frozen=True)
class StageLambdaArns:
    """Lambda ARNs for each stage. Caller supplies via CFN params."""

    adapter_disqualification_arn: str
    provenance_arn: str
    sandbox_arn: str
    oracle_arn: str
    cge_scoring_arn: str
    report_arn: str
    hitl_queue_arn: str


@dataclass(frozen=True)
class StateMachineConfig:
    """Tunables for the generated ASL."""

    timeout_seconds: int = 3_600           # 1 hour per pipeline run
    retry_attempts: int = 2                # per Lambda invocation
    retry_interval_seconds: int = 5
    retry_backoff: float = 2.0


def build_state_machine_definition(
    arns: StageLambdaArns,
    config: StateMachineConfig | None = None,
) -> dict:
    """Build the ASL JSON dict.

    The state machine has one Choice state after CGE scoring that
    routes to the HITL queue or auto-reject based on the assurance
    verdict — mirroring ``PipelineOrchestrator._stage_cge_scoring``.
    """
    cfg = config or StateMachineConfig()
    common_retry = [
        {
            "ErrorEquals": ["States.TaskFailed"],
            "IntervalSeconds": cfg.retry_interval_seconds,
            "MaxAttempts": cfg.retry_attempts,
            "BackoffRate": cfg.retry_backoff,
        }
    ]
    common_catch = [
        {
            "ErrorEquals": ["States.ALL"],
            "Next": "InfrastructureError",
            "ResultPath": "$.error",
        }
    ]

    def _task(name: str, arn: str, next_state: str) -> dict:
        return {
            "Type": "Task",
            "Resource": "arn:aws:states:::lambda:invoke",
            "Parameters": {
                "FunctionName": arn,
                "Payload.$": "$",
            },
            "ResultPath": f"$.{name}",
            "Retry": common_retry,
            "Catch": common_catch,
            "Next": next_state,
        }

    states: dict[str, dict] = {}

    # 1. Adapter disqualification
    states[PipelineStage.ADAPTER_DISQUALIFICATION.value] = _task(
        PipelineStage.ADAPTER_DISQUALIFICATION.value,
        arns.adapter_disqualification_arn,
        "AdapterDecision",
    )
    states["AdapterDecision"] = {
        "Type": "Choice",
        "Choices": [
            {
                "Variable": (
                    f"$.{PipelineStage.ADAPTER_DISQUALIFICATION.value}"
                    ".Payload.disqualified"
                ),
                "BooleanEquals": True,
                "Next": "Disqualified",
            }
        ],
        "Default": PipelineStage.PROVENANCE.value,
    }

    # 2. Provenance
    states[PipelineStage.PROVENANCE.value] = _task(
        PipelineStage.PROVENANCE.value,
        arns.provenance_arn,
        "ProvenanceDecision",
    )
    states["ProvenanceDecision"] = {
        "Type": "Choice",
        "Choices": [
            {
                "Variable": (
                    f"$.{PipelineStage.PROVENANCE.value}.Payload.verdict"
                ),
                "StringEquals": "quarantined",
                "Next": "Quarantined",
            },
            {
                "Variable": (
                    f"$.{PipelineStage.PROVENANCE.value}.Payload.verdict"
                ),
                "StringEquals": "rejected",
                "Next": "Rejected",
            },
        ],
        "Default": PipelineStage.SANDBOX.value,
    }

    # 3. Sandbox provisioning
    states[PipelineStage.SANDBOX.value] = _task(
        PipelineStage.SANDBOX.value,
        arns.sandbox_arn,
        PipelineStage.ORACLE.value,
    )

    # 4. Oracle
    states[PipelineStage.ORACLE.value] = _task(
        PipelineStage.ORACLE.value,
        arns.oracle_arn,
        PipelineStage.CGE_SCORING.value,
    )

    # 5. CGE scoring
    states[PipelineStage.CGE_SCORING.value] = _task(
        PipelineStage.CGE_SCORING.value,
        arns.cge_scoring_arn,
        "FloorViolationCheck",
    )
    states["FloorViolationCheck"] = {
        "Type": "Choice",
        "Choices": [
            {
                "Variable": (
                    f"$.{PipelineStage.CGE_SCORING.value}.Payload.verdict"
                ),
                "StringEquals": "reject",
                "Next": "Rejected",
            }
        ],
        "Default": PipelineStage.REPORT.value,
    }

    # 6. Report generation
    states[PipelineStage.REPORT.value] = _task(
        PipelineStage.REPORT.value,
        arns.report_arn,
        PipelineStage.HITL_QUEUED.value,
    )

    # 7. HITL queue
    states[PipelineStage.HITL_QUEUED.value] = {
        "Type": "Task",
        "Resource": "arn:aws:states:::lambda:invoke",
        "Parameters": {
            "FunctionName": arns.hitl_queue_arn,
            "Payload.$": "$",
        },
        "ResultPath": f"$.{PipelineStage.HITL_QUEUED.value}",
        "Retry": common_retry,
        "Catch": common_catch,
        "End": True,
    }

    # Terminal states for non-HITL exits
    states["Disqualified"] = {
        "Type": "Pass",
        "Result": {"decision": PipelineDecision.DISQUALIFIED.value},
        "ResultPath": "$.decision",
        "End": True,
    }
    states["Quarantined"] = {
        "Type": "Pass",
        "Result": {"decision": PipelineDecision.QUARANTINED.value},
        "ResultPath": "$.decision",
        "End": True,
    }
    states["Rejected"] = {
        "Type": "Pass",
        "Result": {"decision": PipelineDecision.REJECTED.value},
        "ResultPath": "$.decision",
        "End": True,
    }
    states["InfrastructureError"] = {
        "Type": "Pass",
        "Result": {"decision": PipelineDecision.INFRASTRUCTURE_ERROR.value},
        "ResultPath": "$.decision",
        "End": True,
    }

    return {
        "Comment": "ADR-088 Continuous Model Assurance pipeline",
        "StartAt": PipelineStage.ADAPTER_DISQUALIFICATION.value,
        "TimeoutSeconds": cfg.timeout_seconds,
        "States": states,
    }


def build_state_machine_json(
    arns: StageLambdaArns,
    config: StateMachineConfig | None = None,
) -> str:
    """Convenience: serialise the ASL dict to JSON for CFN."""
    return json.dumps(build_state_machine_definition(arns, config), indent=2)
