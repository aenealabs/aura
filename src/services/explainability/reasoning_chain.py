"""
Project Aura - Reasoning Chain Builder

Builds structured reasoning chains from agent decision processes.
Extracts steps, evidence, and references to create complete
documentation of the decision logic.

Author: Project Aura Team
Created: 2026-01-25
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from .config import ReasoningChainConfig
from .contracts import ReasoningChain

logger = logging.getLogger(__name__)


class ReasoningChainBuilder:
    """
    Build structured reasoning chains from agent decision processes.

    Extracts reasoning steps from decision inputs and outputs,
    links evidence, and maps references to create complete
    documentation of decision logic.
    """

    def __init__(
        self,
        bedrock_client: Any = None,
        config: Optional[ReasoningChainConfig] = None,
    ):
        """
        Initialize the reasoning chain builder.

        Args:
            bedrock_client: AWS Bedrock client for LLM extraction
            config: Configuration for reasoning chain building
        """
        self.bedrock = bedrock_client
        self.config = config or ReasoningChainConfig()
        logger.info("ReasoningChainBuilder initialized")

    async def build(
        self,
        decision_id: str,
        agent_id: str,
        decision_input: dict[str, Any],
        decision_output: dict[str, Any],
        min_steps: int = 2,
        context: Optional[dict[str, Any]] = None,
    ) -> ReasoningChain:
        """
        Build a reasoning chain from decision input and output.

        Args:
            decision_id: Unique identifier for the decision
            agent_id: The agent making the decision
            decision_input: Input data for the decision
            decision_output: Output/result of the decision
            min_steps: Minimum number of reasoning steps required
            context: Additional context for reasoning extraction

        Returns:
            ReasoningChain with structured reasoning steps
        """
        logger.debug(f"Building reasoning chain for decision {decision_id}")

        # Create the chain
        chain = ReasoningChain(
            decision_id=decision_id,
            agent_id=agent_id,
            input_summary=self._summarize_input(decision_input),
            output_summary=self._summarize_output(decision_output),
        )

        # Extract reasoning steps
        if self.config.enable_llm_extraction and self.bedrock:
            steps = await self._extract_steps_with_llm(
                decision_input, decision_output, context, min_steps
            )
        else:
            steps = self._extract_steps_heuristic(
                decision_input, decision_output, min_steps
            )

        # Add steps to chain
        for step_data in steps:
            chain.add_step(
                description=step_data.get("description", ""),
                evidence=step_data.get("evidence", []),
                confidence=step_data.get("confidence", 1.0),
                references=step_data.get("references", []),
            )

        # Ensure minimum steps
        while len(chain.steps) < min_steps:
            chain.add_step(
                description=f"Additional reasoning step {len(chain.steps) + 1}",
                evidence=["Inferred from decision context"],
                confidence=0.7,
            )

        logger.debug(
            f"Built reasoning chain with {len(chain.steps)} steps, "
            f"total_confidence={chain.total_confidence:.2f}"
        )
        return chain

    def build_sync(
        self,
        decision_id: str,
        agent_id: str,
        decision_input: dict[str, Any],
        decision_output: dict[str, Any],
        min_steps: int = 2,
    ) -> ReasoningChain:
        """
        Synchronous version of build using heuristic extraction.

        Args:
            decision_id: Unique identifier for the decision
            agent_id: The agent making the decision
            decision_input: Input data for the decision
            decision_output: Output/result of the decision
            min_steps: Minimum number of reasoning steps required

        Returns:
            ReasoningChain with structured reasoning steps
        """
        chain = ReasoningChain(
            decision_id=decision_id,
            agent_id=agent_id,
            input_summary=self._summarize_input(decision_input),
            output_summary=self._summarize_output(decision_output),
        )

        steps = self._extract_steps_heuristic(
            decision_input, decision_output, min_steps
        )

        for step_data in steps:
            chain.add_step(
                description=step_data.get("description", ""),
                evidence=step_data.get("evidence", []),
                confidence=step_data.get("confidence", 1.0),
                references=step_data.get("references", []),
            )

        while len(chain.steps) < min_steps:
            chain.add_step(
                description=f"Additional reasoning step {len(chain.steps) + 1}",
                evidence=["Inferred from decision context"],
                confidence=0.7,
            )

        return chain

    def _summarize_input(self, decision_input: dict[str, Any]) -> str:
        """Create a brief summary of decision input."""
        if "task" in decision_input:
            return str(decision_input["task"])[:200]
        if "query" in decision_input:
            return str(decision_input["query"])[:200]
        if "description" in decision_input:
            return str(decision_input["description"])[:200]
        # Fallback to key list
        keys = list(decision_input.keys())[:5]
        return f"Input with keys: {', '.join(keys)}"

    def _summarize_output(self, decision_output: dict[str, Any]) -> str:
        """Create a brief summary of decision output."""
        if "action" in decision_output:
            return str(decision_output["action"])[:200]
        if "result" in decision_output:
            return str(decision_output["result"])[:200]
        if "recommendation" in decision_output:
            return str(decision_output["recommendation"])[:200]
        # Fallback to key list
        keys = list(decision_output.keys())[:5]
        return f"Output with keys: {', '.join(keys)}"

    async def _extract_steps_with_llm(
        self,
        decision_input: dict[str, Any],
        decision_output: dict[str, Any],
        context: Optional[dict[str, Any]],
        min_steps: int,
    ) -> list[dict[str, Any]]:
        """Extract reasoning steps using LLM."""
        prompt = f"""Analyze the following decision and extract the reasoning steps.

DECISION INPUT:
{json.dumps(decision_input, indent=2, default=str)[:2000]}

DECISION OUTPUT:
{json.dumps(decision_output, indent=2, default=str)[:2000]}

CONTEXT:
{json.dumps(context or {}, indent=2, default=str)[:500]}

Extract at least {min_steps} reasoning steps. For each step, provide:
1. A clear description of the reasoning
2. Evidence supporting the step
3. Confidence level (0.0-1.0)
4. Any references to code, documents, or external sources

Respond in JSON format:
{{
    "steps": [
        {{
            "description": "Step 1 reasoning",
            "evidence": ["evidence item 1", "evidence item 2"],
            "confidence": 0.9,
            "references": ["file.py:42", "doc.md"]
        }}
    ]
}}
"""

        try:
            response = await self._call_bedrock(prompt)
            return response.get("steps", [])
        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}, falling back to heuristic")
            return self._extract_steps_heuristic(
                decision_input, decision_output, min_steps
            )

    def _extract_steps_heuristic(
        self,
        decision_input: dict[str, Any],
        decision_output: dict[str, Any],
        min_steps: int,
    ) -> list[dict[str, Any]]:
        """Extract reasoning steps using heuristics."""
        steps = []

        # Step 1: Input analysis
        input_keys = list(decision_input.keys())
        steps.append(
            {
                "description": f"Analyzed input containing: {', '.join(input_keys[:5])}",
                "evidence": [f"Input key: {k}" for k in input_keys[:3]],
                "confidence": 0.9,
                "references": [],
            }
        )

        # Step 2: Processing logic (inferred from output type)
        output_type = self._infer_output_type(decision_output)
        steps.append(
            {
                "description": f"Applied {output_type} processing logic",
                "evidence": [f"Output type: {output_type}"],
                "confidence": 0.85,
                "references": [],
            }
        )

        # Step 3: Result determination
        if "action" in decision_output:
            steps.append(
                {
                    "description": f"Determined action: {decision_output['action']}",
                    "evidence": ["Action field present in output"],
                    "confidence": 0.95,
                    "references": [],
                }
            )
        elif "result" in decision_output:
            steps.append(
                {
                    "description": f"Produced result: {str(decision_output['result'])[:100]}",
                    "evidence": ["Result field present in output"],
                    "confidence": 0.95,
                    "references": [],
                }
            )

        # Step 4: Validation (if present)
        if any(k in decision_output for k in ["validated", "verified", "checked"]):
            steps.append(
                {
                    "description": "Validated output against requirements",
                    "evidence": ["Validation flags present"],
                    "confidence": 0.9,
                    "references": [],
                }
            )

        # Additional steps to meet minimum
        while len(steps) < min_steps:
            steps.append(
                {
                    "description": f"Applied decision rule {len(steps) + 1}",
                    "evidence": ["Inferred from decision pattern"],
                    "confidence": 0.7,
                    "references": [],
                }
            )

        return steps[: self.config.max_steps]

    def _infer_output_type(self, decision_output: dict[str, Any]) -> str:
        """Infer the type of decision from output structure."""
        if "code" in decision_output or "code_changes" in decision_output:
            return "code_generation"
        if "review" in decision_output or "findings" in decision_output:
            return "code_review"
        if "recommendation" in decision_output:
            return "recommendation"
        if "test" in decision_output or "test_results" in decision_output:
            return "testing"
        if "security" in decision_output or "vulnerability" in decision_output:
            return "security_analysis"
        return "general_processing"

    async def _call_bedrock(self, prompt: str) -> dict[str, Any]:
        """Call Bedrock for LLM extraction."""
        if not self.bedrock:
            return {"steps": []}

        try:
            response = self.bedrock.invoke_model(
                modelId=self.config.extraction_model,
                body=json.dumps(
                    {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": self.config.max_tokens,
                        "temperature": self.config.extraction_temperature,
                        "messages": [{"role": "user", "content": prompt}],
                    }
                ),
                contentType="application/json",
                accept="application/json",
            )

            response_body = json.loads(response["body"].read())
            content = response_body.get("content", [{}])[0].get("text", "{}")

            # Extract JSON from response
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {"steps": []}

        except Exception as e:
            logger.error(f"Bedrock call failed: {e}")
            return {"steps": []}


# Global instance management
_reasoning_chain_builder: Optional[ReasoningChainBuilder] = None


def get_reasoning_chain_builder() -> ReasoningChainBuilder:
    """Get the global reasoning chain builder instance."""
    global _reasoning_chain_builder
    if _reasoning_chain_builder is None:
        _reasoning_chain_builder = ReasoningChainBuilder()
    return _reasoning_chain_builder


def configure_reasoning_chain_builder(
    bedrock_client: Any = None,
    config: Optional[ReasoningChainConfig] = None,
) -> ReasoningChainBuilder:
    """Configure and return the global reasoning chain builder."""
    global _reasoning_chain_builder
    _reasoning_chain_builder = ReasoningChainBuilder(
        bedrock_client=bedrock_client,
        config=config,
    )
    return _reasoning_chain_builder


def reset_reasoning_chain_builder() -> None:
    """Reset the global reasoning chain builder instance."""
    global _reasoning_chain_builder
    _reasoning_chain_builder = None
