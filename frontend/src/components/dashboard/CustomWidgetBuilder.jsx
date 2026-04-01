/**
 * Custom Widget Builder Component
 *
 * Enables power users to create custom widgets with user-defined queries.
 * Implements ADR-064 Phase 3 custom widget builder functionality.
 */

import { useState, useCallback, useEffect, memo } from 'react';
import {
  XMarkIcon,
  BeakerIcon,
  PlayIcon,
  CheckIcon,
  ExclamationCircleIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  CodeBracketIcon,
  ChartBarIcon,
  TableCellsIcon,
  CalculatorIcon,
} from '@heroicons/react/24/outline';

// Query types with icons
const QUERY_TYPES = [
  { value: 'metric', label: 'Single Metric', icon: CalculatorIcon, description: 'A single value with optional trend' },
  { value: 'time_series', label: 'Time Series', icon: ChartBarIcon, description: 'Time-based data for charts' },
  { value: 'table', label: 'Table', icon: TableCellsIcon, description: 'Tabular data display' },
  { value: 'aggregation', label: 'Aggregation', icon: CodeBracketIcon, description: 'Grouped or aggregated data' },
];

// Widget types
const WIDGET_TYPES = [
  { value: 'metric', label: 'Metric Card' },
  { value: 'chart_line', label: 'Line Chart' },
  { value: 'chart_bar', label: 'Bar Chart' },
  { value: 'chart_donut', label: 'Donut Chart' },
  { value: 'table', label: 'Data Table' },
  { value: 'gauge', label: 'Gauge' },
  { value: 'progress', label: 'Progress Bar' },
];

// Categories
const CATEGORIES = [
  { value: 'security', label: 'Security' },
  { value: 'operations', label: 'Operations' },
  { value: 'analytics', label: 'Analytics' },
  { value: 'compliance', label: 'Compliance' },
  { value: 'cost', label: 'Cost' },
];

// Time ranges
const TIME_RANGES = [
  { value: '1h', label: 'Last Hour' },
  { value: '6h', label: 'Last 6 Hours' },
  { value: '24h', label: 'Last 24 Hours' },
  { value: '7d', label: 'Last 7 Days' },
  { value: '30d', label: 'Last 30 Days' },
];

// Aggregation functions
const AGGREGATIONS = [
  { value: '', label: 'None' },
  { value: 'count', label: 'Count' },
  { value: 'sum', label: 'Sum' },
  { value: 'avg', label: 'Average' },
  { value: 'min', label: 'Minimum' },
  { value: 'max', label: 'Maximum' },
];

// Query type selector component
const QueryTypeSelector = memo(function QueryTypeSelector({ value, onChange }) {
  return (
    <div className="grid grid-cols-2 gap-3">
      {QUERY_TYPES.map((type) => {
        const Icon = type.icon;
        const isSelected = value === type.value;
        return (
          <button
            key={type.value}
            onClick={() => onChange(type.value)}
            className={`
              flex flex-col items-start p-3 rounded-lg border transition-all text-left
              ${isSelected
                ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/20'
                : 'border-surface-200 dark:border-surface-700 hover:border-surface-300 dark:hover:border-surface-600'
              }
            `}
          >
            <div className="flex items-center gap-2 mb-1">
              <Icon className={`w-4 h-4 ${isSelected ? 'text-aura-500' : 'text-surface-500'}`} />
              <span className={`text-sm font-medium ${isSelected ? 'text-aura-600 dark:text-aura-400' : 'text-surface-700 dark:text-surface-300'}`}>
                {type.label}
              </span>
            </div>
            <span className="text-xs text-surface-500 dark:text-surface-400">
              {type.description}
            </span>
          </button>
        );
      })}
    </div>
  );
});

// Filter row component
const FilterRow = memo(function FilterRow({ filter, index, onUpdate, onRemove }) {
  return (
    <div className="flex items-center gap-2">
      <input
        type="text"
        placeholder="Field"
        value={filter.field || ''}
        onChange={(e) => onUpdate(index, { ...filter, field: e.target.value })}
        className="flex-1 px-3 py-1.5 text-sm rounded border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100"
      />
      <select
        value={filter.operator || 'eq'}
        onChange={(e) => onUpdate(index, { ...filter, operator: e.target.value })}
        className="px-2 py-1.5 text-sm rounded border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 text-surface-700 dark:text-surface-300"
      >
        <option value="eq">=</option>
        <option value="ne">!=</option>
        <option value="gt">&gt;</option>
        <option value="gte">&gt;=</option>
        <option value="lt">&lt;</option>
        <option value="lte">&lt;=</option>
        <option value="contains">contains</option>
      </select>
      <input
        type="text"
        placeholder="Value"
        value={filter.value || ''}
        onChange={(e) => onUpdate(index, { ...filter, value: e.target.value })}
        className="flex-1 px-3 py-1.5 text-sm rounded border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100"
      />
      <button
        onClick={() => onRemove(index)}
        className="p-1.5 text-surface-400 hover:text-critical-500 rounded"
      >
        <XMarkIcon className="w-4 h-4" />
      </button>
    </div>
  );
});

// Preview panel component
const PreviewPanel = memo(function PreviewPanel({ data, isLoading, error, executionTime }) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-48 bg-surface-50 dark:bg-surface-800 rounded-lg">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-aura-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-48 bg-critical-50 dark:bg-critical-900/20 rounded-lg p-4">
        <ExclamationCircleIcon className="w-8 h-8 text-critical-500 mb-2" />
        <p className="text-sm text-critical-600 dark:text-critical-400 text-center">{error}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex flex-col items-center justify-center h-48 bg-surface-50 dark:bg-surface-800 rounded-lg p-4">
        <BeakerIcon className="w-8 h-8 text-surface-400 mb-2" />
        <p className="text-sm text-surface-500 dark:text-surface-400">
          Click &quot;Preview Query&quot; to test your query
        </p>
      </div>
    );
  }

  return (
    <div className="bg-surface-50 dark:bg-surface-800 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-surface-500 dark:text-surface-400">
          Preview Result
        </span>
        <span className="text-xs text-surface-400">
          {executionTime}ms
        </span>
      </div>
      <pre className="text-xs text-surface-700 dark:text-surface-300 overflow-auto max-h-40 bg-white dark:bg-surface-900 rounded p-3">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
});

// Collapsible section component
const CollapsibleSection = memo(function CollapsibleSection({ title, children, defaultOpen = true }) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border border-surface-200 dark:border-surface-700 rounded-lg overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 bg-surface-50 dark:bg-surface-800 text-left"
      >
        <span className="text-sm font-medium text-surface-700 dark:text-surface-300">
          {title}
        </span>
        {isOpen ? (
          <ChevronDownIcon className="w-4 h-4 text-surface-500" />
        ) : (
          <ChevronRightIcon className="w-4 h-4 text-surface-500" />
        )}
      </button>
      {isOpen && (
        <div className="p-4 space-y-4">
          {children}
        </div>
      )}
    </div>
  );
});

// Main Custom Widget Builder component
export default function CustomWidgetBuilder({
  isOpen,
  onClose,
  onSave,
  editWidget = null,
  dataSources = [],
}) {
  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [widgetType, setWidgetType] = useState('metric');
  const [category, setCategory] = useState('analytics');
  const [refreshSeconds, setRefreshSeconds] = useState(60);

  // Query state
  const [queryType, setQueryType] = useState('metric');
  const [dataSource, setDataSource] = useState('');
  const [endpoint, setEndpoint] = useState('');
  const [timeRange, setTimeRange] = useState('24h');
  const [aggregation, setAggregation] = useState('');
  const [groupBy, setGroupBy] = useState('');
  const [filters, setFilters] = useState([]);
  const [limit, setLimit] = useState(100);

  // Preview state
  const [previewData, setPreviewData] = useState(null);
  const [previewError, setPreviewError] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [executionTime, setExecutionTime] = useState(0);

  // Submission state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  // Initialize form when editing
  useEffect(() => {
    if (editWidget) {
      setName(editWidget.name);
      setDescription(editWidget.description || '');
      setWidgetType(editWidget.widget_type);
      setCategory(editWidget.category);
      setRefreshSeconds(editWidget.refresh_seconds);

      const query = editWidget.query;
      if (query) {
        setQueryType(query.query_type);
        setDataSource(query.data_source);
        setEndpoint(query.endpoint);
        setTimeRange(query.time_range || '24h');
        setAggregation(query.aggregation || '');
        setGroupBy(query.group_by?.join(', ') || '');
        setFilters(query.filters || []);
        setLimit(query.limit || 100);
      }
    }
  }, [editWidget]);

  // Get endpoints for selected data source
  const availableEndpoints = dataSources.find(ds => ds.type === dataSource)?.endpoints || [];

  // Add filter
  const handleAddFilter = useCallback(() => {
    setFilters(prev => [...prev, { field: '', operator: 'eq', value: '' }]);
  }, []);

  // Update filter
  const handleUpdateFilter = useCallback((index, filter) => {
    setFilters(prev => {
      const updated = [...prev];
      updated[index] = filter;
      return updated;
    });
  }, []);

  // Remove filter
  const handleRemoveFilter = useCallback((index) => {
    setFilters(prev => prev.filter((_, i) => i !== index));
  }, []);

  // Preview query
  const handlePreview = useCallback(async () => {
    if (!dataSource || !endpoint) {
      setPreviewError('Please select a data source and endpoint');
      return;
    }

    setPreviewLoading(true);
    setPreviewError(null);
    setPreviewData(null);

    try {
      const response = await fetch('/api/v1/widgets/custom/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query_type: queryType,
          data_source: dataSource,
          endpoint,
          time_range: timeRange,
          aggregation: aggregation || null,
          group_by: groupBy ? groupBy.split(',').map(g => g.trim()) : [],
          filters: filters.filter(f => f.field && f.value),
          limit: Math.min(limit, 10),
        }),
      });

      const result = await response.json();

      if (result.success) {
        setPreviewData(result.data);
        setExecutionTime(result.execution_time_ms);
      } else {
        setPreviewError(result.error || 'Query failed');
      }
    } catch (err) {
      setPreviewError(err.message || 'Failed to preview query');
    } finally {
      setPreviewLoading(false);
    }
  }, [queryType, dataSource, endpoint, timeRange, aggregation, groupBy, filters, limit]);

  // Save widget
  const handleSave = useCallback(async () => {
    if (!name.trim()) {
      setSubmitError('Widget name is required');
      return;
    }
    if (!dataSource || !endpoint) {
      setSubmitError('Please select a data source and endpoint');
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      const widgetData = {
        name: name.trim(),
        description: description.trim(),
        widget_type: widgetType,
        category,
        refresh_seconds: refreshSeconds,
        query: {
          query_type: queryType,
          data_source: dataSource,
          endpoint,
          time_range: timeRange,
          aggregation: aggregation || null,
          group_by: groupBy ? groupBy.split(',').map(g => g.trim()) : [],
          filters: filters.filter(f => f.field && f.value),
          limit,
          parameters: {},
        },
        display_config: {},
      };

      await onSave(widgetData, editWidget?.widget_id);
      onClose();
    } catch (err) {
      setSubmitError(err.message || 'Failed to save widget');
    } finally {
      setIsSubmitting(false);
    }
  }, [name, description, widgetType, category, refreshSeconds, queryType, dataSource, endpoint, timeRange, aggregation, groupBy, filters, limit, onSave, onClose, editWidget]);

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-50 transition-opacity"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-10 overflow-y-auto">
        <div
          className="bg-white dark:bg-surface-900 rounded-xl shadow-xl max-w-3xl w-full"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-surface-200 dark:border-surface-700">
            <div className="flex items-center gap-3">
              <BeakerIcon className="w-6 h-6 text-aura-500" />
              <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
                {editWidget ? 'Edit Custom Widget' : 'Create Custom Widget'}
              </h2>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-800 text-surface-500 transition-colors"
            >
              <XMarkIcon className="w-5 h-5" />
            </button>
          </div>

          {/* Content */}
          <div className="p-6 space-y-6 max-h-[calc(100vh-200px)] overflow-y-auto">
            {/* Basic Info */}
            <CollapsibleSection title="Widget Details">
              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2">
                  <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                    Widget Name *
                  </label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="My Custom Widget"
                    className="w-full px-3 py-2 rounded-lg border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100"
                  />
                </div>

                <div className="col-span-2">
                  <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                    Description
                  </label>
                  <textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Describe what this widget shows..."
                    rows={2}
                    className="w-full px-3 py-2 rounded-lg border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                    Display Type
                  </label>
                  <select
                    value={widgetType}
                    onChange={(e) => setWidgetType(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 text-surface-700 dark:text-surface-300"
                  >
                    {WIDGET_TYPES.map((type) => (
                      <option key={type.value} value={type.value}>
                        {type.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                    Category
                  </label>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 text-surface-700 dark:text-surface-300"
                  >
                    {CATEGORIES.map((cat) => (
                      <option key={cat.value} value={cat.value}>
                        {cat.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                    Refresh Interval
                  </label>
                  <select
                    value={refreshSeconds}
                    onChange={(e) => setRefreshSeconds(Number(e.target.value))}
                    className="w-full px-3 py-2 rounded-lg border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 text-surface-700 dark:text-surface-300"
                  >
                    <option value={30}>30 seconds</option>
                    <option value={60}>1 minute</option>
                    <option value={300}>5 minutes</option>
                    <option value={600}>10 minutes</option>
                    <option value={1800}>30 minutes</option>
                    <option value={3600}>1 hour</option>
                  </select>
                </div>
              </div>
            </CollapsibleSection>

            {/* Query Builder */}
            <CollapsibleSection title="Query Configuration">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                    Query Type
                  </label>
                  <QueryTypeSelector value={queryType} onChange={setQueryType} />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      Data Source *
                    </label>
                    <select
                      value={dataSource}
                      onChange={(e) => {
                        setDataSource(e.target.value);
                        setEndpoint('');
                      }}
                      className="w-full px-3 py-2 rounded-lg border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 text-surface-700 dark:text-surface-300"
                    >
                      <option value="">Select a data source...</option>
                      {dataSources.map((ds) => (
                        <option key={ds.type} value={ds.type}>
                          {ds.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      Endpoint *
                    </label>
                    <select
                      value={endpoint}
                      onChange={(e) => setEndpoint(e.target.value)}
                      disabled={!dataSource}
                      className="w-full px-3 py-2 rounded-lg border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 text-surface-700 dark:text-surface-300 disabled:opacity-50"
                    >
                      <option value="">Select an endpoint...</option>
                      {availableEndpoints.map((ep) => (
                        <option key={ep} value={ep}>
                          {ep}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      Time Range
                    </label>
                    <select
                      value={timeRange}
                      onChange={(e) => setTimeRange(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 text-surface-700 dark:text-surface-300"
                    >
                      {TIME_RANGES.map((range) => (
                        <option key={range.value} value={range.value}>
                          {range.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      Result Limit
                    </label>
                    <input
                      type="number"
                      value={limit}
                      onChange={(e) => setLimit(Math.min(1000, Math.max(1, Number(e.target.value))))}
                      min={1}
                      max={1000}
                      className="w-full px-3 py-2 rounded-lg border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100"
                    />
                  </div>

                  {queryType === 'aggregation' && (
                    <>
                      <div>
                        <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                          Aggregation
                        </label>
                        <select
                          value={aggregation}
                          onChange={(e) => setAggregation(e.target.value)}
                          className="w-full px-3 py-2 rounded-lg border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 text-surface-700 dark:text-surface-300"
                        >
                          {AGGREGATIONS.map((agg) => (
                            <option key={agg.value} value={agg.value}>
                              {agg.label}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                          Group By (comma-separated)
                        </label>
                        <input
                          type="text"
                          value={groupBy}
                          onChange={(e) => setGroupBy(e.target.value)}
                          placeholder="field1, field2"
                          className="w-full px-3 py-2 rounded-lg border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100"
                        />
                      </div>
                    </>
                  )}
                </div>

                {/* Filters */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm font-medium text-surface-700 dark:text-surface-300">
                      Filters
                    </label>
                    <button
                      onClick={handleAddFilter}
                      className="text-xs text-aura-600 dark:text-aura-400 hover:underline"
                    >
                      + Add Filter
                    </button>
                  </div>
                  <div className="space-y-2">
                    {filters.map((filter, index) => (
                      <FilterRow
                        key={index}
                        filter={filter}
                        index={index}
                        onUpdate={handleUpdateFilter}
                        onRemove={handleRemoveFilter}
                      />
                    ))}
                    {filters.length === 0 && (
                      <p className="text-sm text-surface-500 dark:text-surface-400 italic">
                        No filters added
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </CollapsibleSection>

            {/* Preview */}
            <CollapsibleSection title="Query Preview" defaultOpen={false}>
              <div className="space-y-4">
                <button
                  onClick={handlePreview}
                  disabled={previewLoading || !dataSource || !endpoint}
                  className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-aura-600 hover:bg-aura-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
                >
                  {previewLoading ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                      Running...
                    </>
                  ) : (
                    <>
                      <PlayIcon className="w-4 h-4" />
                      Preview Query
                    </>
                  )}
                </button>

                <PreviewPanel
                  data={previewData}
                  isLoading={previewLoading}
                  error={previewError}
                  executionTime={executionTime}
                />
              </div>
            </CollapsibleSection>

            {/* Error message */}
            {submitError && (
              <div className="flex items-center gap-2 px-4 py-3 bg-critical-50 dark:bg-critical-900/20 rounded-lg">
                <ExclamationCircleIcon className="w-5 h-5 text-critical-500" />
                <p className="text-sm text-critical-600 dark:text-critical-400">{submitError}</p>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-surface-200 dark:border-surface-700">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={isSubmitting || !name.trim() || !dataSource || !endpoint}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-aura-600 hover:bg-aura-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
            >
              {isSubmitting ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                  Saving...
                </>
              ) : (
                <>
                  <CheckIcon className="w-4 h-4" />
                  {editWidget ? 'Update Widget' : 'Create Widget'}
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
