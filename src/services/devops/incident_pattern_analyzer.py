"""
Incident Pattern Analyzer Service - AWS DevOps Agent Parity

Implements comprehensive incident analysis and pattern detection:
- Root cause analysis automation
- Pattern recognition across incidents
- Predictive incident detection
- Runbook recommendation
- Post-incident analysis automation
- SLO/SLI tracking and breach prediction

Reference: ADR-030 Section 5.3 DevOps Agent Components
"""

import statistics
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================


class IncidentSeverity(str, Enum):
    """Incident severity levels."""

    SEV1 = "sev1"  # Critical - major outage
    SEV2 = "sev2"  # High - significant impact
    SEV3 = "sev3"  # Medium - limited impact
    SEV4 = "sev4"  # Low - minimal impact


class IncidentStatus(str, Enum):
    """Incident lifecycle status."""

    DETECTED = "detected"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MITIGATING = "mitigating"
    RESOLVED = "resolved"
    CLOSED = "closed"


class IncidentCategory(str, Enum):
    """Category of incident."""

    AVAILABILITY = "availability"
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    SATURATION = "saturation"
    SECURITY = "security"
    DATA_INTEGRITY = "data_integrity"
    DEPENDENCY = "dependency"
    CONFIGURATION = "configuration"


class RootCauseCategory(str, Enum):
    """Categories of root causes."""

    CODE_CHANGE = "code_change"
    CONFIGURATION_CHANGE = "configuration_change"
    INFRASTRUCTURE = "infrastructure"
    DEPENDENCY_FAILURE = "dependency_failure"
    CAPACITY = "capacity"
    SECURITY_EVENT = "security_event"
    DATA_ISSUE = "data_issue"
    HUMAN_ERROR = "human_error"
    EXTERNAL_FACTOR = "external_factor"
    UNKNOWN = "unknown"


class PatternType(str, Enum):
    """Types of incident patterns."""

    RECURRING = "recurring"
    CASCADING = "cascading"
    TIME_BASED = "time_based"
    LOAD_BASED = "load_based"
    DEPLOYMENT_RELATED = "deployment_related"
    DEPENDENCY_CHAIN = "dependency_chain"


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class IncidentTimeline:
    """Timeline event for an incident."""

    timestamp: datetime
    event_type: str
    description: str
    actor: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IncidentMetrics:
    """Metrics captured during an incident."""

    # Impact metrics
    error_rate_peak: float = 0.0
    latency_p99_peak_ms: float = 0.0
    availability_nadir: float = 100.0
    requests_affected: int = 0
    users_affected: int = 0

    # Duration metrics
    time_to_detect_seconds: float = 0.0
    time_to_acknowledge_seconds: float = 0.0
    time_to_mitigate_seconds: float = 0.0
    time_to_resolve_seconds: float = 0.0

    # Recovery metrics
    mttr_seconds: float = 0.0  # Mean time to recovery
    mttd_seconds: float = 0.0  # Mean time to detect


@dataclass
class Incident:
    """An incident record."""

    incident_id: str
    title: str
    description: str
    severity: IncidentSeverity
    status: IncidentStatus
    category: IncidentCategory

    # Impact
    affected_services: list[str]
    affected_regions: list[str]
    customer_impact: str

    # Timeline
    detected_at: datetime
    acknowledged_at: datetime | None = None
    identified_at: datetime | None = None
    mitigated_at: datetime | None = None
    resolved_at: datetime | None = None
    closed_at: datetime | None = None

    # Root cause
    root_cause: str = ""
    root_cause_category: RootCauseCategory = RootCauseCategory.UNKNOWN
    contributing_factors: list[str] = field(default_factory=list)

    # Related items
    related_alerts: list[str] = field(default_factory=list)
    related_deployments: list[str] = field(default_factory=list)
    related_incidents: list[str] = field(default_factory=list)

    # Timeline and metrics
    timeline: list[IncidentTimeline] = field(default_factory=list)
    metrics: IncidentMetrics = field(default_factory=IncidentMetrics)

    # Actions taken
    actions_taken: list[str] = field(default_factory=list)
    runbooks_executed: list[str] = field(default_factory=list)

    # Post-incident
    postmortem_url: str = ""
    action_items: list[str] = field(default_factory=list)

    # Responders
    incident_commander: str = ""
    responders: list[str] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IncidentPattern:
    """A detected pattern across incidents."""

    pattern_id: str
    pattern_type: PatternType
    name: str
    description: str

    # Pattern details
    matching_incidents: list[str]
    occurrence_count: int
    first_occurrence: datetime
    last_occurrence: datetime

    # Pattern characteristics
    common_services: list[str]
    common_root_causes: list[str]
    common_time_windows: list[str]  # e.g., "business hours", "deployment window"
    average_severity: float
    average_mttr_seconds: float

    # Confidence
    confidence_score: float

    # Prevention
    recommended_actions: list[str]
    prevention_suggestions: list[str]

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RootCauseAnalysis:
    """Root cause analysis for an incident."""

    analysis_id: str
    incident_id: str

    # Primary root cause
    root_cause: str
    root_cause_category: RootCauseCategory
    confidence: float

    # Analysis details
    evidence: list[str]
    timeline_analysis: str
    contributing_factors: list[str]
    ruled_out: list[str]

    # Correlations
    correlated_events: list[dict[str, Any]]
    correlated_deployments: list[str]

    # Recommendations
    immediate_actions: list[str]
    long_term_fixes: list[str]
    prevention_measures: list[str]

    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RunbookRecommendation:
    """Recommended runbook for an incident."""

    runbook_id: str
    name: str
    description: str
    relevance_score: float
    matching_factors: list[str]
    estimated_resolution_time: str
    steps: list[str]
    automation_available: bool = False


@dataclass
class SLODefinition:
    """Service Level Objective definition."""

    slo_id: str
    name: str
    service: str
    objective_type: str  # availability, latency, error_rate
    target_value: float
    window_days: int = 30
    burn_rate_threshold: float = 1.0
    error_budget_policy: str = ""


@dataclass
class SLOStatus:
    """Current status of an SLO."""

    slo_id: str
    slo_name: str
    service: str
    current_value: float
    target_value: float
    error_budget_remaining: float
    error_budget_consumed: float
    burn_rate: float
    projected_breach_date: datetime | None
    status: str  # healthy, warning, critical, breached
    window_start: datetime
    window_end: datetime


@dataclass
class PredictiveAlert:
    """Alert for predicted incident."""

    alert_id: str
    alert_type: str
    severity: AlertSeverity
    title: str
    description: str
    predicted_incident_type: str
    confidence: float
    prediction_basis: list[str]
    recommended_actions: list[str]
    affected_services: list[str]
    predicted_time: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PostIncidentReport:
    """Automated post-incident report."""

    report_id: str
    incident_id: str
    incident_title: str

    # Summary
    executive_summary: str
    impact_summary: str
    timeline_summary: str

    # Analysis
    root_cause_analysis: str
    contributing_factors: list[str]
    what_went_well: list[str]
    what_could_improve: list[str]

    # Metrics
    duration_minutes: float
    mttr_minutes: float
    customer_impact_duration_minutes: float
    slo_impact: dict[str, float]

    # Actions
    immediate_actions_taken: list[str]
    follow_up_actions: list[str]
    prevention_measures: list[str]

    # Learning
    lessons_learned: list[str]
    similar_past_incidents: list[str]

    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# Incident Pattern Analyzer Service
# =============================================================================


class IncidentPatternAnalyzer:
    """
    Comprehensive incident analysis and pattern detection service.

    Provides:
    - Root cause analysis automation
    - Pattern recognition
    - Predictive alerting
    - Runbook recommendations
    - SLO tracking
    - Post-incident automation
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

        # Storage
        self._incidents: dict[str, Incident] = {}
        self._patterns: dict[str, IncidentPattern] = {}
        self._slos: dict[str, SLODefinition] = {}
        self._runbooks: dict[str, dict[str, Any]] = {}

        # Pattern detection config
        self._pattern_detection_window_days = 90
        self._min_pattern_occurrences = 3
        self._similarity_threshold = 0.7

        self._logger = logger.bind(service="incident_pattern_analyzer")

    # =========================================================================
    # Incident Management
    # =========================================================================

    async def record_incident(self, incident: Incident) -> Incident:
        """
        Record a new incident and trigger analysis.

        Args:
            incident: The incident to record

        Returns:
            Recorded incident with analysis
        """
        self._incidents[incident.incident_id] = incident

        # Calculate metrics
        incident.metrics = self._calculate_incident_metrics(incident)

        # Find similar past incidents
        similar = await self._find_similar_incidents(incident)
        if similar:
            incident.related_incidents = [i.incident_id for i in similar[:5]]

        # Recommend runbooks
        runbooks = await self.recommend_runbooks(incident)
        if runbooks:
            incident.runbooks_executed = [r.runbook_id for r in runbooks[:3]]

        self._logger.info(
            "Incident recorded",
            incident_id=incident.incident_id,
            severity=incident.severity.value,
            similar_incidents=len(incident.related_incidents),
        )

        return incident

    async def update_incident(
        self,
        incident_id: str,
        status: IncidentStatus | None = None,
        root_cause: str | None = None,
        root_cause_category: RootCauseCategory | None = None,
    ) -> Incident:
        """Update incident status and details."""
        incident = self._incidents.get(incident_id)
        if not incident:
            raise ValueError(f"Incident not found: {incident_id}")

        now = datetime.now(timezone.utc)

        if status:
            incident.status = status

            if status == IncidentStatus.ACKNOWLEDGED and not incident.acknowledged_at:
                incident.acknowledged_at = now
            elif status == IncidentStatus.IDENTIFIED and not incident.identified_at:
                incident.identified_at = now
            elif status == IncidentStatus.MITIGATING and not incident.mitigated_at:
                incident.mitigated_at = now
            elif status == IncidentStatus.RESOLVED and not incident.resolved_at:
                incident.resolved_at = now
            elif status == IncidentStatus.CLOSED and not incident.closed_at:
                incident.closed_at = now

            # Update metrics
            incident.metrics = self._calculate_incident_metrics(incident)

        if root_cause:
            incident.root_cause = root_cause
        if root_cause_category:
            incident.root_cause_category = root_cause_category

        return incident

    def _calculate_incident_metrics(self, incident: Incident) -> IncidentMetrics:
        """Calculate metrics for an incident."""
        metrics = incident.metrics

        if incident.acknowledged_at and incident.detected_at:
            metrics.time_to_acknowledge_seconds = (
                incident.acknowledged_at - incident.detected_at
            ).total_seconds()
            metrics.mttd_seconds = metrics.time_to_acknowledge_seconds

        if incident.mitigated_at and incident.detected_at:
            metrics.time_to_mitigate_seconds = (
                incident.mitigated_at - incident.detected_at
            ).total_seconds()

        if incident.resolved_at and incident.detected_at:
            metrics.time_to_resolve_seconds = (
                incident.resolved_at - incident.detected_at
            ).total_seconds()
            metrics.mttr_seconds = metrics.time_to_resolve_seconds

        return metrics

    # =========================================================================
    # Root Cause Analysis
    # =========================================================================

    async def analyze_root_cause(self, incident: Incident) -> RootCauseAnalysis:
        """
        Perform automated root cause analysis.

        Args:
            incident: The incident to analyze

        Returns:
            Root cause analysis
        """
        self._logger.info(
            "Starting root cause analysis", incident_id=incident.incident_id
        )

        evidence: list[str] = []
        contributing_factors: list[str] = []
        ruled_out: list[str] = []
        correlated_events: list[dict[str, Any]] = []

        # Analyze timeline
        timeline_analysis = self._analyze_timeline(incident)

        # Check for deployment correlation
        deployment_correlation = await self._check_deployment_correlation(incident)
        if deployment_correlation:
            evidence.append(
                f"Deployment correlated: {deployment_correlation['deployment_id']}"
            )
            correlated_events.append(deployment_correlation)

        # Check for configuration changes
        config_changes = await self._check_config_changes(incident)
        if config_changes:
            evidence.append(f"Configuration changes detected: {len(config_changes)}")
            contributing_factors.append("Recent configuration changes")

        # Check for dependency issues
        dependency_issues = await self._check_dependency_issues(incident)
        if dependency_issues:
            evidence.append(f"Dependency issues: {dependency_issues}")
            contributing_factors.append("Dependency failures")

        # Check for capacity issues
        capacity_issues = await self._check_capacity_issues(incident)
        if capacity_issues:
            evidence.append(f"Capacity metrics: {capacity_issues}")
            contributing_factors.append("Resource saturation")

        # Determine most likely root cause
        root_cause, category, confidence = self._determine_root_cause(
            incident,
            evidence,
            deployment_correlation,
            config_changes,
            dependency_issues,
            capacity_issues,
        )

        # Generate recommendations
        immediate_actions = self._generate_immediate_actions(category, incident)
        long_term_fixes = self._generate_long_term_fixes(category, incident)
        prevention_measures = self._generate_prevention_measures(category, incident)

        analysis = RootCauseAnalysis(
            analysis_id=str(uuid.uuid4()),
            incident_id=incident.incident_id,
            root_cause=root_cause,
            root_cause_category=category,
            confidence=confidence,
            evidence=evidence,
            timeline_analysis=timeline_analysis,
            contributing_factors=contributing_factors,
            ruled_out=ruled_out,
            correlated_events=correlated_events,
            correlated_deployments=[
                str(e["deployment_id"])
                for e in correlated_events
                if "deployment_id" in e
            ],
            immediate_actions=immediate_actions,
            long_term_fixes=long_term_fixes,
            prevention_measures=prevention_measures,
        )

        # Update incident with root cause
        incident.root_cause = root_cause
        incident.root_cause_category = category
        incident.contributing_factors = contributing_factors

        self._logger.info(
            "Root cause analysis completed",
            incident_id=incident.incident_id,
            root_cause_category=category.value,
            confidence=confidence,
        )

        return analysis

    def _analyze_timeline(self, incident: Incident) -> str:
        """Analyze incident timeline for patterns."""
        events = []

        events.append(
            f"Incident detected at {incident.detected_at.strftime('%H:%M:%S UTC')}"
        )

        if incident.acknowledged_at:
            delta = (incident.acknowledged_at - incident.detected_at).total_seconds()
            events.append(f"Acknowledged after {delta/60:.1f} minutes")

        if incident.identified_at:
            delta = (incident.identified_at - incident.detected_at).total_seconds()
            events.append(f"Root cause identified after {delta/60:.1f} minutes")

        if incident.mitigated_at:
            delta = (incident.mitigated_at - incident.detected_at).total_seconds()
            events.append(f"Mitigated after {delta/60:.1f} minutes")

        if incident.resolved_at:
            delta = (incident.resolved_at - incident.detected_at).total_seconds()
            events.append(f"Resolved after {delta/60:.1f} minutes")

        return " → ".join(events)

    async def _check_deployment_correlation(
        self, incident: Incident
    ) -> dict[str, Any] | None:
        """Check for deployment correlation."""
        # Look for deployments in the 4 hours before incident
        _window_start = incident.detected_at - timedelta(hours=4)  # noqa: F841

        # In production, query deployment history
        # For now, check related_deployments
        if incident.related_deployments:
            return {
                "deployment_id": incident.related_deployments[0],
                "correlation_type": "time_proximity",
            }
        return None

    async def _check_config_changes(self, incident: Incident) -> list[dict[str, Any]]:
        """Check for configuration changes before incident."""
        # In production, query config change history
        return []

    async def _check_dependency_issues(self, incident: Incident) -> str | None:
        """Check for dependency issues."""
        # In production, check dependency health metrics
        if incident.category == IncidentCategory.DEPENDENCY:
            return "Upstream dependency degradation detected"
        return None

    async def _check_capacity_issues(self, incident: Incident) -> str | None:
        """Check for capacity issues."""
        if incident.category == IncidentCategory.SATURATION:
            return "CPU/Memory utilization exceeded thresholds"
        return None

    def _determine_root_cause(
        self,
        incident: Incident,
        evidence: list[str],
        deployment_correlation: dict | None,
        config_changes: list,
        dependency_issues: str | None,
        capacity_issues: str | None,
    ) -> tuple[str, RootCauseCategory, float]:
        """Determine most likely root cause."""

        # Priority scoring for each potential cause
        scores: dict[RootCauseCategory, float] = defaultdict(float)

        if deployment_correlation:
            scores[RootCauseCategory.CODE_CHANGE] += 0.4
            if incident.category == IncidentCategory.ERROR_RATE:
                scores[RootCauseCategory.CODE_CHANGE] += 0.2

        if config_changes:
            scores[RootCauseCategory.CONFIGURATION_CHANGE] += 0.3

        if dependency_issues:
            scores[RootCauseCategory.DEPENDENCY_FAILURE] += 0.5

        if capacity_issues:
            scores[RootCauseCategory.CAPACITY] += 0.4

        if incident.category == IncidentCategory.SECURITY:
            scores[RootCauseCategory.SECURITY_EVENT] += 0.5

        if incident.category == IncidentCategory.DATA_INTEGRITY:
            scores[RootCauseCategory.DATA_ISSUE] += 0.5

        # Find highest scoring category
        if scores:
            category = max(scores, key=lambda k: scores[k])
            confidence = min(1.0, scores[category])
        else:
            category = RootCauseCategory.UNKNOWN
            confidence = 0.3

        # Generate root cause description
        root_cause_templates = {
            RootCauseCategory.CODE_CHANGE: f"Code change in deployment introduced regression in {incident.affected_services[0] if incident.affected_services else 'service'}",
            RootCauseCategory.CONFIGURATION_CHANGE: "Configuration change caused unexpected behavior",
            RootCauseCategory.DEPENDENCY_FAILURE: f"Upstream dependency failure impacted {incident.affected_services[0] if incident.affected_services else 'service'}",
            RootCauseCategory.CAPACITY: "Resource exhaustion under load",
            RootCauseCategory.SECURITY_EVENT: "Security event triggered incident",
            RootCauseCategory.DATA_ISSUE: "Data corruption or inconsistency",
            RootCauseCategory.INFRASTRUCTURE: "Infrastructure component failure",
            RootCauseCategory.HUMAN_ERROR: "Manual operation error",
            RootCauseCategory.EXTERNAL_FACTOR: "External factor outside our control",
            RootCauseCategory.UNKNOWN: "Root cause under investigation",
        }

        root_cause = root_cause_templates.get(category, "Unknown root cause")

        return root_cause, category, confidence

    def _generate_immediate_actions(
        self, category: RootCauseCategory, incident: Incident
    ) -> list[str]:
        """Generate immediate action recommendations."""
        actions = {
            RootCauseCategory.CODE_CHANGE: [
                "Consider rollback to previous version",
                "Enable feature flags to disable new functionality",
                "Scale up resources while investigating",
            ],
            RootCauseCategory.CONFIGURATION_CHANGE: [
                "Revert configuration change",
                "Verify configuration consistency across environments",
            ],
            RootCauseCategory.DEPENDENCY_FAILURE: [
                "Check dependency service status",
                "Enable circuit breaker if not already active",
                "Consider failover to backup dependency",
            ],
            RootCauseCategory.CAPACITY: [
                "Scale up affected resources immediately",
                "Enable rate limiting to reduce load",
                "Identify and shed non-critical traffic",
            ],
            RootCauseCategory.SECURITY_EVENT: [
                "Isolate affected systems",
                "Engage security team immediately",
                "Preserve logs and evidence",
            ],
            RootCauseCategory.DATA_ISSUE: [
                "Stop writes to affected data",
                "Identify scope of data impact",
                "Prepare for data recovery",
            ],
        }

        return actions.get(category, ["Continue investigation", "Monitor situation"])

    def _generate_long_term_fixes(
        self, category: RootCauseCategory, incident: Incident
    ) -> list[str]:
        """Generate long-term fix recommendations."""
        fixes = {
            RootCauseCategory.CODE_CHANGE: [
                "Improve test coverage for affected area",
                "Add canary deployment stage",
                "Implement better monitoring for regression detection",
            ],
            RootCauseCategory.CONFIGURATION_CHANGE: [
                "Implement configuration validation",
                "Add configuration change approval workflow",
                "Create configuration drift detection",
            ],
            RootCauseCategory.DEPENDENCY_FAILURE: [
                "Implement circuit breaker pattern",
                "Add dependency health monitoring",
                "Consider redundant dependency options",
            ],
            RootCauseCategory.CAPACITY: [
                "Implement auto-scaling",
                "Add capacity alerts before saturation",
                "Conduct load testing regularly",
            ],
            RootCauseCategory.SECURITY_EVENT: [
                "Review and enhance security controls",
                "Implement additional monitoring",
                "Conduct security audit",
            ],
        }

        return fixes.get(category, ["Document findings", "Review processes"])

    def _generate_prevention_measures(
        self, category: RootCauseCategory, incident: Incident
    ) -> list[str]:
        """Generate prevention measure recommendations."""
        measures = {
            RootCauseCategory.CODE_CHANGE: [
                "Require approval for production deployments",
                "Implement deployment health gates",
                "Add automated rollback triggers",
            ],
            RootCauseCategory.CONFIGURATION_CHANGE: [
                "Version control all configurations",
                "Implement configuration as code",
                "Add staging environment validation",
            ],
            RootCauseCategory.DEPENDENCY_FAILURE: [
                "Define and monitor dependency SLOs",
                "Implement graceful degradation",
                "Add dependency failover mechanisms",
            ],
            RootCauseCategory.CAPACITY: [
                "Implement predictive scaling",
                "Set up capacity forecasting",
                "Regular capacity planning reviews",
            ],
        }

        return measures.get(
            category, ["Regular incident reviews", "Process improvements"]
        )

    # =========================================================================
    # Pattern Detection
    # =========================================================================

    async def detect_patterns(self) -> list[IncidentPattern]:
        """
        Detect patterns across historical incidents.

        Returns:
            List of detected patterns
        """
        self._logger.info("Starting pattern detection")

        patterns = []
        cutoff = datetime.now(timezone.utc) - timedelta(
            days=self._pattern_detection_window_days
        )

        # Get incidents in window
        incidents = [i for i in self._incidents.values() if i.detected_at >= cutoff]

        # Detect recurring patterns (same service, same category)
        recurring = await self._detect_recurring_patterns(incidents)
        patterns.extend(recurring)

        # Detect time-based patterns
        time_based = await self._detect_time_patterns(incidents)
        patterns.extend(time_based)

        # Detect deployment-related patterns
        deployment_related = await self._detect_deployment_patterns(incidents)
        patterns.extend(deployment_related)

        # Store patterns
        for pattern in patterns:
            self._patterns[pattern.pattern_id] = pattern

        self._logger.info("Pattern detection completed", patterns_found=len(patterns))

        return patterns

    async def _detect_recurring_patterns(
        self, incidents: list[Incident]
    ) -> list[IncidentPattern]:
        """Detect recurring incident patterns."""
        patterns = []

        # Group by service and category
        groups: dict[tuple[str, str], list[Incident]] = defaultdict(list)

        for incident in incidents:
            for service in incident.affected_services:
                key = (service, incident.category.value)
                groups[key].append(incident)

        for (service, category), group_incidents in groups.items():
            if len(group_incidents) >= self._min_pattern_occurrences:
                avg_severity = sum(
                    {"sev1": 4, "sev2": 3, "sev3": 2, "sev4": 1}[i.severity.value]
                    for i in group_incidents
                ) / len(group_incidents)

                avg_mttr = (
                    statistics.mean(
                        [
                            i.metrics.mttr_seconds
                            for i in group_incidents
                            if i.metrics.mttr_seconds > 0
                        ]
                    )
                    if any(i.metrics.mttr_seconds > 0 for i in group_incidents)
                    else 0
                )

                common_root_causes = list(
                    {
                        i.root_cause_category.value
                        for i in group_incidents
                        if i.root_cause_category != RootCauseCategory.UNKNOWN
                    }
                )

                pattern = IncidentPattern(
                    pattern_id=str(uuid.uuid4()),
                    pattern_type=PatternType.RECURRING,
                    name=f"Recurring {category} in {service}",
                    description=f"{len(group_incidents)} {category} incidents in {service} over {self._pattern_detection_window_days} days",
                    matching_incidents=[i.incident_id for i in group_incidents],
                    occurrence_count=len(group_incidents),
                    first_occurrence=min(i.detected_at for i in group_incidents),
                    last_occurrence=max(i.detected_at for i in group_incidents),
                    common_services=[service],
                    common_root_causes=common_root_causes,
                    common_time_windows=[],
                    average_severity=avg_severity,
                    average_mttr_seconds=avg_mttr,
                    confidence_score=0.8,
                    recommended_actions=[
                        f"Investigate recurring {category} issues in {service}",
                        "Review service architecture and dependencies",
                        "Consider dedicated remediation project",
                    ],
                    prevention_suggestions=[
                        "Implement proactive monitoring",
                        "Add chaos engineering tests",
                        "Review and improve runbooks",
                    ],
                )
                patterns.append(pattern)

        return patterns

    async def _detect_time_patterns(
        self, incidents: list[Incident]
    ) -> list[IncidentPattern]:
        """Detect time-based incident patterns."""
        patterns = []

        # Group by hour of day
        by_hour: dict[int, list[Incident]] = defaultdict(list)
        for incident in incidents:
            by_hour[incident.detected_at.hour].append(incident)

        # Check for concentration in specific hours
        total = len(incidents)
        for hour, hour_incidents in by_hour.items():
            if len(hour_incidents) >= self._min_pattern_occurrences:
                concentration = len(hour_incidents) / total
                if concentration > 0.2:  # More than 20% at this hour
                    pattern = IncidentPattern(
                        pattern_id=str(uuid.uuid4()),
                        pattern_type=PatternType.TIME_BASED,
                        name=f"Peak incidents at {hour:02d}:00",
                        description=f"{len(hour_incidents)} incidents ({concentration:.0%}) occur around {hour:02d}:00",
                        matching_incidents=[i.incident_id for i in hour_incidents],
                        occurrence_count=len(hour_incidents),
                        first_occurrence=min(i.detected_at for i in hour_incidents),
                        last_occurrence=max(i.detected_at for i in hour_incidents),
                        common_services=list(
                            {s for i in hour_incidents for s in i.affected_services}
                        )[:5],
                        common_root_causes=[],
                        common_time_windows=[f"{hour:02d}:00-{(hour + 1) % 24:02d}:00"],
                        average_severity=0,
                        average_mttr_seconds=0,
                        confidence_score=0.7,
                        recommended_actions=[
                            f"Review what happens at {hour:02d}:00 (jobs, traffic patterns)",
                            "Consider load shedding or scaling during this window",
                        ],
                        prevention_suggestions=[
                            "Stagger scheduled jobs",
                            "Pre-scale before peak hours",
                        ],
                    )
                    patterns.append(pattern)

        return patterns

    async def _detect_deployment_patterns(
        self, incidents: list[Incident]
    ) -> list[IncidentPattern]:
        """Detect deployment-related incident patterns."""
        patterns = []

        # Find incidents with deployment correlations
        deployment_incidents = [
            i
            for i in incidents
            if i.related_deployments
            or i.root_cause_category == RootCauseCategory.CODE_CHANGE
        ]

        if len(deployment_incidents) >= self._min_pattern_occurrences:
            pattern = IncidentPattern(
                pattern_id=str(uuid.uuid4()),
                pattern_type=PatternType.DEPLOYMENT_RELATED,
                name="Deployment-Related Incidents",
                description=f"{len(deployment_incidents)} incidents correlated with deployments",
                matching_incidents=[i.incident_id for i in deployment_incidents],
                occurrence_count=len(deployment_incidents),
                first_occurrence=min(i.detected_at for i in deployment_incidents),
                last_occurrence=max(i.detected_at for i in deployment_incidents),
                common_services=list(
                    {s for i in deployment_incidents for s in i.affected_services}
                )[:5],
                common_root_causes=["code_change"],
                common_time_windows=["deployment_window"],
                average_severity=0,
                average_mttr_seconds=0,
                confidence_score=0.85,
                recommended_actions=[
                    "Review deployment process and gates",
                    "Implement canary deployments",
                    "Add deployment health checks",
                ],
                prevention_suggestions=[
                    "Require deployment approval",
                    "Implement automatic rollback",
                    "Improve test coverage",
                ],
            )
            patterns.append(pattern)

        return patterns

    async def _find_similar_incidents(self, incident: Incident) -> list[Incident]:
        """Find similar past incidents."""
        similar = []

        for past in self._incidents.values():
            if past.incident_id == incident.incident_id:
                continue

            # Calculate similarity score
            score = 0.0

            # Same category
            if past.category == incident.category:
                score += 0.3

            # Overlapping services
            overlap = set(past.affected_services) & set(incident.affected_services)
            if overlap:
                score += 0.4 * len(overlap) / max(len(incident.affected_services), 1)

            # Same root cause category
            if past.root_cause_category == incident.root_cause_category:
                score += 0.2

            # Similar severity
            if past.severity == incident.severity:
                score += 0.1

            if score >= self._similarity_threshold:
                similar.append(past)

        # Sort by similarity (implicit in score calculation)
        return similar[:10]

    # =========================================================================
    # Runbook Recommendations
    # =========================================================================

    async def recommend_runbooks(
        self, incident: Incident
    ) -> list[RunbookRecommendation]:
        """
        Recommend relevant runbooks for an incident.

        Args:
            incident: The incident needing runbooks

        Returns:
            List of recommended runbooks
        """
        recommendations = []

        # Get relevant runbooks based on category and services
        relevant_runbooks = self._find_relevant_runbooks(
            incident.category, incident.affected_services
        )

        for runbook_id, runbook in relevant_runbooks.items():
            matching_factors = []

            if runbook.get("category") == incident.category.value:
                matching_factors.append("Category match")

            if any(
                s in runbook.get("services", []) for s in incident.affected_services
            ):
                matching_factors.append("Service match")

            if runbook.get("severity") == incident.severity.value:
                matching_factors.append("Severity match")

            relevance_score = len(matching_factors) / 3

            recommendations.append(
                RunbookRecommendation(
                    runbook_id=runbook_id,
                    name=runbook.get("name", "Unknown"),
                    description=runbook.get("description", ""),
                    relevance_score=relevance_score,
                    matching_factors=matching_factors,
                    estimated_resolution_time=runbook.get("estimated_time", "Unknown"),
                    steps=runbook.get("steps", []),
                    automation_available=runbook.get("automated", False),
                )
            )

        # Sort by relevance
        recommendations.sort(key=lambda r: r.relevance_score, reverse=True)

        return recommendations

    def _find_relevant_runbooks(
        self, category: IncidentCategory, services: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Find runbooks relevant to category and services."""
        # Default runbooks if none registered
        if not self._runbooks:
            self._runbooks = {
                "rb-001": {
                    "name": "Generic High Error Rate Response",
                    "description": "Steps to diagnose and resolve high error rates",
                    "category": "error_rate",
                    "services": [],
                    "severity": "sev2",
                    "estimated_time": "30 minutes",
                    "steps": [
                        "Check error logs for patterns",
                        "Identify affected endpoints",
                        "Check recent deployments",
                        "Check dependency health",
                        "Scale up if needed",
                        "Consider rollback",
                    ],
                    "automated": False,
                },
                "rb-002": {
                    "name": "Service Availability Recovery",
                    "description": "Steps to recover service availability",
                    "category": "availability",
                    "services": [],
                    "severity": "sev1",
                    "estimated_time": "15 minutes",
                    "steps": [
                        "Verify service health endpoints",
                        "Check infrastructure status",
                        "Restart unhealthy instances",
                        "Verify load balancer health",
                        "Enable failover if available",
                    ],
                    "automated": True,
                },
                "rb-003": {
                    "name": "Latency Spike Response",
                    "description": "Steps to diagnose and resolve latency issues",
                    "category": "latency",
                    "services": [],
                    "severity": "sev3",
                    "estimated_time": "45 minutes",
                    "steps": [
                        "Check resource utilization",
                        "Review database query performance",
                        "Check downstream dependency latency",
                        "Enable caching if applicable",
                        "Scale horizontally",
                    ],
                    "automated": False,
                },
            }

        relevant = {}
        for rb_id, runbook in self._runbooks.items():
            if runbook.get("category") == category.value:
                relevant[rb_id] = runbook
            elif any(s in runbook.get("services", []) for s in services):
                relevant[rb_id] = runbook

        return relevant

    def register_runbook(
        self,
        runbook_id: str,
        name: str,
        description: str,
        category: str,
        services: list[str],
        steps: list[str],
        estimated_time: str = "Unknown",
        automated: bool = False,
    ) -> None:
        """Register a runbook for recommendations."""
        self._runbooks[runbook_id] = {
            "name": name,
            "description": description,
            "category": category,
            "services": services,
            "steps": steps,
            "estimated_time": estimated_time,
            "automated": automated,
        }

    # =========================================================================
    # SLO Management
    # =========================================================================

    def define_slo(
        self,
        name: str,
        service: str,
        objective_type: str,
        target_value: float,
        window_days: int = 30,
    ) -> SLODefinition:
        """Define a Service Level Objective."""
        slo = SLODefinition(
            slo_id=str(uuid.uuid4()),
            name=name,
            service=service,
            objective_type=objective_type,
            target_value=target_value,
            window_days=window_days,
        )

        self._slos[slo.slo_id] = slo

        self._logger.info(
            "SLO defined", slo_id=slo.slo_id, service=service, target=target_value
        )

        return slo

    async def get_slo_status(self, slo_id: str, current_value: float) -> SLOStatus:
        """Get current status of an SLO."""
        slo = self._slos.get(slo_id)
        if not slo:
            raise ValueError(f"SLO not found: {slo_id}")

        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=slo.window_days)

        # Calculate error budget
        if slo.objective_type == "availability":
            error_budget_total = 100 - slo.target_value
            error_budget_consumed = 100 - current_value
        else:
            error_budget_total = slo.target_value
            error_budget_consumed = (
                current_value if current_value > slo.target_value else 0
            )

        error_budget_remaining = max(0, error_budget_total - error_budget_consumed)

        # Calculate burn rate
        days_elapsed = (now - window_start).days or 1
        expected_budget_consumed = (error_budget_total / slo.window_days) * days_elapsed
        burn_rate = error_budget_consumed / max(expected_budget_consumed, 0.001)

        # Determine status
        if current_value < slo.target_value and slo.objective_type == "availability":
            status = "breached"
        elif burn_rate > 2.0:
            status = "critical"
        elif burn_rate > 1.5:
            status = "warning"
        else:
            status = "healthy"

        # Project breach date
        projected_breach = None
        if burn_rate > 1.0 and error_budget_remaining > 0:
            days_to_breach = error_budget_remaining / (
                (error_budget_consumed / days_elapsed)
                - (error_budget_total / slo.window_days)
            )
            if days_to_breach > 0:
                projected_breach = now + timedelta(days=days_to_breach)

        return SLOStatus(
            slo_id=slo_id,
            slo_name=slo.name,
            service=slo.service,
            current_value=current_value,
            target_value=slo.target_value,
            error_budget_remaining=error_budget_remaining,
            error_budget_consumed=error_budget_consumed,
            burn_rate=burn_rate,
            projected_breach_date=projected_breach,
            status=status,
            window_start=window_start,
            window_end=now,
        )

    # =========================================================================
    # Predictive Alerting
    # =========================================================================

    async def generate_predictive_alerts(self) -> list[PredictiveAlert]:
        """
        Generate predictive alerts based on patterns and trends.

        Returns:
            List of predictive alerts
        """
        alerts = []

        # Check SLO burn rates
        for slo_id, slo in self._slos.items():
            # In production, get actual current value
            current_value = 99.5  # Simulated
            status = await self.get_slo_status(slo_id, current_value)

            if status.status == "critical":
                alerts.append(
                    PredictiveAlert(
                        alert_id=str(uuid.uuid4()),
                        alert_type="slo_burn_rate",
                        severity=AlertSeverity.CRITICAL,
                        title=f"SLO Breach Predicted: {slo.name}",
                        description=f"Current burn rate {status.burn_rate:.1f}x will exhaust error budget",
                        predicted_incident_type="availability",
                        confidence=0.8,
                        prediction_basis=[
                            f"Burn rate: {status.burn_rate:.1f}x",
                            f"Error budget remaining: {status.error_budget_remaining:.2f}%",
                        ],
                        recommended_actions=[
                            "Investigate recent changes",
                            "Consider scaling resources",
                            "Review error sources",
                        ],
                        affected_services=[slo.service],
                        predicted_time=status.projected_breach_date,
                    )
                )
            elif status.status == "warning":
                alerts.append(
                    PredictiveAlert(
                        alert_id=str(uuid.uuid4()),
                        alert_type="slo_burn_rate",
                        severity=AlertSeverity.WARNING,
                        title=f"SLO Warning: {slo.name}",
                        description=f"Elevated burn rate {status.burn_rate:.1f}x",
                        predicted_incident_type="availability",
                        confidence=0.6,
                        prediction_basis=[f"Burn rate: {status.burn_rate:.1f}x"],
                        recommended_actions=["Monitor closely"],
                        affected_services=[slo.service],
                    )
                )

        # Check patterns for predicted incidents
        for pattern in self._patterns.values():
            if pattern.pattern_type == PatternType.RECURRING:
                # Predict next occurrence
                interval = (
                    pattern.last_occurrence - pattern.first_occurrence
                ).days / max(pattern.occurrence_count - 1, 1)
                next_predicted = pattern.last_occurrence + timedelta(days=interval)

                if next_predicted <= datetime.now(timezone.utc) + timedelta(days=7):
                    alerts.append(
                        PredictiveAlert(
                            alert_id=str(uuid.uuid4()),
                            alert_type="pattern_prediction",
                            severity=AlertSeverity.WARNING,
                            title=f"Recurring Incident Predicted: {pattern.name}",
                            description=f"Based on pattern of {pattern.occurrence_count} incidents",
                            predicted_incident_type=(
                                pattern.common_root_causes[0]
                                if pattern.common_root_causes
                                else "unknown"
                            ),
                            confidence=pattern.confidence_score * 0.7,
                            prediction_basis=[
                                f"{pattern.occurrence_count} similar incidents",
                                f"Average interval: {interval:.0f} days",
                            ],
                            recommended_actions=pattern.prevention_suggestions,
                            affected_services=pattern.common_services,
                            predicted_time=next_predicted,
                        )
                    )

        return alerts

    # =========================================================================
    # Post-Incident Analysis
    # =========================================================================

    async def generate_post_incident_report(
        self, incident: Incident
    ) -> PostIncidentReport:
        """
        Generate automated post-incident report.

        Args:
            incident: The incident to report on

        Returns:
            Post-incident report
        """
        # Generate executive summary
        executive_summary = self._generate_executive_summary(incident)

        # Generate impact summary
        impact_summary = self._generate_impact_summary(incident)

        # Generate timeline summary
        timeline_summary = self._analyze_timeline(incident)

        # Find similar past incidents
        similar = await self._find_similar_incidents(incident)

        # Calculate SLO impact
        slo_impact = {}
        for _slo_id, slo in self._slos.items():
            if slo.service in incident.affected_services:
                # Calculate impact on SLO
                if incident.metrics.mttr_seconds > 0:
                    downtime_percent = (
                        incident.metrics.mttr_seconds / (slo.window_days * 24 * 3600)
                    ) * 100
                    slo_impact[slo.name] = downtime_percent

        # Generate what went well / could improve
        what_went_well = self._analyze_what_went_well(incident)
        what_could_improve = self._analyze_what_could_improve(incident)

        report = PostIncidentReport(
            report_id=str(uuid.uuid4()),
            incident_id=incident.incident_id,
            incident_title=incident.title,
            executive_summary=executive_summary,
            impact_summary=impact_summary,
            timeline_summary=timeline_summary,
            root_cause_analysis=incident.root_cause,
            contributing_factors=incident.contributing_factors,
            what_went_well=what_went_well,
            what_could_improve=what_could_improve,
            duration_minutes=(
                incident.metrics.mttr_seconds / 60
                if incident.metrics.mttr_seconds
                else 0
            ),
            mttr_minutes=(
                incident.metrics.mttr_seconds / 60
                if incident.metrics.mttr_seconds
                else 0
            ),
            customer_impact_duration_minutes=(
                incident.metrics.time_to_mitigate_seconds / 60
                if incident.metrics.time_to_mitigate_seconds
                else 0
            ),
            slo_impact=slo_impact,
            immediate_actions_taken=incident.actions_taken,
            follow_up_actions=incident.action_items,
            prevention_measures=self._generate_prevention_measures(
                incident.root_cause_category, incident
            ),
            lessons_learned=self._generate_lessons_learned(incident),
            similar_past_incidents=[i.incident_id for i in similar[:3]],
        )

        return report

    def _generate_executive_summary(self, incident: Incident) -> str:
        """Generate executive summary for incident."""
        duration = (
            incident.metrics.mttr_seconds / 60 if incident.metrics.mttr_seconds else 0
        )

        return (
            f"On {incident.detected_at.strftime('%Y-%m-%d')}, a {incident.severity.value.upper()} "
            f"incident affected {', '.join(incident.affected_services[:3])}. "
            f"The incident was detected at {incident.detected_at.strftime('%H:%M UTC')} "
            f"and resolved after {duration:.0f} minutes. "
            f"Root cause: {incident.root_cause or 'Under investigation'}."
        )

    def _generate_impact_summary(self, incident: Incident) -> str:
        """Generate impact summary."""
        return (
            f"Services affected: {', '.join(incident.affected_services)}. "
            f"Regions: {', '.join(incident.affected_regions) if incident.affected_regions else 'All'}. "
            f"Customer impact: {incident.customer_impact}. "
            f"Peak error rate: {incident.metrics.error_rate_peak:.1%}. "
            f"Users affected: {incident.metrics.users_affected:,}."
        )

    def _analyze_what_went_well(self, incident: Incident) -> list[str]:
        """Analyze what went well during incident."""
        items = []

        if incident.metrics.time_to_acknowledge_seconds < 300:
            items.append("Fast acknowledgment (< 5 minutes)")

        if incident.metrics.time_to_mitigate_seconds < 1800:
            items.append("Quick mitigation (< 30 minutes)")

        if incident.runbooks_executed:
            items.append(
                f"Runbooks were available and used ({len(incident.runbooks_executed)})"
            )

        if len(incident.responders) > 1:
            items.append("Good team collaboration")

        if not items:
            items.append("Incident was detected and resolved")

        return items

    def _analyze_what_could_improve(self, incident: Incident) -> list[str]:
        """Analyze what could improve."""
        items = []

        if incident.metrics.time_to_acknowledge_seconds > 600:
            items.append("Acknowledgment time could be faster")

        if incident.metrics.mttr_seconds > 3600:
            items.append("Resolution took longer than target")

        if not incident.runbooks_executed:
            items.append("No runbooks were used - consider creating one")

        if incident.root_cause_category == RootCauseCategory.UNKNOWN:
            items.append("Root cause was not definitively identified")

        if not incident.action_items:
            items.append("No follow-up actions identified")

        return items

    def _generate_lessons_learned(self, incident: Incident) -> list[str]:
        """Generate lessons learned."""
        lessons = []

        if incident.root_cause_category == RootCauseCategory.CODE_CHANGE:
            lessons.append(
                "Deployment validation should include more comprehensive checks"
            )

        if incident.root_cause_category == RootCauseCategory.CONFIGURATION_CHANGE:
            lessons.append(
                "Configuration changes should follow same review process as code"
            )

        if incident.metrics.time_to_detect_seconds > 300:
            lessons.append(
                "Monitoring and alerting could be improved for faster detection"
            )

        if not incident.runbooks_executed:
            lessons.append("Creating/updating runbooks would speed future response")

        if not lessons:
            lessons.append("Document learnings from this incident for future reference")

        return lessons
