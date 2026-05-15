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

A per-test wall-clock cap of 120 seconds is enforced via `pytest-timeout`
(`--timeout=120 --timeout-method=thread` in default `addopts`). Override
for legitimately long tests via `@pytest.mark.timeout(N)` at the file or
function level, or `--timeout=N` on the command line.

`tests/performance/` is excluded from default collection via
`--ignore=tests/performance` in `pyproject.toml` `addopts`. It runs on
the dedicated `.github/workflows/benchmarks.yml` workflow on a pinned
runner. Local invocation:

```bash
pytest tests/performance/ -m performance --no-cov -v
```

To update perf baselines after a deliberate perf-relevant change, see
`tests/performance/README.md` -- the rebaseline procedure requires
three runs on the target environment plus explicit reviewer sign-off.

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

---

## Linux Test Harness (on-demand, not per-PR)

The Podman/Docker harness at `deploy/docker/test-harness/` runs pytest on Linux 3.12-slim. Its purpose is **closing the ~6,576 macOS-fork skips** caused by darwin's Objective-C runtime forbidding `fork()` after torch loads (see the guard at `tests/conftest.py` line 1042-1048). On Linux there's no Objective-C runtime to taint so `pytest.mark.forked` tests run normally.

```bash
scripts/run-tests-in-container.sh                  # full suite
scripts/run-tests-in-container.sh tests/test_x.py  # subset
scripts/run-tests-in-container.sh --shell          # interactive bash
scripts/run-tests-in-container.sh --rebuild        # force image rebuild
```

**When to use:**

- Validating changes to code under `pytest.mark.forked` (torch / neural memory / JEPA / RLM / constraint geometry / GPU scheduler).
- Reproducing a CI failure locally without waiting on CodeBuild.
- Spot-checking that a fix didn't introduce regressions in the forked tests darwin can't run.

**When NOT to use:**

- Per-PR validation. CodeBuild already runs the full suite on Linux-native (no emulation penalty); the harness re-runs the same tests under `linux/amd64` emulation at ~2x wall-clock. Burning extra developer time per push isn't worth the duplicated signal.
- Day-to-day inner loop. macOS native pytest is faster for the tests that DO run on macOS; let the harness be a "I'm about to push" or "CI is red, repro locally" tool.

Source of truth for "did all tests pass on Linux" remains CodeBuild. Phase 2 promotion (private ECR base, CI-built, hash-pinned) is tracked in issue #195.

---

## #194 Regression Lint (AURA194)

`tests/_lint_sys_modules.py` is an AST scanner that flags module-collection-time `sys.modules` mutations and `importlib.reload()` calls -- the exact pattern that caused issue #194's last residual (top-level `del sys.modules["src.services.bedrock_llm_service"]` in `test_bedrock_llm_edge_cases.py` left other modules' cached enum-class references stale, producing identity-mismatch failures with identical reprs).

The lint runs automatically during `pytest_configure` in **warn mode** -- it prints findings to stderr but does not fail collection. 151 legacy violations exist as of 2026-05-14; strict mode will land in a separate change after they're either fixed (move the mutation into a function-scoped fixture) or grandfathered with `# noqa: AURA194` on the offending line.

Reproduce the scan on demand:

```bash
python -m tests._lint_sys_modules tests/
```

If you're writing a new test that needs to mock a module:

- Put the `sys.modules[...] = mock_x` calls inside a **function-scoped** fixture (`@pytest.fixture` with default scope). The lint only flags top-level body.
- If you genuinely need a module-scoped mock, use `@pytest.fixture(scope="module")` and restore in a finalizer.
- Avoid module-scoped `del sys.modules[...]` at all costs -- that's what #194 was.
