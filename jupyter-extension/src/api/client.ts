/**
 * Aura API Client for JupyterLab
 *
 * TypeScript client for communicating with the Aura API server.
 * Handles notebook-specific API calls.
 */

import { URLExt } from '@jupyterlab/coreutils';
import { ServerConnection } from '@jupyterlab/services';

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

export interface CellScanRequest {
    notebook_path: string;
    cell_id: string;
    cell_index: number;
    source_code: string;
    language: string;
}

export interface CellScanResponse {
    scan_id: string;
    status: string;
    findings_count: number;
    message: string;
}

export interface Finding {
    id: string;
    file_path: string;
    cell_id?: string;
    cell_index?: number;
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

export interface CellFindingsResponse {
    notebook_path: string;
    cell_id: string;
    findings: Finding[];
    scan_timestamp: string;
}

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

export interface ApplyFixResponse {
    success: boolean;
    finding_id: string;
    file_path: string;
    message: string;
}

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

// GraphRAG Types (P0 Key Differentiator)
export type GraphNodeType = 'file' | 'class' | 'function' | 'method' | 'module' | 'variable' | 'import' | 'cell';
export type GraphEdgeType = 'calls' | 'imports' | 'inherits' | 'implements' | 'contains' | 'references' | 'depends_on';

export interface GraphNode {
    id: string;
    type: GraphNodeType;
    name: string;
    file_path: string | null;
    cell_id?: string;
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
    cell_id?: string;
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
// API Client
// ============================================================================

export class AuraApiClient {
    private baseUrl: string;
    private serverSettings: ServerConnection.ISettings;

    constructor(baseUrl: string) {
        this.baseUrl = baseUrl;
        this.serverSettings = ServerConnection.makeSettings();
    }

    /**
     * Make a request to the Aura API
     */
    private async request<T>(
        endpoint: string,
        method: string = 'GET',
        body?: any
    ): Promise<T> {
        const url = URLExt.join(this.baseUrl, 'api/v1/extension', endpoint);

        const options: RequestInit = {
            method,
            headers: {
                'Content-Type': 'application/json',
            },
        };

        if (body) {
            options.body = JSON.stringify(body);
        }

        const response = await fetch(url, options);

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
            throw new Error(error.detail || `Request failed: ${response.status}`);
        }

        return response.json();
    }

    /**
     * Get extension configuration from server
     */
    async getConfig(): Promise<ExtensionConfig> {
        return this.request<ExtensionConfig>('/config');
    }

    /**
     * Scan a notebook cell for vulnerabilities
     */
    async scanCell(request: CellScanRequest): Promise<CellScanResponse> {
        return this.request<CellScanResponse>('/notebook/scan-cell', 'POST', request);
    }

    /**
     * Get findings for a specific cell
     */
    async getCellFindings(notebookPath: string, cellId: string): Promise<CellFindingsResponse> {
        const encodedPath = encodeURIComponent(notebookPath);
        const encodedCellId = encodeURIComponent(cellId);
        return this.request<CellFindingsResponse>(
            `/notebook/findings/${encodedPath}/${encodedCellId}`
        );
    }

    /**
     * Get all findings for a notebook
     */
    async getNotebookFindings(notebookPath: string): Promise<{
        notebook_path: string;
        findings: Finding[];
        scan_timestamp: string;
    }> {
        const encodedPath = encodeURIComponent(notebookPath);
        return this.request(`/notebook/findings/${encodedPath}`);
    }

    /**
     * Preview a fix before applying
     */
    async previewFix(request: FixPreviewRequest): Promise<FixPreviewResponse> {
        return this.request<FixPreviewResponse>('/fix/preview', 'POST', request);
    }

    /**
     * Apply a fix
     */
    async applyFix(findingId: string, filePath: string, confirm: boolean): Promise<ApplyFixResponse> {
        const params = new URLSearchParams({
            finding_id: findingId,
            file_path: filePath,
            confirm: String(confirm),
        });
        return this.request<ApplyFixResponse>(`/fix/apply?${params}`, 'POST');
    }

    /**
     * Check content for secrets
     */
    async checkSecrets(filePath: string, content: string): Promise<SecretsCheckResponse> {
        return this.request<SecretsCheckResponse>('/secrets/check', 'POST', {
            file_path: filePath,
            content,
        });
    }

    /**
     * Get GraphRAG context (P0 Key Differentiator)
     */
    async getGraphContext(request: GraphContextRequest): Promise<GraphContextResponse> {
        return this.request<GraphContextResponse>('/graph/context', 'POST', request);
    }
}
