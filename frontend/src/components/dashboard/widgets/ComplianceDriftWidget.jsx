/**
 * Compliance Drift Widget
 *
 * Displays compliance control failures requiring remediation.
 *
 * Per ADR-075: Widget ID 'palantir-compliance-drift', Category: COMPLIANCE
 *
 * @module components/dashboard/widgets/ComplianceDriftWidget
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  ClipboardDocumentCheckIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  XCircleIcon,
} from '@heroicons/react/24/solid';
import { DataFreshnessIndicator } from '../../palantir/DataFreshnessIndicator';

// Mock compliance drift data
const MOCK_DRIFT_DATA = {
  frameworks: [
    { name: 'SOC 2', passing: 45, failing: 3, total: 48 },
    { name: 'HIPAA', passing: 28, failing: 2, total: 30 },
    { name: 'CMMC L2', passing: 108, failing: 5, total: 113 },
    { name: 'NIST 800-53', passing: 95, failing: 7, total: 102 },
  ],
  recentFailures: [
    { id: 'ctrl-001', control: 'AC-2.3', framework: 'NIST', description: 'Access review not completed', daysOpen: 3 },
    { id: 'ctrl-002', control: 'AU-6', framework: 'NIST', description: 'Log review overdue', daysOpen: 7 },
    { id: 'ctrl-003', control: 'CC6.1', framework: 'SOC 2', description: 'Encryption key rotation', daysOpen: 1 },
  ],
};

/**
 * Framework progress bar
 */
function FrameworkRow({ name, passing, failing, total }) {
  const percentage = (passing / total) * 100;
  const isHealthy = failing === 0;

  return (
    <div className="py-2">
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
          {name}
        </span>
        <div className="flex items-center gap-2">
          {isHealthy ? (
            <CheckCircleIcon className="w-4 h-4 text-green-500" />
          ) : (
            <span className="text-xs text-red-600 font-medium">{failing} failing</span>
          )}
        </div>
      </div>
      <div className="h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full transition-all ${isHealthy ? 'bg-green-500' : 'bg-amber-500'}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <p className="text-xs text-gray-500 mt-0.5">
        {passing}/{total} controls passing
      </p>
    </div>
  );
}

/**
 * ComplianceDriftWidget component
 */
export function ComplianceDriftWidget({
  refreshInterval = 300000,
  onControlClick = null,
  className = '',
}) {
  const [driftData, setDriftData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const mountedRef = useRef(true);

  const fetchDrift = useCallback(async () => {
    try {
      await new Promise((resolve) => setTimeout(resolve, 500));

      if (mountedRef.current) {
        setDriftData(MOCK_DRIFT_DATA);
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
    fetchDrift();

    const interval = setInterval(fetchDrift, refreshInterval);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchDrift, refreshInterval]);

  if (isLoading) {
    return (
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 animate-pulse">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-8 h-8 rounded-lg bg-surface-200 dark:bg-surface-700" />
          <div className="w-32 h-5 rounded bg-surface-200 dark:bg-surface-700" />
        </div>
        <div className="space-y-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-10 bg-surface-100 dark:bg-surface-700 rounded" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-red-200 p-4 flex flex-col items-center justify-center min-h-[200px]">
        <ExclamationTriangleIcon className="w-8 h-8 text-red-500 mb-2" />
        <p className="text-sm text-gray-600 mb-3">Failed to load compliance data</p>
        <button
          onClick={fetchDrift}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-blue-600 hover:bg-blue-50 rounded-lg"
        >
          <ArrowPathIcon className="w-4 h-4" />
          Retry
        </button>
      </div>
    );
  }

  const totalFailing = driftData?.frameworks.reduce((sum, f) => sum + f.failing, 0) || 0;

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        overflow-hidden
        ${className}
      `}
    >
      {/* Header */}
      <div className="p-4 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-teal-100 dark:bg-teal-900/30">
              <ClipboardDocumentCheckIcon className="w-5 h-5 text-teal-600 dark:text-teal-400" />
            </div>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">
              Compliance Drift
            </h3>
          </div>
          {totalFailing > 0 && (
            <span className="px-2 py-0.5 text-xs font-medium bg-red-100 text-red-700 rounded-full">
              {totalFailing} drifts
            </span>
          )}
        </div>
      </div>

      {/* Framework Status */}
      <div className="p-4 divide-y divide-gray-100 dark:divide-gray-700">
        {driftData?.frameworks.map((framework) => (
          <FrameworkRow key={framework.name} {...framework} />
        ))}
      </div>

      {/* Recent Failures */}
      {driftData?.recentFailures.length > 0 && (
        <div className="border-t border-gray-200 dark:border-gray-700">
          <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50">
            <h4 className="text-xs font-medium text-gray-500 uppercase">
              Recent Control Failures
            </h4>
          </div>
          <div className="divide-y divide-gray-100 dark:divide-gray-700">
            {driftData.recentFailures.slice(0, 3).map((failure) => (
              <button
                key={failure.id}
                onClick={() => onControlClick?.(failure)}
                className="
                  w-full text-left px-4 py-2
                  hover:bg-gray-50 dark:hover:bg-gray-800
                  transition-colors
                "
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <XCircleIcon className="w-4 h-4 text-red-500" />
                    <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                      {failure.control}
                    </span>
                    <span className="text-xs text-gray-500">
                      ({failure.framework})
                    </span>
                  </div>
                  <span className="text-xs text-gray-500">
                    {failure.daysOpen}d open
                  </span>
                </div>
                <p className="text-xs text-gray-500 ml-6 mt-0.5 line-clamp-1">
                  {failure.description}
                </p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700">
        <DataFreshnessIndicator timestamp={lastUpdated} label="Updated" />
      </div>
    </div>
  );
}

ComplianceDriftWidget.propTypes = {
  refreshInterval: PropTypes.number,
  onControlClick: PropTypes.func,
  className: PropTypes.string,
};

export default ComplianceDriftWidget;
