/**
 * Project Aura - Health Check Modal Component
 *
 * Comprehensive system health status display showing:
 * - Agent health and status
 * - API connectivity
 * - Database status (Neptune, OpenSearch)
 * - LLM service health (Bedrock)
 * - Infrastructure metrics
 *
 * Design System: Apple-inspired with clean data visualization,
 * semantic color coding, and smooth animations.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import {
  XMarkIcon,
  HeartIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ExclamationCircleIcon,
  ArrowPathIcon,
  CpuChipIcon,
  CircleStackIcon,
  ServerStackIcon,
  BoltIcon,
  CloudIcon,
  ClockIcon,
  SignalIcon,
} from '@heroicons/react/24/outline';

// Health status configurations
const HEALTH_STATUS = {
  healthy: {
    label: 'Healthy',
    icon: CheckCircleIcon,
    color: 'olive',
    bgClass: 'bg-olive-100 dark:bg-olive-900/30',
    textClass: 'text-olive-600 dark:text-olive-400',
    borderClass: 'border-olive-200 dark:border-olive-700',
  },
  degraded: {
    label: 'Degraded',
    icon: ExclamationTriangleIcon,
    color: 'warning',
    bgClass: 'bg-warning-100 dark:bg-warning-900/30',
    textClass: 'text-warning-600 dark:text-warning-400',
    borderClass: 'border-warning-200 dark:border-warning-700',
  },
  unhealthy: {
    label: 'Unhealthy',
    icon: ExclamationCircleIcon,
    color: 'critical',
    bgClass: 'bg-critical-100 dark:bg-critical-900/30',
    textClass: 'text-critical-600 dark:text-critical-400',
    borderClass: 'border-critical-200 dark:border-critical-700',
  },
  unknown: {
    label: 'Unknown',
    icon: ExclamationTriangleIcon,
    color: 'surface',
    bgClass: 'bg-surface-100 dark:bg-surface-700',
    textClass: 'text-surface-600 dark:text-surface-400',
    borderClass: 'border-surface-200 dark:border-surface-600',
  },
};

// Service category icons
const CATEGORY_ICONS = {
  agents: CpuChipIcon,
  databases: CircleStackIcon,
  api: ServerStackIcon,
  llm: CloudIcon,
  infrastructure: SignalIcon,
};

/**
 * Status Badge Component
 */
function StatusBadge({ status, size = 'md' }) {
  const config = HEALTH_STATUS[status] || HEALTH_STATUS.unknown;
  const Icon = config.icon;

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs gap-1',
    md: 'px-2.5 py-1 text-sm gap-1.5',
    lg: 'px-3 py-1.5 text-base gap-2',
  };

  const iconSizes = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
    lg: 'w-5 h-5',
  };

  return (
    <span
      className={`
        inline-flex items-center rounded-full font-medium
        ${config.bgClass} ${config.textClass} ${sizeClasses[size]}
      `}
    >
      <Icon className={iconSizes[size]} />
      {config.label}
    </span>
  );
}

/**
 * Progress Ring Component for metrics
 */
function _ProgressRing({ value, max = 100, size = 48, strokeWidth = 4, color = 'aura' }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const percentage = Math.min((value / max) * 100, 100);
  const offset = circumference - (percentage / 100) * circumference;

  const colorMap = {
    aura: '#3B82F6',
    olive: '#7C9A3E',
    warning: '#F59E0B',
    critical: '#DC2626',
  };

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="transform -rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          className="text-surface-200 dark:text-surface-700"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={colorMap[color] || colorMap.aura}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-500 ease-out"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-sm font-semibold text-surface-900 dark:text-surface-100">
          {Math.round(percentage)}%
        </span>
      </div>
    </div>
  );
}

/**
 * Service Health Card Component
 */
function ServiceHealthCard({ service }) {
  const statusConfig = HEALTH_STATUS[service.status] || HEALTH_STATUS.unknown;
  const StatusIcon = statusConfig.icon;

  return (
    <div
      className={`
        p-4 rounded-xl border transition-all duration-200 ease-[var(--ease-tahoe)]
        bg-white dark:bg-surface-800 backdrop-blur-xl
        ${statusConfig.borderClass}
        shadow-[var(--shadow-glass)] hover:shadow-[var(--shadow-glass-hover)]
      `}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={`p-1.5 rounded-lg ${statusConfig.bgClass}`}>
            <StatusIcon className={`w-4 h-4 ${statusConfig.textClass}`} />
          </div>
          <h4 className="font-medium text-surface-900 dark:text-surface-100">
            {service.name}
          </h4>
        </div>
        <StatusBadge status={service.status} size="sm" />
      </div>

      {service.metrics && (
        <div className="space-y-2">
          {service.metrics.map((metric, idx) => (
            <div key={idx} className="flex items-center justify-between text-sm">
              <span className="text-surface-600 dark:text-surface-400">{metric.label}</span>
              <span className="font-medium text-surface-900 dark:text-surface-100">
                {metric.value}
              </span>
            </div>
          ))}
        </div>
      )}

      {service.message && (
        <p className="mt-2 text-xs text-surface-500 dark:text-surface-400">
          {service.message}
        </p>
      )}
    </div>
  );
}

/**
 * Category Section Component
 */
function CategorySection({ title, icon: Icon, services, overallStatus }) {
  const _statusConfig = HEALTH_STATUS[overallStatus] || HEALTH_STATUS.unknown;

  return (
    <div className="mb-6 last:mb-0">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Icon className="w-5 h-5 text-surface-500 dark:text-surface-400" />
          <h3 className="font-semibold text-surface-900 dark:text-surface-100">{title}</h3>
        </div>
        <StatusBadge status={overallStatus} size="sm" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {services.map((service, idx) => (
          <ServiceHealthCard key={idx} service={service} />
        ))}
      </div>
    </div>
  );
}

/**
 * Overall Health Summary Component
 */
function HealthSummary({ healthData, loading }) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <ArrowPathIcon className="w-8 h-8 text-aura-500 animate-spin" />
        <span className="ml-3 text-surface-600 dark:text-surface-400">
          Checking system health...
        </span>
      </div>
    );
  }

  const overallStatus = healthData?.overallStatus || 'unknown';
  const statusConfig = HEALTH_STATUS[overallStatus];
  const StatusIcon = statusConfig.icon;

  return (
    <div className={`p-6 rounded-xl ${statusConfig.bgClass} backdrop-blur-sm border ${statusConfig.borderClass} mb-6 shadow-[var(--shadow-glass)]`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className={`p-3 rounded-xl bg-white/60 dark:bg-surface-800/60 backdrop-blur-sm`}>
            <StatusIcon className={`w-8 h-8 ${statusConfig.textClass}`} />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
              System Status: {statusConfig.label}
            </h3>
            <p className="text-sm text-surface-600 dark:text-surface-400 mt-0.5">
              {healthData?.summary || 'All systems operational'}
            </p>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="hidden md:flex items-center gap-6">
          <div className="text-center">
            <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">
              {healthData?.healthyServices || 0}
            </p>
            <p className="text-xs text-surface-500 dark:text-surface-400">Healthy</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-warning-600 dark:text-warning-400">
              {healthData?.degradedServices || 0}
            </p>
            <p className="text-xs text-surface-500 dark:text-surface-400">Degraded</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-critical-600 dark:text-critical-400">
              {healthData?.unhealthyServices || 0}
            </p>
            <p className="text-xs text-surface-500 dark:text-surface-400">Unhealthy</p>
          </div>
        </div>
      </div>

      {/* Last Updated */}
      <div className="flex items-center gap-2 mt-4 text-xs text-surface-500 dark:text-surface-400">
        <ClockIcon className="w-3.5 h-3.5" />
        Last updated: {healthData?.lastUpdated || 'Just now'}
      </div>
    </div>
  );
}

/**
 * Mock health data generator
 */
function generateMockHealthData() {
  return {
    overallStatus: 'healthy',
    summary: 'All 12 services are operating normally',
    healthyServices: 11,
    degradedServices: 1,
    unhealthyServices: 0,
    lastUpdated: new Date().toLocaleTimeString(),
    categories: {
      agents: {
        status: 'healthy',
        services: [
          {
            name: 'Orchestrator Agent',
            status: 'healthy',
            metrics: [
              { label: 'Active Tasks', value: '3' },
              { label: 'Success Rate', value: '99.2%' },
              { label: 'Avg Response', value: '245ms' },
            ],
          },
          {
            name: 'Coder Agent',
            status: 'healthy',
            metrics: [
              { label: 'Patches Generated', value: '12' },
              { label: 'In Progress', value: '2' },
              { label: 'Queue Depth', value: '5' },
            ],
          },
          {
            name: 'Reviewer Agent',
            status: 'healthy',
            metrics: [
              { label: 'Reviews Today', value: '28' },
              { label: 'Avg Duration', value: '4.2m' },
            ],
          },
          {
            name: 'Validator Agent',
            status: 'healthy',
            metrics: [
              { label: 'Tests Run', value: '156' },
              { label: 'Pass Rate', value: '98.7%' },
            ],
          },
        ],
      },
      databases: {
        status: 'healthy',
        services: [
          {
            name: 'Neptune (Graph DB)',
            status: 'healthy',
            metrics: [
              { label: 'Nodes', value: '12,847' },
              { label: 'Edges', value: '38,291' },
              { label: 'Avg Latency', value: '42ms' },
            ],
          },
          {
            name: 'OpenSearch (Vector)',
            status: 'healthy',
            metrics: [
              { label: 'Documents', value: '245,912' },
              { label: 'Index Size', value: '2.4 GB' },
              { label: 'Query Latency', value: '18ms' },
            ],
          },
          {
            name: 'DynamoDB',
            status: 'healthy',
            metrics: [
              { label: 'Tables', value: '8' },
              { label: 'Read Capacity', value: '85%' },
              { label: 'Write Capacity', value: '23%' },
            ],
          },
        ],
      },
      api: {
        status: 'degraded',
        services: [
          {
            name: 'API Gateway',
            status: 'healthy',
            metrics: [
              { label: 'Requests/min', value: '1,234' },
              { label: 'Error Rate', value: '0.02%' },
              { label: 'P95 Latency', value: '127ms' },
            ],
          },
          {
            name: 'Context Retrieval Service',
            status: 'degraded',
            metrics: [
              { label: 'Cache Hit Rate', value: '72%' },
              { label: 'Avg Response', value: '345ms' },
            ],
            message: 'Elevated latency detected. Auto-scaling in progress.',
          },
        ],
      },
      llm: {
        status: 'healthy',
        services: [
          {
            name: 'AWS Bedrock',
            status: 'healthy',
            metrics: [
              { label: 'Model', value: 'Claude 3.5 Sonnet' },
              { label: 'Tokens Today', value: '2.4M' },
              { label: 'Avg Latency', value: '1.2s' },
            ],
          },
          {
            name: 'Embedding Service',
            status: 'healthy',
            metrics: [
              { label: 'Model', value: 'Titan Embed v2' },
              { label: 'Embeddings/hr', value: '12,456' },
            ],
          },
        ],
      },
      infrastructure: {
        status: 'healthy',
        services: [
          {
            name: 'EKS Cluster',
            status: 'healthy',
            metrics: [
              { label: 'Nodes', value: '6' },
              { label: 'CPU Usage', value: '45%' },
              { label: 'Memory', value: '62%' },
            ],
          },
          {
            name: 'Sandbox Network',
            status: 'healthy',
            metrics: [
              { label: 'Active Sandboxes', value: '3' },
              { label: 'Available', value: '7' },
            ],
          },
        ],
      },
    },
  };
}

/**
 * Main Health Check Modal Component
 */
export default function HealthCheckModal({ isOpen, onClose }) {
  const [healthData, setHealthData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const modalRef = useRef(null);
  const refreshIntervalRef = useRef(null);

  // Fetch health data
  const fetchHealthData = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    try {
      // In production, this would call the health API
      // const data = await getSystemHealth();
      await new Promise((resolve) => setTimeout(resolve, 800));
      setHealthData(generateMockHealthData());
    } catch (err) {
      console.error('Failed to fetch health data:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  // Initial load and auto-refresh
  useEffect(() => {
    if (isOpen) {
      fetchHealthData();

      // Set up auto-refresh
      if (autoRefresh) {
        refreshIntervalRef.current = setInterval(() => {
          fetchHealthData(true);
        }, 30000); // Refresh every 30 seconds
      }
    }

    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
  }, [isOpen, autoRefresh, fetchHealthData]);

  // Handle escape key
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    document.body.style.overflow = 'hidden';

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="health-modal-title"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-md transition-opacity duration-200"
        onClick={onClose}
      />

      {/* Modal */}
      <div
        ref={modalRef}
        className="relative bg-white/95 dark:bg-surface-800/95 backdrop-blur-xl backdrop-saturate-150 rounded-2xl shadow-[var(--shadow-glass-hover)] max-w-4xl w-full max-h-[90vh] overflow-hidden animate-in fade-in zoom-in-95 duration-[var(--duration-overlay)] ease-[var(--ease-tahoe)]"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-surface-100/50 dark:border-surface-700/30">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-olive-100 dark:bg-olive-900/30">
                <HeartIcon className="w-5 h-5 text-olive-600 dark:text-olive-400" />
              </div>
              <div>
                <h2
                  id="health-modal-title"
                  className="text-lg font-semibold text-surface-900 dark:text-surface-100"
                >
                  System Health Check
                </h2>
                <p className="text-sm text-surface-500 dark:text-surface-400">
                  Real-time status of all Aura services
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* Auto-refresh toggle */}
              <label className="flex items-center gap-2 text-sm text-surface-600 dark:text-surface-400 cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                  className="w-4 h-4 rounded border-surface-300 dark:border-surface-600 text-aura-600 focus:ring-aura-500"
                />
                Auto-refresh
              </label>

              {/* Manual refresh button */}
              <button
                onClick={() => fetchHealthData(true)}
                disabled={refreshing}
                className="p-2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-200 hover:bg-surface-50 dark:hover:bg-surface-700 rounded-xl transition-all duration-200 ease-[var(--ease-tahoe)] disabled:opacity-50"
                aria-label="Refresh health data"
              >
                <ArrowPathIcon className={`w-5 h-5 ${refreshing ? 'animate-spin' : ''}`} />
              </button>

              {/* Close button */}
              <button
                onClick={onClose}
                className="p-2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-200 hover:bg-surface-50 dark:hover:bg-surface-700 rounded-xl transition-all duration-200 ease-[var(--ease-tahoe)]"
                aria-label="Close modal"
              >
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-140px)]">
          {/* Overall Health Summary */}
          <HealthSummary healthData={healthData} loading={loading} />

          {/* Service Categories */}
          {!loading && healthData?.categories && (
            <>
              <CategorySection
                title="Agents"
                icon={CATEGORY_ICONS.agents}
                services={healthData.categories.agents.services}
                overallStatus={healthData.categories.agents.status}
              />
              <CategorySection
                title="Databases"
                icon={CATEGORY_ICONS.databases}
                services={healthData.categories.databases.services}
                overallStatus={healthData.categories.databases.status}
              />
              <CategorySection
                title="API Services"
                icon={CATEGORY_ICONS.api}
                services={healthData.categories.api.services}
                overallStatus={healthData.categories.api.status}
              />
              <CategorySection
                title="LLM Services"
                icon={CATEGORY_ICONS.llm}
                services={healthData.categories.llm.services}
                overallStatus={healthData.categories.llm.status}
              />
              <CategorySection
                title="Infrastructure"
                icon={CATEGORY_ICONS.infrastructure}
                services={healthData.categories.infrastructure.services}
                overallStatus={healthData.categories.infrastructure.status}
              />
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-surface-100/50 dark:border-surface-700/30 bg-white/60 dark:bg-surface-800/50 backdrop-blur-sm flex items-center justify-between">
          <p className="text-xs text-surface-500 dark:text-surface-400 flex items-center gap-1">
            <BoltIcon className="w-3.5 h-3.5" />
            Health checks run every 30 seconds when auto-refresh is enabled
          </p>
          <button
            onClick={onClose}
            className="px-4 py-2.5 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-surface-50 dark:hover:bg-surface-700 rounded-xl transition-all duration-200 ease-[var(--ease-tahoe)]"
          >
            Close
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
