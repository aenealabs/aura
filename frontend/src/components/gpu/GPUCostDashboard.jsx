/**
 * Project Aura - GPU Cost Dashboard Component
 *
 * Displays GPU usage costs, budget status, and forecasts.
 * ADR-061: GPU Workload Scheduler - Phase 4 Observability & Cost
 */

import { useState, useEffect, useCallback, memo } from 'react';
import {
  CurrencyDollarIcon,
  ClockIcon,
  ChartBarIcon,
  ExclamationTriangleIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  CalendarDaysIcon,
  CogIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';
import {
  getGPUCosts,
  getBudgetStatus,
  getCostForecast,
  formatCost,
} from '../../services/gpuSchedulerApi';

/**
 * Metric card component
 */
const MetricCard = memo(function MetricCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  trendValue,
  className = '',
}) {
  return (
    <div className={`bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 ${className}`}>
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          {Icon && (
            <div className="p-2 bg-aura-50 dark:bg-aura-900/20 rounded-lg">
              <Icon className="w-5 h-5 text-aura-600 dark:text-aura-400" />
            </div>
          )}
          <div>
            <p className="text-sm text-surface-500 dark:text-surface-400">{title}</p>
            <p className="text-2xl font-semibold text-surface-900 dark:text-surface-100 mt-0.5">
              {value}
            </p>
            {subtitle && (
              <p className="text-xs text-surface-400 dark:text-surface-500 mt-0.5">{subtitle}</p>
            )}
          </div>
        </div>
        {trend && (
          <div className={`flex items-center gap-1 text-sm ${
            trend === 'up' ? 'text-critical-600 dark:text-critical-400' :
            trend === 'down' ? 'text-success-600 dark:text-success-400' :
            'text-surface-500'
          }`}>
            {trend === 'up' && <ArrowTrendingUpIcon className="w-4 h-4" />}
            {trend === 'down' && <ArrowTrendingDownIcon className="w-4 h-4" />}
            <span>{trendValue}</span>
          </div>
        )}
      </div>
    </div>
  );
});

/**
 * Budget progress bar
 */
const BudgetProgress = memo(function BudgetProgress({
  used,
  total,
  alertThreshold = 80,
}) {
  const percent = (used / total) * 100;
  const isWarning = percent >= alertThreshold;
  const isOver = percent >= 100;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="text-surface-600 dark:text-surface-400">Budget Usage</span>
        <span className={`font-medium ${
          isOver ? 'text-critical-600 dark:text-critical-400' :
          isWarning ? 'text-warning-600 dark:text-warning-400' :
          'text-surface-700 dark:text-surface-300'
        }`}>
          {formatCost(used)} / {formatCost(total)} ({percent.toFixed(0)}%)
        </span>
      </div>
      <div className="h-3 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden relative">
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            isOver ? 'bg-critical-500' :
            isWarning ? 'bg-warning-500' :
            'bg-aura-500'
          }`}
          style={{ width: `${Math.min(100, percent)}%` }}
        />
        {/* Alert threshold marker */}
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-surface-400 dark:bg-surface-500"
          style={{ left: `${alertThreshold}%` }}
        />
      </div>
      <div className="flex items-center justify-between text-xs text-surface-500 dark:text-surface-400">
        <span>{formatCost(0)}</span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 bg-surface-400 dark:bg-surface-500 rounded-full" />
          Alert at {alertThreshold}%
        </span>
        <span>{formatCost(total)}</span>
      </div>
    </div>
  );
});

/**
 * Cost by job type chart (simple bar chart)
 */
const CostByJobTypeChart = memo(function CostByJobTypeChart({ data }) {
  if (!data || Object.keys(data).length === 0) {
    return (
      <div className="text-center py-8 text-surface-500 dark:text-surface-400">
        No cost data available
      </div>
    );
  }

  const maxValue = Math.max(...Object.values(data));
  const jobTypeLabels = {
    embedding_generation: 'Embedding Gen',
    vulnerability_training: 'Vuln Training',
    swe_rl_training: 'SWE-RL Training',
    memory_consolidation: 'Memory Consol.',
    local_inference: 'Local Inference',
  };

  const colors = [
    'bg-aura-500',
    'bg-info-500',
    'bg-success-500',
    'bg-warning-500',
    'bg-critical-500',
  ];

  return (
    <div className="space-y-3">
      {Object.entries(data).map(([jobType, cost], index) => (
        <div key={jobType} className="space-y-1">
          <div className="flex items-center justify-between text-sm">
            <span className="text-surface-700 dark:text-surface-300">
              {jobTypeLabels[jobType] || jobType}
            </span>
            <span className="text-surface-600 dark:text-surface-400 font-medium">
              {formatCost(cost)}
            </span>
          </div>
          <div className="h-2 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full ${colors[index % colors.length]}`}
              style={{ width: `${(cost / maxValue) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
});

/**
 * Daily cost trend chart (sparkline style)
 */
const DailyCostTrend = memo(function DailyCostTrend({ data }) {
  if (!data || data.length === 0) {
    return (
      <div className="text-center py-8 text-surface-500 dark:text-surface-400">
        No trend data available
      </div>
    );
  }

  const maxCost = Math.max(...data.map((d) => d.cost_usd));
  const chartHeight = 100;

  return (
    <div className="relative h-32">
      {/* Y-axis labels */}
      <div className="absolute left-0 top-0 bottom-6 w-12 flex flex-col justify-between text-xs text-surface-500 dark:text-surface-400">
        <span>{formatCost(maxCost)}</span>
        <span>{formatCost(maxCost / 2)}</span>
        <span>{formatCost(0)}</span>
      </div>

      {/* Chart area */}
      <div className="ml-14 h-full pb-6 flex items-end gap-1">
        {data.map((day, index) => {
          const height = (day.cost_usd / maxCost) * chartHeight;
          const isToday = index === data.length - 1;

          return (
            <div
              key={day.date}
              className="flex-1 flex flex-col items-center gap-1"
              title={`${day.date}: ${formatCost(day.cost_usd)}`}
            >
              <div
                className={`w-full rounded-t transition-all hover:opacity-80 ${
                  isToday ? 'bg-aura-500' : 'bg-aura-300 dark:bg-aura-700'
                }`}
                style={{ height: `${Math.max(4, height)}%` }}
              />
              <span className="text-xs text-surface-500 dark:text-surface-400 truncate w-full text-center">
                {new Date(day.date).toLocaleDateString('en-US', { weekday: 'short' })}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
});

/**
 * Forecast card
 */
const ForecastCard = memo(function ForecastCard({ forecast, budget }) {
  if (!forecast) return null;

  const trend = forecast.trend;
  const trendConfig = {
    over_budget: {
      color: 'text-critical-600 dark:text-critical-400',
      bgColor: 'bg-critical-50 dark:bg-critical-900/20',
      icon: ExclamationTriangleIcon,
      label: 'Over Budget',
    },
    approaching: {
      color: 'text-warning-600 dark:text-warning-400',
      bgColor: 'bg-warning-50 dark:bg-warning-900/20',
      icon: ArrowTrendingUpIcon,
      label: 'Approaching Limit',
    },
    on_track: {
      color: 'text-success-600 dark:text-success-400',
      bgColor: 'bg-success-50 dark:bg-success-900/20',
      icon: ChartBarIcon,
      label: 'On Track',
    },
  };

  const config = trendConfig[trend] || trendConfig.on_track;
  const TrendIcon = config.icon;

  return (
    <div className={`rounded-xl border border-surface-200 dark:border-surface-700 p-4 ${config.bgColor}`}>
      <div className="flex items-start gap-3">
        <div className={`p-2 rounded-lg ${config.bgColor}`}>
          <TrendIcon className={`w-5 h-5 ${config.color}`} />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <h4 className={`font-medium ${config.color}`}>
              End-of-Month Forecast: {config.label}
            </h4>
          </div>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-surface-500 dark:text-surface-400">Forecast</span>
              <p className="font-semibold text-surface-900 dark:text-surface-100">
                {formatCost(forecast.forecast_usd)}
              </p>
            </div>
            <div>
              <span className="text-surface-500 dark:text-surface-400">Daily Avg</span>
              <p className="font-semibold text-surface-900 dark:text-surface-100">
                {formatCost(forecast.daily_average_usd)}
              </p>
            </div>
            <div>
              <span className="text-surface-500 dark:text-surface-400">Confidence Range</span>
              <p className="font-medium text-surface-700 dark:text-surface-300">
                {formatCost(forecast.confidence_low_usd)} - {formatCost(forecast.confidence_high_usd)}
              </p>
            </div>
            <div>
              <span className="text-surface-500 dark:text-surface-400">Days Remaining</span>
              <p className="font-semibold text-surface-900 dark:text-surface-100">
                {forecast.days_remaining} days
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
});

/**
 * Budget alert banner
 */
const BudgetAlertBanner = memo(function BudgetAlertBanner({ status, onDismiss }) {
  if (!status?.alert_triggered) return null;

  const isOver = status.usage_percent >= 100;

  return (
    <div
      className={`flex items-start gap-3 p-4 rounded-lg mb-6 ${
        isOver
          ? 'bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800'
          : 'bg-warning-50 dark:bg-warning-900/20 border border-warning-200 dark:border-warning-800'
      }`}
      role="alert"
    >
      <ExclamationTriangleIcon
        className={`w-5 h-5 flex-shrink-0 mt-0.5 ${
          isOver ? 'text-critical-600 dark:text-critical-400' : 'text-warning-600 dark:text-warning-400'
        }`}
      />
      <div className="flex-1">
        <h4 className={`font-medium ${
          isOver ? 'text-critical-700 dark:text-critical-300' : 'text-warning-700 dark:text-warning-300'
        }`}>
          {isOver ? 'GPU Budget Exceeded' : 'GPU Budget Warning'}
        </h4>
        <p className={`text-sm mt-1 ${
          isOver ? 'text-critical-600 dark:text-critical-400' : 'text-warning-600 dark:text-warning-400'
        }`}>
          {isOver
            ? `You have exceeded your monthly GPU budget of ${formatCost(status.budget_limit_usd)}. New jobs may be blocked.`
            : `You have used ${status.usage_percent.toFixed(0)}% of your monthly GPU budget (${formatCost(status.budget_used_usd)} of ${formatCost(status.budget_limit_usd)}).`}
        </p>
      </div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className={`${
            isOver ? 'text-critical-400 hover:text-critical-600' : 'text-warning-400 hover:text-warning-600'
          } dark:hover:text-warning-300`}
          aria-label="Dismiss"
        >
          ×
        </button>
      )}
    </div>
  );
});

/**
 * Main GPU Cost Dashboard Component
 */
export default function GPUCostDashboard({ className = '' }) {
  const [costs, setCosts] = useState(null);
  const [budgetStatus, setBudgetStatus] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [alertDismissed, setAlertDismissed] = useState(false);

  // Get current month name
  const currentMonth = new Date().toLocaleDateString('en-US', {
    month: 'long',
    year: 'numeric',
  });

  /**
   * Fetch all cost data
   */
  const fetchCostData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [costsData, budgetData, forecastData] = await Promise.all([
        getGPUCosts(),
        getBudgetStatus(),
        getCostForecast(),
      ]);

      setCosts(costsData);
      setBudgetStatus(budgetData);
      setForecast(forecastData);
    } catch (err) {
      console.error('Failed to fetch cost data:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch on mount
  useEffect(() => {
    fetchCostData();
  }, [fetchCostData]);

  // Loading state
  if (loading) {
    return (
      <div className={`animate-pulse space-y-6 ${className}`}>
        <div className="h-8 bg-surface-200 dark:bg-surface-700 rounded w-48" />
        <div className="grid grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-28 bg-surface-200 dark:bg-surface-700 rounded-xl" />
          ))}
        </div>
        <div className="grid grid-cols-2 gap-6">
          <div className="h-64 bg-surface-200 dark:bg-surface-700 rounded-xl" />
          <div className="h-64 bg-surface-200 dark:bg-surface-700 rounded-xl" />
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className={`bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800 rounded-xl p-6 ${className}`}>
        <div className="flex items-center gap-3">
          <ExclamationTriangleIcon className="w-6 h-6 text-critical-600 dark:text-critical-400" />
          <div>
            <h3 className="font-medium text-critical-700 dark:text-critical-300">
              Failed to load cost data
            </h3>
            <p className="text-sm text-critical-600 dark:text-critical-400 mt-1">{error}</p>
          </div>
        </div>
        <button
          onClick={fetchCostData}
          className="mt-4 px-4 py-2 bg-critical-600 hover:bg-critical-700 text-white rounded-lg text-sm font-medium"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-surface-900 dark:text-surface-100">
            GPU Usage & Costs
          </h2>
          <p className="text-sm text-surface-500 dark:text-surface-400 mt-0.5">
            {currentMonth}
          </p>
        </div>
        <button
          onClick={fetchCostData}
          className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
        >
          <CogIcon className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Budget Alert Banner */}
      {!alertDismissed && (
        <BudgetAlertBanner
          status={budgetStatus}
          onDismiss={() => setAlertDismissed(true)}
        />
      )}

      {/* Summary Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Cost"
          value={formatCost(costs?.total_cost_usd)}
          subtitle={`${costs?.jobs_count || 0} jobs`}
          icon={CurrencyDollarIcon}
        />
        <MetricCard
          title="GPU Hours"
          value={`${costs?.gpu_hours?.toFixed(1) || 0} hrs`}
          subtitle="This month"
          icon={ClockIcon}
        />
        <MetricCard
          title="Avg Job Cost"
          value={formatCost(costs?.avg_job_cost_usd)}
          subtitle="Per job"
          icon={ChartBarIcon}
        />
        <MetricCard
          title="Days Remaining"
          value={forecast?.days_remaining || 0}
          subtitle={`${formatCost(budgetStatus?.budget_remaining_usd)} left`}
          icon={CalendarDaysIcon}
        />
      </div>

      {/* Budget Progress */}
      {budgetStatus && (
        <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-5">
          <h3 className="font-medium text-surface-900 dark:text-surface-100 mb-4">
            Monthly Budget
          </h3>
          <BudgetProgress
            used={budgetStatus.budget_used_usd}
            total={budgetStatus.budget_limit_usd}
            alertThreshold={budgetStatus.alert_threshold_percent}
          />
        </div>
      )}

      {/* Forecast Card */}
      {forecast && (
        <ForecastCard forecast={forecast} budget={budgetStatus?.budget_limit_usd} />
      )}

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Cost by Job Type */}
        <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-medium text-surface-900 dark:text-surface-100">
              Cost by Job Type
            </h3>
            <InformationCircleIcon
              className="w-4 h-4 text-surface-400"
              title="Cost breakdown by GPU workload type"
            />
          </div>
          <CostByJobTypeChart data={costs?.by_job_type} />
        </div>

        {/* Daily Trend */}
        <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-medium text-surface-900 dark:text-surface-100">
              Daily Cost Trend
            </h3>
            <span className="text-xs text-surface-500 dark:text-surface-400">
              Last 7 days
            </span>
          </div>
          <DailyCostTrend data={costs?.daily_costs} />
        </div>
      </div>

      {/* Footer info */}
      <div className="flex items-center gap-2 text-xs text-surface-500 dark:text-surface-400">
        <InformationCircleIcon className="w-4 h-4" />
        <span>
          Costs are based on Spot instance pricing. Actual costs may vary based on Spot market conditions.
        </span>
      </div>
    </div>
  );
}
