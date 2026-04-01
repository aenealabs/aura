/**
 * Verify Email Page Component
 *
 * Email verification form with:
 * - 6-digit code input
 * - Resend code functionality
 * - Auto-focus and auto-submit
 */

import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import AuthLayout, { SubmitButton, Alert } from './AuthLayout';
import { EnvelopeIcon, CheckCircleIcon } from '@heroicons/react/24/outline';

const VerifyEmailPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { confirmSignUp, resendCode, loading, error, clearError, isAuthenticated } = useAuth();

  // Get email from navigation state
  const email = location.state?.email || '';
  const codeDeliveryDetails = location.state?.codeDeliveryDetails;

  // Form state
  const [code, setCode] = useState(['', '', '', '', '', '']);
  const [success, setSuccess] = useState(false);
  const [resendSuccess, setResendSuccess] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const [formError, setFormError] = useState('');

  // Refs for code inputs
  const inputRefs = useRef([]);

  // Redirect if no email provided
  useEffect(() => {
    if (!email) {
      navigate('/signup', { replace: true });
    }
  }, [email, navigate]);

  // Redirect if authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/', { replace: true });
    }
  }, [isAuthenticated, navigate]);

  // Focus first input on mount
  useEffect(() => {
    if (inputRefs.current[0]) {
      inputRefs.current[0].focus();
    }
  }, []);

  // Resend cooldown timer
  useEffect(() => {
    if (resendCooldown > 0) {
      const timer = setTimeout(() => setResendCooldown(resendCooldown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [resendCooldown]);

  // Clear errors on code change (intentionally omit error/clearError to avoid loops)
  useEffect(() => {
    if (error || formError) {
      clearError();
      setFormError('');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code]);

  /**
   * Handle code input change
   */
  const handleCodeChange = (index, value) => {
    // Only allow digits
    const digit = value.replace(/\D/g, '').slice(-1);

    const newCode = [...code];
    newCode[index] = digit;
    setCode(newCode);

    // Auto-focus next input
    if (digit && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }

    // Auto-submit when complete
    if (digit && index === 5) {
      const fullCode = newCode.join('');
      if (fullCode.length === 6) {
        handleSubmit(null, fullCode);
      }
    }
  };

  /**
   * Handle key down (backspace navigation)
   */
  const handleKeyDown = (index, e) => {
    if (e.key === 'Backspace' && !code[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  /**
   * Handle paste
   */
  const handlePaste = (e) => {
    e.preventDefault();
    const pastedData = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);

    if (pastedData.length > 0) {
      const newCode = [...code];
      for (let i = 0; i < pastedData.length; i++) {
        newCode[i] = pastedData[i];
      }
      setCode(newCode);

      // Focus appropriate input
      const focusIndex = Math.min(pastedData.length, 5);
      inputRefs.current[focusIndex]?.focus();

      // Auto-submit if complete
      if (pastedData.length === 6) {
        handleSubmit(null, pastedData);
      }
    }
  };

  /**
   * Handle form submission
   */
  const handleSubmit = async (e, fullCode = null) => {
    if (e) e.preventDefault();

    const verificationCode = fullCode || code.join('');

    if (verificationCode.length !== 6) {
      setFormError('Please enter a valid 6-digit verification code');
      return;
    }

    try {
      await confirmSignUp(email, verificationCode);
      setSuccess(true);

      // Redirect to login after delay
      setTimeout(() => {
        navigate('/login', {
          state: { message: 'Email verified successfully. You can now sign in.' },
        });
      }, 2000);
    } catch (err) {
      // Reset code on error
      setCode(['', '', '', '', '', '']);
      inputRefs.current[0]?.focus();
    }
  };

  /**
   * Handle resend code
   */
  const handleResendCode = async () => {
    if (resendCooldown > 0) return;

    try {
      await resendCode(email);
      setResendSuccess(true);
      setResendCooldown(60); // 60 second cooldown

      // Clear resend success message after 5 seconds
      setTimeout(() => setResendSuccess(false), 5000);
    } catch (err) {
      // Error is set in context
    }
  };

  // Success state
  if (success) {
    return (
      <AuthLayout>
        <div className="text-center py-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-success-100 dark:bg-success-900/30 rounded-full mb-6">
            <CheckCircleIcon className="w-8 h-8 text-success-600 dark:text-success-400" />
          </div>
          <h2 className="text-xl font-semibold text-surface-900 dark:text-surface-100 mb-2">
            Email Verified!
          </h2>
          <p className="text-surface-600 dark:text-surface-400 mb-4">
            Your email has been successfully verified.
          </p>
          <p className="text-sm text-surface-500 dark:text-surface-400">
            Redirecting to sign in...
          </p>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Verify your email"
      subtitle={
        codeDeliveryDetails
          ? `We sent a verification code to ${codeDeliveryDetails.Destination}`
          : `We sent a verification code to ${email}`
      }
      showBackToLogin
    >
      {/* Email icon */}
      <div className="flex justify-center mb-6">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-aura-100 dark:bg-aura-900/30 rounded-full">
          <EnvelopeIcon className="w-8 h-8 text-aura-600 dark:text-aura-400" />
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

      {/* Resend Success Message */}
      {resendSuccess && (
        <Alert
          type="success"
          message="Verification code resent successfully!"
          className="mb-4"
        />
      )}

      {/* Verification Form */}
      <form onSubmit={handleSubmit}>
        {/* Code inputs */}
        <div className="flex justify-center gap-2 mb-6">
          {code.map((digit, index) => (
            <input
              key={index}
              ref={(el) => (inputRefs.current[index] = el)}
              type="text"
              inputMode="numeric"
              maxLength={1}
              value={digit}
              onChange={(e) => handleCodeChange(index, e.target.value)}
              onKeyDown={(e) => handleKeyDown(index, e)}
              onPaste={handlePaste}
              className={`
                w-12 h-14 text-center text-2xl font-semibold rounded-lg border
                bg-white dark:bg-surface-700
                text-surface-900 dark:text-surface-100
                focus:outline-none focus:ring-2 focus:ring-aura-500 focus:border-transparent
                transition-colors
                ${
                  error || formError
                    ? 'border-critical-300 dark:border-critical-700'
                    : 'border-surface-300 dark:border-surface-600'
                }
              `}
            />
          ))}
        </div>

        {/* Submit Button */}
        <SubmitButton loading={loading}>
          <span>Verify Email</span>
        </SubmitButton>
      </form>

      {/* Resend code */}
      <div className="mt-6 text-center">
        <p className="text-sm text-surface-500 dark:text-surface-400 mb-2">
          Didn't receive the code?
        </p>
        <button
          type="button"
          onClick={handleResendCode}
          disabled={resendCooldown > 0 || loading}
          className={`
            text-sm font-medium transition-colors
            ${
              resendCooldown > 0
                ? 'text-surface-400 dark:text-surface-500 cursor-not-allowed'
                : 'text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300'
            }
          `}
        >
          {resendCooldown > 0
            ? `Resend code in ${resendCooldown}s`
            : 'Resend verification code'}
        </button>
      </div>

      {/* Help text */}
      <div className="mt-6 p-4 bg-surface-50 dark:bg-surface-700/50 rounded-lg">
        <p className="text-xs text-surface-500 dark:text-surface-400 text-center">
          Check your spam folder if you don't see the email.
          The code expires in 24 hours.
        </p>
      </div>
    </AuthLayout>
  );
};

export default VerifyEmailPage;
