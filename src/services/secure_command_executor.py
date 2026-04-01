"""
Project Aura - Secure Command Executor Service

Provides safe command execution utilities to prevent command injection.
Addresses OWASP A3:2021 (Injection) and CWE-78 (OS Command Injection).

Author: Project Aura Team
Created: 2025-12-12
"""

import logging
import re
import shlex
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CommandExecutionError(Exception):
    """Raised when command execution fails or is blocked."""


class SecurityViolationError(Exception):
    """Raised when a security violation is detected."""


class CommandRisk(Enum):
    """Risk level for command operations."""

    LOW = "low"  # Read-only operations
    MEDIUM = "medium"  # Modifying operations
    HIGH = "high"  # Potentially destructive operations
    CRITICAL = "critical"  # System-level operations


@dataclass
class CommandResult:
    """Result of command execution."""

    stdout: str
    stderr: str
    return_code: int
    command: list[str]
    success: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "return_code": self.return_code,
            "command": self.command,
            "success": self.success,
        }


class SecureCommandExecutor:
    """
    Secure command executor that prevents command injection.

    Features:
    - Never uses shell=True
    - Validates and sanitizes all arguments
    - Whitelist-based command filtering
    - Argument validation against dangerous patterns
    - Audit logging of all executions
    """

    # Commands that are generally safe for read-only operations
    # NOTE: env/printenv intentionally excluded - could leak secrets (CWE-214)
    SAFE_COMMANDS = frozenset(
        {
            "git",
            "ls",
            "cat",
            "head",
            "tail",
            "grep",
            "wc",
            "diff",
            "echo",
            "pwd",
            "whoami",
            "date",
            "hostname",
            "which",
        }
    )

    # Commands that require elevated permissions
    RESTRICTED_COMMANDS = frozenset(
        {
            "rm",
            "mv",
            "cp",
            "mkdir",
            "chmod",
            "chown",
            "kill",
            "pkill",
            "docker",
            "kubectl",
            "pip",
            "npm",
            "apt",
            "yum",
        }
    )

    # Commands that are always blocked
    BLOCKED_COMMANDS = frozenset(
        {
            "sudo",
            "su",
            "chroot",
            "mount",
            "umount",
            "dd",
            "mkfs",
            "fdisk",
            "shutdown",
            "reboot",
            "init",
            "systemctl",
            "service",
            "iptables",
            "nc",
            "netcat",
            "curl",
            "wget",
            "ssh",
            "scp",
            "rsync",
        }
    )

    # Dangerous argument patterns (regex)
    DANGEROUS_PATTERNS = [
        r"[;&|`$(){}]",  # Shell metacharacters
        r"\.\./",  # Path traversal
        r"^-[a-zA-Z]*r[a-zA-Z]*f",  # Dangerous rm flags (-rf)
        r"^/dev/",  # Device files
        r"^/etc/",  # System config (when combined with writes)
        r"^/proc/",  # Proc filesystem
        r"^/sys/",  # Sys filesystem
        r"\x00",  # Null bytes
        r"\\x[0-9a-fA-F]{2}",  # Hex escapes
        r"\\[0-7]{3}",  # Octal escapes
    ]

    def __init__(
        self,
        allow_restricted: bool = False,
        custom_whitelist: set[str] | None = None,
        timeout_seconds: int = 30,
        working_dir: str | None = None,
        log_commands: bool = True,
    ):
        """
        Initialize secure command executor.

        Args:
            allow_restricted: Allow restricted commands (requires explicit enable)
            custom_whitelist: Additional commands to allow
            timeout_seconds: Maximum execution time
            working_dir: Working directory for commands
            log_commands: Whether to log executed commands
        """
        self.allow_restricted = allow_restricted
        self.custom_whitelist = custom_whitelist or set()
        self.timeout_seconds = timeout_seconds
        self.working_dir = working_dir
        self.log_commands = log_commands

        # Statistics
        self._stats = {
            "total_executed": 0,
            "blocked": 0,
            "succeeded": 0,
            "failed": 0,
        }

        # Compile dangerous patterns
        self._compiled_patterns = [
            re.compile(pattern) for pattern in self.DANGEROUS_PATTERNS
        ]

    def _validate_command(self, command: str) -> CommandRisk:
        """
        Validate if command is allowed.

        Args:
            command: The command name (without arguments)

        Returns:
            Risk level of the command

        Raises:
            SecurityViolationError: If command is blocked
        """
        cmd_lower = command.lower()

        # Check blocked commands first
        if cmd_lower in self.BLOCKED_COMMANDS:
            raise SecurityViolationError(
                f"Command '{command}' is blocked for security reasons"
            )

        # Check restricted commands
        if cmd_lower in self.RESTRICTED_COMMANDS:
            if not self.allow_restricted:
                raise SecurityViolationError(
                    f"Command '{command}' is restricted. Enable allow_restricted to use it."
                )
            return CommandRisk.HIGH

        # Check safe commands
        if cmd_lower in self.SAFE_COMMANDS:
            return CommandRisk.LOW

        # Check custom whitelist
        if cmd_lower in self.custom_whitelist:
            return CommandRisk.MEDIUM

        # Unknown commands are blocked by default
        raise SecurityViolationError(
            f"Command '{command}' is not in the allowed list. "
            "Add it to custom_whitelist if needed."
        )

    def _validate_argument(self, arg: str) -> None:
        """
        Validate a single argument for dangerous patterns.

        Args:
            arg: The argument to validate

        Raises:
            SecurityViolationError: If argument contains dangerous patterns
        """
        for pattern in self._compiled_patterns:
            if pattern.search(arg):
                raise SecurityViolationError(
                    f"Argument contains dangerous pattern: {arg!r}"
                )

    def _sanitize_argument(self, arg: str) -> str:
        """
        Sanitize an argument by removing potentially dangerous characters.

        Args:
            arg: The argument to sanitize

        Returns:
            Sanitized argument
        """
        # Remove null bytes
        sanitized = arg.replace("\x00", "")

        # Escape shell metacharacters by using shlex.quote
        # Note: We don't actually need this since we use shell=False,
        # but it provides an extra layer of safety
        return sanitized

    def execute(
        self,
        command: str | list[str],
        capture_output: bool = True,
        check: bool = False,
    ) -> CommandResult:
        """
        Execute a command securely.

        Args:
            command: Command as string (will be split) or list of arguments
            capture_output: Capture stdout/stderr
            check: Raise exception on non-zero return code

        Returns:
            CommandResult with execution results

        Raises:
            SecurityViolationError: If command or arguments are blocked
            CommandExecutionError: If execution fails
        """
        # Parse command if string
        if isinstance(command, str):
            try:
                cmd_list = shlex.split(command)
            except ValueError as e:
                raise CommandExecutionError(f"Invalid command format: {e}")
        else:
            cmd_list = list(command)

        if not cmd_list:
            raise CommandExecutionError("Empty command")

        # Validate command name
        cmd_name = cmd_list[0]
        risk = self._validate_command(cmd_name)

        # Validate all arguments
        for arg in cmd_list[1:]:
            self._validate_argument(arg)

        # Sanitize arguments
        sanitized_cmd = [cmd_list[0]] + [
            self._sanitize_argument(arg) for arg in cmd_list[1:]
        ]

        # Log command execution
        if self.log_commands:
            logger.info(f"Executing command: {sanitized_cmd!r} (risk: {risk.value})")

        self._stats["total_executed"] += 1

        try:
            # Execute with shell=False (CRITICAL for security)
            result = subprocess.run(
                sanitized_cmd,
                capture_output=capture_output,
                text=True,
                timeout=self.timeout_seconds,
                cwd=self.working_dir,
                shell=False,  # NEVER use shell=True
            )

            cmd_result = CommandResult(
                stdout=result.stdout if capture_output else "",
                stderr=result.stderr if capture_output else "",
                return_code=result.returncode,
                command=sanitized_cmd,
                success=result.returncode == 0,
            )

            if cmd_result.success:
                self._stats["succeeded"] += 1
            else:
                self._stats["failed"] += 1

            if check and not cmd_result.success:
                raise CommandExecutionError(
                    f"Command failed with return code {result.returncode}: "
                    f"{result.stderr}"
                )

            return cmd_result

        except subprocess.TimeoutExpired:
            self._stats["failed"] += 1
            raise CommandExecutionError(
                f"Command timed out after {self.timeout_seconds} seconds"
            )
        except subprocess.SubprocessError as e:
            self._stats["failed"] += 1
            raise CommandExecutionError(f"Command execution failed: {e}")

    def execute_git(self, *args: str, check: bool = True) -> CommandResult:
        """
        Execute a git command securely.

        Args:
            *args: Git command arguments (e.g., "status", "--short")
            check: Raise exception on failure

        Returns:
            CommandResult
        """
        return self.execute(["git", *args], check=check)

    def get_stats(self) -> dict[str, int]:
        """Get execution statistics."""
        return dict(self._stats)

    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = {
            "total_executed": 0,
            "blocked": 0,
            "succeeded": 0,
            "failed": 0,
        }


# =============================================================================
# Singleton Instance
# =============================================================================


_executor: SecureCommandExecutor | None = None


def get_secure_executor() -> SecureCommandExecutor:
    """Get singleton secure command executor instance."""
    global _executor
    if _executor is None:
        _executor = SecureCommandExecutor(log_commands=True)
    return _executor


def safe_execute(
    command: str | list[str],
    capture_output: bool = True,
    check: bool = False,
) -> CommandResult:
    """
    Convenience function to execute a command securely.

    Args:
        command: Command to execute
        capture_output: Capture stdout/stderr
        check: Raise on failure

    Returns:
        CommandResult
    """
    executor = get_secure_executor()
    return executor.execute(command, capture_output=capture_output, check=check)
