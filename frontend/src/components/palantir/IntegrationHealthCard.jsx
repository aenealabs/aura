/**
 * Integration Health Card Component
 *
 * Displays a summary card for Palantir integration health status
 * including circuit breaker state, sync status, and data freshness.
 *
 * @module components/palantir/IntegrationHealthCard
 */

import React from 'react';
import PropTypes from 'prop-types';
import {
  ShieldCheckIcon,
  ShieldExclamationIcon,
  ExclamationTriangleIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/solid';
import { CircuitBreakerIndicator } from './CircuitBreakerIndicator';
import { DataFreshnessIndicator } from './DataFreshnessIndicator';

// Status configurations
const STATUS_CONFIG = {
  healthy: {
    icon: ShieldCheckIcon,
    color: 'text-green-600',
    bgColor: 'bg-green-50',
    borderColor: 'border-green-200',
    label: 'Healthy',
    description: 'All systems operational',
  },
  warning: {
    icon: ExclamationTriangleIcon,
    color: 'text-amber-600',
    bgColor: 'bg-amber-50',
    borderColor: 'border-amber-200',
    label: 'Warning',
    description: 'Some issues detected',
  },
  degraded: {
    icon: ShieldExclamationIcon,
    color: 'text-red-600',
    bgColor: 'bg-red-50',
    borderColor: 'border-red-200',
    label: 'Degraded',
    description: 'Integration experiencing issues',
  },
  error: {
    icon: ShieldExclamationIcon,
    color: 'text-red-600',
    bgColor: 'bg-red-50',
    borderColor: 'border-red-200',
    label: 'Error',
    description: 'Unable to connect to Palantir',
  },
  unknown: {
    icon: ArrowPathIcon,
    color: 'text-gray-500',
    bgColor: 'bg-gray-50',
    borderColor: 'border-gray-200',
    label: 'Unknown',
    description: 'Status unavailable',
  },
};

/**
 * Skeleton loader for the card
 */
function IntegrationHealthCardSkeleton() {
  return (
    <div className="rounded-lg border border-gray-200 p-4 animate-pulse">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gray-200 rounded-lg" />
          <div>
            <div className="h-4 w-24 bg-gray-200 rounded mb-1" />
            <div className="h-3 w-32 bg-gray-200 rounded" />
          </div>
        </div>
        <div className="h-6 w-20 bg-gray-200 rounded-full" />
      </div>
      <div className="space-y-2">
        <div className="h-3 w-full bg-gray-200 rounded" />
        <div className="h-3 w-3/4 bg-gray-200 rounded" />
      </div>
    </div>
  );
}

/**
 * IntegrationHealthCard component
 */
export function IntegrationHealthCard({
  status = 'unknown',
  health = null,
  circuitBreaker = null,
  syncStatus = null,
  lastSyncTime = null,
  isLoading = false,
  onRefresh = null,
  onResetBreaker = null,
  showCircuitBreaker = true,
  showSyncDetails = true,
  className = '',
}) {
  // Show skeleton while loading
  if (isLoading) {
    return <IntegrationHealthCardSkeleton />;
  }

  const config = STATUS_CONFIG[status] || STATUS_CONFIG.unknown;
  const Icon = config.icon;

  // Count sync statuses
  const syncCounts = syncStatus ? {
    total: Object.keys(syncStatus).length,
    synced: Object.values(syncStatus).filter((s) => s.last_sync_status === 'synced').length,
    failed: Object.values(syncStatus).filter((s) => s.last_sync_status === 'failed').length,
    pending: Object.values(syncStatus).filter((s) => s.last_sync_status === 'pending').length,
  } : null;

  return (
    <div
      className={`
        rounded-lg border ${config.borderColor} ${config.bgColor}
        overflow-hidden
        ${className}
      `}
      role="region"
      aria-label="Palantir Integration Health"
    >
      {/* Header */}
      <div className="p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg bg-white shadow-sm`}>
              <Icon className={`w-6 h-6 ${config.color}`} aria-hidden="true" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">Palantir AIP</h3>
              <p className={`text-sm ${config.color}`}>{config.label}</p>
            </div>
          </div>

          {/* Status Badge */}
          <div className="flex items-center gap-2">
            {lastSyncTime && (
              <DataFreshnessIndicator timestamp={lastSyncTime} compact />
            )}
            {onRefresh && (
              <button
                onClick={onRefresh}
                className="
                  p-1.5 rounded-full hover:bg-white/50
                  transition-colors focus:outline-none focus:ring-2
                  focus:ring-blue-500 focus:ring-offset-1
                "
                aria-label="Refresh status"
              >
                <ArrowPathIcon className="w-4 h-4 text-gray-500" />
              </button>
            )}
          </div>
        </div>

        <p className="text-sm text-gray-600">{config.description}</p>

        {/* Sync Summary */}
        {showSyncDetails && syncCounts && (
          <div className="mt-3 flex gap-4 text-sm">
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-green-500" />
              <span className="text-gray-600">{syncCounts.synced} synced</span>
            </div>
            {syncCounts.failed > 0 && (
              <div className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-red-500" />
                <span className="text-gray-600">{syncCounts.failed} failed</span>
              </div>
            )}
            {syncCounts.pending > 0 && (
              <div className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-amber-500" />
                <span className="text-gray-600">{syncCounts.pending} pending</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Circuit Breaker Section */}
      {showCircuitBreaker && circuitBreaker && (
        <div className="border-t border-gray-200 p-4 bg-white/50">
          <CircuitBreakerIndicator
            state={circuitBreaker.state}
            failureCount={circuitBreaker.failure_count}
            failureThreshold={5}
            successCount={circuitBreaker.success_count}
            totalFailures={circuitBreaker.total_failures}
            totalSuccesses={circuitBreaker.total_successes}
            lastFailure={circuitBreaker.last_failure}
            lastStateChange={circuitBreaker.last_state_change}
            recoveryTimeout={circuitBreaker.recovery_timeout_seconds}
            onReset={onResetBreaker}
            showActions={!!onResetBreaker}
            showMetrics={false}
          />
        </div>
      )}

      {/* Sync Details Table */}
      {showSyncDetails && syncStatus && (
        <div className="border-t border-gray-200 bg-white">
          <div className="px-4 py-2 bg-gray-50 border-b border-gray-200">
            <h4 className="text-xs font-medium text-gray-500 uppercase">
              Sync Status by Object Type
            </h4>
          </div>
          <div className="divide-y divide-gray-100">
            {Object.entries(syncStatus).map(([objectType, sync]) => (
              <div
                key={objectType}
                className="px-4 py-2 flex items-center justify-between text-sm"
              >
                <span className="font-medium text-gray-700">{objectType}</span>
                <div className="flex items-center gap-3">
                  <span className="text-gray-500">
                    {sync.objects_synced.toLocaleString()} objects
                  </span>
                  <span
                    className={`
                      px-2 py-0.5 text-xs rounded-full
                      ${sync.last_sync_status === 'synced'
                        ? 'bg-green-100 text-green-700'
                        : sync.last_sync_status === 'failed'
                          ? 'bg-red-100 text-red-700'
                          : 'bg-amber-100 text-amber-700'
                      }
                    `}
                  >
                    {sync.last_sync_status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

IntegrationHealthCard.propTypes = {
  status: PropTypes.oneOf(['healthy', 'warning', 'degraded', 'error', 'unknown']),
  health: PropTypes.shape({
    status: PropTypes.string,
    connector_status: PropTypes.string,
    is_healthy: PropTypes.bool,
    message: PropTypes.string,
  }),
  circuitBreaker: PropTypes.shape({
    state: PropTypes.string,
    failure_count: PropTypes.number,
    success_count: PropTypes.number,
    total_failures: PropTypes.number,
    total_successes: PropTypes.number,
    last_failure: PropTypes.string,
    last_state_change: PropTypes.string,
    recovery_timeout_seconds: PropTypes.number,
  }),
  syncStatus: PropTypes.objectOf(
    PropTypes.shape({
      object_type: PropTypes.string,
      last_sync_time: PropTypes.string,
      last_sync_status: PropTypes.string,
      objects_synced: PropTypes.number,
      objects_failed: PropTypes.number,
      conflicts_resolved: PropTypes.number,
      last_error: PropTypes.string,
    })
  ),
  lastSyncTime: PropTypes.string,
  isLoading: PropTypes.bool,
  onRefresh: PropTypes.func,
  onResetBreaker: PropTypes.func,
  showCircuitBreaker: PropTypes.bool,
  showSyncDetails: PropTypes.bool,
  className: PropTypes.string,
};

export default IntegrationHealthCard;
