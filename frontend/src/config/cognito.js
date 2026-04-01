/**
 * Cognito Configuration
 *
 * AWS Cognito User Pool configuration for production authentication.
 * All sensitive values are loaded from environment variables.
 *
 * Required environment variables:
 *   - VITE_COGNITO_USER_POOL_ID: Cognito User Pool ID (e.g., us-east-1_xxxxxxxxx)
 *   - VITE_COGNITO_CLIENT_ID: App Client ID (no secret required for SPA)
 *   - VITE_COGNITO_REGION: AWS Region (defaults to us-east-1)
 *
 * Optional environment variables:
 *   - VITE_COGNITO_DOMAIN: Cognito domain for hosted UI (required for OAuth flow)
 *   - VITE_REDIRECT_SIGN_IN: OAuth redirect URI after sign-in
 *   - VITE_REDIRECT_SIGN_OUT: OAuth redirect URI after sign-out
 *   - VITE_DEV_MODE: Set to 'true' to enable mock authentication
 */

// Check if development mode is enabled
export const isDevMode = import.meta.env.VITE_DEV_MODE === 'true';

// Check if running on localhost
const isLocalhost = typeof window !== 'undefined' &&
  (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');

/**
 * Get environment variable with validation
 * @param {string} name - Environment variable name
 * @param {string} defaultValue - Default value for development
 * @param {boolean} required - Whether the variable is required in production
 * @returns {string} - The environment variable value
 */
const getEnvVar = (name, defaultValue = '', required = false) => {
  const value = import.meta.env[name];

  if (value) {
    return value;
  }

  // In dev mode, return placeholder values
  if (isDevMode) {
    return defaultValue || 'dev-mode-placeholder';
  }

  // Allow defaults for localhost development
  if (isLocalhost && defaultValue) {
    console.warn(`[Cognito] Using default value for ${name}. Set env var for production.`);
    return defaultValue;
  }

  // Throw error for required variables in production
  if (required && !isLocalhost) {
    throw new Error(
      `Missing required environment variable: ${name}. ` +
      'See frontend/.env.example for required values.'
    );
  }

  return defaultValue;
};

/**
 * Cognito User Pool Configuration
 */
export const cognitoConfig = {
  // User Pool settings
  userPoolId: getEnvVar('VITE_COGNITO_USER_POOL_ID', '', true),
  clientId: getEnvVar('VITE_COGNITO_CLIENT_ID', '', true),
  region: getEnvVar('VITE_COGNITO_REGION', 'us-east-1'),

  // Cognito domain for OAuth/hosted UI
  domain: getEnvVar('VITE_COGNITO_DOMAIN', ''),

  // OAuth redirect URIs
  redirectSignIn: getEnvVar(
    'VITE_REDIRECT_SIGN_IN',
    'http://localhost:5173/auth/callback'
  ),
  redirectSignOut: getEnvVar(
    'VITE_REDIRECT_SIGN_OUT',
    'http://localhost:5173/login'
  ),

  // OAuth scopes
  scopes: ['email', 'openid', 'profile'],

  // OAuth response type
  responseType: 'code',

  // Token refresh settings (in milliseconds)
  tokenRefreshBuffer: 5 * 60 * 1000, // Refresh 5 minutes before expiry
  sessionCheckInterval: 60 * 1000,    // Check session every minute

  // Session timeout settings
  idleTimeout: 30 * 60 * 1000,        // 30 minutes idle timeout
  absoluteTimeout: 12 * 60 * 60 * 1000, // 12 hours absolute timeout

  // Development mode flag
  isDevMode,
};

/**
 * Password policy configuration (should match Cognito User Pool settings)
 */
export const passwordPolicy = {
  minLength: 12,
  requireUppercase: true,
  requireLowercase: true,
  requireNumbers: true,
  requireSymbols: true,
  temporaryPasswordValidityDays: 7,
};

/**
 * Validate password against policy
 * @param {string} password - Password to validate
 * @returns {{ valid: boolean, errors: string[] }} - Validation result
 */
export const validatePassword = (password) => {
  const errors = [];

  if (!password || password.length < passwordPolicy.minLength) {
    errors.push(`Password must be at least ${passwordPolicy.minLength} characters`);
  }

  if (passwordPolicy.requireUppercase && !/[A-Z]/.test(password)) {
    errors.push('Password must contain at least one uppercase letter');
  }

  if (passwordPolicy.requireLowercase && !/[a-z]/.test(password)) {
    errors.push('Password must contain at least one lowercase letter');
  }

  if (passwordPolicy.requireNumbers && !/\d/.test(password)) {
    errors.push('Password must contain at least one number');
  }

  if (passwordPolicy.requireSymbols && !/[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]/.test(password)) {
    errors.push('Password must contain at least one special character');
  }

  return {
    valid: errors.length === 0,
    errors,
  };
};

/**
 * Validate email format
 * @param {string} email - Email to validate
 * @returns {boolean} - Whether email is valid
 */
export const validateEmail = (email) => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
};

/**
 * Get Cognito endpoints
 */
export const getCognitoEndpoints = () => {
  const { userPoolId, region, domain, clientId, redirectSignIn, redirectSignOut, scopes } = cognitoConfig;

  return {
    // Cognito Identity Provider endpoints
    issuer: `https://cognito-idp.${region}.amazonaws.com/${userPoolId}`,
    jwks: `https://cognito-idp.${region}.amazonaws.com/${userPoolId}/.well-known/jwks.json`,
    userInfo: `https://cognito-idp.${region}.amazonaws.com/${userPoolId}/oauth2/userInfo`,

    // OAuth/Hosted UI endpoints (if domain is configured)
    ...(domain && {
      authorize: `https://${domain}/oauth2/authorize`,
      token: `https://${domain}/oauth2/token`,
      logout: `https://${domain}/logout`,
      login: `https://${domain}/login?` + new URLSearchParams({
        client_id: clientId,
        response_type: 'code',
        scope: scopes.join(' '),
        redirect_uri: redirectSignIn,
      }).toString(),
      logoutUrl: `https://${domain}/logout?` + new URLSearchParams({
        client_id: clientId,
        logout_uri: redirectSignOut,
      }).toString(),
    }),
  };
};

/**
 * Error codes and messages for authentication
 */
export const AuthErrorCodes = {
  // Sign-in errors
  UserNotFoundException: 'Account not found. Please check your email or sign up.',
  NotAuthorizedException: 'Incorrect email or password.',
  UserNotConfirmedException: 'Please verify your email before signing in.',
  PasswordResetRequiredException: 'Password reset required. Please reset your password.',

  // Sign-up errors
  UsernameExistsException: 'An account with this email already exists.',
  InvalidPasswordException: 'Password does not meet security requirements.',
  InvalidParameterException: 'Invalid input. Please check your information.',

  // Verification errors
  CodeMismatchException: 'Invalid verification code. Please try again.',
  ExpiredCodeException: 'Verification code has expired. Please request a new code.',
  LimitExceededException: 'Too many attempts. Please wait before trying again.',

  // Session errors
  TokenRefreshException: 'Session expired. Please sign in again.',
  NetworkError: 'Network error. Please check your connection.',

  // Password reset errors
  InvalidPasswordResetCode: 'Invalid or expired password reset code.',

  // MFA errors
  CodeDeliveryFailureException: 'Failed to send verification code. Please try again.',

  // Generic errors
  InternalErrorException: 'An internal error occurred. Please try again later.',
  TooManyRequestsException: 'Too many requests. Please wait before trying again.',
  UnknownError: 'An unexpected error occurred. Please try again.',
};

/**
 * Get user-friendly error message from Cognito error
 * @param {Error} error - Cognito error object
 * @returns {string} - User-friendly error message
 */
export const getAuthErrorMessage = (error) => {
  if (!error) {
    return AuthErrorCodes.UnknownError;
  }

  // Check for network errors
  if (error.message === 'Network request failed' || error.name === 'NetworkError') {
    return AuthErrorCodes.NetworkError;
  }

  // Get error code from Cognito error
  const errorCode = error.code || error.name || '';

  // Return mapped message or the original error message
  return AuthErrorCodes[errorCode] || error.message || AuthErrorCodes.UnknownError;
};

export default cognitoConfig;
