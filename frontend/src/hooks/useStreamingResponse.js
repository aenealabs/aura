import { useState, useCallback, useRef, useEffect } from 'react';

/**
 * useStreamingResponse - Hook for handling Server-Sent Events (SSE) streaming
 *
 * Provides a complete solution for streaming text responses from LLM APIs:
 * - Real-time token-by-token streaming
 * - Abort controller for cancellation
 * - Automatic reconnection with exponential backoff
 * - Progress indication
 * - Error handling and recovery
 *
 * Usage:
 * ```jsx
 * const {
 *   content,
 *   isStreaming,
 *   error,
 *   startStream,
 *   cancel,
 *   reset
 * } = useStreamingResponse();
 *
 * // Start streaming
 * await startStream(sendMessageFn, [message, attachments]);
 * ```
 */

// Reconnection configuration
const MAX_RECONNECT_ATTEMPTS = 3;
const INITIAL_RECONNECT_DELAY = 1000;
const MAX_RECONNECT_DELAY = 10000;

/**
 * Main streaming response hook
 */
export function useStreamingResponse(options = {}) {
  const {
    onToken,
    onComplete,
    onError,
    onToolCall,
    autoReconnect = true,
    maxReconnectAttempts = MAX_RECONNECT_ATTEMPTS,
  } = options;

  // State
  const [content, setContent] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState(0);
  const [tokenCount, setTokenCount] = useState(0);
  const [metadata, setMetadata] = useState(null);

  // Refs for cleanup and reconnection
  const abortControllerRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef(null);
  const streamFnRef = useRef(null);
  const streamArgsRef = useRef(null);
  const isMountedRef = useRef(true);

  // Cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      cancel();
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * Cancel the current stream
   */
  const cancel = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (isMountedRef.current) {
      setIsStreaming(false);
      setIsPaused(false);
    }
  }, []);

  /**
   * Reset the hook state
   */
  const reset = useCallback(() => {
    cancel();
    setContent('');
    setError(null);
    setProgress(0);
    setTokenCount(0);
    setMetadata(null);
    reconnectAttemptsRef.current = 0;
  }, [cancel]);

  /**
   * Calculate reconnection delay with exponential backoff
   */
  const getReconnectDelay = useCallback(() => {
    const attempt = reconnectAttemptsRef.current;
    const delay = INITIAL_RECONNECT_DELAY * Math.pow(2, attempt);
    // Add jitter (0-25%)
    const jitter = delay * Math.random() * 0.25;
    return Math.min(delay + jitter, MAX_RECONNECT_DELAY);
  }, []);

  /**
   * Attempt to reconnect after a failure
   */
  const attemptReconnect = useCallback(() => {
    if (!autoReconnect) return false;
    if (reconnectAttemptsRef.current >= maxReconnectAttempts) return false;
    if (!streamFnRef.current || !streamArgsRef.current) return false;

    reconnectAttemptsRef.current += 1;
    const delay = getReconnectDelay();

    console.warn(
      `Attempting reconnect in ${Math.round(delay)}ms (attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts})`
    );

    reconnectTimeoutRef.current = setTimeout(() => {
      if (isMountedRef.current) {
        startStream(streamFnRef.current, streamArgsRef.current, { isRetry: true });
      }
    }, delay);

    return true;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoReconnect, maxReconnectAttempts, getReconnectDelay]);

  /**
   * Start streaming with the provided function
   *
   * @param {Function} streamFn - Async function that handles streaming (e.g., chatApi.sendMessage)
   * @param {Array} args - Arguments to pass to streamFn
   * @param {Object} internalOptions - Internal options for retry logic
   */
  const startStream = useCallback(
    async (streamFn, args = [], internalOptions = {}) => {
      const { isRetry = false } = internalOptions;

      // Store for potential reconnection
      streamFnRef.current = streamFn;
      streamArgsRef.current = args;

      // Cancel any existing stream
      cancel();

      // Create new abort controller
      abortControllerRef.current = new AbortController();

      // Reset state for new stream (but preserve content on retry)
      if (!isRetry) {
        setContent('');
        setTokenCount(0);
        setMetadata(null);
        reconnectAttemptsRef.current = 0;
      }
      setError(null);
      setIsStreaming(true);
      setProgress(0);

      try {
        // Build options with callbacks
        const streamOptions = {
          signal: abortControllerRef.current.signal,
          onToken: (token, fullContent) => {
            if (!isMountedRef.current) return;

            setContent(fullContent);
            setTokenCount((prev) => prev + 1);

            // Estimate progress (approximate based on typical response length)
            const estimatedMaxTokens = 500;
            setProgress(Math.min((tokenCount / estimatedMaxTokens) * 100, 95));

            onToken?.(token, fullContent);
          },
          onToolCall: (toolCall) => {
            if (!isMountedRef.current) return;
            onToolCall?.(toolCall);
          },
          onComplete: (result) => {
            if (!isMountedRef.current) return;

            setIsStreaming(false);
            setProgress(100);
            setMetadata({
              messageId: result.messageId,
              conversationId: result.conversationId,
              modelId: result.modelId,
              tokenUsage: result.tokenUsage,
            });
            reconnectAttemptsRef.current = 0;

            onComplete?.(result);
          },
          onError: (_err) => {
            if (!isMountedRef.current) return;
            // Error handled below
          },
        };

        // Call the streaming function with args and options
        const result = await streamFn(...args, streamOptions);
        return result;
      } catch (err) {
        if (!isMountedRef.current) return;

        // Handle abort
        if (err.name === 'AbortError') {
          setIsStreaming(false);
          return;
        }

        // Set error state
        setError(err);
        setIsStreaming(false);

        // Attempt reconnection for retryable errors
        if (err.isRetryable && attemptReconnect()) {
          return;
        }

        // Call error callback
        onError?.(err);
        throw err;
      }
    },
    [cancel, onToken, onComplete, onError, onToolCall, attemptReconnect, tokenCount]
  );

  /**
   * Pause the stream (if supported by the API)
   * Note: SSE doesn't support true pause, this is a visual state only
   */
  const pause = useCallback(() => {
    setIsPaused(true);
  }, []);

  /**
   * Resume the stream
   */
  const resume = useCallback(() => {
    setIsPaused(false);
  }, []);

  return {
    // State
    content,
    isStreaming,
    isPaused,
    error,
    progress,
    tokenCount,
    metadata,

    // Actions
    startStream,
    cancel,
    reset,
    pause,
    resume,

    // Computed
    hasContent: content.length > 0,
    isComplete: !isStreaming && content.length > 0 && !error,
    reconnectAttempts: reconnectAttemptsRef.current,
  };
}

/**
 * useStreamingText - Simplified hook for streaming text with typing effect
 *
 * Provides a "typewriter" effect for displaying streamed text character by character.
 */
export function useStreamingText(options = {}) {
  const { typingSpeed = 15, onComplete } = options;

  const [displayedText, setDisplayedText] = useState('');
  const [targetText, setTargetText] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const typingIntervalRef = useRef(null);

  // Clear typing interval on unmount
  useEffect(() => {
    return () => {
      if (typingIntervalRef.current) {
        clearInterval(typingIntervalRef.current);
      }
    };
  }, []);

  // Handle typing animation when target text changes
  useEffect(() => {
    if (targetText.length <= displayedText.length) return;

    setIsTyping(true);

    // Clear any existing interval
    if (typingIntervalRef.current) {
      clearInterval(typingIntervalRef.current);
    }

    let currentIndex = displayedText.length;

    typingIntervalRef.current = setInterval(() => {
      if (currentIndex < targetText.length) {
        setDisplayedText(targetText.slice(0, currentIndex + 1));
        currentIndex++;
      } else {
        clearInterval(typingIntervalRef.current);
        typingIntervalRef.current = null;
        setIsTyping(false);
        onComplete?.();
      }
    }, typingSpeed);

    return () => {
      if (typingIntervalRef.current) {
        clearInterval(typingIntervalRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetText, typingSpeed, onComplete]);

  const setContent = useCallback((text) => {
    setTargetText(text);
  }, []);

  const setContentImmediate = useCallback((text) => {
    if (typingIntervalRef.current) {
      clearInterval(typingIntervalRef.current);
      typingIntervalRef.current = null;
    }
    setTargetText(text);
    setDisplayedText(text);
    setIsTyping(false);
  }, []);

  const reset = useCallback(() => {
    if (typingIntervalRef.current) {
      clearInterval(typingIntervalRef.current);
      typingIntervalRef.current = null;
    }
    setDisplayedText('');
    setTargetText('');
    setIsTyping(false);
  }, []);

  return {
    text: displayedText,
    isTyping,
    setContent,
    setContentImmediate,
    reset,
    progress: targetText.length > 0 ? (displayedText.length / targetText.length) * 100 : 0,
  };
}

/**
 * useSSEConnection - Low-level hook for managing SSE connections
 *
 * Use this for more granular control over SSE connections.
 */
export function useSSEConnection(url, options = {}) {
  const {
    onMessage,
    onOpen,
    onError,
    autoConnect = false,
    reconnect = true,
    maxReconnectAttempts = 3,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState(null);

  const eventSourceRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  const isMountedRef = useRef(true);

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const connect = useCallback(() => {
    disconnect();
    setError(null);

    try {
      const eventSource = new EventSource(url);
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        if (!isMountedRef.current) return;
        setIsConnected(true);
        reconnectAttemptsRef.current = 0;
        onOpen?.();
      };

      eventSource.onmessage = (event) => {
        if (!isMountedRef.current) return;
        try {
          const data = JSON.parse(event.data);
          onMessage?.(data);
        } catch (e) {
          onMessage?.(event.data);
        }
      };

      eventSource.onerror = (_event) => {
        if (!isMountedRef.current) return;

        const err = new Error('SSE connection error');
        setError(err);
        setIsConnected(false);
        onError?.(err);

        // Attempt reconnection
        if (
          reconnect &&
          reconnectAttemptsRef.current < maxReconnectAttempts
        ) {
          reconnectAttemptsRef.current++;
          const delay = Math.min(
            1000 * Math.pow(2, reconnectAttemptsRef.current),
            10000
          );
          setTimeout(() => {
            if (isMountedRef.current) {
              connect();
            }
          }, delay);
        }
      };
    } catch (err) {
      setError(err);
      onError?.(err);
    }
  }, [url, disconnect, onMessage, onOpen, onError, reconnect, maxReconnectAttempts]);

  // Auto-connect on mount if enabled
  useEffect(() => {
    if (autoConnect) {
      connect();
    }
    return () => {
      isMountedRef.current = false;
      disconnect();
    };
  }, [autoConnect, connect, disconnect]);

  return {
    isConnected,
    error,
    connect,
    disconnect,
    reconnectAttempts: reconnectAttemptsRef.current,
  };
}

export default useStreamingResponse;
