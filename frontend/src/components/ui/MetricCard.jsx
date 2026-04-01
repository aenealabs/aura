import { memo } from 'react';
import {
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  MinusIcon,
} from '@heroicons/react/24/solid';
import { MetricCardSkeleton } from './LoadingSkeleton';

// Trend indicator component (memoized to prevent unnecessary re-renders)
const TrendIndicator = memo(function TrendIndicator({ value, inverse = false }) {
  if (value === 0 || value === null || value === undefined) {
    return (
      <span className="flex items-center gap-1 text-surface-500">
        <MinusIcon className="w-4 h-4" />
        <span className="text-sm font-medium">0%</span>
      </span>
    );
  }

  // For some metrics, down is good (e.g., vulnerabilities)
  const isPositive = inverse ? value < 0 : value > 0;
  const absValue = Math.abs(value);

  return (
    <span
      className={`
        flex items-center gap-1
        ${isPositive
          ? 'text-olive-600 dark:text-olive-400'
          : 'text-critical-600 dark:text-critical-400'
        }
      `}
    >
      {value > 0 ? (
        <ArrowTrendingUpIcon className="w-4 h-4" />
      ) : (
        <ArrowTrendingDownIcon className="w-4 h-4" />
      )}
      <span className="text-sm font-medium">{absValue}%</span>
    </span>
  );
});

// Mini sparkline chart (memoized for performance)
const Sparkline = memo(function Sparkline({ data, color = 'aura', className = '' }) {
  if (!data || data.length < 2) return null;

  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;

  const points = data.map((value, index) => {
    const x = (index / (data.length - 1)) * 100;
    const y = 100 - ((value - min) / range) * 100;
    return `${x},${y}`;
  }).join(' ');

  const colorClasses = {
    aura: 'stroke-aura-500 dark:stroke-aura-400',
    olive: 'stroke-olive-500 dark:stroke-olive-400',
    critical: 'stroke-critical-500 dark:stroke-critical-400',
    warning: 'stroke-warning-500 dark:stroke-warning-400',
  };

  return (
    <svg
      viewBox="0 0 100 40"
      className={`w-full h-10 ${className}`}
      preserveAspectRatio="none"
    >
      <polyline
        points={points}
        fill="none"
        className={colorClasses[color] || colorClasses.aura}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
});

// Status badge for metric cards (memoized for performance)
const StatusBadge = memo(function StatusBadge({ status, label }) {
  const statusClasses = {
    healthy: 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400',
    warning: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    critical: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
    info: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
    neutral: 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-300',
  };

  return (
    <span
      className={`
        inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap
        ${statusClasses[status] || statusClasses.neutral}
      `}
    >
      {label}
    </span>
  );
});

// Main MetricCard component (memoized to prevent re-renders when parent state changes)
const MetricCard = memo(function MetricCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  trendInverse = false,
  trendLabel,
  sparklineData,
  sparklineColor = 'aura',
  status,
  statusLabel,
  iconColor = 'aura',
  loading = false,
  onClick,
  className = '',
  titleClassName = '',
}) {
  if (loading) {
    return <MetricCardSkeleton className={className} />;
  }

  const iconColorClasses = {
    aura: 'bg-aura-100 text-aura-600 dark:bg-aura-900/30 dark:text-aura-400',
    olive: 'bg-olive-100 text-olive-600 dark:bg-olive-900/30 dark:text-olive-400',
    critical: 'bg-critical-100 text-critical-600 dark:bg-critical-900/30 dark:text-critical-400',
    warning: 'bg-warning-100 text-warning-600 dark:bg-warning-900/30 dark:text-warning-400',
    surface: 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-300',
  };

  const CardWrapper = onClick ? 'button' : 'div';

  // Status-based border colors for visual indication
  const statusBorderClasses = {
    healthy: 'border-l-4 border-l-olive-500',
    warning: 'border-l-4 border-l-warning-500',
    critical: 'border-l-4 border-l-critical-500',
    neutral: '',
  };

  return (
    <CardWrapper
      onClick={onClick}
      className={`
        glass-card
        transition-all duration-200 ease-[var(--ease-tahoe)]
        px-4 py-3 text-left w-full
        ${status ? statusBorderClasses[status] || '' : ''}
        ${onClick ? 'cursor-pointer hover:-translate-y-1 hover:shadow-[var(--shadow-glass-hover)]' : ''}
        ${className}
      `}
    >
      {/* Row 1: Icon + Value + Trend */}
      <div className="flex items-center gap-2 mb-0.5 min-w-0">
        {/* Icon */}
        {Icon && (
          <div
            className={`
              p-2 rounded-lg flex-shrink-0
              ${iconColorClasses[iconColor] || iconColorClasses.aura}
            `}
          >
            <Icon className="w-5 h-5" />
          </div>
        )}
        {/* Value - responsive sizing for longer text */}
        <span className={`font-bold text-surface-900 dark:text-surface-50 truncate min-w-0 ${
          String(value).length > 12 ? 'text-lg' : 'text-2xl'
        }`}>
          {value}
        </span>
        {/* Trend (always next to value) */}
        {trend !== undefined && (
          <TrendIndicator value={trend} inverse={trendInverse} />
        )}
      </div>

      {/* Row 2: Status badge (if present) */}
      {(status && statusLabel) && (
        <div className="mb-1">
          <StatusBadge status={status} label={statusLabel} />
        </div>
      )}

      {/* Row 3: Title */}
      <h3 className={`text-sm mb-0.5 whitespace-nowrap ${titleClassName || 'font-medium text-surface-500 dark:text-surface-400'}`}>
        {title}
      </h3>

      {/* Row 4: Subtitle */}
      {(subtitle || trendLabel) && (
        <p className="text-xs text-surface-400 dark:text-surface-500 whitespace-nowrap">
          {trendLabel || subtitle}
        </p>
      )}

      {/* Sparkline chart */}
      {sparklineData && sparklineData.length > 1 && (
        <div className="mt-2 -mx-1">
          <Sparkline data={sparklineData} color={sparklineColor} />
        </div>
      )}
    </CardWrapper>
  );
});

export default MetricCard;

// Compact metric card variant (memoized)
export const MetricCardCompact = memo(function MetricCardCompact({
  title,
  value,
  icon: Icon,
  iconColor = 'aura',
  loading = false,
  className = '',
}) {
  if (loading) {
    return (
      <div className={`flex items-center gap-3 p-3 rounded-xl glass-card-subtle ${className}`}>
        <div className="skeleton w-8 h-8 rounded-lg" />
        <div className="flex-1">
          <div className="skeleton w-12 h-5 rounded mb-1" />
          <div className="skeleton w-20 h-3 rounded" />
        </div>
      </div>
    );
  }

  const iconColorClasses = {
    aura: 'bg-aura-100 text-aura-600 dark:bg-aura-900/30 dark:text-aura-400',
    olive: 'bg-olive-100 text-olive-600 dark:bg-olive-900/30 dark:text-olive-400',
    critical: 'bg-critical-100 text-critical-600 dark:bg-critical-900/30 dark:text-critical-400',
    warning: 'bg-warning-100 text-warning-600 dark:bg-warning-900/30 dark:text-warning-400',
  };

  return (
    <div
      className={`
        flex items-center gap-3 p-3 rounded-xl
        glass-card-subtle
        transition-all duration-200 ease-[var(--ease-tahoe)]
        ${className}
      `}
    >
      {Icon && (
        <div
          className={`
            p-2 rounded-lg
            ${iconColorClasses[iconColor] || iconColorClasses.aura}
          `}
        >
          <Icon className="w-4 h-4" />
        </div>
      )}
      <div>
        <p className="text-lg font-semibold text-surface-900 dark:text-surface-50">
          {value}
        </p>
        <p className="text-xs text-surface-500 dark:text-surface-400">
          {title}
        </p>
      </div>
    </div>
  );
});

// Grid layout helper for metric cards (memoized)
export const MetricCardGrid = memo(function MetricCardGrid({ children, columns = 4, className = '' }) {
  const gridCols = {
    2: 'grid-cols-1 sm:grid-cols-2',
    3: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
    4: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4',
    5: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5',
    6: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6',
  };

  return (
    <div className={`grid gap-4 md:gap-6 ${gridCols[columns] || gridCols[4]} ${className}`}>
      {children}
    </div>
  );
});
