/**
 * GuardDuty Findings Widget
 *
 * Displays AWS GuardDuty security findings with code links
 * and severity distribution.
 *
 * Per ADR-077: Widget ID 'runtime-guardduty-findings', Category: SECURITY
 *
 * @module components/dashboard/widgets/GuardDutyFindingsWidget
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  ShieldExclamationIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  CodeBracketIcon,
  ChevronRightIcon,
  LinkIcon,
} from '@heroicons/react/24/solid';
import { getGuardDutyFindings, getGuardDutyStats } from '../../../services/runtimeSecurityApi';
import { DataFreshnessIndicator } from '../../palantir/DataFreshnessIndicator';

// Severity configurations
const SEVERITY_CONFIG = {
  Critical: {
    bgColor: 'bg-red-100 dark:bg-red-900/30',
    borderColor: 'border-red-200 dark:border-red-800',
    textColor: 'text-red-700 dark:text-red-300',
    badge: 'bg-red-500 text-white',
    dotColor: 'bg-red-500',
  },
  High: {
    bgColor: 'bg-orange-100 dark:bg-orange-900/30',
    borderColor: 'border-orange-200 dark:border-orange-800',
    textColor: 'text-orange-700 dark:text-orange-300',
    badge: 'bg-orange-500 text-white',
    dotColor: 'bg-orange-500',
  },
  Medium: {
    bgColor: 'bg-amber-100 dark:bg-amber-900/30',
    borderColor: 'border-amber-200 dark:border-amber-800',
    textColor: 'text-amber-700 dark:text-amber-300',
    badge: 'bg-amber-500 text-white',
    dotColor: 'bg-amber-500',
  },
  Low: {
    bgColor: 'bg-green-100 dark:bg-green-900/30',
    borderColor: 'border-green-200 dark:border-green-800',
    textColor: 'text-green-700 dark:text-green-300',
    badge: 'bg-green-500 text-white',
    dotColor: 'bg-green-500',
  },
};

/**
 * Loading skeleton
 */
function GuardDutyFindingsWidgetSkeleton() {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 animate-pulse">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-surface-200 dark:bg-surface-700" />
          <div className="w-36 h-5 rounded bg-surface-200 dark:bg-surface-700" />
        </div>
      </div>
      <div className="grid grid-cols-4 gap-2 mb-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-12 rounded bg-surface-100 dark:bg-surface-700" />
        ))}
      </div>
      <div className="space-y-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-16 rounded bg-surface-100 dark:bg-surface-700" />
        ))}
      </div>
    </div>
  );
}

/**
 * Error state
 */
function GuardDutyFindingsWidgetError({ onRetry }) {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-red-200 dark:border-red-800 p-4 flex flex-col items-center justify-center min-h-[200px]">
      <ExclamationTriangleIcon className="w-8 h-8 text-red-500 mb-2" />
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
        Failed to load GuardDuty findings
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
 * Severity count badge
 */
function SeverityBadge({ label, count, color }) {
  return (
    <div className="text-center p-2 rounded-lg bg-gray-50 dark:bg-gray-800/50">
      <div className="flex items-center justify-center gap-1">
        <span className={`w-2 h-2 rounded-full ${color}`} />
        <span className="text-xs text-gray-500">{label}</span>
      </div>
      <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">
        {count}
      </p>
    </div>
  );
}

/**
 * Finding card
 */
function FindingCard({ finding, onClick }) {
  const config = SEVERITY_CONFIG[finding.severity] || SEVERITY_CONFIG.Medium;
  const hasCodeLink = !!finding.code_link;

  return (
    <button
      onClick={() => onClick?.(finding)}
      className={`
        w-full text-left p-3 rounded-lg border
        ${config.bgColor} ${config.borderColor}
        hover:shadow-sm transition-all duration-200
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1
      `}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`px-2 py-0.5 text-xs font-medium rounded ${config.badge}`}>
            {finding.severity}
          </span>
          {hasCodeLink && (
            <span className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400">
              <LinkIcon className="w-3 h-3" />
              Code linked
            </span>
          )}
        </div>
        <ChevronRightIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />
      </div>

      {/* Title */}
      <p className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-1">
        {finding.title}
      </p>

      {/* Type */}
      <p className="text-xs font-mono text-gray-600 dark:text-gray-400 mb-2 truncate">
        {finding.type}
      </p>

      {/* Code Link if present */}
      {hasCodeLink && (
        <div className="flex items-start gap-2 p-2 rounded bg-white/50 dark:bg-black/20 mb-2">
          <CodeBracketIcon className="w-3.5 h-3.5 text-gray-500 flex-shrink-0 mt-0.5" />
          <div className="min-w-0 flex-1">
            <p className="text-xs font-mono text-gray-700 dark:text-gray-300 truncate">
              {finding.code_link.file}:{finding.code_link.line}
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400 line-clamp-1">
              {finding.code_link.context}
            </p>
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
        <span>{finding.resource_type}: {finding.resource_id}</span>
        <span>{formatRelativeTime(finding.detected_at)}</span>
      </div>
    </button>
  );
}

/**
 * GuardDutyFindingsWidget component
 */
export function GuardDutyFindingsWidget({
  refreshInterval = 60000,
  maxFindings = 3,
  onFindingClick = null,
  className = '',
}) {
  const [findings, setFindings] = useState(null);
  const [stats, setStats] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    try {
      const [findingsData, statsData] = await Promise.all([
        getGuardDutyFindings({ archived: false }),
        getGuardDutyStats(),
      ]);

      if (mountedRef.current) {
        setFindings(findingsData);
        setStats(statsData);
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
    fetchData();

    const interval = setInterval(fetchData, refreshInterval);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchData, refreshInterval]);

  if (isLoading) {
    return <GuardDutyFindingsWidgetSkeleton />;
  }

  if (error) {
    return <GuardDutyFindingsWidgetError onRetry={fetchData} />;
  }

  // Sort by severity and recency
  const severityOrder = { Critical: 0, High: 1, Medium: 2, Low: 3 };
  const sortedFindings = findings
    ? [...findings]
        .sort((a, b) => {
          const severityDiff = severityOrder[a.severity] - severityOrder[b.severity];
          if (severityDiff !== 0) return severityDiff;
          return new Date(b.detected_at) - new Date(a.detected_at);
        })
        .slice(0, maxFindings)
    : [];

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        overflow-hidden
        ${className}
      `}
      role="region"
      aria-label="GuardDuty Findings"
    >
      {/* Header */}
      <div className="p-4 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-orange-100 dark:bg-orange-900/30">
              <ShieldExclamationIcon className="w-5 h-5 text-orange-600 dark:text-orange-400" />
            </div>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">
              GuardDuty Findings
            </h3>
          </div>
          <div className="flex items-center gap-2">
            <DataFreshnessIndicator timestamp={lastUpdated} compact />
            <button
              onClick={fetchData}
              className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              aria-label="Refresh"
            >
              <ArrowPathIcon className="w-4 h-4 text-gray-500" />
            </button>
          </div>
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          AWS security findings with code correlation
        </p>
      </div>

      {/* Severity Summary */}
      <div className="p-4 grid grid-cols-4 gap-2 border-b border-gray-200 dark:border-gray-700">
        <SeverityBadge
          label="Critical"
          count={stats?.critical_count || 0}
          color="bg-red-500"
        />
        <SeverityBadge
          label="High"
          count={stats?.high_count || 0}
          color="bg-orange-500"
        />
        <SeverityBadge
          label="Medium"
          count={stats?.medium_count || 0}
          color="bg-amber-500"
        />
        <SeverityBadge
          label="Low"
          count={stats?.low_count || 0}
          color="bg-green-500"
        />
      </div>

      {/* Findings List */}
      <div className="p-4">
        {sortedFindings.length > 0 ? (
          <div className="space-y-3">
            {sortedFindings.map((finding) => (
              <FindingCard
                key={finding.finding_id}
                finding={finding}
                onClick={onFindingClick}
              />
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500 dark:text-gray-400">
            <ShieldExclamationIcon className="w-12 h-12 mx-auto mb-2 opacity-30" />
            <p className="text-sm font-medium">No active findings</p>
            <p className="text-xs mt-1">Environment is secure</p>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>{stats?.total_findings || 0} total findings</span>
          <span>
            Code linked: {stats?.code_linked_count || 0} ({stats?.correlation_rate || 0}%)
          </span>
        </div>
      </div>
    </div>
  );
}

GuardDutyFindingsWidget.propTypes = {
  refreshInterval: PropTypes.number,
  maxFindings: PropTypes.number,
  onFindingClick: PropTypes.func,
  className: PropTypes.string,
};

export default GuardDutyFindingsWidget;
