/**
 * Project Aura - Agent Deploy Modal Component
 *
 * Modal for deploying new agents to the platform.
 * Allows selection of agent type, configuration of capabilities, and resource limits.
 */

import { useState } from 'react';
import {
  XMarkIcon,
  CpuChipIcon,
  CommandLineIcon,
  EyeIcon,
  ShieldCheckIcon,
  MagnifyingGlassIcon,
  GlobeAltIcon,
  RocketLaunchIcon,
  CheckIcon,
} from '@heroicons/react/24/outline';

import { AGENT_TYPES, DEFAULT_AGENT_CONFIG, deployAgent } from '../../services/agentApi';

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
const COLOR_STYLES = {
  olive: {
    bg: 'bg-olive-100 dark:bg-olive-900/30',
    text: 'text-olive-600 dark:text-olive-400',
    border: 'border-olive-300 dark:border-olive-700',
    selected: 'ring-2 ring-aura-500 border-aura-500',
  },
  aura: {
    bg: 'bg-aura-100 dark:bg-aura-900/30',
    text: 'text-aura-600 dark:text-aura-400',
    border: 'border-aura-300 dark:border-aura-700',
    selected: 'ring-2 ring-aura-500 border-aura-500',
  },
  warning: {
    bg: 'bg-warning-100 dark:bg-warning-900/30',
    text: 'text-warning-600 dark:text-warning-400',
    border: 'border-warning-300 dark:border-warning-700',
    selected: 'ring-2 ring-aura-500 border-aura-500',
  },
};

/**
 * Agent Deploy Modal
 */
export default function AgentDeployModal({ isOpen, onClose, onDeploy }) {
  const [step, setStep] = useState(1);
  const [selectedType, setSelectedType] = useState(null);
  const [agentName, setAgentName] = useState('');
  const [description, setDescription] = useState('');
  const [selectedCapabilities, setSelectedCapabilities] = useState([]);
  const [deploying, setDeploying] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const agentTypes = Object.entries(AGENT_TYPES).map(([key, value]) => ({
    id: key,
    ...value,
  }));

  const handleTypeSelect = (typeId) => {
    setSelectedType(typeId);
    const typeConfig = AGENT_TYPES[typeId];
    setSelectedCapabilities(typeConfig.capabilities || []);
    setDescription(typeConfig.description);
  };

  const handleCapabilityToggle = (capability) => {
    setSelectedCapabilities((prev) =>
      prev.includes(capability)
        ? prev.filter((c) => c !== capability)
        : [...prev, capability]
    );
  };

  const handleDeploy = async () => {
    if (!selectedType || !agentName.trim()) return;

    setDeploying(true);
    setError(null);

    try {
      const result = await deployAgent({
        name: agentName.trim(),
        type: selectedType,
        description: description.trim(),
        capabilities: selectedCapabilities,
      });
      onDeploy?.(result);
      handleClose();
    } catch (err) {
      setError(err.message || 'Failed to deploy agent');
    } finally {
      setDeploying(false);
    }
  };

  const handleClose = () => {
    setStep(1);
    setSelectedType(null);
    setAgentName('');
    setDescription('');
    setSelectedCapabilities([]);
    setError(null);
    onClose();
  };

  const canProceedStep1 = selectedType !== null;
  const canProceedStep2 = agentName.trim().length > 0;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-md transition-opacity duration-[var(--duration-overlay)] ease-[var(--ease-tahoe)]"
        onClick={handleClose}
      />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative bg-white/95 dark:bg-surface-800/95 backdrop-blur-xl backdrop-saturate-150 rounded-2xl shadow-[var(--shadow-glass-hover)] w-full max-w-2xl max-h-[90vh] overflow-hidden animate-in fade-in zoom-in-95 duration-[var(--duration-overlay)] ease-[var(--ease-tahoe)]">
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b border-surface-100/50 dark:border-surface-700/30">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-olive-100 dark:bg-olive-900/30 rounded-lg">
                <RocketLaunchIcon className="w-6 h-6 text-olive-600 dark:text-olive-400" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-surface-900 dark:text-surface-100">
                  Deploy New Agent
                </h2>
                <p className="text-sm text-surface-500 dark:text-surface-400">
                  Step {step} of 3
                </p>
              </div>
            </div>
            <button
              onClick={handleClose}
              className="p-2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 rounded-xl hover:bg-surface-50 dark:hover:bg-surface-700 transition-all duration-200 ease-[var(--ease-tahoe)]"
            >
              <XMarkIcon className="w-5 h-5" />
            </button>
          </div>

          {/* Content */}
          <div className="p-6 overflow-y-auto max-h-[60vh]">
            {/* Step 1: Select Agent Type */}
            {step === 1 && (
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
                  Select Agent Type
                </h3>
                <p className="text-sm text-surface-500 dark:text-surface-400">
                  Choose the type of agent you want to deploy based on its primary function.
                </p>
                <div className="grid grid-cols-2 gap-4 mt-4">
                  {agentTypes.map((type) => {
                    const Icon = AGENT_ICONS[type.id];
                    const colors = COLOR_STYLES[type.color];
                    const isSelected = selectedType === type.id;

                    return (
                      <button
                        key={type.id}
                        onClick={() => handleTypeSelect(type.id)}
                        className={`
                          p-4 rounded-xl border-2 text-left transition-all duration-200 ease-[var(--ease-tahoe)]
                          ${isSelected
                            ? `${colors.selected} bg-white dark:bg-surface-700 shadow-[var(--shadow-glass)]`
                            : 'border-surface-200/50 dark:border-surface-700/30 bg-surface-50 dark:bg-surface-800 hover:bg-white dark:hover:bg-surface-700'}
                          hover:shadow-[var(--shadow-glass)]
                        `}
                      >
                        <div className="flex items-start gap-3">
                          <div className={`p-2 rounded-lg ${colors.bg}`}>
                            <Icon className={`w-5 h-5 ${colors.text}`} />
                          </div>
                          <div className="flex-1">
                            <div className="flex items-center justify-between">
                              <span className="font-medium text-surface-900 dark:text-surface-100">
                                {type.label}
                              </span>
                              {isSelected && (
                                <CheckIcon className="w-5 h-5 text-olive-500" />
                              )}
                            </div>
                            <p className="text-sm text-surface-500 dark:text-surface-400 mt-1">
                              {type.description}
                            </p>
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Step 2: Configure Agent */}
            {step === 2 && (
              <div className="space-y-6">
                <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
                  Configure Agent
                </h3>

                {/* Agent Name */}
                <div>
                  <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                    Agent Name *
                  </label>
                  <input
                    type="text"
                    value={agentName}
                    onChange={(e) => setAgentName(e.target.value)}
                    placeholder="e.g., Security Scanner Alpha"
                    className="w-full px-4 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
                  />
                </div>

                {/* Description */}
                <div>
                  <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                    Description
                  </label>
                  <textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    rows={3}
                    placeholder="Describe the agent's purpose..."
                    className="w-full px-4 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent resize-none"
                  />
                </div>

                {/* Capabilities */}
                <div>
                  <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                    Capabilities
                  </label>
                  <div className="space-y-2">
                    {AGENT_TYPES[selectedType]?.capabilities.map((capability) => (
                      <label
                        key={capability}
                        className="flex items-center gap-3 p-3 rounded-xl border border-surface-200/50 dark:border-surface-700/30 bg-surface-50 dark:bg-surface-800 hover:bg-white dark:hover:bg-surface-700 cursor-pointer transition-all duration-200 ease-[var(--ease-tahoe)]"
                      >
                        <input
                          type="checkbox"
                          checked={selectedCapabilities.includes(capability)}
                          onChange={() => handleCapabilityToggle(capability)}
                          className="w-4 h-4 rounded border-surface-300 text-aura-600 focus:ring-aura-500"
                        />
                        <span className="text-sm text-surface-700 dark:text-surface-300 capitalize">
                          {capability.replace(/_/g, ' ')}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Step 3: Review & Deploy */}
            {step === 3 && (
              <div className="space-y-6">
                <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
                  Review & Deploy
                </h3>

                {error && (
                  <div className="p-4 bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800 rounded-lg text-critical-700 dark:text-critical-400 text-sm">
                    {error}
                  </div>
                )}

                <div className="bg-white dark:bg-surface-800 backdrop-blur-sm rounded-xl p-6 space-y-4 border border-surface-100/50 dark:border-surface-700/30">
                  {/* Agent Type */}
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-surface-500 dark:text-surface-400">Type</span>
                    <span className="font-medium text-surface-900 dark:text-surface-100">
                      {AGENT_TYPES[selectedType]?.label}
                    </span>
                  </div>

                  {/* Agent Name */}
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-surface-500 dark:text-surface-400">Name</span>
                    <span className="font-medium text-surface-900 dark:text-surface-100">
                      {agentName}
                    </span>
                  </div>

                  {/* Description */}
                  <div className="flex items-start justify-between">
                    <span className="text-sm text-surface-500 dark:text-surface-400">Description</span>
                    <span className="font-medium text-surface-900 dark:text-surface-100 text-right max-w-xs">
                      {description || 'No description'}
                    </span>
                  </div>

                  {/* Capabilities */}
                  <div>
                    <span className="text-sm text-surface-500 dark:text-surface-400 block mb-2">
                      Enabled Capabilities
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {selectedCapabilities.map((cap) => (
                        <span
                          key={cap}
                          className="px-2 py-1 text-xs font-medium bg-aura-100 dark:bg-aura-900/30 text-aura-700 dark:text-aura-400 rounded-full capitalize"
                        >
                          {cap.replace(/_/g, ' ')}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Resource Defaults */}
                  <div className="pt-4 border-t border-surface-100/50 dark:border-surface-700/30">
                    <span className="text-sm text-surface-500 dark:text-surface-400 block mb-2">
                      Default Resource Limits
                    </span>
                    <div className="grid grid-cols-3 gap-4 text-sm">
                      <div>
                        <span className="text-surface-500 dark:text-surface-400">CPU</span>
                        <p className="font-medium text-surface-900 dark:text-surface-100">
                          {DEFAULT_AGENT_CONFIG.resource_limits.cpu_millicores}m
                        </p>
                      </div>
                      <div>
                        <span className="text-surface-500 dark:text-surface-400">Memory</span>
                        <p className="font-medium text-surface-900 dark:text-surface-100">
                          {DEFAULT_AGENT_CONFIG.resource_limits.memory_mb} MB
                        </p>
                      </div>
                      <div>
                        <span className="text-surface-500 dark:text-surface-400">Max Tokens</span>
                        <p className="font-medium text-surface-900 dark:text-surface-100">
                          {DEFAULT_AGENT_CONFIG.resource_limits.max_tokens_per_request.toLocaleString()}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between p-6 border-t border-surface-100/50 dark:border-surface-700/30 bg-white/60 dark:bg-surface-800/50 backdrop-blur-sm">
            <button
              onClick={step === 1 ? handleClose : () => setStep(step - 1)}
              className="px-4 py-2 text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-100 hover:bg-surface-50 dark:hover:bg-surface-700 rounded-xl font-medium transition-all duration-200 ease-[var(--ease-tahoe)]"
            >
              {step === 1 ? 'Cancel' : 'Back'}
            </button>

            <div className="flex items-center gap-2">
              {/* Step Indicators */}
              <div className="flex items-center gap-1 mr-4">
                {[1, 2, 3].map((s) => (
                  <div
                    key={s}
                    className={`w-2 h-2 rounded-full transition-colors ${
                      s === step
                        ? 'bg-aura-500'
                        : s < step
                        ? 'bg-olive-500'
                        : 'bg-surface-300 dark:bg-surface-600'
                    }`}
                  />
                ))}
              </div>

              {step < 3 ? (
                <button
                  onClick={() => setStep(step + 1)}
                  disabled={step === 1 ? !canProceedStep1 : !canProceedStep2}
                  className="flex items-center gap-2 px-6 py-2 bg-aura-500 hover:bg-aura-600 disabled:bg-surface-300 disabled:cursor-not-allowed text-white rounded-xl font-medium shadow-[var(--shadow-glass)] hover:shadow-[var(--shadow-glass-hover)] transition-all duration-200 ease-[var(--ease-tahoe)]"
                >
                  Continue
                </button>
              ) : (
                <button
                  onClick={handleDeploy}
                  disabled={deploying}
                  className="flex items-center gap-2 px-6 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-surface-300 disabled:cursor-not-allowed text-white rounded-xl font-medium shadow-[var(--shadow-glass)] hover:shadow-[var(--shadow-glass-hover)] transition-all duration-200 ease-[var(--ease-tahoe)]"
                >
                  {deploying ? (
                    <>
                      <svg className="animate-spin h-4 w-4\" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Deploying...
                    </>
                  ) : (
                    <>
                      <RocketLaunchIcon className="w-4 h-4" />
                      Deploy Agent
                    </>
                  )}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
