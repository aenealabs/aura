/**
 * Container Escape Widget
 *
 * Displays container escape attempts with MITRE ATT&CK mapping
 * and blocking status.
 *
 * Per ADR-077: Widget ID 'runtime-container-escape', Category: SECURITY
 *
 * @module components/dashboard/widgets/ContainerEscapeWidget
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  BugAntIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  ShieldCheckIcon,
  ShieldExclamationIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/solid';
import { getContainerEscapeAttempts } from '../../../services/runtimeSecurityApi';
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

/**
 * Loading skeleton
 */
function ContainerEscapeWidgetSkeleton() {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 animate-pulse">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-surface-200 dark:bg-surface-700" />
          <div className="w-32 h-5 rounded bg-surface-200 dark:bg-surface-700" />
        </div>
        <div className="w-16 h-5 rounded-full bg-surface-200 dark:bg-surface-700" />
      </div>
      <div className="space-y-3">
        {[1, 2].map((i) => (
          <div key={i} className="p-3 rounded-lg bg-surface-100 dark:bg-surface-700">
            <div className="w-full h-4 rounded bg-surface-200 dark:bg-surface-600 mb-2" />
            <div className="w-3/4 h-3 rounded bg-surface-200 dark:bg-surface-600" />
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Error state
 */
function ContainerEscapeWidgetError({ onRetry }) {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-red-200 dark:border-red-800 p-4 flex flex-col items-center justify-center min-h-[200px]">
      <ExclamationTriangleIcon className="w-8 h-8 text-red-500 mb-2" />
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
        Failed to load escape attempts
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
 * Escape attempt card
 */
function EscapeAttemptCard({ attempt, onClick }) {
  const config = SEVERITY_CONFIG[attempt.severity] || SEVERITY_CONFIG.medium;

  return (
    <button
      onClick={() => onClick?.(attempt)}
      className={`
        w-full text-left p-3 rounded-lg border
        ${config.bgColor} ${config.borderColor}
        hover:shadow-sm transition-all duration-200
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1
      `}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 text-xs font-medium rounded ${config.badge}`}>
            {attempt.severity.toUpperCase()}
          </span>
          {attempt.blocked ? (
            <span className="flex items-center gap-1 text-xs text-green-600">
              <ShieldCheckIcon className="w-3 h-3" />
              Blocked
            </span>
          ) : (
            <span className="flex items-center gap-1 text-xs text-red-600">
              <ShieldExclamationIcon className="w-3 h-3" />
              Unblocked
            </span>
          )}
        </div>
        <ChevronRightIcon className="w-4 h-4 text-gray-400" />
      </div>

      <div className="mb-2">
        <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
          {attempt.technique}
        </p>
        <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">
          {attempt.pod_name} in {attempt.namespace}
        </p>
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs px-1.5 py-0.5 rounded bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 font-mono">
            {attempt.mitre_technique}
          </span>
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {attempt.mitre_tactic}
          </span>
        </div>
        <span className="text-xs text-gray-500 dark:text-gray-400">
          {formatRelativeTime(attempt.detected_at)}
        </span>
      </div>
    </button>
  );
}

/**
 * ContainerEscapeWidget component
 */
export function ContainerEscapeWidget({
  refreshInterval = 30000,
  maxAttempts = 3,
  onAttemptClick = null,
  className = '',
}) {
  const [attempts, setAttempts] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const mountedRef = useRef(true);

  const fetchAttempts = useCallback(async () => {
    try {
      const data = await getContainerEscapeAttempts();

      if (mountedRef.current) {
        setAttempts(data);
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
    fetchAttempts();

    const interval = setInterval(fetchAttempts, refreshInterval);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchAttempts, refreshInterval]);

  if (isLoading) {
    return <ContainerEscapeWidgetSkeleton />;
  }

  if (error) {
    return <ContainerEscapeWidgetError onRetry={fetchAttempts} />;
  }

  // Sort by severity and recency
  const severityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
  const sortedAttempts = attempts
    ? [...attempts]
        .sort((a, b) => {
          const severityDiff = severityOrder[a.severity] - severityOrder[b.severity];
          if (severityDiff !== 0) return severityDiff;
          return new Date(b.detected_at) - new Date(a.detected_at);
        })
        .slice(0, maxAttempts)
    : [];

  const criticalCount = attempts?.filter((a) => a.severity === 'critical').length || 0;
  const blockedCount = attempts?.filter((a) => a.blocked).length || 0;
  const totalCount = attempts?.length || 0;

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        overflow-hidden
        ${className}
      `}
      role="region"
      aria-label="Container Escape Attempts"
    >
      {/* Header */}
      <div className="p-4 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-red-100 dark:bg-red-900/30">
              <BugAntIcon className="w-5 h-5 text-red-600 dark:text-red-400" />
            </div>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">
              Container Escapes
            </h3>
          </div>
          <div className="flex items-center gap-2">
            {criticalCount > 0 && (
              <span className="px-2 py-0.5 text-xs font-medium bg-red-100 text-red-700 rounded-full">
                {criticalCount} critical
              </span>
            )}
            <button
              onClick={fetchAttempts}
              className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              aria-label="Refresh"
            >
              <ArrowPathIcon className="w-4 h-4 text-gray-500" />
            </button>
          </div>
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          Container escape attempts with MITRE ATT&CK mapping
        </p>
      </div>

      {/* Summary */}
      <div className="px-4 py-3 bg-gray-50 dark:bg-gray-800/50 grid grid-cols-3 gap-4 border-b border-gray-200 dark:border-gray-700">
        <div className="text-center">
          <p className="text-xs text-gray-500">Total Attempts</p>
          <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            {totalCount}
          </p>
        </div>
        <div className="text-center">
          <p className="text-xs text-gray-500">Blocked</p>
          <p className="text-lg font-semibold text-green-600">
            {blockedCount}
          </p>
        </div>
        <div className="text-center">
          <p className="text-xs text-gray-500">Block Rate</p>
          <p className={`text-lg font-semibold ${totalCount > 0 && blockedCount / totalCount >= 0.9 ? 'text-green-600' : 'text-amber-600'}`}>
            {totalCount > 0 ? ((blockedCount / totalCount) * 100).toFixed(0) : 100}%
          </p>
        </div>
      </div>

      {/* Attempts List */}
      <div className="p-4">
        {sortedAttempts.length > 0 ? (
          <div className="space-y-3">
            {sortedAttempts.map((attempt) => (
              <EscapeAttemptCard
                key={attempt.attempt_id}
                attempt={attempt}
                onClick={onAttemptClick}
              />
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500 dark:text-gray-400">
            <ShieldCheckIcon className="w-12 h-12 mx-auto mb-2 text-green-500 opacity-50" />
            <p className="text-sm font-medium">No escape attempts detected</p>
            <p className="text-xs mt-1">Containers are secure</p>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>
            MITRE: {[...new Set(attempts?.map((a) => a.mitre_tactic) || [])].length} tactics
          </span>
          <DataFreshnessIndicator timestamp={lastUpdated} compact />
        </div>
      </div>
    </div>
  );
}

ContainerEscapeWidget.propTypes = {
  refreshInterval: PropTypes.number,
  maxAttempts: PropTypes.number,
  onAttemptClick: PropTypes.func,
  className: PropTypes.string,
};

export default ContainerEscapeWidget;
