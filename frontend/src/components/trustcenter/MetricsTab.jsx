/**
 * Metrics Tab Component
 *
 * Displays Constitutional AI safety metrics with:
 * - Key metric cards with gauges
 * - Time series charts
 * - Issues by severity breakdown
 */

import { memo } from 'react';
import {
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  MinusIcon,
} from '@heroicons/react/24/outline';
import { LineChart, DonutChart, ProgressChart } from '../ui/Charts';

/**
 * Metric Gauge Card Component
 */
const MetricGaugeCard = memo(function MetricGaugeCard({ metric, title, targetLabel, isLowerBetter = false }) {
  if (!metric) return null;

  const value = metric.current_value || 0;
  const target = metric.target_value || 100;
  const trend = metric.trend || 'stable';

  // Calculate status based on value vs target (not relying on mock data)
  // Thresholds: Healthy ≥90% of target, Warning 70-89%, Critical <70%
  // For latency: lower is better, so thresholds are inverted
  const getCalculatedStatus = () => {
    if (isLowerBetter) {
      // For latency metrics: lower is better
      // Healthy: at or below target, Warning: up to 30% over, Critical: >30% over
      const percentage = (value / target) * 100;
      if (percentage <= 100) return 'healthy';
      if (percentage <= 130) return 'warning'; // Up to 30% over target
      return 'critical';
    } else {
      // For percentage metrics: higher is better
      const percentage = (value / target) * 100;
      if (percentage >= 90) return 'healthy';  // ≥90% of target
      if (percentage >= 60) return 'warning';  // 60-89% of target
      return 'critical';                        // <60% of target
    }
  };

  const calculatedStatus = getCalculatedStatus();

  const statusColors = {
    healthy: 'olive',
    warning: 'warning',
    critical: 'critical',
    neutral: 'surface',
  };

  const trendIcons = {
    improving: <ArrowTrendingUpIcon className="w-4 h-4 text-olive-500" />,
    degrading: <ArrowTrendingDownIcon className="w-4 h-4 text-critical-500" />,
    stable: <MinusIcon className="w-4 h-4 text-surface-400" />,
  };

  return (
    <div className="glass-card p-4 flex flex-col items-center">
      <h4 className="text-sm font-bold text-surface-900 dark:text-white mb-3">
        {title}
      </h4>

      <ProgressChart
        value={value}
        max={isLowerBetter ? Math.max(value, target) * 1.2 : (target <= 100 ? 100 : target)}
        color={statusColors[calculatedStatus]}
        size={100}
        strokeWidth={10}
        displayValue={isLowerBetter ? `${Math.round(value)}ms` : null}
      />

      <div className="mt-3 flex items-center gap-2">
        {trendIcons[trend]}
        <span className="text-xs text-surface-500 dark:text-surface-400">
          {trend === 'improving' ? 'Improving' : trend === 'degrading' ? 'Degrading' : 'Stable'}
        </span>
      </div>

      <p className="text-xs text-surface-400 dark:text-surface-500 mt-1">
        {targetLabel}
      </p>
    </div>
  );
});

/**
 * Metric Time Series Card Component
 */
const MetricTimeSeriesCard = memo(function MetricTimeSeriesCard({ metric, title, chartData }) {
  if (!metric || !chartData) return null;

  const statusColors = {
    healthy: 'olive',
    warning: 'warning',
    critical: 'critical',
    neutral: 'aura',
  };

  return (
    <LineChart
      data={chartData.data}
      labels={chartData.labels}
      title={title}
      subtitle={`Current: ${metric.current_value?.toFixed(1)}${metric.unit === 'percent' ? '%' : metric.unit === 'ms' ? 'ms' : ''} | Target: ${metric.target_value}${metric.unit === 'percent' ? '%' : metric.unit === 'ms' ? 'ms' : ''}`}
      color={statusColors[metric.status] || 'aura'}
      height={200}
    />
  );
});

/**
 * Issues By Severity Component
 */
const IssuesBySeverity = memo(function IssuesBySeverity({ issues }) {
  if (!issues) return null;

  const data = [
    issues.critical || 0,
    issues.high || 0,
    issues.medium || 0,
    issues.low || 0,
  ];

  const total = data.reduce((sum, val) => sum + val, 0);

  return (
    <DonutChart
      data={data}
      labels={['Critical', 'High', 'Medium', 'Low']}
      colors={['critical', 'warning', 'aura', 'surface']}
      title="Issues by Severity"
      centerValue={total}
      centerLabel="Total Issues"
      size={180}
      strokeWidth={32}
    />
  );
});

/**
 * Evaluation Summary Component
 */
const EvaluationSummary = memo(function EvaluationSummary({ metrics }) {
  if (!metrics) return null;

  return (
    <div className="glass-card p-6">
      <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4">
        Evaluation Summary
      </h3>

      <div className="grid grid-cols-2 gap-6">
        <div className="text-center p-4 rounded-xl bg-surface-50 dark:bg-surface-800">
          <div className="text-3xl font-bold text-aura-600 dark:text-aura-400">
            {metrics.total_evaluations || 0}
          </div>
          <div className="text-sm text-surface-500 dark:text-surface-400 mt-1">
            Total Evaluations
          </div>
        </div>

        <div className="text-center p-4 rounded-xl bg-surface-50 dark:bg-surface-800">
          <div className="text-3xl font-bold text-olive-600 dark:text-olive-400">
            {metrics.total_critiques || 0}
          </div>
          <div className="text-sm text-surface-500 dark:text-surface-400 mt-1">
            Total Critiques
          </div>
        </div>
      </div>

      <div className="mt-4 text-xs text-surface-400 dark:text-surface-500 text-center">
        Generated: {metrics.generated_at ? new Date(metrics.generated_at).toLocaleString() : 'N/A'}
      </div>
    </div>
  );
});

/**
 * Main Metrics Tab Component
 */
export default function MetricsTab({ metrics, metricsSummary, chartData, period: _period, loading }) {
  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-6 gap-4">
          {[1, 2, 3, 4, 5, 6].map(i => (
            <div key={i} className="skeleton h-40 rounded-xl" />
          ))}
        </div>
        <div className="grid grid-cols-2 gap-6">
          <div className="skeleton h-64 rounded-xl" />
          <div className="skeleton h-64 rounded-xl" />
        </div>
      </div>
    );
  }

  if (!metrics || !metricsSummary) {
    return (
      <div className="text-center py-12 text-surface-500 dark:text-surface-400">
        No metrics data available.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Metric Gauges */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
        <MetricGaugeCard
          metric={metricsSummary.critiqueAccuracy}
          title="Critique Accuracy"
          targetLabel="Target: 90%"
        />
        <MetricGaugeCard
          metric={metricsSummary.revisionConvergence}
          title="Revision Convergence"
          targetLabel="Target: 95%"
        />
        <MetricGaugeCard
          metric={metricsSummary.cacheHitRate}
          title="Cache Hit Rate"
          targetLabel="Target: 30%"
        />
        <MetricGaugeCard
          metric={metricsSummary.nonEvasiveRate}
          title="Non-Evasive Rate"
          targetLabel="Target: 70%"
        />
        <MetricGaugeCard
          metric={metricsSummary.latencyP95}
          title="Latency P95"
          targetLabel="Target: <500ms"
          isLowerBetter={true}
        />
        <MetricGaugeCard
          metric={metricsSummary.goldenSetPass}
          title="Golden Set Pass"
          targetLabel="Target: 95%"
        />
      </div>

      {/* Time Series Charts */}
      <div className="grid md:grid-cols-2 gap-6">
        <MetricTimeSeriesCard
          metric={metricsSummary.critiqueAccuracy}
          title="Critique Accuracy Trend"
          chartData={chartData.critiqueAccuracy}
        />
        <MetricTimeSeriesCard
          metric={metricsSummary.revisionConvergence}
          title="Revision Convergence Trend"
          chartData={chartData.revisionConvergence}
        />
      </div>

      {/* Additional Charts */}
      <div className="grid md:grid-cols-2 gap-6">
        <MetricTimeSeriesCard
          metric={metricsSummary.latencyP95}
          title="Latency P95 Trend"
          chartData={chartData.latencyP95}
        />
        <IssuesBySeverity issues={metrics.issues_by_severity} />
      </div>

      {/* Evaluation Summary */}
      <EvaluationSummary metrics={metrics} />
    </div>
  );
}
