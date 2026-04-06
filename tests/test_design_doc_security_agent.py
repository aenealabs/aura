"""
Tests for Design Document Security Agent.

This module tests the proactive security review capabilities for
design documents, ADRs, and architecture diagrams. Part of AWS
Security Agent capability parity (Gap 2/4).

Author: Project Aura Team
Created: 2025-12-03
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.design_doc_security_agent import (
    CWE_MAPPINGS,
    NIST_CONTROL_MAPPINGS,
    DesignDocSecurityAgent,
    DesignSecurityFinding,
    DocumentAnalysisResult,
    FindingCategory,
    FindingSeverity,
    create_design_doc_security_agent,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def agent():
    """Create agent without LLM for pattern-based testing."""
    return DesignDocSecurityAgent(llm_client=None, use_llm_analysis=False)


@pytest.fixture
def agent_with_llm():
    """Create agent with mocked LLM."""
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(return_value="[]")
    return DesignDocSecurityAgent(llm_client=mock_llm, use_llm_analysis=True)


@pytest.fixture
def sample_finding():
    """Create sample finding for testing."""
    return DesignSecurityFinding(
        finding_id="DSF-20251203120000-0001",
        document_path="docs/design.md",
        severity=FindingSeverity.HIGH,
        category=FindingCategory.AUTHENTICATION,
        title="Authentication Gap Detected",
        description="Public API without authentication",
        location="Line 42, Section: API Design",
        recommendation="Add authentication to all endpoints",
        affected_components=["API Gateway", "User Service"],
        cwe_ids=["CWE-287", "CWE-306"],
        nist_controls=["IA-2", "IA-5"],
        confidence=0.85,
    )


@pytest.fixture
def temp_repo():
    """Create temporary repository with test documents."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        # Create docs directory
        docs_dir = repo_path / "docs"
        docs_dir.mkdir()

        # Create architecture document
        arch_doc = docs_dir / "architecture.md"
        arch_doc.write_text(
            """# System Architecture

## Overview
This is the system architecture.

## API Design
The API uses a public endpoint for health checks.

## Authentication
All endpoints require JWT tokens.
"""
        )

        # Create ADR with issues
        adr_dir = repo_path / "docs" / "adr"
        adr_dir.mkdir()
        adr = adr_dir / "ADR-001-auth.md"
        adr.write_text(
            """# ADR-001: Authentication

## Status
Accepted

## Context
We need to decide on authentication.

## Decision
Use open access for internal APIs.
Skip auth for admin endpoints.
"""
        )

        yield repo_path


# =============================================================================
# Dataclass Tests
# =============================================================================


class TestDesignSecurityFinding:
    """Tests for DesignSecurityFinding dataclass."""

    def test_finding_creation(self, sample_finding):
        """Test finding can be created with all fields."""
        assert sample_finding.finding_id == "DSF-20251203120000-0001"
        assert sample_finding.severity == FindingSeverity.HIGH
        assert sample_finding.category == FindingCategory.AUTHENTICATION
        assert len(sample_finding.cwe_ids) == 2
        assert len(sample_finding.nist_controls) == 2

    def test_finding_to_dict(self, sample_finding):
        """Test finding serialization."""
        data = sample_finding.to_dict()

        assert data["finding_id"] == "DSF-20251203120000-0001"
        assert data["severity"] == "high"
        assert data["category"] == "authentication"
        assert data["cwe_ids"] == ["CWE-287", "CWE-306"]

    def test_finding_default_values(self):
        """Test finding with minimal fields."""
        finding = DesignSecurityFinding(
            finding_id="DSF-001",
            document_path="test.md",
            severity=FindingSeverity.LOW,
            category=FindingCategory.COMPLIANCE,
            title="Test",
            description="Test finding",
            location="Line 1",
            recommendation="Fix it",
        )

        assert finding.affected_components == []
        assert finding.cwe_ids == []
        assert finding.confidence == 0.8


class TestDocumentAnalysisResult:
    """Tests for DocumentAnalysisResult dataclass."""

    def test_result_creation(self, sample_finding):
        """Test analysis result creation."""
        result = DocumentAnalysisResult(
            document_path="docs/design.md",
            document_type="architecture",
            findings=[sample_finding],
            sections_analyzed=5,
            total_risk_score=25.0,
            analysis_duration_seconds=1.5,
        )

        assert result.document_path == "docs/design.md"
        assert result.document_type == "architecture"
        assert len(result.findings) == 1
        assert result.total_risk_score == 25.0


# =============================================================================
# Pattern-Based Detection Tests
# =============================================================================


class TestAuthenticationPatterns:
    """Tests for authentication gap detection."""

    @pytest.mark.asyncio
    async def test_detect_public_api(self, agent):
        """Test detection of public API without auth."""
        content = """
        # API Design

        We expose a public API for all users.
        The public endpoint handles sensitive data.
        """

        findings = await agent.review_document("test.md", content)
        auth_findings = [
            f for f in findings if f.category == FindingCategory.AUTHENTICATION
        ]

        assert len(auth_findings) >= 1
        assert any("public" in f.description.lower() for f in auth_findings)

    @pytest.mark.asyncio
    async def test_detect_no_auth(self, agent):
        """Test detection of explicitly disabled auth."""
        content = """
        # Admin Panel

        The internal admin panel uses no authentication.
        This is fine because it's internal.
        """

        findings = await agent.review_document("test.md", content)
        auth_findings = [
            f for f in findings if f.category == FindingCategory.AUTHENTICATION
        ]

        assert len(auth_findings) >= 1
        assert auth_findings[0].severity == FindingSeverity.HIGH

    @pytest.mark.asyncio
    async def test_detect_skip_auth(self, agent):
        """Test detection of auth bypass."""
        content = """
        For development, we skip auth on localhost.
        """

        findings = await agent.review_document("test.md", content)
        auth_findings = [
            f for f in findings if f.category == FindingCategory.AUTHENTICATION
        ]

        assert len(auth_findings) >= 1


class TestAuthorizationPatterns:
    """Tests for authorization gap detection."""

    @pytest.mark.asyncio
    async def test_detect_admin_without_check(self, agent):
        """Test detection of admin access without verification."""
        content = """
        Admin users access all data without check.
        """

        findings = await agent.review_document("test.md", content)
        authz_findings = [
            f for f in findings if f.category == FindingCategory.AUTHORIZATION
        ]

        assert len(authz_findings) >= 1

    @pytest.mark.asyncio
    async def test_detect_no_rbac(self, agent):
        """Test detection of missing RBAC."""
        content = """
        The system uses no RBAC - all users have same permissions.
        """

        findings = await agent.review_document("test.md", content)
        authz_findings = [
            f for f in findings if f.category == FindingCategory.AUTHORIZATION
        ]

        assert len(authz_findings) >= 1


class TestDataProtectionPatterns:
    """Tests for data protection issue detection."""

    @pytest.mark.asyncio
    async def test_detect_plaintext(self, agent):
        """Test detection of plaintext data."""
        content = """
        Passwords are stored in plaintext for simplicity.
        """

        findings = await agent.review_document("test.md", content)
        data_findings = [
            f for f in findings if f.category == FindingCategory.DATA_PROTECTION
        ]

        assert len(data_findings) >= 1
        assert data_findings[0].severity == FindingSeverity.MEDIUM

    @pytest.mark.asyncio
    async def test_detect_http_url(self, agent):
        """Test detection of non-HTTPS URLs."""
        content = """
        The API is available at http://api.example.com
        """

        findings = await agent.review_document("test.md", content)
        data_findings = [
            f for f in findings if f.category == FindingCategory.DATA_PROTECTION
        ]

        assert len(data_findings) >= 1

    @pytest.mark.asyncio
    async def test_detect_unencrypted(self, agent):
        """Test detection of unencrypted data mention."""
        content = """
        Data is stored unencrypted in S3 for cost savings.
        """

        findings = await agent.review_document("test.md", content)
        data_findings = [
            f for f in findings if f.category == FindingCategory.DATA_PROTECTION
        ]

        assert len(data_findings) >= 1


class TestSecretsPatterns:
    """Tests for hardcoded secrets detection."""

    @pytest.mark.asyncio
    async def test_detect_hardcoded_password(self, agent):
        """Test detection of hardcoded password."""
        content = """
        password = "supersecret123"
        """

        findings = await agent.review_document("test.md", content)
        secrets_findings = [
            f for f in findings if f.category == FindingCategory.SECRETS_MANAGEMENT
        ]

        assert len(secrets_findings) >= 1
        assert secrets_findings[0].severity == FindingSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_detect_hardcoded_api_key(self, agent):
        """Test detection of hardcoded API key."""
        content = """
        api_key = "sk-1234567890abcdef"
        """

        findings = await agent.review_document("test.md", content)
        secrets_findings = [
            f for f in findings if f.category == FindingCategory.SECRETS_MANAGEMENT
        ]

        assert len(secrets_findings) >= 1

    @pytest.mark.asyncio
    async def test_detect_aws_access_key(self, agent):
        """Test detection of AWS access key pattern."""
        content = """
        Use this key: AKIAIOSFODNN7EXAMPLE
        """

        findings = await agent.review_document("test.md", content)
        secrets_findings = [
            f for f in findings if f.category == FindingCategory.SECRETS_MANAGEMENT
        ]

        assert len(secrets_findings) >= 1


class TestLoggingPatterns:
    """Tests for audit logging gap detection."""

    @pytest.mark.asyncio
    async def test_detect_no_logging(self, agent):
        """Test detection of disabled logging."""
        content = """
        We use no logging to improve performance.
        """

        findings = await agent.review_document("test.md", content)
        logging_findings = [
            f for f in findings if f.category == FindingCategory.AUDIT_LOGGING
        ]

        assert len(logging_findings) >= 1

    @pytest.mark.asyncio
    async def test_detect_skip_audit(self, agent):
        """Test detection of audit bypass."""
        content = """
        For batch operations, skip audit to reduce I/O.
        """

        findings = await agent.review_document("test.md", content)
        logging_findings = [
            f for f in findings if f.category == FindingCategory.AUDIT_LOGGING
        ]

        assert len(logging_findings) >= 1


class TestArchitecturePatterns:
    """Tests for architecture security risk detection."""

    @pytest.mark.asyncio
    async def test_detect_single_point_of_failure(self, agent):
        """Test detection of SPOF."""
        content = """
        The database is a single point of failure.
        """

        findings = await agent.review_document("test.md", content)
        arch_findings = [
            f for f in findings if f.category == FindingCategory.ARCHITECTURE
        ]

        assert len(arch_findings) >= 1

    @pytest.mark.asyncio
    async def test_detect_no_rate_limit(self, agent):
        """Test detection of missing rate limiting."""
        content = """
        The API has no rate limiting for now.
        """

        findings = await agent.review_document("test.md", content)
        arch_findings = [
            f for f in findings if f.category == FindingCategory.ARCHITECTURE
        ]

        assert len(arch_findings) >= 1

    @pytest.mark.asyncio
    async def test_detect_client_trust(self, agent):
        """Test detection of client-side trust."""
        content = """
        We trust client for role validation.
        """

        findings = await agent.review_document("test.md", content)
        arch_findings = [
            f for f in findings if f.category == FindingCategory.ARCHITECTURE
        ]

        assert len(arch_findings) >= 1


# =============================================================================
# Diagram Analysis Tests
# =============================================================================


class TestMermaidDiagramAnalysis:
    """Tests for Mermaid diagram security analysis."""

    @pytest.mark.asyncio
    async def test_detect_unprotected_data_flow(self, agent):
        """Test detection of unprotected data flow in diagram."""
        content = """# Architecture

```mermaid
graph TD
    A[Client] -->|http| B[API]
    B -->|plaintext| C[Database]
```
"""

        findings = await agent.review_document("test.md", content)
        data_flow_findings = [
            f for f in findings if f.category == FindingCategory.DATA_FLOW
        ]

        assert len(data_flow_findings) >= 1

    @pytest.mark.asyncio
    async def test_detect_direct_db_access(self, agent):
        """Test detection of direct client-to-database access."""
        content = """# Architecture

```mermaid
graph TD
    Client --> Database
    User --> MySQL
```
"""

        findings = await agent.review_document("test.md", content)
        arch_findings = [
            f for f in findings if f.category == FindingCategory.ARCHITECTURE
        ]

        assert len(arch_findings) >= 1
        assert any("direct" in f.description.lower() for f in arch_findings)

    @pytest.mark.asyncio
    async def test_detect_missing_auth_in_diagram(self, agent):
        """Test detection of missing auth service in diagram."""
        content = """# Architecture

```mermaid
graph TD
    Client --> API
    API --> Database
    API --> Cache
```
"""

        findings = await agent.review_document("test.md", content)
        auth_findings = [
            f for f in findings if f.category == FindingCategory.AUTHENTICATION
        ]

        # Should detect missing auth service
        assert len(auth_findings) >= 1


# =============================================================================
# API Specification Analysis Tests
# =============================================================================


class TestAPISpecAnalysis:
    """Tests for API specification security analysis."""

    @pytest.mark.asyncio
    async def test_detect_sensitive_endpoint_no_auth(self, agent):
        """Test detection of sensitive endpoint without auth context."""
        content = """
        # API Endpoints

        POST /admin/users
        DELETE /admin/config
        GET /user/profile
        POST /payment/process
        """

        findings = await agent.review_document("test.md", content)
        auth_findings = [
            f for f in findings if f.category == FindingCategory.AUTHENTICATION
        ]

        # Should detect sensitive endpoints without auth
        assert len(auth_findings) >= 1

    @pytest.mark.asyncio
    async def test_sensitive_endpoint_with_auth_ok(self, agent):
        """Test that endpoints with auth context don't trigger false positives."""
        content = """
        # API Endpoints

        POST /admin/users
        Requires: Bearer token with admin role

        Authorization: OAuth2 with admin scope
        """

        findings = await agent.review_document("test.md", content)
        auth_findings = [
            f
            for f in findings
            if f.category == FindingCategory.AUTHENTICATION
            and "sensitive endpoint" in f.title.lower()
        ]

        # Should not trigger (auth is mentioned)
        assert len(auth_findings) == 0


# =============================================================================
# Risk Score and Deduplication Tests
# =============================================================================


class TestRiskScoreCalculation:
    """Tests for risk score calculation."""

    def test_risk_score_critical(self, agent):
        """Test risk score with critical finding."""
        finding = DesignSecurityFinding(
            finding_id="DSF-001",
            document_path="test.md",
            severity=FindingSeverity.CRITICAL,
            category=FindingCategory.SECRETS_MANAGEMENT,
            title="Test",
            description="Test",
            location="Line 1",
            recommendation="Fix",
            confidence=1.0,
        )

        score = agent._calculate_risk_score([finding])
        assert score == 10.0  # CRITICAL weight * 1.0 confidence

    def test_risk_score_multiple_findings(self, agent):
        """Test risk score with multiple findings."""
        findings = [
            DesignSecurityFinding(
                finding_id="DSF-001",
                document_path="test.md",
                severity=FindingSeverity.HIGH,
                category=FindingCategory.AUTHENTICATION,
                title="Test 1",
                description="Test",
                location="Line 1",
                recommendation="Fix",
                confidence=1.0,
            ),
            DesignSecurityFinding(
                finding_id="DSF-002",
                document_path="test.md",
                severity=FindingSeverity.MEDIUM,
                category=FindingCategory.AUTHORIZATION,
                title="Test 2",
                description="Test",
                location="Line 2",
                recommendation="Fix",
                confidence=0.8,
            ),
        ]

        score = agent._calculate_risk_score(findings)
        expected = 5.0 * 1.0 + 2.0 * 0.8  # HIGH + MEDIUM
        assert score == expected

    def test_risk_score_capped_at_100(self, agent):
        """Test risk score doesn't exceed 100."""
        # Create many high severity findings
        findings = [
            DesignSecurityFinding(
                finding_id=f"DSF-{i:03d}",
                document_path="test.md",
                severity=FindingSeverity.CRITICAL,
                category=FindingCategory.AUTHENTICATION,
                title=f"Test {i}",
                description="Test",
                location=f"Line {i}",
                recommendation="Fix",
                confidence=1.0,
            )
            for i in range(20)
        ]

        score = agent._calculate_risk_score(findings)
        assert score == 100.0  # Capped


class TestDeduplication:
    """Tests for finding deduplication."""

    def test_deduplicate_same_title_location(self, agent):
        """Test deduplication of identical findings."""
        findings = [
            DesignSecurityFinding(
                finding_id="DSF-001",
                document_path="test.md",
                severity=FindingSeverity.HIGH,
                category=FindingCategory.AUTHENTICATION,
                title="Same Title",
                description="Test",
                location="Same Location",
                recommendation="Fix",
            ),
            DesignSecurityFinding(
                finding_id="DSF-002",
                document_path="test.md",
                severity=FindingSeverity.HIGH,
                category=FindingCategory.AUTHENTICATION,
                title="Same Title",
                description="Different description",
                location="Same Location",
                recommendation="Different fix",
            ),
        ]

        deduplicated = agent._deduplicate_findings(findings)
        assert len(deduplicated) == 1

    def test_keep_different_findings(self, agent):
        """Test that different findings are kept."""
        findings = [
            DesignSecurityFinding(
                finding_id="DSF-001",
                document_path="test.md",
                severity=FindingSeverity.HIGH,
                category=FindingCategory.AUTHENTICATION,
                title="Auth Issue",
                description="Test",
                location="Line 10",
                recommendation="Fix",
            ),
            DesignSecurityFinding(
                finding_id="DSF-002",
                document_path="test.md",
                severity=FindingSeverity.MEDIUM,
                category=FindingCategory.AUTHORIZATION,
                title="Authz Issue",
                description="Test",
                location="Line 20",
                recommendation="Fix",
            ),
        ]

        deduplicated = agent._deduplicate_findings(findings)
        assert len(deduplicated) == 2


# =============================================================================
# Document Classification Tests
# =============================================================================


class TestDocumentClassification:
    """Tests for document type classification."""

    def test_classify_adr_by_path(self, agent):
        """Test ADR classification by path."""
        doc_type = agent._classify_document("docs/adr/ADR-001.md", "")
        assert doc_type == "adr"

    def test_classify_adr_by_content(self, agent):
        """Test ADR classification by content."""
        content = """# ADR-001
## Status
Accepted
## Context
Some context
"""
        doc_type = agent._classify_document("random.md", content)
        assert doc_type == "adr"

    def test_classify_api_spec(self, agent):
        """Test API spec classification."""
        doc_type = agent._classify_document("docs/api-spec.md", "")
        assert doc_type == "api_spec"

    def test_classify_architecture(self, agent):
        """Test architecture doc classification."""
        doc_type = agent._classify_document("docs/architecture/system.md", "")
        assert doc_type == "architecture"

    def test_classify_readme(self, agent):
        """Test README classification."""
        doc_type = agent._classify_document("README.md", "")
        assert doc_type == "readme"

    def test_classify_default(self, agent):
        """Test default classification."""
        doc_type = agent._classify_document("random.md", "Some content")
        assert doc_type == "design"


# =============================================================================
# Repository Scanning Tests
# =============================================================================


class TestRepositoryScanning:
    """Tests for repository-wide document scanning."""

    @pytest.mark.asyncio
    async def test_scan_repository(self, agent, temp_repo):
        """Test scanning all docs in a repository."""
        results = await agent.review_repository_docs(str(temp_repo))

        assert len(results) >= 2  # At least 2 docs created
        assert all(isinstance(r, DocumentAnalysisResult) for r in results)

    @pytest.mark.asyncio
    async def test_scan_with_custom_patterns(self, agent, temp_repo):
        """Test scanning with custom glob patterns."""
        # Create additional file
        (temp_repo / "custom.security.md").write_text("password = 'test123'")

        results = await agent.review_repository_docs(
            str(temp_repo), doc_patterns=["*.security.md"]
        )

        assert len(results) == 1
        assert "custom.security.md" in results[0].document_path


# =============================================================================
# LLM Integration Tests
# =============================================================================


class TestLLMEnhancedAnalysis:
    """Tests for LLM-enhanced security analysis."""

    @pytest.mark.asyncio
    async def test_llm_analysis_called(self, agent_with_llm):
        """Test that LLM analysis is invoked."""
        content = "# API Design\n\nSome design content."

        await agent_with_llm.review_document("test.md", content)

        agent_with_llm.llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_findings_parsed(self):
        """Test parsing of LLM findings."""
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(
            return_value="""
        [
            {
                "category": "authentication",
                "severity": "HIGH",
                "title": "Missing JWT validation",
                "description": "API does not validate JWT expiration",
                "recommendation": "Add exp claim validation"
            }
        ]
        """
        )

        agent = DesignDocSecurityAgent(llm_client=mock_llm, use_llm_analysis=True)
        findings = await agent.review_document("test.md", "# API\nSome content")

        # Find the LLM finding
        llm_findings = [f for f in findings if f.location == "LLM analysis"]
        assert len(llm_findings) == 1
        assert llm_findings[0].title == "Missing JWT validation"
        assert llm_findings[0].confidence == 0.7  # Lower for LLM

    @pytest.mark.asyncio
    async def test_llm_error_handled(self):
        """Test graceful handling of LLM errors."""
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(side_effect=Exception("LLM unavailable"))

        agent = DesignDocSecurityAgent(llm_client=mock_llm, use_llm_analysis=True)
        findings = await agent.review_document("test.md", "password = 'test'")

        # Should still get pattern-based findings
        assert len(findings) >= 1


# =============================================================================
# CWE and NIST Mapping Tests
# =============================================================================


class TestCWEandNISTMappings:
    """Tests for CWE and NIST control mappings."""

    def test_cwe_mappings_exist(self):
        """Test that CWE mappings exist for key categories."""
        assert FindingCategory.AUTHENTICATION in CWE_MAPPINGS
        assert FindingCategory.AUTHORIZATION in CWE_MAPPINGS
        assert FindingCategory.SECRETS_MANAGEMENT in CWE_MAPPINGS

    def test_nist_mappings_exist(self):
        """Test that NIST mappings exist for key categories."""
        assert FindingCategory.AUTHENTICATION in NIST_CONTROL_MAPPINGS
        assert FindingCategory.AUTHORIZATION in NIST_CONTROL_MAPPINGS
        assert FindingCategory.AUDIT_LOGGING in NIST_CONTROL_MAPPINGS

    @pytest.mark.asyncio
    async def test_finding_has_cwe_ids(self, agent):
        """Test that findings include CWE IDs."""
        content = "public endpoint without auth"

        findings = await agent.review_document("test.md", content)
        auth_findings = [
            f for f in findings if f.category == FindingCategory.AUTHENTICATION
        ]

        assert len(auth_findings) >= 1
        assert len(auth_findings[0].cwe_ids) > 0
        assert auth_findings[0].cwe_ids[0].startswith("CWE-")


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for agent factory function."""

    def test_create_agent_no_llm(self):
        """Test creating agent without LLM."""
        agent = create_design_doc_security_agent()

        assert agent is not None
        assert agent.llm is None
        assert agent.use_llm_analysis is False

    def test_create_agent_with_llm(self):
        """Test creating agent with LLM."""
        mock_llm = MagicMock()
        agent = create_design_doc_security_agent(llm_client=mock_llm)

        assert agent is not None
        assert agent.llm is mock_llm
        assert agent.use_llm_analysis is True

    def test_create_agent_disable_llm(self):
        """Test creating agent with LLM disabled."""
        mock_llm = MagicMock()
        agent = create_design_doc_security_agent(
            llm_client=mock_llm, use_llm_analysis=False
        )

        assert agent.llm is mock_llm
        assert agent.use_llm_analysis is False


# =============================================================================
# Spawnable Agent Adapter Tests
# =============================================================================


class TestSpawnableDesignSecurityReviewAgent:
    """Tests for SpawnableDesignSecurityReviewAgent adapter."""

    @pytest.fixture
    def spawnable_agent(self):
        """Create spawnable adapter for testing."""
        from src.agents.spawnable_agent_adapters import (
            SpawnableDesignSecurityReviewAgent,
        )

        return SpawnableDesignSecurityReviewAgent(agent_id="test-design-review")

    @pytest.fixture
    def spawnable_agent_with_llm(self):
        """Create spawnable adapter with LLM for testing."""
        from src.agents.spawnable_agent_adapters import (
            SpawnableDesignSecurityReviewAgent,
        )

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value="[]")
        return SpawnableDesignSecurityReviewAgent(
            agent_id="test-design-review-llm", llm_client=mock_llm
        )

    @pytest.mark.asyncio
    async def test_adapter_capability(self, spawnable_agent):
        """Test adapter has correct capability."""
        from src.agents.meta_orchestrator import AgentCapability

        assert spawnable_agent.capability == AgentCapability.DESIGN_SECURITY_REVIEW

    @pytest.mark.asyncio
    async def test_adapter_execute_single_doc(self, spawnable_agent):
        """Test adapter executes single document review."""
        context = {
            "document_path": "test.md",
            "document_content": "password = 'secret123'",
        }

        result = await spawnable_agent.execute(
            task="Review this document", context=context
        )

        assert result.success is True
        assert "finding_count" in result.output
        assert result.output["finding_count"] >= 1

    @pytest.mark.asyncio
    async def test_adapter_execute_inline_content(self, spawnable_agent):
        """Test adapter with task as document content."""
        result = await spawnable_agent.execute(
            task="The API uses open access for all endpoints", context=None
        )

        assert result.success is True
        assert "finding_count" in result.output

    @pytest.mark.asyncio
    async def test_adapter_execute_repo_scan(self, spawnable_agent, temp_repo):
        """Test adapter executes repository scan."""
        context = {"repo_path": str(temp_repo)}

        result = await spawnable_agent.execute(
            task="Scan repository for security issues", context=context
        )

        assert result.success is True
        assert "documents_analyzed" in result.output
        assert result.output["documents_analyzed"] >= 2


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_document(self, agent):
        """Test handling of empty document."""
        findings = await agent.review_document("test.md", "")

        assert findings == []

    @pytest.mark.asyncio
    async def test_document_without_issues(self, agent):
        """Test document with no security issues."""
        content = """
        # Secure API Design

        ## Authentication
        All endpoints require JWT authentication with RS256 signing.

        ## Authorization
        RBAC with principle of least privilege.

        ## Data Protection
        All data encrypted at rest (AES-256) and in transit (TLS 1.3).
        """

        findings = await agent.review_document("test.md", content)

        # Should have minimal or no findings
        assert len(findings) <= 1  # May detect "http" in TLS 1.3 as false positive

    @pytest.mark.asyncio
    async def test_nonexistent_file(self, agent):
        """Test handling of nonexistent file."""
        findings = await agent.review_document("/nonexistent/path.md")

        assert findings == []

    @pytest.mark.asyncio
    async def test_finding_id_uniqueness(self, agent):
        """Test that finding IDs are unique."""
        content = """
        password = 'secret1'
        password = 'secret2'
        password = 'secret3'
        """

        findings = await agent.review_document("test.md", content)
        finding_ids = [f.finding_id for f in findings]

        assert len(finding_ids) == len(set(finding_ids))  # All unique

    @pytest.mark.asyncio
    async def test_location_formatting(self, agent):
        """Test location includes line number and section."""
        content = """
        # Overview

        Some overview content.

        ## API Design

        The API uses a public endpoint for testing.
        """

        findings = await agent.review_document("test.md", content)
        auth_findings = [
            f for f in findings if f.category == FindingCategory.AUTHENTICATION
        ]

        if auth_findings:
            location = auth_findings[0].location
            assert "Line" in location
            assert "Section" in location


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for full workflow."""

    @pytest.mark.asyncio
    async def test_full_document_review(self, agent):
        """Test full document review workflow."""
        content = """
        # System Design Document

        ## Overview
        This document describes the system architecture.

        ## API Design

        ### Public Endpoints
        The public API exposes several endpoints:
        - GET /api/users (no auth required)
        - POST /admin/config

        ### Data Flow

        ```mermaid
        graph TD
            Client --> API
            API -->|plaintext| Database
        ```

        ## Security Notes
        - We trust client for validation
        - No rate limiting implemented yet
        - password = "admin123" for testing
        """

        findings = await agent.review_document("design.md", content)

        # Should detect multiple categories of issues
        categories = {f.category for f in findings}

        assert (
            FindingCategory.AUTHENTICATION in categories
            or FindingCategory.SECRETS_MANAGEMENT in categories
        )
        assert len(findings) >= 3  # Multiple issues

    @pytest.mark.asyncio
    async def test_full_repo_scan(self, agent, temp_repo):
        """Test full repository scan workflow."""
        results = await agent.review_repository_docs(str(temp_repo))

        # Verify result structure
        assert len(results) >= 2

        for result in results:
            assert isinstance(result.document_path, str)
            assert isinstance(result.document_type, str)
            assert isinstance(result.findings, list)
            assert isinstance(result.total_risk_score, float)
            assert result.total_risk_score >= 0
            assert result.total_risk_score <= 100
