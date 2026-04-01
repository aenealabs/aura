/**
 * True Positive Rate Widget (P0)
 *
 * Gauge displaying 0-100% true positive rate for verified findings
 * with trend indicator and breakdown.
 *
 * Per ADR-084: Widget ID 'scanner-true-positive-rate'
 *
 * @module components/dashboard/widgets/scanner/TruePositiveRateWidget
 */

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { CheckBadgeIcon, ArrowTrendingUpIcon, ArrowTrendingDownIcon } from '@heroicons/react/24/solid';
import { MOCK_TRUE_POSITIVE_RATE } from '../../../../services/vulnScannerMockData';
import { WidgetSkeleton, WidgetError } from './ScannerWidgetShared';

/**
 * TruePositiveRateWidget component
 */
export function TruePositiveRateWidget({
  refreshInterval = 300000,
  className = '',
}) {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [displayRate, setDisplayRate] = useState(0);
  const mountedRef = useRef(true);
  const animationRef = useRef(null);

  const fetchData = useCallback(async () => {
    try {
      await new Promise((r) => setTimeout(r, 200));
      if (mountedRef.current) {
        setData(MOCK_TRUE_POSITIVE_RATE);
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

  // Animate gauge
  useEffect(() => {
    if (!data) return;
    const target = data.rate;
    const start = displayRate;
    const duration = 800;
    const startTime = performance.now();

    const animate = (currentTime) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayRate(start + (target - start) * eased);
      if (progress < 1) animationRef.current = requestAnimationFrame(animate);
    };

    animationRef.current = requestAnimationFrame(animate);
    return () => { if (animationRef.current) cancelAnimationFrame(animationRef.current); };
  }, [data?.rate]);

  if (isLoading) return <WidgetSkeleton className={className} />;
  if (error) return <WidgetError title="True Positive Rate" onRetry={fetchData} className={className} />;

  const size = 140;
  const strokeWidth = 12;
  const center = size / 2;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const progressOffset = circumference - (displayRate / 100) * circumference;

  const rateColor = displayRate >= 85 ? '#10B981' : displayRate >= 70 ? '#F59E0B' : '#DC2626';
  const trendPositive = data?.trend > 0;

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        shadow-card p-5 h-full flex flex-col items-center justify-center
        ${className}
      `}
      role="meter"
      aria-valuenow={data?.rate || 0}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`True positive rate: ${data?.rate || 0}%`}
    >
      {/* Gauge */}
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="transform -rotate-90">
          <circle
            cx={center} cy={center} r={radius}
            fill="none" stroke="currentColor" strokeWidth={strokeWidth}
            className="text-gray-200 dark:text-gray-700"
          />
          <circle
            cx={center} cy={center} r={radius}
            fill="none" stroke={rateColor} strokeWidth={strokeWidth}
            strokeDasharray={circumference} strokeDashoffset={progressOffset}
            strokeLinecap="round"
            className="transition-all duration-500 ease-out"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-bold" style={{ color: rateColor }}>
            {Math.round(displayRate)}%
          </span>
        </div>
      </div>

      <h3 className="mt-3 text-sm font-semibold text-gray-900 dark:text-gray-100">
        True Positive Rate
      </h3>

      {/* Trend */}
      {data?.trend !== undefined && (
        <div className={`mt-1 flex items-center gap-1 text-xs font-medium ${
          trendPositive ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
        }`}>
          {trendPositive ? (
            <ArrowTrendingUpIcon className="w-3.5 h-3.5" />
          ) : (
            <ArrowTrendingDownIcon className="w-3.5 h-3.5" />
          )}
          <span>{Math.abs(data.trend)}% vs last week</span>
        </div>
      )}

      {/* Breakdown */}
      <div className="mt-3 flex items-center gap-4 text-xs text-gray-500">
        <span>{data?.true_positives || 0} TP</span>
        <span className="w-px h-3 bg-gray-200 dark:bg-gray-700" />
        <span>{data?.false_positives || 0} FP</span>
        <span className="w-px h-3 bg-gray-200 dark:bg-gray-700" />
        <span>{data?.total_verified || 0} verified</span>
      </div>
    </div>
  );
}

export default TruePositiveRateWidget;
