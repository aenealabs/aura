"""
Project Aura - Logging Configuration Tests

Tests for structured logging configuration:
- JSON formatter
- Development formatter
- Correlation ID management
- Sensitive data redaction

Issue: #45 - Observability: Standardize logging levels and format
"""

import json
import logging
import platform
from unittest.mock import patch

import pytest

# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestCorrelationId:
    """Tests for correlation ID management."""

    def test_get_correlation_id_generates_uuid(self):
        """Test that get_correlation_id generates a UUID if not set."""
        from src.config.logging_config import clear_correlation_id, get_correlation_id

        clear_correlation_id()
        cid = get_correlation_id()

        assert cid is not None
        assert len(cid) == 36  # UUID format

    def test_set_and_get_correlation_id(self):
        """Test setting and getting correlation ID."""
        from src.config.logging_config import (
            clear_correlation_id,
            get_correlation_id,
            set_correlation_id,
        )

        clear_correlation_id()
        set_correlation_id("test-correlation-123")

        assert get_correlation_id() == "test-correlation-123"

    def test_clear_correlation_id(self):
        """Test clearing correlation ID generates new one on next get."""
        from src.config.logging_config import (
            clear_correlation_id,
            get_correlation_id,
            set_correlation_id,
        )

        set_correlation_id("original-id")
        clear_correlation_id()
        new_id = get_correlation_id()

        assert new_id != "original-id"


class TestCloudWatchJSONFormatter:
    """Tests for JSON formatter."""

    @pytest.fixture
    def json_formatter(self):
        """Create JSON formatter."""
        from src.config.logging_config import CloudWatchJSONFormatter

        return CloudWatchJSONFormatter()

    @pytest.fixture
    def log_record(self):
        """Create a log record."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        return record

    def test_format_returns_valid_json(self, json_formatter, log_record):
        """Test that formatter returns valid JSON."""
        output = json_formatter.format(log_record)
        parsed = json.loads(output)

        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert parsed["message"] == "Test message"
        assert "timestamp" in parsed
        assert "correlation_id" in parsed

    def test_format_includes_extra_fields(self, json_formatter, log_record):
        """Test that extra fields are included."""
        log_record.operation = "test_op"
        log_record.duration_ms = 150

        output = json_formatter.format(log_record)
        parsed = json.loads(output)

        assert parsed["extra"]["operation"] == "test_op"
        assert parsed["extra"]["duration_ms"] == 150

    def test_format_redacts_sensitive_fields(self, json_formatter, log_record):
        """Test that sensitive fields are redacted."""
        log_record.password = "secret123"
        log_record.api_key = "sk-xxx"
        log_record.username = "john"

        output = json_formatter.format(log_record)
        parsed = json.loads(output)

        assert parsed["extra"]["password"] == "[REDACTED]"
        assert parsed["extra"]["api_key"] == "[REDACTED]"
        assert parsed["extra"]["username"] == "john"

    def test_format_includes_location_for_errors(self, json_formatter):
        """Test that location is included for ERROR level."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Error message",
            args=(),
            exc_info=None,
        )

        output = json_formatter.format(record)
        parsed = json.loads(output)

        assert "location" in parsed
        assert parsed["location"]["line"] == 42

    def test_format_does_not_include_location_for_info(
        self, json_formatter, log_record
    ):
        """Test that location is not included for INFO level."""
        output = json_formatter.format(log_record)
        parsed = json.loads(output)

        assert "location" not in parsed


class TestDevelopmentFormatter:
    """Tests for development formatter."""

    @pytest.fixture
    def dev_formatter(self):
        """Create development formatter without colors."""
        from src.config.logging_config import DevelopmentFormatter

        return DevelopmentFormatter(use_color=False)

    @pytest.fixture
    def log_record(self):
        """Create a log record."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        return record

    def test_format_includes_timestamp(self, dev_formatter, log_record):
        """Test that output includes timestamp."""
        output = dev_formatter.format(log_record)

        # Should start with timestamp in brackets
        assert output.startswith("[")
        assert "]" in output

    def test_format_includes_level(self, dev_formatter, log_record):
        """Test that output includes log level."""
        output = dev_formatter.format(log_record)

        assert "INFO" in output

    def test_format_includes_correlation_id(self, dev_formatter, log_record):
        """Test that output includes correlation ID."""
        output = dev_formatter.format(log_record)

        assert "[cid:" in output

    def test_format_includes_extra_fields(self, dev_formatter, log_record):
        """Test that extra fields are included."""
        log_record.operation = "test_op"
        log_record.duration_ms = 150

        output = dev_formatter.format(log_record)

        assert "operation=test_op" in output
        assert "duration_ms=150" in output


class TestStructuredLogger:
    """Tests for structured logger wrapper."""

    @pytest.fixture
    def structured_logger(self):
        """Create structured logger."""
        from src.config.logging_config import StructuredLogger

        logger = logging.getLogger("test.structured")
        return StructuredLogger(logger)

    def test_info_with_kwargs(self, structured_logger, caplog):
        """Test info logging with keyword arguments."""
        with caplog.at_level(logging.INFO):
            structured_logger.info("Test message", key1="value1", key2=42)

        assert "Test message" in caplog.text

    def test_error_with_exc_info(self, structured_logger, caplog):
        """Test error logging with exception info."""
        with caplog.at_level(logging.ERROR):
            try:
                raise ValueError("Test error")
            except ValueError:
                structured_logger.error("Error occurred", exc_info=True)

        assert "Error occurred" in caplog.text

    def test_all_log_levels(self, structured_logger, caplog):
        """Test all log level methods exist and work."""
        with caplog.at_level(logging.DEBUG):
            structured_logger.debug("Debug message")
            structured_logger.info("Info message")
            structured_logger.warning("Warning message")
            structured_logger.error("Error message")
            structured_logger.critical("Critical message")

        assert "Debug message" in caplog.text
        assert "Info message" in caplog.text
        assert "Warning message" in caplog.text
        assert "Error message" in caplog.text
        assert "Critical message" in caplog.text


class TestConfigureLogging:
    """Tests for logging configuration."""

    def test_configure_logging_development(self):
        """Test configuring logging for development."""
        from src.config.logging_config import DevelopmentFormatter, configure_logging

        configure_logging(environment="development")

        root_logger = logging.getLogger()
        assert len(root_logger.handlers) > 0
        # Check formatter type
        handler = root_logger.handlers[0]
        assert isinstance(handler.formatter, DevelopmentFormatter)

    def test_configure_logging_production(self):
        """Test configuring logging for production."""
        from src.config.logging_config import CloudWatchJSONFormatter, configure_logging

        configure_logging(environment="production")

        root_logger = logging.getLogger()
        assert len(root_logger.handlers) > 0
        handler = root_logger.handlers[0]
        assert isinstance(handler.formatter, CloudWatchJSONFormatter)

    def test_configure_logging_sets_level(self):
        """Test that configure_logging sets the log level."""
        from src.config.logging_config import configure_logging

        configure_logging(level="WARNING")

        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING

    def test_configure_from_environment(self):
        """Test configuration from environment variables."""
        from src.config.logging_config import configure_from_environment

        with patch.dict(
            "os.environ",
            {"AURA_ENVIRONMENT": "qa", "AURA_LOG_LEVEL": "DEBUG"},
        ):
            configure_from_environment()

        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_returns_structured_logger(self):
        """Test that get_logger returns a StructuredLogger."""
        from src.config.logging_config import StructuredLogger, get_logger

        logger = get_logger(__name__)

        assert isinstance(logger, StructuredLogger)

    def test_get_logger_same_name_same_logger(self):
        """Test that same module name returns same underlying logger."""
        from src.config.logging_config import get_logger

        logger1 = get_logger("test.module")
        logger2 = get_logger("test.module")

        assert logger1._logger is logger2._logger


class TestLogLevel:
    """Tests for LogLevel enum."""

    def test_log_level_values(self):
        """Test that LogLevel enum has correct values."""
        from src.config.logging_config import LogLevel

        assert LogLevel.DEBUG.value == logging.DEBUG
        assert LogLevel.INFO.value == logging.INFO
        assert LogLevel.WARNING.value == logging.WARNING
        assert LogLevel.ERROR.value == logging.ERROR
        assert LogLevel.CRITICAL.value == logging.CRITICAL


class TestEnvironment:
    """Tests for Environment enum."""

    def test_environment_values(self):
        """Test that Environment enum has correct values."""
        from src.config.logging_config import Environment

        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.QA.value == "qa"
        assert Environment.PRODUCTION.value == "production"
