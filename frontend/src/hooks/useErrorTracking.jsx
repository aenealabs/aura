/**
 * Project Aura - Error Tracking Hook
 *
 * React hook for initializing and using error tracking throughout the app.
 * Handles global error handlers, route change tracking, and performance monitoring.
 *
 * Issue: #20 - Frontend production polish
 */

import { useEffect, useCallback, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import {
  setupGlobalHandlers,
  initPerformanceMonitoring,
  setUserContext,
  clearUserContext,
  trackRouteChange,
  breadcrumb,
  flush,
  trackEvent,
  reportError,
  reportWarning,
  trackInteraction,
} from '../services/errorTrackingApi';

// Track if error tracking has been initialized globally
let isInitialized = false;

/**
 * Main error tracking hook
 * Initialize once at the app root level
 *
 * @param {Object} options - Configuration options
 * @param {Object} options.user - User object for context
 * @param {boolean} options.enablePerformance - Enable Core Web Vitals tracking
 * @param {boolean} options.trackRoutes - Track route changes as breadcrumbs
 */
export function useErrorTracking(options = {}) {
  const { user = null, enablePerformance = true, trackRoutes = true } = options;

  const prevLocationRef = useRef(null);

  // Get current location for route tracking (requires Router context)
  const location = useLocation();

  // Initialize global handlers once
  useEffect(() => {
    if (isInitialized) return;

    // Setup global error handlers
    setupGlobalHandlers();

    // Initialize performance monitoring if enabled
    if (enablePerformance) {
      initPerformanceMonitoring();
    }

    // Add initialization breadcrumb
    breadcrumb('Error tracking initialized', 'system');

    isInitialized = true;

    // Cleanup on unmount
    return () => {
      flush();
    };
  }, [enablePerformance]);

  // Update user context when user changes
  useEffect(() => {
    if (user) {
      setUserContext(user.id, {
        email: user.email,
        name: user.name,
        role: user.role,
        groups: user.groups,
      });
    } else {
      clearUserContext();
    }
  }, [user]);

  // Track route changes
  useEffect(() => {
    if (!trackRoutes) return;

    const currentPath = location.pathname + location.search;
    const prevPath = prevLocationRef.current;

    if (prevPath !== null && prevPath !== currentPath) {
      trackRouteChange(prevPath, currentPath);
    }

    prevLocationRef.current = currentPath;
  }, [location, trackRoutes]);

  // Memoized error reporting function
  const captureError = useCallback((error, metadata = {}) => {
    return reportError(error, null, metadata);
  }, []);

  // Memoized warning reporting function
  const captureWarning = useCallback((message, context = {}) => {
    return reportWarning(message, context);
  }, []);

  // Memoized event tracking function
  const captureEvent = useCallback((eventName, properties = {}) => {
    trackEvent(eventName, properties);
  }, []);

  // Memoized breadcrumb function
  const addBreadcrumb = useCallback((message, category = 'custom', data = {}) => {
    breadcrumb(message, category, data);
  }, []);

  // Memoized interaction tracking
  const captureInteraction = useCallback((action, target, data = {}) => {
    trackInteraction(action, target, data);
  }, []);

  return {
    captureError,
    captureWarning,
    captureEvent,
    addBreadcrumb,
    captureInteraction,
    flush,
  };
}

/**
 * Hook for tracking form interactions
 * Automatically captures form field changes and submissions
 *
 * @param {string} formName - Name of the form for tracking
 */
export function useFormTracking(formName) {
  const trackField = useCallback(
    (fieldName, action = 'change') => {
      breadcrumb(`Form field ${action}: ${fieldName}`, 'form', { form: formName, field: fieldName });
    },
    [formName]
  );

  const trackSubmit = useCallback(
    (success, errorMessage = null) => {
      const level = success ? 'info' : 'error';
      breadcrumb(`Form ${success ? 'submitted' : 'failed'}: ${formName}`, 'form', { success, error: errorMessage }, level);
      trackEvent(`form:${success ? 'submit' : 'error'}`, { form: formName, error: errorMessage });
    },
    [formName]
  );

  return { trackField, trackSubmit };
}

/**
 * Hook for tracking component lifecycle
 * Useful for debugging rendering issues
 *
 * @param {string} componentName - Name of the component
 */
export function useComponentTracking(componentName) {
  const mountTimeRef = useRef(null);

  useEffect(() => {
    mountTimeRef.current = performance.now();
    breadcrumb(`Component mounted: ${componentName}`, 'component');

    return () => {
      const duration = performance.now() - mountTimeRef.current;
      breadcrumb(`Component unmounted: ${componentName}`, 'component', { lifespan: `${duration.toFixed(0)}ms` });
    };
  }, [componentName]);
}

/**
 * Hook for tracking async operations
 * Captures loading states, errors, and timing
 *
 * @param {string} operationName - Name of the operation
 */
export function useAsyncTracking(operationName) {
  const startTimeRef = useRef(null);

  const start = useCallback(() => {
    startTimeRef.current = performance.now();
    breadcrumb(`Started: ${operationName}`, 'async', { state: 'started' });
  }, [operationName]);

  const success = useCallback(
    (_data = null) => {
      const duration = startTimeRef.current ? performance.now() - startTimeRef.current : null;
      breadcrumb(`Completed: ${operationName}`, 'async', {
        state: 'success',
        duration: duration ? `${duration.toFixed(0)}ms` : undefined,
      });
      trackEvent(`async:success`, { operation: operationName, duration });
    },
    [operationName]
  );

  const error = useCallback(
    (err) => {
      const duration = startTimeRef.current ? performance.now() - startTimeRef.current : null;
      breadcrumb(`Failed: ${operationName}`, 'async', {
        state: 'error',
        error: err.message,
        duration: duration ? `${duration.toFixed(0)}ms` : undefined,
      }, 'error');
      trackEvent(`async:error`, { operation: operationName, error: err.message, duration });
    },
    [operationName]
  );

  return { start, success, error };
}

/**
 * Hook for tracking user engagement
 * Tracks page visibility, focus, and time spent
 */
export function useEngagementTracking() {
  const startTimeRef = useRef(Date.now());
  const activeTimeRef = useRef(0);
  const lastActiveRef = useRef(Date.now());

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        // Page hidden - record active time
        activeTimeRef.current += Date.now() - lastActiveRef.current;
        breadcrumb('Page hidden', 'engagement', {
          activeTime: `${(activeTimeRef.current / 1000).toFixed(1)}s`,
        });
      } else {
        // Page visible - resume tracking
        lastActiveRef.current = Date.now();
        breadcrumb('Page visible', 'engagement');
      }
    };

    const handleBeforeUnload = () => {
      // Calculate final active time
      if (!document.hidden) {
        activeTimeRef.current += Date.now() - lastActiveRef.current;
      }

      const totalTime = Date.now() - startTimeRef.current;
      trackEvent('engagement:session', {
        totalTime: `${(totalTime / 1000).toFixed(1)}s`,
        activeTime: `${(activeTimeRef.current / 1000).toFixed(1)}s`,
      });
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('beforeunload', handleBeforeUnload);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, []);
}

/**
 * HOC for wrapping components with error tracking
 * Captures render errors and provides error context
 */
export function withErrorTracking(WrappedComponent, componentName) {
  return function ErrorTrackedComponent(props) {
    useComponentTracking(componentName || WrappedComponent.displayName || WrappedComponent.name);
    return <WrappedComponent {...props} />;
  };
}

// Export all hooks
export default {
  useErrorTracking,
  useFormTracking,
  useComponentTracking,
  useAsyncTracking,
  useEngagementTracking,
  withErrorTracking,
};
