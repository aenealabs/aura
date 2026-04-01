"""
Unit tests for RLM Security Guard module.

Tests cover:
- Code validation and AST analysis
- Blocked builtin detection
- Dangerous pattern detection
- Safe namespace creation
- Subcall tracking
- Audit record generation

Reference: ADR-051 Recursive Context Scaling and Embedding Prediction
"""

import platform

import pytest

from src.services.rlm.security_guard import (
    CodeValidationResult,
    ExecutionResult,
    REPLSecurityGuard,
)

# Use forked mode on non-Linux to prevent state pollution
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestCodeValidation:
    """Tests for code validation functionality."""

    def test_valid_simple_code(self):
        """Test that simple valid code passes validation."""
        guard = REPLSecurityGuard()
        code = """
result = []
for i in range(10):
    result.append(i * 2)
sum(result)
"""
        result = guard.validate_code(code)

        assert result.is_valid
        assert len(result.violations) == 0
        assert result.code_hash
        assert result.validated_at
        assert result.code_length == len(code)

    def test_valid_list_comprehension(self):
        """Test that list comprehensions are allowed."""
        guard = REPLSecurityGuard()
        code = "[x * 2 for x in range(100)]"

        result = guard.validate_code(code)

        assert result.is_valid

    def test_valid_dictionary_operations(self):
        """Test that dictionary operations are allowed."""
        guard = REPLSecurityGuard()
        code = """
data = {"a": 1, "b": 2}
result = {k: v * 2 for k, v in data.items()}
"""
        result = guard.validate_code(code)

        assert result.is_valid

    def test_blocks_import_statement(self):
        """Test that import statements are blocked."""
        guard = REPLSecurityGuard()
        code = "import os"

        result = guard.validate_code(code)

        assert not result.is_valid
        assert any("Import" in v for v in result.violations)

    def test_blocks_from_import(self):
        """Test that from...import statements are blocked."""
        guard = REPLSecurityGuard()
        code = "from os import system"

        result = guard.validate_code(code)

        assert not result.is_valid
        assert any("ImportFrom" in v or "Import" in v for v in result.violations)

    def test_blocks_eval_call(self):
        """Test that eval() calls are blocked."""
        guard = REPLSecurityGuard()
        code = 'eval("print(1)")'

        result = guard.validate_code(code)

        assert not result.is_valid
        assert any("eval" in v.lower() for v in result.violations)

    def test_blocks_exec_call(self):
        """Test that exec() calls are blocked."""
        guard = REPLSecurityGuard()
        code = 'exec("x = 1")'

        result = guard.validate_code(code)

        assert not result.is_valid
        assert any("exec" in v.lower() for v in result.violations)

    def test_blocks_open_call(self):
        """Test that open() calls are blocked."""
        guard = REPLSecurityGuard()
        code = 'open("/etc/passwd")'

        result = guard.validate_code(code)

        assert not result.is_valid
        assert any("open" in v.lower() for v in result.violations)

    def test_blocks_dunder_class(self):
        """Test that __class__ access is blocked."""
        guard = REPLSecurityGuard()
        code = 'x = "".__class__'

        result = guard.validate_code(code)

        assert not result.is_valid
        assert any("__class__" in v for v in result.violations)

    def test_blocks_dunder_globals(self):
        """Test that __globals__ access is blocked."""
        guard = REPLSecurityGuard()
        code = "func.__globals__"

        result = guard.validate_code(code)

        assert not result.is_valid
        assert any("__globals__" in v for v in result.violations)

    def test_blocks_dunder_builtins(self):
        """Test that __builtins__ access is blocked."""
        guard = REPLSecurityGuard()
        code = "__builtins__"

        result = guard.validate_code(code)

        assert not result.is_valid
        assert any("builtins" in v.lower() for v in result.violations)

    def test_blocks_os_system(self):
        """Test that os.system patterns are blocked."""
        guard = REPLSecurityGuard()
        code = 'os.system("ls")'

        result = guard.validate_code(code)

        assert not result.is_valid
        assert any("system" in v.lower() for v in result.violations)

    def test_blocks_subprocess(self):
        """Test that subprocess patterns are blocked."""
        guard = REPLSecurityGuard()
        code = "subprocess.run(['ls'])"

        result = guard.validate_code(code)

        assert not result.is_valid
        assert any("subprocess" in v.lower() for v in result.violations)

    def test_blocks_pickle(self):
        """Test that pickle patterns are blocked."""
        guard = REPLSecurityGuard()
        code = "pickle.loads(data)"

        result = guard.validate_code(code)

        assert not result.is_valid
        assert any("deserialization" in v.lower() for v in result.violations)

    def test_blocks_socket(self):
        """Test that socket patterns are blocked."""
        guard = REPLSecurityGuard()
        code = "socket.socket()"

        result = guard.validate_code(code)

        assert not result.is_valid
        assert any("network" in v.lower() for v in result.violations)

    def test_code_too_long(self):
        """Test that overly long code is rejected."""
        guard = REPLSecurityGuard(max_code_length=100)
        code = "x = 1\n" * 50  # 300 characters

        result = guard.validate_code(code)

        assert not result.is_valid
        assert any("exceeds maximum length" in v for v in result.violations)

    def test_syntax_error_detected(self):
        """Test that syntax errors are caught."""
        guard = REPLSecurityGuard()
        code = "def foo(:"  # Invalid syntax

        result = guard.validate_code(code)

        assert not result.is_valid
        assert any("Syntax error" in v for v in result.violations)

    def test_null_bytes_detected(self):
        """Test that null bytes are detected."""
        guard = REPLSecurityGuard()
        code = "x = 1\x00y = 2"

        result = guard.validate_code(code)

        assert not result.is_valid
        assert any("null bytes" in v.lower() for v in result.violations)

    def test_global_declaration_blocked(self):
        """Test that global declarations are blocked."""
        guard = REPLSecurityGuard()
        code = """
def foo():
    global x
    x = 1
"""
        result = guard.validate_code(code)

        assert not result.is_valid
        assert any("Global" in v for v in result.violations)


class TestSafeNamespace:
    """Tests for safe namespace creation."""

    def test_creates_namespace_with_basic_builtins(self):
        """Test that safe namespace includes basic builtins."""
        guard = REPLSecurityGuard()
        ns = guard.create_safe_namespace()

        # Check basic operations are available
        assert ns["len"]([1, 2, 3]) == 3
        assert ns["str"](123) == "123"
        assert ns["int"]("42") == 42
        assert ns["list"]((1, 2)) == [1, 2]

    def test_safe_namespace_has_math_operations(self):
        """Test that math operations are available."""
        guard = REPLSecurityGuard()
        ns = guard.create_safe_namespace()

        assert ns["sum"]([1, 2, 3]) == 6
        assert ns["min"]([3, 1, 2]) == 1
        assert ns["max"]([3, 1, 2]) == 3
        assert ns["abs"](-5) == 5

    def test_safe_namespace_has_iteration_tools(self):
        """Test that iteration tools are available."""
        guard = REPLSecurityGuard()
        ns = guard.create_safe_namespace()

        assert list(ns["range"](3)) == [0, 1, 2]
        assert list(ns["enumerate"](["a", "b"])) == [(0, "a"), (1, "b")]
        assert list(ns["zip"]([1, 2], ["a", "b"])) == [(1, "a"), (2, "b")]

    def test_safe_namespace_includes_context_vars(self):
        """Test that context variables are included."""
        guard = REPLSecurityGuard()
        ns = guard.create_safe_namespace(
            context_vars={"CONTEXT": "test content", "TASK": "analyze"}
        )

        assert ns["CONTEXT"] == "test content"
        assert ns["TASK"] == "analyze"

    def test_safe_namespace_includes_helper_functions(self):
        """Test that helper functions are included."""
        guard = REPLSecurityGuard()

        def my_search(pattern):
            return ["match1", "match2"]

        ns = guard.create_safe_namespace(helper_functions={"context_search": my_search})

        assert ns["context_search"]("test") == ["match1", "match2"]

    def test_safe_print_returns_string(self):
        """Test that safe print returns string instead of printing."""
        guard = REPLSecurityGuard()
        ns = guard.create_safe_namespace()

        result = ns["print"]("hello", "world")

        assert result == "hello world"

    def test_safe_isinstance_allows_basic_types(self):
        """Test that isinstance works for basic types."""
        guard = REPLSecurityGuard()
        ns = guard.create_safe_namespace()

        assert ns["isinstance"]("test", str)
        assert ns["isinstance"](123, int)
        assert ns["isinstance"]([1, 2], list)

    def test_safe_isinstance_blocks_custom_types(self):
        """Test that isinstance blocks checks on custom types."""
        guard = REPLSecurityGuard()
        ns = guard.create_safe_namespace()

        class CustomType:
            pass

        with pytest.raises(TypeError):
            ns["isinstance"]("test", CustomType)


class TestSubcallTracking:
    """Tests for subcall tracking functionality."""

    def test_allows_subcalls_under_limit(self):
        """Test that subcalls under limit are allowed."""
        guard = REPLSecurityGuard(max_total_subcalls=10)

        for _ in range(10):
            assert guard.track_subcall() is True

    def test_blocks_subcalls_over_limit(self):
        """Test that subcalls over limit are blocked."""
        guard = REPLSecurityGuard(max_total_subcalls=5)

        for _ in range(5):
            guard.track_subcall()

        assert guard.track_subcall() is False

    def test_get_subcall_count(self):
        """Test getting current subcall count."""
        guard = REPLSecurityGuard()

        guard.track_subcall()
        guard.track_subcall()

        assert guard.get_subcall_count() == 2

    def test_reset_subcall_count(self):
        """Test resetting subcall counter."""
        guard = REPLSecurityGuard()

        guard.track_subcall()
        guard.track_subcall()
        guard.reset_subcall_count()

        assert guard.get_subcall_count() == 0


class TestOutputValidation:
    """Tests for output validation."""

    def test_valid_small_output(self):
        """Test that small outputs pass validation."""
        guard = REPLSecurityGuard()

        is_valid, error = guard.validate_output("small result")

        assert is_valid
        assert error is None

    def test_blocks_large_output(self):
        """Test that overly large outputs are blocked."""
        guard = REPLSecurityGuard(max_output_size=100)
        large_output = "x" * 200

        is_valid, error = guard.validate_output(large_output)

        assert not is_valid
        assert "exceeds maximum size" in error


class TestAuditRecords:
    """Tests for audit record generation."""

    def test_creates_audit_record(self):
        """Test that audit records are created correctly."""
        guard = REPLSecurityGuard()
        validation_result = CodeValidationResult(
            is_valid=True,
            violations=[],
            code_hash="abc123",
            validated_at="2026-01-04T12:00:00Z",
            code_length=100,
            ast_node_count=50,
        )

        record = guard.create_audit_record(
            request_id="req-123",
            user_id="user-456",
            organization_id="org-789",
            code_hash="abc123",
            validation_result=validation_result,
        )

        assert record["event_type"] == "rlm_code_execution"
        assert record["request_id"] == "req-123"
        assert record["user_id"] == "user-456"
        assert record["organization_id"] == "org-789"
        assert record["code_hash"] == "abc123"
        assert record["validation_result"] == "passed"

    def test_audit_record_includes_execution_result(self):
        """Test that execution results are included in audit record."""
        guard = REPLSecurityGuard()
        validation_result = CodeValidationResult(
            is_valid=True,
            violations=[],
            code_hash="abc123",
            validated_at="2026-01-04T12:00:00Z",
        )
        execution_result = ExecutionResult(
            success=True,
            result="test result",
            execution_time_ms=50.5,
        )

        record = guard.create_audit_record(
            request_id="req-123",
            user_id="user-456",
            organization_id="org-789",
            code_hash="abc123",
            validation_result=validation_result,
            execution_result=execution_result,
        )

        assert record["execution_success"] is True
        assert record["execution_time_ms"] == 50.5


class TestAdditionalBlockedBuiltins:
    """Tests for custom blocked builtins."""

    def test_additional_blocked_builtins(self):
        """Test that additional blocked builtins can be specified."""
        guard = REPLSecurityGuard(additional_blocked_builtins={"my_dangerous_func"})
        code = "my_dangerous_func()"

        result = guard.validate_code(code)

        assert not result.is_valid
        assert any("my_dangerous_func" in v for v in result.violations)


class TestCodeValidationResult:
    """Tests for CodeValidationResult dataclass."""

    def test_to_audit_dict(self):
        """Test conversion to audit dictionary."""
        result = CodeValidationResult(
            is_valid=False,
            violations=["violation1", "violation2"],
            code_hash="hash123",
            validated_at="2026-01-04T12:00:00Z",
            code_length=500,
            ast_node_count=100,
        )

        audit_dict = result.to_audit_dict()

        assert audit_dict["is_valid"] is False
        assert audit_dict["violation_count"] == 2
        assert audit_dict["code_hash"] == "hash123"
        assert audit_dict["code_length"] == 500
        assert audit_dict["ast_node_count"] == 100

    def test_audit_dict_limits_violations(self):
        """Test that audit dict limits number of violations."""
        violations = [f"violation{i}" for i in range(20)]
        result = CodeValidationResult(
            is_valid=False,
            violations=violations,
            code_hash="hash123",
            validated_at="2026-01-04T12:00:00Z",
        )

        audit_dict = result.to_audit_dict()

        assert len(audit_dict["violations"]) <= 10
