"""
DevOps Agent Orchestrator - AWS DevOps Agent Parity

Unified orchestration layer for all DevOps agent capabilities:
- Deployment tracking and correlation
- Infrastructure topology management
- Incident analysis and pattern detection
- 24/7 intelligent triage
- Automated remediation workflows

Reference: ADR-030 Section 5.3 DevOps Agent Components
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

import structlog

from .deployment_history_correlator import (
    Deployment,
    DeploymentHealthReport,
    DeploymentHistoryCorrelator,
    RollbackRecommendation,
)
from .incident_pattern_analyzer import (
    Incident,
    IncidentCategory,
    IncidentPattern,
    IncidentPatternAnalyzer,
    IncidentSeverity,
    IncidentStatus,
    PredictiveAlert,
    RunbookRecommendation,
    SLOStatus,
)
from .resource_topology_mapper import ResourceTopologyMapper

logger = structlog.get_logger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================


class TriageAction(str, Enum):
    """Actions from triage."""

    AUTO_REMEDIATE = "auto_remediate"
    ESCALATE = "escalate"
    PAGE_ONCALL = "page_oncall"
    CREATE_INCIDENT = "create_incident"
    MONITOR = "monitor"
    ROLLBACK = "rollback"
    SCALE = "scale"
    RESTART = "restart"


class RemediationStatus(str, Enum):
    """Status of remediation."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class AlertType(str, Enum):
    """Types of alerts."""

    THRESHOLD = "threshold"
    ANOMALY = "anomaly"
    PREDICTIVE = "predictive"
    PATTERN = "pattern"


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class Alert:
    """An incoming alert."""

    alert_id: str
    alert_type: AlertType
    severity: str
    title: str
    description: str
    source: str  # CloudWatch, Datadog, etc.
    service: str
    metric_name: str
    metric_value: float
    threshold: float | None = None
    fired_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)


@dataclass
class TriageResult:
    """Result of alert triage."""

    triage_id: str
    alert: Alert
    action: TriageAction
    confidence: float
    reasoning: list[str]

    # Context gathered
    recent_deployments: list[Deployment]
    similar_incidents: list[Incident]
    affected_services: list[str]
    blast_radius: list[str]

    # Recommendations
    runbook_recommendations: list[RunbookRecommendation]
    rollback_recommendation: RollbackRecommendation | None

    # Auto-remediation
    auto_remediation_available: bool
    remediation_steps: list[str]

    # Escalation
    escalation_target: str | None
    estimated_severity: IncidentSeverity

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RemediationAction:
    """A remediation action."""

    action_id: str
    action_type: str
    target: str
    parameters: dict[str, Any]
    status: RemediationStatus = RemediationStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: str = ""
    error: str = ""


@dataclass
class RemediationWorkflow:
    """A remediation workflow."""

    workflow_id: str
    trigger_alert: Alert
    incident_id: str | None
    actions: list[RemediationAction]
    status: RemediationStatus
    started_at: datetime
    completed_at: datetime | None = None
    result_summary: str = ""


@dataclass
class DevOpsInsight:
    """An insight from DevOps analysis."""

    insight_id: str
    category: str
    title: str
    description: str
    severity: str
    evidence: list[str]
    recommendations: list[str]
    affected_services: list[str]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class OperationalReport:
    """Operational status report."""

    report_id: str
    period_start: datetime
    period_end: datetime

    # Deployment metrics
    total_deployments: int
    successful_deployments: int
    failed_deployments: int
    deployment_success_rate: float
    mean_time_to_deploy: float

    # Incident metrics
    total_incidents: int
    incidents_by_severity: dict[str, int]
    mttr_seconds: float
    incidents_per_deployment: float

    # SLO status
    slo_statuses: list[SLOStatus]
    slos_at_risk: int

    # Infrastructure
    total_resources: int
    resources_by_status: dict[str, int]
    estimated_monthly_cost: float

    # Patterns and predictions
    active_patterns: list[IncidentPattern]
    predictive_alerts: list[PredictiveAlert]

    # Insights
    insights: list[DevOpsInsight]

    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# DevOps Agent Orchestrator
# =============================================================================


class DevOpsAgentOrchestrator:
    """
    Unified orchestrator for all DevOps agent capabilities.

    Provides:
    - 24/7 intelligent alert triage
    - Automated incident correlation
    - Auto-remediation workflows
    - Operational insights
    - Predictive alerting
    """

    def __init__(
        self,
        neptune_client: Any = None,
        opensearch_client: Any = None,
        cloudwatch_client: Any = None,
        llm_client: Any = None,
        notification_service: Any = None,
    ):
        self._neptune = neptune_client
        self._opensearch = opensearch_client
        self._cloudwatch = cloudwatch_client
        self._llm = llm_client
        self._notifications = notification_service

        # Initialize component services
        self._deployment_correlator = DeploymentHistoryCorrelator(
            neptune_client=neptune_client,
            opensearch_client=opensearch_client,
            cloudwatch_client=cloudwatch_client,
            llm_client=llm_client,
        )

        self._topology_mapper = ResourceTopologyMapper(
            neptune_client=neptune_client,
            opensearch_client=opensearch_client,
            aws_client=None,  # Would inject AWS client
            cost_explorer_client=None,
        )

        self._incident_analyzer = IncidentPatternAnalyzer(
            neptune_client=neptune_client,
            opensearch_client=opensearch_client,
            cloudwatch_client=cloudwatch_client,
            llm_client=llm_client,
        )

        # Workflow storage
        self._remediation_workflows: dict[str, RemediationWorkflow] = {}
        self._triage_results: dict[str, TriageResult] = {}

        # Auto-remediation rules
        self._auto_remediation_rules: list[dict[str, Any]] = []

        self._logger = logger.bind(service="devops_agent_orchestrator")

    # =========================================================================
    # Alert Triage
    # =========================================================================

    async def triage_alert(self, alert: Alert) -> TriageResult:
        """
        Perform intelligent triage on an incoming alert.

        Args:
            alert: The alert to triage

        Returns:
            Triage result with recommended actions
        """
        triage_id = str(uuid.uuid4())

        self._logger.info(
            "Starting alert triage",
            triage_id=triage_id,
            alert_id=alert.alert_id,
            service=alert.service,
            severity=alert.severity,
        )

        reasoning = []

        # Gather context
        recent_deployments = (
            await self._deployment_correlator.get_deployments_for_service(
                alert.service, limit=5
            )
        )

        # Check for deployment correlation
        deployment_correlated = False
        correlated_deployment = None
        if recent_deployments:
            for deployment in recent_deployments:
                time_since = (
                    datetime.now(timezone.utc) - deployment.started_at
                ).total_seconds()
                if time_since < 14400:  # 4 hours
                    deployment_correlated = True
                    correlated_deployment = deployment
                    reasoning.append(
                        f"Recent deployment: {deployment.name} ({time_since/60:.0f} min ago)"
                    )
                    break

        # Get blast radius
        blast_radius = []
        if alert.service:
            service = self._topology_mapper.get_service_by_name(alert.service)
            if service:
                blast_radius = service.downstream_services

        # Find similar past incidents
        similar_incidents = []
        for incident in self._incident_analyzer._incidents.values():
            if alert.service in incident.affected_services:
                similar_incidents.append(incident)

        similar_incidents = similar_incidents[:5]
        if similar_incidents:
            reasoning.append(f"Found {len(similar_incidents)} similar past incidents")

        # Get runbook recommendations
        mock_incident = Incident(
            incident_id="triage",
            title=alert.title,
            description=alert.description,
            severity=self._map_alert_severity(alert.severity),
            status=IncidentStatus.DETECTED,
            category=self._infer_category(alert),
            affected_services=[alert.service],
            affected_regions=[],
            customer_impact="",
            detected_at=alert.fired_at,
        )
        runbook_recommendations = await self._incident_analyzer.recommend_runbooks(
            mock_incident
        )

        # Get rollback recommendation if deployment correlated
        rollback_recommendation = None
        if correlated_deployment:
            rollback_recommendation = (
                await self._deployment_correlator.recommend_rollback(
                    correlated_deployment
                )
            )
            if rollback_recommendation.should_rollback:
                reasoning.append("Rollback recommended based on deployment correlation")

        # Determine action
        action, confidence = self._determine_triage_action(
            alert,
            deployment_correlated,
            similar_incidents,
            rollback_recommendation,
            blast_radius,
        )

        # Check for auto-remediation
        auto_remediation_available, remediation_steps = self._check_auto_remediation(
            alert, action
        )

        # Determine escalation target
        escalation_target = None
        if action in [TriageAction.ESCALATE, TriageAction.PAGE_ONCALL]:
            escalation_target = self._get_escalation_target(alert.service)

        # Estimate severity
        estimated_severity = self._estimate_incident_severity(
            alert, blast_radius, similar_incidents
        )

        result = TriageResult(
            triage_id=triage_id,
            alert=alert,
            action=action,
            confidence=confidence,
            reasoning=reasoning,
            recent_deployments=recent_deployments,
            similar_incidents=similar_incidents,
            affected_services=[alert.service] + blast_radius[:5],
            blast_radius=blast_radius,
            runbook_recommendations=runbook_recommendations[:3],
            rollback_recommendation=rollback_recommendation,
            auto_remediation_available=auto_remediation_available,
            remediation_steps=remediation_steps,
            escalation_target=escalation_target,
            estimated_severity=estimated_severity,
        )

        self._triage_results[triage_id] = result

        self._logger.info(
            "Alert triage completed",
            triage_id=triage_id,
            action=action.value,
            confidence=confidence,
            auto_remediation=auto_remediation_available,
        )

        return result

    def _map_alert_severity(self, severity: str) -> IncidentSeverity:
        """Map alert severity to incident severity."""
        mapping = {
            "critical": IncidentSeverity.SEV1,
            "high": IncidentSeverity.SEV2,
            "warning": IncidentSeverity.SEV3,
            "medium": IncidentSeverity.SEV3,
            "low": IncidentSeverity.SEV4,
            "info": IncidentSeverity.SEV4,
        }
        return mapping.get(severity.lower(), IncidentSeverity.SEV3)

    def _infer_category(self, alert: Alert) -> IncidentCategory:
        """Infer incident category from alert."""
        metric_lower = alert.metric_name.lower()

        if "error" in metric_lower or "5xx" in metric_lower:
            return IncidentCategory.ERROR_RATE
        elif "latency" in metric_lower or "duration" in metric_lower:
            return IncidentCategory.LATENCY
        elif "availability" in metric_lower or "health" in metric_lower:
            return IncidentCategory.AVAILABILITY
        elif (
            "cpu" in metric_lower or "memory" in metric_lower or "disk" in metric_lower
        ):
            return IncidentCategory.SATURATION
        else:
            return IncidentCategory.AVAILABILITY

    def _determine_triage_action(
        self,
        alert: Alert,
        deployment_correlated: bool,
        similar_incidents: list[Incident],
        rollback_recommendation: RollbackRecommendation | None,
        blast_radius: list[str],
    ) -> tuple[TriageAction, float]:
        """Determine the triage action based on context."""
        _confidence = 0.5  # noqa: F841

        # Critical alerts with deployment correlation → rollback
        if (
            alert.severity.lower() == "critical"
            and rollback_recommendation
            and rollback_recommendation.should_rollback
        ):
            return TriageAction.ROLLBACK, 0.85

        # Critical alerts → page oncall
        if alert.severity.lower() == "critical":
            return TriageAction.PAGE_ONCALL, 0.9

        # High severity with large blast radius → escalate
        if alert.severity.lower() == "high" and len(blast_radius) > 3:
            return TriageAction.ESCALATE, 0.8

        # Similar past incidents that were auto-resolved
        auto_resolved = [
            i
            for i in similar_incidents
            if i.status == IncidentStatus.RESOLVED and i.metrics.mttr_seconds < 900
        ]
        if auto_resolved:
            return TriageAction.AUTO_REMEDIATE, 0.7

        # Deployment correlated → consider rollback
        if deployment_correlated:
            if rollback_recommendation and rollback_recommendation.should_rollback:
                return TriageAction.ROLLBACK, 0.75
            else:
                return TriageAction.CREATE_INCIDENT, 0.7

        # Default actions based on severity
        if alert.severity.lower() in ["high", "critical"]:
            return TriageAction.CREATE_INCIDENT, 0.6
        elif alert.severity.lower() == "warning":
            return TriageAction.MONITOR, 0.6
        else:
            return TriageAction.MONITOR, 0.5

    def _check_auto_remediation(
        self, alert: Alert, action: TriageAction
    ) -> tuple[bool, list[str]]:
        """Check if auto-remediation is available."""
        if action not in [
            TriageAction.AUTO_REMEDIATE,
            TriageAction.ROLLBACK,
            TriageAction.SCALE,
            TriageAction.RESTART,
        ]:
            return False, []

        steps = []

        # Check registered rules
        for rule in self._auto_remediation_rules:
            if self._rule_matches_alert(rule, alert):
                steps.extend(rule.get("steps", []))

        # Default remediation steps based on action
        if action == TriageAction.ROLLBACK:
            steps = [
                "Identify deployment to rollback",
                "Execute rollback procedure",
                "Verify service health",
                "Monitor for recovery",
            ]
        elif action == TriageAction.SCALE:
            steps = [
                "Calculate required capacity",
                "Scale service horizontally",
                "Verify new instances healthy",
                "Monitor load distribution",
            ]
        elif action == TriageAction.RESTART:
            steps = [
                "Identify unhealthy instances",
                "Gracefully drain connections",
                "Restart instances",
                "Verify health checks pass",
            ]

        return bool(steps), steps

    def _rule_matches_alert(self, rule: dict, alert: Alert) -> bool:
        """Check if a remediation rule matches an alert."""
        if rule.get("service") and rule["service"] != alert.service:
            return False
        if rule.get("metric") and rule["metric"] != alert.metric_name:
            return False
        if rule.get("severity") and rule["severity"] != alert.severity:
            return False
        return True

    def _get_escalation_target(self, service: str) -> str:
        """Get escalation target for a service."""
        # In production, look up service ownership
        return f"{service}-oncall"

    def _estimate_incident_severity(
        self, alert: Alert, blast_radius: list[str], similar_incidents: list[Incident]
    ) -> IncidentSeverity:
        """Estimate incident severity from alert context."""
        base_severity = self._map_alert_severity(alert.severity)

        # Upgrade if large blast radius
        if len(blast_radius) > 5 and base_severity != IncidentSeverity.SEV1:
            severity_order = [
                IncidentSeverity.SEV4,
                IncidentSeverity.SEV3,
                IncidentSeverity.SEV2,
                IncidentSeverity.SEV1,
            ]
            idx = severity_order.index(base_severity)
            if idx < len(severity_order) - 1:
                return severity_order[idx + 1]

        # Check similar incidents for severity patterns
        if similar_incidents:
            avg_severity = sum(
                {"sev1": 4, "sev2": 3, "sev3": 2, "sev4": 1}[i.severity.value]
                for i in similar_incidents
            ) / len(similar_incidents)

            if avg_severity >= 3:
                return IncidentSeverity.SEV2

        return base_severity

    # =========================================================================
    # Auto-Remediation
    # =========================================================================

    async def execute_remediation(
        self, triage_result: TriageResult
    ) -> RemediationWorkflow:
        """
        Execute auto-remediation based on triage result.

        Args:
            triage_result: The triage result to act on

        Returns:
            Remediation workflow
        """
        workflow_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)

        self._logger.info(
            "Starting remediation workflow",
            workflow_id=workflow_id,
            triage_id=triage_result.triage_id,
            action=triage_result.action.value,
        )

        actions = []

        if triage_result.action == TriageAction.ROLLBACK:
            actions = await self._create_rollback_actions(triage_result)
        elif triage_result.action == TriageAction.SCALE:
            actions = await self._create_scale_actions(triage_result)
        elif triage_result.action == TriageAction.RESTART:
            actions = await self._create_restart_actions(triage_result)
        elif triage_result.action == TriageAction.AUTO_REMEDIATE:
            actions = await self._create_generic_remediation_actions(triage_result)

        # Execute actions
        overall_status = RemediationStatus.SUCCEEDED
        for action in actions:
            action.status = RemediationStatus.IN_PROGRESS
            action.started_at = datetime.now(timezone.utc)

            try:
                result = await self._execute_action(action)
                action.status = RemediationStatus.SUCCEEDED
                action.result = result
            except Exception as e:
                action.status = RemediationStatus.FAILED
                action.error = str(e)
                overall_status = RemediationStatus.FAILED

            action.completed_at = datetime.now(timezone.utc)

        workflow = RemediationWorkflow(
            workflow_id=workflow_id,
            trigger_alert=triage_result.alert,
            incident_id=None,
            actions=actions,
            status=overall_status,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            result_summary=f"Executed {len(actions)} actions, {sum(1 for a in actions if a.status == RemediationStatus.SUCCEEDED)} succeeded",
        )

        self._remediation_workflows[workflow_id] = workflow

        self._logger.info(
            "Remediation workflow completed",
            workflow_id=workflow_id,
            status=overall_status.value,
            actions_executed=len(actions),
        )

        return workflow

    async def _create_rollback_actions(
        self, triage_result: TriageResult
    ) -> list[RemediationAction]:
        """Create rollback actions."""
        actions = []

        if triage_result.recent_deployments:
            deployment = triage_result.recent_deployments[0]

            actions.append(
                RemediationAction(
                    action_id=str(uuid.uuid4()),
                    action_type="rollback",
                    target=deployment.deployment_id,
                    parameters={
                        "deployment_id": deployment.deployment_id,
                        "service": triage_result.alert.service,
                    },
                )
            )

            actions.append(
                RemediationAction(
                    action_id=str(uuid.uuid4()),
                    action_type="verify_health",
                    target=triage_result.alert.service,
                    parameters={"timeout_seconds": 300},
                )
            )

        return actions

    async def _create_scale_actions(
        self, triage_result: TriageResult
    ) -> list[RemediationAction]:
        """Create scale actions."""
        return [
            RemediationAction(
                action_id=str(uuid.uuid4()),
                action_type="scale_out",
                target=triage_result.alert.service,
                parameters={"scale_factor": 1.5, "max_instances": 10},
            ),
            RemediationAction(
                action_id=str(uuid.uuid4()),
                action_type="verify_health",
                target=triage_result.alert.service,
                parameters={"timeout_seconds": 180},
            ),
        ]

    async def _create_restart_actions(
        self, triage_result: TriageResult
    ) -> list[RemediationAction]:
        """Create restart actions."""
        return [
            RemediationAction(
                action_id=str(uuid.uuid4()),
                action_type="rolling_restart",
                target=triage_result.alert.service,
                parameters={"batch_size": 1, "delay_seconds": 30},
            ),
            RemediationAction(
                action_id=str(uuid.uuid4()),
                action_type="verify_health",
                target=triage_result.alert.service,
                parameters={"timeout_seconds": 300},
            ),
        ]

    async def _create_generic_remediation_actions(
        self, triage_result: TriageResult
    ) -> list[RemediationAction]:
        """Create generic remediation actions."""
        actions = []

        for i, step in enumerate(triage_result.remediation_steps):
            actions.append(
                RemediationAction(
                    action_id=str(uuid.uuid4()),
                    action_type="runbook_step",
                    target=triage_result.alert.service,
                    parameters={"step_number": i + 1, "description": step},
                )
            )

        return actions

    async def _execute_action(self, action: RemediationAction) -> str:
        """Execute a remediation action."""
        # In production, this would call actual remediation APIs
        # For now, simulate execution

        self._logger.info(
            "Executing remediation action",
            action_id=action.action_id,
            action_type=action.action_type,
            target=action.target,
        )

        await asyncio.sleep(0.1)  # Simulate execution

        return f"Action {action.action_type} completed successfully"

    def register_auto_remediation_rule(
        self,
        service: str | None = None,
        metric: str | None = None,
        severity: str | None = None,
        action: TriageAction = TriageAction.AUTO_REMEDIATE,
        steps: list[str] | None = None,
    ) -> None:
        """Register an auto-remediation rule."""
        self._auto_remediation_rules.append(
            {
                "service": service,
                "metric": metric,
                "severity": severity,
                "action": action,
                "steps": steps or [],
            }
        )

    # =========================================================================
    # Operational Reporting
    # =========================================================================

    async def generate_operational_report(self, days: int = 7) -> OperationalReport:
        """
        Generate comprehensive operational report.

        Args:
            days: Number of days to include

        Returns:
            Operational report
        """
        report_id = str(uuid.uuid4())
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days)

        # Get deployment health report
        deployment_health = await self._deployment_correlator.generate_health_report(
            days
        )

        # Get incident metrics
        incidents = [
            i
            for i in self._incident_analyzer._incidents.values()
            if i.detected_at >= start_time
        ]

        incidents_by_severity: dict[str, int] = {}
        for incident in incidents:
            sev = incident.severity.value
            incidents_by_severity[sev] = incidents_by_severity.get(sev, 0) + 1

        mttr_values = [
            i.metrics.mttr_seconds for i in incidents if i.metrics.mttr_seconds > 0
        ]
        avg_mttr = sum(mttr_values) / len(mttr_values) if mttr_values else 0

        # Calculate incidents per deployment
        incidents_per_deployment = len(incidents) / max(
            deployment_health.total_deployments, 1
        )

        # Get SLO statuses
        slo_statuses = []
        slos_at_risk = 0
        for slo_id in self._incident_analyzer._slos:
            # In production, get actual values
            status = await self._incident_analyzer.get_slo_status(slo_id, 99.5)
            slo_statuses.append(status)
            if status.status in ["warning", "critical"]:
                slos_at_risk += 1

        # Get topology stats
        snapshot = await self._topology_mapper.take_snapshot()

        # Get patterns
        patterns = list(self._incident_analyzer._patterns.values())

        # Get predictive alerts
        predictive_alerts = await self._incident_analyzer.generate_predictive_alerts()

        # Generate insights
        insights = await self._generate_insights(deployment_health, incidents, patterns)

        return OperationalReport(
            report_id=report_id,
            period_start=start_time,
            period_end=end_time,
            total_deployments=deployment_health.total_deployments,
            successful_deployments=deployment_health.successful_deployments,
            failed_deployments=deployment_health.failed_deployments,
            deployment_success_rate=deployment_health.success_rate,
            mean_time_to_deploy=deployment_health.mean_time_to_deploy,
            total_incidents=len(incidents),
            incidents_by_severity=incidents_by_severity,
            mttr_seconds=avg_mttr,
            incidents_per_deployment=incidents_per_deployment,
            slo_statuses=slo_statuses,
            slos_at_risk=slos_at_risk,
            total_resources=snapshot.total_resources,
            resources_by_status={},
            estimated_monthly_cost=snapshot.total_monthly_cost,
            active_patterns=patterns,
            predictive_alerts=predictive_alerts,
            insights=insights,
        )

    async def _generate_insights(
        self,
        deployment_health: DeploymentHealthReport,
        incidents: list[Incident],
        patterns: list[IncidentPattern],
    ) -> list[DevOpsInsight]:
        """Generate operational insights."""
        insights = []

        # Deployment quality insight
        if deployment_health.success_rate < 0.95:
            insights.append(
                DevOpsInsight(
                    insight_id=str(uuid.uuid4()),
                    category="deployments",
                    title="Deployment Success Rate Below Target",
                    description=f"Current success rate is {deployment_health.success_rate:.1%}, below 95% target",
                    severity="high",
                    evidence=[
                        f"{deployment_health.failed_deployments} failed deployments",
                        f"{deployment_health.rolled_back_deployments} rolled back",
                    ],
                    recommendations=[
                        "Review pre-deployment validation",
                        "Improve staging environment testing",
                        "Consider canary deployments",
                    ],
                    affected_services=deployment_health.high_risk_services,
                )
            )

        # Incident correlation insight
        if deployment_health.incident_correlation_rate > 0.1:
            insights.append(
                DevOpsInsight(
                    insight_id=str(uuid.uuid4()),
                    category="incidents",
                    title="High Deployment-Incident Correlation",
                    description=f"{deployment_health.incident_correlation_rate:.1%} of deployments correlate with incidents",
                    severity="high",
                    evidence=[
                        f"{deployment_health.deployments_causing_incidents} deployments caused incidents"
                    ],
                    recommendations=[
                        "Implement deployment health gates",
                        "Add automated rollback triggers",
                        "Improve monitoring coverage",
                    ],
                    affected_services=[],
                )
            )

        # Pattern-based insight
        for pattern in patterns:
            if pattern.occurrence_count >= 5:
                insights.append(
                    DevOpsInsight(
                        insight_id=str(uuid.uuid4()),
                        category="patterns",
                        title=f"Recurring Pattern Detected: {pattern.name}",
                        description=pattern.description,
                        severity="medium",
                        evidence=[f"{pattern.occurrence_count} occurrences detected"],
                        recommendations=pattern.prevention_suggestions,
                        affected_services=pattern.common_services,
                    )
                )

        return insights

    # =========================================================================
    # Component Access
    # =========================================================================

    @property
    def deployment_correlator(self) -> DeploymentHistoryCorrelator:
        """Access deployment correlator directly."""
        return self._deployment_correlator

    @property
    def topology_mapper(self) -> ResourceTopologyMapper:
        """Access topology mapper directly."""
        return self._topology_mapper

    @property
    def incident_analyzer(self) -> IncidentPatternAnalyzer:
        """Access incident analyzer directly."""
        return self._incident_analyzer

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    async def process_alert_end_to_end(self, alert: Alert) -> dict[str, Any]:
        """
        Process an alert through full triage and remediation.

        Args:
            alert: The incoming alert

        Returns:
            Complete processing result
        """
        # Triage
        triage_result = await self.triage_alert(alert)

        # Execute remediation if appropriate
        workflow = None
        if triage_result.auto_remediation_available and triage_result.confidence >= 0.7:
            workflow = await self.execute_remediation(triage_result)

        # Create incident if needed
        incident = None
        if triage_result.action in [
            TriageAction.CREATE_INCIDENT,
            TriageAction.PAGE_ONCALL,
            TriageAction.ESCALATE,
        ]:
            incident = Incident(
                incident_id=str(uuid.uuid4()),
                title=alert.title,
                description=alert.description,
                severity=triage_result.estimated_severity,
                status=IncidentStatus.DETECTED,
                category=self._infer_category(alert),
                affected_services=triage_result.affected_services,
                affected_regions=[],
                customer_impact="Under investigation",
                detected_at=alert.fired_at,
                related_alerts=[alert.alert_id],
            )
            await self._incident_analyzer.record_incident(incident)

        return {
            "triage": triage_result,
            "workflow": workflow,
            "incident": incident,
            "action_taken": triage_result.action.value,
            "confidence": triage_result.confidence,
        }
