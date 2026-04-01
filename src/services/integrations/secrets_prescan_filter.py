"""
Secrets Pre-Scan Filter - Detect and redact secrets before GraphRAG storage.

This module provides a critical security control that scans code content for
secrets (API keys, passwords, tokens) BEFORE it reaches the Neptune graph
database. Detected secrets are redacted with type-specific placeholders.

ADR Reference: ADR-048 Security Considerations - Critical Control #1
"""

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SecretType(Enum):
    """Types of secrets that can be detected."""

    # Cloud Provider Keys
    AWS_ACCESS_KEY = "aws_access_key"
    AWS_SECRET_KEY = "aws_secret_key"
    AZURE_CLIENT_SECRET = "azure_client_secret"
    GCP_SERVICE_ACCOUNT = "gcp_service_account"

    # Source Control (GitHub, GitLab)
    GITHUB_TOKEN = "github_token"
    GITHUB_PAT = "github_pat"
    GITLAB_TOKEN = "gitlab_token"

    # Ticketing Integrations (Integration Hub)
    ZENDESK_API_TOKEN = "zendesk_api_token"
    SERVICENOW_PASSWORD = "servicenow_password"
    SERVICENOW_OAUTH = "servicenow_oauth"
    LINEAR_API_KEY = "linear_api_key"
    JIRA_API_TOKEN = "jira_api_token"
    JIRA_OAUTH = "jira_oauth"

    # Monitoring Integrations (Integration Hub)
    DATADOG_API_KEY = "datadog_api_key"
    DATADOG_APP_KEY = "datadog_app_key"
    PAGERDUTY_API_KEY = "pagerduty_api_key"
    PAGERDUTY_INTEGRATION_KEY = "pagerduty_integration_key"
    SPLUNK_TOKEN = "splunk_token"
    SPLUNK_HEC_TOKEN = "splunk_hec_token"

    # Security Integrations (Integration Hub)
    QUALYS_CREDENTIALS = "qualys_credentials"
    SNYK_TOKEN = "snyk_token"

    # Communication Integrations (Integration Hub)
    SLACK_TOKEN = "slack_token"
    SLACK_WEBHOOK = "slack_webhook"
    TEAMS_WEBHOOK = "teams_webhook"

    # Payment/SaaS Keys
    STRIPE_KEY = "stripe_key"
    OPENAI_KEY = "openai_key"
    ANTHROPIC_KEY = "anthropic_key"

    # Generic Patterns
    GENERIC_API_KEY = "generic_api_key"
    GENERIC_SECRET = "generic_secret"
    PASSWORD = "password"
    PRIVATE_KEY = "private_key"
    JWT_TOKEN = "jwt_token"
    BEARER_TOKEN = "bearer_token"
    DATABASE_URL = "database_url"
    CONNECTION_STRING = "connection_string"
    BASIC_AUTH = "basic_auth"


@dataclass
class SecretDetection:
    """A detected secret in code content."""

    secret_type: SecretType
    line_number: int
    column_start: int
    column_end: int
    original_length: int
    confidence: float  # 0.0 to 1.0
    context: str  # Surrounding code (redacted)
    detection_id: str = field(default_factory=lambda: "")

    def __post_init__(self):
        if not self.detection_id:
            # Generate deterministic ID for deduplication
            content = f"{self.secret_type.value}:{self.line_number}:{self.column_start}"
            self.detection_id = hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/API responses."""
        return {
            "detection_id": self.detection_id,
            "secret_type": self.secret_type.value,
            "line_number": self.line_number,
            "column_start": self.column_start,
            "column_end": self.column_end,
            "original_length": self.original_length,
            "confidence": self.confidence,
        }


@dataclass
class RedactionResult:
    """Result of scanning and redacting content."""

    original_content_hash: str
    redacted_content: str
    secrets_found: list[SecretDetection]
    scan_duration_ms: float
    is_clean: bool  # True if no secrets found

    @property
    def secret_count(self) -> int:
        """Return total number of secrets detected."""
        return len(self.secrets_found)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "is_clean": self.is_clean,
            "secret_count": self.secret_count,
            "scan_duration_ms": self.scan_duration_ms,
            "secrets": [s.to_dict() for s in self.secrets_found],
        }


# Secret detection patterns with confidence scores
SECRET_PATTERNS: list[tuple[SecretType, str, float]] = [
    # ==========================================================================
    # CLOUD PROVIDER KEYS
    # ==========================================================================
    # AWS keys
    (
        SecretType.AWS_ACCESS_KEY,
        r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}",
        0.95,
    ),
    (
        SecretType.AWS_SECRET_KEY,
        r"(?i)aws[_\-]?secret[_\-]?(?:access[_\-]?)?key['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})",
        0.90,
    ),
    # Azure
    (
        SecretType.AZURE_CLIENT_SECRET,
        r"(?i)azure[_\-]?(?:client[_\-]?)?secret['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9\-_.~]{30,})",
        0.85,
    ),
    # GCP
    (SecretType.GCP_SERVICE_ACCOUNT, r'"type"\s*:\s*"service_account"', 0.95),
    # ==========================================================================
    # SOURCE CONTROL (GitHub, GitLab)
    # ==========================================================================
    (SecretType.GITHUB_TOKEN, r"ghp_[A-Za-z0-9]{36}", 0.98),
    (SecretType.GITHUB_TOKEN, r"gho_[A-Za-z0-9]{36}", 0.98),
    (SecretType.GITHUB_TOKEN, r"ghu_[A-Za-z0-9]{36}", 0.98),
    (SecretType.GITHUB_TOKEN, r"ghs_[A-Za-z0-9]{36}", 0.98),
    (SecretType.GITHUB_TOKEN, r"ghr_[A-Za-z0-9]{36}", 0.98),
    (SecretType.GITHUB_PAT, r"github_pat_[A-Za-z0-9]{22}_[A-Za-z0-9]{59}", 0.98),
    (SecretType.GITLAB_TOKEN, r"glpat-[A-Za-z0-9\-_]{20}", 0.95),
    # ==========================================================================
    # TICKETING INTEGRATIONS (Integration Hub)
    # ==========================================================================
    # Zendesk - API tokens are 40-character alphanumeric
    (
        SecretType.ZENDESK_API_TOKEN,
        r"(?i)zendesk[_\-]?(?:api[_\-]?)?token['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9]{40})",
        0.90,
    ),
    (
        SecretType.ZENDESK_API_TOKEN,
        r"(?i)(?:zendesk|zd)[_\-]?token['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9]{20,})",
        0.80,
    ),
    # ServiceNow - passwords and OAuth tokens
    (
        SecretType.SERVICENOW_PASSWORD,
        r"(?i)servicenow[_\-]?(?:password|pwd)['\"]?\s*[:=]\s*['\"]?([^\s'\"]{8,})",
        0.85,
    ),
    (
        SecretType.SERVICENOW_OAUTH,
        r"(?i)servicenow[_\-]?(?:client[_\-]?)?secret['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9\-_]{20,})",
        0.85,
    ),
    # Linear - API keys start with lin_api_
    (SecretType.LINEAR_API_KEY, r"lin_api_[A-Za-z0-9]{32,}", 0.98),
    (
        SecretType.LINEAR_API_KEY,
        r"(?i)linear[_\-]?(?:api[_\-]?)?key['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9\-_]{20,})",
        0.80,
    ),
    # Jira - API tokens and OAuth
    (
        SecretType.JIRA_API_TOKEN,
        r"(?i)jira[_\-]?(?:api[_\-]?)?token['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9]{24,})",
        0.85,
    ),
    (
        SecretType.JIRA_OAUTH,
        r"(?i)atlassian[_\-]?(?:client[_\-]?)?secret['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9\-_]{20,})",
        0.85,
    ),
    # ==========================================================================
    # MONITORING INTEGRATIONS (Integration Hub)
    # ==========================================================================
    # Datadog - API keys are 32 hex chars, App keys are 40 hex chars
    (
        SecretType.DATADOG_API_KEY,
        r"(?i)(?:dd|datadog)[_\-]?api[_\-]?key['\"]?\s*[:=]\s*['\"]?([a-f0-9]{32})",
        0.95,
    ),
    (
        SecretType.DATADOG_APP_KEY,
        r"(?i)(?:dd|datadog)[_\-]?app(?:lication)?[_\-]?key['\"]?\s*[:=]\s*['\"]?([a-f0-9]{40})",
        0.95,
    ),
    # PagerDuty - API keys and integration keys
    (
        SecretType.PAGERDUTY_API_KEY,
        r"(?i)pagerduty[_\-]?(?:api[_\-]?)?(?:key|token)['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9+/=]{20,})",
        0.90,
    ),
    (
        SecretType.PAGERDUTY_INTEGRATION_KEY,
        r"(?i)pagerduty[_\-]?(?:integration|routing)[_\-]?key['\"]?\s*[:=]\s*['\"]?([a-f0-9]{32})",
        0.95,
    ),
    # Splunk - tokens (HEC tokens are typically UUIDs)
    (
        SecretType.SPLUNK_TOKEN,
        r"(?i)splunk[_\-]?(?:api[_\-]?)?token['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9\-_]{20,})",
        0.85,
    ),
    (
        SecretType.SPLUNK_HEC_TOKEN,
        r"(?i)(?:hec|http_event_collector)[_\-]?token['\"]?\s*[:=]\s*['\"]?([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})",
        0.95,
    ),
    # ==========================================================================
    # SECURITY INTEGRATIONS (Integration Hub)
    # ==========================================================================
    # Qualys - username:password in URL or config
    (
        SecretType.QUALYS_CREDENTIALS,
        r"(?i)qualys[_\-]?(?:password|pwd)['\"]?\s*[:=]\s*['\"]?([^\s'\"]{8,})",
        0.85,
    ),
    (SecretType.QUALYS_CREDENTIALS, r"https://[^:]+:[^@]+@qualysapi\.", 0.95),
    # Snyk - API tokens
    (
        SecretType.SNYK_TOKEN,
        r"(?i)snyk[_\-]?(?:api[_\-]?)?token['\"]?\s*[:=]\s*['\"]?([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})",
        0.95,
    ),
    (
        SecretType.SNYK_TOKEN,
        r"(?i)snyk[_\-]?token['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9\-_]{36,})",
        0.85,
    ),
    # ==========================================================================
    # COMMUNICATION INTEGRATIONS (Integration Hub)
    # ==========================================================================
    # Slack
    (SecretType.SLACK_TOKEN, r"xox[baprs]-[0-9A-Za-z\-]{10,250}", 0.95),
    (
        SecretType.SLACK_WEBHOOK,
        r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+",
        0.98,
    ),
    # Microsoft Teams - webhook URLs
    (
        SecretType.TEAMS_WEBHOOK,
        r"https://[a-z0-9\-]+\.webhook\.office\.com/webhookb2/[a-f0-9\-]+",
        0.98,
    ),
    (
        SecretType.TEAMS_WEBHOOK,
        r"(?i)teams[_\-]?webhook[_\-]?url['\"]?\s*[:=]\s*['\"]?(https://[^\s'\"]+)",
        0.85,
    ),
    # ==========================================================================
    # PAYMENT/SAAS KEYS
    # ==========================================================================
    # Stripe keys
    (SecretType.STRIPE_KEY, r"sk_(?:live|test)_[A-Za-z0-9]{24,}", 0.98),
    (SecretType.STRIPE_KEY, r"pk_(?:live|test)_[A-Za-z0-9]{24,}", 0.98),
    (SecretType.STRIPE_KEY, r"rk_(?:live|test)_[A-Za-z0-9]{24,}", 0.98),
    # OpenAI/Anthropic keys
    (SecretType.OPENAI_KEY, r"sk-[A-Za-z0-9]{48}", 0.95),
    (SecretType.ANTHROPIC_KEY, r"sk-ant-[A-Za-z0-9\-]{80,}", 0.95),
    # ==========================================================================
    # GENERIC PATTERNS (lower confidence)
    # ==========================================================================
    (
        SecretType.GENERIC_API_KEY,
        r"(?i)(?:api[_\-]?key|apikey)['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9\-_]{20,})['\"]?",
        0.70,
    ),
    (
        SecretType.GENERIC_SECRET,
        r"(?i)(?:secret|token|password|passwd|pwd)['\"]?\s*[:=]\s*['\"]?([^\s'\"]{8,})['\"]?",
        0.60,
    ),
    # ==========================================================================
    # CRYPTOGRAPHIC SECRETS
    # ==========================================================================
    # Private keys
    (
        SecretType.PRIVATE_KEY,
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
        0.99,
    ),
    (SecretType.PRIVATE_KEY, r"-----BEGIN PGP PRIVATE KEY BLOCK-----", 0.99),
    # JWT tokens
    (
        SecretType.JWT_TOKEN,
        r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
        0.85,
    ),
    # Bearer tokens
    (SecretType.BEARER_TOKEN, r"(?i)bearer\s+[A-Za-z0-9\-_\.]{20,}", 0.80),
    # ==========================================================================
    # DATABASE/CONNECTION STRINGS
    # ==========================================================================
    (SecretType.DATABASE_URL, r"(?:postgres|mysql|mongodb|redis)://[^:]+:[^@]+@", 0.90),
    (
        SecretType.CONNECTION_STRING,
        r"(?i)(?:connection[_\-]?string|conn[_\-]?str)['\"]?\s*[:=]\s*['\"]?[^\s'\"]{20,}",
        0.75,
    ),
    # Basic auth
    (SecretType.BASIC_AUTH, r"(?i)basic\s+[A-Za-z0-9+/=]{20,}", 0.85),
]

# Patterns that should be excluded (known safe patterns)
EXCLUSION_PATTERNS: list[str] = [
    r"AKIAIOSFODNN7EXAMPLE",  # AWS example key
    r"wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",  # AWS example secret
    r"your-api-key-here",
    r"<your-token>",
    r"\$\{[A-Z_]+\}",  # Environment variable placeholders
    r"process\.env\.[A-Z_]+",  # Node.js env vars
    r"os\.environ\[['\"]",  # Python env vars
    r"ENV\[['\"]",  # Ruby env vars
]


class SecretsPrescanFilter:
    """
    Scans code content for secrets and redacts them before GraphRAG storage.

    This is a CRITICAL security control that prevents sensitive credentials
    from being stored in the Neptune graph database.
    """

    def __init__(
        self,
        min_confidence: float = 0.7,
        enable_audit_logging: bool = True,
        custom_patterns: list[tuple[SecretType, str, float]] | None = None,
    ):
        """
        Initialize the secrets filter.

        Args:
            min_confidence: Minimum confidence threshold for detection (0.0-1.0)
            enable_audit_logging: Whether to log detected secrets (redacted)
            custom_patterns: Additional patterns to detect
        """
        self.min_confidence = min_confidence
        self.enable_audit_logging = enable_audit_logging

        # Compile patterns for performance
        self._patterns: list[tuple[SecretType, re.Pattern[str], float]] = []
        all_patterns = SECRET_PATTERNS + (custom_patterns or [])

        for secret_type, pattern_str, confidence in all_patterns:
            try:
                compiled = re.compile(pattern_str)
                self._patterns.append((secret_type, compiled, confidence))
            except re.error as e:
                logger.warning(f"Invalid pattern for {secret_type.value}: {e}")

        # Compile exclusion patterns
        self._exclusions = [re.compile(p) for p in EXCLUSION_PATTERNS]

    def scan_and_redact(
        self,
        content: str,
        file_path: str | None = None,
        organization_id: str | None = None,
    ) -> RedactionResult:
        """
        Scan content for secrets and return redacted version.

        Args:
            content: The code content to scan
            file_path: Optional file path for logging context
            organization_id: Optional organization ID for audit trail

        Returns:
            RedactionResult with redacted content and detection details
        """
        import time

        start_time = time.perf_counter()

        # Hash original content for audit trail
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        # Find all secrets
        detections: list[SecretDetection] = []
        lines = content.split("\n")

        for line_num, line in enumerate(lines, start=1):
            line_detections = self._scan_line(line, line_num)
            detections.extend(line_detections)

        # Sort by position (line, column) descending for safe replacement
        detections.sort(key=lambda d: (d.line_number, d.column_start), reverse=True)

        # Deduplicate overlapping detections
        detections = self._deduplicate_detections(detections)

        # Redact secrets from content
        redacted_lines = lines.copy()
        for detection in detections:
            line_idx = detection.line_number - 1
            line = redacted_lines[line_idx]

            # Create redaction placeholder
            placeholder = f"[REDACTED:{detection.secret_type.value}]"

            # Replace the secret
            redacted_lines[line_idx] = (
                line[: detection.column_start]
                + placeholder
                + line[detection.column_end :]
            )

        redacted_content = "\n".join(redacted_lines)
        scan_duration_ms = (time.perf_counter() - start_time) * 1000

        # Audit logging
        if self.enable_audit_logging and detections:
            self._log_detections(
                detections=detections,
                file_path=file_path,
                organization_id=organization_id,
            )

        return RedactionResult(
            original_content_hash=content_hash,
            redacted_content=redacted_content,
            secrets_found=detections,
            scan_duration_ms=scan_duration_ms,
            is_clean=len(detections) == 0,
        )

    def scan_only(
        self,
        content: str,
        file_path: str | None = None,
    ) -> list[SecretDetection]:
        """
        Scan content for secrets without redacting.

        Useful for pre-commit hooks or editor integrations that want
        to warn but not modify content.

        Args:
            content: The code content to scan
            file_path: Optional file path for context

        Returns:
            List of detected secrets
        """
        detections: list[SecretDetection] = []
        lines = content.split("\n")

        for line_num, line in enumerate(lines, start=1):
            line_detections = self._scan_line(line, line_num)
            detections.extend(line_detections)

        return self._deduplicate_detections(detections)

    def _scan_line(self, line: str, line_number: int) -> list[SecretDetection]:
        """Scan a single line for secrets."""
        detections: list[SecretDetection] = []

        # Skip empty lines
        if not line.strip():
            return detections

        # Check each pattern
        for secret_type, pattern, confidence in self._patterns:
            if confidence < self.min_confidence:
                continue

            for match in pattern.finditer(line):
                # Check if this match should be excluded
                matched_text = match.group(0)
                if self._is_excluded(matched_text):
                    continue

                # Get column positions
                col_start = match.start()
                col_end = match.end()

                # Create context (surrounding code, truncated)
                context_start = max(0, col_start - 20)
                context_end = min(len(line), col_end + 20)
                context = line[context_start:context_end]

                # Mask the actual secret in context
                masked_context = (
                    context[: col_start - context_start]
                    + "***"
                    + context[col_end - context_start :]
                )

                detection = SecretDetection(
                    secret_type=secret_type,
                    line_number=line_number,
                    column_start=col_start,
                    column_end=col_end,
                    original_length=col_end - col_start,
                    confidence=confidence,
                    context=masked_context,
                )
                detections.append(detection)

        return detections

    def _is_excluded(self, text: str) -> bool:
        """Check if text matches an exclusion pattern."""
        for pattern in self._exclusions:
            if pattern.search(text):
                return True
        return False

    def _deduplicate_detections(
        self, detections: list[SecretDetection]
    ) -> list[SecretDetection]:
        """Remove overlapping detections, keeping highest confidence."""
        if not detections:
            return []

        # Sort by line, column, then confidence (highest first)
        sorted_dets = sorted(
            detections,
            key=lambda d: (d.line_number, d.column_start, -d.confidence),
        )

        result: list[SecretDetection] = []
        for det in sorted_dets:
            # Check for overlap with existing detections
            overlaps = False
            for existing in result:
                if existing.line_number != det.line_number:
                    continue
                # Check column overlap
                if not (
                    det.column_end <= existing.column_start
                    or det.column_start >= existing.column_end
                ):
                    overlaps = True
                    break

            if not overlaps:
                result.append(det)

        return result

    def _log_detections(
        self,
        detections: list[SecretDetection],
        file_path: str | None,
        organization_id: str | None,
    ) -> None:
        """Log detected secrets for audit trail."""
        for detection in detections:
            logger.warning(
                "Secret detected and redacted",
                extra={
                    "event_type": "secret_detection",
                    "detection_id": detection.detection_id,
                    "secret_type": detection.secret_type.value,
                    "line_number": detection.line_number,
                    "confidence": detection.confidence,
                    "file_path": file_path,
                    "organization_id": organization_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
