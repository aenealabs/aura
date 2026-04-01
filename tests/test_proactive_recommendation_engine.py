"""
Project Aura - Proactive Recommendation Engine Tests

Tests for the proactive recommendation engine that generates
operational excellence recommendations.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.services.proactive_recommendation_engine import (
    ArchitectureSpec,
    CostData,
    DeploymentEvent,
    ImplementationEffort,
    IncidentRecord,
    ObservabilityConfig,
    PipelineConfig,
    ProactiveRecommendation,
    ProactiveRecommendationEngine,
    RecommendationCategory,
    RecommendationPriority,
    RecommendationSummary,
    ResourceGraph,
)


class TestRecommendationCategory:
    """Tests for RecommendationCategory enum."""

    def test_observability(self):
        """Test observability category."""
        assert RecommendationCategory.OBSERVABILITY.value == "observability"

    def test_infrastructure(self):
        """Test infrastructure category."""
        assert RecommendationCategory.INFRASTRUCTURE.value == "infrastructure"

    def test_deployment_pipeline(self):
        """Test deployment pipeline category."""
        assert RecommendationCategory.DEPLOYMENT_PIPELINE.value == "deployment_pipeline"

    def test_application_resilience(self):
        """Test application resilience category."""
        assert (
            RecommendationCategory.APPLICATION_RESILIENCE.value
            == "application_resilience"
        )

    def test_security(self):
        """Test security category."""
        assert RecommendationCategory.SECURITY.value == "security"

    def test_cost(self):
        """Test cost category."""
        assert RecommendationCategory.COST.value == "cost"

    def test_all_categories_exist(self):
        """Test all expected categories exist."""
        categories = list(RecommendationCategory)
        assert len(categories) == 6


class TestRecommendationPriority:
    """Tests for RecommendationPriority enum."""

    def test_critical(self):
        """Test critical priority."""
        assert RecommendationPriority.CRITICAL.value == "critical"

    def test_high(self):
        """Test high priority."""
        assert RecommendationPriority.HIGH.value == "high"

    def test_medium(self):
        """Test medium priority."""
        assert RecommendationPriority.MEDIUM.value == "medium"

    def test_low(self):
        """Test low priority."""
        assert RecommendationPriority.LOW.value == "low"


class TestImplementationEffort:
    """Tests for ImplementationEffort enum."""

    def test_trivial(self):
        """Test trivial effort."""
        assert ImplementationEffort.TRIVIAL.value == "trivial"

    def test_low(self):
        """Test low effort."""
        assert ImplementationEffort.LOW.value == "low"

    def test_medium(self):
        """Test medium effort."""
        assert ImplementationEffort.MEDIUM.value == "medium"

    def test_high(self):
        """Test high effort."""
        assert ImplementationEffort.HIGH.value == "high"

    def test_major(self):
        """Test major effort."""
        assert ImplementationEffort.MAJOR.value == "major"


class TestProactiveRecommendation:
    """Tests for ProactiveRecommendation dataclass."""

    def test_minimal_recommendation(self):
        """Test minimal recommendation creation."""
        rec = ProactiveRecommendation(
            recommendation_id="REC-001",
            category=RecommendationCategory.OBSERVABILITY,
            priority=RecommendationPriority.HIGH,
            title="Enable tracing",
            description="Enable distributed tracing",
            impact="Faster debugging",
            effort=ImplementationEffort.MEDIUM,
        )
        assert rec.recommendation_id == "REC-001"
        assert rec.category == RecommendationCategory.OBSERVABILITY
        assert rec.evidence == []
        assert rec.implementation_steps == []

    def test_full_recommendation(self):
        """Test full recommendation creation."""
        rec = ProactiveRecommendation(
            recommendation_id="REC-002",
            category=RecommendationCategory.INFRASTRUCTURE,
            priority=RecommendationPriority.CRITICAL,
            title="Add redundancy",
            description="Add multi-AZ support",
            impact="99.99% availability",
            effort=ImplementationEffort.HIGH,
            evidence=["Single point of failure detected"],
            implementation_steps=["Step 1", "Step 2"],
            estimated_improvement="10x improvement",
            affected_resources=["vpc-1", "ec2-1"],
            references=["https://docs.aws.amazon.com"],
        )
        assert len(rec.evidence) == 1
        assert len(rec.implementation_steps) == 2
        assert len(rec.affected_resources) == 2

    def test_recommendation_has_timestamp(self):
        """Test recommendation has created_at timestamp."""
        rec = ProactiveRecommendation(
            recommendation_id="REC-003",
            category=RecommendationCategory.SECURITY,
            priority=RecommendationPriority.HIGH,
            title="Test",
            description="Test",
            impact="Test",
            effort=ImplementationEffort.LOW,
        )
        assert rec.created_at is not None


class TestObservabilityConfig:
    """Tests for ObservabilityConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ObservabilityConfig()
        assert config.log_retention_days == 30
        assert config.metrics_enabled is True
        assert config.tracing_enabled is False
        assert config.alerting_enabled is False
        assert config.dashboards_count == 0
        assert config.alarm_count == 0

    def test_custom_config(self):
        """Test custom configuration values."""
        config = ObservabilityConfig(
            log_retention_days=90,
            tracing_enabled=True,
            alerting_enabled=True,
            dashboards_count=5,
            alarm_count=20,
            log_groups=["app-logs", "access-logs"],
            custom_metrics=["requests", "errors"],
        )
        assert config.log_retention_days == 90
        assert config.tracing_enabled is True
        assert len(config.log_groups) == 2


class TestResourceGraph:
    """Tests for ResourceGraph dataclass."""

    def test_empty_graph(self):
        """Test empty resource graph."""
        graph = ResourceGraph()
        assert graph.nodes == []
        assert graph.edges == []

    def test_graph_with_nodes(self):
        """Test graph with nodes and edges."""
        graph = ResourceGraph(
            nodes=[
                {"id": "ec2-1", "type": "instance"},
                {"id": "rds-1", "type": "database"},
            ],
            edges=[
                {"source": "ec2-1", "target": "rds-1", "type": "connects"},
            ],
        )
        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1


class TestPipelineConfig:
    """Tests for PipelineConfig dataclass."""

    def test_default_config(self):
        """Test default pipeline configuration."""
        config = PipelineConfig()
        assert config.pipeline_name == ""
        assert config.has_tests is False
        assert config.has_security_scan is False
        assert config.has_approval_gate is False
        assert config.failure_rate == 0.0

    def test_full_config(self):
        """Test full pipeline configuration."""
        config = PipelineConfig(
            pipeline_name="main-deploy",
            stages=["build", "test", "deploy"],
            has_tests=True,
            has_security_scan=True,
            has_approval_gate=True,
            deployment_frequency_per_day=5.0,
            failure_rate=0.05,
            mean_time_to_recovery_minutes=30.0,
        )
        assert config.has_tests is True
        assert len(config.stages) == 3


class TestArchitectureSpec:
    """Tests for ArchitectureSpec dataclass."""

    def test_default_spec(self):
        """Test default architecture spec."""
        spec = ArchitectureSpec()
        assert spec.services == []
        assert spec.has_redundancy is False
        assert spec.has_circuit_breakers is False
        assert spec.has_rate_limiting is False
        assert spec.has_health_checks is False

    def test_full_spec(self):
        """Test full architecture spec."""
        spec = ArchitectureSpec(
            services=["api", "worker", "scheduler"],
            databases=["postgres", "redis"],
            has_redundancy=True,
            has_circuit_breakers=True,
            has_rate_limiting=True,
            has_health_checks=True,
        )
        assert len(spec.services) == 3
        assert spec.has_redundancy is True


class TestCostData:
    """Tests for CostData dataclass."""

    def test_default_cost_data(self):
        """Test default cost data."""
        cost = CostData()
        assert cost.monthly_total == 0.0
        assert cost.by_service == {}
        assert cost.trend == "stable"

    def test_cost_data_with_values(self):
        """Test cost data with values."""
        cost = CostData(
            monthly_total=5000.0,
            by_service={"EC2": 2000.0, "RDS": 1500.0, "S3": 500.0},
            trend="increasing",
        )
        assert cost.monthly_total == 5000.0
        assert cost.trend == "increasing"


class TestIncidentRecord:
    """Tests for IncidentRecord dataclass."""

    def test_incident_creation(self):
        """Test incident record creation."""
        incident = IncidentRecord(
            incident_id="INC-001",
            severity="high",
            service="api-gateway",
            duration_minutes=45,
            root_cause="Memory leak",
            occurred_at=datetime.now(timezone.utc),
        )
        assert incident.incident_id == "INC-001"
        assert incident.severity == "high"
        assert incident.duration_minutes == 45


class TestDeploymentEvent:
    """Tests for DeploymentEvent dataclass."""

    def test_successful_deployment(self):
        """Test successful deployment event."""
        event = DeploymentEvent(
            deployment_id="DEP-001",
            service="api",
            success=True,
            duration_minutes=10,
            rollback=False,
            deployed_at=datetime.now(timezone.utc),
        )
        assert event.success is True
        assert event.rollback is False

    def test_failed_deployment(self):
        """Test failed deployment event."""
        event = DeploymentEvent(
            deployment_id="DEP-002",
            service="api",
            success=False,
            duration_minutes=5,
            rollback=True,
            deployed_at=datetime.now(timezone.utc),
        )
        assert event.success is False
        assert event.rollback is True


class TestRecommendationSummary:
    """Tests for RecommendationSummary dataclass."""

    def test_summary_creation(self):
        """Test recommendation summary creation."""
        summary = RecommendationSummary(
            total_count=10,
            by_category={"observability": 3, "infrastructure": 4, "security": 3},
            by_priority={"critical": 2, "high": 5, "medium": 3},
            estimated_total_impact="High impact",
        )
        assert summary.total_count == 10
        assert sum(summary.by_category.values()) == 10


class TestProactiveRecommendationEngine:
    """Tests for ProactiveRecommendationEngine class."""

    def test_init_without_collectors(self):
        """Test initialization without collectors."""
        engine = ProactiveRecommendationEngine()
        assert engine.metrics is None
        assert engine.resources is None
        assert engine._recommendations == []

    def test_init_with_collectors(self):
        """Test initialization with collectors."""
        mock_metrics = MagicMock()
        mock_resources = MagicMock()

        engine = ProactiveRecommendationEngine(
            metrics_collector=mock_metrics,
            resource_discovery=mock_resources,
        )

        assert engine.metrics == mock_metrics
        assert engine.resources == mock_resources


class TestAnalyzeObservability:
    """Tests for observability analysis."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = ProactiveRecommendationEngine()

    @pytest.mark.asyncio
    async def test_analyze_low_log_retention(self):
        """Test recommendations for low log retention."""
        config = ObservabilityConfig(log_retention_days=7)
        recs = await self.engine.analyze_observability(config)

        assert any("log retention" in r.title.lower() for r in recs)

    @pytest.mark.asyncio
    async def test_analyze_tracing_disabled(self):
        """Test recommendations when tracing is disabled."""
        config = ObservabilityConfig(tracing_enabled=False)
        recs = await self.engine.analyze_observability(config)

        assert any("tracing" in r.title.lower() for r in recs)

    @pytest.mark.asyncio
    async def test_analyze_low_alarm_count(self):
        """Test recommendations for low alarm count."""
        config = ObservabilityConfig(alarm_count=2)
        recs = await self.engine.analyze_observability(config)

        assert any("alerting" in r.title.lower() for r in recs)

    @pytest.mark.asyncio
    async def test_analyze_low_dashboard_count(self):
        """Test recommendations for low dashboard count."""
        config = ObservabilityConfig(dashboards_count=1)
        recs = await self.engine.analyze_observability(config)

        assert any("dashboard" in r.title.lower() for r in recs)

    @pytest.mark.asyncio
    async def test_analyze_well_configured(self):
        """Test no recommendations for well-configured observability."""
        config = ObservabilityConfig(
            log_retention_days=90,
            tracing_enabled=True,
            alerting_enabled=True,
            alarm_count=20,
            dashboards_count=10,
        )
        recs = await self.engine.analyze_observability(config)

        assert len(recs) == 0


class TestAnalyzeInfrastructure:
    """Tests for infrastructure analysis."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = ProactiveRecommendationEngine()

    @pytest.mark.asyncio
    async def test_analyze_underutilized_resources(self):
        """Test recommendations for underutilized resources."""
        graph = ResourceGraph(
            nodes=[
                {"id": "ec2-1", "cpu_utilization": 5},
                {"id": "ec2-2", "cpu_utilization": 10},
            ]
        )
        recs = await self.engine.analyze_infrastructure(graph)

        assert any("underutilized" in r.title.lower() for r in recs)

    @pytest.mark.asyncio
    async def test_analyze_single_points_of_failure(self):
        """Test recommendations for single points of failure."""
        graph = ResourceGraph(
            nodes=[
                {"id": "db-1", "incoming_edges": 10, "has_redundancy": False},
            ]
        )
        recs = await self.engine.analyze_infrastructure(graph)

        assert any("single point" in r.title.lower() for r in recs)

    @pytest.mark.asyncio
    async def test_analyze_increasing_costs(self):
        """Test recommendations for increasing costs."""
        graph = ResourceGraph()
        cost_data = CostData(monthly_total=10000.0, trend="increasing")
        recs = await self.engine.analyze_infrastructure(graph, cost_data)

        assert any("cost" in r.title.lower() for r in recs)


class TestAnalyzeDeploymentPipeline:
    """Tests for deployment pipeline analysis."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = ProactiveRecommendationEngine()

    @pytest.mark.asyncio
    async def test_analyze_no_security_scan(self):
        """Test recommendations for missing security scan."""
        config = PipelineConfig(has_security_scan=False)
        recs = await self.engine.analyze_deployment_pipeline(config, [])

        assert any("security" in r.title.lower() for r in recs)

    @pytest.mark.asyncio
    async def test_analyze_no_tests(self):
        """Test recommendations for missing tests."""
        config = PipelineConfig(has_tests=False)
        recs = await self.engine.analyze_deployment_pipeline(config, [])

        assert any("test" in r.title.lower() for r in recs)

    @pytest.mark.asyncio
    async def test_analyze_no_approval_gate(self):
        """Test recommendations for missing approval gate."""
        config = PipelineConfig(has_approval_gate=False)
        recs = await self.engine.analyze_deployment_pipeline(config, [])

        assert any("approval" in r.title.lower() for r in recs)

    @pytest.mark.asyncio
    async def test_analyze_high_failure_rate(self):
        """Test recommendations for high failure rate."""
        config = PipelineConfig(
            has_tests=True,
            has_security_scan=True,
            has_approval_gate=True,
        )
        deployments = [
            DeploymentEvent(
                deployment_id=f"dep-{i}",
                service="api",
                success=i % 5 != 0,  # 20% failure rate
                duration_minutes=10,
                rollback=False,
                deployed_at=datetime.now(timezone.utc),
            )
            for i in range(10)
        ]
        recs = await self.engine.analyze_deployment_pipeline(config, deployments)

        assert any("failure rate" in r.title.lower() for r in recs)

    @pytest.mark.asyncio
    async def test_analyze_high_mttr(self):
        """Test recommendations for high MTTR."""
        config = PipelineConfig(
            has_tests=True,
            has_security_scan=True,
            has_approval_gate=True,
            mean_time_to_recovery_minutes=120.0,
        )
        recs = await self.engine.analyze_deployment_pipeline(config, [])

        assert any("recovery" in r.title.lower() for r in recs)


class TestAnalyzeResilience:
    """Tests for resilience analysis."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = ProactiveRecommendationEngine()

    @pytest.mark.asyncio
    async def test_analyze_no_circuit_breakers(self):
        """Test recommendations for missing circuit breakers."""
        arch = ArchitectureSpec(has_circuit_breakers=False)
        recs = await self.engine.analyze_resilience(arch, [])

        assert any("circuit breaker" in r.title.lower() for r in recs)

    @pytest.mark.asyncio
    async def test_analyze_no_rate_limiting(self):
        """Test recommendations for missing rate limiting."""
        arch = ArchitectureSpec(has_rate_limiting=False)
        recs = await self.engine.analyze_resilience(arch, [])

        assert any("rate limit" in r.title.lower() for r in recs)

    @pytest.mark.asyncio
    async def test_analyze_no_health_checks(self):
        """Test recommendations for missing health checks."""
        arch = ArchitectureSpec(has_health_checks=False)
        recs = await self.engine.analyze_resilience(arch, [])

        assert any("health check" in r.title.lower() for r in recs)

    @pytest.mark.asyncio
    async def test_analyze_recurring_incidents(self):
        """Test recommendations for recurring incidents."""
        arch = ArchitectureSpec(
            has_circuit_breakers=True,
            has_rate_limiting=True,
            has_health_checks=True,
        )
        incidents = [
            IncidentRecord(
                incident_id=f"inc-{i}",
                severity="high",
                service="api",
                duration_minutes=30,
                root_cause="Unknown",
                occurred_at=datetime.now(timezone.utc) - timedelta(days=i),
            )
            for i in range(5)
        ]
        recs = await self.engine.analyze_resilience(arch, incidents)

        assert any("recurring" in r.title.lower() for r in recs)


class TestRecommendationRetrieval:
    """Tests for recommendation retrieval methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = ProactiveRecommendationEngine()

    @pytest.mark.asyncio
    async def test_get_all_recommendations(self):
        """Test getting all recommendations."""
        config = ObservabilityConfig(log_retention_days=7, tracing_enabled=False)
        await self.engine.analyze_observability(config)

        all_recs = await self.engine.get_all_recommendations()
        assert len(all_recs) >= 2

    @pytest.mark.asyncio
    async def test_get_recommendations_by_category(self):
        """Test filtering by category."""
        config = ObservabilityConfig(log_retention_days=7)
        await self.engine.analyze_observability(config)

        obs_recs = await self.engine.get_all_recommendations(
            category=RecommendationCategory.OBSERVABILITY
        )
        assert all(r.category == RecommendationCategory.OBSERVABILITY for r in obs_recs)

    @pytest.mark.asyncio
    async def test_get_recommendations_by_priority(self):
        """Test filtering by priority."""
        config = ObservabilityConfig(tracing_enabled=False)
        await self.engine.analyze_observability(config)

        high_recs = await self.engine.get_all_recommendations(
            priority=RecommendationPriority.HIGH
        )
        assert all(r.priority == RecommendationPriority.HIGH for r in high_recs)

    def test_get_recommendation_summary(self):
        """Test getting recommendation summary."""
        summary = self.engine.get_recommendation_summary()

        assert summary.total_count >= 0
        assert isinstance(summary.by_category, dict)
        assert isinstance(summary.by_priority, dict)

    def test_get_service_stats(self):
        """Test getting service stats."""
        stats = self.engine.get_service_stats()

        assert "total_recommendations" in stats
        assert "by_category" in stats
