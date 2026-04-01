/**
 * Usage Metrics Component
 *
 * Displays usage statistics with progress bars for license limits.
 */

import {
  FolderIcon,
  UsersIcon,
  CpuChipIcon,
  CloudArrowUpIcon,
  CircleStackIcon,
  ClockIcon,
} from '@heroicons/react/24/outline';

const METRIC_CONFIG = {
  repositories: {
    label: 'Repositories',
    icon: FolderIcon,
    format: (value) => value.toLocaleString(),
  },
  users: {
    label: 'Users',
    icon: UsersIcon,
    format: (value) => value.toLocaleString(),
  },
  agents: {
    label: 'Active Agents',
    icon: CpuChipIcon,
    format: (value) => value.toLocaleString(),
  },
  api_calls: {
    label: 'API Calls',
    icon: CloudArrowUpIcon,
    format: (value) => {
      if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
      if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
      return value.toLocaleString();
    },
  },
  storage_gb: {
    label: 'Storage',
    icon: CircleStackIcon,
    format: (value) => `${value} GB`,
  },
  agent_hours: {
    label: 'Agent Hours',
    icon: ClockIcon,
    format: (value) => value.toLocaleString(),
  },
};

function getProgressColor(percentage) {
  if (percentage >= 90) return 'bg-critical-500 dark:bg-critical-400';
  if (percentage >= 75) return 'bg-warning-500 dark:bg-warning-400';
  return 'bg-aura-500 dark:bg-aura-400';
}

function MetricCard({ metricKey, used, limit }) {
  const config = METRIC_CONFIG[metricKey];
  if (!config) return null;

  const Icon = config.icon;
  const percentage = limit > 0 ? Math.round((used / limit) * 100) : 0;
  const isNearLimit = percentage >= 75;

  return (
    <div
      className={`
        bg-surface-50 dark:bg-surface-800
        backdrop-blur-sm
        rounded-xl p-4
        border border-surface-200/30 dark:border-surface-700/20
        ${isNearLimit ? 'ring-1 ring-warning-500/50' : ''}
      `}
    >
      <div className="flex items-center gap-2 mb-3">
        <Icon className="h-5 w-5 text-surface-400 dark:text-surface-500" />
        <span className="text-sm font-medium text-surface-600 dark:text-surface-400">
          {config.label}
        </span>
      </div>

      <div className="text-2xl font-bold text-surface-900 dark:text-surface-100 mb-2">
        {config.format(used)}
        <span className="text-sm font-normal text-surface-400 dark:text-surface-500">
          {' / '}{config.format(limit)}
        </span>
      </div>

      <div className="space-y-1">
        <div className="flex justify-between text-xs text-surface-500 dark:text-surface-400">
          <span>{percentage}% used</span>
          {isNearLimit && (
            <span className="text-warning-600 dark:text-warning-400 font-medium">
              Near limit
            </span>
          )}
        </div>
        <div className="h-2 bg-surface-200/50 dark:bg-surface-700/50 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${getProgressColor(percentage)}`}
            style={{ width: `${Math.min(percentage, 100)}%` }}
            role="progressbar"
            aria-valuenow={used}
            aria-valuemin={0}
            aria-valuemax={limit}
            aria-label={`${config.label}: ${used} of ${limit} used`}
          />
        </div>
      </div>
    </div>
  );
}

export default function UsageMetrics({ metrics, onViewDetails }) {
  if (!metrics) {
    return (
      <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
            Usage Overview
          </h3>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div
              key={i}
              className="bg-surface-100 dark:bg-surface-700/30 rounded-xl p-4 animate-pulse"
            >
              <div className="h-4 w-24 bg-surface-200 dark:bg-surface-600 rounded mb-3" />
              <div className="h-8 w-32 bg-surface-200 dark:bg-surface-600 rounded mb-2" />
              <div className="h-2 bg-surface-200 dark:bg-surface-600 rounded-full" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  const metricKeys = Object.keys(metrics).filter((key) => METRIC_CONFIG[key]);

  return (
    <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
          Usage Overview
        </h3>
        {onViewDetails && (
          <button
            onClick={onViewDetails}
            className="text-sm text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300 font-medium"
          >
            View Details
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {metricKeys.map((key) => (
          <MetricCard
            key={key}
            metricKey={key}
            used={metrics[key].used}
            limit={metrics[key].limit}
          />
        ))}
      </div>
    </div>
  );
}
