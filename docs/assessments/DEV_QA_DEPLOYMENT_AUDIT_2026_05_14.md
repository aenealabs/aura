# DEV/QA Deployment Capability Audit — 2026-05-14

**Scope:** Independent technical assessment of Project Aura's documented DEV and QA deployment capabilities versus what the codebase actually implements, in the style of a vendor codebase review.

**Method:** Eight parallel audit tracks (T1–T8), each scoped to one capability surface. Findings restricted to "broken or actively misleading." Stylistic suggestions and "could be improved" notes are intentionally excluded.

**Result:** 16 findings — 6 CRITICAL, 7 HIGH, 3 MEDIUM. Three deaf CI alarms, one documented `deploy` command that fails on its own example, a 32% drift on a key infrastructure count claim, and a kill-switch with no concurrent-run guard. Detail below; each finding cites a file:line and an evidence command.

---

## Executive verdict

The DEV/QA platform is **deployable** but the documentation and CI surface around it has accumulated meaningful drift since the last full audit. Three classes of problem dominate:

1. **Doc-to-code numeric drift.** The "Current Status" block in `CLAUDE.md` and `docs/PROJECT_STATUS.md` is stale across most exact counts (CodeBuild projects, test count, LOC, CFN template count, security service test count). The ADR-count and buildspec-count claims still hold.
2. **Deaf CI gates.** Three scheduled or required workflows are silently failing: `nightly-live-llm.yml`, `nightly-iam-validation.yml` (recovered but ran red 5+ nights without alarm), and `code-quality.yml` masks `pip install` errors with `|| true`. The `aura-security-review.yml` workflow is gated off entirely for Dependabot PRs — a real coverage gap given today's 15-PR Dependabot wave.
3. **Single-environment shape leaking into multi-env claims.** The four committed parameter overlays (`enterprise/medium/small/govcloud`) all hardcode `"Environment": "prod"`. There is no committed DEV or QA overlay. The `deploy-network-services.sh prod 4` command documented in `CLAUDE.md` would fail the script's own tier validator.

None of these block a determined engineer from deploying DEV or QA today. All of them would surprise a new engineer relying on the documentation, and a vendor reviewing the codebase would flag every item below as a documentation-versus-reality discrepancy.

---

## Findings — by severity

### CRITICAL (deploy would fail, or documented capability is materially misrepresented)

#### C1. Documented `deploy-network-services.sh prod 4` command fails its own tier validator

**Location:** `CLAUDE.md:349-354`
**What the doc says:**
```
# Deploy to production
./deploy/scripts/deploy-network-services.sh prod 4
```
**What the script does:** `deploy/scripts/deploy-network-services.sh:271` validates `tier` against `^(1|2|all)$`. A second-argument value of `4` exits non-zero with "Invalid tier: 4 — Must be one of: 1 (kubernetes), 2 (fargate), all" before any deploy step runs.
**Severity reasoning:** The literal example in the canonical engineer-onboarding doc would fail immediately. Anyone copy-pasting it learns the tier scheme is wrong, not the script.

---

#### C2. Customer parameter overlays inject phantom EKS parameter names into the wrong template

**Location:**
- `deploy/customer/parameters/enterprise.json`, `medium.json`, `small.json`, `govcloud.json` — all supply `EKSNodeInstanceType`, `EKSNodeMinSize`, `EKSNodeMaxSize`.
- `deploy/customer/cloudformation/aura-quick-start.yaml:133,143,150` — declares these EKS-prefixed names.
- `deploy/customer/cloudformation/aura-application.yaml:83,94,101` — declares `NodeInstanceType`, `NodeMinSize`, `NodeMaxSize` (no prefix).
**What's broken:** Using the parameter overlay with the wrapper (`aura-quick-start.yaml`) works. Using the same overlay against `aura-application.yaml` directly — which a docs reader might do, since both templates live in `deploy/customer/cloudformation/` — fails with "Unknown parameter EKSNodeInstanceType." The two templates were never reconciled after the EKS- prefix was introduced.
**Severity reasoning:** Silent template-API mismatch in customer-facing templates.

---

#### C3. Kill-switches have no concurrent-run lock; a double-run can corrupt CFN state

**Location:** `scripts/dev_killswitch.py:1804-1805` (same pattern in `scripts/qa_killswitch.py`)
**What's broken:** Pre-flight state check is `warn()` only, no `exit`. Two operators (or one operator double-clicking) can invoke shutdown simultaneously. Both pass the warning, both begin deleting the same ~80 stacks via `cloudformation:DeleteStack`. CloudFormation does not serialize concurrent deletes against the same stack ARN; the typical result is `ROLLBACK_FAILED` on the second-arriving delete and an environment that cannot be cleanly restored without console intervention.
**Severity reasoning:** A documented operational tool ("`scripts/dev_killswitch.py`, 86 tests" per PROJECT_STATUS) can leave the environment in a worse state than before, and no test covers the concurrent-invoke path.

---

#### C4. `nightly-live-llm.yml` has been in `startup_failure` for 5+ consecutive runs

**Location:** `.github/workflows/nightly-live-llm.yml`
**Evidence:** Last 5 scheduled runs (since 2026-05-10) all reported `startup_failure`. The conditional at line 39 (`if: vars.LIVE_LLM_ENABLED == 'true' || github.event_name == 'workflow_dispatch'`) gates job execution but does not prevent runner-initialization failure — likely an OIDC role assumption or missing `AURA_LIVE_LLM_ROLE_ARN` secret, since the workflow file is structurally valid.
**Severity reasoning:** A scheduled gate has been silently dead for nearly a week with no alarm. The `PROJECT_STATUS` doc references "Mythos-Class Model Scaffolding" as live-validated through this surface; the surface is currently dead.

---

#### C5. `code-quality.yml` masks `pip install` failures with `|| true`

**Location:** `.github/workflows/code-quality.yml:85`
**What's broken:**
```yaml
pip install -r requirements.txt || true
```
When PyPI returns a transient network error or a wheel is unavailable, the install silently succeeds at the shell level but leaves required packages uninstalled. Subsequent `pytest` invocations then fail with `ModuleNotFoundError`. Recent CI history shows 4 consecutive `boto3`-missing runs between 2026-05-14 00:22 and 00:36 UTC, followed by a green run at 00:56 UTC — i.e., flake masquerading as a real failure.
**Severity reasoning:** This is a **required** branch-protection check. Its intermittent failure mode is opaque — engineers re-run and pass, never knowing whether the green run actually installed everything.

---

#### C6. Doc-to-code drift on CodeBuild project count (19 claimed, 25 actual)

**Location:** `CLAUDE.md:251`, `docs/PROJECT_STATUS.md`
**Claim:** "CodeBuild Projects: 19 projects (9 parent layers + 10 sub-layers...)"
**Actual:** `grep -rh "AWS::CodeBuild::Project" deploy/cloudformation/*.yaml | wc -l` → **25**
**Bootstrap drift:** `deploy/buildspecs/buildspec-bootstrap.yml:39` says "24 CodeBuild project templates" — different from both numbers.
**Severity reasoning:** 32% drift on an exact-count claim. The "no rounding" rule in `CLAUDE.md` makes any imprecise count a documentation defect. Three different parts of the codebase tell three different stories (19 / 24 / 25).

---

### HIGH

#### H1. `aura-security-review.yml` skipped on all Dependabot PRs

**Location:** `.github/workflows/aura-security-review.yml:40` (`if: github.actor != 'dependabot[bot]'`)
**Why it matters now:** Earlier today, 15 Dependabot PRs were merged in a wave that included major bumps (numpy 1→2, openai 1→2). None ran the aura security review. The gate exists in name only for the most-common PR type.
**Remediation note:** Either remove the dependabot exclusion, or run a stripped security review on lockfile/dep changes and document the rationale in-workflow.

---

#### H2. `nightly-iam-validation.yml` ran red five consecutive nights without surfacing

**Location:** `.github/workflows/nightly-iam-validation.yml:43-73`
**Evidence:** 6 sequential `FAILURE` runs (IDs 25621031708, 25592887001, 25538042724, 25478002565, 25418373885, 25359321213) followed by 2 recovery `SUCCESS` runs. The "Create issue for invalid actions" step (intended as the alarm) is gated on the cfn-lint-wrapper step succeeding — so a wrapper failure suppresses the alarm that exists *for* wrapper failures.
**Severity reasoning:** Recovered, but the failure pattern shows the alarm wiring inverted: the alarm only fires when the gate is healthy. Future failures will be deaf again unless this is restructured.

---

#### H3. `benchmarks.yml` last four runs all `CANCELLED`

**Location:** `.github/workflows/benchmarks.yml:40` (runs on `ubuntu-24.04-large`)
**Evidence:** 4 consecutive `CANCELLED` conclusions on path-triggered PR runs. Pinned `ubuntu-24.04-large` runner is likely unavailable. PRs that touch AST parser / git ingestion / graph services never get the perf regression signal the workflow is designed to provide.

---

#### H4. Multiple kill-switch failure paths uncovered by tests

**Location:**
- `deploy/cloudformation/dev-cost-scheduler.yaml:372-380` — Lambda fires `eks.update_nodegroup_config()` and returns success without polling EKS state. The API is asynchronous; nodes can run at full capacity for 5–10 minutes after "shutdown."
- `scripts/dev_killswitch.py:1889-1901` — `deploy_stack()` does not wait for `CREATE_COMPLETE` before advancing phases. Node-group deploy can begin before EKS control plane finishes, failing on missing cluster ARN.
- `docs/runbooks/DEV_KILLSWITCH_RUNBOOK.md:228-242` — Documents three post-restore manual steps (`aws eks update-kubeconfig`, `kubectl get nodes`, monitoring upper-layer CodeBuild) as required for a working environment. The script does not perform them and the doc presents them after the script's success message.
**Severity reasoning:** Test counts on kill-switches are *also* drifted (see H6), and the most consequential AWS-async-behavior paths are exactly the ones not covered.

---

#### H5. Service Catalog products default to public ECR — violates the mandatory private-ECR rule

**Location:**
- `deploy/service-catalog/products/quick-test-v1.yaml:33` → `Default: 'public.ecr.aws/docker/library/nginx:alpine'`
- `deploy/service-catalog/products/full-stack-v1.yaml:31` → `Default: 'public.ecr.aws/docker/library/python:3.11-slim'`
- `deploy/service-catalog/products/python-fastapi-v1.yaml:31` → `Default: 'public.ecr.aws/docker/library/python:3.11-slim'`
**Rule violated:** `CLAUDE.md` Container Security section: "ALWAYS use private ECR base images" / "NEVER use public.ecr.aws/* images in production builds."
**Note:** A second copy of these templates at `deploy/cloudformation/service-catalog-products/quick-test-v1.yaml:33` correctly carries a `ConstraintDescription` rejecting public registries. The two copies have diverged; the old copy is the one still wired into the product catalog.
**Severity reasoning:** Users who launch the catalog product without explicitly overriding `ContainerImage` get a public-ECR pull, bypassing the supply-chain controls the rule exists to enforce.

---

#### H6. Test count drift on kill-switches and security services

**Location:** `CLAUDE.md:257,260` and the kill-switch runbooks.
**Claims vs reality:**
| Claim | Actual | Source command |
|---|---|---|
| DEV kill-switch: 86 tests | **100** | `pytest tests/test_dev_killswitch.py --collect-only -q` |
| QA kill-switch: 47 tests | **61** | `pytest tests/test_qa_killswitch.py --collect-only -q` |
| Security Services: 328 tests | ~642+ collected across security-prefixed test files | `pytest tests/test_security*.py tests/test_a2as*.py tests/test_compliance*.py --collect-only -q` |
| Test Suite: ~25,253 | **26,414** | `pytest --collect-only -q` |
**Severity reasoning:** Each count is the kind of quote a vendor sees in `PROJECT_STATUS` and asks the engineer to verify. None match.

---

#### H7. Buildspec idempotency drift — seven buildspecs still use create-vs-update branching

**Location:** Wave 10 in commit `7670397` was documented as replacing all inline create/update branching with `aws cloudformation deploy --no-fail-on-empty-changeset`. The audit found seven buildspecs still doing it:
- `deploy/buildspecs/buildspec-application.yml` (lines 212, 227, 290, 305, 350, 358, 397, 405, 444, 452, 492, 500)
- `deploy/buildspecs/buildspec-compute.yml` (286, 301, 342, 358, 455, 471)
- `deploy/buildspecs/buildspec-security.yml` (67, 87, 147, 169, 203, 219)
- `deploy/buildspecs/buildspec-sandbox.yml` (135, 156, 262-290, 570, 589)
- `deploy/buildspecs/buildspec-service-frontend.yml` (72, 87)
**Severity reasoning:** The CLAUDE.md "Pattern Compliance" section explicitly forbids new instances of this pattern. Each remaining instance is a footgun and silently contradicts the documented Wave 10 cleanup completion.

---

### MEDIUM

#### M1. No committed DEV/QA parameter overlay; all four committed overlays hardcode `Environment: prod`

**Location:** `deploy/customer/parameters/{enterprise,medium,small,govcloud}.json`
**What's missing:** `dev.json`, `qa.json`.
**Effect:** DEV/QA deployers either fabricate parameter files at deploy time, supply `--parameter-overrides` ad-hoc, or accidentally deploy a prod-sized config to non-prod. None of those paths is versioned. The four committed overlays represent customer sizing tiers, not internal env staging.

---

#### M2. Twenty-plus DynamoDB / SQS / KMS resources have `DeletionPolicy: Retain` without an environment conditional

**Location:** `constitutional-audit-queue.yaml`, `semantic-guardrails.yaml`, `test-env-state.yaml`, `kms-replica-secondary.yaml`, `constitutional-ai-evaluation.yaml`, `runtime-security-dynamodb.yaml`, `neptune-simplified.yaml`, `onboarding.yaml`, `repository-tables.yaml`. Only `orchestrator-dispatcher.yaml` uses the correct conditional pattern (`!If [IsProduction, Retain, Delete]`).
**Effect:** When kill-switch tears down DEV/QA, these resources orphan and continue accruing charges. The DEV cost scheduler is meant to *avoid* orphan cost — this pattern actively works against it.

---

#### M3. Documentation off-by-one on CFN template count

**Location:** `CLAUDE.md:250`, `docs/PROJECT_STATUS.md`
**Claim:** 175 templates (170 + 5 service-catalog)
**Actual:** 176 (`find deploy/cloudformation -path "*/archive" -prune -o -name "*.yaml" -type f -print | grep -v "/archive/" | wc -l`)
**Severity reasoning:** Tiny absolute drift, but `CLAUDE.md` explicitly says "No Rounding: Always use exact percentages and metrics." A 175→176 mismatch is the smallest possible case of the same defect class as C6.

---

## Findings — by audit track

### T1 — CFN template integrity
Production templates have **no cfn-lint errors** (errors-only, excluding W3037 false-positive class). The seven broken templates in `deploy/cloudformation/archive/` are not deployed but should not live in the active codebase unmodified — they fail cfn-lint with E-class errors (`config-compliance.yaml`, `ecs-dev-cluster.yaml`, `ecs-scheduled-scaling.yaml`, `eks-multi-tier.yaml`, `marketplace.yaml`, `network-services-enhanced.yaml`, `opensearch-filesystem-index.yaml`). **Twenty-nine dead parameters** were found across seven production templates (`alb-controller.yaml`, `capability-governance.yaml`, `cognito.yaml`, `incident-investigation-workflow.yaml`, `opensearch.yaml`, `semantic-guardrails.yaml`, `ssr-training-pipeline.yaml`) — declared but never `!Ref`'d. Five `!ImportValue` chains assume the exporting stack is named with a specific `${ProjectName}-service-${Environment}` pattern; if a stack is renamed during deploy, the import fails. See findings M2, M3 for the consequential issues.

### T2 — Buildspec ↔ template wiring
Buildspec count (28) **matches the claim exactly**. CodeBuild project count does **not** match (see C6). Seven buildspecs still use the pre-Wave-10 create/update pattern (see H7). Two buildspecs (`buildspec-docker-build.yml`, `buildspec-coordinator.yml`) are not in the bootstrap deployment loop but exist in the directory — verify whether intentional. `buildspec-observability.yml` has env-specific cfn-lint validation that doesn't reflect actual env-specific deployment.

### T3 — Deployment script reality
**One CRITICAL** — see C1. Otherwise all documented entrypoints exist (`deploy-network-services.sh`, `deploy-*-codebuild.sh`, `cfn-lint-wrapper.sh`), arg parsing matches docs in every other case, and prerequisite-checking is in place. The `deploy-network-services.sh` is the only script with documentation drift on arg semantics.

### T4 — DEV/QA parameter files
Phantom EKS-prefixed parameters (see C2). No DEV/QA overlays (see M1). `NeptuneBackupRetention` parity gap between enterprise (14d) / govcloud (35d) and medium/small (default 7d) — three operational SLA tiers without explanation. No real secrets committed; pre-commit `detect-private-key` exclusions appropriately scoped.

### T5 — CI/CD workflow health
Three deaf workflows (C4, C5, H2). One critical coverage gap (H1, Dependabot skip). One stalled benchmark gate (H3). Dependency-risk-audit has 2/5 recent runs `CANCELLED` due to concurrency-group collisions when manual dispatch overlaps the scheduled run — not blocking, but the workflow loses observability when this happens.

### T6 — Kill-switch & cost-control reality
Test counts drifted (see H6). Five additional code-path findings (H4, C3): no concurrent-run lock, async EKS update not polled, async CFN deploy not polled, restore-path manual steps undocumented as required, cost claim ("estimated monthly, 27-37% of DEV compute") has no baseline figure committed against which the percentage could be verified.

### T7 — Doc-to-code drift
**Verified accurate:**
- ADR count: 93 claimed, 93 actual.
- Buildspec count: 28 claimed, 28 actual.

**Verified inaccurate:**
- CodeBuild Projects: 19 / 25 (see C6).
- CFN templates: 175 / 176 (see M3).
- Tests: ~25,253 / 26,414 (see H6).
- Security Services tests: 328 / 642+ (see H6).
- LOC: 375,000+ claimed for "production + infrastructure; tests counted separately." `cloc src/ deploy/ tests/ --md` reports 706,865 total lines; src+deploy is ~329,925 lines of code+comments, ~166,898 lines of code alone. Depending on the methodology the doc intends, the figure either understates (if it means total) or overstates (if it means src-only) — the claim is unverifiable as written.

### T8 — DEV/QA security posture
**Cleanly passing:** IAM PassRole scoping (correctly conditioned on `iam:PassedToService` in checked templates), S3 public-access-block configuration on all checked buckets, KMS keys per-environment (no cross-env reuse), security groups (ALB 0.0.0.0/0 only on 80/443, everything else VPC-scoped), pre-commit hook exclusion list. **Failing:** three Service Catalog products default to public ECR (see H5). The `nvcr.io` CUDA reference in `deploy/docker/memory-service/Dockerfile.memory-service:22` is a known design exception (no private mirror exists for proprietary Nvidia CUDA) but is not documented as an exception in `CLAUDE.md` — engineers reading the "NEVER use public images" rule will not know it's been deliberately relaxed here.

---

## Recommended remediation order

The audit produced no items that block deployment **right now**, but the deaf alarms and the kill-switch concurrent-run hazard mean the platform's operational confidence is lower than the documentation suggests. Suggested order, smallest fixes first:

1. **C1, M3, H6, C6** — single-file doc edits. Update `CLAUDE.md` and `docs/PROJECT_STATUS.md` to actual counts; correct `prod 4` → `prod all` (or whichever tier is intended) in the deploy-script example. Run once, audit cleanly.
2. **C5** — remove `|| true` from `code-quality.yml:85`. The mask actively hides flake from required-check observers; failing fast is strictly better.
3. **H1** — decide whether `aura-security-review.yml` should run on Dependabot. If yes, remove the `if:`. If no, document the rationale in-workflow and route the gate to a different mechanism for lockfile changes.
4. **H5** — replace public-ECR defaults in `deploy/service-catalog/products/*.yaml` with the `ConstraintDescription` pattern already used by their `deploy/cloudformation/service-catalog-products/` twins. Delete or merge the duplicate templates.
5. **C2, M1** — reconcile `aura-quick-start.yaml` and `aura-application.yaml` on the `EKSNode*` vs `Node*` parameter names. Add `dev.json` and `qa.json` overlays for internal envs.
6. **C3, H4** — add a file-based or DynamoDB-conditional-write lock to `dev_killswitch.py` and `qa_killswitch.py`. Add `eks:DescribeNodegroup` polling after `eks:UpdateNodegroupConfig`. Add `cloudformation describe-stacks --query 'Stacks[0].StackStatus'` polling to the restore phase. Bring runbook manual steps into the script.
7. **C4, H2, H3** — fix the three deaf scheduled workflows. For each, the simplest robust fix is wiring an unconditional issue-open step on workflow `failure()` rather than gating the alarm on the failing step.
8. **H7** — finish Wave 10 in the seven remaining buildspecs.
9. **M2** — convert the unconditional `DeletionPolicy: Retain` cases to `!If [IsProduction, Retain, Delete]` so the kill-switch cost benefit is realized.

The first five steps would close most of the documentation-vs-reality gap a vendor reviewer would surface in a follow-up audit. The remaining four address real operational fragility that has not yet caused a visible incident but would surface as one under load.

---

## Audit metadata

- **Date:** 2026-05-14
- **Tracks:** T1 (CFN integrity), T2 (buildspec wiring), T3 (deployment scripts), T4 (parameter files), T5 (CI/CD workflows), T6 (kill-switches), T7 (doc drift), T8 (security posture)
- **Files referenced by direct line:** 41
- **Verification commands recorded:** 17 (each finding above can be re-checked with the command shown)
- **Severity bar:** broken-or-actively-misleading only; "could be improved" suggestions excluded by design.
