/**
 * Page Loading Fallback Component
 *
 * Provides contextual loading states for lazy-loaded route components.
 * Used with React.Suspense for code-split pages.
 */

import { Suspense } from 'react';
import { ErrorBoundary } from './ErrorBoundary';

/**
 * Full-page loading fallback for route transitions
 */
export function PageLoadingFallback({ pageName = 'page' }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center min-h-[400px]">
      <div className="flex flex-col items-center gap-4">
        {/* Animated loading indicator */}
        <div className="relative">
          <div className="w-12 h-12 rounded-full border-4 border-surface-200 dark:border-surface-700" />
          <div className="absolute inset-0 w-12 h-12 rounded-full border-4 border-transparent border-t-aura-500 animate-spin" />
        </div>
        {/* Loading text */}
        <span className="text-sm text-surface-500 dark:text-surface-400">
          Loading {pageName}...
        </span>
      </div>
    </div>
  );
}

/**
 * Suspense wrapper with integrated error boundary
 * Provides error isolation so lazy load failures don't crash the entire app
 */
export function SuspenseWrapper({ children, fallback, name = 'component' }) {
  return (
    <ErrorBoundary
      name={`${name}ErrorBoundary`}
      variant="inline"
      errorTitle={`Failed to load ${name}`}
      errorMessage="Please check your connection and try again."
    >
      <Suspense fallback={fallback || <PageLoadingFallback pageName={name} />}>
        {children}
      </Suspense>
    </ErrorBoundary>
  );
}

export default PageLoadingFallback;
