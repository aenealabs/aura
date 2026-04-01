/**
 * Aura API Client
 *
 * TypeScript client for communicating with the Aura API server.
 * Handles all extension-related API calls.
 */

import axios, { AxiosInstance, AxiosError } from 'axios';

// ============================================================================
// Types
// ============================================================================

export interface ExtensionConfig {
    scan_on_save: boolean;
    auto_suggest_patches: boolean;
    severity_threshold: string;
    supported_languages: string[];
    api_version: string;
    features: Record<string, boolean>;
}

export interface ScanRequest {
    file_path: string;
    file_content: string;
    language: string;
    workspace_path: string;
}

export interface ScanResponse {
    scan_id: string;
    status: string;
    findings_count: number;
    message: string;
}

export interface Finding {
    id: string;
    file_path: string;
    line_start: number;
    line_end: number;
    column_start: number;
    column_end: number;
    severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
    category: string;
    title: string;
    description: string;
    code_snippet: string;
    suggestion: string;
    cwe_id: string | null;
    owasp_category: string | null;
    has_patch: boolean;
    patch_id: string | null;
}

export interface FindingsResponse {
    file_path: string;
    findings: Finding[];
    scan_timestamp: string;
    scan_duration_ms: number;
}

export interface PatchRequest {
    finding_id: string;
    file_path: string;
    file_content: string;
    context_lines: number;
}

export interface Patch {
    id: string;
    finding_id: string;
    file_path: string;
    status: 'pending' | 'generating' | 'ready' | 'approved' | 'applied' | 'rejected' | 'failed';
    original_code: string;
    patched_code: string;
    diff: string;
    explanation: string;
    confidence: number;
    requires_approval: boolean;
    approval_id: string | null;
    created_at: string;
    applied_at: string | null;
}

export interface PatchResponse {
    patch: Patch;
    message: string;
}

export interface ApplyPatchResponse {
    success: boolean;
    patch_id: string;
    file_path: string;
    message: string;
    backup_path: string | null;
}

export interface ApprovalStatus {
    patch_id: string;
    approval_id: string | null;
    status: string;
    reviewer: string | null;
    reviewed_at: string | null;
    comments: string | null;
}

// ============================================================================
// GraphRAG Context Types (ADR-048 P0 - Key Differentiator)
// ============================================================================

export type GraphNodeType = 'file' | 'class' | 'function' | 'method' | 'module' | 'variable' | 'import';
export type GraphEdgeType = 'calls' | 'imports' | 'inherits' | 'implements' | 'contains' | 'references' | 'depends_on';

export interface GraphNode {
    id: string;
    type: GraphNodeType;
    name: string;
    file_path: string | null;
    line_start: number | null;
    line_end: number | null;
    metadata: Record<string, unknown>;
}

export interface GraphEdge {
    source_id: string;
    target_id: string;
    type: GraphEdgeType;
    weight: number;
    metadata: Record<string, unknown>;
}

export interface GraphContextRequest {
    file_path: string;
    line_number?: number;
    depth?: number;
    include_types?: GraphNodeType[];
}

export interface GraphContextResponse {
    file_path: string;
    focus_node_id: string | null;
    nodes: GraphNode[];
    edges: GraphEdge[];
    relationships: Record<string, number>;
    query_duration_ms: number;
    metadata: Record<string, unknown>;
}

// ============================================================================
// Fix Preview Types (ADR-048)
// ============================================================================

export interface FixPreviewRequest {
    finding_id: string;
    file_content: string;
    apply_all?: boolean;
}

export interface FixPreviewResponse {
    finding_id: string;
    diff: string;
    confidence: number;
    explanation: string;
    side_effects: string[];
    test_suggestions: string[];
    requires_review: boolean;
}

// ============================================================================
// Secrets Detection Types (ADR-048 Security Control)
// ============================================================================

export interface SecretFinding {
    detection_id: string;
    secret_type: string;
    line_number: number;
    column_start: number;
    column_end: number;
    confidence: number;
    context: string;
}

export interface SecretsCheckResponse {
    is_clean: boolean;
    secret_count: number;
    secrets: SecretFinding[];
    scan_duration_ms: number;
    blocked: boolean;
}

// ============================================================================
// API Client
// ============================================================================

export class AuraApiClient {
    private client: AxiosInstance;
    private baseUrl: string;

    constructor(baseUrl: string) {
        this.baseUrl = baseUrl;
        this.client = axios.create({
            baseURL: `${baseUrl}/api/v1/extension`,
            timeout: 30000,
            headers: {
                'Content-Type': 'application/json',
            },
        });

        // Add response interceptor for error handling
        this.client.interceptors.response.use(
            response => response,
            (error: AxiosError) => {
                if (error.response) {
                    const data = error.response.data as any;
                    throw new Error(data.detail || data.error || 'API request failed');
                } else if (error.request) {
                    throw new Error('No response from server');
                } else {
                    throw new Error(error.message);
                }
            }
        );
    }

    /**
     * Update the base URL (e.g., when configuration changes)
     */
    setBaseUrl(baseUrl: string): void {
        this.baseUrl = baseUrl;
        this.client.defaults.baseURL = `${baseUrl}/api/v1/extension`;
    }

    /**
     * Get extension configuration from server
     */
    async getConfig(): Promise<ExtensionConfig> {
        const response = await this.client.get<ExtensionConfig>('/config');
        return response.data;
    }

    /**
     * Scan a file for vulnerabilities
     */
    async scanFile(request: ScanRequest): Promise<ScanResponse> {
        const response = await this.client.post<ScanResponse>('/scan', request);
        return response.data;
    }

    /**
     * Get findings for a specific file
     */
    async getFindings(filePath: string): Promise<FindingsResponse> {
        const encodedPath = encodeURIComponent(filePath);
        const response = await this.client.get<FindingsResponse>(`/findings/${encodedPath}`);
        return response.data;
    }

    /**
     * Get all findings across all files
     */
    async getAllFindings(
        severity?: string,
        category?: string
    ): Promise<{ total: number; findings: Finding[] }> {
        const params: Record<string, string> = {};
        if (severity) params.severity = severity;
        if (category) params.category = category;

        const response = await this.client.get<{ total: number; findings: Finding[] }>(
            '/findings',
            { params }
        );
        return response.data;
    }

    /**
     * Generate a patch for a finding
     */
    async generatePatch(request: PatchRequest): Promise<PatchResponse> {
        const response = await this.client.post<PatchResponse>('/patches', request);
        return response.data;
    }

    /**
     * Get details of a specific patch
     */
    async getPatch(patchId: string): Promise<Patch> {
        const response = await this.client.get<Patch>(`/patches/${patchId}`);
        return response.data;
    }

    /**
     * Apply an approved patch
     */
    async applyPatch(patchId: string, confirm: boolean): Promise<ApplyPatchResponse> {
        const response = await this.client.post<ApplyPatchResponse>(
            `/patches/${patchId}/apply`,
            { patch_id: patchId, confirm }
        );
        return response.data;
    }

    /**
     * Get approval status for a patch
     */
    async getApprovalStatus(approvalId: string): Promise<ApprovalStatus> {
        const response = await this.client.get<ApprovalStatus>(`/approvals/${approvalId}`);
        return response.data;
    }

    /**
     * Health check
     */
    async healthCheck(): Promise<boolean> {
        try {
            await axios.get(`${this.baseUrl}/health`);
            return true;
        } catch {
            return false;
        }
    }

    // ========================================================================
    // GraphRAG Context Methods (ADR-048 P0 - Key Differentiator)
    // ========================================================================

    /**
     * Get GraphRAG context for a file (P0 Key Differentiator)
     *
     * Returns the code relationship graph for visualization.
     * Shows how the current file/function connects to other parts of the codebase.
     */
    async getGraphContext(request: GraphContextRequest): Promise<GraphContextResponse> {
        const response = await this.client.post<GraphContextResponse>('/graph/context', request);
        return response.data;
    }

    // ========================================================================
    // Fix Preview Methods (ADR-048)
    // ========================================================================

    /**
     * Preview a fix before applying it
     */
    async previewFix(request: FixPreviewRequest): Promise<FixPreviewResponse> {
        const response = await this.client.post<FixPreviewResponse>('/fix/preview', request);
        return response.data;
    }

    /**
     * Apply a fix directly (for medium/low severity findings)
     */
    async applyFix(findingId: string, filePath: string, confirm: boolean = true): Promise<ApplyPatchResponse> {
        const params = new URLSearchParams({
            finding_id: findingId,
            file_path: filePath,
            confirm: String(confirm),
        });
        const response = await this.client.post<ApplyPatchResponse>(`/fix/apply?${params}`);
        return response.data;
    }

    // ========================================================================
    // Secrets Detection Methods (ADR-048 Security Control)
    // ========================================================================

    /**
     * Check file content for secrets before storing in GraphRAG
     */
    async checkSecrets(filePath: string, content: string): Promise<SecretsCheckResponse> {
        const params = new URLSearchParams({
            file_path: filePath,
            content: content,
        });
        const response = await this.client.post<SecretsCheckResponse>(`/secrets/check?${params}`);
        return response.data;
    }

    /**
     * Redact secrets from file content
     */
    async redactSecrets(filePath: string, content: string): Promise<{
        original_hash: string;
        redacted_content: string;
        secrets_redacted: number;
        is_clean: boolean;
    }> {
        const params = new URLSearchParams({
            file_path: filePath,
            content: content,
        });
        const response = await this.client.post(`/secrets/redact?${params}`);
        return response.data;
    }
}
