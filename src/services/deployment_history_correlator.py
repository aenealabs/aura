"""Deployment History Correlator Service

Implements ADR-037 Phase 3.1: Deployment History Correlator

Correlates incidents with deployment and configuration changes
to identify potential root causes and blast radius.

Key Features:
- Git commit correlation
- CI/CD pipeline integration
- Configuration change tracking
- Blast radius analysis
- Deployment timeline visualization
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)


class DeploymentEventType(Enum):
    """Types of deployment events."""

    DEPLOY = "deploy"
    ROLLBACK = "rollback"
    CONFIG_CHANGE = "config_change"
    SCALE = "scale"
    RESTART = "restart"
    FEATURE_FLAG = "feature_flag"
    DATABASE_MIGRATION = "database_migration"
    INFRASTRUCTURE = "infrastructure"
    SECRET_ROTATION = "secret_rotation"


class CorrelationStrength(Enum):
    """Strength of deployment-incident correlation."""

    STRONG = "strong"  # High probability of causation
    MODERATE = "moderate"  # Possible causation
    WEAK = "weak"  # Unlikely but worth noting
    NONE = "none"  # No correlation


class DynamoDBClient(Protocol):
    """Protocol for DynamoDB client."""

    async def put_item(self, table_name: str, item: dict) -> None:
        """Put item."""
        ...

    async def query(
        self, table_name: str, key_condition: str, values: dict, **kwargs
    ) -> list[dict]:
        """Query items."""
        ...


class GitClient(Protocol):
    """Protocol for Git client."""

    async def get_commit_info(self, commit_sha: str) -> dict:
        """Get commit information."""
        ...

    async def get_commits_between(self, from_sha: str, to_sha: str) -> list[dict]:
        """Get commits between two SHAs."""
        ...


@dataclass
class DeploymentEvent:
    """A deployment or configuration change event."""

    event_id: str
    event_type: DeploymentEventType
    service: str
    environment: str
    timestamp: datetime
    git_commit: Optional[str] = None
    previous_commit: Optional[str] = None
    changed_files: list[str] = field(default_factory=list)
    deployer: str = "unknown"
    ci_pipeline_id: Optional[str] = None
    deployment_duration_seconds: Optional[int] = None
    rollback_of: Optional[str] = None  # ID of deployment being rolled back
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def affects_service(self, service: str) -> bool:
        """Check if deployment affects a service."""
        return self.service == service or service in self.metadata.get(
            "affected_services", []
        )


@dataclass
class CorrelatedDeployment:
    """A deployment correlated with an incident."""

    deployment: DeploymentEvent
    correlation_strength: CorrelationStrength
    time_delta_seconds: int
    correlation_score: float
    reasons: list[str] = field(default_factory=list)
    changed_components: list[str] = field(default_factory=list)
    risk_factors: list[str] = field(default_factory=list)


@dataclass
class BlastRadiusAnalysis:
    """Analysis of deployment blast radius."""

    deployment_id: str
    affected_services: list[str]
    affected_endpoints: list[str]
    affected_users_estimate: int
    affected_regions: list[str]
    dependency_depth: int
    risk_score: float  # 0-1
    mitigation_suggestions: list[str] = field(default_factory=list)


@dataclass
class DeploymentTimeline:
    """Timeline of deployments for visualization."""

    start_time: datetime
    end_time: datetime
    events: list[DeploymentEvent]
    incidents: list[dict[str, Any]]
    correlations: list[tuple[str, str, float]]  # (deploy_id, incident_id, score)


@dataclass
class CorrelatorConfig:
    """Configuration for deployment correlator."""

    events_table: str = "aura-deployment-events"
    lookback_hours_default: float = 24.0
    lookback_hours_max: float = 168.0  # 1 week
    correlation_window_minutes: int = 60
    min_correlation_score: float = 0.3


class DeploymentHistoryCorrelator:
    """Correlate incidents with deployment history.

    Features:
    - Git commit correlation
    - CI/CD pipeline integration
    - Configuration change tracking
    - Blast radius analysis

    Usage:
        correlator = DeploymentHistoryCorrelator(dynamodb, git_client)

        # Ingest deployment events
        await correlator.ingest_deployment(event)

        # Find correlations
        correlations = await correlator.correlate_incident(
            incident_time=datetime.now(timezone.utc),
            affected_services=["api", "database"],
        )

        # Analyze blast radius
        blast = await correlator.analyze_blast_radius(deployment)
    """

    def __init__(
        self,
        dynamodb_client: DynamoDBClient,
        git_client: Optional[GitClient] = None,
        config: Optional[CorrelatorConfig] = None,
    ):
        """Initialize deployment history correlator.

        Args:
            dynamodb_client: DynamoDB client
            git_client: Git client for commit info
            config: Correlator configuration
        """
        self.dynamodb = dynamodb_client
        self.git = git_client
        self.config = config or CorrelatorConfig()
        self._events_cache: list[DeploymentEvent] = []
        self._service_dependencies: dict[str, list[str]] = {}

    async def ingest_deployment(
        self,
        event: DeploymentEvent,
    ) -> None:
        """Ingest deployment event for correlation.

        Args:
            event: Deployment event
        """
        # Enrich with git info if available
        if event.git_commit and self.git:
            try:
                commit_info = await self.git.get_commit_info(event.git_commit)
                event.metadata["commit_message"] = commit_info.get("message")
                event.metadata["commit_author"] = commit_info.get("author")
                if not event.changed_files:
                    event.changed_files = commit_info.get("files", [])
            except Exception as e:
                logger.warning(f"Failed to get commit info: {e}")

        # Store in DynamoDB
        await self.dynamodb.put_item(
            self.config.events_table,
            {
                "event_id": event.event_id,
                "service": event.service,
                "environment": event.environment,
                "event_type": event.event_type.value,
                "timestamp": event.timestamp.isoformat(),
                "git_commit": event.git_commit,
                "previous_commit": event.previous_commit,
                "changed_files": event.changed_files,
                "deployer": event.deployer,
                "ci_pipeline_id": event.ci_pipeline_id,
                "metadata": event.metadata,
                "tags": event.tags,
            },
        )

        # Update cache
        self._events_cache.append(event)
        self._events_cache = sorted(
            self._events_cache, key=lambda e: e.timestamp, reverse=True
        )[
            :1000
        ]  # Keep recent 1000

        logger.info(f"Ingested deployment event: {event.event_id}")

    async def correlate_incident(
        self,
        incident_time: datetime,
        affected_services: list[str],
        lookback_hours: Optional[float] = None,
        incident_type: Optional[str] = None,
    ) -> list[CorrelatedDeployment]:
        """Find deployments correlated with incident.

        Args:
            incident_time: When incident occurred
            affected_services: Services affected by incident
            lookback_hours: Hours to look back
            incident_type: Type of incident for smarter correlation

        Returns:
            Correlated deployments ranked by strength
        """
        lookback = lookback_hours or self.config.lookback_hours_default
        lookback = min(lookback, self.config.lookback_hours_max)

        start_time = incident_time - timedelta(hours=lookback)

        # Get deployments in window
        deployments = await self._get_deployments_in_range(start_time, incident_time)

        correlations = []

        for deployment in deployments:
            # Calculate time delta
            time_delta = (incident_time - deployment.timestamp).total_seconds()

            # Skip if after incident
            if time_delta < 0:
                continue

            # Check service correlation
            service_match = any(
                deployment.affects_service(s) for s in affected_services
            )

            if not service_match:
                # Check indirect correlation via dependencies
                service_match = self._check_dependency_correlation(
                    deployment.service, affected_services
                )

            if not service_match:
                continue

            # Calculate correlation score
            score, strength, reasons = self._calculate_correlation(
                deployment, incident_time, affected_services, incident_type
            )

            if score >= self.config.min_correlation_score:
                correlations.append(
                    CorrelatedDeployment(
                        deployment=deployment,
                        correlation_strength=strength,
                        time_delta_seconds=int(time_delta),
                        correlation_score=score,
                        reasons=reasons,
                        changed_components=self._extract_components(deployment),
                        risk_factors=self._identify_risk_factors(deployment),
                    )
                )

        # Sort by score
        correlations.sort(key=lambda c: c.correlation_score, reverse=True)

        logger.info(
            f"Found {len(correlations)} correlated deployments for incident at {incident_time}"
        )

        return correlations

    async def analyze_blast_radius(
        self,
        deployment: DeploymentEvent,
    ) -> BlastRadiusAnalysis:
        """Analyze potential blast radius of deployment.

        Args:
            deployment: Deployment to analyze

        Returns:
            Blast radius analysis
        """
        # Get affected services
        affected_services = [deployment.service]
        affected_services.extend(deployment.metadata.get("affected_services", []))

        # Add downstream dependencies
        for service in list(affected_services):
            deps = self._get_downstream_dependencies(service)
            affected_services.extend(deps)

        affected_services = list(set(affected_services))

        # Estimate affected endpoints
        affected_endpoints = []
        for service in affected_services:
            endpoints = self._get_service_endpoints(service)
            affected_endpoints.extend(endpoints)

        # Calculate risk score
        risk_score = self._calculate_risk_score(
            deployment, affected_services, affected_endpoints
        )

        # Generate mitigation suggestions
        suggestions = self._generate_mitigation_suggestions(
            deployment, risk_score, affected_services
        )

        return BlastRadiusAnalysis(
            deployment_id=deployment.event_id,
            affected_services=affected_services,
            affected_endpoints=affected_endpoints,
            affected_users_estimate=self._estimate_affected_users(affected_services),
            affected_regions=deployment.metadata.get("regions", ["us-east-1"]),
            dependency_depth=self._calculate_dependency_depth(
                deployment.service, affected_services
            ),
            risk_score=risk_score,
            mitigation_suggestions=suggestions,
        )

    async def get_deployment_timeline(
        self,
        service: str,
        start_time: datetime,
        end_time: datetime,
        include_incidents: bool = True,
    ) -> DeploymentTimeline:
        """Get deployment timeline for visualization.

        Args:
            service: Service to get timeline for
            start_time: Timeline start
            end_time: Timeline end
            include_incidents: Include incidents in timeline

        Returns:
            Deployment timeline
        """
        deployments = await self._get_deployments_in_range(
            start_time, end_time, service=service
        )

        incidents: list[dict[str, Any]] = []
        correlations: list[tuple[str, str, float]] = []

        if include_incidents:
            # Would fetch incidents from monitoring system
            pass

        return DeploymentTimeline(
            start_time=start_time,
            end_time=end_time,
            events=deployments,
            incidents=incidents,
            correlations=correlations,
        )

    async def get_deployment_frequency(
        self,
        service: str,
        days: int = 30,
    ) -> dict[str, Any]:
        """Get deployment frequency metrics.

        Args:
            service: Service to analyze
            days: Days to analyze

        Returns:
            Frequency metrics
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days)

        deployments = await self._get_deployments_in_range(
            start_time, end_time, service=service
        )

        total = len(deployments)
        by_type: dict[str, int] = {}
        by_day: dict[str, int] = {}

        for d in deployments:
            # Count by type
            t = d.event_type.value
            by_type[t] = by_type.get(t, 0) + 1

            # Count by day
            day = d.timestamp.strftime("%Y-%m-%d")
            by_day[day] = by_day.get(day, 0) + 1

        return {
            "service": service,
            "period_days": days,
            "total_deployments": total,
            "daily_average": total / days if days > 0 else 0,
            "by_type": by_type,
            "by_day": by_day,
            "rollback_rate": (
                by_type.get("rollback", 0) / total * 100 if total > 0 else 0
            ),
        }

    def register_service_dependency(
        self,
        service: str,
        depends_on: list[str],
    ) -> None:
        """Register service dependencies.

        Args:
            service: Service name
            depends_on: Services it depends on
        """
        self._service_dependencies[service] = depends_on

    async def _get_deployments_in_range(
        self,
        start_time: datetime,
        end_time: datetime,
        service: Optional[str] = None,
    ) -> list[DeploymentEvent]:
        """Get deployments in time range.

        Args:
            start_time: Range start
            end_time: Range end
            service: Optional service filter

        Returns:
            List of deployments
        """
        # Query from DynamoDB
        items = await self.dynamodb.query(
            self.config.events_table,
            key_condition="environment = :env AND timestamp BETWEEN :start AND :end",
            values={
                ":env": "dev",  # Would be parameterized
                ":start": start_time.isoformat(),
                ":end": end_time.isoformat(),
            },
        )

        deployments = []
        for item in items:
            if service and item.get("service") != service:
                continue

            deployments.append(
                DeploymentEvent(
                    event_id=item["event_id"],
                    event_type=DeploymentEventType(item["event_type"]),
                    service=item["service"],
                    environment=item["environment"],
                    timestamp=datetime.fromisoformat(item["timestamp"]),
                    git_commit=item.get("git_commit"),
                    previous_commit=item.get("previous_commit"),
                    changed_files=item.get("changed_files", []),
                    deployer=item.get("deployer", "unknown"),
                    ci_pipeline_id=item.get("ci_pipeline_id"),
                    metadata=item.get("metadata", {}),
                    tags=item.get("tags", []),
                )
            )

        # Also include cached events
        for event in self._events_cache:
            if start_time <= event.timestamp <= end_time:
                if service and event.service != service:
                    continue
                if event not in deployments:
                    deployments.append(event)

        return sorted(deployments, key=lambda d: d.timestamp, reverse=True)

    def _calculate_correlation(
        self,
        deployment: DeploymentEvent,
        incident_time: datetime,
        affected_services: list[str],
        incident_type: Optional[str],
    ) -> tuple[float, CorrelationStrength, list[str]]:
        """Calculate correlation score and strength.

        Args:
            deployment: Deployment event
            incident_time: Incident time
            affected_services: Affected services
            incident_type: Type of incident

        Returns:
            Tuple of (score, strength, reasons)
        """
        score = 0.0
        reasons = []

        # Time proximity (closer = stronger)
        time_delta = (incident_time - deployment.timestamp).total_seconds()
        time_score = max(
            0, 1 - time_delta / (self.config.correlation_window_minutes * 60)
        )
        score += time_score * 0.4
        if time_score > 0.8:
            reasons.append(f"Deployed {int(time_delta / 60)} minutes before incident")

        # Service match
        direct_match = deployment.service in affected_services
        if direct_match:
            score += 0.3
            reasons.append(f"Direct service match: {deployment.service}")

        # Event type risk
        risky_types = {
            DeploymentEventType.DEPLOY: 0.2,
            DeploymentEventType.DATABASE_MIGRATION: 0.25,
            DeploymentEventType.CONFIG_CHANGE: 0.15,
            DeploymentEventType.INFRASTRUCTURE: 0.2,
            DeploymentEventType.SECRET_ROTATION: 0.1,
        }
        type_risk = risky_types.get(deployment.event_type, 0.05)
        score += type_risk
        if type_risk > 0.15:
            reasons.append(f"High-risk change type: {deployment.event_type.value}")

        # File changes analysis
        if deployment.changed_files:
            critical_patterns = ["config", "database", "security", "auth"]
            critical_changes = [
                f
                for f in deployment.changed_files
                if any(p in f.lower() for p in critical_patterns)
            ]
            if critical_changes:
                score += 0.1
                reasons.append(f"Critical file changes: {len(critical_changes)} files")

        # Determine strength
        if score >= 0.7:
            strength = CorrelationStrength.STRONG
        elif score >= 0.5:
            strength = CorrelationStrength.MODERATE
        elif score >= 0.3:
            strength = CorrelationStrength.WEAK
        else:
            strength = CorrelationStrength.NONE

        return score, strength, reasons

    def _check_dependency_correlation(
        self,
        deployed_service: str,
        affected_services: list[str],
    ) -> bool:
        """Check if deployment affects services via dependencies."""
        for affected in affected_services:
            deps = self._service_dependencies.get(affected, [])
            if deployed_service in deps:
                return True
        return False

    def _get_downstream_dependencies(self, service: str) -> list[str]:
        """Get services that depend on given service."""
        downstream = []
        for svc, deps in self._service_dependencies.items():
            if service in deps:
                downstream.append(svc)
        return downstream

    def _get_service_endpoints(self, service: str) -> list[str]:
        """Get endpoints for service (mock)."""
        return [f"/{service}/api/v1"]

    def _extract_components(self, deployment: DeploymentEvent) -> list[str]:
        """Extract changed components from deployment."""
        components = set()
        for f in deployment.changed_files:
            parts = f.split("/")
            if len(parts) > 1:
                components.add(parts[0])
        return list(components)

    def _identify_risk_factors(self, deployment: DeploymentEvent) -> list[str]:
        """Identify risk factors in deployment."""
        factors = []

        if deployment.event_type == DeploymentEventType.DATABASE_MIGRATION:
            factors.append("Database schema change")

        if len(deployment.changed_files) > 50:
            factors.append(f"Large change: {len(deployment.changed_files)} files")

        if "production" in deployment.environment.lower():
            factors.append("Production deployment")

        return factors

    def _calculate_risk_score(
        self,
        deployment: DeploymentEvent,
        affected_services: list[str],
        affected_endpoints: list[str],
    ) -> float:
        """Calculate overall risk score."""
        score = 0.0

        # Number of affected services
        score += min(0.3, len(affected_services) * 0.1)

        # Number of affected endpoints
        score += min(0.2, len(affected_endpoints) * 0.02)

        # Change size
        score += min(0.2, len(deployment.changed_files) * 0.004)

        # Event type risk
        type_risks = {
            DeploymentEventType.DATABASE_MIGRATION: 0.3,
            DeploymentEventType.INFRASTRUCTURE: 0.25,
            DeploymentEventType.CONFIG_CHANGE: 0.15,
            DeploymentEventType.DEPLOY: 0.1,
        }
        score += type_risks.get(deployment.event_type, 0.05)

        return min(1.0, score)

    def _calculate_dependency_depth(self, source: str, affected: list[str]) -> int:
        """Calculate maximum dependency depth."""
        # Simple implementation - would be more sophisticated
        return len(affected) - 1 if len(affected) > 1 else 0

    def _estimate_affected_users(self, services: list[str]) -> int:
        """Estimate affected users (mock)."""
        return len(services) * 1000

    def _generate_mitigation_suggestions(
        self,
        deployment: DeploymentEvent,
        risk_score: float,
        affected_services: list[str],
    ) -> list[str]:
        """Generate mitigation suggestions."""
        suggestions = []

        if risk_score > 0.7:
            suggestions.append("Consider phased rollout")
            suggestions.append("Enable feature flags for quick rollback")

        if len(affected_services) > 3:
            suggestions.append("Monitor all affected services during deployment")

        if deployment.event_type == DeploymentEventType.DATABASE_MIGRATION:
            suggestions.append("Ensure database backups are current")
            suggestions.append("Test migration on staging first")

        return suggestions

    def get_service_stats(self) -> dict:
        """Get service statistics."""
        return {
            "cached_events": len(self._events_cache),
            "registered_dependencies": len(self._service_dependencies),
            "config": {
                "lookback_hours_default": self.config.lookback_hours_default,
                "correlation_window_minutes": self.config.correlation_window_minutes,
            },
        }
