"""
Project Aura - Structured Logging Configuration

Provides centralized logging configuration with:
- JSON format for production (CloudWatch)
- Human-readable format for development
- Correlation ID support for distributed tracing
- Structured logging helpers

Issue: #45 - Observability: Standardize logging levels and format

Usage:
    >>> from src.config.logging_config import configure_logging, get_logger
    >>> configure_logging(environment="production")
    >>> logger = get_logger(__name__)
    >>> logger.info("Operation completed", operation="patch_apply", duration_ms=150)
"""

import contextvars
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

# Context variable for correlation ID (thread-safe)
correlation_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)


class LogLevel(Enum):
    """
    Standard logging levels with documented use cases.

    | Level    | Use Case                                    |
    |----------|---------------------------------------------|
    | DEBUG    | Detailed diagnostic info (dev only)         |
    | INFO     | Normal operation events                     |
    | WARNING  | Unexpected but handled situations           |
    | ERROR    | Errors that need attention                  |
    | CRITICAL | System failures requiring immediate action  |
    """

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class Environment(Enum):
    """Deployment environments."""

    DEVELOPMENT = "development"
    QA = "qa"
    PRODUCTION = "production"


# =============================================================================
# Correlation ID Management
# =============================================================================


def get_correlation_id() -> str:
    """
    Get the current correlation ID or generate a new one.

    Returns:
        Current correlation ID from context, or a new UUID if not set.
    """
    cid = correlation_id_var.get()
    if cid is None:
        cid = str(uuid.uuid4())
        correlation_id_var.set(cid)
    return cid


def set_correlation_id(correlation_id: str) -> None:
    """
    Set the correlation ID for the current context.

    Args:
        correlation_id: Unique identifier for tracing requests across services.
    """
    correlation_id_var.set(correlation_id)


def clear_correlation_id() -> None:
    """Clear the correlation ID from the current context."""
    correlation_id_var.set(None)


# =============================================================================
# JSON Formatter (CloudWatch Compatible)
# =============================================================================


class CloudWatchJSONFormatter(logging.Formatter):
    """
    JSON formatter optimized for CloudWatch Logs.

    Outputs logs in a format easily parsed by CloudWatch Logs Insights:
    {
        "timestamp": "2025-12-25T12:00:00.000Z",
        "level": "INFO",
        "logger": "src.services.context_retrieval",
        "message": "Operation completed",
        "correlation_id": "uuid-here",
        "extra": {...}
    }
    """

    # Fields that should never appear in logs (security)
    SENSITIVE_FIELDS = frozenset(
        {
            "password",
            "secret",
            "token",
            "api_key",
            "apikey",
            "auth",
            "credential",
            "private_key",
            "access_key",
            "secret_key",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Build base log entry
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id(),
        }

        # Add source location for errors
        if record.levelno >= logging.ERROR:
            log_entry["location"] = {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields (from logger.info(..., extra={...}))
        extra = self._extract_extra(record)
        if extra:
            log_entry["extra"] = self._sanitize_extra(extra)

        return json.dumps(log_entry, default=str)

    def _extract_extra(self, record: logging.LogRecord) -> dict[str, Any]:
        """Extract extra fields from log record."""
        # Standard LogRecord attributes to exclude
        standard_attrs = {
            "name",
            "msg",
            "args",
            "created",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "exc_info",
            "exc_text",
            "thread",
            "threadName",
            "taskName",
            "message",
        }

        return {
            key: value
            for key, value in record.__dict__.items()
            if key not in standard_attrs and not key.startswith("_")
        }

    def _sanitize_extra(self, extra: dict[str, Any]) -> dict[str, Any]:
        """Remove sensitive fields from extra data."""
        sanitized: dict[str, Any] = {}
        for key, value in extra.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in self.SENSITIVE_FIELDS):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_extra(value)
            else:
                sanitized[key] = value
        return sanitized


# =============================================================================
# Human-Readable Formatter (Development)
# =============================================================================


class DevelopmentFormatter(logging.Formatter):
    """
    Human-readable formatter for local development.

    Format: [TIMESTAMP] LEVEL LOGGER - MESSAGE {extra}
    Color-coded by log level.
    """

    COLORS = {
        logging.DEBUG: "\033[36m",  # Cyan
        logging.INFO: "\033[32m",  # Green
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",  # Red
        logging.CRITICAL: "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, use_color: bool = True) -> None:
        """
        Initialize formatter.

        Args:
            use_color: Whether to use ANSI color codes.
        """
        super().__init__()
        self.use_color = use_color and sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        """Format log record for human readability."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        level = record.levelname.ljust(8)
        logger_name = record.name

        # Shorten long logger names
        if len(logger_name) > 40:
            parts = logger_name.split(".")
            logger_name = f"...{'.'.join(parts[-2:])}"

        message = record.getMessage()
        correlation_id = get_correlation_id()

        # Build output
        if self.use_color:
            color = self.COLORS.get(record.levelno, "")
            output = (
                f"[{timestamp}] {color}{level}{self.RESET} {logger_name} - {message}"
            )
        else:
            output = f"[{timestamp}] {level} {logger_name} - {message}"

        # Add correlation ID
        output += f" [cid:{correlation_id[:8]}...]"

        # Add extra fields
        extra = self._extract_extra(record)
        if extra:
            extra_str = " ".join(f"{k}={v}" for k, v in extra.items())
            output += f" {{{extra_str}}}"

        # Add exception info
        if record.exc_info:
            output += f"\n{self.formatException(record.exc_info)}"

        return output

    def _extract_extra(self, record: logging.LogRecord) -> dict[str, Any]:
        """Extract extra fields from log record."""
        standard_attrs = {
            "name",
            "msg",
            "args",
            "created",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "exc_info",
            "exc_text",
            "thread",
            "threadName",
            "taskName",
            "message",
        }

        return {
            key: value
            for key, value in record.__dict__.items()
            if key not in standard_attrs and not key.startswith("_")
        }


# =============================================================================
# Structured Logger Wrapper
# =============================================================================


class StructuredLogger:
    """
    Wrapper around Python logger that enables structured logging.

    Provides a convenient API for logging with extra context:

        logger = get_logger(__name__)
        logger.info("Operation completed", operation="patch", duration_ms=150)

    Instead of:
        logger.info("Operation completed", extra={"operation": "patch", "duration_ms": 150})
    """

    def __init__(self, logger: logging.Logger) -> None:
        """Initialize with underlying logger."""
        self._logger = logger

    def debug(self, msg: str, **kwargs: Any) -> None:
        """Log at DEBUG level with structured data."""
        self._logger.debug(msg, extra=kwargs)

    def info(self, msg: str, **kwargs: Any) -> None:
        """Log at INFO level with structured data."""
        self._logger.info(msg, extra=kwargs)

    def warning(self, msg: str, **kwargs: Any) -> None:
        """Log at WARNING level with structured data."""
        self._logger.warning(msg, extra=kwargs)

    def error(self, msg: str, exc_info: bool = False, **kwargs: Any) -> None:
        """Log at ERROR level with structured data."""
        self._logger.error(msg, exc_info=exc_info, extra=kwargs)

    def critical(self, msg: str, exc_info: bool = False, **kwargs: Any) -> None:
        """Log at CRITICAL level with structured data."""
        self._logger.critical(msg, exc_info=exc_info, extra=kwargs)

    def exception(self, msg: str, **kwargs: Any) -> None:
        """Log exception with traceback."""
        self._logger.exception(msg, extra=kwargs)


# =============================================================================
# Logging Configuration
# =============================================================================


def configure_logging(
    environment: str | Environment = "development",
    level: str | LogLevel = "INFO",
    log_file: str | None = None,
) -> None:
    """
    Configure logging for the application.

    Args:
        environment: Deployment environment ("development", "qa", "production").
        level: Minimum log level ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL").
        log_file: Optional path to log file.

    Examples:
        >>> configure_logging(environment="production")
        >>> configure_logging(environment="development", level="DEBUG")
    """
    # Normalize environment
    if isinstance(environment, str):
        environment = Environment(environment.lower())

    # Normalize level
    if isinstance(level, str):
        level_int = getattr(logging, level.upper(), logging.INFO)
    else:
        level_int = level.value

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level_int)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level_int)

    # Set formatter based on environment
    if environment == Environment.PRODUCTION:
        console_handler.setFormatter(CloudWatchJSONFormatter())
    else:
        console_handler.setFormatter(DevelopmentFormatter())

    root_logger.addHandler(console_handler)

    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level_int)
        file_handler.setFormatter(CloudWatchJSONFormatter())
        root_logger.addHandler(file_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> StructuredLogger:
    """
    Get a structured logger for the given module.

    Args:
        name: Module name (typically __name__).

    Returns:
        StructuredLogger wrapper with convenient API.

    Examples:
        >>> logger = get_logger(__name__)
        >>> logger.info("User logged in", user_id="123", ip="192.168.1.1")
    """
    return StructuredLogger(logging.getLogger(name))


def configure_from_environment() -> None:
    """
    Configure logging based on environment variables.

    Environment variables:
        AURA_ENVIRONMENT: "development", "qa", "production" (default: development)
        AURA_LOG_LEVEL: "DEBUG", "INFO", "WARNING", "ERROR" (default: INFO)
        AURA_LOG_FILE: Path to log file (optional)
    """
    environment = os.getenv("AURA_ENVIRONMENT", "development")
    level = os.getenv("AURA_LOG_LEVEL", "INFO")
    log_file = os.getenv("AURA_LOG_FILE")

    configure_logging(environment=environment, level=level, log_file=log_file)


# =============================================================================
# Convenience Exports
# =============================================================================

__all__ = [
    # Configuration
    "configure_logging",
    "configure_from_environment",
    "get_logger",
    # Log levels
    "LogLevel",
    "Environment",
    # Correlation ID
    "get_correlation_id",
    "set_correlation_id",
    "clear_correlation_id",
    # Formatters (for custom configuration)
    "CloudWatchJSONFormatter",
    "DevelopmentFormatter",
    "StructuredLogger",
]
