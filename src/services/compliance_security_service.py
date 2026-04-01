"""
Compliance-Aware Security Review Service.

Integrates compliance profiles with security scanning to provide
compliance-aware vulnerability detection and remediation.

Author: Aura Platform Team
Date: 2025-12-06
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.services.compliance_config import get_compliance_config
from src.services.compliance_profiles import ComplianceLevel, SeverityLevel

logger = logging.getLogger(__name__)


@dataclass
class SecurityFinding:
    """Represents a security vulnerability finding."""

    id: str
    severity: SeverityLevel
    title: str
    description: str
    file_path: str
    line_number: Optional[int] = None
    cwe_id: Optional[str] = None
    owasp_category: Optional[str] = None
    remediation: Optional[str] = None
    compliance_impact: List[str] = field(default_factory=list)


@dataclass
class ComplianceScanResult:
    """Results from a compliance-aware security scan."""

    profile_name: ComplianceLevel
    profile_display_name: str
    scan_timestamp: datetime
    files_scanned: int
    files_skipped: int
    findings: List[SecurityFinding]
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    should_block_deployment: bool = False
    requires_manual_review: bool = False
    manual_review_reasons: List[str] = field(default_factory=list)
    audit_metadata: Dict = field(default_factory=dict)


class ComplianceSecurityService:
    """
    Provides compliance-aware security scanning.

    Integrates with:
    - Compliance profile system
    - Semgrep/Trivy security scanners
    - HITL approval workflows
    - Audit logging
    """

    def __init__(self) -> None:
        """Initialize ComplianceSecurityService."""
        self.config = get_compliance_config()
        self.profile = self.config.get_profile()
        self.profile_manager = self.config.get_profile_manager()

        logger.info(
            f"Initialized ComplianceSecurityService with profile: {self.profile.display_name}"
        )

    def should_scan_file(self, file_path: str) -> Tuple[bool, str]:
        """
        Determine if a file should be scanned based on compliance profile.

        Args:
            file_path: Path to the file

        Returns:
            Tuple of (should_scan, reason)
        """
        if not self.config.is_enabled():
            return True, "Compliance enforcement disabled"

        # Get scanning policy from profile
        scanning = self.profile.scanning

        # Normalize path
        normalized_path = str(Path(file_path).as_posix())

        # Check exclusions first
        for pattern in scanning.excluded_paths:
            pattern_normalized = pattern.replace("**", "").replace("*", "")
            if pattern_normalized in normalized_path:
                return False, f"Excluded by pattern: {pattern}"

        # If scan_all_changes is True, scan unless explicitly excluded
        if scanning.scan_all_changes:
            return True, "Profile scans all changes"

        # Check inclusions
        for pattern in scanning.included_paths:
            pattern_normalized = pattern.replace("**", "").replace("*", "")
            if pattern_normalized in normalized_path:
                return True, f"Included by pattern: {pattern}"

        # Apply specific scanning rules
        if file_path.endswith(".md") or file_path.endswith(".rst"):
            if scanning.scan_documentation:
                return True, "Documentation scanning enabled"
            return False, "Documentation scanning disabled"

        if any(
            file_path.endswith(ext)
            for ext in [".yaml", ".yml", ".json", ".toml", ".ini"]
        ):
            if scanning.scan_configuration:
                return True, "Configuration scanning enabled"
            return False, "Configuration scanning disabled"

        if "test" in normalized_path.lower():
            if scanning.scan_tests:
                return True, "Test scanning enabled"
            return False, "Test scanning disabled"

        # Infrastructure files
        if any(
            keyword in normalized_path.lower()
            for keyword in [
                "cloudformation",
                "terraform",
                "dockerfile",
                "docker-compose",
            ]
        ):
            if scanning.scan_infrastructure:
                return True, "Infrastructure scanning enabled"
            return False, "Infrastructure scanning disabled"

        # Default: don't scan
        return False, "Not matched by any inclusion pattern"

    def filter_files_for_scanning(
        self, file_paths: List[str]
    ) -> Tuple[List[str], List[str], Dict[str, str]]:
        """
        Filter files based on compliance profile.

        Args:
            file_paths: List of file paths to evaluate

        Returns:
            Tuple of (files_to_scan, files_skipped, skip_reasons)
        """
        to_scan = []
        skipped = []
        skip_reasons = {}

        for file_path in file_paths:
            should_scan, reason = self.should_scan_file(file_path)

            if should_scan:
                to_scan.append(file_path)
            else:
                skipped.append(file_path)
                skip_reasons[file_path] = reason

        logger.info(
            f"Filtered {len(file_paths)} files: {len(to_scan)} to scan, {len(skipped)} skipped"
        )

        return to_scan, skipped, skip_reasons

    def categorize_findings(
        self, findings: List[SecurityFinding]
    ) -> Dict[SeverityLevel, List[SecurityFinding]]:
        """
        Categorize findings by severity.

        Args:
            findings: List of security findings

        Returns:
            Dictionary mapping severity to findings
        """
        categorized: dict[SeverityLevel, list[SecurityFinding]] = {
            SeverityLevel.CRITICAL: [],
            SeverityLevel.HIGH: [],
            SeverityLevel.MEDIUM: [],
            SeverityLevel.LOW: [],
            SeverityLevel.INFO: [],
        }

        for finding in findings:
            categorized[finding.severity].append(finding)

        return categorized

    def should_block_deployment(
        self, findings: List[SecurityFinding]
    ) -> Tuple[bool, str]:
        """
        Determine if deployment should be blocked based on findings.

        Args:
            findings: List of security findings

        Returns:
            Tuple of (should_block, reason)
        """
        review_policy = self.profile.review

        categorized = self.categorize_findings(findings)

        critical_count = len(categorized[SeverityLevel.CRITICAL])
        high_count = len(categorized[SeverityLevel.HIGH])

        # Check critical findings
        if critical_count > 0 and review_policy.block_on_critical:
            return True, f"Found {critical_count} critical vulnerabilities"

        # Check high severity findings
        if high_count > 0 and review_policy.block_on_high:
            return True, f"Found {high_count} high severity vulnerabilities"

        return False, "No blocking vulnerabilities found"

    def requires_manual_review(
        self, changed_files: List[str]
    ) -> Tuple[bool, List[str]]:
        """
        Determine if changes require manual HITL review.

        Args:
            changed_files: List of changed file paths

        Returns:
            Tuple of (requires_review, reasons)
        """
        review_policy = self.profile.review
        reasons = []

        # Check for files requiring security approval
        for file_path in changed_files:
            for required_file in review_policy.require_security_approval:
                if required_file in file_path:
                    reasons.append(f"Security-critical file modified: {required_file}")

        # Check for change types requiring review
        for file_path in changed_files:
            # IAM policies
            if "iam" in file_path.lower() and (
                file_path.endswith(".yaml") or file_path.endswith(".yml")
            ):
                if self.profile_manager.requires_manual_review("iam_policies"):
                    reasons.append("IAM policy changes require manual review")

            # Network configurations
            if any(
                keyword in file_path.lower()
                for keyword in ["vpc", "security-group", "network"]
            ):
                if self.profile_manager.requires_manual_review("network_configs"):
                    reasons.append(
                        "Network configuration changes require manual review"
                    )

            # Encryption keys
            if any(keyword in file_path.lower() for keyword in ["kms", "encryption"]):
                if self.profile_manager.requires_manual_review("encryption_keys"):
                    reasons.append("Encryption key changes require manual review")

        requires_review = len(reasons) > 0
        return requires_review, list(set(reasons))  # Deduplicate

    def perform_scan(
        self,
        file_paths: List[str],
        external_findings: Optional[List[SecurityFinding]] = None,
    ) -> ComplianceScanResult:
        """
        Perform a compliance-aware security scan.

        Args:
            file_paths: List of files to scan
            external_findings: Pre-scanned findings from Semgrep/Trivy (optional)

        Returns:
            ComplianceScanResult with findings and compliance metadata
        """
        scan_start = datetime.now(timezone.utc)

        # Filter files based on compliance profile
        to_scan, skipped, skip_reasons = self.filter_files_for_scanning(file_paths)

        # Use external findings or run scan (simplified - real implementation would call Semgrep)
        findings = external_findings or []

        # Categorize findings
        categorized = self.categorize_findings(findings)

        # Determine if deployment should be blocked
        should_block, block_reason = self.should_block_deployment(findings)

        # Determine if manual review is required
        requires_review, review_reasons = self.requires_manual_review(to_scan)

        # Get audit metadata
        audit_metadata = self.profile_manager.get_audit_metadata()
        audit_metadata.update(
            {
                "scan_timestamp": scan_start.isoformat(),
                "files_scanned": len(to_scan),
                "files_skipped": len(skipped),
                "skip_reasons_summary": {
                    reason: len([f for f, r in skip_reasons.items() if r == reason])
                    for reason in set(skip_reasons.values())
                },
                "block_deployment": should_block,
                "block_reason": block_reason if should_block else None,
            }
        )

        result = ComplianceScanResult(
            profile_name=self.profile.name,
            profile_display_name=self.profile.display_name,
            scan_timestamp=scan_start,
            files_scanned=len(to_scan),
            files_skipped=len(skipped),
            findings=findings,
            critical_count=len(categorized[SeverityLevel.CRITICAL]),
            high_count=len(categorized[SeverityLevel.HIGH]),
            medium_count=len(categorized[SeverityLevel.MEDIUM]),
            low_count=len(categorized[SeverityLevel.LOW]),
            should_block_deployment=should_block,
            requires_manual_review=requires_review,
            manual_review_reasons=review_reasons,
            audit_metadata=audit_metadata,
        )

        logger.info(
            f"Scan complete: {len(findings)} findings, "
            f"{result.critical_count} critical, {result.high_count} high. "
            f"Block deployment: {should_block}"
        )

        return result

    def format_scan_summary(self, result: ComplianceScanResult) -> str:
        """
        Format scan result as a human-readable summary.

        Args:
            result: ComplianceScanResult instance

        Returns:
            Formatted summary string
        """
        lines = []
        lines.append("## Aura Compliance-Aware Security Scan")
        lines.append("")
        lines.append(f"**Profile:** {result.profile_display_name}")
        lines.append(
            f"**Scan Time:** {result.scan_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
        lines.append(f"**Files Scanned:** {result.files_scanned}")
        lines.append(f"**Files Skipped:** {result.files_skipped}")
        lines.append("")

        # Findings summary
        total_findings = len(result.findings)
        if total_findings == 0:
            lines.append("### No security findings detected")
        else:
            lines.append(f"### Found {total_findings} security findings:")
            lines.append("")
            if result.critical_count > 0:
                lines.append(f"- **Critical:** {result.critical_count}")
            if result.high_count > 0:
                lines.append(f"- **High:** {result.high_count}")
            if result.medium_count > 0:
                lines.append(f"- **Medium:** {result.medium_count}")
            if result.low_count > 0:
                lines.append(f"- **Low:** {result.low_count}")
            lines.append("")

        # Deployment decision
        if result.should_block_deployment:
            lines.append("### Deployment Status: BLOCKED")
            for reason in result.manual_review_reasons:
                lines.append(f"- {reason}")
        else:
            lines.append("### Deployment Status: APPROVED")

        # Manual review
        if result.requires_manual_review:
            lines.append("")
            lines.append("### Manual Review Required:")
            for reason in result.manual_review_reasons:
                lines.append(f"- {reason}")

        lines.append("")
        lines.append("---")
        lines.append(f"*Scanned per {result.profile_display_name} compliance profile*")

        return "\n".join(lines)

    def get_compliance_report(self) -> Dict:
        """
        Generate a compliance report for audit purposes.

        Returns:
            Dictionary containing compliance metadata
        """
        return {
            "profile": {
                "name": self.profile.name.value,
                "display_name": self.profile.display_name,
                "version": self.profile.version,
                "description": self.profile.description,
            },
            "scanning_policy": {
                "scan_all_changes": self.profile.scanning.scan_all_changes,
                "scan_infrastructure": self.profile.scanning.scan_infrastructure,
                "scan_documentation": self.profile.scanning.scan_documentation,
                "scan_configuration": self.profile.scanning.scan_configuration,
                "scan_tests": self.profile.scanning.scan_tests,
            },
            "review_policy": {
                "block_on_critical": self.profile.review.block_on_critical,
                "block_on_high": self.profile.review.block_on_high,
                "min_reviewers": self.profile.review.min_reviewers,
                "required_reviews": list(self.profile.review.require_manual_review),
            },
            "audit_policy": {
                "log_retention_days": self.profile.audit.log_retention_days,
                "log_scan_decisions": self.profile.audit.log_scan_decisions,
                "log_findings": self.profile.audit.log_findings,
            },
            "control_mappings": self.profile.control_mappings,
        }
