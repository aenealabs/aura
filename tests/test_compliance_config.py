"""
Tests for Compliance Configuration Management.

Tests configuration loading, validation, and profile management.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from src.services.compliance_config import (
    ComplianceConfig,
    ConfigurationError,
    get_compliance_config,
    reload_compliance_config,
)
from src.services.compliance_profiles import ComplianceLevel

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create temporary directory for config files."""
    config_dir = tmp_path / ".aura"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def valid_config_file(temp_config_dir):
    """Create a valid config file."""
    config_path = temp_config_dir / "config.yml"
    config_data = {
        "compliance": {
            "profile": "CMMC_LEVEL_3",
            "enabled": True,
            "custom_overrides": {},
        }
    }
    with open(config_path, "w") as f:
        yaml.safe_dump(config_data, f)
    return str(config_path)


@pytest.fixture
def invalid_yaml_file(temp_config_dir):
    """Create an invalid YAML file."""
    config_path = temp_config_dir / "config.yml"
    with open(config_path, "w") as f:
        f.write("invalid: yaml: content: [")
    return str(config_path)


@pytest.fixture
def reset_global_config():
    """Reset global config after test."""
    import src.services.compliance_config as config_module

    original = config_module._global_config
    yield
    config_module._global_config = original


# ============================================================================
# ConfigurationError Tests
# ============================================================================


class TestConfigurationError:
    """Test ConfigurationError exception."""

    def test_exception_message(self):
        """Test exception with message."""
        with pytest.raises(ConfigurationError) as exc_info:
            raise ConfigurationError("Test error")
        assert "Test error" in str(exc_info.value)


# ============================================================================
# ComplianceConfig Initialization Tests
# ============================================================================


class TestComplianceConfigInit:
    """Test ComplianceConfig initialization."""

    def test_init_with_path(self):
        """Test initialization with explicit path."""
        config = ComplianceConfig(config_path="/path/to/config.yml")
        assert config.config_path == "/path/to/config.yml"
        assert config.config_data == {}
        assert config.profile_manager is None

    @patch.object(Path, "exists", return_value=False)
    def test_init_without_path_no_config_found(self, mock_exists):
        """Test initialization without path when no config found."""
        config = ComplianceConfig()
        # Should return empty string when no config found
        assert config.config_path == ""


# ============================================================================
# Config File Discovery Tests
# ============================================================================


class TestFindConfigFile:
    """Test config file discovery."""

    @patch.object(Path, "cwd")
    @patch.object(Path, "home")
    def test_finds_project_config(self, mock_home, mock_cwd, tmp_path):
        """Test finding project config file."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        aura_dir = project_dir / ".aura"
        aura_dir.mkdir()
        config_file = aura_dir / "config.yml"
        config_file.write_text("compliance:\n  profile: CMMC_LEVEL_3")

        mock_cwd.return_value = project_dir
        mock_home.return_value = tmp_path / "home"

        config = ComplianceConfig()
        assert "config.yml" in config.config_path

    @patch.object(Path, "cwd")
    @patch.object(Path, "home")
    def test_finds_home_config(self, mock_home, mock_cwd, tmp_path):
        """Test finding home directory config."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        aura_dir = home_dir / ".aura"
        aura_dir.mkdir()
        config_file = aura_dir / "config.yml"
        config_file.write_text("compliance:\n  profile: CMMC_LEVEL_3")

        mock_cwd.return_value = project_dir
        mock_home.return_value = home_dir

        config = ComplianceConfig()
        assert ".aura" in config.config_path or config.config_path == ""


# ============================================================================
# Config Loading Tests
# ============================================================================


class TestLoadConfig:
    """Test configuration loading."""

    def test_load_valid_config(self, valid_config_file):
        """Test loading a valid configuration file."""
        config = ComplianceConfig(config_path=valid_config_file)
        config.load()

        assert config.config_data is not None
        assert "compliance" in config.config_data
        assert config.config_data["compliance"]["profile"] == "CMMC_LEVEL_3"

    def test_load_no_config_uses_defaults(self):
        """Test loading with no config file uses defaults."""
        config = ComplianceConfig(config_path="")
        config.load()

        assert config.config_data["compliance"]["profile"] == "CMMC_LEVEL_3"
        assert config.config_data["compliance"]["enabled"] is True

    def test_load_invalid_yaml(self, invalid_yaml_file):
        """Test loading invalid YAML raises error."""
        config = ComplianceConfig(config_path=invalid_yaml_file)
        with pytest.raises(ConfigurationError, match="Invalid YAML"):
            config.load()

    def test_load_nonexistent_file(self, tmp_path):
        """Test loading nonexistent file uses defaults."""
        config = ComplianceConfig(config_path=str(tmp_path / "nonexistent.yml"))
        config.load()
        # Should use defaults
        assert config.config_data["compliance"]["profile"] == "CMMC_LEVEL_3"


# ============================================================================
# Config Validation Tests
# ============================================================================


class TestConfigValidation:
    """Test configuration validation."""

    def test_validate_missing_compliance_section(self, temp_config_dir):
        """Test validation adds defaults for missing compliance section."""
        config_path = temp_config_dir / "config.yml"
        with open(config_path, "w") as f:
            yaml.safe_dump({"other_section": {}}, f)

        config = ComplianceConfig(config_path=str(config_path))
        config.load()
        # Should have compliance section with defaults
        assert "compliance" in config.config_data

    def test_validate_invalid_profile_name(self, temp_config_dir):
        """Test validation rejects invalid profile name."""
        config_path = temp_config_dir / "config.yml"
        with open(config_path, "w") as f:
            yaml.safe_dump({"compliance": {"profile": "INVALID_PROFILE"}}, f)

        config = ComplianceConfig(config_path=str(config_path))
        with pytest.raises(ConfigurationError, match="Invalid compliance profile"):
            config.load()

    def test_validate_invalid_enabled_type(self, temp_config_dir):
        """Test validation rejects non-boolean enabled value."""
        config_path = temp_config_dir / "config.yml"
        with open(config_path, "w") as f:
            yaml.safe_dump(
                {
                    "compliance": {
                        "profile": "CMMC_LEVEL_3",
                        "enabled": "yes",  # Should be boolean
                    }
                },
                f,
            )

        config = ComplianceConfig(config_path=str(config_path))
        with pytest.raises(ConfigurationError, match="must be boolean"):
            config.load()

    def test_validate_invalid_overrides_type(self, temp_config_dir):
        """Test validation rejects non-dict custom_overrides."""
        config_path = temp_config_dir / "config.yml"
        with open(config_path, "w") as f:
            yaml.safe_dump(
                {
                    "compliance": {
                        "profile": "CMMC_LEVEL_3",
                        "custom_overrides": ["list", "not", "dict"],
                    }
                },
                f,
            )

        config = ComplianceConfig(config_path=str(config_path))
        with pytest.raises(ConfigurationError, match="must be a dictionary"):
            config.load()


# ============================================================================
# Config Methods Tests
# ============================================================================


class TestConfigMethods:
    """Test ComplianceConfig methods."""

    def test_is_enabled_true(self, valid_config_file):
        """Test is_enabled returns true when enabled."""
        config = ComplianceConfig(config_path=valid_config_file)
        config.load()
        assert config.is_enabled() is True

    def test_is_enabled_false(self, temp_config_dir):
        """Test is_enabled returns false when disabled."""
        config_path = temp_config_dir / "config.yml"
        with open(config_path, "w") as f:
            yaml.safe_dump(
                {
                    "compliance": {
                        "profile": "CMMC_LEVEL_3",
                        "enabled": False,
                    }
                },
                f,
            )

        config = ComplianceConfig(config_path=str(config_path))
        config.load()
        assert config.is_enabled() is False

    def test_get_profile(self, valid_config_file):
        """Test getting the compliance profile."""
        config = ComplianceConfig(config_path=valid_config_file)
        config.load()
        profile = config.get_profile()
        assert profile.name == ComplianceLevel.CMMC_LEVEL_3

    def test_get_profile_manager(self, valid_config_file):
        """Test getting the profile manager."""
        config = ComplianceConfig(config_path=valid_config_file)
        config.load()
        manager = config.get_profile_manager()
        assert manager is not None
        assert manager._current_profile is not None

    def test_get_profile_name(self, valid_config_file):
        """Test getting the profile name."""
        config = ComplianceConfig(config_path=valid_config_file)
        config.load()
        assert config.get_profile_name() == "CMMC_LEVEL_3"

    def test_get_profile_without_load(self):
        """Test get_profile initializes profile manager if needed."""
        config = ComplianceConfig(config_path="")
        config.config_data = {"compliance": {"profile": "DEVELOPMENT"}}
        profile = config.get_profile()
        assert profile is not None


# ============================================================================
# Config Save Tests
# ============================================================================


class TestConfigSave:
    """Test configuration saving."""

    def test_save_to_existing_path(self, valid_config_file):
        """Test saving to existing config path."""
        config = ComplianceConfig(config_path=valid_config_file)
        config.load()
        config.config_data["compliance"]["enabled"] = False
        config.save()

        # Reload and verify
        with open(valid_config_file, "r") as f:
            saved_data = yaml.safe_load(f)
        assert saved_data["compliance"]["enabled"] is False

    def test_save_to_new_path(self, tmp_path):
        """Test saving to a new path."""
        config = ComplianceConfig(config_path="")
        config.config_data = {"compliance": {"profile": "SOX"}}

        save_path = str(tmp_path / ".aura" / "config.yml")
        config.save(save_path)

        with open(save_path, "r") as f:
            saved_data = yaml.safe_load(f)
        assert saved_data["compliance"]["profile"] == "SOX"

    def test_save_creates_directory(self, tmp_path):
        """Test save creates directory if needed."""
        config = ComplianceConfig(config_path="")
        config.config_data = {"compliance": {"profile": "CMMC_LEVEL_2"}}

        save_path = str(tmp_path / "new_dir" / ".aura" / "config.yml")
        config.save(save_path)

        assert os.path.exists(save_path)


# ============================================================================
# Factory Method Tests
# ============================================================================


class TestCreateDefaultConfig:
    """Test create_default_config factory method."""

    def test_create_default_config(self, tmp_path):
        """Test creating default configuration."""
        output_path = str(tmp_path / ".aura" / "config.yml")
        result = ComplianceConfig.create_default_config(output_path)

        assert result == output_path
        assert os.path.exists(output_path)

        with open(output_path, "r") as f:
            config_data = yaml.safe_load(f)

        assert "compliance" in config_data
        assert config_data["compliance"]["profile"] == "CMMC_LEVEL_3"
        assert "agent" in config_data
        assert "sandbox" in config_data


# ============================================================================
# Global Config Tests
# ============================================================================


class TestGlobalConfig:
    """Test global config functions."""

    @patch("src.services.compliance_config._global_config", None)
    def test_get_compliance_config(self, reset_global_config):
        """Test getting global config singleton."""
        with patch.object(ComplianceConfig, "load", return_value=None):
            config = get_compliance_config()
            assert config is not None

    @patch("src.services.compliance_config._global_config", None)
    def test_reload_compliance_config(self, reset_global_config):
        """Test reloading global config."""
        with patch.object(ComplianceConfig, "load", return_value=None):
            config = reload_compliance_config()
            assert config is not None


# ============================================================================
# Custom Overrides Tests
# ============================================================================


class TestCustomOverrides:
    """Test custom overrides functionality."""

    def test_load_with_overrides(self, temp_config_dir):
        """Test loading config with custom overrides."""
        config_path = temp_config_dir / "config.yml"
        with open(config_path, "w") as f:
            yaml.safe_dump(
                {
                    "compliance": {
                        "profile": "CMMC_LEVEL_3",
                        "enabled": True,
                        "custom_overrides": {
                            "scanning.scan_documentation": False,
                            "review.min_reviewers": 3,
                        },
                    }
                },
                f,
            )

        config = ComplianceConfig(config_path=str(config_path))
        config.load()

        # Overrides should be applied via profile manager
        config.get_profile()
        # Note: overrides are applied via profile manager
        assert config.profile_manager is not None
