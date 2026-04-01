/**
 * Job Timeline View
 *
 * Calendar/Gantt visualization of scheduled and completed jobs.
 * ADR-055 Phase 2: Timeline and HITL Integration
 */

import { useState, useEffect, useMemo, useCallback } from 'react';
import {
  CalendarDaysIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  FunnelIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';
import {
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  PlayIcon,
} from '@heroicons/react/24/solid';
import { getTimeline, getStatusColor, formatDuration, rescheduleJob } from '../../services/schedulingApi';
import { useToast } from '../ui/Toast';

// View modes
const VIEW_MODES = [
  { id: 'day', label: 'Day', days: 1 },
  { id: 'week', label: 'Week', days: 7 },
  { id: 'month', label: 'Month', days: 30 },
];

// Job type colors
const JOB_TYPE_COLORS = {
  SECURITY_SCAN: 'bg-critical-500',
  CODE_REVIEW: 'bg-aura-500',
  PATCH_GENERATION: 'bg-warning-500',
  VULNERABILITY_ASSESSMENT: 'bg-critical-600',
  DEPENDENCY_UPDATE: 'bg-olive-500',
  REPOSITORY_INDEXING: 'bg-info-500',
  COMPLIANCE_CHECK: 'bg-purple-500',
  THREAT_ANALYSIS: 'bg-critical-400',
  CODE_QUALITY_SCAN: 'bg-aura-400',
  PERFORMANCE_ANALYSIS: 'bg-amber-500',
};

// Status icons
const STATUS_ICONS = {
  PENDING: ClockIcon,
  DISPATCHED: PlayIcon,
  RUNNING: PlayIcon,
  SUCCEEDED: CheckCircleIcon,
  FAILED: XCircleIcon,
  CANCELLED: XCircleIcon,
};

export default function JobTimelineView({ onRefresh }) {
  const [viewMode, setViewMode] = useState('week');
  const [currentDate, setCurrentDate] = useState(new Date());
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({
    includeScheduled: true,
    includeCompleted: true,
    jobTypes: [],
  });
  const [showFilters, setShowFilters] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState(null);

  // Drag and drop state
  const [draggedEntry, setDraggedEntry] = useState(null);
  const [dropTargetDate, setDropTargetDate] = useState(null);
  const [isRescheduling, setIsRescheduling] = useState(false);
  const { toast } = useToast();

  // Calculate date range based on view mode
  const dateRange = useMemo(() => {
    const mode = VIEW_MODES.find((m) => m.id === viewMode);
    const days = mode?.days || 7;

    const start = new Date(currentDate);
    start.setHours(0, 0, 0, 0);

    if (viewMode === 'week') {
      // Start from Sunday
      start.setDate(start.getDate() - start.getDay());
    } else if (viewMode === 'month') {
      // Start from first of month
      start.setDate(1);
    }

    const end = new Date(start);
    end.setDate(end.getDate() + days);
    end.setHours(23, 59, 59, 999);

    return { start, end, days };
  }, [currentDate, viewMode]);

  // Generate time slots for the view
  const timeSlots = useMemo(() => {
    const slots = [];
    const { start, days } = dateRange;

    for (let i = 0; i < days; i++) {
      const date = new Date(start);
      date.setDate(date.getDate() + i);
      slots.push({
        date,
        label: date.toLocaleDateString('en-US', {
          weekday: viewMode === 'day' ? 'long' : 'short',
          month: viewMode === 'month' ? 'numeric' : 'short',
          day: 'numeric',
        }),
        isToday: isSameDay(date, new Date()),
      });
    }

    return slots;
  }, [dateRange, viewMode]);

  // Load timeline data
  useEffect(() => {
    loadTimeline();
  }, [dateRange, filters]);

  const loadTimeline = async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await getTimeline({
        startDate: dateRange.start.toISOString(),
        endDate: dateRange.end.toISOString(),
        includeScheduled: filters.includeScheduled,
        includeCompleted: filters.includeCompleted,
        limit: 200,
      });

      let filteredEntries = data.entries || [];

      // Apply job type filter
      if (filters.jobTypes.length > 0) {
        filteredEntries = filteredEntries.filter((e) =>
          filters.jobTypes.includes(e.job_type)
        );
      }

      setEntries(filteredEntries);
    } catch (err) {
      console.error('Failed to load timeline:', err);
      setError(err.message || 'Failed to load timeline');
    } finally {
      setLoading(false);
    }
  };

  // Navigation handlers
  const navigatePrev = () => {
    const newDate = new Date(currentDate);
    const mode = VIEW_MODES.find((m) => m.id === viewMode);
    newDate.setDate(newDate.getDate() - (mode?.days || 7));
    setCurrentDate(newDate);
  };

  const navigateNext = () => {
    const newDate = new Date(currentDate);
    const mode = VIEW_MODES.find((m) => m.id === viewMode);
    newDate.setDate(newDate.getDate() + (mode?.days || 7));
    setCurrentDate(newDate);
  };

  const navigateToday = () => {
    setCurrentDate(new Date());
  };

  // Get entries for a specific day
  const getEntriesForDay = (date) => {
    return entries.filter((entry) => {
      const entryDate = new Date(
        entry.scheduled_at || entry.started_at || entry.completed_at
      );
      return isSameDay(entryDate, date);
    });
  };

  // Helper to check if two dates are the same day
  function isSameDay(d1, d2) {
    return (
      d1.getFullYear() === d2.getFullYear() &&
      d1.getMonth() === d2.getMonth() &&
      d1.getDate() === d2.getDate()
    );
  }

  // Get unique job types from entries
  const availableJobTypes = useMemo(() => {
    const types = new Set(entries.map((e) => e.job_type));
    return Array.from(types).sort();
  }, [entries]);

  // Drag and drop handlers
  const handleDragStart = useCallback((entry, event) => {
    // Only allow dragging PENDING jobs
    if (entry.status !== 'PENDING') {
      event.preventDefault();
      return;
    }
    setDraggedEntry(entry);
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', entry.job_id);
  }, []);

  const handleDragEnd = useCallback(() => {
    setDraggedEntry(null);
    setDropTargetDate(null);
  }, []);

  const handleDragOver = useCallback((date, event) => {
    event.preventDefault();
    if (!draggedEntry) return;

    // Don't allow dropping on same day
    const entryDate = new Date(draggedEntry.scheduled_at);
    if (isSameDay(entryDate, date)) {
      event.dataTransfer.dropEffect = 'none';
      return;
    }

    event.dataTransfer.dropEffect = 'move';
    setDropTargetDate(date);
  }, [draggedEntry]);

  const handleDragLeave = useCallback(() => {
    setDropTargetDate(null);
  }, []);

  const handleDrop = useCallback(async (targetDate, event) => {
    event.preventDefault();
    setDropTargetDate(null);

    if (!draggedEntry || isRescheduling) return;

    // Don't allow dropping on same day
    const entryDate = new Date(draggedEntry.scheduled_at);
    if (isSameDay(entryDate, targetDate)) {
      setDraggedEntry(null);
      return;
    }

    // Calculate new scheduled time (keep original time, change date)
    const originalTime = new Date(draggedEntry.scheduled_at);
    const newScheduledAt = new Date(targetDate);
    newScheduledAt.setHours(
      originalTime.getHours(),
      originalTime.getMinutes(),
      originalTime.getSeconds()
    );

    setIsRescheduling(true);
    const entryToMove = draggedEntry;
    setDraggedEntry(null);

    try {
      await rescheduleJob(entryToMove.schedule_id || entryToMove.job_id, newScheduledAt.toISOString());
      toast.success(`Job rescheduled to ${newScheduledAt.toLocaleDateString()}`);
      // Reload timeline data
      loadTimeline();
      if (onRefresh) onRefresh();
    } catch (err) {
      console.error('Failed to reschedule job:', err);
      toast.error(err.message || 'Failed to reschedule job');
    } finally {
      setIsRescheduling(false);
    }
  }, [draggedEntry, isRescheduling, loadTimeline, onRefresh, toast]);

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-3 sm:p-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 sm:gap-4">
          {/* Row 1: View Mode + Navigation (mobile: stacked, desktop: inline) */}
          <div className="flex items-center justify-between sm:justify-start gap-2 sm:gap-4">
            {/* View Mode Selector */}
            <div className="flex items-center gap-1 sm:gap-2">
              {VIEW_MODES.map((mode) => (
                <button
                  key={mode.id}
                  onClick={() => setViewMode(mode.id)}
                  className={`px-2 sm:px-3 py-1.5 text-xs sm:text-sm font-medium rounded-lg transition-colors touch-target ${
                    viewMode === mode.id
                      ? 'bg-aura-100 dark:bg-aura-900/30 text-aura-700 dark:text-aura-300'
                      : 'text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700'
                  }`}
                >
                  {mode.label}
                </button>
              ))}
            </div>

            {/* Navigation */}
            <div className="flex items-center gap-1 sm:gap-2">
              <button
                onClick={navigatePrev}
                aria-label="Previous period"
                className="p-2 text-surface-500 hover:text-surface-700 dark:hover:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors touch-target"
              >
                <ChevronLeftIcon className="w-5 h-5" />
              </button>
              <button
                onClick={navigateToday}
                className="px-2 sm:px-3 py-1.5 text-xs sm:text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
              >
                Today
              </button>
              <button
                onClick={navigateNext}
                aria-label="Next period"
                className="p-2 text-surface-500 hover:text-surface-700 dark:hover:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors touch-target"
              >
                <ChevronRightIcon className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Row 2: Date Range + Actions (mobile: stacked, desktop: inline) */}
          <div className="flex items-center justify-between sm:justify-end gap-2 sm:gap-4">
            {/* Date Range Display */}
            <div className="flex items-center gap-2 sm:gap-3">
              <CalendarDaysIcon className="w-4 h-4 sm:w-5 sm:h-5 text-surface-400" />
              <span className="text-xs sm:text-sm font-medium text-surface-700 dark:text-surface-300">
                {dateRange.start.toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                })}{' '}
                -{' '}
                {dateRange.end.toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric',
                })}
              </span>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-1 sm:gap-2">
              <button
                onClick={() => setShowFilters(!showFilters)}
                aria-label="Toggle filters"
                className={`flex items-center gap-1 sm:gap-2 px-2 sm:px-3 py-1.5 text-xs sm:text-sm font-medium rounded-lg transition-colors touch-target ${
                  showFilters
                    ? 'bg-aura-100 dark:bg-aura-900/30 text-aura-700 dark:text-aura-300'
                    : 'text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700'
                }`}
              >
                <FunnelIcon className="w-4 h-4" />
                <span className="hidden sm:inline">Filters</span>
              </button>
              <button
                onClick={loadTimeline}
                disabled={loading}
                aria-label="Refresh timeline"
                className="p-2 text-surface-500 hover:text-surface-700 dark:hover:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors disabled:opacity-50 touch-target"
              >
                <ArrowPathIcon className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>
        </div>

        {/* Filters Panel */}
        {showFilters && (
          <div className="mt-4 pt-4 border-t border-surface-200 dark:border-surface-700">
            <div className="flex flex-wrap gap-4">
              {/* Include toggles */}
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={filters.includeScheduled}
                    onChange={(e) =>
                      setFilters({ ...filters, includeScheduled: e.target.checked })
                    }
                    className="rounded border-surface-300 text-aura-600 focus:ring-aura-500"
                  />
                  <span className="text-surface-700 dark:text-surface-300">
                    Scheduled
                  </span>
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={filters.includeCompleted}
                    onChange={(e) =>
                      setFilters({ ...filters, includeCompleted: e.target.checked })
                    }
                    className="rounded border-surface-300 text-aura-600 focus:ring-aura-500"
                  />
                  <span className="text-surface-700 dark:text-surface-300">
                    Completed
                  </span>
                </label>
              </div>

              {/* Job type filter */}
              {availableJobTypes.length > 0 && (
                <div className="flex items-center gap-2">
                  <span className="text-sm text-surface-500">Types:</span>
                  <div className="flex flex-wrap gap-1">
                    {availableJobTypes.map((type) => (
                      <button
                        key={type}
                        onClick={() => {
                          const types = filters.jobTypes.includes(type)
                            ? filters.jobTypes.filter((t) => t !== type)
                            : [...filters.jobTypes, type];
                          setFilters({ ...filters, jobTypes: types });
                        }}
                        className={`px-2 py-0.5 text-xs font-medium rounded transition-colors ${
                          filters.jobTypes.includes(type) ||
                          filters.jobTypes.length === 0
                            ? 'bg-aura-100 dark:bg-aura-900/30 text-aura-700 dark:text-aura-300'
                            : 'bg-surface-100 dark:bg-surface-700 text-surface-500'
                        }`}
                      >
                        {type.replace(/_/g, ' ')}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Error State */}
      {error && (
        <div className="p-4 bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800 rounded-lg">
          <p className="text-sm text-critical-700 dark:text-critical-300">{error}</p>
        </div>
      )}

      {/* Timeline Grid */}
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 overflow-hidden">
        {/* Mobile hint for horizontal scroll */}
        <div className="lg:hidden px-4 py-2 bg-surface-50 dark:bg-surface-700/50 border-b border-surface-200 dark:border-surface-700 text-xs text-surface-500 flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
          </svg>
          <span>Scroll horizontally to view more days</span>
        </div>
        <div className="overflow-x-auto overflow-y-auto max-h-[600px] scrollbar-hide lg:scrollbar-default">
          {/* Header Row */}
          <div
            className="grid border-b border-surface-200 dark:border-surface-700 sticky top-0 z-10"
            style={{
              gridTemplateColumns: viewMode === 'day'
                ? '1fr'
                : viewMode === 'week'
                ? 'repeat(7, minmax(100px, 1fr))'
                : `repeat(${timeSlots.length}, minmax(80px, 1fr))`,
              minWidth: viewMode === 'month' ? `${timeSlots.length * 80}px` : undefined,
            }}
          >
          {timeSlots.map((slot, index) => (
            <div
              key={index}
              className={`px-2 py-3 text-center border-r border-surface-200 dark:border-surface-700 last:border-r-0 ${
                slot.isToday
                  ? 'bg-aura-50 dark:bg-aura-900/20'
                  : 'bg-surface-50 dark:bg-surface-800'
              }`}
            >
              <p
                className={`text-xs sm:text-sm font-medium truncate ${
                  slot.isToday
                    ? 'text-aura-700 dark:text-aura-300'
                    : 'text-surface-700 dark:text-surface-300'
                }`}
              >
                {slot.label}
              </p>
            </div>
          ))}
        </div>

        {/* Timeline Content */}
        <div
          className="grid min-h-[300px] sm:min-h-[400px]"
          style={{
            gridTemplateColumns: viewMode === 'day'
              ? '1fr'
              : viewMode === 'week'
              ? 'repeat(7, minmax(100px, 1fr))'
              : `repeat(${timeSlots.length}, minmax(80px, 1fr))`,
            minWidth: viewMode === 'month' ? `${timeSlots.length * 80}px` : undefined,
          }}
        >
          {timeSlots.map((slot, index) => {
            const dayEntries = getEntriesForDay(slot.date);
            const isDropTarget = dropTargetDate && isSameDay(dropTargetDate, slot.date);

            return (
              <div
                key={index}
                className={`p-1.5 sm:p-2 border-r border-surface-200 dark:border-surface-700 last:border-r-0 min-h-[300px] sm:min-h-[400px] transition-colors ${
                  slot.isToday ? 'bg-aura-50/30 dark:bg-aura-900/10' : ''
                } ${
                  isDropTarget
                    ? 'bg-aura-100 dark:bg-aura-900/30 ring-2 ring-inset ring-aura-500/50'
                    : ''
                } ${draggedEntry ? 'cursor-pointer' : ''}`}
                onDragOver={(e) => handleDragOver(slot.date, e)}
                onDragLeave={handleDragLeave}
                onDrop={(e) => handleDrop(slot.date, e)}
              >
                {loading ? (
                  <div className="space-y-2">
                    {[1, 2].map((i) => (
                      <div
                        key={i}
                        className="h-16 bg-surface-200 dark:bg-surface-700 rounded animate-pulse"
                      />
                    ))}
                  </div>
                ) : dayEntries.length === 0 ? (
                  <div className="h-full flex items-center justify-center">
                    <span className="text-xs text-surface-400">
                      {isDropTarget ? 'Drop here to reschedule' : 'No jobs'}
                    </span>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {dayEntries.map((entry) => (
                      <TimelineEntry
                        key={entry.job_id}
                        entry={entry}
                        onClick={() => setSelectedEntry(entry)}
                        isSelected={selectedEntry?.job_id === entry.job_id}
                        onDragStart={(e) => handleDragStart(entry, e)}
                        onDragEnd={handleDragEnd}
                        isDragging={draggedEntry?.job_id === entry.job_id}
                      />
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
        </div>
      </div>

      {/* Entry Detail Modal */}
      {selectedEntry && (
        <EntryDetailModal
          entry={selectedEntry}
          onClose={() => setSelectedEntry(null)}
        />
      )}

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-3 sm:gap-4 text-xs text-surface-500">
        <span className="font-medium w-full sm:w-auto">Status:</span>
        <div className="flex flex-wrap items-center gap-3 sm:gap-4">
          <div className="flex items-center gap-1">
            <ClockIcon className="w-3 h-3 text-warning-500" />
            <span>Pending</span>
          </div>
          <div className="flex items-center gap-1">
            <PlayIcon className="w-3 h-3 text-info-500" />
            <span>Running</span>
          </div>
          <div className="flex items-center gap-1">
            <CheckCircleIcon className="w-3 h-3 text-olive-500" />
            <span>Succeeded</span>
          </div>
          <div className="flex items-center gap-1">
            <XCircleIcon className="w-3 h-3 text-critical-500" />
            <span>Failed</span>
          </div>
        </div>
        <span className="w-full sm:w-auto sm:ml-4 text-aura-600 dark:text-aura-400">
          Tip: Drag pending jobs to reschedule
        </span>
      </div>
    </div>
  );
}

// Timeline Entry Component
function TimelineEntry({ entry, onClick, isSelected, onDragStart, onDragEnd, isDragging }) {
  const StatusIcon = STATUS_ICONS[entry.status] || ClockIcon;
  const bgColor = JOB_TYPE_COLORS[entry.job_type] || 'bg-surface-500';
  const isDraggable = entry.status === 'PENDING';

  const time = entry.scheduled_at || entry.started_at || entry.completed_at;
  const timeStr = time
    ? new Date(time).toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: '2-digit',
      })
    : '';

  return (
    <button
      onClick={onClick}
      draggable={isDraggable}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      className={`w-full text-left p-2 rounded-lg border transition-all ${
        isSelected
          ? 'border-aura-500 ring-2 ring-aura-500/20'
          : 'border-surface-200 dark:border-surface-600 hover:border-surface-300 dark:hover:border-surface-500'
      } ${
        isDragging
          ? 'opacity-50 scale-95 shadow-lg'
          : ''
      } ${
        isDraggable
          ? 'cursor-grab active:cursor-grabbing'
          : ''
      } bg-white dark:bg-surface-700`}
    >
      <div className="flex items-start gap-2">
        <div className={`w-1 h-full rounded-full ${bgColor}`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1">
            <StatusIcon
              className={`w-3 h-3 flex-shrink-0 ${
                entry.status === 'SUCCEEDED'
                  ? 'text-olive-500'
                  : entry.status === 'FAILED'
                  ? 'text-critical-500'
                  : entry.status === 'RUNNING' || entry.status === 'DISPATCHED'
                  ? 'text-info-500'
                  : 'text-warning-500'
              }`}
            />
            <span className="text-xs font-medium text-surface-700 dark:text-surface-300 truncate">
              {entry.title || entry.job_type.replace(/_/g, ' ')}
            </span>
          </div>
          <div className="flex items-center gap-2 mt-1 text-xs text-surface-500">
            <span>{timeStr}</span>
            {entry.duration_seconds && (
              <span>• {formatDuration(entry.duration_seconds)}</span>
            )}
          </div>
          {entry.repository_name && (
            <p className="text-xs text-surface-400 truncate mt-0.5">
              {entry.repository_name}
            </p>
          )}
          {isDraggable && (
            <p className="text-[10px] text-aura-500 dark:text-aura-400 mt-1">
              Drag to reschedule
            </p>
          )}
        </div>
      </div>
    </button>
  );
}

// Entry Detail Modal
function EntryDetailModal({ entry, onClose }) {
  const StatusIcon = STATUS_ICONS[entry.status] || ClockIcon;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-surface-800 rounded-xl shadow-xl max-w-md w-full p-6">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <StatusIcon
              className={`w-6 h-6 ${
                entry.status === 'SUCCEEDED'
                  ? 'text-olive-500'
                  : entry.status === 'FAILED'
                  ? 'text-critical-500'
                  : entry.status === 'RUNNING'
                  ? 'text-info-500'
                  : 'text-warning-500'
              }`}
            />
            <div>
              <h3 className="font-semibold text-surface-900 dark:text-surface-100">
                {entry.title || entry.job_type.replace(/_/g, ' ')}
              </h3>
              <p className="text-sm text-surface-500">{entry.status}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-surface-400 hover:text-surface-600 dark:hover:text-surface-300"
          >
            <XCircleIcon className="w-6 h-6" />
          </button>
        </div>

        <dl className="space-y-3">
          <div>
            <dt className="text-xs font-medium text-surface-500 uppercase">
              Job Type
            </dt>
            <dd className="text-sm text-surface-900 dark:text-surface-100">
              {entry.job_type.replace(/_/g, ' ')}
            </dd>
          </div>

          {entry.repository_name && (
            <div>
              <dt className="text-xs font-medium text-surface-500 uppercase">
                Repository
              </dt>
              <dd className="text-sm text-surface-900 dark:text-surface-100">
                {entry.repository_name}
              </dd>
            </div>
          )}

          {entry.scheduled_at && (
            <div>
              <dt className="text-xs font-medium text-surface-500 uppercase">
                Scheduled At
              </dt>
              <dd className="text-sm text-surface-900 dark:text-surface-100">
                {new Date(entry.scheduled_at).toLocaleString()}
              </dd>
            </div>
          )}

          {entry.started_at && (
            <div>
              <dt className="text-xs font-medium text-surface-500 uppercase">
                Started At
              </dt>
              <dd className="text-sm text-surface-900 dark:text-surface-100">
                {new Date(entry.started_at).toLocaleString()}
              </dd>
            </div>
          )}

          {entry.completed_at && (
            <div>
              <dt className="text-xs font-medium text-surface-500 uppercase">
                Completed At
              </dt>
              <dd className="text-sm text-surface-900 dark:text-surface-100">
                {new Date(entry.completed_at).toLocaleString()}
              </dd>
            </div>
          )}

          {entry.duration_seconds && (
            <div>
              <dt className="text-xs font-medium text-surface-500 uppercase">
                Duration
              </dt>
              <dd className="text-sm text-surface-900 dark:text-surface-100">
                {formatDuration(entry.duration_seconds)}
              </dd>
            </div>
          )}

          {entry.created_by && (
            <div>
              <dt className="text-xs font-medium text-surface-500 uppercase">
                Created By
              </dt>
              <dd className="text-sm text-surface-900 dark:text-surface-100">
                {entry.created_by}
              </dd>
            </div>
          )}
        </dl>

        <div className="mt-6 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 bg-surface-100 dark:bg-surface-700 rounded-lg hover:bg-surface-200 dark:hover:bg-surface-600 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
