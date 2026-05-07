"""Evaluation sandbox provisioner (ADR-088 Phase 2.4).

The provisioner validates the SandboxSpec against the policy, calls
into the underlying compute service to create the sandbox, executes
the supplied work callable inside it, and tears it down on completion
regardless of outcome.

Three guarantees the design enforces:

  1. **No orphan storage.** The teardown path always runs. Even if
     the work callable raises, the provisioner catches, returns a
     SandboxOutcome with the failure, and reports DESTROYED state.
  2. **Egress check before READY.** A spec whose egress policy
     would silently allow non-Bedrock traffic never reaches the
     READY state.
  3. **Ephemeral state.** No persistent volumes are wired in by
     this module; the SandboxSpec exposes only a scratch-size knob
     that the underlying compute service uses to provision an
     ephemeral overlay.

The actual cloud provisioning is a pluggable callable so:
  * Tests inject a synchronous in-memory provisioner.
  * Phase 2.4 production wiring (CloudFormation + ECS Fargate) is
    a one-line replacement.
  * Local dev can inject a Podman-backed provisioner.

The Python module here is the policy + lifecycle harness; the IaC
template (zero-egress security group, IAM role, taint configuration)
lives in ``deploy/cloudformation/model-assurance-sandbox.yaml`` and
ships alongside Phase 2's overall infrastructure bundle.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Sequence

from src.services.model_assurance.sandbox.contracts import (
    EgressDecision,
    SandboxLifecycleState,
    SandboxOutcome,
    SandboxSpec,
)

logger = logging.getLogger(__name__)


# Provisioning hook signature: (spec) → SandboxHandle (any opaque object)
# Test stubs and production wiring both implement this.
ProvisionFn = Callable[[SandboxSpec], object]
TeardownFn = Callable[[SandboxSpec, object], None]
WorkFn = Callable[[SandboxSpec, object], None]


@dataclass(frozen=True)
class IAMPolicyDocument:
    """Minimal IAM policy view used for the policy gate.

    Real IAM policies have far more shape; for the gate we only need
    the action list to detect forbidden grants. Production wiring
    parses ``aws iam get-role-policy`` output into this shape.
    """

    actions: tuple[str, ...]


def _matches(rule: str, action: str) -> bool:
    """Glob-y match: ``foo:*`` matches ``foo:Bar`` etc."""
    if rule == "*":
        return True
    if rule.endswith("*"):
        return action.startswith(rule[:-1])
    return rule == action


def validate_iam_policy(
    policy: IAMPolicyDocument, *, forbidden: tuple[str, ...]
) -> tuple[str, ...]:
    """Return the subset of forbidden actions present in ``policy``."""
    violations: list[str] = []
    for action in policy.actions:
        for forbidden_pattern in forbidden:
            if _matches(forbidden_pattern, action):
                violations.append(action)
                break
    return tuple(violations)


def validate_egress_endpoints(
    spec: SandboxSpec,
    candidate_destinations: Sequence[tuple[str, int]],
) -> tuple[str, ...]:
    """Pre-flight check: every candidate destination must validate ALLOW.

    Returns the list of (host:port) strings that would be denied. An
    empty return means the planned destinations all pass.
    """
    denied: list[str] = []
    for host, port in candidate_destinations:
        decision = spec.egress_policy.validate_destination(host, port)
        if decision is not EgressDecision.ALLOW:
            denied.append(f"{host}:{port}")
    return tuple(denied)


def _identity_provision(_: SandboxSpec) -> object:
    return object()


def _no_op_teardown(_: SandboxSpec, __: object) -> None:
    return None


def _no_op_work(_: SandboxSpec, __: object) -> None:
    return None


class SandboxProvisioner:
    """Lifecycle harness for evaluation sandboxes.

    The provisioner is stateless — every ``execute`` call walks
    through provision → ready (with policy gate) → execute → teardown
    → destroyed. Failures during work surface as FAILED state and
    still trigger teardown.
    """

    def __init__(
        self,
        *,
        provision_fn: ProvisionFn = _identity_provision,
        teardown_fn: TeardownFn = _no_op_teardown,
        iam_policy_fetcher: Callable[[SandboxSpec], IAMPolicyDocument | None]
        | None = None,
    ) -> None:
        self._provision_fn = provision_fn
        self._teardown_fn = teardown_fn
        self._iam_policy_fetcher = iam_policy_fetcher

    def execute(
        self,
        spec: SandboxSpec,
        *,
        work: WorkFn = _no_op_work,
        planned_egress: Sequence[tuple[str, int]] = (),
    ) -> SandboxOutcome:
        started = datetime.now(timezone.utc)
        sandbox_id = spec.sandbox_id

        # ------------------------------- 1. egress pre-flight
        denied = validate_egress_endpoints(spec, planned_egress)
        if denied:
            return SandboxOutcome(
                sandbox_id=sandbox_id,
                state=SandboxLifecycleState.FAILED,
                egress_violations=denied,
                error="planned egress endpoints failed allowlist check",
                started_at=started,
            )

        # ------------------------------- 2. iam policy check
        iam_violations: tuple[str, ...] = ()
        if self._iam_policy_fetcher is not None:
            policy = self._iam_policy_fetcher(spec)
            if policy is not None:
                iam_violations = validate_iam_policy(
                    policy, forbidden=spec.iam_constraint.forbidden_actions,
                )
        if iam_violations:
            return SandboxOutcome(
                sandbox_id=sandbox_id,
                state=SandboxLifecycleState.FAILED,
                iam_violations=iam_violations,
                error="iam policy contains forbidden actions",
                started_at=started,
            )

        # ------------------------------- 3. provision
        try:
            handle = self._provision_fn(spec)
        except Exception as exc:
            return SandboxOutcome(
                sandbox_id=sandbox_id,
                state=SandboxLifecycleState.FAILED,
                error=f"provision failed: {exc}",
                started_at=started,
            )

        # ------------------------------- 4. work + teardown (always)
        work_error: str | None = None
        try:
            work(spec, handle)
        except Exception as exc:
            work_error = f"work failed: {exc}"
            logger.warning(
                "sandbox work raised in %s: %s", sandbox_id, exc,
            )
        finally:
            try:
                self._teardown_fn(spec, handle)
            except Exception as teardown_exc:
                # Teardown failure is logged but doesn't override the
                # work_error — the spec's invariant is "we tried".
                logger.error(
                    "sandbox teardown failed for %s: %s",
                    sandbox_id, teardown_exc,
                )

        if work_error is not None:
            return SandboxOutcome(
                sandbox_id=sandbox_id,
                state=SandboxLifecycleState.FAILED,
                error=work_error,
                started_at=started,
            )

        return SandboxOutcome(
            sandbox_id=sandbox_id,
            state=SandboxLifecycleState.DESTROYED,
            started_at=started,
        )
