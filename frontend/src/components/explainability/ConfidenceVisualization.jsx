/**
 * ConfidenceVisualization Component (ADR-068)
 *
 * Displays confidence intervals with uncertainty visualization.
 * Shows point estimate, bounds, and uncertainty sources.
 *
 * @module components/explainability/ConfidenceVisualization
 */

import React from 'react';
import PropTypes from 'prop-types';
import {
  ExclamationTriangleIcon,
  InformationCircleIcon,
  CheckCircleIcon,
} from '@heroicons/react/24/outline';

/**
 * ConfidenceIntervalChart - Visual confidence interval display
 */
function ConfidenceIntervalChart({ interval }) {
  const { pointEstimate, lowerBound, upperBound } = interval;

  // Scale to percentages
  const lower = Math.round(lowerBound * 100);
  const point = Math.round(pointEstimate * 100);
  const upper = Math.round(upperBound * 100);

  // Determine color based on confidence
  const getPointColor = () => {
    if (point >= 85) return 'bg-olive-600';
    if (point >= 70) return 'bg-aura-600';
    if (point >= 50) return 'bg-warning-600';
    return 'bg-critical-600';
  };

  return (
    <div className="relative pt-10 pb-6">
      {/* Scale labels */}
      <div className="absolute top-0 left-0 right-0 flex justify-between text-xs text-surface-400">
        <span>0%</span>
        <span>25%</span>
        <span>50%</span>
        <span>75%</span>
        <span>100%</span>
      </div>

      {/* Track */}
      <div className="relative h-10 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden">
        {/* Confidence range (lower to upper) */}
        <div
          className="absolute top-2 bottom-2 bg-aura-200 dark:bg-aura-800 rounded-full transition-all"
          style={{
            left: `${lower}%`,
            width: `${Math.max(1, upper - lower)}%`,
          }}
        />

        {/* Lower bound marker */}
        <div
          className="absolute top-1 bottom-1 w-0.5 bg-surface-400 dark:bg-surface-500"
          style={{ left: `${lower}%` }}
        />

        {/* Upper bound marker */}
        <div
          className="absolute top-1 bottom-1 w-0.5 bg-surface-400 dark:bg-surface-500"
          style={{ left: `${upper}%` }}
        />

        {/* Point estimate marker */}
        <div
          className={`absolute top-0 bottom-0 w-1.5 rounded-full ${getPointColor()} transition-all`}
          style={{ left: `calc(${point}% - 3px)` }}
        >
          {/* Label above */}
          <div
            className={`absolute -top-8 left-1/2 -translate-x-1/2 px-2 py-1 rounded ${getPointColor()} text-white text-sm font-bold whitespace-nowrap`}
          >
            {point}%
          </div>
        </div>
      </div>

      {/* Bound labels */}
      <div className="flex justify-between mt-2 text-xs text-surface-500 dark:text-surface-400">
        <span style={{ marginLeft: `${Math.max(0, lower - 5)}%` }}>
          {lower}% Lower
        </span>
        <span style={{ marginRight: `${Math.max(0, 100 - upper - 10)}%` }}>
          Upper {upper}%
        </span>
      </div>
    </div>
  );
}

ConfidenceIntervalChart.propTypes = {
  interval: PropTypes.shape({
    pointEstimate: PropTypes.number.isRequired,
    lowerBound: PropTypes.number.isRequired,
    upperBound: PropTypes.number.isRequired,
  }).isRequired,
};

/**
 * UncertaintySource - Individual uncertainty factor
 */
function UncertaintySource({ source }) {
  const severityConfig = {
    high: {
      icon: ExclamationTriangleIcon,
      color: 'text-critical-500',
      bg: 'bg-critical-50 dark:bg-critical-900/20',
    },
    medium: {
      icon: ExclamationTriangleIcon,
      color: 'text-warning-500',
      bg: 'bg-warning-50 dark:bg-warning-900/20',
    },
    low: {
      icon: InformationCircleIcon,
      color: 'text-aura-500',
      bg: 'bg-aura-50 dark:bg-aura-900/20',
    },
  };

  const config = severityConfig[source.severity] || severityConfig.low;
  const Icon = config.icon;

  return (
    <div
      className={`flex items-center gap-3 p-3 rounded-lg ${config.bg} transition-colors`}
    >
      <Icon className={`w-5 h-5 flex-shrink-0 ${config.color}`} />
      <span className="flex-1 text-sm text-surface-700 dark:text-surface-300">
        {source.description}
      </span>
      <span className="text-sm font-medium text-surface-600 dark:text-surface-400">
        +{source.contribution}%
      </span>
    </div>
  );
}

UncertaintySource.propTypes = {
  source: PropTypes.shape({
    description: PropTypes.string.isRequired,
    contribution: PropTypes.number.isRequired,
    severity: PropTypes.oneOf(['high', 'medium', 'low']),
  }).isRequired,
};

/**
 * StepConfidenceBar - Confidence bar for individual step
 */
function StepConfidenceBar({ step, index }) {
  const percentage = Math.round(step.confidence * 100);

  const getBarColor = () => {
    if (percentage >= 85) return 'bg-olive-500';
    if (percentage >= 70) return 'bg-aura-500';
    if (percentage >= 50) return 'bg-warning-500';
    return 'bg-critical-500';
  };

  return (
    <div className="flex items-center gap-3">
      <span className="w-40 text-sm text-surface-600 dark:text-surface-400 truncate">
        Step {index + 1}: {step.title || step.description?.slice(0, 20)}
      </span>
      <div className="flex-1 h-3 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${getBarColor()}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className="w-12 text-sm font-medium text-surface-700 dark:text-surface-300 text-right">
        {percentage}%
      </span>
    </div>
  );
}

StepConfidenceBar.propTypes = {
  step: PropTypes.shape({
    title: PropTypes.string,
    description: PropTypes.string,
    confidence: PropTypes.number.isRequired,
  }).isRequired,
  index: PropTypes.number.isRequired,
};

/**
 * CalibrationStatus - Shows if confidence is well-calibrated
 */
function CalibrationStatus({ status, method }) {
  const statusConfig = {
    'well-calibrated': {
      icon: CheckCircleIcon,
      color: 'text-olive-600 dark:text-olive-400',
      label: 'Well-calibrated',
    },
    overconfident: {
      icon: ExclamationTriangleIcon,
      color: 'text-warning-600 dark:text-warning-400',
      label: 'Overconfident',
    },
    underconfident: {
      icon: InformationCircleIcon,
      color: 'text-aura-600 dark:text-aura-400',
      label: 'Underconfident',
    },
    unknown: {
      icon: InformationCircleIcon,
      color: 'text-surface-500',
      label: 'Unknown',
    },
  };

  const config = statusConfig[status] || statusConfig.unknown;
  const Icon = config.icon;

  return (
    <div className="flex items-center justify-between text-sm">
      <div className="flex items-center gap-2">
        <span className="text-surface-600 dark:text-surface-400">Calibration Status:</span>
        <div className={`flex items-center gap-1 ${config.color}`}>
          <Icon className="w-4 h-4" />
          <span className="font-medium">{config.label}</span>
        </div>
      </div>
      {method && (
        <span className="text-surface-500 dark:text-surface-400">
          Method: {method}
        </span>
      )}
    </div>
  );
}

CalibrationStatus.propTypes = {
  status: PropTypes.oneOf(['well-calibrated', 'overconfident', 'underconfident', 'unknown'])
    .isRequired,
  method: PropTypes.string,
};

/**
 * ConfidenceVisualization - Main component
 *
 * @param {Object} props
 * @param {Object} props.confidenceData - Confidence analysis data
 * @param {Array} [props.reasoningSteps] - Steps with individual confidence
 * @param {string} [props.className] - Additional CSS classes
 */
function ConfidenceVisualization({
  confidenceData,
  reasoningSteps = [],
  className = '',
}) {
  const {
    interval = { pointEstimate: 0.85, lowerBound: 0.71, upperBound: 0.94 },
    uncertaintySources = [],
    calibrationStatus = 'well-calibrated',
    calibrationMethod,
  } = confidenceData;

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div>
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
          Confidence Analysis
        </h3>
        <p className="text-sm text-surface-600 dark:text-surface-400 mt-1">
          Overall decision confidence with uncertainty breakdown
        </p>
      </div>

      {/* Main confidence interval */}
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4">
        <h4 className="text-sm font-medium text-surface-700 dark:text-surface-300 mb-4">
          Overall Decision Confidence
        </h4>
        <ConfidenceIntervalChart interval={interval} />
      </div>

      {/* Uncertainty sources */}
      {uncertaintySources.length > 0 && (
        <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4">
          <h4 className="text-sm font-medium text-surface-700 dark:text-surface-300 mb-3">
            Uncertainty Sources
          </h4>
          <div className="space-y-2">
            {uncertaintySources.map((source, index) => (
              <UncertaintySource key={index} source={source} />
            ))}
          </div>
        </div>
      )}

      {/* Calibration status */}
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4">
        <CalibrationStatus status={calibrationStatus} method={calibrationMethod} />
      </div>

      {/* Per-step confidence */}
      {reasoningSteps.length > 0 && (
        <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4">
          <h4 className="text-sm font-medium text-surface-700 dark:text-surface-300 mb-4">
            Confidence by Reasoning Step
          </h4>
          <div className="space-y-3">
            {reasoningSteps.map((step, index) => (
              <StepConfidenceBar key={index} step={step} index={index} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

ConfidenceVisualization.propTypes = {
  confidenceData: PropTypes.shape({
    interval: PropTypes.shape({
      pointEstimate: PropTypes.number.isRequired,
      lowerBound: PropTypes.number.isRequired,
      upperBound: PropTypes.number.isRequired,
    }),
    uncertaintySources: PropTypes.arrayOf(
      PropTypes.shape({
        description: PropTypes.string.isRequired,
        contribution: PropTypes.number.isRequired,
        severity: PropTypes.string,
      })
    ),
    calibrationStatus: PropTypes.string,
    calibrationMethod: PropTypes.string,
  }).isRequired,
  reasoningSteps: PropTypes.arrayOf(
    PropTypes.shape({
      title: PropTypes.string,
      description: PropTypes.string,
      confidence: PropTypes.number.isRequired,
    })
  ),
  className: PropTypes.string,
};

export default ConfidenceVisualization;
export { ConfidenceIntervalChart };
