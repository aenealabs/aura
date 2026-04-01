"""
Project Aura - Input Validation Service

Comprehensive input validation for API endpoints covering:
- Path traversal prevention (CWE-22)
- SQL/NoSQL injection patterns (CWE-89)
- XSS prevention (CWE-79)
- SSRF prevention (CWE-918)
- Email/URL/File path validation
- JSON/XML injection prevention

Author: Project Aura Team
Created: 2025-12-12
"""

import ipaddress
import logging
import re
import socket
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from urllib.parse import unquote, urlparse

logger = logging.getLogger(__name__)

# Default maximum nesting depth for JSON structures
DEFAULT_MAX_JSON_DEPTH = 100


class ValidationError(Exception):
    """Raised when input validation fails."""

    def __init__(
        self, message: str, field: str | None = None, code: str | None = None
    ) -> None:
        super().__init__(message)
        self.field = field
        self.code = code


class ThreatType(Enum):
    """Types of security threats detected."""

    PATH_TRAVERSAL = "path_traversal"
    SQL_INJECTION = "sql_injection"
    NOSQL_INJECTION = "nosql_injection"
    XSS = "xss"
    SSRF = "ssrf"
    COMMAND_INJECTION = "command_injection"
    LDAP_INJECTION = "ldap_injection"
    XML_INJECTION = "xml_injection"
    TEMPLATE_INJECTION = "template_injection"
    SECRETS_EXPOSURE = "secrets_exposure"


@dataclass
class ValidationResult:
    """Result of input validation."""

    is_valid: bool
    sanitized_value: Any
    threats_detected: list[ThreatType] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    original_value: Any = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_valid": self.is_valid,
            "threats_detected": [t.value for t in self.threats_detected],
            "warnings": self.warnings,
        }


class InputValidator:
    """
    Comprehensive input validation service.

    Provides validation and sanitization for various input types
    with detection of common attack patterns.
    """

    # Path traversal patterns
    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./",  # ../
        r"\.\.\%2[fF]",  # URL encoded ../
        r"\.\.\\",  # ..\
        r"\.\.\%5[cC]",  # URL encoded ..\
        r"%2[eE]%2[eE]%2[fF]",  # Double URL encoded
        r"%252[eE]%252[eE]%252[fF]",  # Triple URL encoded
        r"\.\.%c0%af",  # Unicode encoding
        r"\.\.%c1%9c",  # Unicode encoding
    ]

    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|TRUNCATE)\b)",
        r"(\b(OR|AND)\s+[\d\w'\"=]+\s*[=<>])",
        r"(-{2}|#|/\*)",  # SQL comments
        r"(\bEXEC(UTE)?\b|\bxp_)",  # SQL Server specific
        r"(\bWAITFOR\s+DELAY\b)",  # Time-based
        r"(\bBENCHMARK\s*\()",  # MySQL time-based
        r"('\s*(OR|AND)\s*')",  # String-based
        r"(;\s*(SELECT|INSERT|UPDATE|DELETE))",  # Stacked queries
        r"(\bINTO\s+(OUTFILE|DUMPFILE)\b)",  # File operations
        r"(\bLOAD_FILE\s*\()",  # File reading
    ]

    # NoSQL injection patterns (MongoDB, etc.)
    NOSQL_INJECTION_PATTERNS = [
        r"\$where",
        r"\$gt|\$lt|\$ne|\$eq",
        r"\$regex",
        r"\$or|\$and|\$not|\$nor",
        r"{\s*['\"]?\$",
        r"\[\s*\$",
    ]

    # XSS patterns
    XSS_PATTERNS = [
        r"<script[^>]*>",
        r"javascript:",
        r"on\w+\s*=",  # Event handlers
        r"<iframe",
        r"<object",
        r"<embed",
        r"<svg[^>]*onload",
        r"<img[^>]*onerror",
        r"expression\s*\(",  # CSS expression
        r"url\s*\(\s*['\"]?data:",  # Data URLs
        r"<\s*style[^>]*>.*expression",
    ]

    # Command injection patterns
    COMMAND_INJECTION_PATTERNS = [
        r"[;&|`$]",  # Shell metacharacters
        r"\$\(",  # Command substitution
        r"`[^`]+`",  # Backtick execution
        r"\|\s*\w+",  # Pipe to command
        r">\s*/",  # Redirect to path
        r"<\s*/",  # Input from path
    ]

    # LDAP injection patterns
    LDAP_INJECTION_PATTERNS = [
        r"[()\\*\x00]",  # LDAP special chars
        r"\x00",  # Null byte
    ]

    # XML injection patterns
    XML_INJECTION_PATTERNS = [
        r"<!ENTITY",
        r"<!DOCTYPE",
        r"<!\[CDATA\[",
        r"&[a-zA-Z]+;",  # Entity references
        r"&#\d+;",  # Numeric entities
        r"&#x[a-fA-F0-9]+;",  # Hex entities
    ]

    # Template injection patterns (Jinja2, etc.)
    TEMPLATE_INJECTION_PATTERNS = [
        r"\{\{.*\}\}",  # Jinja2/Django
        r"\{%.*%\}",  # Jinja2
        r"\$\{.*\}",  # Various
        r"<%.*%>",  # ASP/JSP
        r"#\{.*\}",  # Ruby ERB
    ]

    # Private/internal IP ranges for SSRF
    PRIVATE_IP_RANGES = [
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("127.0.0.0/8"),
        ipaddress.ip_network("169.254.0.0/16"),  # Link-local
        ipaddress.ip_network("0.0.0.0/8"),
        ipaddress.ip_network("::1/128"),  # IPv6 loopback
        ipaddress.ip_network("fc00::/7"),  # IPv6 private
        ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
    ]

    # Blocked URL schemes for SSRF
    BLOCKED_SCHEMES = {"file", "gopher", "dict", "ftp", "ldap", "tftp"}

    # Cloud metadata service endpoints (SSRF targets)
    CLOUD_METADATA_HOSTS = {
        "169.254.169.254",  # AWS, Azure, DigitalOcean, Oracle
        "metadata.google.internal",  # GCP
        "100.100.100.200",  # Alibaba Cloud
        "169.254.170.2",  # AWS ECS task metadata
    }

    # DNS rebinding service domains (wildcards resolve to embedded IPs)
    DNS_REBINDING_DOMAINS = [
        r"\.nip\.io$",
        r"\.xip\.io$",
        r"\.sslip\.io$",
        r"\.lvh\.me$",
        r"\.localtest\.me$",
        r"\.vcap\.me$",
    ]

    # Dangerous filesystem paths (container escape, privilege escalation)
    DANGEROUS_PATH_PATTERNS = [
        # Cgroup escape vectors
        r"^/sys/fs/cgroup(/.*)?/release_agent$",
        r"^/proc/1/cgroup$",
        # Device files
        r"^/dev/(sd[a-z]|hd[a-z]|nvme\d+n\d+)",
        r"^/dev/(mem|kmem|port)$",
        # /proc filesystem sensitive paths
        r"^/proc/self/(exe|mem|environ|root|fd)$",
        r"^/proc/\d+/(root|mem|environ)$",
        # Docker socket
        r"^/(var/run|run)/docker\.sock$",
    ]

    def __init__(
        self,
        strict_mode: bool = False,
        log_threats: bool = True,
        max_string_length: int = 10000,
    ):
        """
        Initialize input validator.

        Args:
            strict_mode: If True, reject on any threat detection
            log_threats: Log detected threats
            max_string_length: Maximum allowed string length
        """
        self.strict_mode = strict_mode
        self.log_threats = log_threats
        self.max_string_length = max_string_length

        # Compile patterns for efficiency
        self._path_patterns = [
            re.compile(p, re.I) for p in self.PATH_TRAVERSAL_PATTERNS
        ]
        self._sql_patterns = [re.compile(p, re.I) for p in self.SQL_INJECTION_PATTERNS]
        self._nosql_patterns = [
            re.compile(p, re.I) for p in self.NOSQL_INJECTION_PATTERNS
        ]
        self._xss_patterns = [re.compile(p, re.I) for p in self.XSS_PATTERNS]
        self._cmd_patterns = [re.compile(p) for p in self.COMMAND_INJECTION_PATTERNS]
        self._ldap_patterns = [re.compile(p) for p in self.LDAP_INJECTION_PATTERNS]
        self._xml_patterns = [re.compile(p, re.I) for p in self.XML_INJECTION_PATTERNS]
        self._template_patterns = [
            re.compile(p) for p in self.TEMPLATE_INJECTION_PATTERNS
        ]
        self._dns_rebinding_patterns = [
            re.compile(p, re.I) for p in self.DNS_REBINDING_DOMAINS
        ]
        self._dangerous_path_patterns = [
            re.compile(p) for p in self.DANGEROUS_PATH_PATTERNS
        ]

        # Statistics
        self._stats: dict[str, Any] = {
            "total_validated": 0,
            "threats_detected": 0,
            "by_threat_type": {t.value: 0 for t in ThreatType},
        }

    def validate_string(
        self,
        value: str,
        field_name: str = "input",
        check_path_traversal: bool = True,
        check_sql_injection: bool = True,
        check_xss: bool = True,
        check_command_injection: bool = True,
    ) -> ValidationResult:
        """
        Validate a string input for common attack patterns.

        Args:
            value: String to validate
            field_name: Name of field for error messages
            check_path_traversal: Check for path traversal
            check_sql_injection: Check for SQL injection
            check_xss: Check for XSS
            check_command_injection: Check for command injection

        Returns:
            ValidationResult with validation status and detected threats
        """
        self._stats["total_validated"] += 1
        threats = []
        warnings = []

        # Check length
        if len(value) > self.max_string_length:
            warnings.append(f"Input exceeds maximum length of {self.max_string_length}")
            if self.strict_mode:
                return ValidationResult(
                    is_valid=False,
                    sanitized_value=value[: self.max_string_length],
                    threats_detected=[],
                    warnings=warnings,
                    original_value=value,
                )

        # Check for various attack patterns
        if check_path_traversal and self._check_patterns(value, self._path_patterns):
            threats.append(ThreatType.PATH_TRAVERSAL)
            self._log_threat(ThreatType.PATH_TRAVERSAL, field_name, value)

        if check_sql_injection and self._check_patterns(value, self._sql_patterns):
            threats.append(ThreatType.SQL_INJECTION)
            self._log_threat(ThreatType.SQL_INJECTION, field_name, value)

        if check_xss and self._check_patterns(value, self._xss_patterns):
            threats.append(ThreatType.XSS)
            self._log_threat(ThreatType.XSS, field_name, value)

        if check_command_injection and self._check_patterns(value, self._cmd_patterns):
            threats.append(ThreatType.COMMAND_INJECTION)
            self._log_threat(ThreatType.COMMAND_INJECTION, field_name, value)

        # Update stats
        if threats:
            self._stats["threats_detected"] += 1
            for threat in threats:
                self._stats["by_threat_type"][threat.value] += 1

        # Determine validity
        is_valid = len(threats) == 0 or not self.strict_mode

        return ValidationResult(
            is_valid=is_valid,
            sanitized_value=self._sanitize_string(value) if threats else value,
            threats_detected=threats,
            warnings=warnings,
            original_value=value,
        )

    def validate_path(self, path: str, base_dir: str | None = None) -> ValidationResult:
        """
        Validate a file path for security issues.

        Detects path traversal attempts including:
        - Standard patterns (../, ..)
        - URL encoded patterns (%2e%2e%2f)
        - Double URL encoded patterns (%252e%252e%252f)
        - Overlong UTF-8 encoding (%c0%af for /)
        - Unicode normalization bypass attempts

        Args:
            path: Path to validate
            base_dir: Optional base directory to check containment

        Returns:
            ValidationResult
        """
        self._stats["total_validated"] += 1
        threats = []
        warnings = []
        sanitized_path = path

        # Check for path traversal patterns in original path
        if self._check_patterns(path, self._path_patterns):
            threats.append(ThreatType.PATH_TRAVERSAL)
            self._log_threat(ThreatType.PATH_TRAVERSAL, "path", path)

        # Detect Unicode normalization / encoding bypass attempts
        # Decode URL encoding multiple times to catch double/triple encoding
        decoded_path = path
        decode_iterations = 0
        max_decode_iterations = 3  # Prevent infinite loops

        while decode_iterations < max_decode_iterations:
            try:
                new_decoded = unquote(decoded_path)
                if new_decoded == decoded_path:
                    break  # No more decoding needed
                decoded_path = new_decoded
                decode_iterations += 1
            except Exception:
                break

        # Check decoded path for traversal patterns
        if ".." in decoded_path and ThreatType.PATH_TRAVERSAL not in threats:
            threats.append(ThreatType.PATH_TRAVERSAL)
            warnings.append("Path traversal detected after URL decoding")
            self._log_threat(ThreatType.PATH_TRAVERSAL, "path", path)

        # Detect overlong UTF-8 encoding patterns (bypass attempts)
        # %c0%af is an overlong encoding of '/' (should be %2f)
        # %c1%9c is an overlong encoding of '\' (should be %5c)
        overlong_patterns = [
            r"%c0%[a-f0-9]{2}",  # Overlong UTF-8 sequences starting with c0
            r"%c1%[a-f0-9]{2}",  # Overlong UTF-8 sequences starting with c1
        ]
        for pattern in overlong_patterns:
            if re.search(pattern, path, re.I):
                if ThreatType.PATH_TRAVERSAL not in threats:
                    threats.append(ThreatType.PATH_TRAVERSAL)
                warnings.append("Overlong UTF-8 encoding detected (potential bypass)")
                self._log_threat(ThreatType.PATH_TRAVERSAL, "path", path)
                break

        # Detect double URL encoding (%25 is encoded %)
        if "%25" in path.lower():
            # This indicates double encoding
            if ThreatType.PATH_TRAVERSAL not in threats:
                # Check if decoded version contains traversal
                if ".." in decoded_path:
                    threats.append(ThreatType.PATH_TRAVERSAL)
                    warnings.append("Double URL encoding detected with path traversal")
                    self._log_threat(ThreatType.PATH_TRAVERSAL, "path", path)

        # Check for null bytes
        if "\x00" in path:
            if ThreatType.PATH_TRAVERSAL not in threats:
                threats.append(ThreatType.PATH_TRAVERSAL)
            warnings.append("Null byte detected in path")

        # Build sanitized path: remove null bytes and strip traversal sequences
        sanitized_path = path.replace("\x00", "")
        # Remove .. sequences from sanitized value to prevent traversal
        while ".." in sanitized_path:
            sanitized_path = sanitized_path.replace("..", "")

        # Check if path stays within base directory
        if base_dir:
            try:
                import os

                resolved = os.path.realpath(os.path.join(base_dir, path))
                base_resolved = os.path.realpath(base_dir)
                if not resolved.startswith(base_resolved):
                    if ThreatType.PATH_TRAVERSAL not in threats:
                        threats.append(ThreatType.PATH_TRAVERSAL)
                    warnings.append("Path escapes base directory")
            except Exception:
                if ThreatType.PATH_TRAVERSAL not in threats:
                    threats.append(ThreatType.PATH_TRAVERSAL)
                warnings.append("Unable to resolve path")

        # Check for dangerous filesystem paths (container escape, privilege escalation)
        # Check both original path and decoded/normalized path
        paths_to_check = [path, decoded_path]
        if sanitized_path not in paths_to_check:
            paths_to_check.append(sanitized_path)

        # Also check if traversal resolves to dangerous path
        normalized = self._normalize_path_for_check(decoded_path)
        if normalized and normalized not in paths_to_check:
            paths_to_check.append(normalized)

        for check_path in paths_to_check:
            for pattern in self._dangerous_path_patterns:
                if pattern.search(check_path):
                    if ThreatType.PATH_TRAVERSAL not in threats:
                        threats.append(ThreatType.PATH_TRAVERSAL)
                    warnings.append(f"Dangerous filesystem path blocked: {check_path}")
                    self._log_threat(ThreatType.PATH_TRAVERSAL, "path", path)
                    break

        if threats:
            self._stats["threats_detected"] += 1
            for threat in threats:
                self._stats["by_threat_type"][threat.value] += 1

        return ValidationResult(
            is_valid=len(threats) == 0,
            sanitized_value=sanitized_path,
            threats_detected=threats,
            warnings=warnings,
            original_value=path,
        )

    def validate_url(
        self,
        url: str,
        allow_private: bool = False,
        allowed_schemes: set[str] | None = None,
    ) -> ValidationResult:
        """
        Validate a URL for SSRF and other security issues.

        Args:
            url: URL to validate
            allow_private: Allow private/internal IP addresses
            allowed_schemes: Allowed URL schemes (default: http, https)

        Returns:
            ValidationResult
        """
        self._stats["total_validated"] += 1
        threats = []
        warnings = []

        allowed = allowed_schemes or {"http", "https"}

        try:
            parsed = urlparse(url)

            # Check scheme
            if parsed.scheme.lower() in self.BLOCKED_SCHEMES:
                threats.append(ThreatType.SSRF)
                warnings.append(f"Blocked URL scheme: {parsed.scheme}")
            elif parsed.scheme.lower() not in allowed:
                warnings.append(f"Unexpected URL scheme: {parsed.scheme}")

            # Check for private IP addresses
            if parsed.hostname and not allow_private:
                try:
                    # Resolve hostname to IP
                    ip = socket.gethostbyname(parsed.hostname)
                    ip_addr = ipaddress.ip_address(ip)

                    for network in self.PRIVATE_IP_RANGES:
                        if ip_addr in network:
                            threats.append(ThreatType.SSRF)
                            warnings.append(f"URL resolves to private IP: {ip}")
                            break
                except socket.gaierror:
                    # Can't resolve - might be internal hostname
                    if self._is_internal_hostname(parsed.hostname):
                        threats.append(ThreatType.SSRF)
                        warnings.append(
                            f"Potentially internal hostname: {parsed.hostname}"
                        )

            # Check for URL obfuscation
            if parsed.hostname:
                # Check for decimal IP
                if re.match(r"^\d+$", parsed.hostname):
                    threats.append(ThreatType.SSRF)
                    warnings.append("Decimal IP address detected")

                # Check for hex IP
                if re.match(r"^0x[0-9a-fA-F]+$", parsed.hostname):
                    threats.append(ThreatType.SSRF)
                    warnings.append("Hexadecimal IP address detected")

            # Check for cloud metadata service endpoints
            if parsed.hostname and not allow_private:
                hostname_lower = parsed.hostname.lower()
                if hostname_lower in self.CLOUD_METADATA_HOSTS:
                    threats.append(ThreatType.SSRF)
                    warnings.append(
                        f"Cloud metadata service endpoint blocked: {parsed.hostname}"
                    )
                    self._log_threat(ThreatType.SSRF, "url", url)

            # Check for IPv6 localhost addresses
            if parsed.hostname and not allow_private:
                if self._is_ipv6_localhost(parsed.hostname):
                    threats.append(ThreatType.SSRF)
                    warnings.append(
                        f"IPv6 localhost address blocked: {parsed.hostname}"
                    )
                    self._log_threat(ThreatType.SSRF, "url", url)

            # Check for DNS rebinding service domains
            if parsed.hostname:
                for pattern in self._dns_rebinding_patterns:
                    if pattern.search(parsed.hostname):
                        threats.append(ThreatType.SSRF)
                        warnings.append(
                            f"DNS rebinding service domain detected: {parsed.hostname}"
                        )
                        self._log_threat(ThreatType.SSRF, "url", url)
                        break

            # Check for URL parsing confusion attacks (e.g., http://a]@169.254.169.254/)
            if "]@" in url or "[@" in url:
                threats.append(ThreatType.SSRF)
                warnings.append("URL parsing confusion attack detected")
                self._log_threat(ThreatType.SSRF, "url", url)

        except Exception as e:
            warnings.append(f"URL parsing error: {e}")

        if threats:
            self._stats["threats_detected"] += 1
            for threat in threats:
                self._stats["by_threat_type"][threat.value] += 1

        return ValidationResult(
            is_valid=len(threats) == 0,
            sanitized_value=url,
            threats_detected=threats,
            warnings=warnings,
            original_value=url,
        )

    def validate_email(self, email: str) -> ValidationResult:
        """
        Validate an email address.

        Args:
            email: Email address to validate

        Returns:
            ValidationResult
        """
        self._stats["total_validated"] += 1
        warnings = []

        # Normalize email first (strip whitespace, lowercase)
        normalized_email = email.strip().lower()

        # Basic email pattern
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

        if not re.match(email_pattern, normalized_email):
            warnings.append("Invalid email format")
            return ValidationResult(
                is_valid=False,
                sanitized_value=normalized_email,
                threats_detected=[],
                warnings=warnings,
                original_value=email,
            )

        # Check for injection patterns in email
        threats = []
        if self._check_patterns(normalized_email, self._xss_patterns):
            threats.append(ThreatType.XSS)

        return ValidationResult(
            is_valid=len(threats) == 0,
            sanitized_value=normalized_email,
            threats_detected=threats,
            warnings=warnings,
            original_value=email,
        )

    def validate_json_field(
        self,
        value: Any,
        field_name: str = "field",
        max_depth: int | None = None,
        _current_depth: int = 0,
    ) -> ValidationResult:
        """
        Validate a JSON field value recursively.

        Args:
            value: Value to validate (can be dict, list, or scalar)
            field_name: Name of field for error messages
            max_depth: Maximum allowed nesting depth (default: DEFAULT_MAX_JSON_DEPTH).
                       If exceeded, validation fails with a warning.
            _current_depth: Internal parameter to track recursion depth

        Returns:
            ValidationResult
        """
        max_depth = max_depth if max_depth is not None else DEFAULT_MAX_JSON_DEPTH

        # Check depth limit
        if _current_depth > max_depth:
            return ValidationResult(
                is_valid=False,
                sanitized_value=value,
                threats_detected=[],
                warnings=[
                    f"JSON nesting depth exceeds maximum allowed depth of {max_depth}"
                ],
                original_value=value,
            )

        if isinstance(value, str):
            return self.validate_string(value, field_name)
        elif isinstance(value, dict):
            return self._validate_dict(
                value, field_name, max_depth=max_depth, _current_depth=_current_depth
            )
        elif isinstance(value, list):
            return self._validate_list(
                value, field_name, max_depth=max_depth, _current_depth=_current_depth
            )
        else:
            # Scalar values (int, float, bool, None) are safe
            return ValidationResult(
                is_valid=True,
                sanitized_value=value,
                threats_detected=[],
                warnings=[],
                original_value=value,
            )

    def _validate_dict(
        self,
        d: dict,
        field_name: str,
        max_depth: int | None = None,
        _current_depth: int = 0,
    ) -> ValidationResult:
        """Validate dictionary recursively."""
        all_threats = []
        all_warnings = []
        sanitized = {}
        max_depth = max_depth if max_depth is not None else DEFAULT_MAX_JSON_DEPTH

        for key, value in d.items():
            # Validate key
            key_result = self.validate_string(str(key), f"{field_name}.key")
            all_threats.extend(key_result.threats_detected)
            all_warnings.extend(key_result.warnings)

            # Validate value with depth tracking
            value_result = self.validate_json_field(
                value,
                f"{field_name}.{key}",
                max_depth=max_depth,
                _current_depth=_current_depth + 1,
            )
            all_threats.extend(value_result.threats_detected)
            all_warnings.extend(value_result.warnings)
            sanitized[key] = value_result.sanitized_value

            # If value validation failed due to depth, propagate failure
            if not value_result.is_valid:
                return ValidationResult(
                    is_valid=False,
                    sanitized_value=sanitized,
                    threats_detected=list(set(all_threats)),
                    warnings=all_warnings,
                    original_value=d,
                )

        return ValidationResult(
            is_valid=len(all_threats) == 0 or not self.strict_mode,
            sanitized_value=sanitized,
            threats_detected=list(set(all_threats)),
            warnings=all_warnings,
            original_value=d,
        )

    def _validate_list(
        self,
        lst: list,
        field_name: str,
        max_depth: int | None = None,
        _current_depth: int = 0,
    ) -> ValidationResult:
        """Validate list recursively."""
        all_threats = []
        all_warnings = []
        sanitized = []
        max_depth = max_depth if max_depth is not None else DEFAULT_MAX_JSON_DEPTH

        for i, item in enumerate(lst):
            result = self.validate_json_field(
                item,
                f"{field_name}[{i}]",
                max_depth=max_depth,
                _current_depth=_current_depth + 1,
            )
            all_threats.extend(result.threats_detected)
            all_warnings.extend(result.warnings)
            sanitized.append(result.sanitized_value)

            # If item validation failed due to depth, propagate failure
            if not result.is_valid:
                return ValidationResult(
                    is_valid=False,
                    sanitized_value=sanitized,
                    threats_detected=list(set(all_threats)),
                    warnings=all_warnings,
                    original_value=lst,
                )

        return ValidationResult(
            is_valid=len(all_threats) == 0 or not self.strict_mode,
            sanitized_value=sanitized,
            threats_detected=list(set(all_threats)),
            warnings=all_warnings,
            original_value=lst,
        )

    def _check_patterns(self, value: str, patterns: list[re.Pattern]) -> bool:
        """Check if value matches any pattern."""
        for pattern in patterns:
            if pattern.search(value):
                return True
        return False

    def _sanitize_string(self, value: str) -> str:
        """Basic string sanitization."""
        # Remove null bytes
        sanitized = value.replace("\x00", "")
        # HTML encode dangerous characters
        sanitized = (
            sanitized.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
        )
        return sanitized

    def _is_internal_hostname(self, hostname: str) -> bool:
        """Check if hostname looks internal."""
        internal_patterns = [
            r"localhost",
            r"\.local$",
            r"\.internal$",
            r"\.corp$",
            r"\.lan$",
            r"^10\.",
            r"^192\.168\.",
            r"^172\.(1[6-9]|2[0-9]|3[0-1])\.",
            r"^127\.",
        ]
        hostname_lower = hostname.lower()
        for pattern in internal_patterns:
            if re.search(pattern, hostname_lower):
                return True
        return False

    def _normalize_path_for_check(self, path: str) -> str | None:
        """
        Normalize a path for dangerous path checking.

        Resolves traversal sequences (.., .) to determine where the path
        would actually point. Handles paths starting with traversal sequences
        by assuming they would resolve from a typical working directory.

        Returns:
            Normalized absolute path, or None if path cannot be normalized
        """
        if not path:
            return None

        try:
            import os

            # If path starts with traversal, assume it's relative to root
            # for security checking purposes
            if path.startswith(".."):
                # Remove leading traversals and treat remaining as absolute
                parts = path.split("/")
                # Count leading ".." segments
                traversal_count = 0
                for part in parts:
                    if part == "..":
                        traversal_count += 1
                    elif part == ".":
                        continue
                    else:
                        break

                # Get the remaining path after traversals
                remaining = "/".join(parts[traversal_count:])
                if remaining:
                    return "/" + remaining.lstrip("/")
                return None

            # For absolute paths, just normalize
            if path.startswith("/"):
                return os.path.normpath(path)

            return None
        except Exception:
            return None

    def _is_ipv6_localhost(self, hostname: str) -> bool:
        """
        Check if hostname is an IPv6 localhost address.

        Detects various forms of IPv6 localhost:
        - [::1] - Short form loopback
        - [0:0:0:0:0:0:0:1] - Full form loopback
        - [::ffff:127.0.0.1] - IPv4-mapped IPv6 loopback
        """
        # Remove brackets if present
        if hostname.startswith("[") and hostname.endswith("]"):
            hostname = hostname[1:-1]

        try:
            # Parse as IPv6 address
            addr = ipaddress.ip_address(hostname)

            # Check for IPv6 loopback
            if addr == ipaddress.ip_address("::1"):
                return True

            # Check for IPv4-mapped IPv6 loopback (::ffff:127.0.0.1)
            if isinstance(addr, ipaddress.IPv6Address):
                # Check if it's an IPv4-mapped address pointing to localhost
                ipv4_mapped = addr.ipv4_mapped
                if ipv4_mapped and ipv4_mapped.is_loopback:
                    return True

        except ValueError:
            # Not a valid IP address
            pass

        return False

    def _log_threat(self, threat_type: ThreatType, field: str, value: str) -> None:
        """Log detected threat."""
        if self.log_threats:
            # Truncate value for logging
            truncated = value[:100] + "..." if len(value) > 100 else value
            logger.warning(
                f"Security threat detected: type={threat_type.value} "
                f"field={field} value={truncated!r}"
            )

    def get_stats(self) -> dict[str, Any]:
        """Get validation statistics."""
        return dict(self._stats)

    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = {
            "total_validated": 0,
            "threats_detected": 0,
            "by_threat_type": {t.value: 0 for t in ThreatType},
        }


# =============================================================================
# Singleton Instance
# =============================================================================

_validator: InputValidator | None = None


def get_input_validator() -> InputValidator:
    """Get singleton input validator instance."""
    global _validator
    if _validator is None:
        _validator = InputValidator(strict_mode=False, log_threats=True)
    return _validator


def validate_input(value: str, field_name: str = "input") -> ValidationResult:
    """Convenience function to validate string input."""
    return get_input_validator().validate_string(value, field_name)


def validate_path(path: str, base_dir: str | None = None) -> ValidationResult:
    """Convenience function to validate file path."""
    return get_input_validator().validate_path(path, base_dir)


def validate_url(url: str, allow_private: bool = False) -> ValidationResult:
    """Convenience function to validate URL."""
    return get_input_validator().validate_url(url, allow_private)
