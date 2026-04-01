/**
 * Overview Tab Component
 *
 * Displays the AI Trust Center overview including:
 * - System health status hero
 * - Compliance score gauge
 * - Key metrics summary cards
 * - Quick status indicators
 */

import { memo } from 'react';
import {
  ShieldCheckIcon,
  CheckCircleIcon,
  ClockIcon,
  CpuChipIcon,
  ScaleIcon,
} from '@heroicons/react/24/outline';
import MetricCard, { MetricCardGrid } from '../ui/MetricCard';
import { ProgressChart } from '../ui/Charts';

/**
 * Status Legend Component - Horizontal display of threshold definitions
 *
 * Thresholds for Constitutional AI metrics:
 * - Critique Accuracy: Green ≥90%, Yellow 80-89%, Red <80%
 * - Revision Convergence: Green ≥95%, Yellow 85-94%, Red <85%
 * - Cache Hit Rate: Green ≥30%, Yellow 20-29%, Red <20%
 * - Non-Evasive Rate: Green ≥70%, Yellow 55-69%, Red <55%
 * - Overall Compliance: Green ≥90%, Yellow 70-89%, Red <70%
 */
const StatusLegend = memo(function StatusLegend() {
  return (
    <div className="inline-flex items-center gap-6 glass-card-subtle rounded-xl px-4 py-3 mb-4">
      <span className="text-sm font-medium text-surface-600 dark:text-surface-300">
        Status Legend:
      </span>
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-olive-500" />
          <span className="text-xs text-surface-600 dark:text-surface-400">Healthy ≥ 90%</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-warning-500" />
          <span className="text-xs text-surface-600 dark:text-surface-400">Warning 70–89%</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-critical-500" />
          <span className="text-xs text-surface-600 dark:text-surface-400">Critical &lt; 70%</span>
        </div>
      </div>
    </div>
  );
});

/**
 * Status Hero Component
 */
const StatusHero = memo(function StatusHero({ status, complianceScore }) {
  const statusColors = {
    healthy: 'olive',
    warning: 'warning',
    critical: 'critical',
    unknown: 'surface',
  };

  const statusMessages = {
    healthy: 'All Constitutional AI systems are operating normally.',
    warning: 'Minor issues detected. Review recommended.',
    critical: 'Critical issues require immediate attention.',
    unknown: 'System status is being determined.',
  };

  const overallStatus = status?.overall_status || 'unknown';
  const _color = statusColors[overallStatus] || 'surface';

  // Determine border color based on compliance score and status
  const getBorderColor = () => {
    if (overallStatus === 'critical' || complianceScore < 70) {
      return 'border-critical-500';
    }
    if (overallStatus === 'warning' || complianceScore < 90) {
      return 'border-warning-500';
    }
    if (overallStatus === 'healthy') {
      return 'border-olive-500';
    }
    return 'border-surface-400';
  };

  return (
    <div className={`
      relative overflow-hidden rounded-2xl p-6
      glass-card
      border-2
      ${getBorderColor()}
    `}>
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        {/* Left: Status Info */}
        <div className="flex items-start gap-4">
          <div className={`
            p-3 rounded-xl
            ${overallStatus === 'healthy' ? 'bg-olive-100 dark:bg-olive-900/30' : ''}
            ${overallStatus === 'warning' ? 'bg-warning-100 dark:bg-warning-900/30' : ''}
            ${overallStatus === 'critical' ? 'bg-critical-100 dark:bg-critical-900/30' : ''}
            ${overallStatus === 'unknown' ? 'bg-surface-100 dark:bg-surface-700' : ''}
          `}>
            <ShieldCheckIcon className={`w-8 h-8
              ${overallStatus === 'healthy' ? 'text-olive-600 dark:text-olive-400' : ''}
              ${overallStatus === 'warning' ? 'text-warning-600 dark:text-warning-400' : ''}
              ${overallStatus === 'critical' ? 'text-critical-600 dark:text-critical-400' : ''}
              ${overallStatus === 'unknown' ? 'text-surface-500' : ''}
            `} />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-surface-900 dark:text-surface-100">
              Constitutional AI Status
            </h2>
            <p className="mt-1 text-surface-600 dark:text-surface-400">
              {statusMessages[overallStatus]}
            </p>
            <div className="mt-3 flex flex-wrap gap-3">
              <StatusChip
                icon={<CheckCircleIcon className="w-4 h-4" />}
                label="CAI Active"
                active={status?.constitutional_ai_active}
              />
              <StatusChip
                icon={<ShieldCheckIcon className="w-4 h-4" />}
                label="Guardrails Active"
                active={status?.guardrails_active}
              />
            </div>
          </div>
        </div>

        {/* Right: Compliance Score */}
        <div className="flex items-center gap-4">
          <ProgressChart
            value={complianceScore}
            max={100}
            label="Compliance"
            color={complianceScore >= 90 ? 'olive' : complianceScore >= 70 ? 'warning' : 'critical'}
            size={100}
            strokeWidth={10}
          />
        </div>
      </div>
    </div>
  );
});

/**
 * Status Chip Component
 */
const StatusChip = memo(function StatusChip({ icon, label, active }) {
  return (
    <span className={`
      inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium
      ${active
        ? 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400'
        : 'bg-surface-100 text-surface-500 dark:bg-surface-700 dark:text-surface-400'
      }
    `}>
      {icon}
      {label}
    </span>
  );
});

/**
 * Quick Stats Section
 */
const QuickStats = memo(function QuickStats({ status, metrics: _metrics }) {
  if (!status) return null;

  return (
    <MetricCardGrid columns={4}>
      <MetricCard
        title="Active Principles"
        value={status.active_principles_count || 0}
        subtitle={`${status.critical_principles_count || 0} critical`}
        icon={ScaleIcon}
        iconColor="aura"
      />
      <MetricCard
        title="Decisions (24h)"
        value={status.decisions_last_24h || 0}
        subtitle={`${status.issues_last_24h || 0} issues found`}
        icon={ClockIcon}
        iconColor={status.issues_last_24h > 0 ? 'warning' : 'olive'}
      />
      <MetricCard
        title="Pending HITL"
        value={status.pending_hitl_approvals || 0}
        subtitle={`${status.pending_hitl_critical || 0} critical, ${status.pending_hitl_high || 0} high`}
        icon={CpuChipIcon}
        iconColor={status.pending_hitl_critical > 0 ? 'critical' : status.pending_hitl_approvals > 0 ? 'warning' : 'olive'}
        status={status.pending_hitl_critical > 0 ? 'critical' : status.pending_hitl_approvals > 5 ? 'warning' : 'healthy'}
      />
      <MetricCard
        title="Last Evaluation"
        value={formatTimeAgo(status.last_evaluation_time)}
        subtitle="Most recent check"
        icon={CheckCircleIcon}
        iconColor="olive"
      />
    </MetricCardGrid>
  );
});

/**
 * Key Metrics Section
 */
const KeyMetrics = memo(function KeyMetrics({ metrics }) {
  if (!metrics) return null;

  const metricsData = [
    {
      title: 'Critique Accuracy',
      metric: metrics.critiqueAccuracy,
      targetLabel: 'Target: 90%',
    },
    {
      title: 'Revision Convergence',
      metric: metrics.revisionConvergence,
      targetLabel: 'Target: 95%',
    },
    {
      title: 'Cache Hit Rate',
      metric: metrics.cacheHitRate,
      targetLabel: 'Target: 30%',
    },
    {
      title: 'Non-Evasive Rate',
      metric: metrics.nonEvasiveRate,
      targetLabel: 'Target: 70%',
    },
  ];

  return (
    <div>
      <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4">
        Key Safety Metrics
      </h3>
      <MetricCardGrid columns={4}>
        {metricsData.map((item) => {
          // Generate status label combining health status and trend
          const getStatusLabel = () => {
            if (!item.metric) return 'No Data';
            const status = item.metric.status;
            const trend = item.metric.trend;
            if (status === 'critical') return trend === 'degrading' ? 'Critical - Degrading' : 'Critical';
            if (status === 'warning') return trend === 'degrading' ? 'Warning - Degrading' : trend === 'improving' ? 'Warning - Improving' : 'Warning';
            return trend === 'improving' ? 'Healthy - Improving' : 'Healthy';
          };

          return (
            <MetricCard
              key={item.title}
              title={item.title}
              value={item.metric ? `${item.metric.current_value?.toFixed(1)}%` : '--'}
              subtitle={item.targetLabel}
              status={item.metric?.status || 'neutral'}
              statusLabel={getStatusLabel()}
              trend={item.metric?.change_24h}
            />
          );
        })}
      </MetricCardGrid>
    </div>
  );
});

/**
 * Helper: Format autonomy level
 */
function formatAutonomyLevel(level) {
  if (!level) return 'Unknown';
  const labels = {
    full_hitl: 'Full HITL',
    critical_hitl: 'Critical HITL',
    audit_only: 'Audit Only',
    full_autonomous: 'Autonomous',
  };
  return labels[level] || level.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

/**
 * Helper: Format time ago
 */
function formatTimeAgo(isoString) {
  if (!isoString) return 'Never';
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

/**
 * Main Overview Tab Component
 */
export default function OverviewTab({ status, complianceScore, metrics, principles: _principles, autonomy: _autonomy, loading }) {
  if (loading) {
    return (
      <div className="space-y-6">
        {/* Legend skeleton */}
        <div className="skeleton h-14 rounded-xl" />
        {/* Hero skeleton */}
        <div className="skeleton h-40 rounded-2xl" />
        <div className="grid grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="skeleton h-32 rounded-xl" />
          ))}
        </div>
        <div className="grid grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="skeleton h-32 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Status Threshold Legend */}
      <StatusLegend />

      {/* Hero Section */}
      <StatusHero status={status} complianceScore={complianceScore} />

      {/* Quick Stats */}
      <QuickStats status={status} metrics={metrics} />

      {/* Key Metrics */}
      <KeyMetrics metrics={metrics} />
    </div>
  );
}
