/**
 * Project Aura - GPU Workloads Context Provider
 *
 * Provides global state management for GPU workloads with real-time updates,
 * WebSocket integration, and job management.
 * ADR-061: GPU Workload Scheduler - Phase 3 Frontend Integration
 */

import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import {
  getGPUJobs,
  getGPUJob,
  submitGPUJob,
  cancelGPUJob,
  boostJobPriority,
  getGPUResources,
  getGPUQueueMetrics,
  getQueuePosition,
  estimateQueuePosition,
  getJobLogs,
  createGPUWebSocket,
  GPUWSMessageType,
  GPU_JOB_TYPES,
  GPU_JOB_PRIORITIES,
  GPU_ERROR_TYPES,
} from '../services/gpuSchedulerApi';

// Create context
const GPUWorkloadsContext = createContext(null);

// Polling interval for resources (10 seconds)
const RESOURCE_POLLING_INTERVAL = 10000;

// Polling interval for queue metrics (30 seconds)
const QUEUE_POLLING_INTERVAL = 30000;

/**
 * GPU Workloads Provider Component
 */
export function GPUWorkloadsProvider({ children }) {
  // Job list state
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Resource state
  const [resources, setResources] = useState({
    gpus_in_use: 0,
    gpus_total: 0,
    gpus_available: 0,
    queue_depth: 0,
    estimated_wait_minutes: 0,
    cost_today_usd: 0,
    cost_delta_percent: 0,
    nodes_active: 0,
    nodes_scaling: 0,
    gpu_utilization_percent: 0,
    gpu_memory_used_gb: 0,
    gpu_memory_total_gb: 0,
  });

  // Queue metrics state
  const [queueMetrics, setQueueMetrics] = useState({
    total_queued: 0,
    by_priority: { high: 0, normal: 0, low: 0 },
    by_organization: {},
    running_jobs: 0,
    running_by_priority: { high: 0, normal: 0, low: 0 },
    avg_wait_time_seconds: 0,
    oldest_queued_at: null,
    estimated_drain_time_minutes: 0,
    preemptions_last_hour: 0,
    starvation_promotions_last_hour: 0,
  });

  // Job logs state
  const [logs, setLogs] = useState([]);
  const [logsLoading, setLogsLoading] = useState(false);

  // Schedule modal state
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState(false);

  // WebSocket connection ref
  const wsRef = useRef(null);
  const wsReconnectTimeoutRef = useRef(null);

  // Polling refs
  const resourcePollingRef = useRef(null);
  const queuePollingRef = useRef(null);

  /**
   * Fetch all GPU jobs
   */
  const fetchJobs = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true);
    setError(null);

    try {
      const response = await getGPUJobs();
      setJobs(response.jobs || []);
    } catch (err) {
      console.error('Failed to fetch GPU jobs:', err);
      setError(err.message || 'Failed to fetch GPU jobs');
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Fetch GPU resources
   */
  const fetchResources = useCallback(async () => {
    try {
      const data = await getGPUResources();
      setResources(data);
    } catch (err) {
      console.error('Failed to fetch GPU resources:', err);
    }
  }, []);

  /**
   * Fetch queue metrics
   */
  const fetchQueueMetrics = useCallback(async () => {
    try {
      const data = await getGPUQueueMetrics();
      setQueueMetrics(data);
    } catch (err) {
      console.error('Failed to fetch queue metrics:', err);
    }
  }, []);

  /**
   * Fetch job details
   */
  const fetchJobDetail = useCallback(async (jobId) => {
    try {
      const job = await getGPUJob(jobId);
      setSelectedJob(job);
      return job;
    } catch (err) {
      console.error('Failed to fetch job detail:', err);
      setError(err.message);
      return null;
    }
  }, []);

  /**
   * Fetch job logs
   */
  const fetchJobLogs = useCallback(async (jobId, lines = 100) => {
    setLogsLoading(true);
    try {
      const response = await getJobLogs(jobId, { lines });
      setLogs(response.logs || []);
      return response;
    } catch (err) {
      console.error('Failed to fetch job logs:', err);
      return { logs: [], has_more: false };
    } finally {
      setLogsLoading(false);
    }
  }, []);

  /**
   * Submit a new GPU job
   */
  const handleSubmitJob = useCallback(async (jobData) => {
    try {
      const newJob = await submitGPUJob(jobData);

      // Add to jobs list
      setJobs((prev) => [newJob, ...prev]);

      // Refresh metrics
      await fetchQueueMetrics();

      // Subscribe to job updates via WebSocket
      if (wsRef.current) {
        wsRef.current.send(JSON.stringify({
          type: GPUWSMessageType.SUBSCRIBE_JOB,
          job_id: newJob.job_id,
        }));
      }

      return newJob;
    } catch (err) {
      console.error('Failed to submit GPU job:', err);
      throw err;
    }
  }, [fetchQueueMetrics]);

  /**
   * Cancel a GPU job
   */
  const handleCancelJob = useCallback(async (jobId) => {
    try {
      const cancelledJob = await cancelGPUJob(jobId);

      // Update local state
      setJobs((prev) =>
        prev.map((j) => (j.job_id === jobId ? { ...j, status: 'cancelled' } : j))
      );

      if (selectedJob?.job_id === jobId) {
        setSelectedJob((prev) => ({ ...prev, status: 'cancelled' }));
      }

      // Unsubscribe from job updates
      if (wsRef.current) {
        wsRef.current.send(JSON.stringify({
          type: GPUWSMessageType.UNSUBSCRIBE_JOB,
          job_id: jobId,
        }));
      }

      // Refresh metrics
      await fetchQueueMetrics();

      return cancelledJob;
    } catch (err) {
      console.error('Failed to cancel GPU job:', err);
      throw err;
    }
  }, [selectedJob, fetchQueueMetrics]);

  /**
   * Boost job priority
   */
  const handleBoostPriority = useCallback(async (jobId) => {
    try {
      const updatedJob = await boostJobPriority(jobId);

      // Update local state
      setJobs((prev) =>
        prev.map((j) => (j.job_id === jobId ? { ...j, priority: updatedJob.priority } : j))
      );

      if (selectedJob?.job_id === jobId) {
        setSelectedJob((prev) => ({ ...prev, priority: updatedJob.priority }));
      }

      // Refresh metrics
      await fetchQueueMetrics();

      return updatedJob;
    } catch (err) {
      console.error('Failed to boost job priority:', err);
      throw err;
    }
  }, [selectedJob, fetchQueueMetrics]);

  /**
   * Get queue position estimate for a new job
   */
  const getEstimatedPosition = useCallback(async (priority, jobType) => {
    try {
      return await estimateQueuePosition({ priority, job_type: jobType });
    } catch (err) {
      console.error('Failed to get estimated position:', err);
      return null;
    }
  }, []);

  /**
   * Handle WebSocket message
   */
  const handleWSMessage = useCallback((message) => {
    switch (message.type) {
      case GPUWSMessageType.JOB_PROGRESS:
        setJobs((prev) =>
          prev.map((j) =>
            j.job_id === message.job_id
              ? {
                  ...j,
                  progress_percent: message.progress_percent,
                  cost_usd: message.cost_usd,
                  estimated_remaining_minutes: message.estimated_remaining_minutes,
                }
              : j
          )
        );
        if (selectedJob?.job_id === message.job_id) {
          setSelectedJob((prev) => ({
            ...prev,
            progress_percent: message.progress_percent,
            cost_usd: message.cost_usd,
            estimated_remaining_minutes: message.estimated_remaining_minutes,
          }));
        }
        break;

      case GPUWSMessageType.JOB_STARTED:
        setJobs((prev) =>
          prev.map((j) =>
            j.job_id === message.job_id
              ? { ...j, status: 'running', started_at: message.started_at }
              : j
          )
        );
        fetchQueueMetrics();
        break;

      case GPUWSMessageType.JOB_COMPLETED:
        setJobs((prev) =>
          prev.map((j) =>
            j.job_id === message.job_id
              ? {
                  ...j,
                  status: 'completed',
                  progress_percent: 100,
                  completed_at: message.completed_at,
                  cost_usd: message.cost_usd,
                }
              : j
          )
        );
        fetchQueueMetrics();
        break;

      case GPUWSMessageType.JOB_FAILED:
        setJobs((prev) =>
          prev.map((j) =>
            j.job_id === message.job_id
              ? {
                  ...j,
                  status: 'failed',
                  completed_at: message.completed_at,
                  error_message: message.error_message,
                  error_type: message.error_type,
                }
              : j
          )
        );
        fetchQueueMetrics();
        break;

      case GPUWSMessageType.QUEUE_UPDATED:
        fetchQueueMetrics();
        break;

      case GPUWSMessageType.RESOURCE_UPDATED:
        setResources((prev) => ({ ...prev, ...message.resources }));
        break;

      case GPUWSMessageType.LOG_ENTRY:
        if (selectedJob?.job_id === message.job_id) {
          setLogs((prev) => [...prev, message.log]);
        }
        break;

      case GPUWSMessageType.HEARTBEAT:
        // Connection is alive
        break;

      default:
        // Unknown message type
        break;
    }
  }, [selectedJob, fetchQueueMetrics]);

  /**
   * Connect to WebSocket
   */
  const connectWebSocket = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    wsRef.current = createGPUWebSocket({
      onMessage: handleWSMessage,
      onError: (error) => {
        console.error('GPU WebSocket error:', error);
      },
      onClose: () => {
        // Attempt reconnection after 5 seconds
        wsReconnectTimeoutRef.current = setTimeout(() => {
          connectWebSocket();
        }, 5000);
      },
    });

    // Subscribe to queue updates
    wsRef.current.send(JSON.stringify({
      type: GPUWSMessageType.SUBSCRIBE_QUEUE,
    }));

    // Subscribe to running jobs
    jobs.forEach((job) => {
      if (['queued', 'starting', 'running'].includes(job.status)) {
        wsRef.current.send(JSON.stringify({
          type: GPUWSMessageType.SUBSCRIBE_JOB,
          job_id: job.job_id,
        }));
      }
    });
  }, [handleWSMessage, jobs]);

  /**
   * Start resource polling
   */
  const startResourcePolling = useCallback(() => {
    const poll = async () => {
      await fetchResources();
      resourcePollingRef.current = setTimeout(poll, RESOURCE_POLLING_INTERVAL);
    };
    poll();
  }, [fetchResources]);

  /**
   * Start queue metrics polling
   */
  const startQueuePolling = useCallback(() => {
    const poll = async () => {
      await fetchQueueMetrics();
      queuePollingRef.current = setTimeout(poll, QUEUE_POLLING_INTERVAL);
    };
    poll();
  }, [fetchQueueMetrics]);

  /**
   * Stop all polling
   */
  const stopPolling = useCallback(() => {
    if (resourcePollingRef.current) {
      clearTimeout(resourcePollingRef.current);
      resourcePollingRef.current = null;
    }
    if (queuePollingRef.current) {
      clearTimeout(queuePollingRef.current);
      queuePollingRef.current = null;
    }
  }, []);

  /**
   * Refresh all data
   */
  const refresh = useCallback(async () => {
    await Promise.all([fetchJobs(true), fetchResources(), fetchQueueMetrics()]);
  }, [fetchJobs, fetchResources, fetchQueueMetrics]);

  /**
   * Open schedule modal
   */
  const openScheduleModal = useCallback(() => {
    setIsScheduleModalOpen(true);
  }, []);

  /**
   * Close schedule modal
   */
  const closeScheduleModal = useCallback(() => {
    setIsScheduleModalOpen(false);
  }, []);

  // Derived state
  const activeJobs = jobs.filter((j) => ['running', 'starting'].includes(j.status));
  const queuedJobs = jobs.filter((j) => j.status === 'queued');
  const recentJobs = jobs.filter((j) => ['completed', 'failed', 'cancelled'].includes(j.status)).slice(0, 10);
  const hasRunningJobs = activeJobs.length > 0;
  const isEmpty = jobs.length === 0;

  // Initial fetch and setup
  useEffect(() => {
    // Fetch initial data
    fetchJobs();
    fetchResources();
    fetchQueueMetrics();

    // Setup WebSocket for real-time updates
    connectWebSocket();

    // Start polling for resources and queue metrics (with delay to avoid double-fetch on mount)
    resourcePollingRef.current = setTimeout(() => {
      startResourcePolling();
    }, RESOURCE_POLLING_INTERVAL);

    queuePollingRef.current = setTimeout(() => {
      startQueuePolling();
    }, QUEUE_POLLING_INTERVAL);

    return () => {
      stopPolling();
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (wsReconnectTimeoutRef.current) {
        clearTimeout(wsReconnectTimeoutRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Context value
  const value = {
    // State
    jobs,
    activeJobs,
    queuedJobs,
    recentJobs,
    selectedJob,
    loading,
    error,
    resources,
    queueMetrics,
    logs,
    logsLoading,
    isScheduleModalOpen,

    // Derived state
    hasRunningJobs,
    isEmpty,

    // Actions
    fetchJobs,
    fetchJobDetail,
    fetchJobLogs,
    handleSubmitJob,
    handleCancelJob,
    handleBoostPriority,
    getEstimatedPosition,
    setSelectedJob,
    refresh,
    openScheduleModal,
    closeScheduleModal,

    // Constants
    GPU_JOB_TYPES,
    GPU_JOB_PRIORITIES,
    GPU_ERROR_TYPES,
  };

  return (
    <GPUWorkloadsContext.Provider value={value}>
      {children}
    </GPUWorkloadsContext.Provider>
  );
}

/**
 * Hook to use GPU workloads context
 */
export function useGPUWorkloads() {
  const context = useContext(GPUWorkloadsContext);
  if (!context) {
    throw new Error('useGPUWorkloads must be used within a GPUWorkloadsProvider');
  }
  return context;
}

export default GPUWorkloadsContext;
