/**
 * Scanner Widget Shared Components
 *
 * Reusable building blocks for all ADR-084 vulnerability scanner widgets.
 * Follows the established widget pattern from ADR-064/077/083.
 *
 * @module components/dashboard/widgets/scanner/ScannerWidgetShared
 */

import {
  ArrowPathIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/solid';

// Severity color configuration
export const SEVERITY_COLORS = {
  CRITICAL: { hex: '#DC2626', bg: 'bg-red-100 dark:bg-red-900/30', text: 'text-red-700 dark:text-red-300', badge: 'bg-red-500 text-white', border: 'border-red-200 dark:border-red-800' },
  HIGH: { hex: '#EA580C', bg: 'bg-orange-100 dark:bg-orange-900/30', text: 'text-orange-700 dark:text-orange-300', badge: 'bg-orange-500 text-white', border: 'border-orange-200 dark:border-orange-800' },
  MEDIUM: { hex: '#F59E0B', bg: 'bg-amber-100 dark:bg-amber-900/30', text: 'text-amber-700 dark:text-amber-300', badge: 'bg-amber-500 text-white', border: 'border-amber-200 dark:border-amber-800' },
  LOW: { hex: '#3B82F6', bg: 'bg-blue-100 dark:bg-blue-900/30', text: 'text-blue-700 dark:text-blue-300', badge: 'bg-blue-500 text-white', border: 'border-blue-200 dark:border-blue-800' },
  INFO: { hex: '#6B7280', bg: 'bg-gray-100 dark:bg-gray-900/30', text: 'text-gray-700 dark:text-gray-300', badge: 'bg-gray-500 text-white', border: 'border-gray-200 dark:border-gray-800' },
};

// Alarm status colors
export const ALARM_COLORS = {
  OK: { bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-700 dark:text-green-300', dot: 'bg-green-500' },
  WARNING: { bg: 'bg-amber-100 dark:bg-amber-900/30', text: 'text-amber-700 dark:text-amber-300', dot: 'bg-amber-500' },
  ALARM: { bg: 'bg-red-100 dark:bg-red-900/30', text: 'text-red-700 dark:text-red-300', dot: 'bg-red-500' },
};

// Pipeline stage display names
export const STAGE_LABELS = {
  DISCOVERY: 'Discovery',
  EXTRACTION: 'Extraction',
  CANDIDATE_SELECTION: 'Candidates',
  LLM_ANALYSIS: 'LLM Analysis',
  VERIFICATION: 'Verification',
  DEDUP_TRIAGE: 'Dedup/Triage',
  CLEANUP: 'Cleanup',
};

// Stage status colors
export const STAGE_STATUS_COLORS = {
  complete: 'bg-green-500',
  running: 'bg-blue-500 animate-pulse',
  pending: 'bg-gray-300 dark:bg-gray-600',
  failed: 'bg-red-500',
};

/**
 * Severity badge component
 */
export function SeverityBadge({ severity, size = 'sm' }) {
  const config = SEVERITY_COLORS[severity] || SEVERITY_COLORS.INFO;
  const sizeClasses = size === 'sm' ? 'px-1.5 py-0.5 text-xs' : 'px-2 py-1 text-sm';

  return (
    <span className={`inline-flex items-center font-medium rounded ${sizeClasses} ${config.badge}`}>
      {severity}
    </span>
  );
}

/**
 * Confidence badge component
 */
export function ConfidenceBadge({ confidence }) {
  const pct = Math.round(confidence * 100);
  const colorClass = pct >= 90
    ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
    : pct >= 70
      ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300'
      : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300';

  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 text-xs font-medium rounded ${colorClass}`}>
      {pct}%
    </span>
  );
}

/**
 * Verification status badge
 */
export function VerificationBadge({ status }) {
  const configs = {
    verified_true_positive: { label: 'Verified TP', className: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' },
    verified_false_positive: { label: 'False Positive', className: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400' },
    pending: { label: 'Pending', className: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' },
    skipped: { label: 'Skipped', className: 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-500' },
  };
  const config = configs[status] || configs.pending;

  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 text-xs font-medium rounded ${config.className}`}>
      {config.label}
    </span>
  );
}

/**
 * Widget loading skeleton
 */
export function WidgetSkeleton({ className = '' }) {
  return (
    <div className={`bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 animate-pulse ${className}`}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-surface-200 dark:bg-surface-700" />
          <div className="w-32 h-5 rounded bg-surface-200 dark:bg-surface-700" />
        </div>
        <div className="w-16 h-5 rounded-full bg-surface-200 dark:bg-surface-700" />
      </div>
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="w-full h-4 rounded bg-surface-200 dark:bg-surface-700" />
        ))}
      </div>
    </div>
  );
}

/**
 * Widget error state
 */
export function WidgetError({ title, onRetry, className = '' }) {
  return (
    <div className={`bg-white dark:bg-surface-800 rounded-xl border border-red-200 dark:border-red-800 p-4 flex flex-col items-center justify-center min-h-[160px] ${className}`}>
      <ExclamationTriangleIcon className="w-8 h-8 text-red-500 mb-2" />
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
        Failed to load {title}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-lg transition-colors"
        >
          <ArrowPathIcon className="w-4 h-4" />
          Retry
        </button>
      )}
    </div>
  );
}

/**
 * Widget card wrapper
 */
export function WidgetCard({ children, title, subtitle, icon: Icon, iconColor = 'blue', onRefresh, badge, className = '' }) {
  const iconBgColors = {
    blue: 'bg-blue-100 dark:bg-blue-900/30',
    red: 'bg-red-100 dark:bg-red-900/30',
    green: 'bg-green-100 dark:bg-green-900/30',
    amber: 'bg-amber-100 dark:bg-amber-900/30',
    gray: 'bg-gray-100 dark:bg-gray-800',
  };

  const iconTextColors = {
    blue: 'text-blue-600 dark:text-blue-400',
    red: 'text-red-600 dark:text-red-400',
    green: 'text-green-600 dark:text-green-400',
    amber: 'text-amber-600 dark:text-amber-400',
    gray: 'text-gray-600 dark:text-gray-400',
  };

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        overflow-hidden h-full flex flex-col
        ${className}
      `}
      role="region"
      aria-label={title}
    >
      {/* Header */}
      <div className="p-4 border-b border-surface-200 dark:border-surface-700 flex-shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 min-w-0">
            {Icon && (
              <div className={`p-1.5 rounded-lg flex-shrink-0 ${iconBgColors[iconColor] || iconBgColors.blue}`}>
                <Icon className={`w-5 h-5 ${iconTextColors[iconColor] || iconTextColors.blue}`} />
              </div>
            )}
            <h3 className="font-semibold text-gray-900 dark:text-gray-100 truncate">
              {title}
            </h3>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {badge}
            {onRefresh && (
              <button
                onClick={onRefresh}
                className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                aria-label="Refresh"
              >
                <ArrowPathIcon className="w-4 h-4 text-gray-500" />
              </button>
            )}
          </div>
        </div>
        {subtitle && (
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{subtitle}</p>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0">
        {children}
      </div>
    </div>
  );
}

/**
 * Format duration in human-readable form
 */
export function formatDuration(ms) {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  const mins = Math.floor(ms / 60000);
  const secs = Math.floor((ms % 60000) / 1000);
  return `${mins}m ${secs}s`;
}

/**
 * Format relative time
 */
export function formatRelativeTime(isoString) {
  if (!isoString) return 'N/A';
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.floor(diffHours / 24)}d ago`;
}

/**
 * Format number with locale
 */
export function formatNumber(num) {
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return num.toLocaleString();
}
