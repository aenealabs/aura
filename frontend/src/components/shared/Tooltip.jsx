/**
 * Tooltip Component
 *
 * Reusable tooltip for contextual help and information.
 * Supports multiple positions and accessible by default.
 *
 * @module components/shared/Tooltip
 */

import React, { useState, useRef, useEffect } from 'react';
import PropTypes from 'prop-types';

/**
 * Tooltip - Displays contextual information on hover
 *
 * @param {Object} props
 * @param {React.ReactNode} props.content - Tooltip content
 * @param {React.ReactNode} props.children - Trigger element
 * @param {'top' | 'bottom' | 'left' | 'right'} [props.position='top'] - Tooltip position
 * @param {number} [props.delay=200] - Show delay in ms
 * @param {string} [props.className] - Additional CSS classes
 */
function Tooltip({
  content,
  children,
  position = 'top',
  delay = 200,
  className = '',
}) {
  const [isVisible, setIsVisible] = useState(false);
  const [shouldRender, setShouldRender] = useState(false);
  const timeoutRef = useRef(null);
  const tooltipRef = useRef(null);

  const positionClasses = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left: 'right-full top-1/2 -translate-y-1/2 mr-2',
    right: 'left-full top-1/2 -translate-y-1/2 ml-2',
  };

  const arrowClasses = {
    top: 'top-full -mt-1 left-1/2 -translate-x-1/2',
    bottom: 'bottom-full -mb-1 left-1/2 -translate-x-1/2',
    left: 'left-full -ml-1 top-1/2 -translate-y-1/2',
    right: 'right-full -mr-1 top-1/2 -translate-y-1/2',
  };

  const handleMouseEnter = () => {
    timeoutRef.current = setTimeout(() => {
      setShouldRender(true);
      // Small delay to allow render before transition
      requestAnimationFrame(() => setIsVisible(true));
    }, delay);
  };

  const handleMouseLeave = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    setIsVisible(false);
    // Wait for transition to complete before unmounting
    setTimeout(() => setShouldRender(false), 150);
  };

  const handleFocus = () => handleMouseEnter();
  const handleBlur = () => handleMouseLeave();

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return (
    <div className={`relative inline-block ${className}`}>
      <div
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onFocus={handleFocus}
        onBlur={handleBlur}
      >
        {children}
      </div>

      {shouldRender && (
        <div
          ref={tooltipRef}
          role="tooltip"
          className={`
            absolute z-50 ${positionClasses[position]}
            px-2 py-1.5 text-xs font-medium
            text-white bg-surface-900 dark:bg-surface-100 dark:text-surface-900
            rounded-lg shadow-lg
            whitespace-nowrap
            transition-opacity duration-150
            ${isVisible ? 'opacity-100' : 'opacity-0'}
          `}
        >
          {content}
          {/* Arrow */}
          <div
            className={`
              absolute w-2 h-2
              bg-surface-900 dark:bg-surface-100
              transform rotate-45
              ${arrowClasses[position]}
            `}
          />
        </div>
      )}
    </div>
  );
}

Tooltip.propTypes = {
  content: PropTypes.node.isRequired,
  children: PropTypes.node.isRequired,
  position: PropTypes.oneOf(['top', 'bottom', 'left', 'right']),
  delay: PropTypes.number,
  className: PropTypes.string,
};

export default Tooltip;
