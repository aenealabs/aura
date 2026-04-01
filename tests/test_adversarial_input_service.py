"""
Project Aura - Adversarial Input Service Tests

Tests for the adversarial input service that provides attack patterns
and fuzzing capabilities for red-team testing.
"""

from src.services.adversarial_input_service import (
    OWASP_INJECTION_PATTERNS,
    OWASP_PATH_TRAVERSAL_PATTERNS,
    OWASP_SSRF_PATTERNS,
    OWASP_XSS_PATTERNS,
    AdversarialCategory,
    AdversarialPattern,
    AdversarialTestCase,
    FuzzedInput,
    FuzzingStrategy,
    Severity,
    TargetLanguage,
)


class TestAdversarialCategory:
    """Tests for AdversarialCategory enum."""

    def test_prompt_injection(self):
        """Test prompt injection category."""
        assert AdversarialCategory.PROMPT_INJECTION.value == "prompt_injection"

    def test_code_injection(self):
        """Test code injection category."""
        assert AdversarialCategory.CODE_INJECTION.value == "code_injection"

    def test_command_injection(self):
        """Test command injection category."""
        assert AdversarialCategory.COMMAND_INJECTION.value == "command_injection"

    def test_path_traversal(self):
        """Test path traversal category."""
        assert AdversarialCategory.PATH_TRAVERSAL.value == "path_traversal"

    def test_sql_injection(self):
        """Test SQL injection category."""
        assert AdversarialCategory.SQL_INJECTION.value == "sql_injection"

    def test_xss(self):
        """Test XSS category."""
        assert AdversarialCategory.XSS.value == "xss"

    def test_ssrf(self):
        """Test SSRF category."""
        assert AdversarialCategory.SSRF.value == "ssrf"

    def test_deserialization(self):
        """Test deserialization category."""
        assert AdversarialCategory.DESERIALIZATION.value == "deserialization"

    def test_buffer_overflow(self):
        """Test buffer overflow category."""
        assert AdversarialCategory.BUFFER_OVERFLOW.value == "buffer_overflow"

    def test_sandbox_escape(self):
        """Test sandbox escape category."""
        assert AdversarialCategory.SANDBOX_ESCAPE.value == "sandbox_escape"

    def test_all_categories_exist(self):
        """Test all expected categories exist."""
        categories = list(AdversarialCategory)
        assert len(categories) == 12


class TestTargetLanguage:
    """Tests for TargetLanguage enum."""

    def test_python(self):
        """Test Python language."""
        assert TargetLanguage.PYTHON.value == "python"

    def test_javascript(self):
        """Test JavaScript language."""
        assert TargetLanguage.JAVASCRIPT.value == "javascript"

    def test_java(self):
        """Test Java language."""
        assert TargetLanguage.JAVA.value == "java"

    def test_go(self):
        """Test Go language."""
        assert TargetLanguage.GO.value == "go"

    def test_rust(self):
        """Test Rust language."""
        assert TargetLanguage.RUST.value == "rust"

    def test_shell(self):
        """Test shell language."""
        assert TargetLanguage.SHELL.value == "shell"


class TestFuzzingStrategy:
    """Tests for FuzzingStrategy enum."""

    def test_random_mutation(self):
        """Test random mutation strategy."""
        assert FuzzingStrategy.RANDOM_MUTATION.value == "random_mutation"

    def test_boundary_values(self):
        """Test boundary values strategy."""
        assert FuzzingStrategy.BOUNDARY_VALUES.value == "boundary_values"

    def test_special_characters(self):
        """Test special characters strategy."""
        assert FuzzingStrategy.SPECIAL_CHARACTERS.value == "special_characters"

    def test_encoding_variations(self):
        """Test encoding variations strategy."""
        assert FuzzingStrategy.ENCODING_VARIATIONS.value == "encoding_variations"

    def test_semantic_manipulation(self):
        """Test semantic manipulation strategy."""
        assert FuzzingStrategy.SEMANTIC_MANIPULATION.value == "semantic_manipulation"


class TestSeverity:
    """Tests for Severity enum."""

    def test_critical(self):
        """Test critical severity."""
        assert Severity.CRITICAL.value == "critical"

    def test_high(self):
        """Test high severity."""
        assert Severity.HIGH.value == "high"

    def test_medium(self):
        """Test medium severity."""
        assert Severity.MEDIUM.value == "medium"

    def test_low(self):
        """Test low severity."""
        assert Severity.LOW.value == "low"

    def test_info(self):
        """Test info severity."""
        assert Severity.INFO.value == "info"


class TestAdversarialPattern:
    """Tests for AdversarialPattern dataclass."""

    def test_minimal_pattern(self):
        """Test minimal pattern creation."""
        pattern = AdversarialPattern(
            pattern_id="test-001",
            name="Test Pattern",
            category=AdversarialCategory.SQL_INJECTION,
            severity=Severity.HIGH,
            pattern="' OR '1'='1",
            description="Test SQL injection pattern",
        )
        assert pattern.pattern_id == "test-001"
        assert pattern.category == AdversarialCategory.SQL_INJECTION
        assert pattern.severity == Severity.HIGH
        assert pattern.detection_regex is None
        assert pattern.target_languages == []
        assert pattern.cwe_ids == []

    def test_full_pattern(self):
        """Test full pattern creation."""
        pattern = AdversarialPattern(
            pattern_id="full-001",
            name="Full Pattern",
            category=AdversarialCategory.XSS,
            severity=Severity.CRITICAL,
            pattern="<script>alert('XSS')</script>",
            description="Full XSS test pattern",
            detection_regex=r"<script[^>]*>",
            target_languages=[TargetLanguage.JAVASCRIPT],
            cwe_ids=["CWE-79"],
            owasp_category="A07:2021-XSS",
            references=["https://owasp.org"],
        )
        assert pattern.detection_regex is not None
        assert TargetLanguage.JAVASCRIPT in pattern.target_languages
        assert "CWE-79" in pattern.cwe_ids
        assert pattern.owasp_category == "A07:2021-XSS"

    def test_to_dict(self):
        """Test pattern to_dict conversion."""
        pattern = AdversarialPattern(
            pattern_id="dict-001",
            name="Dict Pattern",
            category=AdversarialCategory.COMMAND_INJECTION,
            severity=Severity.CRITICAL,
            pattern="; rm -rf /",
            description="Command injection test",
            target_languages=[TargetLanguage.SHELL],
            cwe_ids=["CWE-78"],
        )
        data = pattern.to_dict()
        assert data["pattern_id"] == "dict-001"
        assert data["category"] == "command_injection"
        assert data["severity"] == "critical"
        assert "shell" in data["target_languages"]


class TestFuzzedInput:
    """Tests for FuzzedInput dataclass."""

    def test_fuzzed_input_creation(self):
        """Test fuzzed input creation."""
        fuzzed = FuzzedInput(
            fuzz_id="fuzz-001",
            base_pattern_id="base-001",
            strategy=FuzzingStrategy.RANDOM_MUTATION,
            original_input="SELECT * FROM users",
            fuzzed_input="SELECT * FROM users--",
            mutation_description="Added SQL comment suffix",
        )
        assert fuzzed.fuzz_id == "fuzz-001"
        assert fuzzed.strategy == FuzzingStrategy.RANDOM_MUTATION
        assert fuzzed.original_input == "SELECT * FROM users"
        assert fuzzed.fuzzed_input == "SELECT * FROM users--"

    def test_fuzzed_input_has_timestamp(self):
        """Test fuzzed input has created_at timestamp."""
        fuzzed = FuzzedInput(
            fuzz_id="fuzz-ts",
            base_pattern_id="base-ts",
            strategy=FuzzingStrategy.ENCODING_VARIATIONS,
            original_input="test",
            fuzzed_input="test",
            mutation_description="No change",
        )
        assert fuzzed.created_at is not None

    def test_different_strategies(self):
        """Test fuzzed inputs with different strategies."""
        for strategy in FuzzingStrategy:
            fuzzed = FuzzedInput(
                fuzz_id=f"fuzz-{strategy.value}",
                base_pattern_id="base",
                strategy=strategy,
                original_input="input",
                fuzzed_input="fuzzed",
                mutation_description=f"Using {strategy.value}",
            )
            assert fuzzed.strategy == strategy


class TestAdversarialTestCase:
    """Tests for AdversarialTestCase dataclass."""

    def test_minimal_test_case(self):
        """Test minimal test case creation."""
        pattern = AdversarialPattern(
            pattern_id="tc-pattern",
            name="Test Pattern",
            category=AdversarialCategory.SQL_INJECTION,
            severity=Severity.HIGH,
            pattern="test",
            description="Test",
        )
        test_case = AdversarialTestCase(
            test_id="tc-001",
            name="Test Case",
            patterns=[pattern],
            expected_detection=True,
            expected_blocked=True,
            target_component="api",
            description="Test case description",
        )
        assert test_case.test_id == "tc-001"
        assert len(test_case.patterns) == 1
        assert test_case.expected_detection is True
        assert test_case.max_duration_seconds == 60
        assert test_case.requires_hitl is False

    def test_test_case_with_steps(self):
        """Test case with setup and cleanup steps."""
        test_case = AdversarialTestCase(
            test_id="tc-steps",
            name="Test with Steps",
            patterns=[],
            expected_detection=True,
            expected_blocked=False,
            target_component="auth-service",
            description="Test with steps",
            setup_steps=["Create test user", "Configure mock server"],
            cleanup_steps=["Delete test user", "Reset mock server"],
        )
        assert len(test_case.setup_steps) == 2
        assert len(test_case.cleanup_steps) == 2

    def test_test_case_requires_hitl(self):
        """Test case requiring HITL approval."""
        test_case = AdversarialTestCase(
            test_id="tc-hitl",
            name="Critical Test",
            patterns=[],
            expected_detection=True,
            expected_blocked=True,
            target_component="production-api",
            description="Critical severity test",
            requires_hitl=True,
            max_duration_seconds=300,
        )
        assert test_case.requires_hitl is True
        assert test_case.max_duration_seconds == 300


class TestOWASPInjectionPatterns:
    """Tests for OWASP injection patterns."""

    def test_patterns_list_exists(self):
        """Test patterns list exists and is not empty."""
        assert len(OWASP_INJECTION_PATTERNS) > 0

    def test_all_patterns_have_ids(self):
        """Test all patterns have unique IDs."""
        ids = [p.pattern_id for p in OWASP_INJECTION_PATTERNS]
        assert len(ids) == len(set(ids))

    def test_patterns_have_owasp_category(self):
        """Test injection patterns have OWASP category."""
        for pattern in OWASP_INJECTION_PATTERNS:
            assert pattern.owasp_category is not None
            assert "A03:2021" in pattern.owasp_category

    def test_sql_injection_patterns(self):
        """Test SQL injection patterns exist."""
        sql_patterns = [
            p
            for p in OWASP_INJECTION_PATTERNS
            if p.category == AdversarialCategory.SQL_INJECTION
        ]
        assert len(sql_patterns) >= 3

    def test_command_injection_patterns(self):
        """Test command injection patterns exist."""
        cmd_patterns = [
            p
            for p in OWASP_INJECTION_PATTERNS
            if p.category == AdversarialCategory.COMMAND_INJECTION
        ]
        assert len(cmd_patterns) >= 2


class TestOWASPXSSPatterns:
    """Tests for OWASP XSS patterns."""

    def test_patterns_list_exists(self):
        """Test XSS patterns list exists."""
        assert len(OWASP_XSS_PATTERNS) > 0

    def test_all_patterns_are_xss(self):
        """Test all patterns are XSS category."""
        for pattern in OWASP_XSS_PATTERNS:
            assert pattern.category == AdversarialCategory.XSS

    def test_patterns_have_detection_regex(self):
        """Test XSS patterns have detection regex."""
        for pattern in OWASP_XSS_PATTERNS:
            assert pattern.detection_regex is not None

    def test_patterns_target_javascript(self):
        """Test XSS patterns target JavaScript."""
        for pattern in OWASP_XSS_PATTERNS:
            assert TargetLanguage.JAVASCRIPT in pattern.target_languages


class TestOWASPPathTraversalPatterns:
    """Tests for OWASP path traversal patterns."""

    def test_patterns_list_exists(self):
        """Test path traversal patterns list exists."""
        assert len(OWASP_PATH_TRAVERSAL_PATTERNS) > 0

    def test_all_patterns_are_path_traversal(self):
        """Test all patterns are path traversal category."""
        for pattern in OWASP_PATH_TRAVERSAL_PATTERNS:
            assert pattern.category == AdversarialCategory.PATH_TRAVERSAL

    def test_patterns_have_cwe_22(self):
        """Test path traversal patterns have CWE-22."""
        for pattern in OWASP_PATH_TRAVERSAL_PATTERNS:
            assert "CWE-22" in pattern.cwe_ids


class TestOWASPSSRFPatterns:
    """Tests for OWASP SSRF patterns."""

    def test_patterns_list_exists(self):
        """Test SSRF patterns list exists."""
        assert len(OWASP_SSRF_PATTERNS) > 0

    def test_all_patterns_are_ssrf(self):
        """Test all patterns are SSRF category."""
        for pattern in OWASP_SSRF_PATTERNS:
            assert pattern.category == AdversarialCategory.SSRF


class TestPatternSeverityDistribution:
    """Tests for pattern severity distribution."""

    def test_critical_patterns_exist(self):
        """Test critical severity patterns exist."""
        all_patterns = (
            OWASP_INJECTION_PATTERNS
            + OWASP_XSS_PATTERNS
            + OWASP_PATH_TRAVERSAL_PATTERNS
        )
        critical = [p for p in all_patterns if p.severity == Severity.CRITICAL]
        assert len(critical) >= 1

    def test_high_patterns_exist(self):
        """Test high severity patterns exist."""
        all_patterns = (
            OWASP_INJECTION_PATTERNS
            + OWASP_XSS_PATTERNS
            + OWASP_PATH_TRAVERSAL_PATTERNS
        )
        high = [p for p in all_patterns if p.severity == Severity.HIGH]
        assert len(high) >= 1


class TestPatternValidation:
    """Tests for pattern validation."""

    def test_patterns_have_descriptions(self):
        """Test all patterns have descriptions."""
        all_patterns = (
            OWASP_INJECTION_PATTERNS
            + OWASP_XSS_PATTERNS
            + OWASP_PATH_TRAVERSAL_PATTERNS
        )
        for pattern in all_patterns:
            assert pattern.description
            assert len(pattern.description) > 10

    def test_patterns_have_names(self):
        """Test all patterns have names."""
        all_patterns = (
            OWASP_INJECTION_PATTERNS
            + OWASP_XSS_PATTERNS
            + OWASP_PATH_TRAVERSAL_PATTERNS
        )
        for pattern in all_patterns:
            assert pattern.name
            assert len(pattern.name) > 3
