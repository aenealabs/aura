/**
 * Project Aura - Documentation Data Hook
 *
 * Custom React hook for generating and managing documentation data.
 * Supports streaming progress updates, caching, and feedback submission.
 *
 * ADR-056: Documentation Agent for Architecture and Data Flow Diagrams.
 * ADR-060: Enterprise Diagram Generation with professional SVG support.
 *
 * @module hooks/useDocumentationData
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import {
  generateDocumentation,
  generateDocumentationStream,
  submitFeedback,
  getCacheStats,
  invalidateCache,
  getDiagramTypes,
  getConfidenceLevel,
  DocumentationApiError,
  GenerationMode,
  RenderEngine,
} from '../services/documentationApi';

/**
 * @typedef {Object} DocumentationState
 * @property {Object|null} result - Generated documentation result
 * @property {Array|null} diagrams - Generated diagrams
 * @property {Object|null} report - Technical report
 * @property {Array|null} serviceBoundaries - Detected service boundaries
 * @property {number|null} confidence - Overall confidence score
 */

/**
 * @typedef {Object} ProgressState
 * @property {string} phase - Current generation phase
 * @property {number} progress - Progress percentage (0-100)
 * @property {string} message - Status message
 * @property {number} currentStep - Current step number
 * @property {number} totalSteps - Total steps
 */

/**
 * Custom hook for documentation generation and management.
 *
 * Features:
 * - Streaming progress updates during generation
 * - Result caching with invalidation
 * - Feedback submission for calibration
 * - AbortController for cancellation
 * - Auto-retry on retryable errors
 *
 * @param {Object} [options] - Hook options
 * @param {boolean} [options.streaming=true] - Enable streaming progress
 * @param {number} [options.retryAttempts=3] - Number of retry attempts
 * @returns {Object} Documentation data and control functions
 *
 * @example
 * const {
 *   generate,
 *   result,
 *   progress,
 *   loading,
 *   error,
 *   cancel,
 * } = useDocumentationData();
 *
 * // Generate with streaming
 * await generate('my-repo-id', { diagramTypes: ['architecture'] });
 */
export function useDocumentationData(options = {}) {
  const { streaming = true, retryAttempts = 3 } = options;

  // Result state
  const [result, setResult] = useState(null);

  // Progress state for streaming
  const [progress, setProgress] = useState({
    phase: 'idle',
    progress: 0,
    message: '',
    currentStep: 0,
    totalSteps: 0,
  });

  // Loading and error states
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Diagram types state
  const [diagramTypes, setDiagramTypes] = useState([]);
  const [diagramTypesLoading, setDiagramTypesLoading] = useState(false);

  // Cache stats state
  const [cacheStats, setCacheStats] = useState(null);

  // Refs for cleanup and cancellation
  const mountedRef = useRef(true);
  const abortControllerRef = useRef(null);
  const retryCountRef = useRef(0);

  /**
   * Generate documentation for a repository
   *
   * @param {string} repositoryId - Repository ID to generate docs for
   * @param {Object} genOptions - Generation options
   * @returns {Promise<Object>} Documentation result
   */
  const generate = useCallback(
    async (repositoryId, genOptions = {}) => {
      if (!mountedRef.current) return null;

      // Cancel any pending request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      abortControllerRef.current = new AbortController();

      setLoading(true);
      setError(null);
      setProgress({
        phase: 'starting',
        progress: 0,
        message: 'Starting documentation generation...',
        currentStep: 0,
        totalSteps: 4,
      });

      // ADR-060: Determine effective mode first to auto-select render engine
      const effectiveMode = genOptions.mode || GenerationMode.CODE_ANALYSIS;

      const {
        diagramTypes: types = ['architecture', 'data_flow'],
        includeReport = true,
        maxServices = 20,
        minConfidence = 0.45,
        // ADR-060: Professional diagram generation parameters
        mode = GenerationMode.CODE_ANALYSIS,
        prompt = '',
        // ADR-060: Auto-select 'eraser' render engine for AI_PROMPT mode
        // to generate professional SVG diagrams with cloud provider icons
        renderEngine = effectiveMode === GenerationMode.AI_PROMPT
          ? RenderEngine.ERASER
          : RenderEngine.MERMAID,
      } = genOptions;

      try {
        let docResult;

        // ADR-060: AI_PROMPT mode uses non-streaming endpoint (POST with prompt body)
        // Streaming is only for CODE_ANALYSIS mode which uses GET with query params
        const useStreaming = streaming && mode !== GenerationMode.AI_PROMPT;

        if (useStreaming) {
          // Use streaming endpoint for real-time progress (CODE_ANALYSIS mode only)
          docResult = await generateDocumentationStream(repositoryId, {
            diagramTypes: Array.isArray(types) ? types.join(',') : types,
            includeReport,
            signal: abortControllerRef.current.signal,
            onProgress: (progressData) => {
              if (mountedRef.current) {
                setProgress(progressData);
              }
            },
            onComplete: (completeResult) => {
              if (mountedRef.current) {
                setResult(completeResult);
                setProgress({
                  phase: 'complete',
                  progress: 100,
                  message: 'Documentation complete',
                  currentStep: 4,
                  totalSteps: 4,
                });
              }
            },
            onError: (err) => {
              if (mountedRef.current) {
                setError(err);
                setProgress({
                  phase: 'error',
                  progress: 0,
                  message: err.message,
                  currentStep: 0,
                  totalSteps: 4,
                });
              }
            },
          });
        } else {
          // Use non-streaming endpoint
          // ADR-060: Pass mode, prompt, and renderEngine for professional diagrams
          docResult = await generateDocumentation(repositoryId, {
            diagramTypes: types,
            includeReport,
            maxServices,
            minConfidence,
            mode,
            prompt,
            renderEngine,
          });

          if (mountedRef.current) {
            setResult(docResult);
            setProgress({
              phase: 'complete',
              progress: 100,
              message: 'Documentation complete',
              currentStep: 4,
              totalSteps: 4,
            });
          }
        }

        retryCountRef.current = 0;
        return docResult;
      } catch (err) {
        if (err.name === 'AbortError') {
          // Request was cancelled, don't treat as error
          return null;
        }

        // Handle retryable errors
        if (
          err instanceof DocumentationApiError &&
          err.isRetryable &&
          retryCountRef.current < retryAttempts
        ) {
          retryCountRef.current += 1;
          console.warn(
            `Documentation generation failed, retrying (${retryCountRef.current}/${retryAttempts})...`
          );

          // Exponential backoff
          await new Promise((resolve) =>
            setTimeout(resolve, Math.pow(2, retryCountRef.current) * 1000)
          );

          return generate(repositoryId, genOptions);
        }

        if (mountedRef.current) {
          setError(err);
          setProgress({
            phase: 'error',
            progress: 0,
            message: err.message || 'Generation failed',
            currentStep: 0,
            totalSteps: 4,
          });
        }

        throw err;
      } finally {
        if (mountedRef.current) {
          setLoading(false);
        }
      }
    },
    [streaming, retryAttempts]
  );

  /**
   * Cancel ongoing generation
   */
  const cancel = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }

    if (mountedRef.current) {
      setLoading(false);
      setProgress({
        phase: 'cancelled',
        progress: 0,
        message: 'Generation cancelled',
        currentStep: 0,
        totalSteps: 4,
      });
    }
  }, []);

  /**
   * Submit feedback for calibration
   *
   * @param {Object} feedbackData - Feedback data
   * @returns {Promise<Object>} Feedback response
   */
  const submitDocFeedback = useCallback(async (feedbackData) => {
    if (!result?.jobId) {
      throw new Error('No documentation job ID available');
    }

    return submitFeedback({
      jobId: result.jobId,
      ...feedbackData,
    });
  }, [result]);

  /**
   * Invalidate cache for a repository
   *
   * @param {string} repositoryId - Repository ID
   * @returns {Promise<Object>} Invalidation result
   */
  const invalidateRepoCache = useCallback(async (repositoryId) => {
    const invalidationResult = await invalidateCache(repositoryId);
    // Refresh cache stats after invalidation
    await refreshCacheStats();
    return invalidationResult;
  }, []);

  /**
   * Refresh cache statistics
   */
  const refreshCacheStats = useCallback(async () => {
    try {
      const stats = await getCacheStats();
      if (mountedRef.current) {
        setCacheStats(stats);
      }
      return stats;
    } catch (err) {
      console.error('Failed to fetch cache stats:', err);
      return null;
    }
  }, []);

  /**
   * Fetch available diagram types
   */
  const fetchDiagramTypes = useCallback(async () => {
    if (!mountedRef.current) return [];

    setDiagramTypesLoading(true);
    try {
      const types = await getDiagramTypes();
      if (mountedRef.current) {
        setDiagramTypes(types);
      }
      return types;
    } catch (err) {
      console.error('Failed to fetch diagram types:', err);
      return [];
    } finally {
      if (mountedRef.current) {
        setDiagramTypesLoading(false);
      }
    }
  }, []);

  /**
   * Clear current result and reset state
   */
  const clear = useCallback(() => {
    setResult(null);
    setError(null);
    setProgress({
      phase: 'idle',
      progress: 0,
      message: '',
      currentStep: 0,
      totalSteps: 0,
    });
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    mountedRef.current = true;

    return () => {
      mountedRef.current = false;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  // Fetch diagram types on mount
  useEffect(() => {
    fetchDiagramTypes();
  }, [fetchDiagramTypes]);

  // Computed properties
  const isGenerating = loading && progress.phase !== 'idle';
  const isComplete = progress.phase === 'complete';
  const hasError = error !== null;
  const confidenceLevel = result?.confidence ? getConfidenceLevel(result.confidence) : null;

  return {
    // Generation
    generate,
    cancel,
    clear,

    // Result data
    result,
    diagrams: result?.diagrams || [],
    report: result?.report || null,
    serviceBoundaries: result?.serviceBoundaries || [],
    confidence: result?.confidence || null,
    confidenceLevel,

    // Progress
    progress,
    isGenerating,
    isComplete,

    // Loading and error
    loading,
    error,
    hasError,

    // Feedback
    submitFeedback: submitDocFeedback,

    // Cache management
    cacheStats,
    refreshCacheStats,
    invalidateCache: invalidateRepoCache,

    // Diagram types
    diagramTypes,
    diagramTypesLoading,
    fetchDiagramTypes,
  };
}

/**
 * Hook for fetching documentation result by job ID.
 * Useful for retrieving previously generated documentation.
 *
 * @param {string} jobId - Documentation job ID
 * @returns {Object} Documentation result and loading state
 */
export function useDocumentationResult(jobId) {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(!!jobId);
  const [error, setError] = useState(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;

    if (!jobId) {
      setResult(null);
      setLoading(false);
      return;
    }

    // For now, we don't have a GET endpoint for fetching by job ID
    // The result would typically come from the generation process or cache
    // This is a placeholder for when that endpoint is added
    setLoading(false);

    return () => {
      mountedRef.current = false;
    };
  }, [jobId]);

  return {
    result,
    loading,
    error,
    confidenceLevel: result?.confidence ? getConfidenceLevel(result.confidence) : null,
  };
}

/**
 * Hook for managing cache statistics with auto-refresh.
 *
 * @param {Object} [options] - Hook options
 * @param {number} [options.refreshInterval=60000] - Refresh interval (default: 1 minute)
 * @returns {Object} Cache statistics and controls
 */
export function useCacheStats(options = {}) {
  const { refreshInterval = 60000 } = options;

  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const mountedRef = useRef(true);

  const fetchStats = useCallback(async () => {
    if (!mountedRef.current) return;

    setLoading(true);
    setError(null);

    try {
      const data = await getCacheStats();
      if (mountedRef.current) {
        setStats(data);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err);
        console.error('Failed to fetch cache stats:', err);
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchStats();

    const interval = setInterval(fetchStats, refreshInterval);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchStats, refreshInterval]);

  return {
    stats,
    loading,
    error,
    refetch: fetchStats,
  };
}

export default useDocumentationData;
