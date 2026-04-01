/**
 * Audit Tab Component
 *
 * Displays the decision audit timeline with:
 * - Timeline view of Constitutional AI decisions
 * - Filter by agent
 * - Pagination
 * - Decision details (issues, severity, HITL status)
 */

import { memo, useState } from 'react';
import {
  ClipboardDocumentListIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  UserIcon,
  FunnelIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline';

// Agent options for filter
const AGENT_OPTIONS = [
  { value: null, label: 'All Agents' },
  { value: 'CoderAgent', label: 'Coder Agent' },
  { value: 'ReviewerAgent', label: 'Reviewer Agent' },
  { value: 'ValidatorAgent', label: 'Validator Agent' },
  { value: 'PatcherAgent', label: 'Patcher Agent' },
];

/**
 * Filter Bar Component
 */
const FilterBar = memo(function FilterBar({ filter, setFilter }) {
  return (
    <div className="flex flex-wrap items-center gap-4 p-4 rounded-xl glass-card-subtle">
      <div className="flex items-center gap-2 text-surface-500 dark:text-surface-400">
        <FunnelIcon className="w-4 h-4" />
        <span className="text-sm font-medium">Filter</span>
      </div>

      {/* Agent Filter */}
      <select
        value={filter.agentName || ''}
        onChange={(e) => setFilter({ ...filter, agentName: e.target.value || null })}
        className="
          px-3 py-2 rounded-lg text-sm
          bg-white dark:bg-surface-700
          border border-surface-200 dark:border-surface-600
          text-surface-900 dark:text-surface-100
          focus:outline-none focus:ring-2 focus:ring-aura-500
        "
      >
        {AGENT_OPTIONS.map((opt) => (
          <option key={opt.value || 'all'} value={opt.value || ''}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
});

/**
 * Severity Badge Component
 */
const SeverityBadge = memo(function SeverityBadge({ severity, count }) {
  const colors = {
    critical: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
    high: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    medium: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
    low: 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-400',
  };

  if (count === 0) return null;

  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[severity] || colors.low}`}>
      {count} {severity}
    </span>
  );
});

/**
 * Decision Card Component
 */
const DecisionCard = memo(function DecisionCard({ decision }) {
  const [isExpanded, setIsExpanded] = useState(false);

  const hasIssues = decision.issues_found > 0;
  const wasApproved = decision.hitl_approved === true;
  const wasRejected = decision.hitl_approved === false;

  // Status icon
  let StatusIcon = CheckCircleIcon;
  let statusColor = 'olive';
  if (decision.hitl_required) {
    StatusIcon = UserIcon;
    statusColor = wasApproved ? 'olive' : wasRejected ? 'critical' : 'warning';
  } else if (hasIssues) {
    StatusIcon = ExclamationTriangleIcon;
    statusColor = 'warning';
  }

  return (
    <div className="relative pl-8">
      {/* Timeline connector */}
      <div className="absolute left-0 top-0 bottom-0 w-px bg-surface-200 dark:bg-surface-700" />

      {/* Timeline dot */}
      <div className={`
        absolute left-0 top-4 -translate-x-1/2 w-4 h-4 rounded-full border-2 border-white dark:border-surface-900
        ${statusColor === 'olive' ? 'bg-olive-500' : ''}
        ${statusColor === 'warning' ? 'bg-warning-500' : ''}
        ${statusColor === 'critical' ? 'bg-critical-500' : ''}
      `} />

      {/* Card */}
      <div className="glass-card p-4 mb-4 ml-4">
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className={`
              p-2 rounded-lg
              ${statusColor === 'olive' ? 'bg-olive-100 dark:bg-olive-900/30' : ''}
              ${statusColor === 'warning' ? 'bg-warning-100 dark:bg-warning-900/30' : ''}
              ${statusColor === 'critical' ? 'bg-critical-100 dark:bg-critical-900/30' : ''}
            `}>
              <StatusIcon className={`w-5 h-5
                ${statusColor === 'olive' ? 'text-olive-600 dark:text-olive-400' : ''}
                ${statusColor === 'warning' ? 'text-warning-600 dark:text-warning-400' : ''}
                ${statusColor === 'critical' ? 'text-critical-600 dark:text-critical-400' : ''}
              `} />
            </div>
            <div>
              <h4 className="font-semibold text-surface-900 dark:text-surface-100">
                {decision.agent_name}
              </h4>
              <p className="text-sm text-surface-500 dark:text-surface-400">
                {decision.operation_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
              </p>
            </div>
          </div>

          <div className="text-right">
            <div className="text-sm text-surface-500 dark:text-surface-400">
              {new Date(decision.timestamp).toLocaleString()}
            </div>
            <div className="text-xs text-surface-400 dark:text-surface-500">
              {decision.execution_time_ms?.toFixed(0)}ms
            </div>
          </div>
        </div>

        {/* Summary */}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-sm text-surface-600 dark:text-surface-400">
            {decision.principles_evaluated} principles evaluated
          </span>
          <span className="text-surface-300 dark:text-surface-600">|</span>
          <span className={`text-sm ${hasIssues ? 'text-warning-600 dark:text-warning-400' : 'text-olive-600 dark:text-olive-400'}`}>
            {decision.issues_found} issues found
          </span>

          {decision.severity_breakdown && Object.entries(decision.severity_breakdown).map(([severity, count]) => (
            <SeverityBadge key={severity} severity={severity} count={count} />
          ))}
        </div>

        {/* Status badges */}
        <div className="mt-3 flex flex-wrap gap-2">
          {decision.requires_revision && (
            <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400">
              <ExclamationTriangleIcon className="w-3 h-3" />
              Revision Required
            </span>
          )}
          {decision.revised && (
            <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400">
              <CheckCircleIcon className="w-3 h-3" />
              Revised
            </span>
          )}
          {decision.hitl_required && (
            <span className={`
              inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium
              ${wasApproved ? 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400' : ''}
              ${wasRejected ? 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400' : ''}
              ${!wasApproved && !wasRejected ? 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400' : ''}
            `}>
              <UserIcon className="w-3 h-3" />
              {wasApproved ? 'HITL Approved' : wasRejected ? 'HITL Rejected' : 'HITL Pending'}
            </span>
          )}
        </div>

        {/* Approved by */}
        {decision.approved_by && (
          <div className="mt-3 text-sm text-surface-500 dark:text-surface-400">
            Approved by: {decision.approved_by}
          </div>
        )}

        {/* Expand/Collapse */}
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="mt-3 text-xs text-aura-600 dark:text-aura-400 hover:underline"
        >
          {isExpanded ? 'Hide details' : 'Show details'}
        </button>

        {isExpanded && (
          <div className="mt-3 p-3 rounded-lg bg-surface-50 dark:bg-surface-800 text-xs">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <span className="text-surface-500 dark:text-surface-400">Decision ID:</span>
                <span className="ml-2 text-surface-700 dark:text-surface-300 font-mono">
                  {decision.decision_id}
                </span>
              </div>
              <div>
                <span className="text-surface-500 dark:text-surface-400">Execution Time:</span>
                <span className="ml-2 text-surface-700 dark:text-surface-300">
                  {decision.execution_time_ms?.toFixed(2)}ms
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
});

/**
 * Pagination Component
 */
const Pagination = memo(function Pagination({ page, hasMore, onNext, onPrev, totalCount }) {
  return (
    <div className="flex items-center justify-between p-4 rounded-xl glass-card-subtle">
      <span className="text-sm text-surface-500 dark:text-surface-400">
        Showing {page * 20 + 1} - {Math.min((page + 1) * 20, totalCount)} of {totalCount}
      </span>

      <div className="flex items-center gap-2">
        <button
          onClick={onPrev}
          disabled={page === 0}
          className="
            p-2 rounded-lg
            bg-white dark:bg-surface-700
            border border-surface-200 dark:border-surface-600
            text-surface-600 dark:text-surface-400
            hover:bg-surface-50 dark:hover:bg-surface-600
            disabled:opacity-50 disabled:cursor-not-allowed
            transition-colors duration-200
          "
          aria-label="Previous page"
        >
          <ChevronLeftIcon className="w-4 h-4" />
        </button>

        <span className="text-sm text-surface-600 dark:text-surface-400 px-2">
          Page {page + 1}
        </span>

        <button
          onClick={onNext}
          disabled={!hasMore}
          className="
            p-2 rounded-lg
            bg-white dark:bg-surface-700
            border border-surface-200 dark:border-surface-600
            text-surface-600 dark:text-surface-400
            hover:bg-surface-50 dark:hover:bg-surface-600
            disabled:opacity-50 disabled:cursor-not-allowed
            transition-colors duration-200
          "
          aria-label="Next page"
        >
          <ChevronRightIcon className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
});

/**
 * Main Audit Tab Component
 */
export default function AuditTab({
  decisions,
  filter,
  setFilter,
  page,
  onNextPage,
  onPrevPage,
  loading,
}) {
  if (loading) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-16 rounded-xl" />
        <div className="space-y-4">
          {[1, 2, 3, 4, 5].map(i => (
            <div key={i} className="skeleton h-32 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  const decisionsList = decisions?.decisions || [];
  const totalCount = decisions?.total_count || 0;
  const hasMore = decisions?.has_more || false;

  return (
    <div className="space-y-6">
      {/* Filter Bar */}
      <FilterBar filter={filter} setFilter={setFilter} />

      {/* Summary */}
      <div className="text-sm text-surface-500 dark:text-surface-400">
        {totalCount} decisions found
      </div>

      {/* Timeline */}
      <div className="relative">
        {decisionsList.length > 0 ? (
          <div className="space-y-0">
            {decisionsList.map((decision) => (
              <DecisionCard key={decision.decision_id} decision={decision} />
            ))}
          </div>
        ) : (
          <div className="text-center py-12 text-surface-500 dark:text-surface-400">
            <ClipboardDocumentListIcon className="w-12 h-12 mx-auto mb-4 text-surface-300 dark:text-surface-600" />
            <p>No decisions found matching the selected filters.</p>
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalCount > 0 && (
        <Pagination
          page={page}
          hasMore={hasMore}
          onNext={onNextPage}
          onPrev={onPrevPage}
          totalCount={totalCount}
        />
      )}
    </div>
  );
}
