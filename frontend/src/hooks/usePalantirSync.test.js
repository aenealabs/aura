/**
 * usePalantirSync Hook Tests
 *
 * Tests for the Palantir sync status React hook.
 *
 * ADR-075: Palantir AIP UI Enhancements
 */

import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { usePalantirSync, useCircuitBreaker, usePalantirHealth } from './usePalantirSync';
import * as palantirApi from '../services/palantirApi';

// Mock the palantir API
vi.mock('../services/palantirApi');

describe('usePalantirSync', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('fetches initial data on mount', async () => {
    const mockHealth = { status: 'ok', is_healthy: true };
    const mockCircuitBreaker = { state: 'CLOSED', failure_count: 0 };
    const mockSyncStatus = { ThreatActor: { objects_synced: 100 } };

    palantirApi.getAllStatus.mockResolvedValue({
      health: mockHealth,
      circuitBreaker: mockCircuitBreaker,
      syncStatus: mockSyncStatus,
    });

    const { result } = renderHook(() => usePalantirSync({ autoRefresh: false }));

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.health).toEqual(mockHealth);
    expect(result.current.circuitBreaker).toEqual(mockCircuitBreaker);
    expect(result.current.syncStatus).toEqual(mockSyncStatus);
    expect(result.current.error).toBeNull();
  });

  test('sets error state when fetch fails', async () => {
    palantirApi.getAllStatus.mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => usePalantirSync({ autoRefresh: false }));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBeTruthy();
  });

  test('refetches data on interval when autoRefresh is true', async () => {
    vi.useFakeTimers();
    const mockData = {
      health: { status: 'ok', is_healthy: true },
      circuitBreaker: { state: 'CLOSED' },
      syncStatus: {},
    };
    palantirApi.getAllStatus.mockResolvedValue(mockData);

    const { result } = renderHook(() =>
      usePalantirSync({ refreshInterval: 5000, autoRefresh: true })
    );

    // Wait for initial load
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });

    expect(palantirApi.getAllStatus).toHaveBeenCalledTimes(1);

    // Advance timer for auto-refresh
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    expect(palantirApi.getAllStatus).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });

  test('does not refetch when autoRefresh is false', async () => {
    vi.useFakeTimers();
    const mockData = {
      health: { status: 'ok', is_healthy: true },
      circuitBreaker: { state: 'CLOSED' },
      syncStatus: {},
    };
    palantirApi.getAllStatus.mockResolvedValue(mockData);

    const { result } = renderHook(() =>
      usePalantirSync({ refreshInterval: 5000, autoRefresh: false })
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });

    expect(palantirApi.getAllStatus).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });

    expect(palantirApi.getAllStatus).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });

  test('refetch function manually refetches data', async () => {
    const mockData = {
      health: { status: 'ok', is_healthy: true },
      circuitBreaker: { state: 'CLOSED' },
      syncStatus: {},
    };
    palantirApi.getAllStatus.mockResolvedValue(mockData);

    const { result } = renderHook(() => usePalantirSync({ autoRefresh: false }));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(palantirApi.getAllStatus).toHaveBeenCalledTimes(1);

    await act(async () => {
      await result.current.refetch();
    });

    expect(palantirApi.getAllStatus).toHaveBeenCalledTimes(2);
  });

  test('resetBreaker calls API and updates state', async () => {
    const mockData = {
      health: { status: 'ok', is_healthy: true },
      circuitBreaker: { state: 'OPEN', failure_count: 5 },
      syncStatus: {},
    };
    palantirApi.getAllStatus.mockResolvedValue(mockData);
    palantirApi.resetCircuitBreaker.mockResolvedValue({ status: 'success', new_state: 'CLOSED' });

    const { result } = renderHook(() => usePalantirSync({ autoRefresh: false }));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.resetBreaker();
    });

    expect(palantirApi.resetCircuitBreaker).toHaveBeenCalled();
  });

  test('triggerObjectSync calls API', async () => {
    const mockData = {
      health: { status: 'ok', is_healthy: true },
      circuitBreaker: { state: 'CLOSED' },
      syncStatus: {},
    };
    palantirApi.getAllStatus.mockResolvedValue(mockData);
    palantirApi.triggerSync.mockResolvedValue({ triggered: true });

    const { result } = renderHook(() => usePalantirSync({ autoRefresh: false }));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.triggerObjectSync('ThreatActor');
    });

    expect(palantirApi.triggerSync).toHaveBeenCalledWith('ThreatActor', false);
  });

  test('computes integrationStatus correctly for healthy state', async () => {
    const mockData = {
      health: { status: 'ok', is_healthy: true },
      circuitBreaker: { state: 'CLOSED' },
      syncStatus: {
        ThreatActor: { last_sync_status: 'synced', objects_synced: 100 },
        Asset: { last_sync_status: 'synced', objects_synced: 50 },
      },
    };
    palantirApi.getAllStatus.mockResolvedValue(mockData);

    const { result } = renderHook(() => usePalantirSync({ autoRefresh: false }));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.integrationStatus).toBe('healthy');
    expect(result.current.isHealthy).toBe(true);
  });

  test('returns warning status when circuit breaker is HALF_OPEN', async () => {
    const mockData = {
      health: { status: 'ok', is_healthy: true },
      circuitBreaker: { state: 'HALF_OPEN' },
      syncStatus: {},
    };
    palantirApi.getAllStatus.mockResolvedValue(mockData);

    const { result } = renderHook(() => usePalantirSync({ autoRefresh: false }));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.integrationStatus).toBe('warning');
    expect(result.current.isCircuitHalfOpen).toBe(true);
  });

  test('returns degraded status when circuit breaker is OPEN', async () => {
    const mockData = {
      health: { status: 'ok', is_healthy: true },
      circuitBreaker: { state: 'OPEN' },
      syncStatus: {},
    };
    palantirApi.getAllStatus.mockResolvedValue(mockData);

    const { result } = renderHook(() => usePalantirSync({ autoRefresh: false }));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.integrationStatus).toBe('degraded');
    expect(result.current.isCircuitOpen).toBe(true);
  });

  test('returns warning status when sync has errors', async () => {
    const mockData = {
      health: { status: 'ok', is_healthy: true },
      circuitBreaker: { state: 'CLOSED' },
      syncStatus: {
        ThreatActor: { last_sync_status: 'failed', objects_synced: 0 },
      },
    };
    palantirApi.getAllStatus.mockResolvedValue(mockData);

    const { result } = renderHook(() => usePalantirSync({ autoRefresh: false }));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.integrationStatus).toBe('warning');
    expect(result.current.hasSyncErrors).toBe(true);
  });

  test('cleans up interval on unmount', async () => {
    vi.useFakeTimers();
    const mockData = {
      health: { status: 'ok', is_healthy: true },
      circuitBreaker: { state: 'CLOSED' },
      syncStatus: {},
    };
    palantirApi.getAllStatus.mockResolvedValue(mockData);

    const { unmount } = renderHook(() =>
      usePalantirSync({ refreshInterval: 5000, autoRefresh: true })
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });

    expect(palantirApi.getAllStatus).toHaveBeenCalledTimes(1);

    unmount();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });

    // Should not have been called again after unmount
    expect(palantirApi.getAllStatus).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });
});

describe('useCircuitBreaker', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('fetches circuit breaker status', async () => {
    vi.useFakeTimers();
    const mockStatus = { state: 'CLOSED', failure_count: 0 };
    palantirApi.getCircuitBreaker.mockResolvedValue(mockStatus);

    const { result } = renderHook(() => useCircuitBreaker());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });

    expect(result.current.circuitBreaker).toEqual(mockStatus);
    expect(result.current.state).toBe('CLOSED');
    vi.useRealTimers();
  });

  test('provides reset function', async () => {
    vi.useFakeTimers();
    palantirApi.getCircuitBreaker.mockResolvedValue({ state: 'OPEN' });
    palantirApi.resetCircuitBreaker.mockResolvedValue({ status: 'success', new_state: 'CLOSED' });

    const { result } = renderHook(() => useCircuitBreaker());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });

    await act(async () => {
      await result.current.reset();
    });

    expect(palantirApi.resetCircuitBreaker).toHaveBeenCalled();
    vi.useRealTimers();
  });

  test('provides refetch function', async () => {
    vi.useFakeTimers();
    palantirApi.getCircuitBreaker.mockResolvedValue({ state: 'CLOSED' });

    const { result } = renderHook(() => useCircuitBreaker());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });

    expect(palantirApi.getCircuitBreaker).toHaveBeenCalledTimes(1);

    await act(async () => {
      await result.current.refetch();
    });

    expect(palantirApi.getCircuitBreaker).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });
});

describe('usePalantirHealth', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('fetches health status', async () => {
    vi.useFakeTimers();
    const mockHealth = { status: 'ok', is_healthy: true };
    palantirApi.getHealth.mockResolvedValue(mockHealth);

    const { result } = renderHook(() => usePalantirHealth());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });

    expect(result.current.health).toEqual(mockHealth);
    expect(result.current.isHealthy).toBe(true);
    expect(result.current.status).toBe('ok');
    vi.useRealTimers();
  });

  test('isHealthy is false when is_healthy is false', async () => {
    vi.useFakeTimers();
    const mockHealth = { status: 'degraded', is_healthy: false };
    palantirApi.getHealth.mockResolvedValue(mockHealth);

    const { result } = renderHook(() => usePalantirHealth());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });

    expect(result.current.isHealthy).toBe(false);
    vi.useRealTimers();
  });

  test('provides refetch function', async () => {
    vi.useFakeTimers();
    palantirApi.getHealth.mockResolvedValue({ status: 'ok', is_healthy: true });

    const { result } = renderHook(() => usePalantirHealth());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });

    expect(palantirApi.getHealth).toHaveBeenCalledTimes(1);

    await act(async () => {
      await result.current.refetch();
    });

    expect(palantirApi.getHealth).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });
});
