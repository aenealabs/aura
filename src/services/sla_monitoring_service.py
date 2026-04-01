"""
SLA Monitoring Service.

Tracks Service Level Agreements (SLAs) and Service Level Objectives (SLOs):
- Uptime monitoring and availability calculations
- Latency percentile tracking (p50, p95, p99)
- Error rate monitoring
- SLA breach detection and alerting
- Credit calculation for SLA violations

Enterprise SLA Tiers:
- Standard: 99.5% uptime, p95 < 500ms
- Professional: 99.9% uptime, p95 < 200ms
- Enterprise: 99.95% uptime, p95 < 100ms
- Government: 99.99% uptime, p95 < 50ms (custom SLA)
"""

import logging
import statistics
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================


class SLATier(str, Enum):
    """SLA tier levels."""

    STANDARD = "standard"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    GOVERNMENT = "government"


class SLOMetric(str, Enum):
    """Service Level Objective metrics."""

    UPTIME = "uptime"
    LATENCY_P50 = "latency_p50"
    LATENCY_P95 = "latency_p95"
    LATENCY_P99 = "latency_p99"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"


class BreachSeverity(str, Enum):
    """SLA breach severity levels."""

    WARNING = "warning"
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


class CreditStatus(str, Enum):
    """SLA credit status."""

    PENDING = "pending"
    APPROVED = "approved"
    APPLIED = "applied"
    REJECTED = "rejected"


# =============================================================================
# SLA Definitions
# =============================================================================


@dataclass
class SLODefinition:
    """Definition of a Service Level Objective."""

    metric: SLOMetric
    target: float
    unit: str
    comparison: str  # "gte" (>=), "lte" (<=)
    description: str


@dataclass
class SLADefinition:
    """Complete SLA definition for a tier."""

    tier: SLATier
    name: str
    uptime_target: float  # Percentage (e.g., 99.9)
    latency_p50_ms: int
    latency_p95_ms: int
    latency_p99_ms: int
    error_rate_target: float  # Percentage
    credit_schedule: Dict[str, float]  # Uptime range -> credit percentage
    response_time_hours: int  # Support response time
    resolution_time_hours: int  # Issue resolution time


# SLA tier definitions
SLA_TIERS: Dict[SLATier, SLADefinition] = {
    SLATier.STANDARD: SLADefinition(
        tier=SLATier.STANDARD,
        name="Standard SLA",
        uptime_target=99.5,
        latency_p50_ms=200,
        latency_p95_ms=500,
        latency_p99_ms=1000,
        error_rate_target=1.0,
        credit_schedule={
            "99.0-99.5": 10,
            "95.0-99.0": 25,
            "90.0-95.0": 50,
            "0-90.0": 100,
        },
        response_time_hours=24,
        resolution_time_hours=72,
    ),
    SLATier.PROFESSIONAL: SLADefinition(
        tier=SLATier.PROFESSIONAL,
        name="Professional SLA",
        uptime_target=99.9,
        latency_p50_ms=100,
        latency_p95_ms=200,
        latency_p99_ms=500,
        error_rate_target=0.5,
        credit_schedule={
            "99.5-99.9": 10,
            "99.0-99.5": 25,
            "95.0-99.0": 50,
            "0-95.0": 100,
        },
        response_time_hours=8,
        resolution_time_hours=24,
    ),
    SLATier.ENTERPRISE: SLADefinition(
        tier=SLATier.ENTERPRISE,
        name="Enterprise SLA",
        uptime_target=99.95,
        latency_p50_ms=50,
        latency_p95_ms=100,
        latency_p99_ms=200,
        error_rate_target=0.1,
        credit_schedule={
            "99.9-99.95": 10,
            "99.5-99.9": 25,
            "99.0-99.5": 50,
            "0-99.0": 100,
        },
        response_time_hours=4,
        resolution_time_hours=8,
    ),
    SLATier.GOVERNMENT: SLADefinition(
        tier=SLATier.GOVERNMENT,
        name="Government SLA",
        uptime_target=99.99,
        latency_p50_ms=25,
        latency_p95_ms=50,
        latency_p99_ms=100,
        error_rate_target=0.01,
        credit_schedule={
            "99.95-99.99": 10,
            "99.9-99.95": 25,
            "99.5-99.9": 50,
            "0-99.5": 100,
        },
        response_time_hours=1,
        resolution_time_hours=4,
    ),
}


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class MetricDataPoint:
    """Single metric data point."""

    timestamp: datetime
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SLOStatus:
    """Current status of an SLO."""

    metric: SLOMetric
    target: float
    current: float
    is_met: bool
    margin: float  # Positive = within target, negative = breaching
    trend: str  # "improving", "stable", "degrading"
    samples: int


@dataclass
class SLAReport:
    """SLA compliance report for a period."""

    report_id: str
    customer_id: str
    tier: SLATier
    period_start: datetime
    period_end: datetime
    uptime_actual: float
    uptime_target: float
    latency_p50: float
    latency_p95: float
    latency_p99: float
    error_rate: float
    slo_statuses: List[SLOStatus]
    is_compliant: bool
    breaches: List[Dict[str, Any]]
    credit_eligible: bool
    credit_percentage: float
    credit_amount_cents: int
    generated_at: datetime


@dataclass
class SLABreach:
    """Record of an SLA breach."""

    breach_id: str
    customer_id: str
    tier: SLATier
    metric: SLOMetric
    target: float
    actual: float
    severity: BreachSeverity
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_minutes: int = 0
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class SLACredit:
    """SLA credit for a customer."""

    credit_id: str
    customer_id: str
    period_start: datetime
    period_end: datetime
    uptime_actual: float
    credit_percentage: float
    invoice_amount_cents: int
    credit_amount_cents: int
    status: CreditStatus
    report_id: str
    created_at: datetime
    approved_at: Optional[datetime] = None
    applied_at: Optional[datetime] = None


# =============================================================================
# SLA Monitoring Service
# =============================================================================


class SLAMonitoringService:
    """
    Service for monitoring SLAs and calculating credits.

    Tracks metrics, detects breaches, generates reports, and calculates
    service credits for SLA violations.
    """

    def __init__(self) -> None:
        """Initialize the SLA monitoring service."""
        # In-memory storage (production would use DynamoDB/TimeStream)
        self._customer_tiers: Dict[str, SLATier] = {}
        self._metrics: Dict[str, List[MetricDataPoint]] = {}
        self._breaches: Dict[str, SLABreach] = {}
        self._credits: Dict[str, SLACredit] = {}
        self._reports: Dict[str, SLAReport] = {}

        # Active breach tracking
        self._active_breaches: Dict[str, str] = {}  # customer:metric -> breach_id

        logger.info("SLAMonitoringService initialized")

    # -------------------------------------------------------------------------
    # Customer Configuration
    # -------------------------------------------------------------------------

    def set_customer_tier(self, customer_id: str, tier: SLATier) -> None:
        """Set the SLA tier for a customer."""
        self._customer_tiers[customer_id] = tier
        logger.info(f"Set SLA tier for {customer_id}: {tier.value}")

    def get_customer_tier(self, customer_id: str) -> SLATier:
        """Get the SLA tier for a customer."""
        return self._customer_tiers.get(customer_id, SLATier.STANDARD)

    def get_sla_definition(self, tier: SLATier) -> SLADefinition:
        """Get the SLA definition for a tier."""
        return SLA_TIERS[tier]

    # -------------------------------------------------------------------------
    # Metric Recording
    # -------------------------------------------------------------------------

    def record_metric(
        self,
        customer_id: str,
        metric: SLOMetric,
        value: float,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record a metric data point.

        Args:
            customer_id: Customer identifier
            metric: Type of metric
            value: Metric value
            timestamp: When the metric was recorded
            metadata: Additional context
        """
        key = f"{customer_id}:{metric.value}"

        if key not in self._metrics:
            self._metrics[key] = []

        data_point = MetricDataPoint(
            timestamp=timestamp or datetime.now(timezone.utc),
            value=value,
            metadata=metadata or {},
        )

        self._metrics[key].append(data_point)

        # Check for breaches
        self._check_for_breach(customer_id, metric, value)

        # Cleanup old data points (keep 30 days)
        self._cleanup_old_metrics(key)

    def record_request(
        self,
        customer_id: str,
        latency_ms: float,
        success: bool,
        endpoint: Optional[str] = None,
    ) -> None:
        """
        Record an API request for SLA tracking.

        Convenience method that records latency and updates error rate.

        Args:
            customer_id: Customer identifier
            latency_ms: Request latency in milliseconds
            success: Whether the request succeeded
            endpoint: API endpoint (for metadata)
        """
        timestamp = datetime.now(timezone.utc)
        metadata = {"endpoint": endpoint} if endpoint else {}

        # Record latency
        self.record_metric(
            customer_id=customer_id,
            metric=SLOMetric.LATENCY_P95,  # Individual samples for percentile calc
            value=latency_ms,
            timestamp=timestamp,
            metadata=metadata,
        )

        # Track success/failure for error rate
        error_value = 0 if success else 1
        self.record_metric(
            customer_id=customer_id,
            metric=SLOMetric.ERROR_RATE,
            value=error_value,
            timestamp=timestamp,
            metadata=metadata,
        )

    def record_uptime_check(
        self,
        customer_id: str,
        is_up: bool,
        check_duration_ms: float,
    ) -> None:
        """
        Record an uptime check result.

        Args:
            customer_id: Customer identifier
            is_up: Whether the service was up
            check_duration_ms: Duration of the health check
        """
        self.record_metric(
            customer_id=customer_id,
            metric=SLOMetric.UPTIME,
            value=1 if is_up else 0,
            metadata={"check_duration_ms": check_duration_ms},
        )

    # -------------------------------------------------------------------------
    # Breach Detection
    # -------------------------------------------------------------------------

    def _check_for_breach(
        self,
        customer_id: str,
        metric: SLOMetric,
        value: float,
    ) -> Optional[SLABreach]:
        """Check if a metric value breaches SLA and handle accordingly."""
        tier = self.get_customer_tier(customer_id)
        sla = SLA_TIERS[tier]

        target = self._get_target_for_metric(sla, metric)
        if target is None:
            return None

        is_breach = self._is_breach(metric, value, target)
        breach_key = f"{customer_id}:{metric.value}"

        if is_breach:
            if breach_key not in self._active_breaches:
                # New breach
                breach = self._create_breach(customer_id, tier, metric, target, value)
                self._active_breaches[breach_key] = breach.breach_id
                return breach
        else:
            if breach_key in self._active_breaches:
                # Breach ended
                breach_id = self._active_breaches.pop(breach_key)
                self._end_breach(breach_id)

        return None

    def _get_target_for_metric(
        self, sla: SLADefinition, metric: SLOMetric
    ) -> Optional[float]:
        """Get the target value for a metric from SLA definition."""
        if metric == SLOMetric.UPTIME:
            return sla.uptime_target
        elif metric == SLOMetric.LATENCY_P50:
            return sla.latency_p50_ms
        elif metric == SLOMetric.LATENCY_P95:
            return sla.latency_p95_ms
        elif metric == SLOMetric.LATENCY_P99:
            return sla.latency_p99_ms
        elif metric == SLOMetric.ERROR_RATE:
            return sla.error_rate_target
        return None

    def _is_breach(self, metric: SLOMetric, value: float, target: float) -> bool:
        """Determine if a value breaches the target."""
        if metric in (
            SLOMetric.LATENCY_P50,
            SLOMetric.LATENCY_P95,
            SLOMetric.LATENCY_P99,
            SLOMetric.ERROR_RATE,
        ):
            return value > target  # Lower is better
        elif metric == SLOMetric.UPTIME:
            return value < 1  # 1 = up, 0 = down
        return False

    def _create_breach(
        self,
        customer_id: str,
        tier: SLATier,
        metric: SLOMetric,
        target: float,
        actual: float,
    ) -> SLABreach:
        """Create a new SLA breach record."""
        severity = self._calculate_severity(metric, target, actual)

        breach = SLABreach(
            breach_id=f"breach_{uuid.uuid4().hex[:12]}",
            customer_id=customer_id,
            tier=tier,
            metric=metric,
            target=target,
            actual=actual,
            severity=severity,
            started_at=datetime.now(timezone.utc),
        )

        self._breaches[breach.breach_id] = breach

        logger.warning(
            f"SLA breach detected: {customer_id} {metric.value} "
            f"(target={target}, actual={actual}, severity={severity.value})"
        )

        return breach

    def _end_breach(self, breach_id: str) -> None:
        """Mark a breach as ended."""
        breach = self._breaches.get(breach_id)
        if breach:
            breach.ended_at = datetime.now(timezone.utc)
            breach.duration_minutes = int(
                (breach.ended_at - breach.started_at).total_seconds() / 60
            )
            logger.info(
                f"SLA breach ended: {breach_id} (duration={breach.duration_minutes}m)"
            )

    def _calculate_severity(
        self, metric: SLOMetric, target: float, actual: float
    ) -> BreachSeverity:
        """Calculate breach severity based on deviation from target."""
        if metric == SLOMetric.UPTIME:
            return BreachSeverity.CRITICAL  # Any downtime is critical

        deviation = abs(actual - target) / target if target > 0 else 1

        if deviation < 0.1:
            return BreachSeverity.WARNING
        elif deviation < 0.25:
            return BreachSeverity.MINOR
        elif deviation < 0.5:
            return BreachSeverity.MAJOR
        else:
            return BreachSeverity.CRITICAL

    # -------------------------------------------------------------------------
    # SLA Calculations
    # -------------------------------------------------------------------------

    def calculate_uptime(
        self,
        customer_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> float:
        """Calculate uptime percentage for a period."""
        key = f"{customer_id}:{SLOMetric.UPTIME.value}"
        data_points = self._metrics.get(key, [])

        relevant = [
            dp for dp in data_points if period_start <= dp.timestamp <= period_end
        ]

        if not relevant:
            return 100.0  # No data = assume up

        up_count = sum(1 for dp in relevant if dp.value >= 1)
        return (up_count / len(relevant)) * 100

    def calculate_latency_percentiles(
        self,
        customer_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> Tuple[float, float, float]:
        """Calculate latency percentiles (p50, p95, p99) for a period."""
        key = f"{customer_id}:{SLOMetric.LATENCY_P95.value}"
        data_points = self._metrics.get(key, [])

        relevant = [
            dp.value for dp in data_points if period_start <= dp.timestamp <= period_end
        ]

        if not relevant:
            return (0.0, 0.0, 0.0)

        sorted_values = sorted(relevant)
        n = len(sorted_values)

        p50 = sorted_values[int(n * 0.50)] if n > 0 else 0
        p95 = sorted_values[int(n * 0.95)] if n > 0 else 0
        p99 = sorted_values[int(n * 0.99)] if n > 0 else 0

        return (p50, p95, p99)

    def calculate_error_rate(
        self,
        customer_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> float:
        """Calculate error rate percentage for a period."""
        key = f"{customer_id}:{SLOMetric.ERROR_RATE.value}"
        data_points = self._metrics.get(key, [])

        relevant = [
            dp for dp in data_points if period_start <= dp.timestamp <= period_end
        ]

        if not relevant:
            return 0.0

        error_count = sum(1 for dp in relevant if dp.value > 0)
        return (error_count / len(relevant)) * 100

    # -------------------------------------------------------------------------
    # Credit Calculation
    # -------------------------------------------------------------------------

    def calculate_credit(
        self,
        customer_id: str,
        uptime_actual: float,
        invoice_amount_cents: int,
    ) -> Tuple[float, int]:
        """
        Calculate SLA credit based on uptime and invoice amount.

        Args:
            customer_id: Customer identifier
            uptime_actual: Actual uptime percentage
            invoice_amount_cents: Invoice amount in cents

        Returns:
            Tuple of (credit_percentage, credit_amount_cents)
        """
        tier = self.get_customer_tier(customer_id)
        sla = SLA_TIERS[tier]

        # Find applicable credit tier
        credit_percentage = 0.0
        for range_str, pct in sla.credit_schedule.items():
            low, high = map(float, range_str.split("-"))
            if low <= uptime_actual < high:
                credit_percentage = pct
                break

        # Calculate credit amount
        credit_amount = int(
            Decimal(invoice_amount_cents * credit_percentage / 100).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )

        return (credit_percentage, credit_amount)

    def create_credit(
        self,
        customer_id: str,
        period_start: datetime,
        period_end: datetime,
        invoice_amount_cents: int,
        report_id: str,
    ) -> Optional[SLACredit]:
        """
        Create an SLA credit record if eligible.

        Args:
            customer_id: Customer identifier
            period_start: Billing period start
            period_end: Billing period end
            invoice_amount_cents: Invoice amount
            report_id: Associated SLA report ID

        Returns:
            SLACredit if eligible, None otherwise
        """
        uptime = self.calculate_uptime(customer_id, period_start, period_end)
        tier = self.get_customer_tier(customer_id)
        sla = SLA_TIERS[tier]

        # Check if credit is warranted
        if uptime >= sla.uptime_target:
            return None  # SLA met, no credit

        credit_pct, credit_amount = self.calculate_credit(
            customer_id, uptime, invoice_amount_cents
        )

        if credit_amount <= 0:
            return None

        credit = SLACredit(
            credit_id=f"credit_{uuid.uuid4().hex[:12]}",
            customer_id=customer_id,
            period_start=period_start,
            period_end=period_end,
            uptime_actual=uptime,
            credit_percentage=credit_pct,
            invoice_amount_cents=invoice_amount_cents,
            credit_amount_cents=credit_amount,
            status=CreditStatus.PENDING,
            report_id=report_id,
            created_at=datetime.now(timezone.utc),
        )

        self._credits[credit.credit_id] = credit

        logger.info(
            f"SLA credit created: {credit.credit_id} for {customer_id} "
            f"({credit_pct}% = ${credit_amount / 100:.2f})"
        )

        return credit

    def approve_credit(self, credit_id: str, approved_by: str) -> bool:
        """Approve a pending SLA credit."""
        credit = self._credits.get(credit_id)
        if not credit or credit.status != CreditStatus.PENDING:
            return False

        credit.status = CreditStatus.APPROVED
        credit.approved_at = datetime.now(timezone.utc)

        logger.info(f"SLA credit approved: {credit_id} by {approved_by}")
        return True

    def apply_credit(self, credit_id: str) -> bool:
        """Mark a credit as applied to invoice."""
        credit = self._credits.get(credit_id)
        if not credit or credit.status != CreditStatus.APPROVED:
            return False

        credit.status = CreditStatus.APPLIED
        credit.applied_at = datetime.now(timezone.utc)

        logger.info(f"SLA credit applied: {credit_id}")
        return True

    # -------------------------------------------------------------------------
    # Reports
    # -------------------------------------------------------------------------

    def generate_report(
        self,
        customer_id: str,
        period_start: datetime,
        period_end: datetime,
        invoice_amount_cents: int = 0,
    ) -> SLAReport:
        """
        Generate a comprehensive SLA report for a customer and period.

        Args:
            customer_id: Customer identifier
            period_start: Report period start
            period_end: Report period end
            invoice_amount_cents: Optional invoice amount for credit calc

        Returns:
            Complete SLAReport
        """
        tier = self.get_customer_tier(customer_id)
        sla = SLA_TIERS[tier]

        # Calculate metrics
        uptime = self.calculate_uptime(customer_id, period_start, period_end)
        p50, p95, p99 = self.calculate_latency_percentiles(
            customer_id, period_start, period_end
        )
        error_rate = self.calculate_error_rate(customer_id, period_start, period_end)

        # Build SLO statuses
        slo_statuses = [
            SLOStatus(
                metric=SLOMetric.UPTIME,
                target=sla.uptime_target,
                current=uptime,
                is_met=uptime >= sla.uptime_target,
                margin=uptime - sla.uptime_target,
                trend=self._calculate_trend(customer_id, SLOMetric.UPTIME),
                samples=self._count_samples(
                    customer_id, SLOMetric.UPTIME, period_start, period_end
                ),
            ),
            SLOStatus(
                metric=SLOMetric.LATENCY_P95,
                target=sla.latency_p95_ms,
                current=p95,
                is_met=p95 <= sla.latency_p95_ms,
                margin=sla.latency_p95_ms - p95,
                trend=self._calculate_trend(customer_id, SLOMetric.LATENCY_P95),
                samples=self._count_samples(
                    customer_id, SLOMetric.LATENCY_P95, period_start, period_end
                ),
            ),
            SLOStatus(
                metric=SLOMetric.ERROR_RATE,
                target=sla.error_rate_target,
                current=error_rate,
                is_met=error_rate <= sla.error_rate_target,
                margin=sla.error_rate_target - error_rate,
                trend=self._calculate_trend(customer_id, SLOMetric.ERROR_RATE),
                samples=self._count_samples(
                    customer_id, SLOMetric.ERROR_RATE, period_start, period_end
                ),
            ),
        ]

        # Get breaches for period
        breaches = [
            {
                "breach_id": b.breach_id,
                "metric": b.metric.value,
                "severity": b.severity.value,
                "started_at": b.started_at.isoformat(),
                "duration_minutes": b.duration_minutes,
            }
            for b in self._breaches.values()
            if b.customer_id == customer_id
            and b.started_at >= period_start
            and b.started_at <= period_end
        ]

        # Check overall compliance
        is_compliant = all(s.is_met for s in slo_statuses)

        # Calculate credit if applicable
        credit_pct, credit_amount = (0.0, 0)
        if not is_compliant and invoice_amount_cents > 0:
            credit_pct, credit_amount = self.calculate_credit(
                customer_id, uptime, invoice_amount_cents
            )

        report = SLAReport(
            report_id=f"rpt_{uuid.uuid4().hex[:12]}",
            customer_id=customer_id,
            tier=tier,
            period_start=period_start,
            period_end=period_end,
            uptime_actual=uptime,
            uptime_target=sla.uptime_target,
            latency_p50=p50,
            latency_p95=p95,
            latency_p99=p99,
            error_rate=error_rate,
            slo_statuses=slo_statuses,
            is_compliant=is_compliant,
            breaches=breaches,
            credit_eligible=credit_amount > 0,
            credit_percentage=credit_pct,
            credit_amount_cents=credit_amount,
            generated_at=datetime.now(timezone.utc),
        )

        self._reports[report.report_id] = report

        logger.info(
            f"SLA report generated: {report.report_id} for {customer_id} "
            f"(compliant={is_compliant}, uptime={uptime:.2f}%)"
        )

        return report

    def _calculate_trend(self, customer_id: str, metric: SLOMetric) -> str:
        """Calculate metric trend over recent period."""
        key = f"{customer_id}:{metric.value}"
        data_points = self._metrics.get(key, [])

        if len(data_points) < 10:
            return "stable"

        # Compare recent half to older half
        mid = len(data_points) // 2
        older = [dp.value for dp in data_points[:mid]]
        recent = [dp.value for dp in data_points[mid:]]

        older_avg = statistics.mean(older) if older else 0
        recent_avg = statistics.mean(recent) if recent else 0

        if metric in (
            SLOMetric.LATENCY_P50,
            SLOMetric.LATENCY_P95,
            SLOMetric.LATENCY_P99,
            SLOMetric.ERROR_RATE,
        ):
            # Lower is better
            if recent_avg < older_avg * 0.9:
                return "improving"
            elif recent_avg > older_avg * 1.1:
                return "degrading"
        else:
            # Higher is better (uptime)
            if recent_avg > older_avg * 1.01:
                return "improving"
            elif recent_avg < older_avg * 0.99:
                return "degrading"

        return "stable"

    def _count_samples(
        self,
        customer_id: str,
        metric: SLOMetric,
        period_start: datetime,
        period_end: datetime,
    ) -> int:
        """Count metric samples in a period."""
        key = f"{customer_id}:{metric.value}"
        data_points = self._metrics.get(key, [])

        return len(
            [dp for dp in data_points if period_start <= dp.timestamp <= period_end]
        )

    # -------------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------------

    def get_breaches(
        self,
        customer_id: Optional[str] = None,
        active_only: bool = False,
    ) -> List[SLABreach]:
        """Get SLA breaches, optionally filtered."""
        breaches = list(self._breaches.values())

        if customer_id:
            breaches = [b for b in breaches if b.customer_id == customer_id]

        if active_only:
            breaches = [b for b in breaches if b.ended_at is None]

        return sorted(breaches, key=lambda b: b.started_at, reverse=True)

    def get_credits(
        self,
        customer_id: Optional[str] = None,
        status: Optional[CreditStatus] = None,
    ) -> List[SLACredit]:
        """Get SLA credits, optionally filtered."""
        credits = list(self._credits.values())

        if customer_id:
            credits = [c for c in credits if c.customer_id == customer_id]

        if status:
            credits = [c for c in credits if c.status == status]

        return sorted(credits, key=lambda c: c.created_at, reverse=True)

    def get_report(self, report_id: str) -> Optional[SLAReport]:
        """Get a specific SLA report."""
        return self._reports.get(report_id)

    def get_current_slo_status(self, customer_id: str) -> List[SLOStatus]:
        """Get current SLO status for a customer (last 24 hours)."""
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(hours=24)

        tier = self.get_customer_tier(customer_id)
        sla = SLA_TIERS[tier]

        uptime = self.calculate_uptime(customer_id, period_start, now)
        _, p95, _ = self.calculate_latency_percentiles(customer_id, period_start, now)
        error_rate = self.calculate_error_rate(customer_id, period_start, now)

        return [
            SLOStatus(
                metric=SLOMetric.UPTIME,
                target=sla.uptime_target,
                current=uptime,
                is_met=uptime >= sla.uptime_target,
                margin=uptime - sla.uptime_target,
                trend=self._calculate_trend(customer_id, SLOMetric.UPTIME),
                samples=self._count_samples(
                    customer_id, SLOMetric.UPTIME, period_start, now
                ),
            ),
            SLOStatus(
                metric=SLOMetric.LATENCY_P95,
                target=sla.latency_p95_ms,
                current=p95,
                is_met=p95 <= sla.latency_p95_ms,
                margin=sla.latency_p95_ms - p95,
                trend=self._calculate_trend(customer_id, SLOMetric.LATENCY_P95),
                samples=self._count_samples(
                    customer_id, SLOMetric.LATENCY_P95, period_start, now
                ),
            ),
            SLOStatus(
                metric=SLOMetric.ERROR_RATE,
                target=sla.error_rate_target,
                current=error_rate,
                is_met=error_rate <= sla.error_rate_target,
                margin=sla.error_rate_target - error_rate,
                trend=self._calculate_trend(customer_id, SLOMetric.ERROR_RATE),
                samples=self._count_samples(
                    customer_id, SLOMetric.ERROR_RATE, period_start, now
                ),
            ),
        ]

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    def _cleanup_old_metrics(self, key: str, retention_days: int = 30) -> None:
        """Remove metrics older than retention period."""
        if key not in self._metrics:
            return

        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        self._metrics[key] = [dp for dp in self._metrics[key] if dp.timestamp >= cutoff]


# =============================================================================
# Singleton Instance
# =============================================================================

_service: Optional[SLAMonitoringService] = None


def get_sla_monitoring_service() -> SLAMonitoringService:
    """Get the singleton SLA monitoring service."""
    global _service
    if _service is None:
        _service = SLAMonitoringService()
    return _service


def reset_sla_monitoring_service() -> None:
    """Reset the SLA monitoring service (for testing)."""
    global _service
    _service = None
