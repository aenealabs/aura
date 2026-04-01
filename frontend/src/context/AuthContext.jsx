/**
 * Authentication Context
 *
 * Manages authentication state for the entire application.
 * Provides:
 * - Authentication state (user, tokens, loading, error)
 * - Auto-refresh tokens before expiry
 * - Persist session across page reloads
 * - Handle session timeout gracefully
 * - Role-based access control helpers
 *
 * @module context/AuthContext
 */

import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import {
  signIn as apiSignIn,
  signUp as apiSignUp,
  confirmSignUp as apiConfirmSignUp,
  resendConfirmationCode as apiResendCode,
  signOut as apiSignOut,
  forgotPassword as apiForgotPassword,
  confirmForgotPassword as apiConfirmForgotPassword,
  getCurrentUser,
  refreshTokens as apiRefreshTokens,
  getSession,
  changePassword as apiChangePassword,
  completeMfaChallenge,
  completeNewPasswordChallenge,
  getLastUsername,
  isRememberMeEnabled,
} from '../services/authApi';
import { cognitoConfig, isDevMode } from '../config/cognito';

// Context
const AuthContext = createContext(null);

// Storage keys
const STORAGE_KEYS = {
  TOKENS: 'aura_auth_tokens',
  USER: 'aura_user',
  LAST_ACTIVITY: 'aura_last_activity',
};

/**
 * Parse JWT token payload
 * @param {string} token - JWT token
 * @returns {object | null} - Decoded payload or null
 */
const parseJwt = (token) => {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch {
    return null;
  }
};

/**
 * Check if token is expired
 * @param {string} token - JWT token
 * @returns {boolean} - Whether token is expired
 */
const isTokenExpired = (token) => {
  // Mock tokens never expire in dev mode
  if (isDevMode && token?.startsWith('mock-')) {
    return false;
  }

  const payload = parseJwt(token);
  if (!payload || !payload.exp) return true;

  // Add buffer before actual expiry
  const buffer = cognitoConfig.tokenRefreshBuffer || 5 * 60 * 1000;
  return payload.exp * 1000 < Date.now() + buffer;
};

/**
 * Authentication Provider Component
 */
export const AuthProvider = ({ children }) => {
  // State
  const [user, setUser] = useState(null);
  const [tokens, setTokens] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sessionExpiring, setSessionExpiring] = useState(false);

  // Refs for intervals and timeouts
  const refreshIntervalRef = useRef(null);
  const idleTimeoutRef = useRef(null);
  const absoluteTimeoutRef = useRef(null);

  // Track pending challenges for MFA and new password
  const [pendingChallenge, setPendingChallenge] = useState(null);

  /**
   * Store tokens and user in localStorage
   */
  const persistSession = useCallback((userData, tokenData) => {
    if (userData) {
      localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(userData));
    }
    if (tokenData) {
      localStorage.setItem(STORAGE_KEYS.TOKENS, JSON.stringify(tokenData));
    }
    localStorage.setItem(STORAGE_KEYS.LAST_ACTIVITY, Date.now().toString());
  }, []);

  /**
   * Clear all authentication state
   */
  const clearAuth = useCallback(() => {
    setUser(null);
    setTokens(null);
    setError(null);
    setPendingChallenge(null);
    setSessionExpiring(false);

    localStorage.removeItem(STORAGE_KEYS.TOKENS);
    localStorage.removeItem(STORAGE_KEYS.USER);
    localStorage.removeItem(STORAGE_KEYS.LAST_ACTIVITY);

    // Clear intervals
    if (refreshIntervalRef.current) {
      clearInterval(refreshIntervalRef.current);
      refreshIntervalRef.current = null;
    }
    if (idleTimeoutRef.current) {
      clearTimeout(idleTimeoutRef.current);
      idleTimeoutRef.current = null;
    }
    if (absoluteTimeoutRef.current) {
      clearTimeout(absoluteTimeoutRef.current);
      absoluteTimeoutRef.current = null;
    }
  }, []);

  /**
   * Refresh tokens
   */
  const refreshTokens = useCallback(async () => {
    try {
      const newTokens = await apiRefreshTokens();
      setTokens(newTokens);
      persistSession(null, newTokens);
      return true;
    } catch (err) {
      console.error('[Auth] Token refresh failed:', err);
      setSessionExpiring(true);
      return false;
    }
  }, [persistSession]);

  /**
   * Setup token refresh interval
   */
  const setupTokenRefresh = useCallback(() => {
    // Clear existing interval
    if (refreshIntervalRef.current) {
      clearInterval(refreshIntervalRef.current);
    }

    // Refresh tokens periodically (every minute, check if needed)
    refreshIntervalRef.current = setInterval(async () => {
      if (tokens?.accessToken && isTokenExpired(tokens.accessToken)) {
        await refreshTokens();
      }
    }, cognitoConfig.sessionCheckInterval || 60000);
  }, [tokens, refreshTokens]);

  /**
   * Update last activity timestamp
   */
  const updateActivity = useCallback(() => {
    localStorage.setItem(STORAGE_KEYS.LAST_ACTIVITY, Date.now().toString());
  }, []);

  /**
   * Setup idle timeout
   */
  const setupIdleTimeout = useCallback(() => {
    // Clear existing timeout
    if (idleTimeoutRef.current) {
      clearTimeout(idleTimeoutRef.current);
    }

    // Set idle timeout
    const idleTimeout = cognitoConfig.idleTimeout || 30 * 60 * 1000;
    idleTimeoutRef.current = setTimeout(() => {
      setSessionExpiring(true);
    }, idleTimeout);
  }, []);

  /**
   * Handle user activity
   */
  useEffect(() => {
    if (!user) return;

    const handleActivity = () => {
      updateActivity();
      setupIdleTimeout();
    };

    // Listen for user activity
    const events = ['mousedown', 'keydown', 'touchstart', 'scroll'];
    events.forEach((event) => {
      window.addEventListener(event, handleActivity, { passive: true });
    });

    // Initial setup
    setupIdleTimeout();

    return () => {
      events.forEach((event) => {
        window.removeEventListener(event, handleActivity);
      });
      if (idleTimeoutRef.current) {
        clearTimeout(idleTimeoutRef.current);
      }
    };
  }, [user, updateActivity, setupIdleTimeout]);

  /**
   * Initialize authentication state from storage
   */
  useEffect(() => {
    const initializeAuth = async () => {
      try {
        // Check for existing session
        const result = await getCurrentUser();

        if (result) {
          setUser(result.user);
          setTokens(result.tokens);
          persistSession(result.user, result.tokens);
          setupTokenRefresh();
        }
      } catch (err) {
        console.error('[Auth] Initialization error:', err);
        clearAuth();
      } finally {
        setLoading(false);
      }
    };

    initializeAuth();

    // Cleanup on unmount
    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * Setup token refresh when tokens change
   */
  useEffect(() => {
    if (tokens?.accessToken) {
      setupTokenRefresh();
    }
  }, [tokens, setupTokenRefresh]);

  /**
   * Sign in with email and password
   */
  const signIn = useCallback(async (email, password, rememberMe = false) => {
    setLoading(true);
    setError(null);

    try {
      const result = await apiSignIn(email, password, rememberMe);

      // Handle MFA requirement
      if (result.requiresMfa) {
        setPendingChallenge({
          type: 'MFA',
          cognitoUser: result.cognitoUser,
          mfaType: result.mfaType || 'SMS_MFA',
        });
        setLoading(false);
        return { requiresMfa: true };
      }

      // Handle new password requirement
      if (result.requiresNewPassword) {
        setPendingChallenge({
          type: 'NEW_PASSWORD',
          cognitoUser: result.cognitoUser,
          userAttributes: result.userAttributes,
        });
        setLoading(false);
        return { requiresNewPassword: true };
      }

      // Successful authentication
      setUser(result.user);
      setTokens(result.tokens);
      persistSession(result.user, result.tokens);

      return { success: true };
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [persistSession]);

  /**
   * Complete MFA verification
   */
  const verifyMfa = useCallback(async (code) => {
    if (!pendingChallenge || pendingChallenge.type !== 'MFA') {
      throw new Error('No pending MFA challenge');
    }

    setLoading(true);
    setError(null);

    try {
      const result = await completeMfaChallenge(
        pendingChallenge.cognitoUser,
        code,
        pendingChallenge.mfaType
      );

      setUser(result.user);
      setTokens(result.tokens);
      persistSession(result.user, result.tokens);
      setPendingChallenge(null);

      return { success: true };
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [pendingChallenge, persistSession]);

  /**
   * Complete new password challenge
   */
  const setNewPassword = useCallback(async (newPassword, attributes = {}) => {
    if (!pendingChallenge || pendingChallenge.type !== 'NEW_PASSWORD') {
      throw new Error('No pending new password challenge');
    }

    setLoading(true);
    setError(null);

    try {
      const result = await completeNewPasswordChallenge(
        pendingChallenge.cognitoUser,
        newPassword,
        attributes
      );

      setUser(result.user);
      setTokens(result.tokens);
      persistSession(result.user, result.tokens);
      setPendingChallenge(null);

      return { success: true };
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [pendingChallenge, persistSession]);

  /**
   * Sign up new user
   */
  const signUp = useCallback(async (email, password, attributes = {}) => {
    setLoading(true);
    setError(null);

    try {
      const result = await apiSignUp(email, password, attributes);
      return result;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Confirm sign up with verification code
   */
  const confirmSignUp = useCallback(async (email, code) => {
    setLoading(true);
    setError(null);

    try {
      const result = await apiConfirmSignUp(email, code);
      return result;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Resend verification code
   */
  const resendCode = useCallback(async (email) => {
    setLoading(true);
    setError(null);

    try {
      const result = await apiResendCode(email);
      return result;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Sign out
   */
  const signOut = useCallback(async (global = false) => {
    setLoading(true);

    try {
      await apiSignOut(global);
    } catch (err) {
      console.error('[Auth] Sign out error:', err);
    } finally {
      clearAuth();
      setLoading(false);
    }
  }, [clearAuth]);

  /**
   * Initiate forgot password
   */
  const forgotPassword = useCallback(async (email) => {
    setLoading(true);
    setError(null);

    try {
      const result = await apiForgotPassword(email);
      return result;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Complete forgot password
   */
  const confirmForgotPassword = useCallback(async (email, code, newPassword) => {
    setLoading(true);
    setError(null);

    try {
      const result = await apiConfirmForgotPassword(email, code, newPassword);
      return result;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Change password
   */
  const changePassword = useCallback(async (oldPassword, newPassword) => {
    setLoading(true);
    setError(null);

    try {
      const result = await apiChangePassword(oldPassword, newPassword);
      return result;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Get access token (with auto-refresh if needed)
   */
  const getAccessToken = useCallback(async () => {
    if (!tokens?.accessToken) return null;

    if (isTokenExpired(tokens.accessToken)) {
      const refreshed = await refreshTokens();
      if (refreshed) {
        const session = await getSession();
        return session?.accessToken;
      }
      return null;
    }

    return tokens.accessToken;
  }, [tokens, refreshTokens]);

  /**
   * Check if user has specific role
   */
  const hasRole = useCallback((role) => {
    if (!user) return false;
    if (user.role === 'admin') return true; // Admin has all roles

    if (Array.isArray(role)) {
      return role.some((r) => user.role === r || user.groups?.includes(r));
    }

    return user.role === role || user.groups?.includes(role);
  }, [user]);

  /**
   * Extend session (reset idle timeout)
   */
  const extendSession = useCallback(async () => {
    setSessionExpiring(false);
    setupIdleTimeout();

    // Also refresh tokens to ensure session is fresh
    await refreshTokens();
  }, [setupIdleTimeout, refreshTokens]);

  /**
   * Get remembered username
   */
  const getRememberedEmail = useCallback(() => {
    return getLastUsername();
  }, []);

  /**
   * Check remember me status
   */
  const checkRememberMe = useCallback(() => {
    return isRememberMeEnabled();
  }, []);

  // Computed values
  const isAuthenticated = !!user && !!tokens?.accessToken && !isTokenExpired(tokens.accessToken);

  // Context value
  const value = {
    // State
    user,
    tokens,
    loading,
    error,
    isAuthenticated,
    sessionExpiring,
    pendingChallenge,

    // Auth methods
    signIn,
    signUp,
    confirmSignUp,
    resendCode,
    signOut,
    logout: signOut, // Alias for signOut (used by UserMenu)
    forgotPassword,
    confirmForgotPassword,
    changePassword,

    // Challenge methods
    verifyMfa,
    setNewPassword,

    // Session methods
    getAccessToken,
    refreshTokens,
    extendSession,

    // Role checking
    hasRole,

    // Remember me
    getRememberedEmail,
    checkRememberMe,

    // Clear error
    clearError: () => setError(null),
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

/**
 * Custom hook to use authentication context
 * @returns {object} - Auth context value
 * @throws {Error} - If used outside AuthProvider
 */
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export default AuthContext;
