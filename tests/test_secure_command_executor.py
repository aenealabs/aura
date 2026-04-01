"""
Project Aura - Secure Command Executor Tests

Tests for the secure command execution service covering:
- Command validation and whitelisting
- Argument sanitization
- Dangerous pattern detection
- Command execution with proper security controls

Author: Project Aura Team
Created: 2025-12-12
"""

import pytest

from src.services.secure_command_executor import (
    CommandExecutionError,
    CommandResult,
    CommandRisk,
    SecureCommandExecutor,
    SecurityViolationError,
    get_secure_executor,
    safe_execute,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def executor():
    """Create a standard secure executor instance."""
    return SecureCommandExecutor(log_commands=False)


@pytest.fixture
def restricted_executor():
    """Create an executor with restricted commands enabled."""
    return SecureCommandExecutor(allow_restricted=True, log_commands=False)


# ============================================================================
# Command Validation Tests
# ============================================================================


class TestCommandValidation:
    """Tests for command validation."""

    def test_safe_command_allowed(self, executor):
        """Test that safe commands are allowed."""
        risk = executor._validate_command("git")
        assert risk == CommandRisk.LOW

    def test_safe_commands_list(self, executor):
        """Test all safe commands."""
        for cmd in executor.SAFE_COMMANDS:
            risk = executor._validate_command(cmd)
            assert risk == CommandRisk.LOW

    def test_blocked_command_rejected(self, executor):
        """Test that blocked commands are rejected."""
        for cmd in ["sudo", "ssh", "netcat", "curl", "wget"]:
            with pytest.raises(SecurityViolationError) as exc_info:
                executor._validate_command(cmd)
            assert "blocked" in str(exc_info.value).lower()

    def test_restricted_command_without_flag(self, executor):
        """Test restricted commands fail without allow_restricted."""
        with pytest.raises(SecurityViolationError) as exc_info:
            executor._validate_command("rm")
        assert "restricted" in str(exc_info.value).lower()

    def test_restricted_command_with_flag(self, restricted_executor):
        """Test restricted commands allowed with flag."""
        risk = restricted_executor._validate_command("rm")
        assert risk == CommandRisk.HIGH

    def test_unknown_command_blocked(self, executor):
        """Test that unknown commands are blocked."""
        with pytest.raises(SecurityViolationError) as exc_info:
            executor._validate_command("unknown_cmd")
        assert "not in the allowed list" in str(exc_info.value)

    def test_custom_whitelist(self):
        """Test custom whitelist."""
        executor = SecureCommandExecutor(
            custom_whitelist={"my_tool"},
            log_commands=False,
        )
        risk = executor._validate_command("my_tool")
        assert risk == CommandRisk.MEDIUM

    def test_command_case_insensitive(self, executor):
        """Test that command validation is case-insensitive."""
        risk = executor._validate_command("GIT")
        assert risk == CommandRisk.LOW


# ============================================================================
# Argument Validation Tests
# ============================================================================


class TestArgumentValidation:
    """Tests for argument validation."""

    def test_safe_argument_passes(self, executor):
        """Test that safe arguments pass validation."""
        safe_args = ["file.txt", "--verbose", "-n", "100", "path/to/file"]
        for arg in safe_args:
            executor._validate_argument(arg)  # Should not raise

    def test_shell_metacharacters_blocked(self, executor):
        """Test that shell metacharacters are blocked."""
        dangerous_args = [
            "file; rm -rf /",
            "file | cat /etc/passwd",
            "$(whoami)",
            "`id`",
            "file & background",
        ]
        for arg in dangerous_args:
            with pytest.raises(SecurityViolationError):
                executor._validate_argument(arg)

    def test_path_traversal_blocked(self, executor):
        """Test that path traversal is blocked."""
        with pytest.raises(SecurityViolationError):
            executor._validate_argument("../../etc/passwd")

    def test_null_byte_blocked(self, executor):
        """Test that null bytes are blocked."""
        with pytest.raises(SecurityViolationError):
            executor._validate_argument("file.txt\x00.jpg")

    def test_device_paths_blocked(self, executor):
        """Test that device paths are blocked."""
        with pytest.raises(SecurityViolationError):
            executor._validate_argument("/dev/sda")

    def test_hex_escapes_blocked(self, executor):
        """Test that hex escapes are blocked."""
        with pytest.raises(SecurityViolationError):
            executor._validate_argument("\\x00\\x01")


# ============================================================================
# Command Execution Tests
# ============================================================================


class TestCommandExecution:
    """Tests for command execution."""

    def test_execute_simple_command(self, executor):
        """Test executing a simple safe command."""
        result = executor.execute(["echo", "hello"])
        assert result.success
        assert result.return_code == 0
        assert "hello" in result.stdout

    def test_execute_string_command(self, executor):
        """Test executing command from string."""
        result = executor.execute("echo hello world")
        assert result.success
        assert "hello world" in result.stdout

    def test_execute_git_status(self, executor):
        """Test executing git status."""
        result = executor.execute_git("--version")
        assert result.success
        assert "git version" in result.stdout.lower()

    def test_blocked_command_not_executed(self, executor):
        """Test that blocked commands are not executed."""
        with pytest.raises(SecurityViolationError):
            executor.execute(["sudo", "ls"])

    def test_command_with_dangerous_arg_blocked(self, executor):
        """Test that commands with dangerous arguments are blocked."""
        with pytest.raises(SecurityViolationError):
            executor.execute(["echo", "hello; rm -rf /"])

    def test_command_result_structure(self, executor):
        """Test CommandResult structure."""
        result = executor.execute(["echo", "test"])
        assert isinstance(result, CommandResult)
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)
        assert isinstance(result.return_code, int)
        assert isinstance(result.command, list)
        assert isinstance(result.success, bool)

    def test_to_dict(self, executor):
        """Test CommandResult.to_dict()."""
        result = executor.execute(["echo", "test"])
        d = result.to_dict()
        assert "stdout" in d
        assert "stderr" in d
        assert "return_code" in d
        assert "command" in d
        assert "success" in d

    def test_check_raises_on_failure(self, executor):
        """Test that check=True raises on failure."""
        with pytest.raises(CommandExecutionError):
            executor.execute(["ls", "/nonexistent_path_12345"], check=True)

    def test_empty_command_fails(self, executor):
        """Test that empty command fails."""
        with pytest.raises(CommandExecutionError):
            executor.execute([])


# ============================================================================
# Security Tests
# ============================================================================


class TestSecurityControls:
    """Tests for security controls."""

    def test_no_shell_execution(self, executor):
        """Test that shell execution is never used."""
        # When using shell=False, asterisks should NOT be expanded
        # This test verifies shell=False by checking glob patterns aren't expanded
        result = executor.execute(["echo", "*.txt"])
        # The literal *.txt should appear (not expanded files)
        assert "*.txt" in result.stdout

    def test_command_injection_blocked(self, executor):
        """Test command injection attempts are blocked."""
        injection_attempts = [
            ["echo", "hello; cat /etc/passwd"],
            ["echo", "hello && rm -rf /"],
            ["echo", "$(cat /etc/passwd)"],
            ["echo", "`whoami`"],
        ]
        for cmd in injection_attempts:
            with pytest.raises(SecurityViolationError):
                executor.execute(cmd)

    def test_path_traversal_in_command_blocked(self, executor):
        """Test path traversal in command arguments is blocked."""
        with pytest.raises(SecurityViolationError):
            executor.execute(["cat", "../../../etc/passwd"])


# ============================================================================
# Statistics Tests
# ============================================================================


class TestStatistics:
    """Tests for statistics tracking."""

    def test_stats_tracking(self, executor):
        """Test that statistics are tracked."""
        executor.execute(["echo", "test1"])
        executor.execute(["echo", "test2"])

        stats = executor.get_stats()
        assert stats["total_executed"] == 2
        assert stats["succeeded"] == 2
        assert stats["failed"] == 0

    def test_stats_reset(self, executor):
        """Test that statistics can be reset."""
        executor.execute(["echo", "test"])
        executor.reset_stats()

        stats = executor.get_stats()
        assert stats["total_executed"] == 0


# ============================================================================
# Convenience Function Tests
# ============================================================================


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_get_secure_executor_singleton(self):
        """Test that get_secure_executor returns a singleton."""
        executor1 = get_secure_executor()
        executor2 = get_secure_executor()
        assert executor1 is executor2

    def test_safe_execute_function(self):
        """Test the safe_execute convenience function."""
        result = safe_execute(["echo", "hello"])
        assert result.success
        assert "hello" in result.stdout


# ============================================================================
# Edge Case Tests
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_command_with_spaces_in_args(self, executor):
        """Test command with spaces in arguments."""
        result = executor.execute(["echo", "hello world"])
        assert "hello world" in result.stdout

    def test_command_with_quotes_in_args(self, executor):
        """Test command with quotes in arguments."""
        result = executor.execute(["echo", '"quoted"'])
        assert '"quoted"' in result.stdout

    def test_unicode_in_args(self, executor):
        """Test Unicode characters in arguments."""
        result = executor.execute(["echo", "日本語"])
        assert "日本語" in result.stdout

    def test_working_directory(self):
        """Test working directory configuration."""
        executor = SecureCommandExecutor(
            working_dir="/tmp",
            log_commands=False,
        )
        result = executor.execute(["pwd"])
        assert "/tmp" in result.stdout or "/private/tmp" in result.stdout


# ============================================================================
# Timeout Tests
# ============================================================================


class TestTimeout:
    """Tests for timeout handling."""

    def test_timeout_configured(self):
        """Test that timeout is configurable."""
        executor = SecureCommandExecutor(
            timeout_seconds=5,
            log_commands=False,
        )
        assert executor.timeout_seconds == 5

    def test_timeout_raises_error(self):
        """Test that timeout raises CommandExecutionError - lines 354-355."""
        import subprocess
        from unittest.mock import patch

        executor = SecureCommandExecutor(
            timeout_seconds=1,
            log_commands=False,
        )
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="echo", timeout=1)
            with pytest.raises(CommandExecutionError, match="timed out"):
                executor.execute(["echo", "test"])


# ============================================================================
# Error Handling Tests (Coverage)
# ============================================================================


class TestErrorHandling:
    """Tests for error handling edge cases."""

    def test_invalid_command_format(self, executor):
        """Test invalid command format raises error - lines 294-295."""
        # Unmatched quote causes shlex.split to fail
        with pytest.raises(CommandExecutionError, match="Invalid command format"):
            executor.execute('echo "unclosed quote')

    def test_subprocess_error(self, executor):
        """Test subprocess error handling - lines 359-360."""
        import subprocess
        from unittest.mock import patch

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.SubprocessError("Mock error")
            with pytest.raises(CommandExecutionError, match="execution failed"):
                executor.execute(["echo", "test"])
