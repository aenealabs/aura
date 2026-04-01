"""
PR Security Scanner Service - AWS Security Agent Parity

Implements comprehensive pull request security scanning with:
- Static code analysis for vulnerability detection
- Secret detection and credential scanning
- Dependency vulnerability analysis (SCA)
- Infrastructure-as-Code (IaC) security validation
- License compliance checking
- OWASP Top 10 detection
- CWE mapping and CVSS scoring

Reference: ADR-030 Section 5.2 Security Agent Components
"""

import asyncio
import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================


class SeverityLevel(str, Enum):
    """Vulnerability severity levels aligned with CVSS."""

    CRITICAL = "critical"  # CVSS 9.0-10.0
    HIGH = "high"  # CVSS 7.0-8.9
    MEDIUM = "medium"  # CVSS 4.0-6.9
    LOW = "low"  # CVSS 0.1-3.9
    INFO = "info"  # Informational


class FindingCategory(str, Enum):
    """Categories of security findings."""

    VULNERABILITY = "vulnerability"
    SECRET = "secret"
    DEPENDENCY = "dependency"
    IAC_MISCONFIGURATION = "iac_misconfiguration"
    LICENSE_VIOLATION = "license_violation"
    CODE_QUALITY = "code_quality"
    COMPLIANCE = "compliance"


class ScanStatus(str, Enum):
    """Status of a security scan."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RemediationStatus(str, Enum):
    """Status of remediation suggestions."""

    AVAILABLE = "available"
    AUTO_FIXABLE = "auto_fixable"
    MANUAL_REQUIRED = "manual_required"
    NO_FIX = "no_fix"


class FileRiskLevel(str, Enum):
    """Risk level of file changes."""

    CRITICAL = "critical"  # Security-sensitive files
    HIGH = "high"  # Core business logic
    MEDIUM = "medium"  # Application code
    LOW = "low"  # Tests, docs, configs


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class PRMetadata:
    """Metadata about the pull request being scanned."""

    pr_id: str
    repository: str
    source_branch: str
    target_branch: str
    author: str
    title: str
    description: str
    files_changed: list[str]
    additions: int
    deletions: int
    commits: list[str]
    labels: list[str] = field(default_factory=list)
    reviewers: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CodeLocation:
    """Location of a finding in the code."""

    file_path: str
    start_line: int
    end_line: int
    start_column: int | None = None
    end_column: int | None = None
    snippet: str = ""
    context_before: str = ""
    context_after: str = ""


@dataclass
class CWEReference:
    """Common Weakness Enumeration reference."""

    cwe_id: str
    name: str
    description: str
    url: str


@dataclass
class CVSSScore:
    """CVSS v3.1 score details."""

    base_score: float
    vector_string: str
    attack_vector: str
    attack_complexity: str
    privileges_required: str
    user_interaction: str
    scope: str
    confidentiality_impact: str
    integrity_impact: str
    availability_impact: str


@dataclass
class Remediation:
    """Remediation guidance for a finding."""

    status: RemediationStatus
    description: str
    suggested_fix: str | None = None
    auto_fix_patch: str | None = None
    references: list[str] = field(default_factory=list)
    effort_estimate: str = "unknown"  # low, medium, high


@dataclass
class SecurityFinding:
    """A single security finding from the scan."""

    finding_id: str
    category: FindingCategory
    severity: SeverityLevel
    title: str
    description: str
    location: CodeLocation
    cwe: CWEReference | None = None
    cvss: CVSSScore | None = None
    remediation: Remediation | None = None
    rule_id: str = ""
    confidence: float = 1.0  # 0.0-1.0
    is_new: bool = True  # New in this PR vs existing
    is_false_positive: bool = False
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DependencyInfo:
    """Information about a dependency."""

    name: str
    version: str
    ecosystem: str  # npm, pip, maven, etc.
    license: str | None = None
    is_direct: bool = True
    is_dev: bool = False
    vulnerabilities: list["DependencyVulnerability"] = field(default_factory=list)


@dataclass
class DependencyVulnerability:
    """Vulnerability in a dependency."""

    vuln_id: str  # CVE or advisory ID
    severity: SeverityLevel
    title: str
    description: str
    fixed_version: str | None = None
    cvss_score: float | None = None
    published_at: datetime | None = None
    references: list[str] = field(default_factory=list)


@dataclass
class SecretFinding:
    """A detected secret or credential."""

    secret_type: str
    severity: SeverityLevel
    location: CodeLocation
    entropy: float
    is_verified: bool = False
    secret_hash: str = ""  # SHA256 of secret for tracking
    remediation: str = ""


@dataclass
class IaCFinding:
    """Infrastructure-as-Code security finding."""

    resource_type: str
    resource_name: str
    provider: str  # aws, azure, gcp, kubernetes
    severity: SeverityLevel
    title: str
    description: str
    location: CodeLocation
    policy_id: str
    remediation: str
    compliance_frameworks: list[str] = field(default_factory=list)


@dataclass
class LicenseIssue:
    """License compliance issue."""

    package_name: str
    detected_license: str
    issue_type: str  # incompatible, unknown, copyleft_in_commercial
    severity: SeverityLevel
    description: str
    allowed_licenses: list[str] = field(default_factory=list)


@dataclass
class ScanConfiguration:
    """Configuration for a security scan."""

    enable_sast: bool = True
    enable_secrets: bool = True
    enable_sca: bool = True
    enable_iac: bool = True
    enable_license: bool = True
    severity_threshold: SeverityLevel = SeverityLevel.LOW
    fail_on_severity: SeverityLevel = SeverityLevel.HIGH
    ignore_paths: list[str] = field(default_factory=list)
    ignore_rules: list[str] = field(default_factory=list)
    custom_rules: list[dict] = field(default_factory=list)
    max_findings: int = 1000
    timeout_seconds: int = 600


@dataclass
class ScanResult:
    """Complete result of a PR security scan."""

    scan_id: str
    pr_metadata: PRMetadata
    status: ScanStatus
    findings: list[SecurityFinding]
    secret_findings: list[SecretFinding]
    dependency_findings: list[DependencyInfo]
    iac_findings: list[IaCFinding]
    license_issues: list[LicenseIssue]
    summary: "ScanSummary"
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float = 0.0
    error_message: str | None = None


@dataclass
class ScanSummary:
    """Summary statistics for a scan."""

    total_findings: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    info_count: int
    new_findings: int
    fixed_findings: int
    secrets_detected: int
    vulnerable_dependencies: int
    iac_issues: int
    license_issues: int
    files_scanned: int
    lines_scanned: int
    scan_passed: bool
    block_merge: bool
    risk_score: float  # 0-100


# =============================================================================
# Security Rule Engine
# =============================================================================


class SecurityRule:
    """Base class for security detection rules."""

    def __init__(
        self,
        rule_id: str,
        title: str,
        description: str,
        severity: SeverityLevel,
        category: FindingCategory,
        cwe_id: str | None = None,
        languages: list[str] | None = None,
    ):
        self.rule_id = rule_id
        self.title = title
        self.description = description
        self.severity = severity
        self.category = category
        self.cwe_id = cwe_id
        self.languages = languages or []

    def matches_language(self, file_path: str) -> bool:
        """Check if rule applies to file's language."""
        if not self.languages:
            return True

        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".jsx": "javascript",
            ".java": "java",
            ".go": "go",
            ".rb": "ruby",
            ".php": "php",
            ".cs": "csharp",
            ".cpp": "cpp",
            ".c": "c",
            ".rs": "rust",
        }

        ext = Path(file_path).suffix.lower()
        lang = ext_map.get(ext, "")
        return lang in self.languages or not self.languages


class RegexSecurityRule(SecurityRule):
    """Security rule using regex pattern matching."""

    def __init__(
        self,
        rule_id: str,
        title: str,
        description: str,
        severity: SeverityLevel,
        category: FindingCategory,
        pattern: str,
        cwe_id: str | None = None,
        languages: list[str] | None = None,
        remediation: str = "",
    ):
        super().__init__(
            rule_id, title, description, severity, category, cwe_id, languages
        )
        self.pattern = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
        self.remediation = remediation

    def scan(self, content: str, file_path: str) -> list[dict]:
        """Scan content for pattern matches."""
        if not self.matches_language(file_path):
            return []

        matches = []
        for match in self.pattern.finditer(content):
            line_num = content[: match.start()].count("\n") + 1
            matches.append(
                {
                    "rule_id": self.rule_id,
                    "line": line_num,
                    "match": match.group(),
                    "start": match.start(),
                    "end": match.end(),
                }
            )
        return matches


# =============================================================================
# Built-in Security Rules
# =============================================================================

OWASP_RULES = [
    # A01:2021 - Broken Access Control
    RegexSecurityRule(
        rule_id="OWASP-A01-001",
        title="Potential Path Traversal",
        description="Detected potential path traversal vulnerability allowing access to files outside intended directory",
        severity=SeverityLevel.HIGH,
        category=FindingCategory.VULNERABILITY,
        pattern=r"(\.\.\/|\.\.\\|%2e%2e%2f|%2e%2e\/|\.\.%2f|%2e%2e%5c)",
        cwe_id="CWE-22",
        remediation="Validate and sanitize file paths. Use allowlists for permitted directories.",
    ),
    RegexSecurityRule(
        rule_id="OWASP-A01-002",
        title="Insecure Direct Object Reference",
        description="User-controlled input directly used in database query or file access",
        severity=SeverityLevel.HIGH,
        category=FindingCategory.VULNERABILITY,
        pattern=r"(request\.(GET|POST|params)\[['\"]id['\"]\]|params\[:id\])",
        cwe_id="CWE-639",
        languages=["python", "ruby", "javascript"],
        remediation="Implement proper authorization checks before accessing resources.",
    ),
    # A02:2021 - Cryptographic Failures
    RegexSecurityRule(
        rule_id="OWASP-A02-001",
        title="Weak Cryptographic Algorithm",
        description="Use of weak or deprecated cryptographic algorithm (MD5, SHA1, DES)",
        severity=SeverityLevel.HIGH,
        category=FindingCategory.VULNERABILITY,
        pattern=r"(MD5|SHA1|DES|RC4|Blowfish)\s*\(",
        cwe_id="CWE-327",
        remediation="Use strong algorithms: SHA-256, SHA-3, AES-256-GCM",
    ),
    RegexSecurityRule(
        rule_id="OWASP-A02-002",
        title="Hardcoded Cryptographic Key",
        description="Cryptographic key appears to be hardcoded in source code",
        severity=SeverityLevel.CRITICAL,
        category=FindingCategory.SECRET,
        pattern=r"(encryption_key|secret_key|private_key|api_key)\s*=\s*['\"][a-zA-Z0-9+/=]{16,}['\"]",
        cwe_id="CWE-321",
        remediation="Store keys in secure key management systems (AWS KMS, HashiCorp Vault)",
    ),
    # A03:2021 - Injection
    RegexSecurityRule(
        rule_id="OWASP-A03-001",
        title="SQL Injection",
        description="Potential SQL injection via string concatenation or formatting",
        severity=SeverityLevel.CRITICAL,
        category=FindingCategory.VULNERABILITY,
        pattern=r"(execute|query|cursor\.execute)\s*\(\s*['\"].*%s.*['\"]|f['\"].*SELECT.*\{.*\}|\".*SELECT.*\"\s*\+",
        cwe_id="CWE-89",
        languages=["python", "javascript", "java"],
        remediation="Use parameterized queries or prepared statements",
    ),
    RegexSecurityRule(
        rule_id="OWASP-A03-002",
        title="Command Injection",
        description="Potential command injection via shell execution",
        severity=SeverityLevel.CRITICAL,
        category=FindingCategory.VULNERABILITY,
        pattern=r"(os\.system|subprocess\.call|subprocess\.Popen|exec\(|eval\(|child_process\.exec)\s*\([^)]*\+|shell=True",
        cwe_id="CWE-78",
        languages=["python", "javascript"],
        remediation="Avoid shell execution. Use subprocess with shell=False and argument lists.",
    ),
    RegexSecurityRule(
        rule_id="OWASP-A03-003",
        title="XSS Vulnerability",
        description="Potential Cross-Site Scripting via unsanitized output",
        severity=SeverityLevel.HIGH,
        category=FindingCategory.VULNERABILITY,
        pattern=r"(innerHTML|outerHTML|document\.write|v-html|dangerouslySetInnerHTML)\s*=",
        cwe_id="CWE-79",
        languages=["javascript", "typescript"],
        remediation="Use textContent instead of innerHTML. Sanitize user input with DOMPurify.",
    ),
    # A04:2021 - Insecure Design
    RegexSecurityRule(
        rule_id="OWASP-A04-001",
        title="Missing Rate Limiting",
        description="Authentication endpoint without apparent rate limiting",
        severity=SeverityLevel.MEDIUM,
        category=FindingCategory.VULNERABILITY,
        pattern=r"(@app\.route|@router\.(post|put)).*(/login|/auth|/signin|/register)",
        cwe_id="CWE-307",
        languages=["python"],
        remediation="Implement rate limiting on authentication endpoints",
    ),
    # A05:2021 - Security Misconfiguration
    RegexSecurityRule(
        rule_id="OWASP-A05-001",
        title="Debug Mode Enabled",
        description="Application appears to have debug mode enabled in production",
        severity=SeverityLevel.MEDIUM,
        category=FindingCategory.VULNERABILITY,
        pattern=r"(DEBUG\s*=\s*True|app\.debug\s*=\s*True|debug:\s*true)",
        cwe_id="CWE-489",
        remediation="Disable debug mode in production environments",
    ),
    RegexSecurityRule(
        rule_id="OWASP-A05-002",
        title="CORS Wildcard",
        description="CORS configured to allow all origins",
        severity=SeverityLevel.MEDIUM,
        category=FindingCategory.VULNERABILITY,
        pattern=r"(Access-Control-Allow-Origin|cors.*origin).*\*",
        cwe_id="CWE-942",
        remediation="Specify explicit allowed origins instead of wildcard",
    ),
    # A06:2021 - Vulnerable Components (handled by SCA)
    # A07:2021 - Authentication Failures
    RegexSecurityRule(
        rule_id="OWASP-A07-001",
        title="Weak Password Requirements",
        description="Password validation appears to have weak requirements",
        severity=SeverityLevel.MEDIUM,
        category=FindingCategory.VULNERABILITY,
        pattern=r"(password|pwd).*len.*[<>=]\s*[1-7][^0-9]|min.*length.*[1-7][^0-9]",
        cwe_id="CWE-521",
        remediation="Enforce minimum 12 character passwords with complexity requirements",
    ),
    # A08:2021 - Software and Data Integrity
    RegexSecurityRule(
        rule_id="OWASP-A08-001",
        title="Insecure Deserialization",
        description="Use of potentially unsafe deserialization",
        severity=SeverityLevel.HIGH,
        category=FindingCategory.VULNERABILITY,
        pattern=r"(pickle\.loads?|yaml\.load\(|Marshal\.load|unserialize\(|ObjectInputStream)",
        cwe_id="CWE-502",
        languages=["python", "ruby", "php", "java"],
        remediation="Use safe deserialization methods (yaml.safe_load, json) or validate input",
    ),
    # A09:2021 - Security Logging Failures
    RegexSecurityRule(
        rule_id="OWASP-A09-001",
        title="Sensitive Data in Logs",
        description="Potential logging of sensitive information",
        severity=SeverityLevel.MEDIUM,
        category=FindingCategory.VULNERABILITY,
        pattern=r"(log|logger|print|console\.log).*\(.*password|token|secret|key|credential|ssn|credit.?card",
        cwe_id="CWE-532",
        remediation="Redact sensitive data before logging",
    ),
    # A10:2021 - SSRF
    RegexSecurityRule(
        rule_id="OWASP-A10-001",
        title="Server-Side Request Forgery",
        description="URL from user input used in server-side request",
        severity=SeverityLevel.HIGH,
        category=FindingCategory.VULNERABILITY,
        pattern=r"(requests\.get|urllib\.request|fetch|http\.get)\s*\(\s*(request\.|params|user_input|url_param)",
        cwe_id="CWE-918",
        languages=["python", "javascript"],
        remediation="Validate and allowlist URLs. Use URL parsing to verify host.",
    ),
]

SECRET_PATTERNS = [
    RegexSecurityRule(
        rule_id="SECRET-001",
        title="AWS Access Key",
        description="AWS Access Key ID detected",
        severity=SeverityLevel.CRITICAL,
        category=FindingCategory.SECRET,
        pattern=r"AKIA[0-9A-Z]{16}",
        remediation="Rotate the key immediately and use IAM roles instead",
    ),
    RegexSecurityRule(
        rule_id="SECRET-002",
        title="AWS Secret Key",
        description="AWS Secret Access Key detected",
        severity=SeverityLevel.CRITICAL,
        category=FindingCategory.SECRET,
        pattern=r"(?<![A-Za-z0-9/+=])[A-Za-z0-9/+=]{40}(?![A-Za-z0-9/+=])",
        remediation="Rotate the key immediately and use IAM roles instead",
    ),
    RegexSecurityRule(
        rule_id="SECRET-003",
        title="GitHub Token",
        description="GitHub personal access token detected",
        severity=SeverityLevel.CRITICAL,
        category=FindingCategory.SECRET,
        pattern=r"ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}",
        remediation="Revoke token and generate a new one with minimal permissions",
    ),
    RegexSecurityRule(
        rule_id="SECRET-004",
        title="Generic API Key",
        description="Potential API key detected",
        severity=SeverityLevel.HIGH,
        category=FindingCategory.SECRET,
        pattern=r"(api[_-]?key|apikey|api[_-]?secret)\s*[:=]\s*['\"][a-zA-Z0-9]{20,}['\"]",
        remediation="Move API keys to environment variables or secrets manager",
    ),
    RegexSecurityRule(
        rule_id="SECRET-005",
        title="Private Key",
        description="Private key detected in source code",
        severity=SeverityLevel.CRITICAL,
        category=FindingCategory.SECRET,
        pattern=r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
        remediation="Remove private key and store in secure key management",
    ),
    RegexSecurityRule(
        rule_id="SECRET-006",
        title="JWT Secret",
        description="JWT signing secret detected",
        severity=SeverityLevel.CRITICAL,
        category=FindingCategory.SECRET,
        pattern=r"(jwt[_-]?secret|signing[_-]?key)\s*[:=]\s*['\"][^'\"]{10,}['\"]",
        remediation="Use asymmetric keys (RS256) or store secret in vault",
    ),
    RegexSecurityRule(
        rule_id="SECRET-007",
        title="Database Connection String",
        description="Database connection string with credentials",
        severity=SeverityLevel.CRITICAL,
        category=FindingCategory.SECRET,
        pattern=r"(mongodb|postgres|mysql|redis)://[^:]+:[^@]+@",
        remediation="Use connection pooling with credential-free connections or IAM auth",
    ),
    RegexSecurityRule(
        rule_id="SECRET-008",
        title="Slack Webhook",
        description="Slack webhook URL detected",
        severity=SeverityLevel.MEDIUM,
        category=FindingCategory.SECRET,
        pattern=r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[a-zA-Z0-9]+",
        remediation="Store webhook URL in environment variables",
    ),
]

IAC_RULES = [
    RegexSecurityRule(
        rule_id="IAC-AWS-001",
        title="S3 Bucket Public Access",
        description="S3 bucket configured with public access",
        severity=SeverityLevel.HIGH,
        category=FindingCategory.IAC_MISCONFIGURATION,
        pattern=r"(PublicRead|public-read|PublicReadWrite|public-read-write|acl.*public)",
        cwe_id="CWE-284",
        remediation="Use bucket policies with explicit principal restrictions",
    ),
    RegexSecurityRule(
        rule_id="IAC-AWS-002",
        title="Security Group Open to World",
        description="Security group allows traffic from 0.0.0.0/0",
        severity=SeverityLevel.HIGH,
        category=FindingCategory.IAC_MISCONFIGURATION,
        pattern=r"(cidr_blocks|CidrIp).*0\.0\.0\.0/0",
        cwe_id="CWE-284",
        remediation="Restrict CIDR blocks to specific IP ranges",
    ),
    RegexSecurityRule(
        rule_id="IAC-AWS-003",
        title="Unencrypted Storage",
        description="Storage resource without encryption enabled",
        severity=SeverityLevel.MEDIUM,
        category=FindingCategory.IAC_MISCONFIGURATION,
        pattern=r"(encrypted|encryption)\s*[:=]\s*(false|False|FALSE)",
        cwe_id="CWE-311",
        remediation="Enable encryption at rest for all storage resources",
    ),
    RegexSecurityRule(
        rule_id="IAC-AWS-004",
        title="IAM Policy Too Permissive",
        description="IAM policy with overly broad permissions",
        severity=SeverityLevel.HIGH,
        category=FindingCategory.IAC_MISCONFIGURATION,
        pattern=r"(\"Action\"|Action).*(\"\*\"|'\\*'|:\\s*\\*)",
        cwe_id="CWE-250",
        remediation="Follow least privilege principle with specific actions",
    ),
    RegexSecurityRule(
        rule_id="IAC-AWS-005",
        title="Missing CloudTrail Logging",
        description="AWS resource without CloudTrail logging",
        severity=SeverityLevel.MEDIUM,
        category=FindingCategory.IAC_MISCONFIGURATION,
        pattern=r"(enable_log|logging|log_).*false",
        cwe_id="CWE-778",
        remediation="Enable CloudTrail logging for audit compliance",
    ),
    RegexSecurityRule(
        rule_id="IAC-K8S-001",
        title="Container Running as Root",
        description="Kubernetes container configured to run as root",
        severity=SeverityLevel.HIGH,
        category=FindingCategory.IAC_MISCONFIGURATION,
        pattern=r"runAsUser:\s*0|runAsNonRoot:\s*false",
        cwe_id="CWE-250",
        remediation="Set runAsNonRoot: true and specify non-root runAsUser",
    ),
    RegexSecurityRule(
        rule_id="IAC-K8S-002",
        title="Privileged Container",
        description="Container running in privileged mode",
        severity=SeverityLevel.CRITICAL,
        category=FindingCategory.IAC_MISCONFIGURATION,
        pattern=r"privileged:\s*true",
        cwe_id="CWE-250",
        remediation="Remove privileged mode and use specific capabilities",
    ),
]


# =============================================================================
# PR Security Scanner Service
# =============================================================================


class PRSecurityScanner:
    """
    Comprehensive PR security scanning service.

    Provides multi-layered security analysis:
    - SAST (Static Application Security Testing)
    - Secret detection
    - SCA (Software Composition Analysis)
    - IaC security validation
    - License compliance
    """

    def __init__(
        self,
        neptune_client: Any = None,
        opensearch_client: Any = None,
        llm_client: Any = None,
        vuln_db_client: Any = None,
    ):
        self._neptune = neptune_client
        self._opensearch = opensearch_client
        self._llm = llm_client
        self._vuln_db = vuln_db_client

        # Initialize rule sets
        self._sast_rules = OWASP_RULES
        self._secret_rules = SECRET_PATTERNS
        self._iac_rules = IAC_RULES
        self._custom_rules: list[SecurityRule] = []

        # Scan history for baseline comparison
        self._scan_history: dict[str, list[ScanResult]] = {}

        # Allowed licenses (configurable)
        self._allowed_licenses = {
            "MIT",
            "Apache-2.0",
            "BSD-2-Clause",
            "BSD-3-Clause",
            "ISC",
            "Unlicense",
            "CC0-1.0",
            "0BSD",
        }

        self._logger = logger.bind(service="pr_security_scanner")

    # =========================================================================
    # Main Scan Interface
    # =========================================================================

    async def scan_pull_request(
        self,
        pr_metadata: PRMetadata,
        file_contents: dict[str, str],
        config: ScanConfiguration | None = None,
    ) -> ScanResult:
        """
        Perform comprehensive security scan on a pull request.

        Args:
            pr_metadata: Metadata about the PR
            file_contents: Dict mapping file paths to their content
            config: Scan configuration options

        Returns:
            Complete scan results
        """
        config = config or ScanConfiguration()
        scan_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)

        self._logger.info(
            "Starting PR security scan",
            scan_id=scan_id,
            pr_id=pr_metadata.pr_id,
            repository=pr_metadata.repository,
            files_count=len(file_contents),
        )

        findings: list[SecurityFinding] = []
        secret_findings: list[SecretFinding] = []
        dependency_findings: list[DependencyInfo] = []
        iac_findings: list[IaCFinding] = []
        license_issues: list[LicenseIssue] = []

        try:
            # Run scans in parallel
            tasks: list[Any] = []

            if config.enable_sast:
                tasks.append(self._run_sast_scan(file_contents, config))

            if config.enable_secrets:
                tasks.append(self._run_secret_scan(file_contents, config))

            if config.enable_sca:
                tasks.append(self._run_sca_scan(file_contents, config))

            if config.enable_iac:
                tasks.append(self._run_iac_scan(file_contents, config))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self._logger.error(f"Scan task {i} failed", error=str(result))
                    continue

                if isinstance(result, list):
                    for item in result:
                        if isinstance(item, SecurityFinding):
                            findings.append(item)
                        elif isinstance(item, SecretFinding):
                            secret_findings.append(item)
                        elif isinstance(item, DependencyInfo):
                            dependency_findings.append(item)
                        elif isinstance(item, IaCFinding):
                            iac_findings.append(item)

            # License compliance check
            if config.enable_license:
                license_issues = await self._check_license_compliance(
                    dependency_findings
                )

            # Filter by severity threshold
            findings = [
                f
                for f in findings
                if self._severity_meets_threshold(f.severity, config.severity_threshold)
            ]

            # Limit findings
            findings = findings[: config.max_findings]

            # Mark new vs existing findings
            await self._mark_new_findings(pr_metadata.repository, findings)

            completed_at = datetime.now(timezone.utc)

            # Generate summary
            summary = self._generate_summary(
                findings,
                secret_findings,
                dependency_findings,
                iac_findings,
                license_issues,
                file_contents,
                config,
            )

            scan_result = ScanResult(
                scan_id=scan_id,
                pr_metadata=pr_metadata,
                status=ScanStatus.COMPLETED,
                findings=findings,
                secret_findings=secret_findings,
                dependency_findings=dependency_findings,
                iac_findings=iac_findings,
                license_issues=license_issues,
                summary=summary,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=(completed_at - started_at).total_seconds(),
            )

            # Store in history
            if pr_metadata.repository not in self._scan_history:
                self._scan_history[pr_metadata.repository] = []
            self._scan_history[pr_metadata.repository].append(scan_result)

            self._logger.info(
                "PR security scan completed",
                scan_id=scan_id,
                total_findings=summary.total_findings,
                critical=summary.critical_count,
                high=summary.high_count,
                scan_passed=summary.scan_passed,
                duration_s=scan_result.duration_seconds,
            )

            return scan_result

        except Exception as e:
            self._logger.error("Scan failed", scan_id=scan_id, error=str(e))
            return ScanResult(
                scan_id=scan_id,
                pr_metadata=pr_metadata,
                status=ScanStatus.FAILED,
                findings=[],
                secret_findings=[],
                dependency_findings=[],
                iac_findings=[],
                license_issues=[],
                summary=ScanSummary(
                    total_findings=0,
                    critical_count=0,
                    high_count=0,
                    medium_count=0,
                    low_count=0,
                    info_count=0,
                    new_findings=0,
                    fixed_findings=0,
                    secrets_detected=0,
                    vulnerable_dependencies=0,
                    iac_issues=0,
                    license_issues=0,
                    files_scanned=0,
                    lines_scanned=0,
                    scan_passed=False,
                    block_merge=True,
                    risk_score=100.0,
                ),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                error_message=str(e),
            )

    # =========================================================================
    # SAST Scanning
    # =========================================================================

    async def _run_sast_scan(
        self, file_contents: dict[str, str], config: ScanConfiguration
    ) -> list[SecurityFinding]:
        """Run static application security testing."""
        findings = []
        all_rules = self._sast_rules + self._custom_rules

        for file_path, content in file_contents.items():
            # Skip ignored paths
            if any(ignored in file_path for ignored in config.ignore_paths):
                continue

            for rule in all_rules:
                if rule.rule_id in config.ignore_rules:
                    continue

                if isinstance(rule, RegexSecurityRule):
                    matches = rule.scan(content, file_path)

                    for match in matches:
                        # Get code snippet
                        lines = content.split("\n")
                        line_idx = match["line"] - 1
                        snippet = lines[line_idx] if line_idx < len(lines) else ""

                        # Get context
                        context_before = "\n".join(
                            lines[max(0, line_idx - 2) : line_idx]
                        )
                        context_after = "\n".join(
                            lines[line_idx + 1 : min(len(lines), line_idx + 3)]
                        )

                        location = CodeLocation(
                            file_path=file_path,
                            start_line=match["line"],
                            end_line=match["line"],
                            snippet=snippet.strip(),
                            context_before=context_before,
                            context_after=context_after,
                        )

                        # Build CWE reference if available
                        cwe = None
                        if rule.cwe_id:
                            cwe = CWEReference(
                                cwe_id=rule.cwe_id,
                                name=rule.title,
                                description=rule.description,
                                url=f"https://cwe.mitre.org/data/definitions/{rule.cwe_id.replace('CWE-', '')}.html",
                            )

                        # Build remediation
                        remediation = Remediation(
                            status=RemediationStatus.AVAILABLE,
                            description=(
                                rule.remediation if hasattr(rule, "remediation") else ""
                            ),
                            suggested_fix=None,
                        )

                        findings.append(
                            SecurityFinding(
                                finding_id=str(uuid.uuid4()),
                                category=rule.category,
                                severity=rule.severity,
                                title=rule.title,
                                description=rule.description,
                                location=location,
                                cwe=cwe,
                                remediation=remediation,
                                rule_id=rule.rule_id,
                                confidence=0.85,
                                tags=[rule.rule_id.split("-")[0]],
                            )
                        )

        return findings

    # =========================================================================
    # Secret Scanning
    # =========================================================================

    async def _run_secret_scan(
        self, file_contents: dict[str, str], config: ScanConfiguration
    ) -> list[SecretFinding]:
        """Scan for secrets and credentials."""
        findings = []

        for file_path, content in file_contents.items():
            # Skip binary files and common non-secret files
            if self._should_skip_secret_scan(file_path):
                continue

            for rule in self._secret_rules:
                if rule.rule_id in config.ignore_rules:
                    continue

                if isinstance(rule, RegexSecurityRule):
                    matches = rule.scan(content, file_path)

                    for match in matches:
                        lines = content.split("\n")
                        line_idx = match["line"] - 1
                        snippet = lines[line_idx] if line_idx < len(lines) else ""

                        # Calculate entropy for confidence
                        entropy = self._calculate_entropy(match["match"])

                        # Hash the secret for tracking
                        secret_hash = hashlib.sha256(
                            match["match"].encode()
                        ).hexdigest()[:16]

                        location = CodeLocation(
                            file_path=file_path,
                            start_line=match["line"],
                            end_line=match["line"],
                            snippet=self._redact_secret(snippet),
                        )

                        findings.append(
                            SecretFinding(
                                secret_type=rule.title,
                                severity=rule.severity,
                                location=location,
                                entropy=entropy,
                                is_verified=False,
                                secret_hash=secret_hash,
                                remediation=(
                                    rule.remediation
                                    if hasattr(rule, "remediation")
                                    else ""
                                ),
                            )
                        )

        return findings

    def _should_skip_secret_scan(self, file_path: str) -> bool:
        """Check if file should be skipped for secret scanning."""
        skip_extensions = {
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".ico",
            ".svg",
            ".woff",
            ".woff2",
            ".ttf",
            ".eot",
            ".pdf",
            ".zip",
        }
        skip_dirs = {"node_modules", "vendor", ".git", "__pycache__", "dist", "build"}

        path = Path(file_path)
        if path.suffix.lower() in skip_extensions:
            return True
        if any(skip_dir in path.parts for skip_dir in skip_dirs):
            return True
        return False

    def _calculate_entropy(self, text: str) -> float:
        """Calculate Shannon entropy of text."""
        import math

        if not text:
            return 0.0

        prob = [float(text.count(c)) / len(text) for c in set(text)]
        entropy = -sum(p * math.log2(p) for p in prob if p > 0)
        return entropy

    def _redact_secret(self, text: str) -> str:
        """Redact potential secrets from display."""
        # Simple redaction - show first 4 and last 4 chars
        for rule in self._secret_rules:
            if isinstance(rule, RegexSecurityRule):
                text = rule.pattern.sub(
                    lambda m: m.group()[:4] + "****" + m.group()[-4:], text
                )
        return text

    # =========================================================================
    # Software Composition Analysis
    # =========================================================================

    async def _run_sca_scan(
        self, file_contents: dict[str, str], config: ScanConfiguration
    ) -> list[DependencyInfo]:
        """Scan dependencies for vulnerabilities."""
        dependencies = []

        # Parse dependency files
        for file_path, content in file_contents.items():
            parsed = await self._parse_dependency_file(file_path, content)
            dependencies.extend(parsed)

        # Enrich with vulnerability data
        for dep in dependencies:
            vulns = await self._lookup_vulnerabilities(
                dep.name, dep.version, dep.ecosystem
            )
            dep.vulnerabilities = vulns

        return dependencies

    async def _parse_dependency_file(
        self, file_path: str, content: str
    ) -> list[DependencyInfo]:
        """Parse dependency information from manifest files."""
        dependencies = []
        file_name = Path(file_path).name.lower()

        try:
            if file_name == "package.json":
                dependencies = self._parse_package_json(content)
            elif file_name == "requirements.txt":
                dependencies = self._parse_requirements_txt(content)
            elif file_name == "pyproject.toml":
                dependencies = self._parse_pyproject_toml(content)
            elif file_name == "go.mod":
                dependencies = self._parse_go_mod(content)
            elif file_name == "pom.xml":
                dependencies = self._parse_pom_xml(content)
            elif file_name == "gemfile" or file_name == "gemfile.lock":
                dependencies = self._parse_gemfile(content)
        except Exception as e:
            self._logger.warning(f"Failed to parse {file_path}", error=str(e))

        return dependencies

    def _parse_package_json(self, content: str) -> list[DependencyInfo]:
        """Parse npm package.json."""
        deps = []
        try:
            data = json.loads(content)

            for name, version in data.get("dependencies", {}).items():
                deps.append(
                    DependencyInfo(
                        name=name,
                        version=version.lstrip("^~>=<"),
                        ecosystem="npm",
                        is_direct=True,
                        is_dev=False,
                    )
                )

            for name, version in data.get("devDependencies", {}).items():
                deps.append(
                    DependencyInfo(
                        name=name,
                        version=version.lstrip("^~>=<"),
                        ecosystem="npm",
                        is_direct=True,
                        is_dev=True,
                    )
                )
        except json.JSONDecodeError:
            pass
        return deps

    def _parse_requirements_txt(self, content: str) -> list[DependencyInfo]:
        """Parse Python requirements.txt."""
        deps = []
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue

            # Parse package==version or package>=version etc.
            match = re.match(
                r"^([a-zA-Z0-9_-]+)\s*([=<>!~]+)?\s*([0-9a-zA-Z._-]+)?", line
            )
            if match:
                deps.append(
                    DependencyInfo(
                        name=match.group(1),
                        version=match.group(3) or "unknown",
                        ecosystem="pip",
                        is_direct=True,
                    )
                )
        return deps

    def _parse_pyproject_toml(self, content: str) -> list[DependencyInfo]:
        """Parse Python pyproject.toml."""
        deps = []
        # Simple regex parsing - production would use toml parser
        in_deps = False
        for line in content.split("\n"):
            if "[project.dependencies]" in line or "[tool.poetry.dependencies]" in line:
                in_deps = True
                continue
            if in_deps and line.startswith("["):
                in_deps = False
            if in_deps:
                match = re.match(r'^([a-zA-Z0-9_-]+)\s*=\s*["\']?([^"\']+)', line)
                if match:
                    deps.append(
                        DependencyInfo(
                            name=match.group(1),
                            version=match.group(2),
                            ecosystem="pip",
                            is_direct=True,
                        )
                    )
        return deps

    def _parse_go_mod(self, content: str) -> list[DependencyInfo]:
        """Parse Go go.mod."""
        deps = []
        for line in content.split("\n"):
            match = re.match(r"^\s*([a-zA-Z0-9./_-]+)\s+(v[0-9.]+)", line)
            if match:
                deps.append(
                    DependencyInfo(
                        name=match.group(1),
                        version=match.group(2),
                        ecosystem="go",
                        is_direct=True,
                    )
                )
        return deps

    def _parse_pom_xml(self, content: str) -> list[DependencyInfo]:
        """Parse Maven pom.xml."""
        deps = []
        # Simple regex - production would use XML parser
        dep_pattern = r"<dependency>.*?<groupId>([^<]+)</groupId>.*?<artifactId>([^<]+)</artifactId>.*?<version>([^<]+)</version>.*?</dependency>"
        for match in re.finditer(dep_pattern, content, re.DOTALL):
            deps.append(
                DependencyInfo(
                    name=f"{match.group(1)}:{match.group(2)}",
                    version=match.group(3),
                    ecosystem="maven",
                    is_direct=True,
                )
            )
        return deps

    def _parse_gemfile(self, content: str) -> list[DependencyInfo]:
        """Parse Ruby Gemfile."""
        deps = []
        for line in content.split("\n"):
            match = re.match(
                r"^\s*gem\s+['\"]([^'\"]+)['\"](?:,\s*['\"]([^'\"]+)['\"])?", line
            )
            if match:
                deps.append(
                    DependencyInfo(
                        name=match.group(1),
                        version=match.group(2) or "unknown",
                        ecosystem="rubygems",
                        is_direct=True,
                    )
                )
        return deps

    async def _lookup_vulnerabilities(
        self, package: str, version: str, ecosystem: str
    ) -> list[DependencyVulnerability]:
        """Look up known vulnerabilities for a package."""
        # In production, query OSV, NVD, or Snyk API
        # For now, return simulated data for known vulnerable packages
        vulns: list[DependencyVulnerability] = []

        # Simulated vulnerable packages
        known_vulns = {
            ("lodash", "npm"): [
                DependencyVulnerability(
                    vuln_id="CVE-2021-23337",
                    severity=SeverityLevel.HIGH,
                    title="Prototype Pollution in lodash",
                    description="Lodash before 4.17.21 is vulnerable to Command Injection via template function",
                    fixed_version="4.17.21",
                    cvss_score=7.2,
                )
            ],
            ("requests", "pip"): [
                DependencyVulnerability(
                    vuln_id="CVE-2023-32681",
                    severity=SeverityLevel.MEDIUM,
                    title="Unintended leak of Proxy-Authorization header",
                    description="Requests before 2.31.0 could leak credentials in redirects",
                    fixed_version="2.31.0",
                    cvss_score=6.1,
                )
            ],
        }

        if (package, ecosystem) in known_vulns:
            return known_vulns[(package, ecosystem)]

        return vulns

    # =========================================================================
    # IaC Scanning
    # =========================================================================

    async def _run_iac_scan(
        self, file_contents: dict[str, str], config: ScanConfiguration
    ) -> list[IaCFinding]:
        """Scan Infrastructure-as-Code files."""
        findings = []

        iac_extensions = {".tf", ".yaml", ".yml", ".json", ".template"}

        for file_path, content in file_contents.items():
            path = Path(file_path)
            if path.suffix.lower() not in iac_extensions:
                continue

            # Determine provider
            provider = self._detect_iac_provider(file_path, content)

            for rule in self._iac_rules:
                if rule.rule_id in config.ignore_rules:
                    continue

                if isinstance(rule, RegexSecurityRule):
                    matches = rule.scan(content, file_path)

                    for match in matches:
                        lines = content.split("\n")
                        line_idx = match["line"] - 1
                        snippet = lines[line_idx] if line_idx < len(lines) else ""

                        # Extract resource info
                        resource_type, resource_name = self._extract_resource_info(
                            content, match["line"]
                        )

                        location = CodeLocation(
                            file_path=file_path,
                            start_line=match["line"],
                            end_line=match["line"],
                            snippet=snippet.strip(),
                        )

                        findings.append(
                            IaCFinding(
                                resource_type=resource_type,
                                resource_name=resource_name,
                                provider=provider,
                                severity=rule.severity,
                                title=rule.title,
                                description=rule.description,
                                location=location,
                                policy_id=rule.rule_id,
                                remediation=(
                                    rule.remediation
                                    if hasattr(rule, "remediation")
                                    else ""
                                ),
                                compliance_frameworks=self._get_compliance_frameworks(
                                    rule.rule_id
                                ),
                            )
                        )

        return findings

    def _detect_iac_provider(self, file_path: str, content: str) -> str:
        """Detect IaC provider from file content."""
        if ".tf" in file_path:
            if 'provider "aws"' in content or "aws_" in content:
                return "aws"
            elif 'provider "azurerm"' in content:
                return "azure"
            elif 'provider "google"' in content:
                return "gcp"
        if "apiVersion" in content and "kind" in content:
            return "kubernetes"
        if "AWSTemplateFormatVersion" in content:
            return "cloudformation"
        return "unknown"

    def _extract_resource_info(self, content: str, line_num: int) -> tuple[str, str]:
        """Extract resource type and name from IaC content."""
        lines = content.split("\n")

        # Look backwards for resource definition
        for i in range(line_num - 1, max(0, line_num - 20), -1):
            line = lines[i]
            # Terraform resource
            tf_match = re.match(r'resource\s+"([^"]+)"\s+"([^"]+)"', line)
            if tf_match:
                return tf_match.group(1), tf_match.group(2)
            # Kubernetes kind
            k8s_match = re.match(r"kind:\s*(\w+)", line)
            if k8s_match:
                return k8s_match.group(1), "unnamed"

        return "unknown", "unnamed"

    def _get_compliance_frameworks(self, rule_id: str) -> list[str]:
        """Map rule to compliance frameworks."""
        framework_map = {
            "IAC-AWS-001": ["CIS AWS", "SOC2", "PCI-DSS"],
            "IAC-AWS-002": ["CIS AWS", "NIST 800-53", "FedRAMP"],
            "IAC-AWS-003": ["HIPAA", "PCI-DSS", "SOC2"],
            "IAC-AWS-004": ["CIS AWS", "SOC2", "NIST 800-53"],
            "IAC-K8S-001": ["CIS Kubernetes", "NSA CISA"],
            "IAC-K8S-002": ["CIS Kubernetes", "NSA CISA", "PCI-DSS"],
        }
        return framework_map.get(rule_id, [])

    # =========================================================================
    # License Compliance
    # =========================================================================

    async def _check_license_compliance(
        self, dependencies: list[DependencyInfo]
    ) -> list[LicenseIssue]:
        """Check dependencies for license compliance issues."""
        issues = []

        copyleft_licenses = {"GPL-2.0", "GPL-3.0", "LGPL-2.1", "LGPL-3.0", "AGPL-3.0"}

        for dep in dependencies:
            if not dep.license:
                issues.append(
                    LicenseIssue(
                        package_name=dep.name,
                        detected_license="Unknown",
                        issue_type="unknown",
                        severity=SeverityLevel.MEDIUM,
                        description=f"License information not found for {dep.name}",
                        allowed_licenses=list(self._allowed_licenses),
                    )
                )
            elif dep.license not in self._allowed_licenses:
                if dep.license in copyleft_licenses:
                    issues.append(
                        LicenseIssue(
                            package_name=dep.name,
                            detected_license=dep.license,
                            issue_type="copyleft_in_commercial",
                            severity=SeverityLevel.HIGH,
                            description=f"{dep.name} uses copyleft license {dep.license} which may require source disclosure",
                            allowed_licenses=list(self._allowed_licenses),
                        )
                    )
                else:
                    issues.append(
                        LicenseIssue(
                            package_name=dep.name,
                            detected_license=dep.license,
                            issue_type="incompatible",
                            severity=SeverityLevel.MEDIUM,
                            description=f"{dep.name} uses license {dep.license} not in allowed list",
                            allowed_licenses=list(self._allowed_licenses),
                        )
                    )

        return issues

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def _severity_meets_threshold(
        self, severity: SeverityLevel, threshold: SeverityLevel
    ) -> bool:
        """Check if severity meets or exceeds threshold."""
        severity_order = {
            SeverityLevel.INFO: 0,
            SeverityLevel.LOW: 1,
            SeverityLevel.MEDIUM: 2,
            SeverityLevel.HIGH: 3,
            SeverityLevel.CRITICAL: 4,
        }
        return severity_order[severity] >= severity_order[threshold]

    async def _mark_new_findings(
        self, repository: str, findings: list[SecurityFinding]
    ) -> None:
        """Mark findings as new or existing based on history."""
        if repository not in self._scan_history or not self._scan_history[repository]:
            return

        # Get fingerprints from previous scans
        previous_fingerprints = set()
        for scan in self._scan_history[repository][-5:]:  # Last 5 scans
            for f in scan.findings:
                fingerprint = (
                    f"{f.rule_id}:{f.location.file_path}:{f.location.start_line}"
                )
                previous_fingerprints.add(fingerprint)

        # Mark new findings
        for finding in findings:
            fingerprint = f"{finding.rule_id}:{finding.location.file_path}:{finding.location.start_line}"
            finding.is_new = fingerprint not in previous_fingerprints

    def _generate_summary(
        self,
        findings: list[SecurityFinding],
        secrets: list[SecretFinding],
        dependencies: list[DependencyInfo],
        iac_findings: list[IaCFinding],
        license_issues: list[LicenseIssue],
        file_contents: dict[str, str],
        config: ScanConfiguration,
    ) -> ScanSummary:
        """Generate scan summary statistics."""
        # Count by severity
        severity_counts = dict.fromkeys(SeverityLevel, 0)
        for f in findings:
            severity_counts[f.severity] += 1
        for s in secrets:
            severity_counts[s.severity] += 1
        for i in iac_findings:
            severity_counts[i.severity] += 1

        # Count vulnerable dependencies
        vuln_deps = sum(1 for d in dependencies if d.vulnerabilities)

        # Count new findings
        new_count = sum(1 for f in findings if f.is_new)

        # Calculate risk score (0-100)
        risk_score = min(
            100.0,
            (
                severity_counts[SeverityLevel.CRITICAL] * 25
                + severity_counts[SeverityLevel.HIGH] * 10
                + severity_counts[SeverityLevel.MEDIUM] * 3
                + severity_counts[SeverityLevel.LOW] * 1
                + len(secrets) * 15
                + vuln_deps * 5
            ),
        )

        # Calculate lines scanned
        lines_scanned = sum(
            content.count("\n") + 1 for content in file_contents.values()
        )

        # Determine if scan passes
        fail_severity_order = {
            SeverityLevel.INFO: 0,
            SeverityLevel.LOW: 1,
            SeverityLevel.MEDIUM: 2,
            SeverityLevel.HIGH: 3,
            SeverityLevel.CRITICAL: 4,
        }

        blocking_count = sum(
            1
            for f in findings
            if fail_severity_order[f.severity]
            >= fail_severity_order[config.fail_on_severity]
        )
        blocking_count += len(secrets)  # All secrets block

        scan_passed = blocking_count == 0
        block_merge = not scan_passed

        return ScanSummary(
            total_findings=len(findings) + len(secrets) + len(iac_findings),
            critical_count=severity_counts[SeverityLevel.CRITICAL],
            high_count=severity_counts[SeverityLevel.HIGH],
            medium_count=severity_counts[SeverityLevel.MEDIUM],
            low_count=severity_counts[SeverityLevel.LOW],
            info_count=severity_counts[SeverityLevel.INFO],
            new_findings=new_count,
            fixed_findings=0,  # Would require baseline comparison
            secrets_detected=len(secrets),
            vulnerable_dependencies=vuln_deps,
            iac_issues=len(iac_findings),
            license_issues=len(license_issues),
            files_scanned=len(file_contents),
            lines_scanned=lines_scanned,
            scan_passed=scan_passed,
            block_merge=block_merge,
            risk_score=risk_score,
        )

    # =========================================================================
    # Custom Rules Management
    # =========================================================================

    def add_custom_rule(self, rule: SecurityRule) -> None:
        """Add a custom security rule."""
        self._custom_rules.append(rule)
        self._logger.info("Added custom rule", rule_id=rule.rule_id)

    def set_allowed_licenses(self, licenses: set[str]) -> None:
        """Set allowed licenses for compliance checking."""
        self._allowed_licenses = licenses

    # =========================================================================
    # Report Generation
    # =========================================================================

    def generate_pr_comment(self, result: ScanResult) -> str:
        """Generate a PR comment summarizing scan results."""
        summary = result.summary

        # Status emoji
        if summary.scan_passed:
            status = "## :white_check_mark: Security Scan Passed"
        else:
            status = "## :x: Security Scan Failed"

        lines = [
            status,
            "",
            f"**Risk Score:** {summary.risk_score:.0f}/100",
            "",
            "### Summary",
            "| Category | Count |",
            "|----------|-------|",
            f"| :red_circle: Critical | {summary.critical_count} |",
            f"| :orange_circle: High | {summary.high_count} |",
            f"| :yellow_circle: Medium | {summary.medium_count} |",
            f"| :green_circle: Low | {summary.low_count} |",
            f"| :lock: Secrets | {summary.secrets_detected} |",
            f"| :package: Vulnerable Dependencies | {summary.vulnerable_dependencies} |",
            f"| :cloud: IaC Issues | {summary.iac_issues} |",
            "",
            f"**Files Scanned:** {summary.files_scanned}",
            f"**Lines Scanned:** {summary.lines_scanned:,}",
            f"**New Issues:** {summary.new_findings}",
            "",
        ]

        # Top findings
        if result.findings:
            lines.extend(["### Top Findings", ""])

            for finding in sorted(result.findings, key=lambda f: f.severity.value)[:5]:
                lines.append(
                    f"- **[{finding.severity.value.upper()}]** {finding.title} "
                    f"in `{finding.location.file_path}:{finding.location.start_line}`"
                )

        # Secrets warning
        if result.secret_findings:
            lines.extend(
                [
                    "",
                    "### :warning: Secrets Detected",
                    "",
                    "The following potential secrets were found:",
                    "",
                ]
            )
            for secret in result.secret_findings[:5]:
                lines.append(
                    f"- **{secret.secret_type}** in `{secret.location.file_path}:{secret.location.start_line}`"
                )

        # Block merge warning
        if summary.block_merge:
            lines.extend(
                [
                    "",
                    "---",
                    ":no_entry: **This PR is blocked from merging due to security findings.**",
                    "",
                    "Please address the critical and high severity issues before merging.",
                ]
            )

        return "\n".join(lines)

    def generate_sarif_report(self, result: ScanResult) -> dict:
        """Generate SARIF format report for GitHub Security tab."""
        return {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "Aura PR Security Scanner",
                            "version": "1.0.0",
                            "rules": [
                                {
                                    "id": f.rule_id,
                                    "name": f.title,
                                    "shortDescription": {"text": f.title},
                                    "fullDescription": {"text": f.description},
                                    "defaultConfiguration": {
                                        "level": self._severity_to_sarif_level(
                                            f.severity
                                        )
                                    },
                                }
                                for f in result.findings
                            ],
                        }
                    },
                    "results": [
                        {
                            "ruleId": f.rule_id,
                            "level": self._severity_to_sarif_level(f.severity),
                            "message": {"text": f.description},
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {
                                            "uri": f.location.file_path
                                        },
                                        "region": {
                                            "startLine": f.location.start_line,
                                            "endLine": f.location.end_line,
                                        },
                                    }
                                }
                            ],
                        }
                        for f in result.findings
                    ],
                }
            ],
        }

    def _severity_to_sarif_level(self, severity: SeverityLevel) -> str:
        """Convert severity to SARIF level."""
        mapping = {
            SeverityLevel.CRITICAL: "error",
            SeverityLevel.HIGH: "error",
            SeverityLevel.MEDIUM: "warning",
            SeverityLevel.LOW: "note",
            SeverityLevel.INFO: "note",
        }
        return mapping.get(severity, "note")
