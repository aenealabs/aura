/**
 * Scheduling Page
 *
 * Main view for job scheduling and queue management.
 * ADR-055: Agent Scheduling View and Job Queue Management
 */

import { useState, useEffect, useCallback } from 'react';
import {
  CalendarDaysIcon,
  QueueListIcon,
  ClockIcon,
  PlusIcon,
  ArrowPathIcon,
  ShieldExclamationIcon,
} from '@heroicons/react/24/outline';
import JobQueueDashboard from './JobQueueDashboard';
import ScheduledJobsList from './ScheduledJobsList';
import ScheduleJobModal from './ScheduleJobModal';
import JobTimelineView from './JobTimelineView';
import ApprovalQueueWidget from './ApprovalQueueWidget';
import RecurringTaskManager from './RecurringTaskManager';
import { useToast } from '../ui/Toast';
import { getQueueStatus, getScheduledJobs } from '../../services/schedulingApi';

const TABS = [
  { id: 'queue', label: 'Queue Status', icon: QueueListIcon },
  { id: 'scheduled', label: 'Scheduled Jobs', icon: CalendarDaysIcon },
  { id: 'timeline', label: 'Timeline', icon: ClockIcon },
  { id: 'approvals', label: 'HITL Approvals', icon: ShieldExclamationIcon },
  { id: 'recurring', label: 'Recurring Tasks', icon: ArrowPathIcon },
];

export default function SchedulingPage() {
  const [activeTab, setActiveTab] = useState('queue');
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState(false);
  const [queueStatus, setQueueStatus] = useState(null);
  const [scheduledJobs, setScheduledJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const { toast } = useToast();

  // Load data
  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [statusData, jobsData] = await Promise.all([
        getQueueStatus(),
        getScheduledJobs({ limit: 100 }),
      ]);

      setQueueStatus(statusData);
      setScheduledJobs(jobsData.jobs || []);
    } catch (err) {
      console.error('Failed to load scheduling data:', err);
      setError(err.message || 'Failed to load scheduling data');
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    loadData();
  }, [loadData, refreshKey]);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      loadData();
    }, 30000);

    return () => clearInterval(interval);
  }, [loadData]);

  const handleRefresh = async () => {
    setLoading(true);
    setError(null);

    try {
      const [statusData, jobsData] = await Promise.all([
        getQueueStatus(),
        getScheduledJobs({ limit: 100 }),
      ]);

      setQueueStatus(statusData);
      setScheduledJobs(jobsData.jobs || []);
      toast.success('Agent Scheduling refreshed');
    } catch (err) {
      console.error('Failed to load scheduling data:', err);
      setError(err.message || 'Failed to load scheduling data');
      toast.error('Failed to refresh scheduling data');
    } finally {
      setLoading(false);
    }
  };

  const handleJobScheduled = () => {
    setIsScheduleModalOpen(false);
    handleRefresh();
  };

  const handleJobAction = () => {
    handleRefresh();
  };

  return (
    <div className="min-h-screen">
      {/* Header */}
      <div className="bg-white dark:bg-surface-800 border-b border-surface-200 dark:border-surface-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
                Agent Scheduling
              </h1>
              <p className="mt-1 text-sm text-surface-500 dark:text-surface-400">
                Schedule jobs, monitor queue status, and manage agent activities
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={handleRefresh}
                disabled={loading}
                className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 bg-surface-100 dark:bg-surface-700 rounded-lg hover:bg-surface-200 dark:hover:bg-surface-600 transition-colors disabled:opacity-50"
              >
                <ArrowPathIcon className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </button>
              <button
                onClick={() => setIsScheduleModalOpen(true)}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-aura-600 rounded-lg hover:bg-aura-700 transition-colors"
              >
                <PlusIcon className="w-4 h-4" />
                Schedule Job
              </button>
            </div>
          </div>

          {/* Tabs */}
          <div className="mt-6 flex gap-1 border-b border-surface-200 dark:border-surface-700 -mb-px">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-aura-600 text-aura-600 dark:text-aura-400'
                    : 'border-transparent text-surface-500 dark:text-surface-400 hover:text-surface-700 dark:hover:text-surface-300 hover:border-surface-300'
                }`}
              >
                <tab.icon className="w-4 h-4" />
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Error State */}
        {error && (
          <div className="mb-6 p-4 bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800 rounded-lg">
            <p className="text-sm text-critical-700 dark:text-critical-300">{error}</p>
          </div>
        )}

        {/* Tab Content */}
        {activeTab === 'queue' && (
          <JobQueueDashboard
            queueStatus={queueStatus}
            loading={loading}
            onRefresh={handleRefresh}
          />
        )}

        {activeTab === 'scheduled' && (
          <ScheduledJobsList
            jobs={scheduledJobs}
            loading={loading}
            onJobAction={handleJobAction}
          />
        )}

        {activeTab === 'timeline' && (
          <JobTimelineView onRefresh={handleRefresh} />
        )}

        {activeTab === 'approvals' && (
          <ApprovalQueueWidget onApprovalAction={handleRefresh} />
        )}

        {activeTab === 'recurring' && (
          <RecurringTaskManager />
        )}
      </div>

      {/* Schedule Job Modal */}
      <ScheduleJobModal
        isOpen={isScheduleModalOpen}
        onClose={() => setIsScheduleModalOpen(false)}
        onScheduled={handleJobScheduled}
      />
    </div>
  );
}
