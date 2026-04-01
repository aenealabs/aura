/**
 * Project Aura - GPU Job Error State Component
 *
 * Displays error states for GPU jobs (OOM, Spot interruption, timeout, etc.)
 * with appropriate styling and recovery actions.
 * ADR-061: GPU Workload Scheduler - Phase 3 Frontend Integration
 */

import { memo } from 'react';
import {
  ExclamationCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  StopCircleIcon,
  ArrowPathIcon,
  CogIcon,
  CurrencyDollarIcon,
  ClockIcon,
  ServerIcon,
  CloudIcon,
} from '@heroicons/react/24/outline';
import { GPU_ERROR_TYPES, getErrorTypeInfo, formatCost } from '../../services/gpuSchedulerApi';

/**
 * Error icon based on error type
 */
const ErrorIcon = memo(function ErrorIcon({ errorType, className = 'w-6 h-6' }) {
  const iconMap = {
    oom: ExclamationCircleIcon,
    spot_interruption: CloudIcon,
    timeout: ClockIcon,
    config_error: CogIcon,
    network_error: ServerIcon,
    quota_exceeded: CurrencyDollarIcon,
  };

  const Icon = iconMap[errorType] || ExclamationCircleIcon;
  return <Icon className={className} />;
});

/**
 * Error severity badge
 */
const SeverityBadge = memo(function SeverityBadge({ severity }) {
  const classes = {
    high: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
    medium: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    low: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  };

  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${classes[severity] || classes.medium}`}>
      {severity?.toUpperCase()}
    </span>
  );
});

/**
 * Individual error card for job detail view
 */
export const GPUJobErrorCard = memo(function GPUJobErrorCard({
  job,
  onRetry,
  onViewLogs,
  onAdjustConfig,
  className = '',
}) {
  const errorInfo = getErrorTypeInfo(job.error_type);

  if (!errorInfo) {
    return (
      <div className={`bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800 rounded-lg p-4 ${className}`}>
        <div className="flex items-start gap-3">
          <ExclamationCircleIcon className="w-5 h-5 text-critical-500 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <h4 className="font-medium text-critical-700 dark:text-critical-300">Job Failed</h4>
            <p className="text-sm text-critical-600 dark:text-critical-400 mt-1">
              {job.error_message || 'An unknown error occurred'}
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`${errorInfo.bgColor} border border-surface-200 dark:border-surface-700 rounded-xl p-5 ${className}`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${errorInfo.bgColor}`}>
            <ErrorIcon errorType={job.error_type} className={`w-6 h-6 ${errorInfo.textColor}`} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className={`font-semibold ${errorInfo.textColor}`}>{errorInfo.label}</h3>
              <SeverityBadge severity={errorInfo.severity} />
            </div>
            <p className="text-sm text-surface-600 dark:text-surface-400 mt-0.5">
              {errorInfo.description}
            </p>
          </div>
        </div>
      </div>

      {/* Error message */}
      {job.error_message && (
        <div className="mb-4 p-3 bg-white/50 dark:bg-surface-800/50 rounded-lg">
          <p className="text-sm text-surface-700 dark:text-surface-300 font-mono">
            {job.error_message}
          </p>
        </div>
      )}

      {/* Recommended action */}
      <div className="flex items-start gap-2 mb-4">
        <InformationCircleIcon className="w-4 h-4 text-surface-500 flex-shrink-0 mt-0.5" />
        <p className="text-sm text-surface-600 dark:text-surface-400">
          <span className="font-medium">Recommended action:</span> {errorInfo.action}
        </p>
      </div>

      {/* Job details */}
      <div className="grid grid-cols-2 gap-3 mb-4 text-sm">
        <div>
          <span className="text-surface-500 dark:text-surface-400">Job ID:</span>
          <span className="ml-2 text-surface-700 dark:text-surface-300 font-mono">{job.job_id}</span>
        </div>
        <div>
          <span className="text-surface-500 dark:text-surface-400">Duration:</span>
          <span className="ml-2 text-surface-700 dark:text-surface-300">
            {job.started_at && job.completed_at
              ? `${Math.round((new Date(job.completed_at) - new Date(job.started_at)) / 60000)} min`
              : '-'}
          </span>
        </div>
        <div>
          <span className="text-surface-500 dark:text-surface-400">Cost:</span>
          <span className="ml-2 text-surface-700 dark:text-surface-300">{formatCost(job.cost_usd)}</span>
        </div>
        <div>
          <span className="text-surface-500 dark:text-surface-400">Progress:</span>
          <span className="ml-2 text-surface-700 dark:text-surface-300">
            {job.progress_percent !== null ? `${job.progress_percent}%` : '-'}
          </span>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3 pt-3 border-t border-surface-200 dark:border-surface-700">
        {job.error_type === 'oom' && onAdjustConfig && (
          <button
            onClick={() => onAdjustConfig(job.job_id)}
            className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-aura-600 dark:text-aura-400 hover:bg-aura-50 dark:hover:bg-aura-900/20 rounded-lg transition-colors"
          >
            <CogIcon className="w-4 h-4" />
            Increase Memory & Retry
          </button>
        )}
        {(job.error_type === 'spot_interruption' || job.checkpoint_enabled) && onRetry && (
          <button
            onClick={() => onRetry(job.job_id)}
            className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-aura-600 dark:text-aura-400 hover:bg-aura-50 dark:hover:bg-aura-900/20 rounded-lg transition-colors"
          >
            <ArrowPathIcon className="w-4 h-4" />
            Retry from Checkpoint
          </button>
        )}
        {onRetry && job.error_type !== 'spot_interruption' && !job.checkpoint_enabled && (
          <button
            onClick={() => onRetry(job.job_id)}
            className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-aura-600 dark:text-aura-400 hover:bg-aura-50 dark:hover:bg-aura-900/20 rounded-lg transition-colors"
          >
            <ArrowPathIcon className="w-4 h-4" />
            Retry Job
          </button>
        )}
        {onViewLogs && (
          <button
            onClick={() => onViewLogs(job.job_id)}
            className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
          >
            View Logs
          </button>
        )}
      </div>
    </div>
  );
});

/**
 * Compact error indicator for job list view
 */
export const GPUJobErrorIndicator = memo(function GPUJobErrorIndicator({ errorType, errorMessage }) {
  const errorInfo = getErrorTypeInfo(errorType);

  if (!errorInfo) {
    return (
      <div className="flex items-center gap-1.5 text-critical-600 dark:text-critical-400">
        <ExclamationCircleIcon className="w-4 h-4" />
        <span className="text-sm">Failed</span>
      </div>
    );
  }

  return (
    <div className={`flex items-center gap-1.5 ${errorInfo.textColor}`} title={errorMessage}>
      <ErrorIcon errorType={errorType} className="w-4 h-4" />
      <span className="text-sm">{errorInfo.label}</span>
    </div>
  );
});

/**
 * Error summary panel for queue overview
 */
export const GPUJobErrorSummary = memo(function GPUJobErrorSummary({
  failedJobs,
  onViewJob,
  className = '',
}) {
  if (!failedJobs || failedJobs.length === 0) {
    return null;
  }

  // Group by error type
  const errorGroups = failedJobs.reduce((acc, job) => {
    const type = job.error_type || 'unknown';
    if (!acc[type]) {
      acc[type] = [];
    }
    acc[type].push(job);
    return acc;
  }, {});

  return (
    <div className={`bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 ${className}`}>
      <div className="flex items-center gap-2 mb-3">
        <ExclamationTriangleIcon className="w-5 h-5 text-warning-500" />
        <h3 className="font-medium text-surface-900 dark:text-surface-100">
          Failed Jobs ({failedJobs.length})
        </h3>
      </div>

      <div className="space-y-2">
        {Object.entries(errorGroups).map(([errorType, jobs]) => {
          const errorInfo = getErrorTypeInfo(errorType);
          return (
            <div
              key={errorType}
              className="flex items-center justify-between py-2 px-3 bg-surface-50 dark:bg-surface-700/50 rounded-lg"
            >
              <div className="flex items-center gap-2">
                <ErrorIcon errorType={errorType} className={`w-4 h-4 ${errorInfo?.textColor || 'text-critical-500'}`} />
                <span className="text-sm text-surface-700 dark:text-surface-300">
                  {errorInfo?.label || 'Unknown Error'}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-surface-500 dark:text-surface-400">
                  {jobs.length} job{jobs.length > 1 ? 's' : ''}
                </span>
                <button
                  onClick={() => onViewJob(jobs[0].job_id)}
                  className="text-xs text-aura-600 dark:text-aura-400 hover:underline"
                >
                  View
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
});

/**
 * Spot interruption notice banner
 */
export const SpotInterruptionBanner = memo(function SpotInterruptionBanner({
  job,
  onDismiss,
  className = '',
}) {
  return (
    <div
      className={`flex items-start gap-3 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg ${className}`}
      role="alert"
    >
      <CloudIcon className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
      <div className="flex-1">
        <h4 className="font-medium text-blue-700 dark:text-blue-300">
          Spot Instance Interrupted
        </h4>
        <p className="text-sm text-blue-600 dark:text-blue-400 mt-1">
          Job &quot;{job.job_id}&quot; was interrupted due to AWS Spot capacity reclamation.
          {job.checkpoint_enabled && ' Progress was saved and the job will be automatically re-queued.'}
        </p>
        {job.checkpoint_s3_path && (
          <p className="text-xs text-blue-500 dark:text-blue-500 mt-2 font-mono">
            Checkpoint: {job.checkpoint_s3_path}
          </p>
        )}
      </div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="text-blue-400 hover:text-blue-600 dark:hover:text-blue-300"
          aria-label="Dismiss"
        >
          ×
        </button>
      )}
    </div>
  );
});

/**
 * Quota exceeded error state
 */
export const QuotaExceededError = memo(function QuotaExceededError({
  budgetUsed,
  budgetTotal,
  onRequestIncrease,
  className = '',
}) {
  const percentUsed = (budgetUsed / budgetTotal) * 100;

  return (
    <div className={`bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800 rounded-xl p-5 ${className}`}>
      <div className="flex items-start gap-3 mb-4">
        <div className="p-2 rounded-lg bg-critical-100 dark:bg-critical-900/30">
          <StopCircleIcon className="w-6 h-6 text-critical-600 dark:text-critical-400" />
        </div>
        <div>
          <h3 className="font-semibold text-critical-700 dark:text-critical-300">
            GPU Budget Exceeded
          </h3>
          <p className="text-sm text-critical-600 dark:text-critical-400 mt-0.5">
            You have reached your monthly GPU compute budget
          </p>
        </div>
      </div>

      {/* Budget progress bar */}
      <div className="mb-4">
        <div className="flex items-center justify-between text-sm mb-1">
          <span className="text-surface-600 dark:text-surface-400">Budget Usage</span>
          <span className="text-surface-700 dark:text-surface-300">
            {formatCost(budgetUsed)} / {formatCost(budgetTotal)} ({percentUsed.toFixed(0)}%)
          </span>
        </div>
        <div className="h-2 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-critical-500 rounded-full"
            style={{ width: `${Math.min(100, percentUsed)}%` }}
          />
        </div>
      </div>

      {/* Action */}
      {onRequestIncrease && (
        <button
          onClick={onRequestIncrease}
          className="w-full flex items-center justify-center gap-2 py-2 px-4 bg-critical-600 hover:bg-critical-700 text-white rounded-lg font-medium transition-colors"
        >
          <CurrencyDollarIcon className="w-4 h-4" />
          Request Budget Increase
        </button>
      )}
    </div>
  );
});

// Default export for the main error card
export default GPUJobErrorCard;
