/**
 * Project Aura - Checklist Item
 *
 * Individual item in the onboarding checklist.
 * Shows completion status, description, and action button.
 */

import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircleIcon, ArrowRightIcon } from '@heroicons/react/24/outline';
import { CheckCircleIcon as CheckCircleSolidIcon } from '@heroicons/react/24/solid';

const ChecklistItem = ({ item, isCompleted, onComplete }) => {
  const navigate = useNavigate();

  const handleAction = useCallback(() => {
    if (item.action?.route) {
      navigate(item.action.route);
    }
    // Auto-complete could be handled by context monitoring
  }, [item.action, navigate]);

  return (
    <div
      className={`group p-3 rounded-lg transition-all ${
        isCompleted
          ? 'bg-olive-50/50 dark:bg-olive-900/10'
          : 'bg-surface-50 dark:bg-surface-800/50 hover:bg-surface-100 dark:hover:bg-surface-800'
      }`}
    >
      <div className="flex items-start gap-3">
        {/* Status Icon */}
        <div className="flex-shrink-0 mt-0.5">
          {isCompleted ? (
            <CheckCircleSolidIcon className="w-5 h-5 text-olive-500 dark:text-olive-400" />
          ) : (
            <CheckCircleIcon className="w-5 h-5 text-surface-300 dark:text-surface-600 group-hover:text-surface-400" />
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <h4
            className={`text-sm font-medium ${
              isCompleted
                ? 'text-surface-500 dark:text-surface-400 line-through'
                : 'text-surface-900 dark:text-surface-100'
            }`}
          >
            {item.title}
          </h4>
          <p
            className={`text-xs mt-0.5 ${
              isCompleted
                ? 'text-surface-400 dark:text-surface-500'
                : 'text-surface-500 dark:text-surface-400'
            }`}
          >
            {item.description}
          </p>

          {/* Action Button */}
          {!isCompleted && item.action && (
            <button
              onClick={handleAction}
              className="mt-2 inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-aura-600 dark:text-aura-400 bg-aura-50 dark:bg-aura-900/20 hover:bg-aura-100 dark:hover:bg-aura-900/30 rounded-md transition-colors"
            >
              {item.action.label}
              <ArrowRightIcon className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChecklistItem;
