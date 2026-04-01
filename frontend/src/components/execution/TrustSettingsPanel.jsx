/**
 * Project Aura - Trust Settings Panel Component
 *
 * Configure which actions auto-approve:
 * - Per-tool-type trust levels
 * - Session vs permanent trust
 * - Always require approval list
 *
 * Features:
 * - Toggle trust per action type
 * - Session trust management
 * - Permanent trust configuration
 * - Clear all session trusts
 *
 * @see ADR-032 Configurable Autonomy Framework
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  XMarkIcon,
  ShieldCheckIcon,
  LockClosedIcon,
  TrashIcon,
  ArrowPathIcon,
  InformationCircleIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ChevronDownIcon,
  ChevronUpIcon,
} from '@heroicons/react/24/outline';

import {
  DocumentTextIcon,
  PencilSquareIcon,
  DocumentPlusIcon,
  CommandLineIcon,
  ServerStackIcon,
  CircleStackIcon,
  CloudArrowUpIcon,
  CogIcon,
  KeyIcon,
  GlobeAltIcon,
} from '@heroicons/react/24/outline';

import { useTrustSettings, useExecution } from '../../context/ExecutionContext';

// =============================================================================
// CONSTANTS
// =============================================================================

const ACTION_ICONS = {
  file_read: DocumentTextIcon,
  file_write: PencilSquareIcon,
  file_create: DocumentPlusIcon,
  file_delete: TrashIcon,
  command_execute: CommandLineIcon,
  api_call: ServerStackIcon,
  database_query: CircleStackIcon,
  database_write: CircleStackIcon,
  network_request: GlobeAltIcon,
  deployment: CloudArrowUpIcon,
  configuration_change: CogIcon,
  secret_access: KeyIcon,
};

// =============================================================================
// SUB-COMPONENTS
// =============================================================================

/**
 * Action Type Trust Toggle
 */
function ActionTypeTrustToggle({
  actionType,
  label,
  description,
  isAutoApproved,
  isAlwaysRequired,
  isSessionTrusted,
  onToggleAutoApprove,
  _onToggleAlwaysRequired,
  onClearSessionTrust,
  disabled,
}) {
  const Icon = ACTION_ICONS[actionType] || CommandLineIcon;
  const { RISK_LEVEL_CONFIG, ACTION_TYPE_CONFIG } = useExecution();
  const typeConfig = ACTION_TYPE_CONFIG[actionType] || {};
  const riskConfig = RISK_LEVEL_CONFIG[typeConfig.defaultRisk] || RISK_LEVEL_CONFIG.low;

  return (
    <div className={`
      p-4 rounded-xl border transition-all duration-200 ease-[var(--ease-tahoe)]
      ${isAlwaysRequired
        ? 'border-critical-200/50 dark:border-critical-800/50 bg-critical-50/80 dark:bg-critical-900/20 backdrop-blur-sm'
        : isAutoApproved || isSessionTrusted
          ? 'border-olive-200/50 dark:border-olive-800/50 bg-olive-50/80 dark:bg-olive-900/20 backdrop-blur-sm'
          : 'border-surface-200/50 dark:border-surface-700/30 bg-white dark:bg-surface-800 backdrop-blur-sm hover:bg-surface-50 dark:hover:bg-surface-700'
      }
    `}>
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div className={`
          p-2 rounded-lg
          ${isAlwaysRequired
            ? 'bg-critical-100 dark:bg-critical-900/30'
            : isAutoApproved || isSessionTrusted
              ? 'bg-olive-100 dark:bg-olive-900/30'
              : 'bg-surface-100 dark:bg-surface-700'
          }
        `}>
          <Icon className={`
            w-5 h-5
            ${isAlwaysRequired
              ? 'text-critical-600 dark:text-critical-400'
              : isAutoApproved || isSessionTrusted
                ? 'text-olive-600 dark:text-olive-400'
                : 'text-surface-600 dark:text-surface-400'
            }
          `} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h4 className="font-medium text-surface-900 dark:text-surface-100">
              {label}
            </h4>
            <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${riskConfig.badgeClass}`}>
              {typeConfig.defaultRisk?.toUpperCase() || 'LOW'}
            </span>
          </div>
          <p className="text-xs text-surface-500 dark:text-surface-400 mb-3">
            {description}
          </p>

          {/* Trust indicators */}
          <div className="flex flex-wrap items-center gap-2">
            {isAlwaysRequired && (
              <span className="flex items-center gap-1 px-2 py-1 bg-critical-100 dark:bg-critical-900/30 text-critical-700 dark:text-critical-400 rounded text-xs font-medium">
                <LockClosedIcon className="w-3 h-3" />
                Always requires approval
              </span>
            )}
            {isAutoApproved && !isAlwaysRequired && (
              <span className="flex items-center gap-1 px-2 py-1 bg-olive-100 dark:bg-olive-900/30 text-olive-700 dark:text-olive-400 rounded text-xs font-medium">
                <CheckCircleIcon className="w-3 h-3" />
                Auto-approved
              </span>
            )}
            {isSessionTrusted && !isAutoApproved && !isAlwaysRequired && (
              <span className="flex items-center gap-1 px-2 py-1 bg-aura-100 dark:bg-aura-900/30 text-aura-700 dark:text-aura-400 rounded text-xs font-medium">
                <ShieldCheckIcon className="w-3 h-3" />
                Trusted this session
                <button
                  onClick={() => onClearSessionTrust(actionType)}
                  className="ml-1 p-0.5 hover:bg-aura-200 dark:hover:bg-aura-900/50 rounded"
                  title="Remove session trust"
                >
                  <XMarkIcon className="w-3 h-3" />
                </button>
              </span>
            )}
          </div>
        </div>

        {/* Toggle */}
        {!isAlwaysRequired && (
          <div className="flex-shrink-0">
            <button
              onClick={() => onToggleAutoApprove(actionType)}
              disabled={disabled}
              className={`
                relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent
                transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2 dark:focus:ring-offset-surface-800
                ${isAutoApproved ? 'bg-olive-600' : 'bg-surface-200 dark:bg-surface-600'}
                ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
              `}
              title={isAutoApproved ? 'Disable auto-approve' : 'Enable auto-approve'}
            >
              <span
                className={`
                  pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0
                  transition duration-200 ease-in-out
                  ${isAutoApproved ? 'translate-x-5' : 'translate-x-0'}
                `}
              />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Session Trusts Section
 */
function SessionTrustsSection({ sessionTrusts, onClear, onClearAll }) {
  const { ACTION_TYPE_CONFIG } = useExecution();
  const trustArray = Array.from(sessionTrusts.entries());

  if (trustArray.length === 0) {
    return (
      <div className="p-4 text-center text-surface-500 dark:text-surface-400 text-sm">
        No session trusts active
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {trustArray.map(([actionType, scope]) => {
        const typeConfig = ACTION_TYPE_CONFIG[actionType] || { label: actionType };
        const Icon = ACTION_ICONS[actionType] || CommandLineIcon;

        return (
          <div
            key={actionType}
            className="flex items-center justify-between p-3 bg-aura-50 dark:bg-aura-900/10 border border-aura-200 dark:border-aura-800 rounded-lg"
          >
            <div className="flex items-center gap-2">
              <Icon className="w-4 h-4 text-aura-600 dark:text-aura-400" />
              <span className="text-sm font-medium text-surface-900 dark:text-surface-100">
                {typeConfig.label}
              </span>
              <span className="text-xs text-aura-600 dark:text-aura-400 px-1.5 py-0.5 bg-aura-100 dark:bg-aura-900/30 rounded">
                {scope}
              </span>
            </div>
            <button
              onClick={() => onClear(actionType)}
              className="p-1 text-aura-600 dark:text-aura-400 hover:bg-aura-100 dark:hover:bg-aura-900/30 rounded transition-colors"
              title="Remove trust"
            >
              <XMarkIcon className="w-4 h-4" />
            </button>
          </div>
        );
      })}

      <button
        onClick={onClearAll}
        className="w-full flex items-center justify-center gap-2 p-2 text-sm text-critical-600 dark:text-critical-400 hover:bg-critical-50 dark:hover:bg-critical-900/10 rounded-lg transition-colors"
      >
        <TrashIcon className="w-4 h-4" />
        Clear all session trusts
      </button>
    </div>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

/**
 * Trust Settings Panel
 *
 * @param {Object} props
 * @param {boolean} props.isOpen - Whether the panel is open
 * @param {function} props.onClose - Close callback
 * @param {boolean} props.asModal - Render as modal overlay
 */
export default function TrustSettingsPanel({ isOpen, onClose, asModal = false }) {
  const {
    settings,
    sessionTrusts,
    save,
    removeSessionTrust,
    clearSessionTrusts,
    isLoading,
  } = useTrustSettings();

  const { ACTION_TYPE_CONFIG, TrustScope: _TrustScope } = useExecution();

  // Local state
  const [expandedSection, setExpandedSection] = useState('permanent');
  const [localSettings, setLocalSettings] = useState(settings);
  const [hasChanges, setHasChanges] = useState(false);

  // Sync local settings when settings change
  useEffect(() => {
    setLocalSettings(settings);
    setHasChanges(false);
  }, [settings]);

  // All action types
  const actionTypes = useMemo(() => {
    return Object.entries(ACTION_TYPE_CONFIG).map(([key, config]) => ({
      type: key,
      label: config.label,
      description: `Default risk: ${config.defaultRisk}`,
      defaultRisk: config.defaultRisk,
    }));
  }, [ACTION_TYPE_CONFIG]);

  // Handle toggle auto-approve
  const handleToggleAutoApprove = useCallback((actionType) => {
    setLocalSettings((prev) => {
      const autoApprove = prev.default_auto_approve || [];
      const alwaysRequired = prev.always_require_approval || [];

      // Can't auto-approve if always required
      if (alwaysRequired.includes(actionType)) return prev;

      const newAutoApprove = autoApprove.includes(actionType)
        ? autoApprove.filter((t) => t !== actionType)
        : [...autoApprove, actionType];

      return {
        ...prev,
        default_auto_approve: newAutoApprove,
      };
    });
    setHasChanges(true);
  }, []);

  // Handle toggle always required
  const handleToggleAlwaysRequired = useCallback((actionType) => {
    setLocalSettings((prev) => {
      const alwaysRequired = prev.always_require_approval || [];
      const autoApprove = prev.default_auto_approve || [];

      const newAlwaysRequired = alwaysRequired.includes(actionType)
        ? alwaysRequired.filter((t) => t !== actionType)
        : [...alwaysRequired, actionType];

      // Remove from auto-approve if adding to always required
      const newAutoApprove = newAlwaysRequired.includes(actionType)
        ? autoApprove.filter((t) => t !== actionType)
        : autoApprove;

      return {
        ...prev,
        always_require_approval: newAlwaysRequired,
        default_auto_approve: newAutoApprove,
      };
    });
    setHasChanges(true);
  }, []);

  // Handle save
  const handleSave = useCallback(async () => {
    try {
      await save(localSettings);
      setHasChanges(false);
    } catch (err) {
      console.error('Failed to save trust settings:', err);
    }
  }, [localSettings, save]);

  // Handle reset
  const handleReset = useCallback(() => {
    setLocalSettings(settings);
    setHasChanges(false);
  }, [settings]);

  // Don't render if not open
  if (!isOpen) return null;

  const content = (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-4 border-b border-surface-100/50 dark:border-surface-700/30 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-aura-100 dark:bg-aura-900/30 rounded-lg">
            <ShieldCheckIcon className="w-5 h-5 text-aura-600 dark:text-aura-400" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
              Trust Settings
            </h2>
            <p className="text-sm text-surface-500 dark:text-surface-400">
              Configure auto-approval for action types
            </p>
          </div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="p-2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 hover:bg-white/60 dark:hover:bg-surface-700 rounded-lg transition-all duration-200 ease-[var(--ease-tahoe)]"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Info banner */}
        <div className="flex items-start gap-3 p-4 bg-aura-50/80 dark:bg-aura-900/20 backdrop-blur-sm border border-aura-200/50 dark:border-aura-800/50 rounded-xl">
          <InformationCircleIcon className="w-5 h-5 text-aura-600 dark:text-aura-400 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-aura-700 dark:text-aura-300">
            <p className="font-medium mb-1">How trust settings work</p>
            <ul className="space-y-1 text-aura-600 dark:text-aura-400 text-xs">
              <li>Auto-approved actions execute without waiting for approval</li>
              <li>Session trusts expire when you close the browser</li>
              <li>Actions marked "Always require approval" cannot be auto-approved</li>
            </ul>
          </div>
        </div>

        {/* Session Trusts */}
        <div className="border border-surface-200/50 dark:border-surface-700/30 rounded-xl overflow-hidden">
          <button
            onClick={() => setExpandedSection(expandedSection === 'session' ? '' : 'session')}
            className="w-full px-4 py-3 flex items-center justify-between bg-surface-50 dark:bg-surface-800 hover:bg-white dark:hover:bg-surface-700 transition-all duration-200 ease-[var(--ease-tahoe)]"
          >
            <div className="flex items-center gap-2">
              <ShieldCheckIcon className="w-4 h-4 text-aura-500" />
              <span className="text-sm font-medium text-surface-900 dark:text-surface-100">
                Session Trusts
              </span>
              {sessionTrusts.size > 0 && (
                <span className="px-1.5 py-0.5 text-xs bg-aura-100 dark:bg-aura-900/30 text-aura-700 dark:text-aura-400 rounded">
                  {sessionTrusts.size}
                </span>
              )}
            </div>
            {expandedSection === 'session' ? (
              <ChevronUpIcon className="w-4 h-4 text-surface-400" />
            ) : (
              <ChevronDownIcon className="w-4 h-4 text-surface-400" />
            )}
          </button>

          {expandedSection === 'session' && (
            <div className="p-4 border-t border-surface-100/50 dark:border-surface-700/30">
              <SessionTrustsSection
                sessionTrusts={sessionTrusts}
                onClear={removeSessionTrust}
                onClearAll={clearSessionTrusts}
              />
            </div>
          )}
        </div>

        {/* Permanent Settings */}
        <div className="border border-surface-200/50 dark:border-surface-700/30 rounded-xl overflow-hidden">
          <button
            onClick={() => setExpandedSection(expandedSection === 'permanent' ? '' : 'permanent')}
            className="w-full px-4 py-3 flex items-center justify-between bg-surface-50 dark:bg-surface-800 hover:bg-white dark:hover:bg-surface-700 transition-all duration-200 ease-[var(--ease-tahoe)]"
          >
            <div className="flex items-center gap-2">
              <CogIcon className="w-4 h-4 text-surface-500" />
              <span className="text-sm font-medium text-surface-900 dark:text-surface-100">
                Permanent Settings
              </span>
              {hasChanges && (
                <span className="px-1.5 py-0.5 text-xs bg-warning-100 dark:bg-warning-900/30 text-warning-700 dark:text-warning-400 rounded">
                  Unsaved
                </span>
              )}
            </div>
            {expandedSection === 'permanent' ? (
              <ChevronUpIcon className="w-4 h-4 text-surface-400" />
            ) : (
              <ChevronDownIcon className="w-4 h-4 text-surface-400" />
            )}
          </button>

          {expandedSection === 'permanent' && (
            <div className="p-4 border-t border-surface-100/50 dark:border-surface-700/30 space-y-3">
              {actionTypes.map((actionType) => (
                <ActionTypeTrustToggle
                  key={actionType.type}
                  actionType={actionType.type}
                  label={actionType.label}
                  description={actionType.description}
                  isAutoApproved={(localSettings.default_auto_approve || []).includes(actionType.type)}
                  isAlwaysRequired={(localSettings.always_require_approval || []).includes(actionType.type)}
                  isSessionTrusted={sessionTrusts.has(actionType.type)}
                  onToggleAutoApprove={handleToggleAutoApprove}
                  onToggleAlwaysRequired={handleToggleAlwaysRequired}
                  onClearSessionTrust={removeSessionTrust}
                  disabled={isLoading}
                />
              ))}
            </div>
          )}
        </div>

        {/* Warning about critical actions */}
        <div className="flex items-start gap-3 p-4 bg-critical-50/80 dark:bg-critical-900/20 backdrop-blur-sm border border-critical-200/50 dark:border-critical-800/50 rounded-xl">
          <ExclamationTriangleIcon className="w-5 h-5 text-critical-600 dark:text-critical-400 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-critical-700 dark:text-critical-300">
            <p className="font-medium mb-1">Guardrail Actions</p>
            <p className="text-xs text-critical-600 dark:text-critical-400">
              The following actions always require approval regardless of settings:
              deployments, database writes, credential modifications, infrastructure changes.
            </p>
          </div>
        </div>
      </div>

      {/* Footer */}
      {hasChanges && (
        <div className="px-6 py-4 border-t border-surface-100/50 dark:border-surface-700/30 bg-surface-50 dark:bg-surface-800 flex items-center justify-end gap-3">
          <button
            onClick={handleReset}
            disabled={isLoading}
            className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-white/60 dark:hover:bg-surface-700 rounded-xl transition-all duration-200 ease-[var(--ease-tahoe)] disabled:opacity-50"
          >
            Reset
          </button>
          <button
            onClick={handleSave}
            disabled={isLoading}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-aura-500 rounded-xl hover:bg-aura-600 hover:-translate-y-px hover:shadow-md active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 ease-[var(--ease-tahoe)]"
          >
            {isLoading ? (
              <ArrowPathIcon className="w-4 h-4 animate-spin" />
            ) : (
              <CheckCircleIcon className="w-4 h-4" />
            )}
            Save Changes
          </button>
        </div>
      )}
    </div>
  );

  // Render as modal or inline
  if (asModal) {
    return (
      <div className="fixed inset-0 z-50 overflow-y-auto">
        <div
          className="fixed inset-0 glass-backdrop"
          onClick={onClose}
        />
        <div className="flex min-h-full items-center justify-center p-4">
          <div className="
            relative w-full max-w-xl max-h-[80vh] overflow-hidden flex flex-col
            bg-white/95 dark:bg-surface-800/95
            backdrop-blur-xl backdrop-saturate-150
            rounded-2xl
            border border-white/50 dark:border-surface-700/50
            shadow-[var(--shadow-glass-hover)]
            animate-in fade-in zoom-in-95 duration-[var(--duration-overlay)] ease-[var(--ease-tahoe)]
          ">
            {content}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full bg-white dark:bg-surface-800 backdrop-blur-xl border-l border-surface-100/50 dark:border-surface-700/30">
      {content}
    </div>
  );
}
