/**
 * Critical Findings Trend 30d Widget (P1)
 *
 * Line chart showing daily critical finding counts over 30 days.
 *
 * Per ADR-084: Widget ID 'scanner-critical-findings-trend'
 *
 * @module components/dashboard/widgets/scanner/CriticalFindingsTrendWidget
 */

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { FireIcon } from '@heroicons/react/24/solid';
import { MOCK_CRITICAL_FINDINGS_TREND } from '../../../../services/vulnScannerMockData';
import { WidgetSkeleton, WidgetError, WidgetCard } from './ScannerWidgetShared';

/**
 * CriticalFindingsTrendWidget component
 */
export function CriticalFindingsTrendWidget({
  refreshInterval = 300000,
  className = '',
}) {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hoveredIdx, setHoveredIdx] = useState(null);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    try {
      await new Promise((r) => setTimeout(r, 200));
      if (mountedRef.current) { setData(MOCK_CRITICAL_FINDINGS_TREND); setError(null); }
    } catch (err) { if (mountedRef.current) setError(err); }
    finally { if (mountedRef.current) setIsLoading(false); }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchData();
    const interval = setInterval(fetchData, refreshInterval);
    return () => { mountedRef.current = false; clearInterval(interval); };
  }, [fetchData, refreshInterval]);

  const chartConfig = useMemo(() => {
    if (!data?.data?.length) return null;
    const padding = { top: 12, right: 12, bottom: 28, left: 32 };
    const width = 400;
    const height = 140;
    const innerW = width - padding.left - padding.right;
    const innerH = height - padding.top - padding.bottom;
    const maxVal = Math.max(...data.data.map((d) => d.count), 1);
    const yMax = Math.ceil(maxVal * 1.2);

    const points = data.data.map((d, i) => ({
      x: padding.left + (i / (data.data.length - 1)) * innerW,
      y: padding.top + innerH - (d.count / yMax) * innerH,
      value: d.count,
      date: d.date,
    }));

    const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
    const areaPath = linePath + ` L ${points[points.length - 1].x} ${padding.top + innerH} L ${points[0].x} ${padding.top + innerH} Z`;

    return { width, height, padding, innerW, innerH, yMax, points, linePath, areaPath };
  }, [data]);

  if (isLoading) return <WidgetSkeleton className={className} />;
  if (error) return <WidgetError title="Critical Findings" onRetry={fetchData} className={className} />;

  const totalCritical = data?.data?.reduce((sum, d) => sum + d.count, 0) || 0;

  return (
    <WidgetCard
      title="Critical Findings Trend"
      subtitle={`30-day trend (${totalCritical} total)`}
      icon={FireIcon}
      iconColor="red"
      onRefresh={fetchData}
      className={className}
    >
      <div className="p-4">
        {chartConfig ? (
          <>
            <svg width="100%" viewBox={`0 0 ${chartConfig.width} ${chartConfig.height}`} preserveAspectRatio="xMidYMid meet" className="overflow-visible">
              <defs>
                <linearGradient id="critical-trend-gradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#DC2626" stopOpacity="0.15" />
                  <stop offset="100%" stopColor="#DC2626" stopOpacity="0.02" />
                </linearGradient>
              </defs>

              {/* Area */}
              <path d={chartConfig.areaPath} fill="url(#critical-trend-gradient)" />

              {/* Line */}
              <path d={chartConfig.linePath} fill="none" stroke="#DC2626" strokeWidth="2" strokeLinecap="round" />

              {/* Dots */}
              {chartConfig.points.map((pt, i) => (
                <g key={i}>
                  {hoveredIdx === i && (
                    <circle cx={pt.x} cy={pt.y} r="6" fill="#DC2626" opacity="0.2" />
                  )}
                  <circle cx={pt.x} cy={pt.y} r={hoveredIdx === i ? 4 : 2} fill="#DC2626" className="transition-all duration-150" />
                  <rect x={pt.x - 8} y={chartConfig.padding.top} width="16" height={chartConfig.innerH} fill="transparent"
                    onMouseEnter={() => setHoveredIdx(i)} onMouseLeave={() => setHoveredIdx(null)} className="cursor-pointer" />
                </g>
              ))}

              {/* X labels (weekly) */}
              {chartConfig.points.filter((_, i) => i % 7 === 0 || i === chartConfig.points.length - 1).map((pt) => (
                <text key={pt.date} x={pt.x} y={chartConfig.height - 6} textAnchor="middle" className="fill-gray-400 text-[8px]">
                  {new Date(pt.date).toLocaleDateString('en', { month: 'short', day: 'numeric' })}
                </text>
              ))}
            </svg>

            {/* Tooltip */}
            {hoveredIdx !== null && chartConfig.points[hoveredIdx] && (
              <div className="mt-2 p-2 bg-gray-50 dark:bg-gray-800/50 rounded text-xs flex items-center gap-3">
                <span className="text-gray-500">
                  {new Date(chartConfig.points[hoveredIdx].date).toLocaleDateString()}
                </span>
                <span className="font-bold text-red-600">{chartConfig.points[hoveredIdx].value} critical</span>
              </div>
            )}
          </>
        ) : (
          <p className="text-center text-gray-400 py-8">No trend data</p>
        )}
      </div>
    </WidgetCard>
  );
}

export default CriticalFindingsTrendWidget;
