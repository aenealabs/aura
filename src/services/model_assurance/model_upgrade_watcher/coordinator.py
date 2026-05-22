"""Re-validation coordinator (issue #212).

Glue that orchestrates the watcher + flag + Frozen Reference Oracle
+ HITL gateway + CloudWatch metric. The composition root for the
issue #212 work.

Lifecycle per bump:

  1. Set the SSM-backed feature flag for the tier (blocks DAL A/B
     auto-promotion immediately).
  2. Trigger the Frozen Reference Oracle to re-run its reference
     cases against the new model.
  3. If pass-rate >= ``pass_rate_threshold``: clear the flag.
     If not: open a HITL incident. Either way: emit a CloudWatch
     metric data point.

The coordinator is intentionally synchronous; production wraps it
in a Lambda invocation and the EventBridge schedule drives the
cadence. A single Lambda invocation processes whatever bumps the
watcher detected on this tick (usually zero, occasionally one).
"""

from __future__ import annotations

import logging
from typing import Sequence

from src.services.model_assurance.model_upgrade_watcher.contracts import (
    ModelUpgradeEvent,
    RevalidationOutcome,
    RevalidationStatus,
)
from src.services.model_assurance.model_upgrade_watcher.ports import (
    HitlIncidentPort,
    MetricEmitterPort,
    OracleRerunPort,
    RevalidationFlagPort,
)

logger = logging.getLogger(__name__)


class RevalidationCoordinator:
    """Drive the bump -> re-validate -> clear/escalate lifecycle."""

    def __init__(
        self,
        *,
        flag: RevalidationFlagPort,
        oracle: OracleRerunPort,
        incident: HitlIncidentPort,
        metric: MetricEmitterPort,
        pass_rate_threshold: float = 0.95,
    ) -> None:
        if not 0.0 < pass_rate_threshold <= 1.0:
            raise ValueError("pass_rate_threshold must be in (0, 1]")
        self._flag = flag
        self._oracle = oracle
        self._incident = incident
        self._metric = metric
        self._threshold = pass_rate_threshold

    def process(
        self,
        events: Sequence[ModelUpgradeEvent],
    ) -> tuple[RevalidationOutcome, ...]:
        """Process events from one watcher tick; return per-event outcomes."""
        outcomes: list[RevalidationOutcome] = []
        for event in events:
            if not event.is_bump:
                outcomes.append(
                    RevalidationOutcome(
                        status=RevalidationStatus.SKIPPED,
                        tier=event.tier,
                        model_identity=event.current.identity,
                        rationale="no model version change detected",
                    )
                )
                continue
            outcomes.append(self._handle_bump(event))
        return tuple(outcomes)

    def _handle_bump(self, event: ModelUpgradeEvent) -> RevalidationOutcome:
        tier = event.tier
        new_identity = event.current.identity
        reason = (
            f"Bedrock model bumped for tier {tier!r}: "
            f"{event.previous.identity!r} -> {new_identity!r}. "
            f"DAL A/B auto-promotion is blocked pending re-validation."
        )
        logger.warning(reason)
        self._flag.set(tier=tier, reason=reason)
        flag_set = True

        try:
            passed, total = self._oracle.rerun_reference_cases(
                tier=tier, model_identity=new_identity
            )
        except Exception as exc:  # pragma: no cover -- oracle is best-effort
            logger.exception(
                "Oracle rerun raised; treating as FAILED for tier %s", tier
            )
            ticket = self._incident.open_incident(
                tier=tier,
                model_identity=new_identity,
                cases_passed=0,
                cases_total=0,
                rationale=f"Oracle rerun raised: {exc}",
            )
            self._metric.emit(
                tier=tier,
                model_identity=new_identity,
                status=RevalidationStatus.FAILED.value,
                cases_passed=0,
                cases_total=0,
            )
            return RevalidationOutcome(
                status=RevalidationStatus.FAILED,
                tier=tier,
                model_identity=new_identity,
                cases_total=0,
                cases_passed=0,
                rationale=f"oracle raised: {exc}",
                incident_ticket_id=ticket,
                flag_set=flag_set,
                metric_emitted=True,
            )

        pass_rate = (passed / total) if total > 0 else 0.0
        if pass_rate >= self._threshold:
            self._flag.clear(tier=tier)
            self._metric.emit(
                tier=tier,
                model_identity=new_identity,
                status=RevalidationStatus.PASSED.value,
                cases_passed=passed,
                cases_total=total,
            )
            logger.info(
                "Re-validation PASSED for tier %s: %d/%d cases (threshold %.2f)",
                tier,
                passed,
                total,
                self._threshold,
            )
            return RevalidationOutcome(
                status=RevalidationStatus.PASSED,
                tier=tier,
                model_identity=new_identity,
                cases_total=total,
                cases_passed=passed,
                rationale=(
                    f"pass_rate={pass_rate:.3f} >= threshold={self._threshold:.2f}"
                ),
                flag_set=flag_set,
                flag_cleared=True,
                metric_emitted=True,
            )

        # Below threshold: keep the flag set, open a HITL incident.
        ticket = self._incident.open_incident(
            tier=tier,
            model_identity=new_identity,
            cases_passed=passed,
            cases_total=total,
            rationale=(
                f"pass_rate={pass_rate:.3f} below threshold={self._threshold:.2f}"
            ),
        )
        self._metric.emit(
            tier=tier,
            model_identity=new_identity,
            status=RevalidationStatus.FAILED.value,
            cases_passed=passed,
            cases_total=total,
        )
        logger.warning(
            "Re-validation FAILED for tier %s: %d/%d cases below threshold; "
            "incident=%s",
            tier,
            passed,
            total,
            ticket,
        )
        return RevalidationOutcome(
            status=RevalidationStatus.FAILED,
            tier=tier,
            model_identity=new_identity,
            cases_total=total,
            cases_passed=passed,
            rationale=(f"pass_rate={pass_rate:.3f} < threshold={self._threshold:.2f}"),
            incident_ticket_id=ticket,
            flag_set=flag_set,
            metric_emitted=True,
        )
