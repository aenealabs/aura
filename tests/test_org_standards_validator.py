"""
Tests for Organization Standards Validator Service

Tests for custom coding standards validation and security policy compliance.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

# ==================== Enum Tests ====================


class TestStandardCategory:
    """Tests for StandardCategory enum."""

    def test_all_categories(self):
        """Test all standard categories exist."""
        from src.services.security.org_standards_validator import StandardCategory

        assert StandardCategory.CODING == "coding"
        assert StandardCategory.SECURITY == "security"
        assert StandardCategory.ARCHITECTURE == "architecture"
        assert StandardCategory.NAMING == "naming"
        assert StandardCategory.DOCUMENTATION == "documentation"
        assert StandardCategory.DEPENDENCY == "dependency"
        assert StandardCategory.API == "api"
        assert StandardCategory.TESTING == "testing"
        assert StandardCategory.COMPLIANCE == "compliance"
        assert StandardCategory.ACCESSIBILITY == "accessibility"


class TestViolationSeverity:
    """Tests for ViolationSeverity enum."""

    def test_all_severities(self):
        """Test all violation severities exist."""
        from src.services.security.org_standards_validator import ViolationSeverity

        assert ViolationSeverity.BLOCKER == "blocker"
        assert ViolationSeverity.CRITICAL == "critical"
        assert ViolationSeverity.MAJOR == "major"
        assert ViolationSeverity.MINOR == "minor"
        assert ViolationSeverity.INFO == "info"


class TestValidationStatus:
    """Tests for ValidationStatus enum."""

    def test_all_statuses(self):
        """Test all validation statuses exist."""
        from src.services.security.org_standards_validator import ValidationStatus

        assert ValidationStatus.PASSED == "passed"
        assert ValidationStatus.FAILED == "failed"
        assert ValidationStatus.WARNING == "warning"
        assert ValidationStatus.SKIPPED == "skipped"
        assert ValidationStatus.ERROR == "error"


class TestEnforcementLevel:
    """Tests for EnforcementLevel enum."""

    def test_all_levels(self):
        """Test all enforcement levels exist."""
        from src.services.security.org_standards_validator import EnforcementLevel

        assert EnforcementLevel.STRICT == "strict"
        assert EnforcementLevel.STANDARD == "standard"
        assert EnforcementLevel.ADVISORY == "advisory"
        assert EnforcementLevel.OFF == "off"


# ==================== Dataclass Tests ====================


class TestCodeLocation:
    """Tests for CodeLocation dataclass."""

    def test_creation(self):
        """Test CodeLocation creation."""
        from src.services.security.org_standards_validator import CodeLocation

        location = CodeLocation(
            file_path="src/main.py",
            start_line=10,
            end_line=15,
            start_column=5,
            end_column=20,
            snippet="def foo():",
        )
        assert location.file_path == "src/main.py"
        assert location.start_line == 10
        assert location.end_line == 15
        assert location.snippet == "def foo():"

    def test_minimal_creation(self):
        """Test CodeLocation with minimal required fields."""
        from src.services.security.org_standards_validator import CodeLocation

        location = CodeLocation(file_path="test.py", start_line=1, end_line=5)
        assert location.start_column is None
        assert location.end_column is None
        assert location.snippet == ""


class TestStandardRule:
    """Tests for StandardRule dataclass."""

    def test_creation(self):
        """Test StandardRule creation."""
        from src.services.security.org_standards_validator import (
            StandardCategory,
            StandardRule,
            ViolationSeverity,
        )

        rule = StandardRule(
            rule_id="TEST-001",
            name="Test Rule",
            description="A test rule for testing",
            category=StandardCategory.CODING,
            severity=ViolationSeverity.MAJOR,
            rationale="Testing purposes",
        )
        assert rule.rule_id == "TEST-001"
        assert rule.name == "Test Rule"
        assert rule.category == StandardCategory.CODING
        assert rule.severity == ViolationSeverity.MAJOR
        assert rule.enabled is True  # Default

    def test_full_creation(self):
        """Test StandardRule with all fields."""
        from src.services.security.org_standards_validator import (
            StandardCategory,
            StandardRule,
            ViolationSeverity,
        )

        rule = StandardRule(
            rule_id="SEC-001",
            name="No Hardcoded Secrets",
            description="Prevent hardcoded secrets",
            category=StandardCategory.SECURITY,
            severity=ViolationSeverity.BLOCKER,
            rationale="Secrets in code are dangerous",
            pattern=r"password\s*=",
            check_function="check_secrets",
            languages=["python", "javascript"],
            file_patterns=["*.py", "*.js"],
            auto_fixable=False,
            fix_suggestion="Use environment variables",
            references=["CWE-798"],
            tags=["security", "secrets"],
            enabled=True,
        )
        assert rule.pattern == r"password\s*="
        assert "python" in rule.languages
        assert "security" in rule.tags


class TestStandardViolation:
    """Tests for StandardViolation dataclass."""

    def test_creation(self):
        """Test StandardViolation creation."""
        from src.services.security.org_standards_validator import (
            CodeLocation,
            StandardCategory,
            StandardRule,
            StandardViolation,
            ViolationSeverity,
        )

        rule = StandardRule(
            rule_id="TEST-001",
            name="Test Rule",
            description="Test",
            category=StandardCategory.CODING,
            severity=ViolationSeverity.MINOR,
            rationale="Test",
        )
        location = CodeLocation(file_path="test.py", start_line=10, end_line=10)
        violation = StandardViolation(
            violation_id="v-001",
            rule=rule,
            location=location,
            message="Test violation",
            severity=ViolationSeverity.MINOR,
        )
        assert violation.violation_id == "v-001"
        assert violation.rule.rule_id == "TEST-001"
        assert violation.message == "Test violation"


class TestStandardsPolicy:
    """Tests for StandardsPolicy dataclass."""

    def test_creation(self):
        """Test StandardsPolicy creation."""
        from src.services.security.org_standards_validator import (
            EnforcementLevel,
            StandardCategory,
            StandardRule,
            StandardsPolicy,
            ViolationSeverity,
        )

        rule = StandardRule(
            rule_id="TEST-001",
            name="Test",
            description="Test",
            category=StandardCategory.CODING,
            severity=ViolationSeverity.MINOR,
            rationale="Test",
        )
        policy = StandardsPolicy(
            policy_id="policy-001",
            name="Test Policy",
            description="A test policy",
            version="1.0.0",
            rules=[rule],
            enforcement_level=EnforcementLevel.STANDARD,
        )
        assert policy.policy_id == "policy-001"
        assert policy.name == "Test Policy"
        assert len(policy.rules) == 1
        assert policy.enforcement_level == EnforcementLevel.STANDARD


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_creation(self):
        """Test ValidationResult creation."""
        from src.services.security.org_standards_validator import (
            ValidationResult,
            ValidationStatus,
        )

        result = ValidationResult(
            rule_id="TEST-001",
            status=ValidationStatus.PASSED,
            violations=[],
            files_checked=10,
            execution_time_ms=100.5,
        )
        assert result.rule_id == "TEST-001"
        assert result.status == ValidationStatus.PASSED
        assert result.files_checked == 10


class TestValidationReport:
    """Tests for ValidationReport dataclass."""

    def test_creation(self):
        """Test ValidationReport creation."""
        from src.services.security.org_standards_validator import (
            ValidationReport,
            ValidationStatus,
        )

        report = ValidationReport(
            report_id="report-001",
            policy_name="Test Policy",
            status=ValidationStatus.PASSED,
            total_files=50,
            files_with_violations=5,
            total_violations=10,
            blocker_count=0,
            critical_count=2,
            major_count=5,
            minor_count=3,
            info_count=0,
            results=[],
            violations=[],
            summary_by_category={"coding": 5, "security": 5},
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            duration_seconds=5.5,
            can_merge=True,
        )
        assert report.report_id == "report-001"
        assert report.total_violations == 10
        assert report.can_merge is True


class TestComplianceMapping:
    """Tests for ComplianceMapping dataclass."""

    def test_creation(self):
        """Test ComplianceMapping creation."""
        from src.services.security.org_standards_validator import ComplianceMapping

        mapping = ComplianceMapping(
            framework="SOC2",
            control_id="CC6.1",
            control_name="Logical Access Controls",
            rule_ids=["SEC-001", "SEC-002"],
            evidence_description="Rules enforce access controls",
        )
        assert mapping.framework == "SOC2"
        assert mapping.control_id == "CC6.1"
        assert len(mapping.rule_ids) == 2


class TestExemptionRequest:
    """Tests for ExemptionRequest dataclass."""

    def test_creation(self):
        """Test ExemptionRequest creation."""
        from src.services.security.org_standards_validator import ExemptionRequest

        request = ExemptionRequest(
            request_id="req-001",
            rule_id="CODE-001",
            file_patterns=["tests/*"],
            justification="Test files need longer functions",
            requested_by="developer@example.com",
        )
        assert request.request_id == "req-001"
        assert request.status == "pending"
        assert request.approved_by is None


# ==================== Built-in Rules Tests ====================


class TestBuiltInRules:
    """Tests for built-in standard rules."""

    def test_coding_standards_exist(self):
        """Test CODING_STANDARDS list exists."""
        from src.services.security.org_standards_validator import CODING_STANDARDS

        assert len(CODING_STANDARDS) > 0
        # Check first rule
        assert CODING_STANDARDS[0].rule_id == "CODE-001"
        assert CODING_STANDARDS[0].name == "Function Length"

    def test_security_standards_exist(self):
        """Test SECURITY_STANDARDS list exists."""
        from src.services.security.org_standards_validator import SECURITY_STANDARDS

        assert len(SECURITY_STANDARDS) > 0
        # Check for hardcoded secrets rule
        rule_ids = [r.rule_id for r in SECURITY_STANDARDS]
        assert "SEC-001" in rule_ids


# ==================== Validator Class Tests ====================


class TestOrgStandardsValidatorInit:
    """Tests for OrgStandardsValidator initialization."""

    def test_basic_initialization(self):
        """Test basic initialization without clients."""
        from src.services.security.org_standards_validator import OrgStandardsValidator

        validator = OrgStandardsValidator()
        assert validator._neptune is None
        assert validator._opensearch is None
        assert validator._llm is None
        assert len(validator._rules) > 0  # Built-in rules loaded

    def test_initialization_with_clients(self):
        """Test initialization with client mocks."""
        from src.services.security.org_standards_validator import OrgStandardsValidator

        neptune = MagicMock()
        opensearch = MagicMock()
        llm = MagicMock()

        validator = OrgStandardsValidator(
            neptune_client=neptune, opensearch_client=opensearch, llm_client=llm
        )
        assert validator._neptune == neptune
        assert validator._opensearch == opensearch
        assert validator._llm == llm

    def test_builtin_rules_loaded(self):
        """Test built-in rules are loaded on init."""
        from src.services.security.org_standards_validator import OrgStandardsValidator

        validator = OrgStandardsValidator()

        # Check some expected rules exist
        assert "CODE-001" in validator._rules
        assert "SEC-001" in validator._rules

    def test_check_functions_registered(self):
        """Test custom check functions are registered."""
        from src.services.security.org_standards_validator import OrgStandardsValidator

        validator = OrgStandardsValidator()

        assert "check_function_length" in validator._check_functions
        assert "check_cyclomatic_complexity" in validator._check_functions
        assert "check_circular_imports" in validator._check_functions


class TestPolicyManagement:
    """Tests for policy management methods."""

    def test_create_policy(self):
        """Test creating a new policy."""
        from src.services.security.org_standards_validator import (
            EnforcementLevel,
            OrgStandardsValidator,
        )

        validator = OrgStandardsValidator()
        policy = validator.create_policy(
            name="Test Policy",
            description="A test policy",
            rule_ids=["CODE-001", "SEC-001"],
            enforcement_level=EnforcementLevel.STRICT,
        )

        assert policy.name == "Test Policy"
        assert policy.enforcement_level == EnforcementLevel.STRICT
        assert len(policy.rules) == 2
        assert policy.policy_id in validator._policies

    def test_create_policy_with_invalid_rule_ids(self):
        """Test creating policy with some invalid rule IDs."""
        from src.services.security.org_standards_validator import OrgStandardsValidator

        validator = OrgStandardsValidator()
        policy = validator.create_policy(
            name="Partial Policy",
            description="Policy with some invalid rules",
            rule_ids=["CODE-001", "INVALID-999", "SEC-001"],
        )

        # Should only include valid rules
        rule_ids = [r.rule_id for r in policy.rules]
        assert "CODE-001" in rule_ids
        assert "SEC-001" in rule_ids
        assert "INVALID-999" not in rule_ids

    def test_get_default_policy(self):
        """Test getting the default policy."""
        from src.services.security.org_standards_validator import OrgStandardsValidator

        validator = OrgStandardsValidator()
        policy = validator.get_default_policy()

        assert policy.policy_id == "default"
        assert policy.name == "Default Organization Standards"
        assert len(policy.rules) > 0  # Should have all built-in rules

    def test_add_custom_rule(self):
        """Test adding a custom rule."""
        from src.services.security.org_standards_validator import (
            OrgStandardsValidator,
            StandardCategory,
            StandardRule,
            ViolationSeverity,
        )

        validator = OrgStandardsValidator()
        custom_rule = StandardRule(
            rule_id="CUSTOM-001",
            name="Custom Rule",
            description="A custom organization rule",
            category=StandardCategory.CODING,
            severity=ViolationSeverity.MINOR,
            rationale="Organization-specific requirement",
        )

        validator.add_custom_rule(custom_rule)

        assert "CUSTOM-001" in validator._rules
        assert validator._rules["CUSTOM-001"].name == "Custom Rule"


class TestValidation:
    """Tests for validation methods."""

    @pytest.mark.asyncio
    async def test_validate_basic(self):
        """Test basic validation."""
        from src.services.security.org_standards_validator import (
            EnforcementLevel,
            OrgStandardsValidator,
        )

        validator = OrgStandardsValidator()

        # Create simple policy with one pattern-based rule
        policy = validator.create_policy(
            name="Simple Test",
            description="Simple test policy",
            rule_ids=["CODE-003"],  # Magic numbers rule
            enforcement_level=EnforcementLevel.ADVISORY,
        )

        # Validate empty file list
        report = await validator.validate(file_contents={}, policy=policy)

        assert report is not None
        assert report.policy_name == "Simple Test"

    @pytest.mark.asyncio
    async def test_validate_with_default_policy(self):
        """Test validation with default policy."""
        from src.services.security.org_standards_validator import OrgStandardsValidator

        validator = OrgStandardsValidator()

        report = await validator.validate(file_contents={"test.py": "x = 100\n"})

        assert report is not None
        assert report.policy_name == "Default Organization Standards"


class TestComplianceMappings:
    """Tests for compliance mapping functionality."""

    def test_add_compliance_mapping(self):
        """Test adding a compliance mapping."""
        from src.services.security.org_standards_validator import OrgStandardsValidator

        validator = OrgStandardsValidator()
        mapping = validator.add_compliance_mapping(
            framework="SOC2",
            control_id="CC6.1",
            control_name="Logical Access Controls",
            rule_ids=["SEC-001"],
            evidence_description="Detects hardcoded secrets",
        )

        assert mapping is not None
        assert mapping.framework == "SOC2"
        assert len(validator._compliance_mappings) == 1


# ==================== Edge Cases ====================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_policy(self):
        """Test creating a policy with no rules."""
        from src.services.security.org_standards_validator import OrgStandardsValidator

        validator = OrgStandardsValidator()
        policy = validator.create_policy(
            name="Empty Policy", description="Policy with no rules", rule_ids=[]
        )

        assert policy.name == "Empty Policy"
        assert len(policy.rules) == 0

    def test_policy_with_exemptions(self):
        """Test policy with file exemptions."""
        from src.services.security.org_standards_validator import OrgStandardsValidator

        validator = OrgStandardsValidator()
        policy = validator.create_policy(
            name="With Exemptions",
            description="Policy with exemptions",
            rule_ids=["CODE-001"],
            exemptions=["tests/*", "fixtures/*"],
        )

        assert len(policy.exemptions) == 2
        assert "tests/*" in policy.exemptions

    @pytest.mark.asyncio
    async def test_validate_with_no_policy_uses_default(self):
        """Test validation without policy uses default."""
        from src.services.security.org_standards_validator import OrgStandardsValidator

        validator = OrgStandardsValidator()

        report = await validator.validate(file_contents={})

        # Should use default policy
        assert report.policy_name == "Default Organization Standards"

    def test_rule_with_regex_pattern(self):
        """Test rule with regex pattern."""
        from src.services.security.org_standards_validator import (
            OrgStandardsValidator,
            StandardCategory,
            StandardRule,
            ViolationSeverity,
        )

        validator = OrgStandardsValidator()

        # Add rule with complex regex
        rule = StandardRule(
            rule_id="REGEX-001",
            name="No Print Statements",
            description="Disallow print statements in production code",
            category=StandardCategory.CODING,
            severity=ViolationSeverity.MINOR,
            rationale="Use logging instead",
            pattern=r"\bprint\s*\(",
        )

        validator.add_custom_rule(rule)
        assert validator._rules["REGEX-001"].pattern == r"\bprint\s*\("


class TestExemptionRequests:
    """Tests for exemption request handling."""

    def test_exemption_request_creation(self):
        """Test creating exemption request."""
        from datetime import datetime, timedelta, timezone

        from src.services.security.org_standards_validator import ExemptionRequest

        request = ExemptionRequest(
            request_id="exempt-001",
            rule_id="CODE-001",
            file_patterns=["legacy/*"],
            justification="Legacy code pending refactor",
            requested_by="dev@example.com",
            approved_by="lead@example.com",
            expires_at=datetime.now(timezone.utc) + timedelta(days=90),
            status="approved",
        )

        assert request.status == "approved"
        assert request.approved_by == "lead@example.com"
        assert request.expires_at is not None
