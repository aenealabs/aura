"""Tests for the Autonomous ADR Generation Pipeline agents.

Tests cover:
- ThreatIntelligenceAgent: Threat feed parsing and prioritization
- AdaptiveIntelligenceAgent: Risk analysis and recommendation generation
- ArchitectureReviewAgent: ADR-worthiness evaluation
- ADRGeneratorAgent: Document generation and formatting
"""

from datetime import datetime

import pytest

from src.agents.adaptive_intelligence_agent import (
    AdaptiveIntelligenceAgent,
    AdaptiveRecommendation,
    EffortLevel,
    RecommendationType,
    RiskLevel,
)
from src.agents.adr_generator_agent import ADRDocument, ADRGeneratorAgent
from src.agents.architecture_review_agent import (
    ADRCategory,
    ADRSignificance,
    ADRTriggerEvent,
    ArchitectureReviewAgent,
)
from src.agents.threat_intelligence_agent import (
    ThreatCategory,
    ThreatIntelConfig,
    ThreatIntelligenceAgent,
    ThreatIntelReport,
    ThreatSeverity,
)

# ============================================================================
# ThreatIntelligenceAgent Tests
# ============================================================================


class TestThreatIntelligenceAgent:
    """Tests for ThreatIntelligenceAgent."""

    def test_init_with_default_config(self):
        """Test agent initializes with default configuration."""
        agent = ThreatIntelligenceAgent()

        assert agent.config is not None
        assert agent.config.check_interval_minutes == 60
        assert agent.config.max_cve_age_days == 30

    def test_init_with_custom_config(self):
        """Test agent initializes with custom configuration."""
        config = ThreatIntelConfig(
            check_interval_minutes=30,
            max_cve_age_days=7,
            severity_threshold=ThreatSeverity.HIGH,
        )
        agent = ThreatIntelligenceAgent(config=config)

        assert agent.config.check_interval_minutes == 30
        assert agent.config.max_cve_age_days == 7
        assert agent.config.severity_threshold == ThreatSeverity.HIGH

    def test_set_dependency_sbom(self):
        """Test setting software bill of materials."""
        agent = ThreatIntelligenceAgent()
        sbom = [
            {"name": "requests", "version": "2.28.0"},
            {"name": "fastapi", "version": "0.108.0"},
        ]

        agent.set_dependency_sbom(sbom)

        assert len(agent._dependency_sbom) == 2
        assert agent._dependency_sbom[0]["name"] == "requests"

    def test_cvss_to_severity_critical(self):
        """Test CVSS score conversion to CRITICAL severity."""
        agent = ThreatIntelligenceAgent()

        assert agent._cvss_to_severity(10.0) == ThreatSeverity.CRITICAL
        assert agent._cvss_to_severity(9.5) == ThreatSeverity.CRITICAL
        assert agent._cvss_to_severity(9.0) == ThreatSeverity.CRITICAL

    def test_cvss_to_severity_high(self):
        """Test CVSS score conversion to HIGH severity."""
        agent = ThreatIntelligenceAgent()

        assert agent._cvss_to_severity(8.9) == ThreatSeverity.HIGH
        assert agent._cvss_to_severity(7.5) == ThreatSeverity.HIGH
        assert agent._cvss_to_severity(7.0) == ThreatSeverity.HIGH

    def test_cvss_to_severity_medium(self):
        """Test CVSS score conversion to MEDIUM severity."""
        agent = ThreatIntelligenceAgent()

        assert agent._cvss_to_severity(6.9) == ThreatSeverity.MEDIUM
        assert agent._cvss_to_severity(5.0) == ThreatSeverity.MEDIUM
        assert agent._cvss_to_severity(4.0) == ThreatSeverity.MEDIUM

    def test_cvss_to_severity_low(self):
        """Test CVSS score conversion to LOW severity."""
        agent = ThreatIntelligenceAgent()

        assert agent._cvss_to_severity(3.9) == ThreatSeverity.LOW
        assert agent._cvss_to_severity(2.0) == ThreatSeverity.LOW
        assert agent._cvss_to_severity(0.1) == ThreatSeverity.LOW

    def test_string_to_severity(self):
        """Test string to severity conversion."""
        agent = ThreatIntelligenceAgent()

        assert agent._string_to_severity("critical") == ThreatSeverity.CRITICAL
        assert agent._string_to_severity("HIGH") == ThreatSeverity.HIGH
        assert agent._string_to_severity("Medium") == ThreatSeverity.MEDIUM
        assert agent._string_to_severity("moderate") == ThreatSeverity.MEDIUM
        assert agent._string_to_severity("low") == ThreatSeverity.LOW
        assert agent._string_to_severity("unknown") == ThreatSeverity.INFORMATIONAL

    def test_check_dependency_match(self):
        """Test dependency matching against SBOM."""
        agent = ThreatIntelligenceAgent()
        agent.set_dependency_sbom(
            [
                {"name": "requests", "version": "2.28.0"},
                {"name": "fastapi", "version": "0.108.0"},
            ]
        )

        # Should match
        matches = agent._check_dependency_match(["requests"])
        assert len(matches) == 1
        assert "requests==2.28.0" in matches[0]

        # Should not match
        matches = agent._check_dependency_match(["django"])
        assert len(matches) == 0

    def test_generate_report_id(self):
        """Test unique report ID generation."""
        agent = ThreatIntelligenceAgent()

        id1 = agent._generate_report_id("nvd", "CVE-2025-0001")
        id2 = agent._generate_report_id("nvd", "CVE-2025-0002")
        id3 = agent._generate_report_id("cisa", "CVE-2025-0001")

        # Different CVEs should have different IDs
        assert id1 != id2

        # Same CVE from different sources should have different IDs
        assert id1 != id3

        # Same input should produce same ID
        assert agent._generate_report_id("nvd", "CVE-2025-0001") == id1

    def test_filter_new_reports(self):
        """Test filtering to only new reports."""
        agent = ThreatIntelligenceAgent()

        report1 = ThreatIntelReport(
            id="report-1",
            title="Test Report 1",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.HIGH,
            source="NVD",
            published_date=datetime.now(),
            description="Test",
        )
        report2 = ThreatIntelReport(
            id="report-2",
            title="Test Report 2",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.MEDIUM,
            source="NVD",
            published_date=datetime.now(),
            description="Test",
        )

        # First filter - both should be new
        new_reports = agent._filter_new_reports([report1, report2])
        assert len(new_reports) == 2

        # Second filter - both should be filtered out
        new_reports = agent._filter_new_reports([report1, report2])
        assert len(new_reports) == 0

    def test_prioritize_by_relevance(self):
        """Test report prioritization."""
        agent = ThreatIntelligenceAgent()

        critical_report = ThreatIntelReport(
            id="critical",
            title="Critical Report",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.CRITICAL,
            source="NVD",
            published_date=datetime.now(),
            description="Critical vulnerability",
        )
        low_report = ThreatIntelReport(
            id="low",
            title="Low Report",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.LOW,
            source="NVD",
            published_date=datetime.now(),
            description="Low severity",
        )

        prioritized = agent._prioritize_by_relevance([low_report, critical_report])

        # Critical should come first
        assert prioritized[0].severity == ThreatSeverity.CRITICAL
        assert prioritized[1].severity == ThreatSeverity.LOW

    def test_threat_intel_report_to_dict(self):
        """Test ThreatIntelReport serialization."""
        report = ThreatIntelReport(
            id="test-id",
            title="Test Report",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.HIGH,
            source="NVD",
            published_date=datetime(2025, 11, 29, 12, 0, 0),
            description="Test description",
            affected_components=["requests"],
            cve_ids=["CVE-2025-0001"],
            cvss_score=8.5,
        )

        data = report.to_dict()

        assert data["id"] == "test-id"
        assert data["category"] == "cve"
        assert data["severity"] == "high"
        assert data["cvss_score"] == 8.5
        assert "CVE-2025-0001" in data["cve_ids"]


# ============================================================================
# AdaptiveIntelligenceAgent Tests
# ============================================================================


class TestAdaptiveIntelligenceAgent:
    """Tests for AdaptiveIntelligenceAgent."""

    def test_init(self):
        """Test agent initialization."""
        agent = AdaptiveIntelligenceAgent()

        assert agent.context_service is None
        assert len(agent._best_practices_db) > 0
        assert len(agent._compliance_mappings) > 0

    def test_severity_to_base_score(self):
        """Test severity to base score conversion."""
        agent = AdaptiveIntelligenceAgent()

        assert agent._severity_to_base_score(ThreatSeverity.CRITICAL) == 9.0
        assert agent._severity_to_base_score(ThreatSeverity.HIGH) == 7.0
        assert agent._severity_to_base_score(ThreatSeverity.MEDIUM) == 5.0
        assert agent._severity_to_base_score(ThreatSeverity.LOW) == 3.0
        assert agent._severity_to_base_score(ThreatSeverity.INFORMATIONAL) == 1.0

    def test_score_to_risk_level(self):
        """Test risk score to risk level conversion."""
        agent = AdaptiveIntelligenceAgent()

        assert agent._score_to_risk_level(10.0) == RiskLevel.CRITICAL
        assert agent._score_to_risk_level(9.0) == RiskLevel.CRITICAL
        assert agent._score_to_risk_level(8.0) == RiskLevel.HIGH
        assert agent._score_to_risk_level(7.0) == RiskLevel.HIGH
        assert agent._score_to_risk_level(6.0) == RiskLevel.MODERATE
        assert agent._score_to_risk_level(5.0) == RiskLevel.MODERATE
        assert agent._score_to_risk_level(4.0) == RiskLevel.LOW
        assert agent._score_to_risk_level(3.0) == RiskLevel.LOW
        assert agent._score_to_risk_level(2.0) == RiskLevel.MINIMAL

    def test_determine_recommendation_type_cve(self):
        """Test recommendation type determination for CVE."""
        agent = AdaptiveIntelligenceAgent()

        report = ThreatIntelReport(
            id="test",
            title="Test",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.HIGH,
            source="NVD",
            published_date=datetime.now(),
            description="Test",
            cve_ids=["CVE-2025-0001"],
            affected_components=["requests"],
        )

        rec_type = agent._determine_recommendation_type(report)
        assert rec_type == RecommendationType.DEPENDENCY_UPGRADE

    def test_determine_recommendation_type_compliance(self):
        """Test recommendation type determination for compliance."""
        agent = AdaptiveIntelligenceAgent()

        report = ThreatIntelReport(
            id="test",
            title="Test",
            category=ThreatCategory.COMPLIANCE,
            severity=ThreatSeverity.MEDIUM,
            source="NIST",
            published_date=datetime.now(),
            description="Compliance update",
        )

        rec_type = agent._determine_recommendation_type(report)
        assert rec_type == RecommendationType.COMPLIANCE_UPDATE

    def test_estimate_effort_trivial(self):
        """Test effort estimation for trivial changes."""
        agent = AdaptiveIntelligenceAgent()

        report = ThreatIntelReport(
            id="test",
            title="Test",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.HIGH,
            source="NVD",
            published_date=datetime.now(),
            description="Test",
            cve_ids=["CVE-2025-0001"],
        )

        effort = agent._estimate_effort(report, {"affected_files": []})
        assert effort == EffortLevel.TRIVIAL

    def test_estimate_effort_large(self):
        """Test effort estimation for large changes."""
        agent = AdaptiveIntelligenceAgent()

        report = ThreatIntelReport(
            id="test",
            title="Test",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.HIGH,
            source="NVD",
            published_date=datetime.now(),
            description="Test",
        )

        impact = {
            "affected_files": [
                "file1.py",
                "file2.py",
                "file3.py",
                "file4.py",
                "file5.py",
                "file6.py",
                "file7.py",
                "file8.py",
            ]
        }

        effort = agent._estimate_effort(report, impact)
        assert effort == EffortLevel.LARGE

    def test_check_infrastructure_impact(self):
        """Test infrastructure impact detection."""
        agent = AdaptiveIntelligenceAgent()

        report_infra = ThreatIntelReport(
            id="test",
            title="EKS vulnerability",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.HIGH,
            source="NVD",
            published_date=datetime.now(),
            description="Vulnerability in Kubernetes clusters",
        )

        report_app = ThreatIntelReport(
            id="test2",
            title="Python library issue",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.MEDIUM,
            source="NVD",
            published_date=datetime.now(),
            description="Issue in requests library",
        )

        assert agent._check_infrastructure_impact(report_infra) is True
        assert agent._check_infrastructure_impact(report_app) is False

    def test_adaptive_recommendation_to_dict(self):
        """Test AdaptiveRecommendation serialization."""
        rec = AdaptiveRecommendation(
            id="REC-001",
            title="Test Recommendation",
            recommendation_type=RecommendationType.SECURITY_PATCH,
            severity=ThreatSeverity.HIGH,
            risk_score=8.5,
            risk_level=RiskLevel.HIGH,
            effort_level=EffortLevel.MEDIUM,
            description="Test description",
            rationale="Test rationale",
            affected_components=["component1"],
            implementation_steps=["Step 1", "Step 2"],
        )

        data = rec.to_dict()

        assert data["id"] == "REC-001"
        assert data["recommendation_type"] == "security_patch"
        assert data["risk_score"] == 8.5
        assert len(data["implementation_steps"]) == 2


# ============================================================================
# ArchitectureReviewAgent Tests
# ============================================================================


class TestArchitectureReviewAgent:
    """Tests for ArchitectureReviewAgent."""

    def test_init(self):
        """Test agent initialization."""
        agent = ArchitectureReviewAgent()

        assert len(agent._architecture_patterns) > 0
        assert len(agent._adr_index) > 0

    def test_is_adr_worthy_critical_severity(self):
        """Test ADR-worthiness for critical severity."""
        agent = ArchitectureReviewAgent()

        rec = AdaptiveRecommendation(
            id="REC-001",
            title="Critical Fix",
            recommendation_type=RecommendationType.SECURITY_PATCH,
            severity=ThreatSeverity.CRITICAL,
            risk_score=9.5,
            risk_level=RiskLevel.CRITICAL,
            effort_level=EffortLevel.SMALL,
            description="Critical security fix",
            rationale="Test",
        )

        assert agent._is_adr_worthy(rec) is True

    def test_is_adr_worthy_architecture_change(self):
        """Test ADR-worthiness for architecture changes."""
        agent = ArchitectureReviewAgent()

        rec = AdaptiveRecommendation(
            id="REC-001",
            title="Architecture Change",
            recommendation_type=RecommendationType.ARCHITECTURE_CHANGE,
            severity=ThreatSeverity.MEDIUM,
            risk_score=5.0,
            risk_level=RiskLevel.MODERATE,
            effort_level=EffortLevel.LARGE,
            description="Major architecture change",
            rationale="Test",
        )

        assert agent._is_adr_worthy(rec) is True

    def test_is_adr_worthy_low_severity_small_effort(self):
        """Test ADR-worthiness for low severity, small effort changes."""
        agent = ArchitectureReviewAgent()

        rec = AdaptiveRecommendation(
            id="REC-001",
            title="Minor Update",
            recommendation_type=RecommendationType.DEPENDENCY_UPGRADE,
            severity=ThreatSeverity.LOW,
            risk_score=2.0,
            risk_level=RiskLevel.MINIMAL,
            effort_level=EffortLevel.TRIVIAL,
            description="Minor dependency update",
            rationale="Test",
            affected_components=[],
        )

        # Low severity, trivial effort, no pattern deviation = not ADR-worthy
        assert agent._is_adr_worthy(rec) is False

    def test_determine_significance_critical(self):
        """Test significance determination for critical severity."""
        agent = ArchitectureReviewAgent()

        rec = AdaptiveRecommendation(
            id="REC-001",
            title="Critical",
            recommendation_type=RecommendationType.SECURITY_PATCH,
            severity=ThreatSeverity.CRITICAL,
            risk_score=9.5,
            risk_level=RiskLevel.CRITICAL,
            effort_level=EffortLevel.MEDIUM,
            description="Critical",
            rationale="Test",
        )

        significance = agent._determine_significance(rec)
        assert significance == ADRSignificance.CRITICAL

    def test_determine_significance_high(self):
        """Test significance determination for high severity."""
        agent = ArchitectureReviewAgent()

        rec = AdaptiveRecommendation(
            id="REC-001",
            title="High",
            recommendation_type=RecommendationType.SECURITY_PATCH,
            severity=ThreatSeverity.HIGH,
            risk_score=7.5,
            risk_level=RiskLevel.HIGH,
            effort_level=EffortLevel.MEDIUM,
            description="High severity",
            rationale="Test",
        )

        significance = agent._determine_significance(rec)
        assert significance == ADRSignificance.HIGH

    def test_determine_category(self):
        """Test ADR category determination."""
        agent = ArchitectureReviewAgent()

        rec_security = AdaptiveRecommendation(
            id="REC-001",
            title="Security",
            recommendation_type=RecommendationType.SECURITY_PATCH,
            severity=ThreatSeverity.HIGH,
            risk_score=7.5,
            risk_level=RiskLevel.HIGH,
            effort_level=EffortLevel.MEDIUM,
            description="Security patch",
            rationale="Test",
        )

        rec_dependency = AdaptiveRecommendation(
            id="REC-002",
            title="Dependency",
            recommendation_type=RecommendationType.DEPENDENCY_UPGRADE,
            severity=ThreatSeverity.MEDIUM,
            risk_score=5.0,
            risk_level=RiskLevel.MODERATE,
            effort_level=EffortLevel.SMALL,
            description="Dependency upgrade",
            rationale="Test",
        )

        assert agent._determine_category(rec_security) == ADRCategory.SECURITY
        assert agent._determine_category(rec_dependency) == ADRCategory.DEPENDENCY

    def test_adr_trigger_event_to_dict(self):
        """Test ADRTriggerEvent serialization."""
        trigger = ADRTriggerEvent(
            id="TRIG-001",
            title="Test Trigger",
            category=ADRCategory.SECURITY,
            significance=ADRSignificance.HIGH,
            description="Test description",
            context_summary="Test context",
            affected_components=["component1"],
            requires_hitl=True,
        )

        data = trigger.to_dict()

        assert data["id"] == "TRIG-001"
        assert data["category"] == "security"
        assert data["significance"] == "high"
        assert data["requires_hitl"] is True


# ============================================================================
# ADRGeneratorAgent Tests
# ============================================================================


class TestADRGeneratorAgent:
    """Tests for ADRGeneratorAgent."""

    def test_init(self):
        """Test agent initialization."""
        agent = ADRGeneratorAgent()

        assert agent.adr_directory.name == "architecture-decisions"
        assert agent._next_adr_number >= 1

    def test_adr_document_to_markdown(self):
        """Test ADR document markdown generation."""
        adr = ADRDocument(
            number=99,
            title="Test ADR",
            status="Proposed",
            date="2025-11-29",
            decision_makers="Test Team",
            context="This is the context.",
            decision="This is the decision.",
            alternatives=[
                {
                    "title": "Option A",
                    "description": "Description of A",
                    "pros": ["Pro 1", "Pro 2"],
                    "cons": ["Con 1"],
                }
            ],
            consequences_positive=["Positive 1", "Positive 2"],
            consequences_negative=["Negative 1"],
            consequences_mitigation=["Mitigation 1"],
            references=["Reference 1", "Reference 2"],
        )

        markdown = adr.to_markdown()

        assert "# ADR-099: Test ADR" in markdown
        assert "**Status:** Proposed" in markdown
        assert "## Context" in markdown
        assert "## Decision" in markdown
        assert "## Alternatives Considered" in markdown
        assert "### Alternative 1: Option A" in markdown
        assert "## Consequences" in markdown
        assert "### Positive" in markdown
        assert "### Negative" in markdown
        assert "### Mitigation" in markdown
        assert "## References" in markdown

    def test_adr_document_get_filename(self):
        """Test ADR filename generation."""
        adr = ADRDocument(
            number=99,
            title="Test ADR Title Here",
            status="Proposed",
            date="2025-11-29",
            decision_makers="Test",
            context="Context",
            decision="Decision",
        )

        filename = adr.get_filename()

        assert filename.startswith("ADR-099-")
        assert filename.endswith(".md")
        assert "test-adr-title-here" in filename

    def test_adr_document_get_filename_special_chars(self):
        """Test ADR filename generation with special characters."""
        adr = ADRDocument(
            number=1,
            title="Security: Fix SQL Injection (Critical!)",
            status="Proposed",
            date="2025-11-29",
            decision_makers="Test",
            context="Context",
            decision="Decision",
        )

        filename = adr.get_filename()

        # Special chars should be removed
        assert ":" not in filename
        assert "(" not in filename
        assert ")" not in filename
        assert "!" not in filename
        assert filename.startswith("ADR-001-")

    def test_generate_security_alternatives(self):
        """Test security alternative generation."""
        agent = ADRGeneratorAgent()

        alternatives = agent._generate_security_alternatives(None)

        assert len(alternatives) == 3
        assert alternatives[0]["title"] == "Accept Risk (Do Nothing)"
        assert alternatives[1]["title"] == "Compensating Controls Only"
        assert alternatives[2]["title"] == "Immediate Patch (Chosen)"

        # Each alternative should have pros and cons
        for alt in alternatives:
            assert "pros" in alt
            assert "cons" in alt
            assert len(alt["pros"]) > 0
            assert len(alt["cons"]) > 0

    def test_analyze_consequences(self):
        """Test consequence analysis."""
        agent = ADRGeneratorAgent()

        trigger = ADRTriggerEvent(
            id="TRIG-001",
            title="Test",
            category=ADRCategory.SECURITY,
            significance=ADRSignificance.HIGH,
            description="Test",
            context_summary="Test",
        )

        positives, negatives, mitigations = agent._analyze_consequences_fallback(
            trigger, None
        )

        assert len(positives) > 0
        assert len(negatives) > 0
        assert len(mitigations) > 0

        # Security category should have security-specific consequences
        assert any("vulnerability" in p.lower() for p in positives)

    def test_compile_references(self):
        """Test reference compilation."""
        agent = ADRGeneratorAgent()

        trigger = ADRTriggerEvent(
            id="TRIG-001",
            title="Test",
            category=ADRCategory.SECURITY,
            significance=ADRSignificance.HIGH,
            description="Test",
            context_summary="Test",
            existing_adr_references=["ADR-005", "ADR-008"],
        )

        references = agent._compile_references(trigger, None)

        assert len(references) > 0
        # Should include related ADRs
        assert any("ADR-005" in ref for ref in references)
        # Should include standard references
        assert any("HITL_SANDBOX_ARCHITECTURE" in ref for ref in references)


# ============================================================================
# Integration Tests
# ============================================================================


class TestADRPipelineIntegration:
    """Integration tests for the full ADR pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline_flow(self):
        """Test complete pipeline from threat to ADR."""
        # Create a mock threat report
        threat = ThreatIntelReport(
            id="threat-001",
            title="Critical RCE in requests library",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.CRITICAL,
            source="NVD",
            published_date=datetime.now(),
            description="Remote code execution in requests < 2.31.0",
            affected_components=["requests==2.28.0"],
            cve_ids=["CVE-2025-0001"],
            cvss_score=9.8,
        )

        # Phase 2: Adaptive Intelligence
        adaptive_agent = AdaptiveIntelligenceAgent()
        recommendations = await adaptive_agent.analyze_threats([threat])

        assert len(recommendations) == 1
        rec = recommendations[0]
        assert rec.severity == ThreatSeverity.CRITICAL
        assert rec.risk_score >= 9.0

        # Phase 3: Architecture Review
        review_agent = ArchitectureReviewAgent()
        triggers = review_agent.evaluate_recommendations(recommendations)

        assert len(triggers) == 1
        trigger = triggers[0]
        assert trigger.significance == ADRSignificance.CRITICAL
        assert trigger.requires_hitl is True

        # Phase 4: ADR Generation
        generator_agent = ADRGeneratorAgent()
        adrs = await generator_agent.generate_adrs(triggers)

        assert len(adrs) == 1
        adr = adrs[0]
        assert adr.status == "Proposed"
        assert "Critical" in adr.title or "RCE" in adr.title

        # Verify markdown output
        markdown = adr.to_markdown()
        assert "## Context" in markdown
        assert "## Decision" in markdown
        assert "## Alternatives Considered" in markdown
        assert "## Consequences" in markdown

    @pytest.mark.asyncio
    async def test_pipeline_filters_low_priority(self):
        """Test that pipeline filters out low priority items."""
        # Create a low severity threat
        threat = ThreatIntelReport(
            id="threat-002",
            title="Minor information disclosure",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.LOW,
            source="NVD",
            published_date=datetime.now(),
            description="Minor info disclosure in unused component",
            affected_components=[],  # Not affecting our dependencies
            cve_ids=["CVE-2025-0002"],
            cvss_score=2.5,
        )

        # Phase 2: Adaptive Intelligence
        adaptive_agent = AdaptiveIntelligenceAgent()
        recommendations = await adaptive_agent.analyze_threats([threat])

        # Low severity with no affected components should not require action
        # (depending on implementation, may return 0 or 1 recommendation)

        # Phase 3: Architecture Review
        review_agent = ArchitectureReviewAgent()
        triggers = review_agent.evaluate_recommendations(recommendations)

        # Low priority should not trigger ADR
        # Either no recommendations, or recommendations filtered as not ADR-worthy
        for trigger in triggers:
            # If any triggers, they should be low significance
            assert trigger.significance in [
                ADRSignificance.LOW,
                ADRSignificance.INFORMATIONAL,
            ]
            assert trigger.requires_hitl is False


# ============================================================================
# Additional ADRGeneratorAgent Tests for Coverage
# ============================================================================


class TestADRGeneratorAgentAlternatives:
    """Tests for ADRGeneratorAgent alternative generation methods."""

    def test_generate_dependency_alternatives(self):
        """Test dependency alternative generation."""
        agent = ADRGeneratorAgent()

        alternatives = agent._generate_dependency_alternatives(None)

        assert len(alternatives) == 3
        assert alternatives[0]["title"] == "Pin Current Version"
        assert alternatives[1]["title"] == "Replace Dependency"
        assert alternatives[2]["title"] == "Upgrade to Patched Version (Chosen)"

        for alt in alternatives:
            assert "pros" in alt
            assert "cons" in alt
            assert len(alt["pros"]) > 0
            assert len(alt["cons"]) > 0

    def test_generate_infrastructure_alternatives(self):
        """Test infrastructure alternative generation."""
        agent = ADRGeneratorAgent()

        alternatives = agent._generate_infrastructure_alternatives(None)

        assert len(alternatives) == 2
        assert alternatives[0]["title"] == "Manual Configuration"
        assert alternatives[1]["title"] == "Infrastructure as Code Update (Chosen)"

        for alt in alternatives:
            assert "pros" in alt
            assert "cons" in alt

    def test_generate_compliance_alternatives(self):
        """Test compliance alternative generation."""
        agent = ADRGeneratorAgent()

        alternatives = agent._generate_compliance_alternatives(None)

        assert len(alternatives) == 2
        assert alternatives[0]["title"] == "Request Exception"
        assert alternatives[1]["title"] == "Implement Compliance Control (Chosen)"

        for alt in alternatives:
            assert "pros" in alt
            assert "cons" in alt

    def test_generate_generic_alternatives(self):
        """Test generic alternative generation."""
        agent = ADRGeneratorAgent()

        alternatives = agent._generate_generic_alternatives(None)

        assert len(alternatives) == 2
        assert alternatives[0]["title"] == "Defer Decision"
        assert alternatives[1]["title"] == "Implement Recommendation (Chosen)"

    def test_evaluate_alternatives_fallback_security(self):
        """Test alternatives evaluation for security category."""
        agent = ADRGeneratorAgent()

        trigger = ADRTriggerEvent(
            id="TRIG-001",
            title="Security Fix",
            category=ADRCategory.SECURITY,
            significance=ADRSignificance.HIGH,
            description="Test",
            context_summary="Test",
        )

        alternatives = agent._evaluate_alternatives_fallback(trigger, None)

        assert len(alternatives) == 3
        assert "Immediate Patch" in alternatives[2]["title"]

    def test_evaluate_alternatives_fallback_dependency(self):
        """Test alternatives evaluation for dependency category."""
        agent = ADRGeneratorAgent()

        trigger = ADRTriggerEvent(
            id="TRIG-001",
            title="Dependency Upgrade",
            category=ADRCategory.DEPENDENCY,
            significance=ADRSignificance.HIGH,
            description="Test",
            context_summary="Test",
        )

        alternatives = agent._evaluate_alternatives_fallback(trigger, None)

        assert len(alternatives) == 3
        assert "Upgrade" in alternatives[2]["title"]

    def test_evaluate_alternatives_fallback_infrastructure(self):
        """Test alternatives evaluation for infrastructure category."""
        agent = ADRGeneratorAgent()

        trigger = ADRTriggerEvent(
            id="TRIG-001",
            title="Infrastructure Change",
            category=ADRCategory.INFRASTRUCTURE,
            significance=ADRSignificance.HIGH,
            description="Test",
            context_summary="Test",
        )

        alternatives = agent._evaluate_alternatives_fallback(trigger, None)

        assert len(alternatives) == 2
        assert "Infrastructure as Code" in alternatives[1]["title"]

    def test_evaluate_alternatives_fallback_compliance(self):
        """Test alternatives evaluation for compliance category."""
        agent = ADRGeneratorAgent()

        trigger = ADRTriggerEvent(
            id="TRIG-001",
            title="Compliance Update",
            category=ADRCategory.COMPLIANCE,
            significance=ADRSignificance.HIGH,
            description="Test",
            context_summary="Test",
        )

        alternatives = agent._evaluate_alternatives_fallback(trigger, None)

        assert len(alternatives) == 2
        assert "Compliance Control" in alternatives[1]["title"]

    def test_evaluate_alternatives_fallback_optimization(self):
        """Test alternatives evaluation for optimization category (generic)."""
        agent = ADRGeneratorAgent()

        trigger = ADRTriggerEvent(
            id="TRIG-001",
            title="Performance Optimization",
            category=ADRCategory.OPTIMIZATION,
            significance=ADRSignificance.MEDIUM,
            description="Test",
            context_summary="Test",
        )

        alternatives = agent._evaluate_alternatives_fallback(trigger, None)

        assert len(alternatives) == 2
        assert "Implement Recommendation" in alternatives[1]["title"]


class TestADRGeneratorAgentContextAndDecision:
    """Tests for ADRGeneratorAgent context and decision methods."""

    def test_synthesize_context_fallback_with_threat(self):
        """Test context synthesis with threat information."""
        agent = ADRGeneratorAgent()

        threat = ThreatIntelReport(
            id="threat-001",
            title="Critical RCE",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.CRITICAL,
            source="NVD",
            published_date=datetime.now(),
            description="Test threat",
            cve_ids=["CVE-2025-0001"],
            cvss_score=9.8,
        )

        rec = AdaptiveRecommendation(
            id="REC-001",
            title="Security Patch",
            recommendation_type=RecommendationType.SECURITY_PATCH,
            severity=ThreatSeverity.CRITICAL,
            risk_score=9.5,
            risk_level=RiskLevel.CRITICAL,
            effort_level=EffortLevel.MEDIUM,
            description="Apply patch",
            rationale="Critical vulnerability",
            source_threat=threat,
            compliance_impact=["CMMC-SC.L2-3.13.1", "NIST-SI-2"],
        )

        trigger = ADRTriggerEvent(
            id="TRIG-001",
            title="Security Fix",
            category=ADRCategory.SECURITY,
            significance=ADRSignificance.CRITICAL,
            description="Test",
            context_summary="Critical vulnerability detected.",
            affected_components=["component1", "component2"],
            pattern_deviations=["deviation1"],
            existing_adr_references=["ADR-005"],
            source_recommendation=rec,
        )

        context = agent._synthesize_context_fallback(trigger, rec)

        assert "Critical vulnerability detected" in context
        assert "NVD" in context
        assert "CVE-2025-0001" in context
        assert "9.8" in context
        assert "component1" in context
        assert "deviation1" in context
        assert "ADR-005" in context
        assert "CMMC" in context or "NIST" in context

    def test_formulate_decision_fallback_security(self):
        """Test decision formulation for security category."""
        agent = ADRGeneratorAgent()

        rec = AdaptiveRecommendation(
            id="REC-001",
            title="Security Patch",
            recommendation_type=RecommendationType.SECURITY_PATCH,
            severity=ThreatSeverity.HIGH,
            risk_score=8.0,
            risk_level=RiskLevel.HIGH,
            effort_level=EffortLevel.MEDIUM,
            description="Apply security patch",
            rationale="Addresses critical vulnerability",
            implementation_steps=["Step 1: Review", "Step 2: Apply", "Step 3: Test"],
            validation_criteria=["Tests pass", "No regressions"],
        )

        trigger = ADRTriggerEvent(
            id="TRIG-001",
            title="Security Fix",
            category=ADRCategory.SECURITY,
            significance=ADRSignificance.HIGH,
            description="Test",
            context_summary="Test",
            source_recommendation=rec,
        )

        decision = agent._formulate_decision_fallback(trigger, rec)

        assert "security remediation" in decision
        assert "Addresses critical vulnerability" in decision
        assert "Step 1: Review" in decision
        assert "Tests pass" in decision

    def test_formulate_decision_fallback_all_categories(self):
        """Test decision formulation for all categories."""
        agent = ADRGeneratorAgent()

        categories = [
            (ADRCategory.INFRASTRUCTURE, "infrastructure configuration"),
            (ADRCategory.DEPENDENCY, "upgrade affected dependencies"),
            (ADRCategory.CONFIGURATION, "modify system configuration"),
            (ADRCategory.COMPLIANCE, "compliance requirements"),
            (ADRCategory.OPTIMIZATION, "implement optimization"),
            (ADRCategory.INTEGRATION, "integrate new component"),
        ]

        for category, expected_text in categories:
            trigger = ADRTriggerEvent(
                id="TRIG-001",
                title="Test",
                category=category,
                significance=ADRSignificance.MEDIUM,
                description="Test",
                context_summary="Test",
            )

            decision = agent._formulate_decision_fallback(trigger, None)

            assert expected_text in decision

    def test_formulate_decision_with_best_practices(self):
        """Test decision formulation includes best practices."""
        from src.agents.adaptive_intelligence_agent import BestPractice

        agent = ADRGeneratorAgent()

        bp = BestPractice(
            id="BP-001",
            title="Use SHA256",
            description="Use SHA256 instead of SHA1",
            source="NIST",
        )

        rec = AdaptiveRecommendation(
            id="REC-001",
            title="Security Patch",
            recommendation_type=RecommendationType.SECURITY_PATCH,
            severity=ThreatSeverity.HIGH,
            risk_score=8.0,
            risk_level=RiskLevel.HIGH,
            effort_level=EffortLevel.MEDIUM,
            description="Apply patch",
            rationale="Fix vulnerability",
            best_practices=[bp],
        )

        trigger = ADRTriggerEvent(
            id="TRIG-001",
            title="Security Fix",
            category=ADRCategory.SECURITY,
            significance=ADRSignificance.HIGH,
            description="Test",
            context_summary="Test",
            source_recommendation=rec,
        )

        decision = agent._formulate_decision_fallback(trigger, rec)

        assert "Best Practices Applied" in decision
        assert "Use SHA256" in decision
        assert "NIST" in decision


class TestADRGeneratorAgentConsequences:
    """Tests for ADRGeneratorAgent consequence analysis."""

    def test_analyze_consequences_dependency(self):
        """Test consequence analysis for dependency category."""
        agent = ADRGeneratorAgent()

        trigger = ADRTriggerEvent(
            id="TRIG-001",
            title="Dependency Upgrade",
            category=ADRCategory.DEPENDENCY,
            significance=ADRSignificance.HIGH,
            description="Test",
            context_summary="Test",
        )

        positives, negatives, mitigations = agent._analyze_consequences_fallback(
            trigger, None
        )

        assert any("dependency" in p.lower() for p in positives)
        assert any(
            "breaking" in n.lower() or "compatibility" in n.lower() for n in negatives
        )
        assert any("changelog" in m.lower() or "test" in m.lower() for m in mitigations)

    def test_analyze_consequences_infrastructure(self):
        """Test consequence analysis for infrastructure category."""
        agent = ADRGeneratorAgent()

        trigger = ADRTriggerEvent(
            id="TRIG-001",
            title="Infrastructure Change",
            category=ADRCategory.INFRASTRUCTURE,
            significance=ADRSignificance.HIGH,
            description="Test",
            context_summary="Test",
        )

        positives, negatives, mitigations = agent._analyze_consequences_fallback(
            trigger, None
        )

        assert any(
            "infrastructure" in p.lower() or "security" in p.lower() for p in positives
        )
        assert any(
            "deployment" in n.lower() or "disruption" in n.lower() for n in negatives
        )
        assert any(
            "cloudformation" in m.lower() or "rollback" in m.lower()
            for m in mitigations
        )

    def test_analyze_consequences_compliance(self):
        """Test consequence analysis for compliance category."""
        agent = ADRGeneratorAgent()

        trigger = ADRTriggerEvent(
            id="TRIG-001",
            title="Compliance Update",
            category=ADRCategory.COMPLIANCE,
            significance=ADRSignificance.HIGH,
            description="Test",
            context_summary="Test",
        )

        positives, negatives, mitigations = agent._analyze_consequences_fallback(
            trigger, None
        )

        assert any("compliance" in p.lower() or "audit" in p.lower() for p in positives)
        assert any(
            "process" in n.lower() or "documentation" in n.lower() for n in negatives
        )
        assert any(
            "compliance" in m.lower() or "train" in m.lower() for m in mitigations
        )

    def test_analyze_consequences_with_high_risk(self):
        """Test consequence analysis with high risk recommendation."""
        agent = ADRGeneratorAgent()

        rec = AdaptiveRecommendation(
            id="REC-001",
            title="High Risk Change",
            recommendation_type=RecommendationType.SECURITY_PATCH,
            severity=ThreatSeverity.CRITICAL,
            risk_score=9.5,
            risk_level=RiskLevel.CRITICAL,
            effort_level=EffortLevel.LARGE,
            description="High risk change",
            rationale="Critical but risky",
        )

        trigger = ADRTriggerEvent(
            id="TRIG-001",
            title="Security Fix",
            category=ADRCategory.SECURITY,
            significance=ADRSignificance.CRITICAL,
            description="Test",
            context_summary="Test",
            source_recommendation=rec,
        )

        positives, negatives, mitigations = agent._analyze_consequences_fallback(
            trigger, rec
        )

        # Should include high-risk warning
        assert any("high-risk" in n.lower() or "9.5" in n for n in negatives)
        assert any(
            "sandbox" in m.lower() or "testing" in m.lower() for m in mitigations
        )

        # Should include effort warning
        assert any("effort" in n.lower() or "large" in n.lower() for n in negatives)
        assert any("phased" in m.lower() for m in mitigations)

    def test_analyze_consequences_generic(self):
        """Test consequence analysis for generic category."""
        agent = ADRGeneratorAgent()

        trigger = ADRTriggerEvent(
            id="TRIG-001",
            title="Generic Change",
            category=ADRCategory.INTEGRATION,  # Uses generic
            significance=ADRSignificance.MEDIUM,
            description="Test",
            context_summary="Test",
        )

        positives, negatives, mitigations = agent._analyze_consequences_fallback(
            trigger, None
        )

        assert any("proactively" in p.lower() or "debt" in p.lower() for p in positives)
        assert any("effort" in n.lower() for n in negatives)
        assert any(
            "change management" in m.lower() or "validate" in m.lower()
            for m in mitigations
        )


class TestADRGeneratorAgentLLM:
    """Tests for ADRGeneratorAgent LLM methods."""

    @pytest.mark.asyncio
    async def test_synthesize_context_llm_success(self):
        """Test context synthesis with LLM."""
        from unittest.mock import AsyncMock

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = '{"context": "LLM generated context text."}'

        agent = ADRGeneratorAgent(llm_client=mock_llm)

        trigger = ADRTriggerEvent(
            id="TRIG-001",
            title="Security Fix",
            category=ADRCategory.SECURITY,
            significance=ADRSignificance.HIGH,
            description="Test",
            context_summary="Test context",
            affected_components=["component1"],
        )

        context = await agent._synthesize_context_llm(trigger, None)

        assert context == "LLM generated context text."
        mock_llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_synthesize_context_llm_parse_error(self):
        """Test context synthesis falls back on parse error."""
        from unittest.mock import AsyncMock

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "not valid json"

        agent = ADRGeneratorAgent(llm_client=mock_llm)

        trigger = ADRTriggerEvent(
            id="TRIG-001",
            title="Test",
            category=ADRCategory.SECURITY,
            significance=ADRSignificance.HIGH,
            description="Test",
            context_summary="Test",
        )

        context = await agent._synthesize_context_llm(trigger, None)

        assert context == ""

    @pytest.mark.asyncio
    async def test_formulate_decision_llm_success(self):
        """Test decision formulation with LLM."""
        from unittest.mock import AsyncMock

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = (
            '{"decision": "We decided to implement the fix."}'
        )

        agent = ADRGeneratorAgent(llm_client=mock_llm)

        trigger = ADRTriggerEvent(
            id="TRIG-001",
            title="Test",
            category=ADRCategory.SECURITY,
            significance=ADRSignificance.HIGH,
            description="Test",
            context_summary="Test",
        )

        decision = await agent._formulate_decision_llm(trigger, None)

        assert decision == "We decided to implement the fix."

    @pytest.mark.asyncio
    async def test_evaluate_alternatives_llm_success(self):
        """Test alternatives evaluation with LLM."""
        import json
        from unittest.mock import AsyncMock

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "alternatives": [
                    {
                        "title": "Option A",
                        "description": "Desc A",
                        "pros": ["Pro"],
                        "cons": ["Con"],
                    },
                    {
                        "title": "Option B (Chosen)",
                        "description": "Desc B",
                        "pros": ["Pro"],
                        "cons": ["Con"],
                    },
                ]
            }
        )

        agent = ADRGeneratorAgent(llm_client=mock_llm)

        trigger = ADRTriggerEvent(
            id="TRIG-001",
            title="Test",
            category=ADRCategory.SECURITY,
            significance=ADRSignificance.HIGH,
            description="Test",
            context_summary="Test",
        )

        alternatives = await agent._evaluate_alternatives_llm(trigger, None)

        assert len(alternatives) == 2
        assert alternatives[0]["title"] == "Option A"
        assert alternatives[1]["title"] == "Option B (Chosen)"

    @pytest.mark.asyncio
    async def test_analyze_consequences_llm_success(self):
        """Test consequences analysis with LLM."""
        import json
        from unittest.mock import AsyncMock

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "positive": ["Security improved", "Compliance maintained"],
                "negative": ["Implementation effort"],
                "mitigation": ["Test thoroughly"],
            }
        )

        agent = ADRGeneratorAgent(llm_client=mock_llm)

        trigger = ADRTriggerEvent(
            id="TRIG-001",
            title="Test",
            category=ADRCategory.SECURITY,
            significance=ADRSignificance.HIGH,
            description="Test",
            context_summary="Test",
        )

        positives, negatives, mitigations = await agent._analyze_consequences_llm(
            trigger, None
        )

        assert len(positives) == 2
        assert len(negatives) == 1
        assert len(mitigations) == 1
        assert "Security improved" in positives

    @pytest.mark.asyncio
    async def test_generate_adr_with_llm(self):
        """Test full ADR generation with LLM."""
        import json
        from unittest.mock import AsyncMock

        mock_llm = AsyncMock()

        # Configure different responses for each call
        mock_llm.generate.side_effect = [
            json.dumps({"context": "LLM context"}),
            json.dumps({"decision": "LLM decision"}),
            json.dumps(
                {
                    "alternatives": [
                        {
                            "title": "LLM Alt",
                            "description": "Desc",
                            "pros": ["Pro"],
                            "cons": ["Con"],
                        }
                    ]
                }
            ),
            json.dumps(
                {"positive": ["Pos"], "negative": ["Neg"], "mitigation": ["Mit"]}
            ),
        ]

        agent = ADRGeneratorAgent(llm_client=mock_llm)

        trigger = ADRTriggerEvent(
            id="TRIG-001",
            title="Test ADR",
            category=ADRCategory.SECURITY,
            significance=ADRSignificance.HIGH,
            description="Test",
            context_summary="Test",
        )

        adr = await agent._generate_adr(trigger)

        assert adr.context == "LLM context"
        assert adr.decision == "LLM decision"
        assert len(adr.alternatives) == 1
        assert adr.alternatives[0]["title"] == "LLM Alt"

    @pytest.mark.asyncio
    async def test_generate_adr_llm_fallback_on_error(self):
        """Test ADR generation falls back when LLM fails."""
        from unittest.mock import AsyncMock

        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = Exception("LLM error")

        agent = ADRGeneratorAgent(llm_client=mock_llm)

        trigger = ADRTriggerEvent(
            id="TRIG-001",
            title="Test ADR",
            category=ADRCategory.SECURITY,
            significance=ADRSignificance.HIGH,
            description="Test",
            context_summary="Fallback context",
        )

        adr = await agent._generate_adr(trigger)

        # Should use fallback content
        assert "Fallback context" in adr.context
        assert adr.decision != ""  # Should have fallback decision


class TestADRGeneratorAgentFileOperations:
    """Tests for ADRGeneratorAgent file operations."""

    def test_save_adr(self, tmp_path):
        """Test saving ADR to filesystem."""
        agent = ADRGeneratorAgent(adr_directory=tmp_path)

        adr = ADRDocument(
            number=1,
            title="Test ADR",
            status="Proposed",
            date="2025-12-06",
            decision_makers="Test",
            context="Test context",
            decision="Test decision",
        )

        filepath = agent.save_adr(adr)

        assert filepath.exists()
        content = filepath.read_text()
        assert "# ADR-001: Test ADR" in content
        assert "Test context" in content

    def test_save_adr_creates_directory(self, tmp_path):
        """Test save_adr creates directory if not exists."""
        new_dir = tmp_path / "new_adr_dir"
        agent = ADRGeneratorAgent(adr_directory=new_dir)

        adr = ADRDocument(
            number=1,
            title="Test",
            status="Proposed",
            date="2025-12-06",
            decision_makers="Test",
            context="Context",
            decision="Decision",
        )

        filepath = agent.save_adr(adr)

        assert new_dir.exists()
        assert filepath.exists()

    def test_get_next_adr_number_empty_directory(self, tmp_path):
        """Test next ADR number for empty directory."""
        agent = ADRGeneratorAgent(adr_directory=tmp_path)

        assert agent._next_adr_number == 1

    def test_get_next_adr_number_with_existing(self, tmp_path):
        """Test next ADR number with existing ADRs."""
        # Create some existing ADR files
        (tmp_path / "ADR-001-first.md").write_text("# ADR-001")
        (tmp_path / "ADR-005-fifth.md").write_text("# ADR-005")
        (tmp_path / "ADR-003-third.md").write_text("# ADR-003")

        agent = ADRGeneratorAgent(adr_directory=tmp_path)

        assert agent._next_adr_number == 6

    def test_get_next_adr_number_nonexistent_directory(self, tmp_path):
        """Test next ADR number for nonexistent directory."""
        nonexistent = tmp_path / "does_not_exist"
        agent = ADRGeneratorAgent(adr_directory=nonexistent)

        assert agent._next_adr_number == 1

    def test_update_readme_index_no_readme(self, tmp_path):
        """Test update_readme_index when README doesn't exist."""
        agent = ADRGeneratorAgent(adr_directory=tmp_path)

        adr = ADRDocument(
            number=1,
            title="Test",
            status="Proposed",
            date="2025-12-06",
            decision_makers="Test",
            context="Context",
            decision="Decision",
        )

        # Should not raise error
        agent.update_readme_index([adr])

    def test_update_readme_index_no_table(self, tmp_path):
        """Test update_readme_index when README has no table."""
        readme = tmp_path / "README.md"
        readme.write_text("# Architecture Decisions\n\nNo table here.")

        agent = ADRGeneratorAgent(adr_directory=tmp_path)

        adr = ADRDocument(
            number=1,
            title="Test",
            status="Proposed",
            date="2025-12-06",
            decision_makers="Test",
            context="Context",
            decision="Decision",
        )

        # Should not raise error
        agent.update_readme_index([adr])


class TestADRDocumentEdgeCases:
    """Edge case tests for ADRDocument."""

    def test_to_markdown_empty_alternatives(self):
        """Test markdown with empty alternatives."""
        adr = ADRDocument(
            number=1,
            title="Test",
            status="Proposed",
            date="2025-12-06",
            decision_makers="Test",
            context="Context",
            decision="Decision",
            alternatives=[],
        )

        markdown = adr.to_markdown()

        assert "## Alternatives Considered" not in markdown

    def test_to_markdown_empty_consequences(self):
        """Test markdown with empty consequences."""
        adr = ADRDocument(
            number=1,
            title="Test",
            status="Proposed",
            date="2025-12-06",
            decision_makers="Test",
            context="Context",
            decision="Decision",
            consequences_positive=[],
            consequences_negative=[],
            consequences_mitigation=[],
        )

        markdown = adr.to_markdown()

        assert "## Consequences" in markdown
        assert "### Positive" not in markdown
        assert "### Negative" not in markdown

    def test_to_markdown_empty_references(self):
        """Test markdown with empty references."""
        adr = ADRDocument(
            number=1,
            title="Test",
            status="Proposed",
            date="2025-12-06",
            decision_makers="Test",
            context="Context",
            decision="Decision",
            references=[],
        )

        markdown = adr.to_markdown()

        assert "## References" not in markdown

    def test_to_markdown_alternative_without_pros_cons(self):
        """Test markdown with alternative missing pros/cons."""
        adr = ADRDocument(
            number=1,
            title="Test",
            status="Proposed",
            date="2025-12-06",
            decision_makers="Test",
            context="Context",
            decision="Decision",
            alternatives=[
                {"title": "Option A", "description": "No pros or cons"},
            ],
        )

        markdown = adr.to_markdown()

        assert "### Alternative 1: Option A" in markdown
        assert "No pros or cons" in markdown
        assert "**Pros:**" not in markdown
        assert "**Cons:**" not in markdown

    def test_get_filename_truncates_long_title(self):
        """Test filename truncates very long titles."""
        adr = ADRDocument(
            number=1,
            title="This is a very long title that exceeds fifty characters and should be truncated",
            status="Proposed",
            date="2025-12-06",
            decision_makers="Test",
            context="Context",
            decision="Decision",
        )

        filename = adr.get_filename()

        # Should be truncated (ADR-001- prefix + max 50 chars + .md)
        assert len(filename) < 70


class TestCreateADRGeneratorAgent:
    """Tests for create_adr_generator_agent factory function."""

    def test_create_with_mock(self):
        """Test factory creates agent with mock LLM."""
        from src.agents.adr_generator_agent import create_adr_generator_agent

        agent = create_adr_generator_agent(use_mock=True)

        assert agent.llm is not None
        assert hasattr(agent.llm, "generate")

    def test_create_with_custom_directory(self, tmp_path):
        """Test factory with custom ADR directory."""
        from src.agents.adr_generator_agent import create_adr_generator_agent

        agent = create_adr_generator_agent(use_mock=True, adr_directory=tmp_path)

        assert agent.adr_directory == tmp_path


class TestADRGeneratorAgentGenerateADRs:
    """Tests for generate_adrs method."""

    @pytest.mark.asyncio
    async def test_generate_multiple_adrs(self):
        """Test generating multiple ADRs from triggers."""
        agent = ADRGeneratorAgent()

        triggers = [
            ADRTriggerEvent(
                id="TRIG-001",
                title="First ADR",
                category=ADRCategory.SECURITY,
                significance=ADRSignificance.HIGH,
                description="First",
                context_summary="First context",
            ),
            ADRTriggerEvent(
                id="TRIG-002",
                title="Second ADR",
                category=ADRCategory.DEPENDENCY,
                significance=ADRSignificance.MEDIUM,
                description="Second",
                context_summary="Second context",
            ),
        ]

        adrs = await agent.generate_adrs(triggers)

        assert len(adrs) == 2
        assert adrs[0].title == "First ADR"
        assert adrs[1].title == "Second ADR"
        # Should have sequential numbers
        assert adrs[1].number == adrs[0].number + 1

    @pytest.mark.asyncio
    async def test_generate_adrs_empty_list(self):
        """Test generating ADRs with empty trigger list."""
        agent = ADRGeneratorAgent()

        adrs = await agent.generate_adrs([])

        assert len(adrs) == 0
