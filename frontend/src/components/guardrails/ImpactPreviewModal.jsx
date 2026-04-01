/**
 * ImpactPreviewModal Component (ADR-069)
 *
 * Shows projected impact of guardrail configuration changes before applying.
 * Displays metric comparisons and warnings about potential effects.
 *
 * @module components/guardrails/ImpactPreviewModal
 */

import React from 'react';
import PropTypes from 'prop-types';
import {
  XMarkIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';

/**
 * ChangeIndicator - Shows percentage change with direction
 */
function ChangeIndicator({ before, after, inverted = false, format = 'percent' }) {
  if (before === 0 && after === 0) {
    return <span className="text-surface-500">No change</span>;
  }

  const change = before === 0 ? 100 : ((after - before) / before) * 100;
  const isPositive = change > 0;
  const isGood = inverted ? !isPositive : isPositive;

  const formatChange = () => {
    if (format === 'percent') {
      return `${isPositive ? '+' : ''}${change.toFixed(0)}%`;
    }
    const diff = after - before;
    return `${diff > 0 ? '+' : ''}${diff.toFixed(1)}`;
  };

  return (
    <div
      className={`flex items-center gap-1 ${
        isGood
          ? 'text-olive-600 dark:text-olive-400'
          : 'text-critical-600 dark:text-critical-400'
      }`}
    >
      {isPositive ? (
        <ArrowTrendingUpIcon className="w-4 h-4" />
      ) : (
        <ArrowTrendingDownIcon className="w-4 h-4" />
      )}
      <span className="font-medium">{formatChange()}</span>
    </div>
  );
}

ChangeIndicator.propTypes = {
  before: PropTypes.number.isRequired,
  after: PropTypes.number.isRequired,
  inverted: PropTypes.bool,
  format: PropTypes.oneOf(['percent', 'absolute']),
};

/**
 * MetricComparisonRow - Single row in the comparison table
 */
function MetricComparisonRow({ metric }) {
  return (
    <tr className="border-b border-surface-200 dark:border-surface-700 last:border-0">
      <td className="py-3 pr-4">
        <div className="font-medium text-surface-900 dark:text-surface-100">
          {metric.label}
        </div>
        {metric.description && (
          <div className="text-xs text-surface-500 dark:text-surface-400 mt-0.5">
            {metric.description}
          </div>
        )}
      </td>
      <td className="py-3 px-4 text-right text-surface-600 dark:text-surface-400">
        {metric.format === 'time'
          ? `${metric.before}s`
          : metric.before.toLocaleString()}
      </td>
      <td className="py-3 px-4 text-right font-medium text-surface-900 dark:text-surface-100">
        {metric.format === 'time'
          ? `${metric.after}s`
          : metric.after.toLocaleString()}
      </td>
      <td className="py-3 pl-4 text-right">
        <ChangeIndicator
          before={metric.before}
          after={metric.after}
          inverted={metric.inverted}
          format={metric.format === 'time' ? 'percent' : 'percent'}
        />
      </td>
    </tr>
  );
}

MetricComparisonRow.propTypes = {
  metric: PropTypes.shape({
    label: PropTypes.string.isRequired,
    description: PropTypes.string,
    before: PropTypes.number.isRequired,
    after: PropTypes.number.isRequired,
    inverted: PropTypes.bool,
    format: PropTypes.string,
  }).isRequired,
};

/**
 * WarningBanner - Warning message about the change
 */
function WarningBanner({ severity, title, message }) {
  const severityConfig = {
    info: {
      bg: 'bg-aura-50 dark:bg-aura-900/20',
      border: 'border-aura-200 dark:border-aura-800',
      icon: 'text-aura-500',
      title: 'text-aura-800 dark:text-aura-300',
      Icon: InformationCircleIcon,
    },
    warning: {
      bg: 'bg-warning-50 dark:bg-warning-900/20',
      border: 'border-warning-200 dark:border-warning-800',
      icon: 'text-warning-500',
      title: 'text-warning-800 dark:text-warning-300',
      Icon: ExclamationTriangleIcon,
    },
    critical: {
      bg: 'bg-critical-50 dark:bg-critical-900/20',
      border: 'border-critical-200 dark:border-critical-800',
      icon: 'text-critical-500',
      title: 'text-critical-800 dark:text-critical-300',
      Icon: ExclamationTriangleIcon,
    },
  };

  const config = severityConfig[severity] || severityConfig.info;
  const Icon = config.Icon;

  return (
    <div className={`rounded-lg border p-4 ${config.bg} ${config.border}`}>
      <div className="flex gap-3">
        <Icon className={`w-5 h-5 flex-shrink-0 mt-0.5 ${config.icon}`} />
        <div>
          <h4 className={`font-medium ${config.title}`}>{title}</h4>
          <p className="text-sm text-surface-600 dark:text-surface-400 mt-1">
            {message}
          </p>
        </div>
      </div>
    </div>
  );
}

WarningBanner.propTypes = {
  severity: PropTypes.oneOf(['info', 'warning', 'critical']).isRequired,
  title: PropTypes.string.isRequired,
  message: PropTypes.string.isRequired,
};

/**
 * ImpactPreviewModal - Main modal component
 *
 * @param {Object} props
 * @param {boolean} props.isOpen - Whether modal is visible
 * @param {Function} props.onClose - Callback to close modal
 * @param {Function} props.onConfirm - Callback when changes confirmed
 * @param {Object} props.changesSummary - Description of what's changing
 * @param {Array} props.projectedMetrics - Metrics comparison data
 * @param {Array} [props.warnings=[]] - Warning messages to display
 * @param {boolean} [props.isLoading=false] - Loading state for metrics
 * @param {string} [props.className] - Additional CSS classes
 */
function ImpactPreviewModal({
  isOpen,
  onClose,
  onConfirm,
  changesSummary,
  projectedMetrics,
  warnings = [],
  isLoading = false,
  className = '',
}) {
  if (!isOpen) return null;

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      onClose();
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4
                 bg-black/50 backdrop-blur-sm"
      onClick={handleBackdropClick}
      onKeyDown={handleKeyDown}
      role="dialog"
      aria-modal="true"
      aria-labelledby="impact-preview-title"
    >
      <div
        className={`
          w-full max-w-2xl max-h-[90vh] overflow-hidden
          bg-white dark:bg-surface-800
          rounded-2xl shadow-2xl
          flex flex-col
          ${className}
        `}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-surface-200 dark:border-surface-700">
          <h2
            id="impact-preview-title"
            className="text-xl font-semibold text-surface-900 dark:text-surface-100"
          >
            Review Changes
          </h2>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-surface-500 hover:text-surface-700
                       dark:hover:text-surface-300 hover:bg-surface-100
                       dark:hover:bg-surface-700 transition-colors"
            aria-label="Close modal"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
          {/* Changes summary */}
          <div>
            <h3 className="text-sm font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wide mb-2">
              You&apos;re changing
            </h3>
            <p className="text-surface-900 dark:text-surface-100">
              {changesSummary.description}
            </p>
            {changesSummary.details && (
              <p className="text-sm text-surface-600 dark:text-surface-400 mt-1">
                {changesSummary.details}
              </p>
            )}
          </div>

          {/* Projected impact table */}
          <div className="bg-surface-50 dark:bg-surface-900 rounded-xl p-4">
            <h3 className="text-sm font-medium text-surface-700 dark:text-surface-300 mb-3">
              Projected Impact{' '}
              <span className="font-normal text-surface-500">(based on last 30 days)</span>
            </h3>

            {isLoading ? (
              <div className="animate-pulse space-y-3">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="h-10 bg-surface-200 dark:bg-surface-700 rounded" />
                ))}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wide">
                      <th className="text-left pb-2">Metric</th>
                      <th className="text-right pb-2 px-4">Before</th>
                      <th className="text-right pb-2 px-4">After</th>
                      <th className="text-right pb-2 pl-4">Change</th>
                    </tr>
                  </thead>
                  <tbody>
                    {projectedMetrics.map((metric, index) => (
                      <MetricComparisonRow key={index} metric={metric} />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Warnings */}
          {warnings.length > 0 && (
            <div className="space-y-3">
              {warnings.map((warning, index) => (
                <WarningBanner
                  key={index}
                  severity={warning.severity}
                  title={warning.title}
                  message={warning.message}
                />
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          className="flex items-center justify-end gap-3 px-6 py-4
                        border-t border-surface-200 dark:border-surface-700
                        bg-surface-50 dark:bg-surface-900/50"
        >
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium
                       text-surface-700 dark:text-surface-300
                       hover:bg-surface-200 dark:hover:bg-surface-700
                       rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isLoading}
            className="px-4 py-2 text-sm font-medium
                       bg-aura-600 text-white
                       hover:bg-aura-700
                       disabled:opacity-50 disabled:cursor-not-allowed
                       rounded-lg transition-colors"
          >
            Apply Changes
          </button>
        </div>
      </div>
    </div>
  );
}

ImpactPreviewModal.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onConfirm: PropTypes.func.isRequired,
  changesSummary: PropTypes.shape({
    description: PropTypes.string.isRequired,
    details: PropTypes.string,
  }).isRequired,
  projectedMetrics: PropTypes.arrayOf(
    PropTypes.shape({
      label: PropTypes.string.isRequired,
      description: PropTypes.string,
      before: PropTypes.number.isRequired,
      after: PropTypes.number.isRequired,
      inverted: PropTypes.bool,
      format: PropTypes.string,
    })
  ).isRequired,
  warnings: PropTypes.arrayOf(
    PropTypes.shape({
      severity: PropTypes.oneOf(['info', 'warning', 'critical']).isRequired,
      title: PropTypes.string.isRequired,
      message: PropTypes.string.isRequired,
    })
  ),
  isLoading: PropTypes.bool,
  className: PropTypes.string,
};

export default ImpactPreviewModal;
