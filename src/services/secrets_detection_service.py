"""
Project Aura - Secrets Detection Service

Detects potential secrets, API keys, and sensitive data in code and text.
Supports compliance with CMMC, SOC2, and data protection requirements.

Author: Project Aura Team
Created: 2025-12-12
"""

import hashlib
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SecretType(Enum):
    """Types of secrets that can be detected."""

    # Cloud Provider Keys
    AWS_ACCESS_KEY = "aws_access_key"
    AWS_SECRET_KEY = "aws_secret_key"
    AWS_SESSION_TOKEN = "aws_session_token"
    AZURE_CLIENT_SECRET = "azure_client_secret"
    GCP_API_KEY = "gcp_api_key"
    GCP_SERVICE_ACCOUNT = "gcp_service_account"

    # API Keys
    GENERIC_API_KEY = "generic_api_key"
    OPENAI_API_KEY = "openai_api_key"
    ANTHROPIC_API_KEY = "anthropic_api_key"
    GITHUB_TOKEN = "github_token"
    GITHUB_PAT = "github_pat"
    GITLAB_TOKEN = "gitlab_token"
    SLACK_TOKEN = "slack_token"
    SLACK_WEBHOOK = "slack_webhook"
    STRIPE_KEY = "stripe_key"
    SENDGRID_API_KEY = "sendgrid_api_key"
    TWILIO_API_KEY = "twilio_api_key"
    MAILGUN_API_KEY = "mailgun_api_key"

    # Authentication Tokens
    JWT_TOKEN = "jwt_token"
    BEARER_TOKEN = "bearer_token"
    OAUTH_TOKEN = "oauth_token"

    # Cryptographic Material
    PRIVATE_KEY = "private_key"
    RSA_PRIVATE_KEY = "rsa_private_key"
    SSH_PRIVATE_KEY = "ssh_private_key"
    PGP_PRIVATE_KEY = "pgp_private_key"
    ENCRYPTION_KEY = "encryption_key"

    # Database Credentials
    DATABASE_URL = "database_url"
    MONGODB_URI = "mongodb_uri"
    POSTGRES_PASSWORD = "postgres_password"
    MYSQL_PASSWORD = "mysql_password"
    REDIS_PASSWORD = "redis_password"

    # Generic Secrets
    PASSWORD = "password"
    SECRET = "secret"
    CREDENTIAL = "credential"
    CONNECTION_STRING = "connection_string"

    # Infrastructure
    NPM_TOKEN = "npm_token"
    PYPI_TOKEN = "pypi_token"
    DOCKER_AUTH = "docker_auth"
    KUBERNETES_SECRET = "kubernetes_secret"

    # Other
    BASIC_AUTH = "basic_auth"
    HIGH_ENTROPY_STRING = "high_entropy_string"


class SecretSeverity(Enum):
    """Severity levels for detected secrets."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecretFinding:
    """Represents a detected secret."""

    secret_type: SecretType
    severity: SecretSeverity
    line_number: int | None
    column: int | None
    matched_pattern: str
    redacted_value: str
    context: str
    file_path: str | None = None
    recommendation: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert finding to dictionary."""
        return {
            "secret_type": self.secret_type.value,
            "severity": self.severity.value,
            "line_number": self.line_number,
            "column": self.column,
            "matched_pattern": self.matched_pattern,
            "redacted_value": self.redacted_value,
            "context": self.context,
            "file_path": self.file_path,
            "recommendation": self.recommendation,
        }


@dataclass
class ScanResult:
    """Result of a secrets scan."""

    has_secrets: bool
    findings: list[SecretFinding]
    scanned_lines: int
    scan_time_ms: float = 0.0
    file_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "has_secrets": self.has_secrets,
            "findings": [f.to_dict() for f in self.findings],
            "scanned_lines": self.scanned_lines,
            "scan_time_ms": self.scan_time_ms,
            "file_path": self.file_path,
            "summary": {
                "total_findings": len(self.findings),
                "by_severity": self._count_by_severity(),
                "by_type": self._count_by_type(),
            },
        }

    def _count_by_severity(self) -> dict[str, int]:
        """Count findings by severity."""
        counts: dict[str, int] = {}
        for finding in self.findings:
            key = finding.severity.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    def _count_by_type(self) -> dict[str, int]:
        """Count findings by type."""
        counts: dict[str, int] = {}
        for finding in self.findings:
            key = finding.secret_type.value
            counts[key] = counts.get(key, 0) + 1
        return counts


@dataclass
class SecretPattern:
    """Pattern for detecting a specific type of secret."""

    pattern: re.Pattern[str]
    secret_type: SecretType
    severity: SecretSeverity
    description: str
    recommendation: str = ""


class SecretsDetectionService:
    """
    Service for detecting secrets and sensitive data.

    Features:
    - Pattern-based detection for known secret formats
    - Entropy-based detection for random strings
    - Context-aware analysis
    - Configurable sensitivity levels
    """

    # Characters used for entropy calculation
    ENTROPY_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

    # Minimum entropy threshold for high-entropy string detection
    MIN_ENTROPY_THRESHOLD = 4.5

    # Common false positive patterns to exclude
    # See docs/reference/PRE_COMMIT_FALSE_POSITIVES.md for pattern documentation
    FALSE_POSITIVE_PATTERNS = [
        # Placeholder patterns
        r"example\.com",
        r"placeholder",
        r"your[_-]?(api[_-]?key|secret|password|token)",
        r"xxx+",
        r"\*\*\*+",
        r"CHANGE_?ME",
        r"TODO",
        r"FIXME",
        # Test/mock patterns
        r"test[_-]?(key|secret|password|token)",
        r"dummy[_-]?(key|secret|password|token)",
        r"fake[_-]?(key|secret|password|token)",
        r"sample[_-]?(key|secret|password|token)",
        r"mock[_-]?(key|secret|password|token)",
        # Template/interpolation patterns
        r"<[^>]+>",  # HTML/XML tags
        r"\$\{[^}]+\}",  # Variable interpolation
        r"\{\{[^}]+\}\}",  # Template variables
        r"\{[a-zA-Z_][a-zA-Z0-9_]*\}",  # Python format strings
        # React/UI form field patterns (UI labels, not secrets)
        # Matches patterns like: name="password", label="Password", placeholder="Enter password"
        r'(?:name|label|placeholder|id|htmlFor|aria-label)\s*=\s*["\'][^"\']*(?:password|secret|token|key)[^"\']*["\']',
        # Matches JSX component names like setPassword, handlePasswordChange (camelCase)
        r"(?:set|handle|on|get|validate|check|update|confirm)[A-Z][a-zA-Z]*(?:Password|Secret|Token|Key)",
        # Form field type declarations
        r'type\s*=\s*["\']password["\']',
        # Input field names in forms
        r"(?:input|field|form)\s*[{(].*(?:password|secret)",
        # Schema/configuration key names (not values)
        r'"(?:password|secret|token|key)":\s*(?:null|undefined|""|\{\})',
        r"(?:password|secret|token|key)_?(?:field|name|label|key|type)",
    ]

    def __init__(
        self,
        entropy_threshold: float = 4.5,
        min_secret_length: int = 8,
        max_line_length: int = 1000,
        enable_entropy_detection: bool = True,
        log_findings: bool = True,
    ):
        """
        Initialize secrets detection service.

        Args:
            entropy_threshold: Minimum entropy for high-entropy detection
            min_secret_length: Minimum length for potential secrets
            max_line_length: Maximum line length to scan (performance)
            enable_entropy_detection: Enable entropy-based detection
            log_findings: Log findings to logger
        """
        self.entropy_threshold = entropy_threshold
        self.min_secret_length = min_secret_length
        self.max_line_length = max_line_length
        self.enable_entropy_detection = enable_entropy_detection
        self.log_findings = log_findings

        # Compile patterns
        self._patterns = self._build_patterns()
        self._false_positive_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.FALSE_POSITIVE_PATTERNS
        ]

        # Statistics
        self._stats: dict[str, Any] = {
            "total_scans": 0,
            "total_findings": 0,
            "by_type": {},
        }

    def _build_patterns(self) -> list[SecretPattern]:
        """Build list of secret detection patterns."""
        return [
            # AWS Credentials
            SecretPattern(
                pattern=re.compile(r"AKIA[0-9A-Z]{16}"),
                secret_type=SecretType.AWS_ACCESS_KEY,
                severity=SecretSeverity.CRITICAL,
                description="AWS Access Key ID",
                recommendation="Rotate the AWS access key immediately via IAM console",
            ),
            SecretPattern(
                pattern=re.compile(
                    r"(?i)(aws[_-]?secret[_-]?access[_-]?key|aws[_-]?secret[_-]?key)"
                    r"['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?"
                ),
                secret_type=SecretType.AWS_SECRET_KEY,
                severity=SecretSeverity.CRITICAL,
                description="AWS Secret Access Key",
                recommendation="Rotate the AWS secret key immediately via IAM console",
            ),
            # OpenAI API Key
            SecretPattern(
                pattern=re.compile(r"sk-[A-Za-z0-9]{48,}"),
                secret_type=SecretType.OPENAI_API_KEY,
                severity=SecretSeverity.HIGH,
                description="OpenAI API Key",
                recommendation="Regenerate the API key in OpenAI dashboard",
            ),
            # Anthropic API Key
            SecretPattern(
                pattern=re.compile(r"sk-ant-[A-Za-z0-9\-]{40,}"),
                secret_type=SecretType.ANTHROPIC_API_KEY,
                severity=SecretSeverity.HIGH,
                description="Anthropic API Key",
                recommendation="Regenerate the API key in Anthropic console",
            ),
            # GitHub Tokens
            SecretPattern(
                pattern=re.compile(r"ghp_[A-Za-z0-9]{36}"),
                secret_type=SecretType.GITHUB_PAT,
                severity=SecretSeverity.HIGH,
                description="GitHub Personal Access Token",
                recommendation="Revoke the token in GitHub settings",
            ),
            SecretPattern(
                pattern=re.compile(r"gho_[A-Za-z0-9]{36}"),
                secret_type=SecretType.GITHUB_TOKEN,
                severity=SecretSeverity.HIGH,
                description="GitHub OAuth Token",
                recommendation="Revoke the token in GitHub settings",
            ),
            SecretPattern(
                pattern=re.compile(r"ghu_[A-Za-z0-9]{36}"),
                secret_type=SecretType.GITHUB_TOKEN,
                severity=SecretSeverity.HIGH,
                description="GitHub User Token",
                recommendation="Revoke the token in GitHub settings",
            ),
            SecretPattern(
                pattern=re.compile(r"ghs_[A-Za-z0-9]{36}"),
                secret_type=SecretType.GITHUB_TOKEN,
                severity=SecretSeverity.HIGH,
                description="GitHub Server Token",
                recommendation="Revoke the token in GitHub settings",
            ),
            SecretPattern(
                pattern=re.compile(r"ghr_[A-Za-z0-9]{36}"),
                secret_type=SecretType.GITHUB_TOKEN,
                severity=SecretSeverity.HIGH,
                description="GitHub Refresh Token",
                recommendation="Revoke the token in GitHub settings",
            ),
            # GitLab Tokens
            SecretPattern(
                pattern=re.compile(r"glpat-[A-Za-z0-9\-]{20,}"),
                secret_type=SecretType.GITLAB_TOKEN,
                severity=SecretSeverity.HIGH,
                description="GitLab Personal Access Token",
                recommendation="Revoke the token in GitLab settings",
            ),
            # Slack
            SecretPattern(
                pattern=re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"),
                secret_type=SecretType.SLACK_TOKEN,
                severity=SecretSeverity.HIGH,
                description="Slack Token",
                recommendation="Regenerate the token in Slack workspace settings",
            ),
            SecretPattern(
                pattern=re.compile(
                    r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+"
                ),
                secret_type=SecretType.SLACK_WEBHOOK,
                severity=SecretSeverity.MEDIUM,
                description="Slack Webhook URL",
                recommendation="Regenerate the webhook in Slack app settings",
            ),
            # Stripe
            SecretPattern(
                pattern=re.compile(r"sk_live_[A-Za-z0-9]{24,}"),
                secret_type=SecretType.STRIPE_KEY,
                severity=SecretSeverity.CRITICAL,
                description="Stripe Live Secret Key",
                recommendation="Rotate the key immediately in Stripe dashboard",
            ),
            SecretPattern(
                pattern=re.compile(r"sk_test_[A-Za-z0-9]{24,}"),
                secret_type=SecretType.STRIPE_KEY,
                severity=SecretSeverity.LOW,
                description="Stripe Test Secret Key",
                recommendation="Consider removing test keys from code",
            ),
            # SendGrid
            SecretPattern(
                pattern=re.compile(r"SG\.[A-Za-z0-9\-_]{22,}\.[A-Za-z0-9\-_]{43,}"),
                secret_type=SecretType.SENDGRID_API_KEY,
                severity=SecretSeverity.HIGH,
                description="SendGrid API Key",
                recommendation="Regenerate the API key in SendGrid dashboard",
            ),
            # Twilio
            SecretPattern(
                pattern=re.compile(r"SK[A-Za-z0-9]{32}"),
                secret_type=SecretType.TWILIO_API_KEY,
                severity=SecretSeverity.HIGH,
                description="Twilio API Key",
                recommendation="Regenerate the API key in Twilio console",
            ),
            # Private Keys
            SecretPattern(
                pattern=re.compile(
                    r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----",
                    re.IGNORECASE,
                ),
                secret_type=SecretType.RSA_PRIVATE_KEY,
                severity=SecretSeverity.CRITICAL,
                description="RSA Private Key",
                recommendation="Remove key and generate a new one",
            ),
            SecretPattern(
                pattern=re.compile(
                    r"-----BEGIN\s+OPENSSH\s+PRIVATE\s+KEY-----",
                    re.IGNORECASE,
                ),
                secret_type=SecretType.SSH_PRIVATE_KEY,
                severity=SecretSeverity.CRITICAL,
                description="SSH Private Key",
                recommendation="Remove key and generate a new one",
            ),
            SecretPattern(
                pattern=re.compile(
                    r"-----BEGIN\s+PGP\s+PRIVATE\s+KEY\s+BLOCK-----",
                    re.IGNORECASE,
                ),
                secret_type=SecretType.PGP_PRIVATE_KEY,
                severity=SecretSeverity.CRITICAL,
                description="PGP Private Key",
                recommendation="Remove key and generate a new one",
            ),
            SecretPattern(
                pattern=re.compile(
                    r"-----BEGIN\s+EC\s+PRIVATE\s+KEY-----",
                    re.IGNORECASE,
                ),
                secret_type=SecretType.PRIVATE_KEY,
                severity=SecretSeverity.CRITICAL,
                description="EC Private Key",
                recommendation="Remove key and generate a new one",
            ),
            SecretPattern(
                pattern=re.compile(
                    r"-----BEGIN\s+DSA\s+PRIVATE\s+KEY-----",
                    re.IGNORECASE,
                ),
                secret_type=SecretType.PRIVATE_KEY,
                severity=SecretSeverity.CRITICAL,
                description="DSA Private Key",
                recommendation="Remove key and generate a new one",
            ),
            # JWT Tokens
            SecretPattern(
                pattern=re.compile(
                    r"eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+"
                ),
                secret_type=SecretType.JWT_TOKEN,
                severity=SecretSeverity.MEDIUM,
                description="JSON Web Token",
                recommendation="Ensure JWT is not hardcoded; use proper token management",
            ),
            # Database Connection Strings
            SecretPattern(
                pattern=re.compile(
                    r"(?i)(postgres|postgresql|mysql|mongodb)://[^:]+:[^@]+@[^\s]+"
                ),
                secret_type=SecretType.DATABASE_URL,
                severity=SecretSeverity.CRITICAL,
                description="Database Connection String with Credentials",
                recommendation="Use environment variables or secrets manager",
            ),
            SecretPattern(
                pattern=re.compile(r"mongodb\+srv://[^:]+:[^@]+@[^\s]+"),
                secret_type=SecretType.MONGODB_URI,
                severity=SecretSeverity.CRITICAL,
                description="MongoDB Connection URI with Credentials",
                recommendation="Use environment variables or secrets manager",
            ),
            SecretPattern(
                pattern=re.compile(r"redis://[^:]*:[^@]+@[^\s]+"),
                secret_type=SecretType.REDIS_PASSWORD,
                severity=SecretSeverity.HIGH,
                description="Redis Connection with Password",
                recommendation="Use environment variables or secrets manager",
            ),
            # Generic Password Patterns
            SecretPattern(
                pattern=re.compile(
                    r"(?i)(password|passwd|pwd|secret)[\s]*[=:][\s]*['\"]([^'\"]{8,})['\"]"
                ),
                secret_type=SecretType.PASSWORD,
                severity=SecretSeverity.HIGH,
                description="Hardcoded Password",
                recommendation="Use environment variables or secrets manager",
            ),
            # Basic Auth
            SecretPattern(
                pattern=re.compile(
                    r"(?i)authorization['\"]?\s*[:=]\s*['\"]?basic\s+[A-Za-z0-9+/=]{20,}['\"]?"
                ),
                secret_type=SecretType.BASIC_AUTH,
                severity=SecretSeverity.HIGH,
                description="Basic Authentication Credentials",
                recommendation="Use environment variables or secrets manager",
            ),
            # Bearer Token
            SecretPattern(
                pattern=re.compile(r"(?i)bearer\s+[A-Za-z0-9\-_.~+/]{20,}"),
                secret_type=SecretType.BEARER_TOKEN,
                severity=SecretSeverity.MEDIUM,
                description="Bearer Token",
                recommendation="Ensure token is not hardcoded",
            ),
            # NPM Token
            SecretPattern(
                pattern=re.compile(r"npm_[A-Za-z0-9]{36}"),
                secret_type=SecretType.NPM_TOKEN,
                severity=SecretSeverity.HIGH,
                description="NPM Access Token",
                recommendation="Revoke the token in npm settings",
            ),
            # PyPI Token
            SecretPattern(
                pattern=re.compile(r"pypi-[A-Za-z0-9\-_]{50,}"),
                secret_type=SecretType.PYPI_TOKEN,
                severity=SecretSeverity.HIGH,
                description="PyPI API Token",
                recommendation="Revoke the token in PyPI settings",
            ),
            # GCP
            SecretPattern(
                pattern=re.compile(r"AIza[A-Za-z0-9\-_]{35}"),
                secret_type=SecretType.GCP_API_KEY,
                severity=SecretSeverity.HIGH,
                description="Google Cloud API Key",
                recommendation="Rotate the key in Google Cloud Console",
            ),
            # Azure
            SecretPattern(
                pattern=re.compile(
                    r"(?i)(client[_-]?secret|azure[_-]?secret)['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9\-_.~]{30,})['\"]?"
                ),
                secret_type=SecretType.AZURE_CLIENT_SECRET,
                severity=SecretSeverity.HIGH,
                description="Azure Client Secret",
                recommendation="Rotate the secret in Azure Portal",
            ),
            # Generic API Key patterns
            SecretPattern(
                pattern=re.compile(
                    r"(?i)(api[_-]?key|apikey)['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9\-_.]{20,})['\"]?"
                ),
                secret_type=SecretType.GENERIC_API_KEY,
                severity=SecretSeverity.MEDIUM,
                description="Generic API Key",
                recommendation="Verify and rotate if this is a real API key",
            ),
        ]

    def scan_text(
        self,
        text: str,
        file_path: str | None = None,
    ) -> ScanResult:
        """
        Scan text for secrets.

        Args:
            text: Text content to scan
            file_path: Optional file path for context

        Returns:
            ScanResult with findings
        """
        import time

        start_time = time.time()

        findings: list[SecretFinding] = []
        lines = text.split("\n")

        for line_num, line in enumerate(lines, start=1):
            # Skip very long lines for performance
            if len(line) > self.max_line_length:
                line = line[: self.max_line_length]

            # Pattern-based detection
            for pattern_obj in self._patterns:
                matches = pattern_obj.pattern.finditer(line)
                for match in matches:
                    # Skip false positives
                    if self._is_false_positive(match.group(0), line):
                        continue

                    finding = SecretFinding(
                        secret_type=pattern_obj.secret_type,
                        severity=pattern_obj.severity,
                        line_number=line_num,
                        column=match.start() + 1,
                        matched_pattern=pattern_obj.description,
                        redacted_value=self._redact_value(match.group(0)),
                        context=self._get_context(line, match.start(), match.end()),
                        file_path=file_path,
                        recommendation=pattern_obj.recommendation,
                    )
                    findings.append(finding)

            # Entropy-based detection
            if self.enable_entropy_detection:
                entropy_findings = self._detect_high_entropy(line, line_num, file_path)
                findings.extend(entropy_findings)

        # Update statistics
        self._stats["total_scans"] += 1
        self._stats["total_findings"] += len(findings)

        # Log findings
        if self.log_findings and findings:
            for finding in findings:
                logger.warning(
                    f"Secret detected: {finding.secret_type.value} "
                    f"at line {finding.line_number} "
                    f"(file: {file_path or 'unknown'})"
                )

        scan_time = (time.time() - start_time) * 1000

        return ScanResult(
            has_secrets=len(findings) > 0,
            findings=findings,
            scanned_lines=len(lines),
            scan_time_ms=scan_time,
            file_path=file_path,
        )

    def scan_file(self, file_path: str) -> ScanResult:
        """
        Scan a file for secrets.

        Args:
            file_path: Path to file to scan

        Returns:
            ScanResult with findings
        """
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            return self.scan_text(content, file_path)
        except Exception as e:
            logger.error(f"Error scanning file {file_path}: {e}")
            return ScanResult(
                has_secrets=False,
                findings=[],
                scanned_lines=0,
                file_path=file_path,
            )

    def _is_false_positive(self, value: str, line: str) -> bool:
        """Check if a match is likely a false positive."""
        # Check against false positive patterns
        for pattern in self._false_positive_patterns:
            if pattern.search(value) or pattern.search(line):
                return True

        # Check for placeholder-like values
        if value.lower() in [
            "your_api_key",
            "your_secret",
            "changeme",
            "xxxxxxxxxx",
            "**********",
        ]:
            return True

        return False

    def _redact_value(self, value: str) -> str:
        """Redact a secret value for safe logging."""
        if len(value) <= 8:
            return "*" * len(value)
        # Show first 4 and last 4 characters
        return f"{value[:4]}...{value[-4:]}"

    def _get_context(self, line: str, start: int, end: int) -> str:
        """Get context around a match."""
        context_size = 20
        context_start = max(0, start - context_size)
        context_end = min(len(line), end + context_size)

        prefix = "..." if context_start > 0 else ""
        suffix = "..." if context_end < len(line) else ""

        return f"{prefix}{line[context_start:context_end]}{suffix}"

    def _detect_high_entropy(
        self,
        line: str,
        line_num: int,
        file_path: str | None,
    ) -> list[SecretFinding]:
        """Detect high-entropy strings that might be secrets."""
        findings: list[SecretFinding] = []

        # Look for quoted strings or assignment values
        patterns = [
            r"['\"]([A-Za-z0-9+/=\-_]{20,})['\"]",  # Quoted strings
            r"=\s*([A-Za-z0-9+/=\-_]{20,})\s*$",  # Assignment values
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, line)
            for match in matches:
                value = match.group(1)

                # Skip if already detected by pattern matching
                if self._is_false_positive(value, line):
                    continue

                entropy = self._calculate_entropy(value)
                if entropy >= self.entropy_threshold:
                    finding = SecretFinding(
                        secret_type=SecretType.HIGH_ENTROPY_STRING,
                        severity=SecretSeverity.MEDIUM,
                        line_number=line_num,
                        column=match.start() + 1,
                        matched_pattern=f"High entropy string (entropy: {entropy:.2f})",
                        redacted_value=self._redact_value(value),
                        context=self._get_context(line, match.start(), match.end()),
                        file_path=file_path,
                        recommendation="Review if this is a hardcoded secret",
                    )
                    findings.append(finding)

        return findings

    def _calculate_entropy(self, value: str) -> float:
        """Calculate Shannon entropy of a string."""
        import math

        if not value:
            return 0.0

        # Count character frequencies
        freq: dict[str, int] = {}
        for char in value:
            freq[char] = freq.get(char, 0) + 1

        # Calculate entropy
        entropy = 0.0
        length = len(value)
        for count in freq.values():
            if count > 0:
                probability = count / length
                entropy -= probability * math.log2(probability)

        return entropy

    def hash_secret(self, value: str) -> str:
        """
        Generate a hash of a secret for deduplication.

        This allows tracking unique secrets without storing them.
        """
        return hashlib.sha256(value.encode()).hexdigest()[:16]

    def get_stats(self) -> dict[str, Any]:
        """Get scanning statistics."""
        return dict(self._stats)

    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = {
            "total_scans": 0,
            "total_findings": 0,
            "by_type": {},
        }


# =============================================================================
# Singleton Instance
# =============================================================================

_secrets_service: SecretsDetectionService | None = None


def get_secrets_service() -> SecretsDetectionService:
    """Get singleton secrets detection service instance."""
    global _secrets_service
    if _secrets_service is None:
        _secrets_service = SecretsDetectionService()
    return _secrets_service


def scan_for_secrets(
    text: str,
    file_path: str | None = None,
) -> ScanResult:
    """Convenience function to scan text for secrets."""
    return get_secrets_service().scan_text(text, file_path)


def scan_file_for_secrets(file_path: str) -> ScanResult:
    """Convenience function to scan a file for secrets."""
    return get_secrets_service().scan_file(file_path)
