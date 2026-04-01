/**
 * Project Aura - Environment Admin Settings Component
 *
 * Admin section for managing environment templates, quotas, and defaults.
 */

import { useState, useEffect } from 'react';
import {
  ServerStackIcon,
  PlusIcon,
  PencilSquareIcon,
  TrashIcon,
  CurrencyDollarIcon,
  ClockIcon,
  UserGroupIcon,
  Cog6ToothIcon,
  ArrowPathIcon,
  InformationCircleIcon,
  ShieldCheckIcon,
  DocumentDuplicateIcon,
  ChevronDownIcon,
  ChevronUpIcon,
} from '@heroicons/react/24/outline';

import {
  getEnvironmentTemplates,
  createEnvironmentTemplate,
  updateEnvironmentTemplate,
  deleteEnvironmentTemplate,
  getQuotaConfig,
  updateQuotaConfig,
  getDefaultSettings,
  updateDefaultSettings,
  ENVIRONMENT_TYPE_CONFIG,
  ISOLATION_LEVEL_CONFIG,
  DEFAULT_ADMIN_SETTINGS,
} from '../../services/environmentsApi';

import EditTemplateModal from './EditTemplateModal';

/**
 * Template Card Component
 */
function TemplateCard({ template, onEdit, onDelete, isLoading }) {
  const typeConfig = ENVIRONMENT_TYPE_CONFIG[template.environment_type] || ENVIRONMENT_TYPE_CONFIG.standard;

  return (
    <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 p-4 shadow-[var(--shadow-glass)] transition-all duration-200 ease-[var(--ease-tahoe)] hover:shadow-[var(--shadow-glass-hover)]">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg bg-${typeConfig.color}-100 dark:bg-${typeConfig.color}-900/30`}>
            <DocumentDuplicateIcon className={`h-5 w-5 text-${typeConfig.color}-600 dark:text-${typeConfig.color}-400`} />
          </div>
          <div>
            <h4 className="font-medium text-surface-900 dark:text-surface-100">
              {template.name}
            </h4>
            <span className={`text-xs px-2 py-0.5 rounded-full bg-${typeConfig.color}-100 text-${typeConfig.color}-700 dark:bg-${typeConfig.color}-900/30 dark:text-${typeConfig.color}-400`}>
              {typeConfig.label}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => onEdit(template)}
            disabled={isLoading}
            className="p-1.5 text-surface-400 hover:text-aura-600 dark:hover:text-aura-400 transition-colors"
          >
            <PencilSquareIcon className="h-4 w-4" />
          </button>
          <button
            onClick={() => onDelete(template)}
            disabled={isLoading}
            className="p-1.5 text-surface-400 hover:text-critical-600 dark:hover:text-critical-400 transition-colors"
          >
            <TrashIcon className="h-4 w-4" />
          </button>
        </div>
      </div>

      <p className="text-sm text-surface-500 dark:text-surface-400 mb-3">
        {template.description}
      </p>

      <div className="flex items-center gap-4 text-xs text-surface-500 dark:text-surface-400">
        <span className="flex items-center gap-1">
          <ClockIcon className="h-3.5 w-3.5" />
          {template.default_ttl_hours}h default
        </span>
        <span className="flex items-center gap-1">
          <CurrencyDollarIcon className="h-3.5 w-3.5" />
          ${template.cost_per_day?.toFixed(2) || '0.00'}/day
        </span>
        {template.requires_approval && (
          <span className="flex items-center gap-1 text-warning-600 dark:text-warning-400">
            <ShieldCheckIcon className="h-3.5 w-3.5" />
            HITL Required
          </span>
        )}
      </div>
    </div>
  );
}

/**
 * Quota Configuration Panel
 */
function QuotaConfigPanel({ quota, onUpdate, isLoading }) {
  const [localQuota, setLocalQuota] = useState(quota);
  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    setLocalQuota(quota);
    setHasChanges(false);
  }, [quota]);

  const handleChange = (field, value) => {
    setLocalQuota(prev => ({ ...prev, [field]: value }));
    setHasChanges(true);
  };

  const handleSave = () => {
    onUpdate(localQuota);
    setHasChanges(false);
  };

  return (
    <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)]">
      <div className="p-4 border-b border-surface-100/50 dark:border-surface-700/30">
        <div className="flex items-center gap-2">
          <UserGroupIcon className="h-5 w-5 text-aura-600 dark:text-aura-400" />
          <h3 className="font-semibold text-surface-900 dark:text-surface-100">
            User Quota Configuration
          </h3>
        </div>
      </div>

      <div className="p-4 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
              Default Concurrent Limit
            </label>
            <input
              type="number"
              min={1}
              max={20}
              value={localQuota.default_concurrent_limit || 3}
              onChange={(e) => handleChange('default_concurrent_limit', parseInt(e.target.value))}
              disabled={isLoading}
              className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent disabled:opacity-50"
            />
            <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
              Max concurrent environments per user
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
              Default Monthly Budget ($)
            </label>
            <input
              type="number"
              min={0}
              max={10000}
              step={50}
              value={localQuota.default_monthly_budget || 500}
              onChange={(e) => handleChange('default_monthly_budget', parseFloat(e.target.value))}
              disabled={isLoading}
              className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent disabled:opacity-50"
            />
          </div>
        </div>

        <div className="flex items-center justify-between py-2">
          <div>
            <p className="font-medium text-surface-900 dark:text-surface-100">Allow Extended TTL</p>
            <p className="text-sm text-surface-500 dark:text-surface-400">
              Allow users to create extended (7+ day) environments
            </p>
          </div>
          <button
            type="button"
            onClick={() => handleChange('allow_extended_ttl', !localQuota.allow_extended_ttl)}
            disabled={isLoading}
            className={`
              relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent
              transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-aura-500
              ${localQuota.allow_extended_ttl ? 'bg-olive-600' : 'bg-surface-200 dark:bg-surface-600'}
              ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}
            `}
          >
            <span
              className={`
                pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0
                transition duration-200 ease-in-out
                ${localQuota.allow_extended_ttl ? 'translate-x-5' : 'translate-x-0'}
              `}
            />
          </button>
        </div>

        <div className="flex items-center justify-between py-2">
          <div>
            <p className="font-medium text-surface-900 dark:text-surface-100">Require Approval for Extended</p>
            <p className="text-sm text-surface-500 dark:text-surface-400">
              Require HITL approval for extended environments
            </p>
          </div>
          <button
            type="button"
            onClick={() => handleChange('require_approval_for_extended', !localQuota.require_approval_for_extended)}
            disabled={isLoading}
            className={`
              relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent
              transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-aura-500
              ${localQuota.require_approval_for_extended ? 'bg-olive-600' : 'bg-surface-200 dark:bg-surface-600'}
              ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}
            `}
          >
            <span
              className={`
                pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0
                transition duration-200 ease-in-out
                ${localQuota.require_approval_for_extended ? 'translate-x-5' : 'translate-x-0'}
              `}
            />
          </button>
        </div>
      </div>

      {hasChanges && (
        <div className="p-4 border-t border-surface-100/50 dark:border-surface-700/30 bg-white/60 dark:bg-surface-800/50 backdrop-blur-sm flex justify-end gap-3">
          <button
            onClick={() => {
              setLocalQuota(quota);
              setHasChanges(false);
            }}
            disabled={isLoading}
            className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-surface-50 dark:hover:bg-surface-700 rounded-xl transition-all duration-200 ease-[var(--ease-tahoe)]"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={isLoading}
            className="px-4 py-2 text-sm font-medium bg-aura-600 text-white rounded-xl hover:bg-aura-700 shadow-[var(--shadow-glass)] hover:shadow-[var(--shadow-glass-hover)] disabled:opacity-50 transition-all duration-200 ease-[var(--ease-tahoe)]"
          >
            Save Quota Settings
          </button>
        </div>
      )}
    </div>
  );
}

/**
 * Default Settings Panel
 */
function DefaultSettingsPanel({ settings, onUpdate, isLoading }) {
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
      <div className="p-4 border-b border-surface-100/50 dark:border-surface-700/30">
        <div className="flex items-center gap-2">
          <Cog6ToothIcon className="h-5 w-5 text-aura-600 dark:text-aura-400" />
          <h3 className="font-semibold text-surface-900 dark:text-surface-100">
            Default Environment Settings
          </h3>
        </div>
      </div>

      <div className="p-4 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
              Default TTL (hours)
            </label>
            <input
              type="number"
              min={1}
              max={168}
              value={localSettings.default_ttl_hours || 24}
              onChange={(e) => handleChange('default_ttl_hours', parseInt(e.target.value))}
              disabled={isLoading}
              className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent disabled:opacity-50"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
              Max TTL (hours)
            </label>
            <input
              type="number"
              min={1}
              max={720}
              value={localSettings.max_ttl_hours || 168}
              onChange={(e) => handleChange('max_ttl_hours', parseInt(e.target.value))}
              disabled={isLoading}
              className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent disabled:opacity-50"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
            Default Isolation Level
          </label>
          <select
            value={localSettings.default_isolation_level || 'namespace'}
            onChange={(e) => handleChange('default_isolation_level', e.target.value)}
            disabled={isLoading}
            className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent disabled:opacity-50"
          >
            {Object.entries(ISOLATION_LEVEL_CONFIG).map(([key, config]) => (
              <option key={key} value={key}>
                {config.label} - {config.description}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center justify-between py-2">
          <div>
            <p className="font-medium text-surface-900 dark:text-surface-100">Auto-terminate on Inactivity</p>
            <p className="text-sm text-surface-500 dark:text-surface-400">
              Automatically terminate environments after inactivity period
            </p>
          </div>
          <button
            type="button"
            onClick={() => handleChange('auto_terminate_on_inactivity', !localSettings.auto_terminate_on_inactivity)}
            disabled={isLoading}
            className={`
              relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent
              transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-aura-500
              ${localSettings.auto_terminate_on_inactivity ? 'bg-olive-600' : 'bg-surface-200 dark:bg-surface-600'}
              ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}
            `}
          >
            <span
              className={`
                pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0
                transition duration-200 ease-in-out
                ${localSettings.auto_terminate_on_inactivity ? 'translate-x-5' : 'translate-x-0'}
              `}
            />
          </button>
        </div>

        {localSettings.auto_terminate_on_inactivity && (
          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
              Inactivity Timeout (hours)
            </label>
            <input
              type="number"
              min={1}
              max={24}
              value={localSettings.inactivity_timeout_hours || 4}
              onChange={(e) => handleChange('inactivity_timeout_hours', parseInt(e.target.value))}
              disabled={isLoading}
              className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent disabled:opacity-50"
            />
          </div>
        )}
      </div>

      {hasChanges && (
        <div className="p-4 border-t border-surface-100/50 dark:border-surface-700/30 bg-white/60 dark:bg-surface-800/50 backdrop-blur-sm flex justify-end gap-3">
          <button
            onClick={() => {
              setLocalSettings(settings);
              setHasChanges(false);
            }}
            disabled={isLoading}
            className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-surface-50 dark:hover:bg-surface-700 rounded-xl transition-all duration-200 ease-[var(--ease-tahoe)]"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={isLoading}
            className="px-4 py-2 text-sm font-medium bg-aura-600 text-white rounded-xl hover:bg-aura-700 shadow-[var(--shadow-glass)] hover:shadow-[var(--shadow-glass-hover)] disabled:opacity-50 transition-all duration-200 ease-[var(--ease-tahoe)]"
          >
            Save Default Settings
          </button>
        </div>
      )}
    </div>
  );
}

/**
 * Main Environment Admin Settings Component
 */
export default function EnvironmentAdminSettings({ onSuccess, onError }) {
  const [templates, setTemplates] = useState([]);
  const [quota, setQuota] = useState(DEFAULT_ADMIN_SETTINGS.quotas);
  const [defaults, setDefaults] = useState(DEFAULT_ADMIN_SETTINGS.defaults);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [expandedSection, setExpandedSection] = useState('templates');

  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [isCreating, setIsCreating] = useState(false);

  // Load environment data on mount only (loadData defined below)
  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [templatesData, quotaData, defaultsData] = await Promise.all([
        getEnvironmentTemplates(),
        getQuotaConfig(),
        getDefaultSettings(),
      ]);
      setTemplates(templatesData);
      setQuota(quotaData);
      setDefaults(defaultsData);
    } catch (err) {
      onError?.(`Failed to load environment settings: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleQuotaUpdate = async (updatedQuota) => {
    setSaving(true);
    try {
      await updateQuotaConfig(updatedQuota);
      setQuota(updatedQuota);
      onSuccess?.('Quota configuration updated');
    } catch (err) {
      onError?.(`Failed to update quota: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleDefaultsUpdate = async (updatedDefaults) => {
    setSaving(true);
    try {
      await updateDefaultSettings(updatedDefaults);
      setDefaults(updatedDefaults);
      onSuccess?.('Default settings updated');
    } catch (err) {
      onError?.(`Failed to update defaults: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteTemplate = async (template) => {
    if (!confirm(`Are you sure you want to delete the "${template.name}" template?`)) {
      return;
    }

    setSaving(true);
    try {
      await deleteEnvironmentTemplate(template.template_id);
      setTemplates(prev => prev.filter(t => t.template_id !== template.template_id));
      onSuccess?.('Template deleted');
    } catch (err) {
      onError?.(`Failed to delete template: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  // Open modal for editing an existing template
  const handleEditTemplate = (template) => {
    setEditingTemplate(template);
    setIsCreating(false);
    setIsModalOpen(true);
  };

  // Open modal for creating a new template
  const handleCreateTemplate = () => {
    setEditingTemplate(null);
    setIsCreating(true);
    setIsModalOpen(true);
  };

  // Close modal
  const handleCloseModal = () => {
    setIsModalOpen(false);
    setEditingTemplate(null);
    setIsCreating(false);
  };

  // Save template (create or update)
  const handleSaveTemplate = async (templateData) => {
    setSaving(true);
    try {
      if (isCreating) {
        // Create new template
        const newTemplate = await createEnvironmentTemplate(templateData);
        setTemplates(prev => [...prev, newTemplate]);
        onSuccess?.('Template created successfully');
      } else if (editingTemplate) {
        // Update existing template
        const updatedTemplate = await updateEnvironmentTemplate(
          editingTemplate.template_id,
          templateData
        );
        setTemplates(prev =>
          prev.map(t =>
            t.template_id === editingTemplate.template_id ? updatedTemplate : t
          )
        );
        onSuccess?.('Template updated successfully');
      }
      handleCloseModal();
    } catch (err) {
      onError?.(`Failed to save template: ${err.message}`);
      throw err; // Re-throw to let modal handle error state
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <ArrowPathIcon className="h-8 w-8 text-aura-500 animate-spin" />
        <span className="ml-3 text-surface-600 dark:text-surface-400">
          Loading environment settings...
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Info Banner */}
      <div className="flex items-start gap-3 p-4 bg-aura-50/80 dark:bg-aura-900/20 backdrop-blur-sm border border-aura-200/50 dark:border-aura-800/50 rounded-xl shadow-[var(--shadow-glass)]">
        <InformationCircleIcon className="h-5 w-5 text-aura-600 dark:text-aura-400 flex-shrink-0 mt-0.5" />
        <div>
          <h4 className="font-medium text-aura-800 dark:text-aura-200">Environment Administration</h4>
          <p className="text-sm text-aura-700 dark:text-aura-300 mt-1">
            Configure templates, quotas, and default settings for self-service test environments.
            These settings apply to all users unless overridden.
          </p>
        </div>
      </div>

      {/* Templates Section */}
      <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)]">
        <button
          onClick={() => setExpandedSection(expandedSection === 'templates' ? '' : 'templates')}
          className="w-full p-4 flex items-center justify-between hover:bg-surface-50 dark:hover:bg-surface-700 transition-all duration-200 ease-[var(--ease-tahoe)]"
        >
          <div className="flex items-center gap-2">
            <DocumentDuplicateIcon className="h-5 w-5 text-aura-600 dark:text-aura-400" />
            <h3 className="font-semibold text-surface-900 dark:text-surface-100">
              Environment Templates
            </h3>
            <span className="px-2 py-0.5 bg-surface-100 dark:bg-surface-700 rounded text-xs text-surface-600 dark:text-surface-400">
              {templates.length} templates
            </span>
          </div>
          {expandedSection === 'templates' ? (
            <ChevronUpIcon className="h-5 w-5 text-surface-400" />
          ) : (
            <ChevronDownIcon className="h-5 w-5 text-surface-400" />
          )}
        </button>

        {expandedSection === 'templates' && (
          <div className="p-4 border-t border-surface-100/50 dark:border-surface-700/30">
            {templates.length === 0 ? (
              <div className="text-center py-8">
                <ServerStackIcon className="h-12 w-12 text-surface-300 dark:text-surface-600 mx-auto mb-3" />
                <p className="text-surface-600 dark:text-surface-400">No templates configured</p>
                <button
                  onClick={handleCreateTemplate}
                  className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-aura-600 text-white rounded-xl hover:bg-aura-700 shadow-[var(--shadow-glass)] hover:shadow-[var(--shadow-glass-hover)] transition-all duration-200 ease-[var(--ease-tahoe)] text-sm font-medium"
                >
                  <PlusIcon className="h-4 w-4" />
                  Create Template
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex justify-end">
                  <button
                    onClick={handleCreateTemplate}
                    className="inline-flex items-center gap-2 px-4 py-2 bg-aura-600 text-white rounded-xl hover:bg-aura-700 shadow-[var(--shadow-glass)] hover:shadow-[var(--shadow-glass-hover)] transition-all duration-200 ease-[var(--ease-tahoe)] text-sm font-medium"
                  >
                    <PlusIcon className="h-4 w-4" />
                    Create Template
                  </button>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {templates.map((template) => (
                    <TemplateCard
                      key={template.template_id}
                      template={template}
                      onEdit={handleEditTemplate}
                      onDelete={handleDeleteTemplate}
                      isLoading={saving}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Quota Configuration */}
      <QuotaConfigPanel
        quota={quota}
        onUpdate={handleQuotaUpdate}
        isLoading={saving}
      />

      {/* Default Settings */}
      <DefaultSettingsPanel
        settings={defaults}
        onUpdate={handleDefaultsUpdate}
        isLoading={saving}
      />

      {/* Edit/Create Template Modal */}
      <EditTemplateModal
        isOpen={isModalOpen}
        template={editingTemplate}
        onClose={handleCloseModal}
        onSave={handleSaveTemplate}
        isCreating={isCreating}
      />
    </div>
  );
}
