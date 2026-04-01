/**
 * FilterChip Component
 *
 * Toggle-able filter chip for multi-select filtering.
 * Used in CapabilityGraphFilters, DecisionExplorer, and other filtering contexts.
 *
 * @module components/shared/FilterChip
 */

import React from 'react';
import PropTypes from 'prop-types';
import { XMarkIcon, CheckIcon } from '@heroicons/react/20/solid';

/**
 * FilterChip - Toggleable filter pill
 *
 * @param {Object} props
 * @param {string} props.label - Chip label text
 * @param {boolean} props.active - Whether the chip is selected
 * @param {Function} props.onChange - Callback when toggled
 * @param {string} [props.color] - Custom color (hex code or CSS color)
 * @param {boolean} [props.showIcon=true] - Show check/x icon
 * @param {boolean} [props.removable=false] - Show remove button instead of toggle
 * @param {Function} [props.onRemove] - Callback when remove button clicked
 * @param {'sm' | 'md'} [props.size='md'] - Chip size
 * @param {string} [props.className] - Additional CSS classes
 */
function FilterChip({
  label,
  active,
  onChange,
  color,
  showIcon = true,
  removable = false,
  onRemove,
  size = 'md',
  className = '',
}) {
  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs gap-1',
    md: 'px-3 py-1.5 text-sm gap-1.5',
  };

  const iconSizeClasses = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
  };

  const handleClick = () => {
    if (!removable) {
      onChange(!active);
    }
  };

  const handleRemove = (e) => {
    e.stopPropagation();
    if (onRemove) {
      onRemove();
    }
  };

  // Determine background color
  const getBackgroundStyle = () => {
    if (active && color) {
      return { backgroundColor: color };
    }
    return {};
  };

  return (
    <button
      type="button"
      role="switch"
      aria-checked={active}
      onClick={handleClick}
      style={getBackgroundStyle()}
      className={`
        inline-flex items-center rounded-full font-medium
        transition-all duration-150
        focus:outline-none focus-visible:ring-2 focus-visible:ring-aura-500 focus-visible:ring-offset-2
        ${sizeClasses[size]}
        ${
          active
            ? color
              ? 'text-white'
              : 'bg-aura-600 text-white hover:bg-aura-700'
            : 'bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-400 hover:bg-surface-200 dark:hover:bg-surface-600'
        }
        ${className}
      `}
    >
      {showIcon && active && !removable && (
        <CheckIcon className={iconSizeClasses[size]} aria-hidden="true" />
      )}

      <span>{label}</span>

      {removable && active && (
        <button
          type="button"
          onClick={handleRemove}
          className="ml-1 rounded-full hover:bg-white/20 p-0.5 transition-colors"
          aria-label={`Remove ${label} filter`}
        >
          <XMarkIcon className={iconSizeClasses[size]} aria-hidden="true" />
        </button>
      )}
    </button>
  );
}

FilterChip.propTypes = {
  label: PropTypes.string.isRequired,
  active: PropTypes.bool.isRequired,
  onChange: PropTypes.func.isRequired,
  color: PropTypes.string,
  showIcon: PropTypes.bool,
  removable: PropTypes.bool,
  onRemove: PropTypes.func,
  size: PropTypes.oneOf(['sm', 'md']),
  className: PropTypes.string,
};

export default FilterChip;
