/**
 * LLM Token Spend Widget (P0)
 *
 * Metric card showing daily/monthly token usage and cost
 * with model-level breakdown.
 *
 * Per ADR-084: Widget ID 'scanner-llm-token-spend'
 *
 * @module components/dashboard/widgets/scanner/LLMTokenSpendWidget
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  CurrencyDollarIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
} from '@heroicons/react/24/solid';
import { MOCK_LLM_TOKEN_SPEND } from '../../../../services/vulnScannerMockData';
import { WidgetSkeleton, WidgetError, formatNumber } from './ScannerWidgetShared';

/**
 * LLMTokenSpendWidget component
 */
export function LLMTokenSpendWidget({
  refreshInterval = 60000,
  className = '',
}) {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [viewMode, setViewMode] = useState('daily'); // 'daily' or 'monthly'
  const mountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    try {
      await new Promise((r) => setTimeout(r, 200));
      if (mountedRef.current) {
        setData(MOCK_LLM_TOKEN_SPEND);
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
  if (error) return <WidgetError title="LLM Token Spend" onRetry={fetchData} className={className} />;

  const isDaily = viewMode === 'daily';
  const tokens = isDaily ? data?.daily_tokens : data?.monthly_tokens;
  const cost = isDaily ? data?.daily_cost_usd : data?.monthly_cost_usd;
  const trendDown = (data?.trend_pct || 0) < 0;

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        shadow-card p-5 h-full flex flex-col
        ${className}
      `}
      role="region"
      aria-label="LLM Token Spend"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="p-2.5 rounded-lg bg-amber-100 dark:bg-amber-900/30">
          <CurrencyDollarIcon className="w-5 h-5 text-amber-600 dark:text-amber-400" />
        </div>
        {/* Toggle */}
        <div className="flex rounded-lg bg-gray-100 dark:bg-gray-800 p-0.5">
          <button
            onClick={() => setViewMode('daily')}
            className={`px-2 py-1 text-xs font-medium rounded-md transition-colors ${
              isDaily
                ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Daily
          </button>
          <button
            onClick={() => setViewMode('monthly')}
            className={`px-2 py-1 text-xs font-medium rounded-md transition-colors ${
              !isDaily
                ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Monthly
          </button>
        </div>
      </div>

      {/* Cost */}
      <div className="mb-1">
        <span className="text-2xl font-bold text-gray-900 dark:text-gray-50 tracking-tight">
          ${cost?.toFixed(2) || '0.00'}
        </span>
      </div>

      {/* Tokens */}
      <p className="text-xs text-gray-500 mb-1">
        {formatNumber(tokens || 0)} tokens {isDaily ? 'today' : 'this month'}
      </p>

      {/* Trend */}
      <div className={`flex items-center gap-1 text-xs font-medium ${
        trendDown
          ? 'text-green-600 dark:text-green-400'
          : 'text-red-600 dark:text-red-400'
      }`}>
        {trendDown ? (
          <ArrowTrendingDownIcon className="w-3.5 h-3.5" />
        ) : (
          <ArrowTrendingUpIcon className="w-3.5 h-3.5" />
        )}
        <span>{Math.abs(data?.trend_pct || 0)}% vs prior period</span>
      </div>

      <h3 className="text-sm font-medium text-gray-600 dark:text-gray-400 mt-2">
        LLM Token Spend
      </h3>

      {/* Model breakdown */}
      {data?.model_breakdown?.length > 0 && (
        <div className="mt-auto pt-4 border-t border-gray-100 dark:border-gray-700">
          <p className="text-[10px] font-medium text-gray-400 uppercase mb-2">By Model</p>
          <div className="space-y-2">
            {data.model_breakdown.map((m) => (
              <div key={m.model} className="flex items-center justify-between">
                <span className="text-xs text-gray-600 dark:text-gray-400 truncate mr-2 font-mono">
                  {m.model}
                </span>
                <span className="text-xs font-medium text-gray-900 dark:text-gray-100 flex-shrink-0">
                  ${m.cost_usd.toFixed(2)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default LLMTokenSpendWidget;
