/**
 * Edition Settings Tab Component
 *
 * Main settings tab for edition and license management.
 * See ADR-049: Self-Hosted Deployment Strategy
 */

import { useState, useEffect, useCallback } from 'react';
import {
  getEdition,
  getLicense,
  getUsageMetrics,
  getUpgradeInfo,
  syncLicense,
  getLicenseWarningLevel,
} from '../../services/editionApi';
import {
  ExpirationBanner,
  LicenseStatusCard,
  UsageMetrics,
  UpgradePrompt,
  LicenseActivationPanel,
} from './edition';

export default function EditionSettings({ onSuccess, onError }) {
  const [edition, setEdition] = useState(null);
  const [license, setLicense] = useState(null);
  const [usageMetrics, setUsageMetrics] = useState(null);
  const [_upgradeInfo, setUpgradeInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [showActivation, setShowActivation] = useState(false);

  // Load all data
  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [editionData, licenseData, metricsData, upgradeData] = await Promise.all([
        getEdition(),
        getLicense().catch(() => null),
        getUsageMetrics().catch(() => null),
        getUpgradeInfo().catch(() => null),
      ]);

      setEdition(editionData);
      setLicense(licenseData);
      setUsageMetrics(metricsData);
      setUpgradeInfo(upgradeData);
    } catch (err) {
      onError?.(`Failed to load edition settings: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, [onError]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handle license sync
  const handleSync = async () => {
    setSyncing(true);
    try {
      const updatedLicense = await syncLicense();
      setLicense(updatedLicense);
      onSuccess?.('License synced successfully');
    } catch (err) {
      onError?.(`Failed to sync license: ${err.message}`);
    } finally {
      setSyncing(false);
    }
  };

  // Handle license activation success
  const handleActivationSuccess = (newLicense) => {
    setLicense(newLicense);
    loadData(); // Reload all data to get updated edition info
    onSuccess?.('License activated successfully');
    setShowActivation(false);
  };

  // Handle upgrade click
  const handleUpgrade = (_targetEdition) => {
    // For now, show the activation panel
    setShowActivation(true);
  };

  // Handle contact sales
  const handleContactSales = () => {
    window.open('https://aenealabs.com/contact-sales', '_blank');
  };

  // Handle renew click from expiration banner
  const handleRenew = () => {
    window.open('https://aenealabs.com/renew', '_blank');
  };

  // Calculate warning level
  const warningLevel = license?.expires_at
    ? getLicenseWarningLevel(license.expires_at)
    : null;

  // Loading skeleton
  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="bg-surface-100 dark:bg-surface-700/30 rounded-xl h-48" />
        <div className="bg-surface-100 dark:bg-surface-700/30 rounded-xl h-32" />
        <div className="bg-surface-100 dark:bg-surface-700/30 rounded-xl h-64" />
      </div>
    );
  }

  const isCommunity = edition?.edition === 'community';

  return (
    <div className="space-y-6">
      {/* Expiration Warning Banner */}
      {warningLevel && warningLevel.level !== 'healthy' && (
        <ExpirationBanner
          warningLevel={warningLevel}
          onRenew={handleRenew}
          dismissable={warningLevel.level !== 'expired'}
        />
      )}

      {/* License Status Card */}
      <LicenseStatusCard
        edition={edition}
        license={license}
        onSync={handleSync}
        onManage={() => setShowActivation(!showActivation)}
        syncing={syncing}
      />

      {/* License Activation Panel */}
      {(showActivation || isCommunity) && (
        <LicenseActivationPanel
          onSuccess={handleActivationSuccess}
          onError={onError}
          defaultExpanded={isCommunity}
          showTrial={isCommunity}
        />
      )}

      {/* Usage Metrics (only for licensed editions) */}
      {!isCommunity && usageMetrics && (
        <UsageMetrics metrics={usageMetrics} />
      )}

      {/* Upgrade Prompt */}
      {edition?.edition !== 'enterprise_plus' && (
        <UpgradePrompt
          currentEdition={edition?.edition}
          onUpgrade={handleUpgrade}
          onContactSales={handleContactSales}
        />
      )}

      {/* Additional Info for Enterprise Plus */}
      {edition?.edition === 'enterprise_plus' && (
        <div className="bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-900/20 dark:to-orange-900/20 rounded-xl border border-amber-200 dark:border-amber-800 p-6">
          <h3 className="text-lg font-semibold text-amber-900 dark:text-amber-100 mb-2">
            Enterprise Plus Features
          </h3>
          <p className="text-sm text-amber-700 dark:text-amber-300">
            You have access to all premium features including air-gap deployment,
            FIPS 140-2 compliance, custom LLM integration, and dedicated support.
          </p>
          <a
            href="https://aenealabs.com/docs/enterprise-plus"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block mt-4 text-sm font-medium text-amber-800 dark:text-amber-200 hover:underline"
          >
            View Enterprise Plus Documentation →
          </a>
        </div>
      )}
    </div>
  );
}
