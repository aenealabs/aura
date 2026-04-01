/**
 * Scan Detail Page (P0)
 *
 * Full-page view for a single vulnerability scan showing:
 * - Scan metadata
 * - 7-segment pipeline progress bar
 * - Summary counters
 * - Findings table (sortable/filterable)
 * - LLM usage
 * - Actions (cancel, re-run, download SARIF)
 *
 * Per ADR-084
 *
 * @module components/scanner/ScanDetailPage
 */

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
  ArrowPathIcon,
  StopCircleIcon,
  ArrowDownTrayIcon,
  PlayCircleIcon,
  DocumentTextIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  FunnelIcon,
  ChevronUpDownIcon,
  MagnifyingGlassCircleIcon,
} from '@heroicons/react/24/solid';
import { MOCK_SCAN_DETAIL } from '../../services/vulnScannerMockData';
import { launchScan, downloadSARIF, cancelScan } from '../../services/vulnScannerApi';
import {
  SEVERITY_COLORS,
  STAGE_LABELS,
  STAGE_STATUS_COLORS,
  SeverityBadge,
  ConfidenceBadge,
  VerificationBadge,
  formatDuration,
  formatRelativeTime,
  formatNumber,
} from '../dashboard/widgets/scanner/ScannerWidgetShared';

const STATUS_CONFIG = {
  completed: { icon: CheckCircleIcon, color: 'text-green-500', bg: 'bg-green-100 dark:bg-green-900/30', label: 'Completed' },
  running: { icon: ClockIcon, color: 'text-blue-500', bg: 'bg-blue-100 dark:bg-blue-900/30', label: 'Running' },
  failed: { icon: XCircleIcon, color: 'text-red-500', bg: 'bg-red-100 dark:bg-red-900/30', label: 'Failed' },
  cancelled: { icon: StopCircleIcon, color: 'text-gray-500', bg: 'bg-gray-100 dark:bg-gray-800', label: 'Cancelled' },
  queued: { icon: ClockIcon, color: 'text-amber-500', bg: 'bg-amber-100 dark:bg-amber-900/30', label: 'Queued' },
};

/**
 * Pipeline progress bar (full-width)
 */
function PipelineProgress({ stages }) {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-6">
      <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">Pipeline Progress</h2>
      <div className="flex gap-2">
        {stages?.map((stage) => {
          const statusColor = STAGE_STATUS_COLORS[stage.status] || STAGE_STATUS_COLORS.pending;
          const isComplete = stage.status === 'complete';
          const isRunning = stage.status === 'running';
          const progressPct = stage.items_total > 0 ? Math.round((stage.items_processed / stage.items_total) * 100) : 0;

          return (
            <div key={stage.name} className="flex-1">
              <div className={`h-3 rounded-full overflow-hidden ${isComplete ? '' : 'bg-gray-200 dark:bg-gray-700'}`}>
                <div className={`h-full rounded-full transition-all duration-500 ${statusColor}`}
                  style={{ width: isComplete ? '100%' : isRunning ? `${progressPct}%` : '0%' }} />
              </div>
              <div className="mt-2 text-center">
                <p className={`text-xs font-medium ${
                  isComplete ? 'text-green-600 dark:text-green-400' : isRunning ? 'text-blue-600 dark:text-blue-400' : 'text-gray-400'
                }`}>
                  {STAGE_LABELS[stage.name]}
                </p>
                <p className="text-[10px] text-gray-400 mt-0.5">
                  {stage.items_processed}/{stage.items_total}
                </p>
                {stage.duration_ms > 0 && (
                  <p className="text-[10px] text-gray-400">{formatDuration(stage.duration_ms)}</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Summary counter card
 */
function SummaryCard({ label, value, icon: Icon, color = 'blue' }) {
  const colorMap = {
    blue: 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400',
    green: 'bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400',
    amber: 'bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400',
    red: 'bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400',
  };

  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4">
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-lg ${colorMap[color]}`}>
          <Icon className="w-5 h-5" />
        </div>
        <div>
          <p className="text-xl font-bold text-gray-900 dark:text-gray-100">{typeof value === 'number' ? value.toLocaleString() : value}</p>
          <p className="text-xs text-gray-500">{label}</p>
        </div>
      </div>
    </div>
  );
}

/**
 * ScanDetailPage component
 */
export function ScanDetailPage({
  scanId = 'scan-a1b2c3d4',
  onBack = null,
  onFindingClick = null,
}) {
  const [scan, setScan] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [sortField, setSortField] = useState('severity');
  const [sortOrder, setSortOrder] = useState('asc');
  const [severityFilter, setSeverityFilter] = useState('all');
  const [actionLoading, setActionLoading] = useState(null);
  const mountedRef = useRef(true);

  const fetchScan = useCallback(async () => {
    try {
      await new Promise((r) => setTimeout(r, 300));
      if (mountedRef.current) {
        setScan(MOCK_SCAN_DETAIL);
      }
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, [scanId]);

  useEffect(() => {
    mountedRef.current = true;
    fetchScan();
    return () => { mountedRef.current = false; };
  }, [fetchScan]);

  const handleRerun = useCallback(async () => {
    if (!scan) return;
    setActionLoading('rerun');
    try {
      await launchScan({
        repository_url: scan.repository,
        branch: scan.branch,
        depth: scan.depth,
        autonomy_level: scan.autonomy_level,
      });
      // Refresh after re-launch
      fetchScan();
    } catch {
      // API errors handled by apiClient
    } finally {
      if (mountedRef.current) setActionLoading(null);
    }
  }, [scan, fetchScan]);

  const handleDownloadSARIF = useCallback(async () => {
    if (!scan) return;
    setActionLoading('sarif');
    try {
      const blob = await downloadSARIF(scan.scan_id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${scan.scan_id}.sarif`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      // API errors handled by apiClient
    } finally {
      if (mountedRef.current) setActionLoading(null);
    }
  }, [scan]);

  const handleCancel = useCallback(async () => {
    if (!scan) return;
    setActionLoading('cancel');
    try {
      await cancelScan(scan.scan_id);
      fetchScan();
    } catch {
      // API errors handled by apiClient
    } finally {
      if (mountedRef.current) setActionLoading(null);
    }
  }, [scan, fetchScan]);

  // Sort and filter findings
  const filteredFindings = useMemo(() => {
    if (!scan?.findings) return [];
    const severityOrder = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3, INFO: 4 };
    let findings = [...scan.findings];

    if (severityFilter !== 'all') {
      findings = findings.filter((f) => f.severity === severityFilter);
    }

    findings.sort((a, b) => {
      let cmp = 0;
      if (sortField === 'severity') {
        cmp = severityOrder[a.severity] - severityOrder[b.severity];
      } else if (sortField === 'confidence') {
        cmp = (b.confidence || 0) - (a.confidence || 0);
      } else if (sortField === 'cwe') {
        cmp = (a.cwe_id || '').localeCompare(b.cwe_id || '');
      }
      return sortOrder === 'desc' ? -cmp : cmp;
    });

    return findings;
  }, [scan, sortField, sortOrder, severityFilter]);

  const toggleSort = (field) => {
    if (sortField === field) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortOrder('asc');
    }
  };

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-4 p-6 max-w-7xl mx-auto">
        <div className="h-8 w-48 bg-surface-200 dark:bg-surface-700 rounded" />
        <div className="h-64 bg-surface-200 dark:bg-surface-700 rounded-xl" />
        <div className="grid grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => <div key={i} className="h-20 bg-surface-200 dark:bg-surface-700 rounded-xl" />)}
        </div>
      </div>
    );
  }

  if (!scan) {
    return (
      <div className="flex items-center justify-center min-h-96">
        <p className="text-gray-500">Scan not found</p>
      </div>
    );
  }

  const statusConfig = STATUS_CONFIG[scan.status] || STATUS_CONFIG.completed;
  const StatusIcon = statusConfig.icon;

  return (
    <div className="min-h-screen bg-surface-50 dark:bg-surface-900">
      {/* Page Header */}
      <header className="p-6 bg-white dark:bg-surface-800 border-b border-surface-200 dark:border-surface-700">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-aura-100 dark:bg-aura-900/30 rounded-lg">
              <MagnifyingGlassCircleIcon className="w-6 h-6 text-aura-600 dark:text-aura-400" />
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
                  Vulnerability Scanner
                </h1>
                <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${statusConfig.bg} ${statusConfig.color}`}>
                  <StatusIcon className="w-3.5 h-3.5" />
                  {statusConfig.label}
                </div>
              </div>
              <p className="text-surface-500 dark:text-surface-400">
                {scan.repository?.split('/').pop()} &middot; <span className="font-mono text-xs">{scan.scan_id}</span>
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3 flex-shrink-0">
            <button
              onClick={fetchScan}
              className="p-2 rounded-lg text-surface-500 hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
              aria-label="Refresh"
            >
              <ArrowPathIcon className="w-5 h-5" />
            </button>
            {scan.status === 'running' && (
              <button
                onClick={handleCancel}
                disabled={actionLoading === 'cancel'}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-critical-600 bg-critical-50 hover:bg-critical-100 dark:bg-critical-900/20 dark:hover:bg-critical-900/30 rounded-lg transition-colors disabled:opacity-50"
              >
                <StopCircleIcon className="w-4 h-4" />
                {actionLoading === 'cancel' ? 'Cancelling...' : 'Cancel'}
              </button>
            )}
            <button
              onClick={handleRerun}
              disabled={actionLoading === 'rerun'}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-aura-600 bg-aura-50 hover:bg-aura-100 dark:bg-aura-900/20 dark:hover:bg-aura-900/30 rounded-lg transition-colors disabled:opacity-50"
            >
              <PlayCircleIcon className="w-4 h-4" />
              {actionLoading === 'rerun' ? 'Launching...' : 'Re-run'}
            </button>
            <button
              onClick={handleDownloadSARIF}
              disabled={actionLoading === 'sarif'}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-surface-700 bg-surface-100 hover:bg-surface-200 dark:bg-surface-700 dark:hover:bg-surface-600 dark:text-surface-300 rounded-lg transition-colors disabled:opacity-50"
            >
              <ArrowDownTrayIcon className="w-4 h-4" />
              {actionLoading === 'sarif' ? 'Downloading...' : 'SARIF'}
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto p-6 space-y-6">
      {/* Scan Metadata */}
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-6">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">Scan Metadata</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Repository', value: scan.repository?.split('/').pop() || scan.repository },
            { label: 'Branch', value: scan.branch },
            { label: 'Commit', value: scan.commit_sha?.slice(0, 12), mono: true },
            { label: 'Depth', value: scan.depth },
            { label: 'Autonomy', value: scan.autonomy_level?.replace(/_/g, ' ') },
            { label: 'Requested By', value: scan.requested_by },
            { label: 'Started', value: scan.started_at ? new Date(scan.started_at).toLocaleString() : 'N/A' },
            { label: 'Duration', value: scan.started_at && scan.completed_at ? formatDuration(new Date(scan.completed_at) - new Date(scan.started_at)) : 'In progress' },
          ].map((item) => (
            <div key={item.label}>
              <p className="text-[10px] font-medium text-gray-400 uppercase mb-0.5">{item.label}</p>
              <p className={`text-sm text-gray-900 dark:text-gray-100 ${item.mono ? 'font-mono' : ''} truncate`}>{item.value}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Pipeline Progress */}
      <PipelineProgress stages={scan.pipeline} />

      {/* Summary Counters */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <SummaryCard label="Files Discovered" value={scan.files_discovered} icon={DocumentTextIcon} color="blue" />
        <SummaryCard label="Code Units Extracted" value={scan.code_units_extracted} icon={FunnelIcon} color="amber" />
        <SummaryCard label="Candidates Identified" value={scan.candidates_identified} icon={FunnelIcon} color="amber" />
        <SummaryCard label="Findings" value={scan.findings_count} icon={XCircleIcon} color="red" />
      </div>

      {/* LLM Usage */}
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-6">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">LLM Usage</h2>
        <div className="flex items-center gap-8">
          <div>
            <p className="text-[10px] font-medium text-gray-400 uppercase mb-0.5">Tokens Consumed</p>
            <p className="text-lg font-bold text-gray-900 dark:text-gray-100">{formatNumber(scan.llm_tokens_consumed)}</p>
          </div>
          <div>
            <p className="text-[10px] font-medium text-gray-400 uppercase mb-0.5">Cost</p>
            <p className="text-lg font-bold text-gray-900 dark:text-gray-100">${scan.llm_cost_usd?.toFixed(2)}</p>
          </div>
        </div>
      </div>

      {/* Findings Table */}
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 overflow-hidden">
        <div className="p-4 border-b border-surface-200 dark:border-surface-700 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
            Findings ({filteredFindings.length})
          </h2>
          <div className="flex items-center gap-2">
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="text-xs px-2 py-1 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
              aria-label="Filter by severity"
            >
              <option value="all">All Severities</option>
              {['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'].map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-gray-50 dark:bg-gray-800/50">
                <th className="px-4 py-3 text-[10px] font-medium text-gray-500 uppercase">Title</th>
                <th className="px-4 py-3 text-[10px] font-medium text-gray-500 uppercase cursor-pointer" onClick={() => toggleSort('severity')}>
                  <span className="flex items-center gap-1">Severity <ChevronUpDownIcon className="w-3 h-3" /></span>
                </th>
                <th className="px-4 py-3 text-[10px] font-medium text-gray-500 uppercase cursor-pointer" onClick={() => toggleSort('confidence')}>
                  <span className="flex items-center gap-1">Confidence <ChevronUpDownIcon className="w-3 h-3" /></span>
                </th>
                <th className="px-4 py-3 text-[10px] font-medium text-gray-500 uppercase cursor-pointer" onClick={() => toggleSort('cwe')}>
                  <span className="flex items-center gap-1">CWE <ChevronUpDownIcon className="w-3 h-3" /></span>
                </th>
                <th className="px-4 py-3 text-[10px] font-medium text-gray-500 uppercase">File</th>
                <th className="px-4 py-3 text-[10px] font-medium text-gray-500 uppercase">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
              {filteredFindings.map((finding) => (
                <tr
                  key={finding.finding_id}
                  onClick={() => onFindingClick?.(finding)}
                  className="hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3">
                    <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate max-w-xs">
                      {finding.title}
                    </p>
                  </td>
                  <td className="px-4 py-3"><SeverityBadge severity={finding.severity} /></td>
                  <td className="px-4 py-3"><ConfidenceBadge confidence={finding.confidence} /></td>
                  <td className="px-4 py-3">
                    <span className="text-xs font-mono text-purple-600 dark:text-purple-400">{finding.cwe_id}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-xs text-gray-500 font-mono truncate block max-w-[180px]">
                      {finding.file_path}:{finding.start_line}
                    </span>
                  </td>
                  <td className="px-4 py-3"><VerificationBadge status={finding.verification_status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {filteredFindings.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            <p className="text-sm">No findings match your filters</p>
          </div>
        )}
      </div>
      </div>
    </div>
  );
}

export default ScanDetailPage;
