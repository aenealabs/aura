# ADR-043: Repository Onboarding UI Wizard

**Status:** Deployed
**Date:** 2025-12-17
**Decision Makers:** Project Aura Platform Team
**Related:** ADR-005 (HITL Sandbox Architecture), ADR-030 (Chat Assistant Architecture), ADR-039 (Self-Service Test Environments)

---

## Executive Summary

This ADR documents the decision to implement a customer-facing Repository Onboarding UI Wizard that enables users to connect, configure, and onboard code repositories into the Aura GraphRAG system through a guided multi-step workflow.

**Key Outcomes:**
- 5-step wizard for repository connection (Connect, Select, Configure, Review, Complete)
- OAuth integration with GitHub and GitLab
- Secure credential storage via AWS Secrets Manager
- Real-time ingestion progress tracking
- Integration with existing GitIngestionService and GraphRAG pipeline

---

## Context

### Current State

Aura has a mature backend ingestion pipeline:
- `GitIngestionService` (`src/services/git_ingestion_service.py`) handles repository cloning, parsing, and indexing
- `GitHubAppAuth` (`src/services/github_app_auth.py`) manages GitHub App authentication for the platform
- Neptune (graph) + OpenSearch (vector) pipeline is operational
- Webhook handler supports incremental updates

However, there is **no customer-facing UI** for repository onboarding. Users cannot:
1. Connect their own repositories
2. Select which repositories to analyze
3. Configure analysis settings (branches, languages, scan frequency)
4. Monitor ingestion progress

### Problem Statement

1. **Onboarding Friction:** Without a UI wizard, repository setup requires direct API calls or support assistance
2. **OAuth Complexity:** GitHub/GitLab OAuth requires careful token handling and secure storage
3. **Configuration Visibility:** Users have no way to see their connected repositories or modify settings
4. **Progress Monitoring:** No real-time feedback during potentially long-running ingestion jobs

### Requirements

1. **Multi-Provider Support:** GitHub, GitLab, manual URL+token
2. **Secure Credential Storage:** OAuth tokens stored in Secrets Manager, never exposed to client
3. **Repository Selection:** List available repositories, support multi-select
4. **Configurable Analysis:** Branch selection, language filters, scan frequency
5. **Progress Tracking:** Real-time status during ingestion with WebSocket or polling
6. **Cancellation Support:** Allow users to cancel in-progress operations
7. **Error Recovery:** Clear error messages with retry options
8. **Existing Backend Integration:** Use GitIngestionService, not duplicate logic

---

## Decision

**Implement a 5-step Repository Onboarding Wizard with OAuth integration and secure backend credential management.**

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    REPOSITORY ONBOARDING ARCHITECTURE                        │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────────────────────┐
                    │   Frontend (React)               │
                    │   /repositories/onboard          │
                    │                                  │
                    │   ┌──────────────────────────┐   │
                    │   │ RepositoryOnboardWizard │   │
                    │   │ - Step 1: Connect       │   │
                    │   │ - Step 2: Select        │   │
                    │   │ - Step 3: Configure     │   │
                    │   │ - Step 4: Review        │   │
                    │   │ - Step 5: Complete      │   │
                    │   └──────────────┬───────────┘   │
                    └──────────────────┼───────────────┘
                                       │
                         ┌─────────────┴─────────────┐
                         │ REST API + WebSocket      │
                         ▼                           ▼
              ┌─────────────────────┐    ┌─────────────────────┐
              │ OAuth Flow         │    │ Repository API      │
              │ /oauth/github      │    │ /api/v1/repos       │
              │ /oauth/gitlab      │    │ /api/v1/repos/:id   │
              │ /oauth/callback    │    │ /api/v1/repos/ingest│
              └─────────┬───────────┘    └─────────┬───────────┘
                        │                          │
                        ▼                          ▼
              ┌───────────────────────────────────────────────┐
              │            RepositoryService                   │
              │  ┌───────────────┐  ┌───────────────────────┐ │
              │  │ OAuth Handler │  │ Repository Manager    │ │
              │  │ - Code→Token  │  │ - List repos          │ │
              │  │ - Token store │  │ - Configure analysis  │ │
              │  └───────┬───────┘  │ - Trigger ingestion   │ │
              │          │          └───────────┬───────────┘ │
              └──────────┼──────────────────────┼─────────────┘
                         │                      │
          ┌──────────────┴──────────────┐       │
          ▼                             ▼       ▼
┌─────────────────────┐     ┌─────────────────────────────────┐
│ AWS Secrets Manager │     │ GitIngestionService             │
│ /aura/repos/{id}/*  │     │ - Clone repository              │
│ - oauth_token       │     │ - Parse code (AST)              │
│ - refresh_token     │     │ - Index to Neptune              │
└─────────────────────┘     │ - Generate embeddings           │
                            │ - Index to OpenSearch           │
                            └─────────────────────────────────┘
```

### Step-by-Step Wizard Flow

#### Step 1: Connect Repository Provider

```
┌─────────────────────────────────────────────────────────────┐
│  Connect Your Repository                                      │
│                                                               │
│  Choose how you want to connect:                              │
│                                                               │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  │
│  │  [GitHub]      │  │   [GitLab]     │  │  Manual URL    │  │
│  │  OAuth Login   │  │   OAuth Login  │  │  + Token       │  │
│  └────────────────┘  └────────────────┘  └────────────────┘  │
│                                                               │
│  [ ] Remember this connection for future onboarding           │
└─────────────────────────────────────────────────────────────┘
```

**OAuth Flow:**
1. User clicks "GitHub" button
2. Frontend redirects to: `GET /api/v1/oauth/github/authorize?redirect_uri=...`
3. Backend returns GitHub OAuth URL with state parameter
4. User authenticates on GitHub
5. GitHub redirects to: `/api/v1/oauth/callback?code=...&state=...`
6. Backend exchanges code for token, stores in Secrets Manager
7. Backend returns session token to frontend
8. Frontend proceeds to Step 2

#### Step 2: Select Repositories

```
┌─────────────────────────────────────────────────────────────┐
│  Select Repositories to Analyze                              │
│                                                               │
│  [Search repositories...]                                     │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ [x] org/repo-1          main    Python, JS   2 days ago │ │
│  │ [x] org/repo-2          main    TypeScript   5 days ago │ │
│  │ [ ] org/private-repo    main    Go           1 week ago │ │
│  │ [ ] org/legacy-app      master  Java         2 months   │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  Selected: 2 repositories                                     │
│  Estimated ingestion time: ~5 minutes                         │
└─────────────────────────────────────────────────────────────┘
```

#### Step 3: Configure Analysis

```
┌─────────────────────────────────────────────────────────────┐
│  Configure Analysis Settings                                  │
│                                                               │
│  org/repo-1                                                   │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Branch: [main ▼]                                        │ │
│  │                                                          │ │
│  │ Languages to analyze:                                    │ │
│  │ [x] Python  [x] JavaScript  [x] TypeScript  [ ] Go      │ │
│  │                                                          │ │
│  │ Scan frequency: [On push (webhook) ▼]                   │ │
│  │                                                          │ │
│  │ Exclude patterns: (optional)                             │ │
│  │ [tests/*, docs/*, *.min.js                            ] │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  [ ] Apply same settings to all selected repositories         │
└─────────────────────────────────────────────────────────────┘
```

#### Step 4: Review & Start

```
┌─────────────────────────────────────────────────────────────┐
│  Review Your Configuration                                    │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Provider: GitHub (OAuth)                                 │ │
│  │ Account: @username                                       │ │
│  │                                                          │ │
│  │ Repositories:                                            │ │
│  │ • org/repo-1 (main) - Python, JavaScript                │ │
│  │ • org/repo-2 (main) - TypeScript                        │ │
│  │                                                          │ │
│  │ Scan: On push via webhook                                │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ⚠️ This will create webhooks in your repositories            │
│                                                               │
│  [Back]                           [Start Ingestion]          │
└─────────────────────────────────────────────────────────────┘
```

#### Step 5: Completion

```
┌─────────────────────────────────────────────────────────────┐
│  Ingestion Complete!                                          │
│                                                               │
│  ✓ org/repo-1                                                │
│    Files processed: 347                                       │
│    Code entities indexed: 1,234                               │
│    Embeddings generated: 892                                  │
│    Duration: 2m 34s                                           │
│                                                               │
│  ✓ org/repo-2                                                │
│    Files processed: 156                                       │
│    Code entities indexed: 567                                 │
│    Embeddings generated: 421                                  │
│    Duration: 1m 12s                                           │
│                                                               │
│  [View in Dashboard]              [Onboard More Repos]       │
└─────────────────────────────────────────────────────────────┘
```

### Component Architecture

#### Frontend Components

| Component | Path | Purpose |
|-----------|------|---------|
| `RepositoryOnboardWizard` | `frontend/src/components/repositories/RepositoryOnboardWizard.jsx` | Main wizard container with step navigation |
| `ConnectProviderStep` | `frontend/src/components/repositories/steps/ConnectProviderStep.jsx` | OAuth buttons and manual URL input |
| `SelectRepositoriesStep` | `frontend/src/components/repositories/steps/SelectRepositoriesStep.jsx` | Repository list with search and multi-select |
| `ConfigureAnalysisStep` | `frontend/src/components/repositories/steps/ConfigureAnalysisStep.jsx` | Per-repo settings (branch, languages, frequency) |
| `ReviewStep` | `frontend/src/components/repositories/steps/ReviewStep.jsx` | Summary before ingestion start |
| `CompletionStep` | `frontend/src/components/repositories/steps/CompletionStep.jsx` | Ingestion results and next steps |
| `IngestionProgress` | `frontend/src/components/repositories/IngestionProgress.jsx` | Real-time progress display |
| `RepositoryCard` | `frontend/src/components/repositories/RepositoryCard.jsx` | Repository list item with selection |
| `RepositoriesList` | `frontend/src/components/repositories/RepositoriesList.jsx` | List of connected repositories |

#### API Service

| File | Purpose |
|------|---------|
| `frontend/src/services/repositoryApi.js` | Client-side API wrapper for repository operations |

#### Context

| File | Purpose |
|------|---------|
| `frontend/src/context/RepositoryContext.jsx` | State management for wizard and repository data |

### Backend API Endpoints

#### OAuth Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/oauth/{provider}/authorize` | GET | Returns OAuth authorization URL |
| `/api/v1/oauth/callback` | GET | OAuth callback handler (exchanges code for token) |
| `/api/v1/oauth/connections` | GET | List user's OAuth connections |
| `/api/v1/oauth/connections/{id}` | DELETE | Revoke OAuth connection |

#### Repository Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/repositories` | GET | List user's connected repositories |
| `/api/v1/repositories` | POST | Add repository (manual URL+token) |
| `/api/v1/repositories/{id}` | GET | Get repository details |
| `/api/v1/repositories/{id}` | PUT | Update repository settings |
| `/api/v1/repositories/{id}` | DELETE | Remove repository |
| `/api/v1/repositories/available` | GET | List available repos from OAuth provider |
| `/api/v1/repositories/{id}/ingest` | POST | Trigger ingestion |
| `/api/v1/repositories/{id}/status` | GET | Get ingestion status |
| `/api/v1/repositories/{id}/webhook` | POST | Configure webhook for incremental updates |

### Backend Services

#### New: RepositoryOnboardService

```python
class RepositoryOnboardService:
    """Orchestrates repository onboarding workflow."""

    async def initiate_oauth(self, provider: str, user_id: str) -> str:
        """Generate OAuth authorization URL with state."""

    async def complete_oauth(self, provider: str, code: str, state: str) -> OAuthConnection:
        """Exchange code for token, store securely."""

    async def list_available_repositories(
        self, user_id: str, provider: str
    ) -> list[AvailableRepository]:
        """Fetch repositories from provider API using stored token."""

    async def onboard_repositories(
        self, user_id: str, repos: list[RepositoryConfig]
    ) -> list[OnboardingJob]:
        """Start ingestion for multiple repositories."""

    async def get_ingestion_status(
        self, user_id: str, job_ids: list[str]
    ) -> list[IngestionStatus]:
        """Get status of ongoing ingestion jobs."""
```

#### New: OAuthProviderService

```python
class OAuthProviderService:
    """Handles OAuth flows for GitHub, GitLab."""

    def get_authorization_url(self, provider: str, state: str) -> str:
        """Generate provider-specific OAuth URL."""

    async def exchange_code(self, provider: str, code: str) -> OAuthTokens:
        """Exchange authorization code for access token."""

    async def refresh_token(self, provider: str, refresh_token: str) -> OAuthTokens:
        """Refresh expired access token."""

    async def list_repositories(
        self, provider: str, access_token: str
    ) -> list[ProviderRepository]:
        """Fetch repositories from provider API."""
```

### Data Models

#### DynamoDB: Repository Table

```yaml
TableName: aura-repositories-{env}
KeySchema:
  - AttributeName: repository_id
    KeyType: HASH
GlobalSecondaryIndexes:
  - IndexName: user-index
    KeySchema:
      - AttributeName: user_id
        KeyType: HASH
      - AttributeName: created_at
        KeyType: RANGE
Attributes:
  - repository_id: S (ULID)
  - user_id: S
  - provider: S (github, gitlab, manual)
  - provider_repo_id: S
  - name: S (org/repo)
  - clone_url: S
  - default_branch: S
  - config: M
    - branch: S
    - languages: SS
    - scan_frequency: S (on_push, daily, weekly, manual)
    - exclude_patterns: SS
  - status: S (pending, active, error, archived)
  - last_ingestion_at: S
  - last_ingestion_job_id: S
  - webhook_id: S
  - created_at: S
  - updated_at: S
```

#### DynamoDB: OAuth Connections Table

```yaml
TableName: aura-oauth-connections-{env}
KeySchema:
  - AttributeName: connection_id
    KeyType: HASH
GlobalSecondaryIndexes:
  - IndexName: user-provider-index
    KeySchema:
      - AttributeName: user_id
        KeyType: HASH
      - AttributeName: provider
        KeyType: RANGE
Attributes:
  - connection_id: S (ULID)
  - user_id: S
  - provider: S (github, gitlab)
  - provider_user_id: S
  - provider_username: S
  - scopes: SS
  - secrets_arn: S  # Reference to Secrets Manager
  - status: S (active, revoked, expired)
  - created_at: S
  - expires_at: S
```

#### Secrets Manager Structure

```
/aura/{env}/oauth/{connection_id}
  - access_token: string
  - refresh_token: string (optional)
  - token_type: string
  - expires_at: string (ISO 8601)

/aura/{env}/repos/{repository_id}/token
  - token: string (for manual URL+token)
```

### Security Considerations

| Requirement | Implementation |
|-------------|----------------|
| **OAuth tokens never sent to client** | Tokens stored in Secrets Manager; frontend only receives session references |
| **State parameter for CSRF protection** | Server-generated state stored in DynamoDB with TTL |
| **Minimal OAuth scopes** | GitHub: `repo` (read), `admin:repo_hook` (webhook). GitLab: `read_repository`, `api` |
| **Token encryption at rest** | Secrets Manager with KMS customer-managed key |
| **Token refresh handling** | Backend automatically refreshes expired tokens |
| **User isolation** | Users can only access their own repositories via user_id filter |
| **Webhook signature validation** | Use existing GitHubWebhookHandler HMAC validation |
| **Rate limiting** | Apply existing API rate limiter to OAuth endpoints |

### OAuth Scope Requirements

#### GitHub
```
repo           - Full control of private repositories (for reading and webhooks)
admin:repo_hook - Write access to repository hooks
```

#### GitLab
```
read_repository - Read repository files
api             - Full API access (required for webhooks)
```

---

## Alternatives Considered

### Alternative 1: Platform-Level GitHub App Only (Rejected)

Use a single GitHub App installation for all customer repositories.

**Rejected because:**
- Customers may not want to install third-party Apps
- GitHub App installation requires organization admin approval
- Customer credentials should be isolated (not shared App)
- OAuth provides user-level consent and control

### Alternative 2: Single-Page Form Instead of Wizard (Rejected)

Present all configuration on a single page instead of multi-step wizard.

**Rejected because:**
- Overwhelming for new users
- OAuth flow naturally requires redirect (breaks single-page)
- Repository selection can involve 100+ repos (needs dedicated step)
- Wizard pattern matches existing IntegrationHub and Environments pages

### Alternative 3: Client-Side Token Storage (Rejected)

Store OAuth tokens in localStorage or IndexedDB on the client.

**Rejected because:**
- Security risk: XSS can expose tokens
- No token refresh capability without server
- Violates security best practices for OAuth
- CMMC compliance requires server-side credential storage

### Alternative 4: Background Ingestion Only (Considered, Partially Adopted)

Start ingestion immediately without progress UI; notify on completion.

**Partially adopted because:**
- Good for large repositories (long-running)
- Users want immediate feedback for initial onboarding
- Hybrid approach: Real-time progress for first ingestion, background for subsequent

---

## Consequences

### Positive

1. **Reduced Onboarding Friction:** Users can connect repos in <5 minutes
2. **Secure Credential Handling:** OAuth tokens never exposed to client
3. **Provider Flexibility:** GitHub, GitLab, manual URL all supported
4. **Reusable OAuth Pattern:** OAuth infrastructure can support future integrations
5. **Real-Time Feedback:** Users see ingestion progress immediately
6. **Incremental Updates:** Webhooks enable continuous synchronization

### Negative

1. **OAuth Complexity:** Multiple providers require provider-specific handling
2. **External Dependencies:** GitHub/GitLab API availability affects functionality
3. **Token Management:** Must handle token expiry, refresh, and revocation
4. **Webhook Reliability:** Webhook failures require retry/recovery logic

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| OAuth token theft | Low | Critical | Secrets Manager + KMS encryption; never expose to client |
| GitHub API rate limits | Medium | Medium | Implement caching; use conditional requests |
| Long-running ingestion timeout | Medium | Low | Background processing with status polling |
| Webhook delivery failures | Medium | Low | Idempotent processing; manual re-sync option |
| User abandons wizard mid-flow | Low | Low | Save progress; resume capability |

---

## Implementation

### Phase 1: Backend Foundation (Week 1-2)

| Task | Files | Effort |
|------|-------|--------|
| OAuth endpoint implementation | `src/api/oauth_endpoints.py` | 16h |
| OAuthProviderService (GitHub, GitLab) | `src/services/oauth_provider_service.py` | 16h |
| RepositoryOnboardService | `src/services/repository_onboard_service.py` | 12h |
| DynamoDB tables (repositories, oauth-connections) | `deploy/cloudformation/repository-tables.yaml` | 4h |
| Repository API endpoints | `src/api/repository_endpoints.py` | 12h |
| Unit tests | `tests/test_oauth_*.py`, `tests/test_repository_*.py` | 16h |

### Phase 2: Frontend Wizard (Week 2-3)

| Task | Files | Effort |
|------|-------|--------|
| RepositoryOnboardWizard container | `frontend/src/components/repositories/RepositoryOnboardWizard.jsx` | 8h |
| ConnectProviderStep | `frontend/src/components/repositories/steps/ConnectProviderStep.jsx` | 6h |
| SelectRepositoriesStep | `frontend/src/components/repositories/steps/SelectRepositoriesStep.jsx` | 8h |
| ConfigureAnalysisStep | `frontend/src/components/repositories/steps/ConfigureAnalysisStep.jsx` | 8h |
| ReviewStep | `frontend/src/components/repositories/steps/ReviewStep.jsx` | 4h |
| CompletionStep | `frontend/src/components/repositories/steps/CompletionStep.jsx` | 4h |
| RepositoryContext | `frontend/src/context/RepositoryContext.jsx` | 6h |
| repositoryApi service | `frontend/src/services/repositoryApi.js` | 6h |
| Integration tests | `frontend/src/components/repositories/__tests__/*` | 8h |

### Phase 3: Integration & Polish (Week 3-4)

| Task | Files | Effort |
|------|-------|--------|
| IngestionProgress component | `frontend/src/components/repositories/IngestionProgress.jsx` | 6h |
| WebSocket or polling for status | `frontend/src/hooks/useIngestionStatus.js` | 4h |
| RepositoriesList page | `frontend/src/components/repositories/RepositoriesList.jsx` | 8h |
| Route configuration | `frontend/src/App.jsx` | 2h |
| Sidebar navigation update | `frontend/src/components/CollapsibleSidebar.jsx` | 2h |
| Error handling and retry logic | Various | 6h |
| E2E tests | `tests/e2e/test_repository_onboarding.py` | 8h |

### Phase 4: Webhooks & Monitoring (Week 4-5)

| Task | Files | Effort |
|------|-------|--------|
| Webhook registration service | `src/services/webhook_registration_service.py` | 8h |
| Extend GitHubWebhookHandler for user repos | `src/api/webhook_handler.py` | 6h |
| CloudWatch dashboard for ingestion | `deploy/cloudformation/repository-monitoring.yaml` | 4h |
| SNS notifications for failures | `deploy/cloudformation/repository-alerts.yaml` | 4h |
| Documentation | `docs/user-guide/REPOSITORY_ONBOARDING.md` | 4h |

### CloudFormation Templates (New)

| Template | Layer | Purpose |
|----------|-------|---------|
| `repository-tables.yaml` | 2.6 | DynamoDB tables for repositories and OAuth connections |
| `repository-secrets.yaml` | 2.7 | Secrets Manager configuration for OAuth tokens |
| `repository-monitoring.yaml` | 5.7 | CloudWatch dashboards and alarms |
| `repository-alerts.yaml` | 5.8 | SNS topics for ingestion notifications |

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Time to first repository connected | < 3 minutes | CloudWatch metric |
| OAuth completion rate | > 90% | Funnel analytics |
| Wizard completion rate | > 80% | Funnel analytics |
| Ingestion success rate | > 95% | CloudWatch metric |
| User adoption | 100% of active users | Usage analytics |

---

## References

- ADR-005: HITL Sandbox Architecture
- ADR-030: Chat Assistant Architecture
- ADR-039: Self-Service Test Environments
- [GitHub OAuth Apps](https://docs.github.com/en/apps/oauth-apps)
- [GitLab OAuth](https://docs.gitlab.com/ee/api/oauth2.html)
- [AWS Secrets Manager Best Practices](https://docs.aws.amazon.com/secretsmanager/latest/userguide/best-practices.html)
- Existing: `src/services/git_ingestion_service.py`
- Existing: `src/services/github_app_auth.py`
- Existing: `src/api/webhook_handler.py`
