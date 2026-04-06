/**
 * Agent Lifecycle Widget
 *
 * Displays agent lifecycle state counts (active, dormant, decommissioning,
 * attested, archived) and ghost agent alerts.
 *
 * Per ADR-086: Widget ID 'agent-lifecycle', Category: RUNTIME_SECURITY
 *
 * @module components/dashboard/widgets/AgentLifecycleWidget
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  ArrowPathIcon,
  ShieldCheckIcon,
  ExclamationTriangleIcon,
  UserMinusIcon,
  ArchiveBoxIcon,
  ClockIcon,
  CheckBadgeIcon,
} from '@heroicons/react/24/solid';
import { DataFreshnessIndicator } from '../../palantir/DataFreshnessIndicator';

// State configuration
const STATE_CONFIG = {
  active: {
    icon: ShieldCheckIcon,
    color: 'text-green-500',
    bgColor: 'bg-green-100 dark:bg-green-900/30',
    label: 'Active',
  },
  dormant: {
    icon: ClockIcon,
    color: 'text-yellow-500',
    bgColor: 'bg-yellow-100 dark:bg-yellow-900/30',
    label: 'Dormant',
  },
  decommissioning: {
    icon: UserMinusIcon,
    color: 'text-orange-500',
    bgColor: 'bg-orange-100 dark:bg-orange-900/30',
    label: 'Decommissioning',
  },
  attested: {
    icon: CheckBadgeIcon,
    color: 'text-blue-500',
    bgColor: 'bg-blue-100 dark:bg-blue-900/30',
    label: 'Attested',
  },
  archived: {
    icon: ArchiveBoxIcon,
    color: 'text-surface-400',
    bgColor: 'bg-surface-100 dark:bg-surface-700',
    label: 'Archived',
  },
};

const SEVERITY_COLORS = {
  critical: 'text-red-600 bg-red-100 dark:bg-red-900/30',
  high: 'text-orange-600 bg-orange-100 dark:bg-orange-900/30',
  medium: 'text-yellow-600 bg-yellow-100 dark:bg-yellow-900/30',
  low: 'text-blue-600 bg-blue-100 dark:bg-blue-900/30',
};

/**
 * Loading skeleton
 */
function AgentLifecycleWidgetSkeleton() {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 animate-pulse">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-surface-200 dark:bg-surface-700" />
          <div className="w-36 h-5 rounded bg-surface-200 dark:bg-surface-700" />
        </div>
      </div>
      <div className="grid grid-cols-5 gap-2 mb-4">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="p-2 rounded-lg bg-surface-100 dark:bg-surface-700">
            <div className="w-8 h-6 rounded bg-surface-200 dark:bg-surface-600 mx-auto mb-1" />
            <div className="w-12 h-3 rounded bg-surface-200 dark:bg-surface-600 mx-auto" />
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * State count card
 */
function StateCard({ stateKey, count }) {
  const config = STATE_CONFIG[stateKey];
  if (!config) return null;
  const Icon = config.icon;

  return (
    <div className={`p-2 rounded-lg ${config.bgColor} text-center`}>
      <Icon className={`w-5 h-5 ${config.color} mx-auto mb-1`} />
      <div className={`text-lg font-semibold ${config.color}`}>{count}</div>
      <div className="text-xs text-surface-500 dark:text-surface-400">{config.label}</div>
    </div>
  );
}

StateCard.propTypes = {
  stateKey: PropTypes.string.isRequired,
  count: PropTypes.number.isRequired,
};

/**
 * Ghost agent alert row
 */
function GhostAlertRow({ finding }) {
  const severityClass = SEVERITY_COLORS[finding.severity] || SEVERITY_COLORS.medium;

  return (
    <div className="flex items-center gap-3 p-2 rounded-lg bg-surface-50 dark:bg-surface-700/50">
      <ExclamationTriangleIcon className="w-4 h-4 text-orange-500 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-surface-900 dark:text-surface-100 truncate">
          {finding.agent_id}
        </div>
        <div className="text-xs text-surface-500 dark:text-surface-400">
          {finding.active_credential_count} credential(s) across{' '}
          {finding.active_credential_classes?.length || 0} class(es)
        </div>
      </div>
      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${severityClass}`}>
        {finding.severity}
      </span>
    </div>
  );
}

GhostAlertRow.propTypes = {
  finding: PropTypes.shape({
    agent_id: PropTypes.string.isRequired,
    severity: PropTypes.string.isRequired,
    active_credential_count: PropTypes.number.isRequired,
    active_credential_classes: PropTypes.arrayOf(PropTypes.string),
  }).isRequired,
};

/**
 * Agent Lifecycle Widget
 */
export default function AgentLifecycleWidget({
  refreshInterval = 60,
  maxGhostAlerts = 5,
  onGhostAlertClick,
}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const intervalRef = useRef(null);

  const fetchData = useCallback(async () => {
    try {
      // In production, this calls the lifecycle API endpoint
      const response = await fetch('/api/v1/agents/lifecycle/summary');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const result = await response.json();
      setData(result);
      setLastUpdated(new Date());
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    intervalRef.current = setInterval(fetchData, refreshInterval * 1000);
    return () => clearInterval(intervalRef.current);
  }, [fetchData, refreshInterval]);

  if (loading && !data) return <AgentLifecycleWidgetSkeleton />;

  const stateCounts = data?.state_counts || {};
  const ghostFindings = (data?.ghost_findings || []).slice(0, maxGhostAlerts);

  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-blue-100 dark:bg-blue-900/30">
            <ShieldCheckIcon className="w-5 h-5 text-blue-500" />
          </div>
          <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100">
            Agent Lifecycle
          </h3>
        </div>
        <div className="flex items-center gap-2">
          {lastUpdated && <DataFreshnessIndicator lastUpdated={lastUpdated} />}
          <button
            onClick={fetchData}
            className="p-1 rounded hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
            title="Refresh"
          >
            <ArrowPathIcon className="w-4 h-4 text-surface-400" />
          </button>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="mb-3 p-2 rounded-lg bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-xs">
          {error}
        </div>
      )}

      {/* State counts grid */}
      <div className="grid grid-cols-5 gap-2 mb-4">
        {Object.keys(STATE_CONFIG).map((stateKey) => (
          <StateCard key={stateKey} stateKey={stateKey} count={stateCounts[stateKey] || 0} />
        ))}
      </div>

      {/* Ghost agent alerts */}
      {ghostFindings.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-surface-500 dark:text-surface-400 uppercase tracking-wider mb-2">
            Ghost Agent Alerts
          </h4>
          <div className="space-y-2">
            {ghostFindings.map((finding) => (
              <div
                key={finding.finding_id}
                onClick={() => onGhostAlertClick?.(finding)}
                className={onGhostAlertClick ? 'cursor-pointer' : ''}
              >
                <GhostAlertRow finding={finding} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {ghostFindings.length === 0 && !error && (
        <div className="text-center py-2">
          <CheckBadgeIcon className="w-6 h-6 text-green-400 mx-auto mb-1" />
          <p className="text-xs text-surface-500 dark:text-surface-400">No ghost agents detected</p>
        </div>
      )}
    </div>
  );
}

AgentLifecycleWidget.propTypes = {
  refreshInterval: PropTypes.number,
  maxGhostAlerts: PropTypes.number,
  onGhostAlertClick: PropTypes.func,
};
