"""
Tests for the Remediation Orchestrator.

Covers RemediationStatus enum, PatchCandidate and RemediationPlan frozen
dataclasses, orchestrator plan creation, HITL review workflow, and plan
retrieval/filtering.
"""

import dataclasses
from datetime import datetime, timezone

import pytest

from src.services.runtime_security.correlation.remediation import (
    PatchCandidate,
    RemediationOrchestrator,
    RemediationPlan,
    RemediationStatus,
)

# =========================================================================
# RemediationStatus Tests
# =========================================================================


class TestRemediationStatus:
    """Tests for the RemediationStatus enum."""

    def test_pending_value(self):
        """Test PENDING status value."""
        assert RemediationStatus.PENDING.value == "pending"

    def test_patch_generated_value(self):
        """Test PATCH_GENERATED status value."""
        assert RemediationStatus.PATCH_GENERATED.value == "patch_generated"

    def test_review_requested_value(self):
        """Test REVIEW_REQUESTED status value."""
        assert RemediationStatus.REVIEW_REQUESTED.value == "review_requested"

    def test_approved_value(self):
        """Test APPROVED status value."""
        assert RemediationStatus.APPROVED.value == "approved"

    def test_rejected_value(self):
        """Test REJECTED status value."""
        assert RemediationStatus.REJECTED.value == "rejected"

    def test_applied_value(self):
        """Test APPLIED status value."""
        assert RemediationStatus.APPLIED.value == "applied"

    def test_verified_value(self):
        """Test VERIFIED status value."""
        assert RemediationStatus.VERIFIED.value == "verified"

    def test_failed_value(self):
        """Test FAILED status value."""
        assert RemediationStatus.FAILED.value == "failed"

    def test_status_count(self):
        """Test that there are exactly 8 status values."""
        assert len(RemediationStatus) == 8


# =========================================================================
# PatchCandidate Tests
# =========================================================================


class TestPatchCandidate:
    """Tests for the PatchCandidate frozen dataclass."""

    def test_create_with_all_fields(self, now_utc: datetime):
        """Test creating a PatchCandidate with all fields."""
        patch = PatchCandidate(
            patch_id="pc-test001",
            source_file="src/handler.py",
            line_start=42,
            line_end=58,
            original_code="cursor.execute(f'SELECT * FROM {table}')",
            patched_code="cursor.execute('SELECT * FROM %s', (table,))",
            description="Parameterize SQL query",
            confidence=0.92,
            vulnerability_id="vuln-sql-001",
            generated_by="coder-agent",
            generated_at=now_utc,
        )
        assert patch.patch_id == "pc-test001"
        assert patch.source_file == "src/handler.py"
        assert patch.line_start == 42
        assert patch.line_end == 58
        assert patch.confidence == 0.92
        assert patch.vulnerability_id == "vuln-sql-001"
        assert patch.generated_by == "coder-agent"
        assert patch.generated_at == now_utc

    def test_create_with_defaults(self):
        """Test that optional fields default correctly."""
        patch = PatchCandidate(
            patch_id="pc-defaults",
            source_file="src/file.py",
            line_start=1,
            line_end=5,
            original_code="old",
            patched_code="new",
            description="fix",
            confidence=0.5,
            vulnerability_id="vuln-001",
        )
        assert patch.generated_by == "coder-agent"
        assert patch.generated_at is None

    def test_frozen_immutability(self):
        """Test that PatchCandidate fields cannot be mutated."""
        patch = PatchCandidate(
            patch_id="pc-frozen",
            source_file="src/file.py",
            line_start=1,
            line_end=5,
            original_code="old",
            patched_code="new",
            description="fix",
            confidence=0.5,
            vulnerability_id="vuln-002",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            patch.patch_id = "pc-mutated"  # type: ignore[misc]

    def test_frozen_immutability_confidence(self):
        """Test that confidence cannot be mutated."""
        patch = PatchCandidate(
            patch_id="pc-frozen2",
            source_file="src/file.py",
            line_start=1,
            line_end=5,
            original_code="old",
            patched_code="new",
            description="fix",
            confidence=0.5,
            vulnerability_id="vuln-003",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            patch.confidence = 1.0  # type: ignore[misc]

    def test_to_dict_serialization(self, now_utc: datetime):
        """Test to_dict produces expected keys and values."""
        patch = PatchCandidate(
            patch_id="pc-dict001",
            source_file="src/handler.py",
            line_start=10,
            line_end=20,
            original_code="old code",
            patched_code="new code",
            description="Fix vulnerability",
            confidence=0.87654,
            vulnerability_id="vuln-004",
            generated_by="coder-agent",
            generated_at=now_utc,
        )
        d = patch.to_dict()
        assert d["patch_id"] == "pc-dict001"
        assert d["source_file"] == "src/handler.py"
        assert d["line_start"] == 10
        assert d["line_end"] == 20
        assert d["original_code"] == "old code"
        assert d["patched_code"] == "new code"
        assert d["description"] == "Fix vulnerability"
        assert d["confidence"] == 0.8765
        assert d["vulnerability_id"] == "vuln-004"
        assert d["generated_by"] == "coder-agent"
        assert d["generated_at"] == now_utc.isoformat()

    def test_to_dict_generated_at_none(self):
        """Test that generated_at serializes as None when not set."""
        patch = PatchCandidate(
            patch_id="pc-noneat",
            source_file="src/file.py",
            line_start=1,
            line_end=2,
            original_code="old",
            patched_code="new",
            description="fix",
            confidence=0.5,
            vulnerability_id="vuln-005",
        )
        d = patch.to_dict()
        assert d["generated_at"] is None


# =========================================================================
# RemediationPlan Tests
# =========================================================================


class TestRemediationPlan:
    """Tests for the RemediationPlan frozen dataclass."""

    def test_create_with_patches(self, now_utc: datetime):
        """Test creating a RemediationPlan with patches."""
        patch = PatchCandidate(
            patch_id="pc-plan001",
            source_file="src/handler.py",
            line_start=42,
            line_end=58,
            original_code="old",
            patched_code="new",
            description="fix",
            confidence=0.85,
            vulnerability_id="vuln-010",
        )
        plan = RemediationPlan(
            plan_id="rp-test001",
            vulnerability_id="vuln-010",
            correlation_id="corr-001",
            status=RemediationStatus.PATCH_GENERATED,
            patches=(patch,),
            created_at=now_utc,
            updated_at=now_utc,
        )
        assert plan.plan_id == "rp-test001"
        assert plan.vulnerability_id == "vuln-010"
        assert plan.status == RemediationStatus.PATCH_GENERATED
        assert len(plan.patches) == 1

    def test_frozen_immutability(self, now_utc: datetime):
        """Test that RemediationPlan fields cannot be mutated."""
        plan = RemediationPlan(
            plan_id="rp-frozen",
            vulnerability_id="vuln-011",
            correlation_id="corr-002",
            status=RemediationStatus.PENDING,
            patches=(),
            created_at=now_utc,
            updated_at=now_utc,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            plan.plan_id = "rp-mutated"  # type: ignore[misc]

    def test_patch_count(self, now_utc: datetime):
        """Test patch_count property returns correct count."""
        patches = tuple(
            PatchCandidate(
                patch_id=f"pc-cnt{i}",
                source_file="f.py",
                line_start=i,
                line_end=i + 1,
                original_code="old",
                patched_code="new",
                description="fix",
                confidence=0.5 + i * 0.1,
                vulnerability_id="vuln-012",
            )
            for i in range(3)
        )
        plan = RemediationPlan(
            plan_id="rp-cnt",
            vulnerability_id="vuln-012",
            correlation_id="corr-003",
            status=RemediationStatus.PATCH_GENERATED,
            patches=patches,
            created_at=now_utc,
            updated_at=now_utc,
        )
        assert plan.patch_count == 3

    def test_best_patch_highest_confidence(self, now_utc: datetime):
        """Test best_patch returns patch with highest confidence."""
        low = PatchCandidate(
            patch_id="pc-low",
            source_file="f.py",
            line_start=1,
            line_end=2,
            original_code="o",
            patched_code="n",
            description="d",
            confidence=0.3,
            vulnerability_id="v",
        )
        high = PatchCandidate(
            patch_id="pc-high",
            source_file="f.py",
            line_start=3,
            line_end=4,
            original_code="o",
            patched_code="n",
            description="d",
            confidence=0.95,
            vulnerability_id="v",
        )
        plan = RemediationPlan(
            plan_id="rp-best",
            vulnerability_id="v",
            correlation_id="c",
            status=RemediationStatus.PATCH_GENERATED,
            patches=(low, high),
            created_at=now_utc,
            updated_at=now_utc,
        )
        assert plan.best_patch is high
        assert plan.best_patch.confidence == 0.95

    def test_best_patch_none_when_empty(self, now_utc: datetime):
        """Test best_patch returns None when no patches."""
        plan = RemediationPlan(
            plan_id="rp-nopatch",
            vulnerability_id="v",
            correlation_id="c",
            status=RemediationStatus.FAILED,
            patches=(),
            created_at=now_utc,
            updated_at=now_utc,
        )
        assert plan.best_patch is None

    def test_to_dict_serialization(self, now_utc: datetime):
        """Test to_dict produces expected keys and values."""
        patch = PatchCandidate(
            patch_id="pc-ser",
            source_file="f.py",
            line_start=1,
            line_end=2,
            original_code="old",
            patched_code="new",
            description="fix",
            confidence=0.8,
            vulnerability_id="vuln-013",
        )
        plan = RemediationPlan(
            plan_id="rp-ser",
            vulnerability_id="vuln-013",
            correlation_id="corr-004",
            status=RemediationStatus.APPROVED,
            patches=(patch,),
            created_at=now_utc,
            updated_at=now_utc,
            hitl_approval_id="hitl-abc",
            reviewer_notes="Looks good",
        )
        d = plan.to_dict()
        assert d["plan_id"] == "rp-ser"
        assert d["vulnerability_id"] == "vuln-013"
        assert d["correlation_id"] == "corr-004"
        assert d["status"] == "approved"
        assert len(d["patches"]) == 1
        assert d["patch_count"] == 1
        assert d["created_at"] == now_utc.isoformat()
        assert d["updated_at"] == now_utc.isoformat()
        assert d["hitl_approval_id"] == "hitl-abc"
        assert d["reviewer_notes"] == "Looks good"

    def test_status_field(self, now_utc: datetime):
        """Test that status field holds the correct enum value."""
        plan = RemediationPlan(
            plan_id="rp-status",
            vulnerability_id="v",
            correlation_id="c",
            status=RemediationStatus.REVIEW_REQUESTED,
            patches=(),
            created_at=now_utc,
            updated_at=now_utc,
        )
        assert plan.status == RemediationStatus.REVIEW_REQUESTED
        assert plan.status.value == "review_requested"


# =========================================================================
# RemediationOrchestrator Tests
# =========================================================================


class TestRemediationOrchestrator:
    """Tests for the RemediationOrchestrator workflow operations."""

    async def test_create_plan(self, mock_remediation: RemediationOrchestrator):
        """Test create_plan generates a plan with PATCH_GENERATED status."""
        plan = await mock_remediation.create_plan(
            vulnerability_id="vuln-020",
            correlation_id="corr-020",
            source_file="src/handler.py",
            line_start=42,
            line_end=58,
            description="SQL injection in query builder",
        )
        assert plan.plan_id.startswith("rp-")
        assert plan.status == RemediationStatus.PATCH_GENERATED
        assert plan.vulnerability_id == "vuln-020"
        assert plan.correlation_id == "corr-020"
        assert plan.patch_count >= 1

    async def test_create_plan_generates_patch(
        self, mock_remediation: RemediationOrchestrator
    ):
        """Test that create_plan generates at least one patch candidate."""
        plan = await mock_remediation.create_plan(
            vulnerability_id="vuln-021",
            correlation_id="corr-021",
            source_file="src/db.py",
            line_start=10,
            line_end=15,
            description="Unsafe query",
        )
        assert len(plan.patches) >= 1
        patch = plan.patches[0]
        assert patch.source_file == "src/db.py"
        assert patch.line_start == 10
        assert patch.line_end == 15
        assert patch.vulnerability_id == "vuln-021"
        assert patch.confidence > 0

    async def test_create_plan_stores_plan(
        self, mock_remediation: RemediationOrchestrator
    ):
        """Test that created plan is retrievable by get_plan."""
        plan = await mock_remediation.create_plan(
            vulnerability_id="vuln-022",
            correlation_id="corr-022",
            source_file="src/api.py",
            line_start=1,
            line_end=5,
            description="XSS vulnerability",
        )
        retrieved = mock_remediation.get_plan(plan.plan_id)
        assert retrieved is not None
        assert retrieved.plan_id == plan.plan_id

    async def test_request_review(self, mock_remediation: RemediationOrchestrator):
        """Test that request_review changes status and sets hitl_approval_id."""
        plan = await mock_remediation.create_plan(
            vulnerability_id="vuln-023",
            correlation_id="corr-023",
            source_file="src/route.py",
            line_start=10,
            line_end=20,
            description="CSRF token missing",
        )
        reviewed = await mock_remediation.request_review(plan.plan_id)
        assert reviewed.status == RemediationStatus.REVIEW_REQUESTED
        assert reviewed.hitl_approval_id is not None
        assert reviewed.hitl_approval_id.startswith("hitl-")

    async def test_approve_plan(self, mock_remediation: RemediationOrchestrator):
        """Test that approve_plan changes status to APPROVED with notes."""
        plan = await mock_remediation.create_plan(
            vulnerability_id="vuln-024",
            correlation_id="corr-024",
            source_file="src/auth.py",
            line_start=5,
            line_end=10,
            description="Weak hashing",
        )
        approved = await mock_remediation.approve_plan(
            plan.plan_id, reviewer_notes="Verified fix is correct"
        )
        assert approved.status == RemediationStatus.APPROVED
        assert approved.reviewer_notes == "Verified fix is correct"

    async def test_reject_plan(self, mock_remediation: RemediationOrchestrator):
        """Test that reject_plan changes status to REJECTED."""
        plan = await mock_remediation.create_plan(
            vulnerability_id="vuln-025",
            correlation_id="corr-025",
            source_file="src/util.py",
            line_start=1,
            line_end=3,
            description="Minor issue",
        )
        rejected = await mock_remediation.reject_plan(
            plan.plan_id, reviewer_notes="Fix introduces regression"
        )
        assert rejected.status == RemediationStatus.REJECTED
        assert rejected.reviewer_notes == "Fix introduces regression"

    async def test_request_review_plan_not_found(
        self, mock_remediation: RemediationOrchestrator
    ):
        """Test that request_review raises ValueError for unknown plan."""
        with pytest.raises(ValueError, match="not found"):
            await mock_remediation.request_review("rp-nonexistent")

    async def test_approve_plan_not_found(
        self, mock_remediation: RemediationOrchestrator
    ):
        """Test that approve_plan raises ValueError for unknown plan."""
        with pytest.raises(ValueError, match="not found"):
            await mock_remediation.approve_plan("rp-nonexistent")

    async def test_reject_plan_not_found(
        self, mock_remediation: RemediationOrchestrator
    ):
        """Test that reject_plan raises ValueError for unknown plan."""
        with pytest.raises(ValueError, match="not found"):
            await mock_remediation.reject_plan("rp-nonexistent")

    async def test_get_all_plans(self, mock_remediation: RemediationOrchestrator):
        """Test get_all_plans returns all stored plans."""
        await mock_remediation.create_plan(
            vulnerability_id="vuln-a",
            correlation_id="corr-a",
            source_file="a.py",
            line_start=1,
            line_end=2,
            description="a",
        )
        await mock_remediation.create_plan(
            vulnerability_id="vuln-b",
            correlation_id="corr-b",
            source_file="b.py",
            line_start=1,
            line_end=2,
            description="b",
        )
        plans = mock_remediation.get_all_plans()
        assert len(plans) == 2

    async def test_get_plans_by_status(self, mock_remediation: RemediationOrchestrator):
        """Test get_plans_by_status filters correctly."""
        plan1 = await mock_remediation.create_plan(
            vulnerability_id="vuln-s1",
            correlation_id="corr-s1",
            source_file="s1.py",
            line_start=1,
            line_end=2,
            description="s1",
        )
        await mock_remediation.create_plan(
            vulnerability_id="vuln-s2",
            correlation_id="corr-s2",
            source_file="s2.py",
            line_start=1,
            line_end=2,
            description="s2",
        )
        await mock_remediation.approve_plan(plan1.plan_id)

        generated = mock_remediation.get_plans_by_status(
            RemediationStatus.PATCH_GENERATED
        )
        approved = mock_remediation.get_plans_by_status(RemediationStatus.APPROVED)
        assert len(generated) == 1
        assert len(approved) == 1

    async def test_plan_count(self, mock_remediation: RemediationOrchestrator):
        """Test plan_count property."""
        assert mock_remediation.plan_count == 0
        await mock_remediation.create_plan(
            vulnerability_id="vuln-cnt",
            correlation_id="corr-cnt",
            source_file="cnt.py",
            line_start=1,
            line_end=2,
            description="cnt",
        )
        assert mock_remediation.plan_count == 1

    async def test_get_plan_returns_none_for_unknown(
        self, mock_remediation: RemediationOrchestrator
    ):
        """Test that get_plan returns None for unknown plan_id."""
        assert mock_remediation.get_plan("rp-ghost") is None

    async def test_approve_preserves_hitl_id(
        self, mock_remediation: RemediationOrchestrator
    ):
        """Test that approve_plan preserves the hitl_approval_id from review."""
        plan = await mock_remediation.create_plan(
            vulnerability_id="vuln-hitl",
            correlation_id="corr-hitl",
            source_file="hitl.py",
            line_start=1,
            line_end=2,
            description="hitl",
        )
        reviewed = await mock_remediation.request_review(plan.plan_id)
        hitl_id = reviewed.hitl_approval_id
        approved = await mock_remediation.approve_plan(plan.plan_id)
        assert approved.hitl_approval_id == hitl_id
