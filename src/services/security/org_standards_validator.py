"""
Organization Standards Validator Service - AWS Security Agent Parity

Implements comprehensive organizational security standards enforcement:
- Custom coding standards validation
- Security policy compliance checking
- Architecture pattern enforcement
- Naming convention validation
- Documentation requirements checking
- Dependency policy enforcement
- API design standards validation

Reference: ADR-030 Section 5.2 Security Agent Components
"""

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================


class StandardCategory(str, Enum):
    """Categories of organizational standards."""

    CODING = "coding"
    SECURITY = "security"
    ARCHITECTURE = "architecture"
    NAMING = "naming"
    DOCUMENTATION = "documentation"
    DEPENDENCY = "dependency"
    API = "api"
    TESTING = "testing"
    COMPLIANCE = "compliance"
    ACCESSIBILITY = "accessibility"


class ViolationSeverity(str, Enum):
    """Severity of standard violations."""

    BLOCKER = "blocker"  # Must fix before merge
    CRITICAL = "critical"  # Should fix before merge
    MAJOR = "major"  # Should fix soon
    MINOR = "minor"  # Nice to fix
    INFO = "info"  # Informational


class ValidationStatus(str, Enum):
    """Status of a validation run."""

    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"
    ERROR = "error"


class EnforcementLevel(str, Enum):
    """How strictly to enforce standards."""

    STRICT = "strict"  # All violations are blockers
    STANDARD = "standard"  # Follow defined severity
    ADVISORY = "advisory"  # All violations are warnings
    OFF = "off"  # Don't enforce


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class CodeLocation:
    """Location of a violation in code."""

    file_path: str
    start_line: int
    end_line: int
    start_column: int | None = None
    end_column: int | None = None
    snippet: str = ""


@dataclass
class StandardRule:
    """A single standard rule definition."""

    rule_id: str
    name: str
    description: str
    category: StandardCategory
    severity: ViolationSeverity
    rationale: str
    pattern: str | None = None  # Regex pattern for detection
    check_function: str | None = None  # Name of custom check function
    languages: list[str] = field(default_factory=list)
    file_patterns: list[str] = field(default_factory=list)
    auto_fixable: bool = False
    fix_suggestion: str = ""
    references: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    enabled: bool = True


@dataclass
class StandardViolation:
    """A detected standard violation."""

    violation_id: str
    rule: StandardRule
    location: CodeLocation
    message: str
    severity: ViolationSeverity
    suggested_fix: str | None = None
    auto_fix: str | None = None  # Automated fix if available
    context: dict[str, Any] = field(default_factory=dict)
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class StandardsPolicy:
    """A collection of standards rules forming a policy."""

    policy_id: str
    name: str
    description: str
    version: str
    rules: list[StandardRule]
    enforcement_level: EnforcementLevel = EnforcementLevel.STANDARD
    applies_to: list[str] = field(default_factory=list)  # Repo patterns
    exemptions: list[str] = field(default_factory=list)  # File patterns to exempt
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ValidationResult:
    """Result of validating against a single rule."""

    rule_id: str
    status: ValidationStatus
    violations: list[StandardViolation]
    files_checked: int
    execution_time_ms: float


@dataclass
class ValidationReport:
    """Complete validation report."""

    report_id: str
    policy_name: str
    status: ValidationStatus
    total_files: int
    files_with_violations: int
    total_violations: int
    blocker_count: int
    critical_count: int
    major_count: int
    minor_count: int
    info_count: int
    results: list[ValidationResult]
    violations: list[StandardViolation]
    summary_by_category: dict[str, int]
    started_at: datetime
    completed_at: datetime
    duration_seconds: float
    can_merge: bool


@dataclass
class ComplianceMapping:
    """Maps standards to compliance frameworks."""

    framework: str  # SOC2, PCI-DSS, HIPAA, etc.
    control_id: str  # Control identifier
    control_name: str
    rule_ids: list[str]  # Rules that satisfy this control
    evidence_description: str


@dataclass
class ExemptionRequest:
    """Request to exempt from a standard."""

    request_id: str
    rule_id: str
    file_patterns: list[str]
    justification: str
    requested_by: str
    approved_by: str | None = None
    expires_at: datetime | None = None
    status: str = "pending"  # pending, approved, denied, expired
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# Built-in Standard Rules
# =============================================================================

CODING_STANDARDS = [
    StandardRule(
        rule_id="CODE-001",
        name="Function Length",
        description="Functions should not exceed 50 lines of code",
        category=StandardCategory.CODING,
        severity=ViolationSeverity.MAJOR,
        rationale="Long functions are harder to understand, test, and maintain",
        pattern=None,
        check_function="check_function_length",
        languages=["python", "javascript", "typescript", "java"],
        auto_fixable=False,
        fix_suggestion="Consider breaking this function into smaller, focused functions",
        tags=["maintainability", "readability"],
    ),
    StandardRule(
        rule_id="CODE-002",
        name="Cyclomatic Complexity",
        description="Functions should have cyclomatic complexity <= 10",
        category=StandardCategory.CODING,
        severity=ViolationSeverity.MAJOR,
        rationale="High complexity makes code harder to test and maintain",
        check_function="check_cyclomatic_complexity",
        languages=["python", "javascript", "typescript"],
        tags=["complexity", "testability"],
    ),
    StandardRule(
        rule_id="CODE-003",
        name="Magic Numbers",
        description="Avoid magic numbers; use named constants",
        category=StandardCategory.CODING,
        severity=ViolationSeverity.MINOR,
        rationale="Named constants improve code readability and maintainability",
        pattern=r"(?<!['\"\w])\b(?!0\b|1\b|2\b|-1\b)\d{2,}\b(?!['\"])",
        languages=["python", "javascript", "typescript", "java"],
        auto_fixable=False,
        fix_suggestion="Extract this number to a named constant",
        tags=["readability"],
    ),
    StandardRule(
        rule_id="CODE-004",
        name="TODO Comments",
        description="TODO comments should include ticket reference",
        category=StandardCategory.CODING,
        severity=ViolationSeverity.MINOR,
        rationale="TODOs without tickets often get forgotten",
        pattern=r"#\s*TODO(?!.*(?:JIRA|TICKET|ISSUE|#\d+))",
        languages=["python"],
        fix_suggestion="Add ticket reference: TODO(TICKET-123): description",
        tags=["documentation", "tracking"],
    ),
    StandardRule(
        rule_id="CODE-005",
        name="Commented Out Code",
        description="Remove commented out code blocks",
        category=StandardCategory.CODING,
        severity=ViolationSeverity.MINOR,
        rationale="Commented code adds noise; use version control instead",
        pattern=r"^\s*#.*(?:def |class |import |from |return |if |for |while )",
        languages=["python"],
        fix_suggestion="Delete commented code; it's preserved in version control",
        tags=["cleanliness"],
    ),
]

SECURITY_STANDARDS = [
    StandardRule(
        rule_id="SEC-001",
        name="Hardcoded Secrets",
        description="No hardcoded passwords, API keys, or tokens",
        category=StandardCategory.SECURITY,
        severity=ViolationSeverity.BLOCKER,
        rationale="Hardcoded secrets can be extracted from source code",
        pattern=r"(password|secret|api_key|token|credential)\s*=\s*['\"][^'\"]{8,}['\"]",
        auto_fixable=False,
        fix_suggestion="Use environment variables or a secrets manager",
        references=["CWE-798", "OWASP-A07"],
        tags=["secrets", "credentials"],
    ),
    StandardRule(
        rule_id="SEC-002",
        name="SQL String Formatting",
        description="Use parameterized queries instead of string formatting",
        category=StandardCategory.SECURITY,
        severity=ViolationSeverity.BLOCKER,
        rationale="String formatting in SQL queries can lead to SQL injection",
        pattern=r"execute\s*\(\s*f['\"]|execute\s*\([^)]*%|execute\s*\([^)]*\.format\(",
        languages=["python"],
        fix_suggestion="Use parameterized queries: cursor.execute(sql, params)",
        references=["CWE-89", "OWASP-A03"],
        tags=["injection", "database"],
    ),
    StandardRule(
        rule_id="SEC-003",
        name="Unsafe Deserialization",
        description="Avoid pickle.loads and yaml.load without safe_load",
        category=StandardCategory.SECURITY,
        severity=ViolationSeverity.CRITICAL,
        rationale="Unsafe deserialization can lead to remote code execution",
        pattern=r"pickle\.loads?\(|yaml\.load\([^)]*(?!Loader=|safe)",
        languages=["python"],
        fix_suggestion="Use yaml.safe_load() or json for deserialization",
        references=["CWE-502"],
        tags=["deserialization", "rce"],
    ),
    StandardRule(
        rule_id="SEC-004",
        name="Shell Injection",
        description="Avoid shell=True in subprocess calls",
        category=StandardCategory.SECURITY,
        severity=ViolationSeverity.CRITICAL,
        rationale="shell=True with user input can lead to command injection",
        pattern=r"subprocess\.(call|run|Popen)\([^)]*shell\s*=\s*True",
        languages=["python"],
        fix_suggestion="Use subprocess with shell=False and pass args as list",
        references=["CWE-78"],
        tags=["injection", "command"],
    ),
    StandardRule(
        rule_id="SEC-005",
        name="Debug Mode in Production",
        description="Debug mode should not be enabled in production code",
        category=StandardCategory.SECURITY,
        severity=ViolationSeverity.CRITICAL,
        rationale="Debug mode can expose sensitive information",
        pattern=r"DEBUG\s*=\s*True|app\.debug\s*=\s*True|debug=True",
        languages=["python"],
        fix_suggestion="Use environment variables to control debug mode",
        references=["CWE-489"],
        tags=["configuration"],
    ),
    StandardRule(
        rule_id="SEC-006",
        name="Insecure Random",
        description="Use secrets module for security-sensitive randomness",
        category=StandardCategory.SECURITY,
        severity=ViolationSeverity.MAJOR,
        rationale="random module is not cryptographically secure",
        pattern=r"random\.(choice|randint|random)\(.*(?:token|password|secret|key)",
        languages=["python"],
        fix_suggestion="Use secrets.token_hex() or secrets.token_urlsafe()",
        references=["CWE-330"],
        tags=["cryptography"],
    ),
]

ARCHITECTURE_STANDARDS = [
    StandardRule(
        rule_id="ARCH-001",
        name="Layer Separation",
        description="Controllers should not directly access database models",
        category=StandardCategory.ARCHITECTURE,
        severity=ViolationSeverity.MAJOR,
        rationale="Direct DB access in controllers violates separation of concerns",
        pattern=r"(?:Controller|View|Handler).*(?:session\.query|execute|\.objects\.)",
        languages=["python"],
        fix_suggestion="Use a service layer to access data",
        tags=["layering", "clean-architecture"],
    ),
    StandardRule(
        rule_id="ARCH-002",
        name="Circular Imports",
        description="Avoid circular imports between modules",
        category=StandardCategory.ARCHITECTURE,
        severity=ViolationSeverity.MAJOR,
        rationale="Circular imports cause hard-to-debug initialization issues",
        check_function="check_circular_imports",
        languages=["python"],
        tags=["imports", "modularity"],
    ),
    StandardRule(
        rule_id="ARCH-003",
        name="Service Boundaries",
        description="Services should not directly import from other service internals",
        category=StandardCategory.ARCHITECTURE,
        severity=ViolationSeverity.MAJOR,
        rationale="Services should communicate through defined interfaces",
        pattern=r"from\s+(?:services|modules)\.[^.]+\._",
        languages=["python"],
        fix_suggestion="Import from the service's public API only",
        tags=["boundaries", "coupling"],
    ),
    StandardRule(
        rule_id="ARCH-004",
        name="God Class",
        description="Classes should not have more than 20 public methods",
        category=StandardCategory.ARCHITECTURE,
        severity=ViolationSeverity.MAJOR,
        rationale="Large classes violate single responsibility principle",
        check_function="check_class_size",
        languages=["python", "java", "typescript"],
        fix_suggestion="Break this class into smaller, focused classes",
        tags=["srp", "cohesion"],
    ),
]

NAMING_STANDARDS = [
    StandardRule(
        rule_id="NAME-001",
        name="Class Naming",
        description="Class names should use PascalCase",
        category=StandardCategory.NAMING,
        severity=ViolationSeverity.MINOR,
        rationale="Consistent naming improves code readability",
        pattern=r"class\s+[a-z_][a-zA-Z0-9_]*\s*[:\(]",
        languages=["python"],
        fix_suggestion="Rename class to use PascalCase",
        tags=["convention"],
    ),
    StandardRule(
        rule_id="NAME-002",
        name="Constant Naming",
        description="Constants should use UPPER_SNAKE_CASE",
        category=StandardCategory.NAMING,
        severity=ViolationSeverity.MINOR,
        rationale="Constants should be easily distinguishable from variables",
        pattern=r"^[A-Z][a-z]+[A-Z].*\s*=\s*(?:True|False|\d+|['\"])",
        languages=["python"],
        fix_suggestion="Rename constant to use UPPER_SNAKE_CASE",
        tags=["convention"],
    ),
    StandardRule(
        rule_id="NAME-003",
        name="Boolean Naming",
        description="Boolean variables should use is_, has_, or can_ prefix",
        category=StandardCategory.NAMING,
        severity=ViolationSeverity.MINOR,
        rationale="Boolean naming prefix makes intent clear",
        pattern=r"^\s+(?:enabled|active|valid|visible|hidden)\s*[=:]",
        languages=["python", "javascript", "typescript"],
        fix_suggestion="Use is_enabled, is_active, is_valid, etc.",
        tags=["convention", "readability"],
    ),
    StandardRule(
        rule_id="NAME-004",
        name="Function Naming",
        description="Functions should use snake_case in Python",
        category=StandardCategory.NAMING,
        severity=ViolationSeverity.MINOR,
        rationale="Follow language conventions for consistency",
        pattern=r"def\s+[a-z]+[A-Z][a-zA-Z]*\s*\(",
        languages=["python"],
        fix_suggestion="Rename function to use snake_case",
        tags=["convention"],
    ),
]

DOCUMENTATION_STANDARDS = [
    StandardRule(
        rule_id="DOC-001",
        name="Public Function Docstrings",
        description="Public functions must have docstrings",
        category=StandardCategory.DOCUMENTATION,
        severity=ViolationSeverity.MAJOR,
        rationale="Docstrings help others understand function purpose and usage",
        check_function="check_function_docstrings",
        languages=["python"],
        fix_suggestion="Add a docstring describing the function's purpose, args, and return value",
        tags=["documentation"],
    ),
    StandardRule(
        rule_id="DOC-002",
        name="Class Docstrings",
        description="Classes must have docstrings",
        category=StandardCategory.DOCUMENTATION,
        severity=ViolationSeverity.MAJOR,
        rationale="Class docstrings explain purpose and usage patterns",
        check_function="check_class_docstrings",
        languages=["python"],
        fix_suggestion="Add a docstring describing the class's purpose and key methods",
        tags=["documentation"],
    ),
    StandardRule(
        rule_id="DOC-003",
        name="Module Docstrings",
        description="Modules must have docstrings",
        category=StandardCategory.DOCUMENTATION,
        severity=ViolationSeverity.MINOR,
        rationale="Module docstrings provide overview of the module's purpose",
        check_function="check_module_docstrings",
        languages=["python"],
        fix_suggestion="Add a module-level docstring at the top of the file",
        tags=["documentation"],
    ),
    StandardRule(
        rule_id="DOC-004",
        name="README Required",
        description="Repositories must have a README.md",
        category=StandardCategory.DOCUMENTATION,
        severity=ViolationSeverity.CRITICAL,
        rationale="README provides essential information for new contributors",
        check_function="check_readme_exists",
        file_patterns=["**/README.md"],
        tags=["documentation", "onboarding"],
    ),
]

DEPENDENCY_STANDARDS = [
    StandardRule(
        rule_id="DEP-001",
        name="Pinned Dependencies",
        description="Dependencies should be pinned to specific versions",
        category=StandardCategory.DEPENDENCY,
        severity=ViolationSeverity.MAJOR,
        rationale="Unpinned dependencies can cause unpredictable builds",
        pattern=r"^\s*[a-zA-Z0-9_-]+\s*$|>=|>(?!=)",
        file_patterns=["**/requirements.txt"],
        fix_suggestion="Pin dependencies: package==1.2.3",
        tags=["reproducibility"],
    ),
    StandardRule(
        rule_id="DEP-002",
        name="No Dev Dependencies in Production",
        description="Development dependencies should not be in main requirements",
        category=StandardCategory.DEPENDENCY,
        severity=ViolationSeverity.MAJOR,
        rationale="Dev dependencies increase attack surface in production",
        pattern=r"(?:pytest|black|flake8|mypy|isort|coverage)",
        file_patterns=["**/requirements.txt"],
        fix_suggestion="Move development dependencies to requirements-dev.txt",
        tags=["security", "separation"],
    ),
    StandardRule(
        rule_id="DEP-003",
        name="License Compliance",
        description="Dependencies must use approved licenses",
        category=StandardCategory.DEPENDENCY,
        severity=ViolationSeverity.BLOCKER,
        rationale="Some licenses are incompatible with commercial use",
        check_function="check_dependency_licenses",
        tags=["legal", "compliance"],
    ),
]

API_STANDARDS = [
    StandardRule(
        rule_id="API-001",
        name="Versioned Endpoints",
        description="API endpoints should include version prefix",
        category=StandardCategory.API,
        severity=ViolationSeverity.MAJOR,
        rationale="Versioning allows for backwards-compatible evolution",
        pattern=r"@(?:app|router)\.(get|post|put|delete)\s*\(\s*['\"](?!/v\d+/|/api/v\d+/)",
        languages=["python"],
        fix_suggestion="Prefix endpoints with /api/v1/ or similar",
        tags=["versioning", "compatibility"],
    ),
    StandardRule(
        rule_id="API-002",
        name="Resource Naming",
        description="REST endpoints should use plural nouns",
        category=StandardCategory.API,
        severity=ViolationSeverity.MINOR,
        rationale="Consistent resource naming improves API discoverability",
        pattern=r"@(?:app|router)\.(get|post|put|delete)\s*\(['\"].*/(user|item|order|product)/",
        languages=["python"],
        fix_suggestion="Use plural nouns: /users/, /items/, /orders/",
        tags=["rest", "naming"],
    ),
    StandardRule(
        rule_id="API-003",
        name="HTTP Method Semantics",
        description="Use appropriate HTTP methods for operations",
        category=StandardCategory.API,
        severity=ViolationSeverity.MAJOR,
        rationale="Proper HTTP methods improve API predictability",
        pattern=r"@(?:app|router)\.post\s*\([^)]*(?:get|fetch|list|retrieve|search)",
        languages=["python"],
        fix_suggestion="Use GET for read operations, POST for create",
        tags=["rest", "semantics"],
    ),
    StandardRule(
        rule_id="API-004",
        name="Error Response Format",
        description="API errors should use consistent format",
        category=StandardCategory.API,
        severity=ViolationSeverity.MAJOR,
        rationale="Consistent error format improves client error handling",
        check_function="check_error_format",
        languages=["python"],
        tags=["consistency", "errors"],
    ),
]

TESTING_STANDARDS = [
    StandardRule(
        rule_id="TEST-001",
        name="Test File Naming",
        description="Test files should follow test_*.py or *_test.py pattern",
        category=StandardCategory.TESTING,
        severity=ViolationSeverity.MINOR,
        rationale="Consistent naming helps test discovery",
        file_patterns=["**/tests/**/*.py"],
        check_function="check_test_file_naming",
        languages=["python"],
        tags=["naming", "discovery"],
    ),
    StandardRule(
        rule_id="TEST-002",
        name="Test Function Naming",
        description="Test functions should start with test_",
        category=StandardCategory.TESTING,
        severity=ViolationSeverity.MINOR,
        rationale="Proper naming ensures tests are discovered and run",
        pattern=r"def\s+(?!test_)[a-z_]+test[a-z_]*\s*\(",
        file_patterns=["**/test*.py", "**/*test.py"],
        languages=["python"],
        fix_suggestion="Rename test function to start with test_",
        tags=["naming", "discovery"],
    ),
    StandardRule(
        rule_id="TEST-003",
        name="Assert Messages",
        description="Assertions should include descriptive messages",
        category=StandardCategory.TESTING,
        severity=ViolationSeverity.MINOR,
        rationale="Assert messages help diagnose test failures",
        pattern=r"assert\s+[^,\n]+(?!\s*,\s*['\"])",
        file_patterns=["**/test*.py"],
        languages=["python"],
        fix_suggestion="Add a message: assert condition, 'description'",
        tags=["debugging", "maintainability"],
    ),
    StandardRule(
        rule_id="TEST-004",
        name="Test Coverage",
        description="Code coverage should be at least 80%",
        category=StandardCategory.TESTING,
        severity=ViolationSeverity.MAJOR,
        rationale="Adequate coverage helps catch regressions",
        check_function="check_test_coverage",
        tags=["quality", "coverage"],
    ),
]


# =============================================================================
# Organization Standards Validator Service
# =============================================================================


class OrgStandardsValidator:
    """
    Comprehensive organizational standards validation service.

    Provides:
    - Custom coding standards validation
    - Security policy compliance checking
    - Architecture pattern enforcement
    - Naming convention validation
    - Documentation requirements checking
    - Dependency policy enforcement
    - API design standards validation
    """

    def __init__(
        self,
        neptune_client: Any = None,
        opensearch_client: Any = None,
        llm_client: Any = None,
    ):
        self._neptune = neptune_client
        self._opensearch = opensearch_client
        self._llm = llm_client

        # Initialize built-in rules
        self._rules: dict[str, StandardRule] = {}
        self._load_builtin_rules()

        # Policy storage
        self._policies: dict[str, StandardsPolicy] = {}

        # Exemptions
        self._exemptions: dict[str, ExemptionRequest] = {}

        # Custom check functions
        self._check_functions: dict[str, Callable] = {
            "check_function_length": self._check_function_length,
            "check_cyclomatic_complexity": self._check_cyclomatic_complexity,
            "check_circular_imports": self._check_circular_imports,
            "check_class_size": self._check_class_size,
            "check_function_docstrings": self._check_function_docstrings,
            "check_class_docstrings": self._check_class_docstrings,
            "check_module_docstrings": self._check_module_docstrings,
            "check_readme_exists": self._check_readme_exists,
            "check_dependency_licenses": self._check_dependency_licenses,
            "check_error_format": self._check_error_format,
            "check_test_file_naming": self._check_test_file_naming,
            "check_test_coverage": self._check_test_coverage,
        }

        # Compliance mappings
        self._compliance_mappings: list[ComplianceMapping] = []

        self._logger = logger.bind(service="org_standards_validator")

    def _load_builtin_rules(self) -> None:
        """Load all built-in standard rules."""
        all_rules = (
            CODING_STANDARDS
            + SECURITY_STANDARDS
            + ARCHITECTURE_STANDARDS
            + NAMING_STANDARDS
            + DOCUMENTATION_STANDARDS
            + DEPENDENCY_STANDARDS
            + API_STANDARDS
            + TESTING_STANDARDS
        )

        for rule in all_rules:
            self._rules[rule.rule_id] = rule

    # =========================================================================
    # Policy Management
    # =========================================================================

    def create_policy(
        self,
        name: str,
        description: str,
        rule_ids: list[str],
        enforcement_level: EnforcementLevel = EnforcementLevel.STANDARD,
        applies_to: list[str] | None = None,
        exemptions: list[str] | None = None,
    ) -> StandardsPolicy:
        """
        Create a new standards policy.

        Args:
            name: Policy name
            description: Policy description
            rule_ids: List of rule IDs to include
            enforcement_level: How strictly to enforce
            applies_to: Repository patterns this applies to
            exemptions: File patterns to exempt

        Returns:
            Created policy
        """
        rules = [self._rules[rid] for rid in rule_ids if rid in self._rules]

        policy = StandardsPolicy(
            policy_id=str(uuid.uuid4()),
            name=name,
            description=description,
            version="1.0.0",
            rules=rules,
            enforcement_level=enforcement_level,
            applies_to=applies_to or ["*"],
            exemptions=exemptions or [],
        )

        self._policies[policy.policy_id] = policy

        self._logger.info(
            "Created standards policy",
            policy_id=policy.policy_id,
            name=name,
            rules=len(rules),
        )

        return policy

    def get_default_policy(self) -> StandardsPolicy:
        """Get the default standards policy with all rules."""
        if "default" not in self._policies:
            self._policies["default"] = StandardsPolicy(
                policy_id="default",
                name="Default Organization Standards",
                description="Comprehensive standards policy including all built-in rules",
                version="1.0.0",
                rules=list(self._rules.values()),
                enforcement_level=EnforcementLevel.STANDARD,
            )
        return self._policies["default"]

    def add_custom_rule(self, rule: StandardRule) -> None:
        """Add a custom rule to the registry."""
        self._rules[rule.rule_id] = rule
        self._logger.info("Added custom rule", rule_id=rule.rule_id, name=rule.name)

    # =========================================================================
    # Main Validation Interface
    # =========================================================================

    async def validate(
        self,
        file_contents: dict[str, str],
        policy: StandardsPolicy | None = None,
        categories: list[StandardCategory] | None = None,
    ) -> ValidationReport:
        """
        Validate files against organizational standards.

        Args:
            file_contents: Dict mapping file paths to content
            policy: Standards policy to use (defaults to default policy)
            categories: Specific categories to check (defaults to all)

        Returns:
            Complete validation report
        """
        policy = policy or self.get_default_policy()
        report_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)

        self._logger.info(
            "Starting standards validation",
            report_id=report_id,
            policy=policy.name,
            files=len(file_contents),
        )

        all_results: list[ValidationResult] = []
        all_violations: list[StandardViolation] = []
        files_with_violations: set[str] = set()

        # Filter rules by category if specified
        rules_to_check = policy.rules
        if categories:
            rules_to_check = [r for r in rules_to_check if r.category in categories]

        # Run each rule
        for rule in rules_to_check:
            if not rule.enabled:
                continue

            result = await self._run_rule(rule, file_contents, policy)
            all_results.append(result)

            for violation in result.violations:
                # Check for exemptions
                if self._is_exempted(rule.rule_id, violation.location.file_path):
                    continue

                # Apply enforcement level
                adjusted_violation = self._apply_enforcement(
                    violation, policy.enforcement_level
                )
                all_violations.append(adjusted_violation)
                files_with_violations.add(violation.location.file_path)

        completed_at = datetime.now(timezone.utc)

        # Count by severity
        severity_counts = dict.fromkeys(ViolationSeverity, 0)
        for v in all_violations:
            severity_counts[v.severity] += 1

        # Count by category
        category_counts: dict[str, int] = {}
        for v in all_violations:
            cat = v.rule.category.value
            category_counts[cat] = category_counts.get(cat, 0) + 1

        # Determine overall status
        if severity_counts[ViolationSeverity.BLOCKER] > 0:
            status = ValidationStatus.FAILED
            can_merge = False
        elif severity_counts[ViolationSeverity.CRITICAL] > 0:
            status = ValidationStatus.WARNING
            can_merge = policy.enforcement_level != EnforcementLevel.STRICT
        elif all_violations:
            status = ValidationStatus.WARNING
            can_merge = True
        else:
            status = ValidationStatus.PASSED
            can_merge = True

        report = ValidationReport(
            report_id=report_id,
            policy_name=policy.name,
            status=status,
            total_files=len(file_contents),
            files_with_violations=len(files_with_violations),
            total_violations=len(all_violations),
            blocker_count=severity_counts[ViolationSeverity.BLOCKER],
            critical_count=severity_counts[ViolationSeverity.CRITICAL],
            major_count=severity_counts[ViolationSeverity.MAJOR],
            minor_count=severity_counts[ViolationSeverity.MINOR],
            info_count=severity_counts[ViolationSeverity.INFO],
            results=all_results,
            violations=all_violations,
            summary_by_category=category_counts,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=(completed_at - started_at).total_seconds(),
            can_merge=can_merge,
        )

        self._logger.info(
            "Standards validation completed",
            report_id=report_id,
            status=status.value,
            total_violations=len(all_violations),
            blockers=severity_counts[ViolationSeverity.BLOCKER],
            can_merge=can_merge,
        )

        return report

    async def _run_rule(
        self, rule: StandardRule, file_contents: dict[str, str], policy: StandardsPolicy
    ) -> ValidationResult:
        """Run a single rule against all applicable files."""
        start_time = datetime.now(timezone.utc)
        violations = []
        files_checked = 0

        # Filter files by pattern and language
        applicable_files = self._get_applicable_files(
            file_contents, rule.file_patterns, rule.languages, policy.exemptions
        )

        for file_path, content in applicable_files.items():
            files_checked += 1

            if rule.pattern:
                # Regex-based check
                file_violations = self._check_pattern(rule, file_path, content)
                violations.extend(file_violations)

            if rule.check_function and rule.check_function in self._check_functions:
                # Custom function check
                check_fn = self._check_functions[rule.check_function]
                file_violations = check_fn(rule, file_path, content)
                violations.extend(file_violations)

        execution_time = (
            datetime.now(timezone.utc) - start_time
        ).total_seconds() * 1000

        status = ValidationStatus.FAILED if violations else ValidationStatus.PASSED

        return ValidationResult(
            rule_id=rule.rule_id,
            status=status,
            violations=violations,
            files_checked=files_checked,
            execution_time_ms=execution_time,
        )

    def _get_applicable_files(
        self,
        file_contents: dict[str, str],
        file_patterns: list[str],
        languages: list[str],
        exemptions: list[str],
    ) -> dict[str, str]:
        """Filter files to those applicable for a rule."""
        applicable = {}

        language_extensions = {
            "python": [".py"],
            "javascript": [".js", ".jsx"],
            "typescript": [".ts", ".tsx"],
            "java": [".java"],
            "go": [".go"],
            "ruby": [".rb"],
            "rust": [".rs"],
        }

        for file_path, content in file_contents.items():
            # Check exemptions
            if any(self._matches_pattern(file_path, pattern) for pattern in exemptions):
                continue

            # Check file patterns
            if file_patterns:
                if not any(
                    self._matches_pattern(file_path, pattern)
                    for pattern in file_patterns
                ):
                    continue
            elif languages:
                # Check language extensions
                ext = Path(file_path).suffix.lower()
                applicable_exts = []
                for lang in languages:
                    applicable_exts.extend(language_extensions.get(lang, []))
                if ext not in applicable_exts:
                    continue

            applicable[file_path] = content

        return applicable

    def _matches_pattern(self, file_path: str, pattern: str) -> bool:
        """Check if file path matches a glob pattern."""
        import fnmatch

        return fnmatch.fnmatch(file_path, pattern)

    def _check_pattern(
        self, rule: StandardRule, file_path: str, content: str
    ) -> list[StandardViolation]:
        """Check content against regex pattern."""
        violations: list[StandardViolation] = []

        if not rule.pattern:
            return violations

        try:
            pattern = re.compile(rule.pattern, re.MULTILINE)
            lines = content.split("\n")

            for match in pattern.finditer(content):
                # Calculate line number
                line_num = content[: match.start()].count("\n") + 1
                snippet = lines[line_num - 1] if line_num <= len(lines) else ""

                violations.append(
                    StandardViolation(
                        violation_id=str(uuid.uuid4()),
                        rule=rule,
                        location=CodeLocation(
                            file_path=file_path,
                            start_line=line_num,
                            end_line=line_num,
                            snippet=snippet.strip(),
                        ),
                        message=f"{rule.name}: {rule.description}",
                        severity=rule.severity,
                        suggested_fix=rule.fix_suggestion,
                    )
                )
        except re.error as e:
            self._logger.warning(
                f"Invalid regex pattern for rule {rule.rule_id}", error=str(e)
            )

        return violations

    def _apply_enforcement(
        self, violation: StandardViolation, level: EnforcementLevel
    ) -> StandardViolation:
        """Apply enforcement level to violation severity."""
        if level == EnforcementLevel.STRICT:
            # Upgrade all to blocker
            violation.severity = ViolationSeverity.BLOCKER
        elif level == EnforcementLevel.ADVISORY:
            # Downgrade all to info
            violation.severity = ViolationSeverity.INFO

        return violation

    # =========================================================================
    # Custom Check Functions
    # =========================================================================

    def _check_function_length(
        self, rule: StandardRule, file_path: str, content: str
    ) -> list[StandardViolation]:
        """Check for functions exceeding maximum length."""
        violations = []
        max_lines = 50

        # Simple function detection for Python
        function_pattern = re.compile(r"^(\s*)def\s+(\w+)\s*\(", re.MULTILINE)
        lines = content.split("\n")

        for match in function_pattern.finditer(content):
            indent = len(match.group(1))
            func_name = match.group(2)
            start_line = content[: match.start()].count("\n") + 1

            # Find function end by indentation
            end_line = start_line
            for i in range(start_line, len(lines)):
                line = lines[i]
                if (
                    line.strip()
                    and not line.startswith(" " * (indent + 1))
                    and i > start_line
                ):
                    if not line.strip().startswith("#"):
                        break
                end_line = i + 1

            func_length = end_line - start_line

            if func_length > max_lines:
                violations.append(
                    StandardViolation(
                        violation_id=str(uuid.uuid4()),
                        rule=rule,
                        location=CodeLocation(
                            file_path=file_path,
                            start_line=start_line,
                            end_line=end_line,
                            snippet=f"def {func_name}(...)",
                        ),
                        message=f"Function '{func_name}' is {func_length} lines (max: {max_lines})",
                        severity=rule.severity,
                        suggested_fix=rule.fix_suggestion,
                        context={"function_name": func_name, "line_count": func_length},
                    )
                )

        return violations

    def _check_cyclomatic_complexity(
        self, rule: StandardRule, file_path: str, content: str
    ) -> list[StandardViolation]:
        """Check for high cyclomatic complexity."""
        violations = []
        max_complexity = 10

        # Count complexity by counting branching statements
        complexity_keywords = [
            "if",
            "elif",
            "for",
            "while",
            "except",
            "and",
            "or",
            "case",
        ]

        function_pattern = re.compile(r"^(\s*)def\s+(\w+)\s*\([^)]*\):", re.MULTILINE)
        lines = content.split("\n")

        for match in function_pattern.finditer(content):
            indent = len(match.group(1))
            func_name = match.group(2)
            start_line = content[: match.start()].count("\n") + 1

            # Find function body
            complexity = 1  # Base complexity

            for i in range(start_line, len(lines)):
                line = lines[i]
                if (
                    line.strip()
                    and not line.startswith(" " * (indent + 1))
                    and i > start_line
                ):
                    if not line.strip().startswith("#"):
                        break

                # Count complexity keywords
                for keyword in complexity_keywords:
                    if re.search(rf"\b{keyword}\b", line):
                        complexity += 1

            if complexity > max_complexity:
                violations.append(
                    StandardViolation(
                        violation_id=str(uuid.uuid4()),
                        rule=rule,
                        location=CodeLocation(
                            file_path=file_path,
                            start_line=start_line,
                            end_line=start_line,
                            snippet=f"def {func_name}(...)",
                        ),
                        message=f"Function '{func_name}' has complexity {complexity} (max: {max_complexity})",
                        severity=rule.severity,
                        suggested_fix="Break function into smaller, focused functions",
                        context={"function_name": func_name, "complexity": complexity},
                    )
                )

        return violations

    def _check_circular_imports(
        self, rule: StandardRule, file_path: str, content: str
    ) -> list[StandardViolation]:
        """Check for potential circular imports."""
        # This would need cross-file analysis in production
        return []

    def _check_class_size(
        self, rule: StandardRule, file_path: str, content: str
    ) -> list[StandardViolation]:
        """Check for classes with too many methods."""
        violations = []
        max_methods = 20

        class_pattern = re.compile(r"^class\s+(\w+)", re.MULTILINE)
        method_pattern = re.compile(r"^\s+def\s+(?!_)", re.MULTILINE)

        for class_match in class_pattern.finditer(content):
            class_name = class_match.group(1)
            start_line = content[: class_match.start()].count("\n") + 1

            # Find class body and count methods
            class_body_start = class_match.end()
            class_body_end = len(content)

            # Find next class or end
            next_class = class_pattern.search(content, class_match.end())
            if next_class:
                class_body_end = next_class.start()

            class_body = content[class_body_start:class_body_end]
            method_count = len(method_pattern.findall(class_body))

            if method_count > max_methods:
                violations.append(
                    StandardViolation(
                        violation_id=str(uuid.uuid4()),
                        rule=rule,
                        location=CodeLocation(
                            file_path=file_path,
                            start_line=start_line,
                            end_line=start_line,
                            snippet=f"class {class_name}",
                        ),
                        message=f"Class '{class_name}' has {method_count} public methods (max: {max_methods})",
                        severity=rule.severity,
                        suggested_fix=rule.fix_suggestion,
                        context={
                            "class_name": class_name,
                            "method_count": method_count,
                        },
                    )
                )

        return violations

    def _check_function_docstrings(
        self, rule: StandardRule, file_path: str, content: str
    ) -> list[StandardViolation]:
        """Check for functions missing docstrings."""
        violations = []

        # Match public functions (not starting with _)
        function_pattern = re.compile(
            r"^(\s*)def\s+([a-zA-Z][a-zA-Z0-9_]*)\s*\([^)]*\):", re.MULTILINE
        )
        lines = content.split("\n")

        for match in function_pattern.finditer(content):
            func_name = match.group(2)
            start_line = content[: match.start()].count("\n") + 1

            # Check if next non-empty line is a docstring
            has_docstring = False
            for i in range(start_line, min(start_line + 3, len(lines))):
                line = lines[i].strip()
                if line and (line.startswith('"""') or line.startswith("'''")):
                    has_docstring = True
                    break
                elif line and not line.startswith("#"):
                    break

            if not has_docstring:
                violations.append(
                    StandardViolation(
                        violation_id=str(uuid.uuid4()),
                        rule=rule,
                        location=CodeLocation(
                            file_path=file_path,
                            start_line=start_line,
                            end_line=start_line,
                            snippet=f"def {func_name}(...)",
                        ),
                        message=f"Function '{func_name}' is missing a docstring",
                        severity=rule.severity,
                        suggested_fix=rule.fix_suggestion,
                    )
                )

        return violations

    def _check_class_docstrings(
        self, rule: StandardRule, file_path: str, content: str
    ) -> list[StandardViolation]:
        """Check for classes missing docstrings."""
        violations = []

        class_pattern = re.compile(r"^class\s+(\w+)", re.MULTILINE)
        lines = content.split("\n")

        for match in class_pattern.finditer(content):
            class_name = match.group(1)
            start_line = content[: match.start()].count("\n") + 1

            # Check if next non-empty line is a docstring
            has_docstring = False
            for i in range(start_line, min(start_line + 3, len(lines))):
                line = lines[i].strip()
                if line and (line.startswith('"""') or line.startswith("'''")):
                    has_docstring = True
                    break
                elif line and not line.startswith("#") and "class" not in line:
                    break

            if not has_docstring:
                violations.append(
                    StandardViolation(
                        violation_id=str(uuid.uuid4()),
                        rule=rule,
                        location=CodeLocation(
                            file_path=file_path,
                            start_line=start_line,
                            end_line=start_line,
                            snippet=f"class {class_name}",
                        ),
                        message=f"Class '{class_name}' is missing a docstring",
                        severity=rule.severity,
                        suggested_fix=rule.fix_suggestion,
                    )
                )

        return violations

    def _check_module_docstrings(
        self, rule: StandardRule, file_path: str, content: str
    ) -> list[StandardViolation]:
        """Check for module-level docstring."""
        violations = []

        lines = content.split("\n")
        has_docstring = False

        for _i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith('"""') or stripped.startswith("'''"):
                has_docstring = True
            break

        if not has_docstring:
            violations.append(
                StandardViolation(
                    violation_id=str(uuid.uuid4()),
                    rule=rule,
                    location=CodeLocation(
                        file_path=file_path,
                        start_line=1,
                        end_line=1,
                        snippet=lines[0] if lines else "",
                    ),
                    message="Module is missing a docstring",
                    severity=rule.severity,
                    suggested_fix=rule.fix_suggestion,
                )
            )

        return violations

    def _check_readme_exists(
        self, rule: StandardRule, file_path: str, content: str
    ) -> list[StandardViolation]:
        """Check for README.md existence."""
        # This check is done at the repository level, not file level
        return []

    def _check_dependency_licenses(
        self, rule: StandardRule, file_path: str, content: str
    ) -> list[StandardViolation]:
        """Check dependencies for license compliance."""
        # Would need to query license database
        return []

    def _check_error_format(
        self, rule: StandardRule, file_path: str, content: str
    ) -> list[StandardViolation]:
        """Check API error response format consistency."""
        # Would need to analyze error handling patterns
        return []

    def _check_test_file_naming(
        self, rule: StandardRule, file_path: str, content: str
    ) -> list[StandardViolation]:
        """Check test file naming convention."""
        violations = []
        filename = Path(file_path).name

        if "test" in file_path.lower():
            if not filename.startswith("test_") and not filename.endswith("_test.py"):
                violations.append(
                    StandardViolation(
                        violation_id=str(uuid.uuid4()),
                        rule=rule,
                        location=CodeLocation(
                            file_path=file_path, start_line=1, end_line=1
                        ),
                        message=f"Test file '{filename}' should follow test_*.py or *_test.py pattern",
                        severity=rule.severity,
                        suggested_fix="Rename file to test_*.py or *_test.py",
                    )
                )

        return violations

    def _check_test_coverage(
        self, rule: StandardRule, file_path: str, content: str
    ) -> list[StandardViolation]:
        """Check test coverage metrics."""
        # Would need integration with coverage tools
        return []

    # =========================================================================
    # Exemption Management
    # =========================================================================

    def request_exemption(
        self,
        rule_id: str,
        file_patterns: list[str],
        justification: str,
        requested_by: str,
        expires_at: datetime | None = None,
    ) -> ExemptionRequest:
        """Request an exemption from a standard."""
        exemption = ExemptionRequest(
            request_id=str(uuid.uuid4()),
            rule_id=rule_id,
            file_patterns=file_patterns,
            justification=justification,
            requested_by=requested_by,
            expires_at=expires_at,
        )

        self._exemptions[exemption.request_id] = exemption

        self._logger.info(
            "Exemption requested",
            request_id=exemption.request_id,
            rule_id=rule_id,
            requested_by=requested_by,
        )

        return exemption

    def approve_exemption(self, request_id: str, approved_by: str) -> ExemptionRequest:
        """Approve an exemption request."""
        exemption = self._exemptions.get(request_id)
        if not exemption:
            raise ValueError(f"Exemption request not found: {request_id}")

        exemption.approved_by = approved_by
        exemption.status = "approved"

        self._logger.info(
            "Exemption approved", request_id=request_id, approved_by=approved_by
        )

        return exemption

    def _is_exempted(self, rule_id: str, file_path: str) -> bool:
        """Check if a file is exempted from a rule."""
        for exemption in self._exemptions.values():
            if exemption.rule_id != rule_id:
                continue
            if exemption.status != "approved":
                continue
            if exemption.expires_at and exemption.expires_at < datetime.now(
                timezone.utc
            ):
                continue

            for pattern in exemption.file_patterns:
                if self._matches_pattern(file_path, pattern):
                    return True

        return False

    # =========================================================================
    # Compliance Mapping
    # =========================================================================

    def add_compliance_mapping(
        self,
        framework: str,
        control_id: str,
        control_name: str,
        rule_ids: list[str],
        evidence_description: str,
    ) -> ComplianceMapping:
        """Map standards to compliance framework controls."""
        mapping = ComplianceMapping(
            framework=framework,
            control_id=control_id,
            control_name=control_name,
            rule_ids=rule_ids,
            evidence_description=evidence_description,
        )

        self._compliance_mappings.append(mapping)
        return mapping

    def get_compliance_report(
        self, validation_report: ValidationReport, framework: str
    ) -> dict[str, Any]:
        """Generate compliance-focused report for a framework."""
        mappings = [m for m in self._compliance_mappings if m.framework == framework]

        control_status = {}
        for mapping in mappings:
            # Check if all mapped rules passed
            rule_violations = [
                v
                for v in validation_report.violations
                if v.rule.rule_id in mapping.rule_ids
            ]

            if not rule_violations:
                status = "compliant"
            else:
                blocker_violations = [
                    v
                    for v in rule_violations
                    if v.severity
                    in [ViolationSeverity.BLOCKER, ViolationSeverity.CRITICAL]
                ]
                status = "non_compliant" if blocker_violations else "partial"

            control_status[mapping.control_id] = {
                "control_name": mapping.control_name,
                "status": status,
                "violations": len(rule_violations),
                "evidence": mapping.evidence_description,
            }

        return {
            "framework": framework,
            "report_date": datetime.now(timezone.utc).isoformat(),
            "controls_evaluated": len(mappings),
            "compliant_controls": sum(
                1 for c in control_status.values() if c["status"] == "compliant"
            ),
            "controls": control_status,
        }

    # =========================================================================
    # Report Generation
    # =========================================================================

    def generate_pr_comment(self, report: ValidationReport) -> str:
        """Generate a PR comment summarizing validation results."""
        status_emoji = {
            ValidationStatus.PASSED: ":white_check_mark:",
            ValidationStatus.FAILED: ":x:",
            ValidationStatus.WARNING: ":warning:",
        }

        emoji = status_emoji.get(report.status, ":question:")

        lines = [
            f"## {emoji} Organization Standards Validation",
            "",
            f"**Policy:** {report.policy_name}",
            f"**Status:** {report.status.value.upper()}",
            f"**Can Merge:** {'Yes' if report.can_merge else 'No'}",
            "",
            "### Summary",
            "",
            "| Severity | Count |",
            "|----------|-------|",
            f"| :no_entry: Blocker | {report.blocker_count} |",
            f"| :red_circle: Critical | {report.critical_count} |",
            f"| :orange_circle: Major | {report.major_count} |",
            f"| :yellow_circle: Minor | {report.minor_count} |",
            f"| :information_source: Info | {report.info_count} |",
            "",
            f"**Files Analyzed:** {report.total_files}",
            f"**Files with Issues:** {report.files_with_violations}",
            "",
        ]

        # Group violations by category
        if report.violations:
            lines.extend(["### Violations by Category", ""])

            for category, count in sorted(report.summary_by_category.items()):
                lines.append(f"- **{category.capitalize()}:** {count}")

            lines.append("")

        # Top violations
        if report.violations:
            lines.extend(["### Top Issues", ""])

            # Sort by severity and show top 10
            sorted_violations = sorted(
                report.violations,
                key=lambda v: list(ViolationSeverity).index(v.severity),
            )

            for v in sorted_violations[:10]:
                severity_badge = {
                    ViolationSeverity.BLOCKER: ":no_entry:",
                    ViolationSeverity.CRITICAL: ":red_circle:",
                    ViolationSeverity.MAJOR: ":orange_circle:",
                    ViolationSeverity.MINOR: ":yellow_circle:",
                    ViolationSeverity.INFO: ":information_source:",
                }
                badge = severity_badge.get(v.severity, "")

                lines.append(
                    f"- {badge} **{v.rule.name}** in `{v.location.file_path}:{v.location.start_line}`"
                )
                lines.append(f"  {v.message}")
                if v.suggested_fix:
                    lines.append(f"  > Fix: {v.suggested_fix}")
                lines.append("")

        # Footer
        if not report.can_merge:
            lines.extend(
                [
                    "---",
                    ":no_entry: **This PR cannot be merged until blocker issues are resolved.**",
                ]
            )

        return "\n".join(lines)

    def generate_json_report(self, report: ValidationReport) -> str:
        """Generate JSON format report."""
        return json.dumps(
            {
                "report_id": report.report_id,
                "policy": report.policy_name,
                "status": report.status.value,
                "can_merge": report.can_merge,
                "summary": {
                    "total_files": report.total_files,
                    "files_with_violations": report.files_with_violations,
                    "total_violations": report.total_violations,
                    "by_severity": {
                        "blocker": report.blocker_count,
                        "critical": report.critical_count,
                        "major": report.major_count,
                        "minor": report.minor_count,
                        "info": report.info_count,
                    },
                    "by_category": report.summary_by_category,
                },
                "violations": [
                    {
                        "rule_id": v.rule.rule_id,
                        "rule_name": v.rule.name,
                        "category": v.rule.category.value,
                        "severity": v.severity.value,
                        "file": v.location.file_path,
                        "line": v.location.start_line,
                        "message": v.message,
                        "suggested_fix": v.suggested_fix,
                    }
                    for v in report.violations
                ],
                "duration_seconds": report.duration_seconds,
            },
            indent=2,
        )
