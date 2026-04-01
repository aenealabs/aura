/**
 * Project Aura - GPU Job Loading Skeleton Component
 *
 * Loading placeholder for GPU workloads panel.
 * ADR-061: GPU Workload Scheduler - Phase 3 Frontend Integration
 */

import { memo } from 'react';

/**
 * Skeleton pulse animation component
 */
const Skeleton = memo(function Skeleton({ className = '' }) {
  return (
    <div className={`animate-pulse bg-surface-200 dark:bg-surface-700 rounded ${className}`} />
  );
});

/**
 * Resource metrics skeleton
 */
const ResourceMetricsSkeleton = memo(function ResourceMetricsSkeleton() {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4">
      <Skeleton className="w-20 h-4 mb-3" />
      <div className="grid grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="text-center p-3 bg-surface-50 dark:bg-surface-700/50 rounded-lg">
            <Skeleton className="w-12 h-6 mx-auto mb-1" />
            <Skeleton className="w-16 h-3 mx-auto" />
          </div>
        ))}
      </div>
    </div>
  );
});

/**
 * Active job card skeleton
 */
const ActiveJobSkeleton = memo(function ActiveJobSkeleton() {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <Skeleton className="w-8 h-8 rounded-lg" />
          <div>
            <Skeleton className="w-32 h-4 mb-1" />
            <Skeleton className="w-24 h-3" />
          </div>
        </div>
        <Skeleton className="w-16 h-6 rounded" />
      </div>
      <div className="mb-2">
        <div className="flex items-center justify-between mb-1">
          <Skeleton className="w-20 h-3" />
          <Skeleton className="w-16 h-3" />
        </div>
        <Skeleton className="w-full h-2 rounded-full" />
      </div>
      <div className="flex items-center justify-between">
        <Skeleton className="w-16 h-3" />
        <Skeleton className="w-16 h-3" />
      </div>
    </div>
  );
});

/**
 * Queued job row skeleton
 */
const QueuedJobSkeleton = memo(function QueuedJobSkeleton() {
  return (
    <div className="flex items-center justify-between py-3 px-4">
      <div className="flex items-center gap-3 flex-1">
        <Skeleton className="w-2 h-2 rounded-full" />
        <div className="flex-1">
          <Skeleton className="w-40 h-4 mb-1" />
          <Skeleton className="w-24 h-3" />
        </div>
      </div>
      <div className="flex items-center gap-3">
        <Skeleton className="w-16 h-5 rounded-full" />
        <Skeleton className="w-20 h-4" />
        <div className="flex gap-1">
          <Skeleton className="w-6 h-6 rounded" />
          <Skeleton className="w-6 h-6 rounded" />
        </div>
      </div>
    </div>
  );
});

/**
 * Section skeleton with header
 */
const SectionSkeleton = memo(function SectionSkeleton({ children }) {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-2">
          <Skeleton className="w-24 h-4" />
          <Skeleton className="w-6 h-4" />
        </div>
        <Skeleton className="w-5 h-5" />
      </div>
      <div className="border-t border-surface-200 dark:border-surface-700">
        {children}
      </div>
    </div>
  );
});

/**
 * GPU Job Loading Skeleton Component
 */
function GPUJobLoadingSkeleton({ className = '' }) {
  return (
    <div className={`space-y-6 ${className}`} aria-busy="true" aria-label="Loading GPU workloads">
      {/* Header skeleton */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Skeleton className="w-10 h-10 rounded-lg" />
          <div>
            <Skeleton className="w-32 h-5 mb-1" />
            <Skeleton className="w-40 h-4" />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Skeleton className="w-8 h-8 rounded-lg" />
          <Skeleton className="w-8 h-8 rounded-lg" />
          <Skeleton className="w-8 h-8 rounded-lg" />
        </div>
      </div>

      {/* Resource metrics skeleton */}
      <ResourceMetricsSkeleton />

      {/* Active jobs skeleton */}
      <SectionSkeleton>
        <div className="p-4 space-y-3">
          <ActiveJobSkeleton />
        </div>
      </SectionSkeleton>

      {/* Queued jobs skeleton */}
      <SectionSkeleton>
        <div className="divide-y divide-surface-100 dark:divide-surface-700">
          <QueuedJobSkeleton />
          <QueuedJobSkeleton />
        </div>
      </SectionSkeleton>

      {/* Schedule button skeleton */}
      <Skeleton className="w-full h-12 rounded-xl" />

      {/* Recent jobs skeleton (collapsed) */}
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2">
            <Skeleton className="w-28 h-4" />
            <Skeleton className="w-6 h-4" />
          </div>
          <Skeleton className="w-5 h-5" />
        </div>
      </div>
    </div>
  );
}

export default memo(GPUJobLoadingSkeleton);
