"""Trust Center Service for AI Trust Center UI.

This service aggregates data from Constitutional AI, Autonomy Policies,
and CloudWatch metrics to provide a unified view of AI safety status
for the Trust Center dashboard.

Endpoints supported:
- GET /api/v1/trust-center/status - Overall system status
- GET /api/v1/trust-center/principles - Constitutional AI principles
- GET /api/v1/trust-center/autonomy - Current autonomy configuration
- GET /api/v1/trust-center/metrics - Safety metrics (24h, 7d, 30d)
- GET /api/v1/trust-center/decisions - Decision audit timeline
- GET /api/v1/trust-center/export - Export data (PDF/JSON)
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================


class TrustCenterMode(Enum):
    """Operating modes for Trust Center service."""

    MOCK = "mock"
    AWS = "aws"


class OverallHealthStatus(Enum):
    """Overall system health status."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class AutonomyLevel(Enum):
    """Autonomy level definitions."""

    FULL_HITL = "full_hitl"
    CRITICAL_HITL = "critical_hitl"
    AUDIT_ONLY = "audit_only"
    FULL_AUTONOMOUS = "full_autonomous"


@dataclass
class SystemStatus:
    """Overall system status for Trust Center."""

    overall_status: OverallHealthStatus
    constitutional_ai_active: bool
    guardrails_active: bool
    autonomy_level: str
    active_principles_count: int
    critical_principles_count: int
    last_evaluation_time: Optional[datetime]
    decisions_last_24h: int
    issues_last_24h: int
    compliance_score: float
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "overall_status": self.overall_status.value,
            "constitutional_ai_active": self.constitutional_ai_active,
            "guardrails_active": self.guardrails_active,
            "autonomy_level": self.autonomy_level,
            "active_principles_count": self.active_principles_count,
            "critical_principles_count": self.critical_principles_count,
            "last_evaluation_time": (
                self.last_evaluation_time.isoformat()
                if self.last_evaluation_time
                else None
            ),
            "decisions_last_24h": self.decisions_last_24h,
            "issues_last_24h": self.issues_last_24h,
            "compliance_score": self.compliance_score,
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class ConstitutionalPrincipleInfo:
    """Constitutional principle information for UI display."""

    id: str
    name: str
    category: str
    severity: str
    description: str
    domain_tags: list[str]
    enabled: bool
    violation_count_24h: int = 0
    last_triggered: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "severity": self.severity,
            "description": self.description,
            "domain_tags": self.domain_tags,
            "enabled": self.enabled,
            "violation_count_24h": self.violation_count_24h,
            "last_triggered": (
                self.last_triggered.isoformat() if self.last_triggered else None
            ),
        }


@dataclass
class AutonomyConfig:
    """Current autonomy configuration."""

    current_level: str
    hitl_enabled: bool
    preset_name: Optional[str]
    severity_overrides: dict[str, str]
    operation_overrides: dict[str, str]
    active_guardrails: list[str]
    last_hitl_decision: Optional[datetime]
    auto_approved_24h: int
    hitl_required_24h: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "current_level": self.current_level,
            "hitl_enabled": self.hitl_enabled,
            "preset_name": self.preset_name,
            "severity_overrides": self.severity_overrides,
            "operation_overrides": self.operation_overrides,
            "active_guardrails": self.active_guardrails,
            "last_hitl_decision": (
                self.last_hitl_decision.isoformat() if self.last_hitl_decision else None
            ),
            "auto_approved_24h": self.auto_approved_24h,
            "hitl_required_24h": self.hitl_required_24h,
        }


@dataclass
class SafetyMetric:
    """Individual safety metric with time series data."""

    metric_name: str
    display_name: str
    current_value: float
    target_value: float
    unit: str
    trend: str  # "improving", "stable", "degrading"
    status: str  # "healthy", "warning", "critical"
    change_24h: float
    time_series: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metric_name": self.metric_name,
            "display_name": self.display_name,
            "current_value": self.current_value,
            "target_value": self.target_value,
            "unit": self.unit,
            "trend": self.trend,
            "status": self.status,
            "change_24h": self.change_24h,
            "time_series": self.time_series,
        }


@dataclass
class SafetyMetricsSnapshot:
    """Aggregated safety metrics for a time period."""

    period: str  # "24h", "7d", "30d"
    critique_accuracy: SafetyMetric
    revision_convergence_rate: SafetyMetric
    cache_hit_rate: SafetyMetric
    non_evasive_rate: SafetyMetric
    critique_latency_p95: SafetyMetric
    golden_set_pass_rate: SafetyMetric
    total_evaluations: int
    total_critiques: int
    issues_by_severity: dict[str, int]
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "period": self.period,
            "critique_accuracy": self.critique_accuracy.to_dict(),
            "revision_convergence_rate": self.revision_convergence_rate.to_dict(),
            "cache_hit_rate": self.cache_hit_rate.to_dict(),
            "non_evasive_rate": self.non_evasive_rate.to_dict(),
            "critique_latency_p95": self.critique_latency_p95.to_dict(),
            "golden_set_pass_rate": self.golden_set_pass_rate.to_dict(),
            "total_evaluations": self.total_evaluations,
            "total_critiques": self.total_critiques,
            "issues_by_severity": self.issues_by_severity,
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class AuditDecision:
    """Individual audit decision entry."""

    decision_id: str
    timestamp: datetime
    agent_name: str
    operation_type: str
    principles_evaluated: int
    issues_found: int
    severity_breakdown: dict[str, int]
    requires_revision: bool
    revised: bool
    hitl_required: bool
    hitl_approved: Optional[bool]
    approved_by: Optional[str]
    execution_time_ms: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "decision_id": self.decision_id,
            "timestamp": self.timestamp.isoformat(),
            "agent_name": self.agent_name,
            "operation_type": self.operation_type,
            "principles_evaluated": self.principles_evaluated,
            "issues_found": self.issues_found,
            "severity_breakdown": self.severity_breakdown,
            "requires_revision": self.requires_revision,
            "revised": self.revised,
            "hitl_required": self.hitl_required,
            "hitl_approved": self.hitl_approved,
            "approved_by": self.approved_by,
            "execution_time_ms": self.execution_time_ms,
        }


@dataclass
class ExportData:
    """Export data structure."""

    export_id: str
    format: str  # "pdf" or "json"
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    status: SystemStatus
    principles: list[ConstitutionalPrincipleInfo]
    autonomy: AutonomyConfig
    metrics: SafetyMetricsSnapshot
    decisions_count: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "export_id": self.export_id,
            "format": self.format,
            "generated_at": self.generated_at.isoformat(),
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "status": self.status.to_dict(),
            "principles": [p.to_dict() for p in self.principles],
            "autonomy": self.autonomy.to_dict(),
            "metrics": self.metrics.to_dict(),
            "decisions_count": self.decisions_count,
        }


# =============================================================================
# Trust Center Service
# =============================================================================


class TrustCenterService:
    """Service for aggregating Trust Center data.

    Integrates with:
    - Constitutional AI service (principles, critiques)
    - Autonomy Policy service (HITL configuration)
    - CloudWatch metrics (Aura/ConstitutionalAI namespace)
    - DynamoDB (audit table)
    """

    def __init__(
        self,
        mode: TrustCenterMode = TrustCenterMode.MOCK,
        environment: str = "dev",
        organization_id: Optional[str] = None,
    ):
        """Initialize the Trust Center service.

        Args:
            mode: Operating mode (MOCK or AWS)
            environment: Environment name (dev, qa, prod)
            organization_id: Organization ID for multi-tenant support
        """
        self.mode = mode
        self.environment = environment
        self.organization_id = organization_id or "default"
        self._principles_cache: list[ConstitutionalPrincipleInfo] = []
        self._principles_loaded_at: Optional[datetime] = None
        self._cloudwatch_client = None
        self._dynamodb_client = None

        # Load constitution.yaml on init
        self._load_principles()

    def _load_principles(self) -> None:
        """Load constitutional principles from YAML file."""
        try:
            constitution_path = (
                Path(__file__).parent / "constitutional_ai" / "constitution.yaml"
            )

            if not constitution_path.exists():
                logger.warning(f"Constitution file not found: {constitution_path}")
                self._principles_cache = self._get_mock_principles()
                return

            with open(constitution_path) as f:
                constitution = yaml.safe_load(f)

            principles = constitution.get("principles", {})
            self._principles_cache = []

            for principle_id, principle_data in principles.items():
                # Extract first sentence of critique_prompt as description
                critique_prompt = principle_data.get("critique_prompt", "")
                description = critique_prompt.split("\n")[0].strip()
                if len(description) > 200:
                    description = description[:197] + "..."

                self._principles_cache.append(
                    ConstitutionalPrincipleInfo(
                        id=principle_id,
                        name=principle_data.get("name", principle_id),
                        category=principle_data.get("category", "unknown"),
                        severity=principle_data.get("severity", "medium"),
                        description=description,
                        domain_tags=principle_data.get("domain_tags", []),
                        enabled=True,
                    )
                )

            self._principles_loaded_at = datetime.now(timezone.utc)
            logger.info(
                f"Loaded {len(self._principles_cache)} constitutional principles"
            )

        except Exception as e:
            logger.error(f"Error loading constitution.yaml: {e}")
            self._principles_cache = self._get_mock_principles()

    def _get_mock_principles(self) -> list[ConstitutionalPrincipleInfo]:
        """Return mock principles for testing."""
        return [
            ConstitutionalPrincipleInfo(
                id="principle_1_security_first",
                name="Security-First Code Generation",
                category="safety",
                severity="critical",
                description="Analyze code for security vulnerabilities including SQL injection, XSS, and command injection.",
                domain_tags=["security", "owasp", "code_generation"],
                enabled=True,
            ),
            ConstitutionalPrincipleInfo(
                id="principle_2_data_protection",
                name="Data Protection and Privacy",
                category="safety",
                severity="critical",
                description="Analyze responses for data protection and privacy issues.",
                domain_tags=["privacy", "pii", "data_protection"],
                enabled=True,
            ),
            ConstitutionalPrincipleInfo(
                id="principle_3_sandbox_isolation",
                name="Sandbox Environment Isolation",
                category="safety",
                severity="critical",
                description="Analyze responses for potential sandbox escape or isolation violations.",
                domain_tags=["sandbox", "isolation", "container"],
                enabled=True,
            ),
        ]

    async def get_system_status(self) -> SystemStatus:
        """Get overall system status.

        Returns:
            SystemStatus with current health information
        """
        if self.mode == TrustCenterMode.MOCK:
            return self._get_mock_status()

        # AWS mode - aggregate real data
        try:
            # Get metrics from CloudWatch
            metrics = await self._get_cloudwatch_metrics()

            # Get audit data from DynamoDB
            audit_data = await self._get_audit_summary()

            # Calculate compliance score
            compliance = self._calculate_compliance_score(metrics, audit_data)

            # Determine overall status
            overall = self._determine_overall_status(metrics, audit_data, compliance)

            # Count principles
            critical_count = sum(
                1 for p in self._principles_cache if p.severity == "critical"
            )

            return SystemStatus(
                overall_status=overall,
                constitutional_ai_active=True,
                guardrails_active=True,
                autonomy_level="critical_hitl",
                active_principles_count=len(self._principles_cache),
                critical_principles_count=critical_count,
                last_evaluation_time=audit_data.get("last_evaluation"),
                decisions_last_24h=audit_data.get("decisions_24h", 0),
                issues_last_24h=audit_data.get("issues_24h", 0),
                compliance_score=compliance,
            )

        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return self._get_mock_status()

    def _get_mock_status(self) -> SystemStatus:
        """Get mock system status for testing."""
        critical_count = sum(
            1 for p in self._principles_cache if p.severity == "critical"
        )

        return SystemStatus(
            overall_status=OverallHealthStatus.HEALTHY,
            constitutional_ai_active=True,
            guardrails_active=True,
            autonomy_level="critical_hitl",
            active_principles_count=len(self._principles_cache),
            critical_principles_count=critical_count,
            last_evaluation_time=datetime.now(timezone.utc) - timedelta(minutes=15),
            decisions_last_24h=47,
            issues_last_24h=3,
            compliance_score=0.94,
        )

    async def get_principles(
        self,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        include_metrics: bool = False,
    ) -> list[ConstitutionalPrincipleInfo]:
        """Get constitutional principles with optional filtering.

        Args:
            category: Filter by category (safety, compliance, etc.)
            severity: Filter by severity (critical, high, medium, low)
            include_metrics: Include violation metrics (requires AWS mode)

        Returns:
            List of ConstitutionalPrincipleInfo
        """
        principles = self._principles_cache.copy()

        # Apply filters
        if category:
            principles = [p for p in principles if p.category == category]

        if severity:
            principles = [p for p in principles if p.severity == severity]

        # Add metrics if requested and in AWS mode
        if include_metrics and self.mode == TrustCenterMode.AWS:
            try:
                await self._enrich_principles_with_metrics(principles)
            except Exception as e:
                logger.warning(f"Failed to enrich principles with metrics: {e}")

        return principles

    async def _enrich_principles_with_metrics(
        self, principles: list[ConstitutionalPrincipleInfo]
    ) -> None:
        """Enrich principles with violation metrics from DynamoDB."""
        # Query audit table for principle violations in last 24h
        # This would use the agent-timestamp-index GSI
        pass  # Implementation for AWS mode

    async def get_autonomy_config(
        self, policy_id: Optional[str] = None
    ) -> AutonomyConfig:
        """Get current autonomy configuration.

        Args:
            policy_id: Specific policy ID to retrieve

        Returns:
            AutonomyConfig with current settings
        """
        if self.mode == TrustCenterMode.MOCK:
            return self._get_mock_autonomy_config()

        # AWS mode - get from autonomy service
        try:
            from src.services.autonomy_policy_service import (
                AutonomyServiceMode,
                create_autonomy_policy_service,
            )

            service = create_autonomy_policy_service(mode=AutonomyServiceMode.AWS)

            # Get policies for organization
            policies = service.list_policies(
                organization_id=self.organization_id,
                include_inactive=False,
            )

            if not policies:
                return self._get_mock_autonomy_config()

            # Use first active policy or specified policy
            policy = policies[0]
            if policy_id:
                for p in policies:
                    if p.policy_id == policy_id:
                        policy = p
                        break

            return AutonomyConfig(
                current_level=policy.default_level.value,
                hitl_enabled=policy.hitl_enabled,
                preset_name=policy.preset_name,
                severity_overrides={
                    k: v.value for k, v in policy.severity_overrides.items()
                },
                operation_overrides={
                    k: v.value for k, v in policy.operation_overrides.items()
                },
                active_guardrails=policy.guardrails,
                last_hitl_decision=None,  # Would query from decisions
                auto_approved_24h=0,
                hitl_required_24h=0,
            )

        except Exception as e:
            logger.error(f"Error getting autonomy config: {e}")
            return self._get_mock_autonomy_config()

    def _get_mock_autonomy_config(self) -> AutonomyConfig:
        """Get mock autonomy configuration for testing."""
        return AutonomyConfig(
            current_level="critical_hitl",
            hitl_enabled=True,
            preset_name="enterprise_standard",
            severity_overrides={"CRITICAL": "full_hitl"},
            operation_overrides={
                "production_deployment": "full_hitl",
                "credential_modification": "full_hitl",
            },
            active_guardrails=[
                "production_deployment",
                "credential_modification",
                "security_policy_change",
            ],
            last_hitl_decision=datetime.now(timezone.utc) - timedelta(hours=2),
            auto_approved_24h=42,
            hitl_required_24h=5,
        )

    async def get_safety_metrics(self, period: str = "24h") -> SafetyMetricsSnapshot:
        """Get safety metrics for the specified period.

        Args:
            period: Time period ("24h", "7d", "30d")

        Returns:
            SafetyMetricsSnapshot with aggregated metrics
        """
        if self.mode == TrustCenterMode.MOCK:
            return self._get_mock_metrics(period)

        # AWS mode - query CloudWatch
        try:
            return await self._query_cloudwatch_metrics(period)
        except Exception as e:
            logger.error(f"Error getting safety metrics: {e}")
            return self._get_mock_metrics(period)

    async def _query_cloudwatch_metrics(self, period: str) -> SafetyMetricsSnapshot:
        """Query CloudWatch for Constitutional AI metrics."""
        import boto3

        if self._cloudwatch_client is None:
            self._cloudwatch_client = boto3.client("cloudwatch")

        # Calculate time range
        period_hours = {"24h": 24, "7d": 168, "30d": 720}.get(period, 24)
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=period_hours)

        namespace = "Aura/ConstitutionalAI"

        # Query each metric
        metrics_to_query = [
            ("CritiqueAccuracy", "Percent"),
            ("RevisionConvergenceRate", "Percent"),
            ("CacheHitRate", "Percent"),
            ("NonEvasiveRate", "Percent"),
            ("CritiqueLatencyP95", "Milliseconds"),
            ("GoldenSetPassRate", "Percent"),
        ]

        results = {}
        for metric_name, unit in metrics_to_query:
            try:
                response = self._cloudwatch_client.get_metric_statistics(
                    Namespace=namespace,
                    MetricName=metric_name,
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=3600,  # 1 hour granularity
                    Statistics=["Average"],
                    Dimensions=[
                        {"Name": "Environment", "Value": self.environment},
                    ],
                )
                datapoints = response.get("Datapoints", [])
                if datapoints:
                    # Sort by timestamp and get most recent
                    sorted_points = sorted(
                        datapoints, key=lambda x: x["Timestamp"], reverse=True
                    )
                    results[metric_name] = {
                        "value": sorted_points[0]["Average"],
                        "unit": unit,
                        "datapoints": sorted_points,
                    }
            except Exception as e:
                logger.warning(f"Error querying metric {metric_name}: {e}")

        return self._build_metrics_snapshot(period, results)

    def _build_metrics_snapshot(
        self, period: str, results: dict[str, Any]
    ) -> SafetyMetricsSnapshot:
        """Build SafetyMetricsSnapshot from CloudWatch results."""

        def build_metric(
            name: str, display: str, target: float, unit: str
        ) -> SafetyMetric:
            data = results.get(name, {"value": 0.0, "datapoints": []})
            value = data.get("value", 0.0)

            # Determine trend and status
            if value >= target:
                status = "healthy"
            elif value >= target * 0.9:
                status = "warning"
            else:
                status = "critical"

            # Calculate trend from datapoints
            datapoints = data.get("datapoints", [])
            if len(datapoints) >= 2:
                recent = datapoints[0].get("Average", 0)
                older = datapoints[-1].get("Average", 0)
                if recent > older:
                    trend = "improving"
                elif recent < older:
                    trend = "degrading"
                else:
                    trend = "stable"
                change = recent - older
            else:
                trend = "stable"
                change = 0.0

            # Build time series
            time_series = [
                {"timestamp": dp["Timestamp"].isoformat(), "value": dp["Average"]}
                for dp in datapoints
            ]

            return SafetyMetric(
                metric_name=name,
                display_name=display,
                current_value=value,
                target_value=target,
                unit=unit,
                trend=trend,
                status=status,
                change_24h=change,
                time_series=time_series,
            )

        return SafetyMetricsSnapshot(
            period=period,
            critique_accuracy=build_metric(
                "CritiqueAccuracy", "Critique Accuracy", 90.0, "percent"
            ),
            revision_convergence_rate=build_metric(
                "RevisionConvergenceRate", "Revision Convergence", 95.0, "percent"
            ),
            cache_hit_rate=build_metric(
                "CacheHitRate", "Cache Hit Rate", 30.0, "percent"
            ),
            non_evasive_rate=build_metric(
                "NonEvasiveRate", "Non-Evasive Rate", 70.0, "percent"
            ),
            critique_latency_p95=build_metric(
                "CritiqueLatencyP95", "Critique Latency (P95)", 500.0, "ms"
            ),
            golden_set_pass_rate=build_metric(
                "GoldenSetPassRate", "Golden Set Pass Rate", 95.0, "percent"
            ),
            total_evaluations=0,
            total_critiques=0,
            issues_by_severity={"critical": 0, "high": 0, "medium": 0, "low": 0},
        )

    def _get_mock_metrics(self, period: str) -> SafetyMetricsSnapshot:
        """Get mock metrics for testing."""

        def mock_time_series(base: float, points: int = 24) -> list[dict[str, Any]]:
            import random

            series = []
            now = datetime.now(timezone.utc)
            for i in range(points):
                ts = now - timedelta(hours=points - i)
                variation = random.uniform(-3, 3)
                series.append(
                    {
                        "timestamp": ts.isoformat(),
                        "value": round(base + variation, 1),
                    }
                )
            return series

        return SafetyMetricsSnapshot(
            period=period,
            critique_accuracy=SafetyMetric(
                metric_name="CritiqueAccuracy",
                display_name="Critique Accuracy",
                current_value=92.3,
                target_value=90.0,
                unit="percent",
                trend="stable",
                status="healthy",
                change_24h=0.5,
                time_series=mock_time_series(92.0),
            ),
            revision_convergence_rate=SafetyMetric(
                metric_name="RevisionConvergenceRate",
                display_name="Revision Convergence",
                current_value=96.8,
                target_value=95.0,
                unit="percent",
                trend="improving",
                status="healthy",
                change_24h=1.2,
                time_series=mock_time_series(96.0),
            ),
            cache_hit_rate=SafetyMetric(
                metric_name="CacheHitRate",
                display_name="Cache Hit Rate",
                current_value=34.5,
                target_value=30.0,
                unit="percent",
                trend="improving",
                status="healthy",
                change_24h=2.1,
                time_series=mock_time_series(33.0),
            ),
            non_evasive_rate=SafetyMetric(
                metric_name="NonEvasiveRate",
                display_name="Non-Evasive Rate",
                current_value=78.2,
                target_value=70.0,
                unit="percent",
                trend="stable",
                status="healthy",
                change_24h=-0.3,
                time_series=mock_time_series(78.0),
            ),
            critique_latency_p95=SafetyMetric(
                metric_name="CritiqueLatencyP95",
                display_name="Critique Latency (P95)",
                current_value=342.0,
                target_value=500.0,
                unit="ms",
                trend="improving",
                status="healthy",
                change_24h=-15.0,
                time_series=mock_time_series(350.0),
            ),
            golden_set_pass_rate=SafetyMetric(
                metric_name="GoldenSetPassRate",
                display_name="Golden Set Pass Rate",
                current_value=98.0,
                target_value=95.0,
                unit="percent",
                trend="stable",
                status="healthy",
                change_24h=0.0,
                time_series=mock_time_series(98.0),
            ),
            total_evaluations=156,
            total_critiques=1247,
            issues_by_severity={"critical": 0, "high": 3, "medium": 12, "low": 28},
        )

    async def get_audit_decisions(
        self,
        limit: int = 50,
        offset: int = 0,
        agent_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> list[AuditDecision]:
        """Get audit decision timeline.

        Args:
            limit: Maximum number of decisions to return
            offset: Offset for pagination
            agent_name: Filter by agent name
            start_time: Filter by start time
            end_time: Filter by end time

        Returns:
            List of AuditDecision entries
        """
        if self.mode == TrustCenterMode.MOCK:
            return self._get_mock_audit_decisions(limit, agent_name)

        # AWS mode - query DynamoDB
        try:
            return await self._query_audit_table(
                limit, offset, agent_name, start_time, end_time
            )
        except Exception as e:
            logger.error(f"Error getting audit decisions: {e}")
            return self._get_mock_audit_decisions(limit, agent_name)

    async def _query_audit_table(
        self,
        limit: int,
        offset: int,
        agent_name: Optional[str],
        start_time: Optional[datetime],
        end_time: Optional[datetime],
    ) -> list[AuditDecision]:
        """Query DynamoDB audit table."""
        import boto3

        if self._dynamodb_client is None:
            self._dynamodb_client = boto3.resource("dynamodb")

        table_name = f"aura-constitutional-audit-{self.environment}"
        table = self._dynamodb_client.Table(table_name)

        # Use agent-timestamp-index GSI if filtering by agent
        if agent_name:
            response = table.query(
                IndexName="agent-timestamp-index",
                KeyConditionExpression="agent_name = :agent",
                ExpressionAttributeValues={":agent": agent_name},
                Limit=limit,
                ScanIndexForward=False,  # Most recent first
            )
        else:
            # Scan with limit (not ideal but acceptable for small datasets)
            response = table.scan(Limit=limit)

        decisions = []
        for item in response.get("Items", []):
            decisions.append(
                AuditDecision(
                    decision_id=item.get("pk", ""),
                    timestamp=datetime.fromisoformat(item.get("timestamp", "")),
                    agent_name=item.get("agent_name", ""),
                    operation_type=item.get("operation_type", ""),
                    principles_evaluated=item.get("principles_evaluated", 0),
                    issues_found=item.get("issues_found", 0),
                    severity_breakdown=item.get("severity_breakdown", {}),
                    requires_revision=item.get("requires_revision", False),
                    revised=item.get("revised", False),
                    hitl_required=item.get("hitl_required", False),
                    hitl_approved=item.get("hitl_approved"),
                    approved_by=item.get("approved_by"),
                    execution_time_ms=item.get("execution_time_ms", 0),
                )
            )

        return decisions

    def _get_mock_audit_decisions(
        self, limit: int, agent_name: Optional[str] = None
    ) -> list[AuditDecision]:
        """Get mock audit decisions for testing."""
        import uuid

        agents = ["CoderAgent", "ReviewerAgent", "ValidatorAgent", "PatcherAgent"]
        operations = [
            "code_generation",
            "vulnerability_scan",
            "patch_validation",
            "deployment_check",
        ]

        decisions = []
        now = datetime.now(timezone.utc)

        for i in range(min(limit, 20)):
            agent = agents[i % len(agents)]
            if agent_name and agent != agent_name:
                continue

            issues = i % 4
            decisions.append(
                AuditDecision(
                    decision_id=str(uuid.uuid4()),
                    timestamp=now - timedelta(hours=i * 2),
                    agent_name=agent,
                    operation_type=operations[i % len(operations)],
                    principles_evaluated=16,
                    issues_found=issues,
                    severity_breakdown={
                        "critical": 0 if issues < 3 else 1,
                        "high": min(issues, 1),
                        "medium": max(0, issues - 1),
                        "low": 0,
                    },
                    requires_revision=issues > 0,
                    revised=issues > 0,
                    hitl_required=issues >= 3,
                    hitl_approved=True if issues >= 3 else None,
                    approved_by="admin@example.com" if issues >= 3 else None,
                    execution_time_ms=125.0 + (i * 10),
                )
            )

        return decisions

    async def generate_export(
        self,
        format: str = "json",
        period: str = "24h",
    ) -> ExportData:
        """Generate export data.

        Args:
            format: Export format ("json" or "pdf")
            period: Time period to export

        Returns:
            ExportData with aggregated information
        """
        import uuid

        now = datetime.now(timezone.utc)
        period_hours = {"24h": 24, "7d": 168, "30d": 720}.get(period, 24)
        period_start = now - timedelta(hours=period_hours)

        # Gather all data
        status = await self.get_system_status()
        principles = await self.get_principles(include_metrics=True)
        autonomy = await self.get_autonomy_config()
        metrics = await self.get_safety_metrics(period)
        decisions = await self.get_audit_decisions(limit=1000)

        return ExportData(
            export_id=str(uuid.uuid4()),
            format=format,
            generated_at=now,
            period_start=period_start,
            period_end=now,
            status=status,
            principles=principles,
            autonomy=autonomy,
            metrics=metrics,
            decisions_count=len(decisions),
        )

    async def _get_cloudwatch_metrics(self) -> dict[str, Any]:
        """Get CloudWatch metrics summary."""
        return {}  # Placeholder for AWS implementation

    async def _get_audit_summary(self) -> dict[str, Any]:
        """Get audit table summary."""
        return {
            "last_evaluation": datetime.now(timezone.utc),
            "decisions_24h": 47,
            "issues_24h": 3,
        }

    def _calculate_compliance_score(
        self, metrics: dict[str, Any], audit_data: dict[str, Any]
    ) -> float:
        """Calculate compliance score from metrics."""
        return 0.94  # Placeholder

    def _determine_overall_status(
        self,
        metrics: dict[str, Any],
        audit_data: dict[str, Any],
        compliance: float,
    ) -> OverallHealthStatus:
        """Determine overall health status."""
        if compliance >= 0.9:
            return OverallHealthStatus.HEALTHY
        elif compliance >= 0.7:
            return OverallHealthStatus.WARNING
        else:
            return OverallHealthStatus.CRITICAL


# =============================================================================
# Factory Function
# =============================================================================


def create_trust_center_service(
    mode: str = "mock",
    environment: Optional[str] = None,
    organization_id: Optional[str] = None,
) -> TrustCenterService:
    """Create a TrustCenterService instance.

    Args:
        mode: "mock" or "aws"
        environment: Environment name (defaults to ENVIRONMENT env var)
        organization_id: Organization ID for multi-tenant support

    Returns:
        Configured TrustCenterService
    """
    env = environment or os.environ.get("ENVIRONMENT", "dev")
    service_mode = TrustCenterMode.AWS if mode == "aws" else TrustCenterMode.MOCK

    return TrustCenterService(
        mode=service_mode,
        environment=env,
        organization_id=organization_id,
    )
