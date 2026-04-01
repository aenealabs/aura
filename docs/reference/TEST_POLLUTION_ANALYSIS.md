# Test Pollution Analysis: Forked Markers and Coverage

## Problem Statement

Tests that pass in isolation fail when run in the full suite due to module state pollution. The pytest-forked marker solves this by running each test in a subprocess, but prevents coverage measurement since coverage.py doesn't track forked processes by default.

## Root Cause Analysis

### 1. Python Enum Identity Issue

Python enums compare by object identity, not value:

```python
# After module removal and reimport:
from src.services.neptune_graph_service import NeptuneMode
mode1 = NeptuneMode.MOCK

del sys.modules['src.services.neptune_graph_service']

from src.services.neptune_graph_service import NeptuneMode
mode2 = NeptuneMode.MOCK

assert mode1 == mode2  # FAILS! Different class identities
assert mode1.value == mode2.value  # PASSES - same string value
```

### 2. Module State Pollution Sources

Several mechanisms cause inconsistent module state:

| Source | Mechanism | Effect |
|--------|-----------|--------|
| `patch.dict("sys.modules", ...)` | Temporarily replaces modules | Leaves stale references |
| `importlib.reload()` | Creates new module object | New enum class identities |
| `pytest_runtest_teardown` | Removes non-protected modules | Partial cleanup |
| Test fixture cleanup | May not fully restore state | Inconsistent globals |

### 3. Protected Prefixes in conftest.py

The `_protected_prefixes` tuple prevents cleanup of core modules:

```python
_protected_prefixes = (
    "src",           # All src.* modules protected
    "src.services",  # Service modules never cleaned
    "jose", "httpx", # Auth libraries protected
    "torch",         # Cannot unload safely
    ...
)
```

This creates a paradox: modules are protected from cleanup, but patches within tests can still modify their state, leading to inconsistency.

### 4. Why Forked Markers Work

Each test runs in a fresh subprocess:
- Fresh `sys.modules` cache
- Fresh enum class identities
- No state pollution between tests
- Complete isolation

## Affected Test Files

| File | Tests | Pollution Type |
|------|-------|----------------|
| `test_neptune_graph_service.py` | 124 | Enum identity mismatch |
| `test_opensearch_vector_service.py` | 91 | Enum identity mismatch |
| `test_job_persistence_service.py` | 88 | AWS mode mock pollution |
| `test_health_endpoints.py` | 55 | Logger mock not applied |
| `test_memory_benchmark.py` | 48 | Iterator/mock pollution |
| `test_filesystem_indexer.py` | 79 | git.Repo mock pollution |

## Proposed Solutions

### Option A: Subprocess Coverage Tracking (Recommended)

Enable coverage.py subprocess tracking by:

1. Create `coverage_subprocess.pth` in site-packages:
```python
import coverage; coverage.process_startup()
```

2. Set environment variable before tests:
```bash
COVERAGE_PROCESS_START=pyproject.toml pytest tests/
```

3. Coverage will track all subprocesses including forked tests.

**Pros:** Full coverage tracking, no test changes needed
**Cons:** Requires site-packages modification, CI configuration

### Option B: Use `.value` for Enum Comparisons

Change test assertions from:
```python
assert service.mode == NeptuneMode.MOCK
```

To:
```python
assert service.mode.value == NeptuneMode.MOCK.value
```

**Pros:** Simple change, no infrastructure needed
**Cons:** Less elegant, doesn't fix underlying pollution

### Option C: Class-Level Module Reset Fixture

Add fixture that resets module state before each test class:

```python
@pytest.fixture(scope="class", autouse=True)
def reset_neptune_module():
    """Reset neptune module to ensure fresh enum identity."""
    import sys
    import importlib

    mod_name = "src.services.neptune_graph_service"
    if mod_name in sys.modules:
        importlib.reload(sys.modules[mod_name])

    yield
```

**Pros:** Targeted fix, maintains enum identity within class
**Cons:** Must be added to each affected test file

### Option D: Expand Module Refresh List

Add affected modules to `_refresh_src_modules_for_fork()`:

```python
modules_to_refresh = [
    "src.api.auth",
    "src.services.api_rate_limiter",
    "src.config",
    "src.services.neptune_graph_service",      # Add
    "src.services.opensearch_vector_service",  # Add
    "src.services.job_persistence_service",    # Add
]
```

**Pros:** Centralized fix
**Cons:** Only helps forked tests, doesn't fix non-forked runs

## Recommended Approach

1. **Short-term:** Keep forked markers to ensure tests pass
2. **Medium-term:** Implement Option A (subprocess coverage) for proper coverage tracking
3. **Long-term:** Consider Option C fixtures for tests that truly need isolation

## Implementation Notes

### For Option A (Subprocess Coverage)

Add to CI workflow:
```yaml
- name: Run tests with subprocess coverage
  run: |
    echo "import coverage; coverage.process_startup()" > /tmp/coverage_subprocess.pth
    cp /tmp/coverage_subprocess.pth $(python -c "import site; print(site.getsitepackages()[0])")
    COVERAGE_PROCESS_START=pyproject.toml pytest tests/ --cov --cov-report=xml
```

### pyproject.toml Configuration

```toml
[tool.coverage.run]
parallel = true
concurrency = ["multiprocessing"]
sigterm = true
```

## References

- [Coverage.py Subprocess Measurement](https://coverage.readthedocs.io/en/latest/subprocess.html)
- [pytest-forked Issue #67](https://github.com/pytest-dev/pytest-forked/issues/67)
- [Python Enum Identity](https://docs.python.org/3/library/enum.html#comparisons)
