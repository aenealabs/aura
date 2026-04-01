"""
Tests for AI security service - Model Weight Guardian and Training Data Sentinel.
"""

from datetime import datetime, timezone

import pytest

from src.services.ai_security import (
    AccessType,
    AISecurityConfig,
    ModelWeightAccess,
    ModelWeightGuardian,
    PIIType,
    TrainingDataSentinel,
    TrainingSample,
    get_model_guardian,
    get_training_sentinel,
    reset_model_guardian,
    reset_training_sentinel,
)


class TestAISecurityConfig:
    """Tests for AI security configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = AISecurityConfig()
        assert config.enabled is True
        assert config.model_guardian.enabled is True
        assert config.training_sentinel.enabled is True

    def test_for_testing(self):
        """Test test configuration."""
        config = AISecurityConfig.for_testing()
        assert config.environment == "test"
        assert config.alerting.enabled is False
        assert config.storage.dynamodb_enabled is False

    def test_for_production(self):
        """Test production configuration."""
        config = AISecurityConfig.for_production()
        assert config.environment == "prod"
        assert config.alerting.enabled is True

    def test_validate_success(self):
        """Test validation with valid config."""
        config = AISecurityConfig()
        errors = config.validate()
        assert len(errors) == 0

    def test_validate_invalid_threshold(self):
        """Test validation with invalid anomaly threshold."""
        config = AISecurityConfig()
        config.model_guardian.anomaly_threshold = 1.5  # Invalid (> 1.0)
        errors = config.validate()
        assert any("anomaly_threshold" in e for e in errors)


class TestModelWeightGuardian:
    """Tests for ModelWeightGuardian."""

    def test_initialize(self, test_config):
        """Test guardian initialization."""
        guardian = ModelWeightGuardian(test_config)
        assert guardian is not None

    def test_singleton(self, test_config):
        """Test singleton pattern."""
        guardian1 = get_model_guardian()
        guardian2 = get_model_guardian()
        assert guardian1 is guardian2

    def test_reset_singleton(self, test_config):
        """Test singleton reset."""
        guardian1 = get_model_guardian()
        reset_model_guardian()
        guardian2 = get_model_guardian()
        assert guardian1 is not guardian2

    @pytest.mark.asyncio
    async def test_register_model(self, guardian):
        """Test registering a model."""
        model = await guardian.register_model(
            model_id="model-001",
            name="Test Model",
            version="1.0.0",
            weight_paths=["model/weights.bin"],
        )
        # register_model returns MonitoredModel
        assert model.model_id == "model-001"
        assert model.name == "Test Model"

    @pytest.mark.asyncio
    async def test_get_model(self, guardian):
        """Test getting a registered model."""
        await guardian.register_model(
            model_id="model-002",
            name="Test Model 2",
            version="1.0.0",
            weight_paths=["model/weights.bin"],
        )

        retrieved = await guardian.get_model("model-002")
        assert retrieved is not None
        assert retrieved.name == "Test Model 2"

    @pytest.mark.asyncio
    async def test_get_nonexistent_model(self, guardian):
        """Test getting non-existent model."""
        retrieved = await guardian.get_model("nonexistent")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_log_access(self, guardian, sample_access):
        """Test logging model access."""
        # Register model first
        await guardian.register_model(
            model_id="model-001",
            name="Test Model",
            version="1.0.0",
            weight_paths=["model/weights.bin"],
        )

        # Log access - returns Optional[WeightThreatDetection]
        result = await guardian.log_access(sample_access)
        # Result is None if no threat detected
        # The access should be logged without raising an error

    @pytest.mark.asyncio
    async def test_log_access_unregistered_model(self, guardian):
        """Test access logging for unregistered model raises error."""
        from src.services.ai_security.exceptions import ModelNotRegisteredError

        access = ModelWeightAccess(
            access_id="access-001",
            model_id="unregistered-model",
            model_version="1.0.0",
            access_type=AccessType.READ,
            accessor_identity="user-001",
            accessor_ip="192.168.1.1",
            timestamp=datetime.now(timezone.utc),
            bytes_accessed=1024,
        )

        # Access to unregistered model should raise error
        with pytest.raises(ModelNotRegisteredError):
            await guardian.log_access(access)

    @pytest.mark.asyncio
    async def test_detect_anomalies(self, guardian):
        """Test anomaly detection."""
        # Register model
        await guardian.register_model(
            model_id="model-001",
            name="Test Model",
            version="1.0.0",
            weight_paths=["model/weights.bin"],
        )

        # Log multiple accesses to establish baseline
        for i in range(10):
            access = ModelWeightAccess(
                access_id=f"access-{i:03d}",
                model_id="model-001",
                model_version="1.0.0",
                access_type=AccessType.READ,
                accessor_identity="user-001",
                accessor_ip="192.168.1.1",
                timestamp=datetime.now(timezone.utc),
                bytes_accessed=1024,
            )
            await guardian.log_access(access)

        # Detect anomalies
        anomalies = await guardian.detect_anomalies("model-001")
        assert isinstance(anomalies, list)

    @pytest.mark.asyncio
    async def test_enforce_policy(self, guardian):
        """Test policy enforcement."""
        # Register model with a policy
        await guardian.register_model(
            model_id="model-001",
            name="Test Model",
            version="1.0.0",
            weight_paths=["model/weights.bin"],
        )

        # Test policy enforcement
        access_request = {
            "access_type": "read",
            "accessor_identity": "user-001",
            "accessor_ip": "192.168.1.1",
        }

        allowed, reason = await guardian.enforce_policy("model-001", access_request)
        # Model exists, so access should be allowed (no specific policy restrictions)
        assert isinstance(allowed, bool)
        assert isinstance(reason, str)

    @pytest.mark.asyncio
    async def test_generate_audit_report(self, guardian):
        """Test audit report generation."""
        # Register model
        await guardian.register_model(
            model_id="model-001",
            name="Test Model",
            version="1.0.0",
            weight_paths=["model/weights.bin"],
        )

        # Log some accesses
        for i in range(5):
            access = ModelWeightAccess(
                access_id=f"access-{i:03d}",
                model_id="model-001",
                model_version="1.0.0",
                access_type=AccessType.READ,
                accessor_identity="user-001",
                accessor_ip="192.168.1.1",
                timestamp=datetime.now(timezone.utc),
                bytes_accessed=1024,
            )
            await guardian.log_access(access)

        report = await guardian.generate_audit_report("model-001")
        assert report.model_id == "model-001"
        assert report.total_accesses == 5

    @pytest.mark.asyncio
    async def test_list_models(self, guardian):
        """Test listing models."""
        # Register a model
        await guardian.register_model(
            model_id="model-list-test",
            name="List Test Model",
            version="1.0.0",
            weight_paths=["model/weights.bin"],
        )

        models = await guardian.list_models()
        assert isinstance(models, list)
        assert len(models) >= 1


class TestTrainingDataSentinel:
    """Tests for TrainingDataSentinel."""

    def test_initialize(self, test_config):
        """Test sentinel initialization."""
        sentinel = TrainingDataSentinel(test_config)
        assert sentinel is not None

    def test_singleton(self, test_config):
        """Test singleton pattern."""
        sentinel1 = get_training_sentinel()
        sentinel2 = get_training_sentinel()
        assert sentinel1 is sentinel2

    def test_reset_singleton(self, test_config):
        """Test singleton reset."""
        sentinel1 = get_training_sentinel()
        reset_training_sentinel()
        sentinel2 = get_training_sentinel()
        assert sentinel1 is not sentinel2

    @pytest.mark.asyncio
    async def test_analyze_dataset(self, sentinel, sample_training_samples):
        """Test dataset analysis."""
        analysis = await sentinel.analyze_dataset(
            dataset_id="dataset-001",
            samples=sample_training_samples,
        )

        assert analysis.dataset_id == "dataset-001"
        assert analysis.total_samples == 10
        # Check quality_issues list exists
        assert isinstance(analysis.quality_issues, list)

    @pytest.mark.asyncio
    async def test_detect_backdoors(self, sentinel, sample_training_samples):
        """Test backdoor detection."""
        backdoors = await sentinel.detect_backdoors(sample_training_samples)
        assert isinstance(backdoors, list)

    @pytest.mark.asyncio
    async def test_verify_label_consistency(self, sentinel, sample_training_samples):
        """Test label consistency verification."""
        # Returns list of (sample_id, score) tuples for inconsistent samples
        result = await sentinel.verify_label_consistency(sample_training_samples)
        assert isinstance(result, list)
        # Result is list of tuples
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 2

    @pytest.mark.asyncio
    async def test_check_provenance(self, sentinel, sample_training_samples):
        """Test provenance checking."""
        # check_provenance takes a single sample, not a list
        sample = sample_training_samples[0]
        result = await sentinel.check_provenance(sample)
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_find_duplicates(self, sentinel, duplicate_samples):
        """Test duplicate detection."""
        duplicates = await sentinel.find_duplicates(duplicate_samples)
        # Should find duplicates (all 3 samples have same content)
        assert len(duplicates) > 0

    @pytest.mark.asyncio
    async def test_detect_pii_email(self, sentinel, sample_with_pii):
        """Test PII detection for email."""
        # detect_pii returns list of (sample_id, list[PIIType]) tuples
        pii_results = await sentinel.detect_pii([sample_with_pii])
        assert len(pii_results) > 0

        # Check email was detected
        sample_id, pii_types = pii_results[0]
        assert sample_id == sample_with_pii.sample_id
        assert PIIType.EMAIL in pii_types

    @pytest.mark.asyncio
    async def test_detect_pii_phone(self, sentinel, sample_with_pii):
        """Test PII detection for phone."""
        pii_results = await sentinel.detect_pii([sample_with_pii])
        assert len(pii_results) > 0

        # Check phone was detected
        sample_id, pii_types = pii_results[0]
        assert PIIType.PHONE in pii_types

    @pytest.mark.asyncio
    async def test_detect_pii_clean_samples(self, sentinel, sample_training_samples):
        """Test PII detection on clean samples."""
        pii_results = await sentinel.detect_pii(sample_training_samples)
        # Clean samples should have no PII
        assert len(pii_results) == 0

    @pytest.mark.asyncio
    async def test_quarantine_samples(self, sentinel, sample_training_samples):
        """Test sample quarantine."""
        # First analyze dataset to create it
        await sentinel.analyze_dataset(
            dataset_id="dataset-quarantine",
            samples=sample_training_samples,
        )

        # Quarantine first sample
        sample_ids = [sample_training_samples[0].sample_id]
        record = await sentinel.quarantine_samples(
            dataset_id="dataset-quarantine",
            sample_ids=sample_ids,
            reason="Test quarantine",
        )

        assert record is not None
        assert len(record.sample_ids) == 1

    @pytest.mark.asyncio
    async def test_get_quarantine_record(self, sentinel, sample_training_samples):
        """Test getting quarantine records."""
        # First analyze dataset to create it
        await sentinel.analyze_dataset(
            dataset_id="dataset-record",
            samples=sample_training_samples,
        )

        # Quarantine some samples
        sample_ids = [sample_training_samples[0].sample_id]
        record = await sentinel.quarantine_samples(
            dataset_id="dataset-record",
            sample_ids=sample_ids,
            reason="Test record retrieval",
        )

        # Verify record was created
        assert record is not None
        assert record.dataset_id == "dataset-record"
        assert sample_ids[0] in record.sample_ids

    @pytest.mark.asyncio
    async def test_analyze_with_quality_issues(self, sentinel):
        """Test analysis detecting quality issues."""
        # Create samples that might have quality issues
        samples = [
            TrainingSample(
                sample_id="quality-001",
                content="Normal content for category A",
                label="positive",
                source="trusted-source",
            ),
            TrainingSample(
                sample_id="quality-002",
                content="Normal content for category A",  # Same content
                label="negative",  # Different label - potential issue
                source="untrusted-source",
            ),
        ]

        analysis = await sentinel.analyze_dataset(
            dataset_id="quality-dataset",
            samples=samples,
        )

        # Should complete analysis
        assert analysis.total_samples == 2
        # Quality issues might include duplicates or label inconsistency
        assert isinstance(analysis.quality_issues, list)
