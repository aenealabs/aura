import { useState, useCallback, useRef, useEffect } from 'react';

/**
 * useVoiceInput Hook - Web Speech API integration for voice input
 *
 * Features:
 * - Speech recognition with real-time transcription
 * - Browser compatibility detection (Chrome, Edge, Safari)
 * - Continuous listening mode
 * - Auto-stop on silence
 * - Error handling with user-friendly messages
 *
 * Issue: #20 - Frontend production polish
 *
 * Usage:
 *   const {
 *     isListening,
 *     transcript,
 *     isSupported,
 *     error,
 *     startListening,
 *     stopListening,
 *     resetTranscript,
 *   } = useVoiceInput({ onResult: (text) => setMessage(text) });
 */

// Check for browser support
const SpeechRecognition =
  typeof window !== 'undefined' &&
  (window.SpeechRecognition ||
    window.webkitSpeechRecognition ||
    window.mozSpeechRecognition ||
    window.msSpeechRecognition);

/**
 * Get browser name for compatibility messages
 */
function getBrowserInfo() {
  const ua = navigator.userAgent;
  if (ua.includes('Chrome') && !ua.includes('Edg')) return { name: 'Chrome', supported: true };
  if (ua.includes('Edg')) return { name: 'Edge', supported: true };
  if (ua.includes('Safari') && !ua.includes('Chrome')) return { name: 'Safari', supported: true };
  if (ua.includes('Firefox')) return { name: 'Firefox', supported: false };
  return { name: 'Unknown', supported: false };
}

/**
 * Error messages for different error types
 */
const ERROR_MESSAGES = {
  'not-allowed': 'Microphone access was denied. Please enable microphone permissions in your browser settings.',
  'no-speech': 'No speech was detected. Please try speaking again.',
  'audio-capture': 'No microphone was found. Please connect a microphone and try again.',
  'network': 'A network error occurred. Please check your connection and try again.',
  'aborted': 'Speech recognition was stopped.',
  'service-not-allowed': 'Speech recognition service is not available. Please try again later.',
  'language-not-supported': 'The selected language is not supported.',
  'not-supported': 'Voice input is not supported in your browser. Please try Chrome, Edge, or Safari.',
  default: 'An error occurred with voice input. Please try again.',
};

/**
 * Main useVoiceInput hook
 */
export function useVoiceInput(options = {}) {
  const {
    language = 'en-US',
    continuous = true,
    interimResults = true,
    onResult,
    onError,
    autoStopTimeout = 3000, // Auto-stop after 3 seconds of silence
  } = options;

  // State
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [interimTranscript, setInterimTranscript] = useState('');
  const [error, setError] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);

  // Refs
  const recognitionRef = useRef(null);
  const autoStopTimerRef = useRef(null);
  const mountedRef = useRef(true);

  // Check browser support
  const isSupported = Boolean(SpeechRecognition);
  const browserInfo = getBrowserInfo();

  // Cleanup on unmount
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (recognitionRef.current) {
        recognitionRef.current.abort();
      }
      if (autoStopTimerRef.current) {
        clearTimeout(autoStopTimerRef.current);
      }
    };
  }, []);

  // Reset auto-stop timer
  const resetAutoStopTimer = useCallback(() => {
    if (autoStopTimerRef.current) {
      clearTimeout(autoStopTimerRef.current);
    }
    if (autoStopTimeout > 0) {
      autoStopTimerRef.current = setTimeout(() => {
        if (mountedRef.current && recognitionRef.current) {
          recognitionRef.current.stop();
        }
      }, autoStopTimeout);
    }
  }, [autoStopTimeout]);

  // Initialize recognition instance
  const initRecognition = useCallback(() => {
    if (!SpeechRecognition) return null;

    const recognition = new SpeechRecognition();

    // Configuration
    recognition.lang = language;
    recognition.continuous = continuous;
    recognition.interimResults = interimResults;
    recognition.maxAlternatives = 1;

    // Event handlers
    recognition.onstart = () => {
      if (mountedRef.current) {
        setIsListening(true);
        setError(null);
        setIsProcessing(false);
        resetAutoStopTimer();
      }
    };

    recognition.onend = () => {
      if (mountedRef.current) {
        setIsListening(false);
        setInterimTranscript('');
        if (autoStopTimerRef.current) {
          clearTimeout(autoStopTimerRef.current);
        }
      }
    };

    recognition.onresult = (event) => {
      if (!mountedRef.current) return;

      let finalTranscript = '';
      let currentInterim = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const text = result[0].transcript;

        if (result.isFinal) {
          finalTranscript += text;
        } else {
          currentInterim += text;
        }
      }

      // Update interim transcript
      setInterimTranscript(currentInterim);

      // Update final transcript
      if (finalTranscript) {
        setTranscript((prev) => {
          const newTranscript = prev + (prev ? ' ' : '') + finalTranscript.trim();
          onResult?.(newTranscript);
          return newTranscript;
        });
      }

      // Reset auto-stop timer on activity
      resetAutoStopTimer();
    };

    recognition.onerror = (event) => {
      if (!mountedRef.current) return;

      const errorMessage = ERROR_MESSAGES[event.error] || ERROR_MESSAGES.default;
      setError(errorMessage);
      setIsListening(false);
      setIsProcessing(false);
      onError?.(event.error, errorMessage);

      // Don't log aborted errors (these are intentional)
      if (event.error !== 'aborted') {
        console.warn('Speech recognition error:', event.error);
      }
    };

    recognition.onnomatch = () => {
      if (mountedRef.current) {
        setError(ERROR_MESSAGES['no-speech']);
      }
    };

    recognition.onaudiostart = () => {
      if (mountedRef.current) {
        setIsProcessing(true);
      }
    };

    recognition.onaudioend = () => {
      if (mountedRef.current) {
        setIsProcessing(false);
      }
    };

    return recognition;
  }, [language, continuous, interimResults, onResult, onError, resetAutoStopTimer]);

  // Start listening
  const startListening = useCallback(async () => {
    if (!isSupported) {
      setError(ERROR_MESSAGES['not-supported']);
      return false;
    }

    // Stop any existing recognition
    if (recognitionRef.current) {
      recognitionRef.current.abort();
    }

    try {
      // Request microphone permission first
      await navigator.mediaDevices.getUserMedia({ audio: true });

      // Create and start recognition
      recognitionRef.current = initRecognition();
      if (recognitionRef.current) {
        recognitionRef.current.start();
        return true;
      }
    } catch (err) {
      const errorMessage =
        err.name === 'NotAllowedError'
          ? ERROR_MESSAGES['not-allowed']
          : err.name === 'NotFoundError'
            ? ERROR_MESSAGES['audio-capture']
            : ERROR_MESSAGES.default;

      setError(errorMessage);
      onError?.(err.name, errorMessage);
      return false;
    }

    return false;
  }, [isSupported, initRecognition, onError]);

  // Stop listening
  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
    if (autoStopTimerRef.current) {
      clearTimeout(autoStopTimerRef.current);
    }
  }, []);

  // Toggle listening
  const toggleListening = useCallback(() => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  }, [isListening, startListening, stopListening]);

  // Reset transcript
  const resetTranscript = useCallback(() => {
    setTranscript('');
    setInterimTranscript('');
    setError(null);
  }, []);

  // Abort recognition (cancel without triggering end event handling)
  const abortListening = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.abort();
    }
    if (autoStopTimerRef.current) {
      clearTimeout(autoStopTimerRef.current);
    }
    setIsListening(false);
    setInterimTranscript('');
  }, []);

  return {
    // State
    isListening,
    isProcessing,
    transcript,
    interimTranscript,
    fullTranscript: transcript + (interimTranscript ? ' ' + interimTranscript : ''),
    error,

    // Browser info
    isSupported,
    browserInfo,

    // Actions
    startListening,
    stopListening,
    toggleListening,
    resetTranscript,
    abortListening,
  };
}

/**
 * VoiceInputIndicator - Visual indicator component for voice recording state
 */
export function VoiceInputIndicator({ isListening, isProcessing }) {
  if (!isListening) return null;

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 bg-critical-50 dark:bg-critical-900/30 rounded-lg animate-pulse">
      <div className="relative">
        <span className="absolute inset-0 rounded-full bg-critical-500 animate-ping opacity-75" />
        <span className="relative block w-3 h-3 rounded-full bg-critical-500" />
      </div>
      <span className="text-xs font-medium text-critical-600 dark:text-critical-400">
        {isProcessing ? 'Listening...' : 'Starting...'}
      </span>
    </div>
  );
}

/**
 * Unsupported browser message component
 */
export function VoiceInputUnsupportedMessage({ browserInfo }) {
  return (
    <div className="p-3 bg-warning-50 dark:bg-warning-900/20 rounded-lg border border-warning-200 dark:border-warning-800">
      <p className="text-sm text-warning-700 dark:text-warning-400">
        Voice input is not supported in {browserInfo.name}.
      </p>
      <p className="text-xs text-warning-600 dark:text-warning-500 mt-1">
        Please use Chrome, Edge, or Safari for voice input functionality.
      </p>
    </div>
  );
}

export default useVoiceInput;
