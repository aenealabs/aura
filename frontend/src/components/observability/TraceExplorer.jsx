/**
 * Project Aura - Trace Explorer
 *
 * OpenTelemetry trace visualization dashboard (Issue #30).
 * Displays trace list, timeline/Gantt view, and span details.
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Activity,
  Clock,
  AlertTriangle,
  ChevronRight,
  ChevronDown,
  Search,
  RefreshCw,
  X,
  Info,
  Layers,
  Zap,
  Target,
} from 'lucide-react';

import {
  getTraceMetrics,
  listTraces,
  getTrace,
  formatDuration,
  formatTimestamp,
  formatRelativeTime,
  buildSpanTree,
  flattenSpanTree,
  calculateTimelineScale,
  calculateSpanPosition,
  SPAN_COLORS,
  STATUS_COLORS,
  AGENT_TYPE_INFO,
  TraceStatus,
  AgentType,
} from '../../services/tracesApi';
import { PageSkeleton } from '../ui/LoadingSkeleton';
import { useToast } from '../ui/Toast';

// ============================================================================
// TraceMetricCards Component
// ============================================================================

const TraceMetricCards = ({ metrics, isLoading }) => {
  const cards = [
    {
      id: 'total',
      label: 'Total Traces',
      value: metrics?.total_traces ?? 0,
      icon: Activity,
      color: 'text-brand-500',
      bgColor: 'bg-brand-50 dark:bg-brand-900/20',
    },
    {
      id: 'latency',
      label: 'Avg Latency',
      value: metrics?.avg_latency_ms ? formatDuration(metrics.avg_latency_ms) : '0ms',
      icon: Clock,
      color: 'text-violet-500',
      bgColor: 'bg-violet-50 dark:bg-violet-900/20',
    },
    {
      id: 'errors',
      label: 'Error Rate',
      value: `${(metrics?.error_rate ?? 0).toFixed(1)}%`,
      icon: AlertTriangle,
      color: metrics?.error_rate > 5 ? 'text-critical-500' : 'text-amber-500',
      bgColor: metrics?.error_rate > 5
        ? 'bg-critical-50 dark:bg-critical-900/20'
        : 'bg-amber-50 dark:bg-amber-900/20',
      warning: metrics?.error_rate > 5,
    },
    {
      id: 'coverage',
      label: 'Coverage',
      value: `${(metrics?.coverage ?? 0).toFixed(1)}%`,
      icon: Target,
      color: 'text-warning-500',
      bgColor: 'bg-warning-50 dark:bg-warning-900/20',
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      {cards.map((card) => (
        <div
          key={card.id}
          className={`
            rounded-xl border border-surface-200/50 dark:border-surface-700/30
            bg-white dark:bg-surface-800 backdrop-blur-xl p-4
            shadow-[var(--shadow-glass)] hover:shadow-[var(--shadow-glass-hover)]
            transition-all duration-200 ease-[var(--ease-tahoe)]
            ${card.warning ? 'ring-2 ring-critical-500/50' : ''}
          `}
          role="status"
          aria-label={`${card.label}: ${card.value}`}
        >
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${card.bgColor}`}>
              <card.icon className={`w-5 h-5 ${card.color}`} aria-hidden="true" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-surface-500 dark:text-surface-400 truncate">
                {card.label}
              </p>
              <p className={`text-xl font-semibold ${card.color} ${isLoading ? 'animate-pulse' : ''}`}>
                {isLoading ? '...' : card.value}
              </p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

// ============================================================================
// TraceFilterBar Component
// ============================================================================

const TraceFilterBar = ({
  filters,
  onFilterChange,
  onSearch,
}) => {
  const [searchValue, setSearchValue] = useState(filters.search || '');

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    onSearch(searchValue);
  };

  const handleSearchClear = () => {
    setSearchValue('');
    onSearch('');
  };

  return (
    <div className="flex flex-wrap items-center gap-3 mb-4">
      {/* Search */}
      <form onSubmit={handleSearchSubmit} className="relative flex-1 min-w-[200px] max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-surface-400" />
        <input
          type="text"
          value={searchValue}
          onChange={(e) => setSearchValue(e.target.value)}
          placeholder="Search traces..."
          className="w-full pl-10 pr-8 py-2 border border-surface-300 dark:border-surface-600 rounded-lg
            bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400
            focus:ring-2 focus:ring-aura-500 focus:border-transparent"
          aria-label="Search traces"
        />
        {searchValue && (
          <button
            type="button"
            onClick={handleSearchClear}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-400 hover:text-surface-600 transition-colors duration-200"
            aria-label="Clear search"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </form>

      {/* Time Period Filter */}
      <select
        value={filters.period}
        onChange={(e) => onFilterChange({ period: e.target.value })}
        className="px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg
          bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100
          focus:ring-2 focus:ring-aura-500 focus:border-transparent"
        aria-label="Time period"
      >
        <option value="1h">Last 1 hour</option>
        <option value="6h">Last 6 hours</option>
        <option value="24h">Last 24 hours</option>
        <option value="7d">Last 7 days</option>
        <option value="30d">Last 30 days</option>
      </select>

      {/* Status Filter */}
      <select
        value={filters.status || ''}
        onChange={(e) => onFilterChange({ status: e.target.value || null })}
        className="px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg
          bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100
          focus:ring-2 focus:ring-aura-500 focus:border-transparent"
        aria-label="Status filter"
      >
        <option value="">All Statuses</option>
        <option value="success">Success</option>
        <option value="error">Error</option>
        <option value="timeout">Timeout</option>
      </select>

      {/* Agent Type Filter */}
      <select
        value={filters.agentType || ''}
        onChange={(e) => onFilterChange({ agentType: e.target.value || null })}
        className="px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg
          bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100
          focus:ring-2 focus:ring-aura-500 focus:border-transparent"
        aria-label="Agent type filter"
      >
        <option value="">All Agents</option>
        {Object.entries(AgentType).map(([key, value]) => (
          <option key={value} value={value}>
            {AGENT_TYPE_INFO[value]?.label || key}
          </option>
        ))}
      </select>

    </div>
  );
};

// ============================================================================
// TraceList Component
// ============================================================================

const TraceList = ({ traces, selectedTraceId, onSelectTrace, isLoading }) => {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <RefreshCw className="w-6 h-6 animate-spin text-brand-500" />
        <span className="ml-2 text-surface-500">Loading traces...</span>
      </div>
    );
  }

  if (!traces || traces.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-surface-500">
        <Activity className="w-12 h-12 mb-3 opacity-50" />
        <p>No traces found</p>
        <p className="text-sm">Try adjusting your filters</p>
      </div>
    );
  }

  return (
    <div className="space-y-2" role="listbox" aria-label="Trace list">
      {traces.map((trace) => {
        const isSelected = trace.trace_id === selectedTraceId;
        const statusColors = STATUS_COLORS[trace.status] || STATUS_COLORS.success;

        // Status-based selection colors - solid backgrounds with colored borders only
        const getSelectionStyles = () => {
          if (!isSelected) {
            return 'border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 hover:bg-surface-50 dark:hover:bg-surface-700 hover:border-surface-300 dark:hover:border-surface-600';
          }
          // Selected: apply status-colored border with solid background (no tinting)
          switch (trace.status) {
            case 'error':
              return 'border-critical-500 bg-white dark:bg-surface-800 shadow-md';
            case 'timeout':
              return 'border-warning-500 bg-white dark:bg-surface-800 shadow-md';
            case 'success':
            default:
              return 'border-olive-500 bg-white dark:bg-surface-800 shadow-md';
          }
        };

        return (
          <button
            key={trace.trace_id}
            onClick={() => onSelectTrace(trace.trace_id)}
            className={`
              w-full text-left p-3 rounded-xl border-2 transition-all duration-200 ease-[var(--ease-tahoe)]
              ${getSelectionStyles()}
            `}
            role="option"
            aria-selected={isSelected}
          >
            <div className="flex items-start gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium text-surface-900 dark:text-surface-100 truncate">
                    {trace.name}
                  </span>
                  <span className={`
                    px-1.5 py-0.5 text-xs rounded-full
                    ${statusColors.bg} ${statusColors.text}
                  `}>
                    {trace.status}
                  </span>
                </div>
                <div className="flex items-center gap-4 text-sm text-surface-500">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {formatDuration(trace.duration_ms)}
                  </span>
                  <span className="flex items-center gap-1">
                    <Layers className="w-3 h-3" />
                    {trace.span_count} spans
                  </span>
                  {trace.error_count > 0 && (
                    <span className="flex items-center gap-1 text-critical-500">
                      <AlertTriangle className="w-3 h-3" />
                      {trace.error_count} errors
                    </span>
                  )}
                </div>
                <div className="text-xs text-surface-400 mt-1">
                  {formatRelativeTime(trace.start_time)}
                </div>
              </div>
              <ChevronRight className="w-4 h-4 text-surface-400 flex-shrink-0 mt-1" />
            </div>
          </button>
        );
      })}
    </div>
  );
};

// ============================================================================
// TraceTimeline Component (Gantt View)
// ============================================================================

const TraceTimeline = ({ trace, selectedSpanId, onSelectSpan }) => {
  const [expandedSpans, setExpandedSpans] = useState(new Set());

  // Build span tree and flatten with depth info
  const spanTree = useMemo(() => {
    if (!trace?.spans) return [];
    return buildSpanTree(trace.spans);
  }, [trace?.spans]);

  const _flatSpans = useMemo(() => {
    return flattenSpanTree(spanTree);
  }, [spanTree]);

  const scale = useMemo(() => {
    return calculateTimelineScale(trace?.spans || []);
  }, [trace?.spans]);

  // Toggle span expansion
  const toggleExpand = useCallback((spanId) => {
    setExpandedSpans((prev) => {
      const next = new Set(prev);
      if (next.has(spanId)) {
        next.delete(spanId);
      } else {
        next.add(spanId);
      }
      return next;
    });
  }, []);

  // Initialize expanded state for spans with children
  useEffect(() => {
    if (spanTree.length > 0) {
      const hasChildren = new Set();
      const findWithChildren = (nodes) => {
        nodes.forEach((node) => {
          if (node.children && node.children.length > 0) {
            hasChildren.add(node.span_id);
            findWithChildren(node.children);
          }
        });
      };
      findWithChildren(spanTree);
      setExpandedSpans(hasChildren);
    }
  }, [spanTree]);

  // Filter visible spans based on expansion state
  const visibleSpans = useMemo(() => {
    const visible = [];
    const addVisible = (nodes, parentExpanded = true) => {
      nodes.forEach((node) => {
        if (parentExpanded) {
          visible.push(node);
        }
        if (node.children && node.children.length > 0) {
          addVisible(node.children, parentExpanded && expandedSpans.has(node.span_id));
        }
      });
    };
    addVisible(spanTree);
    return visible;
  }, [spanTree, expandedSpans]);

  if (!trace) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[300px] text-center">
        <div className="w-16 h-16 rounded-2xl bg-surface-100 dark:bg-surface-700/50 flex items-center justify-center mb-4">
          <Activity className="w-8 h-8 text-surface-400 dark:text-surface-500" />
        </div>
        <h3 className="text-lg font-medium text-surface-600 dark:text-surface-400 mb-1">
          Select a Trace
        </h3>
        <p className="text-sm text-surface-500 dark:text-surface-500">
          Choose a trace to view its timeline and spans
        </p>
      </div>
    );
  }

  return (
    <div className="relative" role="tree" aria-label="Span timeline">
      {/* Timeline Header */}
      <div className="flex items-center border-b border-surface-100/50 dark:border-surface-700/30 pb-2 mb-2">
        <div className="w-48 flex-shrink-0 text-sm font-medium text-surface-600 dark:text-surface-400">
          Operation
        </div>
        <div className="flex-1 text-sm font-medium text-surface-600 dark:text-surface-400">
          Timeline ({formatDuration(scale.totalMs)})
        </div>
      </div>

      {/* Timeline Rows */}
      <div className="space-y-1">
        {visibleSpans.map((span) => {
          const position = calculateSpanPosition(span, scale);
          const hasChildren = span.children && span.children.length > 0;
          const isExpanded = expandedSpans.has(span.span_id);
          const isSelected = span.span_id === selectedSpanId;
          const spanColor = SPAN_COLORS[span.kind] || SPAN_COLORS.internal;

          return (
            <div
              key={span.span_id}
              className={`
                flex items-center h-8 rounded-lg cursor-pointer transition-all duration-200 ease-[var(--ease-tahoe)]
                ${isSelected
                  ? 'bg-aura-50/80 dark:bg-aura-900/20 backdrop-blur-sm'
                  : 'hover:bg-surface-50 dark:hover:bg-surface-700'
                }
              `}
              onClick={() => onSelectSpan(span.span_id)}
              role="treeitem"
              aria-expanded={hasChildren ? isExpanded : undefined}
              aria-selected={isSelected}
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  onSelectSpan(span.span_id);
                } else if (e.key === 'ArrowRight' && hasChildren && !isExpanded) {
                  toggleExpand(span.span_id);
                } else if (e.key === 'ArrowLeft' && hasChildren && isExpanded) {
                  toggleExpand(span.span_id);
                }
              }}
            >
              {/* Span Name with Indentation */}
              <div
                className="w-48 flex-shrink-0 flex items-center text-sm truncate"
                style={{ paddingLeft: `${span.depth * 16}px` }}
              >
                {hasChildren ? (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleExpand(span.span_id);
                    }}
                    className="p-0.5 mr-1 hover:bg-surface-50 dark:hover:bg-surface-700 rounded-lg transition-colors duration-200"
                    aria-label={isExpanded ? 'Collapse' : 'Expand'}
                  >
                    {isExpanded ? (
                      <ChevronDown className="w-3 h-3" />
                    ) : (
                      <ChevronRight className="w-3 h-3" />
                    )}
                  </button>
                ) : (
                  <span className="w-4 mr-1" />
                )}
                <span
                  className="w-2 h-2 rounded-full mr-2 flex-shrink-0"
                  style={{ backgroundColor: spanColor }}
                  aria-hidden="true"
                />
                <span className="truncate text-surface-900 dark:text-surface-100">
                  {span.name}
                </span>
              </div>

              {/* Timeline Bar */}
              <div className="flex-1 relative h-6">
                <div
                  className="absolute h-5 rounded transition-all"
                  style={{
                    left: `${position.left}%`,
                    width: `${Math.max(position.width, 0.5)}%`,
                    backgroundColor: spanColor,
                    opacity: span.status === TraceStatus.ERROR ? 1 : 0.8,
                    top: '2px',
                  }}
                  title={`${span.name}: ${formatDuration(span.duration_ms)}`}
                >
                  {/* Error indicator */}
                  {span.status === TraceStatus.ERROR && (
                    <div
                      className="absolute inset-0 rounded"
                      style={{
                        backgroundImage: 'repeating-linear-gradient(45deg, transparent, transparent 2px, rgba(255,255,255,0.2) 2px, rgba(255,255,255,0.2) 4px)',
                      }}
                    />
                  )}
                </div>
              </div>

              {/* Duration */}
              <div className="w-20 flex-shrink-0 text-right text-xs text-surface-500 pr-2">
                {formatDuration(span.duration_ms)}
              </div>
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 mt-4 pt-4 border-t border-surface-100/50 dark:border-surface-700/30">
        <span className="text-xs text-surface-500">Legend:</span>
        {Object.entries(SPAN_COLORS).map(([kind, color]) => (
          <div key={kind} className="flex items-center gap-1">
            <span
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: color }}
            />
            <span className="text-xs capitalize text-surface-600 dark:text-surface-400">
              {kind}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

// ============================================================================
// SpanDetailPanel Component
// ============================================================================

const SpanDetailPanel = ({ trace, selectedSpanId, onClose }) => {
  const [activeTab, setActiveTab] = useState('attributes');

  const selectedSpan = useMemo(() => {
    if (!trace?.spans || !selectedSpanId) return null;
    return trace.spans.find((s) => s.span_id === selectedSpanId);
  }, [trace?.spans, selectedSpanId]);

  if (!selectedSpan) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[300px] text-center p-6">
        <div className="w-16 h-16 rounded-2xl bg-surface-100 dark:bg-surface-700/50 flex items-center justify-center mb-4">
          <Layers className="w-8 h-8 text-surface-400 dark:text-surface-500" />
        </div>
        <h3 className="text-lg font-medium text-surface-600 dark:text-surface-400 mb-1">
          Select a Span
        </h3>
        <p className="text-sm text-surface-500 dark:text-surface-500">
          Choose a span to view its attributes and events
        </p>
      </div>
    );
  }

  const tabs = [
    { id: 'attributes', label: 'Attributes' },
    { id: 'events', label: `Events (${selectedSpan.events?.length || 0})` },
    { id: 'links', label: `Links (${selectedSpan.links?.length || 0})` },
  ];

  const statusColors = STATUS_COLORS[selectedSpan.status] || STATUS_COLORS.success;
  const spanColor = SPAN_COLORS[selectedSpan.kind] || SPAN_COLORS.internal;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-start justify-between p-4 border-b border-surface-100/50 dark:border-surface-700/30">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: spanColor }}
            />
            <h3 className="font-semibold text-surface-900 dark:text-surface-100 truncate">
              {selectedSpan.name}
            </h3>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className={`px-1.5 py-0.5 rounded-full ${statusColors.bg} ${statusColors.text}`}>
              {selectedSpan.status}
            </span>
            <span className="text-surface-500">
              {formatDuration(selectedSpan.duration_ms)}
            </span>
            <span className="text-surface-400 capitalize">
              {selectedSpan.kind}
            </span>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 hover:bg-surface-50 dark:hover:bg-surface-700 rounded-lg transition-all duration-200 ease-[var(--ease-tahoe)]"
          aria-label="Close panel"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-surface-100/50 dark:border-surface-700/30">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`
              px-4 py-2 text-sm font-medium transition-all duration-200 ease-[var(--ease-tahoe)]
              ${activeTab === tab.id
                ? 'text-brand-600 dark:text-brand-400 border-b-2 border-brand-500'
                : 'text-surface-500 hover:text-surface-700 dark:hover:text-surface-300'
              }
            `}
            role="tab"
            aria-selected={activeTab === tab.id}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-auto p-4" role="tabpanel">
        {activeTab === 'attributes' && (
          <div className="space-y-2">
            {/* Standard Fields */}
            <div className="grid grid-cols-2 gap-2 mb-4">
              <div className="text-sm">
                <span className="text-surface-500 block">Span ID</span>
                <code className="text-surface-900 dark:text-surface-100 text-xs font-mono">
                  {selectedSpan.span_id}
                </code>
              </div>
              {selectedSpan.parent_span_id && (
                <div className="text-sm">
                  <span className="text-surface-500 block">Parent Span</span>
                  <code className="text-surface-900 dark:text-surface-100 text-xs font-mono">
                    {selectedSpan.parent_span_id}
                  </code>
                </div>
              )}
              <div className="text-sm">
                <span className="text-surface-500 block">Start Time</span>
                <span className="text-surface-900 dark:text-surface-100 text-xs">
                  {formatTimestamp(selectedSpan.start_time)}
                </span>
              </div>
              <div className="text-sm">
                <span className="text-surface-500 block">End Time</span>
                <span className="text-surface-900 dark:text-surface-100 text-xs">
                  {formatTimestamp(selectedSpan.end_time)}
                </span>
              </div>
            </div>

            {/* Custom Attributes */}
            {Object.keys(selectedSpan.attributes || {}).length > 0 && (
              <>
                <h4 className="text-sm font-medium text-surface-700 dark:text-surface-300 mt-4 mb-2">
                  Custom Attributes
                </h4>
                <div className="space-y-1">
                  {Object.entries(selectedSpan.attributes).map(([key, value]) => (
                    <div
                      key={key}
                      className="flex items-start gap-2 text-sm py-1 px-2 rounded-lg bg-white dark:bg-surface-800"
                    >
                      <span className="text-surface-500 font-mono text-xs min-w-[120px]">
                        {key}
                      </span>
                      <span className="text-surface-900 dark:text-surface-100 text-xs break-all">
                        {value}
                      </span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {activeTab === 'events' && (
          <div className="space-y-3">
            {selectedSpan.events?.length > 0 ? (
              selectedSpan.events.map((event, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-xl bg-white dark:bg-surface-800 border border-surface-200/50 dark:border-surface-700/30"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <Zap className="w-4 h-4 text-warning-500" />
                    <span className="font-medium text-sm text-surface-900 dark:text-surface-100">
                      {event.name}
                    </span>
                    <span className="text-xs text-surface-500">
                      {formatTimestamp(event.timestamp)}
                    </span>
                  </div>
                  {Object.keys(event.attributes || {}).length > 0 && (
                    <div className="space-y-1 mt-2">
                      {Object.entries(event.attributes).map(([key, value]) => (
                        <div key={key} className="text-xs">
                          <span className="text-surface-500">{key}: </span>
                          <span className="text-surface-700 dark:text-surface-300">{value}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))
            ) : (
              <div className="text-center text-surface-500 py-8">
                No events recorded
              </div>
            )}
          </div>
        )}

        {activeTab === 'links' && (
          <div className="space-y-3">
            {selectedSpan.links?.length > 0 ? (
              selectedSpan.links.map((link, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-xl bg-white dark:bg-surface-800 border border-surface-200/50 dark:border-surface-700/30"
                >
                  <div className="text-sm">
                    <span className="text-surface-500">Trace: </span>
                    <code className="text-surface-900 dark:text-surface-100 font-mono text-xs">
                      {link.trace_id}
                    </code>
                  </div>
                  <div className="text-sm mt-1">
                    <span className="text-surface-500">Span: </span>
                    <code className="text-surface-900 dark:text-surface-100 font-mono text-xs">
                      {link.span_id}
                    </code>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-center text-surface-500 py-8">
                No linked spans
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

// ============================================================================
// Main TraceExplorer Component
// ============================================================================

const TraceExplorer = () => {
  // State
  const [metrics, setMetrics] = useState(null);
  const [traces, setTraces] = useState([]);
  const [selectedTrace, setSelectedTrace] = useState(null);
  const [selectedSpanId, setSelectedSpanId] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingTrace, setIsLoadingTrace] = useState(false);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState(null);

  // Toast notifications
  const { toast } = useToast();
  const [filters, setFilters] = useState({
    period: '24h',
    status: null,
    agentType: null,
    search: '',
  });
  const [pagination, setPagination] = useState({
    page: 1,
    pageSize: 20,
    total: 0,
    hasMore: false,
  });

  // Fetch metrics
  const fetchMetrics = useCallback(async () => {
    try {
      const data = await getTraceMetrics(filters.period);
      setMetrics(data);
    } catch (err) {
      console.error('Failed to fetch metrics:', err);
    }
  }, [filters.period]);

  // Fetch traces
  const fetchTraces = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listTraces({
        page: pagination.page,
        pageSize: pagination.pageSize,
        status: filters.status,
        agentType: filters.agentType,
        period: filters.period,
        search: filters.search,
      });
      setTraces(data.traces);
      setPagination((prev) => ({
        ...prev,
        total: data.total,
        hasMore: data.has_more,
      }));
    } catch (err) {
      console.error('Failed to fetch traces:', err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, [filters, pagination.page, pagination.pageSize]);

  // Fetch single trace details
  const fetchTraceDetails = useCallback(async (traceId) => {
    setIsLoadingTrace(true);
    try {
      const data = await getTrace(traceId);
      setSelectedTrace(data);
      setSelectedSpanId(data.spans?.[0]?.span_id || null);
    } catch (err) {
      console.error('Failed to fetch trace:', err);
    } finally {
      setIsLoadingTrace(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchMetrics();
    fetchTraces();
  }, [fetchMetrics, fetchTraces]);

  // Handle filter changes
  const handleFilterChange = useCallback((updates) => {
    setFilters((prev) => ({ ...prev, ...updates }));
    setPagination((prev) => ({ ...prev, page: 1 }));
  }, []);

  // Handle search
  const handleSearch = useCallback((search) => {
    setFilters((prev) => ({ ...prev, search }));
    setPagination((prev) => ({ ...prev, page: 1 }));
  }, []);

  // Handle refresh
  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      await Promise.all([fetchMetrics(), fetchTraces()]);
      toast.success('Trace Explorer refreshed');
    } catch (err) {
      toast.error('Failed to refresh traces');
    } finally {
      setIsRefreshing(false);
    }
  }, [fetchMetrics, fetchTraces, toast]);

  // Handle trace selection (toggle behavior - click again to unselect)
  const handleSelectTrace = useCallback((traceId) => {
    if (selectedTrace?.trace_id === traceId) {
      setSelectedTrace(null);
      setSelectedSpanId(null);
    } else {
      fetchTraceDetails(traceId);
    }
  }, [fetchTraceDetails, selectedTrace?.trace_id]);

  // Handle span selection
  const handleSelectSpan = useCallback((spanId) => {
    setSelectedSpanId(spanId);
  }, []);

  // Close detail panel
  const handleCloseDetail = useCallback(() => {
    setSelectedSpanId(null);
  }, []);

  // Track initial load completion with minimum visible duration
  useEffect(() => {
    if (!isLoading && isInitialLoad) {
      const timer = setTimeout(() => setIsInitialLoad(false), 300);
      return () => clearTimeout(timer);
    }
  }, [isLoading, isInitialLoad]);

  // Show page skeleton on initial load
  if (isInitialLoad && isLoading) {
    return <PageSkeleton />;
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <header className="flex-shrink-0 px-6 py-4 bg-white dark:bg-surface-800 backdrop-blur-xl border-b border-surface-100/50 dark:border-surface-700/30">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-surface-900 dark:text-surface-100">
              Trace Explorer
            </h1>
            <p className="text-sm text-surface-500 mt-1">
              OpenTelemetry distributed tracing visualization
            </p>
          </div>
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-2 px-3 py-2 text-sm text-surface-600 dark:text-surface-400
              hover:text-surface-900 dark:hover:text-surface-100 hover:bg-surface-50 dark:hover:bg-surface-700
              rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 ease-[var(--ease-tahoe)]"
            aria-label="Refresh traces"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-hidden p-6">
        {/* Metrics Cards */}
        <TraceMetricCards metrics={metrics} isLoading={isLoading && !metrics} />

        {/* Filter Bar */}
        <TraceFilterBar
          filters={filters}
          onFilterChange={handleFilterChange}
          onSearch={handleSearch}
        />

        {/* Error Display */}
        {error && (
          <div className="mb-4 p-3 rounded-xl bg-critical-50/80 dark:bg-critical-900/20 backdrop-blur-sm text-critical-600 dark:text-critical-400 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            <span>{error}</span>
          </div>
        )}

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 h-[calc(100%-200px)]">
          {/* Trace List */}
          <div className="lg:col-span-3 overflow-auto p-3">
            <TraceList
              traces={traces}
              selectedTraceId={selectedTrace?.trace_id}
              onSelectTrace={handleSelectTrace}
              isLoading={isLoading}
            />

            {/* Pagination */}
            {pagination.total > 0 && (
              <div className="flex items-center justify-between mt-4 pt-3 border-t border-surface-100/50 dark:border-surface-700/30">
                <span className="text-xs text-surface-500">
                  {pagination.total} traces
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPagination((p) => ({ ...p, page: p.page - 1 }))}
                    disabled={pagination.page <= 1}
                    className="px-2 py-1 text-xs rounded-lg border border-surface-200/50 dark:border-surface-700/30 hover:bg-surface-50 dark:hover:bg-surface-700 disabled:opacity-50 transition-all duration-200 ease-[var(--ease-tahoe)]"
                  >
                    Prev
                  </button>
                  <span className="text-xs text-surface-500 px-2 py-1">
                    {pagination.page}
                  </span>
                  <button
                    onClick={() => setPagination((p) => ({ ...p, page: p.page + 1 }))}
                    disabled={!pagination.hasMore}
                    className="px-2 py-1 text-xs rounded-lg border border-surface-200/50 dark:border-surface-700/30 hover:bg-surface-50 dark:hover:bg-surface-700 disabled:opacity-50 transition-all duration-200 ease-[var(--ease-tahoe)]"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Timeline View */}
          <div className={`lg:col-span-5 overflow-auto rounded-xl border border-surface-200/50 dark:border-surface-700/30 transition-all duration-200 ${
            selectedTrace
              ? 'bg-white dark:bg-surface-800 backdrop-blur-xl shadow-[var(--shadow-glass)] p-4'
              : 'bg-transparent'
          }`}>
            {isLoadingTrace ? (
              <div className="flex items-center justify-center h-full">
                <RefreshCw className="w-6 h-6 animate-spin text-brand-500" />
              </div>
            ) : (
              <TraceTimeline
                trace={selectedTrace}
                selectedSpanId={selectedSpanId}
                onSelectSpan={handleSelectSpan}
              />
            )}
          </div>

          {/* Span Details */}
          <div className={`lg:col-span-4 overflow-hidden rounded-xl border border-surface-200/50 dark:border-surface-700/30 transition-all duration-200 ${
            selectedSpanId
              ? 'bg-white dark:bg-surface-800 backdrop-blur-xl shadow-[var(--shadow-glass)]'
              : 'bg-transparent'
          }`}>
            <SpanDetailPanel
              trace={selectedTrace}
              selectedSpanId={selectedSpanId}
              onClose={handleCloseDetail}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default TraceExplorer;
