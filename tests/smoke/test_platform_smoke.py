"""
Project Aura - Simplified Smoke Tests (Production Validation)

These tests validate that critical platform components are functional.
Run before EVERY deployment - must complete in < 30 seconds.

Usage:
    pytest tests/smoke/test_platform_smoke.py -v
"""

from pathlib import Path

import pytest

# Register custom markers
pytest.mark.smoke = pytest.mark.smoke


@pytest.mark.smoke
class TestCoreComponents:
    """Validate core platform components are functional."""

    def test_ast_parser_can_be_imported_and_initialized(self):
        """CRITICAL: AST Parser can be imported and initialized."""
        from src.agents.ast_parser_agent import ASTParserAgent

        parser = ASTParserAgent()
        assert parser is not None
        assert hasattr(parser, "parse_file")  # Actual method name
        assert hasattr(parser, "supported_extensions")

    def test_ast_parser_can_parse_python_code(self):
        """CRITICAL: AST Parser can parse simple Python code."""
        import tempfile

        from src.agents.ast_parser_agent import ASTParserAgent

        parser = ASTParserAgent()

        # Create temporary file with code
        test_code = """
def hello():
    return "world"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(test_code)
            test_file = Path(f.name)

        try:
            result = parser.parse_file(test_file)
            assert result is not None
            assert isinstance(result, list)  # Returns list of CodeEntity objects
            assert len(result) > 0
        finally:
            test_file.unlink()  # Cleanup

    def test_context_objects_can_be_created(self):
        """CRITICAL: Context objects can be instantiated."""
        from src.agents.context_objects import ContextItem, ContextSource, HybridContext

        # Create context item
        item = ContextItem(
            content="Test content",
            source=ContextSource.GRAPH_STRUCTURAL,
            confidence=0.95,
            metadata={"test": "data"},
        )

        assert item.content == "Test content"
        assert item.confidence == 0.95

        # Create hybrid context (requires items, query, target_entity)
        context = HybridContext(
            items=[item], query="test query", target_entity="test_entity"
        )

        assert len(context.items) == 1  # Access items directly, no get_items_count()

    def test_neptune_service_mock_mode(self):
        """CRITICAL: Neptune service works in MOCK mode."""
        from src.services.neptune_graph_service import NeptuneGraphService, NeptuneMode

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        # Add entity using correct API
        entity_id = service.add_code_entity(
            name="test_function",
            entity_type="function",
            file_path="test.py",
            line_number=1,
            metadata={},
        )

        assert entity_id is not None

        # Verify entity exists using search_by_name (get_code_entity doesn't exist)
        results = service.search_by_name("test_function")
        assert len(results) > 0
        assert results[0]["name"] == "test_function"

    def test_monitoring_service_can_be_created(self):
        """CRITICAL: Monitoring service can be instantiated."""
        from src.agents.monitoring_service import MonitorAgent

        monitor = MonitorAgent()
        assert monitor is not None

        # Get execution report (actual method is finalize_report)
        report = monitor.finalize_report()
        assert report is not None
        assert isinstance(report, dict)

    def test_observability_service_tracks_operations(self):
        """CRITICAL: Observability service tracks operations."""
        from src.services.observability_service import ObservabilityService

        monitor = ObservabilityService()

        # Track a simple operation
        with monitor.track_latency("test.operation"):
            pass  # Simulated operation

        # Verify latency was recorded
        avg_latency = monitor.get_average_latency("test.operation")
        assert avg_latency is not None
        assert avg_latency >= 0

    def test_observability_service_reports_health(self):
        """CRITICAL: Observability service reports health status."""
        from src.services.observability_service import (
            ObservabilityService,
            ServiceHealth,
        )

        monitor = ObservabilityService()

        # Record some successful operations
        monitor.record_success("test.operation")
        monitor.record_success("test.operation")

        health = monitor.get_service_health()
        assert health in [
            ServiceHealth.HEALTHY,
            ServiceHealth.DEGRADED,
            ServiceHealth.UNHEALTHY,
        ]

        # Get full report
        report = monitor.get_health_report()
        assert report is not None
        assert "status" in report
        assert "golden_signals" in report


@pytest.mark.smoke
@pytest.mark.performance
class TestPerformance:
    """Validate performance SLAs are met."""

    def test_ast_parsing_is_fast(self):
        """CRITICAL: AST parsing completes quickly."""
        import tempfile
        import time

        from src.agents.ast_parser_agent import ASTParserAgent

        parser = ASTParserAgent()

        # Generate 50 lines of code
        code = "def test():\n    pass\n" * 25

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            test_file = Path(f.name)

        try:
            start = time.time()
            result = parser.parse_file(test_file)
            elapsed = time.time() - start

            assert result is not None
            assert elapsed < 2.0, f"Parsing took {elapsed:.2f}s (should be < 2s)"
        finally:
            test_file.unlink()  # Cleanup

    def test_neptune_mock_queries_are_fast(self):
        """CRITICAL: Neptune MOCK queries are fast."""
        import time

        from src.services.neptune_graph_service import NeptuneGraphService, NeptuneMode

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        # Add some entities
        for i in range(5):
            service.add_code_entity(
                name=f"func{i}",
                entity_type="function",
                file_path=f"test{i}.py",
                line_number=1,
            )

        # Query should be fast
        start = time.time()
        results = service.search_by_name("func")
        elapsed = time.time() - start

        assert len(results) > 0
        assert elapsed < 0.5, f"Query took {elapsed*1000:.0f}ms (should be < 500ms)"


@pytest.mark.smoke
class TestEndToEndWorkflow:
    """Validate end-to-end critical path."""

    def test_complete_code_analysis_workflow(self):
        """
        CRITICAL: Complete workflow from code to analysis.

        This validates multiple components working together.
        """
        import tempfile

        from src.agents.ast_parser_agent import ASTParserAgent
        from src.agents.monitoring_service import MonitorAgent
        from src.services.neptune_graph_service import NeptuneGraphService, NeptuneMode

        # Setup
        parser = ASTParserAgent()
        monitor = MonitorAgent()
        neptune = NeptuneGraphService(mode=NeptuneMode.MOCK)

        # Sample code with security issue
        code = """
import hashlib

def hash_password(pwd):
    return hashlib.md5(pwd.encode()).hexdigest()
"""

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            test_file = Path(f.name)

        try:
            # Step 1: Parse code (returns list of CodeEntity objects)
            parse_result = parser.parse_file(test_file)
            assert parse_result is not None
            assert isinstance(parse_result, list)

            # Step 2: Store entities in graph
            for entity in parse_result:
                if entity.entity_type == "function":
                    entity_id = neptune.add_code_entity(
                        name=entity.name,
                        entity_type="function",
                        file_path="auth.py",
                        line_number=entity.line_number,
                    )
                    assert entity_id is not None

            # Step 3: Verify we can query
            results = neptune.search_by_name("hash_password")
            assert len(results) > 0

            # Step 4: Get monitoring report (actual method is finalize_report)
            report = monitor.finalize_report()
            assert report is not None

            # SUCCESS: End-to-end workflow completed
        finally:
            test_file.unlink()  # Cleanup


if __name__ == "__main__":
    # Run smoke tests
    pytest.main([__file__, "-v", "-m", "smoke"])
