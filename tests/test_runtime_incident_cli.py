"""
Project Aura - Runtime Incident CLI Tests

Tests for the RuntimeIncidentAgent CLI wrapper that runs
incident investigations in ECS Fargate tasks.
"""

import importlib
import json
import os
import sys
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

# =============================================================================
# Mock Classes
# =============================================================================


@dataclass
class MockInvestigation:
    """Mock investigation result."""

    incident_id: str = "inc-123"
    confidence_score: float = 85.0
    rca_hypothesis: str = "Root cause identified"
    hitl_status: str = "approved"


# =============================================================================
# Fixtures for Module Isolation
# =============================================================================


@pytest.fixture(scope="module")
def cli_module():
    """
    Fixture that provides a fresh import of the CLI module with mocked dependencies.

    This ensures proper test isolation by:
    1. Saving original sys.modules state
    2. Clearing any cached CLI module
    3. Injecting mock modules
    4. Importing CLI with mocks in place
    5. Restoring sys.modules after all tests in this file complete
    """
    # Modules to mock
    modules_to_mock = [
        "src.agents.runtime_incident_agent",
        "src.services.bedrock_llm_service",
    ]
    cli_module_name = "src.agents.runtime_incident_cli"

    # Save original state
    original_modules = {m: sys.modules.get(m) for m in modules_to_mock}
    original_cli = sys.modules.get(cli_module_name)

    # Create mock agent
    mock_agent = MagicMock()
    mock_agent.investigate = AsyncMock(return_value=MockInvestigation())

    # Create mock LLM service
    mock_llm_service = MagicMock()

    # Create mock modules
    mock_agent_module = MagicMock()
    mock_agent_module.RuntimeIncidentAgent = MagicMock(return_value=mock_agent)

    mock_llm_module = MagicMock()
    mock_llm_module.BedrockLLMService = MagicMock(return_value=mock_llm_service)
    mock_llm_module.BedrockMode = MagicMock()
    mock_llm_module.BedrockMode.AWS = "aws"

    # Clear CLI module from cache to ensure fresh import
    if cli_module_name in sys.modules:
        del sys.modules[cli_module_name]

    # Inject mocks into sys.modules
    sys.modules["src.agents.runtime_incident_agent"] = mock_agent_module
    sys.modules["src.services.bedrock_llm_service"] = mock_llm_module

    # Import CLI with mocks in place
    cli = importlib.import_module(cli_module_name)

    # Yield the module and mocks for tests
    yield {
        "cli": cli,
        "main": cli.main,
        "run_investigation": cli.run_investigation,
        "mock_agent": mock_agent,
        "mock_agent_module": mock_agent_module,
        "mock_llm_module": mock_llm_module,
        "mock_llm_service": mock_llm_service,
    }

    # Cleanup: Remove CLI module from cache
    if cli_module_name in sys.modules:
        del sys.modules[cli_module_name]

    # Restore original modules
    for mod_name, original in original_modules.items():
        if original is not None:
            sys.modules[mod_name] = original
        else:
            sys.modules.pop(mod_name, None)

    # Restore original CLI if it existed
    if original_cli is not None:
        sys.modules[cli_module_name] = original_cli


@pytest.fixture
def reset_mocks(cli_module):
    """Reset mocks before each test."""
    cli_module["mock_agent"].investigate.reset_mock()
    cli_module["mock_agent"].investigate.return_value = MockInvestigation()
    cli_module["mock_agent"].investigate.side_effect = None
    cli_module["mock_agent_module"].RuntimeIncidentAgent.reset_mock()
    cli_module["mock_agent_module"].RuntimeIncidentAgent.return_value = cli_module[
        "mock_agent"
    ]
    cli_module["mock_llm_module"].BedrockLLMService.side_effect = None
    return cli_module


# =============================================================================
# Test Classes
# =============================================================================


class TestRunInvestigation:
    """Tests for run_investigation function."""

    @pytest.mark.asyncio
    async def test_run_investigation_success(self, reset_mocks):
        """Test successful investigation run."""
        run_investigation = reset_mocks["run_investigation"]
        mock_agent = reset_mocks["mock_agent"]

        incident_event = {
            "detail": {
                "incident_id": "inc-123",
                "severity": "high",
            }
        }

        exit_code = await run_investigation(
            incident_id="inc-123",
            incident_event=incident_event,
            environment="dev",
        )

        assert exit_code == 0
        mock_agent.investigate.assert_called_once_with(incident_event)

    @pytest.mark.asyncio
    async def test_run_investigation_with_llm(self, reset_mocks):
        """Test investigation with LLM enabled."""
        run_investigation = reset_mocks["run_investigation"]

        os.environ["ENABLE_LLM"] = "true"

        incident_event = {"detail": {"incident_id": "inc-456"}}

        exit_code = await run_investigation(
            incident_id="inc-456",
            incident_event=incident_event,
            environment="dev",
        )

        assert exit_code == 0

    @pytest.mark.asyncio
    async def test_run_investigation_without_llm(self, reset_mocks):
        """Test investigation with LLM disabled."""
        run_investigation = reset_mocks["run_investigation"]

        os.environ["ENABLE_LLM"] = "false"

        incident_event = {"detail": {"incident_id": "inc-789"}}

        exit_code = await run_investigation(
            incident_id="inc-789",
            incident_event=incident_event,
            environment="dev",
        )

        assert exit_code == 0
        os.environ["ENABLE_LLM"] = "true"  # Reset

    @pytest.mark.asyncio
    async def test_run_investigation_llm_init_failure(self, reset_mocks):
        """Test investigation continues when LLM init fails."""
        run_investigation = reset_mocks["run_investigation"]
        mock_llm_module = reset_mocks["mock_llm_module"]

        os.environ["ENABLE_LLM"] = "true"
        mock_llm_module.BedrockLLMService.side_effect = Exception("LLM init failed")

        incident_event = {"detail": {"incident_id": "inc-llm-fail"}}

        # Should still succeed (LLM is optional)
        exit_code = await run_investigation(
            incident_id="inc-llm-fail",
            incident_event=incident_event,
            environment="dev",
        )

        assert exit_code == 0
        mock_llm_module.BedrockLLMService.side_effect = None

    @pytest.mark.asyncio
    async def test_run_investigation_agent_failure(self, reset_mocks):
        """Test investigation failure handling."""
        run_investigation = reset_mocks["run_investigation"]
        mock_agent = reset_mocks["mock_agent"]

        mock_agent.investigate.side_effect = Exception("Investigation failed")

        incident_event = {"detail": {"incident_id": "inc-fail"}}

        exit_code = await run_investigation(
            incident_id="inc-fail",
            incident_event=incident_event,
            environment="dev",
        )

        assert exit_code == 1
        mock_agent.investigate.side_effect = None

    @pytest.mark.asyncio
    async def test_run_investigation_different_environments(self, reset_mocks):
        """Test investigation in different environments."""
        run_investigation = reset_mocks["run_investigation"]

        for env in ["dev", "qa", "prod"]:
            incident_event = {"detail": {"incident_id": f"inc-{env}"}}

            exit_code = await run_investigation(
                incident_id=f"inc-{env}",
                incident_event=incident_event,
                environment=env,
            )

            assert exit_code == 0


class TestMainCLI:
    """Tests for main CLI entrypoint."""

    def test_main_missing_args(self, reset_mocks):
        """Test main with missing required arguments."""
        main = reset_mocks["main"]

        original_argv = sys.argv
        sys.argv = ["runtime_incident_cli.py"]

        with pytest.raises(SystemExit) as exc_info:
            main()

        # argparse exits with code 2 for missing arguments
        assert exc_info.value.code == 2
        sys.argv = original_argv

    def test_main_file_not_found(self, reset_mocks, tmp_path):
        """Test main with non-existent incident file."""
        main = reset_mocks["main"]

        original_argv = sys.argv
        sys.argv = [
            "runtime_incident_cli.py",
            "--incident-id",
            "inc-123",
            "--incident-file",
            str(tmp_path / "nonexistent.json"),
        ]

        exit_code = main()

        assert exit_code == 2
        sys.argv = original_argv

    def test_main_invalid_json(self, reset_mocks, tmp_path):
        """Test main with invalid JSON file."""
        main = reset_mocks["main"]

        # Create file with invalid JSON
        incident_file = tmp_path / "invalid.json"
        incident_file.write_text("not valid json {}")

        original_argv = sys.argv
        sys.argv = [
            "runtime_incident_cli.py",
            "--incident-id",
            "inc-123",
            "--incident-file",
            str(incident_file),
        ]

        exit_code = main()

        assert exit_code == 2
        sys.argv = original_argv

    def test_main_success(self, reset_mocks, tmp_path):
        """Test main with valid arguments."""
        main = reset_mocks["main"]

        # Create valid incident file
        incident_file = tmp_path / "incident.json"
        incident_data = {
            "detail": {
                "incident_id": "inc-123",
                "severity": "high",
            }
        }
        incident_file.write_text(json.dumps(incident_data))

        original_argv = sys.argv
        sys.argv = [
            "runtime_incident_cli.py",
            "--incident-id",
            "inc-123",
            "--incident-file",
            str(incident_file),
            "--environment",
            "dev",
        ]

        exit_code = main()

        assert exit_code == 0
        sys.argv = original_argv

    def test_main_environment_choices(self, reset_mocks, tmp_path):
        """Test main with different environment choices."""
        main = reset_mocks["main"]

        incident_file = tmp_path / "incident.json"
        incident_file.write_text(json.dumps({"detail": {}}))

        for env in ["dev", "qa", "prod"]:
            original_argv = sys.argv
            sys.argv = [
                "runtime_incident_cli.py",
                "--incident-id",
                f"inc-{env}",
                "--incident-file",
                str(incident_file),
                "--environment",
                env,
            ]

            exit_code = main()

            assert exit_code == 0
            sys.argv = original_argv

    def test_main_log_level(self, reset_mocks, tmp_path):
        """Test main with different log levels."""
        main = reset_mocks["main"]

        incident_file = tmp_path / "incident.json"
        incident_file.write_text(json.dumps({"detail": {}}))

        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            original_argv = sys.argv
            sys.argv = [
                "runtime_incident_cli.py",
                "--incident-id",
                "inc-log",
                "--incident-file",
                str(incident_file),
                "--log-level",
                level,
            ]

            exit_code = main()

            assert exit_code == 0
            sys.argv = original_argv

    def test_main_sets_environment_variables(self, reset_mocks, tmp_path):
        """Test that main sets environment variables correctly."""
        main = reset_mocks["main"]

        incident_file = tmp_path / "incident.json"
        incident_file.write_text(json.dumps({"detail": {}}))

        original_argv = sys.argv
        original_env = os.environ.get("ENVIRONMENT")
        original_aura_env = os.environ.get("AURA_ENV")

        sys.argv = [
            "runtime_incident_cli.py",
            "--incident-id",
            "inc-env",
            "--incident-file",
            str(incident_file),
            "--environment",
            "qa",
        ]

        main()

        assert os.environ.get("ENVIRONMENT") == "qa"
        assert os.environ.get("AURA_ENV") == "qa"

        # Restore
        sys.argv = original_argv
        if original_env:
            os.environ["ENVIRONMENT"] = original_env
        if original_aura_env:
            os.environ["AURA_ENV"] = original_aura_env


class TestInvestigationResult:
    """Tests for investigation result handling."""

    @pytest.mark.asyncio
    async def test_investigation_result_logging(self, reset_mocks):
        """Test that investigation results are logged."""
        run_investigation = reset_mocks["run_investigation"]
        mock_agent = reset_mocks["mock_agent"]

        mock_result = MockInvestigation(
            incident_id="inc-log-test",
            confidence_score=92.5,
            rca_hypothesis="Memory leak in service X",
            hitl_status="pending",
        )
        mock_agent.investigate.return_value = mock_result

        exit_code = await run_investigation(
            incident_id="inc-log-test",
            incident_event={"detail": {}},
            environment="dev",
        )

        assert exit_code == 0

    @pytest.mark.asyncio
    async def test_investigation_low_confidence(self, reset_mocks):
        """Test investigation with low confidence score."""
        run_investigation = reset_mocks["run_investigation"]
        mock_agent = reset_mocks["mock_agent"]

        mock_result = MockInvestigation(
            confidence_score=35.0,
            rca_hypothesis="Uncertain cause",
        )
        mock_agent.investigate.return_value = mock_result

        exit_code = await run_investigation(
            incident_id="inc-low-conf",
            incident_event={"detail": {}},
            environment="dev",
        )

        # Should still succeed even with low confidence
        assert exit_code == 0
