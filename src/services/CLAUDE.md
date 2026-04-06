# Python Services Development Guide

> Universal security rules are in the root `CLAUDE.md`. This file covers service-specific conventions.

---

## Technology Stack

- **Language:** Python 3.11+
- **Framework:** FastAPI
- **LLM Integration:** OpenAI GPT-4, Anthropic Claude (via Bedrock)
- **Graph Database:** AWS Neptune (Gremlin) at `neptune.aura.local:8182`
- **Vector Database:** AWS OpenSearch at `opensearch.aura.local:9200`

---

## Code Quality Standards

- **Type hints:** Required on all public functions and class methods
- **Docstrings:** Required for all public functions/classes
- **Naming:** Descriptive, single responsibility, DRY principle
- **Formatting:** `black --line-length=88` (auto-enforced by pre-commit)
- **Linting:** `flake8 --max-line-length=120`
- **Import ordering:** `isort --profile=black`
- **Error handling:** Proper try-catch, input validation, edge case coverage

---

## Service Architecture Patterns

- Services are organized as single-file modules or package directories under `src/services/`
- Shared dependencies: `bedrock_llm_service`, `neptune_graph_service`, `opensearch_vector_service`
- Agent orchestrators coordinate multi-step workflows (see `security_agent_orchestrator.py`, `cognitive_memory_service.py`)

---

## Independent Service Packages (Fork-Join Safe)

These packages only import within themselves and are safe for parallel worktree-isolated work:

- `rlm/` - RecursiveContextEngine (100x context scaling)
- `jepa/` - EmbeddingPredictor (2.85x inference efficiency)
- `constraint_geometry/` - Deterministic cortical discrimination
- `gpu_scheduler/` - Self-service GPU job management
- `env_validator/` - Cross-environment validation
- `airgap/` - Air-gapped deployment support
- `vulnerability_scanner/` - Native scanning engine

---

## Shared Dependency Cluster (NOT Fork-Join Safe)

These services share `bedrock_llm_service`, `neptune_graph_service`, and `opensearch_vector_service`. Coordinate changes carefully:

- `constitutional_ai/` (imports bedrock, semantic cache)
- Most single-file services under `src/services/`
- Agent orchestrators

---

## Testing

- Every service must have corresponding tests in `tests/`
- Minimum 70% coverage threshold (enforced in `pyproject.toml`)
- Run: `pytest tests/test_{service_name}.py -v`
- Full guide: `docs/reference/TESTING_STRATEGY.md`
