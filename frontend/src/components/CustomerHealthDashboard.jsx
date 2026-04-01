import { useState, useCallback } from 'react';
import {
  ServerIcon,
  CpuChipIcon,
  CurrencyDollarIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  ArrowPathIcon,
  CalendarIcon,
  DocumentArrowDownIcon,
  XMarkIcon,
  LightBulbIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline';
import { DonutChart } from './ui/Charts';
import { PageSkeleton, MetricCardSkeleton, ChartSkeleton, Skeleton } from './ui/LoadingSkeleton';
import DashboardGrid from './ui/DashboardGrid';
import { useToast } from './ui/Toast';

// Health-specific components
import { HealthScoreGauge } from './health';
import { HealthTrendChart } from './health';
import { IncidentTimeline, IncidentSummary } from './health';

// Custom hook for health data
import { useCustomerHealth } from '../hooks/useCustomerHealth';

// API utilities
import { TimeRanges, formatNumber, formatCurrency } from '../services/customerHealthApi';

/**
 * Customer Health Dashboard
 *
 * Comprehensive health monitoring dashboard for Project Aura deployments.
 * Features:
 * - Real-time health score with trend visualization
 * - Component-level health breakdown
 * - Incident timeline with filtering and actions
 * - AI-powered recommendations
 * - Report export functionality
 * - Auto-refresh every 60 seconds
 *
 * Used by:
 * - Aenea Labs team to monitor SaaS customers
 * - Self-hosted customers to monitor their own deployment
 */

const TIME_RANGE_OPTIONS = [
  { value: TimeRanges.HOUR, label: 'Last Hour' },
  { value: TimeRanges.DAY, label: 'Last 24 Hours' },
  { value: TimeRanges.WEEK, label: 'Last 7 Days' },
  { value: TimeRanges.MONTH, label: 'Last 30 Days' },
];

const INCIDENT_STATUS_FILTERS = [
  { value: null, label: 'All' },
  { value: 'active', label: 'Active' },
  { value: 'acknowledged', label: 'Acknowledged' },
  { value: 'resolved', label: 'Resolved' },
];

const INCIDENT_SEVERITY_FILTERS = [
  { value: null, label: 'All Severities' },
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
];

function StatCard({ title, value, unit, icon: Icon, trend, trendDirection, loading }) {
  if (loading) {
    return <MetricCardSkeleton />;
  }

  const TrendIcon = trendDirection === 'up' ? ArrowTrendingUpIcon : ArrowTrendingDownIcon;
  const trendPositive = (trendDirection === 'up' && title !== 'Error Rate') ||
                        (trendDirection === 'down' && title === 'Error Rate');
  const trendColor = trendPositive ? 'text-olive-600 dark:text-olive-400' : 'text-critical-600 dark:text-critical-400';

  return (
    <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-5 shadow-card">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-surface-500 dark:text-surface-400">{title}</span>
        <Icon className="w-5 h-5 text-surface-400 dark:text-surface-500" />
      </div>
      <div className="flex items-baseline gap-2 min-w-0">
        <span className={`font-semibold text-surface-900 dark:text-surface-100 truncate ${
          String(value).length > 12 ? 'text-lg' : 'text-2xl'
        }`}>{value}</span>
        {unit && <span className="text-sm text-surface-500 dark:text-surface-400 flex-shrink-0">{unit}</span>}
      </div>
      {trend !== undefined && trend !== null && (
        <div className={`flex items-center gap-1 mt-2 text-sm ${trendColor}`}>
          <TrendIcon className="w-4 h-4" />
          <span>{Math.abs(trend).toFixed(1)}%</span>
          <span className="text-surface-400 dark:text-surface-500 ml-1">vs previous</span>
        </div>
      )}
    </div>
  );
}

function ComponentHealthCard({ component, onClick, loading }) {
  if (loading) {
    return (
      <div className="bg-white dark:bg-surface-800 rounded-lg border border-surface-200 dark:border-surface-700 p-4">
        <div className="flex items-center gap-3">
          <Skeleton className="w-10 h-10 rounded-lg" />
          <div className="flex-1">
            <Skeleton className="w-24 h-4 rounded mb-1" />
            <Skeleton className="w-16 h-3 rounded" />
          </div>
          <Skeleton className="w-12 h-6 rounded" />
        </div>
      </div>
    );
  }

  const statusColors = {
    healthy: 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400',
    degraded: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    unhealthy: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
  };

  const iconColors = {
    healthy: 'bg-olive-100 text-olive-600 dark:bg-olive-900/30 dark:text-olive-400',
    degraded: 'bg-warning-100 text-warning-600 dark:bg-warning-900/30 dark:text-warning-400',
    unhealthy: 'bg-critical-100 text-critical-600 dark:bg-critical-900/30 dark:text-critical-400',
  };

  return (
    <button
      type="button"
      onClick={() => onClick?.(component.id)}
      className="w-full bg-white dark:bg-surface-800 rounded-lg border border-surface-200 dark:border-surface-700 p-4 hover:border-aura-300 dark:hover:border-aura-700 hover:shadow-md transition-all duration-200 text-left group"
    >
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-lg ${iconColors[component.status] || iconColors.healthy}`}>
          <CpuChipIcon className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-medium text-surface-900 dark:text-surface-100 truncate">
            {component.name}
          </h4>
          <p className="text-xs text-surface-500 dark:text-surface-400">
            Score: {component.score}%
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 rounded text-xs font-medium capitalize ${statusColors[component.status] || statusColors.healthy}`}>
            {component.status}
          </span>
          <ChevronRightIcon className="w-4 h-4 text-surface-400 opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      </div>
    </button>
  );
}

function RecommendationCard({ recommendation, onDismiss }) {
  const [dismissing, setDismissing] = useState(false);

  const priorityColors = {
    high: 'border-l-critical-500',
    medium: 'border-l-warning-500',
    low: 'border-l-info-500',
  };

  const categoryIcons = {
    performance: CpuChipIcon,
    cost: CurrencyDollarIcon,
    reliability: ServerIcon,
    security: ExclamationTriangleIcon,
  };

  const CategoryIcon = categoryIcons[recommendation.category] || LightBulbIcon;

  const handleDismiss = async () => {
    setDismissing(true);
    try {
      await onDismiss?.(recommendation.id);
    } finally {
      setDismissing(false);
    }
  };

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-lg border border-surface-200 dark:border-surface-700
        border-l-4 ${priorityColors[recommendation.priority] || priorityColors.low}
        p-4 hover:shadow-md transition-shadow duration-200
      `}
    >
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-lg bg-surface-100 dark:bg-surface-700">
          <CategoryIcon className="w-5 h-5 text-surface-600 dark:text-surface-400" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <h4 className="text-sm font-medium text-surface-900 dark:text-surface-100">
              {recommendation.title}
            </h4>
            <button
              type="button"
              onClick={handleDismiss}
              disabled={dismissing}
              className="p-1 rounded hover:bg-surface-100 dark:hover:bg-surface-700 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 transition-colors"
              aria-label="Dismiss recommendation"
            >
              <XMarkIcon className="w-4 h-4" />
            </button>
          </div>
          <p className="mt-1 text-xs text-surface-600 dark:text-surface-400 line-clamp-2">
            {recommendation.description}
          </p>
          <div className="mt-2 flex items-center gap-3">
            <span className="text-xs text-surface-500 dark:text-surface-400 capitalize">
              {recommendation.category}
            </span>
            <span className="text-xs text-surface-400">|</span>
            <span className={`text-xs font-medium capitalize ${
              recommendation.priority === 'high' ? 'text-critical-600 dark:text-critical-400' :
              recommendation.priority === 'medium' ? 'text-warning-600 dark:text-warning-400' :
              'text-info-600 dark:text-info-400'
            }`}>
              {recommendation.priority} priority
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function DateRangePicker({ startDate, endDate, onStartChange, onEndChange }) {
  return (
    <div className="flex items-center gap-2">
      <CalendarIcon className="w-5 h-5 text-surface-400" />
      <input
        type="date"
        value={startDate}
        onChange={(e) => onStartChange(e.target.value)}
        className="px-3 py-1.5 text-sm border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
        aria-label="Start date"
      />
      <span className="text-surface-400">to</span>
      <input
        type="date"
        value={endDate}
        onChange={(e) => onEndChange(e.target.value)}
        className="px-3 py-1.5 text-sm border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
        aria-label="End date"
      />
    </div>
  );
}

export default function CustomerHealthDashboard({ _customerId }) {
  // State for date range picker (for export)
  const [exportStartDate, setExportStartDate] = useState('');
  const [exportEndDate, setExportEndDate] = useState('');
  const [showExportOptions, setShowExportOptions] = useState(false);

  // Use the custom hook for all health data
  const {
    // Data
    overview,
    incidents,
    recommendations,
    trendChartData,

    // Computed
    healthScore,
    healthStatus,
    activeIncidentsCount: _activeIncidentsCount,

    // Loading states
    isLoading,
    loadingOverview,
    loadingIncidents,
    loadingRecommendations,
    loadingExport,

    // Error
    error,

    // Filters
    timeRange,
    incidentPage,
    incidentFilter,

    // Actions
    setTimeRange,
    setIncidentFilter,
    selectComponent,
    refreshData,
    loadMoreIncidents,
    loadPreviousIncidents,

    // Mutations
    acknowledgeIncident,
    resolveIncident,
    dismissRecommendation,
    exportReport,
  } = useCustomerHealth({
    autoRefresh: true,
    refreshInterval: 60000,
    initialTimeRange: TimeRanges.DAY,
  });

  const { toast } = useToast();

  // Handle export
  const handleExport = useCallback(async (format) => {
    await exportReport(format, exportStartDate || null, exportEndDate || null);
    setShowExportOptions(false);
  }, [exportReport, exportStartDate, exportEndDate]);

  // Handle refresh with toast notification
  const handleRefresh = useCallback(async () => {
    try {
      await refreshData();
      toast.success('Health data refreshed');
    } catch (err) {
      toast.error('Failed to refresh health data');
    }
  }, [refreshData, toast]);

  // Show loading skeleton on initial load
  if (isLoading && !overview) {
    return <PageSkeleton />;
  }

  // Show error state
  if (error && !overview) {
    return (
      <div className="text-center py-12">
        <ExclamationTriangleIcon className="w-12 h-12 text-critical-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-surface-900 dark:text-surface-100">Unable to load health data</h3>
        <p className="text-surface-500 dark:text-surface-400 mt-1">{error}</p>
        <button
          type="button"
          onClick={refreshData}
          className="mt-4 px-4 py-2 bg-aura-600 text-white rounded-lg hover:bg-aura-700 transition-colors"
        >
          Try Again
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-surface-900 dark:text-surface-100">
            System Health
          </h1>
          <p className="text-surface-500 dark:text-surface-400 text-sm mt-1">
            Real-time monitoring and incident management
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Refresh button */}
          <button
            type="button"
            onClick={handleRefresh}
            disabled={loadingOverview}
            className="flex items-center gap-2 px-4 py-2 text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-100 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors disabled:opacity-50"
            aria-label="Refresh data"
          >
            <ArrowPathIcon className={`h-5 w-5 ${loadingOverview ? 'animate-spin' : ''}`} />
            Refresh
          </button>

          {/* Active incidents summary */}
          <IncidentSummary incidents={incidents.incidents || []} />

          {/* Time range selector */}
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            className="px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-sm text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
            aria-label="Select time range"
          >
            {TIME_RANGE_OPTIONS.map((range) => (
              <option key={range.value} value={range.value}>
                {range.label}
              </option>
            ))}
          </select>

          {/* Export button */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setShowExportOptions(!showExportOptions)}
              disabled={loadingExport}
              className="flex items-center gap-2 px-3 py-2 bg-aura-600 text-white rounded-lg hover:bg-aura-700 transition-colors disabled:opacity-50"
            >
              <DocumentArrowDownIcon className="w-5 h-5" />
              <span className="hidden sm:inline">Export</span>
            </button>

            {showExportOptions && (
              <div className="absolute right-0 mt-2 w-72 bg-white dark:bg-surface-800 rounded-xl shadow-lg border border-surface-200 dark:border-surface-700 p-4 z-10">
                <h4 className="text-sm font-medium text-surface-900 dark:text-surface-100 mb-3">
                  Export Health Report
                </h4>

                <DateRangePicker
                  startDate={exportStartDate}
                  endDate={exportEndDate}
                  onStartChange={setExportStartDate}
                  onEndChange={setExportEndDate}
                />

                <div className="flex gap-2 mt-4">
                  <button
                    type="button"
                    onClick={() => handleExport('pdf')}
                    disabled={loadingExport}
                    className="flex-1 px-3 py-2 bg-aura-600 text-white text-sm rounded-lg hover:bg-aura-700 disabled:opacity-50"
                  >
                    PDF
                  </button>
                  <button
                    type="button"
                    onClick={() => handleExport('csv')}
                    disabled={loadingExport}
                    className="flex-1 px-3 py-2 bg-surface-100 dark:bg-surface-700 text-surface-700 dark:text-surface-300 text-sm rounded-lg hover:bg-surface-200 dark:hover:bg-surface-600 disabled:opacity-50"
                  >
                    CSV
                  </button>
                  <button
                    type="button"
                    onClick={() => handleExport('json')}
                    disabled={loadingExport}
                    className="flex-1 px-3 py-2 bg-surface-100 dark:bg-surface-700 text-surface-700 dark:text-surface-300 text-sm rounded-lg hover:bg-surface-200 dark:hover:bg-surface-600 disabled:opacity-50"
                  >
                    JSON
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Health Score and Trend Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Health Score Gauge */}
        <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-6 shadow-card flex flex-col items-center justify-center">
          <HealthScoreGauge
            score={healthScore}
            status={healthStatus}
            size={180}
            showTrend={true}
            trend={overview?.trend ? {
              direction: overview.trend.direction,
              change: overview.trend.change,
            } : null}
            loading={loadingOverview}
          />
        </div>

        {/* Health Trend Chart */}
        <div className="lg:col-span-2">
          <HealthTrendChart
            data={trendChartData.data}
            labels={trendChartData.labels}
            title="Health Score Trend"
            subtitle={`${TIME_RANGE_OPTIONS.find(r => r.value === timeRange)?.label || 'Last 24 Hours'}`}
            height={220}
            loading={loadingOverview}
          />
        </div>
      </div>

      {/* Key Metrics */}
      <DashboardGrid columns={4}>
        <StatCard
          title="API Requests"
          value={formatNumber(overview?.components?.find(c => c.id === 'api')?.latency_ms ? 15234 : 0)}
          icon={ServerIcon}
          trend={8}
          trendDirection="up"
          loading={loadingOverview}
        />
        <StatCard
          title="Error Rate"
          value="0.28"
          unit="%"
          icon={ExclamationTriangleIcon}
          trend={-12}
          trendDirection="down"
          loading={loadingOverview}
        />
        <StatCard
          title="Avg Latency"
          value={overview?.components?.find(c => c.id === 'api')?.latency_ms || 127}
          unit="ms"
          icon={ClockIcon}
          loading={loadingOverview}
        />
        <StatCard
          title="LLM Cost"
          value={formatCurrency(20.78)}
          icon={CurrencyDollarIcon}
          trend={5}
          trendDirection="up"
          loading={loadingOverview}
        />
      </DashboardGrid>

      {/* Components Grid */}
      <div>
        <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4">
          Component Health
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {loadingOverview ? (
            Array.from({ length: 6 }).map((_, i) => (
              <ComponentHealthCard key={i} loading />
            ))
          ) : (
            overview?.components?.map((component) => (
              <ComponentHealthCard
                key={component.id}
                component={component}
                onClick={selectComponent}
              />
            ))
          )}
        </div>
      </div>

      {/* Incidents and Recommendations Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Incidents Section */}
        <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-6 shadow-card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
              Incidents
            </h2>

            {/* Incident filters */}
            <div className="flex items-center gap-2">
              <select
                value={incidentFilter.status || ''}
                onChange={(e) => setIncidentFilter({ status: e.target.value || null })}
                className="px-2 py-1 text-sm border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-700 dark:text-surface-300 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
                aria-label="Filter by status"
              >
                {INCIDENT_STATUS_FILTERS.map((filter) => (
                  <option key={filter.value || 'all'} value={filter.value || ''}>
                    {filter.label}
                  </option>
                ))}
              </select>

              <select
                value={incidentFilter.severity || ''}
                onChange={(e) => setIncidentFilter({ severity: e.target.value || null })}
                className="px-2 py-1 text-sm border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-700 dark:text-surface-300 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
                aria-label="Filter by severity"
              >
                {INCIDENT_SEVERITY_FILTERS.map((filter) => (
                  <option key={filter.value || 'all'} value={filter.value || ''}>
                    {filter.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <IncidentTimeline
            incidents={incidents.incidents || []}
            total={incidents.total || 0}
            page={incidentPage}
            hasMore={incidents.has_more}
            loading={loadingIncidents}
            onAcknowledge={acknowledgeIncident}
            onResolve={resolveIncident}
            onNextPage={loadMoreIncidents}
            onPrevPage={loadPreviousIncidents}
            emptyMessage="No incidents match your filters"
          />
        </div>

        {/* Recommendations Section */}
        <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-6 shadow-card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
              AI Recommendations
            </h2>
            <LightBulbIcon className="w-5 h-5 text-warning-500" />
          </div>

          {loadingRecommendations ? (
            <div className="space-y-4">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="bg-surface-50 dark:bg-surface-700 rounded-lg p-4">
                  <Skeleton className="w-3/4 h-4 rounded mb-2" />
                  <Skeleton className="w-full h-3 rounded" />
                  <Skeleton className="w-2/3 h-3 rounded mt-1" />
                </div>
              ))}
            </div>
          ) : recommendations.length === 0 ? (
            <div className="text-center py-8">
              <CheckCircleIcon className="w-10 h-10 text-olive-500 mx-auto mb-3" />
              <p className="text-surface-600 dark:text-surface-400">
                No recommendations at this time
              </p>
              <p className="text-sm text-surface-500 dark:text-surface-500 mt-1">
                Your system is well optimized
              </p>
            </div>
          ) : (
            <div className="space-y-4 max-h-96 overflow-y-auto pr-2">
              {recommendations.map((rec) => (
                <RecommendationCard
                  key={rec.id}
                  recommendation={rec}
                  onDismiss={dismissRecommendation}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Agent Performance Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Agent Distribution */}
        <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-6 shadow-card">
          <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4">
            Agent Executions by Type
          </h3>
          {loadingOverview ? (
            <ChartSkeleton />
          ) : (
            <DonutChart
              data={[523, 412, 189, 123]}
              labels={['Scanner', 'Coder', 'Reviewer', 'Validator']}
              colors={['aura', 'olive', 'warning', 'surface']}
              centerValue="1,247"
              centerLabel="Total"
            />
          )}
        </div>

        {/* Agent Performance Stats */}
        <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-6 shadow-card">
          <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4">
            Agent Performance
          </h3>
          {loadingOverview ? (
            <div className="grid grid-cols-2 gap-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i}>
                  <Skeleton className="w-24 h-4 rounded mb-2" />
                  <Skeleton className="w-16 h-8 rounded" />
                </div>
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-6">
              <div>
                <p className="text-sm text-surface-500 dark:text-surface-400">Total Executions</p>
                <p className="text-2xl font-semibold text-surface-900 dark:text-surface-100 mt-1">1,247</p>
              </div>
              <div>
                <p className="text-sm text-surface-500 dark:text-surface-400">Success Rate</p>
                <p className="text-2xl font-semibold text-olive-600 dark:text-olive-400 mt-1">96.1%</p>
              </div>
              <div>
                <p className="text-sm text-surface-500 dark:text-surface-400">Failed Executions</p>
                <p className="text-2xl font-semibold text-critical-600 dark:text-critical-400 mt-1">49</p>
              </div>
              <div>
                <p className="text-sm text-surface-500 dark:text-surface-400">Avg Execution Time</p>
                <p className="text-2xl font-semibold text-surface-900 dark:text-surface-100 mt-1">45.3s</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Footer with last update time */}
      <div className="text-center text-sm text-surface-500 dark:text-surface-400 py-4">
        Last updated: {overview?.last_updated ? new Date(overview.last_updated).toLocaleString() : 'Never'}
        <span className="mx-2">|</span>
        Auto-refresh: every 60 seconds
      </div>
    </div>
  );
}
