/**
 * Project Aura - Identity Provider API Service
 *
 * API service for managing identity provider configurations.
 * Supports LDAP, SAML, OIDC, PingID, and Cognito providers.
 *
 * ADR-054: Multi-IdP Authentication
 */

import { apiClient, ApiError } from './api';

// Simulated delay for mock responses
const simulateDelay = (ms = 300) => new Promise((resolve) => setTimeout(resolve, ms));

// Check if we should use local/dev mode
const shouldUseLocalMode = () => {
  const apiUrl = import.meta.env.VITE_API_URL;
  return !apiUrl || import.meta.env.DEV;
};

// Local storage key for dev mode
const STORAGE_KEY = 'aura_identity_providers';

// Default providers for development
const DEFAULT_PROVIDERS = [];

/**
 * Get stored providers from localStorage (dev mode)
 */
function getStoredProviders() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : DEFAULT_PROVIDERS;
  } catch {
    return DEFAULT_PROVIDERS;
  }
}

/**
 * Save providers to localStorage (dev mode)
 */
function saveStoredProviders(providers) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(providers));
}

/**
 * IdP Types
 */
export const IDP_TYPES = {
  LDAP: 'ldap',
  SAML: 'saml',
  OIDC: 'oidc',
  PINGID: 'pingid',
  COGNITO: 'cognito',
  ENTRA_ID: 'entra_id',
  AZURE_AD_B2C: 'azure_ad_b2c',
};

/**
 * IdP Type metadata for UI
 */
export const IDP_TYPE_CONFIG = [
  {
    id: 'ldap',
    name: 'LDAP / Active Directory',
    description: 'Enterprise directory services for centralized authentication',
    icon: 'ServerStackIcon',
  },
  {
    id: 'saml',
    name: 'SAML 2.0',
    description: 'Okta, OneLogin, and other SAML providers',
    icon: 'KeyIcon',
  },
  {
    id: 'oidc',
    name: 'OpenID Connect',
    description: 'OAuth 2.0 / OIDC providers like Google, Auth0',
    icon: 'GlobeAltIcon',
  },
  {
    id: 'pingid',
    name: 'PingID',
    description: 'Ping Identity authentication services',
    icon: 'ShieldCheckIcon',
  },
  {
    id: 'cognito',
    name: 'AWS Cognito',
    description: 'Amazon managed user pools and identity',
    icon: 'CloudIcon',
  },
  {
    id: 'entra_id',
    name: 'Microsoft Entra ID',
    description: 'Enterprise SSO (formerly Azure Active Directory)',
    icon: 'EntraIDLogo',
  },
  {
    id: 'azure_ad_b2c',
    name: 'Azure AD B2C',
    description: 'Customer identity with social logins and custom branding',
    icon: 'AzureADB2CLogo',
  },
];

/**
 * Status types for IdP connections
 */
export const IDP_STATUS = {
  CONNECTED: 'connected',
  ERROR: 'error',
  PENDING: 'pending',
  DISABLED: 'disabled',
};

/**
 * Aura roles for group mapping
 */
export const AURA_ROLES = [
  { id: 'admin', label: 'Administrator' },
  { id: 'security-engineer', label: 'Security Engineer' },
  { id: 'devops-engineer', label: 'DevOps Engineer' },
  { id: 'developer', label: 'Developer' },
  { id: 'analyst', label: 'Analyst' },
  { id: 'viewer', label: 'Viewer' },
];

/**
 * Aura user fields for attribute mapping
 */
export const AURA_USER_FIELDS = [
  { id: 'email', label: 'Email', required: true },
  { id: 'first_name', label: 'First Name', required: false },
  { id: 'last_name', label: 'Last Name', required: false },
  { id: 'display_name', label: 'Display Name', required: false },
  { id: 'phone', label: 'Phone Number', required: false },
  { id: 'department', label: 'Department', required: false },
  { id: 'job_title', label: 'Job Title', required: false },
  { id: 'groups', label: 'Groups', required: false },
];

/**
 * Get all identity providers
 */
export async function getIdentityProviders() {
  if (shouldUseLocalMode()) {
    await simulateDelay();
    return getStoredProviders();
  }

  try {
    const { data } = await apiClient.get('/identity/providers');
    return data;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return [];
    }
    throw error;
  }
}

/**
 * Get enabled identity providers (for login page)
 */
export async function getEnabledIdentityProviders() {
  const providers = await getIdentityProviders();
  return providers.filter((p) => p.enabled && p.status === IDP_STATUS.CONNECTED);
}

/**
 * Get a single identity provider by ID
 */
export async function getIdentityProvider(id) {
  if (shouldUseLocalMode()) {
    await simulateDelay();
    const providers = getStoredProviders();
    const provider = providers.find((p) => p.id === id);
    if (!provider) {
      throw new ApiError('Provider not found', 404);
    }
    return provider;
  }

  try {
    const { data } = await apiClient.get(`/identity/providers/${id}`);
    return data;
  } catch (error) {
    throw error;
  }
}

/**
 * Create a new identity provider
 */
export async function createIdentityProvider(config) {
  if (shouldUseLocalMode()) {
    await simulateDelay(500);
    const providers = getStoredProviders();
    const newProvider = {
      id: `idp_${Date.now()}`,
      ...config,
      status: IDP_STATUS.PENDING,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    providers.push(newProvider);
    saveStoredProviders(providers);
    return newProvider;
  }

  try {
    const { data } = await apiClient.post('/identity/providers', config);
    return data;
  } catch (error) {
    throw error;
  }
}

/**
 * Update an existing identity provider
 */
export async function updateIdentityProvider(id, config) {
  if (shouldUseLocalMode()) {
    await simulateDelay(500);
    const providers = getStoredProviders();
    const index = providers.findIndex((p) => p.id === id);
    if (index === -1) {
      throw new ApiError('Provider not found', 404);
    }
    providers[index] = {
      ...providers[index],
      ...config,
      updated_at: new Date().toISOString(),
    };
    saveStoredProviders(providers);
    return providers[index];
  }

  try {
    const { data } = await apiClient.put(`/identity/providers/${id}`, config);
    return data;
  } catch (error) {
    throw error;
  }
}

/**
 * Delete an identity provider
 */
export async function deleteIdentityProvider(id) {
  if (shouldUseLocalMode()) {
    await simulateDelay();
    const providers = getStoredProviders();
    const filtered = providers.filter((p) => p.id !== id);
    saveStoredProviders(filtered);
    return { success: true };
  }

  try {
    await apiClient.delete(`/identity/providers/${id}`);
    return { success: true };
  } catch (error) {
    throw error;
  }
}

/**
 * Test connection to an identity provider
 */
export async function testIdentityProvider(id) {
  if (shouldUseLocalMode()) {
    await simulateDelay(1000);
    const providers = getStoredProviders();
    const provider = providers.find((p) => p.id === id);
    if (!provider) {
      throw new ApiError('Provider not found', 404);
    }
    // Simulate successful test and update status
    provider.status = IDP_STATUS.CONNECTED;
    provider.last_tested = new Date().toISOString();
    saveStoredProviders(providers);
    return {
      success: true,
      message: 'Connection successful',
      latency_ms: Math.floor(Math.random() * 200) + 50,
    };
  }

  try {
    const { data } = await apiClient.post(`/identity/providers/${id}/test`);
    return data;
  } catch (error) {
    throw error;
  }
}

/**
 * Set an identity provider as the default
 */
export async function setDefaultIdentityProvider(id) {
  if (shouldUseLocalMode()) {
    await simulateDelay();
    const providers = getStoredProviders();
    providers.forEach((p) => {
      p.is_default = p.id === id;
    });
    saveStoredProviders(providers);
    return { success: true };
  }

  try {
    const { data } = await apiClient.post(`/identity/providers/${id}/set-default`);
    return data;
  } catch (error) {
    throw error;
  }
}

/**
 * Enable or disable an identity provider
 */
export async function toggleIdentityProvider(id, enabled) {
  if (shouldUseLocalMode()) {
    await simulateDelay();
    const providers = getStoredProviders();
    const provider = providers.find((p) => p.id === id);
    if (!provider) {
      throw new ApiError('Provider not found', 404);
    }
    provider.enabled = enabled;
    provider.status = enabled ? IDP_STATUS.PENDING : IDP_STATUS.DISABLED;
    saveStoredProviders(providers);
    return provider;
  }

  try {
    const { data } = await apiClient.patch(`/identity/providers/${id}`, { enabled });
    return data;
  } catch (error) {
    throw error;
  }
}

/**
 * Get domain routing rules
 */
export async function getDomainRoutes() {
  if (shouldUseLocalMode()) {
    await simulateDelay();
    const stored = localStorage.getItem('aura_domain_routes');
    return stored ? JSON.parse(stored) : [];
  }

  try {
    const { data } = await apiClient.get('/identity/domain-routes');
    return data;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return [];
    }
    throw error;
  }
}

/**
 * Create a domain routing rule
 */
export async function createDomainRoute(route) {
  if (shouldUseLocalMode()) {
    await simulateDelay();
    const routes = JSON.parse(localStorage.getItem('aura_domain_routes') || '[]');
    const newRoute = {
      id: `route_${Date.now()}`,
      ...route,
      created_at: new Date().toISOString(),
    };
    routes.push(newRoute);
    localStorage.setItem('aura_domain_routes', JSON.stringify(routes));
    return newRoute;
  }

  try {
    const { data } = await apiClient.post('/identity/domain-routes', route);
    return data;
  } catch (error) {
    throw error;
  }
}

/**
 * Delete a domain routing rule
 */
export async function deleteDomainRoute(id) {
  if (shouldUseLocalMode()) {
    await simulateDelay();
    const routes = JSON.parse(localStorage.getItem('aura_domain_routes') || '[]');
    const filtered = routes.filter((r) => r.id !== id);
    localStorage.setItem('aura_domain_routes', JSON.stringify(filtered));
    return { success: true };
  }

  try {
    await apiClient.delete(`/identity/domain-routes/${id}`);
    return { success: true };
  } catch (error) {
    throw error;
  }
}

/**
 * Get IdP for a given email domain (for auto-routing)
 */
export async function getProviderForEmail(email) {
  const domain = email.split('@')[1]?.toLowerCase();
  if (!domain) return null;

  const routes = await getDomainRoutes();
  const route = routes.find((r) => r.domain.toLowerCase() === domain);
  if (!route) return null;

  const providers = await getEnabledIdentityProviders();
  return providers.find((p) => p.id === route.provider_id) || null;
}

/**
 * Initiate SSO authentication flow
 */
export async function initiateSsoAuth(providerId) {
  if (shouldUseLocalMode()) {
    await simulateDelay();
    // In dev mode, just return a mock redirect URL
    return {
      redirect_url: `http://localhost:5173/auth/sso/callback?provider=${providerId}&mock=true`,
    };
  }

  try {
    const { data } = await apiClient.post(`/identity/providers/${providerId}/auth`);
    return data;
  } catch (error) {
    throw error;
  }
}

export default {
  getIdentityProviders,
  getEnabledIdentityProviders,
  getIdentityProvider,
  createIdentityProvider,
  updateIdentityProvider,
  deleteIdentityProvider,
  testIdentityProvider,
  setDefaultIdentityProvider,
  toggleIdentityProvider,
  getDomainRoutes,
  createDomainRoute,
  deleteDomainRoute,
  getProviderForEmail,
  initiateSsoAuth,
  IDP_TYPES,
  IDP_TYPE_CONFIG,
  IDP_STATUS,
  AURA_ROLES,
  AURA_USER_FIELDS,
};
