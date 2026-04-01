/**
 * Donut Chart Widgets (P2)
 *
 * Shared donut chart component used by:
 * - Findings by Language
 * - Verification Status Distribution
 * - Scan Depth Distribution
 *
 * Per ADR-084
 *
 * @module components/dashboard/widgets/scanner/DonutWidgets
 */

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
  CodeBracketIcon,
  CheckBadgeIcon,
  AdjustmentsHorizontalIcon,
} from '@heroicons/react/24/solid';
import {
  MOCK_FINDINGS_BY_LANGUAGE,
  MOCK_VERIFICATION_STATUS,
  MOCK_SCAN_DEPTH_DISTRIBUTION,
} from '../../../../services/vulnScannerMockData';
import { WidgetSkeleton, WidgetError, WidgetCard } from './ScannerWidgetShared';

const DONUT_PALETTES = {
  language: ['#3B82F6', '#10B981', '#F59E0B', '#DC2626', '#8B5CF6', '#6B7280'],
  verification: ['#10B981', '#6B7280', '#F59E0B', '#9CA3AF'],
  depth: ['#93C5FD', '#3B82F6', '#1D4ED8', '#1E3A5F'],
};

/**
 * Reusable donut chart
 */
function DonutChart({ segments, palette, size = 120, strokeWidth = 24 }) {
  const center = size / 2;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const [hoveredIdx, setHoveredIdx] = useState(null);

  let accumulated = 0;
  const arcs = segments.map((seg, idx) => {
    const pct = seg.pct || 0;
    const offset = circumference - (pct / 100) * circumference;
    const rotation = (accumulated / 100) * 360 - 90;
    accumulated += pct;
    return { ...seg, offset, rotation, color: palette[idx % palette.length] };
  });

  return (
    <div className="flex items-center gap-4">
      <div className="relative flex-shrink-0" style={{ width: size, height: size }}>
        <svg width={size} height={size}>
          {/* Background */}
          <circle cx={center} cy={center} r={radius} fill="none" strokeWidth={strokeWidth} className="stroke-gray-100 dark:stroke-gray-800" />
          {/* Arcs */}
          {arcs.map((arc, idx) => (
            <circle
              key={idx}
              cx={center} cy={center} r={radius}
              fill="none" stroke={arc.color} strokeWidth={strokeWidth}
              strokeDasharray={`${(arc.pct / 100) * circumference} ${circumference}`}
              transform={`rotate(${arc.rotation} ${center} ${center})`}
              className="transition-opacity duration-200"
              opacity={hoveredIdx !== null && hoveredIdx !== idx ? 0.3 : 1}
              onMouseEnter={() => setHoveredIdx(idx)}
              onMouseLeave={() => setHoveredIdx(null)}
            />
          ))}
        </svg>
        {/* Center label */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          {hoveredIdx !== null ? (
            <>
              <span className="text-sm font-bold text-gray-900 dark:text-gray-100">{arcs[hoveredIdx].count}</span>
              <span className="text-[9px] text-gray-400">{arcs[hoveredIdx].pct}%</span>
            </>
          ) : (
            <>
              <span className="text-sm font-bold text-gray-900 dark:text-gray-100">
                {segments.reduce((s, seg) => s + seg.count, 0)}
              </span>
              <span className="text-[9px] text-gray-400">total</span>
            </>
          )}
        </div>
      </div>

      {/* Legend */}
      <div className="flex-1 space-y-1.5 min-w-0">
        {arcs.map((arc, idx) => (
          <div
            key={idx}
            className={`flex items-center gap-2 text-xs transition-opacity ${
              hoveredIdx !== null && hoveredIdx !== idx ? 'opacity-40' : ''
            }`}
            onMouseEnter={() => setHoveredIdx(idx)}
            onMouseLeave={() => setHoveredIdx(null)}
          >
            <div className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ backgroundColor: arc.color }} />
            <span className="text-gray-600 dark:text-gray-400 truncate">{arc.name}</span>
            <span className="text-gray-900 dark:text-gray-100 font-medium ml-auto flex-shrink-0">{arc.count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Generic donut widget factory
 */
function useDonutWidget(mockData, refreshInterval) {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    try {
      await new Promise((r) => setTimeout(r, 200));
      if (mountedRef.current) { setData(mockData); setError(null); }
    } catch (err) { if (mountedRef.current) setError(err); }
    finally { if (mountedRef.current) setIsLoading(false); }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchData();
    const interval = setInterval(fetchData, refreshInterval);
    return () => { mountedRef.current = false; clearInterval(interval); };
  }, [fetchData, refreshInterval]);

  return { data, isLoading, error, fetchData };
}

/**
 * Findings by Language Widget
 */
export function FindingsByLanguageWidget({ refreshInterval = 300000, className = '' }) {
  const { data, isLoading, error, fetchData } = useDonutWidget(MOCK_FINDINGS_BY_LANGUAGE, refreshInterval);

  if (isLoading) return <WidgetSkeleton className={className} />;
  if (error) return <WidgetError title="By Language" onRetry={fetchData} className={className} />;

  return (
    <WidgetCard title="Findings by Language" subtitle="Distribution across languages" icon={CodeBracketIcon} iconColor="blue" onRefresh={fetchData} className={className}>
      <div className="p-4">
        <DonutChart segments={data?.languages || []} palette={DONUT_PALETTES.language} />
      </div>
    </WidgetCard>
  );
}

/**
 * Verification Status Distribution Widget
 */
export function VerificationStatusWidget({ refreshInterval = 300000, className = '' }) {
  const { data, isLoading, error, fetchData } = useDonutWidget(MOCK_VERIFICATION_STATUS, refreshInterval);

  if (isLoading) return <WidgetSkeleton className={className} />;
  if (error) return <WidgetError title="Verification Status" onRetry={fetchData} className={className} />;

  return (
    <WidgetCard title="Verification Status" subtitle="Finding verification outcomes" icon={CheckBadgeIcon} iconColor="green" onRefresh={fetchData} className={className}>
      <div className="p-4">
        <DonutChart segments={data?.statuses || []} palette={DONUT_PALETTES.verification} />
      </div>
    </WidgetCard>
  );
}

/**
 * Scan Depth Distribution Widget
 */
export function ScanDepthDistributionWidget({ refreshInterval = 300000, className = '' }) {
  const { data, isLoading, error, fetchData } = useDonutWidget(MOCK_SCAN_DEPTH_DISTRIBUTION, refreshInterval);

  if (isLoading) return <WidgetSkeleton className={className} />;
  if (error) return <WidgetError title="Scan Depth" onRetry={fetchData} className={className} />;

  return (
    <WidgetCard title="Scan Depth Distribution" subtitle="Scans by configured depth" icon={AdjustmentsHorizontalIcon} iconColor="blue" onRefresh={fetchData} className={className}>
      <div className="p-4">
        <DonutChart segments={data?.depths || []} palette={DONUT_PALETTES.depth} />
      </div>
    </WidgetCard>
  );
}

export default { FindingsByLanguageWidget, VerificationStatusWidget, ScanDepthDistributionWidget };
