"""Code Interpreter Agent for Secure Code Execution

Implements ADR-037 Phase 1.7: Code Interpreter Agent

Provides secure multi-language code execution for data analysis,
visualization, and general computation using sandboxed environments.

Key Features:
- Multi-language support (Python, JavaScript, Go, Rust, Java)
- Secure sandbox execution (Firecracker/gVisor)
- File I/O within sandbox
- Visualization output (charts, graphs)
- Package installation support
"""

import asyncio
import base64
import json
import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)


class SupportedLanguage(Enum):
    """Supported programming languages."""

    PYTHON = "python"
    PYTHON311 = "python3.11"
    PYTHON312 = "python3.12"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    RUBY = "ruby"
    R = "r"
    JULIA = "julia"
    SQL = "sql"
    BASH = "bash"


class VisualizationType(Enum):
    """Types of visualization outputs."""

    PNG = "png"
    SVG = "svg"
    HTML = "html"
    PDF = "pdf"
    JSON = "json"  # For plotly, vega-lite


class ExecutionStatus(Enum):
    """Execution status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    KILLED = "killed"


class SandboxClient(Protocol):
    """Protocol for sandbox execution client."""

    async def create_sandbox(self, config: dict) -> str:
        """Create sandbox environment."""
        ...

    async def execute(self, sandbox_id: str, command: str, timeout: int) -> dict:
        """Execute command in sandbox."""
        ...

    async def write_file(self, sandbox_id: str, path: str, content: bytes) -> None:
        """Write file to sandbox."""
        ...

    async def read_file(self, sandbox_id: str, path: str) -> bytes:
        """Read file from sandbox."""
        ...

    async def destroy_sandbox(self, sandbox_id: str) -> None:
        """Destroy sandbox."""
        ...


class PackageManager(Protocol):
    """Protocol for package management."""

    async def install(
        self, sandbox_id: str, language: str, packages: list[str]
    ) -> bool:
        """Install packages."""
        ...

    async def list_installed(self, sandbox_id: str, language: str) -> list[str]:
        """List installed packages."""
        ...


@dataclass
class Visualization:
    """Visualization output."""

    viz_type: VisualizationType
    content_base64: str
    width: Optional[int] = None
    height: Optional[int] = None
    title: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CodeExecutionRequest:
    """Request to execute code."""

    code: str
    language: SupportedLanguage
    timeout_seconds: int = 60
    memory_mb: int = 256
    cpu_limit: float = 1.0  # CPU cores
    files: dict[str, bytes] = field(default_factory=dict)  # Input files
    packages: list[str] = field(default_factory=list)  # Packages to install
    environment: dict[str, str] = field(default_factory=dict)
    working_directory: str = "/workspace"
    capture_output: bool = True
    return_files: list[str] = field(default_factory=list)  # Files to return


@dataclass
class CodeExecutionResult:
    """Result of code execution."""

    request_id: str
    status: ExecutionStatus
    exit_code: int
    stdout: str
    stderr: str
    return_value: Optional[Any] = None
    output_files: dict[str, bytes] = field(default_factory=dict)
    visualizations: list[Visualization] = field(default_factory=list)
    execution_time_ms: float = 0.0
    memory_used_mb: float = 0.0
    cpu_time_ms: float = 0.0
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class SandboxConfig:
    """Sandbox configuration."""

    memory_mb: int = 256
    cpu_cores: float = 1.0
    disk_mb: int = 1024
    network_enabled: bool = False
    gpu_enabled: bool = False
    timeout_seconds: int = 300
    max_processes: int = 32
    max_file_size_mb: int = 100


@dataclass
class InterpreterConfig:
    """Code interpreter configuration."""

    default_timeout_seconds: int = 60
    max_timeout_seconds: int = 600
    default_memory_mb: int = 256
    max_memory_mb: int = 4096
    max_output_size_bytes: int = 10 * 1024 * 1024  # 10MB
    max_file_size_bytes: int = 50 * 1024 * 1024  # 50MB
    allowed_languages: list[SupportedLanguage] = field(
        default_factory=lambda: list(SupportedLanguage)
    )
    sandbox_image: str = "aura/code-interpreter:latest"
    enable_package_install: bool = True
    enable_network: bool = False


class CodeInterpreterAgent:
    """Secure multi-language code execution agent.

    Implements AWS AgentCore Code Interpreter parity:
    - Multi-language support
    - Firecracker/gVisor sandbox isolation
    - File I/O and visualization output
    - Package management

    Security Features:
    - Network isolation by default
    - Resource limits (CPU, memory, disk)
    - Process limits
    - File size limits
    - Timeout enforcement

    Usage:
        agent = CodeInterpreterAgent(sandbox_client, package_manager)

        result = await agent.execute(CodeExecutionRequest(
            code="print('Hello, World!')",
            language=SupportedLanguage.PYTHON,
        ))

        # With visualization
        result = await agent.execute(CodeExecutionRequest(
            code='''
            import matplotlib.pyplot as plt
            plt.plot([1, 2, 3], [1, 4, 9])
            plt.savefig('/output/plot.png')
            ''',
            language=SupportedLanguage.PYTHON,
            packages=["matplotlib"],
            return_files=["/output/plot.png"],
        ))
    """

    # Language-specific execution commands
    LANGUAGE_COMMANDS = {
        SupportedLanguage.PYTHON: "python3 {file}",
        SupportedLanguage.PYTHON311: "python3.11 {file}",
        SupportedLanguage.PYTHON312: "python3.12 {file}",
        SupportedLanguage.JAVASCRIPT: "node {file}",
        SupportedLanguage.TYPESCRIPT: "npx ts-node {file}",
        SupportedLanguage.GO: "go run {file}",
        SupportedLanguage.RUST: "rustc {file} -o /tmp/a.out && /tmp/a.out",
        SupportedLanguage.JAVA: "javac {file} && java -cp /tmp Main",
        SupportedLanguage.RUBY: "ruby {file}",
        SupportedLanguage.R: "Rscript {file}",
        SupportedLanguage.JULIA: "julia {file}",
        SupportedLanguage.SQL: "sqlite3 :memory: < {file}",
        SupportedLanguage.BASH: "bash {file}",
    }

    # Language file extensions
    LANGUAGE_EXTENSIONS = {
        SupportedLanguage.PYTHON: ".py",
        SupportedLanguage.PYTHON311: ".py",
        SupportedLanguage.PYTHON312: ".py",
        SupportedLanguage.JAVASCRIPT: ".js",
        SupportedLanguage.TYPESCRIPT: ".ts",
        SupportedLanguage.GO: ".go",
        SupportedLanguage.RUST: ".rs",
        SupportedLanguage.JAVA: ".java",
        SupportedLanguage.RUBY: ".rb",
        SupportedLanguage.R: ".r",
        SupportedLanguage.JULIA: ".jl",
        SupportedLanguage.SQL: ".sql",
        SupportedLanguage.BASH: ".sh",
    }

    # Package managers by language
    PACKAGE_MANAGERS = {
        SupportedLanguage.PYTHON: "pip install",
        SupportedLanguage.PYTHON311: "pip install",
        SupportedLanguage.PYTHON312: "pip install",
        SupportedLanguage.JAVASCRIPT: "npm install",
        SupportedLanguage.TYPESCRIPT: "npm install",
        SupportedLanguage.GO: "go get",
        SupportedLanguage.RUST: "cargo add",
        SupportedLanguage.RUBY: "gem install",
        SupportedLanguage.R: "Rscript -e 'install.packages(c({packages}), repos=\"https://cran.r-project.org\")'",
        SupportedLanguage.JULIA: "julia -e 'using Pkg; Pkg.add([{packages}])'",
    }

    def __init__(
        self,
        sandbox_client: Optional[SandboxClient] = None,
        package_manager: Optional[PackageManager] = None,
        config: Optional[InterpreterConfig] = None,
    ):
        """Initialize code interpreter agent.

        Args:
            sandbox_client: Client for sandbox execution
            package_manager: Package manager for installing dependencies
            config: Interpreter configuration
        """
        self.sandbox = sandbox_client
        self.packages = package_manager
        self.config = config or InterpreterConfig()
        self._execution_history: list[CodeExecutionResult] = []
        self._active_sandboxes: dict[str, str] = {}  # request_id -> sandbox_id

    @property
    def capability(self) -> str:
        """Agent capability identifier."""
        return "code_execution"

    async def execute(
        self,
        request: CodeExecutionRequest,
    ) -> CodeExecutionResult:
        """Execute code in secure sandbox.

        Args:
            request: Code execution request

        Returns:
            Execution result
        """
        request_id = secrets.token_urlsafe(16)
        started_at = datetime.now(timezone.utc)

        # Validate request
        validation_error = self._validate_request(request)
        if validation_error:
            return CodeExecutionResult(
                request_id=request_id,
                status=ExecutionStatus.ERROR,
                exit_code=-1,
                stdout="",
                stderr="",
                error_message=validation_error,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
            )

        try:
            # Create sandbox
            sandbox_id = await self._create_sandbox(request)
            self._active_sandboxes[request_id] = sandbox_id

            # Install packages if needed
            if request.packages:
                await self._install_packages(
                    sandbox_id, request.language, request.packages
                )

            # Write input files
            for path, content in request.files.items():
                await self._write_file(sandbox_id, path, content)

            # Write code file
            code_file = await self._write_code_file(sandbox_id, request)

            # Execute code
            result = await self._execute_code(
                sandbox_id, request, code_file, started_at, request_id
            )

            # Collect output files
            if request.return_files:
                result.output_files = await self._collect_output_files(
                    sandbox_id, request.return_files
                )

            # Extract visualizations
            result.visualizations = await self._extract_visualizations(
                sandbox_id, result.output_files
            )

            return result

        except asyncio.TimeoutError:
            return CodeExecutionResult(
                request_id=request_id,
                status=ExecutionStatus.TIMEOUT,
                exit_code=-1,
                stdout="",
                stderr="",
                error_message=f"Execution timed out after {request.timeout_seconds}s",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
            )

        except Exception as e:
            logger.exception(f"Code execution failed: {e}")
            return CodeExecutionResult(
                request_id=request_id,
                status=ExecutionStatus.ERROR,
                exit_code=-1,
                stdout="",
                stderr="",
                error_message=str(e),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
            )

        finally:
            # Cleanup sandbox
            if request_id in self._active_sandboxes:
                await self._cleanup_sandbox(self._active_sandboxes[request_id])
                del self._active_sandboxes[request_id]

    async def execute_interactive(
        self,
        session_id: str,
        code: str,
        language: SupportedLanguage = SupportedLanguage.PYTHON,
    ) -> CodeExecutionResult:
        """Execute code in persistent interactive session.

        Args:
            session_id: Persistent session identifier
            code: Code to execute
            language: Programming language

        Returns:
            Execution result
        """
        # For interactive sessions, maintain sandbox across calls
        if session_id not in self._active_sandboxes:
            sandbox_id = await self._create_sandbox(
                CodeExecutionRequest(code="", language=language)
            )
            self._active_sandboxes[session_id] = sandbox_id

        request = CodeExecutionRequest(code=code, language=language)
        sandbox_id = self._active_sandboxes[session_id]

        code_file = await self._write_code_file(sandbox_id, request)

        return await self._execute_code(
            sandbox_id,
            request,
            code_file,
            datetime.now(timezone.utc),
            secrets.token_urlsafe(16),
        )

    async def close_interactive_session(self, session_id: str) -> None:
        """Close interactive session.

        Args:
            session_id: Session to close
        """
        if session_id in self._active_sandboxes:
            await self._cleanup_sandbox(self._active_sandboxes[session_id])
            del self._active_sandboxes[session_id]

    async def install_packages(
        self,
        language: SupportedLanguage,
        packages: list[str],
        sandbox_id: Optional[str] = None,
    ) -> bool:
        """Install packages in sandbox environment.

        Args:
            language: Target language
            packages: Packages to install
            sandbox_id: Optional existing sandbox

        Returns:
            True if installation successful
        """
        if not self.config.enable_package_install:
            logger.warning("Package installation is disabled")
            return False

        should_cleanup = False
        if not sandbox_id:
            sandbox_id = await self._create_sandbox(
                CodeExecutionRequest(code="", language=language)
            )
            should_cleanup = True

        try:
            return await self._install_packages(sandbox_id, language, packages)
        finally:
            if should_cleanup:
                await self._cleanup_sandbox(sandbox_id)

    async def create_visualization(
        self,
        code: str,
        data: dict[str, Any],
        output_format: VisualizationType = VisualizationType.PNG,
        language: SupportedLanguage = SupportedLanguage.PYTHON,
    ) -> Visualization:
        """Generate visualization from code and data.

        Args:
            code: Visualization code
            data: Data to visualize
            output_format: Output format
            language: Programming language

        Returns:
            Generated visualization
        """
        # Inject data into code
        data_code = self._generate_data_injection(data, language)
        full_code = data_code + "\n" + code

        # Add save command based on format
        output_path = f"/output/viz.{output_format.value}"
        save_code = self._generate_save_code(output_path, output_format, language)
        full_code += "\n" + save_code

        result = await self.execute(
            CodeExecutionRequest(
                code=full_code,
                language=language,
                packages=(
                    ["matplotlib", "pandas"]
                    if language == SupportedLanguage.PYTHON
                    else []
                ),
                return_files=[output_path],
            )
        )

        if result.visualizations:
            return result.visualizations[0]

        if output_path in result.output_files:
            return Visualization(
                viz_type=output_format,
                content_base64=base64.b64encode(
                    result.output_files[output_path]
                ).decode(),
            )

        raise ValueError(f"Failed to generate visualization: {result.error_message}")

    def _validate_request(self, request: CodeExecutionRequest) -> Optional[str]:
        """Validate execution request.

        Args:
            request: Request to validate

        Returns:
            Error message or None if valid
        """
        if request.language not in self.config.allowed_languages:
            return f"Language not allowed: {request.language.value}"

        if request.timeout_seconds > self.config.max_timeout_seconds:
            return f"Timeout exceeds maximum: {self.config.max_timeout_seconds}s"

        if request.memory_mb > self.config.max_memory_mb:
            return f"Memory exceeds maximum: {self.config.max_memory_mb}MB"

        if not request.code.strip():
            return "Empty code"

        # Check code size
        if len(request.code.encode()) > self.config.max_file_size_bytes:
            return f"Code exceeds maximum size: {self.config.max_file_size_bytes} bytes"

        # Check input files size
        for path, content in request.files.items():
            if len(content) > self.config.max_file_size_bytes:
                return f"File {path} exceeds maximum size"

        return None

    async def _create_sandbox(self, request: CodeExecutionRequest) -> str:
        """Create sandbox for execution.

        Args:
            request: Execution request

        Returns:
            Sandbox ID
        """
        if self.sandbox:
            return await self.sandbox.create_sandbox(
                {
                    "memory_mb": request.memory_mb,
                    "cpu_limit": request.cpu_limit,
                    "timeout": request.timeout_seconds,
                    "network": self.config.enable_network,
                    "image": self.config.sandbox_image,
                }
            )

        # Mock sandbox ID for testing
        return secrets.token_urlsafe(16)

    async def _write_file(self, sandbox_id: str, path: str, content: bytes) -> None:
        """Write file to sandbox.

        Args:
            sandbox_id: Sandbox identifier
            path: File path
            content: File content
        """
        if self.sandbox:
            await self.sandbox.write_file(sandbox_id, path, content)

    async def _write_code_file(
        self, sandbox_id: str, request: CodeExecutionRequest
    ) -> str:
        """Write code file to sandbox.

        Args:
            sandbox_id: Sandbox identifier
            request: Execution request

        Returns:
            Code file path
        """
        ext = self.LANGUAGE_EXTENSIONS.get(request.language, ".txt")
        code_file = f"{request.working_directory}/code{ext}"

        await self._write_file(sandbox_id, code_file, request.code.encode())

        return code_file

    async def _install_packages(
        self,
        sandbox_id: str,
        language: SupportedLanguage,
        packages: list[str],
    ) -> bool:
        """Install packages in sandbox.

        Args:
            sandbox_id: Sandbox identifier
            language: Programming language
            packages: Packages to install

        Returns:
            True if successful
        """
        if self.packages:
            return await self.packages.install(sandbox_id, language.value, packages)

        # Mock installation
        logger.debug(f"Would install packages: {packages}")
        return True

    async def _execute_code(
        self,
        sandbox_id: str,
        request: CodeExecutionRequest,
        code_file: str,
        started_at: datetime,
        request_id: str,
    ) -> CodeExecutionResult:
        """Execute code in sandbox.

        Args:
            sandbox_id: Sandbox identifier
            request: Execution request
            code_file: Code file path
            started_at: Execution start time
            request_id: Request identifier

        Returns:
            Execution result
        """
        command_template = self.LANGUAGE_COMMANDS.get(request.language)
        if not command_template:
            return CodeExecutionResult(
                request_id=request_id,
                status=ExecutionStatus.ERROR,
                exit_code=-1,
                stdout="",
                stderr="",
                error_message=f"Unsupported language: {request.language.value}",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
            )

        command = command_template.format(file=code_file)

        if self.sandbox:
            # nosec - sandbox.execute() is container execution, not SQL
            result = await self.sandbox.execute(
                sandbox_id, command, request.timeout_seconds
            )

            completed_at = datetime.now(timezone.utc)
            execution_time_ms = (completed_at - started_at).total_seconds() * 1000

            return CodeExecutionResult(
                request_id=request_id,
                status=(
                    ExecutionStatus.SUCCESS
                    if result.get("exit_code", 0) == 0
                    else ExecutionStatus.ERROR
                ),
                exit_code=result.get("exit_code", 0),
                stdout=result.get("stdout", ""),
                stderr=result.get("stderr", ""),
                execution_time_ms=execution_time_ms,
                memory_used_mb=result.get("memory_mb", 0),
                cpu_time_ms=result.get("cpu_ms", 0),
                started_at=started_at,
                completed_at=completed_at,
            )

        # Mock execution for testing
        return CodeExecutionResult(
            request_id=request_id,
            status=ExecutionStatus.SUCCESS,
            exit_code=0,
            stdout="[Mock execution output]",
            stderr="",
            execution_time_ms=100.0,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
        )

    async def _collect_output_files(
        self, sandbox_id: str, file_paths: list[str]
    ) -> dict[str, bytes]:
        """Collect output files from sandbox.

        Args:
            sandbox_id: Sandbox identifier
            file_paths: Files to collect

        Returns:
            File path -> content mapping
        """
        files = {}

        for path in file_paths:
            try:
                if self.sandbox:
                    content = await self.sandbox.read_file(sandbox_id, path)
                    files[path] = content
            except Exception as e:
                logger.warning(f"Failed to read output file {path}: {e}")

        return files

    async def _extract_visualizations(
        self, sandbox_id: str, output_files: dict[str, bytes]
    ) -> list[Visualization]:
        """Extract visualizations from output files.

        Args:
            sandbox_id: Sandbox identifier
            output_files: Collected output files

        Returns:
            List of visualizations
        """
        visualizations = []

        for path, content in output_files.items():
            ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""

            viz_type = None
            if ext == "png":
                viz_type = VisualizationType.PNG
            elif ext == "svg":
                viz_type = VisualizationType.SVG
            elif ext == "html":
                viz_type = VisualizationType.HTML
            elif ext == "pdf":
                viz_type = VisualizationType.PDF
            elif ext == "json":
                viz_type = VisualizationType.JSON

            if viz_type:
                visualizations.append(
                    Visualization(
                        viz_type=viz_type,
                        content_base64=base64.b64encode(content).decode(),
                    )
                )

        return visualizations

    async def _cleanup_sandbox(self, sandbox_id: str) -> None:
        """Cleanup sandbox.

        Args:
            sandbox_id: Sandbox to cleanup
        """
        if self.sandbox:
            try:
                await self.sandbox.destroy_sandbox(sandbox_id)
            except Exception as e:
                logger.warning(f"Failed to cleanup sandbox {sandbox_id}: {e}")

    def _generate_data_injection(
        self, data: dict[str, Any], language: SupportedLanguage
    ) -> str:
        """Generate code to inject data.

        Args:
            data: Data to inject
            language: Target language

        Returns:
            Data injection code
        """
        if language in (
            SupportedLanguage.PYTHON,
            SupportedLanguage.PYTHON311,
            SupportedLanguage.PYTHON312,
        ):
            return f"import json\ndata = json.loads('''{json.dumps(data)}''')"

        elif language in (SupportedLanguage.JAVASCRIPT, SupportedLanguage.TYPESCRIPT):
            return f"const data = {json.dumps(data)};"

        elif language == SupportedLanguage.R:
            return f"library(jsonlite)\ndata <- fromJSON('{json.dumps(data)}')"

        return ""

    def _generate_save_code(
        self,
        output_path: str,
        output_format: VisualizationType,
        language: SupportedLanguage,
    ) -> str:
        """Generate code to save visualization.

        Args:
            output_path: Output file path
            output_format: Output format
            language: Programming language

        Returns:
            Save code
        """
        if language in (
            SupportedLanguage.PYTHON,
            SupportedLanguage.PYTHON311,
            SupportedLanguage.PYTHON312,
        ):
            return f"import os\nos.makedirs(os.path.dirname('{output_path}'), exist_ok=True)\nplt.savefig('{output_path}')"

        return ""

    async def kill_execution(self, request_id: str) -> bool:
        """Kill running execution.

        Args:
            request_id: Request to kill

        Returns:
            True if killed successfully
        """
        if request_id in self._active_sandboxes:
            await self._cleanup_sandbox(self._active_sandboxes[request_id])
            del self._active_sandboxes[request_id]
            return True
        return False

    def get_supported_languages(self) -> list[dict[str, Any]]:
        """Get list of supported languages.

        Returns:
            Language information
        """
        return [
            {
                "language": lang.value,
                "extension": self.LANGUAGE_EXTENSIONS.get(lang, ""),
                "package_manager": self.PACKAGE_MANAGERS.get(lang, ""),
                "enabled": lang in self.config.allowed_languages,
            }
            for lang in SupportedLanguage
        ]

    def get_service_stats(self) -> dict:
        """Get service statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "active_sandboxes": len(self._active_sandboxes),
            "executions_completed": len(self._execution_history),
            "allowed_languages": [lang.value for lang in self.config.allowed_languages],
            "package_install_enabled": self.config.enable_package_install,
            "network_enabled": self.config.enable_network,
        }
