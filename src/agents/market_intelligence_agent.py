"""Market Intelligence Agent for Autonomous Competitive Research.

This agent operates autonomously to gather, analyze, and disseminate
competitive intelligence throughout the agent system.

Part of ADR-019: Market Intelligence Agent for Autonomous Competitive Research

Capabilities:
- Competitor monitoring (AWS, Azure, GCP, startups)
- Technology trend analysis
- External documentation aggregation
- Capability gap identification
- Knowledge base maintenance
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

from .meta_orchestrator import (
    AgentCapability,
    AgentResult,
    AutonomyLevel,
    SpawnableAgent,
)
from .monitoring_service import MonitorAgent

if TYPE_CHECKING:
    from src.services.bedrock_llm_service import BedrockLLMService

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================


class IntelligenceType(Enum):
    """Types of market intelligence reports."""

    COMPETITOR = "competitor"  # Competitor announcements and features
    TREND = "trend"  # Technology trends and patterns
    CAPABILITY_GAP = "capability_gap"  # Identified capability gaps
    STANDARD = "standard"  # Industry standards and compliance
    DOCUMENTATION = "documentation"  # External documentation updates


class GapSeverity(Enum):
    """Severity levels for capability gaps."""

    CRITICAL = "critical"  # Immediate action required
    HIGH = "high"  # High priority remediation
    MEDIUM = "medium"  # Moderate priority
    LOW = "low"  # Low priority, nice to have


class GapStatus(Enum):
    """Status of capability compared to competitor."""

    MISSING = "missing"  # We don't have this capability
    PARTIAL = "partial"  # We have limited implementation
    EQUIVALENT = "equivalent"  # We match competitor capability
    SUPERIOR = "superior"  # We exceed competitor capability


class DataSource(Enum):
    """Data sources for market intelligence."""

    AWS_BLOG = "aws_blog"
    AZURE_UPDATES = "azure_updates"
    GCP_RELEASES = "gcp_releases"
    GITHUB_TRENDING = "github_trending"
    HACKER_NEWS = "hacker_news"
    REDDIT_DEVOPS = "reddit_devops"
    NIST = "nist"
    OWASP = "owasp"
    CIS_BENCHMARKS = "cis_benchmarks"
    VENDOR_DOCS = "vendor_docs"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class IntelligenceReport:
    """Market intelligence finding."""

    report_id: str
    report_type: IntelligenceType
    source: DataSource
    title: str
    summary: str
    relevance_score: float  # 0.0 - 1.0
    capability_impact: list[AgentCapability] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    raw_content: str | None = None
    source_url: str = ""
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None  # TTL for time-sensitive intel
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary for serialization."""
        return {
            "report_id": self.report_id,
            "report_type": self.report_type.value,
            "source": self.source.value,
            "title": self.title,
            "summary": self.summary,
            "relevance_score": self.relevance_score,
            "capability_impact": [c.value for c in self.capability_impact],
            "recommendations": self.recommendations,
            "source_url": self.source_url,
            "discovered_at": self.discovered_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IntelligenceReport":
        """Create report from dictionary."""
        return cls(
            report_id=data["report_id"],
            report_type=IntelligenceType(data["report_type"]),
            source=DataSource(data["source"]),
            title=data["title"],
            summary=data["summary"],
            relevance_score=data["relevance_score"],
            capability_impact=[
                AgentCapability(c) for c in data.get("capability_impact", [])
            ],
            recommendations=data.get("recommendations", []),
            raw_content=data.get("raw_content"),
            source_url=data.get("source_url", ""),
            discovered_at=datetime.fromisoformat(data["discovered_at"]),
            expires_at=(
                datetime.fromisoformat(data["expires_at"])
                if data.get("expires_at")
                else None
            ),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class CapabilityGapAlert:
    """Alert when competitor capability exceeds ours."""

    alert_id: str
    competitor: str
    capability: str
    our_status: GapStatus
    gap_severity: GapSeverity
    description: str
    recommended_action: str
    related_reports: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = False
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert alert to dictionary for serialization."""
        return {
            "alert_id": self.alert_id,
            "competitor": self.competitor,
            "capability": self.capability,
            "our_status": self.our_status.value,
            "gap_severity": self.gap_severity.value,
            "description": self.description,
            "recommended_action": self.recommended_action,
            "related_reports": self.related_reports,
            "created_at": self.created_at.isoformat(),
            "acknowledged": self.acknowledged,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": (
                self.acknowledged_at.isoformat() if self.acknowledged_at else None
            ),
        }


@dataclass
class CompetitorInfo:
    """Information about a competitor."""

    name: str
    feed_urls: list[str]
    keywords: list[str]
    last_checked: datetime | None = None


@dataclass
class MarketIntelligenceConfig:
    """Configuration for market intelligence gathering."""

    check_interval_minutes: int = 60
    max_report_age_days: int = 30
    relevance_threshold: float = 0.5
    max_reports_per_source: int = 50
    enable_competitor_watch: bool = True
    enable_trend_analysis: bool = True
    enable_doc_aggregation: bool = True

    # Competitor sources
    competitors: list[CompetitorInfo] = field(
        default_factory=lambda: [
            CompetitorInfo(
                name="AWS",
                feed_urls=[
                    "https://aws.amazon.com/blogs/security/feed/",
                    "https://aws.amazon.com/blogs/aws/feed/",
                ],
                keywords=["security agent", "bedrock", "guardrails", "autonomous"],
            ),
            CompetitorInfo(
                name="Azure",
                feed_urls=["https://azure.microsoft.com/en-us/blog/feed/"],
                keywords=["copilot", "security", "ai agent", "defender"],
            ),
            CompetitorInfo(
                name="GCP",
                feed_urls=["https://cloud.google.com/feeds/gcp-release-notes.xml"],
                keywords=["gemini", "security", "vertex ai", "agent"],
            ),
        ]
    )


# =============================================================================
# Sub-Agents
# =============================================================================


class CompetitorWatchAgent(SpawnableAgent):
    """Agent for monitoring competitor announcements and features.

    Sources:
    - AWS Blog, Azure Updates, GCP Release Notes
    - Vendor security bulletins
    - Analyst reports (when accessible)

    Output: Competitor announcements, feature comparisons
    Frequency: Daily scan, immediate alerts for major announcements
    """

    def __init__(
        self,
        llm_client: Any = None,
        agent_id: str | None = None,
        config: MarketIntelligenceConfig | None = None,
        monitor: MonitorAgent | None = None,
    ):
        super().__init__(llm_client, agent_id, max_spawn_depth=0, can_spawn=False)
        self.config = config or MarketIntelligenceConfig()
        self.monitor = monitor
        self._known_items: set[str] = set()

    @property
    def capability(self) -> AgentCapability:
        return AgentCapability.COMPETITOR_WATCH

    async def execute(self, task: str, context: Any = None) -> AgentResult:
        """Execute competitor monitoring task."""
        start_time = datetime.now(timezone.utc)

        try:
            reports = await self._scan_competitors()

            return AgentResult(
                agent_id=self.agent_id,
                capability=self.capability,
                success=True,
                output={
                    "reports": [r.to_dict() for r in reports],
                    "report_count": len(reports),
                    "competitors_scanned": len(self.config.competitors),
                },
                execution_time_seconds=(
                    datetime.now(timezone.utc) - start_time
                ).total_seconds(),
            )
        except Exception as e:
            logger.error(f"CompetitorWatchAgent failed: {e}")
            return AgentResult(
                agent_id=self.agent_id,
                capability=self.capability,
                success=False,
                output=None,
                execution_time_seconds=(
                    datetime.now(timezone.utc) - start_time
                ).total_seconds(),
                error=str(e),
            )

    async def _scan_competitors(self) -> list[IntelligenceReport]:
        """Scan all competitor sources for new intelligence."""
        reports = []

        for competitor in self.config.competitors:
            try:
                competitor_reports = await self._scan_competitor(competitor)
                reports.extend(competitor_reports)
            except Exception as e:
                logger.warning(f"Failed to scan {competitor.name}: {e}")

        return reports

    async def _scan_competitor(
        self, competitor: CompetitorInfo
    ) -> list[IntelligenceReport]:
        """Scan a single competitor's feeds."""
        reports = []

        for feed_url in competitor.feed_urls:
            try:
                items = await self._fetch_feed(feed_url)
                for item in items:
                    if self._is_relevant(item, competitor.keywords):
                        report = self._create_report(item, competitor)
                        if report.report_id not in self._known_items:
                            reports.append(report)
                            self._known_items.add(report.report_id)
            except Exception as e:
                logger.warning(f"Failed to fetch {feed_url}: {e}")

        competitor.last_checked = datetime.now(timezone.utc)
        return reports

    async def _fetch_feed(self, feed_url: str) -> list[dict[str, Any]]:
        """Fetch and parse RSS/Atom feed."""
        # Mock implementation - in production would use feedparser or similar
        # This simulates finding relevant items
        return [
            {
                "id": hashlib.md5(
                    f"{feed_url}-sample".encode(), usedforsecurity=False
                ).hexdigest()[:16],
                "title": "Sample Competitor Announcement",
                "summary": "New AI security features announced",
                "link": feed_url,
                "published": datetime.now(timezone.utc).isoformat(),
            }
        ]

    def _is_relevant(self, item: dict[str, Any], keywords: list[str]) -> bool:
        """Check if item is relevant based on keywords."""
        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        return any(kw.lower() in text for kw in keywords)

    def _create_report(
        self, item: dict[str, Any], competitor: CompetitorInfo
    ) -> IntelligenceReport:
        """Create intelligence report from feed item."""
        return IntelligenceReport(
            report_id=f"comp-{item['id']}",
            report_type=IntelligenceType.COMPETITOR,
            source=DataSource.AWS_BLOG,  # Would be dynamic based on competitor
            title=item.get("title", "Unknown"),
            summary=item.get("summary", ""),
            relevance_score=0.7,  # Would be calculated by LLM
            source_url=item.get("link", ""),
            tags=[competitor.name.lower(), "competitor"],
            metadata={"competitor": competitor.name},
        )


class TrendAnalysisAgent(SpawnableAgent):
    """Agent for analyzing technology trends and patterns.

    Sources:
    - GitHub Trending repositories
    - HackerNews top stories
    - Reddit r/devops, r/aws, r/security

    Output: Emerging technologies, adoption patterns, security trends
    Frequency: Daily aggregation, weekly trend reports
    """

    def __init__(
        self,
        llm_client: Any = None,
        agent_id: str | None = None,
        config: MarketIntelligenceConfig | None = None,
        monitor: MonitorAgent | None = None,
    ):
        super().__init__(llm_client, agent_id, max_spawn_depth=0, can_spawn=False)
        self.config = config or MarketIntelligenceConfig()
        self.monitor = monitor
        self._trend_history: list[dict[str, Any]] = []

    @property
    def capability(self) -> AgentCapability:
        return AgentCapability.TREND_ANALYSIS

    async def execute(self, task: str, context: Any = None) -> AgentResult:
        """Execute trend analysis task."""
        start_time = datetime.now(timezone.utc)

        try:
            reports = await self._analyze_trends()

            return AgentResult(
                agent_id=self.agent_id,
                capability=self.capability,
                success=True,
                output={
                    "reports": [r.to_dict() for r in reports],
                    "report_count": len(reports),
                    "sources_analyzed": 3,
                },
                execution_time_seconds=(
                    datetime.now(timezone.utc) - start_time
                ).total_seconds(),
            )
        except Exception as e:
            logger.error(f"TrendAnalysisAgent failed: {e}")
            return AgentResult(
                agent_id=self.agent_id,
                capability=self.capability,
                success=False,
                output=None,
                execution_time_seconds=(
                    datetime.now(timezone.utc) - start_time
                ).total_seconds(),
                error=str(e),
            )

    async def _analyze_trends(self) -> list[IntelligenceReport]:
        """Analyze trends from multiple sources."""
        reports = []

        # GitHub trending
        github_reports = await self._analyze_github_trending()
        reports.extend(github_reports)

        # HackerNews
        hn_reports = await self._analyze_hackernews()
        reports.extend(hn_reports)

        # Reddit
        reddit_reports = await self._analyze_reddit()
        reports.extend(reddit_reports)

        return reports

    async def _analyze_github_trending(self) -> list[IntelligenceReport]:
        """Analyze GitHub trending repositories."""
        # Mock implementation
        return [
            IntelligenceReport(
                report_id=f"gh-trend-{datetime.now(timezone.utc).strftime('%Y%m%d')}",
                report_type=IntelligenceType.TREND,
                source=DataSource.GITHUB_TRENDING,
                title="AI Agent Frameworks Trending",
                summary="Multiple AI agent orchestration frameworks gaining traction",
                relevance_score=0.8,
                capability_impact=[AgentCapability.MARKET_INTELLIGENCE],
                recommendations=[
                    "Evaluate LangGraph for agent orchestration",
                    "Monitor AutoGen developments",
                ],
                tags=["ai-agents", "orchestration", "trending"],
            )
        ]

    async def _analyze_hackernews(self) -> list[IntelligenceReport]:
        """Analyze HackerNews top stories."""
        # Mock implementation
        return []

    async def _analyze_reddit(self) -> list[IntelligenceReport]:
        """Analyze relevant Reddit communities."""
        # Mock implementation
        return []


class DocumentationAggregatorAgent(SpawnableAgent):
    """Agent for aggregating external documentation and standards.

    Sources:
    - Official API documentation
    - Best practice guides
    - Standards organizations (NIST, OWASP, CIS)
    - Competitor documentation

    Output: Updated documentation references, API changes
    Frequency: Weekly sync, immediate for breaking changes
    """

    def __init__(
        self,
        llm_client: Any = None,
        agent_id: str | None = None,
        config: MarketIntelligenceConfig | None = None,
        monitor: MonitorAgent | None = None,
    ):
        super().__init__(llm_client, agent_id, max_spawn_depth=0, can_spawn=False)
        self.config = config or MarketIntelligenceConfig()
        self.monitor = monitor
        self._doc_versions: dict[str, str] = {}

    @property
    def capability(self) -> AgentCapability:
        return AgentCapability.DOCUMENTATION_AGGREGATION

    async def execute(self, task: str, context: Any = None) -> AgentResult:
        """Execute documentation aggregation task."""
        start_time = datetime.now(timezone.utc)

        try:
            reports = await self._aggregate_documentation()

            return AgentResult(
                agent_id=self.agent_id,
                capability=self.capability,
                success=True,
                output={
                    "reports": [r.to_dict() for r in reports],
                    "report_count": len(reports),
                    "sources_checked": 3,
                },
                execution_time_seconds=(
                    datetime.now(timezone.utc) - start_time
                ).total_seconds(),
            )
        except Exception as e:
            logger.error(f"DocumentationAggregatorAgent failed: {e}")
            return AgentResult(
                agent_id=self.agent_id,
                capability=self.capability,
                success=False,
                output=None,
                execution_time_seconds=(
                    datetime.now(timezone.utc) - start_time
                ).total_seconds(),
                error=str(e),
            )

    async def _aggregate_documentation(self) -> list[IntelligenceReport]:
        """Aggregate documentation from all sources."""
        reports = []

        # NIST standards
        nist_reports = await self._check_nist_updates()
        reports.extend(nist_reports)

        # OWASP updates
        owasp_reports = await self._check_owasp_updates()
        reports.extend(owasp_reports)

        # CIS Benchmarks
        cis_reports = await self._check_cis_updates()
        reports.extend(cis_reports)

        return reports

    async def _check_nist_updates(self) -> list[IntelligenceReport]:
        """Check for NIST standard updates."""
        # Mock implementation
        return [
            IntelligenceReport(
                report_id=f"nist-{datetime.now(timezone.utc).strftime('%Y%m%d')}",
                report_type=IntelligenceType.STANDARD,
                source=DataSource.NIST,
                title="NIST AI Risk Management Framework Update",
                summary="New guidance for AI system security controls",
                relevance_score=0.9,
                capability_impact=[
                    AgentCapability.COMPLIANCE_CHECK,
                    AgentCapability.SECURITY_REVIEW,
                ],
                recommendations=[
                    "Review AI RMF mapping to existing controls",
                    "Update compliance documentation",
                ],
                source_url="https://www.nist.gov/itl/ai-risk-management-framework",
                tags=["nist", "compliance", "ai-security"],
            )
        ]

    async def _check_owasp_updates(self) -> list[IntelligenceReport]:
        """Check for OWASP updates."""
        # Mock implementation
        return []

    async def _check_cis_updates(self) -> list[IntelligenceReport]:
        """Check for CIS Benchmark updates."""
        # Mock implementation
        return []


# =============================================================================
# Main Agent
# =============================================================================


class MarketIntelligenceAgent(SpawnableAgent):
    """Autonomous agent for gathering and analyzing market intelligence.

    This is the main orchestrating agent that coordinates sub-agents:
    - CompetitorWatchAgent: Monitors competitor announcements
    - TrendAnalysisAgent: Analyzes technology trends
    - DocumentationAggregatorAgent: Aggregates external documentation

    Capabilities:
    - Competitor monitoring (AWS, Azure, GCP, startups)
    - Technology trend analysis
    - External documentation aggregation
    - Capability gap identification
    - Knowledge base maintenance

    Implements ADR-019: Market Intelligence Agent
    """

    # Autonomy configuration for market research (low-risk)
    AUTONOMY_PRESET = {
        "default_level": AutonomyLevel.AUDIT_ONLY,
        "severity_overrides": {
            "capability_gap_critical": AutonomyLevel.CRITICAL_HITL,
        },
        "allowed_actions": [
            "web_fetch",
            "api_query",
            "report_generation",
            "knowledge_base_update",
            "alert_creation",
        ],
        "blocked_actions": [
            "code_modification",
            "deployment",
            "external_notification",
        ],
    }

    def __init__(
        self,
        llm_client: "BedrockLLMService | None" = None,
        agent_id: str | None = None,
        config: MarketIntelligenceConfig | None = None,
        monitor: MonitorAgent | None = None,
        max_spawn_depth: int = 2,
    ):
        """Initialize the Market Intelligence Agent.

        Args:
            llm_client: LLM service for analysis and summarization
            agent_id: Optional agent identifier
            config: Configuration for intelligence gathering
            monitor: Optional monitoring agent for metrics
            max_spawn_depth: Maximum depth for spawning sub-agents
        """
        super().__init__(llm_client, agent_id, max_spawn_depth, can_spawn=True)
        self.config = config or MarketIntelligenceConfig()
        self.monitor = monitor
        self._knowledge_base: list[IntelligenceReport] = []
        self._capability_gaps: list[CapabilityGapAlert] = []
        self._last_full_scan: datetime | None = None

        # Initialize sub-agents
        self._competitor_agent = CompetitorWatchAgent(
            llm_client=llm_client, config=config, monitor=monitor
        )
        self._trend_agent = TrendAnalysisAgent(
            llm_client=llm_client, config=config, monitor=monitor
        )
        self._doc_agent = DocumentationAggregatorAgent(
            llm_client=llm_client, config=config, monitor=monitor
        )

    @property
    def capability(self) -> AgentCapability:
        return AgentCapability.MARKET_INTELLIGENCE

    async def execute(self, task: str, context: Any = None) -> AgentResult:
        """Execute market research task.

        Args:
            task: Description of the research task
            context: Optional context for the task

        Returns:
            AgentResult with intelligence reports and gap alerts
        """
        start_time = datetime.now(timezone.utc)

        try:
            # Parse task to determine scope
            scope = self._parse_task_scope(task)

            # Execute sub-agents based on scope
            all_reports: list[IntelligenceReport] = []

            if (
                scope.get("competitor_watch", True)
                and self.config.enable_competitor_watch
            ):
                competitor_result = await self._competitor_agent.execute(task)
                if competitor_result.success and competitor_result.output:
                    reports = [
                        IntelligenceReport.from_dict(r)
                        for r in competitor_result.output.get("reports", [])
                    ]
                    all_reports.extend(reports)

            if scope.get("trend_analysis", True) and self.config.enable_trend_analysis:
                trend_result = await self._trend_agent.execute(task)
                if trend_result.success and trend_result.output:
                    reports = [
                        IntelligenceReport.from_dict(r)
                        for r in trend_result.output.get("reports", [])
                    ]
                    all_reports.extend(reports)

            if (
                scope.get("doc_aggregation", True)
                and self.config.enable_doc_aggregation
            ):
                doc_result = await self._doc_agent.execute(task)
                if doc_result.success and doc_result.output:
                    reports = [
                        IntelligenceReport.from_dict(r)
                        for r in doc_result.output.get("reports", [])
                    ]
                    all_reports.extend(reports)

            # Update knowledge base
            self._knowledge_base.extend(all_reports)
            self._prune_expired_reports()

            # Identify capability gaps
            new_gaps = await self._identify_capability_gaps(all_reports)
            self._capability_gaps.extend(new_gaps)

            # Generate summary report
            summary = await self._generate_summary(all_reports, new_gaps)

            self._last_full_scan = datetime.now(timezone.utc)

            return AgentResult(
                agent_id=self.agent_id,
                capability=self.capability,
                success=True,
                output={
                    "summary": summary,
                    "reports": [r.to_dict() for r in all_reports],
                    "report_count": len(all_reports),
                    "new_gaps": [g.to_dict() for g in new_gaps],
                    "gap_count": len(new_gaps),
                    "knowledge_base_size": len(self._knowledge_base),
                },
                execution_time_seconds=(
                    datetime.now(timezone.utc) - start_time
                ).total_seconds(),
                metadata={
                    "scope": scope,
                    "last_full_scan": self._last_full_scan.isoformat(),
                },
            )

        except Exception as e:
            logger.error(f"MarketIntelligenceAgent failed: {e}", exc_info=True)
            return AgentResult(
                agent_id=self.agent_id,
                capability=self.capability,
                success=False,
                output=None,
                execution_time_seconds=(
                    datetime.now(timezone.utc) - start_time
                ).total_seconds(),
                error=str(e),
            )

    def _parse_task_scope(self, task: str) -> dict[str, bool]:
        """Parse task to determine which sub-agents to run."""
        task_lower = task.lower()

        return {
            "competitor_watch": (
                "competitor" in task_lower
                or "aws" in task_lower
                or "azure" in task_lower
                or "gcp" in task_lower
                or "all" in task_lower
                or "full" in task_lower
            ),
            "trend_analysis": (
                "trend" in task_lower
                or "github" in task_lower
                or "technology" in task_lower
                or "all" in task_lower
                or "full" in task_lower
            ),
            "doc_aggregation": (
                "doc" in task_lower
                or "standard" in task_lower
                or "nist" in task_lower
                or "owasp" in task_lower
                or "all" in task_lower
                or "full" in task_lower
            ),
        }

    def _prune_expired_reports(self) -> None:
        """Remove expired reports from knowledge base."""
        now = datetime.now(timezone.utc)
        max_age = timedelta(days=self.config.max_report_age_days)

        self._knowledge_base = [
            r
            for r in self._knowledge_base
            if (r.expires_at is None or r.expires_at > now)
            and (now - r.discovered_at) < max_age
        ]

    async def _identify_capability_gaps(
        self, reports: list[IntelligenceReport]
    ) -> list[CapabilityGapAlert]:
        """Identify capability gaps from intelligence reports."""
        gaps = []

        for report in reports:
            if report.report_type == IntelligenceType.COMPETITOR:
                # Check for capability mentions that we don't have
                gap = self._check_for_gap(report)
                if gap:
                    gaps.append(gap)

        return gaps

    def _check_for_gap(self, report: IntelligenceReport) -> CapabilityGapAlert | None:
        """Check if a report indicates a capability gap."""
        # Keywords that indicate capabilities we should monitor
        gap_keywords = {
            "penetration testing": ("Active Penetration Testing", GapSeverity.MEDIUM),
            "design review": ("Design Document Review", GapSeverity.MEDIUM),
            "auto pr": ("Automatic PR Creation", GapSeverity.HIGH),
            "autonomous remediation": ("Autonomous Remediation", GapSeverity.HIGH),
        }

        text = f"{report.title} {report.summary}".lower()

        for keyword, (capability_name, severity) in gap_keywords.items():
            if keyword in text:
                return CapabilityGapAlert(
                    alert_id=f"gap-{hashlib.md5(f'{report.report_id}-{keyword}'.encode(), usedforsecurity=False).hexdigest()[:12]}",
                    competitor=report.metadata.get("competitor", "Unknown"),
                    capability=capability_name,
                    our_status=GapStatus.MISSING,
                    gap_severity=severity,
                    description=f"Competitor has {capability_name} capability",
                    recommended_action=f"Evaluate implementing {capability_name}",
                    related_reports=[report.report_id],
                )

        return None

    async def _generate_summary(
        self,
        reports: list[IntelligenceReport],
        gaps: list[CapabilityGapAlert],
    ) -> str:
        """Generate a summary of the intelligence gathered."""
        summary_parts = [
            f"Market Intelligence Summary - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            f"Reports Gathered: {len(reports)}",
            f"New Capability Gaps: {len(gaps)}",
            "",
        ]

        # Group reports by type
        by_type: dict[IntelligenceType, list[IntelligenceReport]] = {}
        for report in reports:
            by_type.setdefault(report.report_type, []).append(report)

        for report_type, type_reports in by_type.items():
            summary_parts.append(
                f"### {report_type.value.title()} ({len(type_reports)})"
            )
            for r in type_reports[:3]:  # Top 3 per type
                summary_parts.append(
                    f"- {r.title} (relevance: {r.relevance_score:.1%})"
                )
            summary_parts.append("")

        if gaps:
            summary_parts.append("### Capability Gaps Identified")
            for gap in gaps:
                summary_parts.append(
                    f"- [{gap.gap_severity.value.upper()}] {gap.capability} "
                    f"(vs {gap.competitor})"
                )

        return "\n".join(summary_parts)

    def get_knowledge_base(self) -> list[IntelligenceReport]:
        """Get all reports in the knowledge base."""
        return self._knowledge_base.copy()

    def get_capability_gaps(self) -> list[CapabilityGapAlert]:
        """Get all identified capability gaps."""
        return self._capability_gaps.copy()

    def query_knowledge_base(
        self,
        report_type: IntelligenceType | None = None,
        min_relevance: float = 0.0,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[IntelligenceReport]:
        """Query the knowledge base with filters."""
        results = self._knowledge_base.copy()

        if report_type:
            results = [r for r in results if r.report_type == report_type]

        if min_relevance > 0:
            results = [r for r in results if r.relevance_score >= min_relevance]

        if tags:
            results = [r for r in results if any(t in r.tags for t in tags)]

        # Sort by relevance and recency
        results.sort(key=lambda r: (-r.relevance_score, -r.discovered_at.timestamp()))

        return results[:limit]


# =============================================================================
# Factory Functions
# =============================================================================


def create_market_intelligence_agent(
    llm_client: "BedrockLLMService | None" = None,
    config: MarketIntelligenceConfig | None = None,
    monitor: MonitorAgent | None = None,
) -> MarketIntelligenceAgent:
    """Factory function to create a MarketIntelligenceAgent.

    Args:
        llm_client: Optional LLM service for analysis
        config: Optional configuration
        monitor: Optional monitoring agent

    Returns:
        Configured MarketIntelligenceAgent instance
    """
    return MarketIntelligenceAgent(
        llm_client=llm_client,
        config=config,
        monitor=monitor,
    )
