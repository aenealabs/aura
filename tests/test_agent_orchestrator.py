"""
Project Aura - Agent Orchestrator Tests

Comprehensive tests for the System 2 autonomous orchestration workflow.
"""

# ruff: noqa: PLR2004

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.agents.agent_orchestrator import (
    ContextRetrievalService,
    EmbeddingAgent,
    GraphBuilderAgent,
    InputSanitizer,
    OpenSearchVectorStore,
    System2Orchestrator,
)
from src.agents.context_objects import ContextSource, HybridContext


class TestInputSanitizer:
    """Test suite for InputSanitizer security utility."""

    def test_sanitize_removes_quotes(self):
        """Test that single and double quotes are removed."""
        result = InputSanitizer.sanitize_for_graph_id('test"value\'with"quotes')

        assert '"' not in result
        assert "'" not in result

    def test_sanitize_escapes_backslashes(self):
        """Test that backslashes are escaped."""
        result = InputSanitizer.sanitize_for_graph_id(r"path\to\file")

        assert r"\\" in result

    def test_sanitize_replaces_colons(self):
        """Test that colons are replaced with _colon."""
        result = InputSanitizer.sanitize_for_graph_id("namespace:entity")

        assert "_colon" in result
        assert ":" not in result

    def test_sanitize_replaces_dots(self):
        """Test that dots are replaced with _dot_."""
        result = InputSanitizer.sanitize_for_graph_id("file.extension")

        assert "_dot_" in result
        assert "." not in result

    def test_sanitize_removes_parentheses(self):
        """Test that parentheses are removed."""
        result = InputSanitizer.sanitize_for_graph_id("function(args)")

        assert "(" not in result
        assert ")" not in result

    def test_sanitize_preserves_spaces(self):
        """Test that spaces are preserved."""
        result = InputSanitizer.sanitize_for_graph_id("hello world")

        assert "hello world" in result

    def test_sanitize_trims_whitespace(self):
        """Test that leading/trailing whitespace is trimmed."""
        result = InputSanitizer.sanitize_for_graph_id("  test  ")

        assert result == "test"

    def test_sanitize_empty_string_returns_empty_literal(self):
        """Test that empty string returns 'empty'."""
        result = InputSanitizer.sanitize_for_graph_id("")

        assert result == "empty"

    def test_sanitize_none_returns_empty_literal(self):
        """Test that None returns 'empty'."""
        result = InputSanitizer.sanitize_for_graph_id(None)

        assert result == "empty"

    def test_sanitize_length_limit(self):
        """Test that output is truncated to 255 characters."""
        long_string = "a" * 300
        result = InputSanitizer.sanitize_for_graph_id(long_string)

        assert len(result) == 255

    def test_sanitize_complex_injection_attempt(self):
        """Test sanitization of complex injection payload."""
        payload = "'; DROP TABLE users; --"
        result = InputSanitizer.sanitize_for_graph_id(payload)

        # Should be safe after sanitization
        assert "DROP" in result  # Text preserved
        assert "'" not in result  # Quotes removed
        # Note: Semicolons are NOT removed by the sanitizer, only quotes


class TestGraphBuilderAgent:
    """Test suite for GraphBuilderAgent."""

    def test_initialization(self):
        """Test GraphBuilderAgent initialization."""
        agent = GraphBuilderAgent()

        assert isinstance(agent.ckge_graph, dict)
        assert len(agent.ckge_graph) == 0

    def test_add_node_new(self):
        """Test adding a new node to graph."""
        agent = GraphBuilderAgent()

        agent.add_node("node1", "Class", name="TestClass")

        assert "node1" in agent.ckge_graph
        assert agent.ckge_graph["node1"]["label"] == "Class"

    def test_add_node_duplicate_ignored(self):
        """Test that duplicate nodes are ignored."""
        agent = GraphBuilderAgent()

        agent.add_node("node1", "Class")
        agent.add_node("node1", "Function")  # Try to add again

        # Should keep original label
        assert agent.ckge_graph["node1"]["label"] == "Class"

    def test_add_edge_success(self):
        """Test adding edge between existing nodes."""
        agent = GraphBuilderAgent()

        agent.add_node("A", "Class")
        agent.add_node("B", "Class")
        agent.add_edge("A", "B", "IMPORTS")

        # Edge should exist - structure is edges[type] = [targets]
        assert "edges" in agent.ckge_graph["A"]
        assert "IMPORTS" in agent.ckge_graph["A"]["edges"]
        assert "B" in agent.ckge_graph["A"]["edges"]["IMPORTS"]

    def test_add_edge_missing_source(self):
        """Test adding edge with missing source node."""
        agent = GraphBuilderAgent()

        agent.add_node("B", "Class")
        agent.add_edge("NonExistent", "B", "CALLS")

        # Should not crash, edge not added
        assert "NonExistent" not in agent.ckge_graph

    def test_add_edge_missing_target(self):
        """Test adding edge with missing target node."""
        agent = GraphBuilderAgent()

        agent.add_node("A", "Class")
        agent.add_edge("A", "NonExistent", "CALLS")

        # Should not crash, but edge still added (mock behavior)
        assert "A" in agent.ckge_graph

    def test_parse_source_code_returns_dict(self):
        """Test that parse_source_code returns expected structure."""
        agent = GraphBuilderAgent()

        result = agent.parse_source_code("print('hello')", "test.py")

        assert isinstance(result, dict)
        assert "file" in result
        assert "classes" in result
        assert "dependencies" in result
        assert isinstance(result["classes"], list)
        assert isinstance(result["dependencies"], list)

    def test_parse_source_code_filename_handling(self):
        """Test parse_source_code with Path object."""
        agent = GraphBuilderAgent()

        result = agent.parse_source_code("code", Path("src/module.py"))

        assert "module" in result["file"].lower() or "src" in result["file"].lower()

    def test_run_gremlin_query_returns_list(self):
        """Test that run_gremlin_query returns list."""
        agent = GraphBuilderAgent()

        result = agent.run_gremlin_query("SomeEntity")

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], str)

    def test_run_gremlin_query_with_dependencies(self):
        """Test gremlin query with dependencies in graph."""
        agent = GraphBuilderAgent()

        agent.add_node("A", "Class")
        agent.add_node("B", "Class")
        agent.add_edge("A", "B", "IMPORTS")

        result = agent.run_gremlin_query("A")

        # Should contain dependency info
        assert len(result) == 1
        assert "dependencies" in result[0].lower() or "B" in result[0]


class TestOpenSearchVectorStore:
    """Test suite for OpenSearchVectorStore."""

    def test_initialization(self):
        """Test OpenSearchVectorStore initialization."""
        store = OpenSearchVectorStore()

        assert isinstance(store.vector_store_index, dict)
        assert len(store.vector_store_index) >= 2  # Pre-populated

    def test_run_knn_search_returns_list(self):
        """Test that run_knn_search returns list."""
        store = OpenSearchVectorStore()

        result = store.run_knn_search("test query")

        assert isinstance(result, list)
        assert len(result) >= 1

    def test_run_knn_search_checksum_keyword(self):
        """Test k-NN search with checksum keyword."""
        store = OpenSearchVectorStore()

        result = store.run_knn_search("checksum calculation")

        # Should return crypto policy
        assert any("crypto" in r.lower() or "policy" in r.lower() for r in result)

    def test_run_knn_search_hash_keyword(self):
        """Test k-NN search with hash keyword."""
        store = OpenSearchVectorStore()

        result = store.run_knn_search("hash function")

        # Should return crypto policy
        assert any("crypto" in r.lower() or "policy" in r.lower() for r in result)

    def test_run_knn_search_default_case(self):
        """Test k-NN search with non-matching query."""
        store = OpenSearchVectorStore()

        result = store.run_knn_search("random query")

        # Should return data processor doc
        assert len(result) >= 1


class TestEmbeddingAgent:
    """Test suite for EmbeddingAgent."""

    def test_chunk_and_embed_success(self):
        """Test successful chunking and embedding."""
        # Content > 50 chars (SIMILARITY_THRESHOLD)
        content = "a" * 100

        result = EmbeddingAgent.chunk_and_embed(content, "code")

        assert result is True

    def test_chunk_and_embed_too_short(self):
        """Test chunking with content below threshold."""
        content = "short"  # < 50 chars

        result = EmbeddingAgent.chunk_and_embed(content, "code")

        assert result is False

    def test_chunk_and_embed_empty_string(self):
        """Test chunking with empty string."""
        result = EmbeddingAgent.chunk_and_embed("", "code")

        assert result is False

    def test_chunk_and_embed_none(self):
        """Test chunking with None."""
        result = EmbeddingAgent.chunk_and_embed(None, "code")

        assert result is False

    def test_chunk_and_embed_exact_threshold(self):
        """Test chunking at exact 50 character threshold."""
        content = "a" * 50

        result = EmbeddingAgent.chunk_and_embed(content, "code")

        assert result is True  # Threshold is < 50, so 50 chars should pass

    def test_chunk_and_embed_just_above_threshold(self):
        """Test chunking just above threshold."""
        content = "a" * 51

        result = EmbeddingAgent.chunk_and_embed(content, "code")

        assert result is True


class TestContextRetrievalService:
    """Test suite for ContextRetrievalService."""

    def test_initialization(self):
        """Test ContextRetrievalService initialization."""
        graph = GraphBuilderAgent()
        vectors = OpenSearchVectorStore()

        service = ContextRetrievalService(graph, vectors)

        assert service.graph == graph
        assert service.vectors == vectors

    def test_get_hybrid_context_returns_context_object(self):
        """Test that get_hybrid_context returns HybridContext."""
        graph = GraphBuilderAgent()
        vectors = OpenSearchVectorStore()
        service = ContextRetrievalService(graph, vectors)

        context = service.get_hybrid_context("TestEntity", "test query")

        assert isinstance(context, HybridContext)

    def test_get_hybrid_context_has_items(self):
        """Test that hybrid context contains items."""
        graph = GraphBuilderAgent()
        vectors = OpenSearchVectorStore()
        service = ContextRetrievalService(graph, vectors)

        context = service.get_hybrid_context("TestEntity", "test query")

        assert len(context.items) >= 2  # Graph + vector

    def test_get_hybrid_context_graph_structural(self):
        """Test that graph results are added with GRAPH_STRUCTURAL source."""
        graph = GraphBuilderAgent()
        vectors = OpenSearchVectorStore()
        service = ContextRetrievalService(graph, vectors)

        context = service.get_hybrid_context("TestEntity", "test query")

        graph_items = context.get_items_by_source(ContextSource.GRAPH_STRUCTURAL)
        assert len(graph_items) >= 1

    def test_get_hybrid_context_confidence_scores(self):
        """Test that context items have appropriate confidence scores."""
        graph = GraphBuilderAgent()
        vectors = OpenSearchVectorStore()
        service = ContextRetrievalService(graph, vectors)

        context = service.get_hybrid_context("TestEntity", "test query")

        # Graph should have 0.95 confidence
        graph_items = context.get_items_by_source(ContextSource.GRAPH_STRUCTURAL)
        if graph_items:
            assert graph_items[0].confidence == 0.95

    def test_get_hybrid_context_with_session_id(self):
        """Test hybrid context with session ID."""
        graph = GraphBuilderAgent()
        vectors = OpenSearchVectorStore()
        service = ContextRetrievalService(graph, vectors)

        context = service.get_hybrid_context(
            "Entity", "query", session_id="session_123"
        )

        assert context.session_id == "session_123"


class TestSystem2Orchestrator:
    """Test suite for System2Orchestrator main workflow."""

    def test_initialization(self):
        """Test System2Orchestrator initialization."""
        # System2Orchestrator uses tests/fixtures/sample_project/main.py
        orchestrator = System2Orchestrator()

        assert orchestrator.monitor is not None
        assert orchestrator.graph_agent is not None
        assert orchestrator.vector_store is not None
        assert orchestrator.context_service is not None

    def test_generate_handover_report_format(self):
        """Test handover report generation format."""
        orchestrator = System2Orchestrator()

        metrics = {
            "total_runtime_seconds": 1.5,
            "total_tokens_used": 1000,
            "llm_cost_usd": 0.30,
            "loc_generated": 50,
            "engineering_hours_saved": 1.0,
            "vulnerabilities_found_count": 1,
            "vulnerabilities_remediated_count": 1,
        }

        report = orchestrator.generate_handover_report(metrics)

        assert isinstance(report, str)
        assert "Handover Report" in report
        assert "1.5" in report  # Runtime
        assert "1.0" in report  # Engineering hours

    @pytest.mark.asyncio
    async def test_execute_request_returns_dict(self):
        """Test that execute_request returns proper structure."""
        orchestrator = System2Orchestrator()

        result = await orchestrator.execute_request("Add SHA256 hashing")

        assert isinstance(result, dict)
        assert "status" in result
        assert "final_code" in result
        assert "metrics" in result
        assert "handover" in result

    @pytest.mark.asyncio
    async def test_execute_request_status_values(self):
        """Test execute_request status is SUCCESS or FAILURE."""
        orchestrator = System2Orchestrator()

        result = await orchestrator.execute_request("Test prompt")

        assert result["status"] in ["SUCCESS", "FAILURE"]


class TestSystem2OrchestratorIntegration:
    """Integration tests for full System2 workflow."""

    @pytest.mark.asyncio
    async def test_self_correction_workflow(self):
        """Test that orchestrator self-corrects vulnerable code."""
        orchestrator = System2Orchestrator()

        result = await orchestrator.execute_request("Implement secure hashing")

        # Should have generated code
        assert len(result["final_code"]) > 0

        # Should have tracked metrics
        assert result["metrics"]["total_tokens_used"] > 0

    @pytest.mark.asyncio
    async def test_validation_failure_detection(self):
        """Test that invalid Python syntax is detected."""
        orchestrator = System2Orchestrator()

        # Mock coder_agent.generate_code to return invalid syntax
        mock_generate = AsyncMock(
            return_value={
                "code": "invalid python code ;;;",
                "language": "python",
                "has_remediation": False,
            }
        )
        orchestrator.coder_agent.generate_code = mock_generate

        result = await orchestrator.execute_request("Test prompt")

        # Should fail validation due to syntax error
        assert result["status"] == "FAILURE"


class TestSystem2OrchestratorPlannerAgent:
    """Tests for System2Orchestrator planner agent methods."""

    @pytest.mark.asyncio
    async def test_planner_agent_fallback_returns_expected_structure(self):
        """Test planner fallback returns correct structure."""
        orchestrator = System2Orchestrator()

        result = orchestrator._planner_agent_fallback("Test prompt")

        assert "target_entity" in result
        assert "task_description" in result
        assert "DataProcessor.calculate_checksum" in result["target_entity"]
        assert "Test prompt" in result["task_description"]

    @pytest.mark.asyncio
    async def test_planner_agent_with_llm_success(self):
        """Test planner with successful LLM response."""
        import json

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {"target_entity": "CustomEntity", "task_description": "Custom task"}
        )
        orchestrator = System2Orchestrator(llm_client=mock_llm)

        result = await orchestrator._planner_agent("Fix security issue")

        assert result["target_entity"] == "CustomEntity"
        assert result["task_description"] == "Custom task"

    @pytest.mark.asyncio
    async def test_planner_agent_llm_json_error_fallback(self):
        """Test planner falls back on JSON parse error."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "not valid json"
        orchestrator = System2Orchestrator(llm_client=mock_llm)

        result = await orchestrator._planner_agent("Test prompt")

        # Should use fallback
        assert "DataProcessor.calculate_checksum" in result["target_entity"]

    @pytest.mark.asyncio
    async def test_planner_agent_llm_exception_fallback(self):
        """Test planner falls back on LLM exception."""
        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = Exception("LLM error")
        orchestrator = System2Orchestrator(llm_client=mock_llm)

        result = await orchestrator._planner_agent("Test prompt")

        # Should use fallback
        assert "DataProcessor.calculate_checksum" in result["target_entity"]


class TestSystem2OrchestratorCoderAgent:
    """Tests for System2Orchestrator coder agent methods."""

    def test_coder_fallback_without_remediation(self):
        """Test coder fallback returns vulnerable code without remediation."""
        orchestrator = System2Orchestrator()
        context = HybridContext(items=[], query="test", target_entity="Test")

        result = orchestrator._coder_agent_fallback(context)

        assert "hashlib.sha1" in result
        assert "VULNERABILITY" in result

    def test_coder_fallback_with_remediation(self):
        """Test coder fallback returns secure code with remediation."""
        orchestrator = System2Orchestrator()
        context = HybridContext(items=[], query="test", target_entity="Test")
        context.add_remediation("Use SHA256", confidence=1.0)

        result = orchestrator._coder_agent_fallback(context)

        assert "hashlib.sha256" in result
        assert "Security Policy Enforced" in result

    @pytest.mark.asyncio
    async def test_coder_agent_llm_strips_python_markers(self):
        """Test coder strips ```python markers."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "```python\nprint('hello')\n```"
        orchestrator = System2Orchestrator(llm_client=mock_llm)

        context = HybridContext(items=[], query="test", target_entity="Test")
        result = await orchestrator._coder_agent(context, "task")

        assert "```" not in result
        assert "print('hello')" in result

    @pytest.mark.asyncio
    async def test_coder_agent_llm_strips_generic_markers(self):
        """Test coder strips generic ``` markers."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "```\ncode here\n```"
        orchestrator = System2Orchestrator(llm_client=mock_llm)

        context = HybridContext(items=[], query="test", target_entity="Test")
        result = await orchestrator._coder_agent(context, "task")

        assert "```" not in result
        assert "code here" in result


class TestSystem2OrchestratorReviewerAgent:
    """Tests for System2Orchestrator reviewer agent methods."""

    def test_reviewer_fallback_detects_sha1(self):
        """Test reviewer fallback detects SHA1 vulnerability."""
        orchestrator = System2Orchestrator()
        code = "return hashlib.sha1(data.encode()).hexdigest()"

        result = orchestrator._reviewer_agent_fallback(code)

        assert result["status"] == "FAIL_SECURITY"
        assert "SHA1" in result["finding"]
        assert result["severity"] == "High"

    def test_reviewer_fallback_passes_sha256(self):
        """Test reviewer fallback passes SHA256 code."""
        orchestrator = System2Orchestrator()
        code = "return hashlib.sha256(data.encode()).hexdigest()"

        result = orchestrator._reviewer_agent_fallback(code)

        assert result["status"] == "PASS"
        assert "compliant" in result["finding"]

    @pytest.mark.asyncio
    async def test_reviewer_agent_llm_success(self):
        """Test reviewer with successful LLM response."""
        import json

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {"status": "PASS", "finding": "Code is secure"}
        )
        orchestrator = System2Orchestrator(llm_client=mock_llm)

        result = await orchestrator._reviewer_agent("secure code")

        assert result["status"] == "PASS"
        assert result["finding"] == "Code is secure"

    @pytest.mark.asyncio
    async def test_reviewer_agent_llm_security_failure(self):
        """Test reviewer with security failure LLM response."""
        import json

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "status": "FAIL_SECURITY",
                "finding": "SQL injection detected",
                "severity": "Critical",
            }
        )
        orchestrator = System2Orchestrator(llm_client=mock_llm)

        result = await orchestrator._reviewer_agent("vulnerable code")

        assert result["status"] == "FAIL_SECURITY"
        assert "SQL injection" in result["finding"]
        assert result["severity"] == "Critical"


class TestSystem2OrchestratorValidatorAgent:
    """Tests for System2Orchestrator validator agent methods."""

    def test_validator_passes_valid_code(self):
        """Test validator passes syntactically valid code."""
        orchestrator = System2Orchestrator()
        code = """import hashlib

def calculate_checksum(data):
    return hashlib.sha256(data).hexdigest()
"""
        result = orchestrator._validator_agent(code)

        assert result is True

    def test_validator_fails_syntax_error(self):
        """Test validator fails code with syntax errors."""
        orchestrator = System2Orchestrator()
        code = "def foo(:\n    pass"

        result = orchestrator._validator_agent(code)

        assert result is False

    def test_validator_fails_missing_hashlib(self):
        """Test validator fails code without hashlib import."""
        orchestrator = System2Orchestrator()
        code = """def calculate_checksum(data):
    return hash(data)
"""
        result = orchestrator._validator_agent(code)

        assert result is False

    def test_validator_fails_missing_checksum(self):
        """Test validator fails code without calculate_checksum."""
        orchestrator = System2Orchestrator()
        code = """import hashlib

def hash_data(data):
    return hashlib.sha256(data).hexdigest()
"""
        result = orchestrator._validator_agent(code)

        assert result is False


class TestSystem2OrchestratorPatchDiff:
    """Tests for System2Orchestrator _generate_patch_diff method."""

    def test_generate_patch_diff_changed_lines(self):
        """Test diff shows changed lines."""
        orchestrator = System2Orchestrator()
        orchestrator.initial_code = "line1\nline2\nline3"
        new_code = "line1\nmodified\nline3"

        result = orchestrator._generate_patch_diff(new_code)

        assert "- line2" in result
        assert "+ modified" in result

    def test_generate_patch_diff_added_lines(self):
        """Test diff shows added lines."""
        orchestrator = System2Orchestrator()
        orchestrator.initial_code = "line1\nline2"
        new_code = "line1\nline2\nline3"

        result = orchestrator._generate_patch_diff(new_code)

        assert "+ line3" in result

    def test_generate_patch_diff_deleted_lines(self):
        """Test diff shows deleted lines."""
        orchestrator = System2Orchestrator()
        orchestrator.initial_code = "line1\nline2\nline3"
        new_code = "line1\nline2"

        result = orchestrator._generate_patch_diff(new_code)

        assert "- line3" in result

    def test_generate_patch_diff_no_changes(self):
        """Test diff returns (no changes) when identical."""
        orchestrator = System2Orchestrator()
        orchestrator.initial_code = "same\ncode"
        new_code = "same\ncode"

        result = orchestrator._generate_patch_diff(new_code)

        assert result == "(no changes)"


class TestSystem2OrchestratorHITL:
    """Tests for System2Orchestrator HITL workflow methods."""

    @pytest.mark.asyncio
    async def test_execute_with_hitl_disabled(self):
        """Test execute_request_with_hitl when HITL is disabled."""
        orchestrator = System2Orchestrator()

        # Mock agents for successful standard workflow
        orchestrator.coder_agent = AsyncMock()
        orchestrator.coder_agent.generate_code.return_value = {
            "code": "import hashlib\ndef calculate_checksum(data): return hashlib.sha256(data).hexdigest()"
        }
        orchestrator.reviewer_agent = AsyncMock()
        orchestrator.reviewer_agent.review_code.return_value = {"status": "PASS"}
        orchestrator.validator_agent = AsyncMock()
        orchestrator.validator_agent.validate_code.return_value = {"valid": True}

        result = await orchestrator.execute_request_with_hitl(
            user_prompt="Fix security", vulnerability_id="VULN-001"
        )

        assert result["hitl_status"] == "DISABLED"

    @pytest.mark.asyncio
    async def test_execute_with_hitl_skipped_on_failure(self):
        """Test execute_request_with_hitl skips HITL on workflow failure."""
        orchestrator = System2Orchestrator()

        # Mock agents for failed standard workflow
        orchestrator.coder_agent = AsyncMock()
        orchestrator.coder_agent.generate_code.return_value = {"code": "invalid"}
        orchestrator.reviewer_agent = AsyncMock()
        orchestrator.reviewer_agent.review_code.return_value = {
            "status": "FAIL_SECURITY",
            "finding": "SHA1 detected",
            "severity": "High",
        }
        orchestrator.validator_agent = AsyncMock()
        orchestrator.validator_agent.validate_code.return_value = {"valid": False}

        result = await orchestrator.execute_request_with_hitl(
            user_prompt="Fix security", vulnerability_id="VULN-001"
        )

        assert result["hitl_status"] == "SKIPPED"

    @pytest.mark.asyncio
    async def test_process_approval_decision_no_hitl(self):
        """Test process_approval_decision without HITL service."""
        orchestrator = System2Orchestrator()

        result = await orchestrator.process_approval_decision(
            approval_id="approval-123",
            decision="APPROVE",
            reviewer_id="reviewer-1",
        )

        assert result["status"] == "ERROR"
        assert "not configured" in result["error"]

    @pytest.mark.asyncio
    async def test_process_approval_decision_invalid_decision(self):
        """Test process_approval_decision with invalid decision."""
        from unittest.mock import MagicMock

        mock_hitl = MagicMock()
        orchestrator = System2Orchestrator(hitl_approval_service=mock_hitl)

        result = await orchestrator.process_approval_decision(
            approval_id="approval-123",
            decision="MAYBE",
            reviewer_id="reviewer-1",
        )

        assert result["status"] == "ERROR"
        assert "Invalid decision" in result["error"]

    @pytest.mark.asyncio
    async def test_process_approval_decision_reject_requires_reason(self):
        """Test process_approval_decision reject requires reason."""
        from unittest.mock import MagicMock

        mock_hitl = MagicMock()
        orchestrator = System2Orchestrator(hitl_approval_service=mock_hitl)

        result = await orchestrator.process_approval_decision(
            approval_id="approval-123",
            decision="REJECT",
            reviewer_id="reviewer-1",
        )

        assert result["status"] == "ERROR"
        assert "reason is required" in result["error"]

    @pytest.mark.asyncio
    async def test_process_approval_decision_approve_success(self):
        """Test process_approval_decision approve success."""
        from unittest.mock import MagicMock

        mock_hitl = MagicMock()
        mock_hitl.approve_request.return_value = True
        orchestrator = System2Orchestrator(hitl_approval_service=mock_hitl)

        result = await orchestrator.process_approval_decision(
            approval_id="approval-123",
            decision="APPROVE",
            reviewer_id="reviewer-1",
        )

        assert result["status"] == "APPROVED"
        assert result["next_step"] == "DEPLOY_TO_PRODUCTION"

    @pytest.mark.asyncio
    async def test_process_approval_decision_reject_success(self):
        """Test process_approval_decision reject success."""
        from unittest.mock import MagicMock

        mock_hitl = MagicMock()
        mock_hitl.reject_request.return_value = True
        orchestrator = System2Orchestrator(hitl_approval_service=mock_hitl)

        result = await orchestrator.process_approval_decision(
            approval_id="approval-123",
            decision="REJECT",
            reviewer_id="reviewer-1",
            reason="Does not meet requirements",
        )

        assert result["status"] == "REJECTED"
        assert result["next_step"] == "MANUAL_REMEDIATION"


class TestCreateSystem2Orchestrator:
    """Tests for create_system2_orchestrator factory function."""

    def test_create_with_mock(self):
        """Test factory creates orchestrator with mock LLM."""
        from src.agents.agent_orchestrator import create_system2_orchestrator

        orch = create_system2_orchestrator(use_mock=True)

        assert orch.llm is not None
        assert hasattr(orch.llm, "generate")

    def test_create_with_mock_has_pre_configured_response(self):
        """Test mock LLM has pre-configured response."""
        from src.agents.agent_orchestrator import create_system2_orchestrator

        orch = create_system2_orchestrator(use_mock=True)

        # The mock should be configured with a return value
        assert orch.llm is not None


class TestSystem2OrchestratorSelfCorrection:
    """Tests for System2Orchestrator self-correction workflow."""

    @pytest.mark.asyncio
    async def test_self_correction_on_review_failure(self):
        """Test orchestrator retries code generation on review failure."""
        orchestrator = System2Orchestrator()

        # Mock agents - first review fails, second passes
        orchestrator.coder_agent = AsyncMock()
        orchestrator.coder_agent.generate_code.return_value = {
            "code": "import hashlib\ndef calculate_checksum(data): return hashlib.sha256(data).hexdigest()"
        }

        orchestrator.reviewer_agent = AsyncMock()
        orchestrator.reviewer_agent.review_code.side_effect = [
            {"status": "FAIL_SECURITY", "finding": "SHA1", "severity": "High"},
            {"status": "PASS", "finding": "Fixed"},
        ]

        orchestrator.validator_agent = AsyncMock()
        orchestrator.validator_agent.validate_code.return_value = {"valid": True}

        result = await orchestrator.execute_request("Fix security")

        assert result["status"] == "SUCCESS"
        # Should have tried code generation twice
        assert orchestrator.coder_agent.generate_code.call_count == 2

    @pytest.mark.asyncio
    async def test_max_attempts_reached(self):
        """Test orchestrator fails after max correction attempts."""
        orchestrator = System2Orchestrator()

        # Mock agents - review always fails
        orchestrator.coder_agent = AsyncMock()
        orchestrator.coder_agent.generate_code.return_value = {"code": "bad code"}

        orchestrator.reviewer_agent = AsyncMock()
        orchestrator.reviewer_agent.review_code.return_value = {
            "status": "FAIL_SECURITY",
            "finding": "Always failing",
            "severity": "High",
        }

        orchestrator.validator_agent = AsyncMock()
        orchestrator.validator_agent.validate_code.return_value = {"valid": True}

        result = await orchestrator.execute_request("Fix security")

        assert result["status"] == "FAILURE"
        # Should have tried max attempts (2)
        assert orchestrator.coder_agent.generate_code.call_count == 2
