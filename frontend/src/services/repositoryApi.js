/**
 * Project Aura - Repository API Service
 *
 * Client-side service for repository onboarding and management.
 * Handles OAuth flows, repository CRUD, and ingestion operations.
 *
 * Part of ADR-043: Repository Onboarding Wizard
 */

// API base URL - uses Vite's environment variable or defaults to relative path
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

// Dev mode detection for mock data
const IS_DEV = import.meta.env.DEV || !import.meta.env.VITE_API_URL;

// ============================================================================
// Mock Data for Development
// ============================================================================

const MOCK_OAUTH_CONNECTIONS = [
  {
    connection_id: 'conn-gh-abc123',
    provider: 'github',
    status: 'active',
    username: 'aenealabs',
    display_name: 'Aenea Labs',
    avatar_url: 'https://avatars.githubusercontent.com/u/12345678',
    email: 'dev@aenealabs.com',
    scopes: ['repo', 'read:org', 'read:user'],
    created_at: '2025-11-15T10:30:00Z',
    last_used_at: '2025-12-30T14:22:00Z',
    repository_count: 8,
  },
  {
    connection_id: 'conn-gl-def456',
    provider: 'gitlab',
    status: 'active',
    username: 'aenea-labs',
    display_name: 'Aenea Labs',
    avatar_url: 'https://gitlab.com/uploads/-/system/user/avatar/12345/avatar.png',
    email: 'gitlab@aenealabs.com',
    scopes: ['read_api', 'read_repository'],
    created_at: '2025-12-01T09:00:00Z',
    last_used_at: '2025-12-28T16:45:00Z',
    repository_count: 3,
  },
];

const MOCK_REPOSITORIES = [
  {
    repository_id: 'repo-001-aura-platform',
    name: 'aura-platform',
    clone_url: 'https://github.com/aenealabs/aura-platform.git',
    status: 'active',
    provider: 'github',
    branch: 'main',
    languages: ['python', 'typescript', 'javascript'],
    scan_frequency: 'on_push',
    exclude_patterns: ['node_modules/', 'venv/', 'dist/', '__pycache__/'],
    enable_webhook: true,
    connection_id: 'conn-gh-abc123',
    last_scan_at: '2025-12-30T08:15:00Z',
    last_scan_status: 'completed',
    files_indexed: 1847,
    entities_discovered: 4521,
    vulnerabilities_found: 3,
    created_at: '2025-11-20T14:30:00Z',
  },
  {
    repository_id: 'repo-002-api-gateway',
    name: 'api-gateway',
    clone_url: 'https://github.com/aenealabs/api-gateway.git',
    status: 'syncing',
    provider: 'github',
    branch: 'develop',
    languages: ['go', 'python'],
    scan_frequency: 'daily',
    exclude_patterns: ['vendor/', 'testdata/'],
    enable_webhook: true,
    connection_id: 'conn-gh-abc123',
    last_scan_at: '2025-12-29T22:00:00Z',
    last_scan_status: 'in_progress',
    files_indexed: 342,
    entities_discovered: 876,
    vulnerabilities_found: 0,
    created_at: '2025-11-25T10:00:00Z',
  },
  {
    repository_id: 'repo-003-ml-models',
    name: 'ml-models',
    clone_url: 'https://github.com/aenealabs/ml-models.git',
    status: 'active',
    provider: 'github',
    branch: 'main',
    languages: ['python'],
    scan_frequency: 'weekly',
    exclude_patterns: ['data/', 'checkpoints/', '*.pkl'],
    enable_webhook: false,
    connection_id: 'conn-gh-abc123',
    last_scan_at: '2025-12-28T03:00:00Z',
    last_scan_status: 'completed',
    files_indexed: 156,
    entities_discovered: 423,
    vulnerabilities_found: 1,
    created_at: '2025-12-05T16:20:00Z',
  },
  {
    repository_id: 'repo-004-frontend-ui',
    name: 'frontend-ui',
    clone_url: 'https://github.com/aenealabs/frontend-ui.git',
    status: 'error',
    provider: 'github',
    branch: 'main',
    languages: ['typescript', 'javascript'],
    scan_frequency: 'on_push',
    exclude_patterns: ['node_modules/', 'build/', '.next/'],
    enable_webhook: true,
    connection_id: 'conn-gh-abc123',
    last_scan_at: '2025-12-30T06:30:00Z',
    last_scan_status: 'failed',
    last_error: 'Failed to parse TypeScript configuration',
    files_indexed: 0,
    entities_discovered: 0,
    vulnerabilities_found: 0,
    created_at: '2025-12-10T11:45:00Z',
  },
  {
    repository_id: 'repo-005-infra-terraform',
    name: 'infra-terraform',
    clone_url: 'https://gitlab.com/aenea-labs/infra-terraform.git',
    status: 'active',
    provider: 'gitlab',
    branch: 'main',
    languages: ['python'],
    scan_frequency: 'manual',
    exclude_patterns: ['.terraform/', '*.tfstate'],
    enable_webhook: false,
    connection_id: 'conn-gl-def456',
    last_scan_at: '2025-12-20T09:00:00Z',
    last_scan_status: 'completed',
    files_indexed: 89,
    entities_discovered: 0,
    vulnerabilities_found: 0,
    created_at: '2025-12-01T09:30:00Z',
  },
  {
    repository_id: 'repo-006-security-scanner',
    name: 'security-scanner',
    clone_url: 'https://github.com/aenealabs/security-scanner.git',
    status: 'pending',
    provider: 'github',
    branch: 'main',
    languages: ['rust', 'python'],
    scan_frequency: 'on_push',
    exclude_patterns: ['target/', 'test_fixtures/'],
    enable_webhook: true,
    connection_id: 'conn-gh-abc123',
    last_scan_at: null,
    last_scan_status: null,
    files_indexed: 0,
    entities_discovered: 0,
    vulnerabilities_found: 0,
    created_at: '2025-12-30T12:00:00Z',
  },
];

/**
 * Custom error class for Repository API errors
 */
export class RepositoryApiError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.name = 'RepositoryApiError';
    this.status = status;
    this.details = details;
  }
}

/**
 * Generic fetch wrapper with error handling
 */
async function fetchApi(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;

  const defaultHeaders = {
    'Content-Type': 'application/json',
  };

  const response = await fetch(url, {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new RepositoryApiError(
      errorData.detail || errorData.error || `API error: ${response.status}`,
      response.status,
      errorData
    );
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return null;
  }

  return response.json();
}

// ============================================================================
// OAuth Operations
// ============================================================================

/**
 * Initiate OAuth flow for a provider
 *
 * @param {string} provider - OAuth provider (github, gitlab)
 * @returns {Promise<{authorizationUrl: string, state: string}>}
 */
export async function initiateOAuth(provider) {
  return fetchApi(`/oauth/${provider}/authorize`);
}

/**
 * Complete OAuth flow with callback parameters
 *
 * @param {string} provider - OAuth provider
 * @param {string} code - Authorization code from provider
 * @param {string} state - CSRF state token
 * @returns {Promise<{connectionId: string, status: string}>}
 */
export async function completeOAuth(provider, code, state) {
  return fetchApi(`/oauth/callback?provider=${provider}&code=${code}&state=${state}`);
}

/**
 * List user's OAuth connections
 *
 * @param {string} [provider] - Filter by provider (optional)
 * @returns {Promise<Array>} List of OAuth connections
 */
export async function listOAuthConnections(provider = null) {
  try {
    const params = provider ? `?provider=${provider}` : '';
    return await fetchApi(`/oauth/connections${params}`);
  } catch (error) {
    // Return mock data in dev mode, empty array otherwise
    if (IS_DEV) {
      console.info('Using mock OAuth connections (dev mode)');
      const connections = provider
        ? MOCK_OAUTH_CONNECTIONS.filter((c) => c.provider === provider)
        : MOCK_OAUTH_CONNECTIONS;
      return connections;
    }
    console.warn('Using empty connections list (API unavailable)');
    return [];
  }
}

/**
 * Get a specific OAuth connection
 *
 * @param {string} connectionId - Connection ID
 * @returns {Promise<Object>} Connection details
 */
export async function getOAuthConnection(connectionId) {
  return fetchApi(`/oauth/connections/${connectionId}`);
}

/**
 * Revoke an OAuth connection
 *
 * @param {string} connectionId - Connection ID to revoke
 * @returns {Promise<{status: string}>}
 */
export async function revokeOAuthConnection(connectionId) {
  return fetchApi(`/oauth/connections/${connectionId}`, {
    method: 'DELETE',
  });
}

/**
 * List repositories from an OAuth connection
 *
 * @param {string} connectionId - Connection ID
 * @param {number} [page=1] - Page number
 * @param {number} [perPage=30] - Items per page
 * @returns {Promise<Array>} List of repositories
 */
export async function listConnectionRepositories(connectionId, page = 1, perPage = 30) {
  return fetchApi(`/oauth/connections/${connectionId}/repos?page=${page}&per_page=${perPage}`);
}

// ============================================================================
// Repository Operations
// ============================================================================

/**
 * List user's connected repositories
 *
 * @param {Object} [filters] - Optional filters
 * @param {string} [filters.status] - Filter by status
 * @param {string} [filters.provider] - Filter by provider
 * @returns {Promise<Array>} List of repositories
 */
export async function listRepositories(filters = {}) {
  try {
    const params = new URLSearchParams();
    if (filters.status) params.append('status', filters.status);
    if (filters.provider) params.append('provider', filters.provider);
    const queryString = params.toString();
    return await fetchApi(`/repositories${queryString ? `?${queryString}` : ''}`);
  } catch (error) {
    // Return mock data in dev mode, empty array otherwise
    if (IS_DEV) {
      console.info('Using mock repositories (dev mode)');
      let repos = [...MOCK_REPOSITORIES];
      if (filters.status) {
        repos = repos.filter((r) => r.status === filters.status);
      }
      if (filters.provider) {
        repos = repos.filter((r) => r.provider === filters.provider);
      }
      return repos;
    }
    console.warn('Using empty repositories list (API unavailable)');
    return [];
  }
}

/**
 * List available repositories from OAuth provider
 *
 * @param {string} connectionId - OAuth connection ID
 * @returns {Promise<{repositories: Array, total: number}>}
 */
export async function listAvailableRepositories(connectionId) {
  return fetchApi(`/repositories/available?connection_id=${connectionId}`);
}

/**
 * Get a specific repository
 *
 * @param {string} repositoryId - Repository ID
 * @returns {Promise<Object>} Repository details
 */
export async function getRepository(repositoryId) {
  return fetchApi(`/repositories/${repositoryId}`);
}

/**
 * Add a repository (via OAuth or manual URL+token)
 *
 * @param {Object} config - Repository configuration
 * @param {string} [config.connectionId] - OAuth connection ID
 * @param {string} [config.providerRepoId] - Provider repository ID
 * @param {string} [config.cloneUrl] - Clone URL for manual entry
 * @param {string} [config.token] - PAT for manual entry
 * @param {string} config.name - Repository display name
 * @param {string} [config.branch='main'] - Default branch
 * @param {string[]} [config.languages] - Languages to parse
 * @param {string} [config.scanFrequency='on_push'] - Scan frequency
 * @param {string[]} [config.excludePatterns] - Patterns to exclude
 * @param {boolean} [config.enableWebhook=true] - Enable webhook
 * @returns {Promise<Object>} Created repository
 */
export async function addRepository(config) {
  // Convert camelCase to snake_case for API
  const payload = {
    connection_id: config.connectionId,
    provider_repo_id: config.providerRepoId,
    clone_url: config.cloneUrl,
    token: config.token,
    name: config.name,
    branch: config.branch || 'main',
    languages: config.languages || ['python', 'javascript', 'typescript'],
    scan_frequency: config.scanFrequency || 'on_push',
    exclude_patterns: config.excludePatterns || [],
    enable_webhook: config.enableWebhook !== false,
  };

  return fetchApi('/repositories', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

/**
 * Update repository settings
 *
 * @param {string} repositoryId - Repository ID
 * @param {Object} config - Updated configuration
 * @returns {Promise<Object>} Updated repository
 */
export async function updateRepository(repositoryId, config) {
  const payload = {
    connection_id: config.connectionId,
    provider_repo_id: config.providerRepoId,
    clone_url: config.cloneUrl,
    token: config.token,
    name: config.name,
    branch: config.branch,
    languages: config.languages,
    scan_frequency: config.scanFrequency,
    exclude_patterns: config.excludePatterns,
    enable_webhook: config.enableWebhook,
  };

  return fetchApi(`/repositories/${repositoryId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

/**
 * Delete a repository
 *
 * @param {string} repositoryId - Repository ID
 * @param {boolean} [deleteData=true] - Also delete indexed data
 * @returns {Promise<{status: string}>}
 */
export async function deleteRepository(repositoryId, deleteData = true) {
  return fetchApi(`/repositories/${repositoryId}?delete_data=${deleteData}`, {
    method: 'DELETE',
  });
}

/**
 * Trigger manual sync for a repository
 *
 * @param {string} repositoryId - Repository ID
 * @returns {Promise<{status: string, jobId: string}>}
 */
export async function triggerSync(repositoryId) {
  return fetchApi(`/repositories/${repositoryId}/sync`, {
    method: 'POST',
  });
}

// ============================================================================
// Ingestion Operations
// ============================================================================

/**
 * Start ingestion for multiple repositories
 *
 * @param {Array<Object>} repositoryConfigs - Array of repository configurations
 * @returns {Promise<{jobs: Array, message: string}>}
 */
export async function startIngestion(repositoryConfigs) {
  // Convert configs to API format
  const repositories = repositoryConfigs.map((config) => ({
    connection_id: config.connectionId,
    provider_repo_id: config.providerRepoId,
    clone_url: config.cloneUrl,
    token: config.token,
    name: config.name,
    branch: config.branch || 'main',
    languages: config.languages || ['python', 'javascript', 'typescript'],
    scan_frequency: config.scanFrequency || 'on_push',
    exclude_patterns: config.excludePatterns || [],
    enable_webhook: config.enableWebhook !== false,
  }));

  return fetchApi('/repositories/ingest', {
    method: 'POST',
    body: JSON.stringify({ repositories }),
  });
}

/**
 * Get ingestion status for jobs
 *
 * @param {string[]} jobIds - Array of job IDs
 * @returns {Promise<Array>} Array of job statuses
 */
export async function getIngestionStatus(jobIds) {
  const ids = jobIds.join(',');
  return fetchApi(`/repositories/ingestion-status?job_ids=${ids}`);
}

/**
 * Cancel an in-progress ingestion job
 *
 * @param {string} jobId - Job ID to cancel
 * @returns {Promise<{status: string}>}
 */
export async function cancelIngestion(jobId) {
  return fetchApi(`/repositories/ingestion/${jobId}/cancel`, {
    method: 'POST',
  });
}

// ============================================================================
// Constants
// ============================================================================

/**
 * Supported OAuth providers
 */
export const OAuthProviders = {
  GITHUB: 'github',
  GITLAB: 'gitlab',
};

/**
 * Repository status options
 */
export const RepositoryStatus = {
  PENDING: 'pending',
  ACTIVE: 'active',
  SYNCING: 'syncing',
  ERROR: 'error',
};

/**
 * Ingestion job status options
 */
export const IngestionStatus = {
  QUEUED: 'queued',
  CLONING: 'cloning',
  PARSING: 'parsing',
  INDEXING_GRAPH: 'indexing_graph',
  INDEXING_VECTORS: 'indexing_vectors',
  COMPLETED: 'completed',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
};

/**
 * Scan frequency options
 */
export const ScanFrequency = {
  ON_PUSH: 'on_push',
  DAILY: 'daily',
  WEEKLY: 'weekly',
  MANUAL: 'manual',
};

/**
 * Default repository configuration
 */
export const DEFAULT_REPOSITORY_CONFIG = {
  branch: 'main',
  languages: ['python', 'javascript', 'typescript', 'java', 'go', 'rust'],
  scanFrequency: ScanFrequency.ON_PUSH,
  excludePatterns: ['node_modules/', 'venv/', '*.min.js', 'dist/', 'build/', '__pycache__/'],
  enableWebhook: true,
};

/**
 * Language display information
 */
export const LanguageInfo = {
  python: { name: 'Python', icon: 'py', color: '#3776AB' },
  javascript: { name: 'JavaScript', icon: 'js', color: '#F7DF1E' },
  typescript: { name: 'TypeScript', icon: 'ts', color: '#3178C6' },
  java: { name: 'Java', icon: 'java', color: '#B07219' },
  go: { name: 'Go', icon: 'go', color: '#00ADD8' },
  rust: { name: 'Rust', icon: 'rs', color: '#DEA584' },
  csharp: { name: 'C#', icon: 'cs', color: '#178600' },
  cpp: { name: 'C++', icon: 'cpp', color: '#00599C' },
  ruby: { name: 'Ruby', icon: 'rb', color: '#CC342D' },
  php: { name: 'PHP', icon: 'php', color: '#777BB4' },
};

// Default export with all functions
export default {
  // OAuth
  initiateOAuth,
  completeOAuth,
  listOAuthConnections,
  getOAuthConnection,
  revokeOAuthConnection,
  listConnectionRepositories,
  // Repositories
  listRepositories,
  listAvailableRepositories,
  getRepository,
  addRepository,
  updateRepository,
  deleteRepository,
  triggerSync,
  // Ingestion
  startIngestion,
  getIngestionStatus,
  cancelIngestion,
  // Constants
  OAuthProviders,
  RepositoryStatus,
  IngestionStatus,
  ScanFrequency,
  DEFAULT_REPOSITORY_CONFIG,
  LanguageInfo,
};
