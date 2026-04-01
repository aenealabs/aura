/**
 * DriftStatusPanel - Configuration drift status display
 *
 * Shows current drift status per environment with affected resources
 * and provides quick actions for drift remediation.
 *
 * Part of ADR-062 Environment Validator Agent.
 */

import { useState } from 'react';
import {
  ShieldCheckIcon,
  ExclamationTriangleIcon,
  ArrowPathIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  DocumentDuplicateIcon,
  EyeIcon,
} from '@heroicons/react/24/outline';
import { Environments, SeverityColors } from '../../services/envValidatorApi';

// Mock drift data - replace with real API call
const MOCK_DRIFT_DATA = {
  dev: {
    drift_detected: true,
    critical_count: 0,
    warning_count: 2,
    last_scan: new Date(Date.now() - 15 * 60000).toISOString(),
    events: [
      {
        event_id: 'drift-001',
        resource_type: 'ConfigMap',
        resource_name: 'aura-api-config',
        namespace: 'default',
        field_path: 'data.ENVIRONMENT',
        baseline_value: 'dev',
        current_value: 'development',
        severity: 'warning',
        detected_at: new Date(Date.now() - 15 * 60000).toISOString(),
      },
      {
        event_id: 'drift-002',
        resource_type: 'ConfigMap',
        resource_name: 'aura-api-config',
        namespace: 'default',
        field_path: 'data.LOG_LEVEL',
        baseline_value: 'INFO',
        current_value: 'DEBUG',
        severity: 'warning',
        detected_at: new Date(Date.now() - 15 * 60000).toISOString(),
      },
    ],
  },
  qa: {
    drift_detected: true,
    critical_count: 1,
    warning_count: 0,
    last_scan: new Date(Date.now() - 5 * 60000).toISOString(),
    events: [
      {
        event_id: 'drift-003',
        resource_type: 'Deployment',
        resource_name: 'aura-api',
        namespace: 'aura-system',
        field_path: 'spec.template.spec.containers.0.image',
        baseline_value: '234567890123.dkr.ecr.us-east-1.amazonaws.com/aura-api:v2.0.0',
        current_value: '123456789012.dkr.ecr.us-east-1.amazonaws.com/aura-api:v2.0.0',
        severity: 'critical',
        detected_at: new Date(Date.now() - 30 * 60000).toISOString(),
      },
    ],
  },
  prod: {
    drift_detected: false,
    critical_count: 0,
    warning_count: 0,
    last_scan: new Date(Date.now() - 2 * 60000).toISOString(),
    events: [],
  },
};

// Status-colored border configuration (matches Red Team pattern)
const STATUS_BORDERS = {
  critical: 'border-critical-500 dark:border-critical-400',
  warning: 'border-warning-500 dark:border-warning-400',
  clean: 'border-olive-500 dark:border-olive-400',
};

function formatTime(timestamp) {
  const date = new Date(timestamp);
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
  });
}

function EnvironmentDriftCard({ env, data, expanded, onToggle, onViewDiff, onRescan }) {
  const hasIssues = data.drift_detected;
  const hasCritical = data.critical_count > 0;

  // Determine selected border based on status (matches Red Team pattern)
  const selectedBorder = hasCritical
    ? STATUS_BORDERS.critical
    : hasIssues
    ? STATUS_BORDERS.warning
    : STATUS_BORDERS.clean;

  const StatusIcon = hasCritical || hasIssues ? ExclamationTriangleIcon : ShieldCheckIcon;
  const statusIconColor = hasCritical
    ? 'text-critical-500'
    : hasIssues
    ? 'text-warning-500'
    : 'text-olive-500';

  return (
    <div
      className={`
        rounded-xl border-2 transition-all duration-200 overflow-hidden
        ${expanded
          ? `${selectedBorder} bg-white dark:bg-surface-800 shadow-lg`
          : 'border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 hover:border-surface-300 dark:hover:border-surface-600 hover:shadow-md'
        }
      `}
    >
      {/* Header */}
      <button
        type="button"
        onClick={() => onToggle(env)}
        className="w-full flex items-center justify-between p-3 transition-colors"
      >
        <div className="flex items-center gap-3">
          <StatusIcon className={`w-5 h-5 ${statusIconColor}`} />
          <div className="text-left">
            <span className="text-sm font-medium text-surface-900 dark:text-surface-100">
              {env.toUpperCase()}
            </span>
            <div className="text-xs text-surface-500 dark:text-surface-400">
              Last scan: {formatTime(data.last_scan)}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {hasIssues && (
            <div className="flex items-center gap-2 text-xs">
              {data.critical_count > 0 && (
                <span className="px-2 py-0.5 rounded-full bg-critical-100 dark:bg-critical-900/30 text-critical-700 dark:text-critical-400">
                  {data.critical_count} critical
                </span>
              )}
              {data.warning_count > 0 && (
                <span className="px-2 py-0.5 rounded-full bg-warning-100 dark:bg-warning-900/30 text-warning-700 dark:text-warning-400">
                  {data.warning_count} warning
                </span>
              )}
            </div>
          )}
          {!hasIssues && (
            <span className="text-xs text-olive-600 dark:text-olive-400">No drift</span>
          )}
          {expanded ? (
            <ChevronDownIcon className="w-4 h-4 text-surface-400" />
          ) : (
            <ChevronRightIcon className="w-4 h-4 text-surface-400" />
          )}
        </div>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 p-3">
          {data.events.length === 0 ? (
            <div className="text-center py-4 text-surface-500 dark:text-surface-400">
              <ShieldCheckIcon className="w-8 h-8 mx-auto mb-2 text-olive-500" />
              <p className="text-sm">No drift detected from baseline</p>
            </div>
          ) : (
            <div className="space-y-2">
              {data.events.map((event) => (
                <DriftEventItem
                  key={event.event_id}
                  event={event}
                  onViewDiff={() => onViewDiff?.(event)}
                />
              ))}
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-end gap-2 mt-3 pt-3 border-t border-surface-200 dark:border-surface-700">
            <button
              type="button"
              onClick={() => onRescan?.(env)}
              className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-100 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-md transition-colors"
            >
              <ArrowPathIcon className="w-4 h-4" />
              Rescan
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function DriftEventItem({ event, onViewDiff }) {
  const colors = SeverityColors[event.severity];

  return (
    <div className={`p-2 rounded-md ${colors.bg} ${colors.border} border`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-xs font-medium ${colors.text}`}>
              {event.severity.toUpperCase()}
            </span>
            <span className="text-xs text-surface-600 dark:text-surface-400">
              {event.resource_type}/{event.resource_name}
            </span>
          </div>
          <div className="text-xs text-surface-500 dark:text-surface-400 font-mono truncate">
            {event.field_path}
          </div>
          <div className="mt-1 flex items-center gap-2 text-xs">
            <span className="text-surface-500 dark:text-surface-400">Expected:</span>
            <code className="px-1 py-0.5 bg-surface-100 dark:bg-surface-700 rounded text-surface-700 dark:text-surface-300 truncate max-w-[150px]">
              {event.baseline_value}
            </code>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className="text-surface-500 dark:text-surface-400">Actual:</span>
            <code className={`px-1 py-0.5 rounded truncate max-w-[150px] ${colors.bg} ${colors.text}`}>
              {event.current_value}
            </code>
          </div>
        </div>

        <button
          type="button"
          onClick={onViewDiff}
          className="p-1 rounded hover:bg-surface-200 dark:hover:bg-surface-600 transition-colors"
          title="View diff"
        >
          <EyeIcon className="w-4 h-4 text-surface-400" />
        </button>
      </div>
    </div>
  );
}

export default function DriftStatusPanel({
  data = MOCK_DRIFT_DATA,
  onViewDiff,
  onRescan,
  loading = false,
  filterEnv = null,
}) {
  const [expandedEnvs, setExpandedEnvs] = useState(new Set(['dev']));

  // Get environments to display (filter if specified)
  const displayEnvs = filterEnv ? [filterEnv] : Environments;

  const toggleEnv = (env) => {
    const newExpanded = new Set(expandedEnvs);
    if (newExpanded.has(env)) {
      newExpanded.delete(env);
    } else {
      newExpanded.add(env);
    }
    setExpandedEnvs(newExpanded);
  };

  // Calculate totals
  const totalCritical = Object.values(data).reduce((sum, d) => sum + d.critical_count, 0);
  const totalWarning = Object.values(data).reduce((sum, d) => sum + d.warning_count, 0);
  const envsWithDrift = Object.values(data).filter((d) => d.drift_detected).length;

  if (loading) {
    return (
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 shadow-card p-4">
        <div className="animate-pulse">
          <div className="h-5 bg-surface-200 dark:bg-surface-700 rounded w-1/3 mb-4" />
          <div className="space-y-3">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-16 bg-surface-200 dark:bg-surface-700 rounded-lg" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 shadow-card h-full flex flex-col">
      {/* Header */}
      <div className="p-3 border-b border-surface-200 dark:border-surface-700 flex-shrink-0">
        <div className="flex items-center justify-between mb-1">
          <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100">
            Drift Status
          </h3>
          <div className="flex items-center gap-2 text-xs">
            {totalCritical > 0 && (
              <span className="px-2 py-0.5 rounded-full bg-critical-100 dark:bg-critical-900/30 text-critical-700 dark:text-critical-400">
                {totalCritical} critical
              </span>
            )}
            {totalWarning > 0 && (
              <span className="px-2 py-0.5 rounded-full bg-warning-100 dark:bg-warning-900/30 text-warning-700 dark:text-warning-400">
                {totalWarning} warning
              </span>
            )}
          </div>
        </div>
        <p className="text-xs text-surface-500 dark:text-surface-400">
          {envsWithDrift === 0
            ? 'All environments match baseline'
            : `${envsWithDrift} environment${envsWithDrift > 1 ? 's' : ''} with drift detected`}
        </p>
      </div>

      {/* Environment cards - scrollable */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2 min-h-0">
        {displayEnvs.map((env) => (
          <EnvironmentDriftCard
            key={env}
            env={env}
            data={data[env] || { drift_detected: false, critical_count: 0, warning_count: 0, last_scan: new Date().toISOString(), events: [] }}
            expanded={expandedEnvs.has(env)}
            onToggle={toggleEnv}
            onViewDiff={onViewDiff}
            onRescan={onRescan}
          />
        ))}
      </div>
    </div>
  );
}
