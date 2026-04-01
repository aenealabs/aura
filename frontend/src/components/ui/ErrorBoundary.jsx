/**
 * Project Aura - Error Boundary Component
 *
 * Catches JavaScript errors anywhere in the child component tree,
 * reports them to CloudWatch/error tracking, and displays a fallback UI.
 *
 * Issue: #20 - Frontend production polish
 */

import { Component } from 'react';
import {
  reportError,
  breadcrumb,
  trackEvent,
} from '../../services/errorTrackingApi';
import {
  ErrorFallback,
  ErrorFallbackCompact,
  ErrorFallbackFullPage,
} from './ErrorFallback';

/**
 * Global Error Boundary Component
 *
 * Catches JavaScript errors anywhere in the child component tree,
 * logs them, and displays a fallback UI.
 */
export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: null,
    };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  async componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo });

    // Log to console in development
    if (import.meta.env.DEV) {
      console.error('Error Boundary caught an error:', error, errorInfo);
    }

    // Report to error tracking service
    try {
      const { errorId } = await reportError(error, errorInfo?.componentStack, {
        boundaryName: this.props.name || 'Unknown',
        url: window.location.href,
        pathname: window.location.pathname,
      });

      this.setState({ errorId });

      // Track the error event
      trackEvent('error:boundary_caught', {
        errorId,
        errorName: error.name,
        errorMessage: error.message,
        boundaryName: this.props.name || 'Unknown',
      });
    } catch (reportingError) {
      // Silently fail if error reporting fails
      console.error('[ErrorBoundary] Failed to report error:', reportingError);
    }
  }

  handleRetry = () => {
    breadcrumb('User clicked retry in ErrorBoundary', 'user', {
      errorId: this.state.errorId,
    });

    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: null,
    });

    // Call optional onRetry callback
    this.props.onRetry?.();
  };

  handleReload = () => {
    breadcrumb('User clicked reload in ErrorBoundary', 'user', {
      errorId: this.state.errorId,
    });

    window.location.reload();
  };

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: null,
    });

    // Call optional onReset callback
    this.props.onReset?.();
  };

  render() {
    if (this.state.hasError) {
      // Check for custom fallback
      if (this.props.fallback) {
        // If fallback is a function, call it with error details
        if (typeof this.props.fallback === 'function') {
          return this.props.fallback({
            error: this.state.error,
            errorId: this.state.errorId,
            errorInfo: this.state.errorInfo,
            onRetry: this.handleRetry,
            onReload: this.handleReload,
            onReset: this.handleReset,
          });
        }
        return this.props.fallback;
      }

      // Use appropriate fallback based on variant
      const FallbackComponent =
        this.props.variant === 'compact'
          ? ErrorFallbackCompact
          : this.props.variant === 'fullPage'
          ? ErrorFallbackFullPage
          : ErrorFallback;

      return (
        <FallbackComponent
          error={this.state.error}
          errorId={this.state.errorId}
          errorInfo={this.state.errorInfo}
          onRetry={this.handleRetry}
          onReload={this.handleReload}
          onReset={this.handleReset}
          showDetails={this.props.showDetails ?? import.meta.env.DEV}
          title={this.props.errorTitle}
          message={this.props.errorMessage}
        />
      );
    }

    return this.props.children;
  }
}

/**
 * Inline Error Display for smaller components
 */
export function InlineError({ message = 'Failed to load', onRetry, className = '' }) {
  return (
    <div
      className={`flex items-center justify-center gap-2 p-4 text-critical-600 dark:text-critical-400 ${className}`}
    >
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
      <span className="text-sm">{message}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          className="text-sm font-medium text-primary-600 hover:text-primary-700 dark:text-primary-400"
        >
          Retry
        </button>
      )}
    </div>
  );
}

/**
 * Page-level Error Display
 */
export function PageError({ title = 'Page Error', message, onRetry, onGoBack }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-50 dark:bg-surface-900 p-6">
      <div className="max-w-lg w-full text-center">
        <div className="mx-auto w-20 h-20 rounded-full bg-critical-100 dark:bg-critical-900/30 flex items-center justify-center mb-8">
          <svg
            className="w-10 h-10 text-critical-600 dark:text-critical-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>

        <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100 mb-3">
          {title}
        </h1>
        <p className="text-surface-600 dark:text-surface-400 mb-8">
          {message || 'An unexpected error occurred. Please try again.'}
        </p>

        <div className="flex items-center justify-center gap-4">
          {onGoBack && (
            <button
              onClick={onGoBack}
              className="px-6 py-2.5 bg-surface-100 dark:bg-surface-700 hover:bg-surface-200 dark:hover:bg-surface-600 text-surface-700 dark:text-surface-300 rounded-lg font-medium transition-colors"
            >
              Go Back
            </button>
          )}
          {onRetry && (
            <button
              onClick={onRetry}
              className="px-6 py-2.5 bg-primary-600 hover:bg-primary-700 text-white rounded-lg font-medium transition-colors"
            >
              Try Again
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// Re-export ErrorFallback components for convenience
export { ErrorFallback, ErrorFallbackCompact, ErrorFallbackFullPage } from './ErrorFallback';

export default ErrorBoundary;
