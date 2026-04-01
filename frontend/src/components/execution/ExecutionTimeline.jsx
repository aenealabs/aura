/**
 * Project Aura - Execution Timeline Component
 *
 * Visual timeline of all actions in an execution:
 * - Completed actions (green)
 * - Current action (yellow/pulsing)
 * - Pending actions (gray)
 *
 * Features:
 * - Click to inspect any action
 * - Progress indicator
 * - Time elapsed display
 * - Compact and expanded modes
 *
 * @see Design Principles: Apple-inspired timeline patterns
 */

import { useState, useCallback, useMemo, Fragment } from 'react';
import {
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  ArrowPathIcon,
  HandRaisedIcon,
  ChevronUpIcon,
  ChevronDownIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';

import {
  DocumentTextIcon,
  PencilSquareIcon,
  TrashIcon,
  CommandLineIcon,
  ServerStackIcon,
  CircleStackIcon,
  CloudArrowUpIcon,
  CogIcon,
  KeyIcon,
  GlobeAltIcon,
  DocumentPlusIcon,
} from '@heroicons/react/24/outline';

import { useExecutionTimeline, useExecution } from '../../context/ExecutionContext';

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

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

function formatDuration(startMs, endMs = Date.now()) {
  const seconds = Math.floor((endMs - startMs) / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}m ${remainingSeconds}s`;
}

function formatTime(isoString) {
  if (!isoString) return '';
  const date = new Date(isoString);
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

// =============================================================================
// SUB-COMPONENTS
// =============================================================================

/**
 * Progress Bar
 */
function ProgressBar({ progress, status }) {
  const getProgressColor = () => {
    if (status === 'failed' || status === 'aborted') {
      return 'bg-critical-500';
    }
    if (status === 'completed') {
      return 'bg-olive-500';
    }
    return 'bg-aura-500';
  };

  return (
    <div className="relative h-2 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden">
      <div
        className={`absolute inset-y-0 left-0 ${getProgressColor()} transition-all duration-500 ease-out`}
        style={{ width: `${progress}%` }}
      />
      {status === 'executing' && (
        <div
          className="absolute inset-y-0 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-shimmer"
          style={{ width: '50%' }}
        />
      )}
    </div>
  );
}

/**
 * Timeline Node
 */
function TimelineNode({ action, isFirst, isLast, isCurrent, onClick }) {
  const { ACTION_TYPE_CONFIG, RISK_LEVEL_CONFIG } = useExecution();
  const _Icon = ACTION_ICONS[action.type] || CommandLineIcon;
  const typeConfig = ACTION_TYPE_CONFIG[action.type] || { label: action.type };
  const riskConfig = RISK_LEVEL_CONFIG[action.risk_level] || RISK_LEVEL_CONFIG.low;

  // Determine node styling based on status
  const getNodeStyles = () => {
    switch (action.status) {
      case 'completed':
        return {
          nodeClass: 'bg-olive-500 text-white',
          lineClass: 'bg-olive-500',
          icon: <CheckCircleIcon className="w-4 h-4" />,
        };
      case 'failed':
        return {
          nodeClass: 'bg-critical-500 text-white',
          lineClass: 'bg-critical-500',
          icon: <XCircleIcon className="w-4 h-4" />,
        };
      case 'denied':
        return {
          nodeClass: 'bg-critical-500 text-white',
          lineClass: 'bg-critical-500',
          icon: <XCircleIcon className="w-4 h-4" />,
        };
      case 'timed_out':
        return {
          nodeClass: 'bg-warning-500 text-white',
          lineClass: 'bg-warning-500',
          icon: <ClockIcon className="w-4 h-4" />,
        };
      case 'executing':
        return {
          nodeClass: 'bg-aura-500 text-white animate-pulse',
          lineClass: 'bg-aura-500',
          icon: <ArrowPathIcon className="w-4 h-4 animate-spin" />,
        };
      case 'awaiting_approval':
        return {
          nodeClass: 'bg-warning-500 text-white animate-pulse',
          lineClass: 'bg-surface-300 dark:bg-surface-600',
          icon: <HandRaisedIcon className="w-4 h-4" />,
        };
      case 'approved':
      case 'modified':
        return {
          nodeClass: 'bg-olive-500 text-white',
          lineClass: 'bg-surface-300 dark:bg-surface-600',
          icon: <CheckCircleIcon className="w-4 h-4" />,
        };
      default:
        return {
          nodeClass: 'bg-surface-300 dark:bg-surface-600 text-surface-500 dark:text-surface-400',
          lineClass: 'bg-surface-300 dark:bg-surface-600',
          icon: <ClockIcon className="w-4 h-4" />,
        };
    }
  };

  const styles = getNodeStyles();
  const isClickable = ['completed', 'failed', 'denied', 'awaiting_approval', 'executing'].includes(action.status);

  return (
    <div className="relative flex items-start gap-3">
      {/* Connector line */}
      {!isFirst && (
        <div
          className={`absolute left-4 bottom-full w-0.5 h-4 ${styles.lineClass}`}
        />
      )}
      {!isLast && (
        <div
          className={`absolute left-4 top-8 w-0.5 h-full ${styles.lineClass}`}
        />
      )}

      {/* Node */}
      <button
        onClick={() => isClickable && onClick?.(action)}
        disabled={!isClickable}
        className={`
          relative z-10 flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center transition-all
          ${styles.nodeClass}
          ${isCurrent ? 'ring-4 ring-aura-200 dark:ring-aura-900' : ''}
          ${isClickable ? 'cursor-pointer hover:scale-110' : 'cursor-default'}
        `}
      >
        {styles.icon}
      </button>

      {/* Content */}
      <div className="flex-1 min-w-0 pb-6">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-sm font-medium text-surface-900 dark:text-surface-100 truncate">
            {typeConfig.label}
          </span>
          {action.risk_level && action.risk_level !== 'safe' && action.risk_level !== 'low' && (
            <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${riskConfig.badgeClass}`}>
              {action.risk_level.toUpperCase()}
            </span>
          )}
        </div>
        <p className="text-xs text-surface-500 dark:text-surface-400 truncate font-mono">
          {action.target}
        </p>
        {action.started_at && (
          <span className="text-[10px] text-surface-400 dark:text-surface-500">
            {formatTime(action.started_at)}
            {action.completed_at && ` - ${formatDuration(new Date(action.started_at).getTime(), new Date(action.completed_at).getTime())}`}
          </span>
        )}
      </div>
    </div>
  );
}

/**
 * Compact Timeline (horizontal)
 */
function CompactTimeline({ actions, currentActionId, onActionClick }) {
  const { RISK_LEVEL_CONFIG } = useExecution();

  return (
    <div className="flex items-center gap-1 overflow-x-auto pb-2">
      {actions.map((action, index) => {
        const isCurrent = action.action_id === currentActionId;
        const _riskConfig = RISK_LEVEL_CONFIG[action.risk_level] || RISK_LEVEL_CONFIG.low;

        const getNodeColor = () => {
          switch (action.status) {
            case 'completed':
              return 'bg-olive-500';
            case 'failed':
            case 'denied':
              return 'bg-critical-500';
            case 'timed_out':
              return 'bg-warning-500';
            case 'executing':
              return 'bg-aura-500 animate-pulse';
            case 'awaiting_approval':
              return 'bg-warning-500 animate-pulse';
            case 'approved':
            case 'modified':
              return 'bg-olive-500';
            default:
              return 'bg-surface-300 dark:bg-surface-600';
          }
        };

        return (
          <Fragment key={action.action_id}>
            {/* Connector */}
            {index > 0 && (
              <div className={`w-4 h-0.5 flex-shrink-0 ${
                ['completed', 'failed', 'denied', 'timed_out'].includes(actions[index - 1].status)
                  ? actions[index - 1].status === 'completed' ? 'bg-olive-500' : 'bg-critical-500'
                  : 'bg-surface-300 dark:bg-surface-600'
              }`} />
            )}

            {/* Node */}
            <button
              onClick={() => onActionClick?.(action)}
              className={`
                relative flex-shrink-0 w-6 h-6 rounded-full transition-all
                ${getNodeColor()}
                ${isCurrent ? 'ring-2 ring-aura-300 dark:ring-aura-700 scale-125' : 'hover:scale-110'}
              `}
              title={`${action.type}: ${action.target}`}
            >
              {action.status === 'completed' && (
                <CheckCircleIcon className="w-4 h-4 text-white absolute inset-1" />
              )}
              {(action.status === 'failed' || action.status === 'denied') && (
                <XCircleIcon className="w-4 h-4 text-white absolute inset-1" />
              )}
              {action.status === 'executing' && (
                <ArrowPathIcon className="w-4 h-4 text-white absolute inset-1 animate-spin" />
              )}
              {action.status === 'awaiting_approval' && (
                <HandRaisedIcon className="w-4 h-4 text-white absolute inset-1" />
              )}
            </button>
          </Fragment>
        );
      })}
    </div>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

/**
 * Execution Timeline
 *
 * @param {Object} props
 * @param {boolean} props.compact - Use compact horizontal layout
 * @param {boolean} props.collapsible - Allow collapsing
 * @param {boolean} props.defaultExpanded - Default expanded state
 * @param {function} props.onActionClick - Callback when action is clicked
 */
export default function ExecutionTimeline({
  compact = false,
  collapsible = true,
  defaultExpanded = true,
  onActionClick,
}) {
  const {
    actions,
    completedActions,
    pendingActions,
    executingActions,
    progress,
  } = useExecutionTimeline();

  const { currentAction, executionStatus, execution } = useExecution();

  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  // Calculate time elapsed
  const timeElapsed = useMemo(() => {
    if (!execution?.started_at) return null;
    return formatDuration(new Date(execution.started_at).getTime());
  }, [execution?.started_at]);

  // Handle action click
  const handleActionClick = useCallback((action) => {
    onActionClick?.(action);
  }, [onActionClick]);

  // Don't render if no actions
  if (!actions || actions.length === 0) {
    return (
      <div className="p-6 text-center text-surface-500 dark:text-surface-400">
        <ClockIcon className="w-12 h-12 mx-auto mb-3 opacity-50" />
        <p className="text-sm">No actions in this execution</p>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-surface-100/50 dark:border-surface-700/30">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
            <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100">
              Execution Timeline
            </h3>
            <div className="flex items-center gap-2 text-xs text-surface-500 dark:text-surface-400">
              <span className="flex items-center gap-1">
                <CheckCircleIcon className="w-3.5 h-3.5 text-olive-500" />
                {completedActions.length}
              </span>
              <span className="text-surface-300 dark:text-surface-600">|</span>
              <span className="flex items-center gap-1">
                <ArrowPathIcon className={`w-3.5 h-3.5 ${executingActions.length > 0 ? 'text-aura-500 animate-spin' : 'text-surface-400'}`} />
                {executingActions.length}
              </span>
              <span className="text-surface-300 dark:text-surface-600">|</span>
              <span className="flex items-center gap-1">
                <ClockIcon className="w-3.5 h-3.5 text-surface-400" />
                {pendingActions.length}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {timeElapsed && (
              <span className="text-xs text-surface-500 dark:text-surface-400 font-mono">
                {timeElapsed} elapsed
              </span>
            )}

            {collapsible && (
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="p-1 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 hover:bg-surface-50 dark:hover:bg-surface-700 rounded-lg transition-all duration-200 ease-[var(--ease-tahoe)]"
              >
                {isExpanded ? (
                  <ChevronUpIcon className="w-4 h-4" />
                ) : (
                  <ChevronDownIcon className="w-4 h-4" />
                )}
              </button>
            )}
          </div>
        </div>

        {/* Progress bar */}
        <ProgressBar progress={progress} status={executionStatus} />

        {/* Progress text */}
        <div className="flex items-center justify-between mt-2 text-xs text-surface-500 dark:text-surface-400">
          <span>
            {completedActions.length} of {actions.length} actions completed
          </span>
          <span className="font-medium">
            {progress}%
          </span>
        </div>
      </div>

      {/* Timeline content */}
      {isExpanded && (
        <div className="p-4">
          {compact ? (
            <CompactTimeline
              actions={actions}
              currentActionId={currentAction?.action_id}
              onActionClick={handleActionClick}
            />
          ) : (
            <div className="space-y-0">
              {actions.map((action, index) => (
                <TimelineNode
                  key={action.action_id}
                  action={action}
                  isFirst={index === 0}
                  isLast={index === actions.length - 1}
                  isCurrent={action.action_id === currentAction?.action_id}
                  onClick={handleActionClick}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Current action highlight (collapsed state) */}
      {!isExpanded && currentAction && (
        <div className="px-4 py-3 bg-warning-50/80 dark:bg-warning-900/20 backdrop-blur-sm border-t border-warning-200/50 dark:border-warning-800/50">
          <div className="flex items-center gap-2 text-sm text-warning-700 dark:text-warning-400">
            <HandRaisedIcon className="w-4 h-4 animate-pulse" />
            <span className="font-medium">Awaiting approval:</span>
            <span className="truncate font-mono text-xs">
              {currentAction.target}
            </span>
          </div>
        </div>
      )}

      {/* Error state */}
      {executionStatus === 'failed' && (
        <div className="px-4 py-3 bg-critical-50/80 dark:bg-critical-900/20 backdrop-blur-sm border-t border-critical-200/50 dark:border-critical-800/50">
          <div className="flex items-center gap-2 text-sm text-critical-700 dark:text-critical-400">
            <ExclamationTriangleIcon className="w-4 h-4" />
            <span className="font-medium">Execution failed</span>
          </div>
        </div>
      )}

      {/* Completed state */}
      {executionStatus === 'completed' && (
        <div className="px-4 py-3 bg-olive-50/80 dark:bg-olive-900/20 backdrop-blur-sm border-t border-olive-200/50 dark:border-olive-800/50">
          <div className="flex items-center gap-2 text-sm text-olive-700 dark:text-olive-400">
            <CheckCircleIcon className="w-4 h-4" />
            <span className="font-medium">Execution completed successfully</span>
          </div>
        </div>
      )}

      {/* Aborted state */}
      {executionStatus === 'aborted' && (
        <div className="px-4 py-3 bg-warning-50/80 dark:bg-warning-900/20 backdrop-blur-sm border-t border-warning-200/50 dark:border-warning-800/50">
          <div className="flex items-center gap-2 text-sm text-warning-700 dark:text-warning-400">
            <XCircleIcon className="w-4 h-4" />
            <span className="font-medium">Execution aborted by user</span>
          </div>
        </div>
      )}
    </div>
  );
}
