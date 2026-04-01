/**
 * Scan Pipeline Progress Widget (P0)
 *
 * 7-segment progress bar per active scan showing stage status,
 * items processed/total, and duration.
 *
 * Per ADR-084: Widget ID 'scanner-pipeline-progress'
 *
 * @module components/dashboard/widgets/scanner/ScanPipelineProgressWidget
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { QueueListIcon, CheckCircleIcon, ClockIcon } from '@heroicons/react/24/solid';
import { MOCK_PIPELINE_PROGRESS } from '../../../../services/vulnScannerMockData';
import { STAGE_LABELS, STAGE_STATUS_COLORS, WidgetSkeleton, WidgetError, WidgetCard, formatDuration } from './ScannerWidgetShared';

/**
 * Stage segment
 */
function StageSegment({ stage, isLast }) {
  const statusColor = STAGE_STATUS_COLORS[stage.status] || STAGE_STATUS_COLORS.pending;
  const isComplete = stage.status === 'complete';
  const isRunning = stage.status === 'running';
  const progressPct = stage.items_total > 0
    ? Math.round((stage.items_processed / stage.items_total) * 100)
    : 0;

  return (
    <div className="flex-1 min-w-0">
      {/* Progress bar segment */}
      <div className={`h-2.5 rounded-full relative overflow-hidden ${
        isComplete ? '' : 'bg-gray-200 dark:bg-gray-700'
      }`}>
        <div
          className={`h-full rounded-full transition-all duration-500 ${statusColor}`}
          style={{ width: isComplete ? '100%' : isRunning ? `${progressPct}%` : '0%' }}
        />
      </div>

      {/* Stage label */}
      <div className="mt-1.5 text-center">
        <p className={`text-[9px] font-medium leading-tight ${
          isComplete
            ? 'text-green-600 dark:text-green-400'
            : isRunning
              ? 'text-blue-600 dark:text-blue-400'
              : 'text-gray-400 dark:text-gray-500'
        }`}>
          {STAGE_LABELS[stage.name] || stage.name}
        </p>
        {(isComplete || isRunning) && (
          <p className="text-[8px] text-gray-400 mt-0.5">
            {stage.items_processed}/{stage.items_total}
          </p>
        )}
        {stage.duration_ms > 0 && (
          <p className="text-[8px] text-gray-400">
            {formatDuration(stage.duration_ms)}
          </p>
        )}
      </div>
    </div>
  );
}

/**
 * ScanPipelineProgressWidget component
 */
export function ScanPipelineProgressWidget({
  scanId = null,
  refreshInterval = 5000,
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
        setData(MOCK_PIPELINE_PROGRESS);
        setError(null);
      }
    } catch (err) {
      if (mountedRef.current) setError(err);
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, [scanId]);

  useEffect(() => {
    mountedRef.current = true;
    fetchData();
    const interval = setInterval(fetchData, refreshInterval);
    return () => { mountedRef.current = false; clearInterval(interval); };
  }, [fetchData, refreshInterval]);

  if (isLoading) return <WidgetSkeleton className={className} />;
  if (error) return <WidgetError title="Pipeline Progress" onRetry={fetchData} className={className} />;

  const completedStages = data?.stages?.filter((s) => s.status === 'complete').length || 0;
  const currentStage = data?.stages?.find((s) => s.status === 'running');
  const totalStages = data?.stages?.length || 7;

  return (
    <WidgetCard
      title="Scan Pipeline"
      subtitle={`Scan ${data?.scan_id || 'N/A'}`}
      icon={QueueListIcon}
      iconColor="blue"
      onRefresh={fetchData}
      badge={
        <span className="text-xs font-medium text-gray-500">
          {completedStages}/{totalStages} stages
        </span>
      }
      className={className}
    >
      <div className="p-4">
        {/* Pipeline progress bar */}
        <div className="flex gap-1">
          {data?.stages?.map((stage, idx) => (
            <StageSegment
              key={stage.name}
              stage={stage}
              isLast={idx === totalStages - 1}
            />
          ))}
        </div>

        {/* Current stage detail */}
        {currentStage && (
          <div className="mt-4 p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-100 dark:border-blue-800">
            <div className="flex items-center gap-2 mb-1">
              <ClockIcon className="w-4 h-4 text-blue-500 animate-pulse" />
              <span className="text-sm font-medium text-blue-700 dark:text-blue-300">
                {STAGE_LABELS[currentStage.name]}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs text-blue-600 dark:text-blue-400">
              <span>{currentStage.items_processed} / {currentStage.items_total} items</span>
              <span>{formatDuration(currentStage.duration_ms)}</span>
            </div>
            {currentStage.items_total > 0 && (
              <div className="mt-2 h-1.5 bg-blue-200 dark:bg-blue-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded-full transition-all duration-300"
                  style={{ width: `${(currentStage.items_processed / currentStage.items_total) * 100}%` }}
                />
              </div>
            )}
          </div>
        )}

        {/* Completed summary */}
        {completedStages === totalStages && (
          <div className="mt-4 p-3 rounded-lg bg-green-50 dark:bg-green-900/20 border border-green-100 dark:border-green-800 flex items-center gap-2">
            <CheckCircleIcon className="w-5 h-5 text-green-500" />
            <span className="text-sm font-medium text-green-700 dark:text-green-300">
              All stages complete
            </span>
          </div>
        )}
      </div>
    </WidgetCard>
  );
}

export default ScanPipelineProgressWidget;
