import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { useCustomerHealth, useHealthOverview, useIncidents } from './useCustomerHealth';

// Mock the customerHealthApi
vi.mock('../services/customerHealthApi', () => ({
  getHealthOverview: vi.fn(),
  getComponentHealth: vi.fn(),
  getHealthHistory: vi.fn(),
  getIncidents: vi.fn(),
  getRecommendations: vi.fn(),
  acknowledgeIncident: vi.fn(),
  resolveIncident: vi.fn(),
  dismissRecommendation: vi.fn(),
  exportHealthReport: vi.fn(),
  TimeRanges: {
    HOUR: '1h',
    DAY: '24h',
    WEEK: '7d',
    MONTH: '30d',
  },
}));

import * as api from '../services/customerHealthApi';

describe('useCustomerHealth', () => {
  const mockOverview = {
    score: 85,
    status: 'healthy',
    lastUpdated: '2025-01-01T00:00:00Z',
    components: [
      { name: 'API', status: 'healthy', score: 95 },
      { name: 'Database', status: 'healthy', score: 88 },
    ],
    trend: {
      data: [
        { timestamp: '2025-01-01', score: 82 },
        { timestamp: '2025-01-02', score: 84 },
        { timestamp: '2025-01-03', score: 85 },
      ],
    },
  };

  const mockHistory = {
    data: [
      { timestamp: '2025-01-01', score: 82 },
      { timestamp: '2025-01-02', score: 84 },
      { timestamp: '2025-01-03', score: 85 },
    ],
  };

  const mockIncidents = {
    incidents: [
      { id: 'inc-1', title: 'High latency', severity: 'medium', status: 'active' },
      { id: 'inc-2', title: 'Memory spike', severity: 'low', status: 'resolved' },
    ],
    total: 2,
    has_more: false,
  };

  const mockRecommendations = [
    { id: 'rec-1', title: 'Upgrade instance', priority: 'high' },
    { id: 'rec-2', title: 'Enable caching', priority: 'medium' },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    api.getHealthOverview.mockResolvedValue(mockOverview);
    api.getHealthHistory.mockResolvedValue(mockHistory);
    api.getIncidents.mockResolvedValue(mockIncidents);
    api.getRecommendations.mockResolvedValue(mockRecommendations);
  });

  test('initially has loading state', () => {
    const { result } = renderHook(() => useCustomerHealth({ autoRefresh: false }));

    expect(result.current.isLoading).toBe(true);
    expect(result.current.overview).toBeNull();
  });

  test('fetches health data on mount', async () => {
    const { result } = renderHook(() => useCustomerHealth({ autoRefresh: false }));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.overview).toEqual(mockOverview);
    expect(result.current.incidents).toEqual(mockIncidents);
    expect(result.current.recommendations).toEqual(mockRecommendations);
  });

  test('handles fetch error', async () => {
    api.getHealthOverview.mockRejectedValue(new Error('API Error'));

    const { result } = renderHook(() => useCustomerHealth({ autoRefresh: false }));

    await waitFor(() => {
      expect(result.current.loadingOverview).toBe(false);
    });

    expect(result.current.error).toBeTruthy();
  });

  test('refresh triggers new fetch', async () => {
    const { result } = renderHook(() => useCustomerHealth({ autoRefresh: false }));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(api.getHealthOverview).toHaveBeenCalledTimes(2); // Initial + useEffect trigger

    await act(async () => {
      await result.current.refreshData();
    });

    expect(api.getHealthOverview).toHaveBeenCalled();
  });

  test('computes healthScore from overview', async () => {
    api.getHealthOverview.mockResolvedValue({ ...mockOverview, score: 95 });

    const { result } = renderHook(() => useCustomerHealth({ autoRefresh: false }));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.healthScore).toBe(95);
  });

  test('computes healthStatus from overview', async () => {
    api.getHealthOverview.mockResolvedValue({ ...mockOverview, status: 'warning' });

    const { result } = renderHook(() => useCustomerHealth({ autoRefresh: false }));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.healthStatus).toBe('warning');
  });

  test('calculates active incidents count', async () => {
    const { result } = renderHook(() => useCustomerHealth({ autoRefresh: false }));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.activeIncidentsCount).toBe(1);
  });

  test('can change time range', async () => {
    const { result } = renderHook(() => useCustomerHealth({ autoRefresh: false }));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    act(() => {
      result.current.setTimeRange('7d');
    });

    expect(result.current.timeRange).toBe('7d');
  });

  test('can acknowledge incident', async () => {
    api.acknowledgeIncident.mockResolvedValue({ success: true });

    const { result } = renderHook(() => useCustomerHealth({ autoRefresh: false }));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      const response = await result.current.acknowledgeIncident('inc-1', 'Investigating');
      expect(response.success).toBe(true);
    });

    expect(api.acknowledgeIncident).toHaveBeenCalledWith('inc-1', 'Investigating');
  });

  test('can resolve incident', async () => {
    api.resolveIncident.mockResolvedValue({ success: true });

    const { result } = renderHook(() => useCustomerHealth({ autoRefresh: false }));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      const response = await result.current.resolveIncident('inc-1', 'Fixed by scaling up');
      expect(response.success).toBe(true);
    });

    expect(api.resolveIncident).toHaveBeenCalledWith('inc-1', 'Fixed by scaling up');
  });
});

describe('useHealthOverview', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getHealthOverview.mockResolvedValue({
      score: 85,
      status: 'healthy',
    });
  });

  test('fetches overview data', async () => {
    const { result } = renderHook(() => useHealthOverview());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.overview).toBeDefined();
    expect(result.current.overview.score).toBe(85);
  });

  test('handles error', async () => {
    api.getHealthOverview.mockRejectedValue(new Error('Failed'));

    const { result } = renderHook(() => useHealthOverview());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBeTruthy();
  });
});

describe('useIncidents', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getIncidents.mockResolvedValue({
      incidents: [{ id: 'inc-1', title: 'Test', status: 'active' }],
      total: 1,
      has_more: false,
    });
  });

  test('fetches incidents', async () => {
    const { result } = renderHook(() => useIncidents());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.incidents.length).toBe(1);
    expect(result.current.total).toBe(1);
  });

  test('supports refresh', async () => {
    const { result } = renderHook(() => useIncidents());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.refresh();
    });

    expect(api.getIncidents).toHaveBeenCalledTimes(2);
  });
});
