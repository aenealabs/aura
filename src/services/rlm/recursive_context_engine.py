"""
Recursive Context Engine - Core RLM decomposition logic.

Enables 100x context scaling by using LLM-generated Python code to
recursively decompose large contexts into manageable sub-problems.

Based on MIT CSAIL "Recursive Language Models" research (December 2025).

Reference: ADR-051 Recursive Context Scaling and Embedding Prediction
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from src.services.rlm.input_sanitizer import InputSanitizer
from src.services.rlm.security_guard import (
    CodeValidationResult,
    ExecutionResult,
    REPLSecurityGuard,
)

logger = logging.getLogger(__name__)


class LLMService(Protocol):
    """Protocol for LLM service integration."""

    async def generate(self, prompt: str, max_tokens: int = 2000) -> str:
        """Generate text from prompt."""
        ...


@dataclass
class Match:
    """Represents a search match in the context."""

    text: str
    start: int
    end: int
    line_number: int | None = None

    def __repr__(self) -> str:
        return f"Match(start={self.start}, end={self.end}, text={self.text[:50]}...)"


@dataclass
class RLMConfig:
    """Configuration for the Recursive Context Engine."""

    # Context limits
    base_context_size: int = 100_000  # Process directly if under this size
    max_context_size: int = 50_000_000  # 50MB absolute max

    # Recursion limits
    max_recursion_depth: int = 10
    max_total_subcalls: int = 50

    # Execution limits
    max_code_length: int = 10_000
    max_output_size: int = 100_000
    execution_timeout_seconds: float = 30.0

    # LLM settings
    max_llm_tokens: int = 2000
    temperature: float = 0.0  # Deterministic for code generation

    # Search settings
    max_search_results: int = 1000


@dataclass
class RLMResult:
    """Result of an RLM decomposition execution."""

    success: bool
    result: str | None
    error: str | None = None

    # Metrics
    recursion_depth: int = 0
    total_subcalls: int = 0
    total_execution_time_ms: float = 0.0
    context_size: int = 0

    # Code execution details
    generated_code: str | None = None
    code_validation: CodeValidationResult | None = None
    execution_result: ExecutionResult | None = None

    # Audit trail
    request_id: str | None = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_audit_dict(self) -> dict[str, Any]:
        """Convert to dictionary for audit logging."""
        return {
            "success": self.success,
            "recursion_depth": self.recursion_depth,
            "total_subcalls": self.total_subcalls,
            "total_execution_time_ms": self.total_execution_time_ms,
            "context_size": self.context_size,
            "request_id": self.request_id,
            "timestamp": self.timestamp,
            "has_error": self.error is not None,
        }


class RecursiveContextEngine:
    """
    Core engine for Recursive Language Model context decomposition.

    Enables processing of 10M+ token contexts by:
    1. Using LLM to generate Python decomposition code
    2. Executing code safely in restricted environment
    3. Recursively calling itself on sub-problems
    4. Aggregating results from all sub-calls

    Example:
        engine = RecursiveContextEngine(llm_service=bedrock_service)

        result = await engine.process(
            context=massive_codebase,  # 10M+ tokens
            task="Find all security vulnerabilities",
            request_id="req-123",
            user_id="user-456",
            organization_id="org-789",
        )

        if result.success:
            print(result.result)
        else:
            print(f"Error: {result.error}")
    """

    # Decomposition prompt template
    DECOMPOSITION_PROMPT = """You have access to a Python REPL environment. Generate Python code to complete the TASK by examining and decomposing the CONTEXT. Only use the provided helper functions.

CONTEXT SIZE: {context_size} characters
TASK: {task}

AVAILABLE FUNCTIONS:
- context_search(pattern: str) -> List[Match]: Search CONTEXT for regex pattern. Returns Match objects with .text, .start, .end, .line_number
- context_chunk(start: int, end: int) -> str: Get a slice of CONTEXT by character position
- recursive_call(sub_context: str, sub_task: str) -> str: Recursively process a sub-problem (use for chunks > 100K chars)
- aggregate_results(results: List[str]) -> str: Combine multiple results into a coherent summary

RULES:
1. Only use the functions listed above
2. Do not define new functions with these names
3. The final expression should be the result (no print statement needed)
4. Do not use import statements
5. Do not access __builtins__, __globals__, or dunder attributes
6. Break large problems into smaller chunks using recursive_call
7. Use context_search to find relevant sections before chunking

Write Python code to solve the TASK:
```python
"""

    def __init__(
        self,
        llm_service: LLMService,
        config: RLMConfig | None = None,
        security_guard: REPLSecurityGuard | None = None,
        input_sanitizer: InputSanitizer | None = None,
    ):
        """
        Initialize the Recursive Context Engine.

        Args:
            llm_service: LLM service for generating decomposition code
            config: Engine configuration
            security_guard: Custom security guard (uses default if None)
            input_sanitizer: Custom input sanitizer (uses default if None)
        """
        self._llm_service = llm_service
        self._config = config or RLMConfig()
        self._security_guard = security_guard or REPLSecurityGuard(
            max_code_length=self._config.max_code_length,
            max_output_size=self._config.max_output_size,
            max_total_subcalls=self._config.max_total_subcalls,
        )
        self._input_sanitizer = input_sanitizer or InputSanitizer(
            max_context_size=self._config.max_context_size,
        )

        # Recursion tracking (reset per top-level call)
        self._current_depth = 0
        self._subcall_count = 0
        self._start_time: float | None = None

        # Context for current execution
        self._current_context: str = ""
        self._current_request_id: str | None = None

    async def process(
        self,
        context: str,
        task: str,
        request_id: str | None = None,
        user_id: str | None = None,
        organization_id: str | None = None,
    ) -> RLMResult:
        """
        Process a task against a large context using recursive decomposition.

        Args:
            context: The large context to analyze (can be 10M+ characters)
            task: Natural language description of the task
            request_id: Optional request ID for tracing
            user_id: Optional user ID for audit
            organization_id: Optional org ID for audit

        Returns:
            RLMResult with the processed result or error
        """
        self._start_time = time.perf_counter()
        self._current_depth = 0
        self._subcall_count = 0
        self._current_request_id = request_id
        self._security_guard.reset_subcall_count()

        try:
            # Sanitize inputs
            context_result = self._input_sanitizer.sanitize_context(context)
            task_result = self._input_sanitizer.sanitize_task(task)

            if not task_result.is_safe:
                return RLMResult(
                    success=False,
                    result=None,
                    error=f"Task contains blocked patterns: {task_result.blocked_patterns_found}",
                    context_size=len(context),
                    request_id=request_id,
                )

            self._current_context = context_result.sanitized_text

            # Log start of processing
            logger.info(
                "Starting RLM processing",
                extra={
                    "event_type": "rlm_process_start",
                    "request_id": request_id,
                    "context_size": len(self._current_context),
                    "task_length": len(task_result.sanitized_text),
                },
            )

            # Process recursively
            result = await self._process_recursive(
                context=self._current_context,
                task=task_result.sanitized_text,
                depth=0,
            )

            elapsed_ms = (time.perf_counter() - self._start_time) * 1000

            # Create audit record
            if request_id and user_id and organization_id:
                audit_record = self._create_audit_record(
                    request_id=request_id,
                    user_id=user_id,
                    organization_id=organization_id,
                    result=result,
                    elapsed_ms=elapsed_ms,
                )
                logger.info(
                    "RLM processing complete",
                    extra={"event_type": "rlm_process_complete", **audit_record},
                )

            result.total_execution_time_ms = elapsed_ms
            result.total_subcalls = self._subcall_count
            result.context_size = len(self._current_context)
            result.request_id = request_id

            return result

        except Exception as e:
            elapsed_ms = (time.perf_counter() - self._start_time) * 1000
            logger.exception(
                "RLM processing failed",
                extra={
                    "event_type": "rlm_process_error",
                    "request_id": request_id,
                    "error": str(e),
                },
            )
            return RLMResult(
                success=False,
                result=None,
                error=f"Processing failed: {str(e)}",
                total_execution_time_ms=elapsed_ms,
                context_size=len(context),
                request_id=request_id,
            )

    async def _process_recursive(
        self,
        context: str,
        task: str,
        depth: int,
    ) -> RLMResult:
        """
        Internal recursive processing implementation.

        Args:
            context: Context to process
            task: Task to perform
            depth: Current recursion depth

        Returns:
            RLMResult with processing outcome
        """
        # Check recursion depth
        if depth >= self._config.max_recursion_depth:
            return RLMResult(
                success=False,
                result=None,
                error=f"Maximum recursion depth ({self._config.max_recursion_depth}) exceeded",
                recursion_depth=depth,
            )

        # Check subcall limit
        if not self._security_guard.track_subcall():
            return RLMResult(
                success=False,
                result=None,
                error=f"Maximum subcalls ({self._config.max_total_subcalls}) exceeded",
                recursion_depth=depth,
            )

        self._subcall_count += 1
        self._current_depth = max(self._current_depth, depth)

        # If context is small enough, process directly with LLM
        if len(context) <= self._config.base_context_size:
            return await self._process_direct(context, task, depth)

        # Generate decomposition code
        generated_code = await self._generate_decomposition_code(context, task)

        if generated_code is None:
            return RLMResult(
                success=False,
                result=None,
                error="Failed to generate decomposition code",
                recursion_depth=depth,
            )

        # Validate the generated code
        validation_result = self._security_guard.validate_code(generated_code)

        if not validation_result.is_valid:
            return RLMResult(
                success=False,
                result=None,
                error=f"Generated code failed validation: {validation_result.violations}",
                recursion_depth=depth,
                generated_code=generated_code,
                code_validation=validation_result,
            )

        # Execute the code in a safe environment
        execution_result = await self._execute_code(
            code=generated_code,
            context=context,
            task=task,
            depth=depth,
        )

        return RLMResult(
            success=execution_result.success,
            result=execution_result.result if execution_result.success else None,
            error=execution_result.error if not execution_result.success else None,
            recursion_depth=depth,
            generated_code=generated_code,
            code_validation=validation_result,
            execution_result=execution_result,
        )

    async def _process_direct(
        self,
        context: str,
        task: str,
        depth: int,
    ) -> RLMResult:
        """
        Process a small context directly with the LLM (no decomposition needed).

        Args:
            context: Small context to process
            task: Task to perform
            depth: Current recursion depth

        Returns:
            RLMResult with LLM response
        """
        prompt = f"""Analyze the following context and complete the task.

CONTEXT:
{context}

TASK: {task}

Provide a concise, accurate response:"""

        try:
            response = await self._llm_service.generate(
                prompt=prompt,
                max_tokens=self._config.max_llm_tokens,
            )
            return RLMResult(
                success=True,
                result=response,
                recursion_depth=depth,
            )
        except Exception as e:
            return RLMResult(
                success=False,
                result=None,
                error=f"LLM generation failed: {str(e)}",
                recursion_depth=depth,
            )

    async def _generate_decomposition_code(
        self,
        context: str,
        task: str,
    ) -> str | None:
        """
        Generate Python code to decompose the task.

        Args:
            context: Context to analyze
            task: Task to decompose

        Returns:
            Generated Python code or None if generation failed
        """
        prompt = self.DECOMPOSITION_PROMPT.format(
            context_size=len(context),
            task=task,
        )

        try:
            response = await self._llm_service.generate(
                prompt=prompt,
                max_tokens=self._config.max_llm_tokens,
            )

            # Extract code from response
            code = self._extract_code(response)
            return code

        except Exception as e:
            logger.warning(
                "Failed to generate decomposition code",
                extra={
                    "event_type": "rlm_code_generation_failed",
                    "error": str(e),
                    "request_id": self._current_request_id,
                },
            )
            return None

    def _extract_code(self, response: str) -> str:
        """
        Extract Python code from LLM response.

        Args:
            response: Raw LLM response

        Returns:
            Extracted code
        """
        # Try to extract from markdown code block
        code_match = re.search(r"```python\s*(.*?)```", response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()

        # Try generic code block
        code_match = re.search(r"```\s*(.*?)```", response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()

        # Assume entire response is code
        return response.strip()

    async def _execute_code(
        self,
        code: str,
        context: str,
        task: str,
        depth: int,
    ) -> ExecutionResult:
        """
        Execute decomposition code in a safe environment.

        Args:
            code: Validated Python code
            context: Current context
            task: Current task
            depth: Current recursion depth

        Returns:
            ExecutionResult with outcome
        """
        start_time = time.perf_counter()

        # Create helper functions bound to current context
        helper_functions = self._create_helper_functions(context, task, depth)

        # Create context variables
        context_vars = {
            "CONTEXT": context,
            "TASK": task,
            "CONTEXT_SIZE": len(context),
        }

        # Create safe namespace
        namespace = self._security_guard.create_safe_namespace(
            context_vars=context_vars,
            helper_functions=helper_functions,
        )

        try:
            # Compile the code
            compiled = compile(code, "<rlm>", "eval")

            # Execute with timeout
            # nosec B307 - eval is intentional here; code is pre-validated by
            # REPLSecurityGuard.validate_code() and runs in restricted namespace
            result = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: eval(compiled, namespace),  # nosec B307
                ),
                timeout=self._config.execution_timeout_seconds,
            )

            # Validate output size
            result_str = str(result)
            is_valid, error = self._security_guard.validate_output(result_str)

            if not is_valid:
                return ExecutionResult(
                    success=False,
                    result=None,
                    error=error,
                    execution_time_ms=(time.perf_counter() - start_time) * 1000,
                )

            return ExecutionResult(
                success=True,
                result=result_str,
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        except asyncio.TimeoutError:
            return ExecutionResult(
                success=False,
                result=None,
                error=f"Execution timed out after {self._config.execution_timeout_seconds}s",
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )
        except SyntaxError as e:
            return ExecutionResult(
                success=False,
                result=None,
                error=f"Syntax error in generated code: {e}",
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                result=None,
                error=f"Execution error: {str(e)}",
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )

    def _create_helper_functions(
        self,
        context: str,
        task: str,
        depth: int,
    ) -> dict[str, Callable[..., Any]]:
        """
        Create helper functions bound to the current context.

        Args:
            context: Current context
            task: Current task
            depth: Current recursion depth

        Returns:
            Dictionary of helper functions
        """

        # Pre-compute line offsets for O(1) line number lookup
        import bisect

        _line_offsets = [0]
        for i, ch in enumerate(context):
            if ch == "\n":
                _line_offsets.append(i + 1)

        def context_search(pattern: str) -> list[Match]:
            """Search the context for a regex pattern."""
            matches = []
            try:
                for i, m in enumerate(re.finditer(pattern, context)):
                    if i >= self._config.max_search_results:
                        break

                    # Calculate line number using pre-computed offsets
                    line_number = bisect.bisect_right(_line_offsets, m.start())

                    matches.append(
                        Match(
                            text=m.group(),
                            start=m.start(),
                            end=m.end(),
                            line_number=line_number,
                        )
                    )
            except re.error as e:
                logger.warning(f"Invalid regex pattern: {pattern}, error: {e}")

            return matches

        def context_chunk(start: int, end: int) -> str:
            """Get a chunk of the context by position."""
            # Clamp to valid range
            start = max(0, min(start, len(context)))
            end = max(start, min(end, len(context)))
            return context[start:end]

        def recursive_call(sub_context: str, sub_task: str) -> str:
            """Recursively process a sub-problem."""
            # This is a synchronous wrapper for the async recursive call
            # We use asyncio.run_coroutine_threadsafe if we're in a different thread
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're in an async context, use a future
                    future = asyncio.ensure_future(
                        self._process_recursive(sub_context, sub_task, depth + 1)
                    )
                    # This blocks, which is okay in the executor thread
                    result = asyncio.get_event_loop().run_until_complete(future)
                else:
                    result = asyncio.run(
                        self._process_recursive(sub_context, sub_task, depth + 1)
                    )

                if result.success:
                    return result.result or ""
                else:
                    return f"[ERROR: {result.error}]"
            except Exception as e:
                return f"[ERROR: Recursive call failed: {str(e)}]"

        def aggregate_results(results: list[str]) -> str:
            """Aggregate multiple results into a summary."""
            if not results:
                return "No results to aggregate."

            # Filter out errors and empty results
            valid_results = [r for r in results if r and not r.startswith("[ERROR:")]

            if not valid_results:
                return "All sub-results failed or were empty."

            # Simple aggregation - join with separators
            # In production, this could use LLM for smarter summarization
            aggregated = "\n\n---\n\n".join(valid_results)

            # Truncate if too long
            if len(aggregated) > self._config.max_output_size:
                aggregated = (
                    aggregated[: self._config.max_output_size - 100]
                    + "\n\n[... truncated ...]"
                )

            return aggregated

        return {
            "context_search": context_search,
            "context_chunk": context_chunk,
            "recursive_call": recursive_call,
            "aggregate_results": aggregate_results,
            "Match": Match,  # Expose Match class for type checking
        }

    def _create_audit_record(
        self,
        request_id: str,
        user_id: str,
        organization_id: str,
        result: RLMResult,
        elapsed_ms: float,
    ) -> dict[str, Any]:
        """
        Create an audit record for the RLM execution.

        Args:
            request_id: Request identifier
            user_id: User identifier
            organization_id: Organization identifier
            result: RLM execution result
            elapsed_ms: Total elapsed time

        Returns:
            Audit record dictionary
        """
        return {
            "event_type": "rlm_execution",
            "request_id": request_id,
            "user_id": user_id,
            "organization_id": organization_id,
            "success": result.success,
            "recursion_depth": result.recursion_depth,
            "total_subcalls": self._subcall_count,
            "context_size": result.context_size,
            "execution_time_ms": elapsed_ms,
            "has_error": result.error is not None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


class SyncRecursiveContextEngine:
    """
    Synchronous wrapper for RecursiveContextEngine.

    Provides a synchronous interface for environments that don't support async.
    """

    def __init__(
        self,
        llm_service: LLMService,
        config: RLMConfig | None = None,
    ):
        """Initialize synchronous engine wrapper."""
        self._async_engine = RecursiveContextEngine(
            llm_service=llm_service,
            config=config,
        )

    def process(
        self,
        context: str,
        task: str,
        request_id: str | None = None,
        user_id: str | None = None,
        organization_id: str | None = None,
    ) -> RLMResult:
        """
        Process a task synchronously.

        Args:
            context: The large context to analyze
            task: Natural language description of the task
            request_id: Optional request ID for tracing
            user_id: Optional user ID for audit
            organization_id: Optional org ID for audit

        Returns:
            RLMResult with the processed result or error
        """
        return asyncio.run(
            self._async_engine.process(
                context=context,
                task=task,
                request_id=request_id,
                user_id=user_id,
                organization_id=organization_id,
            )
        )
