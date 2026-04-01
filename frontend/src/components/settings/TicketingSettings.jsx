/**
 * Project Aura - Support Ticketing Settings Component
 *
 * Configure support ticketing provider and credentials.
 * See ADR-046 for architecture details.
 */

import { useState, useEffect } from 'react';
import {
  TicketIcon,
  CheckCircleIcon,
  XCircleIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  PlayIcon,
  TrashIcon,
  EyeIcon,
  EyeSlashIcon,
  LinkIcon,
} from '@heroicons/react/24/outline';

import {
  getTicketingConfig,
  saveTicketingConfig,
  testTicketingConnection,
  TICKETING_PROVIDERS,
  DEFAULT_TICKETING_CONFIG,
} from '../../services/ticketingApi';

// Import proper brand logos from ProviderLogos
import {
  GitHubLogo,
  ZendeskLogo,
  LinearLogo,
  ServiceNowLogo,
} from '../integrations/ProviderLogos';

// Provider logo mapping for ticketing providers
const PROVIDER_LOGOS = {
  github: GitHubLogo,
  zendesk: ZendeskLogo,
  linear: LinearLogo,
  servicenow: ServiceNowLogo,
};

/**
 * Provider Card Component
 */
function ProviderCard({ provider, isSelected, onSelect, disabled }) {
  const providerData = TICKETING_PROVIDERS[provider];
  const ProviderLogo = PROVIDER_LOGOS[provider];

  return (
    <button
      type="button"
      onClick={() => onSelect(provider)}
      disabled={disabled || !providerData.isImplemented}
      className={`
        relative flex flex-col items-center p-4 rounded-xl border-2 transition-all
        ${isSelected
          ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/20'
          : 'border-surface-200 dark:border-surface-700 hover:border-surface-300 dark:hover:border-surface-600'
        }
        ${disabled || !providerData.isImplemented ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'}
      `}
    >
      <ProviderLogo className="h-10 w-10 rounded-lg mb-3" />
      <h4 className="font-medium text-surface-900 dark:text-surface-100 text-center">
        {providerData.name}
      </h4>
      <p className="text-xs text-surface-500 dark:text-surface-400 text-center mt-1">
        {providerData.description}
      </p>
      {!providerData.isImplemented && (
        <span className="absolute top-2 right-2 px-1.5 py-0.5 text-xs bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400 rounded">
          Coming Soon
        </span>
      )}
      {isSelected && (
        <CheckCircleIcon className="absolute top-2 right-2 h-5 w-5 text-aura-600 dark:text-aura-400" />
      )}
    </button>
  );
}

/**
 * Configuration Form Component
 */
function ConfigurationForm({ provider, config, onChange, onTest, testing, isLoading }) {
  const providerData = TICKETING_PROVIDERS[provider];
  const [showSecrets, setShowSecrets] = useState({});

  if (!providerData) return null;

  const toggleSecret = (fieldName) => {
    setShowSecrets(prev => ({ ...prev, [fieldName]: !prev[fieldName] }));
  };

  const handleFieldChange = (fieldName, value) => {
    onChange({ ...config, [fieldName]: value });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-4">
        <h4 className="font-medium text-surface-900 dark:text-surface-100">
          Configure {providerData.name}
        </h4>
        <a
          href={`https://docs.aenealabs.com/integrations/${provider}`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 text-sm text-aura-600 dark:text-aura-400 hover:underline"
        >
          <LinkIcon className="h-4 w-4" />
          Setup Guide
        </a>
      </div>

      {providerData.configFields.map((field) => (
        <div key={field.name}>
          <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
            {field.label}
            {field.required && <span className="text-critical-500 ml-1">*</span>}
          </label>

          {field.type === 'password' ? (
            <div className="relative">
              <input
                type={showSecrets[field.name] ? 'text' : 'password'}
                value={config[field.name] || ''}
                onChange={(e) => handleFieldChange(field.name, e.target.value)}
                placeholder={field.placeholder || ''}
                disabled={isLoading}
                className="w-full px-3 py-2 pr-10 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 disabled:opacity-50"
              />
              <button
                type="button"
                onClick={() => toggleSecret(field.name)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-surface-400 hover:text-surface-600"
              >
                {showSecrets[field.name] ? (
                  <EyeSlashIcon className="h-5 w-5" />
                ) : (
                  <EyeIcon className="h-5 w-5" />
                )}
              </button>
            </div>
          ) : field.type === 'select' ? (
            <select
              value={config[field.name] || ''}
              onChange={(e) => handleFieldChange(field.name, e.target.value)}
              disabled={isLoading}
              className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent disabled:opacity-50"
            >
              <option value="">Select...</option>
              {field.options?.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          ) : field.type === 'tags' ? (
            <TagsInput
              value={config[field.name] || []}
              onChange={(value) => handleFieldChange(field.name, value)}
              placeholder={field.placeholder || 'Add labels...'}
              disabled={isLoading}
            />
          ) : (
            <input
              type={field.type}
              value={config[field.name] || ''}
              onChange={(e) => handleFieldChange(field.name, e.target.value)}
              placeholder={field.placeholder || ''}
              disabled={isLoading}
              className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent disabled:opacity-50"
            />
          )}

          {field.helpText && (
            <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
              {field.helpText}
            </p>
          )}
        </div>
      ))}

      <div className="pt-4">
        <button
          type="button"
          onClick={onTest}
          disabled={isLoading || testing}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-surface-100 dark:bg-surface-700 text-surface-700 dark:text-surface-300 rounded-lg hover:bg-surface-200 dark:hover:bg-surface-600 disabled:opacity-50 transition-colors"
        >
          {testing ? (
            <>
              <ArrowPathIcon className="h-4 w-4 animate-spin" />
              Testing Connection...
            </>
          ) : (
            <>
              <PlayIcon className="h-4 w-4" />
              Test Connection
            </>
          )}
        </button>
      </div>
    </div>
  );
}

/**
 * Tags Input Component
 */
function TagsInput({ value = [], onChange, placeholder, disabled }) {
  const [inputValue, setInputValue] = useState('');

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      const tag = inputValue.trim();
      if (tag && !value.includes(tag)) {
        onChange([...value, tag]);
      }
      setInputValue('');
    } else if (e.key === 'Backspace' && !inputValue && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  };

  const removeTag = (tagToRemove) => {
    onChange(value.filter(tag => tag !== tagToRemove));
  };

  return (
    <div className="flex flex-wrap gap-2 p-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 min-h-[42px]">
      {value.map((tag) => (
        <span
          key={tag}
          className="flex items-center gap-1 px-2 py-0.5 bg-aura-100 dark:bg-aura-900/30 text-aura-700 dark:text-aura-300 rounded text-sm"
        >
          {tag}
          <button
            type="button"
            onClick={() => removeTag(tag)}
            disabled={disabled}
            className="text-aura-500 hover:text-aura-700 dark:hover:text-aura-200"
          >
            <XCircleIcon className="h-4 w-4" />
          </button>
        </span>
      ))}
      <input
        type="text"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={value.length === 0 ? placeholder : ''}
        disabled={disabled}
        className="flex-1 min-w-[100px] bg-transparent border-none outline-none text-surface-900 dark:text-surface-100 text-sm"
      />
    </div>
  );
}

/**
 * Connection Status Banner
 */
function ConnectionStatus({ status, lastTested }) {
  if (!status) return null;

  return (
    <div className={`
      flex items-center gap-3 p-3 rounded-lg
      ${status === 'connected'
        ? 'bg-olive-50 dark:bg-olive-900/20 text-olive-700 dark:text-olive-300'
        : status === 'error'
        ? 'bg-critical-50 dark:bg-critical-900/20 text-critical-700 dark:text-critical-300'
        : 'bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-400'
      }
    `}>
      {status === 'connected' ? (
        <CheckCircleIcon className="h-5 w-5" />
      ) : status === 'error' ? (
        <XCircleIcon className="h-5 w-5" />
      ) : (
        <ExclamationTriangleIcon className="h-5 w-5" />
      )}
      <div className="flex-1">
        <p className="font-medium">
          {status === 'connected' ? 'Connected' :
           status === 'error' ? 'Connection Failed' :
           'Not Configured'}
        </p>
        {lastTested && (
          <p className="text-xs opacity-75">
            Last tested: {new Date(lastTested).toLocaleString()}
          </p>
        )}
      </div>
    </div>
  );
}

/**
 * Main Ticketing Settings Component
 */
export default function TicketingSettings({ onSuccess, onError }) {
  const [config, setConfig] = useState(DEFAULT_TICKETING_CONFIG);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState(null);
  const [hasChanges, setHasChanges] = useState(false);

  // Load ticketing config on mount only (loadConfig defined below)
  useEffect(() => {
    loadConfig();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadConfig = async () => {
    setLoading(true);
    try {
      const data = await getTicketingConfig();
      setConfig(data);
      if (data.enabled && data.provider) {
        setConnectionStatus('connected');
      }
    } catch (err) {
      onError?.(`Failed to load ticketing configuration: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleProviderSelect = (provider) => {
    setConfig(prev => ({
      ...prev,
      provider,
      config: {},
    }));
    setConnectionStatus(null);
    setHasChanges(true);
  };

  const handleConfigChange = (newConfig) => {
    setConfig(prev => ({
      ...prev,
      config: newConfig,
    }));
    setConnectionStatus(null);
    setHasChanges(true);
  };

  const handleTestConnection = async () => {
    setTesting(true);
    try {
      const result = await testTicketingConnection({
        provider: config.provider,
        config: config.config,
      });

      if (result.success) {
        setConnectionStatus('connected');
        onSuccess?.('Connection successful!');
      } else {
        setConnectionStatus('error');
        onError?.(result.error_message || 'Connection test failed');
      }
    } catch (err) {
      setConnectionStatus('error');
      onError?.(`Connection test failed: ${err.message}`);
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveTicketingConfig({
        ...config,
        enabled: true,
      });
      setHasChanges(false);
      onSuccess?.('Ticketing configuration saved');
    } catch (err) {
      onError?.(`Failed to save configuration: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleDisable = async () => {
    setSaving(true);
    try {
      await saveTicketingConfig({
        ...config,
        enabled: false,
      });
      setConfig(prev => ({ ...prev, enabled: false }));
      setConnectionStatus(null);
      onSuccess?.('Ticketing integration disabled');
    } catch (err) {
      onError?.(`Failed to disable integration: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <ArrowPathIcon className="h-8 w-8 text-aura-500 animate-spin" />
        <span className="ml-3 text-surface-600 dark:text-surface-400">
          Loading ticketing settings...
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Info Banner */}
      <div className="flex items-start gap-3 p-4 bg-aura-50 dark:bg-aura-900/20 border border-aura-200 dark:border-aura-800 rounded-lg">
        <InformationCircleIcon className="h-5 w-5 text-aura-600 dark:text-aura-400 flex-shrink-0 mt-0.5" />
        <div>
          <h4 className="font-medium text-aura-800 dark:text-aura-200">Support Ticketing Integration</h4>
          <p className="text-sm text-aura-700 dark:text-aura-300 mt-1">
            Connect Aura to your ticketing system to create and manage support tickets
            directly from the platform. Tickets are created automatically for HITL
            approvals, security alerts, and customer requests.
          </p>
        </div>
      </div>

      {/* Connection Status */}
      {config.enabled && (
        <ConnectionStatus
          status={connectionStatus}
          lastTested={config.last_tested_at}
        />
      )}

      {/* Provider Selection */}
      <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)]">
        <div className="p-4 border-b border-surface-200 dark:border-surface-700">
          <div className="flex items-center gap-2">
            <TicketIcon className="h-5 w-5 text-aura-600 dark:text-aura-400" />
            <h3 className="font-semibold text-surface-900 dark:text-surface-100">
              Select Provider
            </h3>
          </div>
          <p className="text-sm text-surface-500 dark:text-surface-400 mt-1">
            Choose your ticketing system. GitHub Issues is recommended for most teams.
          </p>
        </div>

        <div className="p-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {Object.keys(TICKETING_PROVIDERS).map((provider) => (
              <ProviderCard
                key={provider}
                provider={provider}
                isSelected={config.provider === provider}
                onSelect={handleProviderSelect}
                disabled={saving}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Configuration Form */}
      {config.provider && (
        <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-6">
          <ConfigurationForm
            provider={config.provider}
            config={config.config || {}}
            onChange={handleConfigChange}
            onTest={handleTestConnection}
            testing={testing}
            isLoading={saving}
          />
        </div>
      )}

      {/* Action Buttons */}
      {hasChanges && (
        <div className="flex justify-end gap-3">
          <button
            onClick={() => {
              loadConfig();
              setHasChanges(false);
            }}
            disabled={saving}
            className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !connectionStatus}
            className="px-4 py-2 text-sm font-medium bg-aura-600 text-white rounded-lg hover:bg-aura-700 disabled:opacity-50 transition-colors"
          >
            {saving ? 'Saving...' : 'Save Configuration'}
          </button>
        </div>
      )}

      {/* Disable Integration */}
      {config.enabled && !hasChanges && (
        <div className="flex justify-end">
          <button
            onClick={handleDisable}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-critical-600 dark:text-critical-400 hover:bg-critical-50 dark:hover:bg-critical-900/20 rounded-lg transition-colors"
          >
            <TrashIcon className="h-4 w-4" />
            Disable Integration
          </button>
        </div>
      )}
    </div>
  );
}
