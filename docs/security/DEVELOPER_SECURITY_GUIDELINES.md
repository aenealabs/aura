# Developer Security Guidelines

## Project Aura - Secure Development Practices

This guide provides security best practices for developers working on Project Aura. Following these guidelines helps maintain CMMC Level 3, SOC 2, and NIST 800-53 compliance.

---

## Table of Contents

1. [Pre-Commit Security Checks](#pre-commit-security-checks)
2. [Secrets Management](#secrets-management)
3. [Input Validation](#input-validation)
4. [Authentication & Authorization](#authentication--authorization)
5. [Agent Security](#agent-security)
6. [API Security](#api-security)
7. [Database Security](#database-security)
8. [Logging & Auditing](#logging--auditing)
9. [Dependency Management](#dependency-management)
10. [Security Testing](#security-testing)

---

## Pre-Commit Security Checks

### Setup

Install the pre-commit hooks to automatically scan for security issues:

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually on all files
pre-commit run --all-files
```

### What Gets Checked

| Hook | Purpose | Blocks On |
|------|---------|-----------|
| `aura-secrets-scan` | Detects hardcoded secrets | CRITICAL, HIGH severity |
| `aura-config-validator` | Validates config files | CRITICAL, HIGH severity |
| `bandit` | Python security linting | Medium+ issues |
| `detect-private-key` | Finds private keys | Any detection |
| `detect-aws-credentials` | Finds AWS keys | Any detection |

### Manual Security Scans

```bash
# Full codebase scan
python scripts/aura_security_cli.py scan . -r

# Quick scan for sensitive files
python scripts/aura_security_cli.py quick

# Validate specific input
python scripts/aura_security_cli.py validate "user input to check"

# Generate security report
python scripts/aura_security_cli.py report -o security_report.json
```

---

## Secrets Management

### Never Do This

```python
# BAD - Hardcoded secrets
AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
DATABASE_PASSWORD = "my_password_123"
API_KEY = "sk-1234567890abcdef"

# BAD - Secrets in config files
config = {
    "api_key": "real_api_key_here",
    "db_password": "production_password"
}
```

### Always Do This

```python
# GOOD - Environment variables
import os
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY_ID")
DATABASE_PASSWORD = os.environ.get("DATABASE_PASSWORD")

# GOOD - AWS Secrets Manager
import boto3
from botocore.exceptions import ClientError

def get_secret(secret_name: str) -> dict:
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])

# GOOD - SSM Parameter Store
def get_parameter(name: str) -> str:
    client = boto3.client("ssm")
    response = client.get_parameter(Name=name, WithDecryption=True)
    return response["Parameter"]["Value"]
```

### Secrets Storage Locations

| Secret Type | Storage | Example |
|-------------|---------|---------|
| API Keys | AWS Secrets Manager | `aura/api-keys/openai` |
| Database Credentials | AWS Secrets Manager | `aura/db/neptune` |
| Configuration Values | SSM Parameter Store | `/aura/dev/config/endpoint` |
| JWT Signing Keys | AWS Secrets Manager | `aura/jwt/signing-key` |

### If You Accidentally Commit a Secret

1. **Immediately rotate the credential** - The secret is compromised
2. **Remove from git history** using BFG or filter-branch:
   ```bash
   # Using BFG (recommended)
   bfg --replace-text secrets.txt repo.git

   # Using git filter-branch
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch path/to/file" \
     --prune-empty --tag-name-filter cat -- --all
   ```
3. **Force push** the cleaned history
4. **Report the incident** to the security team

---

## Input Validation

### Use the Validation Service

```python
from src.services.input_validation_service import InputValidator, ThreatType

validator = InputValidator(strict_mode=True, log_threats=True)

# Validate user input
result = validator.validate_string(
    user_input,
    check_sql_injection=True,
    check_xss=True,
    check_command_injection=True,
    check_path_traversal=True,
    check_ssrf=True,
)

if not result.is_valid:
    raise ValidationError(f"Invalid input: {result.threats_detected}")

# Use sanitized value
safe_input = result.sanitized_value
```

### FastAPI Integration

```python
from src.api.security_integration import (
    ValidatedQueryRequest,
    ValidatedIngestionRequest,
    validate_and_sanitize,
)

# Use validated request models
@app.post("/query")
async def query(request: ValidatedQueryRequest):
    # request.query is already validated
    return {"result": process_query(request.query)}

# Manual validation
@app.post("/process")
async def process(data: dict):
    safe_value = validate_and_sanitize(
        data.get("input", ""),
        field_name="input",
        check_sql=True,
        check_xss=True,
    )
```

### Common Injection Patterns to Block

| Attack Type | Patterns | Example |
|-------------|----------|---------|
| SQL Injection | `' OR 1=1`, `; DROP TABLE`, `UNION SELECT` | `' OR '1'='1` |
| XSS | `<script>`, `javascript:`, `onerror=` | `<script>alert(1)</script>` |
| Command Injection | `; rm`, `| cat`, `$(cmd)`, backticks | `; rm -rf /` |
| Path Traversal | `../`, `..\\`, `%2e%2e%2f` | `../../../../etc/passwd` |
| SSRF | `localhost`, `127.0.0.1`, `169.254.169.254` | `http://169.254.169.254/` |

### URL Validation

```python
from src.services.input_validation_service import InputValidator

validator = InputValidator()

# Validate URLs to prevent SSRF
result = validator.validate_url(
    url,
    allow_localhost=False,      # Block localhost
    allow_private_ip=False,     # Block private IPs
    allowed_schemes=["https"],  # HTTPS only
    allowed_domains=["github.com", "gitlab.com"],  # Whitelist
)
```

---

## Authentication & Authorization

### Password Hashing

```python
# GOOD - Use Argon2id
from argon2 import PasswordHasher

ph = PasswordHasher(
    time_cost=3,        # iterations
    memory_cost=65536,  # 64 MB
    parallelism=4,      # threads
)

# Hash password
hashed = ph.hash(password)

# Verify password
try:
    ph.verify(hashed, password)
except argon2.exceptions.VerifyMismatchError:
    raise AuthenticationError("Invalid password")
```

```python
# BAD - Never use these for passwords
import hashlib
hashlib.md5(password.encode()).hexdigest()   # INSECURE
hashlib.sha1(password.encode()).hexdigest()  # INSECURE
hashlib.sha256(password.encode()).hexdigest() # No salt, too fast
```

### JWT Best Practices

```python
import jwt
from datetime import datetime, timedelta

# Configuration
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION = timedelta(hours=1)  # Short-lived tokens

def create_token(user_id: str, roles: list[str]) -> str:
    payload = {
        "sub": user_id,
        "roles": roles,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + JWT_EXPIRATION,
        "iss": "project-aura",  # Issuer
        "aud": "aura-api",      # Audience
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(token: str) -> dict:
    return jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
        issuer="project-aura",
        audience="aura-api",
    )
```

### Role-Based Access Control

```python
from functools import wraps
from fastapi import HTTPException, Depends

def require_role(required_role: str):
    """Decorator to enforce role-based access."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user=Depends(get_current_user), **kwargs):
            if required_role not in current_user.roles:
                raise HTTPException(
                    status_code=403,
                    detail=f"Role '{required_role}' required"
                )
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator

# Usage
@app.post("/admin/action")
@require_role("admin")
async def admin_action(current_user: User):
    pass
```

---

## Agent Security

### Prompt Injection Prevention

```python
from src.services.input_validation_service import InputValidator

validator = InputValidator()

def prepare_agent_prompt(user_query: str) -> str:
    # Validate for prompt injection
    result = validator.validate_string(
        user_query,
        check_prompt_injection=True,
    )

    if not result.is_valid:
        raise SecurityError("Potential prompt injection detected")

    # Use sanitized input in prompt
    return f"""You are a helpful assistant.

User Query: {result.sanitized_value}

Respond helpfully and safely."""
```

### Tool Authorization

```python
# Define allowed tools per agent role
AGENT_TOOL_PERMISSIONS = {
    "coder": ["read_file", "write_file", "run_tests"],
    "reviewer": ["read_file", "add_comment"],
    "validator": ["read_file", "run_tests", "check_security"],
}

def authorize_tool_use(agent_role: str, tool_name: str) -> bool:
    """Check if agent role is authorized to use tool."""
    allowed = AGENT_TOOL_PERMISSIONS.get(agent_role, [])
    return tool_name in allowed

# Usage in agent execution
def execute_tool(agent_role: str, tool_name: str, **kwargs):
    if not authorize_tool_use(agent_role, tool_name):
        log_security_event(
            event_type="AGENT_TOOL_ABUSE",
            details={"agent": agent_role, "tool": tool_name}
        )
        raise PermissionError(f"Agent '{agent_role}' not authorized for tool '{tool_name}'")

    return tools[tool_name](**kwargs)
```

### Sandbox Isolation

```python
# Agents must run in isolated sandboxes
from src.services.sandbox_network_service import SandboxNetworkService

sandbox_service = SandboxNetworkService()

async def run_agent_safely(agent, task):
    # Create isolated environment
    sandbox = await sandbox_service.create_sandbox(
        isolation_level="vpc",  # Full VPC isolation
        resource_limits={
            "cpu": "1",
            "memory": "512Mi",
            "network_egress": False,  # No external network
        }
    )

    try:
        result = await agent.execute_in_sandbox(sandbox, task)
    finally:
        await sandbox_service.destroy_sandbox(sandbox.id)

    return result
```

---

## API Security

### Request Validation

```python
from pydantic import BaseModel, validator, Field
from src.api.security_integration import validate_and_sanitize

class SecureRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000)
    options: dict = Field(default_factory=dict)

    @validator("query")
    def validate_query(cls, v):
        return validate_and_sanitize(
            v,
            field_name="query",
            check_sql=True,
            check_xss=True,
        )
```

### Rate Limiting

```python
from fastapi import Request, HTTPException
from collections import defaultdict
import time

class RateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self.rpm = requests_per_minute
        self.requests = defaultdict(list)

    def check(self, client_ip: str) -> bool:
        now = time.time()
        minute_ago = now - 60

        # Clean old requests
        self.requests[client_ip] = [
            t for t in self.requests[client_ip] if t > minute_ago
        ]

        if len(self.requests[client_ip]) >= self.rpm:
            return False

        self.requests[client_ip].append(now)
        return True

rate_limiter = RateLimiter(requests_per_minute=60)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host
    if not rate_limiter.check(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    return await call_next(request)
```

### CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

# GOOD - Specific origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.aura.local", "https://admin.aura.local"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# BAD - Wildcard allows any origin
# allow_origins=["*"]  # DON'T DO THIS
```

---

## Database Security

### Parameterized Queries

```python
# GOOD - Parameterized query (prevents SQL injection)
def get_user(user_id: str):
    query = "SELECT * FROM users WHERE id = %s"
    cursor.execute(query, (user_id,))
    return cursor.fetchone()

# BAD - String formatting (SQL injection vulnerable)
def get_user_unsafe(user_id: str):
    query = f"SELECT * FROM users WHERE id = '{user_id}'"  # VULNERABLE
    cursor.execute(query)
```

### Neptune Graph Queries

```python
from gremlin_python.process.traversal import T

# GOOD - Parameterized Gremlin
def get_node(node_id: str):
    return g.V().has(T.id, node_id).valueMap().toList()

# GOOD - Using bindings
def search_nodes(search_term: str):
    return g.V().has("name", TextP.containing(search_term)).toList()
```

### Connection Security

```python
# Always use TLS for database connections
neptune_config = {
    "host": "neptune.aura.local",
    "port": 8182,
    "ssl": True,
    "ssl_context": ssl.create_default_context(),
}

opensearch_config = {
    "hosts": ["https://opensearch.aura.local:9200"],
    "use_ssl": True,
    "verify_certs": True,
    "ssl_context": ssl.create_default_context(),
}
```

---

## Logging & Auditing

### Security Event Logging

```python
from src.services.security_audit_service import (
    log_security_event,
    SecurityEventType,
    SecurityEventSeverity,
    SecurityContext,
)

# Log authentication events
log_security_event(
    event_type=SecurityEventType.AUTH_LOGIN_SUCCESS,
    severity=SecurityEventSeverity.INFO,
    message=f"User {user_id} logged in successfully",
    context=SecurityContext(
        user_id=user_id,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
    ),
)

# Log threat detection
log_security_event(
    event_type=SecurityEventType.THREAT_COMMAND_INJECTION,
    severity=SecurityEventSeverity.CRITICAL,
    message="Command injection attempt detected",
    context=SecurityContext(
        user_id=user_id,
        ip_address=request.client.host,
        request_id=request_id,
    ),
    details={
        "payload": sanitized_payload,
        "endpoint": request.url.path,
    },
)
```

### Audit Decorator

```python
from src.api.security_integration import audit_endpoint
from src.services.security_audit_service import SecurityEventType

@app.post("/sensitive-action")
@audit_endpoint(
    event_type=SecurityEventType.DATA_MODIFICATION,
    severity=SecurityEventSeverity.HIGH,
    include_response=False,  # Don't log response data
)
async def sensitive_action(request: Request):
    # Automatically logged to audit trail
    pass
```

### What to Log

| Event Category | Log Level | Details |
|----------------|-----------|---------|
| Authentication | INFO | User ID, IP, success/failure |
| Authorization | INFO | User ID, resource, permission |
| Data Access | INFO | User ID, resource type, operation |
| Data Modification | HIGH | User ID, resource, before/after |
| Security Threats | CRITICAL | All context, sanitized payload |
| Agent Actions | MEDIUM | Agent ID, tool, parameters |
| Configuration Changes | HIGH | User ID, setting, old/new value |

### What NOT to Log

- Plain text passwords
- Full credit card numbers
- PII without masking
- Session tokens
- Private keys
- Unsanitized malicious payloads

---

## Dependency Management

### Checking for Vulnerabilities

```bash
# Check Python dependencies
pip-audit

# Check npm dependencies
npm audit

# Check specific package
pip-audit --requirement requirements.txt
```

### Keeping Dependencies Updated

```bash
# Update all packages
pip install --upgrade -r requirements.txt

# Check for outdated packages
pip list --outdated

# Use dependabot or renovate for automated updates
```

### Requirements Best Practices

```txt
# requirements.txt - Pin exact versions
fastapi==0.109.0
pydantic==2.5.3
boto3==1.34.25
cryptography==42.0.0

# Use >= only for security patches
argon2-cffi>=23.1.0  # Security-critical, allow patches
```

---

## Security Testing

### Running Security Tests

```bash
# Run all security-related tests
pytest tests/test_security*.py -v

# Run specific security service tests
pytest tests/test_input_validation_service.py -v
pytest tests/test_secrets_detection_service.py -v
pytest tests/test_security_audit_service.py -v
pytest tests/test_security_alerts_service.py -v
pytest tests/test_security_integration.py -v

# Run with coverage
pytest tests/test_security*.py --cov=src/services --cov-report=html
```

### Static Analysis

```bash
# Bandit - Python security linter
bandit -r src/ -ll

# Safety - Check for known vulnerabilities
safety check -r requirements.txt
```

### Manual Testing Checklist

Before submitting a PR with security-sensitive changes:

- [ ] Input validation handles all edge cases
- [ ] Error messages don't leak sensitive information
- [ ] Authentication tokens have proper expiration
- [ ] Authorization checks are in place
- [ ] Database queries are parameterized
- [ ] Secrets are not hardcoded
- [ ] Logging doesn't include sensitive data
- [ ] Rate limiting is configured
- [ ] CORS is properly restricted

---

## Quick Reference

### Security Services Import Paths

```python
# Input Validation
from src.services.input_validation_service import (
    InputValidator,
    ThreatType,
    ValidationResult,
)

# Secrets Detection
from src.services.secrets_detection_service import (
    SecretsDetectionService,
    SecretType,
    SecretSeverity,
)

# Security Audit
from src.services.security_audit_service import (
    log_security_event,
    SecurityEventType,
    SecurityEventSeverity,
    SecurityContext,
)

# Security Alerts
from src.services.security_alerts_service import (
    SecurityAlertsService,
    AlertPriority,
    AlertStatus,
)

# API Integration
from src.api.security_integration import (
    audit_endpoint,
    require_no_secrets,
    validate_and_sanitize,
    ValidatedQueryRequest,
    ValidatedIngestionRequest,
)
```

### CLI Commands

```bash
# Scan for secrets
python scripts/aura_security_cli.py scan . -r

# Validate input
python scripts/aura_security_cli.py validate "input text"

# Quick scan
python scripts/aura_security_cli.py quick

# Generate report
python scripts/aura_security_cli.py report

# Show statistics
python scripts/aura_security_cli.py stats
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-12 | Project Aura Team | Initial release |
