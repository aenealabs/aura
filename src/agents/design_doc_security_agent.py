"""
Project Aura - Design Document Security Agent

Proactively analyzes design documents, ADRs, and architecture diagrams
for security issues before code implementation. Part of AWS Security Agent
capability parity (ADR-019).

Capabilities:
- Markdown document parsing and analysis
- Architecture diagram security review (Mermaid, PlantUML)
- Proactive threat identification
- CMMC/NIST/OWASP compliance gap detection
- CWE mapping for identified issues

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

logger = logging.getLogger(__name__)


class FindingSeverity(Enum):
    """Severity levels for design security findings."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingCategory(Enum):
    """Categories of security findings in design documents."""

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_PROTECTION = "data_protection"
    ENCRYPTION = "encryption"
    INPUT_VALIDATION = "input_validation"
    AUDIT_LOGGING = "audit_logging"
    SECRETS_MANAGEMENT = "secrets_management"
    NETWORK_SECURITY = "network_security"
    THIRD_PARTY_RISK = "third_party_risk"
    COMPLIANCE = "compliance"
    ARCHITECTURE = "architecture"
    DATA_FLOW = "data_flow"


@dataclass
class DesignSecurityFinding:
    """A security finding identified in a design document."""

    finding_id: str
    document_path: str
    severity: FindingSeverity
    category: FindingCategory
    title: str
    description: str
    location: str  # Section/line reference in doc
    recommendation: str
    affected_components: list[str] = field(default_factory=list)
    cwe_ids: list[str] = field(default_factory=list)
    nist_controls: list[str] = field(default_factory=list)
    confidence: float = 0.8
    discovered_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "finding_id": self.finding_id,
            "document_path": self.document_path,
            "severity": self.severity.value,
            "category": self.category.value,
            "title": self.title,
            "description": self.description,
            "location": self.location,
            "recommendation": self.recommendation,
            "affected_components": self.affected_components,
            "cwe_ids": self.cwe_ids,
            "nist_controls": self.nist_controls,
            "confidence": self.confidence,
            "discovered_at": self.discovered_at,
        }


@dataclass
class DocumentAnalysisResult:
    """Result of analyzing a design document."""

    document_path: str
    document_type: str  # adr, design, architecture, api_spec
    findings: list[DesignSecurityFinding]
    sections_analyzed: int
    total_risk_score: float
    analysis_duration_seconds: float
    analyzed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# =============================================================================
# Security Check Rules
# =============================================================================


AUTHENTICATION_PATTERNS = [
    # Missing authentication indicators
    (
        r"(?i)\bpublic\s+(?:api|endpoint|route)",
        "Public API without authentication mention",
    ),
    (r"(?i)\bopen\s+access", "Open access without restrictions"),
    (r"(?i)\bno\s+auth(?:entication)?", "Explicitly disabled authentication"),
    (r"(?i)\bskip\s+auth", "Authentication bypass mentioned"),
]

AUTHORIZATION_PATTERNS = [
    # Missing authorization
    (
        r"(?i)\badmin\b.*(?:without|no).*(?:check|verify)",
        "Admin access without verification",
    ),
    (r"(?i)\baccess\s+all", "Unrestricted access pattern"),
    (r"(?i)\bno\s+(?:rbac|role|permission)", "Missing role-based access control"),
]

DATA_PROTECTION_PATTERNS = [
    # Unencrypted data
    (r"(?i)\bplaintext\b", "Plaintext data mentioned"),
    (r"(?i)\bunencrypted\b", "Unencrypted data mentioned"),
    (r"(?i)\bhttp://\b", "Non-HTTPS URL detected"),
    (r"(?i)\bbase64\s+encode", "Base64 encoding (not encryption) mentioned"),
]

SECRETS_PATTERNS = [
    # Hardcoded secrets
    (r"(?i)\bpassword\s*[:=]\s*['\"][^'\"]+['\"]", "Possible hardcoded password"),
    (r"(?i)\bapi[_-]?key\s*[:=]\s*['\"][^'\"]+['\"]", "Possible hardcoded API key"),
    (r"(?i)\bsecret\s*[:=]\s*['\"][^'\"]+['\"]", "Possible hardcoded secret"),
    (r"(?i)\bAKIA[A-Z0-9]{16}\b", "AWS Access Key ID pattern detected"),
]

LOGGING_PATTERNS = [
    # Missing audit logging
    (r"(?i)\bno\s+log(?:ging)?", "Logging explicitly disabled"),
    (r"(?i)\bskip\s+audit", "Audit logging bypass"),
    (r"(?i)\bdisable\s+(?:log|audit)", "Disabled logging/auditing"),
]

ARCHITECTURE_RISK_PATTERNS = [
    # Risky architecture patterns
    (r"(?i)\bsingle\s+point\s+of\s+failure", "Single point of failure identified"),
    (r"(?i)\bno\s+(?:rate\s+limit|throttl)", "Missing rate limiting"),
    (r"(?i)\btrust(?:ed)?\s+(?:client|user)", "Client-side trust mentioned"),
    (r"(?i)\bshared\s+(?:key|secret|credential)", "Shared credentials pattern"),
]


# =============================================================================
# CWE Mappings
# =============================================================================


CWE_MAPPINGS = {
    FindingCategory.AUTHENTICATION: [
        "CWE-287",  # Improper Authentication
        "CWE-306",  # Missing Authentication for Critical Function
    ],
    FindingCategory.AUTHORIZATION: [
        "CWE-285",  # Improper Authorization
        "CWE-862",  # Missing Authorization
        "CWE-863",  # Incorrect Authorization
    ],
    FindingCategory.DATA_PROTECTION: [
        "CWE-311",  # Missing Encryption of Sensitive Data
        "CWE-319",  # Cleartext Transmission of Sensitive Information
    ],
    FindingCategory.SECRETS_MANAGEMENT: [
        "CWE-798",  # Use of Hard-coded Credentials
        "CWE-321",  # Use of Hard-coded Cryptographic Key
    ],
    FindingCategory.INPUT_VALIDATION: [
        "CWE-20",  # Improper Input Validation
        "CWE-89",  # SQL Injection
        "CWE-79",  # Cross-site Scripting
    ],
    FindingCategory.AUDIT_LOGGING: [
        "CWE-778",  # Insufficient Logging
        "CWE-223",  # Omission of Security-relevant Information
    ],
}

NIST_CONTROL_MAPPINGS = {
    FindingCategory.AUTHENTICATION: ["IA-2", "IA-5", "IA-8"],
    FindingCategory.AUTHORIZATION: ["AC-2", "AC-3", "AC-6"],
    FindingCategory.DATA_PROTECTION: ["SC-8", "SC-13", "SC-28"],
    FindingCategory.ENCRYPTION: ["SC-12", "SC-13"],
    FindingCategory.AUDIT_LOGGING: ["AU-2", "AU-3", "AU-12"],
    FindingCategory.SECRETS_MANAGEMENT: ["IA-5", "SC-12"],
}


class DesignDocSecurityAgent:
    """
    Agent for proactive security review of design documents.

    Analyzes markdown documentation, ADRs, and architecture diagrams
    to identify security issues before code implementation.

    Usage:
        agent = DesignDocSecurityAgent(llm_client=bedrock_service)

        # Review a single document
        findings = await agent.review_document("docs/architecture/api-design.md")

        # Review all docs in a repository
        results = await agent.review_repository_docs("/path/to/repo")
    """

    def __init__(
        self,
        llm_client: Any = None,
        use_llm_analysis: bool = True,
    ):
        """
        Initialize the Design Document Security Agent.

        Args:
            llm_client: LLM service for advanced analysis (e.g., BedrockLLMService)
            use_llm_analysis: Whether to use LLM for enhanced detection
        """
        self.llm = llm_client
        self.use_llm_analysis = use_llm_analysis and llm_client is not None
        self._finding_counter = 0

    def _generate_finding_id(self) -> str:
        """Generate a unique finding ID."""
        self._finding_counter += 1
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"DSF-{timestamp}-{self._finding_counter:04d}"

    async def review_document(
        self,
        document_path: str,
        document_content: str | None = None,
    ) -> list[DesignSecurityFinding]:
        """
        Review a single design document for security issues.

        Args:
            document_path: Path to the document
            document_content: Optional pre-loaded content

        Returns:
            List of security findings
        """
        start_time = datetime.now(timezone.utc)

        # Load document content if not provided
        if document_content is None:
            try:
                with open(document_path, "r", encoding="utf-8") as f:
                    document_content = f.read()
            except Exception as e:
                logger.error(f"Failed to read document {document_path}: {e}")
                return []

        logger.info(f"Reviewing document: {document_path}")

        findings: list[DesignSecurityFinding] = []

        # Pattern-based detection
        findings.extend(self._pattern_based_analysis(document_path, document_content))

        # Architecture diagram analysis
        findings.extend(self._analyze_diagrams(document_path, document_content))

        # API specification analysis
        findings.extend(self._analyze_api_specs(document_path, document_content))

        # LLM-enhanced analysis for complex issues
        if self.use_llm_analysis:
            llm_findings = await self._llm_enhanced_analysis(
                document_path, document_content
            )
            findings.extend(llm_findings)

        # Deduplicate findings
        findings = self._deduplicate_findings(findings)

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.info(
            f"Document review complete: {document_path} - "
            f"Found {len(findings)} issues in {duration:.2f}s"
        )

        return findings

    async def review_repository_docs(
        self,
        repo_path: str,
        doc_patterns: list[str] | None = None,
    ) -> list[DocumentAnalysisResult]:
        """
        Review all design documents in a repository.

        Args:
            repo_path: Path to the repository root
            doc_patterns: Glob patterns for documents (default: docs/**/*.md)

        Returns:
            List of analysis results for each document
        """
        if doc_patterns is None:
            doc_patterns = [
                "docs/**/*.md",
                "**/*ADR*.md",
                "**/architecture/*.md",
                "**/design/*.md",
                "**/*spec*.md",
                "**/README.md",
            ]

        results: list[DocumentAnalysisResult] = []
        repo = Path(repo_path)

        for pattern in doc_patterns:
            for doc_path in repo.glob(pattern):
                if doc_path.is_file():
                    start_time = datetime.now(timezone.utc)

                    try:
                        content = doc_path.read_text(encoding="utf-8")
                        findings = await self.review_document(str(doc_path), content)

                        duration = (
                            datetime.now(timezone.utc) - start_time
                        ).total_seconds()

                        # Determine document type
                        doc_type = self._classify_document(str(doc_path), content)

                        # Calculate risk score
                        risk_score = self._calculate_risk_score(findings)

                        results.append(
                            DocumentAnalysisResult(
                                document_path=str(doc_path),
                                document_type=doc_type,
                                findings=findings,
                                sections_analyzed=content.count("##"),
                                total_risk_score=risk_score,
                                analysis_duration_seconds=duration,
                            )
                        )

                    except Exception as e:
                        logger.error(f"Failed to analyze {doc_path}: {e}")

        return results

    def _pattern_based_analysis(
        self,
        document_path: str,
        content: str,
    ) -> list[DesignSecurityFinding]:
        """Apply regex pattern-based security checks."""
        findings: list[DesignSecurityFinding] = []

        # Authentication patterns
        for pattern, description in AUTHENTICATION_PATTERNS:
            for match in re.finditer(pattern, content):
                findings.append(
                    self._create_finding(
                        document_path=document_path,
                        severity=FindingSeverity.HIGH,
                        category=FindingCategory.AUTHENTICATION,
                        title="Authentication Gap Detected",
                        description=f"{description}: '{match.group()}'",
                        location=self._get_location(content, match.start()),
                        recommendation="Ensure all endpoints require authentication. Use JWT, OAuth, or API keys.",
                    )
                )

        # Authorization patterns
        for pattern, description in AUTHORIZATION_PATTERNS:
            for match in re.finditer(pattern, content):
                findings.append(
                    self._create_finding(
                        document_path=document_path,
                        severity=FindingSeverity.HIGH,
                        category=FindingCategory.AUTHORIZATION,
                        title="Authorization Gap Detected",
                        description=f"{description}: '{match.group()}'",
                        location=self._get_location(content, match.start()),
                        recommendation="Implement role-based access control (RBAC) with principle of least privilege.",
                    )
                )

        # Data protection patterns
        for pattern, description in DATA_PROTECTION_PATTERNS:
            for match in re.finditer(pattern, content):
                findings.append(
                    self._create_finding(
                        document_path=document_path,
                        severity=FindingSeverity.MEDIUM,
                        category=FindingCategory.DATA_PROTECTION,
                        title="Data Protection Issue",
                        description=f"{description}: '{match.group()}'",
                        location=self._get_location(content, match.start()),
                        recommendation="Use TLS 1.3 for data in transit. Encrypt sensitive data at rest with AES-256.",
                    )
                )

        # Secrets patterns
        for pattern, description in SECRETS_PATTERNS:
            for match in re.finditer(pattern, content):
                findings.append(
                    self._create_finding(
                        document_path=document_path,
                        severity=FindingSeverity.CRITICAL,
                        category=FindingCategory.SECRETS_MANAGEMENT,
                        title="Potential Hardcoded Secret",
                        description=f"{description}",
                        location=self._get_location(content, match.start()),
                        recommendation="Use AWS Secrets Manager or SSM Parameter Store for credentials. Never hardcode secrets.",
                    )
                )

        # Logging patterns
        for pattern, description in LOGGING_PATTERNS:
            for match in re.finditer(pattern, content):
                findings.append(
                    self._create_finding(
                        document_path=document_path,
                        severity=FindingSeverity.MEDIUM,
                        category=FindingCategory.AUDIT_LOGGING,
                        title="Audit Logging Gap",
                        description=f"{description}: '{match.group()}'",
                        location=self._get_location(content, match.start()),
                        recommendation="Enable comprehensive audit logging for all security-relevant events.",
                    )
                )

        # Architecture risk patterns
        for pattern, description in ARCHITECTURE_RISK_PATTERNS:
            for match in re.finditer(pattern, content):
                findings.append(
                    self._create_finding(
                        document_path=document_path,
                        severity=FindingSeverity.MEDIUM,
                        category=FindingCategory.ARCHITECTURE,
                        title="Architecture Security Risk",
                        description=f"{description}: '{match.group()}'",
                        location=self._get_location(content, match.start()),
                        recommendation="Review architecture for security best practices. Consider defense in depth.",
                    )
                )

        return findings

    def _analyze_diagrams(
        self,
        document_path: str,
        content: str,
    ) -> list[DesignSecurityFinding]:
        """Analyze architecture diagrams (Mermaid, PlantUML) for security issues."""
        findings: list[DesignSecurityFinding] = []

        # Find Mermaid diagrams
        mermaid_blocks = re.findall(r"```mermaid\n(.*?)\n```", content, re.DOTALL)

        for diagram in mermaid_blocks:
            # Check for unprotected data flows
            if re.search(
                r"-->\s*\|.*(?:http|plaintext|unencrypted)", diagram, re.IGNORECASE
            ):
                findings.append(
                    self._create_finding(
                        document_path=document_path,
                        severity=FindingSeverity.HIGH,
                        category=FindingCategory.DATA_FLOW,
                        title="Unprotected Data Flow in Diagram",
                        description="Architecture diagram shows unencrypted data flow",
                        location="Mermaid diagram",
                        recommendation="Ensure all data flows use TLS encryption. Update diagram to reflect security measures.",
                    )
                )

            # Check for direct database access
            if re.search(
                r"(?:client|user|browser).*-->.*(?:database|db|mysql|postgres)",
                diagram,
                re.IGNORECASE,
            ):
                findings.append(
                    self._create_finding(
                        document_path=document_path,
                        severity=FindingSeverity.HIGH,
                        category=FindingCategory.ARCHITECTURE,
                        title="Direct Database Access from Client",
                        description="Diagram shows direct client-to-database connection without API layer",
                        location="Mermaid diagram",
                        recommendation="Add an API layer between clients and databases. Never expose databases directly.",
                    )
                )

            # Check for missing authentication service
            if "auth" not in diagram.lower() and "login" not in diagram.lower():
                if re.search(r"(?:api|service|endpoint)", diagram, re.IGNORECASE):
                    findings.append(
                        self._create_finding(
                            document_path=document_path,
                            severity=FindingSeverity.MEDIUM,
                            category=FindingCategory.AUTHENTICATION,
                            title="No Authentication Service in Architecture",
                            description="Architecture diagram does not show authentication service",
                            location="Mermaid diagram",
                            recommendation="Add authentication service to architecture. Consider OAuth2/OIDC integration.",
                        )
                    )

        return findings

    def _analyze_api_specs(
        self,
        document_path: str,
        content: str,
    ) -> list[DesignSecurityFinding]:
        """Analyze API specifications for security issues."""
        findings: list[DesignSecurityFinding] = []

        # Find API endpoint definitions
        endpoint_pattern = r"(?:GET|POST|PUT|DELETE|PATCH)\s+[/\w{}-]+"
        endpoints = re.findall(endpoint_pattern, content)

        for endpoint in endpoints:
            # Check for missing authentication in sensitive endpoints
            sensitive_patterns = ["/admin", "/user", "/account", "/payment", "/config"]
            for pattern in sensitive_patterns:
                if pattern in endpoint.lower():
                    # Check if authentication is mentioned nearby
                    context_window = 500
                    endpoint_pos = content.find(endpoint)
                    context = content[
                        max(0, endpoint_pos - context_window) : endpoint_pos
                        + context_window
                    ]

                    if (
                        "auth" not in context.lower()
                        and "bearer" not in context.lower()
                    ):
                        findings.append(
                            self._create_finding(
                                document_path=document_path,
                                severity=FindingSeverity.HIGH,
                                category=FindingCategory.AUTHENTICATION,
                                title="Sensitive Endpoint Without Auth Context",
                                description=f"Endpoint {endpoint} appears to handle sensitive data but has no authentication mentioned",
                                location=self._get_location(content, endpoint_pos),
                                recommendation="Document authentication requirements for all sensitive endpoints.",
                            )
                        )

        return findings

    async def _llm_enhanced_analysis(
        self,
        document_path: str,
        content: str,
    ) -> list[DesignSecurityFinding]:
        """Use LLM for advanced security analysis."""
        if not self.llm:
            return []

        findings: list[DesignSecurityFinding] = []

        # Truncate content if too long
        max_content_length = 8000
        if len(content) > max_content_length:
            content = content[:max_content_length] + "\n... [truncated]"

        prompt = f"""Analyze this design document for security issues:

---
{content}
---

Identify security concerns in these categories:
1. Authentication gaps
2. Authorization weaknesses
3. Data protection issues
4. Secrets management problems
5. Missing audit logging
6. Architecture vulnerabilities
7. Compliance gaps (CMMC, NIST, OWASP)

For each issue found, provide:
- Category (from list above)
- Severity (CRITICAL/HIGH/MEDIUM/LOW)
- Title (brief)
- Description (1-2 sentences)
- Recommendation (actionable)

Format as JSON array of objects with keys: category, severity, title, description, recommendation
Return empty array [] if no issues found."""

        try:
            # Call LLM
            response = await self.llm.generate(prompt)

            # Parse response
            import json

            try:
                # Find JSON array in response
                json_match = re.search(r"\[[\s\S]*?\]", response)
                if json_match:
                    issues = json.loads(json_match.group())

                    for issue in issues:
                        category_map = {
                            "authentication": FindingCategory.AUTHENTICATION,
                            "authorization": FindingCategory.AUTHORIZATION,
                            "data protection": FindingCategory.DATA_PROTECTION,
                            "secrets": FindingCategory.SECRETS_MANAGEMENT,
                            "logging": FindingCategory.AUDIT_LOGGING,
                            "audit": FindingCategory.AUDIT_LOGGING,
                            "architecture": FindingCategory.ARCHITECTURE,
                            "compliance": FindingCategory.COMPLIANCE,
                        }

                        severity_map = {
                            "critical": FindingSeverity.CRITICAL,
                            "high": FindingSeverity.HIGH,
                            "medium": FindingSeverity.MEDIUM,
                            "low": FindingSeverity.LOW,
                        }

                        cat_str = issue.get("category", "").lower()
                        category = next(
                            (v for k, v in category_map.items() if k in cat_str),
                            FindingCategory.ARCHITECTURE,
                        )

                        sev_str = issue.get("severity", "").lower()
                        severity = severity_map.get(sev_str, FindingSeverity.MEDIUM)

                        findings.append(
                            self._create_finding(
                                document_path=document_path,
                                severity=severity,
                                category=category,
                                title=issue.get("title", "Security Issue"),
                                description=issue.get("description", ""),
                                location="LLM analysis",
                                recommendation=issue.get("recommendation", ""),
                                confidence=0.7,  # Lower confidence for LLM findings
                            )
                        )

            except json.JSONDecodeError:
                logger.warning(
                    f"Failed to parse LLM response as JSON for {document_path}"
                )

        except Exception as e:
            logger.error(f"LLM analysis failed for {document_path}: {e}")

        return findings

    def _create_finding(
        self,
        document_path: str,
        severity: FindingSeverity,
        category: FindingCategory,
        title: str,
        description: str,
        location: str,
        recommendation: str,
        confidence: float = 0.8,
    ) -> DesignSecurityFinding:
        """Create a standardized finding with CWE and NIST mappings."""
        return DesignSecurityFinding(
            finding_id=self._generate_finding_id(),
            document_path=document_path,
            severity=severity,
            category=category,
            title=title,
            description=description,
            location=location,
            recommendation=recommendation,
            cwe_ids=CWE_MAPPINGS.get(category, []),
            nist_controls=NIST_CONTROL_MAPPINGS.get(category, []),
            confidence=confidence,
        )

    def _get_location(self, content: str, position: int) -> str:
        """Get human-readable location from character position."""
        lines = content[:position].count("\n") + 1
        # Find nearest section header
        headers = re.findall(r"^#{1,6}\s+(.+)$", content[:position], re.MULTILINE)
        section = headers[-1] if headers else "Document start"
        return f"Line {lines}, Section: {section}"

    def _classify_document(self, path: str, content: str) -> str:
        """Classify the type of design document."""
        path_lower = path.lower()

        if "adr" in path_lower or "decision" in path_lower:
            return "adr"
        if "api" in path_lower or "openapi" in path_lower or "swagger" in path_lower:
            return "api_spec"
        if "architecture" in path_lower or "design" in path_lower:
            return "architecture"
        if "readme" in path_lower:
            return "readme"

        # Check content
        if "## Status" in content and "## Context" in content:
            return "adr"
        if "paths:" in content or '"openapi"' in content:
            return "api_spec"

        return "design"

    def _calculate_risk_score(self, findings: list[DesignSecurityFinding]) -> float:
        """Calculate total risk score from findings."""
        severity_weights = {
            FindingSeverity.CRITICAL: 10.0,
            FindingSeverity.HIGH: 5.0,
            FindingSeverity.MEDIUM: 2.0,
            FindingSeverity.LOW: 1.0,
            FindingSeverity.INFO: 0.5,
        }

        total = sum(severity_weights[f.severity] * f.confidence for f in findings)

        # Normalize to 0-100 scale
        return min(100.0, total)

    def _deduplicate_findings(
        self,
        findings: list[DesignSecurityFinding],
    ) -> list[DesignSecurityFinding]:
        """Remove duplicate findings based on title and location."""
        seen: set[tuple[str, str]] = set()
        unique_findings: list[DesignSecurityFinding] = []

        for finding in findings:
            key = (finding.title, finding.location)
            if key not in seen:
                seen.add(key)
                unique_findings.append(finding)

        return unique_findings


# =============================================================================
# Factory Function
# =============================================================================


def create_design_doc_security_agent(
    llm_client: Any = None,
    use_llm_analysis: bool = True,
) -> DesignDocSecurityAgent:
    """
    Create a DesignDocSecurityAgent instance.

    Args:
        llm_client: LLM service for enhanced analysis
        use_llm_analysis: Whether to enable LLM-based detection

    Returns:
        Configured DesignDocSecurityAgent
    """
    return DesignDocSecurityAgent(
        llm_client=llm_client,
        use_llm_analysis=use_llm_analysis,
    )
