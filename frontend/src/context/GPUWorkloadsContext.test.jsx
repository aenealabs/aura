/**
 * Project Aura - GPU Workloads Context Tests
 *
 * Tests for GPU workloads state management context.
 * ADR-061: GPU Workload Scheduler - Phase 3 Frontend Integration
 */

import { useEffect } from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { GPUWorkloadsProvider, useGPUWorkloads } from './GPUWorkloadsContext';

// Mock the gpuSchedulerApi module
vi.mock('../services/gpuSchedulerApi', () => ({
  getGPUJobs: vi.fn(),
  getGPUJob: vi.fn(),
  submitGPUJob: vi.fn(),
  cancelGPUJob: vi.fn(),
  boostJobPriority: vi.fn(),
  getGPUResources: vi.fn(),
  getGPUQueueMetrics: vi.fn(),
  getQueuePosition: vi.fn(),
  estimateQueuePosition: vi.fn(),
  getJobLogs: vi.fn(),
  createGPUWebSocket: vi.fn(),
  GPUWSMessageType: {
    SUBSCRIBE_JOB: 'subscribe_job',
    UNSUBSCRIBE_JOB: 'unsubscribe_job',
    SUBSCRIBE_QUEUE: 'subscribe_queue',
    JOB_PROGRESS: 'job_progress',
    JOB_STARTED: 'job_started',
    JOB_COMPLETED: 'job_completed',
    JOB_FAILED: 'job_failed',
    QUEUE_UPDATED: 'queue_updated',
    RESOURCE_UPDATED: 'resource_updated',
    LOG_ENTRY: 'log_entry',
    HEARTBEAT: 'heartbeat',
  },
  GPU_JOB_TYPES: [
    { value: 'embedding_generation', label: 'Code Embedding Generation' },
    { value: 'vulnerability_training', label: 'Vulnerability Classifier Training' },
  ],
  GPU_JOB_PRIORITIES: [
    { value: 'low', label: 'Low' },
    { value: 'normal', label: 'Normal' },
    { value: 'high', label: 'High' },
  ],
  GPU_ERROR_TYPES: {
    oom: { label: 'Out of Memory', severity: 'high' },
    spot_interruption: { label: 'Spot Interruption', severity: 'medium' },
  },
}));

import * as gpuSchedulerApi from '../services/gpuSchedulerApi';

// Test consumer component
function TestConsumer({ onMount }) {
  const context = useGPUWorkloads();

  useEffect(() => {
    if (onMount) onMount(context);
  }, [onMount, context]);

  return (
    <div>
      <span data-testid="jobs-count">{context.jobs.length}</span>
      <span data-testid="active-jobs-count">{context.activeJobs.length}</span>
      <span data-testid="queued-jobs-count">{context.queuedJobs.length}</span>
      <span data-testid="loading">{context.loading ? 'true' : 'false'}</span>
      <span data-testid="error">{context.error || 'none'}</span>
      <span data-testid="is-empty">{context.isEmpty ? 'true' : 'false'}</span>
      <span data-testid="gpus-in-use">{context.resources.gpus_in_use}</span>
      <span data-testid="queue-depth">{context.queueMetrics.total_queued}</span>
      <span data-testid="modal-open">{context.isScheduleModalOpen ? 'true' : 'false'}</span>
      <button data-testid="refresh" onClick={() => context.refresh()}>Refresh</button>
      <button data-testid="open-modal" onClick={() => context.openScheduleModal()}>Open Modal</button>
      <button data-testid="close-modal" onClick={() => context.closeScheduleModal()}>Close Modal</button>
    </div>
  );
}

describe('GPUWorkloadsContext', () => {
  const mockJobs = [
    {
      job_id: 'gpu-job-001',
      job_type: 'embedding_generation',
      status: 'running',
      priority: 'normal',
      progress_percent: 67,
      cost_usd: 0.54,
    },
    {
      job_id: 'gpu-job-002',
      job_type: 'vulnerability_training',
      status: 'queued',
      priority: 'normal',
      queue_position: 1,
    },
    {
      job_id: 'gpu-job-003',
      job_type: 'embedding_generation',
      status: 'completed',
      priority: 'normal',
      progress_percent: 100,
      cost_usd: 0.89,
    },
  ];

  const mockResources = {
    gpus_in_use: 1,
    gpus_total: 4,
    gpus_available: 3,
    queue_depth: 1,
    cost_today_usd: 2.47,
    nodes_active: 1,
    nodes_scaling: 0,
  };

  const mockQueueMetrics = {
    total_queued: 1,
    by_priority: { high: 0, normal: 1, low: 0 },
    running_jobs: 1,
    avg_wait_time_seconds: 420,
  };

  let mockWebSocket;

  beforeEach(() => {
    vi.clearAllMocks();

    // Default mock implementations
    gpuSchedulerApi.getGPUJobs.mockResolvedValue({ jobs: mockJobs });
    gpuSchedulerApi.getGPUResources.mockResolvedValue(mockResources);
    gpuSchedulerApi.getGPUQueueMetrics.mockResolvedValue(mockQueueMetrics);
    gpuSchedulerApi.getJobLogs.mockResolvedValue({ logs: [], has_more: false });
    gpuSchedulerApi.estimateQueuePosition.mockResolvedValue({
      queue_position: 2,
      estimated_wait_minutes: 15,
    });

    // Mock WebSocket
    mockWebSocket = {
      send: vi.fn(),
      close: vi.fn(),
    };
    gpuSchedulerApi.createGPUWebSocket.mockReturnValue(mockWebSocket);
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  describe('GPUWorkloadsProvider', () => {
    test('provides initial state', async () => {
      render(
        <GPUWorkloadsProvider>
          <TestConsumer />
        </GPUWorkloadsProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('loading')).toHaveTextContent('false');
      });
    });

    test('fetches jobs on mount', async () => {
      render(
        <GPUWorkloadsProvider>
          <TestConsumer />
        </GPUWorkloadsProvider>
      );

      await waitFor(() => {
        expect(gpuSchedulerApi.getGPUJobs).toHaveBeenCalled();
        expect(screen.getByTestId('jobs-count')).toHaveTextContent('3');
      });
    });

    test('fetches resources on mount', async () => {
      render(
        <GPUWorkloadsProvider>
          <TestConsumer />
        </GPUWorkloadsProvider>
      );

      await waitFor(() => {
        expect(gpuSchedulerApi.getGPUResources).toHaveBeenCalled();
        expect(screen.getByTestId('gpus-in-use')).toHaveTextContent('1');
      });
    });

    test('fetches queue metrics on mount', async () => {
      render(
        <GPUWorkloadsProvider>
          <TestConsumer />
        </GPUWorkloadsProvider>
      );

      await waitFor(() => {
        expect(gpuSchedulerApi.getGPUQueueMetrics).toHaveBeenCalled();
        expect(screen.getByTestId('queue-depth')).toHaveTextContent('1');
      });
    });

    test('derives active and queued jobs correctly', async () => {
      render(
        <GPUWorkloadsProvider>
          <TestConsumer />
        </GPUWorkloadsProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('active-jobs-count')).toHaveTextContent('1'); // running
        expect(screen.getByTestId('queued-jobs-count')).toHaveTextContent('1'); // queued
      });
    });

    test('handles fetch error gracefully', async () => {
      gpuSchedulerApi.getGPUJobs.mockRejectedValue(new Error('Network error'));

      render(
        <GPUWorkloadsProvider>
          <TestConsumer />
        </GPUWorkloadsProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('error')).toHaveTextContent('Network error');
      });
    });

    test('shows empty state when no jobs', async () => {
      gpuSchedulerApi.getGPUJobs.mockResolvedValue({ jobs: [] });

      render(
        <GPUWorkloadsProvider>
          <TestConsumer />
        </GPUWorkloadsProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('is-empty')).toHaveTextContent('true');
      });
    });

    test('creates WebSocket connection on mount', async () => {
      render(
        <GPUWorkloadsProvider>
          <TestConsumer />
        </GPUWorkloadsProvider>
      );

      await waitFor(() => {
        expect(gpuSchedulerApi.createGPUWebSocket).toHaveBeenCalled();
      });
    });
  });

  describe('Modal state', () => {
    test('opens schedule modal', async () => {
      const user = userEvent.setup();

      render(
        <GPUWorkloadsProvider>
          <TestConsumer />
        </GPUWorkloadsProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('modal-open')).toHaveTextContent('false');
      });

      await user.click(screen.getByTestId('open-modal'));

      expect(screen.getByTestId('modal-open')).toHaveTextContent('true');
    });

    test('closes schedule modal', async () => {
      const user = userEvent.setup();

      render(
        <GPUWorkloadsProvider>
          <TestConsumer />
        </GPUWorkloadsProvider>
      );

      await user.click(screen.getByTestId('open-modal'));
      expect(screen.getByTestId('modal-open')).toHaveTextContent('true');

      await user.click(screen.getByTestId('close-modal'));
      expect(screen.getByTestId('modal-open')).toHaveTextContent('false');
    });
  });

  describe('Refresh', () => {
    test('refreshes all data', async () => {
      const user = userEvent.setup();

      render(
        <GPUWorkloadsProvider>
          <TestConsumer />
        </GPUWorkloadsProvider>
      );

      await waitFor(() => {
        expect(gpuSchedulerApi.getGPUJobs).toHaveBeenCalledTimes(1);
      });

      await user.click(screen.getByTestId('refresh'));

      await waitFor(() => {
        expect(gpuSchedulerApi.getGPUJobs).toHaveBeenCalledTimes(2);
        expect(gpuSchedulerApi.getGPUResources).toHaveBeenCalledTimes(2);
        expect(gpuSchedulerApi.getGPUQueueMetrics).toHaveBeenCalledTimes(2);
      });
    });
  });
});

describe('useGPUWorkloads hook', () => {
  test('throws error when used outside provider', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

    expect(() => {
      render(<TestConsumer />);
    }).toThrow('useGPUWorkloads must be used within a GPUWorkloadsProvider');

    consoleError.mockRestore();
  });
});

// Helper consumer for job actions tests
function JobActionsConsumer({ onReady }) {
  const context = useGPUWorkloads();

  useEffect(() => {
    if (!context.loading && onReady) {
      onReady(context);
    }
  }, [context.loading, onReady, context]);

  return null;
}

describe('Job actions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    gpuSchedulerApi.getGPUJobs.mockResolvedValue({
      jobs: [
        { job_id: 'gpu-job-001', status: 'queued', priority: 'normal' },
      ],
    });
    gpuSchedulerApi.getGPUResources.mockResolvedValue({
      gpus_in_use: 0,
      gpus_total: 4,
    });
    gpuSchedulerApi.getGPUQueueMetrics.mockResolvedValue({
      total_queued: 1,
      by_priority: { high: 0, normal: 1, low: 0 },
    });
    gpuSchedulerApi.createGPUWebSocket.mockReturnValue({
      send: vi.fn(),
      close: vi.fn(),
    });
  });

  test('submits new job', async () => {
    const newJob = {
      job_id: 'gpu-job-new',
      job_type: 'embedding_generation',
      status: 'queued',
      priority: 'normal',
    };
    gpuSchedulerApi.submitGPUJob.mockResolvedValue(newJob);

    let contextRef;
    render(
      <GPUWorkloadsProvider>
        <JobActionsConsumer onReady={(ctx) => { contextRef = ctx; }} />
      </GPUWorkloadsProvider>
    );

    await waitFor(() => {
      expect(contextRef).toBeDefined();
    });

    await act(async () => {
      await contextRef.handleSubmitJob({
        job_type: 'embedding_generation',
        priority: 'normal',
        config: { repository_id: 'test-repo' },
      });
    });

    expect(gpuSchedulerApi.submitGPUJob).toHaveBeenCalled();
  });

  test('cancels job', async () => {
    gpuSchedulerApi.cancelGPUJob.mockResolvedValue({
      job_id: 'gpu-job-001',
      status: 'cancelled',
    });

    let contextRef;
    render(
      <GPUWorkloadsProvider>
        <JobActionsConsumer onReady={(ctx) => { contextRef = ctx; }} />
      </GPUWorkloadsProvider>
    );

    await waitFor(() => {
      expect(contextRef).toBeDefined();
    });

    await act(async () => {
      await contextRef.handleCancelJob('gpu-job-001');
    });

    expect(gpuSchedulerApi.cancelGPUJob).toHaveBeenCalledWith('gpu-job-001');
  });

  test('boosts job priority', async () => {
    gpuSchedulerApi.boostJobPriority.mockResolvedValue({
      job_id: 'gpu-job-001',
      priority: 'high',
    });

    let contextRef;
    render(
      <GPUWorkloadsProvider>
        <JobActionsConsumer onReady={(ctx) => { contextRef = ctx; }} />
      </GPUWorkloadsProvider>
    );

    await waitFor(() => {
      expect(contextRef).toBeDefined();
    });

    await act(async () => {
      await contextRef.handleBoostPriority('gpu-job-001');
    });

    expect(gpuSchedulerApi.boostJobPriority).toHaveBeenCalledWith('gpu-job-001');
  });

  test('gets estimated queue position', async () => {
    gpuSchedulerApi.estimateQueuePosition.mockResolvedValue({
      queue_position: 3,
      estimated_wait_minutes: 25,
    });

    let contextRef;
    render(
      <GPUWorkloadsProvider>
        <JobActionsConsumer onReady={(ctx) => { contextRef = ctx; }} />
      </GPUWorkloadsProvider>
    );

    await waitFor(() => {
      expect(contextRef).toBeDefined();
    });

    let estimate;
    await act(async () => {
      estimate = await contextRef.getEstimatedPosition('normal', 'embedding_generation');
    });

    expect(gpuSchedulerApi.estimateQueuePosition).toHaveBeenCalledWith({
      priority: 'normal',
      job_type: 'embedding_generation',
    });
    expect(estimate.queue_position).toBe(3);
  });
});
