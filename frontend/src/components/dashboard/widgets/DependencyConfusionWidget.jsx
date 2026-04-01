/**
 * Dependency Confusion Widget
 *
 * Displays typosquatting alerts and namespace hijacking warnings
 * for supply chain security monitoring.
 *
 * Per ADR-076: Widget ID 'supply-chain-dependency-confusion', Category: SECURITY
 *
 * @module components/dashboard/widgets/DependencyConfusionWidget
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  ShieldExclamationIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  ChevronRightIcon,
  CheckCircleIcon,
} from '@heroicons/react/24/solid';
import { getDependencyConfusionAlerts } from '../../../services/supplyChainApi';
import { DataFreshnessIndicator } from '../../palantir/DataFreshnessIndicator';

// Severity color mappings
const SEVERITY_COLORS = {
  critical: {
    bg: 'bg-red-100 dark:bg-red-900/30',
    text: 'text-red-700 dark:text-red-300',
    border: 'border-red-200 dark:border-red-800',
    badge: 'bg-red-500 text-white',
  },
  high: {
    bg: 'bg-orange-100 dark:bg-orange-900/30',
    text: 'text-orange-700 dark:text-orange-300',
    border: 'border-orange-200 dark:border-orange-800',
    badge: 'bg-orange-500 text-white',
  },
  medium: {
    bg: 'bg-amber-100 dark:bg-amber-900/30',
    text: 'text-amber-700 dark:text-amber-300',
    border: 'border-amber-200 dark:border-amber-800',
    badge: 'bg-amber-500 text-white',
  },
  low: {
    bg: 'bg-green-100 dark:bg-green-900/30',
    text: 'text-green-700 dark:text-green-300',
    border: 'border-green-200 dark:border-green-800',
    badge: 'bg-green-500 text-white',
  },
};

// Alert type labels
const ALERT_TYPE_LABELS = {
  typosquat: 'Typosquatting',
  namespace_hijack: 'Namespace Hijack',
  version_confusion: 'Version Confusion',
};

/**
 * Loading skeleton
 */
function DependencyConfusionWidgetSkeleton() {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 animate-pulse">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-surface-200 dark:bg-surface-700" />
          <div className="w-36 h-5 rounded bg-surface-200 dark:bg-surface-700" />
        </div>
        <div className="w-16 h-5 rounded-full bg-surface-200 dark:bg-surface-700" />
      </div>
      <div className="space-y-3">
        {[1, 2].map((i) => (
          <div key={i} className="p-3 rounded-lg bg-surface-100 dark:bg-surface-700">
            <div className="w-24 h-4 rounded bg-surface-200 dark:bg-surface-600 mb-2" />
            <div className="w-full h-3 rounded bg-surface-200 dark:bg-surface-600" />
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Error state
 */
function DependencyConfusionWidgetError({ onRetry }) {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-red-200 dark:border-red-800 p-4 flex flex-col items-center justify-center min-h-[200px]">
      <ExclamationTriangleIcon className="w-8 h-8 text-red-500 mb-2" />
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
        Failed to load dependency alerts
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
 * Alert card
 */
function AlertCard({ alert, onClick }) {
  const colors = SEVERITY_COLORS[alert.severity] || SEVERITY_COLORS.medium;
  const typeLabel = ALERT_TYPE_LABELS[alert.alert_type] || alert.alert_type;

  return (
    <button
      onClick={() => onClick?.(alert)}
      className={`
        w-full text-left p-3 rounded-lg border
        ${colors.bg} ${colors.border}
        hover:shadow-sm transition-all duration-200
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1
        ${alert.acknowledged ? 'opacity-60' : ''}
      `}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 text-xs font-medium rounded ${colors.badge}`}>
            {alert.severity.toUpperCase()}
          </span>
          <span className="text-xs px-1.5 py-0.5 rounded bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300">
            {typeLabel}
          </span>
        </div>
        <ChevronRightIcon className="w-4 h-4 text-gray-400" />
      </div>

      <div className="mb-2">
        <div className="flex items-center gap-2 text-sm">
          <span className="font-mono font-medium text-gray-900 dark:text-gray-100">
            {alert.package_name}
          </span>
          <span className="text-gray-500">vs</span>
          <span className="font-mono text-red-600 dark:text-red-400">
            {alert.suspected_malicious}
          </span>
        </div>
      </div>

      <p className="text-xs text-gray-600 dark:text-gray-400 line-clamp-1 mb-2">
        {alert.description}
      </p>

      <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
        <span>Confidence: {alert.confidence_score}%</span>
        <span>{alert.repository_id}</span>
      </div>
    </button>
  );
}

/**
 * DependencyConfusionWidget component
 */
export function DependencyConfusionWidget({
  refreshInterval = 60000,
  maxAlerts = 4,
  onAlertClick = null,
  className = '',
}) {
  const [alerts, setAlerts] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const mountedRef = useRef(true);

  const fetchAlerts = useCallback(async () => {
    try {
      const data = await getDependencyConfusionAlerts({ acknowledged: false });

      if (mountedRef.current) {
        setAlerts(data);
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
    fetchAlerts();

    const interval = setInterval(fetchAlerts, refreshInterval);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchAlerts, refreshInterval]);

  if (isLoading) {
    return <DependencyConfusionWidgetSkeleton />;
  }

  if (error) {
    return <DependencyConfusionWidgetError onRetry={fetchAlerts} />;
  }

  // Sort by severity and limit
  const severityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
  const sortedAlerts = alerts
    ? [...alerts]
        .sort((a, b) => severityOrder[a.severity] - severityOrder[b.severity])
        .slice(0, maxAlerts)
    : [];

  const criticalCount = alerts?.filter((a) => a.severity === 'critical').length || 0;
  const highCount = alerts?.filter((a) => a.severity === 'high').length || 0;

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        overflow-hidden
        ${className}
      `}
      role="region"
      aria-label="Dependency Confusion Alerts"
    >
      {/* Header */}
      <div className="p-4 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-rose-100 dark:bg-rose-900/30">
              <ShieldExclamationIcon className="w-5 h-5 text-rose-600 dark:text-rose-400" />
            </div>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">
              Dependency Confusion
            </h3>
          </div>
          <div className="flex items-center gap-2">
            {(criticalCount > 0 || highCount > 0) && (
              <span className="px-2 py-0.5 text-xs font-medium bg-red-100 text-red-700 rounded-full">
                {criticalCount + highCount} critical/high
              </span>
            )}
            <button
              onClick={fetchAlerts}
              className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              aria-label="Refresh"
            >
              <ArrowPathIcon className="w-4 h-4 text-gray-500" />
            </button>
          </div>
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          Typosquatting and namespace hijacking alerts
        </p>
      </div>

      {/* Content */}
      <div className="p-4">
        {sortedAlerts.length === 0 ? (
          <div className="text-center py-8 text-gray-500 dark:text-gray-400">
            <CheckCircleIcon className="w-12 h-12 mx-auto mb-2 text-green-500 opacity-50" />
            <p className="text-sm font-medium">No dependency confusion alerts</p>
            <p className="text-xs mt-1">All packages verified</p>
          </div>
        ) : (
          <div className="space-y-3">
            {sortedAlerts.map((alert) => (
              <AlertCard
                key={alert.alert_id}
                alert={alert}
                onClick={onAlertClick}
              />
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>{alerts?.length || 0} total alerts</span>
          <DataFreshnessIndicator timestamp={lastUpdated} compact />
        </div>
      </div>
    </div>
  );
}

DependencyConfusionWidget.propTypes = {
  refreshInterval: PropTypes.number,
  maxAlerts: PropTypes.number,
  onAlertClick: PropTypes.func,
  className: PropTypes.string,
};

export default DependencyConfusionWidget;
