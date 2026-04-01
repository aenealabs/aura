/**
 * Bundle Status Widget
 *
 * Displays offline bundle version, expiration, and integrity
 * status for air-gapped deployments.
 *
 * Per ADR-078: Widget ID 'airgap-bundle-status', Category: OPERATIONS
 *
 * @module components/dashboard/widgets/BundleStatusWidget
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  ArchiveBoxIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
  ExclamationCircleIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/solid';
import { getBundleStatus } from '../../../services/airgapApi';
import { DataFreshnessIndicator } from '../../palantir/DataFreshnessIndicator';

// Status configurations
const STATUS_CONFIG = {
  current: {
    icon: CheckCircleIcon,
    color: 'text-green-500',
    bgColor: 'bg-green-100 dark:bg-green-900/30',
    label: 'Current',
  },
  expired: {
    icon: ExclamationCircleIcon,
    color: 'text-red-500',
    bgColor: 'bg-red-100 dark:bg-red-900/30',
    label: 'Expired',
  },
  pending: {
    icon: ClockIcon,
    color: 'text-amber-500',
    bgColor: 'bg-amber-100 dark:bg-amber-900/30',
    label: 'Pending',
  },
};

/**
 * Loading skeleton
 */
function BundleStatusWidgetSkeleton() {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 animate-pulse">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 rounded-lg bg-surface-200 dark:bg-surface-700" />
        <div className="w-28 h-5 rounded bg-surface-200 dark:bg-surface-700" />
      </div>
      <div className="h-24 rounded-lg bg-surface-100 dark:bg-surface-700 mb-4" />
      <div className="space-y-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-8 rounded bg-surface-100 dark:bg-surface-700" />
        ))}
      </div>
    </div>
  );
}

/**
 * Error state
 */
function BundleStatusWidgetError({ onRetry }) {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-red-200 dark:border-red-800 p-4 flex flex-col items-center justify-center min-h-[200px]">
      <ExclamationTriangleIcon className="w-8 h-8 text-red-500 mb-2" />
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
        Failed to load bundle status
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
 * Format bytes to human readable
 */
function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

/**
 * Calculate days until expiration
 */
function getDaysUntilExpiration(expiresAt) {
  if (!expiresAt) return null;
  const now = new Date();
  const expiry = new Date(expiresAt);
  const diffMs = expiry - now;
  return Math.ceil(diffMs / (1000 * 60 * 60 * 24));
}

/**
 * Bundle row
 */
function BundleRow({ bundle }) {
  const config = STATUS_CONFIG[bundle.status] || STATUS_CONFIG.pending;
  const StatusIcon = config.icon;

  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-100 dark:border-gray-700 last:border-0">
      <div className="flex items-center gap-2">
        <StatusIcon className={`w-4 h-4 ${config.color}`} />
        <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
          v{bundle.version}
        </span>
      </div>
      <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
        <span className={`px-1.5 py-0.5 rounded ${config.bgColor} ${config.color}`}>
          {config.label}
        </span>
        <span>
          {bundle.expires_in_days > 0
            ? `${bundle.expires_in_days}d remaining`
            : `Expired ${Math.abs(bundle.expires_in_days)}d ago`}
        </span>
      </div>
    </div>
  );
}

/**
 * BundleStatusWidget component
 */
export function BundleStatusWidget({
  refreshInterval = 300000,
  onBundleClick = null,
  className = '',
}) {
  const [bundleData, setBundleData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const mountedRef = useRef(true);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await getBundleStatus();

      if (mountedRef.current) {
        setBundleData(data);
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
    return <BundleStatusWidgetSkeleton />;
  }

  if (error) {
    return <BundleStatusWidgetError onRetry={fetchStatus} />;
  }

  const daysRemaining = getDaysUntilExpiration(bundleData?.expires_at);
  const isExpiringSoon = daysRemaining !== null && daysRemaining <= 7 && daysRemaining > 0;
  const isExpired = daysRemaining !== null && daysRemaining <= 0;
  const config = STATUS_CONFIG[bundleData?.status] || STATUS_CONFIG.current;

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        overflow-hidden
        ${className}
      `}
      role="region"
      aria-label="Bundle Status"
    >
      {/* Header */}
      <div className="p-4 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-cyan-100 dark:bg-cyan-900/30">
              <ArchiveBoxIcon className="w-5 h-5 text-cyan-600 dark:text-cyan-400" />
            </div>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">
              Bundle Status
            </h3>
          </div>
          <div className="flex items-center gap-2">
            <DataFreshnessIndicator timestamp={lastUpdated} compact />
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
          Offline bundle for air-gapped deployment
        </p>
      </div>

      {/* Current Bundle Info */}
      <div className="p-4">
        <div className={`p-4 rounded-lg ${config.bgColor} border ${isExpired ? 'border-red-300 dark:border-red-700' : isExpiringSoon ? 'border-amber-300 dark:border-amber-700' : 'border-green-300 dark:border-green-700'}`}>
          <div className="flex items-start justify-between mb-3">
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400">Current Bundle</p>
              <p className="text-xl font-bold text-gray-900 dark:text-gray-100">
                v{bundleData?.version || 'N/A'}
              </p>
            </div>
            <div className="flex items-center gap-1">
              {bundleData?.integrity_verified ? (
                <>
                  <ShieldCheckIcon className="w-4 h-4 text-green-500" />
                  <span className="text-xs text-green-600">Verified</span>
                </>
              ) : (
                <>
                  <ExclamationTriangleIcon className="w-4 h-4 text-red-500" />
                  <span className="text-xs text-red-600">Unverified</span>
                </>
              )}
            </div>
          </div>

          {/* Expiration Progress */}
          <div className="mb-3">
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-gray-600 dark:text-gray-400">Expires</span>
              <span className={`font-medium ${isExpired ? 'text-red-600' : isExpiringSoon ? 'text-amber-600' : 'text-gray-700 dark:text-gray-300'}`}>
                {daysRemaining !== null
                  ? daysRemaining > 0
                    ? `${daysRemaining} days remaining`
                    : 'Expired'
                  : 'N/A'}
              </span>
            </div>
            <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                className={`h-full transition-all ${isExpired ? 'bg-red-500' : isExpiringSoon ? 'bg-amber-500' : 'bg-green-500'}`}
                style={{ width: `${Math.max(0, Math.min(100, (daysRemaining / 30) * 100))}%` }}
              />
            </div>
          </div>

          {/* Bundle Details */}
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <p className="text-gray-500 dark:text-gray-400">Size</p>
              <p className="font-medium text-gray-900 dark:text-gray-100">
                {formatBytes(bundleData?.size_bytes || 0)}
              </p>
            </div>
            <div>
              <p className="text-gray-500 dark:text-gray-400">Checksum</p>
              <p className="font-mono text-gray-900 dark:text-gray-100 truncate">
                {bundleData?.checksum?.slice(0, 16)}...
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Components */}
      {bundleData?.components && (
        <div className="px-4 pb-4">
          <h4 className="text-xs font-medium text-gray-500 uppercase mb-2">
            Included Components
          </h4>
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(bundleData.components).map(([key, value]) => (
              <div key={key} className="p-2 rounded bg-gray-50 dark:bg-gray-800/50">
                <p className="text-xs text-gray-500 capitalize">{key.replace(/_/g, ' ')}</p>
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{value}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Bundle History */}
      {bundleData?.bundles?.length > 0 && (
        <div className="border-t border-gray-200 dark:border-gray-700">
          <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50">
            <h4 className="text-xs font-medium text-gray-500 uppercase">
              Bundle History
            </h4>
          </div>
          <div className="px-4 py-2">
            {bundleData.bundles.slice(0, 3).map((bundle) => (
              <BundleRow key={bundle.id} bundle={bundle} />
            ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>
            Created: {bundleData?.created_at
              ? new Date(bundleData.created_at).toLocaleDateString()
              : 'N/A'}
          </span>
          <span>ID: {bundleData?.bundle_id?.slice(-12) || 'N/A'}</span>
        </div>
      </div>
    </div>
  );
}

BundleStatusWidget.propTypes = {
  refreshInterval: PropTypes.number,
  onBundleClick: PropTypes.func,
  className: PropTypes.string,
};

export default BundleStatusWidget;
