/**
 * Project Aura - Compliance Settings Component (ADR-040)
 *
 * Provides UI for configuring compliance profiles, KMS encryption,
 * and log retention policies for CMMC/GovCloud compliance.
 */

import { useState, useEffect, useCallback } from 'react';
import {
  ShieldCheckIcon,
  KeyIcon,
  ClockIcon,
  DocumentCheckIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  ArrowPathIcon,
  BuildingOffice2Icon,
  BuildingLibraryIcon,
  CloudIcon,
} from '@heroicons/react/24/outline';

import {
  getComplianceSettings,
  updateComplianceSettings,
  applyComplianceProfile,
  COMPLIANCE_PROFILES,
  DEFAULT_COMPLIANCE_SETTINGS,
} from '../services/settingsApi';

// Profile icon mapping
const PROFILE_ICONS = {
  commercial: CloudIcon,
  cmmc_l1: BuildingOffice2Icon,
  cmmc_l2: ShieldCheckIcon,
  govcloud: BuildingLibraryIcon,
};

// Unified card styling - solid backgrounds with green selection
const CARD_STYLES = {
  base: 'bg-white dark:bg-surface-800 border-surface-200 dark:border-surface-700',
  selected: 'bg-white dark:bg-surface-800 border-olive-500 dark:border-olive-400',
  unselectedWhenOtherSelected: 'opacity-50',
  iconBg: 'bg-surface-100 dark:bg-surface-700',
  iconText: 'text-surface-600 dark:text-surface-400',
  selectedIconBg: 'bg-olive-100 dark:bg-olive-900/30',
  selectedIconText: 'text-olive-600 dark:text-olive-400',
};

/**
 * Compliance Settings Tab Component
 */
export default function ComplianceSettingsTab({ integrationMode, onSuccess, onError }) {
  // Check if Defense Mode is active - Commercial profile should be disabled
  const isDefenseMode = integrationMode === 'defense';
  const [settings, setSettings] = useState(DEFAULT_COMPLIANCE_SETTINGS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [applyingProfile, setApplyingProfile] = useState(null);

  // Load compliance settings on mount only
  useEffect(() => {
    loadSettings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const data = await getComplianceSettings();
      setSettings({
        profile: data.profile || 'commercial',
        kmsEncryptionMode: data.kms_encryption_mode || 'aws_managed',
        logRetentionDays: data.log_retention_days || 90,
        auditLogRetentionDays: data.audit_log_retention_days || 365,
        requireEncryptionAtRest: data.require_encryption_at_rest ?? true,
        requireEncryptionInTransit: data.require_encryption_in_transit ?? true,
        pendingKmsChange: data.pending_kms_change || false,
      });
    } catch (err) {
      onError?.(`Failed to load compliance settings: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleProfileSelect = useCallback(async (profileKey) => {
    setApplyingProfile(profileKey);
    try {
      const result = await applyComplianceProfile(profileKey);
      const profilePreset = COMPLIANCE_PROFILES[profileKey];

      setSettings((prev) => ({
        ...prev,
        profile: profileKey,
        kmsEncryptionMode: profilePreset.kmsMode,
        logRetentionDays: profilePreset.logRetention,
        auditLogRetentionDays: profilePreset.auditLogRetention,
        pendingKmsChange: result.kms_change_pending || false,
      }));

      onSuccess?.(`Applied ${profilePreset.name} compliance profile`);
    } catch (err) {
      onError?.(`Failed to apply profile: ${err.message}`);
    } finally {
      setApplyingProfile(null);
    }
  }, [onSuccess, onError]);

  // Auto-sync profile when Defense Mode is active and Commercial is selected
  useEffect(() => {
    if (isDefenseMode && settings.profile === 'commercial' && !loading) {
      // In Defense Mode, Commercial is not allowed - switch to CMMC Level 1
      handleProfileSelect('cmmc_l1');
    }
  }, [isDefenseMode, settings.profile, loading, handleProfileSelect]);

  const handleSettingChange = async (field, value) => {
    const newSettings = { ...settings, [field]: value };

    // Update local state immediately
    setSettings(newSettings);

    // Sync to backend
    setSaving(true);
    try {
      const result = await updateComplianceSettings({
        profile: newSettings.profile,
        kms_encryption_mode: newSettings.kmsEncryptionMode,
        log_retention_days: newSettings.logRetentionDays,
        audit_log_retention_days: newSettings.auditLogRetentionDays,
        require_encryption_at_rest: newSettings.requireEncryptionAtRest,
        require_encryption_in_transit: newSettings.requireEncryptionInTransit,
      });
      // Only show success if it was a real update or fallback succeeded
      if (result.updated) {
        onSuccess?.('Compliance settings updated (local)');
      } else {
        onSuccess?.('Compliance settings updated');
      }
    } catch (err) {
      onError?.(`Failed to update settings: ${err.message}`);
      // Revert on error (but not for network errors which are handled in the API)
      await loadSettings();
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <ArrowPathIcon className="h-8 w-8 text-aura-500 animate-spin" />
        <span className="ml-3 text-surface-600 dark:text-surface-400">
          Loading compliance settings...
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Pending KMS Change Warning */}
      {settings.pendingKmsChange && (
        <div className="bg-warning-50 dark:bg-warning-900/30 border border-warning-200 dark:border-warning-800 rounded-lg p-4 flex items-start gap-3">
          <ExclamationTriangleIcon className="h-5 w-5 text-warning-600 dark:text-warning-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-warning-800 dark:text-warning-200">
              KMS Encryption Change Pending
            </p>
            <p className="text-sm text-warning-700 dark:text-warning-300 mt-1">
              Changes to KMS encryption mode will take effect on the next
              infrastructure deployment. Existing resources retain their current
              encryption settings.
            </p>
          </div>
        </div>
      )}

      {/* Compliance Profile Selection */}
      <section>
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4 flex items-center gap-2">
          <DocumentCheckIcon className="h-5 w-5 text-aura-500" />
          Compliance Profile
        </h3>
        <p className="text-sm text-surface-600 dark:text-surface-400 mb-4">
          Select a compliance profile to apply pre-configured security settings
          for your regulatory requirements.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {Object.entries(COMPLIANCE_PROFILES).map(([key, profile]) => {
            const Icon = PROFILE_ICONS[key];
            const isSelected = settings.profile === key;
            const isApplying = applyingProfile === key;
            // Disable Commercial profile when in Defense Mode
            const isDisabledProfile = isDefenseMode && key === 'commercial';
            // Show "Defense Mode" badge on CMMC cards (not Commercial) when in Defense Mode
            const isDefenseModeOption = isDefenseMode && key !== 'commercial';
            // Grey out unselected cards when a profile is selected
            const hasSelection = settings.profile !== null;
            const isGreyedOut = hasSelection && !isSelected && !isApplying;

            return (
              <button
                key={key}
                onClick={() => !isDisabledProfile && handleProfileSelect(key)}
                disabled={saving || applyingProfile || isDisabledProfile}
                className={`
                  relative p-4 rounded-xl border-2 text-left transition-all
                  ${isSelected ? CARD_STYLES.selected : CARD_STYLES.base}
                  ${isSelected ? '' : 'hover:border-surface-400 dark:hover:border-surface-500'}
                  ${(saving || applyingProfile || isDisabledProfile) && !isApplying ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
                  ${isGreyedOut && !isDisabledProfile ? CARD_STYLES.unselectedWhenOtherSelected : ''}
                `}
              >
                {isDefenseModeOption && !isSelected && (
                  <span className="absolute top-3 right-3 text-xs font-medium text-critical-600 dark:text-critical-400 bg-critical-100 dark:bg-critical-900/30 px-2 py-0.5 rounded">
                    Defense Mode
                  </span>
                )}

                {isSelected && (
                  <CheckCircleIcon
                    className="absolute top-3 right-3 h-5 w-5 text-olive-500 dark:text-olive-400"
                  />
                )}

                {isApplying && (
                  <ArrowPathIcon className="absolute top-3 right-3 h-5 w-5 text-aura-500 animate-spin" />
                )}

                <div
                  className={`w-10 h-10 rounded-lg flex items-center justify-center mb-3 ${
                    isSelected ? CARD_STYLES.selectedIconBg : CARD_STYLES.iconBg
                  }`}
                >
                  <Icon
                    className={`h-5 w-5 ${isSelected ? CARD_STYLES.selectedIconText : CARD_STYLES.iconText}`}
                  />
                </div>

                <h4
                  className={`font-semibold ${isSelected ? 'text-olive-600 dark:text-olive-400' : 'text-surface-900 dark:text-surface-100'}`}
                >
                  {profile.name}
                </h4>
                <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                  {profile.description}
                </p>

                <div className="mt-3 space-y-1">
                  {profile.features.map((feature, idx) => (
                    <div
                      key={idx}
                      className="flex items-center gap-1.5 text-xs text-surface-600 dark:text-surface-400"
                    >
                      <CheckCircleIcon className="h-3 w-3 text-olive-500" />
                      {feature}
                    </div>
                  ))}
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {/* KMS Encryption Mode */}
      <section>
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4 flex items-center gap-2">
          <KeyIcon className="h-5 w-5 text-aura-500" />
          KMS Encryption
        </h3>

        <div className="bg-white dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded-lg p-6">
          <div className="flex items-start justify-between">
            <div>
              <h4 className="font-medium text-surface-900 dark:text-surface-100">
                Customer-Managed KMS Keys
              </h4>
              <p className="text-sm text-surface-600 dark:text-surface-400 mt-1">
                Use your own KMS keys for DynamoDB and S3 encryption. Required
                for CMMC Level 2 and GovCloud.
              </p>

              {settings.kmsEncryptionMode === 'customer_managed' && (
                <div className="mt-3 flex items-center gap-2 text-sm text-warning-600 dark:text-warning-400">
                  <InformationCircleIcon className="h-4 w-4" />
                  Changes require infrastructure redeployment
                </div>
              )}
            </div>

            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={settings.kmsEncryptionMode === 'customer_managed'}
                onChange={(e) =>
                  handleSettingChange(
                    'kmsEncryptionMode',
                    e.target.checked ? 'customer_managed' : 'aws_managed'
                  )
                }
                disabled={saving}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-surface-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-aura-300 dark:peer-focus:ring-aura-800 rounded-full peer dark:bg-surface-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-surface-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-surface-600 peer-checked:bg-aura-600"></div>
            </label>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-4">
            <div
              className={`p-3 rounded-lg border ${
                settings.kmsEncryptionMode === 'aws_managed'
                  ? 'bg-aura-50 dark:bg-aura-900/30 border-aura-200 dark:border-aura-800'
                  : 'bg-surface-50 dark:bg-surface-800 border-surface-200 dark:border-surface-700'
              }`}
            >
              <p className="text-sm font-medium text-surface-900 dark:text-surface-100">
                AWS-Managed
              </p>
              <p className="text-xs text-surface-500 dark:text-surface-400">
                Default AWS encryption keys
              </p>
            </div>
            <div
              className={`p-3 rounded-lg border ${
                settings.kmsEncryptionMode === 'customer_managed'
                  ? 'bg-aura-50 dark:bg-aura-900/30 border-aura-200 dark:border-aura-800'
                  : 'bg-surface-50 dark:bg-surface-800 border-surface-200 dark:border-surface-700'
              }`}
            >
              <p className="text-sm font-medium text-surface-900 dark:text-surface-100">
                Customer-Managed
              </p>
              <p className="text-xs text-surface-500 dark:text-surface-400">
                Your own KMS CMK keys
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Log Retention Settings */}
      <section>
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4 flex items-center gap-2">
          <ClockIcon className="h-5 w-5 text-aura-500" />
          Log Retention
        </h3>

        <div className="bg-white dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded-lg p-6 space-y-6">
          {/* Application Log Retention */}
          <div>
            <label className="block text-sm font-medium text-surface-900 dark:text-surface-100 mb-2">
              Application Log Retention
            </label>
            <select
              value={settings.logRetentionDays}
              onChange={(e) =>
                handleSettingChange('logRetentionDays', parseInt(e.target.value))
              }
              disabled={saving}
              className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
            >
              <option value={30}>30 days (Commercial)</option>
              <option value={60}>60 days (Commercial)</option>
              <option value={90}>90 days (CMMC L2 Minimum)</option>
              <option value={180}>180 days (Enhanced)</option>
              <option value={365}>365 days (GovCloud/FedRAMP)</option>
            </select>
            {settings.logRetentionDays < 90 && (
              <p className="mt-2 text-sm text-warning-600 dark:text-warning-400 flex items-center gap-1">
                <ExclamationTriangleIcon className="h-4 w-4" />
                Does not meet CMMC L2 requirements (90+ days required)
              </p>
            )}
          </div>

          {/* Audit Log Retention */}
          <div>
            <label className="block text-sm font-medium text-surface-900 dark:text-surface-100 mb-2">
              Audit Log Retention
            </label>
            <select
              value={settings.auditLogRetentionDays}
              onChange={(e) =>
                handleSettingChange(
                  'auditLogRetentionDays',
                  parseInt(e.target.value)
                )
              }
              disabled={saving}
              className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
            >
              <option value={90}>90 days</option>
              <option value={180}>180 days</option>
              <option value={365}>365 days (Recommended)</option>
              <option value={731}>2 years</option>
              <option value={1096}>3 years</option>
            </select>
            <p className="mt-2 text-xs text-surface-500 dark:text-surface-400">
              Audit logs are retained separately for compliance and
              investigation purposes.
            </p>
          </div>
        </div>
      </section>

      {/* Encryption Requirements */}
      <section>
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4 flex items-center gap-2">
          <ShieldCheckIcon className="h-5 w-5 text-aura-500" />
          Encryption Requirements
        </h3>

        <div className="bg-white dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded-lg divide-y divide-surface-200 dark:divide-surface-700">
          {/* Encryption at Rest */}
          <div className="p-4 flex items-center justify-between">
            <div>
              <h4 className="font-medium text-surface-900 dark:text-surface-100">
                Encryption at Rest
              </h4>
              <p className="text-sm text-surface-500 dark:text-surface-400">
                Require all data to be encrypted when stored
              </p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={settings.requireEncryptionAtRest}
                onChange={(e) =>
                  handleSettingChange(
                    'requireEncryptionAtRest',
                    e.target.checked
                  )
                }
                disabled={saving}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-surface-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-aura-300 dark:peer-focus:ring-aura-800 rounded-full peer dark:bg-surface-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-surface-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-surface-600 peer-checked:bg-aura-600"></div>
            </label>
          </div>

          {/* Encryption in Transit */}
          <div className="p-4 flex items-center justify-between">
            <div>
              <h4 className="font-medium text-surface-900 dark:text-surface-100">
                Encryption in Transit
              </h4>
              <p className="text-sm text-surface-500 dark:text-surface-400">
                Require TLS for all network communications
              </p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={settings.requireEncryptionInTransit}
                onChange={(e) =>
                  handleSettingChange(
                    'requireEncryptionInTransit',
                    e.target.checked
                  )
                }
                disabled={saving}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-surface-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-aura-300 dark:peer-focus:ring-aura-800 rounded-full peer dark:bg-surface-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-surface-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-surface-600 peer-checked:bg-aura-600"></div>
            </label>
          </div>
        </div>
      </section>

      {/* Current Status Summary */}
      <section className="bg-surface-50 dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4">
          Current Compliance Status
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center">
            <p className="text-2xl font-bold text-aura-600 dark:text-aura-400">
              {COMPLIANCE_PROFILES[settings.profile]?.name || 'Commercial'}
            </p>
            <p className="text-xs text-surface-500 dark:text-surface-400">
              Active Profile
            </p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">
              {settings.kmsEncryptionMode === 'customer_managed' ? 'CMK' : 'AWS'}
            </p>
            <p className="text-xs text-surface-500 dark:text-surface-400">
              KMS Mode
            </p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">
              {settings.logRetentionDays}d
            </p>
            <p className="text-xs text-surface-500 dark:text-surface-400">
              Log Retention
            </p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">
              {settings.auditLogRetentionDays}d
            </p>
            <p className="text-xs text-surface-500 dark:text-surface-400">
              Audit Retention
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
