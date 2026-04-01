"""
Tests for Security Agent Orchestrator.

Tests the unified security orchestration layer:
- Enums and data models
- PR security review workflow
- Security assessment workflow
- Risk calculation and correlation
"""

import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# Save original modules before mocking to prevent test pollution
_modules_to_save = ["structlog"]
_original_modules = {m: sys.modules.get(m) for m in _modules_to_save}

# Mock structlog before importing the module
sys.modules["structlog"] = MagicMock()

from src.services.security.security_agent_orchestrator import (
    ActionType,
    CorrelatedFinding,
    OverallRiskLevel,
    PRSecurityReview,
    SecurityAction,
    SecurityAgentOrchestrator,
    SecurityAssessment,
    SecurityInsight,
    SecurityWorkflowType,
    WorkflowResult,
    WorkflowStatus,
)

# Restore original modules to prevent pollution of other tests
for mod_name, original in _original_modules.items():
    if original is not None:
        sys.modules[mod_name] = original
    else:
        sys.modules.pop(mod_name, None)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_neptune():
    """Create mock Neptune client."""
    return MagicMock()


@pytest.fixture
def mock_opensearch():
    """Create mock OpenSearch client."""
    return MagicMock()


@pytest.fixture
def mock_llm():
    """Create mock LLM client."""
    return MagicMock()


@pytest.fixture
def mock_notifications():
    """Create mock notification service."""
    return MagicMock()


@pytest.fixture
def orchestrator(mock_neptune, mock_opensearch, mock_llm, mock_notifications):
    """Create orchestrator with mocked dependencies."""
    with patch("src.services.security.security_agent_orchestrator.PRSecurityScanner"):
        with patch(
            "src.services.security.security_agent_orchestrator.DynamicAttackPlanner"
        ):
            with patch(
                "src.services.security.security_agent_orchestrator.OrgStandardsValidator"
            ):
                return SecurityAgentOrchestrator(
                    neptune_client=mock_neptune,
                    opensearch_client=mock_opensearch,
                    llm_client=mock_llm,
                    notification_service=mock_notifications,
                )


# ============================================================================
# Enum Tests
# ============================================================================


class TestEnums:
    """Test enum definitions."""

    def test_security_workflow_type_values(self):
        """Test SecurityWorkflowType enum values."""
        assert SecurityWorkflowType.PR_REVIEW.value == "pr_review"
        assert SecurityWorkflowType.SECURITY_ASSESSMENT.value == "security_assessment"
        assert SecurityWorkflowType.COMPLIANCE_AUDIT.value == "compliance_audit"
        assert SecurityWorkflowType.INCIDENT_ANALYSIS.value == "incident_analysis"
        assert SecurityWorkflowType.THREAT_MODELING.value == "threat_modeling"
        assert (
            SecurityWorkflowType.CONTINUOUS_MONITORING.value == "continuous_monitoring"
        )

    def test_workflow_status_values(self):
        """Test WorkflowStatus enum values."""
        assert WorkflowStatus.PENDING.value == "pending"
        assert WorkflowStatus.RUNNING.value == "running"
        assert WorkflowStatus.COMPLETED.value == "completed"
        assert WorkflowStatus.FAILED.value == "failed"
        assert WorkflowStatus.CANCELLED.value == "cancelled"
        assert WorkflowStatus.REQUIRES_ACTION.value == "requires_action"

    def test_overall_risk_level_values(self):
        """Test OverallRiskLevel enum values."""
        assert OverallRiskLevel.CRITICAL.value == "critical"
        assert OverallRiskLevel.HIGH.value == "high"
        assert OverallRiskLevel.MEDIUM.value == "medium"
        assert OverallRiskLevel.LOW.value == "low"
        assert OverallRiskLevel.MINIMAL.value == "minimal"

    def test_action_type_values(self):
        """Test ActionType enum values."""
        assert ActionType.BLOCK_MERGE.value == "block_merge"
        assert ActionType.REQUEST_REVIEW.value == "request_review"
        assert ActionType.AUTO_FIX.value == "auto_fix"
        assert ActionType.CREATE_TICKET.value == "create_ticket"
        assert ActionType.NOTIFY_TEAM.value == "notify_team"
        assert ActionType.ESCALATE.value == "escalate"
        assert ActionType.REMEDIATE.value == "remediate"


# ============================================================================
# Data Model Tests
# ============================================================================


class TestSecurityAction:
    """Test SecurityAction dataclass."""

    def test_create_action(self):
        """Test creating a security action."""
        action = SecurityAction(
            action_id="action-123",
            action_type=ActionType.BLOCK_MERGE,
            priority=1,
            title="Block PR",
            description="Critical vulnerabilities detected",
            target="PR-456",
        )
        assert action.action_id == "action-123"
        assert action.action_type == ActionType.BLOCK_MERGE
        assert action.priority == 1
        assert action.auto_executable is False

    def test_action_with_all_fields(self):
        """Test action with all optional fields."""
        action = SecurityAction(
            action_id="action-789",
            action_type=ActionType.REQUEST_REVIEW,
            priority=2,
            title="Request Security Review",
            description="High risk changes",
            target="PR-789",
            auto_executable=True,
            deadline=datetime.now(timezone.utc),
            assigned_to="security-team",
            metadata={"severity": "high"},
        )
        assert action.auto_executable is True
        assert action.assigned_to == "security-team"


class TestSecurityInsight:
    """Test SecurityInsight dataclass."""

    def test_create_insight(self):
        """Test creating a security insight."""
        insight = SecurityInsight(
            insight_id="insight-123",
            category="secrets",
            title="Secrets Detected",
            description="Found API keys in code",
            severity=OverallRiskLevel.CRITICAL,
            evidence=["AWS_SECRET_KEY", "GITHUB_TOKEN"],
            recommendations=["Remove secrets", "Use secrets manager"],
        )
        assert insight.insight_id == "insight-123"
        assert insight.severity == OverallRiskLevel.CRITICAL
        assert len(insight.evidence) == 2
        assert len(insight.recommendations) == 2

    def test_insight_with_related_findings(self):
        """Test insight with related findings."""
        insight = SecurityInsight(
            insight_id="insight-456",
            category="dependencies",
            title="Vulnerable Dependencies",
            description="Found outdated packages",
            severity=OverallRiskLevel.HIGH,
            evidence=["lodash@4.17.15"],
            recommendations=["Update packages"],
            related_findings=["finding-1", "finding-2"],
        )
        assert len(insight.related_findings) == 2


class TestCorrelatedFinding:
    """Test CorrelatedFinding dataclass."""

    def test_create_correlated_finding(self):
        """Test creating a correlated finding."""
        finding = CorrelatedFinding(
            correlation_id="corr-123",
            title="SQL Injection + Insecure Input",
            description="Multiple tools detected injection vulnerability",
            severity=OverallRiskLevel.HIGH,
            sources=["security_scan", "standards_validation"],
            finding_ids=["scan-1", "val-1"],
        )
        assert finding.correlation_id == "corr-123"
        assert len(finding.sources) == 2
        assert finding.confidence == 1.0

    def test_correlated_finding_with_mitre(self):
        """Test correlated finding with MITRE techniques."""
        finding = CorrelatedFinding(
            correlation_id="corr-456",
            title="Privilege Escalation Risk",
            description="Detected potential privilege escalation",
            severity=OverallRiskLevel.CRITICAL,
            sources=["attack_planner"],
            finding_ids=["attack-1"],
            attack_paths=["path-1", "path-2"],
            mitre_techniques=["T1548", "T1068"],
            confidence=0.85,
        )
        assert len(finding.mitre_techniques) == 2
        assert finding.confidence == 0.85


class TestWorkflowResult:
    """Test WorkflowResult dataclass."""

    def test_create_workflow_result(self):
        """Test creating a workflow result."""
        result = WorkflowResult(
            workflow_id="wf-123",
            workflow_type=SecurityWorkflowType.PR_REVIEW,
            status=WorkflowStatus.COMPLETED,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            duration_seconds=5.5,
        )
        assert result.workflow_id == "wf-123"
        assert result.status == WorkflowStatus.COMPLETED
        assert result.overall_risk == OverallRiskLevel.MINIMAL
        assert result.can_proceed is True

    def test_workflow_result_with_blocking_issues(self):
        """Test workflow result with blocking issues."""
        result = WorkflowResult(
            workflow_id="wf-456",
            workflow_type=SecurityWorkflowType.SECURITY_ASSESSMENT,
            status=WorkflowStatus.COMPLETED,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            duration_seconds=10.0,
            overall_risk=OverallRiskLevel.CRITICAL,
            can_proceed=False,
            blocking_issues=["Critical vulnerability", "Exposed secrets"],
        )
        assert result.can_proceed is False
        assert len(result.blocking_issues) == 2


class TestPRSecurityReview:
    """Test PRSecurityReview dataclass."""

    def test_create_pr_review(self):
        """Test creating a PR security review."""
        review = PRSecurityReview(
            review_id="rev-123",
            pr_id="PR-456",
            repository="org/repo",
            status=WorkflowStatus.COMPLETED,
            overall_risk=OverallRiskLevel.LOW,
            vulnerability_scan=None,
            standards_validation=None,
            risk_score=15.0,
            correlated_findings=[],
            insights=[],
            actions=[],
            approve=True,
            request_changes=False,
            blocking_reasons=[],
            pr_comment="# Security Review\n\nPassed!",
            detailed_report="Detailed report content",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            duration_seconds=3.5,
        )
        assert review.approve is True
        assert review.request_changes is False
        assert review.overall_risk == OverallRiskLevel.LOW


class TestSecurityAssessment:
    """Test SecurityAssessment dataclass."""

    def test_create_assessment(self):
        """Test creating a security assessment."""
        assessment = SecurityAssessment(
            assessment_id="assess-123",
            name="Q4 Security Review",
            scope="Production environment",
            status=WorkflowStatus.COMPLETED,
            attack_surface=None,
            threat_model=None,
            attack_simulations=[],
            remediation_plans=[],
            overall_risk=OverallRiskLevel.MEDIUM,
            risk_score=45.0,
            critical_findings=2,
            high_findings=5,
            executive_summary="Summary content",
            technical_report="Technical report",
            mitre_mapping={},
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        assert assessment.critical_findings == 2
        assert assessment.high_findings == 5
        assert assessment.overall_risk == OverallRiskLevel.MEDIUM


# ============================================================================
# Orchestrator Initialization Tests
# ============================================================================


class TestOrchestratorInitialization:
    """Test orchestrator initialization."""

    def test_default_initialization(self, orchestrator):
        """Test default initialization."""
        assert orchestrator._workflows == {}
        assert orchestrator._pr_scanner is not None
        assert orchestrator._attack_planner is not None
        assert orchestrator._standards_validator is not None

    def test_component_properties(self, orchestrator):
        """Test component accessor properties."""
        assert orchestrator.pr_scanner is not None
        assert orchestrator.attack_planner is not None
        assert orchestrator.standards_validator is not None


# ============================================================================
# Risk Mapping Tests
# ============================================================================


class TestRiskMapping:
    """Test risk mapping utilities."""

    def test_map_to_overall_risk(self, orchestrator):
        """Test mapping severity strings to risk levels."""
        assert (
            orchestrator._map_to_overall_risk("critical") == OverallRiskLevel.CRITICAL
        )
        assert orchestrator._map_to_overall_risk("high") == OverallRiskLevel.HIGH
        assert orchestrator._map_to_overall_risk("medium") == OverallRiskLevel.MEDIUM
        assert orchestrator._map_to_overall_risk("low") == OverallRiskLevel.LOW
        assert orchestrator._map_to_overall_risk("info") == OverallRiskLevel.MINIMAL

    def test_map_to_overall_risk_standards(self, orchestrator):
        """Test mapping standards severity strings."""
        assert orchestrator._map_to_overall_risk("blocker") == OverallRiskLevel.CRITICAL
        assert orchestrator._map_to_overall_risk("major") == OverallRiskLevel.HIGH
        assert orchestrator._map_to_overall_risk("minor") == OverallRiskLevel.LOW

    def test_map_to_overall_risk_unknown(self, orchestrator):
        """Test mapping unknown severity defaults to medium."""
        assert orchestrator._map_to_overall_risk("unknown") == OverallRiskLevel.MEDIUM

    def test_map_risk_score_to_level(self, orchestrator):
        """Test mapping risk scores to levels."""
        assert orchestrator._map_risk_score_to_level(80) == OverallRiskLevel.CRITICAL
        assert orchestrator._map_risk_score_to_level(70) == OverallRiskLevel.CRITICAL
        assert orchestrator._map_risk_score_to_level(60) == OverallRiskLevel.HIGH
        assert orchestrator._map_risk_score_to_level(50) == OverallRiskLevel.HIGH
        assert orchestrator._map_risk_score_to_level(40) == OverallRiskLevel.MEDIUM
        assert orchestrator._map_risk_score_to_level(20) == OverallRiskLevel.LOW
        assert orchestrator._map_risk_score_to_level(5) == OverallRiskLevel.MINIMAL


# ============================================================================
# PR Risk Calculation Tests
# ============================================================================


class TestPRRiskCalculation:
    """Test PR risk calculation."""

    def test_calculate_pr_risk_no_results(self, orchestrator):
        """Test risk calculation with no results."""
        score, level = orchestrator._calculate_pr_risk(None, None)
        assert score == 0.0
        assert level == OverallRiskLevel.MINIMAL

    def test_calculate_pr_risk_scan_only(self, orchestrator):
        """Test risk calculation with scan only."""
        mock_scan = MagicMock()
        mock_scan.summary.risk_score = 60

        score, level = orchestrator._calculate_pr_risk(mock_scan, None)
        assert score == 36.0  # 60 * 0.6
        assert level == OverallRiskLevel.MEDIUM

    def test_calculate_pr_risk_validation_only(self, orchestrator):
        """Test risk calculation with validation only."""
        mock_validation = MagicMock()
        mock_validation.blocker_count = 0
        mock_validation.critical_count = 2
        mock_validation.major_count = 3
        mock_validation.minor_count = 5

        score, level = orchestrator._calculate_pr_risk(None, mock_validation)
        # Score: (0*25 + 2*15 + 3*5 + 5*1) * 0.4 = (30 + 15 + 5) * 0.4 = 20
        assert score == 20.0
        assert level == OverallRiskLevel.LOW

    def test_calculate_pr_risk_combined(self, orchestrator):
        """Test combined risk calculation."""
        mock_scan = MagicMock()
        mock_scan.summary.risk_score = 50

        mock_validation = MagicMock()
        mock_validation.blocker_count = 1
        mock_validation.critical_count = 0
        mock_validation.major_count = 0
        mock_validation.minor_count = 0

        score, level = orchestrator._calculate_pr_risk(mock_scan, mock_validation)
        # Scan: 50 * 0.6 = 30
        # Validation: (1*25) * 0.4 = 10
        # Total: 40
        assert score == 40.0
        assert level == OverallRiskLevel.MEDIUM


# ============================================================================
# Approval Decision Tests
# ============================================================================


class TestApprovalDecision:
    """Test approval decision logic."""

    def test_approve_no_issues(self, orchestrator):
        """Test approval when no issues found."""
        mock_scan = MagicMock()
        mock_scan.summary.block_merge = False
        mock_scan.secret_findings = []

        mock_validation = MagicMock()
        mock_validation.can_merge = True

        actions = []

        approve, request_changes, blocking = orchestrator._make_approval_decision(
            mock_scan, mock_validation, actions
        )

        assert approve is True
        assert request_changes is False
        assert len(blocking) == 0

    def test_block_on_secrets(self, orchestrator):
        """Test blocking when secrets detected."""
        mock_scan = MagicMock()
        mock_scan.summary.block_merge = False
        mock_scan.secret_findings = [MagicMock()]  # Has secrets

        mock_validation = MagicMock()
        mock_validation.can_merge = True

        actions = []

        approve, request_changes, blocking = orchestrator._make_approval_decision(
            mock_scan, mock_validation, actions
        )

        assert approve is False
        assert request_changes is True
        assert "Secrets detected in code" in blocking

    def test_block_on_scan_block(self, orchestrator):
        """Test blocking when scan requests block."""
        mock_scan = MagicMock()
        mock_scan.summary.block_merge = True
        mock_scan.secret_findings = []

        mock_validation = MagicMock()
        mock_validation.can_merge = True

        actions = []

        approve, request_changes, blocking = orchestrator._make_approval_decision(
            mock_scan, mock_validation, actions
        )

        assert approve is False
        assert request_changes is True
        assert "Security scan detected blocking issues" in blocking

    def test_block_on_validation_fail(self, orchestrator):
        """Test blocking when validation fails."""
        mock_scan = MagicMock()
        mock_scan.summary.block_merge = False
        mock_scan.secret_findings = []

        mock_validation = MagicMock()
        mock_validation.can_merge = False

        actions = []

        approve, request_changes, blocking = orchestrator._make_approval_decision(
            mock_scan, mock_validation, actions
        )

        assert approve is False
        assert request_changes is True
        assert "Standards validation has blocking violations" in blocking

    def test_block_on_block_action(self, orchestrator):
        """Test blocking when block action present."""
        mock_scan = MagicMock()
        mock_scan.summary.block_merge = False
        mock_scan.secret_findings = []

        mock_validation = MagicMock()
        mock_validation.can_merge = True

        actions = [
            SecurityAction(
                action_id="action-1",
                action_type=ActionType.BLOCK_MERGE,
                priority=1,
                title="Block",
                description="Block merge",
                target="PR-1",
            )
        ]

        approve, request_changes, blocking = orchestrator._make_approval_decision(
            mock_scan, mock_validation, actions
        )

        assert approve is False
        assert request_changes is True
        assert "Critical security issues require resolution" in blocking


# ============================================================================
# PR Action Determination Tests
# ============================================================================


class TestPRActionDetermination:
    """Test PR action determination."""

    def test_actions_for_critical_risk(self, orchestrator):
        """Test actions for critical risk."""
        mock_pr = MagicMock()
        mock_pr.pr_id = "PR-123"

        actions = orchestrator._determine_pr_actions(
            None, None, OverallRiskLevel.CRITICAL, mock_pr
        )

        action_types = [a.action_type for a in actions]
        assert ActionType.BLOCK_MERGE in action_types
        assert ActionType.REQUEST_REVIEW in action_types

    def test_actions_for_secrets(self, orchestrator):
        """Test actions when secrets detected."""
        mock_scan = MagicMock()
        mock_scan.secret_findings = [MagicMock(), MagicMock()]
        mock_scan.findings = []

        mock_pr = MagicMock()
        mock_pr.pr_id = "PR-456"

        actions = orchestrator._determine_pr_actions(
            mock_scan, None, OverallRiskLevel.HIGH, mock_pr
        )

        action_types = [a.action_type for a in actions]
        assert ActionType.ESCALATE in action_types

    def test_actions_sorted_by_priority(self, orchestrator):
        """Test actions are sorted by priority."""
        mock_scan = MagicMock()
        mock_scan.secret_findings = [MagicMock()]
        mock_scan.findings = [MagicMock()]
        mock_scan.findings[0].severity = MagicMock()
        mock_scan.findings[0].severity.value = "HIGH"

        mock_pr = MagicMock()
        mock_pr.pr_id = "PR-789"

        actions = orchestrator._determine_pr_actions(
            mock_scan, None, OverallRiskLevel.CRITICAL, mock_pr
        )

        priorities = [a.priority for a in actions]
        assert priorities == sorted(priorities)


# ============================================================================
# Finding Correlation Tests
# ============================================================================


class TestFindingCorrelation:
    """Test finding correlation logic."""

    def test_correlate_no_findings(self, orchestrator):
        """Test correlation with no findings."""
        correlated = orchestrator._correlate_pr_findings(None, None)
        assert correlated == []

    def test_correlate_single_source(self, orchestrator):
        """Test correlation with single source doesn't correlate."""
        mock_scan = MagicMock()
        mock_finding = MagicMock()
        mock_finding.finding_id = "f-1"
        mock_finding.location.file_path = "src/main.py"
        mock_finding.location.start_line = 10
        mock_finding.title = "SQL Injection"
        mock_finding.severity.value = "high"
        mock_finding.category.value = "security"
        mock_scan.findings = [mock_finding]

        correlated = orchestrator._correlate_pr_findings(mock_scan, None)
        # Single source doesn't create correlations
        assert correlated == []

    def test_correlate_nearby_lines(self, orchestrator):
        """Test correlation of findings on nearby lines."""
        mock_scan = MagicMock()
        mock_scan_finding = MagicMock()
        mock_scan_finding.finding_id = "f-1"
        mock_scan_finding.location.file_path = "src/main.py"
        mock_scan_finding.location.start_line = 10
        mock_scan_finding.title = "SQL Injection"
        mock_scan_finding.severity.value = "high"
        mock_scan_finding.category.value = "security"
        mock_scan.findings = [mock_scan_finding]

        mock_validation = MagicMock()
        mock_violation = MagicMock()
        mock_violation.violation_id = "v-1"
        mock_violation.location.file_path = "src/main.py"
        mock_violation.location.start_line = 12  # Within 10 lines
        mock_violation.rule.name = "input-validation"
        mock_violation.severity.value = "major"
        mock_violation.rule.category.value = "security"
        mock_validation.violations = [mock_violation]

        correlated = orchestrator._correlate_pr_findings(mock_scan, mock_validation)
        assert len(correlated) >= 1
        assert "security_scan" in correlated[0].sources
        assert "standards_validation" in correlated[0].sources


# ============================================================================
# Insight Generation Tests
# ============================================================================


class TestInsightGeneration:
    """Test insight generation."""

    def test_generate_no_insights(self, orchestrator):
        """Test generating insights with no findings."""
        insights = orchestrator._generate_pr_insights(None, None, [])
        assert insights == []

    def test_generate_secrets_insight(self, orchestrator):
        """Test generating insight for secrets."""
        mock_scan = MagicMock()
        mock_secret = MagicMock()
        mock_secret.secret_type = "AWS_ACCESS_KEY"
        mock_scan.secret_findings = [mock_secret]
        mock_scan.dependency_findings = []

        insights = orchestrator._generate_pr_insights(mock_scan, None, [])

        assert len(insights) >= 1
        secrets_insight = [i for i in insights if i.category == "secrets"][0]
        assert secrets_insight.severity == OverallRiskLevel.CRITICAL

    def test_generate_dependency_insight(self, orchestrator):
        """Test generating insight for vulnerable dependencies."""
        mock_scan = MagicMock()
        mock_scan.secret_findings = []
        mock_dep = MagicMock()
        mock_dep.name = "lodash"
        mock_dep.vulnerabilities = [MagicMock()]
        mock_scan.dependency_findings = [mock_dep]

        insights = orchestrator._generate_pr_insights(mock_scan, None, [])

        assert len(insights) >= 1
        dep_insight = [i for i in insights if i.category == "dependencies"][0]
        assert dep_insight.severity == OverallRiskLevel.HIGH

    def test_generate_correlation_insight(self, orchestrator):
        """Test generating insight for correlated findings."""
        correlated = [
            CorrelatedFinding(
                correlation_id="c-1",
                title="Correlated Issue",
                description="Multiple tools detected",
                severity=OverallRiskLevel.HIGH,
                sources=["scan", "validation"],
                finding_ids=["f-1", "v-1"],
            )
        ]

        insights = orchestrator._generate_pr_insights(None, None, correlated)

        assert len(insights) >= 1
        corr_insight = [i for i in insights if i.category == "correlation"][0]
        assert corr_insight.severity == OverallRiskLevel.MEDIUM


# ============================================================================
# Comment and Report Generation Tests
# ============================================================================


class TestReportGeneration:
    """Test report generation."""

    def test_generate_pr_comment_no_issues(self, orchestrator):
        """Test generating PR comment with no issues."""
        comment = orchestrator._generate_pr_comment(
            None, None, OverallRiskLevel.MINIMAL, [], []
        )

        assert "Security Review Results" in comment
        assert "MINIMAL" in comment
        assert "No blocking security issues found" in comment

    def test_generate_pr_comment_critical(self, orchestrator):
        """Test generating PR comment for critical issues."""
        actions = [
            SecurityAction(
                action_id="a-1",
                action_type=ActionType.BLOCK_MERGE,
                priority=1,
                title="Block Merge",
                description="Critical issues",
                target="PR-1",
            )
        ]

        comment = orchestrator._generate_pr_comment(
            None, None, OverallRiskLevel.CRITICAL, [], actions
        )

        assert "CRITICAL" in comment
        assert "cannot be merged" in comment

    def test_generate_pr_comment_with_scan_results(self, orchestrator):
        """Test generating PR comment with scan results."""
        mock_scan = MagicMock()
        mock_scan.summary.scan_passed = True
        mock_scan.summary.critical_count = 0
        mock_scan.summary.high_count = 2
        mock_scan.summary.secrets_detected = 0
        mock_scan.summary.vulnerable_dependencies = 1
        mock_scan.summary.iac_issues = 0

        comment = orchestrator._generate_pr_comment(
            mock_scan, None, OverallRiskLevel.MEDIUM, [], []
        )

        assert "Security Scan" in comment
        assert "High Vulnerabilities | 2" in comment

    def test_generate_detailed_report(self, orchestrator):
        """Test generating detailed report."""
        insights = [
            SecurityInsight(
                insight_id="i-1",
                category="test",
                title="Test Insight",
                description="Test description",
                severity=OverallRiskLevel.HIGH,
                evidence=["evidence-1"],
                recommendations=["rec-1"],
            )
        ]

        report = orchestrator._generate_detailed_report(None, None, insights, [])

        assert "Detailed Security Analysis Report" in report
        assert "Test Insight" in report
        assert "HIGH" in report
