# ADR-090: GraphRAG Ingestion Edge Completeness

**Status:** Proposed
**Date:** 2026-05-08
**Author:** Project Aura Team
**Related ADRs:** ADR-049 (Mythos Capability Tier), ADR-063 (Constitutional AI),
ADR-065 (Semantic Guardrails), ADR-066 (Agent Capability Governance),
ADR-067 (Context Provenance & Integrity), ADR-068 (Universal Explainability),
ADR-070 (Policy-as-Code GitOps), ADR-071 (Cross-Agent Capability Graph),
ADR-072 (ML-Based Anomaly Detection), ADR-073 (ABAC),
ADR-077 (Cloud Runtime Security), ADR-083 (Runtime Agent Security Platform),
ADR-084 (Native Vulnerability Scanning Engine)

---

## Context

Aura's correctness story rests on graph-grounded retrieval: agents consult
Neptune for structural code context (CALLS, IMPORTS, INHERITS, etc.) before
acting, and downstream verification layers (ADR-068 explainability, ADR-063
critique-revision, sandbox validation) treat retrieved context as the
authoritative basis for action-completeness claims.

Audit of `src/services/git_ingestion_service.py` and
`src/agents/ast_parser_agent.py` revealed that the deployed pipeline emits
only `CONTAINS` and `DEPENDS_ON` edges. The read-side contract in
`src/services/context_retrieval_service.py:497-507` maps query types to
`CALLS`, `CALLED_BY`, `IMPORTS`, `INHERITS`, `EXTENDS`, `IMPLEMENTS`,
`REQUIRES` — labels the write side never produced. Read-side queries
returned structurally impoverished results without surfacing errors,
producing overconfident agent reasoning chains. The JS/TS parser is
regex-based; tree-sitter is pinned but unused in ingestion.

This is the upstream cause of a class of agent-correctness failures:
agents acting on incomplete context while downstream telemetry shows
green, structurally analogous to the SRE-incident pattern where a JWT
rotation succeeds in `auth-service` while every downstream consumer
caching the prior key remains broken.

---

## Problem Statement

1. **Edge contract divergence:** Read-side references seven edge labels;
   write-side emits two.
2. **Polyglot parser inadequacy:** Python uses real AST; JS/TS uses regex.
3. **No cross-file resolution:** Even Python emits no cross-file `CALLS`.
4. **Stale-edge accumulation on incremental re-ingest** (Phase 0,
   delivered).
5. **Removed files leave orphan vertices and embeddings** (Phase 0,
   delivered).
6. **No config-layer dependencies:** Services bound by SSM parameters,
   environment variables, KMS aliases, and feature flags have no graph
   representation.
7. **Brittle entity IDs:** `{file_path}::{name}` cannot survive renames,
   overloads, or nested classes.
8. **Self-reported LLM confidence** is decorative, not diagnostic.
9. **LLM in the ingestion hot path** would create a backpressure timebomb.

---

## Decision

Close the contract gap in six phases, governed by a single canonical edge
schema documented in this ADR and enforced by a type-system-backed
contract test that prevents recurrence.

### Phase 0 — Stale-Edge Hotfix (DELIVERED)

Merged ahead of this ADR:

- `NeptuneGraphService.delete_outgoing_edges_for_entity()` and
  `delete_outgoing_edges_for_file()` — surgical primitives that drop
  outgoing edges while preserving the vertex and incoming cross-file
  edges. Mock and Gremlin paths.
- `delete_entities_by_file` Gremlin-injection fix.
- `GitIngestionService._delete_removed_files()` — cascading vertex +
  embedding cleanup via the existing `delete_entities_by_file` and
  `delete_by_file_path` methods.
- `ingest_changes(removed_files=...)` parameter.
- `_populate_graph(upsert=True)` clears outgoing edges before re-write.
- 17 new tests; 336-test affected suites pass with no regressions.

### Phase 1 — Entity ID Migration (PRECONDITION)

**This must ship before any new edge writers.** The current
`{file_path}::{name}` scheme collides on overloads, nested classes, and
cross-repo file-path overlaps. Replace it with SCIP-inspired fully
qualified names. We do not target SCIP wire compatibility; we adopt its
properties (stability across non-rename edits, uniqueness under
overloading, location-independent identity, repo-scoped namespace).

**Aura FQN format:**

```
{scheme}:{repo_id}:{module_path}:{symbol_path}#{kind}[@{disambiguator}]
```

| Component | Source | Example |
|---|---|---|
| `scheme` | language | `python`, `typescript`, `javascript` |
| `repo_id` | already in metadata; **repo-scoped (no cross-repo unification)** | `owner/repo` |
| `module_path` | derived from file path, stripping `src/` / `lib/` / `app/` and the file extension | `myapp.services.auth` |
| `symbol_path` | dotted chain of all enclosing scopes | `User.verify_token` |
| `kind` | maps to existing `type` property | `class`, `function`, `method`, `variable`, `import` |
| `disambiguator` | **integer suffix in declaration order** (`@0`, `@1`, ...) for overloads, decorator-produced duplicates, dynamic class generation | `@1` |

**FQN computation lives in `src/services/graph/fqn.py`** as a single
source of truth, imported by `ASTParserAgent`, `NeptuneGraphService`,
and the migration script.

**Migration mechanics.** Gremlin edges reference internal vertex IDs,
not the `entity_id` property — so the migration is a property-add, not
a vertex-replacement. The one-shot idempotent script
(`scripts/migrate_entity_ids_adr090.py`) walks every `CodeEntity`
vertex, computes the FQN from existing properties (`file_path`, `name`,
`parent`, `type`, `metadata.repository`), and writes a new `fqn`
property. Vertices already carrying `fqn` are skipped. Read paths then
prefer `fqn` lookup over `entity_id` lookup with a fallback during the
dual-write window.

**Rollout: backfill all existing graphs before Phase 2 ships.** Phase 2
starts on a clean v2 schema. Phase 1 timeline absorbs the migration
window; subsequent phases are not gated on the lazy-backfill priority
queue described later in this ADR.

### Phase 2 — Python Within-File Edges (Deterministic)

Extend `ASTParserAgent._parse_python_file` to emit:

- `CALLS` — every `ast.Call`, with `call_site_line` edge property.
- `INHERITS` — class base classes (replaces collapsing into
  `DEPENDS_ON`).
- `IMPORTS` — module-to-module edges (replaces standalone import
  vertices).

`INHERITS` carries a `kind` property with values `extends` (concrete
base) or `implements` (Protocol/ABC). `EXTENDS` and `IMPLEMENTS` are
NOT separate edge labels — they were a contract bug, removed from the
read-side mapping in this ADR. `REQUIRES` is removed entirely.

### Phase 3 — JS/TS via tree-sitter (Deterministic)

Replace `_parse_js_file` regex implementation with tree-sitter using the
already-pinned `tree-sitter-javascript` grammar. Same edge set as Phase 2.

### Phase 4 — Cross-File Symbol Resolution (Tiered)

Three-tier resolver in priority order:

**Tier 1 — Deterministic graph traversal.** Build per-repo import graph
from Phase 2 `IMPORTS` edges. Resolve qualified names. Emit cross-file
`CALLS` edges where unambiguous.

**Tier 2 — Static type inference (Pyright).** Pyright resolves an
estimated 80–95% of "ambiguous" cases deterministically by inferring
the type of the call receiver and looking up the method in the type's
MRO. Pyre and Jedi were evaluated and rejected: Pyre's inference is
less aggressive on dynamic dispatch (the cases we care about most),
and Jedi's lower accuracy would push enough work back to Tier 3 to
defeat the cost rationale for Tier 2.

Integration: **subprocess JSON output for the Phase 4 alpha**, migrated
to **Pyright Language Server (LSP) for production** once resolution
accuracy is validated. The LSP daemon amortizes cold-start cost across
many resolutions; the alpha-via-subprocess step de-risks the LSP
integration.

**Invocation scope: per-package within a repo.** Pyright is loaded
with a package-scoped `pyrightconfig.json`; memory is bounded by the
largest package, not the whole monorepo. This matches how enterprise
monorepos are actually structured.

**Timeout: 500ms hard cap per call site, fall through to LLM on
expiry.** Most warm Pyright queries return in <50ms; the 500ms cap
catches outliers without dragging the worker. Pyright crashes,
"`Any`"-only inference, and missing-Pyright-binary all also fall
through to Tier 3. Pyright is a soft dependency: the pipeline must run
without it, just more expensively.

**Tier 3 — LLM disambiguation, decoupled from hot path.**

For residual ambiguity:

1. Ingestion writes a `needs_resolution` marker to **SQS Standard** and
   **does not block**. Step Functions was evaluated and rejected:
   per-state-transition cost (~$25/M) at the expected 3–8M resolutions
   per cold scan would add $75K–$200K of orchestration overhead, and
   each resolution is a single Bedrock call with no branching value
   from orchestration.
2. A separate `SymbolResolverWorker` pool, deployed on **ECS Fargate
   with long-polling SQS receive**, drains the queue. Workers are
   persistent, autoscaled on `ApproximateNumberOfMessagesVisible`, and
   reuse Bedrock connections across messages.
3. The worker invokes Bedrock with **constrained output** — the model
   selects an index from a closed candidate set produced by Tiers 1+2;
   it cannot emit targets not in the AST candidate list (defense vs.
   schema escape).
4. Comments and docstrings are stripped from LLM context. Structural
   resolution does not need prose, and stripping eliminates an
   estimated ~95% of the prompt-injection surface.
5. Edges emitted with **discrete `verification_status`**:
   `{verified, plausible, unverified}` — replacing the confidence float.
   Verification is structural: does the resolved symbol exist? Is it
   importable from the call site?
6. **Confidence tier encoded in edge label**, not just property:
   `CALLS` (deterministic + Tier 2) versus `CALLS_INFERRED` (Tier 3
   LLM). Filter pushdown on labels is index-backed in Neptune;
   `outE('CALLS')` for high-trust traversals stays cheap.
7. **Circuit breaker is per-worker, per-Bedrock-region.** Each worker
   tracks 429/5xx rate independently for its assigned region. No shared
   state, no coordination point that itself can fail.
8. **Degraded-mode default: emit `unverified` edges and continue.**
   When the breaker opens, ingestion never stalls — `CALLS_INFERRED`
   edges are written with `resolution_method=deferred` and
   `verification_status=unverified`, and a self-healing re-resolution
   job retries them when the breaker closes. ADR-068 reasoning chains
   see the lower-confidence signal natively.
9. **Worker writes resolved edges directly to Neptune.** Lowest
   latency, simplest data flow, fewest moving parts. Audit-trail
   requirements are met by structured worker logs (prompt_hash,
   model_id, verification_status, cost_usd) routed to the immutable
   audit store, not by an event-bus hop.

Failed messages route to a DLQ; a DLQ-drain job emits `unverified`
edges so resolution failures degrade rather than disappear.

Cache: content-addressed by
`hash(call_site_AST + transitive_closure_hash(imported_modules_referenced))`.
When a transitive dependency changes, all dependent resolutions
invalidate. Mirrors the Bazel/Buck content-addressing pattern.

### Phase 5 — Config-Layer Dependencies (Deterministic-First)

**Build the deterministic version first.** A new `ConfigDependencyAgent`
scans for SSM references (`ssm:GetParameter`, `boto3.client('ssm').get_parameter`),
environment variable references (`os.environ.get`, `os.getenv`), KMS
aliases, and feature flag patterns. Edges are emitted using regex + AST
context disambiguation only. Precision and recall are measured against
fixture repos.

**LLM is added only if recall < 90%** against the fixture set. The bar
must be met empirically, not assumed.

Vertices use separate labels: `ConfigParameter`, `KMSAlias`,
`FeatureFlag`. Edges: `READS_CONFIG`, `DEPENDS_ON_ENV`, `USES_KMS_KEY`,
`FEATURE_GATED_BY`.

**ABAC gate (ADR-073).** Phase 5 edges form a secret-topology graph
(MITRE T1580 + T1083 surface). The deployed ADR-073 ABAC vocabulary is
reused — no new attribute scheme is introduced.

**Enforcement: Pattern A (edge-property filter, hardened).** Every
Phase 5 edge carries a `sensitivity` property. Traversal queries
include a clearance filter that excludes edges above the caller's
clearance. Pattern A is the practical choice given Neptune's lack of
native label-scoped IAM permissions; Pattern B (separate traversal
source) and Pattern C (separate Neptune cluster) were considered and
rejected on operational-cost grounds.

**Sensitivity tiering** (cybersecurity review, grounded in NIST and
MITRE):

| Edge | Sensitivity | Rationale |
|---|---|---|
| `USES_KMS_KEY` | RESTRICTED | NIST SP 800-57 Pt.1 §5.3; MITRE T1552.004. Direct cryptographic-material map. |
| `READS_CONFIG` | RESTRICTED | NIST 800-53 SC-28/SC-12; OWASP ASVS V6.4. SSM SecureStrings can hold any secret; we cannot disambiguate at ingest, so the reference graph is treated as secret-adjacent. |
| `DEPENDS_ON_ENV` | CONFIDENTIAL | Names only, but T1580 + T1083 cloud-recon surface. |
| `FEATURE_GATED_BY` | CONFIDENTIAL | Reveals kill-switches and unreleased paths; SOX-adjacent material non-public information. |

Per-instance dynamic classification (deriving sensitivity from the
referenced parameter's content) was considered and rejected: it turns
an authorization decision into a data-quality problem with no upper
bound on blast radius (NIST AC-3, AC-4 expect deterministic mediation).
Path forward to per-instance classification requires a ground-truth
parameter classifier with a measured false-negative rate.

**Filter location: `context_retrieval_service` traversal wrapper.**
A single chokepoint where all callers (agents, API, internal services)
hit the same filter logic. Direct `NeptuneGraphService.find_related_code`
calls outside this wrapper are blocked by a contract test.

**Caller experience on near-miss traversal: silent filter + audit log.**
A low-clearance caller whose traversal would have crossed a Phase 5
edge sees the edge filtered without a metadata flag advertising its
existence. The attempt is logged to the ADR-072 anomaly detector for
pattern analysis. Hard-failing the query was rejected because it
breaks legitimate adjacent queries.

**Defense-in-depth controls (all six layered regardless of tiering):**

1. **Fail-closed default.** Edge missing `sensitivity` property →
   treated as TOP_LEVEL. Write-time guard rejects Phase 5 edges
   without a `sensitivity` value.
2. **Per-traversal audit.** Caller identity, clearance, edge type,
   and decision (allow/deny) routed to CloudTrail and immutable S3.
   NIST AU-2, AU-9.
3. **ADR-072 volume anomaly detection.** A single principal pulling
   above a threshold of `USES_KMS_KEY` edges in a window flags as
   T1580 reconnaissance behavior.
4. **SSM-toggleable kill-switch.** A boolean SSM parameter forces all
   Phase 5 edges to RESTRICTED globally — incident-response toggle,
   not a code deploy.
5. **ADR-067 quarterly re-scoring hook.** Provenance review re-classifies
   high-traffic Phase 5 edges; misclassifications are corrected before
   they're queried in anger.
6. **Honeypot edges (ADR-072).** Synthetic `USES_KMS_KEY` edges seeded
   to non-existent KMS aliases. Any traversal is high-confidence
   reconnaissance signal.

A per-tenant kill-switch for Phase 5 ingestion (separate from the
global SSM filter override) follows the existing DEV/QA killswitch
pattern.

### Phase 6 — Runtime Edges (Out of Scope, Documented Here)

`RUNTIME_DEPENDS_ON`, `CACHES_KEY`, and `INVOKES_AT_RUNTIME` are produced
by the ADR-083 runtime-to-code correlation pipeline. This ADR defines
the edge schema so the runtime pipeline targets it without coordination
overhead.

---

## Canonical Edge Contract

### Edge labels (single source of truth)

Implemented as `src/services/graph/edge_labels.py` `EdgeLabel(str, Enum)`.
Both write paths and `context_retrieval_service._get_relationship_types`
import from this enum. An AST-lint rule
(`scripts/lint_edge_labels.py`) rejects string-literal edge labels
outside this module. CI fails on divergence.

| Label | Source → Target | Producer | Trust Tier |
|---|---|---|---|
| `CONTAINS` | parent → child | Phase 0 (existing) | deterministic |
| `INHERITS` | class → base | Phase 2 | deterministic |
| `IMPORTS` | module → module | Phase 2 | deterministic |
| `CALLS` | function → callee | Phase 2 / Phase 4 Tier 1+2 | deterministic |
| `CALLS_INFERRED` | function → callee | Phase 4 Tier 3 (LLM) | inferred |
| `READS_CONFIG` | entity → ConfigParameter | Phase 5 | deterministic (LLM only if recall demands) |
| `DEPENDS_ON_ENV` | service → env var | Phase 5 | deterministic |
| `USES_KMS_KEY` | entity → KMSAlias | Phase 5 | deterministic |
| `FEATURE_GATED_BY` | entity → FeatureFlag | Phase 5 | deterministic |
| `RUNTIME_DEPENDS_ON` | service → service | ADR-083 | runtime |
| `CACHES_KEY` | service → ConfigParameter | ADR-083 | runtime |

`CALLED_BY` is **not materialized** — Gremlin `inE('CALLS')` is
symmetric and cheap. The read-side abstraction provides the alias.

`DEPENDS_ON` is retained as a query-time alias resolving to
`INHERITS ∪ IMPORTS` for backward compatibility during migration.

### Mandatory edge properties

All new edges carry:

- `created_at` (ISO-8601 UTC)
- `source_commit_sha`
- `source_method` ∈ `{ast, tree_sitter, pyright, regex, llm, runtime}`
- `schema_version` (integer; `1` legacy, `2` post-this-ADR)

LLM-produced edges additionally carry:

- `verification_status` ∈ `{verified, plausible, unverified}`
- `model_id` (e.g., `claude-haiku-4-5-20251001`)
- `prompt_hash`
- `valid_until` (ISO-8601; supports soft-delete pattern)

`CALLS` edges additionally carry `call_site_line`.

### Per-edge-type budgets (not aggregate)

| Label | Default budget per repo | Notes |
|---|---|---|
| `CALLS` | 30M | Largest fanout; stdlib deny-list applied |
| `CONTAINS` | 5M | Structural; bounded by entity count |
| `INHERITS` | 500K | Sparse |
| `IMPORTS` | 2M | Module-to-module |
| `CALLS_INFERRED` | 1M | LLM-resolved subset |
| `READS_CONFIG` | 100K | Sparse |
| `USES_KMS_KEY` | 10K | Very sparse, security-sensitive |
| `FEATURE_GATED_BY` | 50K | Sparse |
| `DEPENDS_ON_ENV` | 100K | Sparse |

Per-job ingestion fails fast on budget overrun with an actionable error,
forcing an explicit operator decision rather than silent storage growth.

### Vertex labels

- `CodeEntity` — single label, `type` property distinguishes
  `class`/`function`/`method`/`variable`/`import` (existing).
- `ConfigParameter` — separate label.
- `KMSAlias` — separate label.
- `FeatureFlag` — separate label.

Separate labels for Phase 5 vertex types because property sets are
disjoint, lifecycles differ, and label-scoped Gremlin queries
(`hasLabel`) are index-backed in Neptune.

---

## Migration

### Lazy backfill with priority queue

Existing repos are retained at `schema_version=1` until backfilled. A
background worker drains repos ordered by
`(last_query_time DESC, size ASC)` — recently-queried small repos first.
Webhooks naturally upgrade hot repos because re-ingest produces v2
edges. SLO: 90 days to full migration. Tracked via a dedicated
dashboard.

### Dual-write window for label changes

The `DEPENDS_ON` → `INHERITS` split ships behind a feature flag with a
two-week dual-write period: both labels are emitted, readers query
both. After the dual-write window, `DEPENDS_ON` writes cease; the alias
remains for two more weeks; then the alias is removed.

### Migration validation

- Pre-migration Neptune snapshot (full backup).
- ADR-070 `PolicyValidator` dry-run against ABAC and capability-graph
  policies referencing edge labels (ADR-066, ADR-071).
- Golden-graph regression test (see Tests).
- Documented rollback Gremlin script.

---

## Security Controls

### Phase 4/5 LLM hardening

- Comments and docstrings stripped from LLM context (~95% of the
  injection surface eliminated).
- Constrained output: model selects from a closed candidate set
  produced by deterministic tiers; cannot introduce targets not present
  in the AST candidate list.
- `secret_pre_scan` (detect-secrets / truffleHog) on every snippet
  before LLM submission; positive scan emits an `unverified` edge and
  logs to security monitoring (ADR-083).
- Full prompt + response written to an immutable audit store
  (SOX / NIST 800-53 AU-2 / AU-3 / AU-12 compliance).

### Phase 5 secret-topology protection

- ABAC gate (ADR-073) on edge label, not just node.
- Per-tenant kill-switch for Phase 5 ingestion.
- ADR-067 provenance tagging on every edge.

### Phase 4/5 anomaly detection

- ADR-072 statistical detector consumes per-repo edge-distribution
  baselines; sudden Phase 5 edge spikes trigger anomaly alerts.
- LLM-assisted edges with `verification_status=unverified` and any
  `CALLS_INFERRED` traversed during agent action chains feed
  `confidence_signal` into ADR-068 reasoning.

### Edge-label allow-list at write time

`NeptuneGraphService.add_relationship()` validates against the
`EdgeLabel` enum. Unknown labels raise; cannot be silently written.

---

## Tests

### Architectural prevention of contract divergence

- Single `EdgeLabel(str, Enum)` in `src/services/graph/edge_labels.py`,
  imported by both write paths (`NeptuneGraphService.add_relationship`)
  and read paths (`context_retrieval_service._get_relationship_types`).
- `NeptuneGraphService.add_relationship()` validates the supplied
  label against the enum and raises `NeptuneError` for unknown labels.
- **AST-lint** (`scripts/lint_edge_labels.py`) rejects string-literal
  arguments to `add_relationship` and to any function whose parameter
  is named `relationship` or `edge_label`, with an allowlist for test
  fixtures and docstrings. **Targeted detection**, not broad
  upper-snake-case scanning, to keep the false-positive rate low.
- **Enforced in both pre-commit and CI** — local feedback catches
  violations before push; CI catches anything that bypasses pre-commit.
- Belt-and-suspenders introspection test: every
  `_get_relationship_types` return value has at least one writer
  (property test, not grep).

The enum and lint ship as a **standalone quick-win PR before Phase 1
begins**. This protects the Phase 1 entity-ID migration writers from
re-introducing string-literal edge labels and ensures every subsequent
phase is built on a clean contract foundation.

### Per-phase tests

- **Phase 1:** idempotency test on the migration script (run twice,
  hash graph, assert equal); chaos test (kill mid-run, resume, assert
  convergence).
- **Phase 2/3:** extend `test_ast_parser_agent.py` and
  `test_git_ingestion_service.py`.
- **Phase 4:** unit tests over fixture ASTs for resolver tiers;
  recorded Bedrock responses (VCR-style) for replay determinism;
  `@pytest.mark.live_llm` smoke suite nightly with cost assertion.
- **Phase 5:** precision / recall measurement over fixture repos; ABAC
  policy simulation tests.

### Confidence calibration test

N known-ambiguous + N known-unambiguous fixtures; assert
`verification_status` distributions separate (Mann-Whitney U).
Hardcoded values fail the test by design.

### Golden-graph regression test

Ingest a frozen fixture repo pre-migration → run migration → assert
read-path queries (the actual queries agents run) return semantically
equivalent results. One test per consumer of `_get_relationship_types`.

### Performance gates

`pytest-benchmark` suite with regression thresholds:

- Ingestion p95 latency on the medium fixture
- Edges/sec throughput
- Neptune write batch size

CI fails on >20% latency regression. A memory-ceiling test guards
cardinality expansion.

### Pathological fixture set

Beyond small/medium:

- Circular imports across 3+ modules.
- Dynamic dispatch via `getattr` / dict-of-callables.
- Re-export chains (`from .x import *` then `from .y import *`).
- Polyglot files (Python calling JS via subprocess; TS importing
  generated `.d.ts`).
- Generated code (protobuf, OpenAPI clients) — AST is real but
  semantically opaque.
- Namespace packages.
- Monkey-patched modules.
- Minified / obfuscated JS (validates tree-sitter graceful
  degradation).

Fixtures are version-pinned to detect grammar bumps that change graph
output.

---

## Observability

Required dashboard before Phase 2 ships:

- Edge-write rate per label per repo.
- Resolution-method distribution (`ast` / `pyright` / `llm`) over time.
- LLM cache hit rate.
- LLM cost per 1M LOC ingested.
- Orphan-vertex count.
- Per-edge-type budget consumption (% of cap).
- Migration progress: repos at `schema_version=1` versus `2`.

---

## Consequences

**Positive:**

- Read-side query types resolve to populated edges.
- Agent reasoning chains (ADR-068) defend completeness claims against a
  graph that supports them.
- ADR-071 capability-gap analysis becomes structurally possible.
- The Phase 0 stale-edge bug is fixed.
- Future contract divergence is prevented at compile / lint time.
- Phase 5 produces a security-asset graph governed by ABAC.

**Negative:**

- Edge cardinality expands an estimated 5–15× (see Open Questions).
- Ingestion latency increases per phase (Phase 2: +20%; Phase 3: +30%;
  Phase 4: +50% if LLM in path — but Phase 4 is decoupled, so 0%
  blocking impact; Phase 5: +30%).
- Cross-language parity is an ongoing maintenance burden (Java, Go,
  Rust each become separate ADRs with their own resolver adapters).
- Migration window: 90-day SLO during which graph reads may see mixed
  schema versions.

---

## Alternatives Considered

1. **Read-side AST reconstruction at query time.** Rejected: graph
   queries are the hot path; runtime parsing breaks latency budgets.
2. **External call-graph tools (`pyan`, language servers).** Rejected:
   per-language tooling fragmentation, no clean integration point with
   ADR-067 provenance and ADR-068 explainability.
3. **LLM-only edge extraction.** Rejected: nondeterministic, expensive,
   unfalsifiable. LLM use is bounded to disambiguation only, behind two
   deterministic tiers.
4. **Single confidence float across all edges.** Rejected on expert
   review: self-reported LLM probabilities are not calibrated.
   Replaced by `verification_status` enum + label-tier separation.
5. **Materialized `CALLED_BY` edges.** Rejected: doubles edge count and
   write amplification; Gremlin `inE` is symmetric and cheap.

---

## Open Questions

1. **Pyright dump-mode latency at 100M LOC** — does Tier 2 stay within
   budget? Benchmark before Phase 4 commits.
2. **Tree-sitter JS grammar coverage of TSX edge cases** — pin specific
   grammar version; list known gaps.
3. **Per-tenant LLM amortized ceiling** — what is the right number?
   Real cost data needed from a Phase 4 staging deploy.
4. **Validator dissent threshold** — what dissent rate triggers
   per-file quarantine? Start at 10%, tune from data.
5. **Java / Go / Rust language adapters** — each is a follow-up ADR;
   priority TBD by customer demand.

---

## Implementation Plan

| Phase | Status | LOC est. | Test files | Sequencing |
|---|---|---|---|---|
| 0 (hotfix) | **Delivered** | ~250 | extended existing | shipped |
| **Quick-win PR: EdgeLabel enum + AST-lint** | Proposed | 250–400 | new `test_edge_labels.py`, `test_lint_edge_labels.py` | **next, before Phase 1** |
| 1 (entity ID) | Proposed | 800–1200 | new `test_entity_id_migration.py` | precondition |
| 2 (Python intra) | Proposed | 400–700 | extend AST + ingestion tests | after 1 |
| 3 (JS/TS) | Proposed | 600–900 | new `test_treesitter_parser.py` | after 1; parallel to 2 |
| 4 (cross-file) | Proposed | 1500–2500 | new `test_symbol_resolver.py` + LLM test layers | after 2 |
| 5 (config) | Proposed | 800–1300 | new `test_config_dependency_agent.py` | after 1; parallel to 2/3 |

The Phase 4 estimate accounts for the SQS Standard queue, ECS Fargate
worker pool with long-polling, per-worker per-region Bedrock circuit
breaker, content-addressed cache, and Pyright LSP integration.
