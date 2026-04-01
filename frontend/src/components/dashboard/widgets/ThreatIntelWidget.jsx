/**
 * Threat Intelligence Widget
 *
 * Displays real-time threat campaigns from Palantir AIP alongside
 * affected repositories and EPSS scores.
 *
 * Per ADR-075: Widget ID 'palantir-active-threats', Category: THREAT_INTELLIGENCE
 *
 * @module components/dashboard/widgets/ThreatIntelWidget
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  ShieldExclamationIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/solid';
import { getActiveThreats } from '../../../services/palantirApi';
import { DataFreshnessIndicator } from '../../palantir/DataFreshnessIndicator';

// Severity color mappings
const SEVERITY_COLORS = {
  critical: {
    bg: 'bg-red-100 dark:bg-red-900/30',
    text: 'text-red-700 dark:text-red-300',
    border: 'border-red-200 dark:border-red-800',
    badge: 'bg-red-500 text-white',
  },
  high: {
    bg: 'bg-orange-100 dark:bg-orange-900/30',
    text: 'text-orange-700 dark:text-orange-300',
    border: 'border-orange-200 dark:border-orange-800',
    badge: 'bg-orange-500 text-white',
  },
  medium: {
    bg: 'bg-amber-100 dark:bg-amber-900/30',
    text: 'text-amber-700 dark:text-amber-300',
    border: 'border-amber-200 dark:border-amber-800',
    badge: 'bg-amber-500 text-white',
  },
  low: {
    bg: 'bg-green-100 dark:bg-green-900/30',
    text: 'text-green-700 dark:text-green-300',
    border: 'border-green-200 dark:border-green-800',
    badge: 'bg-green-500 text-white',
  },
};

/**
 * Get severity level from priority score
 */
function getSeverityFromScore(score) {
  if (score >= 90) return 'critical';
  if (score >= 70) return 'high';
  if (score >= 40) return 'medium';
  return 'low';
}

/**
 * Loading skeleton
 */
function ThreatIntelWidgetSkeleton() {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 animate-pulse">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-surface-200 dark:bg-surface-700" />
          <div className="w-32 h-5 rounded bg-surface-200 dark:bg-surface-700" />
        </div>
        <div className="w-20 h-5 rounded-full bg-surface-200 dark:bg-surface-700" />
      </div>
      <div className="space-y-3">
        {[1, 2].map((i) => (
          <div key={i} className="p-3 rounded-lg bg-surface-100 dark:bg-surface-700">
            <div className="w-24 h-4 rounded bg-surface-200 dark:bg-surface-600 mb-2" />
            <div className="w-full h-3 rounded bg-surface-200 dark:bg-surface-600" />
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Error state
 */
function ThreatIntelWidgetError({ onRetry }) {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-red-200 dark:border-red-800 p-4 flex flex-col items-center justify-center min-h-[200px]">
      <ExclamationTriangleIcon className="w-8 h-8 text-red-500 mb-2" />
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
        Failed to load threat intelligence
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
        >
          <ArrowPathIcon className="w-4 h-4" />
          Retry
        </button>
      )}
    </div>
  );
}

/**
 * Individual threat campaign card
 */
function ThreatCard({ threat, onClick }) {
  const severity = getSeverityFromScore(threat.priority_score);
  const colors = SEVERITY_COLORS[severity];

  return (
    <button
      onClick={() => onClick?.(threat)}
      className={`
        w-full text-left p-3 rounded-lg border
        ${colors.bg} ${colors.border}
        hover:shadow-sm transition-all duration-200
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1
      `}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 text-xs font-medium rounded ${colors.badge}`}>
            {severity.toUpperCase()}
          </span>
          <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
            {threat.active_campaigns[0] || 'Unknown Campaign'}
          </span>
        </div>
        <ChevronRightIcon className="w-4 h-4 text-gray-400" />
      </div>

      <div className="flex items-center gap-4 text-xs text-gray-600 dark:text-gray-400">
        {threat.epss_score && (
          <span>EPSS: {(threat.epss_score * 100).toFixed(1)}%</span>
        )}
        <span>{threat.cves.length} CVE{threat.cves.length !== 1 ? 's' : ''}</span>
        {threat.targeted_industries.length > 0 && (
          <span>{threat.targeted_industries[0]} targeting</span>
        )}
      </div>

      {threat.cves.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {threat.cves.slice(0, 3).map((cve) => (
            <span
              key={cve}
              className="px-1.5 py-0.5 text-xs bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded"
            >
              {cve}
            </span>
          ))}
          {threat.cves.length > 3 && (
            <span className="px-1.5 py-0.5 text-xs text-gray-500">
              +{threat.cves.length - 3} more
            </span>
          )}
        </div>
      )}
    </button>
  );
}

/**
 * ThreatIntelWidget component
 */
export function ThreatIntelWidget({
  refreshInterval = 60000,
  maxCampaigns = 4,
  showCorrelation = true,
  onCampaignClick = null,
  className = '',
}) {
  const [threats, setThreats] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const mountedRef = useRef(true);

  const fetchThreats = useCallback(async () => {
    try {
      const data = await getActiveThreats();
      if (mountedRef.current) {
        setThreats(data);
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
    fetchThreats();

    const interval = setInterval(fetchThreats, refreshInterval);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchThreats, refreshInterval]);

  // Show loading state
  if (isLoading) {
    return <ThreatIntelWidgetSkeleton />;
  }

  // Show error state
  if (error) {
    return <ThreatIntelWidgetError onRetry={fetchThreats} />;
  }

  // Sort by priority score and limit
  const displayThreats = threats
    ? [...threats].sort((a, b) => b.priority_score - a.priority_score).slice(0, maxCampaigns)
    : [];

  // Calculate correlation percentage (mock for now)
  const correlationPct = 97;

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        overflow-hidden
        ${className}
      `}
      role="region"
      aria-label="Threat Intelligence"
    >
      {/* Header */}
      <div className="p-4 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-red-100 dark:bg-red-900/30">
              <ShieldExclamationIcon className="w-5 h-5 text-red-600 dark:text-red-400" />
            </div>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">
              Threat Intelligence
            </h3>
          </div>
          <div className="flex items-center gap-2">
            <DataFreshnessIndicator timestamp={lastUpdated} compact />
            <button
              onClick={fetchThreats}
              className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              aria-label="Refresh"
            >
              <ArrowPathIcon className="w-4 h-4 text-gray-500" />
            </button>
          </div>
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          Active campaigns from Palantir AIP
        </p>
      </div>

      {/* Content */}
      <div className="p-4">
        {displayThreats.length === 0 ? (
          <div className="text-center py-8 text-gray-500 dark:text-gray-400">
            <ShieldExclamationIcon className="w-12 h-12 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No active threat campaigns</p>
          </div>
        ) : (
          <div className="space-y-3">
            {displayThreats.map((threat) => (
              <ThreatCard
                key={threat.threat_id}
                threat={threat}
                onClick={onCampaignClick}
              />
            ))}
          </div>
        )}

        {/* Correlation indicator */}
        {showCorrelation && displayThreats.length > 0 && (
          <div className="mt-4 pt-3 border-t border-gray-200 dark:border-gray-700">
            <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 mb-1">
              <span>Threat-to-Vulnerability Correlation</span>
              <span className="font-medium">{correlationPct}%</span>
            </div>
            <div className="h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-green-500 transition-all duration-500"
                style={{ width: `${correlationPct}%` }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

ThreatIntelWidget.propTypes = {
  refreshInterval: PropTypes.number,
  maxCampaigns: PropTypes.number,
  showCorrelation: PropTypes.bool,
  onCampaignClick: PropTypes.func,
  className: PropTypes.string,
};

export default ThreatIntelWidget;
