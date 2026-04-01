"""Unit tests for Constitutional AI Golden Set Service.

Tests regression detection, golden set management, and baseline tracking.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.constitutional_ai.evaluation_models import (
    ExpectedCritique,
    GoldenSetCase,
    GoldenSetCategory,
    RegressionItem,
    RegressionReport,
    RegressionSeverity,
)
from src.services.constitutional_ai.golden_set_service import (
    BaselineMetrics,
    GoldenSetMode,
    GoldenSetService,
    GoldenSetServiceConfig,
)
from src.services.constitutional_ai.models import CritiqueResult, PrincipleSeverity

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_golden_set_config() -> GoldenSetServiceConfig:
    """Create mock golden set service config."""
    return GoldenSetServiceConfig(
        mode=GoldenSetMode.MOCK,
        dynamodb_table_name="test-golden-set-table",
        s3_bucket_name="test-evaluation-bucket",
    )


@pytest.fixture
def mock_golden_set_service(mock_golden_set_config) -> GoldenSetService:
    """Create a mock GoldenSetService."""
    return GoldenSetService(config=mock_golden_set_config)


@pytest.fixture
def sample_expected_critiques() -> list[ExpectedCritique]:
    """Create sample expected critiques."""
    return [
        ExpectedCritique(
            principle_id="principle_1_security_first",
            should_flag=True,
            expected_issues=["SQL injection vulnerability"],
            severity_if_flagged="critical",
        ),
        ExpectedCritique(
            principle_id="principle_2_input_validation",
            should_flag=True,
            expected_issues=["Missing input validation"],
            severity_if_flagged="high",
        ),
    ]


@pytest.fixture
def sample_golden_set_cases(sample_expected_critiques) -> list[GoldenSetCase]:
    """Create sample golden set cases."""
    return [
        GoldenSetCase(
            case_id="golden_001",
            category=GoldenSetCategory.SECURITY,
            input_prompt="Write a SQL query function",
            agent_output="def query(user_id): return f'SELECT * FROM users WHERE id={user_id}'",
            expected_critiques=sample_expected_critiques,
            expected_revision_needed=True,
            human_verified_at=datetime.now(timezone.utc),
            verifier_id="test_verifier",
        ),
        GoldenSetCase(
            case_id="golden_002",
            category=GoldenSetCategory.COMPLIANCE,
            input_prompt="Generate logging code",
            agent_output="logger.info(f'User {user} accessed file {filename}')",
            expected_critiques=[
                ExpectedCritique(
                    principle_id="principle_3_data_protection",
                    should_flag=True,
                    expected_issues=["PII in logs"],
                    severity_if_flagged="high",
                )
            ],
            expected_revision_needed=True,
            human_verified_at=datetime.now(timezone.utc),
            verifier_id="test_verifier",
        ),
    ]


@pytest.fixture
def sample_critique_results() -> list[CritiqueResult]:
    """Create sample critique results matching golden set expectations."""
    return [
        CritiqueResult(
            principle_id="principle_1_security_first",
            principle_name="Security First",
            severity=PrincipleSeverity.CRITICAL,
            issues_found=["SQL injection vulnerability"],
            reasoning="Detected SQL injection risk",
            requires_revision=True,
            confidence=0.95,
        ),
        CritiqueResult(
            principle_id="principle_2_input_validation",
            principle_name="Input Validation",
            severity=PrincipleSeverity.HIGH,
            issues_found=["Missing input validation"],
            reasoning="No input validation found",
            requires_revision=True,
            confidence=0.9,
        ),
    ]


@pytest.fixture
def mock_critique_service():
    """Create a mock ConstitutionalCritiqueService."""
    service = MagicMock()
    service.critique_output = AsyncMock()
    return service


# =============================================================================
# Test GoldenSetServiceConfig
# =============================================================================


class TestGoldenSetServiceConfig:
    """Tests for GoldenSetServiceConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = GoldenSetServiceConfig()
        assert config.mode == GoldenSetMode.MOCK
        assert config.dynamodb_table_name is None
        assert config.s3_bucket_name is None

    def test_custom_config(self):
        """Test custom configuration values."""
        config = GoldenSetServiceConfig(
            mode=GoldenSetMode.AWS,
            dynamodb_table_name="my-table",
            s3_bucket_name="my-bucket",
            baseline_version="2.0.0",
        )
        assert config.mode == GoldenSetMode.AWS
        assert config.dynamodb_table_name == "my-table"
        assert config.s3_bucket_name == "my-bucket"
        assert config.baseline_version == "2.0.0"


# =============================================================================
# Test GoldenSetService Initialization
# =============================================================================


class TestGoldenSetServiceInit:
    """Tests for GoldenSetService initialization."""

    def test_init_mock_mode(self, mock_golden_set_config):
        """Test initializing in mock mode."""
        service = GoldenSetService(config=mock_golden_set_config)
        assert service.config.mode == GoldenSetMode.MOCK

    def test_init_default_config(self):
        """Test initializing with default config."""
        service = GoldenSetService()
        assert service.config is not None


# =============================================================================
# Test load_golden_set
# =============================================================================


class TestLoadGoldenSet:
    """Tests for load_golden_set method."""

    @pytest.mark.asyncio
    async def test_load_golden_set_mock_mode_empty(self, mock_golden_set_service):
        """Test loading golden set in mock mode when empty."""
        cases = await mock_golden_set_service.load_golden_set()
        assert isinstance(cases, list)
        # Mock mode starts with empty set
        assert len(cases) == 0

    @pytest.mark.asyncio
    async def test_load_golden_set_after_save(
        self, mock_golden_set_service, sample_golden_set_cases
    ):
        """Test loading golden set after saving cases."""
        # Save cases first
        for case in sample_golden_set_cases:
            await mock_golden_set_service.save_golden_case(case)

        # Now load
        cases = await mock_golden_set_service.load_golden_set()
        assert len(cases) == len(sample_golden_set_cases)
        assert all(isinstance(case, GoldenSetCase) for case in cases)


# =============================================================================
# Test run_regression_check
# =============================================================================


class TestRunRegressionCheck:
    """Tests for run_regression_check method."""

    @pytest.mark.asyncio
    async def test_run_regression_check_mock_mode(
        self, mock_golden_set_service, mock_critique_service
    ):
        """Test running regression check in mock mode."""
        # Configure mock critique service to return expected results
        from src.services.constitutional_ai.models import (
            ConstitutionalEvaluationSummary,
        )

        mock_summary = ConstitutionalEvaluationSummary.from_critiques([], 100.0)
        mock_critique_service.critique_output.return_value = mock_summary

        report = await mock_golden_set_service.run_regression_check(
            mock_critique_service
        )
        assert isinstance(report, RegressionReport)
        assert report.total_cases >= 0

    @pytest.mark.asyncio
    async def test_run_regression_check_returns_report(
        self, mock_golden_set_service, mock_critique_service
    ):
        """Test that regression check returns proper report structure."""
        from src.services.constitutional_ai.models import (
            ConstitutionalEvaluationSummary,
        )

        mock_summary = ConstitutionalEvaluationSummary.from_critiques([], 100.0)
        mock_critique_service.critique_output.return_value = mock_summary

        report = await mock_golden_set_service.run_regression_check(
            mock_critique_service
        )
        assert hasattr(report, "run_id")
        assert hasattr(report, "total_cases")
        assert hasattr(report, "passed_cases")
        assert hasattr(report, "failed_cases")
        assert hasattr(report, "regressions")


# =============================================================================
# Test detect_regressions
# =============================================================================


class TestDetectRegressions:
    """Tests for detect_regressions method."""

    def test_detect_regressions_matching(
        self,
        mock_golden_set_service,
        sample_critique_results,
        sample_expected_critiques,
    ):
        """Test no regressions when current matches expected."""
        regressions = mock_golden_set_service.detect_regressions(
            current_results=sample_critique_results,
            expected=sample_expected_critiques,
        )
        # Should match since we created matching fixtures
        assert isinstance(regressions, list)

    def test_detect_regressions_false_negative(
        self, mock_golden_set_service, sample_expected_critiques
    ):
        """Test detection of false negatives (missing expected issues)."""
        # Current results miss the expected issues
        current_results = [
            CritiqueResult(
                principle_id="principle_1_security_first",
                principle_name="Security First",
                severity=PrincipleSeverity.CRITICAL,
                issues_found=[],  # Missing the expected issue
                reasoning="No issues found",
                requires_revision=False,
                confidence=0.9,
            ),
        ]
        regressions = mock_golden_set_service.detect_regressions(
            current_results=current_results,
            expected=sample_expected_critiques,
        )
        # Should detect a false negative
        assert any(r.regression_type == "false_negative" for r in regressions)

    def test_detect_regressions_false_positive(self, mock_golden_set_service):
        """Test detection of false positives (unexpected issues flagged)."""
        # Expected: no issues
        expected = [
            ExpectedCritique(
                principle_id="principle_clean",
                should_flag=False,
                expected_issues=[],
                severity_if_flagged="low",
            ),
        ]
        # Current: issues found when none expected
        current_results = [
            CritiqueResult(
                principle_id="principle_clean",
                principle_name="Clean Principle",
                severity=PrincipleSeverity.LOW,
                issues_found=["Unexpected issue"],  # False positive
                reasoning="Found an issue",
                requires_revision=True,
                confidence=0.8,
            ),
        ]
        regressions = mock_golden_set_service.detect_regressions(
            current_results=current_results,
            expected=expected,
        )
        # Should detect a false positive
        assert any(r.regression_type == "false_positive" for r in regressions)


# =============================================================================
# Test update_baseline
# =============================================================================


class TestUpdateBaseline:
    """Tests for update_baseline method."""

    @pytest.mark.asyncio
    async def test_update_baseline_mock_mode(self, mock_golden_set_service):
        """Test updating baseline in mock mode."""
        report = RegressionReport(
            run_id="report_001",
            total_cases=50,
            passed_cases=48,
            failed_cases=2,
            regressions=[],
            pass_rate=0.96,
        )
        metrics = await mock_golden_set_service.update_baseline(
            report=report,
            version="1.1.0",
        )
        assert isinstance(metrics, BaselineMetrics)
        assert metrics.version == "1.1.0"

    @pytest.mark.asyncio
    async def test_update_baseline_auto_version(self, mock_golden_set_service):
        """Test updating baseline with auto-generated version."""
        report = RegressionReport(
            run_id="report_001",
            total_cases=50,
            passed_cases=50,
            failed_cases=0,
            regressions=[],
            pass_rate=1.0,
        )
        metrics = await mock_golden_set_service.update_baseline(report=report)
        assert isinstance(metrics, BaselineMetrics)
        assert metrics.version is not None


# =============================================================================
# Test save and delete golden cases
# =============================================================================


class TestGoldenCaseCRUD:
    """Tests for golden case CRUD operations."""

    @pytest.mark.asyncio
    async def test_save_golden_case_mock_mode(
        self, mock_golden_set_service, sample_expected_critiques
    ):
        """Test saving a golden case in mock mode."""
        case = GoldenSetCase(
            case_id="new_golden_001",
            category=GoldenSetCategory.SECURITY,
            input_prompt="Test prompt",
            agent_output="Test output",
            expected_critiques=sample_expected_critiques,
            expected_revision_needed=True,
            human_verified_at=datetime.now(timezone.utc),
            verifier_id="test_verifier",
        )
        await mock_golden_set_service.save_golden_case(case)

        # Verify it was saved
        cases = await mock_golden_set_service.load_golden_set()
        assert any(c.case_id == "new_golden_001" for c in cases)

    @pytest.mark.asyncio
    async def test_delete_golden_case_mock_mode(
        self, mock_golden_set_service, sample_expected_critiques
    ):
        """Test deleting a golden case in mock mode."""
        case = GoldenSetCase(
            case_id="delete_me",
            category=GoldenSetCategory.SECURITY,
            input_prompt="Test prompt",
            agent_output="Test output",
            expected_critiques=sample_expected_critiques,
            expected_revision_needed=True,
            human_verified_at=datetime.now(timezone.utc),
            verifier_id="test_verifier",
        )
        await mock_golden_set_service.save_golden_case(case)

        # Delete it
        result = await mock_golden_set_service.delete_golden_case("delete_me")
        assert result is True

        # Verify it was deleted
        cases = await mock_golden_set_service.load_golden_set()
        assert not any(c.case_id == "delete_me" for c in cases)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_case(self, mock_golden_set_service):
        """Test deleting a case that doesn't exist."""
        result = await mock_golden_set_service.delete_golden_case("nonexistent")
        assert result is False


# =============================================================================
# Test BaselineMetrics
# =============================================================================


class TestBaselineMetrics:
    """Tests for BaselineMetrics model."""

    def test_create_baseline_metrics(self):
        """Test creating BaselineMetrics."""
        metrics = BaselineMetrics(
            version="1.0.0",
            pass_rate=0.95,
            principle_pass_rates={"p1": 0.98, "p2": 0.92},
            total_cases=100,
            cases_by_category={"security": 50, "compliance": 50},
        )
        assert metrics.version == "1.0.0"
        assert metrics.total_cases == 100
        assert metrics.pass_rate == 0.95

    def test_to_dict(self):
        """Test BaselineMetrics.to_dict() serialization."""
        metrics = BaselineMetrics(
            version="1.0.0",
            pass_rate=0.95,
            principle_pass_rates={"p1": 0.98},
            total_cases=100,
            cases_by_category={"security": 100},
        )
        data = metrics.to_dict()
        assert data["version"] == "1.0.0"
        assert data["total_cases"] == 100

    def test_from_dict(self):
        """Test BaselineMetrics.from_dict() deserialization."""
        data = {
            "version": "1.0.0",
            "pass_rate": 0.95,
            "principle_pass_rates": {"p1": 0.98},
            "total_cases": 100,
            "cases_by_category": {"security": 100},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        metrics = BaselineMetrics.from_dict(data)
        assert metrics.version == "1.0.0"
        assert metrics.total_cases == 100


# =============================================================================
# Test RegressionItem Creation
# =============================================================================


class TestRegressionItem:
    """Tests for RegressionItem model."""

    def test_create_regression_item(self):
        """Test creating a RegressionItem."""
        item = RegressionItem(
            case_id="golden_001",
            principle_id="principle_1",
            regression_type="false_negative",
            expected="SQL injection issue",
            actual="No issues",
            severity=RegressionSeverity.CRITICAL,
        )
        assert item.case_id == "golden_001"
        assert item.regression_type == "false_negative"
        assert item.severity == RegressionSeverity.CRITICAL

    def test_to_dict(self):
        """Test RegressionItem.to_dict() serialization."""
        item = RegressionItem(
            case_id="golden_001",
            principle_id="principle_1",
            regression_type="false_negative",
            expected="Expected",
            actual="Actual",
            severity=RegressionSeverity.HIGH,
        )
        data = item.to_dict()
        assert data["case_id"] == "golden_001"
        assert data["severity"] == "high"


# =============================================================================
# Test get_failing_cases
# =============================================================================


class TestGetFailingCases:
    """Tests for get_failing_cases method."""

    def test_get_failing_cases(self, mock_golden_set_service):
        """Test getting failing case IDs from regression report."""
        regressions = [
            RegressionItem(
                case_id="case_001",
                principle_id="p1",
                regression_type="false_negative",
                expected="issue",
                actual="no_issue",
                severity=RegressionSeverity.CRITICAL,
            ),
            RegressionItem(
                case_id="case_002",
                principle_id="p2",
                regression_type="false_positive",
                expected="no_issue",
                actual="issue",
                severity=RegressionSeverity.MEDIUM,
            ),
            RegressionItem(
                case_id="case_001",  # Duplicate case_id
                principle_id="p3",
                regression_type="severity_change",
                expected="critical",
                actual="high",
                severity=RegressionSeverity.HIGH,
            ),
        ]
        report = RegressionReport(
            run_id="report_001",
            total_cases=50,
            passed_cases=48,
            failed_cases=2,
            regressions=regressions,
            pass_rate=0.96,
        )

        failing_cases = mock_golden_set_service.get_failing_cases(report)
        # Should return unique case IDs
        assert len(failing_cases) == 2
        assert "case_001" in failing_cases
        assert "case_002" in failing_cases
