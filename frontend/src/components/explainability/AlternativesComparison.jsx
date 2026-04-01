/**
 * AlternativesComparison Component (ADR-068)
 *
 * Side-by-side comparison of alternatives considered during decision-making.
 * Shows rejected options with reasons and confidence scores.
 *
 * @module components/explainability/AlternativesComparison
 */

import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  CheckCircleIcon,
  XCircleIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  ScaleIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';
import { ConfidenceBadge } from '../shared';

/**
 * AlternativeCard - Individual alternative option display
 */
function AlternativeCard({ alternative, isSelected, isExpanded, onToggle }) {
  const { name, description, confidence, pros = [], cons = [], rejectionReason } = alternative;

  return (
    <div
      className={`
        rounded-xl border transition-all
        ${isSelected
          ? 'border-olive-300 dark:border-olive-700 bg-olive-50 dark:bg-olive-900/20'
          : 'border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800'
        }
      `}
    >
      {/* Header */}
      <button
        onClick={onToggle}
        className="w-full p-4 flex items-center justify-between text-left"
      >
        <div className="flex items-center gap-3">
          {isSelected ? (
            <div className="p-1.5 rounded-full bg-olive-100 dark:bg-olive-800">
              <CheckCircleIcon className="w-5 h-5 text-olive-600 dark:text-olive-400" />
            </div>
          ) : (
            <div className="p-1.5 rounded-full bg-surface-100 dark:bg-surface-700">
              <XCircleIcon className="w-5 h-5 text-surface-400 dark:text-surface-500" />
            </div>
          )}
          <div>
            <div className="flex items-center gap-2">
              <span className="font-medium text-surface-900 dark:text-surface-100">
                {name}
              </span>
              {isSelected && (
                <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-olive-100 dark:bg-olive-800 text-olive-700 dark:text-olive-300">
                  Selected
                </span>
              )}
            </div>
            <p className="text-sm text-surface-600 dark:text-surface-400 mt-0.5">
              {description}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <ConfidenceBadge value={confidence} />
          {isExpanded ? (
            <ChevronUpIcon className="w-5 h-5 text-surface-400" />
          ) : (
            <ChevronDownIcon className="w-5 h-5 text-surface-400" />
          )}
        </div>
      </button>

      {/* Expanded content */}
      {isExpanded && (
        <div className="px-4 pb-4 border-t border-surface-200 dark:border-surface-700 pt-4">
          <div className="grid grid-cols-2 gap-4">
            {/* Pros */}
            <div>
              <h5 className="text-xs font-medium text-olive-600 dark:text-olive-400 uppercase tracking-wide mb-2">
                Advantages
              </h5>
              {pros.length > 0 ? (
                <ul className="space-y-1.5">
                  {pros.map((pro, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-2 text-sm text-surface-700 dark:text-surface-300"
                    >
                      <CheckCircleIcon className="w-4 h-4 text-olive-500 flex-shrink-0 mt-0.5" />
                      {pro}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-surface-500 dark:text-surface-400 italic">
                  No advantages identified
                </p>
              )}
            </div>

            {/* Cons */}
            <div>
              <h5 className="text-xs font-medium text-critical-600 dark:text-critical-400 uppercase tracking-wide mb-2">
                Disadvantages
              </h5>
              {cons.length > 0 ? (
                <ul className="space-y-1.5">
                  {cons.map((con, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-2 text-sm text-surface-700 dark:text-surface-300"
                    >
                      <XCircleIcon className="w-4 h-4 text-critical-500 flex-shrink-0 mt-0.5" />
                      {con}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-surface-500 dark:text-surface-400 italic">
                  No disadvantages identified
                </p>
              )}
            </div>
          </div>

          {/* Rejection reason (for non-selected alternatives) */}
          {!isSelected && rejectionReason && (
            <div className="mt-4 p-3 rounded-lg bg-surface-50 dark:bg-surface-900">
              <h5 className="text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wide mb-1">
                Why Not Selected
              </h5>
              <p className="text-sm text-surface-700 dark:text-surface-300">
                {rejectionReason}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

AlternativeCard.propTypes = {
  alternative: PropTypes.shape({
    name: PropTypes.string.isRequired,
    description: PropTypes.string.isRequired,
    confidence: PropTypes.number.isRequired,
    pros: PropTypes.arrayOf(PropTypes.string),
    cons: PropTypes.arrayOf(PropTypes.string),
    rejectionReason: PropTypes.string,
  }).isRequired,
  isSelected: PropTypes.bool.isRequired,
  isExpanded: PropTypes.bool.isRequired,
  onToggle: PropTypes.func.isRequired,
};

/**
 * ComparisonMatrix - Side-by-side criteria comparison
 */
function ComparisonMatrix({ alternatives, criteria, selectedIndex }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-surface-200 dark:border-surface-700">
            <th className="text-left py-3 px-4 font-medium text-surface-600 dark:text-surface-400">
              Criteria
            </th>
            {alternatives.map((alt, i) => (
              <th
                key={i}
                className={`text-center py-3 px-4 font-medium ${
                  i === selectedIndex
                    ? 'text-olive-600 dark:text-olive-400'
                    : 'text-surface-600 dark:text-surface-400'
                }`}
              >
                {alt.name}
                {i === selectedIndex && (
                  <CheckCircleIcon className="w-4 h-4 inline ml-1" />
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {criteria.map((criterion, i) => (
            <tr
              key={i}
              className="border-b border-surface-100 dark:border-surface-800"
            >
              <td className="py-3 px-4 text-surface-700 dark:text-surface-300">
                {criterion.name}
              </td>
              {alternatives.map((alt, j) => {
                const score = alt.criteriaScores?.[criterion.id] || 0;
                const getScoreColor = () => {
                  if (score >= 0.8) return 'text-olive-600 dark:text-olive-400';
                  if (score >= 0.6) return 'text-aura-600 dark:text-aura-400';
                  if (score >= 0.4) return 'text-warning-600 dark:text-warning-400';
                  return 'text-critical-600 dark:text-critical-400';
                };

                return (
                  <td
                    key={j}
                    className={`text-center py-3 px-4 font-medium ${getScoreColor()}`}
                  >
                    {Math.round((score || 0) * 100)}%
                  </td>
                );
              })}
            </tr>
          ))}
          {/* Total row */}
          <tr className="bg-surface-50 dark:bg-surface-900">
            <td className="py-3 px-4 font-medium text-surface-900 dark:text-surface-100">
              Overall Score
            </td>
            {alternatives.map((alt, i) => (
              <td
                key={i}
                className={`text-center py-3 px-4 font-bold ${
                  i === selectedIndex
                    ? 'text-olive-600 dark:text-olive-400'
                    : 'text-surface-700 dark:text-surface-300'
                }`}
              >
                {Math.round((alt.confidence || 0) * 100)}%
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  );
}

ComparisonMatrix.propTypes = {
  alternatives: PropTypes.arrayOf(
    PropTypes.shape({
      name: PropTypes.string.isRequired,
      confidence: PropTypes.number.isRequired,
      criteriaScores: PropTypes.object,
    })
  ).isRequired,
  criteria: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
      name: PropTypes.string.isRequired,
    })
  ).isRequired,
  selectedIndex: PropTypes.number.isRequired,
};

/**
 * AlternativesComparison - Main component
 *
 * @param {Object} props
 * @param {Array} props.alternatives - List of alternatives considered
 * @param {number} props.selectedIndex - Index of the selected alternative
 * @param {Array} [props.criteria] - Comparison criteria for matrix view
 * @param {string} [props.decisionRationale] - Overall decision rationale
 * @param {string} [props.className] - Additional CSS classes
 */
function AlternativesComparison({
  alternatives,
  selectedIndex,
  criteria = [],
  decisionRationale,
  className = '',
}) {
  const [expandedIndex, setExpandedIndex] = useState(selectedIndex);
  const [viewMode, setViewMode] = useState('cards'); // 'cards' or 'matrix'

  const toggleExpand = (index) => {
    setExpandedIndex(expandedIndex === index ? -1 : index);
  };

  if (!alternatives || alternatives.length === 0) {
    return (
      <div className={`p-6 text-center ${className}`}>
        <ScaleIcon className="w-12 h-12 mx-auto text-surface-300 dark:text-surface-600" />
        <p className="mt-2 text-surface-600 dark:text-surface-400">
          No alternatives to compare
        </p>
      </div>
    );
  }

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
            Alternatives Considered
          </h3>
          <p className="text-sm text-surface-600 dark:text-surface-400 mt-1">
            {alternatives.length} option{alternatives.length !== 1 ? 's' : ''} evaluated
          </p>
        </div>

        {/* View toggle */}
        {criteria.length > 0 && (
          <div className="flex rounded-lg border border-surface-200 dark:border-surface-700 overflow-hidden">
            <button
              onClick={() => setViewMode('cards')}
              className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                viewMode === 'cards'
                  ? 'bg-aura-600 text-white'
                  : 'bg-white dark:bg-surface-800 text-surface-600 dark:text-surface-400 hover:bg-surface-50 dark:hover:bg-surface-700'
              }`}
            >
              Cards
            </button>
            <button
              onClick={() => setViewMode('matrix')}
              className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                viewMode === 'matrix'
                  ? 'bg-aura-600 text-white'
                  : 'bg-white dark:bg-surface-800 text-surface-600 dark:text-surface-400 hover:bg-surface-50 dark:hover:bg-surface-700'
              }`}
            >
              Matrix
            </button>
          </div>
        )}
      </div>

      {/* Decision rationale */}
      {decisionRationale && (
        <div className="p-4 rounded-xl bg-aura-50 dark:bg-aura-900/20 border border-aura-200 dark:border-aura-800">
          <div className="flex items-start gap-3">
            <ScaleIcon className="w-5 h-5 text-aura-600 dark:text-aura-400 flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="text-sm font-medium text-aura-700 dark:text-aura-300">
                Decision Rationale
              </h4>
              <p className="text-sm text-aura-600 dark:text-aura-400 mt-1">
                {decisionRationale}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Content based on view mode */}
      {viewMode === 'cards' ? (
        <div className="space-y-3">
          {/* Selected alternative first */}
          {alternatives.map((alt, index) => (
            <AlternativeCard
              key={index}
              alternative={alt}
              isSelected={index === selectedIndex}
              isExpanded={expandedIndex === index}
              onToggle={() => toggleExpand(index)}
            />
          ))}
        </div>
      ) : (
        <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 overflow-hidden">
          <ComparisonMatrix
            alternatives={alternatives}
            criteria={criteria}
            selectedIndex={selectedIndex}
          />
        </div>
      )}

      {/* Warning if close alternatives */}
      {alternatives.length > 1 && (
        (() => {
          const scores = alternatives.map((a) => a.confidence);
          const maxScore = Math.max(...scores);
          const secondMaxScore = scores
            .filter((s) => s !== maxScore)
            .sort((a, b) => b - a)[0];
          const margin = maxScore - (secondMaxScore || 0);

          if (margin < 0.1) {
            return (
              <div className="flex items-start gap-3 p-3 rounded-lg bg-warning-50 dark:bg-warning-900/20 border border-warning-200 dark:border-warning-800">
                <ExclamationTriangleIcon className="w-5 h-5 text-warning-600 dark:text-warning-400 flex-shrink-0" />
                <div className="text-sm">
                  <span className="font-medium text-warning-700 dark:text-warning-300">
                    Close decision:
                  </span>{' '}
                  <span className="text-warning-600 dark:text-warning-400">
                    The top alternatives have similar scores (within {Math.round(margin * 100)}%).
                    Consider reviewing the criteria weights.
                  </span>
                </div>
              </div>
            );
          }
          return null;
        })()
      )}
    </div>
  );
}

AlternativesComparison.propTypes = {
  alternatives: PropTypes.arrayOf(
    PropTypes.shape({
      name: PropTypes.string.isRequired,
      description: PropTypes.string.isRequired,
      confidence: PropTypes.number.isRequired,
      pros: PropTypes.arrayOf(PropTypes.string),
      cons: PropTypes.arrayOf(PropTypes.string),
      rejectionReason: PropTypes.string,
      criteriaScores: PropTypes.object,
    })
  ).isRequired,
  selectedIndex: PropTypes.number.isRequired,
  criteria: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
      name: PropTypes.string.isRequired,
    })
  ),
  decisionRationale: PropTypes.string,
  className: PropTypes.string,
};

export default AlternativesComparison;
