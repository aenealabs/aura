/**
 * Prioritized Vulnerabilities Widget
 *
 * Displays CVEs ranked by composite score (EPSS + asset criticality + active threat).
 *
 * Per ADR-075: Widget ID 'palantir-cve-prioritization', Category: SECURITY
 *
 * @module components/dashboard/widgets/PrioritizedVulnsWidget
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  ShieldExclamationIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  ArrowTopRightOnSquareIcon,
} from '@heroicons/react/24/solid';
import { getActiveThreats } from '../../../services/palantirApi';
import { DataFreshnessIndicator } from '../../palantir/DataFreshnessIndicator';

// Score threshold colors
const SCORE_THRESHOLDS = {
  critical: { min: 90, color: 'text-red-600', bg: 'bg-red-500', label: 'Critical' },
  high: { min: 70, color: 'text-orange-600', bg: 'bg-orange-500', label: 'High' },
  medium: { min: 40, color: 'text-amber-600', bg: 'bg-amber-500', label: 'Medium' },
  low: { min: 0, color: 'text-green-600', bg: 'bg-green-500', label: 'Low' },
};

/**
 * Get severity from score
 */
function getSeverityFromScore(score) {
  if (score >= 90) return SCORE_THRESHOLDS.critical;
  if (score >= 70) return SCORE_THRESHOLDS.high;
  if (score >= 40) return SCORE_THRESHOLDS.medium;
  return SCORE_THRESHOLDS.low;
}

/**
 * Loading skeleton
 */
function PrioritizedVulnsWidgetSkeleton() {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 animate-pulse">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-surface-200 dark:bg-surface-700" />
          <div className="w-40 h-5 rounded bg-surface-200 dark:bg-surface-700" />
        </div>
      </div>
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="p-3 rounded-lg bg-surface-100 dark:bg-surface-700">
            <div className="w-32 h-4 rounded bg-surface-200 dark:bg-surface-600 mb-2" />
            <div className="w-full h-3 rounded bg-surface-200 dark:bg-surface-600" />
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Score bar visualization
 */
function ScoreBar({ score }) {
  const severity = getSeverityFromScore(score);

  return (
    <div className="flex items-center gap-2">
      <div className="w-12 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full ${severity.bg} transition-all`}
          style={{ width: `${score}%` }}
        />
      </div>
      <span className={`text-xs font-medium ${severity.color}`}>
        {score.toFixed(1)}
      </span>
    </div>
  );
}

/**
 * Vulnerability row
 */
function VulnRow({ rank, cve, score, epss, reason, onClick }) {
  const severity = getSeverityFromScore(score);

  return (
    <button
      onClick={() => onClick?.(cve)}
      className="
        w-full text-left p-3 rounded-lg
        bg-gray-50 dark:bg-gray-800
        hover:bg-gray-100 dark:hover:bg-gray-700
        transition-colors duration-200
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1
      "
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="
            w-6 h-6 flex items-center justify-center
            text-xs font-bold text-white rounded-full
            bg-gray-400 dark:bg-gray-600
          ">
            {rank}
          </span>
          <div>
            <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${severity.bg} text-white`}>
              {severity.label}
            </span>
            <span className="ml-2 text-sm font-semibold text-gray-900 dark:text-gray-100">
              {cve}
            </span>
          </div>
        </div>
        <ArrowTopRightOnSquareIcon className="w-4 h-4 text-gray-400" />
      </div>

      <div className="flex items-center justify-between pl-8">
        <ScoreBar score={score} />
        {epss && (
          <span className="text-xs text-gray-500 dark:text-gray-400">
            EPSS: {(epss * 100).toFixed(1)}%
          </span>
        )}
      </div>

      {reason && (
        <p className="mt-2 pl-8 text-xs text-gray-500 dark:text-gray-400 line-clamp-1">
          {reason}
        </p>
      )}
    </button>
  );
}

/**
 * PrioritizedVulnsWidget component
 */
export function PrioritizedVulnsWidget({
  refreshInterval = 300000,
  maxVulns = 5,
  onVulnClick = null,
  onViewQueue = null,
  className = '',
}) {
  const [vulns, setVulns] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const mountedRef = useRef(true);

  const fetchVulns = useCallback(async () => {
    try {
      // Get threats and extract CVE info
      const threats = await getActiveThreats();

      // Flatten CVEs from all threats with their scores
      const cveList = [];
      threats.forEach((threat) => {
        threat.cves.forEach((cve) => {
          cveList.push({
            cve,
            score: threat.priority_score,
            epss: threat.epss_score,
            reason: threat.active_campaigns.length > 0
              ? `Active campaign + ${threat.targeted_industries[0] || 'Unknown'} targeting`
              : 'High EPSS score',
          });
        });
      });

      // Sort by score and dedupe
      const uniqueCves = new Map();
      cveList.forEach((item) => {
        if (!uniqueCves.has(item.cve) || uniqueCves.get(item.cve).score < item.score) {
          uniqueCves.set(item.cve, item);
        }
      });

      const sorted = Array.from(uniqueCves.values())
        .sort((a, b) => b.score - a.score);

      if (mountedRef.current) {
        setVulns(sorted);
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
    fetchVulns();

    const interval = setInterval(fetchVulns, refreshInterval);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchVulns, refreshInterval]);

  if (isLoading) {
    return <PrioritizedVulnsWidgetSkeleton />;
  }

  if (error) {
    return (
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-red-200 p-4 flex flex-col items-center justify-center min-h-[200px]">
        <ExclamationTriangleIcon className="w-8 h-8 text-red-500 mb-2" />
        <p className="text-sm text-gray-600 mb-3">Failed to load vulnerabilities</p>
        <button
          onClick={fetchVulns}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-blue-600 hover:bg-blue-50 rounded-lg"
        >
          <ArrowPathIcon className="w-4 h-4" />
          Retry
        </button>
      </div>
    );
  }

  const displayVulns = vulns?.slice(0, maxVulns) || [];

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        overflow-hidden
        ${className}
      `}
    >
      {/* Header */}
      <div className="p-4 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-orange-100 dark:bg-orange-900/30">
              <ShieldExclamationIcon className="w-5 h-5 text-orange-600 dark:text-orange-400" />
            </div>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">
              Prioritized Vulnerabilities
            </h3>
          </div>
          <div className="flex items-center gap-2">
            {onViewQueue && (
              <button
                onClick={onViewQueue}
                className="text-xs text-blue-600 hover:text-blue-700 font-medium"
              >
                Full Queue →
              </button>
            )}
          </div>
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          EPSS + Asset Criticality + Active Threat
        </p>
      </div>

      {/* Content */}
      <div className="p-4 space-y-2">
        {displayVulns.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <ShieldExclamationIcon className="w-12 h-12 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No prioritized vulnerabilities</p>
          </div>
        ) : (
          displayVulns.map((vuln, idx) => (
            <VulnRow
              key={vuln.cve}
              rank={idx + 1}
              cve={vuln.cve}
              score={vuln.score}
              epss={vuln.epss}
              reason={vuln.reason}
              onClick={onVulnClick}
            />
          ))
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700">
        <DataFreshnessIndicator timestamp={lastUpdated} label="Last sync" />
      </div>
    </div>
  );
}

PrioritizedVulnsWidget.propTypes = {
  refreshInterval: PropTypes.number,
  maxVulns: PropTypes.number,
  onVulnClick: PropTypes.func,
  onViewQueue: PropTypes.func,
  className: PropTypes.string,
};

export default PrioritizedVulnsWidget;
