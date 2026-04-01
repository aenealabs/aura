/**
 * Insider Risk Widget
 *
 * Displays count of users with elevated risk scores requiring attention.
 *
 * Per ADR-075: Widget ID 'palantir-insider-risk', Category: SECURITY
 * RBAC: security-engineer only
 *
 * @module components/dashboard/widgets/InsiderRiskWidget
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  UserGroupIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
} from '@heroicons/react/24/solid';
import { DataFreshnessIndicator } from '../../palantir/DataFreshnessIndicator';

// Mock insider risk data
const MOCK_RISK_DATA = {
  elevated_count: 7,
  high_risk_count: 2,
  medium_risk_count: 5,
  total_monitored: 1250,
  trend: 'up',
  trend_delta: 2,
  last_escalation: new Date(Date.now() - 3600000).toISOString(),
};

/**
 * Risk level indicator
 */
function RiskIndicator({ count, level, color }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-gray-500 dark:text-gray-400">{level}</span>
      <span className={`font-semibold ${color}`}>{count}</span>
    </div>
  );
}

/**
 * InsiderRiskWidget component
 */
export function InsiderRiskWidget({
  refreshInterval = 300000,
  onViewDetails = null,
  className = '',
}) {
  const [riskData, setRiskData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const mountedRef = useRef(true);

  const fetchRisk = useCallback(async () => {
    try {
      // Mock data for now
      await new Promise((resolve) => setTimeout(resolve, 400));

      if (mountedRef.current) {
        setRiskData(MOCK_RISK_DATA);
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
    fetchRisk();

    const interval = setInterval(fetchRisk, refreshInterval);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchRisk, refreshInterval]);

  if (isLoading) {
    return (
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 animate-pulse">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-8 h-8 rounded-lg bg-surface-200 dark:bg-surface-700" />
          <div className="w-24 h-5 rounded bg-surface-200 dark:bg-surface-700" />
        </div>
        <div className="w-16 h-10 rounded bg-surface-200 dark:bg-surface-700 mx-auto" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-red-200 p-4 flex flex-col items-center justify-center min-h-[150px]">
        <ExclamationTriangleIcon className="w-6 h-6 text-red-500 mb-2" />
        <p className="text-xs text-gray-600 mb-2">Failed to load</p>
        <button
          onClick={fetchRisk}
          className="flex items-center gap-1 px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50 rounded"
        >
          <ArrowPathIcon className="w-3 h-3" />
          Retry
        </button>
      </div>
    );
  }

  const TrendIcon = riskData?.trend === 'up' ? ArrowTrendingUpIcon : ArrowTrendingDownIcon;
  const trendColor = riskData?.trend === 'up' ? 'text-red-500' : 'text-green-500';

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
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-rose-100 dark:bg-rose-900/30">
            <UserGroupIcon className="w-4 h-4 text-rose-600 dark:text-rose-400" />
          </div>
          <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
            Insider Risk
          </h3>
        </div>
      </div>

      {/* Main Metric */}
      <div className="p-4 text-center">
        <div className="flex items-center justify-center gap-2">
          <span className="text-3xl font-bold text-gray-900 dark:text-gray-100">
            {riskData?.elevated_count || 0}
          </span>
          {riskData?.trend && (
            <div className={`flex items-center ${trendColor}`}>
              <TrendIcon className="w-4 h-4" />
              <span className="text-xs font-medium">
                {riskData.trend_delta > 0 ? '+' : ''}{riskData.trend_delta}
              </span>
            </div>
          )}
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          Elevated Risk Users
        </p>
      </div>

      {/* Breakdown */}
      <div className="px-4 pb-3 space-y-1">
        <RiskIndicator count={riskData?.high_risk_count || 0} level="High" color="text-red-600" />
        <RiskIndicator count={riskData?.medium_risk_count || 0} level="Medium" color="text-amber-600" />
      </div>

      {/* Footer */}
      <div className="px-3 py-2 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>{riskData?.total_monitored?.toLocaleString()} monitored</span>
          <DataFreshnessIndicator timestamp={lastUpdated} compact />
        </div>
      </div>
    </button>
  );
}

InsiderRiskWidget.propTypes = {
  refreshInterval: PropTypes.number,
  onViewDetails: PropTypes.func,
  className: PropTypes.string,
};

export default InsiderRiskWidget;
