/**
 * SBOM Status Widget
 *
 * Displays Software Bill of Materials generation status, format,
 * and component counts for monitored repositories.
 *
 * Per ADR-076: Widget ID 'supply-chain-sbom-status', Category: SECURITY
 *
 * @module components/dashboard/widgets/SBOMStatusWidget
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  DocumentTextIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
  ExclamationCircleIcon,
} from '@heroicons/react/24/solid';
import { getSBOMStatus } from '../../../services/supplyChainApi';
import { DataFreshnessIndicator } from '../../palantir/DataFreshnessIndicator';

// Status configurations
const STATUS_CONFIG = {
  complete: {
    icon: CheckCircleIcon,
    color: 'text-green-500',
    bgColor: 'bg-green-100 dark:bg-green-900/30',
    label: 'Complete',
  },
  generating: {
    icon: ClockIcon,
    color: 'text-amber-500',
    bgColor: 'bg-amber-100 dark:bg-amber-900/30',
    label: 'Generating',
  },
  failed: {
    icon: ExclamationCircleIcon,
    color: 'text-red-500',
    bgColor: 'bg-red-100 dark:bg-red-900/30',
    label: 'Failed',
  },
  pending: {
    icon: ClockIcon,
    color: 'text-gray-500',
    bgColor: 'bg-gray-100 dark:bg-gray-900/30',
    label: 'Pending',
  },
};

/**
 * Loading skeleton
 */
function SBOMStatusWidgetSkeleton() {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 animate-pulse">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-surface-200 dark:bg-surface-700" />
          <div className="w-28 h-5 rounded bg-surface-200 dark:bg-surface-700" />
        </div>
        <div className="w-20 h-5 rounded-full bg-surface-200 dark:bg-surface-700" />
      </div>
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="flex justify-between items-center py-2">
            <div className="w-32 h-4 rounded bg-surface-200 dark:bg-surface-700" />
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
function SBOMStatusWidgetError({ onRetry }) {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-red-200 dark:border-red-800 p-4 flex flex-col items-center justify-center min-h-[200px]">
      <ExclamationTriangleIcon className="w-8 h-8 text-red-500 mb-2" />
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
        Failed to load SBOM status
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
 * Repository row
 */
function RepositoryRow({ repo, onClick }) {
  const statusConfig = STATUS_CONFIG[repo.status] || STATUS_CONFIG.pending;
  const StatusIcon = statusConfig.icon;

  return (
    <button
      onClick={() => onClick?.(repo)}
      className="
        w-full flex items-center justify-between py-2.5 px-2 -mx-2 rounded-lg
        hover:bg-gray-50 dark:hover:bg-gray-800/50
        transition-colors text-left
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1
      "
    >
      <div className="flex items-center gap-2 min-w-0">
        <StatusIcon className={`w-4 h-4 flex-shrink-0 ${statusConfig.color}`} />
        <span className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
          {repo.id}
        </span>
        <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 uppercase">
          {repo.format}
        </span>
      </div>
      <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400 flex-shrink-0">
        <span>{repo.components} components</span>
        {repo.vulnerabilities > 0 && (
          <span className="text-red-600 font-medium">
            {repo.vulnerabilities} vuln
          </span>
        )}
      </div>
    </button>
  );
}

/**
 * SBOMStatusWidget component
 */
export function SBOMStatusWidget({
  refreshInterval = 60000,
  onRepositoryClick = null,
  className = '',
}) {
  const [sbomData, setSbomData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const mountedRef = useRef(true);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await getSBOMStatus();

      if (mountedRef.current) {
        setSbomData(data);
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
    return <SBOMStatusWidgetSkeleton />;
  }

  if (error) {
    return <SBOMStatusWidgetError onRetry={fetchStatus} />;
  }

  const totalComponents = sbomData?.repositories?.reduce((sum, r) => sum + r.components, 0) || 0;
  const totalVulnerabilities = sbomData?.repositories?.reduce((sum, r) => sum + r.vulnerabilities, 0) || 0;
  const completeCount = sbomData?.repositories?.filter((r) => r.status === 'complete').length || 0;
  const totalRepos = sbomData?.repositories?.length || 0;

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        overflow-hidden
        ${className}
      `}
      role="region"
      aria-label="SBOM Status"
    >
      {/* Header */}
      <div className="p-4 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-emerald-100 dark:bg-emerald-900/30">
              <DocumentTextIcon className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
            </div>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">
              SBOM Status
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
          Software Bill of Materials generation status
        </p>
      </div>

      {/* Summary Stats */}
      <div className="px-4 py-3 bg-gray-50 dark:bg-gray-800/50 grid grid-cols-3 gap-4 border-b border-gray-200 dark:border-gray-700">
        <div className="text-center">
          <p className="text-xs text-gray-500">Repositories</p>
          <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            {completeCount}/{totalRepos}
          </p>
        </div>
        <div className="text-center">
          <p className="text-xs text-gray-500">Components</p>
          <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            {totalComponents.toLocaleString()}
          </p>
        </div>
        <div className="text-center">
          <p className="text-xs text-gray-500">Vulnerabilities</p>
          <p className={`text-lg font-semibold ${totalVulnerabilities > 0 ? 'text-red-600' : 'text-green-600'}`}>
            {totalVulnerabilities}
          </p>
        </div>
      </div>

      {/* Repository List */}
      <div className="p-4">
        {sbomData?.repositories?.length > 0 ? (
          <div className="divide-y divide-gray-100 dark:divide-gray-700">
            {sbomData.repositories.map((repo) => (
              <RepositoryRow
                key={repo.id}
                repo={repo}
                onClick={onRepositoryClick}
              />
            ))}
          </div>
        ) : (
          <div className="text-center py-6 text-gray-500 dark:text-gray-400">
            <DocumentTextIcon className="w-8 h-8 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No SBOM data available</p>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>Format: {sbomData?.format?.toUpperCase() || 'CycloneDX'}</span>
          <span>Last scan: {sbomData?.last_generated ? new Date(sbomData.last_generated).toLocaleDateString() : 'N/A'}</span>
        </div>
      </div>
    </div>
  );
}

SBOMStatusWidget.propTypes = {
  refreshInterval: PropTypes.number,
  onRepositoryClick: PropTypes.func,
  className: PropTypes.string,
};

export default SBOMStatusWidget;
