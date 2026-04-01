/**
 * Project Aura - Autonomy Policies Tab Component
 *
 * Displays and manages autonomy policy presets (ADR-032).
 * Allows selection of active policy and configuration of HITL thresholds.
 */

import { useState, useEffect } from 'react';
import {
  ShieldExclamationIcon,
  ShieldCheckIcon,
  BoltIcon,
  ScaleIcon,
  ChartBarIcon,
  ExclamationTriangleIcon,
  WrenchScrewdriverIcon,
  CheckCircleIcon,
  ArrowPathIcon,
  InformationCircleIcon,
  LockClosedIcon,
  LockOpenIcon,
  ChevronDownIcon,
  ChevronUpIcon,
} from '@heroicons/react/24/outline';

import {
  getPolicies,
  POLICY_PRESETS,
  AUTONOMY_LEVEL_CONFIG,
  DEFAULT_POLICY,
} from '../../services/autonomyApi';

// Icon mapping
const ICONS = {
  ShieldExclamationIcon,
  ShieldCheckIcon,
  BoltIcon,
  ScaleIcon,
  ChartBarIcon,
  ExclamationTriangleIcon,
  WrenchScrewdriverIcon,
};

// Color styles following design system
const COLOR_STYLES = {
  critical: {
    bg: 'bg-critical-50 dark:bg-critical-900/20',
    border: 'border-critical-200 dark:border-critical-800',
    text: 'text-critical-700 dark:text-critical-400',
    iconBg: 'bg-critical-100 dark:bg-critical-900/30',
    ring: 'ring-critical-500',
  },
  high: {
    bg: 'bg-warning-50 dark:bg-warning-900/20',
    border: 'border-warning-200 dark:border-warning-800',
    text: 'text-warning-700 dark:text-warning-400',
    iconBg: 'bg-warning-100 dark:bg-warning-900/30',
    ring: 'ring-warning-500',
  },
  warning: {
    bg: 'bg-warning-50 dark:bg-warning-900/20',
    border: 'border-warning-200 dark:border-warning-800',
    text: 'text-warning-700 dark:text-warning-400',
    iconBg: 'bg-warning-100 dark:bg-warning-900/30',
    ring: 'ring-warning-500',
  },
  aura: {
    bg: 'bg-aura-50 dark:bg-aura-900/20',
    border: 'border-aura-200 dark:border-aura-800',
    text: 'text-aura-700 dark:text-aura-400',
    iconBg: 'bg-aura-100 dark:bg-aura-900/30',
    ring: 'ring-aura-500',
  },
  olive: {
    bg: 'bg-olive-50 dark:bg-olive-900/20',
    border: 'border-olive-200 dark:border-olive-800',
    text: 'text-olive-700 dark:text-olive-400',
    iconBg: 'bg-olive-100 dark:bg-olive-900/30',
    ring: 'ring-olive-500',
  },
  surface: {
    bg: 'bg-surface-50 dark:bg-surface-800',
    border: 'border-surface-200 dark:border-surface-700',
    text: 'text-surface-700 dark:text-surface-400',
    iconBg: 'bg-surface-100 dark:bg-surface-700',
    ring: 'ring-surface-500',
  },
};

/**
 * Policy Preset Card Component
 */
function PolicyPresetCard({ preset, presetKey, isActive, onSelect, isLoading }) {
  const Icon = ICONS[preset.icon] || ShieldCheckIcon;
  const colors = COLOR_STYLES[preset.color] || COLOR_STYLES.aura;

  return (
    <button
      onClick={() => onSelect(presetKey)}
      disabled={isLoading}
      className={`
        relative w-full text-left p-4 rounded-xl border-2 transition-all duration-200 ease-[var(--ease-tahoe)]
        ${isActive
          ? `${colors.border} ${colors.bg} backdrop-blur-sm ring-2 ${colors.ring} shadow-[var(--shadow-glass)]`
          : 'border-surface-200/50 dark:border-surface-700/30 bg-white dark:bg-surface-800 backdrop-blur-xl hover:border-surface-300/60 dark:hover:border-surface-600/40 hover:shadow-[var(--shadow-glass)]'
        }
        ${isLoading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
      `}
    >
      {isActive && (
        <div className="absolute top-3 right-3">
          <CheckCircleIcon className={`h-5 w-5 ${colors.text}`} />
        </div>
      )}

      <div className="flex items-start gap-3">
        <div className={`p-2 rounded-lg ${isActive ? colors.iconBg : 'bg-surface-100 dark:bg-surface-700'}`}>
          <Icon className={`h-5 w-5 ${isActive ? colors.text : 'text-surface-600 dark:text-surface-400'}`} />
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="font-semibold text-surface-900 dark:text-surface-100">
            {preset.name}
          </h4>
          <p className="text-sm text-surface-500 dark:text-surface-400 mt-0.5">
            {preset.description}
          </p>
          <div className="flex items-center gap-3 mt-2 text-xs text-surface-500 dark:text-surface-400">
            <span className={`flex items-center gap-1 ${preset.hitlEnabled ? 'text-olive-600 dark:text-olive-400' : 'text-warning-600 dark:text-warning-400'}`}>
              {preset.hitlEnabled ? (
                <LockClosedIcon className="h-3.5 w-3.5" />
              ) : (
                <LockOpenIcon className="h-3.5 w-3.5" />
              )}
              {preset.hitlEnabled ? 'HITL Enabled' : 'HITL Disabled'}
            </span>
            <span className="text-surface-400">|</span>
            <span>{preset.useCase}</span>
          </div>
        </div>
      </div>
    </button>
  );
}

/**
 * Active Policy Details Panel
 */
function ActivePolicyDetails({ policy, onToggleHITL, isLoading }) {
  const [expanded, setExpanded] = useState(false);
  const levelConfig = AUTONOMY_LEVEL_CONFIG[policy.default_level] || AUTONOMY_LEVEL_CONFIG.critical_hitl;
  const colors = COLOR_STYLES[levelConfig.color] || COLOR_STYLES.aura;

  return (
    <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 overflow-hidden shadow-[var(--shadow-glass)]">
      {/* Header */}
      <div className="p-6 border-b border-surface-100/50 dark:border-surface-700/30">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
              Active Policy: {policy.name}
            </h3>
            <p className="text-sm text-surface-500 dark:text-surface-400 mt-1">
              {policy.description}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${colors.bg} ${colors.text}`}>
              {levelConfig.label}
            </span>
          </div>
        </div>
      </div>

      {/* HITL Toggle */}
      <div className="p-6 border-b border-surface-100/50 dark:border-surface-700/30">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${policy.hitl_enabled ? 'bg-olive-100 dark:bg-olive-900/30' : 'bg-warning-100 dark:bg-warning-900/30'}`}>
              {policy.hitl_enabled ? (
                <LockClosedIcon className="h-5 w-5 text-olive-600 dark:text-olive-400" />
              ) : (
                <LockOpenIcon className="h-5 w-5 text-warning-600 dark:text-warning-400" />
              )}
            </div>
            <div>
              <p className="font-medium text-surface-900 dark:text-surface-100">
                Human-in-the-Loop
              </p>
              <p className="text-sm text-surface-500 dark:text-surface-400">
                {policy.hitl_enabled
                  ? 'Approvals required based on autonomy level'
                  : 'Only guardrails require approval'}
              </p>
            </div>
          </div>
          <button
            onClick={() => onToggleHITL(!policy.hitl_enabled)}
            disabled={isLoading}
            className={`
              relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent
              transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2 dark:focus:ring-offset-surface-800
              ${policy.hitl_enabled ? 'bg-olive-600' : 'bg-surface-200 dark:bg-surface-600'}
              ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}
            `}
          >
            <span
              className={`
                pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0
                transition duration-200 ease-in-out
                ${policy.hitl_enabled ? 'translate-x-5' : 'translate-x-0'}
              `}
            />
          </button>
        </div>
      </div>

      {/* Expandable Details */}
      <div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full p-4 flex items-center justify-between text-surface-600 dark:text-surface-400 hover:bg-surface-50 dark:hover:bg-surface-700 transition-all duration-200 ease-[var(--ease-tahoe)]"
        >
          <span className="text-sm font-medium">Policy Details</span>
          {expanded ? (
            <ChevronUpIcon className="h-4 w-4" />
          ) : (
            <ChevronDownIcon className="h-4 w-4" />
          )}
        </button>

        {expanded && (
          <div className="px-6 pb-6 space-y-4">
            {/* Guardrails */}
            <div>
              <h4 className="text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                Guardrails (Always Require Approval)
              </h4>
              <div className="flex flex-wrap gap-2">
                {policy.guardrails.map((guardrail) => (
                  <span
                    key={guardrail}
                    className="px-2 py-1 bg-critical-100 dark:bg-critical-900/30 text-critical-700 dark:text-critical-400 rounded text-xs font-medium"
                  >
                    {guardrail.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            </div>

            {/* Severity Overrides */}
            {Object.keys(policy.severity_overrides).length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                  Severity Overrides
                </h4>
                <div className="space-y-1">
                  {Object.entries(policy.severity_overrides).map(([severity, level]) => (
                    <div key={severity} className="flex items-center justify-between text-sm">
                      <span className="text-surface-600 dark:text-surface-400">{severity}</span>
                      <span className="font-medium text-surface-900 dark:text-surface-100">
                        {AUTONOMY_LEVEL_CONFIG[level]?.label || level}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Metadata */}
            <div className="pt-4 border-t border-surface-100/50 dark:border-surface-700/30">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-surface-500 dark:text-surface-400">Policy ID</span>
                  <p className="font-mono text-surface-900 dark:text-surface-100">{policy.policy_id}</p>
                </div>
                <div>
                  <span className="text-surface-500 dark:text-surface-400">Last Updated</span>
                  <p className="text-surface-900 dark:text-surface-100">
                    {new Date(policy.updated_at).toLocaleDateString('en-US', {
                      month: 'short',
                      day: 'numeric',
                      year: 'numeric',
                    })}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Autonomy Level Comparison Table
 */
function AutonomyLevelComparison() {
  const levels = [
    { key: 'full_hitl', critical: true, high: true, medium: true, low: true },
    { key: 'critical_hitl', critical: true, high: true, medium: false, low: false },
    { key: 'audit_only', critical: true, high: false, medium: false, low: false },
    { key: 'full_autonomous', critical: false, high: false, medium: false, low: false },
  ];

  return (
    <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 p-6 shadow-[var(--shadow-glass)]">
      <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4">
        Autonomy Level Comparison
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-surface-100/50 dark:border-surface-700/30">
              <th className="text-left py-2 pr-4 font-medium text-surface-600 dark:text-surface-400">Level</th>
              <th className="text-center py-2 px-4 font-medium text-critical-600 dark:text-critical-400">Critical</th>
              <th className="text-center py-2 px-4 font-medium text-warning-600 dark:text-warning-400">High</th>
              <th className="text-center py-2 px-4 font-medium text-warning-600 dark:text-warning-400">Medium</th>
              <th className="text-center py-2 px-4 font-medium text-olive-600 dark:text-olive-400">Low</th>
            </tr>
          </thead>
          <tbody>
            {levels.map((level) => {
              const config = AUTONOMY_LEVEL_CONFIG[level.key];
              return (
                <tr key={level.key} className="border-b border-surface-100 dark:border-surface-700/50 last:border-0">
                  <td className="py-3 pr-4">
                    <span className="font-medium text-surface-900 dark:text-surface-100">
                      {config.label}
                    </span>
                  </td>
                  {['critical', 'high', 'medium', 'low'].map((severity) => (
                    <td key={severity} className="text-center py-3 px-4">
                      {level[severity] ? (
                        <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-critical-100 dark:bg-critical-900/30">
                          <LockClosedIcon className="h-4 w-4 text-critical-600 dark:text-critical-400" />
                        </span>
                      ) : (
                        <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-olive-100 dark:bg-olive-900/30">
                          <CheckCircleIcon className="h-4 w-4 text-olive-600 dark:text-olive-400" />
                        </span>
                      )}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-surface-500 dark:text-surface-400 mt-4">
        <LockClosedIcon className="inline h-3 w-3 mr-1" />
        = Requires HITL Approval
        <CheckCircleIcon className="inline h-3 w-3 ml-4 mr-1" />
        = Auto-Approved (Logged)
      </p>
    </div>
  );
}

/**
 * Main Autonomy Policies Tab Component
 */
export default function AutonomyPoliciesTab({ onSuccess, onError }) {
  const [policy, setPolicy] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [selectedPreset, setSelectedPreset] = useState(null);

  // Organization ID (would come from context in real app)
  const organizationId = 'org-aura-001';

  // Load policy on mount only
  useEffect(() => {
    loadPolicy();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadPolicy = async () => {
    setLoading(true);
    try {
      const policies = await getPolicies(organizationId);
      const activePolicy = policies.find(p => p.is_active) || policies[0] || DEFAULT_POLICY;
      setPolicy(activePolicy);
      setSelectedPreset(activePolicy.preset_name || 'balanced');
    } catch (err) {
      onError?.(`Failed to load autonomy policy: ${err.message}`);
      setPolicy(DEFAULT_POLICY);
      setSelectedPreset('balanced');
    } finally {
      setLoading(false);
    }
  };

  const handlePresetSelect = async (presetKey) => {
    if (presetKey === selectedPreset) return;

    setSaving(true);
    try {
      // In a real implementation, this would update the policy
      const preset = POLICY_PRESETS[presetKey];
      const updatedPolicy = {
        ...policy,
        name: preset.name,
        description: preset.description,
        default_level: preset.defaultLevel,
        hitl_enabled: preset.hitlEnabled,
        preset_name: presetKey,
        updated_at: new Date().toISOString(),
      };

      setPolicy(updatedPolicy);
      setSelectedPreset(presetKey);
      onSuccess?.(`Applied ${preset.name} policy preset`);
    } catch (err) {
      onError?.(`Failed to apply preset: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleToggleHITL = async (enabled) => {
    setSaving(true);
    try {
      const updatedPolicy = {
        ...policy,
        hitl_enabled: enabled,
        updated_at: new Date().toISOString(),
      };
      setPolicy(updatedPolicy);
      onSuccess?.(`HITL ${enabled ? 'enabled' : 'disabled'}`);
    } catch (err) {
      onError?.(`Failed to toggle HITL: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <ArrowPathIcon className="h-8 w-8 text-aura-500 animate-spin" />
        <span className="ml-3 text-surface-600 dark:text-surface-400">
          Loading autonomy settings...
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Introduction */}
      <div className="flex items-start gap-3 p-4 bg-aura-50/80 dark:bg-aura-900/20 backdrop-blur-sm border border-aura-200/50 dark:border-aura-800/50 rounded-xl shadow-[var(--shadow-glass)]">
        <InformationCircleIcon className="h-5 w-5 text-aura-600 dark:text-aura-400 flex-shrink-0 mt-0.5" />
        <div>
          <h4 className="font-medium text-aura-800 dark:text-aura-200">Autonomy Framework (ADR-032)</h4>
          <p className="text-sm text-aura-700 dark:text-aura-300 mt-1">
            Configure how much human oversight is required for autonomous operations.
            Select a preset policy or customize HITL requirements for your organization.
          </p>
        </div>
      </div>

      {/* Active Policy Details */}
      {policy && (
        <ActivePolicyDetails
          policy={policy}
          onToggleHITL={handleToggleHITL}
          isLoading={saving}
        />
      )}

      {/* Policy Presets */}
      <div>
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4">
          Policy Presets
        </h3>
        <p className="text-sm text-surface-600 dark:text-surface-400 mb-4">
          Select a preset that matches your organization's security and compliance requirements.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Object.entries(POLICY_PRESETS).map(([key, preset]) => (
            <PolicyPresetCard
              key={key}
              preset={preset}
              presetKey={key}
              isActive={selectedPreset === key}
              onSelect={handlePresetSelect}
              isLoading={saving}
            />
          ))}
        </div>
      </div>

      {/* Autonomy Level Comparison - with clearance for chat button */}
      <div className="mb-24">
        <AutonomyLevelComparison />
      </div>
    </div>
  );
}
