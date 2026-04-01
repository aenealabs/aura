/**
 * Project Aura - Edition Context
 *
 * Provides edition and license state management for feature gating.
 * See ADR-049: Self-Hosted Deployment Strategy
 */

import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  getEdition,
  getLicense,
  getUsageMetrics,
  getLicenseWarningLevel,
} from '../services/editionApi';

const EditionContext = createContext(null);

const STORAGE_KEYS = {
  EDITION_CACHE: 'aura_edition_cache',
};

const CACHE_TTL = 60 * 60 * 1000; // 1 hour

/**
 * Check if cached edition data is still valid
 */
function isEditionCacheValid() {
  try {
    const cache = localStorage.getItem(STORAGE_KEYS.EDITION_CACHE);
    if (!cache) return false;
    const { cachedAt } = JSON.parse(cache);
    return Date.now() - new Date(cachedAt).getTime() < CACHE_TTL;
  } catch {
    return false;
  }
}

/**
 * Get cached edition data
 */
function getCachedEdition() {
  try {
    const cache = localStorage.getItem(STORAGE_KEYS.EDITION_CACHE);
    if (!cache) return null;
    return JSON.parse(cache);
  } catch {
    return null;
  }
}

/**
 * Save edition data to cache (excludes sensitive data)
 */
function cacheEditionData(edition, license) {
  try {
    const cacheData = {
      edition: edition?.edition,
      features: edition?.features || [],
      featureCount: edition?.feature_count || 0,
      isSelfHosted: edition?.is_self_hosted || false,
      licenseRequired: edition?.license_required || false,
      hasValidLicense: edition?.has_valid_license || false,
      expiresAt: license?.expires_at || null,
      organization: license?.organization || null,
      cachedAt: new Date().toISOString(),
    };
    localStorage.setItem(STORAGE_KEYS.EDITION_CACHE, JSON.stringify(cacheData));
  } catch {
    // Ignore cache errors
  }
}

/**
 * Clear edition cache
 */
function clearEditionCache() {
  try {
    localStorage.removeItem(STORAGE_KEYS.EDITION_CACHE);
  } catch {
    // Ignore
  }
}

export function EditionProvider({ children }) {
  const [edition, setEdition] = useState(null);
  const [license, setLicense] = useState(null);
  const [usageMetrics, setUsageMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Derived state
  const warningLevel = license?.expires_at
    ? getLicenseWarningLevel(license.expires_at)
    : null;

  const isCommunity = edition?.edition === 'community';
  const isEnterprise = edition?.edition === 'enterprise';
  const isEnterprisePlus = edition?.edition === 'enterprise_plus';
  const isSelfHosted = edition?.is_self_hosted || false;

  /**
   * Load edition data from API or cache
   */
  const loadEditionData = useCallback(async (forceRefresh = false) => {
    // Use cache if valid and not forcing refresh
    if (!forceRefresh && isEditionCacheValid()) {
      const cached = getCachedEdition();
      if (cached) {
        setEdition({
          edition: cached.edition,
          features: cached.features,
          feature_count: cached.featureCount,
          is_self_hosted: cached.isSelfHosted,
          license_required: cached.licenseRequired,
          has_valid_license: cached.hasValidLicense,
        });
        setLicense({
          expires_at: cached.expiresAt,
          organization: cached.organization,
        });
        setLoading(false);
        // Still fetch fresh data in background
      }
    }

    try {
      const [editionData, licenseData, metricsData] = await Promise.all([
        getEdition(),
        getLicense().catch(() => null),
        getUsageMetrics().catch(() => null),
      ]);

      setEdition(editionData);
      setLicense(licenseData);
      setUsageMetrics(metricsData);
      setError(null);

      // Cache non-sensitive data
      cacheEditionData(editionData, licenseData);
    } catch (err) {
      setError(err.message);
      console.error('Failed to load edition data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Check if a feature is available
   */
  const hasFeature = useCallback(
    (featureName) => {
      if (!edition?.features) return false;
      return edition.features.includes(featureName);
    },
    [edition]
  );

  /**
   * Check if upgrade is required for a feature
   */
  const requiresUpgrade = useCallback(
    (featureName) => {
      return !hasFeature(featureName);
    },
    [hasFeature]
  );

  /**
   * Refresh edition data (after license activation, etc.)
   */
  const refreshEdition = useCallback(() => {
    clearEditionCache();
    return loadEditionData(true);
  }, [loadEditionData]);

  /**
   * Update license state (after activation)
   */
  const updateLicense = useCallback((newLicense) => {
    setLicense(newLicense);
    // Also update edition if license changed
    loadEditionData(true);
  }, [loadEditionData]);

  // Load data on mount
  useEffect(() => {
    loadEditionData();
  }, [loadEditionData]);

  const value = {
    // State
    edition,
    license,
    usageMetrics,
    loading,
    error,

    // Derived state
    warningLevel,
    isCommunity,
    isEnterprise,
    isEnterprisePlus,
    isSelfHosted,

    // Methods
    hasFeature,
    requiresUpgrade,
    refreshEdition,
    updateLicense,
  };

  return (
    <EditionContext.Provider value={value}>{children}</EditionContext.Provider>
  );
}

/**
 * Hook to access edition context
 */
export function useEdition() {
  const context = useContext(EditionContext);
  if (!context) {
    throw new Error('useEdition must be used within an EditionProvider');
  }
  return context;
}

/**
 * Hook to check if a feature is available (convenience)
 */
export function useFeature(featureName) {
  const { hasFeature, requiresUpgrade, loading } = useEdition();
  return {
    available: hasFeature(featureName),
    requiresUpgrade: requiresUpgrade(featureName),
    loading,
  };
}

export default EditionContext;
