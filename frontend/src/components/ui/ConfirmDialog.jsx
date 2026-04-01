import { useEffect, createContext, useContext, useState, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useFocusTrap } from '../../hooks/useFocusTrap';

/**
 * Confirmation Dialog Component
 *
 * Modal dialog for confirming destructive actions.
 * Supports keyboard navigation and focus trapping.
 *
 * Issue: #20 - Frontend production polish
 *
 * Usage:
 *   const { confirm } = useConfirm();
 *   const confirmed = await confirm({
 *     title: 'Delete Item',
 *     message: 'Are you sure?',
 *     confirmText: 'Delete',
 *     variant: 'danger',
 *   });
 */

const ConfirmContext = createContext(null);

// Dialog variants
const VARIANTS = {
  danger: {
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
    ),
    iconBg: 'bg-critical-100 dark:bg-critical-900/30',
    iconColor: 'text-critical-600 dark:text-critical-400',
    buttonClass: 'bg-critical-600 hover:bg-critical-700 focus:ring-critical-500',
  },
  warning: {
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
    ),
    iconBg: 'bg-warning-100 dark:bg-warning-900/30',
    iconColor: 'text-warning-600 dark:text-warning-400',
    buttonClass: 'bg-warning-600 hover:bg-warning-700 focus:ring-warning-500',
  },
  info: {
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    iconBg: 'bg-aura-100 dark:bg-aura-900/30',
    iconColor: 'text-aura-600 dark:text-aura-400',
    buttonClass: 'bg-aura-600 hover:bg-aura-700 focus:ring-aura-500',
  },
};

/**
 * Confirmation Dialog Component
 */
function ConfirmDialog({
  isOpen,
  onConfirm,
  onCancel,
  title = 'Confirm Action',
  message = 'Are you sure you want to proceed?',
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  variant = 'danger',
  loading = false,
}) {
  const config = VARIANTS[variant] || VARIANTS.info;

  // WCAG 2.1 AA: Focus trap for dialog
  const { containerRef: dialogRef, firstFocusableRef: confirmButtonRef } = useFocusTrap(
    isOpen && !loading,
    {
      autoFocus: true,
      restoreFocus: true,
      escapeDeactivates: !loading,
      onEscape: onCancel,
    }
  );

  // Prevent body scroll when open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-title"
    >
      {/* Backdrop - Glass style */}
      <div
        className="absolute inset-0 glass-backdrop"
        onClick={loading ? undefined : onCancel}
      />

      {/* Dialog - Glass style */}
      <div
        ref={dialogRef}
        className="
          relative max-w-md w-full p-6
          bg-white dark:bg-surface-800
          backdrop-blur-xl backdrop-saturate-150
          rounded-2xl
          border border-white/50 dark:border-surface-700/50
          shadow-[var(--shadow-glass-hover)]
          animate-in fade-in zoom-in-95 duration-[var(--duration-overlay)] ease-[var(--ease-tahoe)]
        "
      >
        {/* Icon */}
        <div className={`mx-auto w-12 h-12 rounded-full ${config.iconBg} flex items-center justify-center mb-4`}>
          <div className={config.iconColor}>{config.icon}</div>
        </div>

        {/* Title */}
        <h2
          id="confirm-title"
          className="text-lg font-semibold text-center text-surface-900 dark:text-surface-100 mb-2"
        >
          {title}
        </h2>

        {/* Message */}
        <p className="text-center text-surface-600 dark:text-surface-400 mb-6">
          {message}
        </p>

        {/* Actions */}
        <div className="flex items-center justify-center gap-3">
          <button
            onClick={onCancel}
            disabled={loading}
            className="
              px-4 py-2.5 rounded-xl font-medium
              bg-white dark:bg-surface-700
              hover:bg-surface-50 dark:hover:bg-surface-700
              border border-surface-200/50 dark:border-surface-700/50
              text-surface-700 dark:text-surface-300
              transition-all duration-200 ease-[var(--ease-tahoe)]
              hover:shadow-sm hover:-translate-y-px
              active:scale-[0.98]
              disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0
            "
          >
            {cancelText}
          </button>
          <button
            ref={confirmButtonRef}
            onClick={onConfirm}
            disabled={loading}
            className={`
              px-4 py-2.5 rounded-xl font-medium text-white
              transition-all duration-200 ease-[var(--ease-tahoe)]
              focus:outline-none focus:ring-2 focus:ring-offset-2
              hover:shadow-md hover:-translate-y-px
              active:scale-[0.98]
              disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0
              flex items-center gap-2
              ${config.buttonClass}
            `}
          >
            {loading && (
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
            )}
            {confirmText}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}

/**
 * Confirm Provider Component
 */
export function ConfirmProvider({ children }) {
  const [state, setState] = useState({
    isOpen: false,
    loading: false,
    config: {},
    resolve: null,
  });

  const confirm = useCallback((config) => {
    return new Promise((resolve) => {
      setState({
        isOpen: true,
        loading: false,
        config,
        resolve,
      });
    });
  }, []);

  const handleConfirm = useCallback(async () => {
    if (state.config.onConfirm) {
      setState((prev) => ({ ...prev, loading: true }));
      try {
        await state.config.onConfirm();
      } catch (error) {
        setState((prev) => ({ ...prev, loading: false }));
        throw error;
      }
    }
    state.resolve?.(true);
    setState({ isOpen: false, loading: false, config: {}, resolve: null });
  }, [state]);

  const handleCancel = useCallback(() => {
    state.resolve?.(false);
    setState({ isOpen: false, loading: false, config: {}, resolve: null });
  }, [state]);

  return (
    <ConfirmContext.Provider value={{ confirm }}>
      {children}
      <ConfirmDialog
        isOpen={state.isOpen}
        loading={state.loading}
        onConfirm={handleConfirm}
        onCancel={handleCancel}
        {...state.config}
      />
    </ConfirmContext.Provider>
  );
}

/**
 * Hook to use confirmation dialog
 */
export function useConfirm() {
  const context = useContext(ConfirmContext);
  if (!context) {
    throw new Error('useConfirm must be used within a ConfirmProvider');
  }
  return context;
}

/**
 * Standalone Confirm Dialog (without context)
 */
export function StandaloneConfirmDialog(props) {
  return <ConfirmDialog {...props} />;
}

export default ConfirmProvider;
