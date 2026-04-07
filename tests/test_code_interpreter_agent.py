"""Tests for CodeInterpreterAgent

Comprehensive tests for secure code execution agent.
"""

import asyncio
import base64
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.code_interpreter_agent import (
    CodeExecutionRequest,
    CodeExecutionResult,
    CodeInterpreterAgent,
    ExecutionStatus,
    InterpreterConfig,
    SandboxConfig,
    SupportedLanguage,
    Visualization,
    VisualizationType,
)


class TestSupportedLanguage:
    """Tests for SupportedLanguage enum."""

    def test_python_variants(self):
        """Test Python language variants."""
        assert SupportedLanguage.PYTHON.value == "python"
        assert SupportedLanguage.PYTHON311.value == "python3.11"
        assert SupportedLanguage.PYTHON312.value == "python3.12"

    def test_javascript_variants(self):
        """Test JavaScript/TypeScript variants."""
        assert SupportedLanguage.JAVASCRIPT.value == "javascript"
        assert SupportedLanguage.TYPESCRIPT.value == "typescript"

    def test_compiled_languages(self):
        """Test compiled language values."""
        assert SupportedLanguage.GO.value == "go"
        assert SupportedLanguage.RUST.value == "rust"
        assert SupportedLanguage.JAVA.value == "java"

    def test_scripting_languages(self):
        """Test scripting language values."""
        assert SupportedLanguage.RUBY.value == "ruby"
        assert SupportedLanguage.R.value == "r"
        assert SupportedLanguage.JULIA.value == "julia"
        assert SupportedLanguage.BASH.value == "bash"

    def test_sql(self):
        """Test SQL language value."""
        assert SupportedLanguage.SQL.value == "sql"

    def test_all_languages_count(self):
        """Test total number of supported languages."""
        assert len(SupportedLanguage) == 13


class TestVisualizationType:
    """Tests for VisualizationType enum."""

    def test_image_formats(self):
        """Test image format values."""
        assert VisualizationType.PNG.value == "png"
        assert VisualizationType.SVG.value == "svg"

    def test_document_formats(self):
        """Test document format values."""
        assert VisualizationType.HTML.value == "html"
        assert VisualizationType.PDF.value == "pdf"
        assert VisualizationType.JSON.value == "json"

    def test_all_types_count(self):
        """Test total number of visualization types."""
        assert len(VisualizationType) == 5


class TestExecutionStatus:
    """Tests for ExecutionStatus enum."""

    def test_pending_status(self):
        """Test pending status value."""
        assert ExecutionStatus.PENDING.value == "pending"

    def test_running_status(self):
        """Test running status value."""
        assert ExecutionStatus.RUNNING.value == "running"

    def test_success_status(self):
        """Test success status value."""
        assert ExecutionStatus.SUCCESS.value == "success"

    def test_error_status(self):
        """Test error status value."""
        assert ExecutionStatus.ERROR.value == "error"

    def test_timeout_status(self):
        """Test timeout status value."""
        assert ExecutionStatus.TIMEOUT.value == "timeout"

    def test_killed_status(self):
        """Test killed status value."""
        assert ExecutionStatus.KILLED.value == "killed"


class TestVisualization:
    """Tests for Visualization dataclass."""

    def test_basic_creation(self):
        """Test basic visualization creation."""
        viz = Visualization(
            viz_type=VisualizationType.PNG,
            content_base64="base64content",
        )
        assert viz.viz_type == VisualizationType.PNG
        assert viz.content_base64 == "base64content"
        assert viz.width is None
        assert viz.height is None
        assert viz.title is None
        assert viz.metadata == {}

    def test_full_creation(self):
        """Test full visualization creation with all fields."""
        viz = Visualization(
            viz_type=VisualizationType.SVG,
            content_base64="svgcontent",
            width=800,
            height=600,
            title="Test Chart",
            metadata={"source": "matplotlib"},
        )
        assert viz.viz_type == VisualizationType.SVG
        assert viz.width == 800
        assert viz.height == 600
        assert viz.title == "Test Chart"
        assert viz.metadata == {"source": "matplotlib"}

    def test_json_visualization(self):
        """Test JSON visualization for plotly/vega-lite."""
        data = {"x": [1, 2, 3], "y": [1, 4, 9]}
        viz = Visualization(
            viz_type=VisualizationType.JSON,
            content_base64=base64.b64encode(json.dumps(data).encode()).decode(),
            metadata={"library": "plotly"},
        )
        assert viz.viz_type == VisualizationType.JSON
        decoded = json.loads(base64.b64decode(viz.content_base64))
        assert decoded == data


class TestCodeExecutionRequest:
    """Tests for CodeExecutionRequest dataclass."""

    def test_minimal_request(self):
        """Test minimal request with defaults."""
        request = CodeExecutionRequest(
            code="print('hello')",
            language=SupportedLanguage.PYTHON,
        )
        assert request.code == "print('hello')"
        assert request.language == SupportedLanguage.PYTHON
        assert request.timeout_seconds == 60
        assert request.memory_mb == 256
        assert request.cpu_limit == 1.0
        assert request.files == {}
        assert request.packages == []
        assert request.environment == {}
        assert request.working_directory == "/workspace"
        assert request.capture_output is True
        assert request.return_files == []

    def test_full_request(self):
        """Test full request with all fields."""
        request = CodeExecutionRequest(
            code="import numpy; print(numpy.array([1,2,3]))",
            language=SupportedLanguage.PYTHON312,
            timeout_seconds=120,
            memory_mb=512,
            cpu_limit=2.0,
            files={"data.csv": b"a,b,c\n1,2,3"},
            packages=["numpy", "pandas"],
            environment={"DEBUG": "true"},
            working_directory="/app",
            capture_output=False,
            return_files=["output.txt"],
        )
        assert request.timeout_seconds == 120
        assert request.memory_mb == 512
        assert request.packages == ["numpy", "pandas"]
        assert "data.csv" in request.files

    def test_javascript_request(self):
        """Test JavaScript execution request."""
        request = CodeExecutionRequest(
            code="console.log('Hello, World!');",
            language=SupportedLanguage.JAVASCRIPT,
            timeout_seconds=30,
        )
        assert request.language == SupportedLanguage.JAVASCRIPT


class TestCodeExecutionResult:
    """Tests for CodeExecutionResult dataclass."""

    def test_success_result(self):
        """Test successful execution result."""
        result = CodeExecutionResult(
            request_id="req123",
            status=ExecutionStatus.SUCCESS,
            exit_code=0,
            stdout="Hello, World!",
            stderr="",
        )
        assert result.request_id == "req123"
        assert result.status == ExecutionStatus.SUCCESS
        assert result.exit_code == 0
        assert result.stdout == "Hello, World!"

    def test_error_result(self):
        """Test error execution result."""
        result = CodeExecutionResult(
            request_id="req456",
            status=ExecutionStatus.ERROR,
            exit_code=1,
            stdout="",
            stderr="NameError: name 'x' is not defined",
            error_message="Syntax error in code",
            error_traceback="Traceback (most recent call last):\n  ...",
        )
        assert result.status == ExecutionStatus.ERROR
        assert result.exit_code == 1
        assert "NameError" in result.stderr
        assert result.error_message == "Syntax error in code"

    def test_result_with_timing(self):
        """Test result with timing information."""
        now = datetime.now(timezone.utc)
        result = CodeExecutionResult(
            request_id="req789",
            status=ExecutionStatus.SUCCESS,
            exit_code=0,
            stdout="",
            stderr="",
            execution_time_ms=150.5,
            memory_used_mb=64.2,
            cpu_time_ms=120.0,
            started_at=now,
            completed_at=now,
        )
        assert result.execution_time_ms == 150.5
        assert result.memory_used_mb == 64.2
        assert result.cpu_time_ms == 120.0

    def test_result_with_files_and_visualizations(self):
        """Test result with output files and visualizations."""
        viz = Visualization(
            viz_type=VisualizationType.PNG,
            content_base64="png_data",
        )
        result = CodeExecutionResult(
            request_id="req_viz",
            status=ExecutionStatus.SUCCESS,
            exit_code=0,
            stdout="",
            stderr="",
            output_files={"plot.png": b"png_bytes"},
            visualizations=[viz],
        )
        assert "plot.png" in result.output_files
        assert len(result.visualizations) == 1


class TestSandboxConfig:
    """Tests for SandboxConfig dataclass."""

    def test_default_config(self):
        """Test default sandbox configuration."""
        config = SandboxConfig()
        assert config.memory_mb == 256
        assert config.cpu_cores == 1.0
        assert config.disk_mb == 1024
        assert config.network_enabled is False
        assert config.gpu_enabled is False
        assert config.timeout_seconds == 300
        assert config.max_processes == 32
        assert config.max_file_size_mb == 100

    def test_custom_config(self):
        """Test custom sandbox configuration."""
        config = SandboxConfig(
            memory_mb=1024,
            cpu_cores=4.0,
            disk_mb=4096,
            network_enabled=True,
            gpu_enabled=True,
            timeout_seconds=600,
            max_processes=64,
            max_file_size_mb=500,
        )
        assert config.memory_mb == 1024
        assert config.cpu_cores == 4.0
        assert config.network_enabled is True
        assert config.gpu_enabled is True


class TestInterpreterConfig:
    """Tests for InterpreterConfig dataclass."""

    def test_default_config(self):
        """Test default interpreter configuration."""
        config = InterpreterConfig()
        assert config.default_timeout_seconds == 60
        assert config.max_timeout_seconds == 600
        assert config.default_memory_mb == 256
        assert config.max_memory_mb == 4096
        assert config.max_output_size_bytes == 10 * 1024 * 1024
        assert config.max_file_size_bytes == 50 * 1024 * 1024
        assert config.sandbox_image == "aura/code-interpreter:latest"
        assert config.enable_package_install is True
        assert config.enable_network is False

    def test_allowed_languages_default(self):
        """Test that all languages are allowed by default."""
        config = InterpreterConfig()
        assert len(config.allowed_languages) == len(SupportedLanguage)
        assert SupportedLanguage.PYTHON in config.allowed_languages
        assert SupportedLanguage.JAVASCRIPT in config.allowed_languages

    def test_restricted_languages(self):
        """Test restricted language configuration."""
        config = InterpreterConfig(
            allowed_languages=[SupportedLanguage.PYTHON, SupportedLanguage.JAVASCRIPT]
        )
        assert len(config.allowed_languages) == 2
        assert SupportedLanguage.GO not in config.allowed_languages


class TestCodeInterpreterAgentInit:
    """Tests for CodeInterpreterAgent initialization."""

    def test_basic_init(self):
        """Test basic initialization without dependencies."""
        agent = CodeInterpreterAgent()
        assert agent.sandbox is None
        assert agent.packages is None
        assert agent.config is not None
        assert agent._execution_history == []
        assert agent._active_sandboxes == {}

    def test_init_with_config(self):
        """Test initialization with custom config."""
        config = InterpreterConfig(
            max_timeout_seconds=300,
            enable_network=True,
        )
        agent = CodeInterpreterAgent(config=config)
        assert agent.config.max_timeout_seconds == 300
        assert agent.config.enable_network is True

    def test_init_with_sandbox_client(self):
        """Test initialization with sandbox client."""
        mock_sandbox = MagicMock()
        agent = CodeInterpreterAgent(sandbox_client=mock_sandbox)
        assert agent.sandbox is mock_sandbox

    def test_init_with_package_manager(self):
        """Test initialization with package manager."""
        mock_packages = MagicMock()
        agent = CodeInterpreterAgent(package_manager=mock_packages)
        assert agent.packages is mock_packages

    def test_capability_property(self):
        """Test capability property returns correct value."""
        agent = CodeInterpreterAgent()
        assert agent.capability == "code_execution"


class TestCodeInterpreterAgentLanguageCommands:
    """Tests for language commands and extensions."""

    def test_python_command(self):
        """Test Python execution command."""
        assert (
            CodeInterpreterAgent.LANGUAGE_COMMANDS[SupportedLanguage.PYTHON]
            == "python3 {file}"
        )

    def test_python_version_commands(self):
        """Test Python version-specific commands."""
        assert (
            CodeInterpreterAgent.LANGUAGE_COMMANDS[SupportedLanguage.PYTHON311]
            == "python3.11 {file}"
        )
        assert (
            CodeInterpreterAgent.LANGUAGE_COMMANDS[SupportedLanguage.PYTHON312]
            == "python3.12 {file}"
        )

    def test_javascript_command(self):
        """Test JavaScript execution command."""
        assert (
            CodeInterpreterAgent.LANGUAGE_COMMANDS[SupportedLanguage.JAVASCRIPT]
            == "node {file}"
        )

    def test_typescript_command(self):
        """Test TypeScript execution command."""
        assert (
            CodeInterpreterAgent.LANGUAGE_COMMANDS[SupportedLanguage.TYPESCRIPT]
            == "npx ts-node {file}"
        )

    def test_go_command(self):
        """Test Go execution command."""
        assert (
            CodeInterpreterAgent.LANGUAGE_COMMANDS[SupportedLanguage.GO]
            == "go run {file}"
        )

    def test_rust_command(self):
        """Test Rust execution command."""
        assert "rustc" in CodeInterpreterAgent.LANGUAGE_COMMANDS[SupportedLanguage.RUST]

    def test_java_command(self):
        """Test Java execution command."""
        assert "javac" in CodeInterpreterAgent.LANGUAGE_COMMANDS[SupportedLanguage.JAVA]

    def test_sql_command(self):
        """Test SQL execution command."""
        assert (
            "sqlite3" in CodeInterpreterAgent.LANGUAGE_COMMANDS[SupportedLanguage.SQL]
        )


class TestCodeInterpreterAgentExtensions:
    """Tests for language file extensions."""

    def test_python_extension(self):
        """Test Python file extension."""
        assert (
            CodeInterpreterAgent.LANGUAGE_EXTENSIONS[SupportedLanguage.PYTHON] == ".py"
        )

    def test_javascript_extension(self):
        """Test JavaScript file extension."""
        assert (
            CodeInterpreterAgent.LANGUAGE_EXTENSIONS[SupportedLanguage.JAVASCRIPT]
            == ".js"
        )

    def test_typescript_extension(self):
        """Test TypeScript file extension."""
        assert (
            CodeInterpreterAgent.LANGUAGE_EXTENSIONS[SupportedLanguage.TYPESCRIPT]
            == ".ts"
        )

    def test_go_extension(self):
        """Test Go file extension."""
        assert CodeInterpreterAgent.LANGUAGE_EXTENSIONS[SupportedLanguage.GO] == ".go"

    def test_rust_extension(self):
        """Test Rust file extension."""
        assert CodeInterpreterAgent.LANGUAGE_EXTENSIONS[SupportedLanguage.RUST] == ".rs"

    def test_java_extension(self):
        """Test Java file extension."""
        assert (
            CodeInterpreterAgent.LANGUAGE_EXTENSIONS[SupportedLanguage.JAVA] == ".java"
        )


class TestCodeInterpreterAgentPackageManagers:
    """Tests for package manager commands."""

    def test_python_package_manager(self):
        """Test Python package manager."""
        assert (
            CodeInterpreterAgent.PACKAGE_MANAGERS[SupportedLanguage.PYTHON]
            == "pip install"
        )

    def test_javascript_package_manager(self):
        """Test JavaScript package manager."""
        assert (
            CodeInterpreterAgent.PACKAGE_MANAGERS[SupportedLanguage.JAVASCRIPT]
            == "npm install"
        )

    def test_go_package_manager(self):
        """Test Go package manager."""
        assert CodeInterpreterAgent.PACKAGE_MANAGERS[SupportedLanguage.GO] == "go get"

    def test_rust_package_manager(self):
        """Test Rust package manager."""
        assert (
            CodeInterpreterAgent.PACKAGE_MANAGERS[SupportedLanguage.RUST] == "cargo add"
        )

    def test_ruby_package_manager(self):
        """Test Ruby package manager."""
        assert (
            CodeInterpreterAgent.PACKAGE_MANAGERS[SupportedLanguage.RUBY]
            == "gem install"
        )


class TestCodeInterpreterAgentValidation:
    """Tests for request validation."""

    def test_validate_valid_request(self):
        """Test validation of valid request."""
        agent = CodeInterpreterAgent()
        request = CodeExecutionRequest(
            code="print('hello')",
            language=SupportedLanguage.PYTHON,
        )
        error = agent._validate_request(request)
        assert error is None

    def test_validate_empty_code(self):
        """Test validation rejects empty code."""
        agent = CodeInterpreterAgent()
        request = CodeExecutionRequest(
            code="   ",
            language=SupportedLanguage.PYTHON,
        )
        error = agent._validate_request(request)
        assert error == "Empty code"

    def test_validate_disallowed_language(self):
        """Test validation rejects disallowed language."""
        config = InterpreterConfig(allowed_languages=[SupportedLanguage.PYTHON])
        agent = CodeInterpreterAgent(config=config)
        request = CodeExecutionRequest(
            code="console.log('hello')",
            language=SupportedLanguage.JAVASCRIPT,
        )
        error = agent._validate_request(request)
        assert "Language not allowed" in error

    def test_validate_timeout_exceeds_max(self):
        """Test validation rejects excessive timeout."""
        config = InterpreterConfig(max_timeout_seconds=300)
        agent = CodeInterpreterAgent(config=config)
        request = CodeExecutionRequest(
            code="print('hello')",
            language=SupportedLanguage.PYTHON,
            timeout_seconds=600,
        )
        error = agent._validate_request(request)
        assert "Timeout exceeds maximum" in error

    def test_validate_memory_exceeds_max(self):
        """Test validation rejects excessive memory."""
        config = InterpreterConfig(max_memory_mb=1024)
        agent = CodeInterpreterAgent(config=config)
        request = CodeExecutionRequest(
            code="print('hello')",
            language=SupportedLanguage.PYTHON,
            memory_mb=2048,
        )
        error = agent._validate_request(request)
        assert "Memory exceeds maximum" in error

    def test_validate_code_size_exceeds_max(self):
        """Test validation rejects oversized code."""
        config = InterpreterConfig(max_file_size_bytes=100)
        agent = CodeInterpreterAgent(config=config)
        request = CodeExecutionRequest(
            code="x" * 200,
            language=SupportedLanguage.PYTHON,
        )
        error = agent._validate_request(request)
        assert "Code exceeds maximum size" in error

    def test_validate_file_size_exceeds_max(self):
        """Test validation rejects oversized input file."""
        config = InterpreterConfig(max_file_size_bytes=100)
        agent = CodeInterpreterAgent(config=config)
        request = CodeExecutionRequest(
            code="print('hello')",
            language=SupportedLanguage.PYTHON,
            files={"large.txt": b"x" * 200},
        )
        error = agent._validate_request(request)
        assert "exceeds maximum size" in error


class TestCodeInterpreterAgentExecution:
    """Tests for code execution."""

    @pytest.mark.asyncio
    async def test_execute_mock_mode(self):
        """Test execution in mock mode (no sandbox client)."""
        agent = CodeInterpreterAgent()
        request = CodeExecutionRequest(
            code="print('Hello, World!')",
            language=SupportedLanguage.PYTHON,
        )
        result = await agent.execute(request)

        assert result.status == ExecutionStatus.SUCCESS
        assert result.exit_code == 0
        assert "[Mock execution output]" in result.stdout
        assert result.request_id is not None
        assert result.started_at is not None
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_execute_validation_error(self):
        """Test execution with validation error."""
        agent = CodeInterpreterAgent()
        request = CodeExecutionRequest(
            code="",
            language=SupportedLanguage.PYTHON,
        )
        result = await agent.execute(request)

        assert result.status == ExecutionStatus.ERROR
        assert "Empty code" in result.error_message

    @pytest.mark.asyncio
    async def test_execute_with_sandbox_client(self):
        """Test execution with sandbox client."""
        mock_sandbox = AsyncMock()
        mock_sandbox.create_sandbox.return_value = "sandbox123"
        mock_sandbox.execute.return_value = {
            "exit_code": 0,
            "stdout": "Hello, World!",
            "stderr": "",
            "memory_mb": 64,
            "cpu_ms": 50,
        }

        agent = CodeInterpreterAgent(sandbox_client=mock_sandbox)
        request = CodeExecutionRequest(
            code="print('Hello, World!')",
            language=SupportedLanguage.PYTHON,
        )
        result = await agent.execute(request)

        assert result.status == ExecutionStatus.SUCCESS
        assert result.stdout == "Hello, World!"
        mock_sandbox.create_sandbox.assert_called_once()
        mock_sandbox.execute.assert_called_once()
        mock_sandbox.destroy_sandbox.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_packages(self):
        """Test execution with package installation."""
        mock_sandbox = AsyncMock()
        mock_sandbox.create_sandbox.return_value = "sandbox123"
        mock_sandbox.execute.return_value = {
            "exit_code": 0,
            "stdout": "[1 2 3]",
            "stderr": "",
        }

        mock_packages = AsyncMock()
        mock_packages.install.return_value = True

        agent = CodeInterpreterAgent(
            sandbox_client=mock_sandbox, package_manager=mock_packages
        )
        request = CodeExecutionRequest(
            code="import numpy; print(numpy.array([1,2,3]))",
            language=SupportedLanguage.PYTHON,
            packages=["numpy"],
        )
        result = await agent.execute(request)

        assert result.status == ExecutionStatus.SUCCESS
        mock_packages.install.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_input_files(self):
        """Test execution with input files."""
        mock_sandbox = AsyncMock()
        mock_sandbox.create_sandbox.return_value = "sandbox123"
        mock_sandbox.execute.return_value = {
            "exit_code": 0,
            "stdout": "a,b,c",
            "stderr": "",
        }

        agent = CodeInterpreterAgent(sandbox_client=mock_sandbox)
        request = CodeExecutionRequest(
            code="with open('data.csv') as f: print(f.read())",
            language=SupportedLanguage.PYTHON,
            files={"data.csv": b"a,b,c\n1,2,3"},
        )
        result = await agent.execute(request)

        assert result.status == ExecutionStatus.SUCCESS
        # Verify write_file was called for input file
        calls = mock_sandbox.write_file.call_args_list
        assert len(calls) >= 1

    @pytest.mark.asyncio
    async def test_execute_with_output_files(self):
        """Test execution with output file collection."""
        mock_sandbox = AsyncMock()
        mock_sandbox.create_sandbox.return_value = "sandbox123"
        mock_sandbox.execute.return_value = {
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
        }
        mock_sandbox.read_file.return_value = b"output content"

        agent = CodeInterpreterAgent(sandbox_client=mock_sandbox)
        request = CodeExecutionRequest(
            code="with open('output.txt', 'w') as f: f.write('output content')",
            language=SupportedLanguage.PYTHON,
            return_files=["output.txt"],
        )
        result = await agent.execute(request)

        assert result.status == ExecutionStatus.SUCCESS
        assert "output.txt" in result.output_files

    @pytest.mark.asyncio
    async def test_execute_error_result(self):
        """Test execution with error result."""
        mock_sandbox = AsyncMock()
        mock_sandbox.create_sandbox.return_value = "sandbox123"
        mock_sandbox.execute.return_value = {
            "exit_code": 1,
            "stdout": "",
            "stderr": "NameError: name 'undefined_var' is not defined",
        }

        agent = CodeInterpreterAgent(sandbox_client=mock_sandbox)
        request = CodeExecutionRequest(
            code="print(undefined_var)",
            language=SupportedLanguage.PYTHON,
        )
        result = await agent.execute(request)

        assert result.status == ExecutionStatus.ERROR
        assert result.exit_code == 1
        assert "NameError" in result.stderr

    @pytest.mark.asyncio
    async def test_execute_timeout(self):
        """Test execution timeout handling."""
        mock_sandbox = AsyncMock()
        mock_sandbox.create_sandbox.return_value = "sandbox123"
        mock_sandbox.execute.side_effect = asyncio.TimeoutError()

        agent = CodeInterpreterAgent(sandbox_client=mock_sandbox)
        request = CodeExecutionRequest(
            code="import time; time.sleep(1000)",
            language=SupportedLanguage.PYTHON,
            timeout_seconds=1,
        )
        result = await agent.execute(request)

        assert result.status == ExecutionStatus.TIMEOUT
        assert "timed out" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_execute_exception(self):
        """Test execution exception handling."""
        mock_sandbox = AsyncMock()
        mock_sandbox.create_sandbox.side_effect = Exception("Sandbox creation failed")

        agent = CodeInterpreterAgent(sandbox_client=mock_sandbox)
        request = CodeExecutionRequest(
            code="print('hello')",
            language=SupportedLanguage.PYTHON,
        )
        result = await agent.execute(request)

        assert result.status == ExecutionStatus.ERROR
        assert "Sandbox creation failed" in result.error_message


class TestCodeInterpreterAgentInteractive:
    """Tests for interactive session execution."""

    @pytest.mark.asyncio
    async def test_execute_interactive_new_session(self):
        """Test interactive execution with new session."""
        mock_sandbox = AsyncMock()
        mock_sandbox.create_sandbox.return_value = "sandbox_interactive"
        mock_sandbox.execute.return_value = {
            "exit_code": 0,
            "stdout": "3",
            "stderr": "",
        }

        agent = CodeInterpreterAgent(sandbox_client=mock_sandbox)
        result = await agent.execute_interactive(
            session_id="session1",
            code="print(1+2)",
            language=SupportedLanguage.PYTHON,
        )

        assert result.status == ExecutionStatus.SUCCESS
        assert "session1" in agent._active_sandboxes

    @pytest.mark.asyncio
    async def test_execute_interactive_existing_session(self):
        """Test interactive execution with existing session."""
        mock_sandbox = AsyncMock()
        mock_sandbox.execute.return_value = {
            "exit_code": 0,
            "stdout": "6",
            "stderr": "",
        }

        agent = CodeInterpreterAgent(sandbox_client=mock_sandbox)
        agent._active_sandboxes["session1"] = "sandbox_existing"

        result = await agent.execute_interactive(
            session_id="session1",
            code="print(2*3)",
        )

        assert result.status == ExecutionStatus.SUCCESS
        # Should not create new sandbox
        mock_sandbox.create_sandbox.assert_not_called()

    @pytest.mark.asyncio
    async def test_close_interactive_session(self):
        """Test closing interactive session."""
        mock_sandbox = AsyncMock()

        agent = CodeInterpreterAgent(sandbox_client=mock_sandbox)
        agent._active_sandboxes["session1"] = "sandbox_to_close"

        await agent.close_interactive_session("session1")

        assert "session1" not in agent._active_sandboxes
        mock_sandbox.destroy_sandbox.assert_called_once_with("sandbox_to_close")

    @pytest.mark.asyncio
    async def test_close_nonexistent_session(self):
        """Test closing non-existent session is no-op."""
        agent = CodeInterpreterAgent()
        await agent.close_interactive_session("nonexistent")
        # Should not raise


class TestCodeInterpreterAgentPackages:
    """Tests for package installation."""

    @pytest.mark.asyncio
    async def test_install_packages_enabled(self):
        """Test package installation when enabled."""
        mock_sandbox = AsyncMock()
        mock_sandbox.create_sandbox.return_value = "sandbox123"

        mock_packages = AsyncMock()
        mock_packages.install.return_value = True

        agent = CodeInterpreterAgent(
            sandbox_client=mock_sandbox, package_manager=mock_packages
        )
        result = await agent.install_packages(
            language=SupportedLanguage.PYTHON,
            packages=["numpy", "pandas"],
        )

        assert result is True
        mock_packages.install.assert_called_once()
        mock_sandbox.destroy_sandbox.assert_called_once()

    @pytest.mark.asyncio
    async def test_install_packages_disabled(self):
        """Test package installation when disabled."""
        config = InterpreterConfig(enable_package_install=False)
        agent = CodeInterpreterAgent(config=config)

        result = await agent.install_packages(
            language=SupportedLanguage.PYTHON,
            packages=["numpy"],
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_install_packages_existing_sandbox(self):
        """Test package installation in existing sandbox."""
        mock_packages = AsyncMock()
        mock_packages.install.return_value = True

        agent = CodeInterpreterAgent(package_manager=mock_packages)

        result = await agent.install_packages(
            language=SupportedLanguage.PYTHON,
            packages=["numpy"],
            sandbox_id="existing_sandbox",
        )

        assert result is True


class TestCodeInterpreterAgentVisualization:
    """Tests for visualization generation."""

    @pytest.mark.asyncio
    async def test_create_visualization_python(self):
        """Test visualization creation with Python."""
        mock_sandbox = AsyncMock()
        mock_sandbox.create_sandbox.return_value = "sandbox_viz"
        mock_sandbox.execute.return_value = {
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
        }
        mock_sandbox.read_file.return_value = b"fake_png_data"

        agent = CodeInterpreterAgent(sandbox_client=mock_sandbox)

        viz = await agent.create_visualization(
            code="plt.plot(data['x'], data['y'])",
            data={"x": [1, 2, 3], "y": [1, 4, 9]},
            output_format=VisualizationType.PNG,
            language=SupportedLanguage.PYTHON,
        )

        assert viz.viz_type == VisualizationType.PNG
        assert viz.content_base64 == base64.b64encode(b"fake_png_data").decode()

    @pytest.mark.asyncio
    async def test_create_visualization_from_output_files(self):
        """Test visualization extraction from output files."""
        agent = CodeInterpreterAgent()

        # Test _extract_visualizations directly
        output_files = {
            "/output/chart.png": b"png_data",
            "/output/diagram.svg": b"<svg></svg>",
            "/output/report.html": b"<html></html>",
            "/output/data.json": b'{"key": "value"}',
            "/output/doc.pdf": b"pdf_data",
            "/output/plain.txt": b"text_data",
        }

        visualizations = await agent._extract_visualizations("sandbox123", output_files)

        assert len(visualizations) == 5  # txt is not a visualization
        viz_types = [v.viz_type for v in visualizations]
        assert VisualizationType.PNG in viz_types
        assert VisualizationType.SVG in viz_types
        assert VisualizationType.HTML in viz_types
        assert VisualizationType.JSON in viz_types
        assert VisualizationType.PDF in viz_types


class TestCodeInterpreterAgentDataInjection:
    """Tests for data injection code generation."""

    def test_generate_data_injection_python(self):
        """Test Python data injection."""
        agent = CodeInterpreterAgent()
        data = {"x": [1, 2, 3], "name": "test"}

        code = agent._generate_data_injection(data, SupportedLanguage.PYTHON)

        assert "import json" in code
        assert "data = json.loads" in code
        assert '"x"' in code or "'x'" in code

    def test_generate_data_injection_python311(self):
        """Test Python 3.11 data injection."""
        agent = CodeInterpreterAgent()
        code = agent._generate_data_injection({"a": 1}, SupportedLanguage.PYTHON311)
        assert "import json" in code

    def test_generate_data_injection_javascript(self):
        """Test JavaScript data injection."""
        agent = CodeInterpreterAgent()
        data = {"items": ["a", "b"]}

        code = agent._generate_data_injection(data, SupportedLanguage.JAVASCRIPT)

        assert "const data = " in code

    def test_generate_data_injection_typescript(self):
        """Test TypeScript data injection."""
        agent = CodeInterpreterAgent()
        code = agent._generate_data_injection(
            {"key": "val"}, SupportedLanguage.TYPESCRIPT
        )
        assert "const data = " in code

    def test_generate_data_injection_r(self):
        """Test R data injection."""
        agent = CodeInterpreterAgent()
        code = agent._generate_data_injection({"v": [1, 2]}, SupportedLanguage.R)
        assert "jsonlite" in code

    def test_generate_data_injection_unsupported(self):
        """Test data injection for unsupported language returns empty."""
        agent = CodeInterpreterAgent()
        code = agent._generate_data_injection({"x": 1}, SupportedLanguage.GO)
        assert code == ""


class TestCodeInterpreterAgentSaveCode:
    """Tests for save code generation."""

    def test_generate_save_code_python(self):
        """Test Python save code."""
        agent = CodeInterpreterAgent()

        code = agent._generate_save_code(
            "/output/plot.png", VisualizationType.PNG, SupportedLanguage.PYTHON
        )

        assert "os.makedirs" in code
        assert "plt.savefig" in code
        assert "/output/plot.png" in code

    def test_generate_save_code_python311(self):
        """Test Python 3.11 save code."""
        agent = CodeInterpreterAgent()
        code = agent._generate_save_code(
            "/out/chart.svg", VisualizationType.SVG, SupportedLanguage.PYTHON311
        )
        assert "plt.savefig" in code

    def test_generate_save_code_unsupported(self):
        """Test save code for unsupported language returns empty."""
        agent = CodeInterpreterAgent()
        code = agent._generate_save_code(
            "/output/plot.png", VisualizationType.PNG, SupportedLanguage.JAVASCRIPT
        )
        assert code == ""


class TestCodeInterpreterAgentKillExecution:
    """Tests for kill execution functionality."""

    @pytest.mark.asyncio
    async def test_kill_active_execution(self):
        """Test killing active execution."""
        mock_sandbox = AsyncMock()

        agent = CodeInterpreterAgent(sandbox_client=mock_sandbox)
        agent._active_sandboxes["req123"] = "sandbox_to_kill"

        result = await agent.kill_execution("req123")

        assert result is True
        assert "req123" not in agent._active_sandboxes
        mock_sandbox.destroy_sandbox.assert_called_once_with("sandbox_to_kill")

    @pytest.mark.asyncio
    async def test_kill_nonexistent_execution(self):
        """Test killing non-existent execution."""
        agent = CodeInterpreterAgent()

        result = await agent.kill_execution("nonexistent")

        assert result is False


class TestCodeInterpreterAgentStats:
    """Tests for service statistics."""

    def test_get_supported_languages(self):
        """Test getting supported languages list."""
        agent = CodeInterpreterAgent()
        languages = agent.get_supported_languages()

        assert len(languages) == len(SupportedLanguage)
        python_info = next(lang for lang in languages if lang["language"] == "python")
        assert python_info["extension"] == ".py"
        assert python_info["enabled"] is True

    def test_get_supported_languages_restricted(self):
        """Test getting supported languages with restrictions."""
        config = InterpreterConfig(allowed_languages=[SupportedLanguage.PYTHON])
        agent = CodeInterpreterAgent(config=config)
        languages = agent.get_supported_languages()

        python_info = next(lang for lang in languages if lang["language"] == "python")
        assert python_info["enabled"] is True

        js_info = next(lang for lang in languages if lang["language"] == "javascript")
        assert js_info["enabled"] is False

    def test_get_service_stats_initial(self):
        """Test getting service stats initially."""
        agent = CodeInterpreterAgent()
        stats = agent.get_service_stats()

        assert stats["active_sandboxes"] == 0
        assert stats["executions_completed"] == 0
        assert "python" in stats["allowed_languages"]
        assert stats["package_install_enabled"] is True
        assert stats["network_enabled"] is False

    def test_get_service_stats_with_active_sandboxes(self):
        """Test getting service stats with active sandboxes."""
        agent = CodeInterpreterAgent()
        agent._active_sandboxes = {"req1": "sb1", "req2": "sb2"}

        stats = agent.get_service_stats()
        assert stats["active_sandboxes"] == 2


class TestCodeInterpreterAgentCreateSandbox:
    """Tests for sandbox creation."""

    @pytest.mark.asyncio
    async def test_create_sandbox_with_client(self):
        """Test sandbox creation with client."""
        mock_sandbox = AsyncMock()
        mock_sandbox.create_sandbox.return_value = "new_sandbox_id"

        agent = CodeInterpreterAgent(sandbox_client=mock_sandbox)
        request = CodeExecutionRequest(
            code="print('hello')",
            language=SupportedLanguage.PYTHON,
            memory_mb=512,
            cpu_limit=2.0,
            timeout_seconds=120,
        )

        sandbox_id = await agent._create_sandbox(request)

        assert sandbox_id == "new_sandbox_id"
        mock_sandbox.create_sandbox.assert_called_once()
        call_args = mock_sandbox.create_sandbox.call_args[0][0]
        assert call_args["memory_mb"] == 512
        assert call_args["cpu_limit"] == 2.0
        assert call_args["timeout"] == 120

    @pytest.mark.asyncio
    async def test_create_sandbox_mock_mode(self):
        """Test sandbox creation in mock mode."""
        agent = CodeInterpreterAgent()
        request = CodeExecutionRequest(
            code="print('hello')",
            language=SupportedLanguage.PYTHON,
        )

        sandbox_id = await agent._create_sandbox(request)

        assert sandbox_id is not None
        assert len(sandbox_id) > 0


class TestCodeInterpreterAgentWriteCodeFile:
    """Tests for code file writing."""

    @pytest.mark.asyncio
    async def test_write_code_file_python(self):
        """Test writing Python code file."""
        mock_sandbox = AsyncMock()

        agent = CodeInterpreterAgent(sandbox_client=mock_sandbox)
        request = CodeExecutionRequest(
            code="print('hello')",
            language=SupportedLanguage.PYTHON,
            working_directory="/app",
        )

        code_file = await agent._write_code_file("sandbox123", request)

        assert code_file == "/app/code.py"
        mock_sandbox.write_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_code_file_javascript(self):
        """Test writing JavaScript code file."""
        mock_sandbox = AsyncMock()

        agent = CodeInterpreterAgent(sandbox_client=mock_sandbox)
        request = CodeExecutionRequest(
            code="console.log('hello');",
            language=SupportedLanguage.JAVASCRIPT,
        )

        code_file = await agent._write_code_file("sandbox123", request)

        assert code_file.endswith(".js")


class TestCodeInterpreterAgentCleanup:
    """Tests for sandbox cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_sandbox_success(self):
        """Test successful sandbox cleanup."""
        mock_sandbox = AsyncMock()

        agent = CodeInterpreterAgent(sandbox_client=mock_sandbox)
        await agent._cleanup_sandbox("sandbox123")

        mock_sandbox.destroy_sandbox.assert_called_once_with("sandbox123")

    @pytest.mark.asyncio
    async def test_cleanup_sandbox_error_handled(self):
        """Test sandbox cleanup error is handled gracefully."""
        mock_sandbox = AsyncMock()
        mock_sandbox.destroy_sandbox.side_effect = Exception("Cleanup failed")

        agent = CodeInterpreterAgent(sandbox_client=mock_sandbox)
        # Should not raise
        await agent._cleanup_sandbox("sandbox123")

    @pytest.mark.asyncio
    async def test_cleanup_sandbox_no_client(self):
        """Test sandbox cleanup without client is no-op."""
        agent = CodeInterpreterAgent()
        # Should not raise
        await agent._cleanup_sandbox("sandbox123")
