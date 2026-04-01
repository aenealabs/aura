import React, { forwardRef } from 'react';

/**
 * Form Elements with Validation Feedback
 *
 * Accessible form components with error states, helper text, and validation.
 *
 * Issue: #20 - Frontend production polish
 */

/**
 * Form Field Wrapper
 */
export function FormField({ label, error, helperText, required, children, className = '' }) {
  const id = React.Children.only(children)?.props?.id;

  return (
    <div className={`space-y-1.5 ${className}`}>
      {label && (
        <label
          htmlFor={id}
          className="block text-sm font-medium text-surface-700 dark:text-surface-300"
        >
          {label}
          {required && <span className="text-critical-500 ml-0.5">*</span>}
        </label>
      )}
      {children}
      {(error || helperText) && (
        <p
          className={`text-sm ${
            error
              ? 'text-critical-600 dark:text-critical-400'
              : 'text-surface-500 dark:text-surface-400'
          }`}
          role={error ? 'alert' : undefined}
        >
          {error || helperText}
        </p>
      )}
    </div>
  );
}

/**
 * Text Input with validation
 */
export const Input = forwardRef(function Input(
  {
    type = 'text',
    error,
    className = '',
    leftIcon,
    rightIcon,
    ...props
  },
  ref
) {
  const baseClasses = `
    w-full px-3 py-2.5 rounded-xl border
    bg-white dark:bg-surface-700
    backdrop-blur-sm
    text-surface-900 dark:text-surface-100
    placeholder-surface-400 dark:placeholder-surface-500
    transition-all duration-200 ease-[var(--ease-tahoe)]
    focus:outline-none focus:ring-2 focus:ring-offset-0
    focus:bg-white dark:focus:bg-white/[0.08]
    disabled:opacity-50 disabled:cursor-not-allowed
    shadow-sm focus:shadow-md
  `;

  const stateClasses = error
    ? 'border-critical-300/70 dark:border-critical-700/70 focus:border-critical-500 focus:ring-critical-500/20'
    : 'border-surface-200/50 dark:border-surface-700/50 focus:border-primary-500 focus:ring-primary-500/20';

  const inputClasses = `${baseClasses} ${stateClasses} ${
    leftIcon ? 'pl-10' : ''
  } ${rightIcon ? 'pr-10' : ''} ${className}`;

  return (
    <div className="relative">
      {leftIcon && (
        <div className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-400 dark:text-surface-500 pointer-events-none">
          {leftIcon}
        </div>
      )}
      <input
        ref={ref}
        type={type}
        className={inputClasses}
        aria-invalid={error ? 'true' : 'false'}
        {...props}
      />
      {rightIcon && (
        <div className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-400 dark:text-surface-500">
          {rightIcon}
        </div>
      )}
    </div>
  );
});

/**
 * Textarea with validation
 */
export const Textarea = forwardRef(function Textarea(
  { error, className = '', rows = 4, ...props },
  ref
) {
  const baseClasses = `
    w-full px-3 py-2.5 rounded-xl border
    bg-white dark:bg-surface-700
    backdrop-blur-sm
    text-surface-900 dark:text-surface-100
    placeholder-surface-400 dark:placeholder-surface-500
    transition-all duration-200 ease-[var(--ease-tahoe)]
    focus:outline-none focus:ring-2 focus:ring-offset-0
    focus:bg-white dark:focus:bg-white/[0.08]
    disabled:opacity-50 disabled:cursor-not-allowed
    resize-y
    shadow-sm focus:shadow-md
  `;

  const stateClasses = error
    ? 'border-critical-300/70 dark:border-critical-700/70 focus:border-critical-500 focus:ring-critical-500/20'
    : 'border-surface-200/50 dark:border-surface-700/50 focus:border-primary-500 focus:ring-primary-500/20';

  return (
    <textarea
      ref={ref}
      rows={rows}
      className={`${baseClasses} ${stateClasses} ${className}`}
      aria-invalid={error ? 'true' : 'false'}
      {...props}
    />
  );
});

/**
 * Select with validation
 */
export const Select = forwardRef(function Select(
  { error, className = '', children, placeholder, ...props },
  ref
) {
  const baseClasses = `
    w-full px-3 py-2.5 rounded-xl border
    bg-white dark:bg-surface-700
    backdrop-blur-sm
    text-surface-900 dark:text-surface-100
    transition-all duration-200 ease-[var(--ease-tahoe)]
    focus:outline-none focus:ring-2 focus:ring-offset-0
    focus:bg-white dark:focus:bg-white/[0.08]
    disabled:opacity-50 disabled:cursor-not-allowed
    appearance-none cursor-pointer
    shadow-sm focus:shadow-md
  `;

  const stateClasses = error
    ? 'border-critical-300/70 dark:border-critical-700/70 focus:border-critical-500 focus:ring-critical-500/20'
    : 'border-surface-200/50 dark:border-surface-700/50 focus:border-primary-500 focus:ring-primary-500/20';

  return (
    <div className="relative">
      <select
        ref={ref}
        className={`${baseClasses} ${stateClasses} pr-10 ${className}`}
        aria-invalid={error ? 'true' : 'false'}
        {...props}
      >
        {placeholder && (
          <option value="" disabled>
            {placeholder}
          </option>
        )}
        {children}
      </select>
      <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-surface-400">
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </div>
    </div>
  );
});

/**
 * Checkbox with label
 */
export const Checkbox = forwardRef(function Checkbox(
  { label, error, className = '', ...props },
  ref
) {
  return (
    <label className={`flex items-center gap-2.5 cursor-pointer group ${className}`}>
      <input
        ref={ref}
        type="checkbox"
        className={`
          w-4 h-4 rounded-md border-surface-300/70 dark:border-surface-600/70
          text-primary-600 focus:ring-primary-500 focus:ring-offset-0
          bg-white dark:bg-surface-700
          disabled:opacity-50 disabled:cursor-not-allowed
          transition-all duration-150
          ${error ? 'border-critical-500' : ''}
        `}
        {...props}
      />
      {label && (
        <span className="text-sm text-surface-700 dark:text-surface-300 group-hover:text-surface-900 dark:group-hover:text-surface-100 transition-colors">
          {label}
        </span>
      )}
    </label>
  );
});

/**
 * Radio button with label
 */
export const Radio = forwardRef(function Radio(
  { label, error, className = '', ...props },
  ref
) {
  return (
    <label className={`flex items-center gap-2.5 cursor-pointer group ${className}`}>
      <input
        ref={ref}
        type="radio"
        className={`
          w-4 h-4 border-surface-300/70 dark:border-surface-600/70
          text-primary-600 focus:ring-primary-500 focus:ring-offset-0
          bg-white dark:bg-surface-700
          disabled:opacity-50 disabled:cursor-not-allowed
          transition-all duration-150
          ${error ? 'border-critical-500' : ''}
        `}
        {...props}
      />
      {label && (
        <span className="text-sm text-surface-700 dark:text-surface-300 group-hover:text-surface-900 dark:group-hover:text-surface-100 transition-colors">
          {label}
        </span>
      )}
    </label>
  );
});

/**
 * Form validation utilities
 */
export const validators = {
  required: (value) => (!value || (typeof value === 'string' && !value.trim()) ? 'This field is required' : null),

  email: (value) => {
    if (!value) return null;
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(value) ? null : 'Please enter a valid email address';
  },

  minLength: (min) => (value) => {
    if (!value) return null;
    return value.length >= min ? null : `Must be at least ${min} characters`;
  },

  maxLength: (max) => (value) => {
    if (!value) return null;
    return value.length <= max ? null : `Must be no more than ${max} characters`;
  },

  pattern: (regex, message) => (value) => {
    if (!value) return null;
    return regex.test(value) ? null : message;
  },

  url: (value) => {
    if (!value) return null;
    try {
      new URL(value);
      return null;
    } catch {
      return 'Please enter a valid URL';
    }
  },

  matches: (otherValue, fieldName = 'values') => (value) => {
    return value === otherValue ? null : `${fieldName} must match`;
  },
};

/**
 * Compose multiple validators
 */
export function composeValidators(...validators) {
  return (value) => {
    for (const validator of validators) {
      const error = validator(value);
      if (error) return error;
    }
    return null;
  };
}

export default FormField;
