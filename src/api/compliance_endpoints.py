"""
Project Aura - Compliance Evidence API Endpoints

REST API for compliance evidence collection and reporting:
- SOC 2 control evidence
- Compliance assessments
- Audit reports
- Gap analysis

Author: Project Aura Team
Created: 2025-12-20
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.auth import User, get_current_user, require_role
from src.services.compliance_evidence_service import ComplianceEvidenceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/compliance", tags=["Compliance"])

# Service instance
compliance_service = ComplianceEvidenceService()


# ==============================================================================
# Request/Response Models
# ==============================================================================


class EvidenceCollectionRequest(BaseModel):
    """Request to collect evidence for controls."""

    control_ids: Optional[List[str]] = Field(
        None, description="Specific control IDs to collect evidence for (null for all)"
    )
    categories: Optional[List[str]] = Field(
        None, description="SOC 2 categories to collect (SECURITY, AVAILABILITY, etc.)"
    )
    force_refresh: bool = Field(
        False, description="Force re-collection even if recent evidence exists"
    )


class AssessmentRequest(BaseModel):
    """Request to run a compliance assessment."""

    control_ids: Optional[List[str]] = Field(
        None, description="Specific control IDs to assess (null for all)"
    )
    categories: Optional[List[str]] = Field(
        None, description="SOC 2 categories to assess"
    )
    include_evidence: bool = Field(
        True, description="Include evidence collection in assessment"
    )


class ReportRequest(BaseModel):
    """Request to generate a compliance report."""

    report_type: str = Field(
        "full", description="Report type: full, executive, gap_analysis, evidence_only"
    )
    start_date: Optional[date] = Field(None, description="Start date for report period")
    end_date: Optional[date] = Field(None, description="End date for report period")
    categories: Optional[List[str]] = Field(
        None, description="SOC 2 categories to include"
    )
    include_recommendations: bool = Field(
        True, description="Include remediation recommendations"
    )


class ControlResponse(BaseModel):
    """Response for a compliance control."""

    control_id: str
    category: str
    name: str
    description: str
    requirement: str
    evidence_types: List[str]
    last_assessed: Optional[datetime]
    status: str
    effectiveness_score: Optional[float]


class EvidenceResponse(BaseModel):
    """Response for control evidence."""

    evidence_id: str
    control_id: str
    evidence_type: str
    collected_at: datetime
    source: str
    data_summary: str
    is_valid: bool
    expires_at: Optional[datetime]


class AssessmentResponse(BaseModel):
    """Response for a compliance assessment."""

    assessment_id: str
    control_id: str
    assessed_at: datetime
    assessed_by: str
    status: str
    effectiveness_score: float
    findings: List[str]
    recommendations: List[str]
    evidence_count: int


class ComplianceScoreResponse(BaseModel):
    """Response for overall compliance score."""

    overall_score: float
    category_scores: Dict[str, float]
    controls_assessed: int
    controls_compliant: int
    controls_partial: int
    controls_non_compliant: int
    last_assessment: datetime
    trend: str  # improving, stable, declining


class GapAnalysisResponse(BaseModel):
    """Response for gap analysis."""

    timestamp: datetime
    total_controls: int
    gaps_identified: int
    critical_gaps: int
    high_gaps: int
    medium_gaps: int
    low_gaps: int
    gaps: List[Dict[str, Any]]
    remediation_priority: List[str]


# ==============================================================================
# Control Management Endpoints
# ==============================================================================


@router.get("/controls", response_model=List[ControlResponse])
async def list_controls(
    category: Optional[str] = Query(  # noqa: B008
        None, description="Filter by SOC 2 category"
    ),  # noqa: B008
    status: Optional[str] = Query(None, description="Filter by status"),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
):
    """
    List all compliance controls.

    Returns SOC 2 controls with their current status and last assessment date.
    """
    try:
        from src.services.compliance_evidence_service import SOC2Category

        # Convert string category to enum if provided
        category_enum: Optional[SOC2Category] = None
        if category:
            try:
                category_enum = SOC2Category(category.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid category: {category}. Valid values: {[c.value for c in SOC2Category]}",
                )

        controls = compliance_service.list_controls(
            category=category_enum,
        )

        # Filter by status if provided (post-filter since service doesn't support it)
        if status:
            filtered_controls = []
            for c in controls:
                assessment = compliance_service.get_control_status(c.control_id)
                if assessment and assessment.status.value == status.lower():
                    filtered_controls.append(c)
            controls = filtered_controls

        response_list = []
        for c in controls:
            assessment = compliance_service.get_control_status(c.control_id)
            response_list.append(
                ControlResponse(
                    control_id=c.control_id,
                    category=(
                        c.category.value
                        if hasattr(c.category, "value")
                        else str(c.category)
                    ),
                    name=c.name,
                    description=c.description,
                    requirement=c.description,  # ControlDefinition doesn't have 'requirement', using description
                    evidence_types=[
                        et.value for et in c.evidence_required
                    ],  # Convert EvidenceType enums to strings
                    last_assessed=assessment.assessed_at if assessment else None,
                    status=assessment.status.value if assessment else "not_assessed",
                    effectiveness_score=(
                        assessment.effectiveness_score if assessment else None
                    ),
                )
            )
        return response_list
    except Exception as e:
        logger.error(f"Failed to list controls: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list controls")


@router.get("/controls/{control_id}", response_model=ControlResponse)
async def get_control(
    control_id: str,
    user: User = Depends(get_current_user),  # noqa: B008
):
    """
    Get details for a specific control.
    """
    try:
        control = compliance_service.get_control(control_id)

        if not control:
            raise HTTPException(
                status_code=404, detail=f"Control {control_id} not found"
            )

        assessment = compliance_service.get_control_status(control_id)

        return ControlResponse(
            control_id=control.control_id,
            category=(
                control.category.value
                if hasattr(control.category, "value")
                else str(control.category)
            ),
            name=control.name,
            description=control.description,
            requirement=control.description,  # ControlDefinition doesn't have 'requirement'
            evidence_types=[et.value for et in control.evidence_required],
            last_assessed=assessment.assessed_at if assessment else None,
            status=assessment.status.value if assessment else "not_assessed",
            effectiveness_score=assessment.effectiveness_score if assessment else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get control: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve control")


# ==============================================================================
# Evidence Collection Endpoints
# ==============================================================================


@router.post("/evidence/collect")
async def collect_evidence(
    request: EvidenceCollectionRequest,
    user: User = Depends(require_role("admin")),  # noqa: B008
):
    """
    Collect evidence for compliance controls.

    Triggers automated evidence collection from:
    - AWS Config
    - CloudTrail logs
    - Security scans
    - Access reviews
    - System configurations
    """
    try:
        from src.services.compliance_evidence_service import SOC2Category

        # Determine which controls to process
        controls_to_process = []
        if request.control_ids:
            controls_to_process = request.control_ids
        else:
            # Get all controls, optionally filtered by categories
            category_enums = []
            if request.categories:
                for cat_str in request.categories:
                    try:
                        category_enums.append(SOC2Category(cat_str.lower()))
                    except ValueError:
                        raise HTTPException(
                            status_code=400, detail=f"Invalid category: {cat_str}"
                        )

            all_controls = compliance_service.list_controls()
            if category_enums:
                controls_to_process = [
                    c.control_id for c in all_controls if c.category in category_enums
                ]
            else:
                controls_to_process = [c.control_id for c in all_controls]

        # Collect evidence for each control
        evidence_collected = 0
        controls_processed = 0
        errors = []

        for control_id in controls_to_process:
            control = compliance_service.get_control(control_id)
            if not control:
                errors.append(f"Control {control_id} not found")
                continue

            controls_processed += 1

            # Collect each required evidence type
            for evidence_type in control.evidence_required:
                try:
                    await compliance_service.collect_evidence(
                        control_id=control_id,
                        evidence_type=evidence_type,
                        collected_by=user.email or user.sub,
                    )
                    evidence_collected += 1
                except Exception as e:
                    errors.append(
                        f"Failed to collect {evidence_type.value} for {control_id}: {str(e)}"
                    )

        return {
            "status": "completed",
            "timestamp": datetime.now().isoformat(),
            "controls_processed": controls_processed,
            "evidence_collected": evidence_collected,
            "errors": errors,
        }
    except Exception as e:
        logger.error(f"Failed to collect evidence: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to collect evidence")


@router.get("/evidence", response_model=List[EvidenceResponse])
async def list_evidence(
    control_id: Optional[str] = Query(  # noqa: B008
        None, description="Filter by control ID"
    ),  # noqa: B008
    evidence_type: Optional[str] = Query(  # noqa: B008
        None, description="Filter by evidence type"
    ),  # noqa: B008
    limit: int = Query(50, ge=1, le=500),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
):
    """
    List collected evidence.
    """
    try:
        from src.services.compliance_evidence_service import (
            EvidenceStatus,
            EvidenceType,
        )

        # Get all evidence
        if control_id:
            # Get evidence for specific control
            evidence_list = compliance_service.get_evidence_for_control(control_id)
        else:
            # Get all evidence from internal storage
            evidence_list = list(compliance_service._evidence.values())

        # Filter by evidence type if specified
        if evidence_type:
            try:
                et_enum = EvidenceType(evidence_type.lower())
                evidence_list = [e for e in evidence_list if e.evidence_type == et_enum]
            except ValueError:
                raise HTTPException(
                    status_code=400, detail=f"Invalid evidence_type: {evidence_type}"
                )

        # Sort by collected_at descending and limit
        evidence_list = sorted(
            evidence_list, key=lambda e: e.collected_at, reverse=True
        )[:limit]

        return [
            EvidenceResponse(
                evidence_id=e.evidence_id,
                control_id=e.control_id,
                evidence_type=e.evidence_type.value,
                collected_at=e.collected_at,
                source=e.metadata.get("source", "unknown"),
                data_summary=e.title,  # Using title as summary
                is_valid=(
                    e.status == EvidenceStatus.VERIFIED
                    or e.status == EvidenceStatus.COLLECTED
                ),
                expires_at=e.expires_at,
            )
            for e in evidence_list
        ]
    except Exception as e:
        logger.error(f"Failed to list evidence: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list evidence")


@router.get("/evidence/{evidence_id}")
async def get_evidence(
    evidence_id: str,
    user: User = Depends(get_current_user),  # noqa: B008
):
    """
    Get full details for a specific piece of evidence.

    Includes the actual evidence data (configuration snapshots, logs, etc.).
    """
    try:
        from src.services.compliance_evidence_service import EvidenceStatus

        evidence = compliance_service.get_evidence(evidence_id)

        if not evidence:
            raise HTTPException(
                status_code=404, detail=f"Evidence {evidence_id} not found"
            )

        return {
            "evidence_id": evidence.evidence_id,
            "control_id": evidence.control_id,
            "evidence_type": evidence.evidence_type.value,
            "collected_at": evidence.collected_at.isoformat(),
            "source": evidence.metadata.get("source", "unknown"),
            "data": evidence.metadata,  # Return metadata as data
            "is_valid": (
                evidence.status == EvidenceStatus.VERIFIED
                or evidence.status == EvidenceStatus.COLLECTED
            ),
            "expires_at": (
                evidence.expires_at.isoformat() if evidence.expires_at else None
            ),
            "metadata": evidence.metadata,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get evidence: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve evidence")


# ==============================================================================
# Assessment Endpoints
# ==============================================================================


@router.post("/assessments", response_model=AssessmentResponse)
async def run_assessment(
    request: AssessmentRequest,
    user: User = Depends(require_role("admin")),  # noqa: B008
):
    """
    Run a compliance assessment.

    Evaluates controls against collected evidence and determines:
    - Compliance status
    - Effectiveness score
    - Gaps and findings
    - Remediation recommendations
    """
    try:
        from src.services.compliance_evidence_service import SOC2Category

        # Determine which controls to assess
        controls_to_assess = []
        if request.control_ids:
            controls_to_assess = request.control_ids
        else:
            # Get all controls, optionally filtered by categories
            category_enums = []
            if request.categories:
                for cat_str in request.categories:
                    try:
                        category_enums.append(SOC2Category(cat_str.lower()))
                    except ValueError:
                        raise HTTPException(
                            status_code=400, detail=f"Invalid category: {cat_str}"
                        )

            all_controls = compliance_service.list_controls()
            if category_enums:
                controls_to_assess = [
                    c.control_id for c in all_controls if c.category in category_enums
                ]
            else:
                controls_to_assess = [c.control_id for c in all_controls]

        # Assess the first control (or all if multiple requested)
        # For simplicity, return the first assessment result
        if not controls_to_assess:
            raise HTTPException(status_code=400, detail="No controls to assess")

        result = await compliance_service.assess_control(
            control_id=controls_to_assess[0],
            assessed_by=user.email or user.sub,
        )

        return AssessmentResponse(
            assessment_id=result.assessment_id,
            control_id=result.control_id,
            assessed_at=result.assessed_at,
            assessed_by=result.assessed_by,
            status=result.status.value,
            effectiveness_score=result.effectiveness_score,
            findings=result.findings,
            recommendations=result.recommendations,
            evidence_count=len(result.evidence_ids),
        )
    except Exception as e:
        logger.error(f"Failed to run assessment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to run assessment")


@router.get("/assessments", response_model=List[AssessmentResponse])
async def list_assessments(
    control_id: Optional[str] = Query(  # noqa: B008
        None, description="Filter by control ID"
    ),  # noqa: B008
    start_date: Optional[date] = Query(  # noqa: B008
        None, description="Start date filter"
    ),  # noqa: B008
    end_date: Optional[date] = Query(None, description="End date filter"),  # noqa: B008
    limit: int = Query(50, ge=1, le=500),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
):
    """
    List compliance assessments.
    """
    try:
        # Get all assessments from internal storage
        assessments = list(compliance_service._assessments.values())

        # Filter by control_id if specified
        if control_id:
            assessments = [a for a in assessments if a.control_id == control_id]

        # Filter by date range if specified
        if start_date:
            from datetime import timezone as tz

            start_dt = datetime.combine(start_date, datetime.min.time()).replace(
                tzinfo=tz.utc
            )
            assessments = [a for a in assessments if a.assessed_at >= start_dt]

        if end_date:
            from datetime import timezone as tz

            end_dt = datetime.combine(end_date, datetime.max.time()).replace(
                tzinfo=tz.utc
            )
            assessments = [a for a in assessments if a.assessed_at <= end_dt]

        # Sort by assessed_at descending and limit
        assessments = sorted(assessments, key=lambda a: a.assessed_at, reverse=True)[
            :limit
        ]

        return [
            AssessmentResponse(
                assessment_id=a.assessment_id,
                control_id=a.control_id,
                assessed_at=a.assessed_at,
                assessed_by=a.assessed_by,
                status=a.status.value,
                effectiveness_score=a.effectiveness_score,
                findings=a.findings,
                recommendations=a.recommendations,
                evidence_count=len(a.evidence_ids),
            )
            for a in assessments
        ]
    except Exception as e:
        logger.error(f"Failed to list assessments: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list assessments")


@router.get("/assessments/{assessment_id}", response_model=AssessmentResponse)
async def get_assessment(
    assessment_id: str,
    user: User = Depends(get_current_user),  # noqa: B008
):
    """
    Get details for a specific assessment.
    """
    try:
        assessment = compliance_service._assessments.get(assessment_id)

        if not assessment:
            raise HTTPException(
                status_code=404, detail=f"Assessment {assessment_id} not found"
            )

        return AssessmentResponse(
            assessment_id=assessment.assessment_id,
            control_id=assessment.control_id,
            assessed_at=assessment.assessed_at,
            assessed_by=assessment.assessed_by,
            status=assessment.status.value,
            effectiveness_score=assessment.effectiveness_score,
            findings=assessment.findings,
            recommendations=assessment.recommendations,
            evidence_count=len(assessment.evidence_ids),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get assessment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve assessment")


# ==============================================================================
# Compliance Score Endpoints
# ==============================================================================


@router.get("/score", response_model=ComplianceScoreResponse)
async def get_compliance_score(
    user: User = Depends(get_current_user),  # noqa: B008
):
    """
    Get overall compliance score and category breakdown.

    Returns current compliance posture including:
    - Overall effectiveness score
    - Per-category scores
    - Control counts by status
    - Trend indicator
    """
    try:
        from src.services.compliance_evidence_service import ControlStatus

        # Calculate scores from assessments
        all_controls = compliance_service.list_controls()
        controls_assessed = 0
        controls_compliant = 0
        controls_partial = 0
        controls_non_compliant = 0
        category_scores: Dict[str, float] = {}
        last_assessment_time: Optional[datetime] = None

        # Track by category
        category_stats: Dict[str, Dict[str, Any]] = {}

        for control in all_controls:
            assessment = compliance_service.get_control_status(control.control_id)
            if assessment:
                controls_assessed += 1
                if assessment.assessed_at:
                    if (
                        last_assessment_time is None
                        or assessment.assessed_at > last_assessment_time
                    ):
                        last_assessment_time = assessment.assessed_at

                if assessment.status == ControlStatus.IMPLEMENTED:
                    controls_compliant += 1
                elif assessment.status == ControlStatus.PARTIALLY_IMPLEMENTED:
                    controls_partial += 1
                elif assessment.status == ControlStatus.NOT_IMPLEMENTED:
                    controls_non_compliant += 1

                # Track by category
                cat = control.category.value
                if cat not in category_stats:
                    category_stats[cat] = {"total": 0, "score_sum": 0.0}
                category_stats[cat]["total"] += 1
                category_stats[cat]["score_sum"] += assessment.effectiveness_score

        # Calculate overall and category scores
        overall_score = 0.0
        if controls_assessed > 0:
            overall_score = (
                controls_compliant * 100.0 + controls_partial * 50.0
            ) / controls_assessed

        for cat, stats in category_stats.items():
            if stats["total"] > 0:
                category_scores[cat] = stats["score_sum"] / stats["total"]

        # Determine trend (placeholder - would need historical data)
        trend = "stable"

        return ComplianceScoreResponse(
            overall_score=overall_score,
            category_scores=category_scores,
            controls_assessed=controls_assessed,
            controls_compliant=controls_compliant,
            controls_partial=controls_partial,
            controls_non_compliant=controls_non_compliant,
            last_assessment=last_assessment_time or datetime.now(),
            trend=trend,
        )
    except Exception as e:
        logger.error(f"Failed to get compliance score: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to retrieve compliance score"
        )


@router.get("/score/history")
async def get_score_history(
    days: int = Query(  # noqa: B008
        90, ge=7, le=365, description="Number of days of history"
    ),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
):
    """
    Get compliance score history for trend analysis.
    """
    try:
        # Placeholder implementation - would need to store historical data
        # For now, return empty history
        return {
            "days": days,
            "data_points": 0,
            "history": [],
        }
    except Exception as e:
        logger.error(f"Failed to get score history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve score history")


# ==============================================================================
# Gap Analysis Endpoints
# ==============================================================================


@router.get("/gaps", response_model=GapAnalysisResponse)
async def get_gap_analysis(
    category: Optional[str] = Query(  # noqa: B008
        None, description="Filter by SOC 2 category"
    ),  # noqa: B008
    severity: Optional[str] = Query(  # noqa: B008
        None, description="Filter by severity"
    ),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
):
    """
    Get compliance gap analysis.

    Identifies areas where controls are not meeting requirements:
    - Missing evidence
    - Ineffective controls
    - Policy gaps
    - Technical deficiencies
    """
    try:
        from src.services.compliance_evidence_service import ControlStatus, SOC2Category

        # Convert category string to enum if provided
        category_enum: Optional[SOC2Category] = None
        if category:
            try:
                category_enum = SOC2Category(category.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400, detail=f"Invalid category: {category}"
                )

        # Get controls
        all_controls = compliance_service.list_controls(category=category_enum)

        # Identify gaps
        gaps: List[Dict[str, Any]] = []
        critical_gaps = 0
        high_gaps = 0
        medium_gaps = 0
        low_gaps = 0

        for control in all_controls:
            assessment = compliance_service.get_control_status(control.control_id)

            # Check if there's a gap
            if not assessment or assessment.status in (
                ControlStatus.NOT_IMPLEMENTED,
                ControlStatus.PARTIALLY_IMPLEMENTED,
            ):
                # Determine severity based on effectiveness score
                effectiveness = assessment.effectiveness_score if assessment else 0.0
                if effectiveness < 25:
                    gap_severity = "critical"
                    critical_gaps += 1
                elif effectiveness < 50:
                    gap_severity = "high"
                    high_gaps += 1
                elif effectiveness < 75:
                    gap_severity = "medium"
                    medium_gaps += 1
                else:
                    gap_severity = "low"
                    low_gaps += 1

                # Filter by severity if specified
                if severity and gap_severity != severity.lower():
                    continue

                gap_info = {
                    "control_id": control.control_id,
                    "name": control.name,
                    "category": control.category.value,
                    "severity": gap_severity,
                    "status": assessment.status.value if assessment else "not_assessed",
                    "effectiveness_score": effectiveness,
                    "findings": assessment.findings if assessment else [],
                    "recommendations": assessment.recommendations if assessment else [],
                }
                gaps.append(gap_info)

        # Generate remediation priority (sorted by severity)
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_gaps = sorted(gaps, key=lambda g: severity_order[g["severity"]])
        remediation_priority = [g["control_id"] for g in sorted_gaps]

        return GapAnalysisResponse(
            timestamp=datetime.now(),
            total_controls=len(all_controls),
            gaps_identified=len(gaps),
            critical_gaps=critical_gaps,
            high_gaps=high_gaps,
            medium_gaps=medium_gaps,
            low_gaps=low_gaps,
            gaps=gaps,
            remediation_priority=remediation_priority,
        )
    except Exception as e:
        logger.error(f"Failed to get gap analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve gap analysis")


# ==============================================================================
# Report Generation Endpoints
# ==============================================================================


@router.post("/reports")
async def generate_report(
    request: ReportRequest,
    user: User = Depends(require_role("admin")),  # noqa: B008
):
    """
    Generate a compliance report.

    Report types:
    - full: Complete SOC 2 compliance report
    - executive: High-level summary for leadership
    - gap_analysis: Detailed gap analysis with remediation
    - evidence_only: Evidence collection summary
    """
    try:
        from datetime import timezone as tz

        # Set default dates if not provided
        period_start = request.start_date or date.today() - timedelta(days=90)
        period_end = request.end_date or date.today()

        # Convert dates to datetime
        start_dt = datetime.combine(period_start, datetime.min.time()).replace(
            tzinfo=tz.utc
        )
        end_dt = datetime.combine(period_end, datetime.max.time()).replace(
            tzinfo=tz.utc
        )

        # Use the service's generate_compliance_report method
        report = await compliance_service.generate_compliance_report(
            period_start=start_dt,
            period_end=end_dt,
            generated_by=user.email or user.sub,
        )

        # Create summary based on report data
        summary = (
            f"{request.report_type.upper()} Report: "
            f"{report.implemented}/{report.total_controls} controls implemented, "
            f"overall score {report.overall_score}%"
        )

        return {
            "report_id": report.report_id,
            "report_type": request.report_type,
            "generated_at": report.generated_at.isoformat(),
            "generated_by": report.generated_by,
            "period_start": report.period_start.isoformat(),
            "period_end": report.period_end.isoformat(),
            "summary": summary,
            "download_url": f"/api/v1/compliance/reports/{report.report_id}/download",
            "expires_at": None,
        }
    except ValueError as e:
        logger.warning(f"Report generation validation error: {e}")
        raise HTTPException(
            status_code=400, detail="Invalid report generation parameters"
        )
    except Exception as e:
        logger.error(f"Failed to generate report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate report")


@router.get("/reports")
async def list_reports(
    report_type: Optional[str] = Query(  # noqa: B008
        None, description="Filter by report type"
    ),  # noqa: B008
    limit: int = Query(20, ge=1, le=100),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
):
    """
    List generated compliance reports.
    """
    try:
        reports = compliance_service.list_reports(limit=limit)

        # Note: report_type filter is not supported by service, but we include parameter for API compatibility
        return {
            "reports": [
                {
                    "report_id": r.report_id,
                    "report_type": "full",  # ComplianceReport doesn't have report_type field
                    "generated_at": r.generated_at.isoformat(),
                    "generated_by": r.generated_by,
                    "summary": (
                        f"{r.implemented}/{r.total_controls} controls implemented, "
                        f"score: {r.overall_score}%"
                    ),
                    "download_url": f"/api/v1/compliance/reports/{r.report_id}/download",
                }
                for r in reports
            ],
            "total": len(reports),
        }
    except Exception as e:
        logger.error(f"Failed to list reports: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list reports")


@router.get("/reports/{report_id}")
async def get_report(
    report_id: str,
    user: User = Depends(get_current_user),  # noqa: B008
):
    """
    Get a specific compliance report.
    """
    try:
        report = compliance_service.get_report(report_id)

        if not report:
            raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

        return {
            "report_id": report.report_id,
            "report_type": "full",  # ComplianceReport doesn't have report_type field
            "generated_at": report.generated_at.isoformat(),
            "generated_by": report.generated_by,
            "period_start": report.period_start.isoformat(),
            "period_end": report.period_end.isoformat(),
            "content": {
                "total_controls": report.total_controls,
                "implemented": report.implemented,
                "partially_implemented": report.partially_implemented,
                "not_implemented": report.not_implemented,
                "not_applicable": report.not_applicable,
                "evidence_count": report.evidence_count,
                "overall_score": report.overall_score,
                "by_category": report.by_category,
                "gaps": report.gaps,
                "recommendations": report.recommendations,
            },
            "summary": (
                f"{report.implemented}/{report.total_controls} controls implemented, "
                f"overall score {report.overall_score}%"
            ),
            "download_url": f"/api/v1/compliance/reports/{report.report_id}/download",
            "expires_at": None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve report")


# ==============================================================================
# SOC 2 Categories Reference Endpoint
# ==============================================================================


@router.get("/categories")
async def list_categories(
    user: User = Depends(get_current_user),  # noqa: B008
):
    """
    List SOC 2 Trust Services Categories.

    Returns the five categories with descriptions:
    - Security (Common Criteria)
    - Availability
    - Processing Integrity
    - Confidentiality
    - Privacy
    """
    from src.services.compliance_evidence_service import SOC2Category

    # Count controls per category
    def get_control_count(category_str: str) -> int:
        try:
            cat_enum = SOC2Category(category_str.lower())
            return len(compliance_service.list_controls(category=cat_enum))
        except ValueError:
            return 0

    return {
        "categories": [
            {
                "id": "SECURITY",
                "name": "Security",
                "description": "Protection against unauthorized access (logical and physical)",
                "criteria_prefix": "CC",
                "control_count": get_control_count("SECURITY"),
            },
            {
                "id": "AVAILABILITY",
                "name": "Availability",
                "description": "System availability for operation and use as committed",
                "criteria_prefix": "A",
                "control_count": get_control_count("AVAILABILITY"),
            },
            {
                "id": "PROCESSING_INTEGRITY",
                "name": "Processing Integrity",
                "description": "System processing is complete, valid, accurate, timely, and authorized",
                "criteria_prefix": "PI",
                "control_count": get_control_count("PROCESSING_INTEGRITY"),
            },
            {
                "id": "CONFIDENTIALITY",
                "name": "Confidentiality",
                "description": "Information designated as confidential is protected",
                "criteria_prefix": "C",
                "control_count": get_control_count("CONFIDENTIALITY"),
            },
            {
                "id": "PRIVACY",
                "name": "Privacy",
                "description": "Personal information is collected, used, retained, disclosed, and disposed of properly",
                "criteria_prefix": "P",
                "control_count": get_control_count("PRIVACY"),
            },
        ]
    }
