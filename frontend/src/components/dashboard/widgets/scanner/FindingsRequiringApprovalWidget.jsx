/**
 * Findings Requiring Approval Widget (P0)
 *
 * Metric counter with badge showing count of findings
 * awaiting HITL approval, broken down by severity.
 *
 * Per ADR-084: Widget ID 'scanner-findings-requiring-approval'
 *
 * @module components/dashboard/widgets/scanner/FindingsRequiringApprovalWidget
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  HandRaisedIcon,
  ArrowTrendingUpIcon,
} from '@heroicons/react/24/solid';
import { MOCK_FINDINGS_REQUIRING_APPROVAL } from '../../../../services/vulnScannerMockData';
import { SEVERITY_COLORS, WidgetSkeleton, WidgetError } from './ScannerWidgetShared';

/**
 * FindingsRequiringApprovalWidget component
 */
export function FindingsRequiringApprovalWidget({
  refreshInterval = 30000,
  onClick = null,
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
        setData(MOCK_FINDINGS_REQUIRING_APPROVAL);
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
  if (error) return <WidgetError title="Pending Approvals" onRetry={fetchData} className={className} />;

  const CardWrapper = onClick ? 'button' : 'div';

  return (
    <CardWrapper
      onClick={onClick}
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        shadow-card p-5 h-full flex flex-col text-left w-full
        ${onClick ? 'cursor-pointer hover:shadow-card-hover hover:-translate-y-0.5 transition-all duration-250' : ''}
        ${className}
      `}
      role="region"
      aria-label={`${data?.count || 0} findings requiring approval`}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="p-2.5 rounded-lg bg-amber-100 dark:bg-amber-900/30">
          <HandRaisedIcon className="w-5 h-5 text-amber-600 dark:text-amber-400" />
        </div>
        {data?.count > 0 && (
          <span className="px-2.5 py-1 text-xs font-bold bg-amber-500 text-white rounded-full min-w-[24px] text-center">
            {data.count}
          </span>
        )}
      </div>

      {/* Value */}
      <div className="mb-1">
        <span className="text-2xl font-bold text-gray-900 dark:text-gray-50 tracking-tight">
          {data?.count || 0}
        </span>
      </div>

      <h3 className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-0.5">
        Findings Requiring Approval
      </h3>

      {/* Trend */}
      {data?.trend !== undefined && data.trend > 0 && (
        <div className="flex items-center gap-1 text-xs font-medium text-amber-600 dark:text-amber-400 mb-2">
          <ArrowTrendingUpIcon className="w-3.5 h-3.5" />
          <span>+{data.trend} since yesterday</span>
        </div>
      )}

      {/* Severity breakdown */}
      {data?.by_severity && (
        <div className="mt-auto pt-3 border-t border-gray-100 dark:border-gray-700">
          <div className="flex items-center gap-3">
            {Object.entries(data.by_severity).map(([sev, count]) => (
              <div key={sev} className="flex items-center gap-1">
                <span
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: SEVERITY_COLORS[sev]?.hex || '#6B7280' }}
                />
                <span className="text-xs text-gray-500">{sev}:</span>
                <span className="text-xs font-medium text-gray-700 dark:text-gray-300">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </CardWrapper>
  );
}

export default FindingsRequiringApprovalWidget;
