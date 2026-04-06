/**
 * Aura TypeScript SDK - Utilities
 *
 * Helper functions for working with the Aura API.
 */

import type { Severity, ApprovalStatus, PatchStatus, Finding } from '../types';

// ============================================================================
// Severity Utilities
// ============================================================================

/**
 * Severity level ordering (higher = more severe)
 */
export const SEVERITY_ORDER: Record<Severity, number> = {
  critical: 5,
  high: 4,
  medium: 3,
  low: 2,
  info: 1,
};

/**
 * Compare two severities
 * @returns positive if a > b, negative if a < b, 0 if equal
 */
export function compareSeverity(a: Severity, b: Severity): number {
  return SEVERITY_ORDER[a] - SEVERITY_ORDER[b];
}

/**
 * Check if severity meets threshold
 */
export function meetsSeverityThreshold(
  severity: Severity,
  threshold: Severity
): boolean {
  return SEVERITY_ORDER[severity] >= SEVERITY_ORDER[threshold];
}

/**
 * Get severity color for UI display
 */
export function getSeverityColor(severity: Severity): string {
  const colors: Record<Severity, string> = {
    critical: '#DC2626', // red-600
    high: '#EA580C', // orange-600
    medium: '#F59E0B', // amber-500
    low: '#3B82F6', // blue-500
    info: '#10B981', // green-500
  };
  return colors[severity];
}

/**
 * Get severity label for display
 */
export function getSeverityLabel(severity: Severity): string {
  return severity.charAt(0).toUpperCase() + severity.slice(1);
}

// ============================================================================
// Status Utilities
// ============================================================================

/**
 * Check if approval is actionable
 */
export function isApprovalActionable(status: ApprovalStatus): boolean {
  return status === 'pending';
}

/**
 * Check if patch is applicable
 */
export function isPatchApplicable(status: PatchStatus): boolean {
  return status === 'approved' || status === 'ready';
}

/**
 * Get status color for UI display
 */
export function getStatusColor(
  status: ApprovalStatus | PatchStatus
): string {
  const colors: Record<string, string> = {
    pending: '#F59E0B', // amber
    approved: '#10B981', // green
    rejected: '#DC2626', // red
    expired: '#6B7280', // gray
    cancelled: '#6B7280', // gray
    generating: '#3B82F6', // blue
    ready: '#10B981', // green
    applied: '#10B981', // green
    failed: '#DC2626', // red
  };
  return colors[status] || '#6B7280';
}

// ============================================================================
// Finding Utilities
// ============================================================================

/**
 * Group findings by file path
 */
export function groupFindingsByFile(
  findings: Finding[]
): Map<string, Finding[]> {
  const groups = new Map<string, Finding[]>();
  for (const finding of findings) {
    const existing = groups.get(finding.file_path) || [];
    existing.push(finding);
    groups.set(finding.file_path, existing);
  }
  return groups;
}

/**
 * Group findings by severity
 */
export function groupFindingsBySeverity(
  findings: Finding[]
): Map<Severity, Finding[]> {
  const groups = new Map<Severity, Finding[]>();
  for (const finding of findings) {
    const existing = groups.get(finding.severity) || [];
    existing.push(finding);
    groups.set(finding.severity, existing);
  }
  return groups;
}

/**
 * Sort findings by severity (most severe first)
 */
export function sortFindingsBySeverity(findings: Finding[]): Finding[] {
  return [...findings].sort(
    (a, b) => compareSeverity(b.severity, a.severity)
  );
}

/**
 * Count findings by severity
 */
export function countFindingsBySeverity(
  findings: Finding[]
): Record<Severity, number> {
  const counts: Record<Severity, number> = {
    critical: 0,
    high: 0,
    medium: 0,
    low: 0,
    info: 0,
  };
  for (const finding of findings) {
    counts[finding.severity]++;
  }
  return counts;
}

/**
 * Filter findings by minimum severity
 */
export function filterFindingsBySeverity(
  findings: Finding[],
  minSeverity: Severity
): Finding[] {
  return findings.filter((f) =>
    meetsSeverityThreshold(f.severity, minSeverity)
  );
}

// ============================================================================
// CWE/OWASP Utilities
// ============================================================================

/**
 * Generate MITRE CWE URL from CWE ID
 */
export function getCWEUrl(cweId: string): string {
  const id = cweId.replace(/^CWE-/, '');
  return `https://cwe.mitre.org/data/definitions/${id}.html`;
}

/**
 * Generate OWASP URL from category
 */
export function getOWASPUrl(category: string): string {
  // Extract year and number from format like "A03:2021"
  const match = category.match(/A(\d+):(\d+)/);
  if (match) {
    return `https://owasp.org/Top10/A${match[1]}_${match[2]}/`;
  }
  return 'https://owasp.org/Top10/';
}

// ============================================================================
// Date Utilities
// ============================================================================

/**
 * Format ISO date string for display
 */
export function formatDate(isoString: string): string {
  return new Date(isoString).toLocaleDateString();
}

/**
 * Format ISO date string with time
 */
export function formatDateTime(isoString: string): string {
  return new Date(isoString).toLocaleString();
}

/**
 * Get relative time string (e.g., "2 hours ago")
 */
export function getRelativeTime(isoString: string): string {
  const now = new Date();
  const date = new Date(isoString);
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return formatDate(isoString);
}

/**
 * Check if date is expired
 */
export function isExpired(expiresAt: string): boolean {
  return new Date(expiresAt) < new Date();
}

/**
 * Get time until expiration
 */
export function getTimeUntilExpiration(expiresAt: string): string {
  const now = new Date();
  const expiry = new Date(expiresAt);
  const diffMs = expiry.getTime() - now.getTime();

  if (diffMs <= 0) return 'Expired';

  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 60) return `${diffMins}m remaining`;
  if (diffHours < 24) return `${diffHours}h remaining`;
  return `${diffDays}d remaining`;
}

// ============================================================================
// Diff Utilities
// ============================================================================

/**
 * Parse unified diff into structured format
 */
export interface DiffLine {
  type: 'add' | 'remove' | 'context' | 'header';
  content: string;
  lineNumber?: number;
}

/**
 * Parse unified diff string into structured lines
 */
export function parseDiff(diff: string): DiffLine[] {
  const lines = diff.split('\n');
  const result: DiffLine[] = [];

  let oldLine = 0;
  let newLine = 0;

  for (const line of lines) {
    if (line.startsWith('---') || line.startsWith('+++')) {
      result.push({ type: 'header', content: line });
    } else if (line.startsWith('@@')) {
      result.push({ type: 'header', content: line });
      // Parse line numbers from @@ -start,count +start,count @@
      const match = line.match(/@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
      if (match) {
        oldLine = parseInt(match[1], 10);
        newLine = parseInt(match[2], 10);
      }
    } else if (line.startsWith('+')) {
      result.push({ type: 'add', content: line.slice(1), lineNumber: newLine++ });
    } else if (line.startsWith('-')) {
      result.push({ type: 'remove', content: line.slice(1), lineNumber: oldLine++ });
    } else if (line.startsWith(' ')) {
      result.push({ type: 'context', content: line.slice(1), lineNumber: newLine++ });
      oldLine++;
    }
  }

  return result;
}

// ============================================================================
// Validation Utilities
// ============================================================================

/**
 * Validate file path
 */
export function isValidFilePath(path: string): boolean {
  // Basic validation - no path traversal
  return !path.includes('..') && !path.startsWith('/');
}

/**
 * Validate API key format
 */
export function isValidApiKey(key: string): boolean {
  // Aura API keys are 32 character hex strings
  return /^[a-f0-9]{32}$/i.test(key);
}

/**
 * Validate JWT format (basic check)
 */
export function isValidJwt(token: string): boolean {
  const parts = token.split('.');
  return parts.length === 3;
}
