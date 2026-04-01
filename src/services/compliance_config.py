"""
Compliance Configuration Management.

Loads and validates Aura compliance configuration from YAML files.

Author: Aura Platform Team
Date: 2025-12-06
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional, cast

import yaml

from src.services.compliance_profiles import (
    ComplianceLevel,
    ComplianceProfile,
    ComplianceProfileManager,
)

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration is invalid."""


class ComplianceConfig:
    """
    Compliance configuration loaded from .aura/config.yml.

    Example configuration:
        compliance:
          profile: CMMC_LEVEL_3
          custom_overrides:
            scanning.scan_documentation: false
            review.min_reviewers: 3
          enabled: true
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        """
        Initialize ComplianceConfig.

        Args:
            config_path: Path to config file (defaults to .aura/config.yml)
        """
        self.config_path = config_path or self._find_config_file()
        self.config_data: Dict[str, Any] = {}
        self.profile_manager: Optional[ComplianceProfileManager] = None

    def _find_config_file(self) -> str:
        """
        Find the Aura configuration file.

        Searches in order:
        1. .aura/config.yml (project root)
        2. ~/.aura/config.yml (user home)
        3. Uses default CMMC_LEVEL_3 if not found

        Returns:
            Path to configuration file
        """
        candidates = [
            Path.cwd() / ".aura" / "config.yml",
            Path.home() / ".aura" / "config.yml",
        ]

        for candidate in candidates:
            if candidate.exists():
                logger.info(f"Found Aura config at: {candidate}")
                return str(candidate)

        logger.warning("No .aura/config.yml found, using default CMMC Level 3 profile")
        return ""

    def load(self) -> "ComplianceConfig":
        """
        Load configuration from file.

        Returns:
            Self for method chaining

        Raises:
            ConfigurationError: If configuration is invalid
        """
        if not self.config_path or not Path(self.config_path).exists():
            logger.info("Using default configuration (CMMC Level 3)")
            self.config_data = self._get_default_config()
        else:
            try:
                with open(self.config_path, "r") as f:
                    self.config_data = yaml.safe_load(f) or {}
                logger.info(f"Loaded configuration from {self.config_path}")
            except yaml.YAMLError as e:
                raise ConfigurationError(f"Invalid YAML in config file: {e}")
            except Exception as e:
                raise ConfigurationError(f"Failed to load config file: {e}")

        # Validate configuration
        self._validate()

        # Initialize profile manager
        self._initialize_profile_manager()

        return self

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "compliance": {
                "profile": "CMMC_LEVEL_3",
                "enabled": True,
                "custom_overrides": {},
            }
        }

    def _validate(self) -> None:
        """
        Validate configuration structure.

        Raises:
            ConfigurationError: If configuration is invalid
        """
        # Check for compliance section
        if "compliance" not in self.config_data:
            logger.warning("No 'compliance' section in config, using defaults")
            self.config_data["compliance"] = self._get_default_config()["compliance"]
            return

        compliance = self.config_data["compliance"]

        # Validate profile name
        profile_name = compliance.get("profile", "CMMC_LEVEL_3")
        try:
            ComplianceLevel(profile_name)
        except ValueError:
            raise ConfigurationError(
                f"Invalid compliance profile: {profile_name}. "
                f"Valid profiles: {[p.value for p in ComplianceLevel]}"
            )

        # Validate enabled flag
        if "enabled" in compliance and not isinstance(compliance["enabled"], bool):
            raise ConfigurationError(
                f"'compliance.enabled' must be boolean, got {type(compliance['enabled'])}"
            )

        # Validate custom_overrides
        if "custom_overrides" in compliance:
            if not isinstance(compliance["custom_overrides"], dict):
                raise ConfigurationError(
                    "'compliance.custom_overrides' must be a dictionary"
                )

        logger.info("Configuration validation passed")

    def _initialize_profile_manager(self) -> None:
        """Initialize the compliance profile manager."""
        compliance = self.config_data.get("compliance", {})
        profile_name = ComplianceLevel(compliance.get("profile", "CMMC_LEVEL_3"))

        self.profile_manager = ComplianceProfileManager(profile_name)
        self.profile_manager.load_profile()

        # Apply custom overrides
        overrides = compliance.get("custom_overrides", {})
        if overrides:
            self.profile_manager.apply_overrides(overrides)
            logger.info(f"Applied {len(overrides)} custom overrides")

    def is_enabled(self) -> bool:
        """Check if compliance enforcement is enabled."""
        return cast(bool, self.config_data.get("compliance", {}).get("enabled", True))

    def get_profile(self) -> ComplianceProfile:
        """
        Get the active compliance profile.

        Returns:
            ComplianceProfile instance
        """
        if self.profile_manager is None:
            self._initialize_profile_manager()

        assert self.profile_manager is not None
        return self.profile_manager.get_current_profile()

    def get_profile_manager(self) -> ComplianceProfileManager:
        """
        Get the profile manager.

        Returns:
            ComplianceProfileManager instance
        """
        if self.profile_manager is None:
            self._initialize_profile_manager()

        assert self.profile_manager is not None
        return self.profile_manager

    def get_profile_name(self) -> str:
        """Get the name of the active profile."""
        return cast(
            str, self.config_data.get("compliance", {}).get("profile", "CMMC_LEVEL_3")
        )

    def save(self, path: Optional[str] = None) -> None:
        """
        Save current configuration to file.

        Args:
            path: Path to save to (uses current config_path if None)
        """
        save_path = path or self.config_path

        if not save_path:
            save_path = str(Path.cwd() / ".aura" / "config.yml")

        # Create directory if needed
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)

        with open(save_path, "w") as f:
            yaml.safe_dump(self.config_data, f, default_flow_style=False, indent=2)

        logger.info(f"Saved configuration to {save_path}")

    @classmethod
    def create_default_config(cls, output_path: Optional[str] = None) -> str:
        """
        Create a default configuration file.

        Args:
            output_path: Path to save to (defaults to .aura/config.yml)

        Returns:
            Path to created config file
        """
        if not output_path:
            output_path = str(Path.cwd() / ".aura" / "config.yml")

        config = cls()
        config.config_data = {
            "compliance": {
                "profile": "CMMC_LEVEL_3",
                "enabled": True,
                "custom_overrides": {
                    # Example overrides (commented out)
                    # "scanning.scan_documentation": False,
                    # "review.min_reviewers": 3,
                },
            },
            "agent": {
                "orchestrator": {
                    "max_retries": 3,
                    "timeout_seconds": 300,
                },
                "coder": {
                    "model": "claude-3-5-sonnet-20241022",
                    "temperature": 0.2,
                },
            },
            "sandbox": {
                "default_isolation_level": "container",
                "timeout_minutes": 30,
            },
        }

        config.save(output_path)
        return output_path


# Global configuration instance
_global_config: Optional[ComplianceConfig] = None


def get_compliance_config() -> ComplianceConfig:
    """
    Get the global compliance configuration instance.

    Returns:
        ComplianceConfig singleton
    """
    global _global_config

    if _global_config is None:
        _global_config = ComplianceConfig()
        _global_config.load()

    return _global_config


def reload_compliance_config() -> ComplianceConfig:
    """
    Reload the global compliance configuration.

    Returns:
        ComplianceConfig singleton
    """
    global _global_config
    _global_config = ComplianceConfig()
    _global_config.load()
    return _global_config
