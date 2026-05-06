import { useState, useEffect, memo } from 'react';
import {
  ExclamationCircleIcon,
  CheckCircleIcon,
  ClockIcon,
  MagnifyingGlassIcon,
  FunnelIcon,
  ArrowPathIcon,
  PlusIcon,
  DocumentTextIcon,
  CodeBracketIcon,
  RocketLaunchIcon,
  CpuChipIcon,
  DocumentMagnifyingGlassIcon,
  ArrowTopRightOnSquareIcon,
  ChartBarIcon,
  CommandLineIcon,
  ServerStackIcon,
  GlobeAltIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import { PageSkeleton } from './ui/LoadingSkeleton';
import { ProgressChart } from './ui/Charts';
import { useToast } from './ui/Toast';
import MetricCard from './ui/MetricCard';

// Severity/Status styles
const SEVERITY_STYLES = {
  critical: {
    badge: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
    border: 'border-l-critical-500',
    selectedBorder: 'border-critical-500 dark:border-critical-400',
    bg: 'bg-critical-50 dark:bg-critical-900/20',
    dot: 'bg-critical-500',
  },
  high: {
    badge: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    border: 'border-l-warning-500',
    selectedBorder: 'border-warning-500 dark:border-warning-400',
    bg: 'bg-warning-50 dark:bg-warning-900/20',
    dot: 'bg-warning-500',
  },
  medium: {
    badge: 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400',
    border: 'border-l-olive-500',
    selectedBorder: 'border-olive-500 dark:border-olive-400',
    bg: 'bg-olive-50 dark:bg-olive-900/20',
    dot: 'bg-olive-500',
  },
  low: {
    badge: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
    border: 'border-l-aura-500',
    selectedBorder: 'border-aura-500 dark:border-aura-400',
    bg: 'bg-aura-50 dark:bg-aura-900/20',
    dot: 'bg-aura-500',
  },
};

const STATUS_CONFIG = {
  open: {
    badge: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
    icon: ExclamationCircleIcon,
    label: 'Open',
  },
  investigating: {
    badge: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    icon: MagnifyingGlassIcon,
    label: 'Investigating',
  },
  resolved: {
    badge: 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400',
    icon: CheckCircleIcon,
    label: 'Resolved',
  },
};

// Mock data
const MOCK_INCIDENTS = [
  {
    id: 'INC-001',
    title: 'Memory leak in Coder Agent',
    description: 'Coder Agent memory usage steadily increasing, causing performance degradation',
    severity: 'high',
    status: 'investigating',
    source: 'CloudWatch Alarm',
    affectedService: 'coder-agent',
    assignedAgents: ['Runtime Incident Agent'],
    createdAt: '2024-12-08T08:15:00Z',
    updatedAt: '2024-12-08T10:30:00Z',
    anomalyCount: 3,
    evidenceCount: 5,
    timeline: [
      { timestamp: '2024-12-08T08:15:00Z', event: 'Incident detected', type: 'detection', agent: 'Anomaly Detector' },
      { timestamp: '2024-12-08T08:16:00Z', event: 'Runtime Incident Agent assigned', type: 'assignment', agent: 'Orchestrator' },
      { timestamp: '2024-12-08T08:20:00Z', event: 'Initial analysis started', type: 'action', agent: 'Runtime Incident Agent' },
      { timestamp: '2024-12-08T09:00:00Z', event: 'Memory profiling completed', type: 'action', agent: 'Runtime Incident Agent' },
      { timestamp: '2024-12-08T10:30:00Z', event: 'Root cause identified: unbounded cache', type: 'finding', agent: 'Runtime Incident Agent' },
    ],
    rca: {
      hypothesis: 'The Coder Agent LRU cache is not properly evicting entries due to a race condition in the cleanup routine.',
      confidence: 87,
      codeEntities: [
        { name: 'LRUCache', type: 'class', file: 'src/agents/coder/cache.py', line: 45 },
        { name: 'cleanup_expired', type: 'method', file: 'src/agents/coder/cache.py', line: 112 },
      ],
      deployments: [
        { version: 'v2.3.1', timestamp: '2024-12-07T14:00:00Z', author: 'deploy-bot', status: 'healthy' },
      ],
      mitigation: 'Add mutex lock around cache eviction logic and implement periodic forced cleanup.',
    },
    evidence: [
      { type: 'log', content: '[ERROR] Cache size exceeded threshold: 2.4GB', timestamp: '2024-12-08T08:15:00Z' },
      { type: 'metric', content: 'memory_usage_mb: 2456 (threshold: 1024)', timestamp: '2024-12-08T08:15:00Z' },
      { type: 'trace', content: 'Stack trace showing cache.py:112 -> cleanup_expired()', timestamp: '2024-12-08T09:00:00Z' },
    ],
  },
  {
    id: 'INC-002',
    title: 'High latency in GraphRAG queries',
    description: 'GraphRAG context retrieval experiencing 5x normal latency',
    severity: 'critical',
    status: 'open',
    source: 'Prometheus Alert',
    affectedService: 'context-retrieval',
    assignedAgents: [],
    createdAt: '2024-12-08T11:00:00Z',
    updatedAt: '2024-12-08T11:00:00Z',
    anomalyCount: 1,
    evidenceCount: 2,
    timeline: [
      { timestamp: '2024-12-08T11:00:00Z', event: 'Incident detected', type: 'detection', agent: 'Anomaly Detector' },
    ],
    rca: null,
    evidence: [
      { type: 'metric', content: 'p99_latency_ms: 4523 (threshold: 1000)', timestamp: '2024-12-08T11:00:00Z' },
      { type: 'log', content: '[WARN] Neptune query timeout after 5000ms', timestamp: '2024-12-08T11:00:00Z' },
    ],
  },
  {
    id: 'INC-003',
    title: 'Authentication service connection failures',
    description: 'Intermittent connection failures to auth service causing user login issues',
    severity: 'medium',
    status: 'resolved',
    source: 'User Report',
    affectedService: 'auth-service',
    assignedAgents: ['Runtime Incident Agent'],
    createdAt: '2024-12-07T15:30:00Z',
    updatedAt: '2024-12-07T18:45:00Z',
    resolvedAt: '2024-12-07T18:45:00Z',
    resolvedBy: 'admin@aenealabs.com',
    anomalyCount: 2,
    evidenceCount: 4,
    timeline: [
      { timestamp: '2024-12-07T15:30:00Z', event: 'Incident reported by user', type: 'detection', agent: 'User Report' },
      { timestamp: '2024-12-07T15:35:00Z', event: 'Runtime Incident Agent assigned', type: 'assignment', agent: 'Orchestrator' },
      { timestamp: '2024-12-07T16:00:00Z', event: 'Network analysis completed', type: 'action', agent: 'Runtime Incident Agent' },
      { timestamp: '2024-12-07T17:30:00Z', event: 'Root cause: DNS resolution timeout', type: 'finding', agent: 'Runtime Incident Agent' },
      { timestamp: '2024-12-07T18:45:00Z', event: 'Incident resolved', type: 'resolution', agent: 'admin@aenealabs.com' },
    ],
    rca: {
      hypothesis: 'DNS resolution timeout due to dnsmasq pod restart during deployment.',
      confidence: 94,
      codeEntities: [],
      deployments: [
        { version: 'dnsmasq-v1.2.0', timestamp: '2024-12-07T15:25:00Z', author: 'argocd', status: 'healthy' },
      ],
      mitigation: 'Increase DNS cache TTL and add retry logic for service discovery.',
    },
    evidence: [],
  },
];

// Format relative time
function formatRelativeTime(date) {
  if (!date) return '';
  const now = new Date();
  const then = new Date(date);
  const seconds = Math.floor((now - then) / 1000);

  if (seconds < 60) return 'Just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return then.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

// Incident Card
// Memoized to prevent re-renders when parent state changes but card props are stable
const IncidentCard = memo(function IncidentCard({ incident, isSelected, onClick }) {
  const severity = SEVERITY_STYLES[incident.severity] || SEVERITY_STYLES.medium;
  const status = STATUS_CONFIG[incident.status] || STATUS_CONFIG.open;
  const StatusIcon = status.icon;

  return (
    <button
      onClick={onClick}
      className={`
        w-full text-left p-4 rounded-xl transition-all duration-200
        ${isSelected
          ? `border-2 ${severity.selectedBorder} bg-white dark:bg-surface-800 shadow-lg`
          : 'border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 hover:border-surface-300 dark:hover:border-surface-600 hover:shadow-md'
        }
      `}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold uppercase ${severity.badge}`}>
            {incident.severity}
          </span>
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium flex items-center gap-1 ${status.badge}`}>
            <StatusIcon className="w-3 h-3" />
            {status.label}
          </span>
        </div>
        <span className="text-xs text-surface-500 dark:text-surface-400">
          {incident.id}
        </span>
      </div>

      {/* Title */}
      <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-1 line-clamp-1">
        {incident.title}
      </h3>
      <p className="text-sm text-surface-500 dark:text-surface-400 line-clamp-2 mb-3">
        {incident.description}
      </p>

      {/* Metadata */}
      <div className="flex items-center justify-between text-xs text-surface-500 dark:text-surface-400">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            <ServerStackIcon className="w-3.5 h-3.5" />
            {incident.affectedService}
          </span>
          <span className="flex items-center gap-1">
            <ClockIcon className="w-3.5 h-3.5" />
            {formatRelativeTime(incident.createdAt)}
          </span>
        </div>
        {incident.assignedAgents.length > 0 && (
          <span className="flex items-center gap-1">
            <CpuChipIcon className="w-3.5 h-3.5" />
            {incident.assignedAgents.length} agent{incident.assignedAgents.length > 1 ? 's' : ''}
          </span>
        )}
      </div>
    </button>
  );
});

// Timeline Item
function TimelineItem({ item, isLast }) {
  const typeConfig = {
    detection: { icon: ExclamationCircleIcon, color: 'text-critical-500', bg: 'bg-critical-100 dark:bg-critical-900/30' },
    assignment: { icon: CpuChipIcon, color: 'text-aura-500', bg: 'bg-aura-100 dark:bg-aura-900/30' },
    action: { icon: CommandLineIcon, color: 'text-warning-500', bg: 'bg-warning-100 dark:bg-warning-900/30' },
    finding: { icon: DocumentMagnifyingGlassIcon, color: 'text-olive-500', bg: 'bg-olive-100 dark:bg-olive-900/30' },
    resolution: { icon: CheckCircleIcon, color: 'text-olive-500', bg: 'bg-olive-100 dark:bg-olive-900/30' },
  };

  const config = typeConfig[item.type] || typeConfig.action;
  const Icon = config.icon;

  return (
    <div className="relative flex gap-4">
      {/* Connector line */}
      {!isLast && (
        <div className="absolute left-4 top-10 bottom-0 w-px bg-surface-200 dark:bg-surface-700" />
      )}

      {/* Icon */}
      <div className={`relative z-10 flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${config.bg}`}>
        <Icon className={`w-4 h-4 ${config.color}`} />
      </div>

      {/* Content */}
      <div className="flex-1 pb-6">
        <p className="text-sm font-medium text-surface-900 dark:text-surface-100">
          {item.event}
        </p>
        <div className="flex items-center gap-3 mt-1 text-xs text-surface-500 dark:text-surface-400">
          <span>{new Date(item.timestamp).toLocaleTimeString()}</span>
          <span>by {item.agent}</span>
        </div>
      </div>
    </div>
  );
}

// RCA Panel
function RCAPanel({ rca }) {
  if (!rca) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-surface-400">
        <DocumentMagnifyingGlassIcon className="w-12 h-12 mb-3" />
        <p className="text-sm">Root Cause Analysis not yet available</p>
        <p className="text-xs mt-1">Investigation in progress...</p>
      </div>
    );
  }

  const getConfidenceColor = (confidence) => {
    if (confidence >= 80) return 'text-olive-600 dark:text-olive-400';
    if (confidence >= 60) return 'text-warning-600 dark:text-warning-400';
    return 'text-critical-600 dark:text-critical-400';
  };

  return (
    <div className="space-y-6">
      {/* Confidence Score */}
      <div className="flex items-center gap-4 p-4 bg-surface-50 dark:bg-surface-700/50 rounded-lg">
        <ProgressChart
          value={rca.confidence}
          max={100}
          color={rca.confidence >= 80 ? 'olive' : rca.confidence >= 60 ? 'warning' : 'critical'}
          size={60}
          strokeWidth={6}
          showPercentage={true}
        />
        <div>
          <p className="text-sm font-medium text-surface-900 dark:text-surface-100">
            Confidence Score
          </p>
          <p className={`text-sm ${getConfidenceColor(rca.confidence)}`}>
            {rca.confidence >= 80 ? 'High confidence' : rca.confidence >= 60 ? 'Medium confidence' : 'Low confidence'}
          </p>
        </div>
      </div>

      {/* Hypothesis */}
      <div>
        <h4 className="font-semibold text-surface-900 dark:text-surface-100 mb-2">Root Cause Hypothesis</h4>
        <p className="text-surface-600 dark:text-surface-400 p-4 bg-surface-50 dark:bg-surface-700/50 rounded-lg">
          {rca.hypothesis}
        </p>
      </div>

      {/* Code Entities */}
      {rca.codeEntities.length > 0 && (
        <div>
          <h4 className="font-semibold text-surface-900 dark:text-surface-100 mb-2">Related Code</h4>
          <div className="space-y-2">
            {rca.codeEntities.map((entity, index) => (
              <div key={index} className="flex items-center justify-between p-3 bg-surface-50 dark:bg-surface-700/50 rounded-lg">
                <div className="flex items-center gap-3">
                  <CodeBracketIcon className="w-5 h-5 text-aura-500" />
                  <div>
                    <p className="font-mono text-sm text-aura-600 dark:text-aura-400">{entity.name}</p>
                    <p className="text-xs text-surface-500 dark:text-surface-400">{entity.type}</p>
                  </div>
                </div>
                <p className="font-mono text-xs text-surface-500">{entity.file}:{entity.line}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Related Deployments */}
      {rca.deployments.length > 0 && (
        <div>
          <h4 className="font-semibold text-surface-900 dark:text-surface-100 mb-2">Related Deployments</h4>
          <div className="space-y-2">
            {rca.deployments.map((deploy, index) => (
              <div key={index} className="flex items-center justify-between p-3 bg-surface-50 dark:bg-surface-700/50 rounded-lg">
                <div className="flex items-center gap-3">
                  <RocketLaunchIcon className="w-5 h-5 text-olive-500" />
                  <div>
                    <p className="font-medium text-surface-900 dark:text-surface-100">{deploy.version}</p>
                    <p className="text-xs text-surface-500 dark:text-surface-400">by {deploy.author}</p>
                  </div>
                </div>
                <div className="text-right">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${deploy.status === 'healthy' ? 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400' : 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400'}`}>
                    {deploy.status}
                  </span>
                  <p className="text-xs text-surface-500 mt-1">{formatRelativeTime(deploy.timestamp)}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Mitigation */}
      <div>
        <h4 className="font-semibold text-surface-900 dark:text-surface-100 mb-2">Recommended Mitigation</h4>
        <div className="p-4 bg-olive-50 dark:bg-olive-900/20 border border-olive-200 dark:border-olive-800 rounded-lg">
          <p className="text-olive-800 dark:text-olive-300">{rca.mitigation}</p>
        </div>
      </div>
    </div>
  );
}

// Detail Panel
function IncidentDetailPanel({ incident, onResolve, onAssign, onCreateTicket }) {
  const [activeTab, setActiveTab] = useState('timeline');

  if (!incident) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-surface-400 dark:text-surface-500 p-8">
        <DocumentTextIcon className="w-16 h-16 mb-4" />
        <h3 className="text-lg font-medium mb-2">Select an Incident</h3>
        <p className="text-sm text-center">Choose an incident to view investigation details</p>
      </div>
    );
  }

  const severity = SEVERITY_STYLES[incident.severity];
  const status = STATUS_CONFIG[incident.status];

  return (
    <div className="flex-1 flex flex-col bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 overflow-hidden">
      {/* Header */}
      <div className="p-6 border-b border-surface-200/50 dark:border-surface-700/30 bg-surface-50/50 dark:bg-surface-800/50">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className={`px-2.5 py-1 rounded-full text-xs font-semibold uppercase ${severity.badge}`}>
              {incident.severity}
            </span>
            <span className={`px-2.5 py-1 rounded-full text-xs font-medium flex items-center gap-1 ${status.badge}`}>
              <status.icon className="w-3 h-3" />
              {status.label}
            </span>
            <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-surface-100 dark:bg-surface-700 text-surface-700 dark:text-surface-300">
              {incident.id}
            </span>
          </div>
          <span className="text-xs text-surface-500">{formatRelativeTime(incident.createdAt)}</span>
        </div>
        <h2 className="text-xl font-bold text-surface-900 dark:text-surface-100 mb-2">
          {incident.title}
        </h2>
        <p className="text-surface-600 dark:text-surface-400">
          {incident.description}
        </p>

        {/* Quick Info */}
        <div className="flex items-center gap-4 mt-4 text-sm text-surface-500 dark:text-surface-400">
          <span className="flex items-center gap-1">
            <GlobeAltIcon className="w-4 h-4" />
            {incident.source}
          </span>
          <span className="flex items-center gap-1">
            <ServerStackIcon className="w-4 h-4" />
            {incident.affectedService}
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-surface-200 dark:border-surface-700">
        <nav className="flex gap-1 px-4">
          {[
            { id: 'timeline', label: 'Timeline' },
            { id: 'rca', label: 'RCA' },
            { id: 'evidence', label: 'Evidence' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`
                px-4 py-3 text-sm font-medium border-b-2 transition-colors
                ${activeTab === tab.id
                  ? 'border-aura-500 text-aura-600 dark:text-aura-400'
                  : 'border-transparent text-surface-500 hover:text-surface-700 dark:hover:text-surface-300'
                }
              `}
            >
              {tab.label}
              {tab.id === 'rca' && incident.rca && (
                <span className="ml-1.5 px-1.5 py-0.5 rounded text-xs bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400">
                  {incident.rca.confidence}%
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {activeTab === 'timeline' && (
          <div>
            {incident.timeline.map((item, index) => (
              <TimelineItem
                key={index}
                item={item}
                isLast={index === incident.timeline.length - 1}
              />
            ))}
          </div>
        )}

        {activeTab === 'rca' && (
          <RCAPanel rca={incident.rca} />
        )}

        {activeTab === 'evidence' && (
          <div className="space-y-4">
            {incident.evidence.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-surface-400">
                <DocumentTextIcon className="w-12 h-12 mb-3" />
                <p className="text-sm">No evidence collected yet</p>
              </div>
            ) : (
              incident.evidence.map((item, index) => (
                <div key={index} className="p-4 bg-surface-50 dark:bg-surface-700/50 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <span className="px-2 py-0.5 rounded text-xs font-medium bg-surface-200 dark:bg-surface-600 text-surface-700 dark:text-surface-300 uppercase">
                      {item.type}
                    </span>
                    <span className="text-xs text-surface-500">{formatRelativeTime(item.timestamp)}</span>
                  </div>
                  <pre className="font-mono text-sm text-surface-100 whitespace-pre-wrap bg-surface-900 dark:bg-surface-950 p-3 rounded">
                    {item.content}
                  </pre>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Action Footer */}
      {incident.status !== 'resolved' && (
        <div className="p-4 border-t border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50">
          <div className="flex gap-3">
            {incident.assignedAgents.length === 0 && (
              <button
                onClick={() => onAssign(incident.id)}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors"
              >
                <CpuChipIcon className="w-5 h-5" />
                Assign Agent
              </button>
            )}
            <button
              onClick={onCreateTicket}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-aura-500 hover:bg-aura-600 text-white rounded-lg font-medium transition-colors"
            >
              <ArrowTopRightOnSquareIcon className="w-5 h-5" />
              Create Ticket
            </button>
            <button
              onClick={() => onResolve(incident.id)}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-olive-500 hover:bg-olive-600 text-white rounded-lg font-medium transition-colors"
            >
              <CheckCircleIcon className="w-5 h-5" />
              Mark Resolved
            </button>
          </div>
        </div>
      )}

      {/* Resolved Badge */}
      {incident.status === 'resolved' && (
        <div className="p-4 border-t border-surface-200 dark:border-surface-700 bg-olive-50 dark:bg-olive-900/20">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircleIcon className="w-5 h-5 text-olive-600 dark:text-olive-400" />
              <span className="text-sm font-medium text-olive-700 dark:text-olive-300">
                Resolved by {incident.resolvedBy}
              </span>
            </div>
            <span className="text-sm text-olive-600 dark:text-olive-400">
              {formatRelativeTime(incident.resolvedAt)}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

// New Incident Modal
function NewIncidentModal({ isOpen, onClose, onSubmit }) {
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    severity: 'medium',
    affectedService: '',
    source: 'Manual Entry',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);

    // Simulate API call
    await new Promise((resolve) => setTimeout(resolve, 500));

    onSubmit({
      ...formData,
      id: `INC-${String(Date.now()).slice(-3)}`,
      status: 'open',
      assignedAgents: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      anomalyCount: 0,
      evidenceCount: 0,
      timeline: [
        { timestamp: new Date().toISOString(), event: 'Incident created manually', type: 'detection', agent: 'Manual Entry' },
      ],
      rca: null,
      evidence: [],
    });

    setIsSubmitting(false);
    setFormData({
      title: '',
      description: '',
      severity: 'medium',
      affectedService: '',
      source: 'Manual Entry',
    });
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-lg bg-white dark:bg-surface-800 rounded-2xl shadow-xl border border-surface-200 dark:border-surface-700 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-surface-200 dark:border-surface-700">
          <h2 className="text-xl font-bold text-surface-900 dark:text-surface-100">
            New Incident
          </h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
          >
            <XMarkIcon className="w-5 h-5 text-surface-500" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
              Title *
            </label>
            <input
              type="text"
              required
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              placeholder="Brief description of the incident"
              className="w-full px-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
              Description
            </label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Detailed description of what's happening..."
              rows={3}
              className="w-full px-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-aura-500 focus:border-transparent resize-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                Severity *
              </label>
              <select
                required
                value={formData.severity}
                onChange={(e) => setFormData({ ...formData, severity: e.target.value })}
                className="w-full px-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
              >
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                Affected Service *
              </label>
              <input
                type="text"
                required
                value={formData.affectedService}
                onChange={(e) => setFormData({ ...formData, affectedService: e.target.value })}
                placeholder="e.g., auth-service"
                className="w-full px-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
              Source
            </label>
            <select
              value={formData.source}
              onChange={(e) => setFormData({ ...formData, source: e.target.value })}
              className="w-full px-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
            >
              <option value="Manual Entry">Manual Entry</option>
              <option value="User Report">User Report</option>
              <option value="CloudWatch Alarm">CloudWatch Alarm</option>
              <option value="Prometheus Alert">Prometheus Alert</option>
              <option value="Security Scanner">Security Scanner</option>
            </select>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2.5 border border-surface-300 dark:border-surface-600 text-surface-700 dark:text-surface-300 rounded-lg font-medium hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex-1 px-4 py-2.5 bg-aura-500 hover:bg-aura-600 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
            >
              {isSubmitting ? 'Creating...' : 'Create Incident'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// Create Ticket Modal
function CreateTicketModal({ isOpen, onClose, incident, onSubmit }) {
  const [formData, setFormData] = useState({
    ticketingSystem: 'zendesk',
    priority: 'high',
    assignee: '',
    additionalNotes: '',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const ticketingSystems = [
    { id: 'zendesk', name: 'Zendesk', icon: '🎫' },
    { id: 'servicenow', name: 'ServiceNow', icon: '📋' },
    { id: 'linear', name: 'Linear', icon: '📐' },
    { id: 'jira', name: 'Jira', icon: '🔷' },
  ];

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);

    // Simulate API call to external ticketing system
    await new Promise((resolve) => setTimeout(resolve, 800));

    onSubmit({
      ticketId: `${formData.ticketingSystem.toUpperCase()}-${String(Date.now()).slice(-6)}`,
      system: formData.ticketingSystem,
      incidentId: incident.id,
      priority: formData.priority,
      assignee: formData.assignee,
    });

    setIsSubmitting(false);
    onClose();
  };

  if (!isOpen || !incident) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-lg bg-white dark:bg-surface-800 rounded-2xl shadow-xl border border-surface-200 dark:border-surface-700 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-surface-200 dark:border-surface-700">
          <div>
            <h2 className="text-xl font-bold text-surface-900 dark:text-surface-100">
              Create External Ticket
            </h2>
            <p className="text-sm text-surface-500 dark:text-surface-400 mt-1">
              Export {incident.id} to external ticketing system
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
          >
            <XMarkIcon className="w-5 h-5 text-surface-500" />
          </button>
        </div>

        {/* Incident Summary */}
        <div className="px-6 py-4 bg-surface-50 dark:bg-surface-700/50 border-b border-surface-200 dark:border-surface-700">
          <div className="flex items-start gap-3">
            <div className={`p-2 rounded-lg ${SEVERITY_STYLES[incident.severity].bg}`}>
              <ExclamationCircleIcon className={`w-5 h-5 ${incident.severity === 'critical' ? 'text-critical-600 dark:text-critical-400' : incident.severity === 'high' ? 'text-warning-600 dark:text-warning-400' : 'text-olive-600 dark:text-olive-400'}`} />
            </div>
            <div>
              <h3 className="font-semibold text-surface-900 dark:text-surface-100">
                {incident.title}
              </h3>
              <p className="text-sm text-surface-500 dark:text-surface-400 line-clamp-2">
                {incident.description}
              </p>
            </div>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
              Ticketing System
            </label>
            <div className="grid grid-cols-2 gap-2">
              {ticketingSystems.map((system) => (
                <button
                  key={system.id}
                  type="button"
                  onClick={() => setFormData({ ...formData, ticketingSystem: system.id })}
                  className={`flex items-center gap-2 p-3 rounded-lg border transition-all ${
                    formData.ticketingSystem === system.id
                      ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/20 text-aura-700 dark:text-aura-300'
                      : 'border-surface-200 dark:border-surface-600 hover:border-surface-300 dark:hover:border-surface-500'
                  }`}
                >
                  <span className="text-lg">{system.icon}</span>
                  <span className="font-medium text-surface-900 dark:text-surface-100">{system.name}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                Priority
              </label>
              <select
                value={formData.priority}
                onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
                className="w-full px-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
              >
                <option value="urgent">Urgent</option>
                <option value="high">High</option>
                <option value="normal">Normal</option>
                <option value="low">Low</option>
              </select>
              <p className="text-xs text-surface-500 mt-1">
                Auto-mapped from {incident.severity} severity
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                Assignee (Optional)
              </label>
              <input
                type="text"
                value={formData.assignee}
                onChange={(e) => setFormData({ ...formData, assignee: e.target.value })}
                placeholder="email@company.com"
                className="w-full px-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
              Additional Notes
            </label>
            <textarea
              value={formData.additionalNotes}
              onChange={(e) => setFormData({ ...formData, additionalNotes: e.target.value })}
              placeholder="Any additional context for the external team..."
              rows={2}
              className="w-full px-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-aura-500 focus:border-transparent resize-none"
            />
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2.5 border border-surface-300 dark:border-surface-600 text-surface-700 dark:text-surface-300 rounded-lg font-medium hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-aura-500 hover:bg-aura-600 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
            >
              <ArrowTopRightOnSquareIcon className="w-4 h-4" />
              {isSubmitting ? 'Creating...' : 'Create Ticket'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// Main Component
export default function IncidentInvestigations() {
  const [incidents, setIncidents] = useState([]);
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [showNewIncidentModal, setShowNewIncidentModal] = useState(false);
  const [showCreateTicketModal, setShowCreateTicketModal] = useState(false);
  const { toast } = useToast();

  // Fetch data — calls the backend /api/v1/incidents endpoint and falls
  // back to MOCK_INCIDENTS only if the API is unreachable. Mirrors the
  // pattern used by ApprovalDashboard and SecurityAlertsContext so all
  // three pages behave consistently in dev (real backend, seeded data)
  // and in offline demos (frontend mocks).
  const apiBase = import.meta.env.VITE_API_URL || '/api/v1';

  const fetchIncidents = async () => {
    try {
      const response = await fetch(`${apiBase}/incidents`);
      if (!response.ok) {
        throw new Error(`API responded ${response.status}`);
      }
      const data = await response.json();
      setIncidents(data.incidents || []);
    } catch (err) {
      console.warn('Incidents API unavailable, using mock data:', err.message);
      setIncidents(MOCK_INCIDENTS);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIncidents();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Refresh handler
  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      const response = await fetch(`${apiBase}/incidents`);
      if (!response.ok) {
        throw new Error(`API responded ${response.status}`);
      }
      const data = await response.json();
      setIncidents(data.incidents || []);
      toast.success('Incident Investigations refreshed');
    } catch (err) {
      console.warn('Incidents API unavailable on refresh, using mock data:', err.message);
      setIncidents(MOCK_INCIDENTS);
      toast.info('Showing demo data (API unavailable)');
    } finally {
      setIsRefreshing(false);
    }
  };

  // Filter incidents
  const filteredIncidents = incidents.filter((incident) => {
    const matchesStatus = statusFilter === 'all' || incident.status === statusFilter;
    const matchesSearch =
      searchQuery === '' ||
      incident.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      incident.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      incident.affectedService.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesStatus && matchesSearch;
  });

  // Stats
  const stats = {
    total: incidents.length,
    open: incidents.filter(i => i.status === 'open').length,
    investigating: incidents.filter(i => i.status === 'investigating').length,
    rcaSuccessRate: 86,
  };

  const handleResolve = (id) => {
    setIncidents(prev =>
      prev.map(i =>
        i.id === id
          ? { ...i, status: 'resolved', resolvedAt: new Date().toISOString(), resolvedBy: 'admin@aenealabs.com' }
          : i
      )
    );
    setSelectedIncident(null);
  };

  const handleAssign = (id) => {
    setIncidents(prev =>
      prev.map(i =>
        i.id === id
          ? { ...i, status: 'investigating', assignedAgents: ['Runtime Incident Agent'] }
          : i
      )
    );
  };

  // Handle creating a new incident
  const handleCreateIncident = (newIncident) => {
    setIncidents(prev => [newIncident, ...prev]);
    toast.success(`Incident ${newIncident.id} created successfully`);
  };

  // Handle creating an external ticket
  const handleCreateTicket = (ticketData) => {
    // In production, this would call the ticketing API
    toast.success(`Ticket ${ticketData.ticketId} created in ${ticketData.system}`);

    // Add ticket reference to incident timeline
    if (selectedIncident) {
      setIncidents(prev =>
        prev.map(i =>
          i.id === ticketData.incidentId
            ? {
                ...i,
                timeline: [
                  ...i.timeline,
                  {
                    timestamp: new Date().toISOString(),
                    event: `External ticket created: ${ticketData.ticketId}`,
                    type: 'action',
                    agent: 'User',
                  },
                ],
              }
            : i
        )
      );
      // Update selected incident to show new timeline entry
      setSelectedIncident(prev => prev ? {
        ...prev,
        timeline: [
          ...prev.timeline,
          {
            timestamp: new Date().toISOString(),
            event: `External ticket created: ${ticketData.ticketId}`,
            type: 'action',
            agent: 'User',
          },
        ],
      } : null);
    }
  };

  if (loading) {
    return <PageSkeleton />;
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <header className="p-6 bg-white dark:bg-surface-800 border-b border-surface-200 dark:border-surface-700">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-warning-100 dark:bg-warning-900/30 rounded-lg">
              <ExclamationCircleIcon className="w-6 h-6 text-warning-600 dark:text-warning-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
                Incident Investigations
              </h1>
              <p className="text-surface-500 dark:text-surface-400">
                Code-aware incident response with AI-powered RCA
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3 flex-shrink-0">
            <button
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="flex items-center gap-2 px-4 py-2 text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors disabled:opacity-50"
            >
              <ArrowPathIcon className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            <button
              onClick={() => setShowNewIncidentModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-aura-500 hover:bg-aura-600 text-white rounded-lg font-medium transition-colors"
            >
              <PlusIcon className="w-4 h-4" />
              New Incident
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard icon={DocumentTextIcon} title="Total Incidents" value={stats.total} iconColor="aura" />
          <MetricCard icon={ExclamationCircleIcon} title="Open" value={stats.open} iconColor="critical" />
          <MetricCard icon={MagnifyingGlassIcon} title="Investigating" value={stats.investigating} iconColor="warning" />
          <MetricCard icon={ChartBarIcon} title="RCA Success Rate" value={`${stats.rcaSuccessRate}%`} iconColor="olive" />
        </div>
      </header>

      {/* Search and Filters */}
      <div className="px-6 py-4 bg-white dark:bg-surface-800 border-b border-surface-200 dark:border-surface-700">
        <div className="flex gap-4 flex-wrap">
          <div className="relative flex-1 max-w-md">
            <MagnifyingGlassIcon className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-surface-400" />
            <input
              type="text"
              placeholder="Search incidents..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
            />
          </div>
          <div className="flex gap-2">
            {[
              { key: 'all', label: 'All' },
              { key: 'open', label: 'Open' },
              { key: 'investigating', label: 'Investigating' },
              { key: 'resolved', label: 'Resolved' },
            ].map((status) => (
              <button
                key={status.key}
                onClick={() => setStatusFilter(status.key)}
                className={`
                  px-3 py-1.5 text-sm font-medium rounded-lg transition-colors
                  ${statusFilter === status.key
                    ? 'bg-aura-500 text-white'
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
        {/* Incident List */}
        <div className="w-[400px] flex-shrink-0 overflow-y-auto space-y-3 pr-2">
          {filteredIncidents.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-surface-400">
              <FunnelIcon className="w-12 h-12 mb-3" />
              <p className="text-lg font-medium">No incidents found</p>
            </div>
          ) : (
            filteredIncidents.map((incident) => (
              <IncidentCard
                key={incident.id}
                incident={incident}
                isSelected={selectedIncident?.id === incident.id}
                onClick={() => setSelectedIncident(
                  selectedIncident?.id === incident.id ? null : incident
                )}
              />
            ))
          )}
        </div>

        {/* Detail Panel */}
        <IncidentDetailPanel
          incident={selectedIncident}
          onResolve={handleResolve}
          onAssign={handleAssign}
          onCreateTicket={() => setShowCreateTicketModal(true)}
        />
      </div>

      {/* Modals */}
      <NewIncidentModal
        isOpen={showNewIncidentModal}
        onClose={() => setShowNewIncidentModal(false)}
        onSubmit={handleCreateIncident}
      />
      <CreateTicketModal
        isOpen={showCreateTicketModal}
        onClose={() => setShowCreateTicketModal(false)}
        incident={selectedIncident}
        onSubmit={handleCreateTicket}
      />
    </div>
  );
}
