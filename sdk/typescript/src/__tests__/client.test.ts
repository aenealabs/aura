/**
 * Tests for AuraClient
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import {
  AuraClient,
  AuraAPIError,
  AuthenticationError,
  NotFoundError,
  ValidationError,
} from '../client/AuraClient';
import type { ExtensionConfig, ScanResponse, Finding, Patch } from '../types';

// Mock server setup
const server = setupServer();

beforeEach(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  server.resetHandlers();
  server.close();
});

describe('AuraClient', () => {
  const baseUrl = 'http://localhost:8080';
  let client: AuraClient;

  beforeEach(() => {
    client = new AuraClient({ baseUrl, apiKey: 'test-api-key' });
  });

  describe('constructor', () => {
    it('creates client with config', () => {
      expect(client).toBeInstanceOf(AuraClient);
    });

    it('has extension API', () => {
      expect(client.extension).toBeDefined();
    });

    it('has approvals API', () => {
      expect(client.approvals).toBeDefined();
    });

    it('has incidents API', () => {
      expect(client.incidents).toBeDefined();
    });

    it('has settings API', () => {
      expect(client.settings).toBeDefined();
    });
  });

  describe('healthCheck', () => {
    it('returns true when server is healthy', async () => {
      server.use(
        http.get(`${baseUrl}/health`, () => {
          return HttpResponse.json({ status: 'ok' });
        })
      );

      const result = await client.healthCheck();
      expect(result).toBe(true);
    });

    it('returns false when server is unhealthy', async () => {
      server.use(
        http.get(`${baseUrl}/health`, () => {
          return new HttpResponse(null, { status: 500 });
        })
      );

      const result = await client.healthCheck();
      expect(result).toBe(false);
    });
  });

  describe('extension API', () => {
    describe('getConfig', () => {
      it('returns extension config', async () => {
        const mockConfig: ExtensionConfig = {
          scan_on_save: true,
          auto_suggest_patches: true,
          severity_threshold: 'low',
          supported_languages: ['python', 'typescript'],
          api_version: '1.0.0',
          features: { realtime_scan: true },
        };

        server.use(
          http.get(`${baseUrl}/api/v1/extension/config`, () => {
            return HttpResponse.json(mockConfig);
          })
        );

        const config = await client.extension.getConfig();
        expect(config).toEqual(mockConfig);
      });
    });

    describe('scanFile', () => {
      it('scans file and returns response', async () => {
        const mockResponse: ScanResponse = {
          scan_id: 'scan-123',
          status: 'completed',
          findings_count: 2,
          message: 'Found 2 issues',
        };

        server.use(
          http.post(`${baseUrl}/api/v1/extension/scan`, () => {
            return HttpResponse.json(mockResponse);
          })
        );

        const result = await client.extension.scanFile({
          file_path: 'test.py',
          file_content: 'eval(x)',
          language: 'python',
        });

        expect(result).toEqual(mockResponse);
      });
    });

    describe('getFindings', () => {
      it('returns findings for file', async () => {
        const mockFindings: Finding[] = [
          {
            id: 'f1',
            file_path: 'test.py',
            line_start: 1,
            line_end: 1,
            column_start: 0,
            column_end: 10,
            severity: 'critical',
            category: 'injection',
            title: 'Dangerous eval',
            description: 'Using eval is dangerous',
            code_snippet: 'eval(x)',
            suggestion: 'Use ast.literal_eval',
            cwe_id: 'CWE-95',
            owasp_category: 'A03:2021',
            has_patch: false,
            patch_id: null,
          },
        ];

        server.use(
          http.get(`${baseUrl}/api/v1/extension/findings/test.py`, () => {
            return HttpResponse.json({
              file_path: 'test.py',
              findings: mockFindings,
              scan_timestamp: '2024-01-01T00:00:00Z',
              scan_duration_ms: 100,
            });
          })
        );

        const result = await client.extension.getFindings('test.py');
        expect(result.findings).toEqual(mockFindings);
      });
    });

    describe('generatePatch', () => {
      it('generates patch for finding', async () => {
        const mockPatch: Patch = {
          id: 'p1',
          finding_id: 'f1',
          file_path: 'test.py',
          status: 'ready',
          original_code: 'eval(x)',
          patched_code: 'ast.literal_eval(x)',
          diff: '- eval(x)\n+ ast.literal_eval(x)',
          explanation: 'Replaced eval with safer alternative',
          confidence: 0.95,
          requires_approval: true,
          approval_id: 'a1',
          created_at: '2024-01-01T00:00:00Z',
          applied_at: null,
        };

        server.use(
          http.post(`${baseUrl}/api/v1/extension/patches`, () => {
            return HttpResponse.json({
              patch: mockPatch,
              message: 'Patch generated',
            });
          })
        );

        const result = await client.extension.generatePatch({
          finding_id: 'f1',
          file_path: 'test.py',
          file_content: 'eval(x)',
          context_lines: 10,
        });

        expect(result.patch).toEqual(mockPatch);
      });
    });

    describe('applyPatch', () => {
      it('applies approved patch', async () => {
        server.use(
          http.post(`${baseUrl}/api/v1/extension/patches/p1/apply`, () => {
            return HttpResponse.json({
              success: true,
              patch_id: 'p1',
              file_path: 'test.py',
              message: 'Patch applied',
              backup_path: null,
            });
          })
        );

        const result = await client.extension.applyPatch('p1', true);
        expect(result.success).toBe(true);
      });
    });
  });

  describe('approvals API', () => {
    describe('list', () => {
      it('lists approvals with filters', async () => {
        server.use(
          http.get(`${baseUrl}/api/v1/approvals`, ({ request }) => {
            const url = new URL(request.url);
            expect(url.searchParams.get('status')).toBe('pending');

            return HttpResponse.json({
              approvals: [],
              total: 0,
              page: 1,
              page_size: 20,
              has_more: false,
            });
          })
        );

        const result = await client.approvals.list({ status: 'pending' });
        expect(result.total).toBe(0);
      });
    });

    describe('approve', () => {
      it('approves an approval request', async () => {
        server.use(
          http.post(`${baseUrl}/api/v1/approvals/a1/approve`, () => {
            return HttpResponse.json({
              success: true,
              approval_id: 'a1',
              new_status: 'approved',
              message: 'Approved',
              reviewed_at: '2024-01-01T00:00:00Z',
            });
          })
        );

        const result = await client.approvals.approve('a1', 'LGTM');
        expect(result.success).toBe(true);
        expect(result.new_status).toBe('approved');
      });
    });

    describe('reject', () => {
      it('rejects an approval request', async () => {
        server.use(
          http.post(`${baseUrl}/api/v1/approvals/a1/reject`, () => {
            return HttpResponse.json({
              success: true,
              approval_id: 'a1',
              new_status: 'rejected',
              message: 'Rejected',
              reviewed_at: '2024-01-01T00:00:00Z',
            });
          })
        );

        const result = await client.approvals.reject('a1', 'Not safe');
        expect(result.success).toBe(true);
        expect(result.new_status).toBe('rejected');
      });
    });
  });

  describe('error handling', () => {
    it('throws AuthenticationError on 401', async () => {
      server.use(
        http.get(`${baseUrl}/api/v1/extension/config`, () => {
          return HttpResponse.json(
            { detail: 'Invalid API key' },
            { status: 401 }
          );
        })
      );

      await expect(client.extension.getConfig()).rejects.toThrow(
        AuthenticationError
      );
    });

    it('throws NotFoundError on 404', async () => {
      server.use(
        http.get(`${baseUrl}/api/v1/extension/patches/nonexistent`, () => {
          return HttpResponse.json(
            { detail: 'Patch not found' },
            { status: 404 }
          );
        })
      );

      await expect(
        client.extension.getPatch('nonexistent')
      ).rejects.toThrow(NotFoundError);
    });

    it('throws ValidationError on 422', async () => {
      server.use(
        http.post(`${baseUrl}/api/v1/extension/scan`, () => {
          return HttpResponse.json(
            {
              detail: [
                { loc: ['body', 'file_path'], msg: 'required', type: 'missing' },
              ],
            },
            { status: 422 }
          );
        })
      );

      await expect(
        client.extension.scanFile({
          file_path: '',
          file_content: '',
          language: 'python',
        })
      ).rejects.toThrow(ValidationError);
    });

    it('throws AuraAPIError on other errors', async () => {
      server.use(
        http.get(`${baseUrl}/api/v1/extension/config`, () => {
          return HttpResponse.json(
            { detail: 'Internal error' },
            { status: 500 }
          );
        })
      );

      await expect(client.extension.getConfig()).rejects.toThrow(AuraAPIError);
    });
  });

  describe('authentication', () => {
    it('includes API key in headers', async () => {
      server.use(
        http.get(`${baseUrl}/api/v1/extension/config`, ({ request }) => {
          expect(request.headers.get('X-API-Key')).toBe('test-api-key');
          return HttpResponse.json({
            scan_on_save: true,
            auto_suggest_patches: true,
            severity_threshold: 'low',
            supported_languages: [],
            api_version: '1.0.0',
            features: {},
          });
        })
      );

      await client.extension.getConfig();
    });

    it('can update JWT token', async () => {
      client.setJwtToken('new-token');

      server.use(
        http.get(`${baseUrl}/api/v1/extension/config`, ({ request }) => {
          expect(request.headers.get('Authorization')).toBe('Bearer new-token');
          return HttpResponse.json({
            scan_on_save: true,
            auto_suggest_patches: true,
            severity_threshold: 'low',
            supported_languages: [],
            api_version: '1.0.0',
            features: {},
          });
        })
      );

      await client.extension.getConfig();
    });
  });
});
