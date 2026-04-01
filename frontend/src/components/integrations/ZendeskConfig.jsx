/**
 * Project Aura - Zendesk Integration Configuration Modal
 *
 * Configuration interface for Zendesk ticketing integration with
 * API key authentication, ticket mapping, and priority configuration.
 */

import { useState, useEffect } from 'react';
import {
  XMarkIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ArrowPathIcon,
  EyeIcon,
  EyeSlashIcon,
  LinkIcon,
  InformationCircleIcon,
  TicketIcon,
  ArrowTopRightOnSquareIcon,
} from '@heroicons/react/24/outline';
import { useIntegrationConfig } from '../../hooks/useIntegrations';

// Priority mapping options
const ZENDESK_PRIORITIES = [
  { value: 'urgent', label: 'Urgent', color: 'bg-critical-500' },
  { value: 'high', label: 'High', color: 'bg-warning-500' },
  { value: 'normal', label: 'Normal', color: 'bg-aura-500' },
  { value: 'low', label: 'Low', color: 'bg-surface-400' },
];

const AURA_SEVERITIES = [
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
];

export default function ZendeskConfig({ isOpen, onClose, onSave, existingConfig }) {
  const {
    config,
    loading,
    saving,
    testing,
    testResult,
    validationErrors,
    providerDef: _providerDef,
    updateField,
    testConnection,
    saveConfig,
  } = useIntegrationConfig('zendesk');

  const [showSecrets, setShowSecrets] = useState({});
  const [priorityMapping, setPriorityMapping] = useState({
    critical: 'urgent',
    high: 'high',
    medium: 'normal',
    low: 'low',
  });
  const [autoCreateTickets, setAutoCreateTickets] = useState(true);
  const [syncComments, setSyncComments] = useState(true);

  // Initialize with existing config
  useEffect(() => {
    if (existingConfig) {
      Object.entries(existingConfig).forEach(([key, value]) => {
        updateField(key, value);
      });
      if (existingConfig.priority_mapping) {
        setPriorityMapping(existingConfig.priority_mapping);
      }
      if (existingConfig.auto_create_tickets !== undefined) {
        setAutoCreateTickets(existingConfig.auto_create_tickets);
      }
      if (existingConfig.sync_comments !== undefined) {
        setSyncComments(existingConfig.sync_comments);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [existingConfig]);

  const toggleSecret = (fieldName) => {
    setShowSecrets((prev) => ({ ...prev, [fieldName]: !prev[fieldName] }));
  };

  const handlePriorityChange = (auraSeverity, zendeskPriority) => {
    setPriorityMapping((prev) => ({ ...prev, [auraSeverity]: zendeskPriority }));
  };

  const handleSave = async () => {
    try {
      const fullConfig = {
        ...config,
        priority_mapping: priorityMapping,
        auto_create_tickets: autoCreateTickets,
        sync_comments: syncComments,
      };
      await saveConfig(fullConfig);
      onSave?.(fullConfig);
      onClose();
    } catch (err) {
      // Error handled by hook
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-white dark:bg-surface-800 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-surface-200 dark:border-surface-700 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-100 dark:bg-emerald-900/30 rounded-xl">
              <TicketIcon className="h-6 w-6 text-emerald-600 dark:text-emerald-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-surface-900 dark:text-surface-100">
                Configure Zendesk
              </h2>
              <p className="text-sm text-surface-500 dark:text-surface-400">
                Enterprise customer service platform
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
          >
            <XMarkIcon className="h-5 w-5 text-surface-500 dark:text-surface-400" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6 space-y-6">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <ArrowPathIcon className="h-8 w-8 text-aura-500 animate-spin" />
            </div>
          ) : (
            <>
              {/* Connection Settings */}
              <section>
                <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                  Connection Settings
                </h3>

                <div className="space-y-4">
                  {/* Subdomain */}
                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      Subdomain <span className="text-critical-500">*</span>
                    </label>
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        value={config.subdomain || ''}
                        onChange={(e) => updateField('subdomain', e.target.value)}
                        placeholder="yourcompany"
                        className={`flex-1 px-3 py-2 border rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 ${
                          validationErrors.subdomain
                            ? 'border-critical-300 dark:border-critical-700'
                            : 'border-surface-300 dark:border-surface-600'
                        }`}
                      />
                      <span className="text-surface-500 dark:text-surface-400">.zendesk.com</span>
                    </div>
                    {validationErrors.subdomain && (
                      <p className="text-xs text-critical-600 dark:text-critical-400 mt-1">
                        {validationErrors.subdomain}
                      </p>
                    )}
                  </div>

                  {/* Agent Email */}
                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      Agent Email <span className="text-critical-500">*</span>
                    </label>
                    <input
                      type="email"
                      value={config.email || ''}
                      onChange={(e) => updateField('email', e.target.value)}
                      placeholder="agent@company.com"
                      className={`w-full px-3 py-2 border rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 ${
                        validationErrors.email
                          ? 'border-critical-300 dark:border-critical-700'
                          : 'border-surface-300 dark:border-surface-600'
                      }`}
                    />
                    {validationErrors.email && (
                      <p className="text-xs text-critical-600 dark:text-critical-400 mt-1">
                        {validationErrors.email}
                      </p>
                    )}
                    <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                      Email address of the API user
                    </p>
                  </div>

                  {/* API Token */}
                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      API Token <span className="text-critical-500">*</span>
                    </label>
                    <div className="relative">
                      <input
                        type={showSecrets.api_token ? 'text' : 'password'}
                        value={config.api_token || ''}
                        onChange={(e) => updateField('api_token', e.target.value)}
                        placeholder="Enter your Zendesk API token"
                        className={`w-full px-3 py-2 pr-10 border rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 ${
                          validationErrors.api_token
                            ? 'border-critical-300 dark:border-critical-700'
                            : 'border-surface-300 dark:border-surface-600'
                        }`}
                      />
                      <button
                        type="button"
                        onClick={() => toggleSecret('api_token')}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300"
                      >
                        {showSecrets.api_token ? (
                          <EyeSlashIcon className="h-5 w-5" />
                        ) : (
                          <EyeIcon className="h-5 w-5" />
                        )}
                      </button>
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <p className="text-xs text-surface-500 dark:text-surface-400">
                        Generate from Admin Center &gt; Channels &gt; API
                      </p>
                      <a
                        href="https://support.zendesk.com/hc/en-us/articles/4408889192858"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-aura-600 dark:text-aura-400 hover:underline"
                      >
                        Learn more
                        <ArrowTopRightOnSquareIcon className="h-3 w-3" />
                      </a>
                    </div>
                  </div>
                </div>
              </section>

              {/* Default Assignment */}
              <section>
                <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                  Default Assignment
                </h3>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      Default Assignee ID
                    </label>
                    <input
                      type="text"
                      value={config.default_assignee_id || ''}
                      onChange={(e) => updateField('default_assignee_id', e.target.value)}
                      placeholder="User ID"
                      className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500"
                    />
                    <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                      Optional: User ID to assign tickets
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      Default Group ID
                    </label>
                    <input
                      type="text"
                      value={config.default_group_id || ''}
                      onChange={(e) => updateField('default_group_id', e.target.value)}
                      placeholder="Group ID"
                      className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500"
                    />
                    <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                      Optional: Group for ticket routing
                    </p>
                  </div>
                </div>
              </section>

              {/* Priority Mapping */}
              <section>
                <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                  Priority Mapping
                </h3>

                <div className="bg-surface-50 dark:bg-surface-700/50 rounded-lg p-4">
                  <p className="text-sm text-surface-600 dark:text-surface-400 mb-4">
                    Map Aura severity levels to Zendesk ticket priorities
                  </p>

                  <div className="space-y-3">
                    {AURA_SEVERITIES.map((severity) => (
                      <div key={severity.value} className="flex items-center justify-between">
                        <span className="text-sm font-medium text-surface-900 dark:text-surface-100">
                          {severity.label}
                        </span>
                        <div className="flex items-center gap-2">
                          <span className="text-surface-400">-&gt;</span>
                          <select
                            value={priorityMapping[severity.value] || 'normal'}
                            onChange={(e) => handlePriorityChange(severity.value, e.target.value)}
                            className="px-3 py-1.5 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 text-sm focus:ring-2 focus:ring-aura-500"
                          >
                            {ZENDESK_PRIORITIES.map((priority) => (
                              <option key={priority.value} value={priority.value}>
                                {priority.label}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </section>

              {/* Sync Settings */}
              <section>
                <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                  Sync Settings
                </h3>

                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-surface-900 dark:text-surface-100">
                        Auto-create tickets
                      </p>
                      <p className="text-sm text-surface-500 dark:text-surface-400">
                        Automatically create Zendesk tickets for security alerts
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setAutoCreateTickets(!autoCreateTickets)}
                      className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2 ${
                        autoCreateTickets ? 'bg-aura-600' : 'bg-surface-200 dark:bg-surface-600'
                      }`}
                    >
                      <span
                        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                          autoCreateTickets ? 'translate-x-5' : 'translate-x-0'
                        }`}
                      />
                    </button>
                  </div>

                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-surface-900 dark:text-surface-100">
                        Sync comments
                      </p>
                      <p className="text-sm text-surface-500 dark:text-surface-400">
                        Sync ticket comments bidirectionally
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setSyncComments(!syncComments)}
                      className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2 ${
                        syncComments ? 'bg-aura-600' : 'bg-surface-200 dark:bg-surface-600'
                      }`}
                    >
                      <span
                        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                          syncComments ? 'translate-x-5' : 'translate-x-0'
                        }`}
                      />
                    </button>
                  </div>
                </div>
              </section>

              {/* Connection Test */}
              <section>
                <div className="bg-surface-50 dark:bg-surface-700/50 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="font-medium text-surface-900 dark:text-surface-100">
                      Test Connection
                    </h3>
                    <button
                      onClick={testConnection}
                      disabled={testing || !config.subdomain || !config.email || !config.api_token}
                      className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-aura-600 text-white rounded-lg hover:bg-aura-700 disabled:bg-surface-400 dark:disabled:bg-surface-600 disabled:cursor-not-allowed transition-colors"
                    >
                      {testing ? (
                        <>
                          <ArrowPathIcon className="h-4 w-4 animate-spin" />
                          Testing...
                        </>
                      ) : (
                        <>
                          <LinkIcon className="h-4 w-4" />
                          Test
                        </>
                      )}
                    </button>
                  </div>

                  {testResult && (
                    <div
                      className={`flex items-center gap-3 p-3 rounded-lg ${
                        testResult.success
                          ? 'bg-olive-50 dark:bg-olive-900/20 text-olive-700 dark:text-olive-300'
                          : 'bg-critical-50 dark:bg-critical-900/20 text-critical-700 dark:text-critical-300'
                      }`}
                    >
                      {testResult.success ? (
                        <CheckCircleIcon className="h-5 w-5 text-olive-600 dark:text-olive-400" />
                      ) : (
                        <ExclamationCircleIcon className="h-5 w-5 text-critical-600 dark:text-critical-400" />
                      )}
                      <div>
                        <p className="font-medium">{testResult.message}</p>
                        {testResult.latency_ms && (
                          <p className="text-xs opacity-75">Latency: {testResult.latency_ms}ms</p>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </section>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-surface-200 dark:border-surface-700 flex items-center justify-between bg-surface-50 dark:bg-surface-800">
          <div className="flex items-center gap-2 text-sm text-surface-500 dark:text-surface-400">
            <InformationCircleIcon className="h-4 w-4" />
            <span>Credentials are encrypted at rest</span>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !testResult?.success}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-aura-600 text-white rounded-lg hover:bg-aura-700 disabled:bg-surface-400 dark:disabled:bg-surface-600 disabled:cursor-not-allowed transition-colors"
            >
              {saving ? (
                <>
                  <ArrowPathIcon className="h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <CheckCircleIcon className="h-4 w-4" />
                  Save Configuration
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
