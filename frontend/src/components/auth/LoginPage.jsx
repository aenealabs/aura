/**
 * Login Page Component
 *
 * Email/password authentication form with:
 * - Remember me functionality
 * - Forgot password link
 * - Sign up link
 * - MFA support
 * - New password challenge support
 */

import { useState, useEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { isDevMode } from '../../config/cognito';
import AuthLayout, {
  FormInput,
  FormCheckbox,
  SubmitButton,
  Alert,
  Divider,
} from './AuthLayout';
import SsoLoginButtons from './SsoLoginButtons';
import {
  ShieldCheckIcon,
  LockClosedIcon,
  KeyIcon,
} from '@heroicons/react/24/outline';

const LoginPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const {
    signIn,
    verifyMfa,
    setNewPassword,
    loading,
    error,
    clearError,
    isAuthenticated,
    pendingChallenge,
    getRememberedEmail,
    checkRememberMe: _checkRememberMe,
  } = useAuth();

  // Form state
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  // MFA state
  const [mfaCode, setMfaCode] = useState('');

  // New password state (local form values - not to be confused with auth context's setNewPassword)
  const [newPasswordValue, setNewPasswordValue] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');

  // Local error state
  const [formError, setFormError] = useState('');

  // Get redirect destination
  const from = location.state?.from?.pathname || '/';

  // Initialize with remembered email
  useEffect(() => {
    const rememberedEmail = getRememberedEmail();
    if (rememberedEmail) {
      setEmail(rememberedEmail);
      setRememberMe(true);
    }
  }, [getRememberedEmail]);

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, navigate, from]);

  // Clear errors on input change (intentionally omit error/clearError to avoid loops)
  useEffect(() => {
    if (error || formError) {
      clearError();
      setFormError('');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [email, password, mfaCode, newPasswordValue, confirmNewPassword]);

  /**
   * Handle login form submission
   */
  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError('');

    // Validate inputs
    if (!email.trim()) {
      setFormError('Please enter your email address');
      return;
    }

    if (!password) {
      setFormError('Please enter your password');
      return;
    }

    try {
      const result = await signIn(email.trim(), password, rememberMe);

      if (result.success) {
        navigate(from, { replace: true });
      }
      // MFA and new password challenges are handled by pendingChallenge state
    } catch (err) {
      // Error is set in context
    }
  };

  /**
   * Handle MFA verification
   */
  const handleMfaSubmit = async (e) => {
    e.preventDefault();
    setFormError('');

    if (!mfaCode.trim() || mfaCode.length !== 6) {
      setFormError('Please enter a valid 6-digit verification code');
      return;
    }

    try {
      const result = await verifyMfa(mfaCode.trim());

      if (result.success) {
        navigate(from, { replace: true });
      }
    } catch (err) {
      // Error is set in context
    }
  };

  /**
   * Handle new password submission
   */
  const handleNewPasswordSubmit = async (e) => {
    e.preventDefault();
    setFormError('');

    if (!newPasswordValue) {
      setFormError('Please enter a new password');
      return;
    }

    if (newPasswordValue.length < 12) {
      setFormError('Password must be at least 12 characters long');
      return;
    }

    if (newPasswordValue !== confirmNewPassword) {
      setFormError('Passwords do not match');
      return;
    }

    try {
      const result = await setNewPassword(newPasswordValue);

      if (result.success) {
        navigate(from, { replace: true });
      }
    } catch (err) {
      // Error is set in context
    }
  };

  // Security features list
  const features = [
    {
      icon: ShieldCheckIcon,
      title: 'Enterprise Security',
      description: 'CMMC Level 2 compliant authentication with MFA support',
    },
    {
      icon: LockClosedIcon,
      title: 'Secure Access',
      description: 'Role-based access control for HITL approvals',
    },
    {
      icon: KeyIcon,
      title: 'Enterprise SSO',
      description: 'SAML, OIDC, LDAP, PingID, and Cognito supported',
    },
  ];

  // Render MFA challenge form
  if (pendingChallenge?.type === 'MFA') {
    return (
      <AuthLayout
        title="Two-Factor Authentication"
        subtitle="Enter the verification code from your authenticator app"
        showBackToLogin={false}
      >
        {/* Error Message */}
        {(error || formError) && (
          <Alert
            type="error"
            message={error || formError}
            onDismiss={clearError}
            className="mb-4"
          />
        )}

        <form onSubmit={handleMfaSubmit} className="space-y-4">
          <FormInput
            name="mfaCode"
            type="text"
            label="Verification Code"
            value={mfaCode}
            onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
            placeholder="000000"
            autoComplete="one-time-code"
            required
            className="text-center"
          />

          <SubmitButton loading={loading}>
            <LockClosedIcon className="w-5 h-5" />
            <span>Verify</span>
          </SubmitButton>
        </form>

        <div className="mt-4 text-center">
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="text-sm text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300"
          >
            Start over
          </button>
        </div>
      </AuthLayout>
    );
  }

  // Render new password challenge form
  if (pendingChallenge?.type === 'NEW_PASSWORD') {
    return (
      <AuthLayout
        title="Set New Password"
        subtitle="Your temporary password has expired. Please set a new password."
        showBackToLogin={false}
      >
        {/* Error Message */}
        {(error || formError) && (
          <Alert
            type="error"
            message={error || formError}
            onDismiss={clearError}
            className="mb-4"
          />
        )}

        <form onSubmit={handleNewPasswordSubmit} className="space-y-4">
          <FormInput
            name="newPassword"
            type="password"
            label="New Password"
            value={newPasswordValue}
            onChange={(e) => setNewPasswordValue(e.target.value)}
            placeholder="Enter new password"
            autoComplete="new-password"
            required
          />

          <FormInput
            name="confirmNewPassword"
            type="password"
            label="Confirm New Password"
            value={confirmNewPassword}
            onChange={(e) => setConfirmNewPassword(e.target.value)}
            placeholder="Confirm new password"
            autoComplete="new-password"
            required
          />

          <p className="text-xs text-surface-500 dark:text-surface-400">
            Password must be at least 12 characters and include uppercase, lowercase,
            numbers, and special characters.
          </p>

          <SubmitButton loading={loading}>
            <LockClosedIcon className="w-5 h-5" />
            <span>Set Password</span>
          </SubmitButton>
        </form>

        <div className="mt-4 text-center">
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="text-sm text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300"
          >
            Start over
          </button>
        </div>
      </AuthLayout>
    );
  }

  // Render login form
  return (
    <AuthLayout title="Sign in to continue">
      {/* Error Message */}
      {(error || formError) && (
        <Alert
          type="error"
          message={error || formError}
          onDismiss={() => {
            clearError();
            setFormError('');
          }}
          className="mb-4"
        />
      )}

      {/* SSO Login Options */}
      <SsoLoginButtons
        email={email}
        onError={(msg) => setFormError(msg)}
        className="mb-4"
      />

      {/* Login Form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        <FormInput
          name="email"
          type="email"
          label="Email address"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@company.com"
          autoComplete="email"
          required
        />

        <div className="relative">
          <FormInput
            name="password"
            type={showPassword ? 'text' : 'password'}
            label="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Enter your password"
            autoComplete="current-password"
            required
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute right-3 top-8 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300"
          >
            {showPassword ? (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
              </svg>
            ) : (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
              </svg>
            )}
          </button>
        </div>

        {/* Remember me and Forgot password */}
        <div className="flex items-center justify-between">
          <FormCheckbox
            name="rememberMe"
            label="Remember me"
            checked={rememberMe}
            onChange={(e) => setRememberMe(e.target.checked)}
          />
          <Link
            to="/forgot-password"
            className="text-sm text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300 transition-colors"
          >
            Forgot password?
          </Link>
        </div>

        {/* Submit Button */}
        <SubmitButton loading={loading}>
          <LockClosedIcon className="w-5 h-5" />
          <span>Sign in</span>
        </SubmitButton>
      </form>

      {/* Dev Login Button - Only shown in development mode */}
      {isDevMode && (
        <div className="mt-4">
          <button
            type="button"
            onClick={async () => {
              const mockEmail = import.meta.env.VITE_MOCK_USER_EMAIL || 'dev@aenealabs.com';
              const result = await signIn(mockEmail, 'dev-password', false);
              if (result.success) {
                navigate(from, { replace: true });
              }
            }}
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-warning-500 hover:bg-warning-600 text-white font-medium rounded-xl transition-colors disabled:opacity-50"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
            </svg>
            <span>Dev Login (Skip Auth)</span>
          </button>
          <p className="mt-1 text-xs text-center text-warning-600 dark:text-warning-400">
            Development mode - uses mock authentication
          </p>
        </div>
      )}

      {/* Sign up link */}
      <div className="mt-4 text-center">
        <span className="text-sm text-surface-500 dark:text-surface-400">
          Don't have an account?{' '}
          <Link
            to="/signup"
            className="text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300 font-medium transition-colors"
          >
            Sign up
          </Link>
        </span>
      </div>

      <Divider text="Secure Login" />

      {/* Features */}
      <div className="space-y-3">
        {features.map((feature, index) => (
          <div key={index} className="flex items-start gap-3">
            <feature.icon className="w-5 h-5 text-aura-600 dark:text-aura-400 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm font-medium text-surface-900 dark:text-surface-100">
                {feature.title}
              </p>
              <p className="text-xs text-surface-500 dark:text-surface-400">
                {feature.description}
              </p>
            </div>
          </div>
        ))}
      </div>
    </AuthLayout>
  );
};

export default LoginPage;
