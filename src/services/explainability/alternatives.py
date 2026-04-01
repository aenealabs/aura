"""
Project Aura - Alternatives Analyzer

Analyzes and documents alternatives considered for a decision,
including pros/cons, comparison criteria, and rejection reasons.

Author: Project Aura Team
Created: 2026-01-25
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Optional

from .config import AlternativesConfig
from .contracts import AlternativesReport

logger = logging.getLogger(__name__)


class AlternativesAnalyzer:
    """
    Analyze alternatives considered for a decision.

    Discovers possible options, compares them using criteria,
    and documents why the chosen option was selected and
    why others were rejected.
    """

    def __init__(
        self,
        bedrock_client: Any = None,
        config: Optional[AlternativesConfig] = None,
    ):
        """
        Initialize the alternatives analyzer.

        Args:
            bedrock_client: AWS Bedrock client for LLM analysis
            config: Configuration for alternatives analysis
        """
        self.bedrock = bedrock_client
        self.config = config or AlternativesConfig()
        logger.info("AlternativesAnalyzer initialized")

    async def analyze(
        self,
        decision_id: str,
        decision_input: dict[str, Any],
        decision_output: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
        min_alternatives: int = 2,
    ) -> AlternativesReport:
        """
        Analyze alternatives for a decision.

        Args:
            decision_id: Unique identifier for the decision
            decision_input: Input data for the decision
            decision_output: Output/result of the decision
            context: Additional context for analysis
            min_alternatives: Minimum number of alternatives required

        Returns:
            AlternativesReport with analyzed alternatives
        """
        logger.debug(f"Analyzing alternatives for decision {decision_id}")

        report = AlternativesReport(
            decision_id=decision_id,
            comparison_criteria=self._get_comparison_criteria(
                decision_input, decision_output
            ),
        )

        # Discover alternatives
        if self.config.enable_llm_analysis and self.bedrock:
            alternatives_data = await self._discover_alternatives_with_llm(
                decision_input, decision_output, context, min_alternatives
            )
        else:
            alternatives_data = self._discover_alternatives_heuristic(
                decision_input, decision_output, min_alternatives
            )

        # Add alternatives to report
        for alt_data in alternatives_data:
            report.add_alternative(
                alternative_id=alt_data.get("id", f"alt_{uuid.uuid4().hex[:8]}"),
                description=alt_data.get("description", ""),
                confidence=alt_data.get("confidence", 0.5),
                pros=alt_data.get("pros", []),
                cons=alt_data.get("cons", []),
                was_chosen=alt_data.get("was_chosen", False),
                rejection_reason=alt_data.get("rejection_reason"),
            )

        # Ensure minimum alternatives
        while len(report.alternatives) < min_alternatives:
            report.add_alternative(
                alternative_id=f"alt_{uuid.uuid4().hex[:8]}",
                description=f"Alternative option {len(report.alternatives) + 1}",
                confidence=0.4,
                pros=["Could be considered"],
                cons=["Not the optimal choice"],
                was_chosen=False,
                rejection_reason="Not selected based on decision criteria",
            )

        # Set decision rationale
        chosen = report.get_chosen()
        if chosen:
            report.decision_rationale = (
                f"Selected '{chosen.description}' based on evaluation criteria"
            )
        else:
            report.decision_rationale = (
                "Decision made based on analysis of available options"
            )

        logger.debug(
            f"Analyzed {len(report.alternatives)} alternatives for decision {decision_id}"
        )
        return report

    def analyze_sync(
        self,
        decision_id: str,
        decision_input: dict[str, Any],
        decision_output: dict[str, Any],
        min_alternatives: int = 2,
    ) -> AlternativesReport:
        """
        Synchronous version using heuristic analysis.

        Args:
            decision_id: Unique identifier for the decision
            decision_input: Input data for the decision
            decision_output: Output/result of the decision
            min_alternatives: Minimum number of alternatives required

        Returns:
            AlternativesReport with analyzed alternatives
        """
        report = AlternativesReport(
            decision_id=decision_id,
            comparison_criteria=self._get_comparison_criteria(
                decision_input, decision_output
            ),
        )

        alternatives_data = self._discover_alternatives_heuristic(
            decision_input, decision_output, min_alternatives
        )

        for alt_data in alternatives_data:
            report.add_alternative(
                alternative_id=alt_data.get("id", f"alt_{uuid.uuid4().hex[:8]}"),
                description=alt_data.get("description", ""),
                confidence=alt_data.get("confidence", 0.5),
                pros=alt_data.get("pros", []),
                cons=alt_data.get("cons", []),
                was_chosen=alt_data.get("was_chosen", False),
                rejection_reason=alt_data.get("rejection_reason"),
            )

        while len(report.alternatives) < min_alternatives:
            report.add_alternative(
                alternative_id=f"alt_{uuid.uuid4().hex[:8]}",
                description=f"Alternative option {len(report.alternatives) + 1}",
                confidence=0.4,
                pros=["Could be considered"],
                cons=["Not the optimal choice"],
                was_chosen=False,
                rejection_reason="Not selected based on decision criteria",
            )

        chosen = report.get_chosen()
        if chosen:
            report.decision_rationale = (
                f"Selected '{chosen.description}' based on evaluation"
            )

        return report

    def _get_comparison_criteria(
        self,
        decision_input: dict[str, Any],
        decision_output: dict[str, Any],
    ) -> list[str]:
        """Determine comparison criteria based on decision type."""
        criteria = []

        # Infer criteria from input/output
        if (
            "security" in str(decision_input).lower()
            or "security" in str(decision_output).lower()
        ):
            criteria.append("Security impact")
        if "performance" in str(decision_input).lower():
            criteria.append("Performance impact")
        if "cost" in str(decision_input).lower():
            criteria.append("Cost efficiency")
        if "code" in str(decision_output).lower():
            criteria.extend(["Code quality", "Maintainability"])
        if "test" in str(decision_output).lower():
            criteria.append("Test coverage")

        # Default criteria
        if not criteria:
            criteria = [
                "Effectiveness",
                "Complexity",
                "Risk level",
            ]

        return criteria[: self.config.comparison_criteria_count]

    async def _discover_alternatives_with_llm(
        self,
        decision_input: dict[str, Any],
        decision_output: dict[str, Any],
        context: Optional[dict[str, Any]],
        min_alternatives: int,
    ) -> list[dict[str, Any]]:
        """Discover alternatives using LLM analysis."""
        prompt = f"""Analyze the following decision and identify alternatives that were or could have been considered.

DECISION INPUT:
{json.dumps(decision_input, indent=2, default=str)[:1500]}

DECISION OUTPUT (CHOSEN):
{json.dumps(decision_output, indent=2, default=str)[:1500]}

CONTEXT:
{json.dumps(context or {}, indent=2, default=str)[:500]}

Identify at least {min_alternatives} alternatives including the chosen one. For each:
1. Describe the alternative
2. List pros and cons
3. Provide a confidence score (0.0-1.0) for how good this option is
4. If not chosen, explain why it was rejected

Respond in JSON format:
{{
    "alternatives": [
        {{
            "id": "alt_001",
            "description": "The chosen approach",
            "pros": ["pro 1", "pro 2"],
            "cons": ["con 1"],
            "confidence": 0.9,
            "was_chosen": true,
            "rejection_reason": null
        }},
        {{
            "id": "alt_002",
            "description": "Alternative approach",
            "pros": ["pro 1"],
            "cons": ["con 1", "con 2"],
            "confidence": 0.6,
            "was_chosen": false,
            "rejection_reason": "Higher complexity without significant benefit"
        }}
    ]
}}
"""

        try:
            response = await self._call_bedrock(prompt)
            return response.get("alternatives", [])
        except Exception as e:
            logger.warning(f"LLM analysis failed: {e}, falling back to heuristic")
            return self._discover_alternatives_heuristic(
                decision_input, decision_output, min_alternatives
            )

    def _discover_alternatives_heuristic(
        self,
        decision_input: dict[str, Any],
        decision_output: dict[str, Any],
        min_alternatives: int,
    ) -> list[dict[str, Any]]:
        """Discover alternatives using heuristics."""
        alternatives = []

        # The chosen alternative (based on actual output)
        chosen_desc = self._describe_chosen(decision_output)
        alternatives.append(
            {
                "id": f"alt_{uuid.uuid4().hex[:8]}",
                "description": chosen_desc,
                "pros": self._infer_pros(decision_output),
                "cons": ["May have trade-offs"],
                "confidence": 0.85,
                "was_chosen": True,
                "rejection_reason": None,
            }
        )

        # Generate alternative options based on decision type
        decision_type = self._infer_decision_type(decision_input, decision_output)

        if decision_type == "code_change":
            alternatives.extend(
                [
                    {
                        "id": f"alt_{uuid.uuid4().hex[:8]}",
                        "description": "No code change - accept current behavior",
                        "pros": ["No implementation risk", "No testing required"],
                        "cons": ["Issue remains unaddressed"],
                        "confidence": 0.3,
                        "was_chosen": False,
                        "rejection_reason": "Does not address the underlying issue",
                    },
                    {
                        "id": f"alt_{uuid.uuid4().hex[:8]}",
                        "description": "Refactor entire module for comprehensive fix",
                        "pros": ["Thorough solution", "Addresses root cause"],
                        "cons": ["High complexity", "Longer implementation time"],
                        "confidence": 0.5,
                        "was_chosen": False,
                        "rejection_reason": "Scope exceeds immediate requirements",
                    },
                ]
            )
        elif decision_type == "security":
            alternatives.extend(
                [
                    {
                        "id": f"alt_{uuid.uuid4().hex[:8]}",
                        "description": "Apply minimal security patch",
                        "pros": ["Quick implementation", "Low risk"],
                        "cons": ["May not fully address vulnerability"],
                        "confidence": 0.6,
                        "was_chosen": False,
                        "rejection_reason": "Insufficient coverage of security risk",
                    },
                    {
                        "id": f"alt_{uuid.uuid4().hex[:8]}",
                        "description": "Implement defense-in-depth approach",
                        "pros": ["Comprehensive protection", "Future-proof"],
                        "cons": ["Higher complexity", "More resources needed"],
                        "confidence": 0.7,
                        "was_chosen": False,
                        "rejection_reason": "Selected approach provides adequate protection",
                    },
                ]
            )
        else:
            # Generic alternatives
            alternatives.extend(
                [
                    {
                        "id": f"alt_{uuid.uuid4().hex[:8]}",
                        "description": "Alternative approach using different methodology",
                        "pros": ["Different perspective"],
                        "cons": ["Less proven"],
                        "confidence": 0.5,
                        "was_chosen": False,
                        "rejection_reason": "Current approach better suited to requirements",
                    },
                    {
                        "id": f"alt_{uuid.uuid4().hex[:8]}",
                        "description": "Defer decision for more information",
                        "pros": ["More informed decision later"],
                        "cons": ["Delays progress"],
                        "confidence": 0.4,
                        "was_chosen": False,
                        "rejection_reason": "Sufficient information available for decision",
                    },
                ]
            )

        return alternatives[: self.config.max_alternatives]

    def _describe_chosen(self, decision_output: dict[str, Any]) -> str:
        """Describe the chosen alternative from output."""
        if "action" in decision_output:
            return f"Execute action: {decision_output['action']}"
        if "recommendation" in decision_output:
            return f"Recommendation: {decision_output['recommendation']}"
        if "code_changes" in decision_output:
            return "Implement proposed code changes"
        if "result" in decision_output:
            return f"Apply result: {str(decision_output['result'])[:100]}"
        return "Apply the determined solution"

    def _infer_pros(self, decision_output: dict[str, Any]) -> list[str]:
        """Infer pros of the chosen option."""
        pros = []
        if "verified" in decision_output or "validated" in decision_output:
            pros.append("Verified and validated")
        if "tests" in decision_output:
            pros.append("Has test coverage")
        if "secure" in str(decision_output).lower():
            pros.append("Security considerations addressed")
        if not pros:
            pros = ["Addresses requirements", "Feasible implementation"]
        return pros

    def _infer_decision_type(
        self,
        decision_input: dict[str, Any],
        decision_output: dict[str, Any],
    ) -> str:
        """Infer the type of decision."""
        combined = str(decision_input) + str(decision_output)
        if "security" in combined.lower() or "vulnerability" in combined.lower():
            return "security"
        if "code" in combined.lower() or "fix" in combined.lower():
            return "code_change"
        if "test" in combined.lower():
            return "testing"
        if "review" in combined.lower():
            return "review"
        return "general"

    async def _call_bedrock(self, prompt: str) -> dict[str, Any]:
        """Call Bedrock for LLM analysis."""
        if not self.bedrock:
            return {"alternatives": []}

        try:
            response = self.bedrock.invoke_model(
                modelId=self.config.analysis_model,
                body=json.dumps(
                    {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 2000,
                        "temperature": self.config.analysis_temperature,
                        "messages": [{"role": "user", "content": prompt}],
                    }
                ),
                contentType="application/json",
                accept="application/json",
            )

            response_body = json.loads(response["body"].read())
            content = response_body.get("content", [{}])[0].get("text", "{}")

            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {"alternatives": []}

        except Exception as e:
            logger.error(f"Bedrock call failed: {e}")
            return {"alternatives": []}


# Global instance management
_alternatives_analyzer: Optional[AlternativesAnalyzer] = None


def get_alternatives_analyzer() -> AlternativesAnalyzer:
    """Get the global alternatives analyzer instance."""
    global _alternatives_analyzer
    if _alternatives_analyzer is None:
        _alternatives_analyzer = AlternativesAnalyzer()
    return _alternatives_analyzer


def configure_alternatives_analyzer(
    bedrock_client: Any = None,
    config: Optional[AlternativesConfig] = None,
) -> AlternativesAnalyzer:
    """Configure and return the global alternatives analyzer."""
    global _alternatives_analyzer
    _alternatives_analyzer = AlternativesAnalyzer(
        bedrock_client=bedrock_client,
        config=config,
    )
    return _alternatives_analyzer


def reset_alternatives_analyzer() -> None:
    """Reset the global alternatives analyzer instance."""
    global _alternatives_analyzer
    _alternatives_analyzer = None
