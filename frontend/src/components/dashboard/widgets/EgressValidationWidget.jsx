/**
 * Egress Validation Widget
 *
 * Displays network egress monitoring status and violations
 * for air-gapped environments.
 *
 * Per ADR-078: Widget ID 'airgap-egress-validation', Category: SECURITY
 *
 * @module components/dashboard/widgets/EgressValidationWidget
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  GlobeAltIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  ShieldCheckIcon,
  NoSymbolIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/solid';
import { getEgressStatus } from '../../../services/airgapApi';
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
function EgressValidationWidgetSkeleton() {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 animate-pulse">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 rounded-lg bg-surface-200 dark:bg-surface-700" />
        <div className="w-32 h-5 rounded bg-surface-200 dark:bg-surface-700" />
      </div>
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="h-20 rounded-lg bg-surface-100 dark:bg-surface-700" />
        <div className="h-20 rounded-lg bg-surface-100 dark:bg-surface-700" />
      </div>
      <div className="space-y-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-14 rounded bg-surface-100 dark:bg-surface-700" />
        ))}
      </div>
    </div>
  );
}

/**
 * Error state
 */
function EgressValidationWidgetError({ onRetry }) {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-red-200 dark:border-red-800 p-4 flex flex-col items-center justify-center min-h-[200px]">
      <ExclamationTriangleIcon className="w-8 h-8 text-red-500 mb-2" />
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
        Failed to load egress status
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
 * Violation card
 */
function ViolationCard({ violation, onClick }) {
  const config = SEVERITY_CONFIG[violation.severity] || SEVERITY_CONFIG.medium;

  return (
    <button
      onClick={() => onClick?.(violation)}
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
            {violation.severity.toUpperCase()}
          </span>
          {violation.blocked ? (
            <span className="flex items-center gap-1 text-xs text-green-600">
              <NoSymbolIcon className="w-3 h-3" />
              Blocked
            </span>
          ) : (
            <span className="flex items-center gap-1 text-xs text-amber-600">
              <ExclamationTriangleIcon className="w-3 h-3" />
              Allowed
            </span>
          )}
        </div>
        <ChevronRightIcon className="w-4 h-4 text-gray-400" />
      </div>

      <div className="mb-2">
        <p className="text-sm font-mono text-gray-900 dark:text-gray-100 truncate">
          {violation.destination}:{violation.port}
        </p>
        <p className="text-xs text-gray-500 dark:text-gray-400">
          From: {violation.source_device} via {violation.protocol}
        </p>
      </div>

      <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
        <span className="line-clamp-1 flex-1 mr-2">{violation.reason}</span>
        <span className="flex-shrink-0">{formatRelativeTime(violation.detected_at)}</span>
      </div>
    </button>
  );
}

/**
 * EgressValidationWidget component
 */
export function EgressValidationWidget({
  refreshInterval = 30000,
  maxViolations = 4,
  onViolationClick = null,
  className = '',
}) {
  const [egressData, setEgressData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const mountedRef = useRef(true);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await getEgressStatus();

      if (mountedRef.current) {
        setEgressData(data);
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
    fetchStatus();

    const interval = setInterval(fetchStatus, refreshInterval);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchStatus, refreshInterval]);

  if (isLoading) {
    return <EgressValidationWidgetSkeleton />;
  }

  if (error) {
    return <EgressValidationWidgetError onRetry={fetchStatus} />;
  }

  const blockRate = egressData?.total_connections_24h > 0
    ? ((egressData.blocked_connections_24h / egressData.total_connections_24h) * 100).toFixed(2)
    : 0;

  const violations = egressData?.recent_violations || [];
  const criticalCount = violations.filter((v) => v.severity === 'critical').length;

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        overflow-hidden
        ${className}
      `}
      role="region"
      aria-label="Egress Validation"
    >
      {/* Header */}
      <div className="p-4 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-rose-100 dark:bg-rose-900/30">
              <GlobeAltIcon className="w-5 h-5 text-rose-600 dark:text-rose-400" />
            </div>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">
              Egress Validation
            </h3>
          </div>
          <div className="flex items-center gap-2">
            {egressData?.monitoring_enabled ? (
              <span className="flex items-center gap-1 text-xs text-green-600">
                <ShieldCheckIcon className="w-3 h-3" />
                Active
              </span>
            ) : (
              <span className="flex items-center gap-1 text-xs text-red-600">
                <ExclamationTriangleIcon className="w-3 h-3" />
                Disabled
              </span>
            )}
            <button
              onClick={fetchStatus}
              className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              aria-label="Refresh"
            >
              <ArrowPathIcon className="w-4 h-4 text-gray-500" />
            </button>
          </div>
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          Network egress monitoring for air-gapped environment
        </p>
      </div>

      {/* Stats */}
      <div className="p-4 grid grid-cols-2 gap-4 border-b border-gray-200 dark:border-gray-700">
        <div className="p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
          <p className="text-xs text-blue-600 dark:text-blue-400">Connections (24h)</p>
          <p className="text-2xl font-bold text-blue-700 dark:text-blue-300">
            {egressData?.total_connections_24h?.toLocaleString() || 0}
          </p>
          <p className="text-xs text-blue-500 mt-1">
            {egressData?.blocked_connections_24h || 0} blocked ({blockRate}%)
          </p>
        </div>
        <div className="p-3 rounded-lg bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800">
          <p className="text-xs text-green-600 dark:text-green-400">Allowed Domains</p>
          <p className="text-2xl font-bold text-green-700 dark:text-green-300">
            {egressData?.allowed_domains || 0}
          </p>
          <p className="text-xs text-green-500 mt-1">
            In allowlist
          </p>
        </div>
      </div>

      {/* Recent Violations */}
      <div className="p-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-xs font-medium text-gray-500 uppercase">
            Recent Violations
          </h4>
          {criticalCount > 0 && (
            <span className="px-2 py-0.5 text-xs font-medium bg-red-100 text-red-700 rounded-full">
              {criticalCount} critical
            </span>
          )}
        </div>
        {violations.length > 0 ? (
          <div className="space-y-2">
            {violations.slice(0, maxViolations).map((violation) => (
              <ViolationCard
                key={violation.violation_id}
                violation={violation}
                onClick={onViolationClick}
              />
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500 dark:text-gray-400">
            <ShieldCheckIcon className="w-12 h-12 mx-auto mb-2 text-green-500 opacity-50" />
            <p className="text-sm font-medium">No egress violations</p>
            <p className="text-xs mt-1">All traffic within policy</p>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>
            {violations.length} total violations
          </span>
          <DataFreshnessIndicator timestamp={lastUpdated} compact />
        </div>
      </div>
    </div>
  );
}

EgressValidationWidget.propTypes = {
  refreshInterval: PropTypes.number,
  maxViolations: PropTypes.number,
  onViolationClick: PropTypes.func,
  className: PropTypes.string,
};

export default EgressValidationWidget;
