/**
 * Project Aura - Linear Integration Configuration Modal
 *
 * Configuration interface for Linear issue tracking integration with
 * API key authentication, team selection, and label mapping.
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
  ArrowTopRightOnSquareIcon,
  PlusIcon,
  XCircleIcon,
} from '@heroicons/react/24/outline';
import { useIntegrationConfig } from '../../hooks/useIntegrations';

// Linear priority levels
const LINEAR_PRIORITIES = [
  { value: 0, label: 'No priority', color: 'bg-surface-400' },
  { value: 1, label: 'Urgent', color: 'bg-critical-500' },
  { value: 2, label: 'High', color: 'bg-warning-500' },
  { value: 3, label: 'Medium', color: 'bg-aura-500' },
  { value: 4, label: 'Low', color: 'bg-surface-400' },
];

const AURA_SEVERITIES = [
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
];

// Linear icon component
const LinearIcon = () => (
  <svg className="h-6 w-6" viewBox="0 0 100 100" fill="none">
    <path
      d="M1.22541 61.5228c-.2225-.9485.90748-1.5459 1.59638-.857L39.3342 97.1782c.6889.6889.0915 1.8189-.857 1.5765-16.6971-4.2561-30.0809-17.6398-34.3313-34.3313-.0964-.4025-.1917-.8053-.2855-1.2088zm6.47638 6.4764C18.0096 81.2095 33.7904 89.7359 50 89.7359 72.3903 89.7359 90.4997 71.6264 90.4997 49.2361c0-16.2096-8.5264-31.99044-21.7364-42.29782-.0201-.02008-.0401-.04016-.0601-.06022-.7054-.59438-1.724.05936-1.5179.92436.2061.86498.4133 1.72998.6216 2.59497 4.988 20.72679 9.9959 41.43969 15.0036 62.16629.2215.9171-.1948 1.753-.9833 2.1175-.6925.3199-1.4768.2032-2.0345-.3033L35.8507 29.4295c-.5577-.5065-1.341-.6232-2.0336-.3033-.7884.3645-1.2048 1.2004-.9833 2.1176 5.0077 20.7265 10.0157 41.4394 15.0036 62.1662.2061.865-.1875 1.5188-.8929 1.9132-.0201.0112-.0401.0224-.0601.0336-.7053.3913-1.5716.3257-2.2162-.1681-5.8015-4.4486-10.6948-10.0178-14.3782-16.4035-3.6834-6.3857-6.1568-13.5766-7.2138-21.0668-.4249-3.0146-.6424-6.0627-.6424-9.1328 0-3.0701.2175-6.1183.6424-9.1328 1.0571-7.4903 3.5304-14.6812 7.2138-21.0668C33.9558 10.0178 38.849 4.44857 44.6505 0c-.02.01-.04.02-.06.03-.7053.39131-1.5717.32571-2.2162-.16811C30.2408 7.43181 21.0095 19.7389 17.1314 33.87c-3.878 14.1311-2.3251 29.4094 4.5704 42.1292zm77.1782-5.3343c-.2061-.865.1875-1.5188.8929-1.9132.0201-.0112.0401-.0224.0601-.0336.7053-.3913 1.5716-.3256 2.2162.1682 5.8014 4.4486 10.6947 10.0178 14.3782 16.4035 3.6834 6.3856 6.1567 13.5765 7.2138 21.0668.4248 3.0145.6424 6.0627.6424 9.1327 0 3.0701-.2176 6.1183-.6424 9.1328-1.0571 7.4903-3.5304 14.6812-7.2138 21.0668-3.6835 6.3857-8.5768 11.9549-14.3782 16.4035-.0201.02-.0401.04-.0601.06-.7053.5938-1.724-.0594-1.5179-.9244.2061-.865.4133-1.73.6216-2.595 4.988-20.7268 9.9959-41.4397 15.0036-62.1663.2215-.9171-.1948-1.753-.9833-2.1175-.6925-.3199-1.4768-.2032-2.0346.3033L64.1493 70.5705c-.5577.5065-1.341.6232-2.0336.3033-.7884-.3645-1.2048-1.2004-.9833-2.1176-4.9878-20.7064-9.9957-41.3993-15.0036-62.1062zm8.2757-28.0607C82.9604 18.7905 67.1796 10.2641 50.97 10.2641 28.5797 10.2641 10.4703 28.3736 10.4703 50.7639c0 16.2095 8.5264 31.9904 21.7363 42.2978.0201.0201.0401.0402.0602.0602.7053.5944 1.724-.0593 1.5179-.9243-.2061-.865-.4133-1.73-.6216-2.595-4.988-20.7268-9.9959-41.4397-15.0036-62.1663-.2215-.9171.1948-1.753.9833-2.1175.6925-.3199 1.4768-.2032 2.0345.3033L65.1193 70.5405c.5577.5065 1.341.6232 2.0336.3033.7884-.3645 1.2048-1.2004.9833-2.1175-5.0077-20.7266-10.0156-41.4395-15.0036-62.1663-.2061-.865.1875-1.5188.8929-1.9132.0201-.0111.0401-.0223.0602-.0335.7053-.3914 1.5716-.3257 2.2161.168 5.8015 4.4486 10.6948 10.0178 14.3783 16.4035 3.6833 6.3857 6.1567 13.5766 7.2138 21.0668.4248 3.0146.6423 6.0627.6423 9.1328 0 3.0701-.2175 6.1182-.6423 9.1328-1.0571 7.4902-3.5305 14.6811-7.2138 21.0668-3.6835 6.3856-8.5768 11.9548-14.3783 16.4035.02-.01.04-.02.06-.03.7054-.3914 1.5717-.3257 2.2162.168 12.134-7.5691 21.3652-19.8762 25.2433-34.0073 3.878-14.1311 2.3251-29.4094-4.5704-42.1292z"
      fill="currentColor"
    />
  </svg>
);

export default function LinearConfig({ isOpen, onClose, onSave, existingConfig }) {
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
  } = useIntegrationConfig('linear');

  const [showApiKey, setShowApiKey] = useState(false);
  const [priorityMapping, setPriorityMapping] = useState({
    critical: 1,
    high: 2,
    medium: 3,
    low: 4,
  });
  const [defaultLabels, setDefaultLabels] = useState([]);
  const [labelInput, setLabelInput] = useState('');
  const [createSubIssues, setCreateSubIssues] = useState(false);
  const [linkToCycle, setLinkToCycle] = useState(false);

  // Initialize with existing config
  useEffect(() => {
    if (existingConfig) {
      Object.entries(existingConfig).forEach(([key, value]) => {
        updateField(key, value);
      });
      if (existingConfig.priority_mapping) {
        setPriorityMapping(existingConfig.priority_mapping);
      }
      if (existingConfig.default_labels) {
        setDefaultLabels(existingConfig.default_labels);
      }
      if (existingConfig.create_sub_issues !== undefined) {
        setCreateSubIssues(existingConfig.create_sub_issues);
      }
      if (existingConfig.link_to_cycle !== undefined) {
        setLinkToCycle(existingConfig.link_to_cycle);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [existingConfig]);

  const handlePriorityChange = (auraSeverity, linearPriority) => {
    setPriorityMapping((prev) => ({ ...prev, [auraSeverity]: parseInt(linearPriority, 10) }));
  };

  const handleAddLabel = () => {
    const label = labelInput.trim();
    if (label && !defaultLabels.includes(label)) {
      setDefaultLabels((prev) => [...prev, label]);
      setLabelInput('');
    }
  };

  const handleRemoveLabel = (label) => {
    setDefaultLabels((prev) => prev.filter((l) => l !== label));
  };

  const handleLabelKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      handleAddLabel();
    }
  };

  const handleSave = async () => {
    try {
      const fullConfig = {
        ...config,
        priority_mapping: priorityMapping,
        default_labels: defaultLabels,
        create_sub_issues: createSubIssues,
        link_to_cycle: linkToCycle,
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
            <div className="p-2 bg-indigo-100 dark:bg-indigo-900/30 rounded-xl text-indigo-600 dark:text-indigo-400">
              <LinearIcon />
            </div>
            <div>
              <h2 className="text-xl font-bold text-surface-900 dark:text-surface-100">
                Configure Linear
              </h2>
              <p className="text-sm text-surface-500 dark:text-surface-400">
                Modern issue tracking for high-performance teams
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
              {/* API Authentication */}
              <section>
                <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                  API Authentication
                </h3>

                <div className="space-y-4">
                  {/* API Key */}
                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      API Key <span className="text-critical-500">*</span>
                    </label>
                    <div className="relative">
                      <input
                        type={showApiKey ? 'text' : 'password'}
                        value={config.api_key || ''}
                        onChange={(e) => updateField('api_key', e.target.value)}
                        placeholder="lin_api_..."
                        className={`w-full px-3 py-2 pr-10 border rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 font-mono text-sm ${
                          validationErrors.api_key
                            ? 'border-critical-300 dark:border-critical-700'
                            : 'border-surface-300 dark:border-surface-600'
                        }`}
                      />
                      <button
                        type="button"
                        onClick={() => setShowApiKey(!showApiKey)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300"
                      >
                        {showApiKey ? (
                          <EyeSlashIcon className="h-5 w-5" />
                        ) : (
                          <EyeIcon className="h-5 w-5" />
                        )}
                      </button>
                    </div>
                    {validationErrors.api_key && (
                      <p className="text-xs text-critical-600 dark:text-critical-400 mt-1">
                        {validationErrors.api_key}
                      </p>
                    )}
                    <div className="flex items-center gap-2 mt-1">
                      <p className="text-xs text-surface-500 dark:text-surface-400">
                        Generate from Settings &gt; Account &gt; API
                      </p>
                      <a
                        href="https://linear.app/settings/api"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-aura-600 dark:text-aura-400 hover:underline"
                      >
                        Open Linear
                        <ArrowTopRightOnSquareIcon className="h-3 w-3" />
                      </a>
                    </div>
                  </div>
                </div>
              </section>

              {/* Team & Project */}
              <section>
                <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                  Team & Project
                </h3>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      Team ID <span className="text-critical-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={config.team_id || ''}
                      onChange={(e) => updateField('team_id', e.target.value)}
                      placeholder="e.g., TEAM-123"
                      className={`w-full px-3 py-2 border rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 ${
                        validationErrors.team_id
                          ? 'border-critical-300 dark:border-critical-700'
                          : 'border-surface-300 dark:border-surface-600'
                      }`}
                    />
                    {validationErrors.team_id && (
                      <p className="text-xs text-critical-600 dark:text-critical-400 mt-1">
                        {validationErrors.team_id}
                      </p>
                    )}
                    <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                      Target team for issue creation
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      Default Project
                    </label>
                    <input
                      type="text"
                      value={config.project_id || ''}
                      onChange={(e) => updateField('project_id', e.target.value)}
                      placeholder="Optional"
                      className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500"
                    />
                    <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                      Optional project for categorization
                    </p>
                  </div>
                </div>
              </section>

              {/* Default Labels */}
              <section>
                <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                  Default Labels
                </h3>

                <div className="bg-surface-50 dark:bg-surface-700/50 rounded-lg p-4">
                  <p className="text-sm text-surface-600 dark:text-surface-400 mb-3">
                    Labels to apply to all issues created by Aura
                  </p>

                  <div className="flex flex-wrap gap-2 mb-3">
                    {defaultLabels.map((label) => (
                      <span
                        key={label}
                        className="inline-flex items-center gap-1 px-2.5 py-1 bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 rounded-full text-sm"
                      >
                        {label}
                        <button
                          type="button"
                          onClick={() => handleRemoveLabel(label)}
                          className="text-indigo-500 hover:text-indigo-700 dark:hover:text-indigo-200"
                        >
                          <XCircleIcon className="h-4 w-4" />
                        </button>
                      </span>
                    ))}
                  </div>

                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={labelInput}
                      onChange={(e) => setLabelInput(e.target.value)}
                      onKeyDown={handleLabelKeyDown}
                      placeholder="Add label..."
                      className="flex-1 px-3 py-1.5 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 text-sm focus:ring-2 focus:ring-aura-500"
                    />
                    <button
                      type="button"
                      onClick={handleAddLabel}
                      className="px-3 py-1.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
                    >
                      <PlusIcon className="h-4 w-4" />
                    </button>
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
                    Map Aura severity levels to Linear issue priorities
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
                            value={priorityMapping[severity.value] || 3}
                            onChange={(e) => handlePriorityChange(severity.value, e.target.value)}
                            className="px-3 py-1.5 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 text-sm focus:ring-2 focus:ring-aura-500"
                          >
                            {LINEAR_PRIORITIES.map((priority) => (
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

              {/* Advanced Settings */}
              <section>
                <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                  Advanced Settings
                </h3>

                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-surface-900 dark:text-surface-100">
                        Create sub-issues
                      </p>
                      <p className="text-sm text-surface-500 dark:text-surface-400">
                        Create child issues for related vulnerabilities
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setCreateSubIssues(!createSubIssues)}
                      className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2 ${
                        createSubIssues ? 'bg-aura-600' : 'bg-surface-200 dark:bg-surface-600'
                      }`}
                    >
                      <span
                        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                          createSubIssues ? 'translate-x-5' : 'translate-x-0'
                        }`}
                      />
                    </button>
                  </div>

                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-surface-900 dark:text-surface-100">
                        Link to active cycle
                      </p>
                      <p className="text-sm text-surface-500 dark:text-surface-400">
                        Automatically add issues to the current cycle
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setLinkToCycle(!linkToCycle)}
                      className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2 ${
                        linkToCycle ? 'bg-aura-600' : 'bg-surface-200 dark:bg-surface-600'
                      }`}
                    >
                      <span
                        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                          linkToCycle ? 'translate-x-5' : 'translate-x-0'
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
                      disabled={testing || !config.api_key || !config.team_id}
                      className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:bg-surface-400 dark:disabled:bg-surface-600 disabled:cursor-not-allowed transition-colors"
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
                        {testResult.team_name && (
                          <p className="text-xs opacity-75">Team: {testResult.team_name}</p>
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
            <span>API keys are encrypted at rest</span>
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
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:bg-surface-400 dark:disabled:bg-surface-600 disabled:cursor-not-allowed transition-colors"
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
