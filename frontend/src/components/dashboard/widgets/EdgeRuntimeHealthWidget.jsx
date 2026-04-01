/**
 * Edge Runtime Health Widget
 *
 * Displays edge device sync status, health metrics, and
 * update availability.
 *
 * Per ADR-078: Widget ID 'airgap-edge-health', Category: OPERATIONS
 *
 * @module components/dashboard/widgets/EdgeRuntimeHealthWidget
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  ServerStackIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  XCircleIcon,
  ArrowDownTrayIcon,
} from '@heroicons/react/24/solid';
import { getEdgeHealth } from '../../../services/airgapApi';
import { DataFreshnessIndicator } from '../../palantir/DataFreshnessIndicator';

// Status configurations
const STATUS_CONFIG = {
  online: {
    icon: CheckCircleIcon,
    color: 'text-green-500',
    bgColor: 'bg-green-100 dark:bg-green-900/30',
    dotColor: 'bg-green-500',
    label: 'Online',
  },
  offline: {
    icon: XCircleIcon,
    color: 'text-red-500',
    bgColor: 'bg-red-100 dark:bg-red-900/30',
    dotColor: 'bg-red-500',
    label: 'Offline',
  },
  syncing: {
    icon: ArrowPathIcon,
    color: 'text-amber-500',
    bgColor: 'bg-amber-100 dark:bg-amber-900/30',
    dotColor: 'bg-amber-500',
    label: 'Syncing',
  },
};

/**
 * Loading skeleton
 */
function EdgeRuntimeHealthWidgetSkeleton() {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 animate-pulse">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 rounded-lg bg-surface-200 dark:bg-surface-700" />
        <div className="w-32 h-5 rounded bg-surface-200 dark:bg-surface-700" />
      </div>
      <div className="grid grid-cols-3 gap-3 mb-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-16 rounded-lg bg-surface-100 dark:bg-surface-700" />
        ))}
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
function EdgeRuntimeHealthWidgetError({ onRetry }) {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-red-200 dark:border-red-800 p-4 flex flex-col items-center justify-center min-h-[200px]">
      <ExclamationTriangleIcon className="w-8 h-8 text-red-500 mb-2" />
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
        Failed to load edge health
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
 * Health metric bar
 */
function HealthMetric({ label, value, threshold = 80 }) {
  const isWarning = value > threshold;
  const color = isWarning ? 'bg-amber-500' : 'bg-green-500';

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-500 w-10">{label}</span>
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
 * Device row
 */
function DeviceRow({ device, onClick }) {
  const config = STATUS_CONFIG[device.status] || STATUS_CONFIG.offline;
  const StatusIcon = config.icon;

  return (
    <button
      onClick={() => onClick?.(device)}
      className="
        w-full text-left p-3 rounded-lg border
        bg-gray-50 dark:bg-gray-800/50 border-gray-200 dark:border-gray-700
        hover:bg-gray-100 dark:hover:bg-gray-800
        hover:shadow-sm transition-all duration-200
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1
      "
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${config.dotColor}`} />
          <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
            {device.hostname}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {device.update_available && (
            <span className="flex items-center gap-1 text-xs text-blue-600">
              <ArrowDownTrayIcon className="w-3 h-3" />
              Update
            </span>
          )}
          <StatusIcon className={`w-4 h-4 ${config.color}`} />
        </div>
      </div>

      {/* Details */}
      <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 mb-2">
        <span>v{device.bundle_version}</span>
        <span>Last sync: {formatRelativeTime(device.last_sync)}</span>
      </div>

      {/* Health Metrics (if online) */}
      {device.status === 'online' && device.health_metrics && (
        <div className="space-y-1 mt-2 pt-2 border-t border-gray-200 dark:border-gray-700">
          <HealthMetric label="CPU" value={device.health_metrics.cpu} />
          <HealthMetric label="RAM" value={device.health_metrics.memory} />
          <HealthMetric label="Disk" value={device.health_metrics.disk} threshold={90} />
        </div>
      )}
    </button>
  );
}

/**
 * EdgeRuntimeHealthWidget component
 */
export function EdgeRuntimeHealthWidget({
  refreshInterval = 30000,
  onDeviceClick = null,
  className = '',
}) {
  const [healthData, setHealthData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const mountedRef = useRef(true);

  const fetchHealth = useCallback(async () => {
    try {
      const data = await getEdgeHealth();

      if (mountedRef.current) {
        setHealthData(data);
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
    return <EdgeRuntimeHealthWidgetSkeleton />;
  }

  if (error) {
    return <EdgeRuntimeHealthWidgetError onRetry={fetchHealth} />;
  }

  const onlineRate = healthData?.total_devices > 0
    ? ((healthData.online_count / healthData.total_devices) * 100).toFixed(0)
    : 0;
  const updateCount = healthData?.devices?.filter((d) => d.update_available).length || 0;

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        overflow-hidden
        ${className}
      `}
      role="region"
      aria-label="Edge Runtime Health"
    >
      {/* Header */}
      <div className="p-4 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-teal-100 dark:bg-teal-900/30">
              <ServerStackIcon className="w-5 h-5 text-teal-600 dark:text-teal-400" />
            </div>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">
              Edge Runtime Health
            </h3>
          </div>
          <div className="flex items-center gap-2">
            <DataFreshnessIndicator timestamp={lastUpdated} compact />
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
          Edge device sync and health status
        </p>
      </div>

      {/* Summary */}
      <div className="p-4 grid grid-cols-3 gap-3 border-b border-gray-200 dark:border-gray-700">
        <div className="text-center p-2 rounded-lg bg-green-50 dark:bg-green-900/20">
          <p className="text-xs text-gray-500">Online</p>
          <p className="text-xl font-bold text-green-600">
            {healthData?.online_count || 0}
          </p>
        </div>
        <div className="text-center p-2 rounded-lg bg-red-50 dark:bg-red-900/20">
          <p className="text-xs text-gray-500">Offline</p>
          <p className="text-xl font-bold text-red-600">
            {healthData?.offline_count || 0}
          </p>
        </div>
        <div className="text-center p-2 rounded-lg bg-amber-50 dark:bg-amber-900/20">
          <p className="text-xs text-gray-500">Syncing</p>
          <p className="text-xl font-bold text-amber-600">
            {healthData?.syncing_count || 0}
          </p>
        </div>
      </div>

      {/* Device List */}
      <div className="p-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-xs font-medium text-gray-500 uppercase">
            Edge Devices
          </h4>
          {updateCount > 0 && (
            <span className="text-xs text-blue-600">
              {updateCount} updates available
            </span>
          )}
        </div>
        {healthData?.devices?.length > 0 ? (
          <div className="space-y-2">
            {healthData.devices.slice(0, 4).map((device) => (
              <DeviceRow
                key={device.device_id}
                device={device}
                onClick={onDeviceClick}
              />
            ))}
          </div>
        ) : (
          <div className="text-center py-6 text-gray-500 dark:text-gray-400">
            <ServerStackIcon className="w-8 h-8 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No edge devices configured</p>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>
            {healthData?.total_devices || 0} total devices
          </span>
          <span>
            Online rate: {onlineRate}%
          </span>
        </div>
      </div>
    </div>
  );
}

EdgeRuntimeHealthWidget.propTypes = {
  refreshInterval: PropTypes.number,
  onDeviceClick: PropTypes.func,
  className: PropTypes.string,
};

export default EdgeRuntimeHealthWidget;
