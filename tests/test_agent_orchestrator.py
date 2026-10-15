"""
Project Aura - Agent Orchestrator Tests

Comprehensive tests for the System 2 autonomous orchestration workflow.
"""

# ruff: noqa: PLR2004

from pathlib import Path
from unittest.mock import AsyncMock, patch

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

    def test_validator_does_not_require_hardcoded_demo_strings(self):
        """Code unrelated to the checksum demo passes when the task asks for it."""
        orchestrator = System2Orchestrator()
        code = """def sanitize_username(name: str) -> str:
    return name.strip().lower()
"""
        result = orchestrator._validator_agent(
            code, expected_elements=["sanitize_username"]
        )

        assert result is True

    def test_validator_fails_missing_task_element(self):
        """Test validator fails when the task's target symbol is missing."""
        orchestrator = System2Orchestrator()
        code = """import hashlib

def hash_data(data):
    return hashlib.sha256(data).hexdigest()
"""
        result = orchestrator._validator_agent(
            code, expected_elements=["calculate_checksum"]
        )

        assert result is False

    def test_validator_fails_dangerous_pattern(self):
        """Test validator applies the ValidatorAgent security checks."""
        orchestrator = System2Orchestrator()
        code = "def run(expr):\n    return eval(expr)\n"

        assert orchestrator._validator_agent(code, expected_elements=["run"]) is False


class TestTaskDerivedRequirements:
    """Tests for deriving validation requirements from the planned task."""

    def test_expected_elements_uses_target_leaf(self):
        tasks = {"target_entity": "billing.InvoiceService.compute_total"}

        assert System2Orchestrator._expected_elements_for_task(tasks) == [
            "compute_total"
        ]

    def test_expected_elements_handles_double_colon(self):
        tasks = {"target_entity": "Auth::verify_token"}

        assert System2Orchestrator._expected_elements_for_task(tasks) == [
            "verify_token"
        ]

    @pytest.mark.parametrize(
        "tasks",
        [None, {}, {"target_entity": ""}, {"target_entity": "foo; drop table"}],
    )
    def test_expected_elements_empty_for_missing_or_invalid_target(self, tasks):
        assert System2Orchestrator._expected_elements_for_task(tasks) == []

    @pytest.mark.asyncio
    async def test_execute_request_passes_task_derived_elements(self):
        """validate_code receives the planner's target, not hardcoded strings."""
        orchestrator = System2Orchestrator()
        orchestrator._planner_agent = AsyncMock(
            return_value={
                "target_entity": "UserRepo.find_by_email",
                "task_description": "Parameterize the SQL query",
            }
        )
        orchestrator.coder_agent = AsyncMock()
        orchestrator.coder_agent.generate_code.return_value = {"code": "x = 1"}
        orchestrator.reviewer_agent = AsyncMock()
        orchestrator.reviewer_agent.review_code.return_value = {"status": "PASS"}
        orchestrator.validator_agent = AsyncMock()
        orchestrator.validator_agent.validate_code.return_value = {"valid": True}

        await orchestrator.execute_request("Fix SQL injection")

        kwargs = orchestrator.validator_agent.validate_code.call_args.kwargs
        assert kwargs["expected_elements"] == ["find_by_email"]


class TestRemediationFromReviewerFindings:
    """Remediation guidance must come from the reviewer's actual output."""

    def test_remediation_text_includes_reviewer_details(self):
        review = {
            "status": "FAIL_SECURITY",
            "finding": "SQL built by string concatenation",
            "severity": "Critical",
            "vulnerabilities": [
                {"type": "SQL_INJECTION", "line": 12, "description": "f-string SQL"}
            ],
            "recommendations": ["Use parameterized queries"],
        }

        text = System2Orchestrator._build_remediation_text(review)

        assert "[Critical] SQL built by string concatenation" in text
        assert "(line 12): f-string SQL" in text
        assert "Fix: Use parameterized queries" in text
        assert "SHA256" not in text

    def test_remediation_text_without_details_is_explicit(self):
        text = System2Orchestrator._build_remediation_text(
            {"status": "FAIL_LLM_UNAVAILABLE"}
        )

        assert "FAIL_LLM_UNAVAILABLE" in text
        assert "without details" in text

    @pytest.mark.asyncio
    async def test_execute_request_feeds_reviewer_finding_to_coder(self):
        """The second coding attempt sees the reviewer's real finding."""
        orchestrator = System2Orchestrator()
        orchestrator.coder_agent = AsyncMock()
        orchestrator.coder_agent.generate_code.return_value = {
            "code": "def calculate_checksum(d):\n    return d\n"
        }
        orchestrator.reviewer_agent = AsyncMock()
        orchestrator.reviewer_agent.review_code.side_effect = [
            {
                "status": "FAIL_SECURITY",
                "finding": "Hardcoded API token",
                "severity": "Critical",
                "recommendations": ["Load the token from Secrets Manager"],
            },
            {"status": "PASS", "finding": "ok"},
        ]
        orchestrator.validator_agent = AsyncMock()
        orchestrator.validator_agent.validate_code.return_value = {"valid": True}

        await orchestrator.execute_request("Fix security")

        second_context = orchestrator.coder_agent.generate_code.call_args_list[1].args[
            0
        ]
        remediation = second_context.get_items_by_source(ContextSource.REMEDIATION)
        assert len(remediation) == 1
        assert "Hardcoded API token" in remediation[0].content
        assert "Secrets Manager" in remediation[0].content
        assert "SHA256" not in remediation[0].content


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


class _StubGraph:
    """Graph backend stub returning preconfigured results."""

    def __init__(self, results):
        self._results = results

    def run_gremlin_query(self, source_entity):
        return list(self._results)


class _StubVectors:
    """Vector backend stub returning preconfigured results."""

    def __init__(self, results):
        self._results = results

    def run_knn_search(self, query):
        return list(self._results)


class TestContextConfidenceFromBackendScores:
    """Context confidences use backend scores when available."""

    def test_unscored_results_fall_back_to_defaults(self):
        from src.agents.agent_orchestrator import (
            DEFAULT_GRAPH_CONFIDENCE,
            DEFAULT_VECTOR_CONFIDENCE,
        )

        service = ContextRetrievalService(
            _StubGraph(["Structural: A calls B"]),
            _StubVectors(["Code doc for A"]),
        )

        context = service.get_hybrid_context("A", "q")

        graph_item = context.get_items_by_source(ContextSource.GRAPH_STRUCTURAL)[0]
        vector_item = context.get_items_by_source(ContextSource.VECTOR_SEMANTIC)[0]
        assert graph_item.confidence == DEFAULT_GRAPH_CONFIDENCE
        assert vector_item.confidence == DEFAULT_VECTOR_CONFIDENCE
        assert graph_item.metadata["confidence_source"] == "default"
        assert vector_item.metadata["confidence_source"] == "default"

    def test_opensearch_style_scores_are_used(self):
        service = ContextRetrievalService(
            _StubGraph([("Structural: A calls B", 0.42)]),
            _StubVectors(
                [
                    {"text": "Security Policy: no MD5", "_score": 0.73},
                    {"text": "Doc for A", "score": 0.61},
                    {"content": "Doc for C", "similarity": 0.55},
                ]
            ),
        )

        context = service.get_hybrid_context("A", "q")

        graph_item = context.get_items_by_source(ContextSource.GRAPH_STRUCTURAL)[0]
        policy = context.get_items_by_source(ContextSource.SECURITY_POLICY)[0]
        vectors = context.get_items_by_source(ContextSource.VECTOR_SEMANTIC)
        assert graph_item.confidence == pytest.approx(0.42)
        assert graph_item.content == "Structural: A calls B"
        assert policy.confidence == pytest.approx(0.73)
        assert policy.content == "Security Policy: no MD5"
        assert sorted(v.confidence for v in vectors) == pytest.approx([0.55, 0.61])
        assert all(i.metadata["confidence_source"] == "backend" for i in context.items)

    def test_out_of_range_scores_are_clamped(self):
        service = ContextRetrievalService(
            _StubGraph([]),
            _StubVectors(
                [{"text": "inner product hit", "score": 7.5}, ("negative", -0.2)]
            ),
        )

        context = service.get_hybrid_context("A", "q")

        by_content = {i.content: i.confidence for i in context.items}
        assert by_content == {"inner product hit": 1.0, "negative": 0.0}

    @pytest.mark.parametrize("bad_score", [None, "high", float("nan"), True])
    def test_unusable_scores_fall_back(self, bad_score):
        from src.agents.agent_orchestrator import DEFAULT_VECTOR_CONFIDENCE

        service = ContextRetrievalService(
            _StubGraph([]),
            _StubVectors([{"text": "doc", "score": bad_score}]),
        )

        context = service.get_hybrid_context("A", "q")

        assert context.items[0].confidence == DEFAULT_VECTOR_CONFIDENCE
        assert context.items[0].metadata["confidence_source"] == "default"


def _hitl_ready_orchestrator(
    hitl_service, titan_memory=None, sandbox_orchestrator=None
):
    """Build an orchestrator whose standard workflow succeeds."""
    orchestrator = System2Orchestrator(
        hitl_approval_service=hitl_service,
        titan_memory=titan_memory,
        sandbox_orchestrator=sandbox_orchestrator,
    )
    orchestrator.coder_agent = AsyncMock()
    orchestrator.coder_agent.generate_code.return_value = {
        "code": "import hashlib\n\ndef calculate_checksum(d):\n"
        "    return hashlib.sha256(d).hexdigest()\n"
    }
    orchestrator.reviewer_agent = AsyncMock()
    orchestrator.reviewer_agent.review_code.return_value = {
        "status": "PASS",
        "finding": "No issues",
        "reflection_confidence": 0.87,
    }
    # Real ValidatorAgent, built by System2Orchestrator.__init__ with the
    # injected sandbox_orchestrator (None -> sandbox step skips honestly).
    return orchestrator


class _FakeSandboxOrchestrator:
    """Sandbox orchestrator double reporting a finished task."""

    def __init__(self, all_tests_passed):
        self.all_tests_passed = all_tests_passed
        self.created = []
        self.destroyed = []

    async def create_sandbox(self, sandbox_id, patch_id, test_suite, **kwargs):
        self.created.append((sandbox_id, patch_id, test_suite))

    async def get_sandbox_status(self, sandbox_id):
        return {
            "status": "completed",
            "all_tests_passed": self.all_tests_passed,
            "test_results": [
                {"name": "t1", "status": "passed"},
                {
                    "name": "t2",
                    "status": "passed" if self.all_tests_passed else "failed",
                },
            ],
        }

    async def destroy_sandbox(self, sandbox_id):
        self.destroyed.append(sandbox_id)


class TestSandboxOrchestratorInjection:
    """System2Orchestrator wires an injected sandbox orchestrator to the validator."""

    def test_constructor_passes_sandbox_to_validator(self):
        fake = _FakeSandboxOrchestrator(True)
        orchestrator = System2Orchestrator(sandbox_orchestrator=fake)
        assert orchestrator.validator_agent.sandbox_orchestrator is fake

    def test_default_has_no_sandbox(self):
        assert System2Orchestrator().validator_agent.sandbox_orchestrator is None

    def test_factory_passes_explicit_sandbox(self):
        from src.agents.agent_orchestrator import create_system2_orchestrator

        fake = _FakeSandboxOrchestrator(True)
        orchestrator = create_system2_orchestrator(
            use_mock=True,
            enable_a2as=False,
            sandbox_orchestrator=fake,
        )
        assert orchestrator.validator_agent.sandbox_orchestrator is fake

    def test_factory_unconfigured_env_yields_none(self, monkeypatch):
        from src.agents.agent_orchestrator import create_system2_orchestrator

        monkeypatch.delenv("SANDBOX_ENABLED", raising=False)
        orchestrator = create_system2_orchestrator(use_mock=True, enable_a2as=False)
        assert orchestrator.validator_agent.sandbox_orchestrator is None

    def test_factory_builds_from_env(self, monkeypatch):
        from src.agents.agent_orchestrator import create_system2_orchestrator

        fake = _FakeSandboxOrchestrator(True)
        monkeypatch.setenv("SANDBOX_ENABLED", "true")
        monkeypatch.delenv("USE_MOCK_SERVICES", raising=False)
        with patch(
            "src.services.sandbox_network_service.FargateSandboxOrchestrator",
            return_value=fake,
        ):
            orchestrator = create_system2_orchestrator(use_mock=True, enable_a2as=False)
        assert orchestrator.validator_agent.sandbox_orchestrator is fake

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "tests_pass,expected_status", [(True, "PASSED"), (False, "FAILED")]
    )
    async def test_hitl_runs_injected_sandbox(self, tests_pass, expected_status):
        from unittest.mock import MagicMock

        hitl = MagicMock()
        hitl.create_approval_request.return_value = MagicMock(approval_id="a")
        fake = _FakeSandboxOrchestrator(tests_pass)
        orchestrator = _hitl_ready_orchestrator(hitl, sandbox_orchestrator=fake)

        result = await orchestrator.execute_request_with_hitl(
            user_prompt="Fix checksum", vulnerability_id="VULN-9"
        )

        assert len(fake.created) == 1
        assert fake.destroyed == [fake.created[0][0]]
        assert result["sandbox_results"]["status"] == expected_status
        assert result["sandbox_results"]["runtime_tested"] is True


class TestHITLSandboxIntegration:
    """Sandbox phase of execute_request_with_hitl uses the real validator path."""

    @pytest.mark.asyncio
    async def test_no_sandbox_configured_records_honest_skip(self):
        from unittest.mock import MagicMock

        hitl = MagicMock()
        hitl.create_approval_request.return_value = MagicMock(
            approval_id="appr-1",
            patch_id="patch-1",
            created_at="t0",
            expires_at="t1",
            patch_diff="diff",
        )
        orchestrator = _hitl_ready_orchestrator(hitl)

        result = await orchestrator.execute_request_with_hitl(
            user_prompt="Fix checksum", vulnerability_id="VULN-9"
        )

        sandbox = hitl.create_approval_request.call_args.kwargs["sandbox_results"]
        assert sandbox["status"] == "SKIPPED"
        assert sandbox["sandbox_valid"] is None
        assert sandbox["runtime_tested"] is False
        assert sandbox["sandbox_id"] is None
        assert "not configured" in sandbox["skip_reason"]
        # No fabricated test counts that would read as "0 failed"
        assert "tests_passed" not in sandbox
        assert "tests_failed" not in sandbox
        assert result["status"] == "AWAITING_APPROVAL"
        assert result["sandbox_results"] is sandbox
        metadata = hitl.create_approval_request.call_args.kwargs["metadata"]
        assert metadata["sandbox_status"] == "SKIPPED"

    @pytest.mark.asyncio
    async def test_sandbox_pass_passes_real_results(self):
        from unittest.mock import MagicMock

        hitl = MagicMock()
        hitl.create_approval_request.return_value = MagicMock(approval_id="a")
        orchestrator = _hitl_ready_orchestrator(hitl)
        orchestrator.validator_agent.validate_in_sandbox = AsyncMock(
            return_value={
                "sandbox_valid": True,
                "sandbox_id": "sandbox-patch-x-abc123",
                "test_results": [
                    {"name": "t1", "status": "passed"},
                    {"name": "t2", "status": "passed"},
                    {"name": "t3", "passed": True},
                ],
                "execution_time": 12.5,
                "sandbox_status": "completed",
                "errors": [],
            }
        )

        await orchestrator.execute_request_with_hitl(
            user_prompt="Fix checksum", vulnerability_id="VULN-9"
        )

        call = orchestrator.validator_agent.validate_in_sandbox.call_args.kwargs
        assert call["code"] == orchestrator.final_code
        sandbox = hitl.create_approval_request.call_args.kwargs["sandbox_results"]
        assert sandbox["status"] == "PASSED"
        assert sandbox["sandbox_id"] == "sandbox-patch-x-abc123"
        assert sandbox["tests_passed"] == 3
        assert sandbox["tests_failed"] == 0
        assert sandbox["runtime_tested"] is True
        # patch_id is shared between the sandbox run and the approval request
        assert (
            call["patch_id"]
            == hitl.create_approval_request.call_args.kwargs["patch_id"]
        )

    @pytest.mark.asyncio
    async def test_sandbox_failure_blocks_approval(self):
        from unittest.mock import MagicMock

        hitl = MagicMock()
        orchestrator = _hitl_ready_orchestrator(hitl)
        orchestrator.validator_agent.validate_in_sandbox = AsyncMock(
            return_value={
                "sandbox_valid": False,
                "sandbox_id": "sandbox-p-1",
                "test_results": [
                    {"name": "t1", "status": "passed"},
                    {"name": "t2", "status": "failed"},
                ],
                "execution_time": 3,
                "sandbox_status": "completed",
                "errors": [],
            }
        )

        result = await orchestrator.execute_request_with_hitl(
            user_prompt="Fix checksum", vulnerability_id="VULN-9"
        )

        assert result["hitl_status"] == "SANDBOX_FAILED"
        assert result["sandbox_results"]["tests_failed"] == 1
        hitl.create_approval_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_sandbox_exception_fails_closed(self):
        from unittest.mock import MagicMock

        hitl = MagicMock()
        orchestrator = _hitl_ready_orchestrator(hitl)
        orchestrator.validator_agent.validate_in_sandbox = AsyncMock(
            side_effect=RuntimeError("ECS unavailable")
        )

        result = await orchestrator.execute_request_with_hitl(
            user_prompt="Fix checksum", vulnerability_id="VULN-9"
        )

        assert result["hitl_status"] == "SANDBOX_FAILED"
        assert "ECS unavailable" in result["sandbox_results"]["errors"][0]
        hitl.create_approval_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_mock_sandbox_ids_in_source_path(self):
        """The HITL path never invents '-mock' sandbox identifiers."""
        from unittest.mock import MagicMock

        hitl = MagicMock()
        hitl.create_approval_request.return_value = MagicMock(approval_id="a")
        orchestrator = _hitl_ready_orchestrator(hitl)

        result = await orchestrator.execute_request_with_hitl(
            user_prompt="Fix checksum", vulnerability_id="VULN-9"
        )

        sandbox_id = result["sandbox_results"]["sandbox_id"]
        assert sandbox_id is None or "mock" not in sandbox_id

    @pytest.mark.asyncio
    async def test_hitl_defers_memory_until_human_decision(self):
        from unittest.mock import MagicMock

        titan = AsyncMock()
        titan.load_cognitive_context.return_value = {}
        hitl = MagicMock()
        hitl.create_approval_request.return_value = MagicMock(approval_id="a")
        orchestrator = _hitl_ready_orchestrator(hitl, titan_memory=titan)

        await orchestrator.execute_request_with_hitl(
            user_prompt="Fix checksum", vulnerability_id="VULN-9"
        )

        titan.record_episode.assert_not_called()
        metadata = hitl.create_approval_request.call_args.kwargs["metadata"]
        assert metadata["decision_confidence"] == pytest.approx(0.87)
        assert metadata["decision_confidence_source"] == "reviewer_reflection"
        assert metadata["review_finding"] == "No issues"


class TestHumanDecisionMemory:
    """process_approval_decision records the human outcome in memory."""

    @staticmethod
    def _hitl_with_request(metadata=None):
        from unittest.mock import MagicMock

        hitl = MagicMock()
        hitl.approve_request.return_value = True
        hitl.reject_request.return_value = True
        hitl.get_request.return_value = MagicMock(
            vulnerability_id="VULN-7",
            metadata=(
                metadata
                if metadata is not None
                else {
                    "user_prompt": "Fix weak hash in checksum",
                    "target_entity": "DataProcessor.calculate_checksum",
                    "review_finding": "Code is secure",
                    "decision_confidence": 0.91,
                    "decision_confidence_source": "reviewer_reflection",
                }
            ),
            sandbox_test_results={"status": "SKIPPED"},
        )
        return hitl

    @pytest.mark.asyncio
    async def test_approval_records_success_episode(self):
        from src.services.cognitive_memory_service import OutcomeStatus

        titan = AsyncMock()
        orchestrator = System2Orchestrator(
            hitl_approval_service=self._hitl_with_request(), titan_memory=titan
        )

        result = await orchestrator.process_approval_decision(
            approval_id="appr-1", decision="APPROVE", reviewer_id="alice"
        )

        assert result["status"] == "APPROVED"
        kwargs = titan.record_episode.call_args.kwargs
        assert kwargs["outcome"] == OutcomeStatus.SUCCESS
        assert kwargs["task_description"] == "Fix weak hash in checksum"
        assert kwargs["confidence_at_decision"] == pytest.approx(0.91)
        assert "alice" in kwargs["reasoning"]
        assert "sandbox: SKIPPED" in kwargs["reasoning"]
        assert kwargs["error_message"] is None

    @pytest.mark.asyncio
    async def test_rejection_records_failure_episode_with_reason(self):
        from src.services.cognitive_memory_service import OutcomeStatus

        titan = AsyncMock()
        orchestrator = System2Orchestrator(
            hitl_approval_service=self._hitl_with_request(), titan_memory=titan
        )

        result = await orchestrator.process_approval_decision(
            approval_id="appr-1",
            decision="REJECT",
            reviewer_id="bob",
            reason="Breaks backward compatibility of stored checksums",
        )

        assert result["status"] == "REJECTED"
        kwargs = titan.record_episode.call_args.kwargs
        assert kwargs["outcome"] == OutcomeStatus.FAILURE
        assert "Breaks backward compatibility" in kwargs["outcome_details"]
        assert "Breaks backward compatibility" in kwargs["error_message"]

    @pytest.mark.asyncio
    async def test_missing_confidence_uses_documented_default(self):
        from src.agents.agent_orchestrator import DEFAULT_DECISION_CONFIDENCE

        titan = AsyncMock()
        orchestrator = System2Orchestrator(
            hitl_approval_service=self._hitl_with_request(metadata={}),
            titan_memory=titan,
        )

        await orchestrator.process_approval_decision(
            approval_id="appr-2", decision="APPROVE", reviewer_id="alice"
        )

        kwargs = titan.record_episode.call_args.kwargs
        assert kwargs["confidence_at_decision"] == DEFAULT_DECISION_CONFIDENCE
        assert "default_prior" in kwargs["reasoning"]
        assert kwargs["task_description"] == "Security patch for VULN-7"

    @pytest.mark.asyncio
    async def test_memory_failure_does_not_break_approval(self, caplog):
        import logging

        titan = AsyncMock()
        titan.record_episode.side_effect = RuntimeError("DynamoDB throttled")
        orchestrator = System2Orchestrator(
            hitl_approval_service=self._hitl_with_request(), titan_memory=titan
        )

        with caplog.at_level(logging.WARNING):
            result = await orchestrator.process_approval_decision(
                approval_id="appr-3",
                decision="REJECT",
                reviewer_id="bob",
                reason="Wrong fix",
            )

        assert result["status"] == "REJECTED"
        titan.record_episode.assert_called_once()
        assert "non-blocking" in caplog.text

    @pytest.mark.asyncio
    async def test_failed_decision_records_nothing(self):
        titan = AsyncMock()
        hitl = self._hitl_with_request()
        hitl.approve_request.return_value = False
        orchestrator = System2Orchestrator(
            hitl_approval_service=hitl, titan_memory=titan
        )

        result = await orchestrator.process_approval_decision(
            approval_id="appr-4", decision="APPROVE", reviewer_id="alice"
        )

        assert result["status"] == "ERROR"
        titan.record_episode.assert_not_called()

    @pytest.mark.asyncio
    async def test_autonomous_learn_uses_reflection_confidence(self):
        titan = AsyncMock()
        titan.load_cognitive_context.return_value = {}
        orchestrator = _hitl_ready_orchestrator(None, titan_memory=titan)

        result = await orchestrator.execute_request("Fix checksum")

        assert result["status"] == "SUCCESS"
        kwargs = titan.record_episode.call_args.kwargs
        assert kwargs["confidence_at_decision"] == pytest.approx(0.87)
        assert "reviewer_reflection" in kwargs["reasoning"]


class TestScoredVectorSearchPreference:
    """ContextRetrievalService prefers run_knn_search_scored when available."""

    def test_scored_method_used_for_confidence(self):
        class _ScoredVectors:
            def run_knn_search(self, query):
                return ["plain"]

            def run_knn_search_scored(self, query):
                return [{"text": "Code Context (a.py): x", "score": 0.83}]

        service = ContextRetrievalService(_StubGraph([]), _ScoredVectors())
        context = service.get_hybrid_context("A", "q")

        assert len(context.items) == 1
        assert context.items[0].confidence == pytest.approx(0.83)
        assert context.items[0].metadata["confidence_source"] == "backend"
