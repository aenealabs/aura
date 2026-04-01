"""
Deployment History Correlator Service - AWS DevOps Agent Parity

Implements comprehensive deployment tracking and incident correlation:
- Deployment event tracking and timeline
- Change-to-incident correlation (86% accuracy target)
- Blast radius analysis
- Rollback recommendations
- Deployment health scoring
- CI/CD pipeline integration

Reference: ADR-030 Section 5.3 DevOps Agent Components
"""

import statistics
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, cast

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================


class DeploymentStatus(str, Enum):
    """Status of a deployment."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class DeploymentType(str, Enum):
    """Type of deployment."""

    ROLLING = "rolling"
    BLUE_GREEN = "blue_green"
    CANARY = "canary"
    RECREATE = "recreate"
    FEATURE_FLAG = "feature_flag"
    DATABASE_MIGRATION = "database_migration"
    INFRASTRUCTURE = "infrastructure"
    CONFIGURATION = "configuration"


class ChangeCategory(str, Enum):
    """Category of change in deployment."""

    CODE = "code"
    CONFIGURATION = "configuration"
    INFRASTRUCTURE = "infrastructure"
    DEPENDENCY = "dependency"
    DATABASE = "database"
    SECURITY = "security"
    FEATURE_FLAG = "feature_flag"


class IncidentSeverity(str, Enum):
    """Severity of an incident."""

    SEV1 = "sev1"  # Critical - full outage
    SEV2 = "sev2"  # Major - significant impact
    SEV3 = "sev3"  # Minor - limited impact
    SEV4 = "sev4"  # Low - minimal impact


class CorrelationConfidence(str, Enum):
    """Confidence level of correlation."""

    HIGH = "high"  # >80% confidence
    MEDIUM = "medium"  # 50-80% confidence
    LOW = "low"  # <50% confidence


class RiskLevel(str, Enum):
    """Risk level for deployments."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class DeploymentChange:
    """A single change included in a deployment."""

    change_id: str
    category: ChangeCategory
    description: str
    files_changed: list[str] = field(default_factory=list)
    commit_sha: str = ""
    author: str = ""
    ticket_id: str = ""
    risk_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeploymentArtifact:
    """An artifact deployed."""

    artifact_id: str
    name: str
    version: str
    artifact_type: str  # container, lambda, config, etc.
    registry: str = ""
    sha256: str = ""
    size_bytes: int = 0
    build_id: str = ""


@dataclass
class DeploymentTarget:
    """Target environment/resource for deployment."""

    target_id: str
    name: str
    environment: str  # prod, staging, dev
    region: str
    resource_type: str  # eks, ecs, lambda, ec2, etc.
    replica_count: int = 1
    current_version: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeploymentMetrics:
    """Metrics captured during deployment."""

    duration_seconds: float = 0.0
    replicas_updated: int = 0
    replicas_failed: int = 0
    rollback_count: int = 0
    health_check_failures: int = 0
    error_rate_before: float = 0.0
    error_rate_after: float = 0.0
    latency_p50_before: float = 0.0
    latency_p50_after: float = 0.0
    latency_p99_before: float = 0.0
    latency_p99_after: float = 0.0
    cpu_utilization_delta: float = 0.0
    memory_utilization_delta: float = 0.0


@dataclass
class Deployment:
    """A deployment event."""

    deployment_id: str
    name: str
    description: str
    deployment_type: DeploymentType
    status: DeploymentStatus

    # What was deployed
    changes: list[DeploymentChange]
    artifacts: list[DeploymentArtifact]

    # Where it was deployed
    targets: list[DeploymentTarget]
    environment: str

    # Who and when
    initiated_by: str
    approved_by: str | None = None

    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    # Pipeline info
    pipeline_id: str = ""
    pipeline_run_id: str = ""

    # Metrics and health
    metrics: DeploymentMetrics = field(default_factory=DeploymentMetrics)
    health_score: float = 100.0

    # Risk assessment
    risk_level: RiskLevel = RiskLevel.LOW
    risk_factors: list[str] = field(default_factory=list)

    # Related items
    ticket_ids: list[str] = field(default_factory=list)
    related_incidents: list[str] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Incident:
    """An incident that may be correlated with deployments."""

    incident_id: str
    title: str
    description: str
    severity: IncidentSeverity
    status: str  # open, investigating, resolved, closed

    # Impact
    affected_services: list[str]
    affected_regions: list[str]
    customer_impact: str

    # Timeline
    detected_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None

    # Metrics during incident
    error_rate_peak: float = 0.0
    latency_p99_peak: float = 0.0
    requests_affected: int = 0

    # Root cause
    root_cause: str = ""
    root_cause_category: str = ""

    # Related
    related_deployments: list[str] = field(default_factory=list)
    related_alerts: list[str] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeploymentCorrelation:
    """Correlation between a deployment and an incident."""

    correlation_id: str
    deployment_id: str
    incident_id: str
    confidence: CorrelationConfidence
    confidence_score: float  # 0.0 to 1.0

    # Why we think they're correlated
    correlation_factors: list[str]
    timeline_analysis: str
    change_analysis: str

    # Impact assessment
    estimated_impact: str
    blast_radius: list[str]

    # Recommendations
    recommended_action: str
    rollback_recommended: bool = False

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class BlastRadiusAnalysis:
    """Analysis of potential blast radius for a deployment."""

    deployment_id: str

    # Direct impact
    directly_affected_services: list[str]
    directly_affected_regions: list[str]

    # Indirect impact (dependencies)
    downstream_services: list[str]
    upstream_services: list[str]

    # Data impact
    affected_data_stores: list[str]
    affected_queues: list[str]

    # User impact estimation
    estimated_users_affected: int
    estimated_requests_per_minute: int

    # Risk score
    total_blast_radius_score: float
    risk_factors: list[str]


@dataclass
class RollbackRecommendation:
    """Recommendation for rollback."""

    recommendation_id: str
    deployment_id: str
    should_rollback: bool
    confidence: float

    # Reasoning
    reasons: list[str]
    evidence: list[str]

    # Rollback plan
    rollback_steps: list[str]
    estimated_rollback_time: str
    rollback_risks: list[str]

    # Alternative actions
    alternative_actions: list[str]

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DeploymentHealthReport:
    """Health report for recent deployments."""

    report_id: str
    time_range_start: datetime
    time_range_end: datetime

    # Deployment stats
    total_deployments: int
    successful_deployments: int
    failed_deployments: int
    rolled_back_deployments: int

    # Success metrics
    success_rate: float
    mean_time_to_deploy: float
    mean_time_to_rollback: float

    # Quality metrics
    deployments_causing_incidents: int
    incident_correlation_rate: float

    # By environment
    deployments_by_environment: dict[str, int]
    success_rate_by_environment: dict[str, float]

    # Trends
    deployment_frequency_trend: str  # increasing, stable, decreasing
    quality_trend: str

    # Top issues
    top_failure_reasons: list[dict[str, Any]]
    high_risk_services: list[str]


@dataclass
class ChangeWindow:
    """A change window for deployments."""

    window_id: str
    name: str
    start_time: datetime
    end_time: datetime
    environment: str
    is_frozen: bool = False
    approved_deployments: list[str] = field(default_factory=list)
    restrictions: list[str] = field(default_factory=list)


# =============================================================================
# Deployment History Correlator Service
# =============================================================================


class DeploymentHistoryCorrelator:
    """
    Comprehensive deployment tracking and incident correlation service.

    Provides:
    - Deployment event tracking
    - Change-to-incident correlation (86% accuracy)
    - Blast radius analysis
    - Rollback recommendations
    - Deployment health scoring
    """

    def __init__(
        self,
        neptune_client: Any = None,
        opensearch_client: Any = None,
        cloudwatch_client: Any = None,
        llm_client: Any = None,
    ):
        self._neptune = neptune_client
        self._opensearch = opensearch_client
        self._cloudwatch = cloudwatch_client
        self._llm = llm_client

        # In-memory storage (production would use Neptune/OpenSearch)
        self._deployments: dict[str, Deployment] = {}
        self._incidents: dict[str, Incident] = {}
        self._correlations: dict[str, DeploymentCorrelation] = {}
        self._change_windows: dict[str, ChangeWindow] = {}

        # Service dependency graph (would be populated from Neptune)
        self._service_dependencies: dict[str, list[str]] = {}

        # Correlation weights for ML model
        self._correlation_weights = {
            "time_proximity": 0.35,
            "service_overlap": 0.25,
            "change_type_match": 0.20,
            "historical_pattern": 0.20,
        }

        self._logger = logger.bind(service="deployment_history_correlator")

    # =========================================================================
    # Deployment Tracking
    # =========================================================================

    async def record_deployment(self, deployment: Deployment) -> Deployment:
        """
        Record a new deployment event.

        Args:
            deployment: The deployment to record

        Returns:
            Recorded deployment with calculated risk
        """
        # Calculate risk score
        deployment.risk_level, deployment.risk_factors = (
            await self._assess_deployment_risk(deployment)
        )

        # Calculate health score based on metrics
        if deployment.status == DeploymentStatus.SUCCEEDED:
            deployment.health_score = self._calculate_health_score(deployment)

        # Store deployment
        self._deployments[deployment.deployment_id] = deployment

        # Index in OpenSearch for search
        if self._opensearch:
            await self._index_deployment(deployment)

        # Store in Neptune for graph queries
        if self._neptune:
            await self._store_deployment_graph(deployment)

        self._logger.info(
            "Deployment recorded",
            deployment_id=deployment.deployment_id,
            status=deployment.status.value,
            risk_level=deployment.risk_level.value,
            health_score=deployment.health_score,
        )

        return deployment

    async def update_deployment_status(
        self,
        deployment_id: str,
        status: DeploymentStatus,
        metrics: DeploymentMetrics | None = None,
    ) -> Deployment:
        """Update deployment status and metrics."""
        deployment = self._deployments.get(deployment_id)
        if not deployment:
            raise ValueError(f"Deployment not found: {deployment_id}")

        deployment.status = status

        if status in [
            DeploymentStatus.SUCCEEDED,
            DeploymentStatus.FAILED,
            DeploymentStatus.ROLLED_BACK,
        ]:
            deployment.completed_at = datetime.now(timezone.utc)

        if metrics:
            deployment.metrics = metrics
            deployment.health_score = self._calculate_health_score(deployment)

        # Check for incident correlation on completion
        if status in [DeploymentStatus.SUCCEEDED, DeploymentStatus.FAILED]:
            await self._check_for_correlations(deployment)

        return deployment

    async def _assess_deployment_risk(
        self, deployment: Deployment
    ) -> tuple[RiskLevel, list[str]]:
        """Assess risk level of a deployment."""
        risk_factors = []
        risk_score = 0.0

        # Check environment
        if deployment.environment == "production":
            risk_score += 20
            risk_factors.append("Production deployment")

        # Check deployment type
        if deployment.deployment_type == DeploymentType.RECREATE:
            risk_score += 15
            risk_factors.append("Recreate deployment (service interruption)")
        elif deployment.deployment_type == DeploymentType.DATABASE_MIGRATION:
            risk_score += 25
            risk_factors.append("Database migration")

        # Check change categories
        for change in deployment.changes:
            if change.category == ChangeCategory.DATABASE:
                risk_score += 20
                risk_factors.append(f"Database change: {change.description[:50]}")
            elif change.category == ChangeCategory.INFRASTRUCTURE:
                risk_score += 15
                risk_factors.append(f"Infrastructure change: {change.description[:50]}")
            elif change.category == ChangeCategory.SECURITY:
                risk_score += 10
                risk_factors.append(f"Security change: {change.description[:50]}")

        # Check number of changes
        if len(deployment.changes) > 10:
            risk_score += 15
            risk_factors.append(f"Large change set ({len(deployment.changes)} changes)")

        # Check number of targets
        if len(deployment.targets) > 5:
            risk_score += 10
            risk_factors.append(
                f"Multi-target deployment ({len(deployment.targets)} targets)"
            )

        # Check time of deployment
        hour = deployment.started_at.hour
        if hour < 6 or hour > 22:
            risk_score += 10
            risk_factors.append("Off-hours deployment")

        # Check change window
        if not await self._is_in_change_window(deployment):
            risk_score += 15
            risk_factors.append("Outside approved change window")

        # Check historical incident rate for affected services
        incident_rate = await self._get_historical_incident_rate(
            [t.name for t in deployment.targets]
        )
        if incident_rate > 0.1:  # >10% incident rate
            risk_score += 20
            risk_factors.append(f"High historical incident rate ({incident_rate:.1%})")

        # Determine risk level
        if risk_score >= 60:
            level = RiskLevel.CRITICAL
        elif risk_score >= 40:
            level = RiskLevel.HIGH
        elif risk_score >= 20:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW

        return level, risk_factors

    def _calculate_health_score(self, deployment: Deployment) -> float:
        """Calculate deployment health score (0-100)."""
        score = 100.0
        metrics = deployment.metrics

        # Penalize for failures
        if metrics.replicas_failed > 0:
            failure_rate = metrics.replicas_failed / max(
                metrics.replicas_updated + metrics.replicas_failed, 1
            )
            score -= failure_rate * 30

        # Penalize for health check failures
        if metrics.health_check_failures > 0:
            score -= min(metrics.health_check_failures * 5, 20)

        # Penalize for error rate increase
        if metrics.error_rate_after > metrics.error_rate_before:
            error_increase = metrics.error_rate_after - metrics.error_rate_before
            score -= min(error_increase * 100, 25)

        # Penalize for latency increase
        if metrics.latency_p99_after > metrics.latency_p99_before:
            latency_increase = (
                metrics.latency_p99_after - metrics.latency_p99_before
            ) / max(metrics.latency_p99_before, 1)
            score -= min(latency_increase * 50, 15)

        # Penalize for rollbacks
        if metrics.rollback_count > 0:
            score -= metrics.rollback_count * 10

        return max(0.0, score)

    async def _is_in_change_window(self, deployment: Deployment) -> bool:
        """Check if deployment is within approved change window."""
        now = deployment.started_at

        for window in self._change_windows.values():
            if window.environment != deployment.environment:
                continue
            if window.is_frozen:
                continue
            if window.start_time <= now <= window.end_time:
                return True

        # Default: allow if no windows defined
        return len(self._change_windows) == 0

    async def _get_historical_incident_rate(
        self, services: list[str], days: int = 30
    ) -> float:
        """Get historical incident rate for services."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        total_deployments = 0
        incident_deployments = 0

        for deployment in self._deployments.values():
            if deployment.started_at < cutoff:
                continue

            deployment_services = [t.name for t in deployment.targets]
            if not any(s in services for s in deployment_services):
                continue

            total_deployments += 1
            if deployment.related_incidents:
                incident_deployments += 1

        return incident_deployments / max(total_deployments, 1)

    async def _index_deployment(self, deployment: Deployment) -> None:
        """Index deployment in OpenSearch."""
        # Production implementation

    async def _store_deployment_graph(self, deployment: Deployment) -> None:
        """Store deployment in Neptune graph."""
        # Production implementation

    # =========================================================================
    # Incident Correlation
    # =========================================================================

    async def record_incident(self, incident: Incident) -> Incident:
        """Record an incident and find correlated deployments."""
        self._incidents[incident.incident_id] = incident

        # Find correlated deployments
        correlations = await self.correlate_incident_to_deployments(incident)

        # Update incident with related deployments
        incident.related_deployments = [c.deployment_id for c in correlations]

        # Update deployments with related incident
        for correlation in correlations:
            deployment = self._deployments.get(correlation.deployment_id)
            if deployment:
                deployment.related_incidents.append(incident.incident_id)

        self._logger.info(
            "Incident recorded",
            incident_id=incident.incident_id,
            severity=incident.severity.value,
            correlated_deployments=len(correlations),
        )

        return incident

    async def correlate_incident_to_deployments(
        self, incident: Incident, time_window_hours: int = 4
    ) -> list[DeploymentCorrelation]:
        """
        Find deployments that may have caused an incident.

        Uses multiple signals for 86% accuracy target:
        - Time proximity
        - Service overlap
        - Change type matching
        - Historical patterns

        Args:
            incident: The incident to correlate
            time_window_hours: Hours before incident to search

        Returns:
            List of deployment correlations sorted by confidence
        """
        correlations = []

        # Find deployments in time window
        window_start = incident.detected_at - timedelta(hours=time_window_hours)

        candidate_deployments = [
            d
            for d in self._deployments.values()
            if d.started_at >= window_start and d.started_at <= incident.detected_at
        ]

        for deployment in candidate_deployments:
            correlation = await self._calculate_correlation(deployment, incident)
            if correlation.confidence_score >= 0.3:  # Minimum threshold
                correlations.append(correlation)
                self._correlations[correlation.correlation_id] = correlation

        # Sort by confidence
        correlations.sort(key=lambda c: c.confidence_score, reverse=True)

        return correlations

    async def _calculate_correlation(
        self, deployment: Deployment, incident: Incident
    ) -> DeploymentCorrelation:
        """Calculate correlation between deployment and incident."""
        factors = []

        # Time proximity score (0-1)
        time_delta = (incident.detected_at - deployment.started_at).total_seconds()
        if time_delta < 0:
            time_score = 0.0
        elif time_delta < 900:  # 15 minutes
            time_score = 1.0
            factors.append(
                f"Incident occurred {time_delta/60:.0f} minutes after deployment"
            )
        elif time_delta < 3600:  # 1 hour
            time_score = 0.8
            factors.append(
                f"Incident occurred {time_delta/60:.0f} minutes after deployment"
            )
        elif time_delta < 7200:  # 2 hours
            time_score = 0.5
            factors.append(
                f"Incident occurred {time_delta/3600:.1f} hours after deployment"
            )
        else:
            time_score = 0.3
            factors.append(
                f"Incident occurred {time_delta/3600:.1f} hours after deployment"
            )

        # Service overlap score (0-1)
        deployment_services = {t.name for t in deployment.targets}
        incident_services = set(incident.affected_services)

        if deployment_services & incident_services:
            overlap = len(deployment_services & incident_services) / len(
                incident_services
            )
            service_score = overlap
            factors.append(
                f"Service overlap: {deployment_services & incident_services}"
            )
        else:
            # Check for downstream dependencies
            downstream = await self._get_downstream_services(list(deployment_services))
            if set(downstream) & incident_services:
                service_score = 0.5
                factors.append("Incident in downstream service")
            else:
                service_score = 0.1

        # Change type match score (0-1)
        change_score = 0.0
        change_categories = [c.category for c in deployment.changes]

        if incident.root_cause_category:
            category_match = {
                "database": ChangeCategory.DATABASE,
                "configuration": ChangeCategory.CONFIGURATION,
                "code": ChangeCategory.CODE,
                "infrastructure": ChangeCategory.INFRASTRUCTURE,
            }
            if (
                category_match.get(incident.root_cause_category.lower())
                in change_categories
            ):
                change_score = 1.0
                factors.append(
                    f"Change type matches root cause: {incident.root_cause_category}"
                )

        if change_score == 0.0:
            # Score based on change risk
            if ChangeCategory.DATABASE in change_categories:
                change_score = 0.7
                factors.append("Database changes present")
            elif ChangeCategory.INFRASTRUCTURE in change_categories:
                change_score = 0.6
                factors.append("Infrastructure changes present")
            elif ChangeCategory.CONFIGURATION in change_categories:
                change_score = 0.5
                factors.append("Configuration changes present")
            else:
                change_score = 0.3

        # Historical pattern score (0-1)
        history_score = await self._check_historical_pattern(deployment, incident)
        if history_score > 0.5:
            factors.append("Historical pattern match")

        # Calculate weighted score
        confidence_score = (
            time_score * self._correlation_weights["time_proximity"]
            + service_score * self._correlation_weights["service_overlap"]
            + change_score * self._correlation_weights["change_type_match"]
            + history_score * self._correlation_weights["historical_pattern"]
        )

        # Determine confidence level
        if confidence_score >= 0.8:
            confidence = CorrelationConfidence.HIGH
        elif confidence_score >= 0.5:
            confidence = CorrelationConfidence.MEDIUM
        else:
            confidence = CorrelationConfidence.LOW

        # Generate timeline analysis
        timeline_analysis = self._generate_timeline_analysis(deployment, incident)

        # Generate change analysis
        change_analysis = self._generate_change_analysis(deployment, incident)

        # Determine blast radius
        blast_radius = await self._get_blast_radius_services(deployment)

        # Determine recommended action
        if confidence_score >= 0.7 and incident.severity in [
            IncidentSeverity.SEV1,
            IncidentSeverity.SEV2,
        ]:
            recommended_action = "Consider immediate rollback"
            rollback_recommended = True
        elif confidence_score >= 0.5:
            recommended_action = "Investigate deployment changes"
            rollback_recommended = False
        else:
            recommended_action = "Monitor situation"
            rollback_recommended = False

        return DeploymentCorrelation(
            correlation_id=str(uuid.uuid4()),
            deployment_id=deployment.deployment_id,
            incident_id=incident.incident_id,
            confidence=confidence,
            confidence_score=confidence_score,
            correlation_factors=factors,
            timeline_analysis=timeline_analysis,
            change_analysis=change_analysis,
            estimated_impact=f"{incident.severity.value} incident affecting {len(incident.affected_services)} services",
            blast_radius=blast_radius,
            recommended_action=recommended_action,
            rollback_recommended=rollback_recommended,
        )

    async def _get_downstream_services(self, services: list[str]) -> list[str]:
        """Get downstream dependent services."""
        downstream = []
        for service in services:
            downstream.extend(self._service_dependencies.get(service, []))
        return list(set(downstream))

    async def _check_historical_pattern(
        self, deployment: Deployment, incident: Incident
    ) -> float:
        """Check if this pattern has caused incidents before."""
        # Get similar past deployments
        similar_deployments = []

        change_categories = {c.category for c in deployment.changes}
        deployment_services = {t.name for t in deployment.targets}

        for past_deployment in self._deployments.values():
            if past_deployment.deployment_id == deployment.deployment_id:
                continue

            past_categories = {c.category for c in past_deployment.changes}
            past_services = {t.name for t in past_deployment.targets}

            if (
                past_categories & change_categories
                and past_services & deployment_services
            ):
                similar_deployments.append(past_deployment)

        if not similar_deployments:
            return 0.0

        # Check how many similar deployments caused incidents
        incident_count = sum(1 for d in similar_deployments if d.related_incidents)

        return incident_count / len(similar_deployments)

    def _generate_timeline_analysis(
        self, deployment: Deployment, incident: Incident
    ) -> str:
        """Generate timeline analysis narrative."""
        time_delta = (incident.detected_at - deployment.started_at).total_seconds()

        lines = [
            f"Deployment '{deployment.name}' started at {deployment.started_at.strftime('%H:%M:%S UTC')}",
        ]

        if deployment.completed_at:
            lines.append(
                f"Deployment completed at {deployment.completed_at.strftime('%H:%M:%S UTC')}"
            )

        lines.append(
            f"Incident detected at {incident.detected_at.strftime('%H:%M:%S UTC')} "
            f"({time_delta/60:.0f} minutes after deployment start)"
        )

        return " → ".join(lines)

    def _generate_change_analysis(
        self, deployment: Deployment, incident: Incident
    ) -> str:
        """Generate change analysis narrative."""
        lines = []

        for change in deployment.changes[:5]:  # Top 5 changes
            lines.append(f"- {change.category.value}: {change.description[:100]}")

        if len(deployment.changes) > 5:
            lines.append(f"- ... and {len(deployment.changes) - 5} more changes")

        return "\n".join(lines)

    async def _get_blast_radius_services(self, deployment: Deployment) -> list[str]:
        """Get all services in blast radius."""
        services = {t.name for t in deployment.targets}

        # Add downstream dependencies
        for service in list(services):
            services.update(self._service_dependencies.get(service, []))

        return list(services)

    async def _check_for_correlations(self, deployment: Deployment) -> None:
        """Check for correlations after deployment completion."""
        # Look for incidents that occurred shortly after deployment
        window_end = datetime.now(timezone.utc)
        window_start = deployment.completed_at or deployment.started_at

        for incident in self._incidents.values():
            if window_start <= incident.detected_at <= window_end:
                correlation = await self._calculate_correlation(deployment, incident)
                if correlation.confidence_score >= 0.5:
                    self._correlations[correlation.correlation_id] = correlation
                    deployment.related_incidents.append(incident.incident_id)

    # =========================================================================
    # Blast Radius Analysis
    # =========================================================================

    async def analyze_blast_radius(self, deployment: Deployment) -> BlastRadiusAnalysis:
        """
        Analyze potential blast radius of a deployment.

        Args:
            deployment: The deployment to analyze

        Returns:
            Blast radius analysis
        """
        # Direct impact
        directly_affected = [t.name for t in deployment.targets]
        directly_affected_regions = list({t.region for t in deployment.targets})

        # Downstream services
        downstream = []
        for service in directly_affected:
            downstream.extend(self._service_dependencies.get(service, []))
        downstream = list(set(downstream) - set(directly_affected))

        # Upstream services (services that depend on affected services)
        upstream = []
        for service, deps in self._service_dependencies.items():
            if any(affected in deps for affected in directly_affected):
                upstream.append(service)
        upstream = list(set(upstream) - set(directly_affected))

        # Data stores and queues (from deployment metadata)
        data_stores: list[str] = []
        queues: list[str] = []
        for change in deployment.changes:
            if change.category == ChangeCategory.DATABASE:
                data_stores.append(change.description.split()[0])

        # Estimate user impact
        total_replicas = sum(t.replica_count for t in deployment.targets)
        estimated_users = total_replicas * 1000  # Simplified estimation
        estimated_rpm = total_replicas * 100

        # Calculate blast radius score
        risk_factors = []
        score = 0.0

        score += len(directly_affected) * 10
        risk_factors.append(f"{len(directly_affected)} directly affected services")

        score += len(downstream) * 5
        if downstream:
            risk_factors.append(f"{len(downstream)} downstream services at risk")

        score += len(upstream) * 3
        if upstream:
            risk_factors.append(f"{len(upstream)} upstream services may be affected")

        if len(directly_affected_regions) > 1:
            score += 20
            risk_factors.append(
                f"Multi-region deployment ({len(directly_affected_regions)} regions)"
            )

        if data_stores:
            score += 15
            risk_factors.append(
                f"Database changes affecting {len(data_stores)} data stores"
            )

        return BlastRadiusAnalysis(
            deployment_id=deployment.deployment_id,
            directly_affected_services=directly_affected,
            directly_affected_regions=directly_affected_regions,
            downstream_services=downstream,
            upstream_services=upstream,
            affected_data_stores=data_stores,
            affected_queues=queues,
            estimated_users_affected=estimated_users,
            estimated_requests_per_minute=estimated_rpm,
            total_blast_radius_score=min(100, score),
            risk_factors=risk_factors,
        )

    # =========================================================================
    # Rollback Recommendations
    # =========================================================================

    async def recommend_rollback(
        self, deployment: Deployment, current_metrics: DeploymentMetrics | None = None
    ) -> RollbackRecommendation:
        """
        Generate rollback recommendation for a deployment.

        Args:
            deployment: The deployment to evaluate
            current_metrics: Current system metrics

        Returns:
            Rollback recommendation
        """
        reasons = []
        evidence = []
        confidence = 0.0

        metrics = current_metrics or deployment.metrics

        # Check error rate increase
        if metrics.error_rate_after > metrics.error_rate_before:
            error_increase = metrics.error_rate_after - metrics.error_rate_before
            if error_increase > 0.05:  # >5% increase
                reasons.append("Significant error rate increase")
                evidence.append(
                    f"Error rate increased from {metrics.error_rate_before:.2%} "
                    f"to {metrics.error_rate_after:.2%}"
                )
                confidence += 0.3

        # Check latency increase
        if metrics.latency_p99_after > metrics.latency_p99_before * 1.5:
            reasons.append("Significant latency increase")
            evidence.append(
                f"P99 latency increased from {metrics.latency_p99_before:.0f}ms "
                f"to {metrics.latency_p99_after:.0f}ms"
            )
            confidence += 0.2

        # Check health check failures
        if metrics.health_check_failures > 3:
            reasons.append("Multiple health check failures")
            evidence.append(f"{metrics.health_check_failures} health check failures")
            confidence += 0.2

        # Check for related incidents
        if deployment.related_incidents:
            sev1_sev2_incidents = [
                i
                for i in deployment.related_incidents
                if self._incidents.get(
                    i,
                    Incident(
                        incident_id="",
                        title="",
                        description="",
                        severity=IncidentSeverity.SEV4,
                        status="",
                        affected_services=[],
                        affected_regions=[],
                        customer_impact="",
                        detected_at=datetime.now(timezone.utc),
                    ),
                ).severity
                in [IncidentSeverity.SEV1, IncidentSeverity.SEV2]
            ]
            if sev1_sev2_incidents:
                reasons.append("Correlated with high-severity incident")
                evidence.append(
                    f"{len(sev1_sev2_incidents)} SEV1/SEV2 incidents detected"
                )
                confidence += 0.4

        # Check deployment health score
        if deployment.health_score < 70:
            reasons.append("Low deployment health score")
            evidence.append(f"Health score: {deployment.health_score:.0f}/100")
            confidence += 0.1

        should_rollback = confidence >= 0.5

        # Generate rollback steps
        rollback_steps = self._generate_rollback_steps(deployment)

        # Estimate rollback time
        estimated_time = self._estimate_rollback_time(deployment)

        # Identify rollback risks
        rollback_risks = self._identify_rollback_risks(deployment)

        # Generate alternative actions
        alternatives = []
        if not should_rollback:
            alternatives = [
                "Continue monitoring metrics closely",
                "Prepare rollback plan for quick execution if needed",
                "Enable feature flags to disable new functionality",
                "Scale up resources to handle increased load",
            ]

        return RollbackRecommendation(
            recommendation_id=str(uuid.uuid4()),
            deployment_id=deployment.deployment_id,
            should_rollback=should_rollback,
            confidence=min(1.0, confidence),
            reasons=reasons,
            evidence=evidence,
            rollback_steps=rollback_steps,
            estimated_rollback_time=estimated_time,
            rollback_risks=rollback_risks,
            alternative_actions=alternatives,
        )

    def _generate_rollback_steps(self, deployment: Deployment) -> list[str]:
        """Generate rollback steps based on deployment type."""
        steps = []

        if deployment.deployment_type == DeploymentType.BLUE_GREEN:
            steps = [
                "Switch traffic back to blue (previous) environment",
                "Verify blue environment is healthy",
                "Monitor error rates and latency",
                "Keep green environment for debugging",
            ]
        elif deployment.deployment_type == DeploymentType.CANARY:
            steps = [
                "Halt canary rollout immediately",
                "Route 100% traffic to stable version",
                "Terminate canary instances",
                "Verify service stability",
            ]
        elif deployment.deployment_type == DeploymentType.ROLLING:
            steps = [
                "Trigger rolling update with previous version",
                "Monitor deployment progress",
                "Verify each batch is healthy before continuing",
                "Complete rollback verification",
            ]
        elif deployment.deployment_type == DeploymentType.DATABASE_MIGRATION:
            steps = [
                "WARNING: Database rollback may require manual intervention",
                "Execute rollback migration script if available",
                "Verify data integrity",
                "Update application to use previous schema",
            ]
        else:
            steps = [
                "Deploy previous version using same deployment method",
                "Verify deployment completes successfully",
                "Monitor service health metrics",
                "Confirm incident is resolved",
            ]

        return steps

    def _estimate_rollback_time(self, deployment: Deployment) -> str:
        """Estimate rollback time."""
        if deployment.deployment_type == DeploymentType.BLUE_GREEN:
            return "1-2 minutes"
        elif deployment.deployment_type == DeploymentType.CANARY:
            return "2-5 minutes"
        elif deployment.deployment_type == DeploymentType.ROLLING:
            # Based on original deployment time
            original_duration = deployment.metrics.duration_seconds
            return f"{original_duration/60:.0f}-{original_duration/30:.0f} minutes"
        elif deployment.deployment_type == DeploymentType.DATABASE_MIGRATION:
            return "15-60 minutes (manual verification required)"
        else:
            return "5-15 minutes"

    def _identify_rollback_risks(self, deployment: Deployment) -> list[str]:
        """Identify risks associated with rollback."""
        risks = []

        # Check for database migrations
        if any(c.category == ChangeCategory.DATABASE for c in deployment.changes):
            risks.append("Database schema changes may not be reversible")

        # Check for data migrations
        if any("migration" in c.description.lower() for c in deployment.changes):
            risks.append(
                "Data migrations may have modified data in ways that require manual recovery"
            )

        # Check for API changes
        if any("api" in c.description.lower() for c in deployment.changes):
            risks.append("API contract changes may affect clients during rollback")

        # Check for infrastructure changes
        if any(c.category == ChangeCategory.INFRASTRUCTURE for c in deployment.changes):
            risks.append("Infrastructure changes may require manual cleanup")

        # General risks
        if deployment.deployment_type != DeploymentType.BLUE_GREEN:
            risks.append("Brief service interruption during rollback")

        return risks

    # =========================================================================
    # Health Reports
    # =========================================================================

    async def generate_health_report(self, days: int = 30) -> DeploymentHealthReport:
        """
        Generate deployment health report.

        Args:
            days: Number of days to include

        Returns:
            Deployment health report
        """
        report_id = str(uuid.uuid4())
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days)

        # Filter deployments in range
        deployments = [
            d for d in self._deployments.values() if d.started_at >= start_time
        ]

        total = len(deployments)
        succeeded = len(
            [d for d in deployments if d.status == DeploymentStatus.SUCCEEDED]
        )
        failed = len([d for d in deployments if d.status == DeploymentStatus.FAILED])
        rolled_back = len(
            [d for d in deployments if d.status == DeploymentStatus.ROLLED_BACK]
        )

        # Calculate metrics
        success_rate = succeeded / max(total, 1)

        durations = [
            d.metrics.duration_seconds
            for d in deployments
            if d.metrics.duration_seconds > 0
        ]
        mean_time_to_deploy = statistics.mean(durations) if durations else 0

        rollback_times = [
            d.metrics.duration_seconds
            for d in deployments
            if d.status == DeploymentStatus.ROLLED_BACK
        ]
        mean_time_to_rollback = statistics.mean(rollback_times) if rollback_times else 0

        # Incident correlation
        causing_incidents = len([d for d in deployments if d.related_incidents])
        correlation_rate = causing_incidents / max(total, 1)

        # By environment
        by_env: dict[str, list[Deployment]] = {}
        for d in deployments:
            if d.environment not in by_env:
                by_env[d.environment] = []
            by_env[d.environment].append(d)

        deployments_by_env = {env: len(deps) for env, deps in by_env.items()}
        success_by_env = {
            env: len([d for d in deps if d.status == DeploymentStatus.SUCCEEDED])
            / max(len(deps), 1)
            for env, deps in by_env.items()
        }

        # Trends
        first_half = [
            d
            for d in deployments
            if d.started_at < start_time + timedelta(days=days / 2)
        ]
        second_half = [
            d
            for d in deployments
            if d.started_at >= start_time + timedelta(days=days / 2)
        ]

        if len(second_half) > len(first_half) * 1.1:
            frequency_trend = "increasing"
        elif len(second_half) < len(first_half) * 0.9:
            frequency_trend = "decreasing"
        else:
            frequency_trend = "stable"

        first_success = len(
            [d for d in first_half if d.status == DeploymentStatus.SUCCEEDED]
        ) / max(len(first_half), 1)
        second_success = len(
            [d for d in second_half if d.status == DeploymentStatus.SUCCEEDED]
        ) / max(len(second_half), 1)

        if second_success > first_success + 0.05:
            quality_trend = "improving"
        elif second_success < first_success - 0.05:
            quality_trend = "declining"
        else:
            quality_trend = "stable"

        # Top failure reasons
        failure_reasons: dict[str, int] = {}
        for d in deployments:
            if d.status == DeploymentStatus.FAILED and d.risk_factors:
                for factor in d.risk_factors:
                    failure_reasons[factor] = failure_reasons.get(factor, 0) + 1

        top_failures = sorted(
            [{"reason": k, "count": v} for k, v in failure_reasons.items()],
            key=lambda x: cast(int, x["count"]),
            reverse=True,
        )[:5]

        # High risk services
        service_incidents: dict[str, int] = {}
        for d in deployments:
            if d.related_incidents:
                for t in d.targets:
                    service_incidents[t.name] = service_incidents.get(t.name, 0) + len(
                        d.related_incidents
                    )

        high_risk = sorted(
            [k for k, v in service_incidents.items() if v >= 2],
            key=lambda x: service_incidents[x],
            reverse=True,
        )[:5]

        return DeploymentHealthReport(
            report_id=report_id,
            time_range_start=start_time,
            time_range_end=end_time,
            total_deployments=total,
            successful_deployments=succeeded,
            failed_deployments=failed,
            rolled_back_deployments=rolled_back,
            success_rate=success_rate,
            mean_time_to_deploy=mean_time_to_deploy,
            mean_time_to_rollback=mean_time_to_rollback,
            deployments_causing_incidents=causing_incidents,
            incident_correlation_rate=correlation_rate,
            deployments_by_environment=deployments_by_env,
            success_rate_by_environment=success_by_env,
            deployment_frequency_trend=frequency_trend,
            quality_trend=quality_trend,
            top_failure_reasons=top_failures,
            high_risk_services=high_risk,
        )

    # =========================================================================
    # Change Window Management
    # =========================================================================

    def create_change_window(
        self,
        name: str,
        start_time: datetime,
        end_time: datetime,
        environment: str,
        restrictions: list[str] | None = None,
    ) -> ChangeWindow:
        """Create a change window for deployments."""
        window = ChangeWindow(
            window_id=str(uuid.uuid4()),
            name=name,
            start_time=start_time,
            end_time=end_time,
            environment=environment,
            restrictions=restrictions or [],
        )
        self._change_windows[window.window_id] = window
        return window

    def freeze_deployments(self, environment: str, reason: str) -> None:
        """Freeze all deployments for an environment."""
        for window in self._change_windows.values():
            if window.environment == environment:
                window.is_frozen = True
                window.restrictions.append(f"Frozen: {reason}")

        self._logger.warning(
            "Deployments frozen", environment=environment, reason=reason
        )

    def unfreeze_deployments(self, environment: str) -> None:
        """Unfreeze deployments for an environment."""
        for window in self._change_windows.values():
            if window.environment == environment:
                window.is_frozen = False

        self._logger.info("Deployments unfrozen", environment=environment)

    # =========================================================================
    # Service Dependencies
    # =========================================================================

    def register_service_dependency(self, service: str, depends_on: list[str]) -> None:
        """Register service dependencies for blast radius analysis."""
        self._service_dependencies[service] = depends_on

    def get_service_dependencies(self, service: str) -> list[str]:
        """Get dependencies for a service."""
        return self._service_dependencies.get(service, [])

    # =========================================================================
    # Query Methods
    # =========================================================================

    async def get_deployment(self, deployment_id: str) -> Deployment | None:
        """Get a deployment by ID."""
        return self._deployments.get(deployment_id)

    async def get_recent_deployments(
        self, environment: str | None = None, limit: int = 20
    ) -> list[Deployment]:
        """Get recent deployments."""
        deployments = list(self._deployments.values())

        if environment:
            deployments = [d for d in deployments if d.environment == environment]

        deployments.sort(key=lambda d: d.started_at, reverse=True)
        return deployments[:limit]

    async def get_deployments_for_service(
        self, service: str, limit: int = 10
    ) -> list[Deployment]:
        """Get deployments that affected a specific service."""
        deployments = [
            d
            for d in self._deployments.values()
            if any(t.name == service for t in d.targets)
        ]
        deployments.sort(key=lambda d: d.started_at, reverse=True)
        return deployments[:limit]

    async def get_correlations_for_incident(
        self, incident_id: str
    ) -> list[DeploymentCorrelation]:
        """Get all correlations for an incident."""
        return [c for c in self._correlations.values() if c.incident_id == incident_id]
