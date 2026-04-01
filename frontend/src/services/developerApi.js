/**
 * Developer Mode API Service
 *
 * Handles API calls for developer/debug mode features.
 * Most dev mode state is client-side, but some features
 * require server interaction.
 */

const API_BASE = import.meta.env.VITE_API_URL || '';
const DEV_MODE = import.meta.env.DEV || !import.meta.env.VITE_API_URL;

/**
 * Get available feature flags from the server
 */
export async function getFeatureFlags() {
  if (DEV_MODE) {
    return [
      { id: 'experimental_graph_viz', label: 'Experimental Graph Visualization', description: 'New 3D graph rendering engine', default: false },
      { id: 'ai_suggestions_v2', label: 'AI Suggestions v2', description: 'Next-gen code suggestion algorithm', default: false },
      { id: 'realtime_collaboration', label: 'Real-time Collaboration', description: 'Live cursor and editing sync', default: false },
      { id: 'advanced_security_scan', label: 'Advanced Security Scanning', description: 'Deep vulnerability analysis', default: false },
      { id: 'agent_autonomy_v2', label: 'Agent Autonomy v2', description: 'Enhanced autonomous decision making', default: false },
      { id: 'titan_memory_v2', label: 'Titan Memory v2', description: 'Enhanced neural memory architecture', default: false },
      { id: 'multi_repo_analysis', label: 'Multi-Repository Analysis', description: 'Cross-repo dependency analysis', default: false },
    ];
  }

  const response = await fetch(`${API_BASE}/api/v1/developer/feature-flags`);
  if (!response.ok) {
    throw new Error('Failed to fetch feature flags');
  }
  return response.json();
}

/**
 * Get server-side performance metrics
 */
export async function getServerMetrics() {
  if (DEV_MODE) {
    return {
      uptime: 86400 + Math.floor(Math.random() * 10000),
      requestsPerSecond: 45 + Math.floor(Math.random() * 30),
      avgResponseTime: 120 + Math.floor(Math.random() * 80),
      dbConnections: 15 + Math.floor(Math.random() * 10),
      cacheHitRate: 0.85 + Math.random() * 0.1,
      memoryUsage: 0.6 + Math.random() * 0.2,
      cpuUsage: 0.3 + Math.random() * 0.3,
    };
  }

  const response = await fetch(`${API_BASE}/api/v1/developer/metrics`);
  if (!response.ok) {
    throw new Error('Failed to fetch server metrics');
  }
  return response.json();
}

/**
 * Get GraphRAG debug information for a query
 */
export async function getGraphRAGDebugInfo(queryId) {
  if (DEV_MODE) {
    return {
      queryId,
      timestamp: new Date().toISOString(),
      graphTraversal: {
        nodesVisited: 145,
        edgesTraversed: 287,
        traversalTime: 45,
        path: ['entity:main.py', 'calls:process_data', 'imports:pandas', 'uses:DataFrame'],
      },
      vectorSearch: {
        queryEmbedding: '[0.123, 0.456, ...]',
        topK: 10,
        threshold: 0.75,
        searchTime: 23,
        results: [
          { score: 0.95, chunk: 'def process_data(...)' },
          { score: 0.89, chunk: 'class DataProcessor:' },
          { score: 0.84, chunk: 'import pandas as pd' },
        ],
      },
      hybridScoring: {
        graphWeight: 0.4,
        vectorWeight: 0.6,
        finalScores: [0.91, 0.87, 0.82],
      },
    };
  }

  const response = await fetch(`${API_BASE}/api/v1/developer/graphrag-debug/${queryId}`);
  if (!response.ok) {
    throw new Error('Failed to fetch GraphRAG debug info');
  }
  return response.json();
}

/**
 * Get agent execution trace
 */
export async function getAgentTrace(executionId) {
  if (DEV_MODE) {
    return {
      executionId,
      agentId: 'security-agent-001',
      startTime: new Date(Date.now() - 5000).toISOString(),
      endTime: new Date().toISOString(),
      status: 'completed',
      steps: [
        { step: 1, action: 'analyze_code', duration: 1200, status: 'success', details: 'Analyzed 45 files' },
        { step: 2, action: 'detect_vulnerabilities', duration: 2300, status: 'success', details: 'Found 3 issues' },
        { step: 3, action: 'generate_patches', duration: 1500, status: 'success', details: 'Created 3 patches' },
      ],
      resourceUsage: {
        tokensUsed: 4500,
        apiCalls: 12,
        sandboxTime: 3200,
      },
    };
  }

  const response = await fetch(`${API_BASE}/api/v1/developer/agent-trace/${executionId}`);
  if (!response.ok) {
    throw new Error('Failed to fetch agent trace');
  }
  return response.json();
}

/**
 * Enable/disable server-side debug logging
 */
export async function setServerDebugMode(enabled, level = 'debug') {
  if (DEV_MODE) {
    // eslint-disable-next-line no-console -- Intentional dev mode logging
    console.log(`[Dev Mode] Server debug logging ${enabled ? 'enabled' : 'disabled'} at level: ${level}`);
    return { success: true, enabled, level };
  }

  const response = await fetch(`${API_BASE}/api/v1/developer/debug-mode`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled, level }),
  });

  if (!response.ok) {
    throw new Error('Failed to set server debug mode');
  }
  return response.json();
}

/**
 * Get recent server logs (for debug mode)
 */
export async function getServerLogs(options = {}) {
  const { level = 'info', limit = 100, since } = options;

  if (DEV_MODE) {
    const levels = ['error', 'warn', 'info', 'debug'];
    return Array.from({ length: Math.min(limit, 50) }, (_, i) => ({
      id: `log-${Date.now()}-${i}`,
      timestamp: new Date(Date.now() - i * 1000).toISOString(),
      level: levels[Math.floor(Math.random() * levels.length)],
      service: ['api', 'orchestrator', 'graphrag', 'sandbox'][Math.floor(Math.random() * 4)],
      message: `Sample log message ${i + 1}`,
      metadata: { requestId: `req-${i}`, userId: 'user-123' },
    }));
  }

  const params = new URLSearchParams({ level, limit: String(limit) });
  if (since) params.append('since', since);

  const response = await fetch(`${API_BASE}/api/v1/developer/logs?${params}`);
  if (!response.ok) {
    throw new Error('Failed to fetch server logs');
  }
  return response.json();
}

/**
 * Simulate network conditions (for testing)
 */
export function createThrottledFetch(preset) {
  const { latency, downloadSpeed } = preset;

  if (latency === 0 && downloadSpeed === Infinity) {
    return fetch; // No throttling
  }

  if (latency === Infinity) {
    // Offline mode
    return () => Promise.reject(new Error('Network offline (simulated)'));
  }

  return async (input, init) => {
    // Add latency
    await new Promise((resolve) => setTimeout(resolve, latency));

    const response = await fetch(input, init);

    // Simulate slow download (simplified)
    if (downloadSpeed < Infinity) {
      const reader = response.body?.getReader();
      if (reader) {
        // For now, just add additional delay based on content length
        const contentLength = response.headers.get('content-length');
        if (contentLength) {
          const downloadTime = (parseInt(contentLength) / 1024) / downloadSpeed * 1000;
          await new Promise((resolve) => setTimeout(resolve, downloadTime));
        }
      }
    }

    return response;
  };
}

/**
 * Format bytes for display
 */
export function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

/**
 * Format duration for display
 */
export function formatDuration(ms) {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}
