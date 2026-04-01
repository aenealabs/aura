/**
 * Reset Password Page Component
 *
 * Password reset completion form with:
 * - Verification code input
 * - New password input with validation
 * - Password strength indicator
 */

import { useState, useEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { validatePassword, validateEmail } from '../../config/cognito';
import AuthLayout, {
  FormInput,
  SubmitButton,
  Alert,
  PasswordStrength,
} from './AuthLayout';
import { LockClosedIcon, CheckCircleIcon } from '@heroicons/react/24/outline';

const ResetPasswordPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { confirmForgotPassword, loading, error, clearError, isAuthenticated } = useAuth();

  // Get email from navigation state
  const initialEmail = location.state?.email || '';

  // Form state
  const [email, setEmail] = useState(initialEmail);
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [success, setSuccess] = useState(false);
  const [formErrors, setFormErrors] = useState({});

  // Redirect if authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/', { replace: true });
    }
  }, [isAuthenticated, navigate]);

  // Clear errors on input change (intentionally omit error/clearError to avoid loops)
  useEffect(() => {
    if (error) {
      clearError();
    }
    if (Object.keys(formErrors).length > 0) {
      setFormErrors({});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [email, code, newPassword, confirmPassword]);

  /**
   * Validate form
   */
  const validateForm = () => {
    const errors = {};

    // Email validation
    if (!email.trim()) {
      errors.email = 'Email is required';
    } else if (!validateEmail(email)) {
      errors.email = 'Please enter a valid email address';
    }

    // Code validation
    if (!code.trim()) {
      errors.code = 'Verification code is required';
    } else if (!/^\d{6}$/.test(code.trim())) {
      errors.code = 'Please enter a valid 6-digit code';
    }

    // Password validation
    if (!newPassword) {
      errors.newPassword = 'New password is required';
    } else {
      const passwordValidation = validatePassword(newPassword);
      if (!passwordValidation.valid) {
        errors.newPassword = passwordValidation.errors[0];
      }
    }

    // Confirm password validation
    if (!confirmPassword) {
      errors.confirmPassword = 'Please confirm your password';
    } else if (newPassword !== confirmPassword) {
      errors.confirmPassword = 'Passwords do not match';
    }

    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  /**
   * Handle form submission
   */
  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    try {
      await confirmForgotPassword(email.trim(), code.trim(), newPassword);
      setSuccess(true);
    } catch (err) {
      // Error is set in context
    }
  };

  // Password requirements list
  const passwordRequirements = [
    { test: (p) => p.length >= 12, text: 'At least 12 characters' },
    { test: (p) => /[A-Z]/.test(p), text: 'One uppercase letter' },
    { test: (p) => /[a-z]/.test(p), text: 'One lowercase letter' },
    { test: (p) => /\d/.test(p), text: 'One number' },
    { test: (p) => /[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]/.test(p), text: 'One special character' },
  ];

  // Success state
  if (success) {
    return (
      <AuthLayout>
        <div className="text-center py-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-success-100 dark:bg-success-900/30 rounded-full mb-6">
            <CheckCircleIcon className="w-8 h-8 text-success-600 dark:text-success-400" />
          </div>
          <h2 className="text-xl font-semibold text-surface-900 dark:text-surface-100 mb-2">
            Password Reset Complete
          </h2>
          <p className="text-surface-600 dark:text-surface-400 mb-6">
            Your password has been successfully reset.
            You can now sign in with your new password.
          </p>
          <Link
            to="/login"
            className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-aura-600 text-white rounded-lg font-medium hover:bg-aura-700 transition-colors"
          >
            <LockClosedIcon className="w-5 h-5" />
            <span>Sign in</span>
          </Link>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Reset your password"
      subtitle="Enter the code we sent you and create a new password"
      showBackToLogin
    >
      {/* Error Message */}
      {error && (
        <Alert
          type="error"
          message={error}
          onDismiss={clearError}
          className="mb-4"
        />
      )}

      {/* Reset Form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Email input (if not provided) */}
        {!initialEmail && (
          <FormInput
            name="email"
            type="email"
            label="Email address"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            autoComplete="email"
            error={formErrors.email}
            required
          />
        )}

        {/* Show email if provided */}
        {initialEmail && (
          <div className="p-3 bg-surface-50 dark:bg-surface-700/50 rounded-lg">
            <p className="text-sm text-surface-500 dark:text-surface-400">
              Resetting password for{' '}
              <span className="font-medium text-surface-900 dark:text-surface-100">
                {email}
              </span>
            </p>
          </div>
        )}

        {/* Verification code */}
        <FormInput
          name="code"
          type="text"
          inputMode="numeric"
          label="Verification code"
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
          placeholder="000000"
          autoComplete="one-time-code"
          error={formErrors.code}
          required
        />

        {/* New password */}
        <div className="relative">
          <FormInput
            name="newPassword"
            type={showPassword ? 'text' : 'password'}
            label="New password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="Create a strong password"
            autoComplete="new-password"
            error={formErrors.newPassword}
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
          <PasswordStrength password={newPassword} />
        </div>

        {/* Password requirements */}
        {newPassword && (
          <div className="text-xs space-y-1">
            {passwordRequirements.map((req, index) => (
              <div
                key={index}
                className={`flex items-center gap-2 ${
                  req.test(newPassword)
                    ? 'text-success-600 dark:text-success-400'
                    : 'text-surface-400 dark:text-surface-500'
                }`}
              >
                {req.test(newPassword) ? (
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                ) : (
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-11a1 1 0 10-2 0v3.586L7.707 9.293a1 1 0 00-1.414 1.414l3 3a1 1 0 001.414 0l3-3a1 1 0 00-1.414-1.414L11 10.586V7z" clipRule="evenodd" />
                  </svg>
                )}
                <span>{req.text}</span>
              </div>
            ))}
          </div>
        )}

        {/* Confirm password */}
        <FormInput
          name="confirmPassword"
          type="password"
          label="Confirm new password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          placeholder="Confirm your new password"
          autoComplete="new-password"
          error={formErrors.confirmPassword}
          required
        />

        {/* Submit Button */}
        <SubmitButton loading={loading}>
          <LockClosedIcon className="w-5 h-5" />
          <span>Reset Password</span>
        </SubmitButton>
      </form>

      {/* Additional options */}
      <div className="mt-6 text-center">
        <p className="text-sm text-surface-500 dark:text-surface-400">
          Didn't receive a code?{' '}
          <Link
            to="/forgot-password"
            className="text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300 font-medium transition-colors"
          >
            Request a new one
          </Link>
        </p>
      </div>
    </AuthLayout>
  );
};

export default ResetPasswordPage;
