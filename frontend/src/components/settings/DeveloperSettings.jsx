/**
 * Developer Settings Tab Component
 *
 * Provides developer/debug mode settings for advanced users.
 * Includes performance bar, API inspector, log levels, and more.
 */

import { useState, useEffect } from 'react';
import {
  CommandLineIcon,
  ShieldCheckIcon,
  ExclamationTriangleIcon,
  ChartBarIcon,
  DocumentMagnifyingGlassIcon,
  BeakerIcon,
  CpuChipIcon,
  CircleStackIcon,
  SignalIcon,
  XMarkIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';
import {
  useDeveloperMode,
  LOG_LEVELS,
  NETWORK_PRESETS,
  SESSION_TIMEOUTS,
  FEATURE_FLAGS,
} from '../../context/DeveloperModeContext';

export default function DeveloperSettings({ onSuccess, onError: _onError }) {
  const {
    enabled,
    sessionTimeout,
    performanceBar,
    logLevel,
    apiInspector,
    featureFlags,
    graphRAGDebug,
    agentTraceViewer,
    mockDataMode,
    networkThrottling,
    enableDevMode,
    disableDevMode,
    togglePerformanceBar,
    setLogLevel,
    toggleApiInspector,
    toggleFeatureFlag,
    toggleGraphRAGDebug,
    toggleAgentTraceViewer,
    toggleMockDataMode,
    setNetworkThrottling,
    getSessionTimeRemaining,
  } = useDeveloperMode();

  const [selectedTimeout, setSelectedTimeout] = useState(sessionTimeout);
  const [timeRemaining, setTimeRemaining] = useState(null);

  // Update time remaining every second
  useEffect(() => {
    if (!enabled) {
      setTimeRemaining(null);
      return;
    }

    const updateTime = () => {
      const remaining = getSessionTimeRemaining();
      setTimeRemaining(remaining);
    };

    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, [enabled, getSessionTimeRemaining]);

  // Format time remaining
  const formatTimeRemaining = (seconds) => {
    if (seconds === null) return 'No timeout';
    if (seconds <= 0) return 'Expired';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    if (mins >= 60) {
      const hours = Math.floor(mins / 60);
      const remainingMins = mins % 60;
      return `${hours}h ${remainingMins}m`;
    }
    return `${mins}m ${secs}s`;
  };

  const handleEnableDevMode = () => {
    enableDevMode(selectedTimeout);
    onSuccess?.('Developer mode enabled');
  };

  const handleDisableDevMode = () => {
    disableDevMode();
    onSuccess?.('Developer mode disabled');
  };

  return (
    <div className="max-w-4xl space-y-6">
      {/* Admin Only Badge */}
      <div className="flex items-center gap-2 text-sm text-surface-500 dark:text-surface-400">
        <ShieldCheckIcon className="h-4 w-4" />
        <span>Admin Only</span>
      </div>

      {/* Warning Banner when enabled */}
      {enabled && (
        <div className="bg-warning-50/90 dark:bg-warning-900/20 backdrop-blur-sm border border-warning-200/50 dark:border-warning-800/50 rounded-xl p-4 flex items-start gap-3 shadow-[var(--shadow-glass)]">
          <ExclamationTriangleIcon className="h-5 w-5 text-warning-600 dark:text-warning-400 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="font-medium text-warning-800 dark:text-warning-200">Developer Mode Active</p>
            <p className="text-sm text-warning-700 dark:text-warning-300 mt-1">
              Debug information is being logged to the console. Performance may be affected.
              {timeRemaining !== null && (
                <span className="ml-2 font-medium">
                  Session expires in: {formatTimeRemaining(timeRemaining)}
                </span>
              )}
            </p>
          </div>
          <button
            onClick={handleDisableDevMode}
            className="p-1.5 hover:bg-warning-100 dark:hover:bg-warning-800/30 rounded-lg transition-colors"
          >
            <XMarkIcon className="h-5 w-5 text-warning-600 dark:text-warning-400" />
          </button>
        </div>
      )}

      {/* Master Toggle Card */}
      <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 p-6 shadow-[var(--shadow-glass)]">
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-4">
            <div className="p-3 bg-aura-100/80 dark:bg-aura-900/30 rounded-xl">
              <CommandLineIcon className="h-6 w-6 text-aura-600 dark:text-aura-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
                Developer Mode
              </h3>
              <p className="text-sm text-surface-500 dark:text-surface-400 mt-1">
                Enable advanced debugging tools and performance monitoring
              </p>
            </div>
          </div>
          <button
            onClick={enabled ? handleDisableDevMode : handleEnableDevMode}
            className={`
              relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent
              transition-all duration-200 ease-[var(--ease-tahoe)] focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2 dark:focus:ring-offset-surface-800
              ${enabled ? 'bg-aura-600 shadow-sm' : 'bg-surface-200 dark:bg-surface-600'}
            `}
          >
            <span
              className={`
                pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-sm ring-0
                transition-all duration-200 ease-[var(--ease-tahoe)]
                ${enabled ? 'translate-x-5' : 'translate-x-0'}
              `}
            />
          </button>
        </div>

        {/* Session Timeout Selector */}
        <div className="mt-6 pt-6 border-t border-surface-200/50 dark:border-surface-700/30">
          <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-3">
            Session Timeout
          </label>
          <div className="flex flex-wrap gap-2">
            {SESSION_TIMEOUTS.map((option) => (
              <button
                key={option.value ?? 'never'}
                onClick={() => setSelectedTimeout(option.value)}
                disabled={enabled}
                className={`
                  px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200
                  ${selectedTimeout === option.value
                    ? 'bg-aura-100 dark:bg-aura-900/30 text-aura-700 dark:text-aura-300 ring-2 ring-aura-500'
                    : 'bg-surface-100 dark:bg-surface-700/50 text-surface-600 dark:text-surface-400 hover:bg-surface-200 dark:hover:bg-surface-700'
                  }
                  ${enabled ? 'opacity-50 cursor-not-allowed' : ''}
                `}
              >
                {option.label}
              </button>
            ))}
          </div>
          <p className="mt-2 text-xs text-surface-400 dark:text-surface-500">
            Developer mode will automatically disable after the selected timeout
          </p>
        </div>
      </div>

      {/* P0 Features */}
      {enabled && (
        <>
          {/* Performance Bar */}
          <SettingsCard
            icon={ChartBarIcon}
            title="Performance Bar"
            description="Display real-time performance metrics overlay"
            shortcut="⌘+Shift+P"
            enabled={performanceBar.enabled}
            onToggle={togglePerformanceBar}
          >
            <div className="mt-4 grid grid-cols-2 lg:grid-cols-4 gap-3">
              <MetricPreview label="API" value="45ms" subvalue="12 calls" />
              <MetricPreview label="DB" value="23ms" subvalue="8 queries" />
              <MetricPreview label="Cache" value="95%" subvalue="hit rate" />
              <MetricPreview label="Memory" value="128MB" subvalue="heap" />
            </div>
          </SettingsCard>

          {/* Log Level */}
          <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 p-6 shadow-[var(--shadow-glass)]">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-surface-100/80 dark:bg-surface-700/50 rounded-xl">
                <DocumentMagnifyingGlassIcon className="h-6 w-6 text-surface-600 dark:text-surface-400" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
                  Console Log Level
                </h3>
                <p className="text-sm text-surface-500 dark:text-surface-400 mt-1">
                  Control the verbosity of debug output in browser console
                </p>

                <div className="mt-4 flex rounded-xl bg-surface-100 dark:bg-surface-700/50 p-1">
                  {Object.values(LOG_LEVELS).map((level) => (
                    <button
                      key={level}
                      onClick={() => setLogLevel(level)}
                      className={`
                        flex-1 py-2 px-3 rounded-lg text-sm font-medium capitalize transition-all duration-200
                        ${logLevel === level
                          ? 'bg-white dark:bg-surface-600 text-surface-900 dark:text-surface-100 shadow-sm'
                          : 'text-surface-500 dark:text-surface-400 hover:text-surface-700 dark:hover:text-surface-300'
                        }
                      `}
                    >
                      {level}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* P1 Features */}
          <div className="pt-4">
            <h4 className="text-sm font-semibold text-surface-500 dark:text-surface-400 uppercase tracking-wider mb-4">
              Inspection Tools
            </h4>

            {/* API Inspector */}
            <SettingsCard
              icon={SignalIcon}
              title="API Inspector"
              description="Capture and view all API request/response payloads"
              enabled={apiInspector.enabled}
              onToggle={toggleApiInspector}
            />

            {/* GraphRAG Debug */}
            <SettingsCard
              icon={CircleStackIcon}
              title="GraphRAG Debug View"
              description="Visualize graph traversals and vector search queries"
              enabled={graphRAGDebug}
              onToggle={toggleGraphRAGDebug}
              className="mt-4"
            />

            {/* Agent Trace Viewer */}
            <SettingsCard
              icon={CpuChipIcon}
              title="Agent Trace Viewer"
              description="View detailed execution traces for agent actions"
              enabled={agentTraceViewer}
              onToggle={toggleAgentTraceViewer}
              className="mt-4"
            />
          </div>

          {/* Feature Flags */}
          <div className="pt-4">
            <h4 className="text-sm font-semibold text-surface-500 dark:text-surface-400 uppercase tracking-wider mb-4">
              Feature Flag Overrides
            </h4>

            <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 p-6 shadow-[var(--shadow-glass)]">
              <div className="flex items-center gap-2 mb-4">
                <BeakerIcon className="h-5 w-5 text-aura-600 dark:text-aura-400" />
                <span className="text-sm text-surface-500 dark:text-surface-400">
                  Session-only overrides (not persisted)
                </span>
              </div>

              <div className="space-y-3">
                {FEATURE_FLAGS.map((flag) => (
                  <div
                    key={flag.id}
                    className="flex items-center justify-between py-3 border-b border-surface-100 dark:border-surface-700/50 last:border-0"
                  >
                    <div>
                      <p className="font-medium text-surface-900 dark:text-surface-100">
                        {flag.label}
                      </p>
                      <p className="text-sm text-surface-500 dark:text-surface-400">
                        {flag.description}
                      </p>
                    </div>
                    <button
                      onClick={() => toggleFeatureFlag(flag.id)}
                      className={`
                        relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent
                        transition-all duration-200 ease-[var(--ease-tahoe)]
                        ${featureFlags[flag.id] ? 'bg-aura-600' : 'bg-surface-200 dark:bg-surface-600'}
                      `}
                    >
                      <span
                        className={`
                          pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-sm
                          transition-all duration-200 ease-[var(--ease-tahoe)]
                          ${featureFlags[flag.id] ? 'translate-x-4' : 'translate-x-0'}
                        `}
                      />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* P2 Features */}
          <div className="pt-4">
            <h4 className="text-sm font-semibold text-surface-500 dark:text-surface-400 uppercase tracking-wider mb-4">
              Testing Tools
            </h4>

            {/* Mock Data Mode */}
            <SettingsCard
              icon={CircleStackIcon}
              title="Mock Data Mode"
              description="Use simulated data instead of real API responses"
              enabled={mockDataMode}
              onToggle={toggleMockDataMode}
            />

            {/* Network Throttling */}
            <div className="mt-4 bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 p-6 shadow-[var(--shadow-glass)]">
              <div className="flex items-start gap-4">
                <div className="p-3 bg-surface-100/80 dark:bg-surface-700/50 rounded-xl">
                  <SignalIcon className="h-6 w-6 text-surface-600 dark:text-surface-400" />
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
                    Network Throttling
                  </h3>
                  <p className="text-sm text-surface-500 dark:text-surface-400 mt-1">
                    Simulate different network conditions for testing
                  </p>

                  <div className="mt-4 flex flex-wrap gap-2">
                    {Object.values(NETWORK_PRESETS).map((preset) => (
                      <button
                        key={preset.id}
                        onClick={() => setNetworkThrottling(preset.id)}
                        className={`
                          px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200
                          ${networkThrottling === preset.id
                            ? 'bg-aura-100 dark:bg-aura-900/30 text-aura-700 dark:text-aura-300 ring-2 ring-aura-500'
                            : 'bg-surface-100 dark:bg-surface-700/50 text-surface-600 dark:text-surface-400 hover:bg-surface-200 dark:hover:bg-surface-700'
                          }
                        `}
                      >
                        {preset.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Info Footer */}
          <div className="flex items-start gap-3 p-4 bg-surface-50 dark:bg-surface-800/50 rounded-xl">
            <InformationCircleIcon className="h-5 w-5 text-surface-400 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-surface-500 dark:text-surface-400">
              <p>
                Developer mode settings are stored locally and persist across sessions until timeout.
                These tools are intended for debugging and development purposes only.
              </p>
              <p className="mt-2">
                <strong>Keyboard shortcuts:</strong> Press <kbd className="px-1.5 py-0.5 bg-surface-200 dark:bg-surface-700 rounded text-xs">⌘+Shift+P</kbd> to toggle Performance Bar
              </p>
            </div>
          </div>
        </>
      )}

      {/* Disabled State */}
      {!enabled && (
        <div className="text-center py-12">
          <CommandLineIcon className="h-16 w-16 text-surface-300 dark:text-surface-600 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-surface-900 dark:text-surface-100 mb-2">
            Developer Mode Disabled
          </h3>
          <p className="text-surface-500 dark:text-surface-400 max-w-md mx-auto">
            Enable developer mode to access performance monitoring, API inspection,
            feature flag overrides, and other debugging tools.
          </p>
        </div>
      )}
    </div>
  );
}

// Settings Card Component
function SettingsCard({ icon: Icon, title, description, shortcut, enabled, onToggle, children, className = '' }) {
  return (
    <div className={`bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 p-6 shadow-[var(--shadow-glass)] ${className}`}>
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          <div className={`p-3 rounded-xl ${enabled ? 'bg-aura-100/80 dark:bg-aura-900/30' : 'bg-surface-100/80 dark:bg-surface-700/50'}`}>
            <Icon className={`h-6 w-6 ${enabled ? 'text-aura-600 dark:text-aura-400' : 'text-surface-600 dark:text-surface-400'}`} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
                {title}
              </h3>
              {shortcut && (
                <kbd className="px-1.5 py-0.5 bg-surface-100 dark:bg-surface-700 rounded text-xs text-surface-500 dark:text-surface-400">
                  {shortcut}
                </kbd>
              )}
            </div>
            <p className="text-sm text-surface-500 dark:text-surface-400 mt-1">
              {description}
            </p>
          </div>
        </div>
        <button
          onClick={onToggle}
          className={`
            relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent
            transition-all duration-200 ease-[var(--ease-tahoe)] focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2 dark:focus:ring-offset-surface-800
            ${enabled ? 'bg-aura-600 shadow-sm' : 'bg-surface-200 dark:bg-surface-600'}
          `}
        >
          <span
            className={`
              pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-sm ring-0
              transition-all duration-200 ease-[var(--ease-tahoe)]
              ${enabled ? 'translate-x-5' : 'translate-x-0'}
            `}
          />
        </button>
      </div>
      {children}
    </div>
  );
}

// Metric Preview Component
function MetricPreview({ label, value, subvalue }) {
  return (
    <div className="bg-surface-50 dark:bg-surface-700/30 rounded-lg p-3 text-center">
      <p className="text-xs font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wide">
        {label}
      </p>
      <p className="text-lg font-bold text-surface-900 dark:text-surface-100 mt-1">
        {value}
      </p>
      <p className="text-xs text-surface-400 dark:text-surface-500">
        {subvalue}
      </p>
    </div>
  );
}
