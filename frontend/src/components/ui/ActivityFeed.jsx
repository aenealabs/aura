import { useState, useCallback, memo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ShieldCheckIcon,
  ExclamationTriangleIcon,
  BugAntIcon,
  CpuChipIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  DocumentMagnifyingGlassIcon,
  CodeBracketIcon,
  ArrowPathIcon,
  ChevronRightIcon,
  BellIcon,
  FolderIcon,
} from '@heroicons/react/24/outline';
import { ActivityFeedSkeleton } from './LoadingSkeleton';
import { getActivityRoute } from '../../services/activityApi';

// Activity type configurations with navigation targets
const activityTypes = {
  vulnerability_detected: {
    icon: BugAntIcon,
    color: 'critical',
    label: 'Vulnerability Detected',
    navigable: true,
  },
  patch_generated: {
    icon: CodeBracketIcon,
    color: 'aura',
    label: 'Patch Generated',
    navigable: true,
  },
  patch_approved: {
    icon: CheckCircleIcon,
    color: 'olive',
    label: 'Patch Approved',
    navigable: true,
  },
  patch_rejected: {
    icon: XCircleIcon,
    color: 'critical',
    label: 'Patch Rejected',
    navigable: true,
  },
  patch_deployed: {
    icon: ShieldCheckIcon,
    color: 'olive',
    label: 'Patch Deployed',
    navigable: true,
  },
  scan_started: {
    icon: DocumentMagnifyingGlassIcon,
    color: 'aura',
    label: 'Scan Started',
    navigable: true,
  },
  scan_completed: {
    icon: CheckCircleIcon,
    color: 'olive',
    label: 'Scan Completed',
    navigable: true,
  },
  agent_started: {
    icon: CpuChipIcon,
    color: 'aura',
    label: 'Agent Started',
    navigable: true,
  },
  agent_completed: {
    icon: CheckCircleIcon,
    color: 'olive',
    label: 'Agent Completed',
    navigable: true,
  },
  agent_failed: {
    icon: XCircleIcon,
    color: 'critical',
    label: 'Agent Failed',
    navigable: true,
  },
  anomaly_detected: {
    icon: ExclamationTriangleIcon,
    color: 'warning',
    label: 'Anomaly Detected',
    navigable: true,
  },
  alert_triggered: {
    icon: BellIcon,
    color: 'critical',
    label: 'Alert Triggered',
    navigable: true,
  },
  incident_opened: {
    icon: ExclamationTriangleIcon,
    color: 'critical',
    label: 'Incident Opened',
    navigable: true,
  },
  incident_resolved: {
    icon: CheckCircleIcon,
    color: 'olive',
    label: 'Incident Resolved',
    navigable: true,
  },
  repository_connected: {
    icon: FolderIcon,
    color: 'olive',
    label: 'Repository Connected',
    navigable: true,
  },
  repository_updated: {
    icon: FolderIcon,
    color: 'aura',
    label: 'Repository Updated',
    navigable: true,
  },
  pending: {
    icon: ClockIcon,
    color: 'warning',
    label: 'Pending Review',
    navigable: true,
  },
  in_progress: {
    icon: ArrowPathIcon,
    color: 'aura',
    label: 'In Progress',
    navigable: true,
  },
};

// Severity badge colors
const severityColors = {
  critical: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
  high: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
  medium: 'bg-warning-100/70 text-warning-600 dark:bg-warning-900/20 dark:text-warning-500',
  low: 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-400',
};

// Icon background colors
const iconBgColors = {
  critical: 'bg-critical-100 text-critical-600 dark:bg-critical-900/30 dark:text-critical-400',
  warning: 'bg-warning-100 text-warning-600 dark:bg-warning-900/30 dark:text-warning-400',
  olive: 'bg-olive-100 text-olive-600 dark:bg-olive-900/30 dark:text-olive-400',
  aura: 'bg-aura-100 text-aura-600 dark:bg-aura-900/30 dark:text-aura-400',
  surface: 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-400',
};

// Format relative time
function formatRelativeTime(date) {
  const now = new Date();
  const then = new Date(date);
  const seconds = Math.floor((now - then) / 1000);

  if (seconds < 60) return 'Just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;

  return then.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });
}

// Format full timestamp for tooltip
function formatFullTimestamp(date) {
  const then = new Date(date);
  return then.toLocaleString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

// Individual activity item with enhanced interactivity
// Memoized to prevent re-renders when parent state changes but item props are stable
const ActivityItem = memo(function ActivityItem({
  id: _id,
  type,
  title,
  description,
  timestamp,
  severity,
  metadata,
  isLast,
  isRead,
  onClick,
  onNavigate,
  isNavigable,
}) {
  const config = activityTypes[type] || activityTypes.in_progress;
  const Icon = config.icon;
  const canNavigate = isNavigable && config.navigable;

  // Handle keyboard navigation
  const handleKeyDown = useCallback((event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      if (canNavigate && onNavigate) {
        onNavigate();
      } else if (onClick) {
        onClick();
      }
    }
  }, [canNavigate, onClick, onNavigate]);

  // Handle click
  const handleClick = useCallback(() => {
    if (canNavigate && onNavigate) {
      onNavigate();
    } else if (onClick) {
      onClick();
    }
  }, [canNavigate, onClick, onNavigate]);

  return (
    <div
      role={canNavigate ? 'button' : 'article'}
      tabIndex={canNavigate ? 0 : undefined}
      aria-label={`${config.label}: ${title}. ${description || ''} ${severity ? `Severity: ${severity}.` : ''} ${formatRelativeTime(timestamp)}`}
      className={`
        relative flex gap-4 p-4
        ${canNavigate
          ? `cursor-pointer
             hover:bg-surface-50 dark:hover:bg-surface-700
             focus:outline-none focus:ring-2 focus:ring-inset focus:ring-aura-500/40
             focus-visible:bg-white/60 dark:focus-visible:bg-white/[0.04]
             active:bg-white/80 dark:active:bg-white/[0.06]`
          : ''
        }
        ${!isRead ? 'bg-aura-50/30 dark:bg-aura-900/10' : ''}
        transition-all duration-200 ease-[var(--ease-tahoe)]
        group
      `}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
    >
      {/* Timeline connector */}
      {!isLast && (
        <div
          className="
            absolute left-8 top-14 bottom-0 w-px
            bg-surface-200 dark:bg-surface-700
          "
          aria-hidden="true"
        />
      )}

      {/* Unread indicator */}
      {!isRead && (
        <div
          className="absolute left-1 top-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-aura-500"
          aria-label="Unread"
        />
      )}

      {/* Icon */}
      <div
        className={`
          relative z-10 flex-shrink-0
          w-8 h-8 rounded-full flex items-center justify-center
          ${iconBgColors[config.color]}
          transition-transform duration-150
          ${canNavigate ? 'group-hover:scale-110' : ''}
        `}
      >
        <Icon className="w-4 h-4" aria-hidden="true" />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        {/* Header row */}
        <div className="flex items-start justify-between gap-2 mb-1">
          <h4 className="text-sm font-medium text-surface-900 dark:text-surface-100 truncate">
            {title}
          </h4>
          <span
            className="text-xs text-surface-400 dark:text-surface-500 whitespace-nowrap flex-shrink-0"
            title={formatFullTimestamp(timestamp)}
          >
            {formatRelativeTime(timestamp)}
          </span>
        </div>

        {/* Description */}
        {description && (
          <p className="text-sm text-surface-600 dark:text-surface-400 mb-2 line-clamp-2">
            {description}
          </p>
        )}

        {/* Metadata row */}
        <div className="flex items-center flex-wrap gap-2">
          {/* Activity type badge */}
          <span
            className={`
              inline-flex items-center px-2 py-0.5 rounded text-xs font-medium
              ${iconBgColors[config.color]}
            `}
          >
            {config.label}
          </span>

          {/* Severity badge */}
          {severity && (
            <span
              className={`
                inline-flex items-center px-2 py-0.5 rounded text-xs font-medium uppercase
                ${severityColors[severity] || severityColors.low}
              `}
            >
              {severity}
            </span>
          )}

          {/* Additional metadata */}
          {metadata?.file && (
            <span className="text-xs font-mono text-surface-500 dark:text-surface-400 truncate max-w-[200px]">
              {metadata.file}
            </span>
          )}

          {metadata?.agent && (
            <span className="text-xs text-surface-500 dark:text-surface-400">
              Agent: {metadata.agent}
            </span>
          )}

          {metadata?.repository && (
            <span className="text-xs text-surface-500 dark:text-surface-400">
              Repo: {metadata.repository}
            </span>
          )}
        </div>
      </div>

      {/* Navigation indicator */}
      {canNavigate && (
        <div className="flex-shrink-0 flex items-center self-center">
          <ChevronRightIcon
            className="w-5 h-5 text-surface-300 dark:text-surface-600
                       group-hover:text-surface-500 dark:group-hover:text-surface-400
                       group-hover:translate-x-0.5
                       transition-all duration-150"
            aria-hidden="true"
          />
        </div>
      )}
    </div>
  );
});

// Main ActivityFeed component with navigation support
export default function ActivityFeed({
  activities = [],
  title = 'Recent Activity',
  loading = false,
  maxItems = 10,
  onItemClick,
  onLoadMore,
  hasMore = false,
  loadingMore = false,
  emptyMessage = 'No recent activity',
  className = '',
  enableNavigation = true,
  onMarkAsRead,
}) {
  const [expanded, setExpanded] = useState(false);
  const navigate = useNavigate();

  // Handle activity item navigation
  const handleActivityNavigation = useCallback((activity) => {
    // Mark as read if handler provided
    if (onMarkAsRead && !activity.isRead) {
      onMarkAsRead(activity.id);
    }

    // Get the appropriate route for this activity
    const route = getActivityRoute(activity);

    // Navigate to the route
    navigate(route);
  }, [navigate, onMarkAsRead]);

  // Handle activity item click (non-navigation)
  const handleActivityClick = useCallback((activity) => {
    if (onItemClick) {
      onItemClick(activity);
    }
  }, [onItemClick]);

  if (loading) {
    return <ActivityFeedSkeleton count={5} className={className} />;
  }

  const displayedActivities = expanded ? activities : activities.slice(0, maxItems);

  return (
    <div
      className={`
        glass-card overflow-hidden
        ${className}
      `}
      role="feed"
      aria-label={title}
    >
      {/* Header */}
      <div className="px-6 py-4 border-b border-surface-100/50 dark:border-surface-700/30">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
            {title}
          </h3>
          {activities.length > 0 && (
            <span className="text-sm text-surface-500 dark:text-surface-400">
              {activities.length} events
            </span>
          )}
        </div>
      </div>

      {/* Activity list */}
      {activities.length === 0 ? (
        <div className="p-8 text-center">
          <ClockIcon className="w-12 h-12 mx-auto text-surface-300 dark:text-surface-600 mb-3" aria-hidden="true" />
          <p className="text-surface-500 dark:text-surface-400">{emptyMessage}</p>
        </div>
      ) : (
        <div
          className="divide-y divide-surface-100/50 dark:divide-surface-700/30"
          role="list"
        >
          {displayedActivities.map((activity, index) => (
            <ActivityItem
              key={activity.id || index}
              {...activity}
              isLast={index === displayedActivities.length - 1}
              onClick={() => handleActivityClick(activity)}
              onNavigate={enableNavigation ? () => handleActivityNavigation(activity) : undefined}
              isNavigable={enableNavigation}
            />
          ))}
        </div>
      )}

      {/* Footer with expand/load more */}
      {(activities.length > maxItems || hasMore) && (
        <div className="px-6 py-3 border-t border-surface-100/50 dark:border-surface-700/30">
          {hasMore ? (
            <button
              onClick={onLoadMore}
              disabled={loadingMore}
              className="
                w-full py-2.5 text-sm font-medium rounded-xl
                text-aura-600 dark:text-aura-400
                hover:bg-surface-50 dark:hover:bg-surface-700
                disabled:opacity-50 disabled:cursor-not-allowed
                focus:outline-none focus:ring-2 focus:ring-aura-500/30
                transition-all duration-200 ease-[var(--ease-tahoe)]
              "
              aria-label={loadingMore ? 'Loading more activities...' : 'Load more activities'}
            >
              {loadingMore ? (
                <span className="flex items-center justify-center gap-2">
                  <ArrowPathIcon className="w-4 h-4 animate-spin" aria-hidden="true" />
                  Loading...
                </span>
              ) : (
                'Load More'
              )}
            </button>
          ) : activities.length > maxItems && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="
                w-full py-2.5 text-sm font-medium rounded-xl
                text-aura-600 dark:text-aura-400
                hover:bg-surface-50 dark:hover:bg-surface-700
                focus:outline-none focus:ring-2 focus:ring-aura-500/30
                transition-all duration-200 ease-[var(--ease-tahoe)]
              "
              aria-expanded={expanded}
              aria-label={expanded ? 'Show fewer activities' : `Show all ${activities.length} activities`}
            >
              {expanded ? 'Show Less' : `Show All (${activities.length})`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// Compact activity feed for sidebars or smaller spaces
export function ActivityFeedCompact({
  activities = [],
  maxItems = 5,
  className = '',
  enableNavigation = true,
  onItemClick,
}) {
  const navigate = useNavigate();

  const handleItemClick = useCallback((activity) => {
    if (onItemClick) {
      onItemClick(activity);
    }
    if (enableNavigation) {
      const route = getActivityRoute(activity);
      navigate(route);
    }
  }, [navigate, enableNavigation, onItemClick]);

  const handleKeyDown = useCallback((event,activity) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      handleItemClick(activity);
    }
  }, [handleItemClick]);

  return (
    <div className={`space-y-3 ${className}`} role="list" aria-label="Recent activities">
      {activities.slice(0, maxItems).map((activity, index) => {
        const config = activityTypes[activity.type] || activityTypes.in_progress;
        const Icon = config.icon;

        return (
          <div
            key={activity.id || index}
            role={enableNavigation ? 'button' : 'listitem'}
            tabIndex={enableNavigation ? 0 : undefined}
            className={`
              flex items-start gap-3 p-2 rounded-xl
              ${enableNavigation
                ? `cursor-pointer
                   hover:bg-surface-50 dark:hover:bg-surface-700
                   focus:outline-none focus:ring-2 focus:ring-aura-500/30
                   active:bg-white/80 dark:active:bg-white/[0.08]`
                : ''
              }
              transition-all duration-200 ease-[var(--ease-tahoe)]
              group
            `}
            onClick={() => enableNavigation && handleItemClick(activity)}
            onKeyDown={(e) => enableNavigation && handleKeyDown(e,activity)}
            aria-label={`${config.label}: ${activity.title}`}
          >
            <div
              className={`
                flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center
                ${iconBgColors[config.color]}
                transition-transform duration-150
                ${enableNavigation ? 'group-hover:scale-110' : ''}
              `}
            >
              <Icon className="w-3 h-3" aria-hidden="true" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-surface-700 dark:text-surface-300 truncate">
                {activity.title}
              </p>
              <p className="text-xs text-surface-400 dark:text-surface-500">
                {formatRelativeTime(activity.timestamp)}
              </p>
            </div>
            {enableNavigation && (
              <ChevronRightIcon
                className="w-4 h-4 text-surface-300 dark:text-surface-600
                           group-hover:text-surface-500 dark:group-hover:text-surface-400
                           flex-shrink-0 self-center
                           transition-colors duration-150"
                aria-hidden="true"
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

// Export activity types for external use
export { activityTypes, severityColors, iconBgColors, formatRelativeTime };
