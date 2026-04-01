"""
Tests for Air-Gap Deployment Services.

Tests egress validation, model verification, and inference audit logging.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.airgap.egress_validator import (
    EgressValidationResult,
    EgressValidator,
    EgressViolation,
    EgressViolationType,
    validate_air_gap_mode,
)
from src.services.airgap.inference_audit import (
    InferenceAuditEvent,
    InferenceAuditLogger,
    InferenceEventType,
    get_inference_audit_logger,
)
from src.services.airgap.model_verifier import (
    FileChecksum,
    ModelVerificationResult,
    ModelVerifier,
    verify_model_checksums,
)


class TestEgressViolation:
    """Tests for EgressViolation dataclass."""

    def test_violation_creation(self):
        """Test creating an egress violation."""
        violation = EgressViolation(
            violation_type=EgressViolationType.DNS_RESOLUTION,
            destination="google.com",
            port=443,
            blocked=False,
        )

        assert violation.violation_type == EgressViolationType.DNS_RESOLUTION
        assert violation.destination == "google.com"
        assert violation.port == 443
        assert violation.blocked is False

    def test_violation_to_dict(self):
        """Test violation serialization."""
        violation = EgressViolation(
            violation_type=EgressViolationType.TCP_CONNECTION,
            destination="api.openai.com",
            port=443,
            blocked=True,
            details="Connection refused",
        )

        data = violation.to_dict()

        assert data["type"] == "tcp_connection"
        assert data["destination"] == "api.openai.com"
        assert data["port"] == 443
        assert data["blocked"] is True
        assert "timestamp" in data


class TestEgressValidationResult:
    """Tests for EgressValidationResult dataclass."""

    def test_compliant_result(self):
        """Test compliant result (no violations)."""
        result = EgressValidationResult(
            is_air_gapped=True,
            violations=[],
            tests_passed=10,
            tests_failed=0,
        )

        assert result.is_compliant is True

    def test_non_compliant_result(self):
        """Test non-compliant result (has violations)."""
        violation = EgressViolation(
            violation_type=EgressViolationType.DNS_RESOLUTION,
            destination="external.com",
            blocked=False,
        )

        result = EgressValidationResult(
            is_air_gapped=True,
            violations=[violation],
            tests_passed=9,
            tests_failed=1,
        )

        assert result.is_compliant is False

    def test_non_airgap_not_compliant(self):
        """Test non-air-gap mode is not compliant."""
        result = EgressValidationResult(
            is_air_gapped=False,
            violations=[],
        )

        assert result.is_compliant is False


class TestEgressValidator:
    """Tests for EgressValidator."""

    def test_validator_creation(self):
        """Test creating egress validator."""
        validator = EgressValidator(timeout_seconds=2.0)
        assert validator._timeout == 2.0

    @patch.dict(os.environ, {"AURA_DEPLOYMENT_MODE": ""})
    def test_not_air_gap_mode(self):
        """Test validation skipped when not in air-gap mode."""
        validator = EgressValidator()
        result = validator.validate_sync()

        assert result.is_air_gapped is False
        assert len(result.violations) == 0

    @patch.dict(os.environ, {"AURA_DEPLOYMENT_MODE": "air_gapped"})
    @patch("socket.gethostbyname_ex")
    @patch("socket.socket")
    def test_air_gap_mode_blocked(self, mock_socket, mock_dns):
        """Test validation passes when all egress blocked."""
        # Mock DNS failure
        import socket

        mock_dns.side_effect = socket.gaierror("Name or service not known")

        # Mock socket connection failure
        mock_sock_instance = MagicMock()
        mock_sock_instance.connect_ex.return_value = 111  # Connection refused
        mock_socket.return_value = mock_sock_instance

        validator = EgressValidator(timeout_seconds=0.1)
        result = validator.validate_sync()

        assert result.is_air_gapped is True
        assert len(result.violations) == 0
        assert result.is_compliant is True

    @patch.dict(os.environ, {"AURA_DEPLOYMENT_MODE": "air_gapped"})
    @patch("socket.gethostbyname_ex")
    def test_air_gap_mode_violation(self, mock_dns):
        """Test violation detected when DNS resolves."""
        # Mock DNS success (violation)
        mock_dns.return_value = ("google.com", [], ["142.250.80.46"])

        validator = EgressValidator(
            timeout_seconds=0.1,
            test_endpoints=[("google.com", 443)],
        )
        result = validator.validate_sync()

        assert result.is_air_gapped is True
        assert len(result.violations) >= 1
        assert result.is_compliant is False


class TestValidateAirGapMode:
    """Tests for validate_air_gap_mode convenience function."""

    @patch.dict(os.environ, {"AURA_DEPLOYMENT_MODE": ""})
    def test_not_air_gap(self):
        """Test returns result when not in air-gap mode."""
        result = validate_air_gap_mode()
        assert result.is_air_gapped is False


class TestFileChecksum:
    """Tests for FileChecksum dataclass."""

    def test_checksum_valid(self):
        """Test valid checksum."""
        checksum = FileChecksum(
            file_path="/models/test/config.json",
            expected_hash="abc123",
            actual_hash="abc123",
            verified=True,
        )

        assert checksum.is_valid is True

    def test_checksum_invalid(self):
        """Test invalid checksum."""
        checksum = FileChecksum(
            file_path="/models/test/config.json",
            expected_hash="abc123",
            actual_hash="def456",
            verified=True,
        )

        assert checksum.is_valid is False


class TestModelVerificationResult:
    """Tests for ModelVerificationResult dataclass."""

    def test_result_to_dict(self):
        """Test result serialization."""
        result = ModelVerificationResult(
            model_name="test-model",
            model_path="/models/test-model",
            is_valid=True,
            files_verified=5,
            total_size_bytes=1024 * 1024 * 100,  # 100MB
        )

        data = result.to_dict()

        assert data["model_name"] == "test-model"
        assert data["is_valid"] is True
        assert data["files_verified"] == 5
        assert data["total_size_mb"] == 100.0


class TestModelVerifier:
    """Tests for ModelVerifier."""

    @pytest.fixture
    def temp_model_dir(self):
        """Create temporary model directory with test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir) / "test-model"
            model_dir.mkdir()

            # Create test files
            (model_dir / "config.json").write_text('{"model": "test"}')
            (model_dir / "tokenizer.json").write_text('{"version": "1.0"}')
            (model_dir / "model.safetensors").write_bytes(b"fake model weights")

            yield model_dir

    def test_verify_model_exists(self, temp_model_dir):
        """Test verifying existing model."""
        verifier = ModelVerifier(models_dir=str(temp_model_dir.parent))
        result = verifier.verify_model("test-model")

        assert result.model_name == "test-model"
        assert result.files_verified >= 3
        assert result.is_valid is True

    def test_verify_model_not_found(self):
        """Test verifying non-existent model."""
        with tempfile.TemporaryDirectory() as tmpdir:
            verifier = ModelVerifier(models_dir=tmpdir)
            result = verifier.verify_model("nonexistent-model")

            assert result.is_valid is False
            assert "not found" in result.errors[0]

    def test_generate_checksums(self, temp_model_dir):
        """Test generating checksums for model."""
        verifier = ModelVerifier(models_dir=str(temp_model_dir.parent))
        checksums = verifier.generate_checksums("test-model")

        assert "config.json" in checksums
        assert "tokenizer.json" in checksums
        assert len(checksums["config.json"]) == 64  # SHA-256 hex

    def test_load_checksums_file(self, temp_model_dir):
        """Test loading checksums from file."""
        # Create checksum file
        checksum_file = temp_model_dir.parent / "SHA256SUMS"
        checksum_file.write_text(
            "abc123def456  test-model/config.json\n"
            "def456abc123  test-model/tokenizer.json\n"
        )

        verifier = ModelVerifier(
            models_dir=str(temp_model_dir.parent),
            checksum_file=str(checksum_file),
        )

        assert "test-model" in verifier._known_checksums
        assert "config.json" in verifier._known_checksums["test-model"]


class TestVerifyModelChecksums:
    """Tests for verify_model_checksums convenience function."""

    def test_verify_nonexistent(self):
        """Test verifying non-existent model."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"AURA_MODELS_DIR": tmpdir}):
                result = verify_model_checksums("nonexistent")
                assert result.is_valid is False


class TestInferenceAuditEvent:
    """Tests for InferenceAuditEvent dataclass."""

    def test_event_creation(self):
        """Test creating audit event."""
        event = InferenceAuditEvent(
            event_type=InferenceEventType.INFERENCE_REQUEST,
            request_id="req-123",
            user_id="user-456",
            model_name="mistral-7b",
            prompt_length=100,
        )

        assert event.event_type == InferenceEventType.INFERENCE_REQUEST
        assert event.request_id == "req-123"
        assert event.user_id == "user-456"
        assert event.model_name == "mistral-7b"

    def test_event_to_dict(self):
        """Test event serialization."""
        event = InferenceAuditEvent(
            event_type=InferenceEventType.INFERENCE_RESPONSE,
            request_id="req-123",
            input_tokens=50,
            output_tokens=100,
            latency_ms=250.5,
        )

        data = event.to_dict()

        assert data["event_type"] == "inference_response"
        assert data["input_tokens"] == 50
        assert data["output_tokens"] == 100
        assert data["latency_ms"] == 250.5

    def test_event_to_json(self):
        """Test event JSON serialization."""
        event = InferenceAuditEvent(
            event_type=InferenceEventType.INFERENCE_REQUEST,
            request_id="req-123",
        )

        json_str = event.to_json()
        data = json.loads(json_str)

        assert data["event_type"] == "inference_request"
        assert data["request_id"] == "req-123"


class TestInferenceAuditLogger:
    """Tests for InferenceAuditLogger."""

    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_logger_creation(self, temp_log_dir):
        """Test creating audit logger."""
        logger = InferenceAuditLogger(
            log_dir=temp_log_dir,
            log_to_file=True,
            log_to_syslog=False,
        )

        assert logger._log_dir == Path(temp_log_dir)
        logger.shutdown()

    def test_log_inference_request(self, temp_log_dir):
        """Test logging inference request."""
        logger = InferenceAuditLogger(
            log_dir=temp_log_dir,
            log_to_file=True,
            log_to_syslog=False,
        )

        event = logger.log_inference_request(
            request_id="req-123",
            model_name="mistral-7b",
            prompt="Hello, world!",
            user_id="user-456",
        )

        assert event.event_type == InferenceEventType.INFERENCE_REQUEST
        assert event.request_id == "req-123"
        assert event.model_name == "mistral-7b"
        assert event.prompt_length == 13

        logger.shutdown()

    def test_log_inference_response(self, temp_log_dir):
        """Test logging inference response."""
        logger = InferenceAuditLogger(
            log_dir=temp_log_dir,
            log_to_file=True,
            log_to_syslog=False,
        )

        event = logger.log_inference_response(
            request_id="req-123",
            model_name="mistral-7b",
            response="Hello! How can I help?",
            input_tokens=5,
            output_tokens=7,
            latency_ms=150.0,
        )

        assert event.event_type == InferenceEventType.INFERENCE_RESPONSE
        assert event.input_tokens == 5
        assert event.output_tokens == 7
        assert event.total_tokens == 12
        assert event.success is True

        logger.shutdown()

    def test_log_inference_error(self, temp_log_dir):
        """Test logging inference error."""
        logger = InferenceAuditLogger(
            log_dir=temp_log_dir,
            log_to_file=True,
            log_to_syslog=False,
        )

        event = logger.log_inference_error(
            request_id="req-123",
            model_name="mistral-7b",
            error_code="MODEL_OVERLOADED",
            error_message="Model queue full",
        )

        assert event.event_type == InferenceEventType.INFERENCE_ERROR
        assert event.success is False
        assert event.error_code == "MODEL_OVERLOADED"

        logger.shutdown()

    def test_log_access_denied(self, temp_log_dir):
        """Test logging access denied event."""
        logger = InferenceAuditLogger(
            log_dir=temp_log_dir,
            log_to_file=True,
            log_to_syslog=False,
        )

        event = logger.log_access_denied(
            request_id="req-123",
            user_id="user-456",
            model_name="gpt-4",
            reason="Model not licensed",
        )

        assert event.event_type == InferenceEventType.ACCESS_DENIED
        assert event.success is False
        assert event.error_code == "ACCESS_DENIED"

        logger.shutdown()

    def test_hash_content(self, temp_log_dir):
        """Test content hashing for privacy."""
        audit_logger = InferenceAuditLogger(
            log_dir=temp_log_dir,
            hash_content=True,
        )

        hash1 = audit_logger._compute_hash("Hello, world!")
        hash2 = audit_logger._compute_hash("Hello, world!")
        hash3 = audit_logger._compute_hash("Different content")

        assert hash1 == hash2  # Same content = same hash
        assert hash1 != hash3  # Different content = different hash
        assert len(hash1) == 32  # Truncated hash

        audit_logger.shutdown()

    def test_flush_events(self, temp_log_dir):
        """Test flushing events to log."""
        logger = InferenceAuditLogger(
            log_dir=temp_log_dir,
            log_to_file=True,
            log_to_syslog=False,
        )

        # Log some events
        for i in range(5):
            logger.log_inference_request(
                request_id=f"req-{i}",
                model_name="test-model",
                prompt=f"Test prompt {i}",
            )

        # Flush
        logger.flush()
        logger.shutdown()

        # Check log file exists
        log_file = Path(temp_log_dir) / "inference_audit.jsonl"
        assert log_file.exists()


class TestGetInferenceAuditLogger:
    """Tests for get_inference_audit_logger convenience function."""

    def test_get_logger_returns_instance(self):
        """Test getting global logger instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"AURA_AUDIT_LOG_DIR": tmpdir}):
                # Reset global logger
                import src.services.airgap.inference_audit as audit_module

                audit_module._audit_logger = None

                audit_logger = get_inference_audit_logger()
                assert isinstance(audit_logger, InferenceAuditLogger)

                # Cleanup
                audit_logger.shutdown()
                audit_module._audit_logger = None
