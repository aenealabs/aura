import { useState, useEffect, useCallback } from 'react';
import {
  CpuChipIcon,
  GlobeAltIcon,
  PlusIcon,
  MagnifyingGlassIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  ShieldCheckIcon,
  ArrowPathIcon,
  PlayIcon,
  PauseIcon,
  StopIcon,
  Cog6ToothIcon,
  CommandLineIcon,
  EyeIcon,
  TrashIcon,
  ArrowTrendingUpIcon,
} from '@heroicons/react/24/outline';
import { PageSkeleton } from './ui/LoadingSkeleton';
import { useToast } from './ui/Toast';
import MetricCard from './ui/MetricCard';
import { useConfirm } from './ui/ConfirmDialog';
import AgentConfigModal from './settings/AgentConfigModal';
import AgentDeployModal from './settings/AgentDeployModal';
import {
  startAgent,
  stopAgent,
  pauseAgent,
  resumeAgent,
  restartAgent,
  deleteAgent,
  updateAgentConfig,
  validateConfigLocally,
} from '../services/agentControlApi';

// =============================================================================
// Design System Styles - Aligned with Project Aura
// =============================================================================

const AGENT_TYPE_CONFIG = {
  orchestrator: {
    label: 'Orchestrator',
    icon: CpuChipIcon,
    color: 'olive',
    description: 'Coordinates multi-agent workflows',
  },
  coder: {
    label: 'Coder',
    icon: CommandLineIcon,
    color: 'aura',
    description: 'Generates and modifies code',
  },
  reviewer: {
    label: 'Reviewer',
    icon: EyeIcon,
    color: 'warning',
    description: 'Reviews code for quality and security',
  },
  validator: {
    label: 'Validator',
    icon: ShieldCheckIcon,
    color: 'olive',
    description: 'Validates patches in sandbox',
  },
  scanner: {
    label: 'Scanner',
    icon: MagnifyingGlassIcon,
    color: 'aura',
    description: 'Scans for vulnerabilities',
  },
  external: {
    label: 'External',
    icon: GlobeAltIcon,
    color: 'warning',
    description: 'External A2A agent',
  },
};

const STATUS_CONFIG = {
  active: {
    label: 'Active',
    badge: 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400',
    dot: 'bg-olive-500',
  },
  idle: {
    label: 'Idle',
    badge: 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-400',
    dot: 'bg-surface-400',
  },
  busy: {
    label: 'Busy',
    badge: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
    dot: 'bg-aura-500',
  },
  paused: {
    label: 'Paused',
    badge: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    dot: 'bg-warning-500',
  },
  stopped: {
    label: 'Stopped',
    badge: 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-400',
    dot: 'bg-surface-500',
  },
  starting: {
    label: 'Starting',
    badge: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
    dot: 'bg-aura-500 animate-pulse',
  },
  stopping: {
    label: 'Stopping',
    badge: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    dot: 'bg-warning-500 animate-pulse',
  },
  degraded: {
    label: 'Degraded',
    badge: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    dot: 'bg-warning-500',
  },
  error: {
    label: 'Error',
    badge: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
    dot: 'bg-critical-500',
  },
  pending: {
    label: 'Pending',
    badge: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    dot: 'bg-warning-500',
  },
};

// =============================================================================
// Mock Data
// =============================================================================

const MOCK_AGENTS = [
  {
    id: 'agent-001',
    name: 'Orchestrator Prime',
    type: 'orchestrator',
    status: 'active',
    currentTask: 'Coordinating patch workflow for CVE-2024-1234',
    health: { cpu: 45, memory: 62, tokens: 8500 },
    metrics: {
      tasksCompleted: 1247,
      successRate: 98.5,
      avgExecutionTime: 12.4,
      lastActive: '2024-12-08T10:30:00Z',
    },
    version: 'v2.3.1',
    capabilities: ['workflow_orchestration', 'agent_coordination', 'priority_management'],
  },
  {
    id: 'agent-002',
    name: 'Coder Agent Alpha',
    type: 'coder',
    status: 'busy',
    currentTask: 'Generating SQL injection fix for UserController',
    health: { cpu: 78, memory: 85, tokens: 12400 },
    metrics: {
      tasksCompleted: 892,
      successRate: 94.2,
      avgExecutionTime: 28.7,
      lastActive: '2024-12-08T10:32:00Z',
    },
    version: 'v2.1.0',
    capabilities: ['code_generation', 'patch_creation', 'refactoring'],
  },
  {
    id: 'agent-003',
    name: 'Security Reviewer',
    type: 'reviewer',
    status: 'active',
    currentTask: 'Analyzing patch quality for XSS mitigation',
    health: { cpu: 32, memory: 45, tokens: 6200 },
    metrics: {
      tasksCompleted: 2156,
      successRate: 99.1,
      avgExecutionTime: 8.2,
      lastActive: '2024-12-08T10:31:00Z',
    },
    version: 'v1.8.3',
    capabilities: ['security_review', 'owasp_analysis', 'compliance_check'],
  },
  {
    id: 'agent-004',
    name: 'Sandbox Validator',
    type: 'validator',
    status: 'idle',
    currentTask: 'Waiting for patches to validate',
    health: { cpu: 12, memory: 28, tokens: 0 },
    metrics: {
      tasksCompleted: 567,
      successRate: 97.8,
      avgExecutionTime: 45.3,
      lastActive: '2024-12-08T09:45:00Z',
    },
    version: 'v1.5.2',
    capabilities: ['sandbox_testing', 'integration_testing', 'regression_testing'],
  },
  {
    id: 'agent-005',
    name: 'Vulnerability Scanner',
    type: 'scanner',
    status: 'active',
    currentTask: 'Scanning repository: core-api',
    health: { cpu: 56, memory: 68, tokens: 4800 },
    metrics: {
      tasksCompleted: 3421,
      successRate: 99.7,
      avgExecutionTime: 15.8,
      lastActive: '2024-12-08T10:28:00Z',
    },
    version: 'v2.0.0',
    capabilities: ['vulnerability_detection', 'cve_matching', 'threat_assessment'],
  },
  {
    id: 'agent-006',
    name: 'External Code Analyzer',
    type: 'external',
    status: 'degraded',
    currentTask: 'Connection latency issues',
    health: { cpu: 0, memory: 0, tokens: 0 },
    metrics: {
      tasksCompleted: 234,
      successRate: 89.5,
      avgExecutionTime: 120.5,
      lastActive: '2024-12-08T08:15:00Z',
    },
    version: 'A2A v1.0',
    provider: 'acme-security',
    capabilities: ['static_analysis', 'dependency_check'],
  },
];

const MOCK_TASK_HISTORY = [
  {
    id: 'task-001',
    agentId: 'agent-002',
    agentName: 'Coder Agent Alpha',
    task: 'Generate patch for SQL injection vulnerability',
    status: 'completed',
    duration: 32.5,
    timestamp: '2024-12-08T10:15:00Z',
    result: 'success',
  },
  {
    id: 'task-002',
    agentId: 'agent-003',
    agentName: 'Security Reviewer',
    task: 'Review patch quality for PR-892',
    status: 'completed',
    duration: 8.2,
    timestamp: '2024-12-08T10:20:00Z',
    result: 'success',
  },
  {
    id: 'task-003',
    agentId: 'agent-001',
    agentName: 'Orchestrator Prime',
    task: 'Coordinate multi-agent workflow',
    status: 'completed',
    duration: 2.1,
    timestamp: '2024-12-08T10:22:00Z',
    result: 'success',
  },
  {
    id: 'task-004',
    agentId: 'agent-004',
    agentName: 'Sandbox Validator',
    task: 'Run integration tests in sandbox',
    status: 'completed',
    duration: 48.7,
    timestamp: '2024-12-08T09:45:00Z',
    result: 'success',
  },
  {
    id: 'task-005',
    agentId: 'agent-006',
    agentName: 'External Code Analyzer',
    task: 'Static analysis of auth module',
    status: 'failed',
    duration: 120.5,
    timestamp: '2024-12-08T08:15:00Z',
    result: 'timeout',
    error: 'Connection timeout after 120s',
  },
];

// =============================================================================
// Helper Functions
// =============================================================================

function formatRelativeTime(date) {
  if (!date) return '';
  const now = new Date();
  const then = new Date(date);
  const seconds = Math.floor((now - then) / 1000);

  if (seconds < 60) return 'Just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return then.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function getColorClasses(color) {
  const colorMap = {
    olive: {
      bg: 'bg-olive-100 dark:bg-olive-900/30',
      text: 'text-olive-600 dark:text-olive-400',
      icon: 'text-olive-500',
      selectedBorder: 'border-olive-500 dark:border-olive-400',
      selectedBg: 'bg-olive-50 dark:bg-olive-900/20',
    },
    aura: {
      bg: 'bg-aura-100 dark:bg-aura-900/30',
      text: 'text-aura-600 dark:text-aura-400',
      icon: 'text-aura-500',
      selectedBorder: 'border-aura-500 dark:border-aura-400',
      selectedBg: 'bg-aura-50 dark:bg-aura-900/20',
    },
    warning: {
      bg: 'bg-warning-100 dark:bg-warning-900/30',
      text: 'text-warning-600 dark:text-warning-400',
      icon: 'text-warning-500',
      selectedBorder: 'border-warning-500 dark:border-warning-400',
      selectedBg: 'bg-warning-50 dark:bg-warning-900/20',
    },
    critical: {
      bg: 'bg-critical-100 dark:bg-critical-900/30',
      text: 'text-critical-600 dark:text-critical-400',
      icon: 'text-critical-500',
      selectedBorder: 'border-critical-500 dark:border-critical-400',
      selectedBg: 'bg-critical-50 dark:bg-critical-900/20',
    },
  };
  return colorMap[color] || colorMap.olive;
}

// =============================================================================
// Components
// =============================================================================

// Health Bar Component
function HealthBar({ label, value, _color = 'aura' }) {
  const colorClasses = {
    aura: 'bg-aura-500',
    olive: 'bg-olive-500',
    warning: 'bg-warning-500',
    critical: 'bg-critical-500',
  };

  const getBarColor = (val) => {
    if (val >= 80) return colorClasses.critical;
    if (val >= 60) return colorClasses.warning;
    return colorClasses.olive;
  };

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-surface-500 dark:text-surface-400">{label}</span>
        <span className="text-surface-700 dark:text-surface-300 font-medium">{value}%</span>
      </div>
      <div className="h-1.5 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${getBarColor(value)}`}
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  );
}

// Agent Card Component
function AgentCard({ agent, onClick, isSelected }) {
  const typeConfig = AGENT_TYPE_CONFIG[agent.type] || AGENT_TYPE_CONFIG.orchestrator;
  const statusConfig = STATUS_CONFIG[agent.status] || STATUS_CONFIG.idle;
  const colorClasses = getColorClasses(typeConfig.color);
  const TypeIcon = typeConfig.icon;

  return (
    <button
      onClick={onClick}
      className={`
        w-full text-left p-4 rounded-xl border-2 transition-all duration-200
        ${isSelected
          ? `${colorClasses.selectedBorder} bg-white dark:bg-surface-800 shadow-lg`
          : 'border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 hover:border-surface-300 dark:hover:border-surface-600 hover:shadow-md'
        }
      `}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <div className={`p-1.5 rounded-lg ${colorClasses.bg}`}>
            <TypeIcon className={`w-4 h-4 ${colorClasses.icon}`} />
          </div>
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusConfig.badge}`}>
            <span className={`inline-block w-1.5 h-1.5 rounded-full mr-1.5 ${statusConfig.dot}`} />
            {statusConfig.label}
          </span>
        </div>
        <span className="text-xs text-surface-400 dark:text-surface-500">{agent.version}</span>
      </div>

      {/* Name and Type */}
      <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-1">
        {agent.name}
      </h3>
      <p className="text-xs text-surface-500 dark:text-surface-400 mb-3">
        {typeConfig.description}
      </p>

      {/* Current Task */}
      <div className="bg-surface-50 dark:bg-surface-700/50 rounded-lg p-2 mb-3">
        <p className="text-xs text-surface-600 dark:text-surface-400 line-clamp-1">
          {agent.currentTask}
        </p>
      </div>

      {/* Health Metrics */}
      <div className="space-y-2 mb-3">
        <HealthBar label="CPU" value={agent.health.cpu} />
        <HealthBar label="Memory" value={agent.health.memory} />
      </div>

      {/* Bottom Metrics */}
      <div className="flex items-center justify-between text-xs text-surface-500 dark:text-surface-400">
        <span className="flex items-center gap-1">
          <CheckCircleIcon className="w-3.5 h-3.5" />
          {agent.metrics.successRate}% success
        </span>
        <span className="flex items-center gap-1">
          <ClockIcon className="w-3.5 h-3.5" />
          {agent.metrics.avgExecutionTime}s avg
        </span>
      </div>
    </button>
  );
}

// Agent Detail Panel
function AgentDetailPanel({ agent, _onClose, onAction, actionLoading }) {
  const [activeTab, setActiveTab] = useState('overview');

  if (!agent) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-surface-400 dark:text-surface-500 p-8">
        <CpuChipIcon className="w-16 h-16 mb-4" />
        <h3 className="text-lg font-medium mb-2">Select an Agent</h3>
        <p className="text-sm text-center">Choose an agent to view details and manage configuration</p>
      </div>
    );
  }

  const typeConfig = AGENT_TYPE_CONFIG[agent.type] || AGENT_TYPE_CONFIG.orchestrator;
  const statusConfig = STATUS_CONFIG[agent.status] || STATUS_CONFIG.idle;
  const colorClasses = getColorClasses(typeConfig.color);
  const TypeIcon = typeConfig.icon;

  return (
    <div className="flex-1 flex flex-col bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] overflow-hidden mb-16">
      {/* Header */}
      <div className="p-6 border-b border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className={`p-3 rounded-xl ${colorClasses.bg}`}>
              <TypeIcon className={`w-6 h-6 ${colorClasses.icon}`} />
            </div>
            <div>
              <h2 className="text-xl font-bold text-surface-900 dark:text-surface-100">
                {agent.name}
              </h2>
              <p className="text-sm text-surface-500 dark:text-surface-400">
                {typeConfig.label} Agent
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className={`px-3 py-1 rounded-full text-xs font-medium ${statusConfig.badge}`}>
              <span className={`inline-block w-2 h-2 rounded-full mr-2 ${statusConfig.dot} ${agent.status === 'active' ? 'animate-pulse' : ''}`} />
              {statusConfig.label}
            </span>
            <span className="px-2 py-1 rounded bg-surface-100 dark:bg-surface-700 text-xs font-mono text-surface-600 dark:text-surface-400">
              {agent.version}
            </span>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="text-center p-3 bg-olive-100 dark:bg-olive-900/30 rounded-lg">
            <p className="text-xl font-bold text-olive-700 dark:text-olive-400">
              {agent.metrics.tasksCompleted.toLocaleString()}
            </p>
            <p className="text-xs text-olive-600 dark:text-olive-500">Tasks Done</p>
          </div>
          <div className="text-center p-3 bg-aura-100 dark:bg-aura-900/30 rounded-lg">
            <p className="text-xl font-bold text-aura-700 dark:text-aura-400">
              {agent.metrics.successRate}%
            </p>
            <p className="text-xs text-aura-600 dark:text-aura-500">Success Rate</p>
          </div>
          <div className="text-center p-3 bg-warning-100 dark:bg-warning-900/30 rounded-lg">
            <p className="text-xl font-bold text-warning-700 dark:text-warning-400">
              {agent.metrics.avgExecutionTime}s
            </p>
            <p className="text-xs text-warning-600 dark:text-warning-500">Avg Time</p>
          </div>
          <div className="text-center p-3 bg-surface-100 dark:bg-surface-700 rounded-lg">
            <p className="text-xl font-bold text-surface-700 dark:text-surface-300">
              {agent.health.tokens > 0 ? `${(agent.health.tokens / 1000).toFixed(1)}k` : '0'}
            </p>
            <p className="text-xs text-surface-500 dark:text-surface-400">Tokens</p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-surface-200 dark:border-surface-700">
        <nav className="flex gap-1 px-4">
          {[
            { id: 'overview', label: 'Overview' },
            { id: 'health', label: 'Health' },
            { id: 'capabilities', label: 'Capabilities' },
            { id: 'history', label: 'History' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`
                px-4 py-3 text-sm font-medium border-b-2 transition-colors
                ${activeTab === tab.id
                  ? 'border-olive-500 text-olive-600 dark:text-olive-400'
                  : 'border-transparent text-surface-500 hover:text-surface-700 dark:hover:text-surface-300'
                }
              `}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Current Task */}
            <div>
              <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-3">Current Task</h3>
              <div className="bg-surface-50 dark:bg-surface-700/50 rounded-lg p-4">
                <p className="text-surface-700 dark:text-surface-300">{agent.currentTask}</p>
                <p className="text-xs text-surface-500 mt-2">
                  Last active: {formatRelativeTime(agent.metrics.lastActive)}
                </p>
              </div>
            </div>

            {/* Agent Info */}
            <div>
              <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-3">Agent Information</h3>
              <div className="bg-surface-50 dark:bg-surface-700/50 rounded-lg p-4 space-y-3">
                <div className="flex justify-between">
                  <span className="text-surface-600 dark:text-surface-400">Agent ID</span>
                  <span className="font-mono text-sm text-surface-900 dark:text-surface-100">{agent.id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-surface-600 dark:text-surface-400">Type</span>
                  <span className="text-surface-900 dark:text-surface-100">{typeConfig.label}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-surface-600 dark:text-surface-400">Version</span>
                  <span className="text-surface-900 dark:text-surface-100">{agent.version}</span>
                </div>
                {agent.provider && (
                  <div className="flex justify-between">
                    <span className="text-surface-600 dark:text-surface-400">Provider</span>
                    <span className="text-surface-900 dark:text-surface-100">{agent.provider}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'health' && (
          <div className="space-y-6">
            {/* Real-time Health */}
            <div>
              <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-3">Resource Usage</h3>
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between mb-2">
                    <span className="text-sm text-surface-600 dark:text-surface-400">CPU Usage</span>
                    <span className="text-sm font-medium text-surface-900 dark:text-surface-100">{agent.health.cpu}%</span>
                  </div>
                  <div className="h-3 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        agent.health.cpu >= 80 ? 'bg-critical-500' :
                        agent.health.cpu >= 60 ? 'bg-warning-500' : 'bg-olive-500'
                      }`}
                      style={{ width: `${agent.health.cpu}%` }}
                    />
                  </div>
                </div>

                <div>
                  <div className="flex justify-between mb-2">
                    <span className="text-sm text-surface-600 dark:text-surface-400">Memory Usage</span>
                    <span className="text-sm font-medium text-surface-900 dark:text-surface-100">{agent.health.memory}%</span>
                  </div>
                  <div className="h-3 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        agent.health.memory >= 80 ? 'bg-critical-500' :
                        agent.health.memory >= 60 ? 'bg-warning-500' : 'bg-olive-500'
                      }`}
                      style={{ width: `${agent.health.memory}%` }}
                    />
                  </div>
                </div>

                <div>
                  <div className="flex justify-between mb-2">
                    <span className="text-sm text-surface-600 dark:text-surface-400">Token Usage (Session)</span>
                    <span className="text-sm font-medium text-surface-900 dark:text-surface-100">
                      {agent.health.tokens.toLocaleString()} tokens
                    </span>
                  </div>
                  <div className="h-3 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-aura-500 rounded-full transition-all duration-500"
                      style={{ width: `${Math.min((agent.health.tokens / 20000) * 100, 100)}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Health Status */}
            <div>
              <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-3">System Health</h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-olive-50 dark:bg-olive-900/20 border border-olive-200 dark:border-olive-800 rounded-lg p-4">
                  <CheckCircleIcon className="w-6 h-6 text-olive-500 mb-2" />
                  <p className="text-sm font-medium text-olive-700 dark:text-olive-400">LLM Connection</p>
                  <p className="text-xs text-olive-600 dark:text-olive-500">Healthy</p>
                </div>
                <div className="bg-olive-50 dark:bg-olive-900/20 border border-olive-200 dark:border-olive-800 rounded-lg p-4">
                  <CheckCircleIcon className="w-6 h-6 text-olive-500 mb-2" />
                  <p className="text-sm font-medium text-olive-700 dark:text-olive-400">GraphRAG</p>
                  <p className="text-xs text-olive-600 dark:text-olive-500">Connected</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'capabilities' && (
          <div className="space-y-6">
            <div>
              <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-3">Agent Capabilities</h3>
              <div className="flex flex-wrap gap-2">
                {agent.capabilities.map((cap) => (
                  <span
                    key={cap}
                    className="px-3 py-1.5 bg-surface-100 dark:bg-surface-700 rounded-lg text-sm text-surface-700 dark:text-surface-300 border border-surface-200 dark:border-surface-600"
                  >
                    {cap.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            </div>

            <div>
              <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-3">Permissions</h3>
              <div className="bg-surface-50 dark:bg-surface-700/50 rounded-lg p-4 space-y-3">
                <div className="flex items-center gap-3">
                  <CheckCircleIcon className="w-5 h-5 text-olive-500" />
                  <span className="text-surface-700 dark:text-surface-300">Execute code in sandbox</span>
                </div>
                <div className="flex items-center gap-3">
                  <CheckCircleIcon className="w-5 h-5 text-olive-500" />
                  <span className="text-surface-700 dark:text-surface-300">Access GraphRAG context</span>
                </div>
                <div className="flex items-center gap-3">
                  <CheckCircleIcon className="w-5 h-5 text-olive-500" />
                  <span className="text-surface-700 dark:text-surface-300">Generate patches</span>
                </div>
                <div className="flex items-center gap-3">
                  <XCircleIcon className="w-5 h-5 text-surface-400" />
                  <span className="text-surface-500 dark:text-surface-400">Deploy to production (requires HITL)</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'history' && (
          <div className="space-y-4">
            <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-3">Recent Tasks</h3>
            {MOCK_TASK_HISTORY
              .filter(t => t.agentId === agent.id)
              .slice(0, 10)
              .map((task) => (
                <div
                  key={task.id}
                  className="flex items-center gap-4 p-3 bg-surface-50 dark:bg-surface-700/50 rounded-lg"
                >
                  {task.result === 'success' ? (
                    <CheckCircleIcon className="w-5 h-5 text-olive-500 flex-shrink-0" />
                  ) : (
                    <XCircleIcon className="w-5 h-5 text-critical-500 flex-shrink-0" />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-surface-900 dark:text-surface-100 truncate">
                      {task.task}
                    </p>
                    <p className="text-xs text-surface-500 dark:text-surface-400">
                      {task.duration}s - {formatRelativeTime(task.timestamp)}
                    </p>
                  </div>
                </div>
              ))}
            {MOCK_TASK_HISTORY.filter(t => t.agentId === agent.id).length === 0 && (
              <div className="text-center py-8 text-surface-400">
                <ClockIcon className="w-12 h-12 mx-auto mb-3" />
                <p>No task history available</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Action Footer */}
      <div className="p-4 border-t border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50">
        {/* Primary Actions Row */}
        <div className="flex gap-3 mb-3">
          {agent.status === 'active' || agent.status === 'busy' ? (
            <button
              onClick={() => onAction(agent.id, 'pause')}
              disabled={actionLoading}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-orange-500 hover:bg-orange-600 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {actionLoading === 'pause' ? (
                <ArrowPathIcon className="w-5 h-5 animate-spin" />
              ) : (
                <PauseIcon className="w-5 h-5" />
              )}
              Pause
            </button>
          ) : agent.status === 'paused' ? (
            <button
              onClick={() => onAction(agent.id, 'resume')}
              disabled={actionLoading}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {actionLoading === 'resume' ? (
                <ArrowPathIcon className="w-5 h-5 animate-spin" />
              ) : (
                <PlayIcon className="w-5 h-5" />
              )}
              Resume
            </button>
          ) : (
            <button
              onClick={() => onAction(agent.id, 'start')}
              disabled={actionLoading}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {actionLoading === 'start' ? (
                <ArrowPathIcon className="w-5 h-5 animate-spin" />
              ) : (
                <PlayIcon className="w-5 h-5" />
              )}
              Start
            </button>
          )}
          <button
            onClick={() => onAction(agent.id, 'stop')}
            disabled={actionLoading || agent.status === 'stopped' || agent.status === 'idle'}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-critical-500 hover:bg-critical-600 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {actionLoading === 'stop' ? (
              <ArrowPathIcon className="w-5 h-5 animate-spin" />
            ) : (
              <StopIcon className="w-5 h-5" />
            )}
            Stop
          </button>
          <button
            onClick={() => onAction(agent.id, 'restart')}
            disabled={actionLoading}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-aura-500 hover:bg-aura-600 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {actionLoading === 'restart' ? (
              <ArrowPathIcon className="w-5 h-5 animate-spin" />
            ) : (
              <ArrowPathIcon className="w-5 h-5" />
            )}
            Restart
          </button>
        </div>
        {/* Secondary Actions Row */}
        <div className="flex gap-3">
          <button
            onClick={() => onAction(agent.id, 'configure')}
            disabled={actionLoading}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-olive-500 hover:bg-olive-600 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Cog6ToothIcon className="w-5 h-5" />
            Configure
          </button>
          <button
            onClick={() => onAction(agent.id, 'delete')}
            disabled={actionLoading}
            className="flex items-center justify-center gap-2 px-4 py-2.5 bg-critical-500 hover:bg-critical-600 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {actionLoading === 'delete' ? (
              <ArrowPathIcon className="w-5 h-5 animate-spin" />
            ) : (
              <TrashIcon className="w-5 h-5" />
            )}
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}

// Task History Timeline
function TaskHistoryTimeline({ tasks, filter }) {
  const filteredTasks = filter === 'all'
    ? tasks
    : tasks.filter(t => t.result === filter);

  return (
    <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-surface-900 dark:text-surface-100">Task History</h3>
        <span className="text-xs text-surface-500 dark:text-surface-400">
          {filteredTasks.length} tasks
        </span>
      </div>
      <div className="space-y-3 max-h-[300px] overflow-y-auto">
        {filteredTasks.map((task) => (
          <div
            key={task.id}
            className="flex items-start gap-3 p-3 bg-surface-50 dark:bg-surface-700/50 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
          >
            {task.result === 'success' ? (
              <CheckCircleIcon className="w-5 h-5 text-olive-500 flex-shrink-0 mt-0.5" />
            ) : (
              <XCircleIcon className="w-5 h-5 text-critical-500 flex-shrink-0 mt-0.5" />
            )}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-surface-900 dark:text-surface-100 truncate">
                {task.task}
              </p>
              <div className="flex items-center gap-3 mt-1 text-xs text-surface-500 dark:text-surface-400">
                <span>{task.agentName}</span>
                <span>{task.duration}s</span>
                <span>{formatRelativeTime(task.timestamp)}</span>
              </div>
              {task.error && (
                <p className="text-xs text-critical-600 dark:text-critical-400 mt-1">
                  {task.error}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// =============================================================================
// Main Component
// =============================================================================

export default function AgentRegistry() {
  const [agents, setAgents] = useState([]);
  const [taskHistory, setTaskHistory] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [historyFilter, setHistoryFilter] = useState('all');
  const [configModalOpen, setConfigModalOpen] = useState(false);
  const [deployModalOpen, setDeployModalOpen] = useState(false);
  const [agentToConfig, setAgentToConfig] = useState(null);
  const [actionLoading, setActionLoading] = useState(null);

  // Hooks for notifications and confirmations
  const { toast } = useToast();
  const { confirm } = useConfirm();

  // Fetch data
  useEffect(() => {
    const timer = setTimeout(() => {
      setAgents(MOCK_AGENTS);
      setTaskHistory(MOCK_TASK_HISTORY);
      setLoading(false);
    }, 800);
    return () => clearTimeout(timer);
  }, []);

  // Update selected agent when agents list changes (intentionally excludes selectedAgent)
  useEffect(() => {
    if (selectedAgent) {
      const updatedAgent = agents.find(a => a.id === selectedAgent.id);
      if (updatedAgent) {
        setSelectedAgent(updatedAgent);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agents]);

  // Handle refresh
  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      // Simulate refresh delay
      await new Promise(resolve => setTimeout(resolve, 500));
      setAgents(MOCK_AGENTS);
      setTaskHistory(MOCK_TASK_HISTORY);
      toast.success('Agents refreshed');
    } catch (err) {
      toast.error('Failed to refresh agents');
    } finally {
      setIsRefreshing(false);
    }
  };

  // Filter agents
  const filteredAgents = agents.filter((agent) => {
    const matchesStatus = statusFilter === 'all' || agent.status === statusFilter;
    const matchesSearch =
      searchQuery === '' ||
      agent.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      agent.type.toLowerCase().includes(searchQuery.toLowerCase()) ||
      agent.capabilities.some(c => c.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesStatus && matchesSearch;
  });

  // Stats
  const stats = {
    total: agents.length,
    active: agents.filter(a => a.status === 'active' || a.status === 'busy').length,
    successRate: agents.length > 0
      ? (agents.reduce((sum, a) => sum + a.metrics.successRate, 0) / agents.length).toFixed(1)
      : 0,
    avgTime: agents.length > 0
      ? (agents.reduce((sum, a) => sum + a.metrics.avgExecutionTime, 0) / agents.length).toFixed(1)
      : 0,
  };

  // Update agent status in local state
  const updateAgentStatus = useCallback((agentId, newStatus) => {
    setAgents(prev => prev.map(agent =>
      agent.id === agentId ? { ...agent, status: newStatus } : agent
    ));
  }, []);

  // Remove agent from local state
  const removeAgent = useCallback((agentId) => {
    setAgents(prev => prev.filter(agent => agent.id !== agentId));
    if (selectedAgent?.id === agentId) {
      setSelectedAgent(null);
    }
  }, [selectedAgent]);

  // Handle agent control actions
  const handleAgentAction = useCallback(async (agentId, action) => {
    const agent = agents.find(a => a.id === agentId);
    if (!agent) return;

    // Handle configure action (no API call needed)
    if (action === 'configure') {
      setAgentToConfig(agent);
      setConfigModalOpen(true);
      return;
    }

    // Handle destructive actions with confirmation
    if (action === 'stop') {
      const confirmed = await confirm({
        title: 'Stop Agent',
        message: `Are you sure you want to stop "${agent.name}"? Any running tasks will be terminated.`,
        confirmText: 'Stop Agent',
        variant: 'warning',
      });
      if (!confirmed) return;
    }

    if (action === 'delete') {
      const confirmed = await confirm({
        title: 'Delete Agent',
        message: `Are you sure you want to permanently delete "${agent.name}"? This action cannot be undone.`,
        confirmText: 'Delete Agent',
        variant: 'danger',
      });
      if (!confirmed) return;
    }

    // Set loading state
    setActionLoading(action);

    try {
      switch (action) {
        case 'start':
          await startAgent(agentId);
          updateAgentStatus(agentId, 'active');
          toast.success(`Agent "${agent.name}" started successfully`);
          break;

        case 'stop':
          await stopAgent(agentId, { graceful: true });
          updateAgentStatus(agentId, 'stopped');
          toast.success(`Agent "${agent.name}" stopped successfully`);
          break;

        case 'pause':
          await pauseAgent(agentId);
          updateAgentStatus(agentId, 'paused');
          toast.success(`Agent "${agent.name}" paused successfully`);
          break;

        case 'resume':
          await resumeAgent(agentId);
          updateAgentStatus(agentId, 'active');
          toast.success(`Agent "${agent.name}" resumed successfully`);
          break;

        case 'restart':
          // Show transitional state
          updateAgentStatus(agentId, 'stopping');
          await restartAgent(agentId);
          updateAgentStatus(agentId, 'active');
          toast.success(`Agent "${agent.name}" restarted successfully`);
          break;

        case 'delete':
          await deleteAgent(agentId);
          removeAgent(agentId);
          toast.success(`Agent "${agent.name}" deleted successfully`);
          break;

        default:
          console.warn(`Unknown action: ${action}`);
      }
    } catch (error) {
      console.error(`Failed to ${action} agent:`, error);
      toast.error(
        error.message || `Failed to ${action} agent "${agent.name}"`,
        { title: 'Action Failed' }
      );
    } finally {
      setActionLoading(null);
    }
  }, [agents, confirm, toast, updateAgentStatus, removeAgent]);

  // Handle config save with validation
  const handleConfigSave = useCallback(async (config) => {
    if (!agentToConfig) return;

    // Validate configuration locally first
    const validation = validateConfigLocally(config);
    if (!validation.valid) {
      const errorMessages = validation.errors.map(e => e.message).join(', ');
      toast.error(`Configuration validation failed: ${errorMessages}`, {
        title: 'Validation Error',
      });
      return;
    }

    try {
      await updateAgentConfig(agentToConfig.id, config);
      toast.success(`Configuration for "${agentToConfig.name}" saved successfully`, {
        title: 'Configuration Saved',
      });
      setConfigModalOpen(false);
      setAgentToConfig(null);
    } catch (error) {
      console.error('Failed to save agent config:', error);
      toast.error(
        error.message || 'Failed to save configuration',
        { title: 'Save Failed' }
      );
    }
  }, [agentToConfig, toast]);

  if (loading) {
    return <PageSkeleton />;
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <header className="p-6 bg-white dark:bg-surface-800 border-b border-surface-200 dark:border-surface-700">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-olive-100 dark:bg-olive-900/30 rounded-lg">
              <CpuChipIcon className="w-6 h-6 text-olive-600 dark:text-olive-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
                Agent Registry
              </h1>
              <p className="text-surface-500 dark:text-surface-400">
                Manage and monitor autonomous agents
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3 flex-shrink-0">
            <button
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="flex items-center gap-2 px-4 py-2 text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors disabled:opacity-50"
            >
              <ArrowPathIcon className={`w-5 h-5 ${isRefreshing ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            <button
              onClick={() => setDeployModalOpen(true)}
              className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors"
            >
              <PlusIcon className="w-4 h-4" />
              Deploy Agent
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard icon={CpuChipIcon} title="Total Agents" value={stats.total} iconColor="aura" />
          <MetricCard icon={PlayIcon} title="Active" value={stats.active} iconColor="olive" />
          <MetricCard icon={CheckCircleIcon} title="Avg Success Rate" value={`${stats.successRate}%`} trend={2.3} iconColor="olive" />
          <MetricCard icon={ClockIcon} title="Avg Execution" value={`${stats.avgTime}s`} iconColor="warning" />
        </div>
      </header>

      {/* Search and Filters */}
      <div className="px-6 py-4 bg-white dark:bg-surface-800 border-b border-surface-200 dark:border-surface-700">
        <div className="flex gap-4 flex-wrap">
          <div className="relative flex-1 max-w-md">
            <MagnifyingGlassIcon className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-surface-400" />
            <input
              type="text"
              placeholder="Search agents by name, type, or capability..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
            />
          </div>
          <div className="flex gap-2">
            {[
              { key: 'all', label: 'All' },
              { key: 'active', label: 'Active' },
              { key: 'idle', label: 'Idle' },
              { key: 'busy', label: 'Busy' },
              { key: 'error', label: 'Error' },
            ].map((status) => (
              <button
                key={status.key}
                onClick={() => setStatusFilter(status.key)}
                className={`
                  px-3 py-1.5 text-sm font-medium rounded-lg transition-colors
                  ${statusFilter === status.key
                    ? 'bg-olive-500 text-white'
                    : 'bg-surface-100 dark:bg-surface-700 text-surface-700 dark:text-surface-300 hover:bg-surface-200 dark:hover:bg-surface-600'
                  }
                `}
              >
                {status.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden p-6 gap-6">
        {/* Agent Grid - pb-20 ensures content stays above floating chat button */}
        <div className="w-[500px] flex-shrink-0 overflow-y-auto pr-2 pb-20">
          <div className="grid grid-cols-1 gap-4">
            {filteredAgents.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-surface-400">
                <CpuChipIcon className="w-12 h-12 mb-3" />
                <p className="text-lg font-medium">No agents found</p>
                <p className="text-sm">Try adjusting your filters</p>
              </div>
            ) : (
              filteredAgents.map((agent) => (
                <AgentCard
                  key={agent.id}
                  agent={agent}
                  isSelected={selectedAgent?.id === agent.id}
                  onClick={() => setSelectedAgent(
                    selectedAgent?.id === agent.id ? null : agent
                  )}
                />
              ))
            )}
          </div>

          {/* Task History */}
          <div className="mt-6">
            <div className="flex items-center gap-2 mb-3">
              <h3 className="font-semibold text-surface-900 dark:text-surface-100">Task History</h3>
              <div className="flex gap-1">
                {['all', 'success', 'failed'].map((f) => (
                  <button
                    key={f}
                    onClick={() => setHistoryFilter(f)}
                    className={`
                      px-2 py-0.5 text-xs font-medium rounded transition-colors
                      ${historyFilter === f
                        ? 'bg-olive-500 text-white'
                        : 'bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-400'
                      }
                    `}
                  >
                    {f.charAt(0).toUpperCase() + f.slice(1)}
                  </button>
                ))}
              </div>
            </div>
            <TaskHistoryTimeline tasks={taskHistory} filter={historyFilter} />
          </div>
        </div>

        {/* Detail Panel */}
        <AgentDetailPanel
          agent={selectedAgent}
          onClose={() => setSelectedAgent(null)}
          onAction={handleAgentAction}
          actionLoading={actionLoading}
        />
      </div>

      {/* Agent Configuration Modal */}
      <AgentConfigModal
        agent={agentToConfig}
        isOpen={configModalOpen}
        onClose={() => {
          setConfigModalOpen(false);
          setAgentToConfig(null);
        }}
        onSave={handleConfigSave}
      />

      {/* Agent Deploy Modal */}
      <AgentDeployModal
        isOpen={deployModalOpen}
        onClose={() => setDeployModalOpen(false)}
        onDeploy={(newAgent) => {
          toast.success(`Agent "${newAgent.name}" deployed successfully`);
          handleRefresh();
        }}
      />
    </div>
  );
}
