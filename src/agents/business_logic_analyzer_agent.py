"""
Project Aura - Business Logic Vulnerability Analyzer Agent

Detects context-specific vulnerabilities that require understanding of
application logic, including IDOR, race conditions, authorization bypasses,
and business rule violations.

Part of AWS Security Agent capability parity (ADR-019 Gap 4).

Author: Project Aura Team
Created: 2025-12-03
Version: 1.0.0
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from src.services.authorization_flow_analyzer import (
    AuthorizationFlow,
    AuthorizationGap,
    create_authorization_flow_analyzer,
)

logger = logging.getLogger(__name__)


class VulnerabilityType(Enum):
    """Types of business logic vulnerabilities."""

    IDOR = "idor"  # Insecure Direct Object Reference
    RACE_CONDITION = "race_condition"
    IMPROPER_AUTHORIZATION = "improper_authorization"
    BUSINESS_RULE_BYPASS = "business_rule_bypass"
    MASS_ASSIGNMENT = "mass_assignment"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    INSUFFICIENT_WORKFLOW = "insufficient_workflow"


class Severity(Enum):
    """Vulnerability severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class BusinessLogicFinding:
    """A business logic vulnerability finding."""

    finding_id: str
    vulnerability_type: VulnerabilityType
    severity: Severity
    title: str
    description: str
    file_path: str
    line_number: int
    code_snippet: str
    recommendation: str
    cwe_ids: list[str] = field(default_factory=list)
    nist_controls: list[str] = field(default_factory=list)
    confidence: float = 0.8
    affected_functions: list[str] = field(default_factory=list)
    discovered_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "finding_id": self.finding_id,
            "vulnerability_type": self.vulnerability_type.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "code_snippet": self.code_snippet,
            "recommendation": self.recommendation,
            "cwe_ids": self.cwe_ids,
            "nist_controls": self.nist_controls,
            "confidence": self.confidence,
            "affected_functions": self.affected_functions,
            "discovered_at": self.discovered_at,
        }


@dataclass
class AnalysisResult:
    """Result of business logic analysis."""

    total_files_analyzed: int
    total_functions_analyzed: int
    findings: list[BusinessLogicFinding]
    authorization_flows: list[AuthorizationFlow]
    authorization_gaps: list[AuthorizationGap]
    analysis_duration_seconds: float
    risk_score: float


# =============================================================================
# Detection Patterns
# =============================================================================


IDOR_PATTERNS = [
    # Direct ID usage from request without validation
    (
        r"request\.(?:args|form|json|params)(?:\[['\"]|\.get\(['\"])(\w*[iI][dD]\w*)",
        "Direct ID from request",
    ),
    # Route parameters with ID
    (r"<(?:int:)?(\w*[iI][dD]\w*)>", "Route parameter with ID"),
    # Query by ID without owner check
    (r"\.get\s*\(\s*(\w+_id)\s*\)", "Get by ID without owner validation"),
]

RACE_CONDITION_PATTERNS = [
    # Check-then-act patterns
    (
        r"if\s+(\w+)\.(?:exists|count|balance|quantity).*:\s*\n.*\1\.(?:save|update|delete)",
        "Check-then-act pattern",
    ),
    # Non-atomic read-modify-write
    (r"(\w+)\s*=\s*\w+\.get\(.*\n.*\1\s*(?:\+|\-)=", "Non-atomic update"),
    # Balance/quantity checks followed by modification
    (
        r"if\s+\w+\.(?:balance|quantity|stock)\s*>=?.*:\s*\n.*\.(?:balance|quantity|stock)\s*-=",
        "Balance check-then-modify",
    ),
]

MASS_ASSIGNMENT_PATTERNS = [
    # Direct dictionary/JSON to model
    (
        r"(\w+)\s*=\s*\w+Model\s*\(\s*\*\*(?:request\.json|data|payload)",
        "Direct mass assignment to model",
    ),
    # Update with unfiltered input
    (
        r"\.update\s*\(\s*\*\*(?:request\.json|data|payload)",
        "Update with unfiltered input",
    ),
    # Setattr from request
    (r"setattr\s*\(\s*\w+,\s*\w+,\s*request\.", "Setattr from request data"),
]

PRIVILEGE_ESCALATION_PATTERNS = [
    # Role/admin in request without validation
    (
        r"request\.(?:json|form|data)(?:\[['\"]|\.get\(['\"])(?:role|is_admin|permission)",
        "Role from request without validation",
    ),
    # Self-promotion patterns
    (
        r"user\.(?:role|is_admin|permissions?)\s*=\s*request\.",
        "User privilege from request",
    ),
]

WORKFLOW_BYPASS_PATTERNS = [
    # Status changes without validation
    (
        r"\.(?:status|state)\s*=\s*['\"](?:approved|completed|paid)['\"]",
        "Direct status change to approved state",
    ),
    # Skipping steps
    (r"skip_(?:validation|verification|approval)", "Explicit step skip"),
]


# =============================================================================
# CWE Mappings
# =============================================================================


CWE_MAPPINGS = {
    VulnerabilityType.IDOR: ["CWE-639", "CWE-284"],
    VulnerabilityType.RACE_CONDITION: ["CWE-362", "CWE-367"],
    VulnerabilityType.IMPROPER_AUTHORIZATION: ["CWE-285", "CWE-862", "CWE-863"],
    VulnerabilityType.BUSINESS_RULE_BYPASS: ["CWE-840"],
    VulnerabilityType.MASS_ASSIGNMENT: ["CWE-915"],
    VulnerabilityType.PRIVILEGE_ESCALATION: ["CWE-269", "CWE-266"],
    VulnerabilityType.INSUFFICIENT_WORKFLOW: ["CWE-841"],
}

NIST_MAPPINGS = {
    VulnerabilityType.IDOR: ["AC-3", "AC-4"],
    VulnerabilityType.RACE_CONDITION: ["SC-4"],
    VulnerabilityType.IMPROPER_AUTHORIZATION: ["AC-2", "AC-3", "AC-6"],
    VulnerabilityType.MASS_ASSIGNMENT: ["AC-3", "CM-7"],
    VulnerabilityType.PRIVILEGE_ESCALATION: ["AC-5", "AC-6"],
}


class BusinessLogicAnalyzerAgent:
    """
    Agent for detecting business logic vulnerabilities.

    Uses pattern matching and graph analysis to detect:
    - IDOR (Insecure Direct Object Reference)
    - Race conditions
    - Authorization bypasses
    - Business rule violations
    - Mass assignment vulnerabilities
    - Privilege escalation

    Usage:
        agent = BusinessLogicAnalyzerAgent(neptune_service, llm_client)
        findings = await agent.analyze_file("src/api/users.py", content)
        result = await agent.analyze_repository("src/")
    """

    def __init__(
        self,
        neptune_service: Any = None,
        llm_client: Any = None,
        use_llm_analysis: bool = True,
    ):
        """
        Initialize the Business Logic Analyzer Agent.

        Args:
            neptune_service: Neptune graph service for flow analysis
            llm_client: LLM service for advanced detection
            use_llm_analysis: Enable LLM-based analysis
        """
        self.neptune = neptune_service
        self.llm = llm_client
        self.use_llm_analysis = use_llm_analysis and llm_client is not None

        # Initialize authorization flow analyzer
        self.auth_analyzer = create_authorization_flow_analyzer(
            neptune_service=neptune_service,
            use_mock=neptune_service is None,
        )

        self._finding_counter = 0

    def _generate_finding_id(self) -> str:
        """Generate unique finding ID."""
        self._finding_counter += 1
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"BLF-{timestamp}-{self._finding_counter:04d}"

    async def analyze_file(
        self,
        file_path: str,
        content: str | None = None,
    ) -> list[BusinessLogicFinding]:
        """
        Analyze a single file for business logic vulnerabilities.

        Args:
            file_path: Path to the file
            content: Optional pre-loaded content

        Returns:
            List of findings
        """
        # Load content if not provided
        if content is None:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                logger.error(f"Failed to read file {file_path}: {e}")
                return []

        findings: list[BusinessLogicFinding] = []

        # Pattern-based detection
        findings.extend(self._detect_idor(file_path, content))
        findings.extend(self._detect_race_conditions(file_path, content))
        findings.extend(self._detect_mass_assignment(file_path, content))
        findings.extend(self._detect_privilege_escalation(file_path, content))
        findings.extend(self._detect_workflow_bypass(file_path, content))

        # Authorization flow analysis
        auth_flows = await self.auth_analyzer.analyze_file(file_path, content)
        auth_gaps = await self.auth_analyzer.find_authorization_gaps(auth_flows)

        # Convert auth gaps to findings
        for gap in auth_gaps:
            findings.append(self._gap_to_finding(gap))

        # LLM-enhanced analysis
        if self.use_llm_analysis:
            llm_findings = await self._llm_analysis(file_path, content)
            findings.extend(llm_findings)

        # Deduplicate
        findings = self._deduplicate_findings(findings)

        logger.info(f"Analyzed {file_path}: found {len(findings)} issues")
        return findings

    async def analyze_repository(
        self,
        repo_path: str,
        file_patterns: list[str] | None = None,
    ) -> AnalysisResult:
        """
        Analyze all relevant files in a repository.

        Args:
            repo_path: Path to repository root
            file_patterns: Glob patterns for files to analyze

        Returns:
            Complete analysis result
        """
        start_time = datetime.now(timezone.utc)

        if file_patterns is None:
            file_patterns = [
                "**/*.py",  # Python files
                "**/api/**/*.py",  # API endpoints
                "**/routes/**/*.py",  # Route handlers
                "**/views/**/*.py",  # View handlers
                "**/controllers/**/*.py",  # Controllers
            ]

        repo = Path(repo_path)
        all_findings: list[BusinessLogicFinding] = []
        all_flows: list[AuthorizationFlow] = []
        all_gaps: list[AuthorizationGap] = []
        files_analyzed = 0
        functions_analyzed = 0

        for pattern in file_patterns:
            for file_path in repo.glob(pattern):
                if file_path.is_file() and not self._should_skip_file(str(file_path)):
                    try:
                        content = file_path.read_text(encoding="utf-8")
                        files_analyzed += 1

                        # Count functions
                        functions_analyzed += len(
                            re.findall(r"(?:def|async def)\s+\w+\s*\(", content)
                        )

                        # Analyze file
                        findings = await self.analyze_file(str(file_path), content)
                        all_findings.extend(findings)

                        # Get auth flows
                        flows = await self.auth_analyzer.analyze_file(
                            str(file_path), content
                        )
                        all_flows.extend(flows)

                        gaps = await self.auth_analyzer.find_authorization_gaps(flows)
                        all_gaps.extend(gaps)

                    except Exception as e:
                        logger.error(f"Failed to analyze {file_path}: {e}")

        # Calculate risk score
        risk_score = self._calculate_risk_score(all_findings)

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()

        return AnalysisResult(
            total_files_analyzed=files_analyzed,
            total_functions_analyzed=functions_analyzed,
            findings=all_findings,
            authorization_flows=all_flows,
            authorization_gaps=all_gaps,
            analysis_duration_seconds=duration,
            risk_score=risk_score,
        )

    def _should_skip_file(self, file_path: str) -> bool:
        """Check if file should be skipped."""
        skip_patterns = [
            "test_",
            "_test.py",
            "tests/",
            "__pycache__",
            "migrations/",
            ".venv/",
            "venv/",
            "node_modules/",
        ]
        return any(pattern in file_path for pattern in skip_patterns)

    def _detect_idor(
        self,
        file_path: str,
        content: str,
    ) -> list[BusinessLogicFinding]:
        """Detect IDOR vulnerabilities."""
        findings: list[BusinessLogicFinding] = []

        for pattern, description in IDOR_PATTERNS:
            for match in re.finditer(pattern, content):
                line_number = content[: match.start()].count("\n") + 1
                snippet = self._get_code_snippet(content, line_number)

                # Check if there's an ownership check nearby
                context = content[max(0, match.start() - 500) : match.end() + 500]
                has_owner_check = any(
                    check in context.lower()
                    for check in ["owner", "belongs_to", "user.id ==", "current_user"]
                )

                if not has_owner_check:
                    findings.append(
                        BusinessLogicFinding(
                            finding_id=self._generate_finding_id(),
                            vulnerability_type=VulnerabilityType.IDOR,
                            severity=Severity.CRITICAL,
                            title="Potential IDOR Vulnerability",
                            description=f"{description}: '{match.group(0)}' - ID used without ownership verification",
                            file_path=file_path,
                            line_number=line_number,
                            code_snippet=snippet,
                            recommendation="Verify that the current user owns or has access to the resource before retrieval. Add ownership check: if resource.owner_id != current_user.id: raise Forbidden()",
                            cwe_ids=CWE_MAPPINGS[VulnerabilityType.IDOR],
                            nist_controls=NIST_MAPPINGS[VulnerabilityType.IDOR],
                            confidence=0.85,
                        )
                    )

        return findings

    def _detect_race_conditions(
        self,
        file_path: str,
        content: str,
    ) -> list[BusinessLogicFinding]:
        """Detect race condition vulnerabilities."""
        findings: list[BusinessLogicFinding] = []

        for pattern, description in RACE_CONDITION_PATTERNS:
            for match in re.finditer(pattern, content, re.MULTILINE):
                line_number = content[: match.start()].count("\n") + 1
                snippet = self._get_code_snippet(content, line_number, context=5)

                # Check for locking mechanisms
                context = content[max(0, match.start() - 300) : match.end() + 300]
                has_lock = any(
                    lock in context.lower()
                    for lock in [
                        "lock",
                        "mutex",
                        "semaphore",
                        "atomic",
                        "transaction",
                        "with_for_update",
                    ]
                )

                if not has_lock:
                    findings.append(
                        BusinessLogicFinding(
                            finding_id=self._generate_finding_id(),
                            vulnerability_type=VulnerabilityType.RACE_CONDITION,
                            severity=Severity.HIGH,
                            title="Potential Race Condition",
                            description=f"{description} detected without synchronization",
                            file_path=file_path,
                            line_number=line_number,
                            code_snippet=snippet,
                            recommendation="Use database transactions with SELECT FOR UPDATE, or implement proper locking mechanisms to prevent race conditions",
                            cwe_ids=CWE_MAPPINGS[VulnerabilityType.RACE_CONDITION],
                            nist_controls=NIST_MAPPINGS.get(
                                VulnerabilityType.RACE_CONDITION, []
                            ),
                            confidence=0.75,
                        )
                    )

        return findings

    def _detect_mass_assignment(
        self,
        file_path: str,
        content: str,
    ) -> list[BusinessLogicFinding]:
        """Detect mass assignment vulnerabilities."""
        findings: list[BusinessLogicFinding] = []

        for pattern, description in MASS_ASSIGNMENT_PATTERNS:
            for match in re.finditer(pattern, content):
                line_number = content[: match.start()].count("\n") + 1
                snippet = self._get_code_snippet(content, line_number)

                findings.append(
                    BusinessLogicFinding(
                        finding_id=self._generate_finding_id(),
                        vulnerability_type=VulnerabilityType.MASS_ASSIGNMENT,
                        severity=Severity.HIGH,
                        title="Mass Assignment Vulnerability",
                        description=f"{description}: attacker could modify protected fields",
                        file_path=file_path,
                        line_number=line_number,
                        code_snippet=snippet,
                        recommendation="Use explicit field whitelisting instead of **kwargs. Define allowed_fields and filter input: Model(**{k:v for k,v in data.items() if k in allowed_fields})",
                        cwe_ids=CWE_MAPPINGS[VulnerabilityType.MASS_ASSIGNMENT],
                        nist_controls=NIST_MAPPINGS.get(
                            VulnerabilityType.MASS_ASSIGNMENT, []
                        ),
                        confidence=0.9,
                    )
                )

        return findings

    def _detect_privilege_escalation(
        self,
        file_path: str,
        content: str,
    ) -> list[BusinessLogicFinding]:
        """Detect privilege escalation vulnerabilities."""
        findings: list[BusinessLogicFinding] = []

        for pattern, description in PRIVILEGE_ESCALATION_PATTERNS:
            for match in re.finditer(pattern, content):
                line_number = content[: match.start()].count("\n") + 1
                snippet = self._get_code_snippet(content, line_number)

                findings.append(
                    BusinessLogicFinding(
                        finding_id=self._generate_finding_id(),
                        vulnerability_type=VulnerabilityType.PRIVILEGE_ESCALATION,
                        severity=Severity.CRITICAL,
                        title="Privilege Escalation Risk",
                        description=f"{description}: user could escalate their own privileges",
                        file_path=file_path,
                        line_number=line_number,
                        code_snippet=snippet,
                        recommendation="Never allow users to set their own roles or permissions from request data. Use server-side authorization and admin-only endpoints for privilege changes.",
                        cwe_ids=CWE_MAPPINGS[VulnerabilityType.PRIVILEGE_ESCALATION],
                        nist_controls=NIST_MAPPINGS.get(
                            VulnerabilityType.PRIVILEGE_ESCALATION, []
                        ),
                        confidence=0.9,
                    )
                )

        return findings

    def _detect_workflow_bypass(
        self,
        file_path: str,
        content: str,
    ) -> list[BusinessLogicFinding]:
        """Detect business workflow bypass vulnerabilities."""
        findings: list[BusinessLogicFinding] = []

        for pattern, description in WORKFLOW_BYPASS_PATTERNS:
            for match in re.finditer(pattern, content):
                line_number = content[: match.start()].count("\n") + 1
                snippet = self._get_code_snippet(content, line_number)

                # Check for proper state machine
                context = content[max(0, match.start() - 500) : match.end() + 500]
                has_state_machine = any(
                    sm in context.lower()
                    for sm in [
                        "state_machine",
                        "transition",
                        "allowed_transitions",
                        "valid_transitions",
                    ]
                )

                if not has_state_machine:
                    findings.append(
                        BusinessLogicFinding(
                            finding_id=self._generate_finding_id(),
                            vulnerability_type=VulnerabilityType.BUSINESS_RULE_BYPASS,
                            severity=Severity.MEDIUM,
                            title="Potential Workflow Bypass",
                            description=f"{description} without state validation",
                            file_path=file_path,
                            line_number=line_number,
                            code_snippet=snippet,
                            recommendation="Implement a proper state machine with defined transitions. Validate that the current state allows the requested transition.",
                            cwe_ids=CWE_MAPPINGS[
                                VulnerabilityType.BUSINESS_RULE_BYPASS
                            ],
                            nist_controls=[],
                            confidence=0.7,
                        )
                    )

        return findings

    def _gap_to_finding(self, gap: AuthorizationGap) -> BusinessLogicFinding:
        """Convert an authorization gap to a finding."""
        return BusinessLogicFinding(
            finding_id=self._generate_finding_id(),
            vulnerability_type=VulnerabilityType.IMPROPER_AUTHORIZATION,
            severity=Severity[gap.severity],
            title=f"Authorization Gap: {gap.gap_type}",
            description=gap.description,
            file_path=gap.flow.entry_point.file_path,
            line_number=gap.flow.entry_point.line_number,
            code_snippet=f"Function: {gap.flow.entry_point.name}",
            recommendation=gap.recommendation,
            cwe_ids=gap.cwe_ids,
            nist_controls=NIST_MAPPINGS.get(
                VulnerabilityType.IMPROPER_AUTHORIZATION, []
            ),
            confidence=gap.flow.confidence,
            affected_functions=[gap.flow.entry_point.name],
        )

    def _get_code_snippet(
        self,
        content: str,
        line_number: int,
        context: int = 3,
    ) -> str:
        """Get code snippet around line number."""
        lines = content.split("\n")
        start = max(0, line_number - context - 1)
        end = min(len(lines), line_number + context)
        return "\n".join(lines[start:end])

    async def _llm_analysis(
        self,
        file_path: str,
        content: str,
    ) -> list[BusinessLogicFinding]:
        """Use LLM for advanced business logic analysis."""
        if not self.llm:
            return []

        findings: list[BusinessLogicFinding] = []

        # Truncate if too long
        max_length = 8000
        if len(content) > max_length:
            content = content[:max_length] + "\n... [truncated]"

        prompt = f"""Analyze this code for business logic vulnerabilities:

```python
{content}
```

Look for:
1. IDOR - accessing resources by ID without ownership checks
2. Race conditions - check-then-act patterns, non-atomic operations
3. Authorization bypasses - missing or weak access controls
4. Business rule violations - workflow bypasses, state manipulation
5. Mass assignment - unfiltered user input to models
6. Privilege escalation - users setting their own roles

For each issue found, provide:
- type: One of (idor, race_condition, improper_authorization, business_rule_bypass, mass_assignment, privilege_escalation)
- severity: One of (CRITICAL, HIGH, MEDIUM, LOW)
- title: Brief title
- description: 1-2 sentences
- line_number: Approximate line number
- recommendation: How to fix

Format as JSON array. Return [] if no issues found."""

        try:
            response = await self.llm.generate(prompt)

            # Parse response
            import json

            json_match = re.search(r"\[[\s\S]*?\]", response)
            if json_match:
                issues = json.loads(json_match.group())

                type_map = {
                    "idor": VulnerabilityType.IDOR,
                    "race_condition": VulnerabilityType.RACE_CONDITION,
                    "improper_authorization": VulnerabilityType.IMPROPER_AUTHORIZATION,
                    "business_rule_bypass": VulnerabilityType.BUSINESS_RULE_BYPASS,
                    "mass_assignment": VulnerabilityType.MASS_ASSIGNMENT,
                    "privilege_escalation": VulnerabilityType.PRIVILEGE_ESCALATION,
                }

                severity_map = {
                    "critical": Severity.CRITICAL,
                    "high": Severity.HIGH,
                    "medium": Severity.MEDIUM,
                    "low": Severity.LOW,
                }

                for issue in issues:
                    vuln_type = type_map.get(
                        issue.get("type", "").lower(),
                        VulnerabilityType.IMPROPER_AUTHORIZATION,
                    )
                    severity = severity_map.get(
                        issue.get("severity", "").lower(), Severity.MEDIUM
                    )

                    findings.append(
                        BusinessLogicFinding(
                            finding_id=self._generate_finding_id(),
                            vulnerability_type=vuln_type,
                            severity=severity,
                            title=issue.get("title", "Security Issue"),
                            description=issue.get("description", ""),
                            file_path=file_path,
                            line_number=issue.get("line_number", 0),
                            code_snippet="LLM analysis",
                            recommendation=issue.get("recommendation", ""),
                            cwe_ids=CWE_MAPPINGS.get(vuln_type, []),
                            nist_controls=NIST_MAPPINGS.get(vuln_type, []),
                            confidence=0.7,  # Lower confidence for LLM findings
                        )
                    )

        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")

        return findings

    def _calculate_risk_score(
        self,
        findings: list[BusinessLogicFinding],
    ) -> float:
        """Calculate total risk score from findings."""
        severity_weights = {
            Severity.CRITICAL: 10.0,
            Severity.HIGH: 5.0,
            Severity.MEDIUM: 2.0,
            Severity.LOW: 1.0,
        }

        total = sum(severity_weights[f.severity] * f.confidence for f in findings)

        return min(100.0, total)

    def _deduplicate_findings(
        self,
        findings: list[BusinessLogicFinding],
    ) -> list[BusinessLogicFinding]:
        """Remove duplicate findings."""
        seen: set[tuple[str, int, str]] = set()
        unique: list[BusinessLogicFinding] = []

        for finding in findings:
            key = (
                finding.file_path,
                finding.line_number,
                finding.vulnerability_type.value,
            )
            if key not in seen:
                seen.add(key)
                unique.append(finding)

        return unique


# =============================================================================
# Factory Function
# =============================================================================


def create_business_logic_analyzer(
    neptune_service: Any = None,
    llm_client: Any = None,
    use_llm_analysis: bool = True,
) -> BusinessLogicAnalyzerAgent:
    """
    Create a BusinessLogicAnalyzerAgent instance.

    Args:
        neptune_service: Neptune graph service for flow analysis
        llm_client: LLM service for advanced detection
        use_llm_analysis: Enable LLM-based analysis

    Returns:
        Configured BusinessLogicAnalyzerAgent
    """
    return BusinessLogicAnalyzerAgent(
        neptune_service=neptune_service,
        llm_client=llm_client,
        use_llm_analysis=use_llm_analysis,
    )
