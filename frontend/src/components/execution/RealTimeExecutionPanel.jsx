/**
 * Project Aura - Real-Time Execution Panel Component
 *
 * Main container for the agent intervention UI, combining:
 * - Streaming view of agent execution
 * - Action approval cards as they appear
 * - Execution timeline
 * - Trust settings panel
 * - Live logs and thinking stream
 *
 * Similar to Claude Code's tool approval model and Antigravity's intervention feature.
 *
 * @see Design Principles: Apple-inspired, Claude Code-style
 */

import { useState, useEffect, useRef } from 'react';
import {
  PlayIcon,
  NoSymbolIcon,
  ArrowPathIcon,
  CogIcon,
  CommandLineIcon,
  CpuChipIcon,
  EyeIcon,
  XMarkIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  SignalIcon,
  SignalSlashIcon,
  ChevronDoubleRightIcon,
  ListBulletIcon,
  ClockIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline';

import { useExecution, ExecutionProvider } from '../../context/ExecutionContext';
import ActionApprovalCard from './ActionApprovalCard';
import ActionModifyModal from './ActionModifyModal';
import ExecutionTimeline from './ExecutionTimeline';
import TrustSettingsPanel from './TrustSettingsPanel';

// =============================================================================
// SUB-COMPONENTS
// =============================================================================

/**
 * Connection Status Indicator
 */
function ConnectionStatus() {
  const { connectionStatus, connectionError, connect } = useExecution();

  const statusConfig = {
    connected: {
      icon: SignalIcon,
      label: 'Connected',
      className: 'text-olive-600 dark:text-olive-400 bg-olive-100 dark:bg-olive-900/30',
      iconClass: 'text-olive-500',
    },
    connecting: {
      icon: ArrowPathIcon,
      label: 'Connecting',
      className: 'text-warning-600 dark:text-warning-400 bg-warning-100 dark:bg-warning-900/30',
      iconClass: 'text-warning-500 animate-spin',
    },
    reconnecting: {
      icon: ArrowPathIcon,
      label: 'Reconnecting',
      className: 'text-warning-600 dark:text-warning-400 bg-warning-100 dark:bg-warning-900/30',
      iconClass: 'text-warning-500 animate-spin',
    },
    disconnected: {
      icon: SignalSlashIcon,
      label: 'Disconnected',
      className: 'text-critical-600 dark:text-critical-400 bg-critical-100 dark:bg-critical-900/30',
      iconClass: 'text-critical-500',
    },
  };

  const config = statusConfig[connectionStatus] || statusConfig.disconnected;
  const Icon = config.icon;

  return (
    <div className="flex items-center gap-2">
      <div className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium ${config.className}`}>
        <Icon className={`w-3.5 h-3.5 ${config.iconClass}`} />
        <span>{config.label}</span>
      </div>

      {connectionStatus === 'disconnected' && (
        <button
          onClick={connect}
          className="text-xs text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300 underline"
        >
          Retry
        </button>
      )}

      {connectionError && (
        <span className="text-xs text-critical-600 dark:text-critical-400 truncate max-w-[200px]" title={connectionError}>
          {connectionError}
        </span>
      )}
    </div>
  );
}

/**
 * Execution Controls
 */
function ExecutionControls() {
  const { executionStatus, abortExecution, loading, hasCurrentAction } = useExecution();

  const isActive = ['connecting', 'connected', 'executing'].includes(executionStatus);

  return (
    <div className="flex items-center gap-2">
      {isActive && (
        <button
          onClick={() => abortExecution('User requested abort')}
          disabled={loading.abort}
          className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-critical-600 dark:text-critical-400 border border-critical-300 dark:border-critical-700 rounded-lg hover:bg-critical-50 dark:hover:bg-critical-900/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading.abort ? (
            <ArrowPathIcon className="w-4 h-4 animate-spin" />
          ) : (
            <NoSymbolIcon className="w-4 h-4" />
          )}
          Abort
        </button>
      )}

      {hasCurrentAction && (
        <div className="flex items-center gap-1 px-2 py-1 bg-warning-100 dark:bg-warning-900/30 text-warning-700 dark:text-warning-400 rounded-lg text-xs font-medium animate-pulse">
          <ExclamationTriangleIcon className="w-4 h-4" />
          <span>Action requires approval</span>
        </div>
      )}
    </div>
  );
}

/**
 * Thinking Stream Panel
 */
function ThinkingStream() {
  const { thinking, executionStatus } = useExecution();
  const streamEndRef = useRef(null);

  useEffect(() => {
    streamEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [thinking]);

  const typeConfig = {
    analysis: { icon: EyeIcon, color: 'aura', label: 'Analyzing' },
    planning: { icon: ListBulletIcon, color: 'olive', label: 'Planning' },
    decision: { icon: CheckCircleIcon, color: 'warning', label: 'Deciding' },
    risk_assessment: { icon: ShieldCheckIcon, color: 'critical', label: 'Risk Assessment' },
  };

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 bg-surface-50 dark:bg-surface-800 border-b border-surface-100/50 dark:border-surface-700/30 flex items-center justify-between">
        <h4 className="text-sm font-medium text-surface-700 dark:text-surface-300 flex items-center gap-2">
          <CpuChipIcon className="w-4 h-4" />
          Agent Thinking
        </h4>
        {executionStatus === 'executing' && (
          <span className="text-xs text-aura-600 dark:text-aura-400 flex items-center gap-1">
            <span className="flex gap-0.5">
              <span className="w-1.5 h-1.5 rounded-full bg-aura-500 animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-1.5 h-1.5 rounded-full bg-aura-500 animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-1.5 h-1.5 rounded-full bg-aura-500 animate-bounce" style={{ animationDelay: '300ms' }} />
            </span>
          </span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4 bg-white dark:bg-surface-800">
        {thinking.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-surface-400 dark:text-surface-500">
            <CpuChipIcon className="w-12 h-12 mb-3 opacity-50" />
            <p className="text-sm">Waiting for agent thoughts...</p>
          </div>
        ) : (
          <div className="space-y-4">
            {thinking.map((thought, index) => {
              const config = typeConfig[thought.type] || typeConfig.analysis;
              const Icon = config.icon;
              const isLast = index === thinking.length - 1;

              return (
                <div key={thought.id || index} className="relative flex gap-3">
                  {/* Connector line */}
                  {!isLast && (
                    <div className="absolute left-4 top-8 bottom-0 w-px bg-surface-200 dark:bg-surface-700" />
                  )}

                  {/* Icon */}
                  <div className={`relative z-10 flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-${config.color}-100 dark:bg-${config.color}-900/30`}>
                    <Icon className={`w-4 h-4 text-${config.color}-600 dark:text-${config.color}-400`} />
                  </div>

                  {/* Content */}
                  <div className="flex-1 pb-2">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-xs font-medium uppercase tracking-wide text-${config.color}-600 dark:text-${config.color}-400`}>
                        {config.label}
                      </span>
                      {thought.timestamp && (
                        <span className="text-[10px] text-surface-400 dark:text-surface-500">
                          {new Date(thought.timestamp).toLocaleTimeString()}
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-surface-700 dark:text-surface-300 leading-relaxed">
                      {thought.content}
                    </p>
                  </div>
                </div>
              );
            })}
            <div ref={streamEndRef} />
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Log Stream Panel
 */
function LogStream() {
  const { logs } = useExecution();
  const logsEndRef = useRef(null);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const levelConfig = {
    info: { icon: InformationCircleIcon, color: 'text-aura-500' },
    warning: { icon: ExclamationTriangleIcon, color: 'text-warning-500' },
    error: { icon: XMarkIcon, color: 'text-critical-500' },
    success: { icon: CheckCircleIcon, color: 'text-olive-500' },
    debug: { icon: CogIcon, color: 'text-surface-400' },
  };

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 bg-surface-50 dark:bg-surface-800 border-b border-surface-100/50 dark:border-surface-700/30 flex items-center justify-between">
        <h4 className="text-sm font-medium text-surface-700 dark:text-surface-300 flex items-center gap-2">
          <CommandLineIcon className="w-4 h-4" />
          Execution Log
        </h4>
        <span className="text-xs text-surface-400 dark:text-surface-500">
          {logs.length} entries
        </span>
      </div>

      <div className="flex-1 overflow-y-auto bg-surface-900/95 dark:bg-surface-950/95 backdrop-blur-sm font-mono text-xs">
        {logs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-surface-500">
            <CommandLineIcon className="w-12 h-12 mb-3 opacity-50" />
            <p className="text-sm">No logs yet</p>
          </div>
        ) : (
          <div className="py-2">
            {logs.map((log, index) => {
              const config = levelConfig[log.level] || levelConfig.info;
              const Icon = config.icon;
              const timestamp = log.timestamp
                ? new Date(log.timestamp).toLocaleTimeString('en-US', { hour12: false })
                : '';

              return (
                <div
                  key={index}
                  className="flex items-start gap-2 px-3 py-1.5 hover:bg-surface-800 dark:hover:bg-surface-900 transition-colors"
                >
                  <span className="text-surface-500 w-16 flex-shrink-0">
                    {timestamp}
                  </span>
                  <Icon className={`w-3.5 h-3.5 flex-shrink-0 mt-0.5 ${config.color}`} />
                  <span className="text-surface-300 flex-1 break-all">
                    {log.message}
                  </span>
                </div>
              );
            })}
            <div ref={logsEndRef} />
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Current Action Panel
 */
function CurrentActionPanel() {
  const { currentAction, hasCurrentAction, actions } = useExecution();

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="px-4 py-3 bg-surface-50 dark:bg-surface-800 border-b border-surface-100/50 dark:border-surface-700/30">
        <h4 className="text-sm font-medium text-surface-700 dark:text-surface-300 flex items-center gap-2">
          <ChevronDoubleRightIcon className="w-4 h-4" />
          Pending Actions
        </h4>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {hasCurrentAction ? (
          <>
            {/* Current action highlighted */}
            <ActionApprovalCard
              action={currentAction}
              isCurrentAction={true}
            />

            {/* Other pending actions */}
            {actions
              .filter(a => a.status === 'pending' && a.action_id !== currentAction?.action_id)
              .map((action) => (
                <ActionApprovalCard
                  key={action.action_id}
                  action={action}
                  isCurrentAction={false}
                  compact={true}
                />
              ))}
          </>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-surface-400 dark:text-surface-500">
            <ClockIcon className="w-12 h-12 mb-3 opacity-50" />
            <p className="text-sm font-medium">No actions pending</p>
            <p className="text-xs mt-1">Actions will appear here when they need approval</p>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Keyboard Shortcuts Help
 */
function KeyboardShortcutsHelp({ isOpen, onClose }) {
  if (!isOpen) return null;

  const shortcuts = [
    { key: 'A', description: 'Approve current action' },
    { key: 'D', description: 'Deny current action' },
    { key: 'M', description: 'Modify current action' },
    { key: 'T', description: 'Trust this action type for session' },
    { key: 'Esc', description: 'Abort execution / Close modal' },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="fixed inset-0 glass-backdrop"
        onClick={onClose}
      />
      <div className="
        relative p-6 w-full max-w-sm
        bg-white/95 dark:bg-surface-800/95
        backdrop-blur-xl backdrop-saturate-150
        rounded-2xl
        border border-white/50 dark:border-surface-700/50
        shadow-[var(--shadow-glass-hover)]
        animate-in fade-in zoom-in-95 duration-[var(--duration-overlay)] ease-[var(--ease-tahoe)]
      ">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
            Keyboard Shortcuts
          </h3>
          <button
            onClick={onClose}
            className="p-1.5 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 hover:bg-white/60 dark:hover:bg-surface-700 rounded-lg transition-all duration-200 ease-[var(--ease-tahoe)]"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>
        <div className="space-y-3">
          {shortcuts.map((shortcut) => (
            <div key={shortcut.key} className="flex items-center justify-between">
              <span className="text-sm text-surface-600 dark:text-surface-400">
                {shortcut.description}
              </span>
              <kbd className="px-2 py-1 text-xs font-mono bg-white dark:bg-surface-700 text-surface-700 dark:text-surface-300 rounded-lg border border-surface-200/50 dark:border-surface-600/50">
                {shortcut.key}
              </kbd>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

/**
 * Real-Time Execution Panel Inner Component
 */
function RealTimeExecutionPanelInner({ executionId, onClose }) {
  const {
    subscribeToExecution,
    unsubscribeFromExecution,
    executionStatus: _executionStatus,
    execution,
    setTrustPanelOpen,
    trustPanelOpen,
    currentAction: _currentAction,
  } = useExecution();

  // Local state
  const [showHelp, setShowHelp] = useState(false);
  const [activeTab, setActiveTab] = useState('actions'); // 'actions' | 'thinking' | 'logs'

  // Subscribe to execution on mount
  useEffect(() => {
    if (executionId) {
      subscribeToExecution(executionId);
    }

    return () => {
      unsubscribeFromExecution();
    };
  }, [executionId, subscribeToExecution, unsubscribeFromExecution]);

  // Keyboard shortcut for help
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === '?' && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        setShowHelp(true);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const tabs = [
    { id: 'actions', label: 'Actions', icon: ChevronDoubleRightIcon },
    { id: 'thinking', label: 'Thinking', icon: CpuChipIcon },
    { id: 'logs', label: 'Logs', icon: CommandLineIcon },
  ];

  return (
    <div className="flex flex-col h-full bg-surface-50/50 dark:bg-surface-900/50">
      {/* Header */}
      <header className="px-4 py-3 bg-white dark:bg-surface-800 backdrop-blur-xl border-b border-surface-100/50 dark:border-surface-700/30">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-aura-100 dark:bg-aura-900/30 rounded-lg">
              <PlayIcon className="w-5 h-5 text-aura-600 dark:text-aura-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
                Live Execution
              </h2>
              <p className="text-sm text-surface-500 dark:text-surface-400 truncate max-w-md">
                {execution?.task || 'Waiting for execution...'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <ConnectionStatus />
            <ExecutionControls />

            <button
              onClick={() => setTrustPanelOpen(!trustPanelOpen)}
              className={`
                p-2 rounded-xl transition-all duration-200 ease-[var(--ease-tahoe)]
                ${trustPanelOpen
                  ? 'bg-aura-100 dark:bg-aura-900/30 text-aura-600 dark:text-aura-400'
                  : 'text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 hover:bg-white/60 dark:hover:bg-surface-700'
                }
              `}
              title="Trust Settings"
            >
              <ShieldCheckIcon className="w-5 h-5" />
            </button>

            <button
              onClick={() => setShowHelp(true)}
              className="p-2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 hover:bg-white/60 dark:hover:bg-surface-700 rounded-xl transition-all duration-200 ease-[var(--ease-tahoe)]"
              title="Keyboard shortcuts"
            >
              <span className="text-xs font-mono">?</span>
            </button>

            {onClose && (
              <button
                onClick={onClose}
                className="p-2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 hover:bg-white/60 dark:hover:bg-surface-700 rounded-xl transition-all duration-200 ease-[var(--ease-tahoe)]"
              >
                <XMarkIcon className="w-5 h-5" />
              </button>
            )}
          </div>
        </div>

        {/* Mobile tabs */}
        <div className="flex gap-1 md:hidden">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`
                flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium rounded-xl transition-all duration-200 ease-[var(--ease-tahoe)]
                ${activeTab === tab.id
                  ? 'bg-aura-100 dark:bg-aura-900/30 text-aura-700 dark:text-aura-400'
                  : 'text-surface-600 dark:text-surface-400 hover:bg-white/60 dark:hover:bg-surface-700'
                }
              `}
            >
              <tab.icon className="w-4 h-4" />
              <span className="hidden sm:inline">{tab.label}</span>
            </button>
          ))}
        </div>
      </header>

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Timeline */}
        <div className="hidden lg:block w-72 border-r border-surface-100/50 dark:border-surface-700/30 overflow-y-auto p-4">
          <ExecutionTimeline
            collapsible={false}
            defaultExpanded={true}
          />
        </div>

        {/* Center: Main panels */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Desktop: Split view */}
          <div className="hidden md:flex flex-1 overflow-hidden">
            {/* Actions panel */}
            <div className="flex-1 border-r border-surface-100/50 dark:border-surface-700/30">
              <CurrentActionPanel />
            </div>

            {/* Thinking/Logs split */}
            <div className="w-[400px] flex flex-col">
              <div className="flex-1 border-b border-surface-100/50 dark:border-surface-700/30 overflow-hidden">
                <ThinkingStream />
              </div>
              <div className="h-48 overflow-hidden">
                <LogStream />
              </div>
            </div>
          </div>

          {/* Mobile: Tab content */}
          <div className="flex-1 overflow-hidden md:hidden">
            {activeTab === 'actions' && <CurrentActionPanel />}
            {activeTab === 'thinking' && <ThinkingStream />}
            {activeTab === 'logs' && <LogStream />}
          </div>
        </div>

        {/* Right: Trust settings panel */}
        {trustPanelOpen && (
          <div className="w-80 border-l border-surface-100/50 dark:border-surface-700/30">
            <TrustSettingsPanel
              isOpen={trustPanelOpen}
              onClose={() => setTrustPanelOpen(false)}
            />
          </div>
        )}
      </div>

      {/* Modals */}
      <ActionModifyModal />
      <KeyboardShortcutsHelp isOpen={showHelp} onClose={() => setShowHelp(false)} />
    </div>
  );
}

// =============================================================================
// EXPORT WITH PROVIDER
// =============================================================================

/**
 * Real-Time Execution Panel
 *
 * Main container for the agent intervention UI.
 * Wraps content with ExecutionProvider for state management.
 *
 * @param {Object} props
 * @param {string} props.executionId - ID of the execution to stream
 * @param {function} props.onClose - Close callback
 */
export default function RealTimeExecutionPanel({ executionId, onClose }) {
  return (
    <ExecutionProvider>
      <RealTimeExecutionPanelInner executionId={executionId} onClose={onClose} />
    </ExecutionProvider>
  );
}
