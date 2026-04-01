/**
 * Project Aura - GPU Scheduler API Service Tests
 *
 * Tests for GPU scheduler API functions and utilities.
 * ADR-061: GPU Workload Scheduler - Phase 3 Frontend Integration
 */

import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
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
  getGPUCosts,
  getJobLogs,
  formatGPUMemory,
  formatCost,
  formatDuration,
  getGPUStatusColor,
  getGPUPriorityColor,
  getJobTypeInfo,
  getErrorTypeInfo,
  GPU_JOB_TYPES,
  GPU_JOB_PRIORITIES,
  GPU_ERROR_TYPES,
} from './gpuSchedulerApi';

// Mock fetch globally
global.fetch = vi.fn();

// Mock localStorage
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
};
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

describe('gpuSchedulerApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorageMock.getItem.mockReturnValue(null);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Constants', () => {
    test('GPU_JOB_TYPES contains expected job types', () => {
      expect(GPU_JOB_TYPES).toHaveLength(5);
      expect(GPU_JOB_TYPES.map((t) => t.value)).toContain('embedding_generation');
      expect(GPU_JOB_TYPES.map((t) => t.value)).toContain('vulnerability_training');
      expect(GPU_JOB_TYPES.map((t) => t.value)).toContain('swe_rl_training');
      expect(GPU_JOB_TYPES.map((t) => t.value)).toContain('memory_consolidation');
      expect(GPU_JOB_TYPES.map((t) => t.value)).toContain('local_inference');
    });

    test('GPU_JOB_PRIORITIES contains expected priorities', () => {
      expect(GPU_JOB_PRIORITIES).toHaveLength(3);
      expect(GPU_JOB_PRIORITIES.map((p) => p.value)).toEqual(['low', 'normal', 'high']);
    });

    test('GPU_ERROR_TYPES contains expected error types', () => {
      expect(GPU_ERROR_TYPES).toHaveProperty('oom');
      expect(GPU_ERROR_TYPES).toHaveProperty('spot_interruption');
      expect(GPU_ERROR_TYPES).toHaveProperty('timeout');
      expect(GPU_ERROR_TYPES).toHaveProperty('config_error');
      expect(GPU_ERROR_TYPES).toHaveProperty('network_error');
    });

    test('Each GPU_JOB_TYPE has required properties', () => {
      GPU_JOB_TYPES.forEach((type) => {
        expect(type).toHaveProperty('value');
        expect(type).toHaveProperty('label');
        expect(type).toHaveProperty('description');
        expect(type).toHaveProperty('typicalDuration');
        expect(type).toHaveProperty('gpuMemory');
      });
    });

    test('Each GPU_ERROR_TYPE has required properties', () => {
      Object.values(GPU_ERROR_TYPES).forEach((error) => {
        expect(error).toHaveProperty('label');
        expect(error).toHaveProperty('description');
        expect(error).toHaveProperty('severity');
        expect(error).toHaveProperty('action');
        expect(error).toHaveProperty('bgColor');
        expect(error).toHaveProperty('textColor');
      });
    });
  });

  describe('Utility functions', () => {
    describe('formatGPUMemory', () => {
      test('formats GB values correctly', () => {
        expect(formatGPUMemory(8)).toBe('8.0 GB');
        expect(formatGPUMemory(16)).toBe('16.0 GB');
        expect(formatGPUMemory(24)).toBe('24.0 GB');
      });

      test('formats sub-GB values as MB', () => {
        expect(formatGPUMemory(0.5)).toBe('512 MB');
        expect(formatGPUMemory(0.25)).toBe('256 MB');
      });

      test('handles decimal GB values', () => {
        expect(formatGPUMemory(8.5)).toBe('8.5 GB');
        expect(formatGPUMemory(1.25)).toBe('1.3 GB');
      });
    });

    describe('formatCost', () => {
      test('formats USD values correctly', () => {
        expect(formatCost(0.54)).toBe('$0.54');
        expect(formatCost(2.47)).toBe('$2.47');
        expect(formatCost(100)).toBe('$100.00');
      });

      test('handles null and undefined', () => {
        expect(formatCost(null)).toBe('-');
        expect(formatCost(undefined)).toBe('-');
      });

      test('handles zero', () => {
        expect(formatCost(0)).toBe('$0.00');
      });
    });

    describe('formatDuration', () => {
      test('formats minutes correctly', () => {
        expect(formatDuration(5)).toBe('5 min');
        expect(formatDuration(30)).toBe('30 min');
        expect(formatDuration(45)).toBe('45 min');
      });

      test('formats hours and minutes correctly', () => {
        expect(formatDuration(60)).toBe('1h');
        expect(formatDuration(90)).toBe('1h 30m');
        expect(formatDuration(120)).toBe('2h');
        expect(formatDuration(150)).toBe('2h 30m');
      });

      test('handles null, undefined, and negative values', () => {
        expect(formatDuration(null)).toBe('-');
        expect(formatDuration(undefined)).toBe('-');
        expect(formatDuration(-5)).toBe('-');
        expect(formatDuration(0)).toBe('-');
      });
    });

    describe('getGPUStatusColor', () => {
      test('returns correct color for each status', () => {
        expect(getGPUStatusColor('queued')).toBe('warning');
        expect(getGPUStatusColor('starting')).toBe('info');
        expect(getGPUStatusColor('running')).toBe('aura');
        expect(getGPUStatusColor('completed')).toBe('success');
        expect(getGPUStatusColor('failed')).toBe('critical');
        expect(getGPUStatusColor('cancelled')).toBe('surface');
      });

      test('returns surface for unknown status', () => {
        expect(getGPUStatusColor('unknown')).toBe('surface');
      });
    });

    describe('getGPUPriorityColor', () => {
      test('returns correct color for each priority', () => {
        expect(getGPUPriorityColor('high')).toBe('critical');
        expect(getGPUPriorityColor('normal')).toBe('info');
        expect(getGPUPriorityColor('low')).toBe('surface');
      });

      test('returns surface for unknown priority', () => {
        expect(getGPUPriorityColor('unknown')).toBe('surface');
      });
    });

    describe('getJobTypeInfo', () => {
      test('returns job type info for valid type', () => {
        const info = getJobTypeInfo('embedding_generation');
        expect(info).not.toBeNull();
        expect(info.label).toBe('Code Embedding Generation');
      });

      test('returns null for invalid type', () => {
        expect(getJobTypeInfo('invalid_type')).toBeNull();
      });
    });

    describe('getErrorTypeInfo', () => {
      test('returns error type info for valid type', () => {
        const info = getErrorTypeInfo('oom');
        expect(info).not.toBeNull();
        expect(info.label).toBe('Out of Memory');
        expect(info.severity).toBe('high');
      });

      test('returns null for invalid type', () => {
        expect(getErrorTypeInfo('invalid_error')).toBeNull();
      });
    });
  });

  describe('API functions in DEV mode', () => {
    // These tests verify that the mock data is returned in dev mode
    // The actual implementation checks import.meta.env.DEV

    test('getGPUJobs returns mock data in dev mode', async () => {
      const result = await getGPUJobs();
      expect(result).toHaveProperty('jobs');
      expect(Array.isArray(result.jobs)).toBe(true);
    });

    test('getGPUJobs filters by status', async () => {
      const result = await getGPUJobs({ status: 'running' });
      expect(result.jobs.every((j) => j.status === 'running')).toBe(true);
    });

    test('getGPUJob returns mock job data', async () => {
      const result = await getGPUJobs();
      const jobId = result.jobs[0]?.job_id;

      if (jobId) {
        const job = await getGPUJob(jobId);
        expect(job.job_id).toBe(jobId);
      }
    });

    test('getGPUJob throws for non-existent job', async () => {
      await expect(getGPUJob('non-existent-job')).rejects.toThrow('GPU job not found');
    });

    test('submitGPUJob creates new job', async () => {
      const jobData = {
        job_type: 'embedding_generation',
        priority: 'normal',
        gpu_memory_gb: 8,
        config: { repository_id: 'test-repo' },
      };

      const result = await submitGPUJob(jobData);
      expect(result.job_type).toBe('embedding_generation');
      expect(result.status).toBe('queued');
      expect(result.job_id).toBeDefined();
    });

    test('cancelGPUJob cancels a queued job', async () => {
      // First create a job
      const newJob = await submitGPUJob({
        job_type: 'embedding_generation',
        priority: 'normal',
        config: {},
      });

      // Then cancel it
      const result = await cancelGPUJob(newJob.job_id);
      expect(result.status).toBe('cancelled');
    });

    test('cancelGPUJob throws for non-existent job', async () => {
      await expect(cancelGPUJob('non-existent-job')).rejects.toThrow('GPU job not found');
    });

    test('boostJobPriority increases job priority', async () => {
      // Create a low priority job
      const newJob = await submitGPUJob({
        job_type: 'embedding_generation',
        priority: 'low',
        config: {},
      });

      // Boost it
      const result = await boostJobPriority(newJob.job_id);
      expect(result.priority).toBe('normal');
    });

    test('getGPUResources returns mock resource data', async () => {
      const result = await getGPUResources();
      expect(result).toHaveProperty('gpus_in_use');
      expect(result).toHaveProperty('gpus_total');
      expect(result).toHaveProperty('cost_today_usd');
      expect(typeof result.gpus_in_use).toBe('number');
    });

    test('getGPUQueueMetrics returns mock queue metrics', async () => {
      const result = await getGPUQueueMetrics();
      expect(result).toHaveProperty('total_queued');
      expect(result).toHaveProperty('by_priority');
      expect(result).toHaveProperty('running_jobs');
      expect(result).toHaveProperty('avg_wait_time_seconds');
    });

    test('estimateQueuePosition returns position estimate', async () => {
      const result = await estimateQueuePosition({
        priority: 'normal',
        job_type: 'embedding_generation',
      });

      expect(result).toHaveProperty('queue_position');
      expect(result).toHaveProperty('estimated_wait_minutes');
      expect(result).toHaveProperty('confidence');
      expect(result).toHaveProperty('factors');
    });

    test('getGPUCosts returns cost summary', async () => {
      const result = await getGPUCosts();

      expect(result).toHaveProperty('total_cost_usd');
      expect(result).toHaveProperty('gpu_hours');
      expect(result).toHaveProperty('jobs_count');
      expect(result).toHaveProperty('by_job_type');
      expect(result).toHaveProperty('daily_costs');
    });

    test('getJobLogs returns mock logs', async () => {
      const jobs = await getGPUJobs();
      const runningJob = jobs.jobs.find((j) => j.status === 'running');

      if (runningJob) {
        const result = await getJobLogs(runningJob.job_id);
        expect(result).toHaveProperty('logs');
        expect(Array.isArray(result.logs)).toBe(true);
      }
    });
  });
});

describe('Error type coverage', () => {
  test('OOM error has correct properties', () => {
    const oomError = GPU_ERROR_TYPES.oom;
    expect(oomError.label).toBe('Out of Memory');
    expect(oomError.severity).toBe('high');
    expect(oomError.action).toContain('memory');
  });

  test('Spot interruption error has correct properties', () => {
    const spotError = GPU_ERROR_TYPES.spot_interruption;
    expect(spotError.label).toBe('Spot Interruption');
    expect(spotError.severity).toBe('medium');
    expect(spotError.action).toContain('checkpoint');
  });

  test('Timeout error has correct properties', () => {
    const timeoutError = GPU_ERROR_TYPES.timeout;
    expect(timeoutError.label).toBe('Timeout');
    expect(timeoutError.severity).toBe('medium');
    expect(timeoutError.action).toContain('runtime');
  });

  test('Config error has correct properties', () => {
    const configError = GPU_ERROR_TYPES.config_error;
    expect(configError.label).toBe('Configuration Error');
    expect(configError.severity).toBe('high');
    expect(configError.action).toContain('config');
  });

  test('Network error has correct properties', () => {
    const networkError = GPU_ERROR_TYPES.network_error;
    expect(networkError.label).toBe('Network Error');
    expect(networkError.severity).toBe('medium');
    expect(networkError.action).toContain('network');
  });
});

describe('Job type coverage', () => {
  test('Embedding generation type has correct properties', () => {
    const type = getJobTypeInfo('embedding_generation');
    expect(type.label).toBe('Code Embedding Generation');
    expect(type.gpuMemory).toBe('4-8 GB');
  });

  test('Local inference type has correct properties', () => {
    const type = getJobTypeInfo('local_inference');
    expect(type.label).toBe('Local LLM Inference');
    expect(type.gpuMemory).toBe('8-16 GB');
    expect(type.typicalDuration).toBe('Continuous');
  });

  test('Vulnerability training type has correct properties', () => {
    const type = getJobTypeInfo('vulnerability_training');
    expect(type.label).toBe('Vulnerability Classifier Training');
    expect(type.gpuMemory).toBe('8-16 GB');
  });

  test('SWE-RL training type has correct properties', () => {
    const type = getJobTypeInfo('swe_rl_training');
    expect(type.label).toBe('Self-Play SWE-RL Training');
    expect(type.gpuMemory).toBe('16-24 GB');
  });

  test('Memory consolidation type has correct properties', () => {
    const type = getJobTypeInfo('memory_consolidation');
    expect(type.label).toBe('Titan Memory Consolidation');
    expect(type.gpuMemory).toBe('4-8 GB');
  });
});
