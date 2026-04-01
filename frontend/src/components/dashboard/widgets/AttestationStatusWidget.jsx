/**
 * Attestation Status Widget
 *
 * Displays signed SBOM count, Sigstore verification status,
 * and recent attestation records.
 *
 * Per ADR-076: Widget ID 'supply-chain-attestation', Category: COMPLIANCE
 *
 * @module components/dashboard/widgets/AttestationStatusWidget
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  ShieldCheckIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
} from '@heroicons/react/24/solid';
import { getAttestationStatus } from '../../../services/supplyChainApi';
import { DataFreshnessIndicator } from '../../palantir/DataFreshnessIndicator';

// Sigstore status configurations
const SIGSTORE_STATUS_CONFIG = {
  operational: {
    color: 'text-green-600',
    bgColor: 'bg-green-100 dark:bg-green-900/30',
    label: 'Operational',
  },
  degraded: {
    color: 'text-amber-600',
    bgColor: 'bg-amber-100 dark:bg-amber-900/30',
    label: 'Degraded',
  },
  unavailable: {
    color: 'text-red-600',
    bgColor: 'bg-red-100 dark:bg-red-900/30',
    label: 'Unavailable',
  },
};

/**
 * Loading skeleton
 */
function AttestationStatusWidgetSkeleton() {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 animate-pulse">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 rounded-lg bg-surface-200 dark:bg-surface-700" />
        <div className="w-32 h-5 rounded bg-surface-200 dark:bg-surface-700" />
      </div>
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="h-16 rounded-lg bg-surface-100 dark:bg-surface-700" />
        <div className="h-16 rounded-lg bg-surface-100 dark:bg-surface-700" />
      </div>
      <div className="space-y-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-10 rounded bg-surface-100 dark:bg-surface-700" />
        ))}
      </div>
    </div>
  );
}

/**
 * Error state
 */
function AttestationStatusWidgetError({ onRetry }) {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-red-200 dark:border-red-800 p-4 flex flex-col items-center justify-center min-h-[200px]">
      <ExclamationTriangleIcon className="w-8 h-8 text-red-500 mb-2" />
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
        Failed to load attestation status
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
 * Attestation record row
 */
function AttestationRow({ attestation }) {
  const isVerified = attestation.signed && attestation.verified;

  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-100 dark:border-gray-700 last:border-0">
      <div className="flex items-center gap-2 min-w-0">
        {isVerified ? (
          <CheckCircleIcon className="w-4 h-4 text-green-500 flex-shrink-0" />
        ) : attestation.signed ? (
          <ClockIcon className="w-4 h-4 text-amber-500 flex-shrink-0" />
        ) : (
          <XCircleIcon className="w-4 h-4 text-red-500 flex-shrink-0" />
        )}
        <span className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
          {attestation.repository}
        </span>
      </div>
      <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400 flex-shrink-0">
        <span className={`px-1.5 py-0.5 rounded ${isVerified ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'}`}>
          {isVerified ? 'Verified' : attestation.signed ? 'Pending' : 'Unsigned'}
        </span>
        <span className="w-16 text-right">{formatRelativeTime(attestation.timestamp)}</span>
      </div>
    </div>
  );
}

/**
 * AttestationStatusWidget component
 */
export function AttestationStatusWidget({
  refreshInterval = 300000,
  onAttestationClick = null,
  className = '',
}) {
  const [attestationData, setAttestationData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const mountedRef = useRef(true);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await getAttestationStatus();

      if (mountedRef.current) {
        setAttestationData(data);
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
    return <AttestationStatusWidgetSkeleton />;
  }

  if (error) {
    return <AttestationStatusWidgetError onRetry={fetchStatus} />;
  }

  const sigstoreConfig = SIGSTORE_STATUS_CONFIG[attestationData?.sigstore_status] || SIGSTORE_STATUS_CONFIG.unavailable;
  const totalSBOMs = (attestationData?.signed_sbom_count || 0) + (attestationData?.unsigned_sbom_count || 0);
  const signedPercentage = totalSBOMs > 0
    ? ((attestationData.signed_sbom_count / totalSBOMs) * 100).toFixed(0)
    : 0;
  const verificationRate = attestationData?.signed_sbom_count > 0
    ? ((attestationData.sigstore_verified_count / attestationData.signed_sbom_count) * 100).toFixed(0)
    : 0;

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        overflow-hidden
        ${className}
      `}
      role="region"
      aria-label="Attestation Status"
    >
      {/* Header */}
      <div className="p-4 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-violet-100 dark:bg-violet-900/30">
              <ShieldCheckIcon className="w-5 h-5 text-violet-600 dark:text-violet-400" />
            </div>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">
              Attestation Status
            </h3>
          </div>
          <div className="flex items-center gap-2">
            <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${sigstoreConfig.bgColor} ${sigstoreConfig.color}`}>
              Sigstore: {sigstoreConfig.label}
            </span>
            <button
              onClick={fetchStatus}
              className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              aria-label="Refresh"
            >
              <ArrowPathIcon className="w-4 h-4 text-gray-500" />
            </button>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="p-4 grid grid-cols-2 gap-4">
        {/* Signed SBOMs */}
        <div className="p-3 rounded-lg bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800">
          <div className="flex items-center justify-between">
            <span className="text-xs text-green-700 dark:text-green-400">Signed SBOMs</span>
            <CheckCircleIcon className="w-4 h-4 text-green-500" />
          </div>
          <div className="mt-1 flex items-baseline gap-1">
            <span className="text-2xl font-bold text-green-700 dark:text-green-400">
              {attestationData?.signed_sbom_count || 0}
            </span>
            <span className="text-xs text-green-600 dark:text-green-500">
              / {totalSBOMs}
            </span>
          </div>
          <div className="mt-2 h-1 bg-green-200 dark:bg-green-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-green-500 transition-all"
              style={{ width: `${signedPercentage}%` }}
            />
          </div>
          <p className="text-xs text-green-600 dark:text-green-500 mt-1">
            {signedPercentage}% signed
          </p>
        </div>

        {/* Verified */}
        <div className="p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
          <div className="flex items-center justify-between">
            <span className="text-xs text-blue-700 dark:text-blue-400">Sigstore Verified</span>
            <ShieldCheckIcon className="w-4 h-4 text-blue-500" />
          </div>
          <div className="mt-1 flex items-baseline gap-1">
            <span className="text-2xl font-bold text-blue-700 dark:text-blue-400">
              {attestationData?.sigstore_verified_count || 0}
            </span>
            <span className="text-xs text-blue-600 dark:text-blue-500">
              / {attestationData?.signed_sbom_count || 0}
            </span>
          </div>
          <div className="mt-2 h-1 bg-blue-200 dark:bg-blue-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 transition-all"
              style={{ width: `${verificationRate}%` }}
            />
          </div>
          <p className="text-xs text-blue-600 dark:text-blue-500 mt-1">
            {verificationRate}% verified
          </p>
        </div>
      </div>

      {/* Recent Attestations */}
      <div className="border-t border-gray-200 dark:border-gray-700">
        <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50">
          <h4 className="text-xs font-medium text-gray-500 uppercase">
            Recent Attestations
          </h4>
        </div>
        <div className="px-4 py-2">
          {attestationData?.recent_attestations?.length > 0 ? (
            <div>
              {attestationData.recent_attestations.slice(0, 4).map((attestation) => (
                <AttestationRow
                  key={attestation.sbom_id}
                  attestation={attestation}
                />
              ))}
            </div>
          ) : (
            <div className="text-center py-4 text-gray-500 dark:text-gray-400">
              <ShieldCheckIcon className="w-6 h-6 mx-auto mb-1 opacity-30" />
              <p className="text-xs">No recent attestations</p>
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>Last verification: {formatRelativeTime(attestationData?.last_verification)}</span>
          <DataFreshnessIndicator timestamp={lastUpdated} compact />
        </div>
      </div>
    </div>
  );
}

AttestationStatusWidget.propTypes = {
  refreshInterval: PropTypes.number,
  onAttestationClick: PropTypes.func,
  className: PropTypes.string,
};

export default AttestationStatusWidget;
