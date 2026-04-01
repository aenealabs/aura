/**
 * ViolationHeatmap - Compact matrix visualization of violations by rule and environment
 *
 * Displays all 14 validation rules (8 critical, 4 warning, 2 info) in a space-efficient
 * heatmap format with clear swim lane separation by severity.
 *
 * Design: Optimized for ~380px card height with proper Aura design system colors.
 */

import { Environments } from '../../services/envValidatorApi';

// Rule definitions organized by severity
const RULES = {
  critical: [
    { id: 'ENV-001', label: 'Account ID' },
    { id: 'ENV-002', label: 'ECR Registry' },
    { id: 'ENV-003', label: 'DynamoDB' },
    { id: 'ENV-004', label: 'Neptune/OS' },
    { id: 'ENV-005', label: 'SNS/SQS' },
    { id: 'ENV-006', label: 'Region' },
    { id: 'ENV-007', label: 'KMS Keys' },
    { id: 'ENV-008', label: 'IAM Roles' },
  ],
  warning: [
    { id: 'ENV-101', label: 'ENV Vars' },
    { id: 'ENV-102', label: 'Secrets' },
    { id: 'ENV-103', label: 'Log Groups' },
    { id: 'ENV-104', label: 'IRSA' },
  ],
  info: [
    { id: 'ENV-201', label: 'Naming' },
    { id: 'ENV-202', label: 'Tags' },
  ],
};

// Mock data for development
const MOCK_HEATMAP_DATA = {
  dev: {
    'ENV-001': 0, 'ENV-002': 2, 'ENV-003': 0, 'ENV-004': 0,
    'ENV-005': 0, 'ENV-006': 0, 'ENV-007': 0, 'ENV-008': 1,
    'ENV-101': 3, 'ENV-102': 1, 'ENV-103': 0, 'ENV-104': 0,
    'ENV-201': 5, 'ENV-202': 2,
  },
  qa: {
    'ENV-001': 1, 'ENV-002': 0, 'ENV-003': 0, 'ENV-004': 0,
    'ENV-005': 0, 'ENV-006': 0, 'ENV-007': 0, 'ENV-008': 0,
    'ENV-101': 1, 'ENV-102': 0, 'ENV-103': 2, 'ENV-104': 1,
    'ENV-201': 3, 'ENV-202': 1,
  },
  prod: {
    'ENV-001': 0, 'ENV-002': 0, 'ENV-003': 0, 'ENV-004': 0,
    'ENV-005': 0, 'ENV-006': 0, 'ENV-007': 0, 'ENV-008': 0,
    'ENV-101': 0, 'ENV-102': 0, 'ENV-103': 0, 'ENV-104': 0,
    'ENV-201': 1, 'ENV-202': 0,
  },
};

// Severity-specific color configurations matching Aura design system
const SEVERITY_CONFIG = {
  critical: {
    label: 'Critical',
    // Cell colors - red palette
    cellBg: 'bg-critical-100 dark:bg-critical-900/40',
    cellText: 'text-critical-700 dark:text-critical-300',
    cellRing: 'ring-critical-500',
    // Swim lane colors - transparent background, border only
    laneBorder: 'border-l-critical-500',
    labelText: 'text-critical-600 dark:text-critical-400',
  },
  warning: {
    label: 'Warning',
    // Cell colors - amber palette
    cellBg: 'bg-warning-100 dark:bg-warning-900/40',
    cellText: 'text-warning-700 dark:text-warning-300',
    cellRing: 'ring-warning-500',
    // Swim lane colors - transparent background, border only
    laneBorder: 'border-l-warning-500',
    labelText: 'text-warning-600 dark:text-warning-400',
  },
  info: {
    label: 'Info',
    // Cell colors - blue palette
    cellBg: 'bg-aura-100 dark:bg-aura-900/40',
    cellText: 'text-aura-700 dark:text-aura-300',
    cellRing: 'ring-aura-500',
    // Swim lane colors - transparent background, border only
    laneBorder: 'border-l-aura-500',
    labelText: 'text-aura-600 dark:text-aura-400',
  },
};

/**
 * Individual heatmap cell - clickable button
 */
function HeatCell({ count, severity, onClick, ruleId, env }) {
  const config = SEVERITY_CONFIG[severity];
  const hasViolations = count > 0;
  const isHigh = count >= 3;

  // Build cell classes based on violation count
  const cellClasses = hasViolations
    ? `${config.cellBg} ${config.cellText} ${isHigh ? `ring-2 ring-inset ${config.cellRing}` : ''}`
    : 'bg-surface-100 dark:bg-surface-700/50 text-surface-400 dark:text-surface-500';

  return (
    <button
      type="button"
      onClick={() => onClick?.(ruleId, env)}
      className={`
        w-10 h-7 rounded-md flex items-center justify-center
        text-sm font-semibold
        transition-all duration-150
        hover:scale-105 hover:shadow-md hover:z-10
        focus:outline-none focus-visible:ring-2 focus-visible:ring-aura-500
        ${cellClasses}
      `}
      title={`${ruleId} in ${env.toUpperCase()}: ${count} violation${count !== 1 ? 's' : ''}`}
      aria-label={`${count} violations for ${ruleId} in ${env}`}
    >
      {hasViolations ? count : '\u2013'}
    </button>
  );
}

/**
 * Single rule row within a severity section
 */
function RuleRow({ rule, severity, data, environments, onCellClick }) {
  return (
    <div className="flex items-center gap-3 h-8">
      {/* Rule label - fixed width with no truncation to show full text */}
      <div
        className="w-24 text-sm text-surface-600 dark:text-surface-400 whitespace-nowrap"
        title={rule.label}
      >
        {rule.label}
      </div>
      {/* Environment cells */}
      <div className="flex gap-1.5">
        {environments.map((env) => (
          <HeatCell
            key={env}
            count={data[env]?.[rule.id] || 0}
            severity={severity}
            onClick={onCellClick}
            ruleId={rule.id}
            env={env}
          />
        ))}
      </div>
    </div>
  );
}

/**
 * Severity swim lane - compact section with left border indicator
 */
function SeverityLane({ severity, rules, data, environments, onCellClick }) {
  const config = SEVERITY_CONFIG[severity];

  return (
    <div className={`border-l-2 ${config.laneBorder} pl-2 py-1.5`}>
      {/* Section label */}
      <div className={`text-[11px] font-bold ${config.labelText} uppercase tracking-wider mb-1`}>
        {config.label} ({rules.length})
      </div>
      {/* Rules grid */}
      <div className="space-y-0.5">
        {rules.map((rule) => (
          <RuleRow
            key={rule.id}
            rule={rule}
            severity={severity}
            data={data}
            environments={environments}
            onCellClick={onCellClick}
          />
        ))}
      </div>
    </div>
  );
}

/**
 * Sidebar legend explaining the heatmap scoring
 */
function HeatmapSidebarLegend() {
  return (
    <div className="w-52 flex-shrink-0 border-l border-surface-200 dark:border-surface-700 p-4 space-y-5">
      {/* Violation Count Scale */}
      <div>
        <h4 className="text-sm font-semibold text-surface-700 dark:text-surface-300 mb-3">
          Violation Count
        </h4>
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <div className="w-8 h-6 rounded bg-surface-100 dark:bg-surface-700/50 border border-surface-200 dark:border-surface-600 flex items-center justify-center text-xs text-surface-400">–</div>
            <span className="text-sm text-surface-600 dark:text-surface-400">No violations</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-8 h-6 rounded bg-critical-100 dark:bg-critical-900/40 flex items-center justify-center text-xs text-critical-700 dark:text-critical-300 font-semibold">1</div>
            <span className="text-sm text-surface-600 dark:text-surface-400">Low count</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-8 h-6 rounded bg-critical-100 dark:bg-critical-900/40 ring-2 ring-inset ring-critical-500 flex items-center justify-center text-xs text-critical-700 dark:text-critical-300 font-semibold">3+</div>
            <span className="text-sm text-surface-600 dark:text-surface-400">High priority</span>
          </div>
        </div>
      </div>

      {/* Severity Categories */}
      <div>
        <h4 className="text-sm font-semibold text-surface-700 dark:text-surface-300 mb-3">
          Severity Levels
        </h4>
        <div className="space-y-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <div className="w-1.5 h-4 rounded-full bg-critical-500" />
              <span className="text-sm font-medium text-critical-600 dark:text-critical-400">Critical</span>
            </div>
            <p className="text-xs text-surface-500 dark:text-surface-400 pl-3.5">
              Wrong account, ECR, databases, IAM
            </p>
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <div className="w-1.5 h-4 rounded-full bg-warning-500" />
              <span className="text-sm font-medium text-warning-600 dark:text-warning-400">Warning</span>
            </div>
            <p className="text-xs text-surface-500 dark:text-surface-400 pl-3.5">
              Env vars, secrets, logs, IRSA
            </p>
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <div className="w-1.5 h-4 rounded-full bg-aura-500" />
              <span className="text-sm font-medium text-aura-600 dark:text-aura-400">Info</span>
            </div>
            <p className="text-xs text-surface-500 dark:text-surface-400 pl-3.5">
              Naming conventions, tags
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Loading skeleton for the heatmap
 */
function HeatmapSkeleton() {
  return (
    <div className="h-full flex flex-col">
      <div className="px-3 py-2 border-b border-surface-200 dark:border-surface-700">
        <div className="h-4 w-32 bg-surface-200 dark:bg-surface-700 rounded animate-pulse" />
      </div>
      <div className="flex-1 p-3 space-y-3">
        {[8, 4, 2].map((count, i) => (
          <div key={i} className="space-y-1">
            <div className="h-3 w-16 bg-surface-200 dark:bg-surface-700 rounded animate-pulse" />
            {[...Array(count)].map((_, j) => (
              <div key={j} className="h-6 bg-surface-200 dark:bg-surface-700 rounded animate-pulse" />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * ViolationHeatmap - Main component
 *
 * Compact matrix visualization showing all 14 validation rules across 3 environments.
 * Designed to fit within a ~380px card with clear visual hierarchy.
 */
export default function ViolationHeatmap({
  data = MOCK_HEATMAP_DATA,
  onCellClick,
  loading = false,
  showLegend = true,
  filterEnv = null,
}) {
  // Get environments to display (filter if specified)
  const displayEnvs = filterEnv ? [filterEnv] : Environments;
  if (loading) {
    return (
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 shadow-card h-full">
        <HeatmapSkeleton />
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 shadow-card h-full flex flex-col">
      {/* Header row */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-surface-200 dark:border-surface-700">
        <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100">
          Violation Heatmap
        </h3>
      </div>

      {/* Main content area with heatmap and sidebar legend */}
      <div className="flex-1 flex min-h-0">
        {/* Heatmap content */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Column headers - padding matches swim lane content: p-2 + border(2px) + pl-2 = 18px */}
          <div className="flex items-center gap-3 pl-[18px] pr-2 py-2 bg-surface-50 dark:bg-surface-800/50">
            <div className="w-24 text-xs font-medium text-surface-500 dark:text-surface-400">
              Rule
            </div>
            <div className="flex gap-1.5">
              {displayEnvs.map((env) => (
                <div
                  key={env}
                  className="w-10 text-center text-xs font-bold text-surface-600 dark:text-surface-400 uppercase"
                >
                  {env}
                </div>
              ))}
            </div>
          </div>

          {/* Severity swim lanes */}
          <div className="flex-1 p-2 space-y-2 overflow-y-auto">
            <SeverityLane
              severity="critical"
              rules={RULES.critical}
              data={data}
              environments={displayEnvs}
              onCellClick={onCellClick}
            />
            <SeverityLane
              severity="warning"
              rules={RULES.warning}
              data={data}
              environments={displayEnvs}
              onCellClick={onCellClick}
            />
            <SeverityLane
              severity="info"
              rules={RULES.info}
              data={data}
              environments={displayEnvs}
              onCellClick={onCellClick}
            />
          </div>
        </div>

        {/* Sidebar legend */}
        {showLegend && <HeatmapSidebarLegend />}
      </div>
    </div>
  );
}
