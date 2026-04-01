/**
 * Performance Bar Component
 *
 * GitLab-inspired performance metrics overlay that displays
 * real-time API timing, database queries, cache stats, and memory usage.
 */

import { useState, useEffect } from 'react';
import {
  XMarkIcon,
  ChevronUpIcon,
  ChevronDownIcon,
  CircleStackIcon,
  ServerStackIcon,
  CpuChipIcon,
} from '@heroicons/react/24/outline';
import { useDeveloperMode } from '../../context/DeveloperModeContext';
import { formatBytes } from '../../services/developerApi';

export default function PerformanceBar() {
  const {
    enabled,
    performanceBar,
    performanceMetrics,
    togglePerformanceBar,
    updatePerformanceMetrics,
  } = useDeveloperMode();

  const [expanded, setExpanded] = useState(false);
  const [selectedMetric, setSelectedMetric] = useState(null);

  // Keyboard shortcut handler
  useEffect(() => {
    const handleKeyDown = (e) => {
      // ⌘+Shift+P or Ctrl+Shift+P
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === 'p') {
        e.preventDefault();
        togglePerformanceBar();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [togglePerformanceBar]);

  // Simulate performance metrics updates (in real app, this would come from actual monitoring)
  useEffect(() => {
    if (!enabled || !performanceBar.enabled) return;

    const interval = setInterval(() => {
      updatePerformanceMetrics({
        apiCalls: performanceMetrics.apiCalls + Math.floor(Math.random() * 3),
        apiTime: 80 + Math.floor(Math.random() * 60),
        dbQueries: performanceMetrics.dbQueries + Math.floor(Math.random() * 2),
        dbTime: 15 + Math.floor(Math.random() * 25),
        cacheHits: performanceMetrics.cacheHits + Math.floor(Math.random() * 5),
        cacheMisses: performanceMetrics.cacheMisses + Math.floor(Math.random() * 1),
        memoryUsage: 100 + Math.floor(Math.random() * 50) * 1024 * 1024,
      });
    }, 2000);

    return () => clearInterval(interval);
  }, [enabled, performanceBar.enabled, performanceMetrics, updatePerformanceMetrics]);

  if (!enabled || !performanceBar.enabled) {
    return null;
  }

  const cacheHitRate = performanceMetrics.cacheHits + performanceMetrics.cacheMisses > 0
    ? ((performanceMetrics.cacheHits / (performanceMetrics.cacheHits + performanceMetrics.cacheMisses)) * 100).toFixed(1)
    : 0;

  const metrics = [
    {
      id: 'api',
      icon: ServerStackIcon,
      label: 'API',
      value: `${performanceMetrics.apiTime}ms`,
      detail: `${performanceMetrics.apiCalls} calls`,
      color: performanceMetrics.apiTime > 200 ? 'text-warning-500' : 'text-olive-500',
    },
    {
      id: 'db',
      icon: CircleStackIcon,
      label: 'DB',
      value: `${performanceMetrics.dbTime}ms`,
      detail: `${performanceMetrics.dbQueries} queries`,
      color: performanceMetrics.dbTime > 50 ? 'text-warning-500' : 'text-olive-500',
    },
    {
      id: 'cache',
      icon: CpuChipIcon,
      label: 'Cache',
      value: `${cacheHitRate}%`,
      detail: `${performanceMetrics.cacheHits}/${performanceMetrics.cacheHits + performanceMetrics.cacheMisses}`,
      color: parseFloat(cacheHitRate) < 80 ? 'text-warning-500' : 'text-olive-500',
    },
    {
      id: 'memory',
      icon: CpuChipIcon,
      label: 'Memory',
      value: formatBytes(performanceMetrics.memoryUsage),
      detail: 'heap',
      color: performanceMetrics.memoryUsage > 200 * 1024 * 1024 ? 'text-warning-500' : 'text-olive-500',
    },
  ];

  return (
    <div
      className={`
        fixed bottom-0 left-0 right-0 z-50
        bg-surface-900/95 dark:bg-surface-950/95 backdrop-blur-xl
        border-t border-surface-700/50
        transition-all duration-300 ease-[var(--ease-tahoe)]
        ${expanded ? 'h-64' : 'h-10'}
      `}
    >
      {/* Collapsed Bar */}
      <div className="h-10 px-4 flex items-center justify-between">
        <div className="flex items-center gap-1">
          {/* Expand/Collapse Button */}
          <button
            onClick={() => setExpanded(!expanded)}
            className="p-1 hover:bg-white/10 rounded transition-colors mr-2"
          >
            {expanded ? (
              <ChevronDownIcon className="h-4 w-4 text-surface-400" />
            ) : (
              <ChevronUpIcon className="h-4 w-4 text-surface-400" />
            )}
          </button>

          {/* Performance Metrics */}
          {metrics.map((metric, index) => (
            <button
              key={metric.id}
              onClick={() => {
                setSelectedMetric(metric.id);
                setExpanded(true);
              }}
              className={`
                flex items-center gap-2 px-3 py-1 rounded-lg text-sm
                hover:bg-white/10 transition-colors
                ${selectedMetric === metric.id ? 'bg-white/10' : ''}
              `}
            >
              <metric.icon className={`h-4 w-4 ${metric.color}`} />
              <span className="text-surface-300 font-medium">{metric.label}</span>
              <span className={`font-mono ${metric.color}`}>{metric.value}</span>
              <span className="text-surface-500 text-xs">{metric.detail}</span>
              {index < metrics.length - 1 && (
                <span className="text-surface-600 ml-2">|</span>
              )}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          {/* Timestamp */}
          <span className="text-xs text-surface-500 font-mono">
            {new Date().toLocaleTimeString()}
          </span>

          {/* Close Button */}
          <button
            onClick={togglePerformanceBar}
            className="p-1 hover:bg-white/10 rounded transition-colors"
            title="Close Performance Bar (⌘+Shift+P)"
          >
            <XMarkIcon className="h-4 w-4 text-surface-400" />
          </button>
        </div>
      </div>

      {/* Expanded Detail View */}
      {expanded && (
        <div className="h-[calc(100%-2.5rem)] p-4 overflow-auto">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 h-full">
            {metrics.map((metric) => (
              <MetricDetailCard
                key={metric.id}
                metric={metric}
                isSelected={selectedMetric === metric.id}
                onSelect={() => setSelectedMetric(metric.id)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function MetricDetailCard({ metric, isSelected, onSelect }) {
  // Generate sample historical data
  const [history] = useState(() =>
    Array.from({ length: 20 }, (_, i) => ({
      time: Date.now() - (20 - i) * 1000,
      value: parseFloat(metric.value) * (0.8 + Math.random() * 0.4),
    }))
  );

  const maxValue = Math.max(...history.map((h) => h.value));

  return (
    <div
      onClick={onSelect}
      className={`
        bg-surface-800/50 rounded-xl p-4 cursor-pointer
        border transition-all duration-200
        ${isSelected
          ? 'border-aura-500 ring-1 ring-aura-500/50'
          : 'border-surface-700/50 hover:border-surface-600'
        }
      `}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <metric.icon className={`h-5 w-5 ${metric.color}`} />
          <span className="font-medium text-surface-200">{metric.label}</span>
        </div>
        <span className={`text-xl font-bold font-mono ${metric.color}`}>
          {metric.value}
        </span>
      </div>

      {/* Mini Chart */}
      <div className="h-16 flex items-end gap-0.5">
        {history.map((point, i) => (
          <div
            key={i}
            className="flex-1 bg-aura-500/60 rounded-t"
            style={{
              height: `${(point.value / maxValue) * 100}%`,
              opacity: 0.3 + (i / history.length) * 0.7,
            }}
          />
        ))}
      </div>

      <div className="mt-3 text-xs text-surface-500">
        {metric.detail}
      </div>
    </div>
  );
}
