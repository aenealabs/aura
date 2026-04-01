# Project Aura - API Reference

Quick reference for core platform APIs used in smoke tests and production code.

---

## AST Parser Agent

**Location:** `src/agents/ast_parser_agent.py`

### Constructor
```python
ASTParserAgent()  # No parameters
```

### Key Methods
```python
# Parse file (NOT parse_code) - Returns list of CodeEntity objects
parse_file(self, file_path: Path) -> list[CodeEntity]

# Supported extensions
supported_extensions: set = {".py", ".js", ".jsx", ".ts", ".tsx"}
```

**Example:**
```python
from src.agents.ast_parser_agent import ASTParserAgent
from pathlib import Path

parser = ASTParserAgent()
result = parser.parse_file(Path("test.py"))
```

---

## Context Objects

**Location:** `src/agents/context_objects.py`

### ContextSource (Enum)
```python
class ContextSource(Enum):
    GRAPH_STRUCTURAL = "graph"      # NOT "GRAPH"
    VECTOR_SEMANTIC = "vector"
    SECURITY_POLICY = "security"
    REMEDIATION = "remediation"
    USER_PROMPT = "user_prompt"
    COMPLIANCE = "compliance"
```

### ContextItem
```python
ContextItem(
    content: str,
    source: ContextSource,
    confidence: float,
    metadata: dict
)
```

### HybridContext
```python
HybridContext(
    items: list[ContextItem],
    query: str,
    target_entity: str
)
```

**Example:**
```python
from src.agents.context_objects import ContextItem, ContextSource, HybridContext

item = ContextItem(
    content="Test",
    source=ContextSource.GRAPH_STRUCTURAL,
    confidence=0.95,
    metadata={}
)

context = HybridContext(
    items=[item],
    query="test query",
    target_entity="test_entity"
)
```

---

## Neptune Graph Service

**Location:** `src/services/neptune_graph_service.py`

### Constructor
```python
NeptuneGraphService(
    mode: NeptuneMode = NeptuneMode.MOCK,
    endpoint: str | None = None,
    port: int = 8182,
    use_iam_auth: bool = True
)
```

### Key Methods
```python
# Add entity (note: line_number NOT start_line/end_line)
add_code_entity(
    self,
    name: str,
    entity_type: str,
    file_path: str,
    line_number: int,           # Single line number
    parent: str | None = None,
    metadata: dict | None = None
) -> str

# Search (returns list of dicts, NOT entities)
search_by_name(self, pattern: str) -> list[dict]

# Query by file
query_by_file(self, file_path: str) -> list[dict]
```

**Example:**
```python
from src.services.neptune_graph_service import NeptuneGraphService, NeptuneMode

service = NeptuneGraphService(mode=NeptuneMode.MOCK)

entity_id = service.add_code_entity(
    name="my_function",
    entity_type="function",
    file_path="test.py",
    line_number=10,
    metadata={}
)

results = service.search_by_name("my_function")
```

---

## Monitoring Service

**Location:** `src/agents/monitoring_service.py`

### Constructor
```python
MonitorAgent()  # No parameters
```

### Key Methods
```python
# Get report (NOT get_execution_report) - Actual method is finalize_report
finalize_report(self) -> dict

# Record activity
record_agent_activity(self, tokens_used: int, loc_generated: int = 0)

# Record security finding
record_security_finding(self, agent: AgentRole, finding: str, severity: str = "High", status: str = "Detected")

# Properties
start_time: datetime
tasks: list
```

**Example:**
```python
from src.agents.monitoring_service import MonitorAgent

monitor = MonitorAgent()
report = monitor.get_execution_report()
```

---

## Observability Service

**Location:** `src/services/observability_service.py`

### Constructor
```python
ObservabilityService()  # No parameters
```

### Key Methods
```python
# Track latency (context manager)
@contextmanager
track_latency(self, operation: str)

# Record metrics
record_latency(self, operation: str, duration_seconds: float)
record_request(self, endpoint: str)
record_error(self, operation: str, error: Exception | None = None)
record_success(self, operation: str)
record_resource_usage(self, resource: str, usage_percent: float)

# Get metrics
get_p95_latency(self, operation: str) -> float | None
get_average_latency(self, operation: str) -> float | None
get_error_rate(self, operation: str) -> float
get_success_rate(self, operation: str) -> float
get_service_health(self) -> ServiceHealth
get_health_report(self) -> dict

# Alerting
create_alert(
    self,
    severity: AlertSeverity,
    service: str,
    message: str,
    metadata: dict | None = None
)
```

**Example:**
```python
from src.services.observability_service import ObservabilityService

monitor = ObservabilityService()

# Track operation
with monitor.track_latency("test.operation"):
    # Do work
    pass

# Get metrics
health = monitor.get_service_health()
report = monitor.get_health_report()
```

---

## Health Check Endpoints

**Location:** `src/api/health_endpoints.py`

### Constructor
```python
HealthCheckEndpoints(
    neptune_service=None,
    opensearch_service=None,
    bedrock_service=None
)
```

### Key Methods (all async)
```python
async def liveness_probe(self) -> dict
async def readiness_probe(self) -> dict
async def startup_probe(self) -> dict
async def detailed_health(self) -> dict
async def aws_health_check(self) -> dict
```

**Example:**
```python
from src.api.health_endpoints import HealthCheckEndpoints

health = HealthCheckEndpoints()

# In async context
status = await health.liveness_probe()
```

---

## Common Patterns

### 1. Production Monitoring
```python
from src.services.observability_service import get_monitor

monitor = get_monitor()  # Singleton

with monitor.track_latency("orchestrator.execute"):
    result = orchestrator.execute(task)
```

### 2. Health Checks
```python
from src.api.health_endpoints import HealthCheckEndpoints

health = HealthCheckEndpoints(
    neptune_service=neptune,
    opensearch_service=opensearch
)

# Check readiness
status = await health.readiness_probe()
if status["status"] == "ready":
    # Accept traffic
    pass
```

### 3. Graph Operations
```python
from src.services.neptune_graph_service import NeptuneGraphService, NeptuneMode

# Development (MOCK mode)
neptune = NeptuneGraphService(mode=NeptuneMode.MOCK)

# Production (AWS mode)
neptune = NeptuneGraphService(
    mode=NeptuneMode.AWS,
    endpoint="neptune.aura.local",
    port=8182
)

# Add entity
entity_id = neptune.add_code_entity(
    name="vulnerable_function",
    entity_type="function",
    file_path="auth.py",
    line_number=42
)

# Search
results = neptune.search_by_name("vulnerable")
```

---

## API Differences from Initial Assumptions

| Component | Assumed API | Actual API |
|-----------|-------------|------------|
| **ASTParserAgent** | `parse_code()` | `parse_file()` |
| **ASTParserAgent** | `__init__(llm_client)` | `__init__()` (no params) |
| **ContextSource** | `GRAPH` | `GRAPH_STRUCTURAL` |
| **HybridContext** | `__init__()` (no params) | `__init__(items, query, target_entity)` |
| **NeptuneGraphService** | `start_line, end_line` | `line_number` (single) |
| **NeptuneGraphService** | `get_code_entity()` | Returns dict from `search_by_name()` |
| **MonitorAgent** | `get_execution_report()` | `finalize_report()` only |
| **ASTParserAgent** | Returns `dict` | Returns `list[CodeEntity]` |
| **HybridContext** | `get_items_count()` | `len(context.items)` |

---

## Testing Patterns

### Smoke Test Pattern
```python
import pytest

@pytest.mark.smoke
def test_component_works():
    from src.services.observability_service import ObservabilityService

    monitor = ObservabilityService()

    with monitor.track_latency("test.op"):
        pass

    assert monitor.get_average_latency("test.op") is not None
```

### Performance Test Pattern
```python
import pytest
import time

@pytest.mark.performance
def test_operation_is_fast():
    from src.services.neptune_graph_service import NeptuneGraphService, NeptuneMode

    service = NeptuneGraphService(mode=NeptuneMode.MOCK)

    start = time.time()
    results = service.search_by_name("test")
    elapsed = time.time() - start

    assert elapsed < 0.5, f"Too slow: {elapsed}s"
```

---

## Production Deployment

### Health Check Endpoints (FastAPI)
```python
from fastapi import FastAPI
from src.api.health_endpoints import setup_health_endpoints_fastapi

app = FastAPI()

services = {
    "neptune": neptune_service,
    "opensearch": opensearch_service,
    "bedrock": bedrock_service
}

await setup_health_endpoints_fastapi(app, services)

# Endpoints available:
# GET /health - AWS ALB
# GET /health/live - Kubernetes liveness
# GET /health/ready - Kubernetes readiness
# GET /health/startup - Kubernetes startup
# GET /health/detailed - Monitoring dashboards
```

### Observability Integration
```python
from src.services.observability_service import get_monitor, monitored

# Singleton pattern
monitor = get_monitor()

# Decorator pattern
@monitored("my_service.process")
def process_request(data):
    return do_work(data)

# Context manager pattern
with monitor.track_latency("my_service.process"):
    result = do_work(data)
```

---

## Quick Reference

| Need | Use |
|------|-----|
| Parse code file | `ASTParserAgent().parse_file(path)` |
| Store in graph | `neptune.add_code_entity(name, type, path, line)` |
| Search graph | `neptune.search_by_name(pattern)` |
| Track latency | `monitor.track_latency(operation)` |
| Check health | `monitor.get_service_health()` |
| Get metrics | `monitor.get_health_report()` |
| Health endpoint | `health.readiness_probe()` |
