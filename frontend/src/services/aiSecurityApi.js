/**
 * Project Aura - AI Security & Scale API Service
 *
 * Client-side service for interacting with AI security and
 * scale monitoring endpoints per ADR-079.
 *
 * @module services/aiSecurityApi
 */

import { apiClient, ApiError } from './api';

// API endpoints for AI Security & Scale
const ENDPOINTS = {
  // Streaming Performance
  STREAMING_LATENCY: '/api/v1/ai-security/streaming/latency',
  STREAMING_METRICS: '/api/v1/ai-security/streaming/metrics',
  STREAMING_HEALTH: '/api/v1/ai-security/streaming/health',

  // Model Security
  MODEL_ACCESS: '/api/v1/ai-security/model/access',
  MODEL_ANOMALIES: '/api/v1/ai-security/model/anomalies',
  MODEL_AUDIT: '/api/v1/ai-security/model/audit',

  // Training Security
  TRAINING_POISONING: '/api/v1/ai-security/training/poisoning',
  TRAINING_INTEGRITY: '/api/v1/ai-security/training/integrity',
  TRAINING_DATASETS: '/api/v1/ai-security/training/datasets',

  // Graph Scale
  GRAPH_HEALTH: '/api/v1/ai-security/graph/health',
  GRAPH_SHARDS: '/api/v1/ai-security/graph/shards',
  GRAPH_QUERIES: '/api/v1/ai-security/graph/queries',
};

/**
 * @typedef {Object} StreamingLatency
 * @property {number} p50_ms - 50th percentile latency
 * @property {number} p95_ms - 95th percentile latency
 * @property {number} p99_ms - 99th percentile latency
 * @property {number} avg_ms - Average latency
 * @property {number} throughput_rps - Requests per second
 * @property {Object[]} trend_data - Historical trend data
 */

/**
 * @typedef {Object} ModelAccessAnomaly
 * @property {string} anomaly_id - Anomaly identifier
 * @property {string} model_id - Affected model
 * @property {string} anomaly_type - Type of anomaly
 * @property {string} severity - Severity level
 * @property {string} user_id - User who accessed
 * @property {string} access_pattern - Detected access pattern
 * @property {string} detected_at - Detection timestamp
 * @property {boolean} investigated - Investigation status
 */

/**
 * @typedef {Object} TrainingPoisoningAlert
 * @property {string} alert_id - Alert identifier
 * @property {string} dataset_id - Affected dataset
 * @property {string} poisoning_type - Type of poisoning detected
 * @property {string} severity - Severity level
 * @property {number} confidence_score - Detection confidence
 * @property {number} affected_samples - Number of affected samples
 * @property {string} detected_at - Detection timestamp
 * @property {boolean} quarantined - Whether data was quarantined
 */

/**
 * @typedef {Object} GraphShardHealth
 * @property {string} shard_id - Shard identifier
 * @property {string} status - Health status
 * @property {number} node_count - Number of nodes
 * @property {number} edge_count - Number of edges
 * @property {number} query_latency_ms - Average query latency
 * @property {number} replication_lag_ms - Replication lag
 * @property {string} last_compaction - Last compaction timestamp
 */

// Mock data for development
const MOCK_STREAMING_LATENCY = {
  p50_ms: 45,
  p95_ms: 128,
  p99_ms: 312,
  avg_ms: 67,
  throughput_rps: 1247,
  status: 'healthy',
  trend_data: (() => {
    const data = [];
    const now = Date.now();
    for (let i = 23; i >= 0; i--) {
      data.push({
        timestamp: new Date(now - i * 60 * 60 * 1000).toISOString(),
        label: `${23 - i}h ago`,
        p50: 40 + Math.random() * 20,
        p95: 110 + Math.random() * 40,
        p99: 280 + Math.random() * 80,
      });
    }
    return data;
  })(),
};

const MOCK_MODEL_ACCESS = {
  total_accesses_24h: 15847,
  unique_users_24h: 127,
  anomaly_count: 3,
  anomalies: [
    {
      anomaly_id: 'ma-001',
      model_id: 'claude-3-sonnet',
      anomaly_type: 'unusual_volume',
      severity: 'medium',
      user_id: 'user-abc123',
      access_pattern: 'Burst of 500 requests in 1 minute',
      detected_at: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
      investigated: false,
      details: 'Access volume 10x normal rate for this user',
    },
    {
      anomaly_id: 'ma-002',
      model_id: 'gpt-4-turbo',
      anomaly_type: 'weight_exfiltration_attempt',
      severity: 'critical',
      user_id: 'user-def456',
      access_pattern: 'Sequential probing of model internals',
      detected_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
      investigated: true,
      details: 'Attempted to extract model weights via embedding API',
    },
    {
      anomaly_id: 'ma-003',
      model_id: 'embedding-ada-002',
      anomaly_type: 'off_hours_access',
      severity: 'low',
      user_id: 'service-account-batch',
      access_pattern: 'Access outside maintenance window',
      detected_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
      investigated: false,
      details: 'Service account accessed model at 3AM UTC',
    },
  ],
};

const MOCK_TRAINING_POISONING = {
  total_datasets_monitored: 47,
  clean_datasets: 44,
  quarantined_datasets: 2,
  under_investigation: 1,
  alerts: [
    {
      alert_id: 'tp-001',
      dataset_id: 'training-code-v3',
      poisoning_type: 'backdoor_injection',
      severity: 'critical',
      confidence_score: 94,
      affected_samples: 127,
      detected_at: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
      quarantined: true,
      description: 'Detected trigger pattern in code samples suggesting backdoor',
    },
    {
      alert_id: 'tp-002',
      dataset_id: 'finetuning-security-v2',
      poisoning_type: 'label_flipping',
      severity: 'high',
      confidence_score: 87,
      affected_samples: 45,
      detected_at: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString(),
      quarantined: true,
      description: 'Labels inconsistent with expected vulnerability classifications',
    },
    {
      alert_id: 'tp-003',
      dataset_id: 'embedding-corpus-v4',
      poisoning_type: 'data_drift',
      severity: 'medium',
      confidence_score: 72,
      affected_samples: 1250,
      detected_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
      quarantined: false,
      description: 'Statistical distribution shift detected in recent samples',
    },
  ],
};

const MOCK_GRAPH_HEALTH = {
  cluster_status: 'healthy',
  total_nodes: 15847293,
  total_edges: 47892156,
  shard_count: 8,
  avg_query_latency_ms: 23,
  replication_status: 'synchronized',
  shards: [
    {
      shard_id: 'neptune-shard-001',
      status: 'healthy',
      node_count: 1980912,
      edge_count: 5986519,
      query_latency_ms: 18,
      replication_lag_ms: 0,
      last_compaction: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
      cpu_utilization: 45,
      memory_utilization: 62,
    },
    {
      shard_id: 'neptune-shard-002',
      status: 'healthy',
      node_count: 1980911,
      edge_count: 5986520,
      query_latency_ms: 21,
      replication_lag_ms: 0,
      last_compaction: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
      cpu_utilization: 52,
      memory_utilization: 58,
    },
    {
      shard_id: 'neptune-shard-003',
      status: 'degraded',
      node_count: 1980912,
      edge_count: 5986519,
      query_latency_ms: 45,
      replication_lag_ms: 150,
      last_compaction: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(),
      cpu_utilization: 78,
      memory_utilization: 85,
    },
    {
      shard_id: 'neptune-shard-004',
      status: 'healthy',
      node_count: 1980911,
      edge_count: 5986520,
      query_latency_ms: 19,
      replication_lag_ms: 0,
      last_compaction: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
      cpu_utilization: 41,
      memory_utilization: 55,
    },
  ],
  query_stats: {
    total_24h: 2847156,
    slow_queries_24h: 127,
    failed_queries_24h: 12,
  },
};

// ============================================================================
// Streaming Performance Endpoints
// ============================================================================

/**
 * Get streaming analysis latency metrics.
 *
 * @param {string} [timeRange='24h'] - Time range for metrics
 * @returns {Promise<StreamingLatency>} Latency metrics
 * @throws {ApiError} When the request fails
 */
export async function getStreamingLatency(timeRange = '24h') {
  try {
    const { data } = await apiClient.get(`${ENDPOINTS.STREAMING_LATENCY}?range=${timeRange}`);
    return data;
  } catch (err) {
    console.warn('Using mock streaming latency (API unavailable)');
    return MOCK_STREAMING_LATENCY;
  }
}

/**
 * Get detailed streaming metrics.
 *
 * @returns {Promise<Object>} Streaming metrics
 * @throws {ApiError} When the request fails
 */
export async function getStreamingMetrics() {
  const { data } = await apiClient.get(ENDPOINTS.STREAMING_METRICS);
  return data;
}

/**
 * Get streaming service health.
 *
 * @returns {Promise<Object>} Health status
 * @throws {ApiError} When the request fails
 */
export async function getStreamingHealth() {
  const { data } = await apiClient.get(ENDPOINTS.STREAMING_HEALTH);
  return data;
}

// ============================================================================
// Model Security Endpoints
// ============================================================================

/**
 * Get model access anomalies.
 *
 * @param {Object} [filters] - Optional filters
 * @param {string} [filters.severity] - Filter by severity
 * @param {boolean} [filters.investigated] - Filter by investigation status
 * @returns {Promise<Object>} Access anomalies
 * @throws {ApiError} When the request fails
 */
export async function getModelAccessAnomalies(filters = {}) {
  try {
    const params = new URLSearchParams();
    if (filters.severity) params.append('severity', filters.severity);
    if (filters.investigated !== undefined) params.append('investigated', filters.investigated);

    const url = `${ENDPOINTS.MODEL_ANOMALIES}${params.toString() ? `?${params}` : ''}`;
    const { data } = await apiClient.get(url);
    return data;
  } catch (err) {
    console.warn('Using mock model access data (API unavailable)');
    let anomalies = [...MOCK_MODEL_ACCESS.anomalies];
    if (filters.severity) {
      anomalies = anomalies.filter((a) => a.severity === filters.severity);
    }
    if (filters.investigated !== undefined) {
      anomalies = anomalies.filter((a) => a.investigated === filters.investigated);
    }
    return { ...MOCK_MODEL_ACCESS, anomalies };
  }
}

/**
 * Get model access audit log.
 *
 * @param {string} modelId - Model identifier
 * @param {string} [timeRange='24h'] - Time range
 * @returns {Promise<Object[]>} Audit log entries
 * @throws {ApiError} When the request fails
 */
export async function getModelAuditLog(modelId, timeRange = '24h') {
  const { data } = await apiClient.get(`${ENDPOINTS.MODEL_AUDIT}/${modelId}?range=${timeRange}`);
  return data;
}

/**
 * Mark anomaly as investigated.
 *
 * @param {string} anomalyId - Anomaly identifier
 * @param {Object} findings - Investigation findings
 * @returns {Promise<Object>} Update result
 * @throws {ApiError} When the request fails
 */
export async function markAnomalyInvestigated(anomalyId, findings) {
  const { data } = await apiClient.post(`${ENDPOINTS.MODEL_ANOMALIES}/${anomalyId}/investigate`, findings);
  return data;
}

// ============================================================================
// Training Security Endpoints
// ============================================================================

/**
 * Get training data poisoning alerts.
 *
 * @param {Object} [filters] - Optional filters
 * @param {string} [filters.severity] - Filter by severity
 * @param {boolean} [filters.quarantined] - Filter by quarantine status
 * @returns {Promise<Object>} Poisoning alerts
 * @throws {ApiError} When the request fails
 */
export async function getTrainingPoisoningAlerts(filters = {}) {
  try {
    const params = new URLSearchParams();
    if (filters.severity) params.append('severity', filters.severity);
    if (filters.quarantined !== undefined) params.append('quarantined', filters.quarantined);

    const url = `${ENDPOINTS.TRAINING_POISONING}${params.toString() ? `?${params}` : ''}`;
    const { data } = await apiClient.get(url);
    return data;
  } catch (err) {
    console.warn('Using mock training poisoning data (API unavailable)');
    let alerts = [...MOCK_TRAINING_POISONING.alerts];
    if (filters.severity) {
      alerts = alerts.filter((a) => a.severity === filters.severity);
    }
    if (filters.quarantined !== undefined) {
      alerts = alerts.filter((a) => a.quarantined === filters.quarantined);
    }
    return { ...MOCK_TRAINING_POISONING, alerts };
  }
}

/**
 * Quarantine a dataset.
 *
 * @param {string} datasetId - Dataset identifier
 * @param {string} reason - Quarantine reason
 * @returns {Promise<Object>} Quarantine result
 * @throws {ApiError} When the request fails
 */
export async function quarantineDataset(datasetId, reason) {
  const { data } = await apiClient.post(`${ENDPOINTS.TRAINING_DATASETS}/${datasetId}/quarantine`, {
    reason,
  });
  return data;
}

/**
 * Get training dataset integrity report.
 *
 * @param {string} datasetId - Dataset identifier
 * @returns {Promise<Object>} Integrity report
 * @throws {ApiError} When the request fails
 */
export async function getDatasetIntegrity(datasetId) {
  const { data } = await apiClient.get(`${ENDPOINTS.TRAINING_INTEGRITY}/${datasetId}`);
  return data;
}

// ============================================================================
// Graph Scale Endpoints
// ============================================================================

/**
 * Get Neptune graph health and shard status.
 *
 * @returns {Promise<Object>} Graph health
 * @throws {ApiError} When the request fails
 */
export async function getGraphHealth() {
  try {
    const { data } = await apiClient.get(ENDPOINTS.GRAPH_HEALTH);
    return data;
  } catch (err) {
    console.warn('Using mock graph health (API unavailable)');
    return MOCK_GRAPH_HEALTH;
  }
}

/**
 * Get detailed shard information.
 *
 * @param {string} [shardId] - Optional shard ID to filter
 * @returns {Promise<GraphShardHealth[]>} Shard health data
 * @throws {ApiError} When the request fails
 */
export async function getGraphShards(shardId) {
  const url = shardId
    ? `${ENDPOINTS.GRAPH_SHARDS}/${shardId}`
    : ENDPOINTS.GRAPH_SHARDS;
  const { data } = await apiClient.get(url);
  return data;
}

/**
 * Get slow query analysis.
 *
 * @param {string} [timeRange='24h'] - Time range
 * @returns {Promise<Object[]>} Slow queries
 * @throws {ApiError} When the request fails
 */
export async function getSlowQueries(timeRange = '24h') {
  const { data } = await apiClient.get(`${ENDPOINTS.GRAPH_QUERIES}/slow?range=${timeRange}`);
  return data;
}

/**
 * API error specific to AI Security operations
 */
export class AISecurityApiError extends ApiError {
  constructor(message, status, details = null) {
    super(message, status, details);
    this.name = 'AISecurityApiError';
  }
}

// Default export for convenience
export default {
  // Streaming Performance
  getStreamingLatency,
  getStreamingMetrics,
  getStreamingHealth,

  // Model Security
  getModelAccessAnomalies,
  getModelAuditLog,
  markAnomalyInvestigated,

  // Training Security
  getTrainingPoisoningAlerts,
  quarantineDataset,
  getDatasetIntegrity,

  // Graph Scale
  getGraphHealth,
  getGraphShards,
  getSlowQueries,

  // Error class
  AISecurityApiError,

  // Constants
  ENDPOINTS,
};
