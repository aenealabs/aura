"""ADR Generator Agent for Autonomous ADR Generation Pipeline.

This agent generates fully-structured Architecture Decision Records
from ADR trigger events, including context, alternatives, consequences,
and references.

Part of ADR-010: Autonomous ADR Generation Pipeline

Integrates with BedrockLLMService for production LLM calls.
Updated: 2025-12-01 (Bedrock integration)
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from .adaptive_intelligence_agent import AdaptiveRecommendation, EffortLevel, RiskLevel
from .architecture_review_agent import ADRCategory, ADRTriggerEvent
from .monitoring_service import AgentRole, MonitorAgent

if TYPE_CHECKING:
    from src.services.bedrock_llm_service import BedrockLLMService

logger = logging.getLogger(__name__)


@dataclass
class ADRDocument:
    """Complete ADR document structure."""

    number: int
    title: str
    status: str  # Proposed, Accepted, Deprecated, Superseded
    date: str
    decision_makers: str
    context: str
    decision: str
    alternatives: list[dict[str, Any]] = field(default_factory=list)
    consequences_positive: list[str] = field(default_factory=list)
    consequences_negative: list[str] = field(default_factory=list)
    consequences_mitigation: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    source_trigger: ADRTriggerEvent | None = None

    def to_markdown(self) -> str:
        """Render ADR as markdown document.

        Returns:
            Complete ADR in markdown format.
        """
        lines = []

        # Header
        lines.append(f"# ADR-{self.number:03d}: {self.title}")
        lines.append("")
        lines.append(f"**Status:** {self.status}")
        lines.append(f"**Date:** {self.date}")
        lines.append(f"**Decision Makers:** {self.decision_makers}")
        lines.append("")

        # Context
        lines.append("## Context")
        lines.append("")
        lines.append(self.context)
        lines.append("")

        # Decision
        lines.append("## Decision")
        lines.append("")
        lines.append(self.decision)
        lines.append("")

        # Alternatives Considered
        if self.alternatives:
            lines.append("## Alternatives Considered")
            lines.append("")
            for i, alt in enumerate(self.alternatives, 1):
                lines.append(f"### Alternative {i}: {alt['title']}")
                lines.append("")
                lines.append(alt.get("description", ""))
                lines.append("")
                if alt.get("pros"):
                    lines.append("**Pros:**")
                    for pro in alt["pros"]:
                        lines.append(f"- {pro}")
                    lines.append("")
                if alt.get("cons"):
                    lines.append("**Cons:**")
                    for con in alt["cons"]:
                        lines.append(f"- {con}")
                    lines.append("")

        # Consequences
        lines.append("## Consequences")
        lines.append("")

        if self.consequences_positive:
            lines.append("### Positive")
            lines.append("")
            for i, pos in enumerate(self.consequences_positive, 1):
                lines.append(f"{i}. {pos}")
            lines.append("")

        if self.consequences_negative:
            lines.append("### Negative")
            lines.append("")
            for i, neg in enumerate(self.consequences_negative, 1):
                lines.append(f"{i}. {neg}")
            lines.append("")

        if self.consequences_mitigation:
            lines.append("### Mitigation")
            lines.append("")
            for mitigation in self.consequences_mitigation:
                lines.append(f"- {mitigation}")
            lines.append("")

        # References
        if self.references:
            lines.append("## References")
            lines.append("")
            for ref in self.references:
                lines.append(f"- {ref}")
            lines.append("")

        return "\n".join(lines)

    def get_filename(self) -> str:
        """Generate filename for ADR.

        Returns:
            Filename in standard ADR format.
        """
        # Convert title to kebab-case
        slug = self.title.lower()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"[\s_]+", "-", slug)
        slug = re.sub(r"-+", "-", slug)
        slug = slug.strip("-")[:50]  # Limit length

        return f"ADR-{self.number:03d}-{slug}.md"


class ADRGeneratorAgent:
    """Agent for ADR document creation.

    Generates fully-structured Architecture Decision Records from
    ADR trigger events, including:
    - Context synthesis from threat intelligence and recommendations
    - Alternative evaluation
    - Trade-off analysis (consequences)
    - Reference compilation

    Produces ADRDocument objects ready for review and commit.
    """

    def __init__(
        self,
        llm_client: "BedrockLLMService | None" = None,
        adr_directory: str | Path = "docs/architecture-decisions",
        monitor: MonitorAgent | None = None,
    ):
        """Initialize the ADR Generator Agent.

        Args:
            llm_client: LLM client for intelligent generation (BedrockLLMService).
            adr_directory: Path to ADR directory.
            monitor: Optional monitoring agent for metrics/logging.
        """
        self.llm = llm_client
        self.adr_directory = Path(adr_directory)
        self.monitor = monitor
        self._next_adr_number = self._get_next_adr_number()
        logger.info("Initialized ADRGeneratorAgent")

    async def generate_adrs(
        self, trigger_events: list[ADRTriggerEvent]
    ) -> list[ADRDocument]:
        """Generate ADR documents from trigger events.

        Uses LLM for intelligent content generation when available.

        Args:
            trigger_events: List of ADR trigger events.

        Returns:
            List of generated ADR documents.
        """
        self._log_activity(f"Generating ADRs from {len(trigger_events)} triggers")

        adrs = []
        for trigger in trigger_events:
            adr = await self._generate_adr(trigger)
            adrs.append(adr)
            self._next_adr_number += 1

        self._log_activity(f"Generated {len(adrs)} ADR documents")

        return adrs

    async def _generate_adr(self, trigger: ADRTriggerEvent) -> ADRDocument:
        """Generate single ADR from trigger event.

        Uses LLM for intelligent content generation when available.

        Args:
            trigger: ADR trigger event.

        Returns:
            Generated ADR document.
        """
        recommendation = trigger.source_recommendation

        # Generate content using LLM if available, otherwise use fallback
        if self.llm:
            try:
                context = await self._synthesize_context_llm(trigger, recommendation)
                decision = await self._formulate_decision_llm(trigger, recommendation)
                alternatives = await self._evaluate_alternatives_llm(
                    trigger, recommendation
                )
                positives, negatives, mitigations = (
                    await self._analyze_consequences_llm(trigger, recommendation)
                )
            except Exception as e:
                logger.warning(f"LLM generation failed, using fallback: {e}")
                context = self._synthesize_context_fallback(trigger, recommendation)
                decision = self._formulate_decision_fallback(trigger, recommendation)
                alternatives = self._evaluate_alternatives_fallback(
                    trigger, recommendation
                )
                positives, negatives, mitigations = self._analyze_consequences_fallback(
                    trigger, recommendation
                )
        else:
            context = self._synthesize_context_fallback(trigger, recommendation)
            decision = self._formulate_decision_fallback(trigger, recommendation)
            alternatives = self._evaluate_alternatives_fallback(trigger, recommendation)
            positives, negatives, mitigations = self._analyze_consequences_fallback(
                trigger, recommendation
            )

        # Compile references (no LLM needed - deterministic)
        references = self._compile_references(trigger, recommendation)

        adr = ADRDocument(
            number=self._next_adr_number,
            title=trigger.title,
            status="Proposed",
            date=datetime.now().strftime("%Y-%m-%d"),
            decision_makers="Aura Adaptive Intelligence",
            context=context,
            decision=decision,
            alternatives=alternatives,
            consequences_positive=positives,
            consequences_negative=negatives,
            consequences_mitigation=mitigations,
            references=references,
            source_trigger=trigger,
        )

        return adr

    async def _synthesize_context_llm(
        self,
        trigger: ADRTriggerEvent,
        recommendation: AdaptiveRecommendation | None,
    ) -> str:
        """Synthesize context section using LLM.

        Args:
            trigger: ADR trigger event.
            recommendation: Source recommendation.

        Returns:
            Context section text.
        """
        # Build context data for prompt
        threat_info = ""
        if recommendation and recommendation.source_threat:
            threat = recommendation.source_threat
            threat_info = f"""
Threat Intelligence:
- Title: {threat.title}
- Source: {threat.source}
- CVEs: {', '.join(threat.cve_ids) if threat.cve_ids else 'None'}
- CVSS Score: {threat.cvss_score if threat.cvss_score else 'Not available'}"""

        prompt = f"""You are a technical writer specializing in Architecture Decision Records. Generate a comprehensive Context section for an ADR.

ADR TITLE: {trigger.title}
CATEGORY: {trigger.category.value}
SIGNIFICANCE: {trigger.significance.value}

TRIGGER CONTEXT:
{trigger.context_summary}

AFFECTED COMPONENTS: {', '.join(trigger.affected_components) if trigger.affected_components else 'None identified'}
PATTERN DEVIATIONS: {', '.join(trigger.pattern_deviations) if trigger.pattern_deviations else 'None'}
EXISTING ADR REFERENCES: {', '.join(trigger.existing_adr_references) if trigger.existing_adr_references else 'None'}
{threat_info}

COMPLIANCE IMPACT: {', '.join(recommendation.compliance_impact) if recommendation and recommendation.compliance_impact else 'None identified'}

REQUIREMENTS:
- Write a clear, professional Context section (3-5 paragraphs)
- Explain the background and why this decision is needed
- Reference the threat intelligence if applicable
- Mention affected components and compliance implications
- Use markdown formatting

RESPOND IN JSON FORMAT:
{{
  "context": "Your context section text here..."
}}

Generate the Context section now:"""

        if self.llm is None:
            return ""
        response = await self.llm.generate(prompt, agent="ADRGenerator")
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                data = json.loads(response[json_start:json_end])
                return cast(str, data.get("context", ""))
        except Exception as e:
            logger.warning(f"Failed to parse context response: {e}")
        return ""

    def _synthesize_context_fallback(
        self,
        trigger: ADRTriggerEvent,
        recommendation: AdaptiveRecommendation | None,
    ) -> str:
        """Synthesize context section (fallback without LLM).

        Args:
            trigger: ADR trigger event.
            recommendation: Source recommendation.

        Returns:
            Context section text.
        """
        parts = []

        # Opening context
        parts.append(trigger.context_summary)
        parts.append("")

        # Threat context if available
        if recommendation and recommendation.source_threat:
            threat = recommendation.source_threat
            parts.append(
                f"This decision was triggered by security intelligence from {threat.source}:"
            )
            parts.append(f"- **Threat:** {threat.title}")
            if threat.cve_ids:
                parts.append(f"- **CVEs:** {', '.join(threat.cve_ids)}")
            if threat.cvss_score:
                parts.append(f"- **CVSS Score:** {threat.cvss_score}")
            parts.append("")

        # Affected components
        if trigger.affected_components:
            parts.append("**Affected Components:**")
            for component in trigger.affected_components:
                parts.append(f"- {component}")
            parts.append("")

        # Pattern deviations if any
        if trigger.pattern_deviations:
            parts.append("**Pattern Deviations Detected:**")
            for deviation in trigger.pattern_deviations:
                parts.append(f"- {deviation}")
            parts.append("")

        # Related ADRs
        if trigger.existing_adr_references:
            parts.append("**Related Architecture Decisions:**")
            for adr_ref in trigger.existing_adr_references:
                parts.append(f"- {adr_ref}")
            parts.append("")

        # Compliance context
        if recommendation and recommendation.compliance_impact:
            parts.append("**Compliance Implications:**")
            for impact in recommendation.compliance_impact:
                parts.append(f"- {impact}")
            parts.append("")

        return "\n".join(parts)

    async def _formulate_decision_llm(
        self,
        trigger: ADRTriggerEvent,
        recommendation: AdaptiveRecommendation | None,
    ) -> str:
        """Formulate decision section using LLM."""
        impl_steps = ""
        if recommendation and recommendation.implementation_steps:
            impl_steps = "\n".join(
                f"- {step}" for step in recommendation.implementation_steps
            )

        prompt = f"""You are a technical writer specializing in Architecture Decision Records. Generate a comprehensive Decision section for an ADR.

ADR TITLE: {trigger.title}
CATEGORY: {trigger.category.value}

RATIONALE: {recommendation.rationale if recommendation else 'Not available'}

IMPLEMENTATION STEPS:
{impl_steps if impl_steps else 'Not available'}

BEST PRACTICES: {', '.join(bp.title for bp in recommendation.best_practices) if recommendation and recommendation.best_practices else 'None'}

REQUIREMENTS:
- Write a clear decision statement explaining what was decided
- Include the rationale for the decision
- Reference implementation approach
- List validation criteria as checkboxes
- Use markdown formatting

RESPOND IN JSON FORMAT:
{{
  "decision": "Your decision section text here..."
}}

Generate the Decision section now:"""

        if self.llm is None:
            return ""
        response = await self.llm.generate(prompt, agent="ADRGenerator")
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                data = json.loads(response[json_start:json_end])
                return cast(str, data.get("decision", ""))
        except Exception as e:
            logger.warning(f"Failed to parse decision response: {e}")
        return ""

    def _formulate_decision_fallback(
        self,
        trigger: ADRTriggerEvent,
        recommendation: AdaptiveRecommendation | None,
    ) -> str:
        """Formulate decision section (fallback without LLM).

        Args:
            trigger: ADR trigger event.
            recommendation: Source recommendation.

        Returns:
            Decision section text.
        """
        parts = []

        # Decision statement
        category_actions = {
            ADRCategory.SECURITY: "implement security remediation",
            ADRCategory.INFRASTRUCTURE: "update infrastructure configuration",
            ADRCategory.DEPENDENCY: "upgrade affected dependencies",
            ADRCategory.CONFIGURATION: "modify system configuration",
            ADRCategory.COMPLIANCE: "update for compliance requirements",
            ADRCategory.OPTIMIZATION: "implement optimization",
            ADRCategory.INTEGRATION: "integrate new component",
        }

        action = category_actions.get(trigger.category, "address the identified issue")
        parts.append(f"We chose to **{action}** based on the following rationale:")
        parts.append("")

        # Rationale
        if recommendation:
            parts.append(recommendation.rationale)
            parts.append("")

        # Implementation approach
        if recommendation and recommendation.implementation_steps:
            parts.append("**Implementation Approach:**")
            parts.append("")
            for i, step in enumerate(recommendation.implementation_steps, 1):
                parts.append(f"{i}. {step}")
            parts.append("")

        # Best practices applied
        if recommendation and recommendation.best_practices:
            parts.append("**Best Practices Applied:**")
            parts.append("")
            for bp in recommendation.best_practices:
                parts.append(f"- **{bp.title}** ({bp.source}): {bp.description}")
            parts.append("")

        # Validation criteria
        if recommendation and recommendation.validation_criteria:
            parts.append("**Validation Criteria:**")
            parts.append("")
            for criterion in recommendation.validation_criteria:
                parts.append(f"- [ ] {criterion}")
            parts.append("")

        return "\n".join(parts)

    async def _evaluate_alternatives_llm(
        self,
        trigger: ADRTriggerEvent,
        recommendation: AdaptiveRecommendation | None,
    ) -> list[dict[str, Any]]:
        """Evaluate alternatives using LLM."""
        prompt = f"""You are a technical writer specializing in Architecture Decision Records. Generate alternatives for an ADR.

ADR TITLE: {trigger.title}
CATEGORY: {trigger.category.value}
CONTEXT: {trigger.context_summary}

REQUIREMENTS:
- Generate 2-3 alternatives that were considered
- For each alternative, provide title, description, pros, and cons
- Mark the chosen alternative with "(Chosen)" in the title
- Be specific to the category (security, dependency, infrastructure, etc.)

RESPOND IN JSON FORMAT:
{{
  "alternatives": [
    {{
      "title": "Alternative 1 Title",
      "description": "Description of the alternative",
      "pros": ["Pro 1", "Pro 2"],
      "cons": ["Con 1", "Con 2"]
    }},
    {{
      "title": "Alternative 2 (Chosen)",
      "description": "Description of the chosen approach",
      "pros": ["Pro 1", "Pro 2"],
      "cons": ["Con 1"]
    }}
  ]
}}

Generate the alternatives now:"""

        if self.llm is None:
            return []
        response = await self.llm.generate(prompt, agent="ADRGenerator")
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                data = json.loads(response[json_start:json_end])
                return cast(list[dict[str, Any]], data.get("alternatives", []))
        except Exception as e:
            logger.warning(f"Failed to parse alternatives response: {e}")
        return []

    def _evaluate_alternatives_fallback(
        self,
        trigger: ADRTriggerEvent,
        recommendation: AdaptiveRecommendation | None,
    ) -> list[dict[str, Any]]:
        """Evaluate alternatives (fallback without LLM).

        Args:
            trigger: ADR trigger event.
            recommendation: Source recommendation.

        Returns:
            List of alternative options with pros/cons.
        """
        alternatives = []

        # Generate alternatives based on category
        if trigger.category == ADRCategory.SECURITY:
            alternatives = self._generate_security_alternatives(recommendation)
        elif trigger.category == ADRCategory.DEPENDENCY:
            alternatives = self._generate_dependency_alternatives(recommendation)
        elif trigger.category == ADRCategory.INFRASTRUCTURE:
            alternatives = self._generate_infrastructure_alternatives(recommendation)
        elif trigger.category == ADRCategory.COMPLIANCE:
            alternatives = self._generate_compliance_alternatives(recommendation)
        else:
            alternatives = self._generate_generic_alternatives(recommendation)

        return alternatives

    def _generate_security_alternatives(
        self, recommendation: AdaptiveRecommendation | None
    ) -> list[dict[str, Any]]:
        """Generate alternatives for security decisions.

        Args:
            recommendation: Source recommendation.

        Returns:
            List of security alternatives.
        """
        return [
            {
                "title": "Accept Risk (Do Nothing)",
                "description": "Document the vulnerability and accept the risk without remediation.",
                "pros": [
                    "No implementation effort required",
                    "No risk of introducing regressions",
                ],
                "cons": [
                    "Vulnerability remains exploitable",
                    "Compliance violations likely",
                    "Potential security incident",
                    "Audit findings",
                ],
            },
            {
                "title": "Compensating Controls Only",
                "description": "Implement compensating controls (WAF rules, network restrictions) without patching.",
                "pros": [
                    "Faster to implement",
                    "No code changes required",
                    "Reduces attack surface",
                ],
                "cons": [
                    "Root cause not addressed",
                    "Controls may be bypassed",
                    "Technical debt accumulates",
                    "May not satisfy compliance",
                ],
            },
            {
                "title": "Immediate Patch (Chosen)",
                "description": "Apply security patch through validated remediation process.",
                "pros": [
                    "Addresses root cause",
                    "Compliance maintained",
                    "Reduces long-term risk",
                    "Follows security best practices",
                ],
                "cons": [
                    "Implementation effort required",
                    "Potential for regressions",
                    "Requires testing resources",
                ],
            },
        ]

    def _generate_dependency_alternatives(
        self, recommendation: AdaptiveRecommendation | None
    ) -> list[dict[str, Any]]:
        """Generate alternatives for dependency decisions.

        Args:
            recommendation: Source recommendation.

        Returns:
            List of dependency alternatives.
        """
        return [
            {
                "title": "Pin Current Version",
                "description": "Keep current vulnerable version and monitor for exploits.",
                "pros": [
                    "No compatibility testing needed",
                    "Stable known behavior",
                ],
                "cons": [
                    "Vulnerability remains",
                    "Security debt accumulates",
                    "May block future upgrades",
                ],
            },
            {
                "title": "Replace Dependency",
                "description": "Switch to alternative library without the vulnerability.",
                "pros": [
                    "Eliminates vulnerability",
                    "May get additional features",
                ],
                "cons": [
                    "Significant refactoring effort",
                    "New library learning curve",
                    "Different API to adapt to",
                ],
            },
            {
                "title": "Upgrade to Patched Version (Chosen)",
                "description": "Upgrade dependency to version with security fix.",
                "pros": [
                    "Minimal code changes",
                    "Vulnerability addressed",
                    "Familiar API maintained",
                    "Future updates easier",
                ],
                "cons": [
                    "Potential breaking changes",
                    "Compatibility testing required",
                ],
            },
        ]

    def _generate_infrastructure_alternatives(
        self, recommendation: AdaptiveRecommendation | None
    ) -> list[dict[str, Any]]:
        """Generate alternatives for infrastructure decisions.

        Args:
            recommendation: Source recommendation.

        Returns:
            List of infrastructure alternatives.
        """
        return [
            {
                "title": "Manual Configuration",
                "description": "Apply changes manually through AWS Console.",
                "pros": [
                    "Immediate implementation",
                    "Visual verification",
                ],
                "cons": [
                    "Not reproducible",
                    "Drift from IaC",
                    "No audit trail in code",
                    "Violates single source of truth",
                ],
            },
            {
                "title": "Infrastructure as Code Update (Chosen)",
                "description": "Update CloudFormation/Terraform templates with changes.",
                "pros": [
                    "Reproducible",
                    "Version controlled",
                    "Audit trail maintained",
                    "Consistent across environments",
                ],
                "cons": [
                    "Deployment pipeline required",
                    "Testing overhead",
                ],
            },
        ]

    def _generate_compliance_alternatives(
        self, recommendation: AdaptiveRecommendation | None
    ) -> list[dict[str, Any]]:
        """Generate alternatives for compliance decisions.

        Args:
            recommendation: Source recommendation.

        Returns:
            List of compliance alternatives.
        """
        return [
            {
                "title": "Request Exception",
                "description": "Document exception request for compliance deviation.",
                "pros": [
                    "No implementation required",
                    "Formal risk acceptance",
                ],
                "cons": [
                    "Exception may be denied",
                    "Increased audit scrutiny",
                    "Temporary solution only",
                ],
            },
            {
                "title": "Implement Compliance Control (Chosen)",
                "description": "Implement required control to maintain compliance.",
                "pros": [
                    "Full compliance maintained",
                    "Reduced audit risk",
                    "Security posture improved",
                ],
                "cons": [
                    "Implementation effort",
                    "Potential process changes",
                ],
            },
        ]

    def _generate_generic_alternatives(
        self, recommendation: AdaptiveRecommendation | None
    ) -> list[dict[str, Any]]:
        """Generate generic alternatives.

        Args:
            recommendation: Source recommendation.

        Returns:
            List of generic alternatives.
        """
        return [
            {
                "title": "Defer Decision",
                "description": "Postpone decision pending further analysis.",
                "pros": [
                    "More time for evaluation",
                    "Additional data gathering",
                ],
                "cons": [
                    "Risk exposure continues",
                    "Decision debt accumulates",
                ],
            },
            {
                "title": "Implement Recommendation (Chosen)",
                "description": "Proceed with recommended changes.",
                "pros": [
                    "Addresses identified issue",
                    "Follows best practices",
                    "Reduces technical debt",
                ],
                "cons": [
                    "Implementation effort required",
                    "Change management overhead",
                ],
            },
        ]

    async def _analyze_consequences_llm(
        self,
        trigger: ADRTriggerEvent,
        recommendation: AdaptiveRecommendation | None,
    ) -> tuple[list[str], list[str], list[str]]:
        """Analyze consequences using LLM."""
        risk_info = ""
        if recommendation:
            risk_info = f"""
Risk Level: {recommendation.risk_level.value if recommendation.risk_level else 'Unknown'}
Risk Score: {recommendation.risk_score}/10
Effort Level: {recommendation.effort_level.value if recommendation.effort_level else 'Unknown'}"""

        prompt = f"""You are a technical writer specializing in Architecture Decision Records. Generate consequences for an ADR.

ADR TITLE: {trigger.title}
CATEGORY: {trigger.category.value}
CONTEXT: {trigger.context_summary}
{risk_info}

REQUIREMENTS:
- Generate 3-4 positive consequences
- Generate 2-3 negative consequences
- Generate 2-3 mitigation strategies for the negative consequences
- Be specific to the category and context

RESPOND IN JSON FORMAT:
{{
  "positive": ["Positive consequence 1", "Positive consequence 2"],
  "negative": ["Negative consequence 1", "Negative consequence 2"],
  "mitigation": ["Mitigation strategy 1", "Mitigation strategy 2"]
}}

Generate the consequences now:"""

        if self.llm is None:
            return [], [], []
        response = await self.llm.generate(prompt, agent="ADRGenerator")
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                data = json.loads(response[json_start:json_end])
                return (
                    cast(list[str], data.get("positive", [])),
                    cast(list[str], data.get("negative", [])),
                    cast(list[str], data.get("mitigation", [])),
                )
        except Exception as e:
            logger.warning(f"Failed to parse consequences response: {e}")
        return [], [], []

    def _analyze_consequences_fallback(
        self,
        trigger: ADRTriggerEvent,
        recommendation: AdaptiveRecommendation | None,
    ) -> tuple[list[str], list[str], list[str]]:
        """Analyze consequences (fallback without LLM).

        Args:
            trigger: ADR trigger event.
            recommendation: Source recommendation.

        Returns:
            Tuple of (positive, negative, mitigation) consequences.
        """
        positives = []
        negatives = []
        mitigations = []

        # Category-specific consequences
        if trigger.category == ADRCategory.SECURITY:
            positives.extend(
                [
                    "Security vulnerability addressed",
                    "Compliance posture maintained",
                    "Reduced risk of security incident",
                    "Audit findings prevented",
                ]
            )
            negatives.extend(
                [
                    "Implementation effort required",
                    "Testing overhead for validation",
                ]
            )
            mitigations.extend(
                [
                    "Sandbox validation before production deployment",
                    "HITL approval for critical changes",
                    "Rollback plan documented and tested",
                ]
            )

        elif trigger.category == ADRCategory.DEPENDENCY:
            positives.extend(
                [
                    "Vulnerability in dependency addressed",
                    "Access to latest features and fixes",
                    "Reduced security debt",
                ]
            )
            negatives.extend(
                [
                    "Potential breaking changes from upgrade",
                    "Compatibility testing required",
                ]
            )
            mitigations.extend(
                [
                    "Review changelog for breaking changes",
                    "Run full test suite before deployment",
                    "Stage rollout with monitoring",
                ]
            )

        elif trigger.category == ADRCategory.INFRASTRUCTURE:
            positives.extend(
                [
                    "Infrastructure aligned with best practices",
                    "Improved security posture",
                    "Better observability/manageability",
                ]
            )
            negatives.extend(
                [
                    "Deployment complexity",
                    "Potential service disruption during update",
                ]
            )
            mitigations.extend(
                [
                    "Use CloudFormation change sets for preview",
                    "Deploy during maintenance window",
                    "Have rollback procedure ready",
                ]
            )

        elif trigger.category == ADRCategory.COMPLIANCE:
            positives.extend(
                [
                    "Compliance requirement satisfied",
                    "Audit readiness improved",
                    "Regulatory risk reduced",
                ]
            )
            negatives.extend(
                [
                    "Process changes may be required",
                    "Additional documentation burden",
                ]
            )
            mitigations.extend(
                [
                    "Document compliance evidence",
                    "Train team on new requirements",
                    "Schedule periodic compliance reviews",
                ]
            )

        else:
            positives.extend(
                [
                    "Issue addressed proactively",
                    "Technical debt reduced",
                    "System maintainability improved",
                ]
            )
            negatives.extend(
                [
                    "Implementation effort required",
                ]
            )
            mitigations.extend(
                [
                    "Follow standard change management process",
                    "Validate in non-production environment first",
                ]
            )

        # Add risk-based consequences
        if recommendation:
            if recommendation.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                negatives.append(
                    f"High-risk change (score: {recommendation.risk_score}/10) "
                    "requires careful validation"
                )
                mitigations.append("Extended sandbox testing period recommended")

            if recommendation.effort_level in [EffortLevel.LARGE, EffortLevel.MAJOR]:
                negatives.append(
                    f"Significant effort ({recommendation.effort_level.value}) "
                    "impacts team capacity"
                )
                mitigations.append("Consider phased implementation if possible")

        return positives, negatives, mitigations

    def _compile_references(
        self,
        trigger: ADRTriggerEvent,
        recommendation: AdaptiveRecommendation | None,
    ) -> list[str]:
        """Compile references for the ADR.

        Args:
            trigger: ADR trigger event.
            recommendation: Source recommendation.

        Returns:
            List of reference strings.
        """
        references = []

        # Related ADRs
        for adr_ref in trigger.existing_adr_references:
            references.append(f"`docs/architecture-decisions/{adr_ref}.md`")

        # Threat source references
        if recommendation and recommendation.source_threat:
            threat = recommendation.source_threat
            for ref in threat.references:
                references.append(ref)

        # Best practice references
        if recommendation:
            for bp in recommendation.best_practices:
                references.append(f"{bp.source}: {bp.title}")

        # Affected files
        if recommendation and recommendation.affected_files:
            references.append(
                f"Affected files: {', '.join(recommendation.affected_files[:5])}"
            )

        # Standard references
        references.extend(
            [
                "`docs/design/HITL_SANDBOX_ARCHITECTURE.md` - Sandbox validation process",
                "`agent-config/agents/security-code-reviewer.md` - Security review guidelines",
            ]
        )

        return references

    def save_adr(self, adr: ADRDocument) -> Path:
        """Save ADR document to filesystem.

        Args:
            adr: ADR document to save.

        Returns:
            Path to saved file.
        """
        filename = adr.get_filename()
        filepath = self.adr_directory / filename

        # Ensure directory exists
        self.adr_directory.mkdir(parents=True, exist_ok=True)

        # Write ADR
        content = adr.to_markdown()
        filepath.write_text(content)

        self._log_activity(f"Saved ADR to {filepath}")

        return filepath

    def update_readme_index(self, adrs: list[ADRDocument]) -> None:
        """Update README.md index with new ADRs.

        Args:
            adrs: List of ADR documents to add to index.
        """
        readme_path = self.adr_directory / "README.md"

        if not readme_path.exists():
            self._log_activity("README.md not found, skipping index update")
            return

        content = readme_path.read_text()

        # Find the index table
        table_pattern = (
            r"(\| ADR \| Title \| Status \| Date \|\n\|[-|]+\n(?:\|[^\n]+\n)*)"
        )
        match = re.search(table_pattern, content)

        if not match:
            self._log_activity("Could not find index table in README.md")
            return

        # Generate new rows
        new_rows = []
        for adr in adrs:
            filename = adr.get_filename()
            new_rows.append(
                f"| [ADR-{adr.number:03d}]({filename}) | {adr.title} | {adr.status} | {adr.date} |"
            )

        # Insert new rows before the blank line after table
        current_table = match.group(1)
        updated_table = current_table.rstrip() + "\n" + "\n".join(new_rows) + "\n"

        updated_content = content.replace(current_table, updated_table)

        readme_path.write_text(updated_content)
        self._log_activity(f"Updated README.md index with {len(adrs)} new ADRs")

    def _get_next_adr_number(self) -> int:
        """Get next available ADR number.

        Returns:
            Next sequential ADR number.
        """
        if not self.adr_directory.exists():
            return 1

        existing_numbers = []
        for file in self.adr_directory.glob("ADR-*.md"):
            match = re.match(r"ADR-(\d+)", file.stem)
            if match:
                existing_numbers.append(int(match.group(1)))

        if existing_numbers:
            return max(existing_numbers) + 1

        return 1

    def _log_activity(self, message: str) -> None:
        """Log agent activity.

        Args:
            message: Log message.
        """
        print(f"[{AgentRole.CODER.value}:ADRGenerator] {message}")

        if self.monitor:
            self.monitor.log_activity(
                role=AgentRole.CODER,
                activity=f"ADRGenerator: {message}",
            )


# Factory function for production usage
def create_adr_generator_agent(
    use_mock: bool = False,
    adr_directory: str | Path = "docs/architecture-decisions",
    monitor: MonitorAgent | None = None,
) -> "ADRGeneratorAgent":
    """
    Create an ADRGeneratorAgent with real or mock LLM.

    Args:
        use_mock: If True, use mock LLM for testing. If False, use real Bedrock.
        adr_directory: Path to ADR directory.
        monitor: Optional monitoring agent.

    Returns:
        Configured ADRGeneratorAgent instance
    """
    if use_mock:
        from unittest.mock import AsyncMock

        mock_llm = AsyncMock()
        # Configure mock responses
        mock_llm.generate.return_value = json.dumps(
            {
                "context": "Sample context for ADR document.",
                "decision": "Sample decision text with rationale.",
                "alternatives": [
                    {
                        "title": "Do Nothing",
                        "description": "Accept the risk",
                        "pros": ["No effort"],
                        "cons": ["Risk remains"],
                    },
                    {
                        "title": "Implement Fix (Chosen)",
                        "description": "Apply remediation",
                        "pros": ["Risk addressed"],
                        "cons": ["Effort required"],
                    },
                ],
                "positive": ["Security improved", "Compliance maintained"],
                "negative": ["Implementation effort"],
                "mitigation": ["Test thoroughly"],
            }
        )
        logger.info("Created ADRGeneratorAgent with mock LLM")
        return ADRGeneratorAgent(
            llm_client=mock_llm,
            adr_directory=adr_directory,
            monitor=monitor,
        )
    else:
        from src.services.bedrock_llm_service import create_llm_service

        llm_service = create_llm_service()
        logger.info("Created ADRGeneratorAgent with real Bedrock LLM")
        return ADRGeneratorAgent(
            llm_client=llm_service,
            adr_directory=adr_directory,
            monitor=monitor,
        )
