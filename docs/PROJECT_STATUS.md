# Project Aura: Development Status

**Last Assessment:** May 12, 2026
**Status:** All 9 deployment phases complete (Foundation, Data, Compute, Application, Observability, Serverless, Sandbox, Security, Scanning Engine). Disaster Recovery initiative (#143) **complete -- all 13 sub-issues closed**. Buildspec line-cap remediation (#131) **complete -- all 4 sub-issues + 5 follow-ups closed via Tara's runtime-budget approach** (cold-start `TimeoutInMinutes` raised to 480 on the four parent CodeBuild projects, 11 dead scaffold buildspecs deleted, parent → sub-layer CodeBuild nesting forbidden going forward, orphan stacks wired). May 9, 2026 documentation + security pass closed an additional 4 doc-refresh follow-ups (#158, #159, #160, #161) and 2 CodeQL alerts (#271 critical code injection, #272 medium unpinned action). Issue #142 (eslint-plugin-react swap) reviewed and deferred per its own trigger conditions. **GTM-readiness audit (#163) CLOSED on May 12, 2026 after 14 waves of remediation (Waves 1-14).** Waves 6-14 followed Wave 5a and shipped: defense-in-depth guardrails (IMMUTABLE_GUARDRAILS, prod-tier signer assertion, log retention 7d→30d, workflow pinning), doc accuracy corrections (React 19 / JavaScript / Vite stack restatement, broken-link fixes), top-level dashboard widget live-wiring (5 metrics endpoints + system-health endpoint backing MTTR/AssetCriticality/ComplianceDrift/InsiderRisk widgets + HealthCheckModal -- closes the audit's "DO-NOT-SHIP" frontend-mock finding), customer-visible TODO/toast remediation (8 CommandPalette/CKGEConsole/KnowledgeGraph silent click-handlers replaced with toast feedback), buildspec inline create/update refactor (29 sites → canonical `aws cloudformation deploy --no-fail-on-empty-changeset`, -640 LOC across 3 buildspecs), frontend lint sweep (281→93 problems, 20→0 errors), and ADR-092 (CFN deploy-role wildcard scoping, **Accepted v2 with deploy phases Deferred (Cost Gate)** -- Phase 2 code complete + offline static action scanner substitute). Remaining tracked work: #180 (out-of-band SNS/PagerDuty/Slack subscribers + GitHub secrets + 68 deaf alarms, OPEN, external-endpoint dependency), #181 (vulnerability_scanner/parsing real tree-sitter implementation, OPEN, multi-week pure-code effort), #182 (tech-debt tracker, substantially closed -- buildspec/lint/IAM code-merge complete; ADR-092 deploy phases Deferred (Cost Gate); "Coming Soon" panels won't-fix).

---

## Overview

| Metric | Value |
|--------|-------|
| **Overall Completion** | 99% (GTM-readiness audit #163 closed; remaining work tracked in #180 external-endpoints, #181 tree-sitter implementation, #182 tech-debt tracker) |
| **Lines of Code** | 375,000+ |
| **Test Suite** | ~25,190+ tests as of May 13, 2026 (~25,176+ through ADR-093 Phase 2 + 14 ADR-093 Phase 3 tests: 3 addV/property tenant-predicate hardening + 6 persist_summaries write-path + 5 rescan-equivalence acceptance). The May 10 GTM audit observed 25 hard failures at maxfail in a full sweep and one order-dependent crash path now hardened (commit c8aa3df). A clean full-suite re-run with all wave-1 through wave-14 fixes is still pending; the "0 failures" claim should be re-asserted only after that run. |
| **Architecture Decision Records** | 93 ADRs (88 Deployed/Accepted, 1 Reserved [082], 2 Proposed [087, 089], 1 Accepted-with-deploy-Deferred [092], 1 Accepted-Phase-1-unblocked [093]; ADR-090 GraphRAG ingestion edge completeness + ADR-091 Cognito cross-region DR + ADR-092 CFN deploy-role wildcard scoping + ADR-093 Neptune-backed cross-file taint resolver added in May 2026; counted via `ls docs/architecture-decisions/ADR-*.md | wc -l`) |
| **CloudFormation Templates** | 175 templates (170 in `deploy/cloudformation/` + 5 in `deploy/cloudformation/service-catalog-products/`, counted by `AWSTemplateFormatVersion` header on May 12, 2026; includes both CodeBuild project templates and infrastructure templates. The 13 templates under `deploy/cloudformation/archive/` are excluded.) |
| **Buildspecs** | 28 buildspec files in deploy/buildspecs/ (down from 38 after #131 cleanup -- 11 dead scaffolds deleted, -1,467 LOC) |
| **CodeBuild Projects** | 19 projects (9 parent layers + 10 sub-layers) |
| **Deployment Phases** | 9 of 9 complete |
| **GovCloud Readiness** | Service compatibility: 19/19. **ARN partition compliance: complete (Wave 3, commit 3929913)** -- 204 hardcoded `arn:aws:` strings swept to `arn:${AWS::Partition}:` across 19 templates; the 4 remaining instances are inside YAML `#` comments (CLI examples for human readers). All 21 originally-affected templates pass `./scripts/cfn-lint-wrapper.sh`. Bedrock IAM model authorization on current-gen Sonnet 4.5 / Haiku 4.5 (commit a025ac5). |

---

## Infrastructure Phases

| Phase | Layer | Components | Status |
|-------|-------|------------|--------|
| 1 | Foundation | VPC, IAM, Security Groups, WAF, VPC Endpoints | Complete |
| 2 | Data | Neptune, OpenSearch, DynamoDB, S3 | Complete |
| 3 | Compute | EKS cluster, EC2 node groups, ECR | Complete |
| 4 | Application | Bedrock Integration, ECR, dnsmasq with DNSSEC | Complete |
| 5 | Observability | Secrets Manager, Monitoring, Cost Alerts, Budgets | Complete |
| 6 | Serverless | Lambda, EventBridge, Step Functions, Chat Assistant | Complete |
| 7 | Sandbox | HITL Workflow, Step Functions, ECS cluster | Complete |
| 8 | Security | AWS Config, GuardDuty, Drift Detection | Complete |
| 9 | Scanning Engine | Vulnerability Scanner, Step Functions Pipeline | Complete |

---

## Key Components

### Core Platform

| Component | Status | Details |
|-----------|--------|---------|
| Agent Orchestrator | Complete | Multi-agent coordination with Coder, Reviewer, Validator agents |
| Hybrid GraphRAG | Complete | Neptune graph + OpenSearch vector + BM25 keyword search |
| HITL Workflows | Complete | 4 autonomy levels, 7 policy presets (ADR-032) |
| Constitutional AI | Complete | 16-principle critique-revision pipeline, 463 tests (ADR-063) |
| Sandbox Validation | Complete | ECS Fargate network-isolated environments |
| Context Engineering | Complete | 7 services deployed (ADR-034) |

### Security & Governance

| Component | Status | Details |
|-----------|--------|---------|
| Semantic Guardrails Engine | Complete | 6-layer threat detection, 793 tests (ADR-065) |
| Agent Capability Governance | Complete | 4-tier tool classification, runtime enforcement, 322 tests (ADR-066) |
| Context Provenance & Integrity | Complete | Trust scoring, anomaly detection, quarantine, 275 tests (ADR-067) |
| Runtime Agent Security | Complete | Traffic interception, behavioral baselines, AURA-ATT&CK, 1005 tests (ADR-083). Wave 3 added real boto3 CloudWatch metric emitter (commit 17d9827) and a FastAPI stub router (12 endpoints + health, commit 2652b2f). Wave 5a wired the 12 handlers to a per-process `RuntimeSecurityHistoryStore` and replaced the Neptune `NotImplementedError` writers in `graph_integration.py` with real Gremlin upserts (commits 3a441f2 + 101148e). |
| Policy-as-Code GitOps | Complete | OPA Rego validation, policy simulation, 98 tests (ADR-070) |
| ABAC Authorization | Complete | Clearance levels, multi-tenant isolation, 115 tests (ADR-073) |
| Agentic Identity Lifecycle | 100% | Decommission assurance, 15 credential enumerators, ghost scanner, self-modification sentinel, delegation trust envelope, 7 channel verifiers, 271 tests (ADR-086) |

### AI Optimizations

| Component | Status | Details |
|-----------|--------|---------|
| Titan Neural Memory | Complete | Continuous learning, 237 tests (ADR-024) |
| Recursive Context Scaling | Complete | 100x context window expansion, 167 tests (ADR-051) |
| Self-Play SWE-RL | Complete | Dual-role self-play training pipeline, 354 tests (ADR-050) |
| GPU Workload Scheduler | Complete | Self-service GPU jobs, queue management, 391 tests (ADR-061) |
| Constraint Geometry Engine | Phase 1 | 7-axis constraint space, 358 tests (ADR-081) |

### Disaster Recovery (Umbrella #143 -- COMPLETE, all 13 sub-issues closed)

| Sub-Issue | Status | Details |
|-----------|--------|---------|
| DR-1 (#144) | Closed | DynamoDB Global Tables for 7 Tier 1 tables (4 templates: idp-infrastructure, dynamodb, repository-tables, onboarding); per-region CMKs for auth tables; replication-lag alarms (5min) |
| DR-1.0 (#153) | Closed | Cross-region foundation: per-region CMKs (NOT MRKs) for replicated auth tables -- `kms.yaml` AuthCredentialsKMSKey + `kms-replica-secondary.yaml` (Layer 1.10) AuthCredentialsReplicaKey |
| DR-1.1 (#154) | Closed | Audit-shape tables: 3 tables (IdPAuditTable, AutonomyDecisionsTable, PolicyAuditTable) keep regional shape; Streams -> Kinesis -> Firehose -> S3 Object Lock (governance, ~7yr) via `audit-pipeline.yaml` (Layer 5.12) + CRR via `audit-pipeline-replica.yaml` (Layer 5.13) |
| DR-1.2 (#155) | Closed | AnomaliesTable + CodebaseMetadataTable reclassified to Tier 1 Global Tables |
| DR-2 (#145) | Closed | Cognito DR via Lambda-based mirror to DDB Global Table + standby pool + hydrator Lambda + force re-auth (ADR-091; runbook: `COGNITO_FAILOVER_RUNBOOK.md`); 4 templates (`cognito.yaml` modified, `cognito-secondary.yaml` Layer 4.14, `cognito-dr-hydrator.yaml` Layer 6.21, `user-mirror-table.yaml` Layer 2.22); per-region CMKs for mirror table |
| DR-3 (#146) | Closed | Neptune cross-region failover via existing AWS Backup + `NEPTUNE_FAILOVER_RUNBOOK.md` (CFN does not support Neptune Global Database -- verified May 2026) |
| DR-3.0 (#156) | Closed | Secondary-region VPC foundation (`networking-secondary.yaml`, Layer 1.11): 10.1.0.0/16 in us-west-2, 3 private subnets, VPC Flow Logs, prod-only |
| DR-4 (#147) | Closed | OpenSearch cross-region failover via AWS Backup hourly snapshots + cross-region copy + `OPENSEARCH_FAILOVER_RUNBOOK.md` (HourlyBackupPlan extended with CopyActions; OpenSearchBackupSelection added) |
| DR-5 (#148) | Closed | S3 cross-region replication on `ArtifactsBucket` + `CodeRepositoryBucket` (`s3.yaml` modified, `s3-replica.yaml` Layer 2.21); constructed-ARN replication role |
| DR-6 (#149) | Closed | Secrets Manager native multi-region replicas for 10 Tier 1 secrets (Bedrock config, API keys, JWT signing keys, IdP credentials) |
| DR-7 (#150) | Closed | Multi-region failover orchestration pipeline: `multi-region-failover.yaml` (Layer 5.15) provides Route 53 health checks + failover records + 3 cutover Lambdas (Cognito hydrator trigger, Cognito SSM cutover, data-plane secret cutover); `multi-region-pipeline.yaml` (Layer 6.22) is a Step Functions Standard state machine with HITL approval gates at every destructive step + dual execution modes (failover / rollback); operator runbook `MULTI_REGION_DR_OPERATIONS.md` composes the per-service runbooks into a single sequence |
| DR-8 (#151) | Closed | NIST 800-53 compliance controls (Sally's seven): `dr-compliance-controls.yaml` (Layer 5.16) deploys evidence S3 bucket (Object Lock GOVERNANCE 7yr) + evidence-package generator Lambda (wired into pipeline at every terminal state) + two-person approval Lambda (gates SendTaskSuccess on two distinct IAM principals + break-glass mode) + AWS Signer profile + Lambda code-signing config (infrastructure ready) + SSM Session Manager S3-logged session-recording bucket + custom session preferences SSM document + drill-cadence check Lambda (weekly EventBridge, alarm > 90d). Operator guide: `DR_COMPLIANCE_CONTROLS_GUIDE.md`. Auditor's killer question -- *"show me the last successful end-to-end failover with measured RTO and approval chain"* -- now answered with `s3://aura-compliance-evidence-{account}-prod/<quarter>/<execution>/manifest.json`. |
| DR-9 (#152) | Closed | Cross-region drift detection + observability: `dr-monitoring.yaml` (Layer 5.14) deploys SNS topic, weekly drift-detection Lambda, cross-region CloudWatch dashboard |

**DR follow-ups (tracked separately, not blocking the umbrella close):**
- IAM policy split for DR-8 Control 2 (release-manager vs on-call roles)
- S3-package migration for the ~6 inline-code failover Lambdas to actually use the DR-8 Control 4 Signer profile
- `aws:RequestedRegion` conditions on failover Lambda assume-role policies (DR-8 Control 5)
- One-time SSM Session Manager default-document console selection
- `SECURITY.md` SaaS DR scope-statement update reflecting the now-audit-defensible posture
- Hourly Neptune backup selection (currently daily; closes the Tier 2 RPO 1h gap that's documented in `NEPTUNE_FAILOVER_RUNBOOK.md`)
- Pre-staged secondary-region service foundation templates for Neptune + OpenSearch (subnet groups + security groups; shaves ~10 min off RTO per the runbooks)

### Buildspec Line-Cap Remediation (Umbrella #131 -- COMPLETE, all 4 sub-issues + 5 follow-ups closed)

| Sub-Issue | Status | Outcome |
|-----------|--------|---------|
| #131 (umbrella) | Closed | 600-line cap rule replaced with runtime-budget rule in `deploy/buildspecs/CLAUDE.md` (cold-start `TimeoutInMinutes` is the actual constraint, not line count). New rule: parent → sub-layer CodeBuild nesting forbidden; only `bootstrap → parent` 1-level chain allowed. Sub-layer indirection (when genuinely required) goes through Step Functions, following the `codebuild-serverless-symbol-resolver.yaml` model. |
| #132 (application, 1,049 lines) | Closed | `TimeoutInMinutes: 20 → 480` on `codebuild-application.yaml`. Buildspec retained at 1,049 lines (within new runtime-budget rule). 4 empty scaffold buildspecs deleted. |
| #133 (serverless, 903 lines) | Closed | `TimeoutInMinutes: 45 → 480` on `codebuild-serverless.yaml`. Buildspec retained at 903 lines. 3 empty scaffolds + 1 orphan deleted (orphan was duplicate work the parent already runs at lines 723-748). |
| #134 (sandbox, 685 lines) | Closed | `TimeoutInMinutes: 45 → 480` on `codebuild-sandbox.yaml`. Buildspec retained at 685 lines. 3 empty scaffolds deleted. |
| #135 (observability, 615 lines) | Closed | `TimeoutInMinutes: 20 → 480` on `codebuild-observability.yaml`. Buildspec retained at 615 lines. No scaffolds existed for this layer. |
| #157 (orphan sub-layer wiring) | Closed | Step Functions invocation added for `aura-application-identity-deploy-{env}` (LOUD-FAIL: IdP is on the customer auth path) and `aura-serverless-documentation-deploy-{env}` (non-blocking, ADR-056). Retry blocks added to all three sub-layer states (incl. backfill on symbol-resolver). Pass-state observability now emits structured `{subLayer, status, executionArn, cause}` instead of static text. Reviewed by Tara + Macy in parallel; loud-fail vs non-blocking split per Macy's review. |
| #158 (HTML marketing artifacts) | Closed | `cicd-pipeline-deployment-automation.html` + `infrastructure-deployment-architecture.html` surgically updated: deleted-buildspec rows removed, `symbol-resolver` row added, "600 lines" callout replaced with the runtime-budget rule + Critical Rule 5, count claims refreshed (24→25 CodeBuild, 38→28 buildspecs, 168→170 CFN templates, 20→25 projects). Both files still parse via Python `html.parser`. |
| #159 (SYSTEM_ARCHITECTURE.md ASCII diagrams) | Closed | Three stale labels in the "Hybrid Deployment Architecture" diagram updated with width-preserving replacements (84-char width preserved, box-drawing pipes still column-aligned): "Dev Environment (ECS Fargate) - NOT YET DEPLOYED" → "Deployed (Layer 6)"; "[NOT YET DEPLOYED]" → "[Deployed -- Layer 7]"; "Future: EKS Cluster" → "EKS Cluster (Layer 3 - EC2 Managed Node Groups)". Line 91 "Future: OpenAI GPT-4" deliberately retained as accurate roadmap entry. |
| #160 (ADR-074 stale buildspec reference) | Closed | Audit revealed deeper issue: `iam-palantir-integration.yaml` was an orphan stack -- never deployed by any buildspec. ADR-074's "CI/CD Integration" section updated with status-note callout explaining what was deleted/never-existed; bullet list rewritten as "current (manual)" vs "target (per #161)"; historical decision rationale preserved untouched. Filed #161 as the wiring follow-up. |
| #161 (Palantir IAM wiring) | Closed | Single-line addition to `buildspec-application.yml` Phase 3.12 (Layer 4 parent buildspec) deploying `iam-palantir-integration.yaml`. cfn-lint validation added to pre_build phase. No new CodeBuild project required; no parent → sub-layer nesting introduced. Buildspec line count 1,049 → 1,075 (well within runtime-budget rule). OIDC params left at empty defaults; IRSA wiring deferred until a production Palantir engagement requires it. ADR-074 status-note rewritten to record closure. |

**Buildspec follow-ups (tracked separately, not blocking the umbrella close):**
- Optional: add `aws stepfunctions validate-state-machine-definition` step to the cfn-lint wrapper or pre-commit (Macy's optional add for catching ASL JSON-shape issues earlier). ~5 lines.
- Inline parallelism (`xargs -P` or background jobs) inside parent buildspecs to reduce cold-start runtime. Tara's optional optimization; defer until measurements show the timeout-extended buildspecs are slow enough to need it.
- Promoting the cold-start path to Step Functions Standard for true parallel orchestration with retry. Defer until inline parallelism proves insufficient.
- Bootstrap drill on a fresh DEV account to confirm `idp-infrastructure` + `cloud-discovery` + `calibration-pipeline` + `iam-palantir-integration` land end-to-end without manual intervention. Recommended next time a DEV account is rebuilt.
- ASCII-diagram refresh of the remaining "Hybrid Deployment Architecture" / "Sandbox Infrastructure" boxes in `SYSTEM_ARCHITECTURE.md` (current diagrams are now factually accurate post-#159 but could benefit from a structural redraw if the diagram-as-doc surface is taken seriously).
- Real OIDC param wiring on `iam-palantir-integration.yaml` (`EKSOIDCProviderArn`, `EKSOIDCIssuer`) when a production Palantir engagement requires Cognito-federated AIP access.

### May 9, 2026 Documentation & Security Pass

| Track | Status | Outcome |
|-------|--------|---------|
| Marcus thorough doc refresh | Complete (commit `c8a2cee`) | 10 files updated across `README.md`, `SECURITY.md`, `DOCUMENTATION_INDEX.md`, `SYSTEM_ARCHITECTURE.md`, `BUILDSPEC_COMPLEXITY_ANALYSIS.md`, `DEPLOYMENT_GUIDE.md`, `RESOURCE_DEPLOYMENT_AUDIT.md`, `DEPENDENCY_RISK_REGISTER.md`, `disaster-recovery.md`, `frontend/CLAUDE.md`. ADR count `89 → 91`; SECURITY.md SaaS DR scope-statement rewritten to reflect now-audit-defensible posture (closes the DR-8 follow-up); `--legacy-peer-deps` workaround section now explicitly cites #142 trigger-gating. Marcus reviewed but did NOT touch: `PROJECT_STATUS.md` (already canonical), all `docs/runbooks/*` (already accurate), all support/architecture sub-files lacking DR/buildspec content, `CHANGELOG.md` (auto-generated). |
| CodeQL alert #271 (Critical code injection) | Closed (commit `53adf3d`) | `aura-ci-autofix.yml` "Push fix to feature branch" step env-var'd 3 interpolations (`TARGET_BRANCH`, `FIX_TYPE`, `WORKFLOW_RUN_URL`); consumer side now matches the input-side hardening already in the `target` step. Alert auto-closed by CodeQL re-scan with `state: fixed`. |
| CodeQL alert #272 (Medium unpinned action) | Closed (commit `53adf3d`) | `aws-actions/configure-aws-credentials@v4` pinned to commit SHA `7474bc4690e29a8392af63c5b98e7449536d5c3a` (v4.3.1) following the existing repo pattern (every other action was already SHA-pinned). |
| #142 eslint-plugin-react swap | Deferred (issue stays open as tracking artifact) | Trigger-condition assessment posted: trigger 1 (6mo silence from issue filing) earliest fires ~2026-11-08; `eslint-plugin-react` still at 7.37.5 (peer caps `^9.7`); no CI escape from `--legacy-peer-deps`. Per the issue's own logic: "track, not do" until triggers fire. Forward-looking note recorded that swap scope is smaller than the issue body anticipated (`grep -rln "eslint-disable.*react/" frontend/src` returns zero hits). #138's recurring dependency audit is the detection mechanism for trigger 1. |

**Documentation & security follow-ups (tracked separately):**
- HTML marketing artifacts in `docs/` would benefit from auto-regeneration from a markdown source-of-truth if a build process is ever introduced; current refresh was surgical-edit only (commit `9cb9044`).
- ASCII diagram structural refresh in `SYSTEM_ARCHITECTURE.md` (also listed under buildspec follow-ups above).
- Pre-existing modified files in working tree noted by Marcus and left untouched: `elasticache.yaml`, `govcloud.json`, `TITANS_MIRAS_ANALYSIS.md`, `trustCenterExport.js`, `contracts.py`, untracked `robots.txt` -- none related to this session's work.

### May 11-12, 2026 GTM-Readiness Remediation Waves 6-14 (Umbrella #163 -- CLOSED)

| Wave | Commit | Theme | Outcome |
|------|--------|-------|---------|
| 6 | `bfec189` | Defense-in-depth + scanner detail + CI hygiene | `AutonomyPolicy.IMMUTABLE_GUARDRAILS` makes `credential_modification` + `production_deployment` unbypassable under any preset; `assert_signer_safe_for_environment()` refuses MockKMSSigner in prod-tier `AURA_ENV`; ScanDetailPage live-wired (no more `MOCK_SCAN_DETAIL`); Service Catalog products `AllowedPattern` rejects public ECR; 18 new commit_msg_hook tests; `__test__ = False` on TestConnectionModel + TestOutcome; `datetime.utcnow()` → `datetime.now(timezone.utc)` sweep; all workflows pinned to `ubuntu-24.04`; `code-quality.yml` permissions `contents: write` → `read`; log retention raised 7d → 30d on opensearch + monitoring. |
| 7 | `37c814e` | Doc accuracy + auth bundle split + test isolation | DOCUMENTATION_INDEX 3 broken `../PROJECT_STATUS.md` paths fixed; root CLAUDE.md stack claim corrected (React 19 / JavaScript / Vite, not React 18 / TypeScript / Next.js 14); `codebuild-bootstrap.yaml` description: "1 bootstrap + 24 downstream = 25 total"; `App.jsx` auth code-split (`ProtectedRoute` imported from module path not barrel); Provenance/Integrity singleton tests monkeypatch HMAC env vars. |
| 8 | `8197263` | Top-level dashboard widgets live-wired behind stub backend | New `src/api/dashboard_metrics_endpoints.py` with 5 endpoints (MTTR, asset-criticality, compliance-drift, insider-risk, health); new `frontend/src/services/dashboardMetricsApi.js`; 4 widgets wired (MTTR/AssetCriticality/ComplianceDrift/InsiderRisk); `DemoDataBadge` removed from those four; 6 new endpoint tests in `tests/api/test_dashboard_metrics_endpoints.py`. **Closes the audit's "DO-NOT-SHIP: 4 top-level widgets import from MOCK" finding.** |
| 9 | `996b2d8` | Customer-visible TODOs + HealthCheckModal + vendor-mermaid + release-please tag | 8 silent click-handler TODOs in CommandPalette/CKGEConsole/KnowledgeGraph replaced with toast feedback; `HealthCheckModal` wired to new `GET /api/v1/system-health` stub endpoint; new `src/api/system_health_endpoints.py` + `frontend/src/services/systemHealthApi.js` + 2 endpoint tests; vendor-mermaid 2.99 MB chunk no longer in `modulepreload`; `v1.7.0`/`v1.7`/`v1` git tags created at PR #30 merge to unblock release-please. |
| 10 | `7670397` | Buildspec branching refactor | 27 inline create/update branches replaced with canonical `aws cloudformation deploy --no-fail-on-empty-changeset`. `buildspec-application.yml`: 5 sites; `buildspec-observability.yml`: 9; `buildspec-serverless.yml`: 13. 2,593 → 1,953 lines (-640 LOC). |
| 11 | `b885e5c` | Frontend lint sweep | 281 problems → 93; 20 errors → 0; 162 auto-fixed; 12 try/catch wrappers removed; 7 useless assignments; 1 case-declaration; 5 console; 1 hook-deps. |
| 12 | `970371a`, `f14f20d` | ADR-092 Phase 2 code (CFN deploy-role wildcard scoping) | New ADR-092 **Accepted (v2)** with deploy phases **Deferred (Cost Gate)**. Three-agent review (Tara/Sally/Jake) drove design. 8-statement scoped structure on `CloudFormationServiceRole`: KMS bootstrap/operate, CloudWatch namespace, Logs CreateLogDelivery, read-only, Self-Broadening Deny (T1098.001), PassRole `PassedToService` constraint (T1078.004), Project-tag Deny, safety Deny. `UseLegacyDeployRole` parameter for blue/green rollback. `iam.yaml`: 569 → 1,287 lines initially. |
| 13 | `ce60ff7`, `d067836`, `f14f20d` | Offline static-scan tooling (Phase 1 substitute) | New `scripts/adr_092_static_action_scan.py` parses all 187 CFN templates (including archive), cross-references actions with the scoped policy, reports coverage gaps. 37 unit tests in `tests/scripts/test_adr_092_static_action_scan.py`. Surfaced and applied 3 real EC2 SG gap fixes; rejected 3 aspirational DynamoDB GSI typos. Follow-up added 16 services (Lambda, SNS, SQS, Events, Scheduler, StepFunctions, ApiGateway, Cognito, Route53, CodeBuild, Config, Budgets, CloudFront, ACM, Backup, ServiceCatalog): 524 → 336 uncovered actions. Surfaced AWS 6,144-char managed-policy size limit issue. |
| 14 | `ee3c0fd` | Managed-policy size resolution | 2 oversized policies split into 5 by lifecycle blast-radius tier per Tara's review: Data / Compute / EC2OperateAndStorage / EventsAndIntegration / PlatformManagement. All under 6,144 chars with headroom. Coverage byte-identical before/after split (Sally verified). |

**Cost-Gate Constraint (NEW context as of May 12, 2026):** The platform is self-funded; live-AWS validation is paused indefinitely to control cost. This means ADR-092 deploy phases 1, 3, 3.5, 4, 5, and 6 are **Deferred (Cost Gate)**. All Phase 2 code work is complete and reviewable; deploys will resume when budget allows. The offline static-scan substitute (`scripts/adr_092_static_action_scan.py`) is the Phase 1 stand-in. Documentation must continue to reflect this honestly -- not "100% Deployed" claims where deploy has not happened.

**Open Issues Post-#163 Closure:**
- **#180 (OPEN, blocked external):** Ops -- SNS subscribers + GitHub Actions secrets + 68 deaf CloudWatch alarms. Blocked on external endpoint provisioning (PagerDuty, Slack) which is out-of-band.
- **#181 (OPEN, multi-week pure-code):** `vulnerability_scanner/parsing` tree-sitter real implementation. **Phase 1 (AST surface) and Phase 2 (symbol extraction) BOTH structurally complete across all 8 Phase-1 languages (May 12, 2026).** Phase 1: 155 tests. Phase 2 Python: 55 tests. Phase 2 JavaScript: 46 tests. Phase 2 TypeScript (subclasses JS): 38 tests. Phase 2 Go (two-pass walker for receiver-bound methods): 34 tests. Phase 2 Java (class/interface/enum/record → CLASS): 37 tests. Phase 2 Rust (two-pass walker: struct/enum/trait → CLASS; impl resolution): 36 tests. Phase 2 C (return-type reconstruction across pointer_declarator wrappers; struct/union/enum + typedef-wrapped aggregates → CLASS; prototype-skipping): 34 tests. Phase 2 C++ follow-on: `CppSymbolExtractor` (two-pass walker: pass 1 emits class_specifier/struct/union/enum + namespace_definition + template_declaration as CLASS and their inline methods; pass 2 resolves out-of-line ``ReturnType Class::method() {}`` definitions against the class lookup with deduplication when an inline prototype was already emitted; constructors/destructors emit with `return_type=None`; nested-namespace and multi-level `qualified_identifier` scope resolution for ``foo::Bar::method``; reference / pointer return-type reconstruction so ``int& f()`` -> ``"int &"``), 41 tests. Phase 3 (dataflow + taint) is the only remaining work on #181.
- **#182 (substantially closed):** Tech-debt tracker. Buildspec/lint/IAM code-merge items closed; ADR-092 deploy phases Deferred (Cost Gate); "Coming Soon" panels won't-fix. Issue stays open as audit trail; could be closed.

### Integrations & Deployment

| Component | Status | Details |
|-----------|--------|---------|
| Cloud Abstraction Layer | Complete | Multi-cloud AWS/Azure support, 46 tests (ADR-004) |
| Palantir AIP Integration | Complete | Ontology Bridge, event publisher, 197 tests (ADR-074). Wave 1 wired the Palantir router into the FastAPI app at startup (commit 5fed82b). |
| Self-Hosted Deployment | Complete | Podman, Windows/Linux/macOS (ADR-049) |
| Air-Gapped & Edge | Complete | Offline model bundles, edge runtime, 200 tests (ADR-078) |
| Developer Tools | Complete | VSCode, PyCharm, JupyterLab, Dataiku connectors (ADR-048) |
| Native Vulnerability Scanner | Infrastructure Deployed; Parsing Phase 1 + Phase 2 (Python) Complete | GraphRAG-enhanced LLM analysis (ADR-084); ADVANCED-tier (Mythos-class) scaffolding inert by default (capability router, exploit-generation contract, separate ADVANCED prompts, per-scan cost tracker, sandbox verifier, 48 mock-tested paths); live-model validation tracked in issue #115. Wave 3 added real boto3 CloudWatch metric emitter (commit 17d9827). Wave 4 wired `ActiveScansWidget` + `FindingsBySeverityWidget` to the live `vulnScannerApi` and removed the silent-mock fallback in `useDashboardData.js` (commit 8df9cc3). Wave 6 live-wired `ScanDetailPage` (no more `MOCK_SCAN_DETAIL` import) and tightened Service Catalog products to private-ECR-only via `AllowedPattern` (commit bfec189). Wave 8 wired 4 top-level dashboard widgets (MTTR, AssetCriticality, ComplianceDrift, InsiderRisk) to a new stub backend at `src/api/dashboard_metrics_endpoints.py` (commit 8197263). **Issue #181 Phase 1 (May 12, 2026):** real tree-sitter AST surface landed under `src/services/vulnerability_scanner/parsing/` (`languages.py` extension+shebang+content-sniff detection, `grammar_loader.py` lazy thread-safe per-language grammar cache, `parser_pool.py` bounded-LRU thread-safe parser pool, `ast.py` `parse_file` / `parse_source` with timeout + file-size guards); 8 canonical fixtures and 155 new tests covering Python/JS/TS/Go/Java/Rust/C/C++; new grammar pip deps `tree-sitter-{typescript,go,java,rust,c,cpp}` added to `requirements.txt` and `requirements-agents.txt`. **Issue #181 Phase 2 COMPLETE across all 8 Phase-1 languages (May 12, 2026):** `parsing/symbols.py` with `SymbolExtractor` protocol + module-level dispatcher + eight extractors (Python, JavaScript, TypeScript [subclasses JS], Go, Java, Rust, C, C++). Three of the eight use two-pass walkers for receiver / impl / out-of-line method resolution (Go, Rust, C++). Cumulative: 321 new symbol-extraction tests. **Phase 3 pre-work (PR 3.0) shipped after a three-agent design review (Sally cybersecurity, Jake code review, Kelly test architect):** shared helpers extracted from `symbols.py` (now 4,926 LOC) into `parsing/_parsing_helpers.py`; `DataFlowChain` extended with `confidence` + `cwe_ids`; `DataFlowNode` extended with `start_byte` + `end_byte`; `ParsingConfig.enable_dataflow_analysis` default flipped to `False` (production explicit opt-in retained). **Phase 3.1 (Python taint analyzer) shipped:** `parsing/dataflow.py` (~1500 LOC) with `DataFlowAnalyzer` Protocol + dispatcher + `TaintTaxonomy` dataclass + `PythonTaintAnalyzer` (intra-procedural + same-module return-value propagation). Hard-coded Python taxonomy of ~110 identifiers grouped by CWE. Two-pass analyzer with confidence scoring (0.95 direct / 0.75 cross-fn / 0.65 partial-sanitized). Ships as PREVIEW (`enable_dataflow_analysis=False` default). 42 new tests. **Phase 3.2 (LLM analyzer integration) shipped:** `prompt_builder.build_analysis_prompt` enriched to surface `DataFlowChain.confidence`, `cwe_ids`, `taint_label`, and `hop_count` in the DATA FLOW ANALYSIS prompt section. 14 new prompt-builder tests. **Phase 3.3 (JavaScript taint analyzer) shipped:** 38 new tests. **Phase 3.4-3.9 (TypeScript / Go / Java / Rust / C / C++ taint analyzers) ALL SHIPPED (May 12, 2026) via a parallel-agent strategy:** six general-purpose agents launched simultaneously on isolated git worktrees, each implementing one language analyzer + tests; five completed cleanly (TS / Java / Rust / C / C++), one (Go) hit an API error and was finished manually using the now-established pattern. After all agents returned, their worktree branches were cherry-picked sequentially onto main, resolving the predictable conflicts at `__all__` / `_TAXONOMIES` / `_bootstrap_registry`. Each language ships with its own `<LANG>_TAXONOMY` and `<Lang>TaintAnalyzer`: TS subclasses `JavaScriptTaintAnalyzer` and adds TS type-assertion unwrapping (`as_expression`, `satisfies_expression`, `type_assertion`, `non_null_expression`); Go is a standalone two-pass walker (handler param ``r *http.Request`` plus gin / echo context sources, ``database/sql`` / ``os/exec`` / ``net/http`` / ``html/template`` sinks across CWE-89/78/94/22/79/918/601/117); Java covers Servlet / Spring / JNDI sources, JDBC / Runtime / ProcessBuilder / ScriptEngine / ObjectInputStream / DocumentBuilder sinks across CWE-89/78/94/502/22/79/918/601/611/117 with chained-receiver collapse for `new T(...).foo` patterns; Rust seeds typed-parameter taint for `web::Query<T>` / `Json<T>` etc. and handles macro_invocation for log macros; C is single-pass with argv-subscript-as-source plus snprintf-as-out-parameter-sanitizer; C++ extends C with class methods, namespaces, templates, out-of-line method definitions via qualified_identifier, and `operator<<` stream sink detection. Cumulative across Phase 3.4-3.9: 33 TS + 23 Go + 36 Java + 37 Rust + 35 C + 44 C++ = **208 new dataflow tests**. **Phase 3.10 (cross-file inter-procedural taint, in-memory v1) shipped (May 12, 2026):** new `FunctionSummary` Protocol + `CrossFileTaintContext` dataclass in `dataflow.py` index per-function summaries by `CodeUnit.unit_id` (Phase 2's SHA-256 stable IDs) with secondary indexes by short and qualified callable name; `DataFlowAnalyzer.analyze` Protocol signature extended with `cross_file_context: Optional[CrossFileTaintContext]`; `extract_dataflows` dispatcher threads the context through with a `TypeError` fallback so the 7 non-Python analyzers keep working unchanged. PythonTaintAnalyzer is the first analyzer wired to BOTH populate (record each pass-1 summary into the context) AND consume (cross-file source and sink resolution in `_expression_taint` and `_handle_call`, with a file-boundary check so intra-file lookups never double-emit). New `_CONFIDENCE_CROSS_FILE = 0.50` constant -- lower than same-module cross-fn (0.75) because the resolver has no import awareness and can mis-route across name collisions. Recommended two-pass caller workflow (pass 1 populates, pass 2 emits) is the published contract. 18 new tests. **Phase 3.11 (cross-file wiring for the remaining 7 analyzers) shipped (May 13, 2026):** JavaScript, TypeScript (via JS subclass), Go, Java, Rust, C, and C++ analyzers now all accept `cross_file_context` in their `analyze()` signature, populate per-function summaries in pass 1, and consume the context in `_handle_call` (cross-file sink) and `_expression_taint` (cross-file source) with file-boundary verification and `_CONFIDENCE_CROSS_FILE` (0.50) confidence floor downgraded via `_emit_chain`. C++ uses `::` as the qualifier separator for short-name fallback (vs `.` in the other languages); the dispatcher's `TypeError` fallback is no longer reached on any registered analyzer. 18 new tests (4 JS, 2 TS, 3 Go, 3 Java, 2 Rust, 2 C, 2 C++). **Phase 3.12 (scan-wide assembly bridge) shipped (May 13, 2026):** new `parsing/scan_assembly.py` module exposes `ParsedFile`, `ScanParseBundle`, and `assemble_dataflow_for_scan(files, scan_id, config)`. The assembler orchestrates the full parse-symbol-dataflow pipeline (two-pass cross-file workflow internally) and returns chains indexed by SINK `code_unit_id` -- the exact shape `LLMVulnerabilityAnalyzer.analyze_candidates` expects for `candidate.code_unit_id` lookups. Cross-file chains (source in file A, sink in file B) are indexed under file B. Single-file parse / extract failures are logged and skipped, not raised. Bundle's `cross_file_context` field is exposed so a follow-on Neptune-backed resolver can swap the in-memory implementation without changing call sites. 15 new tests. **ADR-093 accepted (v2) on May 13, 2026** after a three-agent design review (Tara/Sally/Jake). **ADR-093 Phase 1 (Test substrate) shipped (May 13, 2026):** Phase 1.1 added the `TaintContext` Protocol in `dataflow.py` next to `FunctionSummary`, renamed the existing `CrossFileTaintContext` dataclass to `InMemoryTaintContext`, kept `CrossFileTaintContext` as a one-release back-compat type alias, widened all 17 `Optional["CrossFileTaintContext"]` type hints across the 8 language analyzers + dispatcher to `Optional["TaintContext"]`, and updated `ScanParseBundle.cross_file_context` to the polymorphic `Optional[TaintContext]` annotation. Phase 1.2 added the 12-fixture equivalence harness (`test_taint_resolver_equivalence.py`) parametrized over `backend ∈ {in_memory, neptune_tinker}` — 12 in-memory runs pass; 12 `neptune_tinker` placeholders skip pending Phase 2; F10 tenant-isolation test runs standalone. Conftest with session-scoped `gremlin_server` + function-scoped `tinker_graph` fixtures sketched (Phase 2 will fill). **ADR-093 Phase 3 (Writer + end-of-scan flush) shipped (May 13, 2026):** Phase 3.1 added `SignatureSigner` Protocol + `DeterministicSigner`/`DeterministicVerifier` test pair + `WriteFence` Protocol + `InMemoryWriteFence` (production wires KMS + DynamoDB in Phase 4). Phase 3.2 added `NeptuneTaintRepository.persist_summaries()` — content-hash + transport-bound signature (Sally C-5: scan_id, commit_sha, session_nonce) + signed `addV` for each `VulnCodeUnit` vertex + `addE` for each `SINKS_PARAM` edge, all via bytecode through `TenantScopedGremlinClient.submit_write` (rate-limited). Mid-batch failure raises `NeptuneQueryError` (caller must not set write-fence). Phase 3.3 extended `TaintContext` Protocol with `flush()` method (no-op default; `NeptuneBackedTaintContext.flush()` writes the cache + marks write-fence). `InMemoryTaintContext` now retains `units_by_id` so flush can read `source_hash`. `TenantScopedGremlinClient` extended to accept `addV` entries requiring `.property('tenant_id', T)` predicate (read path uses `.has(...)`; write path uses `.property(...)`). Factory wires write-side deps (signer_factory + signer_arn_for_tenant + write_fence + session_nonce_factory). `assemble_dataflow_for_scan` accepts `commit_sha` kwarg and calls `ctx.flush()` at end-of-scan (failures logged but never fail the scan). Phase 3.4 **acceptance gate passes**: 5-test `test_rescan_equivalence.py` proves scan N writes summaries → scan N+1 reads them via preload → produces chains byte-equivalent to a fresh in-memory scan, exercised via an in-process `FakeGremlin` emulator that understands the exact bytecode shapes Phase 3 emits (`addV`/`addE`/`V().has().value_map`). The fake is the cost-gate substitute for the full TinkerGraph fixture (Phase 4). **1390 scanner tests total (was 1376; +14 Phase-3).** Phase 4 (kill-switch + observability + KMS/DynamoDB production wiring + TinkerGraph fixture) is now unblocked. **ADR-093 Phase 2 (Resolver read path) shipped (May 13, 2026):** Phase 2.1 added `TenantScopedGremlinClient` (`parsing/tenant_scoped_gremlin_client.py`) — bytecode-only Gremlin wrapper that rejects string-mode submissions, requires `.has('tenant_id', T)` within the first 6 steps of every traversal (including `.E()` entries), enforces per-tenant 600-writes/min quota (Sally T1499.004 defense); new exception types `StringModeRejectedError` and `WriteRateExceededError` added to scanner exceptions; 18 unit tests covering all 7 Sally-required hardening cases + positive paths. Phase 2.2 added `NeptuneTaintRepository` + `NeptuneBackedTaintContext` (`parsing/neptune_taint_repository.py`) — read-only repository with paginated preload + lazy single-callable lookup, `SignatureVerifier` and `RevocationOracle` Protocol injection points (test verifiers `AlwaysTrust`/`NeverTrust`/`NoRevocation` shipped; production wires KMS + DynamoDB in Phase 4), `SCHEMA_VERSION=1` module constant per Jake's review (integer compare on read; no in-place migrations), schema-mismatch + signature-failure + revocation-hit + malformed-vertex all degrade gracefully to "drop summary; log; treat as cache miss"; `NeptuneBackedTaintContext` satisfies the `TaintContext` Protocol, composes `InMemoryTaintContext` for the preload cache (per Jake: no parallel cache); 16 unit tests + 2 Phase-3-deferred skips. Phase 2.3 added `build_taint_context` factory (`parsing/taint_context_factory.py`) with whole-scan fail-safe (Jake's option B) — single seam at `scan_assembly.py:165`; degrades to in-memory on any of {flag off, flag read fails, tenant_id missing, repo factory missing, repo factory raises, preload raises}; emits `taint.resolver.degraded_to_memory.<reason>` metric exactly once per degrade; metric-emitter resilience (degrade still happens if emitter raises); 9 unit tests. `assemble_dataflow_for_scan` now accepts `tenant_id` + `factory_deps` kwargs (defaults preserve backward compatibility -- existing callers unaffected). **1376 scanner tests total (was 1333; +43 Phase-2 unit tests).** Phase 3 (writer + GraphBuildStage) is now unblocked. |
| Deterministic Verification Envelope | Complete | All 5 phases implemented: N-of-M consensus, MC/DC coverage gate, Z3 formal verification, DAL-A/DAL-B profiles, DO-178C lifecycle data, DVE pipeline orchestrator with DynamoDB/S3/CloudWatch sinks, 191 tests (ADR-085) |
| Continuous Model Assurance | Complete | All 3 phases implemented: CGE regression-floor, Adapter Registry, 6-axis MA1-MA6 domain, Scout Agent, Model Provenance Service (Sigstore), Frozen Reference Oracle (400 cases, 10% rotation cap), Step Functions pipeline, zero-egress sandbox, anti-Goodhart controls, HuggingFace + Internal SWE-RL sources, rollback mechanism, CloudTrail audit (13 events x 6 NIST controls), GovCloud FIPS validator, 567 new tests (ADR-088) |
| Long-Horizon Security Campaigns | Phase 1 In-Process | Campaign manager service composing existing primitives into multi-hour autonomous workloads (compliance hardening, vulnerability remediation, cross-repo chain analysis, threat hunting, Mythos exploit refinement, self-play training); orchestrator + operation ledger with idempotency contract + per-token cost tracker with 5% graceful-stop reservation + tenant cost rollup + drift detector + checkpoint store + state store with optimistic concurrency + Phase abstraction with harness-driven loop control + ComplianceHardeningWorker stub; Step Functions Standard chosen as production substrate (in-process now, same Protocols); 42 tests (ADR-089) |
| SWE-Bench Pro Benchmark Adapter | Phase 1 | Typed contracts, runner with bounded concurrency + per-task timeout, mock adapters, real Aura+Bedrock adapter with cost-cap halt, unofficial heuristic-scoring mode (file F1 + hunk overlap + token Jaccard), enhanced adapter scaffolding (GraphRAG retrieval + Reviewer pass), CLI at scripts/benchmarks/run_swe_bench_pro.py; defaults updated to current-gen Claude (Sonnet 4.6 / Haiku 4.5); 57 tests |

### UI & Dashboard

| Component | Status | Details |
|-----------|--------|---------|
| Customizable Dashboards | Complete | 25 widgets, drag-drop editor, role defaults, 83 tests (ADR-064) |
| Customer Onboarding | Complete | Welcome modal, checklist, tour, tooltips (ADR-047) |
| Repository Onboarding | Complete | 5-step wizard, OAuth GitHub/GitLab (ADR-043) |
| Guardrail Configuration UI | Complete | Compliance profiles, validation, 128 tests (ADR-069) |
| Hyperscale Agent Orchestration | Phase 1 | UI gating, execution tier selection, security gate validation, ~500 lines UI (ADR-087). Wave 4 replaced the hardcoded-zero telemetry placeholders with a new `ModeTelemetryCollector` backed by K8s + SQS lookups (commit a48f3e6). |
| Model Assurance Queue (HITL) | Complete | React `/model-assurance` page, 6-axis radar, integrity badge, edge-case spotlight, cost analysis, 15 tests (ADR-088) |

---

## Compliance Posture

| Framework | Status |
|-----------|--------|
| NIST 800-53 | Technical controls implemented |
| SOX | Controls implemented |
| GovCloud Ready | 100% (all deployed services compatible) |
| CMMC Level 2 | Infrastructure complete, organizational controls pending |
| FedRAMP High | Authorization path available |

---

## Roadmap

| Phase | Timeline | Milestone |
|-------|----------|-----------|
| DEV Environment | Complete | All 9 layers deployed to AWS Commercial Cloud |
| QA Environment | Q1 2026 | Mirror dev configuration |
| PROD Environment | Q2-Q3 2026 | GovCloud deployment with STIG/FIPS hardening |
| Public Launch | Q3-Q4 2026 | GA release |

---

## Architecture Decision Records

93 ADRs document rationale for significant design choices. See [docs/architecture-decisions/](architecture-decisions/) for the full list. Key ADRs:

- **ADR-004**: Cloud Abstraction Layer (Multi-cloud)
- **ADR-024**: Titan Neural Memory Architecture
- **ADR-032**: Configurable HITL Autonomy Framework
- **ADR-034**: Context Engineering Framework
- **ADR-049**: Self-Hosted Deployment (Podman) and Mythos Capability Tier
- **ADR-051**: Recursive Context & Embedding Prediction
- **ADR-063**: Constitutional AI Integration
- **ADR-065**: Semantic Guardrails Engine
- **ADR-066**: Agent Capability Governance
- **ADR-078**: Air-Gapped & Edge Deployment
- **ADR-083**: Runtime Agent Security Platform
- **ADR-084**: Native Vulnerability Scanning Engine
- **ADR-085**: Deterministic Verification Envelope (All 5 Phases Implemented)
- **ADR-086**: Agentic Identity Lifecycle Controls (Deployed)
- **ADR-087**: Hyperscale Agent Orchestration (Phase 1 Deployed)
- **ADR-088**: Continuous Model Assurance (All 3 Phases Implemented)
- **ADR-089**: Long-Horizon Security Campaigns (Proposed; Phase 1 in-process implementation)
- **ADR-090**: GraphRAG Ingestion Edge Completeness
- **ADR-091**: Cognito Cross-Region DR
- **ADR-092**: CloudFormation Deploy-Role Wildcard Scoping (Accepted v2; Phase 2 code merged; deploy phases Deferred (Cost Gate))
