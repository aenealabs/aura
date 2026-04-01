/**
 * Cleanup Activity Widget (P2)
 *
 * Bar chart showing cleanup operations over time.
 *
 * Per ADR-084: Widget ID 'scanner-cleanup-activity'
 *
 * @module components/dashboard/widgets/scanner/CleanupActivityWidget
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { TrashIcon } from '@heroicons/react/24/solid';
import { MOCK_CLEANUP_ACTIVITY } from '../../../../services/vulnScannerMockData';
import { WidgetSkeleton, WidgetError, WidgetCard } from './ScannerWidgetShared';

const CLEANUP_COLORS = {
  temp_files_cleaned: { hex: '#3B82F6', label: 'Temp Files' },
  caches_cleared: { hex: '#10B981', label: 'Caches' },
  artifacts_archived: { hex: '#F59E0B', label: 'Artifacts' },
};

/**
 * CleanupActivityWidget component
 */
export function CleanupActivityWidget({
  refreshInterval = 300000,
  className = '',
}) {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    try {
      await new Promise((r) => setTimeout(r, 200));
      if (mountedRef.current) { setData(MOCK_CLEANUP_ACTIVITY); setError(null); }
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
  if (error) return <WidgetError title="Cleanup Activity" onRetry={fetchData} className={className} />;

  const keys = Object.keys(CLEANUP_COLORS);
  const maxVal = Math.max(...(data?.data?.map((d) => keys.reduce((s, k) => s + (d[k] || 0), 0)) || [1]));

  return (
    <WidgetCard
      title="Cleanup Activity"
      subtitle="Post-scan cleanup operations"
      icon={TrashIcon}
      iconColor="gray"
      onRefresh={fetchData}
      className={className}
    >
      <div className="p-4">
        <div className="flex items-end gap-1.5 h-28">
          {data?.data?.map((day) => {
            const total = keys.reduce((s, k) => s + (day[k] || 0), 0);
            return (
              <div key={day.date} className="flex-1 flex flex-col-reverse rounded-t overflow-hidden" style={{ height: `${(total / maxVal) * 100}%` }}>
                {keys.map((key) => {
                  const count = day[key] || 0;
                  if (count === 0) return null;
                  return (
                    <div key={key} style={{ height: `${(count / total) * 100}%`, backgroundColor: CLEANUP_COLORS[key].hex }} className="min-h-[1px]" />
                  );
                })}
              </div>
            );
          })}
        </div>
        <div className="flex gap-1.5 mt-2">
          {data?.data?.map((day) => (
            <div key={day.date} className="flex-1 text-center">
              <span className="text-[9px] text-gray-400">{new Date(day.date).toLocaleDateString('en', { weekday: 'narrow' })}</span>
            </div>
          ))}
        </div>

        <div className="mt-3 flex items-center justify-center gap-4">
          {keys.map((key) => (
            <div key={key} className="flex items-center gap-1">
              <div className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: CLEANUP_COLORS[key].hex }} />
              <span className="text-[10px] text-gray-500">{CLEANUP_COLORS[key].label}</span>
            </div>
          ))}
        </div>
      </div>
    </WidgetCard>
  );
}

export default CleanupActivityWidget;
