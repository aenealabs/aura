/**
 * Scan Duration Trend Widget (P1)
 *
 * Time series line chart showing scan duration averages
 * with P50/P95 percentile lines.
 *
 * Per ADR-084: Widget ID 'scanner-duration-trend'
 *
 * @module components/dashboard/widgets/scanner/ScanDurationTrendWidget
 */

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { ChartBarIcon } from '@heroicons/react/24/solid';
import { MOCK_SCAN_DURATION_TREND } from '../../../../services/vulnScannerMockData';
import { WidgetSkeleton, WidgetError, WidgetCard } from './ScannerWidgetShared';

const LINE_COLORS = {
  avg: '#3B82F6',
  p50: '#10B981',
  p95: '#F59E0B',
};

/**
 * ScanDurationTrendWidget component
 */
export function ScanDurationTrendWidget({
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
      if (mountedRef.current) { setData(MOCK_SCAN_DURATION_TREND); setError(null); }
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
    const padding = { top: 16, right: 16, bottom: 32, left: 44 };
    const width = 400;
    const height = 160;
    const innerW = width - padding.left - padding.right;
    const innerH = height - padding.top - padding.bottom;
    const maxVal = Math.max(...data.data.map((d) => d.p95_s));
    const yMax = Math.ceil(maxVal / 50) * 50;

    const makePoints = (key) => data.data.map((d, i) => ({
      x: padding.left + (i / (data.data.length - 1)) * innerW,
      y: padding.top + innerH - (d[key] / yMax) * innerH,
      value: d[key],
    }));

    const toPath = (pts) => pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');

    return {
      width, height, padding, innerW, innerH, yMax,
      lines: [
        { key: 'p95', label: 'P95', color: LINE_COLORS.p95, points: makePoints('p95_s'), path: toPath(makePoints('p95_s')), dash: '4 2' },
        { key: 'avg', label: 'Avg', color: LINE_COLORS.avg, points: makePoints('avg_duration_s'), path: toPath(makePoints('avg_duration_s')) },
        { key: 'p50', label: 'P50', color: LINE_COLORS.p50, points: makePoints('p50_s'), path: toPath(makePoints('p50_s')) },
      ],
      yLabels: [0, Math.round(yMax / 4), Math.round(yMax / 2), Math.round(yMax * 3 / 4), yMax].map((v) => ({
        value: v,
        y: padding.top + innerH - (v / yMax) * innerH,
      })),
    };
  }, [data]);

  if (isLoading) return <WidgetSkeleton className={className} />;
  if (error) return <WidgetError title="Scan Duration" onRetry={fetchData} className={className} />;

  return (
    <WidgetCard
      title="Scan Duration Trend"
      subtitle="Average and percentile scan times (seconds)"
      icon={ChartBarIcon}
      iconColor="blue"
      onRefresh={fetchData}
      className={className}
    >
      <div className="p-4">
        {chartConfig ? (
          <>
            <svg width="100%" viewBox={`0 0 ${chartConfig.width} ${chartConfig.height}`} preserveAspectRatio="xMidYMid meet" className="overflow-visible">
              {/* Grid */}
              {chartConfig.yLabels.map((label, i) => (
                <g key={i}>
                  <line x1={chartConfig.padding.left} y1={label.y} x2={chartConfig.width - chartConfig.padding.right} y2={label.y} className="stroke-gray-200 dark:stroke-gray-700" strokeWidth="1" opacity="0.5" />
                  <text x={chartConfig.padding.left - 6} y={label.y} textAnchor="end" dominantBaseline="middle" className="fill-gray-400 text-[9px]">{label.value}s</text>
                </g>
              ))}

              {/* Lines */}
              {chartConfig.lines.map((line) => (
                <path key={line.key} d={line.path} fill="none" stroke={line.color} strokeWidth="2" strokeLinecap="round" strokeDasharray={line.dash || 'none'} />
              ))}

              {/* Hover dots */}
              {hoveredIdx !== null && chartConfig.lines.map((line) => (
                <circle key={`dot-${line.key}`} cx={line.points[hoveredIdx].x} cy={line.points[hoveredIdx].y} r="4" fill={line.color} stroke="white" strokeWidth="2" />
              ))}

              {/* Hit areas */}
              {data?.data?.map((_, i) => {
                const x = chartConfig.padding.left + (i / (data.data.length - 1)) * chartConfig.innerW;
                return (
                  <rect key={i} x={x - 20} y={chartConfig.padding.top} width="40" height={chartConfig.innerH} fill="transparent"
                    onMouseEnter={() => setHoveredIdx(i)} onMouseLeave={() => setHoveredIdx(null)} className="cursor-pointer" />
                );
              })}

              {/* X labels */}
              {data?.data?.map((d, i) => {
                const x = chartConfig.padding.left + (i / (data.data.length - 1)) * chartConfig.innerW;
                return (
                  <text key={i} x={x} y={chartConfig.height - 8} textAnchor="middle" className="fill-gray-400 text-[9px]">
                    {new Date(d.date).toLocaleDateString('en', { month: 'short', day: 'numeric' })}
                  </text>
                );
              })}
            </svg>

            {/* Tooltip */}
            {hoveredIdx !== null && data?.data?.[hoveredIdx] && (
              <div className="mt-2 p-2 bg-gray-50 dark:bg-gray-800/50 rounded-lg text-xs flex items-center gap-4">
                <span className="text-gray-500">{new Date(data.data[hoveredIdx].date).toLocaleDateString()}</span>
                {chartConfig.lines.map((line) => (
                  <span key={line.key} className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full" style={{ backgroundColor: line.color }} />
                    <span className="font-medium text-gray-700 dark:text-gray-300">{line.points[hoveredIdx].value}s</span>
                    <span className="text-gray-400">{line.label}</span>
                  </span>
                ))}
              </div>
            )}

            {/* Legend */}
            <div className="mt-3 flex items-center justify-center gap-4">
              {chartConfig.lines.map((line) => (
                <div key={line.key} className="flex items-center gap-1.5">
                  <div className="w-3 h-0.5 rounded" style={{ backgroundColor: line.color, borderStyle: line.dash ? 'dashed' : 'solid' }} />
                  <span className="text-[10px] text-gray-500 font-medium">{line.label}</span>
                </div>
              ))}
            </div>
          </>
        ) : (
          <p className="text-center text-gray-400 py-8">No duration data</p>
        )}
      </div>
    </WidgetCard>
  );
}

export default ScanDurationTrendWidget;
