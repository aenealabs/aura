"""
Tests for runtime security configuration.
"""

from src.services.runtime_security import (
    PolicyMode,
    RuntimeSecurityConfig,
    Severity,
    get_runtime_security_config,
    reset_runtime_security_config,
    set_runtime_security_config,
)


class TestRuntimeSecurityConfig:
    """Tests for RuntimeSecurityConfig dataclass."""

    def test_default_config(self, test_config):
        """Test default configuration values."""
        assert test_config.environment == "test"
        assert test_config.enabled is True
        assert test_config.admission.enabled is True
        assert test_config.correlator.enabled is True

    def test_validate_valid_config(self, test_config):
        """Test validation with valid config."""
        errors = test_config.validate()
        assert len(errors) == 0

    def test_validate_invalid_timeout(self):
        """Test validation catches invalid timeout."""
        config = RuntimeSecurityConfig.for_testing()
        config.admission.timeout_seconds = 0
        errors = config.validate()
        assert any("timeout_seconds" in e for e in errors)

    def test_validate_excessive_timeout(self):
        """Test validation catches excessive timeout."""
        config = RuntimeSecurityConfig.for_testing()
        config.admission.timeout_seconds = 60
        errors = config.validate()
        assert any("timeout_seconds" in e for e in errors)

    def test_validate_invalid_batch_size(self):
        """Test validation catches invalid batch size."""
        config = RuntimeSecurityConfig.for_testing()
        config.correlator.batch_size = 0
        errors = config.validate()
        assert any("batch_size" in e for e in errors)

    def test_for_production(self):
        """Test production configuration."""
        config = RuntimeSecurityConfig.for_production()
        assert config.environment == "prod"
        assert config.admission.default_mode == PolicyMode.ENFORCE
        assert config.admission.require_sbom is True
        assert config.admission.require_signed_images is True
        assert config.admission.max_critical_cves == 0
        assert config.escape_detector.block_escapes is True
        assert config.storage.use_mock_storage is False

    def test_for_testing(self):
        """Test testing configuration."""
        config = RuntimeSecurityConfig.for_testing()
        assert config.environment == "test"
        assert config.admission.default_mode == PolicyMode.AUDIT
        assert config.admission.require_sbom is False
        assert config.storage.use_mock_storage is True
        assert config.metrics.enabled is False


class TestConfigFromEnvironment:
    """Tests for environment-based configuration."""

    def test_from_environment_defaults(self, monkeypatch):
        """Test loading config with default environment values."""
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        reset_runtime_security_config()
        config = RuntimeSecurityConfig.from_environment()
        assert config.environment == "dev"
        assert config.enabled is True

    def test_from_environment_custom(self, monkeypatch):
        """Test loading config with custom environment values."""
        monkeypatch.setenv("ENVIRONMENT", "staging")
        monkeypatch.setenv("RUNTIME_SECURITY_ENABLED", "true")
        monkeypatch.setenv("RUNTIME_ADMISSION_ENABLED", "true")
        monkeypatch.setenv("RUNTIME_WEBHOOK_PORT", "9443")
        monkeypatch.setenv("RUNTIME_SEVERITY_THRESHOLD", "CRITICAL")
        monkeypatch.setenv("RUNTIME_ADMISSION_MODE", "audit")

        reset_runtime_security_config()
        config = RuntimeSecurityConfig.from_environment()

        assert config.environment == "staging"
        assert config.admission.webhook_port == 9443
        assert config.admission.severity_threshold == Severity.CRITICAL
        assert config.admission.default_mode == PolicyMode.AUDIT

    def test_from_environment_disabled(self, monkeypatch):
        """Test loading config with features disabled."""
        monkeypatch.setenv("RUNTIME_SECURITY_ENABLED", "false")
        monkeypatch.setenv("RUNTIME_ADMISSION_ENABLED", "false")
        monkeypatch.setenv("RUNTIME_CORRELATOR_ENABLED", "false")
        monkeypatch.setenv("RUNTIME_ESCAPE_ENABLED", "false")

        reset_runtime_security_config()
        config = RuntimeSecurityConfig.from_environment()

        assert config.enabled is False
        assert config.admission.enabled is False
        assert config.correlator.enabled is False
        assert config.escape_detector.enabled is False

    def test_from_environment_storage(self, monkeypatch):
        """Test loading storage config from environment."""
        monkeypatch.setenv("ENVIRONMENT", "prod")
        monkeypatch.setenv("RUNTIME_EVENTS_TABLE", "custom-events-table")
        monkeypatch.setenv("NEPTUNE_ENDPOINT", "neptune.example.com")
        monkeypatch.setenv("RUNTIME_GRAPH_MOCK", "false")

        reset_runtime_security_config()
        config = RuntimeSecurityConfig.from_environment()

        assert config.storage.runtime_events_table == "custom-events-table"
        assert config.graph.neptune_endpoint == "neptune.example.com"
        assert config.graph.use_mock is False


class TestConfigSingleton:
    """Tests for configuration singleton pattern."""

    def test_get_config_singleton(self, test_config):
        """Test getting singleton instance."""
        config1 = get_runtime_security_config()
        config2 = get_runtime_security_config()
        assert config1 is config2

    def test_reset_config_singleton(self, test_config):
        """Test resetting singleton."""
        config1 = get_runtime_security_config()
        reset_runtime_security_config()
        config2 = get_runtime_security_config()
        assert config1 is not config2

    def test_set_config_singleton(self):
        """Test setting custom config."""
        custom_config = RuntimeSecurityConfig(
            environment="custom",
            enabled=True,
        )
        set_runtime_security_config(custom_config)
        config = get_runtime_security_config()
        assert config.environment == "custom"


class TestAdmissionControllerConfig:
    """Tests for AdmissionControllerConfig."""

    def test_allowed_registries(self, test_config):
        """Test allowed registries configuration."""
        assert len(test_config.admission.allowed_registries) > 0
        assert any("ecr" in r for r in test_config.admission.allowed_registries)

    def test_exempt_namespaces(self, test_config):
        """Test exempt namespaces configuration."""
        assert "kube-system" in test_config.admission.exempt_namespaces
        assert "kube-public" in test_config.admission.exempt_namespaces

    def test_cve_thresholds(self, test_config):
        """Test CVE threshold configuration."""
        # Test config has relaxed thresholds
        assert test_config.admission.require_sbom is False


class TestEscapeDetectorConfig:
    """Tests for EscapeDetectorConfig."""

    def test_syscalls_to_monitor(self, test_config):
        """Test syscalls configuration."""
        syscalls = test_config.escape_detector.syscalls_to_monitor
        assert "setuid" in syscalls
        assert "ptrace" in syscalls
        assert "mount" in syscalls

    def test_capabilities_to_alert(self, test_config):
        """Test capabilities configuration."""
        caps = test_config.escape_detector.capabilities_to_alert
        assert "CAP_SYS_ADMIN" in caps
        assert "CAP_SYS_PTRACE" in caps
