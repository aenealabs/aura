"""Pytest fixtures for memory evolution service tests."""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.memory_evolution import (
    MemoryEvolutionConfig,
    MemoryRefiner,
    RefineAction,
    RefineOperation,
    reset_memory_evolution_config,
    reset_memory_refiner,
    set_memory_evolution_config,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singletons before each test."""
    reset_memory_evolution_config()
    reset_memory_refiner()
    yield
    reset_memory_evolution_config()
    reset_memory_refiner()


@pytest.fixture
def test_config() -> MemoryEvolutionConfig:
    """Create a test configuration."""
    config = MemoryEvolutionConfig(
        environment="test",
        project_name="aura-test",
        aws_region="us-east-1",
    )
    # Enable all Phase 1a features
    config.features.consolidate_enabled = True
    config.features.prune_enabled = True
    # Disable later phases
    config.features.reinforce_enabled = False
    config.features.abstract_enabled = False
    set_memory_evolution_config(config)
    return config


@pytest.fixture
def mock_memory_store() -> MagicMock:
    """Create a mock memory store."""
    store = MagicMock()

    # Mock async methods
    store.get_memory = AsyncMock(
        return_value={
            "memory_id": "mem-1",
            "content": "Test memory content",
            "tenant_id": "tenant-123",
            "security_domain": "development",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    store.get_memories = AsyncMock(
        return_value=[
            {
                "memory_id": "mem-1",
                "content": "Test memory 1",
                "tenant_id": "tenant-123",
                "security_domain": "development",
            },
            {
                "memory_id": "mem-2",
                "content": "Test memory 2",
                "tenant_id": "tenant-123",
                "security_domain": "development",
            },
        ]
    )

    store.merge_memories = AsyncMock(
        return_value={
            "memory_id": "mem-merged",
            "content": "Merged memory content",
            "tenant_id": "tenant-123",
            "security_domain": "development",
        }
    )

    store.soft_delete_memory = AsyncMock(return_value=True)

    store.get_memory_similarity = AsyncMock(return_value=0.92)

    store.find_similar_memories = AsyncMock(
        return_value=[
            ("mem-1", "mem-2", 0.95),
            ("mem-3", "mem-4", 0.88),
        ]
    )

    store.get_prune_candidates = AsyncMock(
        return_value=[
            {
                "memory_id": "mem-old-1",
                "access_count": 0,
                "value_score": 0.1,
                "age_days": 45,
            },
            {
                "memory_id": "mem-old-2",
                "access_count": 1,
                "value_score": 0.2,
                "age_days": 60,
            },
        ]
    )

    return store


@pytest.fixture
def mock_record_store() -> MagicMock:
    """Create a mock evolution record store."""
    store = MagicMock()
    store.save_record = AsyncMock()
    store.get_recent_records = AsyncMock(return_value=[])
    return store


@pytest.fixture
def mock_metrics_publisher() -> MagicMock:
    """Create a mock metrics publisher."""
    publisher = MagicMock()
    publisher.publish_refine_result = AsyncMock()
    return publisher


@pytest.fixture
def memory_refiner(
    mock_memory_store: MagicMock,
    mock_record_store: MagicMock,
    mock_metrics_publisher: MagicMock,
    test_config: MemoryEvolutionConfig,
) -> MemoryRefiner:
    """Create a MemoryRefiner with mock dependencies."""
    return MemoryRefiner(
        memory_store=mock_memory_store,
        record_store=mock_record_store,
        metrics_publisher=mock_metrics_publisher,
        config=test_config,
    )


@pytest.fixture
def consolidate_action() -> RefineAction:
    """Create a sample CONSOLIDATE action."""
    return RefineAction(
        operation=RefineOperation.CONSOLIDATE,
        target_memory_ids=["mem-1", "mem-2"],
        reasoning="Similar debugging patterns for Python exceptions",
        confidence=0.9,
        tenant_id="tenant-123",
        security_domain="development",
        agent_id="coder-agent-1",
        metadata={"task_id": "task-456"},
    )


@pytest.fixture
def prune_action() -> RefineAction:
    """Create a sample PRUNE action."""
    return RefineAction(
        operation=RefineOperation.PRUNE,
        target_memory_ids=["mem-old-1", "mem-old-2"],
        reasoning="Low value memories not accessed in 30+ days",
        confidence=0.85,
        tenant_id="tenant-123",
        security_domain="development",
        agent_id="system",
        metadata={"auto_prune": True},
    )


@pytest.fixture
def sample_memories() -> list[dict[str, Any]]:
    """Create sample memory data."""
    return [
        {
            "memory_id": "mem-1",
            "content": "Debugging Python exception handling patterns",
            "embedding": [0.1] * 768,
            "tenant_id": "tenant-123",
            "security_domain": "development",
            "access_count": 5,
            "value_score": 0.8,
            "created_at": "2024-01-01T00:00:00Z",
        },
        {
            "memory_id": "mem-2",
            "content": "Exception handling best practices in Python",
            "embedding": [0.12] * 768,
            "tenant_id": "tenant-123",
            "security_domain": "development",
            "access_count": 3,
            "value_score": 0.7,
            "created_at": "2024-01-02T00:00:00Z",
        },
        {
            "memory_id": "mem-3",
            "content": "Old unused memory about deprecated feature",
            "embedding": [0.5] * 768,
            "tenant_id": "tenant-123",
            "security_domain": "development",
            "access_count": 0,
            "value_score": 0.1,
            "created_at": "2023-06-01T00:00:00Z",
        },
    ]
