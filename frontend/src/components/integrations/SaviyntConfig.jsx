/**
 * Project Aura - Saviynt Enterprise Identity Cloud Configuration Modal
 *
 * Configuration interface for Saviynt Identity Governance and Administration (IGA)
 * platform with username/password authentication and bearer token flow.
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
  UserGroupIcon,
  KeyIcon,
  ShieldCheckIcon,
  ClipboardDocumentListIcon,
  ExclamationTriangleIcon,
  ChartBarIcon,
  ArrowTopRightOnSquareIcon,
} from '@heroicons/react/24/outline';
import { useIntegrationConfig } from '../../hooks/useIntegrations';

// Saviynt feature toggles
const SAVIYNT_FEATURES = [
  {
    id: 'user_management',
    label: 'User Management',
    description: 'User provisioning and lifecycle management',
    icon: UserGroupIcon,
  },
  {
    id: 'entitlements',
    label: 'Entitlements',
    description: 'Access entitlement sync and analysis',
    icon: KeyIcon,
  },
  {
    id: 'access_requests',
    label: 'Access Requests',
    description: 'Access request workflow integration',
    icon: ClipboardDocumentListIcon,
  },
  {
    id: 'certifications',
    label: 'Certifications',
    description: 'Access certification campaigns',
    icon: ShieldCheckIcon,
  },
  {
    id: 'pam_sessions',
    label: 'PAM Sessions',
    description: 'Privileged access session monitoring',
    icon: ShieldCheckIcon,
  },
  {
    id: 'risk_analytics',
    label: 'Risk Analytics',
    description: 'Identity risk scoring and analytics',
    icon: ChartBarIcon,
  },
];

// Risk threshold options
const RISK_THRESHOLDS = [
  { value: 'critical', label: 'Critical Only (Score >= 90)', minScore: 90 },
  { value: 'high', label: 'High and Above (Score >= 70)', minScore: 70 },
  { value: 'medium', label: 'Medium and Above (Score >= 50)', minScore: 50 },
  { value: 'all', label: 'All Risk Levels', minScore: 0 },
];

export default function SaviyntConfig({ isOpen, onClose, onSave, existingConfig }) {
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
  } = useIntegrationConfig('saviynt');

  const [showPassword, setShowPassword] = useState(false);
  const [enabledFeatures, setEnabledFeatures] = useState({
    user_management: true,
    entitlements: true,
    access_requests: true,
    certifications: false,
    pam_sessions: false,
    risk_analytics: false,
  });
  const [isGovCloud, setIsGovCloud] = useState(false);
  const [riskThreshold, setRiskThreshold] = useState('high');
  const [syncInterval, setSyncInterval] = useState('1hour');

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
      if (existingConfig.risk_threshold) {
        setRiskThreshold(existingConfig.risk_threshold);
      }
      if (existingConfig.sync_interval) {
        setSyncInterval(existingConfig.sync_interval);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [existingConfig]);

  const toggleFeature = (featureId) => {
    setEnabledFeatures((prev) => ({ ...prev, [featureId]: !prev[featureId] }));
  };

  const handleSave = async () => {
    try {
      const fullConfig = {
        ...config,
        enabled_features: enabledFeatures,
        is_govcloud: isGovCloud,
        risk_threshold: riskThreshold,
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
            <div className="p-2 bg-indigo-100 dark:bg-indigo-900/30 rounded-xl">
              <UserGroupIcon className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-surface-900 dark:text-surface-100">
                Configure Saviynt Enterprise Identity Cloud
              </h2>
              <p className="text-sm text-surface-500 dark:text-surface-400">
                Identity governance and privileged access management
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
                    <div className="p-2 bg-indigo-100 dark:bg-indigo-900/30 rounded-lg">
                      <ShieldCheckIcon className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                    </div>
                    <div>
                      <p className="font-medium text-surface-900 dark:text-surface-100">
                        GovCloud Environment
                      </p>
                      <p className="text-sm text-surface-500 dark:text-surface-400">
                        Enable for US Government deployment
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

              {/* Connection Settings */}
              <section>
                <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                  Connection Settings
                </h3>

                <div className="space-y-4">
                  {/* Base URL */}
                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      Saviynt URL <span className="text-critical-500">*</span>
                    </label>
                    <input
                      type="url"
                      value={config.base_url || ''}
                      onChange={(e) => updateField('base_url', e.target.value)}
                      placeholder="https://your-tenant.saviyntcloud.com"
                      className={`w-full px-3 py-2 border rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 ${
                        validationErrors.base_url
                          ? 'border-critical-300 dark:border-critical-700'
                          : 'border-surface-300 dark:border-surface-600'
                      }`}
                    />
                    {validationErrors.base_url && (
                      <p className="text-xs text-critical-600 dark:text-critical-400 mt-1">
                        {validationErrors.base_url}
                      </p>
                    )}
                    <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                      Your Saviynt EIC tenant URL
                    </p>
                  </div>

                  {/* Username */}
                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      Username <span className="text-critical-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={config.username || ''}
                      onChange={(e) => updateField('username', e.target.value)}
                      placeholder="api_service_account"
                      className={`w-full px-3 py-2 border rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 ${
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
                    <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                      Service account username with API access
                    </p>
                  </div>

                  {/* Password */}
                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      Password <span className="text-critical-500">*</span>
                    </label>
                    <div className="relative">
                      <input
                        type={showPassword ? 'text' : 'password'}
                        value={config.password || ''}
                        onChange={(e) => updateField('password', e.target.value)}
                        placeholder="Enter service account password"
                        className={`w-full px-3 py-2 pr-10 border rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 ${
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
                    <div className="flex items-center gap-2 mt-1">
                      <p className="text-xs text-surface-500 dark:text-surface-400">
                        Used to obtain bearer token for API calls
                      </p>
                      <a
                        href="https://docs.saviyntcloud.com/bundle/EIC-Admin-Guide/page/Content/Chapter06-API.htm"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-aura-600 dark:text-aura-400 hover:underline"
                      >
                        API Guide
                        <ArrowTopRightOnSquareIcon className="h-3 w-3" />
                      </a>
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
                  {SAVIYNT_FEATURES.map((feature) => {
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

              {/* Risk Analytics Settings */}
              {enabledFeatures.risk_analytics && (
                <section>
                  <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                    Risk Analytics Settings
                  </h3>

                  <div className="bg-surface-50 dark:bg-surface-700/50 rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-4">
                      <ExclamationTriangleIcon className="h-5 w-5 text-warning-500" />
                      <p className="text-sm font-medium text-surface-900 dark:text-surface-100">
                        Risk Threshold
                      </p>
                    </div>

                    <div className="space-y-2">
                      {RISK_THRESHOLDS.map((threshold) => (
                        <label
                          key={threshold.value}
                          className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-colors ${
                            riskThreshold === threshold.value
                              ? 'bg-aura-100 dark:bg-aura-900/30 border-2 border-aura-500'
                              : 'bg-white dark:bg-surface-700 border-2 border-transparent hover:border-surface-300 dark:hover:border-surface-600'
                          }`}
                        >
                          <input
                            type="radio"
                            name="risk_threshold"
                            value={threshold.value}
                            checked={riskThreshold === threshold.value}
                            onChange={(e) => setRiskThreshold(e.target.value)}
                            className="text-aura-600 focus:ring-aura-500"
                          />
                          <span className="text-sm text-surface-900 dark:text-surface-100">
                            {threshold.label}
                          </span>
                        </label>
                      ))}
                    </div>
                  </div>
                </section>
              )}

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
                    <option value="15min">Every 15 minutes</option>
                    <option value="30min">Every 30 minutes</option>
                    <option value="1hour">Every hour</option>
                    <option value="4hour">Every 4 hours</option>
                    <option value="daily">Daily</option>
                    <option value="manual">Manual only</option>
                  </select>
                  <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                    How often to sync identity data from Saviynt
                  </p>
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
                      disabled={testing || !config.base_url || !config.username || !config.password}
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
