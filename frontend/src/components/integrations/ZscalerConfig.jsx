/**
 * Project Aura - Zscaler Zero Trust Integration Configuration Modal
 *
 * Configuration interface for Zscaler Zero Trust platform integration with
 * ZIA (Internet Access), ZPA (Private Access), API key + OAuth2 authentication,
 * and GovCloud support.
 *
 * ADR-053: Enterprise Security Integrations Phase 2
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
  ShieldCheckIcon,
  GlobeAltIcon,
  LockClosedIcon,
  ArrowTopRightOnSquareIcon,
} from '@heroicons/react/24/outline';
import { useIntegrationConfig } from '../../hooks/useIntegrations';

// Zscaler feature toggles
const ZSCALER_FEATURES = [
  {
    id: 'web_security',
    label: 'Web Security (ZIA)',
    description: 'URL filtering, threat protection, and web DLP',
    icon: GlobeAltIcon,
  },
  {
    id: 'private_access',
    label: 'Private Access (ZPA)',
    description: 'Secure access to private applications',
    icon: LockClosedIcon,
  },
  {
    id: 'dlp_incidents',
    label: 'DLP Incidents',
    description: 'Data loss prevention incident sync',
    icon: ShieldCheckIcon,
  },
  {
    id: 'url_filtering',
    label: 'URL Filtering Logs',
    description: 'Web traffic and URL filtering events',
    icon: GlobeAltIcon,
  },
];

// Zscaler cloud options
const ZSCALER_CLOUDS = [
  { value: 'zscaler.net', label: 'Commercial (zscaler.net)', region: 'Global' },
  { value: 'zscalerone.net', label: 'ZscalerOne (zscalerone.net)', region: 'Enterprise' },
  { value: 'zscalertwo.net', label: 'ZscalerTwo (zscalertwo.net)', region: 'Enterprise' },
  { value: 'zscloud.net', label: 'ZS Cloud (zscloud.net)', region: 'Regional' },
  { value: 'zscalergov.net', label: 'GovCloud (zscalergov.net)', region: 'US Government' },
];

export default function ZscalerConfig({ isOpen, onClose, onSave, existingConfig }) {
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
  } = useIntegrationConfig('zscaler');

  const [showSecrets, setShowSecrets] = useState({});
  const [enabledFeatures, setEnabledFeatures] = useState({
    web_security: true,
    private_access: true,
    dlp_incidents: false,
    url_filtering: false,
  });
  const [isGovCloud, setIsGovCloud] = useState(false);
  const [syncInterval, setSyncInterval] = useState('15min');

  // Initialize with existing config
  useEffect(() => {
    if (existingConfig) {
      Object.entries(existingConfig).forEach(([key, value]) => {
        updateField(key, value);
      });
      if (existingConfig.enabled_features) {
        setEnabledFeatures(existingConfig.enabled_features);
      }
      if (existingConfig.is_govcloud !== undefined) {
        setIsGovCloud(existingConfig.is_govcloud);
      }
      if (existingConfig.sync_interval) {
        setSyncInterval(existingConfig.sync_interval);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [existingConfig]);

  // Update cloud based on GovCloud toggle
  useEffect(() => {
    if (isGovCloud && config.cloud !== 'zscalergov.net') {
      updateField('cloud', 'zscalergov.net');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isGovCloud]);

  const toggleSecret = (fieldName) => {
    setShowSecrets((prev) => ({ ...prev, [fieldName]: !prev[fieldName] }));
  };

  const toggleFeature = (featureId) => {
    setEnabledFeatures((prev) => ({ ...prev, [featureId]: !prev[featureId] }));
  };

  const handleSave = async () => {
    try {
      const fullConfig = {
        ...config,
        enabled_features: enabledFeatures,
        is_govcloud: isGovCloud,
        sync_interval: syncInterval,
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
            <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-xl">
              <ShieldCheckIcon className="h-6 w-6 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-surface-900 dark:text-surface-100">
                Configure Zscaler Zero Trust
              </h2>
              <p className="text-sm text-surface-500 dark:text-surface-400">
                Cloud-native security platform for zero trust architecture
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
              {/* GovCloud Toggle */}
              <section>
                <div className="flex items-center justify-between p-4 bg-surface-50 dark:bg-surface-700/50 rounded-lg border border-surface-200 dark:border-surface-600">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                      <ShieldCheckIcon className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                    </div>
                    <div>
                      <p className="font-medium text-surface-900 dark:text-surface-100">
                        GovCloud Environment
                      </p>
                      <p className="text-sm text-surface-500 dark:text-surface-400">
                        Enable for US Government (zscalergov.net)
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setIsGovCloud(!isGovCloud)}
                    className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2 ${
                      isGovCloud ? 'bg-aura-600' : 'bg-surface-200 dark:bg-surface-600'
                    }`}
                  >
                    <span
                      className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                        isGovCloud ? 'translate-x-5' : 'translate-x-0'
                      }`}
                    />
                  </button>
                </div>
              </section>

              {/* ZIA Configuration */}
              <section>
                <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                  ZIA (Zscaler Internet Access)
                </h3>

                <div className="space-y-4">
                  {/* ZIA Base URL */}
                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      ZIA Base URL <span className="text-critical-500">*</span>
                    </label>
                    <input
                      type="url"
                      value={config.zia_base_url || ''}
                      onChange={(e) => updateField('zia_base_url', e.target.value)}
                      placeholder={`https://zsapi.${isGovCloud ? 'zscalergov.net' : 'zscaler.net'}`}
                      className={`w-full px-3 py-2 border rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 ${
                        validationErrors.zia_base_url
                          ? 'border-critical-300 dark:border-critical-700'
                          : 'border-surface-300 dark:border-surface-600'
                      }`}
                    />
                    {validationErrors.zia_base_url && (
                      <p className="text-xs text-critical-600 dark:text-critical-400 mt-1">
                        {validationErrors.zia_base_url}
                      </p>
                    )}
                    <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                      Your Zscaler Internet Access API endpoint
                    </p>
                  </div>

                  {/* ZIA Cloud */}
                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      Cloud Environment <span className="text-critical-500">*</span>
                    </label>
                    <select
                      value={config.cloud || (isGovCloud ? 'zscalergov.net' : 'zscaler.net')}
                      onChange={(e) => updateField('cloud', e.target.value)}
                      className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500"
                    >
                      {ZSCALER_CLOUDS.map((cloud) => (
                        <option key={cloud.value} value={cloud.value}>
                          {cloud.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </section>

              {/* ZPA Configuration */}
              <section>
                <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                  ZPA (Zscaler Private Access)
                </h3>

                <div className="space-y-4">
                  {/* ZPA Base URL */}
                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      ZPA Base URL
                    </label>
                    <input
                      type="url"
                      value={config.zpa_base_url || ''}
                      onChange={(e) => updateField('zpa_base_url', e.target.value)}
                      placeholder={`https://config.private.zscaler.com`}
                      className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500"
                    />
                    <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                      Optional: Required for Private Access features
                    </p>
                  </div>
                </div>
              </section>

              {/* API Credentials */}
              <section>
                <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                  API Credentials
                </h3>

                <div className="space-y-4">
                  {/* API Key */}
                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      API Key <span className="text-critical-500">*</span>
                    </label>
                    <div className="relative">
                      <input
                        type={showSecrets.api_key ? 'text' : 'password'}
                        value={config.api_key || ''}
                        onChange={(e) => updateField('api_key', e.target.value)}
                        placeholder="Enter your Zscaler API key"
                        className={`w-full px-3 py-2 pr-10 border rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 ${
                          validationErrors.api_key
                            ? 'border-critical-300 dark:border-critical-700'
                            : 'border-surface-300 dark:border-surface-600'
                        }`}
                      />
                      <button
                        type="button"
                        onClick={() => toggleSecret('api_key')}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300"
                      >
                        {showSecrets.api_key ? (
                          <EyeSlashIcon className="h-5 w-5" />
                        ) : (
                          <EyeIcon className="h-5 w-5" />
                        )}
                      </button>
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <p className="text-xs text-surface-500 dark:text-surface-400">
                        Generate from ZIA Admin Portal &gt; Administration &gt; API Key Management
                      </p>
                      <a
                        href="https://help.zscaler.com/zia/api-developers-guide"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-aura-600 dark:text-aura-400 hover:underline"
                      >
                        Learn more
                        <ArrowTopRightOnSquareIcon className="h-3 w-3" />
                      </a>
                    </div>
                  </div>

                  {/* OAuth Client ID */}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                        Client ID
                      </label>
                      <input
                        type="text"
                        value={config.client_id || ''}
                        onChange={(e) => updateField('client_id', e.target.value)}
                        placeholder="OAuth Client ID"
                        className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500"
                      />
                      <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                        Required for OAuth2 flows
                      </p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                        Client Secret
                      </label>
                      <div className="relative">
                        <input
                          type={showSecrets.client_secret ? 'text' : 'password'}
                          value={config.client_secret || ''}
                          onChange={(e) => updateField('client_secret', e.target.value)}
                          placeholder="OAuth Client Secret"
                          className="w-full px-3 py-2 pr-10 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500"
                        />
                        <button
                          type="button"
                          onClick={() => toggleSecret('client_secret')}
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300"
                        >
                          {showSecrets.client_secret ? (
                            <EyeSlashIcon className="h-5 w-5" />
                          ) : (
                            <EyeIcon className="h-5 w-5" />
                          )}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </section>

              {/* Feature Selection */}
              <section>
                <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                  Enabled Features
                </h3>

                <div className="grid grid-cols-2 gap-3">
                  {ZSCALER_FEATURES.map((feature) => {
                    const FeatureIcon = feature.icon;
                    return (
                      <button
                        key={feature.id}
                        type="button"
                        onClick={() => toggleFeature(feature.id)}
                        className={`p-3 rounded-lg border-2 text-left transition-all ${
                          enabledFeatures[feature.id]
                            ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/20'
                            : 'border-surface-200 dark:border-surface-700 hover:border-surface-300 dark:hover:border-surface-600'
                        }`}
                      >
                        <div className="flex items-center gap-2 mb-1">
                          <FeatureIcon
                            className={`h-4 w-4 ${
                              enabledFeatures[feature.id]
                                ? 'text-aura-600 dark:text-aura-400'
                                : 'text-surface-400'
                            }`}
                          />
                          <p className="font-medium text-surface-900 dark:text-surface-100 text-sm">
                            {feature.label}
                          </p>
                        </div>
                        <p className="text-xs text-surface-500 dark:text-surface-400">
                          {feature.description}
                        </p>
                      </button>
                    );
                  })}
                </div>
              </section>

              {/* Sync Settings */}
              <section>
                <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                  Sync Settings
                </h3>

                <div>
                  <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                    Sync Interval
                  </label>
                  <select
                    value={syncInterval}
                    onChange={(e) => setSyncInterval(e.target.value)}
                    className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500"
                  >
                    <option value="5min">Every 5 minutes</option>
                    <option value="15min">Every 15 minutes</option>
                    <option value="30min">Every 30 minutes</option>
                    <option value="1hour">Every hour</option>
                    <option value="manual">Manual only</option>
                  </select>
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
                      disabled={testing || !config.zia_base_url || !config.api_key}
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
