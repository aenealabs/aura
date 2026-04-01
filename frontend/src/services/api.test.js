import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { apiClient, ApiError } from './api';

// Mock fetch globally
global.fetch = vi.fn();

describe('api', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('apiClient', () => {
    test('makes GET request', async () => {
      const mockResponse = { id: 1, name: 'test' };
      global.fetch.mockResolvedValue({
        ok: true,
        headers: {
          get: () => 'application/json',
        },
        json: () => Promise.resolve(mockResponse),
      });

      const result = await apiClient.get('/test-endpoint');

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/test-endpoint'),
        expect.objectContaining({ method: 'GET' })
      );
      expect(result).toEqual({ data: mockResponse });
    });

    test('makes POST request with body', async () => {
      const mockResponse = { id: 1 };
      const postData = { name: 'Test' };

      global.fetch.mockResolvedValue({
        ok: true,
        headers: {
          get: () => 'application/json',
        },
        json: () => Promise.resolve(mockResponse),
      });

      const result = await apiClient.post('/items', postData);

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/items'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(postData),
        })
      );
      expect(result).toEqual({ data: mockResponse });
    });

    test('makes PUT request', async () => {
      const mockResponse = { updated: true };
      const putData = { name: 'Updated' };

      global.fetch.mockResolvedValue({
        ok: true,
        headers: {
          get: () => 'application/json',
        },
        json: () => Promise.resolve(mockResponse),
      });

      await apiClient.put('/items/1', putData);

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/items/1'),
        expect.objectContaining({ method: 'PUT' })
      );
    });

    test('makes DELETE request', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        headers: {
          get: () => 'application/json',
        },
        json: () => Promise.resolve({ deleted: true }),
      });

      await apiClient.delete('/items/1');

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/items/1'),
        expect.objectContaining({ method: 'DELETE' })
      );
    });

    test('sets content-type header for JSON', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        headers: {
          get: () => 'application/json',
        },
        json: () => Promise.resolve({}),
      });

      await apiClient.post('/items', { data: 'test' });

      expect(fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
          }),
        })
      );
    });
  });

  describe('error handling', () => {
    test('extracts error message from response', async () => {
      global.fetch.mockResolvedValue({
        ok: false,
        status: 400,
        json: () => Promise.resolve({ message: 'Bad request' }),
      });

      await expect(apiClient.get('/error')).rejects.toThrow('Bad request');
    });

    test('handles network errors', async () => {
      global.fetch.mockRejectedValue(new Error('Network error'));

      await expect(apiClient.get('/network-error')).rejects.toThrow('Network error');
    });

    test('handles 401 unauthorized', async () => {
      global.fetch.mockResolvedValue({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ message: 'Unauthorized' }),
      });

      await expect(apiClient.get('/protected')).rejects.toThrow();
    });

    test('handles 403 forbidden', async () => {
      global.fetch.mockResolvedValue({
        ok: false,
        status: 403,
        json: () => Promise.resolve({ message: 'Forbidden' }),
      });

      await expect(apiClient.get('/forbidden')).rejects.toThrow('Forbidden');
    });

    test('handles 404 not found', async () => {
      global.fetch.mockResolvedValue({
        ok: false,
        status: 404,
        json: () => Promise.resolve({ message: 'Not found' }),
      });

      await expect(apiClient.get('/missing')).rejects.toThrow('Not found');
    });

    test('handles 500 server error', async () => {
      global.fetch.mockResolvedValue({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ message: 'Internal server error' }),
      });

      await expect(apiClient.get('/server-error')).rejects.toThrow();
    });

    test('handles non-JSON error response', async () => {
      global.fetch.mockResolvedValue({
        ok: false,
        status: 500,
        json: () => Promise.reject(new Error('Invalid JSON')),
      });

      await expect(apiClient.get('/html-error')).rejects.toThrow();
    });
  });

  describe('request configuration', () => {
    test('supports custom headers', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        headers: {
          get: () => 'application/json',
        },
        json: () => Promise.resolve({}),
      });

      await apiClient.get('/endpoint', {
        headers: {
          Authorization: 'Bearer test-token',
        },
      });

      expect(fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer test-token',
          }),
        })
      );
    });

    test('makes PATCH request', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        headers: {
          get: () => 'application/json',
        },
        json: () => Promise.resolve({ patched: true }),
      });

      await apiClient.patch('/items/1', { status: 'active' });

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/items/1'),
        expect.objectContaining({ method: 'PATCH' })
      );
    });
  });
});
