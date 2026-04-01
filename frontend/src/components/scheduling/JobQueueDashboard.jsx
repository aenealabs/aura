/**
 * Job Queue Dashboard Component
 *
 * Displays real-time queue status and metrics.
 * ADR-055: Agent Scheduling View and Job Queue Management
 */

import {
  QueueListIcon,
  ClockIcon,
  BoltIcon,
  CalendarIcon,
  ChartBarIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';
import MetricCard, { MetricCardGrid } from '../ui/MetricCard';
import { formatDuration, formatRelativeTime, getPriorityColor } from '../../services/schedulingApi';

function PriorityBreakdown({ byPriority }) {
  const priorities = ['CRITICAL', 'HIGH', 'NORMAL', 'LOW'];
  const total = Object.values(byPriority || {}).reduce((sum, v) => sum + v, 0);

  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-5">
      <h3 className="text-sm font-medium text-surface-900 dark:text-surface-100 mb-4">
        Queue by Priority
      </h3>
      <div className="space-y-3">
        {priorities.map((priority) => {
          const count = byPriority?.[priority] || 0;
          const percentage = total > 0 ? (count / total) * 100 : 0;
          const color = getPriorityColor(priority);

          const barColors = {
            critical: 'bg-critical-500',
            warning: 'bg-warning-500',
            info: 'bg-aura-500',
            surface: 'bg-surface-400',
          };

          return (
            <div key={priority}>
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="text-surface-600 dark:text-surface-400">{priority}</span>
                <span className="font-medium text-surface-900 dark:text-surface-100">{count}</span>
              </div>
              <div className="h-2 bg-surface-100 dark:bg-surface-700 rounded-full overflow-hidden">
                <div
                  className={`h-full ${barColors[color]} transition-all duration-300`}
                  style={{ width: `${percentage}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function JobTypeBreakdown({ byType }) {
  const entries = Object.entries(byType || {}).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((sum, [, count]) => sum + count, 0);

  if (entries.length === 0) {
    return (
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-5">
        <h3 className="text-sm font-medium text-surface-900 dark:text-surface-100 mb-4">
          Queue by Job Type
        </h3>
        <p className="text-sm text-surface-500 dark:text-surface-400">No jobs in queue</p>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-5">
      <h3 className="text-sm font-medium text-surface-900 dark:text-surface-100 mb-4">
        Queue by Job Type
      </h3>
      <div className="space-y-2">
        {entries.map(([type, count]) => {
          const percentage = total > 0 ? (count / total) * 100 : 0;

          return (
            <div key={type} className="flex items-center gap-3">
              <div className="flex-1">
                <div className="flex items-center justify-between text-sm mb-1">
                  <span className="text-surface-600 dark:text-surface-400 truncate">
                    {type.replace(/_/g, ' ')}
                  </span>
                  <span className="font-medium text-surface-900 dark:text-surface-100 ml-2">
                    {count}
                  </span>
                </div>
                <div className="h-1.5 bg-surface-100 dark:bg-surface-700 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-aura-500 transition-all duration-300"
                    style={{ width: `${percentage}%` }}
                  />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function QueueHealthIndicator({ queueStatus }) {
  const { total_queued, active_jobs, avg_wait_time_seconds, by_priority } = queueStatus || {};
  const criticalJobs = by_priority?.CRITICAL || 0;

  // Enhanced health calculation with multiple conditions
  let health = 'good';
  let healthColor = 'olive';
  let healthMessage = 'Queue is operating normally';

  // Warning conditions (checked first, can be overridden by critical)
  if (avg_wait_time_seconds > 120) {
    health = 'warning';
    healthColor = 'warning';
    healthMessage = 'Average wait time exceeds 2 minutes';
  } else if (total_queued > 25) {
    health = 'warning';
    healthColor = 'warning';
    healthMessage = 'Queue depth above normal threshold';
  } else if (criticalJobs > 0 && active_jobs === 0) {
    health = 'warning';
    healthColor = 'warning';
    healthMessage = 'Critical jobs waiting with no active workers';
  }

  // Critical conditions (highest priority)
  if (avg_wait_time_seconds > 300) {
    health = 'critical';
    healthColor = 'critical';
    healthMessage = 'Jobs waiting longer than 5 minutes';
  } else if (total_queued > 50 && active_jobs < 3) {
    health = 'critical';
    healthColor = 'critical';
    healthMessage = 'Queue backlog detected - insufficient workers';
  } else if (criticalJobs > 5) {
    health = 'critical';
    healthColor = 'critical';
    healthMessage = `${criticalJobs} critical priority jobs in queue`;
  }

  // Toast-style configuration matching the app's toast notifications
  const statusConfig = {
    olive: {
      containerClass: 'bg-olive-100 dark:bg-olive-900 border-l-4 border-l-olive-500 border-y border-r border-olive-300 dark:border-olive-700',
      iconClass: 'text-olive-600 dark:text-olive-300',
      titleClass: 'text-olive-800 dark:text-olive-100',
      messageClass: 'text-olive-700 dark:text-olive-200',
      title: 'Good',
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      ),
    },
    warning: {
      containerClass: 'bg-warning-100 dark:bg-warning-900 border-l-4 border-l-warning-500 border-y border-r border-warning-300 dark:border-warning-700',
      iconClass: 'text-warning-600 dark:text-warning-300',
      titleClass: 'text-warning-800 dark:text-warning-100',
      messageClass: 'text-warning-700 dark:text-warning-200',
      title: 'Warning',
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      ),
    },
    critical: {
      containerClass: 'bg-critical-100 dark:bg-critical-900 border-l-4 border-l-critical-500 border-y border-r border-critical-300 dark:border-critical-700',
      iconClass: 'text-critical-600 dark:text-critical-300',
      titleClass: 'text-critical-800 dark:text-critical-100',
      messageClass: 'text-critical-700 dark:text-critical-200',
      title: 'Critical',
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
  };

  const config = statusConfig[healthColor];

  return (
    <div className={`inline-flex items-start gap-3 rounded-lg px-4 py-3 ${config.containerClass}`}>
      <div className={`flex-shrink-0 ${config.iconClass}`}>
        {config.icon}
      </div>
      <div className="flex-1 min-w-0">
        <p className={`text-sm font-semibold ${config.titleClass}`}>
          Queue Health: {config.title}
        </p>
        <p className={`text-sm ${config.messageClass}`}>
          {healthMessage}
        </p>
      </div>
    </div>
  );
}

export default function JobQueueDashboard({ queueStatus, loading }) {
  if (loading && !queueStatus) {
    return (
      <div className="space-y-6">
        {/* Loading skeleton */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div
              key={i}
              className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-5 animate-pulse"
            >
              <div className="h-4 bg-surface-200 dark:bg-surface-700 rounded w-24 mb-3" />
              <div className="h-8 bg-surface-200 dark:bg-surface-700 rounded w-16" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!queueStatus) {
    return (
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-8 text-center">
        <ExclamationTriangleIcon className="w-12 h-12 text-surface-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-surface-900 dark:text-surface-100 mb-2">
          Unable to Load Queue Status
        </h3>
        <p className="text-sm text-surface-500 dark:text-surface-400">
          Please try refreshing the page
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Health Indicator */}
      <QueueHealthIndicator queueStatus={queueStatus} />

      {/* Metric Cards */}
      <MetricCardGrid columns={4}>
        <MetricCard
          icon={QueueListIcon}
          title="Queued Jobs"
          value={queueStatus.total_queued}
          subtitle={queueStatus.oldest_queued_at ? `Oldest: ${formatRelativeTime(queueStatus.oldest_queued_at)}` : null}
          iconColor={queueStatus.total_queued > 20 ? 'warning' : 'aura'}
        />
        <MetricCard
          icon={BoltIcon}
          title="Active Jobs"
          value={queueStatus.active_jobs}
          subtitle="Currently running"
          iconColor="warning"
        />
        <MetricCard
          icon={CalendarIcon}
          title="Scheduled"
          value={queueStatus.total_scheduled}
          subtitle={queueStatus.next_scheduled_at ? `Next: ${formatRelativeTime(queueStatus.next_scheduled_at)}` : 'None scheduled'}
          iconColor="aura"
        />
        <MetricCard
          icon={ClockIcon}
          title="Avg Wait Time"
          value={formatDuration(queueStatus.avg_wait_time_seconds)}
          subtitle={`${queueStatus.throughput_per_hour?.toFixed(1) || 0} jobs/hr throughput`}
          iconColor={queueStatus.avg_wait_time_seconds > 120 ? 'warning' : 'aura'}
        />
      </MetricCardGrid>

      {/* Breakdowns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PriorityBreakdown byPriority={queueStatus.by_priority} />
        <JobTypeBreakdown byType={queueStatus.by_type} />
      </div>

      {/* Quick Stats */}
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-5">
        <h3 className="text-sm font-medium text-surface-900 dark:text-surface-100 mb-4 flex items-center gap-2">
          <ChartBarIcon className="w-4 h-4" />
          Queue Summary
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
          <div>
            <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">
              {queueStatus.total_queued + queueStatus.active_jobs}
            </p>
            <p className="text-xs text-surface-500 dark:text-surface-400">Total In System</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-critical-600 dark:text-critical-400">
              {queueStatus.by_priority?.CRITICAL || 0}
            </p>
            <p className="text-xs text-surface-500 dark:text-surface-400">Critical Priority</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-warning-600 dark:text-warning-400">
              {queueStatus.by_priority?.HIGH || 0}
            </p>
            <p className="text-xs text-surface-500 dark:text-surface-400">High Priority</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-aura-600 dark:text-aura-400">
              {queueStatus.total_scheduled}
            </p>
            <p className="text-xs text-surface-500 dark:text-surface-400">Scheduled</p>
          </div>
        </div>
      </div>
    </div>
  );
}
