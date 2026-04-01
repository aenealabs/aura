"""
Tests for adaptive_intelligence_agent.py

Comprehensive tests for the AdaptiveIntelligenceAgent which analyzes
threat intelligence reports and generates prioritized recommendations.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.adaptive_intelligence_agent import (
    AdaptiveIntelligenceAgent,
    AdaptiveRecommendation,
    BestPractice,
    EffortLevel,
    RecommendationType,
    RiskLevel,
)
from src.agents.threat_intelligence_agent import (
    ThreatCategory,
    ThreatIntelReport,
    ThreatSeverity,
)

# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest.fixture
def sample_threat_report() -> ThreatIntelReport:
    """Create a sample threat report for testing."""
    return ThreatIntelReport(
        id="threat-12345678",
        title="Critical CVE in requests library",
        category=ThreatCategory.CVE,
        severity=ThreatSeverity.CRITICAL,
        source="NVD",
        published_date=datetime.now(),
        description="Remote code execution vulnerability in requests library",
        affected_components=["requests==2.28.0"],
        cve_ids=["CVE-2024-1234"],
        cvss_score=9.8,
        recommended_actions=["Upgrade to requests>=2.30.0"],
        references=["https://nvd.nist.gov/vuln/detail/CVE-2024-1234"],
    )


@pytest.fixture
def internal_threat_report() -> ThreatIntelReport:
    """Create an internal threat report."""
    return ThreatIntelReport(
        id="internal-87654321",
        title="Unusual API access pattern detected",
        category=ThreatCategory.INTERNAL,
        severity=ThreatSeverity.HIGH,
        source="Internal Telemetry",
        published_date=datetime.now(),
        description="Multiple failed authentication attempts from unusual IP",
        affected_components=[],
        cve_ids=[],
        cvss_score=None,
    )


@pytest.fixture
def compliance_threat_report() -> ThreatIntelReport:
    """Create a compliance-related threat report."""
    return ThreatIntelReport(
        id="compliance-11111111",
        title="New CMMC requirement for logging",
        category=ThreatCategory.COMPLIANCE,
        severity=ThreatSeverity.MEDIUM,
        source="CMMC Update",
        published_date=datetime.now(),
        description="Updated logging requirements for CMMC Level 3",
        affected_components=[],
        cve_ids=[],
        cvss_score=None,
    )


# =============================================================================
# Test AdaptiveIntelligenceAgent Initialization
# =============================================================================


class TestAdaptiveIntelligenceAgentInit:
    """Tests for agent initialization."""

    def test_init_default(self):
        """Test default initialization."""
        agent = AdaptiveIntelligenceAgent()

        assert agent.llm is None
        assert agent.context_service is None
        assert agent.monitor is None
        assert len(agent._best_practices_db) > 0
        assert len(agent._compliance_mappings) > 0

    def test_init_with_llm_client(self):
        """Test initialization with LLM client."""
        mock_llm = MagicMock()
        agent = AdaptiveIntelligenceAgent(llm_client=mock_llm)

        assert agent.llm is mock_llm

    def test_init_with_context_service(self):
        """Test initialization with context service."""
        mock_context = MagicMock()
        agent = AdaptiveIntelligenceAgent(context_service=mock_context)

        assert agent.context_service is mock_context

    def test_init_with_monitor(self):
        """Test initialization with monitor."""
        mock_monitor = MagicMock()
        agent = AdaptiveIntelligenceAgent(monitor=mock_monitor)

        assert agent.monitor is mock_monitor


# =============================================================================
# Test Recommendation Type Determination
# =============================================================================


class TestRecommendationTypeDetermination:
    """Tests for _determine_recommendation_type."""

    def test_cve_with_components_returns_dependency_upgrade(self, sample_threat_report):
        """Test CVE with affected components returns DEPENDENCY_UPGRADE."""
        agent = AdaptiveIntelligenceAgent()
        rec_type = agent._determine_recommendation_type(sample_threat_report)

        assert rec_type == RecommendationType.DEPENDENCY_UPGRADE

    def test_cve_without_components_returns_security_patch(self):
        """Test CVE without components returns SECURITY_PATCH."""
        agent = AdaptiveIntelligenceAgent()
        report = ThreatIntelReport(
            id="test",
            title="CVE Test",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.HIGH,
            source="NVD",
            published_date=datetime.now(),
            description="Test",
            cve_ids=["CVE-2024-0001"],
            affected_components=[],  # No components
        )

        rec_type = agent._determine_recommendation_type(report)

        assert rec_type == RecommendationType.SECURITY_PATCH

    def test_compliance_category_returns_compliance_update(
        self, compliance_threat_report
    ):
        """Test compliance category returns COMPLIANCE_UPDATE."""
        agent = AdaptiveIntelligenceAgent()
        rec_type = agent._determine_recommendation_type(compliance_threat_report)

        assert rec_type == RecommendationType.COMPLIANCE_UPDATE

    def test_internal_category_returns_configuration_change(
        self, internal_threat_report
    ):
        """Test internal category returns CONFIGURATION_CHANGE."""
        agent = AdaptiveIntelligenceAgent()
        rec_type = agent._determine_recommendation_type(internal_threat_report)

        assert rec_type == RecommendationType.CONFIGURATION_CHANGE


# =============================================================================
# Test Risk Score Calculation
# =============================================================================


class TestRiskScoreCalculation:
    """Tests for risk score calculation."""

    def test_risk_score_with_cvss(self, sample_threat_report):
        """Test risk score calculation with CVSS score."""
        agent = AdaptiveIntelligenceAgent()
        impact = {
            "direct_dependency_match": True,
            "infrastructure_impact": False,
            "compliance_relevance": False,
        }

        score = agent._calculate_risk_score(sample_threat_report, impact)

        # Base 9.8 + 1.0 for direct match = capped at 10.0
        assert score == 10.0

    def test_risk_score_without_cvss(self, internal_threat_report):
        """Test risk score calculation without CVSS score."""
        agent = AdaptiveIntelligenceAgent()
        impact = {
            "direct_dependency_match": False,
            "infrastructure_impact": True,
            "compliance_relevance": True,
        }

        score = agent._calculate_risk_score(internal_threat_report, impact)

        # HIGH severity = 8.0 base + 0.5 infra + 0.5 compliance = 9.0
        assert 8.0 <= score <= 10.0

    def test_risk_score_minimum_is_zero(self):
        """Test risk score cannot go below 0."""
        agent = AdaptiveIntelligenceAgent()
        report = ThreatIntelReport(
            id="test",
            title="Low threat",
            category=ThreatCategory.ADVISORY,
            severity=ThreatSeverity.LOW,
            source="Test",
            published_date=datetime.now(),
            description="Test",
        )
        impact = {
            "direct_dependency_match": False,
            "infrastructure_impact": False,
            "compliance_relevance": False,
        }

        score = agent._calculate_risk_score(report, impact)

        assert score >= 0.0

    def test_risk_score_maximum_is_ten(self, sample_threat_report):
        """Test risk score is capped at 10.0."""
        agent = AdaptiveIntelligenceAgent()
        impact = {
            "direct_dependency_match": True,
            "infrastructure_impact": True,
            "compliance_relevance": True,
        }

        score = agent._calculate_risk_score(sample_threat_report, impact)

        assert score <= 10.0


# =============================================================================
# Test Risk Level Mapping
# =============================================================================


class TestRiskLevelMapping:
    """Tests for _score_to_risk_level."""

    def test_critical_risk_level(self):
        """Test critical risk level for high scores."""
        agent = AdaptiveIntelligenceAgent()

        assert agent._score_to_risk_level(9.5) == RiskLevel.CRITICAL
        assert agent._score_to_risk_level(10.0) == RiskLevel.CRITICAL

    def test_high_risk_level(self):
        """Test high risk level."""
        agent = AdaptiveIntelligenceAgent()

        assert agent._score_to_risk_level(7.5) == RiskLevel.HIGH
        assert agent._score_to_risk_level(8.9) == RiskLevel.HIGH

    def test_moderate_risk_level(self):
        """Test moderate risk level."""
        agent = AdaptiveIntelligenceAgent()

        assert agent._score_to_risk_level(5.0) == RiskLevel.MODERATE
        assert agent._score_to_risk_level(6.9) == RiskLevel.MODERATE

    def test_low_risk_level(self):
        """Test low risk level."""
        agent = AdaptiveIntelligenceAgent()

        assert agent._score_to_risk_level(3.0) == RiskLevel.LOW
        assert agent._score_to_risk_level(4.9) == RiskLevel.LOW

    def test_minimal_risk_level(self):
        """Test minimal risk level."""
        agent = AdaptiveIntelligenceAgent()

        assert agent._score_to_risk_level(1.0) == RiskLevel.MINIMAL
        assert agent._score_to_risk_level(2.9) == RiskLevel.MINIMAL


# =============================================================================
# Test Codebase Impact Assessment
# =============================================================================


class TestCodebaseImpactAssessment:
    """Tests for _assess_codebase_impact."""

    def test_impact_with_requests_component(self, sample_threat_report):
        """Test impact assessment finds requests-related files."""
        agent = AdaptiveIntelligenceAgent()
        sample_threat_report.affected_components = ["requests==2.28.0"]

        impact = agent._assess_codebase_impact(sample_threat_report)

        assert impact["requires_action"] is True
        assert len(impact["affected_files"]) > 0
        assert any(
            "requests" in f.lower() or "service" in f.lower()
            for f in impact["affected_files"]
        )

    def test_impact_critical_severity_requires_action(self):
        """Test that critical severity always requires action."""
        agent = AdaptiveIntelligenceAgent()
        report = ThreatIntelReport(
            id="test",
            title="Critical threat",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.CRITICAL,
            source="NVD",
            published_date=datetime.now(),
            description="Critical vulnerability",
            affected_components=[],  # No components
        )

        impact = agent._assess_codebase_impact(report)

        assert impact["requires_action"] is True

    def test_impact_low_severity_no_components(self):
        """Test low severity without components may not require action."""
        agent = AdaptiveIntelligenceAgent()
        report = ThreatIntelReport(
            id="test",
            title="Low threat",
            category=ThreatCategory.ADVISORY,
            severity=ThreatSeverity.LOW,
            source="Test",
            published_date=datetime.now(),
            description="Minor issue",
            affected_components=[],
        )

        impact = agent._assess_codebase_impact(report)

        # Low severity with no components doesn't require action
        assert impact["requires_action"] is False


# =============================================================================
# Test Infrastructure Impact Check
# =============================================================================


class TestInfrastructureImpact:
    """Tests for _check_infrastructure_impact."""

    def test_infrastructure_impact_with_eks(self):
        """Test infrastructure impact detection for EKS."""
        agent = AdaptiveIntelligenceAgent()
        report = ThreatIntelReport(
            id="test",
            title="EKS vulnerability discovered",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.HIGH,
            source="NVD",
            published_date=datetime.now(),
            description="Vulnerability in Kubernetes cluster",
            affected_components=[],
        )

        assert agent._check_infrastructure_impact(report) is True

    def test_infrastructure_impact_with_s3_in_description(self):
        """Test infrastructure impact for S3 mentioned in description."""
        agent = AdaptiveIntelligenceAgent()
        report = ThreatIntelReport(
            id="test",
            title="Data exposure vulnerability",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.HIGH,
            source="NVD",
            published_date=datetime.now(),
            description="S3 bucket misconfiguration allows public access",
            affected_components=[],
        )

        assert agent._check_infrastructure_impact(report) is True

    def test_no_infrastructure_impact(self):
        """Test no infrastructure impact for non-infra components."""
        agent = AdaptiveIntelligenceAgent()
        report = ThreatIntelReport(
            id="test",
            title="Library vulnerability",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.MEDIUM,
            source="NVD",
            published_date=datetime.now(),
            description="Generic library issue",
            affected_components=["pandas==1.5.0"],
        )

        assert agent._check_infrastructure_impact(report) is False


# =============================================================================
# Test Compliance Relevance Check
# =============================================================================


class TestComplianceRelevance:
    """Tests for _check_compliance_relevance."""

    def test_compliance_relevant_for_compliance_category(
        self, compliance_threat_report
    ):
        """Test compliance relevance for compliance category."""
        agent = AdaptiveIntelligenceAgent()

        assert agent._check_compliance_relevance(compliance_threat_report) is True

    def test_compliance_relevant_for_critical_severity(self, sample_threat_report):
        """Test compliance relevance for critical severity threats."""
        agent = AdaptiveIntelligenceAgent()

        assert agent._check_compliance_relevance(sample_threat_report) is True


# =============================================================================
# Test Best Practices Lookup
# =============================================================================


class TestBestPracticesLookup:
    """Tests for _find_best_practices."""

    def test_find_best_practices_with_matching_keywords(self):
        """Test finding best practices with matching keywords."""
        agent = AdaptiveIntelligenceAgent()
        # Create a report with keywords that match best practices
        report = ThreatIntelReport(
            id="test",
            title="SQL Injection vulnerability in database",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.HIGH,
            source="NVD",
            published_date=datetime.now(),
            description="Input validation vulnerability allows SQL injection attacks",
        )

        practices = agent._find_best_practices(report)

        # Result should be a list (may be empty if no keyword overlap)
        assert isinstance(practices, list)
        assert all(isinstance(p, BestPractice) for p in practices)

    def test_find_best_practices_returns_list(self, sample_threat_report):
        """Test that find_best_practices always returns a list."""
        agent = AdaptiveIntelligenceAgent()

        practices = agent._find_best_practices(sample_threat_report)

        assert isinstance(practices, list)

    def test_find_best_practices_for_internal(self, internal_threat_report):
        """Test finding best practices for internal threats."""
        agent = AdaptiveIntelligenceAgent()

        practices = agent._find_best_practices(internal_threat_report)

        # Should return relevant practices even for internal threats
        assert isinstance(practices, list)


# =============================================================================
# Test Compliance Impact Assessment
# =============================================================================


class TestComplianceImpactAssessment:
    """Tests for _assess_compliance_impact."""

    def test_compliance_impact_for_cve(self, sample_threat_report):
        """Test compliance impact for CVE threats."""
        agent = AdaptiveIntelligenceAgent()

        impact = agent._assess_compliance_impact(sample_threat_report)

        assert isinstance(impact, list)
        # Critical CVEs should have compliance implications
        assert len(impact) > 0

    def test_compliance_impact_for_compliance_threat(self, compliance_threat_report):
        """Test compliance impact for compliance category threats."""
        agent = AdaptiveIntelligenceAgent()

        impact = agent._assess_compliance_impact(compliance_threat_report)

        assert isinstance(impact, list)


# =============================================================================
# Test Implementation Steps Generation (Fallback)
# =============================================================================


class TestImplementationStepsFallback:
    """Tests for fallback implementation steps generation."""

    def test_dependency_upgrade_steps(self, sample_threat_report):
        """Test steps for dependency upgrade."""
        agent = AdaptiveIntelligenceAgent()
        impact = {"affected_files": ["requirements.txt"]}

        steps = agent._generate_implementation_steps_fallback(
            sample_threat_report, RecommendationType.DEPENDENCY_UPGRADE, impact
        )

        assert len(steps) >= 5
        assert any(
            "requirements.txt" in s.lower() or "dependency" in s.lower() for s in steps
        )
        assert any("HITL" in s for s in steps)

    def test_security_patch_steps(self, sample_threat_report):
        """Test steps for security patch."""
        agent = AdaptiveIntelligenceAgent()
        impact = {"affected_files": []}

        steps = agent._generate_implementation_steps_fallback(
            sample_threat_report, RecommendationType.SECURITY_PATCH, impact
        )

        assert len(steps) >= 5
        assert any("security" in s.lower() or "patch" in s.lower() for s in steps)

    def test_configuration_change_steps(self, internal_threat_report):
        """Test steps for configuration change."""
        agent = AdaptiveIntelligenceAgent()
        impact = {"affected_files": []}

        steps = agent._generate_implementation_steps_fallback(
            internal_threat_report, RecommendationType.CONFIGURATION_CHANGE, impact
        )

        assert len(steps) >= 5
        assert any(
            "cloudformation" in s.lower() or "kubernetes" in s.lower() for s in steps
        )


# =============================================================================
# Test Validation Criteria Generation (Fallback)
# =============================================================================


class TestValidationCriteriaFallback:
    """Tests for fallback validation criteria generation."""

    def test_dependency_upgrade_criteria(self):
        """Test criteria for dependency upgrade."""
        agent = AdaptiveIntelligenceAgent()

        criteria = agent._generate_validation_criteria_fallback(
            RecommendationType.DEPENDENCY_UPGRADE
        )

        assert len(criteria) >= 3
        assert any("test" in c.lower() for c in criteria)
        assert any(
            "dependency" in c.lower() or "conflict" in c.lower() for c in criteria
        )

    def test_security_patch_criteria(self):
        """Test criteria for security patch."""
        agent = AdaptiveIntelligenceAgent()

        criteria = agent._generate_validation_criteria_fallback(
            RecommendationType.SECURITY_PATCH
        )

        assert len(criteria) >= 3
        assert any(
            "vulnerability" in c.lower() or "security" in c.lower() for c in criteria
        )

    def test_compliance_update_criteria(self):
        """Test criteria for compliance update."""
        agent = AdaptiveIntelligenceAgent()

        criteria = agent._generate_validation_criteria_fallback(
            RecommendationType.COMPLIANCE_UPDATE
        )

        assert len(criteria) >= 3
        assert any("compliance" in c.lower() or "audit" in c.lower() for c in criteria)


# =============================================================================
# Test Rollback Plan Generation (Fallback)
# =============================================================================


class TestRollbackPlanFallback:
    """Tests for fallback rollback plan generation."""

    def test_dependency_upgrade_rollback(self):
        """Test rollback plan for dependency upgrade."""
        agent = AdaptiveIntelligenceAgent()
        impact = {"affected_files": ["requirements.txt"]}

        plan = agent._generate_rollback_plan_fallback(
            RecommendationType.DEPENDENCY_UPGRADE, impact
        )

        assert len(plan) > 0
        assert "revert" in plan.lower() or "requirements" in plan.lower()

    def test_configuration_change_rollback(self):
        """Test rollback plan for configuration change."""
        agent = AdaptiveIntelligenceAgent()
        impact = {"affected_files": ["deploy/cloudformation/eks.yaml"]}

        plan = agent._generate_rollback_plan_fallback(
            RecommendationType.CONFIGURATION_CHANGE, impact
        )

        assert len(plan) > 0
        assert "cloudformation" in plan.lower() or "rollback" in plan.lower()


# =============================================================================
# Test Rationale Generation (Fallback)
# =============================================================================


class TestRationaleFallback:
    """Tests for fallback rationale generation."""

    def test_rationale_for_critical_threat(self, sample_threat_report):
        """Test rationale for critical severity threat."""
        agent = AdaptiveIntelligenceAgent()
        impact = {"direct_dependency_match": True}

        rationale = agent._generate_rationale_fallback(sample_threat_report, impact)

        assert len(rationale) > 0
        assert "critical" in rationale.lower() or "immediate" in rationale.lower()

    def test_rationale_for_compliance_threat(self, compliance_threat_report):
        """Test rationale for compliance threat."""
        agent = AdaptiveIntelligenceAgent()
        impact = {"compliance_relevance": True}

        rationale = agent._generate_rationale_fallback(compliance_threat_report, impact)

        assert len(rationale) > 0


# =============================================================================
# Test Full Recommendation Generation
# =============================================================================


class TestRecommendationGeneration:
    """Tests for full recommendation generation."""

    @pytest.mark.asyncio
    async def test_generate_recommendation_without_llm(self, sample_threat_report):
        """Test generating recommendation without LLM."""
        agent = AdaptiveIntelligenceAgent()  # No LLM
        impact = {
            "requires_action": True,
            "affected_files": ["src/services/api.py"],
            "direct_dependency_match": True,
            "infrastructure_impact": False,
            "compliance_relevance": True,
        }

        recommendation = await agent._generate_recommendation(
            sample_threat_report, impact
        )

        assert isinstance(recommendation, AdaptiveRecommendation)
        assert recommendation.id.startswith("REC-")
        assert recommendation.severity == ThreatSeverity.CRITICAL
        assert len(recommendation.implementation_steps) > 0
        assert len(recommendation.validation_criteria) > 0
        assert recommendation.rollback_plan is not None

    @pytest.mark.asyncio
    async def test_generate_recommendation_with_llm(self, sample_threat_report):
        """Test generating recommendation with LLM."""
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(
            return_value='{"steps": ["Step 1", "Step 2", "Step 3"]}'
        )

        agent = AdaptiveIntelligenceAgent(llm_client=mock_llm)
        impact = {
            "requires_action": True,
            "affected_files": [],
            "direct_dependency_match": True,
            "infrastructure_impact": False,
            "compliance_relevance": False,
        }

        recommendation = await agent._generate_recommendation(
            sample_threat_report, impact
        )

        assert isinstance(recommendation, AdaptiveRecommendation)
        # LLM was called for generation
        assert mock_llm.generate.called

    @pytest.mark.asyncio
    async def test_generate_recommendation_llm_fallback_on_error(
        self, sample_threat_report
    ):
        """Test fallback when LLM fails."""
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(side_effect=Exception("LLM Error"))

        agent = AdaptiveIntelligenceAgent(llm_client=mock_llm)
        impact = {
            "requires_action": True,
            "affected_files": [],
            "direct_dependency_match": True,
            "infrastructure_impact": False,
            "compliance_relevance": False,
        }

        # Should not raise, should fallback
        recommendation = await agent._generate_recommendation(
            sample_threat_report, impact
        )

        assert isinstance(recommendation, AdaptiveRecommendation)


# =============================================================================
# Test Threat Analysis
# =============================================================================


class TestThreatAnalysis:
    """Tests for analyze_threats."""

    @pytest.mark.asyncio
    async def test_analyze_single_threat(self, sample_threat_report):
        """Test analyzing a single threat."""
        agent = AdaptiveIntelligenceAgent()

        recommendations = await agent.analyze_threats([sample_threat_report])

        # Critical threat with CVE should generate recommendation
        assert len(recommendations) >= 1

    @pytest.mark.asyncio
    async def test_analyze_multiple_threats(
        self, sample_threat_report, internal_threat_report
    ):
        """Test analyzing multiple threats."""
        agent = AdaptiveIntelligenceAgent()

        recommendations = await agent.analyze_threats(
            [sample_threat_report, internal_threat_report]
        )

        # Both threats should generate recommendations
        assert len(recommendations) >= 1

    @pytest.mark.asyncio
    async def test_analyze_low_priority_threat(self):
        """Test analyzing low priority threat."""
        agent = AdaptiveIntelligenceAgent()
        low_threat = ThreatIntelReport(
            id="low-threat",
            title="Minor advisory",
            category=ThreatCategory.ADVISORY,
            severity=ThreatSeverity.LOW,
            source="Advisory",
            published_date=datetime.now(),
            description="Minor issue with no known exploits",
            affected_components=[],
        )

        recommendations = await agent.analyze_threats([low_threat])

        # Low threat with no components may not require action
        assert isinstance(recommendations, list)

    @pytest.mark.asyncio
    async def test_analyze_empty_threats(self):
        """Test analyzing empty threat list."""
        agent = AdaptiveIntelligenceAgent()

        recommendations = await agent.analyze_threats([])

        assert recommendations == []


# =============================================================================
# Test Recommendation Prioritization
# =============================================================================


class TestRecommendationPrioritization:
    """Tests for _prioritize_recommendations."""

    @pytest.mark.asyncio
    async def test_prioritization_orders_by_risk(self):
        """Test that recommendations are ordered by risk score."""
        agent = AdaptiveIntelligenceAgent()

        # Create threats with different severities
        critical_threat = ThreatIntelReport(
            id="critical",
            title="Critical issue",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.CRITICAL,
            source="NVD",
            published_date=datetime.now(),
            description="Critical",
            cve_ids=["CVE-2024-0001"],
            cvss_score=9.8,
            affected_components=["requests"],
        )

        low_threat = ThreatIntelReport(
            id="low",
            title="Low issue",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.LOW,
            source="NVD",
            published_date=datetime.now(),
            description="Low",
            cve_ids=["CVE-2024-0002"],
            cvss_score=2.0,
            affected_components=["requests"],
        )

        # Analyze both - critical first to test ordering
        recommendations = await agent.analyze_threats([low_threat, critical_threat])

        if len(recommendations) >= 2:
            # First recommendation should have higher risk
            assert recommendations[0].risk_score >= recommendations[1].risk_score


# =============================================================================
# Test AdaptiveRecommendation Dataclass
# =============================================================================


class TestAdaptiveRecommendationDataclass:
    """Tests for AdaptiveRecommendation dataclass."""

    def test_to_dict(self, sample_threat_report):
        """Test recommendation serialization."""
        rec = AdaptiveRecommendation(
            id="REC-12345678",
            title="Test Recommendation",
            recommendation_type=RecommendationType.SECURITY_PATCH,
            severity=ThreatSeverity.HIGH,
            risk_score=8.5,
            risk_level=RiskLevel.HIGH,
            effort_level=EffortLevel.MEDIUM,
            description="Test description",
            rationale="Test rationale",
            affected_components=["component1"],
            affected_files=["file1.py"],
            implementation_steps=["Step 1", "Step 2"],
            best_practices=[],
            compliance_impact=["CMMC.AC-1"],
            rollback_plan="Rollback plan",
            validation_criteria=["Criterion 1"],
            source_threat=sample_threat_report,
        )

        result = rec.to_dict()

        assert result["id"] == "REC-12345678"
        assert result["title"] == "Test Recommendation"
        assert result["recommendation_type"] == "security_patch"
        assert result["severity"] == "high"
        assert result["risk_score"] == 8.5
        assert result["risk_level"] == "high"
        assert result["effort_level"] == "medium"
        assert len(result["implementation_steps"]) == 2


# =============================================================================
# Test LLM Response Parsing
# =============================================================================


class TestLLMResponseParsing:
    """Tests for LLM response parsing."""

    def test_parse_steps_response_valid_json(self):
        """Test parsing valid JSON response."""
        agent = AdaptiveIntelligenceAgent()
        response = '{"steps": ["Step 1", "Step 2", "Step 3"]}'

        steps = agent._parse_steps_response(response)

        assert steps == ["Step 1", "Step 2", "Step 3"]

    def test_parse_steps_response_with_prefix(self):
        """Test parsing JSON with text prefix."""
        agent = AdaptiveIntelligenceAgent()
        response = 'Here are the steps:\n{"steps": ["Step 1", "Step 2"]}'

        steps = agent._parse_steps_response(response)

        assert steps == ["Step 1", "Step 2"]

    def test_parse_steps_response_invalid_json(self):
        """Test parsing invalid JSON returns empty list."""
        agent = AdaptiveIntelligenceAgent()
        response = "This is not valid JSON"

        steps = agent._parse_steps_response(response)

        assert steps == []

    def test_parse_steps_response_missing_key(self):
        """Test parsing JSON without steps key."""
        agent = AdaptiveIntelligenceAgent()
        response = '{"other_key": ["value"]}'

        steps = agent._parse_steps_response(response)

        assert steps == []


# =============================================================================
# Test Effort Estimation
# =============================================================================


class TestEffortEstimation:
    """Tests for _estimate_effort."""

    def test_effort_dependency_upgrade_is_small(self, sample_threat_report):
        """Test dependency upgrade with few files has small effort."""
        agent = AdaptiveIntelligenceAgent()
        sample_threat_report.affected_components = ["requests==2.28.0"]
        impact = {"affected_files": ["requirements.txt"]}

        effort = agent._estimate_effort(sample_threat_report, impact)

        # 1 file = SMALL effort
        assert effort == EffortLevel.SMALL

    def test_effort_no_files_with_cve_is_trivial(self, sample_threat_report):
        """Test CVE with no affected files is trivial."""
        agent = AdaptiveIntelligenceAgent()
        impact = {"affected_files": []}

        effort = agent._estimate_effort(sample_threat_report, impact)

        # No files + CVE = TRIVIAL
        assert effort == EffortLevel.TRIVIAL

    def test_effort_many_files_is_large(self):
        """Test many affected files means large effort."""
        agent = AdaptiveIntelligenceAgent()
        report = ThreatIntelReport(
            id="test",
            title="Infrastructure issue",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.HIGH,
            source="NVD",
            published_date=datetime.now(),
            description="Major infrastructure change needed",
        )
        impact = {
            "affected_files": [
                "deploy/cloudformation/eks.yaml",
                "deploy/cloudformation/neptune.yaml",
                "deploy/kubernetes/deployment.yaml",
                "deploy/kubernetes/service.yaml",
                "deploy/cloudformation/iam.yaml",
                "deploy/cloudformation/vpc.yaml",
            ],
            "infrastructure_impact": True,
        }

        effort = agent._estimate_effort(report, impact)

        # 6 files = LARGE effort
        assert effort == EffortLevel.LARGE

    def test_effort_medium_file_count(self):
        """Test medium file count results in medium effort."""
        agent = AdaptiveIntelligenceAgent()
        report = ThreatIntelReport(
            id="test",
            title="Test issue",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.MEDIUM,
            source="NVD",
            published_date=datetime.now(),
            description="Test",
        )
        impact = {
            "affected_files": ["file1.py", "file2.py", "file3.py"],
        }

        effort = agent._estimate_effort(report, impact)

        # 3 files = MEDIUM effort
        assert effort == EffortLevel.MEDIUM


# =============================================================================
# Test Severity to Base Score
# =============================================================================


class TestSeverityToBaseScore:
    """Tests for _severity_to_base_score."""

    def test_critical_severity_score(self):
        """Test critical severity returns high score."""
        agent = AdaptiveIntelligenceAgent()

        score = agent._severity_to_base_score(ThreatSeverity.CRITICAL)

        assert score == 9.0

    def test_high_severity_score(self):
        """Test high severity returns appropriate score."""
        agent = AdaptiveIntelligenceAgent()

        score = agent._severity_to_base_score(ThreatSeverity.HIGH)

        assert score == 7.0

    def test_medium_severity_score(self):
        """Test medium severity returns appropriate score."""
        agent = AdaptiveIntelligenceAgent()

        score = agent._severity_to_base_score(ThreatSeverity.MEDIUM)

        assert score == 5.0

    def test_low_severity_score(self):
        """Test low severity returns low score."""
        agent = AdaptiveIntelligenceAgent()

        score = agent._severity_to_base_score(ThreatSeverity.LOW)

        assert score == 3.0

    def test_informational_severity_score(self):
        """Test informational severity returns minimal score."""
        agent = AdaptiveIntelligenceAgent()

        score = agent._severity_to_base_score(ThreatSeverity.INFORMATIONAL)

        assert score == 1.0
