/**
 * AdvancedGuardrailSettings Component (ADR-069)
 *
 * Progressive disclosure panel for granular guardrail configuration.
 * Provides power users with fine-grained control over HITL thresholds,
 * trust requirements, and explanation verbosity.
 *
 * @module components/guardrails/AdvancedGuardrailSettings
 */

import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  ChevronDownIcon,
  ChevronUpIcon,
  LockClosedIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';
import { SegmentedControl, Tooltip } from '../shared';

/**
 * HITL sensitivity levels with descriptions
 */
const HITL_LEVELS = [
  { value: 0, label: 'Low', description: 'Fewer interruptions, more autonomous operations' },
  { value: 1, label: 'Medium', description: 'Balanced human oversight and automation' },
  { value: 2, label: 'High', description: 'More human review, fewer auto-approvals' },
  { value: 3, label: 'Critical-Only', description: 'Only critical operations require approval' },
];

/**
 * Trust level options for context verification
 */
const TRUST_LEVELS = [
  { value: 'all', label: 'All Sources' },
  { value: 'low', label: 'Low+' },
  { value: 'medium', label: 'Medium+' },
  { value: 'high', label: 'High Only' },
];

/**
 * Explanation verbosity options
 */
const VERBOSITY_LEVELS = [
  { value: 'minimal', label: 'Minimal' },
  { value: 'standard', label: 'Standard' },
  { value: 'detailed', label: 'Detailed' },
  { value: 'debug', label: 'Debug' },
];

/**
 * Verbosity descriptions
 */
const VERBOSITY_DESCRIPTIONS = {
  minimal: 'Brief summaries for routine decisions',
  standard: 'Reasoning steps + alternatives for significant decisions',
  detailed: 'Full reasoning chains with confidence intervals',
  debug: 'Complete audit trail with all intermediate steps',
};

/**
 * Reviewer type options
 */
const REVIEWER_TYPES = [
  { value: 'team_lead', label: 'Team Lead' },
  { value: 'security_team', label: 'Security Team' },
  { value: 'architect', label: 'Architect' },
  { value: 'auto_escalate', label: 'Auto-escalate' },
];

/**
 * RangeSlider - Custom slider with labeled stops
 */
function RangeSlider({ value, onChange, levels, disabled, locked, lockedReason }) {
  const currentLevel = levels.find((l) => l.value === value) || levels[0];

  return (
    <div className={`space-y-2 ${disabled || locked ? 'opacity-50' : ''}`}>
      {/* Labels */}
      <div className="flex justify-between text-xs text-surface-500 dark:text-surface-400">
        {levels.map((level) => (
          <span
            key={level.value}
            className={value === level.value ? 'font-medium text-aura-600 dark:text-aura-400' : ''}
          >
            {level.label}
          </span>
        ))}
      </div>

      {/* Slider */}
      <div className="relative">
        {locked && (
          <div className="absolute inset-0 flex items-center justify-center z-10">
            <Tooltip content={lockedReason || 'Locked by compliance'}>
              <LockClosedIcon className="w-5 h-5 text-surface-500" />
            </Tooltip>
          </div>
        )}
        <input
          type="range"
          min={0}
          max={levels.length - 1}
          value={value}
          onChange={(e) => onChange(parseInt(e.target.value, 10))}
          disabled={disabled || locked}
          className="w-full h-2 bg-surface-200 dark:bg-surface-700 rounded-lg
                     appearance-none cursor-pointer accent-aura-600
                     disabled:cursor-not-allowed"
        />
      </div>

      {/* Description */}
      <p className="text-sm text-surface-600 dark:text-surface-400">
        {currentLevel.description}
      </p>
    </div>
  );
}

RangeSlider.propTypes = {
  value: PropTypes.number.isRequired,
  onChange: PropTypes.func.isRequired,
  levels: PropTypes.arrayOf(
    PropTypes.shape({
      value: PropTypes.number.isRequired,
      label: PropTypes.string.isRequired,
      description: PropTypes.string,
    })
  ).isRequired,
  disabled: PropTypes.bool,
  locked: PropTypes.bool,
  lockedReason: PropTypes.string,
};

/**
 * SettingSection - Wrapper for individual settings
 */
function SettingSection({ title, description, children, locked, lockedReason }) {
  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between">
        <div>
          <h4 className="text-sm font-medium text-surface-900 dark:text-surface-100 flex items-center gap-2">
            {title}
            {locked && (
              <Tooltip content={lockedReason || 'Locked by compliance requirements'}>
                <LockClosedIcon className="w-4 h-4 text-surface-500" />
              </Tooltip>
            )}
          </h4>
          {description && (
            <p className="text-xs text-surface-500 dark:text-surface-400 mt-0.5">
              {description}
            </p>
          )}
        </div>
      </div>
      {children}
    </div>
  );
}

SettingSection.propTypes = {
  title: PropTypes.string.isRequired,
  description: PropTypes.string,
  children: PropTypes.node.isRequired,
  locked: PropTypes.bool,
  lockedReason: PropTypes.string,
};

/**
 * AdvancedGuardrailSettings - Main component
 *
 * @param {Object} props
 * @param {Object} props.settings - Current settings values
 * @param {Function} props.onSettingsChange - Callback when any setting changes
 * @param {Object} [props.lockedSettings={}] - Settings locked by compliance
 * @param {boolean} [props.defaultExpanded=false] - Whether to start expanded
 * @param {string} [props.className] - Additional CSS classes
 */
function AdvancedGuardrailSettings({
  settings,
  onSettingsChange,
  lockedSettings = {},
  defaultExpanded = false,
  className = '',
}) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  const handleSettingChange = (key, value) => {
    onSettingsChange({
      ...settings,
      [key]: value,
    });
  };

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        overflow-hidden
        ${className}
      `}
    >
      {/* Header - Collapsible trigger */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-3
                   hover:bg-surface-50 dark:hover:bg-surface-700/50
                   transition-colors"
        aria-expanded={isExpanded}
        aria-controls="advanced-settings-content"
      >
        <span className="font-medium text-surface-900 dark:text-surface-100">
          Advanced Settings
        </span>
        {isExpanded ? (
          <ChevronUpIcon className="w-5 h-5 text-surface-500" />
        ) : (
          <ChevronDownIcon className="w-5 h-5 text-surface-500" />
        )}
      </button>

      {/* Content */}
      {isExpanded && (
        <div
          id="advanced-settings-content"
          className="px-4 pb-4 space-y-6 border-t border-surface-200 dark:border-surface-700 pt-4 max-h-[400px] overflow-y-auto"
        >
          {/* HITL Escalation Sensitivity */}
          <SettingSection
            title="HITL Escalation Sensitivity"
            description="Control how often operations require human approval"
            locked={lockedSettings.hitlSensitivity}
            lockedReason={lockedSettings.hitlSensitivityReason}
          >
            <RangeSlider
              value={settings.hitlSensitivity || 1}
              onChange={(v) => handleSettingChange('hitlSensitivity', v)}
              levels={HITL_LEVELS}
              locked={lockedSettings.hitlSensitivity}
              lockedReason={lockedSettings.hitlSensitivityReason}
            />
            <div className="flex justify-between text-xs text-surface-500 dark:text-surface-400 mt-1">
              <span>Fewer interruptions</span>
              <span>More human oversight</span>
            </div>
          </SettingSection>

          {/* Context Trust Requirements */}
          <SettingSection
            title="Context Trust Requirements"
            description="Minimum trust level for accepting context sources"
            locked={lockedSettings.trustLevel}
            lockedReason={lockedSettings.trustLevelReason}
          >
            <SegmentedControl
              options={TRUST_LEVELS}
              value={settings.trustLevel || 'medium'}
              onChange={(v) => handleSettingChange('trustLevel', v)}
              fullWidth
              ariaLabel="Context trust level"
            />
            <p className="text-xs text-surface-500 dark:text-surface-400 mt-2">
              Accept context from sources with{' '}
              <span className="font-medium">
                {TRUST_LEVELS.find((l) => l.value === settings.trustLevel)?.label || 'Medium+'}
              </span>{' '}
              trust or higher
            </p>
          </SettingSection>

          {/* Explanation Verbosity */}
          <SettingSection
            title="Explanation Verbosity"
            description="How detailed AI explanations should be"
            locked={lockedSettings.verbosity}
            lockedReason={lockedSettings.verbosityReason}
          >
            <SegmentedControl
              options={VERBOSITY_LEVELS}
              value={settings.verbosity || 'standard'}
              onChange={(v) => handleSettingChange('verbosity', v)}
              fullWidth
              ariaLabel="Explanation verbosity level"
            />
            <p className="text-xs text-surface-500 dark:text-surface-400 mt-2">
              {VERBOSITY_DESCRIPTIONS[settings.verbosity || 'standard']}
            </p>
          </SettingSection>

          {/* Quarantine Review Delegation */}
          <SettingSection
            title="Quarantine Review Delegation"
            description="Who reviews quarantined content and decisions"
            locked={lockedSettings.reviewerType}
            lockedReason={lockedSettings.reviewerTypeReason}
          >
            <div className="relative">
              <select
                value={settings.reviewerType || 'team_lead'}
                onChange={(e) => handleSettingChange('reviewerType', e.target.value)}
                disabled={lockedSettings.reviewerType}
                className="w-full px-3 py-2 rounded-lg
                           border border-surface-300 dark:border-surface-600
                           bg-white dark:bg-surface-700
                           text-surface-900 dark:text-surface-100
                           focus:ring-2 focus:ring-aura-500 focus:border-aura-500
                           disabled:opacity-50 disabled:cursor-not-allowed
                           appearance-none cursor-pointer"
              >
                {REVIEWER_TYPES.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
              <ChevronDownIcon className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-surface-400 pointer-events-none" />
            </div>
          </SettingSection>

          {/* Additional toggles */}
          <div className="space-y-3 pt-4 border-t border-surface-200 dark:border-surface-700">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.enableAnomalyAlerts ?? true}
                onChange={(e) => handleSettingChange('enableAnomalyAlerts', e.target.checked)}
                disabled={lockedSettings.enableAnomalyAlerts}
                className="w-4 h-4 rounded border-surface-300 text-aura-600 focus:ring-aura-500
                           disabled:opacity-50 disabled:cursor-not-allowed"
              />
              <div>
                <span className="text-sm font-medium text-surface-900 dark:text-surface-100">
                  Enable anomaly alerts
                </span>
                <p className="text-xs text-surface-500 dark:text-surface-400">
                  Notify when unusual agent behavior is detected
                </p>
              </div>
            </label>

            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.auditAllDecisions ?? false}
                onChange={(e) => handleSettingChange('auditAllDecisions', e.target.checked)}
                disabled={lockedSettings.auditAllDecisions}
                className="w-4 h-4 rounded border-surface-300 text-aura-600 focus:ring-aura-500
                           disabled:opacity-50 disabled:cursor-not-allowed"
              />
              <div>
                <span className="text-sm font-medium text-surface-900 dark:text-surface-100">
                  Audit all decisions
                </span>
                <p className="text-xs text-surface-500 dark:text-surface-400">
                  Log every decision for compliance review (increases storage)
                </p>
              </div>
            </label>

            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.enableContradictionDetection ?? true}
                onChange={(e) => handleSettingChange('enableContradictionDetection', e.target.checked)}
                disabled={lockedSettings.enableContradictionDetection}
                className="w-4 h-4 rounded border-surface-300 text-aura-600 focus:ring-aura-500
                           disabled:opacity-50 disabled:cursor-not-allowed"
              />
              <div>
                <span className="text-sm font-medium text-surface-900 dark:text-surface-100">
                  Contradiction detection
                </span>
                <p className="text-xs text-surface-500 dark:text-surface-400">
                  Alert when reasoning conflicts with actions
                </p>
              </div>
            </label>
          </div>
        </div>
      )}
    </div>
  );
}

AdvancedGuardrailSettings.propTypes = {
  settings: PropTypes.shape({
    hitlSensitivity: PropTypes.number,
    trustLevel: PropTypes.string,
    verbosity: PropTypes.string,
    reviewerType: PropTypes.string,
    enableAnomalyAlerts: PropTypes.bool,
    auditAllDecisions: PropTypes.bool,
    enableContradictionDetection: PropTypes.bool,
  }).isRequired,
  onSettingsChange: PropTypes.func.isRequired,
  lockedSettings: PropTypes.object,
  defaultExpanded: PropTypes.bool,
  className: PropTypes.string,
};

export default AdvancedGuardrailSettings;
export { HITL_LEVELS, TRUST_LEVELS, VERBOSITY_LEVELS, REVIEWER_TYPES };
