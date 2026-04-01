/**
 * Recurring Task Manager
 *
 * CRUD interface for managing recurring scheduled tasks.
 * ADR-055 Phase 3: Recurring Tasks and Advanced Features
 */

import { useState, useEffect, useCallback } from 'react';
import {
  ArrowPathIcon,
  PlusIcon,
  PencilIcon,
  TrashIcon,
  PlayIcon,
  PauseIcon,
  ClockIcon,
  CalendarDaysIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  XMarkIcon,
  MagnifyingGlassIcon,
} from '@heroicons/react/24/outline';
import CronExpressionBuilder from './CronExpressionBuilder';
import {
  getRecurringTasks,
  createRecurringTask,
  updateRecurringTask,
  deleteRecurringTask,
  toggleRecurringTask,
  JOB_TYPES,
} from '../../services/schedulingApi';

// Job type display configuration
const JOB_TYPE_CONFIG = {
  SECURITY_SCAN: { label: 'Security Scan', color: 'critical', icon: '🔒' },
  CODE_REVIEW: { label: 'Code Review', color: 'aura', icon: '📝' },
  PATCH_GENERATION: { label: 'Patch Generation', color: 'warning', icon: '🔧' },
  VULNERABILITY_ASSESSMENT: { label: 'Vulnerability Assessment', color: 'critical', icon: '🛡️' },
  DEPENDENCY_UPDATE: { label: 'Dependency Update', color: 'success', icon: '📦' },
  REPOSITORY_INDEXING: { label: 'Repository Indexing', color: 'info', icon: '📊' },
  COMPLIANCE_CHECK: { label: 'Compliance Check', color: 'purple', icon: '✓' },
  THREAT_ANALYSIS: { label: 'Threat Analysis', color: 'critical', icon: '⚠️' },
};

export default function RecurringTaskManager() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingTask, setEditingTask] = useState(null);
  const [deletingTaskId, setDeletingTaskId] = useState(null);
  const [togglingIds, setTogglingIds] = useState(new Set());
  const [search, setSearch] = useState('');

  // Filter tasks by search
  const filteredTasks = tasks.filter((task) => {
    if (!search) return true;
    const searchLower = search.toLowerCase();
    const config = JOB_TYPE_CONFIG[task.job_type] || { label: task.job_type };
    return (
      task.name?.toLowerCase().includes(searchLower) ||
      config.label.toLowerCase().includes(searchLower) ||
      task.cron_expression?.toLowerCase().includes(searchLower) ||
      task.repository_name?.toLowerCase().includes(searchLower)
    );
  });

  // Load recurring tasks
  const loadTasks = useCallback(async () => {
    try {
      const data = await getRecurringTasks();
      setTasks(data.tasks || []);
      setError(null);
    } catch (err) {
      console.error('Failed to load recurring tasks:', err);
      setError(err.message || 'Failed to load recurring tasks');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  // Handle create/edit
  const handleSave = async (taskData) => {
    try {
      if (editingTask) {
        await updateRecurringTask(editingTask.task_id, taskData);
      } else {
        await createRecurringTask(taskData);
      }
      setIsModalOpen(false);
      setEditingTask(null);
      loadTasks();
    } catch (err) {
      console.error('Failed to save task:', err);
      throw err;
    }
  };

  // Handle delete
  const handleDelete = async (taskId) => {
    try {
      await deleteRecurringTask(taskId);
      setDeletingTaskId(null);
      loadTasks();
    } catch (err) {
      console.error('Failed to delete task:', err);
    }
  };

  // Handle enable/disable toggle
  const handleToggle = async (taskId, currentEnabled) => {
    setTogglingIds((prev) => new Set([...prev, taskId]));
    try {
      await toggleRecurringTask(taskId, !currentEnabled);
      setTasks((prev) =>
        prev.map((t) =>
          t.task_id === taskId ? { ...t, enabled: !currentEnabled } : t
        )
      );
    } catch (err) {
      console.error('Failed to toggle task:', err);
    } finally {
      setTogglingIds((prev) => {
        const next = new Set(prev);
        next.delete(taskId);
        return next;
      });
    }
  };

  // Open edit modal
  const openEdit = (task) => {
    setEditingTask(task);
    setIsModalOpen(true);
  };

  // Open create modal
  const openCreate = () => {
    setEditingTask(null);
    setIsModalOpen(true);
  };

  if (loading) {
    return (
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-8">
        <div className="flex items-center justify-center gap-2">
          <ArrowPathIcon className="w-5 h-5 text-aura-600 animate-spin" />
          <span className="text-sm text-surface-500">Loading recurring tasks...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-critical-50 dark:bg-critical-900/20 rounded-xl border border-critical-200 dark:border-critical-800 p-6">
        <div className="flex items-center gap-2 text-critical-700 dark:text-critical-300">
          <ExclamationTriangleIcon className="w-5 h-5" />
          <span className="text-sm">{error}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
            Recurring Tasks
          </h2>
          <p className="text-sm text-surface-500">
            Automated scheduled tasks that run on a regular basis
          </p>
        </div>
        <button
          onClick={openCreate}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-aura-600 rounded-lg hover:bg-aura-700 transition-colors"
        >
          <PlusIcon className="w-4 h-4" />
          Create Task
        </button>
      </div>

      {/* Search Bar */}
      <div className="relative max-w-md" role="search">
        <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-surface-400" aria-hidden="true" />
        <input
          type="text"
          placeholder="Search tasks..."
          aria-label="Search recurring tasks"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:outline-none focus:ring-2 focus:ring-aura-500 focus:border-transparent"
        />
      </div>

      {/* Task List */}
      {filteredTasks.length === 0 ? (
        <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-8 text-center">
          <CalendarDaysIcon className="w-12 h-12 text-surface-300 mx-auto mb-3" />
          <p className="text-surface-500">
            {search ? 'No tasks match your search' : 'No recurring tasks configured'}
          </p>
          <p className="text-xs text-surface-400 mt-1">
            {search ? 'Try a different search term' : 'Create a recurring task to automate agent activities'}
          </p>
          {!search && (
            <button
              onClick={openCreate}
              className="mt-4 inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-aura-600 dark:text-aura-400 bg-aura-50 dark:bg-aura-900/20 rounded-lg hover:bg-aura-100 dark:hover:bg-aura-900/40 transition-colors"
            >
              <PlusIcon className="w-4 h-4" />
              Create First Task
            </button>
          )}
        </div>
      ) : (
        <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 overflow-hidden">
          <div className="divide-y divide-surface-200 dark:divide-surface-700 max-h-[500px] overflow-y-auto">
            {filteredTasks.map((task) => (
              <TaskRow
                key={task.task_id}
                task={task}
                onEdit={() => openEdit(task)}
                onDelete={() => setDeletingTaskId(task.task_id)}
                onToggle={() => handleToggle(task.task_id, task.enabled)}
                isToggling={togglingIds.has(task.task_id)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Create/Edit Modal */}
      {isModalOpen && (
        <TaskFormModal
          task={editingTask}
          onSave={handleSave}
          onClose={() => {
            setIsModalOpen(false);
            setEditingTask(null);
          }}
        />
      )}

      {/* Delete Confirmation */}
      {deletingTaskId && (
        <DeleteConfirmModal
          onConfirm={() => handleDelete(deletingTaskId)}
          onCancel={() => setDeletingTaskId(null)}
        />
      )}
    </div>
  );
}

// Individual Task Row
function TaskRow({ task, onEdit, onDelete, onToggle, isToggling }) {
  const config = JOB_TYPE_CONFIG[task.job_type] || {
    label: task.job_type,
    color: 'surface',
    icon: '📋',
  };

  const nextRunDate = task.next_run_at ? new Date(task.next_run_at) : null;
  const lastRunDate = task.last_run_at ? new Date(task.last_run_at) : null;

  return (
    <div
      className={`p-4 transition-colors ${
        !task.enabled ? 'bg-surface-50 dark:bg-surface-800/50 opacity-60' : ''
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          {/* Task Header */}
          <div className="flex items-center gap-3 mb-2">
            <span className="text-lg">{config.icon}</span>
            <div>
              <h3 className="font-medium text-surface-900 dark:text-surface-100">
                {task.name || config.label}
              </h3>
              <p className="text-xs text-surface-500">{config.label}</p>
            </div>
            {!task.enabled && (
              <span className="px-2 py-0.5 text-xs font-medium bg-surface-200 dark:bg-surface-700 text-surface-500 rounded">
                Paused
              </span>
            )}
          </div>

          {/* Schedule Info */}
          <div className="flex items-center gap-4 text-sm text-surface-500">
            <div className="flex items-center gap-1">
              <ClockIcon className="w-4 h-4" />
              <span className="font-mono text-xs">{task.cron_expression}</span>
            </div>
            {task.repository_name && (
              <div className="flex items-center gap-1">
                <span>📁</span>
                <span>{task.repository_name}</span>
              </div>
            )}
          </div>

          {/* Run Times */}
          <div className="flex items-center gap-4 mt-2 text-xs text-surface-400">
            {nextRunDate && task.enabled && (
              <span>
                Next run: {nextRunDate.toLocaleDateString()}{' '}
                {nextRunDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
            {lastRunDate && (
              <span>
                Last run: {lastRunDate.toLocaleDateString()}{' '}
                {lastRunDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={onToggle}
            disabled={isToggling}
            className={`p-2 rounded-lg transition-colors ${
              task.enabled
                ? 'text-warning-600 hover:bg-warning-50 dark:hover:bg-warning-900/20'
                : 'text-success-600 hover:bg-success-50 dark:hover:bg-success-900/20'
            } disabled:opacity-50`}
            title={task.enabled ? 'Pause' : 'Enable'}
          >
            {isToggling ? (
              <ArrowPathIcon className="w-4 h-4 animate-spin" />
            ) : task.enabled ? (
              <PauseIcon className="w-4 h-4" />
            ) : (
              <PlayIcon className="w-4 h-4" />
            )}
          </button>
          <button
            onClick={onEdit}
            className="p-2 text-surface-500 hover:text-surface-700 dark:hover:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
            title="Edit"
          >
            <PencilIcon className="w-4 h-4" />
          </button>
          <button
            onClick={onDelete}
            className="p-2 text-critical-500 hover:text-critical-700 dark:hover:text-critical-300 hover:bg-critical-50 dark:hover:bg-critical-900/20 rounded-lg transition-colors"
            title="Delete"
          >
            <TrashIcon className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

// Task Form Modal
function TaskFormModal({ task, onSave, onClose }) {
  const [formData, setFormData] = useState({
    name: task?.name || '',
    job_type: task?.job_type || 'SECURITY_SCAN',
    cron_expression: task?.cron_expression || '0 6 * * *',
    repository_id: task?.repository_id || '',
    parameters: task?.parameters || {},
    enabled: task?.enabled ?? true,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    try {
      await onSave(formData);
    } catch (err) {
      setError(err.message || 'Failed to save task');
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-surface-800 rounded-xl shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-surface-200 dark:border-surface-700">
          <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
            {task ? 'Edit Recurring Task' : 'Create Recurring Task'}
          </h3>
          <button
            onClick={onClose}
            className="text-surface-400 hover:text-surface-600 dark:hover:text-surface-300"
          >
            <XMarkIcon className="w-6 h-6" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {error && (
            <div className="p-3 bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800 rounded-lg">
              <p className="text-sm text-critical-700 dark:text-critical-300">{error}</p>
            </div>
          )}

          {/* Task Name */}
          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
              Task Name
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="e.g., Weekly Security Scan"
              className="w-full px-3 py-2 text-sm border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500"
            />
          </div>

          {/* Job Type */}
          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
              Job Type
            </label>
            <select
              value={formData.job_type}
              onChange={(e) => setFormData({ ...formData, job_type: e.target.value })}
              className="w-full px-3 py-2 text-sm border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500"
            >
              {Object.entries(JOB_TYPE_CONFIG).map(([value, config]) => (
                <option key={value} value={value}>
                  {config.icon} {config.label}
                </option>
              ))}
            </select>
          </div>

          {/* Schedule */}
          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
              Schedule
            </label>
            <CronExpressionBuilder
              value={formData.cron_expression}
              onChange={(cron) => setFormData({ ...formData, cron_expression: cron })}
            />
          </div>

          {/* Enabled Toggle */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setFormData({ ...formData, enabled: !formData.enabled })}
              className={`relative w-11 h-6 rounded-full transition-colors ${
                formData.enabled ? 'bg-aura-600' : 'bg-surface-300 dark:bg-surface-600'
              }`}
            >
              <span
                className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                  formData.enabled ? 'translate-x-5' : ''
                }`}
              />
            </button>
            <span className="text-sm text-surface-700 dark:text-surface-300">
              {formData.enabled ? 'Enabled' : 'Disabled'}
            </span>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-4 border-t border-surface-200 dark:border-surface-700">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 bg-surface-100 dark:bg-surface-700 rounded-lg hover:bg-surface-200 dark:hover:bg-surface-600 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-aura-600 rounded-lg hover:bg-aura-700 transition-colors disabled:opacity-50"
            >
              {saving && <ArrowPathIcon className="w-4 h-4 animate-spin" />}
              {task ? 'Save Changes' : 'Create Task'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// Delete Confirmation Modal
function DeleteConfirmModal({ onConfirm, onCancel }) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-surface-800 rounded-xl shadow-xl max-w-sm w-full p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-critical-100 dark:bg-critical-900/30 rounded-full">
            <TrashIcon className="w-6 h-6 text-critical-600 dark:text-critical-400" />
          </div>
          <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
            Delete Task
          </h3>
        </div>
        <p className="text-sm text-surface-500 mb-6">
          Are you sure you want to delete this recurring task? This action cannot be undone.
        </p>
        <div className="flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 bg-surface-100 dark:bg-surface-700 rounded-lg hover:bg-surface-200 dark:hover:bg-surface-600 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 text-sm font-medium text-white bg-critical-600 rounded-lg hover:bg-critical-700 transition-colors"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}
