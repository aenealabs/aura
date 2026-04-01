import { useState, useEffect, useCallback } from 'react';
import {
  ExclamationCircleIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  XCircleIcon,
  EyeIcon,
  MagnifyingGlassIcon,
  FunnelIcon,
  ArrowPathIcon,
  ClockIcon,
  ShieldExclamationIcon,
  DocumentTextIcon,
  ChevronRightIcon,
  BellAlertIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';
import { useSecurityAlerts } from '../context/SecurityAlertsContext';
import { PRIORITY_CONFIG } from '../services/securityAlertsApi';
import { useToast } from './ui/Toast';
import { PageSkeleton } from './ui/LoadingSkeleton';

// Priority styles following design system
const PRIORITY_STYLES = {
  P1_CRITICAL: {
    badge: 'bg-critical-100 text-critical-800 dark:bg-critical-900/30 dark:text-critical-400',
    border: 'border-l-4 border-critical-500',
    icon: ExclamationCircleIcon,
    pulse: true,
  },
  P2_HIGH: {
    badge: 'bg-warning-100 text-warning-800 dark:bg-warning-900/30 dark:text-warning-400',
    border: 'border-l-4 border-warning-500',
    icon: ExclamationTriangleIcon,
    pulse: false,
  },
  P3_MEDIUM: {
    badge: 'bg-warning-100 text-warning-800 dark:bg-warning-900/30 dark:text-warning-400',
    border: 'border-l-4 border-warning-500',
    icon: InformationCircleIcon,
    pulse: false,
  },
  P4_LOW: {
    badge: 'bg-aura-100 text-aura-800 dark:bg-aura-900/30 dark:text-aura-400',
    border: 'border-l-4 border-aura-500',
    icon: InformationCircleIcon,
    pulse: false,
  },
  P5_INFO: {
    badge: 'bg-surface-100 text-surface-800 dark:bg-surface-700 dark:text-surface-300',
    border: 'border-l-4 border-surface-400',
    icon: InformationCircleIcon,
    pulse: false,
  },
};

const STATUS_STYLES = {
  NEW: {
    badge: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
    icon: BellAlertIcon,
    label: 'New',
  },
  ACKNOWLEDGED: {
    badge: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    icon: EyeIcon,
    label: 'Acknowledged',
  },
  INVESTIGATING: {
    badge: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
    icon: MagnifyingGlassIcon,
    label: 'Investigating',
  },
  RESOLVED: {
    badge: 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400',
    icon: CheckCircleIcon,
    label: 'Resolved',
  },
  FALSE_POSITIVE: {
    badge: 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-400',
    icon: XCircleIcon,
    label: 'False Positive',
  },
};

// Alert Card Component
function AlertCard({ alert, isSelected, onClick }) {
  const priorityStyle = PRIORITY_STYLES[alert.priority] || PRIORITY_STYLES.P3_MEDIUM;
  const statusStyle = STATUS_STYLES[alert.status] || STATUS_STYLES.NEW;
  const StatusIcon = statusStyle.icon;
  const PriorityIcon = priorityStyle.icon;

  const timeAgo = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);

    if (seconds < 60) return 'Just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  };

  return (
    <button
      onClick={onClick}
      className={`
        w-full text-left p-4 rounded-xl border-2 transition-all duration-200 cursor-pointer
        ${isSelected
          ? 'border-aura-500 dark:border-aura-400 bg-white dark:bg-surface-800 shadow-lg'
          : 'border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 hover:border-surface-300 dark:hover:border-surface-600 hover:shadow-md'
        }
        ${priorityStyle.pulse && alert.status === 'NEW' ? 'animate-pulse-slow' : ''}
      `}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <PriorityIcon className={`w-5 h-5 flex-shrink-0 mt-0.5 ${
            alert.priority === 'P1_CRITICAL' ? 'text-critical-500' :
            alert.priority === 'P2_HIGH' ? 'text-warning-500' :
            'text-surface-500 dark:text-surface-400'
          }`} />
          <div className="flex-1 min-w-0">
            <h3 className="font-medium text-surface-900 dark:text-surface-100 truncate">
              {alert.title}
            </h3>
            <p className="text-sm text-surface-500 dark:text-surface-400 truncate mt-0.5">
              {alert.event_type || alert.description}
            </p>
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              <span className={`px-2 py-0.5 text-xs font-medium rounded ${priorityStyle.badge}`}>
                {PRIORITY_CONFIG[alert.priority]?.label || alert.priority}
              </span>
              <span className={`px-2 py-0.5 text-xs font-medium rounded inline-flex items-center gap-1 ${statusStyle.badge}`}>
                <StatusIcon className="w-3 h-3" />
                {statusStyle.label}
              </span>
            </div>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1 flex-shrink-0">
          <span className="text-xs text-surface-500 dark:text-surface-400">
            {timeAgo(alert.created_at)}
          </span>
          <ChevronRightIcon className={`w-4 h-4 text-surface-400 transition-transform ${isSelected ? 'rotate-90' : ''}`} />
        </div>
      </div>
    </button>
  );
}

// Alert Detail Panel Component
function AlertDetailPanel({ alert, onAcknowledge, onResolve }) {
  const [activeTab, setActiveTab] = useState('details');
  const priorityStyle = PRIORITY_STYLES[alert.priority] || PRIORITY_STYLES.P3_MEDIUM;
  const statusStyle = STATUS_STYLES[alert.status] || STATUS_STYLES.NEW;

  const tabs = [
    { id: 'details', label: 'Details', icon: DocumentTextIcon },
    { id: 'remediation', label: 'Remediation', icon: ShieldExclamationIcon },
    { id: 'timeline', label: 'Timeline', icon: ClockIcon },
  ];

  return (
    <div className="h-full flex flex-col bg-white dark:bg-surface-800 backdrop-blur-xl">
      {/* Header */}
      <div className={`p-6 border-b border-surface-100/50 dark:border-surface-700/30 ${priorityStyle.border}`}>
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-xl font-semibold text-surface-900 dark:text-surface-100">
              {alert.title}
            </h2>
            <p className="text-sm text-surface-500 dark:text-surface-400 mt-1">
              Alert ID: {alert.alert_id}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className={`px-3 py-1 text-sm font-medium rounded ${priorityStyle.badge}`}>
              {PRIORITY_CONFIG[alert.priority]?.label}
            </span>
            <span className={`px-3 py-1 text-sm font-medium rounded ${statusStyle.badge}`}>
              {statusStyle.label}
            </span>
          </div>
        </div>

        {/* Action Buttons */}
        {alert.status === 'NEW' && (
          <div className="flex gap-2 mt-4">
            <button
              onClick={() => onAcknowledge(alert.alert_id)}
              className="px-4 py-2 bg-orange-500 hover:bg-orange-600 text-white rounded-xl font-medium transition-all duration-200 ease-[var(--ease-tahoe)] hover:-translate-y-px hover:shadow-md active:scale-[0.98] flex items-center gap-2"
            >
              <EyeIcon className="w-4 h-4" />
              Acknowledge
            </button>
          </div>
        )}
        {(alert.status === 'ACKNOWLEDGED' || alert.status === 'INVESTIGATING') && (
          <div className="flex gap-2 mt-4">
            <button
              onClick={() => onResolve(alert.alert_id)}
              className="px-4 py-2 bg-olive-500 hover:bg-olive-600 text-white rounded-xl font-medium transition-all duration-200 ease-[var(--ease-tahoe)] hover:-translate-y-px hover:shadow-md active:scale-[0.98] flex items-center gap-2"
            >
              <CheckCircleIcon className="w-4 h-4" />
              Resolve
            </button>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="border-b border-surface-100/50 dark:border-surface-700/30">
        <nav className="flex gap-4 px-6" aria-label="Tabs">
          {tabs.map((tab) => {
            const TabIcon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`
                  py-3 px-1 border-b-2 font-medium text-sm flex items-center gap-2 transition-all duration-200 ease-[var(--ease-tahoe)]
                  ${activeTab === tab.id
                    ? 'border-aura-500 text-aura-600 dark:text-aura-400'
                    : 'border-transparent text-surface-500 hover:text-surface-700 hover:border-surface-300 dark:text-surface-400'
                  }
                `}
              >
                <TabIcon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {activeTab === 'details' && (
          <div className="space-y-6">
            <div>
              <h3 className="text-sm font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wider mb-2">
                Description
              </h3>
              <p className="text-surface-900 dark:text-surface-100">
                {alert.description}
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <h3 className="text-sm font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wider mb-2">
                  Event Type
                </h3>
                <p className="text-surface-900 dark:text-surface-100 font-mono text-sm">
                  {alert.event_type}
                </p>
              </div>
              <div>
                <h3 className="text-sm font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wider mb-2">
                  Severity
                </h3>
                <p className="text-surface-900 dark:text-surface-100">
                  {alert.severity}
                </p>
              </div>
              {alert.source_ip && (
                <div>
                  <h3 className="text-sm font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wider mb-2">
                    Source IP
                  </h3>
                  <p className="text-surface-900 dark:text-surface-100 font-mono text-sm">
                    {alert.source_ip}
                  </p>
                </div>
              )}
              {alert.user_id && (
                <div>
                  <h3 className="text-sm font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wider mb-2">
                    User ID
                  </h3>
                  <p className="text-surface-900 dark:text-surface-100 font-mono text-sm">
                    {alert.user_id}
                  </p>
                </div>
              )}
            </div>

            <div>
              <h3 className="text-sm font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wider mb-2">
                Created
              </h3>
              <p className="text-surface-900 dark:text-surface-100">
                {new Date(alert.created_at).toLocaleString()}
              </p>
            </div>
          </div>
        )}

        {activeTab === 'remediation' && (
          <div className="space-y-4">
            <h3 className="text-sm font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wider">
              Recommended Actions
            </h3>
            {alert.remediation_steps?.length > 0 ? (
              <ol className="space-y-3">
                {alert.remediation_steps.map((step, index) => (
                  <li key={index} className="flex items-start gap-3">
                    <span className="flex-shrink-0 w-6 h-6 bg-aura-100 dark:bg-aura-900/30 text-aura-600 dark:text-aura-400 rounded-full flex items-center justify-center text-sm font-medium">
                      {index + 1}
                    </span>
                    <span className="text-surface-900 dark:text-surface-100">{step}</span>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="text-surface-500 dark:text-surface-400">
                No remediation steps available for this alert.
              </p>
            )}
          </div>
        )}

        {activeTab === 'timeline' && (
          <div className="space-y-4">
            <div className="relative">
              <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-surface-200 dark:bg-surface-700" />
              <ul className="space-y-4">
                <li className="relative pl-10">
                  <div className="absolute left-2.5 w-3 h-3 bg-critical-500 rounded-full" />
                  <p className="text-sm text-surface-900 dark:text-surface-100 font-medium">Alert Created</p>
                  <p className="text-xs text-surface-500 dark:text-surface-400">
                    {new Date(alert.created_at).toLocaleString()}
                  </p>
                </li>
                {alert.acknowledged_at && (
                  <li className="relative pl-10">
                    <div className="absolute left-2.5 w-3 h-3 bg-warning-500 rounded-full" />
                    <p className="text-sm text-surface-900 dark:text-surface-100 font-medium">Acknowledged</p>
                    <p className="text-xs text-surface-500 dark:text-surface-400">
                      {new Date(alert.acknowledged_at).toLocaleString()}
                    </p>
                  </li>
                )}
                {alert.resolved_at && (
                  <li className="relative pl-10">
                    <div className="absolute left-2.5 w-3 h-3 bg-olive-500 rounded-full" />
                    <p className="text-sm text-surface-900 dark:text-surface-100 font-medium">Resolved</p>
                    <p className="text-xs text-surface-500 dark:text-surface-400">
                      {new Date(alert.resolved_at).toLocaleString()}
                    </p>
                    {alert.resolution && (
                      <p className="text-sm text-surface-600 dark:text-surface-300 mt-1">
                        {alert.resolution}
                      </p>
                    )}
                  </li>
                )}
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Main SecurityAlertsPanel Component
export default function SecurityAlertsPanel() {
  const {
    alerts,
    selectedAlert,
    loading,
    error,
    filters,
    unacknowledgedCount,
    fetchAlerts: _fetchAlerts,
    fetchAlertDetail,
    handleAcknowledge,
    handleResolve,
    updateFilters,
    clearFilters,
    setSelectedAlert,
    refresh,
  } = useSecurityAlerts();

  const [searchTerm, setSearchTerm] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const { toast } = useToast();

  // Handle refresh with toast notification
  const handleRefresh = useCallback(async () => {
    try {
      await refresh();
      toast.success('Alerts refreshed');
    } catch (err) {
      toast.error('Failed to refresh alerts');
    }
  }, [refresh, toast]);

  // Track initial load completion
  useEffect(() => {
    if (!loading && isInitialLoad) {
      // Add small delay to ensure skeleton is visible
      const timer = setTimeout(() => setIsInitialLoad(false), 300);
      return () => clearTimeout(timer);
    }
  }, [loading, isInitialLoad]);

  // Show page skeleton on initial load
  if (isInitialLoad && loading) {
    return <PageSkeleton />;
  }

  // Filter alerts by search term
  const filteredAlerts = alerts.filter(alert =>
    alert.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    alert.description?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    alert.event_type?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Handle alert selection (toggle behavior - click again to unselect)
  const handleSelectAlert = async (alert) => {
    if (selectedAlert?.alert_id === alert.alert_id) {
      setSelectedAlert(null);
    } else {
      setSelectedAlert(alert);
      await fetchAlertDetail(alert.alert_id);
    }
  };

  // Handle acknowledge action
  const onAcknowledge = async (alertId) => {
    const userId = localStorage.getItem('userId') || 'security-analyst';
    await handleAcknowledge(alertId, userId);
  };

  // Handle resolve action
  const onResolve = async (alertId) => {
    const userId = localStorage.getItem('userId') || 'security-analyst';
    await handleResolve(alertId, userId, 'Resolved via Security Dashboard');
  };

  return (
    <div className="h-full flex flex-col bg-surface-50/50 dark:bg-surface-900/50">
      {/* Header */}
      <header className="bg-white dark:bg-surface-800 backdrop-blur-xl border-b border-surface-100/50 dark:border-surface-700/30 p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-critical-100 dark:bg-critical-900/30 rounded-lg">
              <ShieldExclamationIcon className="w-6 h-6 text-critical-600 dark:text-critical-400" />
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
                  Security Alerts
                </h1>
                {unacknowledgedCount > 0 && (
                  <span className="px-2 py-1 text-xs font-bold bg-critical-500 text-white rounded-full">
                    {unacknowledgedCount} new
                  </span>
                )}
              </div>
              <p className="text-surface-500 dark:text-surface-400">
                Monitor and respond to security threats
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleRefresh}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-100 hover:bg-white/60 dark:hover:bg-surface-700 rounded-xl transition-all duration-200 ease-[var(--ease-tahoe)] disabled:opacity-50"
            >
              <ArrowPathIcon className={`h-5 w-5 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`p-2 rounded-xl transition-all duration-200 ease-[var(--ease-tahoe)] ${
                showFilters
                  ? 'text-aura-600 bg-aura-50/80 dark:bg-aura-900/30'
                  : 'text-surface-500 hover:text-surface-700 hover:bg-white/60 dark:text-surface-400 dark:hover:bg-surface-700'
              }`}
            >
              <FunnelIcon className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Search Bar */}
        <div className="mt-4 relative max-w-md">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-surface-400" />
          <input
            type="text"
            placeholder="Search alerts..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
          />
        </div>

        {/* Filters */}
        {showFilters && (
          <div className="mt-4 flex flex-wrap gap-2">
            <select
              value={filters.priority || ''}
              onChange={(e) => updateFilters({ priority: e.target.value || null })}
              className="px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-sm text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
            >
              <option value="">All Priorities</option>
              <option value="P1_CRITICAL">P1 Critical</option>
              <option value="P2_HIGH">P2 High</option>
              <option value="P3_MEDIUM">P3 Medium</option>
              <option value="P4_LOW">P4 Low</option>
              <option value="P5_INFO">P5 Info</option>
            </select>
            <select
              value={filters.status || ''}
              onChange={(e) => updateFilters({ status: e.target.value || null })}
              className="px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-sm text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
            >
              <option value="">All Statuses</option>
              <option value="NEW">New</option>
              <option value="ACKNOWLEDGED">Acknowledged</option>
              <option value="INVESTIGATING">Investigating</option>
              <option value="RESOLVED">Resolved</option>
              <option value="FALSE_POSITIVE">False Positive</option>
            </select>
            {(filters.priority || filters.status) && (
              <button
                onClick={clearFilters}
                className="px-3 py-1.5 text-sm text-aura-600 dark:text-aura-400 hover:underline"
              >
                Clear filters
              </button>
            )}
          </div>
        )}
      </header>

      {/* Content */}
      <div className="flex-1 flex overflow-hidden p-6 pb-24 gap-6">
        {/* Alert List */}
        <div className="w-[400px] flex-shrink-0 overflow-y-auto space-y-3 pr-4 border-r border-surface-200 dark:border-surface-700">
          {error && (
            <div className="p-4 bg-critical-50/80 dark:bg-critical-900/20 backdrop-blur-sm text-critical-700 dark:text-critical-400 text-sm rounded-lg">
              {error}
            </div>
          )}

          {loading && filteredAlerts.length === 0 ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="p-4 rounded-xl border-2 border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 animate-pulse">
                  <div className="h-4 bg-surface-200 dark:bg-surface-700 rounded w-3/4 mb-2" />
                  <div className="h-3 bg-surface-200 dark:bg-surface-700 rounded w-1/2" />
                </div>
              ))}
            </div>
          ) : filteredAlerts.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-surface-400">
              <ShieldExclamationIcon className="w-12 h-12 mb-3" />
              <p className="text-lg font-medium">No alerts found</p>
            </div>
          ) : (
            filteredAlerts.map((alert) => (
              <AlertCard
                key={alert.alert_id}
                alert={alert}
                isSelected={selectedAlert?.alert_id === alert.alert_id}
                onClick={() => handleSelectAlert(alert)}
              />
            ))
          )}
        </div>

        {/* Detail Panel */}
        {selectedAlert ? (
          <div className="flex-1 overflow-hidden bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700">
            <AlertDetailPanel
              alert={selectedAlert}
              onAcknowledge={onAcknowledge}
              onResolve={onResolve}
            />
          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-surface-400 dark:text-surface-500 p-8">
            <ShieldExclamationIcon className="w-16 h-16 mb-4" />
            <h3 className="text-lg font-medium mb-2">Select an Alert</h3>
            <p className="text-sm text-center">Choose an alert to view details and take action</p>
          </div>
        )}
      </div>
    </div>
  );
}
