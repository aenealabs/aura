/**
 * Autonomy Tab Component
 *
 * Displays the current autonomy configuration including:
 * - Current autonomy level indicator
 * - HITL settings
 * - Severity and operation overrides
 * - Active guardrails
 * - Decision stats (auto-approved vs HITL required)
 */

import { memo } from 'react';
import {
  CpuChipIcon,
  UserIcon,
  ShieldCheckIcon,
  CheckCircleIcon,
  ClockIcon,
} from '@heroicons/react/24/outline';
import { ProgressChart } from '../ui/Charts';

// Autonomy level definitions
const AUTONOMY_LEVELS = {
  full_hitl: {
    label: 'Full HITL',
    description: 'All actions require human approval before execution.',
    color: 'critical',
    icon: UserIcon,
    order: 1,
  },
  critical_hitl: {
    label: 'Critical HITL',
    description: 'Critical severity actions require human approval. Others execute with audit.',
    color: 'warning',
    icon: ShieldCheckIcon,
    order: 2,
  },
  audit_only: {
    label: 'Audit Only',
    description: 'All actions execute but are logged for audit review.',
    color: 'aura',
    icon: ClockIcon,
    order: 3,
  },
  full_autonomous: {
    label: 'Full Autonomous',
    description: 'All actions execute automatically without human intervention.',
    color: 'olive',
    icon: CpuChipIcon,
    order: 4,
  },
};

/**
 * Autonomy Level Indicator Component
 */
const AutonomyLevelIndicator = memo(function AutonomyLevelIndicator({ currentLevel }) {
  const levelInfo = AUTONOMY_LEVELS[currentLevel] || AUTONOMY_LEVELS.critical_hitl;
  const LevelIcon = levelInfo.icon;

  // Progress position (1-4)
  const progressPercent = (levelInfo.order / 4) * 100;

  const colorClasses = {
    critical: {
      bg: 'bg-critical-100 dark:bg-critical-900/30',
      text: 'text-critical-600 dark:text-critical-400',
      border: 'border-critical-500',
      fill: 'bg-critical-500',
    },
    warning: {
      bg: 'bg-warning-100 dark:bg-warning-900/30',
      text: 'text-warning-600 dark:text-warning-400',
      border: 'border-warning-500',
      fill: 'bg-warning-500',
    },
    aura: {
      bg: 'bg-aura-100 dark:bg-aura-900/30',
      text: 'text-aura-600 dark:text-aura-400',
      border: 'border-aura-500',
      fill: 'bg-aura-500',
    },
    olive: {
      bg: 'bg-olive-100 dark:bg-olive-900/30',
      text: 'text-olive-600 dark:text-olive-400',
      border: 'border-olive-500',
      fill: 'bg-olive-500',
    },
  };

  const colors = colorClasses[levelInfo.color] || colorClasses.aura;

  return (
    <div className="glass-card p-6">
      <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4">
        Current Autonomy Level
      </h3>

      {/* Level Display */}
      <div className="flex items-center gap-4 mb-6">
        <div className={`p-4 rounded-xl ${colors.bg}`}>
          <LevelIcon className={`w-8 h-8 ${colors.text}`} />
        </div>
        <div>
          <h4 className={`text-2xl font-bold ${colors.text}`}>
            {levelInfo.label}
          </h4>
          <p className="text-surface-600 dark:text-surface-400 mt-1">
            {levelInfo.description}
          </p>
        </div>
      </div>

      {/* Level Scale */}
      <div className="relative pt-8 pb-4">
        {/* Scale bar */}
        <div className="h-2 bg-surface-200 dark:bg-surface-700 rounded-full">
          <div
            className={`h-full rounded-full ${colors.fill} transition-all duration-500`}
            style={{ width: `${progressPercent}%` }}
          />
        </div>

        {/* Scale labels */}
        <div className="flex justify-between mt-4">
          {Object.entries(AUTONOMY_LEVELS).map(([key, level]) => (
            <div
              key={key}
              className={`text-center flex-1 ${
                key === currentLevel
                  ? colors.text + ' font-semibold'
                  : 'text-surface-400'
              }`}
            >
              <div className={`
                w-3 h-3 rounded-full mx-auto mb-1
                ${key === currentLevel ? colors.fill : 'bg-surface-300 dark:bg-surface-600'}
              `} />
              <span className="text-xs">{level.label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
});

/**
 * Guardrails List Component
 */
const GuardrailsList = memo(function GuardrailsList({ guardrails }) {
  if (!guardrails?.length) {
    return (
      <div className="text-sm text-surface-500 dark:text-surface-400">
        No guardrails configured
      </div>
    );
  }

  // No scroll - guardrails are fixed categories, card shows all contents
  return (
    <div className="space-y-2">
      {guardrails.map((guardrail) => (
        <div
          key={guardrail}
          className="flex items-center gap-2 p-3 rounded-lg bg-surface-50 dark:bg-surface-800"
        >
          <ShieldCheckIcon className="w-4 h-4 text-aura-500" />
          <span className="text-sm text-surface-700 dark:text-surface-300">
            {guardrail.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
          </span>
        </div>
      ))}
    </div>
  );
});

/**
 * Overrides Section Component
 */
const OverridesSection = memo(function OverridesSection({ title, overrides, enableScroll = false }) {
  const entries = Object.entries(overrides || {});

  if (entries.length === 0) {
    return (
      <div className="glass-card-subtle p-4">
        <h4 className="font-medium text-surface-900 dark:text-surface-100 mb-2">
          {title}
        </h4>
        <p className="text-sm text-surface-500 dark:text-surface-400">
          No overrides configured
        </p>
      </div>
    );
  }

  // Enable scroll when there are 6+ entries and scroll is enabled
  const shouldScroll = enableScroll && entries.length >= 6;

  return (
    <div className="glass-card-subtle p-4">
      <h4 className="font-medium text-surface-900 dark:text-surface-100 mb-3">
        {title}
      </h4>
      <div className={`
        space-y-2
        ${shouldScroll ? 'max-h-[240px] overflow-y-auto pr-2 scrollbar-thin' : ''}
      `}>
        {entries.map(([key, value]) => (
          <div
            key={key}
            className="flex items-center justify-between p-2 rounded-lg bg-white dark:bg-surface-700"
          >
            <span className="text-sm text-surface-700 dark:text-surface-300">
              {key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
            </span>
            <span className={`
              text-sm font-medium px-2 py-0.5 rounded
              ${value === 'full_hitl' ? 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400' : ''}
              ${value === 'critical_hitl' ? 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400' : ''}
              ${value === 'audit_only' ? 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400' : ''}
              ${value === 'full_autonomous' ? 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400' : ''}
            `}>
              {value.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
});

/**
 * Decision Stats Component
 */
const DecisionStats = memo(function DecisionStats({ autonomy }) {
  const autoApproved = autonomy?.auto_approved_24h || 0;
  const hitlRequired = autonomy?.hitl_required_24h || 0;
  const total = autoApproved + hitlRequired;
  const autoApprovedPercent = total > 0 ? Math.round((autoApproved / total) * 100) : 0;

  return (
    <div className="glass-card p-6">
      <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4">
        Decision Statistics (24h)
      </h3>

      <div className="flex items-center gap-8">
        <ProgressChart
          value={autoApproved}
          max={total || 1}
          label="Auto-Approved"
          color="olive"
          size={120}
          strokeWidth={12}
          showPercentage={false}
        />

        <div className="flex-1 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircleIcon className="w-5 h-5 text-olive-500" />
              <span className="text-surface-700 dark:text-surface-300">Auto-Approved</span>
            </div>
            <span className="text-xl font-bold text-olive-600 dark:text-olive-400">
              {autoApproved}
            </span>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <UserIcon className="w-5 h-5 text-warning-500" />
              <span className="text-surface-700 dark:text-surface-300">HITL Required</span>
            </div>
            <span className="text-xl font-bold text-warning-600 dark:text-warning-400">
              {hitlRequired}
            </span>
          </div>

          <div className="pt-2 border-t border-surface-200 dark:border-surface-700">
            <div className="flex items-center justify-between">
              <span className="text-surface-500 dark:text-surface-400">Automation Rate</span>
              <span className="font-semibold text-surface-900 dark:text-surface-100">
                {autoApprovedPercent}%
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
});

/**
 * Main Autonomy Tab Component
 */
export default function AutonomyTab({ autonomy, loading }) {
  if (loading) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-64 rounded-2xl" />
        <div className="grid grid-cols-2 gap-6">
          <div className="skeleton h-48 rounded-xl" />
          <div className="skeleton h-48 rounded-xl" />
        </div>
      </div>
    );
  }

  if (!autonomy) {
    return (
      <div className="text-center py-12 text-surface-500 dark:text-surface-400">
        No autonomy configuration available.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Autonomy Level Indicator */}
      <AutonomyLevelIndicator currentLevel={autonomy.current_level} />

      {/* Stats and Config Grid */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Decision Stats */}
        <DecisionStats autonomy={autonomy} />

        {/* HITL Status */}
        <div className="glass-card p-6">
          <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4">
            HITL Configuration
          </h3>

          <div className="space-y-4">
            <div className="flex items-center justify-between p-3 rounded-lg bg-surface-50 dark:bg-surface-800">
              <span className="text-surface-700 dark:text-surface-300">HITL Enabled</span>
              <span className={`
                px-3 py-1 rounded-full text-sm font-medium
                ${autonomy.hitl_enabled
                  ? 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400'
                  : 'bg-surface-200 text-surface-600 dark:bg-surface-700 dark:text-surface-400'
                }
              `}>
                {autonomy.hitl_enabled ? 'Yes' : 'No'}
              </span>
            </div>

            {autonomy.preset_name && (
              <div className="flex items-center justify-between p-3 rounded-lg bg-surface-50 dark:bg-surface-800">
                <span className="text-surface-700 dark:text-surface-300">Preset</span>
                <span className="text-sm font-medium text-aura-600 dark:text-aura-400">
                  {autonomy.preset_name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                </span>
              </div>
            )}

            {autonomy.last_hitl_decision && (
              <div className="flex items-center justify-between p-3 rounded-lg bg-surface-50 dark:bg-surface-800">
                <span className="text-surface-700 dark:text-surface-300">Last HITL Decision</span>
                <span className="text-sm text-surface-600 dark:text-surface-400">
                  {new Date(autonomy.last_hitl_decision).toLocaleString()}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Guardrails and Overrides */}
      <div className="grid md:grid-cols-3 gap-6">
        {/* Active Guardrails (fixed categories - left position) */}
        <div className="glass-card-subtle p-4">
          <h4 className="font-medium text-surface-900 dark:text-surface-100 mb-3">
            Active Guardrails
          </h4>
          <GuardrailsList guardrails={autonomy.active_guardrails} />
        </div>

        {/* Severity Overrides (fixed categories - center position) */}
        <OverridesSection
          title="Severity Overrides"
          overrides={autonomy.severity_overrides}
        />

        {/* Operation Overrides (dynamic - right position, with scroll) */}
        <OverridesSection
          title="Operation Overrides"
          overrides={autonomy.operation_overrides}
          enableScroll={true}
        />
      </div>
    </div>
  );
}
