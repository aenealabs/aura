"""
Guardrails Configuration API Endpoints.

REST API endpoints for the Guardrail Settings page (ADR-069), providing
configuration management, activity metrics, and compliance profile handling.

Endpoints:
- GET  /api/v1/guardrails/config       - Get current configuration
- PUT  /api/v1/guardrails/config       - Update configuration
- POST /api/v1/guardrails/config/reset - Reset to defaults
- GET  /api/v1/guardrails/metrics      - Get activity metrics
- POST /api/v1/guardrails/impact       - Get impact preview
- GET  /api/v1/guardrails/profiles     - List compliance profiles
- GET  /api/v1/guardrails/history      - Get change history
"""

import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.auth import User, get_current_user
from src.api.log_sanitizer import sanitize_log
from src.services.api_rate_limiter import RateLimitResult, standard_rate_limit

logger = logging.getLogger(__name__)

# =============================================================================
# Router Configuration
# =============================================================================

router = APIRouter(prefix="/api/v1/guardrails", tags=["Guardrails"])

# =============================================================================
# Response/Request Models
# =============================================================================


class AdvancedSettings(BaseModel):
    """Advanced guardrail settings."""

    hitlSensitivity: int = Field(1, ge=0, le=3, description="HITL sensitivity level")
    trustLevel: str = Field("medium", description="Context trust level")
    verbosity: str = Field("standard", description="Explanation verbosity")
    reviewerType: str = Field("team_lead", description="Reviewer assignment type")
    enableAnomalyAlerts: bool = Field(True, description="Enable anomaly detection")
    auditAllDecisions: bool = Field(False, description="Audit all decisions")
    enableContradictionDetection: bool = Field(
        True, description="Enable contradiction detection"
    )


class GuardrailConfigResponse(BaseModel):
    """Response model for guardrail configuration."""

    profile: str = Field(..., description="Security profile ID")
    complianceProfile: Optional[str] = Field(None, description="Compliance profile ID")
    advanced: AdvancedSettings = Field(..., description="Advanced settings")
    version: int = Field(1, description="Configuration version")
    lastModifiedBy: Optional[str] = Field(None, description="Last modifier")
    lastModifiedAt: Optional[str] = Field(None, description="Last modification time")


class GuardrailConfigUpdateRequest(BaseModel):
    """Request model for updating configuration."""

    profile: str = Field(..., description="Security profile ID")
    complianceProfile: Optional[str] = Field(None, description="Compliance profile ID")
    advanced: AdvancedSettings = Field(..., description="Advanced settings")
    justification: str = Field("", description="Change justification")


class ResetRequest(BaseModel):
    """Request model for reset."""

    justification: str = Field("Reset to defaults", description="Reset justification")


class AgentMetrics(BaseModel):
    """Metrics for a single agent."""

    decisions: int
    hitl: int
    avgLatency: int


class ActivityMetricsResponse(BaseModel):
    """Response model for activity metrics."""

    totalDecisions: int
    autoApproved: int
    hitlRequired: int
    hitlApproved: int
    hitlRejected: int
    avgResponseTimeMs: int
    anomaliesDetected: int
    contradictionsFound: int
    byAgent: dict[str, AgentMetrics]
    timeSeriesData: list[dict[str, Any]]


class ImpactMetric(BaseModel):
    """Single impact metric projection."""

    label: str
    before: float
    after: float
    inverted: bool = False
    format: Optional[str] = None


class ImpactWarning(BaseModel):
    """Impact warning message."""

    severity: str
    title: str
    message: str


class ImpactPreviewResponse(BaseModel):
    """Response model for impact preview."""

    metrics: list[ImpactMetric]
    warnings: list[ImpactWarning]


class ComplianceProfileResponse(BaseModel):
    """Response model for compliance profile."""

    id: str
    name: str
    description: str
    lockedSettings: list[str]


class ChangeHistoryRecord(BaseModel):
    """Single change history record."""

    id: str
    timestamp: str
    userId: str
    settingPath: str
    previousValue: Any
    newValue: Any
    justification: str
    changeType: str = "update"


# =============================================================================
# In-memory storage (replaced by DynamoDB in production)
# =============================================================================

_current_config: dict[str, Any] = {
    "profile": "balanced",
    "complianceProfile": None,
    "advanced": {
        "hitlSensitivity": 1,
        "trustLevel": "medium",
        "verbosity": "standard",
        "reviewerType": "team_lead",
        "enableAnomalyAlerts": True,
        "auditAllDecisions": False,
        "enableContradictionDetection": True,
    },
    "version": 3,
    "lastModifiedBy": "admin@aenealabs.com",
    "lastModifiedAt": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
}

_change_history: list[dict[str, Any]] = [
    {
        "id": "chg-001",
        "timestamp": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
        "userId": "admin@aenealabs.com",
        "settingPath": "profile",
        "previousValue": "conservative",
        "newValue": "balanced",
        "justification": "Reducing HITL friction after initial deployment stabilization",
        "changeType": "update",
    },
    {
        "id": "chg-002",
        "timestamp": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
        "userId": "security@aenealabs.com",
        "settingPath": "enableAnomalyAlerts",
        "previousValue": False,
        "newValue": True,
        "justification": "Enabling anomaly detection per security team recommendation",
        "changeType": "update",
    },
    {
        "id": "chg-003",
        "timestamp": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
        "userId": "admin@aenealabs.com",
        "settingPath": "*",
        "previousValue": None,
        "newValue": "initial",
        "justification": "Initial configuration",
        "changeType": "create",
    },
]


def _generate_metrics(time_range: str) -> dict[str, Any]:
    """Generate realistic metrics for the given time range."""
    multipliers = {"24h": 1, "7d": 7, "30d": 30}
    mult = multipliers.get(time_range, 7)

    # Base daily metrics
    daily_decisions = 167
    daily_hitl = 5
    daily_approved = 4
    daily_rejected = 1

    total_decisions = daily_decisions * mult
    hitl_required = daily_hitl * mult
    hitl_approved = daily_approved * mult
    hitl_rejected = daily_rejected * mult
    auto_approved = total_decisions - hitl_required

    # Generate time series
    time_series = []
    if time_range == "24h":
        for hour in range(24):
            time_series.append(
                {
                    "label": f"{hour:02d}:00",
                    "decisions": random.randint(3, 15),
                    "hitl": random.randint(0, 2),
                }
            )
    elif time_range == "7d":
        base_date = datetime.now(timezone.utc) - timedelta(days=6)
        for day in range(7):
            current_date = base_date + timedelta(days=day)
            time_series.append(
                {
                    "label": current_date.strftime("%Y-%m-%d"),
                    "decisions": random.randint(150, 210),
                    "hitl": random.randint(5, 15),
                }
            )
    else:  # 30d
        base_date = datetime.now(timezone.utc) - timedelta(days=29)
        for week in range(5):
            time_series.append(
                {
                    "label": f"Week {week + 1}",
                    "decisions": random.randint(1000, 1300),
                    "hitl": random.randint(50, 70),
                }
            )

    return {
        "totalDecisions": total_decisions,
        "autoApproved": auto_approved,
        "hitlRequired": hitl_required,
        "hitlApproved": hitl_approved,
        "hitlRejected": hitl_rejected,
        "avgResponseTimeMs": random.randint(280, 380),
        "anomaliesDetected": random.randint(0, 3) * mult // 7,
        "contradictionsFound": random.randint(0, 2) * mult // 7,
        "byAgent": {
            "CoderAgent": AgentMetrics(
                decisions=int(total_decisions * 0.42),
                hitl=int(hitl_required * 0.31),
                avgLatency=random.randint(290, 340),
            ).model_dump(),
            "ReviewerAgent": AgentMetrics(
                decisions=int(total_decisions * 0.24),
                hitl=int(hitl_required * 0.26),
                avgLatency=random.randint(250, 300),
            ).model_dump(),
            "ValidatorAgent": AgentMetrics(
                decisions=int(total_decisions * 0.20),
                hitl=int(hitl_required * 0.21),
                avgLatency=random.randint(180, 220),
            ).model_dump(),
            "PatcherAgent": AgentMetrics(
                decisions=int(total_decisions * 0.14),
                hitl=int(hitl_required * 0.22),
                avgLatency=random.randint(400, 480),
            ).model_dump(),
        },
        "timeSeriesData": time_series,
    }


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/config", response_model=GuardrailConfigResponse)
async def get_guardrail_config(
    user: User = Depends(get_current_user),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
) -> GuardrailConfigResponse:
    """
    Get current guardrail configuration.

    Returns the active configuration including security profile,
    compliance profile, and advanced settings.

    Requires authentication.
    """
    logger.info(f"User {user.email} requesting guardrail config")

    return GuardrailConfigResponse(
        profile=_current_config["profile"],
        complianceProfile=_current_config["complianceProfile"],
        advanced=AdvancedSettings(**_current_config["advanced"]),
        version=_current_config["version"],
        lastModifiedBy=_current_config["lastModifiedBy"],
        lastModifiedAt=_current_config["lastModifiedAt"],
    )


@router.put("/config", response_model=GuardrailConfigResponse)
async def update_guardrail_config(
    request: GuardrailConfigUpdateRequest,
    user: User = Depends(get_current_user),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
) -> GuardrailConfigResponse:
    """
    Update guardrail configuration.

    Validates and applies the new configuration. Records change
    in audit history with justification.

    Requires authentication.
    """
    global _current_config, _change_history  # noqa: F824

    logger.info(f"User {user.email} updating guardrail config")

    # Record changes
    old_profile = _current_config["profile"]
    new_profile = request.profile

    if old_profile != new_profile:
        change_id = f"chg-{len(_change_history) + 1:03d}"
        _change_history.insert(
            0,
            {
                "id": change_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "userId": user.email,
                "settingPath": "profile",
                "previousValue": old_profile,
                "newValue": new_profile,
                "justification": request.justification or "Configuration update",
                "changeType": "update",
            },
        )

    # Update configuration
    _current_config = {
        "profile": request.profile,
        "complianceProfile": request.complianceProfile,
        "advanced": request.advanced.model_dump(),
        "version": _current_config["version"] + 1,
        "lastModifiedBy": user.email,
        "lastModifiedAt": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(
        f"Guardrail config updated by {sanitize_log(user.email)} (version {sanitize_log(_current_config['version'])})"
    )

    return GuardrailConfigResponse(
        profile=_current_config["profile"],
        complianceProfile=_current_config["complianceProfile"],
        advanced=AdvancedSettings(**_current_config["advanced"]),
        version=_current_config["version"],
        lastModifiedBy=_current_config["lastModifiedBy"],
        lastModifiedAt=_current_config["lastModifiedAt"],
    )


@router.post("/config/reset", response_model=GuardrailConfigResponse)
async def reset_guardrail_config(
    request: ResetRequest,
    user: User = Depends(get_current_user),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
) -> GuardrailConfigResponse:
    """
    Reset configuration to defaults.

    Requires authentication.
    """
    global _current_config, _change_history  # noqa: F824

    logger.info(f"User {user.email} resetting guardrail config to defaults")

    # Record reset
    change_id = f"chg-{len(_change_history) + 1:03d}"
    _change_history.insert(
        0,
        {
            "id": change_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "userId": user.email,
            "settingPath": "*",
            "previousValue": _current_config.copy(),
            "newValue": "defaults",
            "justification": request.justification,
            "changeType": "reset",
        },
    )

    # Reset to defaults
    _current_config = {
        "profile": "balanced",
        "complianceProfile": None,
        "advanced": {
            "hitlSensitivity": 1,
            "trustLevel": "medium",
            "verbosity": "standard",
            "reviewerType": "team_lead",
            "enableAnomalyAlerts": True,
            "auditAllDecisions": False,
            "enableContradictionDetection": True,
        },
        "version": _current_config["version"] + 1,
        "lastModifiedBy": user.email,
        "lastModifiedAt": datetime.now(timezone.utc).isoformat(),
    }

    return GuardrailConfigResponse(
        profile=_current_config["profile"],
        complianceProfile=_current_config["complianceProfile"],
        advanced=AdvancedSettings(**_current_config["advanced"]),
        version=_current_config["version"],
        lastModifiedBy=_current_config["lastModifiedBy"],
        lastModifiedAt=_current_config["lastModifiedAt"],
    )


@router.get("/metrics", response_model=ActivityMetricsResponse)
async def get_guardrail_metrics(
    time_range: str = Query(
        default="7d",
        description="Time range: 24h, 7d, or 30d",
    ),
    user: User = Depends(get_current_user),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
) -> ActivityMetricsResponse:
    """
    Get guardrail activity metrics.

    Returns decision counts, HITL statistics, and per-agent breakdowns
    for the specified time range.

    Requires authentication.
    """
    logger.debug(
        f"User {sanitize_log(user.email)} requesting metrics (time_range={sanitize_log(time_range)})"
    )

    # Validate time range
    valid_ranges = ["24h", "7d", "30d"]
    if time_range not in valid_ranges:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid time_range. Must be one of: {valid_ranges}",
        )

    metrics = _generate_metrics(time_range)

    return ActivityMetricsResponse(
        totalDecisions=metrics["totalDecisions"],
        autoApproved=metrics["autoApproved"],
        hitlRequired=metrics["hitlRequired"],
        hitlApproved=metrics["hitlApproved"],
        hitlRejected=metrics["hitlRejected"],
        avgResponseTimeMs=metrics["avgResponseTimeMs"],
        anomaliesDetected=metrics["anomaliesDetected"],
        contradictionsFound=metrics["contradictionsFound"],
        byAgent=metrics["byAgent"],
        timeSeriesData=metrics["timeSeriesData"],
    )


@router.post("/impact", response_model=ImpactPreviewResponse)
async def get_impact_preview(
    proposed_changes: GuardrailConfigUpdateRequest,
    user: User = Depends(get_current_user),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
) -> ImpactPreviewResponse:
    """
    Get impact preview for proposed changes.

    Returns projected metrics changes and any warnings about
    the proposed configuration.

    Requires authentication.
    """
    logger.info(f"User {user.email} requesting impact preview")

    # Calculate impact based on profile changes
    current_profile = _current_config["profile"]
    new_profile = proposed_changes.profile

    # Profile impact factors
    profile_factors = {
        "conservative": {"hitl_mult": 2.0, "auto_mult": 0.7, "latency_mult": 1.5},
        "balanced": {"hitl_mult": 1.0, "auto_mult": 1.0, "latency_mult": 1.0},
        "efficient": {"hitl_mult": 0.5, "auto_mult": 1.2, "latency_mult": 0.8},
        "aggressive": {"hitl_mult": 0.2, "auto_mult": 1.4, "latency_mult": 0.6},
    }

    current_factors = profile_factors.get(current_profile, profile_factors["balanced"])
    new_factors = profile_factors.get(new_profile, profile_factors["balanced"])

    base_hitl = 12
    base_auto = 847
    base_latency = 2.3

    metrics = [
        ImpactMetric(
            label="Daily HITL prompts",
            before=round(base_hitl * current_factors["hitl_mult"]),
            after=round(base_hitl * new_factors["hitl_mult"]),
            inverted=True,
        ),
        ImpactMetric(
            label="Auto-approved operations",
            before=round(base_auto * current_factors["auto_mult"]),
            after=round(base_auto * new_factors["auto_mult"]),
        ),
        ImpactMetric(
            label="Quarantined items",
            before=3,
            after=3 + (2 if new_profile in ["efficient", "aggressive"] else 0),
        ),
        ImpactMetric(
            label="Avg decision latency",
            before=round(base_latency * current_factors["latency_mult"], 1),
            after=round(base_latency * new_factors["latency_mult"], 1),
            inverted=True,
            format="time",
        ),
    ]

    # Generate warnings
    warnings = []
    if new_profile == "aggressive":
        warnings.append(
            ImpactWarning(
                severity="warning",
                title="Reduced oversight",
                message="Aggressive mode significantly reduces human oversight. "
                "Ensure this aligns with your compliance requirements.",
            )
        )

    if proposed_changes.complianceProfile and new_profile in [
        "efficient",
        "aggressive",
    ]:
        warnings.append(
            ImpactWarning(
                severity="critical",
                title="Compliance conflict",
                message=f"The {new_profile} profile may conflict with "
                f"{proposed_changes.complianceProfile} compliance requirements.",
            )
        )

    return ImpactPreviewResponse(metrics=metrics, warnings=warnings)


@router.get("/profiles", response_model=list[ComplianceProfileResponse])
async def get_compliance_profiles(
    user: User = Depends(get_current_user),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
) -> list[ComplianceProfileResponse]:
    """
    Get available compliance profiles.

    Returns the list of compliance profiles with their locked settings.

    Requires authentication.
    """
    logger.debug(f"User {user.email} requesting compliance profiles")

    profiles = [
        ComplianceProfileResponse(
            id="cmmc_l2",
            name="CMMC Level 2",
            description="Cybersecurity Maturity Model Certification Level 2 requirements",
            lockedSettings=["auditAllDecisions"],
        ),
        ComplianceProfileResponse(
            id="cmmc_l3",
            name="CMMC Level 3",
            description="Cybersecurity Maturity Model Certification Level 3 requirements",
            lockedSettings=["auditAllDecisions", "enableContradictionDetection"],
        ),
        ComplianceProfileResponse(
            id="fedramp_high",
            name="FedRAMP High",
            description="Federal Risk and Authorization Management Program High baseline",
            lockedSettings=["hitlSensitivity", "trustLevel", "auditAllDecisions"],
        ),
        ComplianceProfileResponse(
            id="sox",
            name="SOX Compliance",
            description="Sarbanes-Oxley Act compliance requirements",
            lockedSettings=["auditAllDecisions"],
        ),
        ComplianceProfileResponse(
            id="hipaa",
            name="HIPAA",
            description="Health Insurance Portability and Accountability Act requirements",
            lockedSettings=["auditAllDecisions", "enableAnomalyAlerts"],
        ),
    ]

    return profiles


@router.get("/history", response_model=list[ChangeHistoryRecord])
async def get_change_history(
    limit: int = Query(default=100, ge=1, le=500, description="Maximum records"),
    user: User = Depends(get_current_user),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
) -> list[ChangeHistoryRecord]:
    """
    Get configuration change history.

    Returns the audit trail of configuration changes.

    Requires authentication.
    """
    logger.debug(f"User {user.email} requesting change history")

    return [
        ChangeHistoryRecord(
            id=record["id"],
            timestamp=record["timestamp"],
            userId=record["userId"],
            settingPath=record["settingPath"],
            previousValue=record["previousValue"],
            newValue=record["newValue"],
            justification=record["justification"],
            changeType=record.get("changeType", "update"),
        )
        for record in _change_history[:limit]
    ]


@router.get("/health")
async def guardrails_health() -> dict[str, str]:
    """Health check for Guardrails API."""
    return {
        "status": "healthy",
        "service": "guardrails",
        "config_version": str(_current_config.get("version", 0)),
    }
