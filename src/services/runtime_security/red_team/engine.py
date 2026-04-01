"""
Project Aura - Red Team Engine

Orchestrates automated adversarial testing against live agent
deployments using the AURA-ATT&CK taxonomy.

Based on ADR-083: Runtime Agent Security Platform

Compliance:
- NIST 800-53 CA-8: Penetration testing
- NIST 800-53 RA-5: Vulnerability scanning
"""

import logging
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from .taxonomy import (
    AURA_ATTACK_TAXONOMY,
    AttackCategory,
    AttackTechnique,
    get_technique_by_id,
    get_techniques_by_category,
)

logger = logging.getLogger(__name__)


class TestOutcome(Enum):
    """Outcome of a red team test."""

    BLOCKED = "blocked"  # Attack was successfully blocked
    DETECTED = "detected"  # Attack was detected but not blocked
    PARTIAL = "partial"  # Attack partially succeeded
    SUCCEEDED = "succeeded"  # Attack fully succeeded (vulnerability found)
    ERROR = "error"  # Test execution failed
    SKIPPED = "skipped"  # Test was skipped (not applicable)


@dataclass(frozen=True)
class RedTeamResult:
    """Immutable result of a single red team test."""

    result_id: str
    technique: AttackTechnique
    outcome: TestOutcome
    timestamp: datetime
    target_agent_id: str
    payload_used: str
    response_received: str
    detection_point: Optional[str] = None
    latency_ms: float = 0.0
    notes: str = ""

    @property
    def is_vulnerability(self) -> bool:
        """True if the test found a vulnerability."""
        return self.outcome in (TestOutcome.SUCCEEDED, TestOutcome.PARTIAL)

    @property
    def is_blocked(self) -> bool:
        """True if the attack was blocked."""
        return self.outcome == TestOutcome.BLOCKED

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "result_id": self.result_id,
            "technique_id": self.technique.technique_id,
            "technique_name": self.technique.name,
            "category": self.technique.category.value,
            "outcome": self.outcome.value,
            "timestamp": self.timestamp.isoformat(),
            "target_agent_id": self.target_agent_id,
            "payload_used": self.payload_used,
            "response_received": self.response_received,
            "detection_point": self.detection_point,
            "latency_ms": round(self.latency_ms, 3),
            "is_vulnerability": self.is_vulnerability,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class RedTeamCampaign:
    """Immutable summary of a red team campaign (batch of tests)."""

    campaign_id: str
    started_at: datetime
    completed_at: datetime
    target_agent_id: str
    categories_tested: tuple[AttackCategory, ...]
    results: tuple[RedTeamResult, ...]

    @property
    def total_tests(self) -> int:
        """Total number of tests run."""
        return len(self.results)

    @property
    def blocked_count(self) -> int:
        """Number of attacks blocked."""
        return sum(1 for r in self.results if r.outcome == TestOutcome.BLOCKED)

    @property
    def detected_count(self) -> int:
        """Number of attacks detected (but not blocked)."""
        return sum(1 for r in self.results if r.outcome == TestOutcome.DETECTED)

    @property
    def vulnerability_count(self) -> int:
        """Number of vulnerabilities found."""
        return sum(1 for r in self.results if r.is_vulnerability)

    @property
    def block_rate(self) -> float:
        """Percentage of attacks blocked."""
        if self.total_tests == 0:
            return 0.0
        return self.blocked_count / self.total_tests

    @property
    def detection_rate(self) -> float:
        """Percentage of attacks detected (blocked + detected)."""
        if self.total_tests == 0:
            return 0.0
        return (self.blocked_count + self.detected_count) / self.total_tests

    @property
    def vulnerability_rate(self) -> float:
        """Percentage of tests that found vulnerabilities."""
        if self.total_tests == 0:
            return 0.0
        return self.vulnerability_count / self.total_tests

    def results_by_category(self) -> dict[str, list[RedTeamResult]]:
        """Group results by attack category."""
        grouped: dict[str, list[RedTeamResult]] = {}
        for r in self.results:
            cat = r.technique.category.value
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append(r)
        return grouped

    def vulnerabilities(self) -> list[RedTeamResult]:
        """Get all results that found vulnerabilities."""
        return [r for r in self.results if r.is_vulnerability]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "campaign_id": self.campaign_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "target_agent_id": self.target_agent_id,
            "categories_tested": [c.value for c in self.categories_tested],
            "total_tests": self.total_tests,
            "blocked_count": self.blocked_count,
            "detected_count": self.detected_count,
            "vulnerability_count": self.vulnerability_count,
            "block_rate": round(self.block_rate, 4),
            "detection_rate": round(self.detection_rate, 4),
            "vulnerability_rate": round(self.vulnerability_rate, 4),
            "results": [r.to_dict() for r in self.results],
        }


class RedTeamEngine:
    """
    Automated red teaming orchestrator.

    Executes adversarial tests from the AURA-ATT&CK taxonomy against
    target agents in sandboxed environments. Tracks results and generates
    campaign reports.

    Usage:
        engine = RedTeamEngine()

        # Run a single technique
        result = await engine.execute_technique(
            technique_id="ATA-01.001",
            target_agent_id="coder-agent",
        )

        # Run a full campaign
        campaign = await engine.run_campaign(
            target_agent_id="coder-agent",
            categories=[AttackCategory.PROMPT_INJECTION],
        )
    """

    def __init__(
        self,
        test_executor: Optional[Any] = None,
        sandboxed: bool = True,
    ):
        self._executor = test_executor
        self.sandboxed = sandboxed
        self._results: deque[RedTeamResult] = deque(maxlen=10000)
        self._campaigns: deque[RedTeamCampaign] = deque(maxlen=1000)

    async def execute_technique(
        self,
        technique_id: str,
        target_agent_id: str,
        custom_payload: Optional[str] = None,
    ) -> RedTeamResult:
        """
        Execute a single red team technique.

        Args:
            technique_id: AURA-ATT&CK technique ID.
            target_agent_id: Agent to test against.
            custom_payload: Optional custom payload (defaults to technique's example).

        Returns:
            RedTeamResult with outcome.
        """
        technique = get_technique_by_id(technique_id)
        if technique is None:
            return RedTeamResult(
                result_id=f"rr-{uuid.uuid4().hex[:16]}",
                technique=AttackTechnique(
                    technique_id=technique_id,
                    name="Unknown",
                    category=AttackCategory.PROMPT_INJECTION,
                    description="Unknown technique",
                    complexity=(
                        technique.complexity if technique else _default_complexity()
                    ),
                    mitre_attack_ids=(),
                    nist_controls=(),
                    detection_points=(),
                    example_payload="",
                    expected_behavior="",
                    remediation="",
                ),
                outcome=TestOutcome.ERROR,
                timestamp=datetime.now(timezone.utc),
                target_agent_id=target_agent_id,
                payload_used="",
                response_received="",
                notes=f"Technique {technique_id} not found in taxonomy",
            )

        payload = custom_payload or technique.example_payload
        result = await self._execute_test(technique, target_agent_id, payload)
        self._results.append(result)
        return result

    async def run_campaign(
        self,
        target_agent_id: str,
        categories: Optional[list[AttackCategory]] = None,
        technique_ids: Optional[list[str]] = None,
    ) -> RedTeamCampaign:
        """
        Run a red team campaign with multiple techniques.

        Args:
            target_agent_id: Agent to test against.
            categories: Attack categories to include (None = all).
            technique_ids: Specific technique IDs (overrides categories).

        Returns:
            RedTeamCampaign with all results.
        """
        started_at = datetime.now(timezone.utc)

        if technique_ids:
            techniques = [get_technique_by_id(tid) for tid in technique_ids]
            techniques = [t for t in techniques if t is not None]
        elif categories:
            techniques = []
            for cat in categories:
                techniques.extend(get_techniques_by_category(cat))
        else:
            techniques = list(AURA_ATTACK_TAXONOMY)

        results: list[RedTeamResult] = []
        for technique in techniques:
            result = await self._execute_test(
                technique, target_agent_id, technique.example_payload
            )
            results.append(result)
            self._results.append(result)

        tested_categories = tuple(
            sorted(
                {t.category for t in techniques},
                key=lambda c: c.value,
            )
        )

        campaign = RedTeamCampaign(
            campaign_id=f"rc-{uuid.uuid4().hex[:16]}",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            target_agent_id=target_agent_id,
            categories_tested=tested_categories,
            results=tuple(results),
        )
        self._campaigns.append(campaign)
        return campaign

    def get_all_results(self) -> list[RedTeamResult]:
        """Get all test results."""
        return list(self._results)

    def get_all_campaigns(self) -> list[RedTeamCampaign]:
        """Get all campaigns."""
        return list(self._campaigns)

    def get_vulnerabilities(self) -> list[RedTeamResult]:
        """Get all results that found vulnerabilities."""
        return [r for r in self._results if r.is_vulnerability]

    @property
    def total_tests(self) -> int:
        """Total number of tests executed."""
        return len(self._results)

    @property
    def total_campaigns(self) -> int:
        """Total number of campaigns run."""
        return len(self._campaigns)

    @property
    def vulnerability_count(self) -> int:
        """Total vulnerabilities found."""
        return sum(1 for r in self._results if r.is_vulnerability)

    # =========================================================================
    # Internal Methods
    # =========================================================================

    async def _execute_test(
        self,
        technique: AttackTechnique,
        target_agent_id: str,
        payload: str,
    ) -> RedTeamResult:
        """Execute a single test against an agent."""
        if self._executor:
            return await self._executor.execute(technique, target_agent_id, payload)

        # Default mock execution: simulate blocked response
        return RedTeamResult(
            result_id=f"rr-{uuid.uuid4().hex[:16]}",
            technique=technique,
            outcome=TestOutcome.BLOCKED,
            timestamp=datetime.now(timezone.utc),
            target_agent_id=target_agent_id,
            payload_used=payload,
            response_received="[Mock] Attack blocked by security controls",
            detection_point=(
                technique.detection_points[0] if technique.detection_points else None
            ),
            latency_ms=5.0,
            notes="Mock execution - replace with real agent executor",
        )


def _default_complexity():
    """Default complexity for unknown techniques."""
    from .taxonomy import TechniqueComplexity

    return TechniqueComplexity.MEDIUM


# Singleton instance
_engine_instance: Optional[RedTeamEngine] = None


def get_red_team_engine() -> RedTeamEngine:
    """Get singleton red team engine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = RedTeamEngine()
    return _engine_instance


def reset_red_team_engine() -> None:
    """Reset red team engine singleton (for testing)."""
    global _engine_instance
    _engine_instance = None
