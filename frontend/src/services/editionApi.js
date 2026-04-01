/**
 * Project Aura - Edition API Service
 *
 * Client-side service for edition detection and license management.
 * See ADR-049: Self-Hosted Deployment Strategy
 */

const API_BASE = import.meta.env.VITE_API_URL || '';

// Development mode detection
const isDev = import.meta.env.DEV || !import.meta.env.VITE_API_URL;

// Mock data for development
const MOCK_EDITION_INFO = {
  edition: 'enterprise',
  is_self_hosted: true,
  features: [
    'graphrag_basic',
    'graphrag_advanced',
    'vulnerability_scanning',
    'patch_generation',
    'sandbox_testing',
    'hitl_approval',
    'multi_repo',
    'sso_saml',
    'audit_logging',
    'priority_support',
    'api_access',
    'custom_integrations',
    'advanced_analytics',
    'team_management',
    'role_based_access',
    'webhook_notifications',
    'custom_workflows',
    'code_review_automation',
    'security_dashboards',
    'compliance_reports',
    'agent_customization',
    'model_selection',
    'context_tuning',
    'knowledge_graph_explorer',
  ],
  feature_count: 24,
  license_required: true,
  has_valid_license: true,
};

const MOCK_LICENSE_INFO = {
  license_key: 'AURA...7X4M',
  edition: 'enterprise',
  organization: 'Acme Corporation',
  issued_at: '2025-01-01T00:00:00Z',
  expires_at: new Date(Date.now() + 72 * 24 * 60 * 60 * 1000).toISOString(), // 72 days from now
  features: MOCK_EDITION_INFO.features,
  max_users: 1000,
  max_repositories: 100,
  support_tier: 'premium',
  is_valid: true,
  is_expired: false,
  validation_error: null,
};

const MOCK_USAGE_METRICS = {
  repositories: { used: 12, limit: 100 },
  users: { used: 45, limit: 1000 },
  agents: { used: 3, limit: 10 },
  api_calls: { used: 45000, limit: 100000 },
  storage_gb: { used: 8, limit: 50 },
  agent_hours: { used: 120, limit: 500 },
};

const MOCK_UPGRADE_INFO = {
  current_edition: 'enterprise',
  available_upgrades: [
    {
      edition: 'enterprise_plus',
      name: 'Enterprise Plus',
      price: 'Contact Sales',
      features: [
        'air_gap_deployment',
        'fips_140_2',
        'custom_llm',
        'compliance_reporting',
        'dedicated_support',
        'white_label',
        'on_prem_llm',
        'hardware_security_module',
      ],
      highlights: [
        'Air-gapped deployment support',
        'FIPS 140-2 compliance',
        'Custom LLM integration',
        'Dedicated support engineer',
      ],
    },
  ],
  contact_sales_url: 'https://aenealabs.com/contact-sales',
  pricing_url: 'https://aenealabs.com/pricing',
};

// License warning thresholds (days)
export const LICENSE_WARNING_THRESHOLDS = {
  GENTLE: 60,
  WARNING: 30,
  URGENT: 14,
  CRITICAL: 7,
};

/**
 * Get license warning level based on expiration date
 * @param {string} expiresAt - ISO date string
 * @returns {{ level: string, days: number } | null}
 */
export function getLicenseWarningLevel(expiresAt) {
  if (!expiresAt) return null;

  const now = new Date();
  const expiry = new Date(expiresAt);
  const daysRemaining = Math.ceil((expiry - now) / (1000 * 60 * 60 * 24));

  if (daysRemaining <= 0) return { level: 'expired', days: daysRemaining };
  if (daysRemaining <= LICENSE_WARNING_THRESHOLDS.CRITICAL)
    return { level: 'critical', days: daysRemaining };
  if (daysRemaining <= LICENSE_WARNING_THRESHOLDS.URGENT)
    return { level: 'urgent', days: daysRemaining };
  if (daysRemaining <= LICENSE_WARNING_THRESHOLDS.WARNING)
    return { level: 'warning', days: daysRemaining };
  if (daysRemaining <= LICENSE_WARNING_THRESHOLDS.GENTLE)
    return { level: 'gentle', days: daysRemaining };

  return { level: 'healthy', days: daysRemaining };
}

/**
 * Helper to make API requests
 */
async function apiRequest(endpoint, options = {}) {
  const response = await fetch(`${API_BASE}/api/v1${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `API request failed: ${response.status}`);
  }

  return response.json();
}

/**
 * Get current edition information
 * @returns {Promise<EditionInfo>}
 */
export async function getEdition() {
  if (isDev) {
    return MOCK_EDITION_INFO;
  }
  return apiRequest('/edition');
}

/**
 * Get list of available features
 * @returns {Promise<string[]>}
 */
export async function getFeatures() {
  if (isDev) {
    return MOCK_EDITION_INFO.features;
  }
  return apiRequest('/edition/features');
}

/**
 * Check if a specific feature is available
 * @param {string} featureName - Feature to check
 * @returns {Promise<{ available: boolean, requires_upgrade: boolean }>}
 */
export async function checkFeature(featureName) {
  if (isDev) {
    const available = MOCK_EDITION_INFO.features.includes(featureName);
    return { available, requires_upgrade: !available };
  }
  return apiRequest('/edition/features/check', {
    method: 'POST',
    body: JSON.stringify({ feature: featureName }),
  });
}

/**
 * Get current license information
 * @returns {Promise<LicenseInfo | null>}
 */
export async function getLicense() {
  if (isDev) {
    return MOCK_LICENSE_INFO;
  }
  return apiRequest('/edition/license');
}

/**
 * Validate and activate a license key
 * @param {string} licenseKey - License key to validate
 * @returns {Promise<LicenseInfo>}
 */
export async function activateLicense(licenseKey) {
  if (isDev) {
    // Simulate activation in dev mode
    await new Promise((resolve) => setTimeout(resolve, 1500));
    if (licenseKey.startsWith('AURA-')) {
      return {
        ...MOCK_LICENSE_INFO,
        license_key: `${licenseKey.slice(0, 4)}...${licenseKey.slice(-4)}`,
      };
    }
    throw new Error('Invalid license key format. Expected: AURA-XXX-XXXX-XXXX');
  }
  return apiRequest('/edition/license', {
    method: 'POST',
    body: JSON.stringify({ license_key: licenseKey }),
  });
}

/**
 * Upload and activate a license file (for air-gapped deployments)
 * @param {File} file - License file (.lic)
 * @returns {Promise<LicenseInfo>}
 */
export async function activateLicenseFile(file) {
  if (isDev) {
    await new Promise((resolve) => setTimeout(resolve, 1500));
    return {
      ...MOCK_LICENSE_INFO,
      license_key: 'FILE...XXXX',
    };
  }

  const formData = new FormData();
  formData.append('license_file', file);

  const response = await fetch(`${API_BASE}/api/v1/edition/license/file`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to upload license file');
  }

  return response.json();
}

/**
 * Clear current license (revert to Community)
 * @returns {Promise<void>}
 */
export async function clearLicense() {
  if (isDev) {
    return;
  }
  await apiRequest('/edition/license', { method: 'DELETE' });
}

/**
 * Sync license with vendor portal (online instances only)
 * @returns {Promise<LicenseInfo>}
 */
export async function syncLicense() {
  if (isDev) {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    return MOCK_LICENSE_INFO;
  }
  return apiRequest('/edition/license/sync', { method: 'POST' });
}

/**
 * Get upgrade information
 * @returns {Promise<UpgradeInfo>}
 */
export async function getUpgradeInfo() {
  if (isDev) {
    return MOCK_UPGRADE_INFO;
  }
  return apiRequest('/edition/upgrade-info');
}

/**
 * Get usage metrics
 * @returns {Promise<UsageMetrics>}
 */
export async function getUsageMetrics() {
  if (isDev) {
    return MOCK_USAGE_METRICS;
  }
  return apiRequest('/edition/usage');
}

/**
 * Start a free trial
 * @param {Object} trialInfo - Trial registration info
 * @returns {Promise<LicenseInfo>}
 */
export async function startTrial(trialInfo) {
  if (isDev) {
    await new Promise((resolve) => setTimeout(resolve, 1500));
    return {
      ...MOCK_LICENSE_INFO,
      edition: 'enterprise',
      expires_at: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
      license_key: 'TRIAL...XXXX',
    };
  }
  return apiRequest('/edition/trial', {
    method: 'POST',
    body: JSON.stringify(trialInfo),
  });
}
