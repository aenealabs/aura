/**
 * Admission Decisions Widget
 *
 * Displays Kubernetes admission controller ALLOW/DENY/WARN decisions
 * with policy details and summary statistics.
 *
 * Per ADR-077: Widget ID 'runtime-admission-decisions', Category: SECURITY
 *
 * @module components/dashboard/widgets/AdmissionDecisionsWidget
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  ShieldCheckIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationCircleIcon,
} from '@heroicons/react/24/solid';
import { getAdmissionDecisions } from '../../../services/runtimeSecurityApi';
import { DataFreshnessIndicator } from '../../palantir/DataFreshnessIndicator';

// Decision configurations
const DECISION_CONFIG = {
  ALLOW: {
    icon: CheckCircleIcon,
    color: 'text-green-500',
    bgColor: 'bg-green-100 dark:bg-green-900/30',
    borderColor: 'border-green-200 dark:border-green-800',
  },
  DENY: {
    icon: XCircleIcon,
    color: 'text-red-500',
    bgColor: 'bg-red-100 dark:bg-red-900/30',
    borderColor: 'border-red-200 dark:border-red-800',
  },
  WARN: {
    icon: ExclamationCircleIcon,
    color: 'text-amber-500',
    bgColor: 'bg-amber-100 dark:bg-amber-900/30',
    borderColor: 'border-amber-200 dark:border-amber-800',
  },
};

/**
 * Loading skeleton
 */
function AdmissionDecisionsWidgetSkeleton() {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 animate-pulse">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-surface-200 dark:bg-surface-700" />
          <div className="w-36 h-5 rounded bg-surface-200 dark:bg-surface-700" />
        </div>
      </div>
      <div className="grid grid-cols-3 gap-3 mb-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-16 rounded-lg bg-surface-100 dark:bg-surface-700" />
        ))}
      </div>
      <div className="space-y-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-12 rounded bg-surface-100 dark:bg-surface-700" />
        ))}
      </div>
    </div>
  );
}

/**
 * Error state
 */
function AdmissionDecisionsWidgetError({ onRetry }) {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-red-200 dark:border-red-800 p-4 flex flex-col items-center justify-center min-h-[200px]">
      <ExclamationTriangleIcon className="w-8 h-8 text-red-500 mb-2" />
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
        Failed to load admission decisions
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
  if (!isoString) return 'N/A';
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
 * Summary stat card
 */
function StatCard({ label, count, icon: Icon, color, bgColor }) {
  return (
    <div className={`p-3 rounded-lg ${bgColor} border border-opacity-50`}>
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-600 dark:text-gray-400">{label}</span>
        <Icon className={`w-4 h-4 ${color}`} />
      </div>
      <p className={`text-xl font-bold ${color} mt-1`}>
        {count.toLocaleString()}
      </p>
    </div>
  );
}

/**
 * Decision row
 */
function DecisionRow({ decision, onClick }) {
  const config = DECISION_CONFIG[decision.decision] || DECISION_CONFIG.WARN;
  const DecisionIcon = config.icon;

  return (
    <button
      onClick={() => onClick?.(decision)}
      className={`
        w-full text-left p-3 rounded-lg border
        ${config.bgColor} ${config.borderColor}
        hover:shadow-sm transition-all duration-200
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1
      `}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <DecisionIcon className={`w-4 h-4 ${config.color} flex-shrink-0`} />
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                {decision.resource_name}
              </span>
              <span className="text-xs px-1.5 py-0.5 rounded bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400">
                {decision.resource_type}
              </span>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              {decision.namespace} / {decision.policy_name}
            </p>
          </div>
        </div>
        <span className="text-xs text-gray-500 dark:text-gray-400 flex-shrink-0">
          {formatRelativeTime(decision.timestamp)}
        </span>
      </div>
      <p className="text-xs text-gray-600 dark:text-gray-400 mt-2 line-clamp-1">
        {decision.reason}
      </p>
    </button>
  );
}

/**
 * AdmissionDecisionsWidget component
 */
export function AdmissionDecisionsWidget({
  refreshInterval = 30000,
  maxDecisions = 4,
  onDecisionClick = null,
  className = '',
}) {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const mountedRef = useRef(true);

  const fetchDecisions = useCallback(async () => {
    try {
      const result = await getAdmissionDecisions({ limit: maxDecisions });

      if (mountedRef.current) {
        setData(result);
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
  }, [maxDecisions]);

  useEffect(() => {
    mountedRef.current = true;
    fetchDecisions();

    const interval = setInterval(fetchDecisions, refreshInterval);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchDecisions, refreshInterval]);

  if (isLoading) {
    return <AdmissionDecisionsWidgetSkeleton />;
  }

  if (error) {
    return <AdmissionDecisionsWidgetError onRetry={fetchDecisions} />;
  }

  const { decisions = [], summary = {} } = data || {};

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        overflow-hidden
        ${className}
      `}
      role="region"
      aria-label="Admission Decisions"
    >
      {/* Header */}
      <div className="p-4 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-sky-100 dark:bg-sky-900/30">
              <ShieldCheckIcon className="w-5 h-5 text-sky-600 dark:text-sky-400" />
            </div>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">
              Admission Decisions
            </h3>
          </div>
          <div className="flex items-center gap-2">
            <DataFreshnessIndicator timestamp={lastUpdated} compact />
            <button
              onClick={fetchDecisions}
              className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              aria-label="Refresh"
            >
              <ArrowPathIcon className="w-4 h-4 text-gray-500" />
            </button>
          </div>
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          Kubernetes admission controller decisions (24h)
        </p>
      </div>

      {/* Summary Stats */}
      <div className="p-4 grid grid-cols-3 gap-3 border-b border-gray-200 dark:border-gray-700">
        <StatCard
          label="Allowed"
          count={summary.allow_count || 0}
          icon={CheckCircleIcon}
          color="text-green-600"
          bgColor="bg-green-50 dark:bg-green-900/20"
        />
        <StatCard
          label="Denied"
          count={summary.deny_count || 0}
          icon={XCircleIcon}
          color="text-red-600"
          bgColor="bg-red-50 dark:bg-red-900/20"
        />
        <StatCard
          label="Warned"
          count={summary.warn_count || 0}
          icon={ExclamationCircleIcon}
          color="text-amber-600"
          bgColor="bg-amber-50 dark:bg-amber-900/20"
        />
      </div>

      {/* Recent Decisions */}
      <div className="p-4">
        <h4 className="text-xs font-medium text-gray-500 uppercase mb-3">
          Recent Decisions
        </h4>
        {decisions.length > 0 ? (
          <div className="space-y-2">
            {decisions.slice(0, maxDecisions).map((decision) => (
              <DecisionRow
                key={decision.decision_id}
                decision={decision}
                onClick={onDecisionClick}
              />
            ))}
          </div>
        ) : (
          <div className="text-center py-6 text-gray-500 dark:text-gray-400">
            <ShieldCheckIcon className="w-8 h-8 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No recent decisions</p>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>Total: {summary.total_24h?.toLocaleString() || 0} decisions (24h)</span>
          <span>
            Block rate: {summary.total_24h > 0 ? ((summary.deny_count / summary.total_24h) * 100).toFixed(1) : 0}%
          </span>
        </div>
      </div>
    </div>
  );
}

AdmissionDecisionsWidget.propTypes = {
  refreshInterval: PropTypes.number,
  maxDecisions: PropTypes.number,
  onDecisionClick: PropTypes.func,
  className: PropTypes.string,
};

export default AdmissionDecisionsWidget;
