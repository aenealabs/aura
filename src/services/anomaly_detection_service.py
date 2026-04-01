"""
Project Aura - Real-Time Anomaly Detection Service

Monitors system metrics, security events, and threat intelligence feeds to detect
anomalies and trigger automated analysis and remediation via the MetaOrchestrator.

Integrates with:
- ObservabilityService for system metrics (Four Golden Signals)
- ThreatFeedClient for CVE and vulnerability intelligence
- MetaOrchestrator for automated investigation and remediation
- External tool connectors (Slack, Jira, PagerDuty) for notifications

Detection Methods:
- Statistical baselines (Z-score, MAD)
- Time-series analysis (rolling windows)
- Pattern matching (security events)
- Rule engine (CVE matching, threshold checks)
"""

import asyncio
import hashlib
import logging
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================


class AnomalyType(Enum):
    """Types of detected anomalies."""

    LATENCY_SPIKE = "latency_spike"
    ERROR_RATE_SURGE = "error_rate_surge"
    TRAFFIC_ANOMALY = "traffic_anomaly"
    RESOURCE_SATURATION = "resource_saturation"
    SECURITY_EVENT = "security_event"
    NEW_CVE = "new_cve"
    KNOWN_EXPLOITATION = "known_exploitation"
    DEPENDENCY_VULNERABILITY = "dependency_vulnerability"
    PATTERN_MATCH = "pattern_match"
    AGENT_FAILURE = "agent_failure"
    HITL_TIMEOUT = "hitl_timeout"
    SANDBOX_ANOMALY = "sandbox_anomaly"


class AnomalySeverity(Enum):
    """Anomaly severity levels aligned with incident management."""

    CRITICAL = "critical"  # Immediate attention, wake people up
    HIGH = "high"  # Attention within 1 hour
    MEDIUM = "medium"  # Attention within 1 day
    LOW = "low"  # Informational
    INFO = "info"  # Tracking only


class AnomalyStatus(Enum):
    """Lifecycle status of an anomaly."""

    DETECTED = "detected"
    INVESTIGATING = "investigating"
    TRIGGERED_ORCHESTRATOR = "triggered_orchestrator"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"
    ESCALATED = "escalated"


@dataclass
class AnomalyEvent:
    """Represents a detected anomaly."""

    id: str
    type: AnomalyType
    severity: AnomalySeverity
    title: str
    description: str
    source: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: AnomalyStatus = AnomalyStatus.DETECTED
    metadata: dict[str, Any] = field(default_factory=dict)
    dedup_key: str | None = None
    cve_id: str | None = None
    affected_components: list[str] = field(default_factory=list)
    recommended_action: str | None = None
    orchestrator_task_id: str | None = None
    hitl_approval_id: str | None = None

    def __post_init__(self) -> None:
        """Generate dedup key if not provided."""
        if not self.dedup_key:
            # Create dedup key from type + source + (CVE or title hash)
            key_parts = [self.type.value, self.source]
            if self.cve_id:
                key_parts.append(self.cve_id)
            else:
                key_parts.append(
                    hashlib.md5(self.title.encode(), usedforsecurity=False).hexdigest()[
                        :8
                    ]
                )
            self.dedup_key = "-".join(key_parts)


@dataclass
class MetricBaseline:
    """Statistical baseline for a metric."""

    metric_name: str
    mean: float
    std_dev: float
    median: float
    min_value: float
    max_value: float
    sample_count: int
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def z_score_threshold(self) -> float:
        """Z-score threshold for anomaly detection (default 3 sigma)."""
        return 3.0

    def is_anomaly(self, value: float) -> tuple[bool, float]:
        """Check if value is anomalous based on Z-score."""
        if self.std_dev == 0:
            return (False, 0.0)

        z_score = abs(value - self.mean) / self.std_dev
        return (z_score > self.z_score_threshold, z_score)


@dataclass
class DetectionRule:
    """Custom rule for pattern-based anomaly detection."""

    id: str
    name: str
    pattern: str  # Regex pattern or condition
    severity: AnomalySeverity
    anomaly_type: AnomalyType
    enabled: bool = True
    cooldown_seconds: int = 300  # Prevent alert storms
    last_triggered: datetime | None = None


# =============================================================================
# Anomaly Detection Service
# =============================================================================


class AnomalyDetectionService:
    """
    Real-time anomaly detection engine.

    Monitors system metrics and events, detects anomalies using statistical
    analysis and pattern matching, and triggers the MetaOrchestrator for
    automated investigation and remediation.

    Usage:
        detector = AnomalyDetectionService()

        # Register a callback for when anomalies are detected
        detector.on_anomaly(async_callback_function)

        # Feed metrics continuously
        detector.record_metric("api.latency_p95", 150.0)
        detector.record_metric("api.error_rate", 0.02)

        # Feed security events
        await detector.process_security_event({
            "type": "new_cve",
            "cve_id": "CVE-2025-0001",
            "severity": "CRITICAL"
        })

        # Start background monitoring loop
        await detector.start_monitoring()
    """

    def __init__(
        self,
        baseline_window_hours: int = 24,
        min_samples_for_baseline: int = 30,
        enable_notifications: bool = True,
    ):
        """
        Initialize anomaly detection service.

        Args:
            baseline_window_hours: Hours of data to consider for baseline
            min_samples_for_baseline: Minimum samples before baseline is valid
            enable_notifications: Whether to send external notifications
        """
        self.baseline_window_hours = baseline_window_hours
        self.min_samples_for_baseline = min_samples_for_baseline
        self.enable_notifications = enable_notifications

        # Metric storage (rolling windows)
        self._metric_windows: dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))

        # Baselines for each metric
        self._baselines: dict[str, MetricBaseline] = {}

        # Active anomalies (dedup_key -> AnomalyEvent)
        self._active_anomalies: dict[str, AnomalyEvent] = {}

        # Recently seen anomalies for deduplication (dedup_key -> expiry time)
        self._recent_anomalies: dict[str, datetime] = {}
        self._dedup_window_minutes = 30

        # Detection rules
        self._rules: list[DetectionRule] = []

        # Callbacks for anomaly events
        self._anomaly_callbacks: list[Callable] = []

        # Statistics - use typed counters to avoid mypy issues
        self._total_anomalies_detected: int = 0
        self._anomalies_by_type: dict[str, int] = defaultdict(int)
        self._anomalies_by_severity: dict[str, int] = defaultdict(int)
        self._orchestrator_triggers: int = 0
        self._notifications_sent: int = 0
        self._false_positives_dismissed: int = 0

        # Monitoring state
        self._is_monitoring = False
        self._monitoring_task: asyncio.Task | None = None

        # Thresholds for quick detection (before baseline is established)
        self._default_thresholds = {
            "error_rate": 0.05,  # 5% error rate
            "latency_p95_ms": 5000,  # 5 seconds
            "cpu_percent": 85,  # 85% CPU
            "memory_percent": 90,  # 90% memory
            "connections_percent": 80,  # 80% connection pool
        }

        # Load default detection rules
        self._load_default_rules()

        logger.info("AnomalyDetectionService initialized")

    def _load_default_rules(self) -> None:
        """Load default security and system detection rules."""
        self._rules = [
            DetectionRule(
                id="critical-cve",
                name="Critical CVE Detection",
                pattern="CRITICAL",
                severity=AnomalySeverity.CRITICAL,
                anomaly_type=AnomalyType.NEW_CVE,
                cooldown_seconds=0,  # Always alert on new critical CVEs
            ),
            DetectionRule(
                id="known-exploitation",
                name="Known Exploitation (CISA KEV)",
                pattern="known_exploitation",
                severity=AnomalySeverity.CRITICAL,
                anomaly_type=AnomalyType.KNOWN_EXPLOITATION,
                cooldown_seconds=0,
            ),
            DetectionRule(
                id="agent-max-depth",
                name="Agent Max Depth Exceeded",
                pattern="max_depth_exceeded",
                severity=AnomalySeverity.HIGH,
                anomaly_type=AnomalyType.AGENT_FAILURE,
                cooldown_seconds=300,
            ),
            DetectionRule(
                id="sandbox-escape",
                name="Sandbox Escape Attempt",
                pattern="sandbox_escape|breakout|privilege_escalation",
                severity=AnomalySeverity.CRITICAL,
                anomaly_type=AnomalyType.SANDBOX_ANOMALY,
                cooldown_seconds=0,
            ),
            DetectionRule(
                id="hitl-timeout",
                name="HITL Approval Timeout",
                pattern="approval_timeout",
                severity=AnomalySeverity.HIGH,
                anomaly_type=AnomalyType.HITL_TIMEOUT,
                cooldown_seconds=600,
            ),
        ]

    # =========================================================================
    # Metric Recording and Baseline Management
    # =========================================================================

    def record_metric(
        self,
        metric_name: str,
        value: float,
        timestamp: datetime | None = None,
        check_anomaly: bool = True,
    ) -> AnomalyEvent | None:
        """
        Record a metric value and optionally check for anomalies.

        Args:
            metric_name: Name of the metric (e.g., "api.latency_p95")
            value: Metric value
            timestamp: Optional timestamp (defaults to now)
            check_anomaly: Whether to check if value is anomalous

        Returns:
            AnomalyEvent if anomaly detected, None otherwise
        """
        ts = timestamp or datetime.now(timezone.utc)

        # Store in rolling window
        self._metric_windows[metric_name].append((ts, value))

        # Update baseline periodically
        self._maybe_update_baseline(metric_name)

        if not check_anomaly:
            return None

        # Check against baseline or default threshold
        return self._check_metric_anomaly(metric_name, value, ts)

    def _maybe_update_baseline(self, metric_name: str) -> None:
        """Update baseline if we have enough samples."""
        window = self._metric_windows[metric_name]
        if len(window) < self.min_samples_for_baseline:
            return

        # Check if baseline needs refresh (every hour)
        existing = self._baselines.get(metric_name)
        if existing:
            age = datetime.now(timezone.utc) - existing.last_updated
            if age < timedelta(hours=1):
                return

        # Calculate baseline from window
        values = [v for _, v in window]
        self._baselines[metric_name] = MetricBaseline(
            metric_name=metric_name,
            mean=statistics.mean(values),
            std_dev=statistics.stdev(values) if len(values) > 1 else 0,
            median=statistics.median(values),
            min_value=min(values),
            max_value=max(values),
            sample_count=len(values),
        )

        logger.debug(
            f"Updated baseline for {metric_name}: "
            f"mean={self._baselines[metric_name].mean:.2f}, "
            f"std={self._baselines[metric_name].std_dev:.2f}"
        )

    def _check_metric_anomaly(
        self, metric_name: str, value: float, timestamp: datetime
    ) -> AnomalyEvent | None:
        """Check if a metric value is anomalous."""
        baseline = self._baselines.get(metric_name)

        if baseline and baseline.sample_count >= self.min_samples_for_baseline:
            # Use statistical baseline
            is_anomaly, z_score = baseline.is_anomaly(value)
            if is_anomaly:
                return self._create_metric_anomaly(
                    metric_name, value, baseline, z_score, timestamp
                )
        else:
            # Use default thresholds
            threshold_key = self._get_threshold_key(metric_name)
            if threshold_key and threshold_key in self._default_thresholds:
                threshold = self._default_thresholds[threshold_key]
                if value > threshold:
                    return self._create_threshold_anomaly(
                        metric_name, value, threshold, timestamp
                    )

        return None

    def _get_threshold_key(self, metric_name: str) -> str | None:
        """Map metric name to threshold key."""
        if "error_rate" in metric_name.lower():
            return "error_rate"
        elif "latency" in metric_name.lower() and "p95" in metric_name.lower():
            return "latency_p95_ms"
        elif "cpu" in metric_name.lower():
            return "cpu_percent"
        elif "memory" in metric_name.lower():
            return "memory_percent"
        elif "connection" in metric_name.lower():
            return "connections_percent"
        return None

    def _create_metric_anomaly(
        self,
        metric_name: str,
        value: float,
        baseline: MetricBaseline,
        z_score: float,
        timestamp: datetime,
    ) -> AnomalyEvent | None:
        """Create anomaly event for metric deviation."""
        # Determine anomaly type and severity based on metric
        if "error" in metric_name.lower():
            anomaly_type = AnomalyType.ERROR_RATE_SURGE
            severity = AnomalySeverity.CRITICAL if z_score > 5 else AnomalySeverity.HIGH
        elif "latency" in metric_name.lower():
            anomaly_type = AnomalyType.LATENCY_SPIKE
            severity = AnomalySeverity.MEDIUM if z_score < 4 else AnomalySeverity.HIGH
        elif "cpu" in metric_name.lower() or "memory" in metric_name.lower():
            anomaly_type = AnomalyType.RESOURCE_SATURATION
            severity = AnomalySeverity.HIGH if value > 90 else AnomalySeverity.MEDIUM
        else:
            anomaly_type = AnomalyType.TRAFFIC_ANOMALY
            severity = AnomalySeverity.MEDIUM

        event = AnomalyEvent(
            id=f"anomaly-{metric_name}-{timestamp.timestamp():.0f}",
            type=anomaly_type,
            severity=severity,
            title=f"{anomaly_type.value.replace('_', ' ').title()}: {metric_name}",
            description=(
                f"Metric {metric_name} value {value:.2f} deviates significantly "
                f"from baseline (mean={baseline.mean:.2f}, z-score={z_score:.2f})"
            ),
            source="metric_baseline",
            timestamp=timestamp,
            metadata={
                "metric_name": metric_name,
                "current_value": value,
                "baseline_mean": baseline.mean,
                "baseline_std": baseline.std_dev,
                "z_score": z_score,
            },
            recommended_action=(
                f"Investigate {anomaly_type.value.replace('_', ' ')} "
                "and identify root cause"
            ),
        )

        return self._process_anomaly(event)

    def _create_threshold_anomaly(
        self,
        metric_name: str,
        value: float,
        threshold: float,
        timestamp: datetime,
    ) -> AnomalyEvent | None:
        """Create anomaly event for threshold breach."""
        # Determine type based on metric
        if "error" in metric_name.lower():
            anomaly_type = AnomalyType.ERROR_RATE_SURGE
            severity = (
                AnomalySeverity.CRITICAL
                if value > threshold * 2
                else AnomalySeverity.HIGH
            )
        elif "latency" in metric_name.lower():
            anomaly_type = AnomalyType.LATENCY_SPIKE
            severity = AnomalySeverity.HIGH
        else:
            anomaly_type = AnomalyType.RESOURCE_SATURATION
            severity = AnomalySeverity.HIGH

        event = AnomalyEvent(
            id=f"threshold-{metric_name}-{timestamp.timestamp():.0f}",
            type=anomaly_type,
            severity=severity,
            title=f"Threshold Breach: {metric_name}",
            description=(
                f"Metric {metric_name} value {value:.2f} exceeds "
                f"threshold {threshold:.2f}"
            ),
            source="threshold_check",
            timestamp=timestamp,
            metadata={
                "metric_name": metric_name,
                "current_value": value,
                "threshold": threshold,
                "exceed_ratio": value / threshold,
            },
            recommended_action="Investigate root cause and remediate",
        )

        return self._process_anomaly(event)

    # =========================================================================
    # Security Event Processing
    # =========================================================================

    async def process_security_event(
        self, event: dict[str, Any]
    ) -> AnomalyEvent | None:
        """
        Process a security event and create anomaly if warranted.

        Args:
            event: Security event dict with fields like:
                - type: Event type (new_cve, exploitation, etc.)
                - cve_id: CVE identifier if applicable
                - severity: CRITICAL, HIGH, MEDIUM, LOW
                - description: Event description
                - affected_components: List of affected components

        Returns:
            AnomalyEvent if anomaly detected, None otherwise
        """
        event_type = event.get("type", "unknown")
        severity_str = event.get("severity", "MEDIUM").upper()
        cve_id = event.get("cve_id")

        # Map severity
        severity_map = {
            "CRITICAL": AnomalySeverity.CRITICAL,
            "HIGH": AnomalySeverity.HIGH,
            "MEDIUM": AnomalySeverity.MEDIUM,
            "LOW": AnomalySeverity.LOW,
            "INFO": AnomalySeverity.INFO,
        }
        severity = severity_map.get(severity_str, AnomalySeverity.MEDIUM)

        # Map event type to anomaly type
        type_map = {
            "new_cve": AnomalyType.NEW_CVE,
            "known_exploitation": AnomalyType.KNOWN_EXPLOITATION,
            "dependency_vulnerability": AnomalyType.DEPENDENCY_VULNERABILITY,
            "sandbox_escape": AnomalyType.SANDBOX_ANOMALY,
            "agent_failure": AnomalyType.AGENT_FAILURE,
            "hitl_timeout": AnomalyType.HITL_TIMEOUT,
            "pattern_match": AnomalyType.PATTERN_MATCH,
        }
        anomaly_type = type_map.get(event_type, AnomalyType.SECURITY_EVENT)

        # Create anomaly event
        anomaly = AnomalyEvent(
            id=f"security-{event_type}-{datetime.now(timezone.utc).timestamp():.0f}",
            type=anomaly_type,
            severity=severity,
            title=event.get("title", f"Security Event: {event_type}"),
            description=event.get(
                "description", f"Security event of type {event_type} detected"
            ),
            source="security_event",
            cve_id=cve_id,
            affected_components=event.get("affected_components", []),
            metadata=event,
            recommended_action=self._get_recommended_action(anomaly_type, severity),
        )

        return self._process_anomaly(anomaly)

    def _get_recommended_action(
        self, anomaly_type: AnomalyType, severity: AnomalySeverity
    ) -> str:
        """Get recommended action based on anomaly type and severity."""
        actions = {
            AnomalyType.NEW_CVE: "Analyze vulnerability impact and generate patch",
            AnomalyType.KNOWN_EXPLOITATION: (
                "Immediate patching required - vulnerability actively exploited"
            ),
            AnomalyType.DEPENDENCY_VULNERABILITY: (
                "Update affected dependency and validate compatibility"
            ),
            AnomalyType.SANDBOX_ANOMALY: (
                "Investigate sandbox isolation breach and contain threat"
            ),
            AnomalyType.AGENT_FAILURE: "Review agent execution logs and retry if safe",
            AnomalyType.HITL_TIMEOUT: "Escalate approval request to backup approvers",
            AnomalyType.ERROR_RATE_SURGE: "Investigate error logs and identify root cause",
            AnomalyType.LATENCY_SPIKE: (
                "Check resource utilization and identify bottlenecks"
            ),
            AnomalyType.RESOURCE_SATURATION: "Scale resources or optimize usage patterns",
        }

        base_action = actions.get(anomaly_type, "Investigate and remediate")

        if severity == AnomalySeverity.CRITICAL:
            return f"URGENT: {base_action}"
        return base_action

    # =========================================================================
    # Anomaly Processing and Deduplication
    # =========================================================================

    def _process_anomaly(self, event: AnomalyEvent) -> AnomalyEvent | None:
        """
        Process anomaly event with deduplication.

        Returns:
            AnomalyEvent if new anomaly, None if duplicate
        """
        # Clean up expired dedup entries
        self._cleanup_dedup_entries()

        # Get dedup key (guaranteed non-None after __post_init__)
        dedup_key: str = event.dedup_key or ""

        # Check for deduplication
        if dedup_key in self._recent_anomalies:
            logger.debug(f"Duplicate anomaly suppressed: {dedup_key}")
            return None

        # Add to recent anomalies for deduplication
        expiry = datetime.now(timezone.utc) + timedelta(
            minutes=self._dedup_window_minutes
        )
        self._recent_anomalies[dedup_key] = expiry

        # Track in active anomalies
        self._active_anomalies[dedup_key] = event

        # Update statistics
        self._total_anomalies_detected += 1
        self._anomalies_by_type[event.type.value] += 1
        self._anomalies_by_severity[event.severity.value] += 1

        logger.info(
            f"Anomaly detected: {event.type.value} ({event.severity.value}) - {event.title}"
        )

        # Trigger callbacks
        self._notify_callbacks(event)

        return event

    def _cleanup_dedup_entries(self) -> None:
        """Remove expired dedup entries."""
        now = datetime.now(timezone.utc)
        expired = [
            key for key, expiry in self._recent_anomalies.items() if expiry < now
        ]
        for key in expired:
            del self._recent_anomalies[key]

    def _notify_callbacks(self, event: AnomalyEvent) -> None:
        """Notify all registered callbacks of new anomaly."""
        for callback in self._anomaly_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(event))
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Error in anomaly callback: {e}")

    # =========================================================================
    # Callback Registration
    # =========================================================================

    def on_anomaly(self, callback: Callable[[AnomalyEvent], Any]) -> None:
        """
        Register a callback for anomaly events.

        Args:
            callback: Function to call when anomaly is detected.
                     Can be sync or async.
        """
        self._anomaly_callbacks.append(callback)
        logger.info(f"Registered anomaly callback: {callback.__name__}")

    # =========================================================================
    # MetaOrchestrator Integration
    # =========================================================================

    async def trigger_orchestrator(
        self,
        anomaly: AnomalyEvent,
        orchestrator: Any,  # MetaOrchestrator
        autonomy_policy: Any | None = None,  # AutonomyPolicy
    ) -> dict[str, Any]:
        """
        Trigger MetaOrchestrator to investigate and remediate anomaly.

        Args:
            anomaly: The anomaly event to investigate
            orchestrator: MetaOrchestrator instance
            autonomy_policy: Optional autonomy policy override

        Returns:
            Orchestrator result dict
        """
        # Update anomaly status
        anomaly.status = AnomalyStatus.TRIGGERED_ORCHESTRATOR

        # Build task description based on anomaly type
        task = self._build_orchestrator_task(anomaly)

        # Map severity to orchestrator severity string
        severity_map = {
            AnomalySeverity.CRITICAL: "CRITICAL",
            AnomalySeverity.HIGH: "HIGH",
            AnomalySeverity.MEDIUM: "MEDIUM",
            AnomalySeverity.LOW: "LOW",
            AnomalySeverity.INFO: "LOW",
        }

        logger.info(
            f"Triggering MetaOrchestrator for anomaly {anomaly.id}: {task[:100]}..."
        )

        try:
            result = await orchestrator.execute(
                task=task,
                severity=severity_map[anomaly.severity],
                context={
                    "anomaly_id": anomaly.id,
                    "anomaly_type": anomaly.type.value,
                    "cve_id": anomaly.cve_id,
                    "affected_components": anomaly.affected_components,
                    "metadata": anomaly.metadata,
                    "source": "anomaly_detection_service",
                },
            )

            # Track the task ID
            anomaly.orchestrator_task_id = getattr(result, "task_id", None)

            # Check if HITL is required
            if getattr(result, "hitl_required", False):
                anomaly.status = AnomalyStatus.INVESTIGATING
                anomaly.hitl_approval_id = getattr(result, "hitl_request_id", None)
            elif getattr(result, "success", False):
                anomaly.status = AnomalyStatus.RESOLVED

            self._orchestrator_triggers += 1

            return {
                "success": getattr(result, "success", False),
                "task_id": anomaly.orchestrator_task_id,
                "hitl_required": getattr(result, "hitl_required", False),
                "hitl_approval_id": anomaly.hitl_approval_id,
            }

        except Exception as e:
            logger.error(f"Failed to trigger orchestrator for {anomaly.id}: {e}")
            anomaly.status = AnomalyStatus.ESCALATED
            return {"success": False, "error": str(e)}

    def _build_orchestrator_task(self, anomaly: AnomalyEvent) -> str:
        """Build task description for MetaOrchestrator."""
        tasks = {
            AnomalyType.NEW_CVE: (
                f"Analyze and patch {anomaly.cve_id or 'vulnerability'}: "
                f"{anomaly.description}"
            ),
            AnomalyType.KNOWN_EXPLOITATION: (
                f"URGENT: Immediately patch actively exploited vulnerability "
                f"{anomaly.cve_id or ''}: {anomaly.description}"
            ),
            AnomalyType.DEPENDENCY_VULNERABILITY: (
                f"Update vulnerable dependency {anomaly.cve_id or ''}: "
                f"{anomaly.description}. Validate compatibility after update."
            ),
            AnomalyType.ERROR_RATE_SURGE: (
                f"Investigate and resolve error rate surge: {anomaly.description}. "
                "Analyze error logs, identify root cause, and implement fix."
            ),
            AnomalyType.LATENCY_SPIKE: (
                f"Investigate and optimize performance issue: {anomaly.description}. "
                "Profile system, identify bottlenecks, and optimize."
            ),
            AnomalyType.RESOURCE_SATURATION: (
                f"Address resource exhaustion: {anomaly.description}. "
                "Analyze usage patterns and optimize or scale resources."
            ),
            AnomalyType.SANDBOX_ANOMALY: (
                f"SECURITY: Investigate potential sandbox isolation breach: "
                f"{anomaly.description}. Contain threat and audit impact."
            ),
            AnomalyType.AGENT_FAILURE: (
                f"Review and resolve agent failure: {anomaly.description}. "
                "Analyze execution logs and determine if retry is safe."
            ),
            AnomalyType.HITL_TIMEOUT: (
                f"Handle HITL approval timeout: {anomaly.description}. "
                "Escalate to backup approvers or implement fallback."
            ),
        }

        return tasks.get(
            anomaly.type,
            f"Investigate anomaly: {anomaly.title}. {anomaly.description}",
        )

    # =========================================================================
    # External Notifications
    # =========================================================================

    async def send_notifications(
        self,
        anomaly: AnomalyEvent,
        slack_connector: Any | None = None,
        jira_connector: Any | None = None,
        pagerduty_connector: Any | None = None,
        approval_url: str | None = None,
    ) -> dict[str, bool]:
        """
        Send notifications to external tools for an anomaly.

        Args:
            anomaly: The anomaly event
            slack_connector: Optional SlackConnector instance
            jira_connector: Optional JiraConnector instance
            pagerduty_connector: Optional PagerDutyConnector instance
            approval_url: Optional URL to HITL approval dashboard

        Returns:
            Dict mapping tool name to success status
        """
        if not self.enable_notifications:
            return {}

        results: dict[str, bool] = {}

        # Only notify for significant severities
        if anomaly.severity in (AnomalySeverity.INFO, AnomalySeverity.LOW):
            logger.debug(f"Skipping notifications for {anomaly.severity.value} anomaly")
            return results

        # Slack notification
        if slack_connector:
            try:
                result = await slack_connector.send_security_alert(
                    severity=anomaly.severity.value.upper(),
                    title=anomaly.title,
                    description=anomaly.description,
                    cve_id=anomaly.cve_id,
                    affected_file=(
                        anomaly.affected_components[0]
                        if anomaly.affected_components
                        else None
                    ),
                    recommendation=anomaly.recommended_action,
                    approval_url=approval_url,
                )
                results["slack"] = result.success
                if result.success:
                    self._notifications_sent += 1
            except Exception as e:
                logger.error(f"Slack notification failed: {e}")
                results["slack"] = False

        # Jira ticket creation (for HIGH and CRITICAL)
        if jira_connector and anomaly.severity in (
            AnomalySeverity.CRITICAL,
            AnomalySeverity.HIGH,
        ):
            try:
                result = await jira_connector.create_security_issue(
                    summary=anomaly.title,
                    cve_id=anomaly.cve_id,
                    severity=anomaly.severity.value.upper(),
                    affected_file=(
                        anomaly.affected_components[0]
                        if anomaly.affected_components
                        else "unknown"
                    ),
                    description=f"{anomaly.description}\n\n{anomaly.recommended_action}",
                )
                results["jira"] = result.success
                if result.success:
                    self._notifications_sent += 1
            except Exception as e:
                logger.error(f"Jira notification failed: {e}")
                results["jira"] = False

        # PagerDuty incident (for CRITICAL)
        if pagerduty_connector and anomaly.severity == AnomalySeverity.CRITICAL:
            try:
                result = await pagerduty_connector.trigger_security_incident(
                    title=anomaly.title,
                    cve_id=anomaly.cve_id,
                    severity=anomaly.severity.value.upper(),
                    affected_file=(
                        anomaly.affected_components[0]
                        if anomaly.affected_components
                        else "unknown"
                    ),
                    description=anomaly.description,
                    approval_url=approval_url,
                )
                results["pagerduty"] = result.success
                if result.success:
                    self._notifications_sent += 1
            except Exception as e:
                logger.error(f"PagerDuty notification failed: {e}")
                results["pagerduty"] = False

        return results

    # =========================================================================
    # Monitoring Loop
    # =========================================================================

    async def start_monitoring(
        self,
        observability_service: Any | None = None,
        threat_feed_client: Any | None = None,
        check_interval_seconds: int = 60,
    ):
        """
        Start background monitoring loop.

        Args:
            observability_service: ObservabilityService instance for metrics
            threat_feed_client: ThreatFeedClient instance for CVE monitoring
            check_interval_seconds: Interval between checks
        """
        if self._is_monitoring:
            logger.warning("Monitoring loop already running")
            return

        self._is_monitoring = True
        logger.info(
            f"Starting anomaly detection monitoring loop "
            f"(interval: {check_interval_seconds}s)"
        )

        async def monitoring_loop():
            while self._is_monitoring:
                try:
                    # Check observability metrics
                    if observability_service:
                        await self._check_observability_metrics(observability_service)

                    # Check threat feeds (less frequently)
                    if threat_feed_client:
                        await self._check_threat_feeds(threat_feed_client)

                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")

                await asyncio.sleep(check_interval_seconds)

        self._monitoring_task = asyncio.create_task(monitoring_loop())

    async def stop_monitoring(self) -> None:
        """Stop the background monitoring loop."""
        self._is_monitoring = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
        logger.info("Anomaly detection monitoring stopped")

    async def _check_observability_metrics(self, observability_service: Any) -> None:
        """Check observability service for anomalies."""
        try:
            health_report = observability_service.get_health_report()

            # Check error rate
            error_rate = (
                health_report.get("golden_signals", {})
                .get("errors", {})
                .get("error_rate", 0)
            )
            self.record_metric("system.error_rate", error_rate)

            # Check latency (if available)
            latency = (
                health_report.get("golden_signals", {}).get("latency", {}).get("p95_ms")
            )
            if latency:
                self.record_metric("system.latency_p95", latency)

            # Check saturation
            saturation = health_report.get("golden_signals", {}).get("saturation", {})
            for resource, value in saturation.items():
                self.record_metric(f"system.{resource}", value)

        except Exception as e:
            logger.error(f"Error checking observability metrics: {e}")

    async def _check_threat_feeds(self, threat_feed_client: Any) -> None:
        """Check threat feeds for new vulnerabilities."""
        try:
            # This would poll NVD/CISA feeds for new CVEs
            # For now, this is a placeholder for the integration
            pass
        except Exception as e:
            logger.error(f"Error checking threat feeds: {e}")

    # =========================================================================
    # Anomaly Management
    # =========================================================================

    def resolve_anomaly(self, dedup_key: str, resolution: str = "resolved") -> None:
        """Mark an anomaly as resolved."""
        if dedup_key in self._active_anomalies:
            anomaly = self._active_anomalies[dedup_key]
            anomaly.status = AnomalyStatus.RESOLVED
            anomaly.metadata["resolution"] = resolution
            anomaly.metadata["resolved_at"] = datetime.now(timezone.utc).isoformat()
            logger.info(f"Anomaly resolved: {dedup_key}")

    def dismiss_anomaly(self, dedup_key: str, reason: str = "false_positive") -> None:
        """Dismiss an anomaly as false positive or not actionable."""
        if dedup_key in self._active_anomalies:
            anomaly = self._active_anomalies[dedup_key]
            anomaly.status = AnomalyStatus.DISMISSED
            anomaly.metadata["dismiss_reason"] = reason
            self._false_positives_dismissed += 1
            logger.info(f"Anomaly dismissed: {dedup_key} ({reason})")

    def get_active_anomalies(self) -> list[AnomalyEvent]:
        """Get all active (unresolved) anomalies."""
        return [
            a
            for a in self._active_anomalies.values()
            if a.status not in (AnomalyStatus.RESOLVED, AnomalyStatus.DISMISSED)
        ]

    def get_anomaly(self, dedup_key: str) -> AnomalyEvent | None:
        """Get anomaly by dedup key."""
        return self._active_anomalies.get(dedup_key)

    # =========================================================================
    # Statistics and Reporting
    # =========================================================================

    def get_statistics(self) -> dict[str, Any]:
        """Get anomaly detection statistics."""
        return {
            "total_anomalies_detected": self._total_anomalies_detected,
            "anomalies_by_type": dict(self._anomalies_by_type),
            "anomalies_by_severity": dict(self._anomalies_by_severity),
            "orchestrator_triggers": self._orchestrator_triggers,
            "notifications_sent": self._notifications_sent,
            "false_positives_dismissed": self._false_positives_dismissed,
            "active_anomalies": len(self.get_active_anomalies()),
            "baselines_established": len(self._baselines),
            "is_monitoring": self._is_monitoring,
        }

    def get_baseline(self, metric_name: str) -> MetricBaseline | None:
        """Get baseline for a specific metric."""
        return self._baselines.get(metric_name)


# =============================================================================
# Factory Function
# =============================================================================


def create_anomaly_detector(
    enable_notifications: bool = True,
    baseline_window_hours: int = 24,
) -> AnomalyDetectionService:
    """
    Create and configure an AnomalyDetectionService instance.

    Args:
        enable_notifications: Whether to send external notifications
        baseline_window_hours: Hours of data for baseline calculation

    Returns:
        Configured AnomalyDetectionService instance
    """
    return AnomalyDetectionService(
        enable_notifications=enable_notifications,
        baseline_window_hours=baseline_window_hours,
    )
