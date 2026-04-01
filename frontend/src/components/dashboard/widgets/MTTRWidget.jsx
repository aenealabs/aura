/**
 * MTTR Widget
 *
 * Displays Mean Time To Remediation metrics comparing current vs target.
 *
 * Per ADR-075: Widget ID 'palantir-mttr', Category: ANALYTICS
 *
 * @module components/dashboard/widgets/MTTRWidget
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  ClockIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
} from '@heroicons/react/24/solid';
import { DataFreshnessIndicator } from '../../palantir/DataFreshnessIndicator';

// Mock MTTR data
const MOCK_MTTR_DATA = {
  current_mttr_hours: 18.5,
  target_mttr_hours: 24,
  previous_mttr_hours: 22.3,
  critical_mttr_hours: 4.2,
  high_mttr_hours: 12.8,
  medium_mttr_hours: 36.4,
  open_count: 23,
  closed_last_7d: 47,
};

/**
 * Format hours into readable string
 */
function formatDuration(hours) {
  if (hours < 1) {
    return `${Math.round(hours * 60)}m`;
  }
  if (hours < 24) {
    return `${hours.toFixed(1)}h`;
  }
  const days = Math.floor(hours / 24);
  const remainingHours = Math.round(hours % 24);
  return remainingHours > 0 ? `${days}d ${remainingHours}h` : `${days}d`;
}

/**
 * Progress arc for MTTR visualization
 */
function MTTRGauge({ current, target }) {
  const percentage = Math.min((current / target) * 100, 100);
  const isOnTarget = current <= target;
  const color = isOnTarget ? '#10B981' : '#EF4444';

  return (
    <div className="relative w-20 h-20 mx-auto">
      <svg className="w-full h-full -rotate-90" viewBox="0 0 36 36">
        {/* Background circle */}
        <circle
          cx="18"
          cy="18"
          r="15.5"
          fill="none"
          stroke="currentColor"
          strokeWidth="3"
          className="text-gray-200 dark:text-gray-700"
        />
        {/* Progress circle */}
        <circle
          cx="18"
          cy="18"
          r="15.5"
          fill="none"
          stroke={color}
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={`${percentage}, 100`}
          className="transition-all duration-500"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-lg font-bold text-gray-900 dark:text-gray-100">
          {formatDuration(current)}
        </span>
      </div>
    </div>
  );
}

/**
 * Severity MTTR row
 */
function SeverityRow({ severity, hours, color }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className={`font-medium ${color}`}>{severity}</span>
      <span className="text-gray-600 dark:text-gray-400">{formatDuration(hours)}</span>
    </div>
  );
}

/**
 * MTTRWidget component
 */
export function MTTRWidget({
  refreshInterval = 300000,
  onViewDetails = null,
  className = '',
}) {
  const [mttrData, setMttrData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const mountedRef = useRef(true);

  const fetchMTTR = useCallback(async () => {
    try {
      // Mock data for now
      await new Promise((resolve) => setTimeout(resolve, 400));

      if (mountedRef.current) {
        setMttrData(MOCK_MTTR_DATA);
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
    fetchMTTR();

    const interval = setInterval(fetchMTTR, refreshInterval);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchMTTR, refreshInterval]);

  if (isLoading) {
    return (
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 animate-pulse">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-8 h-8 rounded-lg bg-surface-200 dark:bg-surface-700" />
          <div className="w-16 h-5 rounded bg-surface-200 dark:bg-surface-700" />
        </div>
        <div className="w-20 h-20 rounded-full bg-surface-200 dark:bg-surface-700 mx-auto" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-red-200 p-4 flex flex-col items-center justify-center min-h-[150px]">
        <ExclamationTriangleIcon className="w-6 h-6 text-red-500 mb-2" />
        <p className="text-xs text-gray-600 mb-2">Failed to load</p>
        <button
          onClick={fetchMTTR}
          className="flex items-center gap-1 px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50 rounded"
        >
          <ArrowPathIcon className="w-3 h-3" />
          Retry
        </button>
      </div>
    );
  }

  const isOnTarget = mttrData?.current_mttr_hours <= mttrData?.target_mttr_hours;
  const improvement = mttrData?.previous_mttr_hours - mttrData?.current_mttr_hours;

  return (
    <button
      onClick={() => onViewDetails?.()}
      className={`
        w-full text-left
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        hover:border-surface-300 dark:hover:border-surface-600
        transition-colors cursor-pointer
        overflow-hidden
        ${className}
      `}
    >
      {/* Header */}
      <div className="p-3 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-cyan-100 dark:bg-cyan-900/30">
              <ClockIcon className="w-4 h-4 text-cyan-600 dark:text-cyan-400" />
            </div>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
              MTTR
            </h3>
          </div>
          {isOnTarget ? (
            <CheckCircleIcon className="w-4 h-4 text-green-500" />
          ) : (
            <ExclamationCircleIcon className="w-4 h-4 text-red-500" />
          )}
        </div>
      </div>

      {/* Gauge */}
      <div className="p-4">
        <MTTRGauge
          current={mttrData?.current_mttr_hours || 0}
          target={mttrData?.target_mttr_hours || 24}
        />
        <p className="text-xs text-center text-gray-500 dark:text-gray-400 mt-2">
          Target: {formatDuration(mttrData?.target_mttr_hours || 24)}
          {improvement > 0 && (
            <span className="text-green-600 ml-2">
              ↓ {formatDuration(improvement)}
            </span>
          )}
        </p>
      </div>

      {/* Breakdown by Severity */}
      <div className="px-4 pb-3 space-y-1">
        <SeverityRow
          severity="Critical"
          hours={mttrData?.critical_mttr_hours || 0}
          color="text-red-600"
        />
        <SeverityRow
          severity="High"
          hours={mttrData?.high_mttr_hours || 0}
          color="text-orange-600"
        />
        <SeverityRow
          severity="Medium"
          hours={mttrData?.medium_mttr_hours || 0}
          color="text-amber-600"
        />
      </div>

      {/* Footer */}
      <div className="px-3 py-2 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>{mttrData?.closed_last_7d} closed (7d)</span>
          <DataFreshnessIndicator timestamp={lastUpdated} compact />
        </div>
      </div>
    </button>
  );
}

MTTRWidget.propTypes = {
  refreshInterval: PropTypes.number,
  onViewDetails: PropTypes.func,
  className: PropTypes.string,
};

export default MTTRWidget;
