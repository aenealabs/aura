"""Constitutional Revision Service for Project Aura.

This module implements the ConstitutionalRevisionService which revises
AI agent outputs based on constitutional critique feedback to address
identified issues.

ADR-063 Phase 3 enhancements:
- Semantic caching for revision results
"""

import asyncio
import json
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from src.config.logging_config import get_logger
from src.services.constitutional_ai.critique_service import (
    ConstitutionalCritiqueService,
)
from src.services.constitutional_ai.exceptions import (
    CritiqueParseError,
    HITLRequiredError,
    LLMServiceError,
    RevisionConvergenceError,
)
from src.services.constitutional_ai.failure_policy import (
    ConstitutionalFailureConfig,
    RevisionFailurePolicy,
    get_failure_config,
)
from src.services.constitutional_ai.models import (
    ConstitutionalContext,
    ConstitutionalEvaluationSummary,
    CritiqueResult,
    PrincipleSeverity,
    RevisionResult,
)

if TYPE_CHECKING:
    from src.services.bedrock_llm_service import BedrockLLMService
    from src.services.semantic_cache_service import SemanticCacheService

logger = get_logger(__name__)


class ConstitutionalRevisionService:
    """Stateful service for revising outputs based on constitutional critique.

    This service orchestrates the revision loop:
    1. Take output and critiques requiring revision
    2. Generate revised output using LLM
    3. Re-evaluate revised output against principles
    4. Repeat until convergence or max iterations

    Each revision session is isolated to prevent cross-contamination
    between different revision contexts.

    Attributes:
        critique: The critique service for re-evaluation
        llm: The LLM service for making revision calls
        failure_config: Configuration for handling failures
        mock_mode: Whether to use mock responses (for testing)
    """

    def __init__(
        self,
        critique_service: ConstitutionalCritiqueService,
        llm_service: Optional["BedrockLLMService"] = None,
        failure_config: Optional[ConstitutionalFailureConfig] = None,
        mock_mode: bool = False,
        semantic_cache: Optional["SemanticCacheService"] = None,
    ) -> None:
        """Initialize the revision service.

        Args:
            critique_service: ConstitutionalCritiqueService for re-evaluation
            llm_service: BedrockLLMService for revision calls
            failure_config: Failure handling configuration
            mock_mode: If True, use mock responses instead of real LLM
            semantic_cache: SemanticCacheService for Phase 3 caching (ADR-063)
        """
        self.critique = critique_service
        self.llm = llm_service
        self.failure_config = failure_config or get_failure_config()
        self.mock_mode = mock_mode

        # Phase 3: Semantic cache (ADR-063)
        self.semantic_cache = semantic_cache
        self._cache_hits = 0
        self._cache_misses = 0

        logger.info(
            f"ConstitutionalRevisionService initialized"
            f"{', cache enabled' if semantic_cache else ''}"
        )

    async def revise_output(
        self,
        agent_output: str,
        critiques: List[CritiqueResult],
        context: Optional[ConstitutionalContext] = None,
        max_iterations: Optional[int] = None,
    ) -> RevisionResult:
        """Revise an output based on critique feedback.

        This method implements the revision loop, iterating until all
        critical issues are resolved or max iterations is reached.

        Args:
            agent_output: The original output to revise
            critiques: List of critique results requiring revision
            context: Context for the revision
            max_iterations: Override for max revision iterations

        Returns:
            RevisionResult with original and revised output

        Raises:
            HITLRequiredError: If revision cannot resolve critical issues
            RevisionConvergenceError: If max iterations reached with issues
            LLMServiceError: If LLM calls fail
        """
        max_iters = max_iterations or self.failure_config.max_revision_iterations

        # Filter to critiques that require revision
        pending_critiques = [c for c in critiques if c.requires_revision]

        if not pending_critiques:
            logger.info("No critiques require revision")
            return RevisionResult(
                original_output=agent_output,
                revised_output=agent_output,
                critiques_addressed=[],
                reasoning_chain="No revision required - all principles satisfied",
                revision_iterations=0,
                converged=True,
            )

        # Create default context if not provided
        if context is None:
            context = ConstitutionalContext(
                agent_name="unknown",
                operation_type="revision",
            )

        logger.info(
            f"Starting revision with {len(pending_critiques)} critiques, "
            f"max {max_iters} iterations"
        )

        current_output = agent_output
        reasoning_chain_parts = []
        addressed_critiques: List[str] = []
        iteration = 0

        while iteration < max_iters and pending_critiques:
            iteration += 1
            logger.debug(f"Revision iteration {iteration}/{max_iters}")

            # Perform revision
            revision_response = await self._perform_revision(
                current_output,
                pending_critiques,
                context,
                iteration,
            )

            current_output = revision_response["revised_output"]
            reasoning_chain_parts.append(
                f"Iteration {iteration}:\n{revision_response['reasoning']}"
            )
            addressed_critiques.extend(revision_response["addressed"])

            # Re-evaluate against the principles that had issues
            principle_ids = [c.principle_id for c in pending_critiques]
            re_eval = await self.critique.critique_output(
                current_output,
                context,
                applicable_principles=principle_ids,
            )

            # Update pending critiques
            pending_critiques = [c for c in re_eval.critiques if c.requires_revision]

            # Check for convergence
            if not pending_critiques:
                logger.info(f"Revision converged after {iteration} iterations")
                break

            # Check for critical issues that remain
            remaining_critical = [
                c for c in pending_critiques if c.severity == PrincipleSeverity.CRITICAL
            ]
            if remaining_critical and iteration >= max_iters:
                logger.warning(
                    f"Max iterations reached with {len(remaining_critical)} "
                    f"critical issues remaining"
                )
                break

        # Determine final outcome
        converged = len(pending_critiques) == 0
        remaining_critical = [
            c for c in pending_critiques if c.severity == PrincipleSeverity.CRITICAL
        ]

        if remaining_critical:
            await self._handle_revision_failure(
                agent_output,
                current_output,
                remaining_critical,
                iteration,
                reasoning_chain_parts,
            )

        return RevisionResult(
            original_output=agent_output,
            revised_output=current_output,
            critiques_addressed=list(set(addressed_critiques)),
            reasoning_chain="\n\n".join(reasoning_chain_parts),
            revision_iterations=iteration,
            converged=converged,
            metadata={
                "remaining_issues": len(pending_critiques),
                "max_iterations": max_iters,
            },
        )

    async def _perform_revision(
        self,
        current_output: str,
        critiques: List[CritiqueResult],
        context: ConstitutionalContext,
        iteration: int,
    ) -> Dict[str, Any]:
        """Perform a single revision iteration.

        Args:
            current_output: The current output to revise
            critiques: Critiques to address
            context: Revision context
            iteration: Current iteration number

        Returns:
            Dictionary with revised_output, reasoning, and addressed critique IDs
        """
        if self.mock_mode:
            return self._generate_mock_revision(current_output, critiques)

        if self.llm is None:
            raise LLMServiceError(
                "LLM service not configured",
                operation="revision",
            )

        # Build revision prompt
        prompt = self._build_revision_prompt(current_output, critiques, context)

        try:
            result = await asyncio.wait_for(
                self.llm.invoke_model_async(
                    prompt=prompt,
                    agent="ConstitutionalAI",
                    operation="constitutional_revision",
                    temperature=0.3,  # Some creativity for revisions
                ),
                timeout=self.failure_config.revision_timeout_seconds,
            )

            return self._parse_revision_response(result["response"], critiques)

        except asyncio.TimeoutError:
            raise LLMServiceError(
                f"Revision timed out after {self.failure_config.revision_timeout_seconds}s",
                operation="revision",
            )
        except Exception as e:
            raise LLMServiceError(
                f"Revision LLM call failed: {e}",
                original_error=e,
                operation="revision",
            )

    def _build_revision_prompt(
        self,
        output: str,
        critiques: List[CritiqueResult],
        context: ConstitutionalContext,
    ) -> str:
        """Build the prompt for revision.

        Args:
            output: The current output to revise
            critiques: Critiques to address
            context: Revision context

        Returns:
            Formatted prompt string
        """
        # Get revision prompts for each critique
        issues_section = ""
        for critique in critiques:
            principle = self.critique.get_principle(critique.principle_id)
            revision_prompt = principle.revision_prompt if principle else ""

            issues_section += f"""
### {critique.principle_name} ({critique.severity.value.upper()})
**Issues Found:**
{chr(10).join(f'- {issue}' for issue in critique.issues_found)}

**Reasoning:**
{critique.reasoning}

**Revision Guidance:**
{revision_prompt}

---
"""

        return f"""You are a Constitutional AI revision assistant for Project Aura.

Your task is to revise the following AI output to address the identified constitutional issues
while preserving the helpful intent and functionality.

## Context
Agent: {context.agent_name}
Operation: {context.operation_type}
{f'User Request: {context.user_request}' if context.user_request else ''}

## Original Output to Revise
```
{output}
```

## Issues to Address
{issues_section}

## Revision Requirements
1. Address ALL identified issues, prioritizing CRITICAL severity first
2. Maintain the original intent and helpfulness of the output
3. Make minimal changes necessary to resolve issues
4. Preserve correct portions of the output
5. Explain your reasoning for each change

## Required Output Format
Return your response in this exact JSON format:

```json
{{
  "revised_output": "Your complete revised output here",
  "reasoning": "Your reasoning explaining what changes were made and why",
  "addressed": ["principle_id_1", "principle_id_2"]
}}
```

The "addressed" array should contain the principle IDs you believe are now resolved.
Return ONLY the JSON, no other text.
"""

    def _parse_revision_response(
        self,
        response: str,
        critiques: List[CritiqueResult],
    ) -> Dict[str, Any]:
        """Parse the LLM revision response.

        Args:
            response: Raw LLM response string
            critiques: Critiques that were being addressed

        Returns:
            Dictionary with revised_output, reasoning, and addressed IDs

        Raises:
            CritiqueParseError: If response cannot be parsed
        """
        try:
            # Extract JSON from response
            json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = response.strip()

            data = json.loads(json_str)

            return {
                "revised_output": data.get("revised_output", ""),
                "reasoning": data.get("reasoning", ""),
                "addressed": data.get("addressed", []),
            }

        except json.JSONDecodeError as e:
            raise CritiqueParseError(
                f"Failed to parse revision response: {e}",
                raw_response=response,
                parse_error=str(e),
            )

    async def _handle_revision_failure(
        self,
        original_output: str,
        best_effort_output: str,
        remaining_critical: List[CritiqueResult],
        iterations: int,
        reasoning_chain_parts: List[str],
    ) -> None:
        """Handle failure to resolve all critical issues.

        Args:
            original_output: The original unrevised output
            best_effort_output: The best revision achieved
            remaining_critical: Critical issues still unresolved
            iterations: Number of iterations attempted
            reasoning_chain_parts: Reasoning from revision attempts

        Raises:
            HITLRequiredError: If policy requires human review
            RevisionConvergenceError: If policy allows return but convergence failed
        """
        policy = self.failure_config.revision_failure_policy

        logger.warning(
            f"Revision failed with {len(remaining_critical)} critical issues "
            f"after {iterations} iterations. Policy: {policy.value}"
        )

        if policy == RevisionFailurePolicy.BLOCK_FOR_HITL:
            raise HITLRequiredError(
                f"Human review required: {len(remaining_critical)} critical issues "
                f"could not be resolved after {iterations} iterations",
                remaining_issues=remaining_critical,
                revision_iterations=iterations,
            )

        elif policy == RevisionFailurePolicy.RETURN_ORIGINAL:
            # Return original is handled by caller based on result
            raise RevisionConvergenceError(
                f"Revision did not converge after {iterations} iterations",
                max_iterations=iterations,
                remaining_issues=remaining_critical,
            )

        # RETURN_BEST_EFFORT doesn't raise - returns the best effort result

    def _generate_mock_revision(
        self,
        output: str,
        critiques: List[CritiqueResult],
    ) -> Dict[str, Any]:
        """Generate mock revision response for testing.

        Args:
            output: The output being revised
            critiques: Critiques to address

        Returns:
            Mock revision response dictionary
        """
        return {
            "revised_output": f"[REVISED] {output}",
            "reasoning": "Mock revision - addressed all issues",
            "addressed": [c.principle_id for c in critiques],
        }

    async def revise_with_evaluation(
        self,
        agent_output: str,
        context: Optional[ConstitutionalContext] = None,
        applicable_principles: Optional[List[str]] = None,
    ) -> tuple[ConstitutionalEvaluationSummary, Optional[RevisionResult]]:
        """Combined critique and revision workflow.

        Convenience method that performs critique and revision in one call.

        Args:
            agent_output: The output to evaluate and potentially revise
            context: Context for evaluation and revision
            applicable_principles: Optional principle IDs to apply

        Returns:
            Tuple of (evaluation_summary, revision_result)
            revision_result is None if no revision was needed
        """
        # First, critique the output
        summary = await self.critique.critique_output(
            agent_output,
            context,
            applicable_principles,
        )

        # Check if revision is needed
        if not summary.requires_revision:
            logger.info("No revision required based on critique")
            return summary, None

        # Perform revision
        critiques_to_address = [c for c in summary.critiques if c.requires_revision]

        revision = await self.revise_output(
            agent_output,
            critiques_to_address,
            context,
        )

        return summary, revision

    async def iterative_revise(
        self,
        agent_output: str,
        context: Optional[ConstitutionalContext] = None,
        applicable_principles: Optional[List[str]] = None,
        max_total_iterations: int = 5,
    ) -> RevisionResult:
        """Iterative revision with full re-evaluation at each step.

        This method performs a more thorough revision process where
        the entire output is re-evaluated after each revision, not just
        the principles that had issues.

        Args:
            agent_output: The output to revise
            context: Context for evaluation and revision
            applicable_principles: Principle IDs to apply
            max_total_iterations: Maximum total iterations across all passes

        Returns:
            Final RevisionResult
        """
        current_output = agent_output
        total_iterations = 0
        all_addressed: List[str] = []
        reasoning_parts: List[str] = []

        while total_iterations < max_total_iterations:
            # Full evaluation
            summary = await self.critique.critique_output(
                current_output,
                context,
                applicable_principles,
            )

            if not summary.requires_revision:
                logger.info(
                    f"Iterative revision converged after {total_iterations} iterations"
                )
                break

            # Get critiques requiring revision
            pending = [c for c in summary.critiques if c.requires_revision]
            if not pending:
                break

            # Single revision iteration
            response = await self._perform_revision(
                current_output,
                pending,
                context,
                total_iterations + 1,
            )

            current_output = response["revised_output"]
            reasoning_parts.append(response["reasoning"])
            all_addressed.extend(response["addressed"])
            total_iterations += 1

        converged = total_iterations < max_total_iterations

        return RevisionResult(
            original_output=agent_output,
            revised_output=current_output,
            critiques_addressed=list(set(all_addressed)),
            reasoning_chain="\n\n".join(reasoning_parts),
            revision_iterations=total_iterations,
            converged=converged,
            metadata={
                "iterative_mode": True,
                "max_iterations": max_total_iterations,
            },
        )
