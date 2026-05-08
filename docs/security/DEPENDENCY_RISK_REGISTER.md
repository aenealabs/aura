# Dependency Risk Register

**Last Updated:** 2026-05-08
**Owner:** Platform Engineering
**Audit Cadence:** Weekly (automated via `.github/workflows/dependency-risk-audit.yml`)
**Runbook:** `docs/runbooks/DEPENDENCY_RISK_AUDIT_RUNBOOK.md`

---

## Purpose

Track every third-party dependency Aura runs against, score each by long-term durability risk, and surface a mitigation plan for anything that could break the platform if the upstream goes dark.

This register exists because: a dependency that becomes abandonware, gets compromised in a supply-chain incident, or is deprecated by its maintainer is operationally indistinguishable from "stops working" -- our defense against that is documented mitigations, not faith.

## Risk Tiering

| Tier | Definition | Action |
| --- | --- | --- |
| **Healthy** | Corporate or foundation backing, multiple maintainers, active release cadence (within last 6 months), no known supply-chain incidents | Track via the recurring audit; no other action |
| **Watch** | Single maintainer but active, or niche package without obvious successor, or recent maintenance slowdown | Recurring audit; revisit annually; ensure abstraction-readiness if not already abstracted |
| **At-Risk** | Visible long-term risk: deprecated by maintainer, slow patch turnaround on CVEs, ecosystem migration in progress, or a known supply-chain history | File a mitigation issue; pin precisely; have a swap plan documented |
| **Replace-Now** | Already deprecated, compromised, or with no viable upgrade path | Open a remediation PR within the current sprint; do not let the dep age further |

## At-Risk and Replace-Now Items (act on these)

The headline list. These are the deps that will hurt the platform if we don't actively manage them.

| Package | Surface | Tier | Reason | Mitigation |
| --- | --- | --- | --- | --- |
| `gremlinpython` | Python (API runtime) | **At-Risk** | Apache TinkerPop project, but the Python binding has historically thin maintenance compared to the Java reference. Tied to Neptune. Also note: as of `gremlinpython==3.8.0`, this package transitively requires `nest_asyncio`, so removing our direct pin on `nest-asyncio` does not eliminate it from the install set -- the gremlinpython binding still pulls it in. Our code no longer calls `nest_asyncio.apply()`, so the transitive presence is harmless. | Track upstream cadence via the recurring audit. If trigger conditions fire (Python compatibility lag, unpatched CVE > 30 days, EOL announcement), execute the swap to Neptune's HTTP API per `docs/runbooks/GREMLINPYTHON_FALLBACK_RUNBOOK.md`. The `_ThreadDispatchedGremlinClient` wrapper introduced when we replaced nest-asyncio is the structural seam for the swap. |
| `eslint-plugin-react` | Frontend (devDep) | **At-Risk** | Latest release `7.37.5` shipped 2025-04-03 (~13 months ago). Peer-eslint range capped at `^9.7`, despite `eslint@10.0.0` going GA on 2026-02-06 (~3 months ago) and `10.3.0` shipping 2026-05-01. No 7.37.6 / 7.38.x / 8.x exists; no visible upstream issue tracking eslint@10 peer support. This forces every `npm install` / `npm ci` in `frontend/` to use `--legacy-peer-deps`, which globally silences peer-dep conflicts and weakens our ability to catch *new* peer-dep regressions in unrelated packages. The package itself is dev-only (linting; never bundled to production), so the production blast radius is zero -- but the operational friction is real. | Two-track mitigation. **Track 1 (immediate)**: live with `--legacy-peer-deps` documented in `frontend/CLAUDE.md` as a known workaround. **Track 2 (planned)**: swap to `@eslint-react/eslint-plugin` (a.k.a. `eslint-plugin-react-x`) -- active fork by the eslint-react team, latest `5.7.5`, peer `eslint: ^10.3.0`. Tracked as a follow-up issue with explicit "execute when upstream silence persists" trigger rather than a date-based deadline. The recurring audit will flag if `eslint-plugin-react` ships a release with eslint@10 peer support (which would close this naturally) or if the silence stretches further (which strengthens the swap case). |
| `pptxgenjs` | Frontend (runtime) | **Watch** | Last release `4.0.1` was 2025-06-26 (~10-month gap as of audit). Single-maintainer, niche. Used for one feature: PowerPoint export of architecture diagrams in `frontend/src/components/documentation/DiagramViewer.jsx`. The import is dynamic (`await import('pptxgenjs')`), so the single callsite is already the natural swap seam. | Non-critical feature; PowerPoint export can degrade to PDF export (already wired in the same component) if pptxgenjs becomes unavailable. If a CVE lands without a fix or the project is formally archived, replace with server-side PowerPoint generation (python-pptx) or remove the export option. |

## Healthy Tier (most of the surface)

These are the deps with corporate or foundation backing where we accept the risk and rely on the upstream's maintenance commitment. Listed for completeness so the recurring audit knows the expected baseline.

### Python -- Healthy

| Package | Backing |
| --- | --- |
| `boto3` / `botocore` | AWS |
| `fastapi`, `uvicorn`, `starlette` | Tiangolo (Sebastián Ramírez, full-time funded; Microsoft contributions) |
| `pydantic` / `pydantic-settings` | Pydantic (Samuel Colvin's company) |
| `httpx` | Encode collective (`encode/httpx`) |
| `aiohttp` | aio-libs collective |
| `torch` | Meta / Linux Foundation (PyTorch Foundation) |
| `numpy`, `scipy`, `scikit-learn` | NumFOCUS sponsored |
| `opensearch-py` | OpenSearch Project (AWS-led) |
| `cryptography` | Python Cryptographic Authority |
| `defusedxml` | PSF |
| `PyJWT` | jpadilla / community (large contributor base) |
| `PyYAML` | yaml.org / community |
| `requests` | psf / community |
| `networkx` | NetworkX team (NSF-funded) |
| `tree-sitter`, `tree-sitter-python`, `tree-sitter-javascript` | tree-sitter community (multi-org) |
| `openai` | OpenAI |
| `google-cloud-aiplatform` | Google |
| `protobuf`, `grpcio`, `grpcio-tools` | Google |
| `prometheus-client` | Prometheus team (CNCF) |
| `opentelemetry-*` | CNCF |
| `structlog` | hynek schlawack (active, well-known maintainer) |
| `email-validator` | community |
| `python-dotenv` | community |
| `python-multipart` | community |
| `defusedxml` | PSF |
| `z3-solver` | Microsoft Research (Z3) -- the Python binding tracks the C++ release |
| `cfn-lint` | AWS Cloud Engineering |
| `moto` | Spulec / community (large maintainer base now) |
| `pytest` and the pytest-* plugins | pytest-dev |
| `ruff`, `mypy`, `bandit`, `black` | Astral / Python community (well-funded) |
| `GitPython` | community |
| `PyGithub` | community |

### Frontend -- Healthy

| Package | Backing |
| --- | --- |
| `react`, `react-dom` | Meta |
| `react-router-dom` | Remix / Shopify |
| `vite`, `@vitejs/plugin-react` | Evan You / VoidZero |
| `vitest`, `@vitest/coverage-v8` | Anthony Fu / community |
| `tailwindcss`, `@tailwindcss/vite` | Tailwind Labs |
| `eslint`, `@eslint/js`, `eslint-plugin-react`, `eslint-plugin-react-hooks` | OpenJS Foundation |
| `@testing-library/*` | Testing Library (community, widely adopted) |
| `@types/react`, `@types/react-dom` | DefinitelyTyped (Microsoft) |
| `esbuild` | Evan Wallace |
| `jsdom` | tmpvar / community |
| `lucide-react` | Lucide (well-maintained icon set) |
| `react-grid-layout` | Samuel Reed (STRML); v2 TypeScript rewrite shipped Dec 2025, eight releases through Mar 2026 (v1.5.3 -> v2.0.0 -> v2.1.x -> v2.2.x). Native React 19 support (peer `react >= 16.3.0`). Aura consumers route through a thin `frontend/src/lib/grid-layout.js` re-export wrapper so a future swap (if ever needed) is one file to change; see `docs/runbooks/REACT_GRID_LAYOUT_FALLBACK_RUNBOOK.md`. |
| `mermaid` | Knut Sveidqvist + the Mermaid Chart team (commercial backing since 2022). Six releases between Oct 2025 and Apr 2026 including major v11. Aura consumers go through `frontend/src/utils/mermaidLoader.js` which is already a singleton lazy-loader -- that's the swap seam, no new wrapper needed. |
| `jspdf` | Community-maintained at `parallax/jsPDF`. Six releases between Sep 2025 and Mar 2026, including a v4 major in Jan 2026. Two consumers in src/ (`DocumentationDashboard.jsx`, `services/trustCenterExport.js`) use it for PDF export of compliance reports. |
| `jspdf-autotable` | Companion table plugin to jspdf; same author (simonbengtsson). v5.0.7 in Jan 2026 after a longer gap. Used alongside jspdf in `services/trustCenterExport.js` only. Borderline cadence but currently active; tracked alongside jspdf for re-evaluation if either slows. |
| `peter-evans/create-pull-request` | GitHub Action; six releases between Nov 2025 and Apr 2026 including v8 major (Dec 2025). Single-maintainer (Peter Evans) but well-funded by sponsorship and adoption. SHA-pinned at v7.0.8 in `.github/workflows/aura-ci-autofix.yml`; one usage. |
| `@heroicons/react` | Tailwind Labs |
| `recharts` | Recharts community |
| `amazon-cognito-identity-js` | AWS |
| `eslint-plugin-unused-imports` | community |
| `globals` | sindresorhus (active, well-known) |

### Infra -- Healthy

| Item | Notes |
| --- | --- |
| `public.ecr.aws/docker/library/python:3.11-slim` | Mirrored to private ECR per CLAUDE.md mandate; Docker official image |
| `public.ecr.aws/docker/library/alpine:3.19` | Same; Alpine Linux (community) |
| `public.ecr.aws/docker/library/node:20-alpine` | Same; Node.js |
| `public.ecr.aws/docker/library/nginx:1.28-alpine` | Same; nginx (F5) |
| `nvcr.io/nvidia/cuda:cudnn-runtime-ubuntu22.04` | NVIDIA-published; mirrored to private ECR for GPU workloads |
| `actions/checkout`, `actions/setup-python`, `actions/upload-artifact`, `actions/github-script` | GitHub-owned official actions |
| `aws-actions/configure-aws-credentials` | AWS-owned |
| `github/codeql-action` | GitHub-owned |
| `googleapis/release-please-action` | Google-owned |
| `aquasecurity/trivy-action` | Aqua Security (commercial vendor, active) |

## Recurring Audit

The weekly audit (`.github/workflows/dependency-risk-audit.yml`) runs:

1. `pip-audit` against all `requirements*.txt` files for Python CVEs.
2. `npm audit --json` against `frontend/` for npm CVEs.
3. A maintainer-staleness check (last release date) against the **Watch** and **At-Risk** tiers from this register, using `pip show` / `npm view` metadata so no external API calls are needed.

Output is posted as a comment on the tracking issue (`#138`). New high or critical CVEs surfaced as separate issues for triage.

## Replacement Decisions Made

| Decision | Date | Rationale |
| --- | --- | --- |
| Replaced `python-jose` with `PyJWT[crypto]` | Pre-existing | `python-jose` had unpatched CVEs and a maintainer who explicitly stated they were no longer maintaining; PyJWT has corporate-backed crypto via the `cryptography` package. |
| Replaced `tj-actions/changed-files` with native `git diff` step | 2026-05-08 | CVE-2025-30066 supply-chain compromise; single-maintainer action with documented incident. Replaced with a custom bash step in `.github/workflows/aura-security-review.yml` that uses `git diff --name-only` and grep filtering. Same outputs (`any_changed`, `all_changed_files`) so downstream steps unchanged. Closes #139. |
| Replaced `google-generativeai` with `google-genai` | 2026-05-08 | Old SDK deprecated by Google in 2025 SDK consolidation; new features land only in the unified `google-genai` package. Migrated `GeminiLLMService` from the `genai.configure(...) -> GenerativeModel(...).generate_content(...)` shape to `genai.Client(api_key=...).models.generate_content(model=..., contents=..., config=...)`. New focused test (`test_gemini_genai_backend_uses_new_client_models_shape`) validates the call boundary even when no real Gemini credentials are present. Closes #140. |
| Dropped `requests-aws4auth` | 2026-05-08 | Single-maintainer, slow release cadence. The package was pinned in `requirements.txt` and `requirements-api.txt` but had **no production code consumers** -- `grep -rn "AWS4Auth\|requests_aws4auth"` returned only an archived CloudFormation template, an inline reference in a deploy script comment, and the deprecated PHASE2 implementation guide. OpenSearch SigV4 signing in production code uses `boto3`/`botocore` directly via `opensearch-py`'s AWS auth helper. Dead-weight pin removed; the deploy script's comment was updated to reference `botocore.SigV4Auth` as the suggested production path. |
| Replaced `nest-asyncio` with in-tree thread-dispatch wrapper | 2026-05-08 | Single-maintainer with slowing release cadence. The actual problem was gremlin-python's sync API calling `loop.run_until_complete()` from inside FastAPI's running event loop; nest-asyncio worked around this by patching asyncio. The replacement is a ~90-line wrapper (`_ThreadDispatchedGremlinClient` + `_ThreadDispatchedSubmitResult`) in `src/services/neptune_graph_service.py` that detects the running loop and dispatches the blocking gremlin call to a small ThreadPoolExecutor whose worker threads have no running loop -- so `run_until_complete()` succeeds without re-entry. Zero call-site changes (the wrapper preserves the `client.submit(q).all().result()` chain). New focused test in `tests/test_gremlin_thread_dispatch.py` validates both sync-context pass-through and async-context dispatch. |
| Re-tiered `react-grid-layout` from Watch to Healthy + added swap seam | 2026-05-08 | The original Watch entry's claim ("maintenance has slowed in 2024-2026; React 19 compatibility is community-patched") was inaccurate. Verified evidence: same author as v1 (Samuel Reed / STRML), v2 TypeScript rewrite shipped Dec 2025, eight releases through Mar 2026, native React 19 support (peer `react >= 16.3.0`). Tier corrected to Healthy. As a defensive measure, added `frontend/src/lib/grid-layout.js` as a single import seam so consumers (`DashboardGrid.jsx`, `DashboardEditor.jsx`) no longer couple directly to the package -- a future swap, if ever needed, is one-file. Surface preserved exactly: same default + named exports as upstream. New tests: `frontend/src/lib/grid-layout.test.js` (5 surface-shape tests), `frontend/src/components/ui/DashboardGrid.test.jsx` (4 behavior tests on the previously-uncovered grid wrapper component), `frontend/src/components/dashboard/DashboardEditor.test.jsx` (8 behavior tests on the editor). Closes the test-coverage gap that previously had zero tests touching the grid layer. Contingency plan documented in `docs/runbooks/REACT_GRID_LAYOUT_FALLBACK_RUNBOOK.md`. |
| Re-tiered `mermaid` from Watch to Healthy | 2026-05-08 | Original Watch reasoning ("single-maintainer historically (Knut Sveidqvist), bus-factor concerns") was outdated. Mermaid Chart became the commercial sponsor in 2022 and now staffs maintainers full-time. Verified evidence: six releases between Oct 2025 and Apr 2026, including major v11 series and ongoing v11.x patches (latest `11.14.0` on 2026-04-01). Tier corrected to Healthy. No code change needed -- the existing `frontend/src/utils/mermaidLoader.js` lazy-singleton loader IS the swap seam (4 consumers go through it), and `from 'mermaid'` only appears in the loader and one direct dynamic import in `DiagramViewer.jsx`. The original mitigation note ("isolated to diagram-rendering paths; falls back to plain text on render failure") still holds. |
| Re-tiered `jspdf` from Watch to Healthy | 2026-05-08 | Original Watch reasoning ("community-maintained; release cadence is irregular") was outdated. Verified evidence: six releases between Sep 2025 and Mar 2026, including v4 major (2026-01-03) and ongoing v4.x patches (latest `4.2.1` on 2026-03-17). The `parallax/jsPDF` repo is community-maintained and active. Tier corrected to Healthy. No code change. Two callsites use it directly today (`DocumentationDashboard.jsx`, `services/trustCenterExport.js`); if a future swap becomes necessary, those two files would change together. |
| Re-tiered `jspdf-autotable` from Watch to Healthy | 2026-05-08 | Tracked alongside jspdf as the table-rendering plugin. v5.0.7 shipped 2026-01-04 after a longer gap; the project is currently active. One consumer (`services/trustCenterExport.js`) uses both jspdf and jspdf-autotable together. Tier corrected to Healthy with the caveat that the cadence is borderline; the recurring audit will flag if it slows further. |
| Re-tiered `peter-evans/create-pull-request` from Watch to Healthy | 2026-05-08 | Original Watch reasoning ("single-maintainer, bus-factor of one") was true but overstated the risk -- the project has six releases between Nov 2025 and Apr 2026 including v8 major (Dec 2025), with sponsorship and broad enterprise adoption keeping it well-funded. Tier corrected to Healthy. Currently SHA-pinned at v7.0.8 in `.github/workflows/aura-ci-autofix.yml` (one usage). The recurring audit watches release tempo; bumping to v8.x is a separate workflow-modernization concern, not a risk-driven action. |
| Refined `pptxgenjs` Watch entry | 2026-05-08 | Kept on Watch (not re-tiered). The original assessment was correct: last release `4.0.1` was 2025-06-26, ~10-month gap as of audit. Refined the entry to note that the single Aura consumer is `frontend/src/components/documentation/DiagramViewer.jsx` and the import is dynamic (`await import('pptxgenjs')`), so the callsite itself is the natural swap seam. PowerPoint export degrades to PDF export (already wired in the same component) if pptxgenjs becomes unavailable -- non-critical feature. If trigger conditions fire (CVE without fix, project archived), replace with server-side python-pptx generation or remove the export option. |
| Bumped `uuid` `11.1.0 -> 11.1.1` (CVE-2026-41907) and `brace-expansion` `1.1.12 -> 1.1.14` (GHSA-f886-m6hf-6m8v) | 2026-05-08 | First real triage run after the audit pipeline landed. Dependabot surfaced both on push to main (alert #40 was the user-visible signal). Triage per the runbook decision tree: both have fixes, both are transitive (`uuid` via `mermaid`, `brace-expansion` via `eslint-plugin-react -> minimatch`), and both are unreachable in our actual usage paths -- `uuid` is only reachable via mermaid which uses v4 (random) not the affected v3/v5/v6 with `buf` paths; `brace-expansion` is dev-only via ESLint, never bundled to production, and ESLint only sees source-controlled glob inputs (no user-controlled input that would trigger the ReDoS). Both fixes applied via `overrides` block in `frontend/package.json` (npm-native pattern for transitive bumps). Verified: `npm audit` returns 0 vulns, 111/111 dashboard tests pass, `vite build` clean. No advisory published -- fix-available transitive CVEs that bump cleanly within hours of detection don't require customer-facing GHSAs; they show up in `CHANGELOG.md` under Security via the `security:` commit prefix. |

(Add to this table when a Replace-Now decision is executed.)

## Updating This Register

- A new dep entering the Watch / At-Risk / Replace-Now tier must be added to the headline table here, with an explicit mitigation written.
- A dep moving down a tier (e.g., Watch -> Healthy) gets a single-line entry in `Replacement Decisions Made` with the date and rationale.
- The recurring audit posts diffs against this register; reviewers should update the register when triaging an audit issue rather than just silencing the alert.

## References

- Audit script: `scripts/security/dep_risk_audit.py`
- Workflow: `.github/workflows/dependency-risk-audit.yml`
- Runbook: `docs/runbooks/DEPENDENCY_RISK_AUDIT_RUNBOOK.md`
- Tracking issue: `#138`
