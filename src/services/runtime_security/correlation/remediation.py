"""
Project Aura - Remediation Orchestrator

Generates candidate patches for detected vulnerabilities using
the Coder agent and routes them through HITL approval (ADR-032).

Based on ADR-083: Runtime Agent Security Platform

Integration:
- Agent Orchestrator (Coder/Reviewer/Validator)
- ADR-032 HITL workflow
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RemediationStatus(Enum):
    """Status of a remediation effort."""

    PENDING = "pending"
    PATCH_GENERATED = "patch_generated"
    REVIEW_REQUESTED = "review_requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    VERIFIED = "verified"
    FAILED = "failed"


@dataclass(frozen=True)
class PatchCandidate:
    """Immutable candidate patch for a detected vulnerability."""

    patch_id: str
    source_file: str
    line_start: int
    line_end: int
    original_code: str
    patched_code: str
    description: str
    confidence: float
    vulnerability_id: str
    generated_by: str = "coder-agent"
    generated_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "patch_id": self.patch_id,
            "source_file": self.source_file,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "original_code": self.original_code,
            "patched_code": self.patched_code,
            "description": self.description,
            "confidence": round(self.confidence, 4),
            "vulnerability_id": self.vulnerability_id,
            "generated_by": self.generated_by,
            "generated_at": (
                self.generated_at.isoformat() if self.generated_at else None
            ),
        }


@dataclass(frozen=True)
class RemediationPlan:
    """Immutable remediation plan for a detected vulnerability."""

    plan_id: str
    vulnerability_id: str
    correlation_id: str
    status: RemediationStatus
    patches: tuple[PatchCandidate, ...]
    created_at: datetime
    updated_at: datetime
    hitl_approval_id: Optional[str] = None
    reviewer_notes: str = ""

    @property
    def patch_count(self) -> int:
        """Number of candidate patches."""
        return len(self.patches)

    @property
    def best_patch(self) -> Optional[PatchCandidate]:
        """Highest confidence patch."""
        if not self.patches:
            return None
        return max(self.patches, key=lambda p: p.confidence)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "plan_id": self.plan_id,
            "vulnerability_id": self.vulnerability_id,
            "correlation_id": self.correlation_id,
            "status": self.status.value,
            "patches": [p.to_dict() for p in self.patches],
            "patch_count": self.patch_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "hitl_approval_id": self.hitl_approval_id,
            "reviewer_notes": self.reviewer_notes,
        }


class RemediationOrchestrator:
    """
    Orchestrates patch generation and HITL approval for vulnerabilities.

    Coordinates with the Coder agent to generate patches, the Reviewer
    agent to validate them, and the HITL workflow for approval.

    Usage:
        orchestrator = RemediationOrchestrator()
        plan = await orchestrator.create_plan(
            vulnerability_id="vuln-001",
            correlation_id="corr-001",
            source_file="src/services/api/handler.py",
            line_start=42,
            line_end=48,
            description="SQL injection in query builder",
        )
    """

    def __init__(
        self,
        coder_agent: Optional[Any] = None,
        reviewer_agent: Optional[Any] = None,
        hitl_gateway: Optional[Any] = None,
    ):
        self._coder = coder_agent
        self._reviewer = reviewer_agent
        self._hitl = hitl_gateway
        self._plans: dict[str, RemediationPlan] = {}

    async def create_plan(
        self,
        vulnerability_id: str,
        correlation_id: str,
        source_file: str,
        line_start: int,
        line_end: int,
        description: str,
        original_code: str = "",
    ) -> RemediationPlan:
        """
        Create a remediation plan for a vulnerability.

        Args:
            vulnerability_id: ID of the detected vulnerability.
            correlation_id: ID of the correlation that found it.
            source_file: Path to the affected source file.
            line_start: Start line of the vulnerable code.
            line_end: End line of the vulnerable code.
            description: Description of the vulnerability.
            original_code: The original vulnerable code.

        Returns:
            RemediationPlan with generated patches.
        """
        now = datetime.now(timezone.utc)
        plan_id = f"rp-{uuid.uuid4().hex[:16]}"

        # Generate patches
        patches = await self._generate_patches(
            vulnerability_id,
            source_file,
            line_start,
            line_end,
            description,
            original_code,
        )

        plan = RemediationPlan(
            plan_id=plan_id,
            vulnerability_id=vulnerability_id,
            correlation_id=correlation_id,
            status=(
                RemediationStatus.PATCH_GENERATED
                if patches
                else RemediationStatus.FAILED
            ),
            patches=tuple(patches),
            created_at=now,
            updated_at=now,
        )

        self._plans[plan_id] = plan
        return plan

    async def request_review(self, plan_id: str) -> RemediationPlan:
        """Submit a remediation plan for HITL review."""
        plan = self._plans.get(plan_id)
        if plan is None:
            raise ValueError(f"Plan {plan_id} not found")

        now = datetime.now(timezone.utc)
        updated = RemediationPlan(
            plan_id=plan.plan_id,
            vulnerability_id=plan.vulnerability_id,
            correlation_id=plan.correlation_id,
            status=RemediationStatus.REVIEW_REQUESTED,
            patches=plan.patches,
            created_at=plan.created_at,
            updated_at=now,
            hitl_approval_id=f"hitl-{uuid.uuid4().hex[:12]}",
        )
        self._plans[plan_id] = updated
        return updated

    async def approve_plan(
        self, plan_id: str, reviewer_notes: str = ""
    ) -> RemediationPlan:
        """Approve a remediation plan."""
        plan = self._plans.get(plan_id)
        if plan is None:
            raise ValueError(f"Plan {plan_id} not found")

        now = datetime.now(timezone.utc)
        updated = RemediationPlan(
            plan_id=plan.plan_id,
            vulnerability_id=plan.vulnerability_id,
            correlation_id=plan.correlation_id,
            status=RemediationStatus.APPROVED,
            patches=plan.patches,
            created_at=plan.created_at,
            updated_at=now,
            hitl_approval_id=plan.hitl_approval_id,
            reviewer_notes=reviewer_notes,
        )
        self._plans[plan_id] = updated
        return updated

    async def reject_plan(
        self, plan_id: str, reviewer_notes: str = ""
    ) -> RemediationPlan:
        """Reject a remediation plan."""
        plan = self._plans.get(plan_id)
        if plan is None:
            raise ValueError(f"Plan {plan_id} not found")

        now = datetime.now(timezone.utc)
        updated = RemediationPlan(
            plan_id=plan.plan_id,
            vulnerability_id=plan.vulnerability_id,
            correlation_id=plan.correlation_id,
            status=RemediationStatus.REJECTED,
            patches=plan.patches,
            created_at=plan.created_at,
            updated_at=now,
            hitl_approval_id=plan.hitl_approval_id,
            reviewer_notes=reviewer_notes,
        )
        self._plans[plan_id] = updated
        return updated

    def get_plan(self, plan_id: str) -> Optional[RemediationPlan]:
        """Get a remediation plan by ID."""
        return self._plans.get(plan_id)

    def get_all_plans(self) -> list[RemediationPlan]:
        """Get all remediation plans."""
        return list(self._plans.values())

    def get_plans_by_status(self, status: RemediationStatus) -> list[RemediationPlan]:
        """Get plans filtered by status."""
        return [p for p in self._plans.values() if p.status == status]

    @property
    def plan_count(self) -> int:
        """Total number of plans."""
        return len(self._plans)

    async def _generate_patches(
        self,
        vulnerability_id: str,
        source_file: str,
        line_start: int,
        line_end: int,
        description: str,
        original_code: str,
    ) -> list[PatchCandidate]:
        """Generate candidate patches using Coder agent."""
        if self._coder:
            # Real implementation would invoke Coder agent
            pass

        # Mock: generate a placeholder patch
        now = datetime.now(timezone.utc)
        return [
            PatchCandidate(
                patch_id=f"pc-{uuid.uuid4().hex[:12]}",
                source_file=source_file,
                line_start=line_start,
                line_end=line_end,
                original_code=original_code
                or f"# vulnerable code at {source_file}:{line_start}",
                patched_code=f"# patched code for {vulnerability_id}",
                description=f"Auto-generated patch for: {description}",
                confidence=0.85,
                vulnerability_id=vulnerability_id,
                generated_at=now,
            ),
        ]
