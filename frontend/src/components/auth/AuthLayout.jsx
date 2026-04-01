/**
 * Authentication Layout Component
 *
 * Shared layout for all authentication pages (login, signup, etc.)
 * Provides consistent branding and visual styling.
 */

import { Link } from 'react-router-dom';

/**
 * AuthLayout - Wrapper for authentication pages
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children - Page content
 * @param {string} props.title - Page title
 * @param {string} props.subtitle - Page subtitle
 * @param {boolean} props.showBackToLogin - Show back to login link
 */
const AuthLayout = ({ children, title, subtitle, showBackToLogin = false }) => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-900 via-aura-900 to-surface-900 flex items-center justify-center px-4 py-12">
      <div className="max-w-md w-full">
        {/* Logo and Title */}
        <div className="text-center mb-8">
          <Link to="/login" className="inline-block">
            <div className="inline-flex items-center justify-center w-16 h-16 mb-4 hover:scale-105 transition-transform">
              <img
                src="/assets/aura-spiral.png"
                alt="Aura Logo"
                className="w-16 h-16 object-contain drop-shadow-lg"
              />
            </div>
          </Link>
          <h1 className="text-3xl font-bold text-white mb-2">Project Aura</h1>
          <p className="text-surface-400">Autonomous Code Intelligence Platform</p>
        </div>

        {/* Content Card */}
        <div className="bg-white dark:bg-surface-800 rounded-2xl shadow-2xl p-8 border border-surface-200 dark:border-surface-700">
          {/* Page Title */}
          {title && (
            <div className="text-center mb-6">
              <h2 className="text-xl font-semibold text-surface-900 dark:text-surface-100">
                {title}
              </h2>
              {subtitle && (
                <p className="mt-1 text-sm text-surface-500 dark:text-surface-400">
                  {subtitle}
                </p>
              )}
            </div>
          )}

          {/* Page Content */}
          {children}

          {/* Back to Login Link */}
          {showBackToLogin && (
            <div className="mt-6 text-center">
              <Link
                to="/login"
                className="text-sm text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300 transition-colors"
              >
                Back to sign in
              </Link>
            </div>
          )}
        </div>

        {/* Footer */}
        <p className="text-center text-surface-500 dark:text-surface-400 text-sm mt-6">
          Aenea Labs
        </p>
      </div>
    </div>
  );
};

/**
 * Form Input Component
 */
export const FormInput = ({
  id,
  name,
  type = 'text',
  label,
  value,
  onChange,
  placeholder,
  error,
  disabled = false,
  autoComplete,
  required = false,
  className = '',
}) => {
  return (
    <div className={className}>
      {label && (
        <label
          htmlFor={id || name}
          className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1.5"
        >
          {label}
          {required && <span className="text-critical-500 ml-1">*</span>}
        </label>
      )}
      <input
        id={id || name}
        name={name}
        type={type}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        disabled={disabled}
        autoComplete={autoComplete}
        required={required}
        className={`
          w-full px-4 py-2.5 rounded-lg border text-surface-900 dark:text-surface-100
          bg-white dark:bg-surface-700
          placeholder-surface-400 dark:placeholder-surface-500
          focus:outline-none focus:ring-2 focus:ring-aura-500 focus:border-transparent
          disabled:opacity-50 disabled:cursor-not-allowed
          transition-colors
          ${error
            ? 'border-critical-300 dark:border-critical-700'
            : 'border-surface-300 dark:border-surface-600'
          }
        `}
      />
      {error && (
        <p className="mt-1.5 text-sm text-critical-600 dark:text-critical-400">{error}</p>
      )}
    </div>
  );
};

/**
 * Form Checkbox Component
 */
export const FormCheckbox = ({
  id,
  name,
  label,
  checked,
  onChange,
  disabled = false,
  className = '',
}) => {
  return (
    <div className={`flex items-center ${className}`}>
      <input
        id={id || name}
        name={name}
        type="checkbox"
        checked={checked}
        onChange={onChange}
        disabled={disabled}
        className="
          h-4 w-4 rounded border-surface-300 dark:border-surface-600
          text-aura-600 focus:ring-aura-500 focus:ring-offset-0
          bg-white dark:bg-surface-700
          disabled:opacity-50 disabled:cursor-not-allowed
        "
      />
      <label
        htmlFor={id || name}
        className="ml-2 text-sm text-surface-600 dark:text-surface-400"
      >
        {label}
      </label>
    </div>
  );
};

/**
 * Submit Button Component
 */
export const SubmitButton = ({
  children,
  loading = false,
  disabled = false,
  onClick,
  type = 'submit',
  className = '',
}) => {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={loading || disabled}
      className={`
        w-full flex items-center justify-center gap-2 px-4 py-3
        bg-aura-600 text-white rounded-lg font-medium
        hover:bg-aura-700 focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2
        dark:focus:ring-offset-surface-800
        disabled:opacity-50 disabled:cursor-not-allowed
        transition-colors
        ${className}
      `}
    >
      {loading ? (
        <>
          <svg
            className="animate-spin h-5 w-5 text-white"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
          <span>Processing...</span>
        </>
      ) : (
        children
      )}
    </button>
  );
};

/**
 * Alert Component
 */
export const Alert = ({ type = 'error', message, onDismiss, className = '' }) => {
  const styles = {
    error: {
      bg: 'bg-critical-50 dark:bg-critical-900/30',
      border: 'border-critical-200 dark:border-critical-800',
      text: 'text-critical-700 dark:text-critical-300',
      icon: 'text-critical-500',
    },
    success: {
      bg: 'bg-olive-50 dark:bg-olive-900/30',
      border: 'border-olive-200 dark:border-olive-800',
      text: 'text-olive-700 dark:text-olive-300',
      icon: 'text-olive-500',
    },
    warning: {
      bg: 'bg-warning-50 dark:bg-warning-900/30',
      border: 'border-warning-200 dark:border-warning-800',
      text: 'text-warning-700 dark:text-warning-300',
      icon: 'text-warning-500',
    },
    info: {
      bg: 'bg-aura-50 dark:bg-aura-900/30',
      border: 'border-aura-200 dark:border-aura-800',
      text: 'text-aura-700 dark:text-aura-300',
      icon: 'text-aura-500',
    },
  };

  const style = styles[type] || styles.error;

  return (
    <div className={`p-3 rounded-lg border ${style.bg} ${style.border} ${className}`}>
      <div className="flex">
        <div className="flex-shrink-0">
          {type === 'error' && (
            <svg className={`h-5 w-5 ${style.icon}`} viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
          )}
          {type === 'success' && (
            <svg className={`h-5 w-5 ${style.icon}`} viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
          )}
          {type === 'warning' && (
            <svg className={`h-5 w-5 ${style.icon}`} viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
          )}
          {type === 'info' && (
            <svg className={`h-5 w-5 ${style.icon}`} viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
            </svg>
          )}
        </div>
        <div className="ml-3 flex-1">
          <p className={`text-sm ${style.text}`}>{message}</p>
        </div>
        {onDismiss && (
          <div className="ml-auto pl-3">
            <button
              onClick={onDismiss}
              className={`inline-flex rounded-md p-1.5 ${style.text} hover:bg-surface-100 dark:hover:bg-surface-700 focus:outline-none transition-colors`}
            >
              <span className="sr-only">Dismiss</span>
              <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

/**
 * Password Strength Indicator
 */
export const PasswordStrength = ({ password }) => {
  const getStrength = (pwd) => {
    if (!pwd) return { score: 0, label: '', color: '' };

    let score = 0;

    // Length check
    if (pwd.length >= 8) score += 1;
    if (pwd.length >= 12) score += 1;
    if (pwd.length >= 16) score += 1;

    // Character variety
    if (/[a-z]/.test(pwd)) score += 1;
    if (/[A-Z]/.test(pwd)) score += 1;
    if (/\d/.test(pwd)) score += 1;
    if (/[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]/.test(pwd)) score += 1;

    // Normalize to 0-4 scale
    const normalizedScore = Math.min(Math.floor(score / 2), 4);

    const labels = ['Very Weak', 'Weak', 'Fair', 'Strong', 'Very Strong'];
    const colors = [
      'bg-critical-500',
      'bg-warning-500',
      'bg-warning-400',
      'bg-olive-400',
      'bg-olive-500',
    ];

    return {
      score: normalizedScore,
      label: labels[normalizedScore],
      color: colors[normalizedScore],
    };
  };

  const strength = getStrength(password);

  if (!password) return null;

  return (
    <div className="mt-2">
      <div className="flex gap-1 mb-1">
        {[0, 1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className={`h-1 flex-1 rounded-full transition-colors ${
              i <= strength.score ? strength.color : 'bg-surface-200 dark:bg-surface-600'
            }`}
          />
        ))}
      </div>
      <p className="text-xs text-surface-500 dark:text-surface-400">
        Password strength: {strength.label}
      </p>
    </div>
  );
};

/**
 * Divider with text
 */
export const Divider = ({ text }) => {
  return (
    <div className="flex items-center my-6">
      <div className="flex-1 border-t border-surface-200 dark:border-surface-700"></div>
      {text && (
        <span className="px-3 text-sm text-surface-500 dark:text-surface-400">{text}</span>
      )}
      <div className="flex-1 border-t border-surface-200 dark:border-surface-700"></div>
    </div>
  );
};

export default AuthLayout;
