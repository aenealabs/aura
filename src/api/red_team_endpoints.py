"""
Project Aura - Red Team Dashboard API Endpoints

REST API endpoints for the Red Team Dashboard (ADR-028 Phase 7).
Provides visibility into adversarial testing results, CI/CD gate status,
and security findings for AI-generated patches.

Endpoints:
- GET  /api/v1/red-team/status     - CI/CD gate status
- GET  /api/v1/red-team/categories - Test category breakdown
- GET  /api/v1/red-team/findings   - List findings with filters
- GET  /api/v1/red-team/trends     - 30-day trend data
- GET  /api/v1/red-team/findings/{id} - Get finding details
- POST /api/v1/red-team/findings/{id}/dismiss - Dismiss a finding
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from src.api.log_sanitizer import sanitize_log

logger = logging.getLogger(__name__)

# ============================================================================
# Router Configuration
# ============================================================================

router = APIRouter(prefix="/api/v1/red-team", tags=["Red Team"])


# ============================================================================
# Enums
# ============================================================================


class GateStatus(str, Enum):
    """CI/CD gate status values."""

    PASSED = "passed"
    WARNING = "warning"
    BLOCKED = "blocked"


class FindingSeverity(str, Enum):
    """Finding severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingStatus(str, Enum):
    """Finding status values."""

    OPEN = "open"
    DISMISSED = "dismissed"
    RESOLVED = "resolved"


class TestCategory(str, Enum):
    """Adversarial test categories."""

    PROMPT_INJECTION = "prompt_injection"
    CODE_INJECTION = "code_injection"
    SANDBOX_ESCAPE = "sandbox_escape"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DATA_EXFILTRATION = "data_exfiltration"
    RESOURCE_ABUSE = "resource_abuse"


# ============================================================================
# Pydantic Models
# ============================================================================


class CIGateStatusResponse(BaseModel):
    """CI/CD gate status response."""

    status: GateStatus
    findings_blocking: int = Field(description="Number of findings blocking deployment")
    last_run_at: str = Field(description="ISO timestamp of last test run")
    last_run_duration_seconds: float = Field(description="Duration of last test run")
    pipeline_url: str | None = Field(None, description="Link to pipeline details")
    message: str = Field(description="Human-readable status message")


class TestCategoryStats(BaseModel):
    """Statistics for a single test category."""

    category: TestCategory
    display_name: str
    icon: str
    tests_run: int
    tests_passed: int
    tests_failed: int
    coverage_percent: float = Field(ge=0, le=100)


class TestCategoriesResponse(BaseModel):
    """Test categories breakdown response."""

    categories: list[TestCategoryStats]
    total_tests: int
    total_passed: int
    total_failed: int
    overall_coverage: float


class FindingListItem(BaseModel):
    """Condensed finding for list view."""

    id: str
    title: str
    description: str
    category: TestCategory
    severity: FindingSeverity
    status: FindingStatus
    patch_id: str | None = None
    test_id: str | None = None
    created_at: str
    dismissed_at: str | None = None
    dismissed_by: str | None = None


class FindingsListResponse(BaseModel):
    """Response for findings list endpoint."""

    findings: list[FindingListItem]
    total: int
    by_severity: dict[str, int]
    by_category: dict[str, int]


class FindingDetailResponse(BaseModel):
    """Full finding details."""

    id: str
    title: str
    description: str
    category: TestCategory
    severity: FindingSeverity
    status: FindingStatus
    patch_id: str | None = None
    test_id: str | None = None
    test_name: str | None = None
    affected_file: str | None = None
    affected_line: int | None = None
    evidence: str | None = None
    remediation: str | None = None
    cwe_ids: list[str] = []
    created_at: str
    dismissed_at: str | None = None
    dismissed_by: str | None = None
    dismissal_reason: str | None = None
    metadata: dict[str, Any] | None = None


class TrendDataPoint(BaseModel):
    """Single data point for trend chart."""

    date: str
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0


class TrendsResponse(BaseModel):
    """30-day trend data response."""

    data: list[TrendDataPoint]
    period_start: str
    period_end: str
    total_findings: int
    trend_direction: str = Field(description="up, down, or stable")


class DismissRequest(BaseModel):
    """Request to dismiss a finding."""

    dismissed_by: str = Field(..., description="Email of person dismissing")
    reason: str = Field(..., description="Reason for dismissal")


class DismissResponse(BaseModel):
    """Response for dismiss action."""

    success: bool
    finding_id: str
    new_status: FindingStatus
    message: str


# ============================================================================
# In-Memory Data Store (Replace with DynamoDB in production)
# ============================================================================

# Mock data store for development
_findings_store: dict[str, dict[str, Any]] = {}
_test_runs: list[dict[str, Any]] = []


def _init_mock_data() -> None:
    """Initialize mock data for development."""
    if _findings_store:
        return  # Already initialized

    # Create sample findings
    sample_findings: list[dict[str, Any]] = [
        {
            "id": str(uuid.uuid4()),
            "title": "Prompt injection detected in patch #2847",
            "description": "LLM output contains instruction override pattern that could bypass security controls",
            "category": TestCategory.PROMPT_INJECTION,
            "severity": FindingSeverity.CRITICAL,
            "status": FindingStatus.OPEN,
            "patch_id": "patch-2847",
            "test_id": "pi-001",
            "test_name": "Instruction Override Detection",
            "affected_file": "src/agents/coder_agent.py",
            "affected_line": 156,
            "evidence": "Output contains 'ignore previous instructions' pattern",
            "remediation": "Add output sanitization filter before returning LLM response",
            "cwe_ids": ["CWE-94", "CWE-77"],
            "created_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "title": "SQL injection pattern in patch #2851",
            "description": "Generated code contains unsanitized SQL query construction",
            "category": TestCategory.CODE_INJECTION,
            "severity": FindingSeverity.HIGH,
            "status": FindingStatus.OPEN,
            "patch_id": "patch-2851",
            "test_id": "ci-003",
            "test_name": "SQL Injection Scanner",
            "affected_file": "src/services/data_service.py",
            "affected_line": 89,
            "evidence": 'f-string SQL query with user input: f"SELECT * FROM {table}"',
            "remediation": "Use parameterized queries instead of string formatting",
            "cwe_ids": ["CWE-89"],
            "created_at": (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "title": "Privilege escalation attempt in patch #2849",
            "description": "Patch attempts to modify file permissions beyond required scope",
            "category": TestCategory.PRIVILEGE_ESCALATION,
            "severity": FindingSeverity.HIGH,
            "status": FindingStatus.OPEN,
            "patch_id": "patch-2849",
            "test_id": "pe-002",
            "test_name": "Permission Escalation Check",
            "affected_file": "src/utils/file_utils.py",
            "affected_line": 45,
            "evidence": "os.chmod(path, 0o777) grants excessive permissions",
            "remediation": "Limit permissions to minimum required (e.g., 0o644 for files)",
            "cwe_ids": ["CWE-269", "CWE-732"],
            "created_at": (datetime.now(timezone.utc) - timedelta(hours=8)).isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "title": "Potential data exfiltration in patch #2845",
            "description": "Code contains network call that may leak sensitive data",
            "category": TestCategory.DATA_EXFILTRATION,
            "severity": FindingSeverity.MEDIUM,
            "status": FindingStatus.DISMISSED,
            "patch_id": "patch-2845",
            "test_id": "de-001",
            "test_name": "Data Leakage Scanner",
            "evidence": "HTTP POST to external endpoint with request body",
            "remediation": "Review network call and ensure no sensitive data is transmitted",
            "cwe_ids": ["CWE-200"],
            "created_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            "dismissed_at": (
                datetime.now(timezone.utc) - timedelta(hours=12)
            ).isoformat(),
            "dismissed_by": "security@aenealabs.com",
            "dismissal_reason": "False positive - external call is to internal metrics service",
        },
        {
            "id": str(uuid.uuid4()),
            "title": "Container breakout pattern in patch #2840",
            "description": "Code attempts to mount host filesystem into container",
            "category": TestCategory.SANDBOX_ESCAPE,
            "severity": FindingSeverity.CRITICAL,
            "status": FindingStatus.RESOLVED,
            "patch_id": "patch-2840",
            "test_id": "se-001",
            "test_name": "Container Escape Detection",
            "evidence": "docker run -v /:/host pattern detected",
            "remediation": "Remove host mount and use dedicated volumes",
            "cwe_ids": ["CWE-250"],
            "created_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
        },
    ]

    for finding in sample_findings:
        _findings_store[finding["id"]] = finding

    # Create sample test run
    _test_runs.append(
        {
            "run_id": str(uuid.uuid4()),
            "started_at": (
                datetime.now(timezone.utc) - timedelta(minutes=5)
            ).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": 127.5,
            "status": GateStatus.WARNING,
            "total_tests": 357,
            "passed": 353,
            "failed": 4,
            "categories": {
                TestCategory.PROMPT_INJECTION: {"run": 156, "passed": 154, "failed": 2},
                TestCategory.CODE_INJECTION: {"run": 89, "passed": 89, "failed": 0},
                TestCategory.SANDBOX_ESCAPE: {"run": 45, "passed": 45, "failed": 0},
                TestCategory.PRIVILEGE_ESCALATION: {
                    "run": 67,
                    "passed": 65,
                    "failed": 2,
                },
            },
        }
    )


# Initialize mock data on module load
_init_mock_data()


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("/status", response_model=CIGateStatusResponse)
async def get_gate_status() -> CIGateStatusResponse:
    """
    Get current CI/CD gate status.

    Returns the overall gate status (passed/warning/blocked),
    number of blocking findings, and last run information.
    """
    _init_mock_data()

    # Calculate status from findings
    open_findings = [
        f for f in _findings_store.values() if f["status"] == FindingStatus.OPEN
    ]
    critical_count = sum(
        1 for f in open_findings if f["severity"] == FindingSeverity.CRITICAL
    )
    high_count = sum(1 for f in open_findings if f["severity"] == FindingSeverity.HIGH)

    # Determine gate status
    if critical_count > 0:
        status = GateStatus.BLOCKED
        message = f"{critical_count} critical finding(s) blocking deployment"
    elif high_count > 0:
        status = GateStatus.WARNING
        message = f"{high_count} high severity finding(s) require review"
    else:
        status = GateStatus.PASSED
        message = "All adversarial tests passed"

    # Get last run info
    last_run = _test_runs[-1] if _test_runs else None

    return CIGateStatusResponse(
        status=status,
        findings_blocking=critical_count + high_count,
        last_run_at=(
            last_run["completed_at"]
            if last_run
            else datetime.now(timezone.utc).isoformat()
        ),
        last_run_duration_seconds=last_run["duration_seconds"] if last_run else 0.0,
        pipeline_url="https://github.com/aenealabs/aura/actions/runs/12345",
        message=message,
    )


@router.get("/categories", response_model=TestCategoriesResponse)
async def get_test_categories() -> TestCategoriesResponse:
    """
    Get test category breakdown with pass/fail statistics.

    Returns statistics for each adversarial test category including
    tests run, passed, failed, and coverage percentage.
    """
    _init_mock_data()

    last_run = _test_runs[-1] if _test_runs else None
    if not last_run:
        return TestCategoriesResponse(
            categories=[],
            total_tests=0,
            total_passed=0,
            total_failed=0,
            overall_coverage=0.0,
        )

    # Build category stats
    category_config: dict[TestCategory, dict[str, Any]] = {
        TestCategory.PROMPT_INJECTION: {
            "display_name": "Prompt Injection",
            "icon": "syringe",
            "target_coverage": 90,
        },
        TestCategory.CODE_INJECTION: {
            "display_name": "Code Injection",
            "icon": "code",
            "target_coverage": 100,
        },
        TestCategory.SANDBOX_ESCAPE: {
            "display_name": "Sandbox Escape",
            "icon": "box",
            "target_coverage": 85,
        },
        TestCategory.PRIVILEGE_ESCALATION: {
            "display_name": "Privilege Escalation",
            "icon": "arrow-up",
            "target_coverage": 80,
        },
        TestCategory.DATA_EXFILTRATION: {
            "display_name": "Data Exfiltration",
            "icon": "download",
            "target_coverage": 75,
        },
        TestCategory.RESOURCE_ABUSE: {
            "display_name": "Resource Abuse",
            "icon": "cpu",
            "target_coverage": 70,
        },
    }

    categories = []
    for cat, config in category_config.items():
        stats = last_run["categories"].get(cat, {"run": 0, "passed": 0, "failed": 0})
        run = stats.get("run", 0)
        passed = stats.get("passed", 0)
        failed = stats.get("failed", 0)

        # Calculate coverage as pass rate relative to target
        coverage = (passed / run * 100) if run > 0 else 0.0

        categories.append(
            TestCategoryStats(
                category=cat,
                display_name=str(config["display_name"]),
                icon=str(config["icon"]),
                tests_run=run,
                tests_passed=passed,
                tests_failed=failed,
                coverage_percent=round(coverage, 1),
            )
        )

    total_tests = last_run["total_tests"]
    total_passed = last_run["passed"]
    total_failed = last_run["failed"]
    overall_coverage = (total_passed / total_tests * 100) if total_tests > 0 else 0.0

    return TestCategoriesResponse(
        categories=categories,
        total_tests=total_tests,
        total_passed=total_passed,
        total_failed=total_failed,
        overall_coverage=round(overall_coverage, 1),
    )


@router.get("/findings", response_model=FindingsListResponse)
async def list_findings(
    severity: FindingSeverity | None = Query(  # noqa: B008
        None, description="Filter by severity"
    ),  # noqa: B008
    category: TestCategory | None = Query(  # noqa: B008
        None, description="Filter by category"
    ),  # noqa: B008
    status: FindingStatus | None = Query(  # noqa: B008
        None, description="Filter by status"
    ),  # noqa: B008
    limit: int = Query(  # noqa: B008
        50, ge=1, le=200, description="Maximum findings to return"
    ),  # noqa: B008
    offset: int = Query(0, ge=0, description="Offset for pagination"),  # noqa: B008
) -> FindingsListResponse:
    """
    List security findings with optional filters.

    Supports filtering by severity, category, and status.
    Returns paginated results with aggregated counts.
    """
    _init_mock_data()

    # Filter findings
    findings = list(_findings_store.values())

    if severity:
        findings = [f for f in findings if f["severity"] == severity]
    if category:
        findings = [f for f in findings if f["category"] == category]
    if status:
        findings = [f for f in findings if f["status"] == status]

    # Sort by created_at descending
    findings.sort(key=lambda x: x["created_at"], reverse=True)

    # Calculate aggregates before pagination
    all_findings = list(_findings_store.values())
    by_severity: dict[str, int] = {}
    by_category: dict[str, int] = {}

    for f in all_findings:
        sev = f["severity"].value if isinstance(f["severity"], Enum) else f["severity"]
        cat = f["category"].value if isinstance(f["category"], Enum) else f["category"]
        by_severity[sev] = by_severity.get(sev, 0) + 1
        by_category[cat] = by_category.get(cat, 0) + 1

    # Paginate
    total = len(findings)
    findings = findings[offset : offset + limit]

    # Convert to response model
    items = [
        FindingListItem(
            id=f["id"],
            title=f["title"],
            description=f["description"],
            category=f["category"],
            severity=f["severity"],
            status=f["status"],
            patch_id=f.get("patch_id"),
            test_id=f.get("test_id"),
            created_at=f["created_at"],
            dismissed_at=f.get("dismissed_at"),
            dismissed_by=f.get("dismissed_by"),
        )
        for f in findings
    ]

    return FindingsListResponse(
        findings=items,
        total=total,
        by_severity=by_severity,
        by_category=by_category,
    )


@router.get("/findings/{finding_id}", response_model=FindingDetailResponse)
async def get_finding(finding_id: str) -> FindingDetailResponse:
    """
    Get detailed information about a specific finding.
    """
    _init_mock_data()

    finding = _findings_store.get(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail=f"Finding {finding_id} not found")

    return FindingDetailResponse(
        id=finding["id"],
        title=finding["title"],
        description=finding["description"],
        category=finding["category"],
        severity=finding["severity"],
        status=finding["status"],
        patch_id=finding.get("patch_id"),
        test_id=finding.get("test_id"),
        test_name=finding.get("test_name"),
        affected_file=finding.get("affected_file"),
        affected_line=finding.get("affected_line"),
        evidence=finding.get("evidence"),
        remediation=finding.get("remediation"),
        cwe_ids=finding.get("cwe_ids", []),
        created_at=finding["created_at"],
        dismissed_at=finding.get("dismissed_at"),
        dismissed_by=finding.get("dismissed_by"),
        dismissal_reason=finding.get("dismissal_reason"),
        metadata=finding.get("metadata"),
    )


@router.post("/findings/{finding_id}/dismiss", response_model=DismissResponse)
async def dismiss_finding(finding_id: str, request: DismissRequest) -> DismissResponse:
    """
    Dismiss a security finding.

    Requires a reason for dismissal for audit purposes.
    Finding status will be changed to 'dismissed'.
    """
    _init_mock_data()

    finding = _findings_store.get(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail=f"Finding {finding_id} not found")

    if finding["status"] == FindingStatus.DISMISSED:
        raise HTTPException(status_code=400, detail="Finding is already dismissed")

    # Update finding
    finding["status"] = FindingStatus.DISMISSED
    finding["dismissed_at"] = datetime.now(timezone.utc).isoformat()
    finding["dismissed_by"] = request.dismissed_by
    finding["dismissal_reason"] = request.reason

    logger.info(
        f"Finding {sanitize_log(finding_id)} dismissed by {sanitize_log(request.dismissed_by)}: {sanitize_log(request.reason)}"
    )

    return DismissResponse(
        success=True,
        finding_id=finding_id,
        new_status=FindingStatus.DISMISSED,
        message=f"Finding dismissed by {request.dismissed_by}",
    )


@router.get("/trends", response_model=TrendsResponse)
async def get_trends(
    days: int = Query(  # noqa: B008
        30, ge=7, le=90, description="Number of days for trend data"
    ),  # noqa: B008
) -> TrendsResponse:
    """
    Get finding trends over time.

    Returns daily counts of findings by severity for the specified period.
    """
    _init_mock_data()

    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days)

    # Generate mock trend data
    data_points = []
    total_findings = 0

    # Simulate trending data with some variability
    import random

    random.seed(42)  # Consistent results

    prev_critical = 2
    prev_high = 5
    prev_medium = 8
    prev_low = 12

    for i in range(days):
        date = start_date + timedelta(days=i)

        # Add some randomness but keep trends somewhat stable
        critical = max(0, prev_critical + random.randint(-1, 1))
        high = max(0, prev_high + random.randint(-2, 2))
        medium = max(0, prev_medium + random.randint(-2, 3))
        low = max(0, prev_low + random.randint(-3, 3))

        # Recent spike in critical/high to simulate the current state
        if i >= days - 3:
            critical = max(critical, 1)
            high = max(high, 2)

        data_points.append(
            TrendDataPoint(
                date=date.isoformat(),
                critical=critical,
                high=high,
                medium=medium,
                low=low,
            )
        )

        total_findings += critical + high + medium + low
        prev_critical, prev_high, prev_medium, prev_low = critical, high, medium, low

    # Determine trend direction
    recent_sum = sum(dp.critical + dp.high for dp in data_points[-7:])
    older_sum = sum(dp.critical + dp.high for dp in data_points[-14:-7])

    if recent_sum > older_sum * 1.1:
        trend_direction = "up"
    elif recent_sum < older_sum * 0.9:
        trend_direction = "down"
    else:
        trend_direction = "stable"

    return TrendsResponse(
        data=data_points,
        period_start=start_date.isoformat(),
        period_end=end_date.isoformat(),
        total_findings=total_findings,
        trend_direction=trend_direction,
    )


# ============================================================================
# Export Router
# ============================================================================

red_team_router = router
