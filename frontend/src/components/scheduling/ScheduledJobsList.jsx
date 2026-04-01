/**
 * Scheduled Jobs List Component
 *
 * Displays a table of scheduled jobs with actions.
 * ADR-055: Agent Scheduling View and Job Queue Management
 */

import { useState } from 'react';
import {
  CalendarIcon,
  ClockIcon,
  XMarkIcon,
  PencilIcon,
  EyeIcon,
  FunnelIcon,
  MagnifyingGlassIcon,
} from '@heroicons/react/24/outline';
import {
  formatRelativeTime,
  getStatusColor,
  getPriorityColor,
  cancelScheduledJob,
  rescheduleJob,
} from '../../services/schedulingApi';

function StatusBadge({ status }) {
  const color = getStatusColor(status);

  const colorClasses = {
    success: 'bg-success-100 dark:bg-success-900/30 text-success-700 dark:text-success-300',
    warning: 'bg-warning-100 dark:bg-warning-900/30 text-warning-700 dark:text-warning-300',
    critical: 'bg-critical-100 dark:bg-critical-900/30 text-critical-700 dark:text-critical-300',
    info: 'bg-aura-100 dark:bg-aura-900/30 text-aura-700 dark:text-aura-300',
    surface: 'bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-400',
  };

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colorClasses[color]}`}>
      {status}
    </span>
  );
}

function PriorityBadge({ priority }) {
  const color = getPriorityColor(priority);

  const colorClasses = {
    critical: 'bg-critical-100 dark:bg-critical-900/30 text-critical-700 dark:text-critical-300',
    warning: 'bg-warning-100 dark:bg-warning-900/30 text-warning-700 dark:text-warning-300',
    info: 'bg-aura-100 dark:bg-aura-900/30 text-aura-700 dark:text-aura-300',
    surface: 'bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-400',
  };

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colorClasses[color]}`}>
      {priority}
    </span>
  );
}

function RescheduleModal({ job, isOpen, onClose, onReschedule }) {
  const [newDate, setNewDate] = useState('');
  const [newTime, setNewTime] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen || !job) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const scheduledAt = new Date(`${newDate}T${newTime}`).toISOString();
      await rescheduleJob(job.schedule_id, scheduledAt);
      onReschedule();
    } catch (err) {
      setError(err.message || 'Failed to reschedule job');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
      <div className="bg-white dark:bg-surface-800 rounded-xl shadow-xl max-w-md w-full p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
            Reschedule Job
          </h3>
          <button onClick={onClose} className="text-surface-400 hover:text-surface-600">
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        <p className="text-sm text-surface-500 dark:text-surface-400 mb-4">
          Reschedule "{job.description || job.job_type}" to a new time.
        </p>

        {error && (
          <div className="mb-4 p-3 bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800 rounded-lg">
            <p className="text-sm text-critical-700 dark:text-critical-300">{error}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
              Date
            </label>
            <input
              type="date"
              value={newDate}
              onChange={(e) => setNewDate(e.target.value)}
              required
              min={new Date().toISOString().split('T')[0]}
              className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:outline-none focus:ring-2 focus:ring-aura-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
              Time
            </label>
            <input
              type="time"
              value={newTime}
              onChange={(e) => setNewTime(e.target.value)}
              required
              className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:outline-none focus:ring-2 focus:ring-aura-500"
            />
          </div>

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 bg-surface-100 dark:bg-surface-700 rounded-lg hover:bg-surface-200 dark:hover:bg-surface-600"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 px-4 py-2 text-sm font-medium text-white bg-aura-600 rounded-lg hover:bg-aura-700 disabled:opacity-50"
            >
              {loading ? 'Saving...' : 'Reschedule'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function ScheduledJobsList({ jobs, loading, onJobAction }) {
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [selectedJob, setSelectedJob] = useState(null);
  const [isRescheduleOpen, setIsRescheduleOpen] = useState(false);
  const [cancellingId, setCancellingId] = useState(null);

  // Filter jobs
  const filteredJobs = jobs.filter((job) => {
    // Status filter
    if (filter !== 'all' && job.status !== filter) {
      return false;
    }

    // Search filter
    if (search) {
      const searchLower = search.toLowerCase();
      return (
        job.job_type.toLowerCase().includes(searchLower) ||
        job.description?.toLowerCase().includes(searchLower) ||
        job.repository_id?.toLowerCase().includes(searchLower)
      );
    }

    return true;
  });

  const handleCancel = async (job) => {
    if (!confirm(`Are you sure you want to cancel this scheduled job?`)) {
      return;
    }

    setCancellingId(job.schedule_id);
    try {
      await cancelScheduledJob(job.schedule_id);
      onJobAction?.();
    } catch (err) {
      alert(err.message || 'Failed to cancel job');
    } finally {
      setCancellingId(null);
    }
  };

  const handleReschedule = (job) => {
    setSelectedJob(job);
    setIsRescheduleOpen(true);
  };

  const handleRescheduleComplete = () => {
    setIsRescheduleOpen(false);
    setSelectedJob(null);
    onJobAction?.();
  };

  if (loading && jobs.length === 0) {
    return (
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-8">
        <div className="animate-pulse space-y-4">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 bg-surface-100 dark:bg-surface-700 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1 max-w-md" role="search">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-surface-400" aria-hidden="true" />
          <input
            type="text"
            placeholder="Search jobs..."
            aria-label="Search scheduled jobs"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:outline-none focus:ring-2 focus:ring-aura-500 focus:border-transparent"
          />
        </div>
        <div className="flex items-center gap-2">
          <FunnelIcon className="w-4 h-4 text-surface-400" />
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 focus:outline-none focus:ring-2 focus:ring-aura-500"
          >
            <option value="all">All Status</option>
            <option value="PENDING">Pending</option>
            <option value="DISPATCHED">Dispatched</option>
            <option value="CANCELLED">Cancelled</option>
            <option value="FAILED">Failed</option>
          </select>
        </div>
      </div>

      {/* Jobs Table */}
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 overflow-hidden">
        {filteredJobs.length === 0 ? (
          <div className="p-8 text-center">
            <CalendarIcon className="w-12 h-12 text-surface-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-surface-900 dark:text-surface-100 mb-2">
              No Scheduled Jobs
            </h3>
            <p className="text-sm text-surface-500 dark:text-surface-400">
              {search || filter !== 'all'
                ? 'No jobs match your filters'
                : 'Schedule a job to get started'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
            <table className="w-full">
              <thead className="bg-surface-50 dark:bg-surface-700/50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wider">
                    Job
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wider">
                    Scheduled For
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wider">
                    Priority
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-200 dark:divide-surface-700">
                {filteredJobs.map((job) => (
                  <tr key={job.schedule_id} className="hover:bg-surface-50 dark:hover:bg-surface-700/50">
                    <td className="px-4 py-4">
                      <div>
                        <p className="text-sm font-medium text-surface-900 dark:text-surface-100">
                          {job.job_type.replace(/_/g, ' ')}
                        </p>
                        {job.description && (
                          <p className="text-xs text-surface-500 dark:text-surface-400 mt-0.5">
                            {job.description}
                          </p>
                        )}
                        {job.repository_id && (
                          <p className="text-xs text-surface-400 dark:text-surface-500 mt-0.5">
                            {job.repository_id}
                          </p>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-2 text-sm text-surface-600 dark:text-surface-400">
                        <ClockIcon className="w-4 h-4" />
                        <span>{formatRelativeTime(job.scheduled_at)}</span>
                      </div>
                      <p className="text-xs text-surface-400 dark:text-surface-500 mt-0.5">
                        {new Date(job.scheduled_at).toLocaleString()}
                      </p>
                    </td>
                    <td className="px-4 py-4">
                      <PriorityBadge priority={job.priority} />
                    </td>
                    <td className="px-4 py-4">
                      <StatusBadge status={job.status} />
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center justify-end gap-2">
                        {job.status === 'PENDING' && (
                          <>
                            <button
                              onClick={() => handleReschedule(job)}
                              className="p-1.5 text-surface-400 hover:text-aura-600 dark:hover:text-aura-400 transition-colors"
                              title="Reschedule"
                              aria-label="Reschedule job"
                            >
                              <PencilIcon className="w-4 h-4" aria-hidden="true" />
                            </button>
                            <button
                              onClick={() => handleCancel(job)}
                              disabled={cancellingId === job.schedule_id}
                              className="p-1.5 text-surface-400 hover:text-critical-600 dark:hover:text-critical-400 transition-colors disabled:opacity-50"
                              title="Cancel"
                              aria-label="Cancel job"
                            >
                              <XMarkIcon className="w-4 h-4" aria-hidden="true" />
                            </button>
                          </>
                        )}
                        <button
                          className="p-1.5 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 transition-colors"
                          title="View Details"
                          aria-label="View job details"
                        >
                          <EyeIcon className="w-4 h-4" aria-hidden="true" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Reschedule Modal */}
      <RescheduleModal
        job={selectedJob}
        isOpen={isRescheduleOpen}
        onClose={() => setIsRescheduleOpen(false)}
        onReschedule={handleRescheduleComplete}
      />
    </div>
  );
}
