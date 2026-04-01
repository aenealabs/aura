/**
 * Project Aura - Error Fallback Component
 *
 * User-friendly error display with support reference ID,
 * feedback form, and recovery actions.
 *
 * Issue: #20 - Frontend production polish
 */

import { useState } from 'react';
import { reportError, trackEvent } from '../../services/errorTrackingApi';

/**
 * Main Error Fallback Component
 * Displays user-friendly error UI with reference ID and recovery options
 */
export function ErrorFallback({
  error,
  errorId,
  errorInfo,
  onRetry,
  onReload,
  onReset,
  showDetails = false,
  showFeedbackForm = true,
  title = 'Something went wrong',
  message = 'We encountered an unexpected error. Our team has been notified.',
}) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [feedbackText, setFeedbackText] = useState('');
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleGoToDashboard = () => {
    onReset?.();
    window.location.href = '/';
  };

  const handleSubmitFeedback = async () => {
    if (!feedbackText.trim()) return;

    setIsSubmitting(true);

    try {
      // Track the feedback submission
      trackEvent('error:feedback_submitted', {
        errorId,
        feedbackLength: feedbackText.length,
      });

      // Report as additional context
      await reportError(
        new Error('User provided additional error context'),
        null,
        {
          type: 'user_feedback',
          originalErrorId: errorId,
          userFeedback: feedbackText,
          errorMessage: error?.message,
        }
      );

      setFeedbackSubmitted(true);
      setFeedbackOpen(false);
    } catch {
      // Silently fail - don't show another error
    } finally {
      setIsSubmitting(false);
    }
  };

  const copyErrorId = () => {
    if (errorId) {
      navigator.clipboard.writeText(errorId);
      trackEvent('error:id_copied', { errorId });
    }
  };

  return (
    <div className="min-h-[400px] flex items-center justify-center p-6">
      <div className="max-w-lg w-full">
        {/* Error Icon */}
        <div className="text-center mb-8">
          <div className="mx-auto w-20 h-20 rounded-full bg-critical-100 dark:bg-critical-900/30 flex items-center justify-center mb-6">
            <svg
              className="w-10 h-10 text-critical-600 dark:text-critical-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>

          {/* Error Message */}
          <h2 className="text-2xl font-semibold text-surface-900 dark:text-surface-100 mb-3">
            {title}
          </h2>
          <p className="text-surface-600 dark:text-surface-400 mb-4">
            {message}
          </p>

          {/* Error Reference ID */}
          {errorId && (
            <div className="inline-flex items-center gap-2 px-4 py-2 bg-surface-100 dark:bg-surface-800 rounded-lg mb-6">
              <span className="text-sm text-surface-500 dark:text-surface-400">
                Reference ID:
              </span>
              <code className="text-sm font-mono text-surface-700 dark:text-surface-300">
                {errorId}
              </code>
              <button
                onClick={copyErrorId}
                className="p-1 hover:bg-surface-200 dark:hover:bg-surface-700 rounded transition-colors"
                title="Copy error ID"
              >
                <svg className="w-4 h-4 text-surface-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              </button>
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mb-6">
          {onRetry && (
            <button
              onClick={onRetry}
              className="w-full sm:w-auto px-6 py-2.5 bg-primary-600 hover:bg-primary-700 text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Try Again
            </button>
          )}
          <button
            onClick={handleGoToDashboard}
            className="w-full sm:w-auto px-6 py-2.5 bg-surface-100 dark:bg-surface-700 hover:bg-surface-200 dark:hover:bg-surface-600 text-surface-700 dark:text-surface-300 rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
            Go to Dashboard
          </button>
          {onReload && (
            <button
              onClick={onReload}
              className="w-full sm:w-auto px-6 py-2.5 border border-surface-300 dark:border-surface-600 hover:bg-surface-50 dark:hover:bg-surface-800 text-surface-700 dark:text-surface-300 rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Refresh Page
            </button>
          )}
        </div>

        {/* Feedback Form */}
        {showFeedbackForm && !feedbackSubmitted && (
          <div className="mt-6 border-t border-surface-200 dark:border-surface-700 pt-6">
            {!feedbackOpen ? (
              <button
                onClick={() => setFeedbackOpen(true)}
                className="w-full text-sm text-primary-600 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300 font-medium flex items-center justify-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
                Report additional details
              </button>
            ) : (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                    What were you doing when this error occurred?
                  </label>
                  <textarea
                    value={feedbackText}
                    onChange={(e) => setFeedbackText(e.target.value)}
                    placeholder="Please describe what you were doing..."
                    rows={3}
                    className="w-full px-4 py-3 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
                  />
                </div>
                <div className="flex items-center justify-end gap-3">
                  <button
                    onClick={() => setFeedbackOpen(false)}
                    className="px-4 py-2 text-sm text-surface-600 dark:text-surface-400 hover:text-surface-800 dark:hover:text-surface-200"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSubmitFeedback}
                    disabled={!feedbackText.trim() || isSubmitting}
                    className="px-4 py-2 bg-primary-600 hover:bg-primary-700 disabled:bg-surface-300 dark:disabled:bg-surface-600 text-white rounded-lg text-sm font-medium transition-colors disabled:cursor-not-allowed"
                  >
                    {isSubmitting ? 'Sending...' : 'Send Feedback'}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Feedback Submitted Confirmation */}
        {feedbackSubmitted && (
          <div className="mt-6 p-4 bg-olive-50 dark:bg-olive-900/20 border border-olive-200 dark:border-olive-800 rounded-lg">
            <div className="flex items-center gap-3">
              <svg className="w-5 h-5 text-olive-600 dark:text-olive-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-sm text-olive-700 dark:text-olive-300">
                Thank you for your feedback. Our team will investigate this issue.
              </span>
            </div>
          </div>
        )}

        {/* Error Details (Development) */}
        {showDetails && error && (
          <div className="mt-6 text-left">
            <button
              onClick={() => setDetailsOpen(!detailsOpen)}
              className="text-sm text-surface-500 hover:text-surface-700 dark:hover:text-surface-300 flex items-center gap-1"
            >
              <svg
                className={`w-4 h-4 transition-transform ${detailsOpen ? 'rotate-90' : ''}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
              {detailsOpen ? 'Hide' : 'Show'} Technical Details
            </button>

            {detailsOpen && (
              <div className="mt-3 p-4 bg-surface-100 dark:bg-surface-800 rounded-lg overflow-auto max-h-64">
                <div className="space-y-3">
                  <div>
                    <span className="text-xs font-medium text-surface-500 uppercase tracking-wide">Error</span>
                    <pre className="mt-1 text-xs text-critical-600 dark:text-critical-400 whitespace-pre-wrap font-mono">
                      {error.toString()}
                    </pre>
                  </div>
                  {error.stack && (
                    <div>
                      <span className="text-xs font-medium text-surface-500 uppercase tracking-wide">Stack Trace</span>
                      <pre className="mt-1 text-xs text-surface-600 dark:text-surface-400 whitespace-pre-wrap font-mono">
                        {error.stack}
                      </pre>
                    </div>
                  )}
                  {errorInfo?.componentStack && (
                    <div>
                      <span className="text-xs font-medium text-surface-500 uppercase tracking-wide">Component Stack</span>
                      <pre className="mt-1 text-xs text-surface-600 dark:text-surface-400 whitespace-pre-wrap font-mono">
                        {errorInfo.componentStack}
                      </pre>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Support Link */}
        <div className="mt-8 text-center text-sm text-surface-500 dark:text-surface-400">
          Need help?{' '}
          <a
            href="mailto:support@aenealabs.com"
            className="text-primary-600 hover:text-primary-700 dark:text-primary-400 font-medium"
          >
            Contact Support
          </a>
        </div>
      </div>
    </div>
  );
}

/**
 * Compact Error Display for smaller components
 */
export function ErrorFallbackCompact({
  error: _error,
  errorId,
  onRetry,
  message = 'Something went wrong',
}) {
  return (
    <div className="flex flex-col items-center justify-center p-6 text-center">
      <div className="w-12 h-12 rounded-full bg-critical-100 dark:bg-critical-900/30 flex items-center justify-center mb-4">
        <svg className="w-6 h-6 text-critical-600 dark:text-critical-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
      <p className="text-surface-600 dark:text-surface-400 mb-3">{message}</p>
      {errorId && (
        <code className="text-xs text-surface-400 dark:text-surface-500 mb-4">{errorId}</code>
      )}
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-2 text-sm bg-primary-600 hover:bg-primary-700 text-white rounded-lg font-medium transition-colors"
        >
          Try Again
        </button>
      )}
    </div>
  );
}

/**
 * Full Page Error Display
 */
export function ErrorFallbackFullPage({
  error,
  errorId,
  errorInfo,
  onRetry,
  onReload,
  onReset,
  showDetails = false,
}) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-50 dark:bg-surface-900 p-6">
      <ErrorFallback
        error={error}
        errorId={errorId}
        errorInfo={errorInfo}
        onRetry={onRetry}
        onReload={onReload}
        onReset={onReset}
        showDetails={showDetails}
        title="Application Error"
        message="We're sorry, but something went wrong. Our team has been notified and is working to fix this issue."
      />
    </div>
  );
}

export default ErrorFallback;
