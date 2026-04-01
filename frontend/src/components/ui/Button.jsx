import React, { forwardRef } from 'react';

/**
 * Button Component with Loading State
 *
 * Accessible button with variants, sizes, and loading spinner.
 *
 * Issue: #20 - Frontend production polish
 */

const VARIANTS = {
  primary: `
    bg-primary-600 hover:bg-primary-700 active:bg-primary-800
    text-white
    focus:ring-primary-500/50
    shadow-sm hover:shadow-md hover:-translate-y-px
  `,
  secondary: `
    bg-white dark:bg-surface-700
    hover:bg-surface-50 dark:hover:bg-surface-700
    active:bg-surface-100 dark:active:bg-surface-600
    text-surface-700 dark:text-surface-300
    border border-surface-200/50 dark:border-surface-700/50
    focus:ring-surface-500/50
    backdrop-blur-sm
    shadow-sm hover:shadow-md hover:-translate-y-px
  `,
  danger: `
    bg-critical-600 hover:bg-critical-700 active:bg-critical-800
    text-white
    focus:ring-critical-500/50
    shadow-sm hover:shadow-md hover:-translate-y-px
  `,
  warning: `
    bg-warning-500 hover:bg-warning-600 active:bg-warning-700
    text-white
    focus:ring-warning-500/50
    shadow-sm hover:shadow-md hover:-translate-y-px
  `,
  success: `
    bg-olive-600 hover:bg-olive-700 active:bg-olive-800
    text-white
    focus:ring-olive-500/50
    shadow-sm hover:shadow-md hover:-translate-y-px
  `,
  ghost: `
    bg-transparent hover:bg-surface-100 dark:hover:bg-surface-700
    text-surface-700 dark:text-surface-300
    focus:ring-surface-500/50
    hover:shadow-sm hover:-translate-y-px
  `,
  link: `
    bg-transparent hover:underline
    text-primary-600 dark:text-primary-400
    focus:ring-primary-500/50
    px-0
  `,
  outline: `
    bg-transparent border-2 border-primary-600 dark:border-primary-500
    hover:bg-primary-50 dark:hover:bg-primary-900/20
    text-primary-600 dark:text-primary-400
    focus:ring-primary-500/50
    hover:-translate-y-px
  `,
};

const SIZES = {
  xs: 'px-2 py-1 text-xs rounded-lg',
  sm: 'px-3 py-1.5 text-sm rounded-lg',
  md: 'px-4 py-2 text-sm rounded-xl',
  lg: 'px-5 py-2.5 text-base rounded-xl',
  xl: 'px-6 py-3 text-lg rounded-2xl',
};

const ICON_SIZES = {
  xs: 'w-3 h-3',
  sm: 'w-4 h-4',
  md: 'w-4 h-4',
  lg: 'w-5 h-5',
  xl: 'w-6 h-6',
};

/**
 * Loading Spinner
 */
function LoadingSpinner({ size = 'md' }) {
  return (
    <svg
      className={`animate-spin ${ICON_SIZES[size]}`}
      viewBox="0 0 24 24"
      fill="none"
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
  );
}

/**
 * Button Component
 */
export const Button = forwardRef(function Button(
  {
    variant = 'primary',
    size = 'md',
    loading = false,
    disabled = false,
    leftIcon,
    rightIcon,
    fullWidth = false,
    children,
    className = '',
    type = 'button',
    ...props
  },
  ref
) {
  const isDisabled = disabled || loading;

  const baseClasses = `
    inline-flex items-center justify-center gap-2
    font-medium
    transition-all duration-200 ease-[var(--ease-tahoe)]
    focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-white dark:focus:ring-offset-surface-900
    disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0 disabled:hover:shadow-none
    active:scale-[0.98]
  `;

  return (
    <button
      ref={ref}
      type={type}
      disabled={isDisabled}
      className={`
        ${baseClasses}
        ${VARIANTS[variant]}
        ${SIZES[size]}
        ${fullWidth ? 'w-full' : ''}
        ${className}
      `}
      {...props}
    >
      {loading ? (
        <>
          <LoadingSpinner size={size} />
          <span className="sr-only">Loading...</span>
          {children}
        </>
      ) : (
        <>
          {leftIcon && <span className={ICON_SIZES[size]}>{leftIcon}</span>}
          {children}
          {rightIcon && <span className={ICON_SIZES[size]}>{rightIcon}</span>}
        </>
      )}
    </button>
  );
});

/**
 * Icon Button (square button for icons only)
 */
export const IconButton = forwardRef(function IconButton(
  {
    variant = 'ghost',
    size = 'md',
    loading = false,
    disabled = false,
    'aria-label': ariaLabel,
    children,
    className = '',
    ...props
  },
  ref
) {
  const isDisabled = disabled || loading;

  const sizeClasses = {
    xs: 'p-1',
    sm: 'p-1.5',
    md: 'p-2',
    lg: 'p-2.5',
    xl: 'p-3',
  };

  const baseClasses = `
    inline-flex items-center justify-center
    rounded-xl
    transition-all duration-200 ease-[var(--ease-tahoe)]
    focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-white dark:focus:ring-offset-surface-900
    disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0 disabled:hover:shadow-none
    active:scale-[0.95]
  `;

  return (
    <button
      ref={ref}
      type="button"
      disabled={isDisabled}
      aria-label={ariaLabel}
      className={`
        ${baseClasses}
        ${VARIANTS[variant]}
        ${sizeClasses[size]}
        ${className}
      `}
      {...props}
    >
      {loading ? (
        <LoadingSpinner size={size} />
      ) : (
        <span className={ICON_SIZES[size]}>{children}</span>
      )}
    </button>
  );
});

/**
 * Button Group
 */
export function ButtonGroup({ children, className = '' }) {
  return (
    <div
      className={`inline-flex rounded-xl overflow-hidden divide-x divide-surface-200/50 dark:divide-surface-600/50 shadow-sm ${className}`}
      role="group"
    >
      {React.Children.map(children, (child) =>
        React.cloneElement(child, {
          className: `${child.props.className || ''} rounded-none first:rounded-l-xl last:rounded-r-xl shadow-none hover:shadow-none`,
        })
      )}
    </div>
  );
}

export default Button;
