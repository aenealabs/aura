/**
 * Project Aura - Activity Detail View
 *
 * Generic activity detail view for items without specific pages.
 * Displays full activity metadata, timestamps, and related entities.
 */

import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeftIcon,
  ClockIcon,
  ShieldCheckIcon,
  ExclamationTriangleIcon,
  BugAntIcon,
  CpuChipIcon,
  CheckCircleIcon,
  XCircleIcon,
  DocumentMagnifyingGlassIcon,
  CodeBracketIcon,
  ArrowPathIcon,
  BellIcon,
  FolderIcon,
  TagIcon,
  UserIcon,
  LinkIcon,
  DocumentTextIcon,
  ChevronRightIcon,
  EyeIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';
import { PageSkeleton } from './ui/LoadingSkeleton';
import { Button } from './ui/Button';



// Activity type configurations (matching ActivityFeed)
const activityTypeConfig = {
  vulnerability_detected: {
    icon: BugAntIcon,
    color: 'critical',
    label: 'Vulnerability Detected',
  },
  patch_generated: {
    icon: CodeBracketIcon,
    color: 'aura',
    label: 'Patch Generated',
  },
  patch_approved: {
    icon: CheckCircleIcon,
    color: 'olive',
    label: 'Patch Approved',
  },
  patch_rejected: {
    icon: XCircleIcon,
    color: 'critical',
    label: 'Patch Rejected',
  },
  patch_deployed: {
    icon: ShieldCheckIcon,
    color: 'olive',
    label: 'Patch Deployed',
  },
  scan_started: {
    icon: DocumentMagnifyingGlassIcon,
    color: 'aura',
    label: 'Scan Started',
  },
  scan_completed: {
    icon: CheckCircleIcon,
    color: 'olive',
    label: 'Scan Completed',
  },
  agent_started: {
    icon: CpuChipIcon,
    color: 'aura',
    label: 'Agent Started',
  },
  agent_completed: {
    icon: CheckCircleIcon,
    color: 'olive',
    label: 'Agent Completed',
  },
  agent_failed: {
    icon: XCircleIcon,
    color: 'critical',
    label: 'Agent Failed',
  },
  anomaly_detected: {
    icon: ExclamationTriangleIcon,
    color: 'warning',
    label: 'Anomaly Detected',
  },
  alert_triggered: {
    icon: BellIcon,
    color: 'critical',
    label: 'Alert Triggered',
  },
  incident_opened: {
    icon: ExclamationTriangleIcon,
    color: 'critical',
    label: 'Incident Opened',
  },
  incident_resolved: {
    icon: CheckCircleIcon,
    color: 'olive',
    label: 'Incident Resolved',
  },
  repository_connected: {
    icon: FolderIcon,
    color: 'olive',
    label: 'Repository Connected',
  },
  repository_updated: {
    icon: FolderIcon,
    color: 'aura',
    label: 'Repository Updated',
  },
  pending: {
    icon: ClockIcon,
    color: 'warning',
    label: 'Pending Review',
  },
  in_progress: {
    icon: ArrowPathIcon,
    color: 'aura',
    label: 'In Progress',
  },
};

// Color class mappings
const colorClasses = {
  critical: {
    bg: 'bg-critical-100 dark:bg-critical-900/30',
    text: 'text-critical-700 dark:text-critical-400',
    border: 'border-critical-200 dark:border-critical-800',
    icon: 'text-critical-600 dark:text-critical-400',
  },
  warning: {
    bg: 'bg-warning-100 dark:bg-warning-900/30',
    text: 'text-warning-700 dark:text-warning-400',
    border: 'border-warning-200 dark:border-warning-800',
    icon: 'text-warning-600 dark:text-warning-400',
  },
  olive: {
    bg: 'bg-olive-100 dark:bg-olive-900/30',
    text: 'text-olive-700 dark:text-olive-400',
    border: 'border-olive-200 dark:border-olive-800',
    icon: 'text-olive-600 dark:text-olive-400',
  },
  aura: {
    bg: 'bg-aura-100 dark:bg-aura-900/30',
    text: 'text-aura-700 dark:text-aura-400',
    border: 'border-aura-200 dark:border-aura-800',
    icon: 'text-aura-600 dark:text-aura-400',
  },
};

// Severity badge configurations
const severityConfig = {
  critical: {
    label: 'Critical',
    classes: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
  },
  high: {
    label: 'High',
    classes: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
  },
  medium: {
    label: 'Medium',
    classes: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
  },
  low: {
    label: 'Low',
    classes: 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-400',
  },
};

// Format timestamp with full detail
function formatFullTimestamp(date) {
  if (!date) return 'N/A';
  const d = new Date(date);
  return d.toLocaleString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZoneName: 'short',
  });
}

// Format relative time
function formatRelativeTime(date) {
  if (!date) return 'N/A';
  const now = new Date();
  const then = new Date(date);
  const seconds = Math.floor((now - then) / 1000);

  if (seconds < 60) return 'Just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)} minutes ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} hours ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)} days ago`;

  return then.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

// Related entity card component
function RelatedEntityCard({ entity, type }) {
  const navigate = useNavigate();

  const entityConfig = {
    agent: {
      icon: CpuChipIcon,
      label: 'Agent',
      route: (e) => `/agents/mission-control/${e.id}`,
    },
    scan: {
      icon: DocumentMagnifyingGlassIcon,
      label: 'Scan',
      route: () => null, // No dedicated scan page
    },
    approval: {
      icon: CheckCircleIcon,
      label: 'Approval',
      route: () => '/approvals',
    },
    repository: {
      icon: FolderIcon,
      label: 'Repository',
      route: () => '/repositories',
    },
    alert: {
      icon: BellIcon,
      label: 'Alert',
      route: () => '/security/alerts',
    },
    incident: {
      icon: ExclamationTriangleIcon,
      label: 'Incident',
      route: () => '/incidents',
    },
  };

  const config = entityConfig[type] || {
    icon: DocumentTextIcon,
    label: 'Related',
    route: () => null,
  };

  const Icon = config.icon;
  const targetRoute = config.route(entity);

  const handleClick = () => {
    if (targetRoute) {
      navigate(targetRoute);
    }
  };

  const handleKeyDown = (event) => {
    if ((event.key === 'Enter' || event.key === ' ') && targetRoute) {
      event.preventDefault();
      navigate(targetRoute);
    }
  };

  return (
    <div
      role={targetRoute ? 'button' : 'article'}
      tabIndex={targetRoute ? 0 : undefined}
      onClick={targetRoute ? handleClick : undefined}
      onKeyDown={targetRoute ? handleKeyDown : undefined}
      className={`
        flex items-center gap-3 p-4 rounded-lg border
        border-surface-200 dark:border-surface-700
        bg-white dark:bg-surface-800
        ${targetRoute
          ? 'cursor-pointer hover:bg-surface-50 dark:hover:bg-surface-700/50 focus:outline-none focus:ring-2 focus:ring-aura-500'
          : ''
        }
        transition-colors duration-150
        group
      `}
      aria-label={`${config.label}: ${entity.name || entity.title || entity.id}`}
    >
      <div className="p-2 rounded-lg bg-surface-100 dark:bg-surface-700">
        <Icon className="w-5 h-5 text-surface-500 dark:text-surface-400" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-surface-900 dark:text-surface-100 truncate">
          {entity.name || entity.title || entity.id}
        </p>
        <p className="text-xs text-surface-500 dark:text-surface-400">
          {config.label}
        </p>
      </div>
      {targetRoute && (
        <ChevronRightIcon
          className="w-5 h-5 text-surface-300 dark:text-surface-600
                     group-hover:text-surface-500 dark:group-hover:text-surface-400
                     transition-colors duration-150"
          aria-hidden="true"
        />
      )}
    </div>
  );
}

// Metadata row component
function MetadataRow({ icon: Icon, label, value, isCode = false }) {
  if (!value) return null;

  return (
    <div className="flex items-start gap-3 py-3 border-b border-surface-100 dark:border-surface-700/50 last:border-b-0">
      <div className="flex-shrink-0 mt-0.5">
        <Icon className="w-4 h-4 text-surface-400 dark:text-surface-500" />
      </div>
      <div className="flex-1 min-w-0">
        <dt className="text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wide mb-1">
          {label}
        </dt>
        <dd className={`text-sm text-surface-900 dark:text-surface-100 ${isCode ? 'font-mono' : ''}`}>
          {value}
        </dd>
      </div>
    </div>
  );
}

// Mock data for demonstration when API is not available
const mockActivity = {
  id: 'act-001',
  type: 'vulnerability_detected',
  title: 'SQL Injection vulnerability in auth.py',
  description: 'CWE-89: Improper Neutralization of Special Elements detected in login handler. This vulnerability allows attackers to inject malicious SQL code through user input fields, potentially exposing sensitive database information.',
  timestamp: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
  createdAt: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
  updatedAt: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
  severity: 'critical',
  isRead: false,
  status: 'open',
  metadata: {
    file: 'src/auth/handlers/login.py',
    line: 45,
    cwe: 'CWE-89',
    cvss: 9.8,
    agent: 'Security Scanner Alpha',
    repository: 'core-api',
    commit: 'abc1234',
    branch: 'main',
  },
  source: 'Security Scanner',
  actor: 'system',
  tags: ['security', 'sql-injection', 'critical', 'auth'],
};

const mockRelatedEntities = {
  agents: [
    { id: 'agent-001', name: 'Security Scanner Alpha', type: 'scanner' },
    { id: 'agent-002', name: 'Coder Agent', type: 'coder' },
  ],
  repositories: [
    { id: 'repo-001', name: 'core-api' },
  ],
  approvals: [
    { id: 'approval-001', title: 'Patch for SQL Injection Fix' },
  ],
};

export default function ActivityDetail() {
  const { activityId } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [activity, setActivity] = useState(null);
  const [relatedEntities, setRelatedEntities] = useState(null);
  const [error, setError] = useState(null);
  const [isMarking, setIsMarking] = useState(false);
  const [isDismissing, setIsDismissing] = useState(false);

  // Load activity data
  useEffect(() => {
    async function loadActivity() {
      setLoading(true);
      setError(null);

      try {
        // In production, these would be real API calls
        // For now, use mock data with simulated delay
        await new Promise((resolve) => setTimeout(resolve, 500));

        // Simulate API call - in production:
        // const activityData = await getActivity(activityId);
        // const relatedData = await getActivityRelatedEntities(activityId);

        setActivity(mockActivity);
        setRelatedEntities(mockRelatedEntities);
      } catch (err) {
        console.error('Error loading activity:', err);
        setError(err.message || 'Failed to load activity details');
      } finally {
        setLoading(false);
      }
    }

    if (activityId) {
      loadActivity();
    }
  }, [activityId]);

  // Handle back navigation
  const handleBack = useCallback(() => {
    navigate(-1);
  }, [navigate]);

  // Handle mark as read
  const handleMarkAsRead = useCallback(async () => {
    if (!activity || activity.isRead || isMarking) return;

    setIsMarking(true);
    try {
      // In production: await markAsRead(activity.id);
      await new Promise((resolve) => setTimeout(resolve, 300));
      setActivity((prev) => ({ ...prev, isRead: true }));
    } catch (err) {
      console.error('Error marking as read:', err);
    } finally {
      setIsMarking(false);
    }
  }, [activity, isMarking]);

  // Handle dismiss
  const handleDismiss = useCallback(async () => {
    if (!activity || isDismissing) return;

    setIsDismissing(true);
    try {
      // In production: await dismissActivity(activity.id);
      await new Promise((resolve) => setTimeout(resolve, 300));
      navigate(-1);
    } catch (err) {
      console.error('Error dismissing activity:', err);
      setIsDismissing(false);
    }
  }, [activity, isDismissing, navigate]);

  // Handle keyboard navigation
  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        handleBack();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleBack]);

  if (loading) {
    return <PageSkeleton />;
  }

  if (error) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8">
        <ExclamationTriangleIcon className="w-16 h-16 text-critical-500 mb-4" />
        <h2 className="text-xl font-semibold text-surface-900 dark:text-surface-100 mb-2">
          Error Loading Activity
        </h2>
        <p className="text-surface-600 dark:text-surface-400 mb-6 text-center max-w-md">
          {error}
        </p>
        <Button onClick={handleBack} variant="primary">
          Go Back
        </Button>
      </div>
    );
  }

  if (!activity) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8">
        <DocumentTextIcon className="w-16 h-16 text-surface-300 dark:text-surface-600 mb-4" />
        <h2 className="text-xl font-semibold text-surface-900 dark:text-surface-100 mb-2">
          Activity Not Found
        </h2>
        <p className="text-surface-600 dark:text-surface-400 mb-6">
          The activity you're looking for doesn't exist or has been removed.
        </p>
        <Button onClick={handleBack} variant="primary">
          Go Back
        </Button>
      </div>
    );
  }

  const typeConfig = activityTypeConfig[activity.type] || activityTypeConfig.in_progress;
  const colors = colorClasses[typeConfig.color] || colorClasses.aura;
  const Icon = typeConfig.icon;
  const severityConf = activity.severity ? severityConfig[activity.severity] : null;

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-4xl mx-auto p-6 lg:p-8">
        {/* Back button */}
        <button
          onClick={handleBack}
          className="
            flex items-center gap-2 mb-6 text-sm font-medium
            text-surface-600 dark:text-surface-400
            hover:text-surface-900 dark:hover:text-surface-100
            focus:outline-none focus:ring-2 focus:ring-aura-500 rounded-lg p-1 -ml-1
            transition-colors duration-150
          "
          aria-label="Go back"
        >
          <ArrowLeftIcon className="w-4 h-4" />
          Back
        </button>

        {/* Header card */}
        <div className={`
          rounded-2xl border-2 ${colors.border} ${colors.bg}
          p-6 mb-6
        `}>
          <div className="flex items-start gap-4">
            {/* Type icon */}
            <div className={`
              flex-shrink-0 w-12 h-12 rounded-xl
              ${colors.bg} flex items-center justify-center
            `}>
              <Icon className={`w-6 h-6 ${colors.icon}`} />
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
              {/* Type badge and severity */}
              <div className="flex items-center flex-wrap gap-2 mb-2">
                <span className={`
                  inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold
                  ${colors.bg} ${colors.text}
                `}>
                  {typeConfig.label}
                </span>
                {severityConf && (
                  <span className={`
                    inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold uppercase
                    ${severityConf.classes}
                  `}>
                    {severityConf.label}
                  </span>
                )}
                {!activity.isRead && (
                  <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-aura-500 text-white">
                    Unread
                  </span>
                )}
              </div>

              {/* Title */}
              <h1 className="text-xl lg:text-2xl font-bold text-surface-900 dark:text-surface-100 mb-2">
                {activity.title}
              </h1>

              {/* Timestamp */}
              <p className="text-sm text-surface-500 dark:text-surface-400">
                {formatRelativeTime(activity.timestamp)} - {formatFullTimestamp(activity.timestamp)}
              </p>
            </div>
          </div>

          {/* Description */}
          {activity.description && (
            <div className="mt-6 pt-6 border-t border-surface-200 dark:border-surface-700/50">
              <p className="text-surface-700 dark:text-surface-300 leading-relaxed">
                {activity.description}
              </p>
            </div>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex flex-wrap gap-3 mb-6">
          {!activity.isRead && (
            <Button
              onClick={handleMarkAsRead}
              disabled={isMarking}
              variant="secondary"
              className="flex items-center gap-2"
            >
              {isMarking ? (
                <ArrowPathIcon className="w-4 h-4 animate-spin" />
              ) : (
                <EyeIcon className="w-4 h-4" />
              )}
              Mark as Read
            </Button>
          )}
          <Button
            onClick={handleDismiss}
            disabled={isDismissing}
            variant="ghost"
            className="flex items-center gap-2 text-critical-600 dark:text-critical-400 hover:bg-critical-50 dark:hover:bg-critical-900/20"
          >
            {isDismissing ? (
              <ArrowPathIcon className="w-4 h-4 animate-spin" />
            ) : (
              <TrashIcon className="w-4 h-4" />
            )}
            Dismiss
          </Button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Metadata section */}
          <div className="lg:col-span-2">
            <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-6">
              <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4">
                Details
              </h2>

              <dl className="space-y-0">
                <MetadataRow
                  icon={ClockIcon}
                  label="Created"
                  value={formatFullTimestamp(activity.createdAt || activity.timestamp)}
                />
                {activity.updatedAt && activity.updatedAt !== activity.createdAt && (
                  <MetadataRow
                    icon={ArrowPathIcon}
                    label="Updated"
                    value={formatFullTimestamp(activity.updatedAt)}
                  />
                )}
                {activity.metadata?.file && (
                  <MetadataRow
                    icon={DocumentTextIcon}
                    label="File"
                    value={`${activity.metadata.file}${activity.metadata.line ? `:${activity.metadata.line}` : ''}`}
                    isCode
                  />
                )}
                {activity.metadata?.repository && (
                  <MetadataRow
                    icon={FolderIcon}
                    label="Repository"
                    value={activity.metadata.repository}
                  />
                )}
                {activity.metadata?.branch && (
                  <MetadataRow
                    icon={CodeBracketIcon}
                    label="Branch"
                    value={activity.metadata.branch}
                    isCode
                  />
                )}
                {activity.metadata?.commit && (
                  <MetadataRow
                    icon={LinkIcon}
                    label="Commit"
                    value={activity.metadata.commit}
                    isCode
                  />
                )}
                {activity.metadata?.agent && (
                  <MetadataRow
                    icon={CpuChipIcon}
                    label="Agent"
                    value={activity.metadata.agent}
                  />
                )}
                {activity.metadata?.cwe && (
                  <MetadataRow
                    icon={ShieldCheckIcon}
                    label="CWE"
                    value={activity.metadata.cwe}
                    isCode
                  />
                )}
                {activity.metadata?.cvss && (
                  <MetadataRow
                    icon={ExclamationTriangleIcon}
                    label="CVSS Score"
                    value={activity.metadata.cvss.toString()}
                  />
                )}
                {activity.source && (
                  <MetadataRow
                    icon={DocumentMagnifyingGlassIcon}
                    label="Source"
                    value={activity.source}
                  />
                )}
                {activity.actor && (
                  <MetadataRow
                    icon={UserIcon}
                    label="Actor"
                    value={activity.actor}
                  />
                )}
              </dl>

              {/* Tags */}
              {activity.tags && activity.tags.length > 0 && (
                <div className="mt-6 pt-4 border-t border-surface-100 dark:border-surface-700/50">
                  <div className="flex items-center gap-2 mb-3">
                    <TagIcon className="w-4 h-4 text-surface-400" />
                    <span className="text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wide">
                      Tags
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {activity.tags.map((tag) => (
                      <span
                        key={tag}
                        className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium
                                   bg-surface-100 text-surface-700 dark:bg-surface-700 dark:text-surface-300"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Related entities section */}
          <div className="lg:col-span-1">
            <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-6">
              <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4">
                Related
              </h2>

              {relatedEntities && (
                Object.values(relatedEntities).some((arr) => arr && arr.length > 0) ? (
                  <div className="space-y-3">
                    {relatedEntities.agents?.map((entity) => (
                      <RelatedEntityCard key={entity.id} entity={entity} type="agent" />
                    ))}
                    {relatedEntities.repositories?.map((entity) => (
                      <RelatedEntityCard key={entity.id} entity={entity} type="repository" />
                    ))}
                    {relatedEntities.approvals?.map((entity) => (
                      <RelatedEntityCard key={entity.id} entity={entity} type="approval" />
                    ))}
                    {relatedEntities.alerts?.map((entity) => (
                      <RelatedEntityCard key={entity.id} entity={entity} type="alert" />
                    ))}
                    {relatedEntities.incidents?.map((entity) => (
                      <RelatedEntityCard key={entity.id} entity={entity} type="incident" />
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-surface-500 dark:text-surface-400 text-center py-4">
                    No related entities found.
                  </p>
                )
              )}
            </div>

            {/* Quick actions */}
            <div className="mt-6 bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-6">
              <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4">
                Quick Actions
              </h2>

              <div className="space-y-2">
                {activity.type === 'vulnerability_detected' && (
                  <Link
                    to="/approvals"
                    className="
                      flex items-center justify-between p-3 rounded-lg
                      bg-surface-50 dark:bg-surface-700/50
                      hover:bg-surface-100 dark:hover:bg-surface-700
                      text-surface-700 dark:text-surface-300
                      transition-colors duration-150
                    "
                  >
                    <span className="text-sm font-medium">View Patch Approvals</span>
                    <ChevronRightIcon className="w-4 h-4" />
                  </Link>
                )}
                {(activity.type === 'agent_started' || activity.type === 'agent_completed' || activity.type === 'agent_failed') && (
                  <Link
                    to="/agents/mission-control"
                    className="
                      flex items-center justify-between p-3 rounded-lg
                      bg-surface-50 dark:bg-surface-700/50
                      hover:bg-surface-100 dark:hover:bg-surface-700
                      text-surface-700 dark:text-surface-300
                      transition-colors duration-150
                    "
                  >
                    <span className="text-sm font-medium">Open Mission Control</span>
                    <ChevronRightIcon className="w-4 h-4" />
                  </Link>
                )}
                <Link
                  to="/"
                  className="
                    flex items-center justify-between p-3 rounded-lg
                    bg-surface-50 dark:bg-surface-700/50
                    hover:bg-surface-100 dark:hover:bg-surface-700
                    text-surface-700 dark:text-surface-300
                    transition-colors duration-150
                  "
                >
                  <span className="text-sm font-medium">Back to Dashboard</span>
                  <ChevronRightIcon className="w-4 h-4" />
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
