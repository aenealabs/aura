/**
 * Project Aura - Onboarding Checklist
 *
 * P1: Fixed bottom-right checklist widget for tracking setup progress.
 *
 * States:
 * - Collapsed: Progress ring + "Setup (2/5)"
 * - Expanded: Full list with progress bar, item statuses, CTAs
 *
 * Features:
 * - Progress ring visualization
 * - Collapsible/expandable
 * - Keyboard accessible
 * - Dark mode support
 */

import { useCallback, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { useOnboarding } from '../../context/OnboardingContext';
import ChecklistItem from './ChecklistItem';
import {
  ChevronUpIcon,
  ChevronDownIcon,
  XMarkIcon,
  CheckIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline';

const OnboardingChecklist = () => {
  const {
    showChecklist,
    checklistExpanded,
    checklistSteps,
    checklistProgress,
    isChecklistComplete,
    checklistItems,
    toggleChecklist,
    dismissChecklist,
    completeChecklistItem,
    startTour,
  } = useOnboarding();

  // Calculate stroke dasharray for progress ring
  const progressRing = useMemo(() => {
    const radius = 18;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (checklistProgress.percent / 100) * circumference;
    return { circumference, offset, radius };
  }, [checklistProgress.percent]);

  const handleDismiss = useCallback(() => {
    dismissChecklist();
  }, [dismissChecklist]);

  const handleToggle = useCallback(() => {
    toggleChecklist();
  }, [toggleChecklist]);

  const handleStartTour = useCallback(() => {
    startTour();
  }, [startTour]);

  if (!showChecklist) {
    return null;
  }

  const widget = (
    <div
      className="fixed bottom-6 right-6 z-50"
      role="complementary"
      aria-label="Setup progress checklist"
    >
      {/* Collapsed State */}
      {!checklistExpanded && (
        <button
          onClick={handleToggle}
          className="group flex items-center gap-3 px-4 py-3 bg-white dark:bg-surface-800 rounded-full shadow-lg border border-surface-200 dark:border-surface-700 hover:shadow-xl transition-all"
          aria-expanded="false"
          aria-label={`Setup progress: ${checklistProgress.completed} of ${checklistProgress.total} complete. Click to expand.`}
        >
          {/* Progress Ring */}
          <div className="relative">
            <svg className="w-10 h-10 -rotate-90" viewBox="0 0 40 40">
              {/* Background circle */}
              <circle
                cx="20"
                cy="20"
                r={progressRing.radius}
                fill="none"
                stroke="currentColor"
                strokeWidth="3"
                className="text-surface-200 dark:text-surface-700"
              />
              {/* Progress circle */}
              <circle
                cx="20"
                cy="20"
                r={progressRing.radius}
                fill="none"
                stroke="currentColor"
                strokeWidth="3"
                strokeLinecap="round"
                strokeDasharray={progressRing.circumference}
                strokeDashoffset={progressRing.offset}
                className="text-aura-500 dark:text-aura-400 transition-all duration-500"
              />
            </svg>
            {/* Center icon */}
            <div className="absolute inset-0 flex items-center justify-center">
              {isChecklistComplete ? (
                <CheckIcon className="w-4 h-4 text-olive-500" />
              ) : (
                <span className="text-xs font-bold text-surface-900 dark:text-surface-100">
                  {checklistProgress.completed}
                </span>
              )}
            </div>
          </div>

          {/* Label */}
          <div className="pr-2">
            <span className="text-sm font-medium text-surface-900 dark:text-surface-100">
              {isChecklistComplete ? 'Setup Complete!' : 'Setup'}
            </span>
            <span className="text-xs text-surface-500 dark:text-surface-400 ml-1">
              ({checklistProgress.completed}/{checklistProgress.total})
            </span>
          </div>

          <ChevronUpIcon className="w-4 h-4 text-surface-400 group-hover:text-surface-600 dark:group-hover:text-surface-300" />
        </button>
      )}

      {/* Expanded State */}
      {checklistExpanded && (
        <div className="w-80 bg-white dark:bg-surface-800 rounded-xl shadow-xl border border-surface-200 dark:border-surface-700 overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-surface-100 dark:border-surface-700">
            <div className="flex items-center gap-2">
              <SparklesIcon className="w-5 h-5 text-aura-500" />
              <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100">
                Getting Started
              </h3>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={handleToggle}
                className="p-1.5 rounded-lg text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
                aria-label="Collapse checklist"
              >
                <ChevronDownIcon className="w-4 h-4" />
              </button>
              <button
                onClick={handleDismiss}
                className="p-1.5 rounded-lg text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
                aria-label="Dismiss checklist"
              >
                <XMarkIcon className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="px-4 py-3 border-b border-surface-100 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-surface-600 dark:text-surface-400">
                Progress
              </span>
              <span className="text-xs font-bold text-surface-900 dark:text-surface-100">
                {checklistProgress.percent}%
              </span>
            </div>
            <div className="w-full h-2 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-aura-500 to-aura-400 rounded-full transition-all duration-500"
                style={{ width: `${checklistProgress.percent}%` }}
              />
            </div>
          </div>

          {/* Checklist Items */}
          <div className="p-2 space-y-1 max-h-80 overflow-y-auto">
            {checklistItems.map((item) => (
              <ChecklistItem
                key={item.id}
                item={item}
                isCompleted={checklistSteps[item.id]}
                onComplete={() => completeChecklistItem(item.id)}
              />
            ))}
          </div>

          {/* Footer */}
          <div className="px-4 py-3 border-t border-surface-100 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50">
            {isChecklistComplete ? (
              <div className="text-center">
                <p className="text-sm text-olive-600 dark:text-olive-400 font-medium">
                  You&apos;re all set!
                </p>
                <button
                  onClick={handleDismiss}
                  className="mt-2 text-xs text-surface-500 hover:text-surface-700 dark:hover:text-surface-300"
                >
                  Dismiss checklist
                </button>
              </div>
            ) : (
              <button
                onClick={handleStartTour}
                className="w-full text-center text-xs text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300 font-medium"
              >
                Need help? Take a quick tour
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );

  return createPortal(widget, document.body);
};

export default OnboardingChecklist;
