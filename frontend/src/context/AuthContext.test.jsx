import { useEffect } from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { AuthProvider, useAuth } from './AuthContext';

// Mock the authApi module
vi.mock('../services/authApi', () => ({
  signIn: vi.fn(),
  signUp: vi.fn(),
  confirmSignUp: vi.fn(),
  resendConfirmationCode: vi.fn(),
  signOut: vi.fn(),
  forgotPassword: vi.fn(),
  confirmForgotPassword: vi.fn(),
  getCurrentUser: vi.fn(),
  refreshTokens: vi.fn(),
  getSession: vi.fn(),
  changePassword: vi.fn(),
  completeMfaChallenge: vi.fn(),
  completeNewPasswordChallenge: vi.fn(),
  getLastUsername: vi.fn(),
  isRememberMeEnabled: vi.fn(),
}));

// Mock cognito config
vi.mock('../config/cognito', () => ({
  cognitoConfig: {
    tokenRefreshBuffer: 5 * 60 * 1000,
    sessionCheckInterval: 60000,
    idleTimeout: 30 * 60 * 1000,
  },
  isDevMode: true, // Use dev mode to avoid token expiry checks
}));

import * as authApi from '../services/authApi';

// Test component to access auth context
function TestConsumer({ onMount }) {
  const auth = useAuth();

  useEffect(() => {
    if (onMount) onMount(auth);
  }, [onMount, auth]);

  return (
    <div>
      <span data-testid="is-authenticated">{auth.isAuthenticated ? 'true' : 'false'}</span>
      <span data-testid="loading">{auth.loading ? 'true' : 'false'}</span>
      <span data-testid="error">{auth.error || 'none'}</span>
      <span data-testid="user">{auth.user ? JSON.stringify(auth.user) : 'null'}</span>
      <button data-testid="sign-in" onClick={() => auth.signIn('test@example.com', 'password123').catch(() => {})}>
        Sign In
      </button>
      <button data-testid="sign-out" onClick={() => auth.signOut()}>Sign Out</button>
      <button data-testid="sign-up" onClick={() => auth.signUp('new@example.com', 'password123', { name: 'Test' }).catch(() => {})}>
        Sign Up
      </button>
    </div>
  );
}

describe('AuthContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();

    // Default mock implementations
    authApi.getCurrentUser.mockResolvedValue(null);
    authApi.getLastUsername.mockReturnValue(null);
    authApi.isRememberMeEnabled.mockReturnValue(false);
  });

  afterEach(() => {
    vi.clearAllTimers();
    localStorage.clear();
  });

  describe('AuthProvider', () => {
    test('provides auth context to children', async () => {
      authApi.getCurrentUser.mockResolvedValue(null);

      render(
        <AuthProvider>
          <TestConsumer />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('loading')).toHaveTextContent('false');
      });

      expect(screen.getByTestId('is-authenticated')).toBeInTheDocument();
    });

    test('initializes with loading state then completes', async () => {
      authApi.getCurrentUser.mockResolvedValue(null);

      render(
        <AuthProvider>
          <TestConsumer />
        </AuthProvider>
      );

      // After initialization completes
      await waitFor(() => {
        expect(screen.getByTestId('loading')).toHaveTextContent('false');
      });
    });

    test('restores user from existing session', async () => {
      const mockUser = { email: 'test@example.com', role: 'admin' };
      const mockTokens = { accessToken: 'mock-access-token', refreshToken: 'mock-refresh' };

      authApi.getCurrentUser.mockResolvedValue({ user: mockUser, tokens: mockTokens });

      render(
        <AuthProvider>
          <TestConsumer />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('is-authenticated')).toHaveTextContent('true');
      });

      expect(screen.getByTestId('user')).toHaveTextContent('test@example.com');
    });

    test('handles initialization error gracefully', async () => {
      authApi.getCurrentUser.mockRejectedValue(new Error('Session expired'));

      render(
        <AuthProvider>
          <TestConsumer />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('is-authenticated')).toHaveTextContent('false');
        expect(screen.getByTestId('loading')).toHaveTextContent('false');
      });
    });

    test('shows unauthenticated when no session', async () => {
      authApi.getCurrentUser.mockResolvedValue(null);

      render(
        <AuthProvider>
          <TestConsumer />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('is-authenticated')).toHaveTextContent('false');
      });
    });
  });

  describe('signIn', () => {
    test('successfully signs in user', async () => {
      const mockUser = { email: 'test@example.com', role: 'user' };
      const mockTokens = { accessToken: 'mock-token123', refreshToken: 'mock-refresh123' };

      authApi.signIn.mockResolvedValue({ user: mockUser, tokens: mockTokens });
      authApi.getCurrentUser.mockResolvedValue(null);

      render(
        <AuthProvider>
          <TestConsumer />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('loading')).toHaveTextContent('false');
      });

      fireEvent.click(screen.getByTestId('sign-in'));

      await waitFor(() => {
        expect(authApi.signIn).toHaveBeenCalledWith('test@example.com', 'password123', false);
      });

      await waitFor(() => {
        expect(screen.getByTestId('is-authenticated')).toHaveTextContent('true');
      });
    });

    test('handles MFA requirement', async () => {
      authApi.signIn.mockResolvedValue({
        requiresMfa: true,
        cognitoUser: {},
        mfaType: 'SMS_MFA',
      });
      authApi.getCurrentUser.mockResolvedValue(null);

      let capturedAuth;
      render(
        <AuthProvider>
          <TestConsumer onMount={(auth) => { capturedAuth = auth; }} />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('loading')).toHaveTextContent('false');
      });

      fireEvent.click(screen.getByTestId('sign-in'));

      await waitFor(() => {
        expect(capturedAuth.pendingChallenge?.type).toBe('MFA');
      });
    });

    test('handles new password requirement', async () => {
      authApi.signIn.mockResolvedValue({
        requiresNewPassword: true,
        cognitoUser: {},
        userAttributes: { email: 'test@example.com' },
      });
      authApi.getCurrentUser.mockResolvedValue(null);

      let capturedAuth;
      render(
        <AuthProvider>
          <TestConsumer onMount={(auth) => { capturedAuth = auth; }} />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('loading')).toHaveTextContent('false');
      });

      fireEvent.click(screen.getByTestId('sign-in'));

      await waitFor(() => {
        expect(capturedAuth.pendingChallenge?.type).toBe('NEW_PASSWORD');
      });
    });

    test('handles sign in error', async () => {
      authApi.signIn.mockRejectedValue(new Error('Invalid credentials'));
      authApi.getCurrentUser.mockResolvedValue(null);

      render(
        <AuthProvider>
          <TestConsumer />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('loading')).toHaveTextContent('false');
      });

      fireEvent.click(screen.getByTestId('sign-in'));

      await waitFor(() => {
        expect(screen.getByTestId('error')).toHaveTextContent('Invalid credentials');
      });
    });
  });

  describe('signOut', () => {
    test('clears user session on sign out', async () => {
      const mockUser = { email: 'test@example.com' };
      const mockTokens = { accessToken: 'mock-token', refreshToken: 'mock-refresh' };

      authApi.getCurrentUser.mockResolvedValue({ user: mockUser, tokens: mockTokens });
      authApi.signOut.mockResolvedValue(undefined);

      render(
        <AuthProvider>
          <TestConsumer />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('is-authenticated')).toHaveTextContent('true');
      });

      fireEvent.click(screen.getByTestId('sign-out'));

      await waitFor(() => {
        expect(screen.getByTestId('is-authenticated')).toHaveTextContent('false');
      });
    });

    test('handles sign out error gracefully', async () => {
      const mockUser = { email: 'test@example.com' };
      const mockTokens = { accessToken: 'mock-token', refreshToken: 'mock-refresh' };

      authApi.getCurrentUser.mockResolvedValue({ user: mockUser, tokens: mockTokens });
      authApi.signOut.mockRejectedValue(new Error('Network error'));

      render(
        <AuthProvider>
          <TestConsumer />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('is-authenticated')).toHaveTextContent('true');
      });

      fireEvent.click(screen.getByTestId('sign-out'));

      // Should still clear auth even on error
      await waitFor(() => {
        expect(screen.getByTestId('is-authenticated')).toHaveTextContent('false');
      });
    });
  });

  describe('signUp', () => {
    test('successfully registers new user', async () => {
      authApi.signUp.mockResolvedValue({ userConfirmed: false });
      authApi.getCurrentUser.mockResolvedValue(null);

      render(
        <AuthProvider>
          <TestConsumer />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('loading')).toHaveTextContent('false');
      });

      fireEvent.click(screen.getByTestId('sign-up'));

      await waitFor(() => {
        expect(authApi.signUp).toHaveBeenCalledWith(
          'new@example.com',
          'password123',
          { name: 'Test' }
        );
      });
    });

    test('handles sign up error', async () => {
      authApi.signUp.mockRejectedValue(new Error('Email already exists'));
      authApi.getCurrentUser.mockResolvedValue(null);

      render(
        <AuthProvider>
          <TestConsumer />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('loading')).toHaveTextContent('false');
      });

      fireEvent.click(screen.getByTestId('sign-up'));

      await waitFor(() => {
        expect(screen.getByTestId('error')).toHaveTextContent('Email already exists');
      });
    });
  });

  describe('hasRole', () => {
    test('returns true for admin user with any role', async () => {
      const mockUser = { email: 'admin@example.com', role: 'admin' };
      const mockTokens = { accessToken: 'mock-token', refreshToken: 'mock-refresh' };

      authApi.getCurrentUser.mockResolvedValue({ user: mockUser, tokens: mockTokens });

      let capturedAuth;
      render(
        <AuthProvider>
          <TestConsumer onMount={(auth) => { capturedAuth = auth; }} />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('is-authenticated')).toHaveTextContent('true');
      });

      expect(capturedAuth.hasRole('viewer')).toBe(true);
      expect(capturedAuth.hasRole('editor')).toBe(true);
      expect(capturedAuth.hasRole('admin')).toBe(true);
    });

    test('returns false when user is null', async () => {
      authApi.getCurrentUser.mockResolvedValue(null);

      let capturedAuth;
      render(
        <AuthProvider>
          <TestConsumer onMount={(auth) => { capturedAuth = auth; }} />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('loading')).toHaveTextContent('false');
      });

      expect(capturedAuth.hasRole('admin')).toBe(false);
    });

    test('returns true for matching role', async () => {
      const mockUser = { email: 'user@example.com', role: 'editor', groups: [] };
      const mockTokens = { accessToken: 'mock-token', refreshToken: 'mock-refresh' };

      authApi.getCurrentUser.mockResolvedValue({ user: mockUser, tokens: mockTokens });

      let capturedAuth;
      render(
        <AuthProvider>
          <TestConsumer onMount={(auth) => { capturedAuth = auth; }} />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('is-authenticated')).toHaveTextContent('true');
      });

      expect(capturedAuth.hasRole('editor')).toBe(true);
      expect(capturedAuth.hasRole('admin')).toBe(false);
    });

    test('checks role array', async () => {
      const mockUser = { email: 'user@example.com', role: 'viewer' };
      const mockTokens = { accessToken: 'mock-token', refreshToken: 'mock-refresh' };

      authApi.getCurrentUser.mockResolvedValue({ user: mockUser, tokens: mockTokens });

      let capturedAuth;
      render(
        <AuthProvider>
          <TestConsumer onMount={(auth) => { capturedAuth = auth; }} />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('is-authenticated')).toHaveTextContent('true');
      });

      expect(capturedAuth.hasRole(['viewer', 'editor'])).toBe(true);
      expect(capturedAuth.hasRole(['admin', 'superadmin'])).toBe(false);
    });
  });

  describe('useAuth', () => {
    test('throws error when used outside AuthProvider', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      expect(() => {
        render(<TestConsumer />);
      }).toThrow('useAuth must be used within an AuthProvider');

      consoleSpy.mockRestore();
    });
  });

  describe('clearError', () => {
    test('clears error state', async () => {
      authApi.signIn.mockRejectedValue(new Error('Some error'));
      authApi.getCurrentUser.mockResolvedValue(null);

      let capturedAuth;
      render(
        <AuthProvider>
          <TestConsumer onMount={(auth) => { capturedAuth = auth; }} />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('loading')).toHaveTextContent('false');
      });

      fireEvent.click(screen.getByTestId('sign-in'));

      await waitFor(() => {
        expect(screen.getByTestId('error')).toHaveTextContent('Some error');
      });

      // Clear the error
      capturedAuth.clearError();

      await waitFor(() => {
        expect(screen.getByTestId('error')).toHaveTextContent('none');
      });
    });
  });
});
