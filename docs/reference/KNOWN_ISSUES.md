# Known Issues

This document tracks accepted limitations, pre-existing test failures, and technical debt that don't warrant immediate action. For active bugs and feature requests, see [GitHub Issues](https://github.com/aenealabs/aura/issues).

**Last Updated:** 2026-07-01

---

## Skipped Tests

### Deep Research Lambda Tests (mypy_boto3_dynamodb Missing)

**Status:** Skipped via pytest marker
**Date Added:** 2025-12-25
**Tests Affected:** 5 tests in `tests/lambda/chat/test_deep_research.py`

| Test | Description |
|------|-------------|
| `TestResearchEnums::test_research_status_values` | Validates ResearchStatus enum values |
| `TestResearchEnums::test_research_scope_values` | Validates ResearchScope enum values |
| `TestResearchEnums::test_research_urgency_values` | Validates ResearchUrgency enum values |
| `TestResearchTask::test_research_task_creation` | Tests ResearchTask dataclass creation |
| `TestResearchTask::test_research_task_to_dynamodb_item` | Tests DynamoDB item serialization |

**Error:** `ModuleNotFoundError: No module named 'mypy_boto3_dynamodb'`

**Root Cause:** The `mypy_boto3_dynamodb` type stubs package is not installed in the test environment. The source module imports are correctly wrapped in `TYPE_CHECKING`, but the test environment still triggers the import.

**Workaround:** Tests skipped via `pytestmark = pytest.mark.skip()` in the test file.

---

## Resolved Issues

### ~~CPU Memory Backend Tests (pytest-forked Teardown Conflict)~~ (RESOLVED - Dec 26, 2025)

**Error:** `AssertionError: assert col in needed_collectors, "previous item was not torn down properly"` at `_pytest/runner.py:514`

**Root Cause:** The pytest-forked plugin's `pytest_runtest_protocol` hook returns `True`, which tells pytest to skip the normal protocol (including setup/teardown). This leaves the parent process's `SetupState` out of sync when transitioning between test modules.

**Fix:** Added `_sync_setupstate_for_forked_test()` function and `pytest_runtest_protocol` hook in `tests/conftest.py` that properly synchronizes the SetupState after forked tests complete. The hook runs after pytest-forked's hook (using `trylast=True`) and ensures collectors are properly torn down before the next test runs.

### ~~Smoke Tests~~ (RESOLVED - Dec 6, 2025)

All 7 smoke tests in `tests/smoke/test_critical_paths.py` now pass. The API signature issues were fixed and tests updated to match current implementation.

**Tracking:** [GitHub Issue #6](https://github.com/aenealabs/aura/issues/6) (can be closed)

### ~~datetime.utcnow() Deprecation~~ (RESOLVED - Dec 6, 2025)

All `datetime.utcnow()` calls replaced with `datetime.now(timezone.utc)` across the codebase.

**Tracking:** [GitHub Issue #8](https://github.com/aenealabs/aura/issues/8) (can be closed)

### ~~Filesystem Indexer Tests~~ (RESOLVED - Dec 6, 2025)

All 30 tests in `tests/test_filesystem_indexer.py` now pass. The async fixture issues and assertion failures were fixed.

**Tracking:** [GitHub Issue #7](https://github.com/aenealabs/aura/issues/7) (closed)

### ~~Gremlin AiohttpTransport Event Loop Conflict~~ (RESOLVED - Dec 6, 2025)

Fixed by applying `nest_asyncio` patch in `src/services/neptune_graph_service.py:18-26`.
The patch enables nested event loops for gremlin-python compatibility with FastAPI/uvicorn.

### ~~Unawaited Coroutine Warnings~~ (RESOLVED - Dec 6, 2025)

Fixed in both Lambda handlers and their tests:
- `src/lambda/dns_blocklist_updater.py` - Changed to `asyncio.run()`
- `src/lambda/threat_intelligence_processor.py` - Changed to `asyncio.run()`
- `tests/test_lambda_dns_blocklist.py` - Tests now use `AsyncMock` directly
- `tests/test_lambda_threat_intelligence.py` - Tests now use `AsyncMock` directly

---

## Accepted Limitations

### CloudFormation Linting Warnings (cfn-lint)

The following cfn-lint warnings are suppressed in buildspecs. They are either false positives or intentional design decisions.

| Warning | Templates | Explanation | Suppression |
|---------|-----------|-------------|-------------|
| **W2001** (Parameter not used) | neptune-simplified.yaml, opensearch.yaml | **False positive.** VpcId IS passed by `buildspec-data.yml` (lines 64, 79) but cfn-lint doesn't trace it through `VPCOptions` references | `--ignore-checks W2001` |
| **W1020** (Fn::Sub without variables) | secrets.yaml, monitoring.yaml, aura-cost-alerts.yaml | **Intentional.** `Fn::Sub` used for consistency across templates even when no substitution needed | `--ignore-checks W1020` |
| **W3002** (Template file not found) | All templates | **Non-blocking.** Informational warning about relative paths in nested stacks | `--ignore-checks W3002` |
| **W3005** (DependsOn for intrinsic functions) | neptune-simplified.yaml, opensearch.yaml, dynamodb.yaml, s3.yaml | **Non-blocking.** Warns about implicit dependencies; explicit DependsOn not required | `--ignore-checks W3005` |

**Buildspec References:**
- Foundation: `deploy/buildspecs/buildspec-foundation.yml` (W3002)
- Data: `deploy/buildspecs/buildspec-data.yml` (W2001, W3002, W3005)
- Compute: `deploy/buildspecs/buildspec-compute.yml` (W3002)
- Application: `deploy/buildspecs/buildspec-application.yml` (W3002)
- Observability: `deploy/buildspecs/buildspec-observability.yml` (W1020, W3002)

---

### Coverage Status

- **Current:** 81.51%
- **Target:** 80%
- **Status:** Target achieved (Dec 6, 2025)
- **Tests:** 2,539 passing

### EKS on Fargate (GovCloud)

- EKS on Fargate is NOT available in AWS GovCloud
- Mitigation: Using EC2 Managed Node Groups instead
- See: `docs/cloud-strategy/GOVCLOUD_MIGRATION_SUMMARY.md`

### Tree-sitter Parse Timeout — Pinned to `<0.26`

**Status:** Accepted limitation (upstream-blocked)
**Date Added:** 2026-07-01
**Tracking:** Relocated from GitHub Issue #292 (closed as not-viable-as-specified); re-engage condition in `docs/DEFERRED_WORK_REGISTRY.md` (Upstream-maintainer-gate row)

The AST parser is pinned to `tree-sitter>=0.25.2,<0.26` (`requirements.txt`, `requirements-agents.txt`). 0.26.0 removed the `parser.timeout_micros` setter that `src/services/vulnerability_scanner/parsing/ast.py` uses to bound parse time — the DoS guard on untrusted customer/third-party code (`ParsingConfig.tree_sitter_timeout_ms` over 1 MB size-capped input).

Issue #292 proposed migrating to `parser.parse(source, progress_callback=...)` and relaxing the cap to `>=0.26.0`. A spike (verified 2026-07-01) showed that migration is **not viable on 0.26.0**: `progress_callback` is silently ignored for bytestring sources (never fires, cannot cancel) and **segfaults** when combined with a reader source. A real timeout on 0.26 therefore requires process-isolated parse workers, not the callback swap — an architectural change, not the one-site fix #292 assumed. The `<0.26` pin is stable meanwhile (0.25.2 ships cp312 wheels for the Python 3.12 runtime).

**Re-engage when:** py-tree-sitter ships a 0.26.x that fixes the reader + `progress_callback` segfault and restores a working bytestring parse timeout — OR the process-isolated-parser rewrite is scheduled independently.

---

## Resolution Process

1. For new issues, create a [GitHub Issue](https://github.com/aenealabs/aura/issues/new)
2. Once resolved, move to "Resolved Issues" section with date
3. Keep this document under 200 lines - archive old entries to `archive/` if needed
