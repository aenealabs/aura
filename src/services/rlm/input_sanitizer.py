"""
RLM Input Sanitizer - Prevents prompt injection attacks.

Addresses Critical Issue C4 from ADR-051 architectural review:
Input sanitization needed to prevent prompt injection in RLM REPL.

Prompt injection in RLM context could:
1. Inject malicious Python code into the decomposition prompt
2. Override helper function definitions
3. Escape the restricted execution environment
4. Manipulate context variables

Reference: ADR-051 Recursive Context Scaling and Embedding Prediction
"""

import html
import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SanitizationResult:
    """Result of input sanitization."""

    sanitized_text: str
    original_length: int
    sanitized_length: int
    modifications: list[str]
    is_safe: bool
    blocked_patterns_found: list[str] = field(default_factory=list)

    def to_audit_dict(self) -> dict[str, Any]:
        """Convert to dictionary for audit logging."""
        return {
            "original_length": self.original_length,
            "sanitized_length": self.sanitized_length,
            "modification_count": len(self.modifications),
            "is_safe": self.is_safe,
            "blocked_patterns_count": len(self.blocked_patterns_found),
        }


class InputSanitizer:
    """
    Sanitizes user inputs to prevent prompt injection attacks.

    This class implements pattern-based detection and sanitization for
    inputs that will be used in RLM decomposition prompts.

    Attributes:
        max_context_size: Maximum allowed context size in characters
        max_task_size: Maximum allowed task description size

    Example:
        sanitizer = InputSanitizer()

        # Sanitize task description
        task_result = sanitizer.sanitize_task(user_task)
        if not task_result.is_safe:
            raise SecurityError("Task contains blocked patterns")

        # Create safe prompt
        prompt = sanitizer.create_safe_prompt(
            context=large_codebase,
            task=task_result.sanitized_text,
            context_length_hint=len(large_codebase)
        )
    """

    # Patterns that could be used for prompt injection
    # Format: (pattern, replacement, description)
    INJECTION_PATTERNS: list[tuple[str, str, str]] = [
        # Code block escapes
        (r"```python", "[CODE_BLOCK]", "Code block start"),
        (r"```\w*", "[CODE_BLOCK]", "Generic code block"),
        (r"```", "[END_BLOCK]", "Code block end"),
        # Prompt manipulation - instruction overrides
        (
            r"ignore\s+(?:all\s+)?previous\s+instructions?",
            "[BLOCKED]",
            "Instruction override attempt",
        ),
        (
            r"ignore\s+(?:all\s+)?(?:the\s+)?above",
            "[BLOCKED]",
            "Instruction override attempt",
        ),
        (r"disregard\s+previous", "[BLOCKED]", "Instruction override attempt"),
        (r"forget\s+(?:all\s+)?previous", "[BLOCKED]", "Instruction override attempt"),
        (r"override\s+instructions?", "[BLOCKED]", "Instruction override attempt"),
        (r"new\s+instructions?\s*:", "[BLOCKED]", "Instruction injection"),
        (r"actual\s+instructions?\s*:", "[BLOCKED]", "Instruction injection"),
        (r"real\s+instructions?\s*:", "[BLOCKED]", "Instruction injection"),
        (r"updated?\s+instructions?\s*:", "[BLOCKED]", "Instruction injection"),
        # System prompt injection
        (r"system\s*:", "[BLOCKED]", "System prompt injection"),
        (r"<system>", "[BLOCKED]", "System tag injection"),
        (r"</system>", "[BLOCKED]", "System tag injection"),
        (r"\[system\]", "[BLOCKED]", "System bracket injection"),
        (r"\[/system\]", "[BLOCKED]", "System bracket injection"),
        (r"<\|system\|>", "[BLOCKED]", "System delimiter injection"),
        (r"<\|user\|>", "[BLOCKED]", "Role delimiter injection"),
        (r"<\|assistant\|>", "[BLOCKED]", "Role delimiter injection"),
        # Python code injection via helper function override
        (r"def\s+context_search", "[BLOCKED_FUNC]", "Helper function override"),
        (r"def\s+context_chunk", "[BLOCKED_FUNC]", "Helper function override"),
        (r"def\s+recursive_call", "[BLOCKED_FUNC]", "Helper function override"),
        (r"def\s+aggregate_results", "[BLOCKED_FUNC]", "Helper function override"),
        # Variable manipulation
        (r"CONTEXT\s*=", "[BLOCKED_VAR]", "Context variable override"),
        (r"TASK\s*=", "[BLOCKED_VAR]", "Task variable override"),
        (r"__builtins__", "[BLOCKED]", "Builtins access"),
        (r"__globals__", "[BLOCKED]", "Globals access"),
        (r"__import__", "[BLOCKED]", "Import injection"),
        (r"__class__", "[BLOCKED]", "Class access"),
        (r"__mro__", "[BLOCKED]", "MRO access"),
        (r"__subclasses__", "[BLOCKED]", "Subclasses access"),
        # Escape sequences that could be used for obfuscation
        (r"\\x[0-9a-fA-F]{2}", "[HEX]", "Hex escape"),
        (r"\\u[0-9a-fA-F]{4}", "[UNICODE]", "Unicode escape"),
        (r"\\U[0-9a-fA-F]{8}", "[UNICODE]", "Wide unicode escape"),
        # Role-playing attacks
        (r"you\s+are\s+now", "[BLOCKED]", "Role reassignment"),
        (r"pretend\s+(?:you(?:'re|are)|to\s+be)", "[BLOCKED]", "Role-playing attack"),
        (r"act\s+as\s+(?:if|a)", "[BLOCKED]", "Role-playing attack"),
        (r"simulate\s+being", "[BLOCKED]", "Role-playing attack"),
        # Output manipulation
        (r"output\s*:", "[BLOCKED]", "Output manipulation"),
        (r"result\s*:", "[BLOCKED]", "Result manipulation"),
        (r"response\s*:", "[BLOCKED]", "Response manipulation"),
        # XML/JSON injection for structured outputs
        (r"<\?xml", "[BLOCKED]", "XML declaration injection"),
        (r"<!\[CDATA\[", "[BLOCKED]", "CDATA injection"),
        (r'{"__proto__"', "[BLOCKED]", "Prototype pollution"),
    ]

    # Maximum input sizes
    MAX_CONTEXT_SIZE: int = 50_000_000  # 50MB max context
    MAX_TASK_SIZE: int = 10_000  # 10KB max task description

    # Control characters to remove (keep tabs, newlines, carriage returns)
    CONTROL_CHARS: str = "".join(chr(i) for i in range(32) if i not in (9, 10, 13))

    def __init__(
        self,
        max_context_size: int | None = None,
        max_task_size: int | None = None,
        additional_patterns: list[tuple[str, str, str]] | None = None,
    ):
        """
        Initialize the input sanitizer.

        Args:
            max_context_size: Override default max context size
            max_task_size: Override default max task size
            additional_patterns: Extra injection patterns to check
        """
        self._max_context_size = max_context_size or self.MAX_CONTEXT_SIZE
        self._max_task_size = max_task_size or self.MAX_TASK_SIZE

        # Compile all patterns for efficiency
        patterns = list(self.INJECTION_PATTERNS)
        if additional_patterns:
            patterns.extend(additional_patterns)

        self._compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), replacement, description)
            for pattern, replacement, description in patterns
        ]

    def sanitize_context(self, context: str) -> SanitizationResult:
        """
        Sanitize context input.

        Context is large and may contain code, so we apply lighter sanitization:
        1. Limit size
        2. Remove null bytes
        3. Log but don't block code patterns (context may legitimately contain code)

        The security comes from the RestrictedPython execution environment,
        not from sanitizing the context.

        Args:
            context: The context text to sanitize

        Returns:
            SanitizationResult with sanitized context
        """
        modifications: list[str] = []
        original_length = len(context)
        sanitized = context

        # Size limit
        if len(sanitized) > self._max_context_size:
            sanitized = sanitized[: self._max_context_size]
            modifications.append(
                f"Truncated from {original_length} to {self._max_context_size}"
            )

        # Remove null bytes (can break string handling)
        if "\x00" in sanitized:
            sanitized = sanitized.replace("\x00", "")
            modifications.append("Removed null bytes")

        # Note: We don't heavily sanitize context as it may legitimately contain code
        # The security comes from the RestrictedPython execution environment

        result = SanitizationResult(
            sanitized_text=sanitized,
            original_length=original_length,
            sanitized_length=len(sanitized),
            modifications=modifications,
            is_safe=True,  # Context is always considered safe (security via execution)
            blocked_patterns_found=[],
        )

        logger.debug(
            "Context sanitization completed",
            extra={
                "event_type": "rlm_context_sanitization",
                **result.to_audit_dict(),
            },
        )

        return result

    def sanitize_task(self, task: str) -> SanitizationResult:
        """
        Sanitize task description.

        Task descriptions should be natural language, not code.
        We apply strict sanitization to prevent injection attacks.

        Args:
            task: The task description to sanitize

        Returns:
            SanitizationResult with sanitized task
        """
        modifications: list[str] = []
        blocked_patterns: list[str] = []
        original_length = len(task)
        sanitized = task

        # Size limit
        if len(sanitized) > self._max_task_size:
            sanitized = sanitized[: self._max_task_size]
            modifications.append(
                f"Truncated from {original_length} to {self._max_task_size}"
            )

        # Apply injection pattern filters
        for pattern, replacement, description in self._compiled_patterns:
            if pattern.search(sanitized):
                sanitized = pattern.sub(replacement, sanitized)
                modifications.append(f"Blocked: {description}")
                blocked_patterns.append(description)

        # Remove control characters (except newlines and tabs)
        original_sanitized = sanitized
        sanitized = "".join(c for c in sanitized if c not in self.CONTROL_CHARS)
        if sanitized != original_sanitized:
            modifications.append("Removed control characters")

        # Escape HTML entities to prevent XSS if displayed
        html_escaped = html.escape(sanitized)
        if html_escaped != sanitized:
            sanitized = html_escaped
            modifications.append("Escaped HTML entities")

        # Determine if safe (no blocked patterns found)
        is_safe = len(blocked_patterns) == 0

        result = SanitizationResult(
            sanitized_text=sanitized,
            original_length=original_length,
            sanitized_length=len(sanitized),
            modifications=modifications,
            is_safe=is_safe,
            blocked_patterns_found=blocked_patterns,
        )

        log_level = logging.WARNING if not is_safe else logging.DEBUG
        logger.log(
            log_level,
            "Task sanitization completed",
            extra={
                "event_type": "rlm_task_sanitization",
                **result.to_audit_dict(),
            },
        )

        return result

    def create_safe_prompt(
        self,
        context: str,
        task: str,
        context_length_hint: int,
    ) -> str:
        """
        Create a sanitized prompt with clear structural delimiters.

        Uses XML-like tags that the LLM understands as structure,
        making injection attacks more difficult.

        Args:
            context: The context (already sanitized via sanitize_context)
            task: The task description (already sanitized via sanitize_task)
            context_length_hint: Hint about total context size

        Returns:
            Safely structured prompt

        Raises:
            ValueError: If task contains blocked patterns
        """
        # Sanitize inputs (context sanitization runs for side effects like logging)
        self.sanitize_context(context)
        task_result = self.sanitize_task(task)

        if not task_result.is_safe:
            raise ValueError(
                f"Task contains blocked patterns: {task_result.blocked_patterns_found}"
            )

        # Build prompt with clear structure
        prompt = f"""<rlm_decomposition_task>
<instructions>
You have access to a Python REPL environment. Generate Python code to complete the TASK
by examining and decomposing the CONTEXT. Only use the provided helper functions.

AVAILABLE FUNCTIONS:
- context_search(pattern: str) -> List[Match]: Search CONTEXT for regex pattern
- context_chunk(start: int, end: int) -> str: Get a slice of CONTEXT
- recursive_call(sub_context: str, sub_task: str) -> str: Recursively process a sub-problem
- aggregate_results(results: List[str]) -> str: Combine multiple results

RULES:
1. Only use the functions listed above
2. Do not define new functions named context_search, context_chunk, recursive_call, or aggregate_results
3. The final expression should be the result (no print statement needed)
4. Do not use import statements
5. Do not access __builtins__, __globals__, or dunder attributes
6. Do not try to override or modify any variables named CONTEXT or TASK
</instructions>

<context_metadata>
Total characters: {context_length_hint}
Stored in variable: CONTEXT
</context_metadata>

<task>
{task_result.sanitized_text}
</task>

<code_output>
Write your Python code below:
</code_output>
</rlm_decomposition_task>"""

        return prompt

    def validate_task_safety(self, task: str) -> tuple[bool, list[str]]:
        """
        Validate task safety without modifying it.

        Useful for pre-validation before accepting user input.

        Args:
            task: The task description to validate

        Returns:
            Tuple of (is_safe, list of blocked pattern descriptions)
        """
        blocked_patterns: list[str] = []

        for pattern, _, description in self._compiled_patterns:
            if pattern.search(task):
                blocked_patterns.append(description)

        return len(blocked_patterns) == 0, blocked_patterns

    def extract_safe_code_blocks(self, text: str) -> list[str]:
        """
        Extract code blocks from text safely.

        Useful for processing LLM responses that may contain code.

        Args:
            text: Text potentially containing code blocks

        Returns:
            List of extracted code blocks
        """
        # Match markdown code blocks
        pattern = r"```(?:python)?\s*\n(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)

        # Also match indented code blocks (4 spaces)
        indented_pattern = r"(?:^|\n)((?:    .+\n?)+)"
        indented_matches = re.findall(indented_pattern, text)

        all_blocks = matches + indented_matches

        # Clean up each block
        cleaned_blocks = []
        for block in all_blocks:
            # Remove leading/trailing whitespace
            block = block.strip()
            # Skip empty blocks
            if block:
                cleaned_blocks.append(block)

        return cleaned_blocks

    def create_audit_record(
        self,
        request_id: str,
        context_result: SanitizationResult,
        task_result: SanitizationResult,
    ) -> dict[str, Any]:
        """
        Create an audit record for sanitization operations.

        Args:
            request_id: Unique request identifier
            context_result: Context sanitization result
            task_result: Task sanitization result

        Returns:
            Audit record dictionary
        """
        return {
            "event_type": "rlm_input_sanitization",
            "request_id": request_id,
            "context": context_result.to_audit_dict(),
            "task": task_result.to_audit_dict(),
            "overall_safe": context_result.is_safe and task_result.is_safe,
            "total_modifications": (
                len(context_result.modifications) + len(task_result.modifications)
            ),
        }
