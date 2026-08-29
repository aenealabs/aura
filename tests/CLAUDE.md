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

`TESTING=true` is set for the whole run by `tests/conftest.py` (via
`os.environ.setdefault`, so a test that deliberately wants the production
branch can still override it). Several endpoints branch on `TESTING` before
constructing a boto3 client -- `src/api/settings_endpoints.py:420` (log
retention sync Lambda) and `:893` (compliance settings sync Lambda) are the
current two. Assert the *guard short-circuits*, not that the variable is set;
see `tests/test_production_guards.py`.

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

## Frontend Tests Are a Separate Suite

`tests/` is Python only. The frontend has its own vitest suite under
`frontend/src/`, **1,880 tests across 80 files** (verified 2026-08-29), which is
not included in any `pytest --collect-only` count.

```bash
cd frontend
npm ci --legacy-peer-deps   # the flag is mandatory; see frontend/CLAUDE.md
npm run test:run
```

**Node 22 is required** (`^22.22.2 || ^24.15.0 || >=26.0.0`, declared in
`frontend/package.json` `engines`). On Node 20 every vitest worker fails to start
with `TypeError: webidl.util.markAsUncloneable is not a function`. npm only
*warns* on an `engines` mismatch, and a stale `node_modules` keeps the older
`undici`, so a local run can pass against a tree that no longer matches the
lockfile.

Both suites are gated on pull requests as of #415, in separate jobs in
`.github/workflows/code-quality.yml`: `Python Quality & Tests` and
`Frontend Quality & Tests`. Each has its own change detection, so a Python-only
PR does not run `npm ci` and a frontend-only PR does not run pytest. Before #415
the frontend suite ran on developer machines only.

---

## Test File Conventions

- Test files: `test_{service_name}.py` matching the service under test
- Test files are independently executable - safe for parallel worktree work
- Tests may contain intentional mock secrets, security anti-patterns, and placeholder keys for testing purposes (excluded from pre-commit scanning)

---

## Parallel Execution (`pytest -n auto`)

`-n auto` is supported and is expected to produce the same result as a serial
run. `tests/services/test_constraint_geometry/` was the last known directory
where it did not: it passed 403/403 serially and failed 134 of 403 under
xdist. Fixed in #412; that directory now runs 190 items and passes identically
with and without `-n auto`.

**Anti-pattern that caused it -- do not reintroduce.** Five parametrized tests
stashed a baseline on the test *class* on the first parameter value and read it
back on later ones:

```python
# WRONG -- writer and readers land on different xdist workers
if iteration == 0:
    TestCalculatorDeterminism._baseline_coherence = score.coherence
else:
    assert score.coherence == TestCalculatorDeterminism._baseline_coherence
```

xdist distributes parametrized cases across worker *processes*. The case that
writes the attribute routinely lands on a different worker from the ones that
read it, and the readers fail with `AttributeError`.

**Rule:** never carry state between parametrized cases via a class attribute,
module global, or any other cross-item channel. For a determinism assertion,
repeat inside a single test and compare every result against every other -- it
is parallel-safe and a stronger assertion than comparing each result against
one arbitrary baseline. That change also drops item count (403 -> 190 in that
directory) without dropping computations; the same work runs inside the tests
rather than as separate items.

Two latent defects were found in the same file and are worth recognising as
classes:

- An assertion comparing a value to itself (`assert result == pytest.approx(result, abs=0)`)
  passes unconditionally regardless of the code under test.
- An `expected` constant declared but never asserted, whose value did not match
  the real output. Anyone "completing" the test by asserting against it would
  have broken the build.

The class-attribute pattern was swept out of the whole tests tree in #412 and
verified with a positive control against the parent commit (7 writes before,
0 after).

---

## Mock Patterns

- Use mocks for external service boundaries (AWS APIs, LLM calls)
- Do NOT mock internal service interfaces unless testing failure scenarios
- Integration tests should validate real service interactions where feasible
- See `docs/reference/TESTING_STRATEGY.md` for the full testing pyramid and mock rationale

---

## Tests Cannot Reach Real AWS

**Mocking AWS is no longer opt-in.** Two autouse fixtures in `tests/conftest.py`
apply to every test:

- `_fake_aws_credentials_everywhere` (session-scoped) sets fake credentials for
  the whole run via `setdefault`. It does **not** overwrite a real credential
  you have exported -- blocking that is the other fixture's job. Its purpose is
  to make request signing possible so a failure surfaces as a named blocked
  call instead of an opaque `NoCredentialsError`.
- `_block_unmocked_aws_calls` (function-scoped) patches `URLLib3Session.send`
  and raises `UnmockedAWSCallError` naming the method and URL.

The patch sits at the HTTP transport layer rather than at botocore's
`before-send` event because moto registers its interception *at* `before-send`
via `BUILTIN_HANDLERS`; a guard there would race moto's handler and depend on
registration order. At the transport layer the semantics are unambiguous: moto
short-circuits above it, so anything arriving is by definition unmocked.

**What the failure looks like:**

```
UnmockedAWSCallError: Unmocked AWS call: POST https://ssm.us-east-1.amazonaws.com/
Tests must not reach real AWS. Use the moto fixtures (mock_aws_services,
mock_dynamodb, mock_s3) or mock the client. If this fired from production code,
check that its test-mode guard is keyed off TESTING rather than an AWS
environment variable.
```

**How to fix it:**

1. Wrap the test in a moto fixture (`mock_aws_services`, `mock_dynamodb`,
   `mock_s3`) or `mock_aws()`, or patch the client directly.
2. If the call came from production code rather than the test, the code's
   test-mode guard is wrong. Key it off `TESTING`, never off an AWS environment
   variable. `src/agents/spawnable_agent_adapters.py` used
   `use_mock = not AWS_DEFAULT_REGION and not AWS_REGION`, which conflates "a
   region is configured" with "we are in production" -- `AWS_DEFAULT_REGION` is
   exported in most shell profiles, so unit tests silently selected the real
   service and reached SSM Parameter Store. That was a real bug the guard caught
   on its first run (#411).
3. Only if the test genuinely needs the real transport (a contract test against
   a local endpoint, say), unpatch locally. The fixture restores the original
   in a `finally`, so the patch cannot leak into the next test.

A guard that fires under moto would be worse than no guard, so
`tests/test_aws_call_guard.py` asserts both directions: fires on a real call,
stays silent under `mock_aws()` including a create/put/get round trip. Keep it
that way if you touch the guard.

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
