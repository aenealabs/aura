import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { useApi, useMutation, useQuery, useOnlineStatus } from './useApi';

describe('useApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('initially has loading state when not manual', () => {
    const mockFn = vi.fn().mockResolvedValue({ data: 'test' });

    const { result } = renderHook(() => useApi(mockFn, { manual: false }));

    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBeNull();
  });

  test('fetches data on mount when not manual', async () => {
    const mockData = { id: 1, name: 'Test' };
    const mockFn = vi.fn().mockResolvedValue(mockData);

    const { result } = renderHook(() => useApi(mockFn, { manual: false }));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toEqual(mockData);
    expect(mockFn).toHaveBeenCalledTimes(1);
  });

  test('passes args to api function via execute', async () => {
    const mockFn = vi.fn().mockResolvedValue({ data: 'test' });

    const { result } = renderHook(() => useApi(mockFn, { manual: true }));

    await act(async () => {
      await result.current.execute('arg1', 'arg2');
    });

    expect(mockFn).toHaveBeenCalledWith('arg1', 'arg2', expect.objectContaining({ signal: expect.any(AbortSignal) }));
  });

  test('handles fetch error', async () => {
    const mockError = new Error('Fetch failed');
    const mockFn = vi.fn().mockRejectedValue(mockError);

    const { result } = renderHook(() => useApi(mockFn, { manual: true, retries: 0 }));

    await act(async () => {
      try {
        await result.current.execute();
      } catch {
        // Expected
      }
    });

    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBe(mockError);
    expect(result.current.isError).toBe(true);
    expect(result.current.data).toBeNull();
  });

  test('retry triggers new request', async () => {
    const mockFn = vi.fn().mockResolvedValue({ data: 'test' });

    const { result } = renderHook(() => useApi(mockFn, { manual: true }));

    await act(async () => {
      await result.current.execute();
    });

    expect(mockFn).toHaveBeenCalledTimes(1);

    await act(async () => {
      await result.current.retry();
    });

    expect(mockFn).toHaveBeenCalledTimes(2);
  });

  test('does not fetch on mount when manual is true', () => {
    const mockFn = vi.fn().mockResolvedValue({ data: 'test' });

    const { result } = renderHook(() => useApi(mockFn, { manual: true }));

    expect(result.current.loading).toBe(false);
    expect(mockFn).not.toHaveBeenCalled();
  });

  test('reset clears state', async () => {
    const mockFn = vi.fn().mockResolvedValue({ data: 'test' });

    const { result } = renderHook(() => useApi(mockFn, { manual: true }));

    await act(async () => {
      await result.current.execute();
    });

    expect(result.current.data).not.toBeNull();

    act(() => {
      result.current.reset();
    });

    expect(result.current.data).toBeNull();
    expect(result.current.error).toBeNull();
    expect(result.current.isSuccess).toBe(false);
  });

  test('calls onSuccess callback', async () => {
    const mockFn = vi.fn().mockResolvedValue({ id: 1 });
    const onSuccess = vi.fn();

    const { result } = renderHook(() =>
      useApi(mockFn, { manual: true, onSuccess })
    );

    await act(async () => {
      await result.current.execute();
    });

    expect(onSuccess).toHaveBeenCalledWith({ id: 1 });
  });

  test('calls onError callback', async () => {
    const mockError = new Error('Failed');
    const mockFn = vi.fn().mockRejectedValue(mockError);
    const onError = vi.fn();

    const { result } = renderHook(() =>
      useApi(mockFn, { manual: true, retries: 0, onError })
    );

    await act(async () => {
      try {
        await result.current.execute();
      } catch {
        // Expected
      }
    });

    expect(onError).toHaveBeenCalledWith(mockError);
  });

  test('isSuccess is true after successful request', async () => {
    const mockFn = vi.fn().mockResolvedValue({ success: true });

    const { result } = renderHook(() => useApi(mockFn, { manual: true }));

    await act(async () => {
      await result.current.execute();
    });

    expect(result.current.isSuccess).toBe(true);
    expect(result.current.isError).toBe(false);
  });

  test('isError is true after failed request', async () => {
    const mockFn = vi.fn().mockRejectedValue(new Error('Failed'));

    const { result } = renderHook(() => useApi(mockFn, { manual: true, retries: 0 }));

    await act(async () => {
      try {
        await result.current.execute();
      } catch {
        // Expected
      }
    });

    expect(result.current.isError).toBe(true);
    expect(result.current.isSuccess).toBe(false);
  });
});

describe('useMutation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('does not execute on mount', () => {
    const mockFn = vi.fn().mockResolvedValue({ success: true });

    const { result } = renderHook(() => useMutation(mockFn));

    expect(result.current.loading).toBe(false);
    expect(mockFn).not.toHaveBeenCalled();
  });

  test('executes mutation when execute is called', async () => {
    const mockFn = vi.fn().mockResolvedValue({ success: true });

    const { result } = renderHook(() => useMutation(mockFn));

    await act(async () => {
      await result.current.execute({ name: 'Test' });
    });

    expect(mockFn).toHaveBeenCalled();
    expect(result.current.data).toEqual({ success: true });
  });
});

describe('useQuery', () => {
  test('auto-executes on mount', async () => {
    const mockFn = vi.fn().mockResolvedValue({ data: 'test' });

    const { result } = renderHook(() => useQuery(mockFn));

    // Initially loading
    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(mockFn).toHaveBeenCalled();
    expect(result.current.data).toEqual({ data: 'test' });
  });
});

describe('useOnlineStatus', () => {
  test('returns true when navigator is online', () => {
    Object.defineProperty(navigator, 'onLine', { value: true, configurable: true });

    const { result } = renderHook(() => useOnlineStatus());

    expect(result.current).toBe(true);
  });
});
