/**
 * Project Aura - Error Tracking API Service
 *
 * Provides client-side error tracking and reporting to CloudWatch/backend.
 * Includes rate limiting, breadcrumb tracking, and user context.
 *
 * Issue: #20 - Frontend production polish
 */

import { apiClient } from './api';

// Configuration
const CONFIG = {
  maxBreadcrumbs: 50,
  maxErrorsPerMinute: 10,
  flushInterval: 30000, // 30 seconds
  sessionStorageKey: 'aura_error_breadcrumbs',
  endpoint: '/errors/report',
};

// Error queue for batching
let errorQueue = [];
let warningQueue = [];
let eventQueue = [];

// Rate limiting state
let errorCount = 0;
let lastResetTime = Date.now();

// User context
let userContext = null;

// Flush timer
let flushTimer = null;

/**
 * Generate a unique error ID for reference
 */
function generateErrorId() {
  const timestamp = Date.now().toString(36);
  const random = Math.random().toString(36).substring(2, 8);
  return `AURA-${timestamp}-${random}`.toUpperCase();
}

/**
 * Get browser/device metadata
 */
function getBrowserMetadata() {
  const nav = navigator;
  const screen = window.screen;

  return {
    userAgent: nav.userAgent,
    language: nav.language,
    platform: nav.platform,
    vendor: nav.vendor,
    cookieEnabled: nav.cookieEnabled,
    onLine: nav.onLine,
    screen: {
      width: screen.width,
      height: screen.height,
      colorDepth: screen.colorDepth,
      pixelRatio: window.devicePixelRatio,
    },
    viewport: {
      width: window.innerWidth,
      height: window.innerHeight,
    },
    memory: nav.deviceMemory ? `${nav.deviceMemory}GB` : undefined,
    cores: nav.hardwareConcurrency,
    connection: nav.connection
      ? {
          effectiveType: nav.connection.effectiveType,
          downlink: nav.connection.downlink,
          rtt: nav.connection.rtt,
        }
      : undefined,
  };
}

/**
 * Get current route/URL information
 */
function getRouteInfo() {
  return {
    url: window.location.href,
    pathname: window.location.pathname,
    search: window.location.search,
    hash: window.location.hash,
    referrer: document.referrer,
  };
}

/**
 * Check rate limit - reset counter every minute
 */
function checkRateLimit() {
  const now = Date.now();
  if (now - lastResetTime > 60000) {
    errorCount = 0;
    lastResetTime = now;
  }

  if (errorCount >= CONFIG.maxErrorsPerMinute) {
    console.warn('[ErrorTracking] Rate limit exceeded. Error not reported.');
    return false;
  }

  errorCount++;
  return true;
}

/**
 * Load breadcrumbs from session storage
 */
function loadBreadcrumbs() {
  try {
    const stored = sessionStorage.getItem(CONFIG.sessionStorageKey);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

/**
 * Save breadcrumbs to session storage
 */
function saveBreadcrumbs(breadcrumbs) {
  try {
    sessionStorage.setItem(CONFIG.sessionStorageKey, JSON.stringify(breadcrumbs));
  } catch {
    // Session storage full or unavailable
  }
}

/**
 * Add a breadcrumb to the trail
 * Breadcrumbs help trace user actions leading to an error
 *
 * @param {string} message - Description of the action
 * @param {string} category - Category (navigation, user, console, http, etc.)
 * @param {Object} data - Additional context data
 * @param {string} level - Severity (info, warning, error)
 */
export function breadcrumb(message, category = 'custom', data = {}, level = 'info') {
  const breadcrumbs = loadBreadcrumbs();

  const crumb = {
    timestamp: new Date().toISOString(),
    message,
    category,
    level,
    data,
  };

  breadcrumbs.push(crumb);

  // Keep only the most recent breadcrumbs
  if (breadcrumbs.length > CONFIG.maxBreadcrumbs) {
    breadcrumbs.shift();
  }

  saveBreadcrumbs(breadcrumbs);
}

/**
 * Set user context for error reports
 *
 * @param {string} userId - User identifier
 * @param {Object} metadata - Additional user info (name, email, role, etc.)
 */
export function setUserContext(userId, metadata = {}) {
  userContext = {
    userId,
    ...metadata,
    setAt: new Date().toISOString(),
  };

  breadcrumb('User context updated', 'user', { userId });
}

/**
 * Clear user context (e.g., on logout)
 */
export function clearUserContext() {
  userContext = null;
  breadcrumb('User context cleared', 'user');
}

/**
 * Report an error to the backend
 *
 * @param {Error} error - The error object
 * @param {string} componentStack - React component stack trace
 * @param {Object} metadata - Additional context
 * @returns {Promise<{errorId: string, success: boolean}>}
 */
export async function reportError(error, componentStack = null, metadata = {}) {
  if (!checkRateLimit()) {
    return { errorId: null, success: false, rateLimited: true };
  }

  const errorId = generateErrorId();

  const errorReport = {
    errorId,
    timestamp: new Date().toISOString(),
    environment: import.meta.env.MODE || 'development',
    error: {
      name: error.name,
      message: error.message,
      stack: error.stack,
      componentStack,
    },
    route: getRouteInfo(),
    browser: getBrowserMetadata(),
    user: userContext,
    breadcrumbs: loadBreadcrumbs(),
    metadata: {
      ...metadata,
      sessionId: getSessionId(),
    },
    severity: 'error',
  };

  // Add to queue for batching
  errorQueue.push(errorReport);

  // Start flush timer if not running
  startFlushTimer();

  // Also send immediately for errors (don't wait for batch)
  try {
    await sendToBackend([errorReport]);
    errorQueue = errorQueue.filter((e) => e.errorId !== errorId);

    // Add breadcrumb for the error
    breadcrumb(`Error reported: ${error.message}`, 'error', { errorId });

    return { errorId, success: true };
  } catch (sendError) {
    console.error('[ErrorTracking] Failed to send error report:', sendError);
    return { errorId, success: false };
  }
}

/**
 * Report a warning (less severe than error)
 *
 * @param {string} message - Warning message
 * @param {Object} context - Additional context
 * @returns {Promise<{warningId: string, success: boolean}>}
 */
export async function reportWarning(message, context = {}) {
  const warningId = generateErrorId();

  const warningReport = {
    warningId,
    timestamp: new Date().toISOString(),
    environment: import.meta.env.MODE || 'development',
    message,
    route: getRouteInfo(),
    user: userContext,
    context,
    severity: 'warning',
  };

  warningQueue.push(warningReport);
  startFlushTimer();

  breadcrumb(`Warning: ${message}`, 'warning', { warningId });

  return { warningId, success: true };
}

/**
 * Track custom events for analytics
 *
 * @param {string} eventName - Name of the event
 * @param {Object} properties - Event properties
 */
export function trackEvent(eventName, properties = {}) {
  const event = {
    eventName,
    timestamp: new Date().toISOString(),
    properties,
    route: getRouteInfo(),
    user: userContext?.userId,
  };

  eventQueue.push(event);
  startFlushTimer();

  breadcrumb(`Event: ${eventName}`, 'event', properties);
}

/**
 * Get or create session ID
 */
function getSessionId() {
  const key = 'aura_session_id';
  let sessionId = sessionStorage.getItem(key);

  if (!sessionId) {
    sessionId = `session-${Date.now()}-${crypto.getRandomValues(new Uint8Array(5)).reduce((s, b) => s + b.toString(36).padStart(2, '0'), '').substring(0, 7)}`;
    sessionStorage.setItem(key, sessionId);
  }

  return sessionId;
}

/**
 * Start the flush timer for batched sending
 */
function startFlushTimer() {
  if (flushTimer) return;

  flushTimer = setTimeout(() => {
    flush();
    flushTimer = null;
  }, CONFIG.flushInterval);
}

/**
 * Send error reports to the backend
 */
async function sendToBackend(reports) {
  if (reports.length === 0) return;

  try {
    await apiClient.post(CONFIG.endpoint, {
      reports,
      batchTimestamp: new Date().toISOString(),
      sessionId: getSessionId(),
    });
  } catch (error) {
    // Log locally but don't throw - we don't want error reporting to cause errors
    console.error('[ErrorTracking] Backend send failed:', error);

    // Store failed reports for retry on next flush
    if (error.status !== 429) {
      // Don't retry rate-limited requests
      errorQueue = [...reports.filter((r) => r.severity === 'error'), ...errorQueue];
    }
  }
}

/**
 * Force flush all pending errors, warnings, and events
 */
export async function flush() {
  if (flushTimer) {
    clearTimeout(flushTimer);
    flushTimer = null;
  }

  const errors = [...errorQueue];
  const warnings = [...warningQueue];
  const events = [...eventQueue];

  // Clear queues before sending (in case of errors)
  errorQueue = [];
  warningQueue = [];
  eventQueue = [];

  const allReports = [
    ...errors,
    ...warnings.map((w) => ({ ...w, type: 'warning' })),
    ...events.map((e) => ({ ...e, type: 'event' })),
  ];

  if (allReports.length > 0) {
    await sendToBackend(allReports);
  }
}

/**
 * Initialize performance monitoring
 * Tracks Core Web Vitals: LCP, FID, CLS
 */
export function initPerformanceMonitoring() {
  if (typeof PerformanceObserver === 'undefined') {
    console.warn('[ErrorTracking] PerformanceObserver not supported');
    return;
  }

  // Largest Contentful Paint (LCP)
  try {
    const lcpObserver = new PerformanceObserver((entryList) => {
      const entries = entryList.getEntries();
      const lastEntry = entries[entries.length - 1];

      trackEvent('performance:lcp', {
        value: lastEntry.startTime,
        element: lastEntry.element?.tagName,
        url: lastEntry.url,
      });
    });
    lcpObserver.observe({ type: 'largest-contentful-paint', buffered: true });
  } catch {
    // LCP not supported
  }

  // First Input Delay (FID)
  try {
    const fidObserver = new PerformanceObserver((entryList) => {
      const entries = entryList.getEntries();
      entries.forEach((entry) => {
        trackEvent('performance:fid', {
          value: entry.processingStart - entry.startTime,
          name: entry.name,
        });
      });
    });
    fidObserver.observe({ type: 'first-input', buffered: true });
  } catch {
    // FID not supported
  }

  // Cumulative Layout Shift (CLS)
  try {
    let clsValue = 0;
    const clsObserver = new PerformanceObserver((entryList) => {
      for (const entry of entryList.getEntries()) {
        if (!entry.hadRecentInput) {
          clsValue += entry.value;
        }
      }
    });
    clsObserver.observe({ type: 'layout-shift', buffered: true });

    // Report CLS on page hide
    window.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') {
        trackEvent('performance:cls', { value: clsValue });
      }
    });
  } catch {
    // CLS not supported
  }

  // Long tasks (>50ms)
  try {
    const longTaskObserver = new PerformanceObserver((entryList) => {
      entryList.getEntries().forEach((entry) => {
        if (entry.duration > 100) {
          // Only report tasks > 100ms
          breadcrumb(`Long task detected: ${entry.duration.toFixed(0)}ms`, 'performance');
        }
      });
    });
    longTaskObserver.observe({ type: 'longtask', buffered: true });
  } catch {
    // Long tasks not supported
  }
}

/**
 * Setup global error handlers
 * Should be called once at app initialization
 */
export function setupGlobalHandlers() {
  // Global error handler
  const originalOnError = window.onerror;
  window.onerror = function (message, source, lineno, colno, error) {
    reportError(
      error || new Error(message),
      null,
      {
        source,
        lineno,
        colno,
        type: 'window.onerror',
      }
    );

    if (originalOnError) {
      return originalOnError.apply(this, arguments);
    }
    return false;
  };

  // Unhandled promise rejection handler
  const originalOnUnhandledRejection = window.onunhandledrejection;
  window.onunhandledrejection = function (event) {
    const error =
      event.reason instanceof Error
        ? event.reason
        : new Error(String(event.reason) || 'Unhandled Promise Rejection');

    reportError(error, null, {
      type: 'unhandledrejection',
      promiseReason: String(event.reason),
    });

    if (originalOnUnhandledRejection) {
      return originalOnUnhandledRejection.apply(this, arguments);
    }
  };

  // Capture console.error calls
  const originalConsoleError = console.error;
  console.error = function (...args) {
    // Add breadcrumb but don't report as full error
    breadcrumb(args.map(String).join(' '), 'console', { level: 'error' }, 'error');
    return originalConsoleError.apply(console, args);
  };

  // Capture console.warn calls
  const originalConsoleWarn = console.warn;
  console.warn = function (...args) {
    breadcrumb(args.map(String).join(' '), 'console', { level: 'warn' }, 'warning');
    return originalConsoleWarn.apply(console, args);
  };

  // Flush on page unload
  window.addEventListener('beforeunload', () => {
    flush();
  });

  // Flush on visibility change (when page goes to background)
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') {
      flush();
    }
  });
}

/**
 * Track route changes for breadcrumb history
 * Call this in your router's navigation listener
 *
 * @param {string} from - Previous route
 * @param {string} to - New route
 */
export function trackRouteChange(from, to) {
  breadcrumb(`Navigated: ${from} -> ${to}`, 'navigation', { from, to });
}

/**
 * Track HTTP requests for debugging
 *
 * @param {string} method - HTTP method
 * @param {string} url - Request URL
 * @param {number} status - Response status
 * @param {number} duration - Request duration in ms
 */
export function trackHttpRequest(method, url, status, duration) {
  const level = status >= 400 ? 'error' : 'info';
  breadcrumb(`${method} ${url} - ${status} (${duration}ms)`, 'http', { method, url, status, duration }, level);
}

/**
 * Track user interactions
 *
 * @param {string} action - Action type (click, input, etc.)
 * @param {string} target - Target description
 * @param {Object} data - Additional data
 */
export function trackInteraction(action, target, data = {}) {
  breadcrumb(`${action}: ${target}`, 'user', { action, target, ...data });
}

// Export all functions as named exports and as default object
export default {
  reportError,
  reportWarning,
  setUserContext,
  clearUserContext,
  trackEvent,
  breadcrumb,
  flush,
  setupGlobalHandlers,
  initPerformanceMonitoring,
  trackRouteChange,
  trackHttpRequest,
  trackInteraction,
  generateErrorId,
};
