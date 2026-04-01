/**
 * Runtime Correlation Widget
 *
 * Displays CloudTrail and GuardDuty events correlated to source code
 * locations with confidence scores.
 *
 * Per ADR-077: Widget ID 'runtime-correlation', Category: SECURITY
 *
 * @module components/dashboard/widgets/RuntimeCorrelationWidget
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  LinkIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  CloudIcon,
  ShieldExclamationIcon,
  CodeBracketIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/solid';
import { getRuntimeCorrelations } from '../../../services/runtimeSecurityApi';
import { DataFreshnessIndicator } from '../../palantir/DataFreshnessIndicator';

// Source configurations
const SOURCE_CONFIG = {
  cloudtrail: {
    icon: CloudIcon,
    color: 'text-blue-500',
    bgColor: 'bg-blue-100 dark:bg-blue-900/30',
    label: 'CloudTrail',
  },
  guardduty: {
    icon: ShieldExclamationIcon,
    color: 'text-orange-500',
    bgColor: 'bg-orange-100 dark:bg-orange-900/30',
    label: 'GuardDuty',
  },
};

/**
 * Loading skeleton
 */
function RuntimeCorrelationWidgetSkeleton() {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 animate-pulse">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-surface-200 dark:bg-surface-700" />
          <div className="w-36 h-5 rounded bg-surface-200 dark:bg-surface-700" />
        </div>
      </div>
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="p-3 rounded-lg bg-surface-100 dark:bg-surface-700">
            <div className="w-full h-4 rounded bg-surface-200 dark:bg-surface-600 mb-2" />
            <div className="w-3/4 h-3 rounded bg-surface-200 dark:bg-surface-600" />
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Error state
 */
function RuntimeCorrelationWidgetError({ onRetry }) {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-red-200 dark:border-red-800 p-4 flex flex-col items-center justify-center min-h-[200px]">
      <ExclamationTriangleIcon className="w-8 h-8 text-red-500 mb-2" />
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
        Failed to load correlations
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
 * Confidence score indicator
 */
function ConfidenceIndicator({ score }) {
  const color = score >= 90 ? 'bg-green-500' : score >= 70 ? 'bg-amber-500' : 'bg-red-500';
  const textColor = score >= 90 ? 'text-green-600' : score >= 70 ? 'text-amber-600' : 'text-red-600';

  return (
    <div className="flex items-center gap-1.5">
      <div className="w-12 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full ${color} transition-all`}
          style={{ width: `${score}%` }}
        />
      </div>
      <span className={`text-xs font-medium ${textColor}`}>
        {score}%
      </span>
    </div>
  );
}

/**
 * Correlation card
 */
function CorrelationCard({ correlation, onClick }) {
  const sourceConfig = SOURCE_CONFIG[correlation.source_event] || SOURCE_CONFIG.cloudtrail;
  const SourceIcon = sourceConfig.icon;

  return (
    <button
      onClick={() => onClick?.(correlation)}
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
          <div className={`p-1 rounded ${sourceConfig.bgColor}`}>
            <SourceIcon className={`w-3.5 h-3.5 ${sourceConfig.color}`} />
          </div>
          <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
            {correlation.event_name}
          </span>
        </div>
        <ChevronRightIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />
      </div>

      {/* Code Location */}
      <div className="flex items-start gap-2 mb-2 pl-6">
        <CodeBracketIcon className="w-3.5 h-3.5 text-gray-400 flex-shrink-0 mt-0.5" />
        <div className="min-w-0 flex-1">
          <p className="text-xs font-mono text-gray-700 dark:text-gray-300 truncate">
            {correlation.code_location?.file}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Line {correlation.code_location?.line}: {correlation.code_location?.function}
          </p>
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-2 border-t border-gray-200 dark:border-gray-700">
        <ConfidenceIndicator score={correlation.confidence_score} />
        <span className="text-xs text-gray-500 dark:text-gray-400">
          {formatRelativeTime(correlation.correlated_at)}
        </span>
      </div>
    </button>
  );
}

/**
 * RuntimeCorrelationWidget component
 */
export function RuntimeCorrelationWidget({
  refreshInterval = 60000,
  maxCorrelations = 4,
  onCorrelationClick = null,
  className = '',
}) {
  const [correlations, setCorrelations] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const mountedRef = useRef(true);

  const fetchCorrelations = useCallback(async () => {
    try {
      const data = await getRuntimeCorrelations();

      if (mountedRef.current) {
        setCorrelations(data);
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
    fetchCorrelations();

    const interval = setInterval(fetchCorrelations, refreshInterval);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchCorrelations, refreshInterval]);

  if (isLoading) {
    return <RuntimeCorrelationWidgetSkeleton />;
  }

  if (error) {
    return <RuntimeCorrelationWidgetError onRetry={fetchCorrelations} />;
  }

  // Sort by recency and limit
  const sortedCorrelations = correlations
    ? [...correlations]
        .sort((a, b) => new Date(b.correlated_at) - new Date(a.correlated_at))
        .slice(0, maxCorrelations)
    : [];

  const cloudtrailCount = correlations?.filter((c) => c.source_event === 'cloudtrail').length || 0;
  const guarddutyCount = correlations?.filter((c) => c.source_event === 'guardduty').length || 0;
  const avgConfidence = correlations?.length > 0
    ? Math.round(correlations.reduce((sum, c) => sum + c.confidence_score, 0) / correlations.length)
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
      aria-label="Runtime Correlation"
    >
      {/* Header */}
      <div className="p-4 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-purple-100 dark:bg-purple-900/30">
              <LinkIcon className="w-5 h-5 text-purple-600 dark:text-purple-400" />
            </div>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">
              Runtime Correlation
            </h3>
          </div>
          <div className="flex items-center gap-2">
            <DataFreshnessIndicator timestamp={lastUpdated} compact />
            <button
              onClick={fetchCorrelations}
              className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              aria-label="Refresh"
            >
              <ArrowPathIcon className="w-4 h-4 text-gray-500" />
            </button>
          </div>
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          Runtime events correlated to source code
        </p>
      </div>

      {/* Summary */}
      <div className="px-4 py-3 bg-gray-50 dark:bg-gray-800/50 grid grid-cols-3 gap-4 border-b border-gray-200 dark:border-gray-700">
        <div className="text-center">
          <p className="text-xs text-gray-500">CloudTrail</p>
          <p className="text-lg font-semibold text-blue-600">
            {cloudtrailCount}
          </p>
        </div>
        <div className="text-center">
          <p className="text-xs text-gray-500">GuardDuty</p>
          <p className="text-lg font-semibold text-orange-600">
            {guarddutyCount}
          </p>
        </div>
        <div className="text-center">
          <p className="text-xs text-gray-500">Avg Confidence</p>
          <p className={`text-lg font-semibold ${avgConfidence >= 80 ? 'text-green-600' : 'text-amber-600'}`}>
            {avgConfidence}%
          </p>
        </div>
      </div>

      {/* Correlations List */}
      <div className="p-4">
        {sortedCorrelations.length > 0 ? (
          <div className="space-y-3">
            {sortedCorrelations.map((correlation) => (
              <CorrelationCard
                key={correlation.correlation_id}
                correlation={correlation}
                onClick={onCorrelationClick}
              />
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500 dark:text-gray-400">
            <LinkIcon className="w-12 h-12 mx-auto mb-2 opacity-30" />
            <p className="text-sm font-medium">No correlations found</p>
            <p className="text-xs mt-1">Events will appear when correlated</p>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>{correlations?.length || 0} total correlations</span>
          <span>
            Files: {[...new Set(correlations?.map((c) => c.code_location?.file) || [])].length}
          </span>
        </div>
      </div>
    </div>
  );
}

RuntimeCorrelationWidget.propTypes = {
  refreshInterval: PropTypes.number,
  maxCorrelations: PropTypes.number,
  onCorrelationClick: PropTypes.func,
  className: PropTypes.string,
};

export default RuntimeCorrelationWidget;
