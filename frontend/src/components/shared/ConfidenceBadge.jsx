/**
 * ConfidenceBadge Component
 *
 * Displays a color-coded confidence percentage badge.
 * Used across Explainability Dashboard, Decision Explorer, and Reasoning Viewer.
 *
 * @module components/shared/ConfidenceBadge
 */

import React from 'react';
import PropTypes from 'prop-types';

/**
 * Get color classes based on confidence percentage
 * @param {number} percentage - Confidence percentage (0-100)
 * @returns {string} Tailwind CSS classes for colors
 */
function getConfidenceColor(percentage) {
  if (percentage >= 90) {
    return 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400';
  }
  if (percentage >= 75) {
    return 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400';
  }
  if (percentage >= 60) {
    return 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400';
  }
  return 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400';
}

/**
 * ConfidenceBadge - Displays confidence as a colored badge
 *
 * @param {Object} props
 * @param {number} props.value - Confidence value (0-1 or 0-100)
 * @param {'sm' | 'md' | 'lg'} [props.size='md'] - Badge size
 * @param {boolean} [props.showLabel=false] - Show "Confidence:" label
 * @param {string} [props.className] - Additional CSS classes
 */
function ConfidenceBadge({ value, size = 'md', showLabel = false, className = '' }) {
  // Normalize value to percentage (handle both 0-1 and 0-100 inputs)
  // Guard against undefined/null/NaN values
  const safeValue = value ?? 0;
  const percentage = safeValue <= 1 ? Math.round(safeValue * 100) : Math.round(safeValue);

  const sizeClasses = {
    sm: 'px-1.5 py-0.5 text-xs',
    md: 'px-2 py-1 text-sm',
    lg: 'px-3 py-1.5 text-base',
  };

  const colorClasses = getConfidenceColor(percentage);

  return (
    <span
      className={`
        inline-flex items-center gap-1 rounded-full font-medium
        ${colorClasses}
        ${sizeClasses[size]}
        ${className}
      `}
      role="status"
      aria-label={`Confidence: ${percentage}%`}
    >
      {showLabel && <span className="opacity-75">Confidence:</span>}
      {percentage}%
    </span>
  );
}

ConfidenceBadge.propTypes = {
  value: PropTypes.number.isRequired,
  size: PropTypes.oneOf(['sm', 'md', 'lg']),
  showLabel: PropTypes.bool,
  className: PropTypes.string,
};

export default ConfidenceBadge;
