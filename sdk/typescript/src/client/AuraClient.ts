/**
 * Aura TypeScript SDK - Main Client
 *
 * The primary client for interacting with the Aura API.
 *
 * @example
 * ```typescript
 * import { AuraClient } from '@aenealabs/aura-sdk';
 *
 * const client = new AuraClient({
 *   baseUrl: 'https://api.aura.example.com',
 *   apiKey: 'your-api-key',
 * });
 *
 * // Scan a file
 * const result = await client.extension.scanFile({
 *   file_path: 'src/app.ts',
 *   file_content: 'const x = eval(input);',
 *   language: 'typescript',
 * });
 * ```
 */

import type {
  ExtensionConfig,
  ScanRequest,
  ScanResponse,
  Finding,
  FindingsResponse,
  FindingsListResponse,
  PatchRequest,
  Patch,
  PatchResponse,
  ApplyPatchRequest,
  ApplyPatchResponse,
  ApprovalSummary,
  ApprovalDetail,
  ApprovalListResponse,
  ApprovalStats,
  ApprovalActionResponse,
  ApprovalStatusResponse,
  IncidentSummary,
  IncidentDetail,
  IncidentListResponse,
  PlatformSettings,
  IntegrationModeResponse,
  HITLSettings,
  MCPSettings,
  ExternalToolInfo,
  MCPUsageResponse,
  ConnectionTestResponse,
  APIError,
  Severity,
  FindingCategory,
  ApprovalStatus,
  ApprovalType,
  IntegrationMode,
  FindingsFilterParams,
  ApprovalsFilterParams,
  IncidentsFilterParams,
} from '../types';

// ============================================================================
// Configuration
// ============================================================================

/**
 * Configuration options for the Aura client
 */
export interface AuraClientConfig {
  /** Base URL of the Aura API server */
  baseUrl: string;
  /** API key for authentication */
  apiKey?: string;
  /** JWT token for authentication */
  jwtToken?: string;
  /** Request timeout in milliseconds */
  timeout?: number;
  /** Custom headers to include in all requests */
  headers?: Record<string, string>;
  /** Enable debug logging */
  debug?: boolean;
}

/**
 * Request options for individual API calls
 */
export interface RequestOptions {
  /** Custom headers for this request */
  headers?: Record<string, string>;
  /** Signal for aborting the request */
  signal?: AbortSignal;
  /** Request timeout override */
  timeout?: number;
}

// ============================================================================
// Error Classes
// ============================================================================

/**
 * Base error class for Aura API errors
 */
export class AuraAPIError extends Error {
  constructor(
    message: string,
    public readonly statusCode: number,
    public readonly errorCode?: string,
    public readonly details?: unknown
  ) {
    super(message);
    this.name = 'AuraAPIError';
  }
}

/**
 * Error thrown when authentication fails
 */
export class AuthenticationError extends AuraAPIError {
  constructor(message: string = 'Authentication failed') {
    super(message, 401, 'AUTH_FAILED');
    this.name = 'AuthenticationError';
  }
}

/**
 * Error thrown when resource is not found
 */
export class NotFoundError extends AuraAPIError {
  constructor(resource: string, id: string) {
    super(`${resource} not found: ${id}`, 404, 'NOT_FOUND');
    this.name = 'NotFoundError';
  }
}

/**
 * Error thrown when validation fails
 */
export class ValidationError extends AuraAPIError {
  constructor(message: string, public readonly errors: unknown[]) {
    super(message, 422, 'VALIDATION_ERROR', errors);
    this.name = 'ValidationError';
  }
}

// ============================================================================
// HTTP Client
// ============================================================================

/**
 * Internal HTTP client for making API requests
 */
class HttpClient {
  private baseUrl: string;
  private defaultHeaders: Record<string, string>;
  private timeout: number;
  private debug: boolean;

  constructor(config: AuraClientConfig) {
    this.baseUrl = config.baseUrl.replace(/\/$/, '');
    this.timeout = config.timeout ?? 30000;
    this.debug = config.debug ?? false;

    this.defaultHeaders = {
      'Content-Type': 'application/json',
      ...config.headers,
    };

    if (config.apiKey) {
      this.defaultHeaders['X-API-Key'] = config.apiKey;
    }
    if (config.jwtToken) {
      this.defaultHeaders['Authorization'] = `Bearer ${config.jwtToken}`;
    }
  }

  /**
   * Update the JWT token for authentication
   */
  setJwtToken(token: string): void {
    this.defaultHeaders['Authorization'] = `Bearer ${token}`;
  }

  /**
   * Update the API key for authentication
   */
  setApiKey(apiKey: string): void {
    this.defaultHeaders['X-API-Key'] = apiKey;
  }

  /**
   * Make an HTTP request
   */
  async request<T>(
    method: string,
    path: string,
    body?: unknown,
    options?: RequestOptions
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const timeout = options?.timeout ?? this.timeout;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    const headers = {
      ...this.defaultHeaders,
      ...options?.headers,
    };

    if (this.debug) {
      console.log(`[Aura SDK] ${method} ${url}`);
      if (body) console.log('[Aura SDK] Body:', JSON.stringify(body, null, 2));
    }

    try {
      const response = await fetch(url, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
        signal: options?.signal ?? controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const error = await this.parseError(response);
        throw error;
      }

      const data = await response.json();

      if (this.debug) {
        console.log('[Aura SDK] Response:', JSON.stringify(data, null, 2));
      }

      return data as T;
    } catch (error) {
      clearTimeout(timeoutId);

      if (error instanceof AuraAPIError) {
        throw error;
      }

      if (error instanceof Error && error.name === 'AbortError') {
        throw new AuraAPIError('Request timeout', 408, 'TIMEOUT');
      }

      throw new AuraAPIError(
        error instanceof Error ? error.message : 'Unknown error',
        0,
        'NETWORK_ERROR'
      );
    }
  }

  private async parseError(response: Response): Promise<AuraAPIError> {
    try {
      const data = await response.json();
      const message = data.detail || data.message || 'API error';

      if (response.status === 401) {
        return new AuthenticationError(message);
      }
      if (response.status === 404) {
        return new NotFoundError('Resource', 'unknown');
      }
      if (response.status === 422) {
        return new ValidationError(message, data.detail || []);
      }

      return new AuraAPIError(message, response.status, data.error_code);
    } catch {
      return new AuraAPIError(
        `HTTP ${response.status}: ${response.statusText}`,
        response.status
      );
    }
  }

  get<T>(path: string, options?: RequestOptions): Promise<T> {
    return this.request<T>('GET', path, undefined, options);
  }

  post<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>('POST', path, body, options);
  }

  put<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>('PUT', path, body, options);
  }

  delete<T>(path: string, options?: RequestOptions): Promise<T> {
    return this.request<T>('DELETE', path, undefined, options);
  }
}

// ============================================================================
// API Modules
// ============================================================================

/**
 * Extension API - VS Code extension endpoints
 */
export class ExtensionAPI {
  constructor(private http: HttpClient) {}

  /**
   * Get extension configuration from server
   */
  async getConfig(options?: RequestOptions): Promise<ExtensionConfig> {
    return this.http.get<ExtensionConfig>('/api/v1/extension/config', options);
  }

  /**
   * Scan a file for vulnerabilities
   */
  async scanFile(
    request: ScanRequest,
    options?: RequestOptions
  ): Promise<ScanResponse> {
    return this.http.post<ScanResponse>('/api/v1/extension/scan', request, options);
  }

  /**
   * Get findings for a specific file
   */
  async getFindings(
    filePath: string,
    options?: RequestOptions
  ): Promise<FindingsResponse> {
    const encodedPath = encodeURIComponent(filePath);
    return this.http.get<FindingsResponse>(
      `/api/v1/extension/findings/${encodedPath}`,
      options
    );
  }

  /**
   * List all findings with optional filters
   */
  async listFindings(
    params?: FindingsFilterParams,
    options?: RequestOptions
  ): Promise<FindingsListResponse> {
    const query = this.buildQueryString(params);
    return this.http.get<FindingsListResponse>(
      `/api/v1/extension/findings${query}`,
      options
    );
  }

  /**
   * Generate a patch for a finding
   */
  async generatePatch(
    request: PatchRequest,
    options?: RequestOptions
  ): Promise<PatchResponse> {
    return this.http.post<PatchResponse>(
      '/api/v1/extension/patches',
      request,
      options
    );
  }

  /**
   * Get patch details
   */
  async getPatch(patchId: string, options?: RequestOptions): Promise<Patch> {
    return this.http.get<Patch>(`/api/v1/extension/patches/${patchId}`, options);
  }

  /**
   * Apply an approved patch
   */
  async applyPatch(
    patchId: string,
    confirm: boolean = true,
    options?: RequestOptions
  ): Promise<ApplyPatchResponse> {
    return this.http.post<ApplyPatchResponse>(
      `/api/v1/extension/patches/${patchId}/apply`,
      { patch_id: patchId, confirm },
      options
    );
  }

  /**
   * Get approval status for a patch
   */
  async getApprovalStatus(
    approvalId: string,
    options?: RequestOptions
  ): Promise<ApprovalStatusResponse> {
    return this.http.get<ApprovalStatusResponse>(
      `/api/v1/extension/approvals/${approvalId}`,
      options
    );
  }

  private buildQueryString(params?: Record<string, unknown>): string {
    if (!params) return '';
    const entries = Object.entries(params).filter(
      ([, value]) => value !== undefined && value !== null
    );
    if (entries.length === 0) return '';
    return '?' + entries.map(([key, value]) => `${key}=${encodeURIComponent(String(value))}`).join('&');
  }
}

/**
 * Approvals API - HITL approval workflow
 */
export class ApprovalsAPI {
  constructor(private http: HttpClient) {}

  /**
   * List approval requests
   */
  async list(
    params?: ApprovalsFilterParams,
    options?: RequestOptions
  ): Promise<ApprovalListResponse> {
    const query = this.buildQueryString(params);
    return this.http.get<ApprovalListResponse>(`/api/v1/approvals${query}`, options);
  }

  /**
   * Get approval statistics
   */
  async getStats(options?: RequestOptions): Promise<ApprovalStats> {
    return this.http.get<ApprovalStats>('/api/v1/approvals/stats', options);
  }

  /**
   * Get approval details
   */
  async get(approvalId: string, options?: RequestOptions): Promise<ApprovalDetail> {
    return this.http.get<ApprovalDetail>(`/api/v1/approvals/${approvalId}`, options);
  }

  /**
   * Approve an approval request
   */
  async approve(
    approvalId: string,
    comments?: string,
    options?: RequestOptions
  ): Promise<ApprovalActionResponse> {
    return this.http.post<ApprovalActionResponse>(
      `/api/v1/approvals/${approvalId}/approve`,
      { comments },
      options
    );
  }

  /**
   * Reject an approval request
   */
  async reject(
    approvalId: string,
    reason: string,
    options?: RequestOptions
  ): Promise<ApprovalActionResponse> {
    return this.http.post<ApprovalActionResponse>(
      `/api/v1/approvals/${approvalId}/reject`,
      { reason },
      options
    );
  }

  /**
   * Cancel an approval request
   */
  async cancel(
    approvalId: string,
    reason?: string,
    options?: RequestOptions
  ): Promise<ApprovalActionResponse> {
    return this.http.post<ApprovalActionResponse>(
      `/api/v1/approvals/${approvalId}/cancel`,
      { reason },
      options
    );
  }

  private buildQueryString(params?: Record<string, unknown>): string {
    if (!params) return '';
    const entries = Object.entries(params).filter(
      ([, value]) => value !== undefined && value !== null
    );
    if (entries.length === 0) return '';
    return '?' + entries.map(([key, value]) => `${key}=${encodeURIComponent(String(value))}`).join('&');
  }
}

/**
 * Incidents API - Security incident management
 */
export class IncidentsAPI {
  constructor(private http: HttpClient) {}

  /**
   * List incidents
   */
  async list(
    params?: IncidentsFilterParams,
    options?: RequestOptions
  ): Promise<IncidentListResponse> {
    const query = this.buildQueryString(params);
    return this.http.get<IncidentListResponse>(`/api/v1/incidents${query}`, options);
  }

  /**
   * Get incident details
   */
  async get(incidentId: string, options?: RequestOptions): Promise<IncidentDetail> {
    return this.http.get<IncidentDetail>(`/api/v1/incidents/${incidentId}`, options);
  }

  /**
   * Acknowledge an incident
   */
  async acknowledge(
    incidentId: string,
    options?: RequestOptions
  ): Promise<IncidentDetail> {
    return this.http.post<IncidentDetail>(
      `/api/v1/incidents/${incidentId}/acknowledge`,
      {},
      options
    );
  }

  /**
   * Resolve an incident
   */
  async resolve(
    incidentId: string,
    rootCause: string,
    remediation: string[],
    options?: RequestOptions
  ): Promise<IncidentDetail> {
    return this.http.post<IncidentDetail>(
      `/api/v1/incidents/${incidentId}/resolve`,
      { root_cause: rootCause, remediation_steps: remediation },
      options
    );
  }

  private buildQueryString(params?: Record<string, unknown>): string {
    if (!params) return '';
    const entries = Object.entries(params).filter(
      ([, value]) => value !== undefined && value !== null
    );
    if (entries.length === 0) return '';
    return '?' + entries.map(([key, value]) => `${key}=${encodeURIComponent(String(value))}`).join('&');
  }
}

/**
 * Settings API - Platform configuration
 */
export class SettingsAPI {
  constructor(private http: HttpClient) {}

  /**
   * Get platform settings
   */
  async get(options?: RequestOptions): Promise<PlatformSettings> {
    return this.http.get<PlatformSettings>('/api/v1/settings', options);
  }

  /**
   * Update platform settings
   */
  async update(
    settings: Partial<PlatformSettings>,
    options?: RequestOptions
  ): Promise<PlatformSettings> {
    return this.http.put<PlatformSettings>('/api/v1/settings', settings, options);
  }

  /**
   * Get integration mode
   */
  async getIntegrationMode(
    options?: RequestOptions
  ): Promise<IntegrationModeResponse> {
    return this.http.get<IntegrationModeResponse>(
      '/api/v1/settings/integration-mode',
      options
    );
  }

  /**
   * Set integration mode
   */
  async setIntegrationMode(
    mode: IntegrationMode,
    options?: RequestOptions
  ): Promise<IntegrationModeResponse> {
    return this.http.put<IntegrationModeResponse>(
      '/api/v1/settings/integration-mode',
      { mode },
      options
    );
  }

  /**
   * Get HITL settings
   */
  async getHITLSettings(options?: RequestOptions): Promise<HITLSettings> {
    return this.http.get<HITLSettings>('/api/v1/settings/hitl', options);
  }

  /**
   * Update HITL settings
   */
  async updateHITLSettings(
    settings: Partial<HITLSettings>,
    options?: RequestOptions
  ): Promise<HITLSettings> {
    return this.http.put<HITLSettings>('/api/v1/settings/hitl', settings, options);
  }

  /**
   * Get MCP settings
   */
  async getMCPSettings(options?: RequestOptions): Promise<MCPSettings> {
    return this.http.get<MCPSettings>('/api/v1/settings/mcp', options);
  }

  /**
   * Update MCP settings
   */
  async updateMCPSettings(
    settings: Partial<MCPSettings>,
    options?: RequestOptions
  ): Promise<MCPSettings> {
    return this.http.put<MCPSettings>('/api/v1/settings/mcp', settings, options);
  }

  /**
   * Get available MCP tools
   */
  async getMCPTools(options?: RequestOptions): Promise<ExternalToolInfo[]> {
    return this.http.get<ExternalToolInfo[]>('/api/v1/settings/mcp/tools', options);
  }

  /**
   * Test MCP connection
   */
  async testMCPConnection(
    gatewayUrl: string,
    options?: RequestOptions
  ): Promise<ConnectionTestResponse> {
    return this.http.post<ConnectionTestResponse>(
      '/api/v1/settings/mcp/test-connection',
      { gateway_url: gatewayUrl },
      options
    );
  }

  /**
   * Get MCP usage statistics
   */
  async getMCPUsage(options?: RequestOptions): Promise<MCPUsageResponse> {
    return this.http.get<MCPUsageResponse>('/api/v1/settings/mcp/usage', options);
  }
}

// ============================================================================
// Main Client
// ============================================================================

/**
 * Main Aura API client
 *
 * @example
 * ```typescript
 * const client = new AuraClient({
 *   baseUrl: 'https://api.aura.example.com',
 *   apiKey: 'your-api-key',
 * });
 *
 * // Use extension API
 * const findings = await client.extension.listFindings({ severity: 'critical' });
 *
 * // Use approvals API
 * const approvals = await client.approvals.list({ status: 'pending' });
 *
 * // Use settings API
 * const settings = await client.settings.get();
 * ```
 */
export class AuraClient {
  private http: HttpClient;

  /** Extension API - vulnerability scanning and patches */
  public readonly extension: ExtensionAPI;

  /** Approvals API - HITL workflow */
  public readonly approvals: ApprovalsAPI;

  /** Incidents API - security incident management */
  public readonly incidents: IncidentsAPI;

  /** Settings API - platform configuration */
  public readonly settings: SettingsAPI;

  constructor(config: AuraClientConfig) {
    this.http = new HttpClient(config);
    this.extension = new ExtensionAPI(this.http);
    this.approvals = new ApprovalsAPI(this.http);
    this.incidents = new IncidentsAPI(this.http);
    this.settings = new SettingsAPI(this.http);
  }

  /**
   * Update the JWT token for authentication
   */
  setJwtToken(token: string): void {
    this.http.setJwtToken(token);
  }

  /**
   * Update the API key for authentication
   */
  setApiKey(apiKey: string): void {
    this.http.setApiKey(apiKey);
  }

  /**
   * Check API health
   */
  async healthCheck(): Promise<boolean> {
    try {
      await this.http.get('/health');
      return true;
    } catch {
      return false;
    }
  }
}

export default AuraClient;
