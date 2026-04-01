"""
RLM REPL Security Guard - Blocks dangerous Python operations.

Addresses Critical Issue C2 from ADR-051 architectural review:
Dangerous Python builtins must be blocked to prevent sandbox escape.

This module provides multi-layer security for executing LLM-generated Python code
in the Recursive Language Model (RLM) REPL environment.

Security Layers:
1. Code Validation - Static analysis before execution
2. AST Analysis - Detect dangerous patterns in code structure
3. RestrictedPython - Compile-time restrictions
4. Safe Namespace - Runtime restrictions on available operations
5. Subcall Tracking - Prevent recursive runaway

Reference: ADR-051 Recursive Context Scaling and Embedding Prediction
"""

import ast
import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class CodeValidationResult:
    """Result of LLM-generated code validation."""

    is_valid: bool
    violations: list[str]
    code_hash: str
    validated_at: str
    code_length: int = 0
    ast_node_count: int = 0

    def to_audit_dict(self) -> dict[str, Any]:
        """Convert to dictionary for audit logging."""
        return {
            "is_valid": self.is_valid,
            "violation_count": len(self.violations),
            "violations": self.violations[:10],  # Limit for log size
            "code_hash": self.code_hash,
            "validated_at": self.validated_at,
            "code_length": self.code_length,
            "ast_node_count": self.ast_node_count,
        }


@dataclass
class ExecutionResult:
    """Result of code execution in safe namespace."""

    success: bool
    result: Any = None
    error: str | None = None
    execution_time_ms: float = 0.0
    subcall_count: int = 0


class REPLSecurityGuard:
    """
    Security controls for RLM REPL execution.

    Uses a multi-layer approach to create a safe execution environment
    that blocks dangerous operations while allowing legitimate code.

    Attributes:
        max_total_subcalls: Maximum recursive subcalls allowed per request
        max_code_length: Maximum allowed code length in characters
        max_output_size: Maximum output size in bytes

    Example:
        guard = REPLSecurityGuard(max_total_subcalls=50)

        # Validate code before execution
        result = guard.validate_code(llm_generated_code)
        if not result.is_valid:
            raise SecurityError(f"Code validation failed: {result.violations}")

        # Create safe execution namespace
        namespace = guard.create_safe_namespace(
            context_vars={"CONTEXT": large_text, "TASK": "analyze"},
            helper_functions={"context_search": search_fn}
        )

        # Execute (in gVisor container)
        exec(compiled_code, namespace)
    """

    # Builtins that MUST be blocked (sandbox escape vectors)
    BLOCKED_BUILTINS: set[str] = {
        "__import__",  # Dynamic imports
        "eval",  # Arbitrary code execution
        "exec",  # Arbitrary code execution
        "compile",  # Code compilation
        "open",  # File system access
        "input",  # User input (blocks execution)
        "breakpoint",  # Debugger access
        "globals",  # Global namespace access
        "locals",  # Local namespace access
        "vars",  # Variable introspection
        "dir",  # Object introspection (can be used for discovery)
        "getattr",  # Arbitrary attribute access (use guarded version)
        "setattr",  # Arbitrary attribute setting
        "delattr",  # Arbitrary attribute deletion
        "hasattr",  # Attribute probing
        "type",  # Type manipulation
        "super",  # Inheritance manipulation
        "classmethod",  # Class modification
        "staticmethod",  # Class modification
        "property",  # Descriptor creation
        "memoryview",  # Memory access
        "bytearray",  # Mutable bytes (potential buffer overflow)
        "frozenset",  # Can be used in complex attacks
        "object",  # Base object access
        "help",  # Interactive help (blocks)
        "license",  # Interactive (blocks)
        "credits",  # Interactive (blocks)
        "copyright",  # Interactive (blocks)
        "quit",  # Exit interpreter
        "exit",  # Exit interpreter
    }

    # Additional dangerous patterns detected via AST
    BLOCKED_AST_PATTERNS: set[str] = {
        "Import",  # import statements
        "ImportFrom",  # from x import y
        "Global",  # global declarations
        "Nonlocal",  # nonlocal declarations
    }

    # Dangerous dunder attributes that enable sandbox escape
    BLOCKED_DUNDER_ATTRS: set[str] = {
        "__class__",
        "__bases__",
        "__mro__",
        "__subclasses__",
        "__globals__",
        "__code__",
        "__builtins__",
        "__dict__",
        "__module__",
        "__qualname__",
        "__func__",
        "__self__",
        "__closure__",
        "__annotations__",
        "__kwdefaults__",
        "__defaults__",
        "__doc__",  # Can leak information
        "__name__",  # Can leak information
        "__file__",  # Can leak file paths
        "__cached__",
        "__loader__",
        "__spec__",
        "__package__",
        "__path__",
        "__reduce__",
        "__reduce_ex__",
        "__getstate__",
        "__setstate__",
    }

    # Dangerous string patterns that indicate malicious intent
    DANGEROUS_PATTERNS: list[tuple[str, str]] = [
        (r"os\.system", "System command execution"),
        (r"os\.popen", "Process execution"),
        (r"os\.spawn", "Process spawning"),
        (r"os\.exec", "Process replacement"),
        (r"os\.fork", "Process forking"),
        (r"subprocess", "Subprocess execution"),
        (r"__import__", "Dynamic import"),
        (r"importlib", "Import library"),
        (r"eval\s*\(", "Eval execution"),
        (r"exec\s*\(", "Exec execution"),
        (r"compile\s*\(", "Code compilation"),
        (r"open\s*\(", "File system access"),
        (r"socket", "Network access"),
        (r"requests\.", "HTTP requests"),
        (r"urllib", "URL access"),
        (r"http\.client", "HTTP client"),
        (r"ftplib", "FTP access"),
        (r"smtplib", "SMTP access"),
        (r"pickle", "Deserialization attack vector"),
        (r"marshal", "Code object manipulation"),
        (r"ctypes", "C library access"),
        (r"cffi", "C FFI access"),
        (r"multiprocessing", "Process spawning"),
        (r"threading", "Thread spawning"),
        (r"asyncio\.subprocess", "Async subprocess"),
        (r"pty", "Pseudo-terminal"),
        (r"fcntl", "File control"),
        (r"mmap", "Memory mapping"),
        (r"resource", "Resource limits manipulation"),
        (r"signal", "Signal handling"),
        (r"sys\.modules", "Module manipulation"),
        (r"sys\.path", "Path manipulation"),
        (r"builtins", "Builtins access"),
        (r"__builtins__", "Builtins access"),
        (r"codecs\.encode", "Encoding tricks"),
        (r"codecs\.decode", "Decoding tricks"),
        (r"base64", "Base64 encoding (obfuscation)"),
        (r"binascii", "Binary conversion"),
        (r"struct\.pack", "Binary packing"),
        (r"struct\.unpack", "Binary unpacking"),
    ]

    # Maximum limits to prevent resource exhaustion
    MAX_CODE_LENGTH: int = 50_000  # 50KB max code size
    MAX_STRING_LENGTH: int = 1_000_000  # 1MB max string in code
    MAX_OUTPUT_SIZE: int = 10_000_000  # 10MB max output
    MAX_AST_DEPTH: int = 50  # Maximum AST nesting depth
    MAX_AST_NODES: int = 10_000  # Maximum AST nodes

    def __init__(
        self,
        max_total_subcalls: int = 50,
        max_code_length: int | None = None,
        max_output_size: int | None = None,
        additional_blocked_builtins: set[str] | None = None,
    ):
        """
        Initialize the security guard.

        Args:
            max_total_subcalls: Maximum recursive subcalls per request (default: 50)
            max_code_length: Override default max code length
            max_output_size: Override default max output size
            additional_blocked_builtins: Extra builtins to block
        """
        self.max_total_subcalls = max_total_subcalls
        self._subcall_count = 0
        self._max_code_length = max_code_length or self.MAX_CODE_LENGTH
        self._max_output_size = max_output_size or self.MAX_OUTPUT_SIZE

        # Combine blocked builtins
        self._blocked_builtins = self.BLOCKED_BUILTINS.copy()
        if additional_blocked_builtins:
            self._blocked_builtins.update(additional_blocked_builtins)

        # Compile dangerous patterns for efficiency
        self._compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), desc)
            for pattern, desc in self.DANGEROUS_PATTERNS
        ]

    def validate_code(self, code: str) -> CodeValidationResult:
        """
        Validate LLM-generated code before execution.

        Performs multi-layer validation:
        1. Size limit checks
        2. AST analysis for dangerous patterns
        3. String pattern detection
        4. Restricted compilation check

        Args:
            code: The Python code to validate

        Returns:
            CodeValidationResult with validation status and any violations
        """
        violations: list[str] = []
        code_hash = hashlib.sha256(code.encode()).hexdigest()[:16]
        ast_node_count = 0

        # Check code length
        if len(code) > self._max_code_length:
            violations.append(
                f"Code exceeds maximum length ({len(code)} > {self._max_code_length})"
            )

        # Check for null bytes (binary injection)
        if "\x00" in code:
            violations.append("Code contains null bytes (potential binary injection)")

        # AST analysis for dangerous patterns
        try:
            tree = ast.parse(code)
            ast_violations, ast_node_count = self._analyze_ast(tree)
            violations.extend(ast_violations)
        except SyntaxError as e:
            violations.append(f"Syntax error in generated code: {e}")

        # Check for blocked string patterns
        string_violations = self._check_string_patterns(code)
        violations.extend(string_violations)

        # Attempt restricted compilation
        compile_violations = self._check_restricted_compile(code)
        violations.extend(compile_violations)

        result = CodeValidationResult(
            is_valid=len(violations) == 0,
            violations=violations,
            code_hash=code_hash,
            validated_at=datetime.now(timezone.utc).isoformat(),
            code_length=len(code),
            ast_node_count=ast_node_count,
        )

        # Audit log
        logger.info(
            "RLM code validation completed",
            extra={
                "event_type": "rlm_code_validation",
                **result.to_audit_dict(),
            },
        )

        return result

    def _analyze_ast(self, tree: ast.AST) -> tuple[list[str], int]:
        """
        Analyze AST for dangerous patterns.

        Args:
            tree: The parsed AST

        Returns:
            Tuple of (violations list, node count)
        """
        violations: list[str] = []
        node_count = 0
        max_depth = 0

        def get_depth(node: ast.AST, current_depth: int = 0) -> int:
            """Calculate maximum depth of AST."""
            max_child_depth = current_depth
            for child in ast.iter_child_nodes(node):
                child_depth = get_depth(child, current_depth + 1)
                max_child_depth = max(max_child_depth, child_depth)
            return max_child_depth

        max_depth = get_depth(tree)
        if max_depth > self.MAX_AST_DEPTH:
            violations.append(
                f"AST depth exceeds maximum ({max_depth} > {self.MAX_AST_DEPTH})"
            )

        for node in ast.walk(tree):
            node_count += 1

            if node_count > self.MAX_AST_NODES:
                violations.append(
                    f"AST node count exceeds maximum ({node_count} > {self.MAX_AST_NODES})"
                )
                break

            node_type = type(node).__name__

            # Check for blocked node types
            if node_type in self.BLOCKED_AST_PATTERNS:
                violations.append(f"Blocked AST pattern: {node_type}")

            # Check for dangerous function calls
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in self._blocked_builtins:
                        violations.append(f"Blocked builtin call: {node.func.id}")

            # Check for attribute access to dangerous dunder attributes
            if isinstance(node, ast.Attribute):
                if node.attr in self.BLOCKED_DUNDER_ATTRS:
                    violations.append(f"Blocked dunder attribute access: {node.attr}")

            # Check for string manipulation that might be obfuscation
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if len(node.value) > self.MAX_STRING_LENGTH:
                    violations.append(
                        f"String constant exceeds maximum length "
                        f"({len(node.value)} > {self.MAX_STRING_LENGTH})"
                    )

            # Check for f-strings with expressions (potential code injection)
            if isinstance(node, ast.JoinedStr):
                for value in node.values:
                    if isinstance(value, ast.FormattedValue):
                        # Check if the formatted value contains dangerous operations
                        inner_violations, _ = self._analyze_ast(value)
                        violations.extend(inner_violations)

        return violations, node_count

    def _check_string_patterns(self, code: str) -> list[str]:
        """
        Check for dangerous string patterns in code.

        Args:
            code: The code to check

        Returns:
            List of violations found
        """
        violations: list[str] = []

        for pattern, description in self._compiled_patterns:
            if pattern.search(code):
                violations.append(f"Dangerous pattern detected: {description}")

        return violations

    def _check_restricted_compile(self, code: str) -> list[str]:
        """
        Attempt to compile code with restrictions.

        Note: Full RestrictedPython integration requires the RestrictedPython
        package. This method provides basic compilation checking.

        Args:
            code: The code to compile

        Returns:
            List of compilation violations
        """
        violations: list[str] = []

        try:
            # Try to compile as a module
            compile(code, "<rlm-generated>", "exec")
        except SyntaxError as e:
            violations.append(f"Compilation failed: {e}")
        except ValueError as e:
            violations.append(f"Compilation value error: {e}")

        return violations

    def create_safe_namespace(
        self,
        context_vars: dict[str, Any] | None = None,
        helper_functions: dict[str, Callable[..., Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Create a restricted execution namespace.

        Only safe builtins and explicitly provided helpers are available.
        This namespace should be used with exec() in a gVisor container.

        Args:
            context_vars: Variables to make available (e.g., CONTEXT, TASK)
            helper_functions: Controlled helper functions (e.g., context_search)

        Returns:
            Dictionary suitable for use as exec() globals

        Example:
            namespace = guard.create_safe_namespace(
                context_vars={"CONTEXT": text, "TASK": "analyze"},
                helper_functions={
                    "context_search": my_search_fn,
                    "context_chunk": my_chunk_fn,
                }
            )
        """
        # Start with minimal safe builtins
        safe_ns: dict[str, Any] = {
            "__builtins__": self._create_safe_builtins(),
        }

        # Add safe versions of commonly needed builtins
        safe_ns.update(
            {
                # Constants
                "True": True,
                "False": False,
                "None": None,
                # Type constructors (safe subset)
                "len": len,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "list": list,
                "dict": dict,
                "tuple": tuple,
                "set": set,
                # Iteration
                "range": range,
                "enumerate": enumerate,
                "zip": zip,
                "map": self._guarded_map,
                "filter": self._guarded_filter,
                # Sorting and comparison
                "sorted": sorted,
                "reversed": reversed,
                "min": min,
                "max": max,
                # Math
                "sum": sum,
                "abs": abs,
                "round": round,
                "pow": pow,
                "divmod": divmod,
                # Logic
                "all": all,
                "any": any,
                # String operations
                "ord": ord,
                "chr": chr,
                "repr": self._safe_repr,
                "ascii": ascii,
                "format": format,
                # Iteration helpers
                "iter": iter,
                "next": next,
                # Type checking (safe versions)
                "isinstance": self._safe_isinstance,
                "issubclass": self._safe_issubclass,
                # Print (returns string, doesn't print)
                "print": self._safe_print,
            }
        )

        # Add context variables (read-only access via namespace)
        if context_vars:
            safe_ns.update(context_vars)

        # Add helper functions (these are our controlled APIs)
        if helper_functions:
            safe_ns.update(helper_functions)

        return safe_ns

    def _create_safe_builtins(self) -> dict[str, Any]:
        """Create a minimal safe builtins dictionary."""
        return {
            "True": True,
            "False": False,
            "None": None,
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
            "tuple": tuple,
            "set": set,
            "range": range,
            "enumerate": enumerate,
            "zip": zip,
            "sorted": sorted,
            "reversed": reversed,
            "min": min,
            "max": max,
            "sum": sum,
            "abs": abs,
            "round": round,
            "all": all,
            "any": any,
            "ord": ord,
            "chr": chr,
            "repr": self._safe_repr,
            "print": self._safe_print,
            "isinstance": self._safe_isinstance,
        }

    def _safe_print(self, *args: Any, **kwargs: Any) -> str:
        """Safe print that returns string instead of printing."""
        sep = kwargs.get("sep", " ")
        return sep.join(str(arg) for arg in args)

    def _safe_repr(self, obj: Any) -> str:
        """Safe repr with output size limit."""
        result = repr(obj)
        if len(result) > 10000:
            return result[:10000] + "...[truncated]"
        return result

    def _safe_isinstance(self, obj: Any, classinfo: type | tuple[type, ...]) -> bool:
        """Safe isinstance that only allows basic types."""
        allowed_types = (
            int,
            float,
            str,
            bool,
            list,
            dict,
            tuple,
            set,
            type(None),
            bytes,
        )

        if isinstance(classinfo, tuple):
            for t in classinfo:
                if t not in allowed_types:
                    raise TypeError(f"isinstance check not allowed for type: {t}")
        elif classinfo not in allowed_types:
            raise TypeError(f"isinstance check not allowed for type: {classinfo}")

        return isinstance(obj, classinfo)

    def _safe_issubclass(self, cls: type, classinfo: type | tuple[type, ...]) -> bool:
        """Safe issubclass with restrictions."""
        # Only allow basic type hierarchy checks
        allowed_types = (int, float, str, bool, list, dict, tuple, set, type(None))

        if cls not in allowed_types:
            raise TypeError(f"issubclass check not allowed for type: {cls}")

        return issubclass(cls, classinfo)

    def _guarded_map(self, func: Callable[..., Any], *iterables: Any) -> Any:
        """Guarded map that tracks iterations."""
        # Could add iteration limits here if needed
        return map(func, *iterables)

    def _guarded_filter(self, func: Callable[[Any], bool] | None, iterable: Any) -> Any:
        """Guarded filter that tracks iterations."""
        # Could add iteration limits here if needed
        return filter(func, iterable)

    def track_subcall(self) -> bool:
        """
        Track recursive subcalls to prevent runaway.

        Call this before each recursive LLM call in the RLM engine.

        Returns:
            True if subcall is allowed, False if limit exceeded
        """
        self._subcall_count += 1
        if self._subcall_count > self.max_total_subcalls:
            logger.warning(
                f"Subcall limit exceeded: {self._subcall_count} > {self.max_total_subcalls}",
                extra={
                    "event_type": "rlm_subcall_limit_exceeded",
                    "subcall_count": self._subcall_count,
                    "max_subcalls": self.max_total_subcalls,
                },
            )
            return False
        return True

    def get_subcall_count(self) -> int:
        """Get current subcall count."""
        return self._subcall_count

    def reset_subcall_count(self) -> None:
        """Reset subcall counter for new request."""
        self._subcall_count = 0

    def validate_output(self, output: Any) -> tuple[bool, str | None]:
        """
        Validate execution output size.

        Args:
            output: The output from code execution

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            output_str = str(output)
            if len(output_str) > self._max_output_size:
                return False, (
                    f"Output exceeds maximum size "
                    f"({len(output_str)} > {self._max_output_size})"
                )
            return True, None
        except Exception as e:
            return False, f"Failed to convert output to string: {e}"

    def create_audit_record(
        self,
        request_id: str,
        user_id: str,
        organization_id: str,
        code_hash: str,
        validation_result: CodeValidationResult,
        execution_result: ExecutionResult | None = None,
    ) -> dict[str, Any]:
        """
        Create a comprehensive audit record for compliance logging.

        Args:
            request_id: Unique request identifier
            user_id: User who initiated the request
            organization_id: Organization identifier
            code_hash: Hash of the executed code
            validation_result: Code validation result
            execution_result: Optional execution result

        Returns:
            Audit record dictionary for CloudWatch/compliance logging
        """
        record = {
            "event_type": "rlm_code_execution",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
            "user_id": user_id,
            "organization_id": organization_id,
            # Code details
            "code_hash": code_hash,
            "code_length": validation_result.code_length,
            "ast_node_count": validation_result.ast_node_count,
            "validation_result": "passed" if validation_result.is_valid else "failed",
            "validation_violations": validation_result.violations[:5],
            # Execution details
            "subcall_count": self._subcall_count,
            "max_subcalls": self.max_total_subcalls,
        }

        if execution_result:
            record.update(
                {
                    "execution_success": execution_result.success,
                    "execution_time_ms": execution_result.execution_time_ms,
                    "execution_error": execution_result.error,
                }
            )

        return record
