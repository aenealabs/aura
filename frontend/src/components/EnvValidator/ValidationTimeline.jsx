/**
 * ValidationTimeline - Timeline visualization of validation runs
 *
 * Displays a time-series view of environment validation runs with
 * pass/fail status, violation counts, and drill-down capability.
 *
 * Part of ADR-062 Environment Validator Agent.
 */

import { useState, useEffect } from 'react';
import {
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  ClockIcon,
  ChevronRightIcon,
  FunnelIcon,
} from '@heroicons/react/24/outline';
import { ResultColors, Environments } from '../../services/envValidatorApi';

// Mock data for development - replace with real API call
const MOCK_TIMELINE_DATA = [
  {
    run_id: 'run-001',
    timestamp: new Date(Date.now() - 5 * 60000).toISOString(),
    environment: 'qa',
    trigger: 'pre_deploy',
    result: 'pass',
    violations_count: 0,
    warnings_count: 2,
    resources_scanned: 15,
  },
  {
    run_id: 'run-002',
    timestamp: new Date(Date.now() - 35 * 60000).toISOString(),
    environment: 'dev',
    trigger: 'manual',
    result: 'fail',
    violations_count: 3,
    warnings_count: 1,
    resources_scanned: 8,
  },
  {
    run_id: 'run-003',
    timestamp: new Date(Date.now() - 2 * 3600000).toISOString(),
    environment: 'qa',
    trigger: 'scheduled',
    result: 'pass',
    violations_count: 0,
    warnings_count: 0,
    resources_scanned: 15,
  },
  {
    run_id: 'run-004',
    timestamp: new Date(Date.now() - 4 * 3600000).toISOString(),
    environment: 'prod',
    trigger: 'post_deploy',
    result: 'warn',
    violations_count: 0,
    warnings_count: 5,
    resources_scanned: 22,
  },
  {
    run_id: 'run-005',
    timestamp: new Date(Date.now() - 6 * 3600000).toISOString(),
    environment: 'dev',
    trigger: 'drift_detection',
    result: 'pass',
    violations_count: 0,
    warnings_count: 1,
    resources_scanned: 18,
  },
  {
    run_id: 'run-006',
    timestamp: new Date(Date.now() - 12 * 3600000).toISOString(),
    environment: 'qa',
    trigger: 'pre_deploy',
    result: 'fail',
    violations_count: 2,
    warnings_count: 0,
    resources_scanned: 15,
  },
];

// Status-colored border configuration (matches Red Team pattern)
const RESULT_BORDERS = {
  pass: 'border-olive-500 dark:border-olive-400',
  fail: 'border-critical-500 dark:border-critical-400',
  warn: 'border-warning-500 dark:border-warning-400',
};

const TRIGGER_LABELS = {
  pre_deploy: 'Pre-Deploy',
  post_deploy: 'Post-Deploy',
  scheduled: 'Scheduled',
  manual: 'Manual',
  drift_detection: 'Drift Check',
};

function formatRelativeTime(timestamp) {
  const now = new Date();
  const time = new Date(timestamp);
  const diff = now - time;

  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  return `${days}d ago`;
}

function ResultIcon({ result }) {
  switch (result) {
    case 'pass':
      return <CheckCircleIcon className="w-5 h-5 text-olive-500" />;
    case 'fail':
      return <XCircleIcon className="w-5 h-5 text-critical-500" />;
    case 'warn':
      return <ExclamationTriangleIcon className="w-5 h-5 text-warning-500" />;
    default:
      return <ClockIcon className="w-5 h-5 text-surface-400" />;
  }
}

function TimelineItem({ run, onSelect, isSelected = false }) {
  const colors = ResultColors[run.result] || ResultColors.pass;
  const selectedBorder = RESULT_BORDERS[run.result] || RESULT_BORDERS.pass;

  return (
    <button
      type="button"
      onClick={() => onSelect?.(run)}
      className={`
        w-full text-left p-3 rounded-xl border-2 transition-all duration-200 mb-2
        ${isSelected
          ? `${selectedBorder} bg-white dark:bg-surface-800 shadow-lg`
          : 'border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 hover:border-surface-300 dark:hover:border-surface-600 hover:shadow-md'
        }
      `}
    >
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div className={`p-2 rounded-lg ${colors.bg} flex-shrink-0`}>
          <ResultIcon result={run.result} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-medium text-surface-900 dark:text-surface-100">
              {run.environment.toUpperCase()}
            </span>
            <span className={`px-2 py-0.5 text-xs rounded-full ${colors.bg} ${colors.text}`}>
              {run.result.toUpperCase()}
            </span>
            <span className="text-xs text-surface-500 dark:text-surface-400">
              {TRIGGER_LABELS[run.trigger] || run.trigger}
            </span>
          </div>

          <div className="flex items-center gap-4 text-xs text-surface-500 dark:text-surface-400">
            <span>{run.resources_scanned} resources</span>
            {run.violations_count > 0 && (
              <span className="text-critical-600 dark:text-critical-400">
                {run.violations_count} violations
              </span>
            )}
            {run.warnings_count > 0 && (
              <span className="text-warning-600 dark:text-warning-400">
                {run.warnings_count} warnings
              </span>
            )}
          </div>
        </div>

        {/* Time and arrow */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-xs text-surface-400 dark:text-surface-500">
            {formatRelativeTime(run.timestamp)}
          </span>
          <ChevronRightIcon className={`w-4 h-4 text-surface-400 transition-transform ${isSelected ? 'rotate-90' : ''}`} />
        </div>
      </div>
    </button>
  );
}

export default function ValidationTimeline({
  data = MOCK_TIMELINE_DATA,
  onSelectRun,
  loading = false,
  maxItems = 10,
  filterEnv = null,
}) {
  const [envFilter, setEnvFilter] = useState(filterEnv);
  const [resultFilter, setResultFilter] = useState(null);
  const [selectedRunId, setSelectedRunId] = useState(null);

  // Sync envFilter with filterEnv prop when it changes from parent
  useEffect(() => {
    setEnvFilter(filterEnv);
  }, [filterEnv]);

  // Handle run selection
  const handleSelectRun = (run) => {
    setSelectedRunId(run.run_id === selectedRunId ? null : run.run_id);
    onSelectRun?.(run);
  };

  // Filter data
  const filteredData = data.filter((run) => {
    if (envFilter && run.environment !== envFilter) return false;
    if (resultFilter && run.result !== resultFilter) return false;
    return true;
  }).slice(0, maxItems);

  if (loading) {
    return (
      <div className="animate-pulse space-y-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="flex items-start gap-4 p-3">
            <div className="w-9 h-9 bg-surface-200 dark:bg-surface-700 rounded-lg" />
            <div className="flex-1 space-y-2">
              <div className="h-4 bg-surface-200 dark:bg-surface-700 rounded w-1/3" />
              <div className="h-3 bg-surface-200 dark:bg-surface-700 rounded w-1/2" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 shadow-card h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-surface-200 dark:border-surface-700 flex-shrink-0">
        <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100">
          Validation Timeline
        </h3>

        {/* Filters */}
        <div className="flex items-center gap-2">
          <select
            value={envFilter || ''}
            onChange={(e) => setEnvFilter(e.target.value || null)}
            className="text-xs px-2 py-1 rounded-md border border-surface-200 dark:border-surface-600 bg-white dark:bg-surface-700 text-surface-700 dark:text-surface-300"
          >
            <option value="">All Envs</option>
            {Environments.map((env) => (
              <option key={env} value={env}>{env.toUpperCase()}</option>
            ))}
          </select>

          <select
            value={resultFilter || ''}
            onChange={(e) => setResultFilter(e.target.value || null)}
            className="text-xs px-2 py-1 rounded-md border border-surface-200 dark:border-surface-600 bg-white dark:bg-surface-700 text-surface-700 dark:text-surface-300"
          >
            <option value="">All Results</option>
            <option value="pass">Pass</option>
            <option value="fail">Fail</option>
            <option value="warn">Warn</option>
          </select>
        </div>
      </div>

      {/* Timeline - scrollable */}
      <div className="flex-1 overflow-y-auto p-2 min-h-0">
        {filteredData.length === 0 ? (
          <div className="text-center py-8 text-surface-500 dark:text-surface-400">
            <ClockIcon className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No validation runs found</p>
          </div>
        ) : (
          <div className="space-y-0">
            {filteredData.map((run) => (
              <TimelineItem
                key={run.run_id}
                run={run}
                onSelect={handleSelectRun}
                isSelected={run.run_id === selectedRunId}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
