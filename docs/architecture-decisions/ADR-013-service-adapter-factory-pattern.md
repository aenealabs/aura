# ADR-013: Service Adapter and Factory Pattern for Mock-to-Production Switching

**Status:** Deployed
**Date:** 2025-12-01
**Decision Makers:** Project Aura Team

## Context

Project Aura's multi-agent system relies on external services (Neptune graph database, OpenSearch vector store) for context retrieval. During development, we use mock implementations to enable rapid iteration without AWS infrastructure costs. For production, we need real service integrations.

The challenge: **Interface mismatch between mock and real services**.

- Mock `GraphBuilderAgent` uses methods like `parse_source_code()` and `run_gremlin_query()`
- Real `NeptuneGraphService` uses methods like `add_code_entity()` and `find_related_code()`

Without architectural intervention, switching between mock and production would require:
1. Conditional imports scattered throughout agent code
2. Business logic changes in every consumer
3. Multiple code paths to maintain and test

## Decision

We adopted the **Adapter Pattern** combined with **Factory Functions** to achieve zero-code-change deployment switching.

### Adapter Pattern

Wrapper classes translate real service interfaces to match expected mock interfaces:

```python
# src/services/service_adapters.py
class NeptuneGraphAdapter:
    """Wraps NeptuneGraphService with GraphBuilderAgent interface."""

    def __init__(self, neptune_service: NeptuneGraphService):
        self.neptune = neptune_service
        self.ckge_graph = {}  # Local cache for compatibility

    def run_gremlin_query(self, source_entity: str) -> list[str]:
        """Translate mock interface call to real Neptune operations."""
        related = self.neptune.find_related_code(source_entity, max_depth=2)
        # Convert Neptune response to expected string format
        return [f"Structural Context (Graph): {source_entity} integrates with: ..."]
```

### Factory Functions

Environment-aware functions instantiate the correct implementation:

```python
def create_graph_agent(use_real: bool | None = None) -> GraphAgentProtocol:
    """Factory: auto-detects from environment variables."""
    if use_real is None:
        use_real = (
            os.getenv("NEPTUNE_ENDPOINT") is not None
            and os.getenv("USE_MOCK_SERVICES", "").lower() != "true"
        )

    if use_real:
        neptune = NeptuneGraphService(mode=NeptuneMode.AWS, endpoint=...)
        return NeptuneGraphAdapter(neptune)

    return GraphBuilderAgent()  # Mock
```

### Protocol Classes

Python typing protocols define the expected interface contract:

```python
class GraphAgentProtocol(Protocol):
    """Protocol defining the GraphBuilderAgent interface."""
    def parse_source_code(self, _code_content: str, filename: str | Path) -> dict[str, Any]: ...
    def add_node(self, node_id: str, label: str, **properties: Any) -> None: ...
    def run_gremlin_query(self, source_entity: str) -> list[str]: ...
```

### Consumer Usage

Agent code uses factories without knowledge of underlying implementation:

```python
# src/agents/agent_orchestrator.py
from src.services.service_adapters import create_graph_agent, create_vector_store

class AgentOrchestrator:
    def __init__(self):
        # Auto-detects real vs mock based on environment
        self.graph_agent = create_graph_agent()
        self.vector_store = create_vector_store()
```

## Alternatives Considered

### 1. Direct Refactoring (Rejected)

Refactor all mock classes to match real service interfaces exactly.

**Pros:**
- Simpler architecture (no adapters)
- Direct coupling reduces indirection

**Cons:**
- Breaking change to existing tests and integrations
- Mock implementations become tightly coupled to AWS service APIs
- Future AWS API changes would cascade to all mocks

### 2. Dependency Injection Framework (Rejected)

Use a DI framework like `dependency-injector` or `injector`.

**Pros:**
- Industry-standard pattern for large applications
- Automatic lifecycle management
- Built-in testing utilities

**Cons:**
- Additional dependency and learning curve
- Overkill for our current service count (2 services)
- Framework lock-in

### 3. Conditional Imports Throughout (Rejected)

Scatter `if PRODUCTION: import real else: import mock` throughout codebase.

**Pros:**
- No architectural overhead
- Explicit at point of use

**Cons:**
- Code duplication in every consumer
- Easy to miss conditions when adding new consumers
- Harder to test edge cases

### 4. Configuration-Based Service Loader (Considered)

Use a configuration file (YAML/JSON) to specify service implementations.

**Pros:**
- Externalized configuration
- Easy to modify without code changes

**Cons:**
- More complex than environment variables
- Requires configuration management
- Could be added later if needed (factory pattern doesn't preclude this)

## Consequences

### Positive

- **Zero-Code Deployment Switching**: Same codebase runs with mocks locally and real services in AWS
- **Interface Stability**: Consumer code never changes regardless of backend implementation
- **Testability**: Factories can force mock mode via `use_real=False` parameter
- **Gradual Migration**: Services can be switched independently (e.g., real Neptune + mock OpenSearch)
- **Environment Variable Driven**: `NEPTUNE_ENDPOINT`, `OPENSEARCH_ENDPOINT`, `USE_MOCK_SERVICES` control behavior
- **Protocol Contracts**: Python typing protocols provide IDE support and type checking

### Negative

- **Adapter Maintenance**: Each real service requires an adapter class (currently 2, may grow)
- **Indirection Layer**: Debugging requires understanding adapter translation
- **Potential Behavior Drift**: Mock and real implementations could diverge subtly

### Neutral

- **Protocol Evolution**: Adding new methods to protocols requires updating both mock and adapter
- **Error Handling**: Adapters must translate real service exceptions to expected error formats

## Implementation Files

| File | Purpose |
|------|---------|
| `src/services/service_adapters.py` | Adapter classes and factory functions |
| `src/agents/agent_orchestrator.py` | Primary consumer using factories |
| `src/agents/validator_agent.py` | Extended with sandbox factory |

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `NEPTUNE_ENDPOINT` | Neptune cluster endpoint | None (mock mode) |
| `OPENSEARCH_ENDPOINT` | OpenSearch domain endpoint | None (mock mode) |
| `USE_MOCK_SERVICES` | Force mock mode if "true" | None (auto-detect) |
| `NEPTUNE_PORT` | Neptune port | 8182 |
| `OPENSEARCH_PORT` | OpenSearch port | 443 |
| `VECTOR_DIMENSION` | Embedding vector dimension | 1024 |

## Testing Strategy

```python
# Force mock mode in unit tests
def test_orchestrator_with_mocks():
    os.environ["USE_MOCK_SERVICES"] = "true"
    orchestrator = AgentOrchestrator()
    # Tests run against mock implementations

# Integration tests with real services
@pytest.mark.integration
def test_orchestrator_with_neptune():
    os.environ["NEPTUNE_ENDPOINT"] = "real-endpoint"
    os.environ.pop("USE_MOCK_SERVICES", None)
    orchestrator = AgentOrchestrator()
    # Tests run against real Neptune
```

## References

- [Adapter Pattern (GoF)](https://refactoring.guru/design-patterns/adapter)
- [Factory Method Pattern](https://refactoring.guru/design-patterns/factory-method)
- [Python Protocols (PEP 544)](https://peps.python.org/pep-0544/)
- `src/services/neptune_graph_service.py` - Real Neptune service
- `src/services/opensearch_vector_service.py` - Real OpenSearch service
- `src/agents/agent_orchestrator.py` - Mock implementations
