/**
 * Project Aura - GPU Workloads Panel
 *
 * Main panel component for GPU workload management with job lists,
 * resource metrics, and queue status.
 * ADR-061: GPU Workload Scheduler - Phase 3 Frontend Integration
 */

import { memo, useState, useCallback } from 'react';
import {
  CpuChipIcon,
  QueueListIcon,
  CurrencyDollarIcon,
  ClockIcon,
  PlayIcon,
  StopIcon,
  ArrowUpIcon,
  XMarkIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  PlusIcon,
  ArrowPathIcon,
  InformationCircleIcon,
  Cog6ToothIcon,
  QuestionMarkCircleIcon,
  ExclamationCircleIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  BoltIcon,
} from '@heroicons/react/24/outline';
import { CpuChipIcon as CpuChipIconSolid } from '@heroicons/react/24/solid';
import MetricCard, { MetricCardGrid } from '../ui/MetricCard';
import { useGPUWorkloads } from '../../context/GPUWorkloadsContext';
import {
  formatGPUMemory,
  formatCost,
  formatDuration,
  getGPUStatusColor,
  getGPUPriorityColor,
  getJobTypeInfo,
  getErrorTypeInfo,
} from '../../services/gpuSchedulerApi';
import GPUJobEmptyState from './GPUJobEmptyState';
import GPUJobLoadingSkeleton from './GPUJobLoadingSkeleton';

/**
 * Status badge component
 */
const StatusBadge = memo(function StatusBadge({ status }) {
  const color = getGPUStatusColor(status);
  const colorClasses = {
    aura: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
    success: 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400',
    warning: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    critical: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
    info: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
    surface: 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-300',
  };

  const statusLabels = {
    queued: 'Queued',
    starting: 'Starting',
    running: 'Running',
    completed: 'Completed',
    failed: 'Failed',
    cancelled: 'Cancelled',
  };

  return (
    <span
      className={`
        inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium
        ${colorClasses[color] || colorClasses.surface}
      `}
    >
      {statusLabels[status] || status}
    </span>
  );
});

/**
 * Priority badge component
 */
const PriorityBadge = memo(function PriorityBadge({ priority }) {
  const color = getGPUPriorityColor(priority);
  const colorClasses = {
    critical: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
    warning: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    info: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
    surface: 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-300',
  };

  return (
    <span
      className={`
        inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium capitalize
        ${colorClasses[color] || colorClasses.surface}
      `}
    >
      {priority}
    </span>
  );
});

/**
 * Progress bar component with ARIA accessibility
 */
const ProgressBar = memo(function ProgressBar({ progress, estimatedRemaining, jobType }) {
  const progressPercent = Math.min(100, Math.max(0, progress || 0));
  const jobInfo = getJobTypeInfo(jobType);
  const jobLabel = jobInfo?.label || jobType;

  return (
    <div className="w-full">
      <div
        role="progressbar"
        aria-valuenow={progressPercent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${jobLabel}: ${progressPercent}% complete${estimatedRemaining ? `, ~${estimatedRemaining} minutes remaining` : ''}`}
        className="h-2 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden"
      >
        <div
          className="h-full bg-aura-500 dark:bg-aura-400 rounded-full transition-all duration-300 ease-out"
          style={{ width: `${progressPercent}%` }}
        />
      </div>
    </div>
  );
});

/**
 * Active job card component
 */
const ActiveJobCard = memo(function ActiveJobCard({ job, onCancel, onViewLogs }) {
  const jobInfo = getJobTypeInfo(job.job_type);

  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 transition-all hover:shadow-md">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-lg bg-aura-100 dark:bg-aura-900/30">
            <BoltIcon className="w-4 h-4 text-aura-600 dark:text-aura-400" />
          </div>
          <div>
            <h4 className="font-medium text-surface-900 dark:text-surface-50">
              {jobInfo?.label || job.job_type}
            </h4>
            <p className="text-sm text-surface-500 dark:text-surface-400">
              {job.config?.repository_id || job.config?.dataset_id || job.config?.session_id || job.job_id}
            </p>
          </div>
        </div>
        <button
          onClick={() => onCancel(job.job_id)}
          className="px-3 py-1 text-sm text-critical-600 dark:text-critical-400 hover:bg-critical-50 dark:hover:bg-critical-900/20 rounded-md transition-colors"
          aria-label={`Cancel job ${job.job_id}`}
        >
          Cancel
        </button>
      </div>

      <div className="mb-2">
        <div className="flex items-center justify-between text-sm mb-1">
          <span className="text-surface-600 dark:text-surface-400">
            {job.progress_percent}% complete
          </span>
          {job.estimated_remaining_minutes !== null && (
            <span className="text-surface-500 dark:text-surface-400">
              ETA: {formatDuration(job.estimated_remaining_minutes)}
            </span>
          )}
        </div>
        <ProgressBar
          progress={job.progress_percent}
          estimatedRemaining={job.estimated_remaining_minutes}
          jobType={job.job_type}
        />
      </div>

      <div className="flex items-center justify-between text-xs text-surface-500 dark:text-surface-400">
        <span>Cost: {formatCost(job.cost_usd)}</span>
        <button
          onClick={() => onViewLogs(job.job_id)}
          className="text-aura-600 dark:text-aura-400 hover:underline"
        >
          View logs
        </button>
      </div>
    </div>
  );
});

/**
 * Queued job row component
 */
const QueuedJobRow = memo(function QueuedJobRow({ job, onCancel, onBoostPriority }) {
  const jobInfo = getJobTypeInfo(job.job_type);

  return (
    <div className="flex items-center justify-between py-3 px-4 hover:bg-surface-50 dark:hover:bg-surface-700/50 rounded-lg transition-colors">
      <div className="flex items-center gap-3 min-w-0 flex-1">
        <div className="w-2 h-2 rounded-full bg-warning-400 flex-shrink-0" />
        <div className="min-w-0 flex-1">
          <span className="font-medium text-surface-900 dark:text-surface-50 truncate block">
            {jobInfo?.label || job.job_type}
          </span>
          <span className="text-xs text-surface-500 dark:text-surface-400">
            {job.config?.repository_id || job.config?.dataset_id || job.config?.session_id}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <PriorityBadge priority={job.priority} />
        <span className="text-sm text-surface-500 dark:text-surface-400 whitespace-nowrap">
          Position: {job.queue_position}
        </span>
        <div className="flex items-center gap-1">
          {job.priority !== 'high' && (
            <button
              onClick={() => onBoostPriority(job.job_id)}
              className="p-1.5 text-surface-500 hover:text-aura-600 dark:hover:text-aura-400 hover:bg-surface-100 dark:hover:bg-surface-700 rounded transition-colors"
              title="Boost priority"
              aria-label={`Boost priority for ${job.job_id}`}
            >
              <ArrowUpIcon className="w-4 h-4" />
            </button>
          )}
          <button
            onClick={() => onCancel(job.job_id)}
            className="p-1.5 text-surface-500 hover:text-critical-600 dark:hover:text-critical-400 hover:bg-surface-100 dark:hover:bg-surface-700 rounded transition-colors"
            title="Cancel job"
            aria-label={`Cancel job ${job.job_id}`}
          >
            <XMarkIcon className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
});

/**
 * Recent job row component
 */
const RecentJobRow = memo(function RecentJobRow({ job, onClick }) {
  const jobInfo = getJobTypeInfo(job.job_type);
  const errorInfo = job.error_type ? getErrorTypeInfo(job.error_type) : null;

  const statusIcon = {
    completed: <CheckCircleIcon className="w-4 h-4 text-olive-500" />,
    failed: <ExclamationCircleIcon className="w-4 h-4 text-critical-500" />,
    cancelled: <XMarkIcon className="w-4 h-4 text-surface-400" />,
  };

  const formatTime = (dateString) => {
    if (!dateString) return '-';
    const date = new Date(dateString);
    const now = new Date();
    const diffHours = (now - date) / (1000 * 60 * 60);

    if (diffHours < 24) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    return 'Yesterday';
  };

  return (
    <button
      onClick={() => onClick(job.job_id)}
      className="flex items-center justify-between w-full py-2 px-3 hover:bg-surface-50 dark:hover:bg-surface-700/50 rounded-lg transition-colors text-left"
    >
      <div className="flex items-center gap-2 min-w-0 flex-1">
        {statusIcon[job.status]}
        <span
          className={`truncate ${job.status === 'failed' ? 'text-critical-600 dark:text-critical-400' : 'text-surface-700 dark:text-surface-300'}`}
        >
          {jobInfo?.label || job.job_type}
          {job.config?.repository_id && ` - ${job.config.repository_id}`}
          {job.status === 'failed' && errorInfo && ` (${errorInfo.label})`}
        </span>
      </div>
      <div className="flex items-center gap-3 text-sm text-surface-500 dark:text-surface-400">
        <span>{formatTime(job.completed_at)}</span>
        <span>{formatCost(job.cost_usd)}</span>
      </div>
    </button>
  );
});

/**
 * Collapsible section component
 */
const CollapsibleSection = memo(function CollapsibleSection({
  title,
  count,
  children,
  defaultExpanded = true,
}) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center justify-between w-full px-4 py-3 hover:bg-surface-50 dark:hover:bg-surface-700/50 transition-colors"
        aria-expanded={isExpanded}
      >
        <div className="flex items-center gap-2">
          <h3 className="font-medium text-surface-900 dark:text-surface-50">{title}</h3>
          {count !== undefined && (
            <span className="text-sm text-surface-500 dark:text-surface-400">({count})</span>
          )}
        </div>
        {isExpanded ? (
          <ChevronDownIcon className="w-5 h-5 text-surface-400" />
        ) : (
          <ChevronRightIcon className="w-5 h-5 text-surface-400" />
        )}
      </button>
      {isExpanded && <div className="border-t border-surface-200 dark:border-surface-700">{children}</div>}
    </div>
  );
});

/**
 * GPU scaling indicator component
 */
const GPUScalingIndicator = memo(function GPUScalingIndicator({ nodesScaling }) {
  if (nodesScaling <= 0) return null;

  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-aura-50 dark:bg-aura-900/20 rounded-lg text-sm text-aura-700 dark:text-aura-300">
      <div className="animate-spin">
        <ArrowPathIcon className="w-4 h-4" />
      </div>
      <span>Scaling up {nodesScaling} GPU node{nodesScaling > 1 ? 's' : ''}...</span>
    </div>
  );
});

/**
 * Main GPU Workloads Panel component
 */
function GPUWorkloadsPanel({ className = '' }) {
  const {
    activeJobs,
    queuedJobs,
    recentJobs,
    loading,
    error,
    resources,
    isEmpty,
    handleCancelJob,
    handleBoostPriority,
    fetchJobLogs,
    fetchJobDetail,
    openScheduleModal,
    refresh,
  } = useGPUWorkloads();

  const [viewingLogsJobId, setViewingLogsJobId] = useState(null);

  const handleViewLogs = useCallback(
    async (jobId) => {
      setViewingLogsJobId(jobId);
      await fetchJobLogs(jobId);
    },
    [fetchJobLogs]
  );

  const handleViewJob = useCallback(
    async (jobId) => {
      await fetchJobDetail(jobId);
    },
    [fetchJobDetail]
  );

  // Show loading skeleton
  if (loading) {
    return <GPUJobLoadingSkeleton className={className} />;
  }

  // Show error state
  if (error) {
    return (
      <div className={`bg-white dark:bg-surface-800 rounded-xl border border-critical-200 dark:border-critical-800 p-6 ${className}`}>
        <div className="flex items-center gap-3 text-critical-600 dark:text-critical-400">
          <ExclamationCircleIcon className="w-6 h-6" />
          <div>
            <h3 className="font-medium">Failed to load GPU workloads</h3>
            <p className="text-sm text-surface-500 dark:text-surface-400">{error}</p>
          </div>
        </div>
        <button
          onClick={refresh}
          className="mt-4 px-4 py-2 bg-aura-500 text-white rounded-lg hover:bg-aura-600 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  // Show empty state
  if (isEmpty) {
    return <GPUJobEmptyState onScheduleNew={openScheduleModal} className={className} />;
  }

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-aura-100 dark:bg-aura-900/30">
            <CpuChipIconSolid className="w-6 h-6 text-aura-600 dark:text-aura-400" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-50">GPU Workloads</h2>
            <p className="text-sm text-surface-500 dark:text-surface-400">Manage GPU-accelerated jobs</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={refresh}
            className="p-2 text-surface-500 hover:text-surface-700 dark:hover:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
            title="Refresh"
          >
            <ArrowPathIcon className="w-5 h-5" />
          </button>
          <button className="p-2 text-surface-500 hover:text-surface-700 dark:hover:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors" title="Help">
            <QuestionMarkCircleIcon className="w-5 h-5" />
          </button>
          <button className="p-2 text-surface-500 hover:text-surface-700 dark:hover:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors" title="Settings">
            <Cog6ToothIcon className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Resource Metrics */}
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4">
        <h3 className="text-sm font-medium text-surface-500 dark:text-surface-400 mb-3">Resources</h3>
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center p-3 bg-surface-50 dark:bg-surface-700/50 rounded-lg">
            <div className="flex items-center justify-center gap-1 mb-1">
              <CpuChipIcon className="w-4 h-4 text-aura-500" />
              <span className="text-lg font-bold text-surface-900 dark:text-surface-50">
                {resources.gpus_in_use}/{resources.gpus_total}
              </span>
            </div>
            <span className="text-xs text-surface-500 dark:text-surface-400">GPUs in use</span>
          </div>
          <div className="text-center p-3 bg-surface-50 dark:bg-surface-700/50 rounded-lg">
            <div className="flex items-center justify-center gap-1 mb-1">
              <QueueListIcon className="w-4 h-4 text-warning-500" />
              <span className="text-lg font-bold text-surface-900 dark:text-surface-50">
                {queuedJobs.length}
              </span>
            </div>
            <span className="text-xs text-surface-500 dark:text-surface-400">Jobs queued</span>
          </div>
          <div className="text-center p-3 bg-surface-50 dark:bg-surface-700/50 rounded-lg">
            <div className="flex items-center justify-center gap-1 mb-1">
              <CurrencyDollarIcon className="w-4 h-4 text-olive-500" />
              <span className="text-lg font-bold text-surface-900 dark:text-surface-50">
                {formatCost(resources.cost_today_usd)}
              </span>
            </div>
            <span className="text-xs text-surface-500 dark:text-surface-400">Cost today</span>
          </div>
        </div>

        {/* GPU Scaling Indicator */}
        {resources.nodes_scaling > 0 && (
          <div className="mt-4">
            <GPUScalingIndicator nodesScaling={resources.nodes_scaling} />
          </div>
        )}
      </div>

      {/* Active Jobs */}
      {activeJobs.length > 0 && (
        <CollapsibleSection title="Active Jobs" count={activeJobs.length}>
          <div className="p-4 space-y-3">
            {activeJobs.map((job) => (
              <ActiveJobCard
                key={job.job_id}
                job={job}
                onCancel={handleCancelJob}
                onViewLogs={handleViewLogs}
              />
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Queued Jobs */}
      {queuedJobs.length > 0 && (
        <CollapsibleSection title="Queued" count={queuedJobs.length}>
          <div className="divide-y divide-surface-100 dark:divide-surface-700">
            {queuedJobs.map((job) => (
              <QueuedJobRow
                key={job.job_id}
                job={job}
                onCancel={handleCancelJob}
                onBoostPriority={handleBoostPriority}
              />
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Schedule New Job Button */}
      <button
        onClick={openScheduleModal}
        className="flex items-center justify-center gap-2 w-full py-3 px-4 bg-aura-500 hover:bg-aura-600 text-white rounded-xl font-medium transition-colors shadow-sm hover:shadow-md"
      >
        <PlusIcon className="w-5 h-5" />
        Schedule New Job
      </button>

      {/* Recent Jobs */}
      {recentJobs.length > 0 && (
        <CollapsibleSection title="Recent (last 24h)" count={recentJobs.length} defaultExpanded={false}>
          <div className="divide-y divide-surface-100 dark:divide-surface-700 p-2">
            {recentJobs.map((job) => (
              <RecentJobRow key={job.job_id} job={job} onClick={handleViewJob} />
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Live region for accessibility announcements */}
      <div aria-live="polite" aria-atomic="true" className="sr-only">
        {activeJobs.length > 0 && `${activeJobs.length} active GPU jobs running`}
        {queuedJobs.length > 0 && `, ${queuedJobs.length} jobs in queue`}
      </div>
    </div>
  );
}

export default memo(GPUWorkloadsPanel);
