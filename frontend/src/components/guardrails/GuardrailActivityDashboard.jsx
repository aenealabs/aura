/**
 * GuardrailActivityDashboard Component (ADR-069)
 *
 * Read-only dashboard showing guardrail activity metrics.
 * Displays threat detection, context trust, agent operations, and explanation stats.
 *
 * @module components/guardrails/GuardrailActivityDashboard
 */

import React from 'react';
import PropTypes from 'prop-types';
import {
  ShieldCheckIcon,
  LockClosedIcon,
  ServerStackIcon,
  ChatBubbleBottomCenterTextIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';

/**
 * Color mappings for metric cards
 */
const COLOR_MAP = {
  aura: {
    icon: 'bg-aura-100 text-aura-600 dark:bg-aura-900/30 dark:text-aura-400',
  },
  olive: {
    icon: 'bg-olive-100 text-olive-600 dark:bg-olive-900/30 dark:text-olive-400',
  },
  critical: {
    icon: 'bg-critical-100 text-critical-600 dark:bg-critical-900/30 dark:text-critical-400',
  },
  warning: {
    icon: 'bg-warning-100 text-warning-600 dark:bg-warning-900/30 dark:text-warning-400',
  },
};

/**
 * MetricCard - Individual metric display card
 */
function MetricCard({ title, icon: Icon, iconColor, value, breakdown, isLoading }) {
  const colors = COLOR_MAP[iconColor] || COLOR_MAP.aura;

  return (
    <div
      className="bg-white dark:bg-surface-800 rounded-xl
                    border border-surface-200/50 dark:border-surface-700/30
                    p-4 shadow-sm"
    >
      {/* Header */}
      <div className="flex items-center gap-3 mb-3">
        <div className={`p-2 rounded-lg ${colors.icon}`}>
          <Icon className="w-5 h-5" />
        </div>
        <h4 className="font-medium text-surface-900 dark:text-surface-100">{title}</h4>
      </div>

      {/* Value */}
      {isLoading ? (
        <div className="animate-pulse">
          <div className="h-8 bg-surface-200 dark:bg-surface-700 rounded w-24 mb-3" />
          <div className="space-y-2">
            <div className="h-4 bg-surface-200 dark:bg-surface-700 rounded w-full" />
            <div className="h-4 bg-surface-200 dark:bg-surface-700 rounded w-3/4" />
          </div>
        </div>
      ) : (
        <>
          <p className="text-2xl font-bold text-surface-900 dark:text-surface-100 mb-3">
            {typeof value === 'number' ? value.toLocaleString() : value}
          </p>

          {/* Breakdown */}
          {breakdown && breakdown.length > 0 && (
            <div className="space-y-1.5">
              {breakdown.map((item, index) => (
                <div key={index} className="flex justify-between text-sm">
                  <span className="text-surface-500 dark:text-surface-400">{item.label}</span>
                  <span className="font-medium text-surface-700 dark:text-surface-300">
                    {typeof item.value === 'number' ? item.value.toLocaleString() : item.value}
                  </span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

MetricCard.propTypes = {
  title: PropTypes.string.isRequired,
  icon: PropTypes.elementType.isRequired,
  iconColor: PropTypes.oneOf(['aura', 'olive', 'critical', 'warning']),
  value: PropTypes.oneOfType([PropTypes.number, PropTypes.string]).isRequired,
  breakdown: PropTypes.arrayOf(
    PropTypes.shape({
      label: PropTypes.string.isRequired,
      value: PropTypes.oneOfType([PropTypes.number, PropTypes.string]).isRequired,
    })
  ),
  isLoading: PropTypes.bool,
};

/**
 * ProgressBar - Simple progress bar for percentages
 */
function ProgressBar({ value, label, color = 'aura' }) {
  const colorClasses = {
    aura: 'bg-aura-500',
    olive: 'bg-olive-500',
    warning: 'bg-warning-500',
    critical: 'bg-critical-500',
  };

  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-surface-600 dark:text-surface-400">{label}</span>
        <span className="font-medium text-surface-900 dark:text-surface-100">{value}%</span>
      </div>
      <div className="h-2 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${colorClasses[color]}`}
          style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
        />
      </div>
    </div>
  );
}

ProgressBar.propTypes = {
  value: PropTypes.number.isRequired,
  label: PropTypes.string.isRequired,
  color: PropTypes.oneOf(['aura', 'olive', 'warning', 'critical']),
};

/**
 * GuardrailActivityDashboard - Main component
 *
 * @param {Object} props
 * @param {Object} props.metrics - Activity metrics data
 * @param {string} [props.timeRange='7d'] - Time range for metrics
 * @param {Function} [props.onTimeRangeChange] - Callback when time range changes
 * @param {Function} [props.onRefresh] - Callback to refresh data
 * @param {boolean} [props.isLoading=false] - Loading state
 * @param {string} [props.className] - Additional CSS classes
 */
function GuardrailActivityDashboard({
  metrics,
  timeRange = '7d',
  onTimeRangeChange,
  onRefresh,
  isLoading = false,
  className = '',
}) {
  const timeRangeOptions = [
    { value: '24h', label: 'Last 24 Hours' },
    { value: '7d', label: 'Last 7 Days' },
    { value: '30d', label: 'Last 30 Days' },
    { value: '90d', label: 'Last 90 Days' },
  ];

  // Default metrics structure
  const defaultMetrics = {
    threatDetection: {
      blocked: 0,
      breakdown: [],
    },
    contextTrust: {
      verified: 0,
      breakdown: [],
    },
    agentOperations: {
      total: 0,
      breakdown: [],
    },
    explanations: {
      averageConfidence: 0,
      alternativesDisclosed: 0,
      consistency: 0,
    },
  };

  const data = { ...defaultMetrics, ...metrics };

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
          Guardrail Activity
        </h2>
        <div className="flex items-center gap-2">
          {/* Time range selector */}
          <select
            value={timeRange}
            onChange={(e) => onTimeRangeChange?.(e.target.value)}
            className="px-3 py-1.5 text-sm rounded-lg
                       border border-surface-300 dark:border-surface-600
                       bg-white dark:bg-surface-700
                       text-surface-900 dark:text-surface-100
                       focus:ring-2 focus:ring-aura-500"
          >
            {timeRangeOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>

          {/* Refresh button */}
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={isLoading}
              className="p-2 rounded-lg text-surface-500 hover:text-surface-700
                         dark:hover:text-surface-300 hover:bg-surface-100
                         dark:hover:bg-surface-800 transition-colors
                         disabled:opacity-50 disabled:cursor-not-allowed"
              aria-label="Refresh metrics"
            >
              <ArrowPathIcon className={`w-5 h-5 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          )}
        </div>
      </div>

      {/* Metric cards grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Threat Detection */}
        <MetricCard
          title="Threat Detection"
          icon={ShieldCheckIcon}
          iconColor="critical"
          value={`${data.threatDetection.blocked} Blocked`}
          breakdown={data.threatDetection.breakdown}
          isLoading={isLoading}
        />

        {/* Context Trust */}
        <MetricCard
          title="Context Trust"
          icon={LockClosedIcon}
          iconColor="olive"
          value={`${data.contextTrust.verified.toLocaleString()} Verified`}
          breakdown={data.contextTrust.breakdown}
          isLoading={isLoading}
        />

        {/* Agent Operations */}
        <MetricCard
          title="Agent Operations"
          icon={ServerStackIcon}
          iconColor="aura"
          value={`${data.agentOperations.total.toLocaleString()} Total`}
          breakdown={data.agentOperations.breakdown}
          isLoading={isLoading}
        />
      </div>

      {/* Explanations panel */}
      <div
        className="bg-white dark:bg-surface-800 rounded-xl
                      border border-surface-200/50 dark:border-surface-700/30
                      p-4 shadow-sm"
      >
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 rounded-lg bg-aura-100 text-aura-600 dark:bg-aura-900/30 dark:text-aura-400">
            <ChatBubbleBottomCenterTextIcon className="w-5 h-5" />
          </div>
          <h4 className="font-medium text-surface-900 dark:text-surface-100">
            Explanations Generated
          </h4>
        </div>

        {isLoading ? (
          <div className="animate-pulse space-y-4">
            <div className="h-6 bg-surface-200 dark:bg-surface-700 rounded w-full" />
            <div className="h-4 bg-surface-200 dark:bg-surface-700 rounded w-3/4" />
          </div>
        ) : (
          <div className="space-y-4">
            {/* Average Confidence */}
            <ProgressBar
              value={data.explanations.averageConfidence}
              label="Average Confidence"
              color={data.explanations.averageConfidence >= 80 ? 'olive' : 'warning'}
            />

            {/* Stats row */}
            <div className="flex items-center gap-6 text-sm">
              <div>
                <span className="text-surface-500 dark:text-surface-400">
                  Alternatives Disclosed:{' '}
                </span>
                <span className="font-medium text-surface-900 dark:text-surface-100">
                  {data.explanations.alternativesDisclosed}%
                </span>
              </div>
              <div>
                <span className="text-surface-500 dark:text-surface-400">Consistency: </span>
                <span className="font-medium text-surface-900 dark:text-surface-100">
                  {data.explanations.consistency}%
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

GuardrailActivityDashboard.propTypes = {
  metrics: PropTypes.shape({
    threatDetection: PropTypes.shape({
      blocked: PropTypes.number,
      breakdown: PropTypes.array,
    }),
    contextTrust: PropTypes.shape({
      verified: PropTypes.number,
      breakdown: PropTypes.array,
    }),
    agentOperations: PropTypes.shape({
      total: PropTypes.number,
      breakdown: PropTypes.array,
    }),
    explanations: PropTypes.shape({
      averageConfidence: PropTypes.number,
      alternativesDisclosed: PropTypes.number,
      consistency: PropTypes.number,
    }),
  }),
  timeRange: PropTypes.string,
  onTimeRangeChange: PropTypes.func,
  onRefresh: PropTypes.func,
  isLoading: PropTypes.bool,
  className: PropTypes.string,
};

export default GuardrailActivityDashboard;
