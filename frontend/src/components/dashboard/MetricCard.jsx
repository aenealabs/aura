/**
 * Project Aura - Enhanced Dashboard Metric Card
 *
 * Reusable metric display component with trend indicators,
 * sparkline charts, loading skeletons, and error states.
 * Follows Apple's design philosophy with clean, focused UI.
 *
 * @module components/dashboard/MetricCard
 */

import {
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  MinusIcon,
  ExclamationTriangleIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/solid';

/**
 * Loading skeleton for metric card
 */
function MetricCardSkeleton({ className = '' }) {
  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        p-5 animate-pulse
        ${className}
      `}
    >
      {/* Header row: Icon + Trend */}
      <div className="flex items-center justify-between mb-3">
        <div className="w-10 h-10 rounded-lg bg-surface-200 dark:bg-surface-700" />
        <div className="w-16 h-5 rounded bg-surface-200 dark:bg-surface-700" />
      </div>

      {/* Value */}
      <div className="w-20 h-8 rounded bg-surface-200 dark:bg-surface-700 mb-2" />

      {/* Title */}
      <div className="w-28 h-4 rounded bg-surface-200 dark:bg-surface-700 mb-1" />

      {/* Subtitle */}
      <div className="w-20 h-3 rounded bg-surface-200 dark:bg-surface-700" />

      {/* Sparkline placeholder */}
      <div className="mt-4 w-full h-10 rounded bg-surface-200 dark:bg-surface-700" />
    </div>
  );
}

/**
 * Error state for metric card
 *
 * @param {Object} props - Component props
 * @param {string} props.title - Card title
 * @param {Function} props.onRetry - Retry callback
 * @param {string} [props.className] - Additional CSS classes
 */
function MetricCardError({ title, onRetry, className = '' }) {
  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-critical-200 dark:border-critical-800
        p-5 flex flex-col items-center justify-center text-center
        min-h-[160px]
        ${className}
      `}
    >
      <ExclamationTriangleIcon className="w-8 h-8 text-critical-500 mb-2" />
      <p className="text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
        Failed to load {title}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="
            mt-2 flex items-center gap-1.5 px-3 py-1.5
            text-sm font-medium text-aura-600 dark:text-aura-400
            hover:text-aura-700 dark:hover:text-aura-300
            hover:bg-aura-50 dark:hover:bg-aura-900/20
            rounded-lg transition-colors duration-200
          "
        >
          <ArrowPathIcon className="w-4 h-4" />
          Retry
        </button>
      )}
    </div>
  );
}

/**
 * Trend indicator with directional arrow and color
 *
 * @param {Object} props - Component props
 * @param {number} props.value - Trend percentage value
 * @param {boolean} [props.inverse=false] - Invert positive/negative colors
 */
function TrendIndicator({ value, inverse = false }) {
  if (value === 0 || value === null || value === undefined) {
    return (
      <span className="flex items-center gap-1 text-surface-500">
        <MinusIcon className="w-4 h-4" />
        <span className="text-sm font-medium">0%</span>
      </span>
    );
  }

  // For metrics where down is good (e.g., vulnerabilities, errors)
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
}

/**
 * Mini sparkline chart for historical data visualization
 *
 * @param {Object} props - Component props
 * @param {number[]} props.data - Array of data points
 * @param {string} [props.color='aura'] - Chart color theme
 * @param {string} [props.className] - Additional CSS classes
 */
function Sparkline({ data, color = 'aura', className = '' }) {
  if (!data || data.length < 2) return null;

  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;

  // Generate SVG polyline points
  const points = data
    .map((value, index) => {
      const x = (index / (data.length - 1)) * 100;
      const y = 100 - ((value - min) / range) * 80 - 10; // 10-90 range for padding
      return `${x},${y}`;
    })
    .join(' ');

  // Generate area fill path
  const areaPath = data
    .map((value, index) => {
      const x = (index / (data.length - 1)) * 100;
      const y = 100 - ((value - min) / range) * 80 - 10;
      return index === 0 ? `M 0,100 L ${x},${y}` : `L ${x},${y}`;
    })
    .join(' ') + ' L 100,100 Z';

  const colorClasses = {
    aura: {
      stroke: 'stroke-aura-500 dark:stroke-aura-400',
      fill: 'fill-aura-500/10 dark:fill-aura-400/10',
    },
    olive: {
      stroke: 'stroke-olive-500 dark:stroke-olive-400',
      fill: 'fill-olive-500/10 dark:fill-olive-400/10',
    },
    critical: {
      stroke: 'stroke-critical-500 dark:stroke-critical-400',
      fill: 'fill-critical-500/10 dark:fill-critical-400/10',
    },
    warning: {
      stroke: 'stroke-warning-500 dark:stroke-warning-400',
      fill: 'fill-warning-500/10 dark:fill-warning-400/10',
    },
  };

  const colors = colorClasses[color] || colorClasses.aura;

  return (
    <svg
      viewBox="0 0 100 100"
      className={`w-full h-12 ${className}`}
      preserveAspectRatio="none"
    >
      {/* Area fill */}
      <path d={areaPath} className={colors.fill} />
      {/* Line */}
      <polyline
        points={points}
        fill="none"
        className={colors.stroke}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
      {/* End point dot */}
      {data.length > 0 && (
        <circle
          cx="100"
          cy={100 - ((data[data.length - 1] - min) / range) * 80 - 10}
          r="3"
          className={`${colors.stroke} fill-white dark:fill-surface-800`}
          strokeWidth="2"
          vectorEffect="non-scaling-stroke"
        />
      )}
    </svg>
  );
}

/**
 * Status badge for metric cards
 *
 * @param {Object} props - Component props
 * @param {'healthy'|'warning'|'critical'|'info'|'neutral'} props.status - Status type
 * @param {string} props.label - Badge label text
 */
function StatusBadge({ status, label }) {
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
        inline-flex items-center px-2 py-0.5 rounded-full
        text-xs font-medium whitespace-nowrap
        ${statusClasses[status] || statusClasses.neutral}
      `}
    >
      {label}
    </span>
  );
}

/**
 * Enhanced Metric Card Component
 *
 * Displays a single metric with optional trend indicator, sparkline chart,
 * status badge, and loading/error states.
 *
 * @param {Object} props - Component props
 * @param {string} props.title - Metric title
 * @param {string|number} props.value - Metric value
 * @param {React.ComponentType} [props.icon] - Heroicon component
 * @param {number} [props.trend] - Trend percentage (positive = up)
 * @param {boolean} [props.trendInverse=false] - Invert trend color (down = good)
 * @param {string} [props.trendLabel] - Label for trend context
 * @param {number[]} [props.sparklineData] - Historical data for sparkline
 * @param {string} [props.sparklineColor='aura'] - Sparkline color theme
 * @param {string} [props.status] - Status badge type
 * @param {string} [props.statusLabel] - Status badge label
 * @param {string} [props.subtitle] - Additional context text
 * @param {string} [props.iconColor='aura'] - Icon background color
 * @param {boolean} [props.loading=false] - Show loading skeleton
 * @param {Error|null} [props.error=null] - Error state
 * @param {Function} [props.onRetry] - Retry callback for error state
 * @param {Function} [props.onClick] - Click handler (makes card interactive)
 * @param {string} [props.className] - Additional CSS classes
 *
 * @example
 * <DashboardMetricCard
 *   title="Active Agents"
 *   value={12}
 *   icon={CpuChipIcon}
 *   trend={15}
 *   trendLabel="vs last hour"
 *   sparklineData={[8, 10, 9, 11, 12]}
 *   iconColor="aura"
 * />
 */
export default function DashboardMetricCard({
  title,
  value,
  icon: Icon,
  trend,
  trendInverse = false,
  trendLabel,
  sparklineData,
  sparklineColor = 'aura',
  status,
  statusLabel,
  subtitle,
  iconColor = 'aura',
  loading = false,
  error = null,
  onRetry,
  onClick,
  className = '',
}) {
  // Show loading skeleton
  if (loading) {
    return <MetricCardSkeleton className={className} />;
  }

  // Show error state
  if (error) {
    return <MetricCardError title={title} onRetry={onRetry} className={className} />;
  }

  const iconColorClasses = {
    aura: 'bg-aura-100 text-aura-600 dark:bg-aura-900/30 dark:text-aura-400',
    olive: 'bg-olive-100 text-olive-600 dark:bg-olive-900/30 dark:text-olive-400',
    critical: 'bg-critical-100 text-critical-600 dark:bg-critical-900/30 dark:text-critical-400',
    warning: 'bg-warning-100 text-warning-600 dark:bg-warning-900/30 dark:text-warning-400',
    surface: 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-300',
  };

  const CardWrapper = onClick ? 'button' : 'div';

  return (
    <CardWrapper
      onClick={onClick}
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        shadow-card hover:shadow-card-hover
        transition-all duration-250 ease-smooth
        p-5 text-left w-full
        ${onClick ? 'cursor-pointer hover:-translate-y-0.5 active:scale-[0.99]' : ''}
        ${className}
      `}
    >
      {/* Row 1: Icon + Trend */}
      <div className="flex items-center justify-between mb-3">
        {/* Icon */}
        {Icon && (
          <div
            className={`
              p-2.5 rounded-lg flex-shrink-0
              ${iconColorClasses[iconColor] || iconColorClasses.aura}
            `}
          >
            <Icon className="w-5 h-5" />
          </div>
        )}

        {/* Trend indicator */}
        {trend !== undefined && trend !== null && (
          <TrendIndicator value={trend} inverse={trendInverse} />
        )}
      </div>

      {/* Row 2: Value - responsive sizing for longer text */}
      <div className="mb-1 min-w-0">
        <span className={`font-bold text-surface-900 dark:text-surface-50 tracking-tight truncate block ${
          String(typeof value === 'number' ? value.toLocaleString() : value).length > 12 ? 'text-lg' : 'text-2xl'
        }`}>
          {typeof value === 'number' ? value.toLocaleString() : value}
        </span>
      </div>

      {/* Row 3: Status badge (if present) */}
      {status && statusLabel && (
        <div className="mb-2">
          <StatusBadge status={status} label={statusLabel} />
        </div>
      )}

      {/* Row 4: Title */}
      <h3 className="text-sm font-medium text-surface-600 dark:text-surface-400 mb-0.5">
        {title}
      </h3>

      {/* Row 5: Subtitle or trend label */}
      {(subtitle || trendLabel) && (
        <p className="text-xs text-surface-400 dark:text-surface-500">
          {trendLabel || subtitle}
        </p>
      )}

      {/* Sparkline chart */}
      {sparklineData && sparklineData.length > 1 && (
        <div className="mt-4 -mx-1">
          <Sparkline data={sparklineData} color={sparklineColor} />
        </div>
      )}
    </CardWrapper>
  );
}

/**
 * Grid layout helper for metric cards
 *
 * @param {Object} props - Component props
 * @param {React.ReactNode} props.children - Metric cards
 * @param {2|3|4|5|6} [props.columns=4] - Number of columns
 * @param {string} [props.className] - Additional CSS classes
 */
export function MetricCardGrid({ children, columns = 4, className = '' }) {
  const gridCols = {
    2: 'grid-cols-1 sm:grid-cols-2',
    3: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
    4: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4',
    5: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5',
    6: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6',
  };

  return (
    <div className={`grid gap-4 md:gap-5 ${gridCols[columns] || gridCols[4]} ${className}`}>
      {children}
    </div>
  );
}

// Named exports
export { MetricCardSkeleton, MetricCardError, TrendIndicator, Sparkline, StatusBadge };
