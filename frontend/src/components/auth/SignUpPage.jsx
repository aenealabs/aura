/**
 * Sign Up Page Component
 *
 * New user registration form with:
 * - Email and password inputs
 * - Password strength indicator
 * - Name field
 * - Password policy validation
 * - Terms acceptance
 */

import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { validatePassword, validateEmail } from '../../config/cognito';
import AuthLayout, {
  FormInput,
  FormCheckbox,
  SubmitButton,
  Alert,
  PasswordStrength,
} from './AuthLayout';
import { UserPlusIcon } from '@heroicons/react/24/outline';

const SignUpPage = () => {
  const navigate = useNavigate();
  const { signUp, loading, error, clearError, isAuthenticated } = useAuth();

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [formErrors, setFormErrors] = useState({});
  const [_submitted, setSubmitted] = useState(false);

  // Redirect if already authenticated
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
  }, [formData.email, formData.password, formData.confirmPassword, formData.name]);

  /**
   * Handle input change
   */
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  /**
   * Validate form
   */
  const validateForm = () => {
    const errors = {};

    // Name validation
    if (!formData.name.trim()) {
      errors.name = 'Name is required';
    } else if (formData.name.trim().length < 2) {
      errors.name = 'Name must be at least 2 characters';
    }

    // Email validation
    if (!formData.email.trim()) {
      errors.email = 'Email is required';
    } else if (!validateEmail(formData.email)) {
      errors.email = 'Please enter a valid email address';
    }

    // Password validation
    if (!formData.password) {
      errors.password = 'Password is required';
    } else {
      const passwordValidation = validatePassword(formData.password);
      if (!passwordValidation.valid) {
        errors.password = passwordValidation.errors[0];
      }
    }

    // Confirm password validation
    if (!formData.confirmPassword) {
      errors.confirmPassword = 'Please confirm your password';
    } else if (formData.password !== formData.confirmPassword) {
      errors.confirmPassword = 'Passwords do not match';
    }

    // Terms acceptance
    if (!acceptTerms) {
      errors.terms = 'You must accept the terms and conditions';
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
      const result = await signUp(formData.email.trim(), formData.password, {
        name: formData.name.trim(),
      });

      if (result) {
        setSubmitted(true);
        // Navigate to verify page with email
        navigate('/verify-email', {
          state: {
            email: formData.email.trim(),
            codeDeliveryDetails: result.codeDeliveryDetails,
          },
        });
      }
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

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Get started with Project Aura"
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

      {/* Sign Up Form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        <FormInput
          name="name"
          type="text"
          label="Full name"
          value={formData.name}
          onChange={handleChange}
          placeholder="John Smith"
          autoComplete="name"
          error={formErrors.name}
          required
        />

        <FormInput
          name="email"
          type="email"
          label="Work email"
          value={formData.email}
          onChange={handleChange}
          placeholder="you@company.com"
          autoComplete="email"
          error={formErrors.email}
          required
        />

        <div className="relative">
          <FormInput
            name="password"
            type={showPassword ? 'text' : 'password'}
            label="Password"
            value={formData.password}
            onChange={handleChange}
            placeholder="Create a strong password"
            autoComplete="new-password"
            error={formErrors.password}
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
          <PasswordStrength password={formData.password} />
        </div>

        {/* Password requirements */}
        {formData.password && (
          <div className="text-xs space-y-1">
            {passwordRequirements.map((req, index) => (
              <div
                key={index}
                className={`flex items-center gap-2 ${
                  req.test(formData.password)
                    ? 'text-success-600 dark:text-success-400'
                    : 'text-surface-400 dark:text-surface-500'
                }`}
              >
                {req.test(formData.password) ? (
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

        <FormInput
          name="confirmPassword"
          type="password"
          label="Confirm password"
          value={formData.confirmPassword}
          onChange={handleChange}
          placeholder="Confirm your password"
          autoComplete="new-password"
          error={formErrors.confirmPassword}
          required
        />

        {/* Terms acceptance */}
        <div>
          <FormCheckbox
            name="acceptTerms"
            label={
              <span>
                I agree to the{' '}
                <a
                  href="/terms"
                  target="_blank"
                  className="text-aura-600 dark:text-aura-400 hover:underline"
                >
                  Terms of Service
                </a>{' '}
                and{' '}
                <a
                  href="/privacy"
                  target="_blank"
                  className="text-aura-600 dark:text-aura-400 hover:underline"
                >
                  Privacy Policy
                </a>
              </span>
            }
            checked={acceptTerms}
            onChange={(e) => setAcceptTerms(e.target.checked)}
          />
          {formErrors.terms && (
            <p className="mt-1 text-sm text-critical-600 dark:text-critical-400">
              {formErrors.terms}
            </p>
          )}
        </div>

        {/* Submit Button */}
        <SubmitButton loading={loading}>
          <UserPlusIcon className="w-5 h-5" />
          <span>Create account</span>
        </SubmitButton>
      </form>

      {/* Sign in link */}
      <div className="mt-4 text-center">
        <span className="text-sm text-surface-500 dark:text-surface-400">
          Already have an account?{' '}
          <Link
            to="/login"
            className="text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300 font-medium transition-colors"
          >
            Sign in
          </Link>
        </span>
      </div>
    </AuthLayout>
  );
};

export default SignUpPage;
