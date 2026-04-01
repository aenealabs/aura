/**
 * Project Aura - Override Panel
 *
 * Human override interface for AI alignment control.
 * Allows administrators to grant temporary autonomy overrides,
 * execute rollbacks, and manage agent permissions.
 *
 * Features:
 * - Grant temporary autonomy level increases
 * - Revoke active overrides
 * - View override history
 * - Execute action rollbacks
 * - Check rollback capability
 *
 * Reference: ADR-052 AI Alignment Principles & Human-Machine Collaboration
 */

import { useState, useEffect, useCallback } from 'react';
import {
  ShieldCheckIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
  UserIcon,
  XMarkIcon,
  PlusIcon,
  TrashIcon,
  ArrowUturnLeftIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';
import { useToast } from '../ui/Toast';
import ConfirmDialog from '../ui/ConfirmDialog';
import {
  grantOverride,
  revokeOverride,
  getRollbackCapability,
  executeRollback,
  AutonomyLevel,
} from '../../services/alignmentApi';

const AUTONOMY_LEVELS = [
  {
    value: AutonomyLevel.OBSERVE,
    label: 'Observe',
    description: 'Can only observe and report, no actions',
    color: 'bg-surface-100 text-surface-700 dark:bg-surface-700 dark:text-surface-300',
  },
  {
    value: AutonomyLevel.RECOMMEND,
    label: 'Recommend',
    description: 'Can recommend actions, requires approval for all',
    color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
  },
  {
    value: AutonomyLevel.EXECUTE_REVIEW,
    label: 'Execute with Review',
    description: 'Can execute reversible actions, review for others',
    color: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  },
  {
    value: AutonomyLevel.AUTONOMOUS,
    label: 'Autonomous',
    description: 'Can execute most actions autonomously',
    color: 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-300',
  },
];

const DURATION_OPTIONS = [
  { value: 1, label: '1 hour' },
  { value: 4, label: '4 hours' },
  { value: 8, label: '8 hours' },
  { value: 24, label: '24 hours' },
  { value: 48, label: '48 hours' },
  { value: 168, label: '1 week' },
];

/**
 * Override Form Component
 */
function OverrideForm({ onSubmit, onCancel, loading }) {
  const [agentId, setAgentId] = useState('');
  const [newLevel, setNewLevel] = useState(AutonomyLevel.EXECUTE_REVIEW);
  const [reason, setReason] = useState('');
  const [durationHours, setDurationHours] = useState(24);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!agentId.trim() || !reason.trim()) return;
    onSubmit({ agentId, newLevel, reason, durationHours });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
          Agent ID
        </label>
        <input
          type="text"
          value={agentId}
          onChange={(e) => setAgentId(e.target.value)}
          placeholder="e.g., coder-agent-001"
          className="w-full px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-brand-500 focus:border-transparent"
          required
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
          New Autonomy Level
        </label>
        <div className="space-y-2">
          {AUTONOMY_LEVELS.map((level) => (
            <label
              key={level.value}
              className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                newLevel === level.value
                  ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                  : 'border-surface-200 dark:border-surface-700 hover:bg-surface-50 dark:hover:bg-surface-800'
              }`}
            >
              <input
                type="radio"
                name="autonomyLevel"
                value={level.value}
                checked={newLevel === level.value}
                onChange={(e) => setNewLevel(e.target.value)}
                className="mt-1"
              />
              <div>
                <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${level.color}`}>
                  {level.label}
                </span>
                <p className="mt-1 text-sm text-surface-500 dark:text-surface-400">
                  {level.description}
                </p>
              </div>
            </label>
          ))}
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
          Duration
        </label>
        <select
          value={durationHours}
          onChange={(e) => setDurationHours(Number(e.target.value))}
          className="w-full px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100"
        >
          {DURATION_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
          Justification
        </label>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Explain why this override is needed..."
          rows={3}
          className="w-full px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-brand-500 focus:border-transparent"
          required
        />
      </div>

      <div className="flex items-center gap-3 pt-2">
        <button
          type="submit"
          disabled={loading || !agentId.trim() || !reason.trim()}
          className="flex-1 px-4 py-2 rounded-lg bg-brand-500 text-white font-medium hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? 'Granting...' : 'Grant Override'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 rounded-lg border border-surface-300 dark:border-surface-600 text-surface-700 dark:text-surface-300 hover:bg-surface-50 dark:hover:bg-surface-800 transition-colors"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

/**
 * Active Override Card Component
 */
function ActiveOverrideCard({ override, onRevoke, loading }) {
  const level = AUTONOMY_LEVELS.find((l) => l.value === override.new_level);
  const expiresAt = new Date(override.expires_at);
  const hoursRemaining = Math.max(0, Math.round((expiresAt - new Date()) / (1000 * 60 * 60)));

  return (
    <div className="bg-white dark:bg-surface-800 rounded-lg border border-surface-200 dark:border-surface-700 p-4">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheckIcon className="w-5 h-5 text-brand-500" />
            <span className="font-medium text-surface-900 dark:text-surface-100">
              {override.agent_id}
            </span>
          </div>
          <div className="mt-2 flex items-center gap-2">
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${level?.color || 'bg-surface-100 text-surface-700'}`}>
              {level?.label || override.new_level}
            </span>
            <span className="text-xs text-surface-500 dark:text-surface-400">
              (was {override.previous_level})
            </span>
          </div>
        </div>
        <button
          onClick={() => onRevoke(override.agent_id)}
          disabled={loading}
          className="p-1.5 rounded-lg text-surface-400 hover:text-critical-500 hover:bg-critical-50 dark:hover:bg-critical-900/20 transition-colors"
        >
          <TrashIcon className="w-4 h-4" />
        </button>
      </div>
      <div className="mt-3 space-y-1 text-sm text-surface-500 dark:text-surface-400">
        <div className="flex items-center gap-2">
          <ClockIcon className="w-4 h-4" />
          <span>Expires in {hoursRemaining} hours</span>
        </div>
        <div className="flex items-center gap-2">
          <UserIcon className="w-4 h-4" />
          <span>Granted by {override.granted_by}</span>
        </div>
      </div>
      <div className="mt-2 text-sm text-surface-600 dark:text-surface-300 italic">
        "{override.reason}"
      </div>
    </div>
  );
}

/**
 * Rollback Form Component
 */
function RollbackForm({ onSubmit, onCancel, loading }) {
  const [actionId, setActionId] = useState('');
  const [reason, setReason] = useState('');
  const [capability, setCapability] = useState(null);
  const [checkingCapability, setCheckingCapability] = useState(false);

  const checkCapability = async () => {
    if (!actionId.trim()) return;
    setCheckingCapability(true);
    try {
      const result = await getRollbackCapability(actionId);
      setCapability(result);
    } catch (err) {
      setCapability({ can_rollback: false, reason: err.message });
    } finally {
      setCheckingCapability(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!actionId.trim() || !capability?.can_rollback) return;
    onSubmit({ actionId, reason });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
          Action ID
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={actionId}
            onChange={(e) => {
              setActionId(e.target.value);
              setCapability(null);
            }}
            placeholder="e.g., action-00000001"
            className="flex-1 px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-brand-500 focus:border-transparent"
            required
          />
          <button
            type="button"
            onClick={checkCapability}
            disabled={checkingCapability || !actionId.trim()}
            className="px-4 py-2 rounded-lg bg-surface-100 dark:bg-surface-700 text-surface-700 dark:text-surface-300 hover:bg-surface-200 dark:hover:bg-surface-600 disabled:opacity-50 transition-colors"
          >
            {checkingCapability ? 'Checking...' : 'Check'}
          </button>
        </div>
      </div>

      {capability && (
        <div className={`p-3 rounded-lg ${
          capability.can_rollback
            ? 'bg-olive-50 dark:bg-olive-900/20 border border-olive-200 dark:border-olive-800'
            : 'bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800'
        }`}>
          <div className="flex items-center gap-2">
            {capability.can_rollback ? (
              <CheckCircleIcon className="w-5 h-5 text-olive-500" />
            ) : (
              <ExclamationTriangleIcon className="w-5 h-5 text-critical-500" />
            )}
            <span className={`font-medium ${
              capability.can_rollback
                ? 'text-olive-700 dark:text-olive-300'
                : 'text-critical-700 dark:text-critical-300'
            }`}>
              {capability.can_rollback ? 'Rollback Available' : 'Rollback Not Available'}
            </span>
          </div>
          {capability.reason && (
            <p className="mt-1 text-sm text-surface-600 dark:text-surface-400">
              {capability.reason}
            </p>
          )}
          {capability.can_rollback && (
            <div className="mt-2 text-xs text-surface-500 dark:text-surface-400 space-y-1">
              {capability.has_snapshot && <div>Has state snapshot</div>}
              {capability.has_rollback_plan && <div>Has rollback plan</div>}
              {capability.expires_in_hours && (
                <div>Expires in {capability.expires_in_hours.toFixed(1)} hours</div>
              )}
            </div>
          )}
        </div>
      )}

      <div>
        <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
          Reason (optional)
        </label>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Explain why this rollback is needed..."
          rows={2}
          className="w-full px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-brand-500 focus:border-transparent"
        />
      </div>

      <div className="flex items-center gap-3 pt-2">
        <button
          type="submit"
          disabled={loading || !actionId.trim() || !capability?.can_rollback}
          className="flex-1 px-4 py-2 rounded-lg bg-amber-500 text-white font-medium hover:bg-amber-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? 'Executing...' : 'Execute Rollback'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 rounded-lg border border-surface-300 dark:border-surface-600 text-surface-700 dark:text-surface-300 hover:bg-surface-50 dark:hover:bg-surface-800 transition-colors"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

/**
 * Main Override Panel Component
 */
export default function OverridePanel() {
  const [activeTab, setActiveTab] = useState('overrides'); // 'overrides' | 'rollback'
  const [showOverrideForm, setShowOverrideForm] = useState(false);
  const [showRollbackForm, setShowRollbackForm] = useState(false);
  const [activeOverrides, setActiveOverrides] = useState([]);
  const [loading, setLoading] = useState(false);
  const [confirmRevoke, setConfirmRevoke] = useState(null);

  const { showToast } = useToast();

  // In a real implementation, this would fetch active overrides from the API
  // For now, we'll use local state that persists across form submissions

  const handleGrantOverride = async (data) => {
    setLoading(true);
    try {
      const result = await grantOverride(
        data.agentId,
        data.newLevel,
        data.reason,
        data.durationHours
      );
      setActiveOverrides((prev) => [...prev, result]);
      setShowOverrideForm(false);
      showToast('Override granted successfully', 'success');
    } catch (err) {
      showToast(err.message || 'Failed to grant override', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleRevokeOverride = async (agentId) => {
    setLoading(true);
    try {
      await revokeOverride(agentId);
      setActiveOverrides((prev) => prev.filter((o) => o.agent_id !== agentId));
      setConfirmRevoke(null);
      showToast('Override revoked successfully', 'success');
    } catch (err) {
      showToast(err.message || 'Failed to revoke override', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleExecuteRollback = async (data) => {
    setLoading(true);
    try {
      const result = await executeRollback(data.actionId, data.reason);
      setShowRollbackForm(false);
      if (result.status === 'completed') {
        showToast('Rollback completed successfully', 'success');
      } else if (result.status === 'failed') {
        showToast(`Rollback failed: ${result.error_message}`, 'error');
      } else {
        showToast(`Rollback ${result.status}: ${result.steps_completed}/${result.steps_total} steps`, 'info');
      }
    } catch (err) {
      showToast(err.message || 'Failed to execute rollback', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
          Human Override Controls
        </h1>
        <p className="mt-1 text-sm text-surface-500 dark:text-surface-400">
          Grant temporary autonomy overrides and execute rollbacks
        </p>
      </div>

      {/* Warning Banner */}
      <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <ExclamationTriangleIcon className="w-5 h-5 text-amber-500 mt-0.5" />
          <div>
            <h3 className="font-medium text-amber-800 dark:text-amber-200">
              Use with caution
            </h3>
            <p className="mt-1 text-sm text-amber-700 dark:text-amber-300">
              Overrides and rollbacks are powerful controls that bypass normal safety checks.
              All actions are logged for audit purposes.
            </p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-surface-200 dark:border-surface-700">
        <nav className="flex gap-4">
          <button
            onClick={() => setActiveTab('overrides')}
            className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'overrides'
                ? 'border-brand-500 text-brand-600 dark:text-brand-400'
                : 'border-transparent text-surface-500 hover:text-surface-700 dark:text-surface-400 dark:hover:text-surface-200'
            }`}
          >
            <div className="flex items-center gap-2">
              <ShieldCheckIcon className="w-4 h-4" />
              Autonomy Overrides
            </div>
          </button>
          <button
            onClick={() => setActiveTab('rollback')}
            className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'rollback'
                ? 'border-brand-500 text-brand-600 dark:text-brand-400'
                : 'border-transparent text-surface-500 hover:text-surface-700 dark:text-surface-400 dark:hover:text-surface-200'
            }`}
          >
            <div className="flex items-center gap-2">
              <ArrowUturnLeftIcon className="w-4 h-4" />
              Rollback Actions
            </div>
          </button>
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'overrides' && (
        <div className="space-y-4">
          {/* Action Button */}
          {!showOverrideForm && (
            <button
              onClick={() => setShowOverrideForm(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-500 text-white font-medium hover:bg-brand-600 transition-colors"
            >
              <PlusIcon className="w-4 h-4" />
              Grant New Override
            </button>
          )}

          {/* Override Form */}
          {showOverrideForm && (
            <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-6">
              <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4">
                Grant Temporary Override
              </h3>
              <OverrideForm
                onSubmit={handleGrantOverride}
                onCancel={() => setShowOverrideForm(false)}
                loading={loading}
              />
            </div>
          )}

          {/* Active Overrides */}
          <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)]">
            <div className="p-4 border-b border-surface-200 dark:border-surface-700">
              <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
                Active Overrides
              </h3>
            </div>
            <div className="p-4">
              {activeOverrides.length === 0 ? (
                <div className="text-center py-8 text-surface-500 dark:text-surface-400">
                  <ShieldCheckIcon className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p>No active overrides</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {activeOverrides.map((override) => (
                    <ActiveOverrideCard
                      key={override.agent_id}
                      override={override}
                      onRevoke={(agentId) => setConfirmRevoke(agentId)}
                      loading={loading}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'rollback' && (
        <div className="space-y-4">
          {/* Action Button */}
          {!showRollbackForm && (
            <button
              onClick={() => setShowRollbackForm(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500 text-white font-medium hover:bg-amber-600 transition-colors"
            >
              <ArrowUturnLeftIcon className="w-4 h-4" />
              Execute Rollback
            </button>
          )}

          {/* Rollback Form */}
          {showRollbackForm && (
            <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-6">
              <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4">
                Execute Action Rollback
              </h3>
              <RollbackForm
                onSubmit={handleExecuteRollback}
                onCancel={() => setShowRollbackForm(false)}
                loading={loading}
              />
            </div>
          )}

          {/* Info Box */}
          <div className="bg-surface-50 dark:bg-surface-900/50 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <InformationCircleIcon className="w-5 h-5 text-surface-400 mt-0.5" />
              <div className="text-sm text-surface-600 dark:text-surface-400">
                <p className="font-medium text-surface-700 dark:text-surface-300">
                  About Rollbacks
                </p>
                <ul className="mt-2 space-y-1 list-disc list-inside">
                  <li>Class A actions have automatic state snapshots</li>
                  <li>Class B actions have rollback plans but may require manual steps</li>
                  <li>Class C actions are irreversible and cannot be rolled back</li>
                  <li>Snapshots expire after the configured retention period</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Confirm Revoke Dialog */}
      <ConfirmDialog
        isOpen={!!confirmRevoke}
        onClose={() => setConfirmRevoke(null)}
        onConfirm={() => handleRevokeOverride(confirmRevoke)}
        title="Revoke Override"
        message={`Are you sure you want to revoke the override for ${confirmRevoke}? The agent will return to its normal autonomy level.`}
        confirmText="Revoke"
        confirmVariant="danger"
      />
    </div>
  );
}
