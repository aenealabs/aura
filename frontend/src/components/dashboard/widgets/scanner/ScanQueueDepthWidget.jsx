/**
 * Scan Queue Depth Widget (P1)
 *
 * Simple metric counter showing queued scans awaiting execution.
 *
 * Per ADR-084: Widget ID 'scanner-queue-depth'
 *
 * @module components/dashboard/widgets/scanner/ScanQueueDepthWidget
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  QueueListIcon,
  ArrowTrendingDownIcon,
  ArrowTrendingUpIcon,
  MinusIcon,
} from '@heroicons/react/24/solid';
import { MOCK_SCAN_QUEUE_DEPTH } from '../../../../services/vulnScannerMockData';
import { WidgetSkeleton, WidgetError, formatRelativeTime } from './ScannerWidgetShared';

/**
 * ScanQueueDepthWidget component
 */
export function ScanQueueDepthWidget({
  refreshInterval = 15000,
  className = '',
}) {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    try {
      await new Promise((r) => setTimeout(r, 200));
      if (mountedRef.current) { setData(MOCK_SCAN_QUEUE_DEPTH); setError(null); }
    } catch (err) { if (mountedRef.current) setError(err); }
    finally { if (mountedRef.current) setIsLoading(false); }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchData();
    const interval = setInterval(fetchData, refreshInterval);
    return () => { mountedRef.current = false; clearInterval(interval); };
  }, [fetchData, refreshInterval]);

  if (isLoading) return <WidgetSkeleton className={className} />;
  if (error) return <WidgetError title="Queue Depth" onRetry={fetchData} className={className} />;

  const trend = data?.trend || 0;
  const trendDown = trend < 0;

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        shadow-card p-5 h-full flex flex-col
        ${className}
      `}
      role="region"
      aria-label={`Scan queue depth: ${data?.depth || 0}`}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="p-2.5 rounded-lg bg-gray-100 dark:bg-gray-800">
          <QueueListIcon className="w-5 h-5 text-gray-600 dark:text-gray-400" />
        </div>
        {trend !== 0 && (
          <span className={`flex items-center gap-1 text-sm font-medium ${
            trendDown ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
          }`}>
            {trendDown ? <ArrowTrendingDownIcon className="w-4 h-4" /> : <ArrowTrendingUpIcon className="w-4 h-4" />}
            {Math.abs(trend)}
          </span>
        )}
        {trend === 0 && (
          <span className="flex items-center gap-1 text-sm font-medium text-gray-500">
            <MinusIcon className="w-4 h-4" />
            0
          </span>
        )}
      </div>

      <div className="mb-1">
        <span className="text-2xl font-bold text-gray-900 dark:text-gray-50 tracking-tight">
          {data?.depth || 0}
        </span>
      </div>

      <h3 className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-0.5">
        Scan Queue Depth
      </h3>
      <p className="text-xs text-gray-400 dark:text-gray-500">
        Scans waiting to execute
      </p>

      {data?.oldest_queued_at && data.depth > 0 && (
        <p className="mt-auto pt-3 text-xs text-gray-400 border-t border-gray-100 dark:border-gray-700">
          Oldest queued {formatRelativeTime(data.oldest_queued_at)}
        </p>
      )}
    </div>
  );
}

export default ScanQueueDepthWidget;
