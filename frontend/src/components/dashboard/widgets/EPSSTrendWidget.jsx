/**
 * EPSS Trend Widget
 *
 * Displays 30-day EPSS score trends for monitored CVEs.
 *
 * Per ADR-075: Widget ID 'palantir-epss-trend', Category: ANALYTICS
 *
 * @module components/dashboard/widgets/EPSSTrendWidget
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  ChartBarIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/solid';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { DataFreshnessIndicator } from '../../palantir/DataFreshnessIndicator';

// Generate mock trend data
function generateMockTrendData() {
  const data = [];
  const now = new Date();

  for (let i = 29; i >= 0; i--) {
    const date = new Date(now);
    date.setDate(date.getDate() - i);

    data.push({
      date: date.toISOString().split('T')[0],
      label: `${date.getMonth() + 1}/${date.getDate()}`,
      p50: Math.random() * 0.3 + 0.2,
      p95: Math.random() * 0.3 + 0.5,
      p99: Math.random() * 0.2 + 0.75,
    });
  }

  return data;
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
            <span className="text-gray-600 dark:text-gray-400">{entry.dataKey}</span>
          </div>
          <span className="font-medium text-gray-900 dark:text-gray-100">
            {(entry.value * 100).toFixed(1)}%
          </span>
        </div>
      ))}
    </div>
  );
}

/**
 * EPSSTrendWidget component
 */
export function EPSSTrendWidget({
  refreshInterval = 300000,
  className = '',
}) {
  const [trendData, setTrendData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const mountedRef = useRef(true);

  const fetchTrend = useCallback(async () => {
    try {
      // Mock data for now
      await new Promise((resolve) => setTimeout(resolve, 500));
      const data = generateMockTrendData();

      if (mountedRef.current) {
        setTrendData(data);
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
    fetchTrend();

    const interval = setInterval(fetchTrend, refreshInterval);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchTrend, refreshInterval]);

  if (isLoading) {
    return (
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 animate-pulse">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-8 h-8 rounded-lg bg-surface-200 dark:bg-surface-700" />
          <div className="w-32 h-5 rounded bg-surface-200 dark:bg-surface-700" />
        </div>
        <div className="h-48 bg-surface-100 dark:bg-surface-700 rounded" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-red-200 p-4 flex flex-col items-center justify-center min-h-[200px]">
        <ExclamationTriangleIcon className="w-8 h-8 text-red-500 mb-2" />
        <p className="text-sm text-gray-600 mb-3">Failed to load EPSS trends</p>
        <button
          onClick={fetchTrend}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-blue-600 hover:bg-blue-50 rounded-lg"
        >
          <ArrowPathIcon className="w-4 h-4" />
          Retry
        </button>
      </div>
    );
  }

  // Calculate current values
  const latest = trendData?.[trendData.length - 1];

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        overflow-hidden
        ${className}
      `}
    >
      {/* Header */}
      <div className="p-4 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-indigo-100 dark:bg-indigo-900/30">
              <ChartBarIcon className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
            </div>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">
              EPSS Score Trends
            </h3>
          </div>
          <button
            onClick={fetchTrend}
            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            aria-label="Refresh"
          >
            <ArrowPathIcon className="w-4 h-4 text-gray-500" />
          </button>
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          30-day percentile trends for monitored CVEs
        </p>
      </div>

      {/* Current Values */}
      {latest && (
        <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50 grid grid-cols-3 gap-4 border-b border-gray-200 dark:border-gray-700">
          <div className="text-center">
            <p className="text-xs text-gray-500">P50</p>
            <p className="text-lg font-semibold text-green-600">
              {(latest.p50 * 100).toFixed(1)}%
            </p>
          </div>
          <div className="text-center">
            <p className="text-xs text-gray-500">P95</p>
            <p className="text-lg font-semibold text-amber-600">
              {(latest.p95 * 100).toFixed(1)}%
            </p>
          </div>
          <div className="text-center">
            <p className="text-xs text-gray-500">P99</p>
            <p className="text-lg font-semibold text-red-600">
              {(latest.p99 * 100).toFixed(1)}%
            </p>
          </div>
        </div>
      )}

      {/* Chart */}
      <div className="p-4">
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={trendData} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
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
                tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
                domain={[0, 1]}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend
                wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }}
              />
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

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700">
        <DataFreshnessIndicator timestamp={lastUpdated} label="Updated" />
      </div>
    </div>
  );
}

EPSSTrendWidget.propTypes = {
  refreshInterval: PropTypes.number,
  className: PropTypes.string,
};

export default EPSSTrendWidget;
