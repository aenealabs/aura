/**
 * Streaming Latency Widget
 *
 * Displays P50/P95/P99 analysis latency percentiles with
 * trend visualization.
 *
 * Per ADR-079: Widget ID 'ai-security-streaming-latency', Category: ANALYTICS
 *
 * @module components/dashboard/widgets/StreamingLatencyWidget
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  BoltIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
} from '@heroicons/react/24/solid';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { getStreamingLatency } from '../../../services/aiSecurityApi';
import { DataFreshnessIndicator } from '../../palantir/DataFreshnessIndicator';

// Latency thresholds (in ms)
const LATENCY_THRESHOLDS = {
  p50: { good: 50, warning: 100 },
  p95: { good: 150, warning: 250 },
  p99: { good: 350, warning: 500 },
};

/**
 * Get color based on latency value
 */
function getLatencyColor(metric, value) {
  const threshold = LATENCY_THRESHOLDS[metric];
  if (value <= threshold.good) return 'text-green-600';
  if (value <= threshold.warning) return 'text-amber-600';
  return 'text-red-600';
}

/**
 * Loading skeleton
 */
function StreamingLatencyWidgetSkeleton() {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 animate-pulse">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 rounded-lg bg-surface-200 dark:bg-surface-700" />
        <div className="w-32 h-5 rounded bg-surface-200 dark:bg-surface-700" />
      </div>
      <div className="grid grid-cols-3 gap-4 mb-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-16 rounded-lg bg-surface-100 dark:bg-surface-700" />
        ))}
      </div>
      <div className="h-40 bg-surface-100 dark:bg-surface-700 rounded" />
    </div>
  );
}

/**
 * Error state
 */
function StreamingLatencyWidgetError({ onRetry }) {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-red-200 dark:border-red-800 p-4 flex flex-col items-center justify-center min-h-[250px]">
      <ExclamationTriangleIcon className="w-8 h-8 text-red-500 mb-2" />
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
        Failed to load latency metrics
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
 * Custom tooltip
 */
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload) return null;

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 p-3">
      <p className="text-xs font-medium text-gray-500 mb-2">{label}</p>
      {payload.map((entry) => (
        <div key={entry.dataKey} className="flex items-center justify-between gap-4 text-sm">
          <div className="flex items-center gap-1">
            <span
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: entry.color }}
            />
            <span className="text-gray-600 dark:text-gray-400 uppercase">{entry.dataKey}</span>
          </div>
          <span className="font-medium text-gray-900 dark:text-gray-100">
            {entry.value.toFixed(0)}ms
          </span>
        </div>
      ))}
    </div>
  );
}

/**
 * Latency metric card
 */
function LatencyCard({ label, value, threshold }) {
  const colorClass = getLatencyColor(label.toLowerCase(), value);
  const isGood = value <= threshold.good;

  return (
    <div className="text-center p-3 rounded-lg bg-gray-50 dark:bg-gray-800/50">
      <div className="flex items-center justify-center gap-1 mb-1">
        {isGood ? (
          <CheckCircleIcon className="w-3 h-3 text-green-500" />
        ) : value <= threshold.warning ? (
          <ExclamationCircleIcon className="w-3 h-3 text-amber-500" />
        ) : (
          <ExclamationTriangleIcon className="w-3 h-3 text-red-500" />
        )}
        <span className="text-xs text-gray-500 uppercase">{label}</span>
      </div>
      <p className={`text-2xl font-bold ${colorClass}`}>
        {value.toFixed(0)}
      </p>
      <p className="text-xs text-gray-400">ms</p>
    </div>
  );
}

/**
 * StreamingLatencyWidget component
 */
export function StreamingLatencyWidget({
  refreshInterval = 30000,
  className = '',
}) {
  const [latencyData, setLatencyData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const mountedRef = useRef(true);

  const fetchLatency = useCallback(async () => {
    try {
      const data = await getStreamingLatency('24h');

      if (mountedRef.current) {
        setLatencyData(data);
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
    fetchLatency();

    const interval = setInterval(fetchLatency, refreshInterval);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchLatency, refreshInterval]);

  if (isLoading) {
    return <StreamingLatencyWidgetSkeleton />;
  }

  if (error) {
    return <StreamingLatencyWidgetError onRetry={fetchLatency} />;
  }

  const status = latencyData?.status || 'unknown';
  const statusColor = status === 'healthy' ? 'text-green-600' : status === 'degraded' ? 'text-amber-600' : 'text-gray-500';

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        overflow-hidden
        ${className}
      `}
      role="region"
      aria-label="Streaming Latency"
    >
      {/* Header */}
      <div className="p-4 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-yellow-100 dark:bg-yellow-900/30">
              <BoltIcon className="w-5 h-5 text-yellow-600 dark:text-yellow-400" />
            </div>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">
              Streaming Latency
            </h3>
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-xs font-medium capitalize ${statusColor}`}>
              {status}
            </span>
            <button
              onClick={fetchLatency}
              className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              aria-label="Refresh"
            >
              <ArrowPathIcon className="w-4 h-4 text-gray-500" />
            </button>
          </div>
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          Analysis latency percentiles (24h)
        </p>
      </div>

      {/* Percentile Cards */}
      <div className="p-4 grid grid-cols-3 gap-3 border-b border-gray-200 dark:border-gray-700">
        <LatencyCard
          label="P50"
          value={latencyData?.p50_ms || 0}
          threshold={LATENCY_THRESHOLDS.p50}
        />
        <LatencyCard
          label="P95"
          value={latencyData?.p95_ms || 0}
          threshold={LATENCY_THRESHOLDS.p95}
        />
        <LatencyCard
          label="P99"
          value={latencyData?.p99_ms || 0}
          threshold={LATENCY_THRESHOLDS.p99}
        />
      </div>

      {/* Trend Chart */}
      <div className="p-4">
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-xs font-medium text-gray-500 uppercase">
            24-Hour Trend
          </h4>
          <span className="text-xs text-gray-500">
            Avg: {latencyData?.avg_ms?.toFixed(0) || 0}ms | {latencyData?.throughput_rps?.toLocaleString() || 0} RPS
          </span>
        </div>
        <div className="h-36">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={latencyData?.trend_data || []} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
              <XAxis
                dataKey="label"
                tick={{ fontSize: 10 }}
                tickLine={false}
                axisLine={{ stroke: '#e5e7eb' }}
                interval="preserveStartEnd"
              />
              <YAxis
                tick={{ fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(value) => `${value}ms`}
              />
              <Tooltip content={<CustomTooltip />} />
              <Line
                type="monotone"
                dataKey="p50"
                stroke="#10B981"
                strokeWidth={2}
                dot={false}
                name="P50"
              />
              <Line
                type="monotone"
                dataKey="p95"
                stroke="#F59E0B"
                strokeWidth={2}
                dot={false}
                name="P95"
              />
              <Line
                type="monotone"
                dataKey="p99"
                stroke="#DC2626"
                strokeWidth={2}
                dot={false}
                name="P99"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Legend */}
      <div className="px-4 pb-4 flex items-center justify-center gap-6">
        <div className="flex items-center gap-1">
          <span className="w-3 h-0.5 bg-green-500 rounded" />
          <span className="text-xs text-gray-500">P50</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="w-3 h-0.5 bg-amber-500 rounded" />
          <span className="text-xs text-gray-500">P95</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="w-3 h-0.5 bg-red-500 rounded" />
          <span className="text-xs text-gray-500">P99</span>
        </div>
      </div>

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700">
        <DataFreshnessIndicator timestamp={lastUpdated} label="Updated" />
      </div>
    </div>
  );
}

StreamingLatencyWidget.propTypes = {
  refreshInterval: PropTypes.number,
  className: PropTypes.string,
};

export default StreamingLatencyWidget;
