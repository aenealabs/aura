"""Ports for the model-upgrade watcher (issue #212).

Each integration boundary is a narrow Protocol so production wires
boto3-backed implementations and tests use simple fakes. Production
implementations of these ports live in
``model_assurance/govcloud/`` and ``model_assurance/audit/`` (existing
modules); the wiring is a follow-up PR once #212 is merged.
"""

from __future__ import annotations

from typing import Protocol

from src.services.model_assurance.model_upgrade_watcher.contracts import (
    BedrockModelVersion,
)


class BedrockModelRegistryPort(Protocol):
    """Reports the currently-configured Bedrock model version per tier."""

    def current_versions(self) -> tuple[BedrockModelVersion, ...]:
        """Return one entry per configured tier."""


class RevalidationFlagPort(Protocol):
    """SSM-backed feature flag that gates DAL A/B auto-promotion."""

    def is_set(self, *, tier: str) -> bool:
        """Return True iff DAL A/B auto-promotion is currently blocked."""

    def set(self, *, tier: str, reason: str) -> None:
        """Block DAL A/B auto-promotion for ``tier`` with a stored reason."""

    def clear(self, *, tier: str) -> None:
        """Unblock DAL A/B auto-promotion for ``tier``."""


class OracleRerunPort(Protocol):
    """Runs the Frozen Reference Oracle's reference cases.

    Returns ``(cases_passed, cases_total)``. The caller decides what
    threshold counts as "passed" -- the Port stays mechanism-free.
    """

    def rerun_reference_cases(
        self, *, tier: str, model_identity: str
    ) -> tuple[int, int]:
        """Return ``(cases_passed, cases_total)``."""


class HitlIncidentPort(Protocol):
    """Opens a HITL incident on the existing approval gateway."""

    def open_incident(
        self,
        *,
        tier: str,
        model_identity: str,
        cases_passed: int,
        cases_total: int,
        rationale: str,
    ) -> str:
        """Open an incident; return the ticket id."""


class MetricEmitterPort(Protocol):
    """Emits the ``Aura/ModelAssurance/ConsensusReValidationStatus`` metric."""

    def emit(
        self,
        *,
        tier: str,
        model_identity: str,
        status: str,
        cases_passed: int,
        cases_total: int,
    ) -> None:
        """Emit one metric data point."""
