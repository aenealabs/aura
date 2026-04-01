/**
 * Authentication API Service
 *
 * Production-ready AWS Cognito authentication service using amazon-cognito-identity-js.
 * Provides all authentication operations including sign-in, sign-up, password management,
 * and session handling.
 *
 * @module services/authApi
 */

import {
  CognitoUserPool,
  CognitoUser,
  AuthenticationDetails,
  CognitoUserAttribute,
} from 'amazon-cognito-identity-js';
import { cognitoConfig, getAuthErrorMessage, isDevMode } from '../config/cognito';

// Storage keys
const STORAGE_KEYS = {
  REMEMBER_ME: 'aura_remember_me',
  LAST_USERNAME: 'aura_last_username',
};

// Initialize Cognito User Pool (only if not in dev mode)
let userPool = null;

const getUserPool = () => {
  if (!userPool && !isDevMode) {
    userPool = new CognitoUserPool({
      UserPoolId: cognitoConfig.userPoolId,
      ClientId: cognitoConfig.clientId,
    });
  }
  return userPool;
};

/**
 * Get a CognitoUser instance for the given email
 * @param {string} email - User's email address
 * @returns {CognitoUser} - Cognito user instance
 */
const getCognitoUser = (email) => {
  const pool = getUserPool();
  if (!pool) {
    throw new Error('User pool not initialized');
  }
  return new CognitoUser({
    Username: email.toLowerCase().trim(),
    Pool: pool,
  });
};

// Mock user for development mode
const createMockUser = (email) => ({
  id: 'dev-user-' + Date.now(),
  email: email || 'dev@aenealabs.com',
  emailVerified: true,
  name: email?.split('@')[0] || 'Developer',
  groups: ['admin', 'security-engineer'],
  role: 'admin',
});

// Mock tokens for development mode
const createMockTokens = () => ({
  accessToken: 'mock-access-token-' + Date.now(),
  idToken: 'mock-id-token-' + Date.now(),
  refreshToken: 'mock-refresh-token-' + Date.now(),
  expiresIn: 3600,
});

/**
 * Sign in with email and password
 *
 * @param {string} email - User's email address
 * @param {string} password - User's password
 * @param {boolean} rememberMe - Whether to persist session across browser restarts
 * @returns {Promise<{ user: object, tokens: object }>} - User info and tokens
 * @throws {Error} - Authentication error with user-friendly message
 */
export const signIn = async (email, password, rememberMe = false) => {
  // Development mode mock
  if (isDevMode) {
    console.warn('[AuthAPI] Dev mode: Simulating sign-in for', email);
    await new Promise(resolve => setTimeout(resolve, 500)); // Simulate network delay

    // Store remember me preference
    if (rememberMe) {
      localStorage.setItem(STORAGE_KEYS.REMEMBER_ME, 'true');
      localStorage.setItem(STORAGE_KEYS.LAST_USERNAME, email);
    } else {
      localStorage.removeItem(STORAGE_KEYS.REMEMBER_ME);
      localStorage.removeItem(STORAGE_KEYS.LAST_USERNAME);
    }

    return {
      user: createMockUser(email),
      tokens: createMockTokens(),
      requiresMfa: false,
      requiresNewPassword: false,
    };
  }

  return new Promise((resolve, reject) => {
    const cognitoUser = getCognitoUser(email);

    const authenticationDetails = new AuthenticationDetails({
      Username: email.toLowerCase().trim(),
      Password: password,
    });

    cognitoUser.authenticateUser(authenticationDetails, {
      onSuccess: (session) => {
        // Store remember me preference
        if (rememberMe) {
          localStorage.setItem(STORAGE_KEYS.REMEMBER_ME, 'true');
          localStorage.setItem(STORAGE_KEYS.LAST_USERNAME, email);
        } else {
          localStorage.removeItem(STORAGE_KEYS.REMEMBER_ME);
          localStorage.removeItem(STORAGE_KEYS.LAST_USERNAME);
        }

        // Extract user attributes from ID token
        const idToken = session.getIdToken();
        const payload = idToken.payload;

        const user = {
          id: payload.sub,
          email: payload.email,
          emailVerified: payload.email_verified,
          name: payload.name || payload.email?.split('@')[0],
          groups: payload['cognito:groups'] || [],
          role: payload['custom:role'] || payload['cognito:groups']?.[0] || 'viewer',
        };

        const tokens = {
          accessToken: session.getAccessToken().getJwtToken(),
          idToken: idToken.getJwtToken(),
          refreshToken: session.getRefreshToken().getToken(),
          expiresIn: session.getAccessToken().getExpiration() - Math.floor(Date.now() / 1000),
        };

        resolve({ user, tokens, requiresMfa: false, requiresNewPassword: false });
      },

      onFailure: (err) => {
        reject(new Error(getAuthErrorMessage(err)));
      },

      newPasswordRequired: (userAttributes, requiredAttributes) => {
        // User needs to set a new password (first-time login with temp password)
        resolve({
          user: null,
          tokens: null,
          requiresMfa: false,
          requiresNewPassword: true,
          userAttributes,
          requiredAttributes,
          cognitoUser,
        });
      },

      mfaRequired: (challengeName, challengeParameters) => {
        // MFA is required
        resolve({
          user: null,
          tokens: null,
          requiresMfa: true,
          requiresNewPassword: false,
          challengeName,
          challengeParameters,
          cognitoUser,
        });
      },

      totpRequired: (challengeName, challengeParameters) => {
        // TOTP MFA is required
        resolve({
          user: null,
          tokens: null,
          requiresMfa: true,
          requiresNewPassword: false,
          mfaType: 'TOTP',
          challengeName,
          challengeParameters,
          cognitoUser,
        });
      },

      mfaSetup: (challengeName, challengeParameters) => {
        // MFA setup is required
        resolve({
          user: null,
          tokens: null,
          requiresMfa: false,
          requiresMfaSetup: true,
          challengeName,
          challengeParameters,
          cognitoUser,
        });
      },
    });
  });
};

/**
 * Complete MFA challenge
 *
 * @param {CognitoUser} cognitoUser - Cognito user from sign-in response
 * @param {string} mfaCode - MFA verification code
 * @param {string} mfaType - MFA type ('SMS_MFA' or 'SOFTWARE_TOKEN_MFA')
 * @returns {Promise<{ user: object, tokens: object }>} - User info and tokens
 */
export const completeMfaChallenge = async (cognitoUser, mfaCode, mfaType = 'SMS_MFA') => {
  if (isDevMode) {
    console.warn('[AuthAPI] Dev mode: Simulating MFA verification');
    await new Promise(resolve => setTimeout(resolve, 500));
    return { user: createMockUser(), tokens: createMockTokens() };
  }

  return new Promise((resolve, reject) => {
    cognitoUser.sendMFACode(
      mfaCode,
      {
        onSuccess: (session) => {
          const idToken = session.getIdToken();
          const payload = idToken.payload;

          const user = {
            id: payload.sub,
            email: payload.email,
            emailVerified: payload.email_verified,
            name: payload.name || payload.email?.split('@')[0],
            groups: payload['cognito:groups'] || [],
            role: payload['custom:role'] || payload['cognito:groups']?.[0] || 'viewer',
          };

          const tokens = {
            accessToken: session.getAccessToken().getJwtToken(),
            idToken: idToken.getJwtToken(),
            refreshToken: session.getRefreshToken().getToken(),
            expiresIn: session.getAccessToken().getExpiration() - Math.floor(Date.now() / 1000),
          };

          resolve({ user, tokens });
        },
        onFailure: (err) => {
          reject(new Error(getAuthErrorMessage(err)));
        },
      },
      mfaType
    );
  });
};

/**
 * Complete new password challenge (first-time login)
 *
 * @param {CognitoUser} cognitoUser - Cognito user from sign-in response
 * @param {string} newPassword - New password to set
 * @param {object} userAttributes - Additional user attributes to set
 * @returns {Promise<{ user: object, tokens: object }>} - User info and tokens
 */
export const completeNewPasswordChallenge = async (cognitoUser, newPassword, userAttributes = {}) => {
  if (isDevMode) {
    console.warn('[AuthAPI] Dev mode: Simulating new password challenge');
    await new Promise(resolve => setTimeout(resolve, 500));
    return { user: createMockUser(), tokens: createMockTokens() };
  }

  return new Promise((resolve, reject) => {
    // Remove read-only attributes that Cognito doesn't allow
    const sanitizedAttributes = { ...userAttributes };
    delete sanitizedAttributes.email_verified;
    delete sanitizedAttributes.phone_number_verified;

    cognitoUser.completeNewPasswordChallenge(newPassword, sanitizedAttributes, {
      onSuccess: (session) => {
        const idToken = session.getIdToken();
        const payload = idToken.payload;

        const user = {
          id: payload.sub,
          email: payload.email,
          emailVerified: payload.email_verified,
          name: payload.name || payload.email?.split('@')[0],
          groups: payload['cognito:groups'] || [],
          role: payload['custom:role'] || payload['cognito:groups']?.[0] || 'viewer',
        };

        const tokens = {
          accessToken: session.getAccessToken().getJwtToken(),
          idToken: idToken.getJwtToken(),
          refreshToken: session.getRefreshToken().getToken(),
          expiresIn: session.getAccessToken().getExpiration() - Math.floor(Date.now() / 1000),
        };

        resolve({ user, tokens });
      },
      onFailure: (err) => {
        reject(new Error(getAuthErrorMessage(err)));
      },
    });
  });
};

/**
 * Sign up a new user
 *
 * @param {string} email - User's email address
 * @param {string} password - User's password (must meet Cognito password policy)
 * @param {object} attributes - Additional user attributes (name, phone_number, etc.)
 * @returns {Promise<{ userSub: string, codeDeliveryDetails: object }>} - Sign-up result
 */
export const signUp = async (email, password, attributes = {}) => {
  if (isDevMode) {
    console.warn('[AuthAPI] Dev mode: Simulating sign-up for', email);
    await new Promise(resolve => setTimeout(resolve, 500));
    return {
      userSub: 'dev-user-' + Date.now(),
      userConfirmed: false,
      codeDeliveryDetails: {
        AttributeName: 'email',
        DeliveryMedium: 'EMAIL',
        Destination: email.replace(/(.{2})(.*)(@.*)/, '$1***$3'),
      },
    };
  }

  return new Promise((resolve, reject) => {
    const pool = getUserPool();
    if (!pool) {
      reject(new Error('User pool not initialized'));
      return;
    }

    // Build attribute list
    const attributeList = [];

    // Email is required
    attributeList.push(
      new CognitoUserAttribute({
        Name: 'email',
        Value: email.toLowerCase().trim(),
      })
    );

    // Add optional attributes
    if (attributes.name) {
      attributeList.push(
        new CognitoUserAttribute({
          Name: 'name',
          Value: attributes.name,
        })
      );
    }

    if (attributes.phone_number) {
      attributeList.push(
        new CognitoUserAttribute({
          Name: 'phone_number',
          Value: attributes.phone_number,
        })
      );
    }

    // Add any custom attributes
    Object.entries(attributes).forEach(([key, value]) => {
      if (key.startsWith('custom:') && value) {
        attributeList.push(
          new CognitoUserAttribute({
            Name: key,
            Value: String(value),
          })
        );
      }
    });

    pool.signUp(
      email.toLowerCase().trim(),
      password,
      attributeList,
      null,
      (err, result) => {
        if (err) {
          reject(new Error(getAuthErrorMessage(err)));
          return;
        }

        resolve({
          userSub: result.userSub,
          userConfirmed: result.userConfirmed,
          codeDeliveryDetails: result.codeDeliveryDetails,
        });
      }
    );
  });
};

/**
 * Confirm sign-up with verification code
 *
 * @param {string} email - User's email address
 * @param {string} code - Verification code from email
 * @returns {Promise<string>} - Success message
 */
export const confirmSignUp = async (email, code) => {
  if (isDevMode) {
    console.warn('[AuthAPI] Dev mode: Simulating email verification for', email);
    await new Promise(resolve => setTimeout(resolve, 500));

    // Simulate invalid code in dev mode (code '000000' fails)
    if (code === '000000') {
      throw new Error('Invalid verification code');
    }

    return 'Email verified successfully';
  }

  return new Promise((resolve, reject) => {
    const cognitoUser = getCognitoUser(email);

    cognitoUser.confirmRegistration(code, true, (err, result) => {
      if (err) {
        reject(new Error(getAuthErrorMessage(err)));
        return;
      }
      resolve(result);
    });
  });
};

/**
 * Resend verification code
 *
 * @param {string} email - User's email address
 * @returns {Promise<object>} - Code delivery details
 */
export const resendConfirmationCode = async (email) => {
  if (isDevMode) {
    console.warn('[AuthAPI] Dev mode: Simulating resend verification code');
    await new Promise(resolve => setTimeout(resolve, 500));
    return {
      AttributeName: 'email',
      DeliveryMedium: 'EMAIL',
      Destination: email.replace(/(.{2})(.*)(@.*)/, '$1***$3'),
    };
  }

  return new Promise((resolve, reject) => {
    const cognitoUser = getCognitoUser(email);

    cognitoUser.resendConfirmationCode((err, result) => {
      if (err) {
        reject(new Error(getAuthErrorMessage(err)));
        return;
      }
      resolve(result.CodeDeliveryDetails);
    });
  });
};

/**
 * Sign out current user
 *
 * @param {boolean} global - If true, signs out from all devices
 * @returns {Promise<void>}
 */
export const signOut = async (global = false) => {
  if (isDevMode) {
    console.warn('[AuthAPI] Dev mode: Simulating sign-out');
    return;
  }

  const pool = getUserPool();
  if (!pool) {
    return;
  }

  const cognitoUser = pool.getCurrentUser();

  if (!cognitoUser) {
    return;
  }

  if (global) {
    return new Promise((resolve, _reject) => {
      cognitoUser.globalSignOut({
        onSuccess: () => resolve(),
        onFailure: (err) => {
          console.warn('[AuthAPI] Global sign-out failed:', err);
          // Fall back to local sign-out
          cognitoUser.signOut();
          resolve();
        },
      });
    });
  }

  cognitoUser.signOut();
};

/**
 * Initiate forgot password flow
 *
 * @param {string} email - User's email address
 * @returns {Promise<object>} - Code delivery details
 */
export const forgotPassword = async (email) => {
  if (isDevMode) {
    console.warn('[AuthAPI] Dev mode: Simulating forgot password for', email);
    await new Promise(resolve => setTimeout(resolve, 500));
    return {
      AttributeName: 'email',
      DeliveryMedium: 'EMAIL',
      Destination: email.replace(/(.{2})(.*)(@.*)/, '$1***$3'),
    };
  }

  return new Promise((resolve, reject) => {
    const cognitoUser = getCognitoUser(email);

    cognitoUser.forgotPassword({
      onSuccess: (data) => {
        resolve(data.CodeDeliveryDetails);
      },
      onFailure: (err) => {
        reject(new Error(getAuthErrorMessage(err)));
      },
    });
  });
};

/**
 * Complete forgot password with verification code and new password
 *
 * @param {string} email - User's email address
 * @param {string} code - Verification code from email
 * @param {string} newPassword - New password
 * @returns {Promise<string>} - Success message
 */
export const confirmForgotPassword = async (email, code, newPassword) => {
  if (isDevMode) {
    console.warn('[AuthAPI] Dev mode: Simulating password reset for', email);
    await new Promise(resolve => setTimeout(resolve, 500));

    // Simulate invalid code in dev mode
    if (code === '000000') {
      throw new Error('Invalid verification code');
    }

    return 'Password reset successfully';
  }

  return new Promise((resolve, reject) => {
    const cognitoUser = getCognitoUser(email);

    cognitoUser.confirmPassword(code, newPassword, {
      onSuccess: () => {
        resolve('Password reset successfully');
      },
      onFailure: (err) => {
        reject(new Error(getAuthErrorMessage(err)));
      },
    });
  });
};

/**
 * Get current authenticated user
 *
 * @returns {Promise<{ user: object, tokens: object } | null>} - User info and tokens or null
 */
export const getCurrentUser = async () => {
  if (isDevMode) {
    // Check if there's a stored dev session
    const storedUser = localStorage.getItem('aura_user');
    const storedTokens = localStorage.getItem('aura_auth_tokens');

    if (storedUser && storedTokens) {
      return {
        user: JSON.parse(storedUser),
        tokens: JSON.parse(storedTokens),
      };
    }

    // Auto-login with mock user in dev mode for easier testing
    console.warn('[AuthAPI] Dev mode: Auto-creating dev user session');
    const mockUser = createMockUser('dev@aenealabs.com');
    const mockTokens = createMockTokens();

    // Persist to localStorage so it survives page reloads
    localStorage.setItem('aura_user', JSON.stringify(mockUser));
    localStorage.setItem('aura_auth_tokens', JSON.stringify(mockTokens));

    return { user: mockUser, tokens: mockTokens };
  }

  const pool = getUserPool();
  if (!pool) {
    return null;
  }

  const cognitoUser = pool.getCurrentUser();

  if (!cognitoUser) {
    return null;
  }

  return new Promise((resolve, _reject) => {
    cognitoUser.getSession((err, session) => {
      if (err || !session || !session.isValid()) {
        resolve(null);
        return;
      }

      const idToken = session.getIdToken();
      const payload = idToken.payload;

      const user = {
        id: payload.sub,
        email: payload.email,
        emailVerified: payload.email_verified,
        name: payload.name || payload.email?.split('@')[0],
        groups: payload['cognito:groups'] || [],
        role: payload['custom:role'] || payload['cognito:groups']?.[0] || 'viewer',
      };

      const tokens = {
        accessToken: session.getAccessToken().getJwtToken(),
        idToken: idToken.getJwtToken(),
        refreshToken: session.getRefreshToken().getToken(),
        expiresIn: session.getAccessToken().getExpiration() - Math.floor(Date.now() / 1000),
      };

      resolve({ user, tokens });
    });
  });
};

/**
 * Refresh access token
 *
 * @returns {Promise<object>} - New tokens
 */
export const refreshTokens = async () => {
  if (isDevMode) {
    console.warn('[AuthAPI] Dev mode: Simulating token refresh');
    await new Promise(resolve => setTimeout(resolve, 200));
    return createMockTokens();
  }

  const pool = getUserPool();
  if (!pool) {
    throw new Error('User pool not initialized');
  }

  const cognitoUser = pool.getCurrentUser();

  if (!cognitoUser) {
    throw new Error('No authenticated user');
  }

  return new Promise((resolve, reject) => {
    cognitoUser.getSession((err, session) => {
      if (err) {
        reject(new Error(getAuthErrorMessage(err)));
        return;
      }

      const refreshToken = session.getRefreshToken();

      cognitoUser.refreshSession(refreshToken, (refreshErr, newSession) => {
        if (refreshErr) {
          reject(new Error(getAuthErrorMessage(refreshErr)));
          return;
        }

        const tokens = {
          accessToken: newSession.getAccessToken().getJwtToken(),
          idToken: newSession.getIdToken().getJwtToken(),
          refreshToken: newSession.getRefreshToken().getToken(),
          expiresIn: newSession.getAccessToken().getExpiration() - Math.floor(Date.now() / 1000),
        };

        resolve(tokens);
      });
    });
  });
};

/**
 * Get current session with tokens
 *
 * @returns {Promise<object | null>} - Session with tokens or null
 */
export const getSession = async () => {
  if (isDevMode) {
    const storedTokens = localStorage.getItem('aura_auth_tokens');
    if (storedTokens) {
      return JSON.parse(storedTokens);
    }
    return null;
  }

  const pool = getUserPool();
  if (!pool) {
    return null;
  }

  const cognitoUser = pool.getCurrentUser();

  if (!cognitoUser) {
    return null;
  }

  return new Promise((resolve) => {
    cognitoUser.getSession((err, session) => {
      if (err || !session || !session.isValid()) {
        resolve(null);
        return;
      }

      const tokens = {
        accessToken: session.getAccessToken().getJwtToken(),
        idToken: session.getIdToken().getJwtToken(),
        refreshToken: session.getRefreshToken().getToken(),
        expiresIn: session.getAccessToken().getExpiration() - Math.floor(Date.now() / 1000),
        isValid: session.isValid(),
      };

      resolve(tokens);
    });
  });
};

/**
 * Change password for current user
 *
 * @param {string} oldPassword - Current password
 * @param {string} newPassword - New password
 * @returns {Promise<string>} - Success message
 */
export const changePassword = async (oldPassword, newPassword) => {
  if (isDevMode) {
    console.warn('[AuthAPI] Dev mode: Simulating password change');
    await new Promise(resolve => setTimeout(resolve, 500));

    // Simulate wrong current password in dev mode
    if (oldPassword === 'wrong') {
      throw new Error('Incorrect current password');
    }

    return 'Password changed successfully';
  }

  const pool = getUserPool();
  if (!pool) {
    throw new Error('User pool not initialized');
  }

  const cognitoUser = pool.getCurrentUser();

  if (!cognitoUser) {
    throw new Error('No authenticated user');
  }

  return new Promise((resolve, reject) => {
    cognitoUser.getSession((sessionErr, session) => {
      if (sessionErr || !session || !session.isValid()) {
        reject(new Error('Session expired. Please sign in again.'));
        return;
      }

      cognitoUser.changePassword(oldPassword, newPassword, (err, _result) => {
        if (err) {
          reject(new Error(getAuthErrorMessage(err)));
          return;
        }
        resolve('Password changed successfully');
      });
    });
  });
};

/**
 * Get user attributes
 *
 * @returns {Promise<object>} - User attributes
 */
export const getUserAttributes = async () => {
  if (isDevMode) {
    return {
      sub: 'dev-user-123',
      email: 'dev@aenealabs.com',
      email_verified: true,
      name: 'Developer',
    };
  }

  const pool = getUserPool();
  if (!pool) {
    throw new Error('User pool not initialized');
  }

  const cognitoUser = pool.getCurrentUser();

  if (!cognitoUser) {
    throw new Error('No authenticated user');
  }

  return new Promise((resolve, reject) => {
    cognitoUser.getSession((sessionErr) => {
      if (sessionErr) {
        reject(new Error(getAuthErrorMessage(sessionErr)));
        return;
      }

      cognitoUser.getUserAttributes((err, attributes) => {
        if (err) {
          reject(new Error(getAuthErrorMessage(err)));
          return;
        }

        const attrs = {};
        attributes.forEach((attr) => {
          attrs[attr.getName()] = attr.getValue();
        });

        resolve(attrs);
      });
    });
  });
};

/**
 * Update user attributes
 *
 * @param {object} attributes - Attributes to update
 * @returns {Promise<string>} - Success message
 */
export const updateUserAttributes = async (attributes) => {
  if (isDevMode) {
    console.warn('[AuthAPI] Dev mode: Simulating attribute update', attributes);
    await new Promise(resolve => setTimeout(resolve, 500));
    return 'Attributes updated successfully';
  }

  const pool = getUserPool();
  if (!pool) {
    throw new Error('User pool not initialized');
  }

  const cognitoUser = pool.getCurrentUser();

  if (!cognitoUser) {
    throw new Error('No authenticated user');
  }

  return new Promise((resolve, reject) => {
    cognitoUser.getSession((sessionErr) => {
      if (sessionErr) {
        reject(new Error(getAuthErrorMessage(sessionErr)));
        return;
      }

      const attributeList = Object.entries(attributes).map(
        ([key, value]) =>
          new CognitoUserAttribute({
            Name: key,
            Value: String(value),
          })
      );

      cognitoUser.updateAttributes(attributeList, (err, _result) => {
        if (err) {
          reject(new Error(getAuthErrorMessage(err)));
          return;
        }
        resolve('Attributes updated successfully');
      });
    });
  });
};

/**
 * Check if "Remember me" is enabled
 *
 * @returns {boolean} - Whether remember me is enabled
 */
export const isRememberMeEnabled = () => {
  return localStorage.getItem(STORAGE_KEYS.REMEMBER_ME) === 'true';
};

/**
 * Get last used username (if remember me is enabled)
 *
 * @returns {string | null} - Last username or null
 */
export const getLastUsername = () => {
  if (isRememberMeEnabled()) {
    return localStorage.getItem(STORAGE_KEYS.LAST_USERNAME);
  }
  return null;
};

/**
 * Clear remember me data
 */
export const clearRememberMe = () => {
  localStorage.removeItem(STORAGE_KEYS.REMEMBER_ME);
  localStorage.removeItem(STORAGE_KEYS.LAST_USERNAME);
};

// Export all functions
export default {
  signIn,
  signUp,
  confirmSignUp,
  resendConfirmationCode,
  signOut,
  forgotPassword,
  confirmForgotPassword,
  getCurrentUser,
  refreshTokens,
  getSession,
  changePassword,
  getUserAttributes,
  updateUserAttributes,
  completeMfaChallenge,
  completeNewPasswordChallenge,
  isRememberMeEnabled,
  getLastUsername,
  clearRememberMe,
};
