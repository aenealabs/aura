
// Base skeleton with shimmer effect
export function Skeleton({ className = '', ...props }) {
  return (
    <div
      className={`skeleton animate-pulse ${className}`}
      {...props}
    />
  );
}

// Text skeleton
export function SkeletonText({ lines = 1, className = '' }) {
  return (
    <div className={`space-y-2 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className="h-4 rounded"
          style={{
            width: i === lines - 1 && lines > 1 ? '75%' : '100%',
          }}
        />
      ))}
    </div>
  );
}

// Circle skeleton (for avatars)
export function SkeletonCircle({ size = 'md', className = '' }) {
  const sizeClasses = {
    sm: 'w-8 h-8',
    md: 'w-10 h-10',
    lg: 'w-12 h-12',
    xl: 'w-16 h-16',
  };

  return (
    <Skeleton className={`rounded-full ${sizeClasses[size]} ${className}`} />
  );
}

// Metric card skeleton - Glass treatment
export function MetricCardSkeleton({ className = '' }) {
  return (
    <div
      className={`
        glass-card
        p-6 ${className}
      `}
    >
      {/* Icon placeholder */}
      <div className="flex items-start justify-between mb-4">
        <Skeleton className="w-10 h-10 rounded-lg" />
        <Skeleton className="w-16 h-5 rounded" />
      </div>

      {/* Value placeholder */}
      <Skeleton className="w-24 h-8 rounded mb-2" />

      {/* Label placeholder */}
      <Skeleton className="w-32 h-4 rounded mb-3" />

      {/* Trend placeholder */}
      <div className="flex items-center gap-2">
        <Skeleton className="w-4 h-4 rounded" />
        <Skeleton className="w-20 h-4 rounded" />
      </div>
    </div>
  );
}

// Chart skeleton - Glass treatment
export function ChartSkeleton({ className = '' }) {
  return (
    <div
      className={`
        glass-card
        p-6 ${className}
      `}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <Skeleton className="w-32 h-6 rounded" />
        <Skeleton className="w-24 h-8 rounded" />
      </div>

      {/* Chart area */}
      <div className="relative h-48">
        {/* Y-axis labels */}
        <div className="absolute left-0 top-0 bottom-0 flex flex-col justify-between">
          <Skeleton className="w-8 h-3 rounded" />
          <Skeleton className="w-6 h-3 rounded" />
          <Skeleton className="w-8 h-3 rounded" />
          <Skeleton className="w-6 h-3 rounded" />
          <Skeleton className="w-8 h-3 rounded" />
        </div>

        {/* Chart bars or lines */}
        <div className="ml-12 h-full flex items-end justify-between gap-2">
          {Array.from({ length: 7 }).map((_, i) => (
            <Skeleton
              key={i}
              className="flex-1 rounded-t"
              style={{ height: `${30 + Math.random() * 60}%` }}
            />
          ))}
        </div>
      </div>

      {/* X-axis labels */}
      <div className="flex justify-between mt-4 ml-12">
        {Array.from({ length: 7 }).map((_, i) => (
          <Skeleton key={i} className="w-8 h-3 rounded" />
        ))}
      </div>
    </div>
  );
}

// Activity item skeleton
export function ActivityItemSkeleton({ className = '' }) {
  return (
    <div className={`flex items-start gap-4 p-4 ${className}`}>
      {/* Icon */}
      <Skeleton className="w-8 h-8 rounded-full flex-shrink-0" />

      {/* Content */}
      <div className="flex-1 min-w-0">
        <Skeleton className="w-3/4 h-4 rounded mb-2" />
        <Skeleton className="w-1/2 h-3 rounded mb-2" />
        <Skeleton className="w-24 h-3 rounded" />
      </div>

      {/* Timestamp */}
      <Skeleton className="w-16 h-4 rounded flex-shrink-0" />
    </div>
  );
}

// Activity feed skeleton - Glass treatment
export function ActivityFeedSkeleton({ count = 5, className = '' }) {
  return (
    <div
      className={`
        glass-card overflow-hidden
        ${className}
      `}
    >
      {/* Header */}
      <div className="px-6 py-4 border-b border-surface-100/50 dark:border-surface-700/30">
        <Skeleton className="w-32 h-6 rounded" />
      </div>

      {/* Items */}
      <div className="divide-y divide-surface-100/50 dark:divide-surface-700/30">
        {Array.from({ length: count }).map((_, i) => (
          <ActivityItemSkeleton key={i} />
        ))}
      </div>
    </div>
  );
}

// Table row skeleton
export function TableRowSkeleton({ columns = 4, className = '' }) {
  return (
    <tr className={className}>
      {Array.from({ length: columns }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <Skeleton
            className="h-4 rounded"
            style={{ width: `${60 + Math.random() * 30}%` }}
          />
        </td>
      ))}
    </tr>
  );
}

// Table skeleton - Glass treatment
export function TableSkeleton({ rows = 5, columns = 4, className = '' }) {
  return (
    <div
      className={`
        glass-card
        overflow-hidden ${className}
      `}
    >
      <table className="w-full">
        <thead>
          <tr className="bg-white/50 dark:bg-surface-800/30">
            {Array.from({ length: columns }).map((_, i) => (
              <th key={i} className="px-4 py-3 text-left">
                <Skeleton className="h-4 w-20 rounded" />
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-surface-100/50 dark:divide-surface-700/30">
          {Array.from({ length: rows }).map((_, i) => (
            <TableRowSkeleton key={i} columns={columns} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Full page loading skeleton
export function PageSkeleton({ className = '' }) {
  return (
    <div className={`p-6 space-y-6 ${className}`}>
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <Skeleton className="w-48 h-8 rounded mb-2" />
          <Skeleton className="w-72 h-4 rounded" />
        </div>
        <Skeleton className="w-32 h-10 rounded-lg" />
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {Array.from({ length: 4 }).map((_, i) => (
          <MetricCardSkeleton key={i} />
        ))}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartSkeleton />
        <ChartSkeleton />
      </div>

      {/* Activity feed */}
      <ActivityFeedSkeleton count={5} />
    </div>
  );
}

export default Skeleton;
