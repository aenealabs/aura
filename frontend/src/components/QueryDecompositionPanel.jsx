/**
 * Query Decomposition Panel Component (ADR-028 Phase 3 - Issue #32)
 *
 * Shows how complex queries are decomposed into parallel subqueries,
 * providing transparency into the retrieval process.
 *
 * Features:
 * - Collapsible panel (collapsed by default)
 * - Visual subquery flow diagram
 * - Color-coded query types (structural, semantic, temporal)
 * - Confidence score progress bars
 * - Execution time display
 */

import { useState } from 'react';
import {
  ChevronDownIcon,
  ChevronUpIcon,
  ClockIcon,
  MagnifyingGlassIcon,
  CircleStackIcon,
  CalendarIcon,
  DocumentMagnifyingGlassIcon,
} from '@heroicons/react/24/outline';

// ============================================================================
// Constants and Styles
// ============================================================================

const QUERY_TYPE_CONFIG = {
  structural: {
    color: '#3B82F6', // Aura Blue
    bgColor: 'bg-aura-50 dark:bg-aura-900/20',
    borderColor: 'border-aura-200 dark:border-aura-800',
    textColor: 'text-aura-800 dark:text-aura-300',
    badgeBg: 'bg-aura-100 dark:bg-aura-900/30',
    icon: CircleStackIcon,
    label: 'Structural',
    description: 'Graph database (Neptune)',
  },
  semantic: {
    color: '#8B5CF6', // Violet (kept for visual distinction)
    bgColor: 'bg-purple-50 dark:bg-purple-900/20',
    borderColor: 'border-purple-200 dark:border-purple-800',
    textColor: 'text-purple-800 dark:text-purple-300',
    badgeBg: 'bg-purple-100 dark:bg-purple-900/30',
    icon: DocumentMagnifyingGlassIcon,
    label: 'Semantic',
    description: 'Vector search (OpenSearch)',
  },
  temporal: {
    color: '#10B981', // Olive Green
    bgColor: 'bg-olive-50 dark:bg-olive-900/20',
    borderColor: 'border-olive-200 dark:border-olive-800',
    textColor: 'text-olive-800 dark:text-olive-300',
    badgeBg: 'bg-olive-100 dark:bg-olive-900/30',
    icon: CalendarIcon,
    label: 'Temporal',
    description: 'Time-based filtering',
  },
};

// ============================================================================
// Main Component
// ============================================================================

const QueryDecompositionPanel = ({
  decomposition,
  isLoading = false,
  defaultExpanded = false,
  onSubqueryClick = null,
}) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  if (!decomposition && !isLoading) {
    return null;
  }

  const subqueryCount = decomposition?.subqueries?.length || 0;

  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl shadow-lg border border-surface-200 dark:border-surface-700 overflow-hidden transition-all duration-300">
      {/* Panel Header - Always visible */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 flex items-center justify-between bg-gradient-to-r from-surface-50 to-white dark:from-surface-800 dark:to-surface-700 hover:from-surface-100 hover:to-surface-50 dark:hover:from-surface-700 dark:hover:to-surface-800 transition-colors"
        aria-expanded={isExpanded}
        aria-controls="query-decomposition-content"
      >
        <div className="flex items-center space-x-3">
          <MagnifyingGlassIcon className="w-5 h-5 text-aura-600 dark:text-aura-400" />
          <span className="font-semibold text-surface-800 dark:text-surface-200">Query Analysis</span>
          {subqueryCount > 0 && (
            <span className="px-2 py-0.5 text-xs font-medium bg-aura-100 dark:bg-aura-900/30 text-aura-800 dark:text-aura-300 rounded-full">
              {subqueryCount} subquer{subqueryCount === 1 ? 'y' : 'ies'}
            </span>
          )}
        </div>
        <div className="flex items-center space-x-2">
          {decomposition?.execution_time_ms && (
            <span className="text-xs text-surface-500 dark:text-surface-400 flex items-center">
              <ClockIcon className="w-3.5 h-3.5 mr-1" />
              {formatTime(decomposition.execution_time_ms)}
            </span>
          )}
          {isExpanded ? (
            <ChevronUpIcon className="w-5 h-5 text-surface-400 dark:text-surface-500" />
          ) : (
            <ChevronDownIcon className="w-5 h-5 text-surface-400 dark:text-surface-500" />
          )}
        </div>
      </button>

      {/* Panel Content - Collapsible */}
      <div
        id="query-decomposition-content"
        className={`transition-all duration-300 ease-in-out overflow-hidden ${
          isExpanded ? 'max-h-[800px] opacity-100' : 'max-h-0 opacity-0'
        }`}
      >
        {isLoading ? (
          <div className="p-6 flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-aura-600 dark:border-aura-400"></div>
            <span className="ml-3 text-surface-600 dark:text-surface-400">Analyzing query...</span>
          </div>
        ) : decomposition ? (
          <div className="p-4 space-y-4">
            {/* Original Query */}
            <OriginalQueryDisplay
              query={decomposition.original_query}
              timestamp={decomposition.timestamp}
            />

            {/* Subquery Flow Diagram */}
            <SubqueryFlowDiagram
              subqueries={decomposition.subqueries}
              onSubqueryClick={onSubqueryClick}
            />

            {/* Execution Summary */}
            <ExecutionSummary
              totalResults={decomposition.total_results}
              executionTime={decomposition.execution_time_ms}
              executionPlan={decomposition.execution_plan}
              reasoning={decomposition.reasoning}
            />
          </div>
        ) : null}
      </div>
    </div>
  );
};

// ============================================================================
// Sub-Components
// ============================================================================

const OriginalQueryDisplay = ({ query, timestamp }) => {
  const formattedTime = timestamp
    ? new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : null;

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wide">
          Original Query
        </span>
        {formattedTime && (
          <span className="text-xs text-surface-400 dark:text-surface-500">Executed at {formattedTime}</span>
        )}
      </div>
      <div className="bg-surface-50 dark:bg-surface-700 border border-surface-200 dark:border-surface-600 rounded-lg p-3">
        <p className="text-surface-800 dark:text-surface-200 font-medium">{query}</p>
      </div>
    </div>
  );
};

const SubqueryFlowDiagram = ({ subqueries, onSubqueryClick }) => {
  if (!subqueries || subqueries.length === 0) {
    return (
      <div className="text-center py-4 text-surface-500 dark:text-surface-400">
        No subqueries generated
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Flow connector from original query */}
      <div className="flex justify-center">
        <div className="w-0.5 h-6 bg-surface-300 dark:bg-surface-600"></div>
      </div>

      {/* Branching visualization */}
      <div className="relative">
        {/* Horizontal connector line */}
        {subqueries.length > 1 && (
          <div
            className="absolute top-0 left-1/2 transform -translate-x-1/2 h-0.5 bg-surface-300 dark:bg-surface-600"
            style={{
              width: `${Math.min(100, (subqueries.length - 1) * 33)}%`,
            }}
          ></div>
        )}

        {/* Vertical connectors */}
        <div className="flex justify-center space-x-4">
          {subqueries.map((_, idx) => (
            <div key={idx} className="flex flex-col items-center" style={{ width: '200px' }}>
              <div className="w-0.5 h-4 bg-surface-300 dark:bg-surface-600"></div>
              <div className="w-2 h-2 rounded-full bg-surface-400 dark:bg-surface-500"></div>
            </div>
          ))}
        </div>
      </div>

      {/* Subquery Cards */}
      <div className="flex flex-wrap justify-center gap-4">
        {subqueries.map((subquery) => (
          <SubqueryCard
            key={subquery.id}
            subquery={subquery}
            onClick={onSubqueryClick ? () => onSubqueryClick(subquery) : undefined}
          />
        ))}
      </div>
    </div>
  );
};

const SubqueryCard = ({ subquery, onClick }) => {
  const config = QUERY_TYPE_CONFIG[subquery.type] || QUERY_TYPE_CONFIG.semantic;
  const Icon = config.icon;

  return (
    <div
      className={`w-52 rounded-lg border-2 ${config.borderColor} ${config.bgColor} p-3 transition-all duration-200 ${
        onClick ? 'cursor-pointer hover:shadow-md hover:scale-[1.02]' : ''
      }`}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => e.key === 'Enter' && onClick() : undefined}
    >
      {/* Type Badge */}
      <div className="flex items-center space-x-2 mb-2">
        <span
          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${config.badgeBg} ${config.textColor}`}
        >
          <Icon className="w-3.5 h-3.5 mr-1" />
          {config.label}
        </span>
      </div>

      {/* Query Text */}
      <p className="text-sm text-surface-700 dark:text-surface-300 mb-3 line-clamp-2" title={subquery.query}>
        {subquery.query}
      </p>

      {/* Metrics */}
      <div className="space-y-2">
        {/* Result Count */}
        <div className="flex justify-between items-center text-xs">
          <span className="text-surface-500 dark:text-surface-400">Results</span>
          <span className="font-semibold text-surface-800 dark:text-surface-200">{subquery.result_count}</span>
        </div>

        {/* Confidence Bar */}
        <div>
          <div className="flex justify-between items-center text-xs mb-1">
            <span className="text-surface-500 dark:text-surface-400">Confidence</span>
            <span className="font-semibold" style={{ color: config.color }}>
              {subquery.confidence.toFixed(0)}%
            </span>
          </div>
          <ConfidenceBar confidence={subquery.confidence} color={config.color} />
        </div>

        {/* Execution Time */}
        <div className="flex justify-between items-center text-xs">
          <span className="text-surface-500 dark:text-surface-400">Time</span>
          <span className="font-mono text-surface-600 dark:text-surface-400">{formatTime(subquery.execution_time_ms)}</span>
        </div>
      </div>
    </div>
  );
};

const ConfidenceBar = ({ confidence, color }) => {
  return (
    <div className="w-full bg-surface-200 dark:bg-surface-600 rounded-full h-1.5 overflow-hidden">
      <div
        className="h-full rounded-full transition-all duration-500"
        style={{
          width: `${confidence}%`,
          backgroundColor: color,
        }}
      ></div>
    </div>
  );
};

const ExecutionSummary = ({ totalResults, executionTime, executionPlan, reasoning }) => {
  const planLabels = {
    parallel: 'Parallel Execution',
    sequential: 'Sequential Execution',
    hybrid: 'Hybrid (Parallel + Sequential)',
  };

  return (
    <div className="bg-surface-50 dark:bg-surface-800 rounded-lg p-3 border border-surface-200 dark:border-surface-700">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-center">
        <div>
          <p className="text-2xl font-bold text-surface-800 dark:text-surface-200">{totalResults}</p>
          <p className="text-xs text-surface-500 dark:text-surface-400">Total Results</p>
        </div>
        <div>
          <p className="text-2xl font-bold text-surface-800 dark:text-surface-200">{formatTime(executionTime)}</p>
          <p className="text-xs text-surface-500 dark:text-surface-400">Total Time</p>
        </div>
        <div>
          <p className="text-sm font-semibold text-surface-800 dark:text-surface-200">{planLabels[executionPlan] || executionPlan}</p>
          <p className="text-xs text-surface-500 dark:text-surface-400">Strategy</p>
        </div>
      </div>
      {reasoning && (
        <p className="mt-3 text-xs text-surface-600 dark:text-surface-400 italic border-t border-surface-200 dark:border-surface-700 pt-2">
          {reasoning}
        </p>
      )}
    </div>
  );
};

// ============================================================================
// Utility Functions
// ============================================================================

function formatTime(ms) {
  if (ms < 1) return '<1ms';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

// ============================================================================
// Query Type Badge (Exported for use in result attribution)
// ============================================================================

export const QueryTypeBadge = ({ type, size = 'sm' }) => {
  const config = QUERY_TYPE_CONFIG[type] || QUERY_TYPE_CONFIG.semantic;
  const Icon = config.icon;

  const sizeClasses = {
    xs: 'px-1.5 py-0.5 text-xs',
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-sm',
  };

  return (
    <span
      className={`inline-flex items-center rounded font-medium ${config.badgeBg} ${config.textColor} ${sizeClasses[size]}`}
      title={config.description}
    >
      <Icon className={`mr-1 ${size === 'xs' ? 'w-3 h-3' : 'w-3.5 h-3.5'}`} />
      {config.label}
    </span>
  );
};

// ============================================================================
// Exports
// ============================================================================

export default QueryDecompositionPanel;
export { QUERY_TYPE_CONFIG, ConfidenceBar, SubqueryCard };
