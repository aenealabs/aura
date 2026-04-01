import { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { createPortal } from 'react-dom';

/**
 * Toast Notification System
 *
 * Provides toast notifications for success, error, warning, and info messages.
 * Auto-dismisses after configurable duration.
 *
 * Issue: #20 - Frontend production polish
 *
 * Usage:
 *   const { toast } = useToast();
 *   toast.success('Operation completed');
 *   toast.error('Something went wrong');
 */

const ToastContext = createContext(null);

// Toast types with their styling - Solid colored backgrounds with left accent
const TOAST_TYPES = {
  success: {
    title: 'Success',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
      </svg>
    ),
    containerClassName: 'bg-olive-100 dark:bg-olive-900 border-l-4 border-l-olive-500 border-y border-r border-olive-300 dark:border-olive-700',
    iconClassName: 'text-olive-600 dark:text-olive-300',
    titleClassName: 'text-olive-800 dark:text-olive-100',
    messageClassName: 'text-olive-700 dark:text-olive-200',
    dismissClassName: 'text-olive-600 hover:text-olive-800 dark:text-olive-300 dark:hover:text-olive-100',
  },
  error: {
    title: 'Error',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
      </svg>
    ),
    containerClassName: 'bg-critical-100 dark:bg-critical-900 border-l-4 border-l-critical-500 border-y border-r border-critical-300 dark:border-critical-700',
    iconClassName: 'text-critical-600 dark:text-critical-300',
    titleClassName: 'text-critical-800 dark:text-critical-100',
    messageClassName: 'text-critical-700 dark:text-critical-200',
    dismissClassName: 'text-critical-600 hover:text-critical-800 dark:text-critical-300 dark:hover:text-critical-100',
  },
  warning: {
    title: 'Warning',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
    ),
    containerClassName: 'bg-warning-100 dark:bg-warning-900 border-l-4 border-l-warning-500 border-y border-r border-warning-300 dark:border-warning-700',
    iconClassName: 'text-warning-600 dark:text-warning-300',
    titleClassName: 'text-warning-800 dark:text-warning-100',
    messageClassName: 'text-warning-700 dark:text-warning-200',
    dismissClassName: 'text-warning-600 hover:text-warning-800 dark:text-warning-300 dark:hover:text-warning-100',
  },
  info: {
    title: 'Information',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    containerClassName: 'bg-aura-100 dark:bg-aura-900 border-l-4 border-l-aura-500 border-y border-r border-aura-300 dark:border-aura-700',
    iconClassName: 'text-aura-600 dark:text-aura-300',
    titleClassName: 'text-aura-800 dark:text-aura-100',
    messageClassName: 'text-aura-700 dark:text-aura-200',
    dismissClassName: 'text-aura-600 hover:text-aura-800 dark:text-aura-300 dark:hover:text-aura-100',
  },
};

// Default durations
const DEFAULT_DURATION = 5000;
const ERROR_DURATION = 8000;

/**
 * Individual Toast Component
 */
function ToastItem({ toast, onDismiss }) {
  const [isExiting, setIsExiting] = useState(false);
  const config = TOAST_TYPES[toast.type] || TOAST_TYPES.info;

  useEffect(() => {
    if (toast.duration !== Infinity) {
      const timer = setTimeout(() => {
        setIsExiting(true);
        setTimeout(() => onDismiss(toast.id), 200);
      }, toast.duration);

      return () => clearTimeout(timer);
    }
  }, [toast.id, toast.duration, onDismiss]);

  const handleDismiss = () => {
    setIsExiting(true);
    setTimeout(() => onDismiss(toast.id), 200);
  };

  // Use custom title if provided, otherwise use default type title
  const displayTitle = toast.title || config.title;

  return (
    <div
      className={`
        flex items-start gap-3 px-4 py-3 rounded-lg
        shadow-lg
        transition-all duration-200 ease-[var(--ease-tahoe)]
        ${config.containerClassName}
        ${isExiting ? 'opacity-0 translate-x-4 scale-95' : 'opacity-100 translate-x-0 scale-100'}
      `}
      role="alert"
    >
      {/* Icon */}
      <div className={`flex-shrink-0 mt-0.5 ${config.iconClassName}`}>
        {config.icon}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <p className={`font-semibold text-sm ${config.titleClassName}`}>
          {displayTitle}
        </p>
        <p className={`text-sm mt-0.5 ${config.messageClassName}`}>
          {toast.message}
        </p>

        {/* Action Button */}
        {toast.action && (
          <button
            onClick={() => {
              toast.action.onClick();
              handleDismiss();
            }}
            className={`mt-2 text-sm font-medium underline hover:no-underline ${config.titleClassName}`}
          >
            {toast.action.label}
          </button>
        )}
      </div>

      {/* Dismiss Button */}
      <button
        onClick={handleDismiss}
        className={`flex-shrink-0 transition-colors ${config.dismissClassName}`}
        aria-label="Dismiss"
      >
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

/**
 * Toast Container (Portal)
 */
function ToastContainer({ toasts, onDismiss, position = 'top-right' }) {
  const positionClasses = {
    'top-right': 'top-20 right-4',
    'top-left': 'top-20 left-4',
    'top-center': 'top-20 left-1/2 -translate-x-1/2',
    'bottom-right': 'bottom-4 right-4',
    'bottom-left': 'bottom-4 left-4',
    'bottom-center': 'bottom-4 left-1/2 -translate-x-1/2',
  };

  if (toasts.length === 0) return null;

  return createPortal(
    <div
      className={`
        fixed z-50 flex flex-col gap-2 w-full max-w-sm pointer-events-none
        ${positionClasses[position]}
      `}
      aria-live="polite"
      aria-atomic="true"
    >
      {toasts.map((toast) => (
        <div key={toast.id} className="pointer-events-auto">
          <ToastItem toast={toast} onDismiss={onDismiss} />
        </div>
      ))}
    </div>,
    document.body
  );
}

/**
 * Toast Provider Component
 */
export function ToastProvider({ children, position = 'top-right', maxToasts = 5 }) {
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((toast) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const newToast = {
      id,
      duration: toast.type === 'error' ? ERROR_DURATION : DEFAULT_DURATION,
      ...toast,
    };

    setToasts((prev) => {
      const updated = [newToast, ...prev];
      // Limit max toasts
      return updated.slice(0, maxToasts);
    });

    return id;
  }, [maxToasts]);

  const dismissToast = useCallback((id) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const dismissAll = useCallback(() => {
    setToasts([]);
  }, []);

  // Toast helper methods
  const toast = {
    show: (message, options = {}) => addToast({ message, type: 'info', ...options }),
    success: (message, options = {}) => addToast({ message, type: 'success', ...options }),
    error: (message, options = {}) => addToast({ message, type: 'error', ...options }),
    warning: (message, options = {}) => addToast({ message, type: 'warning', ...options }),
    info: (message, options = {}) => addToast({ message, type: 'info', ...options }),
    dismiss: dismissToast,
    dismissAll,
  };

  return (
    <ToastContext.Provider value={{ toast, toasts }}>
      {children}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} position={position} />
    </ToastContext.Provider>
  );
}

/**
 * Hook to use toast notifications
 */
export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
}

/**
 * Show API error toast with retry option
 */
export function showApiError(toast, error, onRetry) {
  const message = error.response?.data?.message || error.message || 'An error occurred';

  toast.error(message, {
    title: 'Request Failed',
    duration: ERROR_DURATION,
    action: onRetry ? { label: 'Retry', onClick: onRetry } : undefined,
  });
}

export default ToastProvider;
