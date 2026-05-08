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
| `peter-evans/create-pull-request` | CI | **Watch** | Single-maintainer (high-profile; widely adopted). No incidents, but bus-factor of one. | SHA-pinned; recurring audit watches release tempo. |
| `mermaid` | Frontend (runtime) | **Watch** | Single-maintainer historically (Knut Sveidqvist). Active project, but bus-factor concerns. | Already isolated to diagram-rendering paths in the UI; falls back to plain text on render failure. |
| `pptxgenjs` | Frontend (runtime) | **Watch** | Single-maintainer, niche package. Used for PowerPoint export of dashboards. | Feature is non-critical; export can degrade to PDF (already wired) if pptxgenjs becomes unavailable. |
| `jspdf` + `jspdf-autotable` | Frontend (runtime) | **Watch** | Community-maintained; release cadence is irregular. | Used for PDF export; non-critical path. PDF generation could move to a backend service later (CSS print, headless Chromium) if needed. |
| `react-grid-layout` | Frontend (runtime) | **Watch** | Maintenance has slowed in 2024-2026; React 19 compatibility is community-patched. | Critical to the customizable dashboard widgets (ADR-064). Track upstream React 19 support; have a fallback to a static-grid mode if the library drops behind. |

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
