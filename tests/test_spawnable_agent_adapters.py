"""
Tests for spawnable_agent_adapters.py

Comprehensive tests for agent adapters that wrap existing agents
for MetaOrchestrator integration.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.context_objects import ContextItem, ContextSource, HybridContext
from src.agents.meta_orchestrator import AgentCapability, AgentRegistry
from src.agents.spawnable_agent_adapters import (
    SpawnableArchitectureReviewAgent,
    SpawnableBusinessLogicAnalyzerAgent,
    SpawnableCoderAgent,
    SpawnableDesignSecurityReviewAgent,
    SpawnableGitHubIntegrationAgent,
    SpawnablePenetrationTestingAgent,
    SpawnableReviewerAgent,
    SpawnableThreatAnalysisAgent,
    SpawnableValidatorAgent,
    SpawnableVulnerabilityScanAgent,
    create_production_meta_orchestrator,
    create_spawnable_architecture_review_agent,
    create_spawnable_business_logic_analyzer_agent,
    create_spawnable_coder_agent,
    create_spawnable_design_security_review_agent,
    create_spawnable_github_integration_agent,
    create_spawnable_penetration_testing_agent,
    create_spawnable_reviewer_agent,
    create_spawnable_threat_analysis_agent,
    create_spawnable_validator_agent,
    create_spawnable_vulnerability_scan_agent,
    register_all_agents,
)

# =============================================================================
# Test Base AgentAdapter
# =============================================================================


class TestAgentAdapter:
    """Tests for the AgentAdapter base class.

    Note: AgentAdapter is abstract, so we use concrete subclasses for testing.
    """

    def test_adapter_init_defaults(self):
        """Test adapter initialization with defaults."""
        # Use a concrete subclass since AgentAdapter is abstract
        adapter = SpawnableCoderAgent()
        assert adapter.llm is None
        assert adapter.max_spawn_depth == 2
        assert adapter.can_spawn is True
        assert adapter._wrapped_agent is None
        assert adapter.monitor is None

    def test_adapter_init_with_params(self):
        """Test adapter initialization with custom parameters."""
        mock_llm = MagicMock()
        mock_registry = MagicMock()
        mock_monitor = MagicMock()

        adapter = SpawnableCoderAgent(
            llm_client=mock_llm,
            agent_id="custom-id",
            max_spawn_depth=5,
            can_spawn=False,
            registry=mock_registry,
            monitor=mock_monitor,
        )

        assert adapter.llm == mock_llm
        assert adapter.agent_id == "custom-id"
        assert adapter.max_spawn_depth == 5
        assert adapter.can_spawn is False
        assert adapter.monitor == mock_monitor

    def test_create_result(self):
        """Test standardized result creation."""
        adapter = SpawnableCoderAgent(agent_id="test-agent")
        start_time = datetime.now()

        result = adapter._create_result(
            success=True,
            output={"data": "test"},
            start_time=start_time,
            tokens_used=100,
        )

        assert result.agent_id == "test-agent"
        assert result.success is True
        assert result.output == {"data": "test"}
        assert result.tokens_used == 100
        assert result.error is None
        assert result.execution_time_seconds >= 0

    def test_create_result_with_error(self):
        """Test result creation with error."""
        adapter = SpawnableCoderAgent(agent_id="test-agent")
        start_time = datetime.now()

        result = adapter._create_result(
            success=False,
            output=None,
            start_time=start_time,
            error="Something failed",
        )

        assert result.success is False
        assert result.output is None
        assert result.error == "Something failed"

    def test_ensure_hybrid_context_already_hybrid(self):
        """Test ensuring hybrid context when already HybridContext."""
        adapter = SpawnableCoderAgent()
        hybrid = HybridContext(
            items=[],
            query="test query",
            target_entity="test_entity",
        )

        result = adapter._ensure_hybrid_context("task", hybrid)
        assert result is hybrid

    def test_ensure_hybrid_context_from_task(self):
        """Test creating HybridContext from task string."""
        adapter = SpawnableCoderAgent()
        result = adapter._ensure_hybrid_context("fix security bug", {"some": "data"})

        assert isinstance(result, HybridContext)
        assert result.query == "fix security bug"
        assert result.target_entity == "generic"
        assert result.items == []


# =============================================================================
# Test SpawnableCoderAgent
# =============================================================================


class TestSpawnableCoderAgent:
    """Tests for SpawnableCoderAgent."""

    def test_capability(self):
        """Test coder agent capability."""
        agent = SpawnableCoderAgent()
        assert agent.capability == AgentCapability.CODE_GENERATION

    @pytest.mark.asyncio
    async def test_execute_code_generation(self):
        """Test code generation execution."""
        mock_llm = MagicMock()
        agent = SpawnableCoderAgent(llm_client=mock_llm)

        mock_coder = AsyncMock()
        mock_coder.generate_code = AsyncMock(
            return_value={"code": "print('hello')", "tokens_used": 50}
        )

        with patch.object(agent, "_get_wrapped_agent", return_value=mock_coder):
            result = await agent.execute("Generate a greeting function")

        assert result.success is True
        assert result.output["code"] == "print('hello')"
        assert result.tokens_used == 50

    @pytest.mark.asyncio
    async def test_execute_patch_generation(self):
        """Test patch generation with vulnerability context."""
        mock_llm = MagicMock()
        agent = SpawnableCoderAgent(llm_client=mock_llm)

        mock_coder = AsyncMock()
        mock_coder.generate_patch = AsyncMock(
            return_value={"patched_code": "safe_code()", "tokens_used": 75}
        )

        with patch.object(agent, "_get_wrapped_agent", return_value=mock_coder):
            context = {
                "original_code": "unsafe_code()",
                "vulnerability": {"type": "SQL_INJECTION"},
            }
            result = await agent.execute("Fix SQL injection vulnerability", context)

        assert result.success is True
        mock_coder.generate_patch.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_patch_fallback_to_generate(self):
        """Test falling back to generate_code when no original code."""
        mock_llm = MagicMock()
        agent = SpawnableCoderAgent(llm_client=mock_llm)

        mock_coder = AsyncMock()
        mock_coder.generate_code = AsyncMock(
            return_value={"code": "fixed", "tokens_used": 25}
        )

        with patch.object(agent, "_get_wrapped_agent", return_value=mock_coder):
            result = await agent.execute("Remediate vulnerability")

        assert result.success is True
        mock_coder.generate_code.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_handles_exception(self):
        """Test execution handles exceptions."""
        agent = SpawnableCoderAgent()

        mock_coder = AsyncMock()
        mock_coder.generate_code = AsyncMock(side_effect=RuntimeError("LLM failed"))

        with patch.object(agent, "_get_wrapped_agent", return_value=mock_coder):
            result = await agent.execute("Generate code")

        assert result.success is False
        assert "LLM failed" in result.error

    def test_extract_vulnerability_info_from_dict(self):
        """Test extracting vulnerability info from dict context."""
        agent = SpawnableCoderAgent()
        context = {"vulnerability": {"type": "XSS", "severity": "HIGH"}}
        result = agent._extract_vulnerability_info("fix xss bug", context)

        assert result["type"] == "XSS"
        assert result["severity"] == "HIGH"

    def test_extract_vulnerability_info_from_hybrid_context(self):
        """Test extracting vulnerability info from HybridContext."""
        agent = SpawnableCoderAgent()
        hybrid = HybridContext(
            items=[
                ContextItem(
                    content="Security policy violation",
                    source=ContextSource.SECURITY_POLICY,
                    confidence=0.9,
                )
            ],
            query="test",
            target_entity="test",
        )
        result = agent._extract_vulnerability_info("task", hybrid)

        assert result["description"] == "Security policy violation"

    def test_extract_vulnerability_type_from_keywords(self):
        """Test detecting vulnerability type from task keywords."""
        agent = SpawnableCoderAgent()

        cases = [
            ("fix sql injection attack", "SQL_INJECTION"),
            ("remediate xss vulnerability", "XSS"),
            ("fix cross-site scripting", "XSS"),
            ("patch command injection", "COMMAND_INJECTION"),
            ("fix path traversal issue", "PATH_TRAVERSAL"),
            ("remediate xxe parsing", "XXE"),
            ("fix ssrf vulnerability", "SSRF"),
            ("patch deserialization bug", "INSECURE_DESERIALIZATION"),
            ("fix crypto weakness", "WEAK_CRYPTO"),
            ("remove hardcoded secret", "HARDCODED_SECRET"),
        ]

        for task, expected_type in cases:
            result = agent._extract_vulnerability_info(task, {})
            assert result["type"] == expected_type, f"Failed for task: {task}"

    def test_extract_original_code_from_dict(self):
        """Test extracting original code from dict."""
        agent = SpawnableCoderAgent()
        context = {"original_code": "def vulnerable(): pass"}
        result = agent._extract_original_code(context)
        assert result == "def vulnerable(): pass"

    def test_extract_original_code_from_hybrid_context(self):
        """Test extracting original code from HybridContext."""
        agent = SpawnableCoderAgent()
        hybrid = HybridContext(
            items=[
                ContextItem(
                    content="original function code",
                    source=ContextSource.GRAPH_STRUCTURAL,
                    confidence=0.8,
                )
            ],
            query="test",
            target_entity="test",
        )
        result = agent._extract_original_code(hybrid)
        assert result == "original function code"


# =============================================================================
# Test SpawnableReviewerAgent
# =============================================================================


class TestSpawnableReviewerAgent:
    """Tests for SpawnableReviewerAgent."""

    def test_capability(self):
        """Test reviewer agent capability."""
        agent = SpawnableReviewerAgent()
        assert agent.capability == AgentCapability.SECURITY_REVIEW

    @pytest.mark.asyncio
    async def test_execute_code_review(self):
        """Test code review execution."""
        mock_llm = MagicMock()
        agent = SpawnableReviewerAgent(llm_client=mock_llm)

        mock_reviewer = AsyncMock()
        mock_reviewer.review_code = AsyncMock(
            return_value={"issues": [], "tokens_used": 80}
        )

        with patch.object(agent, "_get_wrapped_agent", return_value=mock_reviewer):
            result = await agent.execute(
                "Review code for security", {"code": "print('test')"}
            )

        assert result.success is True
        mock_reviewer.review_code.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_patch_review(self):
        """Test patch review execution."""
        mock_llm = MagicMock()
        agent = SpawnableReviewerAgent(llm_client=mock_llm)

        mock_reviewer = AsyncMock()
        mock_reviewer.review_patch = AsyncMock(
            return_value={"approved": True, "tokens_used": 60}
        )

        with patch.object(agent, "_get_wrapped_agent", return_value=mock_reviewer):
            context = {
                "code": "safe_code()",
                "original_code": "unsafe_code()",
                "vulnerability": {"type": "XSS"},
            }
            result = await agent.execute("Verify patch fixes vulnerability", context)

        assert result.success is True
        mock_reviewer.review_patch.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_no_code_provided(self):
        """Test execution fails when no code provided."""
        agent = SpawnableReviewerAgent()
        result = await agent.execute("Review code", {})

        assert result.success is False
        assert "No code provided" in result.error

    @pytest.mark.asyncio
    async def test_execute_handles_exception(self):
        """Test execution handles exceptions."""
        agent = SpawnableReviewerAgent()

        mock_reviewer = AsyncMock()
        mock_reviewer.review_code = AsyncMock(side_effect=Exception("Review failed"))

        with patch.object(agent, "_get_wrapped_agent", return_value=mock_reviewer):
            result = await agent.execute("Review code", {"code": "test"})

        assert result.success is False
        assert "Review failed" in result.error

    def test_extract_code_for_review_from_dict(self):
        """Test extracting code from dict."""
        agent = SpawnableReviewerAgent()

        assert agent._extract_code_for_review("task", {"code": "test1"}) == "test1"
        assert (
            agent._extract_code_for_review("task", {"patched_code": "test2"}) == "test2"
        )

    def test_extract_code_for_review_from_hybrid(self):
        """Test extracting code from HybridContext."""
        agent = SpawnableReviewerAgent()
        hybrid = HybridContext(
            items=[
                ContextItem(
                    content="code content",
                    source=ContextSource.REMEDIATION,
                    confidence=0.9,
                )
            ],
            query="test",
            target_entity="test",
        )
        result = agent._extract_code_for_review("task", hybrid)
        assert result == "code content"

    def test_extract_code_for_review_from_string(self):
        """Test extracting code from string context."""
        agent = SpawnableReviewerAgent()
        result = agent._extract_code_for_review("task", "direct code string")
        assert result == "direct code string"


# =============================================================================
# Test SpawnableValidatorAgent
# =============================================================================


class TestSpawnableValidatorAgent:
    """Tests for SpawnableValidatorAgent."""

    def test_capability(self):
        """Test validator agent capability."""
        agent = SpawnableValidatorAgent()
        assert agent.capability == AgentCapability.PATCH_VALIDATION

    @pytest.mark.asyncio
    async def test_execute_standard_validation(self):
        """Test standard code validation."""
        mock_llm = MagicMock()
        agent = SpawnableValidatorAgent(llm_client=mock_llm)

        mock_validator = AsyncMock()
        mock_validator.validate_code = AsyncMock(
            return_value={"valid": True, "tokens_used": 40}
        )

        with patch.object(agent, "_get_wrapped_agent", return_value=mock_validator):
            result = await agent.execute("Validate code", {"code": "test_code()"})

        assert result.success is True
        mock_validator.validate_code.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_sandbox_validation(self):
        """Test sandbox validation."""
        mock_llm = MagicMock()
        agent = SpawnableValidatorAgent(llm_client=mock_llm)

        mock_validator = AsyncMock()
        mock_validator.validate_with_sandbox = AsyncMock(
            return_value={"valid": True, "sandbox_passed": True, "tokens_used": 100}
        )

        with patch.object(agent, "_get_wrapped_agent", return_value=mock_validator):
            context = {
                "code": "test_code()",
                "test_code": "def test_it(): pass",
            }
            result = await agent.execute("Validate code in sandbox", context)

        assert result.success is True
        mock_validator.validate_with_sandbox.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_requirements_validation(self):
        """Test requirements-based validation."""
        mock_llm = MagicMock()
        agent = SpawnableValidatorAgent(llm_client=mock_llm)

        mock_validator = AsyncMock()
        mock_validator.validate_against_requirements = AsyncMock(
            return_value={"valid": True, "tokens_used": 55}
        )

        with patch.object(agent, "_get_wrapped_agent", return_value=mock_validator):
            context = {
                "code": "test_code()",
                "requirements": ["must be secure", "must be fast"],
            }
            result = await agent.execute("Validate against requirements", context)

        assert result.success is True
        mock_validator.validate_against_requirements.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_no_code_provided(self):
        """Test execution fails when no code provided."""
        agent = SpawnableValidatorAgent()
        result = await agent.execute("Validate code", {})

        assert result.success is False
        assert "No code provided" in result.error

    @pytest.mark.asyncio
    async def test_execute_validation_fails(self):
        """Test when validation returns invalid."""
        mock_llm = MagicMock()
        agent = SpawnableValidatorAgent(llm_client=mock_llm)

        mock_validator = AsyncMock()
        mock_validator.validate_code = AsyncMock(
            return_value={"valid": False, "errors": ["Type error"], "tokens_used": 30}
        )

        with patch.object(agent, "_get_wrapped_agent", return_value=mock_validator):
            result = await agent.execute("Validate code", {"code": "bad_code()"})

        assert result.success is False
        assert result.error == "Validation failed"

    def test_extract_requirements_from_list(self):
        """Test extracting requirements list."""
        agent = SpawnableValidatorAgent()
        context = {"requirements": ["req1", "req2"]}
        result = agent._extract_requirements(context)
        assert result == ["req1", "req2"]

    def test_extract_requirements_from_string(self):
        """Test extracting requirements from single string."""
        agent = SpawnableValidatorAgent()
        context = {"requirements": "single requirement"}
        result = agent._extract_requirements(context)
        assert result == ["single requirement"]


# =============================================================================
# Test SpawnableVulnerabilityScanAgent
# =============================================================================


class TestSpawnableVulnerabilityScanAgent:
    """Tests for SpawnableVulnerabilityScanAgent."""

    def test_capability(self):
        """Test vulnerability scan agent capability."""
        agent = SpawnableVulnerabilityScanAgent()
        assert agent.capability == AgentCapability.VULNERABILITY_SCAN

    @pytest.mark.asyncio
    async def test_execute_with_analyze_dependencies(self):
        """Test executing with analyze_dependencies method."""
        mock_llm = MagicMock()
        agent = SpawnableVulnerabilityScanAgent(llm_client=mock_llm)

        mock_scanner = AsyncMock()
        mock_scanner.analyze_dependencies = AsyncMock(
            return_value={"vulnerabilities": [{"id": "CVE-123"}]}
        )

        with patch.object(agent, "_get_wrapped_agent", return_value=mock_scanner):
            context = {"dependencies": [{"name": "package1", "version": "1.0.0"}]}
            result = await agent.execute("Scan dependencies", context)

        assert result.success is True
        mock_scanner.analyze_dependencies.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_fallback(self):
        """Test fallback when analyze_dependencies not available."""
        mock_llm = MagicMock()
        agent = SpawnableVulnerabilityScanAgent(llm_client=mock_llm)

        mock_scanner = MagicMock(spec=[])  # No analyze_dependencies method

        with patch.object(agent, "_get_wrapped_agent", return_value=mock_scanner):
            result = await agent.execute("Scan dependencies", {})

        assert result.success is True
        assert result.output["scan_status"] == "completed"


# =============================================================================
# Test SpawnableArchitectureReviewAgent
# =============================================================================


class TestSpawnableArchitectureReviewAgent:
    """Tests for SpawnableArchitectureReviewAgent."""

    def test_capability(self):
        """Test architecture review agent capability."""
        agent = SpawnableArchitectureReviewAgent()
        assert agent.capability == AgentCapability.ARCHITECTURE_REVIEW

    @pytest.mark.asyncio
    async def test_execute_review_architecture(self):
        """Test executing architecture review."""
        mock_llm = MagicMock()
        agent = SpawnableArchitectureReviewAgent(llm_client=mock_llm)

        mock_reviewer = AsyncMock()
        mock_reviewer.review_architecture = AsyncMock(
            return_value={"recommendations": ["Use microservices"]}
        )

        with patch.object(agent, "_get_wrapped_agent", return_value=mock_reviewer):
            result = await agent.execute(
                "Review system architecture", {"docs": "arch.md"}
            )

        assert result.success is True
        mock_reviewer.review_architecture.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_evaluate_fallback(self):
        """Test fallback to evaluate method."""
        mock_llm = MagicMock()
        agent = SpawnableArchitectureReviewAgent(llm_client=mock_llm)

        mock_reviewer = MagicMock(spec=["evaluate"])
        mock_reviewer.evaluate = AsyncMock(return_value={"score": 8.5})

        with patch.object(agent, "_get_wrapped_agent", return_value=mock_reviewer):
            result = await agent.execute("Evaluate architecture", {})

        assert result.success is True
        mock_reviewer.evaluate.assert_called_once()


# =============================================================================
# Test SpawnableThreatAnalysisAgent
# =============================================================================


class TestSpawnableThreatAnalysisAgent:
    """Tests for SpawnableThreatAnalysisAgent."""

    def test_capability(self):
        """Test threat analysis agent capability."""
        agent = SpawnableThreatAnalysisAgent()
        assert agent.capability == AgentCapability.THREAT_ANALYSIS

    @pytest.mark.asyncio
    async def test_execute_analyze_threats(self):
        """Test threat analysis execution."""
        mock_llm = MagicMock()
        agent = SpawnableThreatAnalysisAgent(llm_client=mock_llm)

        mock_analyzer = AsyncMock()
        mock_analyzer.analyze_threats = AsyncMock(
            return_value={"threats": [{"type": "INJECTION", "severity": "HIGH"}]}
        )

        with patch.object(agent, "_get_wrapped_agent", return_value=mock_analyzer):
            result = await agent.execute("Analyze threats in API", {"endpoints": []})

        assert result.success is True
        mock_analyzer.analyze_threats.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_generate_recommendations_fallback(self):
        """Test fallback to generate_recommendations."""
        mock_llm = MagicMock()
        agent = SpawnableThreatAnalysisAgent(llm_client=mock_llm)

        mock_analyzer = MagicMock(spec=["generate_recommendations"])
        mock_analyzer.generate_recommendations = AsyncMock(
            return_value={"recommendations": ["Enable WAF"]}
        )

        with patch.object(agent, "_get_wrapped_agent", return_value=mock_analyzer):
            result = await agent.execute("Get security recommendations", {})

        assert result.success is True
        mock_analyzer.generate_recommendations.assert_called_once()


# =============================================================================
# Test SpawnableGitHubIntegrationAgent
# =============================================================================


class TestSpawnableGitHubIntegrationAgent:
    """Tests for SpawnableGitHubIntegrationAgent."""

    def test_capability(self):
        """Test GitHub integration agent capability."""
        agent = SpawnableGitHubIntegrationAgent()
        assert agent.capability == AgentCapability.GITHUB_INTEGRATION

    @pytest.mark.asyncio
    async def test_execute_create_pr(self):
        """Test PR creation execution."""
        agent = SpawnableGitHubIntegrationAgent()

        # Create mock result
        mock_result = MagicMock()
        mock_result.status.value = "success"
        mock_result.pr_number = 123
        mock_result.pr_url = "https://github.com/org/repo/pull/123"
        mock_result.branch_name = "security/fix-xss"
        mock_result.commit_sha = "abc123"
        mock_result.comment_ids = [1, 2]
        mock_result.error_message = None

        mock_service = AsyncMock()
        mock_service.create_remediation_pr = AsyncMock(return_value=mock_result)

        with patch.object(agent, "_get_github_service", return_value=mock_service):
            context = {
                "repo_url": "https://github.com/org/repo",
                "patch_info": {
                    "patch_id": "PATCH-001",
                    "patch_content": "--- a/app.py\n+++ b/app.py",
                    "patched_code": "safe_code()",
                    "file_path": "app.py",
                    "confidence_score": 0.95,
                    "agent_id": "coder-001",
                },
                "vulnerability_info": {
                    "vulnerability_id": "V-001",
                    "vulnerability_type": "XSS",
                    "severity": "HIGH",
                    "file_path": "app.py",
                    "line_number": 42,
                    "description": "XSS vulnerability",
                },
                "approver_email": "security@example.com",
                "approval_id": "APPROVAL-001",
            }
            result = await agent.execute("Create remediation PR", context)

        assert result.success is True
        assert result.output["pr_number"] == 123

    @pytest.mark.asyncio
    async def test_execute_no_dict_context(self):
        """Test execution fails without dict context."""
        agent = SpawnableGitHubIntegrationAgent()
        result = await agent.execute("Create PR", "string context")

        assert result.success is False
        assert "Context must be a dict" in result.error


# =============================================================================
# Test SpawnableDesignSecurityReviewAgent
# =============================================================================


class TestSpawnableDesignSecurityReviewAgent:
    """Tests for SpawnableDesignSecurityReviewAgent."""

    def test_capability(self):
        """Test design security review capability."""
        agent = SpawnableDesignSecurityReviewAgent()
        assert agent.capability == AgentCapability.DESIGN_SECURITY_REVIEW

    @pytest.mark.asyncio
    async def test_execute_repository_scan(self):
        """Test repository documentation scan."""
        mock_llm = MagicMock()
        agent = SpawnableDesignSecurityReviewAgent(llm_client=mock_llm)

        mock_finding = MagicMock()
        mock_finding.to_dict.return_value = {"issue": "Missing auth check"}

        mock_result = MagicMock()
        mock_result.document_path = "docs/api.md"
        mock_result.document_type = "markdown"
        mock_result.findings = [mock_finding]
        mock_result.total_risk_score = 5.0

        mock_reviewer = AsyncMock()
        mock_reviewer.review_repository_docs = AsyncMock(return_value=[mock_result])

        with patch.object(agent, "_get_design_agent", return_value=mock_reviewer):
            context = {"repo_path": "/path/to/repo"}
            result = await agent.execute("Review design docs", context)

        assert result.success is True
        assert result.output["documents_analyzed"] == 1
        mock_reviewer.review_repository_docs.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_single_document(self):
        """Test single document review."""
        mock_llm = MagicMock()
        agent = SpawnableDesignSecurityReviewAgent(llm_client=mock_llm)

        mock_finding = MagicMock()
        mock_finding.to_dict.return_value = {"issue": "Hardcoded credentials"}

        mock_reviewer = AsyncMock()
        mock_reviewer.review_document = AsyncMock(return_value=[mock_finding])

        with patch.object(agent, "_get_design_agent", return_value=mock_reviewer):
            context = {"document_path": "docs/adr-001.md"}
            result = await agent.execute("Review ADR", context)

        assert result.success is True
        assert result.output["finding_count"] == 1

    @pytest.mark.asyncio
    async def test_execute_task_as_content(self):
        """Test treating task as document content."""
        mock_llm = MagicMock()
        agent = SpawnableDesignSecurityReviewAgent(llm_client=mock_llm)

        mock_reviewer = AsyncMock()
        mock_reviewer.review_document = AsyncMock(return_value=[])

        with patch.object(agent, "_get_design_agent", return_value=mock_reviewer):
            result = await agent.execute(
                "# API Design\nStores passwords in plaintext", None
            )

        assert result.success is True


# =============================================================================
# Test SpawnableBusinessLogicAnalyzerAgent
# =============================================================================


class TestSpawnableBusinessLogicAnalyzerAgent:
    """Tests for SpawnableBusinessLogicAnalyzerAgent."""

    def test_capability(self):
        """Test business logic analyzer capability."""
        agent = SpawnableBusinessLogicAnalyzerAgent()
        assert agent.capability == AgentCapability.BUSINESS_LOGIC_ANALYSIS

    @pytest.mark.asyncio
    async def test_execute_repository_analysis(self):
        """Test repository analysis."""
        mock_llm = MagicMock()
        agent = SpawnableBusinessLogicAnalyzerAgent(llm_client=mock_llm)

        mock_finding = MagicMock()
        mock_finding.to_dict.return_value = {"type": "IDOR"}

        mock_result = MagicMock()
        mock_result.total_files_analyzed = 10
        mock_result.total_functions_analyzed = 50
        mock_result.findings = [mock_finding]
        mock_result.risk_score = 7.5
        mock_result.authorization_flows = ["flow1"]
        mock_result.authorization_gaps = []

        mock_analyzer = AsyncMock()
        mock_analyzer.analyze_repository = AsyncMock(return_value=mock_result)

        with patch.object(agent, "_get_analyzer_agent", return_value=mock_analyzer):
            context = {"repo_path": "/path/to/repo"}
            result = await agent.execute("Analyze business logic", context)

        assert result.success is True
        assert result.output["files_analyzed"] == 10

    @pytest.mark.asyncio
    async def test_execute_single_file(self):
        """Test single file analysis."""
        mock_llm = MagicMock()
        agent = SpawnableBusinessLogicAnalyzerAgent(llm_client=mock_llm)

        mock_finding = MagicMock()
        mock_finding.to_dict.return_value = {"type": "RACE_CONDITION"}

        mock_analyzer = AsyncMock()
        mock_analyzer.analyze_file = AsyncMock(return_value=[mock_finding])

        with patch.object(agent, "_get_analyzer_agent", return_value=mock_analyzer):
            context = {"file_path": "api/users.py"}
            result = await agent.execute("Analyze file", context)

        assert result.success is True
        assert result.output["finding_count"] == 1


# =============================================================================
# Test SpawnablePenetrationTestingAgent
# =============================================================================


class TestSpawnablePenetrationTestingAgent:
    """Tests for SpawnablePenetrationTestingAgent."""

    def test_capability(self):
        """Test penetration testing capability."""
        agent = SpawnablePenetrationTestingAgent()
        assert agent.capability == AgentCapability.PENETRATION_TESTING

    @pytest.mark.asyncio
    async def test_execute_list_chains(self):
        """Test listing available attack chains."""
        agent = SpawnablePenetrationTestingAgent()

        mock_chain = MagicMock()
        mock_chain.to_dict.return_value = {"id": "chain-1", "name": "SQL Injection"}

        mock_pentest = MagicMock()
        mock_pentest.get_available_chains = MagicMock(return_value=[mock_chain])

        with patch.object(agent, "_get_pentest_agent", return_value=mock_pentest):
            context = {"list_chains": True}
            result = await agent.execute("List attack chains", context)

        assert result.success is True
        assert result.output["total_chains"] == 1

    @pytest.mark.asyncio
    async def test_execute_chain_missing_id(self):
        """Test execution fails without chain_id."""
        agent = SpawnablePenetrationTestingAgent()

        mock_pentest = MagicMock()
        with patch.object(agent, "_get_pentest_agent", return_value=mock_pentest):
            context = {"sandbox_id": "sandbox-1"}
            result = await agent.execute("Execute chain", context)

        assert result.success is False
        assert "chain_id is required" in result.error

    @pytest.mark.asyncio
    async def test_execute_chain_missing_sandbox(self):
        """Test execution fails without sandbox_id."""
        agent = SpawnablePenetrationTestingAgent()

        mock_pentest = MagicMock()
        with patch.object(agent, "_get_pentest_agent", return_value=mock_pentest):
            context = {"chain_id": "chain-1"}
            result = await agent.execute("Execute chain", context)

        assert result.success is False
        assert "sandbox_id is required" in result.error

    @pytest.mark.asyncio
    async def test_execute_chain_success(self):
        """Test successful chain execution."""
        agent = SpawnablePenetrationTestingAgent()

        mock_result = MagicMock()
        mock_result.status.value = "completed"
        mock_result.to_dict.return_value = {"status": "completed", "findings": []}

        mock_pentest = AsyncMock()
        mock_pentest.execute_chain = AsyncMock(return_value=mock_result)

        with patch.object(agent, "_get_pentest_agent", return_value=mock_pentest):
            context = {
                "chain_id": "chain-1",
                "sandbox_id": "sandbox-1",
                "target_url": "http://localhost:8080",
            }
            result = await agent.execute("Execute chain", context)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_no_context(self):
        """Test execution fails without context."""
        agent = SpawnablePenetrationTestingAgent()
        result = await agent.execute("Execute chain", None)

        assert result.success is False
        assert "Context with chain_id" in result.error


# =============================================================================
# Test Factory Functions
# =============================================================================


class TestFactoryFunctions:
    """Tests for agent factory functions."""

    def test_create_spawnable_coder_agent(self):
        """Test coder agent factory."""
        mock_llm = MagicMock()
        agent = create_spawnable_coder_agent(llm_client=mock_llm, max_spawn_depth=3)

        assert isinstance(agent, SpawnableCoderAgent)
        assert agent.llm == mock_llm
        assert agent.max_spawn_depth == 3

    def test_create_spawnable_reviewer_agent(self):
        """Test reviewer agent factory."""
        mock_llm = MagicMock()
        agent = create_spawnable_reviewer_agent(llm_client=mock_llm, can_spawn=False)

        assert isinstance(agent, SpawnableReviewerAgent)
        assert agent.can_spawn is False

    def test_create_spawnable_validator_agent(self):
        """Test validator agent factory."""
        mock_registry = MagicMock()
        agent = create_spawnable_validator_agent(registry=mock_registry)

        assert isinstance(agent, SpawnableValidatorAgent)

    def test_create_spawnable_vulnerability_scan_agent(self):
        """Test vulnerability scan agent factory."""
        agent = create_spawnable_vulnerability_scan_agent()
        assert isinstance(agent, SpawnableVulnerabilityScanAgent)

    def test_create_spawnable_architecture_review_agent(self):
        """Test architecture review agent factory."""
        agent = create_spawnable_architecture_review_agent()
        assert isinstance(agent, SpawnableArchitectureReviewAgent)

    def test_create_spawnable_threat_analysis_agent(self):
        """Test threat analysis agent factory."""
        agent = create_spawnable_threat_analysis_agent()
        assert isinstance(agent, SpawnableThreatAnalysisAgent)

    def test_create_spawnable_github_integration_agent(self):
        """Test GitHub integration agent factory."""
        agent = create_spawnable_github_integration_agent()
        assert isinstance(agent, SpawnableGitHubIntegrationAgent)

    def test_create_spawnable_design_security_review_agent(self):
        """Test design security review agent factory."""
        agent = create_spawnable_design_security_review_agent()
        assert isinstance(agent, SpawnableDesignSecurityReviewAgent)

    def test_create_spawnable_business_logic_analyzer_agent(self):
        """Test business logic analyzer agent factory."""
        agent = create_spawnable_business_logic_analyzer_agent()
        assert isinstance(agent, SpawnableBusinessLogicAnalyzerAgent)

    def test_create_spawnable_penetration_testing_agent(self):
        """Test penetration testing agent factory."""
        agent = create_spawnable_penetration_testing_agent()
        assert isinstance(agent, SpawnablePenetrationTestingAgent)


# =============================================================================
# Test Registry Integration
# =============================================================================


class TestRegistryIntegration:
    """Tests for registry integration functions."""

    def test_register_all_agents(self):
        """Test registering all agents with registry."""
        registry = AgentRegistry()
        mock_llm = MagicMock()

        register_all_agents(registry, llm_client=mock_llm)

        # Verify all capabilities are registered
        expected_capabilities = [
            AgentCapability.CODE_GENERATION,
            AgentCapability.SECURITY_REVIEW,
            AgentCapability.PATCH_VALIDATION,
            AgentCapability.VULNERABILITY_SCAN,
            AgentCapability.ARCHITECTURE_REVIEW,
            AgentCapability.THREAT_ANALYSIS,
            AgentCapability.GITHUB_INTEGRATION,
            AgentCapability.DESIGN_SECURITY_REVIEW,
            AgentCapability.BUSINESS_LOGIC_ANALYSIS,
            AgentCapability.PENETRATION_TESTING,
        ]

        for capability in expected_capabilities:
            # Registry should have factory for each capability
            assert capability in registry._agent_factories

    def test_create_production_meta_orchestrator(self):
        """Test creating production MetaOrchestrator."""
        mock_llm = MagicMock()

        # Actually create the orchestrator - it uses real imports
        orchestrator = create_production_meta_orchestrator(
            llm_client=mock_llm,
            autonomy_preset="enterprise_standard",
        )

        # Verify orchestrator was created with correct settings
        assert orchestrator is not None
        assert orchestrator.registry is not None


# =============================================================================
# Test Lazy Initialization
# =============================================================================


class TestLazyInitialization:
    """Tests for lazy agent initialization."""

    def test_coder_agent_lazy_init(self):
        """Test CoderAgent is lazily initialized."""
        agent = SpawnableCoderAgent()
        assert agent._wrapped_agent is None

        # Get the wrapped agent - it will import and instantiate
        with patch("src.agents.coder_agent.CoderAgent") as mock_class:
            mock_class.return_value = MagicMock()
            wrapped = agent._get_wrapped_agent()
            assert wrapped is not None

            # Second call should return same instance (cached)
            wrapped2 = agent._get_wrapped_agent()
            assert wrapped2 is wrapped

    def test_reviewer_agent_lazy_init(self):
        """Test ReviewerAgent is lazily initialized."""
        agent = SpawnableReviewerAgent()
        assert agent._wrapped_agent is None

        with patch("src.agents.reviewer_agent.ReviewerAgent") as mock_class:
            mock_class.return_value = MagicMock()
            wrapped = agent._get_wrapped_agent()
            assert wrapped is not None

    def test_validator_agent_lazy_init(self):
        """Test ValidatorAgent is lazily initialized."""
        agent = SpawnableValidatorAgent()
        assert agent._wrapped_agent is None

        with patch("src.agents.validator_agent.ValidatorAgent") as mock_class:
            mock_class.return_value = MagicMock()
            wrapped = agent._get_wrapped_agent()
            assert wrapped is not None

    def test_github_service_lazy_init(self):
        """Test GitHub service is lazily initialized."""
        agent = SpawnableGitHubIntegrationAgent()
        assert agent._wrapped_agent is None

        with patch("src.services.github_pr_service.GitHubPRService") as mock_class:
            mock_class.return_value = MagicMock()
            service = agent._get_github_service()
            assert service is not None


# =============================================================================
# Test Error Handling
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in adapters."""

    @pytest.mark.asyncio
    async def test_coder_agent_exception_handling(self):
        """Test CoderAgent exception handling."""
        agent = SpawnableCoderAgent()
        mock_coder = AsyncMock()
        mock_coder.generate_code = AsyncMock(
            side_effect=RuntimeError("Connection lost")
        )

        with patch.object(agent, "_get_wrapped_agent", return_value=mock_coder):
            result = await agent.execute("Generate code")

        assert result.success is False
        assert "Connection lost" in result.error
        assert result.agent_id is not None

    @pytest.mark.asyncio
    async def test_architecture_review_exception_handling(self):
        """Test ArchitectureReviewAgent exception handling."""
        agent = SpawnableArchitectureReviewAgent()
        mock_reviewer = MagicMock()
        mock_reviewer.review_architecture = AsyncMock(
            side_effect=ValueError("Invalid input")
        )

        with patch.object(agent, "_get_wrapped_agent", return_value=mock_reviewer):
            result = await agent.execute("Review architecture")

        assert result.success is False
        assert "Invalid input" in result.error

    @pytest.mark.asyncio
    async def test_design_review_exception_handling(self):
        """Test DesignSecurityReviewAgent exception handling."""
        agent = SpawnableDesignSecurityReviewAgent()
        mock_reviewer = AsyncMock()
        mock_reviewer.review_document = AsyncMock(
            side_effect=FileNotFoundError("Not found")
        )

        with patch.object(agent, "_get_design_agent", return_value=mock_reviewer):
            context = {"document_path": "/missing/file.md"}
            result = await agent.execute("Review document", context)

        assert result.success is False
        assert "Not found" in result.error
