/**
 * Project Aura - Action Approval Card Component
 *
 * Claude Code-style individual action approval UI with:
 * - Tool name and parameters display
 * - Risk level indicator
 * - Diff preview for file changes
 * - Approve/Deny/Modify buttons
 * - Trust checkbox for auto-approval
 * - Countdown timer for auto-timeout
 *
 * Keyboard shortcuts:
 * - A: Approve
 * - D: Deny
 * - M: Modify
 * - T: Trust this action type
 *
 * @see Design Principles: Apple-inspired, Claude Code-style
 */

import { useState, useEffect, useCallback } from 'react';
import {
  CheckIcon,
  XMarkIcon,
  PencilSquareIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  ShieldExclamationIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  DocumentTextIcon,
  CommandLineIcon,
  ServerStackIcon,
  CircleStackIcon,
  TrashIcon,
  CloudArrowUpIcon,
  CogIcon,
  KeyIcon,
  GlobeAltIcon,
  DocumentPlusIcon,
  CheckCircleIcon,
  XCircleIcon,
  ArrowPathIcon,
  HandRaisedIcon,
} from '@heroicons/react/24/outline';

import { useExecution } from '../../context/ExecutionContext';

// =============================================================================
// ICON MAPPING
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

const STATUS_ICONS = {
  pending: ClockIcon,
  awaiting_approval: HandRaisedIcon,
  approved: CheckCircleIcon,
  denied: XCircleIcon,
  modified: PencilSquareIcon,
  executing: ArrowPathIcon,
  completed: CheckCircleIcon,
  failed: XCircleIcon,
  timed_out: ClockIcon,
};

// =============================================================================
// SUB-COMPONENTS
// =============================================================================

/**
 * Risk Level Badge
 */
function RiskBadge({ level }) {
  const { RISK_LEVEL_CONFIG } = useExecution();
  const config = RISK_LEVEL_CONFIG[level] || RISK_LEVEL_CONFIG.low;

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${config.badgeClass}`}>
      {level === 'critical' && <ShieldExclamationIcon className="w-3 h-3" />}
      {level === 'high' && <ExclamationTriangleIcon className="w-3 h-3" />}
      {config.label}
    </span>
  );
}

/**
 * Action Status Badge
 */
function StatusBadge({ status }) {
  const statusConfig = {
    pending: {
      label: 'Pending',
      className: 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-400',
    },
    awaiting_approval: {
      label: 'Awaiting Approval',
      className: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400 animate-pulse',
    },
    approved: {
      label: 'Approved',
      className: 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400',
    },
    denied: {
      label: 'Denied',
      className: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
    },
    modified: {
      label: 'Modified',
      className: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    },
    executing: {
      label: 'Executing',
      className: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
    },
    completed: {
      label: 'Completed',
      className: 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400',
    },
    failed: {
      label: 'Failed',
      className: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
    },
    timed_out: {
      label: 'Timed Out',
      className: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    },
  };

  const config = statusConfig[status] || statusConfig.pending;
  const Icon = STATUS_ICONS[status] || ClockIcon;

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${config.className}`}>
      <Icon className={`w-3 h-3 ${status === 'executing' ? 'animate-spin' : ''}`} />
      {config.label}
    </span>
  );
}

/**
 * Countdown Timer
 */
function CountdownTimer({ timeoutAt, onTimeout }) {
  const [remaining, setRemaining] = useState(0);

  useEffect(() => {
    if (!timeoutAt) return;

    const updateRemaining = () => {
      const now = Date.now();
      const timeout = new Date(timeoutAt).getTime();
      const diff = Math.max(0, Math.floor((timeout - now) / 1000));
      setRemaining(diff);

      if (diff === 0 && onTimeout) {
        onTimeout();
      }
    };

    updateRemaining();
    const interval = setInterval(updateRemaining, 1000);

    return () => clearInterval(interval);
  }, [timeoutAt, onTimeout]);

  if (!timeoutAt || remaining <= 0) return null;

  const minutes = Math.floor(remaining / 60);
  const seconds = remaining % 60;
  const isUrgent = remaining <= 60;

  return (
    <div className={`flex items-center gap-1.5 text-xs font-medium ${isUrgent ? 'text-critical-600 dark:text-critical-400' : 'text-surface-500 dark:text-surface-400'}`}>
      <ClockIcon className={`w-3.5 h-3.5 ${isUrgent ? 'animate-pulse' : ''}`} />
      <span>
        {minutes}:{seconds.toString().padStart(2, '0')}
      </span>
    </div>
  );
}

/**
 * Diff Viewer for file changes
 */
function DiffViewer({ diff, isExpanded, onToggle }) {
  if (!diff) return null;

  const lines = diff.split('\n');

  return (
    <div className="border-t border-surface-100/50 dark:border-surface-700/30">
      <button
        onClick={onToggle}
        className="w-full px-4 py-2 flex items-center justify-between text-xs font-medium text-surface-600 dark:text-surface-400 hover:bg-white/60 dark:hover:bg-surface-700 transition-all duration-200 ease-[var(--ease-tahoe)]"
      >
        <span className="flex items-center gap-2">
          <DocumentTextIcon className="w-4 h-4" />
          Code Changes Preview
        </span>
        {isExpanded ? (
          <ChevronUpIcon className="w-4 h-4" />
        ) : (
          <ChevronDownIcon className="w-4 h-4" />
        )}
      </button>

      {isExpanded && (
        <div className="bg-surface-50 dark:bg-surface-900 overflow-x-auto border-t border-surface-200 dark:border-surface-700">
          <pre className="text-xs font-mono leading-relaxed">
            {lines.map((line, index) => {
              // IDE-like diff colors (VS Code style)
              let lineClass = 'text-surface-600 dark:text-surface-400 bg-surface-50 dark:bg-surface-900';
              let prefixClass = 'bg-surface-100 dark:bg-surface-800 text-surface-400';
              let prefix = ' ';

              if (line.startsWith('+') && !line.startsWith('+++')) {
                // Added lines: green background
                lineClass = 'bg-green-100 dark:bg-[#1a3d1a] text-green-900 dark:text-green-200';
                prefixClass = 'bg-green-200 dark:bg-[#234d23] text-green-700 dark:text-green-300 font-medium';
                prefix = '+';
              } else if (line.startsWith('-') && !line.startsWith('---')) {
                // Removed lines: critical red (matches CRITICAL status badge)
                lineClass = 'bg-critical-100 dark:bg-critical-900/50 text-critical-800 dark:text-critical-400';
                prefixClass = 'bg-critical-200 dark:bg-critical-800/60 text-critical-700 dark:text-critical-300 font-medium';
                prefix = '-';
              } else if (line.startsWith('@@')) {
                // Hunk headers: blue/cyan
                lineClass = 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300';
                prefixClass = 'bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-400';
                prefix = '@';
              } else if (line.startsWith('+++') || line.startsWith('---')) {
                // File headers
                lineClass = 'bg-surface-100 dark:bg-surface-800 text-surface-700 dark:text-surface-300 font-medium';
                prefixClass = 'bg-surface-200 dark:bg-surface-700 text-surface-500';
                prefix = ' ';
              }

              return (
                <div key={index} className={`flex ${lineClass}`}>
                  <span className={`w-6 text-center select-none flex-shrink-0 ${prefixClass}`}>
                    {prefix}
                  </span>
                  <span className="px-2 flex-1">
                    {line.startsWith('+') || line.startsWith('-') ? line.slice(1) : line || ' '}
                  </span>
                </div>
              );
            })}
          </pre>
        </div>
      )}
    </div>
  );
}

/**
 * Parameters Display
 */
function ParametersDisplay({ parameters, isExpanded, onToggle }) {
  if (!parameters || Object.keys(parameters).length === 0) return null;

  return (
    <div className="border-t border-surface-100/50 dark:border-surface-700/30">
      <button
        onClick={onToggle}
        className="w-full px-4 py-2 flex items-center justify-between text-xs font-medium text-surface-600 dark:text-surface-400 hover:bg-white/60 dark:hover:bg-surface-700 transition-all duration-200 ease-[var(--ease-tahoe)]"
      >
        <span>Parameters</span>
        {isExpanded ? (
          <ChevronUpIcon className="w-4 h-4" />
        ) : (
          <ChevronDownIcon className="w-4 h-4" />
        )}
      </button>

      {isExpanded && (
        <div className="px-4 py-3 bg-surface-50 dark:bg-surface-800">
          <pre className="text-xs font-mono text-surface-700 dark:text-surface-300 whitespace-pre-wrap">
            {JSON.stringify(parameters, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

/**
 * Action Approval Card
 *
 * @param {Object} props
 * @param {Object} props.action - Action object with type, target, description, etc.
 * @param {boolean} props.isCurrentAction - Whether this is the action awaiting approval
 * @param {boolean} props.compact - Use compact layout
 * @param {function} props.onApprove - Callback when approved
 * @param {function} props.onDeny - Callback when denied
 * @param {function} props.onModify - Callback when modify is requested
 * @param {function} props.onClick - Callback when card is clicked
 */
export default function ActionApprovalCard({
  action,
  isCurrentAction = false,
  compact = false,
  onApprove,
  onDeny,
  onModify,
  onClick,
}) {
  const {
    approveAction,
    denyAction,
    openModifyModal,
    loading,
    RISK_LEVEL_CONFIG,
    ACTION_TYPE_CONFIG,
    TrustScope,
  } = useExecution();

  // Local state
  const [isExpanded, setIsExpanded] = useState(isCurrentAction);
  const [showDiff, setShowDiff] = useState(isCurrentAction);
  const [showParameters, setShowParameters] = useState(false);
  const [trustThisType, setTrustThisType] = useState(false);

  // Expand when becomes current action
  useEffect(() => {
    if (isCurrentAction) {
      setIsExpanded(true);
      setShowDiff(true);
    }
  }, [isCurrentAction]);

  // Get action type configuration
  const typeConfig = ACTION_TYPE_CONFIG[action.type] || {
    label: action.type,
    icon: 'CommandLineIcon',
    defaultRisk: 'medium',
  };

  const riskConfig = RISK_LEVEL_CONFIG[action.risk_level] || RISK_LEVEL_CONFIG.low;
  const Icon = ACTION_ICONS[action.type] || CommandLineIcon;

  // Determine if action can be approved
  const canApprove = action.status === 'awaiting_approval';
  const isCompleted = ['completed', 'failed', 'denied', 'timed_out'].includes(action.status);

  // Handlers
  const handleApprove = useCallback((e) => {
    e.stopPropagation();
    const options = trustThisType ? { trustScope: TrustScope.THIS_ACTION_TYPE } : {};
    if (onApprove) {
      onApprove(action.action_id, options);
    } else {
      approveAction(action.action_id, options);
    }
  }, [action.action_id, trustThisType, onApprove, approveAction, TrustScope]);

  const handleDeny = useCallback((e) => {
    e.stopPropagation();
    if (onDeny) {
      onDeny(action.action_id);
    } else {
      denyAction(action.action_id);
    }
  }, [action.action_id, onDeny, denyAction]);

  const handleModify = useCallback((e) => {
    e.stopPropagation();
    if (onModify) {
      onModify(action);
    } else {
      openModifyModal(action);
    }
  }, [action, onModify, openModifyModal]);

  const handleCardClick = useCallback(() => {
    if (onClick) {
      onClick(action);
    } else if (!isCurrentAction) {
      setIsExpanded(!isExpanded);
    }
  }, [action, isCurrentAction, isExpanded, onClick]);

  // Render compact version
  if (compact) {
    return (
      <button
        onClick={handleCardClick}
        className={`
          w-full flex items-center gap-3 p-3 rounded-xl text-left
          transition-all duration-200 ease-[var(--ease-tahoe)]
          ${isCompleted
            ? 'border border-surface-200/50 dark:border-surface-700/50 bg-surface-50/50 dark:bg-surface-800/30 opacity-75'
            : isCurrentAction
              ? `border-2 ${riskConfig.borderClass} ${riskConfig.bgClass} ring-2 ring-aura-500`
              : 'border border-surface-200/50 dark:border-surface-700/50 bg-white dark:bg-surface-800 backdrop-blur-sm hover:bg-surface-50 dark:hover:bg-surface-700 hover:shadow-sm hover:-translate-y-px'
          }
        `}
      >
        {/* Status indicator */}
        <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
          action.status === 'completed' ? 'bg-olive-500' :
          action.status === 'failed' ? 'bg-critical-500' :
          action.status === 'denied' ? 'bg-critical-500' :
          action.status === 'executing' ? 'bg-aura-500 animate-pulse' :
          action.status === 'awaiting_approval' ? 'bg-warning-500 animate-pulse' :
          'bg-surface-400'
        }`} />

        {/* Icon */}
        <Icon className={`w-4 h-4 flex-shrink-0 ${isCompleted ? 'text-surface-400' : riskConfig.badgeClass.includes('critical') ? 'text-critical-500' : 'text-surface-600 dark:text-surface-400'}`} />

        {/* Content */}
        <div className="flex-1 min-w-0">
          <span className="text-sm font-medium text-surface-900 dark:text-surface-100 truncate block">
            {typeConfig.label}
          </span>
          <span className="text-xs text-surface-500 dark:text-surface-400 truncate block font-mono">
            {action.target}
          </span>
        </div>

        {/* Status badge */}
        <StatusBadge status={action.status} />
      </button>
    );
  }

  // Render full version
  return (
    <div
      className={`
        rounded-xl overflow-hidden
        transition-all duration-200 ease-[var(--ease-tahoe)]
        ${isCompleted
          ? 'border border-surface-200/50 dark:border-surface-700/50 bg-surface-50/50 dark:bg-surface-800/30 opacity-75'
          : isCurrentAction
            ? `border-2 ${riskConfig.borderClass} shadow-[var(--shadow-glass-hover)] ring-2 ring-aura-500/50 bg-white dark:bg-surface-800 backdrop-blur-xl`
            : 'border border-surface-200/50 dark:border-surface-700/50 bg-white dark:bg-surface-800 backdrop-blur-xl shadow-[var(--shadow-glass)]'
        }
      `}
    >
      {/* Header */}
      <button
        onClick={handleCardClick}
        className="w-full flex items-center gap-3 p-4 text-left hover:bg-white/60 dark:hover:bg-surface-700 transition-all duration-200 ease-[var(--ease-tahoe)]"
      >
        {/* Action Type Icon */}
        <div className={`p-2.5 rounded-lg ${isCurrentAction ? riskConfig.bgClass : 'bg-surface-100 dark:bg-surface-700'}`}>
          <Icon className={`w-5 h-5 ${isCurrentAction ? riskConfig.badgeClass.split(' ')[1] : 'text-surface-600 dark:text-surface-400'}`} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="text-sm font-semibold text-surface-900 dark:text-surface-100">
              {typeConfig.label}
            </span>
            <RiskBadge level={action.risk_level} />
            <StatusBadge status={action.status} />
          </div>
          <p className="text-xs text-surface-500 dark:text-surface-400 truncate font-mono">
            {action.target}
          </p>
          {action.description && (
            <p className="text-xs text-surface-600 dark:text-surface-400 mt-1 line-clamp-2">
              {action.description}
            </p>
          )}
        </div>

        {/* Timer and expand */}
        <div className="flex items-center gap-3 flex-shrink-0">
          {canApprove && action.timeout_at && (
            <CountdownTimer timeoutAt={action.timeout_at} />
          )}
          {!isCurrentAction && (
            <ChevronDownIcon className={`w-5 h-5 text-surface-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
          )}
        </div>
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <>
          {/* Diff Preview */}
          {action.diff && (
            <DiffViewer
              diff={action.diff}
              isExpanded={showDiff}
              onToggle={() => setShowDiff(!showDiff)}
            />
          )}

          {/* Parameters */}
          {action.parameters && (
            <ParametersDisplay
              parameters={action.parameters}
              isExpanded={showParameters}
              onToggle={() => setShowParameters(!showParameters)}
            />
          )}

          {/* Approval Controls */}
          {canApprove && (
            <div className="p-4 bg-surface-50 dark:bg-surface-800 border-t border-surface-100/50 dark:border-surface-700/30">
              {/* Trust checkbox */}
              <label className="flex items-center gap-2 mb-4 cursor-pointer group">
                <input
                  type="checkbox"
                  checked={trustThisType}
                  onChange={(e) => setTrustThisType(e.target.checked)}
                  className="w-4 h-4 rounded border-surface-300 text-aura-500 focus:ring-aura-500 dark:border-surface-600 dark:bg-surface-700"
                />
                <span className="text-sm text-surface-600 dark:text-surface-400 group-hover:text-surface-900 dark:group-hover:text-surface-200">
                  Trust all "{typeConfig.label}" actions this session
                </span>
                <kbd className="hidden sm:inline-block ml-auto px-1.5 py-0.5 text-xs font-mono bg-surface-200 dark:bg-surface-700 text-surface-500 dark:text-surface-400 rounded">
                  T
                </kbd>
              </label>

              {/* Action buttons */}
              <div className="flex gap-2">
                <button
                  onClick={handleDeny}
                  disabled={loading.deny}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium text-critical-600 dark:text-critical-400 border border-critical-300/50 dark:border-critical-700/50 rounded-xl bg-white dark:bg-surface-800 hover:bg-critical-50 dark:hover:bg-critical-900/20 hover:-translate-y-px hover:shadow-sm disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 ease-[var(--ease-tahoe)]"
                >
                  <XMarkIcon className="w-4 h-4" />
                  Deny
                </button>

                <button
                  onClick={handleModify}
                  disabled={loading.modify}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium text-white bg-orange-500 hover:bg-orange-600 rounded-xl hover:-translate-y-px hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 ease-[var(--ease-tahoe)]"
                >
                  <PencilSquareIcon className="w-4 h-4" />
                  Modify
                </button>

                <button
                  onClick={handleApprove}
                  disabled={loading.approve}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium text-white bg-olive-500 rounded-xl hover:bg-olive-600 hover:-translate-y-px hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 ease-[var(--ease-tahoe)]"
                >
                  {loading.approve ? (
                    <ArrowPathIcon className="w-4 h-4 animate-spin" />
                  ) : (
                    <CheckIcon className="w-4 h-4" />
                  )}
                  Approve
                </button>
              </div>

              {/* Keyboard hint */}
              <p className="text-xs text-surface-400 dark:text-surface-500 text-center mt-3">
                Use keyboard shortcuts for faster approvals
              </p>
            </div>
          )}

          {/* Result display for completed actions */}
          {action.status === 'completed' && action.result && (
            <div className="p-4 bg-olive-50/50 dark:bg-olive-900/10 border-t border-olive-200/50 dark:border-olive-800/30">
              <div className="flex items-center gap-2 text-olive-700 dark:text-olive-400 text-sm">
                <CheckCircleIcon className="w-4 h-4" />
                <span className="font-medium">Completed successfully</span>
              </div>
              {typeof action.result === 'object' && (
                <pre className="mt-2 text-xs font-mono text-olive-600 dark:text-olive-500">
                  {JSON.stringify(action.result, null, 2)}
                </pre>
              )}
            </div>
          )}

          {/* Error display for failed actions */}
          {action.status === 'failed' && action.error && (
            <div className="p-4 bg-critical-50/50 dark:bg-critical-900/10 border-t border-critical-200/50 dark:border-critical-800/30">
              <div className="flex items-center gap-2 text-critical-700 dark:text-critical-400 text-sm">
                <XCircleIcon className="w-4 h-4" />
                <span className="font-medium">Failed</span>
              </div>
              <p className="mt-1 text-xs text-critical-600 dark:text-critical-500">
                {action.error}
              </p>
            </div>
          )}

          {/* Denial reason */}
          {action.status === 'denied' && action.deny_reason && (
            <div className="p-4 bg-critical-50/50 dark:bg-critical-900/10 border-t border-critical-200/50 dark:border-critical-800/30">
              <div className="flex items-center gap-2 text-critical-700 dark:text-critical-400 text-sm">
                <XCircleIcon className="w-4 h-4" />
                <span className="font-medium">Denied</span>
              </div>
              <p className="mt-1 text-xs text-critical-600 dark:text-critical-500">
                {action.deny_reason}
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
