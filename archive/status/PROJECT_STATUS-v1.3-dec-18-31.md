# Project Aura: Development Status Archive

## December 18-31, 2025 Development History

**Archive Date:** January 6, 2026
**Archived From:** docs/PROJECT_STATUS.md

> This file contains archived development notes for December 18-31, 2025. For current status, see [docs/PROJECT_STATUS.md](../../docs/PROJECT_STATUS.md).

---

## December 2025 Development

### ADR-048 Developer Tools & Data Platform Connectors Complete (Dec 31, 2025)

Implemented comprehensive developer tools and data platform integration connectors across 5 phases (~7,700 lines of code).

**Phase 0: Abstraction Layer & Security Services**

| Component | Description | Status |
|-----------|-------------|--------|
| Base Integration Adapter | Abstract base class with retry logic, error hierarchy | Complete |
| Secrets Pre-Scan Filter | 45+ secret patterns for all Integration Hub providers | Complete |
| Export Authorization Service | Row-level security with RBAC | Complete |

**Phase 1: VSCode Extension Enhancements**

| Component | Description | Status |
|-----------|-------------|--------|
| GraphContext Provider | Neptune visualization integration | Complete |
| Diagnostics Provider | Enhanced severity mapping for findings | Complete |
| API Client | Extended with findings and graph endpoints | Complete |

**Phase 2: PyCharm/IntelliJ Plugin**

| Component | Description | Status |
|-----------|-------------|--------|
| Kotlin Plugin | IntelliJ Platform SDK integration | Complete |
| AuraApiClient | Backend communication layer | Complete |
| FindingsService | Vulnerability annotation provider | Complete |
| GraphContextService | Code relationship visualization | Complete |
| ScanFileAction | On-demand security scan trigger | Complete |

**Phase 3: JupyterLab Extension**

| Component | Description | Status |
|-----------|-------------|--------|
| CellAnnotator | Inline finding markers for notebooks | Complete |
| FindingsPanel | Vulnerability findings widget | Complete |
| GraphContextPanel | Code context visualization widget | Complete |
| REST Client | Aura API integration | Complete |

**Phase 4: Dataiku DSS Connector**

| Component | Description | Status |
|-----------|-------------|--------|
| AuraFindingsConnector | Vulnerability data export to DSS | Complete |
| AuraCodePatternsConnector | GraphRAG patterns export | Complete |
| AuraTrendAnalysis | Metrics and trend utilities | Complete |
| scan-repository Recipe | Custom DSS recipe for scanning | Complete |
| trend-analysis Recipe | Custom DSS recipe for analytics | Complete |

**Phase 5: Fivetran Connector + Generic Export API**

| Component | Description | Status |
|-----------|-------------|--------|
| Fivetran Connector | SDK implementation with test/schema/sync | Complete |
| Generic Export API | 5 entity types with pagination | Complete |
| Secrets Redaction | SecretsPrescanFilter integration | Complete |
| Authorization | ExportAuthorizationService for row-level security | Complete |

**Entity Types Supported:**
- `findings` - Security vulnerability findings
- `code_patterns` - GraphRAG code patterns
- `repositories` - Repository metadata
- `scan_history` - Scan execution history
- `metrics` - Platform metrics

**Files Added (40 files, ~7,700 lines):**
- `vscode-extension/src/providers/graphContextProvider.ts`
- `pycharm-plugin/` - Complete Kotlin plugin (11 files)
- `jupyter-extension/` - TypeScript extension (8 files)
- `dataiku-connector/` - DSS plugin with recipes (7 files)
- `fivetran-connector/` - Fivetran SDK connector (5 files)
- `src/api/export_endpoints.py` - Generic Export API (~670 lines)
- `tests/test_export_endpoints.py` - 26 tests

---

### ADR-049 Self-Hosted Deployment Strategy (Dec 31, 2025 - Jan 3, 2026)

Comprehensive architecture decision record for enabling Project Aura as a self-hosted application supporting Windows, Linux (Ubuntu, RHEL), and macOS.

**Key Decisions:**

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Container Runtime | Podman (primary) | Avoids Docker Desktop licensing fees ($5-24/user/month for enterprises) |
| LLM Strategy | Hybrid (cloud APIs primary) | GPU costs prohibitive; cloud APIs (Bedrock/Azure OpenAI) via PrivateLink for 95% of deployments |
| Licensing Model | Open-core (Apache 2.0 Community Edition) | Follows GitLab/Mattermost model |
| Database Migration | Neptune to Neo4j, DynamoDB to PostgreSQL | Self-hostable alternatives with existing Cloud Abstraction Layer |
| Security | TLS everywhere (no HTTP internally) | Enterprise security requirements |

**LLM Deployment Tiers:**

| Tier | Use Case | LLM Strategy | GPU Required |
|------|----------|--------------|--------------|
| Tier 1: Cloud-Connected | Most enterprises | AWS Bedrock via PrivateLink | No |
| Tier 2: Multi-Cloud | Cloud-agnostic | Azure OpenAI + Bedrock failover | No |
| Tier 3: Air-Gapped | Defense/classified (<5%) | vLLM + Mistral (on-prem GPU) | Yes |

**Implementation Timeline (33 weeks):**

| Phase | Duration | Scope | Status |
|-------|----------|-------|--------|
| Phase 0 | 2 weeks | Prerequisites (query language decision, NetworkPolicy, license validation) | Complete |
| Phase 1 | 10 weeks | Container platform (Neo4j adapter, Podman Compose, installer) | Backend Complete |
| Phase 1.5 | 3 weeks | Migration toolkit (SaaS to Self-Hosted data migration) | Complete |
| Phase 2 | 6 weeks | Kubernetes/Helm (production deployments) | Complete |
| Phase 3 | 8 weeks | Air-gap support (offline bundles, FIPS 140-2) | Complete |
| Phase 4 | 4 weeks | Native installers (MSI, DEB, RPM, PKG) | Complete |

**Phase 0 Prerequisites (Complete - Dec 31, 2025):**
- DynamoDB schema reference documentation
- Query language strategy (Gremlin vs Cypher)
- Ed25519 license validation design
- Resource baselines for HPA
- Default-deny NetworkPolicy templates
- Feature flag edition mapping

**Phase 1 Backend Implementation (Complete):**

| Component | Description | Lines |
|-----------|-------------|-------|
| `src/abstractions/cloud_provider.py` | Added `SELF_HOSTED` enum value with `is_self_hosted` property | +15 |
| `src/services/providers/self_hosted/__init__.py` | Package exports for all adapters | 45 |
| `src/services/providers/self_hosted/neo4j_graph_adapter.py` | Neo4j Cypher adapter for Neptune replacement | 520 |
| `src/services/providers/self_hosted/opensearch_adapter.py` | Self-managed OpenSearch with KNN | 380 |
| `src/services/providers/self_hosted/local_llm_adapter.py` | OpenAI-compatible API (vLLM, TGI, Ollama) | 450 |
| `src/services/providers/self_hosted/minio_storage_adapter.py` | MinIO S3-compatible storage | 320 |
| `src/services/providers/self_hosted/file_secrets_adapter.py` | Fernet encryption (AES-128-CBC) secrets | 280 |
| `src/services/providers/self_hosted/postgres_document_adapter.py` | PostgreSQL JSONB for DynamoDB replacement | 620 |
| `src/services/providers/factory.py` | Updated with SELF_HOSTED provider branches | +150 |
| `src/services/edition_service.py` | Edition detection and license management | 315 |
| `src/api/edition_endpoints.py` | 7 REST endpoints for edition/license | 250 |
| `tests/test_self_hosted_providers.py` | 46 tests for self-hosted adapters | 680 |
| `tests/test_edition_service.py` | 35 tests for edition service and API | 400 |

**Total Phase 1 Backend:** ~4,400 lines of code, 81 tests passing

**Self-Hosted Provider Adapters:**

| Adapter | Replaces | Key Features |
|---------|----------|--------------|
| Neo4jGraphAdapter | AWS Neptune | Cypher queries, entity/relationship CRUD, index management |
| OpenSearchAdapter | AWS OpenSearch | KNN vector search, BM25 keyword search, bulk operations |
| LocalLLMAdapter | AWS Bedrock | OpenAI-compatible API, streaming, multiple providers |
| MinIOStorageAdapter | AWS S3 | Bucket operations, presigned URLs, multipart upload |
| FileSecretsAdapter | AWS Secrets Manager | Fernet encryption, JSON storage, rotation tracking |
| PostgresDocumentAdapter | AWS DynamoDB | JSONB storage, GSI-equivalent indexes, TTL support |

**Edition Service Features:**

| Feature | Description |
|---------|-------------|
| 3-tier editions | Community (free), Enterprise, Enterprise+ |
| Feature mapping | 5-tier SaaS to 3-tier self-hosted |
| License validation | AURA-{edition}-{org}-{signature} format |
| API endpoints | GET/POST edition, features, license, upgrade-info |

**Phase 1.5 Migration Toolkit (Complete):**

| Component | Description | Lines |
|-----------|-------------|-------|
| `src/migration/__init__.py` | Package exports for migrators and base classes | 28 |
| `src/migration/base.py` | BaseMigrator abstract class with progress tracking, retry logic, batch processing | 423 |
| `src/migration/neptune_to_neo4j.py` | Graph migration (Gremlin to Cypher), vertices and edges with property preservation | 304 |
| `src/migration/dynamodb_to_postgres.py` | Document migration with TABLE_SCHEMAS, JSONB storage, DynamoDB type conversion | 380 |
| `src/migration/s3_to_minio.py` | Object storage migration with bucket mapping, streaming transfer, metadata preservation | 267 |
| `src/migration/secrets_to_file.py` | Secrets migration with Fernet encryption (AES-128-CBC), secure permissions (0600) | 304 |
| `src/migration/cli.py` | Unified CLI (neptune, dynamodb, s3, secrets, all), progress bar, dry-run mode | 559 |
| `tests/test_migration_toolkit.py` | 63 tests covering all migrators, CLI, integration, error handling | 932 |

**Total Phase 1.5:** ~3,200 lines of code, 63 tests passing

**Migration Toolkit Features:**

| Feature | Description |
|---------|-------------|
| Progress Tracking | Items/sec rate, ETA calculation, percent complete |
| Retry Logic | Configurable retries with exponential backoff |
| Batch Processing | Async processing with semaphore concurrency control |
| Dry-Run Mode | Validate migration without data changes |
| Verification | Post-migration data integrity verification |
| Cancellation | Graceful cancellation for long-running migrations |

**Phase 2 Kubernetes Helm Charts (Complete):**

| Component | Description | Lines |
|-----------|-------------|-------|
| `deploy/helm/aura/Chart.yaml` | Chart metadata with dependency declarations | 46 |
| `deploy/helm/aura/values.yaml` | Comprehensive default configuration | 710 |
| `deploy/helm/aura/templates/_helpers.tpl` | Reusable template functions (labels, images, env vars) | 340 |
| `deploy/helm/aura/templates/api/` | Deployment, Service, HPA, Ingress, PDB for FastAPI | 215 |
| `deploy/helm/aura/templates/frontend/` | Deployment, Service, HPA, Ingress, PDB for React UI | 180 |
| `deploy/helm/aura/templates/orchestrator/` | Deployment, Service, PDB for agent orchestration | 130 |
| `deploy/helm/aura/templates/neo4j/` | StatefulSet, Service, Secret, PDB for graph DB | 200 |
| `deploy/helm/aura/templates/opensearch/` | StatefulSet, Service, Secret for vector search | 160 |
| `deploy/helm/aura/templates/postgres/` | StatefulSet, Service, Secret for document storage | 140 |
| `deploy/helm/aura/templates/llm/` | vLLM, TGI, Ollama deployments with GPU support | 280 |
| `deploy/helm/aura/templates/networkpolicy.yaml` | Default-deny with explicit allow rules | 250 |
| `deploy/helm/aura/templates/rbac.yaml` | ServiceAccount, Role, RoleBinding | 75 |
| `deploy/helm/aura/templates/certificates.yaml` | cert-manager Certificate resources | 95 |
| `deploy/helm/aura/templates/configmap.yaml` | Configuration and feature flags | 65 |
| `deploy/helm/aura/templates/tests/` | Helm test hooks for all services | 145 |
| `deploy/helm/aura/values-self-hosted.yaml` | Enterprise with cloud LLM APIs | 110 |
| `deploy/helm/aura/values-air-gapped.yaml` | Full isolation with local LLM | 145 |
| `deploy/helm/aura/values-minimal.yaml` | Development/testing with minimal resources | 150 |

**Total Phase 2:** ~4,100 lines of Helm templates, 40 files

**Helm Chart Features:**

| Feature | Description |
|---------|-------------|
| HTTPS Health Checks | All probes use scheme: HTTPS per ADR-049 |
| HPA | Autoscaling for API (2-10 replicas) and Frontend (2-5 replicas) |
| PDB | PodDisruptionBudgets for all stateful services |
| NetworkPolicy | Default-deny with explicit allow rules |
| Pod Security | Restricted PSS, runAsNonRoot, readOnlyRootFilesystem |
| cert-manager | Automatic TLS certificate management |
| Edition Support | community/enterprise/enterprise_plus feature flags |
| GPU Support | vLLM/TGI with nvidia.com/gpu resources |

**Deployment Profiles:**

| Profile | Use Case | LLM Provider | GPU Required |
|---------|----------|--------------|--------------|
| values-self-hosted.yaml | Enterprise production | AWS Bedrock | No |
| values-air-gapped.yaml | Defense/classified | vLLM local | Yes |
| values-minimal.yaml | Development/testing | Ollama | No |

**Expert Reviews Incorporated:**
- Infrastructure Architect: Query language strategy (Gremlin vs Cypher), platform limitations
- Security Analyst: Default-deny NetworkPolicy, Ed25519 license validation, container security
- Systems Architect: Migration toolkit, multi-tenancy, support model

**Phase 3 Air-Gap Support (Complete):**

| Component | Description | Lines |
|-----------|-------------|-------|
| `deploy/airgap/scripts/create-airgap-bundle.sh` | Bundle creation with image export, Helm packaging, model weights | 450 |
| `src/services/licensing/__init__.py` | License module exports | 28 |
| `src/services/licensing/license_service.py` | Edition detection, feature gating, Ed25519 validation | 380 |
| `src/services/licensing/hardware_fingerprint.py` | Cross-platform machine ID, MAC, CPU fingerprinting | 270 |
| `src/services/licensing/offline_validator.py` | Offline license validation with hardware binding | 340 |
| `src/services/licensing/fips_compliance.py` | FIPS 140-2 approved algorithms (AES-256-GCM, SHA-256, PBKDF2) | 320 |
| `src/services/airgap/__init__.py` | Air-gap module exports | 25 |
| `src/services/airgap/egress_validator.py` | Network isolation validation (DNS, TCP, HTTP) | 290 |
| `src/services/airgap/model_verifier.py` | SHA-256 checksum verification for LLM weights | 270 |
| `src/services/airgap/inference_audit.py` | SIEM-compatible audit logging for LLM inference | 380 |
| `docs/self-hosted/AIR_GAP_DEPLOYMENT_GUIDE.md` | Comprehensive air-gap deployment documentation | 450 |
| `tests/test_licensing_service.py` | 30 tests for license service and editions | 320 |
| `tests/test_airgap_services.py` | 29 tests for egress, model verification, audit | 520 |

**Total Phase 3:** ~4,000 lines of code, 59 tests passing

**Air-Gap Features:**

| Feature | Description |
|---------|-------------|
| Bundle Creation | `create-airgap-bundle.sh` exports images, charts, models, docs |
| Offline Licensing | Ed25519 signed licenses with hardware fingerprinting |
| FIPS 140-2 | AES-256-GCM, SHA-256, PBKDF2 only; blocks MD5/SHA1/DES |
| Egress Validation | Validates all external connectivity blocked |
| Model Verification | SHA-256 checksums for all model weight files |
| Inference Audit | JSONL audit logs with SIEM export for compliance |

**License Editions:**

| Edition | Price | Features |
|---------|-------|----------|
| Community | Free (Apache 2.0) | Basic GraphRAG, single repo, vulnerability detection |
| Enterprise | Commercial | Multi-repo, SSO/SAML, audit logging, 99.9% SLA |
| Enterprise Plus | Commercial | Air-gap, FIPS 140-2, custom LLM, compliance reporting |

**Phase 4 Native Installers (Complete):**

| Component | Description | Lines |
|-----------|-------------|-------|
| `src/cli/__init__.py` | CLI package initialization | 10 |
| `src/cli/main.py` | Full CLI implementation with commands (status, config, license, deploy, health, logs) | 650 |
| `deploy/installer/native/windows/aura.wxs` | WiX v4 MSI installer definition | 105 |
| `deploy/installer/native/windows/build-msi.ps1` | PowerShell MSI build script with PyInstaller | 160 |
| `deploy/installer/native/macos/build-pkg.sh` | macOS PKG build script with productbuild | 230 |
| `deploy/installer/native/linux/debian/` | DEB package configuration (control, rules, changelog, postinst, build script) | 450 |
| `deploy/installer/native/linux/rpm/` | RPM spec and build script | 320 |
| `deploy/installer/native/homebrew/aura-cli.rb` | Homebrew formula for macOS/Linux | 65 |
| `deploy/installer/native/build-all.sh` | Cross-platform build orchestration | 380 |
| `docs/self-hosted/NATIVE_INSTALLERS_GUIDE.md` | Comprehensive installation documentation | 320 |
| `tests/test_cli.py` | 45 tests for CLI commands and argument parsing | 625 |

**Total Phase 4:** ~3,315 lines of code, 45 tests passing

**Native Installer Features:**

| Feature | Description |
|---------|-------------|
| Windows MSI | WiX v4 installer with PATH integration, shortcuts, registry keys |
| macOS PKG | productbuild installer with postinstall verification |
| Debian DEB | dpkg package with bash/zsh completions, man pages |
| RHEL RPM | rpmbuild spec with recommends/suggests for kubectl/helm |
| Homebrew | Formula with multi-arch support (arm64/x64), completions |
| CLI Commands | status, config (init/show/set), license (status/activate/request), deploy, health, logs |
| Shell Completions | Bash and Zsh completions for all commands |
| Cross-Platform Build | Single script builds for current platform with checksums |

**Status:** ADR-049 All Phases Complete (Phase 0-4)

---

### UI/UX Standardization Complete (Dec 31, 2025)

Comprehensive UI/UX improvements focusing on selection styling standardization, dashboard widget consistency, and test environment mock data.

**Test Environments Mock Data:**

Added mock data fallback for the Test Environments page in `frontend/src/services/environmentsApi.js`:
- 5 mock environments for development/demo mode:
  - API Integration Tests (standard, active)
  - Security Vulnerability Scan (compliance, active)
  - SQL Injection Patch Test (quick, expiring)
  - E2E Test Suite - Sprint 47 (extended, pending_approval)
  - GraphRAG Performance Benchmark (standard, provisioning)
- Mock quota data: 2/3 concurrent slots, $127.40/$500 monthly budget used
- Dev mode fallback for `listEnvironments()` and `getUserQuota()` when API unavailable
- Enables UI demonstration without backend connectivity

**Selection Styling Standardization:**

All interactive selection components now use consistent `aura-*` blue colors across light and dark themes.

| Component | Changes Applied | Status |
|-----------|-----------------|--------|
| AgentRegistry | Selection uses `border-aura-500 bg-aura-50 dark:bg-aura-900/20` | Complete |
| TraceExplorer | Selection uses `border-aura-500 bg-aura-50 dark:bg-aura-900/20` | Complete |
| ScanModal | Scan type cards use `ring-2 ring-aura-500 border-aura-500` | Complete |
| AgentDeployModal | Agent type cards use `ring-2 ring-aura-500 border-aura-500` | Complete |

**Dashboard Widget Improvements:**

| Improvement | Description | Status |
|-------------|-------------|--------|
| Widget card styling | Applied `glass-card` class for uniform darker backgrounds | Complete |
| Heading fonts | Standardized widget heading font sizes to `text-base` | Complete |
| Chart sizing | Increased chart sizes to maximize widget space utilization | Complete |
| DonutChart enhancements | Larger size with improved hover effects | Complete |
| LineChart enhancements | Rectangular shape, vertical gridlines, y-axis title | Complete |
| Y-axis labels | Increased font size to match card text | Complete |
| Error Rate card | Removed red border at low error rates, uses amber/red colors | Complete |

**Dashboard Item Card Consistency:**

| Widget | Changes Applied |
|--------|-----------------|
| Agent Status | Wrapped items in cards like Security Alerts |
| System Health | Wrapped items in cards for consistency |
| Graph Metrics | Wrapped items in cards for consistency |
| Approval Funnel | Wrapped items in cards for consistency |

**HITL Approvals Workflow:**

- Added comprehensive mock data fallback for development testing
- 290+ lines added to ApprovalDashboard.jsx
- Enables UI demonstration without backend connectivity

**Files Modified (13 files):**
- `frontend/src/components/AgentRegistry.jsx`
- `frontend/src/components/observability/TraceExplorer.jsx`
- `frontend/src/components/modals/ScanModal.jsx`
- `frontend/src/components/settings/AgentDeployModal.jsx`
- `frontend/src/components/ApprovalDashboard.jsx`
- `frontend/src/components/dashboard/*.jsx` (multiple widget files)
- `frontend/src/services/environmentsApi.js` (Test Environments mock data)

**Commits:** 49 commits since Dec 29, 2025

---

### Customer Onboarding Features Complete (Dec 30, 2025)

Implemented comprehensive customer onboarding system to improve user activation and retention.

**Onboarding Components (6 features):**

| Priority | Feature | Description | Status |
|----------|---------|-------------|--------|
| P0 | Welcome Modal | First-time user modal with feature highlights, glass morphism design | Complete |
| P1 | Onboarding Checklist | Fixed bottom-right widget tracking 5 setup steps with progress ring | Complete |
| P2 | Welcome Tour | Joyride-style guided tour with spotlight overlay and tooltips (7 steps) | Complete |
| P3 | Feature Tooltips | In-app tooltips for complex features (GraphRAG, HITL, Sandbox) | Complete |
| P4 | Getting-Started Videos | Video catalog with chapter navigation and progress tracking | Complete |
| P5 | Team Invite Wizard | Multi-step wizard for inviting team members with role assignment | Complete |

**Frontend Implementation:**
- `OnboardingContext.jsx` - Central state management with localStorage persistence
- `WelcomeModal.jsx` - Glass morphism modal with keyboard navigation (Esc to close)
- `OnboardingChecklist.jsx` - Collapsible checklist with progress visualization
- `WelcomeTour.jsx` - Tour orchestration with spotlight and tooltip components
- `FeatureTooltip.jsx` - Dismissable tooltips with pulsing indicators
- `VideoModal.jsx` - HTML5 video player with chapter navigation
- `TeamInviteWizard.jsx` - 4-step wizard (email entry, roles, review, completion)
- `DevToolbar.jsx` - Dev-only toolbar for testing onboarding flow

**API Services:**
- `onboardingApi.js` - Full API service with dev mode localStorage fallback
- `authApi.js` - Enhanced with dev mode auto-login for testing

**Key Features:**
- WCAG 2.1 AA accessibility compliance
- Full dark mode support
- Keyboard navigation throughout
- Auto-sync to backend with localStorage fallback
- Dev toolbar for testing without backend

**Files Added/Modified:**
- 8 new components in `frontend/src/components/onboarding/`
- 1 new context in `frontend/src/context/OnboardingContext.jsx`
- 2 new services in `frontend/src/services/`
- Updated `App.jsx` with OnboardingProvider integration

**Tests:** 379 frontend tests passing

---

### Performance Optimizations Complete (Dec 30, 2025)

Implemented comprehensive performance optimization plan (11 items) to reduce latency and improve throughput without impacting reliability or security.

**Backend Optimizations (7 items):**

| # | Optimization | Implementation | Impact |
|---|--------------|----------------|--------|
| 1 | Remove blocking work from event loop | `asyncio.to_thread()` for git clone/fetch, AST parsing, file I/O | p99 latency improvement |
| 2 | Batch OpenSearch writes | `bulk_index_embeddings()` with 200-doc batches | 200x HTTP overhead reduction |
| 3 | Concurrency limits for ingestion | `asyncio.Semaphore` (parse: 10, graph: 20, index: 5) | Prevents CPU/IO saturation |
| 4 | Stream file reads with size caps | 20KB max for embeddings, streaming for larger files | Reduced memory allocation |
| 5 | HTTP client reuse with keep-alive | Process-wide `httpx.Client` with HTTP/2, 5-min keepalive | Reduced TLS handshakes |
| 6 | Lazy boto3 imports | Import inside functions, cache SSM client | Faster cold starts |
| 7 | JWKS token validation O(1) lookup | Pre-build `kid to key` map, TTL cache (1 hour) | Faster auth validation |

**Infrastructure Optimizations (2 items):**

| # | Optimization | Implementation | Impact |
|---|--------------|----------------|--------|
| 8 | Reduce container image size | Split requirements into `-api.txt` and `-agents.txt` | ~2GB image size reduction |
| 11 | Neptune OSGP index | `neptune_enable_osgp_index: '1'` parameter group | 2-10x faster `bothE()` traversals |

**Frontend Optimizations (1 item):**

| # | Optimization | Implementation | Impact |
|---|--------------|----------------|--------|
| 9 | Frontend build & runtime | `React.memo` on list components, Vite `minify: 'esbuild'`, `cssCodeSplit: true` | Faster renders, smaller bundles |

**Observability (1 item):**

| # | Optimization | Implementation | Impact |
|---|--------------|----------------|--------|
| 10 | Reliability metrics | Event loop lag, ingest queue depth, OpenSearch bulk latency, JWKS fetch latency | Performance regression detection |

**Security Enhancements (during optimization):**
- JWKS TTL cache with thread-safe refresh (prevents race conditions)
- Symlink detection and path traversal protection in file reader
- HTTP header-based git authentication (credentials no longer in URLs)

**Files Modified:**
- `src/services/git_ingestion_service.py` - Async operations, bulk indexing, security fixes
- `src/api/auth.py` - JWKS caching, HTTP client reuse
- `src/api/main.py` - Event loop lag monitoring
- `src/services/observability_service.py` - Reliability metrics
- `deploy/cloudformation/neptune-simplified.yaml` - OSGP parameter group
- `deploy/cloudformation/neptune-serverless.yaml` - OSGP parameter group
- `deploy/docker/*/Dockerfile.*` - Slim dependency images
- `requirements-api.txt`, `requirements-agents.txt` - Split dependencies
- `frontend/vite.config.js` - Build optimizations
- `frontend/src/components/ui/ActivityFeed.jsx` - React.memo
- `frontend/src/components/ApprovalDashboard.jsx` - React.memo
- `frontend/src/components/IncidentInvestigations.jsx` - React.memo

**Test Updates:**
- Updated `test_git_ingestion.py` for async methods and bulk API
- Fixed `src/api/main.py` syntax error (duplicate global declaration)
- All 8,174 tests passing

---

### Graph Search Implementation & Security Fixes (Dec 29, 2025)

**Issue #151: Graph Search Implementation - COMPLETE**

Implemented the `_graph_search()` method in `ContextRetrievalService`, completing the hybrid GraphRAG architecture that combines vector, graph, and BM25 search strategies.

**New GraphQueryType Enum (5 Types):**

| Type | Description | Use Case |
|------|-------------|----------|
| `CALL_GRAPH` | Function call relationships | Find callers/callees of a function |
| `DEPENDENCIES` | Import/module dependencies | Trace package dependencies |
| `INHERITANCE` | Class hierarchy | Find parent/child classes |
| `REFERENCES` | Variable/symbol references | Track symbol usage across codebase |
| `RELATED` | Semantically related entities | General context discovery |

**New Methods Added to `context_retrieval_service.py`:**

| Method | Purpose |
|--------|---------|
| `_graph_search()` | Main graph search orchestrator |
| `_extract_graph_terms()` | Extract searchable terms from queries |
| `_detect_graph_query_type()` | Classify query intent for optimal graph traversal |
| `_execute_graph_query()` | Execute Neptune Gremlin queries |
| `_build_gremlin_query()` | Construct type-specific Gremlin traversals |
| `_convert_graph_results_to_file_matches()` | Transform graph results to ranked file matches |

**Test Coverage:**
- 30 new unit tests added to `tests/test_context_retrieval_service.py`
- Covers all 5 query types with edge cases
- Mock-based testing for Neptune Gremlin client

**Architecture Completion:**
- **Before:** Vector (OpenSearch KNN) + BM25 (keyword) only
- **After:** Vector + Graph (Neptune Gremlin) + BM25 = Full Hybrid GraphRAG
- Enables structural code understanding (call graphs, dependencies, inheritance)

---

**IAM Permission Security Fixes - COMPLETE**

Scoped IAM permissions from `Resource: '*'` to project-specific ARNs in `deploy/cloudformation/codebuild-data.yaml`:

**Neptune/RDS Permissions:**

| Before | After |
|--------|-------|
| `Resource: '*'` | `arn:${AWS::Partition}:rds:${AWS::Region}:${AWS::AccountId}:cluster:${ProjectName}-neptune-*` |
| | `arn:${AWS::Partition}:rds:${AWS::Region}:${AWS::AccountId}:db:${ProjectName}-neptune-*` |
| | Subnet groups, parameter groups, cluster parameter groups |

**OpenSearch Permissions:**

| Before | After |
|--------|-------|
| `Resource: '*'` | `arn:${AWS::Partition}:es:${AWS::Region}:${AWS::AccountId}:domain/${ProjectName}-*` |

**Security Impact:**
- Eliminates overly permissive wildcards
- Enforces principle of least privilege
- Maintains CMMC Level 3 compliance posture

---

**DynamoDB GSI Additions (Sandbox Layer) - COMPLETE**

Added 2 new Global Secondary Indexes to `aura-approval-requests` table in `deploy/cloudformation/sandbox.yaml`:

| GSI Name | Partition Key | Sort Key | Purpose |
|----------|---------------|----------|---------|
| `StatusBucketIndex` | `StatusBucket` | `CreatedAt` | Partition spreading to prevent hot partitions (items distributed across 10 buckets like `PENDING#0` through `PENDING#9`) |
| `ReviewedAtIndex` | `ReviewMonth` | `ReviewedAt` | Time-range queries for audit logs (partitioned by month `YYYY-MM`) |

**Deployment Notes:**
- DynamoDB only allows 1 GSI change per CloudFormation update
- Required staged deployment: Deploy GSI 1, wait, deploy GSI 2
- Both indexes now active and operational

---

### Product Infrastructure Implementation (Dec 18-20, 2025)

- **Product Infrastructure Phases 1-3 Implemented** - Building platform capabilities for billing, analytics, feature management, and customer health

**Phase 1: Customer Packaging (Complete)**

| Component | Description | Status |
|-----------|-------------|--------|
| Customer Installer | `deploy/installer/aura-install.sh` - Preflight checks, config wizard, verification | DEPLOYED |
| Customer Documentation | `docs/customer/` - Quick Start, Architecture, Prerequisites, Troubleshooting (8 guides) | DEPLOYED |
| CloudFormation Quick Start | `deploy/customer/cloudformation/` - Single-click deployment templates | DEPLOYED |

**Phase 2: Business Infrastructure (Complete)**

| Component | Description | Files | Status |
|-----------|-------------|-------|--------|
| Marketing Site | Astro static site for aenealabs.com | `marketing/site/` (~15 pages) | DEPLOYED |
| Marketing Infrastructure | CloudFront + S3 + OAC | `deploy/cloudformation/marketing-site.yaml` | DEPLOYED |
| Docs Portal | ReDoc API documentation | `deploy/cloudformation/docs-portal.yaml` | DEPLOYED |
| Route 53 DNS | Public hosted zone config | `deploy/cloudformation/route53-dns.yaml` | DEPLOYED |
| Support Ticketing (ADR-046) | Connector framework for ticketing systems | `src/services/ticketing/` (~2,400 lines) | DEPLOYED |
| Ticketing UI | Settings page integration | `frontend/src/components/settings/TicketingSettings.jsx` | DEPLOYED |
| Customer Health Dashboard | Per-customer metrics aggregation | `src/services/health/customer_metrics.py` | DEPLOYED |
| Health Dashboard UI | React dashboard component | `frontend/src/components/CustomerHealthDashboard.jsx` | DEPLOYED |
| Legal Templates | MSA, EULA, DPA, BAA | `docs/legal/templates/` (4 documents) | DEPLOYED |

**Support Ticketing Connectors (ADR-046):**
- `GitHubIssuesConnector` - Native GitHub Issues integration (fully implemented)
- `ZendeskConnector` - Enterprise ticketing (interface ready)
- `LinearConnector` - Modern issue tracking (interface ready)
- `ServiceNowTicketConnector` - ITSM integration (interface ready)
- Unified `TicketingConnectorFactory` for provider abstraction
- API: `/api/v1/ticketing/*` endpoints for CRUD operations

**Customer Health Metrics:**
- SaaS mode: Per-customer metrics with CustomerId dimension
- Self-hosted mode: Single-tenant metrics
- Metrics: API latency (p50/p95/p99), agent success rate, token costs, storage usage
- Health scoring: 0-100 score with status (healthy/degraded/unhealthy)
- API: `/api/v1/health/customer/{id}`, `/api/v1/health/customers`, `/api/v1/health/summary`

**Phase 3: Private Beta Features (Complete)**

| Component | Description | Files | Status |
|-----------|-------------|-------|--------|
| Feature Flags Service | Tier-gated, customer-override, rollout % | `src/config/feature_flags.py` (~500 lines) | DEPLOYED |
| Feature Flags API | REST endpoints for flag management | `src/api/feature_flags_endpoints.py` (~350 lines) | DEPLOYED |
| Beta Enrollment | Customer beta program enrollment | `POST /api/v1/features/beta/enroll` | DEPLOYED |
| Feature Flags Tests | Comprehensive test coverage | `tests/test_feature_flags.py` (35 tests) | PASSING |

**Feature Flags System:**
- **Core Features (5):** vulnerability_scanning, patch_generation, sandbox_testing, hitl_approval, graphrag_context
- **Beta Features (8):** advanced_analytics, custom_agent_templates, multi_repo_scanning, autonomous_remediation, knowledge_graph_explorer, ticket_integrations, neural_memory, real_time_intervention
- **Tiers:** FREE to STARTER to PROFESSIONAL to ENTERPRISE to GOVERNMENT
- **Customer Overrides:** Per-customer enable/disable with beta enrollment
- **Environment Overrides:** `AURA_FEATURE_*` environment variables
- **Rollout Percentages:** Gradual feature rollout based on customer hash

**CI/CD for Marketing (Complete):**
- `deploy/buildspecs/buildspec-marketing.yml` - 7-phase build pipeline
- `deploy/cloudformation/codebuild-marketing.yaml` - CodeBuild project with IAM
- `deploy/scripts/deploy-marketing-site.sh` - Manual deployment script
- `deploy/scripts/deploy-marketing-codebuild.sh` - CodeBuild project deployer
- `deploy/scripts/generate-api-docs.sh` - OpenAPI/ReDoc generator

**Feedback & Analytics (Complete):**

| Component | Description | Files | Status |
|-----------|-------------|-------|--------|
| Feedback Service | NPS surveys, feedback collection | `src/services/feedback_service.py` (~540 lines) | DEPLOYED |
| Feedback API | REST endpoints for feedback | `src/api/feedback_endpoints.py` (~470 lines) | DEPLOYED |
| Feedback Widget | React floating widget | `frontend/src/components/FeedbackWidget.jsx` (~465 lines) | DEPLOYED |
| Usage Analytics Service | Event tracking, metrics aggregation | `src/services/usage_analytics_service.py` (~550 lines) | DEPLOYED |
| Usage Analytics API | REST endpoints for analytics | `src/api/usage_analytics_endpoints.py` (~380 lines) | DEPLOYED |
| Usage Dashboard | React analytics dashboard | `frontend/src/components/UsageAnalyticsDashboard.jsx` (~400 lines) | DEPLOYED |
| Analytics Tests | Comprehensive test coverage | `tests/test_usage_analytics.py` (25 tests) | PASSING |

**Feedback System:**
- 6 feedback types: general, bug_report, feature_request, usability, documentation, performance
- NPS (Net Promoter Score) survey with 0-10 scale
- Automatic priority assignment based on type and NPS score
- Page URL and browser context capture
- API: `/api/v1/feedback/*`, `/api/v1/feedback/nps/*`

**Usage Analytics:**
- Metrics: api_request, feature_usage, agent_execution, login, page_view, search, export, error
- Time granularity: hourly, daily, weekly, monthly
- Feature adoption tracking with trend analysis
- API usage statistics with latency percentiles (p50/p95/p99)
- Multi-tenant support with customer filtering
- API: `/api/v1/analytics/usage`, `/api/v1/analytics/api`, `/api/v1/analytics/features`

**Phase 4: Revenue Generation (Complete)**

| Component | Description | Files | Status |
|-----------|-------------|-------|--------|
| Billing Service | Stripe subscription management | `src/services/billing_service.py` (~650 lines) | DEPLOYED |
| Billing API | REST endpoints for billing | `src/api/billing_endpoints.py` (~480 lines) | DEPLOYED |
| Customer Health Service | Health score algorithm | `src/services/customer_health_service.py` (~580 lines) | DEPLOYED |
| Customer Health API | REST endpoints for health | `src/api/customer_health_endpoints.py` (~380 lines) | DEPLOYED |

**Billing System:**
- 5 plans: FREE, STARTER, PROFESSIONAL, ENTERPRISE, GOVERNMENT (custom)
- Subscription lifecycle: create, update, cancel, trial periods
- Usage-based billing: LLM tokens (per-token), agent executions (per-execution)
- Invoice generation with line items
- Payment method management (card, bank account)
- API: `/api/v1/billing/plans`, `/api/v1/billing/subscription`, `/api/v1/billing/invoices`

**Customer Health Score:**
- 5 components: engagement (25%), adoption (25%), satisfaction (20%), value_realization (15%), support_health (15%)
- Status levels: EXCELLENT (80+), HEALTHY (60-79), AT_RISK (40-59), CRITICAL (0-39)
- Churn risk assessment: LOW, MEDIUM, HIGH, CRITICAL
- Expansion potential: HIGH, MEDIUM, LOW, NONE
- Trend analysis with historical tracking
- Automated recommendations based on component scores
- API: `/api/v1/customer-health/score`, `/api/v1/customer-health/at-risk`, `/api/v1/customer-health/expansion`

**Phase 4.3: AWS Marketplace Integration (Complete)**

| Component | Description | Files | Status |
|-----------|-------------|-------|--------|
| Marketplace Service | AWS Marketplace metering integration | `src/services/marketplace_service.py` (~680 lines) | DEPLOYED |
| Marketplace API | REST endpoints for Marketplace | `src/api/marketplace_endpoints.py` (~520 lines) | DEPLOYED |
| Marketplace Infrastructure | DynamoDB, SNS, Lambda for metering | `deploy/cloudformation/marketplace.yaml` (~580 lines) | DEPLOYED |
| Marketplace Documentation | Seller guide for AWS listing | `docs/marketplace/AWS_MARKETPLACE_SELLER_GUIDE.md` | DEPLOYED |

**AWS Marketplace Features:**
- **Customer Registration:** ResolveCustomer API for token-based subscription activation
- **SNS Notifications:** Lambda processor for subscribe/unsubscribe events
- **Entitlement Verification:** GetEntitlements API integration for access control
- **Usage Metering:** Scheduled Lambda for hourly usage submission to Marketplace
- **Billing Integration:** Bridge between BillingService and MarketplaceService

**Usage Dimensions:**
- `LLMTokens` - AI model token consumption
- `AgentExecutions` - Autonomous agent runs
- `APICalls` - API requests over base limit
- `StorageGB` - Graph and vector storage
- `GraphNodes` - Code entities indexed
- `Developers` - Active developer seats

**Product Codes:**
- `aura-starter-monthly` - Starter tier ($2,500/mo)
- `aura-professional-monthly` - Professional tier ($7,500/mo)
- `aura-enterprise-monthly` - Enterprise monthly ($20,000/mo)
- `aura-enterprise-annual` - Enterprise annual contract
- `aura-government-annual` - Government (custom pricing)

**API Endpoints:**
- `POST /api/v1/marketplace/resolve` - Resolve customer from registration token
- `POST /api/v1/marketplace/sns-webhook` - Handle SNS notifications
- `GET /api/v1/marketplace/customers` - List marketplace customers
- `GET /api/v1/marketplace/entitlements` - Check entitlements
- `POST /api/v1/marketplace/usage` - Record usage
- `POST /api/v1/marketplace/meter` - Submit pending usage to AWS

**Phase 5: General Availability Infrastructure (Complete)**

| Component | Description | Files | Status |
|-----------|-------------|-------|--------|
| Multi-Region Config | Region failover configuration | `deploy/multi-region/region-config.yaml` (~120 lines) | DEPLOYED |
| Multi-Region CloudFormation | Route 53 health checks, failover automation | `deploy/cloudformation/multi-region-global.yaml` (~430 lines) | DEPLOYED |
| SLA Monitoring Service | Tier-based SLA/SLO tracking | `src/services/sla_monitoring_service.py` (~700 lines) | DEPLOYED |
| SLA API | REST endpoints for SLA monitoring | `src/api/sla_endpoints.py` (~500 lines) | DEPLOYED |
| Disaster Recovery Service | Failover orchestration, DR drills | `src/services/disaster_recovery_service.py` (~650 lines) | DEPLOYED |
| DR API | REST endpoints for DR operations | `src/api/disaster_recovery_endpoints.py` (~520 lines) | DEPLOYED |
| Compliance Evidence Service | SOC 2 evidence collection | `src/services/compliance_evidence_service.py` (~900 lines) | DEPLOYED |
| Compliance API | REST endpoints for compliance | `src/api/compliance_endpoints.py` (~600 lines) | DEPLOYED |
| Phase 5 Tests | SLA, DR, Compliance test coverage | 3 test files (~1,850 lines, 130 tests) | PASSING |

**SLA Monitoring System:**
- 4 SLA tiers: STANDARD (99.5%), PROFESSIONAL (99.9%), ENTERPRISE (99.95%), GOVERNMENT (99.99%)
- SLO metrics: uptime, latency (p50/p95/p99), error_rate, throughput
- Breach detection with severity levels (warning, minor, major, critical)
- Credit calculation with tier-specific schedules (5%-50% based on downtime)
- API: `/api/v1/sla/status`, `/api/v1/sla/tiers`, `/api/v1/sla/breaches`, `/api/v1/sla/credits`

**Disaster Recovery:**
- Multi-region: us-east-1 (primary), us-west-2 (DR), us-gov-west-1 (GovCloud)
- Recovery objectives by tier: Enterprise (15min RTO, 5min RPO), Government (5min RTO, 1min RPO)
- Failover orchestration with step tracking (DNS, traffic, sync, validation)
- DR drill types: tabletop, partial, full
- Backup validation with restore capability testing
- API: `/api/v1/dr/regions`, `/api/v1/dr/failover`, `/api/v1/dr/drills`, `/api/v1/dr/backups`

**SOC 2 Compliance Evidence:**
- 5 Trust Services Categories: Security (CC), Availability (A), Processing Integrity (PI), Confidentiality (C), Privacy (P)
- 20+ control definitions (CC1-CC8, A1, C1 series)
- Automated evidence collectors: IAM config, CloudTrail, security scans, access reviews
- Control assessment with effectiveness scoring
- Gap analysis with remediation priorities
- Report types: full, executive, gap_analysis, evidence_only
- API: `/api/v1/compliance/controls`, `/api/v1/compliance/evidence`, `/api/v1/compliance/assessments`, `/api/v1/compliance/reports`

---

### Certification Roadmaps (Dec 22, 2025)

Comprehensive certification roadmaps for government and defense market access (~3,500 lines of documentation):

| Certification | Timeline | Market Access |
|---------------|----------|---------------|
| **CMMC Level 2** | 8-12 months | 60% of DoD contracts |
| **CMMC Level 3** | +6-12 months | 100% of DoD contracts |
| **FedRAMP High** | 9-14 months | Federal agency contracts |
| **IL5** | +2-4 months | DoD CUI/classified workloads |

**Documentation Created:**
- `docs/compliance/roadmaps/README.md` - Certification hierarchy, decision matrix
- `docs/compliance/roadmaps/CMMC_LEVEL_2_ROADMAP.md` - 110 NIST 800-171 controls, C3PAO process
- `docs/compliance/roadmaps/CMMC_LEVEL_3_ROADMAP.md` - 24 enhanced NIST 800-172 controls
- `docs/compliance/roadmaps/FEDRAMP_HIGH_ROADMAP.md` - 421 NIST 800-53 controls, 3PAO assessment
- `docs/compliance/roadmaps/IL5_CERTIFICATION_ROADMAP.md` - STIG, FIPS 140-2/3, DISA CAP

**Recommended Path:** CMMC Level 2 to FedRAMP High to IL5 to CMMC Level 3

**Leverage Points (Existing Advantages):**
- 100% GovCloud-ready infrastructure (19/19 services)
- 4,874+ automated tests for evidence generation
- 328 security tests for continuous monitoring proof
- Infrastructure-as-Code for CM controls
- SOC 2 compliance evidence service deployed

---

### Code Quality & Type Safety (Dec 25, 2025)

**Issue #44: Type Hints Cleanup - COMPLETE**

Comprehensive mypy type hints cleanup across the entire codebase:

| Category | Files Fixed | Errors Resolved |
|----------|-------------|-----------------|
| Service Files (Batch 1-5) | 17 files | ~150 errors |
| API Endpoints | 10 files | ~180 errors |
| Lambda Functions | 14 files | ~80 errors |
| Core Exceptions | 1 file | 1 error |
| **Total** | **42 files** | **~410 errors** |

**Result:** All 269 source files in `src/` now pass mypy with 0 errors.

**PRs Merged:** #105-#119 (15 PRs total)

**Key Fixes:**
- Added proper `Dict[str, Any]` annotations for dynamic dicts
- Fixed service method signatures to match implementations
- Added `TYPE_CHECKING` guards for boto3/botocore imports
- Fixed dataclass attribute access vs dict access patterns
- Added `Optional` type hints for nullable parameters
- Used `cast()` for type narrowing where needed

**Scalability Assessment:**

Architecture review for concurrent user capacity:

| Scale | Status | Monthly Cost |
|-------|--------|--------------|
| 100-500 users | Ready today | $3-5K |
| 1,000 users | Minor upgrades (HPA, m5.large) | $6-9K |
| 10,000 users | Add Redis, Neptune replicas, CDN | $20-40K |
| 100,000+ users | Multi-region active-active | $150-300K |

**Scalability Strengths:**
- DynamoDB on-demand scales automatically
- Semantic caching provides 60-70% LLM cost reduction
- Multi-region infrastructure already templated
- 100% GovCloud compatible (19/19 services)

**Primary Bottlenecks (at scale):**
- EKS: t3.medium nodes, max 5 nodes, no HPA configured
- Neptune: db.t3.medium (~300 connections)
- OpenSearch: t3.small.search (~80 queries/sec)
- LLM latency: 2-30 seconds per call

---

### GitHub Actions CI/CD Optimizations (Dec 27, 2025)

Implemented industry-standard CI/CD optimizations following Netflix/Spotify patterns to reduce GitHub Actions minutes by an estimated 50-60%:

**Path Filtering:**
- Documentation-only changes (`*.md`, `docs/**`) skip full CI pipeline
- Frontend changes trigger frontend-specific workflows only
- Backend changes trigger Python test workflows only

**Selective Test Execution:**
- Push to `main` runs lint-only (fast feedback)
- Pull requests run full test suite (comprehensive validation)
- Enables rapid iteration on main while maintaining PR quality gates

**Job Timeouts:**
- Lint jobs: 10 minute timeout
- Test jobs: 30 minute timeout
- Build jobs: 20 minute timeout
- Prevents hung jobs from consuming unlimited minutes

**Expected Impact:**
- 50-60% reduction in GitHub Actions minutes
- Faster feedback on documentation-only PRs (~2 min vs ~15 min)
- Reduced cost for CI/CD operations
- Follows industry patterns from Netflix, Spotify, and major open-source projects

---

### Pre-commit Configuration & Code Quality (Dec 28, 2025)

Comprehensive pre-commit hook configuration to eliminate false positives and ensure CI stability:

**Pre-commit False Positives Documentation:**

Created `docs/reference/PRE_COMMIT_FALSE_POSITIVES.md` (~425 lines) documenting all verified false positives with:
- Verification process and reviewer attribution
- Affected files and patterns for each hook
- Rationale for each exclusion
- Configuration file references

**Hook Configuration Updates:**

| Hook | Configuration | Purpose |
|------|--------------|---------|
| `aura-secrets-scan` | Exclude `frontend/src/components/auth/*` | React form field names (Password, NewPassword) |
| `check-yaml` | Exclude `deploy/cloudformation/*.yaml` | CloudFormation intrinsic functions (!Sub, !Ref) |
| `detect-private-key` | Exclude tests, templates, docs | Test fixtures with mock keys |
| `bandit` | `-ll -ii` flags, exclude `src/lambda/` | MEDIUM+ severity only |
| `flake8` | Exclude `deploy/`, `scripts/`, `tests/` | Intentional patterns in non-src code |

**Flake8 Code Quality Fixes:**

| Warning | Files Fixed | Fix Applied |
|---------|-------------|-------------|
| B007 (unused loop var) | 8 files | Prefix with underscore (`_iteration`) |
| B008 (function call default) | 2 files | Add `# noqa: B008` comment |
| C401 (generator to set) | 5 files | Convert `set(x for...)` to `{x for...}` |
| C420 (dict comprehension) | 2 files | Use `dict.fromkeys()` |

**Secrets Detection Fix:**

Fixed overly broad false positive pattern that incorrectly filtered real passwords in connection strings:
- **Before:** `r"(?:Password|PasswordConfirm|...)"` matched "password" in `postgresql://user:password@host`
- **After:** `r"(?:set|handle|on|get|validate)...(Password|Secret)"` matches only camelCase function names

**Frontend Cleanup:**

108 files updated to remove unnecessary explicit React imports (React 17+ JSX transform handles this automatically).

**Test Results:**
- All 8,083 tests passing
- Coverage: 69.79% (meets 69.5% threshold)
- All pre-commit hooks passing (except `no-commit-to-branch` on main - expected)

### Frontend Dependency Upgrades (Dec 28, 2025)

Major frontend dependency upgrades completed in 5 phases to modernize the stack:

**Package Upgrades:**

| Package | Previous | New | Notes |
|---------|----------|-----|-------|
| Vite | 6.0.7 | 7.0.0 | Breaking: requires `--allowNativeModules` flag |
| React | 18.3.1 | 19.0.0 | New JSX transform, no automatic React import |
| React DOM | 18.3.1 | 19.0.0 | Companion upgrade |
| Tailwind CSS | 3.4.16 | 4.1.0 | CSS-first configuration |
| @tailwindcss/vite | - | 4.1.0 | New: replaces PostCSS plugin |
| react-grid-layout | 1.5.0 | 2.0.1 | Breaking: renamed exports |
| eslint-plugin-react | 7.37.4 | 7.37.5 | Minor update |
| eslint-plugin-react-hooks | 5.1.0 | 5.2.0 | React 19 compatibility |

**Tailwind CSS v4 Migration:**

- Migrated from JS config (`tailwind.config.js`) to CSS-first config (`@theme` directive)
- Replaced `@tailwind base/components/utilities` with `@import 'tailwindcss'`
- Added `@variant dark (&:where(.dark, .dark *))` for class-based dark mode
- Fixed `@apply` directives that referenced custom component classes (inlined styles)
- Deleted `tailwind.config.js` and `postcss.config.js` (handled by Vite plugin)

**React 19 Compatibility Fixes:**

- Fixed `ReferenceError: React is not defined` in 3 files using `React.Fragment`
- Added explicit `Fragment` imports and replaced `React.Fragment` with `Fragment`:
  - `RepositoryOnboardWizard.jsx`
  - `FileViewer.jsx`
  - `ExecutionTimeline.jsx`

**Bug Fixes:**

| Issue | Root Cause | Fix |
|-------|------------|-----|
| White hover background in dark mode | Invalid color `surface-750` (doesn't exist) | Changed to `surface-700` |
| Files affected | `SecurityAlertsPanel.jsx`, `QueryDecompositionPanel.jsx` | Semantic color palette |

**Verification:**
- `npm run lint` - passing (0 errors)
- `npm run build` - successful (5.75s)
- Dark mode toggle - working correctly
- All tabs tested in browser - functional

### Bundle Optimization & Code Splitting (Dec 28, 2025)

Implemented comprehensive code splitting to reduce initial bundle size by 91%:

**Before/After Comparison:**

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Main bundle | 2,066 KB | 177 KB | **91% reduction** |
| Initial page load | ~2 MB | ~420 KB | **80% reduction** |

**Route-Based Lazy Loading (App.jsx):**

- Converted 18 page components to `React.lazy()` with dynamic imports
- Created `PageLoadingFallback.jsx` with contextual loading states
- Wrapped routes with `SuspenseWrapper` for error boundary isolation
- Components lazy-loaded: Dashboard, CKGEConsole, SettingsPage, ProfilePage, ApprovalDashboard, IncidentInvestigations, SecurityAlertsPanel, RedTeamDashboard, AgentRegistry, AgentManagerView, Environments, RepositoriesList, TraceExplorer, IntegrationHub, ActivityDetail, auth pages

**Dynamic Mermaid Import (ChatMessage.jsx):**

- Replaced static `import mermaid` with dynamic `import()` via singleton loader
- Created `mermaidLoader.js` utility to cache mermaid initialization
- Mermaid + dependencies (~2.5 MB) now only load when viewing diagrams

**Manual Chunking Strategy (vite.config.js):**

| Chunk | Size (gzip) | When Loaded |
|-------|-------------|-------------|
| `vendor-react` | 229 KB (73 KB) | Always (React core) |
| `vendor-icons` | 85 KB (15 KB) | Always (Heroicons, Lucide) |
| `vendor-mermaid` | 2,595 KB (736 KB) | Only when viewing diagrams |
| `vendor-auth` | 47 KB (16 KB) | Only during login/signup |
| `vendor-grid` | 57 KB (19 KB) | Only on Dashboard |

**Page-Specific Chunks (Lazy Loaded):**

| Page | Chunk Size | Notes |
|------|------------|-------|
| Dashboard | 81 KB | Includes grid layout |
| SettingsPage | 205 KB | Largest page (many tabs) |
| AgentManagerView | 133 KB | Real-time agent monitoring |
| CKGEConsole | 66 KB | Knowledge graph explorer |
| SecurityAlertsPanel | 16 KB | Lightweight alerts view |

**New Files:**
- `src/components/ui/PageLoadingFallback.jsx` - Loading fallback with error boundary
- `src/utils/mermaidLoader.js` - Singleton for lazy mermaid loading

---

**Historical Archive Note:**

> For detailed December 12-17, 2025 development history, see [archive/status/PROJECT_STATUS-v1.3-dec-12-17.md](PROJECT_STATUS-v1.3-dec-12-17.md)
