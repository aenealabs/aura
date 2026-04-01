/**
 * Active Scans Widget (P0)
 *
 * Metric counter showing currently running scans with status pills
 * for each scan's current pipeline stage.
 *
 * Per ADR-084: Widget ID 'scanner-active-scans'
 *
 * @module components/dashboard/widgets/scanner/ActiveScansWidget
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { PlayCircleIcon } from '@heroicons/react/24/solid';
import { MOCK_ACTIVE_SCANS } from '../../../../services/vulnScannerMockData';
import { STAGE_LABELS, STAGE_STATUS_COLORS, WidgetSkeleton, WidgetError, formatRelativeTime } from './ScannerWidgetShared';

/**
 * Pipeline progress mini bar
 */
function MiniPipelineBar({ stageIndex }) {
  const totalStages = 7;
  return (
    <div className="flex gap-0.5">
      {Array.from({ length: totalStages }, (_, i) => (
        <div
          key={i}
          className={`h-1.5 flex-1 rounded-full ${
            i < stageIndex
              ? 'bg-green-500'
              : i === stageIndex
                ? 'bg-blue-500 animate-pulse'
                : 'bg-gray-200 dark:bg-gray-700'
          }`}
        />
      ))}
    </div>
  );
}

/**
 * ActiveScansWidget component
 */
export function ActiveScansWidget({
  refreshInterval = 15000,
  onScanClick = null,
  className = '',
}) {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    try {
      await new Promise((r) => setTimeout(r, 200));
      if (mountedRef.current) {
        setData(MOCK_ACTIVE_SCANS);
        setError(null);
      }
    } catch (err) {
      if (mountedRef.current) setError(err);
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchData();
    const interval = setInterval(fetchData, refreshInterval);
    return () => { mountedRef.current = false; clearInterval(interval); };
  }, [fetchData, refreshInterval]);

  if (isLoading) return <WidgetSkeleton className={className} />;
  if (error) return <WidgetError title="Active Scans" onRetry={fetchData} className={className} />;

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        shadow-card p-5 h-full flex flex-col
        ${className}
      `}
      role="region"
      aria-label="Active Scans"
    >
      {/* Metric */}
      <div className="flex items-center justify-between mb-3">
        <div className="p-2.5 rounded-lg bg-blue-100 dark:bg-blue-900/30">
          <PlayCircleIcon className="w-5 h-5 text-blue-600 dark:text-blue-400" />
        </div>
        {data?.count > 0 && (
          <span className="px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 rounded-full animate-pulse">
            Running
          </span>
        )}
      </div>

      <div className="mb-1">
        <span className="text-2xl font-bold text-gray-900 dark:text-gray-50 tracking-tight">
          {data?.count || 0}
        </span>
      </div>

      <h3 className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-0.5">
        Active Scans
      </h3>
      <p className="text-xs text-gray-400 dark:text-gray-500">
        Currently in progress
      </p>

      {/* Scan list */}
      {data?.scans?.length > 0 && (
        <div className="mt-4 space-y-3 flex-1">
          {data.scans.map((scan) => (
            <button
              key={scan.scan_id}
              onClick={() => onScanClick?.(scan)}
              className="w-full text-left p-2.5 rounded-lg bg-gray-50 dark:bg-gray-800/50 hover:bg-gray-100 dark:hover:bg-gray-700/50 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-medium text-gray-900 dark:text-gray-100 truncate">
                  {scan.repository}
                </span>
                <span className="text-[10px] text-gray-400 flex-shrink-0 ml-2">
                  {formatRelativeTime(scan.started_at)}
                </span>
              </div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium">
                  {STAGE_LABELS[scan.current_stage] || scan.current_stage}
                </span>
                <span className="text-[10px] text-gray-500 font-medium">
                  {scan.progress_pct}%
                </span>
              </div>
              <MiniPipelineBar stageIndex={scan.stage_index} />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default ActiveScansWidget;
