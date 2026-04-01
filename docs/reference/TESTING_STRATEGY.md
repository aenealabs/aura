# Testing Strategy

This document defines the testing philosophy, rationale, and patterns for Project Aura.

## Testing Pyramid

```
        /\
       /  \     E2E Tests (real AWS, manual, rare)
      /----\
     /      \   Integration Tests (mocks, CI, frequent)
    /--------\
   /          \ Unit Tests (no mocks, CI, every commit)
  --------------
```

| Layer | Purpose | Coverage Target | Runs |
|-------|---------|-----------------|------|
| **Unit** | Verify individual functions/classes work correctly | 80%+ code coverage | Every commit |
| **Integration** | Verify components work together correctly | Workflow coverage | Every commit |
| **E2E** | Verify full system with real services | Critical paths | Manual/scheduled |

## Why Integration Tests Use Mocks

Integration tests in `tests/test_end_to_end_integration.py` use mocks intentionally:

### 1. External Dependencies Are Expensive
Real services require:
- AWS Bedrock LLM calls ($0.003-$0.015 per 1K tokens)
- Neptune database cluster (~$0.10/hour)
- OpenSearch domain (~$0.036/hour)
- EKS cluster for sandboxes (~$0.10/hour)

Running these in CI would cost ~$5-10 per test run.

### 2. Deterministic Test Results
```python
# With mocks, we control exact responses
orchestrator.provision_sandbox = AsyncMock(return_value=mock_sandbox)
orchestrator.run_tests = AsyncMock(return_value={"tests_passed": 45, "tests_failed": 0})
```

Real services have:
- Variable latency (network, cold starts)
- Rate limits (NVD: 5 req/30s without API key)
- Transient failures (timeouts, throttling)

### 3. Edge Case Simulation
Mocks enable testing scenarios that are hard to reproduce:
- Sandbox provisioning failures
- Concurrent approval conflicts
- Batch processing of 10+ threats
- Network timeouts at specific points
- Service degradation patterns

### 4. Fast Feedback Loop
| Test Type | Duration | Suitable for CI |
|-----------|----------|-----------------|
| Unit tests | ~0.2s | Yes |
| Integration (mocked) | ~1.3s | Yes |
| E2E (real services) | ~5-10 min | No (cost/time) |

## What Each Test Type Validates

### Unit Tests (80%+ Coverage)
Test individual functions in isolation:
- Input validation logic
- Data transformation
- Business rules
- Error handling paths

```python
def test_input_sanitizer_removes_quotes():
    sanitizer = InputSanitizer()
    result = sanitizer.sanitize('test"input\'with"quotes')
    assert '"' not in result
```

### Integration Tests (Workflow Coverage)
Test component contracts and data flow:

| Test Class | Validates |
|------------|-----------|
| `TestFullPipelineIntegration` | Data flows correctly between phases |
| `TestPipelineStateTracking` | State transitions are valid |
| `TestPipelineErrorHandling` | Failures propagate correctly |
| `TestPipelinePerformance` | Batch/concurrent patterns work |

```python
@pytest.mark.integration
async def test_full_pipeline_threat_to_approval():
    # Phase 1: Threat detection
    threats = await threat_agent.analyze_codebase(...)

    # Phase 2: ADR generation
    adr = await adr_agent.generate(threats[0])

    # Phase 3: Sandbox testing (MOCKED - no real EKS)
    sandbox = await orchestrator.provision_sandbox(...)

    # Phase 4: HITL approval
    approval = await approval_service.submit(...)

    # Verify data flowed correctly between phases
    assert approval.adr_id == adr.id
    assert approval.threat_id == threats[0].id
```

### E2E Tests (Critical Paths)
Run manually against real AWS services:
- Full deployment validation
- Performance benchmarking
- Security penetration testing

## Test File Organization

```
tests/
├── test_*.py                      # Unit tests (80%+ coverage target)
├── test_end_to_end_integration.py # Integration tests (mocked workflows)
└── conftest.py                    # Shared fixtures
```

## Running Tests

```bash
# All tests (unit + integration)
pytest

# Unit tests only (for quick feedback)
pytest -m "not integration"

# Integration tests only
pytest -m integration

# With coverage report
pytest --cov=src --cov-report=html

# Skip coverage check (for integration tests)
pytest tests/test_end_to_end_integration.py --no-cov
```

## Best Practices

### When to Write Unit Tests
- All business logic functions
- Input validation
- Data transformations
- Error handling code paths

### When to Write Integration Tests
- Multi-component workflows
- Agent orchestration flows
- Service-to-service contracts
- State machine transitions

### Test Isolation Patterns

#### Rate Limiter Isolation

The API rate limiter uses a global singleton that maintains state between requests. Without proper isolation, rate limit state can bleed between tests, causing spurious 429 errors.

**Solution:** Use the rate limiter test utilities in `src/services/api_rate_limiter.py`:

```python
from src.services.api_rate_limiter import (
    reset_rate_limiter,
    disable_rate_limiting,
    enable_rate_limiting,
)

# Option 1: Reset rate limiter between tests (preferred for most tests)
@pytest.fixture(autouse=True)
def reset_rate_limiter_fixture():
    """Reset rate limiter before each test to prevent state bleeding."""
    reset_rate_limiter()
    yield
    reset_rate_limiter()

# Option 2: Disable rate limiting entirely (for workflow tests making many requests)
@pytest.fixture(autouse=True)
def mock_rate_limiter():
    """Disable rate limiting for tests that make multiple requests."""
    disable_rate_limiting()
    yield
    enable_rate_limiting()
```

The `reset_rate_limiter_fixture` is already configured as an autouse fixture in `tests/conftest.py`, so all tests automatically get a clean rate limiter state.

For integration tests that make multiple API requests (e.g., list -> view -> approve workflow), use `disable_rate_limiting()` to avoid hitting rate limits during test execution.

#### Configuration State Isolation

Global configuration dictionaries can be mutated by consumers, affecting other tests. Use `copy.deepcopy()` when returning configuration to prevent this.

**Problem:**

```python
# Bad: Returns direct reference that can be mutated
def get_config():
    return GLOBAL_CONFIG[env]  # Consumer can modify this!
```

**Solution:**

```python
import copy

# Good: Returns a copy that can be safely mutated
def get_config():
    return copy.deepcopy(GLOBAL_CONFIG[env])  # Mutations don't affect global state
```

This pattern is used in `src/config/guardrails_config.py` to prevent services from inadvertently modifying shared configuration state.

### Mock Boundaries
Mock at service boundaries, not internal implementation:

```python
# Good: Mock the external service
orchestrator.provision_sandbox = AsyncMock(return_value=mock_sandbox)

# Bad: Mock internal implementation details
orchestrator._validate_config = MagicMock(return_value=True)
```

### Fixture Patterns
Use pytest fixtures for common test data:

```python
@pytest.fixture
def critical_threat():
    return ThreatIntelReport(
        id="threat-critical-001",
        severity=ThreatSeverity.CRITICAL,
        cvss_score=9.8,
        ...
    )
```

## Coverage Requirements

| Test Category | Minimum Coverage |
|---------------|-----------------|
| Unit tests (`src/`) | 80% |
| Integration tests | N/A (workflow focus) |
| Security-critical code | 90% |

The 80% coverage target applies to unit tests measuring line coverage of `src/`. Integration tests focus on workflow validation rather than line coverage.

---

## Test Execution Metrics (January 2026)

| Metric | Count |
|--------|-------|
| **Total test cases** | 20,166 |
| **Passed** | 13,668 |
| **Skipped** | 6,498 |
| **Failed** | 0 |
| **Backend (Python)** | 18,515 tests across 470+ files |
| **Frontend (Vitest)** | 1,651 tests across 63 files |

### Why Tests Are Skipped

Tests are skipped intentionally based on environment availability. This allows the full test suite to be defined while gracefully handling missing dependencies.

| Skip Reason | Description | How to Enable |
|-------------|-------------|---------------|
| **Optional packages not installed** | Redis, sklearn, PyTorch, cairosvg | `pip install redis scikit-learn torch` |
| **External services unavailable** | Neptune, OpenSearch, Redis server | Set endpoints + run services (see below) |
| **E2E tests disabled** | Real AWS integration tests | `RUN_E2E_TESTS=1` or `RUN_AWS_E2E_TESTS=1` |
| **Integration tests disabled** | Component integration tests | `RUN_INTEGRATION_TESTS=1` |
| **GPU not available** | CUDA-specific tests | Requires NVIDIA GPU with CUDA |

### External Service Availability

Services check **two conditions** before running tests:

1. **Package installed** (e.g., `gremlinpython`, `opensearch-py`, `redis`)
2. **Service reachable** (endpoint configured + server running)

| Service | Package | Environment Variable | Default Endpoint |
|---------|---------|---------------------|------------------|
| Neptune | `gremlinpython` | `NEPTUNE_ENDPOINT` | `neptune.aura.local:8182` |
| OpenSearch | `opensearch-py` | `OPENSEARCH_ENDPOINT` | `opensearch.aura.local:9200` |
| Redis | `redis` | `REDIS_URL` | `localhost:6379` |

**Running tests with local services:**

```bash
# Start Redis locally (Docker)
docker run -d -p 6379:6379 redis:7-alpine

# Run tests with Redis available
pytest tests/

# For full E2E tests (requires VPC connectivity to AWS)
RUN_AWS_E2E_TESTS=1 pytest tests/test_aws_services_e2e.py -v
```

### Reducing Skipped Test Count

To maximize test execution locally:

```bash
# Install optional packages
pip install redis scikit-learn torch cairosvg

# Start local Redis
docker run -d -p 6379:6379 redis:7-alpine

# Run with integration tests enabled
RUN_INTEGRATION_TESTS=1 pytest tests/

# Full E2E (requires AWS credentials + VPC access)
RUN_AWS_E2E_TESTS=1 RUN_E2E_TESTS=1 pytest tests/
```

---

## Integration vs E2E Tests: Purpose and Relationship

The testing pyramid has three distinct layers, each serving a specific purpose:

```
┌─────────────────────────────────────────────────────────────┐
│                     E2E Tests                                │
│  Real AWS services (Neptune, OpenSearch, Bedrock)           │
│  Validates: Full system behavior in deployed environment     │
│  Trigger: RUN_AWS_E2E_TESTS=1 (manual/scheduled)            │
├─────────────────────────────────────────────────────────────┤
│                 Integration Tests                            │
│  Mocked boundaries (moto, httpx mocks)                       │
│  Validates: Component contracts, data flow, error handling   │
│  Trigger: RUN_INTEGRATION_TESTS=1 or pytest -m integration   │
├─────────────────────────────────────────────────────────────┤
│                    Unit Tests                                │
│  All dependencies mocked                                     │
│  Validates: Individual function/class behavior               │
│  Trigger: Default (every commit)                             │
└─────────────────────────────────────────────────────────────┘
```

### No Redundancy - Different Validation Goals

| Aspect | Integration Tests | E2E Tests |
|--------|------------------|-----------|
| **AWS Services** | Mocked (moto, LocalStack) | Real (deployed infrastructure) |
| **Network Calls** | Mocked (httpx/aiohttp mocks) | Real HTTP/HTTPS |
| **Speed** | Fast (< 5s per test) | Slow (30s - 5min per test) |
| **Cost** | Free | ~$5-10 per full run |
| **CI/CD** | Every commit | Manual/scheduled |
| **Validates** | Component contracts work | Full system works end-to-end |
| **Catches** | Interface mismatches, data flow bugs | Deployment issues, IAM permissions, network config |

### Recommended Testing Workflow

1. **Development:** Run unit tests continuously (`pytest -m unit`)
2. **Pre-commit:** Run unit + integration (`pytest -m "unit or integration"`)
3. **PR merge:** Full unit + integration suite (CI/CD)
4. **Pre-release:** E2E tests against staging (`RUN_AWS_E2E_TESTS=1`)
5. **Post-deploy:** Smoke tests against production

---

## Test Type Classification

All tests in Project Aura MUST be explicitly marked with one of the following types. This ensures clarity about test dependencies, execution context, and CI/CD pipeline integration.

### Unit Tests (`@pytest.mark.unit`)

**Purpose:** Test individual functions/classes in complete isolation
**Dependencies:** ALL external calls mocked
**Speed:** < 100ms per test
**Location:** `tests/test_*.py` (default)

Characteristics:
- No network calls (real or mocked HTTP clients)
- No file system access outside temp directories
- No database connections
- Deterministic and repeatable
- Pure function testing

```python
@pytest.mark.unit
class TestInputSanitizer:
    def test_removes_sql_injection_patterns(self):
        sanitizer = InputSanitizer()
        result = sanitizer.clean("SELECT * FROM users; DROP TABLE--")
        assert "DROP" not in result
```

### Integration Tests (`@pytest.mark.integration`)

**Purpose:** Test component interactions with mocked external boundaries
**Dependencies:** moto for AWS, aiohttp mocks for external APIs
**Speed:** < 5s per test
**Location:** `tests/test_*_integration.py`

Characteristics:
- Uses moto for AWS service mocking
- Uses aiohttp/httpx mocks for external API calls
- Tests service-to-service contracts
- Validates error propagation across boundaries

```python
@pytest.mark.integration
@pytest.mark.aws_integration
async def test_threat_detection_stores_in_dynamodb(mock_dynamodb):
    detector = ThreatDetector(dynamodb=mock_dynamodb)
    threat = await detector.analyze(malicious_code)

    # Verify data flowed to storage
    stored = await mock_dynamodb.get_item(threat.id)
    assert stored["severity"] == "CRITICAL"
```

### E2E Tests (`@pytest.mark.e2e`)

**Purpose:** Validate full system with real external services
**Dependencies:** Real AWS, real external APIs
**Speed:** 30s - 5min per test
**Location:** `tests/e2e/`

Characteristics:
- Requires `RUN_E2E_TESTS=1` environment variable
- Runs against deployed infrastructure
- Uses real credentials (from SSM/Secrets Manager)
- Run manually or on schedule (not every commit)

```python
@pytest.mark.e2e
@pytest.mark.skipif(not os.getenv("RUN_E2E_TESTS"), reason="E2E disabled")
async def test_full_incident_workflow(aws_clients):
    # Trigger real CloudWatch alarm
    # Wait for Step Functions execution
    # Verify DynamoDB records
    # Validate SNS notification sent
```

---

## Isolation Markers

### `@pytest.mark.forked`

Apply to tests that suffer from mock pollution when run in the same process:

```python
pytestmark = [pytest.mark.unit, pytest.mark.forked]
```

**When to use:**
- aiohttp/httpx mocks leaking between tests
- Global state that cannot be reset via fixtures
- Tests that modify `sys.modules`
- Tests patching module-level constants (e.g., `HTTPX_AVAILABLE`)

**Trade-off:** Slower execution due to subprocess overhead (~50-100ms per test)

### `@pytest.mark.torch_required`

Apply to tests that import PyTorch:

```python
pytestmark = pytest.mark.torch_required
```

**When to use:**
- Tests using TitanMemoryService, neural memory models
- Tests importing torch directly
- These tests run LAST to avoid polluting the main process

### `@pytest.mark.gpu_required`

Apply to tests that require NVIDIA GPU:

```python
@pytest.mark.gpu_required
@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
def test_gpu_memory_backend():
    ...
```

**When to use:**
- Tests for GPU memory backends
- CUDA-specific functionality
- Skip by default on Apple Silicon

---

## Mock Factory Usage

Centralized mock factories are available in `tests/fixtures/mock_factories.py`:

```python
from tests.fixtures.mock_factories import (
    create_aiohttp_session_mock,
    create_aiohttp_multi_response_mock,
    create_httpx_client_mock,
)

# Single response mock
mock = create_aiohttp_session_mock(200, {"status": "ok"})
with patch("module.aiohttp.ClientSession", return_value=mock):
    result = await service.fetch_data()

# Multi-step API flow (auth -> list -> details)
mock = create_aiohttp_multi_response_mock([
    (201, {"access_token": "abc123"}),
    (200, {"resources": ["id1", "id2"]}),
    (200, {"device_id": "id1", "hostname": "server01"}),
])
```

### Available Mock Factories

| Factory | Purpose |
|---------|---------|
| `create_aiohttp_session_mock` | Single-response aiohttp mock |
| `create_aiohttp_multi_response_mock` | Multi-step API flow mock |
| `create_httpx_client_mock` | httpx.AsyncClient mock |
| `create_crowdstrike_auth_response` | CrowdStrike OAuth token |
| `create_crowdstrike_hosts_response` | CrowdStrike host search |
| `create_qualys_vulnerability_response` | Qualys vulnerability detail |
| `create_terraform_workspace_response` | Terraform Cloud workspace |

---

## Test Execution Commands

```bash
# Run only unit tests (fastest, for TDD)
pytest -m unit

# Run unit + integration tests (default CI pipeline)
pytest -m "unit or integration"

# Run unit tests for connectors only
pytest tests/test_*_connector.py -m unit

# Run integration tests only (uses moto, mock HTTP)
pytest -m integration

# Run E2E tests (requires real AWS credentials)
RUN_E2E_TESTS=1 pytest -m e2e --no-cov

# Run tests that need isolation (forked subprocess)
pytest -m forked

# Run everything except torch tests (faster on macOS)
pytest -m "not torch_required"

# Run GPU tests (requires NVIDIA GPU)
pytest -m gpu_required
```

---

## Test Documentation Convention

Every test file should include a standardized docstring:

```python
"""
Project Aura - {Component} {TestType} Tests

Test Type: UNIT | INTEGRATION | E2E
Dependencies: {List of mocked/real dependencies}
Isolation: {Isolation markers if any}
Run Command: pytest {file_path} -v

These tests validate:
- {Validation point 1}
- {Validation point 2}
- {Validation point 3}

Mock Strategy:
- {Mock 1}: {Description}
- {Mock 2}: {Description}

Related E2E Tests:
- tests/e2e/{related_file}.py (requires RUN_E2E_TESTS=1)
"""

pytestmark = [
    pytest.mark.unit,  # or integration, e2e
    pytest.mark.forked,  # if needed
]
```

---

## Performance Markers

### `@pytest.mark.slow`

Apply to tests that take more than 1 second to execute. This allows CI to run fast tests first for quick feedback.

```python
@pytest.mark.slow
def test_full_ingestion_pipeline():
    """Takes ~5 seconds to run full pipeline."""
    ...

# Or for entire test modules:
pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not os.getenv("RUN_AWS_E2E_TESTS"), reason="E2E disabled"),
]
```

**When to use:**
- Tests with network calls to real services (E2E tests)
- Tests with multiple time.sleep delays
- Integration tests running full pipelines
- Benchmark tests with many iterations

**CI Integration:**

```bash
# Quick CI check (runs in seconds)
pytest -m "not slow" --timeout=60

# Full test suite (includes slow tests)
pytest
```

**Files with slow markers:**
- `tests/test_aws_services_e2e.py` - OpenSearch and Pipeline E2E classes
- `tests/integration/test_runtime_incident_e2e.py` - Incident workflow E2E
- `tests/test_anomaly_e2e_synthetic.py` - Anomaly detection E2E
- Various individual tests marked with `@pytest.mark.slow`

---

## Avoiding time.sleep in Tests

Real `time.sleep()` calls add unnecessary delay to test execution. Replace them with mocked time or event-driven waits.

### Pattern 1: Mock time.time() for Duration Tests

When testing elapsed time or runtime calculations:

```python
from unittest.mock import patch

def test_runtime_calculation():
    # Mock time.time() to return controlled values
    mock_times = [0.0, 0.5]  # start_time=0, end_time=0.5
    with patch("src.module.time.time", side_effect=mock_times):
        service = TimedService()  # Calls time.time() in __init__
        result = service.finalize()  # Calls time.time() again

    # Verify exact runtime without waiting
    assert result["runtime_seconds"] == 0.5
```

### Pattern 2: Mock time.sleep() Directly

When testing code that includes waits:

```python
from unittest.mock import patch

def test_retry_logic():
    with patch("src.services.my_service.time.sleep") as mock_sleep:
        service.retry_operation()

    # Verify sleep was called with expected delays
    assert mock_sleep.call_count == 3
    mock_sleep.assert_any_call(1.0)  # First retry delay
```

### Pattern 3: Use Async Waits for Concurrent Tests

For async tests waiting on conditions:

```python
import asyncio

async def test_async_completion():
    # Bad: time.sleep(0.5) blocks the event loop
    # Good: asyncio.wait_for with a condition
    await asyncio.wait_for(
        service.wait_for_ready(),
        timeout=1.0
    )
    assert service.is_ready
```

### When time.sleep is Acceptable

Small delays (< 20ms) are acceptable in specific cases:
- Ensuring timestamp ordering in tests: `time.sleep(0.01)`
- Thread synchronization in concurrent tests
- Benchmark timing tests (using actual wall clock)

For E2E tests that require real AWS service delays (indexing, rate limits), keep the sleep but mark the test with `@pytest.mark.slow`.

---

## Frontend Testing Patterns (Vitest + React Testing Library)

Frontend tests use Vitest with React Testing Library. These patterns address common issues discovered through test maintenance.

### Context Provider Wrappers

Components that use React Context hooks (e.g., `useToast`, `useAuth`, `useTheme`) will fail with errors like `useX must be used within XProvider` if the test doesn't wrap the component in the required provider.

**Solution:** Create a test render function that includes all required providers:

```jsx
import { render } from '@testing-library/react';
import { ToastProvider } from '../context/ToastContext';
import { BrowserRouter } from 'react-router-dom';

// Reusable wrapper with common providers
const renderWithProviders = (ui, options = {}) => {
  const Wrapper = ({ children }) => (
    <BrowserRouter>
      <ToastProvider>
        {children}
      </ToastProvider>
    </BrowserRouter>
  );
  return render(ui, { wrapper: Wrapper, ...options });
};

// Usage
it('should render component that uses toast', () => {
  renderWithProviders(<MyComponent />);
  // ... assertions
});
```

**Common providers needed:**
- `ToastProvider` - For components using `useToast()` hook
- `BrowserRouter` - For components using `useNavigate()` or `<Link>`
- `QueryClientProvider` - For components using React Query hooks
- `ThemeProvider` - For components using theme context

### Keyboard Event Targeting

When testing keyboard events (e.g., Escape key to close modals), the event target must match where the event listener is attached.

**Problem:** Event listeners attached to `document` will not receive events fired on `window`:

```jsx
// Component attaches listener to document
useEffect(() => {
  const handleKeyDown = (e) => {
    if (e.key === 'Escape') onClose();
  };
  document.addEventListener('keydown', handleKeyDown);
  return () => document.removeEventListener('keydown', handleKeyDown);
}, [onClose]);
```

**Incorrect test (will not trigger handler):**
```jsx
// BAD: Event fired on window, listener is on document
fireEvent.keyDown(window, { key: 'Escape' });
```

**Correct test:**
```jsx
// GOOD: Event fired on document, matches listener target
fireEvent.keyDown(document, { key: 'Escape' });
```

**Rule:** Always verify where the event listener is attached in the component code and fire the test event on the same target.

### Async Assertions with waitFor

Focus management and other DOM updates that occur after React's render cycle require `waitFor` to avoid timing issues.

**Problem:** Focus is set in a `useEffect` or after state update:

```jsx
useEffect(() => {
  if (isOpen) {
    buttonRef.current?.focus();
  }
}, [isOpen]);
```

**Incorrect test (may fail intermittently):**
```jsx
// BAD: Focus may not be set yet
expect(button).toHaveFocus();
```

**Correct test:**
```jsx
// GOOD: Wait for focus to be applied
await waitFor(() => {
  expect(button).toHaveFocus();
});
```

**When to use `waitFor`:**
- Testing focus state after modal/dialog opens
- Testing DOM changes after async operations
- Testing state updates that trigger re-renders
- Testing animations or transitions

### Python Test Isolation with pytest.mark.forked

Some Python libraries have global state or backend conflicts that cause test failures when run in the same process as other tests.

**Example:** python-jose's cryptography backend conflicts with cryptography>=42.0.0:

```
JWSError: Expected instance of hashes.HashAlgorithm, got <class 'cryptography.hazmat.primitives.hashes.SHA256'>
```

**Solution:** Use `pytest.mark.forked` to run tests in isolated subprocesses:

```python
import pytest

# Apply to entire module
pytestmark = pytest.mark.forked

class TestTokenService:
    def test_create_token(self):
        # Runs in isolated subprocess
        ...
```

**When to use `pytest.mark.forked`:**
- Tests using python-jose with cryptography backend
- Tests that modify `sys.modules`
- Tests with global state that cannot be reset
- Tests patching module-level constants
- aiohttp/httpx mock pollution between tests

**Trade-off:** Slower execution (~50-100ms overhead per test) due to subprocess creation.
