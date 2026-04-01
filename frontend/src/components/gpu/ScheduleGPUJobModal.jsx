/**
 * Project Aura - Schedule GPU Job Modal
 *
 * Modal for scheduling GPU workloads with Simple/Advanced modes.
 * ADR-061: GPU Workload Scheduler - Phase 3 Frontend Integration
 */

import { useState, useEffect, useCallback, memo, useRef } from 'react';
import { createPortal } from 'react-dom';
import {
  XMarkIcon,
  CpuChipIcon,
  FolderIcon,
  ClockIcon,
  CurrencyDollarIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  InformationCircleIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';
import { useGPUWorkloads } from '../../context/GPUWorkloadsContext';
import {
  GPU_JOB_TYPES,
  GPU_JOB_PRIORITIES,
  formatDuration,
  formatCost,
} from '../../services/gpuSchedulerApi';

/**
 * Job type selector component
 */
const JobTypeSelector = memo(function JobTypeSelector({ value, onChange }) {
  return (
    <div className="space-y-2">
      {GPU_JOB_TYPES.map((type) => {
        const isSelected = value === type.value;
        return (
          <button
            key={type.value}
            type="button"
            onClick={() => onChange(type.value)}
            className={`
              w-full flex items-start gap-3 p-3 rounded-lg border transition-all
              ${isSelected
                ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/20 shadow-sm'
                : 'border-surface-200 dark:border-surface-600 hover:border-aura-300 dark:hover:border-aura-700'
              }
            `}
          >
            <div className={`w-4 h-4 mt-0.5 rounded-full border-2 flex-shrink-0 ${isSelected ? 'border-aura-500 bg-aura-500' : 'border-surface-300 dark:border-surface-600'}`}>
              {isSelected && (
                <div className="w-full h-full flex items-center justify-center">
                  <div className="w-1.5 h-1.5 bg-white rounded-full" />
                </div>
              )}
            </div>
            <div className="flex-1 text-left">
              <p className="text-sm font-medium text-surface-900 dark:text-surface-100">
                {type.label}
              </p>
              <p className="text-xs text-surface-500 dark:text-surface-400 mt-0.5">
                {type.description}
              </p>
              <p className="text-xs text-surface-400 dark:text-surface-500 mt-1">
                {type.typicalDuration} • {type.gpuMemory}
              </p>
            </div>
          </button>
        );
      })}
    </div>
  );
});

/**
 * Priority selector component
 */
const PrioritySelector = memo(function PrioritySelector({ value, onChange }) {
  return (
    <div className="flex gap-2">
      {GPU_JOB_PRIORITIES.map((p) => {
        const isSelected = value === p.value;
        const colorClasses = {
          low: isSelected
            ? 'border-surface-500 bg-surface-100 dark:bg-surface-700'
            : 'border-surface-200 dark:border-surface-600 hover:border-surface-400',
          normal: isSelected
            ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/20'
            : 'border-surface-200 dark:border-surface-600 hover:border-aura-300',
          high: isSelected
            ? 'border-critical-500 bg-critical-50 dark:bg-critical-900/20'
            : 'border-surface-200 dark:border-surface-600 hover:border-critical-300',
        };

        return (
          <button
            key={p.value}
            type="button"
            onClick={() => onChange(p.value)}
            className={`flex-1 py-2 px-3 rounded-lg border text-center transition-all ${colorClasses[p.value]}`}
          >
            <span className={`text-sm font-medium ${isSelected ? 'text-surface-900 dark:text-surface-100' : 'text-surface-600 dark:text-surface-400'}`}>
              {p.label}
            </span>
          </button>
        );
      })}
    </div>
  );
});

/**
 * GPU memory selector component
 */
const GPUMemorySelector = memo(function GPUMemorySelector({ value, onChange, recommended }) {
  const options = [4, 8, 16, 24];

  return (
    <div className="flex gap-2">
      {options.map((gb) => {
        const isSelected = value === gb;
        const isRecommended = gb === recommended;
        return (
          <button
            key={gb}
            type="button"
            onClick={() => onChange(gb)}
            className={`
              flex-1 py-2 px-3 rounded-lg border text-center transition-all relative
              ${isSelected
                ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/20'
                : 'border-surface-200 dark:border-surface-600 hover:border-aura-300'
              }
            `}
          >
            <span className={`text-sm font-medium ${isSelected ? 'text-surface-900 dark:text-surface-100' : 'text-surface-600 dark:text-surface-400'}`}>
              {gb} GB
            </span>
            {isRecommended && (
              <span className="absolute -top-2 left-1/2 -translate-x-1/2 text-[10px] bg-aura-500 text-white px-1.5 rounded">
                Rec
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
});

/**
 * Max runtime selector component
 */
const MaxRuntimeSelector = memo(function MaxRuntimeSelector({ value, onChange }) {
  const options = [
    { value: 60, label: '1 hour' },
    { value: 120, label: '2 hours' },
    { value: 240, label: '4 hours' },
    { value: 480, label: '8 hours' },
  ];

  return (
    <select
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
      className="w-full px-3 py-2 rounded-lg border border-surface-200 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 text-sm focus:ring-2 focus:ring-aura-500 focus:border-aura-500"
    >
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  );
});

/**
 * Estimate display component
 */
const EstimateDisplay = memo(function EstimateDisplay({ estimate, loading }) {
  if (loading) {
    return (
      <div className="p-4 bg-surface-50 dark:bg-surface-700/50 rounded-lg animate-pulse">
        <div className="h-4 bg-surface-200 dark:bg-surface-600 rounded w-3/4 mb-2" />
        <div className="h-4 bg-surface-200 dark:bg-surface-600 rounded w-1/2" />
      </div>
    );
  }

  if (!estimate) {
    return null;
  }

  return (
    <div className="p-4 bg-surface-50 dark:bg-surface-700/50 rounded-lg space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm text-surface-600 dark:text-surface-400">Estimated Cost:</span>
        <span className="text-sm font-medium text-surface-900 dark:text-surface-100">
          $0.45 - $0.90
        </span>
      </div>
      <div className="flex items-center justify-between">
        <span className="text-sm text-surface-600 dark:text-surface-400">Queue Position:</span>
        <span className="text-sm font-medium text-surface-900 dark:text-surface-100">
          {estimate.queue_position} (starts in ~{estimate.estimated_wait_minutes} min)
        </span>
      </div>
      {estimate.gpu_scaling_required && (
        <div className="flex items-center gap-2 text-xs text-warning-600 dark:text-warning-400">
          <InformationCircleIcon className="w-4 h-4" />
          <span>GPU node scaling required (+5 min)</span>
        </div>
      )}
      {estimate.preemption_possible && (
        <div className="flex items-center gap-2 text-xs text-aura-600 dark:text-aura-400">
          <InformationCircleIcon className="w-4 h-4" />
          <span>May preempt lower priority jobs</span>
        </div>
      )}
    </div>
  );
});

/**
 * Budget warning component
 */
const BudgetWarning = memo(function BudgetWarning({ used, total }) {
  const percentUsed = (used / total) * 100;
  if (percentUsed < 80) return null;

  return (
    <div className="flex items-start gap-2 p-3 bg-warning-50 dark:bg-warning-900/20 border border-warning-200 dark:border-warning-800 rounded-lg">
      <ExclamationTriangleIcon className="w-5 h-5 text-warning-600 dark:text-warning-400 flex-shrink-0" />
      <div>
        <p className="text-sm font-medium text-warning-700 dark:text-warning-300">
          Budget Warning
        </p>
        <p className="text-xs text-warning-600 dark:text-warning-400 mt-0.5">
          You&apos;ve used {formatCost(used)} of your {formatCost(total)} monthly GPU budget ({percentUsed.toFixed(0)}%)
        </p>
      </div>
    </div>
  );
});

/**
 * Main Schedule GPU Job Modal component
 */
function ScheduleGPUJobModal({ isOpen, onClose }) {
  const {
    handleSubmitJob,
    getEstimatedPosition,
    resources,
  } = useGPUWorkloads();

  const modalRef = useRef(null);

  // Form state
  const [jobType, setJobType] = useState('embedding_generation');
  const [priority, setPriority] = useState('normal');
  const [gpuMemory, setGpuMemory] = useState(8);
  const [maxRuntime, setMaxRuntime] = useState(120);
  const [checkpointEnabled, setCheckpointEnabled] = useState(true);

  // Configuration state (varies by job type)
  const [repositoryId, setRepositoryId] = useState('');
  const [branch, setBranch] = useState('main');
  const [model, setModel] = useState('codebert-base');

  // UI state
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [estimate, setEstimate] = useState(null);
  const [estimateLoading, setEstimateLoading] = useState(false);

  // Mock budget data (would come from API)
  const budget = { used: 47.82, total: 100 };

  // Get recommended GPU memory based on job type
  const getRecommendedMemory = useCallback((type) => {
    const recommendations = {
      embedding_generation: 8,
      local_inference: 16,
      vulnerability_training: 16,
      swe_rl_training: 24,
      memory_consolidation: 4,
    };
    return recommendations[type] || 8;
  }, []);

  // Update GPU memory when job type changes
  useEffect(() => {
    const recommended = getRecommendedMemory(jobType);
    setGpuMemory(recommended);
  }, [jobType, getRecommendedMemory]);

  // Fetch estimate when priority or job type changes
  useEffect(() => {
    if (!isOpen) return;

    const fetchEstimate = async () => {
      setEstimateLoading(true);
      try {
        const est = await getEstimatedPosition(priority, jobType);
        setEstimate(est);
      } catch (err) {
        console.error('Failed to get estimate:', err);
      } finally {
        setEstimateLoading(false);
      }
    };

    fetchEstimate();
  }, [isOpen, priority, jobType, getEstimatedPosition]);

  // Handle escape key and body scroll
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && !submitting) {
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    document.body.style.overflow = 'hidden';

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [isOpen, submitting, onClose]);

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setJobType('embedding_generation');
      setPriority('normal');
      setGpuMemory(8);
      setMaxRuntime(120);
      setCheckpointEnabled(true);
      setRepositoryId('');
      setBranch('main');
      setModel('codebert-base');
      setShowAdvanced(false);
      setError(null);
    }
  }, [isOpen]);

  // Build job config based on job type
  const buildJobConfig = useCallback(() => {
    switch (jobType) {
      case 'embedding_generation':
        return {
          repository_id: repositoryId,
          branch,
          model,
        };
      case 'vulnerability_training':
        return {
          dataset_id: repositoryId || 'default-dataset',
          epochs: 10,
          batch_size: 32,
          learning_rate: 0.0001,
        };
      case 'swe_rl_training':
        return {
          batch_id: repositoryId || `batch-${Date.now()}`,
          max_epochs: 100,
          checkpoint_interval_minutes: 15,
        };
      case 'memory_consolidation':
        return {
          session_id: repositoryId || `session-${Date.now()}`,
          retention_threshold: 0.7,
        };
      default:
        return {};
    }
  }, [jobType, repositoryId, branch, model]);

  // Handle form submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      // Validation
      if (!jobType) {
        throw new Error('Please select a job type');
      }

      if (jobType === 'embedding_generation' && !repositoryId) {
        throw new Error('Please enter a repository ID');
      }

      // Build job data
      const jobData = {
        job_type: jobType,
        priority,
        gpu_memory_gb: gpuMemory,
        checkpoint_enabled: checkpointEnabled,
        config: buildJobConfig(),
      };

      // Submit job
      await handleSubmitJob(jobData);

      // Close modal on success
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to schedule job');
    } finally {
      setSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="schedule-gpu-job-title"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm transition-opacity"
        onClick={submitting ? undefined : onClose}
      />

      {/* Modal */}
      <div
        ref={modalRef}
        className="relative bg-white dark:bg-surface-800 rounded-2xl shadow-[var(--shadow-modal)] max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-surface-200 dark:border-surface-700">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-aura-100 dark:bg-aura-900/30 rounded-lg">
              <CpuChipIcon className="w-5 h-5 text-aura-600 dark:text-aura-400" />
            </div>
            <div>
              <h2 id="schedule-gpu-job-title" className="text-lg font-semibold text-surface-900 dark:text-surface-100">
                Schedule GPU Job
              </h2>
              <p className="text-sm text-surface-500 dark:text-surface-400">
                Configure and queue a GPU workload
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={submitting}
            className="p-2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 transition-colors rounded-lg hover:bg-surface-100 dark:hover:bg-surface-700 disabled:opacity-50"
            aria-label="Close modal"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6">
          {error && (
            <div className="mb-4 p-3 bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800 rounded-lg">
              <p className="text-sm text-critical-700 dark:text-critical-300">{error}</p>
            </div>
          )}

          {/* Budget warning */}
          <div className="mb-4">
            <BudgetWarning used={budget.used} total={budget.total} />
          </div>

          <form id="schedule-gpu-job-form" onSubmit={handleSubmit} className="space-y-5">
            {/* Job Type */}
            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                <CpuChipIcon className="w-4 h-4" />
                Job Type
              </label>
              <JobTypeSelector value={jobType} onChange={setJobType} />
            </div>

            {/* Configuration - Varies by job type */}
            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                <FolderIcon className="w-4 h-4" />
                Configuration
              </label>
              <div className="space-y-3 p-4 bg-surface-50 dark:bg-surface-700/50 rounded-lg">
                {jobType === 'embedding_generation' && (
                  <>
                    <div>
                      <label className="block text-xs text-surface-500 dark:text-surface-400 mb-1">
                        Repository
                      </label>
                      <input
                        type="text"
                        value={repositoryId}
                        onChange={(e) => setRepositoryId(e.target.value)}
                        placeholder="e.g., backend-services"
                        className="w-full px-3 py-2 rounded-lg border border-surface-200 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 text-sm focus:ring-2 focus:ring-aura-500 focus:border-aura-500"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs text-surface-500 dark:text-surface-400 mb-1">
                          Branch
                        </label>
                        <input
                          type="text"
                          value={branch}
                          onChange={(e) => setBranch(e.target.value)}
                          placeholder="main"
                          className="w-full px-3 py-2 rounded-lg border border-surface-200 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 text-sm focus:ring-2 focus:ring-aura-500 focus:border-aura-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-surface-500 dark:text-surface-400 mb-1">
                          Model
                        </label>
                        <select
                          value={model}
                          onChange={(e) => setModel(e.target.value)}
                          className="w-full px-3 py-2 rounded-lg border border-surface-200 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 text-sm focus:ring-2 focus:ring-aura-500 focus:border-aura-500"
                        >
                          <option value="codebert-base">CodeBERT-base (recommended)</option>
                          <option value="codebert-large">CodeBERT-large</option>
                          <option value="starencoder">StarEncoder</option>
                        </select>
                      </div>
                    </div>
                  </>
                )}
                {jobType !== 'embedding_generation' && (
                  <div>
                    <label className="block text-xs text-surface-500 dark:text-surface-400 mb-1">
                      {jobType === 'vulnerability_training' ? 'Dataset ID' :
                        jobType === 'swe_rl_training' ? 'Batch ID' : 'Session ID'}
                    </label>
                    <input
                      type="text"
                      value={repositoryId}
                      onChange={(e) => setRepositoryId(e.target.value)}
                      placeholder="Leave empty for auto-generated ID"
                      className="w-full px-3 py-2 rounded-lg border border-surface-200 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 text-sm focus:ring-2 focus:ring-aura-500 focus:border-aura-500"
                    />
                  </div>
                )}
              </div>
            </div>

            {/* Resources */}
            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                <ClockIcon className="w-4 h-4" />
                Resources
              </label>
              <div className="space-y-4 p-4 bg-surface-50 dark:bg-surface-700/50 rounded-lg">
                <div>
                  <label className="block text-xs text-surface-500 dark:text-surface-400 mb-2">
                    GPU Memory
                  </label>
                  <GPUMemorySelector
                    value={gpuMemory}
                    onChange={setGpuMemory}
                    recommended={getRecommendedMemory(jobType)}
                  />
                </div>
                <div>
                  <label className="block text-xs text-surface-500 dark:text-surface-400 mb-2">
                    Priority
                  </label>
                  <PrioritySelector value={priority} onChange={setPriority} />
                </div>
              </div>
            </div>

            {/* Advanced Options (Collapsed by default) */}
            <div>
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex items-center gap-2 text-sm text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-100 transition-colors"
              >
                {showAdvanced ? (
                  <ChevronUpIcon className="w-4 h-4" />
                ) : (
                  <ChevronDownIcon className="w-4 h-4" />
                )}
                Advanced Options
              </button>
              {showAdvanced && (
                <div className="mt-3 space-y-3 p-4 bg-surface-50 dark:bg-surface-700/50 rounded-lg">
                  <div>
                    <label className="block text-xs text-surface-500 dark:text-surface-400 mb-2">
                      Max Runtime
                    </label>
                    <MaxRuntimeSelector value={maxRuntime} onChange={setMaxRuntime} />
                  </div>
                  <div className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      id="checkpoint-enabled"
                      checked={checkpointEnabled}
                      onChange={(e) => setCheckpointEnabled(e.target.checked)}
                      className="w-4 h-4 rounded border-surface-300 dark:border-surface-600 text-aura-500 focus:ring-aura-500"
                    />
                    <label htmlFor="checkpoint-enabled" className="text-sm text-surface-700 dark:text-surface-300">
                      Enable checkpointing (recommended for long-running jobs)
                    </label>
                  </div>
                </div>
              )}
            </div>

            {/* Estimate */}
            <EstimateDisplay estimate={estimate} loading={estimateLoading} />
          </form>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50">
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            form="schedule-gpu-job-form"
            disabled={submitting}
            className="px-4 py-2 text-sm font-medium text-white bg-aura-500 hover:bg-aura-600 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {submitting && (
              <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
            )}
            Schedule Job
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}

export default memo(ScheduleGPUJobModal);
