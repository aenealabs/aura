"""Project Aura - Reviewer Agent

Security code review agent with LLM integration for vulnerability detection
and policy compliance verification.

Uses Chain of Draft (CoD) prompting for 92% token reduction (ADR-029 Phase 1.2).
Enhanced with Self-Reflection for 30% fewer false positives (ADR-029 Phase 2.2).
"""

import json
import logging
from typing import TYPE_CHECKING, Any, Callable, Optional

from .context_objects import ContextSource, HybridContext
from .monitoring_service import AgentRole, MonitorAgent

if TYPE_CHECKING:
    from src.services.bedrock_llm_service import BedrockLLMService

# Import CoD prompts - declare types for fallback compatibility
CoDPromptMode: Optional[type] = None
build_cod_prompt: Optional[Callable[..., str]] = None
get_prompt_mode: Optional[Callable[[], Any]] = None

try:
    from src.prompts.cod_templates import CoDPromptMode as _CoDPromptMode
    from src.prompts.cod_templates import build_cod_prompt as _build_cod_prompt
    from src.prompts.cod_templates import get_prompt_mode as _get_prompt_mode

    CoDPromptMode = _CoDPromptMode  # type: ignore[assignment]
    build_cod_prompt = _build_cod_prompt
    get_prompt_mode = _get_prompt_mode
except ImportError:
    # Fallback for testing without full module structure - use None defaults
    pass

logger = logging.getLogger(__name__)


# Security policy definitions
SECURITY_POLICIES = {
    "crypto": {
        "prohibited": ["sha1", "md5", "des", "rc4"],
        "required": ["sha256", "sha384", "sha512", "sha3", "aes"],
        "message": "Cryptographic operations must use FIPS-compliant algorithms",
    },
    "secrets": {
        "patterns": ["password=", "api_key=", "secret=", "token=", "credential"],
        "message": "Hardcoded secrets detected - use environment variables or Secrets Manager",
    },
    "injection": {
        "patterns": ["eval(", "exec(", "subprocess.call(", "os.system(", "shell=True"],
        "message": "Potential code injection vulnerability - sanitize inputs",
    },
}


class ReviewerAgent:
    """Security code review agent with LLM integration.

    The ReviewerAgent is responsible for reviewing generated code for:
    - Security vulnerabilities (OWASP Top 10)
    - Compliance with security policies (CMMC, SOX, NIST 800-53)
    - Code quality and best practices

    Enhanced with Self-Reflection (ADR-029 Phase 2.2) for 30% fewer false positives.

    Attributes:
        llm: Bedrock LLM service for advanced code analysis.
        monitor: MonitorAgent for tracking metrics and findings.
        enable_reflection: Whether to use self-reflection loop.
        reflection: ReflectionModule for self-critique (if enabled).
    """

    def __init__(
        self,
        llm_client: "BedrockLLMService | None" = None,
        monitor: MonitorAgent | None = None,
        enable_reflection: bool = False,
    ):
        """Initialize the ReviewerAgent.

        Args:
            llm_client: Optional Bedrock LLM service. If None, uses pattern-based review.
            monitor: Optional MonitorAgent for metrics tracking.
            enable_reflection: Enable self-reflection loop for reduced false positives.
        """
        self.llm = llm_client
        self.monitor = monitor or MonitorAgent()
        self.enable_reflection = enable_reflection
        self.reflection: "ReflectionModule | None" = None

        # Initialize reflection module if enabled (ADR-029 Phase 2.2)
        if enable_reflection and llm_client is not None:
            try:
                from src.agents.reflection_module import ReflectionModule

                self.reflection = ReflectionModule(
                    llm_client=llm_client,
                    agent_name="Reviewer",
                    max_iterations=3,
                    confidence_threshold=0.9,
                )
                logger.info("Initialized ReviewerAgent with self-reflection enabled")
            except ImportError:
                logger.warning(
                    "ReflectionModule not available, proceeding without reflection"
                )
                self.enable_reflection = False
        else:
            logger.info("Initialized ReviewerAgent")

    async def review_code(
        self, code: str, context: HybridContext | None = None
    ) -> dict[str, Any]:
        """Review code for security vulnerabilities and policy compliance.

        Enhanced with:
        - Neural memory context for memory-informed review (ADR-029 Phase 2.1)
        - Self-reflection for 30% fewer false positives (ADR-029 Phase 2.2)

        Args:
            code: Source code to review.
            context: Optional HybridContext with neural memory signals.

        Returns:
            Dict containing:
                - status: "PASS" or "FAIL_SECURITY"
                - finding: Description of issues found (or confirmation of compliance)
                - severity: "Critical", "High", "Medium", "Low" (if issues found)
                - vulnerabilities: List of specific vulnerabilities detected
                - recommendations: List of remediation recommendations
                - memory_informed: Whether neural memory was used in review
                - reflection_applied: Whether self-reflection was applied
                - reflection_iterations: Number of reflection iterations (if applied)
                - reflection_confidence: Final confidence after reflection (if applied)
        """
        print(
            f"\n[{AgentRole.REVIEWER.value}] Reviewing code for security and policy violations..."
        )
        self.monitor.record_agent_activity(tokens_used=1000)

        # Extract neural memory context if available (ADR-029 Phase 2.1)
        memory_guidance = ""
        memory_informed = False
        if context is not None:
            memory_items = context.get_items_by_source(ContextSource.NEURAL_MEMORY)
            if memory_items:
                memory_informed = True
                high_confidence = any(item.confidence > 0.7 for item in memory_items)
                memory_signals = [item.content for item in memory_items[:2]]
                memory_guidance = (
                    f"\n\nNeural Memory Context:\n"
                    f"{'High confidence - familiar pattern.' if high_confidence else 'Lower confidence - less familiar pattern.'}\n"
                    f"Past review experiences: {'; '.join(memory_signals)}"
                )

        # Initial review
        if self.llm:
            try:
                initial_result = await self._review_code_llm(code, memory_guidance)
            except Exception as e:
                logger.warning(f"LLM reviewer failed, using fallback: {e}")
                initial_result = self._review_code_fallback(code)
        else:
            initial_result = self._review_code_fallback(code)

        initial_result["memory_informed"] = memory_informed
        initial_result["reflection_applied"] = False
        initial_result["reflection_iterations"] = 0
        initial_result["reflection_confidence"] = None

        # Apply self-reflection if enabled (ADR-029 Phase 2.2)
        if self.enable_reflection and self.reflection is not None:
            try:
                from src.agents.reflection_module import REVIEWER_REFLECTION_PROMPT

                reflection_result = await self.reflection.reflect_and_refine(
                    initial_output=initial_result,
                    context=f"Code being reviewed:\n```python\n{code}\n```",
                    reflection_prompt=REVIEWER_REFLECTION_PROMPT,
                )

                # Log reflection metrics
                self.monitor.record_agent_activity(
                    tokens_used=1500,  # Additional tokens for reflection
                )

                # Update result with reflection data
                final_result = reflection_result.revised_output or initial_result
                final_result["reflection_applied"] = True
                final_result["reflection_iterations"] = reflection_result.iteration
                final_result["reflection_confidence"] = reflection_result.confidence
                final_result["memory_informed"] = memory_informed

                logger.info(
                    f"Review completed with reflection: {reflection_result.iteration} iterations, "
                    f"confidence: {reflection_result.confidence:.2f}"
                )
                return final_result

            except Exception as e:
                logger.warning(f"Self-reflection failed, using initial result: {e}")
                return initial_result

        return initial_result

    async def _review_code_llm(
        self, code: str, memory_guidance: str = ""
    ) -> dict[str, Any]:
        """LLM-powered security review using Chain of Draft (CoD) prompts.

        Uses CoD prompting for 92% token reduction while maintaining accuracy.
        ADR-029 Phase 1.2 implementation.
        Enhanced with neural memory context (ADR-029 Phase 2.1).

        Args:
            code: Source code to review.
            memory_guidance: Optional neural memory context for informed review.

        Returns:
            Security review results.
        """
        if self.llm is None:
            return {"status": "PASS", "finding": "No LLM available for review"}

        # Use CoD prompt if available, otherwise fall back to traditional prompt
        if build_cod_prompt is not None and get_prompt_mode is not None:
            prompt = build_cod_prompt("reviewer", code=code)
            logger.debug(f"Using CoD prompt mode: {get_prompt_mode().value}")
        else:
            # Fallback to traditional CoT prompt with optional memory guidance
            prompt = f"""You are a security code reviewer for enterprise software following CMMC Level 3, SOX, and NIST 800-53 compliance requirements.

Review the following code for security vulnerabilities and policy compliance.

Code:
```python
{code}
```
{memory_guidance}

Security Policies to Check:
1. Cryptographic Operations:
   - PROHIBITED: SHA1, MD5, DES, RC4 (not FIPS-compliant)
   - REQUIRED: SHA256, SHA384, SHA512, SHA3, AES (FIPS 140-2 compliant)

2. Secrets Management:
   - No hardcoded passwords, API keys, tokens, or credentials
   - Must use environment variables or AWS Secrets Manager

3. Input Validation:
   - All user inputs must be validated and sanitized
   - No use of eval(), exec(), or shell=True without proper controls

4. OWASP Top 10:
   - Check for injection vulnerabilities
   - Check for broken authentication patterns
   - Check for sensitive data exposure
{"" if not memory_guidance else "5. Memory-Informed Review: Consider past experiences and patterns from neural memory when assessing risk levels."}

Respond with a JSON object containing:
- "status": "PASS" if code is secure, "FAIL_SECURITY" if vulnerabilities found
- "finding": Summary description of the issue or "Code is secure and compliant"
- "severity": "Critical", "High", "Medium", or "Low" (only if status is FAIL_SECURITY)
- "vulnerabilities": Array of specific vulnerability objects with "type", "line", "description"
- "recommendations": Array of remediation recommendations

Response (JSON only):"""

        response = await self.llm.generate(prompt, agent="Reviewer")
        try:
            result = json.loads(response)
            status = result.get("status", "PASS")
            finding = result.get("finding", "Code review completed")
            vulnerabilities = result.get("vulnerabilities", [])
            recommendations = result.get("recommendations", [])

            if status == "FAIL_SECURITY":
                severity = result.get("severity", "High")
                self.monitor.record_security_finding(
                    AgentRole.REVIEWER, finding, severity, "Detected"
                )
                return {
                    "status": status,
                    "finding": finding,
                    "severity": severity,
                    "vulnerabilities": vulnerabilities,
                    "recommendations": recommendations,
                }

            return {
                "status": "PASS",
                "finding": finding,
                "vulnerabilities": [],
                "recommendations": recommendations,
            }
        except json.JSONDecodeError:
            logger.warning("Failed to parse reviewer LLM response, using fallback")
            return self._review_code_fallback(code)

    def _review_code_fallback(self, code: str) -> dict[str, Any]:
        """Fallback pattern-based security review when LLM is unavailable.

        Args:
            code: Source code to review.

        Returns:
            Security review results.
        """
        vulnerabilities = []
        recommendations = []
        max_severity = None

        # Check for weak cryptographic algorithms
        for weak_algo in SECURITY_POLICIES["crypto"]["prohibited"]:
            if (
                f"hashlib.{weak_algo}" in code.lower()
                or f".{weak_algo}(" in code.lower()
            ):
                vuln = {
                    "type": "WEAK_CRYPTOGRAPHY",
                    "description": f"Weak cryptographic algorithm detected: {weak_algo.upper()}",
                    "severity": "High",
                }
                vulnerabilities.append(vuln)
                recommendations.append(
                    f"Replace {weak_algo.upper()} with SHA256 or SHA3-512 for FIPS compliance"
                )
                max_severity = "High"

        # Check for hardcoded secrets
        for pattern in SECURITY_POLICIES["secrets"]["patterns"]:
            if pattern.lower() in code.lower():
                # Check if it's actually a hardcoded value (not just a variable reference)
                if f'{pattern}"' in code or f"{pattern}'" in code:
                    vuln = {
                        "type": "HARDCODED_SECRET",
                        "description": f"Potential hardcoded secret detected: {pattern}",
                        "severity": "Critical",
                    }
                    vulnerabilities.append(vuln)
                    recommendations.append(
                        "Move secrets to environment variables or AWS Secrets Manager"
                    )
                    max_severity = "Critical"

        # Check for injection vulnerabilities
        for pattern in SECURITY_POLICIES["injection"]["patterns"]:
            if pattern in code:
                vuln = {
                    "type": "CODE_INJECTION",
                    "description": f"Potential code injection vulnerability: {pattern}",
                    "severity": "Critical",
                }
                vulnerabilities.append(vuln)
                recommendations.append(
                    f"Avoid using {pattern} - use safer alternatives with input validation"
                )
                if max_severity != "Critical":
                    max_severity = "Critical"

        if vulnerabilities:
            finding = f"Found {len(vulnerabilities)} security issue(s): {', '.join(v['type'] for v in vulnerabilities)}"
            self.monitor.record_security_finding(
                AgentRole.REVIEWER, finding, max_severity or "Medium", "Detected"
            )
            return {
                "status": "FAIL_SECURITY",
                "finding": finding,
                "severity": max_severity,
                "vulnerabilities": vulnerabilities,
                "recommendations": recommendations,
            }

        return {
            "status": "PASS",
            "finding": "Code is secure and compliant with security policies.",
            "vulnerabilities": [],
            "recommendations": [],
        }

    async def review_patch(
        self,
        original_code: str,
        patched_code: str,
        vulnerability: dict[str, str],
    ) -> dict[str, Any]:
        """Review a security patch to verify it properly addresses the vulnerability.

        Args:
            original_code: The original vulnerable code.
            patched_code: The patched code to verify.
            vulnerability: The vulnerability that was supposed to be fixed.

        Returns:
            Dict containing:
                - patch_valid: True if patch correctly fixes the vulnerability
                - regression_check: True if no new vulnerabilities introduced
                - finding: Description of review results
                - confidence: Confidence score (0-1)
        """
        print(f"\n[{AgentRole.REVIEWER.value}] Verifying security patch...")
        self.monitor.record_agent_activity(tokens_used=800)

        if self.llm:
            try:
                return await self._review_patch_llm(
                    original_code, patched_code, vulnerability
                )
            except Exception as e:
                logger.warning(f"LLM patch review failed, using fallback: {e}")

        return self._review_patch_fallback(original_code, patched_code, vulnerability)

    async def _review_patch_llm(
        self,
        original_code: str,
        patched_code: str,
        vulnerability: dict[str, str],
    ) -> dict[str, Any]:
        """LLM-powered patch verification."""
        if self.llm is None:
            return self._review_patch_fallback(
                original_code, patched_code, vulnerability
            )

        prompt = f"""You are a security patch reviewer.

Verify that the following patch correctly addresses the identified vulnerability.

Original Code (VULNERABLE):
```python
{original_code}
```

Patched Code:
```python
{patched_code}
```

Vulnerability that should be fixed:
- Finding: {vulnerability.get('finding', 'Unknown')}
- Severity: {vulnerability.get('severity', 'High')}

Respond with a JSON object containing:
- "patch_valid": true if the patch correctly fixes the vulnerability, false otherwise
- "regression_check": true if no new vulnerabilities were introduced
- "finding": Detailed explanation of your assessment
- "confidence": Confidence score from 0.0 to 1.0

Response (JSON only):"""

        response = await self.llm.generate(prompt, agent="Reviewer")
        try:
            result = json.loads(response)
            return {
                "patch_valid": result.get("patch_valid", False),
                "regression_check": result.get("regression_check", True),
                "finding": result.get("finding", "Patch review completed"),
                "confidence": result.get("confidence", 0.7),
            }
        except json.JSONDecodeError:
            logger.warning("Failed to parse patch review LLM response, using fallback")
            return self._review_patch_fallback(
                original_code, patched_code, vulnerability
            )

    def _review_patch_fallback(
        self,
        original_code: str,
        patched_code: str,
        vulnerability: dict[str, str],
    ) -> dict[str, Any]:
        """Fallback patch verification when LLM is unavailable."""
        patch_valid = False
        finding = vulnerability.get("finding", "")

        # Check if SHA1 vulnerability was fixed
        if "sha1" in finding.lower() or "hashlib.sha1" in original_code:
            if "hashlib.sha1" not in patched_code:
                if "hashlib.sha256" in patched_code or "hashlib.sha3" in patched_code:
                    patch_valid = True

        # Check for regression - run same vulnerability checks on patched code
        regression_result = self._review_code_fallback(patched_code)
        regression_check = regression_result["status"] == "PASS"

        if patch_valid and regression_check:
            return {
                "patch_valid": True,
                "regression_check": True,
                "finding": "Patch correctly fixes vulnerability with no regressions",
                "confidence": 0.9,
            }
        elif patch_valid:
            return {
                "patch_valid": True,
                "regression_check": False,
                "finding": "Patch fixes original issue but introduces new vulnerabilities",
                "confidence": 0.6,
            }
        else:
            return {
                "patch_valid": False,
                "regression_check": regression_check,
                "finding": "Patch does not adequately address the vulnerability",
                "confidence": 0.8,
            }


def create_reviewer_agent(
    use_mock: bool = False,
    monitor: MonitorAgent | None = None,
    enable_reflection: bool = False,
) -> "ReviewerAgent":
    """Factory function to create a ReviewerAgent.

    Args:
        use_mock: If True, use a mock LLM for testing. If False, use real Bedrock.
        monitor: Optional MonitorAgent for metrics tracking.
        enable_reflection: Enable self-reflection loop (ADR-029 Phase 2.2).

    Returns:
        ReviewerAgent: Configured agent instance.
    """
    if use_mock:
        from unittest.mock import AsyncMock

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "status": "PASS",
                "finding": "Code is secure and compliant with security policies.",
                "vulnerabilities": [],
                "recommendations": [],
            }
        )
        logger.info(
            f"Created ReviewerAgent with mock LLM (reflection={enable_reflection})"
        )
        return ReviewerAgent(
            llm_client=mock_llm,
            monitor=monitor,
            enable_reflection=enable_reflection,
        )
    else:
        from src.services.bedrock_llm_service import create_llm_service

        llm_service = create_llm_service()
        logger.info(
            f"Created ReviewerAgent with Bedrock LLM (reflection={enable_reflection})"
        )
        return ReviewerAgent(
            llm_client=llm_service,
            monitor=monitor,
            enable_reflection=enable_reflection,
        )
