"""Project Aura - Validator Agent

Comprehensive code validation agent with LLM integration for syntax checking,
type verification, security scanning, and sandbox testing.

Uses Chain of Draft (CoD) prompting for 92% token reduction (ADR-029 Phase 1.2).
"""

import ast
import json
import logging
import os
import re
import uuid
from typing import TYPE_CHECKING, Any, Callable, Optional, cast

from .monitoring_service import AgentRole, MonitorAgent

if TYPE_CHECKING:
    from src.services.bedrock_llm_service import BedrockLLMService
    from src.services.sandbox_network_service import FargateSandboxOrchestrator

# Import CoD prompts
try:
    from src.prompts.cod_templates import (
        CoDPromptMode,
        build_cod_prompt,
        get_prompt_mode,
    )

    _CoDPromptMode: Optional[type] = CoDPromptMode
    _build_cod_prompt: Optional[Callable[..., str]] = build_cod_prompt
    _get_prompt_mode: Optional[Callable[[], Any]] = get_prompt_mode
except ImportError:
    # Fallback for testing without full module structure
    _CoDPromptMode = None
    _build_cod_prompt = None
    _get_prompt_mode = None

logger = logging.getLogger(__name__)


class ValidatorAgent:
    """Comprehensive code validation agent with LLM integration.

    The ValidatorAgent is responsible for:
    - Syntax validation using AST parsing
    - Structural completeness checks
    - Type hint verification
    - Security-focused static analysis
    - Code quality assessment
    - Sandbox-based runtime validation (optional)

    Attributes:
        llm: Bedrock LLM service for advanced validation.
        monitor: MonitorAgent for tracking metrics.
        sandbox_orchestrator: Optional FargateSandboxOrchestrator for runtime testing.
    """

    def __init__(
        self,
        llm_client: "BedrockLLMService | None" = None,
        monitor: MonitorAgent | None = None,
        sandbox_orchestrator: "FargateSandboxOrchestrator | None" = None,
    ):
        """Initialize the ValidatorAgent.

        Args:
            llm_client: Optional Bedrock LLM service. If None, uses pattern-based validation.
            monitor: Optional MonitorAgent for metrics tracking.
            sandbox_orchestrator: Optional sandbox orchestrator for runtime testing.
        """
        self.llm = llm_client
        self.monitor = monitor or MonitorAgent()
        self.sandbox_orchestrator = sandbox_orchestrator
        logger.info("Initialized ValidatorAgent")

    async def validate_code(
        self,
        code: str,
        expected_elements: list[str] | None = None,
    ) -> dict[str, Any]:
        """Perform comprehensive code validation.

        Args:
            code: Source code to validate.
            expected_elements: Optional list of expected code elements (function names, classes).

        Returns:
            Dict containing:
                - valid: True if all validation checks pass
                - syntax_valid: True if code has valid Python syntax
                - structure_valid: True if expected elements are present
                - type_hints_valid: True if type hints are properly used
                - security_valid: True if no obvious security issues
                - issues: List of validation issues found
                - warnings: List of non-blocking warnings
        """
        print(f"\n[{AgentRole.VALIDATOR.value}] Running comprehensive validation...")
        self.monitor.record_agent_activity(tokens_used=500)

        # Always run syntax validation first
        syntax_result = self._validate_syntax(code)

        if not syntax_result["valid"]:
            return {
                "valid": False,
                "syntax_valid": False,
                "structure_valid": False,
                "type_hints_valid": False,
                "security_valid": False,
                "issues": syntax_result["issues"],
                "warnings": [],
            }

        # Run structural validation
        structure_result = self._validate_structure(code, expected_elements or [])

        # Run type hints validation
        type_result = self._validate_type_hints(code)

        # Run security validation
        security_result = self._validate_security(code)

        # Combine all issues
        all_issues = (
            structure_result.get("issues", [])
            + type_result.get("issues", [])
            + security_result.get("issues", [])
        )
        all_warnings = (
            structure_result.get("warnings", [])
            + type_result.get("warnings", [])
            + security_result.get("warnings", [])
        )

        # Determine overall validity (security issues are blocking)
        valid = (
            syntax_result["valid"]
            and structure_result["valid"]
            and security_result["valid"]
        )

        if self.llm and not valid:
            try:
                # Use LLM for enhanced analysis of issues
                llm_analysis = await self._enhanced_analysis_llm(code, all_issues)
                all_issues.extend(llm_analysis.get("additional_issues", []))
                all_warnings.extend(llm_analysis.get("recommendations", []))
            except Exception as e:
                logger.warning(f"LLM validation enhancement failed: {e}")

        return {
            "valid": valid,
            "syntax_valid": syntax_result["valid"],
            "structure_valid": structure_result["valid"],
            "type_hints_valid": type_result["valid"],
            "security_valid": security_result["valid"],
            "issues": all_issues,
            "warnings": all_warnings,
        }

    def _validate_syntax(self, code: str) -> dict[str, Any]:
        """Validate Python syntax using AST parsing.

        Args:
            code: Source code to validate.

        Returns:
            Dict with 'valid' bool and 'issues' list.
        """
        try:
            ast.parse(code)
            return {"valid": True, "issues": []}
        except SyntaxError as e:
            issue = {
                "type": "SYNTAX_ERROR",
                "line": e.lineno,
                "column": e.offset,
                "message": str(e.msg),
                "severity": "error",
            }
            print(f"[{AgentRole.VALIDATOR.value}] Syntax error detected: {e.msg}")
            return {"valid": False, "issues": [issue]}

    def _validate_structure(
        self,
        code: str,
        expected_elements: list[str],
    ) -> dict[str, Any]:
        """Validate structural completeness of code.

        Args:
            code: Source code to validate.
            expected_elements: List of expected elements (e.g., ['import hashlib', 'calculate_checksum']).

        Returns:
            Dict with 'valid' bool, 'issues' list, and 'warnings' list.
        """
        issues = []
        warnings = []

        # Check for expected elements
        for element in expected_elements:
            if element not in code:
                issues.append(
                    {
                        "type": "MISSING_ELEMENT",
                        "message": f"Expected element not found: {element}",
                        "severity": "error",
                    }
                )

        # Check for common structural issues
        try:
            tree = ast.parse(code)

            # Count classes and functions
            classes = [
                node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
            ]
            functions = [
                node.name
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef)
            ]

            if not classes and not functions:
                warnings.append(
                    {
                        "type": "EMPTY_CODE",
                        "message": "Code contains no classes or functions",
                        "severity": "warning",
                    }
                )

            # Check for overly long functions (>50 lines)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_lines = (
                        node.end_lineno - node.lineno
                        if node.end_lineno is not None
                        else 0
                    )
                    if func_lines > 50:
                        warnings.append(
                            {
                                "type": "LONG_FUNCTION",
                                "message": f"Function '{node.name}' is {func_lines} lines (recommend <50)",
                                "severity": "warning",
                            }
                        )

        except SyntaxError:
            # If we can't parse, that's already handled by syntax validation
            pass

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
        }

    def _validate_type_hints(self, code: str) -> dict[str, Any]:
        """Validate type hint usage in code.

        Args:
            code: Source code to validate.

        Returns:
            Dict with 'valid' bool, 'issues' list, and 'warnings' list.
        """
        warnings = []

        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Check for return type annotation
                    if node.returns is None and node.name != "__init__":
                        warnings.append(
                            {
                                "type": "MISSING_RETURN_TYPE",
                                "message": f"Function '{node.name}' lacks return type annotation",
                                "severity": "warning",
                            }
                        )

                    # Check for argument type annotations
                    for arg in node.args.args:
                        if arg.annotation is None and arg.arg != "self":
                            warnings.append(
                                {
                                    "type": "MISSING_ARG_TYPE",
                                    "message": f"Argument '{arg.arg}' in '{node.name}' lacks type annotation",
                                    "severity": "warning",
                                }
                            )

        except SyntaxError:
            pass

        # Type hints are not blocking - just warnings
        return {
            "valid": True,
            "issues": [],
            "warnings": warnings,
        }

    def _validate_security(self, code: str) -> dict[str, Any]:
        """Perform security-focused static analysis.

        Args:
            code: Source code to validate.

        Returns:
            Dict with 'valid' bool, 'issues' list, and 'warnings' list.
        """
        issues = []
        warnings = []

        # Check for dangerous patterns
        dangerous_patterns = [
            (
                r"\beval\s*\(",
                "EVAL_USAGE",
                "Use of eval() is dangerous - consider alternatives",
            ),
            (
                r"\bexec\s*\(",
                "EXEC_USAGE",
                "Use of exec() is dangerous - consider alternatives",
            ),
            (
                r"subprocess\.call\([^)]*shell\s*=\s*True",
                "SHELL_INJECTION",
                "shell=True is vulnerable to injection",
            ),
            (
                r"os\.system\s*\(",
                "OS_SYSTEM",
                "os.system() is vulnerable - use subprocess with shell=False",
            ),
            (
                r"pickle\.loads?\s*\(",
                "PICKLE_USAGE",
                "pickle can execute arbitrary code - use json instead",
            ),
            (
                r"yaml\.load\s*\([^)]*\)",
                "YAML_UNSAFE",
                "Use yaml.safe_load() instead of yaml.load()",
            ),
        ]

        for pattern, issue_type, message in dangerous_patterns:
            if re.search(pattern, code):
                issues.append(
                    {
                        "type": issue_type,
                        "message": message,
                        "severity": "error",
                    }
                )

        # Check for potential secrets (warning only - might be false positive)
        secret_patterns = [
            (r'password\s*=\s*["\'][^"\']+["\']', "HARDCODED_PASSWORD"),
            (r'api_key\s*=\s*["\'][^"\']+["\']', "HARDCODED_API_KEY"),
            (r'secret\s*=\s*["\'][^"\']+["\']', "HARDCODED_SECRET"),
            (r'token\s*=\s*["\'][^"\']+["\']', "HARDCODED_TOKEN"),
        ]

        for pattern, issue_type in secret_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                warnings.append(
                    {
                        "type": issue_type,
                        "message": f"Potential {issue_type.replace('HARDCODED_', '').lower()} detected",
                        "severity": "warning",
                    }
                )

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
        }

    async def _enhanced_analysis_llm(
        self,
        code: str,
        existing_issues: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Use LLM for enhanced code analysis with Chain of Draft (CoD) prompts.

        Uses CoD prompting for 92% token reduction while maintaining accuracy.
        ADR-029 Phase 1.2 implementation.

        Args:
            code: Source code to analyze.
            existing_issues: Issues already found by pattern matching.

        Returns:
            Dict with additional issues and recommendations.
        """
        issues_str = "\n".join(
            [f"- {i['type']}: {i['message']}" for i in existing_issues]
        )

        # Use CoD prompt if available
        if _build_cod_prompt is not None:
            prompt = _build_cod_prompt(
                "validator_insights",
                code=code,
                issues=issues_str if issues_str else "None",
            )
            if _get_prompt_mode is not None:
                logger.debug(f"Using CoD prompt mode: {_get_prompt_mode().value}")
        else:
            # Fallback to traditional CoT prompt
            prompt = f"""You are a code validation expert.

Analyze the following code and the issues already detected.

Code:
```python
{code}
```

Issues Already Detected:
{issues_str if issues_str else "None"}

Provide additional insights:
1. Any additional security or quality issues not already detected
2. Specific recommendations for fixing the issues

Respond with a JSON object containing:
- "additional_issues": Array of new issues with "type", "message", "severity"
- "recommendations": Array of specific fix recommendations

Response (JSON only):"""

        if self.llm is None:
            return {"additional_issues": [], "recommendations": []}
        response = await self.llm.generate(prompt, agent="Validator")
        try:
            return cast(dict[str, Any], json.loads(response))
        except json.JSONDecodeError:
            return {"additional_issues": [], "recommendations": []}

    def validate_syntax_only(self, code: str) -> bool:
        """Quick syntax-only validation.

        Args:
            code: Source code to validate.

        Returns:
            True if syntax is valid, False otherwise.
        """
        return cast(bool, self._validate_syntax(code)["valid"])

    async def validate_against_requirements(
        self,
        code: str,
        requirements: list[str],
    ) -> dict[str, Any]:
        """Validate code against a list of requirements.

        Args:
            code: Source code to validate.
            requirements: List of requirements the code should meet.

        Returns:
            Dict containing:
                - all_met: True if all requirements are satisfied
                - results: Dict mapping each requirement to pass/fail status
                - confidence: Overall confidence score (0-1)
        """
        print(f"\n[{AgentRole.VALIDATOR.value}] Validating against requirements...")
        self.monitor.record_agent_activity(tokens_used=600)

        if self.llm:
            try:
                return await self._validate_requirements_llm(code, requirements)
            except Exception as e:
                logger.warning(f"LLM requirements validation failed: {e}")

        return self._validate_requirements_fallback(code, requirements)

    async def _validate_requirements_llm(
        self,
        code: str,
        requirements: list[str],
    ) -> dict[str, Any]:
        """LLM-powered requirements validation with Chain of Draft (CoD) prompts.

        Uses CoD prompting for 92% token reduction while maintaining accuracy.
        ADR-029 Phase 1.2 implementation.
        """
        requirements_str = "\n".join(
            [f"{i+1}. {req}" for i, req in enumerate(requirements)]
        )

        # Use CoD prompt if available
        if _build_cod_prompt is not None:
            prompt = _build_cod_prompt(
                "validator_requirements",
                code=code,
                requirements=requirements_str,
            )
            if _get_prompt_mode is not None:
                logger.debug(f"Using CoD prompt mode: {_get_prompt_mode().value}")
        else:
            # Fallback to traditional CoT prompt
            prompt = f"""You are a requirements validation expert.

Verify if the following code meets all the specified requirements.

Code:
```python
{code}
```

Requirements:
{requirements_str}

For each requirement, determine if it is met and explain why.

Respond with a JSON object containing:
- "all_met": true if ALL requirements are satisfied, false otherwise
- "results": Object with requirement number as key, containing "met" (bool) and "reason" (string)
- "confidence": Overall confidence score from 0.0 to 1.0

Response (JSON only):"""

        if self.llm is None:
            return self._validate_requirements_fallback(code, requirements)
        response = await self.llm.generate(prompt, agent="Validator")
        try:
            return cast(dict[str, Any], json.loads(response))
        except json.JSONDecodeError:
            return self._validate_requirements_fallback(code, requirements)

    def _validate_requirements_fallback(
        self,
        code: str,
        requirements: list[str],
    ) -> dict[str, Any]:
        """Fallback requirements validation using pattern matching."""
        results = {}
        all_met = True

        for i, req in enumerate(requirements):
            req_lower = req.lower()

            # Simple pattern matching for common requirements
            if "sha256" in req_lower:
                met = "sha256" in code.lower() and "sha1" not in code.lower()
            elif "sha1" in req_lower and "not" in req_lower:
                met = "sha1" not in code.lower()
            elif "fips" in req_lower or "compliant" in req_lower:
                met = "sha256" in code.lower() or "sha3" in code.lower()
            elif "hashlib" in req_lower:
                met = "import hashlib" in code
            else:
                # Check if requirement keywords exist in code
                keywords = [w for w in req_lower.split() if len(w) > 3]
                met = any(kw in code.lower() for kw in keywords)

            results[str(i + 1)] = {
                "met": met,
                "reason": "Pattern match" if met else "Not found in code",
            }
            if not met:
                all_met = False

        return {
            "all_met": all_met,
            "results": results,
            "confidence": 0.6 if all_met else 0.4,
        }

    async def validate_in_sandbox(
        self,
        code: str,
        patch_id: str,
        test_suite: str = "integration_tests",
        timeout_seconds: int = 300,
    ) -> dict[str, Any]:
        """Run code validation in an isolated sandbox environment.

        This method provisions an ephemeral ECS Fargate task, deploys the patched
        code, runs the specified test suite, and tears down the sandbox.

        Args:
            code: Source code to validate.
            patch_id: Unique identifier for the patch being validated.
            test_suite: Test suite to run (e.g., 'unit_tests', 'integration_tests').
            timeout_seconds: Maximum time to wait for sandbox tests (default 300s).

        Returns:
            Dict containing:
                - sandbox_valid: True if all sandbox tests passed
                - sandbox_id: Unique sandbox identifier
                - test_results: Detailed test execution results
                - execution_time: Total execution time in seconds
                - sandbox_status: Final sandbox status
                - errors: List of any errors encountered
        """
        print(
            f"\n[{AgentRole.VALIDATOR.value}] Running sandbox validation for patch {patch_id}..."
        )
        self.monitor.record_agent_activity(tokens_used=100)

        sandbox_id = f"sandbox-{patch_id}-{uuid.uuid4().hex[:8]}"
        start_time = __import__("time").time()

        # Check if sandbox orchestrator is available
        if not self.sandbox_orchestrator:
            logger.warning(
                "Sandbox orchestrator not configured - skipping runtime validation"
            )
            return {
                "sandbox_valid": None,
                "sandbox_id": None,
                "test_results": [],
                "execution_time": 0,
                "sandbox_status": "skipped",
                "errors": ["Sandbox orchestrator not configured"],
            }

        errors = []
        test_results = []

        try:
            # Step 1: Create sandbox
            logger.info(f"Creating sandbox: {sandbox_id}")
            await self.sandbox_orchestrator.create_sandbox(
                sandbox_id=sandbox_id,
                patch_id=patch_id,
                test_suite=test_suite,
            )

            # Step 2: Wait for sandbox to be ready
            logger.info(f"Waiting for sandbox {sandbox_id} to be ready...")
            status = await self.sandbox_orchestrator.get_sandbox_status(sandbox_id)

            # Step 3: Poll for completion (with timeout)
            poll_interval = 10  # seconds
            elapsed = 0
            while status.get("status") == "running" and elapsed < timeout_seconds:
                await __import__("asyncio").sleep(poll_interval)
                elapsed += poll_interval
                status = await self.sandbox_orchestrator.get_sandbox_status(sandbox_id)

            # Step 4: Collect results
            if status.get("status") == "completed":
                test_results = status.get("test_results", [])
                sandbox_valid = status.get("all_tests_passed", False)
                logger.info(
                    f"Sandbox tests completed: {'PASSED' if sandbox_valid else 'FAILED'}"
                )
            elif elapsed >= timeout_seconds:
                errors.append(f"Sandbox timed out after {timeout_seconds}s")
                sandbox_valid = False
                logger.error(f"Sandbox {sandbox_id} timed out")
            else:
                errors.append(f"Sandbox ended with status: {status.get('status')}")
                sandbox_valid = False
                logger.error(
                    f"Sandbox {sandbox_id} failed: {status.get('error', 'Unknown error')}"
                )

        except Exception as e:
            logger.error(f"Sandbox validation error: {e}")
            errors.append(str(e))
            sandbox_valid = False

        finally:
            # Step 5: Cleanup sandbox
            try:
                if self.sandbox_orchestrator:
                    await self.sandbox_orchestrator.destroy_sandbox(sandbox_id)
                    logger.info(f"Destroyed sandbox: {sandbox_id}")
            except Exception as cleanup_error:
                logger.warning(
                    f"Failed to cleanup sandbox {sandbox_id}: {cleanup_error}"
                )

        execution_time = __import__("time").time() - start_time

        return {
            "sandbox_valid": sandbox_valid,
            "sandbox_id": sandbox_id,
            "test_results": test_results,
            "execution_time": round(execution_time, 2),
            "sandbox_status": "completed" if not errors else "failed",
            "errors": errors,
        }

    async def validate_with_sandbox(
        self,
        code: str,
        patch_id: str,
        expected_elements: list[str] | None = None,
        run_sandbox: bool = True,
    ) -> dict[str, Any]:
        """Perform comprehensive validation including optional sandbox testing.

        Combines static analysis (syntax, security, structure) with optional
        runtime validation in an isolated sandbox environment.

        Args:
            code: Source code to validate.
            patch_id: Unique identifier for the patch.
            expected_elements: Optional list of expected code elements.
            run_sandbox: Whether to run sandbox validation (default True).

        Returns:
            Dict containing both static and sandbox validation results:
                - valid: True if all validations pass
                - static_validation: Results from static code analysis
                - sandbox_validation: Results from sandbox testing (if enabled)
        """
        print(
            f"\n[{AgentRole.VALIDATOR.value}] Running full validation pipeline for {patch_id}..."
        )

        # Run static validation first
        static_result = await self.validate_code(code, expected_elements)

        result = {
            "valid": static_result["valid"],
            "static_validation": static_result,
            "sandbox_validation": None,
        }

        # Only run sandbox if static validation passes and sandbox is enabled
        if run_sandbox and static_result["valid"] and self.sandbox_orchestrator:
            sandbox_result = await self.validate_in_sandbox(
                code=code,
                patch_id=patch_id,
            )
            result["sandbox_validation"] = sandbox_result

            # Update overall validity to include sandbox results
            if sandbox_result["sandbox_valid"] is not None:
                result["valid"] = (
                    static_result["valid"] and sandbox_result["sandbox_valid"]
                )

        return result


def create_validator_agent(
    use_mock: bool = False,
    monitor: MonitorAgent | None = None,
    enable_sandbox: bool = False,
) -> "ValidatorAgent":
    """Factory function to create a ValidatorAgent.

    Args:
        use_mock: If True, use a mock LLM for testing. If False, use real Bedrock.
        monitor: Optional MonitorAgent for metrics tracking.
        enable_sandbox: If True, wire up FargateSandboxOrchestrator for runtime testing.

    Returns:
        ValidatorAgent: Configured agent instance.
    """
    sandbox_orchestrator = None

    # Initialize sandbox orchestrator if enabled
    if enable_sandbox:
        try:
            from src.services.sandbox_network_service import FargateSandboxOrchestrator

            environment = os.getenv("AURA_ENVIRONMENT", "dev")
            sandbox_orchestrator = FargateSandboxOrchestrator(environment=environment)
            logger.info(f"Created FargateSandboxOrchestrator for {environment}")
        except Exception as e:
            logger.warning(f"Failed to create sandbox orchestrator: {e}")

    if use_mock:
        from unittest.mock import AsyncMock

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "additional_issues": [],
                "recommendations": [
                    "Consider adding type hints for better maintainability"
                ],
                "all_met": True,
                "results": {"1": {"met": True, "reason": "Requirement satisfied"}},
                "confidence": 0.9,
            }
        )
        logger.info("Created ValidatorAgent with mock LLM")
        return ValidatorAgent(
            llm_client=mock_llm,
            monitor=monitor,
            sandbox_orchestrator=sandbox_orchestrator,
        )
    else:
        from src.services.bedrock_llm_service import create_llm_service

        llm_service = create_llm_service()
        logger.info("Created ValidatorAgent with Bedrock LLM")
        return ValidatorAgent(
            llm_client=llm_service,
            monitor=monitor,
            sandbox_orchestrator=sandbox_orchestrator,
        )


def create_sandbox_enabled_validator(
    environment: str = "dev",
    monitor: MonitorAgent | None = None,
) -> "ValidatorAgent":
    """Create a ValidatorAgent with sandbox testing enabled.

    This is a convenience factory for creating a validator with full
    sandbox testing capabilities for HITL workflow integration.

    Args:
        environment: Deployment environment (dev, qa, prod).
        monitor: Optional MonitorAgent for metrics tracking.

    Returns:
        ValidatorAgent configured with sandbox orchestrator.
    """
    os.environ["AURA_ENVIRONMENT"] = environment
    return create_validator_agent(
        use_mock=False,
        monitor=monitor,
        enable_sandbox=True,
    )
