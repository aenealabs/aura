/**
 * LLM Latency Widget (P1)
 *
 * Time series showing p50/p95/p99 LLM latency.
 *
 * Per ADR-084: Widget ID 'scanner-llm-latency'
 *
 * @module components/dashboard/widgets/scanner/LLMLatencyWidget
 */

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { BoltIcon } from '@heroicons/react/24/solid';
import { MOCK_LLM_LATENCY } from '../../../../services/vulnScannerMockData';
import { WidgetSkeleton, WidgetError, WidgetCard } from './ScannerWidgetShared';

const LATENCY_COLORS = { p50: '#10B981', p95: '#F59E0B', p99: '#DC2626' };

/**
 * LLMLatencyWidget component
 */
export function LLMLatencyWidget({
  refreshInterval = 30000,
  className = '',
}) {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    try {
      await new Promise((r) => setTimeout(r, 200));
      if (mountedRef.current) { setData(MOCK_LLM_LATENCY); setError(null); }
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
    const padding = { top: 12, right: 12, bottom: 28, left: 40 };
    const width = 400;
    const height = 140;
    const innerW = width - padding.left - padding.right;
    const innerH = height - padding.top - padding.bottom;
    const maxVal = Math.max(...data.data.map((d) => d.p99_ms));
    const yMax = Math.ceil(maxVal / 1000) * 1000;

    const makePoints = (key) => data.data.map((d, i) => ({
      x: padding.left + (i / (data.data.length - 1)) * innerW,
      y: padding.top + innerH - (d[key] / yMax) * innerH,
      value: d[key],
    }));
    const toPath = (pts) => pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');

    return {
      width, height, padding, innerW, innerH, yMax,
      lines: [
        { key: 'p99', label: 'P99', color: LATENCY_COLORS.p99, points: makePoints('p99_ms'), path: toPath(makePoints('p99_ms')), dash: '3 2' },
        { key: 'p95', label: 'P95', color: LATENCY_COLORS.p95, points: makePoints('p95_ms'), path: toPath(makePoints('p95_ms')) },
        { key: 'p50', label: 'P50', color: LATENCY_COLORS.p50, points: makePoints('p50_ms'), path: toPath(makePoints('p50_ms')) },
      ],
    };
  }, [data]);

  if (isLoading) return <WidgetSkeleton className={className} />;
  if (error) return <WidgetError title="LLM Latency" onRetry={fetchData} className={className} />;

  return (
    <WidgetCard
      title="LLM Latency"
      subtitle="Response time percentiles (ms)"
      icon={BoltIcon}
      iconColor="amber"
      onRefresh={fetchData}
      className={className}
    >
      {/* Current values */}
      <div className="px-4 py-2 border-b border-gray-200 dark:border-gray-700 flex items-center gap-6">
        {data?.current && Object.entries(data.current).map(([key, val]) => {
          const label = key.replace('_ms', '').toUpperCase();
          const color = LATENCY_COLORS[key.replace('_ms', '')] || '#6B7280';
          return (
            <div key={key} className="text-center">
              <p className="text-xs text-gray-400">{label}</p>
              <p className="text-sm font-bold" style={{ color }}>{val}ms</p>
            </div>
          );
        })}
      </div>

      <div className="p-4">
        {chartConfig ? (
          <>
            <svg width="100%" viewBox={`0 0 ${chartConfig.width} ${chartConfig.height}`} preserveAspectRatio="xMidYMid meet">
              {/* Lines */}
              {chartConfig.lines.map((line) => (
                <path key={line.key} d={line.path} fill="none" stroke={line.color} strokeWidth="2" strokeLinecap="round" strokeDasharray={line.dash || 'none'} />
              ))}
              {/* End dots */}
              {chartConfig.lines.map((line) => {
                const last = line.points[line.points.length - 1];
                return <circle key={`dot-${line.key}`} cx={last.x} cy={last.y} r="3" fill={line.color} />;
              })}
            </svg>

            <div className="mt-2 flex items-center justify-center gap-4">
              {chartConfig.lines.map((line) => (
                <div key={line.key} className="flex items-center gap-1.5">
                  <div className="w-3 h-0.5 rounded" style={{ backgroundColor: line.color }} />
                  <span className="text-[10px] text-gray-500 font-medium">{line.label}</span>
                </div>
              ))}
            </div>
          </>
        ) : (
          <p className="text-center text-gray-400 py-8">No latency data</p>
        )}
      </div>
    </WidgetCard>
  );
}

export default LLMLatencyWidget;
