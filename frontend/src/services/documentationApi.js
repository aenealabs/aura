/**
 * Project Aura - Documentation API Service
 *
 * Provides integration with the Documentation Agent backend (ADR-056).
 * Supports SSE streaming for real-time progress updates during generation.
 *
 * Features:
 * - Documentation generation with streaming progress
 * - Cache management
 * - User feedback submission
 * - Mock mode for development
 */

// API Configuration
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';
// ADR-060: Default to real API mode for professional diagrams with AWS icons
// Mock mode only enabled via explicit VITE_MOCK_DOCS=true environment variable
const USE_MOCK = import.meta.env.VITE_MOCK_DOCS === 'true';

/**
 * Get authentication headers from stored tokens
 */
function getAuthHeaders() {
  try {
    const stored = localStorage.getItem('aura_auth_tokens');
    if (stored) {
      const tokens = JSON.parse(stored);
      if (tokens.access_token) {
        return { Authorization: `Bearer ${tokens.access_token}` };
      }
    }
  } catch (e) {
    console.warn('Failed to parse auth tokens:', e);
  }
  return {};
}

/**
 * Transform snake_case keys to camelCase for API responses
 */
function snakeToCamel(str) {
  return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
}

function transformKeys(obj) {
  if (Array.isArray(obj)) {
    return obj.map(transformKeys);
  }
  if (obj !== null && typeof obj === 'object') {
    return Object.keys(obj).reduce((acc, key) => {
      acc[snakeToCamel(key)] = transformKeys(obj[key]);
      return acc;
    }, {});
  }
  return obj;
}

/**
 * DocumentationApiError - Custom error class for documentation API errors
 */
export class DocumentationApiError extends Error {
  constructor(message, status = null, code = null, details = null) {
    super(message);
    this.name = 'DocumentationApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }

  get isRetryable() {
    if (this.status >= 500) return true;
    if (this.status === 429) return true;
    if (this.code === 'NETWORK_ERROR') return true;
    return false;
  }
}

/**
 * Confidence level definitions matching backend ConfidenceLevel enum
 */
export const ConfidenceLevel = {
  HIGH: 'high',
  MEDIUM: 'medium',
  LOW: 'low',
  UNCERTAIN: 'uncertain',
};

/**
 * Get confidence level from numeric score
 * @param {number} score - Confidence score (0.0 to 1.0)
 * @returns {string} Confidence level
 */
export function getConfidenceLevel(score) {
  if (score >= 0.85) return ConfidenceLevel.HIGH;
  if (score >= 0.65) return ConfidenceLevel.MEDIUM;
  if (score >= 0.45) return ConfidenceLevel.LOW;
  return ConfidenceLevel.UNCERTAIN;
}

/**
 * Get color for confidence level (design system colors)
 * @param {string} level - Confidence level
 * @returns {string} Tailwind color class
 */
export function getConfidenceColor(level) {
  switch (level) {
    case ConfidenceLevel.HIGH:
      return 'text-green-500';
    case ConfidenceLevel.MEDIUM:
      return 'text-blue-500';
    case ConfidenceLevel.LOW:
      return 'text-amber-500';
    case ConfidenceLevel.UNCERTAIN:
      return 'text-red-500';
    default:
      return 'text-gray-500';
  }
}

/**
 * Diagram type definitions matching backend DiagramType enum
 */
export const DiagramType = {
  ARCHITECTURE: 'architecture',
  DATA_FLOW: 'data_flow',
  DEPENDENCY: 'dependency',
  SEQUENCE: 'sequence',
  COMPONENT: 'component',
};

/**
 * Generation mode definitions (ADR-060)
 * CODE_ANALYSIS: Analyze codebase and generate Mermaid diagrams
 * AI_PROMPT: Generate professional SVG diagrams from natural language prompts
 */
export const GenerationMode = {
  CODE_ANALYSIS: 'CODE_ANALYSIS',
  AI_PROMPT: 'AI_PROMPT',
};

/**
 * Render engine definitions (ADR-060)
 * MERMAID: Traditional Mermaid.js diagrams (code analysis mode)
 * AURA_SVG: Aura's professional SVG with cloud icons (default for AI prompts)
 * ERASER_API: Eraser.io external API (requires API key)
 */
export const RenderEngine = {
  MERMAID: 'mermaid',
  AURA_SVG: 'aura_svg',
  ERASER_API: 'eraser_api',
  // Legacy alias
  ERASER: 'aura_svg',
};

/**
 * Generate documentation for a repository
 *
 * @param {string} repositoryId - Repository ID to generate documentation for
 * @param {Object} options - Generation options
 * @param {string[]} options.diagramTypes - Types of diagrams to generate
 * @param {boolean} options.includeReport - Include technical report
 * @param {number} options.maxServices - Maximum services to detect
 * @param {number} options.minConfidence - Minimum confidence threshold
 * @param {string} options.mode - Generation mode: CODE_ANALYSIS or AI_PROMPT (ADR-060)
 * @param {string} options.prompt - Natural language prompt for AI_PROMPT mode (ADR-060)
 * @param {string} options.renderEngine - Render engine: mermaid or eraser (ADR-060)
 * @returns {Promise<Object>} Documentation result
 */
export async function generateDocumentation(repositoryId, options = {}) {
  // ADR-060: Determine effective mode first to auto-select render engine
  const effectiveMode = options.mode || GenerationMode.CODE_ANALYSIS;

  const {
    diagramTypes = ['architecture', 'data_flow'],
    includeReport = true,
    maxServices = 20,
    minConfidence = 0.45,
    mode = GenerationMode.CODE_ANALYSIS,
    prompt = '',
    // ADR-060: Auto-select 'aura_svg' render engine for AI_PROMPT mode
    // to generate professional SVG diagrams with cloud provider icons
    renderEngine = effectiveMode === GenerationMode.AI_PROMPT
      ? RenderEngine.AURA_SVG
      : RenderEngine.MERMAID,
    // Optional: Eraser.io API key for eraser_api render engine
    eraserApiKey = '',
  } = options;

  // ADR-060: AI_PROMPT mode requires real backend API for professional diagrams
  // Mock mode cannot generate proper AI-driven diagrams with cloud icons
  const useRealApi = effectiveMode === GenerationMode.AI_PROMPT;

  if (USE_MOCK && !useRealApi) {
    // Pass computed renderEngine to mock function
    return generateMockDocumentation(repositoryId, { ...options, renderEngine });
  }

  const url = `${API_BASE_URL}/documentation/generate`;

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify({
      repository_id: repositoryId,
      diagram_types: diagramTypes,
      include_report: includeReport,
      max_services: maxServices,
      min_confidence: minConfidence,
      mode: mode,
      prompt: prompt,
      render_engine: renderEngine,
      eraser_api_key: eraserApiKey,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new DocumentationApiError(
      errorData.message || `Request failed with status ${response.status}`,
      response.status,
      errorData.error,
      errorData
    );
  }

  // Transform snake_case keys to camelCase for frontend consumption
  const data = await response.json();
  return transformKeys(data);
}

/**
 * Generate documentation with streaming progress updates
 *
 * @param {string} repositoryId - Repository ID
 * @param {Object} options - Generation options
 * @param {string} options.diagramTypes - Comma-separated diagram types
 * @param {boolean} options.includeReport - Include technical report
 * @param {AbortSignal} options.signal - AbortController signal
 * @param {Function} options.onProgress - Callback for progress updates
 * @param {Function} options.onComplete - Callback when complete
 * @param {Function} options.onError - Callback on error
 * @returns {Promise<Object>} Documentation result
 */
export async function generateDocumentationStream(repositoryId, options = {}) {
  const {
    diagramTypes = 'architecture,data_flow',
    includeReport = true,
    signal,
    onProgress,
    onComplete,
    onError,
  } = options;

  if (USE_MOCK) {
    return generateMockDocumentationStream(repositoryId, options);
  }

  const params = new URLSearchParams({
    diagram_types: diagramTypes,
    include_report: includeReport.toString(),
  });

  const url = `${API_BASE_URL}/documentation/generate/${repositoryId}/stream?${params}`;

  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        Accept: 'text/event-stream',
        ...getAuthHeaders(),
      },
      signal,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new DocumentationApiError(
        errorData.message || `Request failed with status ${response.status}`,
        response.status,
        errorData.error,
        errorData
      );
    }

    return await handleStreamingResponse(response, { onProgress, onComplete, onError });
  } catch (error) {
    if (error.name === 'AbortError') {
      throw error;
    }

    if (error instanceof DocumentationApiError) {
      onError?.(error);
      throw error;
    }

    const apiError = new DocumentationApiError(
      error.message || 'Network error occurred',
      null,
      'NETWORK_ERROR'
    );
    onError?.(apiError);
    throw apiError;
  }
}

/**
 * Handle SSE streaming response from the API
 */
async function handleStreamingResponse(response, callbacks) {
  const { onProgress, onComplete, onError } = callbacks;

  if (!response.body) {
    throw new DocumentationApiError('Response body is empty', null, 'EMPTY_BODY');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let result = null;

  try {
    while (true) {
      const { done, value } = await reader.read();

      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Process complete SSE messages
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.trim() || line.startsWith(':')) continue;

        // Parse event type
        if (line.startsWith('event: ')) {
          // Event type line - skip, data follows
          continue;
        }

        if (line.startsWith('data: ')) {
          const data = line.slice(6);

          try {
            const parsed = JSON.parse(data);

            if (parsed.phase === 'complete') {
              // Transform snake_case keys to camelCase for frontend consumption
              result = transformKeys(parsed.result);
              onComplete?.(result);
            } else if (parsed.phase === 'error') {
              throw new DocumentationApiError(
                parsed.message || 'Generation failed',
                null,
                'GENERATION_ERROR',
                { error: parsed.error }
              );
            } else {
              // Progress update
              onProgress?.({
                phase: parsed.phase,
                progress: parsed.progress,
                message: parsed.message,
                currentStep: parsed.current_step,
                totalSteps: parsed.total_steps,
                metadata: parsed.metadata || {},
              });
            }
          } catch (e) {
            if (e instanceof DocumentationApiError) throw e;
            console.warn('Failed to parse SSE data:', data, e);
          }
        }
      }
    }

    return result;
  } catch (error) {
    onError?.(error);
    throw error;
  }
}

/**
 * Submit feedback on generated documentation
 *
 * @param {Object} feedback - Feedback data
 * @param {string} feedback.jobId - Job ID for the documentation
 * @param {string} feedback.section - Section being corrected
 * @param {string} feedback.correctionType - Type of correction
 * @param {string} feedback.originalContent - Original content
 * @param {string} feedback.correctedContent - Corrected content
 * @param {number} feedback.confidenceRating - User's confidence rating
 * @param {string} feedback.notes - Additional notes
 * @returns {Promise<Object>} Feedback response
 */
export async function submitFeedback(feedback) {
  if (USE_MOCK) {
    return { feedbackId: `fb-${Date.now()}`, status: 'accepted', message: 'Thank you!' };
  }

  const url = `${API_BASE_URL}/documentation/feedback`;

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify({
      job_id: feedback.jobId,
      section: feedback.section,
      correction_type: feedback.correctionType,
      original_content: feedback.originalContent,
      corrected_content: feedback.correctedContent,
      confidence_rating: feedback.confidenceRating,
      notes: feedback.notes || '',
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new DocumentationApiError(
      errorData.message || 'Failed to submit feedback',
      response.status,
      errorData.error
    );
  }

  return response.json();
}

/**
 * Get cache statistics
 *
 * @returns {Promise<Object>} Cache stats
 */
export async function getCacheStats() {
  if (USE_MOCK) {
    return getMockCacheStats();
  }

  const url = `${API_BASE_URL}/documentation/cache/stats`;

  const response = await fetch(url, {
    method: 'GET',
    headers: {
      ...getAuthHeaders(),
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new DocumentationApiError(
      errorData.message || 'Failed to get cache stats',
      response.status,
      errorData.error
    );
  }

  return response.json();
}

/**
 * Invalidate cache for a repository
 *
 * @param {string} repositoryId - Repository ID to invalidate
 * @returns {Promise<Object>} Invalidation result
 */
export async function invalidateCache(repositoryId) {
  if (USE_MOCK) {
    return { status: 'success', repositoryId, entriesInvalidated: 3 };
  }

  const url = `${API_BASE_URL}/documentation/cache/${repositoryId}`;

  const response = await fetch(url, {
    method: 'DELETE',
    headers: {
      ...getAuthHeaders(),
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new DocumentationApiError(
      errorData.message || 'Failed to invalidate cache',
      response.status,
      errorData.error
    );
  }

  return response.json();
}

/**
 * Get available diagram types
 *
 * @returns {Promise<Array>} Diagram types
 */
export async function getDiagramTypes() {
  if (USE_MOCK) {
    return [
      { value: 'architecture', label: 'Architecture' },
      { value: 'data_flow', label: 'Data Flow' },
      { value: 'dependency', label: 'Dependency' },
      { value: 'sequence', label: 'Sequence' },
      { value: 'component', label: 'Component' },
    ];
  }

  const url = `${API_BASE_URL}/documentation/diagram-types`;

  const response = await fetch(url, {
    method: 'GET',
    headers: {
      ...getAuthHeaders(),
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new DocumentationApiError(
      errorData.message || 'Failed to get diagram types',
      response.status,
      errorData.error
    );
  }

  return response.json();
}

// ============================================================================
// Mock Implementations for Development
// ============================================================================

/**
 * Production-realistic mock repositories for development testing
 */
export const MOCK_REPOSITORIES = [
  {
    repository_id: 'repo-aura-core-1a2',
    name: 'aura-core',
    full_name: 'acme-corp/aura-core',
    description: 'Core platform services for Project Aura - Agent orchestration, GraphRAG, and HITL workflows',
    language: 'Python',
    languages: { Python: 68.4, JavaScript: 15.2, TypeScript: 12.1, Shell: 4.3 },
    default_branch: 'main',
    visibility: 'private',
    stars: 0,
    forks: 0,
    // Analysis metadata
    last_analyzed: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
    last_analyzed_by: 'usr-sys-scheduler',
    last_analyzed_commit: 'a8f3e2d1c4b5a6e7f8d9c0b1a2e3f4d5c6b7a8e9',
    analysis_status: 'completed',
    analysis_duration_seconds: 847,
    // Code metrics
    file_count: 2847,
    line_count: 168453,
    test_coverage_percent: 87.3,
    complexity_avg: 7.2,
    // Documentation stats
    doc_generation_count: 47,
    last_doc_generated: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
    doc_confidence_avg: 0.89,
    // Organization context
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    team_id: 'team-platform-eng',
    team_name: 'Platform Engineering',
    // Collaboration
    contributors_count: 12,
    active_prs: 8,
    open_issues: 23,
    // Integration
    connected_integrations: ['github', 'slack', 'pagerduty'],
    index_status: 'indexed',
    last_indexed: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
    tags: ['core', 'platform', 'graphrag', 'hitl', 'critical'],
  },
  {
    repository_id: 'repo-frontend-app-8b2',
    name: 'aura-dashboard',
    full_name: 'acme-corp/aura-dashboard',
    description: 'React 18 frontend dashboard - Trust Center, GPU Scheduler, and Agent Monitoring views',
    language: 'TypeScript',
    languages: { TypeScript: 72.1, JavaScript: 18.4, CSS: 8.2, HTML: 1.3 },
    default_branch: 'main',
    visibility: 'private',
    stars: 0,
    forks: 0,
    last_analyzed: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(),
    last_analyzed_by: 'usr-sys-scheduler',
    last_analyzed_commit: 'b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8',
    analysis_status: 'completed',
    analysis_duration_seconds: 423,
    file_count: 892,
    line_count: 47823,
    test_coverage_percent: 82.1,
    complexity_avg: 5.8,
    doc_generation_count: 23,
    last_doc_generated: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
    doc_confidence_avg: 0.86,
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    team_id: 'team-frontend',
    team_name: 'Frontend Engineering',
    contributors_count: 6,
    active_prs: 5,
    open_issues: 12,
    connected_integrations: ['github', 'slack'],
    index_status: 'indexed',
    last_indexed: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
    tags: ['frontend', 'react', 'dashboard', 'ui'],
  },
  {
    repository_id: 'repo-ml-pipeline-0d1',
    name: 'ml-training-pipeline',
    full_name: 'acme-corp/ml-training-pipeline',
    description: 'Machine learning infrastructure - SWE-RL training, Titan memory consolidation, embedding generation',
    language: 'Python',
    languages: { Python: 89.2, Shell: 6.4, Dockerfile: 4.4 },
    default_branch: 'main',
    visibility: 'private',
    stars: 0,
    forks: 0,
    last_analyzed: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    last_analyzed_by: 'usr-sys-scheduler',
    last_analyzed_commit: 'c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9',
    analysis_status: 'completed',
    analysis_duration_seconds: 612,
    file_count: 1456,
    line_count: 78234,
    test_coverage_percent: 79.4,
    complexity_avg: 8.1,
    doc_generation_count: 15,
    last_doc_generated: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
    doc_confidence_avg: 0.84,
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    team_id: 'team-ml-platform',
    team_name: 'ML Platform Engineering',
    contributors_count: 8,
    active_prs: 3,
    open_issues: 18,
    connected_integrations: ['github', 'datadog'],
    index_status: 'indexed',
    last_indexed: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
    tags: ['ml', 'training', 'swe-rl', 'titan', 'gpu'],
  },
  {
    repository_id: 'repo-api-gateway-3e4',
    name: 'api-gateway-service',
    full_name: 'acme-corp/api-gateway-service',
    description: 'Kong-based API Gateway with rate limiting, auth middleware, and request routing',
    language: 'Go',
    languages: { Go: 82.3, Lua: 12.4, Shell: 5.3 },
    default_branch: 'main',
    visibility: 'private',
    stars: 0,
    forks: 0,
    last_analyzed: new Date(Date.now() - 36 * 60 * 60 * 1000).toISOString(),
    last_analyzed_by: 'usr-sys-scheduler',
    last_analyzed_commit: 'd1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0',
    analysis_status: 'completed',
    analysis_duration_seconds: 289,
    file_count: 234,
    line_count: 18567,
    test_coverage_percent: 91.2,
    complexity_avg: 4.3,
    doc_generation_count: 8,
    last_doc_generated: new Date(Date.now() - 14 * 24 * 60 * 60 * 1000).toISOString(),
    doc_confidence_avg: 0.92,
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    team_id: 'team-platform-eng',
    team_name: 'Platform Engineering',
    contributors_count: 4,
    active_prs: 2,
    open_issues: 5,
    connected_integrations: ['github', 'pagerduty', 'datadog'],
    index_status: 'indexed',
    last_indexed: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString(),
    tags: ['api', 'gateway', 'kong', 'routing', 'critical'],
  },
  {
    repository_id: 'repo-infra-iac-5f6',
    name: 'infrastructure-as-code',
    full_name: 'acme-corp/infrastructure-as-code',
    description: 'CloudFormation templates, Terraform modules, and deployment scripts for AWS GovCloud',
    language: 'HCL',
    languages: { HCL: 45.2, YAML: 38.4, Python: 12.1, Shell: 4.3 },
    default_branch: 'main',
    visibility: 'private',
    stars: 0,
    forks: 0,
    last_analyzed: new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString(),
    last_analyzed_by: 'usr-sys-scheduler',
    last_analyzed_commit: 'e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1',
    analysis_status: 'completed',
    analysis_duration_seconds: 178,
    file_count: 456,
    line_count: 34892,
    test_coverage_percent: 72.8,
    complexity_avg: 3.2,
    doc_generation_count: 12,
    last_doc_generated: new Date(Date.now() - 10 * 24 * 60 * 60 * 1000).toISOString(),
    doc_confidence_avg: 0.88,
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    team_id: 'team-devops',
    team_name: 'DevOps & Infrastructure',
    contributors_count: 5,
    active_prs: 4,
    open_issues: 9,
    connected_integrations: ['github', 'slack'],
    index_status: 'indexed',
    last_indexed: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(),
    tags: ['infrastructure', 'terraform', 'cloudformation', 'govcloud', 'devops'],
  },
];

/**
 * Mock SVG diagram for AI_PROMPT mode (ADR-060 professional diagrams)
 * This reflects Project Aura's actual architecture with multi-agent system,
 * GraphRAG, HITL workflows, and Constitutional AI
 */
const MOCK_SVG_DIAGRAM = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1400 900" style="background: #0a0a0f;">
  <defs>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="2" dy="3" stdDeviation="4" flood-color="#000" flood-opacity="0.4"/>
    </filter>
    <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">
      <path d="M 24 0 L 0 0 0 24" fill="none" stroke="rgba(59, 130, 246, 0.06)" stroke-width="1"/>
    </pattern>
    <linearGradient id="frontendGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#3b82f6;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#1d4ed8;stop-opacity:1" />
    </linearGradient>
    <linearGradient id="agentGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#14b8a6;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#0d9488;stop-opacity:1" />
    </linearGradient>
    <linearGradient id="securityGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#a855f7;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#7c3aed;stop-opacity:1" />
    </linearGradient>
    <linearGradient id="dataGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#6366f1;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#4f46e5;stop-opacity:1" />
    </linearGradient>
  </defs>

  <!-- Grid Background -->
  <rect width="100%" height="100%" fill="url(#grid)"/>

  <!-- Title -->
  <text x="700" y="45" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="28" font-weight="700" fill="#e0f2fe">Project Aura - System Architecture</text>
  <text x="700" y="70" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="14" fill="#64748b">Autonomous AI SaaS Platform for Enterprise Code Intelligence</text>

  <!-- Frontend Layer -->
  <g transform="translate(50, 100)">
    <rect x="0" y="0" width="280" height="130" rx="12" fill="#1e3a5f" stroke="#3b82f6" stroke-width="1" filter="url(#shadow)"/>
    <rect x="0" y="0" width="280" height="36" rx="12" fill="url(#frontendGrad)"/>
    <text x="140" y="24" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="13" font-weight="600" fill="white">Frontend Layer</text>
    <g transform="translate(20, 50)">
      <rect x="0" y="0" width="72" height="60" rx="8" fill="#0f172a" stroke="#60a5fa" stroke-width="1.5"/>
      <text x="36" y="35" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="10" fill="#e0f2fe">Dashboard</text>
    </g>
    <g transform="translate(102, 50)">
      <rect x="0" y="0" width="72" height="60" rx="8" fill="#0f172a" stroke="#60a5fa" stroke-width="1.5"/>
      <text x="36" y="28" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="10" fill="#e0f2fe">Trust</text>
      <text x="36" y="42" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="10" fill="#e0f2fe">Center</text>
    </g>
    <g transform="translate(184, 50)">
      <rect x="0" y="0" width="72" height="60" rx="8" fill="#0f172a" stroke="#60a5fa" stroke-width="1.5"/>
      <text x="36" y="28" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="10" fill="#e0f2fe">GPU</text>
      <text x="36" y="42" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="10" fill="#e0f2fe">Scheduler</text>
    </g>
  </g>

  <!-- API Gateway -->
  <g transform="translate(380, 100)">
    <rect x="0" y="0" width="220" height="130" rx="12" fill="#1e3a4d" stroke="#06b6d4" stroke-width="1" filter="url(#shadow)"/>
    <rect x="0" y="0" width="220" height="36" rx="12" fill="#06b6d4"/>
    <text x="110" y="24" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="13" font-weight="600" fill="white">API Gateway</text>
    <g transform="translate(20, 50)">
      <rect x="0" y="0" width="80" height="60" rx="8" fill="#0f172a" stroke="#22d3ee" stroke-width="1.5"/>
      <text x="40" y="35" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="10" fill="#cffafe">FastAPI</text>
    </g>
    <g transform="translate(115, 50)">
      <rect x="0" y="0" width="80" height="60" rx="8" fill="#0f172a" stroke="#22d3ee" stroke-width="1.5"/>
      <text x="40" y="28" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="10" fill="#cffafe">Auth MW</text>
      <text x="40" y="42" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="10" fill="#cffafe">+ WAF</text>
    </g>
  </g>

  <!-- Multi-Agent System -->
  <g transform="translate(50, 280)">
    <rect x="0" y="0" width="550" height="160" rx="12" fill="#1a2e35" stroke="#14b8a6" stroke-width="1" filter="url(#shadow)"/>
    <rect x="0" y="0" width="550" height="36" rx="12" fill="url(#agentGrad)"/>
    <text x="275" y="24" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="13" font-weight="600" fill="white">Multi-Agent System</text>
    <g transform="translate(20, 50)">
      <rect x="0" y="0" width="115" height="90" rx="8" fill="#0f172a" stroke="#2dd4bf" stroke-width="1.5"/>
      <text x="57" y="40" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="11" font-weight="500" fill="#ccfbf1">Agent</text>
      <text x="57" y="56" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="11" font-weight="500" fill="#ccfbf1">Orchestrator</text>
    </g>
    <g transform="translate(150, 50)">
      <rect x="0" y="0" width="115" height="90" rx="8" fill="#0f172a" stroke="#2dd4bf" stroke-width="1.5"/>
      <text x="57" y="40" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="11" fill="#ccfbf1">Coder</text>
      <text x="57" y="56" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="11" fill="#ccfbf1">Agent</text>
    </g>
    <g transform="translate(280, 50)">
      <rect x="0" y="0" width="115" height="90" rx="8" fill="#0f172a" stroke="#2dd4bf" stroke-width="1.5"/>
      <text x="57" y="40" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="11" fill="#ccfbf1">Reviewer</text>
      <text x="57" y="56" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="11" fill="#ccfbf1">Agent</text>
    </g>
    <g transform="translate(410, 50)">
      <rect x="0" y="0" width="115" height="90" rx="8" fill="#0f172a" stroke="#2dd4bf" stroke-width="1.5"/>
      <text x="57" y="40" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="11" fill="#ccfbf1">Validator</text>
      <text x="57" y="56" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="11" fill="#ccfbf1">Agent</text>
    </g>
  </g>

  <!-- Context Engineering (GraphRAG) -->
  <g transform="translate(50, 490)">
    <rect x="0" y="0" width="550" height="160" rx="12" fill="#1e3a5f" stroke="#3b82f6" stroke-width="1" filter="url(#shadow)"/>
    <rect x="0" y="0" width="550" height="36" rx="12" fill="url(#frontendGrad)"/>
    <text x="275" y="24" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="13" font-weight="600" fill="white">Context Engineering (Hybrid GraphRAG)</text>
    <g transform="translate(20, 50)">
      <rect x="0" y="0" width="115" height="90" rx="8" fill="#0f172a" stroke="#60a5fa" stroke-width="1.5"/>
      <text x="57" y="40" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="11" fill="#e0f2fe">Context</text>
      <text x="57" y="56" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="11" fill="#e0f2fe">Retrieval</text>
    </g>
    <g transform="translate(150, 50)">
      <rect x="0" y="0" width="115" height="90" rx="8" fill="#0f172a" stroke="#60a5fa" stroke-width="1.5"/>
      <text x="57" y="40" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="11" fill="#e0f2fe">Hybrid</text>
      <text x="57" y="56" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="11" fill="#e0f2fe">GraphRAG</text>
    </g>
    <g transform="translate(280, 50)">
      <rect x="0" y="0" width="115" height="90" rx="8" fill="#0f172a" stroke="#60a5fa" stroke-width="1.5"/>
      <text x="57" y="40" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="11" fill="#e0f2fe">Titan Neural</text>
      <text x="57" y="56" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="11" fill="#e0f2fe">Memory</text>
    </g>
    <g transform="translate(410, 50)">
      <rect x="0" y="0" width="115" height="90" rx="8" fill="#0f172a" stroke="#60a5fa" stroke-width="1.5"/>
      <text x="57" y="40" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="11" fill="#e0f2fe">RLM Context</text>
      <text x="57" y="56" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="11" fill="#e0f2fe">Engine</text>
    </g>
  </g>

  <!-- Security Layer -->
  <g transform="translate(650, 280)">
    <rect x="0" y="0" width="340" height="160" rx="12" fill="#2d1f3d" stroke="#a855f7" stroke-width="1" filter="url(#shadow)"/>
    <rect x="0" y="0" width="340" height="36" rx="12" fill="url(#securityGrad)"/>
    <text x="170" y="24" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="13" font-weight="600" fill="white">Security & HITL</text>
    <g transform="translate(20, 50)">
      <rect x="0" y="0" width="90" height="90" rx="8" fill="#0f0a1a" stroke="#c084fc" stroke-width="1.5"/>
      <text x="45" y="40" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="10" fill="#f3e8ff">HITL</text>
      <text x="45" y="54" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="10" fill="#f3e8ff">Workflow</text>
    </g>
    <g transform="translate(125, 50)">
      <rect x="0" y="0" width="90" height="90" rx="8" fill="#0f0a1a" stroke="#c084fc" stroke-width="1.5"/>
      <text x="45" y="40" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="10" fill="#f3e8ff">Sandbox</text>
      <text x="45" y="54" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="10" fill="#f3e8ff">Network</text>
    </g>
    <g transform="translate(230, 50)">
      <rect x="0" y="0" width="90" height="90" rx="8" fill="#0f0a1a" stroke="#c084fc" stroke-width="1.5"/>
      <text x="45" y="40" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="10" fill="#f3e8ff">Constitutional</text>
      <text x="45" y="54" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="10" fill="#f3e8ff">AI</text>
    </g>
  </g>

  <!-- Data Layer -->
  <g transform="translate(650, 490)">
    <rect x="0" y="0" width="340" height="160" rx="12" fill="#1f2937" stroke="#6366f1" stroke-width="1" filter="url(#shadow)"/>
    <rect x="0" y="0" width="340" height="36" rx="12" fill="url(#dataGrad)"/>
    <text x="170" y="24" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="13" font-weight="600" fill="white">Data Layer</text>
    <g transform="translate(20, 50)">
      <rect x="0" y="0" width="70" height="90" rx="8" fill="#0f172a" stroke="#818cf8" stroke-width="1.5"/>
      <text x="35" y="50" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="10" fill="#e0e7ff">Neptune</text>
    </g>
    <g transform="translate(100, 50)">
      <rect x="0" y="0" width="70" height="90" rx="8" fill="#0f172a" stroke="#818cf8" stroke-width="1.5"/>
      <text x="35" y="44" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="10" fill="#e0e7ff">Open</text>
      <text x="35" y="58" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="10" fill="#e0e7ff">Search</text>
    </g>
    <g transform="translate(180, 50)">
      <rect x="0" y="0" width="70" height="90" rx="8" fill="#0f172a" stroke="#818cf8" stroke-width="1.5"/>
      <text x="35" y="44" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="10" fill="#e0e7ff">Dynamo</text>
      <text x="35" y="58" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="10" fill="#e0e7ff">DB</text>
    </g>
    <g transform="translate(260, 50)">
      <rect x="0" y="0" width="60" height="90" rx="8" fill="#0f172a" stroke="#818cf8" stroke-width="1.5"/>
      <text x="30" y="50" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="10" fill="#e0e7ff">S3</text>
    </g>
  </g>

  <!-- External Services -->
  <g transform="translate(1050, 100)">
    <rect x="0" y="0" width="280" height="200" rx="12" fill="#1c1c1e" stroke="#71717a" stroke-width="1" filter="url(#shadow)"/>
    <rect x="0" y="0" width="280" height="36" rx="12" fill="#52525b"/>
    <text x="140" y="24" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="13" font-weight="600" fill="white">AWS Services</text>
    <g transform="translate(20, 50)">
      <rect x="0" y="0" width="110" height="55" rx="8" fill="#0f172a" stroke="#a1a1aa" stroke-width="1.5"/>
      <text x="55" y="32" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="10" fill="#e4e4e7">Bedrock (LLM)</text>
    </g>
    <g transform="translate(145, 50)">
      <rect x="0" y="0" width="110" height="55" rx="8" fill="#0f172a" stroke="#a1a1aa" stroke-width="1.5"/>
      <text x="55" y="32" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="10" fill="#e4e4e7">Cognito (Auth)</text>
    </g>
    <g transform="translate(20, 120)">
      <rect x="0" y="0" width="110" height="55" rx="8" fill="#0f172a" stroke="#a1a1aa" stroke-width="1.5"/>
      <text x="55" y="32" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="10" fill="#e4e4e7">CloudWatch</text>
    </g>
    <g transform="translate(145, 120)">
      <rect x="0" y="0" width="110" height="55" rx="8" fill="#0f172a" stroke="#a1a1aa" stroke-width="1.5"/>
      <text x="55" y="32" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="10" fill="#e4e4e7">EKS/ECS</text>
    </g>
  </g>

  <!-- Connection arrows -->
  <defs>
    <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
      <polygon points="0 0, 10 3.5, 0 7" fill="#4b5563"/>
    </marker>
  </defs>

  <!-- Frontend to Gateway -->
  <path d="M 330 165 L 380 165" stroke="#4b5563" stroke-width="1" marker-end="url(#arrowhead)" fill="none"/>

  <!-- Gateway to Agents -->
  <path d="M 490 230 L 325 280" stroke="#4b5563" stroke-width="1" marker-end="url(#arrowhead)" fill="none"/>

  <!-- Agents to Context -->
  <path d="M 325 440 L 325 490" stroke="#4b5563" stroke-width="1" marker-end="url(#arrowhead)" fill="none"/>

  <!-- Agents to Security -->
  <path d="M 600 360 L 650 360" stroke="#4b5563" stroke-width="1" marker-end="url(#arrowhead)" fill="none"/>

  <!-- Context to Data -->
  <path d="M 600 570 L 650 570" stroke="#4b5563" stroke-width="1" marker-end="url(#arrowhead)" fill="none"/>

  <!-- Gateway to AWS -->
  <path d="M 600 165 L 1050 165" stroke="#4b5563" stroke-width="1" marker-end="url(#arrowhead)" fill="none"/>

  <!-- Agents to AWS -->
  <path d="M 600 320 L 1050 200" stroke="#4b5563" stroke-width="1" stroke-dasharray="6,3" marker-end="url(#arrowhead)" fill="none"/>

  <!-- Legend -->
  <g transform="translate(1050, 380)">
    <rect x="0" y="0" width="280" height="180" rx="12" fill="rgba(15,23,42,0.8)" stroke="#334155" stroke-width="1"/>
    <text x="140" y="25" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="12" font-weight="600" fill="#e2e8f0">Architecture Layers</text>
    <rect x="15" y="40" width="18" height="18" rx="4" fill="#1e3a5f" stroke="#3b82f6" stroke-width="1.5"/>
    <text x="45" y="54" font-family="Inter, system-ui, sans-serif" font-size="11" fill="#94a3b8">Frontend / Context</text>
    <rect x="15" y="65" width="18" height="18" rx="4" fill="#1e3a4d" stroke="#06b6d4" stroke-width="1.5"/>
    <text x="45" y="79" font-family="Inter, system-ui, sans-serif" font-size="11" fill="#94a3b8">API Gateway</text>
    <rect x="15" y="90" width="18" height="18" rx="4" fill="#1a2e35" stroke="#14b8a6" stroke-width="1.5"/>
    <text x="45" y="104" font-family="Inter, system-ui, sans-serif" font-size="11" fill="#94a3b8">Multi-Agent System</text>
    <rect x="15" y="115" width="18" height="18" rx="4" fill="#2d1f3d" stroke="#a855f7" stroke-width="1.5"/>
    <text x="45" y="129" font-family="Inter, system-ui, sans-serif" font-size="11" fill="#94a3b8">Security & HITL</text>
    <rect x="15" y="140" width="18" height="18" rx="4" fill="#1f2937" stroke="#6366f1" stroke-width="1.5"/>
    <text x="45" y="154" font-family="Inter, system-ui, sans-serif" font-size="11" fill="#94a3b8">Data Layer</text>
  </g>

  <!-- Footer -->
  <text x="700" y="870" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="11" fill="#64748b">Project Aura Documentation Generator • ADR-060 Enterprise Diagrams</text>
</svg>`;

/**
 * Mock DSL content for AI_PROMPT mode (ADR-060)
 * Reflects Project Aura's actual architecture
 */
const MOCK_DSL_CONTENT = `diagram "Project Aura - Autonomous AI SaaS Platform" {
  // Frontend Layer
  group "Frontend Layer" [color=blue] {
    node "Aura Dashboard" [type=webapp, icon=browser]
    node "Trust Center" [type=webapp, icon=shield]
    node "GPU Scheduler UI" [type=webapp, icon=gpu]
  }

  // API Gateway
  group "API Gateway" [color=cyan] {
    node "FastAPI Gateway" [type=gateway, icon=aws/api-gateway]
    node "Auth Middleware" [type=middleware, icon=aws/cognito]
    node "AWS WAF" [type=security, icon=aws/waf]
  }

  // Multi-Agent System
  group "Multi-Agent System" [color=teal] {
    node "Agent Orchestrator" [type=service, icon=aws/step-functions]
    node "Coder Agent" [type=agent, icon=code]
    node "Reviewer Agent" [type=agent, icon=review]
    node "Validator Agent" [type=agent, icon=check]
  }

  // Context Engineering (GraphRAG)
  group "Context Engineering" [color=blue] {
    node "Context Retrieval Service" [type=service, icon=aws/lambda]
    node "Hybrid GraphRAG" [type=service, icon=graph]
    node "Titan Neural Memory" [type=ml, icon=brain]
    node "RLM Context Engine" [type=ml, icon=aws/sagemaker]
  }

  // Security & HITL
  group "Security & HITL" [color=purple] {
    node "HITL Workflow" [type=workflow, icon=aws/step-functions]
    node "Sandbox Network Service" [type=service, icon=aws/ecs]
    node "Security Services" [type=security, icon=aws/shield]
    node "Constitutional AI" [type=ai, icon=ethics]
  }

  // Data Layer
  group "Data Layer" [color=indigo] {
    node "AWS Neptune" [type=database, icon=aws/neptune]
    node "OpenSearch" [type=database, icon=aws/opensearch]
    node "DynamoDB" [type=database, icon=aws/dynamodb]
    node "S3 Storage" [type=storage, icon=aws/s3]
  }

  // AWS Services
  group "AWS Services" [color=gray] {
    node "AWS Bedrock" [type=ai, icon=aws/bedrock]
    node "AWS Cognito" [type=auth, icon=aws/cognito]
    node "CloudWatch" [type=monitoring, icon=aws/cloudwatch]
    node "EKS/ECS" [type=compute, icon=aws/eks]
  }

  // Connections - Frontend to Gateway
  "Aura Dashboard" -> "FastAPI Gateway"
  "Trust Center" -> "FastAPI Gateway"
  "GPU Scheduler UI" -> "FastAPI Gateway"

  // Gateway chain
  "FastAPI Gateway" -> "Auth Middleware" -> "AWS WAF"

  // Gateway to Agents
  "AWS WAF" -> "Agent Orchestrator"

  // Agent connections
  "Agent Orchestrator" -> "Coder Agent"
  "Agent Orchestrator" -> "Reviewer Agent"
  "Agent Orchestrator" -> "Validator Agent"

  // Agents to Context
  "Agent Orchestrator" -> "Context Retrieval Service"
  "Context Retrieval Service" -> "Hybrid GraphRAG"
  "Hybrid GraphRAG" -> "Titan Neural Memory"
  "Titan Neural Memory" -> "RLM Context Engine"

  // Agents to Security
  "Agent Orchestrator" -> "HITL Workflow"
  "HITL Workflow" -> "Sandbox Network Service"
  "Sandbox Network Service" -> "Security Services"
  "Security Services" -> "Constitutional AI"

  // Context to Data
  "Hybrid GraphRAG" -> "AWS Neptune"
  "Hybrid GraphRAG" -> "OpenSearch"
  "Context Retrieval Service" -> "DynamoDB"

  // Security to Data
  "Sandbox Network Service" -> "S3 Storage"

  // External services
  "Agent Orchestrator" -> "AWS Bedrock"
  "Auth Middleware" -> "AWS Cognito"
  "Security Services" -> "CloudWatch"
  "Sandbox Network Service" -> "EKS/ECS"
}`;

/**
 * Mock diagram templates for all 5 diagram types
 */
const MOCK_DIAGRAMS = {
  architecture: {
    mermaidCode: `graph TB
    subgraph Frontend["Frontend Layer"]
        dashboard([Aura Dashboard])
        trustCenter([Trust Center])
        gpuScheduler([GPU Scheduler UI])
    end

    subgraph Gateway["API Gateway"]
        fastapi([FastAPI Gateway])
        authMw[[Auth Middleware]]
        waf[[AWS WAF]]
    end

    subgraph Agents["Multi-Agent System"]
        orchestrator[[Agent Orchestrator]]
        coderAgent([Coder Agent])
        reviewerAgent([Reviewer Agent])
        validatorAgent([Validator Agent])
    end

    subgraph Context["Context Engineering"]
        contextRetrieval[[Context Retrieval Service]]
        graphRAG([Hybrid GraphRAG])
        titanMemory([Titan Neural Memory])
        rlmEngine([RLM Context Engine])
    end

    subgraph Security["Security Layer"]
        hitlWorkflow[[HITL Workflow]]
        sandboxSvc([Sandbox Network Service])
        securitySvc([Security Services])
        constAI([Constitutional AI])
    end

    subgraph DataLayer["Data Layer"]
        neptune[(AWS Neptune)]
        opensearch[(OpenSearch)]
        dynamodb[(DynamoDB)]
        s3[(S3 Storage)]
    end

    subgraph External["External Services"]
        bedrock{{AWS Bedrock}}
        cognito{{AWS Cognito}}
        cloudwatch{{CloudWatch}}
    end

    Frontend --> Gateway
    Gateway --> Agents
    Agents --> Context
    Agents --> Security
    Context --> DataLayer
    Security --> DataLayer
    Agents --> External

    dashboard --> fastapi
    trustCenter --> fastapi
    gpuScheduler --> fastapi

    fastapi --> authMw
    authMw --> waf
    waf --> orchestrator

    orchestrator --> coderAgent
    orchestrator --> reviewerAgent
    orchestrator --> validatorAgent

    orchestrator --> contextRetrieval
    contextRetrieval --> graphRAG
    graphRAG --> titanMemory
    titanMemory --> rlmEngine

    orchestrator --> hitlWorkflow
    hitlWorkflow --> sandboxSvc
    sandboxSvc --> securitySvc
    securitySvc --> constAI

    graphRAG --> neptune
    graphRAG --> opensearch
    contextRetrieval --> dynamodb
    sandboxSvc --> s3

    orchestrator --> bedrock
    authMw --> cognito
    securitySvc --> cloudwatch

    classDef frontend fill:#1e3a5f,stroke:#3b82f6,stroke-width:1px,color:#e0f2fe
    classDef gateway fill:#1e3a4d,stroke:#06b6d4,stroke-width:1px,color:#cffafe
    classDef agent fill:#1a2e35,stroke:#14b8a6,stroke-width:1px,color:#ccfbf1
    classDef context fill:#1e3a5f,stroke:#3b82f6,stroke-width:1px,color:#e0f2fe
    classDef security fill:#2d1f3d,stroke:#a855f7,stroke-width:1px,color:#f3e8ff
    classDef datastore fill:#1f2937,stroke:#6366f1,stroke-width:1px,color:#e0e7ff
    classDef external fill:#1c1c1e,stroke:#71717a,stroke-width:1px,color:#e4e4e7

    class dashboard,trustCenter,gpuScheduler frontend
    class fastapi,authMw,waf gateway
    class orchestrator,coderAgent,reviewerAgent,validatorAgent agent
    class contextRetrieval,graphRAG,titanMemory,rlmEngine context
    class hitlWorkflow,sandboxSvc,securitySvc,constAI security
    class neptune,opensearch,dynamodb,s3 datastore
    class bedrock,cognito,cloudwatch external`,
    confidence: 0.94,
    confidenceLevel: 'high',
    warnings: [],
  },

  data_flow: {
    mermaidCode: `flowchart LR
    subgraph Input["Data Sources"]
        user([User Request])
        webhook([Webhook Event])
        schedule([Scheduled Job])
    end

    subgraph Processing["Processing Pipeline"]
        validate[Validate Input]
        enrich[Enrich Context]
        transform[Transform Data]
        analyze[AI Analysis]
    end

    subgraph Storage["Data Storage"]
        cache[(Redis Cache)]
        neptune[(Neptune Graph)]
        vector[(OpenSearch Vector)]
        blob[(S3 Bucket)]
    end

    subgraph Output["Outputs"]
        api([API Response])
        notification([Notification])
        report([Report])
    end

    user -->|HTTP POST| validate
    webhook -->|Event Payload| validate
    schedule -->|Cron Trigger| validate

    validate -->|Valid| enrich
    validate -->|Invalid| api

    enrich -->|+Metadata| transform
    enrich -.->|Cache Hit| cache

    transform -->|Normalized| analyze
    transform -->|Store| blob

    analyze -->|Embeddings| vector
    analyze -->|Relations| neptune
    analyze -->|Results| cache

    neptune -->|Query| api
    vector -->|Search| api
    cache -->|Fast Path| api

    api -->|Success| notification
    api -->|Batch| report

    classDef input fill:#e0e7ff,stroke:#4338ca,stroke-width:1px,color:#312e81
    classDef process fill:#fef3c7,stroke:#d97706,stroke-width:1px,color:#78350f
    classDef storage fill:#d1fae5,stroke:#059669,stroke-width:1px,color:#064e3b
    classDef output fill:#fce7f3,stroke:#db2777,stroke-width:1px,color:#831843

    class user,webhook,schedule input
    class validate,enrich,transform,analyze process
    class cache,neptune,vector,blob storage
    class api,notification,report output`,
    confidence: 0.84,
    confidenceLevel: 'high',
    warnings: ['Some async flows inferred from event handlers'],
  },

  dependency: {
    mermaidCode: `graph TD
    subgraph Core["Core Packages"]
        main[main.py]
        config[config/]
        utils[utils/]
    end

    subgraph API["API Layer"]
        endpoints[api/endpoints/]
        middleware[api/middleware/]
        schemas[api/schemas/]
    end

    subgraph Services["Service Layer"]
        auth_svc[services/auth/]
        doc_svc[services/documentation/]
        graph_svc[services/graph/]
        search_svc[services/search/]
    end

    subgraph External["External Dependencies"]
        fastapi[FastAPI]
        pydantic[Pydantic]
        boto3[boto3]
        gremlin[gremlin-python]
        opensearchpy[opensearch-py]
    end

    main --> config
    main --> endpoints
    main --> middleware

    endpoints --> schemas
    endpoints --> auth_svc
    endpoints --> doc_svc
    endpoints --> graph_svc

    middleware --> utils
    middleware --> auth_svc

    auth_svc --> config
    auth_svc --> boto3

    doc_svc --> graph_svc
    doc_svc --> search_svc
    doc_svc --> boto3

    graph_svc --> gremlin
    graph_svc --> config

    search_svc --> opensearchpy
    search_svc --> config

    schemas --> pydantic
    endpoints --> fastapi
    middleware --> fastapi

    classDef core fill:#f3e8ff,stroke:#9333ea,stroke-width:1px,color:#581c87
    classDef api fill:#dbeafe,stroke:#2563eb,stroke-width:1px,color:#1e3a8a
    classDef service fill:#d1fae5,stroke:#059669,stroke-width:1px,color:#064e3b
    classDef external fill:#fef3c7,stroke:#d97706,stroke-width:1px,color:#78350f

    class main,config,utils core
    class endpoints,middleware,schemas api
    class auth_svc,doc_svc,graph_svc,search_svc service
    class fastapi,pydantic,boto3,gremlin,opensearchpy external`,
    confidence: 0.88,
    confidenceLevel: 'high',
    warnings: [],
  },

  sequence: {
    mermaidCode: `sequenceDiagram
    autonumber
    participant U as User
    participant GW as API Gateway
    participant Auth as Auth Service
    participant Doc as Doc Service
    participant Graph as Neptune
    participant AI as Bedrock LLM
    participant Cache as Redis

    U->>+GW: POST /api/v1/documentation/generate
    GW->>+Auth: Validate JWT Token
    Auth-->>-GW: Token Valid (user_id)

    GW->>+Doc: Generate Documentation Request

    Doc->>+Cache: Check cache (repo_id + options)
    alt Cache Hit
        Cache-->>Doc: Cached Result
        Doc-->>GW: Return Cached Documentation
    else Cache Miss
        Cache-->>-Doc: No Cache

        Doc->>+Graph: Query Code Graph
        Graph-->>-Doc: Graph Entities & Relations

        Doc->>+AI: Generate Diagrams (context)
        AI-->>-Doc: Mermaid Diagrams

        Doc->>+AI: Generate Report (context)
        AI-->>-Doc: Technical Report

        Doc->>Cache: Store in Cache (TTL: 1hr)

        Doc-->>-GW: Documentation Result
    end

    GW-->>-U: 200 OK (Documentation JSON)

    Note over U,Cache: Streaming updates sent via SSE during generation`,
    confidence: 0.79,
    confidenceLevel: 'medium',
    warnings: ['Timing estimates based on typical request patterns'],
  },

  component: {
    mermaidCode: `graph TB
    subgraph DocumentationService["Documentation Service"]
        direction TB

        subgraph Public["Public Interface"]
            generate[generate_documentation]
            stream[stream_generation]
            feedback[submit_feedback]
        end

        subgraph Core["Core Components"]
            agent[DocumentationAgent]
            detector[ServiceBoundaryDetector]
            generator[DiagramGenerator]
            reporter[ReportGenerator]
        end

        subgraph Support["Supporting Components"]
            cache[CacheService]
            calibrator[ConfidenceCalibrator]
            validator[OutputValidator]
        end

        subgraph Adapters["External Adapters"]
            graph_adapter[GraphQueryAdapter]
            llm_adapter[LLMClientAdapter]
            storage_adapter[StorageAdapter]
        end
    end

    generate --> agent
    stream --> agent
    feedback --> calibrator

    agent --> detector
    agent --> generator
    agent --> reporter
    agent --> cache

    detector --> graph_adapter
    generator --> llm_adapter
    reporter --> llm_adapter

    generator --> validator
    reporter --> validator
    validator --> calibrator

    cache --> storage_adapter

    classDef public fill:#dbeafe,stroke:#2563eb,stroke-width:1px,color:#1e3a8a
    classDef core fill:#d1fae5,stroke:#059669,stroke-width:1px,color:#064e3b
    classDef support fill:#fef3c7,stroke:#d97706,stroke-width:1px,color:#78350f
    classDef adapter fill:#fce7f3,stroke:#db2777,stroke-width:1px,color:#831843

    class generate,stream,feedback public
    class agent,detector,generator,reporter core
    class cache,calibrator,validator support
    class graph_adapter,llm_adapter,storage_adapter adapter`,
    confidence: 0.86,
    confidenceLevel: 'high',
    warnings: [],
  },
};

/**
 * Mock service boundaries with detailed information
 */
const MOCK_SERVICE_BOUNDARIES = [
  {
    boundaryId: 'service-auth',
    boundary_id: 'svc-bnd-auth-7a8b9c0d',
    name: 'Authentication Service',
    description: 'Handles user authentication, JWT token management, and session handling',
    confidence: 0.92,
    confidenceLevel: 'high',
    nodeCount: 18,
    edgesInternal: 32,
    edgesExternal: 8,
    modularityRatio: 0.80,
    nodes: ['auth_handler', 'token_validator', 'session_manager', 'cognito_client', 'jwt_utils', 'password_hasher'],
    entryPoints: ['login', 'logout', 'refresh_token', 'validate_token'],
    detected_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
    analysis_session_id: 'session-doc-a1b2c3d4',
    analysis_version: '2.4.1',
    organization_id: 'org-acme-corp-7x2',
    team_id: 'team-platform-eng',
    team_name: 'Platform Engineering',
    owner: { user_id: 'usr-k4m9n2p5', email: 'sarah.chen@acme-corp.com', name: 'Sarah Chen' },
    complexity_score: 68,
    cyclomatic_complexity_avg: 4.2,
    health_indicators: { code_quality: 'A', test_coverage: 89.4, tech_debt_hours: 12, security_score: 94 },
    dependencies: { upstream: ['service-api-gateway'], downstream: ['service-graph', 'service-storage'] },
    language_breakdown: { python: 78.5, yaml: 12.3, json: 9.2 },
    last_modified: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
  },
  {
    boundaryId: 'service-api-gateway',
    boundary_id: 'svc-bnd-apigw-8b9c0d1e',
    name: 'API Gateway',
    description: 'Routes incoming requests, applies middleware, and handles rate limiting',
    confidence: 0.89,
    confidenceLevel: 'high',
    nodeCount: 14,
    edgesInternal: 24,
    edgesExternal: 15,
    modularityRatio: 0.62,
    nodes: ['router', 'middleware_chain', 'rate_limiter', 'cors_handler', 'request_logger', 'error_handler'],
    entryPoints: ['handle_request', 'apply_middleware'],
    detected_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
    analysis_session_id: 'session-doc-a1b2c3d4',
    analysis_version: '2.4.1',
    organization_id: 'org-acme-corp-7x2',
    team_id: 'team-platform-eng',
    team_name: 'Platform Engineering',
    owner: { user_id: 'usr-j3l8m1p4', email: 'david.kumar@acme-corp.com', name: 'David Kumar' },
    complexity_score: 52,
    cyclomatic_complexity_avg: 3.1,
    health_indicators: { code_quality: 'A', test_coverage: 92.1, tech_debt_hours: 6, security_score: 97 },
    dependencies: { upstream: [], downstream: ['service-auth', 'service-documentation', 'service-graph', 'service-search'] },
    language_breakdown: { python: 82.1, yaml: 10.4, json: 7.5 },
    last_modified: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString(),
  },
  {
    boundaryId: 'service-documentation',
    boundary_id: 'svc-bnd-docs-9c0d1e2f',
    name: 'Documentation Service',
    description: 'Generates architecture diagrams and technical documentation using AI',
    confidence: 0.87,
    confidenceLevel: 'high',
    nodeCount: 22,
    edgesInternal: 38,
    edgesExternal: 12,
    modularityRatio: 0.76,
    nodes: ['documentation_agent', 'diagram_generator', 'report_generator', 'boundary_detector', 'confidence_scorer', 'cache_service'],
    entryPoints: ['generate_documentation', 'stream_generation', 'submit_feedback'],
    detected_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
    analysis_session_id: 'session-doc-a1b2c3d4',
    analysis_version: '2.4.1',
    organization_id: 'org-acme-corp-7x2',
    team_id: 'team-ai-platform',
    team_name: 'AI Platform Team',
    owner: { user_id: 'usr-m5n2p8q1', email: 'lisa.wang@acme-corp.com', name: 'Lisa Wang' },
    complexity_score: 74,
    cyclomatic_complexity_avg: 5.8,
    health_indicators: { code_quality: 'B', test_coverage: 84.7, tech_debt_hours: 24, security_score: 91 },
    dependencies: { upstream: ['service-api-gateway'], downstream: ['service-graph', 'service-search', 'service-storage'] },
    language_breakdown: { python: 88.2, mermaid: 6.4, json: 5.4 },
    last_modified: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
  },
  {
    boundaryId: 'service-graph',
    boundary_id: 'svc-bnd-graph-0d1e2f3a',
    name: 'Graph Query Service',
    description: 'Interfaces with Neptune graph database for code relationship queries',
    confidence: 0.84,
    confidenceLevel: 'high',
    nodeCount: 12,
    edgesInternal: 18,
    edgesExternal: 10,
    modularityRatio: 0.64,
    nodes: ['graph_client', 'query_builder', 'result_mapper', 'connection_pool', 'retry_handler'],
    entryPoints: ['execute_query', 'traverse_graph', 'get_neighbors'],
    detected_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
    analysis_session_id: 'session-doc-a1b2c3d4',
    analysis_version: '2.4.1',
    organization_id: 'org-acme-corp-7x2',
    team_id: 'team-data-eng',
    team_name: 'Data Engineering',
    owner: { user_id: 'usr-n6p3q9r2', email: 'alex.martinez@acme-corp.com', name: 'Alex Martinez' },
    complexity_score: 58,
    cyclomatic_complexity_avg: 3.9,
    health_indicators: { code_quality: 'A', test_coverage: 91.3, tech_debt_hours: 8, security_score: 93 },
    dependencies: { upstream: ['service-auth', 'service-documentation'], downstream: [] },
    language_breakdown: { python: 76.8, gremlin: 18.2, json: 5.0 },
    last_modified: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
  },
  {
    boundaryId: 'service-search',
    boundary_id: 'svc-bnd-search-1e2f3a4b',
    name: 'Search Service',
    description: 'Provides vector and full-text search capabilities via OpenSearch',
    confidence: 0.81,
    confidenceLevel: 'medium',
    nodeCount: 10,
    edgesInternal: 14,
    edgesExternal: 8,
    modularityRatio: 0.64,
    nodes: ['search_client', 'index_manager', 'query_parser', 'result_ranker', 'embedding_service'],
    entryPoints: ['search', 'index_document', 'delete_document'],
    detected_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
    analysis_session_id: 'session-doc-a1b2c3d4',
    analysis_version: '2.4.1',
    organization_id: 'org-acme-corp-7x2',
    team_id: 'team-search-infra',
    team_name: 'Search Infrastructure',
    owner: { user_id: 'usr-p7q4r0s3', email: 'michael.thompson@acme-corp.com', name: 'Michael Thompson' },
    complexity_score: 61,
    cyclomatic_complexity_avg: 4.1,
    health_indicators: { code_quality: 'B', test_coverage: 79.8, tech_debt_hours: 18, security_score: 88 },
    dependencies: { upstream: ['service-api-gateway', 'service-documentation'], downstream: [] },
    language_breakdown: { python: 74.3, opensearch_dsl: 20.7, json: 5.0 },
    last_modified: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
  },
  {
    boundaryId: 'service-storage',
    boundary_id: 'svc-bnd-storage-2f3a4b5c',
    name: 'Storage Service',
    description: 'Manages file storage and retrieval from S3 and local cache',
    confidence: 0.78,
    confidenceLevel: 'medium',
    nodeCount: 8,
    edgesInternal: 10,
    edgesExternal: 6,
    modularityRatio: 0.63,
    nodes: ['s3_client', 'cache_manager', 'file_processor', 'presigned_url_generator'],
    entryPoints: ['upload', 'download', 'get_presigned_url'],
    detected_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
    analysis_session_id: 'session-doc-a1b2c3d4',
    analysis_version: '2.4.1',
    organization_id: 'org-acme-corp-7x2',
    team_id: 'team-platform-eng',
    team_name: 'Platform Engineering',
    owner: { user_id: 'usr-q8r5s1t4', email: 'jennifer.lee@acme-corp.com', name: 'Jennifer Lee' },
    complexity_score: 42,
    cyclomatic_complexity_avg: 2.8,
    health_indicators: { code_quality: 'A', test_coverage: 88.2, tech_debt_hours: 4, security_score: 96 },
    dependencies: { upstream: ['service-auth', 'service-documentation'], downstream: [] },
    language_breakdown: { python: 81.5, yaml: 11.2, json: 7.3 },
    last_modified: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
  },
];

/**
 * Simulated delay for realistic mock behavior
 */
function mockDelay(ms = 500) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Mock documentation generation with all diagram types
 * Supports both CODE_ANALYSIS (Mermaid) and AI_PROMPT (SVG) modes per ADR-060
 */
async function generateMockDocumentation(repositoryId, options = {}) {
  await mockDelay(1500);

  const {
    diagramTypes = ['architecture', 'data_flow'],
    mode = GenerationMode.CODE_ANALYSIS,
    prompt = '',
    renderEngine = RenderEngine.MERMAID,
  } = options;

  // AI_PROMPT mode: Generate professional SVG diagrams
  if (mode === GenerationMode.AI_PROMPT) {
    // Check if using SVG-based render engine (aura_svg or eraser_api)
    const isSvgEngine = renderEngine === RenderEngine.AURA_SVG ||
                        renderEngine === RenderEngine.ERASER_API ||
                        renderEngine === RenderEngine.ERASER; // legacy alias

    // For AI_PROMPT mode, return SVG-based diagram
    const aiDiagram = {
      diagramType: 'architecture',
      // For SVG engines, return SVG; for mermaid fallback, still include mermaid
      svgContent: isSvgEngine ? MOCK_SVG_DIAGRAM : '',
      dslContent: isSvgEngine ? MOCK_DSL_CONTENT : '',
      mermaidCode: isSvgEngine ? '' : MOCK_DIAGRAMS.architecture.mermaidCode,
      renderEngine: renderEngine,
      confidence: 0.94,
      confidenceLevel: 'high',
      warnings: [],
      prompt: prompt,
      generationMode: mode,
    };

    return {
      jobId: `doc-ai-${Date.now().toString(36)}`,
      repositoryId,
      diagrams: [aiDiagram],
      report: null, // AI_PROMPT mode focuses on diagram generation
      serviceBoundaries: [],
      confidence: 0.94,
      confidenceLevel: 'high',
      generatedAt: new Date().toISOString(),
      generationTimeMs: 3200 + Math.random() * 800,
      cached: false,
      mode: mode,
      renderEngine: renderEngine,
    };
  }

  // CODE_ANALYSIS mode: Traditional Mermaid diagram generation
  // Parse diagram types (can be array or comma-separated string)
  const requestedTypes = Array.isArray(diagramTypes)
    ? diagramTypes
    : diagramTypes.split(',').map((t) => t.trim());

  // Build diagrams array based on requested types
  const diagrams = requestedTypes
    .filter((type) => MOCK_DIAGRAMS[type])
    .map((type) => ({
      diagramType: type,
      ...MOCK_DIAGRAMS[type],
      svgContent: '',
      dslContent: '',
      renderEngine: RenderEngine.MERMAID,
      generationMode: GenerationMode.CODE_ANALYSIS,
    }));

  // Calculate overall confidence
  const avgConfidence =
    diagrams.length > 0
      ? diagrams.reduce((sum, d) => sum + d.confidence, 0) / diagrams.length
      : 0.82;

  return {
    jobId: `doc-${Date.now().toString(36)}`,
    repositoryId,
    diagrams,
    report: getMockReport(repositoryId, diagrams.length),
    serviceBoundaries: MOCK_SERVICE_BOUNDARIES,
    confidence: avgConfidence,
    confidenceLevel: avgConfidence >= 0.85 ? 'high' : avgConfidence >= 0.65 ? 'medium' : 'low',
    generatedAt: new Date().toISOString(),
    generationTimeMs: 2450 + Math.random() * 1000,
    cached: false,
    mode: GenerationMode.CODE_ANALYSIS,
    renderEngine: RenderEngine.MERMAID,
  };
}

/**
 * Mock streaming documentation generation with realistic phases
 */
async function generateMockDocumentationStream(repositoryId, options) {
  const { onProgress, onComplete, diagramTypes = 'architecture,data_flow' } = options;

  // Parse requested diagram types
  const requestedTypes = Array.isArray(diagramTypes)
    ? diagramTypes
    : diagramTypes.split(',').map((t) => t.trim());

  // Build dynamic phases based on requested diagram types
  const phases = [
    { phase: 'analyzing', progress: 5, message: 'Initializing documentation agent...' },
    { phase: 'analyzing', progress: 10, message: 'Loading repository metadata...' },
    { phase: 'analyzing', progress: 15, message: 'Parsing code structure...' },
    { phase: 'detecting_boundaries', progress: 20, message: 'Analyzing module boundaries...' },
    { phase: 'detecting_boundaries', progress: 30, message: 'Running Louvain community detection...' },
    { phase: 'detecting_boundaries', progress: 35, message: 'Detected 6 service boundaries' },
  ];

  // Add diagram generation phases dynamically
  let currentProgress = 40;
  const diagramLabels = {
    architecture: 'architecture',
    data_flow: 'data flow',
    dependency: 'dependency',
    sequence: 'sequence',
    component: 'component',
  };

  requestedTypes.forEach((type, index) => {
    const label = diagramLabels[type] || type;
    phases.push({
      phase: 'generating_diagrams',
      progress: currentProgress,
      message: `Generating ${label} diagram (${index + 1}/${requestedTypes.length})...`,
    });
    currentProgress += Math.floor(30 / requestedTypes.length);
  });

  phases.push(
    { phase: 'generating_diagrams', progress: 70, message: 'Validating diagram syntax...' },
    { phase: 'generating_report', progress: 75, message: 'Generating executive summary...' },
    { phase: 'generating_report', progress: 80, message: 'Analyzing service inventory...' },
    { phase: 'generating_report', progress: 85, message: 'Identifying security considerations...' },
    { phase: 'generating_report', progress: 90, message: 'Compiling recommendations...' },
    { phase: 'generating_report', progress: 95, message: 'Calculating confidence scores...' }
  );

  const totalSteps = phases.length;

  for (let i = 0; i < phases.length; i++) {
    await mockDelay(400 + Math.random() * 300); // Variable delay for realism
    onProgress?.({
      ...phases[i],
      currentStep: i + 1,
      totalSteps: totalSteps + 1,
      metadata: {
        elapsedMs: (i + 1) * 500,
        estimatedRemainingMs: (totalSteps - i) * 500,
      },
    });
  }

  await mockDelay(300);

  const result = await generateMockDocumentation(repositoryId, { ...options, diagramTypes: requestedTypes });
  onComplete?.(result);
  return result;
}

/**
 * Generate structured mock report (used by UI)
 */
function getMockReport(repositoryId, diagramCount) {
  const repoName = MOCK_REPOSITORIES.find((r) => r.repository_id === repositoryId)?.name || repositoryId;

  return {
    title: `Technical Documentation: ${repoName}`,
    executiveSummary:
      `This automated technical documentation provides a comprehensive analysis of the ${repoName} codebase. ` +
      `The analysis identified 6 service boundaries, 18 data flows, and generated ${diagramCount} diagram(s). ` +
      `Overall documentation confidence is 86% (high), indicating strong accuracy in the detected architecture. ` +
      `Key findings include well-defined service boundaries with clear separation of concerns, ` +
      `though some areas would benefit from additional inline documentation.`,
    summaryConfidence: 0.88,
    serviceInventory:
      `The codebase is organized into 6 distinct services:\n\n` +
      `• **Authentication Service** - Handles user authentication, JWT management, and session handling (18 components)\n` +
      `• **API Gateway** - Routes requests, applies middleware, handles rate limiting (14 components)\n` +
      `• **Documentation Service** - Generates diagrams and reports using AI (22 components)\n` +
      `• **Graph Query Service** - Interfaces with Neptune for code relationships (12 components)\n` +
      `• **Search Service** - Vector and full-text search via OpenSearch (10 components)\n` +
      `• **Storage Service** - File storage and retrieval from S3 (8 components)`,
    dataFlowAnalysis:
      `The system processes data through three primary flows:\n\n` +
      `**1. User Request Flow:** User → API Gateway → Auth → Service → Database → Response\n` +
      `**2. Async Processing Flow:** Event → Queue → Worker → Storage → Notification\n` +
      `**3. Search & Retrieval Flow:** Query → Cache Check → Vector Search → Graph Enrichment → Results\n\n` +
      `Data is persisted across PostgreSQL (transactional), Neptune (graph relationships), ` +
      `OpenSearch (vector embeddings), and S3 (blob storage). Redis provides caching at multiple layers.`,
    securityConsiderations: [
      'All API endpoints require JWT authentication with token refresh support',
      'Service-to-service communication uses mTLS within the VPC',
      'Sensitive data is encrypted at rest using AWS KMS customer-managed keys',
      'Input validation is applied at the API Gateway level before routing',
      'Rate limiting prevents abuse with configurable thresholds per endpoint',
      'Audit logging captures all authentication and authorization events',
    ],
    recommendations: [
      'Add OpenAPI documentation for 3 undocumented internal endpoints',
      'Consider implementing circuit breaker pattern for external service calls',
      'Increase test coverage in the Storage Service (currently 68%)',
      'Add structured logging with correlation IDs for distributed tracing',
      'Document the async event processing flow in ADR format',
      'Review rate limit thresholds based on actual usage patterns',
    ],
    confidence: 0.86,
    confidenceLevel: 'high',
    sectionCount: 6,
    generatedAt: new Date().toISOString(),
  };
}

/**
 * Generate mock report markdown (legacy format)
 */
function getMockReportMarkdown(repositoryId) {
  const report = getMockReport(repositoryId, 2);
  return `# ${report.title}

## Executive Summary

${report.executiveSummary}

## Service Inventory

${report.serviceInventory}

## Data Flow Analysis

${report.dataFlowAnalysis}

## Security Considerations

${report.securityConsiderations.map((item) => `- ${item}`).join('\n')}

## Recommendations

${report.recommendations.map((item, i) => `${i + 1}. ${item}`).join('\n')}

---

*Generated on ${new Date().toLocaleDateString()} with ${Math.round(report.confidence * 100)}% confidence*
`;
}

/**
 * Mock cache stats
 */
function getMockCacheStats() {
  return {
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    collected_at: new Date().toISOString(),
    collection_period: { start: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(), end: new Date().toISOString(), duration_hours: 24 },
    memory: {
      hits: 1847,
      misses: 423,
      hitRate: 0.814,
      total_requests: 2270,
      size_bytes: 52428800,
      size_mb: 50,
      max_size_mb: 256,
      utilization_percent: 19.5,
      entries_count: 892,
      avg_entry_size_bytes: 58775,
      evictions_24h: 47,
      eviction_policy: 'lru',
      ttl_default_seconds: 3600,
      avg_latency_ms: 0.8,
      p99_latency_ms: 2.1,
    },
    redis: {
      hits: 8934,
      misses: 2156,
      hitRate: 0.806,
      total_requests: 11090,
      size_bytes: 524288000,
      size_mb: 500,
      max_size_mb: 2048,
      utilization_percent: 24.4,
      entries_count: 4521,
      avg_entry_size_bytes: 115982,
      evictions_24h: 234,
      eviction_policy: 'volatile-lru',
      ttl_default_seconds: 7200,
      avg_latency_ms: 1.2,
      p99_latency_ms: 4.7,
      cluster_nodes: 3,
      replication_lag_ms: 0.3,
      connected_clients: 42,
    },
    s3: {
      hits: 2847,
      misses: 589,
      hitRate: 0.829,
      total_requests: 3436,
      size_bytes: 10737418240,
      size_gb: 10,
      storage_class: 'STANDARD',
      entries_count: 15234,
      avg_entry_size_bytes: 705012,
      ttl_default_days: 30,
      avg_latency_ms: 45,
      p99_latency_ms: 180,
      bucket_name: 'aura-documentation-cache-prod',
      region: 'us-east-1',
      cost_estimate_monthly_usd: 0.23,
    },
    total: {
      hits: 13628,
      misses: 3168,
      hitRate: 0.811,
      total_requests: 16796,
      bytes_served: 4294967296,
      bytes_served_gb: 4,
      avg_response_time_ms: 12.4,
      cost_savings_estimate_usd: 847.50,
    },
    top_cached_repositories: [
      { repository_id: 'repo-aura-core-1a2', name: 'aura-core', hits: 2341, hit_rate: 0.89 },
      { repository_id: 'repo-payment-svc-2b3', name: 'payment-service', hits: 1892, hit_rate: 0.84 },
      { repository_id: 'repo-user-mgmt-3c4', name: 'user-management', hits: 1456, hit_rate: 0.81 },
      { repository_id: 'repo-analytics-4d5', name: 'analytics-pipeline', hits: 1123, hit_rate: 0.78 },
    ],
    health: {
      status: 'healthy',
      last_health_check: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
      memory_status: 'healthy',
      redis_status: 'healthy',
      s3_status: 'healthy',
      alerts_active: 0,
    },
  };
}

// Export default object for convenience
export default {
  generateDocumentation,
  generateDocumentationStream,
  submitFeedback,
  getCacheStats,
  invalidateCache,
  getDiagramTypes,
  ConfidenceLevel,
  getConfidenceLevel,
  getConfidenceColor,
  DiagramType,
  GenerationMode,
  RenderEngine,
  DocumentationApiError,
  MOCK_REPOSITORIES,
};
