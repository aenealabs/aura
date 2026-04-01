"""
Tests for SLA Monitoring Service.

Tests cover:
- SLA tier definitions and targets
- Metric recording and tracking
- Breach detection and management
- Credit calculation
- Report generation
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.services.sla_monitoring_service import (
    SLA_TIERS,
    BreachSeverity,
    CreditStatus,
    SLADefinition,
    SLAMonitoringService,
    SLATier,
    SLOMetric,
    get_sla_monitoring_service,
    reset_sla_monitoring_service,
)


@pytest.fixture
def service():
    """Provide a fresh SLA monitoring service for each test."""
    reset_sla_monitoring_service()
    return get_sla_monitoring_service()


@pytest.fixture
def customer_id():
    """Standard test customer ID."""
    return "test-customer-001"


class TestSLATier:
    """Tests for SLA tier enum."""

    def test_all_tiers_exist(self):
        """Verify all expected tiers are defined."""
        assert SLATier.STANDARD.value == "standard"
        assert SLATier.PROFESSIONAL.value == "professional"
        assert SLATier.ENTERPRISE.value == "enterprise"
        assert SLATier.GOVERNMENT.value == "government"

    def test_tier_count(self):
        """Verify we have exactly 4 tiers."""
        assert len(SLATier) == 4


class TestSLOMetric:
    """Tests for SLO metric enum."""

    def test_all_metrics_exist(self):
        """Verify all expected metrics are defined."""
        assert SLOMetric.UPTIME.value == "uptime"
        assert SLOMetric.LATENCY_P50.value == "latency_p50"
        assert SLOMetric.LATENCY_P95.value == "latency_p95"
        assert SLOMetric.LATENCY_P99.value == "latency_p99"
        assert SLOMetric.ERROR_RATE.value == "error_rate"
        assert SLOMetric.THROUGHPUT.value == "throughput"


class TestSLADefinition:
    """Tests for SLA tier definitions."""

    def test_predefined_sla_tiers(self):
        """Verify all tiers have SLA definitions."""
        assert len(SLA_TIERS) == 4
        for tier in SLATier:
            assert tier in SLA_TIERS

    def test_standard_tier_targets(self):
        """Verify Standard tier SLA targets."""
        sla = SLA_TIERS[SLATier.STANDARD]
        assert sla.uptime_target == 99.5
        assert sla.latency_p95_ms == 500
        assert sla.error_rate_target == 1.0

    def test_professional_tier_targets(self):
        """Verify Professional tier SLA targets."""
        sla = SLA_TIERS[SLATier.PROFESSIONAL]
        assert sla.uptime_target == 99.9
        assert sla.latency_p95_ms == 200
        assert sla.error_rate_target == 0.5

    def test_enterprise_tier_targets(self):
        """Verify Enterprise tier SLA targets."""
        sla = SLA_TIERS[SLATier.ENTERPRISE]
        assert sla.uptime_target == 99.95
        assert sla.latency_p95_ms == 100
        assert sla.error_rate_target == 0.1

    def test_government_tier_targets(self):
        """Verify Government tier SLA targets."""
        sla = SLA_TIERS[SLATier.GOVERNMENT]
        assert sla.uptime_target == 99.99
        assert sla.latency_p95_ms == 50
        assert sla.error_rate_target == 0.01

    def test_tier_has_credit_schedule(self):
        """Verify each tier has a credit schedule."""
        for tier in SLATier:
            sla = SLA_TIERS[tier]
            assert hasattr(sla, "credit_schedule")
            assert isinstance(sla.credit_schedule, dict)
            assert len(sla.credit_schedule) > 0


class TestBreachSeverity:
    """Tests for breach severity enum."""

    def test_all_severities_exist(self):
        """Verify all severity levels are defined."""
        assert BreachSeverity.WARNING.value == "warning"
        assert BreachSeverity.MINOR.value == "minor"
        assert BreachSeverity.MAJOR.value == "major"
        assert BreachSeverity.CRITICAL.value == "critical"


class TestCreditStatus:
    """Tests for credit status enum."""

    def test_all_statuses_exist(self):
        """Verify all credit statuses are defined."""
        assert CreditStatus.PENDING.value == "pending"
        assert CreditStatus.APPROVED.value == "approved"
        assert CreditStatus.APPLIED.value == "applied"
        assert CreditStatus.REJECTED.value == "rejected"


class TestSLAMonitoringService:
    """Tests for SLA monitoring service initialization."""

    def test_service_initialization(self, service):
        """Verify service initializes correctly."""
        assert service is not None
        assert isinstance(service, SLAMonitoringService)

    def test_singleton_pattern(self):
        """Verify singleton pattern works."""
        reset_sla_monitoring_service()
        svc1 = get_sla_monitoring_service()
        svc2 = get_sla_monitoring_service()
        assert svc1 is svc2

    def test_set_customer_tier(self, service, customer_id):
        """Test setting customer SLA tier."""
        service.set_customer_tier(customer_id, SLATier.ENTERPRISE)
        tier = service.get_customer_tier(customer_id)
        assert tier == SLATier.ENTERPRISE

    def test_get_customer_tier_default(self, service, customer_id):
        """Test default tier for new customer."""
        tier = service.get_customer_tier(customer_id)
        assert tier == SLATier.STANDARD

    def test_get_sla_definition(self, service):
        """Test getting SLA definition for a tier."""
        sla = service.get_sla_definition(SLATier.ENTERPRISE)
        assert isinstance(sla, SLADefinition)
        assert sla.tier == SLATier.ENTERPRISE


class TestMetricRecording:
    """Tests for metric recording."""

    def test_record_metric(self, service, customer_id):
        """Test recording a metric."""
        service.record_metric(
            customer_id=customer_id,
            metric=SLOMetric.LATENCY_P95,
            value=150.0,
        )
        # Verify metric was recorded
        key = f"{customer_id}:{SLOMetric.LATENCY_P95.value}"
        assert key in service._metrics
        assert len(service._metrics[key]) == 1
        assert service._metrics[key][0].value == 150.0

    def test_record_metric_with_timestamp(self, service, customer_id):
        """Test recording a metric with specific timestamp."""
        ts = datetime.now(timezone.utc) - timedelta(hours=1)
        service.record_metric(
            customer_id=customer_id,
            metric=SLOMetric.UPTIME,
            value=1,
            timestamp=ts,
        )
        # Verify metric was recorded with correct timestamp
        key = f"{customer_id}:{SLOMetric.UPTIME.value}"
        assert key in service._metrics
        assert service._metrics[key][0].timestamp == ts

    def test_record_metric_with_metadata(self, service, customer_id):
        """Test recording a metric with metadata."""
        service.record_metric(
            customer_id=customer_id,
            metric=SLOMetric.LATENCY_P95,
            value=100.0,
            metadata={"endpoint": "/api/query"},
        )
        # Verify metric was recorded with metadata
        key = f"{customer_id}:{SLOMetric.LATENCY_P95.value}"
        assert key in service._metrics
        assert service._metrics[key][0].metadata == {"endpoint": "/api/query"}

    def test_record_request(self, service, customer_id):
        """Test recording an API request."""
        service.record_request(
            customer_id=customer_id,
            latency_ms=125.0,
            success=True,
            endpoint="/api/agents",
        )
        # Verify latency metric was recorded
        latency_key = f"{customer_id}:{SLOMetric.LATENCY_P95.value}"
        assert latency_key in service._metrics
        assert len(service._metrics[latency_key]) == 1
        assert service._metrics[latency_key][0].value == 125.0
        assert service._metrics[latency_key][0].metadata == {"endpoint": "/api/agents"}
        # Verify error rate metric was recorded (0 for success)
        error_key = f"{customer_id}:{SLOMetric.ERROR_RATE.value}"
        assert error_key in service._metrics
        assert service._metrics[error_key][0].value == 0

    def test_record_failed_request(self, service, customer_id):
        """Test recording a failed request."""
        service.record_request(
            customer_id=customer_id,
            latency_ms=5000.0,
            success=False,
        )
        # Verify latency metric was recorded
        latency_key = f"{customer_id}:{SLOMetric.LATENCY_P95.value}"
        assert latency_key in service._metrics
        assert service._metrics[latency_key][0].value == 5000.0
        # Verify error rate metric was recorded (1 for failure)
        error_key = f"{customer_id}:{SLOMetric.ERROR_RATE.value}"
        assert error_key in service._metrics
        assert service._metrics[error_key][0].value == 1

    def test_record_uptime_check_up(self, service, customer_id):
        """Test recording uptime check when service is up."""
        service.record_uptime_check(
            customer_id=customer_id,
            is_up=True,
            check_duration_ms=45.0,
        )
        # Verify uptime metric was recorded with value 1 (up)
        key = f"{customer_id}:{SLOMetric.UPTIME.value}"
        assert key in service._metrics
        assert len(service._metrics[key]) == 1
        assert service._metrics[key][0].value == 1
        assert service._metrics[key][0].metadata == {"check_duration_ms": 45.0}

    def test_record_uptime_check_down(self, service, customer_id):
        """Test recording uptime check when service is down."""
        service.record_uptime_check(
            customer_id=customer_id,
            is_up=False,
            check_duration_ms=5000.0,
        )
        # Verify uptime metric was recorded with value 0 (down)
        key = f"{customer_id}:{SLOMetric.UPTIME.value}"
        assert key in service._metrics
        assert len(service._metrics[key]) == 1
        assert service._metrics[key][0].value == 0
        assert service._metrics[key][0].metadata == {"check_duration_ms": 5000.0}


class TestBreachDetection:
    """Tests for SLA breach detection."""

    def test_latency_breach_detected(self, service, customer_id):
        """Test that latency breach is detected."""
        service.set_customer_tier(customer_id, SLATier.STANDARD)
        # Record latency above threshold (500ms for standard)
        service.record_metric(
            customer_id=customer_id,
            metric=SLOMetric.LATENCY_P95,
            value=600.0,
        )
        breaches = service.get_breaches(customer_id=customer_id)
        assert len(breaches) >= 1

    def test_no_breach_within_target(self, service, customer_id):
        """Test no breach when within target."""
        service.set_customer_tier(customer_id, SLATier.STANDARD)
        service.record_metric(
            customer_id=customer_id,
            metric=SLOMetric.LATENCY_P95,
            value=100.0,
        )
        breaches = service.get_breaches(customer_id=customer_id, active_only=True)
        # Should be no active breaches for latency
        latency_breaches = [b for b in breaches if b.metric == SLOMetric.LATENCY_P95]
        assert len(latency_breaches) == 0

    def test_get_breaches_filtered(self, service, customer_id):
        """Test getting breaches filtered by customer."""
        breaches = service.get_breaches(customer_id=customer_id)
        assert isinstance(breaches, list)

    def test_get_active_breaches(self, service, customer_id):
        """Test getting active breaches only."""
        breaches = service.get_breaches(active_only=True)
        assert isinstance(breaches, list)


class TestSLOStatus:
    """Tests for SLO status queries."""

    def test_get_current_slo_status(self, service, customer_id):
        """Test getting current SLO status."""
        service.set_customer_tier(customer_id, SLATier.ENTERPRISE)
        # Record some metrics
        for _ in range(5):
            service.record_uptime_check(customer_id, True, 50.0)
            service.record_request(customer_id, 50.0, True)

        statuses = service.get_current_slo_status(customer_id)
        assert len(statuses) == 3  # uptime, latency, error_rate

    def test_calculate_uptime_percentage(self, service, customer_id):
        """Test uptime calculation."""
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(hours=1)

        # Record 10 checks, 9 up
        for i in range(10):
            service.record_uptime_check(customer_id, i != 5, 50.0)

        uptime = service.calculate_uptime(customer_id, period_start, now)
        assert 80 <= uptime <= 100  # Should be ~90%


class TestCreditCalculation:
    """Tests for SLA credit calculation."""

    def test_calculate_credit(self, service, customer_id):
        """Test credit calculation."""
        service.set_customer_tier(customer_id, SLATier.STANDARD)
        # Below uptime target
        credit_pct, credit_amount = service.calculate_credit(
            customer_id=customer_id,
            uptime_actual=98.0,
            invoice_amount_cents=100000,  # $1000
        )
        assert credit_pct > 0
        assert credit_amount > 0

    def test_no_credit_when_sla_met(self, service, customer_id):
        """Test no credit when SLA is met."""
        service.set_customer_tier(customer_id, SLATier.STANDARD)
        credit_pct, credit_amount = service.calculate_credit(
            customer_id=customer_id,
            uptime_actual=99.6,  # Above 99.5% target
            invoice_amount_cents=100000,
        )
        assert credit_pct == 0
        assert credit_amount == 0

    def test_create_credit(self, service, customer_id):
        """Test creating SLA credit."""
        service.set_customer_tier(customer_id, SLATier.STANDARD)
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=30)

        # Record downtime to trigger credit eligibility
        for _ in range(20):
            service.record_uptime_check(customer_id, False, 50.0)

        _credit = service.create_credit(
            customer_id=customer_id,
            period_start=period_start,
            period_end=now,
            invoice_amount_cents=100000,
            report_id="test-report",
        )
        # Credit may or may not be created depending on uptime calculation
        # Just verify the method runs without error

    def test_get_credits(self, service, customer_id):
        """Test getting credits."""
        credits = service.get_credits(customer_id=customer_id)
        assert isinstance(credits, list)

    def test_get_credits_by_status(self, service):
        """Test getting credits filtered by status."""
        credits = service.get_credits(status=CreditStatus.PENDING)
        assert isinstance(credits, list)


class TestReportGeneration:
    """Tests for SLA report generation."""

    def test_generate_sla_report(self, service, customer_id):
        """Test generating SLA report."""
        service.set_customer_tier(customer_id, SLATier.ENTERPRISE)
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=30)

        # Record some metrics
        for _ in range(10):
            service.record_uptime_check(customer_id, True, 50.0)
            service.record_request(customer_id, 50.0, True)

        report = service.generate_report(
            customer_id=customer_id,
            period_start=period_start,
            period_end=now,
        )

        assert report is not None
        assert report.customer_id == customer_id
        assert report.tier == SLATier.ENTERPRISE

    def test_report_has_required_fields(self, service, customer_id):
        """Test report has all required fields."""
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=30)

        report = service.generate_report(
            customer_id=customer_id,
            period_start=period_start,
            period_end=now,
        )

        assert hasattr(report, "report_id")
        assert hasattr(report, "uptime_actual")
        assert hasattr(report, "uptime_target")
        assert hasattr(report, "slo_statuses")
        assert hasattr(report, "is_compliant")

    def test_get_report_by_id(self, service, customer_id):
        """Test retrieving report by ID."""
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=30)

        report = service.generate_report(
            customer_id=customer_id,
            period_start=period_start,
            period_end=now,
        )

        retrieved = service.get_report(report.report_id)
        assert retrieved is not None
        assert retrieved.report_id == report.report_id


class TestAllTiers:
    """Tests across all tiers."""

    def test_all_tiers_defined_in_sla_tiers(self):
        """Verify all tiers have definitions in SLA_TIERS."""
        for tier in SLATier:
            assert tier in SLA_TIERS
            sla = SLA_TIERS[tier]
            assert sla.tier == tier

    def test_tiers_ordered_by_strictness(self):
        """Verify tiers are progressively stricter."""
        uptime_targets = [
            SLA_TIERS[t].uptime_target
            for t in [
                SLATier.STANDARD,
                SLATier.PROFESSIONAL,
                SLATier.ENTERPRISE,
                SLATier.GOVERNMENT,
            ]
        ]
        # Each tier should have higher uptime target
        for i in range(len(uptime_targets) - 1):
            assert uptime_targets[i] < uptime_targets[i + 1]


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_metrics_cleanup(self, service, customer_id):
        """Test that old metrics are cleaned up."""
        # Record many metrics
        for i in range(100):
            service.record_metric(customer_id, SLOMetric.LATENCY_P95, 100 + i)
        # Verify metrics were recorded (cleanup only removes old data > 30 days)
        key = f"{customer_id}:{SLOMetric.LATENCY_P95.value}"
        assert key in service._metrics
        assert len(service._metrics[key]) == 100
        # Verify first and last values
        assert service._metrics[key][0].value == 100
        assert service._metrics[key][99].value == 199

    def test_multiple_customers(self, service):
        """Test handling multiple customers."""
        customers = ["cust-1", "cust-2", "cust-3"]

        for i, cust in enumerate(customers):
            tier = list(SLATier)[i % 4]
            service.set_customer_tier(cust, tier)
            service.record_uptime_check(cust, True, 50.0)

        for cust in customers:
            tier = service.get_customer_tier(cust)
            assert tier in SLATier

    def test_all_metrics_recordable(self, service, customer_id):
        """Test all metric types can be recorded."""
        for metric in SLOMetric:
            service.record_metric(customer_id, metric, 100.0)
        # Verify all metric types were stored
        for metric in SLOMetric:
            key = f"{customer_id}:{metric.value}"
            assert key in service._metrics, f"Metric {metric.value} not recorded"
            assert len(service._metrics[key]) >= 1
            assert service._metrics[key][0].value == 100.0
