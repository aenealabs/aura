"""
Security Agent Orchestrator - AWS Security Agent Parity

Unified orchestration layer for all security agent capabilities:
- PR Security Scanning
- Dynamic Attack Planning
- Organization Standards Validation
- Integrated security workflow automation
- Cross-component correlation and analysis

Reference: ADR-030 Section 5.2 Security Agent Components
"""

import asyncio
import hashlib
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, cast

import structlog

from .dynamic_attack_planner import (
    Asset,
    AttackSimulation,
    AttackSurface,
    DynamicAttackPlanner,
    RemediationPlan,
    RiskLevel,
    ThreatModel,
)
from .org_standards_validator import (
    OrgStandardsValidator,
    StandardsPolicy,
    ValidationReport,
)
from .pr_security_scanner import (
    PRMetadata,
    PRSecurityScanner,
    ScanConfiguration,
    ScanResult,
)
from .pr_security_scanner import SeverityLevel as ScanSeverity

logger = structlog.get_logger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================


class SecurityWorkflowType(str, Enum):
    """Types of security workflows."""

    PR_REVIEW = "pr_review"
    SECURITY_ASSESSMENT = "security_assessment"
    COMPLIANCE_AUDIT = "compliance_audit"
    INCIDENT_ANALYSIS = "incident_analysis"
    THREAT_MODELING = "threat_modeling"
    CONTINUOUS_MONITORING = "continuous_monitoring"


class WorkflowStatus(str, Enum):
    """Status of a security workflow."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REQUIRES_ACTION = "requires_action"


class OverallRiskLevel(str, Enum):
    """Overall risk assessment level."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"


class ActionType(str, Enum):
    """Types of recommended actions."""

    BLOCK_MERGE = "block_merge"
    REQUEST_REVIEW = "request_review"
    AUTO_FIX = "auto_fix"
    CREATE_TICKET = "create_ticket"
    NOTIFY_TEAM = "notify_team"
    ESCALATE = "escalate"
    REMEDIATE = "remediate"


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class SecurityAction:
    """A recommended security action."""

    action_id: str
    action_type: ActionType
    priority: int  # 1 (highest) to 5 (lowest)
    title: str
    description: str
    target: str  # What to act on
    auto_executable: bool = False
    deadline: datetime | None = None
    assigned_to: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SecurityInsight:
    """An insight derived from security analysis."""

    insight_id: str
    category: str
    title: str
    description: str
    severity: OverallRiskLevel
    evidence: list[str]
    recommendations: list[str]
    related_findings: list[str] = field(default_factory=list)


@dataclass
class CorrelatedFinding:
    """A finding correlated across multiple security tools."""

    correlation_id: str
    title: str
    description: str
    severity: OverallRiskLevel
    sources: list[str]  # Which tools detected this
    finding_ids: list[str]  # IDs from each tool
    attack_paths: list[str] = field(default_factory=list)
    mitre_techniques: list[str] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class WorkflowResult:
    """Result of a security workflow execution."""

    workflow_id: str
    workflow_type: SecurityWorkflowType
    status: WorkflowStatus
    started_at: datetime
    completed_at: datetime | None
    duration_seconds: float

    # Component results
    scan_result: ScanResult | None = None
    validation_report: ValidationReport | None = None
    attack_surface: AttackSurface | None = None
    threat_model: ThreatModel | None = None

    # Aggregated analysis
    overall_risk: OverallRiskLevel = OverallRiskLevel.MINIMAL
    risk_score: float = 0.0
    correlated_findings: list[CorrelatedFinding] = field(default_factory=list)
    insights: list[SecurityInsight] = field(default_factory=list)
    recommended_actions: list[SecurityAction] = field(default_factory=list)

    # Decision support
    can_proceed: bool = True
    blocking_issues: list[str] = field(default_factory=list)
    summary: str = ""

    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PRSecurityReview:
    """Complete PR security review result."""

    review_id: str
    pr_id: str
    repository: str
    status: WorkflowStatus
    overall_risk: OverallRiskLevel

    # Scan results
    vulnerability_scan: ScanResult | None
    standards_validation: ValidationReport | None

    # Analysis
    risk_score: float
    correlated_findings: list[CorrelatedFinding]
    insights: list[SecurityInsight]
    actions: list[SecurityAction]

    # Decision
    approve: bool
    request_changes: bool
    blocking_reasons: list[str]

    # Report
    pr_comment: str
    detailed_report: str

    started_at: datetime
    completed_at: datetime
    duration_seconds: float


@dataclass
class SecurityAssessment:
    """Comprehensive security assessment result."""

    assessment_id: str
    name: str
    scope: str
    status: WorkflowStatus

    # Analysis components
    attack_surface: AttackSurface | None
    threat_model: ThreatModel | None
    attack_simulations: list[AttackSimulation]
    remediation_plans: list[RemediationPlan]

    # Risk analysis
    overall_risk: OverallRiskLevel
    risk_score: float
    critical_findings: int
    high_findings: int

    # Reports
    executive_summary: str
    technical_report: str
    mitre_mapping: dict[str, Any]

    started_at: datetime
    completed_at: datetime


# =============================================================================
# Security Agent Orchestrator
# =============================================================================


class SecurityAgentOrchestrator:
    """
    Unified orchestrator for all security agent capabilities.

    Provides integrated security workflows:
    - PR security review (scanning + standards)
    - Security assessment (attack surface + threat model)
    - Compliance audit
    - Continuous monitoring
    """

    # Result cache configuration
    MAX_RESULT_CACHE_SIZE = 500
    PR_CACHE_TTL_SECONDS = 3600  # 1 hour
    ASSESSMENT_CACHE_TTL_SECONDS = 7200  # 2 hours

    def __init__(
        self,
        neptune_client: Any = None,
        opensearch_client: Any = None,
        llm_client: Any = None,
        notification_service: Any = None,
        enable_result_cache: bool = True,
    ):
        self._neptune = neptune_client
        self._opensearch = opensearch_client
        self._llm = llm_client
        self._notifications = notification_service
        self._enable_result_cache = enable_result_cache

        # Initialize component services
        self._pr_scanner = PRSecurityScanner(
            neptune_client=neptune_client,
            opensearch_client=opensearch_client,
            llm_client=llm_client,
        )

        self._attack_planner = DynamicAttackPlanner(
            neptune_client=neptune_client,
            opensearch_client=opensearch_client,
            llm_client=llm_client,
        )

        self._standards_validator = OrgStandardsValidator(
            neptune_client=neptune_client,
            opensearch_client=opensearch_client,
            llm_client=llm_client,
        )

        # Workflow history
        self._workflows: dict[str, WorkflowResult] = {}

        # Agent result cache (content-based for deduplication)
        # Key: content hash, Value: {"result": ..., "timestamp": ...}
        self._result_cache: dict[str, dict[str, Any]] = {}

        # Cache statistics
        self._cache_hits = 0
        self._cache_misses = 0

        self._logger = logger.bind(service="security_agent_orchestrator")

    # =========================================================================
    # Result Caching Methods
    # =========================================================================

    def _generate_pr_cache_key(
        self, pr_metadata: "PRMetadata", file_contents: dict[str, str]
    ) -> str:
        """Generate cache key based on PR content hash."""
        # Hash PR metadata
        pr_hash = hashlib.sha256(
            f"{pr_metadata.repository}:{pr_metadata.pr_id}:{pr_metadata.head_sha}".encode()
        ).hexdigest()[:16]

        # Hash file contents for content-based deduplication
        content_hash = hashlib.sha256(
            "".join(sorted(f"{k}:{v}" for k, v in file_contents.items())).encode()
        ).hexdigest()[:16]

        return f"pr:{pr_hash}:{content_hash}"

    def _generate_assessment_cache_key(self, name: str, assets: list["Asset"]) -> str:
        """Generate cache key based on assessment scope."""
        # Hash assessment name and asset fingerprints
        asset_fingerprint = hashlib.sha256(
            "".join(
                sorted(
                    f"{a.asset_id}:{a.asset_type.value}:{a.risk_score}" for a in assets
                )
            ).encode()
        ).hexdigest()[:16]

        name_hash = hashlib.sha256(name.encode()).hexdigest()[:8]
        return f"assessment:{name_hash}:{asset_fingerprint}"

    def _get_cached_result(self, cache_key: str, ttl_seconds: int) -> Any | None:
        """Retrieve cached result if valid (not expired)."""
        if not self._enable_result_cache:
            return None

        cached = self._result_cache.get(cache_key)
        if not cached:
            self._cache_misses += 1
            return None

        # Check TTL
        age = time.time() - cached["timestamp"]
        if age > ttl_seconds:
            del self._result_cache[cache_key]
            self._cache_misses += 1
            return None

        self._cache_hits += 1
        self._logger.debug(
            "Cache hit for agent result",
            cache_key=cache_key,
            age_seconds=age,
        )
        return cached["result"]

    def _cache_result(self, cache_key: str, result: Any) -> None:
        """Cache a result with current timestamp."""
        if not self._enable_result_cache:
            return

        self._result_cache[cache_key] = {
            "result": result,
            "timestamp": time.time(),
        }

        # Enforce cache size limit (FIFO eviction)
        if len(self._result_cache) > self.MAX_RESULT_CACHE_SIZE:
            evict_count = len(self._result_cache) - self.MAX_RESULT_CACHE_SIZE + 50
            keys_to_evict = list(self._result_cache.keys())[:evict_count]
            for key in keys_to_evict:
                del self._result_cache[key]
            self._logger.debug(
                "Evicted stale cache entries",
                evicted=len(keys_to_evict),
            )

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_size": len(self._result_cache),
            "max_size": self.MAX_RESULT_CACHE_SIZE,
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_rate": (
                self._cache_hits / (self._cache_hits + self._cache_misses)
                if (self._cache_hits + self._cache_misses) > 0
                else 0.0
            ),
            "enabled": self._enable_result_cache,
        }

    def clear_cache(self) -> int:
        """Clear the result cache. Returns number of entries cleared."""
        count = len(self._result_cache)
        self._result_cache.clear()
        self._logger.info("Cleared result cache", entries_cleared=count)
        return count

    # =========================================================================
    # PR Security Review Workflow
    # =========================================================================

    async def review_pull_request(
        self,
        pr_metadata: PRMetadata,
        file_contents: dict[str, str],
        scan_config: ScanConfiguration | None = None,
        standards_policy: StandardsPolicy | None = None,
        enable_attack_analysis: bool = False,
        use_cache: bool = True,
    ) -> PRSecurityReview:
        """
        Perform comprehensive security review of a pull request.

        Args:
            pr_metadata: PR metadata
            file_contents: Changed file contents
            scan_config: Security scan configuration
            standards_policy: Standards policy to enforce
            enable_attack_analysis: Whether to analyze potential attack vectors
            use_cache: Use cached result if available (default True)

        Returns:
            Complete PR security review
        """
        # Check cache first (content-based deduplication)
        if use_cache:
            cache_key = self._generate_pr_cache_key(pr_metadata, file_contents)
            cached_result = self._get_cached_result(
                cache_key, self.PR_CACHE_TTL_SECONDS
            )
            if cached_result:
                self._logger.info(
                    "Returning cached PR security review",
                    pr_id=pr_metadata.pr_id,
                    cache_key=cache_key[:32],
                )
                return cached_result

        review_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)

        self._logger.info(
            "Starting PR security review",
            review_id=review_id,
            pr_id=pr_metadata.pr_id,
            repository=pr_metadata.repository,
            files=len(file_contents),
        )

        # Run scans in parallel
        scan_task = self._pr_scanner.scan_pull_request(
            pr_metadata=pr_metadata, file_contents=file_contents, config=scan_config
        )

        validation_task = self._standards_validator.validate(
            file_contents=file_contents, policy=standards_policy
        )

        scan_result_raw, validation_report_raw = await asyncio.gather(
            scan_task, validation_task, return_exceptions=True
        )

        # Handle exceptions - convert to None for type safety
        scan_result: ScanResult | None
        if isinstance(scan_result_raw, Exception):
            self._logger.error("Scan failed", error=str(scan_result_raw))
            scan_result = None
        else:
            # Type narrowing: if not Exception, must be ScanResult
            scan_result = cast(ScanResult, scan_result_raw)

        validation_report: ValidationReport | None
        if isinstance(validation_report_raw, Exception):
            self._logger.error("Validation failed", error=str(validation_report_raw))
            validation_report = None
        else:
            # Type narrowing: if not Exception, must be ValidationReport
            validation_report = cast(ValidationReport, validation_report_raw)

        # Correlate findings across tools
        correlated = self._correlate_pr_findings(scan_result, validation_report)

        # Generate insights
        insights = self._generate_pr_insights(
            scan_result, validation_report, correlated
        )

        # Calculate overall risk
        risk_score, overall_risk = self._calculate_pr_risk(
            scan_result, validation_report
        )

        # Determine recommended actions
        actions = self._determine_pr_actions(
            scan_result, validation_report, overall_risk, pr_metadata
        )

        # Make approval decision
        approve, request_changes, blocking_reasons = self._make_approval_decision(
            scan_result, validation_report, actions
        )

        # Generate reports
        pr_comment = self._generate_pr_comment(
            scan_result, validation_report, overall_risk, correlated, actions
        )

        detailed_report = self._generate_detailed_report(
            scan_result, validation_report, insights, correlated
        )

        completed_at = datetime.now(timezone.utc)

        review = PRSecurityReview(
            review_id=review_id,
            pr_id=pr_metadata.pr_id,
            repository=pr_metadata.repository,
            status=WorkflowStatus.COMPLETED,
            overall_risk=overall_risk,
            vulnerability_scan=scan_result,
            standards_validation=validation_report,
            risk_score=risk_score,
            correlated_findings=correlated,
            insights=insights,
            actions=actions,
            approve=approve,
            request_changes=request_changes,
            blocking_reasons=blocking_reasons,
            pr_comment=pr_comment,
            detailed_report=detailed_report,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=(completed_at - started_at).total_seconds(),
        )

        self._logger.info(
            "PR security review completed",
            review_id=review_id,
            overall_risk=overall_risk.value,
            approve=approve,
            correlated_findings=len(correlated),
            duration_s=review.duration_seconds,
        )

        # Cache result for future identical requests
        if use_cache:
            cache_key = self._generate_pr_cache_key(pr_metadata, file_contents)
            self._cache_result(cache_key, review)

        return review

    def _correlate_pr_findings(
        self, scan_result: ScanResult | None, validation_report: ValidationReport | None
    ) -> list[CorrelatedFinding]:
        """Correlate findings across PR scanning tools."""
        correlated: list[CorrelatedFinding] = []

        if not scan_result and not validation_report:
            return correlated

        # Group by file
        findings_by_file: dict[str, list[dict]] = {}

        if scan_result:
            for finding in scan_result.findings:
                file_path = finding.location.file_path
                if file_path not in findings_by_file:
                    findings_by_file[file_path] = []
                findings_by_file[file_path].append(
                    {
                        "source": "security_scan",
                        "id": finding.finding_id,
                        "title": finding.title,
                        "severity": finding.severity.value,
                        "line": finding.location.start_line,
                        "category": finding.category.value,
                    }
                )

        if validation_report:
            for violation in validation_report.violations:
                file_path = violation.location.file_path
                if file_path not in findings_by_file:
                    findings_by_file[file_path] = []
                findings_by_file[file_path].append(
                    {
                        "source": "standards_validation",
                        "id": violation.violation_id,
                        "title": violation.rule.name,
                        "severity": violation.severity.value,
                        "line": violation.location.start_line,
                        "category": violation.rule.category.value,
                    }
                )

        # Find correlated issues (same file, nearby lines, related categories)
        for file_path, findings in findings_by_file.items():
            if len(findings) < 2:
                continue

            # Check for security + standards correlation
            security_findings = [f for f in findings if f["source"] == "security_scan"]
            standard_findings = [
                f for f in findings if f["source"] == "standards_validation"
            ]

            if security_findings and standard_findings:
                # Check for nearby lines (within 10 lines)
                for sec_f in security_findings:
                    for std_f in standard_findings:
                        if abs(sec_f["line"] - std_f["line"]) <= 10:
                            correlated.append(
                                CorrelatedFinding(
                                    correlation_id=str(uuid.uuid4()),
                                    title=f"Correlated issue in {file_path}",
                                    description=f"Security issue '{sec_f['title']}' found near standards violation '{std_f['title']}'",
                                    severity=self._map_to_overall_risk(
                                        sec_f["severity"]
                                    ),
                                    sources=["security_scan", "standards_validation"],
                                    finding_ids=[sec_f["id"], std_f["id"]],
                                    confidence=0.8,
                                )
                            )

        return correlated

    def _generate_pr_insights(
        self,
        scan_result: ScanResult | None,
        validation_report: ValidationReport | None,
        correlated: list[CorrelatedFinding],
    ) -> list[SecurityInsight]:
        """Generate insights from PR analysis."""
        insights = []

        # Secret detection insight
        if scan_result and scan_result.secret_findings:
            insights.append(
                SecurityInsight(
                    insight_id=str(uuid.uuid4()),
                    category="secrets",
                    title="Secrets Detected in Code",
                    description=f"Found {len(scan_result.secret_findings)} potential secrets or credentials in the changes",
                    severity=OverallRiskLevel.CRITICAL,
                    evidence=[f.secret_type for f in scan_result.secret_findings[:5]],
                    recommendations=[
                        "Remove all secrets from source code immediately",
                        "Rotate any exposed credentials",
                        "Use environment variables or secrets manager",
                    ],
                )
            )

        # Dependency vulnerability insight
        if scan_result:
            vuln_deps = [
                d for d in scan_result.dependency_findings if d.vulnerabilities
            ]
            if vuln_deps:
                insights.append(
                    SecurityInsight(
                        insight_id=str(uuid.uuid4()),
                        category="dependencies",
                        title="Vulnerable Dependencies Detected",
                        description=f"Found {len(vuln_deps)} dependencies with known vulnerabilities",
                        severity=OverallRiskLevel.HIGH,
                        evidence=[d.name for d in vuln_deps[:5]],
                        recommendations=[
                            "Update vulnerable dependencies to patched versions",
                            "Review dependency tree for transitive vulnerabilities",
                            "Consider alternative packages if no patch available",
                        ],
                    )
                )

        # Code quality insight
        if validation_report:
            security_violations = [
                v
                for v in validation_report.violations
                if v.rule.category.value == "security"
            ]
            if security_violations:
                insights.append(
                    SecurityInsight(
                        insight_id=str(uuid.uuid4()),
                        category="code_security",
                        title="Security-Related Code Issues",
                        description=f"Found {len(security_violations)} security-related code standards violations",
                        severity=OverallRiskLevel.HIGH,
                        evidence=[v.rule.name for v in security_violations[:5]],
                        recommendations=[
                            "Address security coding standards violations",
                            "Consider security-focused code review",
                            "Enable pre-commit security checks",
                        ],
                    )
                )

        # Correlation insight
        if correlated:
            insights.append(
                SecurityInsight(
                    insight_id=str(uuid.uuid4()),
                    category="correlation",
                    title="Correlated Security Issues",
                    description=f"Found {len(correlated)} issues correlated across multiple analysis tools",
                    severity=OverallRiskLevel.MEDIUM,
                    evidence=[c.title for c in correlated[:5]],
                    recommendations=[
                        "Review correlated findings for root cause analysis",
                        "Prioritize fixing issues detected by multiple tools",
                    ],
                )
            )

        return insights

    def _calculate_pr_risk(
        self, scan_result: ScanResult | None, validation_report: ValidationReport | None
    ) -> tuple[float, OverallRiskLevel]:
        """Calculate overall risk score for PR."""
        score = 0.0

        if scan_result:
            score += scan_result.summary.risk_score * 0.6  # Weight security scan higher

        if validation_report:
            # Convert validation to 0-100 score
            validation_score = (
                validation_report.blocker_count * 25
                + validation_report.critical_count * 15
                + validation_report.major_count * 5
                + validation_report.minor_count * 1
            )
            score += min(100, validation_score) * 0.4

        # Map to risk level
        if score >= 70:
            level = OverallRiskLevel.CRITICAL
        elif score >= 50:
            level = OverallRiskLevel.HIGH
        elif score >= 30:
            level = OverallRiskLevel.MEDIUM
        elif score >= 10:
            level = OverallRiskLevel.LOW
        else:
            level = OverallRiskLevel.MINIMAL

        return score, level

    def _determine_pr_actions(
        self,
        scan_result: ScanResult | None,
        validation_report: ValidationReport | None,
        overall_risk: OverallRiskLevel,
        pr_metadata: PRMetadata,
    ) -> list[SecurityAction]:
        """Determine recommended actions for PR."""
        actions = []

        # Critical risk = block merge
        if overall_risk in [OverallRiskLevel.CRITICAL]:
            actions.append(
                SecurityAction(
                    action_id=str(uuid.uuid4()),
                    action_type=ActionType.BLOCK_MERGE,
                    priority=1,
                    title="Block PR Merge",
                    description="Critical security issues detected that must be resolved",
                    target=pr_metadata.pr_id,
                    auto_executable=True,
                )
            )

        # Secrets detected = escalate
        if scan_result and scan_result.secret_findings:
            actions.append(
                SecurityAction(
                    action_id=str(uuid.uuid4()),
                    action_type=ActionType.ESCALATE,
                    priority=1,
                    title="Escalate Secret Exposure",
                    description="Secrets detected in code changes require immediate attention",
                    target=pr_metadata.pr_id,
                    metadata={"secret_count": len(scan_result.secret_findings)},
                )
            )

        # High risk = request security review
        if overall_risk in [OverallRiskLevel.HIGH, OverallRiskLevel.CRITICAL]:
            actions.append(
                SecurityAction(
                    action_id=str(uuid.uuid4()),
                    action_type=ActionType.REQUEST_REVIEW,
                    priority=2,
                    title="Request Security Team Review",
                    description="High-risk changes require security team approval",
                    target=pr_metadata.pr_id,
                    assigned_to="security-team",
                )
            )

        # Auto-fixable issues
        if validation_report:
            auto_fixable = [
                v for v in validation_report.violations if v.rule.auto_fixable
            ]
            if auto_fixable:
                actions.append(
                    SecurityAction(
                        action_id=str(uuid.uuid4()),
                        action_type=ActionType.AUTO_FIX,
                        priority=3,
                        title="Apply Automatic Fixes",
                        description=f"{len(auto_fixable)} issues can be automatically fixed",
                        target=pr_metadata.pr_id,
                        auto_executable=True,
                        metadata={"fixable_count": len(auto_fixable)},
                    )
                )

        # Create tickets for remediation
        if scan_result and scan_result.findings:
            critical_high = [
                f
                for f in scan_result.findings
                if f.severity in [ScanSeverity.CRITICAL, ScanSeverity.HIGH]
            ]
            if critical_high:
                actions.append(
                    SecurityAction(
                        action_id=str(uuid.uuid4()),
                        action_type=ActionType.CREATE_TICKET,
                        priority=2,
                        title="Create Security Tickets",
                        description=f"Create tracking tickets for {len(critical_high)} high-priority findings",
                        target="jira",
                        metadata={"finding_count": len(critical_high)},
                    )
                )

        # Sort by priority
        actions.sort(key=lambda a: a.priority)

        return actions

    def _make_approval_decision(
        self,
        scan_result: ScanResult | None,
        validation_report: ValidationReport | None,
        actions: list[SecurityAction],
    ) -> tuple[bool, bool, list[str]]:
        """Make approval decision for PR."""
        blocking_reasons = []

        # Check for blocking scan results
        if scan_result:
            if scan_result.summary.block_merge:
                blocking_reasons.append("Security scan detected blocking issues")
            if scan_result.secret_findings:
                blocking_reasons.append("Secrets detected in code")

        # Check for blocking validation results
        if validation_report:
            if not validation_report.can_merge:
                blocking_reasons.append("Standards validation has blocking violations")

        # Check for blocking actions
        has_block_action = any(a.action_type == ActionType.BLOCK_MERGE for a in actions)
        if has_block_action:
            if "Security scan detected blocking issues" not in blocking_reasons:
                blocking_reasons.append("Critical security issues require resolution")

        approve = len(blocking_reasons) == 0
        request_changes = len(blocking_reasons) > 0

        return approve, request_changes, blocking_reasons

    def _generate_pr_comment(
        self,
        scan_result: ScanResult | None,
        validation_report: ValidationReport | None,
        overall_risk: OverallRiskLevel,
        correlated: list[CorrelatedFinding],
        actions: list[SecurityAction],
    ) -> str:
        """Generate unified PR comment."""
        risk_emoji = {
            OverallRiskLevel.CRITICAL: ":rotating_light:",
            OverallRiskLevel.HIGH: ":warning:",
            OverallRiskLevel.MEDIUM: ":yellow_circle:",
            OverallRiskLevel.LOW: ":large_blue_circle:",
            OverallRiskLevel.MINIMAL: ":white_check_mark:",
        }

        lines = [
            "# Security Review Results",
            "",
            f"**Overall Risk:** {risk_emoji.get(overall_risk, '')} **{overall_risk.value.upper()}**",
            "",
            "---",
            "",
        ]

        # Security Scan Section
        if scan_result:
            scan_status = (
                ":white_check_mark:" if scan_result.summary.scan_passed else ":x:"
            )
            lines.extend(
                [
                    f"## {scan_status} Security Scan",
                    "",
                    "| Finding Type | Count |",
                    "|--------------|-------|",
                    f"| Critical Vulnerabilities | {scan_result.summary.critical_count} |",
                    f"| High Vulnerabilities | {scan_result.summary.high_count} |",
                    f"| Secrets Detected | {scan_result.summary.secrets_detected} |",
                    f"| Vulnerable Dependencies | {scan_result.summary.vulnerable_dependencies} |",
                    f"| IaC Issues | {scan_result.summary.iac_issues} |",
                    "",
                ]
            )

        # Standards Validation Section
        if validation_report:
            val_status = ":white_check_mark:" if validation_report.can_merge else ":x:"
            lines.extend(
                [
                    f"## {val_status} Standards Validation",
                    "",
                    "| Severity | Count |",
                    "|----------|-------|",
                    f"| Blocker | {validation_report.blocker_count} |",
                    f"| Critical | {validation_report.critical_count} |",
                    f"| Major | {validation_report.major_count} |",
                    f"| Minor | {validation_report.minor_count} |",
                    "",
                ]
            )

        # Correlated Findings
        if correlated:
            lines.extend(
                [
                    "## :link: Correlated Findings",
                    "",
                    f"Found {len(correlated)} issues detected by multiple analysis tools.",
                    "",
                ]
            )

        # Required Actions
        blocking_actions = [a for a in actions if a.priority <= 2]
        if blocking_actions:
            lines.extend(["## :exclamation: Required Actions", ""])
            for action in blocking_actions:
                lines.append(f"- **{action.title}**: {action.description}")
            lines.append("")

        # Decision
        has_blockers = any(a.action_type == ActionType.BLOCK_MERGE for a in actions)
        if has_blockers:
            lines.extend(
                [
                    "---",
                    "",
                    ":no_entry: **This PR cannot be merged until blocking issues are resolved.**",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "---",
                    "",
                    ":white_check_mark: **No blocking security issues found.**",
                    "",
                ]
            )

        return "\n".join(lines)

    def _generate_detailed_report(
        self,
        scan_result: ScanResult | None,
        validation_report: ValidationReport | None,
        insights: list[SecurityInsight],
        correlated: list[CorrelatedFinding],
    ) -> str:
        """Generate detailed markdown report."""
        lines = [
            "# Detailed Security Analysis Report",
            "",
            f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "---",
            "",
            "## Executive Summary",
            "",
        ]

        # Add insights
        if insights:
            lines.append("### Key Findings")
            lines.append("")
            for insight in insights:
                lines.append(f"#### {insight.title}")
                lines.append(f"**Severity:** {insight.severity.value.upper()}")
                lines.append(f"**Category:** {insight.category}")
                lines.append("")
                lines.append(insight.description)
                lines.append("")
                if insight.recommendations:
                    lines.append("**Recommendations:**")
                    for rec in insight.recommendations:
                        lines.append(f"- {rec}")
                    lines.append("")

        # Add detailed findings
        if scan_result and scan_result.findings:
            lines.extend(
                [
                    "## Security Findings",
                    "",
                ]
            )
            for finding in scan_result.findings[:20]:  # Top 20
                lines.extend(
                    [
                        f"### {finding.title}",
                        f"- **Severity:** {finding.severity.value}",
                        f"- **Category:** {finding.category.value}",
                        f"- **Location:** `{finding.location.file_path}:{finding.location.start_line}`",
                        f"- **Description:** {finding.description}",
                        "",
                    ]
                )
                if finding.remediation:
                    lines.append(f"**Remediation:** {finding.remediation.description}")
                    lines.append("")

        return "\n".join(lines)

    # =========================================================================
    # Security Assessment Workflow
    # =========================================================================

    async def run_security_assessment(
        self,
        name: str,
        assets: list[Asset],
        threat_actors: list[str] | None = None,
        simulate_attacks: bool = True,
        use_cache: bool = True,
    ) -> SecurityAssessment:
        """
        Run comprehensive security assessment.

        Args:
            name: Assessment name
            assets: Assets to assess
            threat_actors: Threat actors to model
            simulate_attacks: Whether to simulate attack paths
            use_cache: Use cached result if available (default True)

        Returns:
            Complete security assessment
        """
        # Check cache first
        if use_cache:
            cache_key = self._generate_assessment_cache_key(name, assets)
            cached_result = self._get_cached_result(
                cache_key, self.ASSESSMENT_CACHE_TTL_SECONDS
            )
            if cached_result:
                self._logger.info(
                    "Returning cached security assessment",
                    name=name,
                    cache_key=cache_key[:32],
                )
                return cached_result

        assessment_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)

        self._logger.info(
            "Starting security assessment",
            assessment_id=assessment_id,
            name=name,
            assets=len(assets),
        )

        # Analyze attack surface
        attack_surface = await self._attack_planner.analyze_attack_surface(
            scope_name=name, assets=assets, include_vulnerability_scan=True
        )

        # Create threat model
        threat_model = await self._attack_planner.create_threat_model(
            name=f"{name} Threat Model", assets=assets, threat_actors=threat_actors
        )

        # Simulate attacks
        simulations = []
        if simulate_attacks and attack_surface.attack_paths:
            for path in attack_surface.attack_paths[:5]:  # Top 5 paths
                simulation = await self._attack_planner.simulate_attack(
                    attack_path=path, safe_mode=True
                )
                simulations.append(simulation)

        # Generate remediation plans
        remediation_plans = await self._attack_planner.generate_remediation_plan(
            attack_surface
        )

        # Calculate overall risk
        overall_risk = self._map_risk_score_to_level(attack_surface.risk_score)

        # Generate reports
        executive_summary = self._attack_planner.generate_executive_report(
            attack_surface
        )
        mitre_mapping = self._attack_planner.generate_mitre_attack_mapping(
            attack_surface
        )

        technical_report = self._generate_assessment_technical_report(
            attack_surface, threat_model, simulations, remediation_plans
        )

        # Count findings
        critical_findings = len(
            [
                v
                for v in attack_surface.vulnerabilities
                if v.severity == RiskLevel.CRITICAL
            ]
        )
        high_findings = len(
            [v for v in attack_surface.vulnerabilities if v.severity == RiskLevel.HIGH]
        )

        completed_at = datetime.now(timezone.utc)

        assessment = SecurityAssessment(
            assessment_id=assessment_id,
            name=name,
            scope=f"{len(assets)} assets analyzed",
            status=WorkflowStatus.COMPLETED,
            attack_surface=attack_surface,
            threat_model=threat_model,
            attack_simulations=simulations,
            remediation_plans=remediation_plans,
            overall_risk=overall_risk,
            risk_score=attack_surface.risk_score,
            critical_findings=critical_findings,
            high_findings=high_findings,
            executive_summary=executive_summary,
            technical_report=technical_report,
            mitre_mapping=mitre_mapping,
            started_at=started_at,
            completed_at=completed_at,
        )

        self._logger.info(
            "Security assessment completed",
            assessment_id=assessment_id,
            overall_risk=overall_risk.value,
            critical=critical_findings,
            high=high_findings,
        )

        # Cache result for future identical requests
        if use_cache:
            cache_key = self._generate_assessment_cache_key(name, assets)
            self._cache_result(cache_key, assessment)

        return assessment

    def _generate_assessment_technical_report(
        self,
        attack_surface: AttackSurface,
        threat_model: ThreatModel,
        simulations: list[AttackSimulation],
        remediation_plans: list[RemediationPlan],
    ) -> str:
        """Generate technical assessment report."""
        lines = [
            "# Technical Security Assessment Report",
            "",
            f"**Assessment ID:** {attack_surface.surface_id}",
            f"**Date:** {attack_surface.analyzed_at.strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "---",
            "",
            "## Attack Surface Analysis",
            "",
            f"- **Assets Analyzed:** {len(attack_surface.assets)}",
            f"- **Vulnerabilities Found:** {len(attack_surface.vulnerabilities)}",
            f"- **Attack Vectors Identified:** {len(attack_surface.attack_vectors)}",
            f"- **Attack Paths Mapped:** {len(attack_surface.attack_paths)}",
            "",
            "## Threat Model",
            "",
            f"- **Threat Actors Considered:** {len(threat_model.threat_actors)}",
            f"- **Attack Scenarios:** {len(threat_model.attack_scenarios)}",
            f"- **Crown Jewels:** {len(threat_model.crown_jewels)}",
            "",
        ]

        # Simulation results
        if simulations:
            lines.extend(["## Attack Simulation Results", ""])
            for sim in simulations:
                status_emoji = (
                    ":shield:" if sim.status.value == "blocked" else ":warning:"
                )
                lines.extend(
                    [
                        f"### {status_emoji} {sim.attack_path.name}",
                        f"- **Status:** {sim.status.value}",
                        f"- **Steps Completed:** {sim.steps_completed}",
                        f"- **Steps Blocked:** {sim.steps_blocked}",
                        f"- **Controls Triggered:** {', '.join(sim.controls_triggered) or 'None'}",
                        "",
                    ]
                )

        # Remediation priorities
        if remediation_plans:
            lines.extend(["## Remediation Priorities", ""])
            for plan in remediation_plans:
                lines.extend(
                    [
                        f"### {plan.title}",
                        f"- **Priority:** {plan.priority.value}",
                        f"- **Effort:** {plan.effort_estimate}",
                        f"- **Expected Risk Reduction:** {plan.expected_risk_reduction:.1f}%",
                        "",
                    ]
                )

        return "\n".join(lines)

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def _map_to_overall_risk(self, severity: str) -> OverallRiskLevel:
        """Map severity string to overall risk level."""
        mapping = {
            "critical": OverallRiskLevel.CRITICAL,
            "high": OverallRiskLevel.HIGH,
            "medium": OverallRiskLevel.MEDIUM,
            "low": OverallRiskLevel.LOW,
            "info": OverallRiskLevel.MINIMAL,
            "blocker": OverallRiskLevel.CRITICAL,
            "major": OverallRiskLevel.HIGH,
            "minor": OverallRiskLevel.LOW,
        }
        return mapping.get(severity.lower(), OverallRiskLevel.MEDIUM)

    def _map_risk_score_to_level(self, score: float) -> OverallRiskLevel:
        """Map risk score to overall risk level."""
        if score >= 70:
            return OverallRiskLevel.CRITICAL
        elif score >= 50:
            return OverallRiskLevel.HIGH
        elif score >= 30:
            return OverallRiskLevel.MEDIUM
        elif score >= 10:
            return OverallRiskLevel.LOW
        else:
            return OverallRiskLevel.MINIMAL

    # =========================================================================
    # Component Access
    # =========================================================================

    @property
    def pr_scanner(self) -> PRSecurityScanner:
        """Access PR security scanner directly."""
        return self._pr_scanner

    @property
    def attack_planner(self) -> DynamicAttackPlanner:
        """Access attack planner directly."""
        return self._attack_planner

    @property
    def standards_validator(self) -> OrgStandardsValidator:
        """Access standards validator directly."""
        return self._standards_validator
