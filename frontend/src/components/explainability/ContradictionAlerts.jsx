/**
 * ContradictionAlerts Component (ADR-068)
 *
 * Displays alerts for detected contradictions between reasoning and actions.
 * Shows mismatches, severity levels, and recommended resolutions.
 *
 * @module components/explainability/ContradictionAlerts
 */

import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  ExclamationTriangleIcon,
  ExclamationCircleIcon,
  InformationCircleIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  LightBulbIcon,
  ArrowPathIcon,
  CheckIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';

/**
 * Severity configuration for contradiction types
 */
const SEVERITY_CONFIG = {
  critical: {
    icon: ExclamationCircleIcon,
    bgColor: 'bg-critical-50 dark:bg-critical-900/20',
    borderColor: 'border-critical-200 dark:border-critical-800',
    iconColor: 'text-critical-500',
    titleColor: 'text-critical-700 dark:text-critical-300',
    textColor: 'text-critical-600 dark:text-critical-400',
    label: 'Critical',
    labelBg: 'bg-critical-100 dark:bg-critical-800 text-critical-700 dark:text-critical-300',
  },
  high: {
    icon: ExclamationTriangleIcon,
    bgColor: 'bg-warning-50 dark:bg-warning-900/20',
    borderColor: 'border-warning-200 dark:border-warning-800',
    iconColor: 'text-warning-500',
    titleColor: 'text-warning-700 dark:text-warning-300',
    textColor: 'text-warning-600 dark:text-warning-400',
    label: 'High',
    labelBg: 'bg-warning-100 dark:bg-warning-800 text-warning-700 dark:text-warning-300',
  },
  medium: {
    icon: ExclamationTriangleIcon,
    bgColor: 'bg-aura-50 dark:bg-aura-900/20',
    borderColor: 'border-aura-200 dark:border-aura-800',
    iconColor: 'text-aura-500',
    titleColor: 'text-aura-700 dark:text-aura-300',
    textColor: 'text-aura-600 dark:text-aura-400',
    label: 'Medium',
    labelBg: 'bg-aura-100 dark:bg-aura-800 text-aura-700 dark:text-aura-300',
  },
  low: {
    icon: InformationCircleIcon,
    bgColor: 'bg-surface-50 dark:bg-surface-900',
    borderColor: 'border-surface-200 dark:border-surface-700',
    iconColor: 'text-surface-400',
    titleColor: 'text-surface-700 dark:text-surface-300',
    textColor: 'text-surface-600 dark:text-surface-400',
    label: 'Low',
    labelBg: 'bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-400',
  },
};

/**
 * ContradictionCard - Individual contradiction alert display
 */
function ContradictionCard({ contradiction, onResolve, onDismiss, isExpanded, onToggle }) {
  const {
    id,
    severity = 'medium',
    type,
    title,
    description,
    reasoning,
    action,
    recommendations = [],
    detectedAt,
    status = 'active',
  } = contradiction;

  const config = SEVERITY_CONFIG[severity] || SEVERITY_CONFIG.medium;
  const Icon = config.icon;

  const formatTime = (timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  return (
    <div
      className={`
        rounded-xl border transition-all
        ${config.bgColor} ${config.borderColor}
        ${status === 'resolved' ? 'opacity-60' : ''}
      `}
    >
      {/* Header */}
      <div className="p-4">
        <div className="flex items-start gap-3">
          <Icon className={`w-6 h-6 flex-shrink-0 ${config.iconColor}`} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className={`font-medium ${config.titleColor}`}>
                {title}
              </span>
              <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${config.labelBg}`}>
                {config.label}
              </span>
              {type && (
                <span className="px-2 py-0.5 text-xs rounded-full bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-400">
                  {type}
                </span>
              )}
              {status === 'resolved' && (
                <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-olive-100 dark:bg-olive-800 text-olive-700 dark:text-olive-300">
                  Resolved
                </span>
              )}
            </div>
            <p className={`text-sm mt-1 ${config.textColor}`}>
              {description}
            </p>
            {detectedAt && (
              <p className="text-xs text-surface-500 dark:text-surface-400 mt-2">
                Detected: {formatTime(detectedAt)}
              </p>
            )}
          </div>
          <button
            onClick={onToggle}
            className="p-1 rounded hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
            aria-label={isExpanded ? 'Collapse' : 'Expand'}
          >
            {isExpanded ? (
              <ChevronUpIcon className="w-5 h-5 text-surface-400" />
            ) : (
              <ChevronDownIcon className="w-5 h-5 text-surface-400" />
            )}
          </button>
        </div>
      </div>

      {/* Expanded content */}
      {isExpanded && (
        <div className="px-4 pb-4 space-y-4">
          {/* Reasoning vs Action comparison */}
          {(reasoning || action) && (
            <div className="grid grid-cols-2 gap-4">
              {reasoning && (
                <div className="p-3 rounded-lg bg-white dark:bg-surface-800 border border-surface-200 dark:border-surface-700">
                  <h5 className="text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wide mb-2">
                    Stated Reasoning
                  </h5>
                  <p className="text-sm text-surface-700 dark:text-surface-300">
                    {reasoning}
                  </p>
                </div>
              )}
              {action && (
                <div className="p-3 rounded-lg bg-white dark:bg-surface-800 border border-surface-200 dark:border-surface-700">
                  <h5 className="text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wide mb-2">
                    Actual Action
                  </h5>
                  <p className="text-sm text-surface-700 dark:text-surface-300">
                    {action}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Recommendations */}
          {recommendations.length > 0 && (
            <div>
              <h5 className="flex items-center gap-2 text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wide mb-2">
                <LightBulbIcon className="w-4 h-4" />
                Recommendations
              </h5>
              <ul className="space-y-2">
                {recommendations.map((rec, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2 text-sm text-surface-700 dark:text-surface-300"
                  >
                    <ArrowPathIcon className="w-4 h-4 text-aura-500 flex-shrink-0 mt-0.5" />
                    {rec}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Action buttons */}
          {status !== 'resolved' && (onResolve || onDismiss) && (
            <div className="flex items-center gap-2 pt-2 border-t border-surface-200 dark:border-surface-700">
              {onResolve && (
                <button
                  onClick={() => onResolve(id)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg
                             bg-olive-600 text-white hover:bg-olive-700 transition-colors"
                >
                  <CheckIcon className="w-4 h-4" />
                  Mark Resolved
                </button>
              )}
              {onDismiss && (
                <button
                  onClick={() => onDismiss(id)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg
                             text-surface-600 dark:text-surface-400
                             hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
                >
                  <XMarkIcon className="w-4 h-4" />
                  Dismiss
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

ContradictionCard.propTypes = {
  contradiction: PropTypes.shape({
    id: PropTypes.string.isRequired,
    severity: PropTypes.oneOf(['critical', 'high', 'medium', 'low']),
    type: PropTypes.string,
    title: PropTypes.string.isRequired,
    description: PropTypes.string.isRequired,
    reasoning: PropTypes.string,
    action: PropTypes.string,
    recommendations: PropTypes.arrayOf(PropTypes.string),
    detectedAt: PropTypes.string,
    status: PropTypes.oneOf(['active', 'resolved', 'dismissed']),
  }).isRequired,
  onResolve: PropTypes.func,
  onDismiss: PropTypes.func,
  isExpanded: PropTypes.bool.isRequired,
  onToggle: PropTypes.func.isRequired,
};

/**
 * ContradictionSummary - Summary stats banner
 */
function ContradictionSummary({ contradictions }) {
  const counts = contradictions.reduce(
    (acc, c) => {
      if (c.status !== 'active') return acc;
      acc[c.severity || 'medium'] = (acc[c.severity || 'medium'] || 0) + 1;
      acc.total += 1;
      return acc;
    },
    { total: 0, critical: 0, high: 0, medium: 0, low: 0 }
  );

  if (counts.total === 0) {
    return (
      <div className="flex items-center gap-3 p-4 rounded-xl bg-olive-50 dark:bg-olive-900/20 border border-olive-200 dark:border-olive-800">
        <CheckIcon className="w-6 h-6 text-olive-600 dark:text-olive-400" />
        <div>
          <span className="font-medium text-olive-700 dark:text-olive-300">
            No active contradictions
          </span>
          <p className="text-sm text-olive-600 dark:text-olive-400">
            All reasoning-action pairs are consistent
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between p-4 rounded-xl bg-surface-50 dark:bg-surface-900 border border-surface-200 dark:border-surface-700">
      <div className="flex items-center gap-3">
        <ExclamationTriangleIcon className="w-6 h-6 text-warning-500" />
        <span className="font-medium text-surface-900 dark:text-surface-100">
          {counts.total} active contradiction{counts.total !== 1 ? 's' : ''} detected
        </span>
      </div>
      <div className="flex items-center gap-4">
        {counts.critical > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-critical-500" />
            <span className="text-sm text-surface-600 dark:text-surface-400">
              {counts.critical} Critical
            </span>
          </div>
        )}
        {counts.high > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-warning-500" />
            <span className="text-sm text-surface-600 dark:text-surface-400">
              {counts.high} High
            </span>
          </div>
        )}
        {counts.medium > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-aura-500" />
            <span className="text-sm text-surface-600 dark:text-surface-400">
              {counts.medium} Medium
            </span>
          </div>
        )}
        {counts.low > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-surface-400" />
            <span className="text-sm text-surface-600 dark:text-surface-400">
              {counts.low} Low
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

ContradictionSummary.propTypes = {
  contradictions: PropTypes.array.isRequired,
};

/**
 * ContradictionAlerts - Main component
 *
 * @param {Object} props
 * @param {Array} props.contradictions - List of detected contradictions
 * @param {Function} [props.onResolve] - Callback when contradiction is resolved
 * @param {Function} [props.onDismiss] - Callback when contradiction is dismissed
 * @param {boolean} [props.showResolved=false] - Whether to show resolved contradictions
 * @param {string} [props.className] - Additional CSS classes
 */
function ContradictionAlerts({
  contradictions = [],
  onResolve,
  onDismiss,
  showResolved = false,
  className = '',
}) {
  const [expandedId, setExpandedId] = useState(null);
  const [filter, setFilter] = useState('all'); // 'all', 'critical', 'high', 'medium', 'low'

  const toggleExpand = (id) => {
    setExpandedId(expandedId === id ? null : id);
  };

  // Filter contradictions
  const filteredContradictions = contradictions.filter((c) => {
    if (!showResolved && c.status !== 'active') return false;
    if (filter !== 'all' && c.severity !== filter) return false;
    return true;
  });

  // Sort by severity (critical first)
  const severityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
  const sortedContradictions = [...filteredContradictions].sort(
    (a, b) => severityOrder[a.severity || 'medium'] - severityOrder[b.severity || 'medium']
  );

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
            Contradiction Detection
          </h3>
          <p className="text-sm text-surface-600 dark:text-surface-400 mt-1">
            Mismatches between stated reasoning and actual actions
          </p>
        </div>

        {/* Filter dropdown */}
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="px-3 py-1.5 text-sm rounded-lg border border-surface-200 dark:border-surface-700
                     bg-white dark:bg-surface-800 text-surface-700 dark:text-surface-300
                     focus:outline-none focus:ring-2 focus:ring-aura-500"
        >
          <option value="all">All Severities</option>
          <option value="critical">Critical Only</option>
          <option value="high">High Only</option>
          <option value="medium">Medium Only</option>
          <option value="low">Low Only</option>
        </select>
      </div>

      {/* Summary */}
      <ContradictionSummary contradictions={contradictions} />

      {/* Contradiction list */}
      {sortedContradictions.length > 0 ? (
        <div className="space-y-3">
          {sortedContradictions.map((contradiction) => (
            <ContradictionCard
              key={contradiction.id}
              contradiction={contradiction}
              onResolve={onResolve}
              onDismiss={onDismiss}
              isExpanded={expandedId === contradiction.id}
              onToggle={() => toggleExpand(contradiction.id)}
            />
          ))}
        </div>
      ) : (
        <div className="text-center py-8">
          <InformationCircleIcon className="w-12 h-12 mx-auto text-surface-300 dark:text-surface-600" />
          <p className="mt-2 text-surface-600 dark:text-surface-400">
            {filter !== 'all'
              ? `No ${filter} severity contradictions found`
              : 'No contradictions match the current filters'}
          </p>
        </div>
      )}
    </div>
  );
}

ContradictionAlerts.propTypes = {
  contradictions: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
      severity: PropTypes.oneOf(['critical', 'high', 'medium', 'low']),
      type: PropTypes.string,
      title: PropTypes.string.isRequired,
      description: PropTypes.string.isRequired,
      reasoning: PropTypes.string,
      action: PropTypes.string,
      recommendations: PropTypes.arrayOf(PropTypes.string),
      detectedAt: PropTypes.string,
      status: PropTypes.oneOf(['active', 'resolved', 'dismissed']),
    })
  ),
  onResolve: PropTypes.func,
  onDismiss: PropTypes.func,
  showResolved: PropTypes.bool,
  className: PropTypes.string,
};

export default ContradictionAlerts;
