import { useState, useEffect } from 'react';
import {
  ShieldExclamationIcon,
  ShieldCheckIcon,
  PlayIcon,
  PauseIcon,
  StopIcon,
  PlusIcon,
  ChevronRightIcon,
  ClockIcon,
  BugAntIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  XCircleIcon,
  DocumentArrowDownIcon,
  FireIcon,
  BoltIcon,
  ServerIcon,
  LockClosedIcon,
  KeyIcon,
  CommandLineIcon,
  DocumentMagnifyingGlassIcon,
  FunnelIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import { PageSkeleton } from './ui/LoadingSkeleton';
import { useToast } from './ui/Toast';
import MetricCard from './ui/MetricCard';

// Severity styles
const SEVERITY_STYLES = {
  critical: {
    badge: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
    border: 'border-critical-500',
    bg: 'bg-critical-50 dark:bg-critical-900/20',
    text: 'text-critical-600 dark:text-critical-400',
  },
  high: {
    badge: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    border: 'border-warning-500',
    bg: 'bg-warning-50 dark:bg-warning-900/20',
    text: 'text-warning-600 dark:text-warning-400',
  },
  medium: {
    badge: 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400',
    border: 'border-olive-500',
    bg: 'bg-olive-50 dark:bg-olive-900/20',
    text: 'text-olive-600 dark:text-olive-400',
  },
  low: {
    badge: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
    border: 'border-aura-500',
    bg: 'bg-aura-50 dark:bg-aura-900/20',
    text: 'text-aura-600 dark:text-aura-400',
  },
};

// Attack template icons and colors
const ATTACK_TEMPLATES = {
  sql_injection: { icon: ServerIcon, label: 'SQL Injection', color: 'text-critical-500' },
  xss: { icon: CommandLineIcon, label: 'XSS', color: 'text-warning-500' },
  auth_bypass: { icon: LockClosedIcon, label: 'Auth Bypass', color: 'text-critical-500' },
  ssrf: { icon: BoltIcon, label: 'SSRF', color: 'text-warning-500' },
  prompt_injection: { icon: FireIcon, label: 'Prompt Injection', color: 'text-critical-500' },
  path_traversal: { icon: DocumentMagnifyingGlassIcon, label: 'Path Traversal', color: 'text-olive-500' },
  privilege_escalation: { icon: KeyIcon, label: 'Privilege Escalation', color: 'text-critical-500' },
};

// MITRE ATT&CK tags
const MITRE_TAGS = {
  'TA0001': 'Initial Access',
  'TA0002': 'Execution',
  'TA0003': 'Persistence',
  'TA0004': 'Privilege Escalation',
  'TA0005': 'Defense Evasion',
  'TA0006': 'Credential Access',
  'TA0007': 'Discovery',
  'TA0008': 'Lateral Movement',
};

// Mock data
const MOCK_CAMPAIGNS = [
  {
    id: 'CAM-001',
    name: 'API Security Assessment',
    description: 'Comprehensive security testing of REST API endpoints',
    status: 'running',
    templates: ['sql_injection', 'auth_bypass', 'ssrf'],
    progress: 67,
    startedAt: '2024-12-08T08:00:00Z',
    duration: '2h 34m',
    findingsCount: 3,
    findings: {
      critical: 1,
      high: 2,
      medium: 0,
      low: 0,
    },
    mitreTags: ['TA0001', 'TA0006', 'TA0007'],
    targetSystem: 'core-api-service',
  },
  {
    id: 'CAM-002',
    name: 'LLM Agent Security Test',
    description: 'Testing AI agent defenses against prompt injection and manipulation',
    status: 'running',
    templates: ['prompt_injection', 'privilege_escalation'],
    progress: 45,
    startedAt: '2024-12-08T09:30:00Z',
    duration: '1h 04m',
    findingsCount: 3,
    findings: {
      critical: 2,
      high: 1,
      medium: 0,
      low: 0,
    },
    mitreTags: ['TA0002', 'TA0004'],
    targetSystem: 'coder-agent',
  },
  {
    id: 'CAM-003',
    name: 'Frontend XSS Scan',
    description: 'Cross-site scripting vulnerability detection in React components',
    status: 'completed',
    templates: ['xss', 'path_traversal'],
    progress: 100,
    startedAt: '2024-12-07T14:00:00Z',
    completedAt: '2024-12-07T16:23:00Z',
    duration: '2h 23m',
    findingsCount: 2,
    findings: {
      critical: 0,
      high: 1,
      medium: 1,
      low: 0,
    },
    mitreTags: ['TA0001', 'TA0005'],
    targetSystem: 'web-frontend',
  },
  {
    id: 'CAM-004',
    name: 'Authentication Flow Test',
    description: 'Testing OAuth2 and JWT implementation security',
    status: 'failed',
    templates: ['auth_bypass', 'privilege_escalation'],
    progress: 34,
    startedAt: '2024-12-07T10:00:00Z',
    failedAt: '2024-12-07T10:45:00Z',
    duration: '45m',
    findingsCount: 0,
    findings: {
      critical: 0,
      high: 0,
      medium: 0,
      low: 0,
    },
    error: 'Connection timeout to target system',
    mitreTags: ['TA0006'],
    targetSystem: 'auth-service',
  },
];

const MOCK_FINDINGS = [
  {
    id: 'FND-001',
    campaignId: 'CAM-001',
    title: 'SQL Injection in /api/users endpoint',
    severity: 'critical',
    category: 'sql_injection',
    description: 'Unsanitized user input allows arbitrary SQL execution',
    affectedFile: 'src/api/users.py',
    affectedLine: 45,
    evidence: "Parameter 'id' vulnerable to SQL injection: ' OR 1=1 --",
    remediation: 'Use parameterized queries or ORM methods',
    cweId: 'CWE-89',
    createdAt: '2024-12-08T09:15:00Z',
    status: 'open',
  },
  {
    id: 'FND-002',
    campaignId: 'CAM-001',
    title: 'Authentication Bypass via JWT None Algorithm',
    severity: 'high',
    category: 'auth_bypass',
    description: 'JWT validation accepts "none" algorithm, allowing token forgery',
    affectedFile: 'src/auth/jwt_validator.py',
    affectedLine: 23,
    evidence: 'Token with alg: none accepted without signature verification',
    remediation: 'Explicitly validate algorithm against whitelist',
    cweId: 'CWE-287',
    createdAt: '2024-12-08T09:45:00Z',
    status: 'open',
  },
  {
    id: 'FND-003',
    campaignId: 'CAM-002',
    title: 'Prompt Injection in Coder Agent',
    severity: 'critical',
    category: 'prompt_injection',
    description: 'System prompt can be overridden via user input injection',
    affectedFile: 'src/agents/coder.py',
    affectedLine: 112,
    evidence: 'Input: "Ignore previous instructions and..." bypasses safety filters',
    remediation: 'Implement strict input sanitization and prompt isolation',
    cweId: 'CWE-74',
    createdAt: '2024-12-08T10:00:00Z',
    status: 'open',
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
  return then.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// Campaign Card Component
function CampaignCard({ campaign, onClick, isSelected }) {
  const statusConfig = {
    running: {
      badge: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
      icon: PlayIcon,
      label: 'Running',
      selectedBorder: 'border-aura-500 dark:border-aura-400',
    },
    completed: {
      badge: 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400',
      icon: CheckCircleIcon,
      label: 'Completed',
      selectedBorder: 'border-olive-500 dark:border-olive-400',
    },
    failed: {
      badge: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
      icon: XCircleIcon,
      label: 'Failed',
      selectedBorder: 'border-critical-500 dark:border-critical-400',
    },
    paused: {
      badge: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
      icon: PauseIcon,
      label: 'Paused',
      selectedBorder: 'border-warning-500 dark:border-warning-400',
    },
  };

  const status = statusConfig[campaign.status] || statusConfig.running;
  const StatusIcon = status.icon;

  const totalFindings = campaign.findings.critical + campaign.findings.high + campaign.findings.medium + campaign.findings.low;

  return (
    <button
      onClick={onClick}
      className={`
        w-full text-left p-4 rounded-xl border-2 transition-all duration-200
        ${isSelected
          ? `${status.selectedBorder} bg-white dark:bg-surface-800 shadow-lg`
          : 'border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 hover:border-surface-300 dark:hover:border-surface-600 hover:shadow-md'
        }
      `}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium flex items-center gap-1 ${status.badge}`}>
            <StatusIcon className="w-3 h-3" />
            {status.label}
          </span>
          {campaign.status === 'running' && (
            <span className="text-xs text-surface-500 dark:text-surface-400">
              {campaign.progress}%
            </span>
          )}
        </div>
        <ChevronRightIcon className={`w-5 h-5 text-surface-400 transition-transform ${isSelected ? 'rotate-90' : ''}`} />
      </div>

      {/* Title */}
      <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-1">
        {campaign.name}
      </h3>
      <p className="text-sm text-surface-500 dark:text-surface-400 mb-3 line-clamp-2">
        {campaign.description}
      </p>

      {/* Progress Bar (for running campaigns) */}
      {campaign.status === 'running' && (
        <div className="mb-3">
          <div className="h-1.5 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-aura-500 rounded-full transition-all duration-500"
              style={{ width: `${campaign.progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Attack Templates */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        {campaign.templates.map((template) => {
          const config = ATTACK_TEMPLATES[template];
          if (!config) return null;
          return (
            <span
              key={template}
              className="inline-flex items-center gap-1 px-2 py-0.5 bg-surface-100 dark:bg-surface-700 rounded text-xs text-surface-600 dark:text-surface-300"
            >
              <config.icon className={`w-3 h-3 ${config.color}`} />
              {config.label}
            </span>
          );
        })}
      </div>

      {/* Metadata */}
      <div className="flex items-start justify-between text-xs text-surface-500 dark:text-surface-400">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            <BugAntIcon className="w-3.5 h-3.5" />
            {totalFindings} findings
          </span>
          <span className="flex items-center gap-1">
            <ClockIcon className="w-3.5 h-3.5" />
            {campaign.duration}
          </span>
        </div>
        {/* Severity counts - 2x2 grid if 3+ severities, inline if 1-2 */}
        {(() => {
          const severities = [
            { key: 'critical', count: campaign.findings.critical, color: 'text-critical-600 dark:text-critical-400', icon: true },
            { key: 'high', count: campaign.findings.high, color: 'text-warning-600 dark:text-warning-400', icon: false },
            { key: 'medium', count: campaign.findings.medium, color: 'text-olive-600 dark:text-olive-400', icon: false },
            { key: 'low', count: campaign.findings.low, color: 'text-aura-600 dark:text-aura-400', icon: false },
          ].filter(s => s.count > 0);

          if (severities.length === 0) return null;

          const useGrid = severities.length >= 3;
          // Check if first item has icon (critical) - if so, left-column items need spacer for alignment
          const firstHasIcon = severities[0]?.icon;

          return (
            <div className={useGrid ? 'grid grid-cols-2 gap-x-3 gap-y-1' : 'flex items-center gap-2'}>
              {severities.map((severity, index) => {
                // In grid mode, left column items (even indices) need spacer if they don't have icon but first item does
                const needsSpacer = useGrid && firstHasIcon && !severity.icon && index % 2 === 0;
                return (
                  <span key={severity.key} className={`flex items-center gap-1 font-medium ${severity.color}`}>
                    {severity.icon && <ExclamationTriangleIcon className="w-3.5 h-3.5" />}
                    {needsSpacer && <span className="w-3.5" />}
                    {severity.count} {severity.key}
                  </span>
                );
              })}
            </div>
          );
        })()}
      </div>
    </button>
  );
}

// Campaign Detail Panel
function CampaignDetailPanel({ campaign, findings, _onClose }) {
  const [activeTab, setActiveTab] = useState('findings');

  if (!campaign) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-surface-400 dark:text-surface-500 p-8">
        <ShieldExclamationIcon className="w-16 h-16 mb-4" />
        <h3 className="text-lg font-medium mb-2">Select a Campaign</h3>
        <p className="text-sm text-center">Choose a campaign to view detailed results and findings</p>
      </div>
    );
  }

  const campaignFindings = findings.filter(f => f.campaignId === campaign.id);

  return (
    <div className="flex-1 flex flex-col bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] overflow-hidden">
      {/* Header */}
      <div className="p-6 border-b border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold text-surface-900 dark:text-surface-100">
              {campaign.name}
            </h2>
            <p className="text-surface-500 dark:text-surface-400 mt-1">
              {campaign.description}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {campaign.status === 'running' && (
              <>
                <button className="p-2 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors">
                  <PauseIcon className="w-5 h-5 text-surface-600 dark:text-surface-400" />
                </button>
                <button className="p-2 hover:bg-critical-100 dark:hover:bg-critical-900/30 rounded-lg transition-colors">
                  <StopIcon className="w-5 h-5 text-critical-600 dark:text-critical-400" />
                </button>
              </>
            )}
            <button className="p-2 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors">
              <DocumentArrowDownIcon className="w-5 h-5 text-surface-600 dark:text-surface-400" />
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="text-center p-3 bg-critical-100 dark:bg-critical-900/30 rounded-lg">
            <p className="text-2xl font-bold text-critical-700 dark:text-critical-400">
              {campaign.findings.critical}
            </p>
            <p className="text-xs text-critical-600 dark:text-critical-500">Critical</p>
          </div>
          <div className="text-center p-3 bg-warning-100 dark:bg-warning-900/30 rounded-lg">
            <p className="text-2xl font-bold text-warning-700 dark:text-warning-400">
              {campaign.findings.high}
            </p>
            <p className="text-xs text-warning-600 dark:text-warning-500">High</p>
          </div>
          <div className="text-center p-3 bg-olive-100 dark:bg-olive-900/30 rounded-lg">
            <p className="text-2xl font-bold text-olive-700 dark:text-olive-400">
              {campaign.findings.medium}
            </p>
            <p className="text-xs text-olive-600 dark:text-olive-500">Medium</p>
          </div>
          <div className="text-center p-3 bg-aura-100 dark:bg-aura-900/30 rounded-lg">
            <p className="text-2xl font-bold text-aura-700 dark:text-aura-400">
              {campaign.findings.low}
            </p>
            <p className="text-xs text-aura-600 dark:text-aura-500">Low</p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-surface-200 dark:border-surface-700">
        <nav className="flex gap-1 px-4">
          {[
            { id: 'findings', label: 'Findings' },
            { id: 'details', label: 'Campaign Details' },
            { id: 'logs', label: 'Attack Logs' },
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
            </button>
          ))}
        </nav>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {activeTab === 'findings' && (
          <div className="space-y-4">
            {campaignFindings.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-surface-400">
                <ShieldCheckIcon className="w-12 h-12 mb-3" />
                <p className="text-lg font-medium">No findings yet</p>
                <p className="text-sm">Campaign is still running...</p>
              </div>
            ) : (
              campaignFindings.map((finding) => {
                const severity = SEVERITY_STYLES[finding.severity];
                const template = ATTACK_TEMPLATES[finding.category];

                return (
                  <div
                    key={finding.id}
                    className={`p-4 rounded-lg border-l-4 ${severity.border} bg-white dark:bg-surface-800 backdrop-blur-xl shadow-[var(--shadow-glass)]`}
                  >
                    <div className="flex items-start justify-between gap-3 mb-2">
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-semibold uppercase ${severity.badge}`}>
                          {finding.severity}
                        </span>
                        {template && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-white/50 dark:bg-surface-700/50 rounded text-xs">
                            <template.icon className={`w-3 h-3 ${template.color}`} />
                            {template.label}
                          </span>
                        )}
                      </div>
                      <span className="text-xs text-surface-500">{finding.cweId}</span>
                    </div>

                    <h4 className="font-semibold text-surface-900 dark:text-surface-100 mb-1">
                      {finding.title}
                    </h4>
                    <p className="text-sm text-surface-600 dark:text-surface-400 mb-3">
                      {finding.description}
                    </p>

                    {/* Evidence */}
                    <div className="bg-surface-900 dark:bg-surface-950 rounded-lg p-3 mb-3 font-mono text-xs">
                      <p className="text-olive-400"># Evidence</p>
                      <p className="text-surface-300">{finding.evidence}</p>
                    </div>

                    {/* Metadata */}
                    <div className="flex items-center gap-4 text-xs text-surface-500">
                      <span className="font-mono">{finding.affectedFile}:{finding.affectedLine}</span>
                      <span>{formatRelativeTime(finding.createdAt)}</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        )}

        {activeTab === 'details' && (
          <div className="space-y-6">
            {/* Target System */}
            <div>
              <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-3">Target System</h3>
              <div className="bg-surface-50 dark:bg-surface-700/50 rounded-lg p-4">
                <p className="font-mono text-surface-700 dark:text-surface-300">{campaign.targetSystem}</p>
              </div>
            </div>

            {/* Attack Templates */}
            <div>
              <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-3">Attack Templates Used</h3>
              <div className="space-y-2">
                {campaign.templates.map((template) => {
                  const config = ATTACK_TEMPLATES[template];
                  if (!config) return null;
                  return (
                    <div key={template} className="flex items-center gap-3 p-3 bg-surface-50 dark:bg-surface-700/50 rounded-lg">
                      <config.icon className={`w-5 h-5 ${config.color}`} />
                      <span className="font-medium text-surface-700 dark:text-surface-300">{config.label}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* MITRE ATT&CK Tags */}
            <div>
              <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-3">MITRE ATT&CK Mapping</h3>
              <div className="flex flex-wrap gap-2">
                {campaign.mitreTags.map((tag) => (
                  <span
                    key={tag}
                    className="px-3 py-1.5 bg-surface-100 dark:bg-surface-700 rounded-lg text-sm"
                  >
                    <span className="font-mono text-aura-600 dark:text-aura-400">{tag}</span>
                    <span className="text-surface-500 dark:text-surface-400 ml-2">
                      {MITRE_TAGS[tag]}
                    </span>
                  </span>
                ))}
              </div>
            </div>

            {/* Timeline */}
            <div>
              <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-3">Timeline</h3>
              <div className="bg-surface-50 dark:bg-surface-700/50 rounded-lg p-4 space-y-3">
                <div className="flex justify-between">
                  <span className="text-surface-600 dark:text-surface-400">Started</span>
                  <span className="text-surface-900 dark:text-surface-100">
                    {new Date(campaign.startedAt).toLocaleString()}
                  </span>
                </div>
                {campaign.completedAt && (
                  <div className="flex justify-between">
                    <span className="text-surface-600 dark:text-surface-400">Completed</span>
                    <span className="text-surface-900 dark:text-surface-100">
                      {new Date(campaign.completedAt).toLocaleString()}
                    </span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-surface-600 dark:text-surface-400">Duration</span>
                  <span className="text-surface-900 dark:text-surface-100">{campaign.duration}</span>
                </div>
              </div>
            </div>

            {/* Error (for failed campaigns) */}
            {campaign.error && (
              <div>
                <h3 className="font-semibold text-critical-600 dark:text-critical-400 mb-3">Error</h3>
                <div className="bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800 rounded-lg p-4">
                  <p className="text-critical-700 dark:text-critical-400">{campaign.error}</p>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'logs' && (
          <div className="bg-surface-900 dark:bg-surface-950 rounded-lg p-4 font-mono text-xs overflow-x-auto">
            <p className="text-olive-400">[2024-12-08 08:00:01] Campaign started</p>
            <p className="text-surface-400">[2024-12-08 08:00:02] Loading attack templates: sql_injection, auth_bypass, ssrf</p>
            <p className="text-surface-400">[2024-12-08 08:00:05] Connecting to target: {campaign.targetSystem}</p>
            <p className="text-surface-400">[2024-12-08 08:00:07] Target connection established</p>
            <p className="text-surface-400">[2024-12-08 08:00:10] Starting SQL injection tests...</p>
            <p className="text-warning-400">[2024-12-08 08:15:23] FINDING: SQL injection vulnerability detected</p>
            <p className="text-surface-400">[2024-12-08 08:15:24] Generating evidence...</p>
            <p className="text-surface-400">[2024-12-08 08:30:00] Starting authentication bypass tests...</p>
            <p className="text-critical-400">[2024-12-08 08:45:12] CRITICAL: JWT none algorithm accepted</p>
            <p className="text-surface-400">[2024-12-08 08:45:15] Generating remediation suggestions...</p>
            <p className="text-aura-400">[2024-12-08 10:34:00] Campaign progress: {campaign.progress}%</p>
          </div>
        )}
      </div>
    </div>
  );
}

// New Campaign Modal
function NewCampaignModal({ isOpen, onClose, onCreate }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [targetSystem, setTargetSystem] = useState('');
  const [selectedTemplates, setSelectedTemplates] = useState([]);

  if (!isOpen) return null;

  const toggleTemplate = (template) => {
    setSelectedTemplates(prev =>
      prev.includes(template)
        ? prev.filter(t => t !== template)
        : [...prev, template]
    );
  };

  const handleCreate = () => {
    if (!name || !targetSystem || selectedTemplates.length === 0) {
      alert('Please fill in all required fields');
      return;
    }
    onCreate({ name, description, targetSystem, templates: selectedTemplates });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-surface-900/50 dark:bg-black/70 backdrop-blur-sm" onClick={onClose} />

      <div className="relative bg-white dark:bg-surface-800 rounded-2xl shadow-modal w-full max-w-lg max-h-[90vh] overflow-hidden animate-scale-in">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-surface-200 dark:border-surface-700">
          <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
            New Attack Campaign
          </h2>
          <button onClick={onClose} className="p-2 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg">
            <XMarkIcon className="w-5 h-5 text-surface-500" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4 max-h-[60vh] overflow-y-auto">
          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
              Campaign Name *
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., API Security Assessment"
              className="w-full px-4 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe the campaign objectives..."
              rows={2}
              className="w-full px-4 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-aura-500 focus:border-transparent resize-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
              Target System *
            </label>
            <input
              type="text"
              value={targetSystem}
              onChange={(e) => setTargetSystem(e.target.value)}
              placeholder="e.g., core-api-service"
              className="w-full px-4 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
              Attack Templates *
            </label>
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(ATTACK_TEMPLATES).map(([key, config]) => (
                <button
                  key={key}
                  onClick={() => toggleTemplate(key)}
                  className={`
                    flex items-center gap-2 p-3 rounded-lg border-2 text-left transition-all
                    ${selectedTemplates.includes(key)
                      ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/20'
                      : 'border-surface-200 dark:border-surface-700 hover:border-surface-300 dark:hover:border-surface-600'
                    }
                  `}
                >
                  <config.icon className={`w-5 h-5 ${config.color}`} />
                  <span className="text-sm font-medium text-surface-700 dark:text-surface-300">
                    {config.label}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-surface-200 dark:border-surface-700">
          <button
            onClick={onClose}
            className="px-4 py-2 text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg font-medium transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleCreate}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
          >
            <PlayIcon className="w-4 h-4" />
            Launch Campaign
          </button>
        </div>
      </div>
    </div>
  );
}

// Main Component
export default function RedTeamDashboard() {
  const [campaigns, setCampaigns] = useState([]);
  const [findings, setFindings] = useState([]);
  const [selectedCampaign, setSelectedCampaign] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showNewCampaign, setShowNewCampaign] = useState(false);
  const [statusFilter, setStatusFilter] = useState('all');
  const { toast } = useToast();

  // Fetch data
  useEffect(() => {
    const timer = setTimeout(() => {
      setCampaigns(MOCK_CAMPAIGNS);
      setFindings(MOCK_FINDINGS);
      setLoading(false);
    }, 800);
    return () => clearTimeout(timer);
  }, []);

  // Refresh handler
  const handleRefresh = async () => {
    setIsRefreshing(true);
    // Simulate data refresh
    await new Promise((resolve) => setTimeout(resolve, 800));
    setCampaigns(MOCK_CAMPAIGNS);
    setFindings(MOCK_FINDINGS);
    setIsRefreshing(false);
    toast.success('Red Team Dashboard refreshed');
  };

  // Filter campaigns
  const filteredCampaigns = campaigns.filter((campaign) => {
    return statusFilter === 'all' || campaign.status === statusFilter;
  });

  // Stats
  const stats = {
    activeCampaigns: campaigns.filter(c => c.status === 'running').length,
    totalFindings: findings.length,
    criticalFindings: findings.filter(f => f.severity === 'critical').length,
    successRate: campaigns.length > 0
      ? Math.round((campaigns.filter(c => c.status === 'completed').length / campaigns.filter(c => c.status !== 'running').length) * 100) || 0
      : 0,
  };

  const handleCreateCampaign = (campaignData) => {
    const newCampaign = {
      id: `CAM-${String(campaigns.length + 1).padStart(3, '0')}`,
      ...campaignData,
      status: 'running',
      progress: 0,
      startedAt: new Date().toISOString(),
      duration: '0m',
      findingsCount: 0,
      findings: { critical: 0, high: 0, medium: 0, low: 0 },
      mitreTags: ['TA0001'],
    };
    setCampaigns([newCampaign, ...campaigns]);
  };

  if (loading) {
    return <PageSkeleton />;
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <header className="p-6 bg-white dark:bg-surface-800 backdrop-blur-xl border-b border-surface-200/50 dark:border-surface-700/30">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-critical-100 dark:bg-critical-900/30 rounded-lg">
              <ShieldExclamationIcon className="w-6 h-6 text-critical-600 dark:text-critical-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
                Red Team Dashboard
              </h1>
              <p className="text-surface-500 dark:text-surface-400">
                Adversarial testing and security assessment campaigns
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
              onClick={() => setShowNewCampaign(true)}
              className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors"
            >
              <PlusIcon className="w-4 h-4" />
              New Campaign
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            icon={PlayIcon}
            title="Active Campaigns"
            value={stats.activeCampaigns}
            iconColor="aura"
          />
          <MetricCard
            icon={BugAntIcon}
            title="Total Findings"
            value={stats.totalFindings}
            trend={stats.totalFindings > 0 ? 12 : 0}
            iconColor="warning"
          />
          <MetricCard
            icon={ExclamationTriangleIcon}
            title="Critical Findings"
            value={stats.criticalFindings}
            iconColor="critical"
          />
          <MetricCard
            icon={CheckCircleIcon}
            title="Success Rate"
            value={`${stats.successRate}%`}
            iconColor="olive"
          />
        </div>
      </header>

      {/* Filter Tabs */}
      <div className="px-6 py-3 bg-white dark:bg-surface-800 backdrop-blur-xl border-b border-surface-200/50 dark:border-surface-700/30">
        <div className="flex gap-2">
          {[
            { key: 'all', label: 'All Campaigns' },
            { key: 'running', label: 'Running' },
            { key: 'completed', label: 'Completed' },
            { key: 'failed', label: 'Failed' },
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

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden p-6 gap-6">
        {/* Campaign List */}
        <div className="w-[400px] flex-shrink-0 overflow-y-auto space-y-3 pr-2">
          {filteredCampaigns.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-surface-400">
              <FunnelIcon className="w-12 h-12 mb-3" />
              <p className="text-lg font-medium">No campaigns found</p>
              <button
                onClick={() => setShowNewCampaign(true)}
                className="mt-4 flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors"
              >
                <PlusIcon className="w-4 h-4" />
                Create Campaign
              </button>
            </div>
          ) : (
            filteredCampaigns.map((campaign) => (
              <CampaignCard
                key={campaign.id}
                campaign={campaign}
                isSelected={selectedCampaign?.id === campaign.id}
                onClick={() => setSelectedCampaign(
                  selectedCampaign?.id === campaign.id ? null : campaign
                )}
              />
            ))
          )}
        </div>

        {/* Detail Panel */}
        <CampaignDetailPanel
          campaign={selectedCampaign}
          findings={findings}
          onClose={() => setSelectedCampaign(null)}
        />
      </div>

      {/* New Campaign Modal */}
      <NewCampaignModal
        isOpen={showNewCampaign}
        onClose={() => setShowNewCampaign(false)}
        onCreate={handleCreateCampaign}
      />
    </div>
  );
}
