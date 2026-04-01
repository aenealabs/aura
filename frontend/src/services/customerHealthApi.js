/**
 * Project Aura - Customer Health API Service
 *
 * Client-side service for retrieving customer health metrics.
 * Supports both SaaS (multi-tenant) and self-hosted (single-tenant) modes.
 */

// API base URL - uses Vite's environment variable or defaults to relative path
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

/**
 * Custom error class for Customer Health API errors
 */
export class CustomerHealthApiError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.name = 'CustomerHealthApiError';
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
    throw new CustomerHealthApiError(
      errorData.detail || errorData.error || `API error: ${response.status}`,
      response.status,
      errorData
    );
  }

  return response.json();
}

/**
 * Time range options for metrics
 */
export const TimeRanges = {
  HOUR: '1h',
  DAY: '24h',
  WEEK: '7d',
  MONTH: '30d',
};

/**
 * Health status thresholds
 */
export const HealthStatus = {
  HEALTHY: 'healthy',
  DEGRADED: 'degraded',
  UNHEALTHY: 'unhealthy',
};

/**
 * Incident severity levels
 */
export const IncidentSeverity = {
  CRITICAL: 'critical',
  HIGH: 'high',
  MEDIUM: 'medium',
  LOW: 'low',
};

/**
 * Incident status types
 */
export const IncidentStatus = {
  ACTIVE: 'active',
  ACKNOWLEDGED: 'acknowledged',
  RESOLVED: 'resolved',
};

// ============================================================================
// Health Overview API
// ============================================================================

/**
 * Get overall health overview including score, trend, and component status
 *
 * @param {string} timeRange - Time range for trend data (1h, 24h, 7d, 30d)
 * @returns {Promise<Object>} Health overview with score, trend, and components
 */
export async function getHealthOverview(timeRange = '24h') {
  try {
    const params = new URLSearchParams({ time_range: timeRange });
    return await fetchApi(`/health/overview?${params}`);
  } catch (error) {
    // Return mock data for any error (network failures, 404, etc.)
    console.warn('Using mock health overview (API unavailable)');
    return getMockHealthOverview(timeRange);
  }
}

/**
 * Get detailed health metrics for a specific component
 *
 * @param {string} componentId - Component identifier (api, agents, storage, etc.)
 * @param {string} timeRange - Time range for metrics
 * @returns {Promise<Object>} Detailed component health metrics
 */
export async function getComponentHealth(componentId, timeRange = '24h') {
  try {
    const params = new URLSearchParams({ time_range: timeRange });
    return await fetchApi(`/health/components/${componentId}?${params}`);
  } catch (error) {
    // Return mock data for any error (network failures, 404, etc.)
    console.warn(`Using mock component health for ${componentId} (API unavailable)`);
    return getMockComponentHealth(componentId, timeRange);
  }
}

/**
 * Get historical health data for charts
 *
 * @param {number} days - Number of days of history to retrieve
 * @param {string} resolution - Data resolution (hourly, daily)
 * @returns {Promise<Object>} Historical health data with timestamps and scores
 */
export async function getHealthHistory(days = 30, resolution = 'daily') {
  try {
    const params = new URLSearchParams({
      days: days.toString(),
      resolution,
    });
    return await fetchApi(`/health/history?${params}`);
  } catch (error) {
    // Return mock data for any error (network failures, 404, etc.)
    console.warn('Using mock health history (API unavailable)');
    return getMockHealthHistory(days, resolution);
  }
}

// ============================================================================
// Incidents API
// ============================================================================

/**
 * Get active and recent incidents
 *
 * @param {Object} options - Query options
 * @param {string} options.status - Filter by status (active, acknowledged, resolved)
 * @param {string} options.severity - Filter by severity (critical, high, medium, low)
 * @param {number} options.limit - Maximum number of incidents to return
 * @param {number} options.offset - Pagination offset
 * @returns {Promise<Object>} Incidents with pagination info
 */
export async function getIncidents(options = {}) {
  try {
    const params = new URLSearchParams();
    if (options.status) params.append('status', options.status);
    if (options.severity) params.append('severity', options.severity);
    if (options.limit) params.append('limit', options.limit.toString());
    if (options.offset) params.append('offset', options.offset.toString());

    return await fetchApi(`/health/incidents?${params}`);
  } catch (error) {
    // Return mock data for any error (network failures, 404, etc.)
    console.warn('Using mock incidents data (API unavailable)');
    return getMockIncidents(options);
  }
}

/**
 * Acknowledge an incident
 *
 * @param {string} incidentId - Incident identifier
 * @param {string} notes - Optional acknowledgement notes
 * @returns {Promise<Object>} Updated incident
 */
export async function acknowledgeIncident(incidentId, notes = '') {
  try {
    return await fetchApi(`/health/incidents/${incidentId}/acknowledge`, {
      method: 'POST',
      body: JSON.stringify({ notes }),
    });
  } catch (error) {
    if (error.status === 404) {
      // Return mock acknowledged incident for development
      return {
        id: incidentId,
        status: 'acknowledged',
        acknowledged_at: new Date().toISOString(),
        acknowledged_by: 'current-user',
        notes,
      };
    }
    throw error;
  }
}

/**
 * Resolve an incident
 *
 * @param {string} incidentId - Incident identifier
 * @param {string} resolution - Resolution notes
 * @returns {Promise<Object>} Updated incident
 */
export async function resolveIncident(incidentId, resolution = '') {
  try {
    return await fetchApi(`/health/incidents/${incidentId}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ resolution }),
    });
  } catch (error) {
    if (error.status === 404) {
      return {
        id: incidentId,
        status: 'resolved',
        resolved_at: new Date().toISOString(),
        resolved_by: 'current-user',
        resolution,
      };
    }
    throw error;
  }
}

// ============================================================================
// Recommendations API
// ============================================================================

/**
 * Get AI-generated health recommendations
 *
 * @param {string} category - Filter by category (performance, security, cost, reliability)
 * @returns {Promise<Array>} List of recommendations
 */
export async function getRecommendations(category = null) {
  try {
    const params = new URLSearchParams();
    if (category) params.append('category', category);
    return await fetchApi(`/health/recommendations?${params}`);
  } catch (error) {
    // Return mock data for any error (network failures, 404, etc.)
    console.warn('Using mock recommendations (API unavailable)');
    return getMockRecommendations(category);
  }
}

/**
 * Dismiss a recommendation
 *
 * @param {string} recommendationId - Recommendation identifier
 * @param {string} reason - Reason for dismissal
 * @returns {Promise<Object>} Confirmation
 */
export async function dismissRecommendation(recommendationId, reason = '') {
  try {
    return await fetchApi(`/health/recommendations/${recommendationId}/dismiss`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    });
  } catch (error) {
    if (error.status === 404) {
      return { id: recommendationId, dismissed: true };
    }
    throw error;
  }
}

// ============================================================================
// Health Report Export
// ============================================================================

/**
 * Export health report as PDF or CSV
 *
 * @param {Object} options - Export options
 * @param {string} options.format - Export format (pdf, csv, json)
 * @param {string} options.dateFrom - Start date for report
 * @param {string} options.dateTo - End date for report
 * @param {Array<string>} options.sections - Sections to include
 * @returns {Promise<Blob>} Report file blob
 */
export async function exportHealthReport(options = {}) {
  const { format = 'pdf', dateFrom, dateTo, sections = ['overview', 'incidents', 'recommendations'] } = options;

  try {
    const params = new URLSearchParams({
      format,
      sections: sections.join(','),
    });
    if (dateFrom) params.append('date_from', dateFrom);
    if (dateTo) params.append('date_to', dateTo);

    const response = await fetch(`${API_BASE_URL}/health/export?${params}`, {
      headers: {
        'Accept': format === 'pdf' ? 'application/pdf' : format === 'csv' ? 'text/csv' : 'application/json',
      },
    });

    if (!response.ok) {
      throw new CustomerHealthApiError('Failed to export report', response.status);
    }

    return await response.blob();
  } catch (error) {
    if (error.status === 404) {
      // Return mock data as JSON for development
      const mockData = {
        generated_at: new Date().toISOString(),
        overview: getMockHealthOverview('30d'),
        incidents: getMockIncidents({ limit: 50 }),
        recommendations: getMockRecommendations(),
      };
      return new Blob([JSON.stringify(mockData, null, 2)], { type: 'application/json' });
    }
    throw error;
  }
}

// ============================================================================
// Legacy Customer Health API (Backward Compatibility)
// ============================================================================

/**
 * Get health metrics for a specific customer
 *
 * @param {string} customerId - Customer identifier
 * @param {string} timeRange - Time range for metrics (1h, 24h, 7d, 30d)
 * @param {boolean} includeBreakdown - Include detailed breakdowns
 * @returns {Promise<Object>} Customer health metrics
 */
export async function getCustomerHealth(customerId, timeRange = '24h', includeBreakdown = false) {
  try {
    const params = new URLSearchParams({
      time_range: timeRange,
      include_breakdown: includeBreakdown.toString(),
    });
    return await fetchApi(`/customer-health/${customerId}?${params}`);
  } catch (error) {
    // Return mock data for any error (network failures, 404, etc.)
    console.warn(`Using mock customer health for ${customerId} (API unavailable)`);
    return getMockCustomerHealth(customerId, timeRange);
  }
}

/**
 * Get health metrics for all customers (SaaS mode)
 *
 * @param {string} timeRange - Time range for metrics
 * @returns {Promise<Array>} List of customer health metrics
 */
export async function getAllCustomersHealth(timeRange = '24h') {
  try {
    const params = new URLSearchParams({ time_range: timeRange });
    return await fetchApi(`/customer-health?${params}`);
  } catch (error) {
    // Return mock data for any error (network failures, 404, etc.)
    console.warn('Using mock all customers health (API unavailable)');
    return [
      getMockCustomerHealth('cust-001', timeRange),
      getMockCustomerHealth('cust-002', timeRange),
      getMockCustomerHealth('cust-003', timeRange),
    ];
  }
}

/**
 * Get health summary for dashboard widgets
 *
 * @returns {Promise<Object>} Health summary with aggregated metrics
 */
export async function getHealthSummary() {
  try {
    return await fetchApi('/customer-health/summary');
  } catch (error) {
    // Return mock data for any error (network failures, 404, etc.)
    console.warn('Using mock health summary (API unavailable)');
    return getMockHealthSummary();
  }
}

/**
 * Get API metrics for a customer
 *
 * @param {string} customerId - Customer identifier
 * @param {string} timeRange - Time range for metrics
 * @returns {Promise<Object>} API metrics
 */
export async function getApiMetrics(customerId, timeRange = '24h') {
  try {
    return await fetchApi(`/customer-health/${customerId}/api?time_range=${timeRange}`);
  } catch (error) {
    // Return mock data for any error (network failures, 404, etc.)
    console.warn('Using mock API metrics (API unavailable)');
    return getMockApiMetrics();
  }
}

/**
 * Get agent execution metrics for a customer
 *
 * @param {string} customerId - Customer identifier
 * @param {string} timeRange - Time range for metrics
 * @returns {Promise<Object>} Agent metrics
 */
export async function getAgentMetrics(customerId, timeRange = '24h') {
  try {
    return await fetchApi(`/customer-health/${customerId}/agents?time_range=${timeRange}`);
  } catch (error) {
    // Return mock data for any error (network failures, 404, etc.)
    console.warn('Using mock agent metrics (API unavailable)');
    return getMockAgentMetrics();
  }
}

/**
 * Get token usage metrics for a customer
 *
 * @param {string} customerId - Customer identifier
 * @param {string} timeRange - Time range for metrics
 * @returns {Promise<Object>} Token usage metrics
 */
export async function getTokenMetrics(customerId, timeRange = '24h') {
  try {
    return await fetchApi(`/customer-health/${customerId}/tokens?time_range=${timeRange}`);
  } catch (error) {
    // Return mock data for any error (network failures, 404, etc.)
    console.warn('Using mock token metrics (API unavailable)');
    return getMockTokenMetrics();
  }
}

/**
 * Get storage usage metrics for a customer
 *
 * @param {string} customerId - Customer identifier
 * @returns {Promise<Object>} Storage metrics
 */
export async function getStorageMetrics(customerId) {
  try {
    return await fetchApi(`/customer-health/${customerId}/storage`);
  } catch (error) {
    // Return mock data for any error (network failures, 404, etc.)
    console.warn('Using mock storage metrics (API unavailable)');
    return getMockStorageMetrics();
  }
}

// ============================================================================
// Mock Data Generators (Development Mode)
// ============================================================================

function getMockHealthOverview(timeRange) {
  const now = new Date();
  const trendPoints = timeRange === '1h' ? 12 : timeRange === '24h' ? 24 : timeRange === '7d' ? 7 : 30;

  return {
    score: 94,
    status: 'healthy',
    trend: {
      direction: 'up',
      change: 2.3,
      data: Array.from({ length: trendPoints }, (_, i) => ({
        timestamp: new Date(now - (trendPoints - i - 1) * (timeRange === '1h' ? 5 * 60000 : timeRange === '24h' ? 60 * 60000 : 24 * 60 * 60000)).toISOString(),
        score: 90 + Math.random() * 8,
      })),
    },
    components: [
      { id: 'api', name: 'API Gateway', status: 'healthy', score: 98, latency_ms: 127 },
      { id: 'agents', name: 'Agent Orchestrator', status: 'healthy', score: 96, active_agents: 4 },
      { id: 'database', name: 'Neptune Graph DB', status: 'healthy', score: 95, connections: 12 },
      { id: 'search', name: 'OpenSearch', status: 'healthy', score: 94, index_health: 'green' },
      { id: 'storage', name: 'S3 Storage', status: 'healthy', score: 99, used_gb: 2.5 },
      { id: 'llm', name: 'LLM Integration', status: 'degraded', score: 78, avg_latency_ms: 2340 },
    ],
    last_updated: now.toISOString(),
  };
}

function getMockComponentHealth(componentId, _timeRange) {
  const componentData = {
    api: {
      id: 'api',
      name: 'API Gateway',
      status: 'healthy',
      score: 98,
      metrics: {
        request_count: 15234,
        error_count: 42,
        error_rate: 0.28,
        avg_latency_ms: 127.5,
        p50_latency_ms: 89.0,
        p95_latency_ms: 342.0,
        p99_latency_ms: 891.0,
        throughput_rps: 156.7,
      },
      thresholds: {
        error_rate: { warning: 1.0, critical: 5.0 },
        latency_ms: { warning: 500, critical: 2000 },
      },
    },
    agents: {
      id: 'agents',
      name: 'Agent Orchestrator',
      status: 'healthy',
      score: 96,
      metrics: {
        total_executions: 1247,
        successful_executions: 1198,
        failed_executions: 49,
        success_rate: 96.07,
        avg_execution_time_seconds: 45.3,
        active_agents: 4,
        queued_tasks: 12,
      },
      agent_breakdown: {
        scanner: { executions: 523, success_rate: 97.2 },
        coder: { executions: 412, success_rate: 95.4 },
        reviewer: { executions: 189, success_rate: 96.8 },
        validator: { executions: 123, success_rate: 94.3 },
      },
    },
    database: {
      id: 'database',
      name: 'Neptune Graph DB',
      status: 'healthy',
      score: 95,
      metrics: {
        connections_active: 12,
        connections_available: 88,
        query_count: 8934,
        avg_query_time_ms: 23.4,
        storage_used_gb: 0.5,
        cpu_utilization: 34.2,
        memory_utilization: 67.8,
      },
    },
    storage: {
      id: 'storage',
      name: 'S3 Storage',
      status: 'healthy',
      score: 99,
      metrics: {
        total_objects: 12456,
        storage_used_gb: 2.5,
        requests_get: 45678,
        requests_put: 1234,
        bandwidth_in_gb: 0.8,
        bandwidth_out_gb: 3.2,
      },
    },
    llm: {
      id: 'llm',
      name: 'LLM Integration',
      status: 'degraded',
      score: 78,
      metrics: {
        total_requests: 3456,
        successful_requests: 3389,
        failed_requests: 67,
        avg_latency_ms: 2340,
        total_input_tokens: 2450000,
        total_output_tokens: 890000,
        estimated_cost_usd: 20.78,
      },
      model_breakdown: {
        'claude-3.5-sonnet': { requests: 2800, avg_latency_ms: 2100 },
        'claude-3-haiku': { requests: 456, avg_latency_ms: 890 },
        'titan-embed-v2': { requests: 200, avg_latency_ms: 45 },
      },
    },
  };

  return componentData[componentId] || {
    id: componentId,
    name: componentId,
    status: 'unknown',
    score: 0,
    metrics: {},
  };
}

function getMockHealthHistory(days, resolution) {
  const now = new Date();
  const points = resolution === 'hourly' ? days * 24 : days;
  const interval = resolution === 'hourly' ? 60 * 60 * 1000 : 24 * 60 * 60 * 1000;

  return {
    days,
    resolution,
    data: Array.from({ length: points }, (_, i) => {
      const timestamp = new Date(now - (points - i - 1) * interval);
      const baseScore = 90 + Math.sin(i / 10) * 5;
      return {
        timestamp: timestamp.toISOString(),
        score: Math.round(baseScore + Math.random() * 5),
        api_health: Math.round(94 + Math.random() * 5),
        agent_health: Math.round(92 + Math.random() * 6),
        database_health: Math.round(95 + Math.random() * 4),
        incidents_count: Math.floor(Math.random() * 3),
      };
    }),
    summary: {
      avg_score: 93.4,
      min_score: 78,
      max_score: 99,
      uptime_percentage: 99.7,
      total_incidents: 12,
    },
  };
}

function getMockIncidents(options = {}) {
  const { status, severity, limit = 20, offset = 0 } = options;

  const allIncidents = [
    {
      id: 'inc-001',
      title: 'Elevated LLM API Latency',
      description: 'Claude API response times are 40% higher than baseline. Investigating potential rate limiting.',
      severity: 'high',
      status: 'active',
      component: 'llm',
      started_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
      acknowledged_at: null,
      resolved_at: null,
      impact: 'Slower agent execution times affecting patch generation workflow.',
    },
    {
      id: 'inc-002',
      title: 'Intermittent OpenSearch Connection Timeouts',
      description: 'Seeing sporadic connection timeouts to OpenSearch cluster during peak load.',
      severity: 'medium',
      status: 'acknowledged',
      component: 'search',
      started_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
      acknowledged_at: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString(),
      acknowledged_by: 'ops-team',
      resolved_at: null,
      impact: 'Some code search queries experiencing delays.',
    },
    {
      id: 'inc-003',
      title: 'Agent Scanner Memory Spike',
      description: 'Scanner agent encountered memory spike during large repository analysis.',
      severity: 'low',
      status: 'resolved',
      component: 'agents',
      started_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
      acknowledged_at: new Date(Date.now() - 23 * 60 * 60 * 1000).toISOString(),
      resolved_at: new Date(Date.now() - 20 * 60 * 60 * 1000).toISOString(),
      resolution: 'Implemented memory limits and chunked processing for large files.',
      impact: 'Temporary delay in scanning for one repository.',
    },
    {
      id: 'inc-004',
      title: 'API Gateway Rate Limit Warning',
      description: 'Approaching 80% of configured rate limits on /api/v1/agents endpoint.',
      severity: 'low',
      status: 'active',
      component: 'api',
      started_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
      acknowledged_at: null,
      resolved_at: null,
      impact: 'No current user impact, proactive warning.',
    },
    {
      id: 'inc-005',
      title: 'Critical: Neptune Failover Event',
      description: 'Primary Neptune instance experienced unexpected restart. Failover to replica completed successfully.',
      severity: 'critical',
      status: 'resolved',
      component: 'database',
      started_at: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
      acknowledged_at: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000 + 5 * 60 * 1000).toISOString(),
      resolved_at: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000 + 15 * 60 * 1000).toISOString(),
      resolution: 'Automated failover completed. Root cause identified as underlying hardware issue. AWS replaced hardware.',
      impact: 'Approximately 2 minutes of elevated query latency during failover.',
    },
  ];

  // Apply filters
  let filtered = allIncidents;
  if (status) {
    filtered = filtered.filter(inc => inc.status === status);
  }
  if (severity) {
    filtered = filtered.filter(inc => inc.severity === severity);
  }

  // Apply pagination
  const paginated = filtered.slice(offset, offset + limit);

  return {
    incidents: paginated,
    total: filtered.length,
    limit,
    offset,
    has_more: offset + limit < filtered.length,
  };
}

function getMockRecommendations(category = null) {
  const allRecommendations = [
    {
      id: 'rec-001',
      category: 'performance',
      priority: 'high',
      title: 'Optimize LLM Request Batching',
      description: 'Current implementation sends individual requests to Claude API. Implementing request batching could reduce latency by 35% and costs by 20%.',
      impact: { latency_reduction: 35, cost_reduction: 20 },
      effort: 'medium',
      created_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
    },
    {
      id: 'rec-002',
      category: 'cost',
      priority: 'medium',
      title: 'Switch to Claude 3 Haiku for Simple Tasks',
      description: 'Analysis shows 40% of LLM requests are simple classification tasks that could use Claude 3 Haiku instead of Sonnet, saving ~$15/day.',
      impact: { cost_reduction: 45 },
      effort: 'low',
      created_at: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
    },
    {
      id: 'rec-003',
      category: 'reliability',
      priority: 'high',
      title: 'Implement Circuit Breaker for External APIs',
      description: 'Adding circuit breaker pattern for external API calls would prevent cascade failures during third-party outages.',
      impact: { uptime_improvement: 0.5 },
      effort: 'medium',
      created_at: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString(),
    },
    {
      id: 'rec-004',
      category: 'security',
      priority: 'medium',
      title: 'Enable Neptune Audit Logging',
      description: 'Neptune audit logging is currently disabled. Enabling it would improve compliance posture and incident investigation capability.',
      impact: { compliance_score_improvement: 5 },
      effort: 'low',
      created_at: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
    },
    {
      id: 'rec-005',
      category: 'performance',
      priority: 'low',
      title: 'Consider OpenSearch Index Optimization',
      description: 'Current index configuration uses default settings. Custom analyzers could improve code search relevance by 15%.',
      impact: { search_relevance_improvement: 15 },
      effort: 'high',
      created_at: new Date(Date.now() - 10 * 24 * 60 * 60 * 1000).toISOString(),
    },
  ];

  if (category) {
    return allRecommendations.filter(rec => rec.category === category);
  }

  return allRecommendations;
}

function getMockCustomerHealth(customerId, timeRange) {
  return {
    customer_id: customerId,
    customer_name: `Customer ${customerId.split('-')[1]}`,
    time_range: timeRange,
    api: getMockApiMetrics(),
    agents: getMockAgentMetrics(),
    tokens: getMockTokenMetrics(),
    storage: getMockStorageMetrics(),
    health: {
      status: 'healthy',
      score: 94,
      issues: [],
      last_checked: new Date().toISOString(),
    },
    collected_at: new Date().toISOString(),
  };
}

function getMockApiMetrics() {
  return {
    request_count: 15234,
    error_count: 42,
    error_rate: 0.28,
    avg_latency_ms: 127.5,
    p50_latency_ms: 89.0,
    p95_latency_ms: 342.0,
    p99_latency_ms: 891.0,
  };
}

function getMockAgentMetrics() {
  return {
    total_executions: 1247,
    successful_executions: 1198,
    failed_executions: 49,
    success_rate: 96.07,
    avg_execution_time_seconds: 45.3,
    executions_by_type: {
      scanner: 523,
      coder: 412,
      reviewer: 189,
      validator: 123,
    },
  };
}

function getMockTokenMetrics() {
  return {
    total_input_tokens: 2450000,
    total_output_tokens: 890000,
    total_tokens: 3340000,
    estimated_cost_usd: 20.70,
    tokens_by_model: {
      'anthropic.claude-3-5-sonnet': 2800000,
      'anthropic.claude-3-haiku': 340000,
      'amazon.titan-embed-text-v2': 200000,
    },
  };
}

function getMockStorageMetrics() {
  return {
    s3_storage_bytes: 2147483648,
    s3_storage_gb: 2.0,
    neptune_storage_bytes: 536870912,
    neptune_storage_gb: 0.5,
    opensearch_storage_bytes: 1073741824,
    opensearch_storage_gb: 1.0,
    total_storage_gb: 3.5,
  };
}

function getMockHealthSummary() {
  return {
    total_customers: 3,
    healthy_customers: 2,
    degraded_customers: 1,
    unhealthy_customers: 0,
    total_api_requests: 45000,
    total_agent_executions: 3700,
    total_token_usage: 10000000,
    estimated_total_cost_usd: 62.10,
    avg_health_score: 91,
  };
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Format bytes to human-readable size
 */
export function formatBytes(bytes, decimals = 2) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(decimals)) + ' ' + sizes[i];
}

/**
 * Format number with commas
 */
export function formatNumber(num) {
  return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/**
 * Format currency
 */
export function formatCurrency(amount) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount);
}

/**
 * Get health status color class
 */
export function getHealthStatusColor(status) {
  switch (status) {
    case 'healthy':
      return 'text-olive-600 bg-olive-100 dark:text-olive-400 dark:bg-olive-900/30';
    case 'degraded':
      return 'text-warning-600 bg-warning-100 dark:text-warning-400 dark:bg-warning-900/30';
    case 'unhealthy':
      return 'text-critical-600 bg-critical-100 dark:text-critical-400 dark:bg-critical-900/30';
    default:
      return 'text-surface-600 bg-surface-100 dark:text-surface-400 dark:bg-surface-700';
  }
}

/**
 * Get health score color class
 */
export function getHealthScoreColor(score) {
  if (score >= 90) return 'text-olive-600 dark:text-olive-400';
  if (score >= 70) return 'text-warning-600 dark:text-warning-400';
  return 'text-critical-600 dark:text-critical-400';
}

/**
 * Get severity color class
 */
export function getSeverityColor(severity) {
  switch (severity) {
    case 'critical':
      return 'text-critical-600 bg-critical-100 dark:text-critical-400 dark:bg-critical-900/30';
    case 'high':
      return 'text-orange-600 bg-orange-100 dark:text-orange-400 dark:bg-orange-900/30';
    case 'medium':
      return 'text-warning-600 bg-warning-100 dark:text-warning-400 dark:bg-warning-900/30';
    case 'low':
      return 'text-info-600 bg-info-100 dark:text-info-400 dark:bg-info-900/30';
    default:
      return 'text-surface-600 bg-surface-100 dark:text-surface-400 dark:bg-surface-700';
  }
}

/**
 * Get incident status color class
 */
export function getIncidentStatusColor(status) {
  switch (status) {
    case 'active':
      return 'text-critical-600 bg-critical-100 dark:text-critical-400 dark:bg-critical-900/30';
    case 'acknowledged':
      return 'text-warning-600 bg-warning-100 dark:text-warning-400 dark:bg-warning-900/30';
    case 'resolved':
      return 'text-olive-600 bg-olive-100 dark:text-olive-400 dark:bg-olive-900/30';
    default:
      return 'text-surface-600 bg-surface-100 dark:text-surface-400 dark:bg-surface-700';
  }
}

/**
 * Format relative time (e.g., "2 hours ago")
 */
export function formatRelativeTime(dateString) {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now - date;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 60) return 'just now';
  if (diffMin < 60) return `${diffMin} minute${diffMin === 1 ? '' : 's'} ago`;
  if (diffHour < 24) return `${diffHour} hour${diffHour === 1 ? '' : 's'} ago`;
  if (diffDay < 7) return `${diffDay} day${diffDay === 1 ? '' : 's'} ago`;

  return date.toLocaleDateString();
}
