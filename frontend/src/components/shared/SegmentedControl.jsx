/**
 * SegmentedControl Component
 *
 * Apple-style segmented control for selecting between discrete options.
 * Supports keyboard navigation and is fully accessible.
 *
 * @module components/shared/SegmentedControl
 */

import React, { useRef } from 'react';
import PropTypes from 'prop-types';

/**
 * SegmentedControl - Toggle between discrete options
 *
 * @param {Object} props
 * @param {Array<{value: string, label: string, disabled?: boolean}>} props.options - Available options
 * @param {string} props.value - Currently selected value
 * @param {Function} props.onChange - Callback when selection changes
 * @param {'sm' | 'md' | 'lg'} [props.size='md'] - Control size
 * @param {boolean} [props.fullWidth=false] - Expand to full width
 * @param {string} [props.className] - Additional CSS classes
 * @param {string} [props.ariaLabel] - Accessible label for the control group
 */
function SegmentedControl({
  options,
  value,
  onChange,
  size = 'md',
  fullWidth = false,
  className = '',
  ariaLabel = 'Options',
}) {
  const controlRef = useRef(null);

  const sizeClasses = {
    sm: 'px-2 py-1 text-xs',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-2.5 text-base',
  };

  const containerSizeClasses = {
    sm: 'p-0.5',
    md: 'p-1',
    lg: 'p-1',
  };

  const handleKeyDown = (e, index) => {
    const enabledOptions = options.filter((opt) => !opt.disabled);
    const currentEnabledIndex = enabledOptions.findIndex((opt) => opt.value === value);

    switch (e.key) {
      case 'ArrowLeft':
      case 'ArrowUp':
        e.preventDefault();
        if (currentEnabledIndex > 0) {
          onChange(enabledOptions[currentEnabledIndex - 1].value);
        }
        break;
      case 'ArrowRight':
      case 'ArrowDown':
        e.preventDefault();
        if (currentEnabledIndex < enabledOptions.length - 1) {
          onChange(enabledOptions[currentEnabledIndex + 1].value);
        }
        break;
      case 'Home':
        e.preventDefault();
        onChange(enabledOptions[0].value);
        break;
      case 'End':
        e.preventDefault();
        onChange(enabledOptions[enabledOptions.length - 1].value);
        break;
      default:
        break;
    }
  };

  return (
    <div
      ref={controlRef}
      role="radiogroup"
      aria-label={ariaLabel}
      className={`
        inline-flex rounded-lg
        bg-surface-100 dark:bg-surface-700
        ${containerSizeClasses[size]}
        ${fullWidth ? 'w-full' : ''}
        ${className}
      `}
    >
      {options.map((option, index) => {
        const isSelected = value === option.value;
        const isDisabled = option.disabled;

        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={isSelected}
            aria-disabled={isDisabled}
            tabIndex={isSelected ? 0 : -1}
            disabled={isDisabled}
            onClick={() => !isDisabled && onChange(option.value)}
            onKeyDown={(e) => handleKeyDown(e, index)}
            className={`
              ${sizeClasses[size]}
              font-medium rounded-md transition-all
              focus:outline-none focus-visible:ring-2 focus-visible:ring-aura-500
              ${fullWidth ? 'flex-1' : ''}
              ${
                isSelected
                  ? 'bg-aura-600 text-white shadow-sm'
                  : 'text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-200'
              }
              ${isDisabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
            `}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

SegmentedControl.propTypes = {
  options: PropTypes.arrayOf(
    PropTypes.shape({
      value: PropTypes.string.isRequired,
      label: PropTypes.string.isRequired,
      disabled: PropTypes.bool,
    })
  ).isRequired,
  value: PropTypes.string.isRequired,
  onChange: PropTypes.func.isRequired,
  size: PropTypes.oneOf(['sm', 'md', 'lg']),
  fullWidth: PropTypes.bool,
  className: PropTypes.string,
  ariaLabel: PropTypes.string,
};

export default SegmentedControl;
