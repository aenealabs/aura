"""Proactive Recommendation Engine

Implements ADR-037 Phase 3.5: Proactive Recommendation Engine

Generates proactive recommendations for operational excellence
across four focus areas: observability, infrastructure,
deployment pipeline, and application resilience.

Key Features:
- Observability enhancement recommendations
- Infrastructure optimization suggestions
- Deployment pipeline improvement analysis
- Application resilience strengthening
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)


class RecommendationCategory(Enum):
    """Categories of recommendations."""

    OBSERVABILITY = "observability"
    INFRASTRUCTURE = "infrastructure"
    DEPLOYMENT_PIPELINE = "deployment_pipeline"
    APPLICATION_RESILIENCE = "application_resilience"
    SECURITY = "security"
    COST = "cost"


class RecommendationPriority(Enum):
    """Priority levels for recommendations."""

    CRITICAL = "critical"  # Should be addressed immediately
    HIGH = "high"  # Should be addressed soon
    MEDIUM = "medium"  # Should be planned
    LOW = "low"  # Nice to have


class ImplementationEffort(Enum):
    """Effort required to implement recommendation."""

    TRIVIAL = "trivial"  # Minutes
    LOW = "low"  # Hours
    MEDIUM = "medium"  # Days
    HIGH = "high"  # Weeks
    MAJOR = "major"  # Months


class MetricsCollector(Protocol):
    """Protocol for metrics collection."""

    async def get_metrics(
        self, namespace: str, metric_name: str, period: int
    ) -> list[dict]:
        """Get metrics data."""
        ...


class ResourceDiscovery(Protocol):
    """Protocol for resource discovery."""

    async def list_resources(self, resource_type: str) -> list[dict]:
        """List resources of type."""
        ...


@dataclass
class ProactiveRecommendation:
    """A proactive operational recommendation."""

    recommendation_id: str
    category: RecommendationCategory
    priority: RecommendationPriority
    title: str
    description: str
    impact: str
    effort: ImplementationEffort
    evidence: list[str] = field(default_factory=list)
    implementation_steps: list[str] = field(default_factory=list)
    estimated_improvement: Optional[str] = None
    affected_resources: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None


@dataclass
class ObservabilityConfig:
    """Current observability configuration."""

    log_retention_days: int = 30
    metrics_enabled: bool = True
    tracing_enabled: bool = False
    alerting_enabled: bool = False
    dashboards_count: int = 0
    alarm_count: int = 0
    log_groups: list[str] = field(default_factory=list)
    custom_metrics: list[str] = field(default_factory=list)


@dataclass
class ResourceGraph:
    """Graph of infrastructure resources."""

    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PipelineConfig:
    """CI/CD pipeline configuration."""

    pipeline_name: str = ""
    stages: list[str] = field(default_factory=list)
    has_tests: bool = False
    has_security_scan: bool = False
    has_approval_gate: bool = False
    deployment_frequency_per_day: float = 0.0
    failure_rate: float = 0.0
    mean_time_to_recovery_minutes: float = 0.0


@dataclass
class ArchitectureSpec:
    """Application architecture specification."""

    services: list[str] = field(default_factory=list)
    databases: list[str] = field(default_factory=list)
    has_redundancy: bool = False
    has_circuit_breakers: bool = False
    has_rate_limiting: bool = False
    has_health_checks: bool = False


@dataclass
class CostData:
    """Cost data for optimization."""

    monthly_total: float = 0.0
    by_service: dict[str, float] = field(default_factory=dict)
    trend: str = "stable"  # increasing, decreasing, stable


@dataclass
class IncidentRecord:
    """Historical incident record."""

    incident_id: str
    severity: str
    service: str
    duration_minutes: int
    root_cause: str
    occurred_at: datetime


@dataclass
class DeploymentEvent:
    """Deployment event for analysis."""

    deployment_id: str
    service: str
    success: bool
    duration_minutes: int
    rollback: bool
    deployed_at: datetime


@dataclass
class RecommendationSummary:
    """Summary of recommendations."""

    total_count: int
    by_category: dict[str, int]
    by_priority: dict[str, int]
    estimated_total_impact: str


class ProactiveRecommendationEngine:
    """Generate proactive operational recommendations.

    Four focus areas (AWS DevOps Agent parity):
    1. Observability enhancement
    2. Infrastructure optimization
    3. Deployment pipeline improvement
    4. Application resilience strengthening

    Usage:
        engine = ProactiveRecommendationEngine(metrics_collector)

        # Analyze observability
        obs_recs = await engine.analyze_observability(current_config)

        # Analyze infrastructure
        infra_recs = await engine.analyze_infrastructure(
            resource_graph, cost_data
        )

        # Analyze deployment pipeline
        pipeline_recs = await engine.analyze_deployment_pipeline(
            pipeline_config, deployment_history
        )

        # Analyze resilience
        resilience_recs = await engine.analyze_resilience(
            architecture, incident_history
        )
    """

    def __init__(
        self,
        metrics_collector: Optional[MetricsCollector] = None,
        resource_discovery: Optional[ResourceDiscovery] = None,
    ):
        """Initialize recommendation engine.

        Args:
            metrics_collector: Metrics collector for analysis
            resource_discovery: Resource discovery service
        """
        self.metrics = metrics_collector
        self.resources = resource_discovery
        self._recommendations: list[ProactiveRecommendation] = []
        self._rec_counter = 0

    async def analyze_observability(
        self,
        current_config: ObservabilityConfig,
    ) -> list[ProactiveRecommendation]:
        """Analyze and recommend observability improvements.

        Args:
            current_config: Current observability configuration

        Returns:
            List of recommendations
        """
        recommendations = []

        # Check log retention
        if current_config.log_retention_days < 90:
            recommendations.append(
                self._create_recommendation(
                    category=RecommendationCategory.OBSERVABILITY,
                    priority=RecommendationPriority.MEDIUM,
                    title="Increase log retention period",
                    description=(
                        f"Current log retention is {current_config.log_retention_days} days. "
                        "Consider increasing to 90+ days for compliance and debugging."
                    ),
                    impact="Improved debugging capability and compliance",
                    effort=ImplementationEffort.LOW,
                    evidence=[
                        f"Current retention: {current_config.log_retention_days} days",
                        "Recommended minimum: 90 days",
                    ],
                    implementation_steps=[
                        "Update CloudWatch log group retention settings",
                        "Update IAM policies if needed",
                        "Update CloudFormation templates",
                    ],
                )
            )

        # Check tracing
        if not current_config.tracing_enabled:
            recommendations.append(
                self._create_recommendation(
                    category=RecommendationCategory.OBSERVABILITY,
                    priority=RecommendationPriority.HIGH,
                    title="Enable distributed tracing",
                    description=(
                        "Distributed tracing is not enabled. Enable X-Ray or OpenTelemetry "
                        "for end-to-end request visibility."
                    ),
                    impact="50-70% faster incident investigation",
                    effort=ImplementationEffort.MEDIUM,
                    evidence=["Tracing not enabled in current configuration"],
                    implementation_steps=[
                        "Add X-Ray SDK to application code",
                        "Configure sampling rules",
                        "Set up trace groups and service map",
                        "Update IAM permissions",
                    ],
                )
            )

        # Check alerting
        if current_config.alarm_count < 5:
            recommendations.append(
                self._create_recommendation(
                    category=RecommendationCategory.OBSERVABILITY,
                    priority=RecommendationPriority.HIGH,
                    title="Implement comprehensive alerting",
                    description=(
                        f"Only {current_config.alarm_count} alarms configured. "
                        "Add alarms for error rates, latency, and resource utilization."
                    ),
                    impact="Faster incident detection and response",
                    effort=ImplementationEffort.MEDIUM,
                    evidence=[f"Current alarm count: {current_config.alarm_count}"],
                    implementation_steps=[
                        "Define SLOs for key services",
                        "Create alarms for error rate > threshold",
                        "Create alarms for p99 latency",
                        "Create alarms for resource utilization",
                        "Set up SNS notifications",
                    ],
                )
            )

        # Check dashboards
        if current_config.dashboards_count < 3:
            recommendations.append(
                self._create_recommendation(
                    category=RecommendationCategory.OBSERVABILITY,
                    priority=RecommendationPriority.MEDIUM,
                    title="Create operational dashboards",
                    description=(
                        "Few operational dashboards exist. Create dashboards for "
                        "service health, API performance, and infrastructure."
                    ),
                    impact="Improved situational awareness",
                    effort=ImplementationEffort.LOW,
                    evidence=[
                        f"Current dashboard count: {current_config.dashboards_count}"
                    ],
                    implementation_steps=[
                        "Create service health dashboard",
                        "Create API performance dashboard",
                        "Create infrastructure dashboard",
                        "Share dashboards with team",
                    ],
                )
            )

        self._recommendations.extend(recommendations)
        return recommendations

    async def analyze_infrastructure(
        self,
        resource_graph: ResourceGraph,
        cost_data: Optional[CostData] = None,
    ) -> list[ProactiveRecommendation]:
        """Analyze and recommend infrastructure optimizations.

        Args:
            resource_graph: Graph of infrastructure resources
            cost_data: Optional cost data

        Returns:
            List of recommendations
        """
        recommendations = []

        # Analyze resource utilization
        underutilized = self._find_underutilized_resources(resource_graph)
        if underutilized:
            recommendations.append(
                self._create_recommendation(
                    category=RecommendationCategory.INFRASTRUCTURE,
                    priority=RecommendationPriority.MEDIUM,
                    title="Right-size underutilized resources",
                    description=(
                        f"Found {len(underutilized)} potentially underutilized resources. "
                        "Consider downsizing or using reserved capacity."
                    ),
                    impact="Cost reduction of 20-40%",
                    effort=ImplementationEffort.MEDIUM,
                    evidence=[f"Underutilized resources: {underutilized[:5]}"],
                    affected_resources=underutilized,
                    implementation_steps=[
                        "Review CPU and memory utilization for each resource",
                        "Identify appropriate instance sizes",
                        "Plan migration during maintenance window",
                        "Update infrastructure code",
                    ],
                )
            )

        # Check for single points of failure
        spofs = self._find_single_points_of_failure(resource_graph)
        if spofs:
            recommendations.append(
                self._create_recommendation(
                    category=RecommendationCategory.INFRASTRUCTURE,
                    priority=RecommendationPriority.HIGH,
                    title="Eliminate single points of failure",
                    description=(
                        f"Found {len(spofs)} potential single points of failure. "
                        "Add redundancy to improve availability."
                    ),
                    impact="Improved availability from 99.9% to 99.99%",
                    effort=ImplementationEffort.HIGH,
                    evidence=[f"Single points of failure: {spofs}"],
                    affected_resources=spofs,
                    implementation_steps=[
                        "Identify critical components without redundancy",
                        "Design multi-AZ or multi-region architecture",
                        "Implement load balancing",
                        "Add health checks and auto-scaling",
                    ],
                )
            )

        # Cost optimization
        if cost_data and cost_data.trend == "increasing":
            recommendations.append(
                self._create_recommendation(
                    category=RecommendationCategory.COST,
                    priority=RecommendationPriority.MEDIUM,
                    title="Investigate increasing costs",
                    description=(
                        f"Monthly costs are increasing. Current: ${cost_data.monthly_total:.2f}. "
                        "Review resource usage and consider optimization."
                    ),
                    impact="Potential 15-30% cost reduction",
                    effort=ImplementationEffort.MEDIUM,
                    evidence=[
                        f"Monthly cost: ${cost_data.monthly_total:.2f}",
                        f"Cost trend: {cost_data.trend}",
                    ],
                    implementation_steps=[
                        "Review AWS Cost Explorer",
                        "Identify top cost contributors",
                        "Evaluate Reserved Instances or Savings Plans",
                        "Implement cost allocation tags",
                    ],
                )
            )

        self._recommendations.extend(recommendations)
        return recommendations

    async def analyze_deployment_pipeline(
        self,
        pipeline_config: PipelineConfig,
        deployment_history: list[DeploymentEvent],
    ) -> list[ProactiveRecommendation]:
        """Analyze and recommend pipeline improvements.

        Args:
            pipeline_config: Current pipeline configuration
            deployment_history: Recent deployment history

        Returns:
            List of recommendations
        """
        recommendations = []

        # Check for security scanning
        if not pipeline_config.has_security_scan:
            recommendations.append(
                self._create_recommendation(
                    category=RecommendationCategory.DEPLOYMENT_PIPELINE,
                    priority=RecommendationPriority.CRITICAL,
                    title="Add security scanning to pipeline",
                    description=(
                        "No security scanning in deployment pipeline. "
                        "Add SAST, DAST, and dependency scanning."
                    ),
                    impact="Prevent security vulnerabilities in production",
                    effort=ImplementationEffort.MEDIUM,
                    evidence=["Security scanning not configured"],
                    implementation_steps=[
                        "Add SAST tool (e.g., SonarQube, CodeQL)",
                        "Add dependency scanning (e.g., Snyk, Dependabot)",
                        "Configure security gates to fail builds",
                        "Set up vulnerability reporting",
                    ],
                )
            )

        # Check for tests
        if not pipeline_config.has_tests:
            recommendations.append(
                self._create_recommendation(
                    category=RecommendationCategory.DEPLOYMENT_PIPELINE,
                    priority=RecommendationPriority.CRITICAL,
                    title="Add automated testing to pipeline",
                    description=(
                        "No automated tests in pipeline. "
                        "Add unit, integration, and end-to-end tests."
                    ),
                    impact="Reduce production incidents by 60-80%",
                    effort=ImplementationEffort.HIGH,
                    evidence=["Automated testing not configured"],
                    implementation_steps=[
                        "Add unit test stage",
                        "Add integration test stage",
                        "Configure code coverage requirements",
                        "Add test reporting",
                    ],
                )
            )

        # Check for approval gates
        if not pipeline_config.has_approval_gate:
            recommendations.append(
                self._create_recommendation(
                    category=RecommendationCategory.DEPLOYMENT_PIPELINE,
                    priority=RecommendationPriority.MEDIUM,
                    title="Add manual approval gate for production",
                    description=(
                        "No approval gate for production deployments. "
                        "Add human review for production changes."
                    ),
                    impact="Prevent unauthorized production changes",
                    effort=ImplementationEffort.LOW,
                    evidence=["Approval gate not configured"],
                    implementation_steps=[
                        "Add approval stage before production",
                        "Configure approvers list",
                        "Set up notifications for pending approvals",
                    ],
                )
            )

        # Analyze failure rate
        if deployment_history:
            failures = [d for d in deployment_history if not d.success]
            failure_rate = len(failures) / len(deployment_history)

            if failure_rate > 0.1:
                recommendations.append(
                    self._create_recommendation(
                        category=RecommendationCategory.DEPLOYMENT_PIPELINE,
                        priority=RecommendationPriority.HIGH,
                        title="Reduce deployment failure rate",
                        description=(
                            f"Deployment failure rate is {failure_rate:.1%}. "
                            "Investigate and address common failure causes."
                        ),
                        impact="Improved deployment reliability",
                        effort=ImplementationEffort.MEDIUM,
                        evidence=[
                            f"Failure rate: {failure_rate:.1%}",
                            f"Failed deployments: {len(failures)}",
                        ],
                        implementation_steps=[
                            "Analyze deployment failure logs",
                            "Identify common failure patterns",
                            "Add pre-deployment validation",
                            "Improve test coverage",
                        ],
                    )
                )

        # Check MTTR
        if pipeline_config.mean_time_to_recovery_minutes > 60:
            recommendations.append(
                self._create_recommendation(
                    category=RecommendationCategory.DEPLOYMENT_PIPELINE,
                    priority=RecommendationPriority.HIGH,
                    title="Improve mean time to recovery",
                    description=(
                        f"MTTR is {pipeline_config.mean_time_to_recovery_minutes:.0f} minutes. "
                        "Implement faster rollback and recovery procedures."
                    ),
                    impact="Reduce incident duration by 50%",
                    effort=ImplementationEffort.MEDIUM,
                    evidence=[
                        f"Current MTTR: {pipeline_config.mean_time_to_recovery_minutes:.0f} min"
                    ],
                    implementation_steps=[
                        "Implement automated rollback",
                        "Create runbooks for common issues",
                        "Add deployment health checks",
                        "Configure auto-rollback on failure",
                    ],
                )
            )

        self._recommendations.extend(recommendations)
        return recommendations

    async def analyze_resilience(
        self,
        architecture: ArchitectureSpec,
        incident_history: list[IncidentRecord],
    ) -> list[ProactiveRecommendation]:
        """Analyze and recommend resilience improvements.

        Args:
            architecture: Application architecture spec
            incident_history: Historical incident records

        Returns:
            List of recommendations
        """
        recommendations = []

        # Check circuit breakers
        if not architecture.has_circuit_breakers:
            recommendations.append(
                self._create_recommendation(
                    category=RecommendationCategory.APPLICATION_RESILIENCE,
                    priority=RecommendationPriority.HIGH,
                    title="Implement circuit breakers",
                    description=(
                        "No circuit breakers detected. Add circuit breakers "
                        "to prevent cascade failures."
                    ),
                    impact="Prevent cascade failures, improve availability",
                    effort=ImplementationEffort.MEDIUM,
                    evidence=["Circuit breakers not implemented"],
                    implementation_steps=[
                        "Identify critical service dependencies",
                        "Implement circuit breaker pattern",
                        "Configure timeout and retry settings",
                        "Add fallback behaviors",
                    ],
                )
            )

        # Check rate limiting
        if not architecture.has_rate_limiting:
            recommendations.append(
                self._create_recommendation(
                    category=RecommendationCategory.APPLICATION_RESILIENCE,
                    priority=RecommendationPriority.HIGH,
                    title="Implement rate limiting",
                    description=(
                        "No rate limiting detected. Add rate limiting "
                        "to protect against traffic spikes and abuse."
                    ),
                    impact="Protection against traffic spikes and DDoS",
                    effort=ImplementationEffort.MEDIUM,
                    evidence=["Rate limiting not implemented"],
                    implementation_steps=[
                        "Define rate limits per endpoint",
                        "Implement token bucket algorithm",
                        "Add WAF rate limiting rules",
                        "Configure appropriate responses",
                    ],
                )
            )

        # Check health checks
        if not architecture.has_health_checks:
            recommendations.append(
                self._create_recommendation(
                    category=RecommendationCategory.APPLICATION_RESILIENCE,
                    priority=RecommendationPriority.HIGH,
                    title="Implement health checks",
                    description=(
                        "No health check endpoints detected. Add health checks "
                        "for load balancer and orchestrator integration."
                    ),
                    impact="Faster failure detection and recovery",
                    effort=ImplementationEffort.LOW,
                    evidence=["Health checks not implemented"],
                    implementation_steps=[
                        "Add /health endpoint to services",
                        "Include dependency checks",
                        "Configure load balancer health checks",
                        "Set up readiness and liveness probes",
                    ],
                )
            )

        # Analyze incident patterns
        if incident_history:
            # Find recurring issues
            recurring_services = self._find_recurring_incident_services(
                incident_history
            )
            if recurring_services:
                recommendations.append(
                    self._create_recommendation(
                        category=RecommendationCategory.APPLICATION_RESILIENCE,
                        priority=RecommendationPriority.HIGH,
                        title="Address recurring incident patterns",
                        description=(
                            f"Services with recurring incidents: {recurring_services}. "
                            "Investigate and address root causes."
                        ),
                        impact="Reduce incident frequency by 50%",
                        effort=ImplementationEffort.HIGH,
                        evidence=[f"Services with 3+ incidents: {recurring_services}"],
                        implementation_steps=[
                            "Conduct root cause analysis",
                            "Implement permanent fixes",
                            "Add monitoring for early detection",
                            "Update runbooks",
                        ],
                    )
                )

        self._recommendations.extend(recommendations)
        return recommendations

    async def get_all_recommendations(
        self,
        category: Optional[RecommendationCategory] = None,
        priority: Optional[RecommendationPriority] = None,
    ) -> list[ProactiveRecommendation]:
        """Get all recommendations with optional filtering.

        Args:
            category: Filter by category
            priority: Filter by priority

        Returns:
            Filtered recommendations
        """
        recs = self._recommendations

        if category:
            recs = [r for r in recs if r.category == category]

        if priority:
            recs = [r for r in recs if r.priority == priority]

        return recs

    def get_recommendation_summary(self) -> RecommendationSummary:
        """Get summary of all recommendations.

        Returns:
            Recommendation summary
        """
        by_category: dict[str, int] = {}
        by_priority: dict[str, int] = {}

        for rec in self._recommendations:
            cat = rec.category.value
            pri = rec.priority.value
            by_category[cat] = by_category.get(cat, 0) + 1
            by_priority[pri] = by_priority.get(pri, 0) + 1

        return RecommendationSummary(
            total_count=len(self._recommendations),
            by_category=by_category,
            by_priority=by_priority,
            estimated_total_impact="Significant improvement in reliability and cost",
        )

    def _create_recommendation(
        self,
        category: RecommendationCategory,
        priority: RecommendationPriority,
        title: str,
        description: str,
        impact: str,
        effort: ImplementationEffort,
        evidence: list[str],
        implementation_steps: list[str],
        affected_resources: Optional[list[str]] = None,
    ) -> ProactiveRecommendation:
        """Create recommendation with auto-generated ID."""
        self._rec_counter += 1
        return ProactiveRecommendation(
            recommendation_id=f"REC-{self._rec_counter:04d}",
            category=category,
            priority=priority,
            title=title,
            description=description,
            impact=impact,
            effort=effort,
            evidence=evidence,
            implementation_steps=implementation_steps,
            affected_resources=affected_resources or [],
        )

    def _find_underutilized_resources(self, resource_graph: ResourceGraph) -> list[str]:
        """Find underutilized resources in graph."""
        underutilized = []
        for node in resource_graph.nodes:
            if node.get("cpu_utilization", 100) < 20:
                underutilized.append(node.get("id", "unknown"))
        return underutilized

    def _find_single_points_of_failure(
        self, resource_graph: ResourceGraph
    ) -> list[str]:
        """Find single points of failure."""
        spofs = []
        # Simple heuristic: nodes with many incoming edges but no redundancy
        for node in resource_graph.nodes:
            if node.get("incoming_edges", 0) > 3 and not node.get(
                "has_redundancy", False
            ):
                spofs.append(node.get("id", "unknown"))
        return spofs

    def _find_recurring_incident_services(
        self, incidents: list[IncidentRecord]
    ) -> list[str]:
        """Find services with recurring incidents."""
        service_counts: dict[str, int] = {}
        for incident in incidents:
            svc = incident.service
            service_counts[svc] = service_counts.get(svc, 0) + 1

        return [svc for svc, count in service_counts.items() if count >= 3]

    def get_service_stats(self) -> dict:
        """Get service statistics."""
        return {
            "total_recommendations": len(self._recommendations),
            "by_category": {
                cat.value: len([r for r in self._recommendations if r.category == cat])
                for cat in RecommendationCategory
            },
        }
