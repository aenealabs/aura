/**
 * Forgot Password Page Component
 *
 * Password reset request form with:
 * - Email input
 * - Send reset code functionality
 * - Navigation to reset password page
 */

import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { validateEmail } from '../../config/cognito';
import AuthLayout, { FormInput, SubmitButton, Alert } from './AuthLayout';
import { EnvelopeIcon, KeyIcon } from '@heroicons/react/24/outline';

const ForgotPasswordPage = () => {
  const navigate = useNavigate();
  const { forgotPassword, loading, error, clearError, isAuthenticated } = useAuth();

  // Form state
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [formError, setFormError] = useState('');
  const [codeDeliveryDetails, setCodeDeliveryDetails] = useState(null);

  // Redirect if authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/', { replace: true });
    }
  }, [isAuthenticated, navigate]);

  // Clear errors on input change (intentionally omit error/clearError to avoid loops)
  useEffect(() => {
    if (error || formError) {
      clearError();
      setFormError('');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [email]);

  /**
   * Handle form submission
   */
  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError('');

    // Validate email
    if (!email.trim()) {
      setFormError('Please enter your email address');
      return;
    }

    if (!validateEmail(email)) {
      setFormError('Please enter a valid email address');
      return;
    }

    try {
      const result = await forgotPassword(email.trim());
      setCodeDeliveryDetails(result);
      setSubmitted(true);
    } catch (err) {
      // Error is set in context
    }
  };

  /**
   * Navigate to reset password page
   */
  const handleContinue = () => {
    navigate('/reset-password', {
      state: {
        email: email.trim(),
        codeDeliveryDetails,
      },
    });
  };

  // Success state - code sent
  if (submitted) {
    return (
      <AuthLayout showBackToLogin>
        <div className="text-center">
          {/* Email icon */}
          <div className="flex justify-center mb-6">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-success-100 dark:bg-success-900/30 rounded-full">
              <EnvelopeIcon className="w-8 h-8 text-success-600 dark:text-success-400" />
            </div>
          </div>

          <h2 className="text-xl font-semibold text-surface-900 dark:text-surface-100 mb-2">
            Check your email
          </h2>

          <p className="text-surface-600 dark:text-surface-400 mb-6">
            We sent a password reset code to{' '}
            <span className="font-medium text-surface-900 dark:text-surface-100">
              {codeDeliveryDetails?.Destination || email}
            </span>
          </p>

          <SubmitButton onClick={handleContinue}>
            <KeyIcon className="w-5 h-5" />
            <span>Enter Reset Code</span>
          </SubmitButton>

          <div className="mt-6">
            <button
              type="button"
              onClick={() => setSubmitted(false)}
              className="text-sm text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300 transition-colors"
            >
              Didn't receive the email? Try again
            </button>
          </div>
        </div>

        {/* Help text */}
        <div className="mt-6 p-4 bg-surface-50 dark:bg-surface-700/50 rounded-lg">
          <p className="text-xs text-surface-500 dark:text-surface-400 text-center">
            Check your spam folder if you don't see the email.
            The code expires in 1 hour.
          </p>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Forgot your password?"
      subtitle="Enter your email and we'll send you a reset code"
      showBackToLogin
    >
      {/* Key icon */}
      <div className="flex justify-center mb-6">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-aura-100 dark:bg-aura-900/30 rounded-full">
          <KeyIcon className="w-8 h-8 text-aura-600 dark:text-aura-400" />
        </div>
      </div>

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

      {/* Reset Request Form */}
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

        <SubmitButton loading={loading}>
          <EnvelopeIcon className="w-5 h-5" />
          <span>Send Reset Code</span>
        </SubmitButton>
      </form>

      {/* Additional options */}
      <div className="mt-6 text-center space-y-2">
        <p className="text-sm text-surface-500 dark:text-surface-400">
          Remember your password?{' '}
          <Link
            to="/login"
            className="text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300 font-medium transition-colors"
          >
            Sign in
          </Link>
        </p>
        <p className="text-sm text-surface-500 dark:text-surface-400">
          Already have a reset code?{' '}
          <button
            type="button"
            onClick={() => navigate('/reset-password', { state: { email: email.trim() } })}
            className="text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300 font-medium transition-colors"
          >
            Enter code
          </button>
        </p>
      </div>
    </AuthLayout>
  );
};

export default ForgotPasswordPage;
