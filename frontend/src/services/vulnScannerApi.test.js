/**
 * Tests for the Vulnerability Scanner API service
 *
 * - Requests go to /api/v1/scanner/... once (apiClient adds the /api/v1 prefix)
 * - Functions resolve to the response data, not apiClient's { data } wrapper
 * - Query params are sent, and the SARIF download is a Blob the page can save
 */

import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  getScanDetail,
  getTruePositiveRate,
  getRecentScanActivity,
  launchScan,
  downloadSARIF,
} from './vulnScannerApi';

function respond(body) {
  return {
    ok: true,
    status: 200,
    headers: { get: () => 'application/json' },
    json: async () => body,
    text: async () => JSON.stringify(body),
  };
}

let fetchMock;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('vulnScannerApi', () => {
  test('getScanDetail calls the scanner path once and returns the scan itself', async () => {
    const scan = { scan_id: 'scan-1', status: 'completed', findings: [] };
    fetchMock.mockResolvedValue(respond(scan));

    await expect(getScanDetail('scan-1')).resolves.toEqual(scan);
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/scanner/scans/scan-1');
  });

  test('metric calls return the data the widgets render', async () => {
    fetchMock.mockResolvedValue(respond({ rate: 0.93 }));

    await expect(getTruePositiveRate()).resolves.toEqual({ rate: 0.93 });
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/scanner/metrics/true-positive-rate');
  });

  test('getRecentScanActivity sends its filters as a query string', async () => {
    fetchMock.mockResolvedValue(respond([]));

    await getRecentScanActivity({ sort_by: 'severity', sort_order: 'asc', severity_filter: undefined });
    expect(fetchMock.mock.calls[0][0]).toBe(
      '/api/v1/scanner/metrics/recent-activity?sort_by=severity&sort_order=asc'
    );
  });

  test('launchScan posts the config and returns the created scan', async () => {
    fetchMock.mockResolvedValue(respond({ scan_id: 'scan-2' }));

    await expect(launchScan({ repository_url: 'aura-core' })).resolves.toEqual({ scan_id: 'scan-2' });
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/scanner/scans/launch');
    expect(fetchMock.mock.calls[0][1].method).toBe('POST');
  });

  test('downloadSARIF returns a SARIF Blob', async () => {
    const sarif = { version: '2.1.0', runs: [] };
    fetchMock.mockResolvedValue(respond(sarif));

    const blob = await downloadSARIF('scan-1');
    expect(blob).toBeInstanceOf(Blob);
    expect(blob.type).toBe('application/sarif+json');
    expect(JSON.parse(await blob.text())).toEqual(sarif);
  });
});
