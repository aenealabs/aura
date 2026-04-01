// Cognito Authentication Configuration
// All values MUST be provided via environment variables - no hardcoded fallbacks
// See docs/FRONTEND_DEV_MODE_RUNBOOK.md for setup instructions

// Check if dev mode is enabled (bypasses Cognito requirement)
const isDevMode = import.meta.env.VITE_DEV_MODE === 'true';

// Helper to get required env var (throws if missing in non-localhost environments)
const getRequiredEnvVar = (name, fallbackForLocalhost = null) => {
  const value = import.meta.env[name];
  if (value) return value;

  // In dev mode, return placeholder - Cognito won't be used anyway
  if (isDevMode) {
    return fallbackForLocalhost || 'dev-mode-placeholder';
  }

  // Allow fallbacks only for localhost development
  const isLocalhost = typeof window !== 'undefined' &&
    (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');

  if (isLocalhost && fallbackForLocalhost) {
    console.warn(`[Auth] Using localhost fallback for ${name}. Set env var for production.`);
    return fallbackForLocalhost;
  }

  throw new Error(`Missing required environment variable: ${name}. See .env.example for required values.`);
};

export const authConfig = {
  // Dev mode flag
  isDevMode,

  // Cognito User Pool - REQUIRED in production, placeholder in dev mode
  userPoolId: getRequiredEnvVar('VITE_COGNITO_USER_POOL_ID'),
  userPoolClientId: getRequiredEnvVar('VITE_COGNITO_CLIENT_ID'),

  // Cognito Domain (for hosted UI) - REQUIRED in production
  domain: getRequiredEnvVar('VITE_COGNITO_DOMAIN'),

  // OAuth configuration
  region: import.meta.env.VITE_AWS_REGION || 'us-east-1',
  redirectSignIn: getRequiredEnvVar('VITE_REDIRECT_SIGN_IN', 'http://localhost:5173/auth/callback'),
  redirectSignOut: getRequiredEnvVar('VITE_REDIRECT_SIGN_OUT', 'http://localhost:5173'),

  // Scopes
  scopes: ['email', 'openid', 'profile'],

  // Response type
  responseType: 'code',
};

// Build OAuth URLs
export const getLoginUrl = () => {
  const params = new URLSearchParams({
    client_id: authConfig.userPoolClientId,
    response_type: authConfig.responseType,
    scope: authConfig.scopes.join(' '),
    redirect_uri: authConfig.redirectSignIn,
  });
  return `https://${authConfig.domain}/login?${params.toString()}`;
};

export const getLogoutUrl = () => {
  const params = new URLSearchParams({
    client_id: authConfig.userPoolClientId,
    logout_uri: authConfig.redirectSignOut,
  });
  return `https://${authConfig.domain}/logout?${params.toString()}`;
};

export const getTokenUrl = () => {
  return `https://${authConfig.domain}/oauth2/token`;
};

// Cognito Issuer URL for JWT validation
export const getIssuerUrl = () => {
  return `https://cognito-idp.${authConfig.region}.amazonaws.com/${authConfig.userPoolId}`;
};

// JWKS URL for public key retrieval
export const getJwksUrl = () => {
  return `${getIssuerUrl()}/.well-known/jwks.json`;
};
