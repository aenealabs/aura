"""
Tests for market_intelligence_agent.py

Comprehensive tests for the MarketIntelligenceAgent which monitors
competitor announcements, technology trends, and external documentation.

Part of ADR-019: Market Intelligence Agent for Autonomous Competitive Research
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.agents.market_intelligence_agent import (
    CapabilityGapAlert,
    CompetitorInfo,
    CompetitorWatchAgent,
    DataSource,
    DocumentationAggregatorAgent,
    GapSeverity,
    GapStatus,
    IntelligenceReport,
    IntelligenceType,
    MarketIntelligenceAgent,
    MarketIntelligenceConfig,
    TrendAnalysisAgent,
    create_market_intelligence_agent,
)
from src.agents.meta_orchestrator import AgentCapability

# =============================================================================
# Test IntelligenceType Enum
# =============================================================================


class TestIntelligenceType:
    """Tests for IntelligenceType enum."""

    def test_type_values(self):
        """Test intelligence type enum values."""
        assert IntelligenceType.COMPETITOR.value == "competitor"
        assert IntelligenceType.TREND.value == "trend"
        assert IntelligenceType.CAPABILITY_GAP.value == "capability_gap"
        assert IntelligenceType.STANDARD.value == "standard"
        assert IntelligenceType.DOCUMENTATION.value == "documentation"


# =============================================================================
# Test GapSeverity Enum
# =============================================================================


class TestGapSeverity:
    """Tests for GapSeverity enum."""

    def test_severity_values(self):
        """Test gap severity enum values."""
        assert GapSeverity.CRITICAL.value == "critical"
        assert GapSeverity.HIGH.value == "high"
        assert GapSeverity.MEDIUM.value == "medium"
        assert GapSeverity.LOW.value == "low"


# =============================================================================
# Test GapStatus Enum
# =============================================================================


class TestGapStatus:
    """Tests for GapStatus enum."""

    def test_status_values(self):
        """Test gap status enum values."""
        assert GapStatus.MISSING.value == "missing"
        assert GapStatus.PARTIAL.value == "partial"
        assert GapStatus.EQUIVALENT.value == "equivalent"
        assert GapStatus.SUPERIOR.value == "superior"


# =============================================================================
# Test DataSource Enum
# =============================================================================


class TestDataSource:
    """Tests for DataSource enum."""

    def test_source_values(self):
        """Test data source enum values."""
        assert DataSource.AWS_BLOG.value == "aws_blog"
        assert DataSource.GITHUB_TRENDING.value == "github_trending"
        assert DataSource.NIST.value == "nist"
        assert DataSource.OWASP.value == "owasp"


# =============================================================================
# Test IntelligenceReport Dataclass
# =============================================================================


class TestIntelligenceReport:
    """Tests for IntelligenceReport dataclass."""

    def test_report_creation_minimal(self):
        """Test creating report with minimal fields."""
        report = IntelligenceReport(
            report_id="report-001",
            report_type=IntelligenceType.COMPETITOR,
            source=DataSource.AWS_BLOG,
            title="AWS Announces New Security Feature",
            summary="New autonomous security capabilities",
            relevance_score=0.8,
        )

        assert report.report_id == "report-001"
        assert report.report_type == IntelligenceType.COMPETITOR
        assert report.source == DataSource.AWS_BLOG
        assert report.title == "AWS Announces New Security Feature"
        assert report.relevance_score == 0.8
        assert report.capability_impact == []
        assert report.recommendations == []
        assert report.raw_content is None
        assert report.source_url == ""
        assert report.tags == []
        assert report.metadata == {}

    def test_report_creation_full(self):
        """Test creating report with all fields."""
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=30)

        report = IntelligenceReport(
            report_id="report-002",
            report_type=IntelligenceType.CAPABILITY_GAP,
            source=DataSource.AWS_BLOG,
            title="Full Report",
            summary="Comprehensive analysis",
            relevance_score=0.95,
            capability_impact=[AgentCapability.SECURITY_REVIEW],
            recommendations=["Implement feature X", "Update documentation"],
            raw_content="Full content here",
            source_url="https://example.com/report",
            discovered_at=now,
            expires_at=expires,
            tags=["aws", "security", "critical"],
            metadata={"competitor": "AWS", "version": "2.0"},
        )

        assert report.report_id == "report-002"
        assert report.relevance_score == 0.95
        assert len(report.capability_impact) == 1
        assert len(report.recommendations) == 2
        assert report.raw_content == "Full content here"
        assert "critical" in report.tags
        assert report.metadata["competitor"] == "AWS"

    def test_report_to_dict(self):
        """Test report serialization."""
        report = IntelligenceReport(
            report_id="report-003",
            report_type=IntelligenceType.TREND,
            source=DataSource.GITHUB_TRENDING,
            title="AI Agents Trending",
            summary="Multiple AI frameworks gaining traction",
            relevance_score=0.75,
            capability_impact=[AgentCapability.MARKET_INTELLIGENCE],
            tags=["trending", "ai"],
        )

        data = report.to_dict()

        assert data["report_id"] == "report-003"
        assert data["report_type"] == "trend"
        assert data["source"] == "github_trending"
        assert data["relevance_score"] == 0.75
        assert "market_intelligence" in data["capability_impact"]
        assert "trending" in data["tags"]

    def test_report_from_dict(self):
        """Test report deserialization."""
        data = {
            "report_id": "report-004",
            "report_type": "standard",
            "source": "nist",
            "title": "NIST Update",
            "summary": "New security guidelines",
            "relevance_score": 0.9,
            "capability_impact": ["compliance_check"],
            "recommendations": ["Review guidelines"],
            "source_url": "https://nist.gov/update",
            "discovered_at": "2025-12-16T10:00:00",
            "expires_at": None,
            "tags": ["nist", "compliance"],
            "metadata": {},
        }

        report = IntelligenceReport.from_dict(data)

        assert report.report_id == "report-004"
        assert report.report_type == IntelligenceType.STANDARD
        assert report.source == DataSource.NIST
        assert report.relevance_score == 0.9
        assert AgentCapability.COMPLIANCE_CHECK in report.capability_impact


# =============================================================================
# Test CapabilityGapAlert Dataclass
# =============================================================================


class TestCapabilityGapAlert:
    """Tests for CapabilityGapAlert dataclass."""

    def test_alert_creation(self):
        """Test creating capability gap alert."""
        alert = CapabilityGapAlert(
            alert_id="gap-001",
            competitor="AWS",
            capability="Auto PR Creation",
            our_status=GapStatus.MISSING,
            gap_severity=GapSeverity.HIGH,
            description="AWS can auto-create PRs for remediation",
            recommended_action="Implement GitHub PR integration",
            related_reports=["report-001", "report-002"],
        )

        assert alert.alert_id == "gap-001"
        assert alert.competitor == "AWS"
        assert alert.our_status == GapStatus.MISSING
        assert alert.gap_severity == GapSeverity.HIGH
        assert len(alert.related_reports) == 2
        assert alert.acknowledged is False
        assert alert.acknowledged_by is None

    def test_alert_to_dict(self):
        """Test alert serialization."""
        alert = CapabilityGapAlert(
            alert_id="gap-002",
            competitor="Azure",
            capability="Design Review",
            our_status=GapStatus.PARTIAL,
            gap_severity=GapSeverity.MEDIUM,
            description="Azure has full design review",
            recommended_action="Enhance design review capability",
        )

        data = alert.to_dict()

        assert data["alert_id"] == "gap-002"
        assert data["competitor"] == "Azure"
        assert data["our_status"] == "partial"
        assert data["gap_severity"] == "medium"
        assert data["acknowledged"] is False


# =============================================================================
# Test MarketIntelligenceConfig
# =============================================================================


class TestMarketIntelligenceConfig:
    """Tests for MarketIntelligenceConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = MarketIntelligenceConfig()

        assert config.check_interval_minutes == 60
        assert config.max_report_age_days == 30
        assert config.relevance_threshold == 0.5
        assert config.enable_competitor_watch is True
        assert config.enable_trend_analysis is True
        assert config.enable_doc_aggregation is True
        assert len(config.competitors) == 3  # AWS, Azure, GCP

    def test_custom_config(self):
        """Test custom configuration."""
        config = MarketIntelligenceConfig(
            check_interval_minutes=30,
            max_report_age_days=7,
            relevance_threshold=0.8,
            enable_trend_analysis=False,
        )

        assert config.check_interval_minutes == 30
        assert config.max_report_age_days == 7
        assert config.relevance_threshold == 0.8
        assert config.enable_trend_analysis is False


# =============================================================================
# Test CompetitorWatchAgent
# =============================================================================


class TestCompetitorWatchAgent:
    """Tests for CompetitorWatchAgent."""

    def test_agent_creation(self):
        """Test agent initialization."""
        agent = CompetitorWatchAgent()

        assert agent.capability == AgentCapability.COMPETITOR_WATCH
        assert agent.config is not None
        assert agent.can_spawn is False

    def test_agent_with_config(self):
        """Test agent with custom config."""
        config = MarketIntelligenceConfig(
            competitors=[
                CompetitorInfo(
                    name="CustomCompetitor",
                    feed_urls=["https://example.com/feed"],
                    keywords=["security", "ai"],
                )
            ]
        )

        agent = CompetitorWatchAgent(config=config)

        assert len(agent.config.competitors) == 1
        assert agent.config.competitors[0].name == "CustomCompetitor"

    @pytest.mark.asyncio
    async def test_execute_returns_result(self):
        """Test that execute returns proper result."""
        agent = CompetitorWatchAgent()

        result = await agent.execute("Scan competitors for AI announcements")

        assert result.success is True
        assert result.capability == AgentCapability.COMPETITOR_WATCH
        assert "reports" in result.output
        assert "report_count" in result.output
        assert result.execution_time_seconds >= 0


# =============================================================================
# Test TrendAnalysisAgent
# =============================================================================


class TestTrendAnalysisAgent:
    """Tests for TrendAnalysisAgent."""

    def test_agent_creation(self):
        """Test agent initialization."""
        agent = TrendAnalysisAgent()

        assert agent.capability == AgentCapability.TREND_ANALYSIS
        assert agent.config is not None
        assert agent.can_spawn is False

    @pytest.mark.asyncio
    async def test_execute_returns_result(self):
        """Test that execute returns proper result."""
        agent = TrendAnalysisAgent()

        result = await agent.execute("Analyze GitHub trending")

        assert result.success is True
        assert result.capability == AgentCapability.TREND_ANALYSIS
        assert "reports" in result.output
        assert result.execution_time_seconds >= 0


# =============================================================================
# Test DocumentationAggregatorAgent
# =============================================================================


class TestDocumentationAggregatorAgent:
    """Tests for DocumentationAggregatorAgent."""

    def test_agent_creation(self):
        """Test agent initialization."""
        agent = DocumentationAggregatorAgent()

        assert agent.capability == AgentCapability.DOCUMENTATION_AGGREGATION
        assert agent.config is not None
        assert agent.can_spawn is False

    @pytest.mark.asyncio
    async def test_execute_returns_result(self):
        """Test that execute returns proper result."""
        agent = DocumentationAggregatorAgent()

        result = await agent.execute("Check NIST updates")

        assert result.success is True
        assert result.capability == AgentCapability.DOCUMENTATION_AGGREGATION
        assert "reports" in result.output
        assert result.execution_time_seconds >= 0


# =============================================================================
# Test MarketIntelligenceAgent
# =============================================================================


class TestMarketIntelligenceAgent:
    """Tests for MarketIntelligenceAgent."""

    def test_agent_creation(self):
        """Test agent initialization."""
        agent = MarketIntelligenceAgent()

        assert agent.capability == AgentCapability.MARKET_INTELLIGENCE
        assert agent.config is not None
        assert agent.can_spawn is True
        assert agent._competitor_agent is not None
        assert agent._trend_agent is not None
        assert agent._doc_agent is not None

    def test_agent_with_config(self):
        """Test agent with custom config."""
        config = MarketIntelligenceConfig(
            enable_trend_analysis=False,
            check_interval_minutes=30,
        )

        agent = MarketIntelligenceAgent(config=config)

        assert agent.config.enable_trend_analysis is False
        assert agent.config.check_interval_minutes == 30

    @pytest.mark.asyncio
    async def test_execute_full_scan(self):
        """Test full market intelligence scan."""
        agent = MarketIntelligenceAgent()

        result = await agent.execute("Full market intelligence scan")

        assert result.success is True
        assert result.capability == AgentCapability.MARKET_INTELLIGENCE
        assert "summary" in result.output
        assert "reports" in result.output
        assert "report_count" in result.output
        assert "new_gaps" in result.output
        assert "knowledge_base_size" in result.output
        assert result.execution_time_seconds >= 0

    @pytest.mark.asyncio
    async def test_execute_competitor_only(self):
        """Test competitor-only scan."""
        config = MarketIntelligenceConfig(
            enable_trend_analysis=False,
            enable_doc_aggregation=False,
        )
        agent = MarketIntelligenceAgent(config=config)

        result = await agent.execute("Scan AWS competitors")

        assert result.success is True
        # Should still work but only with competitor data

    def test_parse_task_scope(self):
        """Test task scope parsing."""
        agent = MarketIntelligenceAgent()

        # Full scan
        scope = agent._parse_task_scope("Run a full market scan")
        assert scope["competitor_watch"] is True
        assert scope["trend_analysis"] is True
        assert scope["doc_aggregation"] is True

        # Competitor only
        scope = agent._parse_task_scope("Check AWS announcements")
        assert scope["competitor_watch"] is True

        # Trend only
        scope = agent._parse_task_scope("Analyze GitHub trends")
        assert scope["trend_analysis"] is True

        # Documentation only
        scope = agent._parse_task_scope("Check NIST standards")
        assert scope["doc_aggregation"] is True

    def test_knowledge_base_operations(self):
        """Test knowledge base get/query operations."""
        agent = MarketIntelligenceAgent()

        # Initially empty
        assert len(agent.get_knowledge_base()) == 0
        assert len(agent.get_capability_gaps()) == 0

        # Query with filters (empty results)
        results = agent.query_knowledge_base(
            report_type=IntelligenceType.COMPETITOR,
            min_relevance=0.5,
            limit=5,
        )
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_prune_expired_reports(self):
        """Test expired report pruning."""
        agent = MarketIntelligenceAgent()

        # Add an expired report directly
        expired_report = IntelligenceReport(
            report_id="expired-001",
            report_type=IntelligenceType.TREND,
            source=DataSource.GITHUB_TRENDING,
            title="Old Report",
            summary="This is old",
            relevance_score=0.5,
            discovered_at=datetime.now(timezone.utc) - timedelta(days=60),
        )
        agent._knowledge_base.append(expired_report)

        # Add a fresh report
        fresh_report = IntelligenceReport(
            report_id="fresh-001",
            report_type=IntelligenceType.COMPETITOR,
            source=DataSource.AWS_BLOG,
            title="Fresh Report",
            summary="This is new",
            relevance_score=0.8,
            discovered_at=datetime.now(timezone.utc),
        )
        agent._knowledge_base.append(fresh_report)

        assert len(agent._knowledge_base) == 2

        # Prune
        agent._prune_expired_reports()

        # Only fresh report should remain
        assert len(agent._knowledge_base) == 1
        assert agent._knowledge_base[0].report_id == "fresh-001"

    def test_autonomy_preset(self):
        """Test autonomy preset configuration."""
        preset = MarketIntelligenceAgent.AUTONOMY_PRESET

        assert "default_level" in preset
        assert "allowed_actions" in preset
        assert "blocked_actions" in preset
        assert "web_fetch" in preset["allowed_actions"]
        assert "code_modification" in preset["blocked_actions"]


# =============================================================================
# Test Factory Function
# =============================================================================


class TestFactoryFunction:
    """Tests for factory function."""

    def test_create_agent_default(self):
        """Test creating agent with defaults."""
        agent = create_market_intelligence_agent()

        assert isinstance(agent, MarketIntelligenceAgent)
        assert agent.config is not None

    def test_create_agent_with_config(self):
        """Test creating agent with custom config."""
        config = MarketIntelligenceConfig(check_interval_minutes=15)

        agent = create_market_intelligence_agent(config=config)

        assert agent.config.check_interval_minutes == 15

    def test_create_agent_with_monitor(self):
        """Test creating agent with monitor."""
        mock_monitor = MagicMock()

        agent = create_market_intelligence_agent(monitor=mock_monitor)

        assert agent.monitor is mock_monitor


# =============================================================================
# Test AgentCapability Integration
# =============================================================================


class TestAgentCapabilityIntegration:
    """Tests for AgentCapability enum integration."""

    def test_market_intelligence_capability_exists(self):
        """Test that MARKET_INTELLIGENCE capability exists."""
        assert hasattr(AgentCapability, "MARKET_INTELLIGENCE")
        assert AgentCapability.MARKET_INTELLIGENCE.value == "market_intelligence"

    def test_competitor_watch_capability_exists(self):
        """Test that COMPETITOR_WATCH capability exists."""
        assert hasattr(AgentCapability, "COMPETITOR_WATCH")
        assert AgentCapability.COMPETITOR_WATCH.value == "competitor_watch"

    def test_trend_analysis_capability_exists(self):
        """Test that TREND_ANALYSIS capability exists."""
        assert hasattr(AgentCapability, "TREND_ANALYSIS")
        assert AgentCapability.TREND_ANALYSIS.value == "trend_analysis"

    def test_documentation_aggregation_capability_exists(self):
        """Test that DOCUMENTATION_AGGREGATION capability exists."""
        assert hasattr(AgentCapability, "DOCUMENTATION_AGGREGATION")
        assert (
            AgentCapability.DOCUMENTATION_AGGREGATION.value
            == "documentation_aggregation"
        )
