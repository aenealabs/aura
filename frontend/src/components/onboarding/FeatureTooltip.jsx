/**
 * Project Aura - Feature Tooltip
 *
 * P3: In-app tooltips for feature discovery.
 * Wraps elements with a tooltip indicator and hover tooltip.
 *
 * Features:
 * - Pulsing indicator for unseen features
 * - Tooltip on hover/focus
 * - Dismissable
 * - Persists dismissal state
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { useFeatureTooltip } from '../../context/OnboardingContext';
import TooltipIndicator from './TooltipIndicator';
import { XMarkIcon, InformationCircleIcon } from '@heroicons/react/24/outline';

const FeatureTooltip = ({
  tooltipId,
  children,
  placement = 'top',
  showIndicator = true,
  delay = 300,
}) => {
  const { tooltip, isDismissed, dismiss, shouldShow } = useFeatureTooltip(tooltipId);
  const [isVisible, setIsVisible] = useState(false);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const containerRef = useRef(null);
  const tooltipRef = useRef(null);
  const timeoutRef = useRef(null);

  // Calculate tooltip position
  const updatePosition = useCallback(() => {
    if (!containerRef.current || !tooltipRef.current) return;

    const container = containerRef.current.getBoundingClientRect();
    const tooltip = tooltipRef.current.getBoundingClientRect();
    const padding = 8;

    let x = 0;
    let y = 0;

    switch (placement) {
      case 'top':
        x = container.x + container.width / 2 - tooltip.width / 2;
        y = container.y - tooltip.height - padding;
        break;
      case 'bottom':
        x = container.x + container.width / 2 - tooltip.width / 2;
        y = container.bottom + padding;
        break;
      case 'left':
        x = container.x - tooltip.width - padding;
        y = container.y + container.height / 2 - tooltip.height / 2;
        break;
      case 'right':
        x = container.right + padding;
        y = container.y + container.height / 2 - tooltip.height / 2;
        break;
      default:
        x = container.x + container.width / 2 - tooltip.width / 2;
        y = container.y - tooltip.height - padding;
    }

    // Keep within viewport
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    x = Math.max(8, Math.min(x, viewportWidth - tooltip.width - 8));
    y = Math.max(8, Math.min(y, viewportHeight - tooltip.height - 8));

    setPosition({ x, y });
  }, [placement]);

  // Show tooltip on hover/focus
  const handleMouseEnter = useCallback(() => {
    if (!shouldShow) return;
    timeoutRef.current = setTimeout(() => {
      setIsVisible(true);
      setTimeout(updatePosition, 10);
    }, delay);
  }, [shouldShow, delay, updatePosition]);

  const handleMouseLeave = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    setIsVisible(false);
  }, []);

  const handleFocus = useCallback(() => {
    if (!shouldShow) return;
    setIsVisible(true);
    setTimeout(updatePosition, 10);
  }, [shouldShow, updatePosition]);

  const handleBlur = useCallback(() => {
    setIsVisible(false);
  }, []);

  const handleDismiss = useCallback(
    (e) => {
      e.stopPropagation();
      dismiss();
      setIsVisible(false);
    },
    [dismiss]
  );

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  // Update position on resize
  useEffect(() => {
    if (!isVisible) return;

    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', updatePosition, true);

    return () => {
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
    };
  }, [isVisible, updatePosition]);

  if (!tooltip) {
    return children;
  }

  return (
    <div
      ref={containerRef}
      className="relative inline-flex"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onFocus={handleFocus}
      onBlur={handleBlur}
    >
      {children}

      {/* Indicator dot */}
      {showIndicator && !isDismissed && (
        <TooltipIndicator show className="absolute -top-1 -right-1" size="sm" />
      )}

      {/* Tooltip */}
      {isVisible && (
        <div
          ref={tooltipRef}
          className="fixed z-[80] w-64 bg-white dark:bg-surface-800 rounded-lg shadow-xl border border-surface-200 dark:border-surface-700 overflow-hidden"
          style={{
            left: `${position.x}px`,
            top: `${position.y}px`,
          }}
          role="tooltip"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-surface-100 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50">
            <div className="flex items-center gap-2">
              <InformationCircleIcon className="w-4 h-4 text-aura-500" />
              <span className="text-sm font-medium text-surface-900 dark:text-surface-100">
                {tooltip.title}
              </span>
            </div>
            <button
              onClick={handleDismiss}
              className="p-0.5 rounded text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
              aria-label="Dismiss tooltip"
            >
              <XMarkIcon className="w-4 h-4" />
            </button>
          </div>

          {/* Content */}
          <div className="px-3 py-2">
            <p className="text-xs text-surface-600 dark:text-surface-400">
              {tooltip.content}
            </p>
          </div>

          {/* Dismiss hint */}
          <div className="px-3 py-1.5 text-center text-[10px] text-surface-400 dark:text-surface-500 border-t border-surface-100 dark:border-surface-700">
            Click <XMarkIcon className="inline w-3 h-3" /> to hide permanently
          </div>
        </div>
      )}
    </div>
  );
};

export default FeatureTooltip;
