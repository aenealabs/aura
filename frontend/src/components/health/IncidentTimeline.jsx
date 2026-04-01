import { useState } from 'react';
import {
  ExclamationCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  CheckCircleIcon,
  ClockIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  EyeIcon,
} from '@heroicons/react/24/outline';
import { Skeleton } from '../ui/LoadingSkeleton';
import { formatRelativeTime, getSeverityColor, getIncidentStatusColor } from '../../services/customerHealthApi';

/**
 * IncidentTimeline Component
 *
 * Chronological display of incidents with filtering, pagination, and actions.
 * Features:
 * - Color-coded severity badges
 * - Status indicators (active, acknowledged, resolved)
 * - Acknowledge and resolve actions
 * - Pagination support
 * - Expandable incident details
 * - Accessible with keyboard navigation
 *
 * Follows Apple design with clean typography and subtle visual hierarchy.
 */

const SEVERITY_CONFIG = {
  critical: {
    icon: ExclamationCircleIcon,
    color: '#DC2626',
    bgColor: 'bg-critical-100 dark:bg-critical-900/30',
    textColor: 'text-critical-700 dark:text-critical-400',
    borderColor: 'border-critical-200 dark:border-critical-800',
  },
  high: {
    icon: ExclamationTriangleIcon,
    color: '#EA580C',
    bgColor: 'bg-warning-100 dark:bg-warning-900/30',
    textColor: 'text-warning-700 dark:text-warning-400',
    borderColor: 'border-warning-200 dark:border-warning-800',
  },
  medium: {
    icon: ExclamationTriangleIcon,
    color: '#F59E0B',
    bgColor: 'bg-warning-100 dark:bg-warning-900/30',
    textColor: 'text-warning-700 dark:text-warning-400',
    borderColor: 'border-warning-200 dark:border-warning-800',
  },
  low: {
    icon: InformationCircleIcon,
    color: '#3B82F6',
    bgColor: 'bg-info-100 dark:bg-info-900/30',
    textColor: 'text-info-700 dark:text-info-400',
    borderColor: 'border-info-200 dark:border-info-800',
  },
};

const STATUS_CONFIG = {
  active: {
    label: 'Active',
    dotColor: 'bg-critical-500',
    pulse: true,
  },
  acknowledged: {
    label: 'Acknowledged',
    dotColor: 'bg-warning-500',
    pulse: false,
  },
  resolved: {
    label: 'Resolved',
    dotColor: 'bg-olive-500',
    pulse: false,
  },
};

function IncidentCard({
  incident,
  onAcknowledge,
  onResolve,
  _onViewDetails,
  isExpanded,
  onToggleExpand,
}) {
  const [acknowledging, setAcknowledging] = useState(false);
  const [resolving, setResolving] = useState(false);

  const severityConfig = SEVERITY_CONFIG[incident.severity] || SEVERITY_CONFIG.low;
  const statusConfig = STATUS_CONFIG[incident.status] || STATUS_CONFIG.active;
  const SeverityIcon = severityConfig.icon;

  const handleAcknowledge = async () => {
    if (acknowledging) return;
    setAcknowledging(true);
    try {
      await onAcknowledge?.(incident.id);
    } finally {
      setAcknowledging(false);
    }
  };

  const handleResolve = async () => {
    if (resolving) return;
    setResolving(true);
    try {
      await onResolve?.(incident.id);
    } finally {
      setResolving(false);
    }
  };

  return (
    <div
      className={`
        relative bg-white dark:bg-surface-800 rounded-lg border
        transition-all duration-200 hover:shadow-md
        ${severityConfig.borderColor}
        ${incident.status === 'active' ? 'border-l-4' : 'border-l'}
      `}
      style={{
        borderLeftColor: incident.status === 'active' ? severityConfig.color : undefined,
      }}
    >
      {/* Timeline connector dot */}
      <div
        className={`
          absolute -left-[21px] top-6 w-3 h-3 rounded-full border-2 border-white dark:border-surface-900
          ${statusConfig.dotColor}
          ${statusConfig.pulse ? 'animate-pulse' : ''}
        `}
      />

      <div className="p-4">
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3 min-w-0">
            <div
              className={`
                p-2 rounded-lg flex-shrink-0
                ${severityConfig.bgColor}
              `}
            >
              <SeverityIcon
                className="w-5 h-5"
                style={{ color: severityConfig.color }}
              />
            </div>

            <div className="min-w-0">
              <h4 className="font-medium text-surface-900 dark:text-surface-100 leading-tight">
                {incident.title}
              </h4>

              <div className="flex flex-wrap items-center gap-2 mt-1.5">
                {/* Severity badge */}
                <span
                  className={`
                    inline-flex items-center px-2 py-0.5 rounded text-xs font-medium capitalize
                    ${getSeverityColor(incident.severity)}
                  `}
                >
                  {incident.severity}
                </span>

                {/* Status badge */}
                <span
                  className={`
                    inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium
                    ${getIncidentStatusColor(incident.status)}
                  `}
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${statusConfig.dotColor}`}
                  />
                  {statusConfig.label}
                </span>

                {/* Component */}
                {incident.component && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-400">
                    {incident.component}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Time */}
          <div className="flex-shrink-0 text-right">
            <div className="flex items-center gap-1 text-xs text-surface-500 dark:text-surface-400">
              <ClockIcon className="w-3.5 h-3.5" />
              <span>{formatRelativeTime(incident.started_at)}</span>
            </div>
          </div>
        </div>

        {/* Description (always visible) */}
        <p className="mt-3 text-sm text-surface-600 dark:text-surface-400 line-clamp-2">
          {incident.description}
        </p>

        {/* Expanded content */}
        {isExpanded && (
          <div className="mt-4 pt-4 border-t border-surface-100 dark:border-surface-700 space-y-3">
            {/* Impact */}
            {incident.impact && (
              <div>
                <h5 className="text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wide">
                  Impact
                </h5>
                <p className="mt-1 text-sm text-surface-700 dark:text-surface-300">
                  {incident.impact}
                </p>
              </div>
            )}

            {/* Timeline */}
            <div className="space-y-2">
              <h5 className="text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wide">
                Timeline
              </h5>
              <div className="space-y-1.5 text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-surface-500 dark:text-surface-400 w-24">Started:</span>
                  <span className="text-surface-700 dark:text-surface-300">
                    {new Date(incident.started_at).toLocaleString()}
                  </span>
                </div>
                {incident.acknowledged_at && (
                  <div className="flex items-center gap-2">
                    <span className="text-surface-500 dark:text-surface-400 w-24">Acknowledged:</span>
                    <span className="text-surface-700 dark:text-surface-300">
                      {new Date(incident.acknowledged_at).toLocaleString()}
                      {incident.acknowledged_by && ` by ${incident.acknowledged_by}`}
                    </span>
                  </div>
                )}
                {incident.resolved_at && (
                  <div className="flex items-center gap-2">
                    <span className="text-surface-500 dark:text-surface-400 w-24">Resolved:</span>
                    <span className="text-surface-700 dark:text-surface-300">
                      {new Date(incident.resolved_at).toLocaleString()}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Resolution */}
            {incident.resolution && (
              <div>
                <h5 className="text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wide">
                  Resolution
                </h5>
                <p className="mt-1 text-sm text-surface-700 dark:text-surface-300">
                  {incident.resolution}
                </p>
              </div>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="mt-4 flex items-center justify-between">
          <button
            type="button"
            onClick={() => onToggleExpand?.(incident.id)}
            className="flex items-center gap-1 text-xs text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300 font-medium"
          >
            <EyeIcon className="w-4 h-4" />
            {isExpanded ? 'Show less' : 'View details'}
          </button>

          <div className="flex items-center gap-2">
            {incident.status === 'active' && onAcknowledge && (
              <button
                type="button"
                onClick={handleAcknowledge}
                disabled={acknowledging}
                className="
                  px-3 py-1.5 text-xs font-medium rounded-md
                  bg-warning-100 text-warning-700 hover:bg-warning-200
                  dark:bg-warning-900/30 dark:text-warning-400 dark:hover:bg-warning-900/50
                  disabled:opacity-50 disabled:cursor-not-allowed
                  transition-colors duration-150
                "
              >
                {acknowledging ? 'Acknowledging...' : 'Acknowledge'}
              </button>
            )}

            {(incident.status === 'active' || incident.status === 'acknowledged') && onResolve && (
              <button
                type="button"
                onClick={handleResolve}
                disabled={resolving}
                className="
                  px-3 py-1.5 text-xs font-medium rounded-md
                  bg-olive-100 text-olive-700 hover:bg-olive-200
                  dark:bg-olive-900/30 dark:text-olive-400 dark:hover:bg-olive-900/50
                  disabled:opacity-50 disabled:cursor-not-allowed
                  transition-colors duration-150
                "
              >
                {resolving ? 'Resolving...' : 'Resolve'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function IncidentTimelineSkeleton({ count = 3 }) {
  return (
    <div className="space-y-4 pl-6 border-l-2 border-surface-200 dark:border-surface-700 ml-2">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="relative bg-white dark:bg-surface-800 rounded-lg border border-surface-200 dark:border-surface-700 p-4">
          <div className="absolute -left-[21px] top-6 w-3 h-3 rounded-full bg-surface-300 dark:bg-surface-600 border-2 border-white dark:border-surface-900" />
          <div className="flex items-start gap-3">
            <Skeleton className="w-9 h-9 rounded-lg" />
            <div className="flex-1">
              <Skeleton className="w-3/4 h-5 rounded mb-2" />
              <div className="flex gap-2">
                <Skeleton className="w-16 h-5 rounded" />
                <Skeleton className="w-20 h-5 rounded" />
              </div>
            </div>
            <Skeleton className="w-20 h-4 rounded" />
          </div>
          <Skeleton className="w-full h-4 rounded mt-3" />
          <Skeleton className="w-2/3 h-4 rounded mt-1" />
        </div>
      ))}
    </div>
  );
}

export function IncidentTimeline({
  incidents = [],
  total = 0,
  page = 0,
  hasMore = false,
  loading = false,
  onAcknowledge,
  onResolve,
  onViewDetails,
  onNextPage,
  onPrevPage,
  emptyMessage = 'No incidents to display',
  className = '',
}) {
  const [expandedId, setExpandedId] = useState(null);

  const handleToggleExpand = (incidentId) => {
    setExpandedId(current => current === incidentId ? null : incidentId);
  };

  if (loading) {
    return (
      <div className={className}>
        <IncidentTimelineSkeleton count={3} />
      </div>
    );
  }

  if (!incidents || incidents.length === 0) {
    return (
      <div
        className={`
          bg-olive-50 dark:bg-olive-900/20 border border-olive-200 dark:border-olive-800
          rounded-lg p-6 text-center
          ${className}
        `}
      >
        <CheckCircleIcon className="w-10 h-10 text-olive-500 mx-auto mb-3" />
        <p className="text-olive-700 dark:text-olive-400 font-medium">
          {emptyMessage}
        </p>
        <p className="text-olive-600 dark:text-olive-500 text-sm mt-1">
          All systems operating normally
        </p>
      </div>
    );
  }

  return (
    <div className={className}>
      {/* Timeline */}
      <div className="space-y-4 pl-6 border-l-2 border-surface-200 dark:border-surface-700 ml-2">
        {incidents.map((incident) => (
          <IncidentCard
            key={incident.id}
            incident={incident}
            onAcknowledge={onAcknowledge}
            onResolve={onResolve}
            onViewDetails={onViewDetails}
            isExpanded={expandedId === incident.id}
            onToggleExpand={handleToggleExpand}
          />
        ))}
      </div>

      {/* Pagination */}
      {(onNextPage || onPrevPage) && (
        <div className="flex items-center justify-between mt-6 pt-4 border-t border-surface-200 dark:border-surface-700">
          <div className="text-sm text-surface-500 dark:text-surface-400">
            Showing {page * 10 + 1} - {Math.min((page + 1) * 10, total)} of {total} incidents
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onPrevPage}
              disabled={page === 0}
              className="
                p-2 rounded-lg border border-surface-200 dark:border-surface-700
                text-surface-600 dark:text-surface-400
                hover:bg-surface-50 dark:hover:bg-surface-700
                disabled:opacity-50 disabled:cursor-not-allowed
                transition-colors duration-150
              "
              aria-label="Previous page"
            >
              <ChevronLeftIcon className="w-5 h-5" />
            </button>

            <span className="px-3 py-1 text-sm text-surface-700 dark:text-surface-300">
              Page {page + 1}
            </span>

            <button
              type="button"
              onClick={onNextPage}
              disabled={!hasMore}
              className="
                p-2 rounded-lg border border-surface-200 dark:border-surface-700
                text-surface-600 dark:text-surface-400
                hover:bg-surface-50 dark:hover:bg-surface-700
                disabled:opacity-50 disabled:cursor-not-allowed
                transition-colors duration-150
              "
              aria-label="Next page"
            >
              <ChevronRightIcon className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * IncidentSummary
 *
 * Compact summary of active incidents for dashboard widgets.
 */
export function IncidentSummary({ incidents = [], className = '' }) {
  const activeCount = incidents.filter(i => i.status === 'active').length;
  const criticalCount = incidents.filter(i => i.severity === 'critical' && i.status !== 'resolved').length;

  if (incidents.length === 0) {
    return (
      <div className={`flex items-center gap-2 text-olive-600 dark:text-olive-400 ${className}`}>
        <CheckCircleIcon className="w-5 h-5" />
        <span className="text-sm font-medium">No active incidents</span>
      </div>
    );
  }

  return (
    <div className={`flex items-center gap-4 ${className}`}>
      {criticalCount > 0 && (
        <div className="flex items-center gap-1.5 text-critical-600 dark:text-critical-400">
          <ExclamationCircleIcon className="w-5 h-5" />
          <span className="text-sm font-medium">{criticalCount} critical</span>
        </div>
      )}

      <div className="flex items-center gap-1.5 text-warning-600 dark:text-warning-400">
        <ExclamationTriangleIcon className="w-5 h-5" />
        <span className="text-sm font-medium">{activeCount} active</span>
      </div>
    </div>
  );
}

export default IncidentTimeline;
