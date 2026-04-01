/**
 * Schedule Job Modal Component
 *
 * Modal form for scheduling new jobs.
 * ADR-055: Agent Scheduling View and Job Queue Management
 */

import { useState, useEffect } from 'react';
import {
  XMarkIcon,
  CalendarIcon,
  ClockIcon,
  DocumentTextIcon,
  FolderIcon,
  FlagIcon,
  BoltIcon,
} from '@heroicons/react/24/outline';
import { createScheduledJob, getJobTypes } from '../../services/schedulingApi';

const PRIORITY_OPTIONS = [
  { value: 'CRITICAL', label: 'Critical', description: 'Immediate attention required', color: 'critical' },
  { value: 'HIGH', label: 'High', description: 'Process before normal jobs', color: 'warning' },
  { value: 'NORMAL', label: 'Normal', description: 'Standard priority', color: 'aura' },
  { value: 'LOW', label: 'Low', description: 'Process when resources available', color: 'surface' },
];

function PrioritySelector({ value, onChange }) {
  return (
    <div className="space-y-2">
      {PRIORITY_OPTIONS.map((option) => {
        const isSelected = value === option.value;
        const colorClasses = {
          critical: isSelected
            ? 'border-critical-500 bg-critical-50 dark:bg-critical-900/20'
            : 'border-surface-200 dark:border-surface-600 hover:border-critical-300',
          warning: isSelected
            ? 'border-warning-500 bg-warning-50 dark:bg-warning-900/20'
            : 'border-surface-200 dark:border-surface-600 hover:border-warning-300',
          aura: isSelected
            ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/20'
            : 'border-surface-200 dark:border-surface-600 hover:border-aura-300',
          surface: isSelected
            ? 'border-surface-500 bg-surface-100 dark:bg-surface-700'
            : 'border-surface-200 dark:border-surface-600 hover:border-surface-400',
        };

        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            className={`w-full flex items-center gap-3 p-3 rounded-lg border transition-colors ${colorClasses[option.color]}`}
          >
            <div
              className={`w-3 h-3 rounded-full ${
                isSelected ? 'bg-current' : 'bg-surface-300 dark:bg-surface-600'
              }`}
            />
            <div className="flex-1 text-left">
              <p className="text-sm font-medium text-surface-900 dark:text-surface-100">
                {option.label}
              </p>
              <p className="text-xs text-surface-500 dark:text-surface-400">{option.description}</p>
            </div>
          </button>
        );
      })}
    </div>
  );
}

export default function ScheduleJobModal({ isOpen, onClose, onScheduled }) {
  const [jobTypes, setJobTypes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Form state
  const [jobType, setJobType] = useState('');
  const [scheduledDate, setScheduledDate] = useState('');
  const [scheduledTime, setScheduledTime] = useState('');
  const [priority, setPriority] = useState('NORMAL');
  const [repositoryId, setRepositoryId] = useState('');
  const [description, setDescription] = useState('');

  // Load job types on mount
  useEffect(() => {
    async function loadJobTypes() {
      try {
        const types = await getJobTypes();
        setJobTypes(types);
        if (types.length > 0) {
          setJobType(types[0].value);
        }
      } catch (err) {
        console.error('Failed to load job types:', err);
      }
    }

    if (isOpen) {
      loadJobTypes();
      // Set default date/time to 1 hour from now
      const defaultTime = new Date(Date.now() + 60 * 60 * 1000);
      setScheduledDate(defaultTime.toISOString().split('T')[0]);
      setScheduledTime(defaultTime.toTimeString().slice(0, 5));
    }
  }, [isOpen]);

  // Reset form when closed
  useEffect(() => {
    if (!isOpen) {
      setError(null);
      setJobType('');
      setScheduledDate('');
      setScheduledTime('');
      setPriority('NORMAL');
      setRepositoryId('');
      setDescription('');
    }
  }, [isOpen]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      // Validate inputs
      if (!jobType) {
        throw new Error('Please select a job type');
      }
      if (!scheduledDate || !scheduledTime) {
        throw new Error('Please select a date and time');
      }

      // Build scheduled_at timestamp
      const scheduledAt = new Date(`${scheduledDate}T${scheduledTime}`).toISOString();

      // Validate scheduled time is in the future
      if (new Date(scheduledAt) <= new Date()) {
        throw new Error('Scheduled time must be in the future');
      }

      // Create the job
      await createScheduledJob({
        job_type: jobType,
        scheduled_at: scheduledAt,
        priority,
        repository_id: repositoryId || undefined,
        description: description || undefined,
      });

      onScheduled?.();
    } catch (err) {
      setError(err.message || 'Failed to schedule job');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
      <div className="bg-white dark:bg-surface-800 rounded-xl shadow-xl max-w-lg w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-surface-200 dark:border-surface-700">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-aura-100 dark:bg-aura-900/30 rounded-lg">
              <CalendarIcon className="w-5 h-5 text-aura-600 dark:text-aura-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
                Schedule New Job
              </h2>
              <p className="text-sm text-surface-500 dark:text-surface-400">
                Schedule an agent job for later execution
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 transition-colors rounded-lg hover:bg-surface-100 dark:hover:bg-surface-700"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6">
          {error && (
            <div className="mb-4 p-3 bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800 rounded-lg">
              <p className="text-sm text-critical-700 dark:text-critical-300">{error}</p>
            </div>
          )}

          <form id="schedule-job-form" onSubmit={handleSubmit} className="space-y-5">
            {/* Job Type */}
            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                <BoltIcon className="w-4 h-4" />
                Job Type
              </label>
              <select
                value={jobType}
                onChange={(e) => setJobType(e.target.value)}
                required
                className="w-full px-3 py-2.5 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:outline-none focus:ring-2 focus:ring-aura-500"
              >
                <option value="">Select a job type...</option>
                {jobTypes.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Date and Time */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="flex items-center gap-2 text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                  <CalendarIcon className="w-4 h-4" />
                  Date
                </label>
                <input
                  type="date"
                  value={scheduledDate}
                  onChange={(e) => setScheduledDate(e.target.value)}
                  required
                  min={new Date().toISOString().split('T')[0]}
                  className="w-full px-3 py-2.5 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:outline-none focus:ring-2 focus:ring-aura-500"
                />
              </div>
              <div>
                <label className="flex items-center gap-2 text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                  <ClockIcon className="w-4 h-4" />
                  Time
                </label>
                <input
                  type="time"
                  value={scheduledTime}
                  onChange={(e) => setScheduledTime(e.target.value)}
                  required
                  className="w-full px-3 py-2.5 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:outline-none focus:ring-2 focus:ring-aura-500"
                />
              </div>
            </div>

            {/* Priority */}
            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                <FlagIcon className="w-4 h-4" />
                Priority
              </label>
              <PrioritySelector value={priority} onChange={setPriority} />
            </div>

            {/* Repository (Optional) */}
            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                <FolderIcon className="w-4 h-4" />
                Repository
                <span className="text-surface-400 font-normal">(optional)</span>
              </label>
              <input
                type="text"
                value={repositoryId}
                onChange={(e) => setRepositoryId(e.target.value)}
                placeholder="e.g., repo-main, org/repository-name"
                className="w-full px-3 py-2.5 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder:text-surface-400 focus:outline-none focus:ring-2 focus:ring-aura-500"
              />
            </div>

            {/* Description (Optional) */}
            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                <DocumentTextIcon className="w-4 h-4" />
                Description
                <span className="text-surface-400 font-normal">(optional)</span>
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Add a description for this scheduled job..."
                rows={3}
                className="w-full px-3 py-2.5 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder:text-surface-400 focus:outline-none focus:ring-2 focus:ring-aura-500 resize-none"
              />
            </div>
          </form>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 bg-white dark:bg-surface-700 border border-surface-300 dark:border-surface-600 rounded-lg hover:bg-surface-50 dark:hover:bg-surface-600 transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            form="schedule-job-form"
            disabled={loading}
            className="px-4 py-2 text-sm font-medium text-white bg-aura-600 rounded-lg hover:bg-aura-700 disabled:opacity-50 transition-colors flex items-center gap-2"
          >
            {loading ? (
              <>
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                    fill="none"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Scheduling...
              </>
            ) : (
              <>
                <CalendarIcon className="w-4 h-4" />
                Schedule Job
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
