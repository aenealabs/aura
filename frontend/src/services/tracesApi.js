/**
 * Project Aura - Traces API Service
 *
 * Client-side service for OpenTelemetry trace exploration and analysis.
 * Provides access to trace data for the Trace Explorer dashboard (Issue #30).
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

/**
 * Custom error class for Traces API errors
 */
export class TracesApiError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.name = 'TracesApiError';
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
    throw new TracesApiError(
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

/**
 * Span kind types
 */
export const SpanKind = {
  AGENT: 'agent',
  LLM: 'llm',
  TOOL: 'tool',
  INTERNAL: 'internal',
};

/**
 * Trace status types
 */
export const TraceStatus = {
  SUCCESS: 'success',
  ERROR: 'error',
  TIMEOUT: 'timeout',
};

/**
 * Agent types for filtering
 */
export const AgentType = {
  CODER: 'coder',
  REVIEWER: 'reviewer',
  VALIDATOR: 'validator',
  ORCHESTRATOR: 'orchestrator',
  SECURITY: 'security',
};

/**
 * Time period options for filtering
 */
export const TimePeriod = {
  HOUR_1: '1h',
  HOUR_6: '6h',
  HOUR_24: '24h',
  DAY_7: '7d',
  DAY_30: '30d',
};

/**
 * Span kind colors for visualization
 */
export const SPAN_COLORS = {
  [SpanKind.AGENT]: '#3B82F6',    // Blue
  [SpanKind.LLM]: '#8B5CF6',      // Violet
  [SpanKind.TOOL]: '#F59E0B',     // Amber
  [SpanKind.INTERNAL]: '#6B7280', // Gray
};

/**
 * Status colors for badges
 */
export const STATUS_COLORS = {
  [TraceStatus.SUCCESS]: {
    bg: 'bg-olive-100 dark:bg-olive-900/30',
    text: 'text-olive-700 dark:text-olive-300',
    border: 'border-olive-200 dark:border-olive-800',
  },
  [TraceStatus.ERROR]: {
    bg: 'bg-critical-100 dark:bg-critical-900/30',
    text: 'text-critical-700 dark:text-critical-300',
    border: 'border-critical-200 dark:border-critical-800',
  },
  [TraceStatus.TIMEOUT]: {
    bg: 'bg-warning-100 dark:bg-warning-900/30',
    text: 'text-warning-700 dark:text-warning-300',
    border: 'border-warning-200 dark:border-warning-800',
  },
};

/**
 * Agent type display info
 */
export const AGENT_TYPE_INFO = {
  [AgentType.CODER]: { label: 'Coder', icon: 'Code' },
  [AgentType.REVIEWER]: { label: 'Reviewer', icon: 'Search' },
  [AgentType.VALIDATOR]: { label: 'Validator', icon: 'CheckCircle' },
  [AgentType.ORCHESTRATOR]: { label: 'Orchestrator', icon: 'GitBranch' },
  [AgentType.SECURITY]: { label: 'Security', icon: 'Shield' },
};

/**
 * Default metrics for fallback
 */
export const DEFAULT_METRICS = {
  total_traces: 247,
  avg_latency_ms: 2340,
  error_rate: 3.2,
  coverage: 94.7,
  traces_by_status: { success: 231, error: 8, timeout: 8 },
  traces_by_agent: {
    coder: 89,
    reviewer: 67,
    validator: 45,
    orchestrator: 31,
    security: 15,
  },
  latency_histogram: [
    { bucket: '0-100ms', count: 12 },
    { bucket: '100-500ms', count: 45 },
    { bucket: '500ms-1s', count: 78 },
    { bucket: '1-2s', count: 62 },
    { bucket: '2-5s', count: 38 },
    { bucket: '5s+', count: 12 },
  ],
  period: '24h',
};

/**
 * Generate realistic timestamps
 */
function generateTimestamps(baseTime, durationMs) {
  const start = new Date(baseTime);
  const end = new Date(start.getTime() + durationMs);
  return {
    start_time: start.toISOString(),
    end_time: end.toISOString(),
  };
}

/**
 * Mock trace data for development
 */
const MOCK_TRACES = (() => {
  const now = Date.now();
  const hour = 3600000;

  return [
    {
      trace_id: 'trace-001-abc123',
      name: 'Security Patch Generation - CVE-2024-1234',
      agent_type: 'coder',
      status: 'success',
      duration_ms: 4532,
      span_count: 12,
      error_count: 0,
      ...generateTimestamps(now - hour * 0.5, 4532),
    },
    {
      trace_id: 'trace-002-def456',
      name: 'Code Review - PR #892 XSS Vulnerability',
      agent_type: 'reviewer',
      status: 'success',
      duration_ms: 2187,
      span_count: 8,
      error_count: 0,
      ...generateTimestamps(now - hour * 1, 2187),
    },
    {
      trace_id: 'trace-003-ghi789',
      name: 'Sandbox Validation - Patch Test Suite',
      agent_type: 'validator',
      status: 'success',
      duration_ms: 8921,
      span_count: 15,
      error_count: 0,
      ...generateTimestamps(now - hour * 1.5, 8921),
    },
    {
      trace_id: 'trace-004-jkl012',
      name: 'Multi-Agent Orchestration - Incident IR-2024-089',
      agent_type: 'orchestrator',
      status: 'success',
      duration_ms: 12453,
      span_count: 24,
      error_count: 0,
      ...generateTimestamps(now - hour * 2, 12453),
    },
    {
      trace_id: 'trace-005-mno345',
      name: 'Security Scan - Repository aura-core',
      agent_type: 'security',
      status: 'error',
      duration_ms: 3421,
      span_count: 6,
      error_count: 1,
      error_message: 'Rate limit exceeded for vulnerability database',
      ...generateTimestamps(now - hour * 2.5, 3421),
    },
    {
      trace_id: 'trace-006-pqr678',
      name: 'Patch Generation - SQL Injection Fix',
      agent_type: 'coder',
      status: 'success',
      duration_ms: 5678,
      span_count: 14,
      error_count: 0,
      ...generateTimestamps(now - hour * 3, 5678),
    },
    {
      trace_id: 'trace-007-stu901',
      name: 'Code Review - Authentication Module',
      agent_type: 'reviewer',
      status: 'timeout',
      duration_ms: 30000,
      span_count: 4,
      error_count: 1,
      error_message: 'LLM response timeout after 30s',
      ...generateTimestamps(now - hour * 4, 30000),
    },
    {
      trace_id: 'trace-008-vwx234',
      name: 'Dependency Update - npm audit fix',
      agent_type: 'coder',
      status: 'success',
      duration_ms: 1892,
      span_count: 7,
      error_count: 0,
      ...generateTimestamps(now - hour * 5, 1892),
    },
    {
      trace_id: 'trace-009-yza567',
      name: 'SAST Analysis - Critical Path Review',
      agent_type: 'security',
      status: 'success',
      duration_ms: 6234,
      span_count: 11,
      error_count: 0,
      ...generateTimestamps(now - hour * 6, 6234),
    },
    {
      trace_id: 'trace-010-bcd890',
      name: 'Integration Test Validation',
      agent_type: 'validator',
      status: 'error',
      duration_ms: 4521,
      span_count: 9,
      error_count: 2,
      error_message: 'Test assertion failed: expected 200, got 500',
      ...generateTimestamps(now - hour * 7, 4521),
    },
  ];
})();

/**
 * Generate mock spans for a trace
 */
function generateMockSpans(traceId, agentType) {
  const now = Date.now();
  const baseTime = now - 5000;

  const spans = [
    {
      span_id: `${traceId}-span-001`,
      trace_id: traceId,
      parent_span_id: null,
      name: `${agentType.charAt(0).toUpperCase() + agentType.slice(1)} Agent Execution`,
      kind: SpanKind.AGENT,
      status: 'success',
      ...generateTimestamps(baseTime, 4500),
      duration_ms: 4500,
      attributes: {
        'agent.type': agentType,
        'agent.version': '2.1.0',
        'task.id': 'task-' + Math.random().toString(36).substr(2, 9),
      },
    },
    {
      span_id: `${traceId}-span-002`,
      trace_id: traceId,
      parent_span_id: `${traceId}-span-001`,
      name: 'Context Retrieval - GraphRAG Query',
      kind: SpanKind.TOOL,
      status: 'success',
      ...generateTimestamps(baseTime + 100, 450),
      duration_ms: 450,
      attributes: {
        'tool.name': 'graphrag_query',
        'query.type': 'hybrid',
        'results.count': 15,
      },
    },
    {
      span_id: `${traceId}-span-003`,
      trace_id: traceId,
      parent_span_id: `${traceId}-span-001`,
      name: 'LLM Inference - Claude 3.5 Sonnet',
      kind: SpanKind.LLM,
      status: 'success',
      ...generateTimestamps(baseTime + 600, 2800),
      duration_ms: 2800,
      attributes: {
        'llm.model': 'claude-3-5-sonnet',
        'llm.provider': 'bedrock',
        'tokens.input': 4521,
        'tokens.output': 1893,
        'tokens.total': 6414,
      },
    },
    {
      span_id: `${traceId}-span-004`,
      trace_id: traceId,
      parent_span_id: `${traceId}-span-003`,
      name: 'Prompt Construction',
      kind: SpanKind.INTERNAL,
      status: 'success',
      ...generateTimestamps(baseTime + 600, 120),
      duration_ms: 120,
      attributes: {
        'prompt.template': 'security_patch_v2',
        'context.chunks': 8,
      },
    },
    {
      span_id: `${traceId}-span-005`,
      trace_id: traceId,
      parent_span_id: `${traceId}-span-003`,
      name: 'Response Parsing',
      kind: SpanKind.INTERNAL,
      status: 'success',
      ...generateTimestamps(baseTime + 3300, 80),
      duration_ms: 80,
      attributes: {
        'parser.type': 'structured_output',
        'validation.passed': true,
      },
    },
    {
      span_id: `${traceId}-span-006`,
      trace_id: traceId,
      parent_span_id: `${traceId}-span-001`,
      name: 'Tool Call - Code Generation',
      kind: SpanKind.TOOL,
      status: 'success',
      ...generateTimestamps(baseTime + 3500, 650),
      duration_ms: 650,
      attributes: {
        'tool.name': 'code_generator',
        'language': 'python',
        'lines.generated': 47,
      },
    },
    {
      span_id: `${traceId}-span-007`,
      trace_id: traceId,
      parent_span_id: `${traceId}-span-001`,
      name: 'Tool Call - Static Analysis',
      kind: SpanKind.TOOL,
      status: 'success',
      ...generateTimestamps(baseTime + 4200, 280),
      duration_ms: 280,
      attributes: {
        'tool.name': 'bandit_scanner',
        'issues.found': 0,
        'severity.max': 'none',
      },
    },
  ];

  return spans;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Check if error indicates API is unavailable (use mock data)
 */
function shouldUseMockData(error) {
  // Network errors, CORS, 404, or any fetch failure
  return (
    error.status === 404 ||
    error.message?.includes('Failed to fetch') ||
    error.message?.includes('NetworkError') ||
    error.message?.includes('CORS') ||
    error.name === 'TypeError' ||
    !API_BASE_URL ||
    API_BASE_URL === '/api/v1' // No real backend configured
  );
}

/**
 * Get trace metrics summary
 *
 * @param {string} period - Time period: 1h, 6h, 24h, 7d, 30d
 * @returns {Promise<Object>} Trace metrics
 */
export async function getTraceMetrics(period = '24h') {
  // Use mock data directly if no API is configured
  if (!API_BASE_URL || API_BASE_URL === '/api/v1') {
    return { ...DEFAULT_METRICS, period };
  }

  try {
    return await fetchApi(`/traces/metrics?period=${period}`);
  } catch (error) {
    if (shouldUseMockData(error)) {
      console.warn('Trace metrics endpoint not available, using mock data');
      return { ...DEFAULT_METRICS, period };
    }
    throw error;
  }
}

/**
 * List traces with filtering and pagination
 *
 * @param {Object} options - Filter options
 * @param {number} options.page - Page number (1-based)
 * @param {number} options.pageSize - Items per page
 * @param {string} options.status - Status filter
 * @param {string} options.agentType - Agent type filter
 * @param {number} options.minDurationMs - Minimum duration filter
 * @param {number} options.maxDurationMs - Maximum duration filter
 * @param {string} options.period - Time period filter
 * @param {string} options.search - Search query
 * @returns {Promise<Object>} Paginated trace list
 */
export async function listTraces({
  page = 1,
  pageSize = 20,
  status = null,
  agentType = null,
  minDurationMs = null,
  maxDurationMs = null,
  period = '24h',
  search = null,
} = {}) {
  // Helper function to return filtered mock data
  const getMockData = () => {
    let filteredTraces = [...MOCK_TRACES];
    if (status) {
      filteredTraces = filteredTraces.filter(t => t.status === status);
    }
    if (agentType) {
      filteredTraces = filteredTraces.filter(t => t.agent_type === agentType);
    }
    if (search) {
      const searchLower = search.toLowerCase();
      filteredTraces = filteredTraces.filter(t =>
        t.name.toLowerCase().includes(searchLower)
      );
    }
    return {
      traces: filteredTraces,
      total: filteredTraces.length,
      page: 1,
      page_size: pageSize,
      has_more: false
    };
  };

  // Use mock data directly if no API is configured
  if (!API_BASE_URL || API_BASE_URL === '/api/v1') {
    return getMockData();
  }

  try {
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
      period,
    });

    if (status) params.set('status', status);
    if (agentType) params.set('agent_type', agentType);
    if (minDurationMs !== null) params.set('min_duration_ms', minDurationMs.toString());
    if (maxDurationMs !== null) params.set('max_duration_ms', maxDurationMs.toString());
    if (search) params.set('search', search);

    return await fetchApi(`/traces?${params.toString()}`);
  } catch (error) {
    if (shouldUseMockData(error)) {
      console.warn('Traces endpoint not available, using mock data');
      return getMockData();
    }
    throw error;
  }
}

/**
 * Get full trace with all spans
 *
 * @param {string} traceId - Trace identifier
 * @returns {Promise<Object>} Full trace data
 */
export async function getTrace(traceId) {
  // Helper function to return mock trace data
  const getMockTrace = () => {
    const trace = MOCK_TRACES.find(t => t.trace_id === traceId);
    if (trace) {
      const spans = generateMockSpans(traceId, trace.agent_type);
      return {
        ...trace,
        spans,
      };
    }
    // Return a default mock trace if not found
    return {
      trace_id: traceId,
      name: 'Mock Trace',
      agent_type: 'coder',
      status: 'success',
      duration_ms: 4500,
      span_count: 7,
      start_time: new Date(Date.now() - 5000).toISOString(),
      end_time: new Date().toISOString(),
      spans: generateMockSpans(traceId, 'coder'),
    };
  };

  // Use mock data directly if no API is configured
  if (!API_BASE_URL || API_BASE_URL === '/api/v1') {
    return getMockTrace();
  }

  try {
    return await fetchApi(`/traces/${traceId}`);
  } catch (error) {
    if (shouldUseMockData(error)) {
      console.warn('Trace endpoint not available, using mock data');
      return getMockTrace();
    }
    throw error;
  }
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Format duration for display
 *
 * @param {number} ms - Duration in milliseconds
 * @returns {string} Formatted duration string
 */
export function formatDuration(ms) {
  if (ms < 1) {
    return `${(ms * 1000).toFixed(0)}μs`;
  }
  if (ms < 1000) {
    return `${ms.toFixed(0)}ms`;
  }
  if (ms < 60000) {
    return `${(ms / 1000).toFixed(2)}s`;
  }
  const minutes = Math.floor(ms / 60000);
  const seconds = ((ms % 60000) / 1000).toFixed(0);
  return `${minutes}m ${seconds}s`;
}

/**
 * Format timestamp for display
 *
 * @param {string} isoString - ISO timestamp
 * @param {boolean} includeTime - Include time portion
 * @returns {string} Formatted timestamp
 */
export function formatTimestamp(isoString, includeTime = true) {
  const date = new Date(isoString);
  const options = {
    month: 'short',
    day: 'numeric',
    ...(includeTime && { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
  };
  return date.toLocaleString('en-US', options);
}

/**
 * Format relative time (e.g., "5 minutes ago")
 *
 * @param {string} isoString - ISO timestamp
 * @returns {string} Relative time string
 */
export function formatRelativeTime(isoString) {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now - date;
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSeconds < 60) return 'just now';
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return formatTimestamp(isoString, false);
}

/**
 * Build span tree from flat span list
 *
 * @param {Array} spans - Flat list of spans
 * @returns {Array} Tree structure with children
 */
export function buildSpanTree(spans) {
  if (!spans || spans.length === 0) return [];

  const spanMap = new Map();
  const roots = [];

  // First pass: create map of all spans
  spans.forEach(span => {
    spanMap.set(span.span_id, { ...span, children: [] });
  });

  // Second pass: build tree structure
  spans.forEach(span => {
    const node = spanMap.get(span.span_id);
    if (span.parent_span_id && spanMap.has(span.parent_span_id)) {
      spanMap.get(span.parent_span_id).children.push(node);
    } else {
      roots.push(node);
    }
  });

  // Sort children by start time
  const sortChildren = (node) => {
    node.children.sort((a, b) => new Date(a.start_time) - new Date(b.start_time));
    node.children.forEach(sortChildren);
  };

  roots.forEach(sortChildren);
  roots.sort((a, b) => new Date(a.start_time) - new Date(b.start_time));

  return roots;
}

/**
 * Flatten span tree back to array (depth-first)
 *
 * @param {Array} tree - Tree structure
 * @param {number} depth - Current depth (internal)
 * @returns {Array} Flat array with depth info
 */
export function flattenSpanTree(tree, depth = 0) {
  const result = [];

  tree.forEach(node => {
    result.push({ ...node, depth });
    if (node.children && node.children.length > 0) {
      result.push(...flattenSpanTree(node.children, depth + 1));
    }
  });

  return result;
}

/**
 * Calculate timeline scale for span visualization
 *
 * @param {Array} spans - List of spans
 * @returns {Object} Scale info with minTime, maxTime, totalMs
 */
export function calculateTimelineScale(spans) {
  if (!spans || spans.length === 0) {
    return { minTime: 0, maxTime: 0, totalMs: 0 };
  }

  const times = spans.flatMap(s => [
    new Date(s.start_time).getTime(),
    new Date(s.end_time).getTime(),
  ]);

  const minTime = Math.min(...times);
  const maxTime = Math.max(...times);
  const totalMs = maxTime - minTime;

  return { minTime, maxTime, totalMs };
}

/**
 * Calculate span position as percentage of timeline
 *
 * @param {Object} span - Span object
 * @param {Object} scale - Timeline scale from calculateTimelineScale
 * @returns {Object} Position with left and width percentages
 */
export function calculateSpanPosition(span, scale) {
  if (scale.totalMs === 0) {
    return { left: 0, width: 100 };
  }

  const startTime = new Date(span.start_time).getTime();
  const endTime = new Date(span.end_time).getTime();

  const left = ((startTime - scale.minTime) / scale.totalMs) * 100;
  const width = Math.max(((endTime - startTime) / scale.totalMs) * 100, 0.5); // Min 0.5% width

  return { left, width };
}
