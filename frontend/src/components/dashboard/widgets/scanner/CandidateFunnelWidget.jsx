/**
 * Candidate Filter Funnel Widget (P2)
 *
 * Funnel chart: Files > Code Units > Candidates > Findings
 *
 * Per ADR-084: Widget ID 'scanner-candidate-funnel'
 *
 * @module components/dashboard/widgets/scanner/CandidateFunnelWidget
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { FunnelIcon } from '@heroicons/react/24/solid';
import { MOCK_CANDIDATE_FUNNEL } from '../../../../services/vulnScannerMockData';
import { WidgetSkeleton, WidgetError, WidgetCard, formatNumber } from './ScannerWidgetShared';

const FUNNEL_COLORS = ['#3B82F6', '#8B5CF6', '#F59E0B', '#DC2626'];

/**
 * CandidateFunnelWidget component
 */
export function CandidateFunnelWidget({
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
      if (mountedRef.current) { setData(MOCK_CANDIDATE_FUNNEL); setError(null); }
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
  if (error) return <WidgetError title="Candidate Funnel" onRetry={fetchData} className={className} />;

  const maxCount = data?.stages?.[0]?.count || 1;

  return (
    <WidgetCard
      title="Candidate Filter Funnel"
      subtitle="Reduction from files to confirmed findings"
      icon={FunnelIcon}
      iconColor="blue"
      onRefresh={fetchData}
      className={className}
    >
      <div className="p-4 space-y-3">
        {data?.stages?.map((stage, idx) => {
          const widthPct = Math.max((stage.count / maxCount) * 100, 8);
          const conversionRate = idx > 0
            ? ((stage.count / data.stages[idx - 1].count) * 100).toFixed(1)
            : null;

          return (
            <div key={stage.name}>
              {/* Conversion arrow */}
              {conversionRate !== null && (
                <div className="flex items-center justify-center mb-1">
                  <svg className="w-3 h-3 text-gray-300" viewBox="0 0 12 12" fill="currentColor">
                    <path d="M6 10L2 5h8L6 10z" />
                  </svg>
                  <span className="text-[10px] text-gray-400 ml-1">{conversionRate}%</span>
                </div>
              )}

              {/* Funnel bar */}
              <div className="flex items-center gap-3">
                <div className="flex-1">
                  <div
                    className="h-8 rounded-lg flex items-center px-3 transition-all duration-500 mx-auto"
                    style={{
                      width: `${widthPct}%`,
                      backgroundColor: FUNNEL_COLORS[idx],
                    }}
                  >
                    <span className="text-xs font-bold text-white truncate">
                      {formatNumber(stage.count)}
                    </span>
                  </div>
                </div>
              </div>
              <p className="text-[10px] text-gray-500 text-center mt-0.5 font-medium">
                {stage.name}
              </p>
            </div>
          );
        })}
      </div>
    </WidgetCard>
  );
}

export default CandidateFunnelWidget;
