/**
 * CapabilityGraphFilters Component (ADR-071)
 *
 * Filter panel for the Capability Graph visualization.
 * Allows filtering by agent type, tool classification, and escalation paths.
 *
 * @module components/capability/CapabilityGraphFilters
 */

import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  FunnelIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  XMarkIcon,
  ExclamationTriangleIcon,
  ShieldCheckIcon,
  ShieldExclamationIcon,
  EyeIcon,
  EyeSlashIcon,
} from '@heroicons/react/24/outline';

/**
 * Classification color mapping
 */
const CLASSIFICATION_CONFIG = {
  safe: {
    label: 'SAFE',
    color: 'bg-olive-500',
    textColor: 'text-olive-700 dark:text-olive-300',
    bgColor: 'bg-olive-100 dark:bg-olive-900/30',
    description: 'Read-only operations, no side effects',
  },
  monitoring: {
    label: 'MONITORING',
    color: 'bg-warning-500',
    textColor: 'text-warning-700 dark:text-warning-300',
    bgColor: 'bg-warning-100 dark:bg-warning-900/30',
    description: 'Observation tools with audit trails',
  },
  dangerous: {
    label: 'DANGEROUS',
    color: 'bg-orange-500',
    textColor: 'text-orange-700 dark:text-orange-300',
    bgColor: 'bg-orange-100 dark:bg-orange-900/30',
    description: 'Write operations requiring approval',
  },
  critical: {
    label: 'CRITICAL',
    color: 'bg-critical-500',
    textColor: 'text-critical-700 dark:text-critical-300',
    bgColor: 'bg-critical-100 dark:bg-critical-900/30',
    description: 'High-impact operations with strict controls',
  },
};

/**
 * Agent type options
 */
const AGENT_TYPES = [
  { id: 'coder', label: 'Coder', description: 'Code generation and modification' },
  { id: 'reviewer', label: 'Reviewer', description: 'Code review and analysis' },
  { id: 'validator', label: 'Validator', description: 'Testing and validation' },
  { id: 'security', label: 'Security', description: 'Security scanning' },
  { id: 'orchestrator', label: 'Orchestrator', description: 'Workflow coordination' },
];

/**
 * FilterSection - Collapsible filter section
 */
function FilterSection({ title, icon: Icon, children, defaultExpanded = true }) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  return (
    <div className="border-b border-surface-200 dark:border-surface-700 pb-4 mb-4 last:border-b-0 last:pb-0 last:mb-0">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between text-left mb-2"
      >
        <div className="flex items-center gap-2">
          {Icon && <Icon className="w-4 h-4 text-surface-500" />}
          <span className="text-sm font-medium text-surface-700 dark:text-surface-300">
            {title}
          </span>
        </div>
        {isExpanded ? (
          <ChevronUpIcon className="w-4 h-4 text-surface-400" />
        ) : (
          <ChevronDownIcon className="w-4 h-4 text-surface-400" />
        )}
      </button>
      {isExpanded && <div className="space-y-2">{children}</div>}
    </div>
  );
}

FilterSection.propTypes = {
  title: PropTypes.string.isRequired,
  icon: PropTypes.elementType,
  children: PropTypes.node.isRequired,
  defaultExpanded: PropTypes.bool,
};

/**
 * CheckboxFilter - Individual checkbox filter item
 */
function CheckboxFilter({ id, label, description, checked, onChange, color }) {
  return (
    <label className="flex items-start gap-3 cursor-pointer group">
      <div className="relative flex items-center justify-center mt-0.5">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(id, e.target.checked)}
          className="sr-only peer"
        />
        <div
          className={`
            w-4 h-4 rounded border-2 transition-colors
            ${checked
              ? `${color || 'bg-aura-600 border-aura-600'}`
              : 'border-surface-300 dark:border-surface-600 group-hover:border-surface-400'
            }
          `}
        />
        {checked && (
          <svg
            className="absolute w-3 h-3 text-white"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="3"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <span className="text-sm text-surface-700 dark:text-surface-300 block">
          {label}
        </span>
        {description && (
          <span className="text-xs text-surface-500 dark:text-surface-400">
            {description}
          </span>
        )}
      </div>
    </label>
  );
}

CheckboxFilter.propTypes = {
  id: PropTypes.string.isRequired,
  label: PropTypes.string.isRequired,
  description: PropTypes.string,
  checked: PropTypes.bool.isRequired,
  onChange: PropTypes.func.isRequired,
  color: PropTypes.string,
};

/**
 * ClassificationBadge - Visual badge for classification
 */
function ClassificationBadge({ classification, selected, onClick }) {
  const config = CLASSIFICATION_CONFIG[classification] || {};

  return (
    <button
      onClick={onClick}
      className={`
        flex items-center gap-2 px-3 py-2 rounded-lg border transition-all w-full text-left
        ${selected
          ? `${config.bgColor} border-current ${config.textColor}`
          : 'border-surface-200 dark:border-surface-700 hover:border-surface-300 dark:hover:border-surface-600'
        }
      `}
    >
      <span className={`w-3 h-3 rounded-full ${config.color}`} />
      <div className="flex-1 min-w-0">
        <span
          className={`text-sm font-medium block ${
            selected ? config.textColor : 'text-surface-700 dark:text-surface-300'
          }`}
        >
          {config.label}
        </span>
        <span className="text-xs text-surface-500 dark:text-surface-400 block">
          {config.description}
        </span>
      </div>
    </button>
  );
}

ClassificationBadge.propTypes = {
  classification: PropTypes.string.isRequired,
  selected: PropTypes.bool.isRequired,
  onClick: PropTypes.func.isRequired,
};

/**
 * CapabilityGraphFilters - Main component
 *
 * @param {Object} props
 * @param {Object} props.filters - Current filter state
 * @param {Function} props.onFilterChange - Callback when filters change
 * @param {Function} [props.onClearAll] - Callback to clear all filters
 * @param {boolean} [props.isCollapsible=true] - Whether the panel is collapsible
 * @param {string} [props.className] - Additional CSS classes
 */
function CapabilityGraphFilters({
  filters = {},
  onFilterChange,
  onClearAll,
  isCollapsible = true,
  className = '',
}) {
  const [isExpanded, setIsExpanded] = useState(true);

  const {
    agentTypes = [],
    classifications = ['safe', 'monitoring', 'dangerous', 'critical'],
    showEscalationPaths = true,
    showCoverageGaps = false,
    showToxicCombinations = false,
    riskThreshold = 0.5,
  } = filters;

  // Handle agent type toggle
  const handleAgentTypeChange = (agentId, checked) => {
    const newTypes = checked
      ? [...agentTypes, agentId]
      : agentTypes.filter((t) => t !== agentId);
    onFilterChange({ ...filters, agentTypes: newTypes });
  };

  // Handle classification toggle
  const handleClassificationToggle = (classification) => {
    const newClassifications = classifications.includes(classification)
      ? classifications.filter((c) => c !== classification)
      : [...classifications, classification];
    onFilterChange({ ...filters, classifications: newClassifications });
  };

  // Handle boolean toggle
  const handleToggle = (key) => {
    onFilterChange({ ...filters, [key]: !filters[key] });
  };

  // Handle risk threshold change
  const handleRiskThresholdChange = (value) => {
    onFilterChange({ ...filters, riskThreshold: parseFloat(value) });
  };

  // Check if any filters are active
  const hasActiveFilters =
    agentTypes.length > 0 ||
    classifications.length < 4 ||
    !showEscalationPaths ||
    showCoverageGaps ||
    showToxicCombinations ||
    riskThreshold !== 0.5;

  return (
    <div
      className={`bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 ${className}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center gap-2">
          <FunnelIcon className="w-5 h-5 text-surface-500" />
          <span className="font-medium text-surface-900 dark:text-surface-100">
            Filters
          </span>
          {hasActiveFilters && (
            <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-aura-100 dark:bg-aura-900 text-aura-700 dark:text-aura-300">
              Active
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {hasActiveFilters && onClearAll && (
            <button
              onClick={onClearAll}
              className="text-xs text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300"
            >
              Clear all
            </button>
          )}
          {isCollapsible && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="p-1 rounded hover:bg-surface-100 dark:hover:bg-surface-700"
            >
              {isExpanded ? (
                <ChevronUpIcon className="w-4 h-4 text-surface-400" />
              ) : (
                <ChevronDownIcon className="w-4 h-4 text-surface-400" />
              )}
            </button>
          )}
        </div>
      </div>

      {/* Filter content */}
      {(!isCollapsible || isExpanded) && (
        <div className="p-4">
          {/* Agent Types */}
          <FilterSection title="Agent Types" icon={ShieldCheckIcon}>
            <div className="space-y-2">
              {AGENT_TYPES.map((agent) => (
                <CheckboxFilter
                  key={agent.id}
                  id={agent.id}
                  label={agent.label}
                  description={agent.description}
                  checked={agentTypes.length === 0 || agentTypes.includes(agent.id)}
                  onChange={handleAgentTypeChange}
                />
              ))}
            </div>
          </FilterSection>

          {/* Tool Classifications */}
          <FilterSection title="Tool Classification">
            <div className="space-y-2">
              {Object.keys(CLASSIFICATION_CONFIG).map((classification) => (
                <ClassificationBadge
                  key={classification}
                  classification={classification}
                  selected={classifications.includes(classification)}
                  onClick={() => handleClassificationToggle(classification)}
                />
              ))}
            </div>
          </FilterSection>

          {/* Risk Analysis */}
          <FilterSection title="Risk Analysis" icon={ExclamationTriangleIcon}>
            <div className="space-y-3">
              <label className="flex items-center justify-between cursor-pointer">
                <div className="flex items-center gap-2">
                  {showEscalationPaths ? (
                    <EyeIcon className="w-4 h-4 text-aura-500" />
                  ) : (
                    <EyeSlashIcon className="w-4 h-4 text-surface-400" />
                  )}
                  <span className="text-sm text-surface-700 dark:text-surface-300">
                    Show Escalation Paths
                  </span>
                </div>
                <button
                  onClick={() => handleToggle('showEscalationPaths')}
                  className={`
                    relative inline-flex h-5 w-9 items-center rounded-full transition-colors
                    ${showEscalationPaths ? 'bg-aura-600' : 'bg-surface-300 dark:bg-surface-600'}
                  `}
                >
                  <span
                    className={`
                      inline-block h-4 w-4 transform rounded-full bg-white transition-transform
                      ${showEscalationPaths ? 'translate-x-4' : 'translate-x-0.5'}
                    `}
                  />
                </button>
              </label>

              <label className="flex items-center justify-between cursor-pointer">
                <div className="flex items-center gap-2">
                  <ShieldExclamationIcon className="w-4 h-4 text-warning-500" />
                  <span className="text-sm text-surface-700 dark:text-surface-300">
                    Highlight Coverage Gaps
                  </span>
                </div>
                <button
                  onClick={() => handleToggle('showCoverageGaps')}
                  className={`
                    relative inline-flex h-5 w-9 items-center rounded-full transition-colors
                    ${showCoverageGaps ? 'bg-aura-600' : 'bg-surface-300 dark:bg-surface-600'}
                  `}
                >
                  <span
                    className={`
                      inline-block h-4 w-4 transform rounded-full bg-white transition-transform
                      ${showCoverageGaps ? 'translate-x-4' : 'translate-x-0.5'}
                    `}
                  />
                </button>
              </label>

              <label className="flex items-center justify-between cursor-pointer">
                <div className="flex items-center gap-2">
                  <ExclamationTriangleIcon className="w-4 h-4 text-critical-500" />
                  <span className="text-sm text-surface-700 dark:text-surface-300">
                    Show Toxic Combinations
                  </span>
                </div>
                <button
                  onClick={() => handleToggle('showToxicCombinations')}
                  className={`
                    relative inline-flex h-5 w-9 items-center rounded-full transition-colors
                    ${showToxicCombinations ? 'bg-aura-600' : 'bg-surface-300 dark:bg-surface-600'}
                  `}
                >
                  <span
                    className={`
                      inline-block h-4 w-4 transform rounded-full bg-white transition-transform
                      ${showToxicCombinations ? 'translate-x-4' : 'translate-x-0.5'}
                    `}
                  />
                </button>
              </label>

              {/* Risk threshold slider */}
              <div className="pt-2">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-surface-500 dark:text-surface-400">
                    Risk Threshold
                  </span>
                  <span className="text-xs font-medium text-surface-700 dark:text-surface-300">
                    {Math.round(riskThreshold * 100)}%
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={riskThreshold}
                  onChange={(e) => handleRiskThresholdChange(e.target.value)}
                  className="w-full h-2 rounded-full appearance-none cursor-pointer
                             bg-surface-200 dark:bg-surface-700
                             [&::-webkit-slider-thumb]:appearance-none
                             [&::-webkit-slider-thumb]:w-4
                             [&::-webkit-slider-thumb]:h-4
                             [&::-webkit-slider-thumb]:rounded-full
                             [&::-webkit-slider-thumb]:bg-aura-600"
                />
                <div className="flex justify-between text-xs text-surface-400 mt-1">
                  <span>Low</span>
                  <span>High</span>
                </div>
              </div>
            </div>
          </FilterSection>
        </div>
      )}
    </div>
  );
}

CapabilityGraphFilters.propTypes = {
  filters: PropTypes.shape({
    agentTypes: PropTypes.arrayOf(PropTypes.string),
    classifications: PropTypes.arrayOf(PropTypes.string),
    showEscalationPaths: PropTypes.bool,
    showCoverageGaps: PropTypes.bool,
    showToxicCombinations: PropTypes.bool,
    riskThreshold: PropTypes.number,
  }),
  onFilterChange: PropTypes.func.isRequired,
  onClearAll: PropTypes.func,
  isCollapsible: PropTypes.bool,
  className: PropTypes.string,
};

export default CapabilityGraphFilters;
