/**
 * Project Aura - JupyterLab Integration Configuration Modal
 *
 * Configuration interface for JupyterLab notebook integration
 * with workspace token authentication and output scanning settings.
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
  DocumentTextIcon,
  ArrowTopRightOnSquareIcon,
} from '@heroicons/react/24/outline';
import { useIntegrationConfig } from '../../hooks/useIntegrations';

const SCAN_OUTPUT_OPTIONS = [
  { value: 'enabled', label: 'Enabled', description: 'Scan cell outputs for sensitive data' },
  { value: 'disabled', label: 'Disabled', description: 'Skip output scanning (faster)' },
];

export default function JupyterLabConfig({ isOpen, onClose, onSave, existingConfig }) {
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
  } = useIntegrationConfig('jupyterlab');

  const [showSecrets, setShowSecrets] = useState({});
  const [scanMarkdown, setScanMarkdown] = useState(true);
  const [autoSaveNotebooks, setAutoSaveNotebooks] = useState(false);

  // Initialize with existing config
  useEffect(() => {
    if (existingConfig) {
      Object.entries(existingConfig).forEach(([key, value]) => {
        updateField(key, value);
      });
      if (existingConfig.scan_markdown !== undefined) {
        setScanMarkdown(existingConfig.scan_markdown);
      }
      if (existingConfig.auto_save_notebooks !== undefined) {
        setAutoSaveNotebooks(existingConfig.auto_save_notebooks);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [existingConfig]);

  const toggleSecret = (fieldName) => {
    setShowSecrets((prev) => ({ ...prev, [fieldName]: !prev[fieldName] }));
  };

  const handleSave = async () => {
    try {
      const fullConfig = {
        ...config,
        scan_markdown: scanMarkdown,
        auto_save_notebooks: autoSaveNotebooks,
      };
      await saveConfig(fullConfig);
      onSave?.(fullConfig);
      onClose();
    } catch (_err) {
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
            <div className="p-2 bg-orange-100 dark:bg-orange-900/30 rounded-xl">
              <DocumentTextIcon className="h-6 w-6 text-orange-600 dark:text-orange-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-surface-900 dark:text-surface-100">
                Configure JupyterLab
              </h2>
              <p className="text-sm text-surface-500 dark:text-surface-400">
                Interactive notebook security scanning
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
                  Authentication
                </h3>

                <div className="space-y-4">
                  {/* Workspace Token */}
                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      Workspace Token <span className="text-critical-500">*</span>
                    </label>
                    <div className="relative">
                      <input
                        type={showSecrets.workspace_token ? 'text' : 'password'}
                        value={config.workspace_token || ''}
                        onChange={(e) => updateField('workspace_token', e.target.value)}
                        placeholder="aura_wst_xxxxxxxxxxxxxxxxxxxx"
                        className={`w-full px-3 py-2 pr-10 border rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 ${
                          validationErrors.workspace_token
                            ? 'border-critical-300 dark:border-critical-700'
                            : 'border-surface-300 dark:border-surface-600'
                        }`}
                      />
                      <button
                        type="button"
                        onClick={() => toggleSecret('workspace_token')}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300"
                      >
                        {showSecrets.workspace_token ? (
                          <EyeSlashIcon className="h-5 w-5" />
                        ) : (
                          <EyeIcon className="h-5 w-5" />
                        )}
                      </button>
                    </div>
                    {validationErrors.workspace_token && (
                      <p className="text-xs text-critical-600 dark:text-critical-400 mt-1">
                        {validationErrors.workspace_token}
                      </p>
                    )}
                    <div className="flex items-center gap-2 mt-1">
                      <p className="text-xs text-surface-500 dark:text-surface-400">
                        Generate from Settings &gt; Integrations &gt; IDE Tokens
                      </p>
                      <a
                        href="https://jupyterlab.readthedocs.io/en/stable/user/extensions.html"
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

              {/* Server Settings */}
              <section>
                <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                  Server Settings
                </h3>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      Jupyter Server URL
                    </label>
                    <input
                      type="url"
                      value={config.jupyter_server || ''}
                      onChange={(e) => updateField('jupyter_server', e.target.value)}
                      placeholder="http://localhost:8888"
                      className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500"
                    />
                    <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                      Optional: URL of your JupyterLab server (for remote scanning)
                    </p>
                  </div>
                </div>
              </section>

              {/* Output Scanning Settings */}
              <section>
                <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                  Output Scanning
                </h3>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                      Scan Outputs
                    </label>
                    <div className="space-y-2">
                      {SCAN_OUTPUT_OPTIONS.map((option) => (
                        <label
                          key={option.value}
                          className={`flex items-center p-3 border rounded-lg cursor-pointer transition-colors ${
                            config.scan_outputs === option.value
                              ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/20'
                              : 'border-surface-300 dark:border-surface-600 hover:border-surface-400 dark:hover:border-surface-500'
                          }`}
                        >
                          <input
                            type="radio"
                            name="scan_outputs"
                            value={option.value}
                            checked={config.scan_outputs === option.value}
                            onChange={(e) => updateField('scan_outputs', e.target.value)}
                            className="sr-only"
                          />
                          <div className="flex-1">
                            <p className="font-medium text-surface-900 dark:text-surface-100">
                              {option.label}
                            </p>
                            <p className="text-sm text-surface-500 dark:text-surface-400">
                              {option.description}
                            </p>
                          </div>
                          <div
                            className={`w-4 h-4 rounded-full border-2 ${
                              config.scan_outputs === option.value
                                ? 'border-aura-500 bg-aura-500'
                                : 'border-surface-400 dark:border-surface-500'
                            }`}
                          >
                            {config.scan_outputs === option.value && (
                              <div className="w-full h-full flex items-center justify-center">
                                <div className="w-1.5 h-1.5 bg-white rounded-full" />
                              </div>
                            )}
                          </div>
                        </label>
                      ))}
                    </div>
                    <p className="text-xs text-surface-500 dark:text-surface-400 mt-2">
                      Output scanning detects secrets, credentials, and PII in cell outputs
                    </p>
                  </div>
                </div>
              </section>

              {/* Additional Settings */}
              <section>
                <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                  Additional Settings
                </h3>

                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-surface-900 dark:text-surface-100">
                        Scan markdown cells
                      </p>
                      <p className="text-sm text-surface-500 dark:text-surface-400">
                        Include markdown content in security analysis
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setScanMarkdown(!scanMarkdown)}
                      className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2 ${
                        scanMarkdown ? 'bg-aura-600' : 'bg-surface-200 dark:bg-surface-600'
                      }`}
                    >
                      <span
                        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                          scanMarkdown ? 'translate-x-5' : 'translate-x-0'
                        }`}
                      />
                    </button>
                  </div>

                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-surface-900 dark:text-surface-100">
                        Auto-save notebooks
                      </p>
                      <p className="text-sm text-surface-500 dark:text-surface-400">
                        Automatically save notebooks after clearing secrets
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setAutoSaveNotebooks(!autoSaveNotebooks)}
                      className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2 ${
                        autoSaveNotebooks ? 'bg-aura-600' : 'bg-surface-200 dark:bg-surface-600'
                      }`}
                    >
                      <span
                        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                          autoSaveNotebooks ? 'translate-x-5' : 'translate-x-0'
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
                      disabled={testing || !config.workspace_token}
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
