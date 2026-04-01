/**
 * DecisionExplorer Component (ADR-068)
 *
 * Search, filter, and browse AI decisions with full audit trail.
 * Provides visibility into agent decision-making with expandable details.
 *
 * @module components/explainability/DecisionExplorer
 */

import React, { useState, useMemo } from 'react';
import PropTypes from 'prop-types';
import {
  MagnifyingGlassIcon,
  FunnelIcon,
  ArrowDownTrayIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  ExclamationTriangleIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import { ConfidenceBadge, FilterChip } from '../shared';

/**
 * Severity color mappings
 */
const SEVERITY_COLORS = {
  trivial: 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-400',
  normal: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
  significant: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
  critical: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
};

/**
 * Format relative time from timestamp
 */
function formatRelativeTime(timestamp) {
  const now = new Date();
  const date = new Date(timestamp);
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

/**
 * DecisionRow - Single decision row with expandable details
 */
function DecisionRow({ decision, isExpanded, onToggle, onViewDetails }) {
  return (
    <div
      className={`
        border-b border-surface-200 dark:border-surface-700 last:border-0
        hover:bg-surface-50 dark:hover:bg-surface-800/50
        transition-colors
        ${decision.hasContradiction ? 'bg-critical-50 dark:bg-critical-900/10' : ''}
      `}
    >
      {/* Main row */}
      <div
        className="flex items-center gap-4 px-4 py-3 cursor-pointer"
        onClick={onToggle}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && onToggle()}
        aria-expanded={isExpanded}
      >
        {/* Expand/collapse button */}
        <button className="p-1 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300">
          {isExpanded ? (
            <ChevronDownIcon className="w-5 h-5" />
          ) : (
            <ChevronRightIcon className="w-5 h-5" />
          )}
        </button>

        {/* Decision summary */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="font-medium text-surface-900 dark:text-surface-100 truncate">
              {decision.summary}
            </p>
            {decision.hasContradiction && (
              <span
                className="flex items-center gap-1 px-2 py-0.5 rounded-full
                           bg-critical-100 dark:bg-critical-900/30
                           text-critical-700 dark:text-critical-400 text-xs font-medium"
              >
                <ExclamationTriangleIcon className="w-3 h-3" />
                Contradiction
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span
              className={`px-2 py-0.5 rounded text-xs font-medium ${
                SEVERITY_COLORS[decision.severity]
              }`}
            >
              {decision.severity.toUpperCase()}
            </span>
          </div>
        </div>

        {/* Agent */}
        <div className="text-sm text-surface-500 dark:text-surface-400 w-28">
          {decision.agentName}
        </div>

        {/* Confidence */}
        <ConfidenceBadge value={decision.confidence} size="sm" />

        {/* Timestamp */}
        <div className="text-sm text-surface-500 dark:text-surface-400 w-24 text-right">
          {formatRelativeTime(decision.timestamp)}
        </div>

        {/* View button */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onViewDetails(decision);
          }}
          className="px-3 py-1 text-sm text-aura-600 dark:text-aura-400
                     hover:bg-aura-50 dark:hover:bg-aura-900/20 rounded transition-colors"
        >
          View
        </button>
      </div>

      {/* Expanded details */}
      {isExpanded && (
        <div className="px-12 pb-4 space-y-3">
          {/* Input */}
          <div>
            <h4 className="text-xs font-medium text-surface-500 dark:text-surface-400 uppercase mb-1">
              Input
            </h4>
            <p className="text-sm text-surface-700 dark:text-surface-300 bg-surface-100 dark:bg-surface-800 rounded-lg p-3">
              {decision.input}
            </p>
          </div>

          {/* Brief reasoning */}
          {decision.briefReasoning && (
            <div>
              <h4 className="text-xs font-medium text-surface-500 dark:text-surface-400 uppercase mb-1">
                Reasoning Summary
              </h4>
              <p className="text-sm text-surface-700 dark:text-surface-300">
                {decision.briefReasoning}
              </p>
            </div>
          )}

          {/* Output */}
          <div>
            <h4 className="text-xs font-medium text-surface-500 dark:text-surface-400 uppercase mb-1">
              Output
            </h4>
            <p className="text-sm text-surface-700 dark:text-surface-300 bg-surface-100 dark:bg-surface-800 rounded-lg p-3">
              {decision.output}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

DecisionRow.propTypes = {
  decision: PropTypes.shape({
    id: PropTypes.string.isRequired,
    summary: PropTypes.string.isRequired,
    severity: PropTypes.oneOf(['trivial', 'normal', 'significant', 'critical']).isRequired,
    agentName: PropTypes.string.isRequired,
    confidence: PropTypes.number.isRequired,
    timestamp: PropTypes.string.isRequired,
    hasContradiction: PropTypes.bool,
    input: PropTypes.string,
    briefReasoning: PropTypes.string,
    output: PropTypes.string,
  }).isRequired,
  isExpanded: PropTypes.bool.isRequired,
  onToggle: PropTypes.func.isRequired,
  onViewDetails: PropTypes.func.isRequired,
};

/**
 * FilterPanel - Dropdown filter panel
 */
function FilterPanel({ filters, onFiltersChange, agents, isOpen, onClose }) {
  if (!isOpen) return null;

  const severityOptions = ['trivial', 'normal', 'significant', 'critical'];
  const timeRangeOptions = [
    { value: '1h', label: 'Last Hour' },
    { value: '24h', label: 'Last 24 Hours' },
    { value: '7d', label: 'Last 7 Days' },
    { value: '30d', label: 'Last 30 Days' },
  ];

  return (
    <div className="absolute right-0 top-full mt-2 z-20 w-80 bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 shadow-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-medium text-surface-900 dark:text-surface-100">Filters</h3>
        <button onClick={onClose} className="p-1 text-surface-400 hover:text-surface-600">
          <XMarkIcon className="w-5 h-5" />
        </button>
      </div>

      <div className="space-y-4">
        {/* Agent filter */}
        <div>
          <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1.5">
            Agent
          </label>
          <select
            value={filters.agent || ''}
            onChange={(e) => onFiltersChange({ ...filters, agent: e.target.value || null })}
            className="w-full px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100"
          >
            <option value="">All Agents</option>
            {agents.map((agent) => (
              <option key={agent.id} value={agent.id}>
                {agent.name}
              </option>
            ))}
          </select>
        </div>

        {/* Severity filter */}
        <div>
          <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1.5">
            Severity
          </label>
          <div className="flex flex-wrap gap-2">
            {severityOptions.map((severity) => (
              <FilterChip
                key={severity}
                label={severity.charAt(0).toUpperCase() + severity.slice(1)}
                active={filters.severities?.includes(severity) ?? true}
                onChange={(active) => {
                  const current = filters.severities || severityOptions;
                  const updated = active
                    ? [...current, severity]
                    : current.filter((s) => s !== severity);
                  onFiltersChange({ ...filters, severities: updated });
                }}
                size="sm"
              />
            ))}
          </div>
        </div>

        {/* Time range */}
        <div>
          <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1.5">
            Time Range
          </label>
          <select
            value={filters.timeRange || '24h'}
            onChange={(e) => onFiltersChange({ ...filters, timeRange: e.target.value })}
            className="w-full px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100"
          >
            {timeRangeOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Show contradictions only */}
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={filters.contradictionsOnly || false}
            onChange={(e) =>
              onFiltersChange({ ...filters, contradictionsOnly: e.target.checked })
            }
            className="w-4 h-4 rounded border-surface-300 text-aura-600 focus:ring-aura-500"
          />
          <span className="text-sm text-surface-700 dark:text-surface-300">
            Show contradictions only
          </span>
        </label>

        {/* Clear filters */}
        <button
          onClick={() => onFiltersChange({})}
          className="w-full px-3 py-2 text-sm text-aura-600 dark:text-aura-400 hover:bg-aura-50 dark:hover:bg-aura-900/20 rounded-lg transition-colors"
        >
          Clear All Filters
        </button>
      </div>
    </div>
  );
}

FilterPanel.propTypes = {
  filters: PropTypes.object.isRequired,
  onFiltersChange: PropTypes.func.isRequired,
  agents: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
      name: PropTypes.string.isRequired,
    })
  ).isRequired,
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
};

/**
 * DecisionExplorer - Main component
 *
 * @param {Object} props
 * @param {Array} props.decisions - List of decisions to display
 * @param {Array} [props.agents=[]] - Available agents for filtering
 * @param {Function} [props.onViewDecision] - Callback when viewing decision details
 * @param {Function} [props.onExport] - Callback for exporting decisions
 * @param {boolean} [props.isLoading=false] - Loading state
 * @param {number} [props.totalCount] - Total decisions count for pagination
 * @param {number} [props.page=1] - Current page
 * @param {number} [props.pageSize=20] - Items per page
 * @param {Function} [props.onPageChange] - Page change callback
 * @param {string} [props.className] - Additional CSS classes
 */
function DecisionExplorer({
  decisions,
  agents = [],
  onViewDecision,
  onExport,
  isLoading = false,
  totalCount,
  page = 1,
  pageSize = 20,
  onPageChange,
  className = '',
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [filters, setFilters] = useState({});
  const [showFilters, setShowFilters] = useState(false);
  const [expandedIds, setExpandedIds] = useState(new Set());

  // Filter decisions locally
  const filteredDecisions = useMemo(() => {
    let result = decisions;

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(
        (d) =>
          d.summary.toLowerCase().includes(query) ||
          d.input?.toLowerCase().includes(query) ||
          d.output?.toLowerCase().includes(query)
      );
    }

    // Agent filter
    if (filters.agent) {
      result = result.filter((d) => d.agentId === filters.agent);
    }

    // Severity filter
    if (filters.severities && filters.severities.length > 0) {
      result = result.filter((d) => filters.severities.includes(d.severity));
    }

    // Contradictions only
    if (filters.contradictionsOnly) {
      result = result.filter((d) => d.hasContradiction);
    }

    return result;
  }, [decisions, searchQuery, filters]);

  const toggleExpanded = (id) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const hasActiveFilters = Object.keys(filters).some((key) => {
    const value = filters[key];
    if (Array.isArray(value)) return value.length > 0;
    return Boolean(value);
  });

  const totalPages = Math.ceil((totalCount || filteredDecisions.length) / pageSize);
  const startIndex = (page - 1) * pageSize + 1;
  const endIndex = Math.min(page * pageSize, totalCount || filteredDecisions.length);

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
          Decision Explorer
        </h2>
        <div className="flex items-center gap-2">
          {onExport && (
            <button
              onClick={onExport}
              className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-800 rounded-lg transition-colors"
            >
              <ArrowDownTrayIcon className="w-4 h-4" />
              Export
            </button>
          )}
          <div className="relative">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
                hasActiveFilters
                  ? 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400'
                  : 'text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-800'
              }`}
            >
              <FunnelIcon className="w-4 h-4" />
              Filter
              {hasActiveFilters && (
                <span className="w-2 h-2 rounded-full bg-aura-600" />
              )}
            </button>
            <FilterPanel
              filters={filters}
              onFiltersChange={setFilters}
              agents={agents}
              isOpen={showFilters}
              onClose={() => setShowFilters(false)}
            />
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="relative">
        <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-surface-400" />
        <input
          type="text"
          placeholder="Search decisions..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-10 pr-4 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-aura-500 focus:border-aura-500"
        />
      </div>

      {/* Decisions list */}
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 overflow-hidden">
        {/* Table header */}
        <div className="flex items-center gap-4 px-4 py-2 bg-surface-50 dark:bg-surface-900 border-b border-surface-200 dark:border-surface-700 text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wide">
          <div className="w-6" />
          <div className="flex-1">Decision</div>
          <div className="w-28">Agent</div>
          <div className="w-16">Confidence</div>
          <div className="w-24 text-right">Time</div>
          <div className="w-16" />
        </div>

        {/* Decision rows */}
        {isLoading ? (
          <div className="p-8 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-aura-600 mx-auto" />
            <p className="mt-2 text-sm text-surface-500">Loading decisions...</p>
          </div>
        ) : filteredDecisions.length === 0 ? (
          <div className="p-8 text-center text-surface-500 dark:text-surface-400">
            No decisions found
          </div>
        ) : (
          <div>
            {filteredDecisions.map((decision) => (
              <DecisionRow
                key={decision.id}
                decision={decision}
                isExpanded={expandedIds.has(decision.id)}
                onToggle={() => toggleExpanded(decision.id)}
                onViewDetails={() => onViewDecision?.(decision)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <p className="text-surface-600 dark:text-surface-400">
            Showing {startIndex}-{endIndex} of {totalCount || filteredDecisions.length} decisions
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onPageChange?.(page - 1)}
              disabled={page <= 1}
              className="px-3 py-1 rounded border border-surface-300 dark:border-surface-600 text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            {[...Array(Math.min(5, totalPages))].map((_, i) => {
              const pageNum = i + 1;
              return (
                <button
                  key={pageNum}
                  onClick={() => onPageChange?.(pageNum)}
                  className={`px-3 py-1 rounded ${
                    page === pageNum
                      ? 'bg-aura-600 text-white'
                      : 'border border-surface-300 dark:border-surface-600 text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700'
                  }`}
                >
                  {pageNum}
                </button>
              );
            })}
            <button
              onClick={() => onPageChange?.(page + 1)}
              disabled={page >= totalPages}
              className="px-3 py-1 rounded border border-surface-300 dark:border-surface-600 text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

DecisionExplorer.propTypes = {
  decisions: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
      summary: PropTypes.string.isRequired,
      severity: PropTypes.string.isRequired,
      agentId: PropTypes.string,
      agentName: PropTypes.string.isRequired,
      confidence: PropTypes.number.isRequired,
      timestamp: PropTypes.string.isRequired,
      hasContradiction: PropTypes.bool,
      input: PropTypes.string,
      briefReasoning: PropTypes.string,
      output: PropTypes.string,
    })
  ).isRequired,
  agents: PropTypes.array,
  onViewDecision: PropTypes.func,
  onExport: PropTypes.func,
  isLoading: PropTypes.bool,
  totalCount: PropTypes.number,
  page: PropTypes.number,
  pageSize: PropTypes.number,
  onPageChange: PropTypes.func,
  className: PropTypes.string,
};

export default DecisionExplorer;
