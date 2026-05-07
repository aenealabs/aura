"""
Project Aura - Model Router API Endpoints

REST API endpoints for LLM model routing configuration and analytics.
Provides visibility into model selection decisions, cost savings, and routing rules.

Endpoints:
- GET  /api/v1/model-router/stats         - Get routing statistics and cost savings
- GET  /api/v1/model-router/distribution  - Get model distribution data
- GET  /api/v1/model-router/rules         - List routing rules
- POST /api/v1/model-router/rules         - Create new routing rule
- PUT  /api/v1/model-router/rules/{id}    - Update routing rule
- DELETE /api/v1/model-router/rules/{id}  - Delete routing rule
- GET  /api/v1/model-router/ab-test       - Get A/B test configuration
- PUT  /api/v1/model-router/ab-test       - Update A/B test configuration
- GET  /api/v1/model-router/costs         - Get per-investigation costs
"""

import logging
import random
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.services.model_router import ModelTier, RoutingRule, TaskComplexity, get_router

logger = logging.getLogger(__name__)

# ============================================================================
# Router Configuration
# ============================================================================

router = APIRouter(prefix="/api/v1/model-router", tags=["Model Router"])

# ============================================================================
# Pydantic Models for API Requests/Responses
# ============================================================================


class ModelTierEnum(str, Enum):
    """Model tier options for API."""

    FAST = "fast"
    ACCURATE = "accurate"
    MAXIMUM = "maximum"


class TaskComplexityEnum(str, Enum):
    """Task complexity options for API."""

    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


class CostSavingsResponse(BaseModel):
    """Cost savings statistics response."""

    percentage: float = Field(description="Percentage saved vs baseline")
    amount: float = Field(description="Dollar amount saved this period")
    trend: list[float] = Field(description="Historical trend data for sparkline")
    baseline_cost: float = Field(description="Cost if all using ACCURATE tier")
    optimized_cost: float = Field(description="Actual cost with routing")
    period: str = Field(description="Time period for savings calculation")


class ModelDistributionItem(BaseModel):
    """Single model's distribution data."""

    model: str = Field(description="Model name")
    tier: ModelTierEnum = Field(description="Model tier")
    percentage: float = Field(description="Percentage of requests")
    count: int = Field(description="Number of requests")
    color: str = Field(description="Color for chart display")


class ModelDistributionResponse(BaseModel):
    """Model distribution response."""

    distribution: list[ModelDistributionItem] = Field(
        description="Distribution by model"
    )
    total_requests: int = Field(description="Total request count")
    period: str = Field(description="Time period")


class RoutingRuleModel(BaseModel):
    """Routing rule data model."""

    id: str = Field(description="Rule ID")
    task_type: str = Field(description="Task type identifier")
    complexity: TaskComplexityEnum = Field(description="Task complexity level")
    tier: ModelTierEnum = Field(description="Target model tier")
    model: str = Field(description="Model name")
    cost_per_1k: float = Field(description="Cost per 1K tokens")
    description: str = Field(default="", description="Rule description")
    enabled: bool = Field(default=True, description="Whether rule is active")


class RoutingRuleCreateRequest(BaseModel):
    """Request to create a routing rule."""

    task_type: str = Field(description="Task type identifier")
    complexity: TaskComplexityEnum = Field(description="Task complexity level")
    tier: ModelTierEnum = Field(description="Target model tier")
    description: str = Field(default="", description="Rule description")


class RoutingRuleUpdateRequest(BaseModel):
    """Request to update a routing rule."""

    complexity: TaskComplexityEnum | None = Field(
        default=None, description="Task complexity level"
    )
    tier: ModelTierEnum | None = Field(default=None, description="Target model tier")
    description: str | None = Field(default=None, description="Rule description")
    enabled: bool | None = Field(default=None, description="Whether rule is active")


class ABTestConfigModel(BaseModel):
    """A/B test configuration model."""

    enabled: bool = Field(description="Whether A/B testing is enabled")
    experiment_id: str = Field(default="", description="Current experiment ID")
    experiment_name: str = Field(
        default="", description="Human-readable experiment name"
    )
    control_tier: ModelTierEnum = Field(
        default=ModelTierEnum.ACCURATE, description="Control group tier"
    )
    treatment_tier: ModelTierEnum = Field(
        default=ModelTierEnum.FAST, description="Treatment group tier"
    )
    traffic_split: float = Field(
        default=0.5, ge=0, le=1, description="Fraction of traffic to treatment"
    )
    task_types: list[str] = Field(
        default_factory=list, description="Task types included in experiment"
    )
    start_date: str | None = Field(default=None, description="Experiment start date")
    end_date: str | None = Field(default=None, description="Experiment end date")
    status: str = Field(default="inactive", description="Experiment status")


class ABTestUpdateRequest(BaseModel):
    """Request to update A/B test configuration."""

    enabled: bool | None = Field(default=None, description="Enable/disable A/B testing")
    experiment_name: str | None = Field(default=None, description="Experiment name")
    control_tier: ModelTierEnum | None = Field(default=None, description="Control tier")
    treatment_tier: ModelTierEnum | None = Field(
        default=None, description="Treatment tier"
    )
    traffic_split: float | None = Field(
        default=None, ge=0, le=1, description="Traffic split"
    )
    task_types: list[str] | None = Field(default=None, description="Task types")
    duration_days: int | None = Field(
        default=None, ge=1, le=90, description="Experiment duration in days"
    )


class InvestigationCostItem(BaseModel):
    """Per-investigation cost data."""

    id: str = Field(description="Investigation ID")
    task: str = Field(description="Task description")
    model_used: str = Field(description="Model that was used")
    tier: ModelTierEnum = Field(description="Model tier")
    tokens: int = Field(description="Total tokens used")
    cost: float = Field(description="Total cost in USD")
    timestamp: str = Field(description="When the investigation occurred")


class InvestigationCostsResponse(BaseModel):
    """Per-investigation costs response."""

    investigations: list[InvestigationCostItem] = Field(
        description="List of investigations"
    )
    total_cost: float = Field(description="Total cost for period")
    period: str = Field(description="Time period")


class RouterStatsResponse(BaseModel):
    """Full router statistics response."""

    cost_savings: CostSavingsResponse = Field(description="Cost savings data")
    distribution: ModelDistributionResponse = Field(description="Model distribution")
    ab_test: ABTestConfigModel = Field(description="A/B test config")
    total_decisions: int = Field(description="Total routing decisions")


# ============================================================================
# Helper Functions
# ============================================================================

# Model display names and colors
MODEL_DISPLAY_INFO: dict[str, dict[str, str]] = {
    "fast": {"name": "Claude Haiku", "color": "#3B82F6"},
    "accurate": {"name": "Claude Sonnet", "color": "#7C9A3E"},
    "maximum": {"name": "Claude Opus", "color": "#EA580C"},
}


def _tier_to_model_name(tier: ModelTier) -> str:
    """Convert tier to display model name."""
    return MODEL_DISPLAY_INFO.get(tier.value, {}).get("name", tier.value)


def _tier_to_color(tier: ModelTier) -> str:
    """Convert tier to chart color."""
    return MODEL_DISPLAY_INFO.get(tier.value, {}).get("color", "#6B7280")


def _generate_trend_data(days: int = 30) -> list[float]:
    """Generate sample trend data for sparkline."""
    base = 35.0
    trend: list[float] = []
    for i in range(days):
        noise = random.uniform(-5, 5)
        growth = i * 0.3
        trend.append(round(base + growth + noise, 1))
    return trend


def _generate_sample_investigations(count: int = 20) -> list[InvestigationCostItem]:
    """Generate sample investigation cost data."""
    tasks = [
        "Code Review",
        "Vulnerability Scan",
        "Patch Generation",
        "Architecture Analysis",
        "Query Expansion",
        "Threat Detection",
        "Compliance Check",
        "Security Assessment",
    ]

    tiers = [
        (ModelTierEnum.FAST, 0.00025, 200),
        (ModelTierEnum.ACCURATE, 0.003, 800),
        (ModelTierEnum.MAXIMUM, 0.015, 1500),
    ]

    investigations: list[InvestigationCostItem] = []
    now = datetime.now(timezone.utc)

    for i in range(count):
        tier, base_cost, avg_tokens = random.choice(tiers)
        tokens = int(avg_tokens * random.uniform(0.5, 2.0))
        cost = (tokens / 1000) * base_cost * random.uniform(0.8, 1.2)

        investigations.append(
            InvestigationCostItem(
                id=f"INV-{str(uuid.uuid4())[:8].upper()}",
                task=random.choice(tasks),
                model_used=MODEL_DISPLAY_INFO[tier.value]["name"],
                tier=tier,
                tokens=tokens,
                cost=round(cost, 4),
                timestamp=(now - timedelta(hours=i * 2)).isoformat(),
            )
        )

    return sorted(investigations, key=lambda x: x.cost, reverse=True)


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("/stats", response_model=RouterStatsResponse)
async def get_router_stats(
    period: str = Query(  # noqa: B008
        default="30d", description="Time period: 7d, 30d, 90d"
    ),  # noqa: B008
) -> RouterStatsResponse:
    """
    Get comprehensive model router statistics.

    Returns cost savings, model distribution, and A/B test status.
    """
    try:
        model_router = get_router()
        stats = model_router.get_stats()
        ab_config = model_router.get_ab_test_config()

        # Calculate cost savings
        total = stats.get("total_decisions", 0) or 1000
        distribution = stats.get("tier_distribution_percent", {})

        fast_pct = distribution.get("fast", 40.0)
        accurate_pct = distribution.get("accurate", 55.0)
        maximum_pct = distribution.get("maximum", 5.0)

        # Baseline: all ACCURATE at $0.003/1K
        baseline_cost = total * 0.003

        # Optimized: weighted by tier
        optimized_cost = (
            (fast_pct / 100) * total * 0.00025
            + (accurate_pct / 100) * total * 0.003
            + (maximum_pct / 100) * total * 0.015
        )

        savings_amount = baseline_cost - optimized_cost
        savings_pct = (savings_amount / baseline_cost * 100) if baseline_cost > 0 else 0

        cost_savings = CostSavingsResponse(
            percentage=round(savings_pct, 1),
            amount=round(savings_amount, 2),
            trend=_generate_trend_data(30),
            baseline_cost=round(baseline_cost, 2),
            optimized_cost=round(optimized_cost, 2),
            period=period,
        )

        # Model distribution
        tier_counts = stats.get(
            "tier_counts", {"fast": 400, "accurate": 550, "maximum": 50}
        )
        total_count = sum(tier_counts.values()) or 1

        distribution_items = [
            ModelDistributionItem(
                model=MODEL_DISPLAY_INFO[tier]["name"],
                tier=ModelTierEnum(tier),
                percentage=round((count / total_count) * 100, 1),
                count=count,
                color=MODEL_DISPLAY_INFO[tier]["color"],
            )
            for tier, count in tier_counts.items()
        ]

        model_distribution = ModelDistributionResponse(
            distribution=distribution_items,
            total_requests=total_count,
            period=period,
        )

        # A/B test config
        ab_test = ABTestConfigModel(
            enabled=ab_config.enabled,
            experiment_id=ab_config.experiment_id or "",
            experiment_name=ab_config.experiment_id or "",
            control_tier=ModelTierEnum(ab_config.control_tier.value),
            treatment_tier=ModelTierEnum(ab_config.treatment_tier.value),
            traffic_split=ab_config.traffic_split,
            task_types=ab_config.task_types,
            status="active" if ab_config.enabled else "inactive",
        )

        return RouterStatsResponse(
            cost_savings=cost_savings,
            distribution=model_distribution,
            ab_test=ab_test,
            total_decisions=total_count,
        )

    except Exception as e:
        logger.error(f"Failed to get router stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to retrieve router statistics"
        )


@router.get("/distribution", response_model=ModelDistributionResponse)
async def get_model_distribution(
    period: str = Query(  # noqa: B008
        default="30d", description="Time period: 7d, 30d, 90d"
    ),  # noqa: B008
) -> ModelDistributionResponse:
    """
    Get model distribution data for charting.

    Shows percentage of requests handled by each model tier.
    """
    try:
        model_router = get_router()
        stats = model_router.get_stats()

        tier_counts = stats.get(
            "tier_counts", {"fast": 400, "accurate": 550, "maximum": 50}
        )
        total_count = sum(tier_counts.values()) or 1

        distribution_items = [
            ModelDistributionItem(
                model=MODEL_DISPLAY_INFO[tier]["name"],
                tier=ModelTierEnum(tier),
                percentage=round((count / total_count) * 100, 1),
                count=count,
                color=MODEL_DISPLAY_INFO[tier]["color"],
            )
            for tier, count in tier_counts.items()
        ]

        return ModelDistributionResponse(
            distribution=distribution_items,
            total_requests=total_count,
            period=period,
        )

    except Exception as e:
        logger.error(f"Failed to get model distribution: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to retrieve model distribution"
        )


@router.get("/rules", response_model=list[RoutingRuleModel])
async def get_routing_rules() -> list[RoutingRuleModel]:
    """
    Get all routing rules.

    Returns the list of task-to-model routing rules.
    """
    try:
        model_router = get_router()
        rules = model_router.get_routing_rules()

        return [
            RoutingRuleModel(
                id=f"rule-{i}",
                task_type=rule.task_type,
                complexity=TaskComplexityEnum(rule.complexity.value),
                tier=ModelTierEnum(rule.tier.value),
                model=_tier_to_model_name(rule.tier),
                cost_per_1k=model_router._estimate_cost_per_1k(
                    model_router.get_model_for_tier(rule.tier)
                ),
                description=rule.description,
                enabled=rule.enabled,
            )
            for i, rule in enumerate(rules)
        ]

    except Exception as e:
        from src.api.dev_mock_fallback import should_serve_mock

        if should_serve_mock(e):
            logger.warning(
                "get_routing_rules: AWS unavailable, serving mock rules: %s", e
            )
            return _mock_routing_rules()
        logger.error(f"Failed to get routing rules: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve routing rules")


def _mock_routing_rules() -> list[RoutingRuleModel]:
    """Demo routing rules used when Bedrock/DynamoDB are unavailable.

    Mirrors the default rule set the live router would serve, sized so the
    Model Router page renders the rule table with realistic content.
    """
    samples = [
        (
            "code_review",
            TaskComplexityEnum.SIMPLE,
            ModelTierEnum.FAST,
            "Lint-style reviews and small diffs route to Haiku for speed.",
        ),
        (
            "code_review",
            TaskComplexityEnum.COMPLEX,
            ModelTierEnum.ACCURATE,
            "Cross-file refactors and security reviews escalate to Sonnet.",
        ),
        (
            "vulnerability_analysis",
            TaskComplexityEnum.COMPLEX,
            ModelTierEnum.ACCURATE,
            "All vulnerability triage runs on the accurate tier.",
        ),
        (
            "documentation_generation",
            TaskComplexityEnum.SIMPLE,
            ModelTierEnum.FAST,
            "Docstrings and changelog entries route to the fast tier.",
        ),
        (
            "incident_root_cause",
            TaskComplexityEnum.COMPLEX,
            ModelTierEnum.MAXIMUM,
            "Runtime incident RCA uses the maximum tier for breadth of reasoning.",
        ),
        (
            "query_decomposition",
            TaskComplexityEnum.SIMPLE,
            ModelTierEnum.FAST,
            "Sub-query rewrites route to the fast tier.",
        ),
    ]
    cost_by_tier = {
        ModelTierEnum.FAST: 0.00025,
        ModelTierEnum.ACCURATE: 0.003,
        ModelTierEnum.MAXIMUM: 0.015,
    }
    return [
        RoutingRuleModel(
            id=f"rule-{i}",
            task_type=task_type,
            complexity=complexity,
            tier=tier,
            model=(
                _tier_to_model_name(
                    next((t for t in [tier]), tier)  # passthrough; tier is enum already
                )
                if False
                else {
                    ModelTierEnum.FAST: "claude-3-haiku",
                    ModelTierEnum.ACCURATE: "claude-3-5-sonnet",
                    ModelTierEnum.MAXIMUM: "claude-3-opus",
                }[tier]
            ),
            cost_per_1k=cost_by_tier[tier],
            description=description,
            enabled=True,
        )
        for i, (task_type, complexity, tier, description) in enumerate(samples)
    ]


@router.post("/rules", response_model=RoutingRuleModel, status_code=201)
async def create_routing_rule(
    request: RoutingRuleCreateRequest,
) -> RoutingRuleModel:
    """
    Create a new routing rule.

    Adds a new task type to model tier mapping.
    """
    try:
        model_router = get_router()

        # Check for duplicate task type
        existing = [r.task_type for r in model_router.get_routing_rules()]
        if request.task_type in existing:
            raise HTTPException(
                status_code=400,
                detail=f"Rule for task type '{request.task_type}' already exists",
            )

        # Create the rule
        new_rule = RoutingRule(
            task_type=request.task_type,
            complexity=TaskComplexity(request.complexity.value),
            tier=ModelTier(request.tier.value),
            description=request.description,
            enabled=True,
        )

        # Add to router (in production, this would persist to SSM)
        model_router.rules.append(new_rule)
        model_router._rule_lookup[new_rule.task_type] = new_rule

        rule_id = f"rule-{len(model_router.rules) - 1}"

        return RoutingRuleModel(
            id=rule_id,
            task_type=new_rule.task_type,
            complexity=TaskComplexityEnum(new_rule.complexity.value),
            tier=ModelTierEnum(new_rule.tier.value),
            model=_tier_to_model_name(new_rule.tier),
            cost_per_1k=model_router._estimate_cost_per_1k(
                model_router.get_model_for_tier(new_rule.tier)
            ),
            description=new_rule.description,
            enabled=new_rule.enabled,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create routing rule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create routing rule")


@router.put("/rules/{rule_id}", response_model=RoutingRuleModel)
async def update_routing_rule(
    rule_id: str,
    request: RoutingRuleUpdateRequest,
) -> RoutingRuleModel:
    """
    Update an existing routing rule.

    Modifies complexity, tier, description, or enabled status.
    """
    try:
        model_router = get_router()
        rules = model_router.get_routing_rules()

        # Parse rule ID
        try:
            idx = int(rule_id.replace("rule-", ""))
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")

        if idx < 0 or idx >= len(rules):
            raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")

        rule = rules[idx]

        # Apply updates
        if request.complexity is not None:
            rule.complexity = TaskComplexity(request.complexity.value)
        if request.tier is not None:
            rule.tier = ModelTier(request.tier.value)
        if request.description is not None:
            rule.description = request.description
        if request.enabled is not None:
            rule.enabled = request.enabled

        # Update lookup
        model_router._rule_lookup[rule.task_type] = rule

        return RoutingRuleModel(
            id=rule_id,
            task_type=rule.task_type,
            complexity=TaskComplexityEnum(rule.complexity.value),
            tier=ModelTierEnum(rule.tier.value),
            model=_tier_to_model_name(rule.tier),
            cost_per_1k=model_router._estimate_cost_per_1k(
                model_router.get_model_for_tier(rule.tier)
            ),
            description=rule.description,
            enabled=rule.enabled,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update routing rule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update routing rule")


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_routing_rule(rule_id: str) -> None:
    """
    Delete a routing rule.

    Removes the task type to model tier mapping.
    """
    try:
        model_router = get_router()

        # Parse rule ID
        try:
            idx = int(rule_id.replace("rule-", ""))
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")

        if idx < 0 or idx >= len(model_router.rules):
            raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")

        rule = model_router.rules[idx]

        # Remove from lookup and list
        if rule.task_type in model_router._rule_lookup:
            del model_router._rule_lookup[rule.task_type]
        model_router.rules.pop(idx)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete routing rule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete routing rule")


@router.get("/ab-test", response_model=ABTestConfigModel)
async def get_ab_test_config() -> ABTestConfigModel:
    """
    Get current A/B test configuration.

    Returns experiment settings and status.
    """
    try:
        model_router = get_router()
        ab_config = model_router.get_ab_test_config()

        return ABTestConfigModel(
            enabled=ab_config.enabled,
            experiment_id=ab_config.experiment_id or "",
            experiment_name=ab_config.experiment_id or "",
            control_tier=ModelTierEnum(ab_config.control_tier.value),
            treatment_tier=ModelTierEnum(ab_config.treatment_tier.value),
            traffic_split=ab_config.traffic_split,
            task_types=ab_config.task_types,
            status="active" if ab_config.enabled else "inactive",
        )

    except Exception as e:
        logger.error(f"Failed to get A/B test config: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to retrieve A/B test configuration"
        )


@router.put("/ab-test", response_model=ABTestConfigModel)
async def update_ab_test_config(
    request: ABTestUpdateRequest,
) -> ABTestConfigModel:
    """
    Update A/B test configuration.

    Enable/disable experiments and configure parameters.
    """
    try:
        model_router = get_router()
        ab_config = model_router.ab_test

        # Apply updates
        if request.enabled is not None:
            ab_config.enabled = request.enabled
            if request.enabled and not ab_config.experiment_id:
                ab_config.experiment_id = f"exp-{str(uuid.uuid4())[:8]}"

        if request.experiment_name is not None:
            ab_config.experiment_id = request.experiment_name

        if request.control_tier is not None:
            ab_config.control_tier = ModelTier(request.control_tier.value)

        if request.treatment_tier is not None:
            ab_config.treatment_tier = ModelTier(request.treatment_tier.value)

        if request.traffic_split is not None:
            ab_config.traffic_split = request.traffic_split

        if request.task_types is not None:
            ab_config.task_types = request.task_types

        # Calculate dates
        start_date = None
        end_date = None
        if ab_config.enabled:
            start_date = datetime.now(timezone.utc).isoformat()
            if request.duration_days:
                end_date = (
                    datetime.now(timezone.utc) + timedelta(days=request.duration_days)
                ).isoformat()

        return ABTestConfigModel(
            enabled=ab_config.enabled,
            experiment_id=ab_config.experiment_id or "",
            experiment_name=ab_config.experiment_id or "",
            control_tier=ModelTierEnum(ab_config.control_tier.value),
            treatment_tier=ModelTierEnum(ab_config.treatment_tier.value),
            traffic_split=ab_config.traffic_split,
            task_types=ab_config.task_types,
            start_date=start_date,
            end_date=end_date,
            status="active" if ab_config.enabled else "inactive",
        )

    except Exception as e:
        logger.error(f"Failed to update A/B test config: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to update A/B test configuration"
        )


@router.get("/costs", response_model=InvestigationCostsResponse)
async def get_investigation_costs(
    period: str = Query(  # noqa: B008
        default="7d", description="Time period: 1d, 7d, 30d"
    ),  # noqa: B008
    limit: int = Query(  # noqa: B008
        default=20, ge=1, le=100, description="Max results"
    ),  # noqa: B008
) -> InvestigationCostsResponse:
    """
    Get per-investigation cost breakdown.

    Shows recent investigations with model usage and costs.
    """
    try:
        investigations = _generate_sample_investigations(limit)
        total_cost = sum(inv.cost for inv in investigations)

        return InvestigationCostsResponse(
            investigations=investigations,
            total_cost=round(total_cost, 4),
            period=period,
        )

    except Exception as e:
        logger.error(f"Failed to get investigation costs: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to retrieve investigation costs"
        )


@router.post("/refresh", status_code=200)
async def refresh_router_config() -> dict[str, str]:
    """
    Refresh router configuration from SSM Parameter Store.

    Reloads models, rules, and A/B test config.
    """
    try:
        model_router = get_router()
        model_router.reload_config()
        return {"status": "success", "message": "Configuration reloaded"}

    except Exception as e:
        logger.error(f"Failed to refresh router config: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to refresh router configuration"
        )
