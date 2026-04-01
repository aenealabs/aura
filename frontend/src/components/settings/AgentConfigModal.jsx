/**
 * Project Aura - Agent Configuration Modal Component
 *
 * Modal for configuring individual agent parameters.
 * Shows agent capabilities, resource limits, and enabled/disabled state.
 */

import { useState, useEffect } from 'react';
import {
  XMarkIcon,
  CpuChipIcon,
  CommandLineIcon,
  EyeIcon,
  ShieldCheckIcon,
  MagnifyingGlassIcon,
  GlobeAltIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ArrowPathIcon,
  Cog6ToothIcon,
  BoltIcon,
  ChartBarIcon,
} from '@heroicons/react/24/outline';

import {
  getAgentConfig,
  updateAgentConfig,
  enableAgent,
  disableAgent,
  restartAgent,
  AGENT_TYPES,
  DEFAULT_AGENT_CONFIG,
} from '../../services/agentApi';

// Icon mapping for agent types
const AGENT_ICONS = {
  orchestrator: CpuChipIcon,
  coder: CommandLineIcon,
  reviewer: EyeIcon,
  validator: ShieldCheckIcon,
  scanner: MagnifyingGlassIcon,
  external: GlobeAltIcon,
};

// Color styles for agent types
const TYPE_COLORS = {
  orchestrator: 'olive',
  coder: 'aura',
  reviewer: 'warning',
  validator: 'olive',
  scanner: 'aura',
  external: 'warning',
};

const COLOR_STYLES = {
  olive: {
    bg: 'bg-olive-100 dark:bg-olive-900/30',
    text: 'text-olive-600 dark:text-olive-400',
    border: 'border-olive-200 dark:border-olive-800',
  },
  aura: {
    bg: 'bg-aura-100 dark:bg-aura-900/30',
    text: 'text-aura-600 dark:text-aura-400',
    border: 'border-aura-200 dark:border-aura-800',
  },
  warning: {
    bg: 'bg-warning-100 dark:bg-warning-900/30',
    text: 'text-warning-600 dark:text-warning-400',
    border: 'border-warning-200 dark:border-warning-800',
  },
};

/**
 * Capability Toggle Component
 */
function CapabilityToggle({ capability, enabled, onChange, disabled }) {
  return (
    <div className="flex items-center justify-between py-2">
      <span className="text-sm text-surface-700 dark:text-surface-300 capitalize">
        {capability.replace(/_/g, ' ')}
      </span>
      <button
        type="button"
        onClick={() => onChange(!enabled)}
        disabled={disabled}
        className={`
          relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent
          transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2 dark:focus:ring-offset-surface-800
          ${enabled ? 'bg-olive-600' : 'bg-surface-200 dark:bg-surface-600'}
          ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
        `}
      >
        <span
          className={`
            pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0
            transition duration-200 ease-in-out
            ${enabled ? 'translate-x-4' : 'translate-x-0'}
          `}
        />
      </button>
    </div>
  );
}

/**
 * Resource Limit Input Component
 */
function ResourceInput({ label, description, value, onChange, min, max, step = 1, unit, disabled }) {
  return (
    <div>
      <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
        {label}
      </label>
      <div className="flex items-center gap-2">
        <input
          type="number"
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          min={min}
          max={max}
          step={step}
          disabled={disabled}
          className="flex-1 px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 disabled:opacity-50"
        />
        {unit && (
          <span className="text-sm text-surface-500 dark:text-surface-400 w-16">{unit}</span>
        )}
      </div>
      {description && (
        <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">{description}</p>
      )}
    </div>
  );
}

/**
 * Main Agent Configuration Modal Component
 */
export default function AgentConfigModal({ agent, isOpen, onClose, onSave }) {
  const [config, setConfig] = useState(DEFAULT_AGENT_CONFIG);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('general');
  const [hasChanges, setHasChanges] = useState(false);

  // Load agent config when modal opens (loadConfig defined below)
  useEffect(() => {
    if (isOpen && agent) {
      loadConfig();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, agent]);

  const loadConfig = async () => {
    setLoading(true);
    try {
      const data = await getAgentConfig(agent.id);
      setConfig(data);
    } catch (err) {
      console.error('Failed to load agent config:', err);
      setConfig({ ...DEFAULT_AGENT_CONFIG, agent_id: agent.id });
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (field, value) => {
    setConfig(prev => ({
      ...prev,
      [field]: value,
    }));
    setHasChanges(true);
  };

  const handleResourceChange = (field, value) => {
    setConfig(prev => ({
      ...prev,
      resource_limits: {
        ...prev.resource_limits,
        [field]: value,
      },
    }));
    setHasChanges(true);
  };

  const handleRateLimitChange = (field, value) => {
    setConfig(prev => ({
      ...prev,
      rate_limits: {
        ...prev.rate_limits,
        [field]: value,
      },
    }));
    setHasChanges(true);
  };

  const handleCapabilityToggle = (capability, enabled) => {
    const capabilities = enabled
      ? [...(config.capabilities_enabled || []), capability]
      : (config.capabilities_enabled || []).filter(c => c !== capability);
    handleChange('capabilities_enabled', capabilities);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateAgentConfig(agent.id, config);
      onSave?.(config);
      setHasChanges(false);
      onClose();
    } catch (err) {
      console.error('Failed to save agent config:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleToggleEnabled = async () => {
    setSaving(true);
    try {
      if (config.enabled) {
        await disableAgent(agent.id);
      } else {
        await enableAgent(agent.id);
      }
      setConfig(prev => ({ ...prev, enabled: !prev.enabled }));
    } catch (err) {
      console.error('Failed to toggle agent:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleRestart = async () => {
    setSaving(true);
    try {
      await restartAgent(agent.id);
    } catch (err) {
      console.error('Failed to restart agent:', err);
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  const agentType = agent?.type || 'orchestrator';
  const typeConfig = AGENT_TYPES[agentType] || AGENT_TYPES.orchestrator;
  const colorConfig = COLOR_STYLES[TYPE_COLORS[agentType]] || COLOR_STYLES.olive;
  const AgentIcon = AGENT_ICONS[agentType] || CpuChipIcon;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-screen items-center justify-center p-4">
        <div className="fixed inset-0 bg-black/40 backdrop-blur-md transition-opacity duration-[var(--duration-overlay)] ease-[var(--ease-tahoe)]" onClick={onClose} />

        <div className="relative bg-white/95 dark:bg-surface-800/95 backdrop-blur-xl backdrop-saturate-150 rounded-2xl shadow-[var(--shadow-glass-hover)] max-w-2xl w-full max-h-[90vh] overflow-hidden animate-in fade-in zoom-in-95 duration-[var(--duration-overlay)] ease-[var(--ease-tahoe)]">
          {/* Header */}
          <div className="px-6 py-4 border-b border-surface-100/50 dark:border-surface-700/30">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg ${colorConfig.bg}`}>
                  <AgentIcon className={`h-5 w-5 ${colorConfig.text}`} />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
                    Configure {agent?.name || 'Agent'}
                  </h2>
                  <p className="text-sm text-surface-500 dark:text-surface-400">
                    {typeConfig.label} - {typeConfig.description}
                  </p>
                </div>
              </div>
              <button
                onClick={onClose}
                className="p-2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-200 hover:bg-surface-50 dark:hover:bg-surface-700 rounded-xl transition-all duration-200 ease-[var(--ease-tahoe)]"
              >
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <ArrowPathIcon className="h-8 w-8 text-aura-500 animate-spin" />
              <span className="ml-3 text-surface-600 dark:text-surface-400">
                Loading configuration...
              </span>
            </div>
          ) : (
            <>
              {/* Status Banner */}
              <div className={`px-6 py-3 ${config.enabled ? 'bg-olive-50/80 dark:bg-olive-900/20' : 'bg-white/60 dark:bg-surface-700/50'} backdrop-blur-sm flex items-center justify-between`}>
                <div className="flex items-center gap-2">
                  {config.enabled ? (
                    <CheckCircleIcon className="h-5 w-5 text-olive-600 dark:text-olive-400" />
                  ) : (
                    <ExclamationTriangleIcon className="h-5 w-5 text-surface-400" />
                  )}
                  <span className={config.enabled ? 'text-olive-700 dark:text-olive-300 font-medium' : 'text-surface-600 dark:text-surface-400'}>
                    {config.enabled ? 'Agent Enabled' : 'Agent Disabled'}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleRestart}
                    disabled={saving || !config.enabled}
                    className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium bg-aura-500 hover:bg-aura-600 text-white rounded-xl transition-all duration-200 ease-[var(--ease-tahoe)] disabled:opacity-50"
                  >
                    <ArrowPathIcon className="h-4 w-4" />
                    Restart
                  </button>
                  <button
                    onClick={handleToggleEnabled}
                    disabled={saving}
                    className={`
                      px-3 py-1.5 text-sm font-medium rounded-xl transition-all duration-200 ease-[var(--ease-tahoe)] disabled:opacity-50
                      ${config.enabled
                        ? 'text-critical-600 hover:bg-critical-50/80 dark:hover:bg-critical-900/30'
                        : 'text-olive-600 hover:bg-olive-50/80 dark:hover:bg-olive-900/30'
                      }
                    `}
                  >
                    {config.enabled ? 'Disable' : 'Enable'}
                  </button>
                </div>
              </div>

              {/* Tabs */}
              <div className="border-b border-surface-100/50 dark:border-surface-700/30">
                <nav className="flex gap-1 px-6">
                  {[
                    { id: 'general', label: 'General', icon: Cog6ToothIcon },
                    { id: 'resources', label: 'Resources', icon: CpuChipIcon },
                    { id: 'capabilities', label: 'Capabilities', icon: BoltIcon },
                    { id: 'rate_limits', label: 'Rate Limits', icon: ChartBarIcon },
                  ].map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={`
                        flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors
                        ${activeTab === tab.id
                          ? 'border-aura-500 text-aura-600 dark:text-aura-400'
                          : 'border-transparent text-surface-500 hover:text-surface-700 dark:hover:text-surface-300'
                        }
                      `}
                    >
                      <tab.icon className="h-4 w-4" />
                      {tab.label}
                    </button>
                  ))}
                </nav>
              </div>

              {/* Content */}
              <div className="p-6 overflow-y-auto max-h-[50vh]">
                {activeTab === 'general' && (
                  <div className="space-y-4">
                    <ResourceInput
                      label="Max Concurrent Tasks"
                      description="Maximum number of tasks this agent can process simultaneously"
                      value={config.max_concurrent_tasks}
                      onChange={(v) => handleChange('max_concurrent_tasks', v)}
                      min={1}
                      max={20}
                      disabled={saving}
                    />
                    <ResourceInput
                      label="Task Timeout"
                      description="Maximum time (in seconds) for a single task"
                      value={config.timeout_seconds}
                      onChange={(v) => handleChange('timeout_seconds', v)}
                      min={30}
                      max={3600}
                      unit="seconds"
                      disabled={saving}
                    />
                    <ResourceInput
                      label="Retry Attempts"
                      description="Number of retry attempts for failed tasks"
                      value={config.retry_attempts}
                      onChange={(v) => handleChange('retry_attempts', v)}
                      min={0}
                      max={10}
                      disabled={saving}
                    />
                    <ResourceInput
                      label="Retry Delay"
                      description="Delay between retry attempts"
                      value={config.retry_delay_seconds}
                      onChange={(v) => handleChange('retry_delay_seconds', v)}
                      min={1}
                      max={300}
                      unit="seconds"
                      disabled={saving}
                    />
                  </div>
                )}

                {activeTab === 'resources' && (
                  <div className="space-y-4">
                    <ResourceInput
                      label="CPU Limit"
                      description="Maximum CPU allocation (millicores)"
                      value={config.resource_limits?.cpu_millicores || 1000}
                      onChange={(v) => handleResourceChange('cpu_millicores', v)}
                      min={100}
                      max={4000}
                      step={100}
                      unit="mCPU"
                      disabled={saving}
                    />
                    <ResourceInput
                      label="Memory Limit"
                      description="Maximum memory allocation"
                      value={config.resource_limits?.memory_mb || 2048}
                      onChange={(v) => handleResourceChange('memory_mb', v)}
                      min={512}
                      max={8192}
                      step={256}
                      unit="MB"
                      disabled={saving}
                    />
                    <ResourceInput
                      label="Max Tokens per Request"
                      description="Maximum tokens for LLM requests"
                      value={config.resource_limits?.max_tokens_per_request || 16000}
                      onChange={(v) => handleResourceChange('max_tokens_per_request', v)}
                      min={1000}
                      max={128000}
                      step={1000}
                      unit="tokens"
                      disabled={saving}
                    />
                  </div>
                )}

                {activeTab === 'capabilities' && (
                  <div className="space-y-2">
                    <p className="text-sm text-surface-600 dark:text-surface-400 mb-4">
                      Enable or disable specific capabilities for this agent.
                    </p>
                    {(typeConfig.capabilities || []).map((capability) => (
                      <CapabilityToggle
                        key={capability}
                        capability={capability}
                        enabled={(config.capabilities_enabled || []).includes(capability)}
                        onChange={(enabled) => handleCapabilityToggle(capability, enabled)}
                        disabled={saving}
                      />
                    ))}
                    {(!typeConfig.capabilities || typeConfig.capabilities.length === 0) && (
                      <p className="text-sm text-surface-500 dark:text-surface-400 text-center py-4">
                        No configurable capabilities for this agent type.
                      </p>
                    )}
                  </div>
                )}

                {activeTab === 'rate_limits' && (
                  <div className="space-y-4">
                    <ResourceInput
                      label="Requests per Minute"
                      description="Maximum LLM requests per minute"
                      value={config.rate_limits?.requests_per_minute || 30}
                      onChange={(v) => handleRateLimitChange('requests_per_minute', v)}
                      min={1}
                      max={120}
                      disabled={saving}
                    />
                    <ResourceInput
                      label="Requests per Hour"
                      description="Maximum LLM requests per hour"
                      value={config.rate_limits?.requests_per_hour || 500}
                      onChange={(v) => handleRateLimitChange('requests_per_hour', v)}
                      min={10}
                      max={5000}
                      disabled={saving}
                    />
                  </div>
                )}
              </div>

              {/* Footer */}
              <div className="px-6 py-4 border-t border-surface-100/50 dark:border-surface-700/30 bg-white/60 dark:bg-surface-800/50 backdrop-blur-sm flex justify-end gap-3">
                <button
                  onClick={onClose}
                  className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-surface-50 dark:hover:bg-surface-700 rounded-xl transition-all duration-200 ease-[var(--ease-tahoe)]"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={!hasChanges || saving}
                  className="px-4 py-2 text-sm font-medium bg-aura-600 text-white rounded-xl hover:bg-aura-700 shadow-[var(--shadow-glass)] hover:shadow-[var(--shadow-glass-hover)] disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 ease-[var(--ease-tahoe)] flex items-center gap-2"
                >
                  {saving ? (
                    <>
                      <ArrowPathIcon className="h-4 w-4 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    'Save Changes'
                  )}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
