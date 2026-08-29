# GitHub Actions Setup Guide

> **Canonical doc:** [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)
> **This doc covers:** GitHub Actions alternative for CI/CD; complements but does not replace the CodeBuild-based deploy chain.
>
> For the streamlined one-command deploy (`./deploy/deploy.sh
> deploy <env>`) and the prerequisites-and-bootstrap quickstart,
> read DEPLOYMENT_GUIDE.md first; this doc assumes that
> baseline.


**Project Aura - Automated Code Quality and Documentation Checks**

This guide explains the GitHub Actions workflows configured for Project Aura to ensure code quality, security, and compliance from Day 1.

---

## Overview

Project Aura uses GitHub Actions for automated CI/CD workflows to:

1. **Run Python code quality checks** (Black, Flake8, MyPy, Bandit)
2. **Lint changed CloudFormation templates** (cfn-lint, since #406)
3. **Lint, test and build the frontend** (eslint, vitest, Vite, since #415)
4. **Execute security scans** (Bandit, Trivy)
5. **Run automated tests** (pytest with coverage)
6. **Run the repo's own pre-commit hooks** scoped to the diff (includes `markdownlint`)

**Why GitHub Actions?**
- Auditable run logs supporting NIST 800-53 SA-11 / CM-3 / AU-12 evidence
- Enforced centrally; cannot be bypassed the way a local git hook can
- 2,000 free minutes/month on public repos, 3,000 on private repos with GitHub Pro

---

## Workflows

`.github/workflows/` contains ten workflows. The three pull-request quality gates all live in a
single file, `code-quality.yml` -- there is **no** separate frontend or CloudFormation workflow, and
there is no `lint-markdown.yml`. Markdown linting is the `markdownlint` pre-commit hook
(`.pre-commit-config.yaml:301-305`), run in CI by the diff-scoped `pre-commit` step described below.

### 1. Code Quality Checks (`code-quality.yml`)

**Triggers:**
- Pull requests to `main` or `develop` touching `src/`, `tests/`, `deploy/cloudformation/**`,
  `frontend/**`, `requirements*.txt`, `pyproject.toml`, `setup.py`, `setup.cfg`, or the workflow
  file itself
- Pushes to `main` touching `src/`, `tests/`, `deploy/cloudformation/**` or `frontend/**`
  (lint only; the full suite is PR-scoped)
- Manual trigger via `workflow_dispatch`

**Jobs:**

| Job name | Required check? | What it does |
|---|---|---|
| `Check Trigger Type` | No | Resolves `run_full_tests` -- true for pull requests and manual runs, false for pushes |
| `Python Quality & Tests` | **Yes** | Change detection, cfn-lint, pre-commit, Black, Flake8, MyPy, Bandit, pytest + coverage |
| `Security Scanning` | No | Trivy filesystem scan, SARIF upload to the GitHub Security tab |
| `Frontend Quality & Tests` | No | eslint, vitest, Vite build on Node 22 |

#### Change detection: what actually runs

`Python Quality & Tests` opens with a `Detect changed areas` step that resolves `python_changed` and
`cfn_changed` from the diff window (PR base..head, else push before..after, else `HEAD^..HEAD`). The
Python-only steps and the cfn-lint steps are each gated on their flag, so a template-only PR does not
pay for the torch install and the full test suite, and a Python-only PR does not pay for cfn-lint.
`Frontend Quality & Tests` runs its own equivalent detection so it does not have to wait on the
Python job.

| Changed tree | Python steps | cfn-lint step | Frontend job |
|---|---|---|---|
| `src/`, `tests/`, Python config | Run | Skip | Skip |
| `deploy/cloudformation/**` only | Skip | Run on each changed template | Skip |
| `frontend/**` only | Skip | Skip | Run |
| `.github/workflows/code-quality.yml` | Run | Only if templates also changed | Run |
| Diff window unresolvable | Run | Run | Run |

**The detectors key on path prefixes, not on file type.** `python_changed` matches
`^(src/|tests/|requirements.*\.txt$|pyproject\.toml$|setup\.(py|cfg)$|\.github/workflows/code-quality\.yml$)`
(`code-quality.yml:132`). There is no `.md` exclusion, so **a markdown-only edit under `src/` or
`tests/` runs the full Python job** -- torch install, Black, Flake8, MyPy, Bandit and the whole
pytest suite. This is not hypothetical: #420 changed one file, `tests/CLAUDE.md`, and its
`Python Quality & Tests` job ran 19m44s (run `33238518088`, `06:27:55Z` to `06:47:39Z`, against a
`timeout-minutes` ceiling of 25). Markdown anywhere else in the tree, including `docs/`, costs
nothing.

The full run buys no coverage that a markdown diff does not already get: the `pre-commit` step runs
unconditionally regardless of `python_changed` and carries the markdown hooks. Narrowing the pattern
would be safe in principle -- but it is a change to a required check, so the fail-safe direction
matters more than the minutes, and the current behaviour errs the right way. Flagged rather than
changed; if it is fixed, exclude `.md` explicitly rather than enumerating Python extensions, so a new
Python file type cannot silently fall outside the gate.

Three properties are deliberate:

1. **Trigger paths and job-body gating are separate mechanisms.** `deploy/cloudformation/**` and
   `frontend/**` sit in `on.pull_request.paths` purely so the required `Python Quality & Tests`
   context always reports. A required check that never runs is reported as *missing*, not passing,
   which blocked infrastructure-only PRs indefinitely until #406. Do not remove a path from the
   trigger list without also removing the required-check requirement.
2. **Detection fails safe.** If the diff window cannot be resolved, everything runs.
3. **The workflow file counts as a change for both detectors,** so any edit to a gate exercises that
   gate. Without this, a PR touching only the workflow reported green in about five seconds having
   installed, linted and built nothing.

#### Python steps

- **`pre-commit run --from-ref ... --to-ref ...`:** the repo's own hooks, scoped to the diff. Always
  runs, regardless of `python_changed`, so Python files outside `src/` and `tests/` and all markdown
  stay covered. `SKIP=no-commit-to-branch` because that hook is a local guard against direct commits
  to `main` and trivially fails once the commit exists.
- **Black:** `--check --fast src/ tests/`. Fails the job on drift and prints the diff. It does **not**
  auto-commit a fixup -- `main` is protected, so the workflow cannot push.
- **Flake8:** blocking. **MyPy:** `continue-on-error: true`. **Bandit:** MEDIUM+ severity, blocking.
- **pytest:** `--cov=src --cov-fail-under=70 --maxfail=10`. PRs and manual runs only.

#### CloudFormation linting

Runs `scripts/cfn-lint-wrapper.sh` over each changed template, which implements the documented
exit-code contract (4 -> pass, 2/6/8 -> fail). Deleted templates are excluded via `--diff-filter=d`
and `archive/` is skipped. Before #406 nothing in GitHub Actions triggered on
`deploy/cloudformation/**`, so templates reached CI only through the 02:00 nightly job -- after
merge. See `deploy/cloudformation/CLAUDE.md` for the exit-code table and an unresolved divergence
with the buildspec call sites.

#### Frontend gate

Runs `npm ci --legacy-peer-deps`, then `npm run lint`, `npm run test:run`, `npm run build`, all with
`working-directory: frontend`.

- **Node 22 is required**, not a preference. The lockfile has required it since the
  `jsdom 29.1.1 -> 30.0.1` bump in #368; on Node 20 every vitest worker fails to start with
  `TypeError: webidl.util.markAsUncloneable is not a function`. The requirement is declared in
  `frontend/package.json` `engines`. See `frontend/CLAUDE.md`.
- **`--legacy-peer-deps` is mandatory**, not a shortcut: `eslint-plugin-react@7.37.5` caps its
  peer-`eslint` range at `^9.7` while the project is on `eslint@10.x`.
- **Build is included on purpose.** A component can lint and test clean and still break the bundle;
  an unresolved import only surfaces at build time.
- The gate is tuned to fail on regressions without being blocked by the 93 pre-existing eslint
  warnings: it exits 0 on the current baseline and 1 when a real error is introduced.

**Artifacts** (uploaded from `Python Quality & Tests` on `always()`):
- `bandit-report.json`
- `htmlcov/` and `coverage.xml`

Trivy results are uploaded as SARIF to the GitHub Security tab rather than as an artifact.

---

## Setup Instructions

### 1. No Setup Required (Workflows Auto-Run)

The workflows are **already configured** and will run automatically on:
- Pull requests to `main` or `develop`, subject to the path filters above
- Pushes to `main` (lint only -- `run_full_tests` is false, so pytest does not run)

### 2. Optional: VS Code Extensions (Recommended)

Install recommended VS Code extensions for local auto-fixing:

```bash
code --install-extension davidanson.vscode-markdownlint
code --install-extension ms-python.python
code --install-extension ms-python.black-formatter
```

Or install all recommended extensions:
1. Open VS Code
2. View → Extensions
3. Filter: `@recommended`
4. Click "Install Workspace Recommended Extensions"

**With these extensions:**
- Markdown auto-fixes on save
- Python auto-formats with Black on save
- Real-time linting errors shown in editor

### 3. Optional: Local Manual Linting

You can run the same checks locally before pushing:

**Everything CI runs, in one command** (this is the closest local equivalent to the
`pre-commit` step in the workflow, and the recommended pre-push routine):

```bash
pre-commit run --files $(git diff --name-only HEAD~1 HEAD)   # fast: changed files only
SKIP=no-commit-to-branch pre-commit run --all-files          # safest: whole repo
```

**Markdown:** covered by the `markdownlint` pre-commit hook above. There is no separate markdown
workflow. `./scripts/lint-markdown.sh --fix` remains available for a standalone sweep.

**Python:**
```bash
# Install tools
pip install black flake8 mypy bandit pytest pytest-cov

# Format code
black src/ tests/

# Lint code
flake8 src/ tests/ --max-line-length=120

# Type check
mypy src/

# Security scan
bandit -r src/

# Run tests
pytest tests/ -v --cov=src
```

**CloudFormation:** use the wrapper, not bare `cfn-lint` -- the wrapper is what CI runs and it
implements the exit-code contract (4 -> pass, 2/6/8 -> fail).

```bash
pip install cfn-lint
./scripts/cfn-lint-wrapper.sh deploy/cloudformation/template.yaml
```

**Frontend:** requires Node 22 (see `frontend/CLAUDE.md`).

```bash
cd frontend
npm ci --legacy-peer-deps
npm run lint
npm run test:run
npm run build
```

---

## Workflow Permissions

`code-quality.yml` declares these at workflow scope:

```yaml
permissions:
  contents: read           # Quality checks are read-only
  pull-requests: read
  security-events: write   # To upload Trivy SARIF
```

`contents` is deliberately `read`. The workflow does **not** auto-commit fixes: `main` is protected,
so a formatting drift fails the job with the diff printed rather than being pushed back. Jobs that
genuinely need write access (release-please, for example) declare it at job scope in their own
workflow, not here.

**Note:** These permissions are scoped to the `GITHUB_TOKEN` (automatic, no secrets needed).

---

## Branch Protection Rules

`main` is protected by the `main-protection` repository ruleset. It requires four status check
contexts (verified 2026-08-29 via `gh api repos/<owner>/<repo>/rulesets/<id>`):

| Context | Workflow | Path-filtered? |
|---|---|---|
| `Analyze (python)` | `codeql.yml` | No -- runs on every PR to `main` |
| `Analyze (javascript-typescript)` | `codeql.yml` | No |
| `Analyze (actions)` | `codeql.yml` | No |
| `Python Quality & Tests` | `code-quality.yml` | **Yes** |

`Python Quality & Tests` is the only required context that is path-filtered, which is why it is the
only one that can deadlock a PR, and why `deploy/cloudformation/**` and `frontend/**` must stay in
the workflow's trigger paths. `Analyze (ruby)` runs but is not required.

`strict_required_status_checks_policy` is false, so branches do not have to be up to date with
`main` before merging.

**Trees still outside the trigger paths.** #406 closed the deadlock for `deploy/cloudformation/**`
and #415 closed it for `frontend/**`. The following are still absent from
`code-quality.yml`'s `on.pull_request.paths`, so a PR touching only one of them should not trigger
`Python Quality & Tests`:

- `deploy/buildspecs/**` (has its own `buildspec-validation.yml`, which is not a required context)
- `deploy/scripts/**`, `scripts/**`
- `docs/**` and other markdown-only changes
- `.github/workflows/*` other than `code-quality.yml`

This has **not** been verified against a live PR and is inferred from the path filters and the
ruleset. Anyone who hits it should either add the path to the trigger list and gate the expensive
steps in the job body -- the pattern #406 and #415 established -- or remove the required-check
requirement. Do not narrow the trigger and leave the requirement standing.

Candidates not currently required (promoting any of them is a ruleset change made in GitHub
settings, outside this repository):

| Job | Why it is a reasonable candidate | Caveat |
|---|---|---|
| `Frontend Quality & Tests` | Added in #415; gates 1,880 tests, lint and build | Skips its own steps when no frontend file changed, so it reports fast-green on unrelated PRs |
| `Security Scanning` | Trivy findings currently advisory | `upload-sarif` is `continue-on-error` because GitHub Advanced Security may not be enabled |

---

## Compliance & Audit Trail

### NIST 800-53 Alignment

GitHub Actions provides audit trail for compliance:

**SA-11: Developer Security Testing**
- ✅ Automated security scanning (Bandit, Trivy)
- ✅ Logs retained in GitHub Actions history
- ✅ SARIF results uploaded to GitHub Security tab

**CM-3: Configuration Change Control**
- ✅ All code changes go through PR review
- ✅ Automated checks enforce quality standards
- ✅ Audit trail shows who approved/merged

**AU-12: Audit Generation**
- ✅ All workflow runs logged with timestamps
- ✅ Can export logs to CloudWatch for 7-year retention (future)

### SOX Compliance

- ✅ Change management controls (required status checks)
- ✅ Segregation of duties (reviewers cannot approve own PRs)
- ✅ Audit trail (GitHub Actions logs)

---

## Troubleshooting

### PR Blocked With Every Check Green

**Cause:** `Python Quality & Tests` is a required check and did not trigger, so GitHub reports the
context as *missing* rather than passing. This is what #406 fixed for `deploy/cloudformation/**` and
#415 fixed for `frontend/**`.

**Fix:** The changed tree must be in `on.pull_request.paths` in `code-quality.yml`. Add it there,
and gate the expensive steps in the job body rather than narrowing the trigger.

### `pre-commit` Step Fails But Nothing Looks Wrong

**Cause:** Most of the repo's hooks are auto-fixers (`isort`, `black`, `trailing-whitespace`,
`end-of-file-fixer`, `markdownlint --fix`). CI cannot push the fixes back, so it exits non-zero.

**Fix:** Run `pre-commit` locally before pushing and commit the result. Do not use `--no-verify`.

### Frontend Tests Pass Locally, Fail in CI

**Cause:** Node version, or a stale `node_modules`. Node 22 is required; npm only *warns* on an
`engines` mismatch, and a `node_modules` predating the #368 dependency bump keeps an older `undici`
so a local run succeeds against a tree that no longer matches the lockfile.

**Fix:** Check `node --version`, then `rm -rf node_modules && npm ci --legacy-peer-deps`. See
`frontend/CLAUDE.md` for the failure signature.

### Frontend Gate Passes in Five Seconds

**Cause:** Not a bug -- `frontend_changed` resolved false, so every step was skipped. This is
expected on a Python-only or template-only PR.

**Fix:** None needed. Note that editing `code-quality.yml` itself counts as a frontend change
precisely so the gate cannot report green without exercising itself.

### Security Scan False Positives

**Cause:** Trivy flags low-severity issues in dependencies.

**Fix:** Review results in GitHub Security tab → Dismiss false positives with justification.

---

## Cost Analysis

### GitHub Actions Free Tier

- **Public Repositories:** 2,000 minutes/month (free)
- **Private Repositories (Free plan):** 2,000 minutes/month
- **Private Repositories (Pro plan):** 3,000 minutes/month

### Job Timeouts (the enforced ceiling, not an observed average)

`code-quality.yml` caps each job with `timeout-minutes`. These are the only minute figures in this
document verifiable from the repository itself; per-run durations vary and are not tracked here. The
one per-run duration quoted in "Change detection" above is attributed to a specific run ID so it can
be re-checked, and is an observation of that run rather than an average.

| Job | `timeout-minutes` |
|---|---|
| `Check Trigger Type` | 2 |
| `Python Quality & Tests` | 25 |
| `Security Scanning` | 10 |
| `Frontend Quality & Tests` | 15 |

**Minute-reduction measures actually in place:**
- `concurrency` with `cancel-in-progress: true` cancels superseded runs on the same ref
- `cache: 'pip'` on `setup-python`; `cache: 'npm'` keyed on `frontend/package-lock.json`
- Change detection skips the Python toolchain on template-only and frontend-only PRs, and skips
  `npm ci` on Python-only PRs
- `pytest --lf --ff --maxfail=10` fails fast and reruns last-failed first

Note that `pip install --no-cache-dir` is used deliberately for torch and `requirements.txt` -- the
pip cache otherwise retains native wheels built against a stale numpy ABI (issue #221 / PR #172).
That trade is a correctness requirement, not an oversight.

---

## Next Steps

1. Done: workflows in `.github/workflows/`; `Python Quality & Tests` required on `main`
2. Done: PR-level cfn-lint gate (#406) and frontend gate (#415)
3. Optional: install the VS Code extensions above for local auto-fixing
4. Open: decide whether `Frontend Quality & Tests` should be promoted to a required check
5. Open: review the Security tab for Trivy findings; `upload-sarif` is `continue-on-error`, so a
   silent upload failure is possible if GitHub Advanced Security is not enabled

---

## Additional Resources

- **GitHub Actions Documentation:** https://docs.github.com/en/actions
- **markdownlint Rules:** https://github.com/DavidAnson/markdownlint/blob/main/doc/Rules.md
- **cfn-lint Documentation:** https://github.com/aws-cloudformation/cfn-lint
- **Trivy Documentation:** https://aquasecurity.github.io/trivy/

---

**Questions?** See `CLAUDE.md` for project context or open an issue on GitHub.
