"""Project Aura - Coder Agent

Secure code generation agent with LLM integration for autonomous code remediation.
Generates code based on hybrid context from GraphRAG system.

Uses Chain of Draft (CoD) prompting for 92% token reduction (ADR-029 Phase 1.2).
"""

import json
import logging
from typing import TYPE_CHECKING, Any, Callable, Optional, Type

from .context_objects import ContextSource, HybridContext
from .monitoring_service import AgentRole, MonitorAgent

if TYPE_CHECKING:
    from src.services.bedrock_llm_service import BedrockLLMService

# Import CoD prompts
try:
    from src.prompts.cod_templates import (
        CoDPromptMode,
        build_cod_prompt,
        get_prompt_mode,
    )

    CoDPromptMode_Type: Optional[Type[Any]] = CoDPromptMode
    build_cod_prompt_func: Optional[Callable[..., str]] = build_cod_prompt
    get_prompt_mode_func: Optional[Callable[[], Any]] = get_prompt_mode
except ImportError:
    # Fallback for testing without full module structure
    CoDPromptMode_Type = None
    build_cod_prompt_func = None
    get_prompt_mode_func = None

logger = logging.getLogger(__name__)


class CoderAgent:
    """Secure code generation agent with LLM integration.

    The CoderAgent is responsible for generating code based on context retrieved
    from the hybrid GraphRAG system. It follows security policies and compliance
    requirements (CMMC, SOX, NIST 800-53).

    Attributes:
        llm: Bedrock LLM service for code generation.
        monitor: MonitorAgent for tracking metrics and costs.
    """

    def __init__(
        self,
        llm_client: "BedrockLLMService | None" = None,
        monitor: MonitorAgent | None = None,
    ):
        """Initialize the CoderAgent.

        Args:
            llm_client: Optional Bedrock LLM service. If None, uses fallback mode.
            monitor: Optional MonitorAgent for metrics tracking.
        """
        self.llm = llm_client
        self.monitor = monitor or MonitorAgent()
        logger.info("Initialized CoderAgent")

    async def generate_code(
        self,
        context: HybridContext,
        task_description: str,
    ) -> dict[str, Any]:
        """Generate code based on context and task description.

        Args:
            context: HybridContext containing structural and semantic context.
            task_description: Description of the code generation task.

        Returns:
            Dict containing:
                - code: Generated code string
                - language: Programming language (default: python)
                - has_remediation: Whether code includes security remediation
                - tokens_used: Estimated tokens consumed
        """
        print(f"\n[{AgentRole.CODER.value}] Generating code based on hybrid context...")
        self.monitor.record_agent_activity(tokens_used=4000, loc_generated=15)

        if self.llm:
            try:
                code = await self._generate_code_llm(context, task_description)
                has_remediation = (
                    len(context.get_items_by_source(ContextSource.REMEDIATION)) > 0
                )
                return {
                    "code": code,
                    "language": "python",
                    "has_remediation": has_remediation,
                    "tokens_used": 4000,
                }
            except Exception as e:
                logger.warning(f"LLM coder failed, using fallback: {e}")

        code = self._generate_code_fallback(context)
        has_remediation = (
            len(context.get_items_by_source(ContextSource.REMEDIATION)) > 0
        )
        return {
            "code": code,
            "language": "python",
            "has_remediation": has_remediation,
            "tokens_used": 500,
        }

    async def _generate_code_llm(
        self,
        context: HybridContext,
        task_description: str,
    ) -> str:
        """LLM-powered code generation using Chain of Draft (CoD) prompts.

        Uses CoD prompting for 92% token reduction while maintaining accuracy.
        ADR-029 Phase 1.2 implementation.
        Enhanced with neural memory context (ADR-029 Phase 2.1).

        Args:
            context: HybridContext with retrieval results.
            task_description: Task to implement.

        Returns:
            Generated code string.
        """
        if self.llm is None:
            return self._generate_code_fallback(context)

        context_str = context.to_prompt_string()
        has_remediation = (
            len(context.get_items_by_source(ContextSource.REMEDIATION)) > 0
        )

        # Check for neural memory context (ADR-029 Phase 2.1)
        memory_items = context.get_items_by_source(ContextSource.NEURAL_MEMORY)
        has_memory_context = len(memory_items) > 0
        memory_guidance = ""
        if has_memory_context:
            # Extract memory guidance for the prompt
            memory_signals = [item.content for item in memory_items]
            high_confidence = any(item.confidence > 0.7 for item in memory_items)
            memory_guidance = (
                f"\n\nNeural Memory Guidance:\n"
                f"{'High confidence - familiar pattern from past experiences.' if high_confidence else 'Lower confidence - less familiar pattern.'}\n"
                f"Past experiences: {'; '.join(memory_signals[:2])}"
            )

        # Use CoD prompt if available
        if build_cod_prompt_func is not None:
            if has_remediation:
                # Use remediation-focused CoD prompt
                prompt = build_cod_prompt_func(
                    "coder",
                    vulnerability=task_description,
                    context=context_str,
                    code="(see context above)",
                )
            else:
                # Use initial generation CoD prompt
                prompt = build_cod_prompt_func(
                    "coder_initial",
                    task=task_description,
                    context=context_str,
                )
            if get_prompt_mode_func is not None:
                logger.debug(f"Using CoD prompt mode: {get_prompt_mode_func().value}")
        else:
            # Fallback to traditional CoT prompt with optional memory guidance
            prompt = f"""You are a secure code generation agent for enterprise software.

Task: {task_description}

Context:
{context_str}
{memory_guidance}

{"IMPORTANT: Security remediation is required. Previous code had vulnerabilities that must be fixed." if has_remediation else "Generate initial implementation."}

Requirements:
- Follow all security policies mentioned in the context
- Use FIPS-compliant algorithms (SHA256 or SHA3-512, never SHA1)
- Include appropriate comments explaining security decisions
- Follow Python best practices (PEP 8, type hints where appropriate)
- Handle errors appropriately
{"- Leverage past experiences from neural memory if confidence is high" if has_memory_context else ""}

Generate ONLY the Python code, no explanations or markdown:"""

        response = await self.llm.generate(prompt, agent="Coder")

        # Extract code from response (handle markdown code blocks)
        code: str = response.strip()
        if code.startswith("```python"):
            code = code[9:]
        if code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
        return code.strip()

    def _generate_code_fallback(self, context: HybridContext) -> str:
        """Fallback code generation when LLM is unavailable.

        Args:
            context: HybridContext for determining remediation needs.

        Returns:
            Generated code string.
        """
        # Check if remediation context exists
        has_remediation = (
            len(context.get_items_by_source(ContextSource.REMEDIATION)) > 0
        )

        if has_remediation:
            # This block is executed on the self-correction attempt.
            return """import hashlib

class DataProcessor:
    def calculate_checksum(self, data):
        # Security Policy Enforced: Using SHA256
        return hashlib.sha256(data.encode()).hexdigest()
"""
        # This block is executed on the initial attempt, creating the vulnerability.
        return """import hashlib

class DataProcessor:
    def calculate_checksum(self, data):
        # VULNERABILITY: Insecure hash function used
        return hashlib.sha1(data.encode()).hexdigest()
"""

    async def generate_patch(
        self,
        original_code: str,
        vulnerability: dict[str, str],
        context: HybridContext,
    ) -> dict[str, Any]:
        """Generate a security patch for vulnerable code.

        Args:
            original_code: The vulnerable code to patch.
            vulnerability: Dict with 'finding' and 'severity' keys.
            context: HybridContext with security policies.

        Returns:
            Dict containing:
                - patched_code: The fixed code
                - changes_made: Description of changes
                - confidence: Confidence score (0-1)
        """
        print(f"\n[{AgentRole.CODER.value}] Generating security patch...")
        self.monitor.record_agent_activity(tokens_used=3000, loc_generated=10)

        if self.llm:
            try:
                return await self._generate_patch_llm(
                    original_code, vulnerability, context
                )
            except Exception as e:
                logger.warning(f"LLM patch generation failed, using fallback: {e}")

        return self._generate_patch_fallback(original_code, vulnerability)

    async def _generate_patch_llm(
        self,
        original_code: str,
        vulnerability: dict[str, str],
        context: HybridContext,
    ) -> dict[str, Any]:
        """LLM-powered patch generation."""
        if self.llm is None:
            return self._generate_patch_fallback(original_code, vulnerability)

        context_str = context.to_prompt_string()

        prompt = f"""You are a security remediation agent.

Original Code with Vulnerability:
```python
{original_code}
```

Vulnerability Details:
- Finding: {vulnerability.get('finding', 'Unknown vulnerability')}
- Severity: {vulnerability.get('severity', 'High')}

Security Context:
{context_str}

Generate a patched version of the code that:
1. Fixes the identified vulnerability
2. Follows all security policies in the context
3. Maintains the same functionality
4. Includes comments explaining the security fix

Respond with a JSON object containing:
- "patched_code": The complete fixed code
- "changes_made": Brief description of changes
- "confidence": Confidence score from 0.0 to 1.0

Response (JSON only):"""

        response = await self.llm.generate(prompt, agent="Coder")
        try:
            result = json.loads(response)
            return {
                "patched_code": result.get("patched_code", original_code),
                "changes_made": result.get("changes_made", "Applied security patch"),
                "confidence": result.get("confidence", 0.8),
            }
        except json.JSONDecodeError:
            logger.warning("Failed to parse patch LLM response, using fallback")
            return self._generate_patch_fallback(original_code, vulnerability)

    def _generate_patch_fallback(
        self,
        original_code: str,
        vulnerability: dict[str, str],
    ) -> dict[str, Any]:
        """Fallback patch generation when LLM is unavailable."""
        # Simple pattern-based patching for common vulnerabilities
        patched_code = original_code

        if (
            "sha1" in vulnerability.get("finding", "").lower()
            or "hashlib.sha1" in original_code
        ):
            patched_code = original_code.replace("hashlib.sha1", "hashlib.sha256")
            patched_code = patched_code.replace(
                "# VULNERABILITY: Insecure hash function used",
                "# Security Policy Enforced: Using SHA256 (FIPS-compliant)",
            )
            return {
                "patched_code": patched_code,
                "changes_made": "Replaced SHA1 with SHA256 for FIPS compliance",
                "confidence": 0.95,
            }

        return {
            "patched_code": patched_code,
            "changes_made": "No automatic patch available",
            "confidence": 0.0,
        }


def create_coder_agent(
    use_mock: bool = False,
    monitor: MonitorAgent | None = None,
) -> "CoderAgent":
    """Factory function to create a CoderAgent.

    Args:
        use_mock: If True, use a mock LLM for testing. If False, use real Bedrock.
        monitor: Optional MonitorAgent for metrics tracking.

    Returns:
        CoderAgent: Configured agent instance.
    """
    if use_mock:
        from unittest.mock import AsyncMock

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = """import hashlib

class DataProcessor:
    def calculate_checksum(self, data):
        # Security Policy Enforced: Using SHA256
        return hashlib.sha256(data.encode()).hexdigest()
"""
        logger.info("Created CoderAgent with mock LLM")
        return CoderAgent(llm_client=mock_llm, monitor=monitor)
    else:
        from src.services.bedrock_llm_service import create_llm_service

        llm_service = create_llm_service()
        logger.info("Created CoderAgent with Bedrock LLM")
        return CoderAgent(llm_client=llm_service, monitor=monitor)
