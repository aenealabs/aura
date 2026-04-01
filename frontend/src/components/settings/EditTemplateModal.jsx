/**
 * Project Aura - Edit Template Modal Component
 *
 * Modal for editing environment templates with comprehensive configuration options.
 * Features:
 * - Pre-populated fields from existing template
 * - Resource limits with min/max validation
 * - Network policy selection
 * - Advanced configuration (environment variables, init scripts)
 * - Test Configuration button
 * - Apple-inspired design with clean transitions
 */

import { useState, useEffect, useCallback } from 'react';
import {
  XMarkIcon,
  ServerStackIcon,
  CpuChipIcon,
  CircleStackIcon,
  GlobeAltIcon,
  ClockIcon,
  CodeBracketIcon,
  VariableIcon,
  ShieldCheckIcon,
  CheckCircleIcon,
  XCircleIcon,
  ArrowPathIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  PlusIcon,
  TrashIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  BeakerIcon,
  CurrencyDollarIcon,
} from '@heroicons/react/24/outline';

import {
  BASE_IMAGES,
  NETWORK_POLICIES,
  RESOURCE_LIMITS,
  TIMEOUT_LIMITS,
  DEFAULT_TEMPLATE_CONFIG,
  validateTemplateConfig,
  estimateCost,
  testConfiguration,
} from '../../services/templateApi';

import { ENVIRONMENT_TYPE_CONFIG } from '../../services/environmentsApi';

/**
 * Resource Slider Component
 */
function ResourceSlider({
  label,
  description,
  value,
  onChange,
  min,
  max,
  step,
  unit,
  disabled,
  icon: Icon,
}) {
  const percentage = ((value - min) / (max - min)) * 100;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {Icon && <Icon className="h-4 w-4 text-surface-500 dark:text-surface-400" />}
          <label className="text-sm font-medium text-surface-700 dark:text-surface-300">
            {label}
          </label>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="number"
            value={value}
            onChange={(e) => onChange(Number(e.target.value))}
            min={min}
            max={max}
            step={step}
            disabled={disabled}
            className="w-20 px-2 py-1 text-right text-sm border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 disabled:opacity-50"
          />
          <span className="text-sm text-surface-500 dark:text-surface-400 w-12">
            {unit}
          </span>
        </div>
      </div>
      <div className="relative">
        <div className="h-2 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-aura-500 rounded-full transition-all duration-150"
            style={{ width: `${percentage}%` }}
          />
        </div>
        <input
          type="range"
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          min={min}
          max={max}
          step={step}
          disabled={disabled}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
        />
      </div>
      <div className="flex justify-between text-xs text-surface-400">
        <span>
          {min} {unit}
        </span>
        <span>
          {max} {unit}
        </span>
      </div>
      {description && (
        <p className="text-xs text-surface-500 dark:text-surface-400">
          {description}
        </p>
      )}
    </div>
  );
}

/**
 * Environment Variables Editor Component
 */
function EnvVarsEditor({ variables = {}, onChange, disabled }) {
  const entries = Object.entries(variables);

  const addVariable = () => {
    const newKey = `VAR_${entries.length + 1}`;
    onChange({ ...variables, [newKey]: '' });
  };

  const updateVariable = (oldKey, newKey, newValue) => {
    const updated = { ...variables };
    if (oldKey !== newKey) {
      delete updated[oldKey];
    }
    updated[newKey] = newValue;
    onChange(updated);
  };

  const removeVariable = (key) => {
    const updated = { ...variables };
    delete updated[key];
    onChange(updated);
  };

  return (
    <div className="space-y-3">
      {entries.length === 0 ? (
        <p className="text-sm text-surface-500 dark:text-surface-400 text-center py-4">
          No environment variables configured
        </p>
      ) : (
        entries.map(([key, value], index) => (
          <div key={index} className="flex items-center gap-2">
            <input
              type="text"
              value={key}
              onChange={(e) => updateVariable(key, e.target.value.toUpperCase(), value)}
              placeholder="VARIABLE_NAME"
              disabled={disabled}
              className="flex-1 px-3 py-2 text-sm font-mono border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 disabled:opacity-50"
            />
            <span className="text-surface-400">=</span>
            <input
              type="text"
              value={value}
              onChange={(e) => updateVariable(key, key, e.target.value)}
              placeholder="value"
              disabled={disabled}
              className="flex-1 px-3 py-2 text-sm font-mono border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 disabled:opacity-50"
            />
            <button
              type="button"
              onClick={() => removeVariable(key)}
              disabled={disabled}
              className="p-2 text-surface-400 hover:text-critical-600 dark:hover:text-critical-400 transition-colors"
            >
              <TrashIcon className="h-4 w-4" />
            </button>
          </div>
        ))
      )}
      <button
        type="button"
        onClick={addVariable}
        disabled={disabled}
        className="flex items-center gap-2 text-sm text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300 transition-colors"
      >
        <PlusIcon className="h-4 w-4" />
        Add Variable
      </button>
    </div>
  );
}

/**
 * Collapsible Section Component
 */
function CollapsibleSection({ title, icon: Icon, children, defaultOpen = false }) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border border-surface-200 dark:border-surface-700 rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-3 flex items-center justify-between bg-surface-50 dark:bg-surface-800/50 hover:bg-surface-100 dark:hover:bg-surface-700/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          {Icon && <Icon className="h-5 w-5 text-aura-600 dark:text-aura-400" />}
          <span className="font-medium text-surface-900 dark:text-surface-100">
            {title}
          </span>
        </div>
        {isOpen ? (
          <ChevronUpIcon className="h-5 w-5 text-surface-400" />
        ) : (
          <ChevronDownIcon className="h-5 w-5 text-surface-400" />
        )}
      </button>
      {isOpen && (
        <div className="p-4 border-t border-surface-200 dark:border-surface-700">
          {children}
        </div>
      )}
    </div>
  );
}

/**
 * Test Results Display Component
 */
function TestResults({ results, onDismiss }) {
  if (!results) return null;

  return (
    <div
      className={`
        flex items-start gap-3 p-4 rounded-lg border
        ${results.success
          ? 'bg-olive-50 dark:bg-olive-900/20 border-olive-200 dark:border-olive-800'
          : 'bg-critical-50 dark:bg-critical-900/20 border-critical-200 dark:border-critical-800'
        }
      `}
    >
      {results.success ? (
        <CheckCircleIcon className="h-5 w-5 text-olive-600 dark:text-olive-400 flex-shrink-0 mt-0.5" />
      ) : (
        <XCircleIcon className="h-5 w-5 text-critical-600 dark:text-critical-400 flex-shrink-0 mt-0.5" />
      )}
      <div className="flex-1">
        <p
          className={`font-medium ${
            results.success
              ? 'text-olive-700 dark:text-olive-300'
              : 'text-critical-700 dark:text-critical-300'
          }`}
        >
          {results.success ? 'Configuration Valid' : 'Configuration Invalid'}
        </p>
        {results.errors?.length > 0 && (
          <ul className="mt-2 space-y-1">
            {results.errors.map((error, idx) => (
              <li
                key={idx}
                className="text-sm text-critical-600 dark:text-critical-400"
              >
                {error}
              </li>
            ))}
          </ul>
        )}
        {results.warnings?.length > 0 && (
          <ul className="mt-2 space-y-1">
            {results.warnings.map((warning, idx) => (
              <li
                key={idx}
                className="text-sm text-warning-600 dark:text-warning-400 flex items-start gap-1"
              >
                <ExclamationTriangleIcon className="h-4 w-4 flex-shrink-0 mt-0.5" />
                {warning}
              </li>
            ))}
          </ul>
        )}
        {results.estimated_cost !== undefined && (
          <p className="mt-2 text-sm text-surface-600 dark:text-surface-400">
            Estimated cost: ${results.estimated_cost.toFixed(2)}/day
          </p>
        )}
      </div>
      <button
        onClick={onDismiss}
        className="p-1 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 transition-colors"
      >
        <XMarkIcon className="h-4 w-4" />
      </button>
    </div>
  );
}

/**
 * Main Edit Template Modal Component
 */
export default function EditTemplateModal({
  isOpen,
  template,
  onClose,
  onSave,
  isCreating = false,
}) {
  // Form state
  const [formData, setFormData] = useState(DEFAULT_TEMPLATE_CONFIG);
  const [errors, setErrors] = useState({});
  const [hasChanges, setHasChanges] = useState(false);

  // UI state
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResults, setTestResults] = useState(null);
  const [activeTab, setActiveTab] = useState('general');

  // Initialize form data when template changes
  useEffect(() => {
    if (isOpen) {
      if (template) {
        setFormData({
          ...DEFAULT_TEMPLATE_CONFIG,
          ...template,
          resource_limits: {
            ...DEFAULT_TEMPLATE_CONFIG.resource_limits,
            ...template.resource_limits,
          },
          timeout_settings: {
            ...DEFAULT_TEMPLATE_CONFIG.timeout_settings,
            ...template.timeout_settings,
          },
          environment_variables: template.environment_variables || {},
        });
      } else {
        setFormData(DEFAULT_TEMPLATE_CONFIG);
      }
      setErrors({});
      setHasChanges(false);
      setTestResults(null);
      setActiveTab('general');
    }
  }, [isOpen, template]);

  // Track changes
  useEffect(() => {
    if (!isOpen) return;

    if (isCreating) {
      // For new templates, any non-default value counts as a change
      const hasName = formData.name.trim().length > 0;
      setHasChanges(hasName);
    } else if (template) {
      // For editing, compare with original
      const changed =
        JSON.stringify(formData) !== JSON.stringify({ ...DEFAULT_TEMPLATE_CONFIG, ...template });
      setHasChanges(changed);
    }
  }, [formData, template, isCreating, isOpen]);

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Form handlers
  const handleChange = useCallback((field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: null }));
    setTestResults(null);
  }, []);

  const handleResourceChange = useCallback((field, value) => {
    setFormData((prev) => ({
      ...prev,
      resource_limits: {
        ...prev.resource_limits,
        [field]: value,
      },
    }));
    setTestResults(null);
  }, []);

  const handleTimeoutChange = useCallback((field, value) => {
    setFormData((prev) => ({
      ...prev,
      timeout_settings: {
        ...prev.timeout_settings,
        [field]: value,
      },
    }));
    setTestResults(null);
  }, []);

  // Validate form
  const validateForm = () => {
    const validationErrors = validateTemplateConfig(formData);
    const errorMap = {};

    validationErrors.forEach((error) => {
      if (error.includes('name')) errorMap.name = error;
      else if (error.includes('Description')) errorMap.description = error;
      else if (error.includes('CPU')) errorMap.cpu = error;
      else if (error.includes('Memory')) errorMap.memory = error;
      else if (error.includes('Storage')) errorMap.storage = error;
      else errorMap.general = error;
    });

    setErrors(errorMap);
    return validationErrors.length === 0;
  };

  // Test configuration
  const handleTest = async () => {
    setTesting(true);
    setTestResults(null);

    try {
      const results = await testConfiguration(formData);
      setTestResults(results);
    } catch (error) {
      setTestResults({
        success: false,
        errors: [error.message || 'Test failed'],
        warnings: [],
      });
    } finally {
      setTesting(false);
    }
  };

  // Save template
  const handleSave = async () => {
    if (!validateForm()) {
      return;
    }

    setSaving(true);

    try {
      // Calculate cost before saving
      const cost = estimateCost(formData);
      const templateData = {
        ...formData,
        cost_per_day: cost,
      };

      await onSave(templateData);
      onClose();
    } catch (error) {
      setErrors({ submit: error.message || 'Failed to save template' });
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  const estimatedCost = estimateCost(formData);

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-md transition-opacity duration-[var(--duration-overlay)] ease-[var(--ease-tahoe)]"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div
          className="relative w-full max-w-2xl bg-white/95 dark:bg-surface-800/95 backdrop-blur-xl backdrop-saturate-150 rounded-2xl shadow-[var(--shadow-glass-hover)] overflow-hidden animate-in fade-in zoom-in-95 duration-[var(--duration-overlay)] ease-[var(--ease-tahoe)]"
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-title"
        >
          {/* Header */}
          <div className="px-6 py-4 border-b border-surface-100/50 dark:border-surface-700/30">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-aura-100 dark:bg-aura-900/30">
                  <ServerStackIcon className="h-5 w-5 text-aura-600 dark:text-aura-400" />
                </div>
                <div>
                  <h2
                    id="modal-title"
                    className="text-lg font-semibold text-surface-900 dark:text-surface-100"
                  >
                    {isCreating ? 'Create Template' : 'Edit Template'}
                  </h2>
                  <p className="text-sm text-surface-500 dark:text-surface-400 mt-0.5">
                    Configure sandbox environment settings
                  </p>
                </div>
              </div>
              <button
                onClick={onClose}
                className="p-2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 hover:bg-white/60 dark:hover:bg-surface-700 rounded-xl transition-all duration-200 ease-[var(--ease-tahoe)]"
                aria-label="Close modal"
              >
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Tabs */}
          <div className="border-b border-surface-100/50 dark:border-surface-700/30">
            <nav className="flex gap-1 px-6">
              {[
                { id: 'general', label: 'General', icon: InformationCircleIcon },
                { id: 'resources', label: 'Resources', icon: CpuChipIcon },
                { id: 'advanced', label: 'Advanced', icon: CodeBracketIcon },
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

          {/* Body */}
          <div className="p-6 max-h-[60vh] overflow-y-auto">
            {/* General Tab */}
            {activeTab === 'general' && (
              <div className="space-y-6">
                {/* Template Name */}
                <div>
                  <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                    Template Name
                    <span className="text-critical-500 ml-1">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => handleChange('name', e.target.value)}
                    placeholder="e.g., Python Development Environment"
                    disabled={saving}
                    maxLength={64}
                    className={`
                      w-full px-3 py-2 border rounded-lg bg-white dark:bg-surface-700
                      text-surface-900 dark:text-surface-100
                      focus:ring-2 focus:ring-aura-500 focus:border-aura-500 disabled:opacity-50
                      ${errors.name ? 'border-critical-300 dark:border-critical-700' : 'border-surface-300 dark:border-surface-600'}
                    `}
                  />
                  {errors.name && (
                    <p className="text-xs text-critical-600 dark:text-critical-400 mt-1">
                      {errors.name}
                    </p>
                  )}
                  <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                    {formData.name.length}/64 characters
                  </p>
                </div>

                {/* Description */}
                <div>
                  <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                    Description
                  </label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => handleChange('description', e.target.value)}
                    placeholder="Describe the purpose of this template..."
                    disabled={saving}
                    rows={3}
                    maxLength={500}
                    className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 disabled:opacity-50 resize-none"
                  />
                  <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                    {formData.description.length}/500 characters
                  </p>
                </div>

                {/* Environment Type */}
                <div>
                  <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                    Environment Type
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    {Object.entries(ENVIRONMENT_TYPE_CONFIG).map(([type, config]) => (
                      <button
                        key={type}
                        type="button"
                        onClick={() => handleChange('environment_type', type)}
                        disabled={saving}
                        className={`
                          p-3 rounded-lg border-2 text-left transition-all
                          ${formData.environment_type === type
                            ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/20'
                            : 'border-surface-200 dark:border-surface-700 hover:border-surface-300 dark:hover:border-surface-600'
                          }
                          ${saving ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
                        `}
                      >
                        <p className="font-medium text-surface-900 dark:text-surface-100">
                          {config.label}
                        </p>
                        <p className="text-xs text-surface-500 dark:text-surface-400 mt-0.5">
                          {config.description}
                        </p>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Base Image */}
                <div>
                  <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                    Base Image
                  </label>
                  <select
                    value={formData.base_image}
                    onChange={(e) => handleChange('base_image', e.target.value)}
                    disabled={saving}
                    className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 disabled:opacity-50"
                  >
                    {BASE_IMAGES.map((image) => (
                      <option key={image.id} value={image.id}>
                        {image.name} - {image.description}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Network Policy */}
                <div>
                  <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                    Network Policy
                  </label>
                  <div className="space-y-2">
                    {NETWORK_POLICIES.map((policy) => (
                      <button
                        key={policy.id}
                        type="button"
                        onClick={() => handleChange('network_policy', policy.id)}
                        disabled={saving}
                        className={`
                          w-full p-3 rounded-lg border-2 text-left transition-all flex items-center justify-between
                          ${formData.network_policy === policy.id
                            ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/20'
                            : 'border-surface-200 dark:border-surface-700 hover:border-surface-300 dark:hover:border-surface-600'
                          }
                          ${saving ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
                        `}
                      >
                        <div className="flex items-center gap-3">
                          <GlobeAltIcon className="h-5 w-5 text-surface-400" />
                          <div>
                            <p className="font-medium text-surface-900 dark:text-surface-100">
                              {policy.name}
                            </p>
                            <p className="text-xs text-surface-500 dark:text-surface-400">
                              {policy.description}
                            </p>
                          </div>
                        </div>
                        {policy.severity === 'high' && (
                          <span className="px-2 py-0.5 bg-olive-100 dark:bg-olive-900/30 text-olive-700 dark:text-olive-400 text-xs font-medium rounded">
                            Recommended
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Requires Approval Toggle */}
                <div className="flex items-center justify-between py-3 border-t border-surface-200 dark:border-surface-700">
                  <div className="flex items-center gap-2">
                    <ShieldCheckIcon className="h-5 w-5 text-warning-500" />
                    <div>
                      <p className="font-medium text-surface-900 dark:text-surface-100">
                        Require HITL Approval
                      </p>
                      <p className="text-sm text-surface-500 dark:text-surface-400">
                        Require human approval before environment creation
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleChange('requires_approval', !formData.requires_approval)}
                    disabled={saving}
                    className={`
                      relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent
                      transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-aura-500
                      ${formData.requires_approval ? 'bg-warning-600' : 'bg-surface-200 dark:bg-surface-600'}
                      ${saving ? 'opacity-50 cursor-not-allowed' : ''}
                    `}
                  >
                    <span
                      className={`
                        pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0
                        transition duration-200 ease-in-out
                        ${formData.requires_approval ? 'translate-x-5' : 'translate-x-0'}
                      `}
                    />
                  </button>
                </div>
              </div>
            )}

            {/* Resources Tab */}
            {activeTab === 'resources' && (
              <div className="space-y-6">
                {/* Cost Estimate Banner */}
                <div className="flex items-center gap-3 p-4 bg-aura-50 dark:bg-aura-900/20 border border-aura-200 dark:border-aura-800 rounded-lg">
                  <CurrencyDollarIcon className="h-6 w-6 text-aura-600 dark:text-aura-400" />
                  <div>
                    <p className="font-semibold text-aura-800 dark:text-aura-200">
                      Estimated Cost: ${estimatedCost.toFixed(2)}/day
                    </p>
                    <p className="text-sm text-aura-700 dark:text-aura-300">
                      Based on selected resource allocation
                    </p>
                  </div>
                </div>

                {/* Resource Limits */}
                <CollapsibleSection
                  title="Resource Limits"
                  icon={CpuChipIcon}
                  defaultOpen={true}
                >
                  <div className="space-y-6">
                    <ResourceSlider
                      label="CPU"
                      description="Virtual CPU allocation for the environment"
                      value={formData.resource_limits.cpu}
                      onChange={(v) => handleResourceChange('cpu', v)}
                      min={RESOURCE_LIMITS.cpu.min}
                      max={RESOURCE_LIMITS.cpu.max}
                      step={RESOURCE_LIMITS.cpu.step}
                      unit={RESOURCE_LIMITS.cpu.unit}
                      disabled={saving}
                      icon={CpuChipIcon}
                    />

                    <ResourceSlider
                      label="Memory"
                      description="RAM allocation for the environment"
                      value={formData.resource_limits.memory}
                      onChange={(v) => handleResourceChange('memory', v)}
                      min={RESOURCE_LIMITS.memory.min}
                      max={RESOURCE_LIMITS.memory.max}
                      step={RESOURCE_LIMITS.memory.step}
                      unit={RESOURCE_LIMITS.memory.unit}
                      disabled={saving}
                      icon={CircleStackIcon}
                    />

                    <ResourceSlider
                      label="Storage"
                      description="Persistent disk storage allocation"
                      value={formData.resource_limits.storage}
                      onChange={(v) => handleResourceChange('storage', v)}
                      min={RESOURCE_LIMITS.storage.min}
                      max={RESOURCE_LIMITS.storage.max}
                      step={RESOURCE_LIMITS.storage.step}
                      unit={RESOURCE_LIMITS.storage.unit}
                      disabled={saving}
                      icon={CircleStackIcon}
                    />
                  </div>
                </CollapsibleSection>

                {/* Timeout Settings */}
                <CollapsibleSection
                  title="Timeout Settings"
                  icon={ClockIcon}
                  defaultOpen={true}
                >
                  <div className="space-y-6">
                    <ResourceSlider
                      label="Idle Timeout"
                      description="Auto-terminate after this period of inactivity"
                      value={formData.timeout_settings.idle_timeout_minutes}
                      onChange={(v) => handleTimeoutChange('idle_timeout_minutes', v)}
                      min={TIMEOUT_LIMITS.idle.min}
                      max={TIMEOUT_LIMITS.idle.max}
                      step={TIMEOUT_LIMITS.idle.step}
                      unit={TIMEOUT_LIMITS.idle.unit}
                      disabled={saving}
                      icon={ClockIcon}
                    />

                    <ResourceSlider
                      label="Maximum Duration"
                      description="Maximum environment lifetime"
                      value={formData.timeout_settings.max_duration_hours}
                      onChange={(v) => handleTimeoutChange('max_duration_hours', v)}
                      min={TIMEOUT_LIMITS.max.min}
                      max={TIMEOUT_LIMITS.max.max}
                      step={TIMEOUT_LIMITS.max.step}
                      unit={TIMEOUT_LIMITS.max.unit}
                      disabled={saving}
                      icon={ClockIcon}
                    />

                    {/* Default TTL */}
                    <div>
                      <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                        Default TTL (hours)
                      </label>
                      <input
                        type="number"
                        value={formData.default_ttl_hours}
                        onChange={(e) => handleChange('default_ttl_hours', Number(e.target.value))}
                        min={1}
                        max={formData.timeout_settings.max_duration_hours}
                        disabled={saving}
                        className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 disabled:opacity-50"
                      />
                      <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                        Default time-to-live when creating environments from this template
                      </p>
                    </div>
                  </div>
                </CollapsibleSection>
              </div>
            )}

            {/* Advanced Tab */}
            {activeTab === 'advanced' && (
              <div className="space-y-6">
                {/* Environment Variables */}
                <CollapsibleSection
                  title="Environment Variables"
                  icon={VariableIcon}
                  defaultOpen={true}
                >
                  <EnvVarsEditor
                    variables={formData.environment_variables}
                    onChange={(vars) => handleChange('environment_variables', vars)}
                    disabled={saving}
                  />
                </CollapsibleSection>

                {/* Init Script */}
                <CollapsibleSection
                  title="Initialization Script"
                  icon={CodeBracketIcon}
                  defaultOpen={Object.keys(formData.init_script || '').length > 0}
                >
                  <div>
                    <p className="text-sm text-surface-500 dark:text-surface-400 mb-3">
                      Shell script to run when the environment starts. Maximum 10,000 characters.
                    </p>
                    <textarea
                      value={formData.init_script}
                      onChange={(e) => handleChange('init_script', e.target.value)}
                      placeholder={`#!/bin/bash\n# Add initialization commands here\npip install -r requirements.txt`}
                      disabled={saving}
                      rows={10}
                      maxLength={10000}
                      className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-surface-50 dark:bg-surface-900 text-surface-900 dark:text-surface-100 font-mono text-sm focus:ring-2 focus:ring-aura-500 focus:border-aura-500 disabled:opacity-50 resize-y"
                    />
                    <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                      {formData.init_script.length}/10,000 characters
                    </p>
                  </div>
                </CollapsibleSection>
              </div>
            )}

            {/* Test Results */}
            {testResults && (
              <div className="mt-6">
                <TestResults
                  results={testResults}
                  onDismiss={() => setTestResults(null)}
                />
              </div>
            )}

            {/* Submit Error */}
            {errors.submit && (
              <div className="mt-6 flex items-center gap-2 p-3 rounded-lg bg-critical-50 dark:bg-critical-900/20 text-critical-700 dark:text-critical-300">
                <XCircleIcon className="h-5 w-5" />
                <span className="text-sm">{errors.submit}</span>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-surface-100/50 dark:border-surface-700/30 bg-white/60 dark:bg-surface-800/50 backdrop-blur-sm">
            <div className="flex items-center justify-between">
              {/* Cost indicator */}
              <div className="flex items-center gap-2 text-sm text-surface-500 dark:text-surface-400">
                <CurrencyDollarIcon className="h-4 w-4" />
                <span>Est. ${estimatedCost.toFixed(2)}/day</span>
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={onClose}
                  disabled={saving}
                  className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-white/60 dark:hover:bg-surface-700 rounded-xl transition-all duration-200 ease-[var(--ease-tahoe)]"
                >
                  Cancel
                </button>

                <button
                  onClick={handleTest}
                  disabled={saving || testing}
                  className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 border border-surface-200/50 dark:border-surface-600/50 rounded-xl bg-white/60 dark:bg-surface-700 hover:bg-white/80 dark:hover:bg-surface-700 transition-all duration-200 ease-[var(--ease-tahoe)] disabled:opacity-50"
                >
                  {testing ? (
                    <ArrowPathIcon className="h-4 w-4 animate-spin" />
                  ) : (
                    <BeakerIcon className="h-4 w-4" />
                  )}
                  Test Configuration
                </button>

                <button
                  onClick={handleSave}
                  disabled={saving || !hasChanges}
                  className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-aura-600 rounded-xl hover:bg-aura-700 shadow-[var(--shadow-glass)] hover:shadow-[var(--shadow-glass-hover)] disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 ease-[var(--ease-tahoe)]"
                >
                  {saving ? (
                    <ArrowPathIcon className="h-4 w-4 animate-spin" />
                  ) : (
                    <CheckCircleIcon className="h-4 w-4" />
                  )}
                  {isCreating ? 'Create Template' : 'Save Changes'}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
