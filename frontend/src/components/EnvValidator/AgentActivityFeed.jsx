/**
 * AgentActivityFeed - Real-time agent activity stream
 *
 * Displays a live feed of Environment Validator agent actions
 * including validations, drift detections, and remediation attempts.
 *
 * Part of ADR-062 Environment Validator Agent.
 */

import { useState, useEffect, useRef } from 'react';
import {
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  ArrowPathIcon,
  ShieldCheckIcon,
  DocumentMagnifyingGlassIcon,
  WrenchScrewdriverIcon,
  BoltIcon,
  PauseIcon,
  PlayIcon,
} from '@heroicons/react/24/outline';

// Activity types and their configurations
const ACTIVITY_TYPES = {
  validation_started: {
    icon: DocumentMagnifyingGlassIcon,
    color: 'text-aura-500',
    bgColor: 'bg-aura-100 dark:bg-aura-900/30',
    label: 'Validation Started',
    selectedBorder: 'border-aura-500 dark:border-aura-400',
  },
  validation_passed: {
    icon: CheckCircleIcon,
    color: 'text-olive-500',
    bgColor: 'bg-olive-100 dark:bg-olive-900/30',
    label: 'Validation Passed',
    selectedBorder: 'border-olive-500 dark:border-olive-400',
  },
  validation_failed: {
    icon: XCircleIcon,
    color: 'text-critical-500',
    bgColor: 'bg-critical-100 dark:bg-critical-900/30',
    label: 'Validation Failed',
    selectedBorder: 'border-critical-500 dark:border-critical-400',
  },
  validation_warning: {
    icon: ExclamationTriangleIcon,
    color: 'text-warning-500',
    bgColor: 'bg-warning-100 dark:bg-warning-900/30',
    label: 'Validation Warning',
    selectedBorder: 'border-warning-500 dark:border-warning-400',
  },
  drift_detected: {
    icon: ExclamationTriangleIcon,
    color: 'text-warning-500',
    bgColor: 'bg-warning-100 dark:bg-warning-900/30',
    label: 'Drift Detected',
    selectedBorder: 'border-warning-500 dark:border-warning-400',
  },
  drift_scan: {
    icon: ArrowPathIcon,
    color: 'text-aura-500',
    bgColor: 'bg-aura-100 dark:bg-aura-900/30',
    label: 'Drift Scan',
    selectedBorder: 'border-aura-500 dark:border-aura-400',
  },
  baseline_saved: {
    icon: ShieldCheckIcon,
    color: 'text-olive-500',
    bgColor: 'bg-olive-100 dark:bg-olive-900/30',
    label: 'Baseline Saved',
    selectedBorder: 'border-olive-500 dark:border-olive-400',
  },
  remediation_attempted: {
    icon: WrenchScrewdriverIcon,
    color: 'text-aura-500',
    bgColor: 'bg-aura-100 dark:bg-aura-900/30',
    label: 'Remediation Attempted',
    selectedBorder: 'border-aura-500 dark:border-aura-400',
  },
  remediation_success: {
    icon: CheckCircleIcon,
    color: 'text-olive-500',
    bgColor: 'bg-olive-100 dark:bg-olive-900/30',
    label: 'Remediation Success',
    selectedBorder: 'border-olive-500 dark:border-olive-400',
  },
  remediation_failed: {
    icon: XCircleIcon,
    color: 'text-critical-500',
    bgColor: 'bg-critical-100 dark:bg-critical-900/30',
    label: 'Remediation Failed',
    selectedBorder: 'border-critical-500 dark:border-critical-400',
  },
};

// Mock activity data - replace with WebSocket or polling
const MOCK_ACTIVITIES = [
  {
    id: 'act-001',
    type: 'validation_passed',
    timestamp: new Date(Date.now() - 30000).toISOString(),
    environment: 'qa',
    details: 'Pre-deploy validation for aura-api-config',
    resources: 15,
    metadata: { run_id: 'run-001' },
  },
  {
    id: 'act-002',
    type: 'drift_detected',
    timestamp: new Date(Date.now() - 2 * 60000).toISOString(),
    environment: 'dev',
    details: 'Configuration drift in ConfigMap/aura-api-config',
    resources: 1,
    metadata: { field: 'data.ENVIRONMENT', severity: 'warning' },
  },
  {
    id: 'act-003',
    type: 'validation_started',
    timestamp: new Date(Date.now() - 5 * 60000).toISOString(),
    environment: 'qa',
    details: 'Manual validation triggered by user',
    resources: 22,
    metadata: { trigger: 'manual', user: 'admin@aenealabs.com' },
  },
  {
    id: 'act-004',
    type: 'validation_failed',
    timestamp: new Date(Date.now() - 8 * 60000).toISOString(),
    environment: 'dev',
    details: 'Found 2 critical violations in Deployment/aura-api',
    resources: 22,
    metadata: { violations: 2, warnings: 1 },
  },
  {
    id: 'act-005',
    type: 'baseline_saved',
    timestamp: new Date(Date.now() - 15 * 60000).toISOString(),
    environment: 'qa',
    details: 'Baseline updated for ConfigMap/aura-api-config',
    resources: 1,
    metadata: { created_by: 'ci-pipeline' },
  },
  {
    id: 'act-006',
    type: 'drift_scan',
    timestamp: new Date(Date.now() - 30 * 60000).toISOString(),
    environment: 'prod',
    details: 'Scheduled drift scan completed',
    resources: 45,
    metadata: { drift_found: false },
  },
];

function formatRelativeTime(timestamp) {
  const now = new Date();
  const time = new Date(timestamp);
  const diff = now - time;

  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);

  if (seconds < 60) return `${seconds}s ago`;
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  return time.toLocaleDateString();
}

function ActivityItem({ activity, isNew, isSelected, onClick }) {
  const config = ACTIVITY_TYPES[activity.type] || ACTIVITY_TYPES.validation_started;
  const Icon = config.icon;

  return (
    <button
      type="button"
      onClick={onClick}
      className={`
        w-full text-left p-3 rounded-xl border-2 transition-all duration-200
        ${isSelected
          ? `${config.selectedBorder} bg-white dark:bg-surface-800 shadow-lg`
          : 'border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 hover:border-surface-300 dark:hover:border-surface-600 hover:shadow-md'
        }
        ${isNew ? 'ring-2 ring-aura-500/30 ring-offset-1 dark:ring-offset-surface-900' : ''}
      `}
    >
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div className={`p-2 rounded-lg ${config.bgColor} flex-shrink-0`}>
          <Icon className={`w-4 h-4 ${config.color}`} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 mb-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-surface-900 dark:text-surface-100">
                {config.label}
              </span>
              <span className="text-xs px-1.5 py-0.5 rounded-md bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-400 font-medium tracking-wide">
                {activity.environment.toUpperCase()}
              </span>
            </div>
            <span className="text-xs text-surface-400 dark:text-surface-500 flex-shrink-0">
              {formatRelativeTime(activity.timestamp)}
            </span>
          </div>
          <p className="text-sm text-surface-600 dark:text-surface-400 line-clamp-2">
            {activity.details}
          </p>
          {/* Metadata badges */}
          {activity.metadata && (
            <div className="mt-2 flex items-center gap-2 flex-wrap">
              {activity.metadata.violations !== undefined && activity.metadata.violations > 0 && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-critical-100 dark:bg-critical-900/30 text-critical-700 dark:text-critical-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-critical-500" />
                  {activity.metadata.violations} violation{activity.metadata.violations !== 1 ? 's' : ''}
                </span>
              )}
              {activity.metadata.warnings !== undefined && activity.metadata.warnings > 0 && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-warning-100 dark:bg-warning-900/30 text-warning-700 dark:text-warning-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-warning-500" />
                  {activity.metadata.warnings} warning{activity.metadata.warnings !== 1 ? 's' : ''}
                </span>
              )}
              {activity.metadata.trigger && (
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-400">
                  {activity.metadata.trigger}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </button>
  );
}

export default function AgentActivityFeed({
  activities = MOCK_ACTIVITIES,
  maxItems = 20,
  autoScroll = true,
  loading = false,
  onSelectActivity,
  filterEnv = null,
}) {
  const [isPaused, setIsPaused] = useState(false);
  const [newActivityIds, setNewActivityIds] = useState(new Set());
  const [selectedActivityId, setSelectedActivityId] = useState(null);
  const scrollRef = useRef(null);

  // Filter activities by environment if specified
  const filteredActivities = filterEnv
    ? activities.filter((a) => a.environment === filterEnv)
    : activities;

  // Handle activity selection
  const handleSelectActivity = (activity) => {
    setSelectedActivityId(activity.id === selectedActivityId ? null : activity.id);
    onSelectActivity?.(activity);
  };

  // Handle new activities animation
  useEffect(() => {
    if (activities.length > 0) {
      const latestId = activities[0].id;
      setNewActivityIds((prev) => new Set([...prev, latestId]));

      // Clear the "new" state after animation
      const timer = setTimeout(() => {
        setNewActivityIds((prev) => {
          const next = new Set(prev);
          next.delete(latestId);
          return next;
        });
      }, 2000);

      return () => clearTimeout(timer);
    }
  }, [activities[0]?.id]);

  // Auto-scroll to top when new activity arrives
  useEffect(() => {
    if (autoScroll && !isPaused && scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [activities, autoScroll, isPaused]);

  if (loading) {
    return (
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 shadow-card">
        <div className="p-4 border-b border-surface-200 dark:border-surface-700">
          <div className="h-5 bg-surface-200 dark:bg-surface-700 rounded w-1/3" />
        </div>
        <div className="p-2 animate-pulse space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="flex items-start gap-3 p-3">
              <div className="w-8 h-8 bg-surface-200 dark:bg-surface-700 rounded-lg" />
              <div className="flex-1 space-y-2">
                <div className="h-3 bg-surface-200 dark:bg-surface-700 rounded w-1/4" />
                <div className="h-3 bg-surface-200 dark:bg-surface-700 rounded w-3/4" />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  const displayActivities = filteredActivities.slice(0, maxItems);

  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 shadow-card flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center gap-2">
          <BoltIcon className="w-4 h-4 text-aura-500" />
          <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100">
            Agent Activity
          </h3>
          <span className="flex items-center gap-1 text-xs text-olive-600 dark:text-olive-400">
            <span className="w-2 h-2 rounded-full bg-olive-500 animate-pulse" />
            Live
          </span>
        </div>

        <button
          type="button"
          onClick={() => setIsPaused(!isPaused)}
          className="p-1.5 rounded-md hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
          title={isPaused ? 'Resume auto-scroll' : 'Pause auto-scroll'}
        >
          {isPaused ? (
            <PlayIcon className="w-4 h-4 text-surface-500" />
          ) : (
            <PauseIcon className="w-4 h-4 text-surface-500" />
          )}
        </button>
      </div>

      {/* Activity list */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-2"
        onMouseEnter={() => autoScroll && setIsPaused(true)}
        onMouseLeave={() => autoScroll && setIsPaused(false)}
      >
        {displayActivities.length === 0 ? (
          <div className="text-center py-8 text-surface-500 dark:text-surface-400">
            <BoltIcon className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No recent activity</p>
          </div>
        ) : (
          <div className="space-y-2">
            {displayActivities.map((activity) => (
              <ActivityItem
                key={activity.id}
                activity={activity}
                isNew={newActivityIds.has(activity.id)}
                isSelected={activity.id === selectedActivityId}
                onClick={() => handleSelectActivity(activity)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      {filteredActivities.length > maxItems && (
        <div className="p-2 border-t border-surface-200 dark:border-surface-700 text-center">
          <button
            type="button"
            className="text-xs text-aura-600 dark:text-aura-400 hover:underline"
          >
            View all {filteredActivities.length} activities
          </button>
        </div>
      )}
    </div>
  );
}
