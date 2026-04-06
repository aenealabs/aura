"""
Explainability Dashboard API Endpoints.

REST API endpoints for the Universal Explainability Framework (ADR-068),
providing access to decision records, reasoning chains, contradictions,
and dashboard statistics.

Endpoints:
- GET  /api/v1/explainability/decisions           - Get decision records
- GET  /api/v1/explainability/decisions/:id       - Get single decision detail
- GET  /api/v1/explainability/contradictions      - Get contradiction alerts
- POST /api/v1/explainability/contradictions/:id/resolve - Resolve contradiction
- POST /api/v1/explainability/contradictions/:id/dismiss - Dismiss contradiction
- GET  /api/v1/explainability/stats               - Get dashboard statistics
"""

import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from src.api.auth import User, get_current_user
from src.services.api_rate_limiter import RateLimitResult, standard_rate_limit
from src.api.log_sanitizer import sanitize_log

logger = logging.getLogger(__name__)

# =============================================================================
# Router Configuration
# =============================================================================

router = APIRouter(prefix="/api/v1/explainability", tags=["Explainability"])

# =============================================================================
# Response/Request Models
# =============================================================================


class ReasoningStep(BaseModel):
    """Single step in a reasoning chain."""

    step: int
    description: str
    confidence: float
    evidenceSources: list[str]


class ConfidenceData(BaseModel):
    """Confidence interval data."""

    pointEstimate: float
    lowerBound: float
    upperBound: float
    uncertaintySources: list[str]


class Alternative(BaseModel):
    """Alternative considered in decision."""

    id: str
    description: str
    score: float
    chosen: bool
    pros: list[str]
    cons: list[str]
    rejectionReason: Optional[str] = None


class DecisionResponse(BaseModel):
    """Response model for a decision record."""

    id: str
    timestamp: str
    agentId: str
    type: str
    title: str
    description: str
    output: str
    confidence: float
    confidenceData: ConfidenceData
    reasoningChain: list[ReasoningStep]
    alternatives: list[Alternative]
    selectedAlternativeIndex: int
    criteria: list[str]
    rationale: str
    severity: str
    status: str


class DecisionListResponse(BaseModel):
    """Response model for paginated decision list."""

    decisions: list[DecisionResponse]
    totalCount: int
    limit: int
    offset: int
    hasMore: bool


class ContradictionResponse(BaseModel):
    """Response model for a contradiction alert."""

    id: str
    detectedAt: str
    decisionId: str
    agentId: str
    severity: str
    status: str
    title: str
    description: str
    reasoningStatement: str
    actualAction: str
    discrepancyScore: float
    suggestedResolution: str
    affectedCode: str
    resolvedAt: Optional[str] = None
    resolvedBy: Optional[str] = None
    resolution: Optional[str] = None
    dismissedAt: Optional[str] = None
    dismissalReason: Optional[str] = None


class ResolveContradictionRequest(BaseModel):
    """Request model for resolving a contradiction."""

    resolution: str = Field(..., min_length=10, description="Resolution description")


class DismissContradictionRequest(BaseModel):
    """Request model for dismissing a contradiction."""

    reason: str = Field(..., min_length=10, description="Dismissal reason")


class StatsResponse(BaseModel):
    """Response model for dashboard statistics."""

    totalDecisions: int
    avgConfidence: float
    activeContradictions: int
    resolvedToday: int
    decisionsByAgent: dict[str, int]
    confidenceDistribution: dict[str, int]
    contradictionsByStatus: dict[str, int]


# =============================================================================
# Mock Data Generation
# =============================================================================


def _generate_reasoning_chain(decision_type: str) -> list[dict[str, Any]]:
    """Generate mock reasoning chain for a decision type."""
    chains = {
        "code_generation": [
            {
                "step": 1,
                "description": "Analyzed user request for new feature implementation",
                "confidence": 0.95,
                "evidenceSources": ["user_input", "context_window"],
            },
            {
                "step": 2,
                "description": "Retrieved relevant code patterns from knowledge graph",
                "confidence": 0.88,
                "evidenceSources": ["knowledge_graph", "codebase_search"],
            },
            {
                "step": 3,
                "description": "Evaluated 3 implementation approaches against best practices",
                "confidence": 0.82,
                "evidenceSources": ["design_patterns", "security_guidelines"],
            },
            {
                "step": 4,
                "description": "Selected approach balancing performance and maintainability",
                "confidence": 0.85,
                "evidenceSources": ["tradeoff_analysis"],
            },
            {
                "step": 5,
                "description": "Generated code with inline documentation",
                "confidence": 0.91,
                "evidenceSources": ["template_library", "coding_standards"],
            },
        ],
        "security_review": [
            {
                "step": 1,
                "description": "Scanned code for OWASP Top 10 vulnerabilities",
                "confidence": 0.97,
                "evidenceSources": ["semgrep", "security_rules"],
            },
            {
                "step": 2,
                "description": "Analyzed data flow for potential injection points",
                "confidence": 0.92,
                "evidenceSources": ["dataflow_analysis", "taint_tracking"],
            },
            {
                "step": 3,
                "description": "Verified authentication and authorization patterns",
                "confidence": 0.89,
                "evidenceSources": ["auth_patterns", "rbac_config"],
            },
            {
                "step": 4,
                "description": "Assessed cryptographic usage and key management",
                "confidence": 0.94,
                "evidenceSources": ["crypto_best_practices"],
            },
        ],
        "deployment": [
            {
                "step": 1,
                "description": "Validated deployment manifest against environment constraints",
                "confidence": 0.96,
                "evidenceSources": ["kubernetes_schema", "env_config"],
            },
            {
                "step": 2,
                "description": "Checked resource limits and scaling parameters",
                "confidence": 0.91,
                "evidenceSources": ["capacity_planning", "historical_usage"],
            },
            {
                "step": 3,
                "description": "Verified rollback strategy and health checks",
                "confidence": 0.88,
                "evidenceSources": ["deployment_standards", "runbook"],
            },
        ],
    }
    return chains.get(decision_type, chains["code_generation"])


def _generate_alternatives(decision_type: str) -> list[dict[str, Any]]:
    """Generate mock alternatives for a decision type."""
    alternatives = {
        "code_generation": [
            {
                "id": "alt-1",
                "description": "Factory pattern with dependency injection",
                "score": 0.85,
                "chosen": True,
                "pros": ["Testability", "Loose coupling", "Easy to extend"],
                "cons": ["Slightly more complex", "More boilerplate"],
            },
            {
                "id": "alt-2",
                "description": "Direct instantiation with configuration",
                "score": 0.72,
                "chosen": False,
                "pros": ["Simpler initial implementation", "Less code"],
                "cons": ["Harder to test", "Tight coupling"],
                "rejectionReason": "Lower testability score",
            },
            {
                "id": "alt-3",
                "description": "Service locator pattern",
                "score": 0.68,
                "chosen": False,
                "pros": ["Flexible", "Runtime configuration"],
                "cons": ["Hidden dependencies", "Anti-pattern concerns"],
                "rejectionReason": "Generally considered an anti-pattern",
            },
        ],
        "security_review": [
            {
                "id": "alt-1",
                "description": "Allow with additional input validation",
                "score": 0.89,
                "chosen": True,
                "pros": ["Addresses security concern", "Minimal code changes"],
                "cons": ["Adds slight latency"],
            },
            {
                "id": "alt-2",
                "description": "Block until code is refactored",
                "score": 0.75,
                "chosen": False,
                "pros": ["Maximum security"],
                "cons": ["Blocks deployment", "Longer timeline"],
                "rejectionReason": "Risk can be mitigated with validation",
            },
        ],
        "deployment": [
            {
                "id": "alt-1",
                "description": "Rolling update with 25% max unavailable",
                "score": 0.91,
                "chosen": True,
                "pros": ["Zero downtime", "Gradual rollout", "Easy rollback"],
                "cons": ["Slower deployment", "Requires spare capacity"],
            },
            {
                "id": "alt-2",
                "description": "Blue-green deployment",
                "score": 0.82,
                "chosen": False,
                "pros": ["Instant rollback", "Full testing before switch"],
                "cons": ["Requires 2x resources temporarily"],
                "rejectionReason": "Resource constraints in current cluster",
            },
        ],
    }
    return alternatives.get(decision_type, alternatives["code_generation"])


# In-memory storage for decisions and contradictions
_decisions: list[dict[str, Any]] = []
_contradictions: list[dict[str, Any]] = []


def _initialize_mock_data():
    """Initialize mock data if not already done."""
    global _decisions, _contradictions

    if _decisions:
        return

    # Generate decisions
    decision_types = [
        ("code_generation", "Generated", "CoderAgent"),
        ("security_review", "Security review:", "ReviewerAgent"),
        ("deployment", "Validated", "ValidatorAgent"),
        ("security_patch", "Applied", "PatcherAgent"),
    ]

    titles = [
        "authentication middleware",
        "SQL injection risk",
        "production deployment manifest",
        "pagination utility",
        "CVE-2024-1234 remediation",
        "API rate limiting",
        "user input validation",
        "database connection pooling",
        "cache invalidation logic",
        "error boundary component",
    ]

    for i in range(10):
        dt = decision_types[i % len(decision_types)]
        title = f"{dt[1]} {titles[i]}"
        decision_type = dt[0]
        agent = dt[2]

        hours_ago = i * 2 + random.randint(0, 3)
        timestamp = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        confidence = round(random.uniform(0.78, 0.98), 2)

        _decisions.append(
            {
                "id": f"dec-{i + 1:03d}",
                "timestamp": timestamp.isoformat(),
                "agentId": agent,
                "type": decision_type,
                "title": title,
                "description": f"Detailed description for {title}",
                "output": f"Generated output for {title}...",
                "confidence": confidence,
                "confidenceData": {
                    "pointEstimate": confidence,
                    "lowerBound": round(confidence - 0.09, 2),
                    "upperBound": round(min(confidence + 0.07, 0.99), 2),
                    "uncertaintySources": [
                        "limited_training_examples",
                        "ambiguous_requirements",
                    ][: random.randint(0, 2)],
                },
                "reasoningChain": _generate_reasoning_chain(decision_type),
                "alternatives": _generate_alternatives(decision_type),
                "selectedAlternativeIndex": 0,
                "criteria": [
                    "testability",
                    "maintainability",
                    "performance",
                    "security",
                ][: random.randint(2, 4)],
                "rationale": f"Selected approach for optimal balance in {title}",
                "severity": ["low", "medium", "high", "critical"][i % 4],
                "status": "completed",
            }
        )

    # Generate contradictions
    _contradictions = [
        {
            "id": "cont-001",
            "detectedAt": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            "decisionId": "dec-011",
            "agentId": "CoderAgent",
            "severity": "medium",
            "status": "active",
            "title": "Reasoning-Action Mismatch: Error Handling",
            "description": 'Agent stated "comprehensive error handling required" but generated code lacks try-catch blocks',
            "reasoningStatement": "Comprehensive error handling is required for production robustness",
            "actualAction": "Generated function without error handling constructs",
            "discrepancyScore": 0.72,
            "suggestedResolution": "Add try-catch blocks with appropriate error propagation",
            "affectedCode": "src/services/user-service.ts:45-67",
        },
        {
            "id": "cont-002",
            "detectedAt": (datetime.now(timezone.utc) - timedelta(hours=8)).isoformat(),
            "decisionId": "dec-012",
            "agentId": "ReviewerAgent",
            "severity": "low",
            "status": "active",
            "title": "Inconsistent Security Assessment",
            "description": "Stated input validation was sufficient but later flagged same pattern as risky",
            "reasoningStatement": "Current input validation covers OWASP Top 10 requirements",
            "actualAction": "Flagged similar pattern as potential XSS vector in subsequent review",
            "discrepancyScore": 0.45,
            "suggestedResolution": "Clarify security assessment criteria for consistent evaluation",
            "affectedCode": "src/api/endpoints.py:123-145",
        },
        {
            "id": "cont-003",
            "detectedAt": (
                datetime.now(timezone.utc) - timedelta(hours=24)
            ).isoformat(),
            "decisionId": "dec-013",
            "agentId": "ValidatorAgent",
            "severity": "high",
            "status": "resolved",
            "title": "Critical: Deployment Strategy Contradiction",
            "description": "Approved blue-green but reasoning favored rolling update",
            "reasoningStatement": "Rolling update recommended for this service profile",
            "actualAction": "Approved blue-green deployment configuration",
            "discrepancyScore": 0.85,
            "suggestedResolution": "Review deployment decision with correct strategy",
            "affectedCode": "deploy/k8s/production.yaml",
            "resolvedAt": (
                datetime.now(timezone.utc) - timedelta(hours=20)
            ).isoformat(),
            "resolvedBy": "devops@aenealabs.com",
            "resolution": "Corrected to rolling update strategy as per reasoning",
        },
    ]


# Initialize mock data
_initialize_mock_data()

# =============================================================================
# Endpoints
# =============================================================================


@router.get("/decisions", response_model=DecisionListResponse)
async def get_decisions(
    agents: Optional[str] = Query(
        default=None,
        description="Comma-separated agent IDs to filter by",
    ),
    severities: Optional[str] = Query(
        default=None,
        description="Comma-separated severities to filter by",
    ),
    time_range: str = Query(
        default="7d",
        description="Time range: 24h, 7d, or 30d",
    ),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum results"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    user: User = Depends(get_current_user),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
) -> DecisionListResponse:
    """
    Get decision records with optional filtering.

    Returns paginated list of AI decision records with their
    reasoning chains and alternatives considered.

    Requires authentication.
    """
    logger.debug(f"User {user.email} requesting decisions")

    # Apply filters
    filtered = _decisions.copy()

    if agents:
        agent_list = [a.strip() for a in agents.split(",")]
        filtered = [d for d in filtered if d["agentId"] in agent_list]

    if severities:
        severity_list = [s.strip() for s in severities.split(",")]
        filtered = [d for d in filtered if d["severity"] in severity_list]

    # Time range filtering would apply here in production
    # For mock data, we skip this

    total_count = len(filtered)
    paginated = filtered[offset : offset + limit]
    has_more = offset + limit < total_count

    return DecisionListResponse(
        decisions=[
            DecisionResponse(
                id=d["id"],
                timestamp=d["timestamp"],
                agentId=d["agentId"],
                type=d["type"],
                title=d["title"],
                description=d["description"],
                output=d["output"],
                confidence=d["confidence"],
                confidenceData=ConfidenceData(**d["confidenceData"]),
                reasoningChain=[ReasoningStep(**s) for s in d["reasoningChain"]],
                alternatives=[Alternative(**a) for a in d["alternatives"]],
                selectedAlternativeIndex=d["selectedAlternativeIndex"],
                criteria=d["criteria"],
                rationale=d["rationale"],
                severity=d["severity"],
                status=d["status"],
            )
            for d in paginated
        ],
        totalCount=total_count,
        limit=limit,
        offset=offset,
        hasMore=has_more,
    )


@router.get("/decisions/{decision_id}", response_model=DecisionResponse)
async def get_decision_detail(
    decision_id: str = Path(..., description="Decision ID"),
    user: User = Depends(get_current_user),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
) -> DecisionResponse:
    """
    Get detailed decision by ID.

    Returns full decision record with complete reasoning chain
    and alternatives comparison.

    Requires authentication.
    """
    logger.debug(f"User {sanitize_log(user.email)} requesting decision {sanitize_log(decision_id)}")

    decision = next((d for d in _decisions if d["id"] == decision_id), None)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    return DecisionResponse(
        id=decision["id"],
        timestamp=decision["timestamp"],
        agentId=decision["agentId"],
        type=decision["type"],
        title=decision["title"],
        description=decision["description"],
        output=decision["output"],
        confidence=decision["confidence"],
        confidenceData=ConfidenceData(**decision["confidenceData"]),
        reasoningChain=[ReasoningStep(**s) for s in decision["reasoningChain"]],
        alternatives=[Alternative(**a) for a in decision["alternatives"]],
        selectedAlternativeIndex=decision["selectedAlternativeIndex"],
        criteria=decision["criteria"],
        rationale=decision["rationale"],
        severity=decision["severity"],
        status=decision["status"],
    )


@router.get("/contradictions", response_model=list[ContradictionResponse])
async def get_contradictions(
    include_resolved: bool = Query(
        default=False,
        description="Include resolved contradictions",
    ),
    user: User = Depends(get_current_user),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
) -> list[ContradictionResponse]:
    """
    Get contradiction alerts.

    Returns list of detected reasoning-action mismatches.

    Requires authentication.
    """
    logger.debug(f"User {user.email} requesting contradictions")

    filtered = (
        _contradictions
        if include_resolved
        else [c for c in _contradictions if c["status"] == "active"]
    )

    return [
        ContradictionResponse(
            id=c["id"],
            detectedAt=c["detectedAt"],
            decisionId=c["decisionId"],
            agentId=c["agentId"],
            severity=c["severity"],
            status=c["status"],
            title=c["title"],
            description=c["description"],
            reasoningStatement=c["reasoningStatement"],
            actualAction=c["actualAction"],
            discrepancyScore=c["discrepancyScore"],
            suggestedResolution=c["suggestedResolution"],
            affectedCode=c["affectedCode"],
            resolvedAt=c.get("resolvedAt"),
            resolvedBy=c.get("resolvedBy"),
            resolution=c.get("resolution"),
            dismissedAt=c.get("dismissedAt"),
            dismissalReason=c.get("dismissalReason"),
        )
        for c in filtered
    ]


@router.post(
    "/contradictions/{contradiction_id}/resolve",
    response_model=ContradictionResponse,
)
async def resolve_contradiction(
    contradiction_id: str = Path(..., description="Contradiction ID"),
    request: ResolveContradictionRequest = ...,
    user: User = Depends(get_current_user),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
) -> ContradictionResponse:
    """
    Resolve a contradiction.

    Marks the contradiction as resolved with the provided resolution.

    Requires authentication.
    """
    logger.info(f"User {sanitize_log(user.email)} resolving contradiction {sanitize_log(contradiction_id)}")

    contradiction = next(
        (c for c in _contradictions if c["id"] == contradiction_id), None
    )
    if not contradiction:
        raise HTTPException(status_code=404, detail="Contradiction not found")

    if contradiction["status"] != "active":
        raise HTTPException(
            status_code=400, detail="Contradiction is not in active status"
        )

    # Update contradiction
    contradiction["status"] = "resolved"
    contradiction["resolvedAt"] = datetime.now(timezone.utc).isoformat()
    contradiction["resolvedBy"] = user.email
    contradiction["resolution"] = request.resolution

    return ContradictionResponse(
        id=contradiction["id"],
        detectedAt=contradiction["detectedAt"],
        decisionId=contradiction["decisionId"],
        agentId=contradiction["agentId"],
        severity=contradiction["severity"],
        status=contradiction["status"],
        title=contradiction["title"],
        description=contradiction["description"],
        reasoningStatement=contradiction["reasoningStatement"],
        actualAction=contradiction["actualAction"],
        discrepancyScore=contradiction["discrepancyScore"],
        suggestedResolution=contradiction["suggestedResolution"],
        affectedCode=contradiction["affectedCode"],
        resolvedAt=contradiction["resolvedAt"],
        resolvedBy=contradiction["resolvedBy"],
        resolution=contradiction["resolution"],
    )


@router.post(
    "/contradictions/{contradiction_id}/dismiss",
    response_model=ContradictionResponse,
)
async def dismiss_contradiction(
    contradiction_id: str = Path(..., description="Contradiction ID"),
    request: DismissContradictionRequest = ...,
    user: User = Depends(get_current_user),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
) -> ContradictionResponse:
    """
    Dismiss a contradiction as false positive.

    Marks the contradiction as dismissed with the provided reason.

    Requires authentication.
    """
    logger.info(f"User {sanitize_log(user.email)} dismissing contradiction {sanitize_log(contradiction_id)}")

    contradiction = next(
        (c for c in _contradictions if c["id"] == contradiction_id), None
    )
    if not contradiction:
        raise HTTPException(status_code=404, detail="Contradiction not found")

    if contradiction["status"] != "active":
        raise HTTPException(
            status_code=400, detail="Contradiction is not in active status"
        )

    # Update contradiction
    contradiction["status"] = "dismissed"
    contradiction["dismissedAt"] = datetime.now(timezone.utc).isoformat()
    contradiction["dismissalReason"] = request.reason

    return ContradictionResponse(
        id=contradiction["id"],
        detectedAt=contradiction["detectedAt"],
        decisionId=contradiction["decisionId"],
        agentId=contradiction["agentId"],
        severity=contradiction["severity"],
        status=contradiction["status"],
        title=contradiction["title"],
        description=contradiction["description"],
        reasoningStatement=contradiction["reasoningStatement"],
        actualAction=contradiction["actualAction"],
        discrepancyScore=contradiction["discrepancyScore"],
        suggestedResolution=contradiction["suggestedResolution"],
        affectedCode=contradiction["affectedCode"],
        dismissedAt=contradiction["dismissedAt"],
        dismissalReason=contradiction["dismissalReason"],
    )


@router.get("/stats", response_model=StatsResponse)
async def get_explainability_stats(
    user: User = Depends(get_current_user),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
) -> StatsResponse:
    """
    Get dashboard statistics.

    Returns aggregate statistics for the explainability dashboard.

    Requires authentication.
    """
    logger.debug(f"User {user.email} requesting explainability stats")

    # Calculate stats from mock data
    total_decisions = len(_decisions) * 125  # Scale up for realism
    active_contradictions = len([c for c in _contradictions if c["status"] == "active"])
    resolved_contradictions = len(
        [c for c in _contradictions if c["status"] == "resolved"]
    )
    dismissed_contradictions = len(
        [c for c in _contradictions if c["status"] == "dismissed"]
    )

    # Calculate average confidence
    avg_confidence = (
        sum(d["confidence"] for d in _decisions) / len(_decisions)
        if _decisions
        else 0.85
    )

    # Count by agent
    by_agent = {}
    for d in _decisions:
        agent = d["agentId"]
        by_agent[agent] = by_agent.get(agent, 0) + 125  # Scale up

    # Confidence distribution
    high_conf = len([d for d in _decisions if d["confidence"] >= 0.85]) * 125
    med_conf = len([d for d in _decisions if 0.70 <= d["confidence"] < 0.85]) * 125
    low_conf = len([d for d in _decisions if d["confidence"] < 0.70]) * 125

    return StatsResponse(
        totalDecisions=total_decisions,
        avgConfidence=round(avg_confidence, 2),
        activeContradictions=active_contradictions,
        resolvedToday=5,  # Mock value
        decisionsByAgent=by_agent,
        confidenceDistribution={
            "high": high_conf,
            "medium": med_conf,
            "low": low_conf,
        },
        contradictionsByStatus={
            "active": active_contradictions,
            "resolved": resolved_contradictions,
            "dismissed": dismissed_contradictions,
        },
    )


@router.get("/health")
async def explainability_health() -> dict[str, str]:
    """Health check for Explainability API."""
    return {
        "status": "healthy",
        "service": "explainability",
        "decisions_count": str(len(_decisions)),
        "contradictions_count": str(len(_contradictions)),
    }
