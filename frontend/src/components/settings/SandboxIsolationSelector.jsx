/**
 * Project Aura - Sandbox Isolation Selector Component
 *
 * Interactive selector for choosing sandbox isolation levels.
 */

import { useState, useEffect } from 'react';
import {
  ShieldCheckIcon,
  ServerStackIcon,
  GlobeAltIcon,
  BuildingLibraryIcon,
  CheckCircleIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  LockClosedIcon,
  CurrencyDollarIcon,
  ClockIcon,
} from '@heroicons/react/24/outline';

import {
  getEnvironmentIsolation,
  updateEnvironmentIsolation,
  ISOLATION_LEVEL_CONFIG,
} from '../../services/environmentsApi';

// Icon mapping for isolation levels
const ISOLATION_ICONS = {
  namespace: ServerStackIcon,
  container: ShieldCheckIcon,
  vpc: GlobeAltIcon,
  account: BuildingLibraryIcon,
};

// Color mapping for isolation levels
const ISOLATION_COLORS = {
  namespace: {
    bg: 'bg-aura-50 dark:bg-aura-900/20',
    border: 'border-aura-200 dark:border-aura-800',
    ring: 'ring-aura-500',
    text: 'text-aura-700 dark:text-aura-400',
    iconBg: 'bg-aura-100 dark:bg-aura-900/30',
  },
  container: {
    bg: 'bg-olive-50 dark:bg-olive-900/20',
    border: 'border-olive-200 dark:border-olive-800',
    ring: 'ring-olive-500',
    text: 'text-olive-700 dark:text-olive-400',
    iconBg: 'bg-olive-100 dark:bg-olive-900/30',
  },
  vpc: {
    bg: 'bg-warning-50 dark:bg-warning-900/20',
    border: 'border-warning-200 dark:border-warning-800',
    ring: 'ring-warning-500',
    text: 'text-warning-700 dark:text-warning-400',
    iconBg: 'bg-warning-100 dark:bg-warning-900/30',
  },
  account: {
    bg: 'bg-critical-50 dark:bg-critical-900/20',
    border: 'border-critical-200 dark:border-critical-800',
    ring: 'ring-critical-500',
    text: 'text-critical-700 dark:text-critical-400',
    iconBg: 'bg-critical-100 dark:bg-critical-900/30',
  },
};

// Cost estimates for each isolation level
const ISOLATION_COSTS = {
  namespace: { hourly: 0.02, daily: 0.48, provisioning: '< 1 min' },
  container: { hourly: 0.05, daily: 1.20, provisioning: '1-2 min' },
  vpc: { hourly: 0.25, daily: 6.00, provisioning: '5-10 min' },
  account: { hourly: 1.00, daily: 24.00, provisioning: '15-30 min' },
};

/**
 * Isolation Level Card Component
 */
function IsolationLevelCard({ level, config, isSelected, onSelect, isLoading, showImpact }) {
  const Icon = ISOLATION_ICONS[level] || ShieldCheckIcon;
  const colors = ISOLATION_COLORS[level] || ISOLATION_COLORS.namespace;
  const costs = ISOLATION_COSTS[level];

  return (
    <div
      onClick={() => !isLoading && onSelect(level)}
      className={`
        relative rounded-xl border-2 transition-all duration-200 cursor-pointer
        ${isSelected
          ? `${colors.border} ${colors.bg} ring-2 ${colors.ring}`
          : 'border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 hover:border-surface-300 dark:hover:border-surface-600'
        }
        ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}
      `}
    >
      {isSelected && (
        <div className="absolute top-3 right-3">
          <CheckCircleIcon className={`h-5 w-5 ${colors.text}`} />
        </div>
      )}

      <div className="p-5">
        <div className="flex items-start gap-4 mb-4">
          <div className={`p-3 rounded-xl ${isSelected ? colors.iconBg : 'bg-surface-100 dark:bg-surface-700'}`}>
            <Icon className={`h-6 w-6 ${isSelected ? colors.text : 'text-surface-600 dark:text-surface-400'}`} />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h4 className="font-semibold text-surface-900 dark:text-surface-100">
                {config.label}
              </h4>
              <span className={`
                px-2 py-0.5 text-xs font-medium rounded-full
                ${config.securityLevel === 'maximum' ? 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400' :
                  config.securityLevel === 'high' ? 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400' :
                  config.securityLevel === 'enhanced' ? 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400' :
                  'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400'}
              `}>
                {config.securityLevel}
              </span>
            </div>
            <p className="text-sm text-surface-500 dark:text-surface-400 mt-1">
              {config.description}
            </p>
          </div>
        </div>

        {/* Features List */}
        <div className="mb-4">
          <p className="text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wide mb-2">
            Isolation Features
          </p>
          <ul className="space-y-1">
            {config.features.map((feature, idx) => (
              <li key={idx} className="flex items-center gap-2 text-sm text-surface-600 dark:text-surface-400">
                <LockClosedIcon className="h-3.5 w-3.5 text-olive-500" />
                {feature}
              </li>
            ))}
          </ul>
        </div>

        {/* Cost and Time Estimates */}
        {showImpact && costs && (
          <div className="pt-4 border-t border-surface-200 dark:border-surface-700">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-center">
              <div>
                <CurrencyDollarIcon className="h-4 w-4 text-surface-400 mx-auto mb-1" />
                <p className="text-sm font-bold text-surface-900 dark:text-surface-100">
                  ${costs.hourly}
                </p>
                <p className="text-xs text-surface-500 dark:text-surface-400">per hour</p>
              </div>
              <div>
                <CurrencyDollarIcon className="h-4 w-4 text-surface-400 mx-auto mb-1" />
                <p className="text-sm font-bold text-surface-900 dark:text-surface-100">
                  ${costs.daily}
                </p>
                <p className="text-xs text-surface-500 dark:text-surface-400">per day</p>
              </div>
              <div>
                <ClockIcon className="h-4 w-4 text-surface-400 mx-auto mb-1" />
                <p className="text-sm font-bold text-surface-900 dark:text-surface-100">
                  {costs.provisioning}
                </p>
                <p className="text-xs text-surface-500 dark:text-surface-400">provision</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Isolation Impact Warning Component
 */
function IsolationImpactWarning({ currentLevel, newLevel }) {
  if (currentLevel === newLevel) return null;

  const currentConfig = ISOLATION_LEVEL_CONFIG[currentLevel];
  const newConfig = ISOLATION_LEVEL_CONFIG[newLevel];
  const levels = ['namespace', 'container', 'vpc', 'account'];
  const currentIdx = levels.indexOf(currentLevel);
  const newIdx = levels.indexOf(newLevel);

  const isUpgrade = newIdx > currentIdx;

  return (
    <div className={`
      p-4 rounded-lg border mt-4
      ${isUpgrade
        ? 'bg-warning-50 border-warning-200 dark:bg-warning-900/20 dark:border-warning-800'
        : 'bg-olive-50 border-olive-200 dark:bg-olive-900/20 dark:border-olive-800'
      }
    `}>
      <div className="flex items-start gap-3">
        {isUpgrade ? (
          <ExclamationTriangleIcon className="h-5 w-5 text-warning-600 dark:text-warning-400 flex-shrink-0 mt-0.5" />
        ) : (
          <InformationCircleIcon className="h-5 w-5 text-olive-600 dark:text-olive-400 flex-shrink-0 mt-0.5" />
        )}
        <div>
          <h4 className={`font-medium ${isUpgrade ? 'text-warning-800 dark:text-warning-200' : 'text-olive-800 dark:text-olive-200'}`}>
            {isUpgrade ? 'Isolation Upgrade Impact' : 'Isolation Downgrade Notice'}
          </h4>
          <p className={`text-sm mt-1 ${isUpgrade ? 'text-warning-700 dark:text-warning-300' : 'text-olive-700 dark:text-olive-300'}`}>
            {isUpgrade
              ? `Upgrading from ${currentConfig?.label} to ${newConfig?.label} will increase costs and may require environment reprovisioning. Estimated additional time: ${ISOLATION_COSTS[newLevel]?.provisioning}.`
              : `Downgrading from ${currentConfig?.label} to ${newConfig?.label} will reduce isolation. Ensure this meets your security requirements.`
            }
          </p>
        </div>
      </div>
    </div>
  );
}

/**
 * Main Sandbox Isolation Selector Component
 */
export default function SandboxIsolationSelector({
  environmentId,
  currentLevel: propLevel,
  onLevelChange,
  showImpact = true,
  disabled = false,
}) {
  const [currentLevel, setCurrentLevel] = useState(propLevel || 'namespace');
  const [selectedLevel, setSelectedLevel] = useState(propLevel || 'namespace');
  const [loading, setLoading] = useState(!propLevel);
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  // Load isolation level when environmentId changes (propLevel takes precedence)
  useEffect(() => {
    if (environmentId && !propLevel) {
      loadIsolationLevel();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [environmentId]);

  useEffect(() => {
    if (propLevel) {
      setCurrentLevel(propLevel);
      setSelectedLevel(propLevel);
    }
  }, [propLevel]);

  const loadIsolationLevel = async () => {
    setLoading(true);
    try {
      const data = await getEnvironmentIsolation(environmentId);
      setCurrentLevel(data.level);
      setSelectedLevel(data.level);
    } catch (err) {
      console.error('Failed to load isolation level:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelect = (level) => {
    if (disabled) return;
    setSelectedLevel(level);
    setHasChanges(level !== currentLevel);
  };

  const handleApply = async () => {
    if (!hasChanges) return;

    setSaving(true);
    try {
      if (environmentId) {
        await updateEnvironmentIsolation(environmentId, selectedLevel);
      }
      setCurrentLevel(selectedLevel);
      setHasChanges(false);
      onLevelChange?.(selectedLevel);
    } catch (err) {
      console.error('Failed to update isolation level:', err);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <ArrowPathIcon className="h-8 w-8 text-aura-500 animate-spin" />
        <span className="ml-3 text-surface-600 dark:text-surface-400">
          Loading isolation settings...
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Info Banner */}
      <div className="flex items-start gap-3 p-4 bg-aura-50 dark:bg-aura-900/20 border border-aura-200 dark:border-aura-800 rounded-lg">
        <ShieldCheckIcon className="h-5 w-5 text-aura-600 dark:text-aura-400 flex-shrink-0 mt-0.5" />
        <div>
          <h4 className="font-medium text-aura-800 dark:text-aura-200">Sandbox Isolation Level</h4>
          <p className="text-sm text-aura-700 dark:text-aura-300 mt-1">
            Choose the level of isolation for your sandbox environment. Higher isolation
            provides stronger security boundaries but increases cost and provisioning time.
          </p>
        </div>
      </div>

      {/* Isolation Level Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {Object.entries(ISOLATION_LEVEL_CONFIG).map(([level, config]) => (
          <IsolationLevelCard
            key={level}
            level={level}
            config={config}
            isSelected={selectedLevel === level}
            onSelect={handleSelect}
            isLoading={saving || disabled}
            showImpact={showImpact}
          />
        ))}
      </div>

      {/* Impact Warning */}
      {hasChanges && (
        <IsolationImpactWarning
          currentLevel={currentLevel}
          newLevel={selectedLevel}
        />
      )}

      {/* Action Buttons */}
      {hasChanges && !disabled && (
        <div className="flex justify-end gap-3">
          <button
            onClick={() => {
              setSelectedLevel(currentLevel);
              setHasChanges(false);
            }}
            disabled={saving}
            className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleApply}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-aura-600 text-white rounded-lg hover:bg-aura-700 disabled:opacity-50 transition-colors"
          >
            {saving ? (
              <>
                <ArrowPathIcon className="h-4 w-4 animate-spin" />
                Applying...
              </>
            ) : (
              <>
                <ShieldCheckIcon className="h-4 w-4" />
                Apply Isolation Level
              </>
            )}
          </button>
        </div>
      )}

      {/* Security Recommendation */}
      <div className="bg-surface-50 dark:bg-surface-800/50 rounded-lg p-4 border border-surface-200 dark:border-surface-700">
        <h4 className="font-medium text-surface-900 dark:text-surface-100 mb-2">
          Security Recommendations
        </h4>
        <ul className="text-sm text-surface-600 dark:text-surface-400 space-y-1">
          <li className="flex items-start gap-2">
            <CheckCircleIcon className="h-4 w-4 text-olive-500 mt-0.5 flex-shrink-0" />
            <span><strong>Namespace:</strong> Suitable for development and non-sensitive testing</span>
          </li>
          <li className="flex items-start gap-2">
            <CheckCircleIcon className="h-4 w-4 text-olive-500 mt-0.5 flex-shrink-0" />
            <span><strong>Container:</strong> Recommended for production-like testing</span>
          </li>
          <li className="flex items-start gap-2">
            <CheckCircleIcon className="h-4 w-4 text-olive-500 mt-0.5 flex-shrink-0" />
            <span><strong>VPC:</strong> Required for testing with external integrations</span>
          </li>
          <li className="flex items-start gap-2">
            <CheckCircleIcon className="h-4 w-4 text-olive-500 mt-0.5 flex-shrink-0" />
            <span><strong>Account:</strong> Required for compliance testing and GovCloud workloads</span>
          </li>
        </ul>
      </div>
    </div>
  );
}
