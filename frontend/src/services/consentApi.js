/**
 * Project Aura - Consent API Service
 *
 * API service for managing GDPR/CCPA consent for AI training participation.
 * Integrates with backend consent_service.py.
 */

const API_BASE = import.meta.env.VITE_API_URL || '';

// Consent types matching backend ConsentType enum
export const ConsentType = {
  TRAINING_DATA: 'training_data',
  SYNTHETIC_BUGS: 'synthetic_bugs',
  MODEL_UPDATES: 'model_updates',
  TELEMETRY: 'telemetry',
  FEEDBACK: 'feedback',
  ANONYMIZED_BENCHMARKS: 'anonymized_benchmarks',
};

// Consent status matching backend ConsentStatus enum
export const ConsentStatus = {
  GRANTED: 'granted',
  DENIED: 'denied',
  WITHDRAWN: 'withdrawn',
  PENDING: 'pending',
  EXPIRED: 'expired',
};

// Consent type configuration for UI display
export const CONSENT_TYPE_CONFIG = {
  [ConsentType.TRAINING_DATA]: {
    label: 'Training Data',
    description: 'Allow failed debugging attempts as anonymous training data',
    details: [
      'Code snippets are stripped of comments, strings, and identifiers',
      'Only structural patterns are retained for training',
      'Data is encrypted at rest and in transit',
      'Retained for 2 years or until consent withdrawal',
    ],
    category: 'training',
    tier: 2, // Requires confirmation modal
    icon: 'CpuChipIcon',
  },
  [ConsentType.SYNTHETIC_BUGS]: {
    label: 'Synthetic Bugs',
    description: 'Generate test scenarios from your codebase patterns',
    details: [
      'Synthetic bugs are created from code patterns, not actual code',
      'Used to train bug-solving agents',
      'No customer code is stored or shared',
      'Improves Aura\'s ability to find similar issues',
    ],
    category: 'training',
    tier: 2,
    icon: 'BugAntIcon',
  },
  [ConsentType.ANONYMIZED_BENCHMARKS]: {
    label: 'Benchmark Reports',
    description: 'Include anonymized metrics in public performance benchmarks',
    details: [
      'Only aggregate statistics are shared',
      'No code or identifying information included',
      'Helps demonstrate Aura\'s effectiveness',
      'Contributes to industry research',
    ],
    category: 'training',
    tier: 2,
    icon: 'ChartBarIcon',
  },
  [ConsentType.TELEMETRY]: {
    label: 'Performance Telemetry',
    description: 'System performance and usage analytics',
    details: [
      'Page load times and API latency',
      'Feature usage patterns',
      'Error rates and crash reports',
      'Helps prioritize improvements',
    ],
    category: 'platform',
    tier: 1, // Immediate toggle
    icon: 'SignalIcon',
  },
  [ConsentType.FEEDBACK]: {
    label: 'User Feedback',
    description: 'Thumbs up/down ratings for AI responses',
    details: [
      'Your explicit feedback on AI quality',
      'Used to improve response accuracy',
      'No code context is stored with feedback',
      'Helps tune model behavior',
    ],
    category: 'platform',
    tier: 1,
    icon: 'HandThumbUpIcon',
  },
  [ConsentType.MODEL_UPDATES]: {
    label: 'Model Updates',
    description: 'Receive AI improvements from aggregate training',
    details: [
      'Get access to improved AI models',
      'Models are trained on aggregate community data',
      'Opt-out means using the baseline model only',
      'No personal data required',
    ],
    category: 'platform',
    tier: 1,
    icon: 'ArrowPathIcon',
  },
};

// Mock data for development mode
const MOCK_CONSENTS = {
  [ConsentType.TRAINING_DATA]: {
    consent_id: 'consent-1',
    customer_id: 'cust-dev-001',
    consent_type: ConsentType.TRAINING_DATA,
    status: ConsentStatus.PENDING,
    legal_basis: 'consent',
    granted_at: null,
    expires_at: null,
    withdrawn_at: null,
  },
  [ConsentType.SYNTHETIC_BUGS]: {
    consent_id: 'consent-2',
    customer_id: 'cust-dev-001',
    consent_type: ConsentType.SYNTHETIC_BUGS,
    status: ConsentStatus.PENDING,
    legal_basis: 'consent',
    granted_at: null,
    expires_at: null,
    withdrawn_at: null,
  },
  [ConsentType.ANONYMIZED_BENCHMARKS]: {
    consent_id: 'consent-3',
    customer_id: 'cust-dev-001',
    consent_type: ConsentType.ANONYMIZED_BENCHMARKS,
    status: ConsentStatus.DENIED,
    legal_basis: 'consent',
    granted_at: null,
    expires_at: null,
    withdrawn_at: null,
  },
  [ConsentType.TELEMETRY]: {
    consent_id: 'consent-4',
    customer_id: 'cust-dev-001',
    consent_type: ConsentType.TELEMETRY,
    status: ConsentStatus.GRANTED,
    legal_basis: 'legitimate_interest',
    granted_at: '2025-12-15T10:00:00Z',
    expires_at: '2027-12-15T10:00:00Z',
    withdrawn_at: null,
  },
  [ConsentType.FEEDBACK]: {
    consent_id: 'consent-5',
    customer_id: 'cust-dev-001',
    consent_type: ConsentType.FEEDBACK,
    status: ConsentStatus.GRANTED,
    legal_basis: 'consent',
    granted_at: '2025-12-15T10:00:00Z',
    expires_at: '2027-12-15T10:00:00Z',
    withdrawn_at: null,
  },
  [ConsentType.MODEL_UPDATES]: {
    consent_id: 'consent-6',
    customer_id: 'cust-dev-001',
    consent_type: ConsentType.MODEL_UPDATES,
    status: ConsentStatus.GRANTED,
    legal_basis: 'contract',
    granted_at: '2025-12-15T10:00:00Z',
    expires_at: '2027-12-15T10:00:00Z',
    withdrawn_at: null,
  },
};

const MOCK_AUDIT_LOG = [
  {
    audit_id: 'audit-1',
    consent_type: ConsentType.TELEMETRY,
    action: 'granted',
    timestamp: '2025-12-15T10:00:00Z',
    ip_address: '192.168.1.1',
    user_agent: 'Mozilla/5.0',
  },
  {
    audit_id: 'audit-2',
    consent_type: ConsentType.FEEDBACK,
    action: 'granted',
    timestamp: '2025-12-15T10:00:00Z',
    ip_address: '192.168.1.1',
    user_agent: 'Mozilla/5.0',
  },
  {
    audit_id: 'audit-3',
    consent_type: ConsentType.MODEL_UPDATES,
    action: 'granted',
    timestamp: '2025-12-15T10:00:00Z',
    ip_address: '192.168.1.1',
    user_agent: 'Mozilla/5.0',
  },
];

// In-memory store for dev mode
let mockConsentsStore = { ...MOCK_CONSENTS };
let mockAuditLogStore = [...MOCK_AUDIT_LOG];

/**
 * Check if we should use local mock data
 */
function shouldUseLocalMode() {
  return import.meta.env.DEV || !API_BASE;
}

/**
 * Get all consent records for the current customer
 */
export async function getConsents() {
  if (shouldUseLocalMode()) {
    return Object.values(mockConsentsStore);
  }

  const response = await fetch(`${API_BASE}/api/v1/consent/`, {
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error('Failed to fetch consents');
  }

  return response.json();
}

/**
 * Get a specific consent record
 */
export async function getConsent(consentType) {
  if (shouldUseLocalMode()) {
    return mockConsentsStore[consentType] || null;
  }

  const response = await fetch(`${API_BASE}/api/v1/consent/${consentType}`, {
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error('Failed to fetch consent');
  }

  return response.json();
}

/**
 * Grant consent for a specific type
 */
export async function grantConsent(consentType) {
  if (shouldUseLocalMode()) {
    const now = new Date().toISOString();
    const expiresAt = new Date(Date.now() + 2 * 365 * 24 * 60 * 60 * 1000).toISOString();

    mockConsentsStore[consentType] = {
      ...mockConsentsStore[consentType],
      status: ConsentStatus.GRANTED,
      granted_at: now,
      expires_at: expiresAt,
      withdrawn_at: null,
    };

    mockAuditLogStore.unshift({
      audit_id: `audit-${Date.now()}`,
      consent_type: consentType,
      action: 'granted',
      timestamp: now,
      ip_address: '127.0.0.1',
      user_agent: navigator.userAgent,
    });

    return mockConsentsStore[consentType];
  }

  const response = await fetch(`${API_BASE}/api/v1/consent/${consentType}/grant`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error('Failed to grant consent');
  }

  return response.json();
}

/**
 * Withdraw consent for a specific type
 */
export async function withdrawConsent(consentType) {
  if (shouldUseLocalMode()) {
    const now = new Date().toISOString();

    mockConsentsStore[consentType] = {
      ...mockConsentsStore[consentType],
      status: ConsentStatus.WITHDRAWN,
      withdrawn_at: now,
    };

    mockAuditLogStore.unshift({
      audit_id: `audit-${Date.now()}`,
      consent_type: consentType,
      action: 'withdrawn',
      timestamp: now,
      ip_address: '127.0.0.1',
      user_agent: navigator.userAgent,
    });

    return mockConsentsStore[consentType];
  }

  const response = await fetch(`${API_BASE}/api/v1/consent/${consentType}/withdraw`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error('Failed to withdraw consent');
  }

  return response.json();
}

/**
 * Withdraw all data contribution consents (training category)
 */
export async function withdrawAllDataConsents() {
  const trainingConsents = [
    ConsentType.TRAINING_DATA,
    ConsentType.SYNTHETIC_BUGS,
    ConsentType.ANONYMIZED_BENCHMARKS,
  ];

  const results = await Promise.all(
    trainingConsents.map(type => withdrawConsent(type))
  );

  return results;
}

/**
 * Get consent audit log
 */
export async function getConsentAuditLog(limit = 10) {
  if (shouldUseLocalMode()) {
    return mockAuditLogStore.slice(0, limit);
  }

  const response = await fetch(`${API_BASE}/api/v1/consent/audit?limit=${limit}`, {
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error('Failed to fetch audit log');
  }

  return response.json();
}

/**
 * Export customer data (GDPR Article 20 - Data Portability)
 */
export async function exportCustomerData() {
  if (shouldUseLocalMode()) {
    return {
      customer_id: 'cust-dev-001',
      export_date: new Date().toISOString(),
      consents: Object.values(mockConsentsStore),
      audit_log: mockAuditLogStore,
    };
  }

  const response = await fetch(`${API_BASE}/api/v1/consent/export`, {
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error('Failed to export data');
  }

  return response.json();
}

/**
 * Request data erasure (GDPR Article 17 - Right to Erasure)
 */
export async function requestDataErasure() {
  if (shouldUseLocalMode()) {
    return {
      request_id: `erasure-${Date.now()}`,
      status: 'pending',
      estimated_completion: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
    };
  }

  const response = await fetch(`${API_BASE}/api/v1/consent/erasure`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error('Failed to request data erasure');
  }

  return response.json();
}

/**
 * Get detected jurisdiction (GDPR, CCPA, or default)
 */
export async function getJurisdiction() {
  if (shouldUseLocalMode()) {
    return { jurisdiction: 'GDPR', country: 'US', region: 'CA' };
  }

  const response = await fetch(`${API_BASE}/api/v1/consent/jurisdiction`, {
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error('Failed to detect jurisdiction');
  }

  return response.json();
}

/**
 * Get current consent version
 */
export function getConsentVersion() {
  return '1.0.0';
}

/**
 * Calculate days until consent expires
 */
export function getDaysUntilExpiry(expiresAt) {
  if (!expiresAt) return null;
  const expiry = new Date(expiresAt);
  const now = new Date();
  const diffMs = expiry - now;
  return Math.ceil(diffMs / (1000 * 60 * 60 * 24));
}

/**
 * Format consent status for display
 */
export function formatConsentStatus(status) {
  const statusMap = {
    [ConsentStatus.GRANTED]: { label: 'Granted', color: 'olive' },
    [ConsentStatus.DENIED]: { label: 'Denied', color: 'surface' },
    [ConsentStatus.WITHDRAWN]: { label: 'Withdrawn', color: 'critical' },
    [ConsentStatus.PENDING]: { label: 'Pending', color: 'warning' },
    [ConsentStatus.EXPIRED]: { label: 'Expired', color: 'surface' },
  };
  return statusMap[status] || { label: status, color: 'surface' };
}
