/**
 * Project Aura - Model Router Settings Component
 *
 * Dashboard for LLM model routing configuration and analytics.
 * Provides visibility into model selection decisions, cost savings, and routing rules.
 *
 * Issue #31: Model Router Dashboard
 */

import { useState, useEffect, useCallback } from 'react';
import {
  Cog6ToothIcon,
  ArrowPathIcon,
  BanknotesIcon,
  ChartBarIcon,
  BeakerIcon,
  TableCellsIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';

import {
  getRouterStats,
  getRoutingRules,
  updateRoutingRule,
  createRoutingRule,
  deleteRoutingRule,
  updateABTestConfig,
  refreshRouterConfig,
  formatCost,
  formatNumber,
  MODEL_INFO,
  COMPLEXITY_STYLES,
  DEFAULT_STATS,
  DEFAULT_RULES,
} from '../../services/modelRouterApi';
import { useToast } from '../ui/Toast';

// ============================================================================
// Sub-Components
// ============================================================================

/**
 * Animated Sparkline chart for trend visualization
 */
function Sparkline({ data, color = 'olive', className = '', animate = true }) {
  const [isVisible, setIsVisible] = useState(!animate);

  useEffect(() => {
    if (animate) {
      const timer = setTimeout(() => setIsVisible(true), 100);
      return () => clearTimeout(timer);
    }
  }, [animate]);

  if (!data || data.length < 2) return null;

  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;

  const points = data.map((value, index) => {
    const x = (index / (data.length - 1)) * 100;
    const y = 100 - ((value - min) / range) * 100;
    return `${x},${y}`;
  }).join(' ');

  const colorClasses = {
    aura: 'stroke-aura-500 dark:stroke-aura-400',
    olive: 'stroke-olive-500 dark:stroke-olive-400',
    critical: 'stroke-critical-500 dark:stroke-critical-400',
    warning: 'stroke-warning-500 dark:stroke-warning-400',
  };

  // Calculate path length for animation
  const pathLength = 1000;

  return (
    <svg
      viewBox="0 0 100 40"
      className={`w-full h-10 ${className}`}
      preserveAspectRatio="none"
      role="img"
      aria-label={`Trend chart showing values from ${min.toFixed(1)}% to ${max.toFixed(1)}%`}
    >
      <polyline
        points={points}
        fill="none"
        className={colorClasses[color] || colorClasses.olive}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        style={animate ? {
          strokeDasharray: pathLength,
          strokeDashoffset: isVisible ? 0 : pathLength,
          transition: 'stroke-dashoffset 600ms ease-out',
        } : undefined}
      />
    </svg>
  );
}

/**
 * Error state component with retry
 */
function _ErrorState({ message, onRetry }) {
  return (
    <div className="flex items-start gap-3 p-4 bg-critical-50 dark:bg-critical-900/30 border border-critical-200 dark:border-critical-800 rounded-lg">
      <ExclamationTriangleIcon className="h-5 w-5 text-critical-600 dark:text-critical-400 flex-shrink-0 mt-0.5" />
      <div className="flex-1">
        <h4 className="font-medium text-critical-800 dark:text-critical-200">
          Failed to load data
        </h4>
        <p className="text-sm text-critical-700 dark:text-critical-300 mt-1">
          {message || 'Unable to connect to the model router service. Please try again.'}
        </p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="mt-3 text-sm font-medium text-critical-700 dark:text-critical-300 hover:underline focus:outline-none focus:ring-2 focus:ring-critical-500 focus:ring-offset-2 rounded"
          >
            Retry
          </button>
        )}
      </div>
    </div>
  );
}

/**
 * Skeleton loader for cards
 */
function CardSkeleton({ className = '' }) {
  return (
    <div className={`bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-6 animate-pulse ${className}`}>
      <div className="flex items-center gap-2 mb-4">
        <div className="w-10 h-10 bg-surface-200 dark:bg-surface-700 rounded-lg" />
        <div className="w-24 h-4 bg-surface-200 dark:bg-surface-700 rounded" />
      </div>
      <div className="w-20 h-12 bg-surface-200 dark:bg-surface-700 rounded mb-2" />
      <div className="w-32 h-5 bg-surface-200 dark:bg-surface-700 rounded mb-4" />
      <div className="w-full h-10 bg-surface-200 dark:bg-surface-700 rounded" />
    </div>
  );
}

/**
 * Table skeleton loader
 */
function TableSkeleton({ rows = 5 }) {
  return (
    <div className="space-y-2">
      {[...Array(rows)].map((_, i) => (
        <div key={i} className="h-14 bg-surface-100 dark:bg-surface-700/50 rounded animate-pulse" />
      ))}
    </div>
  );
}

/**
 * Cost Savings Card Component
 */
function CostSavingsCard({ data, loading }) {
  if (loading) {
    return <CardSkeleton />;
  }

  const { percentage, amount, trend } = data || {};

  return (
    <div
      className="bg-gradient-to-br from-olive-50 to-white dark:from-olive-900/20 dark:to-surface-800 rounded-xl border border-olive-200 dark:border-olive-800 p-6 shadow-card"
      role="region"
      aria-labelledby="cost-savings-heading"
    >
      <div className="flex items-center gap-2 mb-4">
        <div className="p-2 rounded-lg bg-olive-100 dark:bg-olive-900/30">
          <BanknotesIcon className="h-5 w-5 text-olive-600 dark:text-olive-400" />
        </div>
        <h3 id="cost-savings-heading" className="text-sm font-medium text-surface-600 dark:text-surface-400">
          Cost Savings
        </h3>
      </div>
      <p className="text-5xl font-bold text-surface-900 dark:text-surface-50" aria-live="polite">
        {percentage || 0}%
      </p>
      <p className="text-lg font-semibold text-olive-700 dark:text-olive-400 mt-1">
        {formatCost(amount || 0)} saved
      </p>
      <p className="text-sm text-surface-500 dark:text-surface-400 mt-1">
        This month vs baseline
      </p>
      {trend && trend.length > 1 && (
        <div className="mt-4 -mx-1">
          <Sparkline data={trend} color="olive" />
        </div>
      )}
    </div>
  );
}

/**
 * Model Distribution Chart Component
 */
function ModelDistributionChart({ data, loading }) {
  if (loading) {
    return <CardSkeleton />;
  }

  const { distribution = [], total_requests = 0 } = data || {};

  return (
    <div
      className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-6 shadow-card"
      role="region"
      aria-labelledby="distribution-heading"
    >
      <div className="flex items-center gap-2 mb-4">
        <div className="p-2 rounded-lg bg-aura-100 dark:bg-aura-900/30">
          <ChartBarIcon className="h-5 w-5 text-aura-600 dark:text-aura-400" />
        </div>
        <h3 id="distribution-heading" className="text-sm font-medium text-surface-600 dark:text-surface-400">
          Model Distribution
        </h3>
      </div>

      <div className="space-y-4">
        {distribution.map((item) => (
          <div key={item.tier} className="space-y-1">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium text-surface-900 dark:text-surface-100">
                {item.model}
              </span>
              <span className="text-surface-500 dark:text-surface-400">
                {item.percentage}% ({formatNumber(item.count)})
              </span>
            </div>
            <div className="h-3 bg-surface-100 dark:bg-surface-700 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${item.percentage}%`,
                  backgroundColor: item.color,
                }}
                role="progressbar"
                aria-valuenow={item.percentage}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`${item.model}: ${item.percentage}% of requests`}
              />
            </div>
          </div>
        ))}
      </div>

      <p className="text-xs text-surface-500 dark:text-surface-400 mt-4 text-right">
        Total: {formatNumber(total_requests)} requests
      </p>
    </div>
  );
}

/**
 * Complexity Badge Component
 */
function ComplexityBadge({ complexity }) {
  const style = COMPLEXITY_STYLES[complexity] || COMPLEXITY_STYLES.medium;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${style.bg} ${style.text}`}>
      {style.label}
    </span>
  );
}

/**
 * Routing Rules Table Component
 */
function RoutingRulesTable({ rules, loading, onUpdate, onCreate, onDelete: _onDelete }) {
  const [editingId, setEditingId] = useState(null);
  const [editValues, setEditValues] = useState({});
  const [isCreating, setIsCreating] = useState(false);
  const [newRule, setNewRule] = useState({ task_type: '', complexity: 'medium', tier: 'accurate', description: '' });
  const [error, setError] = useState(null);

  const handleEdit = (rule) => {
    setEditingId(rule.id);
    setEditValues({ complexity: rule.complexity, tier: rule.tier, enabled: rule.enabled });
    setError(null);
  };

  const handleSave = async (ruleId) => {
    try {
      await onUpdate(ruleId, editValues);
      setEditingId(null);
      setEditValues({});
    } catch (err) {
      setError(err.message);
    }
  };

  const handleCancel = () => {
    setEditingId(null);
    setEditValues({});
    setError(null);
  };

  const handleCreate = async () => {
    if (!newRule.task_type.trim()) {
      setError('Task type is required');
      return;
    }
    try {
      await onCreate(newRule);
      setIsCreating(false);
      setNewRule({ task_type: '', complexity: 'medium', tier: 'accurate', description: '' });
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  };

  if (loading) {
    return (
      <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">Routing Rules</h3>
        </div>
        <TableSkeleton rows={5} />
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] overflow-hidden">
      <div className="flex items-center justify-between px-6 py-4 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center gap-2">
          <TableCellsIcon className="h-5 w-5 text-surface-500 dark:text-surface-400" />
          <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">Routing Rules</h3>
        </div>
        <button
          onClick={() => setIsCreating(true)}
          className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium bg-aura-600 text-white rounded-lg hover:bg-aura-700 transition-colors"
        >
          + Add Rule
        </button>
      </div>

      {error && (
        <div className="px-6 py-3 bg-critical-50 dark:bg-critical-900/30 border-b border-critical-200 dark:border-critical-800">
          <div className="flex items-center gap-2 text-sm text-critical-700 dark:text-critical-300">
            <ExclamationTriangleIcon className="h-4 w-4" />
            {error}
          </div>
        </div>
      )}

      {/* Desktop Table View - Hidden on mobile */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full" role="table" aria-label="Routing Rules Configuration">
          <thead className="bg-surface-50 dark:bg-surface-800/50">
            <tr>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wider">
                Task Type
              </th>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wider">
                Complexity
              </th>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wider">
                Model
              </th>
              <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wider">
                Cost/1K
              </th>
              <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-200 dark:divide-surface-700">
            {isCreating && (
              <tr className="bg-aura-50 dark:bg-aura-900/20 border-l-4 border-aura-500">
                <td className="px-6 py-4">
                  <input
                    type="text"
                    value={newRule.task_type}
                    onChange={(e) => setNewRule({ ...newRule, task_type: e.target.value })}
                    placeholder="task_type_name"
                    className="w-full px-3 py-1.5 text-sm border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500"
                  />
                </td>
                <td className="px-6 py-4">
                  <select
                    value={newRule.complexity}
                    onChange={(e) => setNewRule({ ...newRule, complexity: e.target.value })}
                    className="px-3 py-1.5 text-sm border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
                  >
                    <option value="simple">Simple</option>
                    <option value="medium">Medium</option>
                    <option value="complex">Complex</option>
                  </select>
                </td>
                <td className="px-6 py-4">
                  <select
                    value={newRule.tier}
                    onChange={(e) => setNewRule({ ...newRule, tier: e.target.value })}
                    className="px-3 py-1.5 text-sm border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
                  >
                    <option value="fast">Claude Haiku</option>
                    <option value="accurate">Claude Sonnet</option>
                    <option value="maximum">Claude Opus</option>
                  </select>
                </td>
                <td className="px-6 py-4 text-right font-mono text-sm text-surface-500">
                  {formatCost(MODEL_INFO[newRule.tier]?.costPer1k || 0, 5)}
                </td>
                <td className="px-6 py-4 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <button
                      onClick={handleCreate}
                      className="px-3 py-1.5 text-sm font-medium bg-aura-600 text-white rounded-lg hover:bg-aura-700"
                    >
                      Create
                    </button>
                    <button
                      onClick={() => { setIsCreating(false); setError(null); }}
                      className="px-3 py-1.5 text-sm font-medium text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg"
                    >
                      Cancel
                    </button>
                  </div>
                </td>
              </tr>
            )}
            {(rules || []).map((rule) => (
              <tr
                key={rule.id}
                className={`hover:bg-surface-50 dark:hover:bg-surface-700/50 transition-colors ${
                  editingId === rule.id ? 'bg-aura-50 dark:bg-aura-900/20 border-l-4 border-aura-500' : ''
                } ${!rule.enabled ? 'opacity-50' : ''}`}
              >
                <td className="px-6 py-4">
                  <div>
                    <code className="text-sm font-mono text-surface-700 dark:text-surface-300">
                      {rule.task_type}
                    </code>
                    {rule.description && (
                      <p className="text-xs text-surface-500 dark:text-surface-400 mt-0.5">
                        {rule.description}
                      </p>
                    )}
                  </div>
                </td>
                <td className="px-6 py-4">
                  {editingId === rule.id ? (
                    <select
                      value={editValues.complexity}
                      onChange={(e) => setEditValues({ ...editValues, complexity: e.target.value })}
                      className="px-2 py-1 text-sm border border-surface-300 dark:border-surface-600 rounded bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100"
                    >
                      <option value="simple">Simple</option>
                      <option value="medium">Medium</option>
                      <option value="complex">Complex</option>
                    </select>
                  ) : (
                    <ComplexityBadge complexity={rule.complexity} />
                  )}
                </td>
                <td className="px-6 py-4">
                  {editingId === rule.id ? (
                    <select
                      value={editValues.tier}
                      onChange={(e) => setEditValues({ ...editValues, tier: e.target.value })}
                      className="px-2 py-1 text-sm border border-surface-300 dark:border-surface-600 rounded bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100"
                    >
                      <option value="fast">Claude Haiku</option>
                      <option value="accurate">Claude Sonnet</option>
                      <option value="maximum">Claude Opus</option>
                    </select>
                  ) : (
                    <span className="text-sm text-surface-900 dark:text-surface-100">
                      {rule.model}
                    </span>
                  )}
                </td>
                <td className="px-6 py-4 text-right">
                  <span className="font-mono text-sm text-surface-500 dark:text-surface-400">
                    {formatCost(editingId === rule.id ? MODEL_INFO[editValues.tier]?.costPer1k || 0 : rule.cost_per_1k, 5)}
                  </span>
                </td>
                <td className="px-6 py-4 text-right">
                  {editingId === rule.id ? (
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => handleSave(rule.id)}
                        className="px-3 py-1.5 text-sm font-medium bg-aura-600 text-white rounded-lg hover:bg-aura-700"
                      >
                        Save
                      </button>
                      <button
                        onClick={handleCancel}
                        className="px-3 py-1.5 text-sm font-medium text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => handleEdit(rule)}
                      className="px-3 py-1.5 text-sm font-medium text-aura-600 dark:text-aura-400 hover:bg-aura-50 dark:hover:bg-aura-900/20 rounded-lg transition-colors"
                    >
                      Edit
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile Card View - Shown only on mobile */}
      <div className="md:hidden p-4 space-y-3">
        {isCreating && (
          <div className="bg-aura-50 dark:bg-aura-900/20 border border-aura-200 dark:border-aura-800 rounded-lg p-4">
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Task Type</label>
                <input
                  type="text"
                  value={newRule.task_type}
                  onChange={(e) => setNewRule({ ...newRule, task_type: e.target.value })}
                  placeholder="task_type_name"
                  className="w-full px-3 py-2 text-sm border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Complexity</label>
                  <select
                    value={newRule.complexity}
                    onChange={(e) => setNewRule({ ...newRule, complexity: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500"
                  >
                    <option value="simple">Simple</option>
                    <option value="medium">Medium</option>
                    <option value="complex">Complex</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Model</label>
                  <select
                    value={newRule.tier}
                    onChange={(e) => setNewRule({ ...newRule, tier: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500"
                  >
                    <option value="fast">Claude Haiku</option>
                    <option value="accurate">Claude Sonnet</option>
                    <option value="maximum">Claude Opus</option>
                  </select>
                </div>
              </div>
              <div className="flex gap-2 pt-2">
                <button
                  onClick={handleCreate}
                  className="flex-1 py-2 text-sm font-medium bg-aura-600 text-white rounded-lg hover:bg-aura-700"
                >
                  Create
                </button>
                <button
                  onClick={() => { setIsCreating(false); setError(null); }}
                  className="flex-1 py-2 text-sm font-medium text-surface-600 dark:text-surface-400 border border-surface-200 dark:border-surface-600 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-700"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
        {(rules || []).map((rule) => (
          <div
            key={rule.id}
            className={`bg-white dark:bg-surface-800 rounded-lg border border-surface-200 dark:border-surface-700 p-4 ${
              !rule.enabled ? 'opacity-50' : ''
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <code className="text-sm font-mono font-medium text-surface-900 dark:text-surface-100 truncate max-w-[180px]">
                {rule.task_type}
              </code>
              <ComplexityBadge complexity={rule.complexity} />
            </div>
            {rule.description && (
              <p className="text-xs text-surface-500 dark:text-surface-400 mb-3">
                {rule.description}
              </p>
            )}
            <div className="flex items-center justify-between text-sm text-surface-600 dark:text-surface-400 mb-3">
              <span>Model: {rule.model}</span>
              <span className="font-mono">{formatCost(rule.cost_per_1k, 5)}</span>
            </div>
            <button
              onClick={() => handleEdit(rule)}
              className="w-full py-2 text-sm text-aura-600 dark:text-aura-400 border border-aura-200 dark:border-aura-800 rounded-lg hover:bg-aura-50 dark:hover:bg-aura-900/20 transition-colors"
            >
              Edit Rule
            </button>
          </div>
        ))}
      </div>

      {(!rules || rules.length === 0) && !isCreating && (
        <div className="text-center py-12">
          <Cog6ToothIcon className="h-12 w-12 text-surface-300 dark:text-surface-600 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-surface-900 dark:text-surface-100 mb-2">
            No routing rules configured
          </h3>
          <p className="text-surface-500 dark:text-surface-400 mb-6 max-w-md mx-auto">
            Create routing rules to automatically select the optimal model based on task complexity.
          </p>
          <button
            onClick={() => setIsCreating(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-aura-600 text-white rounded-lg hover:bg-aura-700 transition-colors"
          >
            Create First Rule
          </button>
        </div>
      )}
    </div>
  );
}

/**
 * A/B Testing Toggle Component
 */
function ABTestingSection({ config, loading, onUpdate }) {
  const [localConfig, setLocalConfig] = useState(config || {});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (config) {
      setLocalConfig(config);
    }
  }, [config]);

  const handleToggle = async () => {
    setSaving(true);
    try {
      await onUpdate({ enabled: !localConfig.enabled });
      setLocalConfig(prev => ({ ...prev, enabled: !prev.enabled }));
    } catch (err) {
      console.error('Failed to toggle A/B test:', err);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <CardSkeleton />;
  }

  return (
    <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-aura-100 dark:bg-aura-900/30">
            <BeakerIcon className="h-5 w-5 text-aura-600 dark:text-aura-400" />
          </div>
          <div>
            <h3 className="font-medium text-surface-900 dark:text-surface-100">A/B Testing</h3>
            <p className="text-sm text-surface-500 dark:text-surface-400">
              Run experiments to optimize model selection
            </p>
          </div>
        </div>

        <button
          onClick={handleToggle}
          disabled={saving}
          className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2 disabled:opacity-50 ${
            localConfig.enabled ? 'bg-aura-600' : 'bg-surface-200 dark:bg-surface-600'
          }`}
          role="switch"
          aria-checked={localConfig.enabled}
          aria-label="Toggle A/B Testing"
        >
          <span
            className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
              localConfig.enabled ? 'translate-x-5' : 'translate-x-0'
            }`}
          />
        </button>
      </div>

      {localConfig.enabled && (
        <div className="mt-6 pt-6 border-t border-surface-200 dark:border-surface-700">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                Experiment Name
              </label>
              <p className="text-sm text-surface-900 dark:text-surface-100">
                {localConfig.experiment_id || 'No experiment active'}
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                Status
              </label>
              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                localConfig.status === 'active'
                  ? 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400'
                  : 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-400'
              }`}>
                {localConfig.status || 'inactive'}
              </span>
            </div>
            <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                Control Tier
              </label>
              <p className="text-sm text-surface-900 dark:text-surface-100">
                {MODEL_INFO[localConfig.control_tier]?.name || 'Claude Sonnet'}
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                Treatment Tier
              </label>
              <p className="text-sm text-surface-900 dark:text-surface-100">
                {MODEL_INFO[localConfig.treatment_tier]?.name || 'Claude Haiku'}
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                Traffic Split
              </label>
              <p className="text-sm text-surface-900 dark:text-surface-100">
                {((localConfig.traffic_split || 0.5) * 100).toFixed(0)}% treatment / {((1 - (localConfig.traffic_split || 0.5)) * 100).toFixed(0)}% control
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function ModelRouterSettings({ onSuccess, onError }) {
  const [stats, setStats] = useState(null);
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [timeRange, setTimeRange] = useState('30d');

  const { toast } = useToast();

  const loadData = useCallback(async () => {
    try {
      const [statsData, rulesData] = await Promise.all([
        getRouterStats(timeRange),
        getRoutingRules(),
      ]);
      setStats(statsData);
      setRules(rulesData);
    } catch (err) {
      console.error('Failed to load model router data:', err);
      onError?.(`Failed to load data: ${err.message}`);
      // Use defaults
      setStats(DEFAULT_STATS);
      setRules(DEFAULT_RULES);
    } finally {
      setLoading(false);
    }
  }, [timeRange, onError]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await refreshRouterConfig();
      await loadData();
      toast.success('Model Router refreshed');
      onSuccess?.('Configuration refreshed');
    } catch (err) {
      toast.error('Failed to refresh Model Router');
      onError?.(`Failed to refresh: ${err.message}`);
    } finally {
      setRefreshing(false);
    }
  };

  const handleRuleUpdate = async (ruleId, updates) => {
    const updated = await updateRoutingRule(ruleId, updates);
    setRules(prev => prev.map(r => r.id === ruleId ? updated : r));
    onSuccess?.('Rule updated successfully');
  };

  const handleRuleCreate = async (rule) => {
    const created = await createRoutingRule(rule);
    setRules(prev => [...prev, created]);
    onSuccess?.('Rule created successfully');
  };

  const handleRuleDelete = async (ruleId) => {
    await deleteRoutingRule(ruleId);
    setRules(prev => prev.filter(r => r.id !== ruleId));
    onSuccess?.('Rule deleted successfully');
  };

  const handleABTestUpdate = async (updates) => {
    const updated = await updateABTestConfig(updates);
    setStats(prev => ({ ...prev, ab_test: updated }));
    onSuccess?.('A/B test configuration updated');
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-aura-100 dark:bg-aura-900/30">
            <Cog6ToothIcon className="h-6 w-6 text-aura-600 dark:text-aura-400" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-surface-900 dark:text-surface-100">
              Model Router
            </h2>
            <p className="text-sm text-surface-500 dark:text-surface-400">
              Configure LLM model selection and view routing analytics
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            className="px-3 py-2 text-sm border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
          >
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="90d">Last 90 days</option>
          </select>

          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-2 px-4 py-2 text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-100 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors disabled:opacity-50"
          >
            <ArrowPathIcon className={`h-5 w-5 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Info Banner */}
      <div className="flex items-start gap-3 p-4 bg-aura-50 dark:bg-aura-900/20 border border-aura-200 dark:border-aura-800 rounded-lg">
        <InformationCircleIcon className="h-5 w-5 text-aura-600 dark:text-aura-400 flex-shrink-0 mt-0.5" />
        <div>
          <h4 className="font-medium text-aura-800 dark:text-aura-200">Intelligent Model Routing</h4>
          <p className="text-sm text-aura-700 dark:text-aura-300 mt-1">
            The model router automatically selects the optimal LLM based on task complexity to balance cost and quality.
            Simple tasks use Haiku (~40% of traffic), standard tasks use Sonnet (~55%), and complex tasks use Opus (~5%).
          </p>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <CostSavingsCard data={stats?.cost_savings} loading={loading} />
        <ModelDistributionChart data={stats?.distribution} loading={loading} />
      </div>

      {/* Routing Rules */}
      <RoutingRulesTable
        rules={rules}
        loading={loading}
        onUpdate={handleRuleUpdate}
        onCreate={handleRuleCreate}
        onDelete={handleRuleDelete}
      />

      {/* A/B Testing */}
      <ABTestingSection
        config={stats?.ab_test}
        loading={loading}
        onUpdate={handleABTestUpdate}
      />
    </div>
  );
}
