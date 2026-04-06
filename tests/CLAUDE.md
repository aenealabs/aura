# Testing Guide

> Full testing strategy: `docs/reference/TESTING_STRATEGY.md`

---

## Coverage Threshold

**The minimum test coverage threshold of 70% in `pyproject.toml` MUST NOT be lowered under any circumstances.**

- The `fail_under = 70` setting in `[tool.coverage.report]` is a hard requirement
- If coverage drops below 70%, add more tests to increase coverage - never lower the threshold
- This applies to all environments (dev, CI, production)
- Violations require explicit written approval from the project owner

---

## Running Tests

```bash
pytest tests/                          # Run all tests
pytest tests/test_context_objects.py   # Run specific test
pytest -v                              # Verbose output
pytest -n auto                         # Parallel execution
pytest -m integration                  # Integration tests only
```

---

## Test File Conventions

- Test files: `test_{service_name}.py` matching the service under test
- Test files are independently executable - safe for parallel worktree work
- Tests may contain intentional mock secrets, security anti-patterns, and placeholder keys for testing purposes (excluded from pre-commit scanning)

---

## Mock Patterns

- Use mocks for external service boundaries (AWS APIs, LLM calls)
- Do NOT mock internal service interfaces unless testing failure scenarios
- Integration tests should validate real service interactions where feasible
- See `docs/reference/TESTING_STRATEGY.md` for the full testing pyramid and mock rationale

---

## What Tests Must Cover

- All business logic in `src/services/`
- Integration tests for multi-service workflows
- Edge cases and error handling paths
- Security-sensitive code (auth, input validation, sandbox boundaries)
