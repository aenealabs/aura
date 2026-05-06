/**
 * Tests for SDK utilities
 */

import { describe, it, expect } from 'vitest';
import {
  compareSeverity,
  meetsSeverityThreshold,
  getSeverityColor,
  getSeverityLabel,
  isApprovalActionable,
  isPatchApplicable,
  groupFindingsByFile,
  groupFindingsBySeverity,
  sortFindingsBySeverity,
  countFindingsBySeverity,
  filterFindingsBySeverity,
  getCWEUrl,
  getOWASPUrl,
  formatDate,
  formatDateTime,
  getRelativeTime,
  isExpired,
  getTimeUntilExpiration,
  parseDiff,
  isValidFilePath,
  isValidApiKey,
  isValidJwt,
} from '../utils';
import type { Finding, Severity } from '../types';

describe('Severity Utilities', () => {
  describe('compareSeverity', () => {
    it('returns positive when first is more severe', () => {
      expect(compareSeverity('critical', 'high')).toBeGreaterThan(0);
      expect(compareSeverity('high', 'medium')).toBeGreaterThan(0);
      expect(compareSeverity('medium', 'low')).toBeGreaterThan(0);
      expect(compareSeverity('low', 'info')).toBeGreaterThan(0);
    });

    it('returns negative when first is less severe', () => {
      expect(compareSeverity('info', 'low')).toBeLessThan(0);
      expect(compareSeverity('low', 'medium')).toBeLessThan(0);
    });

    it('returns zero when equal', () => {
      expect(compareSeverity('critical', 'critical')).toBe(0);
      expect(compareSeverity('info', 'info')).toBe(0);
    });
  });

  describe('meetsSeverityThreshold', () => {
    it('returns true when severity meets threshold', () => {
      expect(meetsSeverityThreshold('critical', 'high')).toBe(true);
      expect(meetsSeverityThreshold('high', 'high')).toBe(true);
      expect(meetsSeverityThreshold('critical', 'info')).toBe(true);
    });

    it('returns false when severity below threshold', () => {
      expect(meetsSeverityThreshold('low', 'high')).toBe(false);
      expect(meetsSeverityThreshold('info', 'medium')).toBe(false);
    });
  });

  describe('getSeverityColor', () => {
    it('returns correct color for each severity', () => {
      expect(getSeverityColor('critical')).toBe('#DC2626');
      expect(getSeverityColor('high')).toBe('#EA580C');
      expect(getSeverityColor('medium')).toBe('#F59E0B');
      expect(getSeverityColor('low')).toBe('#3B82F6');
      expect(getSeverityColor('info')).toBe('#10B981');
    });
  });

  describe('getSeverityLabel', () => {
    it('capitalizes first letter', () => {
      expect(getSeverityLabel('critical')).toBe('Critical');
      expect(getSeverityLabel('info')).toBe('Info');
    });
  });
});

describe('Status Utilities', () => {
  describe('isApprovalActionable', () => {
    it('returns true for pending', () => {
      expect(isApprovalActionable('pending')).toBe(true);
    });

    it('returns false for other statuses', () => {
      expect(isApprovalActionable('approved')).toBe(false);
      expect(isApprovalActionable('rejected')).toBe(false);
      expect(isApprovalActionable('expired')).toBe(false);
    });
  });

  describe('isPatchApplicable', () => {
    it('returns true for approved and ready', () => {
      expect(isPatchApplicable('approved')).toBe(true);
      expect(isPatchApplicable('ready')).toBe(true);
    });

    it('returns false for other statuses', () => {
      expect(isPatchApplicable('pending')).toBe(false);
      expect(isPatchApplicable('rejected')).toBe(false);
      expect(isPatchApplicable('failed')).toBe(false);
    });
  });
});

describe('Finding Utilities', () => {
  const mockFindings: Finding[] = [
    {
      id: '1',
      file_path: 'file1.py',
      line_start: 1,
      line_end: 1,
      column_start: 0,
      column_end: 10,
      severity: 'critical',
      category: 'injection',
      title: 'Critical Issue',
      description: '',
      code_snippet: '',
      suggestion: '',
      cwe_id: null,
      owasp_category: null,
      has_patch: false,
      patch_id: null,
    },
    {
      id: '2',
      file_path: 'file1.py',
      line_start: 10,
      line_end: 10,
      column_start: 0,
      column_end: 10,
      severity: 'low',
      category: 'code_quality',
      title: 'Low Issue',
      description: '',
      code_snippet: '',
      suggestion: '',
      cwe_id: null,
      owasp_category: null,
      has_patch: false,
      patch_id: null,
    },
    {
      id: '3',
      file_path: 'file2.py',
      line_start: 5,
      line_end: 5,
      column_start: 0,
      column_end: 10,
      severity: 'high',
      category: 'xss',
      title: 'High Issue',
      description: '',
      code_snippet: '',
      suggestion: '',
      cwe_id: null,
      owasp_category: null,
      has_patch: false,
      patch_id: null,
    },
  ];

  describe('groupFindingsByFile', () => {
    it('groups findings by file path', () => {
      const groups = groupFindingsByFile(mockFindings);
      expect(groups.size).toBe(2);
      expect(groups.get('file1.py')?.length).toBe(2);
      expect(groups.get('file2.py')?.length).toBe(1);
    });
  });

  describe('groupFindingsBySeverity', () => {
    it('groups findings by severity', () => {
      const groups = groupFindingsBySeverity(mockFindings);
      expect(groups.get('critical')?.length).toBe(1);
      expect(groups.get('high')?.length).toBe(1);
      expect(groups.get('low')?.length).toBe(1);
    });
  });

  describe('sortFindingsBySeverity', () => {
    it('sorts by severity descending', () => {
      const sorted = sortFindingsBySeverity(mockFindings);
      expect(sorted[0].severity).toBe('critical');
      expect(sorted[1].severity).toBe('high');
      expect(sorted[2].severity).toBe('low');
    });

    it('does not mutate original array', () => {
      const original = [...mockFindings];
      sortFindingsBySeverity(mockFindings);
      expect(mockFindings).toEqual(original);
    });
  });

  describe('countFindingsBySeverity', () => {
    it('counts findings by severity', () => {
      const counts = countFindingsBySeverity(mockFindings);
      expect(counts.critical).toBe(1);
      expect(counts.high).toBe(1);
      expect(counts.medium).toBe(0);
      expect(counts.low).toBe(1);
      expect(counts.info).toBe(0);
    });
  });

  describe('filterFindingsBySeverity', () => {
    it('filters findings by minimum severity', () => {
      const filtered = filterFindingsBySeverity(mockFindings, 'high');
      expect(filtered.length).toBe(2);
      expect(filtered.every((f) => ['critical', 'high'].includes(f.severity))).toBe(true);
    });
  });
});

describe('CWE/OWASP Utilities', () => {
  describe('getCWEUrl', () => {
    it('generates correct CWE URL', () => {
      expect(getCWEUrl('CWE-95')).toBe(
        'https://cwe.mitre.org/data/definitions/95.html'
      );
      expect(getCWEUrl('95')).toBe(
        'https://cwe.mitre.org/data/definitions/95.html'
      );
    });
  });

  describe('getOWASPUrl', () => {
    it('generates correct OWASP URL', () => {
      expect(getOWASPUrl('A03:2021')).toBe(
        'https://owasp.org/Top10/A03_2021/'
      );
    });

    it('returns default URL for invalid format', () => {
      expect(getOWASPUrl('invalid')).toBe('https://owasp.org/Top10/');
    });
  });
});

describe('Date Utilities', () => {
  const isoDate = '2024-01-15T12:30:00Z';

  describe('formatDate', () => {
    it('formats ISO date string', () => {
      const result = formatDate(isoDate);
      expect(result).toMatch(/\d{1,2}\/\d{1,2}\/\d{4}|\d{4}-\d{2}-\d{2}/);
    });
  });

  describe('formatDateTime', () => {
    it('formats ISO date string with time', () => {
      const result = formatDateTime(isoDate);
      expect(result).toBeTruthy();
      expect(result.length).toBeGreaterThan(formatDate(isoDate).length);
    });
  });

  describe('getRelativeTime', () => {
    it('returns "just now" for recent times', () => {
      const now = new Date().toISOString();
      expect(getRelativeTime(now)).toBe('just now');
    });

    it('returns minutes for times less than an hour ago', () => {
      const thirtyMinsAgo = new Date(Date.now() - 30 * 60 * 1000).toISOString();
      expect(getRelativeTime(thirtyMinsAgo)).toMatch(/\d+m ago/);
    });

    it('returns hours for times less than a day ago', () => {
      const fiveHoursAgo = new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString();
      expect(getRelativeTime(fiveHoursAgo)).toMatch(/\d+h ago/);
    });

    it('returns days for times less than a week ago', () => {
      const twoDaysAgo = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString();
      expect(getRelativeTime(twoDaysAgo)).toMatch(/\d+d ago/);
    });
  });

  describe('isExpired', () => {
    it('returns true for past dates', () => {
      const pastDate = '2020-01-01T00:00:00Z';
      expect(isExpired(pastDate)).toBe(true);
    });

    it('returns false for future dates', () => {
      const futureDate = new Date(Date.now() + 86400000).toISOString();
      expect(isExpired(futureDate)).toBe(false);
    });
  });

  describe('getTimeUntilExpiration', () => {
    it('returns "Expired" for past dates', () => {
      const pastDate = '2020-01-01T00:00:00Z';
      expect(getTimeUntilExpiration(pastDate)).toBe('Expired');
    });

    it('returns remaining time for future dates', () => {
      const oneHourFromNow = new Date(Date.now() + 60 * 60 * 1000).toISOString();
      // Function rounds to the largest sensible unit (m/h/d), so 1 hour
      // from now is "1h remaining" rather than "60m remaining".
      expect(getTimeUntilExpiration(oneHourFromNow)).toMatch(
        /\d+(m|h|d) remaining/
      );
    });
  });
});

describe('Diff Utilities', () => {
  describe('parseDiff', () => {
    it('parses unified diff format', () => {
      const diff = `--- a/file.py
+++ b/file.py
@@ -1,3 +1,3 @@
 context line
-removed line
+added line
 context line`;

      const parsed = parseDiff(diff);

      expect(parsed.some((l) => l.type === 'header')).toBe(true);
      expect(parsed.some((l) => l.type === 'add')).toBe(true);
      expect(parsed.some((l) => l.type === 'remove')).toBe(true);
      expect(parsed.some((l) => l.type === 'context')).toBe(true);
    });

    it('extracts line numbers', () => {
      const diff = `@@ -5,1 +5,1 @@
-old
+new`;

      const parsed = parseDiff(diff);
      const addedLine = parsed.find((l) => l.type === 'add');
      expect(addedLine?.lineNumber).toBe(5);
    });
  });
});

describe('Validation Utilities', () => {
  describe('isValidFilePath', () => {
    it('returns true for valid paths', () => {
      expect(isValidFilePath('src/app.ts')).toBe(true);
      expect(isValidFilePath('test.py')).toBe(true);
    });

    it('returns false for path traversal', () => {
      expect(isValidFilePath('../etc/passwd')).toBe(false);
      expect(isValidFilePath('src/../../../etc/passwd')).toBe(false);
    });

    it('returns false for absolute paths', () => {
      expect(isValidFilePath('/etc/passwd')).toBe(false);
    });
  });

  describe('isValidApiKey', () => {
    it('returns true for valid API keys', () => {
      expect(isValidApiKey('0123456789abcdef0123456789abcdef')).toBe(true);
      expect(isValidApiKey('ABCDEF0123456789ABCDEF0123456789')).toBe(true);
    });

    it('returns false for invalid API keys', () => {
      expect(isValidApiKey('too-short')).toBe(false);
      expect(isValidApiKey('xyz')).toBe(false);
      expect(isValidApiKey('')).toBe(false);
    });
  });

  describe('isValidJwt', () => {
    it('returns true for valid JWT format', () => {
      expect(isValidJwt('header.payload.signature')).toBe(true);
      expect(isValidJwt('eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiYWRtaW4iOnRydWUsImlhdCI6MTYxOTQ2MTQ0MCwiZXhwIjoxNjE5NDY1MDQwfQ.DqN0aK_J0wXd4MhR-ADN_v8AJFPxA7K8JqLRKn7l6_Y')).toBe(true);
    });

    it('returns false for invalid JWT format', () => {
      expect(isValidJwt('not-a-jwt')).toBe(false);
      expect(isValidJwt('only.two.parts.here.more')).toBe(false);
      expect(isValidJwt('')).toBe(false);
    });
  });
});
