"""Constitutional Critique Service for Project Aura.

This module implements the ConstitutionalCritiqueService which evaluates
AI agent outputs against constitutional principles using batched parallel
LLM evaluation for efficiency.

ADR-063 Phase 3 enhancements:
- Semantic caching integration for 30-40% hit rate
- Bedrock Guardrails fast-path for CRITICAL principles
"""

import asyncio
import json
import os
import re
import time
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import yaml

from src.config.logging_config import get_logger
from src.services.constitutional_ai.exceptions import (
    ConstitutionLoadError,
    CritiqueParseError,
    CritiqueTimeoutError,
    LLMServiceError,
    PrincipleValidationError,
)
from src.services.constitutional_ai.failure_policy import (
    ConstitutionalFailureConfig,
    CritiqueFailurePolicy,
    get_failure_config,
)
from src.services.constitutional_ai.models import (
    ConstitutionalContext,
    ConstitutionalEvaluationSummary,
    ConstitutionalPrinciple,
    CritiqueResult,
    PrincipleCategory,
    PrincipleSeverity,
)

if TYPE_CHECKING:
    from src.services.bedrock_llm_service import BedrockLLMService
    from src.services.constitutional_ai.guardrails_fast_path import GuardrailsFastPath
    from src.services.semantic_cache_service import SemanticCacheService

logger = get_logger(__name__)

# Default path to constitution file
DEFAULT_CONSTITUTION_PATH = os.path.join(os.path.dirname(__file__), "constitution.yaml")


class ConstitutionalCritiqueService:
    """Stateless service for evaluating outputs against constitutional principles.

    This service loads constitutional principles from a YAML file and evaluates
    AI agent outputs against them using batched parallel LLM calls for efficiency.

    The critique process:
    1. Filter applicable principles based on context and domain tags
    2. Batch principles into groups of 5-6 for parallel evaluation
    3. Execute batched LLM calls concurrently
    4. Parse and aggregate results
    5. Resolve any conflicts between principle evaluations

    Attributes:
        llm: The LLM service for making inference calls
        failure_config: Configuration for handling failures
        principles: List of loaded constitutional principles
        mock_mode: Whether to use mock responses (for testing)
    """

    def __init__(
        self,
        llm_service: Optional["BedrockLLMService"] = None,
        constitution_path: Optional[str] = None,
        failure_config: Optional[ConstitutionalFailureConfig] = None,
        mock_mode: bool = False,
        semantic_cache: Optional["SemanticCacheService"] = None,
        guardrails_fast_path: Optional["GuardrailsFastPath"] = None,
    ) -> None:
        """Initialize the critique service.

        Args:
            llm_service: BedrockLLMService instance for LLM calls
            constitution_path: Path to constitution YAML file
            failure_config: Failure handling configuration
            mock_mode: If True, use mock responses instead of real LLM
            semantic_cache: SemanticCacheService for Phase 3 caching (ADR-063)
            guardrails_fast_path: GuardrailsFastPath for CRITICAL principle checks (ADR-063)
        """
        self.llm = llm_service
        self.failure_config = failure_config or get_failure_config()
        self.mock_mode = mock_mode
        self._constitution_path = constitution_path or DEFAULT_CONSTITUTION_PATH

        # Phase 3: Semantic cache and guardrails fast-path (ADR-063)
        self.semantic_cache = semantic_cache
        self.guardrails_fast_path = guardrails_fast_path

        # Cache metrics
        self._cache_hits = 0
        self._cache_misses = 0
        self._fast_path_blocks = 0

        # Latency tracking for Phase 4 evaluation (ADR-063)
        self._max_latencies_tracked = 1000
        self._latencies_ms: deque[float] = deque(maxlen=self._max_latencies_tracked)

        # Load principles
        self.principles = self._load_constitution(self._constitution_path)

        # Build dict for O(1) principle lookup by ID
        self._principles_by_id: Dict[str, ConstitutionalPrinciple] = {
            p.id: p for p in self.principles
        }

        logger.info(
            f"ConstitutionalCritiqueService initialized with {len(self.principles)} principles"
            f"{', cache enabled' if semantic_cache else ''}"
            f"{', fast-path enabled' if guardrails_fast_path else ''}"
        )

    def _load_constitution(self, path: str) -> List[ConstitutionalPrinciple]:
        """Load constitutional principles from YAML file.

        Args:
            path: Path to the constitution YAML file

        Returns:
            List of ConstitutionalPrinciple instances

        Raises:
            ConstitutionLoadError: If file cannot be loaded or parsed
            PrincipleValidationError: If any principle fails validation
        """
        try:
            constitution_path = Path(path)
            if not constitution_path.exists():
                raise ConstitutionLoadError(
                    f"Constitution file not found: {path}",
                    file_path=path,
                )

            with open(constitution_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data or "principles" not in data:
                raise ConstitutionLoadError(
                    "Constitution file missing 'principles' key",
                    file_path=path,
                )

            principles = []
            for principle_id, principle_data in data["principles"].items():
                try:
                    principle = self._parse_principle(principle_id, principle_data)
                    principles.append(principle)
                except (KeyError, ValueError) as e:
                    raise PrincipleValidationError(
                        f"Invalid principle '{principle_id}': {e}",
                        principle_id=principle_id,
                    )

            logger.info(
                f"Loaded {len(principles)} constitutional principles from {path}"
            )
            return principles

        except yaml.YAMLError as e:
            raise ConstitutionLoadError(
                f"Failed to parse constitution YAML: {e}",
                file_path=path,
                parse_error=str(e),
            )
        except OSError as e:
            raise ConstitutionLoadError(
                f"Failed to read constitution file: {e}",
                file_path=path,
            )

    def _parse_principle(
        self, principle_id: str, data: Dict[str, Any]
    ) -> ConstitutionalPrinciple:
        """Parse a single principle from YAML data.

        Args:
            principle_id: Unique identifier for the principle
            data: Dictionary containing principle fields

        Returns:
            ConstitutionalPrinciple instance

        Raises:
            KeyError: If required fields are missing
            ValueError: If field values are invalid
        """
        return ConstitutionalPrinciple(
            id=principle_id,
            name=data["name"],
            critique_prompt=data["critique_prompt"].strip(),
            revision_prompt=data["revision_prompt"].strip(),
            severity=PrincipleSeverity.from_string(data["severity"]),
            category=PrincipleCategory.from_string(data["category"]),
            domain_tags=data.get("domain_tags", []),
            enabled=data.get("enabled", True),
        )

    def get_principle(self, principle_id: str) -> Optional[ConstitutionalPrinciple]:
        """Get a principle by ID.

        Args:
            principle_id: The principle ID to look up

        Returns:
            The principle if found, None otherwise
        """
        return self._principles_by_id.get(principle_id)

    def get_principles_by_category(
        self, category: PrincipleCategory
    ) -> List[ConstitutionalPrinciple]:
        """Get all principles in a specific category.

        Args:
            category: The category to filter by

        Returns:
            List of principles in the category
        """
        return [p for p in self.principles if p.category == category and p.enabled]

    def get_principles_by_severity(
        self, severity: PrincipleSeverity
    ) -> List[ConstitutionalPrinciple]:
        """Get all principles with a specific severity.

        Args:
            severity: The severity level to filter by

        Returns:
            List of principles with the severity
        """
        return [p for p in self.principles if p.severity == severity and p.enabled]

    def filter_principles(
        self,
        applicable_ids: Optional[List[str]] = None,
        context: Optional[ConstitutionalContext] = None,
    ) -> List[ConstitutionalPrinciple]:
        """Filter principles based on IDs and context.

        Args:
            applicable_ids: Optional list of principle IDs to include
            context: Optional context for domain tag filtering

        Returns:
            List of filtered principles
        """
        principles = [p for p in self.principles if p.enabled]

        # Filter by specific IDs if provided
        if applicable_ids:
            principles = [p for p in principles if p.id in applicable_ids]

        # Filter by domain tags if context provides them
        if context and context.domain_tags:
            context_tags = set(context.domain_tags)
            # Include principles that have at least one matching tag
            # or have no tags (apply to all domains)
            principles = [
                p
                for p in principles
                if not p.domain_tags or set(p.domain_tags) & context_tags
            ]

        return principles

    def _create_principle_batches(
        self,
        principles: List[ConstitutionalPrinciple],
        batch_size: int = 5,
    ) -> List[List[ConstitutionalPrinciple]]:
        """Create batches of principles for parallel evaluation.

        Args:
            principles: List of principles to batch
            batch_size: Maximum principles per batch

        Returns:
            List of principle batches
        """
        batches = []
        for i in range(0, len(principles), batch_size):
            batches.append(principles[i : i + batch_size])
        return batches

    async def critique_output(
        self,
        agent_output: str,
        context: Optional[ConstitutionalContext] = None,
        applicable_principles: Optional[List[str]] = None,
        skip_cache: bool = False,
        skip_fast_path: bool = False,
    ) -> ConstitutionalEvaluationSummary:
        """Evaluate an agent output against constitutional principles.

        This method performs batched parallel evaluation of the output
        against applicable principles, then aggregates and returns results.

        ADR-063 Phase 3 enhancements:
        - Semantic cache check before LLM critique
        - Bedrock Guardrails fast-path for CRITICAL principles
        - Cache write after successful evaluation

        Args:
            agent_output: The AI agent's output to evaluate
            context: Context for the evaluation (agent name, operation, etc.)
            applicable_principles: Optional list of principle IDs to apply
            skip_cache: Skip cache lookup (for testing or force re-evaluation)
            skip_fast_path: Skip guardrails fast-path check

        Returns:
            ConstitutionalEvaluationSummary with all critique results

        Raises:
            CritiqueTimeoutError: If evaluation times out
            LLMServiceError: If LLM calls fail
        """
        start_time = time.time()

        # Create default context if not provided
        if context is None:
            context = ConstitutionalContext(
                agent_name="unknown",
                operation_type="unknown",
            )

        # Filter applicable principles
        principles = self.filter_principles(applicable_principles, context)
        if not principles:
            logger.warning("No applicable principles found for critique")
            return ConstitutionalEvaluationSummary.from_critiques([], 0.0)

        principle_ids = [p.id for p in principles]

        # Phase 3: Check semantic cache (ADR-063)
        cache_key = None
        if self.semantic_cache and not skip_cache:
            cache_result = await self._check_cache(agent_output, principle_ids, context)
            if cache_result is not None:
                self._cache_hits += 1
                elapsed_ms = (time.time() - start_time) * 1000
                cache_result.elapsed_ms = elapsed_ms
                cache_result.cache_hit = True
                logger.info(
                    f"Cache hit for critique: {len(principles)} principles in {elapsed_ms:.1f}ms"
                )
                return cache_result
            self._cache_misses += 1
            cache_key = self._generate_cache_key(agent_output, principle_ids, context)

        # Phase 3: Fast-path check for CRITICAL principles (ADR-063)
        if self.guardrails_fast_path and not skip_fast_path:
            fast_path_result = (
                await self.guardrails_fast_path.check_critical_principles(
                    output=agent_output,
                    context=context.to_dict() if context else None,
                )
            )
            if fast_path_result.blocked:
                self._fast_path_blocks += 1
                elapsed_ms = (time.time() - start_time) * 1000
                summary = self._build_fast_path_summary(
                    fast_path_result, principles, elapsed_ms
                )
                logger.info(
                    f"Fast-path blocked: {fast_path_result.principle_ids_blocked} "
                    f"in {elapsed_ms:.1f}ms"
                )
                return summary

        logger.info(
            f"Evaluating output against {len(principles)} principles "
            f"for agent '{context.agent_name}'"
        )

        # Create batches for parallel evaluation
        batches = self._create_principle_batches(principles, batch_size=5)
        logger.debug(f"Created {len(batches)} batches for evaluation")

        # Evaluate batches in parallel
        all_critiques: List[CritiqueResult] = []
        try:
            tasks = [
                self._evaluate_batch(agent_output, context, batch) for batch in batches
            ]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results and handle errors
            for i, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    await self._handle_batch_error(result, batches[i], all_critiques)
                else:
                    all_critiques.extend(result)

        except asyncio.TimeoutError:
            raise CritiqueTimeoutError(
                "Constitutional critique timed out",
                timeout_seconds=self.failure_config.critique_timeout_seconds,
                batch_size=len(batches),
            )

        # Resolve conflicts between principles
        resolved_critiques = self._resolve_conflicts(all_critiques)

        elapsed_ms = (time.time() - start_time) * 1000
        summary = ConstitutionalEvaluationSummary.from_critiques(
            resolved_critiques, elapsed_ms
        )

        # Phase 3: Write to semantic cache (ADR-063)
        if self.semantic_cache and cache_key and not skip_cache:
            await self._write_cache(cache_key, summary, context)

        # Phase 4: Track latency for P95 calculations (ADR-063)
        self._record_latency(elapsed_ms)

        logger.info(
            f"Critique complete: {summary.total_principles_evaluated} principles, "
            f"{summary.critical_issues} critical, {summary.high_issues} high issues "
            f"in {elapsed_ms:.1f}ms"
        )

        return summary

    async def _evaluate_batch(
        self,
        output: str,
        context: ConstitutionalContext,
        principles: List[ConstitutionalPrinciple],
    ) -> List[CritiqueResult]:
        """Evaluate a batch of principles against an output.

        Args:
            output: The output to evaluate
            context: Evaluation context
            principles: List of principles to evaluate in this batch

        Returns:
            List of critique results for the batch
        """
        if self.mock_mode:
            return self._generate_mock_critiques(principles)

        if self.llm is None:
            raise LLMServiceError(
                "LLM service not configured",
                operation="batch_critique",
            )

        # Build the batch critique prompt
        prompt = self._build_batch_critique_prompt(output, context, principles)

        try:
            # Make LLM call with timeout
            result = await asyncio.wait_for(
                self.llm.invoke_model_async(
                    prompt=prompt,
                    agent="ConstitutionalAI",
                    operation="constitutional_critique",
                    temperature=0.0,  # Deterministic for consistency
                ),
                timeout=self.failure_config.critique_timeout_seconds,
            )

            # Parse the response
            return self._parse_batch_response(result["response"], principles)

        except asyncio.TimeoutError:
            raise CritiqueTimeoutError(
                f"Batch evaluation timed out after {self.failure_config.critique_timeout_seconds}s",
                timeout_seconds=self.failure_config.critique_timeout_seconds,
                batch_size=len(principles),
                principles_evaluated=[p.id for p in principles],
            )
        except Exception as e:
            raise LLMServiceError(
                f"LLM call failed: {e}",
                original_error=e,
                operation="batch_critique",
            )

    def _build_batch_critique_prompt(
        self,
        output: str,
        context: ConstitutionalContext,
        principles: List[ConstitutionalPrinciple],
    ) -> str:
        """Build the prompt for batch critique evaluation.

        Args:
            output: The output to evaluate
            context: Evaluation context
            principles: Principles to evaluate

        Returns:
            Formatted prompt string
        """
        principles_section = ""
        for i, p in enumerate(principles, 1):
            principles_section += f"""
### Principle {i}: {p.name} (ID: {p.id})
Severity: {p.severity.value.upper()}
Category: {p.category.value}

{p.critique_prompt}

---
"""

        return f"""You are a Constitutional AI evaluator for Project Aura, an enterprise code intelligence platform.

Your task is to evaluate the following AI agent output against multiple constitutional principles.
For each principle, determine if any issues are found and whether revision is required.

## Context
Agent: {context.agent_name}
Operation: {context.operation_type}
{f'User Request: {context.user_request}' if context.user_request else ''}

## Agent Output to Evaluate
```
{output}
```

## Principles to Evaluate
{principles_section}

## Required Output Format
For EACH principle, provide your evaluation in this exact JSON format:

```json
[
  {{
    "principle_id": "<principle_id>",
    "issues_found": ["issue 1", "issue 2"],
    "reasoning": "Your chain-of-thought reasoning explaining your evaluation",
    "requires_revision": true/false,
    "confidence": 0.0-1.0
  }}
]
```

Rules:
1. Evaluate EVERY principle listed above
2. Be specific about issues found - cite exact problems
3. Only mark requires_revision=true if there are actionable issues
4. For security issues (CRITICAL), err on the side of caution
5. Provide clear reasoning for each evaluation
6. Confidence should reflect certainty of your assessment

Return ONLY the JSON array, no other text.
"""

    def _parse_batch_response(
        self,
        response: str,
        principles: List[ConstitutionalPrinciple],
    ) -> List[CritiqueResult]:
        """Parse the LLM response into critique results.

        Args:
            response: Raw LLM response string
            principles: Principles that were evaluated

        Returns:
            List of CritiqueResult instances

        Raises:
            CritiqueParseError: If response cannot be parsed
        """
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON array directly
                json_str = response.strip()

            # Parse JSON
            evaluations = json.loads(json_str)

            if not isinstance(evaluations, list):
                raise CritiqueParseError(
                    "Expected JSON array of evaluations",
                    raw_response=response,
                )

            # Build lookup for principles
            principle_map = {p.id: p for p in principles}

            results = []
            for eval_data in evaluations:
                principle_id = eval_data.get("principle_id")
                if principle_id not in principle_map:
                    logger.warning(f"Unknown principle ID in response: {principle_id}")
                    continue

                principle = principle_map[principle_id]
                results.append(
                    CritiqueResult(
                        principle_id=principle_id,
                        principle_name=principle.name,
                        severity=principle.severity,
                        issues_found=eval_data.get("issues_found", []),
                        reasoning=eval_data.get("reasoning", ""),
                        requires_revision=eval_data.get("requires_revision", False),
                        confidence=float(eval_data.get("confidence", 0.0)),
                    )
                )

            return results

        except json.JSONDecodeError as e:
            raise CritiqueParseError(
                f"Failed to parse JSON response: {e}",
                raw_response=response,
                parse_error=str(e),
            )

    async def _handle_batch_error(
        self,
        error: Exception,
        batch: List[ConstitutionalPrinciple],
        all_critiques: List[CritiqueResult],
    ) -> None:
        """Handle errors from batch evaluation.

        Args:
            error: The exception that occurred
            batch: The batch of principles that failed
            all_critiques: List to append error results to
        """
        policy = self.failure_config.critique_failure_policy

        logger.error(
            f"Batch evaluation failed for {len(batch)} principles: {error}",
            exc_info=True,
        )

        if policy == CritiqueFailurePolicy.BLOCK:
            # Re-raise to stop all processing
            raise error

        elif policy == CritiqueFailurePolicy.RETRY_THEN_BLOCK:
            # Retry logic would go here
            # For now, treat as BLOCK after retries exhausted
            raise error

        elif policy in (
            CritiqueFailurePolicy.PROCEED_LOGGED,
            CritiqueFailurePolicy.PROCEED_FLAGGED,
        ):
            # Create placeholder results indicating evaluation failure
            for principle in batch:
                all_critiques.append(
                    CritiqueResult(
                        principle_id=principle.id,
                        principle_name=principle.name,
                        severity=principle.severity,
                        issues_found=["Evaluation failed - manual review required"],
                        reasoning=f"Batch evaluation error: {error}",
                        requires_revision=policy
                        == CritiqueFailurePolicy.PROCEED_FLAGGED,
                        confidence=0.0,
                        metadata={"evaluation_error": str(error)},
                    )
                )

    def _resolve_conflicts(
        self, critiques: List[CritiqueResult]
    ) -> List[CritiqueResult]:
        """Resolve conflicts between principle critiques.

        Uses the conflict resolution hierarchy from Principle 16:
        1. CRITICAL severity takes precedence
        2. Then HIGH severity
        3. Then MEDIUM severity
        4. Then LOW severity

        Args:
            critiques: List of critique results to resolve

        Returns:
            List of critiques with conflicts resolved
        """
        if not critiques:
            return critiques

        # Sort by severity (critical first) for consistent ordering
        severity_order = {
            PrincipleSeverity.CRITICAL: 0,
            PrincipleSeverity.HIGH: 1,
            PrincipleSeverity.MEDIUM: 2,
            PrincipleSeverity.LOW: 3,
        }

        resolved = sorted(critiques, key=lambda c: severity_order.get(c.severity, 4))

        # Look for conflicting recommendations
        # For now, just ensure critical issues are always flagged
        for critique in resolved:
            if critique.severity == PrincipleSeverity.CRITICAL and critique.has_issues:
                critique.requires_revision = True

        return resolved

    def _generate_mock_critiques(
        self, principles: List[ConstitutionalPrinciple]
    ) -> List[CritiqueResult]:
        """Generate mock critique results for testing.

        Args:
            principles: Principles to generate mock results for

        Returns:
            List of mock CritiqueResult instances
        """
        results = []
        for principle in principles:
            results.append(
                CritiqueResult(
                    principle_id=principle.id,
                    principle_name=principle.name,
                    severity=principle.severity,
                    issues_found=[],
                    reasoning="Mock evaluation - no issues found",
                    requires_revision=False,
                    confidence=1.0,
                    metadata={"mock": True},
                )
            )
        return results

    async def critique_single_principle(
        self,
        output: str,
        principle_id: str,
        context: Optional[ConstitutionalContext] = None,
    ) -> Optional[CritiqueResult]:
        """Evaluate output against a single principle.

        Convenience method for evaluating against just one principle.

        Args:
            output: The output to evaluate
            principle_id: ID of the principle to evaluate
            context: Optional evaluation context

        Returns:
            CritiqueResult for the principle, or None if principle not found
        """
        principle = self.get_principle(principle_id)
        if not principle:
            logger.warning(f"Principle not found: {principle_id}")
            return None

        summary = await self.critique_output(
            output, context, applicable_principles=[principle_id]
        )

        for critique in summary.critiques:
            if critique.principle_id == principle_id:
                return critique

        return None

    # =========================================================================
    # Phase 3: Caching and Fast-Path Methods (ADR-063)
    # =========================================================================

    def _generate_cache_key(
        self,
        output: str,
        principle_ids: List[str],
        context: ConstitutionalContext,
    ) -> str:
        """Generate cache key for critique results.

        Args:
            output: The output being critiqued
            principle_ids: List of principle IDs
            context: Evaluation context

        Returns:
            Cache key string
        """
        from src.services.constitutional_ai.cache_utils import (
            generate_critique_cache_key,
        )

        return generate_critique_cache_key(output, principle_ids, context)

    async def _check_cache(
        self,
        output: str,
        principle_ids: List[str],
        context: ConstitutionalContext,
    ) -> Optional[ConstitutionalEvaluationSummary]:
        """Check semantic cache for existing critique result.

        Args:
            output: The output being critiqued
            principle_ids: List of principle IDs
            context: Evaluation context

        Returns:
            Cached ConstitutionalEvaluationSummary if found, None otherwise
        """
        if not self.semantic_cache:
            return None

        try:
            from src.services.semantic_cache_service import QueryType

            cache_key = self._generate_cache_key(output, principle_ids, context)

            cache_result = await self.semantic_cache.get_cached_response(
                query=cache_key,
                model_id="constitutional_critique",
                query_type=QueryType.CONSTITUTIONAL_CRITIQUE,
                agent_name=context.agent_name if context else "unknown",
            )

            if cache_result.hit and cache_result.response:
                # Deserialize cached summary
                cached_data = json.loads(cache_result.response)
                return ConstitutionalEvaluationSummary.from_dict(cached_data)

        except Exception as e:
            logger.warning(f"Cache lookup failed: {e}")

        return None

    async def _write_cache(
        self,
        cache_key: str,
        summary: ConstitutionalEvaluationSummary,
        context: ConstitutionalContext,
    ) -> None:
        """Write critique result to semantic cache.

        Args:
            cache_key: The cache key
            summary: The evaluation summary to cache
            context: Evaluation context
        """
        if not self.semantic_cache:
            return

        try:
            from src.services.semantic_cache_service import QueryType

            # Serialize summary for caching
            cached_data = json.dumps(summary.to_dict())

            await self.semantic_cache.cache_response(
                query=cache_key,
                response=cached_data,
                model_id="constitutional_critique",
                query_type=QueryType.CONSTITUTIONAL_CRITIQUE,
                agent_name=context.agent_name if context else "unknown",
            )

            logger.debug(f"Cached critique result for {context.agent_name}")

        except Exception as e:
            logger.warning(f"Cache write failed: {e}")

    def _build_fast_path_summary(
        self,
        fast_path_result: Any,  # FastPathResult
        principles: List[ConstitutionalPrinciple],
        elapsed_ms: float,
    ) -> ConstitutionalEvaluationSummary:
        """Build evaluation summary from fast-path guardrails block.

        Args:
            fast_path_result: Result from guardrails fast-path
            principles: Full list of principles
            elapsed_ms: Elapsed time in milliseconds

        Returns:
            ConstitutionalEvaluationSummary with blocked principles
        """
        critiques = []

        # Create critique results for blocked principles
        blocked_ids = set(fast_path_result.principle_ids_blocked)
        for principle in principles:
            if principle.id in blocked_ids:
                # Find the violation details
                violation_details = []
                for v in fast_path_result.violations:
                    if v.principle_id == principle.id:
                        violation_details.append(
                            f"Guardrail {v.guardrail_type}: {v.matched_content[:100]}"
                        )

                critiques.append(
                    CritiqueResult(
                        principle_id=principle.id,
                        principle_name=principle.name,
                        severity=principle.severity,
                        issues_found=violation_details
                        or ["Blocked by Bedrock Guardrails"],
                        reasoning="Fast-path guardrails detected violation",
                        requires_revision=True,
                        confidence=0.95,
                        metadata={
                            "fast_path_blocked": True,
                            "guardrail_id": fast_path_result.guardrail_id,
                        },
                    )
                )
            else:
                # Other principles not evaluated (fast-path short-circuit)
                critiques.append(
                    CritiqueResult(
                        principle_id=principle.id,
                        principle_name=principle.name,
                        severity=principle.severity,
                        issues_found=[],
                        reasoning="Not evaluated - fast-path blocked on CRITICAL principle",
                        requires_revision=False,
                        confidence=0.0,
                        metadata={"skipped_due_to_fast_path": True},
                    )
                )

        summary = ConstitutionalEvaluationSummary.from_critiques(critiques, elapsed_ms)
        summary.fast_path_blocked = True
        return summary

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring.

        Returns:
            Dictionary with cache hit/miss counts and rates
        """
        total = self._cache_hits + self._cache_misses
        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": self._cache_hits / total if total > 0 else 0.0,
            "fast_path_blocks": self._fast_path_blocks,
            "cache_enabled": self.semantic_cache is not None,
            "fast_path_enabled": self.guardrails_fast_path is not None,
        }

    # =========================================================================
    # Phase 4: Latency Tracking Methods (ADR-063)
    # =========================================================================

    def _record_latency(self, latency_ms: float) -> None:
        """Record a critique latency for P95 tracking.

        Args:
            latency_ms: Latency in milliseconds
        """
        self._latencies_ms.append(latency_ms)

    def get_latency_stats(self) -> Dict[str, Any]:
        """Get latency statistics for Phase 4 evaluation metrics.

        Returns:
            Dictionary with latency statistics including P50, P95, P99
        """
        if not self._latencies_ms:
            return {
                "count": 0,
                "min_ms": 0.0,
                "max_ms": 0.0,
                "avg_ms": 0.0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
            }

        sorted_latencies = sorted(self._latencies_ms)
        count = len(sorted_latencies)

        return {
            "count": count,
            "min_ms": sorted_latencies[0],
            "max_ms": sorted_latencies[-1],
            "avg_ms": sum(sorted_latencies) / count,
            "p50_ms": sorted_latencies[int(count * 0.50)],
            "p95_ms": (
                sorted_latencies[int(count * 0.95)]
                if count >= 20
                else sorted_latencies[-1]
            ),
            "p99_ms": (
                sorted_latencies[int(count * 0.99)]
                if count >= 100
                else sorted_latencies[-1]
            ),
        }

    def reset_latency_stats(self) -> None:
        """Reset latency tracking (for testing or periodic reset)."""
        self._latencies_ms.clear()

    def get_all_stats(self) -> Dict[str, Any]:
        """Get combined cache and latency statistics.

        Returns:
            Dictionary with all monitoring statistics
        """
        return {
            **self.get_cache_stats(),
            "latency": self.get_latency_stats(),
        }
