/**
 * UsageAnalyticsDashboard Component
 *
 * Displays usage analytics for beta customers including:
 * - API usage metrics and trends
 * - Feature adoption rates
 * - User engagement scores
 * - Export capabilities for reporting
 */

import { useState, useEffect, useCallback } from 'react';
import {
  ArrowPathIcon,
  ChartBarIcon,
  UserGroupIcon,
  LinkIcon,
  CpuChipIcon,
  SignalIcon,
  CheckCircleIcon,
  BoltIcon,
  XCircleIcon,
} from '@heroicons/react/24/outline';
import { useAuth } from '../context/AuthContext';
import { useToast } from './ui/Toast';
import MetricCard from './ui/MetricCard';

// Time period options
const TIME_PERIODS = [
  { value: 7, label: 'Last 7 days' },
  { value: 14, label: 'Last 14 days' },
  { value: 30, label: 'Last 30 days' },
  { value: 90, label: 'Last 90 days' },
];

// Progress bar component for feature adoption
const AdoptionBar = ({ feature, adoption, uses, users }) => (
  <div className="py-3 border-b border-surface-100 dark:border-surface-700 last:border-0">
    <div className="flex items-center justify-between mb-1">
      <span className="text-sm font-medium text-surface-900 dark:text-surface-100">{feature}</span>
      <span className="text-sm text-surface-500 dark:text-surface-400">{adoption}%</span>
    </div>
    <div className="w-full bg-surface-100 dark:bg-surface-700 rounded-full h-2">
      <div
        className="bg-aura-600 h-2 rounded-full transition-all duration-300"
        style={{ width: `${Math.min(adoption, 100)}%` }}
      />
    </div>
    <div className="flex items-center justify-between mt-1 text-xs text-surface-500 dark:text-surface-400">
      <span>{uses.toLocaleString()} uses</span>
      <span>{users.toLocaleString()} users</span>
    </div>
  </div>
);

// User engagement row component
const EngagementRow = ({ user, score, events, lastActive }) => {
  const scoreColor = score >= 80 ? 'text-olive-600 dark:text-olive-400' : score >= 50 ? 'text-warning-600 dark:text-warning-400' : 'text-critical-600 dark:text-critical-400';

  return (
    <tr className="hover:bg-surface-50 dark:hover:bg-surface-700/50">
      <td className="px-4 py-3 text-sm text-surface-900 dark:text-surface-100">{user}</td>
      <td className={`px-4 py-3 text-sm font-medium ${scoreColor}`}>
        {score.toFixed(1)}
      </td>
      <td className="px-4 py-3 text-sm text-surface-500 dark:text-surface-400">{events.toLocaleString()}</td>
      <td className="px-4 py-3 text-sm text-surface-500 dark:text-surface-400">{lastActive}</td>
    </tr>
  );
};

const UsageAnalyticsDashboard = () => {
  const { isAuthenticated } = useAuth();
  const { toast } = useToast();
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [summary, setSummary] = useState(null);
  const [apiUsage, setApiUsage] = useState(null);
  const [features, setFeatures] = useState([]);
  const [engagement, setEngagement] = useState([]);
  const [activeTab, setActiveTab] = useState('overview');

  // Fetch analytics data
  const fetchAnalytics = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [summaryRes, apiRes, featuresRes, engagementRes] = await Promise.all([
        fetch(`/api/v1/analytics/usage?days=${days}`),
        fetch(`/api/v1/analytics/api?days=${days}`),
        fetch(`/api/v1/analytics/features?days=${days}&limit=10`),
        fetch(`/api/v1/analytics/engagement?days=${days}&limit=10`),
      ]);

      if (!summaryRes.ok || !apiRes.ok || !featuresRes.ok || !engagementRes.ok) {
        throw new Error('Failed to fetch analytics data');
      }

      const [summaryData, apiData, featuresData, engagementData] = await Promise.all([
        summaryRes.json(),
        apiRes.json(),
        featuresRes.json(),
        engagementRes.json(),
      ]);

      setSummary(summaryData);
      setApiUsage(apiData);
      setFeatures(featuresData);
      setEngagement(engagementData);
    } catch (err) {
      setError(err.message || 'Failed to load analytics');
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    if (isAuthenticated) {
      fetchAnalytics();
    }
  }, [isAuthenticated, fetchAnalytics]);

  // Export analytics data
  const handleExport = async () => {
    try {
      const response = await fetch(`/api/v1/analytics/export?days=${days}`);
      if (!response.ok) throw new Error('Export failed');

      const data = await response.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `analytics-export-${days}days-${new Date().toISOString().split('T')[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError('Failed to export data');
    }
  };

  // Handle refresh
  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await fetchAnalytics();
      toast.success('Analytics refreshed');
    } catch (err) {
      toast.error('Failed to refresh analytics');
    } finally {
      setIsRefreshing(false);
    }
  };

  // Format relative time
  const formatRelativeTime = (isoString) => {
    const date = new Date(isoString);
    const now = new Date();
    const diffHours = Math.floor((now - date) / (1000 * 60 * 60));

    if (diffHours < 1) return 'Just now';
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  if (!isAuthenticated) {
    return (
      <div className="flex items-center justify-center min-h-96">
        <p className="text-surface-500 dark:text-surface-400">Please log in to view analytics.</p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">Usage Analytics</h1>
          <p className="mt-1 text-sm text-surface-500 dark:text-surface-400">
            Monitor platform usage and user engagement
          </p>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-2 px-4 py-2 text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors disabled:opacity-50"
          >
            <ArrowPathIcon className={`w-5 h-5 ${isRefreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg text-sm bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
          >
            {TIME_PERIODS.map((period) => (
              <option key={period.value} value={period.value}>
                {period.label}
              </option>
            ))}
          </select>
          <button
            onClick={handleExport}
            className="px-4 py-2 bg-surface-100 dark:bg-surface-700 text-surface-700 dark:text-surface-300 rounded-lg hover:bg-surface-200 dark:hover:bg-surface-600 transition-colors text-sm font-medium"
          >
            Export
          </button>
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div className="mb-6 p-4 bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800 rounded-lg text-critical-700 dark:text-critical-300">
          {error}
        </div>
      )}

      {/* Loading state */}
      {loading ? (
        <div className="flex items-center justify-center min-h-96">
          <div className="text-center">
            <svg
              className="animate-spin h-8 w-8 text-aura-600 mx-auto mb-4"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            <p className="text-surface-500 dark:text-surface-400">Loading analytics...</p>
          </div>
        </div>
      ) : (
        <>
          {/* Tabs */}
          <div className="border-b border-surface-200 dark:border-surface-700 mb-6">
            <nav className="flex gap-8">
              {['overview', 'api', 'features', 'users'].map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`py-3 text-sm font-medium border-b-2 transition-colors ${
                    activeTab === tab
                      ? 'border-aura-600 text-aura-600'
                      : 'border-transparent text-surface-500 dark:text-surface-400 hover:text-surface-700 dark:hover:text-surface-300'
                  }`}
                >
                  {tab.charAt(0).toUpperCase() + tab.slice(1)}
                </button>
              ))}
            </nav>
          </div>

          {/* Overview Tab */}
          {activeTab === 'overview' && summary && (
            <div className="space-y-6">
              {/* Summary metrics */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <MetricCard
                  title="Total Events"
                  value={summary.total_events?.toLocaleString() || '0'}
                  subtitle={`${summary.period_days} day period`}
                  icon={ChartBarIcon}
                  iconColor="aura"
                />
                <MetricCard
                  title="Unique Users"
                  value={summary.unique_users?.toLocaleString() || '0'}
                  subtitle="Active users"
                  icon={UserGroupIcon}
                  iconColor="aura"
                />
                <MetricCard
                  title="API Requests"
                  value={summary.api_requests?.toLocaleString() || '0'}
                  subtitle="Total API calls"
                  icon={LinkIcon}
                  iconColor="aura"
                />
                <MetricCard
                  title="Agent Executions"
                  value={summary.agent_executions?.toLocaleString() || '0'}
                  subtitle="AI agent runs"
                  icon={CpuChipIcon}
                  iconColor="aura"
                />
              </div>

              {/* By type breakdown */}
              {summary.by_type && Object.keys(summary.by_type).length > 0 && (
                <div className="bg-white dark:bg-surface-800 rounded-lg border border-surface-200 dark:border-surface-700 p-6">
                  <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4">
                    Events by Type
                  </h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {Object.entries(summary.by_type).map(([type, count]) => (
                      <div key={type} className="text-center p-3 bg-surface-50 dark:bg-surface-700 rounded-lg">
                        <p className="text-2xl font-semibold text-surface-900 dark:text-surface-100">
                          {count.toLocaleString()}
                        </p>
                        <p className="text-sm text-surface-500 dark:text-surface-400 capitalize">
                          {type.replace('_', ' ')}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* API Tab */}
          {activeTab === 'api' && apiUsage && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <MetricCard
                  title="Total Requests"
                  value={apiUsage.total_requests?.toLocaleString() || '0'}
                  icon={SignalIcon}
                  iconColor="aura"
                />
                <MetricCard
                  title="Success Rate"
                  value={`${(apiUsage.success_rate * 100).toFixed(1)}%`}
                  trend={apiUsage.success_rate >= 0.99 ? 5 : apiUsage.success_rate >= 0.95 ? 0 : -5}
                  icon={CheckCircleIcon}
                  iconColor="olive"
                />
                <MetricCard
                  title="Avg Latency"
                  value={`${apiUsage.average_latency_ms?.toFixed(0) || 0} ms`}
                  icon={BoltIcon}
                  iconColor="warning"
                />
                <MetricCard
                  title="Failed Requests"
                  value={apiUsage.failed_requests?.toLocaleString() || '0'}
                  trend={apiUsage.failed_requests === 0 ? 0 : -5}
                  trendInverse={true}
                  icon={XCircleIcon}
                  iconColor="critical"
                />
              </div>

              {/* By endpoint */}
              {apiUsage.by_endpoint && Object.keys(apiUsage.by_endpoint).length > 0 && (
                <div className="bg-white dark:bg-surface-800 rounded-lg border border-surface-200 dark:border-surface-700 p-6">
                  <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4">
                    Requests by Endpoint
                  </h3>
                  <div className="space-y-3">
                    {Object.entries(apiUsage.by_endpoint)
                      .sort((a, b) => b[1] - a[1])
                      .slice(0, 10)
                      .map(([endpoint, count]) => {
                        const total = apiUsage.total_requests || 1;
                        const percentage = (count / total) * 100;
                        return (
                          <div key={endpoint}>
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-sm font-mono text-surface-700 dark:text-surface-300">{endpoint}</span>
                              <span className="text-sm text-surface-500 dark:text-surface-400">{count.toLocaleString()}</span>
                            </div>
                            <div className="w-full bg-surface-100 dark:bg-surface-700 rounded-full h-2">
                              <div
                                className="bg-aura-600 h-2 rounded-full"
                                style={{ width: `${percentage}%` }}
                              />
                            </div>
                          </div>
                        );
                      })}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Features Tab */}
          {activeTab === 'features' && (
            <div className="bg-white dark:bg-surface-800 rounded-lg border border-surface-200 dark:border-surface-700 p-6">
              <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4">
                Feature Adoption
              </h3>
              {features.length > 0 ? (
                <div className="space-y-1">
                  {features.map((feature) => (
                    <AdoptionBar
                      key={feature.feature_name}
                      feature={feature.feature_name}
                      adoption={feature.adoption_rate}
                      uses={feature.total_uses}
                      users={feature.unique_users}
                    />
                  ))}
                </div>
              ) : (
                <p className="text-surface-500 dark:text-surface-400 text-center py-8">
                  No feature usage data available for this period.
                </p>
              )}
            </div>
          )}

          {/* Users Tab */}
          {activeTab === 'users' && (
            <div className="bg-white dark:bg-surface-800 rounded-lg border border-surface-200 dark:border-surface-700 overflow-hidden">
              <div className="px-6 py-4 border-b border-surface-200 dark:border-surface-700">
                <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
                  User Engagement
                </h3>
              </div>
              {engagement.length > 0 ? (
                <table className="w-full">
                  <thead className="bg-surface-50 dark:bg-surface-700">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-surface-500 dark:text-surface-400 uppercase">
                        User
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-surface-500 dark:text-surface-400 uppercase">
                        Score
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-surface-500 dark:text-surface-400 uppercase">
                        Events
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-surface-500 dark:text-surface-400 uppercase">
                        Last Active
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-200 dark:divide-surface-700">
                    {engagement.map((user) => (
                      <EngagementRow
                        key={user.user_id}
                        user={user.user_id}
                        score={user.engagement_score}
                        events={user.total_events}
                        lastActive={formatRelativeTime(user.last_active)}
                      />
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-surface-500 dark:text-surface-400 text-center py-8">
                  No user engagement data available for this period.
                </p>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default UsageAnalyticsDashboard;
