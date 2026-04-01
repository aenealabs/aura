/**
 * GuardrailSettings Component (ADR-069)
 *
 * Main settings page for guardrail configuration.
 * Combines SecurityProfileSelector, AdvancedSettings, and ActivityDashboard.
 *
 * @module components/guardrails/GuardrailSettings
 */

import React, { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import { ArrowLeftIcon, CheckCircleIcon } from '@heroicons/react/24/outline';

import SecurityProfileSelector, { SECURITY_PROFILES } from './SecurityProfileSelector';
import AdvancedGuardrailSettings from './AdvancedGuardrailSettings';
import GuardrailActivityDashboard from './GuardrailActivityDashboard';
import ComplianceProfileBadge, { ComplianceProfileSelector } from './ComplianceProfileBadge';
import ImpactPreviewModal from './ImpactPreviewModal';

/**
 * Default settings for each security profile
 */
const PROFILE_DEFAULTS = {
  conservative: {
    hitlSensitivity: 3,
    trustLevel: 'high',
    verbosity: 'detailed',
    reviewerType: 'security_team',
    enableAnomalyAlerts: true,
    auditAllDecisions: true,
    enableContradictionDetection: true,
  },
  balanced: {
    hitlSensitivity: 1,
    trustLevel: 'medium',
    verbosity: 'standard',
    reviewerType: 'team_lead',
    enableAnomalyAlerts: true,
    auditAllDecisions: false,
    enableContradictionDetection: true,
  },
  efficient: {
    hitlSensitivity: 0,
    trustLevel: 'low',
    verbosity: 'standard',
    reviewerType: 'team_lead',
    enableAnomalyAlerts: true,
    auditAllDecisions: false,
    enableContradictionDetection: true,
  },
  aggressive: {
    hitlSensitivity: 0,
    trustLevel: 'all',
    verbosity: 'minimal',
    reviewerType: 'auto_escalate',
    enableAnomalyAlerts: false,
    auditAllDecisions: false,
    enableContradictionDetection: false,
  },
};

/**
 * GuardrailSettings - Main page component
 *
 * @param {Object} props
 * @param {Object} [props.initialSettings] - Initial configuration values
 * @param {Function} [props.onSave] - Callback when settings are saved
 * @param {Function} [props.onBack] - Callback for back navigation
 * @param {Function} [props.fetchMetrics] - Function to fetch activity metrics
 * @param {Function} [props.fetchImpactPreview] - Function to fetch impact projections
 * @param {string} [props.className] - Additional CSS classes
 */
function GuardrailSettings({
  initialSettings = {},
  onSave,
  onBack,
  fetchMetrics,
  fetchImpactPreview,
  className = '',
}) {
  // State
  const [selectedProfile, setSelectedProfile] = useState(
    initialSettings.profile || 'balanced'
  );
  const [advancedSettings, setAdvancedSettings] = useState({
    ...PROFILE_DEFAULTS.balanced,
    ...initialSettings.advanced,
  });
  const [complianceProfile, setComplianceProfile] = useState(
    initialSettings.complianceProfile || null
  );
  const [metrics, setMetrics] = useState(null);
  const [metricsTimeRange, setMetricsTimeRange] = useState('7d');
  const [isLoadingMetrics, setIsLoadingMetrics] = useState(false);
  const [showImpactModal, setShowImpactModal] = useState(false);
  const [pendingChanges, setPendingChanges] = useState(null);
  const [impactPreview, setImpactPreview] = useState(null);
  const [isLoadingImpact, setIsLoadingImpact] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  // Track changes
  useEffect(() => {
    const currentSettings = {
      profile: selectedProfile,
      complianceProfile,
      advanced: advancedSettings,
    };
    const hasModifications =
      JSON.stringify(currentSettings) !== JSON.stringify(initialSettings);
    setHasChanges(hasModifications);
  }, [selectedProfile, advancedSettings, complianceProfile, initialSettings]);

  // Fetch metrics on mount and time range change
  const loadMetrics = useCallback(async () => {
    if (!fetchMetrics) return;

    setIsLoadingMetrics(true);
    try {
      const data = await fetchMetrics(metricsTimeRange);
      setMetrics(data);
    } catch (error) {
      console.error('Failed to fetch metrics:', error);
    } finally {
      setIsLoadingMetrics(false);
    }
  }, [fetchMetrics, metricsTimeRange]);

  useEffect(() => {
    loadMetrics();
  }, [loadMetrics]);

  // Handle profile change
  const handleProfileChange = (profileId) => {
    setSelectedProfile(profileId);
    // Apply default settings for the profile
    setAdvancedSettings({
      ...advancedSettings,
      ...PROFILE_DEFAULTS[profileId],
    });
  };

  // Handle compliance profile change
  const handleComplianceChange = (profileId) => {
    setComplianceProfile(profileId);
    // In a real app, this would fetch locked settings from the backend
  };

  // Get locked settings based on compliance profile
  const getLockedSettings = () => {
    if (!complianceProfile) return {};

    // Example locked settings for different compliance profiles
    const lockedByCompliance = {
      cmmc_l2: {
        auditAllDecisions: true,
        auditAllDecisionsReason: 'CMMC Level 2 requires full audit trail',
      },
      cmmc_l3: {
        auditAllDecisions: true,
        auditAllDecisionsReason: 'CMMC Level 3 requires full audit trail',
        enableContradictionDetection: true,
        enableContradictionDetectionReason: 'CMMC Level 3 requires contradiction detection',
      },
      fedramp_high: {
        hitlSensitivity: true,
        hitlSensitivityReason: 'FedRAMP High requires maximum HITL oversight',
        trustLevel: true,
        trustLevelReason: 'FedRAMP High requires High trust level only',
        auditAllDecisions: true,
        auditAllDecisionsReason: 'FedRAMP High requires full audit trail',
      },
    };

    return lockedByCompliance[complianceProfile] || {};
  };

  // Get locked profiles based on compliance
  const getLockedProfiles = () => {
    if (!complianceProfile) return [];

    // Example: FedRAMP High locks out Efficient and Aggressive profiles
    const lockedByCompliance = {
      fedramp_high: ['efficient', 'aggressive'],
      cmmc_l3: ['aggressive'],
    };

    return lockedByCompliance[complianceProfile] || [];
  };

  // Prepare to save - show impact preview first
  const handleSaveClick = async () => {
    const changes = {
      profile: selectedProfile,
      complianceProfile,
      advanced: advancedSettings,
    };

    setPendingChanges(changes);

    if (fetchImpactPreview) {
      setIsLoadingImpact(true);
      setShowImpactModal(true);

      try {
        const preview = await fetchImpactPreview(changes);
        setImpactPreview(preview);
      } catch (error) {
        console.error('Failed to fetch impact preview:', error);
        // Show modal anyway with error state
        setImpactPreview({
          metrics: [],
          warnings: [
            {
              severity: 'warning',
              title: 'Unable to load projections',
              message: 'Impact metrics are unavailable. Proceed with caution.',
            },
          ],
        });
      } finally {
        setIsLoadingImpact(false);
      }
    } else {
      // No impact preview available, save directly
      handleConfirmSave();
    }
  };

  // Confirm and save changes
  const handleConfirmSave = async () => {
    setShowImpactModal(false);

    if (onSave) {
      try {
        await onSave(pendingChanges || {
          profile: selectedProfile,
          complianceProfile,
          advanced: advancedSettings,
        });
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 3000);
      } catch (error) {
        console.error('Failed to save settings:', error);
      }
    }
  };

  // Build change summary for impact modal
  const getChangesSummary = () => {
    const currentProfile = SECURITY_PROFILES.find((p) => p.id === selectedProfile);
    return {
      description: `Security profile: ${currentProfile?.name || selectedProfile}`,
      details: complianceProfile
        ? `With ${complianceProfile.toUpperCase()} compliance requirements`
        : 'Custom configuration',
    };
  };

  return (
    <div className={`h-screen overflow-y-auto bg-surface-50 dark:bg-surface-900 bg-grid-dot ${className}`}>
      {/* Header */}
      <div className="bg-white dark:bg-surface-800 border-b border-surface-200 dark:border-surface-700">
        <div className="max-w-[1800px] mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl lg:text-3xl font-bold text-surface-900 dark:text-surface-50">
                Guardrail Settings
              </h1>
              <p className="text-sm text-surface-500 dark:text-surface-400">
                Configure how Aura balances autonomy and human oversight
              </p>
            </div>

            <div className="flex items-center gap-3">
              {/* Save success indicator */}
              {saveSuccess && (
                <div className="flex items-center gap-2 text-olive-600 dark:text-olive-400">
                  <CheckCircleIcon className="w-5 h-5" />
                  <span className="text-sm font-medium">Saved</span>
                </div>
              )}

              {/* Save button */}
              <button
                onClick={handleSaveClick}
                disabled={!hasChanges}
                className="px-4 py-2 text-sm font-medium
                           bg-aura-500 text-white rounded-lg
                           hover:bg-aura-600 transition-colors
                           disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main content with bottom padding for chat assistant */}
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6 pb-32 space-y-6">

      {/* Compliance badge (if active) */}
      {complianceProfile && (
        <ComplianceProfileBadge
          profile={complianceProfile}
          lockedSettingsCount={Object.keys(getLockedSettings()).length / 2}
          lockedSettings={Object.keys(getLockedSettings()).filter(
            (k) => !k.endsWith('Reason')
          )}
        />
      )}

      {/* Compliance profile selector */}
      <ComplianceProfileSelector
        value={complianceProfile}
        onChange={handleComplianceChange}
        className="max-w-md"
      />

      {/* Security profile selection */}
      <SecurityProfileSelector
        selectedProfile={selectedProfile}
        onProfileChange={handleProfileChange}
        lockedProfiles={getLockedProfiles()}
        lockedReasons={{
          efficient: 'Locked by compliance requirements',
          aggressive: 'Locked by compliance requirements',
        }}
        showHelp={false}
      />

      {/* Advanced settings */}
      <AdvancedGuardrailSettings
        settings={advancedSettings}
        onSettingsChange={setAdvancedSettings}
        lockedSettings={getLockedSettings()}
      />

      {/* Activity dashboard */}
      <GuardrailActivityDashboard
        metrics={metrics}
        timeRange={metricsTimeRange}
        onTimeRangeChange={setMetricsTimeRange}
        onRefresh={loadMetrics}
        isLoading={isLoadingMetrics}
      />

      {/* Impact preview modal */}
      <ImpactPreviewModal
        isOpen={showImpactModal}
        onClose={() => setShowImpactModal(false)}
        onConfirm={handleConfirmSave}
        changesSummary={getChangesSummary()}
        projectedMetrics={impactPreview?.metrics || [
          {
            label: 'Daily HITL prompts',
            before: 12,
            after: 5,
            inverted: true,
          },
          {
            label: 'Auto-approved operations',
            before: 847,
            after: 891,
          },
          {
            label: 'Quarantined items',
            before: 3,
            after: 8,
          },
          {
            label: 'Avg decision latency',
            before: 2.3,
            after: 1.1,
            inverted: true,
            format: 'time',
          },
        ]}
        warnings={impactPreview?.warnings || []}
        isLoading={isLoadingImpact}
      />
      </div>
    </div>
  );
}

GuardrailSettings.propTypes = {
  initialSettings: PropTypes.shape({
    profile: PropTypes.string,
    complianceProfile: PropTypes.string,
    advanced: PropTypes.object,
  }),
  onSave: PropTypes.func,
  onBack: PropTypes.func,
  fetchMetrics: PropTypes.func,
  fetchImpactPreview: PropTypes.func,
  className: PropTypes.string,
};

export default GuardrailSettings;
