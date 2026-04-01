/**
 * Concurrent Scan Utilization Widget (P1)
 *
 * Gauge showing active vs max concurrent scans.
 *
 * Per ADR-084: Widget ID 'scanner-concurrent-utilization'
 *
 * @module components/dashboard/widgets/scanner/ConcurrentUtilizationWidget
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { ServerStackIcon } from '@heroicons/react/24/solid';
import { MOCK_CONCURRENT_UTILIZATION } from '../../../../services/vulnScannerMockData';
import { WidgetSkeleton, WidgetError } from './ScannerWidgetShared';

/**
 * ConcurrentUtilizationWidget component
 */
export function ConcurrentUtilizationWidget({
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
      if (mountedRef.current) { setData(MOCK_CONCURRENT_UTILIZATION); setError(null); }
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
  if (error) return <WidgetError title="Concurrent Utilization" onRetry={fetchData} className={className} />;

  const pct = data?.utilization_pct || 0;
  const color = pct >= 90 ? '#DC2626' : pct >= 70 ? '#F59E0B' : '#10B981';
  const size = 120;
  const strokeWidth = 10;
  const center = size / 2;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (pct / 100) * circumference;

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        shadow-card p-5 h-full flex flex-col items-center justify-center
        ${className}
      `}
      role="meter"
      aria-valuenow={data?.active || 0}
      aria-valuemin={0}
      aria-valuemax={data?.max || 5}
      aria-label={`Concurrent utilization: ${pct}%`}
    >
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="transform -rotate-90">
          <circle cx={center} cy={center} r={radius} fill="none" strokeWidth={strokeWidth} className="stroke-gray-200 dark:stroke-gray-700" />
          <circle cx={center} cy={center} r={radius} fill="none" stroke={color} strokeWidth={strokeWidth}
            strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round" className="transition-all duration-500" />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xl font-bold text-gray-900 dark:text-gray-100">
            {data?.active || 0}/{data?.max || 5}
          </span>
          <span className="text-[10px] text-gray-400">scans</span>
        </div>
      </div>

      <h3 className="mt-3 text-sm font-semibold text-gray-900 dark:text-gray-100">
        Concurrent Utilization
      </h3>
      <p className="text-xs text-gray-500 mt-0.5">{pct}% capacity used</p>

      {data?.queue_depth > 0 && (
        <p className="mt-2 text-xs text-amber-600 dark:text-amber-400 font-medium">
          {data.queue_depth} queued
        </p>
      )}
    </div>
  );
}

export default ConcurrentUtilizationWidget;
