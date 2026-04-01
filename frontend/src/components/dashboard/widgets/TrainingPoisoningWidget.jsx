/**
 * Training Poisoning Widget
 *
 * Displays training data poisoning alerts and quarantine status.
 *
 * Per ADR-079: Widget ID 'ai-security-training-poisoning', Category: SECURITY
 *
 * @module components/dashboard/widgets/TrainingPoisoningWidget
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  BeakerIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  ShieldCheckIcon,
  ArchiveBoxXMarkIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/solid';
import { getTrainingPoisoningAlerts } from '../../../services/aiSecurityApi';
import { DataFreshnessIndicator } from '../../palantir/DataFreshnessIndicator';

// Severity configurations
const SEVERITY_CONFIG = {
  critical: {
    bgColor: 'bg-red-100 dark:bg-red-900/30',
    borderColor: 'border-red-200 dark:border-red-800',
    textColor: 'text-red-700 dark:text-red-300',
    badge: 'bg-red-500 text-white',
  },
  high: {
    bgColor: 'bg-orange-100 dark:bg-orange-900/30',
    borderColor: 'border-orange-200 dark:border-orange-800',
    textColor: 'text-orange-700 dark:text-orange-300',
    badge: 'bg-orange-500 text-white',
  },
  medium: {
    bgColor: 'bg-amber-100 dark:bg-amber-900/30',
    borderColor: 'border-amber-200 dark:border-amber-800',
    textColor: 'text-amber-700 dark:text-amber-300',
    badge: 'bg-amber-500 text-white',
  },
  low: {
    bgColor: 'bg-green-100 dark:bg-green-900/30',
    borderColor: 'border-green-200 dark:border-green-800',
    textColor: 'text-green-700 dark:text-green-300',
    badge: 'bg-green-500 text-white',
  },
};

// Poisoning type labels
const POISONING_TYPE_LABELS = {
  backdoor_injection: 'Backdoor Injection',
  label_flipping: 'Label Flipping',
  data_drift: 'Data Drift',
  model_inversion: 'Model Inversion',
  membership_inference: 'Membership Inference',
};

/**
 * Loading skeleton
 */
function TrainingPoisoningWidgetSkeleton() {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 animate-pulse">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 rounded-lg bg-surface-200 dark:bg-surface-700" />
        <div className="w-36 h-5 rounded bg-surface-200 dark:bg-surface-700" />
      </div>
      <div className="grid grid-cols-3 gap-3 mb-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-16 rounded-lg bg-surface-100 dark:bg-surface-700" />
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
function TrainingPoisoningWidgetError({ onRetry }) {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-red-200 dark:border-red-800 p-4 flex flex-col items-center justify-center min-h-[200px]">
      <ExclamationTriangleIcon className="w-8 h-8 text-red-500 mb-2" />
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
        Failed to load poisoning alerts
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
 * Alert card
 */
function AlertCard({ alert, onClick }) {
  const config = SEVERITY_CONFIG[alert.severity] || SEVERITY_CONFIG.medium;
  const typeLabel = POISONING_TYPE_LABELS[alert.poisoning_type] || alert.poisoning_type;

  return (
    <button
      onClick={() => onClick?.(alert)}
      className={`
        w-full text-left p-3 rounded-lg border
        ${config.bgColor} ${config.borderColor}
        hover:shadow-sm transition-all duration-200
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1
      `}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`px-2 py-0.5 text-xs font-medium rounded ${config.badge}`}>
            {alert.severity.toUpperCase()}
          </span>
          <span className="text-xs px-1.5 py-0.5 rounded bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300">
            {typeLabel}
          </span>
          {alert.quarantined && (
            <span className="flex items-center gap-1 text-xs text-amber-600">
              <ArchiveBoxXMarkIcon className="w-3 h-3" />
              Quarantined
            </span>
          )}
        </div>
        <ChevronRightIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />
      </div>

      <div className="mb-2">
        <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
          {alert.dataset_id}
        </p>
        <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5 line-clamp-1">
          {alert.description}
        </p>
      </div>

      <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
        <span>
          {alert.affected_samples.toLocaleString()} samples | {alert.confidence_score}% confidence
        </span>
        <span>{formatRelativeTime(alert.detected_at)}</span>
      </div>
    </button>
  );
}

/**
 * TrainingPoisoningWidget component
 */
export function TrainingPoisoningWidget({
  refreshInterval = 60000,
  maxAlerts = 3,
  onAlertClick = null,
  className = '',
}) {
  const [poisoningData, setPoisoningData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const mountedRef = useRef(true);

  const fetchAlerts = useCallback(async () => {
    try {
      const data = await getTrainingPoisoningAlerts();

      if (mountedRef.current) {
        setPoisoningData(data);
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
    fetchAlerts();

    const interval = setInterval(fetchAlerts, refreshInterval);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchAlerts, refreshInterval]);

  if (isLoading) {
    return <TrainingPoisoningWidgetSkeleton />;
  }

  if (error) {
    return <TrainingPoisoningWidgetError onRetry={fetchAlerts} />;
  }

  // Sort by severity and recency
  const severityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
  const sortedAlerts = poisoningData?.alerts
    ? [...poisoningData.alerts]
        .sort((a, b) => {
          const severityDiff = severityOrder[a.severity] - severityOrder[b.severity];
          if (severityDiff !== 0) return severityDiff;
          return new Date(b.detected_at) - new Date(a.detected_at);
        })
        .slice(0, maxAlerts)
    : [];

  const cleanRate = poisoningData?.total_datasets_monitored > 0
    ? ((poisoningData.clean_datasets / poisoningData.total_datasets_monitored) * 100).toFixed(0)
    : 100;

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        overflow-hidden
        ${className}
      `}
      role="region"
      aria-label="Training Data Poisoning"
    >
      {/* Header */}
      <div className="p-4 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-rose-100 dark:bg-rose-900/30">
              <BeakerIcon className="w-5 h-5 text-rose-600 dark:text-rose-400" />
            </div>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">
              Training Poisoning
            </h3>
          </div>
          <div className="flex items-center gap-2">
            {poisoningData?.quarantined_datasets > 0 && (
              <span className="px-2 py-0.5 text-xs font-medium bg-amber-100 text-amber-700 rounded-full">
                {poisoningData.quarantined_datasets} quarantined
              </span>
            )}
            <button
              onClick={fetchAlerts}
              className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              aria-label="Refresh"
            >
              <ArrowPathIcon className="w-4 h-4 text-gray-500" />
            </button>
          </div>
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          Training data poisoning detection alerts
        </p>
      </div>

      {/* Stats */}
      <div className="p-4 grid grid-cols-3 gap-3 border-b border-gray-200 dark:border-gray-700">
        <div className="text-center p-2 rounded-lg bg-green-50 dark:bg-green-900/20">
          <p className="text-xs text-gray-500">Clean</p>
          <p className="text-xl font-bold text-green-600">
            {poisoningData?.clean_datasets || 0}
          </p>
        </div>
        <div className="text-center p-2 rounded-lg bg-amber-50 dark:bg-amber-900/20">
          <p className="text-xs text-gray-500">Quarantined</p>
          <p className="text-xl font-bold text-amber-600">
            {poisoningData?.quarantined_datasets || 0}
          </p>
        </div>
        <div className="text-center p-2 rounded-lg bg-blue-50 dark:bg-blue-900/20">
          <p className="text-xs text-gray-500">Investigating</p>
          <p className="text-xl font-bold text-blue-600">
            {poisoningData?.under_investigation || 0}
          </p>
        </div>
      </div>

      {/* Alerts List */}
      <div className="p-4">
        <h4 className="text-xs font-medium text-gray-500 uppercase mb-3">
          Recent Alerts
        </h4>
        {sortedAlerts.length > 0 ? (
          <div className="space-y-2">
            {sortedAlerts.map((alert) => (
              <AlertCard
                key={alert.alert_id}
                alert={alert}
                onClick={onAlertClick}
              />
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500 dark:text-gray-400">
            <ShieldCheckIcon className="w-12 h-12 mx-auto mb-2 text-green-500 opacity-50" />
            <p className="text-sm font-medium">No poisoning detected</p>
            <p className="text-xs mt-1">Training data is clean</p>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>
            {poisoningData?.total_datasets_monitored || 0} datasets monitored ({cleanRate}% clean)
          </span>
          <DataFreshnessIndicator timestamp={lastUpdated} compact />
        </div>
      </div>
    </div>
  );
}

TrainingPoisoningWidget.propTypes = {
  refreshInterval: PropTypes.number,
  maxAlerts: PropTypes.number,
  onAlertClick: PropTypes.func,
  className: PropTypes.string,
};

export default TrainingPoisoningWidget;
