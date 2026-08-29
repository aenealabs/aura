# Frontend Development Guide

> Universal security rules and AI attribution policy are in the root `CLAUDE.md`.

---

## Design System

- **Primary Brand Color:** `#3B82F6` (blue)
- **Semantic Colors:**
  - Critical/Error: `#DC2626` (red)
  - High Priority: `#EA580C` (orange)
  - Medium Priority: `#F59E0B` (amber)
  - Success: `#10B981` (green)
  - Info: `#3B82F6` (blue)
- **Typography:** Inter font family, H1 32px, H2 24px, Body 14px, Code 13px (JetBrains Mono)
- **Spacing:** 8px base unit (4px, 8px, 12px, 16px, 24px, 32px, 48px)
- **Accessibility:** WCAG 2.1 AA compliance required (4.5:1 contrast minimum)
- **CSS Framework:** Tailwind CSS (utility-first, LLM-friendly)

---

## Technology Stack

- **Framework:** React 19, Vite (no Next.js)
- **Language:** JavaScript with JSX (no TypeScript). When converting modules to TS, do it incrementally per-file and update this entry.
- **Styling:** Tailwind CSS
- **State Management:** Follow existing patterns in the codebase
- **Build:** Node 22 (see Node version requirement below); bundle via Vite + Rollup

---

## Node version requirement

**Node 22 minimum -- `^22.22.2 || ^24.15.0 || >=26.0.0`**, declared in
`package.json` `engines` and enforced in CI by the `Frontend Quality & Tests`
job.

This guide previously said Node 20, and that became wrong when the
`jsdom 29.1.1 -> 30.0.1` bump (#368) pulled the dependency tree forward:

| Package | Requires |
|---|---|
| `jsdom` | `^22.22.2 \|\| ^24.15.0 \|\| >=26.0.0` |
| `undici` | `>=22.19.0` |
| `@testing-library/jest-dom` | `>=22` |

On Node 20 every vitest worker fails to start with:

```
TypeError: webidl.util.markAsUncloneable is not a function
```

**Two things made this invisible.** npm only *warns* on an `engines` mismatch
rather than failing, so a local install on an unsupported Node appears to
succeed. And a developer with a `node_modules` predating #368 keeps the older
`undici` and sees tests pass against a tree that no longer matches the
lockfile -- `npm ci` on a clean checkout behaves differently from `npm install`
on a stale one.

If tests pass locally but fail in CI, check `node --version` against the table
above and re-run `npm ci --legacy-peer-deps` before assuming the change is at
fault. Note that Node 25 does **not** satisfy the range: `jsdom` skips odd
majors. The declared range is the contract regardless of whether an unlisted
major happens to run the suite -- CI pins `node-version: '22'`, so that is the
only version the tests are actually verified against.

**Not yet reconciled:** the container build path still names Node 20 --
`deploy/docker/frontend/Dockerfile.frontend:23`,
`deploy/buildspecs/buildspec-docker-build.yml:156`,
`deploy/buildspecs/buildspec-marketing.yml:9` -- and the private-ECR base-image
list in the root `CLAUDE.md` offers only `aura-base-images/node:20-slim`.
Whether the production bundle breaks on Node 20 is unverified: the observed
failure was in vitest, which the image does not run. Tracked in
`docs/PROJECT_STATUS.md`. That Dockerfile also runs bare `npm ci --silent`
without `--legacy-peer-deps`, which CI requires (see below).

---

## CI gate: `Frontend Quality & Tests`

Added in #415. Before it, nothing in CI touched `frontend/` -- `code-quality.yml`
was path-filtered to Python and CloudFormation and `buildspec-validation.yml`
covers only buildspecs, so the whole suite ran on developer machines and a
frontend regression merged green.

The gate is a job in `.github/workflows/code-quality.yml`, not a separate
workflow. It runs, in order, with `working-directory: frontend`:

```bash
npm ci --legacy-peer-deps
npm run lint
npm run test:run
npm run build
```

**Build is part of the gate on purpose.** A component can lint and test clean
and still break the bundle -- an unresolved import only surfaces at build time.

**When it runs.** A self-contained detection step resolves `frontend_changed`
from the PR diff, so a Python-only or template-only PR does not pay for an
`npm ci`. Editing `code-quality.yml` itself also counts as a frontend change:
without that, a PR touching only the gate reports green in about five seconds
having installed, linted and built nothing, and the breakage lands on the next
contributor's frontend PR looking like their fault.

**The `frontend/**` glob is in the workflow's trigger paths as well as in the
job.** That is
load-bearing and must not be removed: `Python Quality & Tests` is a *required*
status check, and a required check that never runs is reported as missing rather
than passing, so a frontend-only PR would be blocked indefinitely with every
check it did run green. A standalone frontend workflow would reproduce that
deadlock exactly.

**Lint baseline.** `npm run lint` currently reports **93 problems, 0 errors**.
The gate exits 0 on that baseline and 1 when a real error is introduced, so it
catches regressions without being blocked by the existing warnings. Do not
"fix" the gate by adding `--max-warnings` -- reduce the warnings instead.

`Frontend Quality & Tests` is **not** itself a required status check as of this
writing; promoting it is a main-protection ruleset change made in GitHub
settings, outside this repository.

Local equivalent before pushing:

```bash
cd frontend
npm ci --legacy-peer-deps   # not `npm install` -- see Node version requirement
npm run lint && npm run test:run && npm run build
```

---

## Design References

- **Design Principles:** `agent-config/design-workflows/design-principles.md`
- **Design Review Workflow:** `agent-config/design-workflows/design-review-workflow.md`
- **App UI Blueprint:** `agent-config/design-workflows/app-ui-blueprint.md`

---

## Component Conventions

- Components use PascalCase filenames (e.g., `ProfilePage.jsx`)
- Auth components live in `src/components/auth/`
- Form field names like "Password" are UI labels, not secrets (excluded from secrets scanning)

---

## Known peer-dep workaround: `--legacy-peer-deps` required

`npm install` and `npm ci` in this directory must be run with `--legacy-peer-deps`. This is a known, tracked situation — not an oversight.

**Why:** `eslint-plugin-react@7.37.5` (latest, last released 2025-04-03) caps its peer-eslint range at `^9.7`. Our project uses `eslint@10.x` (GA 2026-02-06). Upstream has not shipped eslint@10 peer support; without `--legacy-peer-deps`, npm refuses to resolve.

**Tracked as:** At-Risk in `docs/security/DEPENDENCY_RISK_REGISTER.md`. Replacement plan: swap to `@eslint-react/eslint-plugin` (active fork, native eslint@10 support) — tracked as issue #142, **deferred per its own trigger conditions** (no date-based deadline). The swap fires when *any one* of: (a) `eslint-plugin-react` goes >18 months without an eslint@10 peer-support release, (b) a CVE lands without an upstream fix, or (c) `eslint@9.x` reaches EOL. Re-evaluation runs on the weekly #138 dependency-risk audit cycle.

**Caveat of the workaround:** `--legacy-peer-deps` is not scoped — it silences *all* peer-dep conflicts, not just this one. If a future PR introduces an unrelated peer-dep regression, the flag will paper over it. When picking up this directory, do a one-time `npm install` *without* the flag to verify no new conflicts have been masked, then proceed with `--legacy-peer-deps` for routine work.

---

## `brace-expansion` override pinned to `^5.0.5`

`package.json` `overrides.brace-expansion` is intentionally pinned at `^5.0.5`. eslint@10's `@eslint/config-array` ships a compiled minimatch@10 that calls `require('brace-expansion').expand` (named export). brace-expansion@1.x and 2.x only expose the function as `module.exports` (default), so an earlier override of `^1.1.13` or `^2.0.2` caused `npm run lint` to crash with `TypeError: brace_expansion_1.expand is not a function` before any source code was inspected. 5.x added the proper named `.expand` export with dual ESM/CJS bundles and TypeScript types, satisfying both minimatch@10 *and* the older minimatch@3.1.5 transitively pulled in by `eslint-plugin-react@7.37.5` (it uses the default `require('brace-expansion')()` call which 5.x preserves). Re-evaluate this override when the `eslint-plugin-react` swap in issue #142 lands.
