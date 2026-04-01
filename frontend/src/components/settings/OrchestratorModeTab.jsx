/**
 * Project Aura - Orchestrator Mode Tab Component
 *
 * Configures orchestrator deployment modes (on-demand, warm pool, hybrid).
 * Manages agent spawn limits, timeouts, and DAG execution settings.
 */

import { useState, useEffect } from 'react';
import {
  CloudIcon,
  ServerStackIcon,
  CpuChipIcon,
  CheckCircleIcon,
  ArrowPathIcon,
  InformationCircleIcon,
  ClockIcon,
  CurrencyDollarIcon,
  BoltIcon,
  ChartBarIcon,
  Cog6ToothIcon,
} from '@heroicons/react/24/outline';

import {
  getOrchestratorSettings,
  updateOrchestratorSettings,
  switchDeploymentMode,
  getModeStatus,
  DEPLOYMENT_MODE_CONFIG,
  DEFAULT_ORCHESTRATOR_SETTINGS,
} from '../../services/orchestratorApi';

// Icon mapping
const ICONS = {
  CloudIcon,
  ServerStackIcon,
  CpuChipIcon,
};

// Color styles following design system
const COLOR_STYLES = {
  aura: {
    bg: 'bg-aura-50 dark:bg-aura-900/20',
    border: 'border-aura-200 dark:border-aura-800',
    text: 'text-aura-700 dark:text-aura-400',
    iconBg: 'bg-aura-100 dark:bg-aura-900/30',
    ring: 'ring-aura-500',
    button: 'bg-aura-600 hover:bg-aura-700',
  },
  olive: {
    bg: 'bg-olive-50 dark:bg-olive-900/20',
    border: 'border-olive-200 dark:border-olive-800',
    text: 'text-olive-700 dark:text-olive-400',
    iconBg: 'bg-olive-100 dark:bg-olive-900/30',
    ring: 'ring-olive-500',
    button: 'bg-olive-600 hover:bg-olive-700',
  },
  warning: {
    bg: 'bg-warning-50 dark:bg-warning-900/20',
    border: 'border-warning-200 dark:border-warning-800',
    text: 'text-warning-700 dark:text-warning-400',
    iconBg: 'bg-warning-100 dark:bg-warning-900/30',
    ring: 'ring-warning-500',
    button: 'bg-warning-600 hover:bg-warning-700',
  },
};

/**
 * Deployment Mode Card Component
 */
function DeploymentModeCard({ mode, config, isActive, onSelect, isLoading, disabled }) {
  const Icon = ICONS[config.icon] || CloudIcon;
  const colors = COLOR_STYLES[config.color] || COLOR_STYLES.aura;

  return (
    <div
      className={`
        relative rounded-xl border-2 transition-all duration-200
        ${isActive
          ? `${colors.border} ${colors.bg} ring-2 ${colors.ring}`
          : 'border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800'
        }
        ${disabled || isLoading ? 'opacity-50' : 'hover:border-surface-300 dark:hover:border-surface-600'}
      `}
    >
      {isActive && (
        <div className="absolute top-3 right-3">
          <CheckCircleIcon className={`h-5 w-5 ${colors.text}`} />
        </div>
      )}

      <div className="p-6">
        <div className="flex items-start gap-4 mb-4">
          <div className={`p-3 rounded-xl ${isActive ? colors.iconBg : 'bg-surface-100 dark:bg-surface-700'}`}>
            <Icon className={`h-6 w-6 ${isActive ? colors.text : 'text-surface-600 dark:text-surface-400'}`} />
          </div>
          <div className="flex-1">
            <h4 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
              {config.label}
            </h4>
            <p className="text-sm text-surface-500 dark:text-surface-400 mt-1">
              {config.description}
            </p>
          </div>
        </div>

        {/* Cost and Performance Metrics */}
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div className="flex items-center gap-2">
            <CurrencyDollarIcon className="h-4 w-4 text-surface-400" />
            <div>
              <p className="text-lg font-bold text-surface-900 dark:text-surface-100">
                ${config.baseCost}
                <span className="text-sm font-normal text-surface-500 dark:text-surface-400">/mo</span>
              </p>
              <p className="text-xs text-surface-500 dark:text-surface-400">Base Cost</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <ClockIcon className="h-4 w-4 text-surface-400" />
            <div>
              <p className="text-lg font-bold text-surface-900 dark:text-surface-100">
                {config.coldStart}
                <span className="text-sm font-normal text-surface-500 dark:text-surface-400">s</span>
              </p>
              <p className="text-xs text-surface-500 dark:text-surface-400">Cold Start</p>
            </div>
          </div>
        </div>

        {/* Recommended For */}
        <div className="mb-4">
          <p className="text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wide mb-2">
            Recommended For
          </p>
          <ul className="space-y-1">
            {config.recommended.slice(0, 3).map((item, idx) => (
              <li key={idx} className="flex items-start gap-2 text-sm text-surface-600 dark:text-surface-400">
                <CheckCircleIcon className="h-4 w-4 text-olive-500 mt-0.5 flex-shrink-0" />
                {item}
              </li>
            ))}
          </ul>
        </div>

        <button
          onClick={() => onSelect(mode)}
          disabled={isActive || isLoading || disabled}
          className={`
            w-full py-2.5 px-4 rounded-lg font-medium text-white transition-colors
            ${isActive
              ? 'bg-surface-400 dark:bg-surface-600 cursor-not-allowed'
              : isLoading || disabled
                ? 'bg-surface-400 dark:bg-surface-600 cursor-not-allowed'
                : colors.button
            }
          `}
        >
          {isActive ? 'Current Mode' : isLoading ? 'Switching...' : `Switch to ${config.label}`}
        </button>
      </div>
    </div>
  );
}

/**
 * Mode Status Display Component
 */
function ModeStatusDisplay({ status, settings: _settings }) {
  if (!status) return null;

  const modeConfig = DEPLOYMENT_MODE_CONFIG[status.current_mode];
  const colors = COLOR_STYLES[modeConfig?.color] || COLOR_STYLES.aura;

  return (
    <div className={`${colors.bg} ${colors.border} border rounded-xl p-6`}>
      <div className="flex items-center gap-4">
        <div className={`p-3 rounded-lg ${colors.iconBg}`}>
          {status.current_mode === 'warm_pool' || status.current_mode === 'hybrid' ? (
            <ServerStackIcon className={`h-6 w-6 ${colors.text}`} />
          ) : (
            <CloudIcon className={`h-6 w-6 ${colors.text}`} />
          )}
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className={`font-semibold ${colors.text}`}>Current Mode:</span>
            <span className="font-bold text-surface-900 dark:text-surface-100">
              {modeConfig?.label || status.current_mode}
            </span>
          </div>
          <div className="flex items-center gap-4 mt-2 text-sm text-surface-600 dark:text-surface-400">
            {status.warm_pool_replicas_desired > 0 && (
              <span className="flex items-center gap-1">
                <ServerStackIcon className="h-4 w-4" />
                Replicas: {status.warm_pool_replicas_ready}/{status.warm_pool_replicas_desired}
              </span>
            )}
            {status.queue_depth > 0 && (
              <span className="flex items-center gap-1">
                <ChartBarIcon className="h-4 w-4" />
                Queue: {status.queue_depth}
              </span>
            )}
            {status.active_burst_jobs > 0 && (
              <span className="flex items-center gap-1">
                <BoltIcon className="h-4 w-4" />
                Burst Jobs: {status.active_burst_jobs}
              </span>
            )}
          </div>
        </div>
        {!status.can_switch_mode && (
          <div className="flex items-center gap-2 text-warning-600 dark:text-warning-400 text-sm">
            <ClockIcon className="h-4 w-4" />
            Cooldown: {Math.ceil(status.cooldown_remaining_seconds / 60)}m
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Advanced Settings Panel Component
 */
function AdvancedSettingsPanel({ settings, onUpdate, isLoading }) {
  const [localSettings, setLocalSettings] = useState(settings);
  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    setLocalSettings(settings);
    setHasChanges(false);
  }, [settings]);

  const handleChange = (field, value) => {
    setLocalSettings(prev => ({ ...prev, [field]: value }));
    setHasChanges(true);
  };

  const handleSave = () => {
    onUpdate(localSettings);
    setHasChanges(false);
  };

  return (
    <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)]">
      <div className="p-6 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center gap-3">
          <Cog6ToothIcon className="h-5 w-5 text-aura-600 dark:text-aura-400" />
          <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
            Advanced Settings
          </h3>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* Warm Pool Settings */}
        <div>
          <h4 className="font-medium text-surface-900 dark:text-surface-100 mb-4">Warm Pool Configuration</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                Warm Pool Replicas
              </label>
              <input
                type="number"
                min={1}
                max={10}
                value={localSettings.warm_pool_replicas || 1}
                onChange={(e) => handleChange('warm_pool_replicas', parseInt(e.target.value))}
                disabled={isLoading}
                className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 disabled:opacity-50"
              />
              <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                Number of always-on orchestrator replicas (1-10)
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                Estimated Monthly Cost
              </label>
              <div className="px-3 py-2 border border-surface-200 dark:border-surface-700 rounded-lg bg-surface-50 dark:bg-surface-800">
                <span className="text-lg font-bold text-surface-900 dark:text-surface-100">
                  ${((localSettings.warm_pool_replicas || 1) * 28).toFixed(2)}
                </span>
                <span className="text-sm text-surface-500 dark:text-surface-400">/mo</span>
              </div>
            </div>
          </div>
        </div>

        {/* Hybrid Mode Settings */}
        <div>
          <h4 className="font-medium text-surface-900 dark:text-surface-100 mb-4">Hybrid Mode Configuration</h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                Queue Depth Threshold
              </label>
              <input
                type="number"
                min={1}
                max={100}
                value={localSettings.hybrid_threshold_queue_depth || 5}
                onChange={(e) => handleChange('hybrid_threshold_queue_depth', parseInt(e.target.value))}
                disabled={isLoading}
                className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 disabled:opacity-50"
              />
              <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                Trigger burst jobs when queue exceeds this depth
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                Scale-up Cooldown (s)
              </label>
              <input
                type="number"
                min={30}
                max={300}
                value={localSettings.hybrid_scale_up_cooldown_seconds || 60}
                onChange={(e) => handleChange('hybrid_scale_up_cooldown_seconds', parseInt(e.target.value))}
                disabled={isLoading}
                className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 disabled:opacity-50"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                Max Burst Jobs
              </label>
              <input
                type="number"
                min={1}
                max={50}
                value={localSettings.hybrid_max_burst_jobs || 10}
                onChange={(e) => handleChange('hybrid_max_burst_jobs', parseInt(e.target.value))}
                disabled={isLoading}
                className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 disabled:opacity-50"
              />
            </div>
          </div>
        </div>

        {/* Mode Change Cooldown */}
        <div>
          <h4 className="font-medium text-surface-900 dark:text-surface-100 mb-4">Mode Change Settings</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                Mode Change Cooldown (seconds)
              </label>
              <input
                type="number"
                min={60}
                max={3600}
                step={60}
                value={localSettings.mode_change_cooldown_seconds || 300}
                onChange={(e) => handleChange('mode_change_cooldown_seconds', parseInt(e.target.value))}
                disabled={isLoading}
                className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 disabled:opacity-50"
              />
              <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                Minimum time between mode changes to prevent thrashing
              </p>
            </div>
            {settings.last_mode_change_at && (
              <div>
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                  Last Mode Change
                </label>
                <div className="px-3 py-2 border border-surface-200 dark:border-surface-700 rounded-lg bg-surface-50 dark:bg-surface-800">
                  <p className="text-surface-900 dark:text-surface-100">
                    {new Date(settings.last_mode_change_at).toLocaleString()}
                  </p>
                  {settings.last_mode_change_by && (
                    <p className="text-xs text-surface-500 dark:text-surface-400">
                      by {settings.last_mode_change_by}
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {hasChanges && (
        <div className="p-4 border-t border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50 flex justify-end gap-3">
          <button
            onClick={() => {
              setLocalSettings(settings);
              setHasChanges(false);
            }}
            disabled={isLoading}
            className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={isLoading}
            className="px-4 py-2 text-sm font-medium bg-aura-600 text-white rounded-lg hover:bg-aura-700 disabled:opacity-50 transition-colors"
          >
            {isLoading ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      )}
    </div>
  );
}

/**
 * Main Orchestrator Mode Tab Component
 */
export default function OrchestratorModeTab({ onSuccess, onError }) {
  const [settings, setSettings] = useState(DEFAULT_ORCHESTRATOR_SETTINGS);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [switching, setSwitching] = useState(false);
  const [saving, setSaving] = useState(false);

  // Load data on mount only
  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [settingsData, statusData] = await Promise.all([
        getOrchestratorSettings(),
        getModeStatus(),
      ]);
      setSettings(settingsData);
      setStatus(statusData);
    } catch (err) {
      onError?.(`Failed to load orchestrator settings: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleModeSwitch = async (targetMode) => {
    if (!status?.can_switch_mode) {
      onError?.(`Mode change on cooldown. ${Math.ceil(status.cooldown_remaining_seconds / 60)} minutes remaining.`);
      return;
    }

    setSwitching(true);
    try {
      const result = await switchDeploymentMode(targetMode);
      setSettings(result);
      setStatus(prev => ({
        ...prev,
        current_mode: targetMode,
        can_switch_mode: false,
        cooldown_remaining_seconds: settings.mode_change_cooldown_seconds,
      }));
      onSuccess?.(`Switched to ${DEPLOYMENT_MODE_CONFIG[targetMode]?.label || targetMode} mode`);
    } catch (err) {
      onError?.(`Failed to switch mode: ${err.message}`);
    } finally {
      setSwitching(false);
    }
  };

  const handleSettingsUpdate = async (updates) => {
    setSaving(true);
    try {
      const result = await updateOrchestratorSettings(updates);
      setSettings(result);
      onSuccess?.('Orchestrator settings updated');
    } catch (err) {
      onError?.(`Failed to update settings: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <ArrowPathIcon className="h-8 w-8 text-aura-500 animate-spin" />
        <span className="ml-3 text-surface-600 dark:text-surface-400">
          Loading orchestrator settings...
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Introduction */}
      <div className="flex items-start gap-3 p-4 bg-aura-50 dark:bg-aura-900/20 border border-aura-200 dark:border-aura-800 rounded-lg">
        <InformationCircleIcon className="h-5 w-5 text-aura-600 dark:text-aura-400 flex-shrink-0 mt-0.5" />
        <div>
          <h4 className="font-medium text-aura-800 dark:text-aura-200">Orchestrator Deployment Modes</h4>
          <p className="text-sm text-aura-700 dark:text-aura-300 mt-1">
            Choose how the Agent Orchestrator is deployed. On-Demand is cost-effective for low volumes,
            Warm Pool provides instant response, and Hybrid balances both for variable workloads.
          </p>
        </div>
      </div>

      {/* Current Status */}
      <ModeStatusDisplay status={status} settings={settings} />

      {/* Deployment Mode Selection */}
      <div>
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4">
          Select Deployment Mode
        </h3>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {Object.entries(DEPLOYMENT_MODE_CONFIG).map(([mode, config]) => (
            <DeploymentModeCard
              key={mode}
              mode={mode}
              config={config}
              isActive={settings.effective_mode === mode}
              onSelect={handleModeSwitch}
              isLoading={switching}
              disabled={!status?.can_switch_mode}
            />
          ))}
        </div>
      </div>

      {/* Cost Warning for Warm Pool */}
      {(settings.effective_mode === 'warm_pool' || settings.effective_mode === 'hybrid') && (
        <div className="flex items-start gap-3 p-4 bg-warning-50 dark:bg-warning-900/20 border border-warning-200 dark:border-warning-800 rounded-lg">
          <CurrencyDollarIcon className="h-5 w-5 text-warning-600 dark:text-warning-400 flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="font-medium text-warning-800 dark:text-warning-200">Active Cost Warning</h4>
            <p className="text-sm text-warning-700 dark:text-warning-300 mt-1">
              Warm Pool mode incurs a base cost of ${(settings.warm_pool_replicas || 1) * 28}/month
              for always-on compute. Consider On-Demand mode for cost-sensitive environments.
            </p>
          </div>
        </div>
      )}

      {/* Advanced Settings */}
      <AdvancedSettingsPanel
        settings={settings}
        onUpdate={handleSettingsUpdate}
        isLoading={saving}
      />
    </div>
  );
}
