/**
 * Project Aura - Tour Tooltip
 *
 * Tooltip component for tour steps.
 * Positioned relative to the target element.
 */

import { useEffect, useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  XMarkIcon,
  CheckIcon,
} from '@heroicons/react/24/outline';

const TourTooltip = ({
  step,
  currentStep,
  totalSteps,
  onNext,
  onPrev,
  onSkip,
}) => {
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const tooltipRef = useRef(null);

  // Calculate tooltip position
  useEffect(() => {
    if (!step) return;

    const updatePosition = () => {
      const tooltip = tooltipRef.current;
      if (!tooltip) return;

      const tooltipRect = tooltip.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;

      // Center placement (for completion step)
      if (!step.target || step.placement === 'center') {
        setPosition({
          x: (viewportWidth - tooltipRect.width) / 2,
          y: (viewportHeight - tooltipRect.height) / 2,
        });
        return;
      }

      const target = document.querySelector(step.target);
      if (!target) return;

      const targetRect = target.getBoundingClientRect();
      const padding = 16;

      let x = 0;
      let y = 0;

      switch (step.placement) {
        case 'bottom':
          x = targetRect.x + targetRect.width / 2 - tooltipRect.width / 2;
          y = targetRect.bottom + padding;
          break;
        case 'top':
          x = targetRect.x + targetRect.width / 2 - tooltipRect.width / 2;
          y = targetRect.top - tooltipRect.height - padding;
          break;
        case 'left':
          x = targetRect.left - tooltipRect.width - padding;
          y = targetRect.y + targetRect.height / 2 - tooltipRect.height / 2;
          break;
        case 'right':
          x = targetRect.right + padding;
          y = targetRect.y + targetRect.height / 2 - tooltipRect.height / 2;
          break;
        default:
          x = targetRect.x + targetRect.width / 2 - tooltipRect.width / 2;
          y = targetRect.bottom + padding;
      }

      // Keep within viewport
      x = Math.max(padding, Math.min(x, viewportWidth - tooltipRect.width - padding));
      y = Math.max(padding, Math.min(y, viewportHeight - tooltipRect.height - padding));

      setPosition({ x, y });
    };

    // Initial position with slight delay for render
    setTimeout(updatePosition, 50);

    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', updatePosition, true);

    return () => {
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
    };
  }, [step]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'ArrowRight' || e.key === 'Enter') {
        e.preventDefault();
        onNext();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        onPrev();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        onSkip();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onNext, onPrev, onSkip]);

  if (!step) return null;

  const isLastStep = currentStep === totalSteps - 1;
  const isFirstStep = currentStep === 0;
  const isCompletionStep = step.id === 'completion';

  const tooltip = (
    <div
      ref={tooltipRef}
      className="fixed z-[95] w-80 bg-white dark:bg-surface-800 rounded-xl shadow-2xl border border-surface-200 dark:border-surface-700 overflow-hidden"
      style={{
        left: `${position.x}px`,
        top: `${position.y}px`,
        transition: 'left 0.2s ease, top 0.2s ease',
      }}
      role="dialog"
      aria-labelledby="tour-step-title"
      aria-describedby="tour-step-content"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-surface-100 dark:border-surface-700 bg-aura-50 dark:bg-aura-900/20">
        <h3
          id="tour-step-title"
          className="text-sm font-semibold text-surface-900 dark:text-surface-100"
        >
          {step.title}
        </h3>
        <button
          onClick={onSkip}
          className="p-1 rounded-lg text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
          aria-label="Skip tour"
        >
          <XMarkIcon className="w-4 h-4" />
        </button>
      </div>

      {/* Content */}
      <div className="px-4 py-4">
        <p
          id="tour-step-content"
          className="text-sm text-surface-600 dark:text-surface-400"
        >
          {step.content}
        </p>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between px-4 py-3 border-t border-surface-100 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50">
        {/* Progress dots */}
        <div className="flex items-center gap-1">
          {Array.from({ length: totalSteps }).map((_, i) => (
            <div
              key={i}
              className={`w-2 h-2 rounded-full transition-colors ${
                i === currentStep
                  ? 'bg-aura-500'
                  : i < currentStep
                  ? 'bg-olive-400'
                  : 'bg-surface-300 dark:bg-surface-600'
              }`}
            />
          ))}
        </div>

        {/* Navigation buttons */}
        <div className="flex items-center gap-2">
          {!isFirstStep && !isCompletionStep && (
            <button
              onClick={onPrev}
              className="flex items-center gap-1 px-3 py-1.5 text-sm text-surface-600 dark:text-surface-400 hover:text-surface-800 dark:hover:text-surface-200 transition-colors"
            >
              <ArrowLeftIcon className="w-4 h-4" />
              Back
            </button>
          )}

          <button
            onClick={onNext}
            className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-white bg-aura-600 hover:bg-aura-700 rounded-lg transition-colors"
          >
            {isCompletionStep ? (
              <>
                <CheckIcon className="w-4 h-4" />
                Finish
              </>
            ) : isLastStep ? (
              'Complete'
            ) : (
              <>
                Next
                <ArrowRightIcon className="w-4 h-4" />
              </>
            )}
          </button>
        </div>
      </div>

      {/* Keyboard hint */}
      <div className="px-4 py-2 text-center text-xs text-surface-400 dark:text-surface-500 border-t border-surface-100 dark:border-surface-700">
        Use <kbd className="px-1 py-0.5 rounded bg-surface-100 dark:bg-surface-700 font-mono">←</kbd>{' '}
        <kbd className="px-1 py-0.5 rounded bg-surface-100 dark:bg-surface-700 font-mono">→</kbd> to navigate,{' '}
        <kbd className="px-1 py-0.5 rounded bg-surface-100 dark:bg-surface-700 font-mono">Esc</kbd> to skip
      </div>
    </div>
  );

  return createPortal(tooltip, document.body);
};

export default TourTooltip;
