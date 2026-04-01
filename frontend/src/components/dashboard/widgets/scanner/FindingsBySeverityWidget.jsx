/**
 * Findings by Severity Widget (P0)
 *
 * Stacked bar chart showing CRITICAL/HIGH/MEDIUM/LOW/INFO distribution
 * over the last 7 days with summary counters.
 *
 * Per ADR-084: Widget ID 'scanner-findings-by-severity'
 *
 * @module components/dashboard/widgets/scanner/FindingsBySeverityWidget
 */

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { ShieldExclamationIcon } from '@heroicons/react/24/solid';
import { MOCK_FINDINGS_BY_SEVERITY } from '../../../../services/vulnScannerMockData';
import { SEVERITY_COLORS, WidgetSkeleton, WidgetError, WidgetCard } from './ScannerWidgetShared';

const SEVERITY_ORDER = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'];

/**
 * FindingsBySeverityWidget component
 */
export function FindingsBySeverityWidget({
  refreshInterval = 60000,
  className = '',
}) {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hoveredBar, setHoveredBar] = useState(null);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    try {
      // In production, replace with: const data = await getFindingsBySeverity();
      await new Promise((r) => setTimeout(r, 300));
      if (mountedRef.current) {
        setData(MOCK_FINDINGS_BY_SEVERITY);
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

  // Calculate max value for scaling
  const maxValue = useMemo(() => {
    if (!data?.timeSeries) return 100;
    return Math.max(...data.timeSeries.map((d) =>
      SEVERITY_ORDER.reduce((sum, s) => sum + (d[s] || 0), 0)
    ));
  }, [data]);

  if (isLoading) return <WidgetSkeleton className={className} />;
  if (error) return <WidgetError title="Findings by Severity" onRetry={fetchData} className={className} />;

  return (
    <WidgetCard
      title="Findings by Severity"
      subtitle="7-day distribution of scan findings"
      icon={ShieldExclamationIcon}
      iconColor="red"
      onRefresh={fetchData}
      className={className}
    >
      {/* Summary counters */}
      <div className="px-4 py-3 grid grid-cols-5 gap-2 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
        {SEVERITY_ORDER.map((severity) => {
          const config = SEVERITY_COLORS[severity];
          return (
            <div key={severity} className="text-center">
              <p className="text-lg font-bold" style={{ color: config.hex }}>
                {data?.summary[severity] || 0}
              </p>
              <p className="text-[10px] font-medium text-gray-500 uppercase">{severity}</p>
            </div>
          );
        })}
      </div>

      {/* Stacked bar chart */}
      <div className="p-4">
        <div className="flex items-end gap-1.5 h-32">
          {data?.timeSeries?.map((day, idx) => {
            const total = SEVERITY_ORDER.reduce((sum, s) => sum + (day[s] || 0), 0);
            const isHovered = hoveredBar === idx;

            return (
              <div
                key={day.date}
                className="flex-1 flex flex-col-reverse rounded-t overflow-hidden cursor-pointer transition-opacity"
                style={{ height: `${(total / maxValue) * 100}%`, opacity: hoveredBar !== null && !isHovered ? 0.5 : 1 }}
                onMouseEnter={() => setHoveredBar(idx)}
                onMouseLeave={() => setHoveredBar(null)}
                role="img"
                aria-label={`${day.date}: ${total} findings`}
              >
                {SEVERITY_ORDER.map((severity) => {
                  const count = day[severity] || 0;
                  if (count === 0) return null;
                  const pct = (count / total) * 100;
                  return (
                    <div
                      key={severity}
                      style={{ height: `${pct}%`, backgroundColor: SEVERITY_COLORS[severity].hex }}
                      className="min-h-[2px] transition-all duration-200"
                    />
                  );
                })}
              </div>
            );
          })}
        </div>

        {/* X-axis labels */}
        <div className="flex gap-1.5 mt-2">
          {data?.timeSeries?.map((day) => (
            <div key={day.date} className="flex-1 text-center">
              <span className="text-[10px] text-gray-400">
                {new Date(day.date).toLocaleDateString('en', { weekday: 'short' })}
              </span>
            </div>
          ))}
        </div>

        {/* Tooltip */}
        {hoveredBar !== null && data?.timeSeries?.[hoveredBar] && (
          <div className="mt-3 p-2 bg-gray-50 dark:bg-gray-800/50 rounded-lg text-xs">
            <p className="font-medium text-gray-700 dark:text-gray-300 mb-1">
              {new Date(data.timeSeries[hoveredBar].date).toLocaleDateString()}
            </p>
            <div className="flex flex-wrap gap-x-3 gap-y-0.5">
              {SEVERITY_ORDER.map((s) => (
                <span key={s} className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: SEVERITY_COLORS[s].hex }} />
                  <span className="text-gray-500">{s}:</span>
                  <span className="font-medium text-gray-700 dark:text-gray-300">{data.timeSeries[hoveredBar][s] || 0}</span>
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="px-4 py-2 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-center gap-4">
          {SEVERITY_ORDER.map((s) => (
            <div key={s} className="flex items-center gap-1">
              <div className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: SEVERITY_COLORS[s].hex }} />
              <span className="text-[10px] text-gray-500 font-medium">{s}</span>
            </div>
          ))}
        </div>
      </div>
    </WidgetCard>
  );
}

export default FindingsBySeverityWidget;
