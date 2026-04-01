/**
 * Project Aura - GPU Job Empty State Component
 *
 * Displays when no GPU jobs have been scheduled.
 * ADR-061: GPU Workload Scheduler - Phase 3 Frontend Integration
 */

import { memo } from 'react';
import { CpuChipIcon, PlusIcon, SparklesIcon, ClockIcon, ShieldCheckIcon } from '@heroicons/react/24/outline';

/**
 * Feature card for empty state
 */
const FeatureCard = memo(function FeatureCard({ icon: Icon, title, description }) {
  return (
    <div className="flex items-start gap-3 p-3 rounded-lg bg-surface-50 dark:bg-surface-700/50">
      <div className="p-2 rounded-lg bg-aura-100 dark:bg-aura-900/30 flex-shrink-0">
        <Icon className="w-4 h-4 text-aura-600 dark:text-aura-400" />
      </div>
      <div>
        <h4 className="font-medium text-surface-900 dark:text-surface-50 text-sm">{title}</h4>
        <p className="text-xs text-surface-500 dark:text-surface-400 mt-0.5">{description}</p>
      </div>
    </div>
  );
});

/**
 * GPU Job Empty State Component
 */
function GPUJobEmptyState({ onScheduleNew, className = '' }) {
  return (
    <div className={`bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-8 text-center ${className}`}>
      {/* Icon */}
      <div className="flex justify-center mb-4">
        <div className="p-4 rounded-full bg-aura-100 dark:bg-aura-900/30">
          <CpuChipIcon className="w-12 h-12 text-aura-500 dark:text-aura-400" />
        </div>
      </div>

      {/* Title and description */}
      <h3 className="text-xl font-semibold text-surface-900 dark:text-surface-50 mb-2">
        No GPU Jobs Yet
      </h3>
      <p className="text-surface-500 dark:text-surface-400 max-w-md mx-auto mb-6">
        Get started by scheduling your first GPU workload. GPU compute is available for code embedding,
        model training, and more.
      </p>

      {/* Feature highlights */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 max-w-2xl mx-auto mb-6">
        <FeatureCard
          icon={SparklesIcon}
          title="Code Embeddings"
          description="Generate semantic vectors for your repositories"
        />
        <FeatureCard
          icon={ShieldCheckIcon}
          title="Security Training"
          description="Train vulnerability classifiers on your patterns"
        />
        <FeatureCard
          icon={ClockIcon}
          title="Scheduled Jobs"
          description="Run jobs in background with queue management"
        />
      </div>

      {/* CTA Button */}
      <button
        onClick={onScheduleNew}
        className="inline-flex items-center gap-2 px-6 py-3 bg-aura-500 hover:bg-aura-600 text-white rounded-xl font-medium transition-colors shadow-sm hover:shadow-md"
      >
        <PlusIcon className="w-5 h-5" />
        Schedule Your First GPU Job
      </button>

      {/* Help text */}
      <p className="text-xs text-surface-400 dark:text-surface-500 mt-4">
        GPU nodes scale to zero when not in use, so there&apos;s no cost when idle.
      </p>
    </div>
  );
}

export default memo(GPUJobEmptyState);
