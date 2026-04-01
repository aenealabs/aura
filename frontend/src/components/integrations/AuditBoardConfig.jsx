/**
 * Project Aura - AuditBoard GRC Integration Configuration Modal
 *
 * Configuration interface for AuditBoard GRC platform integration with
 * HMAC signature authentication (API key + secret) and compliance framework support.
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
  ClipboardDocumentCheckIcon,
  ShieldCheckIcon,
  DocumentMagnifyingGlassIcon,
  ExclamationTriangleIcon,
  DocumentTextIcon,
  ScaleIcon,
  ArrowTopRightOnSquareIcon,
} from '@heroicons/react/24/outline';
import { useIntegrationConfig } from '../../hooks/useIntegrations';

// AuditBoard feature toggles
const AUDITBOARD_FEATURES = [
  {
    id: 'controls',
    label: 'Controls',
    description: 'Control testing and monitoring',
    icon: ShieldCheckIcon,
  },
  {
    id: 'risks',
    label: 'Risks',
    description: 'Risk register and assessments',
    icon: ExclamationTriangleIcon,
  },
  {
    id: 'findings',
    label: 'Findings',
    description: 'Audit findings and remediation',
    icon: DocumentMagnifyingGlassIcon,
  },
  {
    id: 'evidence',
    label: 'Evidence',
    description: 'Evidence collection and requests',
    icon: DocumentTextIcon,
  },
];

// Supported compliance frameworks
const COMPLIANCE_FRAMEWORKS = [
  { id: 'soc2', label: 'SOC 2', description: 'Trust Services Criteria' },
  { id: 'iso27001', label: 'ISO 27001', description: 'Information Security Management' },
  { id: 'cmmc', label: 'CMMC', description: 'Cybersecurity Maturity Model Certification' },
  { id: 'nist_csf', label: 'NIST CSF', description: 'Cybersecurity Framework' },
  { id: 'nist_800_53', label: 'NIST 800-53', description: 'Security Controls' },
  { id: 'hipaa', label: 'HIPAA', description: 'Health Insurance Portability' },
  { id: 'pci_dss', label: 'PCI DSS', description: 'Payment Card Industry' },
  { id: 'gdpr', label: 'GDPR', description: 'General Data Protection Regulation' },
  { id: 'fedramp', label: 'FedRAMP', description: 'Federal Risk Authorization' },
];

// Evidence sync modes
const EVIDENCE_SYNC_MODES = [
  { value: 'all', label: 'All Evidence', description: 'Sync all evidence requests and attachments' },
  { value: 'pending', label: 'Pending Only', description: 'Only sync pending evidence requests' },
  { value: 'manual', label: 'Manual Upload', description: 'Manually push evidence from Aura' },
];

export default function AuditBoardConfig({ isOpen, onClose, onSave, existingConfig }) {
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
  } = useIntegrationConfig('auditboard');

  const [showSecrets, setShowSecrets] = useState({});
  const [enabledFeatures, setEnabledFeatures] = useState({
    controls: true,
    risks: true,
    findings: true,
    evidence: false,
  });
  const [enabledFrameworks, setEnabledFrameworks] = useState({
    soc2: true,
    iso27001: true,
    cmmc: true,
    nist_csf: false,
    nist_800_53: false,
    hipaa: false,
    pci_dss: false,
    gdpr: false,
    fedramp: false,
  });
  const [isGovCloud, setIsGovCloud] = useState(false);
  const [evidenceSyncMode, setEvidenceSyncMode] = useState('pending');
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
      if (existingConfig.enabled_frameworks) {
        setEnabledFrameworks(existingConfig.enabled_frameworks);
      }
      if (existingConfig.is_govcloud !== undefined) {
        setIsGovCloud(existingConfig.is_govcloud);
      }
      if (existingConfig.evidence_sync_mode) {
        setEvidenceSyncMode(existingConfig.evidence_sync_mode);
      }
      if (existingConfig.sync_interval) {
        setSyncInterval(existingConfig.sync_interval);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [existingConfig]);

  const toggleSecret = (fieldName) => {
    setShowSecrets((prev) => ({ ...prev, [fieldName]: !prev[fieldName] }));
  };

  const toggleFeature = (featureId) => {
    setEnabledFeatures((prev) => ({ ...prev, [featureId]: !prev[featureId] }));
  };

  const toggleFramework = (frameworkId) => {
    setEnabledFrameworks((prev) => ({ ...prev, [frameworkId]: !prev[frameworkId] }));
  };

  const handleSave = async () => {
    try {
      const fullConfig = {
        ...config,
        enabled_features: enabledFeatures,
        enabled_frameworks: enabledFrameworks,
        is_govcloud: isGovCloud,
        evidence_sync_mode: evidenceSyncMode,
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

  const selectedFrameworkCount = Object.values(enabledFrameworks).filter(Boolean).length;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-white dark:bg-surface-800 rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-surface-200 dark:border-surface-700 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-100 dark:bg-emerald-900/30 rounded-xl">
              <ClipboardDocumentCheckIcon className="h-6 w-6 text-emerald-600 dark:text-emerald-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-surface-900 dark:text-surface-100">
                Configure AuditBoard GRC
              </h2>
              <p className="text-sm text-surface-500 dark:text-surface-400">
                Governance, risk, and compliance management platform
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
                    <div className="p-2 bg-emerald-100 dark:bg-emerald-900/30 rounded-lg">
                      <ShieldCheckIcon className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
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
                      AuditBoard URL <span className="text-critical-500">*</span>
                    </label>
                    <input
                      type="url"
                      value={config.base_url || ''}
                      onChange={(e) => updateField('base_url', e.target.value)}
                      placeholder="https://your-org.auditboardapp.com"
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
                      Your AuditBoard instance URL
                    </p>
                  </div>

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
                        placeholder="Enter your AuditBoard API key"
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
                    <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                      Used as the public key for HMAC authentication
                    </p>
                  </div>

                  {/* API Secret */}
                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      API Secret <span className="text-critical-500">*</span>
                    </label>
                    <div className="relative">
                      <input
                        type={showSecrets.api_secret ? 'text' : 'password'}
                        value={config.api_secret || ''}
                        onChange={(e) => updateField('api_secret', e.target.value)}
                        placeholder="Enter your AuditBoard API secret"
                        className={`w-full px-3 py-2 pr-10 border rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 ${
                          validationErrors.api_secret
                            ? 'border-critical-300 dark:border-critical-700'
                            : 'border-surface-300 dark:border-surface-600'
                        }`}
                      />
                      <button
                        type="button"
                        onClick={() => toggleSecret('api_secret')}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300"
                      >
                        {showSecrets.api_secret ? (
                          <EyeSlashIcon className="h-5 w-5" />
                        ) : (
                          <EyeIcon className="h-5 w-5" />
                        )}
                      </button>
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <p className="text-xs text-surface-500 dark:text-surface-400">
                        Used to sign requests with HMAC-SHA256
                      </p>
                      <a
                        href="https://support.auditboard.com/hc/en-us/articles/360000000000-API-Documentation"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-aura-600 dark:text-aura-400 hover:underline"
                      >
                        API Docs
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
                  {AUDITBOARD_FEATURES.map((feature) => {
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

              {/* Compliance Frameworks */}
              <section>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide">
                    Compliance Frameworks
                  </h3>
                  <span className="text-xs px-2 py-1 bg-aura-100 dark:bg-aura-900/30 text-aura-700 dark:text-aura-400 rounded-full">
                    {selectedFrameworkCount} selected
                  </span>
                </div>

                <div className="bg-surface-50 dark:bg-surface-700/50 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-4">
                    <ScaleIcon className="h-5 w-5 text-surface-400" />
                    <p className="text-sm text-surface-600 dark:text-surface-400">
                      Select frameworks to sync controls, risks, and findings
                    </p>
                  </div>

                  <div className="grid grid-cols-3 gap-2">
                    {COMPLIANCE_FRAMEWORKS.map((framework) => (
                      <button
                        key={framework.id}
                        type="button"
                        onClick={() => toggleFramework(framework.id)}
                        className={`p-2 rounded-lg border text-left transition-all ${
                          enabledFrameworks[framework.id]
                            ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/20'
                            : 'border-surface-200 dark:border-surface-600 hover:border-surface-300 dark:hover:border-surface-500'
                        }`}
                      >
                        <p className="font-medium text-surface-900 dark:text-surface-100 text-sm">
                          {framework.label}
                        </p>
                        <p className="text-xs text-surface-500 dark:text-surface-400 truncate">
                          {framework.description}
                        </p>
                      </button>
                    ))}
                  </div>
                </div>
              </section>

              {/* Evidence Sync Settings */}
              {enabledFeatures.evidence && (
                <section>
                  <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                    Evidence Sync Mode
                  </h3>

                  <div className="space-y-2">
                    {EVIDENCE_SYNC_MODES.map((mode) => (
                      <label
                        key={mode.value}
                        className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-colors ${
                          evidenceSyncMode === mode.value
                            ? 'bg-aura-100 dark:bg-aura-900/30 border-2 border-aura-500'
                            : 'bg-surface-50 dark:bg-surface-700 border-2 border-transparent hover:border-surface-300 dark:hover:border-surface-600'
                        }`}
                      >
                        <input
                          type="radio"
                          name="evidence_sync_mode"
                          value={mode.value}
                          checked={evidenceSyncMode === mode.value}
                          onChange={(e) => setEvidenceSyncMode(e.target.value)}
                          className="text-aura-600 focus:ring-aura-500"
                        />
                        <div>
                          <p className="text-sm font-medium text-surface-900 dark:text-surface-100">
                            {mode.label}
                          </p>
                          <p className="text-xs text-surface-500 dark:text-surface-400">
                            {mode.description}
                          </p>
                        </div>
                      </label>
                    ))}
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
                    <option value="30min">Every 30 minutes</option>
                    <option value="1hour">Every hour</option>
                    <option value="4hour">Every 4 hours</option>
                    <option value="daily">Daily</option>
                    <option value="manual">Manual only</option>
                  </select>
                  <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                    How often to sync GRC data from AuditBoard
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
                      disabled={testing || !config.base_url || !config.api_key || !config.api_secret}
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
