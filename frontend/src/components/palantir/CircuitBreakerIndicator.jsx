/**
 * Circuit Breaker Indicator Component
 *
 * Displays the current state of the Palantir integration circuit breaker
 * with visual indicators, metrics, and admin actions.
 *
 * States:
 * - CLOSED: Normal operation (green)
 * - HALF_OPEN: Recovery testing (amber)
 * - OPEN: Circuit tripped (red)
 *
 * @module components/palantir/CircuitBreakerIndicator
 */

import React from 'react';
import PropTypes from 'prop-types';
import {
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/solid';

// State configurations
const STATE_CONFIG = {
  CLOSED: {
    color: 'bg-green-500',
    textColor: 'text-green-700',
    bgLight: 'bg-green-50',
    borderColor: 'border-green-200',
    icon: CheckCircleIcon,
    label: 'Operational',
    description: 'Circuit breaker is closed. Normal operation.',
  },
  HALF_OPEN: {
    color: 'bg-amber-500',
    textColor: 'text-amber-700',
    bgLight: 'bg-amber-50',
    borderColor: 'border-amber-200',
    icon: ArrowPathIcon,
    label: 'Recovering',
    description: 'Testing connectivity. Limited requests allowed.',
    animate: true,
  },
  OPEN: {
    color: 'bg-red-500',
    textColor: 'text-red-700',
    bgLight: 'bg-red-50',
    borderColor: 'border-red-200',
    icon: ExclamationTriangleIcon,
    label: 'Degraded',
    description: 'Circuit is open. Requests are being rejected.',
    pulse: true,
  },
};

/**
 * Format seconds into human-readable duration
 */
function formatDuration(seconds) {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  return `${Math.round(seconds / 3600)}h`;
}

/**
 * Format timestamp to relative time
 */
function formatRelativeTime(isoString) {
  if (!isoString) return 'Never';
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

/**
 * CircuitBreakerIndicator component
 */
export function CircuitBreakerIndicator({
  state = 'CLOSED',
  failureCount = 0,
  failureThreshold = 5,
  successCount = 0,
  totalFailures = 0,
  totalSuccesses = 0,
  lastFailure = null,
  lastStateChange = null,
  recoveryTimeout = 60,
  onReset = null,
  onForceOpen = null,
  showActions = false,
  showMetrics = true,
  compact = false,
  className = '',
}) {
  const config = STATE_CONFIG[state] || STATE_CONFIG.CLOSED;
  const Icon = config.icon;
  const failurePercentage = Math.min((failureCount / failureThreshold) * 100, 100);

  // Compact variant for inline display
  if (compact) {
    return (
      <div
        className={`inline-flex items-center gap-2 ${className}`}
        role="status"
        aria-label={`Circuit breaker status: ${config.label}`}
      >
        <span
          className={`
            w-2 h-2 rounded-full ${config.color}
            ${config.pulse ? 'animate-pulse' : ''}
            ${config.animate ? 'animate-spin' : ''}
          `}
        />
        <span className={`text-sm font-medium ${config.textColor}`}>
          {config.label}
        </span>
      </div>
    );
  }

  return (
    <div
      className={`
        rounded-lg border p-4 ${config.bgLight} ${config.borderColor}
        ${className}
      `}
      role="region"
      aria-label="Circuit Breaker Status"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Icon
            className={`
              w-5 h-5 ${config.textColor}
              ${config.animate ? 'animate-spin' : ''}
            `}
            aria-hidden="true"
          />
          <span className={`font-semibold ${config.textColor}`}>
            {config.label}
          </span>
        </div>
        <span
          className={`
            px-2 py-0.5 text-xs font-medium rounded-full
            ${config.color} text-white
            ${config.pulse ? 'animate-pulse' : ''}
          `}
        >
          {state}
        </span>
      </div>

      {/* Description */}
      <p className="text-sm text-gray-600 mb-3" aria-live="polite">
        {config.description}
      </p>

      {/* Failure Progress Bar */}
      <div className="mb-3">
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          <span>Failure Count</span>
          <span>{failureCount} / {failureThreshold}</span>
        </div>
        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all duration-300 ${
              failurePercentage >= 100 ? 'bg-red-500' :
              failurePercentage >= 60 ? 'bg-amber-500' : 'bg-green-500'
            }`}
            style={{ width: `${failurePercentage}%` }}
            role="progressbar"
            aria-valuenow={failureCount}
            aria-valuemin={0}
            aria-valuemax={failureThreshold}
            aria-label={`${failureCount} of ${failureThreshold} failures`}
          />
        </div>
      </div>

      {/* Metrics */}
      {showMetrics && (
        <div className="grid grid-cols-2 gap-2 text-xs text-gray-600 mb-3">
          <div>
            <span className="text-gray-400">Recovery Timeout:</span>{' '}
            <span className="font-medium">{formatDuration(recoveryTimeout)}</span>
          </div>
          <div>
            <span className="text-gray-400">Success Count:</span>{' '}
            <span className="font-medium">{successCount}</span>
          </div>
          <div>
            <span className="text-gray-400">Total Failures:</span>{' '}
            <span className="font-medium">{totalFailures}</span>
          </div>
          <div>
            <span className="text-gray-400">Total Successes:</span>{' '}
            <span className="font-medium">{totalSuccesses}</span>
          </div>
          {lastFailure && (
            <div className="col-span-2">
              <span className="text-gray-400">Last Failure:</span>{' '}
              <span className="font-medium">{formatRelativeTime(lastFailure)}</span>
            </div>
          )}
          {lastStateChange && (
            <div className="col-span-2">
              <span className="text-gray-400">State Changed:</span>{' '}
              <span className="font-medium">{formatRelativeTime(lastStateChange)}</span>
            </div>
          )}
        </div>
      )}

      {/* Admin Actions */}
      {showActions && (
        <div className="flex gap-2 pt-2 border-t border-gray-200">
          {onReset && (
            <button
              onClick={onReset}
              className="
                flex-1 px-3 py-1.5 text-xs font-medium
                bg-white border border-gray-300 rounded
                hover:bg-gray-50 transition-colors
                focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1
              "
              aria-label="Reset circuit breaker failures"
            >
              Reset Failures
            </button>
          )}
          {onForceOpen && state !== 'OPEN' && (
            <button
              onClick={onForceOpen}
              className="
                flex-1 px-3 py-1.5 text-xs font-medium
                bg-red-50 border border-red-200 rounded text-red-700
                hover:bg-red-100 transition-colors
                focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-1
              "
              aria-label="Force open circuit breaker"
            >
              Force Open
            </button>
          )}
        </div>
      )}
    </div>
  );
}

CircuitBreakerIndicator.propTypes = {
  state: PropTypes.oneOf(['CLOSED', 'HALF_OPEN', 'OPEN']),
  failureCount: PropTypes.number,
  failureThreshold: PropTypes.number,
  successCount: PropTypes.number,
  totalFailures: PropTypes.number,
  totalSuccesses: PropTypes.number,
  lastFailure: PropTypes.string,
  lastStateChange: PropTypes.string,
  recoveryTimeout: PropTypes.number,
  onReset: PropTypes.func,
  onForceOpen: PropTypes.func,
  showActions: PropTypes.bool,
  showMetrics: PropTypes.bool,
  compact: PropTypes.bool,
  className: PropTypes.string,
};

export default CircuitBreakerIndicator;
