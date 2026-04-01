/**
 * Stage Duration Waterfall Widget (P1)
 *
 * Horizontal stacked bar showing time spent in each pipeline stage.
 *
 * Per ADR-084: Widget ID 'scanner-stage-duration'
 *
 * @module components/dashboard/widgets/scanner/StageDurationWaterfallWidget
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { Bars3BottomLeftIcon } from '@heroicons/react/24/solid';
import { MOCK_STAGE_DURATION } from '../../../../services/vulnScannerMockData';
import { STAGE_LABELS, WidgetSkeleton, WidgetError, WidgetCard, formatDuration } from './ScannerWidgetShared';

const STAGE_COLORS = [
  '#3B82F6', '#10B981', '#F59E0B', '#DC2626', '#8B5CF6', '#EC4899', '#6B7280',
];

/**
 * StageDurationWaterfallWidget component
 */
export function StageDurationWaterfallWidget({
  refreshInterval = 300000,
  className = '',
}) {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hoveredStage, setHoveredStage] = useState(null);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    try {
      await new Promise((r) => setTimeout(r, 200));
      if (mountedRef.current) { setData(MOCK_STAGE_DURATION); setError(null); }
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
  if (error) return <WidgetError title="Stage Duration" onRetry={fetchData} className={className} />;

  return (
    <WidgetCard
      title="Stage Duration Waterfall"
      subtitle={`Total avg: ${formatDuration(data?.total_avg_ms || 0)}`}
      icon={Bars3BottomLeftIcon}
      iconColor="blue"
      onRefresh={fetchData}
      className={className}
    >
      <div className="p-4">
        {/* Stacked horizontal bar */}
        <div className="h-8 flex rounded-lg overflow-hidden mb-4">
          {data?.stages?.map((stage, idx) => (
            <div
              key={stage.name}
              className="relative transition-opacity duration-200 cursor-pointer"
              style={{
                width: `${stage.pct}%`,
                backgroundColor: STAGE_COLORS[idx],
                opacity: hoveredStage !== null && hoveredStage !== idx ? 0.4 : 1,
              }}
              onMouseEnter={() => setHoveredStage(idx)}
              onMouseLeave={() => setHoveredStage(null)}
              role="img"
              aria-label={`${STAGE_LABELS[stage.name]}: ${stage.pct}%`}
            >
              {stage.pct > 8 && (
                <span className="absolute inset-0 flex items-center justify-center text-[10px] font-medium text-white">
                  {stage.pct}%
                </span>
              )}
            </div>
          ))}
        </div>

        {/* Stage breakdown */}
        <div className="space-y-2">
          {data?.stages?.map((stage, idx) => (
            <div
              key={stage.name}
              className={`flex items-center justify-between py-1.5 px-2 -mx-2 rounded transition-colors ${
                hoveredStage === idx ? 'bg-gray-50 dark:bg-gray-800/50' : ''
              }`}
              onMouseEnter={() => setHoveredStage(idx)}
              onMouseLeave={() => setHoveredStage(null)}
            >
              <div className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-sm flex-shrink-0"
                  style={{ backgroundColor: STAGE_COLORS[idx] }}
                />
                <span className="text-xs font-medium text-gray-700 dark:text-gray-300">
                  {STAGE_LABELS[stage.name] || stage.name}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-500">
                  {formatDuration(stage.avg_ms)}
                </span>
                <span className="text-xs font-medium text-gray-400 w-8 text-right">
                  {stage.pct}%
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </WidgetCard>
  );
}

export default StageDurationWaterfallWidget;
