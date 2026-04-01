/**
 * Project Aura - Security Dashboard
 *
 * Main dashboard component displaying real-time security metrics,
 * agent status, vulnerability trends, and system health.
 * Uses real API integration with auto-refresh and error handling.
 *
 * @module components/Dashboard
 */

import { useState, useCallback, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ShieldCheckIcon,
  BugAntIcon,
  CpuChipIcon,
  BeakerIcon,
  ExclamationTriangleIcon,
  ClockIcon,
  PlayIcon,
  EyeIcon,
  HeartIcon,
  BellAlertIcon,
  CircleStackIcon,
  ArrowsRightLeftIcon,
  BoltIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';
import MetricCard from './ui/MetricCard';
import ActivityFeed from './ui/ActivityFeed';
import { LineChart, DonutChart, ProgressChart } from './ui/Charts';
import { PageSkeleton } from './ui/LoadingSkeleton';
import { useToast } from './ui/Toast';
import DashboardGrid from './ui/DashboardGrid';
import { useSecurityAlerts } from '../context/SecurityAlertsContext';
import { ScanModal, HealthCheckModal } from './modals';
import { DashboardSearchTrigger } from './CommandPalette';
import { useDashboardData } from '../hooks/useDashboardData';
import {
  FindingsBySeverityWidget,
  ActiveScansWidget,
  ScanPipelineProgressWidget,
  TruePositiveRateWidget,
  LLMTokenSpendWidget,
  ScannerAlarmStatusWidget,
  RecentScanActivityWidget,
  FindingsRequiringApprovalWidget,
  ScanDurationTrendWidget,
  StageDurationWaterfallWidget,
  FindingsByCWEWidget,
  LLMLatencyWidget,
  ConcurrentUtilizationWidget,
  CriticalFindingsTrendWidget,
  ScanQueueDepthWidget,
  CandidateFunnelWidget,
  FindingsByLanguageWidget,
  VerificationStatusWidget,
  CleanupActivityWidget,
  ScanDepthDistributionWidget,
} from './dashboard/widgets/scanner';

/**
 * @typedef {Object} QuickActionProps
 * @property {React.ComponentType} icon - Heroicon component
 * @property {string} label - Button label
 * @property {Function} onClick - Click handler
 * @property {'default'|'primary'|'olive'} [variant='default'] - Button variant
 */

/**
 * Quick action button component
 *
 * @param {QuickActionProps} props - Component props
 */
function QuickAction({ icon: Icon, label, onClick, variant = 'default' }) {
  const variantClasses = {
    default: 'bg-surface-100 hover:bg-surface-200 text-surface-700 dark:bg-surface-700 dark:hover:bg-surface-600 dark:text-surface-200',
    primary: 'bg-aura-500 hover:bg-aura-600 text-white',
    olive: 'bg-olive-500 hover:bg-olive-600 text-white',
  };

  return (
    <button
      onClick={onClick}
      className={`
        flex items-center gap-2 px-4 py-2.5 rounded-lg
        font-medium text-sm
        transition-all duration-200 ease-smooth
        hover:shadow-md active:scale-[0.98]
        ${variantClasses[variant]}
      `}
    >
      <Icon className="w-4 h-4" />
      {label}
    </button>
  );
}

/**
 * Agent status card widget displaying real-time agent states
 *
 * @param {Object} props - Component props
 * @param {Array} props.agents - Array of agent status objects
 * @param {boolean} [props.loading=false] - Loading state
 * @param {Error|null} [props.error=null] - Error state
 * @param {Function} [props.onRetry] - Retry callback for error state
 */
function AgentStatusWidget({ agents, loading = false, error = null, onRetry }) {
  if (loading) {
    return (
      <div className="h-full p-4 space-y-4 animate-pulse">
        <div className="flex items-center justify-between mb-4">
          <div className="w-24 h-5 bg-surface-200 dark:bg-surface-700 rounded" />
          <div className="w-12 h-4 bg-surface-200 dark:bg-surface-700 rounded" />
        </div>
        {[1, 2, 3].map((i) => (
          <div key={i} className="space-y-2">
            <div className="w-full h-4 bg-surface-200 dark:bg-surface-700 rounded" />
            <div className="w-3/4 h-3 bg-surface-200 dark:bg-surface-700 rounded" />
            <div className="w-full h-1.5 bg-surface-200 dark:bg-surface-700 rounded-full" />
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full p-4 flex flex-col items-center justify-center text-center">
        <ExclamationTriangleIcon className="w-8 h-8 text-critical-500 mb-2" />
        <p className="text-sm text-surface-600 dark:text-surface-400 mb-2">
          Failed to load agent status
        </p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="flex items-center gap-1 text-sm text-aura-600 dark:text-aura-400 hover:underline"
          >
            <ArrowPathIcon className="w-4 h-4" />
            Retry
          </button>
        )}
      </div>
    );
  }

  // Use provided agents or fallback to empty array
  const agentList = agents || [];

  return (
    <div className="h-full p-4 overflow-auto">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold text-surface-900 dark:text-surface-100">
          Agent Status
        </h3>
        <span className="text-sm text-olive-600 dark:text-olive-400 flex items-center gap-1">
          <span className="w-2 h-2 bg-olive-500 rounded-full animate-pulse" />
          Live
        </span>
      </div>

      {agentList.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-32 text-surface-400">
          <CpuChipIcon className="w-8 h-8 mb-2" />
          <p className="text-sm">No agents available</p>
        </div>
      ) : (
        <div className="space-y-3">
          {agentList.map((agent) => (
            <div
              key={agent.id || agent.name}
              className="p-3 rounded-lg border border-surface-200 dark:border-surface-700 hover:border-aura-300 dark:hover:border-aura-600 hover:bg-surface-50 dark:hover:bg-surface-800/50 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CpuChipIcon className="w-4 h-4 text-aura-500" />
                  <span className="font-medium text-sm text-surface-900 dark:text-surface-100">
                    {agent.name}
                  </span>
                  <span
                    className={`
                      text-xs px-2 py-0.5 rounded-full
                      ${agent.status === 'active'
                        ? 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400'
                        : agent.status === 'error'
                          ? 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400'
                          : 'bg-surface-100 text-surface-500 dark:bg-surface-700 dark:text-surface-400'
                      }
                    `}
                  >
                    {agent.status}
                  </span>
                </div>
                {agent.progress > 0 && (
                  <span className="text-xs text-surface-500 dark:text-surface-400">
                    {agent.progress}%
                  </span>
                )}
              </div>

              <p className="text-xs text-surface-600 dark:text-surface-400 truncate mt-2">
                {agent.task || 'No active task'}
              </p>

              {agent.progress > 0 && (
                <div className="h-1.5 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden mt-2">
                  <div
                    className="h-full bg-aura-500 rounded-full transition-all duration-500 ease-smooth"
                    style={{ width: `${agent.progress}%` }}
                  />
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * System health widget displaying infrastructure status
 *
 * @param {Object} props - Component props
 * @param {Object} [props.health] - Health metrics data
 * @param {boolean} [props.loading=false] - Loading state
 * @param {Error|null} [props.error=null] - Error state
 * @param {Function} [props.onRetry] - Retry callback for error state
 */
function SystemHealthWidget({ health, loading = false, error = null, onRetry }) {
  if (loading) {
    return (
      <div className="h-full p-4 animate-pulse">
        <div className="w-28 h-5 bg-surface-200 dark:bg-surface-700 rounded mb-4" />
        <div className="grid grid-cols-2 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="flex items-center gap-2">
              <div className="w-11 h-11 rounded-full bg-surface-200 dark:bg-surface-700" />
              <div className="space-y-1">
                <div className="w-16 h-3 bg-surface-200 dark:bg-surface-700 rounded" />
                <div className="w-8 h-3 bg-surface-200 dark:bg-surface-700 rounded" />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full p-4 flex flex-col items-center justify-center text-center">
        <ExclamationTriangleIcon className="w-8 h-8 text-critical-500 mb-2" />
        <p className="text-sm text-surface-600 dark:text-surface-400 mb-2">
          Failed to load health metrics
        </p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="flex items-center gap-1 text-sm text-aura-600 dark:text-aura-400 hover:underline"
          >
            <ArrowPathIcon className="w-4 h-4" />
            Retry
          </button>
        )}
      </div>
    );
  }

  // Extract health metrics or use defaults
  const apiHealth = health?.api?.percentage ?? 96;
  const graphRagHealth = health?.graphRag?.percentage ?? 82;
  const llmQuota = health?.llm?.quotaUsed ?? 45;
  const sandboxAvailable = health?.sandbox?.available ?? 3;

  return (
    <div className="h-full p-4 overflow-auto">
      <h3 className="text-base font-semibold text-surface-900 dark:text-surface-100 mb-4">
        System Health
      </h3>

      <div className="grid grid-cols-2 gap-3">
        <div className="flex items-center gap-2 p-3 rounded-lg border border-surface-200 dark:border-surface-700 hover:border-aura-300 dark:hover:border-aura-600 hover:bg-surface-50 dark:hover:bg-surface-800/50 transition-colors">
          <ProgressChart
            value={apiHealth}
            max={100}
            color="olive"
            size={44}
            strokeWidth={5}
            showPercentage={false}
          />
          <div>
            <p className="text-xs font-medium text-surface-900 dark:text-surface-100">
              API Health
            </p>
            <p className="text-xs text-olive-600 dark:text-olive-400">{apiHealth}%</p>
          </div>
        </div>

        <div className="flex items-center gap-2 p-3 rounded-lg border border-surface-200 dark:border-surface-700 hover:border-aura-300 dark:hover:border-aura-600 hover:bg-surface-50 dark:hover:bg-surface-800/50 transition-colors">
          <ProgressChart
            value={graphRagHealth}
            max={100}
            color="aura"
            size={44}
            strokeWidth={5}
            showPercentage={false}
          />
          <div>
            <p className="text-xs font-medium text-surface-900 dark:text-surface-100">
              GraphRAG
            </p>
            <p className="text-xs text-aura-600 dark:text-aura-400">{graphRagHealth}%</p>
          </div>
        </div>

        <div className="flex items-center gap-2 p-3 rounded-lg border border-surface-200 dark:border-surface-700 hover:border-aura-300 dark:hover:border-aura-600 hover:bg-surface-50 dark:hover:bg-surface-800/50 transition-colors">
          <ProgressChart
            value={llmQuota}
            max={100}
            color={llmQuota > 80 ? 'critical' : llmQuota > 60 ? 'warning' : 'warning'}
            size={44}
            strokeWidth={5}
            showPercentage={false}
          />
          <div>
            <p className="text-xs font-medium text-surface-900 dark:text-surface-100">
              LLM Quota
            </p>
            <p className="text-xs text-warning-600 dark:text-warning-400">{llmQuota}%</p>
          </div>
        </div>

        <div className="flex items-center gap-2 p-3 rounded-lg border border-surface-200 dark:border-surface-700 hover:border-aura-300 dark:hover:border-aura-600 hover:bg-surface-50 dark:hover:bg-surface-800/50 transition-colors">
          <ProgressChart
            value={sandboxAvailable > 0 ? 99 : 0}
            max={100}
            color="olive"
            size={44}
            strokeWidth={5}
            showPercentage={false}
          />
          <div>
            <p className="text-xs font-medium text-surface-900 dark:text-surface-100">
              Sandbox
            </p>
            <p className="text-xs text-olive-600 dark:text-olive-400">{sandboxAvailable} avail</p>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Quick Actions Widget
 */
function QuickActionsWidget({ onStartScan, onReviewApprovals, onHealthCheck }) {
  return (
    <div className="h-full p-4 flex flex-col gap-2">
      <h3 className="text-base font-semibold text-surface-900 dark:text-surface-100 mb-2">
        Quick Actions
      </h3>
      <QuickAction
        icon={PlayIcon}
        label="Start Scan"
        variant="primary"
        onClick={onStartScan}
      />
      <QuickAction
        icon={EyeIcon}
        label="Review Approvals"
        onClick={onReviewApprovals}
      />
      <QuickAction
        icon={HeartIcon}
        label="Health Check"
        onClick={onHealthCheck}
      />
    </div>
  );
}

/**
 * Security Alerts Widget - shows recent P1/P2 alerts
 */
function SecurityAlertsWidget() {
  const { alerts, unacknowledgedCount, loading } = useSecurityAlerts();

  // Get critical and high priority alerts
  const criticalAlerts = alerts.filter(a =>
    a.priority === 'P1_CRITICAL' || a.priority === 'P2_HIGH'
  ).slice(0, 4);

  const priorityColors = {
    P1_CRITICAL: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
    P2_HIGH: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    P3_MEDIUM: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    P4_LOW: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
    P5_INFO: 'bg-surface-100 text-surface-700 dark:bg-surface-700 dark:text-surface-300',
  };

  const priorityLabels = {
    P1_CRITICAL: 'P1',
    P2_HIGH: 'P2',
    P3_MEDIUM: 'P3',
    P4_LOW: 'P4',
    P5_INFO: 'P5',
  };

  return (
    <div className="h-full p-4 overflow-auto">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold text-surface-900 dark:text-surface-100 flex items-center gap-2">
          <BellAlertIcon className="w-5 h-5 text-critical-500" />
          Security Alerts
        </h3>
        {unacknowledgedCount > 0 && (
          <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-critical-500 text-white">
            {unacknowledgedCount} new
          </span>
        )}
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="animate-pulse h-16 bg-surface-200 dark:bg-surface-700 rounded-lg" />
          ))}
        </div>
      ) : criticalAlerts.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-32 text-surface-400">
          <ShieldCheckIcon className="w-8 h-8 mb-2" />
          <p className="text-sm">No critical alerts</p>
        </div>
      ) : (
        <div className="space-y-3">
          {criticalAlerts.map(alert => (
            <Link
              key={alert.alert_id}
              to="/security/alerts"
              className="block p-3 rounded-lg border border-surface-200 dark:border-surface-700 hover:border-aura-300 dark:hover:border-aura-600 hover:bg-surface-50 dark:hover:bg-surface-800/50 transition-colors"
            >
              <div className="flex items-start gap-2">
                <span className={`px-1.5 py-0.5 text-xs font-bold rounded ${priorityColors[alert.priority]}`}>
                  {priorityLabels[alert.priority]}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-surface-900 dark:text-surface-100 truncate">
                    {alert.title}
                  </p>
                  <p className="text-xs text-surface-500 dark:text-surface-400 truncate mt-0.5">
                    {alert.event_type}
                  </p>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      <Link
        to="/security/alerts"
        className="mt-4 block text-center text-sm text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300 font-medium"
      >
        View all alerts
      </Link>
    </div>
  );
}

/**
 * Main Dashboard Component
 */
export default function Dashboard() {
  // Fetch dashboard data with auto-refresh
  const {
    data,
    loading,
    error,
    isInitialLoading,
    refetch,
    refetchSection,
    lastUpdated,
  } = useDashboardData({
    refreshInterval: 30000, // 30 seconds
    autoRefresh: true,
  });

  // Modal state
  const [isScanModalOpen, setIsScanModalOpen] = useState(false);
  const [isHealthCheckModalOpen, setIsHealthCheckModalOpen] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Hooks
  const navigate = useNavigate();
  const { toast } = useToast();

  // Quick action handlers
  const handleStartScan = useCallback(() => {
    setIsScanModalOpen(true);
  }, []);

  const handleReviewApprovals = useCallback(() => {
    navigate('/approvals');
  }, [navigate]);

  const handleHealthCheck = useCallback(() => {
    setIsHealthCheckModalOpen(true);
  }, []);

  const handleScanStart = useCallback((_scanConfig) => {
    // Refetch scans data after starting a new scan
    refetchSection('scans');
  }, [refetchSection]);

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      await refetch();
      toast.success('Dashboard refreshed');
    } finally {
      setIsRefreshing(false);
    }
  }, [refetch, toast]);

  // Memoized metrics from API data
  const metrics = useMemo(() => {
    if (!data.summary) {
      return null;
    }

    const summary = data.summary;

    return {
      activeAgents: {
        value: summary.agents?.active ?? 0,
        trend: summary.agents?.trend ?? 0,
        sparkline: summary.agents?.sparkline ?? [],
      },
      pendingApprovals: {
        value: summary.approvals?.pending ?? 0,
        trend: summary.approvals?.trend ?? 0,
      },
      vulnerabilities: {
        value: summary.vulnerabilities?.open ?? 0,
        trend: summary.vulnerabilities?.trend ?? 0,
        sparkline: summary.vulnerabilities?.sparkline ?? [],
      },
      patchesDeployed: {
        value: summary.patches?.deployed ?? 0,
        trend: summary.patches?.trend ?? 0,
        sparkline: summary.patches?.sparkline ?? [],
      },
      sandboxTests: {
        value: summary.sandbox?.running ?? 0,
        status: summary.sandbox?.status ?? 'healthy',
      },
      anomalies: {
        value: summary.anomalies?.count ?? 0,
        status: summary.anomalies?.count > 0 ? 'warning' : 'healthy',
      },
    };
  }, [data.summary]);

  // Memoized chart data
  const vulnerabilityTrend = useMemo(() => {
    if (!data.summary?.vulnerabilities?.history) {
      return {
        data: [245, 232, 220, 210, 198, 185, 178, 172, 168, 165, 162, 160, 158, 157, 156],
        labels: ['Jan 6', 'Jan 8', 'Jan 10', 'Jan 13', 'Jan 15', 'Jan 17', 'Jan 20', 'Jan 22', 'Jan 24', 'Jan 27', 'Jan 29', 'Feb 3', 'Feb 7', 'Feb 10', 'Feb 17'],
      };
    }

    return {
      data: data.summary.vulnerabilities.history.map((d) => d.value),
      labels: data.summary.vulnerabilities.history.map((d) => d.label),
    };
  }, [data.summary]);

  const severityDistribution = useMemo(() => {
    if (!data.summary?.vulnerabilities?.severity) {
      return {
        data: [18, 47, 62, 29],
        labels: ['Critical', 'High', 'Medium', 'Low'],
        colors: ['critical', 'warning', 'olive', 'surface'],
      };
    }

    const severity = data.summary.vulnerabilities.severity;
    return {
      data: [severity.critical ?? 0, severity.high ?? 0, severity.medium ?? 0, severity.low ?? 0],
      labels: ['Critical', 'High', 'Medium', 'Low'],
      colors: ['critical', 'warning', 'olive', 'surface'],
    };
  }, [data.summary]);

  const graphMetrics = useMemo(() => {
    if (!data.health?.graphRag) {
      return {
        nodes: 284000,
        edges: 891000,
        queries: 42800,
        avgLatency: 85,
      };
    }

    return {
      nodes: data.health.graphRag.nodes ?? 0,
      edges: data.health.graphRag.edges ?? 0,
      queries: data.health.graphRag.queries24h ?? 0,
      avgLatency: data.health.graphRag.avgLatencyMs ?? 0,
    };
  }, [data.health]);

  const approvalFunnel = useMemo(() => {
    if (!data.summary?.approvals?.funnel) {
      return {
        data: [1247, 1089, 956, 892],
        labels: ['Detected', 'Patched', 'Approved', 'Deployed'],
      };
    }

    const funnel = data.summary.approvals.funnel;
    return {
      data: [funnel.detected ?? 0, funnel.patched ?? 0, funnel.approved ?? 0, funnel.deployed ?? 0],
      labels: ['Detected', 'Patched', 'Approved', 'Deployed'],
    };
  }, [data.summary]);

  // Activities from scans data
  const activities = useMemo(() => {
    if (!data.scans || data.scans.length === 0) {
      // Return mock activities as fallback
      return [
        {
          id: 'act-001',
          type: 'vulnerability_detected',
          title: 'SQL Injection in payment query handler',
          description: 'CWE-89: Parameterized query bypass detected in transaction_query.py by scanner-agent-019',
          timestamp: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
          severity: 'critical',
          isRead: false,
          metadata: { file: 'src/api/handlers/transaction_query.py', repository: 'payment-service' },
        },
        {
          id: 'act-002',
          type: 'vulnerability_detected',
          title: 'Prompt injection vector in agent input parser',
          description: 'CWE-77: Agent input parser vulnerable to adversarial prompt manipulation',
          timestamp: new Date(Date.now() - 12 * 60 * 1000).toISOString(),
          severity: 'critical',
          isRead: false,
          metadata: { file: 'src/agents/input_parser.py', repository: 'agent-orchestrator' },
        },
        {
          id: 'act-003',
          type: 'patch_approved',
          title: 'XSS mitigation patch approved for frontend-app',
          description: 'Patch #PR-4,291 approved by Security Engineer after sandbox validation',
          timestamp: new Date(Date.now() - 25 * 60 * 1000).toISOString(),
          severity: 'high',
          isRead: true,
          metadata: { approvalId: 'apr-047' },
        },
        {
          id: 'act-004',
          type: 'agent_completed',
          title: 'Reviewer Agent #12 completed analysis',
          description: 'Code review completed for 47 files across 3 repositories (892 total issues found)',
          timestamp: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
          isRead: true,
          metadata: { agent: 'Reviewer #12', agentId: 'reviewer-agent-012', repository: 'core-api' },
        },
        {
          id: 'act-005',
          type: 'patch_deployed',
          title: 'SSRF protection deployed to graphrag-engine',
          description: 'Patch #PR-4,287 deployed via ArgoCD to production EKS cluster',
          timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
          severity: 'high',
          isRead: true,
          metadata: { repository: 'graphrag-engine' },
        },
        {
          id: 'act-006',
          type: 'scan_completed',
          title: 'Full SAST/DAST scan completed',
          description: 'Security scan of data-pipeline found 31 vulnerabilities (8 critical, 12 high)',
          timestamp: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
          isRead: true,
          metadata: { repository: 'data-pipeline', scanId: 'scan-006' },
        },
      ];
    }

    // Transform scan data to activity format
    return data.scans.map((scan) => ({
      id: scan.id,
      type: scan.status === 'completed' ? 'scan_completed' : 'scan_in_progress',
      title: `Security scan ${scan.status}`,
      description: `Scan of ${scan.repositoryName || 'repository'} - ${scan.vulnerabilities || 0} vulnerabilities found`,
      timestamp: scan.completedAt || scan.startedAt,
      severity: scan.vulnerabilities > 10 ? 'high' : scan.vulnerabilities > 0 ? 'medium' : 'low',
      isRead: true,
      metadata: { repository: scan.repositoryName, scanId: scan.id },
    }));
  }, [data.scans]);

  // Widget renderer function
  const renderWidget = useCallback((widgetId) => {
    // Show loading skeleton if initial load
    if (isInitialLoading && !metrics) {
      return (
        <div className="h-full flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-aura-500" />
        </div>
      );
    }

    switch (widgetId) {
      case 'active-agents':
        return (
          <MetricCard
            title="Active Agents"
            value={metrics?.activeAgents?.value ?? 0}
            icon={CpuChipIcon}
            trend={metrics?.activeAgents?.trend}
            trendLabel="vs last hour"
            iconColor="aura"
            loading={loading.summary}
            className="h-full border-0 shadow-none rounded-none"
          />
        );

      case 'pending-approvals':
        return (
          <MetricCard
            title="Pending Approvals"
            value={metrics?.pendingApprovals?.value ?? 0}
            icon={ClockIcon}
            trend={metrics?.pendingApprovals?.trend}
            trendInverse={true}
            trendLabel="vs yesterday"
            iconColor="warning"
            status={metrics?.pendingApprovals?.value > 5 ? 'warning' : 'healthy'}
            statusLabel={metrics?.pendingApprovals?.value > 5 ? 'Needs attention' : 'On track'}
            loading={loading.summary}
            className="h-full border-0 shadow-none rounded-none"
          />
        );

      case 'vulnerabilities':
        return (
          <MetricCard
            title="Open Vulnerabilities"
            value={metrics?.vulnerabilities?.value ?? 0}
            icon={BugAntIcon}
            trend={metrics?.vulnerabilities?.trend}
            trendInverse={true}
            trendLabel="vs last week"
            iconColor="critical"
            loading={loading.summary}
            className="h-full border-0 shadow-none rounded-none"
          />
        );

      case 'patches-deployed':
        return (
          <MetricCard
            title="Patches Deployed"
            value={metrics?.patchesDeployed?.value ?? 0}
            icon={ShieldCheckIcon}
            trend={metrics?.patchesDeployed?.trend}
            trendLabel="this month"
            iconColor="olive"
            loading={loading.summary}
            className="h-full border-0 shadow-none rounded-none"
          />
        );

      case 'sandbox-tests':
        return (
          <MetricCard
            title="Sandbox Tests"
            value={metrics?.sandboxTests?.value ?? 0}
            icon={BeakerIcon}
            status={metrics?.sandboxTests?.status}
            statusLabel="Running"
            subtitle="in progress"
            iconColor="aura"
            loading={loading.summary}
            className="h-full border-0 shadow-none rounded-none"
          />
        );

      case 'anomalies':
        return (
          <MetricCard
            title="Anomalies"
            value={metrics?.anomalies?.value ?? 0}
            icon={ExclamationTriangleIcon}
            status={metrics?.anomalies?.status}
            statusLabel={`${metrics?.anomalies?.value ?? 0} active`}
            subtitle="last 24 hours"
            iconColor="warning"
            loading={loading.summary}
            className="h-full border-0 shadow-none rounded-none"
          />
        );

      case 'vulnerability-trend':
        return (
          <div className="h-full flex flex-col">
            <LineChart
              data={vulnerabilityTrend.data}
              labels={vulnerabilityTrend.labels}
              title="Vulnerability Trend"
              subtitle="15-day rolling history"
              color="critical"
              height={280}
              yAxisLabel="Vulnerability Count"
              className="flex-1 border-0 shadow-none rounded-none"
            />
          </div>
        );

      case 'severity-distribution':
        return (
          <div className="h-full">
            <DonutChart
              data={severityDistribution.data}
              labels={severityDistribution.labels}
              colors={severityDistribution.colors}
              title="Severity Distribution"
              size={180}
              strokeWidth={32}
              centerValue={severityDistribution.data.reduce((a, b) => a + b, 0)}
              centerLabel="Total"
              className="h-full border-0 shadow-none rounded-none"
            />
          </div>
        );

      case 'graph-metrics':
        return (
          <div className="h-full p-4 overflow-y-auto">
            <h3 className="text-base font-semibold text-surface-900 dark:text-surface-100 mb-4">
              Graph Metrics
            </h3>
            <div className="space-y-3">
              <div className="flex items-center gap-3 p-3 rounded-lg border border-surface-200 dark:border-surface-700 hover:border-aura-300 dark:hover:border-aura-600 hover:bg-surface-50 dark:hover:bg-surface-800/50 transition-colors">
                <div className="p-1.5 rounded-lg bg-aura-100 dark:bg-aura-900/30">
                  <CircleStackIcon className="w-4 h-4 text-aura-600 dark:text-aura-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-surface-500 dark:text-surface-400">Nodes</p>
                  <p className="text-sm font-semibold text-surface-900 dark:text-surface-100">
                    {graphMetrics.nodes.toLocaleString()}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 rounded-lg border border-surface-200 dark:border-surface-700 hover:border-aura-300 dark:hover:border-aura-600 hover:bg-surface-50 dark:hover:bg-surface-800/50 transition-colors">
                <div className="p-1.5 rounded-lg bg-olive-100 dark:bg-olive-900/30">
                  <ArrowsRightLeftIcon className="w-4 h-4 text-olive-600 dark:text-olive-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-surface-500 dark:text-surface-400">Edges</p>
                  <p className="text-sm font-semibold text-surface-900 dark:text-surface-100">
                    {graphMetrics.edges.toLocaleString()}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 rounded-lg border border-surface-200 dark:border-surface-700 hover:border-aura-300 dark:hover:border-aura-600 hover:bg-surface-50 dark:hover:bg-surface-800/50 transition-colors">
                <div className="p-1.5 rounded-lg bg-warning-100 dark:bg-warning-900/30">
                  <BoltIcon className="w-4 h-4 text-warning-600 dark:text-warning-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-surface-500 dark:text-surface-400">Queries (24h)</p>
                  <p className="text-sm font-semibold text-surface-900 dark:text-surface-100">
                    {graphMetrics.queries.toLocaleString()}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 rounded-lg border border-surface-200 dark:border-surface-700 hover:border-aura-300 dark:hover:border-aura-600 hover:bg-surface-50 dark:hover:bg-surface-800/50 transition-colors">
                <div className="p-1.5 rounded-lg bg-surface-100 dark:bg-surface-700">
                  <ClockIcon className="w-4 h-4 text-surface-600 dark:text-surface-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-surface-500 dark:text-surface-400">Avg Latency</p>
                  <p className="text-sm font-semibold text-surface-900 dark:text-surface-100">
                    {graphMetrics.avgLatency}ms
                  </p>
                </div>
              </div>
            </div>
          </div>
        );

      case 'activity-feed':
        return (
          <div data-tour="activity-feed" className="h-full overflow-y-auto">
            <ActivityFeed
              activities={activities}
              title="Recent Activity"
              maxItems={6}
              enableNavigation={true}
              className="h-full border-0 shadow-none rounded-none"
            />
          </div>
        );

      case 'agent-status':
        return (
          <AgentStatusWidget
            agents={data.agents}
            loading={loading.agents}
            error={error.agents}
            onRetry={() => refetchSection('agents')}
          />
        );

      case 'system-health':
        return (
          <SystemHealthWidget
            health={data.health}
            loading={loading.health}
            error={error.health}
            onRetry={() => refetchSection('health')}
          />
        );

      case 'quick-actions':
        return (
          <QuickActionsWidget
            onStartScan={handleStartScan}
            onReviewApprovals={handleReviewApprovals}
            onHealthCheck={handleHealthCheck}
          />
        );

      case 'security-alerts':
        return <SecurityAlertsWidget />;

      case 'approval-funnel':
        return (
          <div className="h-full p-4">
            <h3 className="text-base font-semibold text-surface-900 dark:text-surface-100 mb-4">
              Approval Funnel
            </h3>
            <div className="space-y-3">
              {approvalFunnel.labels.map((label, index) => {
                const value = approvalFunnel.data[index];
                const maxValue = approvalFunnel.data[0];
                const percentage = maxValue > 0 ? (value / maxValue) * 100 : 0;
                return (
                  <div key={label} className="p-3 rounded-lg border border-surface-200 dark:border-surface-700 hover:border-aura-300 dark:hover:border-aura-600 hover:bg-surface-50 dark:hover:bg-surface-800/50 transition-colors space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-surface-600 dark:text-surface-400">{label}</span>
                      <span className="font-medium text-surface-900 dark:text-surface-100">{value}</span>
                    </div>
                    <div className="h-2 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-aura-500 rounded-full transition-all duration-500"
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );

      // =====================================================================
      // New ADR-064 Widgets
      // =====================================================================
      case 'mttr':
        return (
          <MetricCard
            title="Mean Time to Remediate"
            value="4.2h"
            icon={ClockIcon}
            trend={-12}
            trendLabel="vs last week"
            iconColor="aura"
            subtitle="Across 156 open vulnerabilities"
            loading={loading.summary}
            className="h-full border-0 shadow-none rounded-none"
          />
        );

      case 'cve-trend':
        return (
          <div className="h-full flex flex-col">
            <LineChart
              data={[12, 15, 18, 14, 22, 19, 16, 20, 17, 15, 13, 11, 14, 12, 10]}
              labels={vulnerabilityTrend.labels}
              title="CVE Trend"
              subtitle="30-day CVE discoveries"
              color="critical"
              height={280}
              className="flex-1 border-0 shadow-none rounded-none"
            />
          </div>
        );

      case 'agent-health-grid':
        return (
          <AgentStatusWidget
            agents={data.agents}
            loading={loading.agents}
            error={error.agents}
            onRetry={() => refetchSection('agents')}
          />
        );

      case 'sandbox-utilization':
        return (
          <MetricCard
            title="Sandbox Utilization"
            value="60%"
            icon={BeakerIcon}
            status="healthy"
            statusLabel="12 of 20 in use"
            subtitle="8 available for new deployments"
            iconColor="aura"
            loading={loading.health}
            className="h-full border-0 shadow-none rounded-none"
          />
        );

      case 'environment-status':
        return (
          <div className="h-full p-4">
            <h3 className="text-base font-semibold text-surface-900 dark:text-surface-100 mb-4">
              Environment Status
            </h3>
            <div className="space-y-2">
              {['dev', 'qa', 'prod'].map((env) => (
                <div key={env} className="flex items-center justify-between p-3 rounded-lg border border-surface-200 dark:border-surface-700">
                  <span className="font-medium text-surface-700 dark:text-surface-300 capitalize">{env}</span>
                  <span className="flex items-center gap-1.5 text-olive-600 dark:text-olive-400 text-sm">
                    <span className="w-2 h-2 bg-olive-500 rounded-full" />
                    Healthy
                  </span>
                </div>
              ))}
            </div>
          </div>
        );

      case 'gpu-jobs-queued':
        return (
          <MetricCard
            title="GPU Jobs Queued"
            value={18}
            icon={CpuChipIcon}
            trend={5}
            trendInverse={true}
            trendLabel="vs yesterday"
            iconColor="warning"
            status="warning"
            statusLabel="3 pending GPU allocation"
            loading={loading.summary}
            className="h-full border-0 shadow-none rounded-none"
          />
        );

      case 'deployment-velocity':
        return (
          <MetricCard
            title="Deployment Velocity"
            value="24.7"
            subtitle="deploys/day across 12 repositories"
            icon={ShieldCheckIcon}
            trend={15}
            trendLabel="7-day avg"
            iconColor="olive"
            loading={loading.summary}
            className="h-full border-0 shadow-none rounded-none"
          />
        );

      case 'code-quality-score':
        return (
          <MetricCard
            title="Code Quality"
            value="87"
            subtitle="Weighted average across 12 repositories"
            icon={ShieldCheckIcon}
            trend={3}
            trendLabel="vs last month"
            iconColor="aura"
            loading={loading.summary}
            className="h-full border-0 shadow-none rounded-none"
          />
        );

      case 'test-coverage-trend':
        return (
          <div className="h-full flex flex-col">
            <LineChart
              data={[72, 74, 73, 76, 78, 77, 79, 81, 80, 82, 84, 83, 85, 86, 87]}
              labels={vulnerabilityTrend.labels}
              title="Test Coverage"
              subtitle="Coverage percentage trend"
              color="olive"
              height={280}
              className="flex-1 border-0 shadow-none rounded-none"
            />
          </div>
        );

      case 'pr-velocity':
        return (
          <div className="h-full p-4">
            <h3 className="text-base font-semibold text-surface-900 dark:text-surface-100 mb-4">
              PR Velocity by Team
            </h3>
            <div className="space-y-3">
              {[
                { team: 'Platform', prs: 87 },
                { team: 'Security', prs: 64 },
                { team: 'Agent Ops', prs: 52 },
                { team: 'Frontend', prs: 41 },
                { team: 'Data', prs: 38 },
                { team: 'Infrastructure', prs: 29 },
              ].map(({ team, prs }) => (
                <div key={team} className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span className="text-surface-600 dark:text-surface-400">{team}</span>
                    <span className="font-medium text-surface-900 dark:text-surface-100">{prs} PRs/week</span>
                  </div>
                  <div className="h-2 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-aura-500 rounded-full"
                      style={{ width: `${(prs / 87) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        );

      case 'compliance-progress':
        return (
          <MetricCard
            title="Compliance"
            value="78%"
            subtitle="NIST 800-53 controls implemented"
            icon={ShieldCheckIcon}
            trend={5}
            trendLabel="this quarter"
            iconColor="aura"
            status="healthy"
            statusLabel="312 of 400 controls satisfied"
            loading={loading.summary}
            className="h-full border-0 shadow-none rounded-none"
          />
        );

      case 'risk-posture':
        return (
          <MetricCard
            title="Risk Posture"
            value="82"
            subtitle="Composite score across 214 agents and 12 repos"
            icon={ShieldCheckIcon}
            status="healthy"
            statusLabel="Low risk"
            iconColor="olive"
            loading={loading.summary}
            className="h-full border-0 shadow-none rounded-none"
          />
        );

      case 'key-incidents':
        return (
          <div className="h-full p-4 overflow-auto">
            <h3 className="text-base font-semibold text-surface-900 dark:text-surface-100 mb-4">
              Key Incidents
            </h3>
            <div className="space-y-2">
              {[
                { id: 'INC-047', title: 'Sandbox escape attempt detected in payment-service', severity: 'high', time: '45m ago' },
                { id: 'INC-046', title: 'Agent orchestrator latency spike (12x baseline)', severity: 'medium', time: '3h ago' },
                { id: 'INC-045', title: 'GraphRAG node replication lag across 3 AZs', severity: 'medium', time: '8h ago' },
                { id: 'INC-044', title: 'LLM quota threshold reached (67% consumed)', severity: 'medium', time: '1d ago' },
                { id: 'INC-043', title: 'Failed deployment rollback on data-pipeline', severity: 'low', time: '2d ago' },
                { id: 'INC-042', title: 'TLS certificate rotation for neptune.aura.local', severity: 'low', time: '3d ago' },
              ].map((incident) => (
                <div key={incident.id} className="p-3 rounded-lg border border-surface-200 dark:border-surface-700">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-surface-900 dark:text-surface-100">{incident.title}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      incident.severity === 'high' ? 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400' :
                      incident.severity === 'medium' ? 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400' :
                      'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-400'
                    }`}>
                      {incident.severity}
                    </span>
                  </div>
                  <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">{incident.time}</p>
                </div>
              ))}
            </div>
          </div>
        );

      case 'monthly-cost':
        return (
          <MetricCard
            title="Monthly Cost"
            value="$148K"
            icon={ExclamationTriangleIcon}
            trend={6}
            trendInverse={true}
            trendLabel="vs last month"
            iconColor="surface"
            subtitle="214 agents, 20 sandboxes, 3 AZs"
            loading={loading.summary}
            className="h-full border-0 shadow-none rounded-none"
          />
        );

      case 'cost-trend':
        return (
          <div className="h-full flex flex-col">
            <LineChart
              data={[112, 118, 122, 126, 129, 132, 135, 138, 140, 142, 144, 145, 146, 147, 148]}
              labels={vulnerabilityTrend.labels}
              title="Cost Trend"
              subtitle="30-day infrastructure cost ($K) across all services"
              color="aura"
              height={280}
              className="flex-1 border-0 shadow-none rounded-none"
            />
          </div>
        );

      // =====================================================================
      // ADR-083: Runtime Agent Security Platform Widgets
      // Enterprise-scale synthetic data (~214 agents, ~1.4M events/day)
      // Aligned with DEFAULT_SUMMARY, DEFAULT_AGENTS, DEFAULT_HEALTH
      // =====================================================================
      case 'red-team-block-rate':
        return (
          <MetricCard
            title="Red Team Block Rate"
            value="96.8%"
            icon={ShieldCheckIcon}
            trend={1.4}
            trendLabel="vs last campaign"
            iconColor="olive"
            status="healthy"
            statusLabel="726 of 750 attacks blocked"
            subtitle="12 AURA-ATT&CK campaigns completed"
            loading={loading.summary}
            className="h-full border-0 shadow-none rounded-none"
          />
        );

      case 'shadow-agents':
        return (
          <MetricCard
            title="Shadow Agents"
            value={7}
            icon={ExclamationTriangleIcon}
            trend={-3}
            trendInverse={true}
            trendLabel="vs last week"
            iconColor="critical"
            status="warning"
            statusLabel="7 of 214 unregistered"
            subtitle="Discovered via interceptor traffic analysis"
            loading={loading.summary}
            className="h-full border-0 shadow-none rounded-none"
          />
        );

      case 'behavioral-anomalies':
        return (
          <div className="h-full p-4 overflow-y-auto">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-base font-semibold text-surface-900 dark:text-surface-100">
                Behavioral Anomalies
              </h3>
              <span className="text-xs text-surface-400 dark:text-surface-500">
                {metrics?.anomalies?.value ?? 23} in last 24h
              </span>
            </div>
            <div className="space-y-2">
              {[
                { agent: 'coder-agent-047', env: 'prod', type: 'Token consumption spike', deviation: '4.7\u03C3', time: '3m ago', severity: 'critical', baseline: '12K tok/req \u2192 89K tok/req', measure: 'LLM token usage 7.4x above baseline during patch generation for CVE-2024-8912' },
                { agent: 'reviewer-agent-012', env: 'prod', type: 'Approval bypass attempt', deviation: '5.1\u03C3', time: '8m ago', severity: 'critical', baseline: '0 bypasses/day \u2192 3 attempts', measure: 'Agent attempted to skip HITL approval on 3 critical patches in 15 minutes' },
                { agent: 'orchestrator-003', env: 'prod', type: 'Cross-tenant data access', deviation: '4.2\u03C3', time: '22m ago', severity: 'critical', baseline: '0 cross-tenant \u2192 7 queries', measure: 'GraphRAG queries accessing code nodes outside assigned tenant boundary' },
                { agent: 'scanner-agent-019', env: 'staging', type: 'Tool call frequency', deviation: '3.4\u03C3', time: '41m ago', severity: 'high', baseline: '45 calls/h \u2192 312 calls/h', measure: 'Security scanner tool invocation rate 6.9x normal during repo-wide scan' },
                { agent: 'coder-agent-108', env: 'prod', type: 'Response latency degradation', deviation: '3.1\u03C3', time: '1h ago', severity: 'high', baseline: '120ms avg \u2192 890ms avg', measure: 'Agent response time degraded 7.4x, indicating possible resource contention' },
                { agent: 'validator-agent-006', env: 'staging', type: 'Error rate elevation', deviation: '2.9\u03C3', time: '1.5h ago', severity: 'medium', baseline: '2.1% error \u2192 14.8% error', measure: 'Validation failure rate increased 7x during sandbox patch testing' },
                { agent: 'mcp-server-015', env: 'prod', type: 'Unusual API endpoint access', deviation: '2.7\u03C3', time: '2h ago', severity: 'medium', baseline: '3 endpoints \u2192 28 endpoints', measure: 'MCP tool server accessing 9.3x more distinct API endpoints than baseline' },
                { agent: 'coder-agent-091', env: 'prod', type: 'Memory consumption drift', deviation: '2.4\u03C3', time: '3h ago', severity: 'medium', baseline: '512MB avg \u2192 1.8GB peak', measure: 'Agent memory usage 3.5x above baseline, potential context window overflow' },
                { agent: 'reviewer-agent-034', env: 'prod', type: 'Output token ratio shift', deviation: '2.2\u03C3', time: '4h ago', severity: 'low', baseline: '1:3.2 in/out \u2192 1:8.7 in/out', measure: 'Output verbosity increased 2.7x, generating unusually detailed review comments' },
                { agent: 'scanner-agent-007', env: 'staging', type: 'Scan duration anomaly', deviation: '2.1\u03C3', time: '5h ago', severity: 'low', baseline: '45s avg \u2192 142s avg', measure: 'Security scan taking 3.2x longer than baseline on auth-service repository' },
              ].map((anomaly, idx) => (
                <div key={idx} className="p-3 rounded-lg border border-surface-200 dark:border-surface-700">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-surface-900 dark:text-surface-100">{anomaly.type}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium flex-shrink-0 ml-2 ${
                      anomaly.severity === 'critical' ? 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400' :
                      anomaly.severity === 'high' ? 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400' :
                      anomaly.severity === 'low' ? 'bg-surface-100 text-surface-500 dark:bg-surface-700 dark:text-surface-500' :
                      'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-400'
                    }`}>
                      {anomaly.deviation}
                    </span>
                  </div>
                  <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">{anomaly.measure}</p>
                  <p className="text-xs text-surface-400 dark:text-surface-500 mt-0.5 italic">{anomaly.baseline}</p>
                  <div className="flex items-center justify-between mt-1.5">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-xs text-surface-500 dark:text-surface-400 truncate">{anomaly.agent}</span>
                      <span className="text-xs px-1.5 py-0.5 rounded bg-surface-100 dark:bg-surface-700 text-surface-500 dark:text-surface-400 flex-shrink-0">{anomaly.env}</span>
                    </div>
                    <span className="text-xs text-surface-400 dark:text-surface-500 flex-shrink-0 ml-2">{anomaly.time}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );

      case 'correlation-rate':
        return (
          <MetricCard
            title="Correlation Rate"
            value="81.4%"
            subtitle="1,847 of 2,269 runtime events traced to source code"
            icon={ShieldCheckIcon}
            trend={4.2}
            trendLabel="vs last month"
            iconColor="aura"
            loading={loading.summary}
            className="h-full border-0 shadow-none rounded-none"
          />
        );

      case 'red-team-by-category':
        return (
          <div className="h-full p-4 overflow-y-auto">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-base font-semibold text-surface-900 dark:text-surface-100">
                Red Team Results by Category
              </h3>
              <span className="text-xs text-surface-400 dark:text-surface-500">
                750 tests | 12 campaigns
              </span>
            </div>
            <div className="space-y-2">
              {[
                { category: 'Prompt Injection', blocked: 151, detected: 4, total: 156, measure: 'LLM input manipulation attempts against agent fleet' },
                { category: 'Tool Abuse', blocked: 99, detected: 2, total: 102, measure: 'Unauthorized tool invocation via agent confusion' },
                { category: 'Agent Confusion', blocked: 84, detected: 2, total: 87, measure: 'Cross-agent role impersonation and task hijacking' },
                { category: 'Data Exfiltration', blocked: 81, detected: 2, total: 84, measure: 'Attempts to extract code/vuln data from sandboxes' },
                { category: 'Privilege Escalation', blocked: 96, detected: 1, total: 98, measure: 'HITL approval bypass and role elevation' },
                { category: 'Denial of Service', blocked: 70, detected: 2, total: 72, measure: 'Agent queue flooding and resource exhaustion' },
                { category: 'Supply Chain', blocked: 75, detected: 2, total: 78, measure: 'Malicious dependency injection via patch generation' },
                { category: 'Evasion', blocked: 70, detected: 2, total: 73, measure: 'Guardrail bypass and detection avoidance techniques' },
              ].map(({ category, blocked, detected, total, measure }) => (
                <div key={category} className="space-y-1" title={measure}>
                  <div className="flex justify-between text-xs">
                    <span className="text-surface-600 dark:text-surface-400 truncate">{category}</span>
                    <div className="flex items-center gap-2 ml-2 flex-shrink-0">
                      <span className="text-olive-600 dark:text-olive-400">{blocked}</span>
                      {detected > 0 && (
                        <span className="text-warning-600 dark:text-warning-400">{detected}</span>
                      )}
                      {total - blocked - detected > 0 && (
                        <span className="text-critical-600 dark:text-critical-400">{total - blocked - detected}</span>
                      )}
                      <span className="font-medium text-surface-900 dark:text-surface-100">/{total}</span>
                    </div>
                  </div>
                  <div className="h-2 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden flex">
                    <div
                      className="h-full bg-olive-500"
                      style={{ width: `${(blocked / total) * 100}%` }}
                    />
                    {detected > 0 && (
                      <div
                        className="h-full bg-warning-500"
                        style={{ width: `${(detected / total) * 100}%` }}
                      />
                    )}
                    {total - blocked - detected > 0 && (
                      <div
                        className="h-full bg-critical-500"
                        style={{ width: `${((total - blocked - detected) / total) * 100}%` }}
                      />
                    )}
                  </div>
                </div>
              ))}
              <div className="flex items-center gap-4 mt-3 pt-3 border-t border-surface-200 dark:border-surface-700">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-olive-500" />
                  <span className="text-xs text-surface-500 dark:text-surface-400">Blocked (726)</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-warning-500" />
                  <span className="text-xs text-surface-500 dark:text-surface-400">Detected (17)</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-critical-500" />
                  <span className="text-xs text-surface-500 dark:text-surface-400">Bypassed (7)</span>
                </div>
              </div>
            </div>
          </div>
        );

      case 'agent-traffic-volume':
        return (
          <div className="h-full flex flex-col">
            <LineChart
              data={[48200, 52100, 57800, 54300, 61200, 58900, 63400, 67100, 64800, 71200, 74500, 72800, 78100, 82400, 79600]}
              labels={vulnerabilityTrend.labels}
              title="Agent Traffic Volume"
              subtitle="Events captured per hour across 214 agents (1.4M/day)"
              color="aura"
              height={280}
              yAxisLabel="Events / Hour"
              className="flex-1 border-0 shadow-none rounded-none"
            />
          </div>
        );

      case 'agent-traffic-by-type':
        return (
          <div className="h-full">
            <DonutChart
              data={[587400, 392600, 210800, 140200, 58400, 11200]}
              labels={['Tool Calls', 'LLM Requests', 'Agent Comms', 'API Gateway', 'MCP Server', 'System']}
              colors={['#3B82F6', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899', '#6B7280']}
              title="Agent Traffic by Type"
              size={180}
              strokeWidth={32}
              centerValue="1.4M"
              centerLabel="events/day"
              className="h-full border-0 shadow-none rounded-none"
            />
          </div>
        );

      // =================================================================
      // ADR-084: Native Vulnerability Scanner Widgets
      // =================================================================
      case 'scanner-findings-by-severity':
        return <FindingsBySeverityWidget className="h-full border-0 shadow-none rounded-none" />;
      case 'scanner-active-scans':
        return <ActiveScansWidget className="h-full border-0 shadow-none rounded-none" />;
      case 'scanner-pipeline-progress':
        return <ScanPipelineProgressWidget className="h-full border-0 shadow-none rounded-none" />;
      case 'scanner-true-positive-rate':
        return <TruePositiveRateWidget className="h-full border-0 shadow-none rounded-none" />;
      case 'scanner-llm-token-spend':
        return <LLMTokenSpendWidget className="h-full border-0 shadow-none rounded-none" />;
      case 'scanner-alarm-status':
        return <ScannerAlarmStatusWidget className="h-full border-0 shadow-none rounded-none" />;
      case 'scanner-recent-activity':
        return <RecentScanActivityWidget className="h-full border-0 shadow-none rounded-none" />;
      case 'scanner-findings-requiring-approval':
        return <FindingsRequiringApprovalWidget className="h-full border-0 shadow-none rounded-none" />;
      case 'scanner-duration-trend':
        return <ScanDurationTrendWidget className="h-full border-0 shadow-none rounded-none" />;
      case 'scanner-stage-duration':
        return <StageDurationWaterfallWidget className="h-full border-0 shadow-none rounded-none" />;
      case 'scanner-findings-by-cwe':
        return <FindingsByCWEWidget className="h-full border-0 shadow-none rounded-none" />;
      case 'scanner-llm-latency':
        return <LLMLatencyWidget className="h-full border-0 shadow-none rounded-none" />;
      case 'scanner-concurrent-utilization':
        return <ConcurrentUtilizationWidget className="h-full border-0 shadow-none rounded-none" />;
      case 'scanner-critical-findings-trend':
        return <CriticalFindingsTrendWidget className="h-full border-0 shadow-none rounded-none" />;
      case 'scanner-queue-depth':
        return <ScanQueueDepthWidget className="h-full border-0 shadow-none rounded-none" />;
      case 'scanner-candidate-funnel':
        return <CandidateFunnelWidget className="h-full border-0 shadow-none rounded-none" />;
      case 'scanner-findings-by-language':
        return <FindingsByLanguageWidget className="h-full border-0 shadow-none rounded-none" />;
      case 'scanner-verification-status':
        return <VerificationStatusWidget className="h-full border-0 shadow-none rounded-none" />;
      case 'scanner-cleanup-activity':
        return <CleanupActivityWidget className="h-full border-0 shadow-none rounded-none" />;
      case 'scanner-depth-distribution':
        return <ScanDepthDistributionWidget className="h-full border-0 shadow-none rounded-none" />;

      default:
        return (
          <div className="h-full flex items-center justify-center text-surface-400">
            Widget: {widgetId}
          </div>
        );
    }
  }, [
    metrics,
    isInitialLoading,
    loading,
    error,
    data.agents,
    data.health,
    vulnerabilityTrend,
    severityDistribution,
    graphMetrics,
    activities,
    approvalFunnel,
    handleStartScan,
    handleReviewApprovals,
    handleHealthCheck,
    refetchSection,
  ]);

  // Show full page skeleton on initial load
  if (isInitialLoading) {
    return <PageSkeleton />;
  }

  return (
    <div className="flex-1 overflow-y-auto">
      {/* Header */}
      <div className="bg-white dark:bg-surface-800 border-b border-surface-200 dark:border-surface-700 px-6 py-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 max-w-[1920px] mx-auto">
          <div className="animate-fade-in">
            <h1 className="text-2xl lg:text-3xl font-bold text-surface-900 dark:text-surface-50">
              Security Dashboard
            </h1>
            <p className="text-surface-500 dark:text-surface-400 mt-1 flex items-center gap-2">
              Real-time overview of your code security posture
              {lastUpdated && (
                <span className="text-xs text-surface-400 dark:text-surface-500">
                  Updated {new Date(lastUpdated).toLocaleTimeString()}
                </span>
              )}
            </p>
          </div>

          {/* Quick Actions */}
          <div data-tour="quick-actions" className="flex flex-wrap gap-2 animate-fade-in animation-delay-100">
            <button
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="flex items-center gap-2 px-4 py-2 text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-100 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors disabled:opacity-50"
            >
              <ArrowPathIcon className={`w-5 h-5 ${isRefreshing ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            <QuickAction
              icon={PlayIcon}
              label="Start Scan"
              variant="primary"
              onClick={handleStartScan}
            />
            <QuickAction
              icon={EyeIcon}
              label="Review Approvals"
              onClick={handleReviewApprovals}
            />
            <QuickAction
              icon={HeartIcon}
              label="Health Check"
              onClick={handleHealthCheck}
            />
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="p-6 lg:p-8 xl:px-8 2xl:px-10 max-w-[1920px] mx-auto">
        {/* Centered Search Trigger */}
        <div data-tour="command-palette" className="w-full flex justify-center py-6">
          <DashboardSearchTrigger />
        </div>

        {/* Draggable Dashboard Grid */}
        <div data-tour="dashboard-metrics">
          <DashboardGrid renderWidget={renderWidget} />
        </div>
      </div>

      {/* Modals */}
      <ScanModal
        isOpen={isScanModalOpen}
        onClose={() => setIsScanModalOpen(false)}
        onScanStart={handleScanStart}
      />
      <HealthCheckModal
        isOpen={isHealthCheckModalOpen}
        onClose={() => setIsHealthCheckModalOpen(false)}
      />
    </div>
  );
}
