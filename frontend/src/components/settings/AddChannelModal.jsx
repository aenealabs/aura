/**
 * Project Aura - Add Channel Modal Component
 *
 * Modal for adding new notification channels.
 * Features:
 * - Channel type selection (Email, Slack, Teams, PagerDuty, Webhook)
 * - Dynamic configuration fields based on channel type
 * - Test connection validation
 * - Apple-inspired design with clean transitions
 */

import { useState, useEffect } from 'react';
import {
  XMarkIcon,
  EnvelopeIcon,
  ChatBubbleLeftRightIcon,
  BellAlertIcon,
  LinkIcon,
  ExclamationTriangleIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  XCircleIcon,
  PlayIcon,
  PlusIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';

import {
  CHANNEL_TYPE_CONFIG,
} from '../../services/notificationsApi';

// Icon mapping for channel types
const CHANNEL_ICONS = {
  email: EnvelopeIcon,
  slack: ChatBubbleLeftRightIcon,
  teams: ChatBubbleLeftRightIcon,
  sns: BellAlertIcon,
  webhook: LinkIcon,
  pagerduty: ExclamationTriangleIcon,
};

// Color styles for channel types
const CHANNEL_COLORS = {
  email: {
    bg: 'bg-aura-100 dark:bg-aura-900/30',
    text: 'text-aura-600 dark:text-aura-400',
    border: 'border-aura-200 dark:border-aura-800',
    ring: 'ring-aura-500',
  },
  slack: {
    bg: 'bg-olive-100 dark:bg-olive-900/30',
    text: 'text-olive-600 dark:text-olive-400',
    border: 'border-olive-200 dark:border-olive-800',
    ring: 'ring-olive-500',
  },
  teams: {
    bg: 'bg-indigo-100 dark:bg-indigo-900/30',
    text: 'text-indigo-600 dark:text-indigo-400',
    border: 'border-indigo-200 dark:border-indigo-800',
    ring: 'ring-indigo-500',
  },
  sns: {
    bg: 'bg-warning-100 dark:bg-warning-900/30',
    text: 'text-warning-600 dark:text-warning-400',
    border: 'border-warning-200 dark:border-warning-800',
    ring: 'ring-warning-500',
  },
  webhook: {
    bg: 'bg-surface-100 dark:bg-surface-700',
    text: 'text-surface-600 dark:text-surface-400',
    border: 'border-surface-200 dark:border-surface-600',
    ring: 'ring-surface-500',
  },
  pagerduty: {
    bg: 'bg-critical-100 dark:bg-critical-900/30',
    text: 'text-critical-600 dark:text-critical-400',
    border: 'border-critical-200 dark:border-critical-800',
    ring: 'ring-critical-500',
  },
};

// Field configuration for each channel type
const CHANNEL_FIELD_CONFIG = {
  email: [
    {
      name: 'recipients',
      label: 'Recipients',
      type: 'tags',
      placeholder: 'Enter email addresses',
      required: true,
      description: 'Email addresses to receive notifications',
    },
    {
      name: 'from_address',
      label: 'From Address',
      type: 'email',
      placeholder: 'noreply@example.com',
      required: false,
      description: 'Sender email address (optional)',
    },
    {
      name: 'subject_prefix',
      label: 'Subject Prefix',
      type: 'text',
      placeholder: '[Aura Alert]',
      required: false,
      description: 'Prefix added to email subjects',
    },
  ],
  slack: [
    {
      name: 'webhook_url',
      label: 'Webhook URL',
      type: 'url',
      placeholder: 'https://hooks.slack.com/services/...',
      required: true,
      description: 'Slack incoming webhook URL',
    },
    {
      name: 'channel',
      label: 'Channel',
      type: 'text',
      placeholder: 'alerts',
      required: true,
      description: 'Slack channel name (without #)',
    },
    {
      name: 'bot_name',
      label: 'Bot Name',
      type: 'text',
      placeholder: 'Aura Bot',
      required: false,
      description: 'Display name for the bot',
    },
    {
      name: 'icon_emoji',
      label: 'Icon Emoji',
      type: 'text',
      placeholder: ':shield:',
      required: false,
      description: 'Emoji to use as bot icon',
    },
  ],
  teams: [
    {
      name: 'webhook_url',
      label: 'Webhook URL',
      type: 'url',
      placeholder: 'https://outlook.office.com/webhook/...',
      required: true,
      description: 'Microsoft Teams incoming webhook URL',
    },
    {
      name: 'channel_name',
      label: 'Channel Name',
      type: 'text',
      placeholder: 'Security Alerts',
      required: false,
      description: 'Channel name for reference',
    },
  ],
  sns: [
    {
      name: 'topic_arn',
      label: 'Topic ARN',
      type: 'text',
      placeholder: 'arn:aws:sns:us-east-1:123456789:topic-name',
      required: true,
      description: 'AWS SNS topic ARN',
    },
    {
      name: 'region',
      label: 'AWS Region',
      type: 'select',
      options: [
        { value: 'us-east-1', label: 'US East (N. Virginia)' },
        { value: 'us-east-2', label: 'US East (Ohio)' },
        { value: 'us-west-1', label: 'US West (N. California)' },
        { value: 'us-west-2', label: 'US West (Oregon)' },
        { value: 'us-gov-west-1', label: 'AWS GovCloud (US-West)' },
        { value: 'us-gov-east-1', label: 'AWS GovCloud (US-East)' },
      ],
      required: true,
      description: 'AWS region for the SNS topic',
    },
  ],
  webhook: [
    {
      name: 'url',
      label: 'Webhook URL',
      type: 'url',
      placeholder: 'https://api.example.com/webhooks/alerts',
      required: true,
      description: 'HTTP endpoint to receive POST requests',
    },
    {
      name: 'auth_type',
      label: 'Authentication Type',
      type: 'select',
      options: [
        { value: 'none', label: 'None' },
        { value: 'bearer', label: 'Bearer Token' },
        { value: 'basic', label: 'Basic Auth' },
        { value: 'api_key', label: 'API Key Header' },
      ],
      required: false,
      description: 'Authentication method for the webhook',
    },
    {
      name: 'auth_token',
      label: 'Auth Token / API Key',
      type: 'password',
      placeholder: 'Enter token or API key',
      required: false,
      description: 'Authentication credential',
      showWhen: (config) => config.auth_type && config.auth_type !== 'none',
    },
    {
      name: 'headers',
      label: 'Custom Headers',
      type: 'keyvalue',
      placeholder: 'Add custom headers',
      required: false,
      description: 'Additional HTTP headers to include',
    },
  ],
  pagerduty: [
    {
      name: 'routing_key',
      label: 'Routing Key',
      type: 'password',
      placeholder: 'Enter PagerDuty routing key',
      required: true,
      description: 'PagerDuty Events API v2 routing key',
    },
    {
      name: 'service_id',
      label: 'Service ID',
      type: 'text',
      placeholder: 'PXXXXXX',
      required: false,
      description: 'PagerDuty service identifier',
    },
  ],
};

/**
 * Tag Input Component for email recipients
 */
function TagInput({ value = [], onChange, placeholder, disabled }) {
  const [inputValue, setInputValue] = useState('');

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addTag();
    } else if (e.key === 'Backspace' && !inputValue && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  };

  const addTag = () => {
    const trimmed = inputValue.trim().replace(',', '');
    if (trimmed && !value.includes(trimmed)) {
      onChange([...value, trimmed]);
    }
    setInputValue('');
  };

  const removeTag = (index) => {
    onChange(value.filter((_, i) => i !== index));
  };

  return (
    <div className={`
      min-h-[42px] px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg
      bg-white dark:bg-surface-700 focus-within:ring-2 focus-within:ring-aura-500 focus-within:border-aura-500
      ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
    `}>
      <div className="flex flex-wrap gap-2">
        {value.map((tag, index) => (
          <span
            key={index}
            className="inline-flex items-center gap-1 px-2 py-0.5 bg-aura-100 dark:bg-aura-900/30 text-aura-700 dark:text-aura-300 text-sm rounded-md"
          >
            {tag}
            <button
              type="button"
              onClick={() => removeTag(index)}
              disabled={disabled}
              className="p-0.5 hover:bg-aura-200 dark:hover:bg-aura-800 rounded transition-colors"
            >
              <XMarkIcon className="h-3 w-3" />
            </button>
          </span>
        ))}
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={addTag}
          placeholder={value.length === 0 ? placeholder : ''}
          disabled={disabled}
          className="flex-1 min-w-[120px] bg-transparent border-none outline-none text-sm text-surface-900 dark:text-surface-100 placeholder-surface-400"
        />
      </div>
    </div>
  );
}

/**
 * Key-Value Input Component for custom headers
 */
function KeyValueInput({ value = {}, onChange, disabled }) {
  const entries = Object.entries(value);

  const addEntry = () => {
    onChange({ ...value, '': '' });
  };

  const updateEntry = (oldKey, newKey, newValue) => {
    const updated = { ...value };
    if (oldKey !== newKey) {
      delete updated[oldKey];
    }
    updated[newKey] = newValue;
    onChange(updated);
  };

  const removeEntry = (key) => {
    const updated = { ...value };
    delete updated[key];
    onChange(updated);
  };

  return (
    <div className="space-y-2">
      {entries.map(([key, val], index) => (
        <div key={index} className="flex items-center gap-2">
          <input
            type="text"
            value={key}
            onChange={(e) => updateEntry(key, e.target.value, val)}
            placeholder="Header name"
            disabled={disabled}
            className="flex-1 px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 text-sm focus:ring-2 focus:ring-aura-500 focus:border-aura-500 disabled:opacity-50"
          />
          <input
            type="text"
            value={val}
            onChange={(e) => updateEntry(key, key, e.target.value)}
            placeholder="Value"
            disabled={disabled}
            className="flex-1 px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 text-sm focus:ring-2 focus:ring-aura-500 focus:border-aura-500 disabled:opacity-50"
          />
          <button
            type="button"
            onClick={() => removeEntry(key)}
            disabled={disabled}
            className="p-2 text-surface-400 hover:text-critical-600 dark:hover:text-critical-400 transition-colors"
          >
            <TrashIcon className="h-4 w-4" />
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={addEntry}
        disabled={disabled}
        className="flex items-center gap-1 text-sm text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300"
      >
        <PlusIcon className="h-4 w-4" />
        Add header
      </button>
    </div>
  );
}

/**
 * Channel Type Selector
 */
function ChannelTypeSelector({ selected, onSelect, disabled }) {
  const channelTypes = Object.keys(CHANNEL_TYPE_CONFIG);

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
      {channelTypes.map((type) => {
        const config = CHANNEL_TYPE_CONFIG[type];
        const colors = CHANNEL_COLORS[type];
        const Icon = CHANNEL_ICONS[type];
        const isSelected = selected === type;

        return (
          <button
            key={type}
            type="button"
            onClick={() => onSelect(type)}
            disabled={disabled}
            className={`
              flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all
              ${isSelected
                ? `${colors.border} ${colors.bg} ring-2 ${colors.ring}`
                : 'border-surface-200 dark:border-surface-700 hover:border-surface-300 dark:hover:border-surface-600'
              }
              ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
            `}
          >
            <div className={`p-2 rounded-lg ${isSelected ? colors.bg : 'bg-surface-100 dark:bg-surface-700'}`}>
              <Icon className={`h-5 w-5 ${isSelected ? colors.text : 'text-surface-500 dark:text-surface-400'}`} />
            </div>
            <span className={`text-sm font-medium ${isSelected ? colors.text : 'text-surface-700 dark:text-surface-300'}`}>
              {config.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}

/**
 * Form Field Component
 */
function FormField({ field, value, onChange, disabled }) {
  const renderInput = () => {
    switch (field.type) {
      case 'tags':
        return (
          <TagInput
            value={value || []}
            onChange={onChange}
            placeholder={field.placeholder}
            disabled={disabled}
          />
        );

      case 'select':
        return (
          <select
            value={value || ''}
            onChange={(e) => onChange(e.target.value)}
            disabled={disabled}
            className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 disabled:opacity-50"
          >
            <option value="">Select an option</option>
            {field.options?.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        );

      case 'keyvalue':
        return (
          <KeyValueInput
            value={value || {}}
            onChange={onChange}
            disabled={disabled}
          />
        );

      case 'password':
        return (
          <input
            type="password"
            value={value || ''}
            onChange={(e) => onChange(e.target.value)}
            placeholder={field.placeholder}
            disabled={disabled}
            className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 disabled:opacity-50"
          />
        );

      case 'url':
      case 'email':
      case 'text':
      default:
        return (
          <input
            type={field.type}
            value={value || ''}
            onChange={(e) => onChange(e.target.value)}
            placeholder={field.placeholder}
            disabled={disabled}
            className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 disabled:opacity-50"
          />
        );
    }
  };

  return (
    <div>
      <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
        {field.label}
        {field.required && <span className="text-critical-500 ml-1">*</span>}
      </label>
      {renderInput()}
      {field.description && (
        <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
          {field.description}
        </p>
      )}
    </div>
  );
}

/**
 * Main Add Channel Modal Component
 */
export default function AddChannelModal({ isOpen, onClose, onSave, onTest }) {
  const [step, setStep] = useState(1);
  const [channelType, setChannelType] = useState(null);
  const [channelName, setChannelName] = useState('');
  const [config, setConfig] = useState({});
  const [enabled, setEnabled] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [errors, setErrors] = useState({});

  // Reset form when modal opens/closes
  useEffect(() => {
    if (isOpen) {
      setStep(1);
      setChannelType(null);
      setChannelName('');
      setConfig({});
      setEnabled(true);
      setTestResult(null);
      setErrors({});
    }
  }, [isOpen]);

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

  const handleTypeSelect = (type) => {
    setChannelType(type);
    setConfig({});
    setChannelName(`${CHANNEL_TYPE_CONFIG[type].label} Channel`);
    setStep(2);
  };

  const handleConfigChange = (fieldName, value) => {
    setConfig((prev) => ({ ...prev, [fieldName]: value }));
    setErrors((prev) => ({ ...prev, [fieldName]: null }));
  };

  const validateForm = () => {
    const newErrors = {};
    const fields = CHANNEL_FIELD_CONFIG[channelType] || [];

    if (!channelName.trim()) {
      newErrors.name = 'Channel name is required';
    }

    fields.forEach((field) => {
      if (field.required) {
        const value = config[field.name];
        if (field.type === 'tags') {
          if (!value || value.length === 0) {
            newErrors[field.name] = `${field.label} is required`;
          }
        } else if (!value || (typeof value === 'string' && !value.trim())) {
          newErrors[field.name] = `${field.label} is required`;
        }
      }
    });

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleTest = async () => {
    if (!validateForm()) return;

    setTesting(true);
    setTestResult(null);

    try {
      await onTest?.({
        type: channelType,
        name: channelName,
        config,
        enabled,
      });
      setTestResult({ success: true, message: 'Connection successful' });
    } catch (error) {
      setTestResult({ success: false, message: error.message || 'Connection failed' });
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    if (!validateForm()) return;

    setSaving(true);

    try {
      await onSave({
        type: channelType,
        name: channelName.trim(),
        config,
        enabled,
      });
      onClose();
    } catch (error) {
      setErrors({ submit: error.message || 'Failed to save channel' });
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  const fields = CHANNEL_FIELD_CONFIG[channelType] || [];
  const typeConfig = channelType ? CHANNEL_TYPE_CONFIG[channelType] : null;
  const colors = channelType ? CHANNEL_COLORS[channelType] : null;
  const Icon = channelType ? CHANNEL_ICONS[channelType] : null;

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
          className="relative w-full max-w-lg bg-white/95 dark:bg-surface-800/95 backdrop-blur-xl backdrop-saturate-150 rounded-2xl shadow-[var(--shadow-glass-hover)] overflow-hidden animate-in fade-in zoom-in-95 duration-[var(--duration-overlay)] ease-[var(--ease-tahoe)]"
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-title"
        >
          {/* Header */}
          <div className="px-6 py-4 border-b border-surface-100/50 dark:border-surface-700/30">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {step === 2 && Icon && (
                  <div className={`p-2 rounded-lg ${colors.bg}`}>
                    <Icon className={`h-5 w-5 ${colors.text}`} />
                  </div>
                )}
                <div>
                  <h2
                    id="modal-title"
                    className="text-lg font-semibold text-surface-900 dark:text-surface-100"
                  >
                    {step === 1 ? 'Add Notification Channel' : `Configure ${typeConfig?.label}`}
                  </h2>
                  <p className="text-sm text-surface-500 dark:text-surface-400 mt-0.5">
                    {step === 1
                      ? 'Select a channel type to get started'
                      : typeConfig?.description
                    }
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

          {/* Body */}
          <div className="p-6 max-h-[60vh] overflow-y-auto">
            {step === 1 ? (
              <ChannelTypeSelector
                selected={channelType}
                onSelect={handleTypeSelect}
                disabled={saving}
              />
            ) : (
              <div className="space-y-4">
                {/* Channel Name */}
                <div>
                  <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                    Channel Name
                    <span className="text-critical-500 ml-1">*</span>
                  </label>
                  <input
                    type="text"
                    value={channelName}
                    onChange={(e) => {
                      setChannelName(e.target.value);
                      setErrors((prev) => ({ ...prev, name: null }));
                    }}
                    placeholder="Enter a name for this channel"
                    disabled={saving}
                    className={`
                      w-full px-3 py-2 border rounded-lg bg-white dark:bg-surface-700
                      text-surface-900 dark:text-surface-100
                      focus:ring-2 focus:ring-aura-500 focus:border-aura-500 disabled:opacity-50
                      ${errors.name ? 'border-critical-300 dark:border-critical-700' : 'border-surface-300 dark:border-surface-600'}
                    `}
                  />
                  {errors.name && (
                    <p className="text-xs text-critical-600 dark:text-critical-400 mt-1">{errors.name}</p>
                  )}
                </div>

                {/* Dynamic Fields */}
                {fields.map((field) => {
                  // Check if field should be shown
                  if (field.showWhen && !field.showWhen(config)) {
                    return null;
                  }

                  return (
                    <div key={field.name}>
                      <FormField
                        field={field}
                        value={config[field.name]}
                        onChange={(value) => handleConfigChange(field.name, value)}
                        disabled={saving}
                      />
                      {errors[field.name] && (
                        <p className="text-xs text-critical-600 dark:text-critical-400 mt-1">
                          {errors[field.name]}
                        </p>
                      )}
                    </div>
                  );
                })}

                {/* Enabled Toggle */}
                <div className="flex items-center justify-between py-2">
                  <div>
                    <p className="font-medium text-surface-900 dark:text-surface-100">Enable Channel</p>
                    <p className="text-sm text-surface-500 dark:text-surface-400">
                      Start receiving notifications immediately
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setEnabled(!enabled)}
                    disabled={saving}
                    className={`
                      relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent
                      transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-aura-500
                      ${enabled ? 'bg-olive-600' : 'bg-surface-200 dark:bg-surface-600'}
                      ${saving ? 'opacity-50 cursor-not-allowed' : ''}
                    `}
                  >
                    <span
                      className={`
                        pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0
                        transition duration-200 ease-in-out
                        ${enabled ? 'translate-x-5' : 'translate-x-0'}
                      `}
                    />
                  </button>
                </div>

                {/* Test Connection Result */}
                {testResult && (
                  <div className={`
                    flex items-center gap-2 p-3 rounded-lg
                    ${testResult.success
                      ? 'bg-olive-50 dark:bg-olive-900/20 text-olive-700 dark:text-olive-300'
                      : 'bg-critical-50 dark:bg-critical-900/20 text-critical-700 dark:text-critical-300'
                    }
                  `}>
                    {testResult.success ? (
                      <CheckCircleIcon className="h-5 w-5" />
                    ) : (
                      <XCircleIcon className="h-5 w-5" />
                    )}
                    <span className="text-sm">{testResult.message}</span>
                  </div>
                )}

                {/* Submit Error */}
                {errors.submit && (
                  <div className="flex items-center gap-2 p-3 rounded-lg bg-critical-50 dark:bg-critical-900/20 text-critical-700 dark:text-critical-300">
                    <XCircleIcon className="h-5 w-5" />
                    <span className="text-sm">{errors.submit}</span>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-surface-100/50 dark:border-surface-700/30 bg-white/60 dark:bg-surface-800/50 backdrop-blur-sm">
            <div className="flex items-center justify-between">
              <div>
                {step === 2 && (
                  <button
                    onClick={() => setStep(1)}
                    disabled={saving}
                    className="text-sm text-surface-600 dark:text-surface-400 hover:text-surface-800 dark:hover:text-surface-200"
                  >
                    Back to channel types
                  </button>
                )}
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={onClose}
                  disabled={saving}
                  className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-white/60 dark:hover:bg-surface-700 rounded-xl transition-all duration-200 ease-[var(--ease-tahoe)]"
                >
                  Cancel
                </button>

                {step === 2 && (
                  <>
                    <button
                      onClick={handleTest}
                      disabled={saving || testing}
                      className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 border border-surface-200/50 dark:border-surface-600/50 rounded-xl bg-white/60 dark:bg-surface-700 hover:bg-white/80 dark:hover:bg-surface-700 transition-all duration-200 ease-[var(--ease-tahoe)] disabled:opacity-50"
                    >
                      {testing ? (
                        <ArrowPathIcon className="h-4 w-4 animate-spin" />
                      ) : (
                        <PlayIcon className="h-4 w-4" />
                      )}
                      Test Connection
                    </button>

                    <button
                      onClick={handleSave}
                      disabled={saving}
                      className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-aura-600 rounded-xl hover:bg-aura-700 shadow-[var(--shadow-glass)] hover:shadow-[var(--shadow-glass-hover)] disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 ease-[var(--ease-tahoe)]"
                    >
                      {saving ? (
                        <ArrowPathIcon className="h-4 w-4 animate-spin" />
                      ) : (
                        <PlusIcon className="h-4 w-4" />
                      )}
                      Add Channel
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
