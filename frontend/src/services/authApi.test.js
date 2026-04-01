import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';

// Create mock instance objects that can be configured per-test
const mockCognitoUserInstance = {
  authenticateUser: vi.fn(),
  confirmRegistration: vi.fn(),
  resendConfirmationCode: vi.fn(),
  forgotPassword: vi.fn(),
  confirmPassword: vi.fn(),
  changePassword: vi.fn(),
  getSession: vi.fn(),
  signOut: vi.fn(),
  globalSignOut: vi.fn(),
  sendMFACode: vi.fn(),
  completeNewPasswordChallenge: vi.fn(),
};

const mockUserPoolInstance = {
  getCurrentUser: vi.fn(),
  signUp: vi.fn(),
};

// Mock amazon-cognito-identity-js with proper class/function syntax
vi.mock('amazon-cognito-identity-js', () => ({
  CognitoUserPool: function MockCognitoUserPool() {
    return mockUserPoolInstance;
  },
  CognitoUser: function MockCognitoUser() {
    return mockCognitoUserInstance;
  },
  AuthenticationDetails: function MockAuthenticationDetails(config) {
    return config;
  },
  CognitoUserAttribute: function MockCognitoUserAttribute(config) {
    return config;
  },
}));

// Mock config - set isDevMode to false to test Cognito path
vi.mock('../config/cognito', () => ({
  cognitoConfig: {
    userPoolId: 'test-pool-id',
    clientId: 'test-client-id',
    region: 'us-east-1',
  },
  getAuthErrorMessage: (err) => err.message || 'Authentication failed',
  isDevMode: false,
}));

describe('authApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    // Reset module to get fresh imports
    vi.resetModules();
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('signIn', () => {
    test('authenticates user successfully', async () => {
      const mockSession = {
        getIdToken: () => ({
          getJwtToken: () => 'id-token',
          payload: {
            sub: 'user-123',
            email: 'test@example.com',
            email_verified: true,
            name: 'Test User',
            'cognito:groups': ['admin'],
          },
        }),
        getAccessToken: () => ({
          getJwtToken: () => 'access-token',
          getExpiration: () => Math.floor(Date.now() / 1000) + 3600,
        }),
        getRefreshToken: () => ({ getToken: () => 'refresh-token' }),
      };

      mockCognitoUserInstance.authenticateUser.mockImplementation((authDetails, callbacks) => {
        callbacks.onSuccess(mockSession);
      });

      const authApi = await import('./authApi');
      const result = await authApi.signIn('test@example.com', 'password123');

      expect(result.tokens).toBeDefined();
      expect(result.tokens.accessToken).toBe('access-token');
      expect(result.user).toBeDefined();
      expect(result.user.email).toBe('test@example.com');
    });

    test('handles MFA required challenge', async () => {
      mockCognitoUserInstance.authenticateUser.mockImplementation((authDetails, callbacks) => {
        callbacks.mfaRequired('SMS_MFA', {});
      });

      const authApi = await import('./authApi');
      const result = await authApi.signIn('test@example.com', 'password123');

      expect(result.requiresMfa).toBe(true);
    });

    test('handles new password required challenge', async () => {
      mockCognitoUserInstance.authenticateUser.mockImplementation((authDetails, callbacks) => {
        callbacks.newPasswordRequired({}, []);
      });

      const authApi = await import('./authApi');
      const result = await authApi.signIn('test@example.com', 'tempPassword');

      expect(result.requiresNewPassword).toBe(true);
    });

    test('handles authentication failure', async () => {
      mockCognitoUserInstance.authenticateUser.mockImplementation((authDetails, callbacks) => {
        callbacks.onFailure({ message: 'Incorrect username or password' });
      });

      const authApi = await import('./authApi');
      await expect(authApi.signIn('test@example.com', 'wrong'))
        .rejects.toThrow('Incorrect username or password');
    });

    test('stores remember me preference', async () => {
      const mockSession = {
        getIdToken: () => ({
          getJwtToken: () => 'id-token',
          payload: {
            sub: 'user-123',
            email: 'test@example.com',
            email_verified: true,
          },
        }),
        getAccessToken: () => ({
          getJwtToken: () => 'access-token',
          getExpiration: () => Math.floor(Date.now() / 1000) + 3600,
        }),
        getRefreshToken: () => ({ getToken: () => 'refresh-token' }),
      };

      mockCognitoUserInstance.authenticateUser.mockImplementation((authDetails, callbacks) => {
        callbacks.onSuccess(mockSession);
      });

      const authApi = await import('./authApi');
      await authApi.signIn('test@example.com', 'password123', true);

      expect(localStorage.getItem('aura_remember_me')).toBe('true');
      expect(localStorage.getItem('aura_last_username')).toBe('test@example.com');
    });
  });

  describe('signUp', () => {
    test('registers new user successfully', async () => {
      mockUserPoolInstance.signUp.mockImplementation((email, password, attributes, validation, callback) => {
        callback(null, {
          userSub: 'new-user-123',
          userConfirmed: false,
          codeDeliveryDetails: { Destination: 'n***@example.com' },
        });
      });

      const authApi = await import('./authApi');
      const result = await authApi.signUp('new@example.com', 'password123', {
        name: 'Test User',
      });

      expect(result.userConfirmed).toBe(false);
      expect(result.userSub).toBe('new-user-123');
    });

    test('handles registration error', async () => {
      mockUserPoolInstance.signUp.mockImplementation((email, password, attributes, validation, callback) => {
        callback({ message: 'User already exists' });
      });

      const authApi = await import('./authApi');
      await expect(authApi.signUp('existing@example.com', 'password123'))
        .rejects.toThrow('User already exists');
    });
  });

  describe('confirmSignUp', () => {
    test('confirms user registration', async () => {
      mockCognitoUserInstance.confirmRegistration.mockImplementation((code, forceAliasCreation, callback) => {
        callback(null, 'SUCCESS');
      });

      const authApi = await import('./authApi');
      const result = await authApi.confirmSignUp('test@example.com', '123456');

      expect(result).toBe('SUCCESS');
    });

    test('handles invalid code', async () => {
      mockCognitoUserInstance.confirmRegistration.mockImplementation((code, forceAliasCreation, callback) => {
        callback({ message: 'Invalid verification code' });
      });

      const authApi = await import('./authApi');
      await expect(authApi.confirmSignUp('test@example.com', 'wrong'))
        .rejects.toThrow('Invalid verification code');
    });
  });

  describe('signOut', () => {
    test('signs out user locally', async () => {
      mockUserPoolInstance.getCurrentUser.mockReturnValue(mockCognitoUserInstance);
      mockCognitoUserInstance.signOut.mockImplementation(() => {});

      const authApi = await import('./authApi');
      await authApi.signOut();

      expect(mockCognitoUserInstance.signOut).toHaveBeenCalled();
    });

    test('signs out user globally when specified', async () => {
      mockUserPoolInstance.getCurrentUser.mockReturnValue(mockCognitoUserInstance);
      mockCognitoUserInstance.globalSignOut.mockImplementation((callbacks) => {
        callbacks.onSuccess();
      });

      const authApi = await import('./authApi');
      await authApi.signOut(true);

      expect(mockCognitoUserInstance.globalSignOut).toHaveBeenCalled();
    });
  });

  describe('forgotPassword', () => {
    test('initiates password reset', async () => {
      mockCognitoUserInstance.forgotPassword.mockImplementation((callbacks) => {
        callbacks.onSuccess({ CodeDeliveryDetails: { Destination: 't***@example.com' } });
      });

      const authApi = await import('./authApi');
      const result = await authApi.forgotPassword('test@example.com');

      expect(result.Destination).toBe('t***@example.com');
    });
  });

  describe('confirmForgotPassword', () => {
    test('resets password with code', async () => {
      mockCognitoUserInstance.confirmPassword.mockImplementation((code, password, callbacks) => {
        callbacks.onSuccess();
      });

      const authApi = await import('./authApi');
      const result = await authApi.confirmForgotPassword(
        'test@example.com',
        '123456',
        'newPassword123'
      );

      expect(result).toBe('Password reset successfully');
    });
  });

  describe('changePassword', () => {
    test('changes password for authenticated user', async () => {
      mockUserPoolInstance.getCurrentUser.mockReturnValue(mockCognitoUserInstance);
      mockCognitoUserInstance.getSession.mockImplementation((callback) => {
        callback(null, { isValid: () => true });
      });
      mockCognitoUserInstance.changePassword.mockImplementation((oldPw, newPw, callback) => {
        callback(null, 'SUCCESS');
      });

      const authApi = await import('./authApi');
      const result = await authApi.changePassword('oldPassword', 'newPassword');

      expect(result).toBe('Password changed successfully');
    });
  });

  describe('getLastUsername', () => {
    test('returns stored username when remember me is enabled', async () => {
      localStorage.setItem('aura_remember_me', 'true');
      localStorage.setItem('aura_last_username', 'stored@example.com');

      const authApi = await import('./authApi');
      const result = authApi.getLastUsername();

      expect(result).toBe('stored@example.com');
    });

    test('returns null when remember me is not enabled', async () => {
      const authApi = await import('./authApi');
      const result = authApi.getLastUsername();

      expect(result).toBeNull();
    });
  });

  describe('isRememberMeEnabled', () => {
    test('returns true when enabled', async () => {
      localStorage.setItem('aura_remember_me', 'true');

      const authApi = await import('./authApi');
      const result = authApi.isRememberMeEnabled();

      expect(result).toBe(true);
    });

    test('returns false when not enabled', async () => {
      const authApi = await import('./authApi');
      const result = authApi.isRememberMeEnabled();

      expect(result).toBe(false);
    });
  });
});
