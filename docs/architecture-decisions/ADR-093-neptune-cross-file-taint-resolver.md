# ADR-093: Neptune-Backed Cross-File Taint Resolver

## Status

**Accepted (v2)** | May 13, 2026 — Phase 0 complete; Phase 1 unblocked. Phases 6–7 Deferred (Cost Gate).

### Revision history

- **v1** (May 13, 2026) — Initial draft. Synthesized preliminary input from Tara / Tom / Sally / Tyler / Kelly. Resolved the JSON-vs-edges modeling question in favor of edges after industry-precedent research (Joern / Yamaguchi 2015 PhD thesis; CodeQL / Semmle; AWS Detective re:Inforce 2020/2021; Microsoft Defender for Cloud Graph 2023). Established tiered tenant model (T1 shared / T2 dedicated cluster / T3 dedicated VPC), content-addressed signed summaries with 30-day TTL and `DEPENDS_ON_SUMMARY` edges for transitive invalidation, write-fence via DynamoDB, RTO=0 fail-safe to in-memory, kill-switch via SSM Parameter Store, ADR-092-style offline static-scan substitute for the cost gate.
- **v2** (May 13, 2026) — Revised after three-agent design review (Tara AWS architecture, Sally cybersecurity, Jake senior code reviewer). Material corrections:
  - Corrected IAM-DB resource-policy misclaim (Neptune does not enforce row/property-level predicates server-side — IAM-DB authenticates the connection only).
  - Added §Network architecture (VPC endpoints for KMS / S3 / DynamoDB; SG rules; partition-templated ARNs for GovCloud/FIPS).
  - Added §Audit trail durability (S3 Object-Lock WORM destination with tier-parameterized retention; CloudWatch Logs alone is insufficient for AU-11).
  - Added §Key lifecycle (annual KMS asymmetric-key rotation; old keys retained `Disabled` for historical verification; compromised-signer revocation runbook + DynamoDB `summary_revocations` table consulted on every read).
  - Expanded NIST control mapping to FedRAMP-Moderate-complete (added AC-3(7), AC-6(9), SC-7(21), SC-12, SC-28, SI-7(1), SI-7(6), AU-2, AU-11).
  - Expanded threat model: T1212 (KMS key protection), T1136 (TenantScopedGremlinClient bypass via string-mode Gremlin and `.E()` entries), T1499.004 (per-tenant write-rate quota), T1556 (HITL-bypass via raised confidence — HITL gate re-verifies signature), T1565.002 (transport-bound signature payload binding session nonce + commit_sha + scan_id).
  - Hardened TenantScopedGremlinClient: reject string-mode Gremlin entirely; require tenant predicate on `.E()` entries; per-tenant write-rate quota for T1499.004.
  - T1 commercial SaaS now uses a per-tenant data-key envelope-encrypted by a shared KMS CMK for SC-28; T2/T3 break-glass approval required for Aura admin `kms:Decrypt` on tenant CMKs.
  - Added §Code architecture (Jake): `TaintContext` Protocol covering `record` / `lookup` / `lookup_with_units`; `build_taint_context` factory at `parsing/taint_context_factory.py` owning flag-reading + Neptune instantiation + whole-scan fail-safe; function-scoped TinkerGraph fixture with session-scoped JVM helper; `NeptuneBackedTaintContext` composes an `InMemoryTaintContext` for the preload cache (no parallel cache); Phase 3 acceptance gates on rescan-equivalence test.
  - Added §Observability (CloudWatch namespace `Aura/Scanner/TaintResolver`, 5 named alarms, IAM permission boundary on writer worker role).
  - §Risks accepted expanded with the three explicit residuals Tara named (Neptune p99 under concurrent multi-tenant load, IAM-DB auth signing overhead, GovCloud Bulk Loader throughput delta).
- **Accepted** (May 13, 2026) — Owner accepted v2 unmodified. Phase 1 (Test substrate) unblocked; Phases 6–7 remain Deferred (Cost Gate) per inherited ADR-092 posture.

### Phase tracker

| Phase | Description | State | Blocker | Re-engage when |
|---|---|---|---|---|
| **0 — ADR + three-agent review** | This document; Tara / Sally / Jake review captured in §Three-agent review | ✅ **Done** (v2, May 13, 2026) | — | — |
| **1 — Test substrate** | TinkerGraph session-JVM + function-graph fixture, equivalence harness (12 fixtures × {in-memory, Neptune} backends), fault-injection harness, static schema scan script | Planned | Phase 0 v2 accepted | Owner accepts v2 |
| **2 — Resolver (read path)** | `TaintContext` Protocol, `InMemoryTaintContext` (renamed), `NeptuneBackedTaintContext` (composes InMemory for preload cache), `TenantScopedGremlinClient` (bytecode-only, reject string-mode), `build_taint_context` factory, lazy Gremlin lookup with whole-scan fail-safe | Planned | Phase 1 complete; §Key lifecycle (Sally C-2) and write-fence KMS scoping (Sally C-4) finalized | Phase 1 green |
| **3 — Writer (GraphBuildStage)** | Batched vertex+edge upserts (bytecode/bindings, no string concat), KMS-signed summaries with transport-bound payload, monotonic `summary_version`, DynamoDB write-fence under per-tenant KMS CMK, per-tenant write-rate quota, S3 Object-Lock audit export | Planned | Phase 2 complete; rescan-equivalence test in Phase 1 harness validates write→read round-trip | Phase 2 green |
| **4 — Kill-switch + observability + runbook** | `scripts/disable_neptune_taint_resolver.py`, CloudWatch namespace `Aura/Scanner/TaintResolver` with 5 named alarms, IAM permission boundary on writer role, `scripts/revoke_summary_signatures.py`, `docs/runbooks/NEPTUNE_TAINT_RESOLVER_RUNBOOK.md` | Planned | Phase 3 complete | Phase 3 green |
| **5 — Offline static-scan substitute** | `scripts/adr_093_taint_schema_static_scan.py` (ADR-092 pattern) + `scripts/adr_093_taint_query_static_scan.py` (CI AST gate enforcing tenant predicate + ARN-walk for `arn:${AWS::Partition}`) | Planned | Phase 3 complete | Phase 3 green |
| **6 — Live validation** | First-prod-scan against single test tenant with feature flag on, kill-switch hot-standby, all 5 alarms armed | **Deferred (Cost Gate)** | Requires live AWS Neptune cluster | Live-AWS budget restored AND Phases 1–5 green |
| **7 — GA enablement** | Flip feature flag default on for enterprise tenants, tiered (T1 first; T2 after observation window; T3 after GovCloud parity validation) | **Deferred (Cost Gate)** | Phase 6 green | After Phase 6 validates |

### Cost gate context

Same posture as ADR-092: the platform is self-funded; live-AWS validation is paused. Phases 0–5 are code-complete deliverables that ship and are reviewed offline. Phases 6–7 require live Neptune (cost-gated). Phase 5's offline static-scan substitute is the load-bearing artifact that lets us ship code-complete without live validation — it catches write/read property drift and tenant-predicate omissions before production exposure.

## Context

### What just shipped

Phases 3.10 / 3.11 / 3.12 of issue #181 delivered cross-file inter-procedural taint analysis end-to-end:

- **3.10** added `FunctionSummary` Protocol + in-memory `CrossFileTaintContext` for Python (commit `f79c754`).
- **3.11** wired the remaining 7 language analyzers (JS / TS / Go / Java / Rust / C / C++) to populate and consume the context (commit `9c61499`).
- **3.12** added `assemble_dataflow_for_scan` — the bridge that hands a `ScanParseBundle` to `LLMVulnerabilityAnalyzer.analyze_candidates` (commit `2931a19`).

The in-memory implementation is per-scan: summaries are computed at the start of a scan, used during the same scan's two-pass dataflow extraction, and discarded at scan end. 36 cross-file tests + 15 scan-assembly tests = 51 tests covering the in-memory path. All eight Phase-1 languages have full intra-scan correctness.

### What this ADR addresses

The next product capability we must support for enterprise Day-1 GA is **incremental scans**: when scan N+1 sees only 10 changed files in a 10K-file repo, it should reuse summaries from scan N for the unchanged 9,990 files. The in-memory `CrossFileTaintContext` cannot do this because it lives in scan-process memory.

A persistent store of per-function taint summaries unlocks:

1. **Incremental scans** — 10×–100× latency win for small-diff scans.
2. **Cross-repo flows** — monorepos with shared libraries; scanned tenant repositories that import internal dependencies summarized by a previous scan.
3. **Audit trail** — "which summary version produced this finding?" answerable post-hoc.
4. **Cross-CWE / cross-fleet analysis** — long-term competitive feature work (ADR-089 long-horizon campaigns).

### Constraints

- **Cost gate**: no live-AWS validation until budget restored.
- **GovCloud parity**: design must work in commercial and GovCloud cloud partitions.
- **NIST 800-53 / FedRAMP-Moderate posture**: AC-3(7), AC-4, AC-6(9), AU-2, AU-11, AU-12, CM-6, SC-4, SC-7(21), SC-12, SC-28, SI-7, SI-7(1), SI-7(6).
- **Multi-tenant by default**: cross-tenant data leak is unrecoverable trust damage.
- **Same compute primitives**: the existing `graph_integration.py` already writes `VulnCodeUnit` vertices to Neptune at `neptune.aura.local:8182`. We reuse this substrate, not introduce a new datastore.

### Industry-precedent research (v1 → resolves edges vs JSON)

Five specialist agents (Tara / Tom / Sally / Tyler / Kelly) reviewed the preliminary direction. The single disagreement was JSON-encoded `sink_params` (Tom: atomic per-vertex, never queried in isolation today) vs edges (Tara: future cross-CWE traversal). Subsequent research into precedent for security graph data modeling was unanimous in favor of edges:

- **Joern / Code Property Graphs** — Fabian Yamaguchi, "Pattern-Based Vulnerability Discovery," PhD thesis 2015. CPGs model data-flow as first-class edges (REACHING_DEF, DDG). Thesis argues directly against JSON-encoded properties: vulnerability discovery is fundamentally a traversal problem.
- **CodeQL / Semmle** (GitHub acquisition $580M+, 2019) — different data model (datalog over relations) but the same principle: data-flow relationships are first-class relations, not blob-encoded properties.
- **AWS Detective on Neptune** — re:Inforce 2020/2021 reference architecture talks: edges over JSON for security investigations.
- **Microsoft Defender for Cloud Graph** (2023 published architecture) — risk relationships as edges.

Edges win this ADR.

## Decision

### Data model: edges, not JSON

Persisted taint summaries are modeled as graph edges. The schema:

```
(VulnCodeUnit {
    tenant_scan_qname,         # composite: "{tenant_id}|{scan_id}|{qualified_name}"
    tenant_scan_shortname,     # composite: "{tenant_id}|{scan_id}|{short_name}"
    code_unit_id,              # Phase 2 SHA-256 stable ID
    qualified_name, file_path, language, commit_sha,
    tenant_id, scan_id,
    summary_version,           # monotonic per-unit
    schema_version,            # ADR-093 schema version, module-level constant
    analyzer_version,          # bump on every dataflow.py release
    taxonomy_version,          # bump on taxonomy changes
    content_hash,              # sha256(normalized_body || analyzer_v || taxonomy_v)
    signed_at, signer_arn,
    summary_signature,         # KMS asymmetric signature over the binding payload
    signature_binding,         # {scan_id, commit_sha, session_nonce} — defeats T1565.002
    is_taint_returns_tainted   # vertex property; returns_tainted is atomic
})

(Sink {
    tenant_id, language, name,  # composite identity, ~110 per language
    cwe_id                      # e.g., "CWE-89"
})

(VulnCodeUnit) -[:SINKS_PARAM {
    param_index,
    confidence,                 # 0.95 / 0.75 / 0.65 / 0.50 per Phase 3.10 constants
    schema_version, analyzer_version,
    signature                   # per-edge KMS signature; supports per-edge revocation
}]-> (Sink)

(VulnCodeUnit) -[:DEPENDS_ON_SUMMARY {
    dep_summary_hash            # callee's content_hash at write time
}]-> (VulnCodeUnit)             # invalidation cascades when dep hash changes
```

`returns_tainted` is a vertex property (single bit, atomic). `sink_params` and dep tracking are edges.

**Why edges** (industry precedent above): security graph workloads are traversal-shaped; AURA's existing graph model (CALL_GRAPH, REFERENCES per issue #151) is edge-based; per-edge integrity supports revocation; Tyler's transitive-dependency invariant maps naturally onto `DEPENDS_ON_SUMMARY` edges.

**Tom's write fan-out concern** (per-function 2.5× writes) is bounded by batching: vertex+edge writes in single Gremlin submissions via `coalesce(unfold(), addV()/addE())` patterns at ~50–100 elements per submission; Neptune Bulk Loader for first-scan backfill (~100K elements/sec commercial; ~50–70K GovCloud); writer instance scales from `db.r6g.xlarge` to `db.r6g.4xlarge` past the 5M-vertex per-cluster threshold (Tara).

### Tenant isolation: tiered, defense in depth

| Tier | Customer profile | Isolation | Cost premium |
|---|---|---|---|
| **T1: Shared cluster** | Commercial SaaS default (FedRAMP-Low-equivalent) | (1) Property + composite-key partitioning; (2) `TenantScopedGremlinClient` bytecode-only client that rejects any traversal lacking `.has('tenant_id', T)` on entry vertex; (3) CI AST gate in `scripts/adr_093_taint_query_static_scan.py`; (4) Per-tenant data key envelope-encrypted under a shared KMS CMK (SC-28); (5) Per-tenant write-rate quota | Included |
| **T2: Dedicated cluster** | FedRAMP-Moderate / CMMC L2 / regulated commercial | All of T1 + dedicated Neptune cluster per tenant + per-tenant KMS asymmetric CMK + Aura admin `kms:Decrypt` denied by default (break-glass approval required) | ~$300/mo/tenant |
| **T3: Dedicated VPC** | GovCloud / defense | All of T2 + dedicated VPC + FIPS endpoints (`neptune-fips.{region}.amazonaws.com`) + air-gappable + cross-region replication of S3 Object-Lock audit destination | TBD |

**Correction (v2)**: Neptune's IAM-DB authentication authenticates the connection only; it does **NOT** enforce row/property-level predicates server-side. The `Condition: tenant_id` claim in the v1 ADR was incorrect. The load-bearing tenant-isolation controls are client-side: `TenantScopedGremlinClient` + CI AST gate. IAM-DB auth scopes the per-worker connection to the cluster ARN.

**TenantScopedGremlinClient hardening (Sally)**:
- Reject string-mode Gremlin entirely (`submit_string`, `submit("g.V()...")`); accept only bytecode traversals with explicit `bindings={}`. Test: `test_string_mode_gremlin_rejected`.
- Require tenant predicate on `.E()` entries (`g.E().has('cwe_id','CWE-89')` is rejected unless source vertex is tenant-filtered). Test: `test_edge_entry_requires_tenant_predicate`.
- Per-tenant write-rate quota (summaries/min) enforced at the repository layer; CloudWatch alarm on `summaries_written_per_tenant > p99 * 3`. Test: `test_summary_write_rate_quota_enforced`. Defeats T1499.004.

### Summary integrity: content-addressed, signed, transport-bound, TTL-bounded

- **Content-addressed**: `content_hash = sha256(normalized_function_body || analyzer_version || taxonomy_version)`. Function-body / analyzer / taxonomy change invalidates the summary automatically.
- **KMS-signed**: every persisted summary carries a signature over its payload, signed by the worker's per-tenant KMS asymmetric key (`signer_arn`). Verified on read; mismatch = treat as cache miss + emit `taint.summary.bad_signature` alarm.
- **Transport-bound signature** (Sally C-5): signature payload includes `{scan_id, commit_sha, session_nonce}`. A signature lifted from a prior scan's persisted record cannot replay in a new scan because the binding doesn't match. Defeats T1565.002. Test: `test_signature_includes_transport_binding`.
- **TTL-bounded**: hard 30-day expiry regardless of code change. Bounds the lifetime of any stealth-poisoned summary.
- **Transitive dep tracking**: `DEPENDS_ON_SUMMARY` edges record the callee's `content_hash` at write time. When a callee's summary hash changes, all upstream summaries invalidate via graph cascade.
- **Confidence floor**: persisted summary may **raise** a downstream finding's confidence but may **never lower** it below the in-memory baseline. Closes the confidence-sinking attack.
- **HITL-bypass defense** (Sally T1556): HITL gate independently re-verifies summary signature AND requires the signature chain to terminate at a tenant-pinned root before honoring a confidence elevation. A poisoned summary cannot elevate a chain past the HITL-auto-approve threshold. Test: `test_poisoned_summary_cannot_elevate_past_hitl_threshold`.

### Key lifecycle and revocation (v2)

- **Rotation**: per-tenant KMS asymmetric CMK annual rotation. Old key retained `Disabled` (not deleted) for historical-summary verification; new summaries always signed with the current key.
- **Revocation runbook**: when summaries signed in time window [T1, T2] become untrustworthy (worker compromise; signing-bug release):
  1. Operator runs `scripts/disable_neptune_taint_resolver.py` (kill-switch via SSM).
  2. Operator runs `scripts/revoke_summary_signatures.py --signer-arn=X --from=T1 --to=T2` which writes a revocation entry to DynamoDB table `summary_revocations` (per-tenant KMS-CMK-encrypted).
  3. `NeptuneTaintRepository.verify()` checks the revocation table BEFORE signature verification; revoked summaries → cache miss + re-derive.
  4. Background job marks affected vertices `quarantined=true`; next scan deletes them.
- **Compromised worker**: worker IAM role's `kms:Sign` permission revoked at IAM; revocation entry written immediately; alarm emitted.

Test: `test_revoked_signature_range_treated_as_cache_miss`.

### Audit trail durability (v2)

ADR-092 set the precedent: AU-11 evidence chains require WORM storage. CloudWatch Logs alone is mutable by admins and insufficient.

- **Primary**: CloudWatch Log Group `aura/scanner/taint-summaries`, KMS-encrypted, 90-day retention. Carries `(scan_id, tenant_id, signer_arn, summary_hash, write_timestamp)` per signed summary.
- **Durable**: nightly export to S3 with **Object-Lock in compliance mode**. Bucket-level KMS CMK. Retention parameterized per compliance tier:
  - FedRAMP-Low / commercial: **13 months** (1 yr + 30-day buffer)
  - FedRAMP-Moderate: **13 months**
  - FedRAMP-High: **37 months** (3 yr + 30-day buffer)
- **GovCloud**: same pattern in `aws-us-gov` partition with FIPS-validated KMS; cross-region replication for SC-7 boundary survival.

### Read pattern: lazy with eager preload

1. **Eager preload at scan start**: paginated Gremlin query loads all summaries for the scan's repo + tenant scope into the in-memory cache (composes `InMemoryTaintContext` — no parallel cache). Pagination: 500–1000 vertices per batch, parallel fetch with 4–8 concurrent reader connections, ~400ms per batch on `r6g.xlarge` commercial. Use explicit `valueMap(true, ...explicit-list...)` to avoid full-vertex pulls.
2. **Lazy single-vertex lookup on miss**: cross-repo cases. Single Gremlin `g.V().has('tenant_scan_qname', tsq).not(has('file_path', caller_file))` with explicit property projection.
3. **Intra-scan two-pass stays in-memory**: per Tyler, pass 1 → pass 2 stays in-memory within a scan; persistence is end-of-scan only.

### Write pattern: end-of-scan, success-gated, fenced

1. Two-pass dataflow extraction completes in-memory.
2. Pre-write integrity check: every summary is content-hashed, signed with transport binding, and stamped with versions.
3. Batched Gremlin upsert via GraphBuildStage: single transaction per file batch, ~50–100 elements per submission, bytecode-only.
4. **Write-fence via DynamoDB** (Tom; Sally C-4): after `g.tx().commit()` returns, GraphBuildStage flips `scan_state[scan_id].taint_write_complete = true` in a DynamoDB table encrypted with the **per-tenant KMS CMK** (not a shared CMK; closes the cross-tenant fence-read vector). Any subsequent scan's resolver refuses to preload from this `scan_id` until the flag is set. Closes the Neptune reader-vs-writer eventual-consistency window (20–100ms).
5. **Failure on write**: scan continues, in-memory chains are emitted as findings, but persistence is logged failed and the fence flag stays false. Next scan re-derives.

### Failure mode: whole-scan degrade to in-memory (Jake)

Neptune unreachable, slow (>5s p99), or signature-mismatched at the preload step → factory returns `InMemoryTaintContext`; the rest of the scan never touches Neptune. **Whole-scan consistency over per-lookup resilience.** Lazy-lookup misses inside a Neptune-using scan treat unavailability as a cache miss and re-derive locally; do not flip the whole context mid-scan.

Emit `taint.resolver.degraded_to_memory` metric at the factory. Single point of fallback observability.

### Code architecture (v2, Jake)

1. **`TaintContext` Protocol** in `parsing/dataflow.py` next to `FunctionSummary`. Surface: `record()`, `lookup()`, `lookup_with_units()`. The existing `CrossFileTaintContext` dataclass is renamed `InMemoryTaintContext`; `CrossFileTaintContext` remains as a one-release type alias for back-compat. `NeptuneBackedTaintContext` implements the same Protocol.

2. **`build_taint_context` factory** in new module `parsing/taint_context_factory.py`. Owns: SSM flag read, Neptune client instantiation via `TenantScopedGremlinClient`, connectivity-probe-with-preload at scan start, whole-scan fail-safe (return `InMemoryTaintContext` on probe failure). One-line seam in `scan_assembly.py:158`: `ctx = build_taint_context(scan_id=scan_id, tenant_id=tenant_id, config=cfg)`. The `ScanParseBundle.cross_file_context` type annotation at `scan_assembly.py:90` widens from `Optional[CrossFileTaintContext]` to `Optional[TaintContext]`.

3. **`NeptuneBackedTaintContext` composes `InMemoryTaintContext`** for the preload cache. No parallel cache layer. Read path: probe + preload INTO an in-memory context; cache hits are the in-memory path; misses do a single Gremlin lookup and write back.

4. **No module-level singleton** for the repository. The Gremlin connection pool can be a singleton; the tenant-scoped client wrapper must be per-scan (multi-tenant test leakage risk).

5. **Schema-versioning code shape**: `schema_version: Final[int] = 1` as a module-level constant in `parsing/neptune_taint_repository.py`. Single integer comparison on read; mismatch → cache miss. No `Compatibility` object; no in-place migrations. Static scan reads the constant via AST, not import.

6. **Test substrate scope** (`tests/services/vulnerability_scanner/parsing/conftest.py`):
   - **Session-scoped JVM** fixture (`gremlin_server`): one Gremlin server process per pytest-xdist worker.
   - **Function-scoped graph** fixture (`tinker_graph`): empty graph; teardown via `g.V().drop().iterate()`.
   - With xdist N workers: N JVMs (~3s cold start each, acceptable); per-test isolation preserved.

7. **Phase 3 acceptance gate**: rescan-after-scan equivalence test. Scan N writes summaries → scan N+1 reads them → produces chains identical to a fresh in-memory scan. Test name: `test_rescan_uses_persisted_summaries_and_matches_fresh_scan`.

### Network architecture (v2, Tara)

- **VPC endpoints** (interface unless noted; required for cost + GovCloud FIPS):
  - `com.amazonaws.{region}.kms` — signature operations.
  - `com.amazonaws.{region}.dynamodb` (gateway) — write-fence + revocation table.
  - `com.amazonaws.{region}.s3` (gateway) — Bulk Loader + Object-Lock audit destination.
  - `com.amazonaws.{region}.neptune-db` — Bulk Loader API; mandatory in GovCloud for FIPS.
  - `com.amazonaws.{region}.logs` — CloudWatch audit log shipping.
- **Security groups**: writer worker SG → Neptune cluster SG on 8182 only. Explicit deny 0.0.0.0/0. No NACL change.
- **Partition-templated endpoints**: every ARN in new modules uses `arn:${AWS::Partition}:...`. FIPS endpoint for T3: `neptune-fips.{region}.amazonaws.com`. Unit test asserts endpoint string contains `fips` when partition is `aws-us-gov`. Phase 5 static scan greps `arn:aws:` in new modules and fails the build on any hit.
- **No cross-account Neptune access**: one cluster per account. T2 dedicated clusters live in the platform account by default; tenant-account-hosted clusters are out of scope for Day-1 GA.

### Observability and runbook (v2, Tara + Sally)

CloudWatch namespace: `Aura/Scanner/TaintResolver`. Five mandatory alarms:

| Alarm | Threshold | Severity |
|---|---|---|
| `summary.bad_signature` | >0 in 5min | P1 — possible tampering or revoked key in use |
| `summary.cache_miss_rate` | >50% over 30min | P2 — preload underperforming or schema drift |
| `summary.write_fence_timeout` | >0 in 5min | P2 — Neptune write or DynamoDB fence write failed |
| `gremlin.p99_latency_ms` | >500 over 15min | P3 — read path degrading |
| `tenant_predicate_rejection` | >0 ever | P1 — TenantScopedGremlinClient rejected a query; indicates code bug or active probe |

**IAM permission boundary** on the writer worker role: denies `neptune-db:*` outside the specific cluster ARN; denies `kms:Sign` outside the per-tenant signing CMK alias pattern (`alias/aura/scanner/taint-signing-{tenant_id}`).

**Runbook deliverable in Phase 4**: `docs/runbooks/NEPTUNE_TAINT_RESOLVER_RUNBOOK.md`. Must include: RTO=0 / RPO=∞ statement (this is cache-class, not system-of-record), kill-switch procedure (<5min remediation without redeploy), revocation procedure, "stale-summary suspicion → kill-switch → next scan re-derives" playbook, the 5 alarms with response steps.

Cross-doc updates: `docs/support/architecture/disaster-recovery.md` adds one paragraph naming this cluster cache-class with no restore procedure.

## Consequences

### Positive

- Incremental scans become correct and fast (cross-scan persistence + dep-tracking invalidation).
- Cross-repo flows become possible.
- Audit trail survives scans (KMS-signed summaries with provenance + S3 Object-Lock WORM retention).
- Compositional traversal queries (cross-CWE, cross-fleet, compliance reporting) become first-class.
- Edge-based data model composes with the rest of AURA's graph.

### Negative

- Two new failure surfaces: Neptune availability, schema drift. Mitigated by whole-scan fail-safe + static scan + kill-switch + 5 alarms.
- Per-scan write cost increase: 2.5× writes per function on average. Batched, parallelizable, amortized.
- Storage cost: ~$870/mo amortized across 100 enterprise T1 tenants (Tara); ~$300/mo/tenant T2 premium; T3 TBD.
- Complexity: ~3–4K LOC of resolver/writer/factory + ~1–2K LOC test substrate + runbook + 2 static-scan scripts.
- First-prod-scan is the live validation gate (cost-gate posture inherited from ADR-092).

### Day-1 enterprise GA blockers (must ship before flag flip)

Per the three-agent review, the following are non-negotiable for Phase 7 flag flip:

1. **`TenantScopedGremlinClient` hardening + CI AST gate** (Sally + Tara + Kelly): bytecode-only; reject string-mode; require tenant predicate on `.E()` entries; per-tenant write-rate quota.
2. **12-fixture equivalence harness** (Kelly + Jake): both backends produce byte-identical chains. Rescan-equivalence is the Phase 3 gate.
3. **`DEPENDS_ON_SUMMARY` edges on every persisted summary** (Tyler): transitive invalidation is correctness-critical.
4. **KMS-signed summaries with transport binding** (Sally): defeats T1565.001 + T1565.002 + replay.
5. **S3 Object-Lock WORM audit destination** (Sally C-1): AU-11 evidence durability.
6. **`summary_revocations` table check on read path** (Sally C-2): bounds compromised-signer blast radius.
7. **Static schema scan + tenant-predicate AST gate in CI** (Kelly + Tara): catches drift before production exposure.
8. **`TaintContext` Protocol + factory seam + composed cache** (Jake): code-shape correctness; whole-scan fail-safe.

### Risks accepted (v2)

Three explicit residuals from the cost-gate posture (Tara):

1. **Neptune p99 latency under concurrent multi-tenant load** — TinkerGraph is single-process; cannot model lock contention, connection-pool exhaustion, or the reader-vs-writer eventual-consistency window the DynamoDB fence is sized for. Validated by feature-flagged Phase 6 with alarms armed and kill-switch hot-standby.
2. **IAM-DB auth signing overhead** — ~30–80ms per connection; not modeled in TinkerGraph. Mitigated by connection pooling.
3. **GovCloud Bulk Loader throughput delta** — historically 30–50% slower than commercial; the 100K elements/sec figure is commercial. T3 backfill latency expectations footnoted accordingly.

Plus structural residuals:

4. **First-prod-scan against real Neptune is the live validation** — feature-flagged, single-tenant, kill-switch hot-standby. Same posture as ADR-092.
5. **Edge fan-out write cost at very-large-scale (100K+ functions/scan)** — mitigated by Bulk Loader for first scan + batched upserts + writer instance scaling at the 5M-vertex threshold.

## Threat model (v2)

Mapped to MITRE ATT&CK + NIST 800-53:

| Threat | ATT&CK | NIST | Control in this ADR |
|---|---|---|---|
| Confidence-sinking via persisted summaries | T1565.001 | SI-7 | Content-addressed + signed; confidence floor (persisted may raise but never lower) |
| Cross-tenant taint summary leak | T1078.004 | SC-4, AC-4 | T1 client-side enforcement (4-layer); T2/T3 dedicated cluster |
| Summary poisoning by compromised worker | T1565.001, T1195.002 | SI-7(1), SI-7(6) | KMS-signed with transport binding; revocation runbook |
| KMS signing-key compromise | T1212 | SC-12 | Per-tenant CMK; annual rotation; old keys retained `Disabled`; CloudTrail `kms:Sign` rate-anomaly alarm |
| `TenantScopedGremlinClient` bypass | T1136 | AC-3(7) | Bytecode-only client; string-mode rejected; `.E()` entry checked; CI AST gate |
| Summary table flooding | T1499.004 | SC-7 | Per-tenant write-rate quota + alarm |
| HITL gate bypass via raised confidence | T1556 | AC-6(9) | HITL re-verifies summary signature; signature chain must terminate at tenant-pinned root |
| In-flight summary tampering worker↔Neptune | T1565.002 | SC-12, SC-28 | Transport-bound signature payload (`scan_id`, `commit_sha`, `session_nonce`) |
| Insider threat — Aura admin reading tenant summaries | — | AC-6(9), SC-12 | T1 acceptable with dual-control + audit; T2/T3 break-glass approval for `kms:Decrypt` |

## NIST 800-53 control mapping (v2)

| Control | Implementation |
|---|---|
| **AC-3(7)** Role-Based Access Control | Per-tenant IAM-DB role; T2/T3 dedicated cluster roles |
| **AC-4** Information Flow Enforcement | `TenantScopedGremlinClient` bytecode rejection; CI AST gate |
| **AC-6(9)** Auditing Use of Privileged Functions | Every `kms:Sign` event + TenantScopedGremlinClient rejection event → AU-12 records |
| **AU-2** Auditable Events | Defined event catalog: write, read, sign, verify, revoke, kill-switch flip |
| **AU-11** Audit Record Retention | 13mo (Mod) / 37mo (High) S3 Object-Lock compliance mode |
| **AU-12** Audit Generation | CloudWatch Log Group `aura/scanner/taint-summaries` with KMS encryption |
| **CM-6** Configuration Settings | `schema_version` + `analyzer_version` + `taxonomy_version` stamped on every summary |
| **SC-4** Information in Shared Resources | T1: client-side tenant predicate + composite keys; T2/T3: separate clusters |
| **SC-7(21)** Isolation of Security Tools | Scanner workers in dedicated subnet/SG |
| **SC-12** Cryptographic Key Establishment | Per-tenant KMS asymmetric CMK; annual rotation; documented lifecycle |
| **SC-28** Protection at Rest | T1: per-tenant data key envelope under shared CMK; T2/T3: per-tenant CMK |
| **SI-7** Software/Firmware Integrity | Signed summaries; signature verified on every read |
| **SI-7(1)** Integrity Checks | Auto-verify on every cache hit before honoring |
| **SI-7(6)** Cryptographic Protection | KMS RSASSA_PSS_SHA_256 signatures |

## Migration / Rollout

This is a Day-1 enterprise feature; there is no in-place data migration. Existing in-memory `CrossFileTaintContext` (renamed `InMemoryTaintContext`) continues as the fail-safe path indefinitely.

Rollout sequence per the phase tracker. Phase 6 is gated by Phases 1–5 being green. Phase 7 is tiered: T1 commercial first; T2 after observation window; T3 after GovCloud parity validation.

## Three-agent review

Per ADR-092 precedent, this ADR was reviewed by Tara (AWS architecture), Sally (cybersecurity), and Jake (senior code reviewer). All three vote **ACCEPT-WITH-CHANGES**; v2 integrates the required changes. Verdict captured below.

### Tara (AWS architecture)

**Verdict**: accept-with-changes. Data model + tiering + write-fence + fail-safe posture are sound; edges-over-JSON confirmed.

Required v2 changes (all integrated): correct the IAM-DB resource-policy misclaim (Neptune does not enforce row-level predicates server-side); add §Network architecture with VPC endpoints + SGs + partition-templated ARNs + ARN-walk static check; add §Observability with CloudWatch namespace `Aura/Scanner/TaintResolver` + 5 named alarms + IAM permission boundary on writer role; document the cache-class RTO=0 / RPO=∞ posture in 3 operational locations (CloudFormation BackupRetentionPeriod comment, new runbook, `disaster-recovery.md`); explicit residual-risk list (Neptune p99 under concurrent load, IAM-DB overhead, GovCloud Bulk Loader delta).

### Sally (cybersecurity)

**Verdict**: accept-with-changes. Day-1 design materially stronger than ADR-092 baseline; five control gaps to close (all integrated in v2).

Required v2 changes (all integrated): C-1 S3 Object-Lock WORM destination with tier-parameterized retention; C-2 KMS key annual rotation + compromised-signer revocation runbook + DynamoDB `summary_revocations` table consulted on read; C-3 expanded NIST mapping (AC-3(7), AC-6(9), SC-7(21), SC-12, SC-28, SI-7(1), SI-7(6), AU-2, AU-11); C-4 DynamoDB write-fence under per-tenant KMS CMK; C-5 signature payload binds transport context. Plus 5 threat-model additions (T1212, T1136, T1499.004, T1556, T1565.002) and TenantScopedGremlinClient hardening (reject string-mode, `.E()` entry checks, per-tenant write-rate quota).

Required test names (integrated into Phase 1 acceptance): `test_string_mode_gremlin_rejected`, `test_edge_entry_requires_tenant_predicate`, `test_revoked_signature_range_treated_as_cache_miss`, `test_poisoned_summary_cannot_elevate_past_hitl_threshold`, `test_signature_includes_transport_binding`, `test_summary_write_rate_quota_enforced`, `test_kms_sign_rate_anomaly_alarms`.

Insider-threat posture: T1 acceptable Day-1 with dual-control + audit; T2/T3 require break-glass approval for Aura admin `kms:Decrypt` on tenant CMKs (integrated into Tier table).

### Jake (senior code reviewer)

**Verdict**: accept-with-changes. Data model + phase tracker sound; 3 interface decisions under-specified in v1 (all integrated in v2).

Required v2 changes (all integrated):

1. **`TaintContext` Protocol** in `parsing/dataflow.py` near `FunctionSummary`. Surface: `record` / `lookup` / `lookup_with_units`. Rename existing `CrossFileTaintContext` → `InMemoryTaintContext`; keep `CrossFileTaintContext` as one-release type alias. `NeptuneBackedTaintContext` implements same Protocol. `ScanParseBundle.cross_file_context` annotation at `scan_assembly.py:90` widens to `Optional[TaintContext]`.

2. **`build_taint_context` factory** in new module `parsing/taint_context_factory.py`. Owns SSM flag-read, `TenantScopedGremlinClient` instantiation, probe+preload, whole-scan fail-safe. `scan_assembly.py:158` becomes a single factory call.

3. **Test substrate**: function-scoped `tinker_graph` fixture + session-scoped `gremlin_server` JVM fixture in `tests/services/vulnerability_scanner/parsing/conftest.py`. Phase 3 acceptance includes `test_rescan_uses_persisted_summaries_and_matches_fresh_scan`.

Plus anti-patterns flagged (integrated): no module-level singleton for the repository; `NeptuneBackedTaintContext` composes an `InMemoryTaintContext` for preload cache (no parallel cache); bytecode/bindings only — never string concat into Gremlin.

## Related ADRs and references

- **ADR-084**: Native Vulnerability Scanning Engine — parent.
- **ADR-085**: Deterministic Verification Envelope — composes via the signing/integrity model.
- **ADR-089**: Long-Horizon Security Campaigns — cross-repo chain analysis use case.
- **ADR-090**: GraphRAG Ingestion Edge Completeness — edge-modeling precedent inside Neptune.
- **ADR-092**: CloudFormation Deploy-Role Wildcard Scoping — cost-gate posture and offline static-scan substitute pattern.
- **Issue #181**: vulnerability_scanner/parsing tree-sitter real implementation.
- **Yamaguchi 2015** — "Pattern-Based Vulnerability Discovery" PhD thesis (industry precedent for edge-modeled CPGs in security).
- **GitHub Advanced Security / CodeQL** — datalog-relational data model.
- **AWS Detective on Neptune** — re:Inforce 2020/2021 reference architecture.
