/**
 * Sync Status Widget
 *
 * Displays real-time status of Palantir Ontology object synchronization
 * with object counts, last sync times, and circuit breaker state.
 *
 * Per ADR-075: Widget ID 'palantir-sync-status', Category: OPERATIONS
 *
 * @module components/dashboard/widgets/SyncStatusWidget
 */

import React from 'react';
import PropTypes from 'prop-types';
import {
  ArrowPathIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ClockIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/solid';
import { usePalantirSync } from '../../../hooks/usePalantirSync';
import { CircuitBreakerIndicator } from '../../palantir/CircuitBreakerIndicator';
import { DataFreshnessIndicator } from '../../palantir/DataFreshnessIndicator';

// Status icon mappings
const STATUS_ICONS = {
  synced: { icon: CheckCircleIcon, color: 'text-green-500' },
  pending: { icon: ClockIcon, color: 'text-amber-500' },
  failed: { icon: ExclamationCircleIcon, color: 'text-red-500' },
};

/**
 * Loading skeleton
 */
function SyncStatusWidgetSkeleton() {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 animate-pulse">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-surface-200 dark:bg-surface-700" />
          <div className="w-32 h-5 rounded bg-surface-200 dark:bg-surface-700" />
        </div>
        <div className="w-20 h-5 rounded-full bg-surface-200 dark:bg-surface-700" />
      </div>
      <div className="space-y-2">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="flex justify-between items-center py-2">
            <div className="w-24 h-4 rounded bg-surface-200 dark:bg-surface-700" />
            <div className="w-16 h-4 rounded bg-surface-200 dark:bg-surface-700" />
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Error state
 */
function SyncStatusWidgetError({ onRetry }) {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-red-200 dark:border-red-800 p-4 flex flex-col items-center justify-center min-h-[200px]">
      <ExclamationTriangleIcon className="w-8 h-8 text-red-500 mb-2" />
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
        Failed to load sync status
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
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
  if (!isoString) return 'Never';
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins} min ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.floor(diffHours / 24)}d ago`;
}

/**
 * Sync status row
 */
function SyncStatusRow({ objectType, sync }) {
  const statusConfig = STATUS_ICONS[sync.last_sync_status] || STATUS_ICONS.pending;
  const StatusIcon = statusConfig.icon;

  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-100 dark:border-gray-700 last:border-0">
      <div className="flex items-center gap-2">
        <StatusIcon className={`w-4 h-4 ${statusConfig.color}`} />
        <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
          {objectType}
        </span>
      </div>
      <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
        <span>{sync.objects_synced.toLocaleString()}</span>
        <span className="w-20 text-right">{formatRelativeTime(sync.last_sync_time)}</span>
      </div>
    </div>
  );
}

/**
 * SyncStatusWidget component
 */
export function SyncStatusWidget({
  refreshInterval = 30000,
  showCircuitBreaker = true,
  onTriggerSync = null,
  className = '',
}) {
  const {
    syncStatus,
    circuitBreaker,
    lastSyncTime,
    isLoading,
    error,
    refetch,
    triggerObjectSync,
  } = usePalantirSync({ refreshInterval });

  // Show loading state
  if (isLoading) {
    return <SyncStatusWidgetSkeleton />;
  }

  // Show error state
  if (error) {
    return <SyncStatusWidgetError onRetry={refetch} />;
  }

  // Get queue count (mock for now)
  const queueCount = 0;

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        overflow-hidden
        ${className}
      `}
      role="region"
      aria-label="Ontology Sync Health"
    >
      {/* Header */}
      <div className="p-4 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-blue-100 dark:bg-blue-900/30">
              <ArrowPathIcon className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            </div>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">
              Ontology Sync Health
            </h3>
          </div>
          <div className="flex items-center gap-2">
            <DataFreshnessIndicator timestamp={lastSyncTime} compact />
            <button
              onClick={refetch}
              className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              aria-label="Refresh"
            >
              <ArrowPathIcon className="w-4 h-4 text-gray-500" />
            </button>
          </div>
        </div>
      </div>

      {/* Sync Status Table */}
      <div className="p-4">
        <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 mb-2 px-1">
          <span>Object Type</span>
          <div className="flex gap-4">
            <span>Count</span>
            <span className="w-20 text-right">Last Sync</span>
          </div>
        </div>

        {syncStatus && Object.entries(syncStatus).length > 0 ? (
          <div>
            {Object.entries(syncStatus).map(([objectType, sync]) => (
              <SyncStatusRow key={objectType} objectType={objectType} sync={sync} />
            ))}
          </div>
        ) : (
          <div className="text-center py-6 text-gray-500 dark:text-gray-400">
            <ArrowPathIcon className="w-8 h-8 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No sync data available</p>
          </div>
        )}
      </div>

      {/* Footer with Circuit Breaker */}
      {showCircuitBreaker && (
        <div className="px-4 pb-4 pt-2 border-t border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <span className="text-gray-600 dark:text-gray-400">Circuit Breaker:</span>
              {circuitBreaker && (
                <CircuitBreakerIndicator
                  state={circuitBreaker.state}
                  compact
                />
              )}
            </div>
            <span className="text-gray-500 dark:text-gray-400">
              Queue: {queueCount} events
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

SyncStatusWidget.propTypes = {
  refreshInterval: PropTypes.number,
  showCircuitBreaker: PropTypes.bool,
  onTriggerSync: PropTypes.func,
  className: PropTypes.string,
};

export default SyncStatusWidget;
