"""
Report Generator for Technical Documentation
=============================================

Generates technical documentation reports from code analysis.
ADR-056: Documentation Agent for Architecture and Data Flow Diagrams.

Report sections:
- Executive Summary
- Service Inventory
- Data Flow Analysis
- Security Considerations
- Recommendations
"""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from src.services.documentation.exceptions import (
    LLMGenerationError,
    ReportGenerationError,
)
from src.services.documentation.types import (
    ConfidenceLevel,
    DataFlow,
    DiagramResult,
    ReportSection,
    ServiceBoundary,
    TechnicalReport,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.services.bedrock_llm_service import BedrockLLMService


class ReportGenerator:
    """
    Generates technical documentation reports.

    The generator creates structured Markdown reports from code analysis
    results, optionally using an LLM for enhanced descriptions.

    Example:
        >>> generator = ReportGenerator()
        >>> report = await generator.generate(
        ...     repository_id="my-app",
        ...     boundaries=boundaries,
        ...     data_flows=flows,
        ...     diagrams=diagrams,
        ... )
        >>> print(report.to_markdown())
    """

    # Section templates for consistent formatting
    SECTION_TEMPLATES = {
        "service_inventory": """
### {service_name}

**Confidence:** {confidence:.1%} ({confidence_level})

{description}

**Components:** {component_count}
**Internal Edges:** {internal_edges}
**External Edges:** {external_edges}
**Modularity Ratio:** {modularity:.2f}

**Entry Points:**
{entry_points}
""",
        "data_flow": """
### {flow_name}

**Source:** {source}
**Target:** {target}
**Type:** {flow_type}
**Protocol:** {protocol}
**Classification:** {classification}
**Confidence:** {confidence:.1%}
""",
    }

    def __init__(
        self,
        llm_client: "BedrockLLMService | None" = None,
        include_confidence_details: bool = True,
    ):
        """
        Initialize the report generator.

        Args:
            llm_client: Optional LLM for enhanced descriptions
            include_confidence_details: Include per-section confidence scores
        """
        self.llm = llm_client
        self.include_confidence_details = include_confidence_details

    async def generate(
        self,
        repository_id: str,
        boundaries: list[ServiceBoundary] | None = None,
        data_flows: list[DataFlow] | None = None,
        diagrams: list[DiagramResult] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TechnicalReport:
        """
        Generate a technical documentation report.

        Args:
            repository_id: Repository being documented
            boundaries: Detected service boundaries
            data_flows: Detected data flows
            diagrams: Generated diagrams
            metadata: Additional metadata

        Returns:
            TechnicalReport with all sections

        Raises:
            ReportGenerationError: If generation fails
        """
        logger.info(f"Generating technical report for repository: {repository_id}")

        try:
            sections: list[ReportSection] = []
            overall_confidence = 0.5

            # Executive Summary
            summary_section = await self._generate_executive_summary(
                repository_id, boundaries, data_flows, diagrams
            )
            sections.append(summary_section)

            # Service Inventory
            if boundaries:
                inventory_section = self._generate_service_inventory(boundaries)
                sections.append(inventory_section)
                overall_confidence = max(
                    overall_confidence, inventory_section.confidence
                )

            # Data Flow Analysis
            if data_flows:
                flow_section = self._generate_data_flow_analysis(data_flows)
                sections.append(flow_section)
                overall_confidence = max(overall_confidence, flow_section.confidence)

            # Security Considerations
            security_section = self._generate_security_considerations(
                boundaries, data_flows
            )
            sections.append(security_section)

            # Recommendations
            recommendations_section = self._generate_recommendations(
                boundaries, data_flows, diagrams
            )
            sections.append(recommendations_section)

            # Calculate overall confidence
            if sections:
                overall_confidence = sum(s.confidence for s in sections) / len(sections)

            # Generate executive summary text
            executive_summary = self._build_executive_summary_text(
                repository_id, boundaries, data_flows, diagrams, overall_confidence
            )

            report = TechnicalReport(
                title=f"Technical Documentation: {repository_id}",
                executive_summary=executive_summary,
                sections=sections,
                generated_at=datetime.now(timezone.utc),
                confidence=overall_confidence,
                repository_id=repository_id,
                metadata=metadata or {},
            )

            logger.info(
                f"Generated report with {len(sections)} sections, "
                f"confidence={overall_confidence:.2f}"
            )
            return report

        except Exception as e:
            raise ReportGenerationError(
                f"Failed to generate report: {e}",
                details={"repository_id": repository_id, "error": str(e)},
            )

    async def _generate_executive_summary(
        self,
        repository_id: str,
        boundaries: list[ServiceBoundary] | None,
        data_flows: list[DataFlow] | None,
        diagrams: list[DiagramResult] | None,
    ) -> ReportSection:
        """Generate executive summary section."""
        lines = []

        # Key metrics
        service_count = len(boundaries) if boundaries else 0
        flow_count = len(data_flows) if data_flows else 0
        diagram_count = len(diagrams) if diagrams else 0

        lines.append("This document provides an automated analysis of the codebase.")
        lines.append("")
        lines.append("### Key Metrics")
        lines.append("")
        lines.append(f"- **Services Detected:** {service_count}")
        lines.append(f"- **Data Flows Identified:** {flow_count}")
        lines.append(f"- **Diagrams Generated:** {diagram_count}")

        if boundaries:
            avg_confidence = sum(b.confidence for b in boundaries) / len(boundaries)
            lines.append(f"- **Average Confidence:** {avg_confidence:.1%}")

        # Use LLM for enhanced summary if available
        if self.llm and boundaries:
            try:
                enhanced = await self._llm_enhance_summary(repository_id, boundaries)
                if enhanced:
                    lines.append("")
                    lines.append("### Analysis Overview")
                    lines.append("")
                    lines.append(enhanced)
            except LLMGenerationError as e:
                logger.warning(f"LLM enhancement failed: {e}")

        confidence = 0.7
        if boundaries:
            confidence = sum(b.confidence for b in boundaries) / len(boundaries)

        return ReportSection(
            title="Overview",
            content="\n".join(lines),
            confidence=confidence,
            source_entities=[b.boundary_id for b in (boundaries or [])[:5]],
        )

    def _generate_service_inventory(
        self, boundaries: list[ServiceBoundary]
    ) -> ReportSection:
        """Generate service inventory section."""
        lines = ["The following services were detected through code analysis:", ""]

        for boundary in sorted(boundaries, key=lambda b: -b.confidence):
            # Entry points list
            entry_list = ""
            if boundary.entry_points:
                entry_items = [f"- `{ep}`" for ep in boundary.entry_points[:5]]
                entry_list = "\n".join(entry_items)
            else:
                entry_list = "- No public entry points detected"

            section = self.SECTION_TEMPLATES["service_inventory"].format(
                service_name=boundary.name,
                confidence=boundary.confidence,
                confidence_level=boundary.confidence_level.value,
                description=boundary.description,
                component_count=len(boundary.node_ids),
                internal_edges=boundary.edges_internal,
                external_edges=boundary.edges_external,
                modularity=boundary.modularity_ratio,
                entry_points=entry_list,
            )
            lines.append(section)

        avg_confidence = sum(b.confidence for b in boundaries) / len(boundaries)

        return ReportSection(
            title="Service Inventory",
            content="\n".join(lines),
            confidence=avg_confidence,
            source_entities=[b.boundary_id for b in boundaries],
        )

    def _generate_data_flow_analysis(self, data_flows: list[DataFlow]) -> ReportSection:
        """Generate data flow analysis section."""
        lines = [
            "The following data flows were identified between components:",
            "",
        ]

        # Group by classification
        by_classification: dict[str, list[DataFlow]] = {}
        for flow in data_flows:
            key = flow.classification.value
            if key not in by_classification:
                by_classification[key] = []
            by_classification[key].append(flow)

        # Order by sensitivity
        classification_order = [
            "pii",
            "sensitive",
            "confidential",
            "internal",
            "public",
        ]

        for classification in classification_order:
            if classification not in by_classification:
                continue

            flows = by_classification[classification]
            lines.append(f"### {classification.upper()} Data Flows")
            lines.append("")

            for flow in flows[:10]:  # Limit per category
                section = self.SECTION_TEMPLATES["data_flow"].format(
                    flow_name=f"{flow.source_id} → {flow.target_id}",
                    source=flow.source_id,
                    target=flow.target_id,
                    flow_type=flow.flow_type,
                    protocol=flow.protocol,
                    classification=flow.classification.value,
                    confidence=flow.confidence,
                )
                lines.append(section)

        avg_confidence = (
            sum(f.confidence for f in data_flows) / len(data_flows)
            if data_flows
            else 0.5
        )

        return ReportSection(
            title="Data Flow Analysis",
            content="\n".join(lines),
            confidence=avg_confidence,
            source_entities=[f.flow_id for f in data_flows[:10]],
        )

    def _generate_security_considerations(
        self,
        boundaries: list[ServiceBoundary] | None,
        data_flows: list[DataFlow] | None,
    ) -> ReportSection:
        """Generate security considerations section."""
        lines = [
            "Based on the code analysis, the following security considerations "
            "have been identified:",
            "",
        ]

        considerations: list[tuple[str, str, float]] = []  # (title, desc, severity)

        # Check for sensitive data flows
        if data_flows:
            sensitive_flows = [
                f
                for f in data_flows
                if f.classification.value in ("pii", "sensitive", "confidential")
            ]
            if sensitive_flows:
                considerations.append(
                    (
                        "Sensitive Data in Transit",
                        f"Detected {len(sensitive_flows)} data flows involving "
                        f"sensitive or PII data. Ensure encryption in transit (TLS) "
                        f"and appropriate access controls.",
                        0.8,
                    )
                )

        # Check for external service connections
        if boundaries:
            total_external = sum(b.edges_external for b in boundaries)
            if total_external > 10:
                considerations.append(
                    (
                        "External Dependencies",
                        f"The system has {total_external} external connections. "
                        f"Consider implementing circuit breakers and retry logic "
                        f"for resilience.",
                        0.6,
                    )
                )

            # Check for services with low modularity
            low_modularity = [b for b in boundaries if b.modularity_ratio < 0.5]
            if low_modularity:
                considerations.append(
                    (
                        "Tightly Coupled Services",
                        f"{len(low_modularity)} services have high external coupling. "
                        f"Consider refactoring to improve isolation and reduce "
                        f"blast radius.",
                        0.5,
                    )
                )

        # Default considerations
        considerations.append(
            (
                "Input Validation",
                "Ensure all entry points validate and sanitize input data "
                "to prevent injection attacks.",
                0.7,
            )
        )

        considerations.append(
            (
                "Authentication & Authorization",
                "Verify that all service-to-service communication uses "
                "appropriate authentication (mTLS, JWT, IAM roles).",
                0.7,
            )
        )

        # Format considerations
        for title, desc, severity in sorted(considerations, key=lambda x: -x[2]):
            severity_label = (
                "HIGH" if severity >= 0.7 else "MEDIUM" if severity >= 0.5 else "LOW"
            )
            lines.append(f"### {title}")
            lines.append("")
            lines.append(f"**Priority:** {severity_label}")
            lines.append("")
            lines.append(desc)
            lines.append("")

        return ReportSection(
            title="Security Considerations",
            content="\n".join(lines),
            confidence=0.7,
            metadata={"consideration_count": len(considerations)},
        )

    def _generate_recommendations(
        self,
        boundaries: list[ServiceBoundary] | None,
        data_flows: list[DataFlow] | None,
        diagrams: list[DiagramResult] | None,
    ) -> ReportSection:
        """Generate recommendations section."""
        lines = [
            "Based on the analysis, the following recommendations are suggested:",
            "",
        ]

        recommendations: list[tuple[str, str]] = []

        # Low confidence areas
        if boundaries:
            low_confidence = [b for b in boundaries if b.confidence < 0.6]
            if low_confidence:
                recommendations.append(
                    (
                        "Improve Service Documentation",
                        f"{len(low_confidence)} services have low detection confidence. "
                        f"Adding explicit module boundaries, README files, or architecture "
                        f"annotations would improve automated documentation accuracy.",
                    )
                )

        # Missing diagrams
        if diagrams:
            diagram_types = {d.diagram_type.value for d in diagrams}
            missing = {"architecture", "data_flow", "sequence"} - diagram_types
            if missing:
                recommendations.append(
                    (
                        "Generate Additional Diagrams",
                        f"Consider generating {', '.join(missing)} diagrams "
                        f"for more complete documentation coverage.",
                    )
                )

        # Data flow recommendations
        if data_flows:
            undocumented_protocols = [f for f in data_flows if f.protocol == "unknown"]
            if undocumented_protocols:
                recommendations.append(
                    (
                        "Document Communication Protocols",
                        f"{len(undocumented_protocols)} data flows have unknown protocols. "
                        f"Adding OpenAPI specs or explicit protocol definitions would "
                        f"improve documentation quality.",
                    )
                )

        # Default recommendation
        recommendations.append(
            (
                "Regular Documentation Updates",
                "Re-run documentation generation after significant code changes "
                "to keep documentation in sync with the codebase.",
            )
        )

        # Format recommendations
        for i, (title, desc) in enumerate(recommendations, 1):
            lines.append(f"### {i}. {title}")
            lines.append("")
            lines.append(desc)
            lines.append("")

        return ReportSection(
            title="Recommendations",
            content="\n".join(lines),
            confidence=0.8,
            metadata={"recommendation_count": len(recommendations)},
        )

    def _build_executive_summary_text(
        self,
        repository_id: str,
        boundaries: list[ServiceBoundary] | None,
        data_flows: list[DataFlow] | None,
        diagrams: list[DiagramResult] | None,
        overall_confidence: float,
    ) -> str:
        """Build the executive summary text."""
        service_count = len(boundaries) if boundaries else 0
        flow_count = len(data_flows) if data_flows else 0
        confidence_level = ConfidenceLevel.from_score(overall_confidence)

        summary = (
            f"This automated technical documentation analyzes the {repository_id} "
            f"repository. The analysis identified {service_count} service "
            f"boundaries and {flow_count} data flows. "
            f"Overall documentation confidence is {overall_confidence:.0%} "
            f"({confidence_level.value}). "
        )

        if overall_confidence < 0.65:
            summary += (
                "Due to lower confidence scores, manual review is recommended "
                "before relying on this documentation for critical decisions."
            )
        elif overall_confidence >= 0.85:
            summary += (
                "High confidence scores suggest this documentation accurately "
                "represents the system architecture."
            )
        else:
            summary += "Some sections may benefit from manual verification."

        return summary

    async def _llm_enhance_summary(
        self,
        repository_id: str,
        boundaries: list[ServiceBoundary],
    ) -> str | None:
        """Use LLM to enhance the executive summary."""
        if not self.llm:
            return None

        try:
            service_names = [b.name for b in boundaries[:10]]
            prompt = (
                f"Given a codebase with these detected services: {', '.join(service_names)}, "
                f"write a 2-3 sentence high-level description of what this system likely does. "
                f"Be concise and technical."
            )

            response = await self.llm.generate(
                prompt=prompt,
                agent="ReportGenerator",
                max_tokens=150,
                temperature=0.3,
            )
            return response.strip()

        except Exception as e:
            logger.warning(f"LLM enhancement failed: {e}")
            return None


# Factory function
def create_report_generator(
    llm_client: "BedrockLLMService | None" = None,
) -> ReportGenerator:
    """
    Factory function to create a ReportGenerator.

    Args:
        llm_client: Optional LLM for enhanced descriptions

    Returns:
        Configured ReportGenerator instance
    """
    return ReportGenerator(llm_client=llm_client)
