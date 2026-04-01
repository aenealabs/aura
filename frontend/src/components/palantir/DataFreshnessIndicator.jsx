/**
 * Data Freshness Indicator Component
 *
 * Displays the freshness of synced data from Palantir with
 * visual indicators for fresh, stale, and expired states.
 *
 * @module components/palantir/DataFreshnessIndicator
 */

import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import { ClockIcon } from '@heroicons/react/24/outline';

// Freshness thresholds in minutes
const FRESHNESS_THRESHOLDS = {
  fresh: {
    maxMinutes: 5,
    color: 'text-green-600',
    bgColor: 'bg-green-100',
    dotColor: 'bg-green-500',
    label: 'Just now',
  },
  stale: {
    maxMinutes: 30,
    color: 'text-amber-600',
    bgColor: 'bg-amber-100',
    dotColor: 'bg-amber-500',
    label: (minutes) => `${minutes} min ago`,
  },
  expired: {
    maxMinutes: 60,
    color: 'text-red-600',
    bgColor: 'bg-red-100',
    dotColor: 'bg-red-500',
    label: 'May be outdated',
  },
  unknown: {
    maxMinutes: Infinity,
    color: 'text-gray-500',
    bgColor: 'bg-gray-100',
    dotColor: 'bg-gray-400',
    label: 'Unknown',
  },
};

/**
 * Calculate freshness state from timestamp
 */
function getFreshnessState(timestamp) {
  if (!timestamp) return 'unknown';

  const now = new Date();
  const then = new Date(timestamp);
  const diffMs = now - then;
  const diffMinutes = Math.floor(diffMs / 60000);

  if (diffMinutes <= FRESHNESS_THRESHOLDS.fresh.maxMinutes) return 'fresh';
  if (diffMinutes <= FRESHNESS_THRESHOLDS.stale.maxMinutes) return 'stale';
  if (diffMinutes <= FRESHNESS_THRESHOLDS.expired.maxMinutes) return 'expired';
  return 'unknown';
}

/**
 * Get minutes since timestamp
 */
function getMinutesSince(timestamp) {
  if (!timestamp) return null;
  const diffMs = new Date() - new Date(timestamp);
  return Math.floor(diffMs / 60000);
}

/**
 * DataFreshnessIndicator component
 */
export function DataFreshnessIndicator({
  timestamp,
  label = 'Last sync',
  showIcon = true,
  showDot = true,
  compact = false,
  className = '',
}) {
  const freshnessState = useMemo(() => getFreshnessState(timestamp), [timestamp]);
  const minutes = useMemo(() => getMinutesSince(timestamp), [timestamp]);
  const config = FRESHNESS_THRESHOLDS[freshnessState];

  // Get display label
  const displayLabel = typeof config.label === 'function'
    ? config.label(minutes)
    : config.label;

  // Compact variant - just a dot and text
  if (compact) {
    return (
      <span
        className={`inline-flex items-center gap-1 ${config.color} ${className}`}
        role="status"
        aria-label={`${label}: ${displayLabel}`}
      >
        {showDot && (
          <span
            className={`w-1.5 h-1.5 rounded-full ${config.dotColor}`}
            aria-hidden="true"
          />
        )}
        <span className="text-xs">{displayLabel}</span>
      </span>
    );
  }

  return (
    <div
      className={`
        inline-flex items-center gap-2 px-2.5 py-1 rounded-full
        ${config.bgColor} ${config.color}
        ${className}
      `}
      role="status"
      aria-label={`${label}: ${displayLabel}`}
    >
      {showIcon && (
        <ClockIcon className="w-4 h-4" aria-hidden="true" />
      )}
      <span className="text-xs font-medium">
        {label}: {displayLabel}
      </span>
    </div>
  );
}

DataFreshnessIndicator.propTypes = {
  timestamp: PropTypes.string,
  label: PropTypes.string,
  showIcon: PropTypes.bool,
  showDot: PropTypes.bool,
  compact: PropTypes.bool,
  className: PropTypes.string,
};

/**
 * Hook for freshness state
 */
export function useFreshness(timestamp) {
  return useMemo(() => {
    const state = getFreshnessState(timestamp);
    const minutes = getMinutesSince(timestamp);
    const config = FRESHNESS_THRESHOLDS[state];

    return {
      state,
      minutes,
      isFresh: state === 'fresh',
      isStale: state === 'stale',
      isExpired: state === 'expired',
      isUnknown: state === 'unknown',
      color: config.color,
      bgColor: config.bgColor,
      label: typeof config.label === 'function' ? config.label(minutes) : config.label,
    };
  }, [timestamp]);
}

export default DataFreshnessIndicator;
