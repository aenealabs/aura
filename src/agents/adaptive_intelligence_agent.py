"""Adaptive Intelligence Agent for Autonomous ADR Generation Pipeline.

This agent analyzes threat intelligence reports, assesses codebase impact
using GraphRAG, and generates prioritized recommendations with risk scoring
and best practice alignment.

Part of ADR-010: Autonomous ADR Generation Pipeline

Integrates with BedrockLLMService for production LLM calls.
Updated: 2025-12-01 (Bedrock integration)
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, cast

from .monitoring_service import AgentRole, MonitorAgent
from .threat_intelligence_agent import ThreatIntelReport, ThreatSeverity

if TYPE_CHECKING:
    from src.services.bedrock_llm_service import BedrockLLMService

logger = logging.getLogger(__name__)


class RecommendationType(Enum):
    """Types of recommendations generated."""

    SECURITY_PATCH = "security_patch"
    DEPENDENCY_UPGRADE = "dependency_upgrade"
    CONFIGURATION_CHANGE = "configuration_change"
    ARCHITECTURE_CHANGE = "architecture_change"
    COMPLIANCE_UPDATE = "compliance_update"
    BEST_PRACTICE = "best_practice"


class EffortLevel(Enum):
    """Estimated implementation effort levels."""

    TRIVIAL = "trivial"  # < 1 hour
    SMALL = "small"  # 1-4 hours
    MEDIUM = "medium"  # 1-2 days
    LARGE = "large"  # 3-5 days
    MAJOR = "major"  # 1+ weeks


class RiskLevel(Enum):
    """Risk levels for implementing recommendations."""

    MINIMAL = "minimal"  # No breaking changes, well-tested
    LOW = "low"  # Minor changes, good test coverage
    MODERATE = "moderate"  # Some risk, requires validation
    HIGH = "high"  # Significant changes, extensive testing needed
    CRITICAL = "critical"  # Major architectural impact


@dataclass
class BestPractice:
    """Industry best practice recommendation."""

    id: str
    title: str
    description: str
    source: str  # NIST, OWASP, CIS, AWS Well-Architected, etc.
    compliance_frameworks: list[str] = field(default_factory=list)


@dataclass
class AdaptiveRecommendation:
    """Structured recommendation from adaptive analysis."""

    id: str
    title: str
    recommendation_type: RecommendationType
    severity: ThreatSeverity
    risk_score: float  # 0.0-10.0
    risk_level: RiskLevel
    effort_level: EffortLevel
    description: str
    rationale: str
    affected_components: list[str] = field(default_factory=list)
    affected_files: list[str] = field(default_factory=list)
    implementation_steps: list[str] = field(default_factory=list)
    best_practices: list[BestPractice] = field(default_factory=list)
    compliance_impact: list[str] = field(default_factory=list)
    rollback_plan: str = ""
    validation_criteria: list[str] = field(default_factory=list)
    source_threat: ThreatIntelReport | None = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert recommendation to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "recommendation_type": self.recommendation_type.value,
            "severity": self.severity.value,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level.value,
            "effort_level": self.effort_level.value,
            "description": self.description,
            "rationale": self.rationale,
            "affected_components": self.affected_components,
            "affected_files": self.affected_files,
            "implementation_steps": self.implementation_steps,
            "best_practices": [
                {"id": bp.id, "title": bp.title, "source": bp.source}
                for bp in self.best_practices
            ],
            "compliance_impact": self.compliance_impact,
            "rollback_plan": self.rollback_plan,
            "validation_criteria": self.validation_criteria,
            "source_threat_id": self.source_threat.id if self.source_threat else None,
            "created_at": self.created_at.isoformat(),
        }


class AdaptiveIntelligenceAgent:
    """Agent for risk analysis and recommendation generation.

    Analyzes threat intelligence reports from ThreatIntelligenceAgent,
    assesses codebase impact using GraphRAG context retrieval, and
    generates prioritized recommendations with:
    - Risk scoring
    - Best practice alignment
    - Implementation effort estimates
    - Compliance impact assessment

    Produces AdaptiveRecommendation objects for downstream processing
    by ArchitectureReviewAgent.
    """

    def __init__(
        self,
        llm_client: "BedrockLLMService | None" = None,
        context_service: Any | None = None,
        monitor: MonitorAgent | None = None,
    ):
        """Initialize the Adaptive Intelligence Agent.

        Args:
            llm_client: LLM client for intelligent generation (BedrockLLMService).
            context_service: GraphRAG context retrieval service for codebase analysis.
            monitor: Optional monitoring agent for metrics/logging.
        """
        self.llm = llm_client
        self.context_service = context_service
        self.monitor = monitor
        self._best_practices_db = self._load_best_practices()
        self._compliance_mappings = self._load_compliance_mappings()
        logger.info("Initialized AdaptiveIntelligenceAgent")

    async def analyze_threats(
        self, threat_reports: list[ThreatIntelReport]
    ) -> list[AdaptiveRecommendation]:
        """Analyze threat reports and generate recommendations.

        Uses LLM for intelligent recommendation generation when available.

        Args:
            threat_reports: List of threat intelligence reports to analyze.

        Returns:
            List of prioritized recommendations.
        """
        self._log_activity(f"Analyzing {len(threat_reports)} threat reports")

        recommendations = []
        for report in threat_reports:
            # Assess codebase impact
            impact_analysis = self._assess_codebase_impact(report)

            # Generate recommendation if action required
            if impact_analysis["requires_action"]:
                recommendation = await self._generate_recommendation(
                    report, impact_analysis
                )
                recommendations.append(recommendation)

        # Prioritize by risk and severity
        prioritized = self._prioritize_recommendations(recommendations)

        self._log_activity(
            f"Generated {len(prioritized)} recommendations from {len(threat_reports)} threats"
        )

        return prioritized

    def _assess_codebase_impact(self, report: ThreatIntelReport) -> dict[str, Any]:
        """Assess impact of threat on codebase using GraphRAG.

        Args:
            report: Threat report to assess.

        Returns:
            Impact analysis with affected files, components, and severity.
        """
        self._log_activity(f"Assessing codebase impact for: {report.title}")

        # In production, this would query GraphRAG for:
        # 1. Files importing affected dependencies
        # 2. Code paths using vulnerable patterns
        # 3. Infrastructure configurations affected
        # 4. Related components via graph traversal

        # Mock implementation demonstrating expected analysis
        affected_files = []
        affected_code_paths = []

        # Simulate GraphRAG query for dependency usage
        if report.affected_components:
            for component in report.affected_components:
                if "requests" in component.lower():
                    affected_files.extend(
                        [
                            "src/services/context_retrieval_service.py",
                            "src/agents/threat_intelligence_agent.py",
                        ]
                    )
                    affected_code_paths.append("HTTP client calls")
                elif "fastapi" in component.lower():
                    affected_files.extend(
                        [
                            "src/api/main.py",
                            "src/api/routes/",
                        ]
                    )
                    affected_code_paths.append("API endpoint definitions")
                elif "opensearch" in component.lower():
                    affected_files.extend(
                        [
                            "src/services/context_retrieval_service.py",
                            "deploy/cloudformation/opensearch.yaml",
                        ]
                    )
                    affected_code_paths.append("Vector search operations")

        # Determine if action is required
        requires_action = bool(affected_files) or report.severity in [
            ThreatSeverity.CRITICAL,
            ThreatSeverity.HIGH,
        ]

        return {
            "requires_action": requires_action,
            "affected_files": affected_files,
            "affected_code_paths": affected_code_paths,
            "direct_dependency_match": bool(report.affected_components),
            "infrastructure_impact": self._check_infrastructure_impact(report),
            "compliance_relevance": self._check_compliance_relevance(report),
        }

    async def _generate_recommendation(
        self,
        report: ThreatIntelReport,
        impact_analysis: dict[str, Any],
    ) -> AdaptiveRecommendation:
        """Generate recommendation from threat report and impact analysis.

        Uses LLM for intelligent generation of steps, rationale, and plans.

        Args:
            report: Source threat report.
            impact_analysis: Codebase impact analysis.

        Returns:
            Structured recommendation.
        """
        # Determine recommendation type
        rec_type = self._determine_recommendation_type(report)

        # Calculate risk score
        risk_score = self._calculate_risk_score(report, impact_analysis)

        # Determine effort level
        effort = self._estimate_effort(report, impact_analysis)

        # Find applicable best practices
        best_practices = self._find_best_practices(report)

        # Assess compliance impact
        compliance_impact = self._assess_compliance_impact(report)

        # Generate LLM-powered content (with fallback to hardcoded if no LLM)
        if self.llm:
            # Use LLM for intelligent generation
            try:
                implementation_steps = await self._generate_implementation_steps_llm(
                    report, rec_type, impact_analysis
                )
                validation_criteria = await self._generate_validation_criteria_llm(
                    rec_type, report
                )
                rollback_plan = await self._generate_rollback_plan_llm(
                    rec_type, impact_analysis, report
                )
                rationale = await self._generate_rationale_llm(report, impact_analysis)
            except Exception as e:
                logger.warning(f"LLM generation failed, using fallback: {e}")
                implementation_steps = self._generate_implementation_steps_fallback(
                    report, rec_type, impact_analysis
                )
                validation_criteria = self._generate_validation_criteria_fallback(
                    rec_type
                )
                rollback_plan = self._generate_rollback_plan_fallback(
                    rec_type, impact_analysis
                )
                rationale = self._generate_rationale_fallback(report, impact_analysis)
        else:
            # No LLM available, use fallback methods
            implementation_steps = self._generate_implementation_steps_fallback(
                report, rec_type, impact_analysis
            )
            validation_criteria = self._generate_validation_criteria_fallback(rec_type)
            rollback_plan = self._generate_rollback_plan_fallback(
                rec_type, impact_analysis
            )
            rationale = self._generate_rationale_fallback(report, impact_analysis)

        recommendation = AdaptiveRecommendation(
            id=f"REC-{report.id[:8]}",
            title=f"Remediate: {report.title}",
            recommendation_type=rec_type,
            severity=report.severity,
            risk_score=risk_score,
            risk_level=self._score_to_risk_level(risk_score),
            effort_level=effort,
            description=report.description,
            rationale=rationale,
            affected_components=report.affected_components,
            affected_files=impact_analysis.get("affected_files", []),
            implementation_steps=implementation_steps,
            best_practices=best_practices,
            compliance_impact=compliance_impact,
            rollback_plan=rollback_plan,
            validation_criteria=validation_criteria,
            source_threat=report,
        )

        return recommendation

    def _determine_recommendation_type(
        self, report: ThreatIntelReport
    ) -> RecommendationType:
        """Determine type of recommendation based on threat.

        Args:
            report: Threat report.

        Returns:
            Appropriate recommendation type.
        """
        if report.cve_ids:
            if report.affected_components:
                return RecommendationType.DEPENDENCY_UPGRADE
            return RecommendationType.SECURITY_PATCH

        if report.category.value == "compliance":
            return RecommendationType.COMPLIANCE_UPDATE

        if report.category.value == "internal":
            return RecommendationType.CONFIGURATION_CHANGE

        return RecommendationType.SECURITY_PATCH

    def _calculate_risk_score(
        self,
        report: ThreatIntelReport,
        impact_analysis: dict[str, Any],
    ) -> float:
        """Calculate composite risk score.

        Factors:
        - CVSS score (if available)
        - Severity level
        - Direct dependency match
        - Infrastructure impact
        - Compliance relevance
        - Active exploitation (CISA KEV)

        Args:
            report: Threat report.
            impact_analysis: Codebase impact analysis.

        Returns:
            Risk score from 0.0 to 10.0.
        """
        base_score = report.cvss_score or self._severity_to_base_score(report.severity)

        # Modifiers
        modifiers = 0.0

        # Direct dependency match increases risk
        if impact_analysis.get("direct_dependency_match"):
            modifiers += 1.0

        # Infrastructure impact increases risk
        if impact_analysis.get("infrastructure_impact"):
            modifiers += 0.5

        # Compliance relevance increases urgency
        if impact_analysis.get("compliance_relevance"):
            modifiers += 0.5

        # CISA KEV (actively exploited) significantly increases risk
        if report.source == "CISA KEV":
            modifiers += 2.0

        # Calculate final score (capped at 10.0)
        final_score = min(base_score + modifiers, 10.0)

        return round(final_score, 1)

    def _severity_to_base_score(self, severity: ThreatSeverity) -> float:
        """Convert severity to base risk score.

        Args:
            severity: Threat severity level.

        Returns:
            Base risk score.
        """
        mapping = {
            ThreatSeverity.CRITICAL: 9.0,
            ThreatSeverity.HIGH: 7.0,
            ThreatSeverity.MEDIUM: 5.0,
            ThreatSeverity.LOW: 3.0,
            ThreatSeverity.INFORMATIONAL: 1.0,
        }
        return mapping.get(severity, 5.0)

    def _score_to_risk_level(self, score: float) -> RiskLevel:
        """Convert risk score to risk level.

        Args:
            score: Risk score (0.0-10.0).

        Returns:
            Corresponding risk level.
        """
        if score >= 9.0:
            return RiskLevel.CRITICAL
        elif score >= 7.0:
            return RiskLevel.HIGH
        elif score >= 5.0:
            return RiskLevel.MODERATE
        elif score >= 3.0:
            return RiskLevel.LOW
        return RiskLevel.MINIMAL

    def _estimate_effort(
        self,
        report: ThreatIntelReport,
        impact_analysis: dict[str, Any],
    ) -> EffortLevel:
        """Estimate implementation effort.

        Args:
            report: Threat report.
            impact_analysis: Codebase impact analysis.

        Returns:
            Estimated effort level.
        """
        affected_files = impact_analysis.get("affected_files", [])
        file_count = len(affected_files)

        # Simple dependency upgrade
        if not affected_files and report.cve_ids:
            return EffortLevel.TRIVIAL

        # Few files affected
        if file_count <= 2:
            return EffortLevel.SMALL

        # Moderate scope
        if file_count <= 5:
            return EffortLevel.MEDIUM

        # Large scope
        if file_count <= 10:
            return EffortLevel.LARGE

        # Major undertaking
        return EffortLevel.MAJOR

    def _check_infrastructure_impact(self, report: ThreatIntelReport) -> bool:
        """Check if threat affects infrastructure.

        Args:
            report: Threat report.

        Returns:
            True if infrastructure is affected.
        """
        infra_keywords = [
            "kubernetes",
            "eks",
            "ec2",
            "vpc",
            "iam",
            "s3",
            "neptune",
            "opensearch",
            "cloudformation",
            "terraform",
        ]
        description_lower = report.description.lower()
        title_lower = report.title.lower()

        return any(
            keyword in description_lower or keyword in title_lower
            for keyword in infra_keywords
        )

    def _check_compliance_relevance(self, report: ThreatIntelReport) -> bool:
        """Check if threat has compliance implications.

        Args:
            report: Threat report.

        Returns:
            True if compliance-relevant.
        """
        # Critical/High severity typically has compliance implications
        if report.severity in [ThreatSeverity.CRITICAL, ThreatSeverity.HIGH]:
            return True

        # CISA advisories have compliance implications
        if report.source == "CISA KEV":
            return True

        # Check for compliance keywords
        compliance_keywords = [
            "cmmc",
            "nist",
            "fedramp",
            "sox",
            "hipaa",
            "encryption",
            "authentication",
            "authorization",
            "audit",
        ]
        description_lower = report.description.lower()

        return any(keyword in description_lower for keyword in compliance_keywords)

    def _find_best_practices(self, report: ThreatIntelReport) -> list[BestPractice]:
        """Find applicable best practices for the threat.

        Args:
            report: Threat report.

        Returns:
            List of relevant best practices.
        """
        applicable = []

        # Match based on threat category and description
        for bp in self._best_practices_db:
            if self._is_best_practice_applicable(bp, report):
                applicable.append(bp)

        return applicable[:3]  # Limit to top 3 most relevant

    def _is_best_practice_applicable(
        self, bp: BestPractice, report: ThreatIntelReport
    ) -> bool:
        """Check if best practice applies to threat.

        Args:
            bp: Best practice to check.
            report: Threat report.

        Returns:
            True if applicable.
        """
        # Simple keyword matching - in production, use semantic similarity
        bp_keywords = bp.title.lower().split() + bp.description.lower().split()
        report_keywords = (
            report.title.lower().split() + report.description.lower().split()
        )

        overlap = set(bp_keywords) & set(report_keywords)
        return len(overlap) >= 2

    def _assess_compliance_impact(self, report: ThreatIntelReport) -> list[str]:
        """Assess impact on compliance frameworks.

        Args:
            report: Threat report.

        Returns:
            List of affected compliance controls.
        """
        impacts = []

        if report.severity in [ThreatSeverity.CRITICAL, ThreatSeverity.HIGH]:
            impacts.append("CMMC AC.L2-3.1.1: Account Management")
            impacts.append("NIST 800-53 SI-2: Flaw Remediation")

        if "authentication" in report.description.lower():
            impacts.append("CMMC IA.L2-3.5.1: Identification")
            impacts.append("NIST 800-53 IA-2: Identification and Authentication")

        if "encryption" in report.description.lower():
            impacts.append("CMMC SC.L2-3.13.8: Cryptographic Protection")
            impacts.append("NIST 800-53 SC-13: Cryptographic Protection")

        return impacts

    async def _generate_implementation_steps_llm(
        self,
        report: ThreatIntelReport,
        rec_type: RecommendationType,
        impact_analysis: dict[str, Any],
    ) -> list[str]:
        """Generate implementation steps using LLM.

        Args:
            report: Threat report.
            rec_type: Recommendation type.
            impact_analysis: Codebase impact analysis.

        Returns:
            List of implementation steps.
        """
        if self.llm is None:
            return []
        prompt = self._build_implementation_steps_prompt(
            report, rec_type, impact_analysis
        )
        response = await self.llm.generate(prompt, agent="AdaptiveIntelligence")
        return self._parse_steps_response(response)

    def _build_implementation_steps_prompt(
        self,
        report: ThreatIntelReport,
        rec_type: RecommendationType,
        impact_analysis: dict[str, Any],
    ) -> str:
        """Build prompt for implementation steps generation."""
        affected_files = impact_analysis.get("affected_files", [])
        return f"""You are a security remediation expert. Generate specific implementation steps for addressing a security threat.

THREAT DETAILS:
- Title: {report.title}
- Description: {report.description}
- Severity: {report.severity.value}
- CVEs: {', '.join(report.cve_ids) if report.cve_ids else 'None'}
- Affected Components: {', '.join(report.affected_components) if report.affected_components else 'None'}

RECOMMENDATION TYPE: {rec_type.value}

AFFECTED FILES:
{chr(10).join(f'- {f}' for f in affected_files) if affected_files else '- No specific files identified'}

REQUIREMENTS:
- Generate 5-8 specific, actionable implementation steps
- Include sandbox testing before production deployment
- Include HITL (Human-in-the-Loop) approval step
- Consider rollback capability at each step
- Follow security best practices

RESPOND IN JSON FORMAT:
{{
  "steps": [
    "Step 1 description",
    "Step 2 description",
    ...
  ]
}}

Generate the implementation steps now:"""

    def _parse_steps_response(self, response: str) -> list[str]:
        """Parse LLM response for implementation steps."""
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                data = json.loads(response[json_start:json_end])
                return cast(list[str], data.get("steps", []))
        except Exception as e:
            logger.warning(f"Failed to parse steps response: {e}")
        return []

    def _generate_implementation_steps_fallback(
        self,
        report: ThreatIntelReport,
        rec_type: RecommendationType,
        impact_analysis: dict[str, Any],
    ) -> list[str]:
        """Generate implementation steps (fallback without LLM).

        Args:
            report: Threat report.
            rec_type: Recommendation type.
            impact_analysis: Codebase impact analysis.

        Returns:
            List of implementation steps.
        """
        steps = []

        if rec_type == RecommendationType.DEPENDENCY_UPGRADE:
            steps = [
                "Review CVE details and identify patched version",
                "Update dependency version in requirements.txt/pyproject.toml",
                "Run dependency resolution to check for conflicts",
                "Execute test suite to validate compatibility",
                "Deploy to sandbox environment for integration testing",
                "Submit for HITL approval",
                "Deploy to production with monitoring",
            ]
        elif rec_type == RecommendationType.SECURITY_PATCH:
            steps = [
                "Analyze vulnerability and affected code paths",
                "Develop security patch addressing the vulnerability",
                "Add regression tests for the vulnerability",
                "Run security scans (Bandit, Safety) on patched code",
                "Deploy to sandbox for validation",
                "Conduct security review",
                "Submit for HITL approval",
                "Deploy to production",
            ]
        elif rec_type == RecommendationType.CONFIGURATION_CHANGE:
            steps = [
                "Identify configuration changes required",
                "Update CloudFormation/Kubernetes manifests",
                "Validate templates with cfn-lint/kubeval",
                "Deploy to sandbox environment",
                "Verify configuration changes applied correctly",
                "Submit for HITL approval",
                "Deploy to production",
            ]
        else:
            steps = [
                "Analyze recommended changes",
                "Implement changes in development environment",
                "Test changes thoroughly",
                "Deploy to sandbox for validation",
                "Submit for HITL approval",
                "Deploy to production",
            ]

        return steps

    async def _generate_validation_criteria_llm(
        self,
        rec_type: RecommendationType,
        report: ThreatIntelReport,
    ) -> list[str]:
        """Generate validation criteria using LLM.

        Args:
            rec_type: Recommendation type.
            report: Threat report for context.

        Returns:
            List of validation criteria.
        """
        prompt = f"""You are a security validation expert. Generate specific validation criteria for a security remediation.

THREAT BEING REMEDIATED:
- Title: {report.title}
- Severity: {report.severity.value}
- CVEs: {', '.join(report.cve_ids) if report.cve_ids else 'None'}

RECOMMENDATION TYPE: {rec_type.value}

REQUIREMENTS:
- Generate 4-6 specific, measurable validation criteria
- Include security-specific checks
- Include regression testing requirements
- Consider compliance requirements (CMMC, NIST)

RESPOND IN JSON FORMAT:
{{
  "criteria": [
    "Criterion 1",
    "Criterion 2",
    ...
  ]
}}

Generate the validation criteria now:"""

        if self.llm is None:
            return []
        response = await self.llm.generate(prompt, agent="AdaptiveIntelligence")
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                data = json.loads(response[json_start:json_end])
                return cast(list[str], data.get("criteria", []))
        except Exception as e:
            logger.warning(f"Failed to parse validation criteria response: {e}")
        return []

    def _generate_validation_criteria_fallback(
        self, rec_type: RecommendationType
    ) -> list[str]:
        """Generate validation criteria (fallback without LLM).

        Args:
            rec_type: Recommendation type.

        Returns:
            List of validation criteria.
        """
        base_criteria = [
            "All existing tests pass",
            "No new security vulnerabilities introduced",
            "Performance within acceptable thresholds",
        ]

        if rec_type == RecommendationType.DEPENDENCY_UPGRADE:
            base_criteria.extend(
                [
                    "Dependency resolves without conflicts",
                    "No deprecated API usage warnings",
                ]
            )
        elif rec_type == RecommendationType.SECURITY_PATCH:
            base_criteria.extend(
                [
                    "Vulnerability no longer exploitable",
                    "Security scan shows no findings",
                ]
            )
        elif rec_type == RecommendationType.COMPLIANCE_UPDATE:
            base_criteria.extend(
                [
                    "Compliance checks pass",
                    "Audit trail properly recorded",
                ]
            )

        return base_criteria

    async def _generate_rollback_plan_llm(
        self,
        rec_type: RecommendationType,
        impact_analysis: dict[str, Any],
        report: ThreatIntelReport,
    ) -> str:
        """Generate rollback plan using LLM.

        Args:
            rec_type: Recommendation type.
            impact_analysis: Codebase impact analysis.
            report: Threat report for context.

        Returns:
            Rollback plan description.
        """
        affected_files = impact_analysis.get("affected_files", [])
        prompt = f"""You are a DevOps rollback planning expert. Generate a concise rollback plan for a security remediation.

REMEDIATION CONTEXT:
- Threat: {report.title}
- Type: {rec_type.value}
- Affected Files: {', '.join(affected_files) if affected_files else 'None identified'}

REQUIREMENTS:
- Describe specific rollback steps (1-3 sentences)
- Mention what artifacts/states are preserved
- Include any precautions needed

RESPOND IN JSON FORMAT:
{{
  "rollback_plan": "Concise rollback plan description..."
}}

Generate the rollback plan now:"""

        if self.llm is None:
            return ""
        response = await self.llm.generate(prompt, agent="AdaptiveIntelligence")
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                data = json.loads(response[json_start:json_end])
                return cast(str, data.get("rollback_plan", ""))
        except Exception as e:
            logger.warning(f"Failed to parse rollback plan response: {e}")
        return ""

    def _generate_rollback_plan_fallback(
        self,
        rec_type: RecommendationType,
        impact_analysis: dict[str, Any],
    ) -> str:
        """Generate rollback plan (fallback without LLM).

        Args:
            rec_type: Recommendation type.
            impact_analysis: Codebase impact analysis.

        Returns:
            Rollback plan description.
        """
        if rec_type == RecommendationType.DEPENDENCY_UPGRADE:
            return (
                "Revert dependency version in requirements.txt and redeploy. "
                "Previous version cached in pip cache."
            )
        elif rec_type == RecommendationType.CONFIGURATION_CHANGE:
            return (
                "Revert CloudFormation stack to previous version using "
                "aws cloudformation rollback-stack or restore from backup."
            )
        else:
            return (
                "Revert commit and redeploy previous version. "
                "Git history preserves all previous states."
            )

    async def _generate_rationale_llm(
        self,
        report: ThreatIntelReport,
        impact_analysis: dict[str, Any],
    ) -> str:
        """Generate rationale using LLM.

        Args:
            report: Threat report.
            impact_analysis: Codebase impact analysis.

        Returns:
            Rationale text.
        """
        affected_files = impact_analysis.get("affected_files", [])
        prompt = f"""You are a security analyst. Generate a concise rationale explaining why this security recommendation should be implemented.

THREAT DETAILS:
- Title: {report.title}
- Description: {report.description}
- Severity: {report.severity.value}
- CVSS Score: {report.cvss_score if report.cvss_score else 'Not available'}
- CVEs: {', '.join(report.cve_ids) if report.cve_ids else 'None'}
- Source: {report.source}

IMPACT ANALYSIS:
- Direct Dependency Match: {impact_analysis.get('direct_dependency_match', False)}
- Infrastructure Impact: {impact_analysis.get('infrastructure_impact', False)}
- Compliance Relevance: {impact_analysis.get('compliance_relevance', False)}
- Affected Files: {len(affected_files)} files

REQUIREMENTS:
- Generate a 2-4 sentence rationale
- Explain the business and security risk
- Reference compliance requirements if relevant (CMMC, NIST)
- Be specific about why action is needed

RESPOND IN JSON FORMAT:
{{
  "rationale": "Your rationale text here..."
}}

Generate the rationale now:"""

        if self.llm is None:
            return ""
        response = await self.llm.generate(prompt, agent="AdaptiveIntelligence")
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                data = json.loads(response[json_start:json_end])
                return cast(str, data.get("rationale", ""))
        except Exception as e:
            logger.warning(f"Failed to parse rationale response: {e}")
        return ""

    def _generate_rationale_fallback(
        self,
        report: ThreatIntelReport,
        impact_analysis: dict[str, Any],
    ) -> str:
        """Generate rationale (fallback without LLM).

        Args:
            report: Threat report.
            impact_analysis: Codebase impact analysis.

        Returns:
            Rationale text.
        """
        parts = []

        parts.append(f"Threat severity: {report.severity.value.upper()}")

        if report.cvss_score:
            parts.append(f"CVSS score: {report.cvss_score}")

        if report.source == "CISA KEV":
            parts.append("Actively exploited in the wild (CISA KEV)")

        if impact_analysis.get("direct_dependency_match"):
            parts.append("Directly affects project dependencies")

        if impact_analysis.get("compliance_relevance"):
            parts.append("Has compliance implications for CMMC/NIST")

        return ". ".join(parts) + "."

    def _prioritize_recommendations(
        self, recommendations: list[AdaptiveRecommendation]
    ) -> list[AdaptiveRecommendation]:
        """Prioritize recommendations by risk and severity.

        Args:
            recommendations: List of recommendations to prioritize.

        Returns:
            Sorted recommendations (highest priority first).
        """

        def priority_key(rec: AdaptiveRecommendation) -> tuple:
            return (
                -rec.risk_score,  # Higher score = higher priority
                rec.effort_level.value,  # Lower effort = prefer (for equal risk)
            )

        return sorted(recommendations, key=priority_key)

    def _load_best_practices(self) -> list[BestPractice]:
        """Load best practices database.

        Returns:
            List of best practices.
        """
        # In production, load from database or external source
        return [
            BestPractice(
                id="BP-001",
                title="Keep dependencies up to date",
                description="Regularly update dependencies to receive security patches",
                source="OWASP",
                compliance_frameworks=["CMMC", "NIST 800-53"],
            ),
            BestPractice(
                id="BP-002",
                title="Use parameterized queries",
                description="Prevent SQL injection by using parameterized queries",
                source="OWASP",
                compliance_frameworks=["CMMC", "PCI-DSS"],
            ),
            BestPractice(
                id="BP-003",
                title="Implement defense in depth",
                description="Use multiple security layers to protect against failures",
                source="NIST",
                compliance_frameworks=["CMMC", "NIST 800-53"],
            ),
            BestPractice(
                id="BP-004",
                title="Encrypt data at rest and in transit",
                description="Use strong encryption for sensitive data",
                source="AWS Well-Architected",
                compliance_frameworks=["CMMC", "HIPAA", "SOX"],
            ),
            BestPractice(
                id="BP-005",
                title="Implement least privilege access",
                description="Grant minimum necessary permissions",
                source="NIST",
                compliance_frameworks=["CMMC", "NIST 800-53", "SOX"],
            ),
        ]

    def _load_compliance_mappings(self) -> dict[str, list[str]]:
        """Load compliance control mappings.

        Returns:
            Mapping of keywords to compliance controls.
        """
        return {
            "authentication": [
                "CMMC IA.L2-3.5.1",
                "NIST IA-2",
            ],
            "encryption": [
                "CMMC SC.L2-3.13.8",
                "NIST SC-13",
            ],
            "logging": [
                "CMMC AU.L2-3.3.1",
                "NIST AU-2",
            ],
            "access_control": [
                "CMMC AC.L2-3.1.1",
                "NIST AC-2",
            ],
        }

    def _log_activity(self, message: str) -> None:
        """Log agent activity.

        Args:
            message: Log message.
        """
        print(f"[{AgentRole.PLANNER.value}:AdaptiveIntel] {message}")

        if self.monitor:
            self.monitor.log_activity(
                role=AgentRole.PLANNER,
                activity=f"AdaptiveIntelligence: {message}",
            )


# Factory function for production usage
def create_adaptive_intelligence_agent(
    use_mock: bool = False,
    context_service: Any | None = None,
    monitor: MonitorAgent | None = None,
) -> "AdaptiveIntelligenceAgent":
    """
    Create an AdaptiveIntelligenceAgent with real or mock LLM.

    Args:
        use_mock: If True, use mock LLM for testing. If False, use real Bedrock.
        context_service: Optional GraphRAG context retrieval service.
        monitor: Optional monitoring agent.

    Returns:
        Configured AdaptiveIntelligenceAgent instance
    """
    if use_mock:
        from unittest.mock import AsyncMock

        mock_llm = AsyncMock()
        # Configure mock responses for different generation methods
        mock_llm.generate.return_value = json.dumps(
            {
                "steps": [
                    "Review CVE details and patched versions",
                    "Update affected dependencies",
                    "Run test suite for compatibility",
                    "Deploy to sandbox environment",
                    "Submit for HITL approval",
                    "Deploy to production",
                ],
                "criteria": [
                    "All tests pass",
                    "No security vulnerabilities",
                    "Performance acceptable",
                ],
                "rollback_plan": "Revert to previous version and redeploy.",
                "rationale": "High severity vulnerability requires immediate attention.",
            }
        )
        logger.info("Created AdaptiveIntelligenceAgent with mock LLM")
        return AdaptiveIntelligenceAgent(
            llm_client=mock_llm,
            context_service=context_service,
            monitor=monitor,
        )
    else:
        from src.services.bedrock_llm_service import create_llm_service

        llm_service = create_llm_service()
        logger.info("Created AdaptiveIntelligenceAgent with real Bedrock LLM")
        return AdaptiveIntelligenceAgent(
            llm_client=llm_service,
            context_service=context_service,
            monitor=monitor,
        )


# Example usage
async def example_usage():
    """Example usage of AdaptiveIntelligenceAgent with real Bedrock."""
    import os

    # Use mock if AURA_LLM_MOCK is set, otherwise use real Bedrock
    use_mock = os.environ.get("AURA_LLM_MOCK", "false").lower() == "true"

    print(f"Using {'mock' if use_mock else 'real Bedrock'} LLM")

    # Create agent
    agent = create_adaptive_intelligence_agent(use_mock=use_mock)

    # Create a sample threat report for testing
    from .threat_intelligence_agent import ThreatCategory, ThreatIntelReport

    sample_threat = ThreatIntelReport(
        id="TEST-001",
        title="Sample CVE in requests library",
        description="A sample vulnerability for testing",
        severity=ThreatSeverity.HIGH,
        category=ThreatCategory.CVE,
        source="Test",
        published_date=datetime.now(),
        affected_components=["requests"],
        cve_ids=["CVE-2025-0001"],
    )

    # Analyze threats
    recommendations = await agent.analyze_threats([sample_threat])

    print(f"\nGenerated {len(recommendations)} recommendations:")
    for rec in recommendations:
        print(
            f"- {rec.title} (Risk: {rec.risk_score}, Effort: {rec.effort_level.value})"
        )
        print(f"  Rationale: {rec.rationale}")
        print(f"  Steps: {len(rec.implementation_steps)} implementation steps")


if __name__ == "__main__":
    import asyncio

    asyncio.run(example_usage())
