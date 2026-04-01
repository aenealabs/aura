/**
 * Findings by CWE Widget (P1)
 *
 * Horizontal bar chart sorted by finding count per CWE category.
 *
 * Per ADR-084: Widget ID 'scanner-findings-by-cwe'
 *
 * @module components/dashboard/widgets/scanner/FindingsByCWEWidget
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { TagIcon } from '@heroicons/react/24/solid';
import { MOCK_FINDINGS_BY_CWE } from '../../../../services/vulnScannerMockData';
import { WidgetSkeleton, WidgetError, WidgetCard } from './ScannerWidgetShared';

/**
 * FindingsByCWEWidget component
 */
export function FindingsByCWEWidget({
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
      if (mountedRef.current) { setData(MOCK_FINDINGS_BY_CWE); setError(null); }
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
  if (error) return <WidgetError title="Findings by CWE" onRetry={fetchData} className={className} />;

  const maxCount = Math.max(...(data?.categories?.map((c) => c.count) || [1]));

  return (
    <WidgetCard
      title="Findings by CWE"
      subtitle="Vulnerability categories ranked by count"
      icon={TagIcon}
      iconColor="amber"
      onRefresh={fetchData}
      className={className}
    >
      <div className="p-4 space-y-2.5">
        {data?.categories?.map((cat) => (
          <div key={cat.cwe_id} className="group">
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 font-mono flex-shrink-0">
                  {cat.cwe_id}
                </span>
                <span className="text-xs text-gray-600 dark:text-gray-400 truncate">
                  {cat.name}
                </span>
              </div>
              <span className="text-xs font-semibold text-gray-900 dark:text-gray-100 flex-shrink-0 ml-2">
                {cat.count}
              </span>
            </div>
            <div className="h-2 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full bg-blue-500 transition-all duration-500"
                style={{ width: `${(cat.count / maxCount) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </WidgetCard>
  );
}

export default FindingsByCWEWidget;
