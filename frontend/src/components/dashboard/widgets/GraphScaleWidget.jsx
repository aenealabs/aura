/**
 * Graph Scale Widget
 *
 * Displays Neptune graph shard health, query latency, and
 * replication status.
 *
 * Per ADR-079: Widget ID 'ai-security-graph-scale', Category: OPERATIONS
 *
 * @module components/dashboard/widgets/GraphScaleWidget
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  CircleStackIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
} from '@heroicons/react/24/solid';
import { getGraphHealth } from '../../../services/aiSecurityApi';
import { DataFreshnessIndicator } from '../../palantir/DataFreshnessIndicator';

// Status configurations
const STATUS_CONFIG = {
  healthy: {
    icon: CheckCircleIcon,
    color: 'text-green-500',
    bgColor: 'bg-green-100 dark:bg-green-900/30',
    dotColor: 'bg-green-500',
    label: 'Healthy',
  },
  degraded: {
    icon: ExclamationCircleIcon,
    color: 'text-amber-500',
    bgColor: 'bg-amber-100 dark:bg-amber-900/30',
    dotColor: 'bg-amber-500',
    label: 'Degraded',
  },
  unhealthy: {
    icon: ExclamationTriangleIcon,
    color: 'text-red-500',
    bgColor: 'bg-red-100 dark:bg-red-900/30',
    dotColor: 'bg-red-500',
    label: 'Unhealthy',
  },
};

/**
 * Loading skeleton
 */
function GraphScaleWidgetSkeleton() {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 animate-pulse">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 rounded-lg bg-surface-200 dark:bg-surface-700" />
        <div className="w-28 h-5 rounded bg-surface-200 dark:bg-surface-700" />
      </div>
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="h-20 rounded-lg bg-surface-100 dark:bg-surface-700" />
        <div className="h-20 rounded-lg bg-surface-100 dark:bg-surface-700" />
      </div>
      <div className="space-y-2">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-12 rounded bg-surface-100 dark:bg-surface-700" />
        ))}
      </div>
    </div>
  );
}

/**
 * Error state
 */
function GraphScaleWidgetError({ onRetry }) {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-red-200 dark:border-red-800 p-4 flex flex-col items-center justify-center min-h-[200px]">
      <ExclamationTriangleIcon className="w-8 h-8 text-red-500 mb-2" />
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
        Failed to load graph health
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-lg transition-colors"
        >
          <ArrowPathIcon className="w-4 h-4" />
          Retry
        </button>
      )}
    </div>
  );
}

/**
 * Format large numbers
 */
function formatNumber(num) {
  if (num >= 1000000000) return (num / 1000000000).toFixed(1) + 'B';
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
  return num.toLocaleString();
}

/**
 * Format relative time
 */
function formatRelativeTime(isoString) {
  if (!isoString) return 'Never';
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.floor(diffHours / 24)}d ago`;
}

/**
 * Utilization bar
 */
function UtilizationBar({ label, value, threshold = 80 }) {
  const isWarning = value > threshold;
  const color = isWarning ? 'bg-amber-500' : 'bg-blue-500';

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-500 w-8">{label}</span>
      <div className="flex-1 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full ${color} transition-all`}
          style={{ width: `${value}%` }}
        />
      </div>
      <span className={`text-xs font-medium ${isWarning ? 'text-amber-600' : 'text-gray-600 dark:text-gray-400'}`}>
        {value}%
      </span>
    </div>
  );
}

/**
 * Shard row
 */
function ShardRow({ shard, onClick }) {
  const config = STATUS_CONFIG[shard.status] || STATUS_CONFIG.healthy;
  const StatusIcon = config.icon;
  const isLagging = shard.replication_lag_ms > 0;

  return (
    <button
      onClick={() => onClick?.(shard)}
      className="
        w-full text-left p-3 rounded-lg border
        bg-gray-50 dark:bg-gray-800/50 border-gray-200 dark:border-gray-700
        hover:bg-gray-100 dark:hover:bg-gray-800
        hover:shadow-sm transition-all duration-200
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1
      "
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${config.dotColor}`} />
          <span className="text-sm font-mono font-medium text-gray-900 dark:text-gray-100">
            {shard.shard_id}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {isLagging && (
            <span className="text-xs text-amber-600">
              Lag: {shard.replication_lag_ms}ms
            </span>
          )}
          <StatusIcon className={`w-4 h-4 ${config.color}`} />
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-2 text-xs text-gray-500 dark:text-gray-400 mb-2">
        <div>
          <span className="text-gray-400">Nodes:</span>{' '}
          <span className="font-medium text-gray-700 dark:text-gray-300">
            {formatNumber(shard.node_count)}
          </span>
        </div>
        <div>
          <span className="text-gray-400">Edges:</span>{' '}
          <span className="font-medium text-gray-700 dark:text-gray-300">
            {formatNumber(shard.edge_count)}
          </span>
        </div>
        <div>
          <span className="text-gray-400">Latency:</span>{' '}
          <span className={`font-medium ${shard.query_latency_ms > 30 ? 'text-amber-600' : 'text-gray-700 dark:text-gray-300'}`}>
            {shard.query_latency_ms}ms
          </span>
        </div>
      </div>

      {/* Utilization */}
      <div className="space-y-1">
        <UtilizationBar label="CPU" value={shard.cpu_utilization} />
        <UtilizationBar label="RAM" value={shard.memory_utilization} />
      </div>
    </button>
  );
}

/**
 * GraphScaleWidget component
 */
export function GraphScaleWidget({
  refreshInterval = 30000,
  onShardClick = null,
  className = '',
}) {
  const [graphData, setGraphData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const mountedRef = useRef(true);

  const fetchHealth = useCallback(async () => {
    try {
      const data = await getGraphHealth();

      if (mountedRef.current) {
        setGraphData(data);
        setLastUpdated(new Date().toISOString());
        setError(null);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err);
      }
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchHealth();

    const interval = setInterval(fetchHealth, refreshInterval);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchHealth, refreshInterval]);

  if (isLoading) {
    return <GraphScaleWidgetSkeleton />;
  }

  if (error) {
    return <GraphScaleWidgetError onRetry={fetchHealth} />;
  }

  const clusterConfig = STATUS_CONFIG[graphData?.cluster_status] || STATUS_CONFIG.healthy;
  const healthyShards = graphData?.shards?.filter((s) => s.status === 'healthy').length || 0;
  const totalShards = graphData?.shards?.length || 0;

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        overflow-hidden
        ${className}
      `}
      role="region"
      aria-label="Graph Scale Health"
    >
      {/* Header */}
      <div className="p-4 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-indigo-100 dark:bg-indigo-900/30">
              <CircleStackIcon className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
            </div>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">
              Graph Scale
            </h3>
          </div>
          <div className="flex items-center gap-2">
            <span className={`flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full ${clusterConfig.bgColor} ${clusterConfig.color}`}>
              <clusterConfig.icon className="w-3 h-3" />
              {clusterConfig.label}
            </span>
            <button
              onClick={fetchHealth}
              className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              aria-label="Refresh"
            >
              <ArrowPathIcon className="w-4 h-4 text-gray-500" />
            </button>
          </div>
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          Neptune graph shard health and query latency
        </p>
      </div>

      {/* Stats */}
      <div className="p-4 grid grid-cols-2 gap-4 border-b border-gray-200 dark:border-gray-700">
        <div className="p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
          <p className="text-xs text-blue-600 dark:text-blue-400">Total Nodes</p>
          <p className="text-2xl font-bold text-blue-700 dark:text-blue-300">
            {formatNumber(graphData?.total_nodes || 0)}
          </p>
          <p className="text-xs text-blue-500 mt-1">
            {formatNumber(graphData?.total_edges || 0)} edges
          </p>
        </div>
        <div className="p-3 rounded-lg bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800">
          <p className="text-xs text-purple-600 dark:text-purple-400">Avg Latency</p>
          <p className={`text-2xl font-bold ${graphData?.avg_query_latency_ms > 50 ? 'text-amber-600' : 'text-purple-700 dark:text-purple-300'}`}>
            {graphData?.avg_query_latency_ms || 0}ms
          </p>
          <p className="text-xs text-purple-500 mt-1">
            {graphData?.replication_status || 'Unknown'}
          </p>
        </div>
      </div>

      {/* Shards */}
      <div className="p-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-xs font-medium text-gray-500 uppercase">
            Shards ({healthyShards}/{totalShards} healthy)
          </h4>
          {graphData?.query_stats && (
            <span className="text-xs text-gray-500">
              {graphData.query_stats.slow_queries_24h} slow queries (24h)
            </span>
          )}
        </div>
        {graphData?.shards?.length > 0 ? (
          <div className="space-y-2">
            {graphData.shards.slice(0, 4).map((shard) => (
              <ShardRow
                key={shard.shard_id}
                shard={shard}
                onClick={onShardClick}
              />
            ))}
          </div>
        ) : (
          <div className="text-center py-6 text-gray-500 dark:text-gray-400">
            <CircleStackIcon className="w-8 h-8 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No shards available</p>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>
            {formatNumber(graphData?.query_stats?.total_24h || 0)} queries (24h) |{' '}
            {graphData?.query_stats?.failed_queries_24h || 0} failed
          </span>
          <DataFreshnessIndicator timestamp={lastUpdated} compact />
        </div>
      </div>
    </div>
  );
}

GraphScaleWidget.propTypes = {
  refreshInterval: PropTypes.number,
  onShardClick: PropTypes.func,
  className: PropTypes.string,
};

export default GraphScaleWidget;
