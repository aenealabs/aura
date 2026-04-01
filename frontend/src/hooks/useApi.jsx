import { useState, useCallback, useRef, useEffect } from 'react';

/**
 * useApi Hook - API request handler with retry logic and state management
 *
 * Features:
 * - Automatic retry with exponential backoff
 * - Loading, error, and success states
 * - Request cancellation
 * - Offline detection
 *
 * Issue: #20 - Frontend production polish
 *
 * Usage:
 *   const { data, loading, error, execute, retry } = useApi(fetchUsers);
 *   const { data, execute } = useApi(createUser, { manual: true });
 */

const DEFAULT_RETRY_COUNT = 3;
const DEFAULT_RETRY_DELAY = 1000;
const MAX_RETRY_DELAY = 30000;

/**
 * Check if error is retryable
 */
function isRetryableError(error) {
  // Network errors
  if (!navigator.onLine) return true;
  if (error.message === 'Network Error') return true;
  if (error.code === 'ECONNABORTED') return true;

  // Server errors (5xx) are retryable
  if (error.response?.status >= 500) return true;

  // Rate limiting (429) is retryable
  if (error.response?.status === 429) return true;

  // Client errors (4xx except 429) are not retryable
  if (error.response?.status >= 400 && error.response?.status < 500) return false;

  return true;
}

/**
 * Calculate delay with exponential backoff
 */
function getRetryDelay(attempt, baseDelay = DEFAULT_RETRY_DELAY) {
  const delay = baseDelay * Math.pow(2, attempt);
  // Add jitter (±25%)
  const jitter = delay * 0.25 * (Math.random() * 2 - 1);
  return Math.min(delay + jitter, MAX_RETRY_DELAY);
}

/**
 * Main useApi hook
 */
export function useApi(apiFunction, options = {}) {
  const {
    manual = false,
    retries = DEFAULT_RETRY_COUNT,
    retryDelay = DEFAULT_RETRY_DELAY,
    onSuccess,
    onError,
    initialData = null,
  } = options;

  const [state, setState] = useState({
    data: initialData,
    loading: !manual,
    error: null,
    isSuccess: false,
    isError: false,
  });

  const abortControllerRef = useRef(null);
  const mountedRef = useRef(true);
  const retryCountRef = useRef(0);

  // Cleanup on unmount
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      abortControllerRef.current?.abort();
    };
  }, []);

  const execute = useCallback(async (...args) => {
    // Cancel any pending request
    abortControllerRef.current?.abort();
    abortControllerRef.current = new AbortController();

    setState((prev) => ({
      ...prev,
      loading: true,
      error: null,
      isSuccess: false,
      isError: false,
    }));

    retryCountRef.current = 0;

    const attemptRequest = async () => {
      try {
        const result = await apiFunction(...args, {
          signal: abortControllerRef.current?.signal,
        });

        if (!mountedRef.current) return;

        setState({
          data: result,
          loading: false,
          error: null,
          isSuccess: true,
          isError: false,
        });

        onSuccess?.(result);
        return result;
      } catch (error) {
        if (!mountedRef.current) return;

        // Don't retry if request was cancelled
        if (error.name === 'AbortError' || error.name === 'CanceledError') {
          return;
        }

        // Check if we should retry
        if (isRetryableError(error) && retryCountRef.current < retries) {
          retryCountRef.current += 1;
          const delay = getRetryDelay(retryCountRef.current, retryDelay);

          console.warn(
            `API request failed, retrying in ${Math.round(delay)}ms (attempt ${retryCountRef.current}/${retries})`,
            error.message
          );

          await new Promise((resolve) => setTimeout(resolve, delay));

          if (mountedRef.current) {
            return attemptRequest();
          }
        }

        // Max retries reached or non-retryable error
        setState({
          data: null,
          loading: false,
          error,
          isSuccess: false,
          isError: true,
        });

        onError?.(error);
        throw error;
      }
    };

    return attemptRequest();
  }, [apiFunction, retries, retryDelay, onSuccess, onError]);

  // Auto-execute on mount if not manual
  useEffect(() => {
    if (!manual) {
      execute().catch(() => {
        // Error is already handled in state
      });
    }
  }, [manual, execute]);

  const retry = useCallback(() => {
    retryCountRef.current = 0;
    return execute();
  }, [execute]);

  const reset = useCallback(() => {
    abortControllerRef.current?.abort();
    setState({
      data: initialData,
      loading: false,
      error: null,
      isSuccess: false,
      isError: false,
    });
  }, [initialData]);

  const cancel = useCallback(() => {
    abortControllerRef.current?.abort();
    setState((prev) => ({
      ...prev,
      loading: false,
    }));
  }, []);

  return {
    ...state,
    execute,
    retry,
    reset,
    cancel,
    isLoading: state.loading,
  };
}

/**
 * useMutation hook for POST/PUT/DELETE operations
 */
export function useMutation(mutationFn, options = {}) {
  return useApi(mutationFn, { manual: true, ...options });
}

/**
 * useQuery hook for GET operations (auto-execute)
 */
export function useQuery(queryFn, options = {}) {
  return useApi(queryFn, { manual: false, ...options });
}

/**
 * Hook to detect online/offline status
 */
export function useOnlineStatus() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  return isOnline;
}

/**
 * Offline Banner Component
 */
export function OfflineBanner() {
  const isOnline = useOnlineStatus();

  if (isOnline) return null;

  return (
    <div className="fixed bottom-0 inset-x-0 z-50 bg-warning-500 text-white px-4 py-2 text-center text-sm font-medium">
      <span className="flex items-center justify-center gap-2">
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 5.636a9 9 0 010 12.728m0 0l-2.829-2.829m2.829 2.829L21 21M15.536 8.464a5 5 0 010 7.072m0 0l-2.829-2.829m-4.243 2.829a4.978 4.978 0 01-1.414-2.83m-1.414 5.658a9 9 0 01-2.167-9.238m7.824 2.167a1 1 0 111.414 1.414m-1.414-1.414L3 3m8.293 8.293l1.414 1.414" />
        </svg>
        You are offline. Some features may be unavailable.
      </span>
    </div>
  );
}

export default useApi;
