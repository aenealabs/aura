/**
 * Project Aura - Rate Limiting Settings Component
 *
 * Configure API rate limits per endpoint and user.
 */

import { useState, useEffect } from 'react';
import {
  ChartBarIcon,
  ArrowPathIcon,
  InformationCircleIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  UserIcon,
  GlobeAltIcon,
  ShieldCheckIcon,
  ChevronDownIcon,
  ChevronUpIcon,
} from '@heroicons/react/24/outline';

// Rate limit tier configuration
const RATE_LIMIT_TIERS = {
  public: {
    label: 'Public',
    description: 'Unauthenticated requests',
    color: 'surface',
    defaults: { requests_per_minute: 30, requests_per_hour: 200 },
    icon: GlobeAltIcon,
  },
  standard: {
    label: 'Standard',
    description: 'Regular authenticated users',
    color: 'aura',
    defaults: { requests_per_minute: 60, requests_per_hour: 1000 },
    icon: UserIcon,
  },
  admin: {
    label: 'Admin',
    description: 'Administrative operations',
    color: 'warning',
    defaults: { requests_per_minute: 5, requests_per_hour: 50 },
    icon: ShieldCheckIcon,
  },
  critical: {
    label: 'Critical',
    description: 'Security-sensitive operations',
    color: 'critical',
    defaults: { requests_per_minute: 2, requests_per_hour: 20 },
    icon: ExclamationTriangleIcon,
  },
};

// Endpoint groups for rate limiting
const ENDPOINT_GROUPS = [
  {
    name: 'Authentication',
    endpoints: [
      { path: '/api/v1/auth/login', tier: 'public', description: 'User login' },
      { path: '/api/v1/auth/refresh', tier: 'standard', description: 'Token refresh' },
      { path: '/api/v1/auth/logout', tier: 'standard', description: 'User logout' },
    ],
  },
  {
    name: 'Autonomy',
    endpoints: [
      { path: '/api/v1/autonomy/policies', tier: 'standard', description: 'List policies' },
      { path: '/api/v1/autonomy/policies/{id}/toggle', tier: 'critical', description: 'Toggle HITL' },
      { path: '/api/v1/autonomy/check', tier: 'standard', description: 'Check HITL requirement' },
    ],
  },
  {
    name: 'Orchestrator',
    endpoints: [
      { path: '/api/v1/orchestrator/settings', tier: 'standard', description: 'Get settings' },
      { path: '/api/v1/orchestrator/settings/switch', tier: 'critical', description: 'Switch mode' },
    ],
  },
  {
    name: 'Environments',
    endpoints: [
      { path: '/api/v1/environments', tier: 'standard', description: 'List environments' },
      { path: '/api/v1/environments/create', tier: 'admin', description: 'Create environment' },
      { path: '/api/v1/environments/{id}/terminate', tier: 'admin', description: 'Terminate environment' },
    ],
  },
  {
    name: 'Agents',
    endpoints: [
      { path: '/api/v1/agents', tier: 'standard', description: 'List agents' },
      { path: '/api/v1/agents/{id}/config', tier: 'admin', description: 'Update agent config' },
      { path: '/api/v1/agents/{id}/restart', tier: 'critical', description: 'Restart agent' },
    ],
  },
];

const COLOR_STYLES = {
  surface: 'bg-surface-100 text-surface-700 dark:bg-surface-700 dark:text-surface-300',
  aura: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
  warning: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
  critical: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
};

/**
 * Rate Limit Tier Card Component
 */
function RateLimitTierCard({ tier: _tier, config, limits, onChange, isLoading }) {
  const Icon = config.icon || ChartBarIcon;
  const colorClass = COLOR_STYLES[config.color] || COLOR_STYLES.aura;

  return (
    <div className="bg-white dark:bg-surface-800 rounded-lg border border-surface-200 dark:border-surface-700 p-4">
      <div className="flex items-center gap-3 mb-4">
        <div className={`p-2 rounded-lg ${colorClass}`}>
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <h4 className="font-medium text-surface-900 dark:text-surface-100">
            {config.label}
          </h4>
          <p className="text-xs text-surface-500 dark:text-surface-400">
            {config.description}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">
            Per Minute
          </label>
          <input
            type="number"
            min={1}
            max={1000}
            value={limits.requests_per_minute}
            onChange={(e) => onChange({ ...limits, requests_per_minute: parseInt(e.target.value) })}
            disabled={isLoading}
            className="w-full px-3 py-2 text-sm border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 disabled:opacity-50"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">
            Per Hour
          </label>
          <input
            type="number"
            min={1}
            max={10000}
            value={limits.requests_per_hour}
            onChange={(e) => onChange({ ...limits, requests_per_hour: parseInt(e.target.value) })}
            disabled={isLoading}
            className="w-full px-3 py-2 text-sm border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 disabled:opacity-50"
          />
        </div>
      </div>
    </div>
  );
}

/**
 * Endpoint Group Panel Component
 */
function EndpointGroupPanel({ group, isExpanded, onToggle }) {
  return (
    <div className="border border-surface-200 dark:border-surface-700 rounded-lg">
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-surface-50 dark:hover:bg-surface-700/50 transition-colors"
      >
        <span className="font-medium text-surface-900 dark:text-surface-100">
          {group.name}
        </span>
        <div className="flex items-center gap-2">
          <span className="text-xs text-surface-500 dark:text-surface-400">
            {group.endpoints.length} endpoints
          </span>
          {isExpanded ? (
            <ChevronUpIcon className="h-4 w-4 text-surface-400" />
          ) : (
            <ChevronDownIcon className="h-4 w-4 text-surface-400" />
          )}
        </div>
      </button>

      {isExpanded && (
        <div className="px-4 pb-4 border-t border-surface-200 dark:border-surface-700">
          <table className="w-full mt-3">
            <thead>
              <tr className="text-xs text-surface-500 dark:text-surface-400">
                <th className="text-left py-2 font-medium">Endpoint</th>
                <th className="text-left py-2 font-medium">Description</th>
                <th className="text-left py-2 font-medium">Tier</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-100 dark:divide-surface-700/50">
              {group.endpoints.map((endpoint, idx) => {
                const tierConfig = RATE_LIMIT_TIERS[endpoint.tier];
                return (
                  <tr key={idx}>
                    <td className="py-2 pr-4">
                      <code className="text-xs font-mono text-surface-600 dark:text-surface-400">
                        {endpoint.path}
                      </code>
                    </td>
                    <td className="py-2 pr-4 text-sm text-surface-600 dark:text-surface-400">
                      {endpoint.description}
                    </td>
                    <td className="py-2">
                      <span className={`
                        px-2 py-0.5 text-xs font-medium rounded-full
                        ${COLOR_STYLES[tierConfig?.color || 'aura']}
                      `}>
                        {tierConfig?.label || endpoint.tier}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/**
 * Current Status Display Component
 */
function RateLimitStatusDisplay({ status }) {
  if (!status) return null;

  return (
    <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-6">
      <div className="flex items-center gap-2 mb-4">
        <ChartBarIcon className="h-5 w-5 text-aura-600 dark:text-aura-400" />
        <h3 className="font-semibold text-surface-900 dark:text-surface-100">
          Current Usage
        </h3>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {Object.entries(status.tiers || {}).map(([tier, data]) => {
          const config = RATE_LIMIT_TIERS[tier];
          if (!config) return null;

          const usagePercent = (data.current / data.limit) * 100;

          return (
            <div key={tier} className="text-center">
              <p className="text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                {config.label}
              </p>
              <div className="relative pt-1">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-surface-500 dark:text-surface-400">
                    {data.current} / {data.limit}
                  </span>
                </div>
                <div className="h-2 bg-surface-100 dark:bg-surface-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${
                      usagePercent >= 90 ? 'bg-critical-500' :
                      usagePercent >= 70 ? 'bg-warning-500' : 'bg-olive-500'
                    }`}
                    style={{ width: `${Math.min(usagePercent, 100)}%` }}
                  />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {status.last_updated && (
        <p className="text-xs text-surface-500 dark:text-surface-400 text-right mt-4">
          Last updated: {new Date(status.last_updated).toLocaleTimeString()}
        </p>
      )}
    </div>
  );
}

/**
 * Main Rate Limiting Settings Component
 */
export default function RateLimitingSettings({ onSuccess, onError }) {
  const [limits, setLimits] = useState(() => {
    const initial = {};
    Object.entries(RATE_LIMIT_TIERS).forEach(([tier, config]) => {
      initial[tier] = { ...config.defaults };
    });
    return initial;
  });
  const [status, setStatus] = useState(null);
  const [_loading, _setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [expandedGroup, setExpandedGroup] = useState(null);

  useEffect(() => {
    loadStatus();
  }, []);

  const loadStatus = async () => {
    // In real implementation, this would fetch current rate limit status
    setStatus({
      tiers: {
        public: { current: 15, limit: 30 },
        standard: { current: 42, limit: 60 },
        admin: { current: 2, limit: 5 },
        critical: { current: 0, limit: 2 },
      },
      last_updated: new Date().toISOString(),
    });
  };

  const handleTierChange = (tier, newLimits) => {
    setLimits(prev => ({
      ...prev,
      [tier]: newLimits,
    }));
    setHasChanges(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      // In real implementation, this would save to API
      await new Promise(resolve => setTimeout(resolve, 1000));
      setHasChanges(false);
      onSuccess?.('Rate limits updated successfully');
    } catch (err) {
      onError?.(`Failed to update rate limits: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    const initial = {};
    Object.entries(RATE_LIMIT_TIERS).forEach(([tier, config]) => {
      initial[tier] = { ...config.defaults };
    });
    setLimits(initial);
    setHasChanges(false);
  };

  return (
    <div className="space-y-6">
      {/* Info Banner */}
      <div className="flex items-start gap-3 p-4 bg-aura-50 dark:bg-aura-900/20 border border-aura-200 dark:border-aura-800 rounded-lg">
        <InformationCircleIcon className="h-5 w-5 text-aura-600 dark:text-aura-400 flex-shrink-0 mt-0.5" />
        <div>
          <h4 className="font-medium text-aura-800 dark:text-aura-200">API Rate Limiting</h4>
          <p className="text-sm text-aura-700 dark:text-aura-300 mt-1">
            Configure rate limits to protect the API from abuse and ensure fair usage.
            Different tiers apply to different types of operations.
          </p>
        </div>
      </div>

      {/* Current Status */}
      <RateLimitStatusDisplay status={status} />

      {/* Rate Limit Tiers */}
      <div>
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4">
          Rate Limit Tiers
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Object.entries(RATE_LIMIT_TIERS).map(([tier, config]) => (
            <RateLimitTierCard
              key={tier}
              tier={tier}
              config={config}
              limits={limits[tier]}
              onChange={(newLimits) => handleTierChange(tier, newLimits)}
              isLoading={saving}
            />
          ))}
        </div>
      </div>

      {/* Endpoint Groups */}
      <div>
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4">
          Endpoint Configuration
        </h3>
        <div className="space-y-2">
          {ENDPOINT_GROUPS.map((group) => (
            <EndpointGroupPanel
              key={group.name}
              group={group}
              isExpanded={expandedGroup === group.name}
              onToggle={() => setExpandedGroup(expandedGroup === group.name ? null : group.name)}
            />
          ))}
        </div>
      </div>

      {/* Action Buttons */}
      {hasChanges && (
        <div className="flex justify-end gap-3 pt-4 border-t border-surface-200 dark:border-surface-700">
          <button
            onClick={handleReset}
            disabled={saving}
            className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
          >
            Reset to Defaults
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-aura-600 text-white rounded-lg hover:bg-aura-700 disabled:opacity-50 transition-colors"
          >
            {saving ? (
              <>
                <ArrowPathIcon className="h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <CheckCircleIcon className="h-4 w-4" />
                Save Rate Limits
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
}
