"""
Pytest fixtures for AI security service tests.
"""

import hashlib
from datetime import datetime, timezone

import pytest

from src.services.ai_security import (
    AccessType,
    AISecurityConfig,
    ModelSecurityPolicy,
    ModelWeightAccess,
    ModelWeightGuardian,
    SampleStatus,
    TrainingDataSentinel,
    TrainingSample,
    reset_ai_security_config,
    reset_model_guardian,
    reset_training_sentinel,
    set_ai_security_config,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all singletons before each test."""
    reset_ai_security_config()
    reset_model_guardian()
    reset_training_sentinel()
    yield
    reset_ai_security_config()
    reset_model_guardian()
    reset_training_sentinel()


@pytest.fixture
def test_config():
    """Create test configuration."""
    config = AISecurityConfig.for_testing()
    set_ai_security_config(config)
    return config


@pytest.fixture
def guardian(test_config):
    """Create model weight guardian."""
    return ModelWeightGuardian(test_config)


@pytest.fixture
def sentinel(test_config):
    """Create training data sentinel."""
    return TrainingDataSentinel(test_config)


@pytest.fixture
def sample_policy():
    """Create sample security policy."""
    return ModelSecurityPolicy(
        policy_id="policy-001",
        model_id="model-001",
        name="Standard Policy",
        allowed_identities=["user-001", "user-002", "service-account"],
        allowed_ips=["10.0.0.0/8", "192.168.1.1"],
        allowed_access_types=[AccessType.READ, AccessType.INFERENCE],
        max_daily_reads=100,
        export_blocked=True,
        alert_on_anomaly=True,
    )


@pytest.fixture
def sample_access():
    """Create sample model weight access."""
    return ModelWeightAccess(
        access_id="access-001",
        model_id="model-001",
        model_version="1.0.0",
        access_type=AccessType.READ,
        accessor_identity="user-001",
        accessor_ip="192.168.1.1",
        timestamp=datetime.now(timezone.utc),
        bytes_accessed=1024,
        file_paths=["model/weights.bin"],
        approved=True,
    )


@pytest.fixture
def sample_training_samples():
    """Create sample training samples."""
    samples = []
    for i in range(10):
        content = f"This is sample content number {i} for training."
        samples.append(
            TrainingSample(
                sample_id=f"sample-{i:03d}",
                content=content,
                label="positive" if i % 2 == 0 else "negative",
                source="dataset-v1",
                provenance_hash=hashlib.sha256(content.encode()).hexdigest(),
                status=SampleStatus.PENDING_REVIEW,
            )
        )
    return samples


@pytest.fixture
def sample_with_pii():
    """Create sample with PII."""
    return TrainingSample(
        sample_id="sample-pii",
        content="Contact john.doe@example.com or call 555-123-4567 for help.",
        label="positive",
        source="web-scrape",
    )


@pytest.fixture
def duplicate_samples():
    """Create duplicate samples."""
    content = "This is duplicate content."
    return [
        TrainingSample(
            sample_id=f"dup-{i}",
            content=content,
            label="positive",
            source="dataset-v1",
        )
        for i in range(3)
    ]
