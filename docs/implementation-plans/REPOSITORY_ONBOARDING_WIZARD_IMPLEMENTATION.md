# Repository Onboarding UI Wizard - Implementation Plan

**Related ADR:** ADR-043
**Date:** 2025-12-17
**Status:** Ready for Implementation

---

## Overview

This document provides the detailed implementation plan for the Repository Onboarding UI Wizard feature. It follows the architecture defined in ADR-043 and aligns with existing Project Aura patterns.

---

## 1. New React Components

### Directory Structure

```
frontend/src/
├── components/
│   └── repositories/
│       ├── index.js                           # Barrel export
│       ├── RepositoryOnboardWizard.jsx        # Main wizard container
│       ├── RepositoriesList.jsx               # List of connected repos
│       ├── RepositoryCard.jsx                 # Individual repo display
│       ├── IngestionProgress.jsx              # Real-time progress
│       ├── steps/
│       │   ├── index.js
│       │   ├── ConnectProviderStep.jsx        # Step 1: OAuth/manual
│       │   ├── SelectRepositoriesStep.jsx     # Step 2: Repo selection
│       │   ├── ConfigureAnalysisStep.jsx      # Step 3: Settings
│       │   ├── ReviewStep.jsx                 # Step 4: Summary
│       │   └── CompletionStep.jsx             # Step 5: Results
│       └── __tests__/
│           ├── RepositoryOnboardWizard.test.jsx
│           └── steps/*.test.jsx
├── context/
│   └── RepositoryContext.jsx                  # Wizard state management
├── hooks/
│   └── useIngestionStatus.js                  # Polling/WebSocket hook
└── services/
    └── repositoryApi.js                       # API client
```

### Component Details

#### 1.1 RepositoryOnboardWizard.jsx
**Path:** `/path/to/project-aura/frontend/src/components/repositories/RepositoryOnboardWizard.jsx`

**Purpose:** Main wizard container managing step navigation and state

**Props:**
```jsx
{
  onComplete: (repositories) => void,  // Called when wizard completes
  onCancel: () => void,                 // Called on cancel
  initialProvider?: 'github' | 'gitlab' | 'manual'  // Pre-select provider
}
```

**State (via RepositoryContext):**
```javascript
{
  currentStep: number,           // 1-5
  provider: string | null,       // 'github', 'gitlab', 'manual'
  connection: OAuthConnection | null,
  availableRepos: Repository[],
  selectedRepos: string[],       // repository IDs
  repoConfigs: Map<string, RepoConfig>,
  ingestionJobs: IngestionJob[],
  isLoading: boolean,
  error: string | null
}
```

**Features:**
- Step indicator with progress (matches IntegrationHub wizard pattern)
- Back/Next navigation with validation
- Keyboard shortcuts (Enter to proceed, Escape to go back)
- Error boundary with retry

**Effort:** 8 hours

---

#### 1.2 ConnectProviderStep.jsx
**Path:** `/path/to/project-aura/frontend/src/components/repositories/steps/ConnectProviderStep.jsx`

**Purpose:** OAuth provider selection and connection

**UI Elements:**
- Three provider cards (GitHub, GitLab, Manual URL)
- OAuth loading state during redirect
- Existing connection indicator
- "Remember connection" checkbox

**OAuth Flow:**
```javascript
const handleGitHubConnect = async () => {
  setIsLoading(true);
  try {
    const { authorizationUrl, state } = await repositoryApi.initiateOAuth('github');
    // Store state in sessionStorage for callback validation
    sessionStorage.setItem('oauth_state', state);
    // Redirect to GitHub
    window.location.href = authorizationUrl;
  } catch (error) {
    setError('Failed to initiate GitHub connection');
  }
};
```

**Manual URL Form:**
```jsx
<div className="space-y-4">
  <input
    type="url"
    placeholder="https://github.com/org/repo.git"
    value={manualUrl}
    onChange={e => setManualUrl(e.target.value)}
    className="w-full px-4 py-2 border rounded-lg..."
  />
  <input
    type="password"
    placeholder="Personal Access Token"
    value={manualToken}
    onChange={e => setManualToken(e.target.value)}
    className="w-full px-4 py-2 border rounded-lg..."
  />
</div>
```

**Effort:** 6 hours

---

#### 1.3 SelectRepositoriesStep.jsx
**Path:** `/path/to/project-aura/frontend/src/components/repositories/steps/SelectRepositoriesStep.jsx`

**Purpose:** Repository list with search and multi-select

**Features:**
- Search/filter repositories
- Sort by name, last updated, language
- Multi-select with checkbox
- Repository metadata display (language, size, last push)
- Pagination for large repo lists (>50)
- Already-connected indicator
- Estimated ingestion time

**API Call:**
```javascript
useEffect(() => {
  const fetchRepos = async () => {
    if (!connection) return;
    setIsLoading(true);
    try {
      const repos = await repositoryApi.listAvailableRepositories(connection.id);
      setAvailableRepos(repos);
    } catch (error) {
      setError('Failed to fetch repositories');
    } finally {
      setIsLoading(false);
    }
  };
  fetchRepos();
}, [connection]);
```

**Effort:** 8 hours

---

#### 1.4 ConfigureAnalysisStep.jsx
**Path:** `/path/to/project-aura/frontend/src/components/repositories/steps/ConfigureAnalysisStep.jsx`

**Purpose:** Per-repository analysis configuration

**Configuration Options:**
```javascript
const defaultConfig = {
  branch: 'main',
  languages: ['python', 'javascript', 'typescript', 'java', 'go', 'rust'],
  scanFrequency: 'on_push',  // on_push, daily, weekly, manual
  excludePatterns: ['node_modules/', 'venv/', '*.min.js', 'dist/'],
  maxFileSize: 500,  // KB
  enableWebhook: true
};
```

**UI:**
- Accordion or tab for each selected repository
- "Apply to all" checkbox
- Language checkboxes with icons
- Branch dropdown (fetched from API)
- Scan frequency dropdown
- Exclude patterns text area with suggestions

**Effort:** 8 hours

---

#### 1.5 ReviewStep.jsx
**Path:** `/path/to/project-aura/frontend/src/components/repositories/steps/ReviewStep.jsx`

**Purpose:** Summary before starting ingestion

**Display:**
- Provider and account info
- List of repositories with configurations
- Estimated total ingestion time
- Estimated storage impact
- Warning about webhook creation
- Confirmation checkbox

**Effort:** 4 hours

---

#### 1.6 CompletionStep.jsx
**Path:** `/path/to/project-aura/frontend/src/components/repositories/steps/CompletionStep.jsx`

**Purpose:** Ingestion results and next steps

**Features:**
- Success/failure status per repository
- Ingestion statistics (files, entities, embeddings)
- Duration display
- Error details with retry button
- "View in Dashboard" button
- "Onboard More Repos" button

**Effort:** 4 hours

---

#### 1.7 IngestionProgress.jsx
**Path:** `/path/to/project-aura/frontend/src/components/repositories/IngestionProgress.jsx`

**Purpose:** Real-time ingestion progress display

**Features:**
- Progress bar per repository
- Status stages: Cloning -> Parsing -> Indexing Graph -> Indexing Vectors -> Complete
- Files processed counter
- Elapsed time
- Cancel button
- Error display with retry

**Implementation:**
```javascript
const useIngestionProgress = (jobIds) => {
  const [progress, setProgress] = useState({});

  useEffect(() => {
    const pollInterval = setInterval(async () => {
      const statuses = await repositoryApi.getIngestionStatus(jobIds);
      setProgress(statuses);

      // Stop polling when all complete
      if (statuses.every(s => s.status === 'completed' || s.status === 'failed')) {
        clearInterval(pollInterval);
      }
    }, 2000);  // Poll every 2 seconds

    return () => clearInterval(pollInterval);
  }, [jobIds]);

  return progress;
};
```

**Effort:** 6 hours

---

#### 1.8 RepositoriesList.jsx
**Path:** `/path/to/project-aura/frontend/src/components/repositories/RepositoriesList.jsx`

**Purpose:** List view of connected repositories (main page, not wizard)

**Features:**
- Grid/list toggle view
- Search and filter
- Status badges (active, error, syncing)
- Last sync time
- Quick actions (re-sync, edit, delete)
- "Add Repository" button

**Effort:** 8 hours

---

#### 1.9 RepositoryCard.jsx
**Path:** `/path/to/project-aura/frontend/src/components/repositories/RepositoryCard.jsx`

**Purpose:** Individual repository card for list display

**Props:**
```jsx
{
  repository: Repository,
  onEdit: (id) => void,
  onDelete: (id) => void,
  onSync: (id) => void,
  selected?: boolean,
  onSelect?: (id) => void
}
```

**Display:**
- Repository name and org
- Provider icon (GitHub/GitLab)
- Language badges
- Status indicator
- Last sync time
- File/entity counts
- Actions dropdown

**Effort:** 4 hours

---

### 1.10 RepositoryContext.jsx
**Path:** `/path/to/project-aura/frontend/src/context/RepositoryContext.jsx`

**Purpose:** State management for wizard and repository operations

**Pattern:** Follows existing `AuthContext.jsx` and `ChatContext.jsx` patterns

```javascript
const RepositoryContext = createContext(null);

export const RepositoryProvider = ({ children }) => {
  // Wizard state
  const [wizardState, setWizardState] = useState({
    currentStep: 1,
    provider: null,
    connection: null,
    availableRepos: [],
    selectedRepos: [],
    repoConfigs: new Map(),
    ingestionJobs: []
  });

  // Repository list state
  const [repositories, setRepositories] = useState([]);
  const [connections, setConnections] = useState([]);

  // Actions
  const setStep = (step) => setWizardState(s => ({ ...s, currentStep: step }));
  const selectProvider = (provider) => setWizardState(s => ({ ...s, provider }));
  const setConnection = (connection) => setWizardState(s => ({ ...s, connection }));
  const toggleRepoSelection = (repoId) => { /* ... */ };
  const updateRepoConfig = (repoId, config) => { /* ... */ };
  const startIngestion = async () => { /* ... */ };
  const resetWizard = () => { /* ... */ };

  // Load repositories on mount
  useEffect(() => {
    const loadRepositories = async () => {
      const repos = await repositoryApi.listRepositories();
      setRepositories(repos);
    };
    loadRepositories();
  }, []);

  return (
    <RepositoryContext.Provider value={{
      ...wizardState,
      repositories,
      connections,
      setStep,
      selectProvider,
      setConnection,
      toggleRepoSelection,
      updateRepoConfig,
      startIngestion,
      resetWizard
    }}>
      {children}
    </RepositoryContext.Provider>
  );
};

export const useRepositories = () => {
  const context = useContext(RepositoryContext);
  if (!context) {
    throw new Error('useRepositories must be used within RepositoryProvider');
  }
  return context;
};
```

**Effort:** 6 hours

---

### 1.11 repositoryApi.js
**Path:** `/path/to/project-aura/frontend/src/services/repositoryApi.js`

**Purpose:** API client for repository operations

```javascript
/**
 * Project Aura - Repository API Service
 * Client-side service for repository onboarding and management.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

export class RepositoryApiError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.name = 'RepositoryApiError';
    this.status = status;
    this.details = details;
  }
}

async function fetchApi(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new RepositoryApiError(
      errorData.detail || `API error: ${response.status}`,
      response.status,
      errorData
    );
  }

  if (response.status === 204) return null;
  return response.json();
}

// OAuth Operations
export async function initiateOAuth(provider) {
  return fetchApi(`/oauth/${provider}/authorize`, { method: 'GET' });
}

export async function completeOAuth(provider, code, state) {
  return fetchApi(`/oauth/callback?provider=${provider}&code=${code}&state=${state}`);
}

export async function listOAuthConnections() {
  return fetchApi('/oauth/connections');
}

export async function revokeOAuthConnection(connectionId) {
  return fetchApi(`/oauth/connections/${connectionId}`, { method: 'DELETE' });
}

// Repository Operations
export async function listRepositories() {
  return fetchApi('/repositories');
}

export async function listAvailableRepositories(connectionId) {
  return fetchApi(`/repositories/available?connection_id=${connectionId}`);
}

export async function getRepository(repositoryId) {
  return fetchApi(`/repositories/${repositoryId}`);
}

export async function addRepository(data) {
  return fetchApi('/repositories', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateRepository(repositoryId, data) {
  return fetchApi(`/repositories/${repositoryId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteRepository(repositoryId) {
  return fetchApi(`/repositories/${repositoryId}`, { method: 'DELETE' });
}

// Ingestion Operations
export async function startIngestion(repositoryConfigs) {
  return fetchApi('/repositories/ingest', {
    method: 'POST',
    body: JSON.stringify({ repositories: repositoryConfigs }),
  });
}

export async function getIngestionStatus(jobIds) {
  const ids = jobIds.join(',');
  return fetchApi(`/repositories/ingestion-status?job_ids=${ids}`);
}

export async function cancelIngestion(jobId) {
  return fetchApi(`/repositories/ingestion/${jobId}/cancel`, { method: 'POST' });
}

// Default export
export default {
  initiateOAuth,
  completeOAuth,
  listOAuthConnections,
  revokeOAuthConnection,
  listRepositories,
  listAvailableRepositories,
  getRepository,
  addRepository,
  updateRepository,
  deleteRepository,
  startIngestion,
  getIngestionStatus,
  cancelIngestion,
};
```

**Effort:** 6 hours

---

## 2. New/Modified API Endpoints

### 2.1 OAuth Endpoints (New)
**Path:** `/path/to/project-aura/src/api/oauth_endpoints.py`

```python
"""
Project Aura - OAuth API Endpoints
Handles OAuth flows for GitHub and GitLab.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional
from src.services.oauth_provider_service import OAuthProviderService
from src.api.auth import get_current_user

router = APIRouter(prefix="/oauth", tags=["oauth"])

class OAuthInitiateResponse(BaseModel):
    authorization_url: str
    state: str

class OAuthConnection(BaseModel):
    connection_id: str
    provider: str
    provider_username: str
    scopes: list[str]
    status: str
    created_at: str

@router.get("/{provider}/authorize", response_model=OAuthInitiateResponse)
async def initiate_oauth(
    provider: str,
    user = Depends(get_current_user),
    oauth_service: OAuthProviderService = Depends()
):
    """Initiate OAuth flow for a provider."""
    if provider not in ["github", "gitlab"]:
        raise HTTPException(400, "Unsupported provider")

    auth_url, state = await oauth_service.initiate_oauth(provider, user.id)
    return OAuthInitiateResponse(authorization_url=auth_url, state=state)

@router.get("/callback")
async def oauth_callback(
    code: str,
    state: str,
    provider: str = Query(...),
    oauth_service: OAuthProviderService = Depends()
):
    """Handle OAuth callback from provider."""
    connection = await oauth_service.complete_oauth(provider, code, state)
    return {"connection_id": connection.connection_id, "status": "connected"}

@router.get("/connections", response_model=list[OAuthConnection])
async def list_connections(
    user = Depends(get_current_user),
    oauth_service: OAuthProviderService = Depends()
):
    """List user's OAuth connections."""
    return await oauth_service.list_connections(user.id)

@router.delete("/connections/{connection_id}")
async def revoke_connection(
    connection_id: str,
    user = Depends(get_current_user),
    oauth_service: OAuthProviderService = Depends()
):
    """Revoke an OAuth connection."""
    await oauth_service.revoke_connection(user.id, connection_id)
    return {"status": "revoked"}
```

**Effort:** 16 hours (including service)

---

### 2.2 Repository Endpoints (New)
**Path:** `/path/to/project-aura/src/api/repository_endpoints.py`

```python
"""
Project Aura - Repository Management API Endpoints
Handles repository CRUD and ingestion operations.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional
from src.services.repository_onboard_service import RepositoryOnboardService
from src.api.auth import get_current_user

router = APIRouter(prefix="/repositories", tags=["repositories"])

class RepositoryConfig(BaseModel):
    repository_id: Optional[str] = None
    connection_id: Optional[str] = None
    clone_url: Optional[str] = None  # For manual URL
    token: Optional[str] = None  # For manual token
    name: str
    branch: str = "main"
    languages: list[str] = ["python", "javascript", "typescript"]
    scan_frequency: str = "on_push"
    exclude_patterns: list[str] = []
    enable_webhook: bool = True

class IngestionRequest(BaseModel):
    repositories: list[RepositoryConfig]

class Repository(BaseModel):
    repository_id: str
    name: str
    provider: str
    clone_url: str
    branch: str
    languages: list[str]
    scan_frequency: str
    status: str
    last_ingestion_at: Optional[str]
    file_count: int
    entity_count: int

@router.get("", response_model=list[Repository])
async def list_repositories(
    user = Depends(get_current_user),
    repo_service: RepositoryOnboardService = Depends()
):
    """List user's connected repositories."""
    return await repo_service.list_repositories(user.id)

@router.get("/available")
async def list_available_repositories(
    connection_id: str,
    user = Depends(get_current_user),
    repo_service: RepositoryOnboardService = Depends()
):
    """List available repositories from OAuth provider."""
    return await repo_service.list_available_repositories(user.id, connection_id)

@router.post("")
async def add_repository(
    config: RepositoryConfig,
    user = Depends(get_current_user),
    repo_service: RepositoryOnboardService = Depends()
):
    """Add a repository (manual URL+token)."""
    return await repo_service.add_repository(user.id, config)

@router.get("/{repository_id}")
async def get_repository(
    repository_id: str,
    user = Depends(get_current_user),
    repo_service: RepositoryOnboardService = Depends()
):
    """Get repository details."""
    repo = await repo_service.get_repository(user.id, repository_id)
    if not repo:
        raise HTTPException(404, "Repository not found")
    return repo

@router.put("/{repository_id}")
async def update_repository(
    repository_id: str,
    config: RepositoryConfig,
    user = Depends(get_current_user),
    repo_service: RepositoryOnboardService = Depends()
):
    """Update repository settings."""
    return await repo_service.update_repository(user.id, repository_id, config)

@router.delete("/{repository_id}")
async def delete_repository(
    repository_id: str,
    user = Depends(get_current_user),
    repo_service: RepositoryOnboardService = Depends()
):
    """Remove a repository."""
    await repo_service.delete_repository(user.id, repository_id)
    return {"status": "deleted"}

@router.post("/ingest")
async def start_ingestion(
    request: IngestionRequest,
    user = Depends(get_current_user),
    repo_service: RepositoryOnboardService = Depends()
):
    """Start ingestion for multiple repositories."""
    jobs = await repo_service.start_ingestion(user.id, request.repositories)
    return {"jobs": jobs}

@router.get("/ingestion-status")
async def get_ingestion_status(
    job_ids: str = Query(..., description="Comma-separated job IDs"),
    user = Depends(get_current_user),
    repo_service: RepositoryOnboardService = Depends()
):
    """Get ingestion status for jobs."""
    ids = job_ids.split(",")
    return await repo_service.get_ingestion_status(user.id, ids)

@router.post("/ingestion/{job_id}/cancel")
async def cancel_ingestion(
    job_id: str,
    user = Depends(get_current_user),
    repo_service: RepositoryOnboardService = Depends()
):
    """Cancel an in-progress ingestion job."""
    await repo_service.cancel_ingestion(user.id, job_id)
    return {"status": "cancelled"}
```

**Effort:** 12 hours

---

## 3. Backend Service Changes

### 3.1 OAuthProviderService (New)
**Path:** `/path/to/project-aura/src/services/oauth_provider_service.py`

**Purpose:** Handle OAuth flows for GitHub and GitLab

**Key Methods:**
- `initiate_oauth(provider, user_id)` - Generate authorization URL with state
- `complete_oauth(provider, code, state)` - Exchange code for token, store in Secrets Manager
- `list_connections(user_id)` - List user's OAuth connections
- `revoke_connection(user_id, connection_id)` - Delete connection and revoke token
- `refresh_token(connection_id)` - Refresh expired tokens
- `get_access_token(connection_id)` - Get valid token (refreshing if needed)

**Dependencies:**
- boto3 (Secrets Manager, DynamoDB)
- requests (GitHub/GitLab API)
- ulid (ID generation)

**Effort:** 16 hours

---

### 3.2 RepositoryOnboardService (New)
**Path:** `/path/to/project-aura/src/services/repository_onboard_service.py`

**Purpose:** Orchestrate repository onboarding workflow

**Key Methods:**
- `list_repositories(user_id)` - Get user's repositories from DynamoDB
- `list_available_repositories(user_id, connection_id)` - Fetch repos from provider
- `add_repository(user_id, config)` - Add manual URL+token repository
- `get_repository(user_id, repository_id)` - Get repository details
- `update_repository(user_id, repository_id, config)` - Update settings
- `delete_repository(user_id, repository_id)` - Remove repository
- `start_ingestion(user_id, repositories)` - Trigger GitIngestionService
- `get_ingestion_status(user_id, job_ids)` - Get job statuses
- `cancel_ingestion(user_id, job_id)` - Cancel job

**Integration with GitIngestionService:**
```python
async def start_ingestion(self, user_id: str, repositories: list[RepositoryConfig]) -> list[dict]:
    jobs = []
    for repo_config in repositories:
        # Get token from Secrets Manager
        token = await self._get_repository_token(repo_config)

        # Call existing GitIngestionService
        result = await self.git_ingestion_service.ingest_repository(
            repository_url=repo_config.clone_url,
            branch=repo_config.branch,
            github_token=token,
            shallow=True
        )

        # Store job reference
        await self._store_ingestion_job(user_id, repo_config.repository_id, result.job_id)

        jobs.append({
            "repository_id": repo_config.repository_id,
            "job_id": result.job_id,
            "status": "started"
        })

    return jobs
```

**Effort:** 12 hours

---

### 3.3 WebhookRegistrationService (New)
**Path:** `/path/to/project-aura/src/services/webhook_registration_service.py`

**Purpose:** Register webhooks on customer repositories

**Key Methods:**
- `register_webhook(repository_id, provider, repo_url, access_token)` - Create webhook
- `update_webhook(repository_id, webhook_id, events)` - Modify webhook events
- `delete_webhook(repository_id)` - Remove webhook
- `verify_webhook(repository_id)` - Check webhook is working

**GitHub Webhook Registration:**
```python
async def register_github_webhook(
    self,
    repo_full_name: str,
    access_token: str,
    callback_url: str
) -> str:
    """Register a GitHub webhook for push events."""
    url = f"https://api.github.com/repos/{repo_full_name}/hooks"

    # Generate webhook secret
    webhook_secret = secrets.token_hex(32)

    payload = {
        "name": "web",
        "active": True,
        "events": ["push", "pull_request"],
        "config": {
            "url": callback_url,
            "content_type": "json",
            "secret": webhook_secret,
            "insecure_ssl": "0"
        }
    }

    response = requests.post(
        url,
        json=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json"
        }
    )
    response.raise_for_status()

    webhook_data = response.json()

    # Store webhook secret in Secrets Manager
    await self._store_webhook_secret(repo_full_name, webhook_secret)

    return webhook_data["id"]
```

**Effort:** 8 hours

---

### 3.4 Modify webhook_handler.py
**Path:** `/path/to/project-aura/src/api/webhook_handler.py`

**Changes:**
1. Support multiple webhook secrets (one per repository)
2. Look up repository by webhook event
3. Validate signature against repository-specific secret
4. Route to correct ingestion job

**Effort:** 6 hours

---

## 4. State Management Approach

### Frontend State Architecture

```
RepositoryProvider (Context)
├── wizardState
│   ├── currentStep: number
│   ├── provider: string | null
│   ├── connection: OAuthConnection | null
│   ├── availableRepos: Repository[]
│   ├── selectedRepos: string[]
│   ├── repoConfigs: Map<string, RepoConfig>
│   └── ingestionJobs: IngestionJob[]
│
├── repositories: Repository[]  (user's connected repos)
├── connections: OAuthConnection[]  (user's OAuth connections)
│
├── loading: boolean
├── error: string | null
│
└── Actions
    ├── setStep(step)
    ├── selectProvider(provider)
    ├── setConnection(connection)
    ├── toggleRepoSelection(repoId)
    ├── selectAllRepos()
    ├── deselectAllRepos()
    ├── updateRepoConfig(repoId, config)
    ├── applyConfigToAll(config)
    ├── startIngestion()
    ├── resetWizard()
    ├── refreshRepositories()
    └── refreshConnections()
```

### State Persistence

- Wizard state is **not** persisted (lost on refresh)
- OAuth state parameter stored in `sessionStorage` (cleared after callback)
- Completed repositories stored in backend DynamoDB

---

## 5. OAuth Integration Requirements

### GitHub OAuth App Setup

1. **Create OAuth App:**
   - GitHub Settings > Developer Settings > OAuth Apps > New OAuth App
   - Application name: "Aura Code Intelligence"
   - Homepage URL: `https://app.aenealabs.com`
   - Authorization callback URL: `https://api.aenealabs.com/api/v1/oauth/callback`

2. **Required Scopes:**
   - `repo` - Full access to private repositories
   - `admin:repo_hook` - Write access to repository hooks

3. **Environment Variables:**
   ```
   GITHUB_OAUTH_CLIENT_ID=<client-id>
   GITHUB_OAUTH_CLIENT_SECRET=<client-secret> (stored in Secrets Manager)
   ```

### GitLab OAuth App Setup

1. **Create Application:**
   - GitLab Settings > Applications > New Application
   - Name: "Aura Code Intelligence"
   - Redirect URI: `https://api.aenealabs.com/api/v1/oauth/callback`
   - Scopes: `read_repository`, `api`

2. **Environment Variables:**
   ```
   GITLAB_OAUTH_CLIENT_ID=<application-id>
   GITLAB_OAUTH_CLIENT_SECRET=<secret> (stored in Secrets Manager)
   ```

### SSM Parameters (New)

```
/aura/{env}/oauth/github/client-id
/aura/{env}/oauth/github/client-secret (SecureString)
/aura/{env}/oauth/gitlab/client-id
/aura/{env}/oauth/gitlab/client-secret (SecureString)
```

---

## 6. Security Considerations

| Concern | Mitigation |
|---------|------------|
| **OAuth token exposure** | Tokens never sent to client; stored in Secrets Manager |
| **CSRF in OAuth flow** | State parameter generated server-side, stored in DynamoDB with TTL |
| **Token theft from Secrets Manager** | KMS encryption with customer-managed key |
| **Webhook signature bypass** | HMAC-SHA256 validation using per-repo secrets |
| **User isolation** | All queries filtered by user_id; partition key includes user_id |
| **Excessive permissions** | Minimal OAuth scopes; repository-level token scoping |
| **Token refresh attacks** | Refresh tokens stored server-side only |
| **Rate limiting** | Apply existing API rate limiter to OAuth endpoints |

### IAM Permissions (New Lambda/ECS Task)

```yaml
Policies:
  - PolicyName: SecretsManagerAccess
    PolicyDocument:
      Statement:
        - Effect: Allow
          Action:
            - secretsmanager:CreateSecret
            - secretsmanager:GetSecretValue
            - secretsmanager:PutSecretValue
            - secretsmanager:DeleteSecret
          Resource:
            - !Sub 'arn:${AWS::Partition}:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:/aura/${Environment}/oauth/*'
            - !Sub 'arn:${AWS::Partition}:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:/aura/${Environment}/repos/*'

  - PolicyName: DynamoDBAccess
    PolicyDocument:
      Statement:
        - Effect: Allow
          Action:
            - dynamodb:GetItem
            - dynamodb:PutItem
            - dynamodb:UpdateItem
            - dynamodb:DeleteItem
            - dynamodb:Query
          Resource:
            - !Sub 'arn:${AWS::Partition}:dynamodb:${AWS::Region}:${AWS::AccountId}:table/aura-repositories-${Environment}'
            - !Sub 'arn:${AWS::Partition}:dynamodb:${AWS::Region}:${AWS::AccountId}:table/aura-repositories-${Environment}/index/*'
            - !Sub 'arn:${AWS::Partition}:dynamodb:${AWS::Region}:${AWS::AccountId}:table/aura-oauth-connections-${Environment}'
            - !Sub 'arn:${AWS::Partition}:dynamodb:${AWS::Region}:${AWS::AccountId}:table/aura-oauth-connections-${Environment}/index/*'
```

---

## 7. Testing Requirements

### Unit Tests

| Test File | Coverage |
|-----------|----------|
| `tests/test_oauth_provider_service.py` | OAuth flow, token exchange, refresh |
| `tests/test_repository_onboard_service.py` | Repository CRUD, ingestion orchestration |
| `tests/test_webhook_registration_service.py` | Webhook create/delete, signature |
| `tests/test_oauth_endpoints.py` | API endpoint validation |
| `tests/test_repository_endpoints.py` | API endpoint validation |

### Integration Tests

| Test File | Coverage |
|-----------|----------|
| `tests/integration/test_oauth_flow.py` | End-to-end OAuth (mocked provider) |
| `tests/integration/test_ingestion_flow.py` | Repository -> Ingestion -> GraphRAG |

### Frontend Tests

| Test File | Coverage |
|-----------|----------|
| `frontend/src/components/repositories/__tests__/RepositoryOnboardWizard.test.jsx` | Wizard navigation, validation |
| `frontend/src/components/repositories/__tests__/steps/*.test.jsx` | Individual step components |
| `frontend/src/services/__tests__/repositoryApi.test.js` | API client |

### E2E Tests

| Test File | Coverage |
|-----------|----------|
| `tests/e2e/test_repository_onboarding.py` | Full wizard flow with Playwright/Selenium |

**Total New Tests:** ~80-100 tests

---

## 8. Estimated Effort Summary

| Component | Effort (hours) |
|-----------|----------------|
| **Backend** | |
| OAuth Endpoints + Service | 32 |
| Repository Endpoints + Service | 24 |
| Webhook Registration Service | 8 |
| DynamoDB Tables (CloudFormation) | 4 |
| Secrets Manager Config | 4 |
| Unit Tests (Backend) | 16 |
| **Frontend** | |
| Wizard Container | 8 |
| Step Components (5) | 30 |
| Context + API Service | 12 |
| Progress Component | 6 |
| Repositories List Page | 12 |
| Frontend Tests | 8 |
| **Integration** | |
| Route Configuration | 2 |
| Integration Tests | 8 |
| E2E Tests | 8 |
| **Infrastructure** | |
| CloudFormation Templates | 8 |
| Monitoring/Alerts | 4 |
| Documentation | 4 |
| **Total** | **198 hours** |

### Timeline Estimate

- **Phase 1 (Backend):** 2 weeks
- **Phase 2 (Frontend Wizard):** 1.5 weeks
- **Phase 3 (Integration):** 1 week
- **Phase 4 (Polish/Testing):** 1 week

**Total:** 5-6 weeks with 1 developer

---

## 9. File Paths Summary

### New Files

| File | Type |
|------|------|
| `/path/to/project-aura/frontend/src/components/repositories/index.js` | Frontend |
| `/path/to/project-aura/frontend/src/components/repositories/RepositoryOnboardWizard.jsx` | Frontend |
| `/path/to/project-aura/frontend/src/components/repositories/RepositoriesList.jsx` | Frontend |
| `/path/to/project-aura/frontend/src/components/repositories/RepositoryCard.jsx` | Frontend |
| `/path/to/project-aura/frontend/src/components/repositories/IngestionProgress.jsx` | Frontend |
| `/path/to/project-aura/frontend/src/components/repositories/steps/index.js` | Frontend |
| `/path/to/project-aura/frontend/src/components/repositories/steps/ConnectProviderStep.jsx` | Frontend |
| `/path/to/project-aura/frontend/src/components/repositories/steps/SelectRepositoriesStep.jsx` | Frontend |
| `/path/to/project-aura/frontend/src/components/repositories/steps/ConfigureAnalysisStep.jsx` | Frontend |
| `/path/to/project-aura/frontend/src/components/repositories/steps/ReviewStep.jsx` | Frontend |
| `/path/to/project-aura/frontend/src/components/repositories/steps/CompletionStep.jsx` | Frontend |
| `/path/to/project-aura/frontend/src/context/RepositoryContext.jsx` | Frontend |
| `/path/to/project-aura/frontend/src/hooks/useIngestionStatus.js` | Frontend |
| `/path/to/project-aura/frontend/src/services/repositoryApi.js` | Frontend |
| `/path/to/project-aura/src/api/oauth_endpoints.py` | Backend |
| `/path/to/project-aura/src/api/repository_endpoints.py` | Backend |
| `/path/to/project-aura/src/services/oauth_provider_service.py` | Backend |
| `/path/to/project-aura/src/services/repository_onboard_service.py` | Backend |
| `/path/to/project-aura/src/services/webhook_registration_service.py` | Backend |
| `/path/to/project-aura/deploy/cloudformation/repository-tables.yaml` | Infrastructure |
| `/path/to/project-aura/deploy/cloudformation/repository-secrets.yaml` | Infrastructure |
| `/path/to/project-aura/deploy/cloudformation/repository-monitoring.yaml` | Infrastructure |

### Modified Files

| File | Changes |
|------|---------|
| `/path/to/project-aura/frontend/src/App.jsx` | Add routes for /repositories |
| `/path/to/project-aura/frontend/src/components/CollapsibleSidebar.jsx` | Add Repositories nav item |
| `/path/to/project-aura/src/api/main.py` | Include new routers |
| `/path/to/project-aura/src/api/webhook_handler.py` | Multi-repository webhook support |
| `/path/to/project-aura/src/services/git_ingestion_service.py` | Accept user-provided tokens |
| `/path/to/project-aura/deploy/buildspecs/buildspec-data.yml` | Deploy new tables |

---

## References

- ADR-043: Repository Onboarding Wizard
- Existing: `frontend/src/components/IntegrationHub.jsx` (wizard pattern)
- Existing: `frontend/src/components/Environments.jsx` (list + modal pattern)
- Existing: `frontend/src/context/AuthContext.jsx` (context pattern)
- Existing: `src/services/git_ingestion_service.py` (ingestion backend)
- Existing: `src/services/github_app_auth.py` (GitHub auth pattern)
