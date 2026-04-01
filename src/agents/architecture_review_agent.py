"""Architecture Review Agent for Autonomous ADR Generation Pipeline.

This agent detects ADR-worthy decisions by analyzing recommendations,
identifying pattern deviations, and evaluating architectural significance.

Part of ADR-010: Autonomous ADR Generation Pipeline

Integrates with BedrockLLMService for production LLM calls.
Updated: 2025-12-01 (Bedrock integration)
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .adaptive_intelligence_agent import (
    AdaptiveRecommendation,
    EffortLevel,
    RecommendationType,
    RiskLevel,
)
from .monitoring_service import AgentRole, MonitorAgent
from .threat_intelligence_agent import ThreatSeverity

if TYPE_CHECKING:
    from src.services.bedrock_llm_service import BedrockLLMService

logger = logging.getLogger(__name__)


class ADRSignificance(Enum):
    """Significance levels for ADR triggers."""

    CRITICAL = "critical"  # Immediate HITL required
    HIGH = "high"  # HITL required
    MEDIUM = "medium"  # Auto-approve with notification
    LOW = "low"  # Auto-approve, log only
    INFORMATIONAL = "informational"  # No ADR needed, document in changelog


class ADRCategory(Enum):
    """Categories of architecture decisions."""

    SECURITY = "security"
    INFRASTRUCTURE = "infrastructure"
    DEPENDENCY = "dependency"
    CONFIGURATION = "configuration"
    COMPLIANCE = "compliance"
    OPTIMIZATION = "optimization"
    INTEGRATION = "integration"


@dataclass
class ADRTriggerEvent:
    """Event triggering ADR generation."""

    id: str
    title: str
    category: ADRCategory
    significance: ADRSignificance
    description: str
    context_summary: str
    affected_components: list[str] = field(default_factory=list)
    source_recommendation: AdaptiveRecommendation | None = None
    existing_adr_references: list[str] = field(default_factory=list)
    pattern_deviations: list[str] = field(default_factory=list)
    requires_hitl: bool = True
    auto_approve_reason: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert trigger event to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category.value,
            "significance": self.significance.value,
            "description": self.description,
            "context_summary": self.context_summary,
            "affected_components": self.affected_components,
            "source_recommendation_id": (
                self.source_recommendation.id if self.source_recommendation else None
            ),
            "existing_adr_references": self.existing_adr_references,
            "pattern_deviations": self.pattern_deviations,
            "requires_hitl": self.requires_hitl,
            "auto_approve_reason": self.auto_approve_reason,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ArchitecturePattern:
    """Documented architecture pattern from existing ADRs."""

    adr_id: str
    pattern_name: str
    description: str
    keywords: list[str] = field(default_factory=list)
    components: list[str] = field(default_factory=list)


class ArchitectureReviewAgent:
    """Agent for ADR trigger detection and pattern analysis.

    Analyzes recommendations from AdaptiveIntelligenceAgent to:
    - Detect ADR-worthy decisions
    - Identify pattern deviations from existing ADRs
    - Evaluate architectural significance
    - Determine HITL requirements

    Produces ADRTriggerEvent objects for downstream processing
    by ADRGeneratorAgent.
    """

    def __init__(
        self,
        llm_client: "BedrockLLMService | None" = None,
        adr_directory: str | Path = "docs/architecture-decisions",
        monitor: MonitorAgent | None = None,
    ):
        """Initialize the Architecture Review Agent.

        Args:
            llm_client: LLM client for intelligent analysis (BedrockLLMService).
            adr_directory: Path to ADR directory for pattern extraction.
            monitor: Optional monitoring agent for metrics/logging.
        """
        self.llm = llm_client
        self.adr_directory = Path(adr_directory)
        self.monitor = monitor
        self._architecture_patterns = self._load_architecture_patterns()
        self._adr_index = self._load_adr_index()
        logger.info("Initialized ArchitectureReviewAgent")

    def evaluate_recommendations(
        self, recommendations: list[AdaptiveRecommendation]
    ) -> list[ADRTriggerEvent]:
        """Evaluate recommendations for ADR-worthiness.

        Args:
            recommendations: List of recommendations to evaluate.

        Returns:
            List of ADR trigger events for worthy recommendations.
        """
        self._log_activity(f"Evaluating {len(recommendations)} recommendations")

        trigger_events = []
        for recommendation in recommendations:
            # Check if recommendation warrants ADR
            if self._is_adr_worthy(recommendation):
                trigger = self._create_trigger_event(recommendation)
                trigger_events.append(trigger)
            else:
                self._log_activity(
                    f"Skipping non-ADR-worthy recommendation: {recommendation.title}"
                )

        self._log_activity(f"Generated {len(trigger_events)} ADR trigger events")

        return trigger_events

    def _is_adr_worthy(self, recommendation: AdaptiveRecommendation) -> bool:
        """Determine if recommendation warrants ADR creation.

        Criteria for ADR-worthiness:
        1. Security remediation with Critical/High severity
        2. Infrastructure changes
        3. Significant architectural impact
        4. Compliance-related changes
        5. Pattern deviation from existing ADRs
        6. New technology or service integration

        Args:
            recommendation: Recommendation to evaluate.

        Returns:
            True if ADR should be created.
        """
        # Security remediations with Critical/High severity
        if recommendation.severity in [ThreatSeverity.CRITICAL, ThreatSeverity.HIGH]:
            return True

        # Architecture changes always warrant ADR
        if recommendation.recommendation_type == RecommendationType.ARCHITECTURE_CHANGE:
            return True

        # Compliance updates always warrant ADR
        if recommendation.recommendation_type == RecommendationType.COMPLIANCE_UPDATE:
            return True

        # Large/Major effort changes warrant ADR
        if recommendation.effort_level in [EffortLevel.LARGE, EffortLevel.MAJOR]:
            return True

        # High risk changes warrant ADR
        if recommendation.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            return True

        # Pattern deviations warrant ADR
        if self._check_pattern_deviation(recommendation):
            return True

        # Infrastructure configuration changes
        if self._affects_infrastructure(recommendation):
            return True

        return False

    def _create_trigger_event(
        self, recommendation: AdaptiveRecommendation
    ) -> ADRTriggerEvent:
        """Create ADR trigger event from recommendation.

        Args:
            recommendation: Source recommendation.

        Returns:
            ADR trigger event.
        """
        # Determine category
        category = self._determine_category(recommendation)

        # Determine significance
        significance = self._determine_significance(recommendation)

        # Find related existing ADRs
        related_adrs = self._find_related_adrs(recommendation)

        # Check for pattern deviations
        pattern_deviations = self._identify_pattern_deviations(recommendation)

        # Determine HITL requirement
        requires_hitl = significance in [
            ADRSignificance.CRITICAL,
            ADRSignificance.HIGH,
        ]

        # Generate context summary
        context_summary = self._generate_context_summary(recommendation)

        # Auto-approve reason for lower significance
        auto_approve_reason = ""
        if not requires_hitl:
            auto_approve_reason = self._generate_auto_approve_reason(
                recommendation, significance
            )

        trigger = ADRTriggerEvent(
            id=f"ADR-TRIG-{recommendation.id}",
            title=self._generate_adr_title(recommendation, category),
            category=category,
            significance=significance,
            description=recommendation.description,
            context_summary=context_summary,
            affected_components=recommendation.affected_components,
            source_recommendation=recommendation,
            existing_adr_references=related_adrs,
            pattern_deviations=pattern_deviations,
            requires_hitl=requires_hitl,
            auto_approve_reason=auto_approve_reason,
        )

        return trigger

    def _determine_category(
        self, recommendation: AdaptiveRecommendation
    ) -> ADRCategory:
        """Determine ADR category from recommendation.

        Args:
            recommendation: Source recommendation.

        Returns:
            ADR category.
        """
        type_mapping = {
            RecommendationType.SECURITY_PATCH: ADRCategory.SECURITY,
            RecommendationType.DEPENDENCY_UPGRADE: ADRCategory.DEPENDENCY,
            RecommendationType.CONFIGURATION_CHANGE: ADRCategory.CONFIGURATION,
            RecommendationType.ARCHITECTURE_CHANGE: ADRCategory.INFRASTRUCTURE,
            RecommendationType.COMPLIANCE_UPDATE: ADRCategory.COMPLIANCE,
            RecommendationType.BEST_PRACTICE: ADRCategory.OPTIMIZATION,
        }

        return type_mapping.get(
            recommendation.recommendation_type, ADRCategory.SECURITY
        )

    def _determine_significance(
        self, recommendation: AdaptiveRecommendation
    ) -> ADRSignificance:
        """Determine ADR significance from recommendation.

        Args:
            recommendation: Source recommendation.

        Returns:
            ADR significance level.
        """
        # Critical severity = Critical significance
        if recommendation.severity == ThreatSeverity.CRITICAL:
            return ADRSignificance.CRITICAL

        # High severity or risk = High significance
        if (
            recommendation.severity == ThreatSeverity.HIGH
            or recommendation.risk_level == RiskLevel.CRITICAL
        ):
            return ADRSignificance.HIGH

        # Medium severity with large effort = Medium significance
        if (
            recommendation.severity == ThreatSeverity.MEDIUM
            or recommendation.effort_level in [EffortLevel.LARGE, EffortLevel.MAJOR]
        ):
            return ADRSignificance.MEDIUM

        # Low severity = Low significance
        if recommendation.severity == ThreatSeverity.LOW:
            return ADRSignificance.LOW

        return ADRSignificance.INFORMATIONAL

    def _find_related_adrs(self, recommendation: AdaptiveRecommendation) -> list[str]:
        """Find existing ADRs related to the recommendation.

        Args:
            recommendation: Source recommendation.

        Returns:
            List of related ADR identifiers.
        """
        related = []

        # Check for keyword matches in existing ADRs
        keywords = self._extract_keywords(recommendation)

        for adr_id, adr_info in self._adr_index.items():
            adr_keywords = adr_info.get("keywords", [])
            if set(keywords) & set(adr_keywords):
                related.append(adr_id)

        # Check for component overlap
        for adr_id, adr_info in self._adr_index.items():
            adr_components = adr_info.get("components", [])
            if set(recommendation.affected_components) & set(adr_components):
                if adr_id not in related:
                    related.append(adr_id)

        return related

    def _identify_pattern_deviations(
        self, recommendation: AdaptiveRecommendation
    ) -> list[str]:
        """Identify deviations from established architecture patterns.

        Args:
            recommendation: Source recommendation.

        Returns:
            List of pattern deviation descriptions.
        """
        deviations = []

        for pattern in self._architecture_patterns:
            # Check if recommendation affects pattern components
            component_overlap = set(recommendation.affected_components) & set(
                pattern.components
            )

            if component_overlap:
                # Check if recommendation aligns with pattern
                if not self._aligns_with_pattern(recommendation, pattern):
                    deviations.append(
                        f"Deviates from {pattern.adr_id}: {pattern.pattern_name}"
                    )

        return deviations

    def _aligns_with_pattern(
        self,
        recommendation: AdaptiveRecommendation,
        pattern: ArchitecturePattern,
    ) -> bool:
        """Check if recommendation aligns with architecture pattern.

        Args:
            recommendation: Source recommendation.
            pattern: Architecture pattern to check.

        Returns:
            True if recommendation aligns with pattern.
        """
        # Simple keyword matching - in production, use more sophisticated analysis
        rec_text = (
            recommendation.description.lower()
            + " "
            + " ".join(recommendation.implementation_steps).lower()
        )

        # Check if recommendation mentions pattern keywords
        keyword_matches = sum(1 for kw in pattern.keywords if kw.lower() in rec_text)

        # Aligned if matches majority of keywords
        return keyword_matches >= len(pattern.keywords) / 2

    def _check_pattern_deviation(self, recommendation: AdaptiveRecommendation) -> bool:
        """Check if recommendation deviates from any pattern.

        Args:
            recommendation: Source recommendation.

        Returns:
            True if pattern deviation detected.
        """
        deviations = self._identify_pattern_deviations(recommendation)
        return len(deviations) > 0

    def _affects_infrastructure(self, recommendation: AdaptiveRecommendation) -> bool:
        """Check if recommendation affects infrastructure.

        Args:
            recommendation: Source recommendation.

        Returns:
            True if infrastructure is affected.
        """
        infra_patterns = [
            r"cloudformation",
            r"terraform",
            r"kubernetes",
            r"eks",
            r"vpc",
            r"iam",
            r"security.?group",
            r"load.?balancer",
            r"database",
            r"neptune",
            r"opensearch",
        ]

        text_to_check = (
            recommendation.description.lower()
            + " "
            + " ".join(recommendation.affected_files).lower()
        )

        return any(re.search(pattern, text_to_check) for pattern in infra_patterns)

    def _generate_adr_title(
        self,
        recommendation: AdaptiveRecommendation,
        category: ADRCategory,
    ) -> str:
        """Generate ADR title from recommendation.

        Args:
            recommendation: Source recommendation.
            category: ADR category.

        Returns:
            ADR title.
        """
        # Extract core subject from recommendation title
        title: str = recommendation.title

        # Remove common prefixes
        prefixes_to_remove = ["Remediate:", "Update:", "Fix:", "Patch:"]
        for prefix in prefixes_to_remove:
            if title.startswith(prefix):
                title = title[len(prefix) :].strip()

        # Add category context if not obvious
        category_prefixes: dict[ADRCategory, str] = {
            ADRCategory.SECURITY: "Security Remediation:",
            ADRCategory.INFRASTRUCTURE: "Infrastructure Update:",
            ADRCategory.COMPLIANCE: "Compliance Update:",
            ADRCategory.DEPENDENCY: "Dependency Update:",
        }

        if category in category_prefixes:
            return f"{category_prefixes[category]} {title}"

        return title

    def _generate_context_summary(self, recommendation: AdaptiveRecommendation) -> str:
        """Generate context summary for ADR.

        Args:
            recommendation: Source recommendation.

        Returns:
            Context summary text.
        """
        parts = []

        # Add threat context if available
        if recommendation.source_threat:
            threat = recommendation.source_threat
            parts.append(f"Triggered by {threat.source} intelligence: {threat.title}")
            if threat.cve_ids:
                parts.append(f"CVEs: {', '.join(threat.cve_ids)}")

        # Add risk context
        parts.append(
            f"Risk assessment: {recommendation.risk_level.value} "
            f"(score: {recommendation.risk_score}/10)"
        )

        # Add effort context
        parts.append(f"Implementation effort: {recommendation.effort_level.value}")

        # Add affected components
        if recommendation.affected_components:
            parts.append(
                f"Affected components: {', '.join(recommendation.affected_components)}"
            )

        # Add compliance context
        if recommendation.compliance_impact:
            parts.append(
                f"Compliance impact: {', '.join(recommendation.compliance_impact[:3])}"
            )

        return ". ".join(parts) + "."

    def _generate_auto_approve_reason(
        self,
        recommendation: AdaptiveRecommendation,
        significance: ADRSignificance,
    ) -> str:
        """Generate reason for auto-approval.

        Args:
            recommendation: Source recommendation.
            significance: ADR significance level.

        Returns:
            Auto-approve reason text.
        """
        if significance == ADRSignificance.MEDIUM:
            return (
                "Medium significance with validated sandbox testing. "
                "Auto-approved with notification to team."
            )
        elif significance == ADRSignificance.LOW:
            return (
                "Low significance, minimal risk change. "
                "Auto-approved, logged for audit trail."
            )
        elif significance == ADRSignificance.INFORMATIONAL:
            return (
                "Informational only, no architectural impact. "
                "Documented in changelog, no ADR required."
            )

        return ""

    def _extract_keywords(self, recommendation: AdaptiveRecommendation) -> list[str]:
        """Extract keywords from recommendation.

        Args:
            recommendation: Source recommendation.

        Returns:
            List of keywords.
        """
        # Combine text sources
        text = (
            recommendation.title
            + " "
            + recommendation.description
            + " "
            + " ".join(recommendation.affected_components)
        )

        # Extract significant words
        words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())

        # Filter to likely keywords
        stop_words = {
            "this",
            "that",
            "with",
            "from",
            "have",
            "been",
            "will",
            "would",
            "could",
            "should",
            "must",
            "into",
            "also",
            "when",
            "than",
            "then",
            "some",
            "such",
            "more",
            "most",
            "only",
        }

        keywords = [w for w in words if w not in stop_words]

        # Return unique keywords
        return list(set(keywords))[:10]

    def _load_architecture_patterns(self) -> list[ArchitecturePattern]:
        """Load architecture patterns from existing ADRs.

        Returns:
            List of architecture patterns.
        """
        # In production, parse actual ADR files
        # Mock implementation with known patterns
        return [
            ArchitecturePattern(
                adr_id="ADR-002",
                pattern_name="VPC Endpoints over NAT Gateways",
                description="Use VPC endpoints for AWS service access",
                keywords=["vpc", "endpoint", "nat", "gateway", "private"],
                components=["networking", "vpc", "security-groups"],
            ),
            ArchitecturePattern(
                adr_id="ADR-003",
                pattern_name="EKS EC2 Managed Node Groups",
                description="Use EC2 node groups for GovCloud compatibility",
                keywords=["eks", "ec2", "fargate", "node", "kubernetes"],
                components=["eks", "compute", "kubernetes"],
            ),
            ArchitecturePattern(
                adr_id="ADR-007",
                pattern_name="Modular CI/CD with Layer-Based Deployment",
                description="Deploy infrastructure in layers with change detection",
                keywords=["cicd", "codebuild", "layer", "deployment", "modular"],
                components=["codebuild", "deployment", "infrastructure"],
            ),
            ArchitecturePattern(
                adr_id="ADR-008",
                pattern_name="Bedrock LLM Cost Controls",
                description="Multi-layer cost controls for LLM usage",
                keywords=["bedrock", "llm", "cost", "budget", "token"],
                components=["bedrock", "llm", "monitoring"],
            ),
            ArchitecturePattern(
                adr_id="ADR-009",
                pattern_name="Dual-Layer Drift Protection",
                description="CloudFormation drift + AWS Config for compliance",
                keywords=["drift", "config", "compliance", "cloudformation"],
                components=["cloudformation", "config", "monitoring"],
            ),
        ]

    def _load_adr_index(self) -> dict[str, dict[str, Any]]:
        """Load ADR index for reference.

        Returns:
            Dictionary mapping ADR IDs to metadata.
        """
        # In production, parse ADR directory
        # Mock implementation with known ADRs
        return {
            "ADR-001": {
                "title": "Separate DynamoDB Tables for Job Types",
                "keywords": ["dynamodb", "tables", "jobs", "separation"],
                "components": ["dynamodb", "data"],
            },
            "ADR-002": {
                "title": "VPC Endpoints over NAT Gateways",
                "keywords": ["vpc", "endpoints", "nat", "networking"],
                "components": ["networking", "vpc"],
            },
            "ADR-003": {
                "title": "EKS EC2 Managed Node Groups for GovCloud",
                "keywords": ["eks", "ec2", "govcloud", "kubernetes"],
                "components": ["eks", "compute"],
            },
            "ADR-005": {
                "title": "HITL Sandbox Testing",
                "keywords": ["hitl", "sandbox", "testing", "approval"],
                "components": ["sandbox", "testing"],
            },
            "ADR-007": {
                "title": "Modular CI/CD with Layer-Based Deployment",
                "keywords": ["cicd", "modular", "layers", "codebuild"],
                "components": ["codebuild", "deployment"],
            },
            "ADR-008": {
                "title": "Bedrock LLM Cost Controls",
                "keywords": ["bedrock", "llm", "cost", "budget"],
                "components": ["bedrock", "monitoring"],
            },
            "ADR-009": {
                "title": "Dual-Layer Drift Protection",
                "keywords": ["drift", "compliance", "config"],
                "components": ["cloudformation", "config"],
            },
            "ADR-010": {
                "title": "Autonomous ADR Generation Pipeline",
                "keywords": ["adr", "autonomous", "pipeline", "agents"],
                "components": ["agents", "documentation"],
            },
        }

    def _log_activity(self, message: str) -> None:
        """Log agent activity.

        Args:
            message: Log message.
        """
        print(f"[{AgentRole.REVIEWER.value}:ArchReview] {message}")

        if self.monitor:
            self.monitor.log_activity(
                role=AgentRole.REVIEWER,
                activity=f"ArchitectureReview: {message}",
            )


def create_architecture_review_agent(
    use_mock: bool = False,
    adr_directory: str | Path = "docs/architecture-decisions",
    monitor: MonitorAgent | None = None,
) -> "ArchitectureReviewAgent":
    """Factory function to create an ArchitectureReviewAgent.

    Args:
        use_mock: If True, use a mock LLM for testing. If False, use real Bedrock.
        adr_directory: Directory containing ADR files.
        monitor: Optional monitor agent for logging.

    Returns:
        ArchitectureReviewAgent: Configured agent instance.
    """
    if use_mock:
        from unittest.mock import AsyncMock

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "compliance_issues": [],
                "recommendations": ["Consider documenting this pattern in an ADR"],
                "risk_assessment": "low",
                "related_adrs": [],
            }
        )
        logger.info("Created ArchitectureReviewAgent with mock LLM")
        return ArchitectureReviewAgent(
            llm_client=mock_llm,
            adr_directory=adr_directory,
            monitor=monitor,
        )
    else:
        from src.services.bedrock_llm_service import create_llm_service

        llm_service = create_llm_service()
        logger.info("Created ArchitectureReviewAgent with Bedrock LLM")
        return ArchitectureReviewAgent(
            llm_client=llm_service,
            adr_directory=adr_directory,
            monitor=monitor,
        )
