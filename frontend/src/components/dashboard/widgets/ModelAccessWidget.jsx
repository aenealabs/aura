/**
 * Model Access Widget
 *
 * Displays model weight access anomalies and suspicious
 * access patterns.
 *
 * Per ADR-079: Widget ID 'ai-security-model-access', Category: SECURITY
 *
 * @module components/dashboard/widgets/ModelAccessWidget
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  CubeTransparentIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  ShieldCheckIcon,
  EyeIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/solid';
import { getModelAccessAnomalies } from '../../../services/aiSecurityApi';
import { DataFreshnessIndicator } from '../../palantir/DataFreshnessIndicator';

// Severity configurations
const SEVERITY_CONFIG = {
  critical: {
    bgColor: 'bg-red-100 dark:bg-red-900/30',
    borderColor: 'border-red-200 dark:border-red-800',
    textColor: 'text-red-700 dark:text-red-300',
    badge: 'bg-red-500 text-white',
  },
  high: {
    bgColor: 'bg-orange-100 dark:bg-orange-900/30',
    borderColor: 'border-orange-200 dark:border-orange-800',
    textColor: 'text-orange-700 dark:text-orange-300',
    badge: 'bg-orange-500 text-white',
  },
  medium: {
    bgColor: 'bg-amber-100 dark:bg-amber-900/30',
    borderColor: 'border-amber-200 dark:border-amber-800',
    textColor: 'text-amber-700 dark:text-amber-300',
    badge: 'bg-amber-500 text-white',
  },
  low: {
    bgColor: 'bg-green-100 dark:bg-green-900/30',
    borderColor: 'border-green-200 dark:border-green-800',
    textColor: 'text-green-700 dark:text-green-300',
    badge: 'bg-green-500 text-white',
  },
};

// Anomaly type labels
const ANOMALY_TYPE_LABELS = {
  unusual_volume: 'Unusual Volume',
  weight_exfiltration_attempt: 'Exfiltration Attempt',
  off_hours_access: 'Off-Hours Access',
  unauthorized_model: 'Unauthorized Model',
  rate_limit_exceeded: 'Rate Limit',
};

/**
 * Loading skeleton
 */
function ModelAccessWidgetSkeleton() {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 animate-pulse">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 rounded-lg bg-surface-200 dark:bg-surface-700" />
        <div className="w-28 h-5 rounded bg-surface-200 dark:bg-surface-700" />
      </div>
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="h-16 rounded-lg bg-surface-100 dark:bg-surface-700" />
        <div className="h-16 rounded-lg bg-surface-100 dark:bg-surface-700" />
      </div>
      <div className="space-y-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-16 rounded bg-surface-100 dark:bg-surface-700" />
        ))}
      </div>
    </div>
  );
}

/**
 * Error state
 */
function ModelAccessWidgetError({ onRetry }) {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-red-200 dark:border-red-800 p-4 flex flex-col items-center justify-center min-h-[200px]">
      <ExclamationTriangleIcon className="w-8 h-8 text-red-500 mb-2" />
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
        Failed to load model access data
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
 * Format relative time
 */
function formatRelativeTime(isoString) {
  if (!isoString) return 'N/A';
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
 * Anomaly card
 */
function AnomalyCard({ anomaly, onClick }) {
  const config = SEVERITY_CONFIG[anomaly.severity] || SEVERITY_CONFIG.medium;
  const typeLabel = ANOMALY_TYPE_LABELS[anomaly.anomaly_type] || anomaly.anomaly_type;

  return (
    <button
      onClick={() => onClick?.(anomaly)}
      className={`
        w-full text-left p-3 rounded-lg border
        ${config.bgColor} ${config.borderColor}
        hover:shadow-sm transition-all duration-200
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1
        ${anomaly.investigated ? 'opacity-60' : ''}
      `}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`px-2 py-0.5 text-xs font-medium rounded ${config.badge}`}>
            {anomaly.severity.toUpperCase()}
          </span>
          <span className="text-xs px-1.5 py-0.5 rounded bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300">
            {typeLabel}
          </span>
          {anomaly.investigated && (
            <span className="text-xs text-green-600">
              <EyeIcon className="w-3 h-3 inline mr-0.5" />
              Investigated
            </span>
          )}
        </div>
        <ChevronRightIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />
      </div>

      <div className="mb-2">
        <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
          {anomaly.model_id}
        </p>
        <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">
          User: {anomaly.user_id}
        </p>
      </div>

      <p className="text-xs text-gray-600 dark:text-gray-400 line-clamp-1 mb-2">
        {anomaly.access_pattern}
      </p>

      <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
        <span className="line-clamp-1 flex-1 mr-2">{anomaly.details}</span>
        <span className="flex-shrink-0">{formatRelativeTime(anomaly.detected_at)}</span>
      </div>
    </button>
  );
}

/**
 * ModelAccessWidget component
 */
export function ModelAccessWidget({
  refreshInterval = 60000,
  maxAnomalies = 3,
  onAnomalyClick = null,
  className = '',
}) {
  const [accessData, setAccessData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const mountedRef = useRef(true);

  const fetchAnomalies = useCallback(async () => {
    try {
      const data = await getModelAccessAnomalies();

      if (mountedRef.current) {
        setAccessData(data);
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
    fetchAnomalies();

    const interval = setInterval(fetchAnomalies, refreshInterval);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchAnomalies, refreshInterval]);

  if (isLoading) {
    return <ModelAccessWidgetSkeleton />;
  }

  if (error) {
    return <ModelAccessWidgetError onRetry={fetchAnomalies} />;
  }

  // Sort by severity and recency
  const severityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
  const sortedAnomalies = accessData?.anomalies
    ? [...accessData.anomalies]
        .filter((a) => !a.investigated)
        .sort((a, b) => {
          const severityDiff = severityOrder[a.severity] - severityOrder[b.severity];
          if (severityDiff !== 0) return severityDiff;
          return new Date(b.detected_at) - new Date(a.detected_at);
        })
        .slice(0, maxAnomalies)
    : [];

  const criticalCount = accessData?.anomalies?.filter((a) => a.severity === 'critical' && !a.investigated).length || 0;

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        overflow-hidden
        ${className}
      `}
      role="region"
      aria-label="Model Access Anomalies"
    >
      {/* Header */}
      <div className="p-4 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-violet-100 dark:bg-violet-900/30">
              <CubeTransparentIcon className="w-5 h-5 text-violet-600 dark:text-violet-400" />
            </div>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">
              Model Access
            </h3>
          </div>
          <div className="flex items-center gap-2">
            {criticalCount > 0 && (
              <span className="px-2 py-0.5 text-xs font-medium bg-red-100 text-red-700 rounded-full">
                {criticalCount} critical
              </span>
            )}
            <button
              onClick={fetchAnomalies}
              className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              aria-label="Refresh"
            >
              <ArrowPathIcon className="w-4 h-4 text-gray-500" />
            </button>
          </div>
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          Model weight access anomalies
        </p>
      </div>

      {/* Stats */}
      <div className="p-4 grid grid-cols-2 gap-3 border-b border-gray-200 dark:border-gray-700">
        <div className="text-center p-2 rounded-lg bg-blue-50 dark:bg-blue-900/20">
          <p className="text-xs text-gray-500">Accesses (24h)</p>
          <p className="text-xl font-bold text-blue-600">
            {accessData?.total_accesses_24h?.toLocaleString() || 0}
          </p>
        </div>
        <div className="text-center p-2 rounded-lg bg-purple-50 dark:bg-purple-900/20">
          <p className="text-xs text-gray-500">Unique Users</p>
          <p className="text-xl font-bold text-purple-600">
            {accessData?.unique_users_24h || 0}
          </p>
        </div>
      </div>

      {/* Anomalies List */}
      <div className="p-4">
        <h4 className="text-xs font-medium text-gray-500 uppercase mb-3">
          Open Anomalies ({accessData?.anomaly_count || 0})
        </h4>
        {sortedAnomalies.length > 0 ? (
          <div className="space-y-2">
            {sortedAnomalies.map((anomaly) => (
              <AnomalyCard
                key={anomaly.anomaly_id}
                anomaly={anomaly}
                onClick={onAnomalyClick}
              />
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500 dark:text-gray-400">
            <ShieldCheckIcon className="w-12 h-12 mx-auto mb-2 text-green-500 opacity-50" />
            <p className="text-sm font-medium">No access anomalies</p>
            <p className="text-xs mt-1">Model access patterns are normal</p>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>
            {accessData?.anomalies?.filter((a) => a.investigated).length || 0} investigated
          </span>
          <DataFreshnessIndicator timestamp={lastUpdated} compact />
        </div>
      </div>
    </div>
  );
}

ModelAccessWidget.propTypes = {
  refreshInterval: PropTypes.number,
  maxAnomalies: PropTypes.number,
  onAnomalyClick: PropTypes.func,
  className: PropTypes.string,
};

export default ModelAccessWidget;
