"""Tests for memory evolution configuration."""

import os
from unittest.mock import patch

from src.services.memory_evolution import (
    AsyncConfig,
    ConsolidationConfig,
    FeatureFlags,
    MemoryEvolutionConfig,
    MetricsConfig,
    PruneConfig,
    SecurityConfig,
    StorageConfig,
    get_memory_evolution_config,
    reset_memory_evolution_config,
    set_memory_evolution_config,
)


class TestMemoryEvolutionConfig:
    """Tests for MemoryEvolutionConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = MemoryEvolutionConfig()

        assert config.environment == "dev"
        assert config.project_name == "aura"
        assert config.aws_region == "us-east-1"

    def test_table_name_property(self):
        """Test table name generation."""
        config = MemoryEvolutionConfig(
            environment="qa",
            project_name="aura",
        )
        assert config.table_name == "aura-memory-evolution-qa"

    def test_ttl_days_by_environment(self):
        """Test TTL varies by environment."""
        dev_config = MemoryEvolutionConfig(environment="dev")
        qa_config = MemoryEvolutionConfig(environment="qa")
        prod_config = MemoryEvolutionConfig(environment="prod")

        assert dev_config.ttl_days == 90
        assert qa_config.ttl_days == 180
        assert prod_config.ttl_days == 365

    def test_kms_key_alias(self):
        """Test KMS key alias generation."""
        config = MemoryEvolutionConfig(
            environment="prod",
            project_name="aura",
        )
        assert config.kms_key_alias == "alias/aura-memory-evolution-prod"

    def test_from_environment_default(self):
        """Test configuration from environment with defaults."""
        with patch.dict(os.environ, {}, clear=True):
            config = MemoryEvolutionConfig.from_environment()

        assert config.environment == "dev"
        assert config.project_name == "aura"

    def test_from_environment_custom(self):
        """Test configuration from custom environment variables."""
        env_vars = {
            "ENVIRONMENT": "production",
            "PROJECT_NAME": "custom-project",
            "AWS_DEFAULT_REGION": "eu-west-1",
            "MEMORY_EVOLUTION_CONSOLIDATION_THRESHOLD": "0.9",
            "MEMORY_EVOLUTION_PRUNE_THRESHOLD": "0.75",
            "MEMORY_EVOLUTION_ASYNC_ENABLED": "false",
            "MEMORY_EVOLUTION_METRICS_ENABLED": "true",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = MemoryEvolutionConfig.from_environment()

        assert config.environment == "production"
        assert config.project_name == "custom-project"
        assert config.aws_region == "eu-west-1"
        assert config.consolidation.similarity_threshold == 0.9
        assert config.prune.prune_threshold == 0.75
        assert config.async_config.async_enabled is False
        assert config.metrics.enabled is True

    def test_feature_flags_from_environment(self):
        """Test feature flags from environment variables."""
        env_vars = {
            "MEMORY_EVOLUTION_REINFORCE_ENABLED": "true",
            "MEMORY_EVOLUTION_ABSTRACT_ENABLED": "true",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = MemoryEvolutionConfig.from_environment()

        assert config.features.reinforce_enabled is True
        assert config.features.abstract_enabled is True


class TestConsolidationConfig:
    """Tests for ConsolidationConfig."""

    def test_default_values(self):
        """Test default consolidation configuration."""
        config = ConsolidationConfig()

        assert config.similarity_threshold == 0.85
        assert config.min_confidence == 0.7
        assert config.max_batch_size == 10
        assert config.default_merge_strategy == "weighted_average"
        assert config.auto_discovery_enabled is True
        assert config.discovery_interval_seconds == 300


class TestPruneConfig:
    """Tests for PruneConfig."""

    def test_default_values(self):
        """Test default prune configuration."""
        config = PruneConfig()

        assert config.prune_threshold == 0.8
        assert config.min_age_days == 7
        assert config.max_batch_size == 50
        assert config.min_access_protection == 3
        assert config.auto_prune_enabled is True
        assert config.soft_delete_days == 30


class TestAsyncConfig:
    """Tests for AsyncConfig."""

    def test_default_values(self):
        """Test default async configuration."""
        config = AsyncConfig()

        assert config.sync_confidence_threshold == 0.9
        assert config.visibility_timeout == 300
        assert config.max_retries == 3
        assert config.async_enabled is True


class TestMetricsConfig:
    """Tests for MetricsConfig."""

    def test_default_values(self):
        """Test default metrics configuration."""
        config = MetricsConfig()

        assert config.aggregation_interval_seconds == 60
        assert config.enabled is True
        assert config.namespace == "Aura/MemoryEvolution"
        assert "EvolutionGain" in config.core_metrics
        assert "StrategyReuseRate" in config.core_metrics
        assert len(config.core_metrics) == 5  # Only 5 core metrics


class TestStorageConfig:
    """Tests for StorageConfig."""

    def test_default_values(self):
        """Test default storage configuration."""
        config = StorageConfig()

        assert "{project_name}" in config.table_name_pattern
        assert config.ttl_days_dev == 90
        assert config.ttl_days_qa == 180
        assert config.ttl_days_prod == 365
        assert config.pitr_enabled is True
        assert config.streams_enabled is True


class TestSecurityConfig:
    """Tests for SecurityConfig."""

    def test_default_values(self):
        """Test default security configuration."""
        config = SecurityConfig()

        assert config.require_tenant_isolation is True
        assert config.require_domain_boundary is True
        assert config.encryption_enabled is True


class TestFeatureFlags:
    """Tests for FeatureFlags."""

    def test_default_phase_1a_enabled(self):
        """Test Phase 1a features are enabled by default."""
        flags = FeatureFlags()

        assert flags.consolidate_enabled is True
        assert flags.prune_enabled is True

    def test_later_phases_disabled(self):
        """Test later phase features are disabled by default."""
        flags = FeatureFlags()

        assert flags.reinforce_enabled is False
        assert flags.abstract_enabled is False
        assert flags.link_enabled is False
        assert flags.correct_enabled is False
        assert flags.rollback_enabled is False


class TestSingletonManagement:
    """Tests for singleton config management."""

    def test_get_returns_same_instance(self):
        """Test get returns the same instance."""
        config1 = get_memory_evolution_config()
        config2 = get_memory_evolution_config()

        assert config1 is config2

    def test_reset_clears_instance(self):
        """Test reset clears the singleton."""
        config1 = get_memory_evolution_config()
        reset_memory_evolution_config()
        config2 = get_memory_evolution_config()

        assert config1 is not config2

    def test_set_replaces_instance(self):
        """Test set replaces the singleton."""
        original = get_memory_evolution_config()
        new_config = MemoryEvolutionConfig(environment="custom")
        set_memory_evolution_config(new_config)
        retrieved = get_memory_evolution_config()

        assert retrieved is new_config
        assert retrieved is not original
        assert retrieved.environment == "custom"
