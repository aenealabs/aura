/**
 * Project Aura - ServiceNow Integration Configuration Modal
 *
 * Configuration interface for ServiceNow ITSM integration with
 * basic authentication, table mappings, and incident templates.
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
  BuildingOfficeIcon,
  DocumentDuplicateIcon,
} from '@heroicons/react/24/outline';
import { useIntegrationConfig } from '../../hooks/useIntegrations';

// ServiceNow table options
const SERVICENOW_TABLES = [
  { value: 'incident', label: 'Incident', description: 'IT service incidents' },
  { value: 'sc_request', label: 'Service Request', description: 'Service catalog requests' },
  { value: 'problem', label: 'Problem', description: 'Root cause analysis' },
  { value: 'change_request', label: 'Change Request', description: 'Change management' },
];

// ServiceNow impact/urgency options
const IMPACT_OPTIONS = [
  { value: 1, label: '1 - High' },
  { value: 2, label: '2 - Medium' },
  { value: 3, label: '3 - Low' },
];

const URGENCY_OPTIONS = [
  { value: 1, label: '1 - High' },
  { value: 2, label: '2 - Medium' },
  { value: 3, label: '3 - Low' },
];

const AURA_SEVERITIES = [
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
];

// Default incident templates
const DEFAULT_TEMPLATES = {
  security_vulnerability: {
    name: 'Security Vulnerability',
    short_description: '[Aura] Security Vulnerability: {title}',
    description: 'A security vulnerability has been detected by Project Aura.\n\nDetails:\n{description}\n\nSeverity: {severity}\nCVE: {cve_id}',
    category: 'Security',
    subcategory: 'Vulnerability',
  },
  patch_approval: {
    name: 'Patch Approval Request',
    short_description: '[Aura] Patch Approval Required: {title}',
    description: 'A security patch requires approval before deployment.\n\nPatch Details:\n{description}\n\nAffected Systems: {affected_systems}',
    category: 'Software',
    subcategory: 'Patch',
  },
  security_alert: {
    name: 'Security Alert',
    short_description: '[Aura] Security Alert: {title}',
    description: 'A security alert has been triggered.\n\nAlert Details:\n{description}\n\nRisk Level: {risk_level}',
    category: 'Security',
    subcategory: 'Alert',
  },
};

export default function ServiceNowConfig({ isOpen, onClose, onSave, existingConfig }) {
  const {
    config,
    loading,
    saving,
    testing,
    testResult,
    validationErrors,
    updateField,
    testConnection,
    saveConfig,
  } = useIntegrationConfig('servicenow');

  const [showPassword, setShowPassword] = useState(false);
  const [impactMapping, setImpactMapping] = useState({
    critical: 1,
    high: 1,
    medium: 2,
    low: 3,
  });
  const [urgencyMapping, setUrgencyMapping] = useState({
    critical: 1,
    high: 2,
    medium: 2,
    low: 3,
  });
  const [templates, setTemplates] = useState(DEFAULT_TEMPLATES);
  const [selectedTemplate, setSelectedTemplate] = useState('security_vulnerability');
  const [autoResolve, setAutoResolve] = useState(true);
  const [syncNotes, setSyncNotes] = useState(true);

  // Initialize with existing config
  useEffect(() => {
    if (existingConfig) {
      Object.entries(existingConfig).forEach(([key, value]) => {
        updateField(key, value);
      });
      if (existingConfig.impact_mapping) {
        setImpactMapping(existingConfig.impact_mapping);
      }
      if (existingConfig.urgency_mapping) {
        setUrgencyMapping(existingConfig.urgency_mapping);
      }
      if (existingConfig.templates) {
        setTemplates(existingConfig.templates);
      }
      if (existingConfig.auto_resolve !== undefined) {
        setAutoResolve(existingConfig.auto_resolve);
      }
      if (existingConfig.sync_notes !== undefined) {
        setSyncNotes(existingConfig.sync_notes);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [existingConfig]);

  const handleImpactChange = (auraSeverity, impact) => {
    setImpactMapping((prev) => ({ ...prev, [auraSeverity]: parseInt(impact, 10) }));
  };

  const handleUrgencyChange = (auraSeverity, urgency) => {
    setUrgencyMapping((prev) => ({ ...prev, [auraSeverity]: parseInt(urgency, 10) }));
  };

  const handleTemplateChange = (templateKey, field, value) => {
    setTemplates((prev) => ({
      ...prev,
      [templateKey]: {
        ...prev[templateKey],
        [field]: value,
      },
    }));
  };

  const handleSave = async () => {
    try {
      const fullConfig = {
        ...config,
        impact_mapping: impactMapping,
        urgency_mapping: urgencyMapping,
        templates,
        auto_resolve: autoResolve,
        sync_notes: syncNotes,
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
      <div className="bg-white dark:bg-surface-800 rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-surface-200 dark:border-surface-700 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-olive-100 dark:bg-olive-900/30 rounded-xl">
              <BuildingOfficeIcon className="h-6 w-6 text-olive-600 dark:text-olive-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-surface-900 dark:text-surface-100">
                Configure ServiceNow
              </h2>
              <p className="text-sm text-surface-500 dark:text-surface-400">
                Enterprise IT service management platform
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
              {/* Instance Configuration */}
              <section>
                <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                  Instance Configuration
                </h3>

                <div className="space-y-4">
                  {/* Instance URL */}
                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      Instance URL <span className="text-critical-500">*</span>
                    </label>
                    <input
                      type="url"
                      value={config.instance_url || ''}
                      onChange={(e) => updateField('instance_url', e.target.value)}
                      placeholder="https://dev12345.service-now.com"
                      className={`w-full px-3 py-2 border rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 ${
                        validationErrors.instance_url
                          ? 'border-critical-300 dark:border-critical-700'
                          : 'border-surface-300 dark:border-surface-600'
                      }`}
                    />
                    {validationErrors.instance_url && (
                      <p className="text-xs text-critical-600 dark:text-critical-400 mt-1">
                        {validationErrors.instance_url}
                      </p>
                    )}
                    <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                      Your ServiceNow instance URL
                    </p>
                  </div>

                  {/* Credentials */}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                        Username <span className="text-critical-500">*</span>
                      </label>
                      <input
                        type="text"
                        value={config.username || ''}
                        onChange={(e) => updateField('username', e.target.value)}
                        placeholder="service_account"
                        className={`w-full px-3 py-2 border rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 ${
                          validationErrors.username
                            ? 'border-critical-300 dark:border-critical-700'
                            : 'border-surface-300 dark:border-surface-600'
                        }`}
                      />
                      {validationErrors.username && (
                        <p className="text-xs text-critical-600 dark:text-critical-400 mt-1">
                          {validationErrors.username}
                        </p>
                      )}
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                        Password <span className="text-critical-500">*</span>
                      </label>
                      <div className="relative">
                        <input
                          type={showPassword ? 'text' : 'password'}
                          value={config.password || ''}
                          onChange={(e) => updateField('password', e.target.value)}
                          placeholder="Enter password"
                          className={`w-full px-3 py-2 pr-10 border rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 ${
                            validationErrors.password
                              ? 'border-critical-300 dark:border-critical-700'
                              : 'border-surface-300 dark:border-surface-600'
                          }`}
                        />
                        <button
                          type="button"
                          onClick={() => setShowPassword(!showPassword)}
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300"
                        >
                          {showPassword ? (
                            <EyeSlashIcon className="h-5 w-5" />
                          ) : (
                            <EyeIcon className="h-5 w-5" />
                          )}
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Default Table */}
                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      Default Table <span className="text-critical-500">*</span>
                    </label>
                    <div className="grid grid-cols-2 gap-3">
                      {SERVICENOW_TABLES.map((table) => (
                        <button
                          key={table.value}
                          type="button"
                          onClick={() => updateField('table', table.value)}
                          className={`p-3 rounded-lg border-2 text-left transition-all ${
                            config.table === table.value
                              ? 'border-olive-500 bg-olive-50 dark:bg-olive-900/20'
                              : 'border-surface-200 dark:border-surface-700 hover:border-surface-300 dark:hover:border-surface-600'
                          }`}
                        >
                          <p className="font-medium text-surface-900 dark:text-surface-100">
                            {table.label}
                          </p>
                          <p className="text-xs text-surface-500 dark:text-surface-400">
                            {table.description}
                          </p>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Assignment Group */}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                        Assignment Group
                      </label>
                      <input
                        type="text"
                        value={config.assignment_group || ''}
                        onChange={(e) => updateField('assignment_group', e.target.value)}
                        placeholder="sys_id of group"
                        className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500"
                      />
                      <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                        Optional: sys_id of the assignment group
                      </p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                        Default Category
                      </label>
                      <input
                        type="text"
                        value={config.category || ''}
                        onChange={(e) => updateField('category', e.target.value)}
                        placeholder="e.g., Security"
                        className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500"
                      />
                    </div>
                  </div>
                </div>
              </section>

              {/* Impact & Urgency Mapping */}
              <section>
                <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                  Impact & Urgency Mapping
                </h3>

                <div className="bg-surface-50 dark:bg-surface-700/50 rounded-lg p-4">
                  <p className="text-sm text-surface-600 dark:text-surface-400 mb-4">
                    Map Aura severity levels to ServiceNow impact and urgency values
                  </p>

                  <div className="space-y-3">
                    <div className="grid grid-cols-3 gap-4 text-sm font-medium text-surface-500 dark:text-surface-400 pb-2 border-b border-surface-200 dark:border-surface-600">
                      <span>Aura Severity</span>
                      <span>Impact</span>
                      <span>Urgency</span>
                    </div>

                    {AURA_SEVERITIES.map((severity) => (
                      <div key={severity.value} className="grid grid-cols-3 gap-4 items-center">
                        <span className="text-sm font-medium text-surface-900 dark:text-surface-100">
                          {severity.label}
                        </span>
                        <select
                          value={impactMapping[severity.value] || 2}
                          onChange={(e) => handleImpactChange(severity.value, e.target.value)}
                          className="px-3 py-1.5 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 text-sm focus:ring-2 focus:ring-aura-500"
                        >
                          {IMPACT_OPTIONS.map((opt) => (
                            <option key={opt.value} value={opt.value}>
                              {opt.label}
                            </option>
                          ))}
                        </select>
                        <select
                          value={urgencyMapping[severity.value] || 2}
                          onChange={(e) => handleUrgencyChange(severity.value, e.target.value)}
                          className="px-3 py-1.5 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 text-sm focus:ring-2 focus:ring-aura-500"
                        >
                          {URGENCY_OPTIONS.map((opt) => (
                            <option key={opt.value} value={opt.value}>
                              {opt.label}
                            </option>
                          ))}
                        </select>
                      </div>
                    ))}
                  </div>
                </div>
              </section>

              {/* Incident Templates */}
              <section>
                <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                  Incident Templates
                </h3>

                <div className="bg-surface-50 dark:bg-surface-700/50 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-4">
                    <DocumentDuplicateIcon className="h-5 w-5 text-surface-400" />
                    <p className="text-sm text-surface-600 dark:text-surface-400">
                      Configure templates for different incident types
                    </p>
                  </div>

                  {/* Template Tabs */}
                  <div className="flex gap-2 mb-4 border-b border-surface-200 dark:border-surface-600">
                    {Object.entries(templates).map(([key, template]) => (
                      <button
                        key={key}
                        type="button"
                        onClick={() => setSelectedTemplate(key)}
                        className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                          selectedTemplate === key
                            ? 'border-olive-500 text-olive-600 dark:text-olive-400'
                            : 'border-transparent text-surface-500 dark:text-surface-400 hover:text-surface-700 dark:hover:text-surface-300'
                        }`}
                      >
                        {template.name}
                      </button>
                    ))}
                  </div>

                  {/* Template Editor */}
                  {templates[selectedTemplate] && (
                    <div className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                          Short Description Template
                        </label>
                        <input
                          type="text"
                          value={templates[selectedTemplate].short_description}
                          onChange={(e) =>
                            handleTemplateChange(selectedTemplate, 'short_description', e.target.value)
                          }
                          className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 font-mono text-sm"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                          Description Template
                        </label>
                        <textarea
                          value={templates[selectedTemplate].description}
                          onChange={(e) =>
                            handleTemplateChange(selectedTemplate, 'description', e.target.value)
                          }
                          rows={4}
                          className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 font-mono text-sm resize-y"
                        />
                        <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                          Available placeholders: {'{title}'}, {'{description}'}, {'{severity}'}, {'{cve_id}'}, {'{affected_systems}'}, {'{risk_level}'}
                        </p>
                      </div>

                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                            Category
                          </label>
                          <input
                            type="text"
                            value={templates[selectedTemplate].category}
                            onChange={(e) =>
                              handleTemplateChange(selectedTemplate, 'category', e.target.value)
                            }
                            className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                            Subcategory
                          </label>
                          <input
                            type="text"
                            value={templates[selectedTemplate].subcategory}
                            onChange={(e) =>
                              handleTemplateChange(selectedTemplate, 'subcategory', e.target.value)
                            }
                            className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500"
                          />
                        </div>
                      </div>
                    </div>
                  )}
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
                        Auto-resolve incidents
                      </p>
                      <p className="text-sm text-surface-500 dark:text-surface-400">
                        Automatically resolve incidents when patches are deployed
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setAutoResolve(!autoResolve)}
                      className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2 ${
                        autoResolve ? 'bg-aura-600' : 'bg-surface-200 dark:bg-surface-600'
                      }`}
                    >
                      <span
                        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                          autoResolve ? 'translate-x-5' : 'translate-x-0'
                        }`}
                      />
                    </button>
                  </div>

                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-surface-900 dark:text-surface-100">
                        Sync work notes
                      </p>
                      <p className="text-sm text-surface-500 dark:text-surface-400">
                        Sync work notes and comments bidirectionally
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setSyncNotes(!syncNotes)}
                      className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2 ${
                        syncNotes ? 'bg-aura-600' : 'bg-surface-200 dark:bg-surface-600'
                      }`}
                    >
                      <span
                        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                          syncNotes ? 'translate-x-5' : 'translate-x-0'
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
                      disabled={
                        testing ||
                        !config.instance_url ||
                        !config.username ||
                        !config.password ||
                        !config.table
                      }
                      className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-olive-600 text-white rounded-lg hover:bg-olive-700 disabled:bg-surface-400 dark:disabled:bg-surface-600 disabled:cursor-not-allowed transition-colors"
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
                        {testResult.instance_name && (
                          <p className="text-xs opacity-75">Instance: {testResult.instance_name}</p>
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
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-olive-600 text-white rounded-lg hover:bg-olive-700 disabled:bg-surface-400 dark:disabled:bg-surface-600 disabled:cursor-not-allowed transition-colors"
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
