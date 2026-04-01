/**
 * Palantir API Service Tests
 *
 * Tests for the Palantir AIP API service layer.
 *
 * ADR-075: Palantir AIP UI Enhancements
 */

import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock the api module before importing palantirApi
vi.mock('./api', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    constructor(message, status, details) {
      super(message);
      this.status = status;
      this.details = details;
    }
  },
}));

import * as palantirApi from './palantirApi';
import { apiClient } from './api';

describe('palantirApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('getHealth', () => {
    test('returns health data on success', async () => {
      const mockHealth = {
        status: 'ok',
        connector_status: 'CLOSED',
        is_healthy: true,
        message: null,
      };

      apiClient.get.mockResolvedValue({ data: mockHealth });

      const result = await palantirApi.getHealth();

      expect(apiClient.get).toHaveBeenCalledWith('/api/v1/palantir/health');
      expect(result).toEqual(mockHealth);
    });

    test('returns mock data when fetch fails', async () => {
      apiClient.get.mockRejectedValue(new Error('Network error'));

      const result = await palantirApi.getHealth();

      // Should return mock data with correct structure
      expect(result).toHaveProperty('status', 'ok');
      expect(result).toHaveProperty('is_healthy', true);
      expect(result).toHaveProperty('connector_status');
    });
  });

  describe('getActiveThreats', () => {
    test('returns active threats list', async () => {
      const mockThreats = [
        {
          threat_id: 'threat-001',
          source_platform: 'palantir',
          cves: ['CVE-2024-0001'],
          priority_score: 85,
        },
      ];

      apiClient.get.mockResolvedValue({ data: mockThreats });

      const result = await palantirApi.getActiveThreats();

      expect(apiClient.get).toHaveBeenCalledWith('/api/v1/palantir/threats/active');
      expect(result).toEqual(mockThreats);
    });

    test('returns mock data on failure', async () => {
      apiClient.get.mockRejectedValue(new Error('Network error'));

      const result = await palantirApi.getActiveThreats();

      expect(Array.isArray(result)).toBe(true);
      expect(result.length).toBeGreaterThan(0);
      expect(result[0]).toHaveProperty('threat_id');
    });
  });

  describe('getThreatContext', () => {
    test('posts CVE IDs and returns context', async () => {
      const cveIds = ['CVE-2024-0001', 'CVE-2024-0002'];
      const mockContext = [
        { cve_id: 'CVE-2024-0001', epss_score: 0.5 },
        { cve_id: 'CVE-2024-0002', epss_score: 0.3 },
      ];

      apiClient.post.mockResolvedValue({ data: mockContext });

      const result = await palantirApi.getThreatContext(cveIds);

      expect(apiClient.post).toHaveBeenCalledWith(
        '/api/v1/palantir/threats/context',
        { cve_ids: cveIds }
      );
      expect(result).toEqual(mockContext);
    });
  });

  describe('getCircuitBreaker', () => {
    test('returns circuit breaker status', async () => {
      const mockStatus = {
        name: 'palantir_integration',
        state: 'CLOSED',
        failure_count: 0,
        success_count: 47,
      };

      apiClient.get.mockResolvedValue({ data: mockStatus });

      const result = await palantirApi.getCircuitBreaker();

      expect(apiClient.get).toHaveBeenCalledWith('/api/v1/palantir/circuit-breaker');
      expect(result).toEqual(mockStatus);
    });

    test('returns mock data with CLOSED state on failure', async () => {
      apiClient.get.mockRejectedValue(new Error('Network error'));

      const result = await palantirApi.getCircuitBreaker();

      expect(result).toHaveProperty('state', 'CLOSED');
      expect(result).toHaveProperty('name', 'palantir_integration');
    });
  });

  describe('resetCircuitBreaker', () => {
    test('sends POST request to reset', async () => {
      apiClient.post.mockResolvedValue({ data: { status: 'success', new_state: 'CLOSED' } });

      const result = await palantirApi.resetCircuitBreaker();

      expect(apiClient.post).toHaveBeenCalledWith('/api/v1/palantir/circuit-breaker/reset');
      expect(result).toEqual({ status: 'success', new_state: 'CLOSED' });
    });
  });

  describe('getSyncStatus', () => {
    test('returns sync status for all object types', async () => {
      const mockStatus = {
        ThreatActor: {
          object_type: 'ThreatActor',
          objects_synced: 247,
          last_sync_time: new Date().toISOString(),
          last_sync_status: 'synced',
        },
        Vulnerability: {
          object_type: 'Vulnerability',
          objects_synced: 1892,
          last_sync_time: new Date().toISOString(),
          last_sync_status: 'synced',
        },
      };

      apiClient.get.mockResolvedValue({ data: mockStatus });

      const result = await palantirApi.getSyncStatus();

      expect(result).toEqual(mockStatus);
    });

    test('returns mock data on failure', async () => {
      apiClient.get.mockRejectedValue(new Error('Network error'));

      const result = await palantirApi.getSyncStatus();

      // Actual mock uses ThreatActor, Vulnerability, Asset, Compliance
      expect(result).toHaveProperty('ThreatActor');
      expect(result.ThreatActor).toHaveProperty('objects_synced');
      expect(result).toHaveProperty('Vulnerability');
      expect(result).toHaveProperty('Asset');
      expect(result).toHaveProperty('Compliance');
    });
  });

  describe('triggerSync', () => {
    test('sends POST request to trigger sync', async () => {
      apiClient.post.mockResolvedValue({ data: { triggered: true } });

      const result = await palantirApi.triggerSync('ThreatActor');

      expect(apiClient.post).toHaveBeenCalledWith(
        '/api/v1/palantir/sync/ThreatActor',
        { full_sync: false }
      );
      expect(result).toEqual({ triggered: true });
    });

    test('sends full_sync flag when requested', async () => {
      apiClient.post.mockResolvedValue({ data: { triggered: true } });

      await palantirApi.triggerSync('Asset', true);

      expect(apiClient.post).toHaveBeenCalledWith(
        '/api/v1/palantir/sync/Asset',
        { full_sync: true }
      );
    });
  });

  describe('getAssetCriticality', () => {
    test('returns asset criticality for repo', async () => {
      const mockCriticality = {
        asset_id: 'repo-123',
        criticality_score: 8,
        data_classification: 'Confidential',
        business_owner: 'owner@example.com',
      };

      apiClient.get.mockResolvedValue({ data: mockCriticality });

      const result = await palantirApi.getAssetCriticality('repo-123');

      expect(apiClient.get).toHaveBeenCalledWith(
        '/api/v1/palantir/assets/repo-123/criticality'
      );
      expect(result).toEqual(mockCriticality);
    });
  });

  describe('testConnection', () => {
    test('sends POST request with config and returns result', async () => {
      const testConfig = {
        ontology_api_url: 'https://test.palantir.com',
        api_key: 'test-key',
      };
      const mockResult = { success: true, latency_ms: 150 };

      apiClient.post.mockResolvedValue({ data: mockResult });

      const result = await palantirApi.testConnection(testConfig);

      expect(apiClient.post).toHaveBeenCalledWith(
        '/api/v1/palantir/test-connection',
        testConfig
      );
      expect(result).toEqual(mockResult);
    });

    test('throws on network error', async () => {
      apiClient.post.mockRejectedValue(new Error('Connection refused'));

      await expect(palantirApi.testConnection({ ontology_url: 'test' })).rejects.toThrow();
    });
  });

  describe('getEventMetrics', () => {
    test('returns event processing metrics', async () => {
      const mockMetrics = {
        total_events: 5000,
        events_processed: 4950,
        events_failed: 50,
        dlq_size: 10,
      };

      apiClient.get.mockResolvedValue({ data: mockMetrics });

      const result = await palantirApi.getEventMetrics();

      expect(apiClient.get).toHaveBeenCalledWith('/api/v1/palantir/events/metrics');
      expect(result).toEqual(mockMetrics);
    });
  });

  describe('retryDLQEvents', () => {
    test('sends POST request to retry DLQ events', async () => {
      apiClient.post.mockResolvedValue({ data: { retried: 10, dlq_stats: {} } });

      const result = await palantirApi.retryDLQEvents();

      expect(apiClient.post).toHaveBeenCalledWith('/api/v1/palantir/events/retry-dlq');
      expect(result).toEqual({ retried: 10, dlq_stats: {} });
    });
  });

  describe('getAllStatus', () => {
    test('fetches health, circuit breaker, and sync status in parallel', async () => {
      const mockHealth = { status: 'ok', is_healthy: true };
      const mockCircuitBreaker = { state: 'CLOSED' };
      const mockSyncStatus = { ThreatActor: { objects_synced: 100 } };

      apiClient.get.mockImplementation((url) => {
        if (url.includes('health')) return Promise.resolve({ data: mockHealth });
        if (url.includes('circuit-breaker')) return Promise.resolve({ data: mockCircuitBreaker });
        if (url.includes('sync')) return Promise.resolve({ data: mockSyncStatus });
        return Promise.reject(new Error('Unknown endpoint'));
      });

      const result = await palantirApi.getAllStatus();

      expect(result.health).toEqual(mockHealth);
      expect(result.circuitBreaker).toEqual(mockCircuitBreaker);
      expect(result.syncStatus).toEqual(mockSyncStatus);
    });
  });

  describe('getPrioritizedCVEs', () => {
    test('returns CVEs sorted by priority score', async () => {
      const mockThreats = [
        { threat_id: 't1', priority_score: 50 },
        { threat_id: 't2', priority_score: 90 },
        { threat_id: 't3', priority_score: 70 },
      ];

      apiClient.post.mockResolvedValue({ data: mockThreats });

      const result = await palantirApi.getPrioritizedCVEs(['CVE-1', 'CVE-2']);

      expect(result[0].priority_score).toBe(90);
      expect(result[1].priority_score).toBe(70);
      expect(result[2].priority_score).toBe(50);
    });
  });
});
