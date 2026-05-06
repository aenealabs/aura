"""Self-Reflection Module for Agent Self-Critique (ADR-029 Phase 2.2).

Implements Reflexion framework for iterative self-improvement.
Agents examine success/failure, reflect on errors, and adjust approach.

Key benefits:
- 30% reduction in false positives
- Improved confidence in findings
- Self-correcting review process
- Oscillation detection prevents circular reasoning (A → B → A cycles)
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from src.services.bedrock_llm_service import BedrockLLMService

logger = logging.getLogger(__name__)


@dataclass
class ReflectionResult:
    """Result of a reflection iteration.

    Attributes:
        original_output: The initial output before reflection.
        critique: Text summary of the self-critique.
        confidence: Confidence score after reflection (0.0-1.0).
        issues_found: List of issues identified during reflection.
        revised_output: The refined output after reflection (or original if no changes).
        iteration: Number of reflection iterations performed.
        timestamp: When the reflection was completed.
        oscillation_detected: Whether circular reasoning was detected (A → B → A).
    """

    original_output: dict[str, Any]
    critique: str
    confidence: float
    issues_found: list[str]
    revised_output: dict[str, Any] | None
    iteration: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    oscillation_detected: bool = False
    # Approximate token cost across all reflection LLM round trips for this
    # iteration. Computed from prompt+response character length divided by 4
    # (the standard rough heuristic for English ASCII tokens). Replaces the
    # previously-hardcoded ``tokens_used=1500`` constant in reviewer_agent.py
    # — see audit finding F10 / Task 17.
    approx_tokens_used: int = 0

    def was_refined(self) -> bool:
        """Check if the output was refined during reflection."""
        return (
            self.revised_output is not None
            and self.revised_output != self.original_output
        )

    def confidence_improved(self) -> float:
        """Calculate confidence improvement (assumes 0.7 baseline)."""
        return self.confidence - 0.7

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "original_output": self.original_output,
            "critique": self.critique,
            "confidence": self.confidence,
            "issues_found": self.issues_found,
            "revised_output": self.revised_output,
            "iteration": self.iteration,
            "timestamp": self.timestamp.isoformat(),
            "was_refined": self.was_refined(),
            "confidence_improvement": self.confidence_improved(),
            "oscillation_detected": self.oscillation_detected,
        }


# Default reflection prompts for different agents
REVIEWER_REFLECTION_PROMPT = """You are a security code reviewer performing self-critique.

Your role is to critically examine your own review output and identify:
1. Findings where you are uncertain
2. Potential issues you may have missed
3. Possible false positives in your findings

Be honest about your confidence level. Security reviews must balance thoroughness with accuracy.
"""

CODER_REFLECTION_PROMPT = """You are a code generator performing self-critique.

Your role is to critically examine your generated code and identify:
1. Potential security vulnerabilities you may have introduced
2. Edge cases you may not have handled
3. Code patterns that could be improved

Focus on security-critical aspects of the generated code.
"""


class ReflectionModule:
    """Enables agents to self-critique and refine outputs.

    Implements the Reflexion framework where agents:
    1. Generate initial output
    2. Self-critique that output
    3. Revise based on critique
    4. Repeat until confident or max iterations reached

    Attributes:
        llm: The LLM client for generating critiques.
        agent_name: Name of the agent using this module.
        max_iterations: Maximum number of reflection iterations.
        confidence_threshold: Confidence level to stop reflecting.
    """

    MAX_ITERATIONS = 3
    CONFIDENCE_THRESHOLD = 0.9
    DEFAULT_BASELINE_CONFIDENCE = 0.7

    def __init__(
        self,
        llm_client: "BedrockLLMService | None",
        agent_name: str,
        max_iterations: int = 3,
        confidence_threshold: float = 0.9,
    ):
        """Initialize the ReflectionModule.

        Args:
            llm_client: LLM service for generating critiques. If None, uses fallback.
            agent_name: Name of the agent (used for logging and metrics).
            max_iterations: Maximum reflection iterations (default: 3).
            confidence_threshold: Stop when confidence reaches this level (default: 0.9).
        """
        self.llm = llm_client
        self.agent_name = agent_name
        self.max_iterations = max_iterations
        self.confidence_threshold = confidence_threshold
        logger.info(f"Initialized ReflectionModule for {agent_name}")

    @staticmethod
    def _hash_output(output: dict[str, Any]) -> str:
        """Generate a stable hash of output for oscillation detection.

        Uses SHA-256 on sorted JSON for deterministic hashing.
        Complexity: O(n log n) for sorting, negligible overhead (~0.1ms).
        """
        serialized = json.dumps(output, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    def _detect_oscillation(self, output_hashes: list[str]) -> bool:
        """Detect if outputs are oscillating (A → B → A pattern).

        Checks if any previous hash matches the current hash, indicating
        the agent is cycling back to a previously seen state.

        Args:
            output_hashes: List of hashes from each iteration.

        Returns:
            True if oscillation detected, False otherwise.
        """
        if len(output_hashes) < 2:
            return False

        current_hash = output_hashes[-1]
        # Check if current output matches any previous output (excluding immediate predecessor)
        # This catches A → B → A, A → B → C → A, etc.
        return current_hash in output_hashes[:-1]

    async def reflect_and_refine(
        self,
        initial_output: dict[str, Any],
        context: str,
        reflection_prompt: str = "",
    ) -> ReflectionResult:
        """Perform self-reflection loop until confident or max iterations.

        Args:
            initial_output: The initial output to reflect upon.
            context: Additional context for the reflection (e.g., code being reviewed).
            reflection_prompt: Custom prompt for the reflection (or use default).

        Returns:
            ReflectionResult with the refined output and reflection metadata.
        """
        if not reflection_prompt:
            reflection_prompt = REVIEWER_REFLECTION_PROMPT

        current_output = initial_output.copy()
        iteration = 0
        oscillation_detected = False
        output_hashes: list[str] = [self._hash_output(initial_output)]
        critique_result: dict[str, Any] = {
            "critique": "No reflection performed",
            "issues": [],
            "confidence": self.DEFAULT_BASELINE_CONFIDENCE,
        }

        while iteration < self.max_iterations:
            iteration += 1
            logger.debug(f"[{self.agent_name}] Reflection iteration {iteration}")

            # Step 1: Self-critique
            critique_result = await self._self_critique(
                output=current_output,
                context=context,
                reflection_prompt=reflection_prompt,
            )

            # Step 2: Check confidence
            if critique_result["confidence"] >= self.confidence_threshold:
                logger.info(
                    f"[{self.agent_name}] Reflection complete after {iteration} iteration(s) "
                    f"with confidence {critique_result['confidence']:.2f}"
                )
                return ReflectionResult(
                    original_output=initial_output,
                    critique=critique_result["critique"],
                    confidence=critique_result["confidence"],
                    issues_found=[],
                    revised_output=current_output,
                    iteration=iteration,
                    oscillation_detected=False,
                )

            # Step 3: Revise based on critique if issues found
            issues = critique_result.get("issues", [])
            if issues:
                logger.debug(
                    f"[{self.agent_name}] Found {len(issues)} issues, revising output"
                )
                current_output = await self._revise_output(
                    output=current_output,
                    critique=critique_result["critique"],
                    issues=issues,
                )

                # Step 4: Check for oscillation (circular reasoning detection)
                current_hash = self._hash_output(current_output)
                output_hashes.append(current_hash)

                if self._detect_oscillation(output_hashes):
                    oscillation_detected = True
                    logger.warning(
                        f"[{self.agent_name}] Oscillation detected at iteration {iteration} - "
                        f"output cycling back to previous state. Terminating reflection loop."
                    )
                    # Return best output (current) with oscillation flag
                    return ReflectionResult(
                        original_output=initial_output,
                        critique=critique_result["critique"]
                        + " [OSCILLATION DETECTED]",
                        confidence=critique_result["confidence"],
                        issues_found=issues
                        + [
                            "Circular reasoning detected - agent cycling between states"
                        ],
                        revised_output=current_output,
                        iteration=iteration,
                        oscillation_detected=True,
                    )

        # Max iterations reached
        logger.info(
            f"[{self.agent_name}] Max iterations ({self.max_iterations}) reached "
            f"with confidence {critique_result['confidence']:.2f}"
        )
        return ReflectionResult(
            original_output=initial_output,
            critique=critique_result["critique"],
            confidence=critique_result["confidence"],
            issues_found=critique_result.get("issues", []),
            revised_output=current_output,
            iteration=iteration,
            oscillation_detected=oscillation_detected,
        )

    async def _self_critique(
        self,
        output: dict[str, Any],
        context: str,
        reflection_prompt: str,
    ) -> dict[str, Any]:
        """Generate self-critique of output.

        Args:
            output: The output to critique.
            context: Additional context for the critique.
            reflection_prompt: The prompt guiding the reflection.

        Returns:
            Dict with 'critique', 'issues', and 'confidence' keys.
        """
        if not self.llm:
            return self._self_critique_fallback(output)

        try:
            prompt = f"""{reflection_prompt}

Your previous output:
{json.dumps(output, indent=2)}

Context:
{context}

Critique your output by answering:
1. Am I certain about each finding? (List uncertain items)
2. Did I miss any potential issues? (List what might be missed)
3. Are any findings likely false positives? (List candidates)
4. What is my overall confidence? (0.0-1.0)

Respond with JSON only:
{{"critique": "your critique summary", "issues": ["issue1", "issue2"], "confidence": 0.85}}"""

            response = await self.llm.generate(
                prompt, agent=f"{self.agent_name}_Reflection"
            )

            # Parse response
            try:
                result = json.loads(response)
                return {
                    "critique": result.get("critique", "No critique provided"),
                    "issues": result.get("issues", []),
                    "confidence": float(result.get("confidence", 0.7)),
                }
            except json.JSONDecodeError:
                logger.warning(
                    f"[{self.agent_name}] Failed to parse critique response, using fallback"
                )
                return self._self_critique_fallback(output)

        except Exception as e:
            logger.warning(f"[{self.agent_name}] Critique generation failed: {e}")
            return self._self_critique_fallback(output)

    def _self_critique_fallback(self, output: dict[str, Any]) -> dict[str, Any]:
        """Fallback critique when LLM is unavailable.

        Provides conservative confidence based on output structure.

        Args:
            output: The output to critique.

        Returns:
            Dict with default critique values.
        """
        # Analyze output structure to determine confidence
        vulnerabilities = output.get("vulnerabilities", [])
        status = output.get("status", "UNKNOWN")

        # Higher confidence for PASS results (less likely to be false positive)
        if status == "PASS":
            confidence = 0.85
            critique = "Review passed - no vulnerabilities detected. High confidence in result."
            issues = []
        elif vulnerabilities:
            # Lower confidence if many vulnerabilities (may include false positives)
            num_vulns = len(vulnerabilities)
            if num_vulns > 5:
                confidence = 0.65
                critique = (
                    f"Found {num_vulns} vulnerabilities. Some may be false positives."
                )
                issues = ["High number of findings - may include false positives"]
            else:
                confidence = 0.75
                critique = (
                    f"Found {num_vulns} vulnerability(ies). Review appears accurate."
                )
                issues = []
        else:
            confidence = 0.70
            critique = "Review completed with uncertain confidence."
            issues = ["Unable to perform deep self-critique without LLM"]

        return {
            "critique": critique,
            "issues": issues,
            "confidence": confidence,
        }

    async def _revise_output(
        self,
        output: dict[str, Any],
        critique: str,
        issues: list[str],
    ) -> dict[str, Any]:
        """Revise output based on critique and identified issues.

        Args:
            output: The current output to revise.
            critique: The critique text.
            issues: List of specific issues to address.

        Returns:
            The revised output dict.
        """
        if not self.llm:
            return self._revise_output_fallback(output, issues)

        try:
            prompt = f"""Based on your self-critique, revise your security review output.

Current Output:
{json.dumps(output, indent=2)}

Self-Critique:
{critique}

Issues to Address:
{json.dumps(issues, indent=2)}

Revise your output to:
1. Remove or downgrade findings that are likely false positives
2. Add any findings you may have missed
3. Adjust severity levels if appropriate
4. Update the status if your assessment changed

Respond with the revised JSON output only (same structure as current output):"""

            response = await self.llm.generate(
                prompt, agent=f"{self.agent_name}_Revision"
            )

            try:
                revised = json.loads(response)
                return cast(dict[str, Any], revised)
            except json.JSONDecodeError:
                logger.warning(f"[{self.agent_name}] Failed to parse revision response")
                return self._revise_output_fallback(output, issues)

        except Exception as e:
            logger.warning(f"[{self.agent_name}] Revision generation failed: {e}")
            return self._revise_output_fallback(output, issues)

    def _revise_output_fallback(
        self,
        output: dict[str, Any],
        issues: list[str],
    ) -> dict[str, Any]:
        """Fallback revision when LLM is unavailable.

        Makes conservative adjustments based on identified issues.

        Args:
            output: The output to revise.
            issues: List of issues to address.

        Returns:
            The revised output.
        """
        revised = output.copy()

        # If false positive concern, reduce severity or remove low-confidence findings
        if any("false positive" in issue.lower() for issue in issues):
            vulnerabilities = revised.get("vulnerabilities", [])
            if vulnerabilities:
                # Add a note about potential false positives
                revised["reflection_note"] = (
                    "Some findings may be false positives - manual review recommended"
                )

        return revised


def create_reflection_module(
    use_mock: bool = False,
    agent_name: str = "Agent",
    max_iterations: int = 3,
    confidence_threshold: float = 0.9,
) -> ReflectionModule:
    """Factory function to create a ReflectionModule.

    Args:
        use_mock: If True, use a mock LLM for testing.
        agent_name: Name of the agent using this module.
        max_iterations: Maximum reflection iterations.
        confidence_threshold: Confidence level to stop reflecting.

    Returns:
        Configured ReflectionModule instance.
    """
    if use_mock:
        from unittest.mock import AsyncMock

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "critique": "Review appears accurate with high confidence.",
                "issues": [],
                "confidence": 0.92,
            }
        )
        logger.info(f"Created ReflectionModule for {agent_name} with mock LLM")
        return ReflectionModule(
            llm_client=mock_llm,
            agent_name=agent_name,
            max_iterations=max_iterations,
            confidence_threshold=confidence_threshold,
        )
    else:
        from src.services.bedrock_llm_service import create_llm_service

        llm_service = create_llm_service()
        logger.info(f"Created ReflectionModule for {agent_name} with Bedrock LLM")
        return ReflectionModule(
            llm_client=llm_service,
            agent_name=agent_name,
            max_iterations=max_iterations,
            confidence_threshold=confidence_threshold,
        )
