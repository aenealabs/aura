# Logging Standards

This document defines the logging standards for Project Aura.

**Issue:** #45 - Observability: Standardize logging levels and format

## Quick Start

```python
from src.config.logging_config import configure_logging, get_logger

# Configure logging at application startup
configure_logging(environment="production")

# Get a logger for your module
logger = get_logger(__name__)

# Log with structured data
logger.info("Operation completed", operation="patch_apply", duration_ms=150, user_id="u123")
```

## Logging Levels

| Level    | Use Case                                         | Example                                        |
|----------|--------------------------------------------------|------------------------------------------------|
| DEBUG    | Detailed diagnostic info (dev only)              | Variable values, loop iterations               |
| INFO     | Normal operation events                          | "User logged in", "Job started"                |
| WARNING  | Unexpected but handled situations                | "Retry attempt 2/3", "Cache miss"              |
| ERROR    | Errors that need attention                       | "Database connection failed", "API error 500"  |
| CRITICAL | System failures requiring immediate action       | "Out of memory", "Security breach detected"    |

### Level Guidelines

**DEBUG:**
- Use sparingly in production code
- Helpful for tracing code flow
- Include variable values relevant to debugging
- Example: `logger.debug("Processing item", item_id=item.id, status=item.status)`

**INFO:**
- Normal business operations
- State transitions
- Successful completions
- Example: `logger.info("Patch applied successfully", patch_id=patch.id, job_id=job.id)`

**WARNING:**
- Recoverable errors
- Deprecated feature usage
- Configuration issues that don't prevent operation
- Example: `logger.warning("Rate limit approaching", current=980, limit=1000)`

**ERROR:**
- Exceptions that prevent operation completion
- Failed API calls
- Data validation failures
- Example: `logger.error("Failed to fetch user", user_id=user_id, exc_info=True)`

**CRITICAL:**
- System-wide failures
- Security incidents
- Data corruption
- Example: `logger.critical("Database corruption detected", table="jobs")`

## Structured Logging Format

### Production (JSON)

In production, logs are formatted as JSON for CloudWatch Logs Insights:

```json
{
  "timestamp": "2025-12-25T12:00:00.000Z",
  "level": "INFO",
  "logger": "src.services.context_retrieval",
  "message": "Operation completed",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "extra": {
    "operation": "patch_apply",
    "duration_ms": 150,
    "user_id": "u123"
  }
}
```

### Development (Human-Readable)

In development, logs use a human-readable format with color coding:

```
[2025-12-25 12:00:00.123] INFO     src.services.context_retrieval - Operation completed [cid:a1b2c3d4...] {operation=patch_apply duration_ms=150 user_id=u123}
```

## Correlation IDs

Correlation IDs enable distributed tracing across services.

### Setting Correlation ID

```python
from src.config.logging_config import set_correlation_id, clear_correlation_id

# At request entry point (e.g., middleware)
def handle_request(request):
    # Use existing ID from header or generate new
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    set_correlation_id(correlation_id)

    try:
        return process_request(request)
    finally:
        clear_correlation_id()
```

### HTTP Header Convention

- Header: `X-Correlation-ID`
- Format: UUID v4
- Propagate to downstream services in all HTTP calls

## Sensitive Data

**NEVER log sensitive data:**

- Passwords
- API keys / tokens
- Session tokens
- Personal identification numbers
- Credit card numbers
- Private keys

The logger automatically redacts fields containing these keywords:
- `password`, `secret`, `token`, `api_key`, `auth`
- `credential`, `private_key`, `access_key`, `secret_key`

```python
# BAD - will be logged (but redacted)
logger.info("User auth", password="secret123")  # password=[REDACTED]

# GOOD - don't include at all
logger.info("User authenticated", user_id="u123")
```

## Configuration

### Environment Variables

| Variable          | Description                        | Default     |
|-------------------|------------------------------------|-------------|
| AURA_ENVIRONMENT  | Environment (development/qa/prod)  | development |
| AURA_LOG_LEVEL    | Minimum log level                  | INFO        |
| AURA_LOG_FILE     | Path to log file (optional)        | None        |

### Programmatic Configuration

```python
from src.config.logging_config import configure_logging

# Development with DEBUG level
configure_logging(environment="development", level="DEBUG")

# Production with file logging
configure_logging(
    environment="production",
    level="INFO",
    log_file="/var/log/aura/app.log"
)

# Auto-configure from environment variables
from src.config.logging_config import configure_from_environment
configure_from_environment()
```

## CloudWatch Logs Insights Queries

### Find all errors in the last hour

```sql
fields @timestamp, @message, correlation_id
| filter level = "ERROR"
| sort @timestamp desc
| limit 100
```

### Trace a request by correlation ID

```sql
fields @timestamp, level, logger, message
| filter correlation_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
| sort @timestamp asc
```

### Find slow operations

```sql
fields @timestamp, message, extra.duration_ms
| filter extra.duration_ms > 1000
| sort extra.duration_ms desc
| limit 50
```

### Error rate by service

```sql
stats count(*) as error_count by logger
| filter level = "ERROR"
| sort error_count desc
```

## Migration Guide

### Before (Standard logging)

```python
import logging

logger = logging.getLogger(__name__)

logger.info(f"Processing job {job_id}")
logger.error(f"Failed to process: {e}")
```

### After (Structured logging)

```python
from src.config.logging_config import get_logger

logger = get_logger(__name__)

logger.info("Processing job", job_id=job_id)
logger.error("Failed to process", exc_info=True, job_id=job_id, error=str(e))
```

## Best Practices

1. **Use structured data over string interpolation**
   - Bad: `logger.info(f"User {user_id} logged in from {ip}")`
   - Good: `logger.info("User logged in", user_id=user_id, ip=ip)`

2. **Include context in every log**
   - Always include relevant IDs (job_id, user_id, request_id)
   - Include timing for operations (duration_ms, latency_ms)

3. **Use appropriate log levels**
   - Don't log everything as INFO
   - Reserve ERROR for actual errors, not expected conditions

4. **Log at boundaries**
   - Entry/exit of public methods
   - Before/after external calls (APIs, databases)
   - State transitions

5. **Include actionable information**
   - What happened
   - Why it matters
   - What to do about it (for errors)

## Testing Logs

```python
import logging
from unittest.mock import patch

def test_logs_operation_completion(caplog):
    with caplog.at_level(logging.INFO):
        service.process_job(job_id="j123")

    assert "Processing job" in caplog.text
    assert "j123" in caplog.text
```
