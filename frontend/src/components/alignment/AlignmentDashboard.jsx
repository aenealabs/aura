/**
 * Project Aura - Alignment Dashboard
 *
 * Real-time visualization of AI alignment health metrics.
 * Displays trust scores, sycophancy detection, transparency compliance,
 * and rollback capability across all agents.
 *
 * Features:
 * - Overall alignment health score with trend
 * - Metric cards for each alignment dimension
 * - Alert management with acknowledge/resolve actions
 * - Agent comparison rankings
 * - Time range filtering
 * - Auto-refresh every 30 seconds
 *
 * Reference: ADR-052 AI Alignment Principles & Human-Machine Collaboration
 */

import { useState, useEffect, useCallback } from 'react';
import {
  ShieldCheckIcon,
  UserGroupIcon,
  EyeIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  MinusIcon,
  BellAlertIcon,
  DocumentChartBarIcon,
  AdjustmentsHorizontalIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import { LineChart, DonutChart } from '../ui/Charts';
import { PageSkeleton, ChartSkeleton, Skeleton } from '../ui/LoadingSkeleton';
import DashboardGrid from '../ui/DashboardGrid';
import MetricCard from '../ui/MetricCard';
import { useToast } from '../ui/Toast';
import {
  getAlignmentHealth,
  getAlerts,
  getTrends,
  getAgentComparisons,
  acknowledgeAlert,
  resolveAlert,
  TimeRanges,
  AlignmentStatus,
  AlertSeverity,
  AlertStatus,
  TrendDirection,
  getStatusColor,
  getStatusBgColor,
  getSeverityColor,
  formatPercent,
  formatScore,
} from '../../services/alignmentApi';

const TIME_RANGE_OPTIONS = [
  { value: TimeRanges.HOUR, label: 'Last Hour' },
  { value: TimeRanges.DAY, label: 'Last 24 Hours' },
  { value: TimeRanges.WEEK, label: 'Last 7 Days' },
  { value: TimeRanges.MONTH, label: 'Last 30 Days' },
];

const REFRESH_INTERVAL = 30000; // 30 seconds

/**
 * Health Score Gauge Component
 */
function HealthScoreGauge({ score, status, loading }) {
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-6">
        <Skeleton className="w-32 h-32 rounded-full" />
        <Skeleton className="w-24 h-4 mt-4" />
      </div>
    );
  }

  const percentage = Math.round(score * 100);
  const circumference = 2 * Math.PI * 45;
  const strokeDashoffset = circumference - (score * circumference);

  const getGaugeColor = () => {
    switch (status) {
      case AlignmentStatus.HEALTHY:
        return 'stroke-olive-500';
      case AlignmentStatus.WARNING:
        return 'stroke-amber-500';
      case AlignmentStatus.CRITICAL:
        return 'stroke-critical-500';
      default:
        return 'stroke-surface-400';
    }
  };

  return (
    <div className="flex flex-col items-center justify-center p-6">
      <div className="relative w-32 h-32">
        <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
          {/* Background circle */}
          <circle
            className="stroke-surface-200 dark:stroke-surface-700"
            strokeWidth="8"
            fill="transparent"
            r="45"
            cx="50"
            cy="50"
          />
          {/* Progress circle */}
          <circle
            className={`${getGaugeColor()} transition-all duration-500 ease-out`}
            strokeWidth="8"
            strokeLinecap="round"
            fill="transparent"
            r="45"
            cx="50"
            cy="50"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-bold text-surface-900 dark:text-surface-100">
            {percentage}
          </span>
          <span className="text-xs text-surface-500 dark:text-surface-400">/ 100</span>
        </div>
      </div>
      <div className={`mt-3 px-3 py-1 rounded-full text-sm font-medium ${getStatusBgColor(status)} ${getStatusColor(status)}`}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </div>
    </div>
  );
}

/**
 * Helper to convert trend direction to numeric trend for standard MetricCard
 */
function convertTrendDirection(trendDirection, changePercent) {
  if (changePercent === undefined || changePercent === null) return undefined;
  // IMPROVING = positive, DEGRADING = negative (standard MetricCard handles display)
  if (trendDirection === TrendDirection.DEGRADING) {
    return -Math.abs(changePercent);
  }
  return Math.abs(changePercent);
}

/**
 * Alert Card Component
 */
function AlertCard({ alert, onAcknowledge, onResolve }) {
  const getSeverityIcon = () => {
    switch (alert.severity) {
      case AlertSeverity.CRITICAL:
        return <ExclamationTriangleIcon className="w-5 h-5 text-critical-500" />;
      case AlertSeverity.WARNING:
        return <ExclamationTriangleIcon className="w-5 h-5 text-amber-500" />;
      default:
        return <BellAlertIcon className="w-5 h-5 text-blue-500" />;
    }
  };

  const getSeverityBg = () => {
    switch (alert.severity) {
      case AlertSeverity.CRITICAL:
        return 'bg-critical-50 dark:bg-critical-900/20 border-critical-200 dark:border-critical-800';
      case AlertSeverity.WARNING:
        return 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800';
      default:
        return 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800';
    }
  };

  const isActive = alert.status === AlertStatus.ACTIVE;
  const isAcknowledged = alert.status === AlertStatus.ACKNOWLEDGED;

  return (
    <div className={`rounded-lg border p-4 ${getSeverityBg()}`}>
      <div className="flex items-start gap-3">
        {getSeverityIcon()}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-surface-900 dark:text-surface-100">
              {alert.metric_name}
            </span>
            <span className="text-xs text-surface-500 dark:text-surface-400">
              {new Date(alert.triggered_at).toLocaleTimeString()}
            </span>
          </div>
          <p className="mt-1 text-sm text-surface-600 dark:text-surface-300">
            {alert.message}
          </p>
          {alert.agent_id && (
            <p className="mt-1 text-xs text-surface-500 dark:text-surface-400">
              Agent: {alert.agent_id}
            </p>
          )}
          <div className="mt-3 flex items-center gap-2">
            {isActive && (
              <button
                onClick={() => onAcknowledge(alert.alert_id)}
                className="px-3 py-1 text-xs font-medium rounded-md bg-surface-100 dark:bg-surface-700 text-surface-700 dark:text-surface-300 hover:bg-surface-200 dark:hover:bg-surface-600 transition-colors"
              >
                Acknowledge
              </button>
            )}
            {(isActive || isAcknowledged) && (
              <button
                onClick={() => onResolve(alert.alert_id)}
                className="px-3 py-1 text-xs font-medium rounded-md bg-olive-100 dark:bg-olive-900/30 text-olive-700 dark:text-olive-300 hover:bg-olive-200 dark:hover:bg-olive-900/50 transition-colors"
              >
                Resolve
              </button>
            )}
            {alert.status === AlertStatus.RESOLVED && (
              <span className="flex items-center gap-1 text-xs text-olive-600 dark:text-olive-400">
                <CheckCircleIcon className="w-4 h-4" />
                Resolved
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Agent Ranking Component
 */
function AgentRanking({ comparison, loading }) {
  if (loading) {
    return (
      <div className="space-y-2">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );
  }

  if (!comparison || !comparison.agents || comparison.agents.length === 0) {
    return (
      <div className="text-center py-4 text-surface-500 dark:text-surface-400">
        No agent data available
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {comparison.agents.slice(0, 5).map((agent, index) => (
        <div
          key={agent.agent_id}
          className="flex items-center gap-3 p-2 rounded-lg bg-surface-50 dark:bg-surface-900/50"
        >
          <span className={`w-6 h-6 flex items-center justify-center rounded-full text-xs font-bold ${
            index === 0 ? 'bg-olive-100 text-olive-700 dark:bg-olive-900/50 dark:text-olive-300' :
            index === 1 ? 'bg-surface-200 text-surface-700 dark:bg-surface-700 dark:text-surface-300' :
            index === 2 ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300' :
            'bg-surface-100 text-surface-600 dark:bg-surface-800 dark:text-surface-400'
          }`}>
            {index + 1}
          </span>
          <div className="flex-1 min-w-0">
            <span className="text-sm font-medium text-surface-900 dark:text-surface-100 truncate block">
              {agent.agent_id}
            </span>
          </div>
          <span className="text-sm font-semibold text-surface-700 dark:text-surface-300">
            {formatScore(agent.value)}
          </span>
        </div>
      ))}
    </div>
  );
}

/**
 * Main Alignment Dashboard Component
 */
export default function AlignmentDashboard() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [timeRange, setTimeRange] = useState(TimeRanges.DAY);
  const [health, setHealth] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [trends, setTrends] = useState([]);
  const [comparisons, setComparisons] = useState([]);
  const [error, setError] = useState(null);

  const { showToast } = useToast();

  const fetchData = useCallback(async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      }

      const [healthData, alertsData, trendsData, comparisonsData] = await Promise.all([
        getAlignmentHealth(),
        getAlerts({ status: null }), // Get all alerts
        getTrends(timeRange),
        getAgentComparisons(timeRange),
      ]);

      setHealth(healthData);
      setAlerts(alertsData);
      setTrends(trendsData);
      setComparisons(comparisonsData);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch alignment data:', err);
      setError(err.message);
      if (isRefresh) {
        showToast('Failed to refresh alignment data', 'error');
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [timeRange, showToast]);

  // Initial load
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Auto-refresh
  useEffect(() => {
    const interval = setInterval(() => {
      fetchData(true);
    }, REFRESH_INTERVAL);

    return () => clearInterval(interval);
  }, [fetchData]);

  const handleAcknowledge = async (alertId) => {
    try {
      await acknowledgeAlert(alertId);
      showToast('Alert acknowledged', 'success');
      fetchData(true);
    } catch (err) {
      showToast('Failed to acknowledge alert', 'error');
    }
  };

  const handleResolve = async (alertId) => {
    try {
      await resolveAlert(alertId);
      showToast('Alert resolved', 'success');
      fetchData(true);
    } catch (err) {
      showToast('Failed to resolve alert', 'error');
    }
  };

  const handleRefresh = () => {
    fetchData(true);
  };

  // Get trend for a specific metric
  const getTrendForMetric = (metricName) => {
    return trends.find((t) => t.metric_name === metricName);
  };

  // Get comparison for a specific metric
  const getComparisonForMetric = (metricName) => {
    return comparisons.find((c) => c.metric_name === metricName);
  };

  // Filter active alerts
  const activeAlerts = alerts.filter((a) => a.status === AlertStatus.ACTIVE);
  const criticalAlerts = activeAlerts.filter((a) => a.severity === AlertSeverity.CRITICAL);

  if (loading) {
    return <PageSkeleton />;
  }

  if (error && !health) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] text-center">
        <ExclamationTriangleIcon className="w-12 h-12 text-critical-500 mb-4" />
        <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
          Failed to load alignment data
        </h2>
        <p className="mt-2 text-surface-500 dark:text-surface-400">{error}</p>
        <button
          onClick={handleRefresh}
          className="mt-4 px-4 py-2 rounded-lg bg-brand-500 text-white hover:bg-brand-600 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
            AI Alignment Dashboard
          </h1>
          <p className="mt-1 text-sm text-surface-500 dark:text-surface-400">
            Monitor and manage AI alignment health across all agents
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(Number(e.target.value))}
            className="px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 text-sm focus:ring-2 focus:ring-aura-500 focus:border-transparent"
          >
            {TIME_RANGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="p-2 rounded-lg border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 hover:bg-surface-50 dark:hover:bg-surface-700 transition-colors"
          >
            <ArrowPathIcon className={`w-5 h-5 text-surface-500 dark:text-surface-400 ${refreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Critical Alert Banner */}
      {criticalAlerts.length > 0 && (
        <div className="bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800 rounded-lg p-4">
          <div className="flex items-center gap-3">
            <ExclamationTriangleIcon className="w-6 h-6 text-critical-500" />
            <div>
              <h3 className="font-semibold text-critical-800 dark:text-critical-200">
                {criticalAlerts.length} Critical Alert{criticalAlerts.length > 1 ? 's' : ''}
              </h3>
              <p className="text-sm text-critical-600 dark:text-critical-300">
                Immediate attention required for alignment issues
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Health Score */}
        <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] shadow-card">
          <div className="p-4 border-b border-surface-200 dark:border-surface-700">
            <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
              Overall Alignment Health
            </h2>
          </div>
          <HealthScoreGauge
            score={health?.overall_score || 0}
            status={health?.status || AlignmentStatus.HEALTHY}
            loading={loading}
          />
          <div className="px-4 pb-4 text-center text-sm text-surface-500 dark:text-surface-400">
            {health?.agents_monitored || 0} agents monitored
          </div>
        </div>

        {/* Metric Cards */}
        <div className="lg:col-span-2 grid grid-cols-2 gap-4">
          <MetricCard
            title="Trust Score"
            value={formatScore(health?.trust_score || 0)}
            icon={ShieldCheckIcon}
            iconColor="olive"
            trend={convertTrendDirection(getTrendForMetric('trust_score')?.direction, getTrendForMetric('trust_score')?.change_percent)}
            subtitle="Average trust across agents"
            loading={loading}
          />
          <MetricCard
            title="Sycophancy Health"
            value={formatScore(health?.sycophancy_score || 0)}
            icon={UserGroupIcon}
            iconColor="aura"
            trend={convertTrendDirection(
              getTrendForMetric('disagreement_rate')?.direction === TrendDirection.DEGRADING ? TrendDirection.IMPROVING : getTrendForMetric('disagreement_rate')?.direction,
              getTrendForMetric('disagreement_rate')?.change_percent
            )}
            subtitle="Anti-sycophancy compliance"
            loading={loading}
          />
          <MetricCard
            title="Transparency"
            value={formatScore(health?.transparency_score || 0)}
            icon={EyeIcon}
            iconColor="aura"
            trend={convertTrendDirection(getTrendForMetric('transparency_score')?.direction, getTrendForMetric('transparency_score')?.change_percent)}
            subtitle="Audit trail completeness"
            loading={loading}
          />
          <MetricCard
            title="Reversibility"
            value={formatScore(health?.reversibility_score || 0)}
            icon={ArrowPathIcon}
            iconColor="warning"
            trend={convertTrendDirection(getTrendForMetric('rollback_success_rate')?.direction, getTrendForMetric('rollback_success_rate')?.change_percent)}
            subtitle="Rollback capability coverage"
            loading={loading}
          />
        </div>
      </div>

      {/* Second Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Active Alerts */}
        <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] shadow-card">
          <div className="p-4 border-b border-surface-200 dark:border-surface-700 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
              Active Alerts
            </h2>
            <span className="px-2 py-1 rounded-full text-xs font-medium bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-300">
              {activeAlerts.length}
            </span>
          </div>
          <div className="p-4 space-y-3 max-h-96 overflow-y-auto">
            {activeAlerts.length === 0 ? (
              <div className="text-center py-8 text-surface-500 dark:text-surface-400">
                <CheckCircleIcon className="w-8 h-8 mx-auto mb-2 text-olive-500" />
                <p>No active alerts</p>
              </div>
            ) : (
              activeAlerts.map((alert) => (
                <AlertCard
                  key={alert.alert_id}
                  alert={alert}
                  onAcknowledge={handleAcknowledge}
                  onResolve={handleResolve}
                />
              ))
            )}
          </div>
        </div>

        {/* Agent Rankings */}
        <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] shadow-card">
          <div className="p-4 border-b border-surface-200 dark:border-surface-700">
            <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
              Agent Trust Rankings
            </h2>
          </div>
          <div className="p-4">
            <AgentRanking
              comparison={getComparisonForMetric('trust_score')}
              loading={loading}
            />
          </div>
        </div>
      </div>

      {/* Last Updated */}
      <div className="text-center text-xs text-surface-400 dark:text-surface-500">
        Last updated: {health?.last_updated ? new Date(health.last_updated).toLocaleString() : 'N/A'}
        {' '}| Auto-refresh every 30 seconds
      </div>
    </div>
  );
}
