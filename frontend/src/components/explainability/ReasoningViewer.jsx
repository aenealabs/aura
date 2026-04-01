/**
 * ReasoningViewer Component (ADR-068)
 *
 * Displays step-by-step reasoning chains with evidence linking.
 * Shows how AI arrived at a decision with confidence per step.
 *
 * @module components/explainability/ReasoningViewer
 */

import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  ChevronDownIcon,
  ChevronUpIcon,
  CheckCircleIcon,
  DocumentTextIcon,
  LinkIcon,
} from '@heroicons/react/24/outline';
import { ConfidenceBadge } from '../shared';

/**
 * ReasoningStep - Individual step in the reasoning chain
 */
function ReasoningStep({ step, stepNumber, isLast, isExpanded, onToggle, compact }) {
  const showExpanded = isExpanded || !compact;

  return (
    <div className="relative">
      {/* Connector line to next step */}
      {!isLast && (
        <div
          className={`absolute left-6 w-0.5 bg-surface-300 dark:bg-surface-600 ${
            compact ? 'top-12 h-6' : 'top-16 h-8'
          }`}
        />
      )}

      <div
        className={`
          bg-white dark:bg-surface-800 rounded-xl border
          border-surface-200 dark:border-surface-700
          ${compact ? 'p-3' : 'p-4'}
          ${compact && !showExpanded ? 'cursor-pointer hover:border-surface-300 dark:hover:border-surface-600' : ''}
        `}
        onClick={compact && !showExpanded ? onToggle : undefined}
        role={compact && !showExpanded ? 'button' : undefined}
        tabIndex={compact && !showExpanded ? 0 : undefined}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <div
              className={`
                rounded-full bg-aura-100 dark:bg-aura-900/30
                flex items-center justify-center
                text-aura-600 dark:text-aura-400 font-medium
                ${compact ? 'w-6 h-6 text-xs' : 'w-8 h-8 text-sm'}
              `}
            >
              {stepNumber}
            </div>
            <span
              className={`font-medium text-surface-900 dark:text-surface-100 ${
                compact ? 'text-sm' : ''
              }`}
            >
              Step {stepNumber}
              {step.title && `: ${step.title}`}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <ConfidenceBadge value={step.confidence} size={compact ? 'sm' : 'md'} />
            {compact && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onToggle();
                }}
                className="p-1 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300"
              >
                {showExpanded ? (
                  <ChevronUpIcon className="w-4 h-4" />
                ) : (
                  <ChevronDownIcon className="w-4 h-4" />
                )}
              </button>
            )}
          </div>
        </div>

        {/* Description */}
        <p
          className={`text-surface-700 dark:text-surface-300 ${compact ? 'text-sm' : ''} ${
            showExpanded ? 'mb-4' : ''
          }`}
        >
          {showExpanded
            ? step.description
            : step.description.length > 100
            ? `${step.description.slice(0, 100)}...`
            : step.description}
        </p>

        {showExpanded && (
          <>
            {/* Evidence */}
            {step.evidence && step.evidence.length > 0 && (
              <div className="mb-4">
                <h5
                  className={`font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wide mb-2 ${
                    compact ? 'text-xs' : 'text-xs'
                  }`}
                >
                  Evidence
                </h5>
                <ul className="space-y-1.5">
                  {step.evidence.map((evidence, i) => (
                    <li
                      key={i}
                      className={`flex items-start gap-2 text-surface-600 dark:text-surface-400 ${
                        compact ? 'text-xs' : 'text-sm'
                      }`}
                    >
                      <CheckCircleIcon className="w-4 h-4 text-olive-500 flex-shrink-0 mt-0.5" />
                      {evidence}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* References */}
            {step.references && step.references.length > 0 && (
              <div className="flex items-center gap-2 flex-wrap">
                <span
                  className={`text-surface-500 dark:text-surface-400 ${
                    compact ? 'text-xs' : 'text-xs'
                  }`}
                >
                  References:
                </span>
                {step.references.map((ref, i) => (
                  <button
                    key={i}
                    className={`
                      flex items-center gap-1 rounded
                      bg-surface-100 dark:bg-surface-700
                      text-aura-600 dark:text-aura-400
                      hover:bg-aura-50 dark:hover:bg-aura-900/20
                      transition-colors
                      ${compact ? 'px-1.5 py-0.5 text-xs' : 'px-2 py-1 text-xs'}
                    `}
                    onClick={(e) => {
                      e.stopPropagation();
                      // Handle reference click - could open document, link, etc.
                    }}
                  >
                    {ref.type === 'document' ? (
                      <DocumentTextIcon className="w-3 h-3" />
                    ) : (
                      <LinkIcon className="w-3 h-3" />
                    )}
                    {ref.label}
                  </button>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

ReasoningStep.propTypes = {
  step: PropTypes.shape({
    title: PropTypes.string,
    description: PropTypes.string.isRequired,
    confidence: PropTypes.number.isRequired,
    evidence: PropTypes.arrayOf(PropTypes.string),
    references: PropTypes.arrayOf(
      PropTypes.shape({
        type: PropTypes.oneOf(['document', 'link', 'code']),
        label: PropTypes.string.isRequired,
        url: PropTypes.string,
      })
    ),
  }).isRequired,
  stepNumber: PropTypes.number.isRequired,
  isLast: PropTypes.bool.isRequired,
  isExpanded: PropTypes.bool,
  onToggle: PropTypes.func,
  compact: PropTypes.bool,
};

/**
 * ReasoningViewer - Main component
 *
 * @param {Object} props
 * @param {Object} props.decision - Decision with reasoning chain
 * @param {boolean} [props.compact=false] - Compact display mode
 * @param {boolean} [props.defaultExpanded=true] - Whether steps start expanded
 * @param {string} [props.className] - Additional CSS classes
 */
function ReasoningViewer({
  decision,
  compact = false,
  defaultExpanded = true,
  className = '',
}) {
  const [expandAll, setExpandAll] = useState(defaultExpanded);
  const [expandedSteps, setExpandedSteps] = useState(
    new Set(
      defaultExpanded
        ? (decision.reasoningChain || []).map((_, i) => i)
        : []
    )
  );

  const toggleStep = (index) => {
    setExpandedSteps((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  const toggleAll = () => {
    if (expandAll) {
      setExpandedSteps(new Set());
    } else {
      setExpandedSteps(
        new Set((decision.reasoningChain || []).map((_, i) => i))
      );
    }
    setExpandAll(!expandAll);
  };

  const reasoningChain = decision.reasoningChain || [];

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Header */}
      {!compact && (
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
            Reasoning Chain
          </h3>
          <button
            onClick={toggleAll}
            className="text-sm text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300"
          >
            {expandAll ? 'Collapse All' : 'Expand All'}
          </button>
        </div>
      )}

      {/* Input */}
      {decision.input && !compact && (
        <div className="bg-surface-50 dark:bg-surface-900 rounded-lg p-4">
          <h4 className="text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wide mb-2">
            Input
          </h4>
          <p className="text-surface-700 dark:text-surface-300">{decision.input}</p>
        </div>
      )}

      {/* Reasoning steps */}
      <div className={compact ? 'space-y-2' : 'space-y-4'}>
        {reasoningChain.map((step, index) => (
          <ReasoningStep
            key={index}
            step={step}
            stepNumber={index + 1}
            isLast={index === reasoningChain.length - 1}
            isExpanded={expandedSteps.has(index)}
            onToggle={() => toggleStep(index)}
            compact={compact}
          />
        ))}
      </div>

      {/* Output */}
      {decision.output && !compact && (
        <div className="bg-olive-50 dark:bg-olive-900/20 rounded-lg p-4 border border-olive-200 dark:border-olive-800">
          <h4 className="text-xs font-medium text-olive-600 dark:text-olive-400 uppercase tracking-wide mb-2">
            Output
          </h4>
          <p className="text-surface-900 dark:text-surface-100 font-medium">
            {decision.output}
          </p>
          {decision.outputConfidence && (
            <div className="mt-2 flex items-center gap-2">
              <span className="text-sm text-surface-600 dark:text-surface-400">
                Final confidence:
              </span>
              <ConfidenceBadge value={decision.outputConfidence} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

ReasoningViewer.propTypes = {
  decision: PropTypes.shape({
    input: PropTypes.string,
    reasoningChain: PropTypes.arrayOf(
      PropTypes.shape({
        title: PropTypes.string,
        description: PropTypes.string.isRequired,
        confidence: PropTypes.number.isRequired,
        evidence: PropTypes.arrayOf(PropTypes.string),
        references: PropTypes.array,
      })
    ).isRequired,
    output: PropTypes.string,
    outputConfidence: PropTypes.number,
  }).isRequired,
  compact: PropTypes.bool,
  defaultExpanded: PropTypes.bool,
  className: PropTypes.string,
};

export default ReasoningViewer;
